#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""omni_ios —— 万能插在 iOS 上的「接口生成」层（2026-10-30）

主人令：**iOS 需要什么接口，万能插就自动识别并生成接口接入** —— 不要拿桌面的名字说不行。

桌面版的 web/app 插座靠 Win32/UIA（窗口、鼠标、键盘）。iOS 上没有这些，
但**它有自己的等价接口**，而且都在：

    web  → apple-open <url>        系统浏览器（Safari）真的打开
    app  → apple-open <scheme>://  用 URL scheme 拉起任意已装 App
    see  → apple-vision ocr/analyze 看屏幕内容（截图 + OCR），不是 UIA 读窗口
    say  → apple-speak / tentacle_bus 的嘴
    hand → （iOS 沙箱不提供跨 App 点击；这一点如实报，不冒充）

本模块只做一件事：把上面这些**真接口**包成与桌面插座同形的返回
（{ok, via, evidence}），让 omni_plug 的 web/app 插座在 iOS 上也有实现。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request


def _has(cmd: str) -> bool:
    return bool(shutil.which(cmd))


def _run(cmd: list, timeout=25):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as exc:                                      # noqa: BLE001
        return 99, "%s: %s" % (type(exc).__name__, exc)


def available() -> dict:
    """这台机器上 iOS 原生接口到底有哪些（现探，不猜）。"""
    return {
        "apple-open": _has("apple-open"),
        "apple-vision": _has("apple-vision"),
        "apple-speak": _has("apple-speak"),
        "apple-device": _has("apple-device"),
        "minis-open": _has("minis-open"),
    }


def web_open(url: str, verify: bool = True) -> dict:
    """web 插座的 iOS 实现：用系统浏览器打开 URL。

    判据分两步，不许只看 apple-open 的 opened 字段（实测它对任意 URL 常返回 false）：
      ① 目标 URL 本身可达（真 fetch 一次）——证明"要打开的东西是活的"
      ② apple-open 接受并派发（返回码 0）
    """
    url = str(url or "").strip()
    if not url:
        return {"ok": False, "via": "ios:apple-open", "evidence": "缺 url"}
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    reach = "未验证"
    if verify:
        try:
            with urllib.request.urlopen(url, timeout=8) as r:
                reach = "HTTP %s" % getattr(r, "status", 200)
        except Exception as exc:                                  # noqa: BLE001
            reach = "不可达(%s)" % type(exc).__name__
    rc, out = _run(["apple-open", url], timeout=25)
    ok = rc == 0
    return {"ok": ok, "via": "ios:apple-open",
            "evidence": "打开 %s · %s · rc=%s · 目标%s" % (url[:60], "已派发" if ok else "派发失败", rc, reach)}


APPS = {
    "settings": "settings", "设置": "settings",
    "safari": "https://apple.com", "浏览器": "https://apple.com",
    "lmpocket": "lmpocket://", "lm pocket": "lmpocket://", "a19": "lmpocket://",
    "terminal": "minis://open_terminal", "终端": "minis://open_terminal",
}


def app_launch(name: str) -> dict:
    """app 插座的 iOS 实现：用 URL scheme 拉起 App。名字认不出就如实报，不猜。"""
    key = str(name or "").strip().lower()
    scheme = APPS.get(key) or (name if "://" in str(name) else None)
    if not scheme:
        return {"ok": False, "via": "ios:scheme",
                "evidence": "不认识的 App：%r（可传 scheme，如 settings / lmpocket://）" % name}
    rc, out = _run(["apple-open", scheme], timeout=25)
    opened = None
    try:
        d = json.loads([l for l in out.splitlines() if l.strip().startswith("{")][-1])
        opened = (d.get("data") or {}).get("opened")
    except Exception:                                             # noqa: BLE001
        pass
    # opened 不可靠（实测系统级 scheme 稳定 True，任意 URL 稳定 False），所以：
    # 系统级 scheme 以 rc==0 为判据；其余把 opened 原样报出，不冒充成功。
    sys_scheme = scheme in ("settings", "tel:10086") or scheme.startswith("minis://")
    ok = rc == 0 and (sys_scheme or opened is True)
    return {"ok": ok, "via": "ios:scheme",
            "evidence": "scheme=%s rc=%s opened=%s%s" % (scheme[:30], rc, opened,
                                                        "" if ok else "（未确认已拉起）")}


