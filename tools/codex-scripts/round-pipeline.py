# -*- coding: utf-8 -*-
"""round-pipeline -- 三段闸：大脑计划 -> 镜像排练 -> 生产落实。"""
from __future__ import annotations
import argparse, glob, json, py_compile, re, subprocess, sys, time
from collections import Counter
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
RUNDIR = ROOT / "state" / "rounds"
FLOORS = {"域名册": 240, "节点名册": 180, "秋叶版契约": 120,
          "秋叶版规程": 96, "看视频理解": 300, "技能蒸馏五式": 150,
          "自主渗透编排": 260, "自适应抓取": 150, "作品解剖展示": 240,
          "AI90年压缩史": 96}


def sh(args, timeout=600):
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT), timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def seg1(round_name, intent):
    payload = json.dumps({"intent": intent, "round": round_name})
    rc, o = sh([PY, "-X", "utf8", "tools/codex-scripts/five-dim.py", "cap", "brain_route", payload, "--full"], 420)
    ok = "'status': 'ok'" in o or '"status": "ok"' in o
    doc = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "round": round_name, "intent": intent,
           "brain_route_rc": rc, "brain_ok": ok, "brain_readout": o[-1200:]}
    (RUNDIR / (round_name + "-plan.json")).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[段1 大脑计划] brain_route rc=%d ok=%s" % (rc, ok))
    return ok


def seg2(round_name, corpus, launcher):
    res = {}
    fams = Counter()
    if corpus and Path(corpus).is_file():
        for ln in Path(corpus).read_text(encoding="utf-8", errors="replace").splitlines():
            if not ln.strip():
                continue
            try:
                fams[json.loads(ln).get("family") or "?"] += 1
            except Exception:
                pass
    total = sum(fams.values()) or 1
    missing = [(k, fams.get(k, 0), v) for k, v in FLOORS.items() if fams.get(k, 0) < v]
    res["ratio"] = {"total": total, "families": len(fams), "below_floor": missing}
    print("[段2a 配比模拟] 总 %d 条 · 族 %d · 低于下限 %d" % (total, len(fams), len(missing)))
    for k, got, need in missing[:6]:
        print("     RED %s %d < 下限 %d" % (k, got, need))
    chain_ok, why = False, "未给 launcher"
    lp = Path(launcher) if launcher else None
    if lp and lp.is_file():
        try:
            py_compile.compile(str(lp), doraise=True)
            src = lp.read_text(encoding="utf-8", errors="replace")
            refs = re.findall(r"\.scratch/([A-Za-z0-9_\-]+\.(?:jsonl|py))", src)
            absent = sorted({r for r in refs if not (ROOT / ".scratch" / r).is_file()})
            badjoin = "; &&" in src
            chain_ok = (not absent) and (not badjoin)
            why = ("引用缺件 " + ",".join(absent[:3])) if absent else ("链含非法 ; &&" if badjoin else "编译 OK · 引用件齐")
        except Exception as e:
            why = "编译失败 " + str(e)[:80]
    res["chain"] = {"ok": chain_ok, "why": why}
    print("[段2b 链干跑] %s %s" % ("OK " if chain_ok else "RED", why))
    jr = []
    allj = sorted(glob.glob(str(ROOT / "tools" / "train" / "accept_*.py")))
    for j in [x for x in allj if Path(x).name != "accept_infer.py"]:
        rc, _ = sh([PY, "-X", "utf8", j, "--help"], 120)
        jr.append({"judge": Path(j).name, "runnable": rc == 0})
    res["judges"] = jr
    res["runners_skipped"] = [Path(x).name for x in allj if Path(x).name == "accept_infer.py"]
    print("[段2c 判据预演] %d 份 可跑 %d" % (len(jr), sum(1 for x in jr if x["runnable"])))
    uq_ok, uq_out = True, ""
    if corpus and Path(corpus).is_file():
        rc, o = sh([PY, "-X", "utf8", "tools/train/check_instruction_unique.py", "--corpus", corpus], 300)
        uq_ok = rc == 0
        lu = [x for x in o.splitlines() if "唯一性" in x]
        uq_out = lu[0] if lu else ""
    res["unique"] = {"ok": uq_ok, "readout": uq_out}
    # 2e 语义唯一（近义题面聚类）
    sq_ok, sq_out = True, ""
    if corpus and Path(corpus).is_file():
        rc, o = sh([PY, "-X", "utf8", "tools/train/check_family_binding.py", "--corpus", corpus], 300)
        sq_ok = rc == 0
        ls = [x for x in o.splitlines() if "语义聚类" in x]
        sq_out = ls[0] if ls else ""
    res["semantic"] = {"ok": sq_ok, "readout": sq_out}
    print("[段2e 语义唯一] %s %s" % ("OK " if sq_ok else "RED", sq_out))
    print("[段2d 题面唯一] %s %s" % ("OK " if uq_ok else "RED", uq_out))
    ok = (not missing) and chain_ok and all(x["runnable"] for x in jr) and uq_ok and sq_ok
    res["ok"] = ok
    (RUNDIR / (round_name + "-rehearsal.json")).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return ok


def seg3(round_name, ok1, ok2, landing):
    allowed = ok1 and ok2
    doc = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "round": round_name, "seg1_brain": ok1, "seg2_mirror": ok2,
           "allowed_to_land": allowed, "landing": (landing if allowed else "blocked")}
    (RUNDIR / (round_name + "-landing.json")).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("[段3 生产闸] 大脑=%s 镜像=%s ⇒ %s" % (ok1, ok2, "允许点火" if allowed else "不允许点火"))
    return allowed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("round")
    ap.add_argument("--intent", default="训练一炉：语料配比→训练→多份推理→八道门")
    ap.add_argument("--corpus", default="")
    ap.add_argument("--launcher", default="")
    ap.add_argument("--landing", default="production")
    a = ap.parse_args()
    RUNDIR.mkdir(parents=True, exist_ok=True)
    ok1 = seg1(a.round, a.intent)
    ok2 = seg2(a.round, a.corpus, a.launcher)
    return 0 if seg3(a.round, ok1, ok2, a.landing) else 1


if __name__ == "__main__":
    raise SystemExit(main())
