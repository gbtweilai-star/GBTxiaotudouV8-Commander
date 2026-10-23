# -*- coding: utf-8 -*-
"""device-deploy -- 部署设备配置（苹果 iPhone 17 / iOS Safari 原生友好）

--inject  给全部页注入：viewport(viewport-fit=cover) · apple-mobile-web-app-* · theme-color ·
          safe-area-inset 内边距 · 触控尺寸 · manifest 链接；并写出 manifest.webmanifest
--check   逐页校验上述七项（缺一即红）
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
PAGE_DIRS = ["holo_pet_w3", "state", "state/blueprints", "docs"]
# 🔴 2026-10-17 事故剪枝（与 `page-reach` 同源 · 自反爆炸）：产物目录绝不进页面枚举
SKIP_PARTS = {".git", "node_modules", ".pylibs", "vendor", "_upstream", ".scratch",
              "mobile-pack", ".mimosa", "__pycache__", ".wrangler"}
MAX_PAGES = 3000


def _skip(p):
    return any(part in SKIP_PARTS for part in p.parts)
MARK = "<!-- gbt-apple-config -->"
# 🔴 2026-10-17 修（**苹果安卓都要** · 留痕 · 原口径 / 为什么翻 / 现口径）：
#   原口径：只注入 Apple 元信息 + 触控 44px。
#   为什么翻（主人令「手机是苹果安卓都有的哈」+ 现读 `state/deploy-profiles.json`）：
#     两档并存：`apple-iphone17`（tap_min_px=44，viewport-fit=cover）与
#     `android-mobile`（**tap_min_px=48**，Chrome 添加到主屏）。原注入缺
#     安卓的 `mobile-web-app-capable`，且触控写死 44 ⇒ **安卓档不达标**。
#   现口径：两档**取严**注入 —— 触控 48px（48 ≥ 44，两档都满足）+ 安卓 `mobile-web-app-capable`
#     （iOS 也照收，不冲突）+ manifest（display:standalone 安卓靠它）。
META = ('<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<meta name="apple-mobile-web-app-capable" content="yes">'
        '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">'
        '<meta name="apple-mobile-web-app-title" content="小土豆V8">'
        '<meta name="mobile-web-app-capable" content="yes">'
        '<meta name="theme-color" content="#0b0d10">'
        '<meta name="format-detection" content="telephone=no">'
        '<style id="gbt-apple-css">:root{--sat:env(safe-area-inset-top);--sab:env(safe-area-inset-bottom)}'
        'body{padding-top:calc(8px + var(--sat));padding-bottom:calc(8px + var(--sab));-webkit-text-size-adjust:100%}'
        'a,button{min-height:48px;min-width:48px;display:inline-block}</style>')


def pages():
    """全部页面（**去重**：`state` 已含 `state/blueprints`，别数两遍/注入两遍）。"""
    out, seen = [], set()
    for d in PAGE_DIRS:
        b = ROOT / d
        if not b.is_dir():
            continue
        for p in sorted(b.rglob("*.html")):
            if not p.is_file() or _skip(p):
                continue
            key = str(p.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
    if len(out) > MAX_PAGES:                                     # fail-closed
        raise SystemExit("页面数 %d > 上限 %d ⇒ 疑似产物自反，拒绝注入" % (len(out), MAX_PAGES))
    return out


def manifest_dir():
    return ROOT / "holo_pet_w3"


def inject():
    ps = pages()
    n = 0
    for p in ps:
        t = p.read_text(encoding="utf-8", errors="replace")
        t = re.sub(r'<meta name="viewport"[^>]*>', "", t)
        t = re.sub(r'<!-- gbt-apple-config -->.*?</style>', "", t, flags=re.S)
        block = MARK + META
        if "<head" in t:
            i = t.find(">", t.find("<head")) + 1
            t = t[:i] + chr(10) + block + chr(10) + t[i:]
        else:
            t = block + chr(10) + t
        p.write_text(t, encoding="utf-8")
        n += 1
    md = manifest_dir()
    md.mkdir(parents=True, exist_ok=True)
    (md / "manifest.webmanifest").write_text(json.dumps({
        "name": "GBT小土豆V8", "short_name": "小土豆V8", "start_url": "./capabilities/index.html",
        "display": "standalone", "background_color": "#0b0d10", "theme_color": "#0b0d10",
        "orientation": "any", "icons": []}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("苹果配置已注入 %d 页 · manifest -> %s" % (n, (md / "manifest.webmanifest").relative_to(ROOT)))


def check():
    ps = pages()
    NEED = [("viewport+cover", 'viewport-fit=cover'), ("apple-capable", "apple-mobile-web-app-capable"),
            ("status-bar", "apple-mobile-web-app-status-bar-style"),
            ("android-capable", "mobile-web-app-capable"),
            ("theme-color", "theme-color"), ("safe-area", "safe-area-inset"),
            ("48px 触控(苹果44/安卓48 取严)", "min-height:48px")]
    ok, bad = 0, []
    for p in ps:
        t = p.read_text(encoding="utf-8", errors="replace")
        miss = [k for k, kw in NEED if kw not in t]
        if not miss:
            ok += 1
        else:
            bad.append((str(p.relative_to(ROOT)), miss))
    mf = manifest_dir() / "manifest.webmanifest"
    print("苹果部署配置：页 %d 张 · **全项齐备 %d** · 未齐 %d · manifest %s"
          % (len(ps), ok, len(bad), "在" if mf.is_file() else "缺"))
    for b in bad[:6]:
        print("   RED %s 缺 %s" % b)
    return 0 if (not bad and mf.is_file()) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inject", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--profile", default="apple-iphone17")
    a = ap.parse_args()
    if a.inject:
        inject()
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
