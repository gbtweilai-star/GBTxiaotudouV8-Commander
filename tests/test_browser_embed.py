# -*- coding: utf-8 -*-
"""我们自己的原生浏览器（browser_embed）契约 + APP 宿主接线验收。"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import browser_embed as BE  # noqa: E402

OK = 0
FAIL = []


def check(name, cond, got=None):
    global OK
    if cond:
        OK += 1
        print("  ok  ", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, "|", repr(got)[:200])


def main() -> int:
    print("[1] 契约自检（URL/边界/标签/下载名）")
    r = BE.verify()
    check("verify() 全绿", r["ok"] is True, r.get("failed"))
    check("判据数 ≥ 20", r["checks"] >= 20, r["checks"])
    check("只放行 http/https",
          BE.normalize_url("http://a.com")["ok"] and BE.normalize_url("https://a.com")["ok"]
          and not BE.normalize_url("file:///x")["ok"] and not BE.normalize_url("javascript:1")["ok"])
    check("裸域名补 https", BE.normalize_url("example.com")["url"] == "https://example.com")
    check("搜索词回退", BE.normalize_url("今天天气")["url"].startswith(BE.SEARCH_BASE))
    check("边界 clamp", BE.safe_bounds({"x": -1, "y": 10, "width": 9999, "height": 20},
                                        {"width": 640, "height": 480})["width"] == 640)
    check("下载名清洗", BE.sanitize_download_name("a<b>:c?.zip") == "a_b__c_.zip")
    m = BE.TabModel()
    m.open("https://a"); m.open("https://b")
    check("标签开关选邻居", m.switch(1)["ok"] and m.close(1)["active"] == 2)
    m1 = BE.TabModel(max_tabs=1)
    m1.open()
    check("标签上限", m1.open()["ok"] is False)

    print("[2] Electron 宿主 / APP 接线")
    host = ROOT / "holo_pet_w3/shell/browser-embed-host.cjs"
    check("宿主模块在盘上", host.is_file())
    ht = host.read_text(encoding="utf-8")
    check("宿主用 WebContentsView", "WebContentsView" in ht and "contentView.addChildView" in ht)
    check("宿主有私有分区/下载/权限收窄",
          "persist:gbt-browser" in ht and "will-download" in ht
          and "setPermissionRequestHandler" in ht)
    check("宿主有 URL 白名单", "normalizeUrl" in ht and "scheme_not_allowed" in ht)
    pre = (ROOT.parent / "GBT小土豆V8桌面版/resources/app/preload.js")
    if pre.is_file():
        pt = pre.read_text(encoding="utf-8")
        check("APP preload 暴露 gbtBrowser", "gbtBrowser" in pt and "browser:embed" in pt)
    main = (ROOT.parent / "GBT小土豆V8桌面版/resources/app/main.js")
    if main.is_file():
        mt = main.read_text(encoding="utf-8")
        check("APP main 安装宿主", "browser-embed-host.cjs" in mt and "WebContentsView" in mt)
        check("APP 宿主文件已同步", (ROOT.parent / "GBT小土豆V8桌面版/resources/app/browser-embed-host.cjs").is_file())
    idx = (ROOT / "holo_pet_w3/console/index.html").read_text(encoding="utf-8")
    js = (ROOT / "holo_pet_w3/console/app.js").read_text(encoding="utf-8")
    check("console 有浏览器标签条", 'id="bw-tabs"' in idx)
    check("console 接 WebContentsView 宿主",
          "ensureHostBrowser" in js and "hostShow" in js and "gbtBrowser" in js)
    check("console 保留 <webview> 降级", 'id="gbt-webview"' in idx)
    check("窗口边界 clamp 传给宿主", "browserBodyRect" in js and "setBounds" in js)
    check("在线 WebContentsView 落地记录（docs）", (ROOT / "docs/162-native-browser-embed.md").is_file())

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— browser_embed 契约（URL/边界/标签/下载名）+ WebContentsView 宿主 + console/APP 接线全绿")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
