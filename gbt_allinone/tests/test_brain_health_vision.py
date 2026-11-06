# -*- coding: utf-8 -*-
"""判据：健康体检的「眼」维不许拿「模块加载成功」冒充「能看到」；
      五维合一的验证链路不许把失败原因压成一个 False。

血账见 `brain_exec._vision_dim` 的 docstring：
2026-11-05 本机 eye_ready() 返回 True、eye_error() 空串，而真实抓帧直接抛
CaptureUnavailable（三级采集后端全灭），health 因此报 5/5 = 100 分。
"""
from __future__ import annotations

import unittest
from unittest import mock

from .. import brain_exec as BE
from ..tentacle import bridge as TB
from ..tentacle import vision_bus as VB


class CaptureUnavailable(RuntimeError):
    """模拟 gbt_allinone.tentacle.omni_core.CaptureUnavailable。"""


class VisionDimTest(unittest.TestCase):
    """视觉维：只有真抓到帧才算 ok。"""

    def test_capture_raises_is_not_ready(self):
        """本机实况：模块加载成功、后端全灭、snapshot 抛异常 —— 必须报不 ok 且带原话。"""
        with mock.patch.object(TB, "eye_ready", return_value=True), \
             mock.patch.object(TB, "get_eye", return_value=object()), \
             mock.patch.object(VB, "snapshot",
                               side_effect=CaptureUnavailable(
                                   "screen_grab_unavailable: 三级后端全灭")):
            d = BE._vision_dim()
        self.assertFalse(d["ok"], "抓帧抛异常却报 ok —— 这正是要防的假绿")
        self.assertIn("CaptureUnavailable", d["detail"])
        self.assertIn("三级后端全灭", d["detail"])

    def test_capture_returns_not_ok(self):
        """snapshot 不抛、但自己说 ok=False —— 也不许算就绪，原因要带出来。"""
        with mock.patch.object(TB, "eye_ready", return_value=True), \
             mock.patch.object(TB, "get_eye", return_value=object()), \
             mock.patch.object(VB, "snapshot",
                               return_value={"ok": False, "error": "no_frame"}):
            d = BE._vision_dim()
        self.assertFalse(d["ok"])
        self.assertIn("no_frame", d["detail"])

    def test_capture_ok_is_ready(self):
        """真抓到帧才算绿。"""
        with mock.patch.object(TB, "eye_ready", return_value=True), \
             mock.patch.object(TB, "get_eye", return_value=object()), \
             mock.patch.object(VB, "snapshot",
                               return_value={"ok": True, "size": [1920, 1080],
                                             "fingerprint": "abc"}):
            d = BE._vision_dim()
        self.assertTrue(d["ok"])
        self.assertIn("1920", d["detail"])

    def test_eye_not_loaded(self):
        """eye 根本没加载 —— 不 ok，且把 eye_error 原话带出来。"""
        with mock.patch.object(TB, "eye_ready", return_value=False), \
             mock.patch.object(TB, "eye_error",
                               return_value="ImportError: 没有 omni_tentacle"):
            d = BE._vision_dim()
        self.assertFalse(d["ok"])
        self.assertIn("没有 omni_tentacle", d["detail"])

    def test_eye_error_blank_still_not_ready(self):
        """eye_error 是空串（本机就是这样）也不许因此判绿。"""
        with mock.patch.object(TB, "eye_ready", return_value=False), \
             mock.patch.object(TB, "eye_error", return_value=""):
            d = BE._vision_dim()
        self.assertFalse(d["ok"])
        self.assertTrue(d["detail"], "detail 不许为空 —— 空串等于没告诉人为什么")

    def test_eye_ready_raising_does_not_explode(self):
        """eye_ready() 自己抛异常也只报不 ok，不许把整个 health 带崩。"""
        with mock.patch.object(TB, "eye_ready",
                               side_effect=RuntimeError("COM 初始化失败")):
            d = BE._vision_dim()
        self.assertFalse(d["ok"])
        self.assertIn("eye_ready", d["detail"])
        self.assertIn("COM 初始化失败", d["detail"])


