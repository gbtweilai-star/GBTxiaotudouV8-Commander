# -*- coding: utf-8 -*-
# gbt-capability: none  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""我们自己的原生浏览器 · 契约层（browser_embed）。

对照上游参考项目的 `electron/browser-embed-host.cjs`（WebContentsView 内嵌宿主：分区/下载/权限/边界），
只取**契约与判据**，不搬代码；Electron 侧宿主在 `holo_pet_w3/shell/browser-embed-host.cjs`。

本件是纯函数（零设备/零出网/零写盘），给宿主和测试共用同一套口径：
  · 只许 http/https；裸域名补 https；非网址走搜索；
  · 页面边界 clamp 到窗口内，防 IPC 传越界/超大 geometry；
  · 标签模型：上限 12、关活动标签自动选邻居、切标签不改历史；
  · 下载文件名清洗（Windows 保留名/非法字符/长度）。
"""
from __future__ import annotations

import hashlib
import re

ALLOWED_SCHEMES = ("http", "https")
MAX_TABS = 12
MAX_URL_LEN = 4096
MAX_BOUNDS = 100000
SEARCH_BASE = "https://www.bing.com/search?q="
_WIN_RESERVED = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$", re.I)


def normalize_url(raw, allow_search: bool = True) -> dict:
    """任何用户输入 → {ok, url} 或 {ok:False, reason}；只放行 http/https。"""
    s = str(raw or "").strip()
    if not s:
        return {"ok": False, "reason": "empty"}
    if len(s) > MAX_URL_LEN:
        return {"ok": False, "reason": "too_long"}
    low = s.lower()
    if "://" in low:
        scheme = low.split("://", 1)[0]
        if scheme not in ALLOWED_SCHEMES:
            return {"ok": False, "reason": "scheme_not_allowed", "scheme": scheme}
        return {"ok": True, "url": s}
    if re.match(r"^(javascript|data|file|vbscript|about|chrome|edge):", low):
        return {"ok": False, "reason": "scheme_not_allowed",
                "scheme": low.split(":", 1)[0]}
    if re.match(r"^[\w-]+(\.[\w-]+)+([/:?#].*)?$", s):
        return {"ok": True, "url": "https://" + s}
    if re.match(r"^localhost(:\d+)?(/.*)?$", s):
        return {"ok": True, "url": "http://" + s}
    if allow_search:
        return {"ok": True, "url": SEARCH_BASE + __import__("urllib.parse").parse.quote(s),
                "search": True}
    return {"ok": False, "reason": "not_url"}


def allowed_navigation(url) -> bool:
    """宿主 will-navigate / setWindowOpenHandler 的同一判据。"""
    return normalize_url(url, allow_search=False).get("ok") is True


def safe_bounds(bounds, content_size) -> dict:
    """页面边界 → 合法整数；clamp 在窗口内；非法输入返回全 0。"""
    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0
    cw = max(1.0, num((content_size or {}).get("width")))
    ch = max(1.0, num((content_size or {}).get("height")))
    x = max(0.0, min(num((bounds or {}).get("x")), cw))
    y = max(0.0, min(num((bounds or {}).get("y")), ch))
    w = max(0.0, min(num((bounds or {}).get("width")), cw - x, MAX_BOUNDS))
    h = max(0.0, min(num((bounds or {}).get("height")), ch - y, MAX_BOUNDS))
    return {"x": int(x), "y": int(y), "width": int(w), "height": int(h)}


def sanitize_download_name(name, fallback: str = "download") -> str:
    s = str(name or "").strip().replace("\\", "/").split("/")[-1]
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", s).strip(" .")
    if not s or _WIN_RESERVED.match(s):
        return fallback
    if len(s) > 180:
        stem, dot, ext = s.rpartition(".")
        s = (stem[:170] + "." + ext[:8]) if dot and ext else s[:180]
    return s


class TabModel:
    """标签模型（纯状态）：宿主只负责把 view 映射到这个 id。"""

    def __init__(self, max_tabs: int = MAX_TABS):
        self.max_tabs = int(max_tabs)
        self._next = 1
        self.tabs = []
        self.active = None

    def open(self, url: str = "", tab_id: int | None = None) -> dict:
        if len(self.tabs) >= self.max_tabs:
            return {"ok": False, "reason": "too_many_tabs"}
        tid = int(tab_id or self._next)
        self._next = max(self._next, tid + 1)
        self.tabs.append({"id": tid, "url": str(url or ""), "title": "新标签页"})
        self.active = tid
        return {"ok": True, "tab": self.tabs[-1], "active": self.active}

    def close(self, tab_id: int) -> dict:
        idx = next((i for i, t in enumerate(self.tabs) if t["id"] == int(tab_id)), -1)
        if idx < 0:
            return {"ok": False, "reason": "no_such_tab"}
        closed = self.tabs.pop(idx)
        if self.active == closed["id"]:
            if not self.tabs:
                self.active = None
            else:
                self.active = self.tabs[min(idx, len(self.tabs) - 1)]["id"]
        return {"ok": True, "closed": closed, "active": self.active, "tabs": len(self.tabs)}

    def switch(self, tab_id: int) -> dict:
        if not any(t["id"] == int(tab_id) for t in self.tabs):
            return {"ok": False, "reason": "no_such_tab"}
        self.active = int(tab_id)
        return {"ok": True, "active": self.active}

    def set_meta(self, tab_id: int, **kw) -> dict:
        for t in self.tabs:
            if t["id"] == int(tab_id):
                for k in ("url", "title", "loading"):
                    if k in kw:
                        t[k] = kw[k]
                return {"ok": True, "tab": t}
        return {"ok": False, "reason": "no_such_tab"}

    def snapshot(self) -> dict:
        return {"tabs": [dict(t) for t in self.tabs], "active": self.active,
                "count": len(self.tabs), "max": self.max_tabs}


def verify() -> dict:
    checks = []

    def ck(name, cond, got=None):
        checks.append({"name": name, "ok": bool(cond), "got": got})

    r = normalize_url("example.com")
    ck("裸域名补 https", r["ok"] and r["url"] == "https://example.com", r)
    ck("http 放行", normalize_url("http://example.com/a")["ok"])
    ck("https 放行", normalize_url("https://example.com")["ok"])
    ck("javascript: 拒", normalize_url("javascript:alert(1)")["ok"] is False)
    ck("file: 拒", normalize_url("file:///C:/x")["ok"] is False)
    ck("data: 拒", normalize_url("data:text/html,x")["ok"] is False)
    ck("空串拒", normalize_url("")["ok"] is False)
    ck("搜索词回退", normalize_url("今天天气")["url"].startswith(SEARCH_BASE))
    ck("超长 URL 拒", normalize_url("https://x.com/" + "a" * 5000)["ok"] is False)
    b = safe_bounds({"x": -10, "y": 20, "width": 99999, "height": -5},
                    {"width": 800, "height": 600})
    ck("bounds clamp", b == {"x": 0, "y": 20, "width": 800, "height": 0}, b)
    ck("bounds 非数字回 0", safe_bounds(None, None) == {"x": 0, "y": 0, "width": 0, "height": 0})
    ck("下载名清洗", sanitize_download_name("a<b>:c?.zip") == "a_b__c_.zip",
       sanitize_download_name("a<b>:c?.zip"))
    ck("保留名回退", sanitize_download_name("CON.txt") == "download")
    ck("下载名去目录", sanitize_download_name("../../x.pdf") == "x.pdf")
    ck("导航白名单", allowed_navigation("https://a.com") and not allowed_navigation("file:///x"))
    m = TabModel()
    ck("开标签", m.open("https://a.com")["ok"] and m.active == 1)
    ck("开第二个", m.open("https://b.com")["ok"] and m.active == 2)
    ck("切标签", m.switch(1)["ok"] and m.active == 1)
    ck("关活动标签选邻居", m.close(1)["ok"] and m.active == 2)
    ck("关不存在标签", m.close(99)["ok"] is False)
    m2 = TabModel(max_tabs=1)
    m2.open()
    ck("标签上限", m2.open()["ok"] is False)
    ck("快照字段", set(TabModel().snapshot()) >= {"tabs", "active", "count", "max"})
    return {"ok": all(c["ok"] for c in checks), "checks": len(checks),
            "failed": [c for c in checks if not c["ok"]],
            "sha": hashlib.sha256(str(checks).encode("utf-8")).hexdigest()[:12]}
