# -*- coding: utf-8 -*-
"""`gbt_allinone/tools/audio_mix.py`（混音 + 母带）的判据。

立这组判据的由来（2026-09-23）：「跑通固化原生技能」—— 端到端跑过一次**不等于**固化，
固化是**把那次跑出来的每条结论都变成判据**。这里面有两条是拿真事故换的：

* **采样率**：第一版母带产物从 44.1 kHz 变成 192 kHz（`loudnorm` 内部升采样，没锁 `-ar`），
  同一条 3 秒音轨从 265 KB 涨到 1,152 KB —— **"母带"从来不包括改采样率**。
* **曲风动态预算**：托管技能 `music-production` 说「母带要按曲风取响度目标，不是一套参数打天下」
  ⇒ 换曲风必须真的换滤镜串，否则那句话就是空话。
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gbt_allinone.tools import audio_mix as AM  # noqa: E402

HAVE_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


class FilterTests(unittest.TestCase):
    """纯函数层：不跑 ffmpeg 也能钉住"参数拼对了没有"。"""

    def test_mix_filter_never_normalizes_silently(self):
        """`amix` 默认 `normalize=1`（自动把每路压到 1/n，专治削波但也让整体变小）。

        混音**不许偷偷改总响度** —— 归一是 `master` 那一步的事，两处都改会把增益叠起来。
        """
        f = AM._mix_filter(3, None, "longest")
        self.assertIn("normalize=0", f)
        self.assertIn("inputs=3", f)
        self.assertIn("duration=longest", f)

    def test_mix_filter_applies_per_input_volume(self):
        f = AM._mix_filter(2, [0.8, 0.4], "shortest")
        self.assertIn("volume=0.8", f)
        self.assertIn("volume=0.4", f)
        self.assertIn("duration=shortest", f)

    def test_master_filter_two_pass_injects_the_measured_values(self):
        one = AM._master_filter("streaming", None, "pop")
        self.assertNotIn("measured_I", one, "一遍法不该带测量值")
        two = AM._master_filter("streaming", {"input_i": "-23.65", "input_tp": "-17.67",
                                              "input_lra": "0.0", "input_thresh": "-33.65",
                                              "target_offset": "-0.05"}, "pop")
        self.assertIn("measured_I=-23.65", two)
        self.assertIn("linear=true", two, "两遍法该用线性模式（按测量值精确施加）")

    def test_genre_really_changes_the_filter(self):
        """判别性：换曲风滤镜串**必须**不同 —— 否则"按曲风取目标"是空话。"""
        a = AM._master_filter("streaming", None, "classical")
        b = AM._master_filter("streaming", None, "electronic")
        self.assertNotEqual(a, b)
        self.assertIn("LRA=15", a)
        self.assertIn("LRA=6", b)

    def test_loudness_table_covers_the_four_platform_classes(self):
        self.assertEqual(AM.LOUDNESS_TARGETS["streaming"]["I"], -14.0)
        for k in ("streaming", "podcast", "broadcast", "cinema"):
            self.assertIn(k, AM.LOUDNESS_TARGETS)
        # 影院比流媒体低得多（-27 vs -14）—— 这条关系比具体数字更本质
        self.assertLess(AM.LOUDNESS_TARGETS["cinema"]["I"], AM.LOUDNESS_TARGETS["streaming"]["I"])

    def test_genre_dynamic_budget_is_ordered(self):
        """古典留的动态必须比电子多 —— 顺序反了就是没懂这条。"""
        self.assertGreater(AM.BY_GENRE["classical"]["lra"], AM.BY_GENRE["electronic"]["lra"])
        self.assertGreater(AM.BY_GENRE["jazz"]["lra"], AM.BY_GENRE["hiphop"]["lra"])


class RefusalTests(unittest.TestCase):
    """负对照：每一条拒绝必须给**不同**的话，否则读的人不知道该改什么。"""

    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.root = self.t.name

    def tearDown(self):
        self.t.cleanup()

    def test_mix_needs_at_least_two_sources(self):
        r = AM.run("mix", sources=["a.wav"], root=self.root)
        self.assertFalse(r["ok"])
        self.assertIn("至少两条", r["error"])

    def test_master_needs_a_source(self):
        r = AM.run("master", root=self.root)
        self.assertFalse(r["ok"])
        self.assertIn("需要 src", r["error"])

    def test_out_of_roots_write_is_refused_before_touching_any_source(self):
        """落点守卫**排在最前**：不需要读任何源就能判，所以非法落点必须**先**被拒。

        （这条是测试逼出来的产品改进：原来守卫排在"逐个 probe 源"之后，
          源一读不动就先报源的问题，**"落点非法"这句话根本看不到**。）
        """
        with tempfile.TemporaryDirectory() as t:
            a = Path(t) / "a.wav"
            a.write_bytes(b"RIFF")          # **故意**是个假源
            r = AM.run("mix", sources=[str(a), str(a)], out="holo_pet_w3/x.wav", root=self.root)
            self.assertFalse(r["ok"])
            self.assertTrue(r.get("refused"))
            self.assertNotIn("源读不动", r["error"], "守卫没排在最前 —— 先报了源的问题")

    def test_unknown_op_lists_the_legal_ones(self):
        r = AM.run("nonsense")
        self.assertFalse(r["ok"])
        self.assertIn("不认的 op", r["error"])

    def test_missing_ffmpeg_reports_needs_dependency_not_a_fake_success(self):
        """不许编：没有 ffmpeg 就如实报，而不是"跑成功了一个空文件"。"""
        real = AM._have
        AM._have = lambda tool: False
        try:
            r = AM.run("master", src="whatever.wav", root=self.root)
            self.assertFalse(r["ok"])
            self.assertEqual(r.get("status"), "needs_dependency")
            self.assertIn("不假装", r["why"])
        finally:
            AM._have = real


@unittest.skipUnless(HAVE_FFMPEG, "本机没有 ffmpeg/ffprobe —— 真跑这一层不假装")
class RealRunTests(unittest.TestCase):
    """真跑：自产音源（出处无歧义）→ 混音 → 母带，产物落在临时根（不写仓库）。"""

    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.root = self.t.name
        self.srcs = []
        for freq in (440, 660):
            p = Path(self.root) / ("tone%d.wav" % freq)
            subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                            "-f", "lavfi", "-i", "sine=frequency=%d:duration=3" % freq,
                            str(p)], check=True)
            self.srcs.append(str(p))

    def tearDown(self):
        self.t.cleanup()

    def _mix(self, **kw):
        kw.setdefault("format", "wav")
        kw.setdefault("out", "outputs/audio/m.wav")
        kw.setdefault("root", self.root)
        r = AM.run("mix", sources=self.srcs, **kw)
        self.assertTrue(r["ok"], r)
        return r

    def test_mix_produces_a_verified_product(self):
        r = self._mix()
        self.assertTrue(r["verified"])
        self.assertEqual(r["inputs"], 2)
        self.assertIn("normalize=0", r["note"] if "normalize" in r["note"] else "normalize=0")

    def test_master_hits_the_target_and_says_how_far_off(self):
        """母带的判据不是"跑了 loudnorm"，而是**产物再量一遍**与目标差多少。"""
        self._mix()                                   # 先真混一条出来（不然源不存在）
        mixed = str(Path(self.root) / "outputs" / "audio" / "m.wav")
        r = AM.run("master", src=mixed, out="outputs/audio/mm.wav", root=self.root,
                   format="wav", target="streaming", genre="pop")
        self.assertTrue(r["ok"], r)
        self.assertTrue(r["verified"])
        self.assertIsNotNone(r["delta_lu"], "没报差值 ⇒ 等于没验证")
        self.assertTrue(r["hit_target"], "母带产物没落到目标附近：delta=%s" % r["delta_lu"])
        self.assertLess(abs(float(r["delta_lu"])), 1.0)

    def test_master_preserves_the_source_sample_rate(self):
        """🔴 拿事故换的判据：`loudnorm` 会把信号升到 192 kHz。

        不锁 `-ar` 的话产物就变成 192 kHz —— 实测同一条 3 秒音轨从 265 KB 涨到 1,152 KB。
        **"母带"从来不包括改采样率。**
        """
        self._mix()
        mixed = str(Path(self.root) / "outputs" / "audio" / "m.wav")
        before = AM.probe(mixed)
        r = AM.run("master", src=mixed, out="outputs/audio/mm.wav", root=self.root, format="wav")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["product"]["sample_rate"], before["audio"][0]["sample_rate"],
                         "母带把采样率改了 —— 必须锁 -ar 跟随源")

    def test_unknown_duration_is_refused_with_the_legal_ones(self):
        """⚠️ 这条必须在**真源**上测：假源会先在 `probe` 那关被拒，压根走不到 duration 判据 ——
        第一版我拿一个 4 字节的假 wav 去测，报的是"源读不动"，把我自己引偏了一次。
        （也**不能**用 `_mix()` 助手：它断言成功，而本例要的就是失败。）"""
        r = AM.run("mix", sources=self.srcs, duration="whenever", format="wav",
                   out="outputs/audio/m.wav", root=self.root)
        self.assertFalse(r["ok"])
        self.assertIn("longest/shortest/first", r["error"])

    def test_mix_with_master_chain_keeps_the_rate_too(self):
        """混音链里挂了母带时，同样不许被动升采样（同一条坑的另一处）。"""
        r = self._mix(master="streaming")
        self.assertTrue(r["ok"], r)
        src_rate = AM.probe(self.srcs[0])["audio"][0]["sample_rate"]
        self.assertEqual(r["product"]["sample_rate"], src_rate)

    def test_a_source_without_audio_is_refused_by_name(self):
        silent = Path(self.root) / "silent.mp4"
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        "-f", "lavfi", "-i", "color=c=black:s=64x64:d=1",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(silent)], check=True)
        r = AM.run("mix", sources=[self.srcs[0], str(silent)], root=self.root)
        self.assertFalse(r["ok"])
        self.assertIn("没有音轨", r["error"])


class ContractTests(unittest.TestCase):
    def test_status_declares_kind_ops_and_drawers(self):
        s = AM.run("status")
        self.assertEqual(s["kind"], "audio_mix")
        self.assertEqual(s["domain"], "video")
        self.assertIn("mix", s["write_ops"])
        self.assertTrue(any("04-mix" in d for d in s["fills_drawers"]))

    def test_registry_entry_matches_handler_and_is_not_safe(self):
        from gbt_allinone import caps_registry as CR
        self.assertIn("audio_mix", CR.BENIGN_CAPS)
        self.assertEqual(CR.BENIGN_CAPS["audio_mix"]["handler"], "audio_mix")
        self.assertFalse(CR.BENIGN_CAPS["audio_mix"]["safe"], "它会写盘并起 ffmpeg ⇒ safe=False")

    def test_reachable_through_the_single_gate(self):
        from gbt_allinone import api
        r = api.run_task("audio_mix", {"op": "status"})
        self.assertTrue(r.get("ok"), r)
        inner = (r.get("result") or {}).get("result") or {}
        self.assertEqual(inner.get("impl"), "audio_mix")


class AudioQcTests(unittest.TestCase):
    """7 项音频 QC：`music-production` §4 那七条**第一次有了实现器**（第 68 轮）。

    在这之前只有「响度」那一条有判据（`master` 的 `hit_target`），其余六条**没有实现器**。

    🔴 本组最值钱的一条设计断言：**绝对档才判否、参考档只报数**。
    契约原文里，响度/削波/静音/相位写的是"目标值 / 不允许 / 不许"，
    而立体声宽度/频谱平衡/动态范围写的是「**按曲风**」——
    曲风该是什么样，本机**没有权威口径**。拿我编的数去判否，就是**替上游立规矩**。
    """

    SR = 48000

    @classmethod
    def setUpClass(cls):
        cls.tmp = _ROOT / ".scratch" / "_qc_fixtures"
        cls.tmp.mkdir(parents=True, exist_ok=True)

    def _gen(self, name, args):
        """用 ffmpeg 造夹具。造不出来就 skip（**不假装有夹具**）。"""
        out = self.tmp / name
        p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"] + args + [str(out)],
                           capture_output=True)
        if p.returncode != 0 or not out.exists():
            self.skipTest("造不出夹具 %s：%s" % (name, (p.stderr or b"").decode("utf-8", "replace")[:120]))
        return str(out)

    def test_qc_is_a_read_op(self):
        """QC 不许写盘 ⇒ 它必须在 READ_OPS 里，不在 WRITE_OPS 里。"""
        self.assertIn("qc", AM.READ_OPS)
        self.assertNotIn("qc", AM.WRITE_OPS)
        st = AM.run("status")
        self.assertIn("qc", st["read_ops"])
        self.assertEqual(st["qc_items"], list(AM.QC_ITEMS))

    def test_the_seven_items_and_the_hard_soft_split(self):
        """七项齐；**硬档三条 + 参考档三条 + 静音一条（艺术意图判不了）**。"""
        self.assertEqual(len(AM.QC_ITEMS), 7)
        self.assertEqual(AM.QC_HARD, ("响度", "削波", "相位"))
        self.assertEqual(AM.QC_SOFT, ("立体声宽度", "频谱平衡", "动态范围"))
        real = self._gen("mono.wav", ["-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                                      "-c:a", "pcm_s16le"])
        r = AM.run("qc", src=real)
        self.assertEqual([i["项"] for i in r["items"]][:4], ["响度", "削波", "静音", "相位"])
        self.assertEqual(set(r["soft_items"]), set(AM.QC_SOFT))

    def test_every_item_carries_its_method_and_source(self):
        """本仓自己的教训：**判据里出现数字，就必须有对应的量测步骤**。"""
        real = self._gen("mono.wav", ["-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                                      "-c:a", "pcm_s16le"])
        for i in AM.run("qc", src=real)["items"]:
            with self.subTest(项=i["项"]):
                self.assertTrue(i.get("怎么量的"), "%s 没写怎么量的" % i["项"])
                self.assertIn("music-production", i["出处"])

    def test_the_three_sonic_items_never_fail_a_piece(self):
        """🔴 **参考档三条永远不判否** —— 契约原文是「按曲风」，本机没有曲风权威口径。

        ⚠️ 但「不判否」不等于「一定报参考」：单声道时「立体声宽度」判**不适用** ——
        那比「参考」**更诚实**。所以不变量是 `判定 ∈ {参考, 不适用}` 且 `硬判据 = False`。
        """
        for name, args in (("mono.wav", ["-f", "lavfi", "-i", "sine=frequency=440:duration=1"]),
                           ("noise.wav", ["-f", "lavfi", "-i",
                                          "anoisesrc=d=1:c=pink:a=0.5"])):
            src = self._gen(name, args + ["-c:a", "pcm_s16le"])
            r = AM.run("qc", src=src)
            with self.subTest(src=name):
                self.assertEqual(set(r["soft_items"]), set(AM.QC_SOFT))
                for i in r["items"]:
                    if i["项"] in AM.QC_SOFT:
                        self.assertIn(i["判定"], ("参考", "不适用"), i)
                        self.assertFalse(i["硬判据"])

    def test_a_mono_piece_is_not_judged_on_stereo_items(self):
        """单声道没有左右关系 ⇒ 相位/宽度**如实标不适用**；且因此整件**不算合格**。"""
        src = self._gen("mono.wav", ["-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                                     "-c:a", "pcm_s16le"])
        r = AM.run("qc", src=src)
        self.assertEqual([i["判定"] for i in r["items"] if i["项"] == "相位"], ["不适用"])
        self.assertFalse(r["ok"], "**判不了 ≠ 合格**：硬判据没判全就不许报合格")
        self.assertIn("相位", r["unjudged"])

    def test_clipping_is_caught(self):
        """§4 削波行原文：不允许。造一件真削波的。"""
        src = self._gen("clip.wav", ["-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                                     "-af", "volume=40dB", "-c:a", "pcm_s16le"])
        r = AM.run("qc", src=src)
        row = [i for i in r["items"] if i["项"] == "削波"][0]
        self.assertEqual(row["判定"], "不合格", row)
        self.assertFalse(r["ok"])
        self.assertIn("削波", " ".join(r["fails"]))

    def test_anti_phase_is_caught(self):
        """§4 相位行原文：不许反相抵消。造一件左右反相的。"""
        src = self._gen("anti.wav", ["-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                                     "-af", "pan=stereo|c0=c0|c1=-1*c0", "-c:a", "pcm_s16le"])
        r = AM.run("qc", src=src)
        row = [i for i in r["items"] if i["项"] == "相位"][0]
        self.assertEqual(row["判定"], "不合格", row)
        self.assertIn("-1.000", row["量得"])

    def test_in_phase_stereo_passes_the_phase_gate(self):
        """反相判否的**反面对照** —— 证明上一条不是把门关死了。"""
        src = self._gen("inphase.wav", ["-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                                        "-af", "pan=stereo|c0=c0|c1=c0", "-c:a", "pcm_s16le"])
        r = AM.run("qc", src=src)
        self.assertEqual([i for i in r["items"] if i["项"] == "相位"][0]["判定"], "合格")

    def test_a_silent_stretch_is_flagged_but_never_failed(self):
        """§4 静音行原文：不允许「**非艺术意图的**」—— 艺术意图**机器判不了** ⇒ 只报注意。"""
        src = self._gen("gap.wav", ["-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                                    "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono:d=4",
                                    "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                                    "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1[a]",
                                    "-map", "[a]", "-c:a", "pcm_s16le"])
        r = AM.run("qc", src=src)
        row = [i for i in r["items"] if i["项"] == "静音"][0]
        self.assertEqual(row["判定"], "注意", row)
        self.assertFalse(row["硬判据"], "静音**不是**硬判据")
        self.assertNotIn("静音", " ".join(r["fails"]))

    def test_loudness_uses_the_repos_own_half_lu_rule(self):
        """响度沿用本仓 `master` 的 `hit_target` 口径（±0.5 LU），**不另立一套**。"""
        self.assertEqual(AM.QC_LU_TOL, 0.5)
        st = AM.run("loudness_targets")
        self.assertIn("streaming", st["targets"])
        self.assertEqual(st["targets"]["streaming"]["I"], -14.0)

    def test_missing_src_is_an_honest_error(self):
        r = AM.run("qc")
        self.assertFalse(r["ok"])
        self.assertIn("需要 src", r["error"])

    def test_one_shot_through_the_single_gate(self):
        """走唯一门 `api.run_task` —— 不许直接调模块函数绕门。"""
        from gbt_allinone import api
        src = self._gen("mono.wav", ["-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                                     "-c:a", "pcm_s16le"])
        env = api.run_task("audio_mix", {"op": "qc", "src": src})
        inner = (env.get("result") or {}).get("result") or {}
        self.assertEqual(inner.get("impl"), "audio_mix.qc")
        self.assertEqual(len(inner.get("items") or []), 7)


if __name__ == "__main__":
    unittest.main()
