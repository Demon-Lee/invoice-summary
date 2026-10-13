"""Business-style native presentation, separate from invoice operations."""
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from . import __version__

FONT = "Microsoft YaHei UI"
PALETTE = {
    "background": "#f3f5f9", "surface": "#ffffff", "text": "#243247",
    "heading": "#17315c", "muted": "#69778b", "line": "#e2e7ef",
    "blue": "#2563eb", "blue_hover": "#1e54cb", "selected": "#e3edff",
}
STAGES = {
    "idle": ("#f3f5f9", "#586a83", "#d8e0eb", "等待预览"),
    "working": ("#eef4ff", "#23509d", "#d4e1fa", "正在处理"),
    "success": ("#f0f9f4", "#22674c", "#cce4d8", "阶段完成"),
    "warning": ("#fff8e9", "#8a601e", "#ecdbb4", "需要处理"),
    "error": ("#fff0ee", "#a13d36", "#efd1cb", "未完成"),
}


def configure_theme(root):
    root.configure(bg=PALETTE["background"])
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", font=(FONT, 10), background=PALETTE["background"], foreground=PALETTE["text"])
    style.configure("TFrame", background=PALETTE["background"])
    style.configure("TLabel", background=PALETTE["background"], foreground=PALETTE["text"])
    style.configure("Surface.TFrame", background=PALETTE["surface"])
    style.configure("Surface.TLabel", background=PALETTE["surface"])
    style.configure("Title.TLabel", background=PALETTE["surface"], foreground=PALETTE["heading"], font=(FONT, 18, "bold"))
    style.configure("Subtitle.TLabel", background=PALETTE["surface"], foreground=PALETTE["muted"], font=(FONT, 9))
    style.configure("Section.TLabel", background=PALETTE["surface"], foreground=PALETTE["heading"], font=(FONT, 11, "bold"))
    style.configure("Muted.TLabel", background=PALETTE["surface"], foreground=PALETTE["muted"], font=(FONT, 9))
    style.configure("Guide.TLabel", background=PALETTE["surface"], foreground="#46556c", font=(FONT, 9))
    style.configure("Step.TLabel", background="#edf3ff", foreground=PALETTE["blue"], font=(FONT, 9, "bold"), padding=(4, 0))
    style.configure("Version.TLabel", background="#f1f4f9", foreground="#586a83", font=(FONT, 10), padding=(10, 4))
    style.configure("Notice.TLabel", background="#fff8e9", foreground="#896024", font=(FONT, 9), padding=(10, 5))
    style.configure("Metric.TLabel", background=PALETTE["surface"], foreground="#273d5d", font=("Segoe UI", 17, "bold"))
    style.configure("MetricAmount.TLabel", background="#f4f8ff", foreground=PALETTE["blue"], font=("Segoe UI", 17, "bold"))
    style.configure("MetricAmountCaption.TLabel", background="#f4f8ff", foreground="#647d9f", font=(FONT, 9))
    style.configure("MetricCorrection.TLabel", background=PALETTE["surface"], foreground="#a0742a", font=("Segoe UI", 17, "bold"))
    style.configure("TButton", padding=(11, 6), borderwidth=1, relief="flat", focusthickness=2, focuscolor="#93b4ff")
    for name, background, foreground, border in (
        ("Secondary", "#ffffff", "#42536e", "#ccd6e3"),
        ("Primary", PALETTE["blue"], "#ffffff", PALETTE["blue"]),
        ("Link", PALETTE["background"], "#66758c", PALETTE["background"]),
    ):
        style.configure(f"{name}.TButton", background=background, foreground=foreground, bordercolor=border, lightcolor=border, darkcolor=border)
        style.map(f"{name}.TButton", background=[("disabled", "#f0f3f7"), ("pressed", "#dbe6fa" if name != "Primary" else "#194bb7"), ("active", "#edf3ff" if name != "Primary" else PALETTE["blue_hover"])], foreground=[("disabled", "#9aa5b5")], bordercolor=[("disabled", "#e0e6ee")])
    style.configure("TEntry", fieldbackground="#fafbfd", foreground="#53637b", bordercolor="#d9e1eb", lightcolor="#d9e1eb", darkcolor="#d9e1eb", padding=(8, 5))
    style.map("TEntry", bordercolor=[("focus", "#8caff7")], fieldbackground=[("disabled", "#f0f3f7")])
    configure_navigation(root, style)
    style.configure("Treeview", rowheight=30, font=(FONT, 9), background=PALETTE["surface"], fieldbackground=PALETTE["surface"], foreground="#445570", borderwidth=0)
    style.configure("Treeview.Heading", font=(FONT, 9, "bold"), padding=(8, 6), background="#f2f5f9", foreground="#53647c", borderwidth=0, relief="flat")
    style.map("Treeview", background=[("selected", PALETTE["selected"])], foreground=[("selected", "#17315c")])
    style.map("Treeview.Heading", background=[("active", "#e8edf5")])
    style.configure("Vertical.TScrollbar", background="#c1ccda", troughcolor="#f4f6fa", borderwidth=0, arrowsize=12)
    style.configure("Horizontal.TScrollbar", background="#c1ccda", troughcolor="#f4f6fa", borderwidth=0, arrowsize=12)
    style.configure("Horizontal.TProgressbar", background=PALETTE["blue"], troughcolor="#e8edf5", borderwidth=0, thickness=3)


