# -*- coding: utf-8 -*-
"""caps_tables · 用**容错**的方式取能力表（2026-09-25 事故对策）

## 为什么要有这一层

2026-09-25，`gbt_allinone/caps_registry.py` 被**另一个作者并发重写**，其间多次**删掉了导出表**
（`UNIMPLEMENTED_CAPS` / `DISABLED_CAPS`）。四处消费方写的是**硬 import**：

    from .caps_registry import BENIGN_CAPS, DISABLED_CAPS, UNIMPLEMENTED_CAPS, all_caps

⇒ **一处缺表 = ImportError = 整个能力 API 起不来**，而且**连治理工具也一起躺下**
（`framework_gate` 自己也 import 包 ⇒ **连护照都开不了**，实测就是这个连锁）。
**这不是"某一位能力坏了"，是"全都起不来"。**

## 对策（把两件事分开）
- **取表**：容错。读不到就给空表 / 空清单，**绝不炸**（本模块）；
- **表必须齐**：由**哨兵闸** `caps-registry-guard.py check` **响亮地报**（坏就有红字 + 复原命令）。
  本模块另给 `health()` 供审计读——**它不是判据**，判据在哨兵闸那里（单一真源）。

## 口径（不许省）
- 容错**不是**假装正常：`health()` 会如实说「注册表可读=False / 缺了哪张表」。
- `security_brain` 的名单完整性检查**照旧会判 not-ok**（它比的是 `len(UNIMPLEMENTED_CAPS) >= 11`），
  ⇒ 表被删时它**如实报故障**，而不是崩掉 —— **这是"能报的检测器"胜过"会炸的 import"**。
"""
from __future__ import annotations

_MISSING: list = []

try:
    from . import caps_registry as _R
    _READABLE, _WHY = True, None
except Exception as exc:            # noqa: BLE001 —— 语法坏/导入炸**都不许**把消费方拖下水
    _R, _READABLE, _WHY = None, False, "%s: %s" % (type(exc).__name__, str(exc)[:140])


def _table(name: str) -> dict:
    """取一张表：**类型不对或读不到都给空表**（不抛）。"""
    v = getattr(_R, name, None) if _READABLE else None
    if isinstance(v, dict):
        return v
    _MISSING.append(name)
    return {}


BENIGN_CAPS = _table("BENIGN_CAPS")
DISABLED_CAPS = _table("DISABLED_CAPS")
UNIMPLEMENTED_CAPS = _table("UNIMPLEMENTED_CAPS")
PARAM_REQUIRED = _table("PARAM_REQUIRED")


def all_caps() -> list:
    """能力位清单。注册表读不到时**返回空清单**（不抛），并由 `health()` 说明原因。"""
    f = getattr(_R, "all_caps", None) if _READABLE else None
    if callable(f):
        try:
            return list(f())
        except Exception:           # noqa: BLE001
            return []
    return [{"name": k, "status": "enabled", **(v if isinstance(v, dict) else {})}
            for k, v in BENIGN_CAPS.items()]


def required_params(kind: str) -> list:
    for src in (PARAM_REQUIRED, BENIGN_CAPS):
        need = (src.get(str(kind or "")) or {}) if isinstance(src, dict) else {}
        if isinstance(need, dict) and need.get("params"):
            return list(need.get("params") or [])
    return []


def params_hint(kind: str) -> str:
    for src in (PARAM_REQUIRED, BENIGN_CAPS):
        need = (src.get(str(kind or "")) or {}) if isinstance(src, dict) else {}
        if isinstance(need, dict) and need.get("hint"):
            return str(need.get("hint"))
    return ""


def health() -> dict:
    """**如实**说明容错层看到了什么。**这不是判据** —— 判据在哨兵闸 `caps-registry-guard`。"""
    return {"注册表可读": _READABLE, "为什么读不到": _WHY,
            "缺的表（读了但类型不对/没有）": sorted(set(_MISSING)),
            "计数": {"BENIGN_CAPS": len(BENIGN_CAPS), "DISABLED_CAPS": len(DISABLED_CAPS),
                    "UNIMPLEMENTED_CAPS": len(UNIMPLEMENTED_CAPS),
                    "PARAM_REQUIRED": len(PARAM_REQUIRED), "all_caps()": len(all_caps())},
            "口径": "**容错取表 ≠ 表齐**：表被删时这里给空表不炸，由哨兵闸响亮报故障"}
