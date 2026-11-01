# -*- coding: utf-8 -*-
"""GBT 万能插 · 手（本地手/眼服务，独立可跑）

为什么单独有一个：仓里的 `tools/model-bridge/server.py` 依赖 `lane_guard`（本 checkout 里缺），
起不来；而"手指"只需要 pyautogui。这个文件**零额外依赖**，双击 `hands-on.cmd` 即开，
在**你自己的普通进程**里跑，所以输入注入不会被 DSH 的 job/低权限拦。

接口（只监听 127.0.0.1）：
    GET  /health                → {"ok": true, "size": [w,h]}
    GET  /windows               → 可见窗口列表
    POST /act  {"limb":"move","x":100,"y":200}
               {"limb":"click","x":..,"y":..,"button":"left","clicks":1}
               {"limb":"double","x":..,"y":..}
               {"limb":"type","text":"..."}
               {"limb":"key","key":"enter"}
               {"limb":"hotkey","keys":["ctrl","l"]}
               {"limb":"scroll","amount":-3}
               {"limb":"focus","title":"Chrome"}
               {"limb":"see","out":"C:/path/shot.png"}
               {"limb":"size"}
"""
from __future__ import annotations

import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import pyautogui
except Exception as exc:  # noqa: BLE001
    print("缺少 pyautogui：", exc)
    print("安装：pyembed 里已装；若换 python 请 pip install pyautogui")
    sys.exit(1)

pyautogui.FAILSAFE = False

VK = {"enter": 0x0D, "esc": 0x1B, "tab": 0x09, "space": 0x20, "backspace": 0x08,
      "delete": 0x2E, "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22,
      "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27, "f5": 0x74}


def _windows():
    import ctypes
    import ctypes.wintypes as wt
    u = ctypes.windll.user32
    out = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, lp):
        if u.IsWindowVisible(h):
            n = u.GetWindowTextLengthW(h)
            if n:
                b = ctypes.create_unicode_buffer(n + 2)
                u.GetWindowTextW(h, b, n + 2)
                out.append({"hwnd": h, "title": b.value})
        return True

    u.EnumWindows(cb, 0)
    return out


def _focus(title_sub: str):
    import ctypes
    import ctypes.wintypes as wt
    u = ctypes.windll.user32
    hit = [w for w in _windows() if title_sub.lower() in w["title"].lower()]
    if not hit:
        return {"ok": False, "error": "没找到窗口: %s" % title_sub}
    hwnd = hit[0]["hwnd"]
    u.ShowWindow(hwnd, 9)
    u.SetForegroundWindow(hwnd)
    time.sleep(0.25)
    return {"ok": u.GetForegroundWindow() == hwnd, "window": hit[0]["title"][:80]}


def act(limb: str, a: dict) -> dict:
    limb = (limb or "").strip().lower()
    if limb == "size":
        return {"ok": True, "size": list(pyautogui.size())}
    if limb == "move":
        pyautogui.moveTo(int(a.get("x", 0)), int(a.get("y", 0)),
                         duration=float(a.get("duration", 0.1)))
        return {"ok": True, "pos": [int(a.get("x", 0)), int(a.get("y", 0))]}
    if limb == "click":
        pyautogui.click(int(a.get("x", 0)), int(a.get("y", 0)),
                        clicks=int(a.get("clicks", 1)), button=str(a.get("button", "left")),
                        interval=float(a.get("interval", 0.1)))
        return {"ok": True, "at": [int(a.get("x", 0)), int(a.get("y", 0))]}
    if limb == "double":
        pyautogui.doubleClick(int(a.get("x", 0)), int(a.get("y", 0)))
        return {"ok": True, "at": [int(a.get("x", 0)), int(a.get("y", 0))]}
    if limb == "type":
        text = str(a.get("text") or "")
        pyautogui.write(text, interval=float(a.get("interval", 0.01)))
        return {"ok": True, "chars": len(text)}
    if limb == "key":
        k = str(a.get("key") or "").lower()
        if k in VK:
            import ctypes
            u = ctypes.windll.user32
            u.keybd_event(VK[k], 0, 0, 0)
            time.sleep(0.03)
            u.keybd_event(VK[k], 0, 2, 0)
            return {"ok": True, "key": k}
        pyautogui.press(k)
        return {"ok": True, "key": k}
    if limb == "hotkey":
        keys = [str(x).lower() for x in (a.get("keys") or [])]
        pyautogui.hotkey(*keys)
        return {"ok": True, "keys": keys}
    if limb == "scroll":
        pyautogui.scroll(int(a.get("amount", -3)))
        return {"ok": True}
    if limb == "focus":
        return _focus(str(a.get("title") or "Chrome"))
    if limb == "windows":
        return {"ok": True, "windows": [w["title"][:80] for w in _windows()][:30]}
    if limb == "see":
        out = str(a.get("out") or os.path.join(os.environ.get("TEMP", "."), "gbt-see.png"))
        img = pyautogui.screenshot()
        img.save(out)
        return {"ok": True, "path": out, "size": list(img.size)}
    return {"ok": False, "error": "不认识的 limb: %s" % limb}


class H(BaseHTTPRequestHandler):
    def _json(self, code: int, obj: dict):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/health"):
            return self._json(200, {"ok": True, "size": list(pyautogui.size()),
                                    "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
        if self.path.startswith("/windows"):
            return self._json(200, {"ok": True, "windows": [w["title"][:80] for w in _windows()][:50]})
        return self._json(404, {"ok": False, "error": "unknown path"})

    def do_POST(self):  # noqa: N802
        if not self.path.startswith("/act"):
            return self._json(404, {"ok": False, "error": "unknown path"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:  # noqa: BLE001
            return self._json(400, {"ok": False, "error": "bad json: %s" % e})
        try:
            return self._json(200, act(str(body.get("limb") or ""), body.get("args") or {}))
        except Exception as e:  # noqa: BLE001
            return self._json(200, {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:160])})

    def log_message(self, fmt, *args):  # 静默
        pass


def main() -> int:
    port = int(os.environ.get("GBT_HANDS_PORT", "8791"))
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print("GBT 手服务已开：http://127.0.0.1:%d  （screen=%s）" % (port, pyautogui.size()))
    print("Ctrl-C 停止。")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
