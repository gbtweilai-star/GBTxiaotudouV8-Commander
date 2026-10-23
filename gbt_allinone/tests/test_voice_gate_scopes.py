# -*- coding: utf-8 -*-
"""语音 · 门作用域现读（`voice_cap._gate_scopes`）+ `attempts` 不覆盖

为什么要有这条判据（2026-10-18 实修两处「读数说假话」）：
  ① `gate_blind_spot` 恒为「作用域 未读到」。
     真因：`policy.evaluate()` 返回的是 **dataclass `PolicyDecision`**，
     而代码只认 `isinstance(x, dict)` ⇒ 永远读不到，字段自相矛盾
     （同一返回里 listen 明明被 privacy_read 拦住）。
  ② `wasapi-record` 腿写「逐条原因见 attempts」，而 `attempts` 是**空数组**。
     真因：`_record_wav` 里 `d["attempts"] = attempts`（解释器级，通常空）
     **覆盖**了录音件自己报的设备级 attempts。

这两条都不需要任何票就能验（纯读 policy / 纯看形状）。
开发者：自由的风 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import inspect
import unittest

from gbt_allinone import voice_cap


class TestGateScopes(unittest.TestCase):
    def test_listen_requires_privacy_read(self):
        sc = voice_cap._gate_scopes("listen")
        self.assertIsNotNone(sc, "读不到 policy 时必须返回 None，不能拿空表冒充")
        self.assertIn("privacy_read", sc, "listen（开麦）必须挂 privacy_read —— 实测门就是这么拦的")

    def test_tts_requires_audio_output(self):
        self.assertIn("audio_output", voice_cap._gate_scopes("tts") or [])

    def test_status_is_ungated(self):
        self.assertEqual([], voice_cap._gate_scopes("status"), "status 是只读探针，不该有作用域")

    def test_unknown_op_does_not_crash(self):
        self.assertIsNotNone(voice_cap._gate_scopes("这是个不存在的 op"))


class TestAttemptsNotClobbered(unittest.TestCase):
    """静态判据：`_record_wav` 不许再把录音件的 attempts 覆盖掉。

    它不是运行时判据——真跑录音要 privacy_read 票。这里咬的是**源码形状**：
    一旦有人把 `d["attempts"] = attempts` 写回去而不同时保留 device_attempts，
    这条就红。（教训：能静态咬住的诚实性缺陷，别等票。）
    """

    def test_source_keeps_device_attempts(self):
        raw = inspect.getsource(voice_cap._record_wav)
        # 🔴 只查**代码行**：我的修法注释里引用了旧代码（"原来这一行直接 d[\"attempts\"] = attempts"），
        #    第一版判据没滤注释 ⇒ 被自己的注释骗出一片红（判据错尺，P1 同族）。
        code = "\n".join(ln for ln in raw.splitlines() if not ln.strip().startswith("#"))
        self.assertIn('d["device_attempts"]', code,
                      "必须把录音件自己的 attempts 另存为 device_attempts")
        i_dev = code.index('d["device_attempts"]')
        i_att = code.index('d["attempts"] = attempts')
        self.assertLess(i_dev, i_att, "必须先保留 device_attempts，再覆盖 attempts")


class TestListenDeviceParam(unittest.TestCase):
    """`listen` 必须能把设备号传下去（2026-10-18 根因修法）。

    本机 `default_input` 全是 -1 ⇒ 只开"默认设备"永远 no_input；
    而 WDM-KS 看得见 Realtek 麦克风 #9。这是接线判据（不录音、不开麦、不要票）：
    只验「设备号有没有真的进到录音件的命令行里」。
    """

    def _fake_run(self, calls):
        import json as _json

        class CP:
            def __init__(self, b, rc=0):
                self.stdout, self.stderr, self.returncode = b, b"", rc

        def run(cmd, **kw):
            calls.append(list(cmd))
            out = cmd[cmd.index("--out") + 1]
            return CP(_json.dumps({"ok": True, "wav": out, "api": "WDM-KS",
                                   "device": "麦克风"}).encode("utf-8"))
        return run

    def test_device_reaches_recorder_command(self):
        from unittest import mock
        calls = []
        with mock.patch.object(voice_cap.subprocess, "run", side_effect=self._fake_run(calls)):
            rec = voice_cap._record_wav(1, 30, device=9)
        self.assertTrue(rec.get("ok"), rec)
        self.assertTrue(calls, "录音件根本没被调用")
        joined = " ".join(calls[0])
        self.assertIn("--device", joined, "设备号没进命令行 ⇒ 还是只会开默认设备")
        self.assertIn("9", calls[0][calls[0].index("--device") + 1::1][0])

    def test_no_device_keeps_old_behavior(self):
        from unittest import mock
        calls = []
        with mock.patch.object(voice_cap.subprocess, "run", side_effect=self._fake_run(calls)):
            voice_cap._record_wav(1, 30)
        self.assertNotIn("--device", " ".join(calls[0]), "不给设备号时不许偷偷加参数")

    def test_bad_device_is_reported_not_guessed(self):
        rec = voice_cap._record_wav(1, 30, device="第九个")
        self.assertFalse(rec.get("ok"))
        self.assertEqual("bad_device", rec.get("status"))
        self.assertIn("整数", rec.get("error") or "")

    def test_listen_signature_accepts_device(self):
        import inspect
        sig = inspect.signature(voice_cap.asr_local)
        self.assertIn("device", sig.parameters, "asr_local 必须收 device，否则分派传不进来")
        self.assertIn("device", voice_cap._ACCEPTED_PARAMS["listen"])


class TestLoopbackLeg(unittest.TestCase):
    """`device=loopback` 必须走**回环件**，不是录音件（2026-10-18 新增能力）。"""

    def test_loopback_routes_to_loopback_script(self):
        from unittest import mock
        seen = []

        class CP:
            stdout = b'{"ok": false, "status": "no_frames", "reason": "\xe7\xa9\xba\xe9\x97\xb2", "device": "x [Loopback]"}'
            stderr = b""
            returncode = 0

        def run(cmd, **kw):
            seen.append(list(cmd))
            return CP()

        with mock.patch.object(voice_cap.subprocess, "run", side_effect=run):
            rec = voice_cap._record_wav(1, 30, device="loopback")

        self.assertTrue(seen, "回环件根本没被调用")
        joined = " ".join(seen[0])
        self.assertIn("wasapi-loopback.py", joined, "device=loopback 必须调回环件")
        self.assertNotIn("wasapi-record.py", joined, "不许调普通录音件")
        self.assertEqual("no_frames", rec.get("status"))
        # 回执必须自己说清走的是哪条腿：loopback 的回执不许冒名 wasapi-record
        self.assertEqual("loopback", rec.get("leg"),
                         "回环回执的 leg 没标 loopback（会被念成普通录音腿）")

    def test_loopback_aliases(self):
        from unittest import mock
        for alias in ("loopback", "desktop", "system"):
            seen = []

            class CP:
                stdout = b'{"ok": true, "status": "recorded", "wav": "/tmp/x.wav"}'
                stderr = b""
                returncode = 0

            def run(cmd, **kw):
                seen.append(list(cmd))
                return CP()

            with mock.patch.object(voice_cap.subprocess, "run", side_effect=run):
                voice_cap._record_wav(1, 30, device=alias)
            self.assertIn("wasapi-loopback.py", " ".join(seen[0]), "别名 %s 没走回环" % alias)


if __name__ == "__main__":
    unittest.main()
