# -*- coding: utf-8 -*-
# ⬻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""压缩与直达（quant_plan）—— 蒸馏自 Bonsai 2 27B，落成**直达能力位**

主人令 2026-10-16：「蒸馏提炼出契合我们大模型的能力和压缩体积，**再重新绑定触手打通直达提速**」。

本位把两件事变成**能直接调**（不绕本地、不绕文档）：
  ① 压缩：每档 ⇒ b/w ⇒ 估算体积 ⇒ 契合哪级硬件（算术自洽，靠 quant-plan-check 咬）
  ② 直达：意图 ⇒ 能力位 ⇒ 车道 ⇒ 端点（**云插件层**，本地不承载）⇒ 速度类

铁律（主人 2026-10-08 / 10-16）：**本地不要任何大模型**；端点不许写 127.0.0.1。
  所以本位的 `route` 返回的路径**不经本机**；速度一律标「他方读数·本机未复现」。

op：status / plan / layer / route / speed / check（**全只读·零作用域**）
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "tools" / "train" / "recipe_v26.json"
JUDGE = ROOT / "tools" / "codex-scripts" / "quant-plan-check.py"
READ_OPS = ("status", "plan", "layer", "route", "speed", "check")
WRITE_OPS = ()
PARAMS = 27e9
OVERHEAD = 1.3
FIT_GB = 8.6

# 他方读数（Bonsai 2 27B，已标出处；**本机未复现**）
REF = {"speed_tok_s": 47, "speed_on": "Apple M5 Max 笔记本", "iq_2xxs": 72.59, "ternary_avg": 84.78,
       "fp16_keep_pct": 98.2, "source": "HF EigenLabs/Ternary-Bonsai-2-27B-MLX-2bit 的 model card"}


def _recipe() -> dict:
    try:
        return json.loads(RECIPE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def estimate(bits: float) -> float:
    return round(PARAMS * float(bits) / 8.0 / 1024.0 ** 3 * OVERHEAD, 2)


def status() -> dict:
    d = _recipe()
    return {"ok": bool(d), "op": "status", "recipe": str(RECIPE), "recipe_exists": RECIPE.is_file(),
            "gen": d.get("gen"), "parent": d.get("parent"),
            "quant_targets": [t.get("name") for t in ((d.get("quantize") or {}).get("targets") or [])],
            "backends": (d.get("execution_layer") or {}).get("backends"),
            "judge": str(JUDGE), "reason": None if d else "recipe_not_found"}


def plan() -> dict:
    """压缩选型表（算术现算，不拄字面）。"""
    d = _recipe()
    rows = []
    for t in ((d.get("quantize") or {}).get("targets") or []):
        b = t.get("bits_per_weight")
        rows.append({"name": t.get("name"), "bits": b, "container": t.get("container"),
                     "role": t.get("role"), "est_gb": estimate(b) if b not in (None, "") else None,
                     "fits_8gb": (estimate(b) <= FIT_GB) if b not in (None, "") else None})
    return {"ok": bool(rows), "op": "plan", "params": PARAMS, "overhead": OVERHEAD, "fit_gb": FIT_GB,
            "targets": rows, "reference": REF,
            "note": "估算含容器开销 ×%.1f；**真体积/显存必须在机上实测**" % OVERHEAD}


def layer() -> dict:
    """执行层三层映射（对接已有施工图，不重造）。"""
    ex = (_recipe().get("execution_layer") or {})
    return {"ok": True, "op": "layer",
            "route": ex.get("route") or "key_gateway.PROVIDERS（单一真源，12 车道）",
            "carry": ex.get("carry") or "AirLLM 钩子 + PTQ1_0 分片",
            "memory": ex.get("memory") or "layer-file + file-backed mmap；resident 白名单",
            "backends": ex.get("backends") or [],
            "rule": ex.get("_铁律") or "本地不要任何大模型",
            "local_role": ex.get("_本机角色") or "只做控制面"}


def route(intent: str = "") -> dict:
    """**直达路线**：意图 ⇒ 能力位 ⇒ 车道 ⇒ 端点（云插件层，不经本机）。"""
    if not str(intent or "").strip():
        return {"ok": False, "reason": "need_intent"}
    steps = [
        {"n": 1, "where": "意图", "what": intent, "via": "人一句话"},
        {"n": 2, "where": "能力位", "what": "quant_plan（本位）", "via": "万能插 cap quant_plan"},
        {"n": 3, "where": "车道", "what": "key_gateway.PROVIDERS（单一真源，12 车道）",
         "via": "不经第二份名单"},
        {"n": 4, "where": "网关", "what": "Worker 网关（GW_AUTH）", "via": "云上拼接网"},
        {"n": 5, "where": "端点", "what": "RunPod Serverless（GBT_POTATO_API_KEY）（我们自己的权重）", "via": "云插件层"},
    ]
    return {"ok": True, "op": "route", "intent": intent, "steps": steps, "hops": len(steps) - 1,
            "direct": True,
            "why_direct": "每一步都有固定落点（位→车道→端点），**不经本机中转**；本地不承载模型",
            "no_local": True}


def speed() -> dict:
    """提速口径（他方读数，**本机未复现**）。"""
    d = _recipe()
    rows = []
    for t in ((d.get("quantize") or {}).get("targets") or []):
        b = t.get("bits_per_weight")
        rows.append({"name": t.get("name"), "bits": b,
                     "why_faster": "每权重位数越少 ⇒ 带宽/计算越省（同体积下三值赢 IQ2_XXS %.2f 分）"
                                  % (REF["ternary_avg"] - REF["iq_2xxs"])})
    return {"ok": True, "op": "speed", "targets": rows, "reference": REF,
            "honest": "上面速度是**他方实测**（%s），本机（无 CUDA）**未复现**；不当我们的读数"
                      % REF["speed_on"]}


def check() -> dict:
    """把判据指向归一（真判据在 quant-plan-check.py）。"""
    return {"ok": True, "op": "check", "judge": str(JUDGE),
            "rules": ["C1 字段齐", "C2 算术自洽", "C3 实测要求",
                      "C4 不许托管充当权重", "C5 承载面不许本机/回环"],
            "cmd": "py -3.14 -X utf8 tools/codex-scripts/quant-plan-check.py",
            "selftest": "py -3.14 -X utf8 tools/codex-scripts/quant-plan-check.py --selftest"}


def run(op: str = "status", **kw) -> dict:
    o = (op or "status").strip().lower()
    if o == "status":
        return status()
    if o == "plan":
        return plan()
    if o == "layer":
        return layer()
    if o == "route":
        return route(kw.get("intent") or "")
    if o == "speed":
        return speed()
    if o == "check":
        return check()
    return {"ok": False, "reason": "unknown_op", "op": o, "known": list(READ_OPS),
            "detail": "未知 op 只回错（fail-closed）"}

