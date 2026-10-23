# -*- coding: utf-8 -*-
"""V8 侦察核心（自 src/core 内迁，实现源码完全自包含）。

两翼：
  · `scanner.py` / `guard.py` —— 网络侧 OSINT（DNS/WHOIS/端口/指纹）
  · `last30days/` —— 内容与社交侧情报检索（同化件，见其 ATTRIBUTION.md）
"""
