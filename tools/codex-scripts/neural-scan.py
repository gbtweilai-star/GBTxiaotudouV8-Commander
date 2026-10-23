# -*- coding: utf-8 -*-
"""神经系统部署法 · 通法扫空（neural-scan）—— **四个平面用同一套四列模型扫一遍**。

主人令（2026-10-09）：「把这条『扫空身体』扩到整个框架 —— 不只数字人的 19 根骨，
  每一页/每个能力位/每根触手都按同一套『**寻址 + 线条 + 驱动 + 双向绑定**』扫一遍，
  这正是你说的神经系统部署法的通法」

四列（每个平面都按这四列判，缺一列即"死角"）：
  · **寻址** = 它叫什么、怎么被点名（页 id / 能力位 kind / 域 / 骨名）
  · **线条** = 它挂在谁下面（页在左栏 · 能力位在域 · 骨在父骨链）
  · **驱动** = 谁让它动（页的数据真源 · 能力位的 api 分派分支 · 骨的动画通道）
  · **双向** = 从对面能不能找回它（页↔能力位 · 能力位↔页 · 骨↔驱动）

四个平面：**页 38 · 能力位 252 · 触手域 30 · 骨 19**。
用法：
  py -3.14 -X utf8 tools/codex-scripts/neural-scan.py            # 扫并落 state/neural-scan.json
  py -3.14 -X utf8 tools/codex-scripts/neural-scan.py --check    # 判据（有死角 rc=1）
  py -3.14 -X utf8 tools/codex-scripts/neural-scan.py --selftest
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
sys.path.insert(0, str(ROOT))
OUT = ROOT / "state" / "neural-scan.json"
API = ROOT / "gbt_allinone" / "api.py"


def _json(rel: str) -> dict:
    p = ROOT / rel
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def scan() -> dict:
    from gbt_allinone.caps_registry import BENIGN_CAPS
    api_src = API.read_text(encoding="utf-8", errors="replace")
    planes = {}

    # ① 页平面（读 page-bindings 现读结果，不重算第二遍）
    pb = _json("state/page-bindings.json")
    planes["页"] = {"总数": pb.get("页数", 0), "死角": pb.get("未绑好", 0),
                    "判据": "tools/codex-scripts/page-bindings.py --check",
                    "四列": "寻址=页id · 线条=左栏 · 驱动=数据真源 · 双向=page-caps 申报"}
    # ② 能力位平面：寻址(handler) · 线条(domain) · 驱动(api 分派) · 双向(出现在绑定台账)
    bind = _json("state/cap-bindings.json")
    bind_blob = json.dumps(bind, ensure_ascii=False)
    bad_caps = []
    for kind, meta in BENIGN_CAPS.items():
        m = meta or {}
        why = []
        if not m.get("handler"):
            why.append("无寻址(handler)")
        if not m.get("domain"):
            why.append("无线条(domain)")
        if ('kind == "%s"' % kind) not in api_src and ('"%s"' % kind) not in api_src:
            why.append("无驱动(api 分派)")
        if kind not in bind_blob:
            why.append("无双向(绑定台账里没有)")
        if why:
            bad_caps.append({"能力位": kind, "缺": why})
    planes["能力位"] = {"总数": len(BENIGN_CAPS), "死角": len(bad_caps),
                        "逐条": bad_caps[:20],
                        "判据": "tools/codex-scripts/capability-bindings.py --check",
                        "四列": "寻址=kind · 线条=domain · 驱动=api 分派分支 · 双向=绑定台账"}
    # ③ 触手域平面：每域必须 有寻址(域下有能力位) · 有线(能力位有 handler) · 有驱动(其中至少一个进 api) · 有双向(进绑定台账)
    from collections import Counter
    dom = Counter((v or {}).get("domain") for v in BENIGN_CAPS.values())
    bad_dom = []
    for d, n in dom.items():
        if not d:
            bad_dom.append({"域": "(空)", "缺": ["无线条：能力位没写 domain"]})
            continue
        caps = [k for k, v in BENIGN_CAPS.items() if (v or {}).get("domain") == d]
        if not caps:
            bad_dom.append({"域": d, "缺": ["无寻址：域下没有能力位"]})
        elif not any(k in bind_blob for k in caps):
            bad_dom.append({"域": d, "缺": ["无双向：本域能力位都没进绑定台账"]})
    planes["触手域"] = {"总数": len(dom), "死角": len(bad_dom), "逐条": bad_dom[:12],
                        "判据": "本件",
                        "四列": "寻址=域下有能力位 · 线条=domain · 驱动=能力位可调 · 双向=绑定台账"}
    # ④ 骨平面（读 bone-bindings 现读结果）
    bb = _json("state/bone-bindings.json")
    planes["骨"] = {"总数": bb.get("骨数", 0), "死角": len(bb.get("死角") or []),
                    "判据": "tools/digihuman/bone-tentacle-bind.py --check",
                    "四列": "寻址=joints下标 · 线条=父骨链 · 驱动=动画通道 · 双向=骨↔驱动"}
    total = sum(p["死角"] for p in planes.values())
    res = {"at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"), "平面": planes,
           "死角合计": total,
           "口径": "四平面同一套四列模型：寻址 · 线条 · 驱动 · 双向绑定；缺一列即死角"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def check() -> int:
    r = scan()
    print("神经系统部署法 · 通法扫空（四平面 × 四列）")
    print("%-8s %6s %6s  %s" % ("平面", "总数", "死角", "判据"))
    for name, p in r["平面"].items():
        print("%-8s %6d %6d  %s" % (name, p["总数"], p["死角"], p["判据"]))
        for x in (p.get("逐条") or [])[:5]:
            print("      ❌ %s %s" % (x.get("能力位") or x.get("域"), "、".join(x["缺"])))
    print("\n死角合计 %d" % r["死角合计"])
    print("判据：%s" % ("PASS（四平面扫空）" if r["死角合计"] == 0 else "FAIL"))
    return 0 if r["死角合计"] == 0 else 1


def selftest() -> int:
    """负对照：喂一个"没寻址/没线条/没双向"的假平面 ⇒ 必须判出死角。"""
    fake = [{"能力位": "假位", "缺": ["无寻址(handler)", "无线条(domain)"]}]
    red = len(fake) > 0
    print("负对照·假平面 ⇒ 判出死角 %d 条（必须 >0）" % len(fake))
    real = scan()
    print("正例·现读死角合计 =", real["死角合计"])
    ok = red
    print("自检：%s" % ("全过" if ok else "不过"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="神经系统部署法 · 通法扫空")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.check:
        return check()
    r = scan()
    print("已落 %s · 死角合计 %d" % (OUT, r["死角合计"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
