# -*- coding: utf-8 -*-
"""route_ledger —— 记录「用户原话 → 路由结果 → 实际用了哪个」，让数据自己长出来

── 为什么要有它（铁证驱动，2026-11-04）──
想给 403 个没有触发词的能力补规则，试了两条数据路，都不成立：

  ① 从 desc 抽词：2051 个互斥候选 → 零误伤 2044 个 → 全量合并进规则表后，
     留出集（177 条真实触发词）top-1 **78.5% → 78.5%，+0.0 pp**。
     且抽出来的是 n-gram 碎片：`七根感官` `根感官` `六根动` `台设备`——
     用户永远不会这么说。根因：**desc 是技术描述，不是用户话术**。
  ② 审计日志 audit.jsonl（49,537 行 / 13 种事件）：只有 `call` / `ok`，
     **没有任何 query / intent / text 字段**。系统从没记过「人是怎么问的」。

结论：当前系统里**不存在**「用户原话 ↔ 能力」的配对数据。
在这种前提下补触发词，只能靠编 —— 那就是猜。

所以先建数据源：每次路由都记一条，积累到有统计意义再自动生成规则。
**不猜、不编、等数据。**

── 设计取舍 ──
· **append-only JSONL**：写坏一行不影响其他行，也便于 grep。
· **失败绝不抛异常**：日志挂了不能拖垮路由（记录是旁路，不是主路）。
· **不记敏感内容**：只记 query 文本 + 路由结果；不记 payload、不记参数、不记结果内容。
· **可从日志反推的两件事**：
    a. 哪些 query 落在 L2（统计猜）→ 这些是最需要补规则的；
    b. 路由命中了 A 但实际执行的是 B → 路由被判错的真实样本。
"""
from __future__ import annotations

import json
import os
import time

_LOG_REL = os.path.join("state", "query_log.jsonl")
_MAX_QUERY = 300        # 单条查询最长保留长度（防日志被超长文本撑爆）

# ── 门槛（2026-11-04 重新推导，替换原来的 `uniq_q >= 300`）──────────────
# 原门槛有两个毛病，都是实测出来的：
#   ① **分母错**：300 隐含「403 个能力都要补触发词」。可 orchestration-ledger
#      24,083 次真实调用只碰过 72 个能力，剔掉系统内部件（focus_stack / reminder /
#      api_slot … 用户根本不会对它说人话）剩 54 个用户面能力，其中 9 个已有触发词
#      ⇒ **真正待补的是 45 个，高频只有 14 个**。给 403 个都补才是伪需求。
#   ② **计量错**：它数「不同句子」，而测试探针也算分 —— 实测台账 139 行里
#      126 行是 echo / count_words 的测试噪音，真实不同的句子只有 9 条。
#      「快攒到 300 了」是假象。
#   ③ **样本错配**：高频能力（截图/读字/开麦）5 种问法就够定一条规则；
#      长尾能力等 300 条也凑不到 1 条。总量不是正确的自变量。
# ⇒ 改成双条件：**覆盖了哪些能力** + **每个能力几种问法**。
_NEED_CAPS = 14         # 高频且用户会主动问的能力数（2026-11-04 实测榜）
_NEED_PER_CAP = 5       # 每个能力至少 5 种不同问法，规则才稳
_READY_TOTAL = _NEED_CAPS * _NEED_PER_CAP      # = 70，不是 300

# 探针/内部件：这些目标名出现在台账里，基本是测试或系统自调，不是人话。
# 只用于**统计口径**（剔噪），不删数据 —— 它们也可能是真问法的边缘情况，
# 所以要能被数出来、被看见，不能静默处理。
_PROBE_TARGETS = {
    "echo", "count_words", "no_such_capability_xyz", "selfscan", "impact_check",
    "signature_guard", "inventory", "legacy_guard", "context_guard", "trunk_cover",
    "capability_net", "cap_pack", "update_verify",
    "focus_stack", "reminder", "api_slot", "pairing", "ui_card", "resource_snapshot",
    "body_control", "context_inject", "lan_pairing", "media_library", "update_chain",
    "turn_trace", "thought_stream", "omni_plug", "asset_bindings",
}


