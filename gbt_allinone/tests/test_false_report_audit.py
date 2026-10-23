"""错报审计器（`gbt_allinone/tools/false_report_audit.py`）的判据（2026-09-22 第 46 轮立）。

═══ 为什么现在才立（实测到的窟窿）═══
这一轮之前，**整个套件里没有任何一条判据碰过这个审计器**：
`grep false_report_audit gbt_allinone/tests` 零命中，连它的 `--selftest` 都没人跑。
而我在会话里**反复引用它的读数**当证据（"命中 0 条 / 两把对照过 / 扫过 344 个 .py"）——
那些全是**我手动敲出来的**。⇒
**一个只靠人手动跑、读数却被当证据引用的仪器，就是错报的藏身处。**

═══ 顺带量出来的第二个窟窿（本文件的核心判据）═══
它的默认分母**只有包内**：345 个 .py；同一套排除目录下工作区有 716 个 ⇒
**371 个（51.8%）从来没被它看过**（最大一块 `tools/codex-scripts` 225 个，
我那批探针和审计工具自己就住在里面）。屏幕上却只打「扫过 345 个 .py（排除目录：…）」，
**不写范围** ⇒ 读者会把「命中 0 条」读成"整个工作区没有错报"。
（实测影响面：`--scope workspace` 会多出 17 条命中。）
⇒ 处置：**范围显式上屏** + 加 `--scope workspace` 开关；**默认值一个字没动**
（偷换默认值 = 偷换基线，读数就不可比了）。本文件把这四件事都钉住：
  ① 两把对照必须自动化地过（不再靠我手动敲）；
  ② 分母必须自洽：`包内 + 范围外 == 全工作区`；
  ③ 范围外那株**默认看不见、换口径就看见**（盲区真实存在，且可关）；
  ④ 范围和范围外件数必须**出现在屏幕和 json 里**（不许静默）。
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gbt_allinone.tools import false_report_audit as fra  # noqa: E402


def _plant_bad(path: Path) -> None:
    """种一株**已知会被抓到**的错报形态。

    ⚠️ 内容**必须在运行时取** `fra._samples()[0]`，不许把那段坏代码抄进本文件 ——
    抄进来的话，本文件自己就成了审计器分母里的一株样本，
    于是"用坏样本测审计器"这件事会反过来把审计器的读数搅浑。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(fra._samples()[0], encoding="utf-8")


class TestFalseReportAuditHasJudges(unittest.TestCase):
    """审计器本体：两把对照必须自动化地过。"""

    def test_two_controls_pass(self):
        """selftest 的返回值就是判决（0 = 正对照不漏 / 负对照不误伤 / 退役规则不开火）。

        实测：本判据立起来之前，这条结论**只存在于我手敲的一次输出里**。
        """
        self.assertEqual(fra.selftest(verbose=False), 0,
                         "错报审计器自己的两把对照没过 —— 审计器都不干净，读数不能引用")

    def test_retired_rules_really_stay_retired(self):
        """退役规则**必须真的不再开火**（退役不是改文档）。"""
        bad_hits = {f["rule"] for f in fra.audit_text(fra._samples()[0], "<bad_scanner.py>")}
        zombie = sorted(set(fra.RETIRED_RULES) & bad_hits)
        self.assertEqual(zombie, [], "已退役的规则又开火了：%s" % zombie)


