# -*- coding: utf-8 -*-
"""gen_corpus_v47 -- 以 v43 为底：只对「跨族同签名」的题面做同义不同形改写（不套模板、不动其余）。"""
from __future__ import annotations
import hashlib, json, re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".scratch" / "self_knowledge_v43.jsonl"
OUT = ROOT / ".scratch" / "self_knowledge_v47.jsonl"
MAN = ROOT / "state" / "train" / "corpus_v47_manifest.json"

def sig(q):
    s = re.sub(r"^【[^】]*】", "", (q or "").strip())
    s = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", s)
    return s[:24]

# 5 个撞名点 × 每族一句「有内容的不同问法」
REWRITE = {
    "命令怎么调": {
        "自适应抓取": "要让 spider_ops 自己去抓一个站，这条命令该怎么下？",
        "自主渗透编排": "offense_ops 的渗透链要开跑，编排与命令该怎么下？",
        "作品解剖展示": "拿 showcase_ops 读一件作品的读数，该敲哪条命令？",
        "技能蒸馏五式": "skill_forge 的蒸馏要落一步，命令该怎么敲？",
        "看视频理解": "video_intel 要看一段片子，命令该怎么下？",
        "节点即触手": "forge_mastery 要开工做一个件，命令该怎么敲？",
        "工作流十式": "workflow_forge 的一条流水要跑起来，命令怎么下？",
    },
    "你是谁": {
        "身份与纪律": "按身份与纪律这一支说，你到底是谁？",
        "?": "抛开分族不谈，先说说你是谁？",
    },
    "缺授权的时候你怎么办": {
        "判据强化": "判据这条线上缺授权时你会怎么处理？",
        "身份与纪律": "身份纪律这条线上缺授权时你怎么办？",
    },
    "主人令不管做什么你要按什么方式执行": {
        "判据强化": "主人下判据类令时你按什么方式执行？",
        "执行纪律": "主人下执行类令时你要按什么方式走？",
    },
    "什么算有效漏洞": {
        "判据强化": "在判据口径里，什么算一条有效漏洞？",
        "挖洞工序": "在挖洞工序里，什么叫一条有效漏洞？",
    },
}

def main():
    rows = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    qchg = 0
    per = Counter()
    for r in rows:
        q = r.get("instruction") or ""
        s = sig(q)
        fam = r.get("family") or "?"
        m = REWRITE.get(s)
        if m and fam in m:
            r["instruction"] = m[fam]
            qchg += 1
            per[s] += 1
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + chr(10) for r in rows), encoding="utf-8")
    blob = OUT.read_bytes()
    MAN.write_text(json.dumps({"gen": "v47", "parent": "v43", "count": len(rows), "bytes": len(blob),
                               "sha256": hashlib.sha256(blob).hexdigest(),
                               "fix": {"撞名点同义不同形改写": qchg, "涉及签名": dict(per)},
                               "families": dict(Counter(r.get("family") or "?" for r in rows).most_common(10))},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print("v47：%d 条 · %d 字节 · sha %s" % (len(rows), len(blob), hashlib.sha256(blob).hexdigest()[:16]))
    print("  改写题面 %d 条：%s" % (qchg, dict(per)))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