class UnifyVerifyDetailTest(unittest.TestCase):
    """五维合一：验证失败必须带得出原因，不许只留一个 False。"""

    @staticmethod
    def _fake_verify(checks, ok, verdict="unverified_no_surface"):
        def _v(*_a, **_k):
            return {"ok": ok, "verdict": verdict, "checks": checks,
                    "counted_faces": [], "faces": 0}
        return _v

    def _run_unify(self, verify_fn):
        rt = {"best": {"kind": "selfscan"}, "candidates": 1,
              "path": "semantic", "degraded": False}
        hl = {"score": 80.0, "healthy_dims": 4, "total_dims": 5}
        with mock.patch.object(BE, "route", return_value=rt), \
             mock.patch.object(BE, "execute",
                               return_value={"ok": True, "status": "ok"}), \
             mock.patch.object(BE, "verify", side_effect=verify_fn), \
             mock.patch.object(BE, "health", return_value=hl):
            return BE.unify("假目标：只验链路结构")

    def test_failed_check_keeps_reason(self):
        checks = {"vision": {"ok": False,
                             "error": "CaptureUnavailable: 三级后端全灭"}}
        r = self._run_unify(self._fake_verify(checks, ok=False))
        v = r["chain"]["verify"]
        self.assertFalse(v["ok"])
        self.assertFalse(v["checks"]["vision"])
        self.assertEqual(v["verdict"], "unverified_no_surface")
        self.assertIn("三级后端全灭", v["detail"]["vision"]["error"])

    def test_passed_check_adds_no_detail_noise(self):
        """过了的项不塞 detail，免得把读数淹掉。"""
        checks = {"reality": {"ok": True, "faces": 2}}
        r = self._run_unify(self._fake_verify(checks, ok=True, verdict="verified"))
        v = r["chain"]["verify"]
        self.assertTrue(v["ok"])
        self.assertEqual(v["detail"], {})

    def test_verify_ok_does_not_override_execute(self):
        """unify 的 ok 仍以 execute 为准（验证「验不了」≠「执行失败」）。"""
        r = self._run_unify(self._fake_verify({}, ok=False))
        self.assertTrue(r["ok"], "execute 成功时 unify 不该因为验不了现实就判失败")


class CaptureLegsStatusTest(unittest.TestCase):
    """采集全灭时，报错要点名三条腿，并区分「缺件」与「装了但没出帧」。

    血账：原来只拼 `_last_err`，而它只有 mss/pyautogui **抛异常**时才写；
    dxcam 返回 None（没装）、mss 直接 None（没装）都不留痕，
    于是报出「三级后端全灭：pyautogui: ModuleNotFoundError」——
    读起来像只缺 pyautogui，实际三条全缺。诊断时被它带偏过一轮。

    为什么只测 `_capture_legs_status()` 而不跑完整 `_screen_capture()`：
    跑完整抓帧的话判据会依赖「本机装没装 mss/pyautogui」——
    实测 pyembed 运行时里 pyautogui 是装着的，只按 dxcam/mss 两条腿时它真能
    抓到帧，`assertRaises` 直接「Exception not raised」假失败。
    判据必须与机器解耦，否则换个解释器就换个结论。
    """

    def test_all_three_legs_named(self):
        from ..tentacle import omni_core as OC
        legs = OC._capture_legs_status()
        self.assertEqual(len(legs), 3, "三路后端都要报，不许只报最后一条")
        joined = "；".join(legs)
        for mod in ("dxcam", "mss", "pyautogui"):
            self.assertIn(mod, joined, "必须点名 %s，否则诊断会被带偏" % mod)

    def test_missing_leg_reported_as_missing(self):
        from ..tentacle import omni_core as OC
        with mock.patch.dict("sys.modules", {"pyautogui": None}):
            joined = "；".join(OC._capture_legs_status())
        self.assertIn("pyautogui", joined)
        self.assertIn("缺件", joined)

    def test_installed_leg_uses_different_wording(self):
        """装上了却没出帧 —— 措辞必须不同于「缺件」，否则分不清该装还是该修。"""
        from ..tentacle import omni_core as OC
        fake = mock.MagicMock(name="mss")
        with mock.patch.dict("sys.modules", {"mss": fake}):
            legs = OC._capture_legs_status()
        self.assertTrue(any("mss" in x and "没出帧" in x for x in legs), legs)


if __name__ == "__main__":
    unittest.main()
