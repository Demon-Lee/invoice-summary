"""Local presentation for native signature dropdowns; selection stays in Tk."""

import tkinter as tk
from tkinter import ttk


def style_combobox_popup(combo, *, font, palette):
    """Style only this combobox's popup and retain its native input bindings."""
    combo._popup_appearance = _ComboboxPopupAppearance(combo, font, palette)


class _ComboboxPopupAppearance:
    VISIBLE = "SignaturePopup.Visible.Vertical.TScrollbar"
    HIDDEN = "SignaturePopup.Hidden.Vertical.TScrollbar"
    FRAME = "SignaturePopup.TFrame"

    def __init__(self, combo, font, palette):
        self.combo = combo
        self.font = font
        self.palette = palette
        self.scrollbar = None
        self.popup = None
        self.timer = None
        self.hovered = False
        self.dragging = False
        self.closed = False
        self._configure_styles()
        combo.configure(postcommand=self._post)
        combo.bind("<Destroy>", self._destroy, add="+")

    def _configure_styles(self):
        style = ttk.Style(self.combo)
        layout = [("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
            ("Vertical.Scrollbar.thumb", {"expand": True, "sticky": "nswe"})]})]
        for name, thumb, track in ((self.VISIBLE, "#b9c6d8", "#eef1f6"),
                                   (self.HIDDEN, self.palette["surface"], self.palette["surface"])):
            style.layout(name, layout)
            style.configure(name, width=8, arrowsize=8, background=thumb, troughcolor=track,
                            bordercolor=thumb, lightcolor=thumb, darkcolor=thumb,
                            relief="flat", borderwidth=0, gripcount=0)
            states = ([("pressed", self.palette["blue"]), ("active", "#7893bb")]
                      if name == self.VISIBLE else [("pressed", thumb), ("active", thumb)])
            style.map(name, **{option:states for option in
                               ("background", "bordercolor", "lightcolor", "darkcolor")})
        style.configure(self.FRAME, background=self.palette["surface"], relief="solid",
                        borderwidth=1, bordercolor=self.palette["line"],
                        lightcolor=self.palette["line"], darkcolor=self.palette["line"])

    def _bind(self, widget_path, sequence, callback):
        # Tk creates these popup widgets itself. Register callbacks on the owning
        # Python combobox so its normal destroy also removes their Tcl commands.
        command = self.combo.register(callback)
        self.combo.tk.call("bind", widget_path, sequence, "+" + command)

    def _post(self):
        if self.closed:
            return
        try:
            popup = str(self.combo.tk.call("ttk::combobox::PopdownWindow", self.combo._w))
            frame, listbox, scrollbar = popup + ".f", popup + ".f.l", popup + ".f.sb"
            self.combo.tk.call(frame, "configure", "-style", self.FRAME)
            self.combo.tk.call(listbox, "configure", "-font", self.font,
                               "-background", self.palette["surface"], "-foreground", self.palette["text"],
                               "-selectbackground", self.palette["selected"],
                               "-selectforeground", self.palette["heading"], "-selectborderwidth", 0,
                               "-relief", "flat", "-borderwidth", 0, "-highlightthickness", 0)
            if self.popup != popup:
                self.popup, self.scrollbar = popup, scrollbar
                for sequence in ("<Enter>", "<Motion>", "<MouseWheel>", "<Button-4>", "<Button-5>", "<KeyPress>"):
                    self._bind(listbox, sequence, self._show)
                self._bind(scrollbar, "<Enter>", self._enter)
                self._bind(scrollbar, "<Leave>", self._leave)
                self._bind(scrollbar, "<ButtonPress-1>", self._press)
                self._bind(scrollbar, "<ButtonRelease-1>", self._release)
                self._bind(popup, "<Map>", self._show)
                self._bind(popup, "<Unmap>", self._unmap)
            self._show()
        except tk.TclError:
            # A missing theme/native popup must never stop the normal picker.
            self._cancel()

    def _cancel(self):
        if self.timer is not None:
            try:
                self.combo.after_cancel(self.timer)
            except tk.TclError:
                pass
            self.timer = None

    def _show(self):
        self._cancel()
        if self.closed or self.scrollbar is None:
            return
        try:
            self.combo.tk.call(self.scrollbar, "configure", "-style", self.VISIBLE)
            if not (self.hovered or self.dragging):
                self.timer = self.combo.after(1400, self._hide)
        except tk.TclError:
            pass

    def _hide(self):
        self.timer = None
        if self.closed or self.hovered or self.dragging or self.scrollbar is None:
            return
        try:
            self.combo.tk.call(self.scrollbar, "configure", "-style", self.HIDDEN)
        except tk.TclError:
            pass

    def _enter(self):
        self.hovered = True
        self._show()

    def _leave(self):
        self.hovered = False
        self._show()

    def _press(self):
        self.dragging = True
        self._show()

    def _release(self):
        self.dragging = False
        self._show()

    def _unmap(self):
        self._cancel()
        self.hovered = self.dragging = False

    def _destroy(self, event):
        if event.widget is self.combo:
            self.closed = True
            self._cancel()
