# gbt-capability: dynamic-import
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""gbt_allinone/omni_web.py — 万能触手·Web 六态（**真名门面**）。

为什么有这个文件（2026-10-04 修）：
  仓里的判据要求「`handler` 字段必须等于能力位真名」（caps_registry 的 `omni_web`，
  见 tests/test_capability_registry.py::test_handler_matches_dispatch_key），
  而 L1 导入连通性扫描按 handler 名 `import gbt_allinone.<handler>` 逐个试导
  ⇒ 真名模块必须可寻址。实现仍住 `omni_web_cap.py`（2026-10-03 入库的历史路径，
  api.py 与绑定账都已按此登记），这里只做真名门面，**不复制任何逻辑**。
"""
from __future__ import annotations

from .omni_web_cap import run, status  # noqa: F401

__all__ = ["run", "status"]