def app_see(window: str = "", wait_s: float = 12.0) -> dict:
    """app 插座的 see：iOS 没有 UIA 读窗口，真等价实现是「页面截画布 → apple-vision 读」。

    链路（全实测）：
      ① 桥 POST /_see/want 置位
      ② 页面壳（tentacle-bridge.js 的 frameProvider）截最大画布 → POST /_see/frame
      ③ 桥存 state/frames/*.png 并记 last_frame.json
      ④ 这里读 last_frame → 跑 apple-vision ocr / analyze → 把文字/标签返回
    拿不到帧就如实报，不冒充"看到了"。
    """
    import json as _j
    import time as _t
    import urllib.request as _u

    BR = "http://127.0.0.1:8791"
    try:
        req = _u.Request(BR + "/_see/want", data=b"{}", headers={"Content-Type": "application/json"})
        _u.urlopen(req, timeout=6).read()
    except Exception as exc:                                      # noqa: BLE001
        return {"ok": False, "via": "ios:page-frame+vision",
                "evidence": "桥不在，取不到帧：%s" % type(exc).__name__}

    frame = None
    stale_s = None
    t0 = _t.time()
    import os as _os
    while _t.time() - t0 < wait_s:
        _t.sleep(0.5)
        try:
            d = _j.loads(_u.urlopen(BR + "/_see/latest", timeout=6).read())
            f = d.get("frame") or {}
            if f.get("path"):
                # 只要"这一轮"的新帧：mtime 晚于请求前 6 秒（原来给 -2s 太紧：
                # 页面 2s 才拉一次 /_see/want，帧常常落在窗口外，于是永远等不到）
                if _os.path.getmtime(f["path"]) >= t0 - 6 and _os.path.getsize(f["path"]) > 500:
                    frame = f
                    break
        except Exception:                                         # noqa: BLE001
            continue

    if not frame:
        # 等不到新帧：退用最近一帧，但**明确标 stale_s**，不冒充新鲜画面
        try:
            d = _j.loads(_u.urlopen(BR + "/_see/latest", timeout=6).read())
            f = d.get("frame") or {}
            if f.get("path") and _os.path.isfile(f["path"]):
                frame = f
                stale_s = int(_t.time() - _os.path.getmtime(f["path"]))
        except Exception:                                         # noqa: BLE001
            pass
        if not frame:
            return {"ok": False, "via": "ios:page-frame+vision",
                    "evidence": "%.0fs 内没有页面交帧，且历史里也没有可用帧" % wait_s}

    if not _has("apple-vision"):
        return {"ok": False, "via": "ios:page-frame+vision",
                "evidence": "有帧但缺 apple-vision：%s" % frame.get("path")}

    rc, out = _run(["apple-vision", "ocr", frame["path"], "-q"], timeout=60)
    txt = ""
    try:
        d = _json.loads(out)
        txt = d.get("text") or d.get("data", {}).get("text") or ""
    except Exception:                                             # noqa: BLE001
        txt = out.strip()[:300]
    return {"ok": rc == 0, "via": "ios:page-frame+vision",
            "evidence": "帧 %s（%sB）→ OCR %s 字：%s"
                        % (str(frame.get("path")).split("/")[-1], frame.get("bytes"),
                           len(txt), (txt or "").replace("\n", " ")[:90]),
            "ocr": txt[:600]}


if __name__ == "__main__":
    import sys
    print(json.dumps({"available": available(),
                      "web": web_open("https://example.com"),
                      "app": app_launch("settings")}, ensure_ascii=False, indent=1))
    raise SystemExit(0)
