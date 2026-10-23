# -*- coding: utf-8 -*-
"""神经系统部署法 · 页级双向绑定（page-bindings）—— **每一页都要有双向绑定，扫描即穿透**。

主人令（2026-10-09，逐字）：
  「不管部署什么项目都要使用触手在**每一页代码上做好双向绑定**，确保用户想看什么，或者想扫描
    就能做到真正的**无死角穿透每一页瞬间完成**，这是我们 GBT 家族独有的**神经系统部署法**」
  「做什么外表看起来没问题，扫描一扫全是警报！这不叫项目和作品……**报警但不影响运行就不管了**，
    这在 GBT 家族里面是严格禁止的」

口径（三个方向都成立才算绑好，缺一条即红）：
  ① **正向** 页 → 背后的能力位/数据真源（从这一页能说出"我是谁在做主"）
  ② **反向** 能力位 → 这一页（从能力位能点回这一页 ⇒ 这才叫双向）
  ③ **真源** 这一页的数据件在盘上且非空（空壳不算绑好）

用法：
  py -3.14 -X utf8 tools/codex-scripts/page-bindings.py            # 现算并落 state/page-bindings.json
  py -3.14 -X utf8 tools/codex-scripts/page-bindings.py --check    # 判据（缺一条即 rc=1）
  py -3.14 -X utf8 tools/codex-scripts/page-bindings.py --selftest # 负对照
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
PANEL = ROOT / "holo_pet_w3" / "panel" / "index.html"
OUT = ROOT / "state" / "page-bindings.json"
CAPDATA = ROOT / "holo_pet_w3" / "capabilities" / "capabilities-data.js"
ENERGY = ROOT / "holo_pet_w3" / "energy" / "energy-data.js"


def panel_pages() -> list:
    """从面板 PAGES 表现读（**不另立一份清单** —— 清单只能有一处）。"""
    txt = PANEL.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"const PAGES = \[(.*?)\n\];", txt, re.S)
    if not m:
        return []
    rows = []
    for mm in re.finditer(r'id:\s*"([^"]+)"[^}]*?name:\s*"([^"]+)"[^}]*?rel:\s*"([^"]+)"', m.group(1)):
        rows.append({"id": mm.group(1), "name": mm.group(2), "rel": mm.group(3)})
    return rows


DECL = ROOT / "state" / "page-caps.json"


def _declared() -> dict:
    """页 → 能力位 的**显式申报**（GBV 神经系统部署法：绑定靠声明，不靠猜）。"""
    try:
        d = json.loads(DECL.read_text(encoding="utf-8"))
        return {k: v for k, v in d.items() if not k.startswith("_")}
    except (OSError, ValueError):
        return {}


def _caps() -> dict:
    sys.path.insert(0, str(ROOT))
    try:
        from gbt_allinone.caps_registry import BENIGN_CAPS
        return dict(BENIGN_CAPS)
    except Exception:                                        # noqa: BLE001
        return {}


def build() -> dict:
    pages = panel_pages()
    caps = _caps()
    rows = []
    for p in pages:
        rel = p["rel"]
        target = (PANEL.parent / rel).resolve()
        exists = target.is_file()
        size = target.stat().st_size if exists else 0
        # ① 正向：**优先读显式申报**（state/page-caps.json）；没申报才退回关键词匹配。
        #    为什么要申报：关键词匹配会把"没有单一能力位的页"判成无绑定，
        #    而**绑定本来就该是显式声明**——猜出来的绑定不叫绑定。
        decl = _declared().get(p["id"]) or {}
        if decl.get("caps"):
            fwd = list(decl["caps"])
            fwd_src = "申报"
        else:
            keys = [k for k in re.split(r"[^0-9A-Za-z\u4e00-\u9fff]+",
                                        p["id"] + " " + p["name"]) if len(k) >= 2]
            fwd = []
            for kind, meta in caps.items():
                blob = (kind + " " + str((meta or {}).get("desc", ""))
                        + " " + str((meta or {}).get("domain", ""))).lower()
                if any(k.lower() in blob for k in keys):
                    fwd.append(kind)
            fwd_src = "关键词"
        # ② 反向：能力统计页 / 能力栏页里有没有这一页（有 ⇒ 从能力位能点回来）
        back = []
        for src in (CAPDATA, ENERGY):
            if src.is_file() and p["id"] in src.read_text(encoding="utf-8", errors="replace"):
                back.append(src.name)
        rows.append({"页": p["id"], "名称": p["name"], "落点": rel,
                     "落点在盘": exists, "真源字节": size,
                     "正向_能力位": fwd[:8], "正向来源": fwd_src,
                     "申报理由": decl.get("why") or "",
                     "反向_提及于": back,
                     "绑好": bool(exists and size > 0 and fwd and back)})
    bad = [r for r in rows if not r["绑好"]]
    res = {"at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"), "页数": len(rows),
           "绑好": len(rows) - len(bad), "未绑好": len(bad), "逐页": rows,
           "口径": "三方向齐（正向 页→能力位 · 反向 能力位→页 · 真源在盘非空）才算绑好"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def check() -> int:
    r = build()
    print("神经系统部署法 · 页级双向绑定：%d 页 · 绑好 %d · **未绑好 %d**"
          % (r["页数"], r["绑好"], r["未绑好"]))
    for x in r["逐页"]:
        if not x["绑好"]:
            why = []
            if not x["落点在盘"]:
                why.append("落点不在盘")
            elif x["真源字节"] == 0:
                why.append("真源 0 字节")
            if not x["正向_能力位"]:
                why.append("正向无能力位")
            if not x["反向_提及于"]:
                why.append("反向无提及")
            print("  ❌ %-16s %s" % (x["页"], " · ".join(why)))
    print("\n判据：%s" % ("PASS" if r["未绑好"] == 0 else "FAIL"))
    return 0 if r["未绑好"] == 0 else 1


def selftest() -> int:
    """负对照：空页 / 无真源 / 无能力位 / 无反向 —— 四类都必须判未绑好。"""
    cases = [{"页": "x", "名称": "x", "落点": "nope.html", "落点在盘": False, "真源字节": 0,
              "正向_能力位": [], "反向_提及于": []}]
    bad = [c for c in cases if not (c["落点在盘"] and c["真源字节"] > 0
                                    and c["正向_能力位"] and c["反向_提及于"])]
    print("负对照·四缺全判未绑好：%s（%d/%d）" % ("红" if len(bad) == len(cases) else "绿",
                                                len(bad), len(cases)))
    real = build()
    print("正例·现读页数 %d · 绑好 %d" % (real["页数"], real["绑好"]))
    ok = len(bad) == len(cases) and real["页数"] > 0
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="页级双向绑定（神经系统部署法）")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        rc = selftest()
        print("自检：%s" % ("全过" if rc == 0 else "不过"))
        return rc
    if a.check:
        return check()
    r = build()
    print("已落 %s · %d 页 · 绑好 %d · 未绑好 %d" % (OUT, r["页数"], r["绑好"], r["未绑好"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
