"""Thin ctypes wrappers over the Win32 APIs that computer use needs.

Everything here works in physical pixels: the process is made per-monitor
DPI aware before any other call, so window rects, cursor positions and
screenshot pixels share one coordinate space.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import threading
import time
from dataclasses import dataclass

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi")

ULONG_PTR = ctypes.c_size_t
LRESULT = ctypes.c_ssize_t

# --------------------------------------------------------------------------
# DPI
# --------------------------------------------------------------------------


def set_dpi_aware() -> None:
    try:
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):  # PER_MONITOR_AWARE_V2
            return
    except AttributeError:
        pass
    try:
        ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
    except OSError:
        user32.SetProcessDPIAware()


# --------------------------------------------------------------------------
# Function prototypes (64-bit safe handles)
# --------------------------------------------------------------------------

EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

user32.EnumWindows.argtypes = [EnumWindowsProc, wt.LPARAM]
user32.EnumChildWindows.argtypes = [wt.HWND, EnumWindowsProc, wt.LPARAM]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.IsIconic.argtypes = [wt.HWND]
user32.IsWindow.argtypes = [wt.HWND]
user32.GetWindow.argtypes = [wt.HWND, wt.UINT]
user32.GetWindow.restype = wt.HWND
user32.GetAncestor.argtypes = [wt.HWND, wt.UINT]
user32.GetAncestor.restype = wt.HWND
user32.GetWindowTextLengthW.argtypes = [wt.HWND]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.ShowWindowAsync.argtypes = [wt.HWND, ctypes.c_int]
user32.GetForegroundWindow.restype = wt.HWND
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.BringWindowToTop.argtypes = [wt.HWND]
user32.WindowFromPoint.argtypes = [wt.POINT]
user32.WindowFromPoint.restype = wt.HWND
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
user32.MessageBoxW.argtypes = [wt.HWND, wt.LPCWSTR, wt.LPCWSTR, wt.UINT]
user32.OpenClipboard.argtypes = [wt.HWND]
user32.GetClipboardData.argtypes = [wt.UINT]
user32.GetClipboardData.restype = wt.HANDLE
user32.SetClipboardData.argtypes = [wt.UINT, wt.HANDLE]
user32.SetClipboardData.restype = wt.HANDLE
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
kernel32.GlobalAlloc.argtypes = [wt.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wt.HGLOBAL
kernel32.GlobalLock.argtypes = [wt.HGLOBAL]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wt.HGLOBAL]
kernel32.GlobalFree.argtypes = [wt.HGLOBAL]
kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
kernel32.GetModuleHandleW.restype = wt.HMODULE
kernel32.GetCurrentThreadId.restype = wt.DWORD
user32.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
dwmapi.DwmGetWindowAttribute.argtypes = [wt.HWND, wt.DWORD, ctypes.c_void_p, wt.DWORD]

GW_OWNER = 4
GA_ROOT = 2
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
DWMWA_CLOAKED = 14
SW_MINIMIZE = 6
SW_SHOWNOACTIVATE = 4
SW_RESTORE = 9

SHELL_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}

# --------------------------------------------------------------------------
# Windows
# --------------------------------------------------------------------------


@dataclass
class Win:
    hwnd: int
    pid: int
    title: str
    cls: str
    rect: tuple[int, int, int, int]  # left, top, right, bottom (physical px)
    minimized: bool


def window_text(hwnd: int) -> str:
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def class_name(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def window_pid(hwnd: int) -> int:
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def window_thread(hwnd: int) -> int:
    return user32.GetWindowThreadProcessId(hwnd, None)


def real_pid(hwnd: int) -> int:
    """PID of the app that owns a window, looking through the UWP frame host."""
    pid = window_pid(hwnd)
    if class_name(hwnd) != "ApplicationFrameWindow":
        return pid
    found: list[int] = []

    def cb(child, _):
        cpid = window_pid(child)
        if cpid != pid:
            found.append(cpid)
            return False
        return True

    user32.EnumChildWindows(hwnd, EnumWindowsProc(cb), 0)
    return found[0] if found else pid


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)


def is_cloaked(hwnd: int) -> bool:
    v = wt.DWORD()
    if dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(v), ctypes.sizeof(v)) != 0:
        return False
    return v.value != 0


def is_app_window(hwnd: int) -> bool:
    """A top-level window that shows up as an app (taskbar-like heuristics)."""
    if not user32.IsWindowVisible(hwnd):
        return False
    if user32.GetWindow(hwnd, GW_OWNER):
        return False
    ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    if ex & WS_EX_TOOLWINDOW:
        return False
    if is_cloaked(hwnd):
        return False
    if class_name(hwnd) in SHELL_CLASSES:
        return False
    return user32.GetWindowTextLengthW(hwnd) > 0


def top_level_windows(app_only: bool = True) -> list[Win]:
    """Top-level windows in z-order, topmost first."""
    hwnds: list[int] = []

    def cb(h, _):
        hwnds.append(h)
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    out = []
    for h in hwnds:
        if app_only and not is_app_window(h):
            continue
        if not app_only and not user32.IsWindowVisible(h):
            continue
        out.append(Win(h, real_pid(h), window_text(h), class_name(h), window_rect(h), bool(user32.IsIconic(h))))
    return out


def root_window_at(x: int, y: int) -> int | None:
    h = user32.WindowFromPoint(wt.POINT(x, y))
    if not h:
        return None
    return user32.GetAncestor(h, GA_ROOT) or h


def foreground_window() -> int | None:
    h = user32.GetForegroundWindow()
    if not h:
        return None
    return user32.GetAncestor(h, GA_ROOT) or h


def minimize(hwnd: int) -> None:
    user32.ShowWindowAsync(hwnd, SW_MINIMIZE)


def unminimize(hwnd: int) -> None:
    if user32.IsWindow(hwnd) and user32.IsIconic(hwnd):
        user32.ShowWindowAsync(hwnd, SW_SHOWNOACTIVATE)


def is_window(hwnd: int) -> bool:
    return bool(user32.IsWindow(hwnd))


def focus(hwnd: int) -> bool:
    """Bring a window to the foreground despite the foreground lock."""
    was_minimized = bool(user32.IsIconic(hwnd))
    if was_minimized:
        user32.ShowWindow(hwnd, SW_RESTORE)
        time.sleep(0.5)  # restore animation; early input gets dropped (seen with Win11 Notepad)
    fg = user32.GetForegroundWindow()
    cur = kernel32.GetCurrentThreadId()
    fg_thread = window_thread(fg) if fg else 0
    attached = False
    if fg_thread and fg_thread != cur:
        attached = bool(user32.AttachThreadInput(cur, fg_thread, True))
    try:
        # A synthetic Alt tap lets this process take the foreground.
        _send([_key(0x12, False), _key(0x12, True)])
        user32.BringWindowToTop(hwnd)
        ok = bool(user32.SetForegroundWindow(hwnd))
    finally:
        if attached:
            user32.AttachThreadInput(cur, fg_thread, False)
    # Wait until the window really owns the foreground before anyone types into it.
    for _ in range(20):
        if foreground_window() == hwnd:
            break
        time.sleep(0.05)
    time.sleep(0.25)
    return ok


# --------------------------------------------------------------------------
# Input
# --------------------------------------------------------------------------


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wt.DWORD), ("wParamL", wt.WORD), ("wParamH", wt.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _INPUTUNION)]


user32.SendInput.argtypes = [wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int]

INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x1, 0x2, 0x4
MOUSE_FLAGS = {
    "left": (0x0002, 0x0004),
    "right": (0x0008, 0x0010),
    "middle": (0x0020, 0x0040),
}
MOUSEEVENTF_WHEEL, MOUSEEVENTF_HWHEEL = 0x0800, 0x1000

EXTENDED_VKS = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E,
                0x5B, 0x5C, 0x5D, 0x6F, 0x90, 0xA3, 0xA5}


def _send(inputs: list[INPUT]) -> None:
    arr = (INPUT * len(inputs))(*inputs)
    sent = user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))
    if sent != len(inputs):
        raise OSError(f"SendInput blocked ({sent}/{len(inputs)} events). "
                      "The target may be an elevated (admin) window, which a non-admin process cannot control.")


def _key(vk: int, up: bool) -> INPUT:
    flags = KEYEVENTF_KEYUP if up else 0
    if vk in EXTENDED_VKS:
        flags |= KEYEVENTF_EXTENDEDKEY
    return INPUT(INPUT_KEYBOARD, _INPUTUNION(ki=KEYBDINPUT(vk, 0, flags, 0, 0)))


def _unicode(unit: int, up: bool) -> INPUT:
    flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0)
    return INPUT(INPUT_KEYBOARD, _INPUTUNION(ki=KEYBDINPUT(0, unit, flags, 0, 0)))


def _mouse(flags: int, data: int = 0) -> INPUT:
    return INPUT(INPUT_MOUSE, _INPUTUNION(mi=MOUSEINPUT(0, 0, data & 0xFFFFFFFF, flags, 0, 0)))


def move_cursor(x: int, y: int) -> None:
    user32.SetCursorPos(int(x), int(y))


def cursor_pos() -> tuple[int, int]:
    p = wt.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return (p.x, p.y)


def mouse_down(button: str) -> None:
    _send([_mouse(MOUSE_FLAGS[button][0])])


def mouse_up(button: str) -> None:
    _send([_mouse(MOUSE_FLAGS[button][1])])


def click(button: str, count: int = 1) -> None:
    down, up = MOUSE_FLAGS[button]
    for i in range(count):
        _send([_mouse(down), _mouse(up)])
        if i + 1 < count:
            time.sleep(0.04)


def wheel(dy_clicks: int, dx_clicks: int = 0) -> None:
    ev = []
    if dy_clicks:
        ev.append(_mouse(MOUSEEVENTF_WHEEL, -120 * dy_clicks))  # positive = scroll down
    if dx_clicks:
        ev.append(_mouse(MOUSEEVENTF_HWHEEL, 120 * dx_clicks))
    if ev:
        _send(ev)


def type_unicode(text: str) -> None:
    for ch in text.replace("\r\n", "\n"):
        if ch == "\n":
            _send([_key(0x0D, False), _key(0x0D, True)])
        elif ch == "\t":
            _send([_key(0x09, False), _key(0x09, True)])
        else:
            data = ch.encode("utf-16-le")
            units = [int.from_bytes(data[i:i + 2], "little") for i in range(0, len(data), 2)]
            _send([_unicode(u, False) for u in units] + [_unicode(u, True) for u in units])
        time.sleep(0.004)


def key_down(vk: int) -> None:
    _send([_key(vk, False)])


def key_up(vk: int) -> None:
    _send([_key(vk, True)])


def press_combo(vks: list[int]) -> None:
    _send([_key(v, False) for v in vks] + [_key(v, True) for v in reversed(vks)])


# --------------------------------------------------------------------------
# Global Esc hook (low-level keyboard hook, consumes physical Esc)
# --------------------------------------------------------------------------


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wt.DWORD), ("scanCode", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wt.WPARAM, wt.LPARAM)
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wt.HINSTANCE, wt.DWORD]
user32.SetWindowsHookExW.restype = wt.HHOOK
user32.CallNextHookEx.argtypes = [wt.HHOOK, ctypes.c_int, wt.WPARAM, wt.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]

WH_KEYBOARD_LL = 13
LLKHF_INJECTED = 0x10
WM_KEYDOWN, WM_SYSKEYDOWN = 0x0100, 0x0104


def start_escape_hook(is_active, on_escape) -> threading.Thread:
    """While is_active() is true, a physical Esc press calls on_escape and is swallowed."""

    def run():
        def proc(n_code, w_param, l_param):
            if n_code == 0:
                kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if kb.vkCode == 0x1B and not (kb.flags & LLKHF_INJECTED) and is_active():
                    if w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                        threading.Thread(target=on_escape, daemon=True).start()
                    return 1
            return user32.CallNextHookEx(None, n_code, w_param, l_param)

        cb = HOOKPROC(proc)
        hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, cb, kernel32.GetModuleHandleW(None), 0)
        if not hook:
            return
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            pass

    t = threading.Thread(target=run, name="esc-hook", daemon=True)
    t.start()
    return t


# --------------------------------------------------------------------------
# Clipboard
# --------------------------------------------------------------------------

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002


def _open_clipboard() -> None:
    for _ in range(20):
        if user32.OpenClipboard(None):
            return
        time.sleep(0.05)
    raise OSError("Clipboard is busy")


def clipboard_get() -> str:
    _open_clipboard()
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        p = kernel32.GlobalLock(h)
        try:
            return ctypes.wstring_at(p)
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def clipboard_set(text: str) -> None:
    data = ctypes.create_unicode_buffer(text)
    size = ctypes.sizeof(data)
    _open_clipboard()
    try:
        user32.EmptyClipboard()
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
        p = kernel32.GlobalLock(h)
        ctypes.memmove(p, data, size)
        kernel32.GlobalUnlock(h)
        if not user32.SetClipboardData(CF_UNICODETEXT, h):
            kernel32.GlobalFree(h)
            raise OSError("SetClipboardData failed")
    finally:
        user32.CloseClipboard()


# --------------------------------------------------------------------------
# Dialog
# --------------------------------------------------------------------------

MB_YESNO = 0x4
MB_ICONWARNING = 0x30
MB_DEFBUTTON2 = 0x100
MB_SYSTEMMODAL = 0x1000
MB_SETFOREGROUND = 0x10000
MB_TOPMOST = 0x40000
IDYES = 6


def ask_yes_no(title: str, text: str) -> bool:
    flags = MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2 | MB_SYSTEMMODAL | MB_SETFOREGROUND | MB_TOPMOST
    return user32.MessageBoxW(None, text, title, flags) == IDYES
