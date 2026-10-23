"""R-H607（2026-09-25）· **被写进 system prompt 的自校验命令，自己必须跑得起来**。

被测故障（现读崩溃，不是推演）：
    `cloud_llm.py` 的 `_BUILTIN_AWARENESS`（会原样注入 system prompt）里写着

        自校验：    python -m gbt_allinone.tools.awareness_gap_guard

    而这条命令**一跑就崩**：`KeyError: 'disabled'` ——
    `awareness_gap_guard.py:225` 读的是 `t['disabled']`，而 `truth_on_disk` 字典里的键叫 **`denied`**
    （同一个文件 150-153 行构造的）。**一条自我介绍里让模型去跑的自检命令，跑不起来。**

判据（三条，都要有牙）：
  1. 三个公开入口（人读档 / `--json` / `--check`）都必须**真能跑完**（rc=0 且输出可读）；
  2. `truth_on_disk` 里**打印机读的每个键都必须真的存在** ——
     这条是**结构判据**：把"键名对不上"这类病在提交前就咬出来，而不是等某天有人手跑才发现；
  3. system prompt 里**点名的那条命令**必须与真实模块路径一致（防"改了模块名、文本没跟"）。
"""
from __future__ import annotations

import ast
import io
import json
import re
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from gbt_allinone.llm import cloud_llm as cl
from gbt_allinone.tools import awareness_gap_guard as agg

ROOT = Path(__file__).resolve().parents[2]
GUARD_PY = Path(agg.__file__)


class GuardActuallyRunsTest(unittest.TestCase):
    def test_human_readable_mode_runs(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = agg.main([])                     # 人读档：崩溃点原来就在这里
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("盘上真实的自己", out)
        self.assertIn("能力位", out)

    def test_json_mode_runs_and_parses(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = agg.main(["--json"])
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue())
        self.assertIn("truth_on_disk", data)
        self.assertEqual(data["truth_on_disk"]["capabilities_total"], len(
            __import__("gbt_allinone.caps_registry", fromlist=["BENIGN_CAPS"]).BENIGN_CAPS))

    def test_check_mode_runs(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = agg.main(["--check"])
        self.assertIn(rc, (0, 1), "--check 只许 0（无硬冲突）或 1（有硬冲突），不许崩")
        self.assertNotIn("Traceback", buf.getvalue())


class TruthKeysAreAllPrintableTest(unittest.TestCase):
    """结构判据：打印机从 `t[...]` 取的每个常量键，`truth` 字典里必须真有。"""

    def _printed_subscripts(self):
        tree = ast.parse(GUARD_PY.read_text(encoding="utf-8", errors="replace"))
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "main")
        keys = set()
        for node in ast.walk(fn):
            # 形如 t["xxx"]，且 t 是本函数里的局部名字
            if (isinstance(node, ast.Subscript)
                    and isinstance(node.value, ast.Name) and node.value.id == "t"
                    and isinstance(node.slice, ast.Constant)
                    and isinstance(node.slice.value, str)):
                keys.add(node.slice.value)
        return keys

    def test_every_printed_key_exists_in_truth(self) -> None:
        truth = agg.run()["truth_on_disk"]
        printed = self._printed_subscripts()
        self.assertTrue(printed, "一条都没解析到 —— 判据失效了（比崩溃更坏）")
        missing = sorted(k for k in printed if k not in truth)
        self.assertEqual([], missing,
                         "main() 打印时读的键在 truth_on_disk 里不存在：%s（现读键：%s）"
                         % (missing, sorted(truth)))


class AdvertisedCommandIsRealTest(unittest.TestCase):
    """system prompt 里点名的自检命令，必须与真实模块路径一致。"""

    def test_prompt_mentions_the_real_module_path(self) -> None:
        text = cl._BUILTIN_AWARENESS
        m = re.search(r"python -m (gbt_allinone\.tools\.awareness_gap_guard)", text)
        self.assertIsNotNone(m, "自我认知里不再点名自校验命令了？")
        mod = m.group(1)
        path = ROOT / (mod.replace(".", "/") + ".py")
        self.assertTrue(path.is_file(), "自我认知点名的模块不存在：%s" % mod)

    def test_prompt_does_not_state_a_stale_cap_count(self) -> None:
        """自我认知里不许出现静态能力计数（它自己写了"不许再静态罗列"）。"""
        text = cl._BUILTIN_AWARENESS
        for bad in ("118", "158", "110", "119"):
            self.assertNotIn(bad, text,
                             "自我认知里出现了静态计数 %s —— 它会随真身漂移" % bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
