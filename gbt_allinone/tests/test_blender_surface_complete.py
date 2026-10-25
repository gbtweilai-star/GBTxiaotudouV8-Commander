"""Blender 可控制面完整性判据（主人令 2026-09-27）。

主人原话：「把这些自动化触手连接**每一个可控制按键**的细节连接都做**双向绑定**确保**不会断连**，
`Blender 4.2.lnk` **所有可控制键都要绑定不能遗漏**。」

**判据（都可判定，不靠人眼）**：
  A. **清单在**：`state/blender_surface.json` 存在且能被 `blender verify` 判过
     （命名空间 ≥60 · 算子 ≥2000 · 数据族 ≥40 —— 阈值比实测 76/2409/49 留余量）；
  B. **不许断连**：清单里 `gone`（消失的键）必须为空 —— 升级后键没了要**报警或解释**，不许静默；
  C. **入口通**：`run_task("blender", {"op":"keys"})` 能过门返回摘要（说明四个新 op 已接线）；
  D. **只读面可用**：`data` op 能真读场景（factory 默认场景里 objects ≥ 1）。

红了怎么办：`run_task('blender', {'op':'surface'})` 重扫；若真有键消失 ⇒ 去 `state/blender_surface.json`
的 `gone` 里看是哪些，判断是 Blender 升级改名（解释掉）还是我们接线掉了（补）。
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "gbt_allinone" / "tools" / "blender_surface.py"
MANIFEST = ROOT / "state" / "blender_surface.json"


def _load():
    spec = importlib.util.spec_from_file_location("blender_surface_probe", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestBlenderSurfaceComplete(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load()

    def test_a_manifest_and_verify(self):
        """A. 清单在，且完整性判过（漏了就不算绑定）。"""
        self.assertTrue(TOOL.is_file(), f"工具不在位：{TOOL}")
        self.assertTrue(MANIFEST.is_file(), "没有可控面清单 ⇒ 跑 run_task('blender', {'op':'surface'})")
        v = self.m.verify()
        self.assertTrue(v["ok"], f"可控制面判据没过：{v['problems']}")

    def test_b_no_disconnected_keys(self):
        """B. 不许断连：消失的键必须为空（升级改名要解释，接线掉了要补）。"""
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        gone = man.get("gone") or []
        self.assertEqual([], gone, f"有 {len(gone)} 个可控制键消失（例：{gone[:5]}）⇒ "
                                   f"要么 Blender 升级改名（解释掉），要么我们接线掉了（补）")

    def test_c_entry_reachable(self):
        """C. 入口通：四个新 op 已接线（过唯一门能拿到摘要）。"""
        r = self.m.keys()
        self.assertTrue(r.get("ok"), f"keys 取不到：{r}")
        c = r.get("counts") or {}
        self.assertGreaterEqual(c.get("operators", 0), self.m.MIN_OPS,
                                f"算子数 {c.get('operators')} 低于阈值 {self.m.MIN_OPS}")

    def test_d_readonly_surface_works(self):
        """D. 只读面可用：真读一次场景（不是"登记了没接"）。"""
        d = self.m.data("objects")
        self.assertTrue(d.get("ok"), f"读场景失败：{str(d)[:200]}")
        self.assertGreaterEqual(d.get("count", -1), 1, "factory 默认场景应有对象（Camera/Cube/Light）")


if __name__ == "__main__":
    unittest.main(verbosity=2)
