"""`gbt_allinone/tools/regression_stamp.py` 的判据（2026-09-23 第 51 轮立）。

═══ 为什么这个工具该有判据 ═══
第 50 轮普查：`gbt_allinone/tools/` 80 个工具里 **21 个一条判据都没有**，
本文件判的这个是其中之一 —— 而它是 `AGENTS.md` 规定的**回归证据工具**：
「回归一律走四元组印章……**没有印章的结论不采信**」。
⇒ 它错了，等于**"证据"本身错了**。

═══ 这一轮量出来的两个真缺陷 ═══
① **护照里的"四元组"一直是残缺的**：`framework_gate.py:334` 从印章里取
   `("python","store","comparability","identity")`，而 `collect()` 写出来的顶层键里
   **根本没有 `python` 和 `comparability`** ⇒ 那个 `if k in data` **静默跳过**，
   护照只记到 **2/4**，一声不响。实测盘上 **52 个印章，四元组齐的 0 个（0%）**
   （`.scratch/stamp_four_tuple_probe.py`）。
② **机读令牌把"有未知"说成了"同口径"**：原来 `same = not diffs`，
   于是**明明有 N 项无法比对**，只要没有确凿差异就照样打 `comparability=same_scope`。
   人读那行括号里写了「未知项见上」，**但令牌把那句话丢了** ——
   下游只认 `same_scope`，会直接拿两次红集对比，而**有些轴根本没验过**。
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

_TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(_TOOLS))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gbt_allinone.tools import regression_stamp as rs  # noqa: E402

# 护照四元组（与 `framework_gate` 里那份**由下面第 8 条判据交叉核对**，不是我抄的）
PASSPORT_KEYS = ("python", "store", "comparability", "identity")


def _scope(**kw):
    base = {"interpreter": "3.12.10 cpython-312", "identity": "interactive|desktop|1",
            "deps": "ABCD", "git": "deadbeef", "store_mode": "fresh",
            "mem_bucket": "loose(>1.5GB)"}
    base.update(kw)
    return base


class TestCompareScope(unittest.TestCase):
    """`compare_scope()` 是"这次能不能跟旧基线比"的唯一判据 —— 三态必须分得清。"""

    def test_identical_scopes_have_no_diffs(self):
        d, u, x = rs.compare_scope(_scope(), _scope())
        self.assertEqual((d, u, x), ([], [], []))

    def test_differing_interpreter_is_a_diff(self):
        d, u, _x = rs.compare_scope(_scope(), _scope(interpreter="3.14.5 cpython-314"))
        self.assertEqual([k for k, _a, _b in d], ["interpreter"])

    def test_none_on_one_side_is_unknown_not_a_diff(self):
        """**最关键的反假红不变量**：旧基线没记这一项 ⇒ 记"未知"，**不是"不一致"**。

        把未知当差异会造出假红（源码注释里写着 2026-09-18 实测踩到）。
        """
        old = _scope()
        del old["store_mode"]
        d, u, _x = rs.compare_scope(old, _scope())
        self.assertEqual(d, [], "缺项被当成了差异 ⇒ 假红")
        self.assertEqual(u, ["store_mode"])

    def test_mem_bucket_difference_is_disclosed_never_a_diff(self):
        """内存档位**只披露、不判**（实测判据②③对内存不敏感）。

        写成不变量：无论怎么变，它都不许进 `diffs`（否则会把"实测不敏感"的变量
        变成假红来源），但**必须出现在 disclosed 里**（不许静默）。
        """
        d, u, x = rs.compare_scope(_scope(), _scope(mem_bucket="tight(<=0.5GB)"))
        self.assertEqual(d, [], "内存档位进了 diffs ⇒ 会变成假红来源")
        self.assertEqual(u, [])
        self.assertIn(("mem_bucket", "loose(>1.5GB)", "tight(<=0.5GB)"), x)


class TestComparabilityToken(unittest.TestCase):
    """机读令牌三态 —— 这是本轮修的第二件事的守门句。

    原来只有 `same = not diffs`：**有未验轴也报 `same_scope`**。
    人读那行括号里写了「未知项见上」，但**令牌把那句话丢了**，
    下游会直接拿两次红集对比，而有些轴根本没验过。
    """

    def test_diffs_mean_not_comparable(self):
        self.assertEqual(rs.comparability_token([("interpreter", "a", "b")], []), "not_comparable")

    def test_unknown_axes_are_never_reported_as_same_scope(self):
        """**核心**：有未知轴时，令牌**不许**是 `same_scope`。

        写成"不许等于某一个值"而不是"必须等于某一个值"，是为了给以后加第四态留余地；
        真正的不变量是：**`same_scope` 的含义必须是"全轴都验过了"**。
        """
        t = rs.comparability_token([], ["store_mode"])
        self.assertNotEqual(t, "same_scope",
                            "有 %d 项无法比对，令牌却说『同口径』⇒ 下游会拿两次红集直接对比"
                            % 1)
        self.assertEqual(t, "same_scope_unverified_axes")

    def test_clean_compare_is_same_scope(self):
        self.assertEqual(rs.comparability_token([], []), "same_scope")

    def test_diffs_win_over_unknown(self):
        """确凿差异优先于未知 —— 有差异就是不可比，别被未知稀释掉。"""
        self.assertEqual(rs.comparability_token([("git", "a", "b")], ["store_mode"]),
                         "not_comparable")


class TestScopeOf(unittest.TestCase):
    def test_store_mode_three_states(self):
        mk = lambda req: {"store": {"requested": req}}          # noqa: E731
        self.assertEqual(rs._scope_of(mk("/tmp/gbt_stamp_store_ab12/store"))["store_mode"], "fresh")
        self.assertEqual(rs._scope_of(mk(r"D:\some\store"))["store_mode"], "explicit")
        self.assertEqual(rs._scope_of(mk(""))["store_mode"], None)

    def test_mem_bucket_boundaries(self):
        for gb, want in ((0.5, "tight(<=0.5GB)"), (0.51, "mid(0.5-1.5GB)"),
                         (1.5, "mid(0.5-1.5GB)"), (1.51, "loose(>1.5GB)"), (None, None)):
            got = rs._scope_of({"memory": {"avail_gb": gb}})["mem_bucket"]
            self.assertEqual(got, want, "avail_gb=%s 分档成了 %s" % (gb, got))


def _gate_expected_keys() -> "list | None":
    """从 `framework_gate.py` 里把"四元组该有哪些键"读出来（AST，不抄文本）。

    支持两种写法（我第一版只认第一种，于是**判据自己报红**了 —— 那是对的，
    它没有静静放过，而是让我回来把取法修对）：
      ① 推导式直接迭代**元组字面量**：`{k: data.get(k) for k in ("a","b") if k in data}`
      ② 推导式迭代一个**名字**：`_want = ("a","b")` 之后 `for k in _want`
    """
    tree = ast.parse((_TOOLS / "framework_gate.py").read_text(encoding="utf-8"))
    # 先把"名字 → 字符串元组"的赋值收集起来（供写法 ② 用）
    named = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Tuple):
            names = [e.value for e in node.value.elts
                     if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            for t in node.targets:
                if isinstance(t, ast.Name) and names:
                    named[t.id] = names
    for node in ast.walk(tree):
        if not isinstance(node, ast.DictComp):
            continue
        for gen in node.generators:
            if isinstance(gen.iter, ast.Tuple):
                names = [e.value for e in gen.iter.elts
                         if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                if names:
                    return names
            if isinstance(gen.iter, ast.Name) and gen.iter.id in named:
                return named[gen.iter.id]
    return None


class TestStampCarriesTheFourTuple(unittest.TestCase):
    """印章文件里**必须真的有**护照四元组那四个键。"""

    def test_collect_has_every_passport_key(self):
        """这是本轮修的那件事的守门句：少一个键 ⇒ 护照就少记一元，而且**不报**。"""
        st = rs.collect(["regression_stamp", "stamp"])
        miss = [k for k in PASSPORT_KEYS if k not in st]
        self.assertEqual(miss, [], "印章缺护照四元组字段 %s ⇒ 护照会静默少记" % miss)
        self.assertIn("cpython-", str(st["python"]),
                      "python 字段形状不对（应当是人能读、能比对的『版本 tag』）：%r" % st.get("python"))

    def test_framework_gate_expects_exactly_these_keys(self):
        """**跨模块不变量**：`framework_gate` 期望的键 ⊆ `collect()` 产出的键。

        ⚠️ 为什么不把那份键表抄进本文件：抄下来的话，**两处会慢慢漂开**，
        而这次这个缺陷**恰恰就是"两处键表不一致"**。
        所以用 **AST 从 `framework_gate.py` 里把它读出来**，再与本文件的
        `PASSPORT_KEYS` 和 `collect()` 的实际产出**三方对齐**。
        """
        found = _gate_expected_keys()
        self.assertIsNotNone(
            found, "在 framework_gate.py 里没读出『四元组该有哪些键』—— "
                   "那段可能被改写了，请人工复核本判据的取法（**取不到就报红，不许静静放过**）")
        self.assertEqual(sorted(found), sorted(PASSPORT_KEYS),
                         "framework_gate 期望的键表变了：%s；本判据与 PASSPORT_KEYS 需要同步复核" % found)
        st = rs.collect(["x"])
        self.assertEqual([k for k in found if k not in st], [],
                         "framework_gate 期望 %s，而 collect() 只给了 %s ⇒ 护照会静默少记"
                         % (found, sorted(st)))


class TestStampProvesItsOwnCleanliness(unittest.TestCase):
    """印章要能**自己证明**这次读数干不干净，并在脏了的时候**指名是谁动的**。

    ⚠️ 这一组是为我自己第 53 轮那个 bug 立的：我把"跑前"那一份指纹**挪到了跑完那几行里**
    ⇒ 两次指纹都在孩子跑完之后取 ⇒ **任何改动都测不出来**，永远报"树没变"。
    实测当场撞到：让孩子建一个新 .py，读数照样是「树指纹未变 = True（962 个文件）」。
    **一个永远说"干净"的机制，比没有它更坏** —— 它会给人虚假的安心。
    """

    PROBE = "gbt_allinone/_probe_tree_diff.py"
    # 面外探针：落在包里 = 依赖面内；落在 holo_pet_w3 下 = **面外**（第 56 轮用它验那一刀）
    PROBE_OUT = "holo_pet_w3/_probe_face_outside.js"

    def _run_stamp(self, child_code: str):
        import subprocess
        py = "%d.%d" % sys.version_info[:2]
        p = subprocess.run(
            [sys.executable, "-m", "gbt_allinone.tools.regression_stamp", "run",
             "--expect-python", py, "--store", "fresh", "--", "python", "-c", child_code],
            cwd=str(Path(__file__).resolve().parents[2]),
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        return (p.stdout or "") + (p.stderr or "")

    def test_child_writing_code_makes_the_stamp_say_dirty_and_name_it(self):
        probe = Path(__file__).resolve().parents[2] / self.PROBE
        try:
            out = self._run_stamp(
                "open(r'%s','w',encoding='utf-8').write('x = 1\\n')" % self.PROBE)
        finally:
            probe.unlink(missing_ok=True)          # 判据自己造的东西，自己收干净
        self.assertNotIn("依赖面未变 = True", out,
                         "孩子明明**在包内**改了码，印章却说『依赖面未变』⇒ 『跑前』那一份取晚了"
                         "（这个 bug 我第 53 轮犯过一次）：\n%s" % out[-500:])
        self.assertIn("依赖面在跑的中途被改了", out, "没报『依赖面被改了』：\n%s" % out[-500:])
        self.assertIn(self.PROBE.replace("\\", "/").split("/")[-1], out,
                      "报了『被改了』却**没指名**是哪个文件 ⇒ 又要人肉考古：\n%s" % out[-500:])

    def test_a_noop_child_reports_the_receipt_valid(self):
        """负对照：孩子什么都不改 ⇒ 必须报『依赖面未变・收据成立』。"""
        out = self._run_stamp("pass")
        self.assertIn("依赖面未变 = True", out, "什么都没改却报了变了：\n%s" % out[-500:])
        self.assertIn("收据成立", out, "没明说收据成立 —— 读者只能自己从哈希推：\n%s" % out[-500:])

    def test_outside_change_keeps_the_receipt_valid(self):
        """**核心（第 56 轮）**：改**包外**文件 ⇒ **收据仍然成立**，但要如实列出面外改动。

        由来（实测）：真起一次 pytest 收集 dump `sys.modules` ⇒ 依赖面 199 个文件全在包里；
        而近几轮"导致不作收据"的 13 个改动里 **12 个在包外**（`holo_pet_w3/*` ·
        `tools/codex-scripts/*`）—— 它们把**本来有效的读数**废掉了。
        """
        probe = Path(__file__).resolve().parents[2] / self.PROBE_OUT
        try:
            out = self._run_stamp(
                "open(r'%s','w',encoding='utf-8').write('// p\\n')" % self.PROBE_OUT)
        finally:
            probe.unlink(missing_ok=True)
        self.assertIn("依赖面未变 = True", out,
                      "**包外**改动把依赖面判成变了 ⇒ 那一刀没切干净：\n%s" % out[-500:])
        self.assertIn("收据成立", out, "面外改动时没说收据成立：\n%s" % out[-500:])
        self.assertNotIn("依赖面在跑的中途被改了", out,
                         "面外改动被当成了『依赖面被改了』⇒ 又回到『面外废掉读数』的老毛病：\n%s"
                         % out[-500:])
        self.assertIn("面外", out, "面外改动**如实列出来**这件事没做：\n%s" % out[-500:])
        self.assertIn(Path(self.PROBE_OUT).name, out, "面外改动没指名：\n%s" % out[-500:])


if __name__ == "__main__":
    unittest.main()