def configure_navigation(root, style):
    """Replace the themed tab border with a white surface and fixed bottom line."""
    element = "InvoiceNavigation.tab"
    if element not in style.element_names():
        images = {}
        for state, background, selected in (
            ("normal", PALETTE["surface"], False),
            ("selected", PALETTE["surface"], True),
            ("active", "#f4f7fc", False),
            ("selected_active", "#f4f7fc", True),
        ):
            image = tk.PhotoImage(master=root, width=2, height=8)
            image.put(background, to=(0, 0, 2, 8))
            if selected:
                image.put(PALETTE["blue"], to=(0, 5, 2, 8))
            images[state] = image
        # Tk style stores image names; Python must keep the actual images alive.
        root._navigation_images = images
        style.element_create(element, "image", images["normal"],
                             ("selected", "active", images["selected_active"]),
                             ("selected", images["selected"]), ("active", images["active"]),
                             border=(0, 0, 0, 3), padding=(0, 0, 0, 3), sticky="nswe")
    style.configure("Underline.TNotebook", background=PALETTE["surface"], borderwidth=0,
                    bordercolor=PALETTE["surface"], lightcolor=PALETTE["surface"],
                    darkcolor=PALETTE["surface"], tabmargins=(18, 0, 18, 0))
    style.configure("Underline.TNotebook.Tab", background=PALETTE["surface"], foreground="#62718a",
                    font=(FONT, 9), padding=(14, 8, 14, 8), expand=(0, 0, 0, 0),
                    focusthickness=1, focuscolor="#93b4ff")
    style.map("Underline.TNotebook.Tab", foreground=[("disabled", "#9aa5b5"), ("selected", PALETTE["blue"])],
              font=[("selected", (FONT, 9, "bold"))],
              padding=[("selected", (14, 8, 14, 8))], expand=[("selected", (0, 0, 0, 0))])
    style.layout("Underline.TNotebook", [("Notebook.client", {"sticky": "nswe"})])
    style.layout("Underline.TNotebook.Tab", [(element, {"sticky": "nswe", "children": [
        ("Notebook.padding", {"sticky": "nswe", "children": [
            ("Notebook.focus", {"sticky": "nswe", "children": [
                ("Notebook.label", {"sticky": "nswe"}),
            ]}),
        ]}),
    ]})])


def surface(parent, *, background=None, padding=0):
    return tk.Frame(parent, bg=background or PALETTE["surface"], padx=padding, pady=padding,
                    highlightthickness=1, highlightbackground=PALETTE["line"], highlightcolor=PALETTE["line"])


def text_widget(parent, height=15):
    return ScrolledText(parent, height=height, wrap="word", bg=PALETTE["surface"], fg=PALETTE["text"],
                        relief="flat", bd=0, padx=12, pady=8, font=(FONT, 9), state="disabled",
                        selectbackground=PALETTE["selected"], selectforeground=PALETTE["heading"])


