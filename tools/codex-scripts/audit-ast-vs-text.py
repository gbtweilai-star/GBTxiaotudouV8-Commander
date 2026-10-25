#!/usr/bin/env python
# gbt-capability: none
"""已废弃 —— 本脚本是「AST 口径」探针的**第一版**，方案已被自己的读数否掉。

为什么废弃（不许删，留着当教训）
--------------------------------
它主张「AST 只看实参/字典键/比较操作数才算真调用」。
实测 **82 个能力位判据不一致**，而且**错的方向是反的**：
它把大量**合法的「名字清单」引用**（如 `awesome_tools_index.py` 里
`["create", "auto_switch", …]` 这种列表元素）全部杀掉
⇒ 把**已接线误判成孤儿**。反方向的假读数同样是假读数。

替代品：`tools/codex-scripts/audit-caller-rule-probe.py`
"""
import sys

print(__doc__)
print("请改用：python tools/codex-scripts/audit-caller-rule-probe.py")
sys.exit(2)
