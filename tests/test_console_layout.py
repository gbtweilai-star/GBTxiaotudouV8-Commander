# -*- coding: utf-8 -*-
"""控制台布局验收：PAGE MESH HUD 必须在布局槽里，不许浮到右栏/身体控制上。"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OK = 0
FAIL = []


def check(name, cond, got=None):
    global OK
    if cond:
        OK += 1
        print("  ok  ", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, "|", repr(got)[:160])


def main() -> int:
    idx = (ROOT / "holo_pet_w3/console/index.html").read_text(encoding="utf-8")
    js = (ROOT / "holo_pet_w3/console/page-mesh.js").read_text(encoding="utf-8")
    css = (ROOT / "holo_pet_w3/console/app.css").read_text(encoding="utf-8")
    check("有 HUD 布局槽", 'id="mesh-hud-slot"' in idx)
    check("JS 优先塞槽", 'getElementById("mesh-hud-slot")' in js and "slot.appendChild(hud)" in js)
    check("HUD 不再 fixed 浮层", "position: static" in css and "#page-mesh-hud" in css)
    # 旧写法若回来：fixed right/bottom 同一条规则
    import re
    m = re.search(r"#page-mesh-hud\s*\{([^}]*)\}", css, re.S)
    block = m.group(1) if m else ""
    check("HUD 规则无 fixed", "position: fixed" not in block, block[:100])
    check("HUD 规则无 bottom/right 像素浮位", not __import__("re").search(r"(?:bottom|right)\s*:\s*\d", block), block[:100])
    check("槽在 tabs 之后", idx.find('id="mesh-hud-slot"') > idx.find('class="view-tabs"'))
    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— PAGE MESH 进入布局槽，不再压住右栏身体控制")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
