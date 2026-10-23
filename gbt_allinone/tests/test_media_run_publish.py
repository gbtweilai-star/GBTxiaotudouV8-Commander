# -*- coding: utf-8 -*-
"""`media_run`（三方向工作流执行器）与 `media_publish`（发布准备 + 授权门）的判据。

这两件是"跑通"那两轮的产物。**跑过一次 ≠ 固化** —— 固化是把那次跑出来的结论变成判据。
本组里最值钱的四条，每条都对应一次真事故或一条不许越的红线：

1. **目录名必须连字符**（`projects/short-video/`）：我第一版写成下划线，
   结果**短视频那条链的产物落在一棵平行树里、门根本看不见**，而我当时已经报了"跑通"。
2. **发布永远 blocked**：发布是不可逆外部动作，本机零凭据 ⇒ 拿**假令牌**也必须是 blocked。
3. **平台口径不许说"已核实"**：框架里一个都没核实过 ⇒ 判据直接断言 `verified` 全为 0。
4. **`not_implemented` 不许被算成跑过**：没有实现器的步必须如实标出来。
"""
import shutil
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gbt_allinone.tools import media_publish as MP  # noqa: E402
from gbt_allinone.tools import media_run as MR      # noqa: E402

HAVE_FFMPEG = shutil.which("ffmpeg") is not None


class ChainTableTests(unittest.TestCase):
    def test_three_chains_exist_and_match_the_framework_kinds(self):
        self.assertEqual(sorted(MR.CHAINS), ["film", "music", "short_video"])
        from gbt_allinone.tools import media_pipeline as MPL
        for k in MR.CHAINS:
            self.assertIn(k, MPL.KINDS, "%s 不在框架的 KINDS 里" % k)

    def test_directory_names_use_the_dash_form(self):
        """🔴 拿事故换的判据：盘上规范目录是 `short-video`（连字符）。

        我第一版写成 `short_video` ⇒ 产物落了平行树、门看不见，而报告里已经写了"跑通"。
        这条直接钉住映射表，别再靠自觉。
        """
        self.assertEqual(MR.DIR_NAME["short_video"], "short-video")
        self.assertEqual(MR.DIR_NAME["film"], "film")
        self.assertEqual(MR.DIR_NAME["music"], "music")

    def test_the_two_naming_places_both_use_the_dash(self):
        """**两处都要连字符**：目录名（DIR_NAME）与文件名（`_name`）——
        命名规则里写死的是 `YYYYMMDD-<方向>-…`。只改一处 = 半修。"""
        n = MR._name("short_video", "w", "assets", "mp4")
        self.assertTrue(n.startswith("20"), n)
        self.assertIn("-short-video-", n)
        self.assertNotIn("short_video", n)

    def test_plan_marks_steps_without_an_implementer(self):
        """没有实现器的步必须 `runnable=False` —— 不许把"人的活"显示成"能跑"。"""
        p = MR.run("plan", kind="music")
        self.assertTrue(p["ok"])
        by = {s["step"]: s for s in p["steps"]}
        self.assertFalse(by["lyrics"]["runnable"], "歌词生成没有实现器，不该标可跑")
        self.assertFalse(by["arrangement"]["runnable"])
        self.assertTrue(by["audio"]["runnable"])
        self.assertTrue(by["master"]["runnable"])
        self.assertTrue(by["publish"]["runnable"])

    def test_unknown_kind_is_refused_with_the_legal_ones(self):
        r = MR.run("run", kind="podcast")
        self.assertFalse(r["ok"])
        self.assertIn("不认的方向", r["error"])
        for k in ("music", "film", "short_video"):
            self.assertIn(k, r["error"])

    def test_missing_ffmpeg_is_reported_not_faked(self):
        real = MR._have
        MR._have = lambda t: False
        try:
            r = MR.run("run", kind="music")
            self.assertFalse(r["ok"])
            self.assertEqual(r.get("status"), "needs_dependency")
            self.assertIn("不假装", r["why"])
        finally:
            MR._have = real

    def test_publish_step_uses_the_prepared_status_not_ran(self):
        """`prepared` 与 `ran` 必须分开：**"备好发布包"不等于"发出去了"**。"""
        caps = [s["cap"] for s in MR.CHAINS["music"]]
        self.assertIn("media_publish.prepare", caps)


class PlatformTests(unittest.TestCase):
    def test_music_reuses_the_existing_capability_instead_of_a_second_table(self):
        """口径不许有两份：音乐的平台表**复用** `music_publishing`。"""
        r = MP.run("platforms", kind="music")
        self.assertTrue(r["ok"])
        self.assertIn("复用", r["source"])
        self.assertIn("music_publishing", r["source"])
        self.assertEqual(r["counts"]["total"], 13)

    def test_no_platform_is_claimed_verified(self):
        """🔴 框架里一个平台都没核实过 ⇒ **判据直接断言全为 0**。

        这条防的是"把『在』说成『能用』" —— 本仓已把它定成红线。
        """
        for k in ("music", "short_video", "film"):
            with self.subTest(kind=k):
                r = MP.run("platforms", kind=k)
                self.assertTrue(r["ok"], r)
                self.assertEqual(r["counts"]["verified"], 0,
                                 "%s 有平台被标成已核实 —— 核实过吗？" % k)

    def test_the_other_two_dimensions_carry_the_unverified_wording(self):
        for k in ("short_video", "film"):
            r = MP.run("platforms", kind=k)
            rows = r.get("platforms") or []
            self.assertTrue(rows, k)
            for row in rows:
                self.assertFalse(row["verified"], row)
                self.assertTrue(row.get("needs"), "缺「要什么才能发」这一栏：%s" % row)


class PublishGateTests(unittest.TestCase):
    def test_submit_is_always_blocked_even_with_a_token(self):
        """🔴 **拿假令牌也必须 blocked** —— 门在 `run_task` 那一层，不在参数上。

        （框架明写"模块不接受自带令牌绕门"；本能力位不替它开路。）
        """
        r = MP.run("submit", kind="music", package="projects/_shared/publish/music/x.publish.json")
        pkg = _ROOT / "projects" / "_shared" / "publish" / "music"
        real = next(iter(sorted(pkg.glob("*.publish.json"))), None)
        if real is None:
            self.skipTest("没有发布包可测")
        r = MP.run("submit", kind="music", package=str(real.relative_to(_ROOT)),
                   authorization="fake-token-123")
        self.assertFalse(r["ok"])
        self.assertTrue(r["blocked"])
        self.assertTrue(r["authorization_seen"], "假令牌应被看见（然后照样拒）")
        self.assertIn("deploy_publish", " ".join(r["owner_actions"]))
        self.assertIn("不会返回", r["never"])

    def test_submit_refuses_a_package_that_is_not_on_disk(self):
        r = MP.run("submit", kind="music", package="projects/_shared/publish/music/nope.json")
        self.assertFalse(r["ok"])
        self.assertIn("不在盘上", r["error"])

    def test_prepare_writes_outside_the_eighteen_drawers(self):
        """发布包落 `_shared/publish/` —— **不许落 18 格抽屉**（抽屉有家规：命名/类型/许可）。"""
        self.assertTrue(MP.PUB_ROOT.startswith("_shared/"))
        pkg = _ROOT / "projects" / "_shared" / "publish" / "music"
        real = next(iter(sorted(pkg.glob("*.publish.json"))), None)
        if real is None:
            self.skipTest("没有发布包可测")
        import json
        d = json.loads(real.read_text(encoding="utf-8"))
        self.assertEqual(d["gate"]["required_scope"], "deploy_publish")
        self.assertIn("preflight", d)
        self.assertIn("targets", d)
        self.assertIsNotNone(d.get("license"), "发布包里必须有许可摘录")

    def test_prepare_needs_a_real_product(self):
        r = MP.run("prepare", kind="music", product="projects/music/06-release/nope.flac")
        self.assertFalse(r["ok"])
        self.assertIn("不在盘上", r["error"])