def draw_stage_icon(canvas, tone, background, foreground):
    canvas.configure(bg=background)
    canvas.delete("all")
    canvas.create_oval(2, 2, 30, 30, outline=foreground, width=1)
    if tone == "success":
        canvas.create_line(9, 16, 14, 21, 24, 10, fill=foreground, width=2)
    elif tone in ("warning", "error"):
        if tone == "warning":
            canvas.create_line(16, 8, 16, 19, fill=foreground, width=2)
            canvas.create_oval(15, 23, 17, 25, fill=foreground, outline=foreground)
        else:
            canvas.create_line(10, 10, 22, 22, fill=foreground, width=2)
            canvas.create_line(22, 10, 10, 22, fill=foreground, width=2)
    else:
        canvas.create_line(16, 8, 16, 16, 22, 19, fill=foreground, width=2)


def set_stage_style(app, tone):
    app.stage_tone = tone
    background, foreground, border, badge = STAGES[tone]
    app.stage_card.configure(bg=background, highlightbackground=border, highlightcolor=border)
    for label in (app.stage_heading, app.stage_body, app.stage_badge):
        label.configure(bg=background, fg=foreground)
    if tone == "success" and not app.busy and str(app.execute.cget("state")) == "normal":
        badge = "可以执行"
    app.stage_badge.configure(text=badge)
    draw_stage_icon(app.stage_icon, tone, background, foreground)


