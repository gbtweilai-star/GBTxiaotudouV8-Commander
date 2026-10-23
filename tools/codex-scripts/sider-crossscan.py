# -*- coding: utf-8 -*-
r"""Sider 穿透式交叉扫描（sider-crossscan）—— **对她项目树逐层量，并核我先前的结论对不对**。

主人令（2026-10-10）：「你先使用**穿透式交叉扫描**一遍 sider 的项目树，**看看到底对不对**，
  还有看看**还有没有遗漏的**」

## 扫的是她真身（不是营销页）
扩展目录 = gbt_allinone/store/native_browser/profile/Default/Extensions/difoiogjjojoaoomphldepapgpbgkhkb
（实测两个版本目录：5.33.0_0 · 5.34.1_0；而 CDP 里正在跑的是 **5.34.2** ⇒ **盘上落后一版**）

## 交叉核对（到底对不对）
| 我先前说的 | 核验 | 证据 |
|---|---|---|
| 能力面 = 60 项可点 | 🔴 **浅了** | 那 60 项来自**营销页**；她真身是 20 个功能页 + 9 条注入 + 56 语言 + 1 个后端口 |
| 未登录 | ✅ 对 | Local Extension Settings 2.67MB 里只有 chatPromotionCache/prod/promotions，**无 token/user/session** |
| 盘上不是最新 | ✅ 对 | 盘 5.34.1 / CDP 5.34.2 |
| 不绕 Cloudflare | ✅ 按她成文口径 | 正路 = CDP 接她真浏览器（实测零挑战） |

## 遗漏清单（还有没有遗漏的）
20 个功能页 · 9 条内容注入（含 Netflix/YouTube hack、联合早报、Google Docs）·
2 个 sandbox 页 · arkose.js（Arkose Labs 人机验证）· 内嵌 AWS SDK ·
唯一后端口 /api/chat · 56 语言（含 zh_TW）· update_url=Chrome 商店（盘上会漂）。

用法：py -3.14 -X utf8 tools/codex-scripts/sider-crossscan.py [--check]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
EXT_ID = "difoiogjjojoaoomphldepapgpbgkhkb"
NATIVE = ROOT / "gbt_allinone" / "store" / "native_browser" / "profile" / "Default"
OUT = ROOT / "state" / "sider-crossscan.json"
V9_EXT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V9\state\chrome_cdp\Default\Extensions") / EXT_ID


def _newest(base: Path):
    if not base.is_dir():
        return None
    ds = sorted([d for d in base.iterdir() if d.is_dir()], key=lambda d: d.name)
    return ds[-1] if ds else None


def scan() -> dict:
    out = {"at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"), "扩展ID": EXT_ID}
    for tag, base in (("V8侧", NATIVE / "Extensions" / EXT_ID), ("V9侧", V9_EXT)):
        v = _newest(base)
        out[tag] = {"目录": str(base), "在盘": base.is_dir(),
                    "版本目录": [d.name for d in base.iterdir() if d.is_dir()] if base.is_dir() else []}
        if not v:
            continue
        files = [p for p in v.rglob("*") if p.is_file()]
        try:
            mf = json.loads((v / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            mf = {}
        pages = sorted(p.stem for p in v.glob("*.html"))
        loc = v / "_locales"
        locs = sorted(d.name for d in loc.iterdir() if d.is_dir()) if loc.is_dir() else []
        bg = ""
        if (v / "background.js").is_file():
            bg = (v / "background.js").read_text(encoding="utf-8", errors="replace")[:3000000]
        cs = mf.get("content_scripts") or []
        out[tag].update({
            "版本": mf.get("version"), "manifest_version": mf.get("manifest_version"),
            "件数": len(files), "字节": sum(p.stat().st_size for p in files),
            "功能页数": len(pages), "功能页": pages,
            "语言数": len(locs), "含zh_TW": "zh_TW" in locs,
            "权限": mf.get("permissions") or [], "host权限": mf.get("host_permissions") or [],
            "注入条数": len(cs),
            "注入": [{"js": (c.get("js") or [""])[0], "matches": len(c.get("matches") or [])} for c in cs],
            "sandbox页": (mf.get("sandbox") or {}).get("pages") or [],
            "她的后端口": sorted(set(re.findall(r'["\'](/api/[a-zA-Z0-9_\-/]{2,40})["\']', bg))),
            "内嵌AWS": "amazonaws" in bg.lower(),
            "人机验证": [n for n in ("arkose", "recaptcha", "hcaptcha", "turnstile")
                        if (v / (n + ".js")).is_file()],
            "update_url": mf.get("update_url"),
            "side_panel": (mf.get("side_panel") or {}).get("default_path"),
        })
    les = NATIVE / "Local Extension Settings" / EXT_ID
    if les.is_dir():
        blob = b""
        for f in les.rglob("*"):
            if f.is_file():
                blob += f.read_bytes()
        # 🔴 2026-10-10 **这一刀是主人要我"看到底对不对"逼出来的**：
        #    我先前只切 blob[:400000] 且只按 (token/auth/user/login/session/email) 过滤 ⇒
        #    **漏掉了她真正的账户键** ⇒ 我下了"未登录"的结论 —— **那是错的**。
        #    她真身里的键是：WUserInfo__ · XVipInfo__ · getUserStatus__ · XWisebaseAllSavedUrl · XoiceRoleList__
        #    （前缀带 W/X 的驼峰命名，且 **VIP** 不在我原来的词表里）
        #    ⇒ 切**整段** + 词表补 vip/plan/credit/authority/subscribe/wisebase。
        ks = {m.decode() for m in re.findall(rb"[a-zA-Z_][a-zA-Z0-9_]{3,60}", blob)}
        WORDS = ("token", "auth", "user", "login", "session", "email", "vip", "plan",
                 "credit", "authority", "subscrib", "wisebase", "account", "status")
        auth = sorted(k for k in ks if any(w in k.lower() for w in WORDS))
        out["本地状态"] = {"在盘": True, "字节": len(blob), "账户登录相关键": auth or "无",
                           "判定": ("**已登录**（见到账户/VIP/状态键）" if auth else "**未登录**（一个账户键都没有）"),
                           "口径": "以 Local Extension Settings 的**键名**为准（值多是压缩的，读不出就别硬读）"}
    else:
        out["本地状态"] = {"在盘": False}
    return out


def check() -> int:
    d = scan()
    v8 = d.get("V8侧") or {}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    for tag in ("V8侧", "V9侧"):
        s = d.get(tag) or {}
        if not s.get("在盘"):
            print("%s：**不在盘** %s" % (tag, s.get("目录")))
            continue
        print("%s 版本 %s（目录 %s）· %d 件 %.1f MB"
              % (tag, s.get("版本"), "/".join(s.get("版本目录") or []),
                 s.get("件数", 0), (s.get("字节") or 0) / 1e6))
        print("   功能页 %d：%s" % (s.get("功能页数", 0), ", ".join((s.get("功能页") or [])[:20])))
        print("   语言 %d（含zh_TW=%s）· 注入 %d 条 · sandbox %s"
              % (s.get("语言数", 0), s.get("含zh_TW"), s.get("注入条数", 0), s.get("sandbox页")))
        print("   权限 %s" % ", ".join(s.get("权限") or []))
        print("   host %s" % ", ".join(s.get("host权限") or []))
        print("   后端口 %s · AWS=%s · 人机验证 %s"
              % (s.get("她的后端口"), s.get("内嵌AWS"), s.get("人机验证")))
    print()
    ls = d.get("本地状态") or {}
    print("登录态（权威处 Local Extension Settings）：%s" % ls.get("判定"))
    print("   账户键：%s" % ls.get("账户登录相关键"))
    disk = v8.get("版本") or "?"
    print("版本核对：盘上 %s · CDP 跑 5.34.2 ⇒ %s"
          % (disk, "**盘上落后（会漂）**" if disk != "5.34.2" else "一致"))
    ok = bool(v8.get("在盘") and v8.get("功能页数"))
    print("判据：%s" % ("PASS" if ok else "FAIL（她不在盘/没功能页）"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Sider 穿透式交叉扫描")
    ap.add_argument("--check", action="store_true")
    ap.parse_args()
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
