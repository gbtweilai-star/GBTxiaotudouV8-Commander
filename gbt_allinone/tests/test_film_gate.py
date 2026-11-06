# -*- coding: utf-8 -*-
"""成片验收器的机器判据（2026-11-06）。

为什么这批判据值得写：整条「分镜→剪切→生图→成片」此前**没有任何机器验收**——
交付靠人写 markdown 报告，报告里的 1080×1920 / 25fps / 15.000s / 字幕尾端差
没人复核，也没法复跑。而本机**没有 ffmpeg**，连 ffprobe 都调不了。

所以这里钉两件事：
  ① 解析器自己解容器（不 shell 出去），自造 MP4 也要读得对；
  ② 判据三态不许混装：缺件 `needs_input`、坏片 `failed`、算不了的一律 `skipped`，
     **不许**把「没给对照」当成「通过了」。
"""
import struct
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from gbt_allinone.tools import film_gate as FG   # noqa: E402


# ── 自造最小 MP4（只为验解析器，不是可播放片）──────────────────────────────
def _box(typ, payload=b""):
    return struct.pack(">I", 8 + len(payload)) + typ.encode("latin-1") + payload


def _mvhd(ts, dur):
    b = bytearray(100)
    struct.pack_into(">I", b, 12, ts)
    struct.pack_into(">I", b, 16, dur)
    return _box("mvhd", bytes(b))


def _tkhd(w, h):
    b = bytearray(84)
    b += struct.pack(">II", int(w * 65536), int(h * 65536))
    return _box("tkhd", bytes(b))


def _mdhd(ts, dur):
    b = bytearray(24)
    struct.pack_into(">I", b, 12, ts)
    struct.pack_into(">I", b, 16, dur)
    return _box("mdhd", bytes(b))


def _hdlr(kind):
    b = bytearray(24)
    b[8:12] = kind.encode("latin-1")
    return _box("hdlr", bytes(b))


def _stts(count, delta):
    b = bytearray(8)
    struct.pack_into(">I", b, 4, 1)
    b += struct.pack(">II", count, delta)
    return _box("stts", bytes(b))


def _stsd(fmt, payload=b""):
    b = bytearray(8)
    struct.pack_into(">I", b, 4, 1)
    b += struct.pack(">I", 8 + len(payload)) + fmt.encode("latin-1") + payload
    return _box("stsd", bytes(b))


def _trak(kind, ts, dur, stbl, w=0, h=0):
    mdia = _box("mdia", _mdhd(ts, dur) + _hdlr(kind)
                + _box("minf", _box("stbl", stbl)))
    return _box("trak", _tkhd(w, h) + mdia)


def _mp4(path, *, dur=15.0, ts=1000, w=1080, h=1920, frames=375, fps=25.0,
         audio=True):
    vdur = int(round(frames / fps * ts))
    stbl = _stsd("avc1") + _stts(frames, int(round(ts / fps)))
    moov = _mvhd(ts, int(round(dur * ts))) + _trak("vide", ts, vdur, stbl, w, h)
    if audio:
        ab = bytearray(28)
        struct.pack_into(">H", ab, 16, 1)              # channels
        struct.pack_into(">I", ab, 24, 44100 << 16)     # samplerate 16.16
        astbl = _stsd("mp4a", bytes(ab)) + _stts(1, 44100)
        moov += _trak("soun", 44100, int(round(dur * 44100)), astbl)
    path.write_bytes(_box("ftyp", b"isom" + b"\x00" * 8) + _box("moov", moov))
    return path


def _sb(**over):
    seg = {"id": "E01-01",
           "cuts": [{"seconds": 3}, {"seconds": 3}, {"seconds": 4}, {"seconds": 5}],
           "h3Prompt": ("Picture 1 (from Shot 1) aligns with the 0.00-second mark; "
                        "Picture 2 (from Shot 2) aligns with the 3.00-second mark; "
                        "Picture 3 (from Shot 3) aligns with the 6.00-second mark; "
                        "Picture 4 (from Shot 4) aligns with the 10.00-second mark.\n"
                        "[Shot 1] a\n[Shot 2] b\n[Shot 3] c\n[Shot 4] d")}
    seg.update(over)
    return {"episodes": [{"ep": 1, "segments": [seg]}]}


