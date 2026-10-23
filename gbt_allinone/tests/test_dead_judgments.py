"""R-H615（2026-09-25）· **恒真判据**必须为零（且豁免要带理由、可见）。

被测对象：`tools/codex-scripts/audit-dead-judgments.py`

由来（一手）：我改面板快照时把嵌数据写坏，而 `verify_v22.py` 报「49 通过」一声没吭。
查下去发现 `verify_v11..v21` 里共 **11 条**判据末尾写着 **`or True`** ——
**从出生起就不可能红**。⇒ 立这条判据：仓库里不许再有"看起来在判、其实恒真"的东西。

判据（四条，都要有牙）：
  1. **待处理必须为 0**（豁免另算，见第 3 条）；
  2. **本器自己得能咬** —— 喂一段"照旧写法"的假代码，必须报出来
     （否则"0 条"可能只是尺子瞎了）；
  3. **豁免必须带理由**，且**已知弱项要标出来**（照 `false_report_audit.KNOWN_LEGIT` 的先例：
     豁免可见、不许静默；已知弱项"不假装不存在"）；
  4. **覆盖面可见**：跳过哪些目录、有多少文件读不到，都要在报告里，
     不许把"没扫到"读成"扫过了没问题"。
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "codex-scripts" / "audit-dead-judgments.py"


def _load():
    spec = importlib.util.spec_from_file_location("audit_dead_judgments", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AUD = _load()


class NoLiveDeadJudgmentsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rep = __import__("json").loads(
            __import__("subprocess").run(
                [__import__("sys").executable, str(TOOL), "--json"],
                cwd=str(ROOT), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=600).stdout)

    def test_no_pending_dead_judgments(self) -> None:
        self.assertEqual([], self.rep["hits"],
                         "还有'不可能红'的判据：%s" % self.rep["hits"])

    def test_scan_actually_covered_files(self) -> None:
        self.assertGreater(self.rep["files"], 500,
                           "只扫了 %d 个文件 ⇒ 判据在空转" % self.rep["files"])

    def test_skips_and_unreadable_are_visible(self) -> None:
        self.assertTrue(self.rep["skipped_dirs"], "跳过名单是空的 ⇒ 覆盖面不可核")
        self.assertIn("store", self.rep["skipped_dirs"], "运行态目录应当被排除且可见")
        self.assertIsInstance(self.rep["unreadable"], list)

    def test_every_exemption_has_a_reason(self) -> None:
        self.assertTrue(self.rep["exempt"], "豁免表空了 ⇒ 那 5 条不该凭空消失")
        for e in self.rep["exempt"]:
            self.assertTrue(str(e.get("why") or "").strip(),
                            "豁免 %s:%s 没有理由" % (e["file"], e["line"]))

    def test_known_weakness_counter_matches_the_table(self) -> None:
        """`known_open_count` 必须与豁免表里标了『已知弱项』的条数**逐条对上**。

        ⚠️ 第一版这条写的是 `>= 2`（当时真有两条未修弱项）。那两条 2026-09-25 修完之后，
        `>= 2` 就成了**假的**（逼着人保留两条弱项才绿）⇒ 改成**不变量**：
        计数器 == 表里标『已知弱项』的条数。这样"修掉弱项"与"新增弱项"两个方向都盯着。
        """
        n = len([e for e in self.rep["exempt"] if "已知弱项" in str(e.get("why") or "")])
        self.assertEqual(self.rep["known_open_count"], n,
                         "已知弱项计数（%s）与豁免表里标『已知弱项』的条数（%d）对不上 ⇒ "
                         "豁免会退化成'静默放过'" % (self.rep["known_open_count"], n))


class AuditorStillBitesTest(unittest.TestCase):
    """负对照：照旧写法喂进去，本器必须报出来。"""

    def _scan(self, src: str) -> list:
        d = Path(tempfile.mkdtemp(prefix="dead_judge_"))
        p = d / "probe.py"
        p.write_text(src, encoding="utf-8")
        hits, bad = AUD.scan_file(p)
        return hits

    def test_or_true_is_caught(self) -> None:
        hits = self._scan('chk("x", ("undefined" not in t) or True, "note")\n')
        self.assertTrue(any(h["rule"].startswith("A/") for h in hits), hits)

    def test_bare_true_condition_is_caught(self) -> None:
        hits = self._scan('chk("x", True, "note")\n')
        self.assertTrue(any(h["rule"].startswith("B/") for h in hits), hits)

    def test_legit_failure_recorder_is_not_caught(self) -> None:
        """`chk(name, False, why)` 是**记录失败**的惯用法，不在"恒真"之列。

        ⚠️ 本器目前会把它报出来（靠 KNOWN 豁免）—— 这条用例**钉住这个已知口径**：
           要么它在豁免表里，要么以后有人把规则改精细。**不许它悄悄变成"没报"。**
        """
        hits = self._scan('chk("包在不在", False, "没有 %s" % APP)\n')
        rules = [h["rule"] for h in hits]
        self.assertTrue(rules, "这条被判成'没问题'了 ⇒ 口径变了，得同步改豁免表")
        key = ("tools/codex-scripts/pack-receipt.py", 98, "B/判据是常量")
        self.assertIn(key, AUD.KNOWN, "豁免表里没有它 ⇒ 上面的说明是空话")


if __name__ == "__main__":
    unittest.main(verbosity=2)
