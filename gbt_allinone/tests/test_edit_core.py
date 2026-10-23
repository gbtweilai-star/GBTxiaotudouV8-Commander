"""`gbt_allinone/tools/edit_core.py`（剪辑引擎 · 剪映语义蒸馏）的判据（2026-09-23 第 58 轮立）。

═══ 为什么这个能力位必须有判据（而且是**这一套**判据）═══
它不是"登记个名字就完了"的骨架：它会**起 ffmpeg 子进程、写真 mp4**。
而这一轮它自己已经踩出**三个静默失败**，每一个都是"命令 rc=0、看着还行、其实是坏的"：

  ① **素材不够长**：我把 3.0s 的源当 3.5s、1.0s 的源当 2.0s 用 ⇒ 尾段整段消失，
     输出只有 6.5s，而**容器时长照样报 8.5s**、rc=0、一句报错都没有。
     ⇒ 判据：`validate()` 必须用 ffprobe **量**素材长度（`test_it_measures_source_length`）。
  ② **回读只是"照抄"**：`nb_frames=195` 与 `时长 8.5s×30fps=255` 摆在一起就能看出缺尾，
     可当时的 `probe()` 只把两个数抄出来、不让它们互相校验。
     ⇒ 判据：`probe_verdict()` 必须让它们**对账**（`test_probe_verdict_catches_*`）。
  ③ **两个出口各写一份布局**：渲染出口按转场重叠推进（成片 7.8s），剪映草稿出口自己抄了
     "起点 = 声明的 t0"（写 8.3s）⇒ 同一条时间线，两个出口**互相矛盾**。
     ⇒ 判据：`layout()` 是唯一布局，两个出口必须**报同一个总长**
     （`test_both_outlets_agree_on_total_duration`）。

═══ 还有一条不是"静默失败"而是"越权"的：═══
`security/policy.py` 里**没有 `edit_pipeline` 这一条**，而 `evaluate()` 对未知 kind
**没有兜底分支** ⇒ 本能力位在门内是**零作用域 = 不卡**（本仓既有现象，`policy.py` 不许改）。
所以判据必须钉住**自收窄**：写 op 只准落 `projects/` · `outputs/` · `.scratch/`，
往仓外或往包内别处写**一律当场拒绝**（`test_write_guard_*`）。这不是"如果方便就做"，
是把门外那一层缺失补在门内。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from gbt_allinone.tools import edit_core as ec  # noqa: E402


def _mk_clip(path: Path, seconds: float, size: str = "64x64", fps: int = 30) -> Path:
    """造一段**真视频**（判据要的是真文件，不是 mock）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "lavfi", "-i", "color=c=0x203040:s=%s:d=%.2f:r=%d" % (size, seconds, fps),
                    "-pix_fmt", "yuv420p", "-c:v", "libx264", str(path)],
                   capture_output=True, timeout=300)
    return path


def _tl(tmp: Path, **over) -> dict:
    """一条**最小可渲染**的时间线（真素材在 tmp 里现造）。"""
    clip = _mk_clip(tmp / "a.mp4", 1.0)
    tl = {"name": "judge-case", "canvas": {"w": 64, "h": 64, "fps": 30},
          "tracks": {"video": [{"src": str(clip), "t0": 0.0, "dur": 1.0, "src_start": 0.0,
                                "fit": "cover"}]}}
    tl.update(over)
    return tl


class TestCapabilityEntry(unittest.TestCase):
    """能力位入口的形状（固化的最低要求）。"""

    def test_status_reports_what_it_really_is(self):
        r = ec.run("status")
        self.assertTrue(r["ok"])
        self.assertEqual(r["kind"], "edit_pipeline")
        self.assertEqual(r["domain"], "video")
        self.assertEqual(tuple(r["write_roots"]), ec.WRITE_ROOTS)
        self.assertFalse(r["jianying_installed"],
                         "本机没有剪映 ⇒ 这个读数必须是 False（假装装了就是假报）")

    def test_unknown_op_is_not_a_silent_success(self):
        r = ec.run("剪一下")
        self.assertFalse(r["ok"], "未知 op 必须报错，不许静默成功")
        self.assertIn("未知 op", r["error"])

    def test_schema_comes_out_of_the_code_not_the_docs(self):
        r = ec.run("schema")
        self.assertEqual(r["schema"]["unit"], "second")
        self.assertIn("reframe", r["schema"]["tracks"]["video"][0])


