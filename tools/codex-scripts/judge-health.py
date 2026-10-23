# -*- coding: utf-8 -*-
"""judge-health -- 判据健康度：一眼分清「是她没练到」还是「我判据太死」。

per 判据报三件：
  1. 最近一轮得分（真跑该判据 × 最新答案件）
  2. 翻正次数（读 state/judge-corrections.jsonl 的固定标记 [JUDGE-FIX]）
  3. 翻正前后的差值 + 原因
判定：若某判据当前满分且有翻正记录 ⇒ 标「曾误判」（不是她没练到）。
用法：py -3.14 tools/codex-scripts/judge-health.py
"""
from __future__ import annotations
import glob, json, re, subprocess, sys
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
LEDGER = ROOT / "state" / "judge-corrections.jsonl"
JUDGES = [
    ("看视频理解", "tools/train/accept_video.py", ["video_a4*.jsonl", "video_a3*.jsonl"]),
    ("技能蒸馏五式", "tools/train/accept_forge.py", ["forge_a4*.jsonl", "forge_a3*.jsonl"]),
    ("自主渗透编排", "tools/train/accept_offense.py", ["offense_a4*.jsonl", "offense_a3*.jsonl"]),
    ("自适应抓取", "tools/train/accept_spider.py", ["spider_a4*.jsonl", "spider_a3*.jsonl"]),
    ("作品解剖展示", None, []),
    ("秋叶版能力", "tools/train/accept_comfy.py", ["comfy_a4*.jsonl", "comfy_a3*.jsonl"]),
]


def newest(pats):
    for pat in pats:
        hits = sorted(glob.glob(str(ROOT / ".scratch" / pat)))
        if hits:
            return hits[-1]
    return ""


def score(script, ans):
    if not script or not ans:
        return ""
    p = subprocess.run([PY, "-X", "utf8", str(ROOT / script), "--answers", ans], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
    for ln in (p.stdout or "").splitlines():
        if ln.startswith("=="):
            return ln.strip("= ").strip()
    return ""


def fixes():
    out = {}
    if LEDGER.is_file():
        for ln in LEDGER.read_text(encoding="utf-8").splitlines():
            if "[JUDGE-FIX]" not in ln:
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue
            out.setdefault(d.get("judge", "?"), []).append(d)
    return out


def main():
    fx = fixes()
    print("判据健康度（" + ("\u542b\u7ffb\u6b63" if fx else "\u65e0\u7ffb\u6b63\u8bb0\u5f55") + "）")
    print("  %-14s %-22s %-8s %s" % ("判据", "最近一轮得分", "翻正", "翻正前后 / 原因"))
    total_fix = 0
    misjudged = []
    for name, script, pats in JUDGES:
        ans = newest(pats)
        sc = score(script, ans)
        base = (script or "").split("/")[-1].replace(".py", "")
        f = fx.get(base, [])
        total_fix += len(f)
        detail = "; ".join("%s -> %s" % (x.get("before"), x.get("after")) for x in f) or "-"
        why = (f[-1].get("why", "")[:52] if f else "")
        print("  %-14s %-22s %-8d %s" % (name, (sc or "(无答案件)")[:22], len(f), detail + (" | " + why if why else "")))
        if f and sc and re.search(r"(\d+)/\1", sc.split("：")[-1].strip() if "：" in sc else ""):
            misjudged.append(name)
    print("  合计翻正 %d 次" % total_fix)
    if misjudged:
        print("  ⚠ 曾误判（当前满分且有翻正）：" + "、".join(misjudged))
    print("  口径：分母满分 + 有翻正 ⇒ 是**判据太死**；无翻正且未满分 ⇒ 是**没练到**（去加固语料）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
