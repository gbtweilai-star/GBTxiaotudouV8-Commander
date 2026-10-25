# -*- coding: utf-8 -*-
"""品牌片尾 · 带牙用例（R-H182）。

① 固定结尾**逐字在场**（改一个字就红）；
② 三层齐 + 四种作品类型都有自述 + 四个场景变体都在；
③ 红线 1 署名不造假：出现"人类制作/真人团队"⇒ 拒绝渲染；
④ 红线 2 致谢不套话：缺作品名 ⇒ 直接拒绝（ValueError）；
⑤ 红线 3 承诺可追溯：缺作品编号 ⇒ traceable=False + 显式 warning（不静默）；
⑥ 红线 4 观众不被当流量：漏斗话术 ⇒ 拒绝渲染；
⑦ 只读：源码不许有联网/写盘路径。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT, ROOT / "gbt_allinone"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gbt_allinone.tools import brand_outro as bo  # noqa: E402


class FixedThanksTests(unittest.TestCase):
    def test_fixed_thanks_is_verbatim(self):
        want = ("感谢每一位观众老爷的观看和喜欢。\n"
                "小土豆在这里谢谢大家，非常非常感谢。\n"
                "我们会继续努力，做更好的作品。\n"
                "—— GBT小土豆 · 新人类AI团队")
        self.assertEqual(bo.FIXED_THANKS, want, "固定结尾是原话，一个字都不许改")

    def test_rendered_outro_contains_every_layer(self):
        out = bo.render("music", "第一首歌", work_id="MUSIC-0001", variant="first",
                        audience="刚分手的人", scene="分手三个月后整理房间翻到对方送的杯子")
        self.assertTrue(out["ok"])
        for piece in ("第一首歌", bo.BRAND, bo.CREATOR, bo.KEEPER, bo.TEAM,
                      bo.FIXED_THANKS, bo.VARIANTS["first"], "出品日期"):
            self.assertIn(piece, out["text"])
        self.assertEqual(out["version"], "brand-outro/v1")
        self.assertTrue(out["promise"]["traceable"])
        self.assertEqual(out["promise"]["ref"], "MUSIC-0001")

    def test_all_work_types_and_scenes_exist(self):
        for wt in ("music", "video", "film", "engineering"):
            self.assertTrue(bo.intro(wt, audience="某个人",
                                     scene="加班到凌晨三点还在改稿"))
        for sc in bo.VARIANT_SCENES:
            self.assertTrue(bo.thanks(sc))


class RedLineTests(unittest.TestCase):
    def test_fake_signature_is_refused(self):
        out = bo.render("film", "某片", work_id="FILM-1",
                        audience="深夜刷片的人", scene="周五深夜一个人在家点开这部片",
                        extra="本片由人类制作团队实拍")
        self.assertFalse(out["ok"])
        self.assertIn("no_fake_signature", [p["rule"] for p in out["problems"]])

    def test_missing_work_name_is_refused(self):
        with self.assertRaises(ValueError):
            bo.render("music", "   ")

    def test_promise_without_work_id_is_visible_not_silent(self):
        out = bo.render("engineering", "某项目",
                        audience="接手的同事", scene="凌晨上线前最后一次核对")
        self.assertTrue(out["ok"])
        self.assertFalse(out["promise"]["traceable"])
        self.assertIn("warning", out, "承诺不可追溯必须显式告警，不许静默")
        self.assertIn("缺作品编号", out["warning"])

    def test_funnel_talk_is_refused(self):
        out = bo.render("video", "某片", work_id="VIDEO-1",
                        audience="通勤路上刷手机的人", scene="地铁上刷到这条的瞬间",
                        extra="看完记得扫码加群领福利")
        self.assertFalse(out["ok"])
        self.assertIn("audience_not_traffic", [p["rule"] for p in out["problems"]])

    def test_selfintro_must_state_audience_and_scene(self):
        """贯通③：自述层必须说清"为谁做、在什么场景下做"（缺一即拒；类别词不算）。"""
        with self.assertRaises(ValueError):
            bo.render("music", "某首歌", work_id="MUSIC-9")
        with self.assertRaises(ValueError):
            bo.render("music", "某首歌", work_id="MUSIC-9", audience="某人",
                      scene="失去这种感受本身")
        ok = bo.render("music", "某首歌", work_id="MUSIC-9", audience="刚分手的人",
                       scene="分手三个月后整理房间翻到对方送的杯子")
        self.assertTrue(ok["ok"])
        self.assertIn("为谁做：刚分手的人", ok["text"])
        self.assertIn("在什么场景下做：", ok["text"])

class ReadonlyTests(unittest.TestCase):
    def test_module_has_no_network_or_write_paths(self):
        src = Path(bo.__file__).read_text(encoding="utf-8")
        for bad in ("import requests", "import urllib", "import socket", "import subprocess",
                    ".write_text(", ".write_bytes(", "unlink(", "from ..store"):
            self.assertNotIn(bad, src, "只读模块里不该出现：%s" % bad)


if __name__ == "__main__":
    unittest.main()