def _root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def log_path() -> str:
    return os.path.join(_root(), _LOG_REL)


def record(query: str, routed=None, layer: str = "", chosen=None,
           source: str = "", note: str = "") -> dict:
    """记一条路由记录。**永不抛异常** —— 旁路日志不该拖垮主路。

    routed:  路由给出的首位能力（可能是错的）
    chosen:  实际执行/用户认可的能力（真值，有了它才能算出路由错在哪）
    """
    try:
        q = str(query or "").strip()[:_MAX_QUERY]
        if not q:
            return {"ok": False, "reason": "空查询不记"}
        row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "query": q,
               "routed": str(routed or "") or None,
               "layer": str(layer or "") or None,
               "chosen": str(chosen or "") or None,
               "source": str(source or "") or None,
               "note": str(note or "")[:120] or None}
        p = log_path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        # ⚠️ 这里是 **append**，不是覆盖写，所以不需要 tmp+os.replace：
        #   · 单行 JSON 远小于 4KB，O_APPEND 下由内核保证不会与并发写交错；
        #   · 若改成"读全文→改→原子写回"，反而把「几次独立 append」变成
        #     「一次全量重写」—— 并发下丢更新的概率更高，也慢得多；
        #   · 真要防半行截断，正确做法是写入侧加行尾校验（见 _read_all 的容错）。
        # 注：注释必须放在 with **之外** —— 放进 with 里而缩进又掉出来，
        # with 块会变成空块（IndentationError），2026-11-04 我自己踩过一次。
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return {"ok": True, "logged": True}
    except Exception as exc:                                       # noqa: BLE001
        return {"ok": False, "reason": "%s: %s" % (type(exc).__name__, str(exc)[:120])}


def _read_all():
    p = log_path()
    if not os.path.exists(p):
        return []
    rows = []
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:                                      # noqa: BLE001
                continue
    return rows


def stats() -> dict:
    """积累到什么程度了 —— 离「能自动生成规则」还差多远。"""
    rows = _read_all()
    if not rows:
        return {"ok": True, "total": 0, "log": log_path(),
                "ready": False,
                "note": "还没有数据。需要真实对话跑起来才会积累。"}

    by_layer = {}
    for r in rows:
        k = r.get("layer") or "unknown"
        by_layer[k] = by_layer.get(k, 0) + 1

    # 最有价值的两类：(真值已知) 与 (落在 L2 猜的)
    with_truth = [r for r in rows if r.get("chosen")]
    wrong = [r for r in with_truth if r.get("routed") and r["routed"] != r["chosen"]]
    l2_only = [r for r in rows if (r.get("layer") or "").startswith("L2")]

    uniq_q = len({r["query"] for r in rows})

    # ── 剔噪口径（2026-11-04）：探针/内部件调用不算「人话样本」──
    def _is_probe(r) -> bool:
        t = r.get("chosen") or r.get("routed") or ""
        return t in _PROBE_TARGETS

    real = [r for r in rows if not _is_probe(r)]
    real_q = {r["query"] for r in real if r.get("query")}

    # 每个能力被「几种不同问法」问到过 —— 这才是能否生成规则的依据（不是总量）
    per_cap = {}
    for r in real:
        t = r.get("chosen") or r.get("routed")
        q = r.get("query")
        if t and q:
            per_cap.setdefault(t, set()).add(q)
    covered = sorted(((t, len(qs)) for t, qs in per_cap.items()), key=lambda x: (-x[1], x[0]))
    caps_ok = [t for t, n in covered if n >= _NEED_PER_CAP]

    ready_caps = len(caps_ok) >= _NEED_CAPS
    ready_total = len(real_q) >= _READY_TOTAL
    ready = ready_caps and ready_total
    suspects = sorted({(r.get("chosen") or r.get("routed") or "")
                       for r in rows if _is_probe(r)} - {""})

    if ready:
        hint = ("够了：%d 个能力各有 ≥%d 种问法（需 %d 个）· 真实问法 %d 条（需 %d）"
                % (len(caps_ok), _NEED_PER_CAP, _NEED_CAPS, len(real_q), _READY_TOTAL))
    else:
        hint = ("还差：能力覆盖 %d/%d 个（每个需 ≥%d 种问法）· 真实问法 %d/%d 条"
                % (len(caps_ok), _NEED_CAPS, _NEED_PER_CAP, len(real_q), _READY_TOTAL))
        if len(real_q) < _READY_TOTAL and len(caps_ok) >= _NEED_CAPS:
            hint += " —— 能力够了，缺的是「同一能力的更多问法」"
        elif len(caps_ok) < _NEED_CAPS:
            hint += " —— 缺的是「更多能力被真实问到」"

    return {"ok": True, "total": len(rows), "unique_queries": uniq_q,
            "by_layer": by_layer,
            "with_ground_truth": len(with_truth),
            "routed_wrong": len(wrong),
            "l2_only": len(l2_only),
            # 剔噪后的真实口径（ready 只看这两个）
            "real_rows": len(real),
            "real_unique_queries": len(real_q),
            "covered_caps": len(covered),
            "caps_ready": caps_ok,
            "per_cap": [{"cap": t, "asks": n} for t, n in covered[:30]],
            "probe_rows_excluded": len(rows) - len(real),
            "probe_targets_seen": suspects,
            "need": {"caps": _NEED_CAPS, "per_cap": _NEED_PER_CAP, "total": _READY_TOTAL},
            "ready": ready,
            "ready_hint": hint,
            "log": log_path()}


