# -*- coding: utf-8 -*-
"""原子替换器的风险分级闸（2026-11-06 主人令）。

主人原话：「只有危险能力使用和资金转账需要终端 YES，其他的 GBT 自己决策」。

这里锁死三件事：
  1. 判级矩阵：文档/技能/普通代码 = normal；可执行载体/授权门 = danger；转账类 = finance；
  2. normal 在**没有点赞**时也放行（自决），danger/finance 没有点赞必须拦；
  3. 一批里有一个危险件 ⇒ 整批走人工（不拆开偷偷放行）。

测试全程不碰真实 state（_ledger 与 like_status 都被替换成内存实现）。
"""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "codex-scripts" / "atomic-sync.py"


def _load():
    spec = importlib.util.spec_from_file_location("atomic_sync_under_test", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestClassify(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load()

    def test_matrix(self):
        cases = [
            ("gbt_allinone/skills/shuohao/novel-art/SKILL.md", "normal"),
            ("holo_pet_w3/console/index.html", "normal"),
            ("gbt_allinone/brain_exec.py", "normal"),
            ("state/operator-index.json", "normal"),
            ("pyembed/python.exe", "danger"),
            ("setup.ps1", "danger"),
            ("holo_pet_w3/shell/main.cjs", "danger"),
            ("gbt_allinone/auth_gate.py", "danger"),
            ("gbt_allinone/security/policy.py", "danger"),
            ("gbt_allinone/caps_registry.py", "danger"),
            ("tools/codex-scripts/atomic-sync.py", "danger"),
            ("state/source-pull/like.json", "danger"),
            ("gbt_allinone/transfer.py", "finance"),
            ("docs/转账流程.md", "finance"),
            # 2026-11-06 反向审计补的洞：解释器/依赖/契约本体/钩子 = 执行面
            ("pyembed/Lib/site-packages/pyperclip/__init__.py", "danger"),
            ("pyembed/python312._pth", "danger"),
            ("holo_pet_w3/node_modules/x/install.js", "danger"),
            ("holo_pet_w3/package.json", "danger"),
            ("gbt_allinone/tentacle/autonomy.py", "danger"),
            ("gbt_allinone/tools/action_gate.py", "danger"),
            (".git/hooks/pre-commit", "danger"),
        ]
        for rel, want in cases:
            with self.subTest(rel=rel):
                self.assertEqual(self.m.classify_rel(rel)["tier"], want)

    def test_batch_takes_worst(self):
        d = self.m.classify_many(["a.md", "b.md", "tools/codex-scripts/atomic-sync.py"])
        self.assertEqual(d["tier"], "danger")
        self.assertEqual(d["counts"]["normal"], 2)
        self.assertEqual(len(d["manual"]), 1)

    def test_batch_all_normal(self):
        d = self.m.classify_many(["a.md", "holo_pet_w3/console/index.html"])
        self.assertEqual(d["tier"], "normal")
        self.assertEqual(d["manual"], [])


class TestGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load()

    def setUp(self):
        self.log = []
        self._orig_ledger = self.m._ledger
        self._orig_like = self.m.like_status
        self.m._ledger = lambda root, rec: self.log.append(rec)
        # 没有点赞
        self.m.like_status = lambda root: {"ok": False, "status": "need_like",
                                           "error": "还没有点赞"}
        self._strict = os.environ.pop("GBT_SYNC_STRICT", None)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "payload"
        self.root.mkdir()

    def tearDown(self):
        self.m._ledger = self._orig_ledger
        self.m.like_status = self._orig_like
        if self._strict is not None:
            os.environ["GBT_SYNC_STRICT"] = self._strict
        else:
            os.environ.pop("GBT_SYNC_STRICT", None)
        self.tmp.cleanup()

    def test_normal_auto_without_like(self):
        dst = self.root / "gbt_allinone" / "skills" / "x.md"
        block, info = self.m._consume_like(self.root, dst, rel="/gbt_allinone/skills/x.md")
        self.assertIsNone(block)
        self.assertEqual(info["mode"], "auto")
        self.assertTrue(any(r.get("op") == "auto_approve" for r in self.log))

    def test_danger_blocked_without_like(self):
        dst = self.root / "gbt_allinone" / "auth_gate.py"
        block, info = self.m._consume_like(self.root, dst, rel="/gbt_allinone/auth_gate.py")
        self.assertIsNotNone(block)
        self.assertEqual(block["status"], "need_like")
        self.assertEqual(info["tier"], "danger")

    def test_finance_blocked_without_like(self):
        dst = self.root / "gbt_allinone" / "transfer.py"
        block, info = self.m._consume_like(self.root, dst, rel="/gbt_allinone/transfer.py")
        self.assertIsNotNone(block)
        self.assertEqual(info["tier"], "finance")

    def test_strict_mode_forces_manual_for_normal(self):
        os.environ["GBT_SYNC_STRICT"] = "1"
        dst = self.root / "docs" / "x.md"
        block, info = self.m._consume_like(self.root, dst, rel="/docs/x.md")
        self.assertIsNotNone(block)
        self.assertEqual(info["mode"], "manual")

    def test_outside_product_never_gated(self):
        dst = Path(self.tmp.name) / "elsewhere" / "x.exe"
        block, info = self.m._consume_like(self.root, dst, rel="/x.exe")
        self.assertIsNone(block)
        self.assertEqual(info["mode"], "not_product")


if __name__ == "__main__":
    unittest.main()