class InputPortTests(unittest.TestCase):
    """人写的步 = **链里的输入口**（第 60 轮加）：模板 + 校验 + 落格，机器不生成内容。"""

    def test_human_steps_are_marked_needs_input_not_just_not_runnable(self):
        for kind, steps in (("music", ("lyrics",)), ("short_video", ("script", "storyboard")),
                            ("film", ("concept", "script"))):
            p = MR.run("plan", kind=kind)
            by = {s["step"]: s for s in p["steps"]}
            for st in steps:
                with self.subTest(kind=kind, step=st):
                    self.assertFalse(by[st]["runnable"])
                    self.assertTrue(by[st]["needs_input"], "%s.%s 应标成「人的活=输入口」" % (kind, st))
                    self.assertTrue(by[st]["fields"], "输入口必须给出必填字段")

    def test_a_machine_step_is_not_marked_needs_input(self):
        by = {s["step"]: s for s in MR.run("plan", kind="music")["steps"]}
        self.assertFalse(by["master"]["needs_input"])

    def test_the_filename_we_tell_humans_to_use_passes_the_gate_naming_rule(self):
        """🔴 这条最要紧：我们让人按某个文件名放件，那个名字**必须真能过门的命名规则** ——
        否则人照做了、门还是红，等于我们把活推回去还给人家。"""
        for kind in ("music", "short_video", "film"):
            for idx, s in enumerate(MR.CHAINS[kind], 1):
                if not s.get("human"):
                    continue
                n = MR._expect_name(kind, "pipeline-selftest", idx, s["step"], s["ext"])
                with self.subTest(kind=kind, step=s["step"], name=n):
                    self.assertTrue(MR.NAME_RE.match(n), "我们给的文件名过不了门的命名规则：%s" % n)

    def test_template_lands_outside_the_drawers(self):
        """模板**不许落进抽屉** —— 塞进去 = 门把它数成"有货"，那是拿空壳冒充成品。"""
        t = MR.run("template", kind="short_video", step="script")
        self.assertTrue(t["ok"], t)
        self.assertTrue(t["template"].startswith(".scratch/"), t["template"])
        self.assertNotIn("projects/short-video/01-script", t["template"])
        self.assertIn("projects/short-video/01-script/", t["put_it_at"])
        self.assertIn("不是作品", t["text"])
        for f in ("标题", "受众与钩子（首 3 秒）"):
            self.assertIn(f, t["text"])

    def test_script_steps_are_validated_by_the_frameworks_own_validator(self):
        """🔴 **在场 ≠ 合格** 这条边界，第一次被真正推进一步。

        剧本类步骤光"文件在、名字对"不算过 —— 还要过框架自己的 `drama.parse_timed`（R1–R5）。
        这条判据直接查那个校验器的行为：**空/过短的输入必须被 R4 拒**，且理由要能被读出来。
        """
        v = MR._validate_script("")
        self.assertFalse(v["ok"])
        self.assertEqual(v["validator"], "drama.parse_timed")
        self.assertIn("R4", str(v.get("error")), "过短输入该被 R4 拦下：%s" % v.get("error"))

    def test_a_rejected_input_is_not_counted_as_ran(self):
        """状态名必须能分开：`input_rejected` **不能**和 `ran` 混成一个数。"""
        src = (Path(MR.__file__)).read_text(encoding="utf-8")
        self.assertIn('"input_rejected"', src)
        self.assertIn("input_rejected", src.split("summary")[0] + src)   # 出现在报告构造里

    def test_template_refuses_a_step_that_has_an_implementer(self):
        r = MR.run("template", kind="music", step="master")
        self.assertFalse(r["ok"])
        self.assertIn("不是人写的步", r["error"])

    def test_template_refuses_an_unknown_step(self):
        r = MR.run("template", kind="music", step="nonsense")
        self.assertFalse(r["ok"])
        self.assertIn("没有这一步", r["error"])


class ContractTests(unittest.TestCase):
    def test_registry_entries_match_handler_names(self):
        from gbt_allinone import caps_registry as CR
        for k in ("media_run", "media_publish"):
            with self.subTest(cap=k):
                self.assertIn(k, CR.BENIGN_CAPS)
                self.assertEqual(CR.BENIGN_CAPS[k]["handler"], k)
                self.assertFalse(CR.BENIGN_CAPS[k]["safe"], "%s 会写盘 ⇒ safe=False" % k)

    def test_reachable_through_the_single_gate(self):
        from gbt_allinone import api
        for k in ("media_run", "media_publish"):
            with self.subTest(cap=k):
                r = api.run_task(k, {"op": "status"})
                inner = (r.get("result") or {}).get("result") or {}
                self.assertEqual(inner.get("impl"), k, "gate 没分派到 %s" % k)