def guide_card(parent, column, title, items, *, numbered=False):
    card = surface(parent, padding=10)
    card.grid(row=0, column=column, sticky="nsew", padx=(0, 6) if column == 0 else (6, 0))
    card.columnconfigure(1, weight=1)
    ttk.Label(card, text=title, style="Section.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))
    labels = []
    for row, text in enumerate(items, 1):
        marker, _, content = text.partition(". ") if numbered else ("·", "", text)
        ttk.Label(card, text=marker if numbered else "·", style="Step.TLabel" if numbered else "Muted.TLabel").grid(row=row, column=0, sticky="nw", padx=(0, 7), pady=1)
        label = ttk.Label(card, text=content, style="Guide.TLabel", wraplength=460, justify="left")
        label.grid(row=row, column=1, sticky="ew", pady=1)
        labels.append(label)
    card.bind("<Configure>", lambda event: [label.configure(wraplength=max(140, event.width - 56)) for label in labels])
    return card


def build_interface(app, *, execution_steps, necessary_conditions, process_notice, preview_note,
                    help_text, boundary_guide, retained_features):
    root = app.root
    root.title(f"发票汇总助手 V{__version__}")
    root.geometry("1220x940")
    root.minsize(900, 760)
    configure_theme(root)
    outer = ttk.Frame(root, padding=(12, 0, 12, 8))
    outer.pack(fill="both", expand=True)
    header = tk.Frame(outer, bg=PALETTE["surface"], padx=18, pady=10)
    header.pack(fill="x")
    brand_icon = tk.Canvas(header, width=33, height=37, bg=PALETTE["blue"], highlightthickness=0)
    brand_icon.pack(side="left", padx=(0, 11))
    brand_icon.create_line(9, 6, 24, 6, 24, 31, 20, 28, 17, 31, 13, 28, 9, 31, 9, 6, fill="white", width=1.5)
    for y in (12, 17, 22):
        brand_icon.create_line(12, y, 21, y, fill="white", width=1.5)
    brand = ttk.Frame(header, style="Surface.TFrame")
    brand.pack(side="left")
    ttk.Label(brand, text="发票汇总助手", style="Title.TLabel").pack(anchor="w")
    ttk.Label(brand, text="先预览，再执行 · 逐分复核金额", style="Subtitle.TLabel").pack(anchor="w")
    ttk.Label(header, text=f"V{__version__}", style="Version.TLabel").pack(side="right")
    ttk.Label(header, text="离线处理", style="Subtitle.TLabel").pack(side="right", padx=(0, 16))
    tabs = ttk.Notebook(outer, style="Underline.TNotebook")
    tabs.pack(fill="both", expand=True)
    process = ttk.Frame(tabs, padding=(12, 10))
    rules = ttk.Frame(tabs, padding=(16, 14))
    help_tab = ttk.Frame(tabs, padding=(16, 14))
    for frame, name in ((process, "处理发票"), (rules, "规则与更新"), (help_tab, "使用说明")):
        tabs.add(frame, text=name)
    process.columnconfigure(0, weight=1)
    process.rowconfigure(7, weight=1)
    guidance = ttk.Frame(process)
    guidance.grid(row=0, column=0, sticky="ew", pady=(0, 7))
    guidance.columnconfigure((0, 1), weight=1, uniform="guidance")
    guide_card(guidance, 0, "执行步骤", execution_steps, numbered=True)
    guide_card(guidance, 1, "必要条件", necessary_conditions)
    notice = ttk.Label(process, text=process_notice, style="Notice.TLabel", wraplength=1050, justify="left")
    notice.grid(row=1, column=0, sticky="ew", pady=(0, 7))
    process.bind("<Configure>", lambda event: notice.configure(wraplength=max(180, event.width - 48)))
    files = surface(process, padding=9)
    files.grid(row=2, column=0, sticky="ew", pady=(0, 7))
    files.columnconfigure(1, weight=1)
    for row, label, variable, action, button_name in (
        (0, "PDF 文件夹", app.pdf, app._pick_pdf, "选择文件夹"),
        (1, "目标工作簿", app.book, app._pick_book, "选择工作簿"),
    ):
        ttk.Label(files, text=label, style="Surface.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 12), pady=3)
        entry = ttk.Entry(files, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", pady=3)
        app.interactive.append(entry)
        app._button(files, button_name, action).grid(row=row, column=2, padx=(10, 0), pady=3)
    actions = ttk.Frame(process)
    actions.grid(row=3, column=0, sticky="ew", pady=(0, 7))
    app.preview_button = app._button(actions, "只读预览", app._preview, style="Primary.TButton")
    app.preview_button.pack(side="left", padx=(0, 8))
    app.execute = app._button(actions, "执行处理", app._apply)
    app.execute.pack(side="left", padx=(0, 8))
    app.execute.configure(state="disabled")
    app.correct_button = app._button(actions, "人工校正", app._edit_detail)
    app.correct_button.pack(side="left")
    app.correct_button.configure(state="disabled")
    app._button(actions, "打开工作簿", lambda: app._open(app.book.get()), style="Link.TButton").pack(side="right")
    app._button(actions, "打开发票目录", lambda: app._open(app.pdf.get()), style="Link.TButton").pack(side="right", padx=(0, 4))
    app.stage_card = surface(process, padding=9)
    app.stage_card.grid(row=4, column=0, sticky="ew", pady=(0, 7))
    app.stage_card.columnconfigure(1, weight=1)
    app.stage_icon = tk.Canvas(app.stage_card, width=32, height=32, highlightthickness=0)
    app.stage_icon.grid(row=0, column=0, rowspan=2, padx=(0, 10))
    app.stage_heading = tk.Label(app.stage_card, textvariable=app.stage_title, font=(FONT, 12, "bold"), anchor="w", justify="left")
    app.stage_heading.grid(row=0, column=1, sticky="ew")
    app.stage_body = tk.Label(app.stage_card, textvariable=app.stage_detail, font=(FONT, 9), anchor="w", justify="left", wraplength=950)
    app.stage_body.grid(row=1, column=1, sticky="ew", pady=(2, 0))
    app.stage_badge = tk.Label(app.stage_card, font=(FONT, 9), padx=8, pady=3)
    app.stage_badge.grid(row=0, column=2, rowspan=2, padx=(12, 0))
    app.stage_card.bind("<Configure>", lambda event: [label.configure(wraplength=max(180, event.width - 180)) for label in (app.stage_heading, app.stage_body)])
    app._set_stage("idle", app.stage_title.get(), app.stage_detail.get())
    metrics = ttk.Frame(process)
    metrics.grid(row=5, column=0, sticky="ew", pady=(0, 7))
    for column, title, variable, style_name in (
        (0, "发票数量（张）", app.metric_invoices, "Metric.TLabel"),
        (1, "明细数量（条）", app.metric_rows, "Metric.TLabel"),
        (2, "本批金额", app.metric_total, "MetricAmount.TLabel"),
        (3, "人工校正（条）", app.metric_corrections, "MetricCorrection.TLabel"),
    ):
        metrics.columnconfigure(column, weight=1, uniform="metrics")
        card = surface(metrics, background="#f4f8ff" if column == 2 else None, padding=8)
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 4, 0 if column == 3 else 4))
        caption = "MetricAmountCaption.TLabel" if column == 2 else "Muted.TLabel"
        ttk.Label(card, text=title, style=caption).pack(anchor="w")
        value = ttk.Label(card, textvariable=variable, style=style_name)
        value.pack(anchor="w", fill="x")
        card.bind("<Configure>", lambda event, label=value: label.configure(wraplength=max(100, event.width - 20)))
    table_heading = ttk.Frame(process)
    table_heading.grid(row=6, column=0, sticky="ew", pady=(0, 4))
    ttk.Label(table_heading, text="发票明细", font=(FONT, 11, "bold")).pack(side="left", padx=(0, 10))
    app.preview_note.set(preview_note)
    note = ttk.Label(table_heading, textvariable=app.preview_note, font=(FONT, 9), foreground=PALETTE["muted"], wraplength=900, justify="left")
    note.pack(side="left", fill="x", expand=True)
    note.bind("<Configure>", lambda event: note.configure(wraplength=max(140, event.width - 4)))
    table = surface(process)
    table.grid(row=7, column=0, sticky="nsew")
    table.rowconfigure(0, weight=1)
    table.columnconfigure(0, weight=1)
    columns = ("sequence", "filename", "product_name", "spec", "unit", "quantity", "price", "amount", "manufacturer", "correction")
    app.tree = ttk.Treeview(table, columns=columns, show="headings", height=4)
    for name, label, width in zip(columns, ("序号", "PDF → 新文件名", "产品名称", "规格型号", "单位", "数量", "单价（自动）", "含税金额", "生产厂家", "人工校正"), (48, 250, 170, 110, 48, 65, 95, 100, 175, 84)):
        app.tree.heading(name, text=label, anchor="e" if name in ("quantity", "price", "amount") else "w" if name in ("filename", "product_name", "spec", "manufacturer") else "center")
        app.tree.column(name, width=width, minwidth=40, anchor="e" if name in ("quantity", "price", "amount") else "w" if name in ("filename", "product_name", "spec", "manufacturer") else "center", stretch=name == "filename")
    app.tree.tag_configure("even", background="#ffffff")
    app.tree.tag_configure("odd", background="#f8fafd")
    app.tree.tag_configure("corrected", background="#fff8e5")
    app.tree.bind("<Double-1>", app._edit_detail)
    app.tree.grid(row=0, column=0, sticky="nsew")
    vertical = ttk.Scrollbar(table, orient="vertical", command=app.tree.yview)
    vertical.grid(row=0, column=1, sticky="ns")
    horizontal = ttk.Scrollbar(table, orient="horizontal", command=app.tree.xview)
    horizontal.grid(row=1, column=0, sticky="ew")
    app.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
    report_heading = ttk.Frame(process)
    report_heading.grid(row=8, column=0, sticky="ew", pady=(7, 3))
    ttk.Label(report_heading, text="检查、异常与实际结果", font=(FONT, 11, "bold")).pack(side="left")
    app.copy_report_button = app._button(report_heading, "复制报告", app._copy_report, style="Link.TButton")
    app.copy_report_button.pack(side="right")
    app.copy_report_button.configure(state="disabled")
    report_panel = surface(process)
    report_panel.grid(row=9, column=0, sticky="ew")
    app.report = app._text(report_panel, height=3)
    app.report.pack(fill="both", expand=True)
    footer = ttk.Frame(outer)
    footer.pack(fill="x", pady=(6, 0))
    ttk.Label(footer, textvariable=app.status, font=(FONT, 9), foreground=PALETTE["muted"], wraplength=850).pack(side="left")
    ttk.Label(footer, text="共享规则版本见“规则与更新”", font=(FONT, 9), foreground=PALETTE["muted"]).pack(side="right")
    app.progress_bar = ttk.Progressbar(outer, mode="indeterminate", length=100)
    app.progress_bar.pack(fill="x", pady=(4, 0))
    build_rules(app, rules, boundary_guide, retained_features)
    help_panel = surface(help_tab)
    help_panel.pack(fill="both", expand=True)
    help_widget = app._text(help_panel)
    help_widget.pack(fill="both", expand=True)
    app._set_text(help_widget, help_text)
    app._mark_headings(help_widget, help_text)


def build_rules(app, parent, boundary_guide, retained_features):
    overview = surface(parent, padding=14)
    overview.pack(fill="x", pady=(0, 12))
    ttk.Label(overview, textvariable=app.version, style="Section.TLabel").pack(anchor="w", pady=(0, 9))
    for text in (
        "普通用户：完整解压即可使用随包规则，无需安装或同步 skill。下面的本机同步、导出和分发操作供维护者使用。",
        "维护者：同步仅更新共享规则，人工校正、清空重填等功能保留。更新成功后关闭软件，打包整个软件文件夹分发。",
        f"软件文件夹：{app.application_dir}",
    ):
        label = ttk.Label(overview, text=text, style="Muted.TLabel", wraplength=1050, justify="left")
        label.pack(anchor="w", fill="x", pady=2)
        overview.bind("<Configure>", lambda event, item=label: item.configure(wraplength=max(180, event.width - 34)), add="+")
    source_panel = surface(parent, padding=12)
    source_panel.pack(fill="x", pady=(0, 12))
    ttk.Label(source_panel, text="本机规则来源", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
    source_row = ttk.Frame(source_panel, style="Surface.TFrame")
    source_row.pack(fill="x")
    entry = ttk.Entry(source_row, textvariable=app.source)
    entry.pack(side="left", fill="x", expand=True)
    app.interactive.append(entry)
    app._button(source_row, "选择 skill", app._pick_source).pack(side="left", padx=(8, 0))
    actions = ttk.Frame(source_panel, style="Surface.TFrame")
    actions.pack(fill="x", pady=(9, 5))
    for label, action, style_name in (
        ("同步本机 skill", app._sync, "Primary.TButton"),
        ("打开软件文件夹", lambda: app._open(app.application_dir), "Secondary.TButton"),
        ("导出离线更新包", app._export, "Secondary.TButton"),
        ("导入更新包", app._import, "Secondary.TButton"),
        ("回退版本", app._rollback, "Secondary.TButton"),
        ("解除绑定", app._unbind, "Secondary.TButton"),
    ):
        app._button(actions, label, action, style=style_name).pack(side="left", padx=(0, 6))
    source_status = ttk.Label(source_panel, textvariable=app.source_status, style="Muted.TLabel", wraplength=1050, justify="left")
    source_status.pack(anchor="w", fill="x", pady=(5, 0))
    source_panel.bind("<Configure>", lambda event: source_status.configure(wraplength=max(180, event.width - 32)))
    app.rule_tabs = ttk.Notebook(parent, style="Underline.TNotebook")
    app.rule_tabs.pack(fill="both", expand=True)
    boundary_tab = ttk.Frame(app.rule_tabs, padding=8)
    app.update_tab = ttk.Frame(app.rule_tabs, padding=8)
    reference_tab = ttk.Frame(app.rule_tabs, padding=8)
    for frame, title in ((boundary_tab, "功能归属"), (app.update_tab, "本次更新结果"), (reference_tab, "skill 原始说明")):
        app.rule_tabs.add(frame, text=title)
    app.boundary_text = app._text(boundary_tab)
    app.boundary_text.pack(fill="both", expand=True)
    app._set_text(app.boundary_text, boundary_guide)
    app._mark_headings(app.boundary_text, boundary_guide)
    app.update_text = app._text(app.update_tab)
    app.update_text.pack(fill="both", expand=True)
    app._set_text(app.update_text, "同步、导入或回退共享规则后，这里会显示更新范围和保留的软件功能。\n\n保留的软件功能：" + retained_features)
    reference_label = ttk.Label(reference_tab, text="此页保留 skill 原文作为共享规则来源参考。软件交互、人工校正及整批重填以“功能归属”页为准。", wraplength=1050, foreground=PALETTE["muted"], font=(FONT, 9))
    reference_label.pack(anchor="w", fill="x", pady=(0, 6))
    reference_tab.bind("<Configure>", lambda event: reference_label.configure(wraplength=max(180, event.width - 22)))
    app.rule_text = app._text(reference_tab)
    app.rule_text.pack(fill="both", expand=True)