class TestScopeIsHonest(unittest.TestCase):
    """范围口径：分母必须自报，且算术必须自洽。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="gbt_fra_scope_")
        self.tmp = Path(self._tmp.name)
        # 包内一株（默认口径**应该**看见）
        _plant_bad(self.tmp / "gbt_allinone" / "tools" / "deep_scanner.py")
        # 包外一株（默认口径**看不见**它 —— 这就是盲区）
        _plant_bad(self.tmp / "other" / "deep_scanner.py")

    def tearDown(self):
        self._tmp.cleanup()

    def test_denominator_adds_up(self):
        """不变量：`包内件数 + 范围外件数 == 全工作区件数`（两边都非空）。

        写成**不变量**而不是写死 345/371/716 ——
        写死的话，工作区一长新文件这条判据就变成错报源（第 35 轮 test_energy_pool 的教训）。
        """
        pkg = fra._targets(self.tmp, fra.SCOPE_PACKAGE)
        ws = fra._targets(self.tmp, fra.SCOPE_WORKSPACE)
        inv = fra.scope_inventory(self.tmp, fra.SCOPE_PACKAGE)
        self.assertTrue(pkg, "包内一个 .py 都没收集到 —— 判据自己的前置就没造出来")
        self.assertTrue(inv["outside"], "范围外一个 .py 都没有 —— 这条判据测不到盲区")
        self.assertEqual(len(pkg) + len(inv["outside"]), len(ws),
                         "范围口径的算术不自洽：包内 %d + 范围外 %d ≠ 全工作区 %d"
                         % (len(pkg), len(inv["outside"]), len(ws)))

    def test_out_of_scope_plant_is_invisible_by_default(self):
        """盲区判据（本文件的核心）：包外那株**默认看不见**、换 `--scope workspace` 就看见。

        这一条同时证明两件事：① 盲区**真实存在**（不是我推断的）；
        ② 盲区**可关**（开关真的接上了）。缺任何一半，这条判据都不算数。
        """
        pkg_rows = fra.audit(fra._targets(self.tmp, fra.SCOPE_PACKAGE), self.tmp)
        ws_rows = fra.audit(fra._targets(self.tmp, fra.SCOPE_WORKSPACE), self.tmp)
        pkg_files = {r["file"] for r in pkg_rows}
        ws_files = {r["file"] for r in ws_rows}

        # 正对照：包内那株必须被抓到（否则"看不见包外那株"可能只是审计器整体失灵）
        self.assertIn("gbt_allinone/tools/deep_scanner.py", pkg_files,
                      "包内种的错报没被抓到 ⇒ 审计器整体没开火，下面那条结论不成立")
        self.assertNotIn("other/deep_scanner.py", pkg_files,
                         "默认口径居然看见了包外文件 —— 那说明范围口径已经变了，"
                         "本判据的前提（有盲区）需要重新量")
        self.assertIn("other/deep_scanner.py", ws_files,
                      "--scope workspace 仍然看不见包外那株 ⇒ 开关是假的")

    def test_scope_inventory_names_where_the_blind_spot_is(self):
        """范围外不能只报个数，还要报**它们住哪**（否则没法判断该不该管）。"""
        inv = fra.scope_inventory(self.tmp, fra.SCOPE_PACKAGE)
        self.assertEqual(inv["outside_top"].get("other"), 1,
                         "范围外件的归属没报对：%s" % inv["outside_top"])

    def test_scope_appears_on_screen_and_in_json(self):
        """范围 + 范围外件数必须**出现在屏幕和 json 里**，不许静默。"""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = fra.main(["--root", str(self.tmp), "--scope", fra.SCOPE_PACKAGE])
        out = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("范围：gbt_allinone", out,
                      "屏幕上没写范围 ⇒ 读者会把『命中 N 条』读成全工作区的结论")
        self.assertIn("之外", out, "范围外还有文件却没上屏警告")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = fra.main(["--root", str(self.tmp), "--json"])
        self.assertEqual(rc, 0)
        rep = json.loads(buf.getvalue())
        self.assertEqual(rep["scope"], fra.SCOPE_PACKAGE,
                         "不带 --scope 时默认口径变了（默认值一改，历史基线就不可比了）")
        self.assertEqual(rep["out_of_scope"], 1, "json 里的范围外件数不对")
        self.assertIn(rep["scope"], " ".join(rep["scope_roots"]))
        self.assertIn("scope_note", rep)


class TestLegitRegistrationIsLineAnchored(unittest.TestCase):
    """登记机制本身（2026-09-23 第 48 轮立）。

    ═══ 为什么要有这一组 ═══
    `KNOWN_LEGIT` 的设计意图是「按**该行**的标记串匹配 ⇒ 那行被改掉，登记自动失效——
    **不做文件名免检**」。但那条意图对**一部分规则实现不了**：
    有些规则的 `detail` 是**固定文案**（FR-2 就是），既不含行号也不含那行代码。
    实测（`.scratch/legit_scope_audit.py`）：`quick_scan.py` 的一条 3 元组登记
    **一条免掉了 2 处**（`[555, 677]`）⇒ 退化成**整文件免检**：
    以后该文件任何一行再冒出 FR-2 形状，都会被**静默放过**。
    —— 一个为了消假阳性而开的门，**顺手把真阳性也放走了**。

    ⇒ 修法：键允许带第 4 个元素（行号）。**下面两条判据把语义钉死**。
      真实仓上的效果另由 `.scratch/mutate_fra_judges.py` **变异验证**
      （在 `quick_scan.py` 别处种一条 FR-2，确认它**仍然报红**）。
    """

    @staticmethod
    def _row(rule, f, line, detail):
        return {"rule": rule, "file": f, "line": line, "detail": detail,
                "what": "", "evidence": ""}

    def test_line_anchored_entry_only_exempts_its_own_line(self):
        """带行号的登记：**只免那一行**，同文件同规则的别处**照样报出来**。

        这条判据就是"门不许顺手放走真阳性"的机器化版本。
        """
        f = "tools/codex-scripts/quick_scan.py"
        detail = "扫描器报 missing 却无 unknown 档（查不到 ≠ 不存在）"
        anchored = (("FR-2", f, "查不到 ≠ 不存在", 555), "理由")
        with mock.patch.dict(fra.KNOWN_LEGIT, {anchored[0]: anchored[1]}, clear=True):
            self.assertTrue(fra._is_known_legit(self._row("FR-2", f, 555, detail)),
                            "带行号的那一行**应该**被免")
            self.assertFalse(fra._is_known_legit(self._row("FR-2", f, 677, detail)),
                             "**别处**一行被一起免掉了 ⇒ 登记退化成整文件免检（第 48 轮修的病复发了）")
            self.assertFalse(fra._is_known_legit(self._row("FR-2", f, 9999, detail)))
            # 规则/文件/标记串任一不符，都不该免
            self.assertFalse(fra._is_known_legit(self._row("FR-5", f, 555, detail)))
            self.assertFalse(fra._is_known_legit(self._row("FR-2", "其他/别的.py", 555, detail)))
            self.assertFalse(fra._is_known_legit(self._row("FR-2", f, 555, "不相关的 detail")))

    def test_three_element_entry_still_works(self):
        """3 元素的旧登记**照旧生效**（向后兼容：既有 11 条不许因为这次改动失效）。

        ⚠️ 这里的 fixture **一律从真仓现取**，一个字符都不手抄。
        为什么（第 48 轮**实测**）：第一版我手写了那条 detail 字面量，于是
        **判据文件自己变成了审计的靶子** —— 本文件在包内口径里、被审计器扫到，
        那一行含有的「关键词判据」形态**当场被报成一条新的 FR-1 命中**（命中 0 → 1）。
        这正是本会话第 79 条：**我的记录动作，改变了我自己的测量结果**；
        而这是本轮**第三次**撞上它（前两次：把正则抄进 `quick_scan.py` 的注释；
        把「命中」和「豁免」两段版式做成一样，害自己读错）。
        ⇒ 规矩：**凡是要复刻某条规则命中形态的 fixture，只能运行时从真仓取，不许手抄。**
        """
        f = "gbt_allinone/truth_scan.py"
        entry = next(e for e in fra.KNOWN_LEGIT
                     if e[0] == "FR-1" and e[1] == f and len(e) == 3)
        txt = (fra.ROOT / f).read_text(encoding="utf-8")
        hits = [h for h in fra.audit_text(txt, f) if h["rule"] == "FR-1"]
        self.assertTrue(hits, "真仓里 %s 已无 FR-1 命中 ⇒ 3 元组兼容性这条判据没了靶子" % f)
        real_detail = hits[0]["detail"]
        with mock.patch.dict(fra.KNOWN_LEGIT, {entry: "既有 3 元组登记"}, clear=True):
            self.assertTrue(fra._is_known_legit(self._row("FR-1", f, hits[0]["line"], real_detail)))
            self.assertTrue(fra._is_known_legit(self._row("FR-1", f, 12345, real_detail)),
                            "3 元组本来就是『不看行号』，这里必须仍然不看")

    def test_every_line_anchored_entry_adds_something(self):
        """带行号的登记必须**真的钉住**：锚点行要对得上它免掉的那一行。

        这是防"我填了个错行号，登记看起来生效、其实靠标记串在免"——
        若填错行号，它一处也免不掉（`audit` 会把它当命中报出来），
        这条判据在**真仓**上复核这件事。
        """
        anchored = [e for e in fra.KNOWN_LEGIT if len(e) > 3]
        self.assertTrue(anchored, "一条带行号的登记都没有 ⇒ 这个机制没接上火（判据自己要先有靶子）")
        # ⚠️ 只审**带行号登记所指向的那几个文件**，不审整个工作区。
        #    第一版写了 `_targets(ROOT, SCOPE_WORKSPACE)` 全量审 —— 实测这一条判据 **19.5 秒**。
        #    重不是问题，"**由负载决定、不由对错决定**"才是问题（本会话第 1745 行的教训）：
        #    机器一忙，这条判据就可能超时变红，而红的成因跟它对不对**毫无关系**。
        #    改窄之后：靶子没变（那几行就在这几个文件里），耗时降到可以忽略。
        files = sorted({fra.ROOT / e[1] for e in anchored})
        missing = [str(p) for p in files if not p.is_file()]
        self.assertEqual(missing, [], "带行号的登记指向了**不存在的文件**：%s" % missing)
        fra.audit(files, fra.ROOT)                       # 填 LEGIT_EXCLUDED
        excluded = list(fra.LEGIT_EXCLUDED)
        for entry in anchored:
            rule, f, marker, line = entry[0], entry[1], entry[2], entry[3]
            mine = [x for x in excluded
                    if x["rule"] == rule and x["file"] == f
                    and marker in x.get("detail", "") and x.get("line") == line]
            self.assertTrue(mine,
                            "带行号的登记 %s %s L%d **一处都没免掉** ⇒ 行号填错了（它现在是死的）"
                            % (rule, f, line))


if __name__ == "__main__":
    unittest.main()
