"""Modal management of the portable signature library."""

from io import BytesIO
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from PIL import Image, ImageTk

from .signatures import SLOTS


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
        self.selector_ids = [None]
        self.refreshing = False
        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        canvas = tk.Canvas(frame, highlightthickness=0)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        body = ttk.Frame(canvas, padding=4)
        body.columnconfigure(0, weight=1)
        window = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        introduction = ttk.Label(body, text="导入签名图片并命名，再为各角色选择签名。修改后立即保存。",
                                 wraplength=550)
        introduction.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        toolbar = ttk.Frame(body)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        import_button = ttk.Button(toolbar, text="导入图片…", command=self.import_image)
        self.rename_button = ttk.Button(toolbar, text="重命名…", command=self.rename)
        self.replace_button = ttk.Button(toolbar, text="替换图片…", command=self.replace)
        self.delete_button = ttk.Button(toolbar, text="删除…", command=self.delete)
        toolbar_buttons = (import_button, self.rename_button, self.replace_button, self.delete_button)
        for index, button in enumerate(toolbar_buttons):
            button.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0, 6), pady=(0, 6))
        toolbar.columnconfigure(0, weight=1)
        toolbar.columnconfigure(1, weight=1)
        library = ttk.Frame(body)
        library.columnconfigure(0, weight=1)
        library.grid(row=2, column=0, sticky="nsew")
        self.listbox = tk.Listbox(library, height=8, width=1, exportselection=False)
        self.listbox.grid(row=0, column=0, sticky="nsew")
        list_scroll = ttk.Scrollbar(library, orient="vertical", command=self.listbox.yview)
        list_scroll.grid(row=0, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=list_scroll.set)
        self.listbox.bind("<<ListboxSelect>>", self.show_selected)
        self.preview = ttk.Label(library, text="请选择签名查看图片", anchor="center",
                                 wraplength=230)
        self.preview.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        roles = ttk.LabelFrame(body, text="PDF 签名角色", padding=10)
        roles.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        roles.columnconfigure(1, weight=1)
        for index, (key, sheet, label) in enumerate(SLOTS):
            ttk.Label(roles, text=f"{sheet} · {label}").grid(row=index * 2, column=0, columnspan=2, sticky="w", pady=(5, 0))
            combo = ttk.Combobox(roles, state="readonly", width=1)
            combo.grid(row=index * 2 + 1, column=0, columnspan=2, sticky="ew", pady=(2, 5))
            combo.bind("<<ComboboxSelected>>", lambda event, slot=key: self.assign(slot))
            self.selectors[key] = combo
        roles.columnconfigure(0, weight=1)
        note = ttk.Label(body, text="同一签名可用于多个角色；未选择的角色不会添加图片。",
                         wraplength=550)
        note.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        def wrap_text(event):
            for label in (introduction, note, self.preview):
                label.configure(wraplength=max(100, event.width - 16))
        body.bind("<Configure>", wrap_text, add="+")
        ttk.Button(frame, text="关闭", command=dialog.destroy).grid(row=1, column=0, sticky="e", pady=(10, 0))
        self.refresh(initial)

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
            button.configure(state="normal" if item_id else "disabled")
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
        label = self.ask_label("命名签名")
        if label is not None:
            self.run(lambda: self.store.import_image(label, path))

    def rename(self):
        item_id = self.selected_id()
        if not item_id:
            return
        item = next(item for item in self.items if item["id"] == item_id)
        label = self.ask_label("重命名签名", item["label"])
        if label is not None:
            self.run(lambda: self.store.rename(item_id, label), item_id)

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
            self.run(lambda: self.store.assign(key, self.selector_ids[index]), self.selected_id())
