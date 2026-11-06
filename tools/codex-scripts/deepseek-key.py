#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deepseek-key —— 包装 gbt_allinone.deepseek_key，绕开 pyembed 的 `-m` 限制。

## 为什么需要这个包装器（AGENTS.md 坑 C）
`pyembed/` 是 **embeddable 包**，根下的 `python312._pth` 让解释器进入 isolated 模式：

    .\\pyembed\\python.exe -m gbt_allinone.deepseek_key set
    -> ModuleNotFoundError: No module named 'gbt_allinone'      # cwd 不进 sys.path

    $env:PYTHONPATH = ...
    -> 被整个忽略（一行不差地报同样的错）

只有 `python <脚本文件>` 这种跑法，脚本自己 `sys.path.insert` 才生效。
本文件就是那层壳：把仓根塞进 sys.path，再把参数原样交给 deepseek_key.main()。

## 用法（与上游完全一致，只把 `-m 包.模块` 换成文件路径）
    "sk-xxx" | .\\pyembed\\python.exe tools\\codex-scripts\\deepseek-key.py set
    .\\pyembed\\python.exe tools\\codex-scripts\\deepseek-key.py status
    .\\pyembed\\python.exe tools\\codex-scripts\\deepseek-key.py inject -- <命令...>

    # 其它保险箱 profile（agnes / potato / hf …）
    .\\pyembed\\python.exe tools\\codex-scripts\\deepseek-key.py status --profile agnes
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:                                        # noqa: BLE001
    pass

from gbt_allinone.deepseek_key import main as key_main  # noqa: E402

if __name__ == "__main__":
    sys.exit(key_main(sys.argv[1:]))