class TestTheWriteSurfaceIsNarrowed(unittest.TestCase):
    """门内自收窄（因为 `policy.py` 里没有这一条，而不许改 policy）。"""

    def test_outside_the_repo_is_refused(self):
        g = ec.write_guard(r"C:\Windows\Temp\gbt_judge_x.mp4")
        self.assertFalse(g["ok"], "往仓外写被放过了 ⇒ 自收窄是空话")
        self.assertIn("仓库之外", g["why"])

    def test_inside_but_not_a_write_root_is_refused(self):
        g = ec.write_guard(_ROOT / "gbt_allinone" / "store" / "x.mp4")
        self.assertFalse(g["ok"], "往包内数据面写被放过了")
        self.assertIn("不在允许的写面内", g["why"])

    def test_the_three_declared_roots_are_accepted(self):
        for top in ec.WRITE_ROOTS:
            g = ec.write_guard(_ROOT / top / "_judge_probe.mp4")
            self.assertTrue(g["ok"], "%s 是声明过的写面，却被拒了" % top)

    def test_render_refuses_before_touching_ffmpeg(self):
        r = ec.run("render", timeline=_tl(Path(tempfile.mkdtemp(prefix="gbt_ec_"))),
                   out=r"C:\Windows\Temp\gbt_judge_y.mp4")
        self.assertTrue(r.get("refused"), "越界落点没有被拒：%r" % r)
        self.assertFalse(r["ok"])


