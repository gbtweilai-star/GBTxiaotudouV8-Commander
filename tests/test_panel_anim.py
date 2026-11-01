# -*- coding: utf-8 -*-
"""界面动效判据（2026-11-01 更新：旧 28 面板已归档，现役是认知界面控制台）。

跑法：python tests/test_panel_anim.py
"""
from __future__ import annotations

import os
import pathlib
import sys

ROOT = pathlib.Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(ROOT))

FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)[:200]))
    if not cond:
        FAILED.append(name)


def main() -> int:
    print("[1] 现役控制台：CSS 入场动画（不依赖 rAF）")
    css = (ROOT / "holo_pet_w3" / "console" / "app.css").read_text(encoding="utf-8")
    check("有 @keyframes rise", "@keyframes rise" in css)
    check("三栏都有入场", css.count("animation: rise") >= 3, css.count("animation: rise"))
    check("尊重 reduced-motion", "prefers-reduced-motion" in css)

    print("[2] 旧动效资产保留（归档页/将来可复用）")
    gsap = ROOT / "holo_pet_w3" / "assets" / "gsap.min.js"
    anim = ROOT / "holo_pet_w3" / "assets" / "panel-anim.js"
    check("gsap.min.js 在位且 >60KB", gsap.is_file() and gsap.stat().st_size > 60000,
          gsap.stat().st_size if gsap.is_file() else 0)
    check("panel-anim.js 在位", anim.is_file())
    js = anim.read_text(encoding="utf-8") if anim.is_file() else ""
    check("panel-anim 仍尊重 reduced-motion", "prefers-reduced-motion" in js)
    check("panel-anim 失败如实标", 'dataset.anim = "failed"' in js)

    print("[3] 旧面板已归档（不再直接对外）")
    arch = ROOT / ".archive" / "panels-20261101"
    check("归档目录存在", arch.is_dir())
    check("panel 已归档", (arch / "panel").is_dir())
    check("现役 w3 无旧面板目录", not (ROOT / "holo_pet_w3" / "panel").exists())

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 控制台 CSS 入场、旧动效资产保留、旧面板已归档")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
