"""Modal management of the portable signature library."""

from pathlib import Path
from queue import Empty
import tkinter as tk
from tkinter import ttk

from PIL import ImageTk

from .signatures import SLOTS
from .signature_tasks import SignatureRefreshError, SignatureTasks
from .ui import FONT, PALETTE, surface
from .ui_widgets import AutoHideScrollbar
from .dialogs import center_dialog, dialog_work_area_size, filedialog, messagebox, simpledialog


def open_signature_manager(parent, store):
    """Open a blocking manager; position edits commit only through Save."""
    previous_grab = parent.grab_current()
    previous_status = previous_grab.grab_status() if previous_grab else None
    dialog = tk.Toplevel(parent)
    dialog.withdraw()
    dialog.title("签名管理")
    dialog.configure(bg=PALETTE["background"])
    dialog.transient(parent.winfo_toplevel())
    manager = _SignatureManager(dialog, store)
    available_width, available_height = dialog_work_area_size(parent)
    width = min(820, max(1, available_width - 80))
    height_limit = max(1, available_height - 80)
    height = min(700, height_limit)
    dialog.geometry(f"{width}x{height}")
    dialog.minsize(min(600, width), min(440, height_limit))
    dialog.update_idletasks()
    # Canvas keeps its own requested height, independent of the embedded page.
    chrome_height = max(0, dialog.winfo_reqheight() - manager.roles_canvas.winfo_reqheight())
    content_height = manager.roles_body.winfo_reqheight() + chrome_height + 8
    height = min(height_limit, max(min(440, height_limit), content_height))
    dialog.geometry(f"{width}x{height}")
    dialog.protocol("WM_DELETE_WINDOW", manager.close)
    dialog.bind("<Escape>", lambda event: manager.close())
    try:
        center_dialog(dialog, parent)
        dialog.deiconify()
        dialog.wait_visibility()
        dialog.grab_set()
        manager.tab_buttons[manager.active_tab].focus_set()
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
        self.role_previews = {}
        self.role_photos = {}
        self.role_preview_keys = {}
        self.role_preview_expected = {}
        self.role_preview_request = None
        self.selector_ids = [None]
        self.pending_bindings = {}
        self.pending_fingerprints = {}
        self.pending_attention = set()
        self.saved_awaiting_refresh = False
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
        header = surface(frame)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(header, text="签名管理", style="Section.TLabel", font=(FONT, 13, "bold")).pack(anchor="w", padx=16, pady=(14, 10))
        style = ttk.Style(dialog)
        style.layout("SignatureTab.TButton", [("Button.padding", {"sticky": "nswe", "children": [
            ("Button.label", {"sticky": "nswe"}),
        ]})])
        style.configure("SignatureTab.TButton", font=(FONT, 10, "bold"), padding=(18, 10),
                        background=PALETTE["surface"], foreground=PALETTE["muted"],
                        anchor="center", width=0, borderwidth=0)
        style.map("SignatureTab.TButton",
                  background=[("selected", "focus", "#dceaff"), ("selected", "#edf4ff"),
                              ("focus", "#e5efff"), ("active", "#f5f8fd"),
                              ("!disabled", PALETTE["surface"]), ("disabled", PALETTE["surface"])],
                  foreground=[("selected", PALETTE["blue"]), ("active", PALETTE["blue"]),
                              ("!disabled", PALETTE["muted"]), ("disabled", PALETTE["muted"])])
        navigation = tk.Frame(header, bg=PALETTE["surface"])
        navigation.pack(fill="x", padx=12)
        self.tab_buttons, self.tab_lines = {}, {}
        self.active_tab = None
        for key, title in (("roles", "签字位置"), ("library", "签名库")):
            item = tk.Frame(navigation, bg=PALETTE["surface"])
            item.pack(side="left", padx=(0, 8))
            button = ttk.Button(item, text=title, style="SignatureTab.TButton", cursor="hand2",
                                command=lambda key=key: self._select_tab(key, focus=True))
            button.pack(fill="x")
            line = tk.Frame(item, height=3, bg=PALETTE["surface"], bd=0, highlightthickness=0)
            line.pack(fill="x")
            button.bind("<Left>", lambda event: self._cycle_tab(-1))
            button.bind("<Right>", lambda event: self._cycle_tab(1))
            button.bind("<Home>", lambda event: self._select_tab("roles", focus=True))
            button.bind("<End>", lambda event: self._select_tab("library", focus=True))
            button.bind("<Return>", lambda event, key=key: self._select_tab(key, focus=True))
            self.tab_buttons[key], self.tab_lines[key] = button, line
        self.pages_host = ttk.Frame(frame)
        self.pages_host.grid(row=1, column=0, sticky="nsew")
        self.pages_host.rowconfigure(0, weight=1)
        self.pages_host.columnconfigure(0, weight=1)
        scale = max(0.75, float(dialog.tk.call("tk", "scaling")) / (4 / 3))
        def scrollable_page():
            host = ttk.Frame(self.pages_host)
            host.rowconfigure(0, weight=1)
            host.columnconfigure(0, weight=1)
            host.columnconfigure(1, minsize=14)
            canvas = tk.Canvas(host, highlightthickness=0, bd=0, bg=PALETTE["background"],
                               yscrollincrement=max(12, round(18 * scale)))
            scroll = AutoHideScrollbar(host, command=canvas.yview, background=PALETTE["background"])
            scroll.attach(canvas, host)
            canvas.configure(yscrollcommand=scroll.set)
            canvas.grid(row=0, column=0, sticky="nsew")
            body = ttk.Frame(canvas)
            body.columnconfigure(0, weight=1)
            window = canvas.create_window((0, 0), window=body, anchor="nw")
            def sync_page(event=None):
                width, height = canvas.winfo_width(), canvas.winfo_height()
                canvas.itemconfigure(window, width=width)
                bounds = canvas.bbox(window)
                content_height = bounds[3] - bounds[1] if bounds else 0
                # A short scrollregion lets Canvas shift fitting content into blank space.
                canvas.configure(scrollregion=(0, 0, width, max(height, content_height)))
                if content_height <= height:
                    canvas.yview_moveto(0)
            body.bind("<Configure>", sync_page)
            canvas.bind("<Configure>", sync_page)
            return host, canvas, body
        self.roles_page, self.roles_canvas, roles_body = scrollable_page()
        self.roles_body = roles_body
        self.library_page, self.canvas, body = scrollable_page()
        self.tab_pages = {"roles": self.roles_page, "library": self.library_page}
        dialog.bind("<Control-Tab>", lambda event: self._cycle_tab(1), add="+")
        dialog.bind("<Control-Shift-Tab>", lambda event: self._cycle_tab(-1), add="+")
        toolbar = ttk.Frame(body)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        # Use the root's existing rounded surfaces; do not rebuild shared theme images.
        import_button = ttk.Button(toolbar, text="导入签名…", command=self.import_image, style="ExecuteAction.TButton", cursor="hand2")
        folder_button = ttk.Button(toolbar, text="打开签名文件夹", command=self.open_folder, style="ExportAction.TButton", cursor="hand2")
        refresh_button = self.refresh_button = ttk.Button(toolbar, text="刷新列表", command=self.load, style="ExportAction.TButton", cursor="hand2")
        selected_tools = ttk.Frame(body)
        selected_tools.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        style.configure("Danger.ExportAction.TButton", foreground="#b4473f")
        style.map("Danger.ExportAction.TButton", foreground=[("disabled", "#8a97aa"), ("!disabled", "#b4473f")])
        self.rename_button = ttk.Button(selected_tools, text="重命名…", command=self.rename, style="ExportAction.TButton")
        self.replace_button = ttk.Button(selected_tools, text="替换图片…", command=self.replace, style="ExportAction.TButton")
        self.delete_button = ttk.Button(selected_tools, text="删除…", command=self.delete, style="Danger.ExportAction.TButton")
        self.toolbar_buttons = (import_button, folder_button, refresh_button, self.rename_button, self.replace_button, self.delete_button)
        tool_layouts = {}
        def layout_tools(host, buttons):
            available = max(1, host.winfo_width())
            widths = tuple(button.winfo_reqwidth() for button in buttons)
            gap = max(6, round(8 * scale))
            columns = max(1, min(len(buttons), available // (max(widths) + gap)))
            signature = (columns, widths)
            if tool_layouts.get(host) == signature:
                return
            tool_layouts[host] = signature
            for column in range(len(buttons)):
                host.columnconfigure(column, weight=0, uniform="signature-tools" if column < columns else "")
            last_row = (len(buttons) - 1) // columns
            for index, button in enumerate(buttons):
                button.grid(row=index // columns, column=index % columns, sticky="ew",
                            padx=(0, gap if index % columns < columns - 1 else 0),
                            pady=(0, 6 if index // columns < last_row else 0))
        for host, buttons in ((toolbar, self.toolbar_buttons[:3]), (selected_tools, self.toolbar_buttons[3:])):
            host.bind("<Configure>", lambda event, host=host, buttons=buttons: layout_tools(host, buttons))
            for button in buttons:
                button.bind("<Configure>", lambda event, host=host, buttons=buttons: layout_tools(host, buttons), add="+")
            layout_tools(host, buttons)
        panels = ttk.Frame(body)
        panels.grid(row=1, column=0, sticky="ew")
        panels.columnconfigure(0, weight=2, uniform="signature-library-panes")
        panels.columnconfigure(1, weight=3, uniform="signature-library-panes")
        list_panel = surface(panels, padding=12)
        list_panel.rowconfigure(1, weight=1)
        list_panel.columnconfigure(0, weight=1)
        ttk.Label(list_panel, text="签名列表", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 10))
        list_view = tk.Frame(list_panel, bg=PALETTE["surface"])
        list_view.grid(row=1, column=0, sticky="nsew")
        list_view.rowconfigure(0, weight=1)
        list_view.columnconfigure(0, weight=1)
        list_view.columnconfigure(1, minsize=14)
        self.listbox = tk.Listbox(list_view, height=11, width=1, exportselection=False, bd=0,
                                 highlightthickness=0, relief="flat", activestyle="none", font=(FONT, 10),
                                 bg=PALETTE["surface"], fg=PALETTE["text"], selectborderwidth=0,
                                 selectbackground=PALETTE["selected"], selectforeground=PALETTE["heading"])
        self.listbox.grid(row=0, column=0, sticky="nsew")
        list_scroll = AutoHideScrollbar(list_view, command=self.listbox.yview)
        list_scroll.attach(self.listbox, list_view)
        self.listbox.configure(yscrollcommand=list_scroll.set)
        self.listbox.bind("<<ListboxSelect>>", self.show_selected)
        preview_panel = surface(panels, padding=12)
        preview_panel.rowconfigure(1, weight=1)
        preview_panel.columnconfigure(0, weight=1)
        ttk.Label(preview_panel, text="签名预览", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 10))
        preview_host = ttk.Frame(preview_panel, style="Surface.TFrame", width=1, height=240)
        preview_host.grid(row=1, column=0, sticky="nsew")
        preview_host.grid_propagate(False)
        preview_host.rowconfigure(0, weight=1)
        preview_host.columnconfigure(0, weight=1)
        self.preview = ttk.Label(preview_host, text="正在读取签名库…", anchor="center",
                                 style="Surface.TLabel", padding=10, wraplength=230)
        self.preview.grid(row=0, column=0, sticky="nsew")
        self.preview.bind("<Configure>", lambda event: self.preview.configure(wraplength=max(100, event.width - 24)))
        library_layout = None
        def layout_library(event=None):
            nonlocal library_layout
            wide = panels.winfo_width() >= 640
            if wide == library_layout:
                return
            library_layout = wide
            list_panel.grid(row=0, column=0, columnspan=1 if wide else 2, sticky="nsew",
                            padx=(0, 12 if wide else 0), pady=(0, 0 if wide else 12))
            preview_panel.grid(row=0 if wide else 1, column=1 if wide else 0,
                               columnspan=1 if wide else 2, sticky="nsew")
            self.listbox.configure(height=11 if wide else 6)
        panels.bind("<Configure>", layout_library)
        layout_library()
        self.notice = ttk.Label(body, style="Notice.TLabel", justify="left", wraplength=550)
        self.notice.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        style.configure("SignatureCaption.TLabel", background=PALETTE["surface"], foreground=PALETTE["muted"], font=(FONT, 9, "bold"))
        style.configure("SignaturePreview.TLabel", background="#f8fafc", foreground=PALETTE["muted"], font=(FONT, 9))
        style.configure("Signature.TCombobox", font=(FONT, 10), padding=(10, 8), arrowsize=14,
                        foreground=PALETTE["text"], fieldbackground="#fafbfd", relief="flat", borderwidth=1,
                        background="#fafbfd", bordercolor="#d9e1eb", lightcolor="#d9e1eb",
                        darkcolor="#d9e1eb", arrowcolor=PALETTE["blue"])
        style.map("Signature.TCombobox", fieldbackground=[("disabled", "#f0f3f7"), ("readonly", "#fafbfd")],
                  selectbackground=[("readonly", "#fafbfd")], selectforeground=[("readonly", PALETTE["text"])],
                  background=[("disabled", "#f0f3f7"), ("!disabled", "#fafbfd")],
                  bordercolor=[("focus", "#8caff7"), ("active", "#8caff7")],
                  lightcolor=[("focus", "#8caff7"), ("active", "#8caff7")],
                  darkcolor=[("focus", "#8caff7"), ("active", "#8caff7")])
        wheel_events = ("<MouseWheel>", "<Shift-MouseWheel>", "<Button-4>", "<Button-5>")
        role_cards = {}
        for key, sheet, label in SLOTS:
            if sheet not in role_cards:
                card = surface(roles_body, padding=16)
                card.grid(row=len(role_cards), column=0, sticky="ew", pady=(0, 12))
                card.columnconfigure((0, 1), weight=1, uniform="signature-fields")
                heading = tk.Frame(card, bg=PALETTE["surface"])
                heading.grid(row=0, column=0, columnspan=2, sticky="ew")
                tk.Frame(heading, bg=PALETTE["blue"], width=3, height=18).pack(side="left", padx=(0, 8))
                ttk.Label(heading, text=f"{sheet}单", style="Section.TLabel").pack(side="left")
                role_cards[sheet] = (card, 0)
            card, column = role_cards[sheet]
            padding = (0, 8) if column == 0 else (8, 0)
            caption = ttk.Label(card, text=label, style="SignatureCaption.TLabel")
            caption.grid(row=1, column=column, sticky="w", padx=padding, pady=(16, 6))
            self.role_labels[key] = caption
            combo = ttk.Combobox(card, state="readonly", width=1, style="Signature.TCombobox")
            combo.grid(row=2, column=column, sticky="ew", padx=padding, pady=(0, 2))
            combo.bind("<<ComboboxSelected>>", lambda event, slot=key: self.assign(slot))
            for sequence in wheel_events:
                # Widget binding runs before TCombobox's wheel-to-change class binding.
                combo.bind(sequence, self._scroll_body)
            self.selectors[key] = combo
            preview_box = tk.Frame(card, bg="#f8fafc", width=1, height=110,
                                   highlightthickness=1, highlightbackground="#e7ecf3")
            preview_box.grid(row=3, column=column, sticky="ew", padx=padding, pady=(10, 0))
            preview_box.grid_propagate(False)
            preview_box.rowconfigure(0, weight=1)
            preview_box.columnconfigure(0, weight=1)
            thumbnail = ttk.Label(preview_box, text="正在读取签名…", style="SignaturePreview.TLabel",
                                  anchor="center", justify="center", padding=6, wraplength=200)
            thumbnail.grid(row=0, column=0, sticky="nsew")
            thumbnail.bind("<Configure>", lambda event, label=thumbnail: label.configure(wraplength=max(100, event.width - 16)))
            self.role_previews[key] = thumbnail
            role_cards[sheet] = (card, column + 1)
        self.roles_notice = ttk.Label(roles_body, style="Notice.TLabel",
                                      justify="left", wraplength=550)
        self.roles_notice.grid(row=len(role_cards), column=0, sticky="ew")
        roles_body.bind("<Configure>", lambda event: self.roles_notice.configure(wraplength=max(100, event.width - 40)), add="+")
        body.bind("<Configure>", lambda event: self.notice.configure(wraplength=max(100, event.width - 40)), add="+")
        for sequence in wheel_events:
            dialog.bind(sequence, self._scroll_body, add="+")
            self.listbox.bind(sequence, self._scroll_library)
        role_actions = ttk.Frame(roles_body)
        role_actions.grid(row=len(role_cards) + 1, column=0, sticky="ew", pady=(4, 2))
        self.role_status = ttk.Label(role_actions, text="正在读取签名库…", foreground=PALETTE["muted"])
        self.role_status.pack(side="left")
        self.save_button = ttk.Button(role_actions, text="保存", command=self.save_bindings, style="ExecuteAction.TButton", cursor="hand2")
        self.save_button.pack(side="right")
        footer = self.footer = ttk.Frame(frame)
        footer.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.status = ttk.Label(footer, text="正在读取签名库…", foreground=PALETTE["muted"])
        self.status.pack(side="left")
        dialog.bind("<Destroy>", self._on_destroy, add="+")
        self._select_tab("roles")
        self.load()
        self.poll_id = dialog.after(40, self._poll)

    def _select_tab(self, key, *, focus=False):
        """Switch presentation only; keep the existing drafts and background tasks."""
        for name, page in self.tab_pages.items():
            selected = name == key
            if selected:
                page.grid(row=0, column=0, sticky="nsew")
            else:
                page.grid_remove()
            self.tab_buttons[name].state(("selected",) if selected else ("!selected",))
            self.tab_lines[name].configure(bg=PALETTE["blue"] if selected else PALETTE["surface"])
        self.active_tab = key
        self._update_footer()
        if focus:
            self.tab_buttons[key].focus_set()
        return "break"

    def _cycle_tab(self, direction):
        keys = tuple(self.tab_pages)
        return self._select_tab(keys[(keys.index(self.active_tab) + direction) % len(keys)], focus=True)

    def _update_footer(self):
        if self.active_tab == "library" and self.status.cget("text"):
            self.footer.grid()
        else:
            self.footer.grid_remove()

    def _set_status(self, text):
        self.role_status.configure(text=text)
        self.status.configure(text=text)
        self._update_footer()

    def _request_role_previews(self):
        if self.closed:
            return
        items = {item["id"]: item for item in self.items}
        cached = {self.role_preview_keys[key]: photo for key, photo in self.role_photos.items()
                  if key in self.role_preview_keys}
        desired, missing = {}, {}
        for key, combo in self.selectors.items():
            index = combo.current()
            item_id = self.selector_ids[index] if 0 <= index < len(self.selector_ids) else None
            item = items.get(item_id)
            if self.needs_refresh or item is None:
                self.role_photos.pop(key, None)
                self.role_preview_keys.pop(key, None)
                attention = key in self.pending_attention or (key in self.data.get("attention", {}) and key not in self.pending_bindings)
                message = "请刷新签名库后核对" if self.needs_refresh else "请重新确认签名" if attention else "未使用签名"
                self.role_previews[key].configure(image="", text=message)
                continue
            fingerprint = (item_id, item["sha256"])
            desired[key] = fingerprint
            if fingerprint in cached:
                self.role_photos[key] = cached[fingerprint]
                self.role_preview_keys[key] = fingerprint
                self.role_previews[key].configure(image=cached[fingerprint], text="")
            else:
                self.role_photos.pop(key, None)
                self.role_preview_keys.pop(key, None)
                self.role_previews[key].configure(image="", text="正在读取预览…")
                missing[key] = fingerprint
        self.role_preview_expected = desired
        if not missing:
            self.tasks.cancel_role_previews()
            self.role_preview_request = None
            return
        revision = self.store.revision(self.data)
        if self.role_preview_request and self.role_preview_request[1:] == (missing, revision):
            return
        item_ids = tuple(dict.fromkeys(fingerprint[0] for fingerprint in missing.values()))
        request = self.tasks.submit("role_previews", item_ids, revision)
        self.role_preview_request = (request, missing, revision)

    def _show_role_previews(self, request, value, error):
        if not self.role_preview_request or request != self.role_preview_request[0]:
            return
        _, expected, _ = self.role_preview_request
        self.role_preview_request = None
        photos = {}
        for key, fingerprint in expected.items():
            if self.role_preview_expected.get(key) != fingerprint:
                continue
            image, problem = (value or {}).get(fingerprint[0], (None, True)) if error is None else (None, True)
            try:
                if problem or image is None:
                    raise ValueError("Preview unavailable")
                if fingerprint not in photos:
                    photos[fingerprint] = ImageTk.PhotoImage(image, master=self.dialog)
                self.role_photos[key] = photos[fingerprint]
                self.role_preview_keys[key] = fingerprint
                self.role_previews[key].configure(image=photos[fingerprint], text="")
            except (OSError, ValueError, tk.TclError):
                self.role_photos.pop(key, None)
                self.role_preview_keys.pop(key, None)
                self.role_previews[key].configure(image="", text="预览暂不可用，请刷新签名库")

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
            canvas = self.roles_canvas if self.active_tab == "roles" else self.canvas
            first, last = canvas.yview()
            if (units < 0 and first > 0) or (units > 0 and last < 1):
                canvas.yview_scroll(units * 3, "units")
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
            fingerprints = {item["id"]: item["sha256"] for item in items}
            for key, item_id in list(self.pending_bindings.items()):
                if item_id is not None and (item_id not in fingerprints
                        or fingerprints[item_id] != self.pending_fingerprints.get(key)):
                    del self.pending_bindings[key]
                    self.pending_fingerprints.pop(key, None)
                    self.pending_attention.add(key)
            self._show_warnings()
            empty = "（不使用签名）"
            while empty in labels:
                empty += " "
            self.selector_ids = [None] + [item["id"] for item in self.items]
            for key, combo in self.selectors.items():
                if changed or not combo.cget("values"):
                    combo.configure(values=[empty] + labels)
                bound = (None if key in self.pending_attention else
                         self.pending_bindings.get(key, data["bindings"].get(key)))
                combo.current(self.selector_ids.index(bound) if bound in self.selector_ids else 0)
            self.show_selected()
            self._request_role_previews()
        finally:
            self.refreshing = False
            self.canvas.yview_moveto(body_position)

    def _show_warnings(self):
        attention = ((set(self.data.get("attention", {})) | self.pending_attention)
                     - self.pending_bindings.keys())
        warnings = list(self.data.get("issues", []))
        affected = [f"{sheet} · {role}" for key, sheet, role in SLOTS if key in attention]
        if affected:
            warnings.insert(0, "以下位置需要重新确认：" + "、".join(affected) + "。请选择标签，或明确选择不使用签名。")
        shown = warnings[:5]
        if len(warnings) > len(shown):
            shown.append(f"另有 {len(warnings) - len(shown)} 项，请处理后刷新列表。")
        for notice in (self.notice, self.roles_notice):
            notice.configure(text="\n".join(shown))
            if warnings:
                notice.grid()
            else:
                notice.grid_remove()
        for key, sheet, role in SLOTS:
            pending = key in attention
            self.role_labels[key].configure(text=role + ("  ·  需确认" if pending else ""),
                                            foreground="#946522" if pending else PALETTE["muted"])

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
        can_save = bool(self.pending_bindings) and not self.busy and not self.needs_refresh and not self.pending_attention
        self.save_button.configure(state="normal" if can_save else "disabled", cursor="hand2" if can_save else "arrow")

    def _begin(self, kind, *args, selected=None, action=None, path=None, **kwargs):
        if self.busy or self.closed:
            return
        self.busy = True
        self.control_kind = kind
        self.tasks.cancel_preview()
        self.preview_request = None
        self.tasks.cancel_role_previews()
        self.role_preview_request = None
        self._update_controls()
        self._set_status("正在保存签名库…" if kind == "mutate" else "正在处理签名库…")
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
            if kind == "role_previews":
                self._show_role_previews(request, value, error)
                continue
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
                if isinstance(error, SignatureRefreshError):
                    if action == "save_bindings":
                        self.saved_awaiting_refresh = True
                    status = "签字位置已保存，请刷新列表核对。" if action == "save_bindings" else "签名已保存，请刷新列表核对。"
                else:
                    status = "操作未完成，请刷新列表核对。"
                self._set_status(status)
                messagebox.showerror("签名库", _error_text(error), parent=self.dialog)
                continue
            if kind == "mutate":
                data, result = value
                selected = result if isinstance(result, str) else selected
            else:
                data = value
            saved_positions = action == "save_bindings" or self.saved_awaiting_refresh
            if saved_positions:
                self.pending_bindings.clear()
                self.pending_fingerprints.clear()
                self.saved_awaiting_refresh = False
            self.refresh(data, selected=selected)
            self._set_status("签字位置已保存" if saved_positions else
                                  "签字位置尚未保存" if self.pending_bindings else "")
            if action and action != "save_bindings":
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
        self.role_preview_request = None
        self.tasks.close()

    def close(self):
        if self.control_kind == "mutate":
            self._set_status("正在保存签名库，请稍候再关闭…")
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
                if self.data["bindings"].get(key) == item_id or self.pending_bindings.get(key) == item_id]

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
            item_id = self.selector_ids[index]
            self.pending_bindings[key] = item_id
            self.pending_fingerprints[key] = next((item["sha256"] for item in self.items if item["id"] == item_id), None)
            self.pending_attention.discard(key)
            self._show_warnings()
            self._update_controls()
            self._set_status("签字位置尚未保存")
            self._request_role_previews()

    def save_bindings(self):
        if self.busy or self.closed or self.needs_refresh or self.pending_attention or not self.pending_bindings:
            return
        self._begin("mutate", "assign_many", dict(self.pending_bindings), action="save_bindings",
                    expected_revision=self.store.revision(self.data), selected=self.selected_id())
