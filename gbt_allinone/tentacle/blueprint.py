# -*- coding: utf-8 -*-
"""蓝图 → 思维导图 → 派遣落地（blueprint）：主人给架构之后的全自动主链。

主人口径（2026-11-01，逐字）：「必须由 GBT小土豆V8 根据用户给的架构框架来生成蓝图，
用户看了没问题就分析推理然后派遣思维导图任务指引给触手去执行任务，直至项目落地」。

## 五段主链（每一段都有落盘产物）

    ① make      架构 → 蓝图（目标/阶段/任务/验收/风险）    → state/blueprints/<id>.json + .md
    ② approve   主人过目（**唯一允许的交互**，之后禁止再问）   → state/blueprints/<id>.approved.json
    ③ mindmap   分析推理 → 任务图（节点=任务，边=依赖）      → <id>.mindmap.json + .mmd（mermaid）
    ④ dispatch  派遣触手执行（拓扑序，只跑安全能力位）        → <id>.runs.jsonl（逐任务留痕）
    ⑤ status    进度 / 是否落地（landed = 全部任务通过验收）

## 纪律

- **蓝图不过目不派遣**（`approve` 之前 dispatch 直接拒）；
- **过目之后不许再问主人**（自动 `autonomy.declare`，除 danger/transfer）；
- **只派遣安全能力位**（registry 里 safe=True 且不在订单/转账面）；危险能力留给票；
- **不装成功**：任务失败就记失败，`landed` 要求**全部**任务 ok，不许"差不多"。
"""
from __future__ import annotations

import json
import pathlib
import time
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
BP_DIR = ROOT / "state" / "blueprints"

# 每阶段默认派遣的安全能力位（都能只读跑，且真的能产出证据）
PHASES = (
    ("勘察", "摸清现状：能力面、代码覆盖、资产与插口",
     [("selfscan", {}, "自检干净"),
      ("cap_self", {"op": "verify"}, "能力位无漂移"),
      ("trunk_cover", {"op": "status"}, "代码覆盖读数"),
      ("inventory", {}, "清单无异物")]),
    ("设计", "把架构拆成可执行任务图与验收口径",
     [("orchestration", {"op": "panel", "limit": 5}, "编排面板可读"),
      ("pulse_core", {"op": "status"}, "脉冲四机制在")]),
    ("实现", "按任务图派遣触手执行（本批为读面任务）",
     [("comfy_native", {"op": "coverage"}, "图像契约覆盖读数"),
      ("body_sense", {"op": "status"}, "身体知觉在")]),
    ("验证", "跑判据：契约测试 / 签名 / 真相扫描",
     [("signature_guard", {"scope": "all"}, "署名完整"),
      ("truth_scan", {}, "无静默造假")]),
    ("固化", "落账本 + 快照，确保重启可续",
     [("orchestration", {"op": "status"}, "账本落盘"),
      ("cap_self", {"op": "brief"}, "记忆条可生成")]),
)



# 架构关键词 → 追加的专项任务（只挑**安全能力位**，每条都能真跑出证据）
ARCH_HINTS = (
    (("触手", "主干", "覆盖"), [
        ("trunk_cover", {"op": "scan"}, "代码每一处都归到某根触手（orphan=0）"),
        ("omni_open", {"op": "scan"}, "插口动态发现（不是写死六类）")]),
    (("权重", "大模型", "指挥官", "推理"), [
        ("commander", {"op": "status"}, "本机权重在位且可判决"),
        ("energy_core", {"op": "status"}, "能源核心取电口读数")]),
    (("上下文", "无限制"), [
        ("context_guard", {"op": "status", "name": "default"}, "无限制上下文：窗口/溢出/落库读数")]),
    (("吞噬", "进化", "强化"), [
        ("devour_auto", {"op": "tick", "limit": 3, "web": False}, "自主吞食一轮：只吃缺口且留痕")]),
    (("脉冲", "提速", "直达"), [
        ("pulse_core", {"op": "verify"}, "脉冲四机制全过"),
        ("pulse_core", {"op": "direct", "intent": "审计"}, "直达 0 token 命中")]),
    (("图像", "comfy", "天真", "秋叶"), [
        ("comfy_native", {"op": "harvest", "limit": 3}, "取食清单：只取缺的、用得上的"),
        ("comfy_native", {"op": "coverage"}, "契约面覆盖读数")]),
    (("自主", "蓝图", "落地", "不说话", "不打扰"), [
        ("autonomy", {"op": "status"}, "自主契约：除 danger/transfer 不许打扰"),
        ("orchestration", {"op": "panel", "limit": 3}, "编排面板：上轮动了什么")]),
    (("身体", "器官", "痛觉", "机器人"), [
        ("body_sense", {"op": "status"}, "本体感觉/痛觉/神经邻域读数")]),
    (("吞", "吞噬", "GitHub"), [
        ("devour_auto", {"op": "status"}, "吞食账本：吃了多少、拒了多少")]),
)


def _arch_tasks(arch: str, start: int) -> list:
    out = []
    for keys, items in ARCH_HINTS:
        if not any(k in arch for k in keys):
            continue
        for cap, payload, accept in items:
            out.append({"id": "专项.%d" % (start + len(out) + 1), "phase": "专项",
                        "title": "专项 · %s" % cap, "cap": cap,
                        "payload": payload, "acceptance": accept, "needs": []})
    return out



# ── 2026-11-01 蓝图模板库：落地过的图**沉淀成模板**，下次相似架构直接复用 ──
# 主人要"架构→落地"越来越快；复用**已验证**的任务图比每次从零拆更可靠。
TEMPLATE_DIR = ROOT / "state" / "blueprint-templates"


def _arch_keys(arch: str) -> list:
    """架构关键词签名（用于模板匹配）：命中 ARCH_HINTS 的键 + 高频词。"""
    a = str(arch or "")
    keys = []
    for words, _items in ARCH_HINTS:
        keys.extend([w for w in words if w in a])
    return sorted(set(keys))


