# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 总指挥能力目录的最小 Python 客户端（零第三方依赖）。

两个东西：

- `Catalog`         读 `data/capabilities.json`，按意图检索能力位；
- `CommanderClient` 对一个 OpenAI 兼容端点说话，并把模型给的能力位名**按目录校一遍**
                    （查不到 = 幻觉 = 不放行）。

30 秒跑通（不需要模型权重、不需要联网）：

    python demo.py "我要把一份 Markdown 变成 PPT，该调哪个能力位？"

文档：docs/03-capabilities.md（能力总表）· docs/07-capability-proof.md（逐位真跑证据）
"""
from __future__ import annotations

from .catalog import Capability, Catalog
from .client import CommanderClient

__version__ = "1.0.0"
__all__ = ["Capability", "Catalog", "CommanderClient", "__version__"]
