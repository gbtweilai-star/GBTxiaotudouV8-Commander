# -*- coding: utf-8 -*-
"""design_atlas 判据：**中文人话 → 英文手册**的桥 · 来源条目抽得到 · 负控 0 命中。

跑法：`py -3.14 -m unittest gbt_allinone.tests.test_design_atlas -v`
（只读，绝不跑上游任何脚本。）
"""
import sys
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from gbt_allinone.tools import design_atlas as DA   # noqa: E402


def setUpModule():
    """前置：本次 store 里没索引就先建（隔离 store 下是空的；用例序在前会假红）。"""
    st = DA.run("status")
    if st["src_present"] and not st["indexed"]:
        DA.run("build")


class TestDesignAtlas(unittest.TestCase):
    def test_build_extracts_recipes_and_sources(self):
        st = DA.run("status")
        self.assertTrue(st["ok"], st)
        if not st["src_present"]:
            self.skipTest("素材不在盘（`_upstream/goated-ui-skill` 未落位）⇒ 跳过，不假装跑过")
        if not st["indexed"]:
            self.assertTrue(DA.run("build")["ok"])
            st = DA.run("status")
        self.assertGreater(st["by_kind"].get("recipe", 0), 100, "recipe 抽得太少：%s" % st)
        self.assertGreater(st["by_kind"].get("source", 0), 20,
                           "来源条目抽得太少（实测：这一份是**表格**不是列表，首版 0 条）：%s" % st)
        self.assertGreaterEqual(st["files"], 10, st)

    def test_chinese_bridge_finds_the_right_section(self):
        """🔴 正控：中文口语 → 英文手册。三问的**头一条**必须落在对的主题上。"""
        cases = (("滚动驱动的文字动画", ("scroll", "text", "motion", "css")),
                 ("毛玻璃卡片背景", ("glass", "backdrop", "css", "background", "color")),
                 ("缓动曲线怎么选", ("easing", "motion", "transition", "gsap")))
        for q, want in cases:
            r = DA.run("find", q=q, limit=1)
            self.assertTrue(r["hits"] > 0, "「%s」没命中：%s" % (q, r))
            f = r["items"][0]["file"]
            self.assertTrue(any(w in f for w in want),
                            "「%s」头一条落在 %s（期望含 %s）" % (q, f, want))
            self.assertRegex(r["items"][0]["where"], r".*\.md#L\d+$",
                             "命中项必须给 `文件#L行号`：%s" % r["items"][0])

    def test_negative_control_zero_hits(self):
        """完全不含桥词的说法必须**0 命中**（不许硬塞候选）。"""
        r = DA.run("find", q="紫色独角兽的早餐", limit=3)
        self.assertEqual(r["hits"], 0, "不认识的说法不许硬塞：%s" % r["items"])

    def test_never_runs_upstream_scripts(self):
        """铁律机检：本件**不含任何执行面**（只读文本）。

        🔴 用 **AST** 判，不扫全文 —— 首版扫字符串，结果命中了**我自己 docstring 里的那句说明**
        （「一处 eval( 是文档示例」）⇒ 假红。**判据不许把散文当代码读**（本会话第 4 次同族）。
        """
        import ast
        tree = ast.parse(Path(DA.__file__).read_text(encoding="utf-8"))
        seen_imports, seen_calls = set(), set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                seen_imports |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                # 只查**绝对** import（`level>0` 是包内相对 import，那是我方自己的件，
                # 不是"引入外部执行面"）——首版把 `..semantic_route` 也算进来 ⇒ 假红。
                if not getattr(n, "level", 0):
                    seen_imports.add((n.module or "").split(".")[0])
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                seen_calls.add(n.func.id)
        # **依赖白名单**（多一个意外 import 就红）——比"黑名单里没有 subprocess"更严：
        # 黑名单只能挡住我想到的，白名单能挡住我没想到的。
        allowed = {"json", "math", "os", "re", "time", "pathlib", "__future__", "argparse"}
        self.assertTrue(seen_imports <= allowed,
                        "本件出现了白名单外的 import：%s" % sorted(seen_imports - allowed))
        for bad in ("eval", "exec", "compile", "__import__"):
            self.assertNotIn(bad, seen_calls, "出现执行原语：%s" % bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
