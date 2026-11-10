"""caps.console_vision.console_vision — 控制台缓冲区直读。

2026-11-09 补齐：omni_read.py 的 read_text_fast / read_text / read_region_text 三处
`from caps.console_vision.console_vision import read_console` 指向的模块在仓里不存在，
表现为 read_console 一路 `No module named 'caps'` —— 整条"显示屏→大脑传输线"断在这里。

零依赖：只用 ctypes。不做猜：附加不上就如实 ok=False，并带上 err 码与候选窗口。
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

__all__ = ["read_console", "list_consoles"]

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_u32 = ctypes.WinDLL("user32", use_last_error=True)

_INVALID_HANDLE = ctypes.c_void_p(-1).value
_CONSOLE_CLASSES = ("ConsoleWindowClass", "CASCADIA_HOSTING_WINDOW_CLASS")


class _COORD(ctypes.Structure):
    _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]


class _SMALL_RECT(ctypes.Structure):
    _fields_ = [("Left", wintypes.SHORT), ("Top", wintypes.SHORT),
                ("Right", wintypes.SHORT), ("Bottom", wintypes.SHORT)]


class _SCREEN_BUFFER_INFO(ctypes.Structure):
    _fields_ = [("dwSize", _COORD), ("dwCursorPosition", _COORD),
                ("wAttributes", wintypes.WORD), ("srWindow", _SMALL_RECT),
                ("dwMaximumWindowSize", _COORD)]


_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _window_pid(hwnd):
    pid = wintypes.DWORD(0)
    _u32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    return int(pid.value)


def _window_text(hwnd):
    n = _u32.GetWindowTextLengthW(hwnd)
    if n <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(n + 1)
    _u32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value


def list_consoles():
    """枚举桌面上的控制台类窗口：[{hwnd,pid,title,class}]。"""
    out = []

    def _cb(hwnd, _lp):
        try:
            if not _u32.IsWindowVisible(hwnd):
                return True
            title = _window_text(hwnd)
            if not title:
                return True
            cls = ctypes.create_unicode_buffer(256)
            _u32.GetClassNameW(hwnd, cls, 256)
            if cls.value not in _CONSOLE_CLASSES:
                return True
            out.append({"hwnd": int(hwnd), "pid": _window_pid(hwnd),
                        "title": title, "class": cls.value})
        except Exception:
            pass
        return True

    _u32.EnumWindows(_WNDENUMPROC(_cb), 0)
    return out


def _pick_pid(pid=None, title=None, text=None):
    if pid:
        return int(pid), ""
    cands = list_consoles()
    if title:
        for c in cands:
            if c["title"] == title:
                return c["pid"], ""
    if text:
        for c in cands:
            if text in c["title"]:
                return c["pid"], ""
    if title or text:
        seen = "; ".join('%s(pid=%d)' % (c["title"][:40], c["pid"]) for c in cands[:6]) or "无控制台窗口"
        return None, "找不到标题匹配的控制台：title=%r text=%r；现有：%s" % (title, text, seen)
    return None, "需要 pid / title / text 之一（不猜当前焦点）"


def _uia_fallback(pid, hwnd):
    """ConPTY（Windows Terminal / VS Code 终端）没有可附加的控制台缓冲区。
    退到 UIA 文本：这不是完整缓冲区，只含窗口当前可见文本 —— 如实标注。"""
    try:
        import uiautomation as auto
    except Exception:
        return None
    try:
        ctrl = auto.ControlFromHandle(hwnd)
        if not ctrl:
            return None
        texts = []

        def walk(c, d=0):
            if d > 7 or len(texts) >= 500:
                return
            try:
                for ch in c.GetChildren():
                    name = (ch.Name or "").strip()
                    ct = ch.ControlTypeName
                    if name and ct in ("TextControl", "DocumentControl", "EditControl"):
                        texts.append(name)
                    walk(ch, d + 1)
            except Exception:
                pass

        walk(ctrl)
        if not texts:
            n = (ctrl.Name or "").strip()
            if n:
                texts = [n]
        if not texts:
            return None
        return {"ok": True, "pid": pid, "w": 0, "h": len(texts),
                "method": "uia-text-fallback",
                "note": "目标为 ConPTY 伪终端，AttachConsole 不可用；这是窗口可见文本，不是完整缓冲区",
                "lines": texts, "full_text": "\n".join(texts)}
    except Exception:
        return None


def read_console(pid=None, title=None, text=None):
    """直读目标控制台字符缓冲区。返回 {ok,pid,w,h,lines[],full_text,method} 或 {ok:False,error}。"""
    target, why = _pick_pid(pid, title, text)
    if not target:
        return {"ok": False, "error": why, "consoles": list_consoles()[:8]}
    if target == _k32.GetCurrentProcessId():
        return {"ok": False, "error": "目标 pid 就是本进程，拒绝自附加"}

    _k32.FreeConsole()  # 本进程可能无控制台，失败无妨
    if not _k32.AttachConsole(wintypes.DWORD(target)):
        err = ctypes.get_last_error()
        # ConPTY（Windows Terminal / VS Code）走的是伪终端，没有经典缓冲区可附加。
        hwnd = None
        for c in list_consoles():
            if c["pid"] == target:
                hwnd = c["hwnd"]
                break
        if hwnd:
            fb = _uia_fallback(target, hwnd)
            if fb:
                fb["attach_error"] = "AttachConsole err=%d（ConPTY/伪终端不支持直读）" % err
                return fb
        return {"ok": False, "pid": target,
                "error": "AttachConsole 失败 err=%d（目标不是控制台进程，或权限不足；ConPTY 终端属于此类）" % err}

    h = None
    try:
        h = _k32.CreateFileW("CONOUT$", 0x80000000 | 0x40000000, 0x3, None, 3, 0, None)
        if h is None or h == _INVALID_HANDLE:
            return {"ok": False, "pid": target,
                    "error": "打开 CONOUT$ 失败 err=%d" % ctypes.get_last_error()}
        info = _SCREEN_BUFFER_INFO()
        if not _k32.GetConsoleScreenBufferInfo(h, ctypes.byref(info)):
            return {"ok": False, "pid": target,
                    "error": "GetConsoleScreenBufferInfo 失败 err=%d" % ctypes.get_last_error()}
        w = int(info.dwSize.X)
        hgt = int(info.dwSize.Y)
        if w <= 0 or hgt <= 0 or w * hgt > 4000000:
            return {"ok": False, "pid": target, "error": "缓冲区尺寸异常 %dx%d" % (w, hgt)}
        lines = []
        for y in range(hgt):
            buf = ctypes.create_unicode_buffer(w + 1)
            read = wintypes.DWORD(0)
            ok = _k32.ReadConsoleOutputCharacterW(
                h, buf, wintypes.DWORD(w), _COORD(0, y), ctypes.byref(read))
            lines.append(buf.value[: read.value] if ok else "")
        while lines and not lines[-1].strip():
            lines.pop()
        return {"ok": True, "pid": target, "w": w, "h": len(lines),
                "method": "AttachConsole+ReadConsoleOutputCharacterW",
                "lines": lines, "full_text": "\n".join(lines)}
    finally:
        if h not in (None, _INVALID_HANDLE):
            try:
                _k32.CloseHandle(h)
            except Exception:
                pass
        try:
            _k32.FreeConsole()
        except Exception:
            pass