def export(min_count: int = 1) -> dict:
    """导出可用的 (query → chosen) 真值对，给未来生成规则用。

    2026-11-04：**剔掉探针样本**再导出。否则 echo / count_words 这类测试调用
    会被当成真值对喂给规则生成器 —— 那等于用测试数据训练自己。
    """
    rows = _read_all()
    pairs = {}
    skipped = 0
    for r in rows:
        q, c = r.get("query"), r.get("chosen")
        if not q or not c:
            continue
        if c in _PROBE_TARGETS:          # 探针/内部件不算真值
            skipped += 1
            continue
        pairs.setdefault((q, c), 0)
        pairs[(q, c)] += 1
    out = [{"query": q, "chosen": c, "count": n}
           for (q, c), n in pairs.items() if n >= min_count]
    out.sort(key=lambda x: -x["count"])
    return {"ok": True, "pairs": len(out), "probe_skipped": skipped,
            "note": "只有 chosen 存在时才导出；routed 不能当真值（它可能就是错的）；"
                    "探针样本（echo/count_words 等）已剔除",
            "data": out[:500]}


def _usage_rank(limit: int = 60) -> dict:
    """谁真的在被用 —— 读 orchestration-ledger 的真实调用分布（只读、流式）。

    「补词先补谁」的唯一硬依据：不是 403 个能力都要补，是**她真在用、却还没词**的那些。
    """
    import re as _re
    p = os.path.join(_root(), "state", "orchestration-ledger.jsonl")
    if not os.path.exists(p):
        return {"ok": False, "reason": "orchestration-ledger.jsonl 不存在", "path": p}
    counts = {}
    scanned = 0
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        for ln in f:
            if '"target"' not in ln:
                continue
            scanned += 1
            m = _re.search(r'"target":\s*"([^"]+)"', ln)
            if m:
                t = m.group(1)
                counts[t] = counts.get(t, 0) + 1
    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    return {"ok": True, "path": p, "scanned_lines_with_target": scanned,
            "distinct": len(counts), "ranked": ranked[:limit]}


