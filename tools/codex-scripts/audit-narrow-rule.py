#!/usr/bin/env python
# gbt-capability: none
"""已废弃 —— 本脚本是「窄规则」探针的**第二版**，测量有 bug，结论不可采信。

为什么废弃（不许删，留着当教训）
--------------------------------
它把 `caps_called_audit._code_only()` 的产物（**一个 token 一行**）再喂进 `tokenize`，
必然抛错并落到 `except` 兜底，而那个兜底**只剥注释、不剥字符串**
⇒ 散文串又被算成命中 ⇒ **同一个问题两次算出 0 与 54 两个互相矛盾的数**。
**测量工具自己坏了，于是"结论"跟着漂。**

替代品：`tools/codex-scripts/audit-caller-rule-probe.py`
（直接读**原始文件文本**，两种口径各自独立实现，不借道 `_code_only()`。）
"""
import sys

print(__doc__)
print("请改用：python tools/codex-scripts/audit-caller-rule-probe.py")
sys.exit(2)
