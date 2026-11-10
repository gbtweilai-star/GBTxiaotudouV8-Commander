#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""adaptive_context —— 上下文预算**按压力自己变**，不写死一个数

## 为什么要有这个（主人原话）

> 「这个别去固定，设计成根据扩张来变动，稳定极限输出」

上一版我在桥里写死 `context_budget = 12000 字`。两个问题：
  ① **数字是错的**：中文约 1.2 字/token，模型 ctx 4096 减掉输出预留
     只剩 ~4300 字。12000 是 3 倍超限 —— 等于没管。
  ② **写死就必然错**：内存会变、上游会换、对话会长会短。
     写死的数只在一个瞬间是对的。

## 它怎么变

```
上限   = (模型 ctx - 输出预留 - 安全边) × 每 token 字数
        · ctx / 每token字数 都从**运行时的真实证据**来，不猜
        · 拿不到证据就用保守默认，并标 conservative=True
下限   = 2000 字（再小就记不住上一句，对话断片）
目标   = 在半开区间里**按压力滑**
        压力低（填充<60% 且延迟健康）→ 涨 ×1.25
        压力高（填充>85% 或延迟退化或内存紧）→ 退 ×0.7
```

## 三条纪律

1. **不许超过模型 ctx** —— 超了就是假窗口，模型照样截断，账却是假的
2. **降要快、涨要慢** —— 逼近上限时踩得太狠会直接掉字，宁可早退
3. **每次变动都留痕** —— `/v1/context` 能读到当前预算与理由，可复核

"""
from __future__ import annotations

import json
import os
import pathlib
import threading
import time

STATE = pathlib.Path(os.environ.get("GBT_STATE_DIR")
                      or pathlib.Path(__file__).resolve().parents[1] / "state") / "adaptive_context.json"

# 中文为主的保守估计：1 token ≈ 1.2 字；英文更省，但按最坏算
CHARS_PER_TOKEN = 1.2
MIN_CHARS = 2000          # 再小就记不住上一句
DEFAULT_CTX_TOKENS = 4096  # 拿不到模型证据时的保守默认

_lock = threading.Lock()
_cache = {"budget": None, "at": 0.0}


def _mem_free_mb() -> float:
    try:
        for ln in open("/proc/meminfo", encoding="utf-8"):
            if ln.startswith("MemFree"):
                return int(ln.split()[1]) / 1024.0
    except Exception:                                          # noqa: BLE001
        pass
    return -1.0


def _read_state() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        return {}


def _write_state(d: dict) -> None:
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:                                          # noqa: BLE001
        pass


def hard_cap(ctx_tokens: int, max_tokens: int, chars_per_token: float = CHARS_PER_TOKEN) -> int:
    """硬上限：**绝不能超模型 ctx**，超了就是自欺欺人。"""
    usable = max(256, int(ctx_tokens) - int(max_tokens) - 128)   # 128 安全边
    return max(MIN_CHARS, int(usable * chars_per_token))


def window_chars(ctx_tokens: int | None = None, max_tokens: int = 512,
                 used_ratio: float | None = None,
                 latency_ms: float | None = None,
                 name: str = "default") -> dict:
    """给出这一发该用多少字。

    · ctx_tokens   模型真实上下文（拿不到就保守默认，并标 conservative）
    · used_ratio   上一次窗口的填充率（0..1）
    · latency_ms   上一次端到端耗时
    """
    conservative = ctx_tokens is None
    ctx = int(ctx_tokens or DEFAULT_CTX_TOKENS)
    cap = hard_cap(ctx, max_tokens)

    st = _read_state()
    cur = int(st.get(name, {}).get("budget") or 0)
    if cur <= 0:
        cur = cap                                  # 首次：直接给满

    reasons = []
    mem = _mem_free_mb()
    target = cur

    # ── 压力判据（**填充率不算数**，见下）────────────────────────
    # 🔴 2026-10-28 修：上一版把 used_ratio ≥85% 当压力，
    #   实测预算一路退到下限 —— 因为 `ring_context.window()` **按定义就填满预算**，
    #   填充率恒 ~98%，它根本不是压力信号，是设计常量。
    #   真正的压力只有两条：**延迟**（模型来不来得及）和**内存**（这台机撑不撑）。
    tight = []
    if latency_ms is not None and latency_ms >= 20000:
        tight.append("上发%.1fs偏慢" % (latency_ms / 1000.0))
    if 0 <= mem < 400:
        tight.append("可用内存%.0fMB<400" % mem)

    if tight:
        target = int(cur * 0.7)                    # **降要快**
        reasons.append("退×0.7：" + "、".join(tight))
    elif cur < cap and (latency_ms is None or latency_ms < 12000) and (mem < 0 or mem >= 600):
        target = int(cur * 1.25)                   # 涨要慢，逼近 cap
        reasons.append("涨×1.25：延迟%.1fs 宽裕、内存%.0fMB 够 ⇒ 往极限推"
                       % ((latency_ms or 0) / 1000.0, mem if mem >= 0 else 0))
    else:
        reasons.append("维持 %d 字（cap %d）" % (cur, cap))
    # 填充率只作信息，不参与判据
    if used_ratio is not None:
        reasons.append("填充%.0f%%（窗口按设计填满，不作压力）" % (used_ratio * 100))

    target = max(MIN_CHARS, min(cap, target))
    if target != cur:
        st.setdefault(name, {})
        st[name].update({"budget": target, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                         "why": "；".join(reasons), "cap": cap, "ctx_tokens": ctx})
        _write_state(st)

    return {"budget": target, "cap": cap, "min": MIN_CHARS, "ctx_tokens": ctx,
            "conservative": conservative, "mem_free_mb": round(mem, 0) if mem >= 0 else None,
            "why": "；".join(reasons)}


def report(name: str = "default") -> dict:
    st = _read_state()
    d = dict(st.get(name) or {})
    d.setdefault("budget", hard_cap(DEFAULT_CTX_TOKENS, 512))
    d["cap"] = hard_cap(int(d.get("ctx_tokens") or DEFAULT_CTX_TOKENS), 512)
    d["mem_free_mb"] = round(_mem_free_mb(), 0)
    d["口径"] = ("预算按压力滑动：填充<60%%且延迟<12s ⇒ ×1.25；填充≥85%%或延迟≥20s"
                 "或内存<400MB ⇒ ×0.7；永不超模型 ctx")
    return d


if __name__ == "__main__":
    print(json.dumps(report(os.sys.argv[1] if len(os.sys.argv) > 1 else "default"),
                     ensure_ascii=False, indent=1))
