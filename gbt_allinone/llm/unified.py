# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 统一大模型入口（Owner 2026-09-19 拍：**全部统一大模型**）。

为什么要有这一层（读数）：改造前框架内有**五条**各自直连模型通道的路径 ——
  `api.py:240` · `autopilot.py:65` · `pipeline.py:93` · `devour.py:636` · `drama.py:170`
同一个能力五张脸 ⇒ 换模型、调重试、加审计、查"谁在出网"都要改五处，且**必然漂移**
（§2.2 的 40/95 覆盖率漂移就是这个形态）。

本模块是**唯一实现**：provider 解析、重试、审计落点、返回形态归一，全在这一处。

分工（Owner 口径）：**通道统一** + **各模块只管自己那段的细节**
（提示词、语义校验、字段契约）。模块不许再自己 import `bridge` 直连。

授权口径：`external_llm` 人工授权门装在 **cap 边界**（`api.run_task("llm_chat")`），
不在这一层 —— 因为框架内部调用（autopilot/pipeline/devour/drama）走的是主人会话，
与 `llm_chat` 对外入口是**同一条实现、不同入口**。要不要把门也装到内部调用上，
属于安全策略变更，**待 Owner 拍**（2026-09-19 已如实登记为观察项）。
"""
from __future__ import annotations

import time

PATH = "llm_unified"

# 统一大模型（Owner 2026-09-19 指定 · Custom Provider）：
#   Base URL https://apihub.agnes-ai.com/v1 · 模型 agnes-2.5-flash
# 口径出处是 `cloud_llm._KEY_CHAIN` 的第一行（**不在这里再写一份地址** ——
# 地址只有一处真相；本处只声明"期望落到谁身上"并**如实报漂移**）。
EXPECTED_PROVIDER = "agnes"
EXPECTED_MODEL = "agnes-2.5-flash"


def ask(prompt, system="", model=None, temperature=0.7, max_tokens=2000,
        timeout=60, purpose="generic", provider=None, **_ignored):
    """统一调用口。返回与旧 `bridge.chat` 同形（ok/reply/provider/model），多一个 `path`。

    审计只落**元数据**（谁调的、哪个 provider/model、多少字符、耗时、成没成），
    **不落提示词与回复正文** —— 与"正文不入档"的既有纪律一致。

    🔴 2026-10-14 修（与下面 purpose 那次同源的断点）：`provider` 原先落进 `**_ignored`
    ⇒ **框架入口点名车道从来没通过**（实测 `cap llm_chat` 点名 potato 仍落 agnes，
    回执 `expected=agnes`）。现在显式接住并透传给 `bridge.chat`（它再给 cloud_llm 的 `_prefer`）。
    不点名（None）时下游 params 不带该键 ⇒ 行为与改动前一致。
    """
    from . import bridge as LB
    t0 = time.time()
    # 🔴 2026-10-12 修（闭环断点就在这里 · 实测）：`purpose` 原来**只写进审计、不传下去** ——
    #    ⇒ `cloud_llm.run()` 的 `_purpose` 恒为 "" ⇒ 按 purpose 的两条机制全部失效：
    #      ① 触手维度独立密钥路由（`_PURPOSE_ROUTING_MAP`）；
    #      ② 2026-10-12 新加的「内部结构化调用跳过 fact_gate / policy_gate 直答门」守卫。
    #    实测病案：`semantic_route.choose()` 明传 `purpose="semantic_route"`，到这里被吞掉，
    #    于是它的 JSON 请求仍被 fact_gate 拦成散文 ⇒ 主路整条失效、永远降级到词表辅路。
    #    下游 `bridge.chat` **本来就支持 purpose**（bridge.py:46,55 透传 cloud_llm）——
    #    断点只在这一处，故只补这一处，不另做第二份实现。
    r = LB.chat(prompt, system=system, model=model, temperature=temperature,
                max_tokens=max_tokens, timeout=timeout,
                purpose=purpose or "generic", provider=provider)
    if not isinstance(r, dict):
        r = {"ok": False, "error": f"桥返回非 dict: {type(r).__name__}"}
    # 漂移如实报：统一大模型说好是 agnes-2.5-flash，落到别人身上要看得见（不静默降级）。
    via = str(r.get("provider") or "")
    drift = bool(r.get("ok")) and via != EXPECTED_PROVIDER
    try:
        from ..store import audit
        audit("llm_unified", {
            "purpose": purpose or "generic",
            "ok": bool(r.get("ok")),
            "provider": via or None,
            "model": r.get("model"),
            "expected": EXPECTED_PROVIDER,
            "drift": drift,
            "prompt_chars": len(str(prompt or "")),
            "reply_chars": len(str(r.get("reply") or "")),
            "ms": int((time.time() - t0) * 1000),
        })
    except Exception:  # noqa: BLE001
        pass          # 审计失败不许反向打断调用；但也不吞掉调用结果
    return {**r, "path": PATH, "expected": EXPECTED_PROVIDER, "drift": drift}


# 旧调用点写的是 `X.chat(...)`：保留同名别名，原地可换，不必改参数。
chat = ask


def status():
    """统一口自述：谁在使用它、唯一实现落在哪。"""
    return {"ok": True, "path": PATH,
            "impl": "gbt_allinone/llm/unified.py::ask",
            "chain_below": "gbt_allinone/llm/bridge.py -> llm/cloud_llm.py",
            "note": "框架内所有模块必须经此口调用模型；模块自己 import bridge 视为漂移。",
            "gate": "external_llm 人工授权门装在 cap 边界（api.run_task('llm_chat')）"}