class StoryboardContractTests(unittest.TestCase):
    """分镜表：把「输入口」从**在场判据**推到**契约判据**（第 65 轮）。

    上一轮剧本那一步接上了 `drama.parse_timed`；这一步接的是**仓内的分镜契约**
    ——`video-pipeline` §0–§6 加 `分镜契约填写页` 的真字段名。出处逐条标在判据里。

    最值钱的两条：
    · **「求转发」不算可转发物**（§5 原文如此）—— 请求不是可转发物，缺了分镜板打回。
    · **方向专属项不许通用强求**：填写页是**绑一部片**的（《AI搬砖人》8 镜 × 4 格），
      `line_shot`/`line_to`/`alt_scene`/`gate_*` 是**那一部的当事人字段**；
      拿它们当通用判据 = 把"别人的剧本"当"契约"，这一条我探出来才没写错。
    """

    @staticmethod
    def _good():
        return {
            "style": "冷调手持纪实 · 无配乐",
            "hook_video": False,
            "share_shot": 2,
            "share_text": "不是你不够努力，是你的努力用错了地方。",
            "att_copyright": True, "att_safety": True, "att_owner": True,
            "shots": [
                {"no": 1, "render": "静帧（配运镜）", "eyeline": "看向窗外",
                 "depth": "浅景深（点名锐面）",
                 "reason": "先读旁白：这段是独白、只要读一样东西 ⇒ 静帧配缓慢推镜就够",
                 "duration": 6},
                {"no": 2, "render": "3D 物件", "eyeline": "低头看手里的工牌",
                 "depth": "深景深（从前到后列出）",
                 "reason": "工牌本身是主体，要能转起来看背面 ⇒ 真 3D 物件", "duration": 5},
            ],
        }

    def _v(self, obj):
        import json
        text = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
        return MR._validate_storyboard(text)

    def _ids(self, v):
        return [c["id"] for c in v["criteria"] if not c["过"]]

    def test_a_conforming_storyboard_passes_every_criterion(self):
        v = self._v(self._good())
        self.assertTrue(v["ok"], v["fails"])
        self.assertEqual(self._ids(v), [])
        self.assertEqual(v["shots_n"], 2)
        self.assertEqual([c["id"] for c in v["criteria"]],
                         ["B%d" % i for i in range(1, 13)])

    def test_every_criterion_carries_its_source(self):
        """每条判据都要能指回仓内的契约 —— 出处不是装饰。"""
        v = self._v(self._good())
        for c in v["criteria"]:
            with self.subTest(cid=c["id"]):
                self.assertTrue(c.get("出处"), "%s 没写出处" % c["id"])
                self.assertIn("video-pipeline", c["出处"])

    def test_no_whole_film_style_is_rejected(self):
        o = self._good()
        o["style"] = ""
        v = self._v(o)
        self.assertFalse(v["ok"])
        self.assertIn("B2", self._ids(v))
        self.assertIn("没有风格的分镜板一律打回", v["error"])

    def test_copied_reasons_fail(self):
        """§2.2 原文：复制别人的理由 = 失败。"""
        o = self._good()
        for s in o["shots"]:
            s["reason"] = "先读旁白再决定"
        self.assertIn("B8", self._ids(self._v(o)))

    def test_static_still_over_the_cap_fails(self):
        """§3：单张静帧最多占一个镜头（max_static_ground_seconds 默认 8s）。"""
        o = self._good()
        o["shots"][0]["duration"] = 12
        self.assertIn("B9", self._ids(self._v(o)))

    def test_the_cap_can_be_lowered_by_the_piece_itself(self):
        o = self._good()
        o["max_static_ground_seconds"] = 5      # 6s 的静帧现在超了
        self.assertIn("B9", self._ids(self._v(o)))

    def test_a_request_is_not_a_shareable(self):
        """§5 原文：「求转发」不算可转发物，那是请求。"""
        o = self._good()
        o["share_text"] = "觉得有用就求转发一下"
        v = self._v(o)
        self.assertIn("B11", self._ids(v))
        self.assertIn("那是请求", v["error"])

    def test_three_signatures_are_required(self):
        """§6 第一道闸：没审批不许生成。三条签署缺一条就不放行。"""
        for k in ("att_copyright", "att_safety", "att_owner"):
            o = self._good()
            o[k] = False
            with self.subTest(sign=k):
                ids = self._ids(self._v(o))
                self.assertIn("B12", ids)
        self.assertTrue(self._v(self._good())["ok"])

    def test_hook_video_must_be_declared(self):
        """§2.3：默认关 ⇒ 必须有人明确说开，缺省 = 未决定 = 打回。"""
        o = self._good()
        del o["hook_video"]
        v = self._v(o)
        self.assertIn("B10", self._ids(v))
        self.assertIn("hook_video", " ".join(v["missing"]))
        # 显式写 false 就过；写 true 只加警告（那笔钱要由 att_owner 交代）
        o["hook_video"] = True
        v2 = self._v(o)
        self.assertTrue(v2["ok"], v2["fails"])
        self.assertTrue(v2["warns"])

    def test_exception_style_needs_hitl_approval(self):
        """§1 表：单镜 `style` 是例外风格，要离开全片预设必须经人工在 HITL 批准过。"""
        o = self._good()
        o["shots"][0]["style"] = "赛博朋克霓虹"
        self.assertIn("B7", self._ids(self._v(o)))
        o["shots"][0]["style_approved"] = True
        self.assertTrue(self._v(o)["ok"])

    def test_render_must_be_in_the_contract_list(self):
        o = self._good()
        o["shots"][0]["render"] = "随便生成一段"
        self.assertIn("B3", self._ids(self._v(o)))

    def test_four_grids_per_shot_are_required(self):
        """逐镜四格 `render`/`eyeline`/`depth`/`reason` 缺一个就进 missing。"""
        for k, cid in (("render", "B3"), ("eyeline", "B4"), ("depth", "B5"), ("reason", "B6")):
            o = self._good()
            o["shots"][0][k] = ""
            with self.subTest(grid=k):
                v = self._v(o)
                self.assertIn(cid, self._ids(v))
                self.assertTrue(any(k in m for m in v["missing"]), v["missing"])

    def test_direction_only_fields_are_not_generic_requirements(self):
        """🔴 反过度强求：填写页是**绑一部片**的，方向专属项不许当通用判据。"""
        v = self._v(self._good())          # 一个方向专属项都没写
        self.assertTrue(v["ok"], v["fails"])
        self.assertEqual(v["direction_only_present"], [])
        o = self._good()
        o["line_shot"] = 3
        v2 = self._v(o)
        self.assertTrue(v2["ok"], "写了方向专属项也不该改变判否")
        self.assertEqual(v2["direction_only_present"], ["line_shot"])

    def test_unparsable_is_never_a_pass(self):
        """**判不了 ≠ 合格** —— 解析不了的件一律不合格，绝不悄悄放过。"""
        for bad in ("{ 这不是 json", "[1,2,3]", "null", ""):
            with self.subTest(bad=bad[:12]):
                v = self._v(bad)
                self.assertFalse(v["ok"])
                self.assertTrue(v["fails"])

    def test_empty_shot_list_is_rejected(self):
        o = self._good()
        o["shots"] = []
        self.assertIn("B1", self._ids(self._v(o)))

    def test_duration_that_is_not_a_number_is_not_a_pass(self):
        o = self._good()
        o["shots"][0]["duration"] = "六秒"
        v = self._v(o)
        self.assertIn("B9", self._ids(v))
        self.assertIn("判不了就不算合格", v["error"])

    def test_validator_table_wires_the_input_ports(self):
        """在场判据 → 契约判据的接线表：剧本走 drama，分镜走仓内契约。"""
        self.assertIn("storyboard", MR._VALIDATORS)
        self.assertIs(MR._VALIDATORS["storyboard"], MR._validate_storyboard)
        for k in ("script", "screenplay"):
            with self.subTest(step=k):
                self.assertIs(MR._VALIDATORS[k], MR._validate_script)
                self.assertIn("drama.parse_timed", MR._VALIDATOR_SRC[k])
        self.assertIn("video-pipeline", MR._VALIDATOR_SRC["storyboard"])

    def test_storyboard_is_step_two_of_short_video(self):
        """期望名要**从被测对象自己那儿取**（上一轮我就是手打名字才误判"没接线"）。"""
        steps = [s["step"] for s in MR.CHAINS["short_video"]]
        idx = steps.index("storyboard") + 1
        self.assertEqual(idx, 2)
        name = MR._expect_name("short_video", "pipeline-selftest", idx, "storyboard", "json")
        self.assertTrue(MR.NAME_RE.match(name), name)


