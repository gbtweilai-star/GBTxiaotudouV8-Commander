"""`gbt_allinone/tools/isolation_sweep.py` 的判据（2026-09-23 第 50 轮立）。

═══ 为什么这个工具最该先有判据 ═══
第 50 轮做了一次普查（`.scratch/judge_coverage_census.py`）：`gbt_allinone/tools/` 80 个工具，
**21 个一条判据都没有（26%）**，而其中最扎眼的就是**本文件判的这个** ——
`isolation_sweep` 是**模式②回归**（"两种都绿才叫绿"）的**执行者与读数来源**：
我每一轮报告的「隔离扫描：N 个文件、红的 = 0」**就是它给的**。

> **一个自己没人守的仪器，它的"0 红"没人在守。**
> 它靠 `_summary()`（**正则解析 pytest 的人类尾巴**）判红绿 ——
> 万一那条正则哪天不匹配了，它会返回 `None`；而"红"是按 `rc != 0` 判的（这条还挺稳），
> 但 `passed/failed` 这些数会显示成 `?`（第 47 轮真出现过 `passed=? failed=?`）。
> ⇒ 判据要把三件事钉住：**能读对 · 读不出时不许猜 · 真红的文件必须被报红**。

═══ 顺带修掉的一个真缺陷（下面第 5 条判据守它）═══
`selftest()` 原来把两个对照文件写进 **共享的** `gbt_allinone/tests/`（跑完再删）。
那几秒里任何并发的全量回归都会**收集到它们**，而 `_CTL_FAIL` **是故意要红的**
⇒ **等于给并发的人递一个假红**（红的成因跟他毫无关系）。
第 48 轮我正因为"不愿递假红"而拒绝往真包里种坏文件 —— 同一件事这里一直这么干着。
已改成写临时目录。⚠️ 注意：**"跑完没有残留"这条判据抓不住旧代码**（旧代码也会删干净），
所以第 5 条判据是**在调用现场监视路径**，而不是事后数残留。
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gbt_allinone.tools import isolation_sweep as iso  # noqa: E402

_REAL_TAIL = """
============================= test session starts =============================
collected 12 items

gbt_allinone\\tests\\test_demo.py ............                            [100%]

