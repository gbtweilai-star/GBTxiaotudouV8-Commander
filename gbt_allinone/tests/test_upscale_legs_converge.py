# -*- coding: utf-8 -*-
"""三条「放大/清晰度」腿的**收敛判据**（2026-10-13 · 主人令「每一个调节都要触手可控」）。

主腿 = `comfy_native.upscale_4k`（PIL LANCZOS + USM）· 历史腿 = `zimage_rewash.upscale`（ffmpeg）。
本判据只验**契约与拒绝语义**（不起 ffmpeg、不写盘）：
  ① 历史腿收到 `sharpen` ⇒ **必须 fail-closed 并指路主腿**（量纲不同，不许改名冒充）
  ② `factor` 与 `scale` 同时给且不等 ⇒ fail-closed
  ③ 被拒时**不许动盘**（没有产物落出来）
  ④ 两条腿的锐化旋钮名**本来就不同**（主腿 `sharpen` / 历史腿 `unsharp`）—— 这是**事实**，判据把它钉死

跑法：`py -3.14 -m unittest gbt_allinone.tests.test_upscale_legs_converge -v`
"""
import base64
import io
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from gbt_allinone.tools import comfy_native as CN          # noqa: E402
from gbt_allinone.tools import zimage_rewash_cap as ZR     # noqa: E402

_TMP = tempfile.TemporaryDirectory(prefix="gbt-upscale-legs-")


def _png(path: Path, w=64, h=48) -> Path:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (30, 30, 40)).save(buf, "PNG")
    path.write_bytes(buf.getvalue())
    return path


class TestLegsConverge(unittest.TestCase):
    def test_sharpen_on_legacy_leg_is_refused_and_points_to_main(self):
        src = _png(Path(_TMP.name) / "src.png")
        out = Path(_TMP.name) / "should-not-exist.png"
        r = ZR.upscale(src=str(src), out=str(out), sharpen=0.6)
        self.assertFalse(r["ok"], r)
        self.assertTrue(r["fail_closed"], r)
        self.assertIn("comfy_native.upscale_4k", r["要锐化就走去主腿"], r)

    def test_factor_scale_conflict_is_refused(self):
        src = _png(Path(_TMP.name) / "src2.png")
        r = ZR.upscale(src=str(src), factor=2, scale=3)
        self.assertFalse(r["ok"], r)
        self.assertTrue(r["fail_closed"], r)

    def test_refusal_does_not_touch_disk(self):
        src = _png(Path(_TMP.name) / "src3.png")
        out = Path(_TMP.name) / "refused-output.png"
        ZR.upscale(src=str(src), out=str(out), sharpen=0.5)
        ZR.upscale(src=str(src), out=str(out), factor=2, scale=3)
        self.assertFalse(out.exists(), "被拒的调用**不许**在盘上留下产物：%s" % out)

    def test_the_two_legs_really_have_different_sharpen_knob_names(self):
        """事实钉死：主腿只有 `sharpen`、历史腿只有 `unsharp` —— 所以「统一名字」是**假统一**。"""
        main_in = {str(x).rstrip("?") for x in CN.NODES["upscale_4k"]["in"]}
        self.assertIn("sharpen", main_in)
        self.assertNotIn("unsharp", main_in, "主腿不该有 unsharp（量纲不同，别混）")
        import inspect
        params = set(inspect.signature(ZR.upscale).parameters)
        self.assertIn("unsharp", params)
        self.assertIn("scale", params, "历史腿要接受统一后的几何新名 scale")
        self.assertIn("sharpen", params, "要显式接住 sharpen 才能拒它（而不是 TypeError）")


if __name__ == "__main__":
    unittest.main(verbosity=2)