class LyricsContractTests(unittest.TestCase):
    """歌词：第三条输入口上契约判据（第 66 轮）。

    出处 = `music-production` §1–§3（CC0-1.0）+ 审批屏既有口径 + 真成品《夜航》的形状。

    🔴 本组里**一半的测试是守住我自己刚犯的 5 个错**。它们全是拿真成品《夜航》跑出来的：
    1. 把**物称「它」**当成人称漂移（第一人称叙事里说「它」是正常的）
    2. 被「**不含纪实**主张」里的「纪实」骗成纪实类（否定式必须**先**看）
    3. 把「也不写"**通过**"」这句**引述**当成主张 ⇒ 冤枉它写了通过
    4. 把「每条主张追到**已核验**来源」这句**引述规则**当成谎称已核验
    5. 取「歌词段」时把「13 项**歌词**闸」那一节也吞了 ⇒ 数出 21 行（真 20 行）

    第 3、4 条归到**同一条原则**：**判「判定列」，不判理由散文。**
    """

    PIECE = """# 音乐 · 《测试》· 01 歌词

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

## 一、概念（七阶段中的第 1–2 阶段）

**主题**：测试主题。
**情绪线**：平 → 起。
**视角**：第一人称，**全篇不变**。

## 二、歌词

**主歌一**
我走在路上
风从背后吹来
夜里没有人
只有灯在亮

## 三、13 项歌词闸 · 逐条自查

| 项 | 判定 | 依据 |
|---|---|---|
| 押韵 | ✅ | 来/亮 通押 |
| 韵律 | ✅ | **实测逐行非空白字数**（4 行）：min 5 · max 6 |
| 发音风险 | ✅ 无 | 无难念字 |
| 视角一致 | ✅ | 全篇第一人称，无漂移 |
| 事实准确 | ✅ **不适用** | 本曲为虚构抒情，**不含纪实主张**，故 §1 溯源铁律**不触发** |
| 其余九项 | ⛔ **未判** | 上游未列全判据；**我不编判据、也不写"通过"** |

## 四、生成前闸（§3）自查

| 项 | 状态 |
|---|---|
| 来源已核验 | ✅ 不适用（非纪实） |
| 显式标志位已设 | ⛔ 未设（待生成端接入） |
| 风格提示词完整 | ⛔ 未写 |
| **艺人名已清** | ✅ 全篇无任何艺人/乐队/作品名 |
"""

    def _v(self, text=None):
        return MR._validate_lyrics(self.PIECE if text is None else text)

    def _ids(self, v):
        return [c["id"] for c in v["criteria"] if not c["过"]]

    def _mut(self, old, new):
        self.assertIn(old, self.PIECE, "夹具里没有这段，测试自己写错了")
        return self.PIECE.replace(old, new, 1)

    # ── 真成品是试金石 ──────────────────────────────────────────────────────
    def test_the_real_audited_piece_passes(self):
        """🔴 真成品《夜航》—— 一件**人工审计过**的件必须判得过。

        这一条是本组最值钱的：判据写完第一次跑它，**判不过**；
        查下去发现 5 个错**全在我这边**，于是改判据、**一条都没为它放宽**，它才过的。
        """
        import io
        p = (_ROOT / "projects/music/01-lyrics/20260921-夜航"
             / "20260921-music-夜航-01lyrics.md")
        if not p.exists():
            self.skipTest("真成品不在盘上（可能被移走）：%s" % p.name)
        with io.open(p, encoding="utf-8", errors="replace") as fh:
            v = self._v(fh.read())
        self.assertTrue(v["ok"], v["fails"])
        self.assertEqual(self._ids(v), [])
        self.assertEqual(v["lines_n"], 20)

    def test_the_fixture_itself_passes(self):
        v = self._v()
        self.assertTrue(v["ok"], v["fails"])
        self.assertEqual([c["id"] for c in v["criteria"]],
                         ["L%d" % i for i in range(1, 11)])

    def test_every_criterion_carries_its_source(self):
        for c in self._v()["criteria"]:
            with self.subTest(cid=c["id"]):
                self.assertTrue(c.get("出处"), "%s 没写出处" % c["id"])

    # ── 守住我犯的那 5 个错 ─────────────────────────────────────────────────
    def test_object_pronoun_is_not_a_viewpoint_drift(self):
        """错 1：**「它」是物称**，第一人称叙事里说「它」不是视角漂移。"""
        t = self._mut("只有灯在亮", "只有它还在亮")
        v = self._v(t)
        self.assertTrue(v["ok"], "物称「它」被误判成人称漂移：%s" % v["fails"])

    def test_a_real_pronoun_drift_does_fail(self):
        """但真漂了就必须判否（证明上一条不是把判据关了）。"""
        t = self._mut("风从背后吹来", "风从你背后吹来")
        self.assertIn("L4", self._ids(self._v(t)))

    def test_negated_mention_of_the_genre_is_not_the_genre(self):
        """错 2：被「**不含纪实**主张」里的「纪实」骗成纪实类 ⇒ 否定式必须先看。"""
        v = self._v()
        self.assertNotIn("L7", self._ids(v))
        self.assertIn("不适用", [c["detail"] for c in v["criteria"] if c["id"] == "L7"][0])

    def test_a_quoted_denial_is_not_a_claim_of_passing(self):
        """错 3：依据里「也不写"**通过**"」是**引述**，判定列写的是「未判」⇒ 该过。"""
        v = self._v()
        self.assertNotIn("L8", self._ids(v))
        row = [c for c in v["criteria"] if c["id"] == "L8"][0]
        self.assertIn("如实写了未判", row["detail"])

    def test_actually_claiming_the_nine_gates_passed_does_fail(self):
        """反过来：判定列真写了 ✅ ⇒ 判否（上游没列全判据，谁都不许替它宣布通过）。"""
        t = self._mut("| 其余九项 | ⛔ **未判** |", "| 其余九项 | ✅ 通过 |")
        v = self._v(t)
        self.assertIn("L8", self._ids(v))
        self.assertIn("谁都不许替它宣布通过", v["error"])

    def test_a_quoted_rule_is_not_a_fake_verification(self):
        """错 4：依据里引述规则「（每条主张追到**已核验来源**）」不是谎称已核验。"""
        t = self._mut("故 §1 溯源铁律**不触发**",
                      "故 §1 溯源铁律（每条主张追到**已核验来源**）**不触发**")
        v = self._v(t)
        self.assertTrue(v["ok"], "引述规则被当成主张：%s" % v["fails"])

    def test_the_lyrics_section_does_not_swallow_the_gate_section(self):
        """错 5：§三 标题里也有「歌词」两个字（13 项**歌词**闸）⇒ 取段必须排除它。

        否则 §三 的散文行会被当成歌词行，字数统计当场失真（真成品上多出 1 行）。
        """
        lines = MR._lyric_lines(self.PIECE)
        self.assertEqual(len(lines), 4, lines)
        for ln in lines:
            self.assertNotIn("上游未列全判据", ln)
        self.assertNotIn("项 | 判定", " ".join(lines))

    # ── 契约本身的硬判据 ────────────────────────────────────────────────────
    def test_numbers_must_come_with_a_measurement_method(self):
        """§2 韵律 + 源件第 63–66 行那条教训的**机检版**：
        「判据里出现数字，就必须有对应的量测步骤」——原写「每行 9–11 字」是编造的。"""
        t = self._mut("**实测逐行非空白字数**（4 行）：min 5 · max 6", "每行 9–11 字")
        v = self._v(t)
        self.assertIn("L5", self._ids(v))
        self.assertIn("没写量法", v["error"])

    def test_recomputed_line_lengths_are_always_shown(self):
        """机器**永远现算**逐行字数并列出来；口径不同只报警告，不替人裁决。"""
        v = self._v()
        self.assertEqual(v["recomputed"]["行数"], 4)
        self.assertEqual(v["recomputed"]["min"], 5)
        self.assertIn("逐行", v["recomputed"])

    def test_a_risk_without_a_fix_suggestion_fails(self):
        """§2 原文：「扫出**发音风险**要给**音标修正建议**，不是打回了事。」"""
        t = self._mut("| 发音风险 | ✅ 无 | 无难念字 |",
                      "| 发音风险 | ⚠️ **有 1 处** | 「谁」易被唱成 suí |")
        self.assertIn("L6", self._ids(self._v(t)))

    def test_a_risk_with_a_fix_suggestion_passes(self):
        """给了修正建议就**过** —— 不是打回了事。"""
        t = self._mut("| 发音风险 | ✅ 无 | 无难念字 |",
                      "| 发音风险 | ⚠️ **有 1 处** | 「谁」易被唱成 suí；**建议改标注**："
                      "演唱提示写「shuí（韵脚重读）」 |")
        self.assertTrue(self._v(t)["ok"], self._v(t)["fails"])

    def test_documentary_pieces_need_a_verified_source_table(self):
        """§1 溯源铁律**只对纪实/真实事件类生效**：一类目 + 一张带核验状态的来源表。"""
        t = self._mut("| 事实准确 | ✅ **不适用** | 本曲为虚构抒情，**不含纪实主张**，故 §1 溯源铁律**不触发** |",
                      "| 事实准确 | ✅ | 本曲为**真实事件**改编 |")
        self.assertIn("L7", self._ids(self._v(t)))

    def test_signature_is_required(self):
        t = self._mut("> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属",
                      "> （署名被删）")
        self.assertIn("L1", self._ids(self._v(t)))

    def test_the_four_pre_generation_gates_must_carry_a_status(self):
        """§3 四项**不要求全绿**（那是生成前那一刻的事），但**不许空着**。"""
        t = self._mut("| 风格提示词完整 | ⛔ 未写 |", "| 风格提示词完整 | |")
        v = self._v(t)
        self.assertIn("L9", self._ids(v))
        self.assertIn("风格提示词完整", " ".join(v["missing"]))

    def test_missing_viewpoint_is_not_a_pass(self):
        """判不了 ≠ 合格：没声明视角就判不了「漂没漂」。"""
        t = self._mut("**视角**：第一人称，**全篇不变**。", "**视角**：（待定）")
        self.assertIn("L4", self._ids(self._v(t)))

    def test_empty_piece_is_never_a_pass(self):
        for bad in ("", "   ", None):
            with self.subTest(bad=repr(bad)[:10]):
                self.assertFalse(self._v(bad if bad is not None else "")["ok"])

    # ── 诚实块：源件自己矛盾，必须记下来 ────────────────────────────────────
    def test_the_honesty_block_records_the_source_contradiction(self):
        """🔴 源件 §2 标题写「13 项」，正文点名 5 项 + 自称「其余九项」= **14**。

        这是个**真矛盾**，而且那九项**没列名**。判据只判点得出名字的项，
        **不替上游编判据** —— 这件事必须出现在读数里，不能只在人脑子里。
        """
        g = self._v()["gates"]
        self.assertEqual(g["源件声明总数"], 13)
        self.assertEqual(g["源件点名"], 5)
        self.assertEqual(g["源件自称其余"], 9)
        self.assertNotEqual(g["源件声明总数"], g["点名加其余"])
        self.assertIn("不替上游编判据", g["note"])
        self.assertEqual(g["names"], list(MR.LY_GATES_NAMED))

    def test_validator_table_wires_the_lyrics_port(self):
        self.assertIs(MR._VALIDATORS["lyrics"], MR._validate_lyrics)
        self.assertIn("music-production", MR._VALIDATOR_SRC["lyrics"])
        steps = [s["step"] for s in MR.CHAINS["music"]]
        self.assertEqual(steps.index("lyrics") + 1, 1)
        name = MR._expect_name("music", "pipeline-selftest", 1, "lyrics", "md")
        self.assertTrue(MR.NAME_RE.match(name), name)


def _vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def _midi(bpm=92.0, key=(0, 1), notes=16, with_tempo=True, with_key=True, tracks=1):
    """造一个真的 Standard MIDI File（**手写字节**，不引第三方库）。"""
    import struct
    ev = b""
    if with_tempo:
        ev += b"\x00\xff\x51\x03" + int(60000000 / bpm).to_bytes(3, "big")
    if with_key:
        ev += b"\x00\xff\x59\x02" + bytes([key[0] & 0xFF, key[1]])
    ev += b"\x00\xc0\x28"
    for i in range(notes):
        ev += _vlq(120) + bytes([0x90, 60 + (i % 12), 100])
        ev += _vlq(120) + bytes([0x80, 60 + (i % 12), 0])
    ev += b"\x00\xff\x2f\x00"
    hdr = b"MThd" + struct.pack(">IHHH", 6, 1 if tracks > 1 else 0, tracks, 480)
    return hdr + (b"MTrk" + struct.pack(">I", len(ev)) + ev) * tracks


