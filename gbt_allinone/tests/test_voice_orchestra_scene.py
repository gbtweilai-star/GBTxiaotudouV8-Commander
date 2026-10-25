"""R-H602（2026-09-25）· voice_orchestra 的**假绿灯**回归用例。

被测故障（实测抓到，不是推演）：
    老实现 `build_pipeline()` 只有 `pipelines.get(scene, pipelines["默认"])`
    ⇒ 未知场景**静默兜底**成「默认」链条，而 `run(op="pipeline")` 又把**请求的场景名**
    原样回显在 `scene` 字段里 ⇒
        `cap voice_orchestra '{"op":"pipeline","scene":"我瞎编的"}'`
    返回 `{"ok": true, "scene": "我瞎编的", "steps": <默认链条>}`。
    **读数在骗人，而且骗得很自然** —— 这正是本仓最忌的"假绿灯"。

判据（三条都要有牙）：
  1. 未知场景 **必须** ok=False（否则假绿灯回归）；
  2. 已知场景 **必须** ok=True 且 steps **与改动前一致**（不能把真路径修坏）；
  3. 空 scene 仍走原有的 `voice_scene_required`（不能顺手改掉别的契约）。
"""
from __future__ import annotations

import unittest

from gbt_allinone import voice_orchestra as VO


class VoiceOrchestraSceneTest(unittest.TestCase):
    def test_known_scene_still_matches_and_keeps_steps(self) -> None:
        """真路径不许被修坏：已知场景照样 ok，且链条内容逐条在。"""
        engine = VO.VoiceSkillEngine()
        for scene in engine.pipeline_scenes():
            res = VO.run("pipeline", scene=scene)
            self.assertTrue(res["ok"], "已知场景 %s 被判成失败" % scene)
            self.assertTrue(res["scene_matched"])
            self.assertEqual(res["steps"], engine.build_pipeline(scene),
                             "已知场景 %s 的链条被改动了" % scene)

    def test_unknown_scene_is_not_a_green_light(self) -> None:
        res = VO.run("pipeline", scene="这个场景不存在")
        self.assertFalse(res["ok"], "未知场景又变成了 ok:true —— 假绿灯回归")
        self.assertFalse(res["scene_matched"])
        self.assertEqual(res["rule"], "voice_scene_unknown")
        self.assertEqual(res["missing"], ["scene"])
        # 信息一点没少：可选场景 + 建议链条都还在，只是不再冒充"命中"
        self.assertIn("有声书", res["known_scenes"])
        self.assertTrue(res["suggested_steps"], "兜底链条没给出来，等于只报错不给人路")
        self.assertEqual(res["fallback_scene"], "默认")

    def test_empty_scene_keeps_the_original_contract(self) -> None:
        res = VO.run("pipeline")
        self.assertFalse(res["ok"])
        self.assertEqual(res["rule"], "voice_scene_required")
        self.assertEqual(res["missing"], ["scene"])

    def test_other_ops_untouched(self) -> None:
        """同一刀不许改到 list / status：这两条是面板真正在调的。"""
        self.assertTrue(VO.run("list")["ok"])
        st = VO.run()
        self.assertTrue(st["ok"])
        self.assertEqual(st["op"], "status")
        self.assertTrue(st.get("readonly"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
