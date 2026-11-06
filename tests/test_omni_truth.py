# -*- coding: utf-8 -*-
"""万能插 / 多域监控的「自述 vs 实际」铁证判据。

全部来自 2026-11-05 用 AST 对账 + 实测抓出的真问题，不是臆想：

  A. `omni_plug._dispatch` 实际认 42 个 op，而它的 known 自述曾经只列 37 个
     （漏 page_route / page_stats / disk_find / disk_stats / 任意）——
     照自述调用的人摸不到入口。L1666 的注释自己承认过同一问题，后来又漏了一次。
  B. `impact_check.run_op` 的 `risky` 原来是**兜底 return**：
     OPS 里以后新增 op 却忘写分支，会**静默变成 risky**，返回值看着正常、口径全错。
  C. `omni_adapter.classify` 把盘上真实存在的 `AGENTS.md` 判成 `https://AGENTS.md`
     ⇒ policy 挂 `external_llm` + `data_export`，回执说「把当前任务数据发送到外部大模型服务」
     —— 而它只是**读一个本地文件**。
  D. `tools/page_lazy.py` 顶层 `import resource` —— Unix-only，Windows 上整份 import 不了，
     连带 `op=page_stats` 直接 ModuleNotFoundError。

四条都是静态判据，不起服务、不联网。
"""
from __future__ import annotations

import ast
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _cstr(n):
    return n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) else None


def _op_literals(fn):
    """函数里 `op == "x"` / `op in ("a","b")` 的字面量。"""
    got = set()
    for n in ast.walk(fn):
        if not isinstance(n, ast.Compare) or len(n.ops) != 1:
            continue
        left, op, right = n.left, n.ops[0], n.comparators[0]
        if isinstance(left, ast.Name) and left.id == "op":
            tgt = right
        elif isinstance(right, ast.Name) and right.id == "op":
            tgt = left
        else:
            continue
        if isinstance(op, ast.Eq):
            s = _cstr(tgt)
            if s:
                got.add(s)
        elif isinstance(op, ast.In) and isinstance(tgt, (ast.Tuple, ast.List, ast.Set)):
            for e in tgt.elts:
                s = _cstr(e)
                if s:
                    got.add(s)
    return got


def _find(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


class TestOmniSelfDescription(unittest.TestCase):
    """A · 自述必须等于实际"""

    def test_known_matches_dispatch(self):
        p = os.path.join(ROOT, "gbt_allinone", "omni_plug.py")
        tree = ast.parse(open(p, encoding="utf-8").read(), filename=p)
        fn = _find(tree, "_dispatch")
        self.assertIsNotNone(fn, "找不到 _dispatch")
        actual = _op_literals(fn)
        declared = set()
        for n in ast.walk(fn):
            if isinstance(n, ast.Dict):
                for k, v in zip(n.keys, n.values):
                    if _cstr(k) == "known" and isinstance(v, ast.List):
                        for e in v.elts:
                            s = _cstr(e)
                            if s:
                                declared.add(s)
        self.assertTrue(declared, "找不到 known 自述列表")
        missing = sorted(actual - declared)
        self.assertEqual(
            missing, [],
            "这些 op 实际认、但 known 自述没列 —— 照自述调用的人摸不到它们：%s" % missing)


class TestImpactCheckOpsHonest(unittest.TestCase):
    """B · OPS 声明的每个 op 都必须有实现分支（不许靠兜底）"""

    def test_every_op_has_branch(self):
        p = os.path.join(ROOT, "gbt_allinone", "tools", "impact_check.py")
        tree = ast.parse(open(p, encoding="utf-8").read(), filename=p)
        ops = None
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    if isinstance(t, ast.Name) and t.id == "OPS":
                        if isinstance(n.value, (ast.Tuple, ast.List)):
                            ops = {_cstr(e) for e in n.value.elts if _cstr(e)}
        self.assertTrue(ops, "找不到 OPS 常量")
        fn = _find(tree, "run_op")
        self.assertIsNotNone(fn, "找不到 run_op")
        branches = _op_literals(fn)
        missing = sorted(ops - branches)
        self.assertEqual(
            missing, [],
            "OPS 声明了但没有实现分支的 op：%s —— 它们会掉到兜底，"
            "返回值看着正常、口径全错（risky 原来就是这么兜的）" % missing)


class TestAdapterClassify(unittest.TestCase):
    """C · 本地路径不许被判成 URL（否则挂 external_llm 外发票）"""

    @classmethod
    def setUpClass(cls):
        p = os.path.join(ROOT, "tools", "omni_adapter.py")
        spec = importlib.util.spec_from_file_location("_oa_guard", p)
        cls.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)

    def _kind(self, t):
        return self.m.classify(t).get("kind")

    def test_real_local_file_is_path(self):
        for t in ("AGENTS.md", "gbt_allinone/api.py", "./AGENTS.md",
                  "tools/impact_check.py"):
            self.assertEqual(
                self._kind(t), "path",
                "%r 被判成 %r —— 盘上的本地路径必须是 path，"
                "否则 policy 会挂 external_llm（读本地文件被当成发外网）"
                % (t, self._kind(t)))

    def test_urls_still_url(self):
        for t, want in (("example.com", "http"),
                        ("http://127.0.0.1:8791", "http"),
                        ("https://api.openai.com/v1", "http"),
                        ("ws://127.0.0.1:9000", "ws")):
            self.assertEqual(self._kind(t), want, "%r 应判 %s" % (t, want))

    def test_dirs_and_bins(self):
        self.assertEqual(self._kind("state/"), "dir")
        self.assertEqual(self._kind("git"), "bin")


