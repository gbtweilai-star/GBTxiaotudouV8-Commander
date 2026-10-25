"""新增能力 · 双向绑定 + 全状态可感知 判据（主人令 2026-09-27）。

主人原话：「记住从现在开始不管新增能力**全部都要与触手双向绑定**，确保触手随时使用
**不会有故障和断连**，以及**都没实现却都没记录**必须时刻随时都能感知到框架的所有状态。」

**为什么做成判据而不是写成口号**：口号不会自己红。
本判据把那条规矩拆成四件可机检的事（读数**只从 `tools/framework_state.py` 来**，不抄第二份逻辑）：

  A. **能力位三处齐**：`caps_registry` 登记 · 图鉴 `skill_atlas.json` 收录 · `api.py` 有分派；
  B. **双向绑定**：正向 = 绑定账里的资产都真在盘上、触手名都在有效标签里；
     **反向** = 每个能力位都在触手字典里**叫得出来**（能绑、能用）；
  C. **没实现必须有名有姓**：A 里任何一项缺，必须登记在 `state/unimplemented.json`
     （带 where/missing/reason/who_can_fix/evidence）—— **不许无声挂着**；登记表损坏也算红；
  D. **全状态可感知**：六个面（能力位/双向绑定/技能源装/覆盖矩阵/视觉面/舰队）都读得出来，
     任何一面读失败或整盘有红项 ⇒ 红。

红了怎么办（判据里直说）：
  · 缺接线 → 补 `api.py` 分派分支或图鉴条目（三处一起改，少一处门就看不见它）；
  · 暂时做不出来 → 登记进 `state/unimplemented.json`（有名有姓 + 谁有权修）；
  · 断连 → 跑 `python tools/tentacle_bind.py autobind` / `sweep` 补绑；
  · 只看一眼全状态 → `python tools/framework_state.py`。
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "framework_state.py"
FACES = ("能力位", "双向绑定", "技能源装", "覆盖矩阵", "视觉面", "舰队")


def _load_tool():
    spec = importlib.util.spec_from_file_location("framework_state_probe", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestCapBidirectionalBinding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = _load_tool().collect()

    def test_d_every_face_is_readable(self):
        """D. 全状态可感知：六个面都读得出来（读失败也算红，不许拿"应该没事"顶替）。"""
        self.assertTrue(TOOL.is_file(), f"状态读取器不在位：{TOOL}")
        for name in FACES:
            self.assertIn(name, self.s["faces"], f"缺面：{name}")
            f = self.s["faces"][name]
            self.assertNotIn("error", f, f"【{name}】面读数失败：{f.get('error')}")

    def test_a_every_cap_is_wired_three_places(self):
        """A. 能力位三处齐：登记 · 图鉴 · 分派。"""
        caps = self.s["faces"]["能力位"]
        self.assertGreater(caps.get("registry", 0), 100, "能力位总数异常小 ⇒ 读数可疑")
        self.assertEqual([], caps.get("undispatched") or [],
                         f"这些能力位在 api.py 没有分派分支（登记了却调不到）：{caps.get('undispatched')}"
                         f"\n⇒ 补分派；暂时做不出就登记进 state/unimplemented.json")
        self.assertEqual([], caps.get("not_in_atlas") or [],
                         f"这些能力位不在图鉴 skill_atlas.json 里：{caps.get('not_in_atlas')}")

    def test_b_binding_clean_both_ways(self):
        """B. 双向绑定：资产↔触手两个方向都要通。"""
        bind = self.s["faces"]["双向绑定"]
        self.assertEqual(0, bind.get("断连_资产缺失"),
                         f"绑定账里有资产已不在盘上 ⇒ 跑 tools/tentacle_bind.py autobind 复核")
        self.assertEqual(0, bind.get("断连_触手不在册"),
                         "绑定账里有触手名不在有效标签里（绑到了不存在的能力位）")
        self.assertEqual([], bind.get("能力位无触手标签") or [],
                         f"这些能力位在触手字典里叫不出来（反向绑定断）＝ 触手用不了它："
                         f"{bind.get('能力位无触手标签')}")

    def test_c_unimplemented_must_be_named(self):
        """C. 没实现必须有名有姓：缺口必须登记，登记表损坏也算红。"""
        caps = self.s["faces"]["能力位"]
        self.assertNotIn("未登记缺口", caps,
                         f"这些缺口**没接线也没登记**（无声挂着）：{caps.get('未登记缺口')}"
                         f"\n⇒ 登记进 state/unimplemented.json（where/missing/reason/who_can_fix/evidence）")

    def test_no_red_anywhere(self):
        """总闸：状态读数若有任何红项，本判据红。"""
        self.assertEqual([], self.s.get("red") or [],
                         "框架状态有红项（见上）：" + "；".join(self.s.get("red") or []))


if __name__ == "__main__":
    unittest.main(verbosity=2)
