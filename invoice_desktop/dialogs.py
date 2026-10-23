"""Place app-owned dialogs over the main window, including native choosers."""

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from functools import wraps
import os
import tkinter as tk
from tkinter import filedialog as _files, messagebox as _messages, simpledialog as _inputs
from types import SimpleNamespace


_RETAINED_HOOKS = []


class _MonitorInfo(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("monitor", wintypes.RECT),
                ("work", wintypes.RECT), ("flags", wintypes.DWORD)]


class _WindowsPlacement:
    def __init__(self, root):
        self.api = ctypes.WinDLL("user32", use_last_error=True)
        declarations = {
            "GetAncestor": ([wintypes.HWND, wintypes.UINT], wintypes.HWND),
            "GetWindowRect": ([wintypes.HWND, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
            "IsWindowVisible": ([wintypes.HWND], wintypes.BOOL),
            "MonitorFromWindow": ([wintypes.HWND, wintypes.DWORD], wintypes.HANDLE),
            "GetMonitorInfoW": ([wintypes.HANDLE, ctypes.POINTER(_MonitorInfo)], wintypes.BOOL),
            "GetClassNameW": ([wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
            "SetWindowPos": ([wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                              ctypes.c_int, ctypes.c_int, wintypes.UINT], wintypes.BOOL),
            "CallNextHookEx": ([wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM], ctypes.c_ssize_t),
            "UnhookWindowsHookEx": ([wintypes.HANDLE], wintypes.BOOL),
        }
        for name, (arguments, result) in declarations.items():
            method = getattr(self.api, name)
            method.argtypes, method.restype = arguments, result
        self.main = self.api.GetAncestor(root.winfo_id(), 2)  # GA_ROOT: include window decorations.
        self.hook = None
        self.callback = None
        self.active = False
        self.centered = set()

    def center(self, hwnd):
        if not hwnd or hwnd == self.main:
            return False
        monitor = self.api.MonitorFromWindow(self.main, 2)
        info = _MonitorInfo()
        info.size = ctypes.sizeof(info)
        rect, reference = wintypes.RECT(), wintypes.RECT()
        if (not self.api.GetMonitorInfoW(monitor, ctypes.byref(info))
                or not self.api.GetWindowRect(hwnd, ctypes.byref(rect))):
            return False
        work = info.work
        if not self.api.IsWindowVisible(self.main) or not self.api.GetWindowRect(self.main, ctypes.byref(reference)):
            reference = work
        width, height = rect.right - rect.left, rect.bottom - rect.top
        if width <= 1 or height <= 1:
            return False
        x = reference.left + (reference.right - reference.left - width) // 2
        y = reference.top + (reference.bottom - reference.top - height) // 2
        x = min(max(x, work.left), max(work.left, work.right - width))
        y = min(max(y, work.top), max(work.top, work.bottom - height))
        # Move only: keep size, stacking, activation and the current DPI mode.
        return bool(self.api.SetWindowPos(hwnd, None, x, y, 0, 0, 0x0001 | 0x0004 | 0x0010))

    def install(self):
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        def callback(code, hwnd, parameter):
            try:
                if code == 4:  # HCBT_DESTROYWND; HWNDs may be reused.
                    self.centered.discard(hwnd)
                elif self.active and code == 5 and hwnd not in self.centered:  # HCBT_ACTIVATE
                    name = ctypes.create_unicode_buffer(64)
                    self.api.GetClassNameW(hwnd, name, len(name))
                    if name.value in ("#32770", "TkTopLevel") and self.center(hwnd):
                        self.centered.add(hwnd)
            except Exception:
                pass  # Never allow a Python exception to escape a Windows callback.
            return self.api.CallNextHookEx(self.hook, code, hwnd, parameter)
        self.callback = callback_type(callback)
        self.api.SetWindowsHookExW.argtypes = [ctypes.c_int, callback_type, wintypes.HINSTANCE, wintypes.DWORD]
        self.api.SetWindowsHookExW.restype = wintypes.HANDLE
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentThreadId.argtypes = []
        kernel.GetCurrentThreadId.restype = wintypes.DWORD
        self.active = True
        self.hook = self.api.SetWindowsHookExW(5, self.callback, None, kernel.GetCurrentThreadId())  # WH_CBT

    def close(self):
        self.active = False
        if self.hook:
            try:
                removed = self.api.UnhookWindowsHookEx(self.hook)
            except Exception:
                removed = False
            if not removed:
                _RETAINED_HOOKS.append(self)  # Keep a still-installed callback alive but inactive.
            else:
                self.hook = None


@contextmanager
def _native_placement(parent):
    placement = None
    try:
        if os.name == "nt" and parent is not None:
            placement = _WindowsPlacement(parent._root())
            placement.install()
    except Exception:
        pass
    try:
        yield
    finally:
        if placement is not None:
            placement.close()


def _centered(method):
    @wraps(method)
    def invoke(*args, **kwargs):
        parent = kwargs.get("parent") or tk._default_root
        if parent is not None:
            kwargs["parent"] = parent
        with _native_placement(parent):
            return method(*args, **kwargs)
    return invoke


messagebox = SimpleNamespace(**{name: _centered(getattr(_messages, name)) for name in
                               ("showinfo", "showwarning", "showerror", "askyesno")})
filedialog = SimpleNamespace(**{name: _centered(getattr(_files, name)) for name in
                               ("askdirectory", "askopenfilename")})
simpledialog = SimpleNamespace(askstring=_centered(_inputs.askstring))


def center_dialog(dialog, parent):
    """Place once before showing, then refine the outer-frame center on first Map."""
    root = parent._root()
    dialog.update_idletasks()
    width, height = dialog.winfo_width(), dialog.winfo_height()
    if width <= 1:
        width = dialog.winfo_reqwidth()
    if height <= 1:
        height = dialog.winfo_reqheight()
    if root.winfo_ismapped():
        x = root.winfo_rootx() + (root.winfo_width() - width) // 2
        y = root.winfo_rooty() + (root.winfo_height() - height) // 2
    else:
        x = (root.winfo_screenwidth() - width) // 2
        y = (root.winfo_screenheight() - height) // 2
    dialog.geometry("+%d+%d" % (x, y))  # Tk accepts absolute negative coordinates as '+-N'.
    if os.name == "nt":
        def mapped(event):
            if event.widget is not dialog:
                return
            dialog.unbind("<Map>", binding)
            try:
                placement = _WindowsPlacement(root)
                placement.center(placement.api.GetAncestor(dialog.winfo_id(), 2))
            except Exception:
                pass
        binding = dialog.bind("<Map>", mapped, add="+")
