# -*- coding: utf-8 -*-
"""逐位核对：**每一项能力 / 每一根触手，能不能被我们自己的权重选中**。

主人令 2026-10-31：「把我们的原生无限制指挥官大模型权重彻底融合进触手主干」
「要做到所有的触手都能通过我们自己的大模型权重」「每一项能力都要全方位不能遗漏」。

这个脚本量的就是这句话，量法只有一种 —— **真跑**：

    候选池 = 95 根触手方法 + 351 位本体能力（commander 的 auto 池，现读）
    对池里每一项：
      用它的别名/说明造一句人话（**抹掉名字本身**，免得泄题）
      → 过本机权重车道（tentacle/commander.py）让它选
      → 选中的名字 == 期望名字 ⇒ 这一项「通」

三条口径（写死，不许事后改）：

1. **候选来自真名表**：交给模型的是现读的表（方法表 + BENIGN_CAPS），不是脚本自带的清单；
2. **造句不泄题**：把期望名字从句子里删掉；方法用别名、能力用 desc 前段；
3. **同表生成 = 上限读数**：别名/desc 同时被召回打分用 ⇒ 这份数偏乐观，只当
   「可达性上限」，不能当泛化命中率。打印时逐项列出 miss，谁没过一眼能看到。

用法：
    python tools/codex-scripts/commander-coverage.py                 # 全量（方法+能力）
    python tools/codex-scripts/commander-coverage.py --space method  # 只看手
    python tools/codex-scripts/commander-coverage.py --space cap     # 只看能力位
    python tools/codex-scripts/commander-coverage.py --limit 20
    python tools/codex-scripts/commander-coverage.py --json state/commander/coverage.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

_PUNCT = re.compile(r"[，。；：！？、·（）()\[\]【】\"'`~!@#$%^&*+=|<>?/\\\\_#>~-]+")


def strip_name(text: str, name: str) -> str:
    """把名字本身从句子里抹掉（含下划线变体），剩下的才是"人话线索"。"""
    out = text
    for variant in {name, name.replace("_", " "), name.replace("_", "")}:
        out = out.replace(variant, " ")
    return re.sub(r"\s+", " ", out).strip()


def build_intent(name: str, hint: str, dom: str) -> str:
    """造一句**不含名字**的人话。"""
    clean = _PUNCT.sub(" ", strip_name(str(hint or ""), name))
    words = [w for w in clean.split() if len(w) >= 2]
    if words:
        body = "".join(words[:4])
        return body if len(body) >= 2 else "帮我看看" + body
    dom_name = {"window": "窗口", "keyboard": "键盘", "mouse": "鼠标", "clipboard": "剪贴板",
                "vision": "屏幕", "process": "进程", "fs": "文件", "read": "读取",
                "tentacle": "触手", "system": "系统", "data": "数据"}.get(dom, dom or "这件事")
    return "帮我处理一下%s相关的事" % dom_name


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--space", choices=["auto", "method", "cap"], default="auto")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--k", type=int, default=12)
    ap.add_argument("--json", default="state/commander/coverage.json")
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--sample", type=int, default=0,
                    help="按域抽样：每个域最多取 N 项（跳过已跑过的），快出全量命中率")
    ap.add_argument("--recall-only", action="store_true",
                    help="只量召回（不调模型，秒级）：目标项是否进了 top-k 候选")
    args = ap.parse_args()

    import gbt_allinone  # noqa: F401
    from gbt_allinone import semantic_route as SR
    from gbt_allinone.tentacle import bridge as TB
    from gbt_allinone.tentacle import commander as C

    st = C.status() if not args.recall_only else {"weights": {}, "endpoint": {"ok": True}, "base": "recall-only"}
    print("权重:", st["weights"].get("name") or st["weights"].get("reason"))
    print("引擎:", "在" if st["endpoint"].get("ok") else "没起（%s）" % st["endpoint"].get("error"))
    if not st["endpoint"].get("ok"):
        print("先起引擎：python -c \"import sys;sys.path.insert(0,'.');"
              "from gbt_allinone.tentacle import commander as C;print(C.start())\"")
        return 2

    items = []
    if args.space in ("auto", "method"):
        for rec in (SR.method_table() or {}).get("items") or []:
            items.append({"space": "method", "name": rec["method"],
                          "dom": rec.get("neighborhood", ""),
                          "hint": rec.get("hint") or TB.INTENT_ALIASES.get(rec["method"], "")})
    if args.space in ("auto", "cap"):
        for rec in C.catalog_caps():
            items.append({"space": "cap", "name": rec["name"], "dom": rec["domain"],
                          "hint": rec["desc"]})
    if args.limit:
        items = items[: args.limit]
    if args.sample:
        # 按域抽样：每个域取前 N 项（域内按名字序，确定性可复算）；跨域全覆盖
        by_dom: dict = {}
        for it in items:
            by_dom.setdefault(it["dom"] or "?", []).append(it)
        picked = []
        for dom in sorted(by_dom):
            picked.extend(by_dom[dom][: args.sample])
        items = picked
    print("待核对:", len(items), "（方法+能力）")

    rows = []
    # 断点续跑：每项一跑完就追加一行 JSONL（真跑 478 项要几小时，中途断了不该白跑）
    rows_path = os.path.join(ROOT, "state", "commander", "coverage-rows.jsonl")
    os.makedirs(os.path.dirname(rows_path), exist_ok=True)
    done = {}
    if os.path.exists(rows_path):
        with open(rows_path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                    done[(rec.get("space"), rec.get("name"))] = rec
                except Exception:  # noqa: BLE001
                    continue
    if args.sample:
        # **抽样要抽没跑过的**（否则样本与已跑项重叠，等于白跑）
        rest = [it for it in items if (it["space"], it["name"]) not in done]
        by_dom2: dict = {}
        for it in rest:
            by_dom2.setdefault(it["dom"] or "?", []).append(it)
        picked2 = []
        for dom in sorted(by_dom2):
            picked2.extend(by_dom2[dom][: args.sample])
        items = picked2
        print("抽样后待跑:", len(items), "（按域每域", args.sample, "项，已排除跑过的）")
    if args.recall_only:
        # 召回是**另一种口径**：不许复用 model 模式的已完成行。
        # 实测血账（2026-11-04）：混用把 recall 误报成 96.39%（真值 99.8%）——
        # 20 个 MISS 里 12 个是从 coverage-rows.jsonl 抄来的 model 结论，
        # 一个都没重算；而且抄得越多错得越多（第一次 done 只有 23 行时只错 1 个）。
        # 「候选池有没有兜住真名」和「权重有没有选对」是两件事，不能互相顶替。
        if done:
            print("召回口径：忽略已完成 %d 行（那是 model 模式的结果，不可混用）"
                  % len(done))
        done = {}
    if done:
        print("续跑：已完成 %d 项，跳过" % len(done))
    t_all = time.time()
    for i, it in enumerate(items, 1):
        if (it["space"], it["name"]) in done:
            rows.append(done[(it["space"], it["name"])])
            continue
        intent = build_intent(it["name"], it["hint"], it["dom"])
        t0 = time.time()
        if args.recall_only:
            # 只量**召回**：目标项有没有进 top-k 候选（不调模型；这是模型排序的上界）
            names_k = [c["name"] for c in C._shortlist(intent, args.k, args.space)]
            inn = it["name"] in names_k
            r = {"ok": inn, "name": it["name"] if inn else (names_k[0] if names_k else None)}
        else:
            r = C.route(intent, k=args.k, space=args.space, timeout=args.timeout)
        ms = int((time.time() - t0) * 1000)
        hit = bool(r.get("ok") and r.get("name") == it["name"])
        row = {"space": it["space"], "name": it["name"], "dom": it["dom"],
               "intent": intent, "hit": hit, "picked": r.get("name"),
               "error": None if r.get("ok") else r.get("error"), "ms": ms}
        rows.append(row)
        if not args.recall_only:
            with open(rows_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print("%3d/%d %-6s %-26s %s %-24s %5dms" % (i, len(items), it["space"], it["name"],
                                                    "HIT " if hit else "MISS", r.get("name") or "-", ms),
              flush=True)

    def rate(subset):
        return round(sum(1 for x in subset if x["hit"]) / len(subset), 4) if subset else 0.0

    by_space = {s: [x for x in rows if x["space"] == s] for s in ("method", "cap")}
    by_dom = {}
    for x in rows:
        by_dom.setdefault(x["dom"] or "?", []).append(x)
    total_ms = int((time.time() - t_all) * 1000)
    summary = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "weights": st["weights"].get("name"), "endpoint": st["base"],
        "space": args.space, "k": args.k,
        "total": len(rows), "hit": sum(1 for x in rows if x["hit"]), "rate": rate(rows),
        "method": {"n": len(by_space["method"]), "hit": sum(1 for x in by_space["method"] if x["hit"]),
                   "rate": rate(by_space["method"])},
        "cap": {"n": len(by_space["cap"]), "hit": sum(1 for x in by_space["cap"] if x["hit"]),
                "rate": rate(by_space["cap"])},
        "by_domain": {d: {"n": len(v), "hit": sum(1 for x in v if x["hit"]), "rate": rate(v)}
                      for d, v in sorted(by_dom.items())},
        "total_ms": total_ms, "avg_ms": int(total_ms / len(rows)) if rows else 0,
        "measure": "同表生成（别名/desc 即召回语料）⇒ 可达性上限，不是泛化命中率",
        "misses": [x for x in rows if not x["hit"]],
        "rows": rows,
    }
    out = args.json if os.path.isabs(args.json) else os.path.join(ROOT, args.json)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=1)

    print("\n== 逐项可达性（上限口径） %d/%d = %.1f%% · 平均 %dms · 总 %ds"
          % (summary["hit"], summary["total"], 100.0 * summary["rate"],
             summary["avg_ms"], total_ms // 1000))
    print("   触手方法 %d/%d = %.1f%% · 本体能力 %d/%d = %.1f%%"
          % (summary["method"]["hit"], summary["method"]["n"], 100.0 * summary["method"]["rate"],
             summary["cap"]["hit"], summary["cap"]["n"], 100.0 * summary["cap"]["rate"]))
    if summary["misses"]:
        print("miss:", ", ".join("%s/%s" % (x["space"], x["name"]) for x in summary["misses"][:25]))
    print("落盘:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
