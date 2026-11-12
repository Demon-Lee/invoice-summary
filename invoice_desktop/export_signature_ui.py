"""Choose remembered PDF signatures without leaving the export dialog."""

from queue import Empty
import tkinter as tk
from tkinter import ttk

from PIL import ImageTk

from .dialogs import messagebox
from .signature_tasks import SignatureTasks
from .signature_ui import open_signature_manager
from .signatures import SLOTS
from .ui import FONT, PALETTE, surface


class ExportSignaturePicker:
    def __init__(self, parent, store, on_state_change):
        self.store = store
        self.on_state_change = on_state_change
        self.frame = ttk.Frame(parent)
        self.dialog = parent.winfo_toplevel()
        self.closed = False
        self.saving = False
        self.loading = False
        self.ready = False
        self.revision = None
        self.data = None
        self.draft = {}
        self.pending_attention = set()
        self.ids = [None]
        self.selectors = {}
        self.previews = {}
        self.photos = {}
        self.preview_keys = {}
        self.preview_widths = {}
        self.preview_request = None
        self.read_request = None
        self.save_request = None
        self.callback = None
        self.poll_id = None
        self.tasks = SignatureTasks(store)
        self.include = tk.BooleanVar(master=self.frame, value=False)

        header = ttk.Frame(self.frame)
        header.pack(fill="x", pady=(0, 10))
        self.checkbox = ttk.Checkbutton(header, text="添加签名", variable=self.include,
                                        command=self._toggle, state="disabled")
        self.checkbox.pack(side="left")
        self.manage_button = ttk.Button(header, text="签名管理", command=self._manage,
                                        style="ExportAction.TButton", cursor="hand2")
        self.manage_button.pack(side="right")
        self.cards = ttk.Frame(self.frame)
        self.cards.pack(fill="x")
        self.cards.columnconfigure((0, 1), weight=1, uniform="export-signature-cards")
        self._build_cards()
        self.status = ttk.Label(self.frame, text="正在读取签名库…", wraplength=650,
                                foreground="#946522", justify="left")
        self.status.pack(fill="x", pady=(6, 0))
        self.refresh(initial=True)
        self.poll_id = self.frame.after(50, self._poll)

    @property
    def can_confirm(self):
        return not (self.loading or self.saving) and (self.ready or not self.include.get())

    def _build_cards(self):
        style = ttk.Style(self.frame)
        style.configure("ExportSignature.TCombobox", font=(FONT, 10), padding=(7, 6),
                        arrowsize=14, foreground=PALETTE["text"], fieldbackground="#fafbfd",
                        background="#fafbfd", bordercolor="#d9e1eb", arrowcolor=PALETTE["blue"])
        style.map("ExportSignature.TCombobox",
                  fieldbackground=[("disabled", "#f0f3f7"), ("readonly", "#fafbfd")],
                  selectbackground=[("readonly", "#fafbfd")],
                  selectforeground=[("readonly", PALETTE["text"])])
        style.configure("ExportSignaturePreview.TLabel", background="#f8fafc",
                        foreground=PALETTE["muted"], font=(FONT, 9))
        cards = {}
        for key, sheet, role in SLOTS:
            if sheet not in cards:
                card = surface(self.cards, padding=12)
                index = len(cards)
                card.grid(row=0, column=index, sticky="nsew", padx=(0, 6) if index == 0 else (6, 0))
                card.columnconfigure((0, 1), weight=1, uniform="export-signature-fields")
                ttk.Label(card, text=f"{sheet}单", style="Section.TLabel").grid(
                    row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
                cards[sheet] = (card, 0)
            card, column = cards[sheet]
            padding = (0, 6) if column == 0 else (6, 0)
            ttk.Label(card, text=role, style="Muted.TLabel").grid(
                row=1, column=column, sticky="w", padx=padding, pady=(0, 5))
            combo = ttk.Combobox(card, state="disabled", width=1, style="ExportSignature.TCombobox")
            combo.grid(row=2, column=column, sticky="ew", padx=padding)
            combo.bind("<<ComboboxSelected>>", lambda event, slot=key: self._choose(slot))
            for sequence in ("<MouseWheel>", "<Shift-MouseWheel>", "<Button-4>", "<Button-5>"):
                combo.bind(sequence, lambda event: "break")
            box = tk.Frame(card, bg="#f8fafc", height=82, width=1,
                           highlightthickness=1, highlightbackground=PALETTE["line"])
            box.grid(row=3, column=column, sticky="ew", padx=padding, pady=(9, 0))
            box.grid_propagate(False)
            box.rowconfigure(0, weight=1)
            box.columnconfigure(0, weight=1)
            preview = ttk.Label(box, text="正在读取…", anchor="center", justify="center",
                                wraplength=130, style="ExportSignaturePreview.TLabel")
            preview.grid(row=0, column=0, sticky="nsew")
            preview.bind("<Configure>", lambda event, slot=key: self._preview_resized(slot, event.width))
            self.selectors[key], self.previews[key] = combo, preview
            cards[sheet] = (card, column + 1)

    def _controls(self):
        busy = self.loading or self.saving
        available = bool(self.data and (self.data["items"] or self.data.get("attention")))
        self.checkbox.configure(state="disabled" if busy or not (available or self.include.get()) else "normal")
        self.manage_button.configure(state="disabled" if busy else "normal")
        for combo in self.selectors.values():
            combo.configure(state="readonly" if self.ready and self.include.get() and not busy else "disabled")
        self.on_state_change()

    def _toggle(self):
        self._controls()
        self._request_previews()

    def _choose(self, key):
        index = self.selectors[key].current()
        if not self.ready or not 0 <= index < len(self.ids):
            return
        item_id = self.ids[index]
        items = {item["id"]: item for item in self.data["items"]}
        self.draft[key] = (item_id, items[item_id]["sha256"] if item_id else None)
        self.pending_attention.discard(key)
        self._request_previews()

    def _preview_resized(self, key, width):
        if self.preview_widths.get(key) == width:
            return
        self.preview_widths[key] = width
        if self.ready and not (self.loading or self.saving):
            self._request_previews()

    def refresh(self, initial=False):
        self.tasks.cancel_role_previews()
        self.preview_request = None
        self.ready = False
        self.loading = True
        self.read_request = (self.tasks.submit("read"), initial)
        self.status.configure(text="正在读取签名库…")
        self._controls()

    def _render(self, data, initial):
        self.data = data
        self.revision = self.store.revision(data)
        items = {item["id"]: item for item in data["items"]}
        labels = [item["label"] for item in data["items"]]
        empty = "（不使用签名）"
        while empty in labels:
            empty += " "
        unresolved_text = "（请重新选择）"
        while unresolved_text in [empty] + labels:
            unresolved_text += " "
        self.ids = [None] + list(items)
        for key, combo in self.selectors.items():
            combo.configure(values=[empty] + labels)
            selected = data["bindings"].get(key)
            unresolved = key in data.get("attention", {})
            if key in self.draft:
                selected, fingerprint = self.draft[key]
                unresolved = selected is not None and (
                    selected not in items or items[selected]["sha256"] != fingerprint)
                if unresolved:
                    del self.draft[key]
                    self.pending_attention.add(key)
            unresolved = unresolved or key in self.pending_attention
            if unresolved:
                combo.set(unresolved_text)
            else:
                combo.current(self.ids.index(selected) if selected in self.ids else 0)
        if initial:
            self.include.set(bool(any(data["bindings"].values()) or data.get("attention")))
        self.ready = True
        issues = data.get("issues", [])
        note = "\n".join(issues[:2])
        if len(issues) > 2:
            note += f"\n另有 {len(issues) - 2} 项，请在签名管理中查看。"
        if not items:
            note = "请在签名管理中导入签名。" + ("\n" + note if note else "")
        self.status.configure(text=note)
        self._request_previews()

    def _request_previews(self):
        self.tasks.cancel_role_previews()
        self.preview_request = None
        cache = {fingerprint: self.photos[key] for key, fingerprint in self.preview_keys.items()
                 if key in self.photos}
        self.photos, self.preview_keys = {}, {}
        desired = {}
        items = {item["id"]: item for item in self.data["items"]} if self.data else {}
        for key, combo in self.selectors.items():
            index = combo.current()
            item_id = self.ids[index] if 0 <= index < len(self.ids) else None
            if not self.include.get() or item_id not in items or not self.ready:
                text = ("未启用签名" if not self.include.get() else
                        "请重新选择" if index < 0 else "不使用签名")
                self.previews[key].configure(image="", text=text)
                continue
            size = max(1, min(140, self.previews[key].winfo_width() - 12))
            fingerprint = (item_id, items[item_id]["sha256"], size)
            if fingerprint in cache:
                self.photos[key] = cache[fingerprint]
                self.preview_keys[key] = fingerprint
                self.previews[key].configure(image=cache[fingerprint], text="")
            else:
                desired[key] = fingerprint
                self.previews[key].configure(image="", text="正在读取预览…")
        if desired:
            request = self.tasks.submit("role_previews", tuple(dict.fromkeys(
                fingerprint[0] for fingerprint in desired.values())), self.revision)
            self.preview_request = (request, desired)

    def _show_previews(self, value, error):
        _, expected = self.preview_request
        self.preview_request = None
        photos = {}
        for key, fingerprint in expected.items():
            image, problem = (value or {}).get(fingerprint[0], (None, True)) if error is None else (None, True)
            try:
                if problem or image is None:
                    raise ValueError("Preview unavailable")
                if fingerprint not in photos:
                    # Worker returns at most 200x90; fit the compact export card.
                    fitted = image.copy()
                    fitted.thumbnail((fingerprint[2], 64))
                    photos[fingerprint] = ImageTk.PhotoImage(fitted, master=self.frame)
                self.photos[key] = photos[fingerprint]
                self.preview_keys[key] = fingerprint
                self.previews[key].configure(image=photos[fingerprint], text="")
            except (OSError, ValueError, tk.TclError):
                self.previews[key].configure(image="", text="预览暂不可用")

    def _manage(self):
        self.tasks.cancel_role_previews()
        self.preview_request = None
        open_signature_manager(self.dialog, self.store)
        if not self.closed:
            self.refresh()

    def confirm(self, callback):
        if self.closed or self.loading or self.saving:
            return
        if not self.include.get():
            callback(None)
            return
        if not self.ready:
            messagebox.showwarning("签名暂不可用", "请先在签名管理中刷新签名库，或取消添加签名。", parent=self.dialog)
            return
        bindings = {}
        for key, sheet, role in SLOTS:
            index = self.selectors[key].current()
            if not 0 <= index < len(self.ids):
                messagebox.showwarning("请确认签名", f"请重新选择{sheet}单的{role}，或明确选择不使用签名。", parent=self.dialog)
                return
            bindings[key] = self.ids[index]
        self.tasks.cancel_role_previews()
        self.preview_request = None
        self.saving = True
        self.callback = callback
        self.status.configure(text="正在保存签名选择…")
        self.save_request = self.tasks.submit("save_export", bindings, expected_revision=self.revision)
        self._controls()

    def _poll(self):
        self.poll_id = None
        if self.closed:
            return
        while True:
            try:
                request, kind, value, error = self.tasks.results.get_nowait()
            except Empty:
                break
            if kind == "read" and self.read_request and request == self.read_request[0]:
                _, initial = self.read_request
                self.read_request = None
                self.loading = False
                if error is None:
                    self._render(value, initial)
                else:
                    self.ready = False
                    if initial:
                        self.include.set(True)
                    self.status.configure(text="签名库读取失败，请进入签名管理检查；如需无签名导出，请取消添加签名。")
                self._controls()
            elif kind == "role_previews" and self.preview_request and request == self.preview_request[0]:
                self._show_previews(value, error)
            elif kind == "save_export" and request == self.save_request:
                self.save_request = None
                self.saving = False
                callback, self.callback = self.callback, None
                if error is None:
                    callback(value if any(value["bindings"].values()) else None)
                    return
                messagebox.showwarning("签名暂不可用", str(error), parent=self.dialog)
                self.refresh()
        if not self.closed:
            self.poll_id = self.frame.after(50, self._poll)

    def close(self):
        self.closed = True
        self.tasks.close()
        if self.poll_id is not None:
            self.frame.after_cancel(self.poll_id)
            self.poll_id = None
