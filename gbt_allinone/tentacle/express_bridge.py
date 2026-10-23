# -*- coding: utf-8 -*-
"""触手大桥 · 直达（A 向）—— **重造版**

> 🔴 **件头声明（照仓规，不许含糊）**：本件是**重造版**，依据是主人手上的
> 《GBT小土豆V8 · 触手双向绑定架构（表格版）》（2026-10-12）——**不是原件**。
> 原件（同名 `tentacle/express_bridge.py`）**不在本仓、也不在 V9 树**（我搜过），主人已确认
> "这两家还没进训练仓"。若原件回来，**以原件为准**，本件让位。

## 为什么要有它（主人令，逐字）
「把触手双向绑定，使其比传统大模型跑得快——传统模型跑一个任务要跑一圈没用的，
  现在直接通过触手大桥**直达**」。

**"直达"的定义**：传统模型每来一个任务，先让主模型**完整推理一次**去猜"该走哪根触手"——
那一整圈就是"没用的"。大桥把它换成「**先快尺、再直达**」：快尺打分命中即派单，
**不烧主模型一次完整推理**。

## A 向链路（表 2 · 逐跳照抄设计）
    intent → route() 命中能力名 → bridge.call_capability() → api.run_task()
    ⚠️ **统一门 run_task 照旧生效**：权限门 / 审计 / 钢印 / 禁用名单，触手不因"是手"免检。
    ⚠️ **禁环**：tentacle → tentacle 硬拒（守卫在 `bridge.call_capability` 自己身上，本件**只透传**，
       不另造第二套守卫）。

## 三层回退（表 3 · 快到慢，层间可回退，逐层如实标 degraded）
    ① express  单遍打分快尺（`llm/decision`）  需凭据 → **当前未配 ⇒ 如实标 degraded、回退②，不阻断**
    ② semantic 本地语义路由（`semantic_route.route`） 本地毫秒级 · 无凭据 · **置 degraded + reason**
    ③ heuristic 方法名字面匹配（`bridge.route_method`） 本地毫秒级 · 无凭据 · **恒标 degraded=true**

## 方向层
`tentacle/direction.analyze` 判「读/写、录/放」方向歧义；**判不出返回 None，不硬猜**（上层不偏置）。

## 纪律
  · **只读 + 路由**：本件自己不写盘、不执行外部命令；执行一律交给 `bridge.call_capability` → 统一门。
  · **不许静默**：哪一层没跑/没凭据/降级，一律写进 `degraded` 与 `reason`，**不许长成"成功"**。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

# 三层定义（表 3 逐条：层名 / 引擎 / 判什么 / 凭据 / 降级口径）
LAYERS = (
    {"层": "① express", "引擎": "Decision-1 快尺（llm.decision.decide）",
     "判什么": "多选一：候选触手 → 命中哪一个", "延迟": "0.17s(P50)",
     "需要凭据": "OPENROUTER_API_KEY", "降级": "未配/失败 ⇒ 静默回退②，不阻断"},
    {"层": "② semantic", "引擎": "本地语义路由（semantic_route.route）",
     "判什么": "单一路由权威（n-gram + 语义 + 方向判别层）", "延迟": "本地毫秒级",
     "需要凭据": "无", "降级": "读到即用；置 degraded + reason"},
    {"层": "③ heuristic", "引擎": "方法名字面匹配（bridge.route_method）",
     "判什么": "方法名字面匹配", "延迟": "本地毫秒级",
     "需要凭据": "无", "降级": "恒标 degraded=true"},
)


def layers() -> dict:
    """三层现读（人可读 / 面板可读）。"""
    return {"ok": True, "层数": len(LAYERS), "三层": [dict(x) for x in LAYERS],
            "口径": "快到慢；层间可回退；**每一层的降级都要如实标，不许长成成功**"}


def _direction_of(intent: str) -> dict:
    """方向层：判读/写、录/放方向歧义。**判不出就如实说判不出，不硬猜。**"""
    try:
        from . import direction as _d
        got = _d.analyze(intent) or {}
        if not got.get("direction"):
            return {"ok": False, "判出": None, "理由": "方向层判不出（不硬猜，上层不偏置）"}
        return {"ok": True, "判出": got.get("direction"), "偏置": _d.bias(got["direction"])}
    except Exception as e:                                   # noqa: BLE001
        return {"ok": False, "判出": None, "理由": "方向层不可用：%s" % type(e).__name__}


def _candidates(limit: int = 80) -> dict:
    """候选集**现读**（她自己查，不等人给）：能力位表 → {名字: 描述}。

    为什么现读：候选人只能从册上取（注册表是唯一真源）；写死候选 =
    下一条新能力位进来它就判不出——那是"死的快尺"。
    """
    cand: dict = {}
    try:
        from .. import caps_registry as _cr
        benign = getattr(_cr, "BENIGN_CAPS", {}) or {}
        for n, d in list(benign.items())[:limit]:
            desc = ""
            if isinstance(d, dict):
                desc = str(d.get("desc") or "")
            cand[str(n)] = desc[:90] or str(n)
    except Exception:                                        # noqa: BLE001
        pass
    return cand


def _layer1(intent: str) -> dict:
    """① 单遍打分快尺：**现读候选 → 打分 → 命中即直达**。

    缺件 ⇒ 如实报"件不在"；候选空 ⇒ 如实报"无可判候选"；都不阻断，回退②。
    **不硬编候选、不假命中**。
    """
    try:
        from ..llm import decision as _dec
    except Exception as e:                                   # noqa: BLE001
        return {"hit": None, "degraded": True, "engine": None,
                "reason": "① 快尺不可用：llm/decision %s（本仓未接）" % type(e).__name__}
    cand = _candidates()
    if not cand:
        return {"hit": None, "degraded": True, "engine": None,
                "reason": "① 快尺无可判候选（注册表现读为空）—— 候选从册上取，不硬编"}
    try:
        r = _dec.decide_choice(intent, cand) or {}           # ← 位置参数：criteria
        res = r.get("result") or {}
        hit = res.get("choice") or None
        return {"hit": hit, "degraded": False, "engine": r.get("engine"),
                "confidence": res.get("confidence"),
                "候选数": len(cand),
                "reason": "" if hit else "① 快尺没给出命中 ⇒ 回退②"}
    except Exception as e:                                   # noqa: BLE001
        return {"hit": None, "degraded": True, "engine": None,
                "reason": "① 快尺失败：%s: %s ⇒ 回退②（不阻断）" % (type(e).__name__, str(e)[:80])}


def route(intent: str, mode: str = "auto") -> dict:
    """三层回退路由：只回答「该派给谁」，**不执行**。

    返回里必须带 `走哪层` 与 `degraded` —— 哪层没跑成，**不许长得像成功**。
    """
    intent = str(intent or "").strip()
    if not intent:
        return {"ok": False, "fail_closed": True, "error": "没给 intent（拿什么路由？）"}

    desc = _direction_of(intent)
    trail: list = []

    l1 = _layer1(intent)
    trail.append({"层": "① express", "hit": l1["hit"], "degraded": l1["degraded"],
                  "reason": l1["reason"]})
    if l1["hit"]:
        return {"ok": True, "走哪层": "① express", "命中": l1["hit"], "degraded": False,
                "方向": desc, "trail": trail, "口径": "快尺命中即直达，**不烧主模型一次完整推理**"}

    try:
        from .. import semantic_route as _sr
        r2 = _sr.route(intent, mode=mode) or {}
        hit2 = r2.get("method") or r2.get("kind") or r2.get("命中")
        trail.append({"层": "② semantic", "hit": hit2,
                      "degraded": True,
                      "reason": r2.get("reason") or "② 语义路由可用，但按件**置 degraded + reason**"})
        if hit2:
            return {"ok": True, "走哪层": "② semantic", "命中": hit2, "degraded": True,
                    "方向": desc, "trail": trail, "原读数": r2}
    except Exception as e:                                   # noqa: BLE001
        trail.append({"层": "② semantic", "hit": None, "degraded": True,
                      "reason": "② 不可用：%s" % type(e).__name__})

    try:
        from . import bridge as _b
        r3 = _b.route_method(intent) or {}
        hit3 = r3.get("method") or r3.get("kind") or r3.get("命中")
        trail.append({"层": "③ heuristic", "hit": hit3, "degraded": True,
                      "reason": "③ 恒标 degraded=true（件里写死）"})
        if hit3:
            return {"ok": True, "走哪层": "③ heuristic", "命中": hit3, "degraded": True,
                    "方向": desc, "trail": trail, "原读数": r3}
    except Exception as e:                                   # noqa: BLE001
        trail.append({"层": "③ heuristic", "hit": None, "degraded": True,
                      "reason": "③ 不可用：%s" % type(e).__name__})

    return {"ok": False, "走哪层": None, "命中": None, "degraded": True,
            "方向": desc, "trail": trail,
            "口径": "**三层都没命中 = 没命中**，不许编一个出来"}


def express(intent: str, payload: dict | None = None) -> dict:
    """直达：路由 + 执行。执行**只经 bridge.call_capability → 统一门**（本件不自造守卫）。

    ⚠️ 本函数走的是 **route()（含"猜"）** —— 主人令 2026-10-13
    「全部以触手来实现，砍掉'理由'这个不定因数」之后，**主路改为 `direct()`**：
    **指名派单、不猜**。本函数保留为"人话入口"（可选加速），**但它判歪过**（`codex_status`），
    所以它**不是主路**，判出来的东西**必须当"提名"而不是决定**。
    """
    r = route(intent)
    if not r.get("ok") or not r.get("命中"):
        return {"ok": False, "stage": "route", "路由": r,
                "口径": "没命中就不派单（fail-closed），不猜一个能力去跑"}
    kind = str(r["命中"])
    try:
        from . import bridge as _b
        call = _b.call_capability(kind, payload or {})
    except Exception as e:                                   # noqa: BLE001
        return {"ok": False, "stage": "call", "路由": r,
                "error": "调用失败：%s: %s" % (type(e).__name__, str(e)[:120])}
    return {"ok": bool(call.get("ok", call.get("status") == "ok")), "stage": "done",
            "路由": r, "能力位": kind, "调用": call,
            "纪律": "统一门 run_task 照旧生效（权限门/审计/钢印/禁用名单）；禁环守卫在 call_capability 内"}


def direct(kind: str, payload: dict | None = None) -> dict:
    """**确定性主路**：指名派单，直达，**不猜**。

    主人令（2026-10-13）：「全部以触手来实现，砍掉『理由』这个不定因数」。

    为什么这条是主路：`route()` 那套是**猜**——实测它把"看屏幕"判成 `codex_status`，
    语义层还偷偷调外部 LLM（耗 6 秒、`provider: agnes`），危险位 `data_hijack` 甚至排到过第一。
    **器官是她的，她知道要哪个**；不确定的猜，不该夹在她和执行之间。

    执行一律经 `bridge.call_capability` → **统一门 run_task**（权限门/审计/钢印/禁用名单照旧）。
    """
    kind = str(kind or "").strip()
    if not kind:
        return {"ok": False, "fail_closed": True,
                "error": "没给能力名 —— 指名直达**不许猜**（要猜请走 express，并自担不确定性）"}
    try:
        from . import bridge as _b
        call = _b.call_capability(kind, payload or {})
    except Exception as e:                                   # noqa: BLE001
        return {"ok": False, "stage": "call", "能力位": kind,
                "error": "调用失败：%s: %s" % (type(e).__name__, str(e)[:120])}
    return {"ok": bool(call.get("ok", call.get("status") == "ok")), "stage": "done",
            "路径": "确定性直达（不猜）", "能力位": kind, "调用": call,
            "纪律": "统一门 run_task 照旧生效；危险动作/付款由护栏+人工审核兜底"}
