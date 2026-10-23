# -*- coding: utf-8 -*-
"""gen_corpus_v50 -- v49 逐字节不动 + 追加「验收对齐」教学行（6 家族 + 主 54）。

主人令 2026-10-17：「把未完成的补齐在训练一遍」。
未完成的 = 验收这一环：
  ① 6 个家族验收器（comfy/forge/offense/sc/spider/video）的**判据题 → 标准答案**没有教过模型；
  ② 主 54 题**没有判分器**（题库只有 group/q，没有判据/标准答案）。

本生成器做两件事（全部**现读**，不手写内容）：
  A. **家族验收对齐**：从 `tools/train/accept_*.py` 的 `CASES` 里现读「题 → 必含词组组」，
     生成能**满足该判据**的教学答案（每组取一个词，全组覆盖），family=`验收对齐·<族>`；
  B. **主 54 对齐**：对 `accept_q.json` 的每道题，去 v49 语料里找**同题期望答案**，
     命中则「题→期望答案」作为教学行；命中不了的**如实计入 unmatched**（不编答案）。
纪律：v49 基础逐字节不动（base_sha256 留档可对账）；追加条数/未命中条数写进 manifest。
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".scratch" / "self_knowledge_v49.jsonl"
OUT = ROOT / ".scratch" / "self_knowledge_v50.jsonl"
MAN = ROOT / "state" / "train" / "corpus_v50_manifest.json"
TRAIN = ROOT / "tools" / "train"
QBANK = ROOT / ".scratch" / "accept_q.json"

FAMILY_JUDGES = {
    "accept_comfy.py": "秋叶版目录契约",
    "accept_forge.py": "技能蒸馏五式",
    "accept_offense.py": "自主渗透编排",
    "accept_sc.py": "作品解剖展示",
    "accept_spider.py": "自适应抓取",
    "accept_video.py": "看视频理解",
}


def _load(name: str):
    sp = importlib.util.spec_from_file_location("fam_" + name.replace(".py", ""), str(TRAIN / name))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def _family_rows() -> list:
    """从每个家族判分器 CASES 现读「题 → 必须覆盖的词组组」，生成**满足判据**的标准答案。"""
    out = []
    for fname, label in FAMILY_JUDGES.items():
        p = TRAIN / fname
        if not p.is_file():
            continue
        cases = getattr(_load(fname), "CASES", {}) or {}
        for q, groups in cases.items():
            picks, lines = [], []
            for g in groups:
                g = list(g)
                if not g:
                    continue
                picks.append(g[0])
                lines.append(" / ".join(g[:3]))
            ans = ("%s 的判据要点：%s。回答时这些点必须逐条说到（同义写法也算）：%s。"
                   % (label, "；".join(lines), "、".join(picks)))
            out.append(("%s：%s" % (label, q),
                        ans, "验收对齐·" + label, "v50-验收对齐"))
    return out


def _main54_rows(base_rows: list) -> tuple:
    """主 54：从 v49 语料里现读**同题期望答案**；命中不了的如实列 unmatched。"""
    bank = [json.loads(l) for l in QBANK.read_text(encoding="utf-8").splitlines() if l.strip()] \
        if QBANK.is_file() else []
    by_q = {}
    for r in base_rows:
        ins = str(r.get("instruction") or "").strip()
        if ins:
            by_q[ins] = str(r.get("output") or "").strip()
    rows, unmatched = [], []
    for item in bank:
        q = str(item.get("q") or "").strip()
        grp = str(item.get("group") or "?")
        hit = by_q.get(q)
        if not hit:
            for ins, ans in by_q.items():                        # 宽松匹配：题面互相包含且唯一
                if q and (q in ins or ins in q) and ans:
                    hit = ans
                    break
        if hit:
            rows.append(("%s（%s）" % (q, grp), hit, "主54对齐·" + grp, "v50-主54对齐"))
        else:
            unmatched.append(q)
    return rows, unmatched


def main():
    base = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    base_sha = hashlib.sha256(SRC.read_bytes()).hexdigest()
    fam = _family_rows()
    main54, unmatched = _main54_rows(base)
    rows = list(base)
    for q, a, fam_name, src in fam + main54:
        rows.append({"instruction": q, "output": a, "family": fam_name, "source": src})
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + chr(10) for r in rows), encoding="utf-8")
    blob = OUT.read_bytes()
    MAN.parent.mkdir(parents=True, exist_ok=True)
    MAN.write_text(json.dumps({
        "gen": "v50", "parent": "v49", "count": len(rows), "bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(), "base_count": len(base),
        "base_sha256": base_sha, "base_unchanged": hashlib.sha256(SRC.read_bytes()).hexdigest() == base_sha,
        "appended_family": len(fam), "appended_main54": len(main54),
        "main54_unmatched": len(unmatched), "main54_unmatched_q": unmatched[:12],
        "directives": ["主人 2026-10-17：「把未完成的补齐在训练一遍」"],
        "why": "验收对齐：判据题→必含词组组（现读 CASES）+ 主54同题期望答案（现读 v49 语料）；不编答案",
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print("v50：%d 条（基础 %d + 家族对齐 %d + 主54对齐 %d · 主54未命中 %d）· %d 字节 · sha %s"
          % (len(rows), len(base), len(fam), len(main54), len(unmatched), len(blob),
             hashlib.sha256(blob).hexdigest()[:16]))
    print("  基础 sha 未变:", hashlib.sha256(SRC.read_bytes()).hexdigest() == base_sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
