# -*- coding: utf-8 -*-
"""主题渲染器 判据（单一色源 ⇒ 界面主题块）。"""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location("theme_render", ROOT / "tools" / "theme-render.py")
TR = importlib.util.module_from_spec(spec)
spec.loader.exec_module(TR)


def _active_palette():
    """现役色源 = 各目标文件主题块**生成头里写的那个**（派生源，不写死名字）。

    🔴 2026-10-25 · 原期望 → 新口径 → 为什么翻：
      原期望：拿 `load_palette("default")` 去量全仓主题块有没有漂移。
      新口径：先从目标文件的生成头读出实际色源（`palettes/<名>.toml`），
              **所有目标必须同源**（不同源直接判红），再用那个源量漂移。
      为什么翻：仓里在役的是 `gbt-brand`（CSS 头写着），写死 `default` 等于
              **拿 A 尺量 B**（本仓 P1），于是 4 件全被误报漂移。**不是放宽**：
              不同源仍红、色源缺失仍红（load_palette 会回 None）。
    """
    import re
    seen = {}
    for rel in TR.TARGETS:
        p = ROOT / rel
        if not p.is_file():
            continue
        m = re.search(r"palettes/([A-Za-z0-9_.\-]+)\.toml",
                      p.read_text(encoding="utf-8", errors="replace"))
        seen[rel] = m.group(1) if m else None
    names = {v for v in seen.values()}
    assert len(names) == 1 and None not in names, \
        "目标文件的生成头不是同一个色源 / 有的没有生成头：%s" % seen
    return names.pop()


class RenderEngineTest(unittest.TestCase):

    def test_token_replaced_from_colors(self):
        out = TR.render_block("a{color:@@gold@@}", {"gold": "#F5B041"})
        self.assertEqual(out, "a{color:#F5B041}")

    def test_token_replaced_from_meta(self):
        out = TR.render_block("/* @@name@@ */", {}, {"name": "X"})
        self.assertEqual(out, "/* X */")

    def test_missing_token_raises_not_silent(self):
        """缺 token 必须报错（不许静默留空 = 不许假绿）。"""
        with self.assertRaises(KeyError):
            TR.render_block("a{color:@@nope@@}", {"gold": "#000"})

    def test_marker_line_with_note_still_matches(self):
        """标记行带中文说明也要能认出（实测踩过：旧正则要求 “BEGIN */” 紧挨）。"""
        text = "x{}\n/* GBT-THEME-BEGIN —— 说明文字 */\n:root{--a:@@gold@@;}\n/* GBT-THEME-END */\n"
        self.assertTrue(TR.has_block(text))
        got = TR.build_template(text, {"gold": "#111111"})
        self.assertIn("--a:#111111;", got)

    def test_build_template_keeps_text_outside_block(self):
        text = "KEEP1\n/* GBT-THEME-BEGIN */\n:root{--a:@@gold@@;}\n/* GBT-THEME-END */\nKEEP2\n"
        got = TR.build_template(text, {"gold": "#222222"})
        self.assertIn("KEEP1", got)
        self.assertIn("KEEP2", got)
        self.assertIn("#222222", got)
        self.assertNotIn("@@gold@@", got)

    def test_render_is_idempotent(self):
        text = "K\n/* GBT-THEME-BEGIN */\n:root{--a:@@gold@@;}\n/* GBT-THEME-END */\n"
        once = TR.build_template(text, {"gold": "#333333"})
        twice = TR.build_template(once, {"gold": "#333333"})
        self.assertEqual(once, twice, "重复渲染不得再变形")


class PaletteTest(unittest.TestCase):

    def test_default_palette_loads_with_expected_keys(self):
        name, meta, colors, _c, _d = TR.load_palette("default")
        self.assertEqual(name, "default")
        self.assertTrue(colors, "色源必须有色")
        for k in ("gold", "cyan", "violet", "ok", "warn", "fault", "off", "text", "dim"):
            with self.subTest(key=k):
                self.assertIn(k, colors)
        self.assertIn("name", meta or {})

    def test_unknown_palette_reports_none(self):
        name, meta, colors, _c, _d = TR.load_palette("no_such_palette_xyz")
        self.assertIsNone(name)
        self.assertIsNone(colors)

    def test_list_palettes_includes_default(self):
        names = [r["name"] for r in TR.list_palettes()]
        self.assertIn("default", names)


