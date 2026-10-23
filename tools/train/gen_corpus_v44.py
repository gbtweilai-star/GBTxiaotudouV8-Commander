# -*- coding: utf-8 -*-
"""gen_corpus_v44 -- 治串族：命令类题的【题面+答案】双双带族名与位名。"""
from __future__ import annotations
import hashlib, json, time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".scratch" / "self_knowledge_v43.jsonl"
OUT = ROOT / ".scratch" / "self_knowledge_v44.jsonl"
MAN = ROOT / "state" / "train" / "corpus_v44_manifest.json"
CAP_OF = {"自主渗透编排": "offense_ops", "自适应抓取": "spider_ops",
          "作品解剖展示": "showcase_ops", "技能蒸馏五式": "skill_forge",
          "看视频理解": "video_intel", "节点即触手": "forge_mastery",
          "工作流十式": "workflow_forge"}


def main():
    rows = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    # v44 前置：凡签名跨族的题面，一律把族名写进题面主体（含 ? 桶）
    _COLL = ("你是谁", "缺授权的时候", "主人令", "有效漏洞")
    _pre = 0
    for _r in rows:
        _q = _r.get("instruction") or ""
        _fam = _r.get("family") or "?"
        if any(w in _q for w in _COLL) and ("就" + _fam + "而言") not in _q:
            _core = _q.split("】", 1)[-1] if _q.startswith("【") else _q
            _r["instruction"] = "【" + _fam + "】就" + _fam + "而言：" + _core
            _pre += 1
    print("前置改写：%d 条" % _pre)

    n_q = n_a = 0
    for r in rows:
        q = r.get("instruction") or ""
        fam = r.get("family") or ""
        if fam not in CAP_OF:
            continue
        cap = CAP_OF[fam]
        if "命令" in q or "怎么调" in q:
            core = q
            if core.startswith("【"):
                core = core.split("】", 1)[-1]
            r["instruction"] = "【" + fam + "】用 " + cap + " " + core
            n_q += 1
        # 通用：凡签名跨族者，把族名写进题面主体（防语义撞名）
        if any(w in q for w in ("你是谁", "缺授权", "主人令", "有效漏洞")):
            core2 = q.split("】", 1)[-1] if q.startswith("【") else q
            r["instruction"] = "【" + fam + "】就" + fam + "而言：" + core2
            n_q += 1
            out = r.get("output") or ""
            if not out.startswith("走 cap " + cap):
                r["output"] = "走 cap " + cap + "：" + out
                n_a += 1
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + chr(10) for r in rows), encoding="utf-8")
    blob = OUT.read_bytes()
    fams = Counter(r.get("family") or "?" for r in rows)
    MAN.write_text(json.dumps({"gen": "v44", "parent": "v43", "count": len(rows), "bytes": len(blob),
                               "sha256": hashlib.sha256(blob).hexdigest(),
                               "fix": {"题面带族名": n_q, "答案带位名": n_a},
                               "families": dict(fams.most_common(12))}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("v44：%d 条 · %d 字节 · sha %s" % (len(rows), len(blob), hashlib.sha256(blob).hexdigest()[:16]))
    print("  修：题面带族名 %d 条 · 答案带位名 %d 条" % (n_q, n_a))
    print("  族（前6）：" + ", ".join("%s=%d" % (k, v) for k, v in fams.most_common(6)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
