"""Native presentation widgets with quiet scrolling and a thin activity line."""
import math
import time
import tkinter as tk


class ProportionalTreeviewColumns:
    """Size native columns by weights while preserving manual divider changes."""

    def __init__(self, tree, columns, weights, minimums):
        self.tree = tree
        self.columns = tuple(columns)
        self.weights = list(weights)
        self.minimums = tuple(minimums)
        if (not self.columns or len(self.columns) != len(self.weights)
                or len(self.columns) != len(self.minimums)
                or any(weight <= 0 for weight in self.weights)
                or any(minimum <= 0 for minimum in self.minimums)):
            raise ValueError("Column names, positive weights and minimums must match")
        self._after = None
        self._last_width = None
        self._dragging = False
        self._drag_start = ()
        self._dead = False
        for sequence, callback in (
            ("<Configure>", self._schedule), ("<Map>", self._schedule),
            ("<ButtonPress-1>", self._press), ("<Double-1>", self._press),
            ("<ButtonRelease-1>", self._release), ("<Destroy>", self._destroyed),
        ):
            tree.bind(sequence, callback, add="+")
        self._schedule()

    def _widths(self, available):
        remaining = max(available, sum(self.minimums))
        active = list(range(len(self.columns)))
        widths = [0] * len(self.columns)
        while active:
            weight_sum = sum(self.weights[index] for index in active)
            constrained = [index for index in active
                           if remaining * self.weights[index] / weight_sum < self.minimums[index]]
            if constrained:
                for index in constrained:
                    widths[index] = self.minimums[index]
                    remaining -= widths[index]
                    active.remove(index)
                continue
            ideals = {index: remaining * self.weights[index] / weight_sum for index in active}
            for index in active:
                widths[index] = int(ideals[index])
            extra = remaining - sum(widths[index] for index in active)
            order = sorted(active, key=lambda index: (-(ideals[index]-widths[index]), index))
            for index in order[:extra]:
                widths[index] += 1
            break
        return widths

    def _cancel(self):
        if self._after is not None:
            try:
                self.tree.after_cancel(self._after)
            except tk.TclError:
                pass
            self._after = None

    def _schedule(self, event=None):
        if not self._dead and not self._dragging and self._after is None:
            self._after = self.tree.after_idle(self._apply)

    def _apply(self):
        self._after = None
        if self._dead or self._dragging or not self.tree.winfo_ismapped():
            return
        available = max(0, self.tree.winfo_width()-2)
        if available <= 1 or available == self._last_width:
            return
        self._last_width = available
        for column, width in zip(self.columns, self._widths(available)):
            if int(self.tree.column(column, "width")) != width:
                self.tree.column(column, width=width)

    def _press(self, event):
        if not self._dead and self.tree.identify_region(event.x, event.y) == "separator":
            self._dragging = True
            self._drag_start = tuple(int(self.tree.column(column, "width")) for column in self.columns)
            self._cancel()

    def _release(self, event):
        if self._dead or not self._dragging:
            return
        self._cancel()
        # Widget bindings run before Treeview's native release/drop binding.
        self._after = self.tree.after_idle(self._finish_drag)

    def _finish_drag(self):
        self._after = None
        if self._dead:
            return
        widths = tuple(int(self.tree.column(column, "width")) for column in self.columns)
        if widths != self._drag_start:
            self.weights = list(widths)
        self._drag_start = ()
        self._dragging = False
        self._schedule()

    def _destroyed(self, event):
        if event.widget is self.tree:
            self._dead = True
            self._cancel()