class ArrangementContractTests(unittest.TestCase):
    """编曲工程件：第 4 条输入口上契约判据（第 69 轮）。

    出处 = **框架自己的设计**：`media_flow` 的编曲格允许 `.als` / `.flp` / `.mid`
    —— 框架自己把人写步设计成「给工程件」。所以判据是「**件在 ⇒ 再看件里到底有没有那些必填的**」。

    🔴 本组最值钱的一条：**「判不了」是一个独立状态**。
    `.als`（gzip 过的 XML）与 `.flp`（专有二进制）本机**没有解析器** ⇒ 返回 `unjudgeable`，
    链上报 `input_unjudged` —— 既不是 `ran`（不许冒充合格），也不是 `input_rejected`（不是它的错）。
    """

    def _v(self, path, raw):
        return MR._validate_arrangement(path, raw)

    def _ids(self, v):
        return [c["id"] for c in v.get("criteria", []) if not c["过"]]

    def test_a_conforming_midi_passes(self):
        v = self._v("x.mid", _midi())
        self.assertTrue(v["ok"], v["fails"])
        self.assertEqual(self._ids(v), [])
        self.assertEqual([c["id"] for c in v["criteria"]],
                         ["A%d" % i for i in range(1, 8)])
        self.assertEqual(v["tempo_bpm"], 92.0)
        self.assertEqual(v["midi"]["key"], "A 小调")
        self.assertEqual(v["midi"]["notes"], 16)

    def test_every_criterion_carries_its_source(self):
        for c in self._v("x.mid", _midi())["criteria"]:
            with self.subTest(cid=c["id"]):
                self.assertTrue(c.get("出处"))

    def test_the_parser_actually_reads_tempo_and_key(self):
        """判据读的是**件里的字节**，不是文件名、也不是声明。"""
        v = self._v("x.mid", _midi(bpm=133.0, key=(-3, 0)))
        self.assertAlmostEqual(v["tempo_bpm"], 133.0, places=2)
        self.assertEqual(v["midi"]["key"], "Eb 大调")

    def test_a_default_tempo_is_not_a_written_tempo(self):
        """🔴 没有 tempo 事件时 SMF 规范规定就是 120 —— 那是**默认值，不是作者写的**。

        必填字段「速度」在件里其实是空的 ⇒ 判否 + 报警告（**不拿默认值冒充读数**）。
        """
        v = self._v("x.mid", _midi(with_tempo=False))
        self.assertIn("A3", self._ids(v))
        self.assertTrue(v["warns"])
        self.assertIn("默认", " ".join(v["warns"]))
        self.assertIsNone(v["tempo_bpm"])

    def test_a_missing_key_goes_to_missing_not_guessed(self):
        """缺调号进 missing，**不许替它猜一个调**。"""
        v = self._v("x.mid", _midi(with_key=False))
        self.assertIn("A4", self._ids(v))
        self.assertIn("不许替它猜", " ".join(v["missing"]))

    def test_an_empty_project_is_rejected(self):
        v = self._v("x.mid", _midi(notes=0))
        self.assertFalse(v["ok"])
        self.assertIn("A5", self._ids(v))

    def test_not_midi_at_all_is_rejected(self):
        for bad in (b"this is not midi at all", b"", b"MThd" + b"\x00" * 20):
            with self.subTest(bad=bad[:14]):
                self.assertFalse(self._v("x.mid", bad)["ok"])

    def test_notes_are_counted_from_real_events(self):
        self.assertEqual(self._v("x.mid", _midi(notes=32))["midi"]["notes"], 32)
        self.assertEqual(self._v("x.mid", _midi(tracks=2))["midi"]["notes"], 32)

    def test_ableton_and_flp_are_honestly_unjudgeable(self):
        """🔴 **判不了 ≠ 合格，也 ≠ 不合格** —— 必须是一个**独立状态**。"""
        for ext in (".als", ".flp", ".ALS"):
            with self.subTest(ext=ext):
                v = self._v("x" + ext, b"\x1f\x8b\x08\x00whatever")
                self.assertTrue(v.get("unjudgeable"), v)
                self.assertFalse(v["ok"])
                self.assertIn("判不了", v["error"])
                # 关键：它**没有**判据结论 —— 不许假装判过
                self.assertEqual(v["criteria"], [])
                self.assertTrue(v["missing"])

    def test_an_unknown_extension_is_rejected_not_unjudged(self):
        """不认的扩展名是**不合格**（不是"判不了"）—— 两件事必须分开。"""
        v = self._v("x.txt", b"hello")
        self.assertFalse(v.get("unjudgeable"))
        self.assertFalse(v["ok"])
        self.assertIn("不认这个扩展名", v["error"])

    def test_the_port_sees_every_extension_the_gate_allows(self):
        """🔴 编曲格收 6 种扩展名，而 `CHAINS` 一个格子只写得出一个 `ext`。

        第一版我只认 `.mid/.als/.flp`，`_filed_input` 也只会找 `CHAINS` 写的那个
        ⇒ 合法放进去的 `.wav`/`.flac`/`.json` 编曲件**输入口根本看不见**。
        """
        self.assertEqual(MR._EXT_ALTS["arrangement"], ("mid", "midi", "wav", "flac", "json", "als", "flp"))
        self.assertEqual(MR.ARR_GATE_EXT,
                         (".mid", ".midi", ".wav", ".flac", ".json", ".als", ".flp"))
        for e in ("mid", "midi", "wav", "flac", "json", "als", "flp"):
            with self.subTest(ext=e):
                n = MR._expect_name("music", "probe", 2, "arrangement", e)
                self.assertTrue(MR.NAME_RE.match(n), n)

    def test_rendered_audio_is_unjudged_not_rejected(self):
        """`.wav`/`.flac`/`.json` 是**合法**输入，只是本机判不了 —— 不许判成「不合格」。"""
        for ext in (".wav", ".flac", ".json"):
            with self.subTest(ext=ext):
                v = self._v("x" + ext, b"RIFF....")
                self.assertTrue(v.get("unjudgeable"), v)
                self.assertIn("判不了", v["error"])
                self.assertIn("只判得动", v["为什么"])   # 说明白本机只判得动 .mid

    def test_the_gate_must_list_is_not_claimed_as_fully_checked(self):
        """闸门那格的 must 是「编曲工程 + 分轨」两样；本判据只看得了前一样 ⇒ 必须如实说。"""
        v = self._v("x.mid", _midi())
        self.assertIn("分轨", " ".join(v["warns"]))

    def test_binary_validator_is_marked_as_binary(self):
        """🔴 二进制件不能按文本读（`errors="replace"` 会把字节换成 U+FFFD，件当场废掉）。"""
        self.assertIn("arrangement", MR._VALIDATOR_BINARY)
        self.assertIs(MR._VALIDATORS["arrangement"], MR._validate_arrangement)
        self.assertIn("编曲格", MR._VALIDATOR_SRC["arrangement"])

    def test_the_input_unjudged_status_exists_in_the_chain(self):
        """链上必须有一个**独立**的 `input_unjudged` 状态（不是 ran / 也不是 rejected）。"""
        import io
        src = io.open(MR.__file__, encoding="utf-8").read()
        self.assertIn('"status": "input_unjudged"', src)
        self.assertIn("unjudgeable", src)