class TestProbeMp4(unittest.TestCase):
    def test_reads_duration_resolution_fps(self):
        with tempfile.TemporaryDirectory() as d:
            p = _mp4(Path(d) / "a.mp4")
            r = FG.probe_mp4(p)
            self.assertTrue(r["ok"], r)
            self.assertAlmostEqual(r["duration"], 15.0, places=3)
            self.assertEqual((r["video"]["width"], r["video"]["height"]), (1080.0, 1920.0))
            self.assertEqual(r["video"]["frames"], 375)
            self.assertAlmostEqual(r["video"]["fps"], 25.0, places=2)
            self.assertEqual(r["video"]["codec"], "avc1")

    def test_reads_audio_track(self):
        with tempfile.TemporaryDirectory() as d:
            r = FG.probe_mp4(_mp4(Path(d) / "a.mp4"))
            self.assertIsNotNone(r["audio"])
            self.assertEqual(r["audio"]["channels"], 1)
            self.assertEqual(r["audio"]["sample_rate"], 44100)

    def test_missing_file_is_needs_input_not_failed(self):
        r = FG.probe_mp4("不存在的片子.mp4")
        self.assertEqual(r["status"], "needs_input")
        self.assertFalse(r["ok"])

    def test_garbage_is_failed(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.mp4"
            p.write_bytes(b"not an mp4 at all")
            r = FG.probe_mp4(p)
            self.assertEqual(r["status"], "failed")
            self.assertIn("moov", r["detail"])


class TestStoryboardTimeline(unittest.TestCase):
    def test_four_cut_timeline_ok(self):
        r = FG.check_storyboard(_sb(), "E01-01")
        self.assertTrue(r["ok"])
        self.assertEqual(r["cutStarts"], [0, 3.0, 6.0, 10.0])
        self.assertEqual(r["total_seconds"], 15.0)
        self.assertTrue(r["checks_ok"])

    def test_declared_cutstarts_mismatch_is_caught(self):
        r = FG.check_storyboard(_sb(cutStarts=[0, 3, 7, 10]), "E01-01")
        self.assertFalse(r["checks_ok"])
        self.assertIn("cutStarts", [c["name"] for c in r["checks"] if not c["ok"]])

    def test_h3_picture_time_mismatch_is_caught(self):
        sb = _sb()
        sb["episodes"][0]["segments"][0]["h3Prompt"] = (
            "Picture 1 aligns with the 0.00-second mark; "
            "Picture 2 aligns with the 4.00-second mark")
        r = FG.check_storyboard(sb, "E01-01")
        self.assertFalse(r["checks_ok"])
        self.assertIn("h3PictureTimes", [c["name"] for c in r["checks"] if not c["ok"]])

    def test_unknown_segment_is_failed_with_inventory(self):
        r = FG.check_storyboard(_sb(), "E09-99")
        self.assertEqual(r["status"], "failed")
        self.assertIn("E01-01", r["detail"])


class TestSubtitles(unittest.TestCase):
    ASS = ("[Script Info]\nPlayResX: 1080\n\n[Events]\n"
           "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
           "Dialogue: 0,0:00:06.08,0:00:09.17,Default,老周,0,0,0,,上船喽。\n"
           "Dialogue: 0,0:00:10.10,0:00:11.15,Default,胡二爷,0,0,0,,等等二爷我！\n")

    def _write(self, d, body=None):
        p = Path(d) / "s.ass"
        p.write_text(body if body is not None else self.ASS, encoding="utf-8")
        return p

    def test_parses_events(self):
        with tempfile.TemporaryDirectory() as d:
            r = FG.parse_ass(self._write(d))
            self.assertEqual(r["count"], 2)
            self.assertEqual(r["events"][0]["start"], 6.08)
            self.assertEqual(r["events"][1]["end"], 11.15)
            self.assertFalse(r["overlaps"])

    def test_overlap_is_caught(self):
        body = self.ASS + "Dialogue: 0,0:00:08.00,0:00:12.00,Default,甲,0,0,0,,撞上了\n"
        with tempfile.TemporaryDirectory() as d:
            r = FG.parse_ass(self._write(d, body))
            self.assertTrue(r["overlaps"], "8.00 起的那条与 6.08–9.17 重叠，必须报")

    def test_missing_file_is_needs_input(self):
        self.assertEqual(FG.parse_ass("没有.ass")["status"], "needs_input")


class TestVerify(unittest.TestCase):
    def test_full_pass_and_three_state(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            film = _mp4(d / "f.mp4")
            subs = d / "s.ass"
            subs.write_text(TestSubtitles.ASS, encoding="utf-8")
            r = FG.verify(film, subs=subs, storyboard=_sb(), segment="E01-01")
            self.assertTrue(r["ok"], r["failed"])
            names = [c["name"] for c in r["checks"]]
            for n in ("resolution", "fps", "audioTrack", "duration", "subOverlap"):
                self.assertIn(n, names)

    def test_wrong_resolution_fails(self):
        with tempfile.TemporaryDirectory() as d:
            r = FG.verify(_mp4(Path(d) / "f.mp4", w=720, h=1280), storyboard=_sb(),
                          segment="E01-01")
            self.assertFalse(r["ok"])
            self.assertIn("resolution", r["failed"])

    def test_duration_drift_fails(self):
        with tempfile.TemporaryDirectory() as d:
            r = FG.verify(_mp4(Path(d) / "f.mp4", dur=14.0, frames=350),
                          storyboard=_sb(), segment="E01-01")
            self.assertFalse(r["ok"])
            self.assertIn("duration", r["failed"])

    def test_sub_tail_skipped_not_green_when_no_refs(self):
        # 关键口径：没给「每句实测尾端」时，这条**不许**判过，只能 skipped。
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            subs = d / "s.ass"
            subs.write_text(TestSubtitles.ASS, encoding="utf-8")
            r = FG.verify(_mp4(d / "f.mp4"), subs=subs)
            self.assertIn("subTail", r["skipped"])
            self.assertTrue(r["ok"], "跳过不等于不通过")

    def test_sub_tail_judged_when_refs_given(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            subs = d / "s.ass"
            subs.write_text(TestSubtitles.ASS, encoding="utf-8")
            ok = FG.verify(_mp4(d / "f.mp4"), subs=subs,
                           spec={"sub_refs": [9.3, 11.3]})
            bad = FG.verify(_mp4(d / "f.mp4"), subs=subs,
                            spec={"sub_refs": [9.3, 13.0]})
            self.assertTrue(ok["ok"], ok["failed"])
            self.assertIn("subTail", bad["failed"])


class TestDeps(unittest.TestCase):
    """依赖体检必须与自身读数一致：缺的都得列出来，不能缺了还说 ok。"""

    def test_deps_matches_its_own_readings(self):
        d = FG.deps()
        self.assertEqual(set(d["missing"]), {k for k, v in d["have"].items() if not v})
        self.assertEqual(d["ok"], not d["missing"])
        self.assertIn(d["status"], ("ok", "needs_dependency"))


class TestThroughGate(unittest.TestCase):
    """触手真正走的那条路：`api.run_task("media_pipeline", {"op": "verify", ...})`。

    为什么非要过这道门：能力模块能跑 ≠ 能力位调得通。仓里已经有过
    「模块写好了、api 没分支、调一次 unknown capability」的死位账。
    """

    @staticmethod
    def _body(env):
        r = (env or {}).get("result")
        if isinstance(r, dict) and "result" in r and not r.get("verdict"):
            r = r["result"]
        return r or {}

    def test_verify_op_is_wired(self):
        from gbt_allinone import api
        with tempfile.TemporaryDirectory() as d:
            film = _mp4(Path(d) / "f.mp4")
            env = api.run_task("media_pipeline",
                               {"op": "verify", "film": str(film),
                                "storyboard": _sb(), "segment": "E01-01"})
            body = self._body(env)
            self.assertTrue(env.get("ok"), env)
            self.assertTrue(body.get("ok"), body.get("failed"))
            self.assertEqual(body.get("verdict"), "过线")

    def test_verify_without_film_is_needs_input(self):
        from gbt_allinone import api
        body = self._body(api.run_task("media_pipeline", {"op": "verify"}))
        self.assertEqual(body.get("status"), "needs_input")
        self.assertFalse(body.get("ok"))


class TestRealDelivery(unittest.TestCase):
    """仓里真有一条交付成片：15s / 1080×1920 / 25fps / 有音轨 / 3 条字幕。

    它不在产品包时跳过（产品不带 `交付成片/`），在就必过 —— 这条防的是
    「解析器只在自造盒子上成立」。
    """

    def test_dukou_e01_01(self):
        film = _REPO / "交付成片" / "AI漫剧-渡口" / "E01-01-1080x1920.mp4"
        sb = (_REPO / "gbt_allinone" / "skills" / "shuohao" / "novel-storyboard"
              / "examples" / "渡口-storyboard.json")
        if not film.is_file() or not sb.is_file():
            self.skipTest("本 checkout 不带交付成片")
        subs = film.parent / "subs.ass"
        r = FG.verify(film, subs=subs if subs.is_file() else None,
                      storyboard=sb, segment="E01-01")
        self.assertTrue(r["ok"], r["failed"])
        self.assertAlmostEqual(r["readings"]["mp4"]["duration"], 15.0, places=3)
        self.assertEqual(r["readings"]["mp4"]["video"]["width"], 1080.0)


if __name__ == "__main__":
    unittest.main()
