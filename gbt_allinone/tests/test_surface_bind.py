"""可控制面完整性判据（主人令 2026-09-27）。

主人原话：「包括我们需要使用到的**其他工具全部都要可控按键全部一个不漏的绑定好**，
实现**想什么就能生产什么画面**的能力就可以了。」

**判据**：
  A. **每个装了工具都有清单**：`state/surfaces/<工具>.json` 在，键数 ≥ 该工具阈值（阈值来自实测）；
  B. **不许断连**：所有清单的 `gone`（消失的键）必须为空；
  C. **入口通**：`run_task("surface_bind", {"op":"keys"})` 能过门拿到总表；
  D. **Blender 不算例外**：它的 2409 个 bpy 算子走 `blender_surface` 清单，也必须齐（≥2000）。

红了的修法：`python -c "…run_task('surface_bind', {'op':'sweep'})"` 重扫；
真有键消失 ⇒ 看清单 `gone` 里是哪些，判断是工具升级改名（解释掉）还是我们接线掉了（补）。
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "gbt_allinone" / "tools" / "surface_bind.py"
DIR = ROOT / "state" / "surfaces"
BLENDER_MAN = ROOT / "state" / "blender_surface.json"


def _load():
    spec = importlib.util.spec_from_file_location("surface_bind_probe", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestSurfaceBindComplete(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load()

    def test_a_every_installed_tool_has_surface(self):
        """A. 装了工具就必须有可控制面清单，且键数过阈值（一个不漏）。"""
        self.assertTrue(TOOL.is_file(), f"绑定器不在位：{TOOL}")
        problems = []
        for tool, spec in self.m.TOOLS.items():
            p = BLENDER_MAN if tool == "blender" else (DIR / f"{tool}.json")
            if not p.is_file():
                # 没装的工具允许没有清单（不硬编），但要能说出"没装"
                if self.m._which(tool):
                    problems.append(f"{tool}: 装了但没清单")
                continue
            d = json.loads(p.read_text(encoding="utf-8"))
            n = (d.get("counts") or {}).get("operators" if tool == "blender" else "keys") or 0
            if n < spec["min_keys"]:
                problems.append(f"{tool}: 键 {n} < 阈值 {spec['min_keys']}（**有漏**）")
        self.assertEqual([], problems, f"可控制面不齐：{problems} ⇒ 跑 sweep 重扫")

    def test_b_no_disconnected_keys(self):
        """B. 不许断连：任何清单的消失键都必须为空。"""
        gone_all = {}
        for p in [BLENDER_MAN] + sorted(DIR.glob("*.json")):
            if not p.is_file():
                continue
            d = json.loads(p.read_text(encoding="utf-8"))
            if d.get("gone"):
                gone_all[d.get("tool") or p.name] = d["gone"][:3]
        self.assertEqual({}, gone_all, f"有工具的可控制键消失（断连）：{gone_all}")

    def test_c_entry_reachable(self):
        """C. 入口通：过唯一门能拿到总表。"""
        r = self.m.keys()
        self.assertTrue(r.get("ok"), f"keys 取不到：{r}")
        self.assertGreaterEqual(len(r.get("surfaces") or []), 3,
                               "可控制面总表少于 3 个工具（可能只探了一部分）")

    def test_d_blender_not_an_exception(self):
        """D. Blender 不算例外：2409 个 bpy 算子必须齐（≥2000）。"""
        self.assertTrue(BLENDER_MAN.is_file(), "Blender 可控制面清单缺失")
        d = json.loads(BLENDER_MAN.read_text(encoding="utf-8"))
        ops = (d.get("counts") or {}).get("operators") or 0
        self.assertGreaterEqual(ops, 2000, f"Blender 算子 {ops} < 2000 ⇒ 有漏")


if __name__ == "__main__":
    unittest.main(verbosity=2)
