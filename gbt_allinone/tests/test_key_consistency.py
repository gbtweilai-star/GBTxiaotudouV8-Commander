"""R-H618（2026-09-25）· **密钥一致性对账**自己的判据。

被测对象：`tools/codex-scripts/key-consistency-check.py`

立它的理由（一手账）：主人令「密钥全部部署跟双向插件一样、可以自动读取」⇒ 密钥现在
**存了两份**（User 作用域注册表 + DPAPI 保险箱）。两份就是两个真相源 —— 轮换时只改一处，
另一处就静默过期。**这不是假想**：本器首跑就现读出一条已经分叉的（`agnes`：库 `sk-HX****`
vs 注册表 `sk-Oy****`）；分叉的后果不是报错，是"有时能通、有时 401"，最难查的那类故障。

判据设计上的取舍（**不许写成快照**）：
  · **不断言"没有分叉"** —— 分叉是主人的决定（哪份是新的），轮不到用例替他判
    （写成"必须无分叉"= 逼着人删掉一条真读数才绿，那是本仓打过的那种假判据）；
  · 断的是**不变量**：分类逻辑四态正确（含负控）· 真机读数自洽（分叉行指纹必须不同、
    一致行指纹必须相同）· 明文不许出现在输出里 · 与 `deepseek_key._PROFILES` 逐 profile 对齐。
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "codex-scripts" / "key-consistency-check.py"


def _load():
    spec = importlib.util.spec_from_file_location("key_consistency_check", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load()


class ClassifyTest(unittest.TestCase):
    """分类逻辑四态 + 负控（纯函数，不用碰真注册表）。"""

    def test_same_value_is_consistent(self) -> None:
        self.assertEqual("一致", MOD.classify("sk-abc123", "sk-abc123"))

    def test_different_values_are_split(self) -> None:
        """**负控**：两份不同必须判分叉 —— 这是本器存在的唯一理由。"""
        self.assertEqual("分叉", MOD.classify("sk-HXxxxx", "sk-Oyxxxx"))

    def test_only_one_side_is_not_an_error(self) -> None:
        self.assertEqual("只在保险箱", MOD.classify("sk-a", ""))
        self.assertEqual("只在注册表", MOD.classify("", "sk-a"))

    def test_neither_side(self) -> None:
        self.assertEqual("两处都没有", MOD.classify("", ""))

    def test_whitespace_does_not_fake_a_split(self) -> None:
        """首尾空白不该造成假分叉（它是最像"两份不同"的同值）。"""
        self.assertEqual("一致", MOD.classify(" sk-a \n", "sk-a"))


class RealRunTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.p = subprocess.run([sys.executable, str(TOOL), "--json"], cwd=str(ROOT),
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=180)
        i = cls.p.stdout.find("{")
        cls.rep = json.loads(cls.p.stdout[i:]) if i >= 0 else {}

    def test_runs_and_covers_every_profile(self) -> None:
        rows = self.rep.get("rows", [])
        sys.path.insert(0, str(ROOT))
        from gbt_allinone import deepseek_key as dk
        self.assertEqual(sorted(dk._PROFILES), sorted(r["profile"] for r in rows),
                         "对账没覆盖全部 profile")
        self.assertIn(self.p.returncode, (0, 1), "退出码只该是 0（无分叉）或 1（有分叉）")

    def test_reading_is_self_consistent(self) -> None:
        """不变量：判『分叉』的行指纹必须不同；判『一致』的行指纹必须相同。"""
        for r in self.rep.get("rows", []):
            with self.subTest(profile=r["profile"]):
                if r["verdict"] == "分叉":
                    self.assertNotEqual(r["vault_fp"], r["registry_fp"],
                                        "判了分叉却指纹相同 ⇒ 读数自相矛盾")
                    self.assertTrue(r["vault_fp"] and r["registry_fp"], "分叉必须两处都有")
                elif r["verdict"] == "一致":
                    self.assertEqual(r["vault_fp"], r["registry_fp"], "判了一致却指纹不同")

    def test_no_plaintext_ever_leaks(self) -> None:
        """红线：读数里只许有掩码与指纹，不许出现任何完整密钥。"""
        sys.path.insert(0, str(ROOT))
        from gbt_allinone import deepseek_key as dk
        for name in dk._PROFILES:
            key, _s = dk.load_from_vault(name)
            if len(key) >= 16:
                self.assertNotIn(key, self.p.stdout,
                                 "对账输出里出现了 %s 的完整密钥" % name)

    def test_exit_code_matches_split_presence(self) -> None:
        """退出码与读数必须自洽（有分叉 ⇒ 1；无 ⇒ 0）——判据只判这一致性，不判有没有分叉。"""
        split = [r for r in self.rep.get("rows", []) if r["verdict"] == "分叉"]
        self.assertEqual(1 if split else 0, self.p.returncode,
                         "退出码与分叉读数不一致")


if __name__ == "__main__":
    unittest.main()
