# -*- coding: utf-8 -*-
"""gen_corpus_v48 -- v43 **逐字节不动** + 追加新行（族专属问法 + 族名位名同句答案）。
依据：v45/v46/v47 三次实测，凡"改写既有行"都掉分 ⇒ 改走"只加不改"。"""
from __future__ import annotations
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".scratch" / "self_knowledge_v43.jsonl"
OUT = ROOT / ".scratch" / "self_knowledge_v48.jsonl"
MAN = ROOT / "state" / "train" / "corpus_v48_manifest.json"

FAM = [
    ("自主渗透编排", "offense_ops", "渗透链编排", "pentagi 蒸馏五道闸"),
    ("自适应抓取", "spider_ops", "自主抓取", "Scrapling 七步 + robots 边界"),
    ("作品解剖展示", "showcase_ops", "作品读数", "anatomy 八步 + 读数同源"),
    ("技能蒸馏五式", "skill_forge", "五式蒸馏", "女娃/last30days/同事/前任/反蒸馏"),
    ("看视频理解", "video_intel", "看片", "ffprobe+ffmpeg 抽帧抽音 + 语义车道"),
    ("节点即触手", "forge_mastery", "节点开工", "N=3 无限递归 + 专业生产"),
    ("工作流十式", "workflow_forge", "流水线", "skills.sh TOP10 十式"),
]
PAT = [
    "{cap} 这一位要怎么叫起来？",
    "想用 {cap} 干活，第一步该敲什么？",
    "{fam} 这一族靠哪个能力位？",
    "{cap} 跑错了怎么办？",
    "{name} 这件事交给谁？",
    "{cap} 能做什么、不能做什么？",
    "{name} 的验收看什么？",
    "为什么要单独给 {cap} 开一个位？",
]


def main():
    base = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    base_bytes = SRC.read_bytes()
    rows = list(base)
    added = 0
    for fam, cap, name, detail in FAM:
        for p in PAT:
            q = p.format(cap=cap, fam=fam, name=name)
            out = ("族＝" + fam + "；位＝" + cap + "；"
                   + "走唯一门 five-dim.py cap " + cap + "："
                   + name + "；" + detail + "；只走这一个位，不拆成别族的动作。")
            rows.append({"instruction": q, "output": out, "family": fam, "source": "v48-追加"})
            added += 1
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + chr(10) for r in rows), encoding="utf-8")
    blob = OUT.read_bytes()
    MAN.write_text(json.dumps({"gen": "v48", "parent": "v43", "count": len(rows), "bytes": len(blob),
                              "sha256": hashlib.sha256(blob).hexdigest(),
                              "base_count": len(base), "base_sha256": hashlib.sha256(base_bytes).hexdigest(),
                              "appended": added, "fix": {"只加不改": True, "族专属问法": added}},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print("v48：%d 条（基础 %d + 追加 %d）· %d 字节 · sha %s"
          % (len(rows), len(base), added, len(blob), hashlib.sha256(blob).hexdigest()[:16]))
    print("  基础 sha256 未变: %s" % (hashlib.sha256(base_bytes).hexdigest() == hashlib.sha256(SRC.read_bytes()).hexdigest()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