class TestItMeasuresInsteadOfTrustingTheJson(unittest.TestCase):
    """① 素材够不够长是**量**出来的。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gbt_ec_"))

    def test_it_measures_source_length(self):
        tl = _tl(self.tmp)
        tl["tracks"]["video"][0]["dur"] = 2.5  # 盘上只有 1.0s
        v = ec.validate(tl)
        self.assertFalse(v["ok"], "素材不够长却被判过 ⇒ 尾段会整段消失（第 58 轮真踩过）")
        self.assertTrue(any("素材不够长" in e for e in v["errors"]), v["errors"])
        self.assertTrue(any("a.mp4" in e for e in v["errors"]), "红了却不说清是谁：%s" % v["errors"])

    def test_exactly_enough_is_accepted(self):
        v = ec.validate(_tl(self.tmp))
        self.assertTrue(v["ok"], v["errors"])

    def test_audio_past_the_end_is_caught(self):
        tl = _tl(self.tmp)
        tl["tracks"]["audio"] = [{"src": str(_mk_clip(self.tmp / "v.mp4", 1.0)),
                                  "t0": 0.8, "dur": 1.0}]
        v = ec.validate(tl)
        self.assertFalse(v["ok"], "音轨越过片尾（话会被切断）却没报")
        self.assertTrue(any("越过片尾" in e for e in v["errors"]), v["errors"])

    def test_canvas_must_be_even(self):
        tl = _tl(self.tmp)
        tl["canvas"] = {"w": 65, "h": 64, "fps": 30}
        self.assertFalse(ec.validate(tl)["ok"], "yuv420p 要求偶数尺寸，奇数必须拦下")

    def test_zoom_out_of_range_is_caught(self):
        tl = _tl(self.tmp)
        tl["tracks"]["video"][0]["reframe"] = {"zoom": 2.6}
        self.assertFalse(ec.validate(tl)["ok"])


class TestTheReadbackAuditsItself(unittest.TestCase):
    """② 回读必须自洽 —— 这一条是**缺尾那次**换来的。"""

    def test_probe_verdict_catches_a_truncated_tail(self):
        bad = {"duration": 8.5, "stream_duration": 6.5,
               "video": {"fps": "30/1", "frames": 195}}
        d = ec.probe_verdict(bad)
        self.assertTrue(any("缺尾" in x for x in d), "视频流比容器短却没报缺尾：%r" % d)
        self.assertTrue(any("帧数" in x for x in d), "195 帧 vs 8.5×30=255 却没报：%r" % d)

    def test_probe_verdict_is_quiet_on_a_healthy_readback(self):
        good = {"duration": 7.8, "stream_duration": 7.8,
                "video": {"fps": "30/1", "frames": 234}}
        self.assertEqual(ec.probe_verdict(good), [])

    def test_probe_verdict_catches_a_video_less_file(self):
        self.assertTrue(any("没有视频流" in x for x in ec.probe_verdict({"video": {}})))

    def test_probe_on_a_real_file_agrees(self):
        tmp = Path(tempfile.mkdtemp(prefix="gbt_ec_"))
        clip = _mk_clip(tmp / "ok.mp4", 1.0)
        p = ec.probe(clip)
        self.assertTrue(p["ok"], p.get("defects"))
        self.assertEqual(p["video"]["frames"], p["video"]["frames_expected"])


class TestTheTwoOutletsAgree(unittest.TestCase):
    """③ 布局只许有一个地方 —— 渲染出口与草稿出口必须报**同一个总长**。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="gbt_ec_"))
        a = _mk_clip(self.tmp / "a.mp4", 1.0)
        b = _mk_clip(self.tmp / "b.mp4", 1.0)
        self.tl = {"name": "outlet-case", "canvas": {"w": 64, "h": 64, "fps": 30},
                   "tracks": {"video": [
                       {"src": str(a), "t0": 0.0, "dur": 1.0},
                       {"src": str(b), "t0": 1.0, "dur": 1.0,
                        "transition_in": {"kind": "fade", "dur": 0.4}}]}}

    def test_layout_is_the_single_source(self):
        lay = ec.layout(self.tl)
        self.assertAlmostEqual(lay["duration"], 1.6, places=3,
                               msg="1.0 + 1.0 - 0.4 转场重叠 = 1.6s")

    def test_both_outlets_agree_on_total_duration(self):
        lay = ec.layout(self.tl)
        d = ec.to_jianying_draft(self.tl, self.tmp / "draft", "case")
        self.assertAlmostEqual(d["duration_s"], round(lay["duration"], 3), places=2,
                               msg="草稿出口与渲染出口报的总长不一致：%s vs %s"
                                   % (d["duration_s"], lay["duration"]))
        self.assertEqual(d["duration_us"], int(round(lay["duration"] * 1e6)),
                         "剪映用微秒 ⇒ 单位换算只许有一个地方")

    def test_the_draft_is_internally_consistent(self):
        """🔴 判据要查**内部自洽**，不只查顶层那个总长。

        由来（第 58 轮变异验证抓到的**判据太弱**）：最初这条只比对顶层 `duration`，
        于是「片段起点回到声明的 t0」这个**原样复发**的变异（6.5 而不是 6.0）照样全绿 ——
        顶层总长没变，只有片段区间之和悄悄变成了 8.3s（= 比成片多 0.5s 的转场重叠）。
        ⇒ 现在逐段比对 `target_timerange.start`，并检查**最大片尾 == 顶层总长**。
        """
        lay = ec.layout(self.tl)
        d = ec.to_jianying_draft(self.tl, self.tmp / "draft3", "case")
        c = json.loads((Path(d["dir"]) / "draft_content.json").read_text(encoding="utf-8"))
        segs = [s for t in c["tracks"] if t["type"] == "video" for s in t["segments"]]
        got = [round(s["target_timerange"]["start"] / 1e6, 3) for s in segs]
        want = [round(L["start"], 3) for L in lay["segments"]]
        self.assertEqual(got, want,
                         "草稿里的片段起点与唯一布局算法对不上：%s vs %s" % (got, want))
        ends = [round((s["target_timerange"]["start"] + s["target_timerange"]["duration"]) / 1e6, 3)
                for s in segs]
        self.assertAlmostEqual(max(ends), round(lay["duration"], 3), places=2,
                               msg="片段区间之和的片尾(%s) 与顶层总长(%s) 对不上"
                                   % (max(ends), lay["duration"]))

    def test_draft_marks_itself_unverified(self):
        d = ec.to_jianying_draft(self.tl, self.tmp / "draft2", "case")
        # 🔴 2026-10-13 更新：加了**结构自检** ⇒ 自标从 `False` 变成 `"structure_only"`。
        #    **但边界没变**：本机没有剪映 ⇒「剪映能不能真打开」**仍未验** —— 这一句必须还在。
        self.assertEqual(d["verified"], "structure_only",
                         "自检过了也只能标 structure_only（剪映打开未验）")
        self.assertTrue(d["selfcheck"]["ok"], d.get("selfcheck"))
        self.assertIn("未验", d["note"])
        self.assertIn("剪映", d["note"], "边界句不许丢：未验的到底是哪一件事要写清")
        names = sorted(p.name for p in (self.tmp / "draft2" / "case").iterdir())
        self.assertEqual(names, ["draft_content.json", "draft_meta_info.json"])
        c = json.loads((self.tmp / "draft2" / "case" / "draft_content.json")
                       .read_text(encoding="utf-8"))
        self.assertEqual(c["new_version"], "110.0.0")
        self.assertEqual(c["version"], 360000)


