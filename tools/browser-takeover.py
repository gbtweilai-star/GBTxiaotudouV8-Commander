# -*- coding: utf-8 -*-
"""接管**已开着的**浏览器（不新开浏览器）：用 Win32 输入注入 + 截屏当眼睛。

为什么不用 CDP：用户浏览器没开远程调试端口，CDP 连不上；但同一桌面会话里可以用
`SendInput` 操作当前窗口 —— 这就是"接管"。

能力：
    python tools/browser-takeover.py find                 # 列出可见顶层窗口（Chrome/Edge）
    python tools/browser-takeover.py focus --title Chrome # 前置窗口
    python tools/browser-takeover.py key --combo ctrl+l   # 组合键
    python tools/browser-takeover.py type --text "https://github.com/..."  # ASCII 输入
    python tools/browser-takeover.py click --x 320 --y 26 # 点按
    python tools/browser-takeover.py shot --out state/tmp/shot.png
    python tools/browser-takeover.py paste                # 剪贴板 → Ctrl+V
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import os
import pathlib
import sys
import time

# 2026-11-01 修：进程 DPI 不觉察时 GetSystemMetrics=1280x800 而实际 1920x1200(150%)，
# SetCursorPos 的坐标会被系统缩放 ⇒ 点哪都偏。先声明 DPI aware，坐标才 1:1。
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)   # PER_MONITOR_AWARE
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

INPUT_KEYBOARD = 1
INPUT_MOUSE = 0
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000

VK = {"ctrl": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B,
      "enter": 0x0D, "esc": 0x1B, "tab": 0x09, "space": 0x20,
      "backspace": 0x08, "delete": 0x2E, "home": 0x24, "end": 0x23,
      "pageup": 0x21, "pagedown": 0x22, "up": 0x26, "down": 0x28,
      "left": 0x25, "right": 0x27, "f5": 0x74, "f12": 0x7B}


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _U)]


def _send(*inputs):
    arr = (INPUT * len(inputs))(*inputs)
    user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))


def _key(vk, flags=0):
    ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=None)
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.ki = ki
    return inp


def key_down(vk):
    _send(_key(vk))


def key_up(vk):
    _send(_key(vk, KEYEVENTF_KEYUP))


def tap(vk):
    key_down(vk); time.sleep(0.02); key_up(vk)


def combo(spec: str):
    keys = [k.strip().lower() for k in spec.replace("+", " ").split() if k.strip()]
    vks = []
    for k in keys:
        if k in VK:
            vks.append(VK[k])
        elif len(k) == 1:
            vks.append(user32.VkKeyScanW(ord(k)) & 0xFF)
        else:
            raise SystemExit("不认识的键：%s" % k)
    for v in vks:
        key_down(v); time.sleep(0.02)
    for v in reversed(vks):
        key_up(v); time.sleep(0.02)


def type_text(text: str):
    """Unicode 注入：支持中文（不依赖键盘布局）。"""
    for ch in text:
        code = ord(ch)
        ki = KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=None)
        inp = INPUT(type=INPUT_KEYBOARD); inp.ki = ki
        _send(inp)
        time.sleep(0.008)
        ki2 = KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP,
                         time=0, dwExtraInfo=None)
        inp2 = INPUT(type=INPUT_KEYBOARD); inp2.ki = ki2
        _send(inp2)
        time.sleep(0.004)


def move(x: int, y: int):
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.05)


def click(x: int, y: int, clicks: int = 1):
    move(x, y)
    for _ in range(max(1, clicks)):
        mi = MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=MOUSEEVENTF_LEFTDOWN,
                        time=0, dwExtraInfo=None)
        inp = INPUT(type=INPUT_MOUSE); inp.mi = mi
        _send(inp)
        time.sleep(0.04)
        mi2 = MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=MOUSEEVENTF_LEFTUP,
                         time=0, dwExtraInfo=None)
        inp2 = INPUT(type=INPUT_MOUSE); inp2.mi = mi2
        _send(inp2)
        time.sleep(0.15)


def list_windows():
    out = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _lp):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n == 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        r = wt.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        out.append({"hwnd": hwnd, "title": buf.value, "class": cls.value,
                    "rect": [r.left, r.top, r.right, r.bottom]})
        return True

    user32.EnumWindows(cb, 0)
    return out


def focus(title_sub: str) -> dict:
    title_sub_l = title_sub.lower()
    cands = [w for w in list_windows() if title_sub_l in w["title"].lower()]
    if not cands:
        cands = [w for w in list_windows() if "chrome" in w["class"].lower()]
    if not cands:
        return {"ok": False, "error": "没找到窗口：%s" % title_sub}
    w = cands[0]
    hwnd = w["hwnd"]
    user32.ShowWindow(hwnd, 9)          # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    time.sleep(0.3)
    return {"ok": True, "window": w["title"][:80], "rect": w["rect"]}


def shot(out: str) -> dict:
    import mss
    from PIL import Image
    p = pathlib.Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    with mss.mss() as s:
        img = s.grab(s.monitors[1])
    Image.frombytes("RGB", img.size, img.rgb).save(str(p))
    return {"ok": True, "path": str(p), "size": list(img.size)}


def clipboard_get() -> str:
    ps = "Get-Clipboard -Raw"
    import subprocess
    r = subprocess.run(["powershell", "-NoProfile", "-c", ps], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=30)
    return (r.stdout or "").strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["find", "focus", "key", "type", "click", "shot", "paste", "clip"])
    ap.add_argument("--title", default="Chrome")
    ap.add_argument("--combo", default="")
    ap.add_argument("--text", default="")
    ap.add_argument("--x", type=int, default=0)
    ap.add_argument("--y", type=int, default=0)
    ap.add_argument("--clicks", type=int, default=1)
    ap.add_argument("--out", default="state/tmp/shot.png")
    a = ap.parse_args()

    if a.cmd == "find":
        print(json_dump([{k: w[k] for k in ("hwnd", "title", "class")} for w in list_windows()]))
    elif a.cmd == "focus":
        print(json_dump(focus(a.title)))
    elif a.cmd == "key":
        combo(a.combo)
        print(json_dump({"ok": True, "combo": a.combo}))
    elif a.cmd == "type":
        type_text(a.text)
        print(json_dump({"ok": True, "chars": len(a.text)}))
    elif a.cmd == "click":
        click(a.x, a.y, a.clicks)
        print(json_dump({"ok": True, "at": [a.x, a.y]}))
    elif a.cmd == "shot":
        print(json_dump(shot(a.out)))
    elif a.cmd == "paste":
        combo("ctrl+v")
        print(json_dump({"ok": True}))
    elif a.cmd == "clip":
        print(json_dump({"text": clipboard_get()[:200]}))
    return 0


def json_dump(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)


if __name__ == "__main__":
    raise SystemExit(main())
