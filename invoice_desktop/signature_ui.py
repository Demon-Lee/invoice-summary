"""Modal management of the portable signature library."""

from io import BytesIO
import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageTk

from .signatures import SLOTS
from .ui import FONT, PALETTE, surface
from .ui_widgets import AutoHideScrollbar


def open_signature_manager(parent, store):
    """Open a blocking manager; all successful changes are saved immediately."""
    try:
        initial = store.read()
    except Exception as exc:
        messagebox.showerror("签名库", _error_text(exc), parent=parent)
        return
    previous_grab = parent.grab_current()
    previous_status = previous_grab.grab_status() if previous_grab else None
    dialog = tk.Toplevel(parent)
    dialog.withdraw()
    dialog.title("签名库与角色设置")
    dialog.configure(bg=PALETTE["background"])
    dialog.transient(parent.winfo_toplevel())
    manager = _SignatureManager(dialog, store, initial)
    width = min(820, max(400, dialog.winfo_screenwidth() - 80))
    height = min(700, max(360, dialog.winfo_screenheight() - 100))
    dialog.geometry(f"{width}x{height}")
    dialog.minsize(min(600, width), min(440, height))
    dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
    dialog.bind("<Escape>", lambda event: dialog.destroy())
    try:
        dialog.deiconify()
        dialog.wait_visibility()
        dialog.grab_set()
        manager.listbox.focus_set()
        parent.wait_window(dialog)
    finally:
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
    def __init__(self, dialog, store, initial):
        self.dialog = dialog
        self.store = store
        self.data = initial
        self.items = []
        self.photo = None
        self.selectors = {}
        self.role_labels = {}
        self.selector_ids = [None]
        self.refreshing = False
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
        refresh_button = ttk.Button(toolbar, text="刷新列表", command=lambda: self.run(lambda: None), style="ExportAction.TButton", cursor="hand2")
        self.rename_button = ttk.Button(toolbar, text="重命名…", command=self.rename, style="ExportAction.TButton")
        self.replace_button = ttk.Button(toolbar, text="替换图片…", command=self.replace, style="ExportAction.TButton")
        self.delete_button = ttk.Button(toolbar, text="删除…", command=self.delete, style="ExportAction.TButton")
        toolbar_buttons = (import_button, folder_button, refresh_button, self.rename_button, self.replace_button, self.delete_button)
        for index, button in enumerate(toolbar_buttons):
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
        self.preview = ttk.Label(library, text="请选择签名查看图片", anchor="center",
                                 style="Surface.TLabel", padding=10, wraplength=230)
        self.preview.grid(row=3, column=0, sticky="ew", pady=(8, 0))
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
        ttk.Label(footer, text="修改后自动保存", foreground=PALETTE["muted"]).pack(side="left")
        ttk.Button(footer, text="关闭", command=dialog.destroy, style="ExportAction.TButton", cursor="hand2").pack(side="right")
        self.refresh(initial)

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
        return self.items[selected[0]]["id"] if selected else None

    def refresh(self, data=None, selected=None):
        if data is None:
            data = self.store.read()
        if selected is None:
            selected = self.selected_id()
        self.refreshing = True
        try:
            self.data = data
            self.items = list(data["items"])
            self.listbox.delete(0, tk.END)
            for index, item in enumerate(self.items):
                self.listbox.insert(tk.END, item["label"])
                if item["id"] == selected:
                    self.listbox.selection_set(index)
                    self.listbox.see(index)
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
                combo.configure(values=[empty] + labels)
                bound = data["bindings"].get(key)
                combo.current(self.selector_ids.index(bound) if bound in self.selector_ids else 0)
            self.show_selected()
        finally:
            self.refreshing = False

    def show_selected(self, event=None):
        item_id = self.selected_id()
        for button in (self.rename_button, self.replace_button, self.delete_button):
            button.configure(state="normal" if item_id else "disabled", cursor="hand2" if item_id else "arrow")
        self.photo = None
        self.preview.configure(image="", text="请选择签名查看图片" if self.items else "尚未导入签名")
        if item_id:
            try:
                with Image.open(BytesIO(self.store.image_bytes(item_id))) as source:
                    thumbnail = source.convert("RGBA")
                thumbnail.thumbnail((280, 180), Image.Resampling.LANCZOS)
                self.photo = ImageTk.PhotoImage(thumbnail, master=self.dialog)
                self.preview.configure(image=self.photo, text="")
            except Exception:
                self.preview.configure(text="图片无法读取，请替换图片或删除此签名。")

    def run(self, operation, selected=None):
        try:
            result = operation()
            self.refresh(selected=result if isinstance(result, str) else selected)
        except Exception as exc:
            messagebox.showerror("签名库", _error_text(exc), parent=self.dialog)
            try:
                self.refresh(selected=selected)
            except Exception:
                self.refresh(self.data, selected=selected)

    def choose_image(self):
        return filedialog.askopenfilename(parent=self.dialog, title="选择签名图片",
            filetypes=[("签名图片", "*.png *.jpg *.jpeg"), ("PNG 图片", "*.png"),
                       ("JPEG 图片", "*.jpg *.jpeg")])

    def open_folder(self):
        try:
            self.refresh()
            os.startfile(self.store.image_dir)
        except (OSError, ValueError) as exc:
            messagebox.showerror("签名文件夹", _error_text(exc), parent=self.dialog)

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
            self.run(lambda: self.store.import_image(label, path, expected_revision=self.store.revision(self.data)))

    def rename(self):
        item_id = self.selected_id()
        if not item_id:
            return
        item = next(item for item in self.items if item["id"] == item_id)
        label = self.ask_label("重命名签名", item["label"])
        if label is not None:
            self.run(lambda: self.store.rename(item_id, label, expected_revision=self.store.revision(self.data)), item_id)

    def affected_roles(self, item_id):
        return [f"{sheet} · {label}" for key, sheet, label in SLOTS
                if self.data["bindings"].get(key) == item_id]

    def fresh_revision(self, item_id):
        fresh = self.store.read()
        self.refresh(fresh, selected=item_id)
        if not any(item["id"] == item_id for item in self.items):
            raise ValueError("此签名已被其他窗口删除，请重新选择。")
        return self.store.revision(fresh)

    def replace(self):
        item_id = self.selected_id()
        if not item_id:
            return
        path = self.choose_image()
        if not path:
            return
        try:
            revision = self.fresh_revision(item_id)
        except Exception as exc:
            messagebox.showerror("签名库", _error_text(exc), parent=self.dialog)
            return
        roles = self.affected_roles(item_id)
        if roles and not messagebox.askyesno("替换签名图片",
                "以下角色正在使用此签名：\n" + "、".join(roles) + "\n\n替换后这些角色将使用新图片。是否继续？",
                parent=self.dialog):
            return
        label = next(item["label"] for item in self.items if item["id"] == item_id)
        self.run(lambda: self.store.import_image(label, path, item_id=item_id,
                                                 expected_revision=revision), item_id)

    def delete(self):
        item_id = self.selected_id()
        if not item_id:
            return
        try:
            revision = self.fresh_revision(item_id)
        except Exception as exc:
            messagebox.showerror("签名库", _error_text(exc), parent=self.dialog)
            return
        roles = self.affected_roles(item_id)
        text = ("以下角色正在使用此签名：\n" + "、".join(roles) + "\n\n删除后将清空这些角色的签名选择。是否删除？"
                if roles else "是否删除选中的签名？")
        if messagebox.askyesno("删除签名", text, parent=self.dialog):
            self.run(lambda: self.store.delete(item_id, expected_revision=revision))

    def assign(self, key):
        if self.refreshing:
            return
        index = self.selectors[key].current()
        if 0 <= index < len(self.selector_ids):
            self.run(lambda: self.store.assign(key, self.selector_ids[index], expected_revision=self.store.revision(self.data)), self.selected_id())
