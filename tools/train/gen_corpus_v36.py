# -*- coding: utf-8 -*-
"""gen_corpus_v35 -- 语料配比器：给每族设下限/上限，现算权重重采样，并出配比读数卡。

治的病：每加一族，老族被稀释（今晚同型出现三次）：
  域名册 2.6% => 30 域题全错；ComfyUI 族 4% => 被她台账带跑；v34 加族后 54 题从 52 掉到 48。
治法：① 验收关键族设**下限**（不够就重采样补齐）② 巨型族设**上限**（超了就按种子裁）③ manifest 里写读数卡。
"""
from __future__ import annotations
import hashlib, json, random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".scratch" / "self_knowledge_v35.jsonl"
OUT = ROOT / ".scratch" / "self_knowledge_v36.jsonl"
MAN = ROOT / "state" / "train" / "corpus_v36_manifest.json"
SEED = 1337
CAP_RATIO = 0.10          # 单族上限：不超过总量 10%
FLOOR = {                 # 验收关键族下限（条数）
    "域名册": 300, "节点名册": 180, "节点契约": 240, "秋叶版图示例": 60,
    "秋叶版契约": 180, "节点连线语义": 24, "秋叶版规程": 144, "看视频理解": 150,
    "身份与纪律": 60, "执行纪律": 60, "挖洞工序": 20, "跨域工序": 12,
    "习惯": 120, "部署法": 60, "工具使用": 60, "镜头导演": 48,
    "音乐自动化": 48, "书变技能": 48, "安全红线": 40, "工作流": 40, "故障处置": 40,
}
rows = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
by = defaultdict(list)
for r in rows:
    by[r.get("family") or "?"].append(r)
before = {k: len(v) for k, v in by.items()}
rnd = random.Random(SEED)
base = [r for r in rows]                      # 先全留一份
counts = defaultdict(int)
for r in base:
    counts[r.get("family") or "?"] += 1
extra = []
# ① 补下限：轮转复制该族条目
for fam, need in FLOOR.items():
    pool = by.get(fam) or []
    if not pool:
        continue
    i = 0
    while counts[fam] < need:
        extra.append(dict(pool[i % len(pool)]))
        counts[fam] += 1
        i += 1
mid = base + extra
mid_counts = defaultdict(int)
for r in mid:
    mid_counts[r.get("family") or "?"] += 1
total_mid = len(mid)
cap = int(total_mid * CAP_RATIO)
# ② 裁上限：只裁超出 cap 的族（按种子随机丢，保可复现）
trimmed = []
dropped = defaultdict(int)
for feat in mid:
    fam = feat.get("family") or "?"
    if fam not in ("?", "") and mid_counts[fam] > cap:
        if rnd.random() < 1.0 - (cap / mid_counts[fam]):
            dropped[fam] += 1
            continue
        mid_counts[fam] -= 1
    trimmed.append(feat)
OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + chr(10) for r in trimmed), encoding="utf-8")
blob = OUT.read_bytes()
after = defaultdict(int)
for r in trimmed:
    after[r.get("family") or "?"] += 1
n = len(trimmed)
card = []
for fam in sorted(set(list(before) + list(after)), key=lambda x: -after.get(x, 0)):
    b, a = before.get(fam, 0), after.get(fam, 0)
    act = "补下限" if a > b else ("裁上限" if a < b else "保持")
    card.append({"族": fam, "原": b, "新": a, "占比": round(a / n * 100, 1) if n else 0, "动作": act})
MAN.write_text(json.dumps({"gen": "v36", "parent": "v35", "seed": SEED, "cap_ratio": CAP_RATIO,
                           "floor": FLOOR, "count": n, "bytes": len(blob),
                           "sha256": hashlib.sha256(blob).hexdigest(),
                           "配比读数卡": card}, ensure_ascii=False, indent=1), encoding="utf-8")
print("v35", n, "条 | 字节", len(blob), "| sha", hashlib.sha256(blob).hexdigest()[:16])
print("前 12 族（原 -> 新 | 占比 | 动作）：")
for c in card[:12]:
    print("  %-16s %5d -> %5d | %5.1f%% | %s" % (c["族"], c["原"], c["新"], c["占比"], c["动作"]))
print("上限 cap =", cap, "| 被裁族:", {k: v for k, v in list(dropped.items())[:6]})




