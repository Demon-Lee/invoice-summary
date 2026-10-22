"""Use display-sized Windows icons instead of Tk 8.6's fixed 16/32 images."""
import ctypes
import os
import tkinter as tk
from ctypes import wintypes


def set_window_icon(root, path):
    """Keep Tk's dialog/fallback icon and retain our native handles on the root."""
    root.iconbitmap(default=str(path))
    root.iconbitmap(str(path))
    if os.name == "nt":
        try:
            root._window_icon = _WindowIcon(root, path)
        except (AttributeError, OSError):
            pass


class _WindowIcon:
    def __init__(self, root, path):
        self.root = root
        self.path = str(path)
        self.handles = []
        self.current = None
        self.pending = None
        self.closed = False
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.GetSystemMetrics.argtypes = [ctypes.c_int]
        self.user32.GetSystemMetrics.restype = ctypes.c_int
        self.user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR,
                                          wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        self.user32.LoadImageW.restype = wintypes.HANDLE
        self.user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                            wintypes.WPARAM, wintypes.LPARAM]
        self.user32.SendMessageW.restype = ctypes.c_ssize_t
        self.user32.DestroyIcon.argtypes = [wintypes.HICON]
        self.user32.DestroyIcon.restype = wintypes.BOOL
        self.dpi_for_window = getattr(self.user32, "GetDpiForWindow", None)
        self.metrics_for_dpi = getattr(self.user32, "GetSystemMetricsForDpi", None)
        if self.dpi_for_window and self.metrics_for_dpi:
            self.dpi_for_window.argtypes = [wintypes.HWND]
            self.dpi_for_window.restype = wintypes.UINT
            self.metrics_for_dpi.argtypes = [ctypes.c_int, wintypes.UINT]
            self.metrics_for_dpi.restype = ctypes.c_int
        root.bind("<Map>", self._schedule, add="+")
        root.bind("<Destroy>", self._destroy, add="+")
        self._schedule()

    def _schedule(self, event=None):
        if event is not None and event.widget is not self.root:
            return
        if not self.closed and self.pending is None:
            self.pending = self.root.after_idle(self._apply)

    def _sizes(self, hwnd):
        dpi = self.dpi_for_window(hwnd) if self.dpi_for_window and self.metrics_for_dpi else 0
        metric = (lambda index: self.metrics_for_dpi(index, dpi)) if dpi else self.user32.GetSystemMetrics
        # SM_CXSMICON/SM_CYSMICON and SM_CXICON/SM_CYICON.
        return ((metric(49), metric(50)), (metric(11), metric(12)))

    def _apply(self):
        self.pending = None
        if self.closed:
            return
        loaded = []
        try:
            # winfo_id() is Tk's client window, not its decorative Windows frame.
            hwnd = int(str(self.root.wm_frame()), 0)
            sizes = self._sizes(hwnd)
            key = (hwnd, sizes)
            if not hwnd or key == self.current or any(min(size) <= 0 for size in sizes):
                return
            for width, height in sizes:
                handle = self.user32.LoadImageW(None, self.path, 1, width, height, 0x10)
                if not handle:
                    raise ctypes.WinError(ctypes.get_last_error())
                loaded.append(handle)
            for kind, handle in enumerate(loaded):
                self.user32.SendMessageW(hwnd, 0x80, kind, handle)  # WM_SETICON
            previous = self.handles
            previous_hwnd = self.current[0] if self.current else None
            self.handles = loaded
            loaded = []
            self.current = key
            # Do not destroy the handles returned by WM_SETICON: Tk owns those.
            self._release(previous, previous_hwnd)
        except (OSError, ValueError, tk.TclError):
            # Cosmetic failures retain the existing Tk icon and never block startup.
            pass
        finally:
            for handle in loaded:
                self.user32.DestroyIcon(handle)

    def _release(self, handles, hwnd):
        for kind, handle in enumerate(handles):
            # Tk's Destroy event can precede destruction of the outer HWND.
            if hwnd and self.user32.SendMessageW(hwnd, 0x7F, kind, 0) == handle:  # WM_GETICON
                self.user32.SendMessageW(hwnd, 0x80, kind, 0)
            self.user32.DestroyIcon(handle)

    def _destroy(self, event):
        if event.widget is not self.root:
            return
        self.closed = True
        if self.pending is not None:
            try:
                self.root.after_cancel(self.pending)
            except tk.TclError:
                pass
            self.pending = None
        self._release(self.handles, self.current[0] if self.current else None)
        self.handles = []
