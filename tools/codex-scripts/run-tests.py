# -*- coding: utf-8 -*-
"""跑 unittest —— 因为 `pyembed` 是 embeddable 包，`-m unittest` 在它下面用不了。

为什么需要这个壳（2026-11-05 实测）：
    pyembed 根下有个 `python312._pth`：
        python312.zip
        .
        Lib\\site-packages
    只要 `._pth` 存在，解释器就进 isolated 模式，于是
      · `''`（当前目录）**不会**自动进 sys.path ⇒ `python -m unittest` 找不到包
      · **PYTHONPATH 环境变量被整个忽略** ⇒ 设了也没用（实测过，报错一字不差）
      · `-c "..."` 可以，但 PowerShell 会吃掉里面的双引号，报 SyntaxError
    唯一稳的路子：写成 .py 文件跑，脚本自己把 cwd 塞进 sys.path。
    （`python xxx.py` 时 sys.path[0] 是**脚本所在目录**，不是 cwd —— 所以这行不能省。）

用法（在仓库根执行）：
    .\\pyembed\\python.exe tools\\codex-scripts\\run-tests.py gbt_allinone.tests.test_omni_plug
    .\\pyembed\\python.exe tools\\codex-scripts\\run-tests.py ^
        gbt_allinone.tests.test_brain_health_vision gbt_allinone.tests.test_standards_pack

注意：`gbt_allinone/tests/__init__.py` 会把 GBT_STORE_DIR setdefault 到临时目录，
所以直接跑就行；不要为了让某条用例过而把 GBT_STORE_DIR 指向生产 store。
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

# 必须在 import 任何 gbt_allinone 之前把隔离 store 钉好：
# `gbt_allinone/__init__` 会 import `.store`，而 `store.py` **在 import 时**就把
# STORE_DIR 绑成常量；`tests/__init__` 见到"已绑生产 store"会直接 raise 停下。
# 所以环境变量晚一步设，整条命令就会以「拒绝在绑定生产 store 的进程里跑测试」告终。
os.environ.setdefault("GBT_STORE_DIR", tempfile.mkdtemp(prefix="gbt_test_store_"))


def main() -> int:
    names = [a for a in sys.argv[1:] if not a.startswith("-")]
    sys.path.insert(0, os.getcwd())
    if not names:
        print("用法：run-tests.py <模块名> [模块名...]")
        return 2

    # 导入检查只作提示：`pkg.mod.Class.method` 这种名字本来就不是模块，
    # 该由 loadTestsFromNames 自己解析；只有"一条都没装上"时才把它们当原因报出来。
    problems = []
    for n in names:
        try:
            __import__(n)
        except Exception as e:                                    # noqa: BLE001
            problems.append("%s -> %s: %s" % (n, type(e).__name__, str(e)[:120]))

    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    if suite.countTestCases() == 0:
        print("❌ 一条用例都没装上（这是环境/路径问题，不是测试失败）：")
        for p in problems:
            print("   " + p)
        return 2

    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
