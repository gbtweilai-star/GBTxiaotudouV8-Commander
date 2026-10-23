# -*- coding: utf-8 -*-
"""三方向工作流的**内容接线**判据（2026-10-09 固化作 · 护照 fc-20261009T093626-0a66）。

锁住三件此前"跑通但没作品"的事：
  ① 成片时长由**脚本**定（原来写死 3s 彩条）· 画面烧进标题/逐镜字幕；
  ② 音乐链把**验过的 MIDI 编曲真渲染**成音频（原来产 440/660Hz 正弦）；
  ③ 剪辑时间线取**素材真时长**。
"""
import struct
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gbt_allinone.tools.media_run import (  # noqa: E402
    _design_clip, _render_arrangement, _script_lines, _midi_events, _have,
    _stamp_media, _read_media_tags, _apply_grade)


def _tiny_midi() -> bytes:
    """一个最小但**合规**的 SMF：tempo 120 + 调号 + 4 个音符 + 一个音色。"""
    div = 480

    def vlq(n):
        out = [n & 0x7F]; n >>= 7
        while n:
            out.append((n & 0x7F) | 0x80); n >>= 7
        return bytes(reversed(out))

    def meta(t, d):
        return bytes([0xFF, t]) + vlq(len(d)) + d

    ev = [(0, meta(0x51, struct.pack(">I", 500000)[1:])),
          (0, meta(0x59, bytes([0, 1]))),
          (0, bytes([0xC0, 0]))]
    for i, p in enumerate((69, 72, 76, 69)):
        ev.append((0 if i == 0 else div, bytes([0x90, p, 80])))
        ev.append((div, bytes([0x80, p, 0])))
    data = b"".join(vlq(d) + e for d, e in ev) + vlq(0) + meta(0x2F, b"")
    trk = b"MTrk" + struct.pack(">I", len(data)) + data
    return b"MThd" + struct.pack(">IHHH", 6, 1, 1, div) + trk


def _dur(p) -> float:
    cp = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                         "-of", "default=nw=1:nk=1", str(p)], capture_output=True, timeout=60)
    try:
        return float((cp.stdout or b"0").decode().strip())
    except ValueError:
        return -1.0


@unittest.skipUnless(_have("ffmpeg"), "本机没有 ffmpeg")
class MediaQualityWiringTest(unittest.TestCase):

    def test_design_clip_has_script_duration_not_three_seconds(self):
        """① 时长听调用方的（脚本），不是写死的 3s；产物非空。"""
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "clip.mp4"
            r = _design_clip(out, 5.0, "320x480", "测试片", ["第一镜", "第二镜"])
            self.assertTrue(r["ok"], r)
            self.assertGreater(out.stat().st_size, 2000)
            self.assertAlmostEqual(_dur(out), 5.0, delta=0.6,
                                   msg="成片时长应等于传入时长（原来恒为 3s）")

    def test_render_arrangement_is_real_audio(self):
        """② 编曲真渲染：音符被解析、时长随 tempo/音符走、波形**不是静音**。"""
        with tempfile.TemporaryDirectory() as td:
            mid = Path(td) / "a.mid"; mid.write_bytes(_tiny_midi())
            out = Path(td) / "a.wav"
            r = _render_arrangement(mid, out)
            self.assertTrue(r["ok"], r)
            self.assertGreaterEqual(r["notes"], 4)
            m = _midi_events(mid.read_bytes())
            self.assertEqual(m["tempo"], 500000)          # 120 BPM
            with wave.open(str(out)) as f:
                frames = f.readframes(f.getnframes())
            self.assertGreater(len(frames), 8000, "渲染出来的音频不该是空的")
            peak = max(abs(int.from_bytes(frames[i:i + 2], "little", signed=True))
                       for i in range(0, min(len(frames), 40000), 2))
            self.assertGreater(peak, 500, "波形近似静音 ⇒ 编曲没被真渲染")

    def test_media_carries_the_gbt_stamp(self):
        """④ objective 要的「带钢印」：`signature` 只覆盖文本页，音视频必须另打容器钢印。"""
        with tempfile.TemporaryDirectory() as td:
            clip = Path(td) / "c.mp4"
            self.assertTrue(_design_clip(clip, 1.5, "320x480", "钢印测试", ["一"]).get("ok"))
            self.assertEqual(_read_media_tags(clip).get("comment"), None,
                             "打钢印之前不该有 comment（否则这条判据测的是空气）")
            r = _stamp_media(clip, "钢印测试", "short_video", "export")
            self.assertTrue(r.get("ok"), r)
            tags = _read_media_tags(clip)
            self.assertIn("自由的风", str(tags.get("artist") or "") + str(tags.get("comment") or ""))
            self.assertIn("不可篡改归属", str(tags.get("comment") or "") + str(tags.get("description") or ""))
            # 幂等：再打一次，不追加、仍 verified
            r2 = _stamp_media(clip, "钢印测试", "short_video", "export")
            self.assertTrue(r2.get("ok"), r2)
            self.assertLessEqual(str(_read_media_tags(clip).get("comment") or "").count("自由的风"), 2,
                                 "重复打钢印把 comment 越堆越长 ⇒ 不是幂等")

    def test_rendered_clip_passes_delivery_qc(self):
        """⑤ 交付 QC 必须过（实测踩过两回）：
        ① 底色调太暗 ⇒ `pix_th=0.06` 把整片当黑帧；
        ② 推拉饱和/太慢 ⇒ 长镜后段卡帧。
        这条把「能不能交付」从感觉变成会红的判据。"""
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "q.mp4"
            shots = [{"title": "甲", "t0": 0, "t1": 3, "shot_size": "特写",
                      "camera": "推近", "emotion": "好奇"},
                     {"title": "乙", "t0": 3, "t1": 6, "shot_size": "中景",
                      "camera": "跟拍", "emotion": "平静"}]
            r = _design_clip(out, 6.0, "320x568", "QC", None, shots=shots)
            self.assertTrue(r.get("ok"), r)
            self.assertEqual(r.get("segments"), 2, "逐镜模式应该两段")
            g = _apply_grade(out, "赛博霓虹")
            self.assertTrue(g.get("ok"), g)
            q = g.get("qc") or {}
            self.assertEqual(q.get("black"), 0, "底色太暗 ⇒ 整片被判黑帧：%s" % q)
            self.assertEqual(q.get("freeze"), 0, "推拉饱和或太慢 ⇒ 卡帧：%s" % q)
            self.assertEqual(q.get("verdict"), "通过", q)

    def test_script_lines_pull_shot_titles(self):
        """③ 字幕取自脚本每镜的小标题（不是占位）。"""
        rel = ".scratch/_test_sop_script.md"
        p = Path(__file__).resolve().parents[2] / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("0s – 4s（开机）\n黑屏。特写，推近，好奇。\n\n"
                     "4s – 9s（爬行）\n管道。中景，跟拍，紧张。\n", encoding="utf-8")
        try:
            self.assertEqual(_script_lines(rel), ["开机", "爬行"])
        finally:
            p.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
