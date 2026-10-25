# -*- coding: utf-8 -*-
"""brain.tentacle_transmission 兼容垫片：V8 审计总线降级实现。

旧触手硬件层（omni_*）通过 `from brain.tentacle_transmission import transmit`
上送穿透数据。V8 复活期本模块提供同形签名，数据落 V8 审计总线。
"""
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))


def transmit(data, source="unknown", channel="default", priority="normal"):
    """穿透传输降级实现：落 V8 审计总线（轻量，绝不阻塞触手本体）。"""
    try:
        from gbt_allinone.store import audit
        audit("tentacle_tx", {"source": str(source)[:60], "channel": str(channel)[:20],
                              "priority": str(priority)[:10],
                              "size": len(str(data))})
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "degraded": "v8_audit_bus"}
