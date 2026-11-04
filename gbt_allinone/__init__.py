"""GBT小土豆V8 · 统一框架核心。

定位：私人自用 · 全功能 · 不为任何企业公司代持。
原则：
- 统一接口 run_task 分发一切能力，全部动作落审计日志；
- 治理是资产不是累赘：审计可追踪、错误如实暴露、不伪造结果；
- 面向用户：先动手、再提意见、一起想办法，不做死板拒绝机器。
"""
from .api import run_task, list_capabilities, DANGEROUS_ENABLED
from .store import audit, query_log, log_count
from .soul import SOUL, stamp_result

# 编码守门：Windows 控制台默认 cp936 / cp1252，print 中文会 UnicodeEncodeError。
# 在 import 时把标准流切到 UTF-8；切不动就静默放过（不影响核心功能）。
import sys as _sys

for _stream in (_sys.stdout, _sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
del _stream

