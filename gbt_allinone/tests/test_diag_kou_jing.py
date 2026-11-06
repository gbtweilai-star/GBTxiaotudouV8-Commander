# -*- coding: utf-8 -*-
"""诊断位口径一致性 · 防再写坏（2026-11-05）。

**事故经过**：改 `impact_check._op_impact` 的「两种口径」时，新句子和旧文本残片
被拼在一起 —— `逐字对齐"` 提前闭了字符串，`"强边"` 这个 key 直接丢了。
文件变成 SyntaxError，整个能力位 import 不了；而 `grep` 输出经过 JSON 转义后
（`"` 显示成 `\\"`），人眼看上去「挺正常」，谁也没发现。

**教训**：口径文本是给人读的，但它躺在源码里 —— 就得有校验。

六条机检，全部静态（不启动进程、不碰生产 store、不依赖图重建）：

  A. 语法能过 —— `ast.parse` 就是最强的那道闸，提前闭合在这里必炸
  B. 「两种口径」三个 key 齐（全边 / 强边 / 已知口径）
  C. 文本里 4 位以上数字必须能对上图里的真实读数，或属于历史白名单 {67}
  D. 文本指向的 `op=status` 的 `strong_edges` 必须真存在（指错了就是假指针）
  E. `risky` 的 caveat 与 `impact` 的「强边」必须同口径（都含 import / impl / 分派）
  F. 不许有重复粘贴的残片（`逐字对齐` 只许出现一次）
"""
from __future__ import annotations

import ast
import io
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMPACT = os.path.join(ROOT, "gbt_allinone", "tools", "impact_check.py")
WIRING = os.path.join(ROOT, "state", "model-pack", "wiring.json")

# 明确标注了「历史值、不会再变」的读数，允许出现在文本里
HISTORICAL = {67}


def _src() -> str:
    with io.open(IMPACT, encoding="utf-8") as fh:
        return fh.read()


def _tree() -> ast.Module:
    return ast.parse(_src(), filename=IMPACT)


def _find_func(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _two_kou_jing() -> dict:
    """`_op_impact` 的 return 字典里，`两种口径` 这个键的 {k: 文本}。"""
    fn = _find_func(_tree(), "_op_impact")
    if fn is None:
        raise AssertionError("找不到 _op_impact 函数")
    for node in ast.walk(fn):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == "两种口径":
                    out = {}
                    if isinstance(v, ast.Dict):
                        for kk, vv in zip(v.keys, v.values):
                            if isinstance(kk, ast.Constant) and isinstance(vv, ast.Constant):
                                out[kk.value] = vv.value
                    return out
    raise AssertionError("_op_impact 里找不到「两种口径」字典")


def _graph_ints() -> set:
    """wiring.json 里所有整数读数（递归收集，不关心具体结构）。"""
    if not os.path.exists(WIRING):
        return set()
    with io.open(WIRING, encoding="utf-8") as fh:
        data = json.load(fh)
    out = set()

    def walk(o):
        if isinstance(o, bool):
            return
        if isinstance(o, int):
            out.add(o)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    return out


def _nums(text: str) -> list:
    """抽 4 位以上数字，先剔掉日期/时刻/小数 —— 它们不是规模读数。"""
    t = re.sub(r"\d{4}-\d{2}-\d{2}", " ", text)
    t = re.sub(r"\d{2}:\d{2}(?::\d{2})?", " ", t)
    t = re.sub(r"\d+\.\d+", " ", t)
    return [int(x) for x in re.findall(r"\d{4,}", t)]


class TestDiagnosticKouJing(unittest.TestCase):
    """A · 语法"""

    def test_a_module_parses(self):
        # 2026-11-05 事故的直接护栏：字符串提前闭合、key 丢失都在这儿炸
        try:
            _tree()
        except SyntaxError as exc:
            self.fail("impact_check.py 语法坏了（第 %s 行）：%s" % (exc.lineno, exc.msg))

    """B · 三个 key 齐"""

    def test_b_three_keys_present(self):
        kj = _two_kou_jing()
        for k in ("全边", "强边", "已知口径"):
            self.assertIn(k, kj, "「两种口径」缺 key %r —— 2026-11-05 就是这么丢的「强边」" % k)
        self.assertEqual(len(kj), 3, "「两种口径」应恰好 3 条，实得 %d 条：%s" % (len(kj), list(kj)))

    """C · 数字对得上"""

    def test_c_numbers_resolve(self):
        kj = _two_kou_jing()
        known = _graph_ints() | HISTORICAL
        if not known:
            self.skipTest("wiring.json 不存在，跳过（开发仓未重建图时正常）")
        bad = []
        for k, v in kj.items():
            if not isinstance(v, str):
                continue
            for n in _nums(v):
                if n not in known:
                    bad.append((k, n))
        self.assertEqual(
            bad, [],
            "这些读数在图里找不到、也不是历史白名单 %s：%s —— 数字一律走 op=status 现查" % (
                sorted(HISTORICAL), bad),
        )

    """D · 指针不是假的"""

    def test_d_pointer_target_exists(self):
        kj = _two_kou_jing()
        text = " ".join(v for v in kj.values() if isinstance(v, str))
        if "strong_edges" not in text:
            self.skipTest("文本未引用 strong_edges")
        fn = _find_func(_tree(), "_op_status")
        self.assertIsNotNone(fn, "文本让读者去看 op=status 的 strong_edges，但 _op_status 不存在")
        seg = ast.get_source_segment(_src(), fn) or ""
        self.assertIn(
            '"strong_edges"', seg,
            "文本说「看 op=status 的 strong_edges」，但 _op_status 返回体里没有这个键 —— 假指针",
        )

    """E · 两处同口径"""

    def test_e_two_sites_agree(self):
        kj = _two_kou_jing()
        impact_txt = kj.get("强边") or ""
        fn = _find_func(_tree(), "_op_risky")
        self.assertIsNotNone(fn, "找不到 _op_risky")
        risky_txt = ast.get_source_segment(_src(), fn) or ""
        for label, txt in (("impact.强边", impact_txt), ("risky.caveat", risky_txt)):
            for token in ("import", "impl", "分派"):
                self.assertIn(
                    token, txt,
                    "%s 没提到 %r —— 两处口径必须同步，否则读者看到两套说法" % (label, token),
                )

    """F · 没有重复粘贴的残片"""

    def test_f_no_duplicated_fragment(self):
        kj = _two_kou_jing()
        text = " ".join(v for v in kj.values() if isinstance(v, str))
        for frag in ("逐字对齐", "v4 口径"):
            n = text.count(frag)
            self.assertLessEqual(
                n, 1,
                "「%s」出现了 %d 次 —— 像是把旧文本又粘了一遍（2026-11-05 事故特征）" % (frag, n),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
