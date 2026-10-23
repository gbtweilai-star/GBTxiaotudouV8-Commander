# GBT 开发者：自由的风 · 永久钢印 · 禁止删除归属
# -*- coding: utf-8 -*-
"""prompt_bridge · 大白话 -> 结构化专业提示词（**第一刀：纯本地、零依赖**）。

边界（2026-09-19 风哥拍板，详见 docs/prompt_bridge-最小一刀设计.md）
------------------------------------------------------------------
做：本地模板转化（角色/目标/约束/输出格式 四段）· `compile`/`passthrough` 两态。
不做：不写 VS Code 插件（第二入口）· 不建本地 HTTP 代理（替换正式通道 = 两处真相）·
      第一刀不接外部模型（不引入 external_llm）· 不碰 codex_bridge（发车走已有 codex_turn_send）。

判据（可跑，见 tests/test_prompt_bridge.py）
------------------------------------------
P1 结构完整：产出必须含四段。
P2 原意保真：原文关键词必须**全部保留**，丢一个即 `intent_loss`。
P3 不通电可降级：任何异常返回结构化 `ok:false + reason_code`，**不抛、不冒充成功**。
P4 两态留痕：`compile` 与 `passthrough` 都经能力层调用（api 层自然落审计）。
P5 零新增依赖：只用标准库。
"""
from __future__ import annotations

import re
import time

# 四段标题（P1 的判据锚点：测试按这四个串断言）
SEGMENTS = ("【角色设定】", "【任务目标】", "【技术要求】", "【输出约束】")

_STOP = {"帮我", "帮忙", "写个", "搞个", "做个", "给我", "一下", "然后", "就是", "这个", "那个",
         "一个", "怎么", "如何", "能不能", "可以"}


def extract_keywords(raw: str, limit: int = 12) -> list:
    """P2 的判据工具：抽"必须保留"的关键词（英文词 + 中文 2~4 字块），保守而可解释。

    不追求语言学分词精度——只求**可复现**：同一输入永远抽出同一集合，
    这样"原意保真"才是可断言的判据，而不是感觉。

    ⚠️ 实测修正（2026-09-19 首跑）：先抽块再过滤填充词是不够的 ——
    `帮我写个用户登录功能` 会被 `[\\u4e00-\\u9fff]{2,4}` 抽出一个**跨填充词的 4 字块 `帮我写个`**，
    而 compile 会把填充词剥掉 ⇒ 假报 `intent_loss`。**必须先把填充词从原文删掉再抽块。**
    """
    raw = str(raw or "")
    clean = raw
    for w in _STOP:                      # 先删填充词，避免跨词块
        clean = clean.replace(w, "")
    words = re.findall(r"[A-Za-z][A-Za-z0-9_\-]{1,}", clean)
    zh = re.findall(r"[\u4e00-\u9fff]{2,4}", clean)
    out = []
    for w in words + zh:
        if w in _STOP or w in out:
            continue
        out.append(w)
    return out[:limit]


def compile_prompt(raw: str) -> dict:
    """核心：大白话 -> 四段结构化提示词，并自检"原意保真"。"""
    t0 = time.perf_counter()
    raw = str(raw or "").strip()
    if not raw:
        return {"ok": False, "reason_code": "empty_input", "prompt": None, "elapsed_ms": 0.0}

    intent = raw
    for junk in ("帮我", "请帮我", "麻烦", "写个", "给个"):
        intent = intent.replace(junk, "")
    intent = intent.strip() or raw

    prompt = (
        "【角色设定】\n你是一位资深软件工程师，按工业级标准交付。\n\n"
        "【任务目标】\n%s\n\n"
        "【技术要求】\n- 遵守单一职责与最小惊讶原则\n- 含类型注解与异常处理\n- 附带可运行的验证方式\n\n"
        "【输出约束】\n- 先给结论/代码，再给必要说明\n- 用 Markdown 代码块包裹代码\n"
    ) % intent

    missing = [k for k in extract_keywords(raw) if k not in prompt]
    out = {"ok": not missing, "prompt": prompt, "mode": "compile",
           "keywords": extract_keywords(raw), "missing": missing,
           "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2)}
    if missing:
        out["reason_code"] = "intent_loss"
    return out


def run(op: str = "compile", **params) -> dict:
    """统一入口（P3：**永不抛**）。op = compile / passthrough / status。"""
    try:
        if op in ("compile", None):
            return compile_prompt(params.get("text"))
        if op == "passthrough":
            raw = str(params.get("text") or "")
            return {"ok": bool(raw), "prompt": raw, "mode": "passthrough",
                    "reason_code": None if raw else "empty_input", "elapsed_ms": 0.0}
        if op == "status":
            return {"ok": True, "segments": list(SEGMENTS), "external_model": False,
                    "deps": "stdlib-only", "note": "第一刀纯本地；未接外部模型（不引入 external_llm）"}
        return {"ok": False, "reason_code": "unknown_op", "op": str(op)[:40]}
    except Exception as exc:  # noqa: BLE001  —— P3：结构化降级，不抛
        return {"ok": False, "reason_code": "internal_error",
                "error": f"{type(exc).__name__}: {exc}"[:160]}
