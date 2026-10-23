# -*- coding: utf-8 -*-
"""穿透网骨架的三条带牙用例（Owner 2026-09-19 · 断言形状不许软化）。"""
from __future__ import annotations

import ast
import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import ai_capability_net as NET  # noqa: E402


class CapabilityNetTests(unittest.TestCase):
    def test_unimplemented_entry_returns_not_implemented_never_ok_true(self):
        """带牙 ①：未实现入口 ⇒ ok=False 且 reason=\"not_implemented\"（不许空壳 ok=True）。"""
        proto = NET.PenetrationProtocol()
        node = NET.CapabilityNode(name="x", invoke_mode="api")
        r = proto.penetrate(node, {})
        self.assertIs(r["ok"], False)
        self.assertEqual(r["reason"], "not_implemented")
        for mode in ("api", "cli", "web", "manual", "unknown"):
            n = NET.CapabilityNode(name="x", invoke_mode=mode)
            self.assertEqual(proto.penetrate(n, {})["reason"], "not_implemented",
                             f"{mode} 分支不许返回 ok=True")

    def test_missing_params_returns_missing_params(self):
        """带牙 ②：缺参 ⇒ ok=False 且 reason=\"missing_params\"，并列出缺哪个。"""
        proto = NET.PenetrationProtocol()
        node = NET.CapabilityNode(name="y", requires_params=["target"])
        r = proto.penetrate(node, {})
        self.assertIs(r["ok"], False)
        self.assertEqual(r["reason"], "missing_params")
        self.assertEqual(r["missing"], ["target"])

    def test_implemented_readonly_column_is_computed_not_hardcoded(self):
        """带牙 ③：`verified(readonly)` 这一栏**必须是现算的**，且只读位必须有入口。

        🔴 2026-09-22 第 35 轮重写（错报治理）。原来这条叫
        `..._carries_evidence_ref` 并写死两个数字：
        `assertEqual(len(green), 6, "应是 6 位（9 口）")` 与
        `assertEqual(seven["verified(readonly)"], "9 口 / 6 位")`。

        两个问题，都是"错报"：
        1. **判据与产品一起写死** —— 产品里那栏本来就是 `"%d 口 / %d 位" % (9, 6)`（字面量），
           测试再把 9/6 抄一遍 ⇒ 两边同错同对，**这条判据失去了发现能力**：
           真值是 5，它守的却不是事实而是"有没有变"。而且 `9` 在盘上**无定义、无来源**
           （见 `build_net` 的 `metric_defs`），"守住 9"本身没有意义。
        2. 原来那句 `all(n.evidence_ref is not None)` 是**空过**：
           `evidence_ref` 默认 `""`，全仓 147 条注册表 **0 条**带 evidence 字段
           ⇒ 空串也不等于 None，断言恒真。名字说"carries evidence_ref"，实际什么都没验。

        ⇒ 现改成**反漂移判据**：报告串必须**逐字等于现算值**。谁把字面量写回去，这里立刻红。
        """
        net = NET.build_net()
        local = net["local"]
        green = [n for n in local if n.verified_readonly]

        # ① 非空：一位都没有的话，"已核实只读"就是空话
        self.assertTrue(green, "verified(readonly) 一位都没有 ⇒ 这一栏是空话")
        # ② 真不变量：已核实只读 ⇒ 必然有入口文件在盘上（没入口谈不上"已核实"）
        self.assertTrue(all(n.entry_known for n in green),
                        "已核实只读却没有入口文件：%s"
                        % [n.name for n in green if not n.entry_known])
        # ③ 反漂移：写得像读数的字面量，在这里必被抓
        expect = "%d 口 / %d 位" % (len([n for n in green if n.entry_known]), len(green))
        seven = net["seven_columns"]
        self.assertEqual(seven["verified(readonly)"], expect,
                         "verified(readonly) 与现算值不一致 ⇒ 有人把读数写死了")
        self.assertEqual(seven["penetrate_ready"], expect,
                         "penetrate_ready 与现算值不一致 ⇒ 有人把读数写死了")
        # ④ 口径必须随读数一起交出去，否则读的人还得猜单位
        self.assertIn("位", net.get("metric_defs", {}))
        self.assertIn("口", net.get("metric_defs", {}))
        # ⑤ evidence_ref 的**已知缺口**必须显式登记（不许假装有证据）
        self.assertIn("evidence_ref_note", net)
        self.assertIn("恒为空串", net["evidence_ref_note"])
        self.assertIn("在索引里", net["honest_boundary"])

    def test_all_honest_flags_default_false(self):
        """默认档：六个诚实位一个都不许默认 True（没跑过就是 False）。"""
        n = NET.CapabilityNode(name="z")
        for attr in ("indexed", "entry_known", "reachable", "verified_reachable",
                     "verified_readonly", "has_test", "penetrate_ready"):
            self.assertIs(getattr(n, attr), False, f"{attr} 不许默认 True")

    def test_needs_review_each_has_a_trigger(self):
        """挂账必须有复查触发条件 —— 没有触发条件的挂账是死账。"""
        for k, v in NET.NEEDS_REVIEW_TRIGGERS.items():
            self.assertTrue(str(v).strip(), f"{k} 缺触发条件")

    def test_router_is_readonly_and_source_has_no_execution(self):
        net = NET.build_net()
        router = NET.SwitchRouter(net["nodes"])
        hit = router.route("recon", "category")
        self.assertIsInstance(hit, list)
        self.assertTrue(all(isinstance(n, NET.CapabilityNode) for n in hit))
        tree = ast.parse(inspect.getsource(NET))
        # 摘掉扫描器自己的模式表（PROC_PRIMITIVES 的定义行）—— 否则会扫到"提到"而不是"用了"
        tree.body = [n for n in tree.body
                     if not (isinstance(n, ast.Assign)
                             and any(getattr(t, "id", "") == "PROC_PRIMITIVES"
                                     for t in n.targets))]
        for node_ in ast.walk(tree):
            if isinstance(node_, (ast.Module, ast.FunctionDef, ast.ClassDef)):
                if (node_.body and isinstance(node_.body[0], ast.Expr)
                        and isinstance(getattr(node_.body[0], "value", None), ast.Constant)
                        and isinstance(node_.body[0].value.value, str)):
                    node_.body.pop(0)
        code = "\n".join(l.split("#", 1)[0] for l in ast.unparse(tree).splitlines())
        for bad in ("run_task(", "subprocess", "Popen", "os.system", "urlopen"):
            self.assertNotIn(bad, code, f"骨架不许有执行原语：{bad}")


if __name__ == "__main__":
    unittest.main()