class RealTargetsTest(unittest.TestCase):
    """真目标：四个界面文件必须**都有标记块**，且与色源一致。"""

    def test_all_four_targets_have_blocks(self):
        _, meta, colors, _c, _d = TR.load_palette("default")
        s = TR.scan(colors, meta)
        got = {x["file"] for x in s["files"]}
        self.assertEqual(got, set(TR.TARGETS),
                         "缺块的：%s" % (set(TR.TARGETS) - got))
        self.assertFalse(s["errors"], s["errors"])

    def test_no_drift_between_palette_and_files(self):
        _, meta, colors, _c, _d = TR.load_palette(_active_palette())
        d = TR.drift(colors, meta)
        self.assertTrue(d["ok"], d["drifted"])

    def test_every_palette_entry_is_used_by_at_least_one_target(self):
        """色源里不该有“写了没人用”的死条目（色与尺寸各自算）。"""
        _, meta, _v, colors, dims = TR.load_palette("default")
        used = set()
        for rel in TR.TARGETS:
            used |= {t.lower() for t in TR.TOKEN.findall(TR._template_of(rel))}
        for label, group in (("颜色", colors), ("尺寸", dims)):
            with self.subTest(group=label):
                unused = sorted(set(group) - used)
                self.assertFalse(unused, "%s里的死条目（没目标引用）：%s" % (label, unused))


class OrphanGuardTest(unittest.TestCase):
    """漂移守卫：答案必须分三档（真悬空 / 靠兜底 / 运行时定义）。"""

    def test_true_orphan_is_an_error(self):
        r = TR.orphan_vars("a{color:var(--nope);}")
        self.assertFalse(r["ok"])
        self.assertIn("--nope", r["orphans"])

    def test_fallback_reference_is_not_an_error(self):
        r = TR.orphan_vars("a{color:var(--nope, red);}")
        self.assertTrue(r["ok"])
        self.assertIn("--nope", r["fallback_only"])

    def test_runtime_defined_is_not_an_error(self):
        r = TR.orphan_vars("a{transform:translate3d(0,0,var(--z));}")
        self.assertTrue(r["ok"])
        self.assertIn("--z", r["runtime"])

    def test_cross_file_visibility_counts_as_defined(self):
        r = TR.orphan_vars("a{color:var(--gbt-cyan);}", None, ":root{--gbt-cyan:#00E5FF;}")
        self.assertTrue(r["ok"], r)

    def test_same_line_multi_definition_is_found(self):
        """`--a: 1px;  --b: 2px;` 同行多个定义也要认出（实测踩过：旧正则只认行首）。"""
        r = TR.orphan_vars(":root{--mc-1: 4px;  --mc-2: 8px;}\na{pad:var(--mc-2);}")
        self.assertTrue(r["ok"], r)

    def test_theme_block_itself_is_exempt(self):
        text = ("/* GBT-THEME-BEGIN */\n:root{--a:#111;}\n/* GBT-THEME-END */\n"
                "b{color:var(--a);}")
        r = TR.orphan_vars(text, ":root{--a:@@gold@@;}")
        self.assertTrue(r["ok"], r)


class TemplateSourceTest(unittest.TestCase):
    """模板必须**独立成件**（不能拿 .bak 当真源）。"""

    def test_templates_dir_exists_and_holds_all_targets(self):
        for rel in TR.TARGETS:
            tpl = TR.TEMPLATES_DIR / (Path(rel).name + ".tpl")
            with self.subTest(rel=rel):
                self.assertTrue(tpl.exists(), "缺模板：%s" % tpl)

    def test_every_template_still_carries_tokens(self):
        """模板里必须还有 `@@token@@`；被渲染过的块不能当模板。"""
        for rel in TR.TARGETS:
            tmpl = TR._template_of(rel)
            with self.subTest(rel=rel):
                self.assertIn("@@", tmpl, "模板里没了 token：%s" % rel)

    def test_template_tokens_all_exist_in_palette(self):
        _, meta, colors, _c, _d = TR.load_palette("default")
        for rel in TR.TARGETS:
            for tok in set(TR.TOKEN.findall(TR._template_of(rel))):
                with self.subTest(rel=rel, token=tok):
                    self.assertTrue(tok.lower() in colors or tok.lower() in (meta or {}),
                                    "模板引用了色源里没有的 token：%s" % tok)


if __name__ == "__main__":
    unittest.main(verbosity=2)
