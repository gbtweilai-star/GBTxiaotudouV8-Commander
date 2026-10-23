# -*- coding: utf-8 -*-
"""deploy-targets -- 四个部署目标逐档校验：苹果 / 安卓 / 本地 / 云端。"""
from __future__ import annotations
import argparse, json, re, socket, subprocess, sys
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
DIRS = ["holo_pet_w3", "state", "state/blueprints", "docs"]
EXEMPT = ("omarchy-community-raw",)   # 第三方原始素材，不改、不入手机包，判据豁免


def pages():
    out = []
    for d in DIRS:
        b = ROOT / d
        if b.is_dir():
            out += sorted(b.rglob("*.html"))
    return [p for p in out if p.is_file()]


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    ps = [x for x in pages() if not any(e in str(x) for e in EXEMPT)]
    _ex = len(pages()) - len(ps)
    if not ps:
        print("未读到页面")
        return 2
    n = len(ps)
    apple = sum(1 for p in ps if all(k in p.read_text(encoding="utf-8", errors="replace") for k in ("viewport-fit=cover", "apple-mobile-web-app-capable", "safe-area-inset")))
    android = sum(1 for p in ps if all(k in p.read_text(encoding="utf-8", errors="replace") for k in ("theme-color", "min-height:44px", "width=device-width")))
    rel_ok = 0
    for p in ps:
        t = p.read_text(encoding="utf-8", errors="replace")
        hrefs = re.findall(r'href="([^"]+)"', t)
        if all((not h.startswith(("file://", "C:", "/"))) for h in hrefs):
            rel_ok += 1
    pack = ROOT / "state" / "mobile-pack"
    pack_n = len(list(pack.rglob("*.html"))) if pack.is_dir() else 0
    manifest = (ROOT / "holo_pet_w3" / "manifest.webmanifest").is_file()
    cloud = [str(x.relative_to(ROOT)) for x in (ROOT / "deploy").rglob("wrangler.toml")][:2] if (ROOT / "deploy").is_dir() else []
    voice = (ROOT / "state" / "voice-bridge" / "voice-bridge-contract.json").is_file()
    print("四目标部署现读（有效页 %d · 豁免 %d 张第三方原始素材）" % (n, _ex))
    print("  ① 苹果 iOS  : %d/%d 页齐备（viewport-fit=cover + apple-web-app + 安全区）· manifest %s" % (apple, n, "在" if manifest else "缺"))
    print("  ② 安卓     : %d/%d 页齐备（viewport + theme-color + 触控≥44px）" % (android, n))
    print("  ③ 本地     : 手机包 %d 页 · 相对链接可离线 %d/%d · 局域网 http://%s:8080/index.html" % (pack_n, rel_ok, n, lan_ip()))
    print("  ④ 云端     : wrangler 配置 %s · 语音契约 %s · 发布需 deploy_publish 钥匙" % (cloud or "未读到", "在" if voice else "缺"))
    ok = (apple == n) and (android == n) and (rel_ok == n) and manifest and pack_n > 0  # 配置面（云端发布另需 deploy_publish，属授权面，不计红）
    print("== 四目标基础就绪 %s（云端发布另需钥匙）==" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
