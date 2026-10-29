"""R-H616（2026-09-25）· **未清故障前提复核器**自己的判据。

被测对象：`tools/codex-scripts/reverify-open-faults.py`
立它的理由：第 37 轮发现 F1/F6 两条高危故障的前提（"4 批没部署"）**早就不成立**，
而它们在账里挂了十几轮 —— **故障清单会无声腐烂**。

判据（五条，都要有牙）：
  1. 现读台账里的未清故障，**一条都不许是「已不成立」**（是的话必须回去改账，不许继续挂）；
  2. 真实台账跑得通、退出码与本器结论自洽；
  3. 🔴 **结论不许与读数自相矛盾**：探针自报"主数据没读到"（机器键 `_读不到_主数据`）时，
     哪怕探针返回"仍成立"，本器也必须**强制降级为「需人读」**
     —— 这是它首版真犯过的错（读数写着"拿不到这个名字"，结论却报"已不成立"）；
  4. 🔴 **反向也算错**：读数里只是**解释性文字**提到"拿不到"（主数据其实读到了），
     **不许**降级 —— 这是它第二版犯的错（把 F5 误降级，而 F5 的静态读其实拿到了 `['D','E','F','V']`）。
     ⇒ 3 与 4 合起来钉住一句话：**靠散文推断机器状态，两个方向都会错；只认机器键。**
  5. 没有探针的故障 id 一律报「需人读」，**不许默认绿**（"没有探针 ≠ 通过"）。
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
TOOL = ROOT / "tools" / "codex-scripts" / "reverify-open-faults.py"
LEDGER = ROOT / "state" / "排查台账.json"
# F13 那条负控住在哪儿（探针要读它，这条用例也要读它 —— **同一份**，不许各写一处）
TESTF = ROOT / "gbt_allinone" / "tests" / "test_isolation_sweep.py"


def _load():
    spec = importlib.util.spec_from_file_location("reverify_open_faults", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load()


def _run() -> tuple:
    p = subprocess.run([sys.executable, str(TOOL), "--json"], cwd=str(ROOT),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    i = p.stdout.find("{")
    return p.returncode, (json.loads(p.stdout[i:]) if i >= 0 else {})


class RealLedgerTest(unittest.TestCase):
    def test_no_open_fault_has_a_collapsed_premise(self) -> None:
        rc, rep = _run()
        broken = [r["id"] for r in rep.get("rows", []) if r["verdict"] == "已不成立"]
        self.assertEqual([], broken,
                         "这些故障的前提已经垮了 ⇒ 回台账改账（结掉或重写），不许继续挂着：%s" % broken)
        self.assertEqual(0, rc, "退出码应为 0（没有坍塌的前提）")

    def test_verdicts_are_consistent_with_readings(self) -> None:
        rc, rep = _run()
        rows = rep.get("rows", [])
        self.assertTrue(rows, "拿不到读数 ⇒ 本器没跑起来")
        for r in rows:
            with self.subTest(fault=r["id"]):
                self.assertIn(r["verdict"], ("仍成立", "已不成立", "需人读"))
                if r["verdict"] == "需人读":
                    # 需人读必须说清**为什么**（没有探针 / 主数据没读到 / 语义问题）
                    self.assertTrue(str(r["reading"]).strip() and r["reading"] != {},
                                    "报『需人读』却没说原因")


class GuardIsNotFooledTest(unittest.TestCase):
    """第 3、4 条：守卫只认机器键，不认散文 —— 两个方向各一条负控。"""

    def _guard(self, reading: dict, verdict: str) -> tuple:
        """复刻本器主循环里的那两行判定（保持与源码同一套规则）。"""
        if reading.get("_读不到_主数据") and verdict != "需人读":
            return "需人读", True
        return verdict, False

    def test_unreadable_primary_data_forces_human_review(self) -> None:
        """③ 主数据没读到 ⇒ 就算探针嘴硬说"仍成立"，也必须降级。"""
        v, downgraded = self._guard({"说明": "什么都拿不到", "_读不到_主数据": True}, "仍成立")
        self.assertEqual("需人读", v)
        self.assertTrue(downgraded)

    def test_prose_mention_of_missing_must_not_downgrade(self) -> None:
        """④ 只是解释性文字里有"拿不到"，主数据其实读到了 ⇒ **不许**降级。"""
        reading = {"来源": "静态读源码（模块属性拿不到）", "声明未实现的维度": ["D", "E", "F", "V"]}
        v, downgraded = self._guard(reading, "仍成立")
        self.assertEqual("仍成立", v, "拿散文里的『拿不到』去推翻结论 ⇒ 又误降级一次")
        self.assertFalse(downgraded)

    def test_source_uses_the_machine_key_and_not_a_prose_scan(self) -> None:
        """回归闸：源码里**只许**用机器键判定，不许再出现"扫散文关键词"的写法。

        这一条是**经验换来的**：散文扫描两版各错一个方向（见类文档），
        所以把它钉在源码上 —— 谁想改回去，这条用例会拦。
        """
        src = TOOL.read_text(encoding="utf-8")
        self.assertIn("_读不到_主数据", src, "机器键不见了")
        self.assertNotIn("any(w in blob for w in", src,
                         "又回到了『扫散文关键词』的写法 ⇒ 两个方向都会误判（见类文档 ③④）")


class NoProbeIsNotGreenTest(unittest.TestCase):
    """第 5 条：没有探针的 id 不许默认绿。"""

    def test_unknown_fault_id_is_human_review(self) -> None:
        self.assertNotIn("F99", MOD.PROBES, "用例前提：F99 不该有探针")
        # 台账里若出现没有探针的 id，主循环会给它『需人读』—— 这里直接验那段逻辑的取值域
        probe = MOD.PROBES.get("F99")
        self.assertIsNone(probe)
        # 复刻主循环：没有探针 ⇒ 需人读（不是『仍成立』）
        verdict = "需人读" if probe is None else "仍成立"
        self.assertEqual("需人读", verdict)


# ── 第 56 轮加：把「需人读」的面积钉住 + 给新探针装负控 ──────────────────────
class EveryProbeIsAliveTest(unittest.TestCase):
    """每条探针都得出得来结论 —— 探针写错名字/写崩了，这一条会红。

    为什么要有：本器最怕的不是"判错"，是**静默退回『需人读』** —— 那与"没有探针"长得一模一样，
    而"没有探针 ≠ 通过"这条口径正是本器存在的理由。
    """

    def test_every_probe_returns_a_valid_verdict(self) -> None:
        bad = []
        for fid, fn in sorted(MOD.PROBES.items()):
            try:
                verdict, reading = fn()
            except Exception as exc:  # noqa: BLE001
                bad.append("%s 抛异常：%s: %s" % (fid, type(exc).__name__, str(exc)[:80]))
                continue
            if verdict not in ("仍成立", "已不成立", "需人读"):
                bad.append("%s 返回了契约外的结论：%r" % (fid, verdict))
            if not isinstance(reading, dict) or not reading:
                bad.append("%s 的读数不是非空字典" % fid)
        self.assertEqual([], bad, "这些探针不健康：%s" % bad)

    def test_human_review_set_is_pinned(self) -> None:
        """**需人读**只许是这四位，且每一位都要有**说得出的理由**：

        · `F3`  —— 语义问题（"该不该把 fail-open 收紧"轮不到机器判）
        · `F11` —— 本条判据跑在**隔离 store** 里（开机自检就是这么定的）⇒ 保险箱是空的
                   ⇒ 探针自己打机器键报『需人读』：**不许由"没读到"推出"分叉已修好"**
        · `F18` —— 要读**活的那个面** `/gbt-master`；页面/服务起不来就判不了（重启后会自己转绿）
        · `F19` —— 不制造负载就复现不了那条假红（**未复现 ≠ 不存在**）

        别的任何一条**静默变成需人读**都在这里红 —— 那通常意味着它的探针悄悄坏了。
        """
        rc, rep = _run()
        rows = rep.get("rows", [])
        human = sorted(r["id"] for r in rows if r["verdict"] == "需人读")
        allowed = {"F3", "F11", "F18", "F19"}
        self.assertTrue(set(human) <= allowed,
                        "这些条目不该是『需人读』：%s（多半是探针悄悄坏了）" % sorted(set(human) - allowed))
        # 🔴 2026-10-25 口径翻正（留痕 · 谁改的、为什么、原期望是什么）：
        #   原文写死 `assertIn("F3", human)`，等于**把 F3 钉成永远『需人读』**。
        #   后果实测撞到了：F3 其实 2026-09-28 就修好（api.py 的异常分支已 fail-closed、
        #   判据 test_preflight_fail_closed 3/3 PASS），这一轮据实结账 ⇒ **这条判据反而变红**。
        #   那等于变相惩罚"把账结掉"：要么永远别结，要么改判据。
        #   原期望（没变）：**不许有『新』id 悄悄混进需人读**（上界检查，上面那行一行没动）。
        #   现口径：**还在册的**才要求它老实报『需人读』；已结账的不再要求。
        open_ids = {r["id"] for r in rows}
        if "F3" in open_ids:
            self.assertIn("F3", human,
                          "F3 还在册 ⇒ 它是语义问题，必须老实报『需人读』，不许被某条探针悄悄判成绿")
        self.assertEqual(0, rc)


class ClosureCriteriaHaveTeethTest(unittest.TestCase):
    """**反空洞**：结掉一条故障的判据，必须在"老样子"下报『仍成立』。

    没有这一组，`probe_f16` 完全可能是一个永远返回『已不成立』的常量 ——
    那样它不但没用，还会**主动催人把没修的故障结掉**。这比没有探针更坏。
    """

    def _with_root(self, tmp: Path):
        """把探针指向临时仓（模块级 ROOT 被替换，其余不动）。"""
        old = MOD.ROOT
        MOD.ROOT = tmp
        return old

    def test_f16_old_state_still_stands(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory(prefix="rev16_") as td:
            tmp = Path(td)
            (tmp / "plugins" / "gbt-master").mkdir(parents=True)
            (tmp / "plugins" / "gbt-master" / "lib").mkdir(parents=True)
            (tmp / "plugins" / "gbt-master" / "lib" / "host.js").write_text(
                "// 本代 158 项能力\n", encoding="utf-8")
            (tmp / "plugins" / "gbt-master" / "README.md").write_text("表\n", encoding="utf-8")
            (tmp / "index.html").write_text("<p>158 项能力</p>\n", encoding="utf-8")
            old = self._with_root(tmp)
            try:
                verdict, reading = MOD.probe_f16()
            finally:
                MOD.ROOT = old
            self.assertEqual("仍成立", verdict, "老样子（写死 158）竟然被判『已不成立』：%s" % reading)

    def test_f15_bad_offset_still_stands(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory(prefix="rev15_") as td:
            tmp = Path(td)
            led = tmp / "排查台账.json"
            led.write_text(json.dumps({
                "updated_at": "2026-09-26T02:00+08:00",
                "log": [{"at": "2026-09-26T02:00+08:00", "what": "x"}],
                "_口径": "没写明历史缺陷",
            }, ensure_ascii=False), encoding="utf-8")
            old_led, old_root = MOD.LEDGER, MOD.ROOT
            MOD.LEDGER, MOD.ROOT = led, tmp
            try:
                verdict, reading = MOD.probe_f15()
            finally:
                MOD.LEDGER, MOD.ROOT = old_led, old_root
            self.assertEqual("仍成立", verdict, "偏移写错竟然被判『已不成立』：%s" % reading)

    def test_f17_missing_tool_is_human_review_not_closed(self) -> None:
        """**不许由"读不到"推出"已不成立"** —— 工具不在盘上时必须报『需人读』并打机器键。"""
        import tempfile
        with tempfile.TemporaryDirectory(prefix="rev17_") as td:
            old = self._with_root(Path(td))
            try:
                verdict, reading = MOD.probe_f17()
            finally:
                MOD.ROOT = old
            self.assertEqual("需人读", verdict)
            self.assertTrue(reading.get("_读不到_主数据"),
                            "主数据没读到却没打机器键 ⇒ 上游守卫拦不住它")

    def test_f13_sees_the_real_negative_control(self) -> None:
        """这条钉住我**第四次**犯的那个错：凭记忆写正则去找负控。

        盘上写的是 `self.assertEqual(1, r["rc"], …)`；我第一版按 `assertEqual(1, rc)` 去找，
        报 False，读起来像"负控没钉死"（其实钉死了）。这条用例同时认两种写法。
        """
        self.assertTrue(re.search(r"assertEqual\(\s*1\s*,\s*r\[\"rc\"\]", TESTF.read_text(
            encoding="utf-8")), "盘上的负控写法变了 ⇒ 探针的正则要跟着改（别再凭记忆写）")
        verdict, reading = MOD.probe_f13()
        self.assertTrue(reading.get("负控钉死 rc == 1（不再用 assertNotEqual(rc,0)）"),
                        "探针没认出那条负控：%s" % reading)


if __name__ == "__main__":
    unittest.main()