class TestPageLazyWindowsPortable(unittest.TestCase):
    """D · `resource` 是 Unix-only，不许在顶层硬 import"""

    def test_page_lazy_imports_on_windows(self):
        p = os.path.join(ROOT, "tools", "page_lazy.py")
        src = open(p, encoding="utf-8").read()
        tree = ast.parse(src, filename=p)
        top_plain = set()
        for n in tree.body:                                  # 只看模块顶层
            if isinstance(n, ast.Import):
                for a in n.names:
                    top_plain.add(a.name)
        self.assertNotIn(
            "resource", top_plain,
            "tools/page_lazy.py 又在顶层 import resource 了 —— 那是 Unix-only，"
            "Windows 上整份文件 import 不了，op=page_stats 会直接 ModuleNotFoundError")
        # 并且必须真的能 import（本机是 Windows）
        spec = importlib.util.spec_from_file_location("_pl_guard", p)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except ModuleNotFoundError as e:
            self.fail("page_lazy.py 在本机 import 失败：%s" % e)


class TestJudgementToolExists(unittest.TestCase):
    """E · 「判据在 X」这句话本身也要有判据。

    来历（2026-11-05）：`omni_plug.py:1668` 与 `caps_registry.py:1615` 都写着
    「判据在 `tools/codex-scripts/omni-monitor.py --gap`（AST 三向对账）」，
    而那个文件**不存在**；`gbt_allinone/omni_monitor.py` 也没有 `--gap`/`main()`。
    自述漏 5 个 op 那种事，就是在这种「以为有人看着、其实没人看着」的状态下发生的。
    """

    def test_gap_tool_exists_and_runs(self):
        p = os.path.join(ROOT, "tools", "codex-scripts", "omni-monitor.py")
        self.assertTrue(
            os.path.isfile(p),
            "被注释点名的判据 tools/codex-scripts/omni-monitor.py 不存在 —— "
            "「判据在 X」这句话本身没有判据")
        spec = importlib.util.spec_from_file_location("_om_gap", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        r = mod.three_way()
        self.assertTrue(r.get("ok"), "三向对账跑不起来：%r" % (r.get("error"),))
        for key in ("impl_minus_declared", "declared_minus_impl", "desc_minus_impl"):
            self.assertEqual(r.get(key), [], "%s 不为空：%s" % (key, r.get(key)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