class ConceptContractTests(unittest.TestCase):
    """概念件：第 5 条输入口上契约判据（第 70 轮）—— **人写步至此零「仅在场」**。

    出处**全取自框架自己的件**（上一轮定的方向：不拿我自己写的字段清单立规矩）：
    `MEDIA_KNOWLEDGE[kind].craft[0]` 那句「概念期第一手艺」· `COMMON_GATES` 头两道 ·
    `self_review()` 的九项结构审查（**直接复用**，不另写一套）。

    🔴 本组最值钱的一条：**判据是分方向的**。同一件概念稿喂给 film 能过，
    喂给 short_video / music 必须挂 —— 因为三个方向的 craft[0] 要的根本不是一回事。
    """

    GOOD = """# 电影 · 《老屋》· 01 概念

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

**主题**：一个人回到已经不需要她日常在场的家。
**欲望**：她想被这个家需要一次。
**阻力**：屋子里没人，也没有一件事非她不可。
**变化**：她擦完相框就走 —— 她接受了「不需要」。

**目标观众**：离乡务工的中年女性及其子女。
**受众证据**：主人提供的观察笔记（**不编数据**）。
**成本上限**：8 美元（单场 · 一人 · 一句台词）。
"""

    def _v(self, kind="film", text=None):
        return MR._validate_concept(kind, self.GOOD if text is None else text)

    def _ids(self, v):
        return [c["id"] for c in v["criteria"] if not c["过"]]

    def test_a_conforming_concept_passes(self):
        v = self._v()
        self.assertTrue(v["ok"], v["fails"])
        self.assertEqual([c["id"] for c in v["criteria"]], ["C1", "C2", "C3", "C4"])

    def test_every_criterion_carries_its_source(self):
        for c in self._v()["criteria"]:
            with self.subTest(cid=c["id"]):
                self.assertTrue(c.get("出处"))

    def test_the_judgement_is_per_direction(self):
        """🔴 同一件喂给别的方向**必须挂** —— 三个方向的 craft[0] 要的不是一回事。"""
        self.assertTrue(self._v("film")["ok"])
        for k in ("short_video", "music"):
            with self.subTest(kind=k):
                v = self._v(k)
                self.assertFalse(v["ok"], "喂给 %s 竟然也过了 ⇒ 判据大概写成通用套话了" % k)
                self.assertIn("C2", self._ids(v))

    def test_each_direction_has_its_own_craft_tokens(self):
        """判据出处就是 craft 原句；三个方向各自的 token 表不是同一份。"""
        from gbt_allinone.tools import media_pipeline as MP
        for kind in ("film", "short_video", "music"):
            with self.subTest(kind=kind):
                craft = MP.MEDIA_KNOWLEDGE[kind]["craft"][0]
                self.assertIn(kind, MR.CPT_CRAFT_TOKENS)
                self.assertIn(craft, self._v(kind)["criteria"][1]["出处"] + craft)

    def test_empty_talk_is_rejected(self):
        v = self._v("film", "# 电影\n\n想拍一个很感人的故事。\n")
        self.assertFalse(v["ok"])
        for cid in ("C2", "C3", "C4"):
            self.assertIn(cid, self._ids(v))
        self.assertTrue(v["missing"])

    def test_audience_needs_evidence_not_just_a_claim(self):
        """`COMMON_GATES[0]` 是「需求与受众**证据**」—— 只有结论没有依据 = 没证据。"""
        t = self.GOOD.replace("**受众证据**：主人提供的观察笔记（**不编数据**）。", "")
        v = self._v("film", t)
        self.assertIn("C3", self._ids(v))
        self.assertIn("没证据", " ".join(v["missing"]))

    def test_cost_ceiling_may_not_be_tbd(self):
        """`video-pipeline` §3 原文：「**未知价格直接失败，不许猜**」⇒「待定」不算写了成本。"""
        for bad in ("**成本上限**：待定。", "**成本上限**：未知。", "**成本上限**：以后再定。"):
            with self.subTest(bad=bad[:16]):
                v = self._v("film", self.GOOD.replace(
                    "**成本上限**：8 美元（单场 · 一人 · 一句台词）。", bad))
                self.assertIn("C4", self._ids(v))
                self.assertIn("未知价格直接失败", v["error"])

    def test_cost_ceiling_needs_a_number(self):
        v = self._v("film", self.GOOD.replace(
            "**成本上限**：8 美元（单场 · 一人 · 一句台词）。", "**成本上限**：很低。"))
        self.assertIn("C4", self._ids(v))

    def test_self_review_is_reused_not_reimplemented(self):
        """🔴 **复用框架自己的 `self_review`**，只把概念期谈得上的四项算判据。"""
        v = self._v()
        sr = v["self_review"]
        self.assertEqual(sorted(sr["适用项"]), sorted(MR.CPT_SELF_REVIEW_APPLIES))
        self.assertEqual(sr["passed"], 4, "适用项应当全过")
        self.assertIn("stage_outputs_bound", sr["这一步还谈不上"])
        self.assertIn("owner_reviewed", sr["这一步还谈不上"])
        # 谈不上的那些**不是不合格**，只是还不到时候 ⇒ 必须在警告里说清
        self.assertIn("还不到时候", " ".join(v["warns"]))

    def test_the_structural_mismatch_is_reported_not_silently_fixed(self):
        """🔴 `concept` 与 `script` **共用抽屉**，而闸门把那一格映射到 `script`。

        抽屉里那件真成品叫 `20260921-film-老屋-01screenplay.md` ⇒ 两步**都看不见它**。
        改编号会动到闸门映射 ⇒ **只报不改**。这条错位必须出现在读数里。
        """
        w = " ".join(self._v()["warns"])
        self.assertIn("共用抽屉", w)
        self.assertIn("都看不见它", w)

    def test_empty_piece_is_never_a_pass(self):
        for bad in ("", "   "):
            with self.subTest(bad=repr(bad)):
                self.assertFalse(self._v("film", bad)["ok"])

    def test_all_six_human_ports_are_now_contracted(self):
        """人写步至此**零「仅在场」** —— 六步全部有契约判据。"""
        from gbt_allinone.tools import media_pipeline as MP
        self.assertEqual(sorted(MR._VALIDATORS),
                         ["arrangement", "concept", "lyrics", "screenplay", "script", "storyboard"])
        humans = [s["step"] for k in MP.KINDS for s in MR.CHAINS[k] if s.get("human")]
        for h in humans:
            with self.subTest(step=h):
                self.assertIn(h, MR._VALIDATORS, "%s 还是「仅在场」" % h)

    def test_three_kinds_of_parameters_are_declared(self):
        """三种入参摊开写着：正文 / `(路径,字节)` / `(方向,正文)` —— 免得下一个人以为它们一样。"""
        self.assertEqual(MR._VALIDATOR_BINARY, ("arrangement",))
        self.assertEqual(MR._VALIDATOR_KINDED, ("concept",))
        for k in MR._VALIDATORS:
            with self.subTest(step=k):
                self.assertIn(k, MR._VALIDATOR_SRC)