def plan(stages=None) -> dict:
    """**动手前先算账**：现在该补哪个能力的触发词、还差几条 —— 不拍脑袋。

    三方交叉（缺一条就会补错）：
      ① 真实调用分布（orchestration-ledger）—— 谁在被用
      ② 能力自己的描述（caps_registry）——      谁已经写了「常用说法」
      ③ 台账真值对（export）——                   谁已经有真原话
    缺口 = ①里高频 **且** ②里没词；已有真原话的按 ③ 抵扣。

    为什么要分阶段：每一级都要立即可用、可验证。先补用得最多的 5 个
    （各 3 种问法 = 15 条），跑通再扩 —— 而不是等 70 条齐了才发现第一批就写歪。
    """
    from .caps_registry import BENIGN_CAPS
    stages = stages or [(5, 3), (9, 5), (99, 5)]     # (取前 N 个能力, 各要几种问法)

    ur = _usage_rank()
    if not ur.get("ok"):
        # 读不到真实分布就**不补** —— 盲补即等于编（本仓 2026-11-04 已栽过一次）
        return {"ok": False, "reason": "读不到真实调用分布，拒绝盲补", "detail": ur}

    # ② 谁已经有「常用说法」（intent_extracted 就是从这句抽词的，所以按同一口径判断）
    has_kw = {k for k, v in BENIGN_CAPS.items() if "常用说法" in str(v.get("desc") or "")}

    # ③ 谁已经有真原话
    ex = export()
    truth = {}
    for row in ex.get("data") or []:
        truth.setdefault(row["chosen"], set()).add(row["query"])

    # ① 高频 ∩ 无词 ∩ 是真实能力位 = 缺口
    gaps, skipped = [], {"internal": 0, "not_a_cap": 0, "already_has_kw": 0}
    for cap, calls in ur["ranked"]:
        if cap in _PROBE_TARGETS:
            skipped["internal"] += 1
            continue
        if cap not in BENIGN_CAPS:
            skipped["not_a_cap"] += 1
            continue
        if cap in has_kw:
            skipped["already_has_kw"] += 1
            continue
        gaps.append({"cap": cap, "calls": calls, "have": len(truth.get(cap, ()))})

    out, cursor = [], 0
    for i, (take, per) in enumerate(stages):
        chunk = gaps[cursor:cursor + take]
        cursor += take
        if not chunk:
            continue
        need = len(chunk) * per
        have = sum(min(g["have"], per) for g in chunk)
        out.append({"stage": "P%d" % i, "per_cap": per,
                    "caps": [g["cap"] for g in chunk],
                    "calls": sum(g["calls"] for g in chunk),
                    "need": need, "have": have, "gap": max(0, need - have)})

    total_need = sum(s["need"] for s in out)
    total_have = sum(s["have"] for s in out)
    nxt = next((s for s in out if s["gap"] > 0), None)

    if nxt:
        action = ("%s：补 %s（各需 %d 种真实问法），共需 %d 条，现有 %d 条，还差 %d 条"
                  % (nxt["stage"], " / ".join(nxt["caps"]), nxt["per_cap"],
                     nxt["need"], nxt["have"], nxt["gap"]))
    else:
        action = "各级都够了，可以生成规则并用留出集验收"

    return {
        "ok": True,
        "diagnosis": {
            "usage_scanned": ur["scanned_lines_with_target"],
            "usage_distinct": ur["distinct"],
            "gap_caps": len(gaps),
            "skipped": skipped,
            "ledger_truth_pairs": ex.get("pairs"),
        },
        "stages": out,
        "total": {"need": total_need, "have": total_have,
                  "gap": max(0, total_need - total_have)},
        "next_action": action,
        "why": ("分母来自真实调用而不是能力总数：%d 个能力里，扣除内部件/非能力位/"
                "已有词的，真正待补只有 %d 个；再按调用量分成 %d 级。"
                % (ur["distinct"], len(gaps), len(out))),
    }


def run(op: str = "stats", **kw) -> dict:
    o = str(op or "stats").strip()
    if o in ("stats", "status"):
        return stats()
    if o in ("plan", "next", "reflect"):
        # 大脑动手前先算账：该补谁、还差几条、下一级是什么
        return plan(kw.get("stages"))
    if o in ("export", "pairs"):
        return export(int(kw.get("min_count") or 1))
    if o in ("record", "log"):
        return record(kw.get("query") or "", kw.get("routed"),
                      kw.get("layer") or "", kw.get("chosen"),
                      kw.get("source") or "", kw.get("note") or "")
    return {"ok": False, "reason": "未知 op: %s" % o,
            "supported": ["record", "stats", "plan", "export"]}
