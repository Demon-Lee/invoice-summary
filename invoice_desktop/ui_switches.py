"""Modern switch indicators that retain native ttk.Checkbutton behavior."""

from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk


def _switch_image(selected, state, focused, scale, palette):
    factor = 4
    unit = scale * factor
    image = Image.new("RGBA", (round(52 * unit), round(30 * unit)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    box = lambda values: tuple(round(value * unit) for value in values)
    disabled = state == "disabled"
    if selected:
        fill = ("#b7c8e4" if disabled else "#194bb7" if state == "pressed" else
                palette["blue_hover"] if state == "hover" else palette["blue"])
    else:
        fill = "#e0e6ef" if disabled else "#a1afc2" if state == "pressed" else "#b5c1d1" if state == "hover" else "#c5cfdd"
    if focused and not disabled:
        draw.rounded_rectangle(box((1, 2, 47, 28)), radius=round(13 * unit),
                               outline="#8caff7", width=max(1, round(1.2 * unit)))
    draw.rounded_rectangle(box((4, 5, 44, 25)), radius=round(10 * unit), fill=fill)
    center = 34 if selected else 14
    draw.ellipse(box((center - 8, 7, center + 8, 23)), fill="#f7f9fc" if disabled else "#ffffff")
    return image.resize((round(52 * scale), round(30 * scale)), Image.Resampling.LANCZOS)


def configure_signature_toggle(parent, *, font, palette):
    """Return a local switch style with DPI-aware images owned by the Tk root."""
    root = parent._root()
    style = ttk.Style(parent)
    element, name = "InvoiceSignatureToggle.indicator", "SignatureToggle.TCheckbutton"
    images = getattr(root, "_signature_toggle_images", None)
    if images is None:
        scale = max(0.75, float(root.tk.call("tk", "scaling")) / (4 / 3))
        states = (("normal", False), ("hover", False), ("pressed", False), ("disabled", False),
                  ("normal", True), ("hover", True), ("pressed", True))
        images = {(selected, state, focused):ImageTk.PhotoImage(
            _switch_image(selected, state, focused, scale, palette), master=root)
                  for selected in (False, True) for state, focused in states}
        root._signature_toggle_images = images
    if element not in style.element_names():
        mappings = [("disabled", "selected", images[True, "disabled", False]),
                    ("disabled", images[False, "disabled", False])]
        for selected in (True, False):
            prefix = ("selected",) if selected else ()
            for state, focused, native in (("pressed", True, ("pressed", "focus")),
                                           ("pressed", False, ("pressed",)),
                                           ("hover", True, ("active", "focus")),
                                           ("hover", False, ("active",)),
                                           ("normal", True, ("focus",))):
                mappings.append((*prefix, *native, images[selected, state, focused]))
            if selected:
                mappings.append(("selected", images[True, "normal", False]))
        style.element_create(element, "image", images[False, "normal", False], *mappings, sticky="w")
    style.layout(name, [("Checkbutton.padding", {"sticky": "nswe", "children": [
        (element, {"side": "left", "sticky": "w"}),
        ("Checkbutton.label", {"side": "left", "sticky": "w"})]})])
    style.configure(name, font=(font, 10), foreground=palette["text"],
                    background=palette["background"], padding=(0, 2, 0, 2))
    style.map(name, foreground=[("disabled", "#9aa5b5")],
              background=[("disabled", palette["background"]), ("!disabled", palette["background"])])
    return name
