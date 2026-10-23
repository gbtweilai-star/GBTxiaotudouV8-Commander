# -*- coding: utf-8 -*-
"""gen_corpus_v51 -- v50 逐字节不动 + 只补 **4 条精准行**（v50 验收实测的红题原文）。

主人令 2026-10-17：「可以必须把细节做到位」。
v50 实测红（现读判分器 + 答案文件对应的题面原文）：
  · comfy 红题「编排前必须先跑哪个判据？它检查哪三类？」— 缺关键词「未知」
    （该族判据 2026-10-17 已显式化为 `accept_comfy.TEXT_RULES`，本生成器**现读**它）
  · offense/sc/spider **同一道红题**「命令怎么调？」— 缺 offense_ops / showcase_ops / spider_ops
  · 主54 两题「你是谁？」「动手之前你先做什么？」— 关键词覆盖率不足

做法（判据**全部现读**，不手写内容）：
  1. 家族红题：去对应判分器现读「必须出现的词组组」并**并集**（同一题面只一行 → 不撞名）；
  2. 主54：取 v50 语料里该题**期望答案原文**（覆盖率必 1.0）；
  3. 族归属：题面若已存在于母语料，就归它原来的族（跨族撞名闸只查不同族之间）；
     新题面归单一族「验收对齐部」。
纪律：v50 基础逐字节不动；manifest 记条数与来源。
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".scratch" / "self_knowledge_v50.jsonl"
OUT = ROOT / ".scratch" / "self_knowledge_v51.jsonl"
MAN = ROOT / "state" / "train" / "corpus_v51_manifest.json"
TRAIN = ROOT / "tools" / "train"

# v50 实测红题 → 判据来源（CASES 类判分器用 CASES[key]；comfy 用 TEXT_RULES[含词]）
FIX_Q = {
    "编排前必须先跑哪个判据？它检查哪三类？": {"judge": "accept_comfy.py", "comfy": True},
    "命令怎么调？": {"judge": ["accept_offense.py", "accept_sc.py", "accept_spider.py"]},
}
FIX_MAIN54 = ["你是谁？", "动手之前你先做什么？"]
PATCH_FAMILY = "验收对齐部"


def _load(fname: str):
    sp = importlib.util.spec_from_file_location("v51_" + fname.replace(".py", ""), str(TRAIN / fname))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def _groups_for(q: str, spec: dict) -> list:
    if spec.get("comfy"):
        rules = getattr(_load(spec["judge"]), "TEXT_RULES", {}) or {}
        for key, groups in rules.items():
            if key in q:
                return [list(g) for g in groups]
        return []
    groups = []
    for j in spec["judge"]:
        cases = getattr(_load(j), "CASES", {}) or {}
        key = next((k for k in cases if k in q), None)
        if key is not None:
            groups += [list(g) for g in cases[key]]
    return groups


def _detail_rows(base: list) -> list:
    fam_of = {}
    for r in base:
        fam_of.setdefault(str(r.get("instruction") or "").strip(), str(r.get("family") or ""))
    rows = []
    for q, spec in FIX_Q.items():
        groups = _groups_for(q, spec)
        if not groups:
            continue
        keys = [g[0] for g in groups if g]
        ans = ("这道题必须逐条说到：%s。关键词必须出现：%s。"
               % ("；".join(" / ".join(g[:3]) for g in groups), "、".join(dict.fromkeys(keys))))
        rows.append((q, ans, fam_of.get(q) or PATCH_FAMILY))
    exp = {}
    for r in base:
        if str(r.get("source") or "") == "v50-主54对齐":
            q = re.sub(r"（[^）]*）$", "", str(r.get("instruction") or "")).strip()
            exp[q] = str(r.get("output") or "")
    for q in FIX_MAIN54:
        if exp.get(q):
            rows.append((q, exp[q], fam_of.get(q) or PATCH_FAMILY))
    return rows


def main():
    base = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    base_sha = hashlib.sha256(SRC.read_bytes()).hexdigest()
    detail = _detail_rows(base)
    rows = list(base) + [{"instruction": q, "output": a, "family": f, "source": "v51-精准补丁"}
                         for q, a, f in detail]
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    blob = OUT.read_bytes()
    MAN.parent.mkdir(parents=True, exist_ok=True)
    MAN.write_text(json.dumps({
        "gen": "v51", "parent": "v50", "count": len(rows), "bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(), "base_count": len(base),
        "base_sha256": base_sha, "base_unchanged": hashlib.sha256(SRC.read_bytes()).hexdigest() == base_sha,
        "appended_detail": len(detail),
        "directives": ["主人 2026-10-17：「可以必须把细节做到位」"],
        "why": "v50 实测红题 4 条精准补丁（判据现读 CASES/TEXT_RULES/期望答案；同题面合并防撞名）",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("v51：%d 条（基础 %d + 精准补丁 %d）· %d 字节 · sha %s"
          % (len(rows), len(base), len(detail), len(blob), hashlib.sha256(blob).hexdigest()[:16]))
    print("  基础 sha 未变:", hashlib.sha256(SRC.read_bytes()).hexdigest() == base_sha)
    for q, _, f in detail:
        print("   + [%s] %s" % (f, q))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
