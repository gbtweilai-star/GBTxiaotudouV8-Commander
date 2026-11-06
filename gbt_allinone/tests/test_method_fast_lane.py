"""触手方法快车道 · 只读白名单回归（2026-11-05）。

血账：快车道原来按**邻域**放行（感知/侦察/信息/媒体/安全），而四个邻域里混着
动手方法。实测下面这些句子会被**直接派发**、完全不经模型（用系统自己公布的别名
就能触发，不需要什么刁钻说法）：

    "往控件里输入" → domain_type        真往控件里打字
    "操作控件"     → domain_act         真触发控件
    "写剪贴板"     → clipboard_write    pyperclip.copy 覆盖剪贴板
    "复制进去"     → clipboard_write
    "录一段视觉"   → vision_stream_record 真写视频文件

本用例钉住三件事：
  ① 动手句拿不到快车道（不能因为"邻域是观测类"就放行）；
  ② 只读句仍然直达（修完不能把快车道修没了）；
  ③ 白名单自身可机器复查 —— 全是零参数方法，且不含任何写类方法。
"""
import inspect
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gbt_allinone import brain_exec as BE  # noqa: E402
from gbt_allinone.tentacle import bridge as TB  # noqa: E402


class MethodFastLaneTests(unittest.TestCase):
    def test_side_effect_phrases_never_take_fast_lane(self):
        for q in ("往控件里输入", "往这个控件里输入文字", "操作控件", "触发控件",
                  "写剪贴板", "复制进去", "录一段视觉", "录屏帧流"):
            self.assertIsNone(BE._method_lane(q), q)

    def test_read_only_phrases_still_take_fast_lane(self):
        for q, want in (("读剪贴板", "clipboard_read"),
                        ("有没有弹窗", "detect_dialog"),
                        ("看一眼现在屏幕什么样", "see")):
            r = BE._method_lane(q)
            self.assertIsNotNone(r, q)
            self.assertEqual(r["best"]["method"], want, q)
            self.assertEqual(r["method_fast"]["gate"], "read_only_whitelist")

    def test_whitelist_is_zero_arg(self):
        """快车道派发只塞 method、不带 kwargs（execute 里 setdefault），必填参会变成 needs_input。"""
        eye = TB.get_eye()
        raw = getattr(eye, "_raw", None) or eye
        for m in sorted(BE._METHOD_FAST_SAFE):
            fn = getattr(raw, m, None)
            self.assertIsNotNone(fn, m)
            sig = inspect.signature(fn)
            req = [n for n, p in sig.parameters.items()
                   if p.default is p.empty
                   and p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)]
            self.assertEqual(req, [], m)

    def test_whitelist_contains_no_writer(self):
        banned = {"clipboard_write", "copy", "cut", "paste", "select_all",
                  "domain_type", "domain_act", "handle_any_dialog", "monitor",
                  "vision_stream_record", "vision_stream_replay",
                  "type", "click", "launch", "kill", "export_data",
                  "file_write_text", "file_delete", "clear_log"}
        self.assertFalse(BE._METHOD_FAST_SAFE & banned,
                         sorted(BE._METHOD_FAST_SAFE & banned))

    def test_neighborhood_is_no_longer_the_gate(self):
        """回归钉子：门是方法名集合，不是邻域名集合（旧口径必须彻底消失）。"""
        self.assertFalse(hasattr(BE, "_METHOD_FAST_DOMAINS"))


if __name__ == "__main__":
    unittest.main()