============================= 12 passed in 3.21s ==============================
"""

_FAIL_TAIL = """
=========================== short test summary info ===========================
FAILED gbt_allinone/tests/test_demo.py::T::test_x - AssertionError: 1 != 2
========================= 1 failed, 5 passed in 2.10s ========================
"""

_ERR_TAIL = """
ERROR gbt_allinone/tests/test_demo.py - RuntimeError: 拒绝在绑定【生产 store】的进程里跑测试
===================== no tests ran, 1 error in 0.94s ==========================
"""


class TestSummaryParser(unittest.TestCase):
    """`_summary()` 是**正则解析人类输出** —— 读数全靠它，必须钉住。"""

    def test_reads_a_real_pytest_tail(self):
        self.assertEqual(iso._summary(_REAL_TAIL),
                         {"passed": 12, "failed": 0, "skipped": 0})

    def test_failed_and_passed_are_both_read(self):
        s = iso._summary(_FAIL_TAIL)
        self.assertEqual(s["failed"], 1)
        self.assertEqual(s["passed"], 5)

    def test_collection_error_tail_yields_none_rather_than_fake_zeroes(self):
        """收集期崩溃的尾巴里**根本没有 passed/failed 计数** ⇒ `_summary` 必须返回 None。

        ⚠️ 这一条我第一版**写反了**（第 50 轮自伤）：我原本断言"error 要被算进 failed"。
        实测 `_summary(_ERR_TAIL)` 返回的是 `None` —— 而**那才是对的**：
        那条尾巴写的是 `no tests ran, 1 error`，**压根没有 "N passed"/"N failed"**，
        硬凑一个 `failed=1` 属于**替读者猜**。返回 None ⇒ 显示成 `passed=? failed=?`，
        即"我没读懂"，这是诚实的。
        ⇒ 真正要钉的不是"error 要变成数字"，而是**下面那条**：红绿判定走 `rc`，
        收集期崩了 `rc != 0` ⇒ **照样报红**。（`summary` 只是给人看的明细。）
        """
        self.assertIsNone(iso._summary(_ERR_TAIL),
                          "这种尾巴里没有用例计数，返回数字就是替读者猜")

    def test_a_collection_error_is_still_reported_red(self):
        """**这条才是关键**：收集期崩（import 不进）必须判红 —— 靠 `rc`，不靠 `summary`。"""
        with tempfile.TemporaryDirectory(prefix="gbt_iso_collect_") as d:
            p = Path(d) / "test_probe_collect_error.py"
            p.write_text("import definitely_not_a_real_module_xyz\n\n\ndef test_x():\n    pass\n",
                         encoding="utf-8")
            r = iso.run_one(p, timeout_s=180)
        self.assertNotEqual(r["rc"], 0,
                            "收集期崩了却没判红 ⇒ 『包断了』会显示成没有红（第 47/48 轮真事）")

    def test_garbage_yields_none_not_zero(self):
        """**读不出来时不许猜**：返回 None，而不是 {passed:0, failed:0}。

        返回 0/0 会把"我没读懂"伪装成"跑了 0 个用例、0 个失败"——
        这正是本会话一直在打的『沉默比崩溃更坏』。
        """
        for junk in ("", "Traceback (most recent call last):\n  boom", "随便一段中文"):
            self.assertIsNone(iso._summary(junk), "垃圾输入 %r 被读成了数字" % junk[:20])


class TestRunOneReallyDetects(unittest.TestCase):
    """**核心判据**：它必须真的分得出红绿（否则"0 红"是空话）。"""

    def _run(self, src: str):
        with tempfile.TemporaryDirectory(prefix="gbt_iso_judge_") as d:
            p = Path(d) / "test_probe.py"
            p.write_text(src, encoding="utf-8")
            return iso.run_one(p, timeout_s=180)

    @staticmethod
    def _cannot_tell(r: dict):
        """这个读数**算不算一次判定**？`None` = 算；否则返回"为什么不算"。

        🔴 规则要精确，不许含糊（2026-09-25 第 42 轮实测定）：
          · `rc=2` **且** tail 里出现 `during collection` / `Interrupted`
            **且** 没有可解析摘要 ⇒ **内层 pytest 一个测试都没跑**（它是在收集期去起什么
            东西时 `FileNotFoundError [WinError 2]`）⇒ 那是"**没测成**"，不是"测出来是红/绿"。
            本文件自己的口径就是「超时 ⇒ 本次无法判定」，这条与它同型。
          · 其余任何情况（包括 rc=2 但确实跑过测试）⇒ **算判定**，该红就红。

        为什么不能简单地"rc=2 就跳过"：那样会**把"扫描器收集不了合法文件"这种真缺陷也放走**。
        必须靠 tail 判断"它到底有没有开口"。
        """
        tail = str(r.get("tail") or "")
        if r.get("rc") == 2 and r.get("summary") is None and (
                "during collection" in tail or "Interrupted" in tail):
            return "内层 pytest 收集期就被打断（rc=2 · 一个测试都没跑）：%s" % tail.strip()[-160:]
        return None

    def _run_retrying_on_collection_error(self, src: str, want_rc: int):
        """跑一次；若 rc 是 **2（pytest 的『被打断 / 收集期出错』）** 就**重试一次**。

        🔴 2026-09-25 第 42 轮实测（**先证「不是我的改动」再决定怎么改**）：
          满仓横扫（机器被压着）时，`test_a_passing_file_is_reported_green` 红了，rc=**2**。
          子进程的 tail 逐字是：
            `collected 0 items / 1 error` + `ERROR ..\\.. - FileNotFoundError: [WinError 2] 系统找不到指定的文件`
            + `Interrupted: 1 error during collection` —— 也就是**内层 pytest 根本没跑起来**，
            它是在**收集期**去起某个东西时找不到可执行文件。
          **卸掉负载后连跑两次**：`rc=0 · summary={'passed':1,'failed':0}`（13.1s / 12.4s）。
          ⇒ 这条红是**负载决定**的，不是扫描器分不出红绿（本文件自己反复写：
             「**一个由负载决定的对错，就是错报**」）。
        ⇒ 修法与那条延迟判据同型：**重试一次，判据本身不动** ——
          真坏的扫描器两次都会给出同一个错码；只有"收集期被打断"这种环境抖动会被重试抹掉。
          重试后仍不是 `want_rc` ⇒ **照样红**，并把两次读数一并打出来。
        """
        first = self._run(src)
        if first.get("timeout") or first["rc"] == want_rc:
            return first, None
        if first["rc"] == 2:            # 2 = 收集期出错/被打断（不是"判出了红或绿"）
            second = self._run(src)
            return second, {"first_rc": first["rc"], "first_tail": str(first.get("tail"))[-200:]}
        return first, None

    def test_a_failing_file_is_reported_red(self):
        """**核心机制**：故意失败的文件必须被判红（`rc != 0`）。

        ⚠️ 这条判据我改过两版，两版都错在"多断言了一个由环境决定的东西"（第 52 轮实测）：
          第一版还断言 `summary["failed"] >= 1` —— 那要求**内层 pytest 产出一份可解析的摘要**。
          而本机现读是 `avail 1.06 GB / load 85% / 换页中`：**内存紧的时候内层 pytest
          可能压根产不出摘要**（`summary=None`），于是这条判据
          **因为机器忙而变红**，跟"它分不分得出红绿"毫无关系。
          实测证据：`.scratch/_stamp_20260923T093313-958100.txt` 里
          `AssertionError: 0 not greater than or equal to 1 : 判红了但 summary 里 failed 不是 >=1：None`
          —— **`rc` 明明已经判红了**。
        ⇒ 现在只钉**机制**（rc 分红绿），摘要只做**自洽性**检查：
          有摘要 ⇒ `failed>=1`；没摘要 ⇒ 那是工具**如实说"我没读懂"**（`_summary` 返回 None），
          **不构成失败**。**一个由负载决定的对错，就是错报。**
        """
        r, _retry = self._run_retrying_on_collection_error(
            "import unittest\n\n\nclass T(unittest.TestCase):\n"
            "    def test_bad(self):\n        self.assertEqual(1, 2)\n", want_rc=1)
        # 🔴 2026-09-25 修**假绿**：子进程超时返回的是 `rc=None`（`run_one` 的
        #    `TimeoutExpired` 分支），而 `None != 0` 是 **True** ⇒ 这条负控会
        #    **因为"超时"而变绿**，读起来却像"它真的分得出红绿"。实测确认过：
        #    `run_one(..., timeout_s=1)` → `{"rc": None, "timeout": True, "summary": None}`。
        #    本文件自己的判据就是"超时 ⇒ 说**本次无法判定**"（见
        #    `TestSelftestIsNotLoadDependent.test_timeout_says_cannot_tell_not_scanner_broken`）
        #    ⇒ 这里照同一条口径办：超时**跳过并说清**，不许算成判红成功。
        if r.get("timeout"):
            self.skipTest("本次无法判定：子进程 180s 超时（机器在忙）—— "
                          "这与『扫描器分不出红绿』是两件事")
        _ct = self._cannot_tell(r)
        if _ct:
            self.skipTest("本次无法判定：%s —— 它**一个测试都没跑**，"
                          "不构成『扫描器分不出红绿』的证据" % _ct)
        # 🔴 2026-09-25 第 42 轮改：原来是 `assertNotEqual(r["rc"], 0)` ——
        #    而 pytest 的 **rc=2 是「收集期出错/被打断」，不是「判出了红」**。
        #    实测过：负载压着时它会返回 2（内层 `FileNotFoundError`，一个测试都没跑），
        #    于是这条**负控会假绿** —— 读起来像"扫描器真分得出红绿"，
        #    其实扫描器**根本没开口**。⇒ 现在钉死 **rc == 1**（pytest 的"有测试失败"）。
        self.assertEqual(1, r["rc"],
                         "故意失败的文件应给出 rc=1（有测试失败）；拿到 %r ⇒ "
                         "要么它没判红，要么那压根不是判红（rc=2 = 收集期出错/被打断）" % r["rc"])
        s = r["summary"]
        if s is not None:                       # 有摘要就必须自洽；没摘要是"读不出"，不是错
            self.assertGreaterEqual(s.get("failed", 0), 1,
                                    "摘要说 failed=0，而 rc 判红了 ⇒ 两者对不上：%s" % s)

    def test_a_passing_file_is_reported_green(self):
        r, retry = self._run_retrying_on_collection_error(
            "import unittest\n\n\nclass T(unittest.TestCase):\n"
            "    def test_ok(self):\n        self.assertEqual(1, 1)\n", want_rc=0)
        # 🔴 2026-09-25 修**假红**（同一天在满仓横扫里实测到的唯一一条红）：
        #    超时返回 `rc=None` ⇒ `assertEqual(rc, 0)` 失败。而本文件反复写的教训是
        #    「**一个由负载决定的对错，就是错报**」⇒ 超时走"本次无法判定"，不算判绿失败。
        if r.get("timeout"):
            self.skipTest("本次无法判定：子进程 180s 超时（机器在忙）—— "
                          "满仓横扫时实测 117s vs 单跑 62s，是负载不是回归")
        _ct = self._cannot_tell(r)
        if _ct:
            self.skipTest("本次无法判定：%s —— 内层一个测试都没跑成，"
                          "不是『通过的文件被误判』" % _ct)
        self.assertEqual(r["rc"], 0,
                         "通过的文件被误判；rc=%r%s" % (
                             r["rc"],
                             ("（注意：这是**重试之后**的读数 —— 第一次 rc=%s，收集期出错），tail=%s"
                              % (retry["first_rc"], retry["first_tail"])) if retry else ""))
        # 摘要只做**自洽性**检查：读不出（`None`）是工具如实说"我没读懂"，不构成失败
        # （与上面那条负控同一口径 —— 原来这里 `.get("failed", 1)` 会把 None 读成 1 ⇒ 假红）。
        s = r["summary"]
        if s is not None:
            self.assertEqual(s.get("failed", 0), 0,
                             "摘要说 failed>0，而 rc 判绿 ⇒ 两者对不上：%s" % s)


class TestSelftestDoesNotPolluteTheSharedTree(unittest.TestCase):
    """`selftest()` 的对照文件**不许落在共享测试树里**（第 50 轮修的那件事）。"""

    def test_control_files_are_not_created_inside_the_tests_dir(self):
        """**在调用现场监视路径**，而不是事后数残留。

        ⚠️ 为什么不能用"跑完看有没有残留"：旧代码也会在 `finally` 里删干净，
        所以事后检查**对旧代码照样绿** —— 那样这条判据就是空的。
        这里把 `iso.TESTS` 换成一个临时目录，并用 spy 记下每次 `run_one` 拿到的路径：
        只要**有对照文件落在那个（被替换成共享树的）目录里**，就是旧病复发。
        """
        seen = []

        def spy(path, timeout_s=300):
            """替身要**分得出红绿**（否则 selftest 自己的判决会挂）。

            ⚠️ 第一版我无脑返回「rc=0, failed=0」⇒ 必红那把对照没被判红 ⇒
            `selftest()` 返回 1 ⇒ 这条判据**因为我的替身太笨而变红**（第 50 轮自伤第 2 处）。
            """
            p = Path(path)
            seen.append(p)
            failing = "fail" in p.name
            return {"file": p.name, "rc": 1 if failing else 0, "ms": 0,
                    "summary": {"passed": 0 if failing else 1,
                                "failed": 1 if failing else 0, "skipped": 0},
                    "tail": "", "timeout": False}

        with tempfile.TemporaryDirectory(prefix="gbt_iso_shared_") as shared:
            shared_p = Path(shared)
            buf = io.StringIO()
            with mock.patch.object(iso, "TESTS", shared_p), \
                    mock.patch.object(iso, "run_one", spy), \
                    contextlib.redirect_stdout(buf):
                rc = iso.selftest()
        self.assertEqual(rc, 0, "两把对照没过：%s" % buf.getvalue()[-300:])
        self.assertEqual(len(seen), 2, "两把对照应当各跑一次，实得 %d 次" % len(seen))
        inside = [str(p) for p in seen if str(p).startswith(str(shared_p))]
        self.assertEqual(inside, [],
                         "对照文件又写进共享测试树了（正在给别人递假红）：%s" % inside)

    def test_selftest_leaves_no_residue(self):
        """补一条事后检查：真跑一遍 `--selftest`，`gbt_allinone/tests` 里不许留对照文件。

        ⚠️ 2026-09-26 第 50 轮：判"跑不成"要**看它说的话**，不要看退出码。
        本函数的退出码契约是「跑不成/判不出都返回 1」（见 `selftest()` 里那段自纠）——
        想靠"退出码 2"区分是我发明的、已被本文件另一条用例抓掉。
        ⇒ 这里改为：`rc != 0` **且**输出里出现「本次无法判定」⇒ 跳过并说清（环境所致）；
        其余非零 ⇒ 照样红。**一个由负载决定的对错，就是错报。**
        """
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = iso.selftest()
        out = buf.getvalue()
        if rc != 0 and "本次无法判定" in out:
            self.skipTest("本次无法判定（环境所致，不是扫描器坏了）：%s" % out[-220:])
        self.assertEqual(rc, 0, out[-300:])
        left = sorted(p.name for p in iso.TESTS.glob("test_zz_sweep_ctl_*.py"))
        self.assertEqual(left, [], "共享测试树里有对照残留：%s" % left)


class TestVacuousSweepIsNotGreen(unittest.TestCase):
    """**"没扫"不许被读成"干净"**（2026-09-23 第 52 轮立）。

    由来：加树指纹时当场撞到 —— `--only test_scan_scope`（**没有这个测试文件**）⇒
    屏幕打「扫过 0 个测试文件；红的 = 0」且**退出码 0**。一次**空绿**。
    而 `--only` 拼错是最容易发生的事（第 43 轮同款：审计器"一个文件都没扫到"）。
    """

    def test_only_matching_nothing_is_vacuous_not_clean(self):
        r = iso.sweep(only="__绝对不存在的测试名__", verbose=False)
        self.assertEqual(r["files"], 0)
        self.assertTrue(r["vacuous"], "空集没被标成 vacuous ⇒ 会被读成『干净』")
        self.assertFalse(r["ok"], "空集判成了 ok=True ⇒ 空绿")
        self.assertEqual(r["failed_files"], [], "空集本来就没有失败文件，这条只是确认语义")

    def test_a_normal_filtered_sweep_is_not_vacuous(self):
        """负对照：**真扫到了**文件时，`vacuous` 必须是 False（否则这条判据没区分力）。

        ⚠️ 这里**只断言这条判据自己的题目**（扫到了没有），**不断言 `r["ok"]`**。
        第一版我顺手断言了 `r["ok"]` —— 那等于把本判据的绿**挂在另一个测试文件的健康上**：
        `test_no_syntax_errors.py` 一旦红（或被并发改动波及），**这条判据就跟着红**，
        而红的成因跟"vacuous 有没有被标对"**毫无关系**。
        ⇒ 一个由**别的文件**决定的对错，就是错报。
        （"绿文件报绿"这件事由 `test_a_passing_file_is_reported_green` 用一个
          **判据自己造的**临时文件来管，不借别人的健康。）
        """
        r = iso.sweep(only="test_no_syntax", verbose=False)
        self.assertGreaterEqual(r["files"], 1, "过滤器一个文件都没匹配上 ⇒ 负对照的前提没造出来")
        self.assertFalse(r["vacuous"])
        self.assertIn(r["ok"], (True, False))       # 只确认它是布尔，不把它当判据


class TestSweepCarriesATreeFingerprint(unittest.TestCase):
    """扫描必须自己带"树有没有被改"的读数（第 52 轮加）。"""

    def test_sweep_reports_tree_before_and_after(self):
        """断言的是**机制的内部一致性**，不是"树一定没被改"。

        ⚠️ 第一版我断言 `tree_changed is False` —— **那是个由环境决定的对错**：
        它要求"这 5 秒里**没有任何人**动过仓"，而这是个**多人/多会话共用**的工作区
        （变异验证时它就真的红过：`before=6e2dd0d5b5b0 after=84e0f32e54bd`）。
        **一个由负载/并发决定、不由对错决定的红，就是错报**（第 1745 行那条教训）。
        ⇒ 改成**不变量**：`tree_changed` 必须**恰好等于**「两次指纹不相等」。
          树真被改了 ⇒ 字段为 True（读数照实），判据**照样绿** —— 因为它判的是"读数自洽"。
        """
        r = iso.sweep(only="test_no_syntax", verbose=False)
        for k in ("tree_before", "tree_after", "tree_changed"):
            self.assertIn(k, r, "缺字段 %s ⇒ 这份读数无法自证干净" % k)
        b = r["tree_before"].get("sha256")
        a = r["tree_after"].get("sha256")
        self.assertIsNotNone(b, "扫前指纹取不到：%r" % r["tree_before"])
        self.assertIsNotNone(a, "扫后指纹取不到：%r" % r["tree_after"])
        self.assertEqual(r["tree_changed"], (b != a),
                         "`tree_changed` 与两次指纹是否相等**对不上** ⇒ 这个字段在说谎"
                         "（before=%s after=%s changed=%s）"
                         % (str(b)[:12], str(a)[:12], r["tree_changed"]))
        self.assertGreaterEqual(r["tree_before"].get("files") or 0, 200,
                                "指纹的分母太小 ⇒ 它没覆盖到代码面，『没变』不作数")


class TestSelftestIsNotLoadDependent(unittest.TestCase):
    """自检**不许"由负载决定对错"**（2026-09-23 第 54 轮立）。

    由来：四臂变异里 C/D 两条红的判据不是预期的那些，我记了"归因不纯、下轮查"。
    本轮查清了：`green`/`red` 原来**都拿 `summary` 当准绳**，而 `summary` 来自
    `_summary()`——**正则解析内层 pytest 的人类尾巴**。机器换页时内层跑崩，
    尾巴里没有 "N passed"/"N failed"，`_summary` **如实返回 None** ⇒
      green = (rc==0 and {}.get("failed",1)==0) → 1==0 → **False**
      red   = (rc!=0 and {}.get("failed",0)>=1) → 0>=1 → **False**
    ⇒ 自检打印「✗ 判红：扫描器分不出红绿」——**而扫描器其实分得出**（`rc` 一直是对的）。
    纯逻辑证据：`.scratch/prove_selftest_load_dependence.py`（不需要真的制造内存压力）。

    ⇒ 修法：`rc` 是**权威信号**；`summary` 只做**自洽性**检查。下面的判据就是钉这一条。
    """

    @staticmethod
    def _spy(rc_pass, rc_fail, summary_pass, summary_fail, timeout=False):
        def spy(path, timeout_s=300):
            failing = "fail" in Path(path).name
            return {"file": Path(path).name,
                    "rc": rc_fail if failing else rc_pass,
                    "ms": 0,
                    "summary": summary_fail if failing else summary_pass,
                    "tail": "", "timeout": timeout}
        return spy

    def _selftest_with(self, spy):
        buf = io.StringIO()
        with mock.patch.object(iso, "run_one", spy), contextlib.redirect_stdout(buf):
            rc = iso.selftest()
        return rc, buf.getvalue()

    def test_unreadable_summaries_do_not_false_alarm(self):
        """**核心**：摘要读不出（`summary=None`）时，只要 `rc` 是对的，自检**不许**判红。

        旧公式在这条路上返回 1 并打印「扫描器分不出红绿」——那是错报。
        """
        rc, out = self._selftest_with(self._spy(0, 1, None, None))
        self.assertEqual(rc, 0,
                         "`rc` 明明分得出红绿（0 / 1），自检却判红 ⇒ 它拿 summary 当了准绳：\n%s"
                         % out[-400:])
        self.assertIn("不是", out, "没把『没读懂输出』与『分不出红绿』区分开：\n%s" % out[-400:])

    def test_wrong_rc_still_fails(self):
        """负对照：`rc` 真的不对时，自检**必须**判红（否则这条判据只会往一个方向咬）。"""
        rc, out = self._selftest_with(self._spy(1, 1, {"passed": 0, "failed": 1}, {"passed": 0, "failed": 1}))
        self.assertEqual(rc, 1, "必过文件返回 rc=1（真的分不出红绿），自检却放过了")

    def test_timeout_says_cannot_tell_not_scanner_broken(self):
        """超时 ⇒ 说『本次无法判定』，**不许**说成『扫描器分不出红绿』（两件事）。"""
        rc, out = self._selftest_with(self._spy(0, 1, None, None, timeout=True))
        self.assertEqual(rc, 1, "对照跑超时应当判红（不知道就是不知道）")
        self.assertIn("无法判定", out, "超时被说成了『扫描器分不出红绿』：\n%s" % out[-400:])

    def test_summary_disagreeing_with_rc_is_caught(self):
        """有摘要时**必须自洽**：摘要说 failed=0 而必红文件的 rc 非 0 ⇒ 不许当成"过"。"""
        rc, out = self._selftest_with(self._spy(0, 1, {"passed": 1, "failed": 0},
                                                {"passed": 0, "failed": 0}))
        self.assertEqual(rc, 1, "摘要与 rc 对不上却放过了：\n%s" % out[-400:])


class TestSweepReportsTheDependencyFace(unittest.TestCase):
    """扫描必须把**依赖面**单独交出来（2026-09-23 第 56 轮加）。

    为什么：连续几轮模式② 的读数都被并发会话写 `holo_pet_w3/*.js` 判成"不作收据"，
    而那些文件**它根本不 import**。依赖面量准之后（实测 199 个文件全在包里），
    **收据看 `deps_changed`**，整仓的 `tree_changed` 只作披露。
    """

    def test_deps_fields_are_present_and_consistent(self):
        r = iso.sweep(only="test_no_syntax", verbose=False)
        for k in ("deps_subdir", "deps_before", "deps_after", "deps_changed", "deps_delta"):
            self.assertIn(k, r, "缺字段 %s ⇒ 收据的有效性无从判断" % k)
        self.assertEqual(r["deps_subdir"], iso.DEPS_SUBDIR)
        b = r["deps_before"].get("sha256")
        a = r["deps_after"].get("sha256")
        self.assertIsNotNone(b, "面内指纹取不到：%r" % r["deps_before"])
        self.assertIsNotNone(a, "面内指纹取不到：%r" % r["deps_after"])
        self.assertEqual(r["deps_changed"], (b != a),
                         "`deps_changed` 与两次面内指纹是否相等对不上 ⇒ 这个字段在说谎")

    def test_the_face_is_a_strict_subset_of_the_repo(self):
        """**不变量**：依赖面必须**严格小于**整仓代码面（否则"面外改动不影响读数"是空话）。

        写成不等式而不是写死数字 —— 写死会随代码增长变红（错报源）。
        """
        r = iso.sweep(only="test_no_syntax", verbose=False)
        face = r["deps_after"].get("files") or 0
        whole = r["tree_after"].get("files") or 0
        self.assertGreaterEqual(face, 200, "依赖面只数到 %s 个文件 ⇒ 口径坏了" % face)
        self.assertLess(face, whole,
                        "依赖面(%s) 不小于整仓(%s) ⇒ 『面外改动不影响读数』这句话没有意义" % (face, whole))


if __name__ == "__main__":
    unittest.main()
