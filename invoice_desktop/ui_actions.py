"""Rounded action surfaces and local icons for native ttk buttons."""
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk


ROLES = {
    "Preview": {"fill": "#edf4ff", "hover": "#e2edff", "pressed": "#cfdef8",
                "border": "#91b4ee", "hover_border": "#5e90e0", "ink": "#2459b3"},
    "Execute": {"fill": "#2563eb", "hover": "#1e54cb", "pressed": "#1945a5",
                "border": "#2059d5", "hover_border": "#194bb7", "ink": "#ffffff"},
    "Export": {"fill": "#ffffff", "hover": "#edf4ff", "pressed": "#e2ebf9",
               "border": "#afbfda", "hover_border": "#7398d4", "ink": "#345e9b"},
}
LOCATION_ROLES = ("OpenInvoices", "OpenWorkbook", "OpenExport")
for _role in LOCATION_ROLES:
    ROLES[_role] = {"fill": "#ffffff", "hover": "#eaf2ff", "pressed": "#dce8fa",
                    "border": "#a5b9d8", "hover_border": "#5787ce", "ink": "#24589d"}
INPUT_ROLES = ("ChooseFolder", "ChooseWorkbook")
for _role in INPUT_ROLES:
    ROLES[_role] = dict(ROLES["Execute"])
DISABLED_INK = "#8a97aa"


def _surface_image(colors, state, focused, scale, background):
    """Draw once at 4x; ttk stretches only the straight middle sections."""
    size = round(40 * scale)
    factor = 4
    image = Image.new("RGB", (size * factor, size * factor), background)
    draw = ImageDraw.Draw(image)
    unit = scale * factor
    box = lambda values: tuple(round(value * unit) for value in values)
    disabled, pressed = state == "disabled", state == "pressed"
    fill = "#f0f3f7" if disabled else colors.get(state, colors["fill"])
    border = "#cdd6e2" if disabled else colors["hover_border"] if state != "normal" else colors["border"]
    if focused and not disabled:
        draw.rounded_rectangle(box((0, 0, 39, 39)), radius=round(10 * unit),
                               outline="#7ca5f2", width=max(1, round(1.2 * unit)))
    if not disabled and not pressed:
        draw.rounded_rectangle(box((3, 5, 36, 37)), radius=round(7 * unit), fill="#d5dfed")
    draw.rounded_rectangle(box((3, 4 if pressed else 2, 36, 36 if pressed else 35)),
                           radius=round(7 * unit), fill=fill, outline=border,
                           width=max(1, round(unit)))
    return image.resize((size, size), Image.Resampling.LANCZOS)


