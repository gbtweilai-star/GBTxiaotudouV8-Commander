"""GBT小土豆V8 · brain 兼容垫片。

触手硬件层（omni_*）从旧 brain/ 目录结构迁移而来，其中"穿透传输"引用
brain.tentacle_transmission.transmit。V8 复活期本垫片提供同形降级实现：
数据落到 V8 审计总线（store），不再依赖旧 brain/ 目录结构。
后续可替换为直连 V8 事件总线。
"""
import sys
import time
from pathlib import Path

# 让 `import brain.tentacle_transmission` 与 `import brain.xxx` 可寻址到本垫片包
_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

# 传输脉冲状态（供 pulse() 只读上报；不保存任何传输内容）
_STATE = {"sent": 0, "last_at": "", "last_source": "", "last_channel": "", "last_error": ""}


def transmit(data, source="unknown", channel="default", priority="normal"):
    """穿透传输降级实现：落 V8 审计总线（轻量，不阻塞硬件层）。"""
    try:
        from gbt_allinone.store import audit
        audit("tentacle_tx", {"source": str(source)[:60], "channel": str(channel)[:20],
                              "priority": str(priority)[:10],
                              "size": len(str(data))})
        _STATE.update({"sent": int(_STATE.get("sent") or 0) + 1,
                       "last_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                       "last_source": str(source)[:60], "last_channel": str(channel)[:20],
                       "last_error": ""})
    except Exception:  # noqa: BLE001
        # 合理兜底：传输层绝不阻塞触手本体；失败原因记入状态，由 pulse() 如实上报
        # （不再静默：`_STATE['last_error']` 会让 pulse().status 变成 degraded）
        _STATE["last_error"] = "audit_unavailable"
    return {"ok": True, "degraded": "v8_audit_bus"}


def pulse() -> dict:
    """传输脉冲（只读）：返回 {status, queue_size, last_transmission}，**永不抛异常**。

    三态：idle（尚未传输）/ online（有成功传输）/ degraded（审计不可用）。
    说明：本垫片无队列设计，`queue_size` 恒为 0——这是"无队列"，不是"零积压"。
    """
    try:
        sent = int(_STATE.get("sent") or 0)
        last_at = str(_STATE.get("last_at") or "")
        error = str(_STATE.get("last_error") or "")
        if error:
            status = "degraded"
        elif sent > 0:
            status = "online"
        else:
            status = "idle"
        return {
            "status": status,
            "queue_size": 0,
            "last_transmission": ({"at": last_at,
                                   "source": str(_STATE.get("last_source") or ""),
                                   "channel": str(_STATE.get("last_channel") or "")}
                                  if last_at else None),
            "sent": sent,
            "transport": "v8_audit_bus",
            "error": error or None,
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "degraded", "queue_size": 0, "last_transmission": None,
                "error": str(exc)[:120]}
