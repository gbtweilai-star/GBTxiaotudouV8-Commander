# -*- coding: utf-8 -*-
"""接管 Colab：CDP 点格子 + **系统级键盘**粘贴运行（绕开 shadow DOM 吃不到注入的问题）。

## 为什么这么绕（真因，不是偷懒）
· CDP `Input.insertText` / `dispatchKeyEvent` 对 Colab 的编辑器**无效**（实测：focus 在
  `DIV.cell` 上、选区 `none`、插入后文本不变）。
· 但**系统级键盘事件**（user32 `keybd_event`）走的是 OS 输入队列，任何网页编辑器都得吃。
⇒ 定位/点击用 CDP（读 DOM 拿 rect），打字用 OS 键盘（Ctrl+V 粘剪贴板 + Ctrl+Enter 运行）。

用法：
  py -3 tools/codex-scripts/colab-takeover.py --paste     # 点格子→Ctrl+V→Ctrl+Enter
  py -3 tools/codex-scripts/colab-takeover.py --watch 600 # 盯页面，等 trycloudflare 地址
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import re
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import websocket                       # websocket-client

user32 = ctypes.windll.user32
CDP = "http://127.0.0.1:9222"
VK_MENU, VK_CONTROL, VK_V, VK_RETURN = 0x12, 0x11, 0x56, 0x0D
KEYEVENTF_KEYUP = 0x0002


def tg():
    with urllib.request.urlopen(CDP + "/json", timeout=8) as r:
        return json.loads(r.read().decode())


def chrome_target():
    for t in tg():
        if t.get("type") == "page" and "colab.research.google.com" in (t.get("url") or ""):
            return t
    return None


class Cdp:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=60, max_size=None)
        self.i = 0

    def send(self, m, **p):
        self.i += 1
        self.ws.send(json.dumps({"id": self.i, "method": m, "params": p}))
        while True:
            r = json.loads(self.ws.recv())
            if r.get("id") == self.i:
                return r

    def js(self, e):
        r = self.send("Runtime.evaluate", expression=e, returnByValue=True, userGesture=True)
        return (r.get("result") or {}).get("result", {}).get("value")


def focus_chrome():
    """把 Chrome 抢到前台（Windows 会拦，先按一下 Alt 再抢）。"""
    hwnd = None
    proc = ctypes.windll.kernel32
    # 用 CDP 的窗口句柄不直接给，这里按标题找
    found = []
    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, _l):
        n = user32.GetWindowTextLengthW(h)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(h, buf, n + 1)
            if "Colab" in buf.value:
                found.append((h, buf.value))
            elif "Chrome" in buf.value:
                found.append((h, buf.value))          # 兜底：没有 Colab 就退到任意 Chrome 窗
        return True
    user32.EnumWindows(cb, 0)
    if not found:
        return None
    hwnd, title = found[0]
    user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.6)
    fg = user32.GetForegroundWindow()
    return "%s · 前台命中=%s" % (title, fg == hwnd)


def key(vk, ctrl=False):
    if ctrl:
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    if ctrl:
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.15)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paste", action="store_true")
    ap.add_argument("--watch", type=int, default=0)
    a = ap.parse_args()

    t = chrome_target()
    if not t:
        print("没有 Colab 标签页")
        return 2
    print("目标:", (t.get("url") or "")[:70])
    title = focus_chrome()
    print("前台 Chrome:", title)

    cdp = Cdp(t["webSocketDebuggerUrl"])

    if a.paste:
        # 优先点“代码”格；没有就点最后一个 cell
        rect = cdp.js("""
        (function(){
          var cs = document.querySelectorAll('.cell.code');
          var c = cs.length ? cs[cs.length-1] : document.querySelector('.cell');
          if (!c) return null;
          c.scrollIntoView({block:'center'});
          var r = c.getBoundingClientRect();
          return {x: Math.round(r.x + 80), y: Math.round(r.y + Math.min(30, r.height/2)), n: document.querySelectorAll('.cell').length};
        })()
        """)
        info = cdp.js("""
        (function(){
          var cs = document.querySelectorAll('.cell');
          var out = [];
          cs.forEach(function(c,i){ if (c.className.toString().indexOf('code')>=0) out.push(i); });
          var c = cs[rectIdx];
          return {code_cells: out, total: cs.length,
                  clicked: rectIdx, cls: (c?c.className.toString():''),
                  head: (c? (c.innerText||'').slice(0,40).replace(/\n/g,' ') : '')};
        })()
        """.replace("rectIdx", "0")) if False else None
        print("点格子:", rect)
        if not rect:
            print("没找到格子（先把 Notebook 打开）")
            return 3
        # 系统级点击（更接近真人，CDP 点也行，这里两层都上）
        user32.SetCursorPos(rect["x"], rect["y"])
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        user32.mouse_event(0x0004, 0, 0, 0, 0)
        time.sleep(0.6)
        cdp.send("Input.dispatchMouseEvent", type="mousePressed", x=rect["x"], y=rect["y"],
                 button="left", clickCount=1)
        cdp.send("Input.dispatchMouseEvent", type="mouseReleased", x=rect["x"], y=rect["y"],
                 button="left", clickCount=1)
        time.sleep(1.0)
        print("粘贴（Ctrl+V）…")
        key(VK_V, ctrl=True)
        time.sleep(1.5)
        print("运行（Ctrl+Enter）…")
        key(VK_RETURN, ctrl=True)
        time.sleep(3)
        print("执行后可见文本尾部:", (cdp.js("document.body.innerText.slice(-300)") or "").replace("\n", " | ")[:300])

    if a.watch:
        print("盯 %d 秒，等隧道地址…" % a.watch)
        deadline = time.time() + a.watch
        last = ""
        while time.time() < deadline:
            txt = cdp.js("document.body.innerText") or ""
            m = re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com", txt)
            if m:
                print("URL:", m[-1])
                return 0
            tail = txt[-160:].replace("\n", " | ")
            if tail != last:
                print("…", tail[:160])
                last = tail
            time.sleep(10)
        print("没等到 URL（看页面输出/报错）")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
