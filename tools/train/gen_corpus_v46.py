# -*- coding: utf-8 -*-
"""gen_corpus_v46 -- 以 v43 为底：只改答案（不动题面），对**全部撞名签名**的行统一绑族名与位名。"""
from __future__ import annotations
import collections, hashlib, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".scratch" / "self_knowledge_v43.jsonl"
OUT = ROOT / ".scratch" / "self_knowledge_v46.jsonl"
MAN = ROOT / "state" / "train" / "corpus_v46_manifest.json"
CAP_OF = {"自主渗透编排": "offense_ops", "自适应抓取": "spider_ops",
          "作品解剖展示": "showcase_ops", "技能蒸馏五式": "skill_forge",
          "看视频理解": "video_intel", "节点即触手": "forge_mastery",
          "工作流十式": "workflow_forge"}


def sig(q):
    s = re.sub(r"^【[^】]*】", "", (q or "").strip())
    return re.sub(r"[^0-9A-Za-z一-鿿]", "", s)[:24]


def main():
    rows = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    by = collections.defaultdict(set)
    for r in rows:
        by[sig(r.get("instruction") or "")].add(r.get("family") or "?")
    collide = {k for k, v in by.items() if len(v) > 1}
    n = 0
    for r in rows:
        if sig(r.get("instruction") or "") not in collide:
            continue
        fam = r.get("family") or "?"
        cap = CAP_OF.get(fam)
        out = r.get("output") or ""
        out = re.sub(r"族＝[^；]*；", "", out)
        out = re.sub(r"位＝[^；]*；", "", out)
        out = re.sub(r"走唯一门 five-dim\.py cap [a-z_]+：", "", out)
        out = re.sub(r"走 cap [a-z_]+：", "", out)
        head = "族＝" + fam + "；位＝" + (cap or "（本族无专属位）") + "；"
        if cap:
            head += "走唯一门 five-dim.py cap " + cap + "："
        r["output"] = head + out
        n += 1
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + chr(10) for r in rows), encoding="utf-8")
    blob = OUT.read_bytes()
    MAN.write_text(json.dumps({"gen": "v46", "parent": "v43", "count": len(rows), "bytes": len(blob),
                               "sha256": hashlib.sha256(blob).hexdigest(),
                               "fix": {"撞名签名组": len(collide), "答案层绑定": n,
                                       "题面未动": True}}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("v46：%d 条 · %d 字节 · sha %s" % (len(rows), len(blob), hashlib.sha256(blob).hexdigest()[:16]))
    print("  撞名签名组 %d · 答案层绑定 %d 条" % (len(collide), n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