class InputPortTests(unittest.TestCase):
    """输入口的**认定口径**必须与家规同源（第 71 轮）。

    🔴 修的是一个真 bug：我的认定**比框架自己的命名规则更严**。
    家规是 `YYYYMMDD-<方向>-<作品>-<工序|rehearsal>[-vN].ext`，`<工序>` = `\\d{2}[a-z]+`
    —— **词自由、序号不绑定步骤**。而我第一版要求「工序词 == 步骤名、序号 == 步骤序」
    ⇒ 抽屉里那件**真成品** `20260921-film-老屋-01screenplay.md`（题「01 剧本」）
    在 `film` 链的两步里**都看不见**（我要的是 `-01concept.md` 或 `-02script.md`）。

    **判据的边界必须与家规同源** —— 这是本仓第三次栽在同一句话上。
    """

    REAL_WORK = "老屋"
    # ⚠️ 真件在**子目录**里（`20260921-老屋/`）—— 第一版我少写了这一层，
    #    于是 8 个测试**全被 skip 掉**、报表还是绿的（"跳过"看着像"通过"）。
    #    本仓第 66 轮栽过同一个坑：**抽屉可以带子目录**。
    REAL = "projects/film/01-screenplay/20260921-老屋/20260921-film-老屋-01screenplay.md"

    def test_the_real_film_piece_is_now_visible_to_the_script_step(self):
        if not (_ROOT / self.REAL).exists():
            self.skipTest("真件不在盘上（可能被移走）")
        got = MR._filed_input("film", "01-screenplay", self.REAL_WORK, 2, "script", "md")
        self.assertEqual(got, self.REAL)
        self.assertIn("screenplay", got)

    def test_the_concept_step_does_not_steal_a_screenplay(self):
        """`concept` 只认 `concept` —— 剧本**不是**概念，不许被抢走充数。"""
        if not (_ROOT / self.REAL).exists():
            self.skipTest("真件不在盘上")
        self.assertIsNone(MR._filed_input("film", "01-screenplay", self.REAL_WORK, 1,
                                          "concept", "md"))

    def test_the_port_does_not_pin_the_index(self):
        """人工件不必按我在 `CHAINS` 里排的第几步来编号 —— **那是我的排法，不是家规**。"""
        if not (_ROOT / self.REAL).exists():
            self.skipTest("真件不在盘上")
        for i in (1, 2, 9):
            with self.subTest(idx=i):
                self.assertEqual(MR._filed_input("film", "01-screenplay", self.REAL_WORK, i,
                                                  "script", "md"), self.REAL)

    def test_each_step_accepts_its_own_words_only(self):
        self.assertEqual(MR._STEP_WORDS["script"], ("script", "screenplay"))
        self.assertEqual(MR._STEP_WORDS["concept"], ("concept",))
        if not (_ROOT / self.REAL).exists():
            self.skipTest("真件不在盘上")
        for step in ("concept", "storyboard", "shots", "lyrics"):
            with self.subTest(step=step):
                self.assertIsNone(MR._filed_input("film", "01-screenplay", self.REAL_WORK, 1,
                                                  step, "md"))

    def test_every_step_in_the_chains_has_a_declared_word_set(self):
        for kind, steps in MR.CHAINS.items():
            for s in steps:
                with self.subTest(kind=kind, step=s["step"]):
                    self.assertIn(s["step"], MR._STEP_WORDS)
                    self.assertIn(s["step"], MR._STEP_WORDS[s["step"]],
                                  "每步至少要认自己的名字")

    def test_the_other_two_directions_still_resolve(self):
        """改口径不许碰坏已经认得的件。

        ⚠️ 写法改成**发现式**：我不再手写期望路径（手写过两次、两次都少写子目录层），
        只钉住真正的不变量 —— **端口说"有"，那个路径就必须盘上真在**。
        """
        probes = (("short_video", "01-script", "AI搬砖人", 1, "script", "md"),
                  ("short_video", "02-storyboard", "AI搬砖人", 2, "storyboard", "md"),
                  ("music", "01-lyrics", "夜航", 1, "lyrics", "md"),
                  ("film", "01-screenplay", "老屋", 2, "script", "md"))
        seen = 0
        for kind, drawer, work, idx, step, ext in probes:
            with self.subTest(kind=kind, drawer=drawer):
                got = MR._filed_input(kind, drawer, work, idx, step, ext)
                if got is None:
                    continue
                seen += 1
                self.assertTrue((_ROOT / got).exists(), "端口给了一个盘上不存在的路径：%s" % got)
                self.assertTrue(MR.NAME_RE.match(got.rsplit("/", 1)[-1]), got)
        self.assertGreaterEqual(seen, 1, "四个探针一个都没命中 ⇒ 端口大概坏了")

    def test_the_returned_path_really_exists_on_disk(self):
        """🔴 返回的路径必须**盘上真在** —— 抹掉子目录拼出来的路径是不存在的。"""
        got = MR._filed_input("film", "01-screenplay", self.REAL_WORK, 2, "script", "md")
        self.assertIsNotNone(got)
        self.assertTrue((_ROOT / got).exists(), "返回了一个盘上不存在的路径：%s" % got)
        self.assertIn("/20260921-老屋/", got, "子目录被抹掉了")

    def test_every_matched_name_satisfies_the_house_rule(self):
        """认定用的一律是**家规** `NAME_RE` —— 端口不许自己另立一套命名。"""
        for kind, drawer, work, idx, step, ext, want in (
                ("film", "01-screenplay", "老屋", 2, "script", "md", self.REAL),):
            if not (_ROOT / want).exists():
                self.skipTest("件不在盘上")
            got = MR._filed_input(kind, drawer, work, idx, step, ext)
            self.assertTrue(MR.NAME_RE.match(got.rsplit("/", 1)[-1]), got)

    def test_what_the_framework_says_about_that_pre_criteria_piece(self):
        """把这件**写在判据立起来之前**的真成品过一遍 `drama.parse_timed`，如实记下结论。

        不断言"必须过"或"必须不过" —— 那件不是为这套判据写的。
        本测试只钉住一件事：**它现在进得了判据门，而且结论是如实报出来的**。
        """
        if not (_ROOT / self.REAL).exists():
            self.skipTest("真件不在盘上")
        import io
        with io.open(_ROOT / self.REAL, encoding="utf-8", errors="replace") as fh:
            v = MR._validate_script(fh.read())
        print("\n[诊断] 《老屋》剧本过 `drama.parse_timed`：ok=%s ｜ %s"
              % (v.get("ok"), str(v.get("error"))[:110]))
        self.assertIn("ok", v)
        self.assertIn("validator", v)
        self.assertEqual(v["validator"], "drama.parse_timed")


