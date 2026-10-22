"""Modal management of the portable signature library."""

from pathlib import Path
from queue import Empty
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import ImageTk

from .signatures import SLOTS
from .signature_tasks import SignatureRefreshError, SignatureTasks
from .ui import FONT, PALETTE, surface
from .ui_widgets import AutoHideScrollbar


def open_signature_manager(parent, store):
    """Open a blocking manager; all successful changes are saved immediately."""
    previous_grab = parent.grab_current()
    previous_status = previous_grab.grab_status() if previous_grab else None
    dialog = tk.Toplevel(parent)
    dialog.withdraw()
    dialog.title("签名库与角色设置")
    dialog.configure(bg=PALETTE["background"])
    dialog.transient(parent.winfo_toplevel())
    manager = _SignatureManager(dialog, store)
    width = min(820, max(400, dialog.winfo_screenwidth() - 80))
    height = min(700, max(360, dialog.winfo_screenheight() - 100))
    dialog.geometry(f"{width}x{height}")
    dialog.minsize(min(600, width), min(440, height))
    dialog.protocol("WM_DELETE_WINDOW", manager.close)
    dialog.bind("<Escape>", lambda event: manager.close())
    try:
        dialog.deiconify()
        dialog.wait_visibility()
        dialog.grab_set()
        manager.listbox.focus_set()
        parent.wait_window(dialog)
    finally:
        manager.stop_tasks()
        if dialog.winfo_exists():
            dialog.destroy()
        if previous_grab is not None:
            try:
                if previous_grab.winfo_exists():
                    if previous_status == "global":
                        previous_grab.grab_set_global()
                    else:
                        previous_grab.grab_set()
            except tk.TclError:
                pass


def _error_text(exc):
    detail = str(exc).strip()
    if isinstance(exc, PermissionError):
        return "签名文件夹无法写入，请检查文件夹权限后重试。"
    if isinstance(exc, (ValueError, OSError)) and detail:
        return "签名操作未完成：" + detail[:240]
    return "签名操作未完成，请检查图片和签名文件夹后重试。"


