# -*- coding: utf-8 -*-
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""权重唯一指针：`ACTIVE.json` 说在哪，所有模块就去哪。

## 为什么必须有这个模块（2026-11-04 实测）

`state/weights/ACTIVE.json` 自己写着：

    "endpoint": "http://127.0.0.1:8111/v1",
    "note": "唯一指针：换版权重只改这个文件；不要在代码里写死路径"

**而代码里写死的是另一个端口**（实测全仓 41 处 `127.0.0.1:8792`，分布 13 个文件）：

    commander.py:68    DEFAULT_BASE = "http://127.0.0.1:8792"
    proactive.py:26    ... GBT_ENGINE_BASE, "http://127.0.0.1:8792"
    energy_core.py:129 探测 8792
    pulse_core         报 "endpoint: 8792 · engine: down"

后果是最坏的一种：**引擎明明起来了，主干却看不见它** ——
`local_llm status` 说 health ok，而 `pulse_core` 说 engine down，两个都"没错"，
因为它们看的是两个端口。这种分裂比"没起"更难查：任何一个组件的自检都可能是绿的。

## 口径

1. **ACTIVE.json 是唯一真源**（它自己声明的，不是这里新立的规矩）
2. 环境变量 `GBT_ENGINE_BASE` 可覆盖（容器/CI 里换地址用）
3. 读不到就给**明确空值 + 原因**，不许猜一个默认端口 —— 猜出来的默认值就是下一次分裂的种子
"""
from __future__ import annotations

import json
import os
from pathlib import Path

__all__ = ["active", "base", "endpoint", "model", "diag"]

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = ROOT / "state" / "weights" / "ACTIVE.json"


def active() -> dict:
    """读指针文件。读不到返回 `{"ok": False, "error": ...}`，**不编默认值**。"""
    if not ACTIVE.is_file():
        return {"ok": False, "error": f"指针文件不在：{ACTIVE}"}
    try:
        d = json.loads(ACTIVE.read_text(encoding="utf-8"))
    except Exception as e:                               # noqa: BLE001
        return {"ok": False, "error": f"指针文件损坏：{type(e).__name__}: {e}"}
    d["ok"] = True
    return d


def base() -> str:
    """引擎根地址，**不带 `/v1`**（例如 `http://127.0.0.1:8111`）。

    优先级：`GBT_ENGINE_BASE` > ACTIVE.json 的 `endpoint`。
    都拿不到时返回空串 —— 让调用方显式处理"没有引擎"，而不是悄悄连一个猜出来的端口。
    """
    env = (os.environ.get("GBT_ENGINE_BASE") or "").strip()
    if env:
        return env.rstrip("/").removesuffix("/v1")
    ep = str(active().get("endpoint") or "").strip()
    if not ep:
        return ""
    return ep.rstrip("/").removesuffix("/v1")


def endpoint() -> str:
    """OpenAI 兼容的根（带 `/v1`）。"""
    b = base()
    return f"{b}/v1" if b else ""


def model() -> str:
    """当前激活权重的文件名（也是 llama-server 的 `--alias`）。"""
    return str(active().get("active_artifact") or "")


def diag() -> dict:
    """给自检用：一处报全「指针说什么 / 实际连哪 / 通不通」。"""
    import urllib.request
    b = base()
    info = {"active_json": str(ACTIVE.relative_to(ROOT)),
            "endpoint_from_pointer": str(active().get("endpoint") or ""),
            "env_override": os.environ.get("GBT_ENGINE_BASE") or "",
            "resolved_base": b, "model": model()}
    if not b:
        info.update({"ok": False, "why": "指针与环境变量都没给出地址"})
        return info
    try:
        with urllib.request.urlopen(b + "/health", timeout=3) as r:
            info.update({"ok": r.status == 200, "health": r.read().decode("utf-8", "replace")[:80]})
    except Exception as e:                               # noqa: BLE001
        info.update({"ok": False, "why": f"{type(e).__name__}: {str(e)[:120]}"})
    return info