class TestItPassesItsOwnDistilledRules(unittest.TestCase):
    """引擎生成的命令必须过本仓那套 GBST-ED 硬规则（闭环比"我觉得对"硬）。"""

    def test_generated_command_passes_ed1_and_ed4(self):
        tmp = Path(tempfile.mkdtemp(prefix="gbt_ec_"))
        clip = _mk_clip(tmp / "a.mp4", 1.0, size="128x96")
        tl = {"name": "rules-case", "canvas": {"w": 64, "h": 96, "fps": 30},
              "tracks": {"video": [{"src": str(clip), "dur": 1.0, "fit": "blur"}],
                         "text": [{"text": "判据样片", "t0": 0.1, "dur": 0.5}]}}
        r = ec.run("check", timeline=tl, out=str(tmp / "x.mp4"))
        self.assertTrue(r["ok"], "自家命令没过自家规则：%s" % r.get("findings"))
        self.assertIn("GBT-ED-1", r["passed"], "字幕在 overlay 之后这条应当被真判过")
        self.assertIn("GBT-ED-4", r["passed"], "overlay 前 setpose=STARTPTS 这条应当被真判过")

    def test_graph_mode_explains_why_re_encoding_is_unavoidable(self):
        tmp = Path(tempfile.mkdtemp(prefix="gbt_ec_"))
        clip = _mk_clip(tmp / "a.mp4", 1.0)
        tl = {"canvas": {"w": 64, "h": 64, "fps": 30},
              "tracks": {"video": [{"src": str(clip), "dur": 1.0, "speed": 2.0}]}}
        r = ec.run("check", timeline=tl, out=str(tmp / "x.mp4"))
        self.assertEqual(r["mode"], "graph")
        self.assertTrue(any("变速" in w for w in r["why"]),
                        "重编码的理由必须写出来（不然就成了无理由的违规）：%r" % r["why"])


class TestJianyingDraftStructureOnly(unittest.TestCase):
    """（下面还有两条：失败不留半成品 + 渲前预算闸）"""

    """剪映草稿出口：**结构自检**（2026-10-13 加）。

    🔴 **边界如实**：本机**没装剪映** ⇒ 「剪映能不能真打开这份草稿」**没被验过**。
    本判据只证**结构自洽**（文件在 / JSON 可解析 / canvas·fps·duration 与时间线对得上 /
    时间是整数微秒 / 素材路径逐个在盘），**不许**把它念成"剪映能打开"。
    """

    def test_draft_passes_its_own_selfcheck(self):
        # ⚠️ 落点必须**在仓内**（`projects/`·`outputs/`·`.scratch/`）—— 本能力位的写面是自钉的，
        #    用 `tempfile`（仓外）会被 `write_guard` 当场拒（这也是判据在正常工作）。
        import shutil
        tmp = Path(".scratch") / "edit_core_draft_judge"
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True, exist_ok=True)
        clip = _mk_clip(tmp / "a.mp4", 1.5)
        tl = {"name": "judge-draft", "canvas": {"w": 64, "h": 64, "fps": 30},
              "tracks": {"video": [
                  {"src": str(clip), "t0": 0.0, "dur": 1.0, "src_start": 0.0},
                  {"src": str(clip), "t0": 1.0, "dur": 1.0, "src_start": 0.5,
                   "transition_in": {"kind": "fade", "dur": 0.5}}],
                  "text": [{"text": "甲", "t0": 0.2, "dur": 1.8}]}}
        r = ec.run("draft", timeline=tl, out=str(tmp / "out"), name="judge-draft")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["verified"], "structure_only",
                         "自检过了也只能标 structure_only（剪映打开未验）：%s" % r.get("verified"))
        sc = r["selfcheck"]
        self.assertTrue(sc["ok"], sc)
        self.assertEqual(sc["failed"], [], sc)
        d = Path(r["dir"])
        c = json.loads((d / "draft_content.json").read_text(encoding="utf-8"))
        # 与 **layout 单源**对得上（微秒）—— 这条是真判据，不是"文件在就算过"
        self.assertEqual(c["duration"], int(ec.layout(tl)["duration"] * 1_000_000), c["duration"])
        self.assertEqual(c["fps"], 30.0)
        self.assertEqual(c["canvas_config"]["width"], 64)
        self.assertEqual(len([t for t in c["tracks"] if t["type"] == "video"][0]["segments"]), 2)
        for m in c["materials"]["videos"]:
            self.assertTrue(Path(m["path"]).is_file(), "素材路径写错了：%s" % m["path"])
        self.assertIn("draft_meta_info", "".join(r["files"]))

    def test_selfcheck_really_bites(self):
        """负控：把素材路径改成不存在的 ⇒ 自检必须**报红**（否则这自检就是摆设）。"""
        tmp = Path(tempfile.mkdtemp(prefix="gbt_ec_draft_bad_"))
        tl = {"name": "judge-bad", "canvas": {"w": 64, "h": 64, "fps": 30},
              "tracks": {"video": [{"src": str(tmp / "并不存在.mp4"), "dur": 1.0}]}}
        sc = ec._draft_selfcheck(tmp, tl, {"canvas_config": {"width": 64, "height": 64}, "fps": 30,
                                          "duration": 1_000_000,
                                          "tracks": [{"type": "video", "segments": [
                                              {"target_timerange": {"start": 0, "duration": 1},
                                               "source_timerange": {"start": 0, "duration": 1}}]}],
                                          "materials": {"videos": [{"path": str(tmp / "并不存在.mp4")}]}},
                                {"draft_id": "x", "draft_name": "", "draft_type": ""})
        self.assertFalse(sc["ok"], "素材不在盘却自检通过 ⇒ 自检是摆设：%s" % sc)
        self.assertIn("素材路径逐个在盘", sc["failed"])