class AutoHideScrollbar(tk.Canvas):
    """A rounded scrollbar in a fixed gutter; visibility never resizes the view."""

    def __init__(self, parent, *, command, orient="vertical", background="white",
                 hide_delay=1400, end_gap=0):
        self.vertical = orient == "vertical"
        self.command = command
        self.hide_delay = hide_delay
        self.end_gap = end_gap
        self.first, self.last = 0.0, 1.0
        self._available = False
        self._visible = False
        self._hovered = False
        self._dragging = False
        self._dead = False
        self._hide_after = None
        self._bindings = []
        self._draw_signature = None
        self._view = None
        self._drag_anchor = self._drag_first = 0.0
        super().__init__(parent, width=14, height=14, bg=background, bd=0,
                         highlightthickness=0, takefocus=False)
        self.bind("<Configure>", lambda event: self._draw())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<MouseWheel>", self._wheel)
        self.bind("<Destroy>", self._destroyed)

    def attach(self, view, host):
        self._view = view
        for widget in (view, host):
            for sequence in ("<Enter>", "<Motion>"):
                self._bindings.append((widget, sequence, widget.bind(sequence, self._activity, add="+")))
        for sequence in ("<MouseWheel>", "<KeyPress>"):
            self._bindings.append((view, sequence, view.bind(sequence, self._activity, add="+")))

    def set(self, first, last):
        first = max(0.0, min(1.0, float(first)))
        last = max(first, min(1.0, float(last)))
        changed = (first, last) != (self.first, self.last)
        self.first, self.last = first, last
        self._available = 0.0 < last - first < 1.0 - 1e-6
        if not self._available:
            self._hide(force=True)
        elif changed:
            self._activity()
        self._draw()

    def _cancel_hide(self):
        if self._hide_after is not None:
            try:
                self.after_cancel(self._hide_after)
            except tk.TclError:
                pass
            self._hide_after = None

    def _schedule_hide(self):
        self._cancel_hide()
        if not self._dead and self._visible and not self._dragging and not self._hovered:
            self._hide_after = self.after(self.hide_delay, self._idle_hide)

    def _idle_hide(self):
        self._hide_after = None
        self._hide()

    def _activity(self, event=None):
        if self._dead or not self._available or self._view is None or not self._view.winfo_ismapped():
            return
        if not self._visible:
            if self.vertical:
                self.place(relx=1.0, x=-15, y=1, relheight=1.0, height=-2-self.end_gap, width=14)
            else:
                self.place(x=1, rely=1.0, y=-15, relwidth=1.0, width=-2-self.end_gap, height=14)
            tk.Misc.tkraise(self)
            self._visible = True
        self._draw()
        self._schedule_hide()

    def _hide(self, *, force=False):
        if self._dead:
            return
        if not force and (self._hovered or self._dragging):
            return
        self._cancel_hide()
        if force:
            self._hovered = self._dragging = False
        if self._visible:
            self.place_forget()
            self._visible = False

    def _geometry(self):
        length = self.winfo_height() if self.vertical else self.winfo_width()
        track = max(0.0, length - 4.0)
        span = self.last - self.first
        thumb = min(track, max(28.0, track * span))
        travel = max(0.0, track - thumb)
        start = 2.0 + travel * self.first / max(1e-6, 1.0-span)
        return start, start+thumb, travel, span

    def _draw(self):
        if self._dead or not self._visible:
            return
        signature = (self.winfo_width(), self.winfo_height(), self.first, self.last, self._hovered, self._dragging)
        if signature == self._draw_signature:
            return
        self._draw_signature = signature
        self.delete("all")
        start, end, _, _ = self._geometry()
        if end - start < 6:
            return
        color = "#2563eb" if self._dragging else "#7893bb" if self._hovered else "#b9c6d8"
        if self.vertical:
            self.create_line(7, 3, 7, max(3, self.winfo_height()-3), fill="#eef1f6", width=2, capstyle=tk.ROUND)
            self.create_line(7, start+3, 7, end-3, fill=color, width=6, capstyle=tk.ROUND)
        else:
            self.create_line(3, 7, max(3, self.winfo_width()-3), 7, fill="#eef1f6", width=2, capstyle=tk.ROUND)
            self.create_line(start+3, 7, end-3, 7, fill=color, width=6, capstyle=tk.ROUND)

    def _enter(self, event):
        self._hovered = True
        self._activity()

    def _leave(self, event):
        self._hovered = False
        self._draw()
        self._schedule_hide()

    def _press(self, event):
        if not self._available:
            return
        coordinate = event.y if self.vertical else event.x
        start, end, travel, span = self._geometry()
        if travel <= 0:
            return
        self._dragging = True
        self._drag_anchor = coordinate
        self._drag_first = self.first
        if not start <= coordinate <= end:
            target = (coordinate - 2 - (end-start)/2) / travel * (1-span)
            self._drag_first = max(0.0, min(1-span, target))
            self.command("moveto", self._drag_first)
        self._activity()

    def _drag(self, event):
        if not self._dragging:
            return
        _, _, travel, span = self._geometry()
        if travel <= 0:
            return
        coordinate = event.y if self.vertical else event.x
        target = self._drag_first + (coordinate-self._drag_anchor)/travel * (1-span)
        self.command("moveto", max(0.0, min(1-span, target)))
        self._activity()

    def _release(self, event):
        if not self._dragging:
            return
        self._dragging = False
        self._hovered = 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height()
        self._draw()
        self._schedule_hide()

    def _wheel(self, event):
        delta = event.delta
        if delta:
            units = -int(delta/120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)
            self.command("scroll", units, "units")
            self._activity()
        return "break"

    def _destroyed(self, event):
        if event.widget is not self:
            return
        self._dead = True
        self._cancel_hide()
        for widget, sequence, callback in self._bindings:
            try:
                if callback and widget.winfo_exists():
                    widget.unbind(sequence, callback)
            except tk.TclError:
                pass
        self._bindings.clear()