def _icon_image(role, color, scale):
    factor = 4
    unit = scale * factor
    location = role in LOCATION_ROLES + INPUT_ROLES
    canvas = (29, 22) if location else (25, 18)
    image = Image.new("RGBA", tuple(round(value * unit) for value in canvas))
    draw = ImageDraw.Draw(image)
    points = lambda values: tuple(round(value * unit) for value in values)
    width = max(1, round((2 if location else 1.7) * unit))
    if role == "Preview":
        draw.ellipse(points((2, 2, 12, 12)), outline=color, width=width)
        draw.line(points((11, 11, 16, 16)), fill=color, width=width)
    elif role == "Execute":
        draw.polygon([points(p) for p in ((4, 2), (15, 9), (4, 16))], fill=color)
    elif role == "Export":
        draw.line(points((10, 16, 3, 16, 3, 2, 11, 2, 15, 6, 15, 9)), fill=color, width=width)
        draw.line(points((11, 2, 11, 6, 15, 6)), fill=color, width=width)
        draw.line(points((15, 10, 15, 16)), fill=color, width=width)
        draw.line(points((12, 13, 15, 16, 18, 13)), fill=color, width=width)
    elif role in ("OpenWorkbook", "ChooseWorkbook"):
        draw.rounded_rectangle(points((3, 2, 20, 20)), radius=round(2 * unit), outline=color, width=width)
        draw.rectangle(points((4, 3, 19, 7)), fill=color)
        draw.line(points((4, 11, 19, 11)), fill=color, width=width)
        draw.line(points((4, 15, 19, 15)), fill=color, width=width)
        draw.line(points((10, 8, 10, 19)), fill=color, width=width)
    elif role in ("OpenInvoices", "OpenExport", "ChooseFolder"):
        draw.polygon([points(p) for p in ((2, 6), (2, 3), (10, 3), (13, 6), (22, 6), (22, 19), (2, 19))], outline=color, width=width)
        if role in ("OpenInvoices", "ChooseFolder"):
            draw.line(points((6, 10, 17, 10)), fill=color, width=width)
            draw.line(points((6, 14, 14, 14)), fill=color, width=width)
        else:
            draw.line(points((12, 8, 12, 16)), fill=color, width=width)
            draw.line(points((8, 12, 12, 16, 16, 12)), fill=color, width=width)
    else:
        draw.polygon([points(p) for p in ((3, 11), (11, 3), (15, 7), (7, 15), (2, 16))],
                     outline=color, width=width)
        draw.line(points((9, 5, 13, 9)), fill=color, width=width)
    return image.resize(tuple(round(value * scale) for value in canvas), Image.Resampling.LANCZOS)


def configure_action_styles(root, style, *, font, background):
    """Keep button semantics and state maps; replace just their themed surface."""
    scale = max(0.75, float(root.tk.call("tk", "scaling")) / (4 / 3))
    root._action_images = {}
    root._action_icons = {}
    for role, colors in ROLES.items():
        element = f"Invoice{role}Action.surface"
        images = {}
        for state, focused in (("normal", False), ("hover", False), ("pressed", False),
                               ("disabled", False), ("normal", True), ("hover", True),
                               ("pressed", True)):
            images[state, focused] = ImageTk.PhotoImage(
                _surface_image(colors, state, focused, scale, "#ffffff" if role in LOCATION_ROLES + INPUT_ROLES else background), master=root)
        root._action_images[role] = images
        edge = round(12 * scale)
        style.element_create(element, "image", images["normal", False],
                             ("disabled", images["disabled", False]),
                             ("pressed", "focus", images["pressed", True]),
                             ("pressed", images["pressed", False]),
                             ("active", "focus", images["hover", True]),
                             ("active", images["hover", False]),
                             ("focus", images["normal", True]),
                             border=(edge, edge, edge, edge),
                             padding=tuple(round(value * scale) for value in (3, 2, 3, 4)),
                             sticky="nswe")
        name = f"{role}Action.TButton"
        style.layout(name, [(element, {"sticky": "nswe", "children": [
            ("Button.padding", {"sticky": "nswe", "children": [
                ("Button.label", {"sticky": "nswe"}),
            ]}),
        ]})])
        compact = role in LOCATION_ROLES + INPUT_ROLES
        style.configure(name, font=(font, 9 if compact else 10, "bold"),
                        foreground=colors["ink"], anchor="center", width=0,
                        padding=(round((12 if compact else 16) * scale), round((6 if compact else 9) * scale)),
                        shiftrelief=0)
        style.map(name, foreground=[("disabled", DISABLED_INK)])
        root._action_icons[role] = tuple(ImageTk.PhotoImage(_icon_image(role, color, scale), master=root)
                                         for color in (colors["ink"], DISABLED_INK))
    root._correction_icons = tuple(ImageTk.PhotoImage(_icon_image("EditHint", color, scale), master=root)
                                   for color in ("#8a5816", DISABLED_INK))


def decorate_action_button(widget: ttk.Button, role: str):
    normal, disabled = widget.winfo_toplevel()._action_icons[role]
    widget.configure(style=f"{role}Action.TButton", image=(normal, "disabled", disabled),
                     compound="left", cursor="hand2")
