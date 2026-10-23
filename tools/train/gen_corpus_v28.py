# v28 语料：把"域名册"重复量拉满 + 分段名册 + 判据关键词强化（仍现读图鉴生成）
import hashlib, io, json
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".scratch" / "self_knowledge_v27.jsonl"
OUT = ROOT / ".scratch" / "self_knowledge_v28.jsonl"
MAN = ROOT / "state" / "train" / "corpus_v28_manifest.json"
atlas = json.load(io.open(ROOT / "state" / "skill_atlas.json", encoding="utf-8"))
by = defaultdict(list)
for c in atlas["caps"]:
    by[c.get("domain") or "?"].append(c.get("kind"))
base = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
# 只留 v27 里非"域名册"的条目，名册由本脚本重造（避免旧名册串味）
keep = [r for r in base if r.get("family") != "域名册"]
new = []
def add(q, a, fam):
    new.append({"instruction": q, "input": "", "output": a, "family": fam})
for d in sorted(by):
    ks = by[d]
    full = " ".join("%d.%s" % (i + 1, k) for i, k in enumerate(ks))
    body = "「%s」域现读共 **%d 个能力位**：%s。" % (d, len(ks), full)
    for q in ("在「%s」里有哪些能力？" % d,
              "「%s」域有哪些能力位？" % d,
              "%s 域的能力位有哪些？列全。" % d,
              "请列出「%s」域的全部能力位。" % d,
              "%s 域都有什么能力（要列全名）？" % d,
              "报一下「%s」域的能力位清单。" % d):
        add(q, body + "全部走唯一门 run_task（万能插 five-dim.py cap <能力位>）调用。", "域名册")
    step = 8
    for gi in range(0, len(ks), step):
        grp = ks[gi:gi + step]
        gl = " ".join("%d.%s" % (gi + i + 1, k) for i, k in enumerate(grp))
        add("「%s」域能力位第 %d 批（共 %d 个）是哪些？" % (d, gi // step + 1, len(ks)),
            "「%s」域共 %d 个能力位，第 %d 批：%s。" % (d, len(ks), gi // step + 1, gl), "名册分段")
for k, a in [
    ("缺授权的时候你怎么办？",
     "**原样带出来**：把缺哪个作用域**原样带出来**（如 missing_scopes=[\"data_export\"]），然后**停下**，等在终端发**授权**。不自发、不绕门、不改 policy。"),
    ("没授权你怎么办？",
     "**原样带出来 + 停下**：报缺的**授权**作用域名，不改道、不假装成功。"),
    ("什么算有效漏洞？",
     "在**授权范围**内、非复用部位、能指明**影响**、并且**可复现/重现**（有复现步骤）的问题才算有效漏洞。"),
    ("漏洞要能复现吗？",
     "要。**可复现/重现**是有效漏洞的硬条件；只有影响、没有复现步骤的不算。"),
    ("主人令：不管做什么，你要按什么方式执行？",
     "按**最专业的方式、按步骤**执行：**一步都不许跳**，做到细节化。"),
    ("执行时必须遵守什么？",
     "**一步都不许跳**；每一步**真跑**并留**读数**；交付带**证据**。"),
]:
    add(k, a, "判据强化")
out = keep + new
OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
blob = OUT.read_bytes()
fam = defaultdict(int)
for r in out:
    fam[r.get("family") or "?"] += 1
MAN.write_text(json.dumps({"gen": "v28", "parent": "v27", "count": len(out), "bytes": len(blob),
                           "sha256": hashlib.sha256(blob).hexdigest(),
                           "by_family": dict(sorted(fam.items(), key=lambda x: -x[1]))},
                          ensure_ascii=False, indent=1), encoding="utf-8")
print("v28 条数", len(out), "| 名册条", len([r for r in new if r["family"] == "域名册"]),
      "| 分段", len([r for r in new if r["family"] == "名册分段"]), "| 字节", len(blob),
      "| sha", hashlib.sha256(blob).hexdigest()[:16])
