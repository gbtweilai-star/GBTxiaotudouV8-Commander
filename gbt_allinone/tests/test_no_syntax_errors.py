"""包内**每一个** .py 都必须 `ast.parse` 得开（2026-09-23 第 48 轮立）。

═══ 为什么要有这一条（**实测的由来**）═══
第 48 轮跑审计时，命令**突然**从"命中 0 条"变成一大段 traceback，真因是
`gbt_allinone/caps_registry.py:963` 里有人写了

    "desc": "…补 `code_patch` 的另一半："改完要能看、要能回滚"）："

—— **双引号字符串里面又用了 ASCII 双引号**。`import gbt_allinone` 当场全断。
（那是**另一个会话**在写 `git_read` 能力时留下的，27 秒后它自己修好了；**不是我的**。）

那 27 秒里发生了什么，才是这一条判据的由来：
  · 包**根本 import 不进来** ⇒ 所有读数在那段时间里**全是废的**；
  · 而症状是 `pytest` 的 **82 条 collection error**（一堆 ImportError 回溯），
    **没有一句话指名道姓说"caps_registry.py:963 解不开"** ——
    读者要自己从 traceback 底部往回翻才看得到。
  · 更糟的一种情形是**它压根不会响**：包内文件里凡**不被 import** 的那些
    （`gbt_allinone/tools/*` · `deploy/*` …）写坏了，测试套件**根本碰不到它们**，
    于是"坏的照样绿"。

⇒ 所以这条判据做一件事：**把"解不开"变成一句带文件:行号的指名报告**，
  并且**覆盖包内全部 .py**（不只被 import 的那些）。

三条判据：① 真仓零解不开（**且分母不低于下限**，防"扫了个空所以全过"）；
②③ 正/负对照 —— 自己造一棵临时树，种一个坏文件**必须被抓到且指对行号**，
干净树**必须不误伤**。
"""
from __future__ import annotations

import ast
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from scan_scope import SKIP_DIRS  # noqa: E402

PKG = Path(__file__).resolve().parents[1]        # = gbt_allinone/
# 分母下限：今天（同一套 SKIP_DIRS 口径下）包内 351 个 .py。
# 写一个**下限**（不是精确值）—— 精确值会随代码增长天天变红（错报源，见第 35 轮教训）。
MIN_FILES = 200


def package_files(root: Path = PKG) -> list:
    """按**审计器同一套 `SKIP_DIRS`** 收集 .py（范围口径只留这一份实现）。

    ⚠️ 为什么不能直接 `rglob("*.py")`（第 48 轮**实测**踩到）：
      包内 `.pylibs/` 是**第三方 vendored**（pyautogui 等），`store/` 是**生产数据**。
      裸 rglob 数出 **3576** 个文件（真正的自有代码只有 351 个），
      而且会在 `store/pipeline/production/.versions/run.py` 上
      **PermissionError 直接崩掉判据**。
      ⇒ 那条红**不是"包里有坏文件"，是我自己的范围口径错了**。
      这与审计器 `--scope` 那次是同一个病：**分母不写清，读数就没意义。**
    """
    out = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            if f.endswith(".py"):
                out.append(Path(dp) / f)
    return sorted(out)


def parse_report(root: Path = PKG):
    """返回 `(解不开, 读不了)` —— 两份清单，**都不许沉默**。

    "读不了" 必须单独报：那是**未知**，不是"没问题"（"没有 X"比"有 X"更需要证据）。
    """
    bad, unreadable = [], []
    for p in package_files(root):
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            unreadable.append((str(p), type(e).__name__))
            continue
        try:
            ast.parse(txt, filename=str(p))
        except SyntaxError as e:
            try:
                rel = str(p.relative_to(root)).replace("\\", "/")
            except ValueError:
                rel = str(p)
            bad.append((rel, e.lineno, "%s: %s" % (type(e).__name__, e.msg)))
    return bad, unreadable


