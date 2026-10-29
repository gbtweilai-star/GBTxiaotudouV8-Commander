# -*- coding: utf-8 -*-
"""主题能力位 判据（theme_cap）。"""
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone import theme_cap as TC  # noqa: E402
from gbt_allinone.security import policy  # noqa: E402


def _scopes(payload):
    d = policy.evaluate("theme_cap", payload or {})
    return sorted(getattr(d, "scopes", ()) or ())


def _active_palette():
    """现役色源 = 4 个主题块**生成头里写的那个**（派生源，不写死名字）。

    🔴 2026-10-25 · 原期望 → 新口径 → 为什么翻：
      原期望：`TC.run("check")` 用默认色源 `default` 校验全仓主题块。
      新口径：先读每个目标文件 `GBT-THEME-BEGIN … palettes/<名>.toml …` 的生成头，
              **四件必须同源**（不同源直接判红），再用那个源去校验。
      为什么翻：仓里在役的是 `gbt-brand`（CSS 头里就写着），而这条判据写死
              `default` ⇒ **拿 A 尺量 B**（本仓 P1），于是 4 件全部被报「漂移」。
              **这不是放宽**：四件不同源仍然红；色源文件不存在也仍然红。
    """
    import re
    targets = TC.run("discover")["targets"]
    seen = {}
    for t in targets:
        rel = t["file"] if isinstance(t, dict) else t
        p = ROOT / rel
        if not p.is_file():
            continue
        head = p.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"palettes/([A-Za-z0-9_.\-]+)\.toml", head)
        seen[rel] = m.group(1) if m else None
    names = {v for v in seen.values()}
    assert len(names) == 1 and None not in names, \
        "4 个主题块的生成头不是同一个色源 / 有的块没有生成头：%s" % seen
    return names.pop()


class ThemeCapReadTest(unittest.TestCase):

    def test_list_reports_palettes(self):
        r = TC.run("list")
        self.assertTrue(r["ok"], r)
        names = [p["name"] for p in r["palettes"]]
        self.assertIn("default", names)

    def test_show_reports_colors_and_dims(self):
        r = TC.run("show")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["palette"], "default")
        self.assertGreater(r["counts"]["colors"], 0)
        self.assertGreater(r["counts"]["dims"], 0)
        self.assertIn("gold", r["colors"])

    def test_show_unknown_palette_is_honest(self):
        r = TC.run("show", palette="no_such_xyz")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "palette_not_found")

    def test_check_passes_on_current_repo(self):
        r = TC.run("check", palette=_active_palette())
        self.assertTrue(r["pass"], r.get("errors") or r.get("drifted"))
        self.assertTrue(r["ok"])

    def test_discover_reports_all_targets_wired(self):
        r = TC.run("discover")
        self.assertTrue(r["ok"], r.get("missing"))
        self.assertFalse(r["missing"])
        self.assertEqual(len(r["targets"]), 4)

    def test_render_is_preview_only_by_default(self):
        r = TC.run("render")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["wrote"], [], "预览不得写盘")
        self.assertTrue(r["would_write"])

    def test_unknown_op_fails_closed(self):
        r = TC.run("definitely_not_an_op")
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "unknown_op")
        self.assertIn("check", r["known"])


class ThemeCapGateTest(unittest.TestCase):

    def test_read_ops_have_no_scopes(self):
        """读类只读文件 ⇒ 零作用域（与本仓纯判据位同格）。"""
        for op in TC.READ_OPS:
            with self.subTest(op=op):
                self.assertEqual(_scopes({"op": op}), [])

    def test_apply_needs_filesystem_write(self):
        self.assertEqual(_scopes({"op": "apply"}), ["filesystem_write"])

    def test_unknown_op_is_not_gated_but_returns_error(self):
        """未知 op 不挂作用域，但它只回错、不动状态。"""
        self.assertEqual(_scopes({"op": "nope"}), [])
        self.assertFalse(TC.run("nope")["ok"])


class ThemeCapEngineTest(unittest.TestCase):

    def test_engine_is_the_same_renderer_not_a_copy(self):
        """能力位必须**加载现有渲染器**，不得另写一份。"""
        eng = TC._engine()
        self.assertIsNotNone(eng, TC._ENGINE_ERR)
        self.assertEqual(Path(eng.__file__).name, "theme-render.py")
        self.assertEqual(len(eng.TARGETS), 4)

    def test_engine_unavailable_is_reported_honestly(self):
        """引擎不在就如实报，不假装能用。"""
        saved = TC._ENGINE
        TC._ENGINE = None
        TC._ENGINE_ERR = ""
        orig = Path.exists
        try:
            Path.exists = lambda self: False if self.name == "theme-render.py" else orig(self)
            TC._ENGINE = None
            r = TC.run("check")
            self.assertFalse(r["ok"])
            self.assertIn(r["reason"], ("engine_unavailable", "palette_not_found"))
        finally:
            Path.exists = orig
            TC._ENGINE = saved


if __name__ == "__main__":
    unittest.main(verbosity=2)