class _SignatureManager:
    def __init__(self, dialog, store):
        self.dialog = dialog
        self.store = store
        self.data = {"items": [], "bindings": {}}
        self.items = []
        self.photo = None
        self.photo_key = None
        self.selectors = {}
        self.role_labels = {}
        self.selector_ids = [None]
        self.refreshing = False
        self.busy = False
        self.needs_refresh = False
        self.closed = False
        self.tasks = SignatureTasks(store)
        self.control_request = None
        self.control_kind = None
        self.preview_request = None
        self.poll_id = None
        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)
        header = surface(frame, padding=12)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(header, text="签名管理", style="Section.TLabel", font=(FONT, 13, "bold")).pack(anchor="w")
        subtitle = ttk.Label(header, text="文件名即标签，也可直接把图片放入签名图片文件夹。", style="Muted.TLabel", wraplength=500)
        subtitle.pack(anchor="w", fill="x", pady=(4, 0))
        header.bind("<Configure>", lambda event: subtitle.configure(wraplength=max(160, event.width - 28)))
        scroll_host = tk.Frame(frame, bg=PALETTE["background"])
        scroll_host.grid(row=1, column=0, sticky="nsew")
        scroll_host.rowconfigure(0, weight=1)
        scroll_host.columnconfigure(0, weight=1)
        scroll_host.columnconfigure(1, minsize=14)
        scale = max(0.75, float(dialog.tk.call("tk", "scaling")) / (4 / 3))
        canvas = self.canvas = tk.Canvas(scroll_host, highlightthickness=0, bd=0,
                                        bg=PALETTE["background"], yscrollincrement=max(12, round(18 * scale)))
        scroll = AutoHideScrollbar(scroll_host, command=canvas.yview, background=PALETTE["background"])
        scroll.attach(canvas, scroll_host)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        body = ttk.Frame(canvas)
        body.columnconfigure(0, weight=1)
        window = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        library = surface(body, padding=12)
        library.columnconfigure(0, weight=1)
        library.grid(row=0, column=0, sticky="ew")
        ttk.Label(library, text="签名库", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        toolbar = ttk.Frame(library, style="Surface.TFrame")
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        # Use the root's existing rounded surfaces; do not rebuild shared theme images.
        import_button = ttk.Button(toolbar, text="导入签名…", command=self.import_image, style="ExecuteAction.TButton", cursor="hand2")
        folder_button = ttk.Button(toolbar, text="打开签名文件夹", command=self.open_folder, style="ExportAction.TButton", cursor="hand2")
        refresh_button = self.refresh_button = ttk.Button(toolbar, text="刷新列表", command=self.load, style="ExportAction.TButton", cursor="hand2")
        self.rename_button = ttk.Button(toolbar, text="重命名…", command=self.rename, style="ExportAction.TButton")
        self.replace_button = ttk.Button(toolbar, text="替换图片…", command=self.replace, style="ExportAction.TButton")
        self.delete_button = ttk.Button(toolbar, text="删除…", command=self.delete, style="ExportAction.TButton")
        self.toolbar_buttons = (import_button, folder_button, refresh_button, self.rename_button, self.replace_button, self.delete_button)
        for index, button in enumerate(self.toolbar_buttons):
            button.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0, 6), pady=(0, 6))
        toolbar.columnconfigure(0, weight=1)
        toolbar.columnconfigure(1, weight=1)
        list_panel = surface(library)
        list_panel.grid(row=2, column=0, sticky="ew")
        list_panel.rowconfigure(0, weight=1)
        list_panel.columnconfigure(0, weight=1)
        list_panel.columnconfigure(1, minsize=14)
        self.listbox = tk.Listbox(list_panel, height=7, width=1, exportselection=False, bd=0,
                                 highlightthickness=0, relief="flat", activestyle="none", font=(FONT, 10),
                                 bg=PALETTE["surface"], fg=PALETTE["text"], selectborderwidth=0,
                                 selectbackground=PALETTE["selected"], selectforeground=PALETTE["heading"])
        self.listbox.grid(row=0, column=0, sticky="nsew")
        list_scroll = AutoHideScrollbar(list_panel, command=self.listbox.yview)
        list_scroll.attach(self.listbox, list_panel)
        self.listbox.configure(yscrollcommand=list_scroll.set)
        self.listbox.bind("<<ListboxSelect>>", self.show_selected)
        preview_host = ttk.Frame(library, style="Surface.TFrame", height=200)
        preview_host.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        preview_host.grid_propagate(False)
        preview_host.rowconfigure(0, weight=1)
        preview_host.columnconfigure(0, weight=1)
        self.preview = ttk.Label(preview_host, text="正在读取签名库…", anchor="center",
                                 style="Surface.TLabel", padding=10, wraplength=230)
        self.preview.grid(row=0, column=0, sticky="nsew")
        self.notice = ttk.Label(library, style="Surface.TLabel", foreground="#946522", justify="left", wraplength=550)
        self.notice.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        roles = surface(body, padding=12)
        roles.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(roles, text="签字位置", style="Section.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        roles.columnconfigure(1, weight=1)
        style = ttk.Style(dialog)
        style.configure("Signature.TCombobox", font=(FONT, 10), padding=(8, 6),
                        foreground=PALETTE["text"], fieldbackground=PALETTE["surface"],
                        background=PALETTE["surface"], bordercolor=PALETTE["line"],
                        lightcolor=PALETTE["line"], darkcolor=PALETTE["line"], arrowcolor=PALETTE["blue"])
        style.map("Signature.TCombobox", fieldbackground=[("readonly", PALETTE["surface"])],
                  bordercolor=[("focus", "#8caff7"), ("active", "#8caff7")])
        wheel_events = ("<MouseWheel>", "<Shift-MouseWheel>", "<Button-4>", "<Button-5>")
        for index, (key, sheet, label) in enumerate(SLOTS):
            caption = ttk.Label(roles, text=f"{sheet} · {label}", style="Surface.TLabel")
            caption.grid(row=index * 2 + 1, column=0, columnspan=2, sticky="w", pady=(5, 0))
            self.role_labels[key] = caption
            combo = ttk.Combobox(roles, state="readonly", width=1, style="Signature.TCombobox")
            combo.grid(row=index * 2 + 2, column=0, columnspan=2, sticky="ew", pady=(2, 5))
            combo.bind("<<ComboboxSelected>>", lambda event, slot=key: self.assign(slot))
            for sequence in wheel_events:
                # Widget binding runs before TCombobox's wheel-to-change class binding.
                combo.bind(sequence, self._scroll_body)
            self.selectors[key] = combo
        roles.columnconfigure(0, weight=1)
        note = ttk.Label(body, text="放入 PNG/JPG/JPEG 后点击刷新列表。同一签名可用于多个位置。",
                         wraplength=550)
        note.grid(row=2, column=0, sticky="ew", pady=(10, 4))
        def wrap_text(event):
            for label in (note, self.preview, self.notice):
                label.configure(wraplength=max(100, event.width - 40))
        body.bind("<Configure>", wrap_text, add="+")
        for sequence in wheel_events:
            dialog.bind(sequence, self._scroll_body, add="+")
            self.listbox.bind(sequence, self._scroll_library)
        footer = ttk.Frame(frame)
        footer.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.status = ttk.Label(footer, text="正在读取签名库…", foreground=PALETTE["muted"])
        self.status.pack(side="left")
        self.close_button = ttk.Button(footer, text="关闭", command=self.close, style="ExportAction.TButton", cursor="hand2")
        self.close_button.pack(side="right")
        dialog.bind("<Destroy>", self._on_destroy, add="+")
        self.load()
        self.poll_id = dialog.after(40, self._poll)

    @staticmethod
    def _wheel_units(event):
        number = getattr(event, "num", None)
        if number in (4, 5):
            return -1 if number == 4 else 1
        delta = getattr(event, "delta", 0)
        return (-int(delta / 120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)) if delta else 0

    def _scroll_body(self, event):
        units = self._wheel_units(event)
        if units:
            self.canvas.yview_scroll(units * 3, "units")
        return "break"

    def _scroll_library(self, event):
        units = self._wheel_units(event)
        first, last = self.listbox.yview()
        if units and ((units < 0 and first > 0) or (units > 0 and last < 1)):
            self.listbox.yview_scroll(units * 3, "units")
            return "break"
        return self._scroll_body(event)

    def selected_id(self):
        selected = self.listbox.curselection()
        return self.items[selected[0]]["id"] if selected and selected[0] < len(self.items) else None

    def refresh(self, data, selected=None):
        """Apply a completed read on Tk's thread without rebuilding unchanged rows."""
        if selected is None:
            selected = self.selected_id()
        previous_selection = self.selected_id()
        list_position = self.listbox.yview()[0]
        body_position = self.canvas.yview()[0]
        self.refreshing = True
        try:
            self.data = data
            items = list(data["items"])
            changed = [(item["id"], item["label"]) for item in items] != [
                (item["id"], item["label"]) for item in self.items]
            self.items = items
            if changed:
                self.listbox.delete(0, tk.END)
                for item in self.items:
                    self.listbox.insert(tk.END, item["label"])
            if changed or selected != previous_selection:
                self.listbox.selection_clear(0, tk.END)
                for index, item in enumerate(self.items):
                    if item["id"] == selected:
                        self.listbox.selection_set(index)
                        if selected != previous_selection:
                            self.listbox.see(index)
                        break
                if selected == previous_selection:
                    self.listbox.yview_moveto(list_position)
            labels = [item["label"] for item in self.items]
            attention = data.get("attention", {})
            warnings = list(data.get("issues", []))
            affected = [f"{sheet} · {role}" for key, sheet, role in SLOTS if key in attention]
            if affected:
                warnings.insert(0, "以下位置需要重新确认：" + "、".join(affected) + "。请选择标签，或明确选择不使用签名。")
            shown = warnings[:5]
            if len(warnings) > len(shown):
                shown.append(f"另有 {len(warnings) - len(shown)} 项，请处理后刷新列表。")
            self.notice.configure(text="\n".join(shown))
            if warnings:
                self.notice.grid()
            else:
                self.notice.grid_remove()
            for key, sheet, role in SLOTS:
                pending = key in attention
                self.role_labels[key].configure(text=f"{sheet} · {role}" + ("  ·  需确认" if pending else ""),
                                                foreground="#946522" if pending else PALETTE["text"])
            empty = "（不使用签名）"
            while empty in labels:
                empty += " "
            self.selector_ids = [None] + [item["id"] for item in self.items]
            for key, combo in self.selectors.items():
                if changed or not combo.cget("values"):
                    combo.configure(values=[empty] + labels)
                bound = data["bindings"].get(key)
                combo.current(self.selector_ids.index(bound) if bound in self.selector_ids else 0)
            self.show_selected()
        finally:
            self.refreshing = False
            self.canvas.yview_moveto(body_position)

    def show_selected(self, event=None):
        if self.busy or self.closed:
            return
        item_id = self.selected_id()
        self._update_controls()
        self.tasks.cancel_preview()
        self.preview_request = None
        item = next((item for item in self.items if item["id"] == item_id), None)
        key = (item_id, item["sha256"]) if item else None
        if key != self.photo_key or self.photo is None:
            self.photo = None
            self.photo_key = None
            self.preview.configure(image="", text=("正在读取签名图片…" if item_id else
                "请选择签名查看图片" if self.items else "尚未导入签名"))
        if item_id:
            request = self.tasks.submit("preview", item_id, self.store.revision(self.data))
            self.preview_request = (request, key)

    def _update_controls(self):
        for button in self.toolbar_buttons:
            disabled = self.busy or (self.needs_refresh and button is not self.refresh_button)
            button.configure(state="disabled" if disabled else "normal")
        self.listbox.configure(state="disabled" if self.busy else "normal")
        for combo in self.selectors.values():
            combo.configure(state="disabled" if self.busy or self.needs_refresh else "readonly")
        enabled = bool(self.selected_id()) and not self.busy and not self.needs_refresh
        for button in (self.rename_button, self.replace_button, self.delete_button):
            button.configure(state="normal" if enabled else "disabled", cursor="hand2" if enabled else "arrow")
        self.close_button.configure(state="disabled" if self.control_kind == "mutate" else "normal")

    def _begin(self, kind, *args, selected=None, action=None, path=None, **kwargs):
        if self.busy or self.closed:
            return
        self.busy = True
        self.control_kind = kind
        self.tasks.cancel_preview()
        self.preview_request = None
        self._update_controls()
        self.status.configure(text="正在保存签名库…" if kind == "mutate" else "正在处理签名库…")
        request = self.tasks.submit(kind, *args, **kwargs)
        self.control_request = (request, selected, action, path)

    def load(self):
        self._begin("read", selected=self.selected_id())

    def run(self, method, *args, selected=None, **kwargs):
        self._begin("mutate", method, *args, selected=selected, **kwargs)

    def _poll(self):
        self.poll_id = None
        if self.closed:
            return
        while not self.closed:
            try:
                request, kind, value, error = self.tasks.results.get_nowait()
            except Empty:
                break
            if kind == "preview":
                if not self.preview_request or request != self.preview_request[0]:
                    continue
                _, key = self.preview_request
                self.preview_request = None
                if error:
                    self.photo = self.photo_key = None
                    self.preview.configure(image="", text="图片无法读取，请刷新列表、替换图片或删除此签名。")
                elif self.photo is None or key != self.photo_key:
                    try:
                        self.photo = ImageTk.PhotoImage(value, master=self.dialog)
                        self.photo_key = key
                        self.preview.configure(image=self.photo, text="")
                    except (OSError, tk.TclError):
                        self.photo = self.photo_key = None
                        self.preview.configure(image="", text="图片无法显示，请刷新列表或替换图片。")
                continue
            if not self.control_request or request != self.control_request[0]:
                continue
            _, selected, action, path = self.control_request
            self.control_request = None
            self.control_kind = None
            self.busy = False
            self.needs_refresh = error is not None
            self._update_controls()
            if error:
                self.refresh(self.data, selected=selected)
                self.status.configure(text="签名已保存，请刷新列表核对。" if isinstance(error, SignatureRefreshError)
                                      else "操作未完成，请刷新列表核对。")
                messagebox.showerror("签名库", _error_text(error), parent=self.dialog)
                continue
            self.status.configure(text="修改后自动保存")
            if kind == "mutate":
                data, result = value
                selected = result if isinstance(result, str) else selected
            else:
                data = value
            self.refresh(data, selected=selected)
            if action:
                self._confirm_change(action, selected, path)
        if not self.closed:
            self.poll_id = self.dialog.after(40, self._poll)

    def _on_destroy(self, event):
        if event.widget is self.dialog:
            self.stop_tasks()

    def stop_tasks(self):
        if self.closed:
            return
        self.closed = True
        if self.poll_id is not None:
            try:
                self.dialog.after_cancel(self.poll_id)
            except tk.TclError:
                pass
            self.poll_id = None
        self.control_request = self.preview_request = None
        self.tasks.close()

    def close(self):
        if self.control_kind == "mutate":
            self.status.configure(text="正在保存签名库，请稍候再关闭…")
            return
        self.stop_tasks()
        self.dialog.destroy()

    def choose_image(self):
        return filedialog.askopenfilename(parent=self.dialog, title="选择签名图片",
            filetypes=[("签名图片", "*.png *.jpg *.jpeg"), ("PNG 图片", "*.png"),
                       ("JPEG 图片", "*.jpg *.jpeg")])

    def open_folder(self):
        self._begin("folder", selected=self.selected_id())

    def ask_label(self, title, initialvalue=""):
        try:
            return simpledialog.askstring(title, "签名名称（不可重复）：",
                                          initialvalue=initialvalue, parent=self.dialog)
        finally:
            # Tk simpledialog releases its own grab when it closes.
            if self.dialog.winfo_exists():
                self.dialog.grab_set()

    def import_image(self):
        path = self.choose_image()
        if not path:
            return
        label = self.ask_label("命名签名", Path(path).stem)
        if label is not None:
            self.run("import_image", label, path, expected_revision=self.store.revision(self.data))

    def rename(self):
        item_id = self.selected_id()
        if not item_id:
            return
        item = next(item for item in self.items if item["id"] == item_id)
        label = self.ask_label("重命名签名", item["label"])
        if label is not None:
            self.run("rename", item_id, label, selected=item_id,
                     expected_revision=self.store.revision(self.data))

    def affected_roles(self, item_id):
        return [f"{sheet} · {label}" for key, sheet, label in SLOTS
                if self.data["bindings"].get(key) == item_id]

    def replace(self):
        item_id = self.selected_id()
        if not item_id:
            return
        path = self.choose_image()
        if not path:
            return
        self._begin("read", selected=item_id, action="replace", path=path)

    def delete(self):
        item_id = self.selected_id()
        if not item_id:
            return
        self._begin("read", selected=item_id, action="delete")

    def _confirm_change(self, action, item_id, path):
        item = next((item for item in self.items if item["id"] == item_id), None)
        if item is None:
            messagebox.showerror("签名库", "此签名已被其他窗口删除，请重新选择。", parent=self.dialog)
            return
        revision = self.store.revision(self.data)
        roles = self.affected_roles(item_id)
        if action == "replace":
            if roles and not messagebox.askyesno("替换签名图片",
                    "以下角色正在使用此签名：\n" + "、".join(roles) + "\n\n替换后这些角色将使用新图片。是否继续？",
                    parent=self.dialog):
                return
            self.run("import_image", item["label"], path, item_id=item_id,
                     expected_revision=revision, selected=item_id)
            return
        text = ("以下角色正在使用此签名：\n" + "、".join(roles) + "\n\n删除后将清空这些角色的签名选择。是否删除？"
                if roles else "是否删除选中的签名？")
        if messagebox.askyesno("删除签名", text, parent=self.dialog):
            self.run("delete", item_id, expected_revision=revision)

    def assign(self, key):
        if self.refreshing or self.busy or self.needs_refresh:
            return
        index = self.selectors[key].current()
        if 0 <= index < len(self.selector_ids):
            self.run("assign", key, self.selector_ids[index],
                     expected_revision=self.store.revision(self.data), selected=self.selected_id())
