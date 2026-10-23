# -*- coding: utf-8 -*-
"""`gbt_allinone/tools/audio_extract.py`（从视频取声音 · 本机 ffmpeg）的判据。

立这组判据的由来（Owner 2026-09-23）：「学会这个能力，固化为自己的原生能力接上」。
要固化的**不只是能跑**，而是三件一起：
  ① **格式知识**（容器 ≠ 编解码器 / 有损与无损两族 / 各格式取舍）—— 落成表，可查可测；
  ② **写面自收窄**——policy 对该 kind 零作用域（本仓既有现象），所以必须**自己钉死**；
  ③ **产出即验证**——落盘后 ffprobe 回读产物，不拿"命令返回 0"当"文件好了"。

判据分两层：**纯逻辑**（不碰 ffmpeg，任何时候都能跑）+ **真跑**（没有 ffmpeg 就 skip，
绝不拿"假装跑过"冒充）。两层都要有判别性：正例与负例必须给出**不同**结果。
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gbt_allinone.tools import audio_extract as AE  # noqa: E402

HAVE_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
SAMPLE = _ROOT / "video-out" / "cut-demo.mp4"        # 仓内真件（有音轨）
SILENT = _ROOT / "video-out" / "motion.mp4"          # 仓内真件（**无音轨**，负对照用）


class FormatTableTests(unittest.TestCase):
    """格式表：把"学会的知识"钉成可测的数据，而不是注释里的散文。"""

    def test_every_format_is_complete_and_legal(self):
        for name, f in AE.FORMATS.items():
            with self.subTest(fmt=name):
                for k in ("codec", "kind", "ext", "why", "note", "default_bitrate"):
                    self.assertIn(k, f, "%s 缺字段 %s" % (name, k))
                self.assertIn(f["kind"], ("有损", "无损", "未压缩"), name)
                self.assertTrue(f["ext"].startswith("."), name)

    def test_lossless_formats_have_no_bitrate_and_lossy_ones_do(self):
        """判别性：无损给码率是错的（它没有码率这个概念），有损不给则是漏了默认值。"""
        for name, f in AE.FORMATS.items():
            with self.subTest(fmt=name):
                if f["kind"] in ("无损", "未压缩"):
                    self.assertIsNone(f["default_bitrate"], "%s 是无损，不该有默认码率" % name)
                else:
                    self.assertTrue(f["default_bitrate"], "%s 是有损，必须有默认码率" % name)

    def test_opus_default_bitrate_is_lower_than_aac(self):
        """🔴 实测换来的判据：Opus 是为**低码率**设计的。

        本机同一条 6.35 s 音轨实测：aac@192k = 73 KB，而 opus@192k = **175 KB** ——
        比 aac 大一倍多，**完全违背选它的理由**。⇒ Opus 的默认码率必须比 AAC 低。
        """
        self.assertLess(int(AE.FORMATS["opus"]["default_bitrate"].rstrip("k")),
                        int(AE.FORMATS["aac"]["default_bitrate"].rstrip("k")))

    def test_opus_is_stored_in_ogg_not_in_a_muxer_named_opus(self):
        """🔴 容器 ≠ 编解码器：`.opus` 文件实际装在 **Ogg** 里。

        第一版我按格式名猜 `-f opus`，那是跑不通的（没有叫 opus 的 muxer）。
        """
        self.assertEqual(AE.MUXERS["opus"], "ogg")
        self.assertNotEqual(AE.MUXERS["opus"], "opus")
        self.assertEqual(AE.MUXERS["aac"], "ipod")
        self.assertEqual(AE.MUXERS["m4a"], "ipod")
        self.assertEqual(AE.MUXERS["wma"], "asf")

    def test_the_articles_two_lessons_are_actually_in_the_table(self):
        """学会的两条真东西必须在表里，缺一条就说明"没真学"。

        ① 那篇走查给的是：**拿不准就用 mp3 / 标准质量**（默认值）；
        ② 格式篇给的是：容器 vs codec 不是一回事，且 **AAC 的扩展名是一族**。
        """
        self.assertEqual(AE.DEFAULT_FORMAT, "mp3")
        self.assertTrue(AE.DEFAULT_BITRATE)
        self.assertIn(".m4b", AE.FORMATS["aac"]["note"])          # 扩展名一族
        out = AE.run("formats")
        self.assertIn("容器", out["two_things_not_one"])
        self.assertIn("≠", out["two_things_not_one"])


class WriteGuardTests(unittest.TestCase):
    """写面自收窄：三正三负，两个方向都要给**不同**结果。"""

    def test_allowed_roots_pass(self):
        for rel in ("projects/a.mp3", "outputs/a.mp3", ".scratch/a.mp3"):
            with self.subTest(rel=rel):
                self.assertTrue(AE.write_guard(rel).get("ok"), rel)

    def test_outside_repo_is_refused(self):
        r = AE.write_guard("C:/Windows/Temp/evil.mp3")
        self.assertFalse(r.get("ok"))
        self.assertIn("仓库之外", r["why"])

    def test_repo_but_not_allowed_root_is_refused(self):
        r = AE.write_guard("holo_pet_w3/x.mp3")
        self.assertFalse(r.get("ok"))
        self.assertIn("不在允许的写面内", r["why"])

    def test_the_two_refusals_say_different_things(self):
        """判别性：两种拒绝的理由**必须不同** —— 否则读的人分不清是"越界"还是"树不对"。"""
        a = AE.write_guard("C:/Windows/Temp/evil.mp3")["why"]
        b = AE.write_guard("holo_pet_w3/x.mp3")["why"]
        self.assertNotEqual(a, b)

    def test_root_parameter_lets_tests_use_a_temp_root_without_bypassing_the_rule(self):
        """`root=` 只换"仓库根在哪"，**判据本身照跑** —— 不许测试里绕开它。"""
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(AE.write_guard("outputs/a.mp3", root=d).get("ok"))
            self.assertFalse(AE.write_guard("holo_pet_w3/a.mp3", root=d).get("ok"))


class BuildArgsTests(unittest.TestCase):
    """纯函数层：不跑 ffmpeg 也能钉住"参数拼对了没有"。"""

    def test_video_is_dropped_and_codec_mapped(self):
        cmd = AE._build_args("in.mp4", "out.mp3", "mp3", "192k", 0, None, None, None, False)
        self.assertIn("-vn", cmd)
        self.assertIn("libmp3lame", cmd)
        self.assertIn("192k", cmd)

    def test_lossless_gets_no_bitrate_flag(self):
        cmd = AE._build_args("in.mp4", "out.wav", "wav", "192k", 0, None, None, None, False)
        self.assertNotIn("-b:a", cmd, "无损格式不该出现 -b:a")
        self.assertIn("pcm_s16le", cmd)

    def test_trim_puts_ss_before_input(self):
        """`-ss` 放在 `-i` **之前**才是快速定位（放后面是解码后裁）。判别性：看下标先后。"""
        cmd = AE._build_args("in.mp4", "out.mp3", "mp3", "192k", 0, "1.5", "3", None, False)
        self.assertLess(cmd.index("-ss"), cmd.index("-i"))
        self.assertIn("1.5", cmd)
        self.assertIn("-to", cmd)

    def test_volume_and_normalize_become_filters(self):
        cmd = AE._build_args("in.mp4", "out.mp3", "mp3", "192k", 0, None, None, "1.5", True)
        i = cmd.index("-filter:a")
        chain = cmd[i + 1]
        self.assertIn("volume=1.5", chain)
        self.assertIn("loudnorm", chain)

    def test_track_selection_is_mapped(self):
        cmd = AE._build_args("in.mp4", "out.mp3", "mp3", "192k", 2, None, None, None, False)
        self.assertIn("0:a:2", cmd)


@unittest.skipUnless(HAVE_FFMPEG, "本机没有 ffmpeg/ffprobe —— 真跑这一层不假装")
class RealRunTests(unittest.TestCase):
    """真跑：拿仓内真件走完整条路，**产物落在临时根**（不写仓库）。"""

    def setUp(self):
        if not SAMPLE.is_file():
            self.skipTest("仓内样本 %s 不在" % SAMPLE)

    def test_probe_reads_real_streams(self):
        r = AE.run("probe", src=str(SAMPLE))
        self.assertTrue(r["ok"], r)
        self.assertTrue(r["has_audio"])
        self.assertGreaterEqual(r["audio_count"], 1)
        self.assertTrue(r["audio"][0]["codec"])
        self.assertTrue(float(r["duration_s"]) > 0)

    def test_tracks_lists_what_can_be_extracted(self):
        r = AE.run("tracks", src=str(SAMPLE))
        self.assertTrue(r["ok"], r)
        self.assertEqual(len(r["tracks"]), r["audio_count"])

    def test_extract_produces_a_verified_product_outside_the_repo(self):
        with tempfile.TemporaryDirectory() as d:
            r = AE.run("extract", src=str(SAMPLE), format="mp3",
                       out="outputs/audio/probe.mp3", root=d)
            self.assertTrue(r["ok"], r)
            self.assertTrue(r["verified"], "产出即验证没通过：%s" % r)
            f = Path(d) / "outputs" / "audio" / "probe.mp3"
            self.assertTrue(f.is_file(), "产物没落盘")
            self.assertGreater(f.stat().st_size, 1000)
            # 产物读数必须来自**回读**，且与源对得上（时长近似、采样率相同）
            self.assertEqual(r["product"]["codec"], "mp3")
            self.assertEqual(r["product"]["sample_rate"], r["source_audio"]["sample_rate"])
            self.assertAlmostEqual(float(r["product"]["duration_s"]),
                                   float(AE.run("probe", src=str(SAMPLE))["duration_s"]), places=0)

    def test_silent_video_is_refused_with_the_real_reason(self):
        """负对照：没有音轨的视频 —— 如实说"没有音轨"，**不许**报成功、也不许编一个空文件。"""
        if not SILENT.is_file():
            self.skipTest("负对照样本不在")
        with tempfile.TemporaryDirectory() as d:
            r = AE.run("extract", src=str(SILENT), format="mp3", root=d)
            self.assertFalse(r["ok"])
            self.assertIn("没有音轨", r["error"])
            self.assertFalse((Path(d) / "outputs").exists(), "拒绝了却还是落了盘")

    def test_out_of_roots_write_is_refused_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            r = AE.run("extract", src=str(SAMPLE), out="holo_pet_w3/bad.mp3", root=d)
            self.assertFalse(r["ok"])
            self.assertTrue(r.get("refused"))
            self.assertFalse((Path(d) / "holo_pet_w3").exists())

    def test_unknown_format_is_refused_and_lists_the_known_ones(self):
        r = AE.run("extract", src=str(SAMPLE), format="m4b_typo")
        self.assertFalse(r["ok"])
        self.assertIn("不认的格式", r["error"])
        for k in ("mp3", "wav", "flac"):
            self.assertIn(k, r["error"])


class DispatchShapeTests(unittest.TestCase):
    """登记面契约：这一位要能被 `run_task` 认出来，且返回形状与同族一致。"""

    def test_status_declares_kind_and_ops(self):
        s = AE.run("status")
        self.assertEqual(s["kind"], "audio_extract")
        self.assertEqual(s["domain"], "video")
        self.assertIn("extract", s["write_ops"])
        self.assertIn("probe", s["read_ops"])
        self.assertEqual(tuple(s["write_roots"]), AE.WRITE_ROOTS)

    def test_registry_entry_matches_handler_name(self):
        """`api.py` 按 **cap 名** 分派，`handler` 是元数据 ⇒ 必须写真名（本仓既有判据）。"""
        from gbt_allinone import caps_registry as CR
        self.assertIn("audio_extract", CR.BENIGN_CAPS)
        self.assertEqual(CR.BENIGN_CAPS["audio_extract"]["handler"], "audio_extract")
        self.assertFalse(CR.BENIGN_CAPS["audio_extract"]["safe"],
                         "它会落盘并起 ffmpeg ⇒ safe 必须为 False")

    def test_unknown_op_is_refused_with_the_legal_ones(self):
        r = AE.run("nonsense_op")
        self.assertFalse(r["ok"])
        self.assertIn("不认的 op", r["error"])

    def test_reachable_through_the_single_gate_run_task(self):
        """**唯一门**契约：本能力位必须能经 `api.run_task` 走到，且载荷位置写清楚。

        🔴 为什么单列一条（第 46 轮实测踩到的读数陷阱）：
           `run_task` 的信封是**两层**的 ——
               {"ok":…, "kind":…, "result": {"status":"ok","kind":…,"result": {真正的载荷}}}
           真载荷在 **`result.result`**。我第一版按单层去读（`r["data"]`），
           于是 `audio_count` 读出 `None`，看上去像"能力没接上"，其实是**我读错层**。
           ⇒ 把这条钉住：既证明走得通，也把"载荷在第几层"写进判据里，免得下一个人又读错。
        """
        from gbt_allinone import api
        r = api.run_task("audio_extract", {"op": "status"})
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r.get("kind"), "audio_extract")
        inner = (r.get("result") or {}).get("result") or {}
        self.assertEqual(inner.get("kind"), "audio_extract", "信封第二层里应是本能力位的载荷")
        self.assertIn("extract", inner.get("write_ops") or [])


if __name__ == "__main__":
    unittest.main()
