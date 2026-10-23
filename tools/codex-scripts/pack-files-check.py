# -*- coding: utf-8 -*-
"""打包白名单判据（pack-files-check）—— **新增页不许漏出安装包**。

主人截图暴露的真故障（2026-10-10）：上帝视角读到的是**旧打包件**（dist 打于 10-08），
我这两天新建的页（god_view / ai-board / vision_loop）**一样都没进包**。
其中 ai-board 的漏法很典型：electron-builder 的 `build.files` 是**手工列目录**的白名单
（"只打壳自己 + 它真要读的东西"），**新建一页就要人肉补一行** ⇒ 迟早漏。

判据：
  · 面板 PAGES 里凡是落在 `holo_pet_w3/` 下的页，其**目录**必须被 `build.files` 覆盖；
  · 落在别处（holo_pet/assets/**）的页**不判** —— 那些由面板桥运行时读仓，本就不进包。
负对照：造一个"盘上有页、白名单里没有"的目录 ⇒ 必须判红。
用法：py -3.14 -X utf8 tools/codex-scripts/pack-files-check.py [--selftest]
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
H = ROOT / "holo_pet_w3"
PANEL = H / "panel" / "index.html"
SUF = "/" + chr(42) * 2 + "/" + chr(42)


def _listed() -> set:
    pkg = json.loads((H / "package.json").read_text(encoding="utf-8"))
    return {f.split("/")[0] for f in pkg["build"]["files"] if f.endswith(SUF)}


def _pages_under_shell() -> set:
    """面板 PAGES 里落在 holo_pet_w3/ 下的页 → 它们的顶层目录名。"""
    txt = PANEL.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"const PAGES = \[(.*?)\n\];", txt, re.S)
    out = set()
    if not m:
        return out
    for mm in re.finditer(r'rel:\s*"([^"]+)"', m.group(1)):
        rel = mm.group(1)
        if not rel.startswith("..") or rel.startswith("../../"):
            continue                       # ../../ 是仓里别处（面板桥读），不进包
        seg = rel.lstrip("./").split("/")[0]
        if seg and seg != "..":
            out.add(seg)
    return out


def check(listed=None) -> dict:
    listed = _listed() if listed is None else listed
    pages = _pages_under_shell()
    bad, ok = [], []
    for d in sorted(pages):
        p = H / d
        if not p.is_dir():
            continue
        (ok if d in listed else bad).append(d)
    return {"ok": not bad, "白名单目录": len(listed), "壳内页目录": sorted(pages),
            "已覆盖": ok, "漏出包": bad}


def main() -> int:
    ap = argparse.ArgumentParser(description="打包白名单判据")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        r = check(listed={"panel"})       # 只给 panel ⇒ 其它壳内页必被判漏
        red = bool(r["漏出包"])
        print("负对照·白名单只给 panel ⇒ 漏出包 %d 个（必须 >0）：%s" % (len(r["漏出包"]), r["漏出包"][:6]))
        real = check()
        print("正例·现读壳内页 %d 个 · 漏出包 %d 个" % (len(real["壳内页目录"]), len(real["漏出包"])))
        ok = red and real["ok"]
        print("自检：%s" % ("全过" if ok else "不过"))
        return 0 if ok else 1
    r = check()
    print("打包白名单：白名单 %d 目录 · 壳内页 %d 个 · **漏出包 %d**"
          % (r["白名单目录"], len(r["壳内页目录"]), len(r["漏出包"])))
    for d in r["漏出包"]:
        print("  ❌ %s 在盘上但不在 build.files 白名单里 ⇒ 装出来的包看不到它" % d)
    print("判据：%s" % ("PASS" if r["ok"] else "FAIL"))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
