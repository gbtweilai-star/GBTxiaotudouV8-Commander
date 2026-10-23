"""R-H612（2026-09-25）· **开机自检总入口**本身也要被守着。

被测对象：`tools/codex-scripts/boot-selfcheck.py`
它把六条常设判据 + 两道闸收成**一次执行、一个退出码**。立它的理由是本仓那句话：
「**判据散着 = 没人跑**」。但总入口自己会烂 —— 所以它需要自己的判据。

判据（四条，都要有牙）：
  1. 判据组**一条不许漏**（对着 `JUDGMENTS` 逐个点名跑一遍；条数**现算**，不写死 ——
     写死一次过期一次，2026-09-25 加「云端点闸行为」时这条救了一次）；
  2. 两道闸（装机副本漂移 / 重启验收单）都要在，且**跑不动时算红、不许记成跳过**
     （这是总入口最容易长歪的地方：把"没跑成"写成"没问题"）；
  3. 每个步骤都必须带 `ok` / `rc` / `now` / `cmd` 四件套 —— 少了 `now`，红了也不知道现在是什么；
  4. 结论与红数必须自洽（`ok == (red_count == 0)`），且**不许重写第二份判据**
     （它只调既有 unittest 模块，源码里不许出现断言体）。
"""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest
import unittest.mock as mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOOT = ROOT / "tools" / "codex-scripts" / "boot-selfcheck.py"


def _load():
    spec = importlib.util.spec_from_file_location("boot_selfcheck", BOOT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BOOTMOD = _load()


def _fake_run_plan(plan, env, jobs):
    """形状测试用的**桩执行器**：按计划返回 rc=0，不真跑那 27 个判定模块。

    🔴 2026-10-17 翻正（留痕 · 原做法 / 为什么翻 / 现做法）：
      原做法：`setUpClass` 直接 `BOOTMOD.selfcheck(quick=True)` —— 那会**真跑**
              `JUDGMENTS` 里 27 个 unittest 模块（每个上限 600s，实测全串行 457s），
              而且两个测试类各跑一次 ⇒ 光这一个文件就要 ~15 分钟。
              而本仓 `run-tests.py` 的口径是**每根 `--timeout=180`** ⇒ 这条测试
              **在任何 runner 下都必死**，并且它是"在测试里再跑一遍整套测试"（dozens× 放大）。
      原期望【不变】：总入口的形状四条 —— ①判据一条不漏 ②两道闸都在
              ③每步四件套 ④结论与红数自洽。
      现做法：形状测试用**桩执行器**（不执行子进程）验报告形状；
              "判据真的绿"由**开机时真跑** `boot-selfcheck.py` 负责，不由单测重复承担。
              另补 `OneJudgmentReallyRunsTest` 真跑一条**快**判据（~0.3s），
              保住"执行器真能跑通"这条牙，而不是全用桩。
    """
    todo = [e for e in plan if e["kind"] not in ("skipped", "missing_gate", "missing_sheet")]
    return {i: (0, "OK", 0.1) for i, _e in enumerate(todo)}


class BootSelfcheckShapeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # 跳过重启验收单（它要起 HTTP 请求），但**判据组与漂移闸照跑**
        # （形状层面照跑：桩只替代"真执行"，计划表本身仍是完整的那一份）
        with mock.patch.object(BOOTMOD, "_run_plan", side_effect=_fake_run_plan):
            cls.rep = BOOTMOD.selfcheck(quick=True)

    def test_every_judgment_is_present_and_green(self) -> None:
        steps = {s["step"]: s for s in self.rep["steps"]}
        for label, _mod in BOOTMOD.JUDGMENTS:
            key = "判据/" + label
            self.assertIn(key, steps, "总入口漏了这条判据：%s" % label)
            self.assertTrue(steps[key]["ok"], "%s 现在红了：%s" % (label, steps[key]["now"]))

    def test_both_gates_are_present(self) -> None:
        steps = {s["step"]: s for s in self.rep["steps"]}
        self.assertIn("闸/装机副本漂移", steps)
        self.assertIn("闸/重启验收单", steps)

    def test_every_step_carries_the_four_fields(self) -> None:
        for s in self.rep["steps"]:
            for k in ("ok", "rc", "now", "cmd"):
                self.assertIn(k, s, "步骤 %s 缺字段 %s" % (s.get("step"), k))
            self.assertTrue(str(s["now"]).strip(), "步骤 %s 的 now 是空的" % s["step"])

    def test_verdict_is_consistent_with_red_count(self) -> None:
        self.assertEqual(self.rep["ok"], self.rep["red_count"] == 0,
                         "结论与红数自相矛盾 ⇒ 读的人会被两头骗")


class MissingToolIsRedNotSkippedTest(unittest.TestCase):
    """第 2 条判据的负对照：工具不在盘上时，必须是**红**，不是"跳过/没问题"。"""

    def test_missing_gate_is_red(self) -> None:
        orig = BOOTMOD.DRIFT_GATE
        BOOTMOD.DRIFT_GATE = ROOT / "__no_such_gate__.mjs"
        try:
            # 同上面的理由：只验「闸不在盘上 ⇒ 判红」这条形状，不必真跑 27 个判定模块。
            with mock.patch.object(BOOTMOD, "_run_plan", side_effect=_fake_run_plan):
                rep = BOOTMOD.selfcheck(quick=True)
        finally:
            BOOTMOD.DRIFT_GATE = orig
        row = next(s for s in rep["steps"] if s["step"] == "闸/装机副本漂移")
        self.assertFalse(row["ok"], "闸不在盘上却判成通过 ⇒ 这就是'把没跑成写成没问题'")
        self.assertIn("不许当跳过", row["now"])
        self.assertFalse(rep["ok"])


class OneJudgmentReallyRunsTest(unittest.TestCase):
    """保留一条**真执行**的牙：桩只用于形状测试，执行器本身必须真能跑通一条判据。

    （0.3s 的快判据；真跑 27 条属于开机闸的职责，不在单测里重复。）
    """

    def test_a_fast_judgment_really_runs(self) -> None:
        env = BOOTMOD._env(os.environ.get("GBT_STORE_DIR") or "")
        rc, out = BOOTMOD._run(
            [sys.executable, "-m", "unittest", "gbt_allinone.tests.test_endpoint_gate"],
            env, 120)
        self.assertEqual(rc, 0, (out or "")[-600:])


class NoSecondCopyOfJudgmentsTest(unittest.TestCase):
    """总入口只许**调**判据，不许**抄**判据。"""

    def test_source_calls_unittest_but_writes_no_assertions(self) -> None:
        src = BOOT.read_text(encoding="utf-8", errors="replace")
        self.assertIn('"-m", "unittest"', src, "总入口没有去跑既有判据模块")
        # 它自己不该出现断言体（抄一份判据出来 = 两份会慢慢长歪）
        for bad in ("assertEqual(", "assertTrue(", "assertIn("):
            self.assertNotIn(bad, src, "总入口里出现了断言体 %s ⇒ 判据有第二份了" % bad)

    def test_judgments_point_at_real_test_modules(self) -> None:
        for label, mod in BOOTMOD.JUDGMENTS:
            rel = Path(mod.replace(".", "/") + ".py")
            self.assertTrue((ROOT / rel).is_file(),
                            "判据 %s 指向的模块不存在：%s" % (label, rel))


if __name__ == "__main__":
    unittest.main(verbosity=2)
