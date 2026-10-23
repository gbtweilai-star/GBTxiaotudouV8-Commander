"""`gbt_allinone/tools/scan_scope.py` 的 `tree_fingerprint()` 判据（2026-09-23 第 52 轮立）。

═══ 为什么需要"树指纹" ═══
第 51 轮的两份回归读数**都被并发写入污染**了：
`file_operation.py` 08:52 落在模式① 窗口内、`caps_registry.py` 08:59 落在模式② 内 ——
而我是**事后按 mtime 考古**才发现的。**考古不是证明**：
  ① mtime 只能事后查，跑的时候不知道；
  ② 它证不了"内容"没变（同秒写两次看不出来）；
  ③ `regression_stamp` 只盖 `git head`，**并发会话的未提交改动它盖不到**。
⇒ 有了指纹，"绿"才能**自己证明**自己干净。

═══ 判据要钉住的三件事 ═══
① **同树同值 / 变则不同**（内容改、加文件、删文件都要能看出来）；
② **读不了的文件必须列出来**（读不了是"未知"，不是"没变"）；
③ **范围就是同一套 `SKIP_DIRS`** —— 指纹只会对"代码面"变化敏感，
   `store/` 里数据翻江倒海也**不该**动它；这条不钉住，"指纹没变"就会被读成
   "整个仓什么都没变"（**分母不清**，本会话第 84/86 条同源）。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(_TOOLS))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scan_scope as ss  # noqa: E402


def _mk(root: Path, name: str, text: str) -> Path:
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


class TestFingerprintDetectsChanges(unittest.TestCase):
    def test_same_tree_same_value(self):
        with tempfile.TemporaryDirectory(prefix="gbt_fp_") as d:
            d = Path(d)
            _mk(d, "a.py", "x = 1\n")
            _mk(d, "sub/b.py", "y = 2\n")
            f1 = ss.tree_fingerprint(d)
            f2 = ss.tree_fingerprint(d)
        self.assertEqual(f1["sha256"], f2["sha256"], "同一棵树两次算出不同的指纹 ⇒ 指纹不可用")
        self.assertEqual(f1["files"], 2)
        self.assertEqual(f1["unreadable"], [])

    def test_content_change_changes_the_value(self):
        with tempfile.TemporaryDirectory(prefix="gbt_fp_") as d:
            d = Path(d)
            p = _mk(d, "a.py", "x = 1\n")
            before = ss.tree_fingerprint(d)["sha256"]
            p.write_text("x = 2\n", encoding="utf-8")     # 只改内容，不改路径/个数
            after = ss.tree_fingerprint(d)["sha256"]
        self.assertNotEqual(before, after, "只改了一个字节，指纹却没变 ⇒ 它挡不住并发写入")

    def test_added_and_removed_files_change_the_value(self):
        with tempfile.TemporaryDirectory(prefix="gbt_fp_") as d:
            d = Path(d)
            _mk(d, "a.py", "x = 1\n")
            base = ss.tree_fingerprint(d)["sha256"]
            _mk(d, "b.py", "y = 2\n")
            with_added = ss.tree_fingerprint(d)["sha256"]
            (d / "b.py").unlink()
            after_removed = ss.tree_fingerprint(d)["sha256"]
        self.assertNotEqual(base, with_added, "加了一个文件没看出来")
        self.assertEqual(base, after_removed, "加了又删，应当回到原指纹")

    def test_suffix_filter_is_honoured(self):
        """只算指定后缀（默认是代码面）⇒ 改一个 `.md` 不该动指纹。"""
        with tempfile.TemporaryDirectory(prefix="gbt_fp_") as d:
            d = Path(d)
            _mk(d, "a.py", "x = 1\n")
            md = _mk(d, "notes.md", "# 一\n")
            before = ss.tree_fingerprint(d)["sha256"]
            md.write_text("# 二\n", encoding="utf-8")
            after = ss.tree_fingerprint(d)["sha256"]
        self.assertEqual(before, after, "默认后缀集里不该包含 .md（口径要写清）")


class TestFingerprintScopeAndHonesty(unittest.TestCase):
    def test_scope_is_the_shared_skip_dirs(self):
        """**范围不变量**：`store/` `.pylibs/` 里的改动**不该**动指纹。

        这条钉住"指纹没变"这句话的**分母** —— 它只对同一套 `SKIP_DIRS` 下的代码面成立。
        """
        with tempfile.TemporaryDirectory(prefix="gbt_fp_") as d:
            d = Path(d)
            _mk(d, "a.py", "x = 1\n")
            base = ss.tree_fingerprint(d)["sha256"]
            for skipped in ("store", ".pylibs", "__pycache__", "node_modules"):
                _mk(d, "%s/noise.py" % skipped, "noise = 1\n")
            after = ss.tree_fingerprint(d)["sha256"]
            self.assertEqual(base, after,
                             "被排除目录里的文件混进了指纹 ⇒ 『指纹没变』会被读成『整个仓没变』")
            self.assertIn("store", ss.SKIP_DIRS)
            self.assertIn(".pylibs", ss.SKIP_DIRS)

    def test_unreadable_files_are_listed_not_skipped_silently(self):
        """读不了的文件必须**列出来** —— 那是"未知"，不是"没变"。

        ⚠️ 第一版我的夹子写错了：我造了一个**名叫 `a.py` 的目录**想让 `read_bytes` 抛错 ——
        但 `os.walk` 把目录放进 `dirnames`，**它压根不会进文件清单** ⇒ 夹子无效、判据变红。
        （本轮第 4 次"新判据第一次红，红在我的夹子/取法"。）
        改成**确定性地打桩**：只让某个名字的 `read_bytes` 抛 `PermissionError`。
        """
        with tempfile.TemporaryDirectory(prefix="gbt_fp_") as d:
            d = Path(d)
            _mk(d, "ok.py", "x = 1\n")
            _mk(d, "locked.py", "y = 2\n")
            real = Path.read_bytes

            def fake(self):
                if self.name == "locked.py":
                    raise PermissionError(13, "denied by judge")
                return real(self)

            with mock.patch.object(Path, "read_bytes", fake):
                f = ss.tree_fingerprint(d)
        self.assertEqual(f["files"], 1, "可读的应当只有 ok.py")
        self.assertEqual([Path(p).name for p, _w in f["unreadable"]], ["locked.py"],
                         "读不了的没被列出来 ⇒ 指纹会在『有文件读不了』时照样报『没变化』")

    def test_real_repo_fingerprint_is_usable(self):
        """真仓上取一次：必须**有值、有分母、且无读不了的**（读不了要当场看见）。"""
        root = Path(__file__).resolve().parents[2]
        f = ss.tree_fingerprint(root)
        self.assertIsNotNone(f["sha256"], "真仓指纹取不到：%r" % f)
        self.assertGreaterEqual(f["files"], 200,
                                "只数到 %s 个文件 ⇒ 范围口径坏了，『指纹』不作数" % f["files"])
        self.assertEqual(f["unreadable"], [], "真仓里有读不了的代码文件：%s" % f["unreadable"][:3])


class TestDiffNamesTheCulprit(unittest.TestCase):
    """`diff_trees()`：**"不作收据"必须能指名是谁动的**（2026-09-23 第 53 轮立）。

    由来：指纹装好后连着两轮，模式② 都报「树在扫描中途被改了 ⇒ 不作收据」，
    可**它只说"变了"，不说"谁变的"** ⇒ 我还得回头查 mtime，**又绕回考古**。
    第 52 轮实测一轮里 4 个文件动过（我 1 个 + 并发会话 3 个），屏幕上却只有一句"变了"。
    """

    def test_added_removed_changed_are_all_named(self):
        with tempfile.TemporaryDirectory(prefix="gbt_diff_") as d:
            d = Path(d)
            _mk(d, "keep.py", "k = 1\n")
            _mk(d, "edit.py", "e = 1\n")
            _mk(d, "gone.py", "g = 1\n")
            before = ss.tree_fingerprint(d, with_rows=True)
            (d / "edit.py").write_text("e = 2\n", encoding="utf-8")
            (d / "gone.py").unlink()
            _mk(d, "fresh.py", "f = 1\n")
            after = ss.tree_fingerprint(d, with_rows=True)
            delta = ss.diff_trees(before, after)
        self.assertTrue(delta["available"])
        self.assertEqual(delta["changed"], ["edit.py"], "改动没被指名")
        self.assertEqual(delta["removed"], ["gone.py"], "删除没被指名")
        self.assertEqual(delta["added"], ["fresh.py"], "新增没被指名")
        self.assertNotIn("keep.py", delta["changed"] + delta["added"] + delta["removed"],
                         "没动过的文件被误报成动了")

    def test_no_change_gives_empty_diff(self):
        with tempfile.TemporaryDirectory(prefix="gbt_diff_") as d:
            d = Path(d)
            _mk(d, "a.py", "x = 1\n")
            f1 = ss.tree_fingerprint(d, with_rows=True)
            f2 = ss.tree_fingerprint(d, with_rows=True)
            delta = ss.diff_trees(f1, f2)
        self.assertEqual((delta["added"], delta["removed"], delta["changed"]), ([], [], []))

    def test_missing_rows_is_reported_not_faked(self):
        """缺明细时**必须说"说不出是谁动的"** —— 不许静默返回空差异（那等于"没动"）。

        这是本条最要紧的一句：**"没动"和"我不知道"是两件事**。
        """
        delta = ss.diff_trees({"sha256": "a"}, {"sha256": "b"})
        self.assertFalse(delta["available"], "缺明细却报成『可用的空差异』⇒ 会把未知说成没动")
        self.assertIn("说不出", delta["note"])
        self.assertEqual((delta["added"], delta["removed"], delta["changed"]), ([], [], []))

    def test_rows_are_not_in_the_compact_form(self):
        """`regression_stamp._compact()` 必须**剥掉逐文件明细**（印章不该被 951 行撑大），
        但也**不许把摘要一起剥掉**。"""
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from gbt_allinone.tools import regression_stamp as rs
        fp = {"sha256": "abc", "files": 3, "bytes": 9, "unreadable": [],
              "rows": [{"path": "a.py", "bytes": 1, "sha256": "z"}]}
        c = rs._compact(fp)
        self.assertNotIn("rows", c, "明细被写进印章了 ⇒ 每个印章文件都会胖 951 行")
        for k in ("sha256", "files", "bytes", "unreadable"):
            self.assertIn(k, c, "摘要字段 %s 被一起剥掉了" % k)


class TestSubdirScopeIsTheDependencyFace(unittest.TestCase):
    """`tree_fingerprint(subdir=...)`：**面外改动不该影响面内指纹**（2026-09-23 第 56 轮立）。

    由来（**实测**，`.scratch/measure_dep_face.py`）：真起一次 pytest 收集后 dump `sys.modules`
    ⇒ **依赖面 = 199 个文件，全部落在 `gbt_allinone/` 之内**；而近几轮"导致模式② 不作收据"
    的 13 个改动里 **只有 1 个在面内**（`gbt_allinone/api.py`），另外 **12 个在面外**
    （`holo_pet_w3/*` 与 `tools/codex-scripts/*`）。
    ⇒ 面外改动把**本来有效的读数**废掉了。这一刀就是把两者分开。
    """

    def _tree(self, d: Path):
        _mk(d, "pkg/a.py", "a = 1\n")
        _mk(d, "pkg/sub/b.py", "b = 1\n")
        _mk(d, "other/c.js", "// c\n")
        _mk(d, "other/deep/d.js", "// d\n")

    def test_outside_change_does_not_move_the_face(self):
        """**核心**：改面外文件 ⇒ 整仓指纹变、**面内指纹不变**（收据因此仍成立）。"""
        with tempfile.TemporaryDirectory(prefix="gbt_face_") as d:
            d = Path(d)
            self._tree(d)
            repo0 = ss.tree_fingerprint(d)
            face0 = ss.tree_fingerprint(d, subdir="pkg")
            (d / "other" / "c.js").write_text("// c2\n", encoding="utf-8")
            _mk(d, "other/fresh.js", "// fresh\n")
            repo1 = ss.tree_fingerprint(d)
            face1 = ss.tree_fingerprint(d, subdir="pkg")
        self.assertNotEqual(repo0["sha256"], repo1["sha256"], "面外改动整仓没看出来")
        self.assertEqual(face0["sha256"], face1["sha256"],
                         "**面外改动动了面内指纹** ⇒ 这一刀没切干净（它正是用来区分那 12/13 的）")
        self.assertEqual(face0["files"], 2, "面内只该有 pkg 下两个 .py：%s" % face0)
        self.assertEqual(repo0["files"], 4, "整仓该有 4 个代码文件：%s" % repo0)

    def test_inside_change_moves_the_face(self):
        """负对照：改**面内**文件 ⇒ 面内指纹**必须**变（否则这一刀把该管的也放过了）。"""
        with tempfile.TemporaryDirectory(prefix="gbt_face_") as d:
            d = Path(d)
            self._tree(d)
            face0 = ss.tree_fingerprint(d, subdir="pkg")
            (d / "pkg" / "sub" / "b.py").write_text("b = 2\n", encoding="utf-8")
            face1 = ss.tree_fingerprint(d, subdir="pkg")
            (d / "pkg" / "fresh.py").write_text("f = 1\n", encoding="utf-8")
            face2 = ss.tree_fingerprint(d, subdir="pkg")
            (d / "pkg" / "a.py").unlink()
            face3 = ss.tree_fingerprint(d, subdir="pkg")
        self.assertNotEqual(face0["sha256"], face1["sha256"], "面内改动没看出来")
        self.assertNotEqual(face1["sha256"], face2["sha256"], "面内新增没看出来")
        self.assertNotEqual(face2["sha256"], face3["sha256"], "面内删除没看出来")

    def test_subdir_is_recorded_in_the_result(self):
        with tempfile.TemporaryDirectory(prefix="gbt_face_") as d:
            d = Path(d)
            self._tree(d)
            face = ss.tree_fingerprint(d, subdir="pkg")
            whole = ss.tree_fingerprint(d)
        self.assertEqual(face["subdir"], "pkg")
        self.assertEqual(whole["subdir"], "", "整仓那一份不该带 subdir")


if __name__ == "__main__":
    unittest.main()
