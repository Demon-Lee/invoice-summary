"""Portable personal signature library; never modifies imported source files."""
from __future__ import annotations

import hashlib
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
    if not value or len(value) > 80 or any(ord(c) < 32 for c in value):
        raise ValueError("签名标签不能为空，须在 80 字以内且不含控制字符")
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
    except (OSError, SyntaxError) as exc:
        raise ValueError("签名图片无法读取或文件已损坏") from exc


class SignatureStore:
    revision = staticmethod(revision)

    def __init__(self, application_dir):
        # Construction must not prevent opening the unsigned invoice workflow.
        self.root = Path(os.path.abspath(Path(application_dir) / "signatures"))
        self.config = self.root / "config.json"
        self._revision = None

    @contextmanager
    def _mutation(self):
        # One persistent byte is locked by the OS, so crashes release the lock.
        # Never unlink the lock file: replacing its inode permits two owners.
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

    def _image_path(self, filename):
        if not isinstance(filename, str) or not re.fullmatch(
            r"images/[0-9a-f]{32}-[0-9a-f]{64}\.png", filename
        ):
            raise ValueError("签名图片相对路径无效")
        return _safe_path(self.root / filename)

    def read(self):
        _safe_path(self.root)
        _safe_path(self.config)
        if not self.config.exists():
            if self.root.exists():
                for child in self.root.iterdir():
                    child = _safe_path(child)
                    if child.name == ".lock" and child.is_file():
                        continue
                    if child.name != "images" or not child.is_dir() or any(child.iterdir()):
                        raise ValueError("签名配置缺失，已有签名文件已保留，请恢复配置")
            self._revision = None
            return {"version": 1, "items": [], "bindings": dict.fromkeys(_KEYS)}
        try:
            if self.config.stat().st_size > 1024 * 1024:
                raise ValueError("签名配置文件过大")
            raw = self.config.read_bytes()
            config = json.loads(raw.decode("utf-8"))
            if not isinstance(config, dict) or config.get("version") != 1:
                raise ValueError("签名配置版本无效")
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
                if _label(label) != label or identifier in ids or label.casefold() in labels:
                    raise ValueError("签名标签或标识重复、无效")
                self._image_path(item["file"])
                if item["file"] != f"images/{identifier}-{digest}.png" or item["file"] in files:
                    raise ValueError("签名图片记录不一致")
                ids.add(identifier)
                labels.add(label.casefold())
                files.add(item["file"])
            if set(bindings) != set(_KEYS) or any(
                value is not None and (not isinstance(value, str) or value not in ids)
                for value in bindings.values()
            ):
                raise ValueError("签名位置关联无效")
            self._revision = hashlib.sha256(raw).hexdigest()
            return config
        except (KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("签名配置已损坏，原文件已保留，请恢复配置") from exc

    def _write(self, path, data):
        path = _safe_path(path)
        _safe_path(path.parent)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".signature-", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            _safe_path(path)
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
        # The mutation lock serializes cooperating instances; also detect changes
        # from external config editors before publication.
        _safe_path(self.config)
        if self.config.exists():
            if self.config.stat().st_size > 1024 * 1024:
                raise ValueError("签名配置已被其他窗口修改，请重新打开签名管理")
            current = hashlib.sha256(self.config.read_bytes()).hexdigest()
        else:
            current = None
        if current != self._revision:
            raise ValueError("签名配置已被其他窗口修改，请重新打开签名管理")
        self._write(self.config, json.dumps(config, ensure_ascii=False, indent=2).encode("utf-8"))

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

    @_serialized
    def import_image(self, label, source, item_id=None, expected_revision=None):
        config = self.read()
        self._expected(config, expected_revision)
        label = self._unique(config, label, item_id)
        if item_id is not None:
            item = self._item(config, item_id)
        else:
            if len(config["items"]) >= 1000:
                raise ValueError("签名数量已达上限，请先删除不需要的签名")
            item_id = uuid.uuid4().hex
            item = None
        source = _safe_path(source)
        if source.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            raise ValueError("签名图片仅支持 PNG、JPG、JPEG")
        try:
            with source.open("rb") as stream:
                data = stream.read(_MAX_BYTES + 1)
        except OSError as exc:
            raise OSError(f"无法读取签名图片：{exc}") from exc
        if len(data) > _MAX_BYTES:
            raise ValueError("签名图片超过 32 MB，请先缩小图片")
        data = _png(data, normalize=True)
        digest = hashlib.sha256(data).hexdigest()
        filename = f"images/{item_id}-{digest}.png"
        path = self._image_path(filename)
        old_file = item["file"] if item else None
        created = not path.exists()
        if created:
            self._write(path, data)
        else:
            if path.read_bytes() != data:
                # Reimporting the original is the repair path for a damaged copy.
                if path == source:
                    raise ValueError("不能覆盖导入源图片，请从原始图片重新导入")
                self._write(path, data)
        record = {"id": item_id, "label": label, "file": filename, "sha256": digest}
        if item is None:
            config["items"].append(record)
        else:
            item.update(record)
        try:
            self._save(config)
        except (OSError, ValueError):
            if created:
                # Remove only our unpublished image; another instance may have
                # published a config referring to the same content meanwhile.
                try:
                    _safe_path(self.config)
                    published = json.loads(self.config.read_text(encoding="utf-8")) if self.config.exists() else {"items": []}
                    if not any(record.get("file") == filename for record in published["items"]):
                        self._image_path(filename).unlink(missing_ok=True)
                except (OSError, ValueError, KeyError, TypeError, AttributeError):
                    pass
            raise
        if old_file and old_file != filename:
            try:
                old_path = self._image_path(old_file)
                if old_path != source:
                    old_path.unlink(missing_ok=True)
            except (OSError, ValueError):
                pass  # Config is committed; unused image cleanup is best effort.
        return item_id

    @_serialized
    def rename(self, item_id, label, expected_revision=None):
        config = self.read()
        self._expected(config, expected_revision)
        item = self._item(config, item_id)
        item["label"] = self._unique(config, label, item_id)
        self._save(config)

    @_serialized
    def delete(self, item_id, expected_revision=None):
        config = self.read()
        self._expected(config, expected_revision)
        item = self._item(config, item_id)
        config["items"].remove(item)
        config["bindings"] = {key: None if value == item_id else value
                              for key, value in config["bindings"].items()}
        self._save(config)
        try:
            self._image_path(item["file"]).unlink(missing_ok=True)
        except (OSError, ValueError):
            pass  # The removal and cleared bindings are already saved.

    @_serialized
    def assign(self, slot_key, item_id_or_None, expected_revision=None):
        if slot_key not in _KEYS:
            raise ValueError("签名位置无效")
        config = self.read()
        self._expected(config, expected_revision)
        if item_id_or_None is not None:
            self._item(config, item_id_or_None)
        config["bindings"][slot_key] = item_id_or_None
        self._save(config)

    def _bytes(self, item):
        path = self._image_path(item["file"])
        try:
            with path.open("rb") as stream:
                data = stream.read(_MAX_BYTES + 1)
        except OSError as exc:
            raise ValueError(f"签名“{item['label']}”图片缺失或无法读取，请重新导入") from exc
        if len(data) > _MAX_BYTES or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError(f"签名“{item['label']}”图片指纹不符，请重新导入")
        _png(data)
        return data

    def image_bytes(self, item_id):
        return self._bytes(self._item(self.read(), item_id))

    @_serialized
    def snapshot(self, expected_revision=None):
        config = self.read()
        self._expected(config, expected_revision)
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
        config = self.read()
        validated = [(item, self._bytes(item)) for item in config["items"]]
        destination = SignatureStore(application_dir)
        if destination.root == self.root:
            return
        # Refuse malformed destination config instead of silently overwriting it.
        with destination._mutation():
            previous = destination.read()
            retained = {item["file"] for item in previous["items"]}
            created = []
            try:
                for item, data in validated:
                    path = destination._image_path(item["file"])
                    if not path.exists() and item["file"] not in retained:
                        created.append(path)
                    destination._write(path, data)
                destination._save(config)
            except (OSError, ValueError):
                for path in created:
                    try:
                        _safe_path(path).unlink(missing_ok=True)
                    except (OSError, ValueError):
                        pass
                raise
