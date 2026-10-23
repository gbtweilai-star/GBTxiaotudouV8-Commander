# -*- coding: utf-8 -*-
"""语音 · 识别前 16 kHz 归一化（`voice_cap._normalize_wav_16k`）

为什么要有这条判据（2026-10-18，主人令「可以」后加的降质点）：
  实测同一条素材：**24 kHz 直喂 → confidence 0.252；转 16 kHz → 0.311（+24%）**。
  识别器走 `SetInputToWaveFile`，桌面版吃 16k；不归一就等于自己把识别率砍掉四分之一。
  这条判据钉三件事：
    ① 24k/立体声 → **真被转**成 16k/单声道/16bit，且回执如实写 `changed=True`；
    ② 本来就 16k 的 → **不折腾**（`changed=False`，路径仍是原文件）；
    ③ 转不成（读不了头 / ffmpeg 不在）→ **如实报未归一**，绝不假装转过。

开发者：自由的风 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
import wave
from pathlib import Path

from gbt_allinone import voice_cap


def _write_wav(path: Path, rate: int, channels: int, seconds: float = 0.5) -> None:
    frames = int(rate * seconds)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * frames * channels)


class TestNormalizeWav16k(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gbt-test-norm-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _rate(self, p: Path):
        with wave.open(str(p), "rb") as w:
            return w.getnchannels(), w.getframerate(), w.getsampwidth()

    def test_24k_stereo_is_converted(self):
        src = self.tmp / "src24k.wav"
        _write_wav(src, 24000, 2)
        info = voice_cap._normalize_wav_16k(src)
        try:
            self.assertTrue(info["changed"], info)
            self.assertEqual(24000, info["in_rate"], "回执要写**源**采样率，别写成目标采样率")
            self.assertEqual(2, info["in_ch"])
            out = Path(info["path"])
            self.assertTrue(out.is_file(), "归一后的文件不在盘上")
            self.assertEqual((1, 16000, 2), self._rate(out), "输出必须是 16k/单声道/16bit")
        finally:
            if info.get("tmpdir"):
                shutil.rmtree(info["tmpdir"], ignore_errors=True)

    def test_already_16k_is_left_alone(self):
        src = self.tmp / "ok16k.wav"
        _write_wav(src, 16000, 1)
        info = voice_cap._normalize_wav_16k(src)
        self.assertFalse(info["changed"], info)
        self.assertEqual(str(src), info["path"])
        self.assertIn("无需归一", info["why"] or "")

    def test_unreadable_reports_honestly(self):
        bogus = self.tmp / "not-a-wav.txt"
        bogus.write_text("我不是 wav", encoding="utf-8")
        info = voice_cap._normalize_wav_16k(bogus)
        self.assertFalse(info["changed"])
        self.assertEqual(str(bogus), info["path"], "读不了头必须原样送识别，不许给个假路径")
        self.assertTrue(info["why"], "失败必须带原因")


if __name__ == "__main__":
    unittest.main()