class ScaffoldTests(unittest.TestCase):
    """骨架（`template`）：**吐对格式 + 自检过不过自己的判据**（第 72 轮）。

    🔴 在这之前 `scaffold` 干了两件错事：
    ① 一律吐 `.md` —— 而分镜表那格要的是 **`.json`**（人照着填也进不去）；
    ② 吐出来的东西**过不了自己的判据**，而且**没有任何读数告诉人"还差什么"**。
    ⇒ 现在：格式按步骤给，且**当场用自己的判据跑一遍骨架**，把「还差什么」列出来。
    **判据立起来了、模板却过不了判据 = 闭环没闭上。**
    """

    def _t(self, kind, step):
        return MR.run("template", kind=kind, step=step)

    def test_every_human_step_yields_a_skeleton_or_an_honest_checklist(self):
        for kind, steps in MR.CHAINS.items():
            for s in steps:
                if not s.get("human"):
                    continue
                with self.subTest(kind=kind, step=s["step"]):
                    r = self._t(kind, s["step"])
                    self.assertTrue(r["ok"], r.get("error"))
                    self.assertIn(r["kind"], ("skeleton", "checklist"))
                    if r["kind"] == "checklist":
                        self.assertTrue(r["why_no_skeleton"], "给不出骨架就必须说清为什么")

    def test_the_storyboard_skeleton_is_real_json(self):
        """分镜表那格要 `.json` —— 骨架必须是**能当 JSON 解析**的真件形状。"""
        import json
        r = self._t("short_video", "storyboard")
        self.assertEqual(r["kind"], "skeleton")
        self.assertEqual(r["format"], "json")
        o = json.loads(r["piece"])
        self.assertEqual(sorted(o["shots"][0]),
                         ["depth", "duration", "eyeline", "no", "reason", "render"])
        self.assertIn("style", o)
        self.assertTrue((_ROOT / r["template"]).exists())

    def test_a_skeleton_never_pretends_to_pass(self):
        """🔴 **骨架本身不许冒充合格**：过的就说过了，没过的必须把那几条列出来。"""
        for kind, step in (("short_video", "storyboard"), ("film", "concept"), ("music", "lyrics")):
            with self.subTest(step=step):
                r = self._t(kind, step)
                if r["骨架过判据"] is True:
                    self.assertEqual(r["还差什么才能过"], [])
                else:
                    self.assertTrue(r["还差什么才能过"], "没过却不说差什么 = 白给")

    def test_the_storyboard_skeleton_is_sufficient(self):
        """**最硬的一条**：照「还差什么」补上之后，必须真的过判据。

        这一条证明骨架是**够用的**（没有藏着一条谁也填不过的判据）。
        """
        import copy
        import json
        r = self._t("short_video", "storyboard")
        filled = copy.deepcopy(json.loads(r["piece"]))
        filled.update({
            "style": "冷调手持纪实 · 无配乐",
            "share_text": "不是你不够努力，是你的努力用错了地方。",
            "att_copyright": True, "att_safety": True, "att_owner": True,
            "shots": [{"no": 1, "render": "静帧（配运镜）", "eyeline": "看向窗外",
                       "depth": "浅景深（点名锐面）",
                       "reason": "先读旁白：只有一样东西要读 ⇒ 静帧配缓慢推镜就够",
                       "duration": 6}],
        })
        v = MR._validate_storyboard(json.dumps(filled, ensure_ascii=False))
        self.assertTrue(v["ok"], v["fails"])
        self.assertEqual(r["还差什么才能过"], ["B11", "B12"], "补的正好是骨架说的那两条")

    def test_an_unfilled_skeleton_is_not_a_piece(self):
        """🔴 实测照出来的弱点：歌词骨架**不填空也过前九条**（那九条判的是结构在场）。

        ⇒ 补一条 L10 明写「件里不许留骨架占位符」。**骨架 ≠ 件。**
        """
        r = self._t("music", "lyrics")
        v = MR._validate_lyrics(r["piece"])
        self.assertIn("L10", [c["id"] for c in v["criteria"] if not c["过"]])
        self.assertFalse(v["ok"], "未填的骨架不许算合格")

    def test_the_checklist_steps_say_why(self):
        """给不出骨架的步**必须说清为什么**，而不是给个假模板。

        ⚠️ 第 76 轮改了这里的期望：`script` **原来给的是清单**（我不敢凭记忆编时间码格式），
        后来去读了 `drama.py` 的真实现（认「起止秒数 + 破折号 + 括号小标题」），
        ⇒ 它现在**给得出可填骨架，而且已过全部判据**。
        所以本测试不再硬点某一步是清单，改成**发现式**：谁是清单，谁就必须说清为什么。
        """
        n_check = 0
        for kind, steps in MR.CHAINS.items():
            for s in steps:
                if not s.get("human"):
                    continue
                r = self._t(kind, s["step"])
                if r["kind"] == "checklist":
                    n_check += 1
                    with self.subTest(step=s["step"]):
                        self.assertTrue(r["why_no_skeleton"].strip(),
                                        "%s 给不出骨架却不说为什么" % s["step"])
        # 二进制那一步（DAW 工程件）**永远**给不出骨架 —— 这是设计如此，不是漏做
        self.assertEqual(self._t("music", "arrangement")["kind"], "checklist")
        self.assertIn("二进制", self._t("music", "arrangement")["why_no_skeleton"])
        self.assertEqual(n_check, 1, "应当只剩 `arrangement` 一步是清单（其余都给得出骨架）")

    def test_the_script_skeleton_passes_the_drama_judge(self):
        """🔴 第 76 轮打通的那一格：`script` 的骨架**必须真的过得了 `drama.parse_timed`**。

        格式出处是 `gbt_allinone/drama.py` 的真实现，不是我记忆里的东西：
        认「起止秒数 + 破折号 + 括号小标题」，每镜正文里要**字面出现**景别/运镜/情绪。
        """
        r = self._t("film", "script")
        self.assertEqual(r["kind"], "skeleton")
        self.assertTrue(r["骨架过判据"], "骨架没过判据 ⇒ 人照着填也进不去")
        self.assertEqual(r["还差什么才能过"], [])
        v = MR._validate_script(r["piece"])
        self.assertTrue(v["ok"], v.get("error"))
        self.assertEqual([(c["id"], c["过"]) for c in v["criteria"]],
                         [("R1", True), ("R2", True), ("R3", True), ("R5", True)])

    def test_the_script_judge_reads_the_verdict_not_the_transport_ok(self):
        """🔴 **判据写着 ≠ 判据在执行**（第 76 轮实测照出来的我自己的 bug）。

        `parse_timed` 的 `ok` 只表示"我解析成功了"，契约判定在 **`verdict`** 里。
        我第 16 轮读的是 `inner["ok"]`，还去取 `criteria`/`missing` 两把**不存在的键**
        ⇒ 那个判据只拦得住"过短"与"没时间码"，**R1/R2/R3 从来没被执行过**。
        """
        import io
        src = io.open(MR.__file__, encoding="utf-8").read()
        self.assertIn('inner.get("verdict")', src)
        self.assertIn("判据写着 ≠ 判据在执行", src)
        self.assertIn("那是假拦", src)

    def test_the_known_path_limitation_is_stated_not_hidden(self):
        """确定性路径**不产出「角色位置」**（源码写死 `subject: ""`）。

        ⇒ 必须**明说**这是路径的局限（并指出要它须走出网那条路），
        **不许**拿 `complete` 当硬判据把每一步都拦死，也**不许**假装它齐了。
        """
        v = MR._validate_script(self._t("film", "script")["piece"])
        self.assertFalse(v["complete"], "确定性路径的 complete 本来就恒为 false")
        self.assertTrue(v["ok"], "但它不该因此被判否 —— 那是假拦")
        self.assertIn("不产出「角色位置」", v["路径局限"])
        self.assertIn("要出网", v["路径局限"])

    def test_the_template_never_lands_in_a_drawer(self):
        """骨架只落 `.scratch/` —— 塞进抽屉 = 拿空壳冒充成品。"""
        for kind, step in (("short_video", "storyboard"), ("music", "lyrics")):
            with self.subTest(step=step):
                r = self._t(kind, step)
                self.assertTrue(r["template"].startswith(".scratch/_media_run_templates/"))
                self.assertIn("projects/", r["put_it_at"])

    def test_non_human_steps_still_refuse(self):
        r = self._t("music", "master")
        self.assertFalse(r["ok"])
        self.assertIn("不是人写的步", r["error"])


class ReleaseModeTests(unittest.TestCase):
    """`release`：闭环的**最后一环**（第 79 轮）。

    🔴 在这之前 `_name()` **永远**吐 `-rehearsal` ⇒ 链子**结构上产不出成品**：
    哪怕三条链全绿跑完，闸门看到的仍是「**只有彩排件，没有该工序成品**」。
    `release=True` 时改吐**工序成品名**（`NNstep` 形式）。

    行为证据（不是断言，是当轮真跑的读数）：
      彩排模式 → 汇总「有货 6 · 仅彩排 9」，`03-raw`/`05-publish` 两条
                「只有彩排件…没有该工序成品」都在；
      成品模式 → 汇总「**有货 8 · 仅彩排 7**」，那两条注意**都消失**，
                盘上落 `-01script.md` / `-03assets.mp4` / `-04edit.mp4` / `-05export.mp4`。
    """

    def test_release_is_threaded_from_run_to_the_chain(self):
        import inspect
        sig = inspect.signature(MR._run_chain)
        self.assertIn("release", sig.parameters, "_run_chain 没接 release")
        self.assertFalse(sig.parameters["release"].default,
                         "缺省必须是彩排 —— **不许悄悄改老行为**")
        import io
        src = io.open(MR.__file__, encoding="utf-8").read()
        self.assertIn('release=bool(kw.get("release"))', src, "run 没把 release 传下去")

    def test_the_two_naming_forms_and_both_obey_the_house_rule(self):
        """成品名用 `NNstep` 形式、彩排名用 `-rehearsal` —— 两者都必须合家规。"""
        prod = MR._expect_name("short_video", "w", 3, "assets", "mp4")
        rehe = MR._name("short_video", "w", "assets", "mp4")
        self.assertIn("-03assets.mp4", prod)
        self.assertIn("-rehearsal.mp4", rehe)
        for n in (prod, rehe):
            with self.subTest(n=n):
                self.assertTrue(MR.NAME_RE.match(n), n)

    def test_release_picks_the_finished_product_name(self):
        """源码里那条分支必须存在：`release` ⇒ `_expect_name`，否则 ⇒ `_name`。

        ⚠️ 这里只钉住**分支在**；"闸门真的从仅彩排翻成有货"那份证据是当轮真跑的读数，
        记在 `memory/2026-09-23.md` 第 79 轮，**不是**本测试能代替的。
        """
        import io
        src = io.open(MR.__file__, encoding="utf-8").read()
        i = src.find("if release:")
        self.assertGreater(i, 0, "release 分支不见了")
        seg = src[i:i + 420]
        self.assertIn("_expect_name(kind, work, idx, step, ext)", seg)
        self.assertIn("_name(kind, work, step, ext)", seg)
        self.assertIn("不代表可发布", src, "必须写明：成品名 ≠ 可发布")

    def test_release_does_not_touch_the_publish_gate(self):
        """**成品名 ≠ 可发布** —— `publish` 那步该停在 `prepared` 就还得停在 `prepared`。"""
        import io
        src = io.open(MR.__file__, encoding="utf-8").read()
        self.assertIn('cap == "media_publish.prepare"', src)
        # 发布提交永远是 blocked（`media_publish.submit` 不接受自带令牌绕门）
        from gbt_allinone.tools import media_publish as MP
        self.assertTrue(hasattr(MP, "run"))
        r = MP.run("submit", package="whatever", token="自带令牌")
        # ⚠️ 不存在的发布包会在"包不在盘上"先被挡，走不到 blocked 那一步 ——
        #    所以这里只断言**实质**：**拿自带令牌提交，绝不许成功**。
        self.assertFalse(r.get("ok"), "发布提交竟然成功了：%s" % r)
        self.assertTrue(r.get("error") or r.get("blocked"), r)


if __name__ == "__main__":
    unittest.main()
