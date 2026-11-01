# -*- coding: utf-8 -*-
"""别名锻造（gen-aliases）：**新能力位一登记就能被直达**，不用等人手写词表。

## 为什么需要

2026-11-01 全量基准 485 项跑完：新加的 8 个器官**全部 MISS** —— 有实现、有登记、有分派，
但 `data/intent-lexicon.json` 里没有它们的口语说法 ⇒ **路由不可达 = 等于没长**。
补 8 条词就 8/8 直达了，但这说明流程有洞：**登记能力位时没有"入口"这一道工序**。

本工具把这道工序自动化：从**能力位自己的 desc 与名字**产出候选口语，去重、去冲突、去通用词后，
可选写入词表（标 `auto: true` 便于审计/回滚）。

## 口径（宁可少生成，不造噪音）

1. 来源：desc 的首段（去 markdown、去括号内说明），2–14 字；名字按 `_` 切出的英文词；
2. 过滤：通用词（能力/工具/读取/执行/状态/文件…）不进；纯英文单词只在 ≥5 字符时进；
3. 去重：已出现在任何 `say` 里的不用；同一别名指向多个能力位 ⇒ **丢弃**（歧义）；
4. 写入时**只增不改**（不动人工词条），每条带 `auto: true`。

用法：
    python tools/codex-scripts/gen-aliases.py --dry-run         # 只看候选与统计
    python tools/codex-scripts/gen-aliases.py --apply           # 写进词表（只增不改）
    python tools/codex-scripts/gen-aliases.py --apply --limit 120
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

LEX = os.path.join(ROOT, "data", "intent-lexicon.json")
OUT = os.path.join(ROOT, "state", "aliases-proposed.json")

GENERIC = {
    "能力", "工具", "读取", "执行", "状态", "文件", "数据", "系统", "结果", "内容",
    "骨架", "只读", "检查", "扫描", "推进", "分析", "处理", "生成", "管理", "服务",
    "读取真实", "返回", "支持", "提供", "汇总", "查看", "获取", "输出",
}
CJK = re.compile(r"[\u4e00-\u9fff]")


def _clean_desc(desc: str) -> str:
    t = str(desc or "")
    t = re.sub(r"\*\*|__|`|#+", "", t)          # markdown
    t = re.sub(r"（[^）]*）|\([^)]*\)", "", t)   # 括号说明
    t = re.split(r"[：:；;。，,、！!\n]", t)[0]
    return t.strip()


def _cjk_alias(text: str) -> str | None:
    t = _clean_desc(text)
    t = re.sub(r"^[【\[]*[^】\]]*[】\]]", "", t)  # 去【】前缀
    t = t.strip(" -·—…")
    if not (2 <= len(t) <= 14) or not CJK.search(t):
        return None
    if t in GENERIC or t in ("", "无"):
        return None
    return t


def _en_aliases(name: str) -> list[str]:
    parts = [p for p in re.split(r"[_\-]", str(name)) if len(p) >= 5 and p.isascii()]
    return parts if len(parts) >= 1 else []


def build() -> dict:
    from gbt_allinone.caps_registry import BENIGN_CAPS
    lex = json.load(open(LEX, encoding="utf-8"))
    used = set()
    for e in lex.get("intents") or []:
        for s in e.get("say") or []:
            used.add(str(s).strip().lower())

    cand: dict[str, list] = {}
    alias_owner: dict[str, set] = {}
    for name, meta in BENIGN_CAPS.items():
        outs = []
        a = _cjk_alias(meta.get("desc") or "")
        if a:
            outs.append(a)
        for en in _en_aliases(name):
            outs.append(en)
        outs = [x for x in dict.fromkeys(outs) if x and x.lower() not in used]
        if not outs:
            continue
        cand[name] = outs[:3]
        for x in outs[:3]:
            alias_owner.setdefault(x.lower(), set()).add(name)

    conflicts = {a: sorted(v) for a, v in alias_owner.items() if len(v) > 1}
    for a in conflicts:
        for name in list(cand):
            cand[name] = [x for x in cand[name] if x.lower() != a]
    cand = {k: v for k, v in cand.items() if v}
    return {"caps": len(BENIGN_CAPS), "with_alias": len(cand),
            "aliases": sum(len(v) for v in cand.values()),
            "conflicts_dropped": len(conflicts),
            "conflict_sample": dict(list(conflicts.items())[:10]),
            "proposals": cand}


def apply(limit: int) -> dict:
    d = build()
    lex = json.load(open(LEX, encoding="utf-8"))
    intents = lex.setdefault("intents", [])
    seen_what = {e.get("what") for e in intents}
    added = 0
    for name, aliases in list(d["proposals"].items())[:limit]:
        what = "自动别名 · " + name
        if what in seen_what:
            continue
        intents.append({"what": what, "say": aliases, "caps": {name: 10},
                        "auto": True, "why": "gen-aliases 从 desc/名字自动生成"})
        seen_what.add(what)
        added += 1
    json.dump(lex, open(LEX, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {"ok": True, "added": added, "total_intents": len(intents),
            "caps_with_alias": d["with_alias"], "conflicts_dropped": d["conflicts_dropped"]}


def measure() -> dict:
    """用脉冲直达回放全量基准的能力位题面，看"可直达率"。"""
    from gbt_allinone.tentacle import pulse_core as P
    import json as _j
    rows_path = os.path.join(ROOT, "state", "commander", "coverage-rows.jsonl")
    last = {}
    for line in open(rows_path, encoding="utf-8"):
        try:
            r = _j.loads(line)
        except Exception:  # noqa: BLE001
            continue
        last[(r["space"], r["name"])] = r
    caps = [r for (sp, _), r in last.items() if sp == "cap"]
    hit = sum(1 for r in caps if P.direct(r["intent"])["hit"] and P.direct(r["intent"])["name"] == r["name"])
    hit_any = sum(1 for r in caps if P.direct(r["intent"])["hit"])
    return {"cap_rows": len(caps), "direct_hit_exact": hit, "direct_hit_any": hit_any,
            "exact_rate": round(hit / len(caps), 4) if caps else 0.0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()

    before = measure()
    d = build()
    print("== 别名锻造 ==")
    print("能力位 %d · 有候选别名 %d · 候选 %d 条 · 丢弃歧义 %d"
          % (d["caps"], d["with_alias"], d["aliases"], d["conflicts_dropped"]))
    if d["conflict_sample"]:
        print("歧义样例:", json.dumps(d["conflict_sample"], ensure_ascii=False)[:300])
    print("脉冲直达可直达率（改前）：%s" % json.dumps(before, ensure_ascii=False))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(d, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("候选落盘:", OUT)
    if args.apply:
        r = apply(args.limit)
        print("写入词表:", json.dumps(r, ensure_ascii=False))
        after = measure()
        print("脉冲直达可直达率（改后）：%s" % json.dumps(after, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
