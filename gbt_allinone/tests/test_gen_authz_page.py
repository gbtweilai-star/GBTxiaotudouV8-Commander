"""R-H621（2026-09-26）· **待授权清单页的生成器**自己的判据。

被测对象：`tools/codex-scripts/gen-authz-page.py`（主人要读的那一页的产出方）

为什么要立它（第 47 轮的实据）：
  原来那个生成器住在**易失目录** `.scratch/_gen_scope_page.py`，产出的却是主人要读的一页；
  它把 `138` / `157` / `129` / `30` / `168` / `3 件事` / `8` / `11` 这些**总数写死在代码里**，
  而页面写着「**本页由脚本现算，不手抄**」。于是注册表从 157 长到 **172** 之后，
  **那页的每个总数都错了，它还在自称现算**。⇒ 登记 F14，并把这个生成器重写进 `tools/codex-scripts/`。

判据五条：
  1. **总数必须等于现读真值**：`registry` == `len(caps_registry.all_caps())`；
     `zero_scope` / `safe_false` 也必须等于**独立现算**的结果（不是抄生成器自己的）；
  2. **缺数据不许生成**：探针账不在 ⇒ 退出码 2（不许拿旧数顶）；
  3. 产物（`docs/待授权清单一页.md`）里必须出现**现读的注册表条数** —— 页与真值对得上；
  4. **回归闸**：源码里不许再出现写死的总数（`138/138`、`157`、`129`、`168`、`3 件事` 这些字面量）；
  5. 写盘后**自验**这件事本身要在源码里（跑完了但写的还是旧数 ⇒ 必须能自己发现）。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "codex-scripts" / "gen-authz-page.py"
PAGE = ROOT / "docs" / "待授权清单一页.md"
sys.path.insert(0, str(ROOT))


def _load():
    spec = importlib.util.spec_from_file_location("gen_authz_page", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load()


def _live():
    from gbt_allinone import caps_registry as R
    from gbt_allinone.security import policy as POL
    caps = R.all_caps()
    zero = 0
    for c in caps:
        try:
            if not (getattr(POL.evaluate(c["name"], {}), "scopes", ()) or ()):
                zero += 1
        except Exception:  # noqa: BLE001
            pass
    return len(caps), zero, sum(1 for c in caps if not c.get("safe"))


class TotalsMustBeLiveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        p = subprocess.run([sys.executable, str(TOOL), "--dry-run", "--json"],
                           cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300)
        i = p.stdout.find("{")
        cls.rep = json.loads(p.stdout[i:]) if i >= 0 else {}
        cls.rc = p.returncode

    def test_registry_total_equals_live_registry(self) -> None:
        n_reg, _z, _s = _live()
        self.assertEqual(n_reg, self.rep.get("registry"),
                         "页面里的注册表条数 != 现读 all_caps() ⇒ 又是写死的数")

    def test_zero_scope_and_safe_false_equal_independent_count(self) -> None:
        _n, zero, safe_false = _live()
        self.assertEqual(zero, self.rep.get("zero_scope"), "零作用域数不是现算的")
        self.assertEqual(safe_false, self.rep.get("safe_false"), "safe=False 数不是现算的")

    def test_probe_age_is_reported(self) -> None:
        self.assertIn("probe_age_hours", self.rep, "页头没印探针数据的时间 ⇒ 读者不知道它多旧")
        self.assertGreaterEqual(float(self.rep["probe_age_hours"]), 0.0)


class RefuseWhenDataMissingTest(unittest.TestCase):
    def test_missing_probe_ledger_refuses(self) -> None:
        orig = MOD.ACC
        try:
            MOD.ACC = ROOT / "state" / "___not_here___.json"
            rc = MOD.main(["--dry-run"])
        finally:
            MOD.ACC = orig
        self.assertEqual(2, rc, "探针账不在却照样生成 ⇒ 会拿旧数/空数顶成'现算'")


class ArtifactMatchesTruthTest(unittest.TestCase):
    def test_page_contains_live_registry_number(self) -> None:
        n_reg, _z, _s = _live()
        self.assertTrue(PAGE.is_file(), "页不在：%s" % PAGE)
        text = PAGE.read_text(encoding="utf-8")
        self.assertIn(str(n_reg), text, "页里没有现读的注册表条数 %d ⇒ 页与真值对不上" % n_reg)
        self.assertIn("gen-authz-page.py", text, "页头没写清是哪个生成器产出的")

    def test_page_stamps_probe_timestamp(self) -> None:
        text = PAGE.read_text(encoding="utf-8")
        self.assertIn("caps-probe-accum.json", text, "页头没写逐位数据的出处")
        self.assertRegex(text, r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", "页头没有时间戳")


class NoHardcodedTotalsTest(unittest.TestCase):
    """第 4 条：回归闸 —— 就是第 47 轮那个病根，钉住它。"""

    def test_source_has_no_hardcoded_totals_in_output(self) -> None:
        src = TOOL.read_text(encoding="utf-8")
        for bad in ("138/138", "129 / 157", "全 168 位", "卡在 `3 件事`"):
            self.assertNotIn(bad, src, "源码里又出现写死的总数：%s" % bad)

    def test_self_verification_after_write_exists(self) -> None:
        src = TOOL.read_text(encoding="utf-8")
        self.assertIn("写盘后自验", src, "少了写盘后自验 ⇒ 可能'跑完了但写的还是旧数'")
        self.assertIn("return 3", src, "自验不过必须有独立退出码")


if __name__ == "__main__":
    unittest.main()