class TestEveryPackageModuleParses(unittest.TestCase):
    def test_no_module_in_the_package_fails_to_parse(self):
        """真仓：自有代码内**一个都不许**解不开；分母要够大；**读不了的必须报出来**。

        分母断言是必须的：若哪天范围口径被改坏（指向空目录/漏掉子树），
        `bad == []` 会**照样绿** —— 那就是"没扫"被读成"没问题"（第 43 轮的病）。
        """
        files = package_files(PKG)
        self.assertGreaterEqual(
            len(files), MIN_FILES,
            "包内只数到 %d 个 .py（下限 %d）⇒ 范围口径坏了，这条判据的『干净』不作数"
            % (len(files), MIN_FILES))
        bad, unreadable = parse_report(PKG)
        self.assertEqual(
            unreadable, [],
            "有 .py **读不了**（不是『没问题』，是**未知**）：\n  "
            + "\n  ".join("%s (%s)" % u for u in unreadable))
        self.assertEqual(
            bad, [],
            "包内有 .py **解不开**（`ast.parse` 失败）—— 这会让 import 全断、读数全废：\n  "
            + "\n  ".join("%s:%s  %s" % b for b in bad))

    def test_planted_syntax_error_is_caught_with_its_line(self):
        """正对照：自己造一棵树、种一个坏文件 ⇒ **必须被抓到、且指对行号**。

        为什么要有它：上面那条判据全绿有两种可能 —— ① 真的没有坏文件；
        ② **这套判定根本没接上火**。这条判据把"没接上火"这种可能排掉。
        """
        with tempfile.TemporaryDirectory(prefix="gbt_parse_") as d:
            root = Path(d)
            (root / "good.py").write_text("x = 1\n", encoding="utf-8")
            (root / "pkg").mkdir()
            # 种的就是第 48 轮那次真事：**双引号字符串里又用 ASCII 双引号**。
            (root / "pkg" / "bad.py").write_text(
                'y = 1\nz = 2\ns = "中文里面用 "ASCII 双引号" 就断了"\n', encoding="utf-8")
            bad, unreadable = parse_report(root)
        self.assertEqual(unreadable, [], "正对照树里不该有读不了的文件")
        self.assertEqual(len(bad), 1, "种了一个坏文件却得到：%s" % bad)
        rel, line, why = bad[0]
        self.assertEqual(rel, "pkg/bad.py", "抓到了但路径不对：%s" % rel)
        self.assertEqual(line, 3, "抓到了但行号不对（应为 3）：%s" % line)
        self.assertIn("SyntaxError", why)

    def test_clean_tree_is_not_flagged(self):
        """负对照：干净树**不许**误伤（否则这条判据自己就成了错报源）。"""
        with tempfile.TemporaryDirectory(prefix="gbt_parse_ok_") as d:
            root = Path(d)
            (root / "a.py").write_text(
                's = "里面用中文引号『这样』就没事"\n', encoding="utf-8")
            (root / "sub").mkdir()
            (root / "sub" / "b.py").write_text("def f():\n    return 1\n", encoding="utf-8")
            bad, unreadable = parse_report(root)
        self.assertEqual((bad, unreadable), ([], []))

    def test_scope_actually_excludes_vendored_and_store(self):
        """范围判据：`SKIP_DIRS` 真的把 `.pylibs` / `store` 排除掉了。

        没有这一条，上面那条"零解不开"就可能只是因为**范围被误收窄到几乎没东西**；
        而反过来若有人把 `.pylibs` 从 SKIP_DIRS 里拿掉，这条也会立刻变红提醒。
        """
        rels = [str(p.relative_to(PKG)).replace("\\", "/") for p in package_files(PKG)]
        for bad_dir in (".pylibs/", "store/", "__pycache__/"):
            leaked = [r for r in rels if r.startswith(bad_dir) or ("/" + bad_dir) in r]
            self.assertEqual(leaked[:3], [],
                             "范围漏了 %s（前几条：%s）" % (bad_dir, leaked[:3]))


if __name__ == "__main__":
    unittest.main()
