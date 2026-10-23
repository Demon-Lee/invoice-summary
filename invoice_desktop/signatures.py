"""Portable personal signature library; never modifies imported source files."""
from __future__ import annotations

import hashlib
from collections import OrderedDict
from contextlib import contextmanager
from functools import wraps
import io
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import threading
from types import MappingProxyType
import uuid
import warnings

from PIL import Image, ImageChops, ImageOps

SLOTS = (
    ("acceptance_handler", "验收", "经办人"),
    ("acceptance_inspector", "验收", "验收人"),
    ("issue_keeper", "领用", "保管人"),
    ("issue_recipient", "领用", "领用人"),
)
_KEYS = tuple(slot[0] for slot in SLOTS)
_MAX_BYTES = 32 * 1024 * 1024
_MAX_PIXELS = 24_000_000
_ID = re.compile(r"[0-9a-f]{32}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_MUTATIONS = threading.RLock()
_CACHE_BYTES = 16 * 1024 * 1024
_CACHE_ENTRIES = 32
_VALIDATION_ENTRIES = 256


def revision(config):
    """Deterministic token for the exact library state shown in a confirmation."""
    return hashlib.sha256(json.dumps(config, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _serialized(method):
    @wraps(method)
    def mutate(self, *args, **kwargs):
        with self._mutation():
            return method(self, *args, **kwargs)
    return mutate


def _safe_path(path):
    """Reject symlinks and Windows junctions on every existing component."""
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("签名路径不能包含符号链接或目录联接")
    return path


def _label(value):
    if not isinstance(value, str):
        raise ValueError("签名标签必须是文字")
    value = value.strip()
    if (not value or len(value) > 80 or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value)
            or any(c in '<>:"/\\|?*' for c in value) or value.endswith((".", " "))
            or re.fullmatch(r"(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9¹²³]|LPT[1-9¹²³])",
                            value.split(".", 1)[0].rstrip(" "), re.IGNORECASE)):
        raise ValueError("签名标签须为 1–80 字的有效 Windows 文件名，不能含禁用字符或保留名称")
    return value


def _png(data, *, normalize=False):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as original:
                if original.format not in (("PNG", "JPEG") if normalize else ("PNG",)):
                    raise ValueError("签名图片仅支持 PNG、JPG、JPEG")
                if original.width * original.height > _MAX_PIXELS:
                    raise ValueError("签名图片像素过多，请先缩小图片")
                if getattr(original, "n_frames", 1) != 1:
                    raise ValueError("签名图片必须是单帧静态图片")
                original.load()
                rgba = ImageOps.exif_transpose(original).convert("RGBA")
        if normalize:
            # Composite on white for conservative ink detection. The one-level
            # threshold retains even very faint strokes; never trim by contrast
            # relative to the darkest pixel, which can erase a faint signature.
            white = Image.new("RGBA", rgba.size, "white")
            visible = Image.alpha_composite(white, rgba).convert("RGB")
            difference = ImageChops.difference(visible, Image.new("RGB", rgba.size, "white"))
            channels = difference.split()
            ink = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
            bounds = ink.getbbox()
            if bounds is None:
                raise ValueError("图片为空白，无法识别签名笔迹")
            rgba = rgba.crop(bounds)
        output = io.BytesIO()
        rgba.save(output, format="PNG")
        result = output.getvalue()
        if len(result) > _MAX_BYTES:
            raise ValueError("签名图片过大，请先缩小图片")
        return result
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("签名图片像素过多，请先缩小图片") from exc
    except (OSError, SyntaxError, EOFError, OverflowError) as exc:
        raise ValueError("签名图片无法读取或文件已损坏") from exc


class SignatureStore:
    revision = staticmethod(revision)

    def __init__(self, application_dir):
        # Construction must not prevent opening the unsigned invoice workflow.
        self.root = Path(os.path.abspath(Path(application_dir) / "signatures"))
        self.config = self.root / "config.json"
        self._revision = None
        self._image_cache = OrderedDict()
        self._image_cache_bytes = 0
        self._validated = OrderedDict()

    @property
    def image_dir(self):
        return self.root / "签名图片"

    @contextmanager
    def _mutation(self):
        # Public entry points take this lock once. Internal helpers never call a
        # public entry point: Windows byte locks are not reentrant across handles.
        with _MUTATIONS:
            _safe_path(self.root).mkdir(parents=True, exist_ok=True)
            lock_path = _safe_path(self.root / ".lock")
            with lock_path.open("a+b") as stream:
                if stream.seek(0, os.SEEK_END) == 0:
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                try:
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as exc:
                    raise ValueError("另一个软件窗口正在修改签名，请稍后重试") from exc
                try:
                    yield
                finally:
                    try:
                        stream.seek(0)
                        if os.name == "nt":
                            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                        else:
                            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass  # Closing the handle also releases the OS lock.

    @staticmethod
    def _expected(config, expected_revision):
        if expected_revision is not None and revision(config) != expected_revision:
            raise ValueError("签名配置已改变，请刷新列表并重新确认受影响位置")

    def _image_path(self, filename, *, legacy=False):
        if not isinstance(filename, str):
            raise ValueError("签名图片相对路径无效")
        if legacy:
            if not re.fullmatch(r"images/[0-9a-f]{32}-[0-9a-f]{64}\.png", filename):
                raise ValueError("旧版签名图片相对路径无效")
        else:
            prefix, separator, name = filename.partition("/")
            if (prefix != "签名图片" or not separator or "/" in name or "\\" in name
                    or Path(name).suffix.lower() not in (".png", ".jpg", ".jpeg")
                    or _label(Path(name).stem) != Path(name).stem):
                raise ValueError("签名图片相对路径无效")
        return _safe_path(self.root / filename)

    @staticmethod
    def _raw_file(path):
        path = _safe_path(path)
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError("签名图片必须为普通文件")
        with path.open("rb") as stream:
            data = stream.read(_MAX_BYTES + 1)
        if len(data) > _MAX_BYTES:
            raise ValueError("签名图片超过 32 MB，请先缩小图片")
        return data

    def _normalized(self, data, *, size=None):
        """Reuse pixel work only for the exact bytes just read and hashed."""
        digest = hashlib.sha256(data).hexdigest()
        key = (digest, size)
        if key in self._image_cache:
            self._image_cache.move_to_end(key)
            return self._image_cache[key]
        if size is None:
            result = _png(data, normalize=True)
            self._validated[digest] = None
            self._validated.move_to_end(digest)
            while len(self._validated) > _VALIDATION_ENTRIES:
                self._validated.popitem(last=False)
        else:
            with Image.open(io.BytesIO(self._normalized(data))) as source:
                thumbnail = source.convert("RGBA")
            thumbnail.thumbnail(size, Image.Resampling.LANCZOS)
            output = io.BytesIO()
            thumbnail.save(output, format="PNG")
            result = output.getvalue()
        if len(result) <= _CACHE_BYTES:
            self._image_cache[key] = result
            self._image_cache_bytes += len(result)
            while (self._image_cache_bytes > _CACHE_BYTES
                   or len(self._image_cache) > _CACHE_ENTRIES):
                _, evicted = self._image_cache.popitem(last=False)
                self._image_cache_bytes -= len(evicted)
        return result

    def _validate_image(self, data):
        digest = hashlib.sha256(data).hexdigest()
        if digest in self._validated:
            self._validated.move_to_end(digest)
        else:
            self._normalized(data)
        return digest

    def _load(self):
        """Read/validate config only; never synchronize or acquire another lock."""
        _safe_path(self.config)
        if not self.config.exists():
            legacy = _safe_path(self.root / "images")
            backups = _safe_path(self.root / "备份")
            if ((legacy.exists() and (not legacy.is_dir() or any(legacy.iterdir())))
                    or backups.exists()):
                raise ValueError("签名配置缺失，已有签名文件已保留，请恢复配置")
            self._revision = None
            return {"version": 2, "items": [], "bindings": dict.fromkeys(_KEYS),
                    "issues": [], "attention": {}}, None
        try:
            if self.config.stat().st_size > 1024 * 1024:
                raise ValueError("签名配置文件过大")
            raw = self.config.read_bytes()
            config = json.loads(raw.decode("utf-8"))
            if not isinstance(config, dict) or config.get("version") not in (1, 2):
                raise ValueError("签名配置版本无效")
            version = config["version"]
            items, bindings = config["items"], config["bindings"]
            if not isinstance(items, list) or len(items) > 1000 or not isinstance(bindings, dict):
                raise ValueError("签名配置结构无效")
            ids, labels, files = set(), set(), set()
            for item in items:
                if not isinstance(item, dict) or set(item) != {"id", "label", "file", "sha256"}:
                    raise ValueError("签名记录无效")
                identifier, label, digest = item["id"], item["label"], item["sha256"]
                if not isinstance(identifier, str) or not _ID.fullmatch(identifier):
                    raise ValueError("签名标识无效")
                if not isinstance(digest, str) or not _HASH.fullmatch(digest):
                    raise ValueError("签名图片指纹无效")
                if version == 1:
                    valid_label = (isinstance(label, str) and label == label.strip()
                                   and 0 < len(label) <= 80 and not any(ord(c) < 32 for c in label))
                else:
                    valid_label = _label(label) == label
                if not valid_label or identifier in ids or label.casefold() in labels:
                    raise ValueError("签名标签或标识重复、无效")
                self._image_path(item["file"], legacy=version == 1)
                if ((version == 1 and item["file"] != f"images/{identifier}-{digest}.png")
                        or (version == 2 and Path(item["file"]).stem != label)
                        or item["file"].casefold() in files):
                    raise ValueError("签名图片记录不一致")
                ids.add(identifier)
                labels.add(label.casefold())
                files.add(item["file"].casefold())
            if set(bindings) != set(_KEYS) or any(
                value is not None and (not isinstance(value, str) or value not in ids)
                for value in bindings.values()
            ):
                raise ValueError("签名位置关联无效")
            if version == 2:
                issues, attention = config["issues"], config["attention"]
                if (not isinstance(issues, list) or any(not isinstance(v, str) for v in issues)
                        or not isinstance(attention, dict)
                        or any(k not in _KEYS or not isinstance(v, str) or not v
                               for k, v in attention.items())
                        or any(bindings[k] is not None for k in attention)):
                    raise ValueError("签名问题或待确认位置记录无效")
            self._revision = hashlib.sha256(raw).hexdigest()
            return config, raw
        except (KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("签名配置已损坏，原文件已保留，请恢复配置") from exc

    def _write(self, path, data, *, exclusive=False):
        """Publish complete bytes. Exclusive mode never overwrites a user file."""
        path = _safe_path(path)
        _safe_path(path.parent).mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".signature-", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            _safe_path(path)
            if exclusive:
                if os.name == "nt":
                    os.rename(temporary, path)  # Windows rename refuses an existing destination.
                else:
                    os.link(temporary, path)  # Same property on POSIX, including races.
                    temporary.unlink()
            else:
                os.replace(temporary, path)
        except OSError as exc:
            raise OSError(f"无法保存签名文件：{exc}") from exc
        finally:
            try:
                if temporary is not None and temporary.exists():
                    temporary.unlink()
            except OSError:
                pass

    def _save(self, config):
        _safe_path(self.config)
        if self.config.exists():
            if self.config.stat().st_size > 1024 * 1024:
                raise ValueError("签名配置已被其他窗口修改，请重新打开签名管理")
            current = hashlib.sha256(self.config.read_bytes()).hexdigest()
        else:
            current = None
        if current != self._revision:
            raise ValueError("签名配置已被其他窗口修改，请重新打开签名管理")
        raw = json.dumps(config, ensure_ascii=False, indent=2).encode("utf-8")
        if len(raw) > 1024 * 1024:
            raise ValueError("签名配置文件过大，请减少图片或文件夹中的问题文件")
        self._write(self.config, raw)
        self._revision = hashlib.sha256(raw).hexdigest()

    def _available(self, label, allowed=None):
        for path in self.image_dir.iterdir():
            if (path.suffix.lower() in (".png", ".jpg", ".jpeg")
                    and path.stem.casefold() == label.casefold()
                    and path.name != allowed):
                raise ValueError(f"标签“{label}”已有同名文件，请先处理图片文件夹中的冲突")

    def _migrate(self, config, raw):
        # Legacy images remain untouched outside the active scan. A byte-exact
        # config backup plus those originals makes migration recoverable.
        _safe_path(self.image_dir).mkdir(parents=True, exist_ok=True)
        used = {p.stem.casefold() for p in self.image_dir.iterdir()
                if p.suffix.lower() in (".png", ".jpg", ".jpeg")}
        for item in config["items"]:
            try:
                used.add(_label(item["label"]).casefold())
            except ValueError:
                pass
        migrated, planned, issues = [], [], []
        for item in config["items"]:
            label = item["label"]
            try:
                _label(label)
            except ValueError:
                base = re.sub(r'[<>:"/\\|?*\x00-\x1f\ud800-\udfff]', "_", label).strip().rstrip(". ") or "签名"
                base = base[:80].rstrip(". ") or "签名"
                try:
                    _label(base)
                except ValueError:
                    base = "_" + base[:79]
                label, number = base, 2
                while label.casefold() in used:
                    suffix = f"_{number}"
                    label = base[:80 - len(suffix)].rstrip(". ") + suffix
                    number += 1
                used.add(label.casefold())
                display = item["label"].encode("utf-8", "backslashreplace").decode("utf-8")
                issues.append(f"旧版迁移：标签“{display}”已改为有效文件名“{label}”。")
            data = self._raw_file(self._image_path(item["file"], legacy=True))
            if hashlib.sha256(data).hexdigest() != item["sha256"]:
                raise ValueError("旧版签名图片指纹不符，原文件已保留，请先恢复或修复旧版配置")
            self._normalized(data)
            filename = f"签名图片/{label}.png"
            path = self._image_path(filename)
            self._available(label, path.name)
            if path.exists() and self._raw_file(path) != data:
                raise ValueError(f"迁移目标“{path.name}”已存在不同图片，原文件已保留，请先处理冲突")
            planned.append((path, data))
            migrated.append(dict(item, label=label, file=filename))
        backup = self.root / "备份" / ("版本1-" + hashlib.sha256(raw).hexdigest()[:16]) / "config.json"
        if backup.exists():
            if _safe_path(backup).read_bytes() != raw:
                raise ValueError("旧版配置备份冲突，请保留文件并检查备份文件夹")
        else:
            self._write(backup, raw, exclusive=True)
        result = {"version": 2, "items": migrated, "bindings": dict(config["bindings"]),
                  "issues": issues, "attention": {}}
        created = []
        try:
            for path, data in planned:
                if not path.exists():
                    self._write(path, data, exclusive=True)
                    created.append((path, hashlib.sha256(data).hexdigest()))
                elif self._raw_file(path) != data:
                    raise ValueError("迁移过程中目标图片已改变，请重新检查图片文件夹")
            self._save(result)
        except (OSError, ValueError):
            for path, digest in reversed(created):
                self._remove_own(path, digest)
            raise
        return result

    def _scan(self, config):
        issues = [v for v in config["issues"] if v.startswith("旧版迁移：")]
        groups = {}
        for path in sorted(self.image_dir.iterdir(), key=lambda p: (p.name.casefold(), p.name)):
            if path.suffix.lower() in (".png", ".jpg", ".jpeg"):
                groups.setdefault(path.stem.casefold(), []).append(path)
        previous = {item["file"]: item for item in config["items"]}
        records = []
        changed = {}
        for paths in groups.values():
            if len(paths) != 1:
                issues.append("同名标签冲突，已跳过：" + "、".join(p.name for p in paths))
                continue
            path = paths[0]
            try:
                if _label(path.stem) != path.stem:
                    raise ValueError("文件名含首尾空格")
                data = self._raw_file(path)
                # Always read/hash current bytes; unchanged content needs no pixel work.
                digest = self._validate_image(data)
            except (OSError, ValueError) as exc:
                issues.append(f"已跳过“{path.name}”：{exc}")
                continue
            filename = f"签名图片/{path.name}"
            old = previous.get(filename)
            if len(records) >= 1000:
                issues.append(f"已跳过“{path.name}”：签名数量上限为 1000 张")
                continue
            identifier = old["id"] if old else uuid.uuid4().hex
            records.append({"id": identifier, "label": path.stem, "file": filename, "sha256": digest})
            if old and old["sha256"] != digest:
                changed[identifier] = f"签名“{old['label']}”图片已从文件夹外部替换，请重新选择签名或不使用签名。"
        retained = {item["id"] for item in records}
        for old in config["items"]:
            if old["id"] not in retained:
                changed[old["id"]] = f"签名“{old['label']}”已删除、改名或无法使用，请重新选择签名或不使用签名。"
        bindings, attention = dict(config["bindings"]), dict(config["attention"])
        for slot, identifier in bindings.items():
            if identifier in changed:
                attention[slot] = changed[identifier]
                bindings[slot] = None
        recovery = _safe_path(self.root / ".recovery")
        if recovery.exists() and (not recovery.is_dir() or any(recovery.iterdir())):
            issues.append("存在操作恢复备份（signatures/.recovery），请保留备份并核对图片及配置。")
        issues = [v.encode("utf-8", "backslashreplace").decode("utf-8") for v in issues]
        return {"version": 2, "items": records, "bindings": bindings,
                "issues": issues, "attention": attention}

    def _read(self):
        config, raw = self._load()
        if config["version"] == 1:
            config = self._migrate(config, raw)
        _safe_path(self.image_dir).mkdir(parents=True, exist_ok=True)
        synchronized = self._scan(config)
        if synchronized != config or self._revision is None:
            self._save(synchronized)
        return synchronized

    @_serialized
    def read(self):
        return self._read()

    @staticmethod
    def _item(config, item_id):
        for item in config["items"]:
            if item["id"] == item_id:
                return item
        raise ValueError("所选签名已不存在，请重新选择")

    @staticmethod
    def _unique(config, label, item_id=None):
        label = _label(label)
        if any(item["id"] != item_id and item["label"].casefold() == label.casefold()
               for item in config["items"]):
            raise ValueError("签名标签已存在，请使用不同标签")
        return label

    def _remove_own(self, path, digest):
        try:
            if hashlib.sha256(self._raw_file(path)).hexdigest() == digest:
                path.unlink()
                return True
        except (OSError, ValueError):
            pass
        return False

    @staticmethod
    def _clean_recovery(directory, backup=None):
        # Only known files in this uniquely created directory are removed.
        try:
            if backup is not None:
                _safe_path(backup).unlink(missing_ok=True)
            _safe_path(directory / "config.before.json").unlink(missing_ok=True)
            directory.rmdir()
            directory.parent.rmdir()
        except (OSError, ValueError):
            pass  # Retained originals are outside the active scan and reported.

    def _commit_files(self, config, *, old=None, filename=None, data=None):
        """Stage an old active file, publish its successor, then commit config.

        Failures restore the staged original. A collision during rollback keeps
        the original and its config in .recovery instead of overwriting a file.
        """
        directory = backup = old_path = new_path = None
        published = False
        digest = hashlib.sha256(data).hexdigest() if data is not None else None
        try:
            if old is not None:
                old_path = self._image_path(old["file"])
                directory = _safe_path(self.root / ".recovery" / uuid.uuid4().hex)
                directory.mkdir(parents=True)
                self._write(directory / "config.before.json", self.config.read_bytes(), exclusive=True)
                backup = directory / old_path.name
                os.rename(_safe_path(old_path), backup)
                staged = self._raw_file(backup)
                if hashlib.sha256(staged).hexdigest() != old["sha256"]:
                    raise ValueError("签名图片在操作过程中改变，请刷新后重新确认")
            if filename is not None:
                new_path = self._image_path(filename)
                self._available(new_path.stem)
                self._write(new_path, data, exclusive=True)
                published = True
            self._save(config)
        except (OSError, ValueError) as exc:
            restored = True
            if published and not self._remove_own(new_path, digest):
                restored = False
            if backup is not None and backup.exists():
                try:
                    # Exclusive publication handles an externally recreated path.
                    self._write(old_path, self._raw_file(backup), exclusive=True)
                except (OSError, ValueError):
                    restored = False
            if restored and directory is not None:
                self._clean_recovery(directory, backup)
            if not restored:
                raise ValueError("操作未完成且文件夹发生变化，原图及操作前配置已保存在 signatures/.recovery，请保留并恢复备份") from exc
            raise
        if directory is not None:
            self._clean_recovery(directory, backup)

    @_serialized
    def import_image(self, label, source, item_id=None, expected_revision=None):
        config = self._read()
        self._expected(config, expected_revision)
        label = self._unique(config, label, item_id)
        item = self._item(config, item_id) if item_id is not None else None
        if item is None and len(config["items"]) >= 1000:
            raise ValueError("签名数量已达上限，请先删除不需要的签名")
        source = _safe_path(source)
        if source.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            raise ValueError("签名图片仅支持 PNG、JPG、JPEG")
        data = self._raw_file(source)
        self._normalized(data)
        filename = f"签名图片/{label}{source.suffix.lower()}"
        self._available(label, Path(item["file"]).name if item else None)
        item_id = item["id"] if item else uuid.uuid4().hex
        record = {"id": item_id, "label": label, "file": filename,
                  "sha256": hashlib.sha256(data).hexdigest()}
        if item is None:
            config["items"].append(record)
        else:
            config["items"] = [record if v["id"] == item_id else v for v in config["items"]]
        self._commit_files(config, old=item, filename=filename, data=data)
        return item_id

    @_serialized
    def rename(self, item_id, label, expected_revision=None):
        config = self._read()
        self._expected(config, expected_revision)
        item = self._item(config, item_id)
        label = self._unique(config, label, item_id)
        if label == item["label"]:
            return
        self._available(label, Path(item["file"]).name)
        data = self._original_bytes(item)
        record = dict(item, label=label, file=f"签名图片/{label}{Path(item['file']).suffix}")
        config["items"] = [record if v["id"] == item_id else v for v in config["items"]]
        self._commit_files(config, old=item, filename=record["file"], data=data)

    @_serialized
    def delete(self, item_id, expected_revision=None):
        config = self._read()
        self._expected(config, expected_revision)
        item = self._item(config, item_id)
        config["items"].remove(item)
        config["bindings"] = {key: None if value == item_id else value
                              for key, value in config["bindings"].items()}
        self._commit_files(config, old=item)

    @_serialized
    def assign(self, slot_key, item_id_or_None, expected_revision=None):
        if slot_key not in _KEYS:
            raise ValueError("签名位置无效")
        config = self._read()
        self._expected(config, expected_revision)
        if item_id_or_None is not None:
            self._item(config, item_id_or_None)
        config["bindings"][slot_key] = item_id_or_None
        config["attention"].pop(slot_key, None)
        self._save(config)

    @_serialized
    def assign_many(self, bindings, expected_revision=None):
        """Commit explicitly chosen positions together after validating all of them."""
        if (not isinstance(bindings, dict) or not bindings
                or any(key not in _KEYS for key in bindings)):
            raise ValueError("签名位置无效")
        config = self._read()
        self._expected(config, expected_revision)
        for item_id in bindings.values():
            if item_id is not None:
                self._item(config, item_id)
        for key, item_id in bindings.items():
            config["bindings"][key] = item_id
            config["attention"].pop(key, None)
        self._save(config)

    def _original_bytes(self, item):
        try:
            data = self._raw_file(self._image_path(item["file"]))
        except OSError as exc:
            raise ValueError(f"签名“{item['label']}”图片缺失或无法读取，请刷新列表") from exc
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError(f"签名“{item['label']}”图片已改变，请刷新列表后重新确认")
        return data

    def _bytes(self, item, *, size=None):
        return self._normalized(self._original_bytes(item), size=size)

    @_serialized
    def image_bytes(self, item_id, expected_revision=None, *, size=None):
        if size is not None:
            if (not isinstance(size, (tuple, list)) or len(size) != 2
                    or any(type(n) is not int or not 1 <= n <= 1024 for n in size)):
                raise ValueError("签名预览尺寸无效")
            size = tuple(size)
        # A preview reads the shown config and selected original only. Discovery
        # remains in read/mutators/snapshot; export never trusts this UI shortcut.
        config, _ = self._load()
        if config["version"] == 1:
            config = self._read()
        self._expected(config, expected_revision)
        return self._bytes(self._item(config, item_id), size=size)

    @_serialized
    def snapshot(self, expected_revision=None):
        config = self._read()
        self._expected(config, expected_revision)
        if config["attention"]:
            raise ValueError("签字位置存在待确认的图片变化，请重新选择签名或明确选择不使用签名")
        assigned = set(config["bindings"].values()) - {None}
        images, labels = {}, {}
        for item in config["items"]:
            if item["id"] in assigned:
                images[item["id"]] = self._bytes(item)
                labels[item["id"]] = item["label"]
        return MappingProxyType({"images": MappingProxyType(images),
                                 "labels": MappingProxyType(labels),
                                 "bindings": MappingProxyType(dict(config["bindings"]))})

    @_serialized
    def copy_to(self, application_dir):
        # Do not call read/_read/_load on the source. Builds must copy a legacy
        # library byte-for-byte before any migration happens in the destination.
        destination = SignatureStore(application_dir)
        if destination.root == self.root:
            return
        if (self.root in destination.root.parents or destination.root in self.root.parents):
            raise ValueError("签名复制的源目录和目标目录不能互相包含")
        with destination._mutation():
            if any(p.name != ".lock" for p in destination.root.iterdir()):
                raise ValueError("签名复制目标目录必须为空，已有文件已保留")
            files, directories = [], []
            def collect(directory):
                for path in directory.iterdir():
                    path = _safe_path(path)
                    if path == self.root / ".lock":
                        continue  # Locks are process state, never copied.
                    mode = path.stat().st_mode
                    relative = path.relative_to(self.root)
                    if stat.S_ISDIR(mode):
                        directories.append(relative)
                        collect(path)
                    elif stat.S_ISREG(mode):
                        files.append((relative, path))
                    else:
                        raise ValueError("签名个人目录包含非普通文件，请保留原目录并检查")
            collect(self.root)
            # Preserve all ordinary private files, including unsupported images,
            # old backups and incomplete-operation recovery files.
            for relative in directories:
                _safe_path(destination.root / relative).mkdir(parents=True, exist_ok=False)
            for relative, path in files:
                destination._write(destination.root / relative, _safe_path(path).read_bytes(), exclusive=True)
            destination._read()