class TestFailureLeavesNoFakeArtifact(unittest.TestCase):
    """（下面还有键集正控/负控两条）"""

    """🔴 失败**不许**留一个「能播但短了」的半成品。

    实测事故（2026-10-13）：1080×1920 + blur 那次 ENOMEM，盘上留下一个 **1.767s** 的 mp4
    （片子应是 2.8s）—— 能播、播放器能开，长度却不对，**这正是"假绿"的物证形态**。
    现在的规矩：失败一律把产物挪成 `*.partial`（留现场，但不许冒充成片）。
    """

    def test_encode_failure_quarantines_the_artifact(self):
        import unittest.mock as mk
        tmp = Path(".scratch") / "edit_core_fail_judge"
        (tmp / "_work").mkdir(parents=True, exist_ok=True)
        out = tmp / "fake.mp4"
        out.write_bytes(b"NOT-A-REAL-MP4")          # 假装 ffmpeg 已经留了个半成品
        tl = {"canvas": {"w": 64, "h": 64, "fps": 30},
              "tracks": {"video": [{"src": str(_mk_clip(tmp / "a.mp4", 1.0)), "dur": 1.0}]}}

        class _R:
            returncode = -12
            stderr = "Cannot allocate memory"

        with mk.patch.object(ec.subprocess, "run", return_value=_R()):
            r = ec.render(tl, out, workdir=str(tmp / "_work"))
        self.assertFalse(r["ok"], r)
        # 段名取决于模式：两段拼接走 `copy` ⇒ 失败在 `extract`；单条滤镜图走 `encode`。
        # 不要写死段名（我第一版就写死了，被自己的断言咬）；要的是**失败一律隔离**。
        self.assertIn(r["stage"], ("extract", "encode"), r)
        self.assertIn("ENOMEM", r["why_failed"], r)
        self.assertFalse(out.exists(), "半成品还留在当眼处（会冒充成片）：%s" % out)
        self.assertTrue(str(r["partial"]).endswith(".partial"), r)

    def test_budget_gate_blocks_before_running_ffmpeg(self):
        """渲前预算闸：**没跑** ffmpeg 就先拒（而不是崩在半路留半成品）。"""
        import unittest.mock as mk
        tmp = Path(".scratch") / "edit_core_budget_judge"
        (tmp / "_work").mkdir(parents=True, exist_ok=True)
        out = tmp / "never.mp4"
        tl = {"canvas": {"w": 1080, "h": 1920, "fps": 30},
              "tracks": {"video": [{"src": str(_mk_clip(tmp / "a.mp4", 1.0)), "dur": 1.0}]}}
        with mk.patch.object(ec, "_avail_mb", return_value=300.0), \
                mk.patch.object(ec.subprocess, "run") as run:
            r = ec.render(tl, out, workdir=str(tmp / "_work"))
        self.assertFalse(r["ok"], r)
        self.assertEqual(r["stage"], "budget", r)
        self.assertTrue(r["blocked"], r)
        run.assert_not_called()
        self.assertFalse(out.exists(), "被预算闸拒了却还在盘上留了东西：%s" % out)

    def test_budget_gate_stays_open_when_memory_unreadable(self):
        """拿不到内存读数 ⇒ **不拦**（不许拿"读不到"当"内存不够"）。"""
        import unittest.mock as mk
        tmp = Path(".scratch") / "edit_core_budget_open"
        (tmp / "_work").mkdir(parents=True, exist_ok=True)
        tl = {"canvas": {"w": 64, "h": 64, "fps": 30},
              "tracks": {"video": [{"src": str(_mk_clip(tmp / "a.mp4", 1.0)), "dur": 1.0}]}}
        class _R:
            returncode = 1
            stderr = "stop-here"
        with mk.patch.object(ec, "_avail_mb", return_value=-1.0), \
                mk.patch.object(ec.subprocess, "run", return_value=_R()):
            r = ec.render(tl, tmp / "x.mp4", workdir=str(tmp / "_work"))
        self.assertNotEqual(r.get("stage"), "budget", "读不到内存时不该走预算闸：%s" % r)