def _slug(arch: str) -> str:
    ks = _arch_keys(arch)
    base = "-".join(ks[:4]) or "general"
    return "%s-%d" % (base[:40], int(time.time()) % 100000)


def save_template(bid: str) -> dict:
    """把一张**已落地**的蓝图存成模板（只存已通过的任务图与验收口径）。"""
    st = status(bid)
    if not st.get("landed"):
        return {"ok": False, "error": "user_error: 没落地的不存模板（避免把失败经验当资产）"}
    P = _paths(str(bid))
    bp = json.loads(P["json"].read_text(encoding="utf-8"))
    graph = json.loads(P["mindmap"].read_text(encoding="utf-8")) if P["mindmap"].is_file() else {"tasks": []}
    keys = _arch_keys(bp.get("architecture") or "")
    if not keys:
        return {"ok": False, "error": "user_error: 架构没有可识别的关键词，存了也匹配不上"}
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    name = _slug(bp.get("architecture") or "")
    tpl = {"name": name, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "keys": keys, "architecture": str(bp.get("architecture"))[:300],
           "accepted": bp.get("acceptance"),
           "tasks": [{"id": t["id"], "phase": t["phase"], "title": t["title"],
                      "cap": t["cap"], "payload": t.get("payload") or {},
                      "acceptance": t.get("acceptance"), "needs": t.get("needs") or []}
                     for t in (graph.get("tasks") or [])]}
    (TEMPLATE_DIR / (name + ".json")).write_text(json.dumps(tpl, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
    return {"ok": True, "template": name, "tasks": len(tpl["tasks"]), "keys": keys}


def find_template(arch: str) -> dict:
    """找最像的模板：关键词重合 ≥2 才复用（宁可不用，不用错）。"""
    keys = set(_arch_keys(arch))
    if not keys or not TEMPLATE_DIR.is_dir():
        return {"ok": False, "why": "无关键词或无模板"}
    best, best_hit = None, 0
    for f in TEMPLATE_DIR.glob("*.json"):
        try:
            t = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        hit = len(keys & set(t.get("keys") or []))
        if hit > best_hit:
            best, best_hit = t, hit
    if best and best_hit >= 2:
        return {"ok": True, "template": best, "hit": best_hit, "keys": sorted(keys)}
    return {"ok": False, "why": "最像的模板重合 %d < 2" % best_hit, "keys": sorted(keys)}


def instantiate_template(tpl: dict, bid: str, arch: str) -> dict:
    """用模板任务图生成新蓝图（任务 id 重排、依赖重连）。"""
    tasks = []
    id_map = {}
    for i, t in enumerate(tpl.get("tasks") or []):
        nid = "%s.%d" % (t.get("phase") or "任务", i + 1)
        id_map[t.get("id")] = nid
        tasks.append({"id": nid, "phase": t.get("phase") or "任务",
                      "title": t.get("title"), "cap": t.get("cap"),
                      "payload": t.get("payload") or {},
                      "acceptance": t.get("acceptance") or "执行通过",
                      "needs": [id_map[n] for n in (t.get("needs") or []) if n in id_map]})
    if not tasks:
        return {"ok": False, "error": "模板里没有任务"}
    tasks += _arch_tasks(arch, len(tasks))
    return {"ok": True, "tasks": tasks}


def templates() -> dict:
    rows = []
    if TEMPLATE_DIR.is_dir():
        for f in sorted(TEMPLATE_DIR.glob("*.json")):
            try:
                t = json.loads(f.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            rows.append({"name": t.get("name"), "tasks": len(t.get("tasks") or []),
                         "keys": t.get("keys"), "at": t.get("at")})
    return {"ok": True, "count": len(rows), "templates": rows,
            "dir": str(TEMPLATE_DIR)}



# ── 2026-11-01 一句话入口：**自然语言 → 蓝图 → 过目 → 落地** 一条命令 ──
# 主人不用记 op；说一句「按这个架构推进到落地：……」即可。
_GO_PREFIX = ("按这个架构", "按架构", "推进到落地", "执行到落地", "开始执行", "开始落地",
              "落地吧", "干吧", "推进吧")


def parse_intent(text: str) -> dict:
    """从一句话里剥出架构与"是否已确认"。"""
    raw = str(text or "").strip()
    if not raw:
        return {"ok": False, "error": "user_error: 说一句话（架构）"}
    approved = any(k in raw for k in ("已确认", "确认过", "直接跑", "直接落地", "不用问",
                                      "我已看过", "我看了"))
    arch = raw
    for p in _GO_PREFIX:
        arch = arch.replace(p, " ")
    arch = arch.replace("：", " ").replace(":", " ")
    arch = " ".join(arch.split())
    return {"ok": bool(arch), "arch": arch or raw, "approved": approved,
            "error": "" if arch else "剥完没有架构内容"}


def go(text: str, auto_approve: bool = False, max_rounds: int = 6, goal: str = "") -> dict:
    """一句话走完整链：解析 → 蓝图 →（已确认则过目）→ 跑到落地。

    **不过目不替你确认**：没写"已确认/直接跑"就只到蓝图，把 id 与过目命令还给你。
    """
    pi = parse_intent(text)
    if not pi.get("ok"):
        return pi
    m = make(pi["arch"], goal or pi["arch"])
    if not m.get("ok"):
        return m
    bid = m["id"]
    out = {"ok": True, "stage": "blueprint", "id": bid, "tasks": m.get("tasks"),
           "from_template": m.get("from_template"), "arch": pi["arch"][:200],
           "blueprint_md": m.get("md"),
           "pending_approval": not (auto_approve or pi.get("approved")),
           "next": "op=approve id=%s 然后 op=land" % bid}
    if out["pending_approval"]:
        return out
    ap = approve(bid)
    land_res = land(bid, max_rounds=max_rounds)
    out.update({"stage": "landed" if land_res.get("landed") else "land_attempted",
                "approve": ap, "land": {k: land_res.get(k) for k in
                                        ("landed", "rounds", "stuck", "template", "note")}})
    out["ok"] = bool(land_res.get("landed"))
    return out


def _new_id(arch: str) -> str:
    slug = "".join(ch for ch in str(arch)[:12] if ch.isalnum()) or "bp"
    return "%s-%s" % (slug.lower(), uuid.uuid4().hex[:6])


def _paths(bid: str) -> dict:
    return {"json": BP_DIR / (bid + ".json"), "md": BP_DIR / (bid + ".md"),
            "approved": BP_DIR / (bid + ".approved.json"),
            "mindmap": BP_DIR / (bid + ".mindmap.json"),
            "mmd": BP_DIR / (bid + ".mmd"), "runs": BP_DIR / (bid + ".runs.jsonl")}



def _task_ok(env: dict) -> tuple:
    """统一判据：信封 ok + 结果里的 ok/verdict。

    为什么不能只看一个字段：`selfscan` 回 `verdict=clean` 没有 `ok`；`cap_self` 回 `ok=True`；
    `inventory` 两个都有。**判据要按"有哪个看哪个"来**，否则会把干净当成失败。
    """
    if not isinstance(env, dict) or not env.get("ok"):
        return False, "信封 ok=False"
    gr = env.get("gbt_result") or {}
    res = gr.get("result") if isinstance(gr.get("result"), dict) else {}
    if res.get("ok") is False:
        return False, "结果 ok=False：%s" % str(res.get("error"))[:120]
    verdict = str(res.get("verdict") or "").lower()
    if verdict in ("bad", "fail", "failed", "error", "foreign_found", "drift"):
        return False, "verdict=%s" % verdict
    return True, verdict or ("ok" if res.get("ok") else "自然完成")


def make(arch: str, goal: str = "", reuse_template: bool = True) -> dict:
    """架构 → 蓝图（模板化生成，字段齐全；后续可用 LLM 增强，不依赖它也能跑）。"""
    arch = str(arch or "").strip()
    if not arch:
        return {"ok": False, "error": "user_error: 要架构（arch）"}
    bid = _new_id(arch)
    P = _paths(bid)
    P["json"].parent.mkdir(parents=True, exist_ok=True)
    tasks = []
    used_tpl, tpl_meta = None, {}
    if reuse_template:
        ft = find_template(arch)
        if ft.get("ok"):
            inst = instantiate_template(ft["template"], bid, arch)
            if inst.get("ok"):
                tasks = inst["tasks"]
                used_tpl = ft["template"].get("name")
                tpl_meta = {"template": used_tpl, "hit_keys": ft.get("hit")}
    if not tasks:
        tasks = []
        for pname, pdesc, items in PHASES:
            for cap, payload, accept in items:
                tasks.append({"id": "%s.%d" % (pname, len(tasks) + 1), "phase": pname,
                              "title": "%s · %s" % (pname, cap), "cap": cap,
                              "payload": payload, "acceptance": accept,
                              "needs": []})
    arch_tasks = [] if used_tpl else _arch_tasks(arch, len(tasks))
    tasks = tasks + arch_tasks
    bp = {"id": bid, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
          "arch_tasks": len(arch_tasks), "template": used_tpl, "template_meta": tpl_meta,
          "architecture": arch[:600], "goal": str(goal or arch)[:300],
          "phases": [{"name": p, "desc": d} for p, d, _ in PHASES] +
                    ([{"name": "专项", "desc": "按主人架构关键词追加的专项任务"}]
                     if arch_tasks else []),
          "tasks": tasks,
          "risks": ["派遣只限安全能力位（危险/转账另走票）",
                    "任何任务失败都如实记失败，不拿'差不多'当落地"],
          "acceptance": "全部任务 ok 且签名/真相判据通过 ⇒ 视为落地"}
    P["json"].write_text(json.dumps(bp, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = ["# 蓝图 %s" % bid, "", "**架构**：%s" % arch[:600], "",
             "**目标**：%s" % bp["goal"], "", "## 阶段与任务"]
    for ph, d, _ in PHASES:
        lines.append("\n### %s —— %s" % (ph, d))
        for t in [x for x in tasks if x["phase"] == ph]:
            lines.append("- `%s` %s（能力位 `%s`，验收：%s）"
                         % (t["id"], t["title"], t["cap"], t["acceptance"]))
    if arch_tasks:
        lines.append("\n### 专项 —— 按你的架构关键词追加")
        for t in arch_tasks:
            lines.append("- `%s` %s（能力位 `%s`，验收：%s）"
                         % (t["id"], t["title"], t["cap"], t["acceptance"]))
    lines += ["", "## 风险", *["- " + r for r in bp["risks"]],
              "", "## 验收", bp["acceptance"],
              "", "> 主人过目：`op=approve id=%s`；批准后**不再打扰**，自动派遣直至落地。" % bid]
    P["md"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"ok": True, "id": bid, "tasks": len(tasks), "arch_tasks": len(arch_tasks),
            "from_template": used_tpl,
            "blueprint": str(P["json"]),
            "md": str(P["md"]), "next": "op=approve id=%s（主人过目）" % bid}


def approve(bid: str) -> dict:
    """主人过目（**唯一允许的交互**）。批准后自动进入自主模式（不再打扰主人）。"""
    P = _paths(str(bid or ""))
    if not P["json"].is_file():
        return {"ok": False, "error": "user_error: 蓝图不存在：%s" % bid}
    P["approved"].write_text(json.dumps(
        {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "id": bid, "approved": True},
        ensure_ascii=False, indent=1), encoding="utf-8")
    try:
        from . import autonomy as AU
        AU.declare("蓝图 %s 已过目" % bid)
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "id": bid, "approved": True,
            "note": "已进入自主模式：此后除 danger/transfer 不再打扰主人"}


def mindmap(bid: str) -> dict:
    """分析推理：蓝图 → 任务图（含依赖与派遣顺序），并输出 mermaid 思维导图。"""
    P = _paths(str(bid or ""))
    if not P["json"].is_file():
        return {"ok": False, "error": "user_error: 蓝图不存在：%s" % bid}
    bp = json.loads(P["json"].read_text(encoding="utf-8"))
    tasks = bp.get("tasks") or []
    # 依赖：同阶段内按顺序串（勘察→…→固化 跨阶段也串），保证"先摸底再动手"
    order, prev = [], None
    for t in tasks:
        if prev:
            t["needs"] = [prev]
        order.append(t["id"])
        prev = t["id"]
    graph = {"id": bid, "order": order, "tasks": tasks, "edges": [
        {"from": t["needs"][0], "to": t["id"]} for t in tasks if t.get("needs")]}
    P["mindmap"].write_text(json.dumps(graph, ensure_ascii=False, indent=1), encoding="utf-8")
    mm = ["mindmap", "  root((%s))" % bid]
    for ph, _d, _i in PHASES:
        mm.append("    %s" % ph)
        for t in [x for x in tasks if x["phase"] == ph]:
            mm.append("      %s[%s]" % (t["cap"].replace("-", "_"), t["acceptance"][:12]))
    P["mmd"].write_text("\n".join(mm) + "\n", encoding="utf-8")
    return {"ok": True, "id": bid, "tasks": len(tasks), "order": order[:6],
            "mindmap": str(P["mindmap"]), "mermaid": str(P["mmd"]),
            "note": "依赖已串好：先勘察→设计→实现→验证→固化"}


def dispatch(bid: str, dry_run: bool = False, max_tasks: int = 30,
             force: bool = False, skip_tasks=None) -> dict:
    """派遣触手执行（拓扑序）。只跑**安全能力位**；危险/转账留票。

    `force=False`（默认）时**跳过已完成任务**（读 runs.jsonl 里 ok 过的），
    这样"跑到落地"可以一轮一轮续跑，不会重复劳动。
    """
    P = _paths(str(bid or ""))
    if not (P["json"].is_file() and P["approved"].is_file()):
        return {"ok": False, "error": "user_error: 蓝图未过目不派遣（先 op=approve）"}
    g = mindmap(bid)
    if not g.get("ok"):
        return g
    graph = json.loads(P["mindmap"].read_text(encoding="utf-8"))
    tasks = {t["id"]: t for t in graph["tasks"]}
    order = graph["order"][:max(1, int(max_tasks))]
    from ..caps_registry import BENIGN_CAPS
    import gbt_allinone as _G

    results, done, failed, skipped = [], set(), [], []
    # 已完成记录（续跑用）：runs.jsonl 里 ok=True 的任务
    if not force and P["runs"].is_file():
        for line in P["runs"].open(encoding="utf-8"):
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if r.get("ok") and r.get("task") in tasks:
                done.add(r["task"])
    t0 = time.time()
    with P["runs"].open("a", encoding="utf-8") as log:
        for tid in order:
            t = tasks[tid]
            meta = BENIGN_CAPS.get(t["cap"]) or {}
            ready = all(n in done for n in (t.get("needs") or []))
            row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "task": tid,
                   "cap": t["cap"], "phase": t["phase"]}
            if skip_tasks and tid in skip_tasks:
                row.update({"ok": False, "skipped": True, "why": "已标 stuck，本轮跳过"})
                skipped.append(tid)
                results.append(row)
                continue
            if tid in done and not force:
                row.update({"ok": True, "already": True, "why": "前几轮已完成"})
                results.append(row)
                continue
            if not ready:
                row.update({"ok": False, "skipped": True, "why": "依赖未完成"})
                skipped.append(tid)
                log.write(json.dumps(row, ensure_ascii=False) + "\n")
                results.append(row)
                continue
            if not meta:
                row.update({"ok": False, "why": "能力位不在注册表（未接线）"})
                failed.append(tid)
                log.write(json.dumps(row, ensure_ascii=False) + "\n")
                results.append(row)
                continue
            if dry_run:
                row.update({"ok": True, "dry_run": True})
                done.add(tid)
                log.write(json.dumps(row, ensure_ascii=False) + "\n")
                results.append(row)
                continue
            try:
                env = _G.run_task(t["cap"], t.get("payload") or {}, probe=False)
                ok, why = _task_ok(env)
                gr = env.get("gbt_result") or {}
                row.update({"ok": ok, "verdict_or_why": why,
                            "acceptance": t["acceptance"],
                            "summary": str(gr.get("result"))[:200]})
                if ok:
                    done.add(tid)
                else:
                    failed.append(tid)
            except Exception as e:  # noqa: BLE001
                row.update({"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:100])})
                failed.append(tid)
            log.write(json.dumps(row, ensure_ascii=False) + "\n")
            results.append(row)
    landed = (not failed) and (len(done) == len(order))
    return {"ok": landed, "id": bid, "dispatched": len(results), "done": len(done),
            "failed": len(failed), "skipped": len(skipped), "landed": landed,
            "seconds": round(time.time() - t0, 2),
            "failed_tasks": failed[:5], "runs": str(P["runs"]),
            "note": "只有全部任务 ok 才叫落地；失败会如实列"}




# ── 2026-11-01 研究环：卡点超出认知 ⇒ 全网查资料/论文 → 学习分析 → 重排任务 ──
# 主人：「遇到真实卡点不在你的认知范围之内就要懂得全网查阅资料，核心资料，以及论文，
#        学习分析推理然后再次生成思维导图任务指引给触手继续推进，然后固化焊死」
KNOW_DIR = ROOT / "state" / "knowledge"
RESEARCH_LEDGER = ROOT / "state" / "research-ledger.jsonl"

# 只读白名单（和 devour_auto 同一套口径：只发 URL、不传自己的数据）
_RESEARCH_ALLOW = ("raw.githubusercontent.com", "github.com", "arxiv.org",
                   "export.arxiv.org", "docs.python.org", "huggingface.co")
_DEFAULT_SOURCES = (
    "https://raw.githubusercontent.com/ggml-org/llama.cpp/master/README.md",
    "https://arxiv.org/abs/2210.17323",
)


def _classify_blocker(text: str) -> str:
    t = str(text or "").lower()
    if any(k in t for k in ("no module named", "missing", "needs_dependency")):
        return "dependency"
    if any(k in t for k in ("permission", "denied", "作用域", "票")):
        return "permission"
    if any(k in t for k in ("timeout", "timed out", "超时")):
        return "timeout"
    if any(k in t for k in ("not found", "不在", "不存在", "missing file")):
        return "missing_asset"
    if any(k in t for k in ("unwired", "未接线", "not implemented")):
        return "unwired"
    return "unknown"


def _fetch_readonly(url: str, timeout: float = 20.0, cap: int = 300_000) -> dict:
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").lower()
    if not any(host == a or host.endswith("." + a) for a in _RESEARCH_ALLOW):
        return {"ok": False, "error": "域名不在只读白名单：%s" % host}
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "gbt-blueprint/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(cap)
        return {"ok": True, "text": raw.decode("utf-8", "replace"), "bytes": len(raw)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:100])}


def _digest(text: str, topic: str, max_lines: int = 12) -> list:
    """从资料里摘与卡点相关的行（命中 topic 词优先，否则摘开头有信息量的行）。"""
    words = [w for w in str(topic).lower().replace("_", " ").split() if len(w) >= 3]
    lines = [ln.strip() for ln in str(text).split("\n") if ln.strip()]
    hit = [ln for ln in lines if any(w in ln.lower() for w in words)]
    picked = (hit or lines)[:max_lines]
    return [ln[:200] for ln in picked]


def research(topic: str, sources=None, max_sources: int = 2) -> dict:
    """查资料 → 落知识 → 出摘要。**只读、白名单、不发自己的数据。**"""
    topic = str(topic or "").strip() or "general blocker"
    srcs = list(sources or _DEFAULT_SOURCES)[:max(1, int(max_sources))]
    got, failed, digest = [], [], []
    for u in srcs:
        r = _fetch_readonly(u)
        if not r.get("ok"):
            failed.append({"url": u, "error": r.get("error")})
            continue
        d = _digest(r["text"], topic)
        digest.extend(d)
        got.append({"url": u, "bytes": r.get("bytes"), "lines": len(d)})
    KNOW_DIR.mkdir(parents=True, exist_ok=True)
    kid = "%s-%d" % ("".join(ch for ch in topic[:12] if ch.isalnum()).lower() or "topic",
                     int(time.time()) % 100000)
    path = KNOW_DIR / (kid + ".md")
    path.write_text("# 研究：%s\n\n**卡点类型**：%s\n\n**来源**：\n%s\n\n**摘录**：\n%s\n"
                    % (topic, _classify_blocker(topic),
                       "\n".join("- %s" % g["url"] for g in got) or "- （全部失败）",
                       "\n".join("- " + ln for ln in digest[:20])),
                    encoding="utf-8")
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "topic": topic[:200],
           "blocker": _classify_blocker(topic), "ok": bool(got),
           "sources": got, "failed": failed, "knowledge": str(path)}
    RESEARCH_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with RESEARCH_LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"ok": bool(got), "topic": topic[:200], "blocker": rec["blocker"],
            "sources": got, "failed": failed, "knowledge": str(path),
            "digest": digest[:6]}



# ── 2026-11-01 深推理：让**本机权重**读研究摘录，判断"这是什么问题、该怎么改任务" ──
# 主人要的不是"摘几行关键词"，是"学习分析推理"（在上下文允许的范围内）。
# 本机权重读不完长文，所以只喂**摘录 + 卡点类型**，要它输出可执行任务（JSON）。
DEEP_SYS = (
    "你是 GBT小土豆V8 的本机总指挥。给你一个卡点、它的类型、资料要点、候选能力位。"
    "请只输出一行 JSON：{\"diagnosis\":\"一句话根因\",\"tasks\":[{\"title\":\"...\","
    "\"cap\":\"候选里的能力位\",\"payload\":{},\"acceptance\":\"怎么算通过\"}]}。"
    "**必须至少给 1 条任务**；若资料不足以定位，就给一条记录类任务："
    "{\"title\":\"记录卡点并列出下一步核查项\",\"cap\":\"cap_self\",\"payload\":{\"op\":\"verify\"},"
    "\"acceptance\":\"账本可查\"}。最多 2 条，cap 只能从候选里挑。"
)



# ── 2026-11-01 深推理质量打分：**模型说的话有没有依据** ──
# 实测 7.6B 会输出"成年礼版 GBT-LLM 微软营"这种胡话。不能把它混进任务里。
# 判据：把诊断里的词与 摘录+卡点 做重合度，重合不上 ⇒ 标 unsupported，只用规则兜底。
def _tokens(text: str) -> set:
    t = str(text or "")
    out = set()
    for w in t.replace("_", " ").replace("-", " ").split():
        w = w.strip("，。、；：()（）[]【】\"'`“”").lower()
        if len(w) >= 2 and w.isascii():
            out.add(w)
    cjk = [ch for ch in t if "\u4e00" <= ch <= "\u9fff"]
    for i in range(len(cjk) - 1):
        out.add(cjk[i] + cjk[i + 1])
    return out


def _score_diagnosis(diagnosis: str, digest, topic: str = "") -> dict:
    """诊断与资料的重合度。`supported=False` ⇒ 视为无依据（只用兜底）。"""
    d_tok = _tokens(diagnosis)
    src = _tokens(" ".join(str(x) for x in (digest or [])) + " " + str(topic or ""))
    if not d_tok:
        return {"supported": False, "score": 0.0, "hits": [], "why": "诊断为空"}
    hits = sorted(d_tok & src)
    score = len(hits) / max(1, len(d_tok))
    return {"supported": bool(hits) and score >= 0.08,
            "score": round(score, 3), "hits": hits[:8],
            "why": "有依据" if hits else "与资料零重合（疑似胡话）"}


def deep_reason(topic: str, digest, candidates=None, timeout: float = 240.0) -> dict:
    """用本机权重把"摘录"变成"可执行任务"。**失败/超时就退回规则兜底**，不装成功。"""
    topic = str(topic or "")[:300]
    digest = list(digest or [])[:10]
    cands = list(candidates or [
        "cap_self", "trunk_cover", "selfscan", "comfy_native", "devour_auto",
        "commander", "pulse_core", "orchestration", "body_sense", "inventory"])
    prompt = ("卡点：%s\n类型：%s\n\n资料要点：\n%s\n\n候选能力位：%s"
              % (topic, _classify_blocker(topic),
                 "\n".join("- " + str(d)[:180] for d in digest),
                 ", ".join(cands)))
    out = {"ok": False, "diagnosis": "", "tasks": [], "source": "fallback"}
    try:
        from .. import energy_core as EC
        r = EC.think([{"role": "system", "content": DEEP_SYS},
                      {"role": "user", "content": prompt}],
                     max_tokens=260, timeout=timeout, label="blueprint.deep")
        if not r.get("ok"):
            return {**out, "error": str(r.get("error"))[:120]}
        import re as _re
        m = _re.search(r"\{[\s\S]*\}", r.get("text") or "")
        d = json.loads(m.group(0)) if m else {}
        diagnosis = str(d.get("diagnosis") or "")[:200]
        tasks = []
        for t in (d.get("tasks") or [])[:2]:
            cap = str(t.get("cap") or "")
            if cap not in cands:
                continue
            tasks.append({"title": str(t.get("title") or "深推理任务")[:80],
                          "cap": cap, "payload": t.get("payload") or {},
                          "acceptance": str(t.get("acceptance") or "执行通过")[:80]})
        sc = _score_diagnosis(diagnosis, digest, topic)
        if not sc["supported"]:
            # 诊断与资料对不上 ⇒ **不采信**，交给规则兜底（来源如实标）
            return {"ok": True, "diagnosis": diagnosis, "tasks": [],
                    "source": "energy_core_unsupported", "quality": sc,
                    "ms": r.get("ms")}
        return {"ok": True, "diagnosis": diagnosis, "tasks": tasks,
                "source": "energy_core", "quality": sc, "ms": r.get("ms")}
    except Exception as e:  # noqa: BLE001
        return {**out, "error": "%s: %s" % (type(e).__name__, str(e)[:100])}


def _append_research_tasks(bid: str, blocker_text: str, research_res: dict) -> dict:
    """把研究结果变成**新任务**追加进思维导图（重排任务指引），并留痕。"""
    P = _paths(str(bid or ""))
    g = mindmap(bid)
    if not g.get("ok"):
        return g
    graph = json.loads(P["mindmap"].read_text(encoding="utf-8"))
    n = len([t for t in graph["tasks"] if str(t["id"]).startswith("研究")])
    tid = "研究.%d" % (n + 1)
    task = {"id": tid, "phase": "研究",
            "title": "研究 · %s" % _classify_blocker(blocker_text),
            "cap": "orchestration",
            "payload": {"op": "record", "action": "scan", "target": "research",
                        "detail": "卡点研究：%s" % blocker_text[:120],
                        "evidence": research_res.get("knowledge")},
            "acceptance": "研究结论已落知识库并记账",
            "needs": []}
    graph["tasks"].append(task)
    graph["order"].append(tid)
    if graph["order"][-2:]:
        graph["edges"].append({"from": graph["order"][-2], "to": tid})
    P["mindmap"].write_text(json.dumps(graph, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "task": tid, "cap": task["cap"]}



def _fallback_deep_task(topic: str) -> dict:
    """**规则兜底**：本机权重给不出任务时，按卡点类型落一条**真能执行**的任务。

    为什么不硬让模型"编一条"：24 条实测里它两次都给 `tasks: []`，
    逼它编会得到更坏的东西（假诊断）。所以规则兜底 + 如实标 `source=fallback_rule`。
    """
    kind = _classify_blocker(topic)
    table = {
        "dependency": {"title": "记录并核对依赖清单（缺什么装什么）", "cap": "cap_self",
                       "payload": {"op": "verify"}, "acceptance": "能力位无漂移，缺依赖已记录"},
        "unwired": {"title": "列全未接线节点并登记", "cap": "comfy_native",
                    "payload": {"op": "coverage"}, "acceptance": "未接线清单可读"},
        "timeout": {"title": "记录超时并复跑一次", "cap": "pulse_core",
                    "payload": {"op": "verify"}, "acceptance": "机制四条全过"},
        "permission": {"title": "记录权限缺口（等票，不绕过）", "cap": "autonomy",
                       "payload": {"op": "status"}, "acceptance": "契约状态可读"},
        "missing_asset": {"title": "记录缺失资产并核对清单", "cap": "inventory",
                          "payload": {}, "acceptance": "清单无异物"},
    }
    t = table.get(kind) or {"title": "记录卡点并列出下一步核查项", "cap": "orchestration",
                            "payload": {"op": "panel", "limit": 5},
                            "acceptance": "账本可追（但结论不足以给出动作）"}
    return {"ok": True, "source": "fallback_rule", "diagnosis": "规则判类：%s" % kind,
            "tasks": [dict(t)]}


def _append_deep_tasks(bid: str, topic: str, deep: dict) -> dict:
    """把深推理给出的任务写进思维导图（重排任务指引）。没有任务就什么都不做。"""
    tasks = deep.get("tasks") or []
    if not tasks:
        return {"ok": False, "why": "深推理没给出可执行任务"}
    P = _paths(str(bid or ""))
    g = mindmap(bid)
    if not g.get("ok"):
        return g
    graph = json.loads(P["mindmap"].read_text(encoding="utf-8"))
    base = len([t for t in graph["tasks"] if str(t["id"]).startswith("深推理")])
    for i, t in enumerate(tasks):
        tid = "深推理.%d" % (base + i + 1)
        graph["tasks"].append({"id": tid, "phase": "深推理", "title": t["title"],
                               "cap": t["cap"], "payload": t.get("payload") or {},
                               "acceptance": t.get("acceptance") or "执行通过",
                               "needs": []})
        graph["order"].append(tid)
        if graph["order"][-2:]:
            graph["edges"].append({"from": graph["order"][-2], "to": tid})
    P["mindmap"].write_text(json.dumps(graph, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "added": len(tasks),
            "caps": [t["cap"] for t in tasks]}



# ── 2026-11-01 死循环保护：**连续两轮失败的任务标 stuck 并剔除**，不许无限拖 ──
# 主人要"跑到落地"，但一条永远不可能通过的任务会把链条拖死。
# 处理：标 stuck、从后续轮次跳过、如实记在账本与 status 里 —— **不是悄悄吞掉**。
STUCK_ROUNDS = 2


def _stuck_path(bid: str):
    return BP_DIR / (str(bid) + ".stuck.json")


def _load_stuck(bid: str) -> dict:
    f = _stuck_path(bid)
    if f.is_file():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {"counts": {}, "stuck": []}


def _save_stuck(bid: str, d: dict) -> None:
    try:
        BP_DIR.mkdir(parents=True, exist_ok=True)
        _stuck_path(bid).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _mark_stuck(bid: str, failed_tasks) -> list:
    d = _load_stuck(bid)
    newly = []
    for tid in failed_tasks or []:
        n = int(d["counts"].get(tid, 0)) + 1
        d["counts"][tid] = n
        if n >= STUCK_ROUNDS and tid not in d["stuck"]:
            d["stuck"].append(tid)
            newly.append(tid)
    _save_stuck(bid, d)
    for tid in newly:
        try:
            from .. import orchestration as _OB
            _OB.record("fix", "blueprint.stuck",
                       detail="任务 %s 连续 %d 轮失败 ⇒ 标 stuck 并从后续轮剔除（不是悄悄吞掉）"
                              % (tid, STUCK_ROUNDS),
                       evidence="state/blueprints/%s.stuck.json" % bid)
        except Exception:  # noqa: BLE001
            pass
    return newly


def land(bid: str, max_rounds: int = 6, force_rounds: bool = False,
         research_blockers: bool = True) -> dict:
    """**跑到落地**：一轮轮 dispatch，直到 `landed` 或需要票/被中断。

    主人 2026-11-01：「从架构蓝图用户确认之后就开始执行直到项目落地，中途除非用户打断
    要不然严禁停下，自己内部沟通写作执行到项目落地」。

    三条内部纪律：
      1. **不停**：有失败就下一轮重试（只重试失败项，已完成的不重跑）；
      2. **不问**：全程不找主人（除 danger/transfer 需票，那种情况标 blocked 并说明）；
      3. **留痕**：每一轮都记进编排账本与 runs.jsonl，重启可续。
    """
    rounds = []
    P = _paths(str(bid or ""))
    for i in range(max(1, int(max_rounds))):
        st = status(bid)
        if st.get("landed"):
            return {"ok": True, "id": bid, "landed": True, "rounds": rounds,
                    "note": "已落地（第 %d 轮前就已满足）" % (i + 1)}
        stuck_now = _load_stuck(bid).get("stuck") or []
        d = dispatch(bid, force=force_rounds, skip_tasks=stuck_now)
        rounds.append({"round": i + 1, "dispatched": d.get("dispatched"),
                       "done": d.get("done"), "failed": d.get("failed"),
                       "landed": d.get("landed"), "failed_tasks": d.get("failed_tasks")})
        newly_stuck = _mark_stuck(bid, d.get("failed_tasks") or [])
        if newly_stuck:
            rounds[-1]["stuck"] = newly_stuck
        _log_round(bid, rounds[-1])
        if d.get("landed"):
            tpl = save_template(bid)
            return {"ok": True, "id": bid, "landed": True, "rounds": rounds,
                    "template": tpl if tpl.get("ok") else None,
                    "note": "落地（共 %d 轮）" % (i + 1)}
        # 需要票才能继续 ⇒ 停下来找主人（这是**唯一**允许的打扰）
        need_ticket = _needs_ticket(d.get("failed_tasks") or [])
        if need_ticket:
            return {"ok": False, "id": bid, "landed": False, "blocked": True,
                    "rounds": rounds, "need_ticket": need_ticket,
                    "note": "只剩需要票的任务（危险能力/转账）⇒ 按契约找主人"}
        force_rounds = False     # 后续轮只重试失败项
        # 卡点超出认知 ⇒ **自己去查资料/论文 → 学习 → 重排任务**（不问主人）
        if research_blockers and d.get("failed"):
            topic = " ".join([str(x) for x in (d.get("failed_tasks") or [])[:3]]) or "unknown blocker"
            rr = research(topic, max_sources=2)
            rounds[-1]["research"] = {"ok": rr.get("ok"), "blocker": rr.get("blocker"),
                                      "sources": len(rr.get("sources") or []),
                                      "knowledge": rr.get("knowledge")}
            if rr.get("ok"):
                deep = deep_reason(topic, rr.get("digest") or [])
                rounds[-1]["research"]["deep"] = {
                    "ok": deep.get("ok"), "source": deep.get("source"),
                    "diagnosis": deep.get("diagnosis"),
                    "quality": deep.get("quality"),
                    "tasks": len(deep.get("tasks") or [])}
                if not deep.get("tasks"):
                    fb = _fallback_deep_task(topic)
                    deep = {**fb, "diagnosis": deep.get("diagnosis") or fb.get("diagnosis"),
                        "quality": deep.get("quality"),
                        "source_was": deep.get("source")}
                    rounds[-1]["research"]["deep"] = {
                        "ok": True, "source": "fallback_rule",
                        "diagnosis": deep.get("diagnosis"),
                        "tasks": len(deep.get("tasks") or [])}
                _append_deep_tasks(bid, topic, deep)
                if not deep.get("tasks"):
                    _append_research_tasks(bid, "%s %s" % (topic, rr.get("digest")), rr)
    st = _load_stuck(bid)
    return {"ok": False, "id": bid, "landed": False, "rounds": rounds,
            "stuck": st.get("stuck") or [],
            "note": "跑了 %d 轮仍未落地（如实报，不装完成）；stuck=%s（已从后续轮剔除）"
                    % (len(rounds), st.get("stuck") or [])}


def _log_round(bid: str, row: dict) -> None:
    try:
        from .. import orchestration as _OB
        _OB.record("run", "blueprint.land", detail="%s 第%d轮 done=%s failed=%s landed=%s"
                   % (bid, row.get("round"), row.get("done"), row.get("failed"), row.get("landed")),
                   evidence="state/blueprints/%s.runs.jsonl" % bid)
    except Exception:  # noqa: BLE001
        pass


def _needs_ticket(failed_tasks: list) -> list:
    """失败的里面，有没有**只有票才能推进**的（危险能力/转账）。"""
    if not failed_tasks:
        return []
    P = None
    try:
        from ..security import policy as _P
        out = []
        for tid in failed_tasks:
            # 从 mindmap 找这个任务对应的能力位
            mm = list(BP_DIR.glob("*.mindmap.json"))
            cap = ""
            for f in mm:
                try:
                    g = json.loads(f.read_text(encoding="utf-8"))
                except Exception:  # noqa: BLE001
                    continue
                for t in (g.get("tasks") or []):
                    if t.get("id") == tid:
                        cap = t.get("cap")
                        break
            if cap:
                scopes = list(_P.evaluate(cap, {}).scopes)
                if any(s in ("process_execute", "remote_device", "privacy_read",
                             "osint_private", "deploy_publish", "deploy_force",
                             "external_llm", "data_export") for s in scopes):
                    out.append({"task": tid, "cap": cap, "scopes": scopes})
        return out
    except Exception:  # noqa: BLE001
        return []


def status(bid: str) -> dict:
    P = _paths(str(bid or ""))
    if not P["json"].is_file():
        # 没有 id ⇒ 列全部蓝图
        items = []
        if BP_DIR.is_dir():
            for f in sorted(BP_DIR.glob("*.json")):
                if f.name.endswith((".approved.json", ".mindmap.json")):
                    continue
                try:
                    items.append(json.loads(f.read_text(encoding="utf-8")).get("id"))
                except Exception:  # noqa: BLE001
                    continue
        return {"ok": True, "blueprints": items, "count": len(items)}
    bp = json.loads(P["json"].read_text(encoding="utf-8"))
    rows = []
    if P["runs"].is_file():
        for line in P["runs"].open(encoding="utf-8"):
            try:
                rows.append(json.loads(line))
            except Exception:  # noqa: BLE001
                continue
    done = sum(1 for r in rows if r.get("ok"))
    total = len(bp.get("tasks") or [])
    return {"ok": True, "id": bid, "tasks": total,
            "approved": P["approved"].is_file(), "attempted": len(rows),
            "done": done, "failed": sum(1 for r in rows if not r.get("ok")),
            "stuck": (_load_stuck(bid).get("stuck") or []),
            "progress": round(done / total, 3) if total else 0.0,
            "landed": bool(rows) and done == total and all(r.get("ok") for r in rows)}


def run(op: str = "status", **kw) -> dict:
    op = str(op or "status").lower()
    bid = str(kw.get("id") or "")
    if op == "make":
        return make(str(kw.get("arch") or ""), str(kw.get("goal") or ""))
    if op == "approve":
        return approve(bid)
    if op == "mindmap":
        return mindmap(bid)
    if op == "dispatch":
        return dispatch(bid, dry_run=bool(kw.get("dry_run")), max_tasks=int(kw.get("max_tasks") or 30))
    if op == "deep":
        r = research(str(kw.get("topic") or ""))
        d = deep_reason(str(kw.get("topic") or ""), r.get("digest") or [])
        if not d.get("tasks"):
            d = _fallback_deep_task(str(kw.get("topic") or ""))
        return {"ok": bool(d.get("ok")), "research": {"ok": r.get("ok"),
                "sources": len(r.get("sources") or []), "knowledge": r.get("knowledge")},
                "deep": d}
    if op in ("go", "intent"):
        return go(str(kw.get("text") or kw.get("arch") or ""),
                  auto_approve=bool(kw.get("auto_approve") or kw.get("approve")),
                  max_rounds=int(kw.get("max_rounds") or 6),
                  goal=str(kw.get("goal") or ""))
    if op == "templates":
        return templates()
    if op == "save_template":
        return save_template(bid)
    if op == "research":
        return research(str(kw.get("topic") or ""))
    if op == "land":
        return land(bid, max_rounds=int(kw.get("max_rounds") or 6),
                    force_rounds=bool(kw.get("force_rounds")))
    if op == "status":
        return status(bid)
    return {"ok": False, "error": "blueprint 不认 op=%s（make/approve/mindmap/dispatch/status）" % op}
