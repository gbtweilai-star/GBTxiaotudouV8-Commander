# gbt-capability: vision-tentacle
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 视觉触手 — 视觉采集·视觉记忆。

提供截屏、读屏、视觉记忆等能力，与 omni_tentacle 的视觉通道配合。
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

_ROOT = Path(__file__).resolve().parent.parent
_MEMORY_PATH = _ROOT / "store" / "_visual_memory.json"


def capture(description: str = "") -> dict:
    """截屏并记录视觉记忆。"""
    # 实际截屏由 omni_tentacle 提供，这里记录元数据
    memory_entry = {
        "timestamp": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
        "description": description,
        "source": "vision_tentacle",
    }
    try:
        memory_path = _MEMORY_PATH
        memories = []
        if memory_path.exists():
            try:
                memories = __import__("json").loads(memory_path.read_text(encoding="utf-8"))
            except Exception:
                memories = []
        memories.append(memory_entry)
        # 保留最近100条
        memories = memories[-100:]
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        memory_path.write_text(__import__("json").dumps(memories, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return {
        "ok": True,
        "entry": memory_entry,
        "total_memories": len(memories) if 'memories' in dir() else 1,
    }


def recall(last_n: int = 10) -> list[dict]:
    """召回最近的视觉记忆。"""
    try:
        if not _MEMORY_PATH.exists():
            return []
        memories = __import__("json").loads(_MEMORY_PATH.read_text(encoding="utf-8"))
        return memories[-last_n:]
    except Exception:
        return []


def clear_memory():
    """清空视觉记忆。"""
    try:
        if _MEMORY_PATH.exists():
            _MEMORY_PATH.unlink()
    except Exception:
        pass