class AutoScrollText(tk.Text):
    """Text API with the same outer geometry delegation as stdlib ScrolledText."""

    def __init__(self, parent, **kwargs):
        background = kwargs.get("bg", "white")
        self.frame = tk.Frame(parent, bg=background, bd=0, highlightthickness=0)
        self.frame.rowconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, minsize=14)
        super().__init__(self.frame, **kwargs)
        tk.Text.grid(self, row=0, column=0, sticky="nsew")
        self.vbar = AutoHideScrollbar(self.frame, command=self.yview, background=background)
        self.vbar.attach(self, self.frame)
        self.configure(yscrollcommand=self.vbar.set)
        geometry_methods = (vars(tk.Pack).keys() | vars(tk.Grid).keys() | vars(tk.Place).keys()) - vars(tk.Text).keys()
        for name in geometry_methods:
            if not name.startswith("_") and name not in ("config", "configure"):
                setattr(self, name, getattr(self.frame, name))

    def __str__(self):
        return str(self.frame)


class ThinProgressbar(tk.Canvas):
    """A rounded, three-pixel activity line with a time-based blue sweep."""

    def __init__(self, parent, *, background="#f3f5f9", accent="#2563eb"):
        super().__init__(parent, height=6, bg=background, bd=0, highlightthickness=0, takefocus=False)
        self._running = False
        self._dead = False
        self._animation_after = None
        self._interval = 32
        self._started = 0.0
        self._track = "#e5ebf4"
        base = tuple(int(self._track[i:i+2], 16) for i in (1, 3, 5))
        blue = tuple(int(accent[i:i+2], 16) for i in (1, 3, 5))
        self._gradient = []
        for index in range(24):
            weight = math.sin(math.pi * (index+0.5)/24)
            color = tuple(round(a+(b-a)*weight) for a, b in zip(base, blue))
            self._gradient.append("#%02x%02x%02x" % color)
        self.bind("<Configure>", lambda event: self._draw())
        self.bind("<Destroy>", self._destroyed)

    def start(self, interval=32):
        if self._dead or self._running:
            return
        self._running = True
        self._interval = max(32, int(interval))
        self._started = time.monotonic()
        self._tick()

    def stop(self):
        self._running = False
        if self._animation_after is not None:
            try:
                self.after_cancel(self._animation_after)
            except tk.TclError:
                pass
            self._animation_after = None
        self._draw()

    def _tick(self):
        self._animation_after = None
        if self._dead or not self._running:
            return
        self._draw()
        self._animation_after = self.after(self._interval, self._tick)

    def _draw(self):
        if self._dead:
            return
        self.delete("all")
        width = self.winfo_width()
        if width <= 6:
            return
        self.create_line(3, 3, width-3, 3, fill=self._track, width=3, capstyle=tk.ROUND)
        if not self._running:
            return
        length = max(28.0, min(230.0, width * 0.28))
        phase = (time.monotonic()-self._started) % 1.7 / 1.7
        eased = (1.0-math.cos(math.pi*phase))/2.0
        start = -length + eased*(width+length)
        for index, color in enumerate(self._gradient):
            left = max(3.0, start + length*index/24)
            right = min(width-3.0, start + length*(index+1)/24)
            if right > left:
                self.create_line(left, 3, right, 3, fill=color, width=3, capstyle=tk.ROUND)

    def _destroyed(self, event):
        if event.widget is self:
            self._dead = True
            self.stop()