class TestDraftKeysCoverExternalTemplate(unittest.TestCase):
    """🔴 **外部尺子**（2026-10-13）：产物顶层键集必须盖住 vendored 的外部模板（28 键）。

    上一轮实测：我们自己手拼的只有 11 键 ⇒ 缺 16 个。现在改成「模板起手 + update 我们算得出的」。
    """

    def test_key_set_covers_the_external_template(self):
        tmp = Path(".scratch") / "edit_core_keys_judge"
        (tmp / "_work").mkdir(parents=True, exist_ok=True)
        clip = _mk_clip(tmp / "a.mp4", 1.5)
        tl = {"name": "judge-keys", "canvas": {"w": 64, "h": 64, "fps": 30},
              "tracks": {"video": [{"src": str(clip), "dur": 1.0}]}}
        d = ec.to_jianying_draft(tl, tmp, "keys")
        self.assertTrue(d["ok"], d)
        c = json.loads((Path(d["dir"]) / "draft_content.json").read_text(encoding="utf-8"))
        tpl = ec._jy_template()
        self.assertTrue(tpl, "vendored 模板不在盘（资产丢了？）")
        miss = sorted(k for k in tpl if k not in c)
        self.assertEqual(miss, [], "产物键集没盖住外部模板：缺 %s" % miss)
        # 我们的算得出键必须**覆盖**模板的默认值（不能被模板冲掉）
        self.assertEqual(c["canvas_config"]["width"], 64)
        self.assertEqual(c["fps"], 30.0)

    def test_selfcheck_bites_when_a_template_key_is_missing(self):
        """负控：故意漏一个模板键 ⇒ 自检必须**报红**（否则那把外部尺子是摆设）。"""
        tpl = ec._jy_template()
        self.assertTrue(tpl, "模板不在盘 ⇒ 这条负控失去对象（不是通过）")
        content = {k: tpl[k] for k in tpl}
        content.update({"canvas_config": {"width": 64, "height": 64},
                        "duration": 1000000, "fps": 30.0, "tracks": [], "materials": {}})
        # ⚠️ 删的必须是**我们不回填**的那个键 —— 第一版删了 `canvas_config`，
        #    而下面 `update` 又把它写回去了 ⇒ 键其实没缺，负控成了空装置（自查抓到）。
        drop = "time_marks"
        self.assertIn(drop, content, "模板里应有 %s（换一个键）" % drop)
        content.pop(drop)
        sc = ec._draft_selfcheck(Path(".scratch"), {"canvas": {"w": 64, "h": 64, "fps": 30}},
                                 content, {"draft_id": "x", "draft_name": "", "draft_type": ""})
        self.assertFalse(sc["ok"], "漏了模板键 %s 却自检通过 ⇒ 外部尺子是摆设：%s" % (drop, sc))
        self.assertTrue(any("外部模板" in f for f in sc["failed"]),
                        "失败清单里应点名外部键集：%s" % sc["failed"])


if __name__ == "__main__":
    unittest.main()
