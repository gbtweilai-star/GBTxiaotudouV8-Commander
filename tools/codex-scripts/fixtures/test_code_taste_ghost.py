# -*- coding: utf-8 -*-
"""负对照 · 空壳测试（P0-4 专用）。

文件名以 `test_` 开头 ⇒ 本器才会把"没有断言的 test_* 函数"判成 P0。
**故意一条断言都不写**：这类测试给的是覆盖率幻觉，比没有测试更坏。
"""


def test_nothing_is_asserted():
    value = 1 + 1


def test_calls_but_never_checks():
    result = {"status": "ok"}
    print(result)


def test_this_one_is_fine():
    assert 1 + 1 == 2
