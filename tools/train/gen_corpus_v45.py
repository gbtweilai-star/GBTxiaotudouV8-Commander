# -*- coding: utf-8 -*-
"""gen_corpus_v45 -- 从根上分开命令类同型题：题面与答案主体都换成“位名+族名同句”。"""
from __future__ import annotations
import hashlib, json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".scratch" / "self_knowledge_v44.jsonl"
OUT = ROOT / ".scratch" / "self_knowledge_v45.jsonl"
MAN = ROOT / "state" / "train" / "corpus_v45_manifest.json"
CAP_OF = {"自主渗透编排": "offense_ops", "自适应抓取": "spider_ops",
          "作品解剖展示": "showcase_ops", "技能蒸馏五式": "skill_forge",
          "看视频理解": "video_intel", "节点即触手": "forge_mastery",
          "工作流十式": "workflow_forge"}


def main():
    rows = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    n_q = n_a = 0
    for r in rows:
        fam = r.get("family") or ""
        if fam not in CAP_OF:
            continue
        cap = CAP_OF[fam]
        q = r.get("instruction") or ""
        if "命令" in q or "怎么调" in q:
            r["instruction"] = "【" + fam + "】" + cap + " 这一位怎么调用？（答案里必须同时出现族名与位名）"
            out = r.get("output") or ""
            import re as _re
            out = _re.sub(r"走唯一门 five-dim\.py cap [a-z_]+：", "", out)
            out = _re.sub(r"走 cap [a-z_]+：", "", out)
            out = _re.sub(r"族＝[^；]*；位＝[a-z_]+；", "", out)
            r["output"] = "族＝" + fam + "；位＝" + cap + "；走唯一门 five-dim.py cap " + cap + "：" + out
            n_q += 1
            n_a += 1
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + chr(10) for r in rows), encoding="utf-8")
    blob = OUT.read_bytes()
    fams = Counter(r.get("family") or "?" for r in rows)
    MAN.write_text(json.dumps({"gen": "v45", "parent": "v44", "count": len(rows), "bytes": len(blob),
                               "sha256": hashlib.sha256(blob).hexdigest(),
                               "fix": {"题面与答案同句绑定": n_q},
                               "families": dict(fams.most_common(10))}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("v45：%d 条 · %d 字节 · sha %s" % (len(rows), len(blob), hashlib.sha256(blob).hexdigest()[:16]))
    print("  修：题面与答案同句绑定 %d 条" % n_q)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
