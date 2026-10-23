# -*- coding: utf-8 -*-
# gbt-capability: media-run
"""三方向自动化工作流执行器（native 能力位 `media_run`）—— **一次调用跑完一条链**。

## 它补的是哪一块

到此为止，三方向的零件是**一个个**通的（`audio_extract` / `audio_mix` / `edit_pipeline` / `voice` …），
但 Owner 要的是「**整套工作流**跑通」：**一次调用，把一条链从头走到尾，每步都落真件**。

## 三条链（步骤名字取自 `media_pipeline.KINDS`，**不另起一套**）

    short_video : script → storyboard → assets → edit → export
    film        : concept → script → shots → sound → edit → export
    music       : lyrics → arrangement → audio → master → export

## 🔴 两条铁律

1. **没有实现器的步骤，绝不许糊过去。** 本执行器对每一步只报三种状态：
   `ran`（真跑了、产物回读验证过）· `manual`（这一步是**人的活**，机器不假装能做）·
   `not_implemented`（本机还没有实现器，并写清**缺什么**）。
   **跑完一遍不等于整条链都通了** —— 报告里会把三种状态分开数。
2. **自产输入**：不给外部素材时，本执行器用**本机 ffmpeg 合成**基础件
   （正弦音轨 / 彩条视频）⇒ 出处无歧义 ⇒ 许可记录可以**如实**写"自有"，
   不用替别人的素材编一个来源。产物一律落在 `projects/<方向>/<格>/`，命名合 `media_flow` 的规则，
   并**同批登记许可**（家规第 2 条：没有许可的素材不许进成品格）。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from .audio_mix import run as amix_run          # noqa: E402
from .audio_extract import write_guard, probe, _have, _run  # noqa: E402  （口径复用，不重写）
from .media_license import run as lic_run        # noqa: E402

_IMPL_VERSION = "1.0"
READ_OPS = ("status", "plan")
WRITE_OPS = ("run",)

# 每条链的每一步：谁来做
#   cap=None 且 human=False ⇒ `not_implemented`（本机没有实现器，写清缺什么）
#   cap=None 且 human=True  ⇒ `awaiting_input`（**这一步是人的活，但它是链里的输入口**：
#        本执行器会去抽屉里找**人填好的真件**；有 ⇒ 这步算过；没有 ⇒ 报「待输入」并给出
#        该放的文件名与字段清单。**模板写进 `.scratch/`，不写进抽屉** ——
#        抽屉里只认人填好的真件，塞一份模板进去 = 拿空壳冒充成品。）
CHAINS = {
    "music": [
        # 字段照仓内契约（第 63 轮改）：出处 = 托管技能 `music-production`（蒸馏自
        # bitwize-music-studio/claude-ai-music-skills · **CC0**）。
        # 它写着：「**歌词里的每一条主张，都要能追到一条已捕获、已核验的来源**」，
        # 外加 **13 项歌词闸**（明列的有：押韵 · 韵律 · 发音风险 · 视角一致 · 事实准确）。
        # ⇒ 所以"溯源"不是可选项，是**歌词这一步的必填**。
        {"step": "lyrics",      "drawer": "01-lyrics",      "ext": "md",  "cap": None, "human": True,
         "why": "歌词是人的活（或模型）—— 本步是**输入口**；闸照 `music-production` §1–§3 判（第 66 轮起过契约判据）",
         "fields": ["标题", "主题/立意", "主歌/副歌分段与结构",
                    "押韵（韵脚方案）", "韵律（字数/拍数是否合乐句）—— **写了数字就必须写清是怎么量的**",
                    "发音风险（难念字/歧义同音）—— 扫出风险要给**音标修正建议**，不是打回了事",
                    "视角一致（人称与叙事视角不许漂）",
                    "事实准确 + **溯源**：**纪实/真实事件类才触发** —— 每条主张追到一条已捕获、已核验的来源；虚构类须**如实标「不适用」**",
                    "其余九项：`music-production` §2 **没列名**（标题写 13 项、正文点名 5 项 + 自称其余九项 = 14，**源件自相矛盾**）—— 逐条自查结论，**不许编名字、不许写「通过」**",
                    "生成前闸（§3）：来源已核验 / 显式标志位已设 / 风格提示词完整 / **艺人名已清**",
                    "署名与出处"]},
        # ⚠️ 编曲也做成**输入口**（第 61 轮）：那格的允许扩展名里写着 `.als/.flp`（Ableton / FL 工程）
        #    与 `.mid` —— **框架自己就是这么设计的：人给工程件**。
        #    ⇒ 标成"未实现"是**读错了这一格**；它本来就该是人的输入口。
        {"step": "arrangement", "drawer": "03-arrange",     "ext": "wav", "cap": None, "human": True,
         "why": "编曲是人的活（DAW/MIDI 工程件）—— 本步是**输入口**",
         "fields": ["调性与速度（BPM）", "和弦进行", "配器清单", "段落结构", "工程文件格式与版本"]},
        {"step": "audio",       "drawer": "04-mix",         "ext": "wav", "cap": "audio_mix.mix"},
        {"step": "master",      "drawer": "05-master",      "ext": "wav", "cap": "audio_mix.master"},
        {"step": "export",      "drawer": "06-release",     "ext": "flac", "cap": "audio_mix.master"},
        {"step": "publish",     "drawer": "_shared/publish", "ext": "json", "cap": "media_publish.prepare"},
    ],
    "short_video": [
        {"step": "script",      "drawer": "01-script",      "ext": "md",  "cap": None, "human": True,
         "why": "剧本/文案是人的活 —— 本步是**输入口**",
         "fields": ["标题", "时长与平台", "受众与钩子（首 3 秒）", "分场/分句", "口播或字幕稿", "署名与出处"]},
        # 字段**照仓内的专业契约**来，不用我自己编的（第 62 轮改）：
        #   出处① `video-pipeline/SKILL.md`（蒸馏自 ttalkkaklab/social-flow · Apache-2.0）：
        #     分镜表四层 + `shot.render`（**必须写选择理由，"复制别人的理由 = 失败"**）·
        #     `shot.style`（例外风格，须 HITL 批准）· `shot.share`（收尾镜头的可转发物；
        #     "求转发"不算可转发物）· `hook_video` 默认**关** · 单张静帧 ≤ `max_static_ground_seconds`（默认 8s）·
        #     同一地点或同一时间发生变化 ⇒ 优先 `dip`。
        #   出处② `projects/_shared/templates/…分镜契约填写页.html`：三条签署（版权已核 / 安全已审 / 主人已批）
        #     —— 与 `media_pipeline.compose` 的 `copyright_attested`/`safety_reviewed`/`owner_reviewed` 一一对应。
        {"step": "storyboard",  "drawer": "02-storyboard",  "ext": "json", "cap": None, "human": True,
         "why": "分镜表由人填（`分镜契约填写页`）—— 本步是**输入口**；字段照 `video-pipeline` 的契约",
         "fields": ["镜头号", "画面（视线 / 景深）", "shot.render 渲染路由 + **选择理由**（抄别人的理由 = 失败）",
                    "时长（单静帧 ≤ max_static_ground_seconds，默认 8s）",
                    "转场（同地点/同时间变化 → 优先 dip）",
                    "shot.share 收尾镜头的可转发物（「求转发」不算）",
                    "shot.style 例外风格（须 HITL 批准，否则留空）",
                    "hook_video（默认关；没有镜头因为「在开头」就值得付钱）",
                    "素材出处与授权", "签署：版权已核 / 安全已审 / 主人已批（HITL#1）"]},
        {"step": "assets",      "drawer": "03-raw",         "ext": "mp4", "cap": "ffmpeg.lavfi"},
        {"step": "edit",        "drawer": "04-cut",         "ext": "mp4", "cap": "edit_pipeline.render"},
        {"step": "export",      "drawer": "05-publish",     "ext": "mp4", "cap": "copy.of_edit"},
        {"step": "publish",     "drawer": "_shared/publish", "ext": "json", "cap": "media_publish.prepare"},
    ],
    "film": [
        {"step": "concept",     "drawer": "01-screenplay",  "ext": "md",  "cap": None, "human": True,
         "why": "概念/立意是人的活 —— 本步是**输入口**",
         "fields": ["片名", "一句话立意（logline）", "类型与时长", "目标观众", "基调与参考片", "署名与出处"]},
        # 字段照 **`drama` 能力位**的契约（第 63 轮改）：它规定**六字段** ——
        # 景别 / 运镜 / 时长 / 情绪 / 角色位置 / 描述 —— 并给出判据
        # R1 六字段齐全 · R2 **缺字段进 missing，不许补默认值** · R3 时长和 = 总时长（±0.05s）·
        # R4 过短输入拒绝 · R5 确定性路径**不调外网**。
        # ⚠️ 该能力位能**校验**这个格式（`parse_timed` 确定性离线；`split` 才补景别/运镜/情绪）。
        #    本执行器下一步就该拿它来**验收人给的稿**，而不是只看"文件在不在"。
        {"step": "script",      "drawer": "01-screenplay",  "ext": "md",  "cap": None, "human": True,
         "why": "剧本是人的活（`drama` 能力位能**解析与校验**剧本，但不生成剧本）—— 本步是**输入口**",
         "fields": ["场次", "场景（时间/地点）", "人物", "动作", "对白", "转场",
                    "**定时六字段**（`drama` 契约）：景别 / 运镜 / 时长 / 情绪 / 角色位置 / 描述",
                    "时长总和须等于总时长（±0.05s）；缺字段**留空**，不许拿默认值顶上"]},
        # ⚠️ 落到 **03-shoot**（该格收 .png/.jpg/.mp4/.mov/.wav/.glb），
        #    不是 02-storyboard（那格只收 .md/.json/.csv，是**分镜表**的位置）。
        #    第一版我写到 02-storyboard ⇒ 门当场报 P2「放了不属于该格的类型」。
        {"step": "shots",       "drawer": "03-shoot",       "ext": "mp4", "cap": "ffmpeg.lavfi"},
        {"step": "sound",       "drawer": "04-assets",      "ext": "wav", "cap": "audio_mix.mix"},
        {"step": "edit",        "drawer": "05-edit",        "ext": "mp4", "cap": "edit_pipeline.render"},
        {"step": "export",      "drawer": "06-final",       "ext": "mp4", "cap": "copy.of_edit"},
        {"step": "publish",     "drawer": "_shared/publish", "ext": "json", "cap": "media_publish.prepare"},
    ],
}
KIND_CN = {"short_video": "短视频", "film": "AI电影", "music": "AI音乐"}

# 🔴 **盘上的目录名用连字符**（第 55 轮真跑抓到的自己一个 bug）：
#    `media_flow` 读的是 `projects/short-video/`（连字符），而我第一版按 CHAINS 的键
#    写成了 `projects/short_video/`（下划线）⇒ **短视频那条链的产物落在了一棵平行树里，
#    门根本看不见**（门自己报 `汇总：有货 6 · 仅彩排 6 · 空 6`，我的件一个都没进去）。
#    文件名里的方向词也必须是连字符（命名规则 `YYYYMMDD-<方向>-…` 写死的是它）——
#    两处都要连字符，别只改一处。
DIR_NAME = {"short_video": "short-video", "film": "film", "music": "music"}

# 自产基础件落 `.scratch/`，**不落抽屉树**（第一版落在 `projects/<方向>/_selftest_stems/`，
# 那是往有家规的地方塞东西 —— 抽屉树里不该出现我自己的中间件）。
STEM_DIR = _ROOT / ".scratch" / "_media_run_stems"


def _name(kind: str, work: str, step: str, ext: str) -> str:
    """合 `media_flow` 的命名规则：`YYYYMMDD-<方向>-<作品>-<工序|rehearsal>[-vN].ext`。

    ⚠️ 方向词用**连字符**那三个（`short-video`），不是目录名（`short_video`）—— 规则里写死的是前者。
    """
    dash = kind.replace("_", "-")
    return "%s-%s-%s-rehearsal.%s" % (time.strftime("%Y%m%d"), dash, work, ext)


# ── 人写的步：**输入口**（2026-09-23 第 60 轮）────────────────────────────────
# 设计要点（三条，都是为了不踩假绿）：
#   ① 模板写进 `.scratch/_media_run_templates/`，**绝不写进抽屉** ——
#      抽屉里塞一份模板，门就会把它数成"有货"，那是拿空壳冒充成品；
#   ② 抽屉里只认**命名合规的真件**（`\d{8}-<方向>-<作品>-<NN工序>.ext` 或 `-rehearsal`）⇒
#      "人填好了"这件事有个客观判据，不靠我说；
#   ③ 没有真件时状态是 **`awaiting_input`**（不是 `ran`、也不是 `not_implemented`）——
#      三种状态分开，读的人才知道这一步到底卡在谁身上。
TEMPLATE_DIR = _ROOT / ".scratch" / "_media_run_templates"
NAME_RE = re.compile(
    r"^\d{8}-(?:short-video|film|music)-.+-(?:\d{2}[a-z]+|rehearsal)(?:-v\d+)?\.[A-Za-z0-9]+$")

# 一格可以收**多种**扩展名（闸门那一格自己就是这么写的）。
# 🔴 编曲格 `03-arrange` 收 `[".mid",".wav",".flac",".json",".als",".flp"]`，
#    而 `CHAINS` 里那一格只能写一个 `ext` ⇒ 输入口会**只找那一个**，
#    放进去的 `.als`/`.wav` 就"看不见"（本仓第 N 次"看着没接线，其实是没找对"）。
#    ⇒ 多扩展名的格子必须在这里列全，**清单与闸门同源**。
_EXT_ALTS = {"arrangement": ("mid", "midi", "wav", "flac", "json", "als", "flp")}


# 🔴 工序词与序号**都不许由我锁死**（第 71 轮）：
#   框架自己的命名规则是 `YYYYMMDD-<方向>-<作品>-<工序|rehearsal>[-vN].ext`，
#   其中 `<工序>` = `\d{2}[a-z]+` —— **词是自由的**，序号也不绑定到某一步。
#   而我第一版要求「工序词 == 步骤名、序号 == 步骤序」⇒ 比家规更严 ⇒
#   抽屉里那件**真成品** `20260921-film-老屋-01screenplay.md`（题「01 剧本」）
#   在 `film` 链的两步里**都看不见**（我要的是 `-01concept.md` 或 `-02script.md`）。
#   ⇒ 放开成：**每步认一组工序词**，序号任意。**判据的边界必须与家规同源。**
_STEP_WORDS = {"script": ("script", "screenplay"), "screenplay": ("script", "screenplay"),
               "storyboard": ("storyboard",), "concept": ("concept",),
               "lyrics": ("lyrics",), "arrangement": ("arrangement",),
               "shots": ("shots",), "sound": ("sound",), "edit": ("edit",),
               "export": ("export",), "assets": ("assets",), "audio": ("audio",),
               "master": ("master",), "publish": ("publish",)}


def _expect_name(kind: str, work: str, idx: int, step: str, ext: str) -> str:
    """人该放进去的文件名（工序编号形式，非彩排）。"""
    return "%s-%s-%s-%02d%s.%s" % (time.strftime("%Y%m%d"), kind.replace("_", "-"), work, idx, step, ext)


def _filed_input(kind: str, drawer: str, work: str, idx: int, step: str, ext: str):
    """抽屉里有没有**人填好的真件**。有 ⇒ 返回它的仓内相对路径；没有 ⇒ None。

    ⚠️ 认定用的是**家规**（`NAME_RE`）+ 每步的**工序词别名**，**不锁序号**：
    人写的件不必按我在 `CHAINS` 里排的第几步来编号 —— 那是我的排法，不是家规。
    """
    d = _ROOT / "projects" / DIR_NAME.get(kind, kind) / drawer
    if not d.is_dir():
        return None
    exts = _EXT_ALTS.get(step, (ext,))
    words = _STEP_WORDS.get(step, (step,))
    dash, w = kind.replace("_", "-"), re.escape(work)
    e_alt, w_alt = "|".join(re.escape(x) for x in exts), "|".join(re.escape(x) for x in words)
    proc = re.compile(r"^\d{8}-%s-%s-\d{2}(?:%s)\.(?:%s)$" % (re.escape(dash), w, w_alt, e_alt))
    rehe = re.compile(r"^\d{8}-%s-%s-rehearsal(?:-v\d+)?\.(?:%s)$"
                      % (re.escape(dash), w, e_alt))
    for p in sorted(d.rglob("*")):
        if not p.is_file() or p.name.startswith(("_", ".")):
            continue
        if (proc.match(p.name) or rehe.match(p.name)) and NAME_RE.match(p.name):
            # 🔴 必须返回**真相对路径**（含子目录）—— 第一版我用
            #    `projects/<方向>/<格>/<文件名>` 拼，**把子目录抹掉了**：
            #    盘上真件在 `01-screenplay/20260921-老屋/` 里，拼出来的路径**不存在**，
            #    调用方 `_ROOT / got` 当场读不到 ⇒ 就算"看得见"也会报「读不动这个文件」。
            #    测试抓到的（`test_the_port_does_not_pin_the_index`）。
            return p.relative_to(_ROOT).as_posix()
    return None


def _validate_script(text: str) -> dict:
    """拿**框架自己的校验器**验收人给的稿：`drama.parse_timed`（确定性 · 离线 · R1–R5）。

    🔴 这是把输入口从「**在场**判据」推到「**契约**判据」的那一步：
    以前只要文件名对、文件在，这步就算过；现在还要过一遍 `drama` 的判据
    （R1 六字段齐全 · R2 缺字段进 missing 不许补默认值 · R3 时长和=总时长 ±0.05s ·
      R4 过短输入拒绝 · R5 确定性路径不调外网）。
    ⚠️ 它吃的是**正文**，不是路径 —— 实测传 `path` 会被当成空输入直接 R4。
    """
    try:
        from .. import api as _api
        r = _api.run_task("drama", {"op": "parse_timed", "text": text})
        inner = (r.get("result") or {}).get("result") or {}
        v = inner.get("verdict") or {}
        shots = inner.get("shots") or []
        # 🔴 **`parse_timed` 的 `ok` 只表示"我解析成功了"，契约判定在 `verdict` 里**
        #    （第 76 轮实测照出来的：我第 16 轮读的是 `inner["ok"]`，还去取 `criteria`/`missing`
        #     这两把**根本不存在的键** ⇒ 那个判据只拦得住"过短"与"没时间码"，
        #     **R1/R2/R3 从来没被执行过**。**判据写着 ≠ 判据在执行。**）
        if not inner.get("ok"):
            return {"ok": False, "validator": "drama.parse_timed",
                    "criteria": [], "missing": [],
                    "error": inner.get("error") or "确定性路径吃不下这份稿",
                    "hint": inner.get("hint") or "分镜稿请写成『0s – 4s（标题）』"}
        lack = ["镜 %s 缺 %s" % (m.get("idx"), "、".join(m.get("lack") or []))
                for m in (v.get("missing") or [])]
        detected = [bool(s.get("shot_size") and s.get("camera") and s.get("emotion"))
                    for s in shots]
        crit = [
            {"id": "R1", "判据": "每镜可检出的字段齐全（景别/运镜/时长/情绪/描述）",
             "过": bool(detected) and all(detected),
             "detail": "字面检出：%d 镜里 %d 镜三项全中" % (len(detected), sum(detected)),
             "出处": "`drama` R1 + `_SIZE_MAP`/`_CAM_MAP`/`_EMO_MAP` 字面检出"},
            {"id": "R2", "判据": "缺字段如实进 missing，不许补默认值",
             "过": True, "detail": "本路径 missing %d 条：%s" % (len(lack), "；".join(lack[:3]) or "无"),
             "出处": "`drama` R2（《反假绿律》）"},
            {"id": "R3", "判据": "镜头时长之和 = 声明总时长（±0.05s）",
             "过": bool(v.get("dur_ok")),
             "detail": "Σ=%.3fs ｜ 声明=%.3fs ｜ 合=%s"
                       % (float(v.get("dur_sum") or 0), float(v.get("dur_declared") or 0),
                          v.get("dur_ok")),
             "出处": "`drama` R3"},
            {"id": "R5", "判据": "确定性路径不调外网（离线可复验）",
             "过": inner.get("source") == "rule-based",
             "detail": "source=%s" % inner.get("source"), "出处": "`drama` R5"},
        ]
        # ⚠️ **这条路径的已知局限**：源码把 `subject`（角色位置）**写死为空**
        #    （注释原文：「确定性路径不猜人物位置」）⇒ `verdict.complete` **恒为 false**。
        #    ⇒ 拿 `complete` 当硬判据 = **让每一步都过不去**，那是假拦。
        #    正确做法：**明说这条路径判不了角色位置**，硬判据只压在它能负责的三项上。
        known_gap = ("角色位置" in " ".join(lack)) or any("角色位置" in x for x in lack)
        ok = bool(shots) and bool(v.get("dur_ok")) and bool(detected) and all(detected)
        return {"ok": ok, "validator": "drama.parse_timed", "criteria": crit,
                "missing": lack, "shots_n": len(shots),
                "total_dur": v.get("dur_declared"), "complete": v.get("complete"),
                "路径局限": ("本条路径**不产出「角色位置」**（源码写死 `subject: \"\"`，注释原文："
                             "『确定性路径不猜人物位置』）⇒ `verdict.complete` 恒为 false。"
                             "**故本判据不拿 `complete` 当硬判据** —— 那是假拦。"
                             "要补角色位置须走 `split()`（模型语义路径，**要出网**）。"
                             if known_gap else ""),
                "error": (None if ok else "没过 R1/R3：%s" % ("；".join(lack[:3]) or "字面检出不足")),
                "source": inner.get("source")}
    except Exception as e:                                            # noqa: BLE001
        return {"ok": False, "validator": "drama.parse_timed", "criteria": [],
                "missing": [], "error": "%s: %s" % (type(e).__name__, str(e)[:100])}


# ── 分镜表的契约判据（第 65 轮）──────────────────────────────────────────────
# 出处**全部**取自仓内两份真契约，**一个字都不自己编**：
#   ① `审美相关skill/skills/video-pipeline/SKILL.md`（蒸馏自 ttalkkaklab/social-flow · Apache-2.0）
#      §1 分镜表四层「每个 shot 必须写清」的四格 · §2 三条硬规则 · §3 预算闸 ·
#      §4 剪辑契约 · §5 内容与叙事闸 · §6 双人审闸
#   ② `projects/_shared/templates/20260921-三方向-HITL1-分镜契约填写页.html`
#      逐镜四格的**真字段名** `render`/`eyeline`/`depth`/`reason`（`data-field`）
#      与顶层**真字段名** `style`/`share_shot`/`share_text`/`hook_video`/`att_*`（`data-global`）
# ⚠️ 探出来的两条边界，写死不許越：
#   · 该模板**绑的是一部片**（短视频《AI搬砖人》8 镜 × 4 格）⇒ `line_shot`/`line_to`/`alt_scene`/`gate_*`
#     是**方向专属**项（那一部的当事人/那一句台词/那一支备选场），**不许通用强求** —— 只报在不在。
#   · 模板逐镜那一行是「画面（来自 parse_timed）| 旁白/动作 | render | eyeline | depth | 为什么这么选」
#     ⇒ **没有** `transition` / `duration` 两个手填格：时长是 `parse_timed` 出来的。
#     所以本判据只在**件里带了** `duration` 时才判 8s 闸；带了就必须判得过（**判不了 ≠ 合格**）。
SB_RENDER = ("静帧（配运镜）", "3D 角色", "3D 物件", "数据图", "生成视频")
SB_DEPTH = ("浅景深", "深景深")
SB_SIGNS = (("att_copyright", "版权已核"), ("att_safety", "安全已审"),
            ("att_owner", "主人已批（HITL#1 分镜审批）"))
# §5 原文：「可转发物：一句能原样被转出去的话。**「求转发」不算可转发物，那是请求**」
SB_ASK = ("求转发", "求扩散", "求关注", "求点赞", "求三连", "帮忙转发", "转发一下",
          "点赞关注", "关注我", "求转发求扩散")
SB_STATIC_SEC = 8.0
# 方向专属项：**只报在不在**，不判合不合格（它们是那一部片的当事人字段）
SB_DIRECTION_ONLY = ("line_shot", "line_to", "alt_scene", "gate_source", "gate_flag",
                     "gate_style_prompt", "gate_artist_clear")


def _validate_storyboard(text: str) -> dict:
    """拿**仓内的分镜契约**验收人给的分镜表（纯离线 · 确定性 · 不调外网 · 不生成一个像素）。

    §0 铁律：分镜阶段**只规划，不生成** —— 所以这里只判"计划写全了没有"，
    判过了也不代表可以开拍（还要过 §6 的 HITL#1，即 `att_owner` 那条签署）。
    """
    crit, missing, fails, warns = [], [], [], []

    def mark(cid, name, ok, detail, src):
        crit.append({"id": cid, "判据": name, "过": bool(ok), "detail": detail, "出处": src})
        if not ok:
            fails.append("%s %s：%s" % (cid, name, detail))
        return bool(ok)

    try:
        obj = json.loads(text)
    except Exception as e:                                            # noqa: BLE001
        return {"ok": False, "validator": "media_run._validate_storyboard",
                "criteria": [], "missing": [], "warns": [], "shots_n": 0,
                "fails": ["B1 结构：分镜表不是合法 JSON —— %s" % str(e)[:80]],
                "error": "JSON 解析失败"}
    if not isinstance(obj, dict):
        return {"ok": False, "validator": "media_run._validate_storyboard",
                "criteria": [], "missing": [], "warns": [], "shots_n": 0,
                "fails": ["B1 结构：顶层必须是对象（要能读出 style / shots / share_text）"],
                "error": "顶层不是对象"}

    shots = obj.get("shots")
    if shots is None:
        shots = obj.get("storyboard")
    if shots is None and isinstance(obj.get("sequence"), dict):
        shots = obj["sequence"].get("shots")
    if not isinstance(shots, list):
        shots = []
    mark("B1", "顶层能解析成对象且带 shots 列表", bool(shots),
         "读到 %d 个镜头" % len(shots), "video-pipeline §1")

    # B3 全片预设风格 —— §1 原文：「**没有风格的分镜板一律打回**」
    style = (obj.get("style") or "").strip() if isinstance(obj.get("style"), str) else ""
    mark("B2", "全片预设风格非空（没有风格的分镜板一律打回）", bool(style),
         ("风格：%s" % style[:40]) if style else "`style` 缺或空", "video-pipeline §1")

    bad_render, bad_depth, no_reason, no_eye, dupes, over, bad_style = [], [], [], [], [], [], []
    seen_reason = {}
    max_static = obj.get("max_static_ground_seconds", SB_STATIC_SEC)
    if not isinstance(max_static, (int, float)):
        max_static = SB_STATIC_SEC

    for i, sh in enumerate(shots, 1):
        if not isinstance(sh, dict):
            bad_render.append("镜 %d（不是对象）" % i)
            continue
        r = (sh.get("render") or "").strip() if isinstance(sh.get("render"), str) else ""
        if not r:
            # **缺字段**与**填错值**是两件事：前者进 missing（不许补默认值），后者只判否
            missing.append("镜 %d 的 render（先读旁白再决定）" % i)
        if not r or not any(r.startswith(x) for x in SB_RENDER):
            bad_render.append("镜 %d（读到 %r）" % (i, r))
        eye = (sh.get("eyeline") or "").strip() if isinstance(sh.get("eyeline"), str) else ""
        if not eye:
            no_eye.append(i)
            missing.append("镜 %d 的 eyeline（视线方向记录）" % i)
        d = (sh.get("depth") or "").strip() if isinstance(sh.get("depth"), str) else ""
        if not d:
            missing.append("镜 %d 的 depth（数观众一次要读几样东西）" % i)
        if not d or not any(d.startswith(x) for x in SB_DEPTH):
            bad_depth.append("镜 %d（读到 %r）" % (i, d))
        why = (sh.get("reason") or "").strip() if isinstance(sh.get("reason"), str) else ""
        if not why:
            no_reason.append(i)
            missing.append("镜 %d 的 reason（为什么这么选）" % i)
        else:
            seen_reason.setdefault(why, []).append(i)
        # §1 表：单镜 `style` 是**例外风格**，要离开全片预设「必须经人工在 HITL 里批准过」
        if isinstance(sh.get("style"), str) and sh["style"].strip() and not sh.get("style_approved"):
            bad_style.append("镜 %d（写了 style=%r 但没 style_approved）" % (i, sh["style"].strip()[:30]))
        # §3 预算闸：单张静帧最多占一个镜头（`max_static_ground_seconds` 默认 8s）
        if any(k in r for k in ("静帧",)) and "duration" in sh:
            try:
                dur = float(sh["duration"])
            except (TypeError, ValueError):
                over.append("镜 %d 的 duration 不是数字（读到 %r）—— **判不了就不算合格**"
                            % (i, sh["duration"]))
                continue
            if dur > float(max_static) + 1e-9:
                over.append("镜 %d 静帧 %.1fs > 上限 %.1fs" % (i, dur, float(max_static)))

    mark("B3", "每镜 render 在契约名单内（先读旁白再决定）", not bad_render,
         ("、".join(bad_render)[:150]) if bad_render else "%d 镜全在名单内" % len(shots),
         "video-pipeline §1 表 + 模板 datalist `render-opts`")
    mark("B4", "每镜 eyeline 非空（一条记录四处同源）", not no_eye,
         ("缺：镜 %s" % "、".join(map(str, no_eye))) if no_eye else "%d 镜全有" % len(shots),
         "video-pipeline §1 表")
    mark("B5", "每镜 depth ∈ 浅景深/深景深", not bad_depth,
         ("、".join(bad_depth)[:150]) if bad_depth else "%d 镜全合" % len(shots),
         "video-pipeline §1 表 + 模板 datalist `depth-opts`")
    mark("B6", "每镜 reason 非空（每一个镜头都要有目的）", not no_reason,
         ("缺：镜 %s" % "、".join(map(str, no_reason))) if no_reason else "%d 镜全有" % len(shots),
         "video-pipeline §2.2")

    # §1 表：单镜 `style` 是**例外风格** —— 只报在不在，不算合格
    mark("B7", "例外风格须经 HITL 批准（`style_approved`）", not bad_style,
         ("；".join(bad_style)[:170]) if bad_style else "无未批的例外风格",
         "video-pipeline §1 表")

    # §2.2 原文：「**复制别人的理由 = 失败**」
    for why, idxs in seen_reason.items():
        if len(idxs) > 1:
            dupes.append("镜 %s 的理由一模一样：%r" % ("、".join(map(str, idxs)), why[:40]))
    mark("B8", "理由不许复制（复制别人的理由 = 失败）", not dupes,
         ("；".join(dupes)[:170]) if dupes else "无重复理由",
         "video-pipeline §2.2")

    mark("B9", "静帧时长 ≤ max_static_ground_seconds（默认 8s）", not over,
         ("；".join(over)[:170]) if over else "带 duration 的静帧镜全在 %.1fs 内" % float(max_static),
         "video-pipeline §3")

    # §2.3 原文：「`hook_video` **默认关**。没有哪个镜头因为「它在开头」就值得付钱。」
    hv = obj.get("hook_video")
    ok_hv = isinstance(hv, bool)
    if not ok_hv:
        missing.append("hook_video（开场是否用付费视频镜：默认关，必须显式写 false/true）")
    mark("B10", "hook_video 必须显式声明（默认关 = 必须有人明确说开）", ok_hv,
         ("读到 %r" % hv) if ok_hv else "缺省 = 未决定 = 打回，不许拿默认值顶上",
         "video-pipeline §2.3")
    if hv is True:
        warns.append("hook_video=true：开场用了付费视频镜 —— §2.3 说没有镜头因为「在开头」就值得付钱，"
                     "须由 `att_owner`（HITL#1）交代")

    # §5 原文：「收尾镜头的 `shot.share`；**缺了分镜板打回**」+「「求转发」不算可转发物，那是请求」
    st = obj.get("share_text")
    st = st.strip() if isinstance(st, str) else ""
    asked = [w for w in SB_ASK if w in st]
    ok_share = bool(st) and not asked
    detail = "读到 %r" % st[:50] if st else "`share_text` 缺或空（§5：缺了分镜板打回）"
    if asked:
        detail = "写着 %r —— 命中请求词 %s；§5 原文：「求转发」不算可转发物，那是请求" % (st[:40], "、".join(asked))
    mark("B11", "收尾镜 share 是**可转发物**（请求不算）", ok_share, detail,
         "video-pipeline §5 + 模板 `share_shot`/`share_text`")
    if not isinstance(obj.get("share_shot"), (int, str)) or str(obj.get("share_shot") or "").strip() == "":
        missing.append("share_shot（这句可转发物挂到第几镜）")
    if ok_share and len([c for c in st if c in "。！？!?"]) > 2:
        warns.append("share_text 看着不止一句（§5 要的是「一句话/一个数字/一个判词」）")

    # §6 双人审闸的第一道：没审批不许生成 —— 与 `media_pipeline.compose` 的三个 flag 一一对应
    bad_sign = []
    for k, cn in SB_SIGNS:
        v = obj.get(k)
        if v is True or str(v).strip().lower() in ("是", "true", "已核", "已审", "已批"):
            continue
        bad_sign.append("%s（`%s`）" % (cn, k))
        missing.append("%s（`%s`）" % (cn, k))
    mark("B12", "三条签署齐全（版权已核 / 安全已审 / 主人已批）", not bad_sign,
         ("、".join(bad_sign)[:150]) if bad_sign else "三条齐",
         "video-pipeline §6 HITL#1 + 模板三项证明")

    # §4 剪辑契约：同地点或同时间发生变化 → 优先 `dip`（**警告**，不阻断 —— 模板没有这两个手填格）
    prev = None
    for i, sh in enumerate(shots, 1):
        if not isinstance(sh, dict):
            continue
        if prev is not None and (sh.get("place"), sh.get("time")) != (prev.get("place"), prev.get("time")):
            if (sh.get("place") or sh.get("time")) and str(sh.get("transition") or "") != "dip":
                warns.append("镜 %d 的地点/时间相对镜 %d 变了，但 transition 不是 dip" % (i, i - 1))
        prev = sh

    direction_present = [k for k in SB_DIRECTION_ONLY if k in obj]
    return {
        "ok": not fails,
        "validator": "media_run._validate_storyboard",
        "契约": ["video-pipeline §0–§6", "分镜契约填写页 20260921-三方向-HITL1"],
        "shots_n": len(shots),
        "criteria": crit,
        "missing": missing,
        "fails": fails,
        "warns": warns,
        # 方向专属项：那一部片的当事人字段，**只报在不在**，不当通用判据
        "direction_only_present": direction_present,
        "error": (fails[0] if fails else None),
    }


# ── 歌词的契约判据（第 66 轮）──────────────────────────────────────────────
# 出处**全部**取自仓内两份真契约 + 一件真跑过的成品，一个字都不自己编：
#   ① `审美相关skill/skills/music-production/SKILL.md`（蒸馏自 bitwize-music-studio/
#      claude-ai-music-skills · **CC0-1.0**）
#      §1 溯源铁律（**只对纪实/真实事件类专辑生效**）· §2 歌词闸 · §3 生成前闸
#   ② `projects/_shared/templates/20260921-三方向-HITL1审批屏.html`
#      —— 那里有一张**真跑过的**「13 项歌词闸 · 逐条自查」表（《夜航》那一件）
#   ③ `projects/music/01-lyrics/20260921-夜航/20260921-music-夜航-01lyrics.md`
#      —— 真成品，本判据按**它这个形状**解析（Markdown · 四个小节 + 两张表）
#
# 🔴 三条不许越的边界，全是探出来才敢写的：
#   · §2 标题写「歌词闸（13 项）」，正文只**点名 5 项**（押韵·韵律·发音风险·视角一致·事实准确）
#     再加「其余九项」。**5 + 9 = 14 ≠ 13** —— 源件自相矛盾，**且那九项没列名**。
#     ⇒ 本判据**只判点得出名字的那几项**，并把「未列名的九项**必须如实标未判**」做成硬判据
#     （不许写"通过"）。**我不替上游编判据。**
#   · §1 溯源铁律**只对纪实/真实事件类生效** —— 虚构抒情曲**不触发**。
#     ⇒ 必须**先声明类目**；不声明就判不了该不该判（**判不了 ≠ 合格**）。
#   · §2 原文：「扫出**发音风险**要给**音标修正建议**，不是打回了事。」
#     ⇒ 标了有风险却**没给修正建议**才判否；给了就过，哪怕风险还在（**不是打回了事**）。
LY_GATES_NAMED = ("押韵", "韵律", "发音风险", "视角一致", "事实准确")
LY_GATES_DECLARED = 13          # §2 标题自己写的数
LY_GATES_STATED_REMAINING = 9   # §2 正文自己写的「其余九项」
LY_LEGAL_KEYS = ("来源已核验", "显式标志位已设", "风格提示词完整", "艺人名已清")
# ⚠️ 第三人称只收**人称**（他/她/他们/她们）—— **不收「它」**：
#    「它」是**物称**，第一人称叙事里说「只有在夜里它才是它原来的样子」是正常的，
#    不是叙事视角漂移。第一版我把「它」也收进来 ⇒ 把真成品《夜航》误判成视角漂移。
LY_PERSON = {"第一人称": ("我", "我们", "咱"),
             "第二人称": ("你", "你们", "您"),
             "第三人称": ("他", "她", "他们", "她们")}
# 否定式类目标记：写着这些就说明**不是**纪实类（第一版被「不含纪实主张」骗了）
LY_NOT_DOC = ("不含纪实", "非纪实", "不触发", "虚构")
LY_MEASURE_WORDS = ("实测", "逐行", "量法", "口径", "按行", "统计")


def _heading_hit(line: str, kw: str, exclude=()) -> bool:
    """小标题是不是要找的那一节。

    ⚠️ 第一版用「标题里含关键词」，于是 `kw="歌词"` **同时命中**了
    `## 二、歌词` 和 `## 三、13 项歌词闸 · 逐条自查` ⇒ 歌词段里混进了 §三 的散文行，
    机器数出 21 行（真歌词 20 行），我自己还以为「口径不同」。**取段要能排除。**
    """
    if not line.startswith("## ") or kw not in line:
        return False
    return not any(x in line for x in exclude)


def _md_table(text: str, title_kw: str, exclude=()):
    """从 Markdown 里取某小节的那张表：返回 [[第1列, 第2列, …]]。"""
    rows, on = [], False
    for line in text.split("\n"):
        if line.startswith("## "):
            on = _heading_hit(line, title_kw, exclude)
            continue
        if not on or not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or set("".join(cells)) <= set("-: "):     # 表头分隔行
            continue
        rows.append(cells)
    return rows


def _md_section(text: str, title_kw: str, exclude=()) -> str:
    """取某小节的正文（到下一个 `## ` 为止）。"""
    out, on = [], False
    for line in text.split("\n"):
        if line.startswith("## "):
            on = _heading_hit(line, title_kw, exclude)
            continue
        if on:
            out.append(line)
    return "\n".join(out)


def _lyric_lines(text: str) -> list:
    """§二 里的**歌词行**：非空、不是 `**段名**` 标签行、不是引用/表格/代码行。

    ⚠️ 取段时必须排除「歌词闸」那一节（它标题里也有「歌词」两个字）。
    """
    out = []
    for line in _md_section(text, "歌词", exclude=("闸", "自查", "生成前")).split("\n"):
        s = line.strip()
        if not s or s.startswith((">", "|", "#", "`", "- ")):
            continue
        if s.startswith("**") and s.endswith(("**", "**。")):
            continue
        out.append(s)
    return out


def _validate_lyrics(text: str) -> dict:
    """拿**仓内的音乐契约**验收人给的歌词件（纯离线 · 确定性 · 不调外网 · 不生成一个音符）。

    按真成品的形状解析（Markdown · §一概念 / §二歌词 / §三 13 项自查表 / §四生成前闸）。
    """
    crit, missing, fails, warns = [], [], [], []

    def mark(cid, name, ok, detail, src):
        crit.append({"id": cid, "判据": name, "过": bool(ok), "detail": detail, "出处": src})
        if not ok:
            fails.append("%s %s：%s" % (cid, name, detail))
        return bool(ok)

    if not isinstance(text, str) or not text.strip():
        return {"ok": False, "validator": "media_run._validate_lyrics", "criteria": [],
                "missing": [], "warns": [], "lines_n": 0,
                "fails": ["L1 结构：歌词件是空的"], "error": "空件"}

    # L1 署名（家规：文本页必须携带署名）
    mark("L1", "携带开发者署名（不许删）", "开发者：自由的风" in text,
         "署名行在" if "开发者：自由的风" in text else "找不到署名行", "仓规 · 署名不可删")

    # L2 §一 概念三字段（七阶段里的前两阶段）
    head = _md_section(text, "概念")
    for f in ("主题", "情绪线", "视角"):
        if not re.search(r"\*\*%s\*\*\s*[：:]" % f, head):
            missing.append("§一 概念的「%s」" % f)
    miss_head = [f for f in ("主题", "情绪线", "视角")
                 if not re.search(r"\*\*%s\*\*\s*[：:]" % f, head)]
    mark("L2", "§一 概念三字段齐全（主题 / 情绪线 / 视角）", not miss_head,
         ("缺：%s" % "、".join(miss_head)) if miss_head else "三字段齐", "music-production §0 七阶段")

    # L3 歌词正文
    lines = _lyric_lines(text)
    mark("L3", "§二 有歌词正文（至少 4 行）", len(lines) >= 4,
         "读出 %d 行歌词" % len(lines), "music-production §0 链路")

    # L4 §2 视角一致闸：声明了视角，且正文人称代词不漂出声明之外
    pm = re.search(r"\*\*视角\*\*\s*[：:]\s*([^\n]+)", head)
    declared = re.sub(r"[`*]", "", pm.group(1)).strip() if pm else ""
    found = {}
    for person, toks in LY_PERSON.items():
        hit = sum(1 for ln in lines for t in toks if t in ln)
        if hit:
            found[person] = hit
    stray = [p for p in found if declared and p not in declared]
    ok_view = bool(declared) and not stray
    detail = ("声明「%s」；正文命中 %s" % (declared[:24],
              "、".join("%s×%d" % (k, v) for k, v in sorted(found.items()))) if declared
              else "**没声明视角** —— 判不了就不算合格")
    if stray:
        detail += "；**漂出声明**：%s" % "、".join(stray)
    mark("L4", "§2 视角一致：声明视角且正文人称不许漂", ok_view, detail,
         "music-production §2 视角一致闸")

    # L5 §2 韵律闸 —— **数字必须带量法**，并**现算对照**
    #    （源件第 63–66 行的教训：原写「每行 9–11 字」是**没实测就写下的数字**，被审计官证伪）
    t3 = _md_table(text, "歌词闸")
    by_item = {}
    for r in t3:
        if r and r[0] and r[0] not in ("项",):
            by_item[r[0].replace("*", "").strip()] = r
    row_yun = by_item.get("韵律") or []
    yun_txt = " ".join(row_yun[2:]) if len(row_yun) > 2 else ""
    has_num = bool(re.search(r"\d", yun_txt))
    has_how = any(w in yun_txt for w in LY_MEASURE_WORDS)
    ok_yun = bool(row_yun) and (not has_num or has_how)
    detail = "自查行在" if row_yun else "**§三 表里没有「韵律」这一行**"
    if has_num and not has_how:
        detail = "写了数字却**没写量法** —— 源件的教训：判据里出现数字就必须有对应的量测步骤"
    mark("L5", "§2 韵律：写了数字就必须写清**是怎么量的**", ok_yun, detail, "music-production §2 + 源件第 63–66 行")

    # L5b **现算对照**（不算判据、只并列 —— 行数口径可能不同，机器不替人裁决）
    lens = [len(re.sub(r"\s", "", ln)) for ln in lines]
    recomputed = {}
    if lens:
        recomputed = {"行数": len(lens), "min": min(lens), "max": max(lens),
                      "均值": round(sum(lens) / len(lens), 1),
                      "逐行": "/".join(map(str, lens))}
        declared_run = re.findall(r"\d+(?:/\d+){2,}", yun_txt)
        if declared_run:
            runs = [list(map(int, r.split("/"))) for r in declared_run]
            flat = [n for r in runs for n in r]
            same = (sorted(flat) == sorted(lens))
            recomputed["自查声明的逐行串"] = declared_run
            recomputed["逐行一致"] = same
            if not same:
                warns.append("韵律的**逐行字数现算对不上自查表**：机器按「§二 里非空、非段名标签行」"
                             "数出 %d 行，自查表声明 %d 行 —— **口径可能不同（尾奏/重复段算不算），"
                             "机器不替人裁决**，但两侧数字都摆在这里供复核。"
                             % (len(lens), len(flat)))

    # L6 §2 发音风险闸：原文「扫出风险要给**音标修正建议**，不是打回了事」
    row_fy = by_item.get("发音风险") or []
    fy_verdict = " ".join(row_fy[1:2]) if len(row_fy) > 1 else ""
    fy_all = " ".join(row_fy[1:]) if len(row_fy) > 1 else ""
    risky = any(w in fy_verdict for w in ("⚠", "有", "存在")) and "无" not in fy_verdict[:4]
    has_fix = any(w in fy_all for w in ("建议", "改为", "替换", "演唱提示", "音标", "改标注"))
    mark("L6", "§2 发音风险：扫出风险须附**修正建议**（不是打回了事）", bool(row_fy) and (not risky or has_fix),
         ("判定 %s；%s" % (fy_verdict[:24], "附了修正建议" if has_fix else "**没给修正建议**"))
         if row_fy else "**§三 表里没有「发音风险」这一行**",
         "music-production §2 原文")

    # L7 §1 溯源铁律 —— **只对纪实/真实事件类生效**，所以必须先看类目
    row_fs = by_item.get("事实准确") or []
    fs_all = " ".join(row_fs[1:]) if len(row_fs) > 1 else ""
    # 🔴 **先看否定式**，再看肯定式：第一版按「纪实 → 真实事件 → 虚构」找关键词，
    #    结果被真成品那句「本曲为虚构抒情，**不含纪实主张**」里的「纪实」骗了 ⇒ 判成纪实类。
    joined = fs_all + "\n" + head
    doc_kind = ""
    for w in LY_NOT_DOC:
        if w in joined:
            doc_kind = "虚构"
            break
    if not doc_kind:
        for w in ("真实事件", "纪实"):
            if w in joined:
                doc_kind = w
                break
    if not doc_kind:
        missing.append("类目声明（纪实 / 真实事件 / 虚构）—— §1 溯源铁律**只对纪实类生效**，不声明就判不了")
        mark("L7", "§1 溯源铁律按类目触发（须先声明类目）", False,
             "**没声明类目** ⇒ 判不了该不该判（判不了 ≠ 合格）", "music-production §1")
    elif doc_kind in ("纪实", "真实事件"):
        src_rows = _md_table(text, "来源") + _md_table(text, "溯源")
        ok_src = len(src_rows) >= 1 and all(
            any(w in " ".join(r) for w in ("已核验", "核验过", "已捕获")) for r in src_rows)
        mark("L7", "§1 纪实类：每条主张都要追到**已捕获、已核验**的来源", ok_src,
             ("来源表 %d 行" % len(src_rows)) if ok_src else
             "纪实类但**没有带核验状态的来源表** —— 溯源铁律要求先核验后作词", "music-production §1")
    else:
        # 🔴 与 L8 同一条原则：**判「判定列」，不判理由散文**。
        #    第一版在整行里找「已核验」，把真成品那句**引述规则本身**的话
        #    （「每条主张追到**已核验来源**」…**不触发**）当成了主张 ⇒ 又冤枉了它。
        fs_verdict = row_fs[1] if len(row_fs) > 1 else ""
        ok_na = ("不适用" in fs_verdict) or ("不触发" in fs_verdict)
        no_fake = "已核验" not in fs_verdict
        mark("L7", "§1 虚构类：须如实标「不适用」，且不许谎称已核验", bool(row_fs) and ok_na and no_fake,
             ("判定列「%s」" % fs_verdict[:30]) if ok_na else
             ("虚构类却没写「不适用」" if row_fs else "**§三 表里没有「事实准确」这一行**") +
             ("" if no_fake else "；**判定列还写了「已核验」**"), "music-production §1")

    # L8 🔴 **未列名的那九项必须如实标未判** —— 不许写「通过」（上一轮立的规矩，现在变硬判据）
    row_9 = by_item.get("其余九项") or by_item.get("其余 13 项") or []
    # 🔴 只看**判定列**：第一版在整行里找「通过」，结果把真成品那句
    #    「我不编判据、**也不写"通过"**」里的**引述**当成了主张 ⇒ 冤枉了它。
    r9_verdict = row_9[1] if len(row_9) > 1 else ""
    r9 = " ".join(row_9[1:]) if len(row_9) > 1 else ""
    claims_pass = any(w in r9_verdict for w in ("✅", "通过", "合格", "已判", "已完成"))
    mark("L8", "源件未列名的其余九项：**必须如实标未判**，不许写「通过」",
         bool(row_9) and not claims_pass,
         ("如实写了未判（%s）" % r9[:44]) if row_9 and not claims_pass else
         ("**判定列写了通过/合格** —— 上游没列全判据，谁都不许替它宣布通过" if claims_pass
          else "**§三 表里没有「其余九项」这一行**"),
         "music-production §2 + 审批屏既有口径")

    # L9 §3 生成前闸四项：都要有明确状态，**不许空**（不要求全绿 —— 那是生成前那一刻的事）
    t4 = _md_table(text, "生成前闸")
    seen = {r[0].replace("*", "").strip(): (r[1] if len(r) > 1 else "") for r in t4 if r and r[0]}
    bad_l = []
    for k in LY_LEGAL_KEYS:
        st = seen.get(k)
        if st is None:
            bad_l.append("缺「%s」" % k)
            missing.append("§四 生成前闸的「%s」（整项都没写）" % k)
        elif not st.strip() or st.strip() in ("—", "-"):
            # **空着也要进 missing** —— 与契约同口径：缺字段进 missing，不许拿默认值顶上
            bad_l.append("「%s」状态空着" % k)
            missing.append("§四 生成前闸的「%s」（行在，状态空着）" % k)
    mark("L9", "§3 生成前闸四项都在场且各有明确状态", not bad_l,
         ("；".join(bad_l)) if bad_l else "四项齐（%s）" % "、".join(LY_LEGAL_KEYS),
         "music-production §3")

    # L10 🔴 **交空壳不算**（第 72 轮实测加）：歌词骨架**不填空也能过前九条** ——
    #     因为那九条判的是「结构在不在场」。骨架住在 `.scratch/`，但它一被复制进抽屉
    #     就成了一件"看着齐全"的东西。⇒ 明写：件里不许留骨架占位符。
    ph = re.findall(r"<[^<>\n]{2,60}>", text)
    mark("L10", "件里不许留骨架占位符（`<…>`）", not ph,
         ("留着 %d 处，例如 %s" % (len(ph), ph[0][:30])) if ph else "无占位符",
         "本仓纪律：**骨架 ≠ 件**；不填就交 = 拿空壳冒充成品")

    return {
        "ok": not fails,
        "validator": "media_run._validate_lyrics",
        "契约": ["music-production §1–§3（CC0-1.0）", "审批屏 20260921-三方向-HITL1 既有口径"],
        "lines_n": len(lines),
        "criteria": crit, "missing": missing, "fails": fails, "warns": warns,
        "recomputed": recomputed,
        # 🔴 诚实块：**源件自相矛盾，且那九项没列名** —— 如实记下，不猜、不编
        "gates": {"源件声明总数": LY_GATES_DECLARED,
                  "源件点名": len(LY_GATES_NAMED), "names": list(LY_GATES_NAMED),
                  "源件自称其余": LY_GATES_STATED_REMAINING,
                  "点名加其余": len(LY_GATES_NAMED) + LY_GATES_STATED_REMAINING,
                  "note": "源件 13 ≠ 5+9，**且那九项未列名** —— 本判据只判点得出名字的项，"
                          "不替上游编判据"},
        "error": (fails[0] if fails else None),
    }


# ── 编曲件的契约判据（第 69 轮）────────────────────────────────────────────
# 出处**取自框架自己的设计**，不是我编的字段：
#   `media_flow` 的编曲格 `music/03-arrange` **允许的扩展名里写着 `.als` / `.flp` / `.mid`**
#   —— 框架自己把这一步设计成「**人给工程件**」。所以判据是：
#   **件在 ⇒ 还要看件里到底有没有那些必填的东西**（在场 ≠ 合格）。
#
# 🔴 一条不许越的边界：**本机只有 `.mid`（Standard MIDI File）能确定性解析**。
#   `.als`（Ableton · gzip 过的 XML）与 `.flp`（FL Studio · 专有二进制）**本机没有解析器**。
#   ⇒ 对这两种格式**不许假装判过**：返回 `unjudgeable`，链上如实报 `input_unjudged`
#   （这是一个**独立状态**，既不是 `ran` 也不是 `input_rejected` —— 「判不了」不等于「不合格」，
#     也绝不等于「合格」）。
ARR_KEYS_MAJOR = ("Cb", "Gb", "Db", "Ab", "Eb", "Bb", "F", "C", "G", "D", "A", "E", "B", "F#", "C#")
ARR_KEYS_MINOR = ("Ab", "Eb", "Bb", "F", "C", "G", "D", "A", "E", "B", "F#", "C#", "G#", "D#", "A#")
# 🔴 允许的扩展名**照抄闸门那一格**（`media_flow` 的 `03-arrange`：`ext` 六种 + `must` 两样）。
#    第一版我只认 `.mid/.als/.flp` ⇒ 会把合法放进来的 `.wav`/`.flac`/`.json` 编曲件
#    误判成「不认的扩展名」。**判据的边界必须与闸门同源，不许自己另立一份。**
ARR_GATE_EXT = (".mid", ".midi", ".wav", ".flac", ".json", ".als", ".flp")
ARR_JUDGEABLE = (".mid", ".midi")
ARR_UNJUDGEABLE = {
    ".als": "Ableton Live 工程（gzip 过的 XML）—— 本机没有解析器",
    ".flp": "FL Studio 工程（专有二进制）—— 本机没有解析器",
    ".wav": "渲染出来的音频 —— 里面没有调号/tempo 事件，判不了「调性与速度」「配器清单」",
    ".flac": "渲染出来的音频 —— 同上",
    ".json": "清单/描述文件 —— 不是工程件，里面没有可核对的 MIDI 事件",
}
# 闸门那格的 must 是**两样**：「编曲工程」+「分轨」。本判据只看得了前一样。
ARR_GATE_MUST = ("编曲工程", "分轨")
ARR_TEMPO_DEFAULT = 120.0       # SMF 规范：没有 tempo 事件时就是 120 BPM（**默认值，不是件里写的**）


def _vlq(b: bytes, i: int):
    """MIDI 的可变长量（varlen）。返回 (值, 新下标)。"""
    v = 0
    while i < len(b):
        c = b[i]
        i += 1
        v = (v << 7) | (c & 0x7F)
        if not (c & 0x80):
            break
    return v, i


def _parse_midi(b: bytes) -> dict:
    """解析 Standard MIDI File（纯 stdlib · 确定性 · 不联网）。读不出就如实说读不出。"""
    if len(b) < 14 or b[:4] != b"MThd":
        return {"ok": False, "error": "没有 `MThd` 头 —— 这不是一个 Standard MIDI File"}
    fmt = int.from_bytes(b[8:10], "big")
    ntrk = int.from_bytes(b[10:12], "big")
    div = int.from_bytes(b[12:14], "big")
    if fmt not in (0, 1, 2):
        return {"ok": False, "error": "SMF 格式号 %d 不在规范里（只认 0/1/2）" % fmt}
    i = 14
    tempos, keys, notes, progs = [], [], 0, set()
    chans = set()
    while i + 8 <= len(b):
        if b[i:i + 4] != b"MTrk":
            i += 1
            continue
        ln = int.from_bytes(b[i + 4:i + 8], "big")
        j, end = i + 8, min(len(b), i + 8 + ln)
        status = 0
        while j < end:
            _d, j = _vlq(b, j)
            if j >= end:
                break
            c = b[j]
            if c & 0x80:
                status = c
                j += 1
            if status == 0xFF:
                if j >= end:
                    break
                mt = b[j]
                j += 1
                sz, j = _vlq(b, j)
                data = b[j:j + sz]
                j += sz
                if mt == 0x51 and len(data) == 3:
                    mspq = int.from_bytes(data, "big")
                    if mspq > 0:
                        tempos.append(round(60000000.0 / mspq, 3))
                elif mt == 0x59 and len(data) >= 2:
                    sf = data[0] - 256 if data[0] > 127 else data[0]
                    keys.append((sf, data[1]))
                elif mt == 0x2F:
                    break
            elif 0x80 <= status <= 0xEF:
                hi = status & 0xF0
                chans.add(status & 0x0F)
                if hi in (0x80, 0x90):
                    if j + 1 >= end:
                        break
                    if hi == 0x90 and b[j + 1] > 0:
                        notes += 1
                    j += 2
                elif hi in (0xC0, 0xD0):
                    if hi == 0xC0 and j < end:
                        progs.add(b[j])
                    j += 1
                else:
                    j += 2
            else:
                j += 1
        i = end
    key_txt = ""
    if keys:
        sf, mi = keys[0]
        if -7 <= sf <= 7:
            nm = (ARR_KEYS_MINOR if mi else ARR_KEYS_MAJOR)[sf + 7]
            key_txt = "%s %s" % (nm, "小调" if mi else "大调")
    return {"ok": True, "format": fmt, "tracks_declared": ntrk, "division": div,
            "tempos": tempos, "key": key_txt, "key_events": len(keys),
            "notes": notes, "channels": sorted(chans), "programs": sorted(progs)}


def _validate_arrangement(path, raw: bytes) -> dict:
    """验收人给的编曲工程件。**只对 `.mid` 判得了**；`.als`/`.flp` 如实标「判不了」。"""
    from pathlib import Path as _P
    ext = _P(str(path)).suffix.lower()
    crit, missing, fails, warns = [], [], [], []

    def mark(cid, name, ok, detail, src):
        crit.append({"id": cid, "判据": name, "过": bool(ok), "detail": detail, "出处": src})
        if not ok:
            fails.append("%s %s：%s" % (cid, name, detail))

    if ext in ARR_UNJUDGEABLE:
        return {"ok": False, "unjudgeable": True,
                "validator": "media_run._validate_arrangement",
                "criteria": [], "missing": ["调性/速度/配器/段落 —— 本机没有该格式的判据件"],
                "fails": ["A0 判不了：%s。**判不了 ≠ 合格，也不等于不合格**，如实标 `input_unjudged`"
                          % ARR_UNJUDGEABLE[ext]],
                "warns": [], "error": "判不了：%s" % ARR_UNJUDGEABLE[ext],
                "为什么": "`media_flow` 的编曲格允许 %s 这 %d 种扩展名；本机只判得动 `.mid`"
                          "（Standard MIDI File，能确定性解析）。要给其余格式上判据，"
                          "得先装对应的解析库 —— **那不是我现在能编的**。"
                          % ("、".join(ARR_GATE_EXT), len(ARR_GATE_EXT))}
    if ext not in ARR_JUDGEABLE:
        return {"ok": False, "validator": "media_run._validate_arrangement", "criteria": [],
                "missing": [], "warns": [],
                "fails": ["A0 格式：`%s` 不在编曲格的允许清单里（那一格收 %s）"
                          % (ext, "、".join(ARR_GATE_EXT))],
                "error": "不认这个扩展名（闸门那一格的清单里没有它）"}

    mark("A1", "是个真的 Standard MIDI File（`MThd` 头 + 格式号 0/1/2）",
         raw[:4] == b"MThd", "读到 %d 字节；头 4 字节 = %r" % (len(raw), raw[:4]),
         "SMF 规范 · 框架编曲格允许 `.mid`")
    m = _parse_midi(raw)
    if not m.get("ok"):
        mark("A2", "能解析出事件", False, str(m.get("error"))[:90], "SMF 规范")
        return {"ok": False, "validator": "media_run._validate_arrangement",
                "criteria": crit, "missing": missing, "fails": fails, "warns": warns,
                "error": m.get("error")}
    mark("A2", "能解析出事件", True,
         "SMF 格式 %d · 声明 %d 轨 · division %d" % (m["format"], m["tracks_declared"], m["division"]),
         "SMF 规范")

    # A3 速度：**没有 tempo 事件时 SMF 规定就是 120** —— 那是默认值，不是件里写的
    if m["tempos"]:
        uniq = sorted(set(m["tempos"]))
        mark("A3", "件里**写了**速度（tempo 事件）", True,
             "BPM %s（tempo 事件 %d 个）" % ("、".join("%g" % t for t in uniq[:6]), len(m["tempos"])),
             "编曲格必填「调性与速度（BPM）」")
    else:
        warns.append("件里**没有 tempo 事件** ⇒ 按 SMF 规范就是默认 **%g BPM**。"
                     "那是**规范的默认值，不是作者写的** —— 必填字段「速度」在件里其实是空的。"
                     % ARR_TEMPO_DEFAULT)
        mark("A3", "件里**写了**速度（tempo 事件）", False,
             "没有 tempo 事件 ⇒ 只能按规范默认 %g BPM 读" % ARR_TEMPO_DEFAULT,
             "编曲格必填「调性与速度（BPM）」")

    # A4 调性
    if m["key"]:
        mark("A4", "件里写了调号（key signature）", True, m["key"], "编曲格必填「调性」")
    else:
        missing.append("调性（key signature 事件）—— 件里没有 ⇒ 进 missing，**不许替它猜一个调**")
        mark("A4", "件里写了调号（key signature）", False,
             "没有调号事件；**不替它猜调**", "编曲格必填「调性」")

    # A5 内容非空（硬判据：空工程 = 打回）
    mark("A5", "件里有音符（空工程打回）", m["notes"] > 0,
         "音符事件 %d 个" % m["notes"], "编曲格必填「段落结构」—— 空件谈不上结构")

    # A6 配器：从**实测**的通道与音色推出来，不是抄件里的声明
    mark("A6", "能读出配器（用到的通道与音色）", bool(m["channels"]),
         "通道 %d 个 %s ｜ 音色变更 %d 次 %s"
         % (len(m["channels"]), m["channels"], len(m["programs"]), m["programs"]),
         "编曲格必填「配器清单」—— 这一条是它的**机读版**（实测，不抄声明）")

    mark("A7", "音符跨度够写出一段结构", m["notes"] >= 8,
         "音符 %d 个（少于 8 个写不出段落结构）" % m["notes"],
         "编曲格必填「段落结构」")
    # 闸门那一格的 must 是**两样**；本判据只看得了前一样 —— 如实说，不冒充看全了
    warns.append("闸门 `03-arrange` 那格的 `must` 是**两样**：%s。"
                 "本判据只看得了「编曲工程」这一样；「分轨」那一样由闸门自己数抽屉里的件。"
                 % " + ".join(ARR_GATE_MUST))

    return {"ok": not fails, "validator": "media_run._validate_arrangement",
            "criteria": crit, "missing": missing, "fails": fails, "warns": warns,
            "midi": {k: m[k] for k in ("format", "tracks_declared", "division", "key",
                                       "notes", "channels", "programs")},
            "tempo_bpm": (m["tempos"][0] if m["tempos"] else None),
            "格式": ext,
            "error": (fails[0] if fails else None)}


# ── 概念的契约判据（第 70 轮）──────────────────────────────────────────────
# 出处**全取自框架自己的件**，不拿我自己写的字段清单立规矩（上一轮定的方向）：
#   ① `media_pipeline.MEDIA_KNOWLEDGE[kind]["craft"][0]` —— 框架给**每个方向**写的
#      「概念期第一手艺」。这三句是这一轮判据的主干：
#        film        「先锁定 **主题、欲望、阻力与变化**」
#        short_video 「**首 3 秒**建立**冲突或收益承诺**」
#        music       「先定义 **情绪曲线、速度、调性和参考边界**」
#   ② `media_pipeline.COMMON_GATES` 的**头两道**：「**需求与受众证据**」「**成本上限**」
#   ③ `media_pipeline.self_review()` —— 框架自己的九项结构审查。**复用它**，
#      但只把**概念期谈得上的**四项算作判据；其余五项如实列成「这一步还谈不上」。
#   ④ `video-pipeline` §3：「**未知价格直接失败，不许猜**」⇒ 成本上限不许写「待定」。
#
# 🔴 **本件发现的一个结构错位（如实记，不擅自改）**：
#    `film` 的第 1 步 `concept` 与第 2 步 `script` **被放在同一个抽屉** `01-screenplay`，
#    而闸门 `media_flow` 把 `01-screenplay` 映射到 **`script`**（它的 film 工序里没有 concept 的格）。
#    更硬的证据：抽屉里那件**真成品**叫 `20260921-film-老屋-**01screenplay**.md`（题「01 剧本」）——
#    它既不是 `-01concept.md` 也不是 `-02script.md` ⇒ **两步现在都看不见它**。
#    ⇒ 本判据把这件事当**警告**报出来，**不擅自改编号**（改了会动到闸门的映射）。
CPT_CRAFT_TOKENS = {
    # 每项都写着它出自哪一句 craft —— 数字与词都不是我编的
    "film": ("主题", "欲望", "阻力", "变化"),
    "short_video": ("首 3 秒", ("冲突", "收益承诺")),
    "music": ("情绪曲线", "速度", "调性", "参考边界"),
}
CPT_AUDIENCE_HINTS = ("目标观众", "受众", "观众")
CPT_EVIDENCE_HINTS = ("证据", "依据", "来源", "调研", "数据", "访谈", "出处")
CPT_COST_HINTS = ("成本上限", "预算上限", "成本", "预算")
CPT_TBD = ("待定", "未知", "未定", "TBD", "tbd", "以后再", "后面再")
CPT_SELF_REVIEW_APPLIES = ("kind_known", "title_present", "brief_present", "stages_declared")


def _validate_concept(kind: str, text: str) -> dict:
    """验收人给的概念件。判据**全取自框架自己的件**（`MEDIA_KNOWLEDGE` / `COMMON_GATES` / `self_review`）。"""
    crit, missing, fails, warns = [], [], [], []

    def mark(cid, name, ok, detail, src):
        crit.append({"id": cid, "判据": name, "过": bool(ok), "detail": detail, "出处": src})
        if not ok:
            fails.append("%s %s：%s" % (cid, name, detail))
        return bool(ok)

    if not isinstance(text, str) or not text.strip():
        return {"ok": False, "validator": "media_run._validate_concept", "criteria": [],
                "missing": [], "warns": [], "fails": ["C1 结构：概念件是空的"], "error": "空件"}
    from .. import api as _api
    from . import media_pipeline as _mp
    kn = _mp.MEDIA_KNOWLEDGE.get(kind) or {}
    craft0 = (kn.get("craft") or [""])[0]
    stage0 = (_mp.KINDS.get(kind) or ("", ()))[1][:1]

    # C1 复用**框架自己的** `self_review`：只把概念期谈得上的四项算判据
    title = ""
    for ln in text.split("\n"):
        if ln.startswith("# "):
            title = ln[2:].strip()
            break
    brief = ""
    for ln in text.split("\n"):
        s = ln.strip()
        # ⚠️ 只排**标题/引用/表格行**。第一版我把 `**` 开头的行也排掉了 ——
        #    可概念件的正文本来就是 `**主题**：…` 这种写法 ⇒ 我自己把 brief 判成了"没写"，
        #    于是 `self_review` 的 `brief_present` 恒为假、C1 永远过不去。
        if s and not s.startswith(("#", ">", "|")):
            brief = s
            break
    sr = _mp.self_review({"kind": kind, "title": title, "brief": brief}, room_id="")
    checks = sr.get("checks") or {}
    bad = [k for k in CPT_SELF_REVIEW_APPLIES if not checks.get(k)]
    mark("C1", "框架自己的 `self_review` 适用项全过（kind/title/brief/stages）", not bad,
         ("没过的：%s" % "、".join(bad)) if bad else
         "四项全过（复用 `media_pipeline.self_review`，未另写一套）",
         "`media_pipeline.self_review()` 的 `checks`")
    not_yet = [k for k in checks if k not in CPT_SELF_REVIEW_APPLIES]
    warns.append("`self_review` 余下 %d 项（%s）**这一步还谈不上**："
                 "素材与 sha256 要等生成端落件，三项签署属于 HITL#1 —— "
                 "它们**不是不合格，是还不到时候**。" % (len(not_yet), "、".join(not_yet)))

    # C2 **方向自己的概念期第一手艺** —— 判据出处就是 `craft[0]` 那一句
    toks = CPT_CRAFT_TOKENS.get(kind) or ()
    hit, lack = [], []
    for t in toks:
        if isinstance(t, tuple):                       # 任选其一（如「冲突」或「收益承诺」）
            if not any(x in text for x in t):
                lack.append("或".join(t))
            else:
                hit.append("/".join(x for x in t if x in text))
        elif t in text:
            hit.append(t)
        else:
            lack.append(t)
    mark("C2", "概念期第一手艺（`MEDIA_KNOWLEDGE[%s].craft[0]`）逐样在场" % kind, not lack,
         ("缺：%s" % "、".join(lack)) if lack else "在场：%s" % "、".join(hit),
         "框架自己的 craft 原句：「%s」" % craft0)
    for x in lack:
        missing.append("概念期手艺里的「%s」（craft 原句：「%s」）" % (x, craft0))

    # C3 需求与受众证据（COMMON_GATES 第 1 道）
    has_aud = any(h in text for h in CPT_AUDIENCE_HINTS)
    has_evi = any(h in text for h in CPT_EVIDENCE_HINTS)
    mark("C3", "需求与受众**证据**（不是只有一句声明）", has_aud and has_evi,
         "受众 %s · 证据 %s" % ("在" if has_aud else "**缺**", "在" if has_evi else "**缺**"),
         "`media_pipeline.COMMON_GATES[0]`「需求与受众证据」")
    if not has_aud:
        missing.append("目标观众/受众（`COMMON_GATES[0]` 要的是**证据**，不是形容词）")
    if not has_evi:
        missing.append("受众证据（来源/调研/数据/出处 —— 只有结论没有依据 = 没证据）")

    # C4 成本上限（COMMON_GATES 第 2 道）+ `video-pipeline` §3「未知价格直接失败，不许猜」
    import re as _re
    money = _re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*(?:美元|USD|usd|\$|元|块|RMB)", text)
    tbd = [w for w in CPT_TBD if w in text]
    has_cost = any(h in text for h in CPT_COST_HINTS)
    ok_cost = has_cost and bool(money) and not tbd
    detail = ("读到 %s" % "、".join(money[:4])) if money else "**没读到任何金额**"
    if tbd:
        detail += "；还写着「%s」—— §3 原文：**未知价格直接失败，不许猜**" % "、".join(tbd[:3])
    elif not has_cost:
        detail = "**整件没写成本上限**"
    mark("C4", "写了成本上限（且不许写「待定」—— 未知价格直接失败）", ok_cost, detail,
         "`COMMON_GATES[1]`「成本上限」+ `video-pipeline` §3")
    if not ok_cost:
        missing.append("成本上限（一个真的数字；「待定」不算）")

    # C5 结构错位：如实报，不擅自改编号
    warns.append("结构错位（本件发现，未擅自改）：`film` 的 `concept` 与 `script` **共用抽屉** "
                 "`01-screenplay`，而闸门把这一格映射到 `script`；抽屉里那件真成品叫 "
                 "`20260921-film-老屋-01screenplay.md` ⇒ 两步现在**都看不见它**。"
                 "改编号会动到闸门映射，故只报不改。")

    return {"ok": not fails, "validator": "media_run._validate_concept",
            "kind": kind, "stage": (stage0[0] if stage0 else ""),
            "契约": ["media_pipeline.MEDIA_KNOWLEDGE[%s].craft[0]" % kind,
                     "media_pipeline.COMMON_GATES[:2]",
                     "media_pipeline.self_review()"],
            "criteria": crit, "missing": missing, "fails": fails, "warns": warns,
            "self_review": {"passed": sr.get("passed"), "total": sr.get("total"),
                            "适用项": list(CPT_SELF_REVIEW_APPLIES),
                            "这一步还谈不上": not_yet},
            "error": (fails[0] if fails else None)}


# 输入口的**判据表**：谁的人写步要过哪个框架自己的校验器（在场 ≠ 合格）
_VALIDATORS = {
    "script": _validate_script,        # 剧本/台词表 → `drama.parse_timed`（确定性离线 R1–R5）
    "screenplay": _validate_script,
    "storyboard": _validate_storyboard,  # 分镜表 → 仓内分镜契约（`video-pipeline` §0–§6）
    "lyrics": _validate_lyrics,        # 歌词 → 仓内音乐契约（`music-production` §1–§3）
    "arrangement": _validate_arrangement,  # 编曲工程件 → 框架自己的编曲格契约（只判得动 `.mid`）
    "concept": _validate_concept,      # 概念 → 框架自己的 craft[0] + COMMON_GATES + self_review
}
_VALIDATOR_SRC = {"script": "`drama.parse_timed`", "screenplay": "`drama.parse_timed`",
                  "storyboard": "仓内分镜契约（`video-pipeline` §0–§6）",
                  "lyrics": "仓内音乐契约（`music-production` §1–§3）",
                  "arrangement": "框架自己的编曲格契约（`media_flow` 编曲格允许的工程件格式）",
                  "concept": "框架自己的概念期契约（`MEDIA_KNOWLEDGE.craft[0]` + `COMMON_GATES` + `self_review`）"}
# ⚠️ 入参有三种：正文（多数）· `(相对路径, 字节)`（二进制）· `(方向, 正文)`（要分方向的）。
#    **不是复制粘贴，是三种入参** —— 摊开写清楚，免得下一个人以为它们一样。
_VALIDATOR_BINARY = ("arrangement",)
_VALIDATOR_KINDED = ("concept",)


def scaffold(kind: str, step: str, work: str = "pipeline-selftest") -> dict:
    """生成"人写的步"的**填空模板**。落在 `.scratch/`，**不进抽屉**。"""
    steps = CHAINS.get(kind) or []
    idx = next((i for i, s in enumerate(steps, 1) if s["step"] == step), 0)
    if not idx:
        return {"ok": False, "error": "方向 %r 里没有这一步 %r" % (kind, step)}
    s = steps[idx - 1]
    if not s.get("human"):
        return {"ok": False, "error": "第 %d 步 %s **不是人写的步**（它有实现器：%s）"
                                     % (idx, step, s.get("cap"))}
    exp = _expect_name(kind, work, idx, step, s["ext"])
    SIGN = "开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"
    head = ["# %s · %s（%s）" % (KIND_CN.get(kind, kind), step, work), "",
            "> 这是**给人填的骨架**，不是作品。填好后按下面的名字放进抽屉，链就会把它当输入收下。",
            "> ⚠️ 本文件落在 `.scratch/`，**不是**抽屉里 —— 骨架塞进抽屉 = 拿空壳冒充成品。", "",
            "放置位置：`projects/%s/%s/`" % (DIR_NAME.get(kind, kind), s["drawer"]),
            "文件名：`%s`" % exp, ""]

    # ── 骨架：**按判据要的形状给**，不是按我高兴 ──────────────────────────────
    # 🔴 本器**自检**：骨架生成后**当场用自己的判据跑一遍**，并把「还差什么」列出来。
    #    **绝不吐一个"看着像模板、其实过不了自己判据"的东西** ——
    #    那正是第 71 轮那个坑的同类：看着接上了，其实没接。
    skel, fmt, why = None, "md", ""
    if step in ("script", "screenplay"):
        # 格式出处：`gbt_allinone/drama.py` 的模块说明 + `_TIME_RANGE`
        #   ——「认『0s – 4s（标题）』这种带时间码的分镜稿」，靠**字面检出**三类词。
        # ⚠️ 说明文字里**绝不能出现**一个真的时间码形状，否则它会被当成**第 1 镜**，
        #    把 Σ时长算歪 ⇒ R3 当场判否（第一版我就这么写坏了）。所以下面用文字描述格式。
        fmt = "md"
        skel = "\n".join([
            "# %s · 《作品名》· 剧本 / 分镜稿" % KIND_CN.get(kind, kind), "", "> " + SIGN, "",
            "> 【格式】每一镜写成：**起止秒数 + 破折号 + 括号小标题**，紧跟着这一镜的正文。",
            "> 【判据】每镜正文里必须**字面出现**三类词（出处 `drama.py` 的检出表）：",
            "> 景别（远景/中景/近景/特写…）· 运镜（推近/横移/手持/环绕…）· 情绪（平静/压抑/温柔…）。",
            "> 【已知局限】这条路径**不产出「角色位置」**（源码写死不猜）—— 要它须走出网那条路。", "",
            "## 分镜稿", "",
            "0s – 4s（<小标题>）", "<画面描述>。远景，手持，平静。", "",
            "4s – 9s（<小标题>）", "<画面描述>。中景，推近，压抑。", "",
            "9s – 14s（<小标题>）", "<画面描述>。近景，横移，温柔。", "",
            "## 署名（不许删）", "", SIGN, ""])
    elif step == "storyboard":
        fmt = "json"
        skel = json.dumps({
            "style": "<全片预设风格；契约 §1：没有风格的分镜板一律打回>",
            "hook_video": False,
            "share_shot": 1,
            "share_text": "<一句能原样被转出去的话；§5：「求转发」不算可转发物，那是请求>",
            "att_copyright": False, "att_safety": False, "att_owner": False,
            "shots": [{"no": 1, "render": "静帧（配运镜）", "eyeline": "<视线方向>",
                       "depth": "浅景深（点名锐面）",
                       "reason": "<为什么这么选；§2.2：复制别人的理由 = 失败>", "duration": 6}],
        }, ensure_ascii=False, indent=2)
    elif step == "lyrics":
        skel = "\n".join([
            "# 音乐 · 《作品名》· 01 歌词", "", "> " + SIGN, "",
            "## 一、概念（七阶段中的第 1–2 阶段）", "",
            "**主题**：<一句话主题>", "**情绪线**：<闷 → 松开 → …>",
            "**视角**：第一人称，**全篇不变**", "", "## 二、歌词", "",
            "**主歌一**", "<一行一句，至少 4 行>", "<第二行>", "<第三行>", "<第四行>", "",
            "## 三、13 项歌词闸 · 逐条自查", "",
            "| 项 | 判定 | 依据 |", "|---|---|---|",
            "| 押韵 | <✅/⚠️> | <韵脚方案> |",
            "| 韵律 | <✅> | **实测逐行非空白字数**（N 行）：min · max · 均值 |",
            "| 发音风险 | <✅ 无 / ⚠️ 有 N 处> | <有风险必须给**音标修正建议**> |",
            "| 视角一致 | <✅> | 全篇第一人称，无漂移 |",
            "| 事实准确 | ✅ **不适用** | 本曲为虚构抒情，**不含纪实主张**，故 §1 溯源铁律**不触发** |",
            "| 其余九项 | ⛔ **未判** | 上游未列全判据；**我不编判据、也不写「通过」** |", "",
            "## 四、生成前闸（§3）自查", "", "| 项 | 状态 |", "|---|---|",
            "| 来源已核验 | <✅ 不适用（非纪实）/ 已核验> |",
            "| 显式标志位已设 | <✅/⛔> |", "| 风格提示词完整 | <✅/⛔> |",
            "| **艺人名已清** | <✅ 全篇无任何艺人/乐队/作品名> |", ""])
    elif step == "concept":
        toks = CPT_CRAFT_TOKENS.get(kind) or ()
        lines = ["# %s · 《作品名》· 01 概念" % KIND_CN.get(kind, kind), "", "> " + SIGN, ""]
        if kind == "film":
            for t in toks:
                lines.append("**%s**：<在这里写>" % t)
        elif kind == "short_video":
            lines += ["**首 3 秒**：<冲突或收益承诺>", "**冲突**：<在这里写>"]
        else:
            for t in toks:
                lines.append("**%s**：<在这里写>" % t)
        lines += ["", "**目标观众**：<写给谁>",
                  "**受众证据**：<来源/调研/数据/出处 —— 只有结论没有依据 = 没证据>",
                  "**成本上限**：<一个真的数字，如 8 美元；「待定」不算>", ""]
        skel = "\n".join(lines)
    else:
        why = ("这一步要的是**二进制工程件**（DAW 导出），模板给不出件；"
               if step in _VALIDATOR_BINARY else
               "这一步的判据要吃**框架自己的时间码格式**，我不敢凭记忆编一个"
               "（编出来的骨架过不了判据 = 白给）。")
    if skel is not None:
        body = head + (["```json", skel, "```", ""] if fmt == "json" else [skel])
    else:
        body = head + ["> ⚠️ **本步给不出可填骨架**：%s" % why,
                       "> 下面是**判据清单** —— 你按它自查，件齐了再放进抽屉。", "",
                       "## 判据清单（过不了就不放行）", ""]
        for f in (s.get("fields") or []):
            body.append("- **%s**" % f)
    body += ["", "## 署名（不许删）", "", SIGN, ""]
    text = "\n".join(body)
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    out = TEMPLATE_DIR / ("%s-%s-%s.%s" % (kind, step, work, fmt))
    out.write_text(text if skel is None else skel, encoding="utf-8")

    # ── 自检：拿自己的判据跑一遍骨架，把「还差什么」如实列出来 ─────────────────
    verdict, remaining = None, []
    if skel is not None and step in _VALIDATORS:
        try:
            if step in _VALIDATOR_KINDED:
                verdict = _VALIDATORS[step](kind, skel)
            else:
                verdict = _VALIDATORS[step](skel)
            remaining = [c["id"] for c in verdict.get("criteria", []) if not c["过"]]
        except Exception as e:                                        # noqa: BLE001
            verdict = {"ok": False, "error": "骨架自检没跑起来：%s" % str(e)[:90]}
    return {"ok": True, "kind": ("skeleton" if skel is not None else "checklist"),
            "template": out.relative_to(_ROOT).as_posix(),
            "text": text, "expect": exp, "format": fmt,
            # ⚠️ `text` 是**给人看的**（json 那份会裹在 ``` 代码围栏里）；
            #    `piece` 是**直接能进抽屉的那份内容**。两者不是一回事，别混。
            "piece": (skel if skel is not None else text),
            "put_it_at": "projects/%s/%s/%s" % (DIR_NAME.get(kind, kind), s["drawer"], exp),
            "骨架过判据": (verdict or {}).get("ok"),
            "还差什么才能过": remaining,
            "判据来源": _VALIDATOR_SRC.get(step, "（本步暂无契约判据）"),
            "why_no_skeleton": why,
            "note": "骨架只落 `.scratch/`；抽屉里只认**人填好的真件**。"
                    "**骨架本身不许冒充合格** —— 上面那份「还差什么」就是你要补的。"}


def _synth_tone(path: Path, freq: int, secs: int = 4) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    rc, _o, _e = _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                       "-i", "sine=frequency=%d:duration=%d" % (freq, secs), str(path)], 300)
    return rc == 0


def _synth_clip(path: Path, secs: int = 3, size: str = "1080x1920", label: str = "selftest") -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    rc, _o, _e = _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                       "-i", "testsrc2=size=%s:rate=30:duration=%d" % (size, secs),
                       "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], 600)
    return rc == 0


# ══ 🔴 2026-10-09 质量接线（护照 fc-20261009T093626-0a66）══════════════════════
# 病根：闭环虽通，机器步产的是**占位件** —— `testsrc2` 3 秒彩条 + 440/660Hz 正弦；
#       而 `drama.parse_timed` 验过的**脚本时长**、《夜航》验过的 **MIDI 编曲**，
#       一个都没进成品 ⇒「跑通」与「有作品」之间差着**整条内容接线**。
# 三条修法：① 成片时长由**脚本**定（不再写死 3s）；② 画面是设计过的动效 + 烧进标题/字幕；
#          ③ 音乐由 **MIDI 编曲真渲染**（不是正弦）。
# ⚠️ 这里存**未转义**的原生路径 —— 转义由 `_design_clip.esc()` 统一做。
#    实测踩坑：常量里先写了 `C\:`，esc 又把 `\` 换成 `/` ⇒ 变成 `C/:/Windows/...`，
#    drawtext 拿着畸形字体路径**直接 ACCESS_VIOLATION**（rc=0xC0000005），不是报错而是崩。
_FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"
_FONT_REG = "C:/Windows/Fonts/msyh.ttc"
# 程序号 → (衰减常数秒, 谐波权重)。粗分三族：键盘 / 拨弦 / 低音。
_INSTR = {0: (0.55, (1.0, 0.45, 0.22, 0.10)), 4: (0.85, (1.0, 0.35, 0.12)),
          24: (0.45, (1.0, 0.50, 0.25, 0.12, 0.06)), 25: (0.45, (1.0, 0.50, 0.25, 0.12)),
          32: (1.10, (1.0, 0.28, 0.09)), 48: (1.30, (1.0, 0.40, 0.15))}


def _midi_events(raw: bytes):
    """解析 Standard MIDI File 的**音符事件**（`_parse_midi` 只回计数，渲染要用事件）。"""
    import struct as _st
    if raw[:4] != b"MThd":
        return None
    fmt, ntrk, div = _st.unpack(">HHH", raw[8:14])
    pos, tempo = 14, 500000
    notes, programs = [], {}
    for _ in range(ntrk):
        if raw[pos:pos + 4] != b"MTrk":
            break
        ln = _st.unpack(">I", raw[pos + 4:pos + 8])[0]
        end, i, t, status = pos + 8 + ln, pos + 8, 0, 0
        live = {}
        while i < end:
            d = 0
            while i < end:
                b = raw[i]; i += 1
                d = (d << 7) | (b & 0x7F)
                if not (b & 0x80):
                    break
            t += d
            if i >= end:
                break
            b0 = raw[i]
            if b0 == 0xFF:
                typ, ln2 = raw[i + 1], raw[i + 2]
                data = raw[i + 3:i + 3 + ln2]; i += 3 + ln2
                if typ == 0x51 and len(data) == 3:
                    tempo = (data[0] << 16) | (data[1] << 8) | data[2]
                continue
            if b0 in (0xF0, 0xF7):
                i += 2 + raw[i + 1]
                continue
            if b0 & 0x80:
                status = b0; i += 1
            hi, ch = status & 0xF0, status & 0x0F
            if hi in (0x80, 0x90, 0xA0, 0xB0, 0xE0):
                p1, p2 = raw[i], raw[i + 1]; i += 2
            elif hi in (0xC0, 0xD0):
                p1, p2 = raw[i], 0; i += 1
            else:
                break
            if hi == 0x90 and p2 > 0:
                live[(ch, p1)] = t
            elif hi in (0x80, 0x90):
                st = live.pop((ch, p1), None)
                if st is not None:
                    notes.append((ch, p1, st, max(1, t - st)))
            elif hi == 0xC0:
                programs[ch] = p1
        pos = end
    return {"format": fmt, "division": div or 480, "tempo": tempo,
            "notes": notes, "programs": programs}


def _render_arrangement(mid_path, out_path) -> dict:
    """把**验过的 MIDI 编曲**真渲染成音频（numpy 加法合成 → 16bit 立体声 WAV）。"""
    import numpy as _np
    import wave as _wave
    raw = Path(mid_path).read_bytes()
    m = _midi_events(raw)
    if not m or not m["notes"]:
        return {"ok": False, "error": "MIDI 解析不出音符事件"}
    sr = 44100
    spb = m["tempo"] / 1e6                          # 秒/拍（tempo 存的是 µs/拍）
    tps = spb / m["division"]                       # 秒/tick
    end = max(s + d for _c, _p, s, d in m["notes"]) * tps + 1.6
    n = int(end * sr)
    buf = _np.zeros((n, 2), dtype=_np.float64)
    for ch, pitch, s, d in m["notes"]:
        tau, harm = _INSTR.get(m["programs"].get(ch, 0), (0.6, (1.0, 0.4, 0.15)))
        freq = 440.0 * 2 ** ((pitch - 69) / 12.0)
        i0 = int(s * tps * sr); i1 = min(n, int((s + d) * tps * sr) + int(0.7 * sr))
        if i1 <= i0:
            continue
        tt = _np.arange(i1 - i0) / sr
        env = _np.exp(-tt / tau) * _np.minimum(1.0, tt / 0.012)
        w = _np.zeros_like(tt)
        for k, amp in enumerate(harm, start=1):
            w += amp * _np.sin(2 * _np.pi * freq * k * tt)
        w *= env
        pan = 0.5 + 0.30 * (0.5 - (ch % 3) / 2.0)
        buf[i0:i1, 0] += w * (1.0 - pan)
        buf[i0:i1, 1] += w * pan
    peak = float(_np.max(_np.abs(buf))) or 1.0
    buf = _np.tanh(buf / peak * 1.15) * 0.89
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with _wave.open(str(out_path), "wb") as f:
        f.setnchannels(2); f.setsampwidth(2); f.setframerate(sr)
        f.writeframes((buf * 32767).astype("<i2").tobytes())
    return {"ok": True, "out": str(out_path), "seconds": round(end, 2),
            "notes": len(m["notes"]), "bpm": round(60_000_000.0 / m["tempo"], 1),
            "programs": m["programs"]}


def _script_lines(rel_path) -> list:
    """从**定时分镜稿**里取每镜的小标题做字幕（取不到退回描述前 18 字）。"""
    try:
        txt = (_ROOT / str(rel_path)).read_text(encoding="utf-8", errors="replace")
        from .. import drama as _drama
        r = _drama.parse_timed(txt)
        out = []
        for s in (r.get("shots") or []):
            t = str(s.get("title") or "").strip() or " ".join(str(s.get("desc") or "").split())[:18]
            if t:
                out.append(t)
        return out
    except Exception:                                              # noqa: BLE001
        return []


def _ambient_bed(path: Path, secs: float) -> dict:
    """给电影声轨铺一条**有时长的和声垫**（不是 4 秒正弦）—— A 小调开放和弦 + 缓慢呼吸。"""
    import numpy as _np
    import wave as _wave
    sr = 44100
    n = max(sr, int(float(secs) * sr))
    tt = _np.arange(n) / sr
    sig = _np.zeros(n)
    for k, (f, a) in enumerate(((110.0, 1.0), (164.81, 0.55), (220.0, 0.42), (329.63, 0.26))):
        sig += a * _np.sin(2 * _np.pi * f * tt + k * 0.7)
    breath = 0.72 + 0.28 * _np.sin(2 * _np.pi * tt / 7.5)
    sig = _np.tanh(sig * breath / 1.8) * 0.82
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with _wave.open(str(path), "wb") as f:
        f.setnchannels(2); f.setsampwidth(2); f.setframerate(sr)
        st = _np.stack([sig, sig * 0.94], axis=1)
        f.writeframes((st * 32767).astype("<i2").tobytes())
    return {"ok": True, "seconds": round(float(secs), 2), "out": str(path)}


# ── U0001f534 集间首尾相连（主人令 2026-10-09）──────────────────────────
# 主人原话：「短视频记得每一集首尾相连对齐」。
# 口径：第 N+1 集的**首镜必须接着第 N 集尾镜的调色**（不是另起一个色）；
# 集内/集间一律**硬切**，只有整部系列的首集才淡入。尾镜调色落
# `.scratch/_media_run_series.json`，下一集读它当 anchor —— 机器判据，不是口头承诺。
_SERIES_MEM = _ROOT / ".scratch" / "_media_run_series.json"


def _ep_prev(work: str):
    """从「<...>-epNN」推出上一集名；不是系列集则 None。"""
    m = re.search(r"-ep(\d{1,3})$", str(work or ""))
    if not m:
        return None, 0
    n = int(m.group(1))
    return ((str(work)[:m.start()] + "-ep%02d" % (n - 1)) if n > 1 else None), n


def _series_read() -> dict:
    import json as _json
    try:
        return _json.loads(_SERIES_MEM.read_text(encoding="utf-8")) or {}
    except Exception:                                              # noqa: BLE001
        return {}


def _series_remember(work: str, tail) -> None:
    import json as _json
    mem = _series_read()
    mem[str(work)] = {"tail_palette": list(tail or []), "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    try:
        _SERIES_MEM.parent.mkdir(parents=True, exist_ok=True)
        _SERIES_MEM.write_text(_json.dumps(mem, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def _ep_anchor(work: str) -> dict:
    """给当前集算出：上一集尾调色（anchor）· 是不是首集（淡入）。"""
    prev, n = _ep_prev(work)
    mem = _series_read()
    anc = (mem.get(prev) or {}).get("tail_palette") if prev else None
    return {"episode": n or None, "prev": prev, "anchor": anc,
            "is_first": bool(n == 1), "remembered": bool(anc)}


# U0001f534 2026-10-09 第 2 轮（交付 QC 红在这里）：原调色对**太暗**，
#    `blackdetect=pix_th=0.06` 把 luma<15 的像素算黑（默认 98% 像素黑就判整帧黑），
#    而 #080D1A / #0A1018 这些基色连亮度 15 都不到 ⇒ 整片被判「黑帧」。
#    不是判据太严 —— 是**曝光不合格**（正常成片不该整帧贴着黑）。现把基色提到 luma 30+ 区间，
#    同时保留「冷蓝为底、情绪决定偏色」的设计口径。
_EMO_PAL = {
    "好奇": ("0x14243C", "0x2E5480"), "紧张": ("0x2A1830", "0x5A2A50"),
    "压抑": ("0x18202E", "0x2E4258"), "震惊": ("0x301A28", "0x6A2A48"),
    "温柔": ("0x2A2038", "0x5A3A66"), "兴奋": ("0x30240E", "0x7A5220"),
    "平静": ("0x18222E", "0x3A5068"), "温暖": ("0x302610", "0x6A4E24"),
    "悲伤": ("0x1A1E2E", "0x36405A"), "愤怒": ("0x301410", "0x6A2820"),
    "恐惧": ("0x181428", "0x3A2452"),
    "默认": ("0x1A2436", "0x36506E"),
}


def _script_shots(rel_path) -> list:
    """从定时分镜稿取**逐镜**字段（标题/景别/运镜/情绪/起止）。"""
    try:
        txt = (_ROOT / str(rel_path)).read_text(encoding="utf-8", errors="replace")
        from .. import drama as _drama
        r = _drama.parse_timed(txt)
        out = []
        for s in (r.get("shots") or []):
            out.append({"title": str(s.get("title") or "").strip() or "镜%s" % s.get("idx"),
                        "t0": float(s.get("t0") or 0), "t1": float(s.get("t1") or 0),
                        "shot_size": str(s.get("shot_size") or ""),
                        "camera": str(s.get("camera") or ""),
                        "emotion": str(s.get("emotion") or "")})
        return out
    except Exception:                                              # noqa: BLE001
        return []


def _design_clip(path: Path, secs: float, size: str, title: str, lines=None,
                 shots=None, anchor=None, fade_in=False, fade_out=False, plates=None) -> dict:
    """设计版动效成片（**逐镜段**）。

    两种模式：
      · 分镜化（给了 shots）：每一镜一段——底色由该镜的**情绪**决定，
        渐变方向逐镜变化，底部字幕是该镜小标题，上方标「景别·运镜」。
      · 退化模式（只有 lines）：单片渐变 + 逐行字幕（保留兼容）。

    🔴 集间首尾相连（主人令 2026-10-09）：
      · anchor = 上一集尾镜的调色对 [c0, c1]；给了就让**本集首镜**接着它。
      · fade_in / fade_out 默认 False：集内与集间一律**硬切**，只有整部系列的首/末集才淡入淡出。
      · 返回里带 tail_palette，给下一集当 anchor 用。
    """
    w, h = (int(x) for x in str(size).lower().split("x"))
    path.parent.mkdir(parents=True, exist_ok=True)
    tdir = _ROOT / ".scratch" / "_media_run_txt"
    tdir.mkdir(parents=True, exist_ok=True)
    esc = lambda s: str(s).replace("\\", "/").replace(":", "\\:")   # noqa: E731
    _seq = [0]

    def _tf(text):
        _seq[0] += 1
        f = tdir / ("t%04d.txt" % _seq[0])
        f.write_text(text, encoding="utf-8")
        return esc(f)

    def _dt(text, px, y, color="0xEAF2FF", bold=True, enable=None):
        if not str(text or "").strip():
            return ""
        return ("drawtext=fontfile='%s':textfile='%s':fontcolor=%s:fontsize=%d:"
                "x=(w-text_w)/2:y=%s%s"
                % (esc(_FONT_BOLD if bold else _FONT_REG), _tf(text), color, px, y,
                   (":enable='%s'" % enable) if enable else ""))

    if shots:
        tmpd = path.parent / ("_work_%s" % path.stem[:20])
        tmpd.mkdir(parents=True, exist_ok=True)
        total = len(shots)
        durs, segs, tail, head, detail = [], [], None, None, []
        for i, sh in enumerate(shots):
            dur = max(1.2, float(sh.get("t1") or 0) - float(sh.get("t0") or 0))
            durs.append(dur)
            if i == 0 and anchor and len(anchor) == 2:
                c0, c1 = str(anchor[0]), str(anchor[1])
            else:
                c0, c1 = _EMO_PAL.get(sh.get("emotion") or "", ("0x080D1A", "0x1B2C4A"))
            if i == 0:
                head = [c0, c1]
            tail = [c0, c1]
            # 逐镜底片必须在**用到它之前**取好：下面淡入那句会引用 _plate
            # （实测只炸第一集：只有它 fade_in=True，短路求值才没提前暴露这个顺序错）。
            _plate = None
            if plates and i < len(plates) and plates[i]:
                _p = _ROOT / str(plates[i])
                if _p.is_file():
                    _plate = _p
            ang = [(w, h), (0, h), (w, 0), (0, 0)][i % 4]
            vf = [_dt(title, max(26, int(h * 0.070)), "h*0.14"),
                  _dt(sh.get("title"), max(20, int(h * 0.042)), "h*0.80", "0xCFE0F5", False),
                  _dt(" · ".join(x for x in (sh.get("shot_size"), sh.get("camera")) if x),
                      max(16, int(h * 0.028)), "h*0.90", "0x8FA8C4", False)]
            # U0001f534 「每一个维度都要细节化」——**每一镜都要有运动**：
            #    静止渐变在本仓自己的交付 QC 里就是「卡帧」（实测 freezedetect 报 8 次）。
            #    逐镜加一次极轻推拉（奇偶镜方向相反）⇒ 每一镜都有真运动，也是节奏细节。
            # U0001f534 第 2 轮：原来用 `min(1+0.0011*on,1.12)` ——**会饱和**：
            #    推到 1.12 之后帧就不再变 ⇒ freezedetect 在尾部咬上（实测 19.03s）。
            #    改成**按本镜帧数线性**：从头到尾一直在动，永不饱和。
            _frames = max(2, int(round(dur * 30)))
            # U0001f534 第 2 轮二修：幅度**必须随本镜时长走**（0.012/秒）。
            #    固定 0.06 时，5s 镜每帧动 0.0004（过），12s 镜只动 0.00017 ⇒
            #    实测电影 26–38s 那一镜 freeze 咬了 5 次。改成恒定**每帧变化率**。
            _amp = round(0.012 * dur, 4)
            _zexpr = (("1+%s*on/%d" % (_amp, _frames)) if i % 2 == 0
                      else ("%s-%s*on/%d" % (round(1 + _amp, 4), _amp, _frames)))
            vf.append("zoompan=z='%s':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=%dx%d:fps=30"
                      % (_zexpr, w, h))
            vf = [v for v in vf if v]
            # 🔴 第 2 轮：`fade` 默认从**纯黑**入 ⇒ blackdetect 在 0–0.2s 咬上；淡入改从**本镜底色**起。
            #    底片模式下**禁淡入**：底片本来就不是黑场，集间又要求硬切 ⇒ 直接硬起。
            if i == 0 and fade_in and _plate is None:
                vf.append("fade=t=in:st=0:d=0.5:color=%s" % c0)
            if i == total - 1 and fade_out:
                vf.append("fade=t=out:st=%.2f:d=0.7" % max(0.1, dur - 0.7))
            seg = tmpd / ("seg%02d.mp4" % i)
            # 🔴 2026-10-09：有**真 3D 底片**（Blender 逐镜出图）就用底片，没有才退回渐变。
            #    底片走 `-loop 1` 当静帧源，前面先 scale+crop 铺满画布，再叠字幕/推拉。
            if _plate is not None:
                ins = ["-loop", "1", "-framerate", "30", "-t", "%.2f" % dur, "-i", str(_plate)]
                vf.insert(0, "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d" % (w, h, w, h))
            else:
                ins = ["-f", "lavfi", "-i",
                       ("gradients=s=%dx%d:d=%.2f:c0=%s:c1=%s:x0=0:y0=0:x1=%d:y1=%d:type=linear:rate=30"
                        % (w, h, dur, c0, c1, ang[0], ang[1]))]
            rc, _o, e = _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + ins +
                              ["-vf", ",".join(vf),
                               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                               "-pix_fmt", "yuv420p", "-t", "%.2f" % dur, str(seg)], 900)
            if rc != 0 or not seg.exists():
                return {"ok": False, "rc": rc,
                        "error": "第 %d 镜渲染失败：%s" % (i + 1, (e or "")[:120])}
            segs.append(seg)
            # U0001f534 「每一个维度都要细节化」：**逐镜**记下每一维（时间/景别/运镜/情绪/
            #    调色/字幕/色纪录），落副本侧车 JSON —— 不是只给一个合计数。
            detail.append({"no": i + 1, "t0": round(float(sh.get("t0") or 0), 2),
                           "t1": round(float(sh.get("t1") or 0), 2), "dur": round(dur, 2),
                           "title": sh.get("title") or "", "shot_size": sh.get("shot_size") or "",
                           "camera": sh.get("camera") or "", "emotion": sh.get("emotion") or "",
                           "palette": [c0, c1], "gradient_axis": [ang[0], ang[1]],
                           "subtitle": sh.get("title") or "",
                           "corner_label": " · ".join(x for x in (sh.get("shot_size"), sh.get("camera")) if x),
                           "anchored_from_prev": bool(i == 0 and anchor),
                            "plate": (str(_plate) if _plate else None)})
        lst = tmpd / "list.txt"
        # ⚠️ concat demuxer 把 `file` 路径当**相对于清单文件所在目录**解析 ——
        #    用相对路径会拼成 `.scratch/_work_x/.scratch/_work_x/seg00.mp4`（实测报
        #    Impossible to open）。必须给**绝对路径**（配 -safe 0）。
        lst.write_text("".join("file '%s'\n" % s.resolve().as_posix() for s in segs), encoding="utf-8")
        rc, _o, e = _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                          "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(path)], 900)
        for s in segs:
            try:
                s.unlink()
            except OSError:
                pass
        try:
            lst.unlink(); tmpd.rmdir()
        except OSError:
            pass
        # ⚠️ 侧车不能落抽屉：抽屉有命名家规（`\d{8}-<方向>-<作品>-<NN工序>.<ext>`），
        #    `x.mp4.shots.json` 不合规 ⇒ 会被闸门当成不合格件。放 `.scratch/`，详情本身不变。
        side = _ROOT / ".scratch" / "_media_run_shots" / (path.stem + ".shots.json")
        try:
            side.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            side = None
        try:
            import json as _json
            side.write_text(_json.dumps({"schema": "gbt-media-shots/v1", "clip": path.name,
                                         "title": title, "segments": detail},
                                        ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            side = None
        return {"ok": rc == 0 and path.exists(), "out": str(path),
                "shots_manifest": (str(side) if side else None),
                "shots": detail,
                "seconds": round(sum(durs), 2), "title": title,
                "segments": total, "mode": "per_shot",
                "head_palette": head, "tail_palette": tail, "concat_err": (e or "")[:200],
                "anchored": bool(anchor), "fade_in": bool(fade_in),
                "fade_out": bool(fade_out), "rc": rc}

    vf = [_dt(title, max(28, int(h * 0.075)), "h*0.18")]
    n_lines = max(1, len(lines or []))
    step = float(secs) / n_lines
    for i, ln in enumerate(lines or []):
        vf.append(_dt(ln, max(20, int(h * 0.040)), "h*0.80", "0xCFE0F5", False,
                      "between(t,%.2f,%.2f)" % (i * step, (i + 1) * step)))
    vf.append("fade=t=in:st=0:d=0.6,fade=t=out:st=%.2f:d=0.8" % max(0.1, float(secs) - 0.8))
    src = ("gradients=s=%dx%d:d=%.2f:c0=0x080D1A:c1=0x1B2C4A:x0=0:y0=0:x1=%d:y1=%d:"
           "type=linear:rate=30" % (w, h, float(secs), w, h))
    rc, _o, _e = _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                       "-f", "lavfi", "-i", src, "-vf", ",".join([v for v in vf if v]),
                       "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                       "-pix_fmt", "yuv420p", "-t", "%.2f" % float(secs), str(path)], 1800)
    return {"ok": rc == 0, "out": str(path), "seconds": round(float(secs), 2),
            "title": title, "subtitle_lines": len(lines or []), "mode": "single", "rc": rc}


# ══ 🔴 2026-10-09 · 音视频**钢印**（objective 要的「带钢印」在媒体上落不了地）══════════
# 病根：本仓 `signature` 钢印只覆盖文本页（.md/.html/.htm/.txt/.csv）；音视频**不在它范围内**。
#       实测三件成品 `ffprobe format_tags` 只有 `encoder=Lavf…` ⇒ **作品没有出处**。
#       钢印纪律是「不可伪造归属、不可移除出处」，它必须同样落在媒体上。
# 做法：把署名写进容器元数据（title/artist/album/comment/description），并**回读校验**——
#       不是许愿：`verified` 是 ffprobe 真读回来的。
_SIG_LINE = "开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"
_STAMPABLE = (".mp4", ".mov", ".mkv", ".wav", ".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus")


def _quintet(step: str, cap, got, v, res, rel, upstream) -> dict:
    """逐步细节化·五问（习惯的机器化落点，由 `tools/codex-scripts/detail-check.py` 咬）。

    输入 / 动作 / 明细 / 判据 / 接点 —— **明细一律逐项**，不许只报合计。
    """
    r = res or {}
    if got:
        return {"输入": {"件": got, "类型": "人填真件（输入口）"},
                "动作": "收下真件" + ("，过一遍契约判据" if v else "（无校验器：只判在场 + 命名合家规）"),
                "明细": (v or {}).get("criteria") or [{"项": "件在场且命名合家规", "值": got}],
                "判据": {"过": bool((v or {}).get("ok", True)),
                          "出处": (v or {}).get("validator") or "NAME_RE + 真件在场"},
                "接点": got}
    detail = []
    if r.get("shots"):
        detail = [{"镜": x.get("no"), "秒": x.get("dur"), "景别": x.get("shot_size"),
                   "运镜": x.get("camera"), "情绪": x.get("emotion"), "调色": x.get("palette"),
                   "字幕": x.get("subtitle")} for x in (r.get("shots") or [])]
    elif r.get("dimensions"):
        import json as _json
        detail = [{"维": k, "值": _json.dumps(vv, ensure_ascii=False)[:200]}
                  for k, vv in (r.get("dimensions") or {}).items() if vv]
    elif r.get("render"):
        rr = r["render"]
        detail = [{"音符": rr.get("notes"), "BPM": rr.get("bpm"), "秒": rr.get("seconds")},
                  {"来源编曲": r.get("from_arrangement")}]
    elif r.get("gbt_stamp"):
        detail = [{"标签": k, "值": str(vv)[:90]}
                  for k, vv in ((r.get("gbt_stamp") or {}).get("tags") or {}).items()]
    elif r.get("package"):
        detail = [{"发布包": r.get("package"), "产物": r.get("product"),
                  "预检": (r.get("preflight") or {})}]
    if not detail:
        detail = [{"产物": rel, "cap": cap, "字节": r.get("bytes")}]
    return {"输入": {"上游": upstream or "本仓自产（ffmpeg）"},
            "动作": str(cap or "人工") + ("（" + str(v.get("validator")) + "）" if v else ""),
            "明细": detail,
            "判据": {"过": bool(r.get("ok", v.get("ok") if v else True)),
                      "出处": (v or {}).get("validator") or ("step=%s（自报 ok）" % step)},
            "接点": rel}


def _style_intent(rel_path) -> str:
    """从分镜契约的 `style` 字段取「意图」——灯光/调色的输入。取不到就给 filmic。"""
    try:
        import json as _json
        d = _json.loads((_ROOT / str(rel_path)).read_text(encoding="utf-8", errors="replace"))
        return str(d.get("style") or "").strip() or "filmic"
    except Exception:                                              # noqa: BLE001
        return "filmic"


def _apply_grade(path, intent: str) -> dict:
    """**灯光师·调色师 + 修饰师**：把人话交给共用外观库 `filmgrade`，全片过一遍外观链。

    ⚠️ 这是**真调色**：`filmgrade.LOOKS` 每条都是完整 ffmpeg 滤镜图
    （curves/colorbalance/eq → cas 锐化 → gblur+blend 辉光 → vignette 暗角 → noise 颗粒），
    不是给画面贴个标签。读数全部现算：哪个味、怎么取的味、修饰五科目在不在、QC 结果。
    """
    try:
        from importlib.util import module_from_spec, spec_from_file_location
        _spec = spec_from_file_location("gbt_filmgrade", _ROOT / "tools" / "filmgrade.py")
        fg = module_from_spec(_spec)
        _spec.loader.exec_module(fg)
    except Exception as e:                                          # noqa: BLE001
        return {"ok": False, "error": "filmgrade 装不上：%s" % str(e)[:90]}
    ex = fg.pick_explain(intent)
    look = ex["look"]
    chain = fg.grade_chain(look)
    from pathlib import Path as _P
    p = _P(str(path))
    tmp = p.with_name(p.stem + ".__grade" + p.suffix)
    rc, _o, err = _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(p),
                        "-vf", chain, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-pix_fmt", "yuv420p", "-c:a", "copy", str(tmp)], 900)
    if rc != 0 or not tmp.exists() or tmp.stat().st_size == 0:
        try:
            tmp.unlink()
        except OSError:
            pass
        return {"ok": False, "look": look, "error": (err or "调色失败")[:140]}
    tmp.replace(p)
    finish = {"sharpen_cas": "cas=" in chain,
              "bloom": ("gblur" in chain and "blend" in chain),
              "vignette": "vignette" in chain,
              "grain": "noise=" in chain,
              "grain_amount": (fg.default_grain() if "noise=" in chain else 0),
              "contrast_curve": "curves=" in chain,
              "color_balance": "colorbalance=" in chain}
    try:
        q = fg.qc(p, label=p.name)
    except Exception as e:                                          # noqa: BLE001
        q = {"ok": False, "error": str(e)[:90]}
    return {"ok": True, "intent": intent, "look": look, "how": ex["how"],
            "chain": chain[:220], "finish": finish, "qc": q, "bytes": p.stat().st_size}


def _read_media_tags(path) -> dict:
    """ffprobe 现读容器标签（钢印校验的唯一依据，不是我自己记的）。"""
    import json as _json
    rc, out, _err = _run(["ffprobe", "-v", "error", "-show_entries", "format_tags",
                          "-of", "json", str(path)], 60)
    if rc != 0:
        return {}
    try:
        return (_json.loads(out or "{}").get("format") or {}).get("tags") or {}
    except Exception:                                              # noqa: BLE001
        return {}


def _stamp_media(path, work: str, kind: str, step: str) -> dict:
    """给音视频产物打 GBT 钢印（写容器元数据 + 回读校验）。非可打类型如实返回 skipped。"""
    from pathlib import Path as _P
    p = _P(str(path))
    if p.suffix.lower() not in _STAMPABLE:
        return {"ok": False, "skipped": True, "why": "该类型不打容器钢印：%s" % p.suffix}
    tmp = p.with_name(p.stem + ".__stamp" + p.suffix)
    meta = ["-metadata", "title=%s" % work,
            "-metadata", "artist=自由的风 · GBT小土豆V8",
            "-metadata", "album=GBT小土豆V8 · %s" % kind,
            "-metadata", "comment=%s" % _SIG_LINE,
            "-metadata", "description=%s" % ("%s/%s · %s" % (kind, step, _SIG_LINE))]
    # ⚠️ `-map_metadata -1` 先**清掉旧标签**再写 —— 否则 FLAC/Vorbis 会把新 comment 追加到旧的后面
    #    （实测变成 `music/export · 开发者…;开发者…`），既不是幂等也读不准。
    rc, _o, err = _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(p),
                        "-map", "0", "-c", "copy", "-map_metadata", "-1"] + meta + [str(tmp)], 300)
    if rc != 0 or not tmp.exists() or tmp.stat().st_size == 0:
        try:
            tmp.unlink()
        except OSError:
            pass
        return {"ok": False, "error": (err or "ffmpeg 打钢印失败")[:140]}
    tmp.replace(p)
    tags = _read_media_tags(p)
    # ⚠️ 判据是「**读回来的标签里有钢印**」，不是「comment 以它开头」：
    #    实测 FLAC 会把 description 并进 comment（`a;b`），startswith 会假红。
    _blob = " ".join(str(v) for v in tags.values())
    verified = "开发者：自由的风" in _blob and "不可篡改归属" in _blob
    return {"ok": verified, "verified": verified, "tags": tags,
            "bytes": p.stat().st_size}

def _register(path: Path, kind: str, step: str, src_note: str) -> dict:
    return lic_run("register", file=str(path),
                   source=src_note,
                   license="自有（本机 ffmpeg 自产，无第三方素材，零出网）",
                   note="三方向工作流自检件 · %s/%s（**彩排，非作品**）" % (KIND_CN.get(kind, kind), step))


def plan(kind: str) -> dict:
    steps = CHAINS.get(kind)
    if not steps:
        return {"ok": False, "error": "不认的方向 %r（认这些：%s）" % (kind, "、".join(CHAINS))}
    return {"ok": True, "kind": kind, "label": KIND_CN.get(kind, kind),
            "steps": [{"step": s["step"], "drawer": s["drawer"], "ext": s["ext"],
                       "cap": s["cap"], "runnable": bool(s["cap"]),
                       "needs_input": bool(s.get("human")),
                       "fields": s.get("fields") or [],
                       "why": s.get("why", "")} for s in steps],
            "note": "`runnable=False` 分两种：**`needs_input=True`** = 人的活，**它是链里的输入口**"
                    "（模板落 `.scratch/`，人填好放进抽屉即算过）；"
                    "`needs_input=False` = 本机还没有实现器。执行时三种状态分开报，**不许当成「跑过了」**。"}


def _run_chain(kind: str, work: str, keep_stems: bool = True,
               release: bool = False) -> dict:
    steps = CHAINS[kind]
    stem_dir = STEM_DIR
    report = []
    ctx = {}
    last_out = ""          # 五问的「输入」用它：上一步真落的件
    for idx, s in enumerate(steps, 1):
        step, drawer, ext, cap = s["step"], s["drawer"], s["ext"], s["cap"]
        if not cap:
            # 人写的步 = **输入口**：抽屉里有真件 ⇒ 这步算过；没有 ⇒ 报「待输入」。
            if s.get("human"):
                got = _filed_input(kind, drawer, work, idx, step, ext)
                if got:
                    # 有校验器的人写步：**再拿框架自己的判据过一遍**（在场 ≠ 合格 → 契约判据）
                    if step in _VALIDATORS:
                        src = _VALIDATOR_SRC.get(step, step)
                        try:
                            if step in _VALIDATOR_BINARY:
                                # 🔴 二进制件（`.mid`/`.als`/`.flp`）**不能按文本读** ——
                                #    `read_text(errors="replace")` 会把字节换成 U+FFFD，件当场废掉。
                                v = _VALIDATORS[step](got, (_ROOT / got).read_bytes())
                            elif step in _VALIDATOR_KINDED:
                                # 要分方向的判据（`concept` 的 craft 每个方向不一样）
                                v = _VALIDATORS[step](
                                    kind, (_ROOT / got).read_text(encoding="utf-8",
                                                                  errors="replace"))
                            else:
                                v = _VALIDATORS[step](
                                    (_ROOT / got).read_text(encoding="utf-8", errors="replace"))
                        except OSError as e:
                            report.append({"step": step, "status": "input_rejected", "input": got,
                                           "why": "读不动这个文件：%s" % str(e)[:80]})
                            continue
                        if v.get("unjudgeable"):
                            # **独立状态**：件在、格式也合法，但本机没有解析器。
                            # 既不是 `ran`（不许冒充合格）也不是 `input_rejected`（不是它的错）。
                            report.append({"step": step, "status": "input_unjudged", "input": got,
                                           "validation": v,
                                           "why": "件在、格式合法，但**本机判不了** —— 判据来源：%s ｜ %s"
                                                  % (src, v.get("error") or "没有解析器")})
                            continue
                        if not v.get("ok"):
                            report.append({"step": step, "status": "input_rejected", "input": got,
                                           "validation": v,
                                           "why": "**件在，但没过判据** —— 判据来源：%s ｜ %s"
                                                  % (src, v.get("error") or "判据未通过")})
                            continue
                        ctx[step] = got
                        ctx[step + "_v"] = v          # 判据读数留给下游（时长/字幕要用它）
                        report.append({"step": step, "status": "ran", "input": got,
                                       "validation": v,
                                       "详细": _quintet(step, None, got, v, None, got, last_out),
                                       "note": "输入已就位**且过了它的判据**（来源：%s）" % src})
                        continue
                    ctx[step] = got
                    report.append({"step": step, "status": "ran", "input": got,
                                   "note": "输入已就位（**人填的真件**在抽屉里）"})
                    continue
                report.append({"step": step, "status": "awaiting_input",
                               "drawer": "projects/%s/%s" % (DIR_NAME.get(kind, kind), drawer),
                               "expect": _expect_name(kind, work, idx, step, ext),
                               "fields": s.get("fields") or [],
                               # 红步也要答满五问（习惯不挑状态）：明细就是**缺哪些字段**，逐条列
                               "详细": {"输入": {"抽屉": "projects/%s/%s" % (DIR_NAME.get(kind, kind), drawer),
                                                  "期望件": _expect_name(kind, work, idx, step, ext)},
                                        "动作": "没做 —— 这一步是**输入口**，等真件",
                                        "明细": [{"缺字段": f} for f in (s.get("fields") or [])] or [{"缺": "真件"}],
                                        "判据": {"过": False, "出处": "NAME_RE + 真件在场（抽屉里没有合规件）"},
                                        "接点": _expect_name(kind, work, idx, step, ext)},
                               "scaffold_cmd": "media_run template kind=%s step=%s" % (kind, step),
                               "why": s.get("why", "")})
                continue
            report.append({"step": step, "status": "not_implemented", "why": s.get("why", "")})
            continue
        # ── 发布步（2026-09-23 第 54 轮加）：**自动化的终点站** ──
        #    把发布包备好（元数据/许可/目标平台/闸清单），然后**停在主人的授权门**前。
        #    状态用 `prepared`（不是 `ran`）—— 因为"备好了"与"发出去了"是两件事，
        #    这个区别必须写在状态里，否则读的人会把"备好"读成"已发布"。
        if cap == "media_publish.prepare":
            prev = ctx.get("export") or ctx.get("edit") or ctx.get("master")
            if not prev:
                report.append({"step": step, "status": "failed", "why": "上一步没有可发布的产物"})
                continue
            from .media_publish import run as mp_run
            pr = mp_run("prepare", kind=kind, product=prev, title=work,
                        desc="三方向工作流自检件（彩排件；正式件不带 -rehearsal）",
                        tags=["selftest", kind])
            sr = mp_run("submit", kind=kind, package=pr.get("package") or "")
            report.append({"step": step,
                           "status": "prepared" if pr.get("ok") else "failed",
                           "详细": {"输入": {"上游": prev},
                                    "动作": "备发布包 + 走 submit（**恒停在主人授权门**）",
                                    "明细": [{"发布包": pr.get("package")}, {"产物": prev},
                                              {"预检": pr.get("preflight")},
                                              {"闸": {"blocked": sr.get("blocked"),
                                                      "reason": sr.get("reason")}}],
                                    "判据": {"过": bool(pr.get("ok")),
                                            "出处": "media_publish.prepare + submit(blocked)"},
                                    "接点": pr.get("package")},
                           "cap": cap, "package": pr.get("package"),
                           "product": prev,
                           "ready_for_owner_review": pr.get("ready_for_owner_review"),
                           "preflight": pr.get("preflight"),
                           "gate": {"blocked": sr.get("blocked"), "reason": sr.get("reason"),
                                    "owner_actions": sr.get("owner_actions")}})
            continue
        # 🔴 **成品名 vs 彩排名**（第 79 轮）：`_name()` 永远吐 `-rehearsal` ⇒
        #    哪怕三条链全绿跑完，闸门看到的仍是「**只有彩排件，没有该工序成品**」
        #    —— 链子**结构上产不出成品**，闭环的最后一环没接上。
        #    ⇒ `release=True` 时改吐**工序成品名**（`NNstep` 形式）。
        #    ⚠️ 这只表示"落成工序成品名"，**不代表可发布**：发布仍卡主人授权门（`publish` 那步）。
        if release:
            rel = "projects/%s/%s/%s" % (DIR_NAME.get(kind, kind), drawer,
                                        _expect_name(kind, work, idx, step, ext))
        else:
            rel = "projects/%s/%s/%s" % (DIR_NAME.get(kind, kind), drawer,
                                        _name(kind, work, step, ext))
        g = write_guard(rel)
        if not g.get("ok"):
            report.append({"step": step, "status": "refused", "why": g["why"]})
            continue
        dst = Path(g["abs"])
        t0 = time.time()
        try:
            if cap == "ffmpeg.lavfi" and ext == "wav":
                ok = _synth_tone(dst, 440, 4)
                res = {"ok": ok, "out": rel}
            elif cap == "ffmpeg.lavfi":
                # 🔴 2026-10-09 质量接线（护照 fc-20261009T093626-0a66）：时长取**脚本判据
                #    读出的 total_dur**，画面换成设计版动效 + 烧进标题/逐镜字幕
                #    （原来写死 3 秒 `testsrc2` 彩条 —— 那不是作品，是占位）。
                sv = ctx.get("script_v") or {}
                secs = float(sv.get("total_dur") or 0) or 6.0
                size = "1080x1920" if kind == "short_video" else "1920x1080"
                lines = _script_lines(ctx.get("script") or "")
                shots = _script_shots(ctx.get("script") or "")
                ep = _ep_anchor(work)
                # 逐镜底片（Blender 出图）：`projects/<方向>/_plates/<作品>/shotNN.png`
                _pdir = _ROOT / "projects" / DIR_NAME.get(kind, kind) / "_plates" / work
                _plates = (["projects/%s/_plates/%s/shot%02d.png"
                            % (DIR_NAME.get(kind, kind), work, i + 1) for i in range(len(shots))]
                           if (shots and _pdir.is_dir()) else None)
                res = _design_clip(dst, secs, size, work, lines, shots=shots or None,
                                   anchor=ep.get("anchor"), fade_in=bool(ep.get("is_first")),
                                   fade_out=False, plates=_plates)
                ok = bool(res.get("ok"))
                if ok:
                    ctx["clip_secs"] = res.get("seconds") or secs
                    res["script_secs"] = secs
                    res["subtitle_source"] = ctx.get("script") or ""
                    res["episode"] = ep
                    if res.get("tail_palette"):
                        _series_remember(work, res["tail_palette"])   # 为下一集留接点
            elif (cap == "audio_mix.mix" and kind == "music"
                  and str(ctx.get("arrangement") or "").lower().endswith((".mid", ".midi"))):
                # 🔴 2026-10-09 质量接线：音乐链的 audio 步**必须把验过的 MIDI 编曲真渲染出来**。
                #    原来这一步产的是 440/660Hz 正弦 —— 编曲判据 A1–A7 过了，声音里却**一个音都没有**。
                rendered = stem_dir / ("arr-%s-%s.wav" % (kind, work))
                rr = _render_arrangement(_ROOT / ctx["arrangement"], rendered)
                if not rr.get("ok"):
                    raise RuntimeError("编曲渲染失败：%s" % rr.get("error"))
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(rendered.read_bytes())
                ok = dst.stat().st_size > 0
                res = {"ok": ok, "out": rel, "from_arrangement": ctx["arrangement"],
                       "render": rr, "bytes": dst.stat().st_size}
            elif cap == "audio_mix.mix":
                # 🔴 第 104 轮修：这两个基础轨原名**写死**（`stem-a.wav` / `stem-b.wav`），
                #    而这个目录是**共享**的，`audio_mix.mix` 又是 **music 的 audio 步与
                #    film 的 sound 步共用的实现器** ⇒ 两链**同跑**时，A 可能混到 B 写的基础轨。
                #    最坏的不是报错，而是**"看着对、其实错"**：合成件各自独立，
                #    **产物读数完全看不出来**（第 102 轮没报错，那是运气 —— 真正的风险是读到半个文件）。
                #    ⇒ 按 `kind + work` 分名；同方向同作品并发才可能撞，而那本来就是**同一个活**。
                # 🔴 2026-10-09：电影声轨改铺**有时长的和声垫**（对齐镜头时长），不再 4 秒正弦。
                tag = "%s-%s" % (kind, work)
                bed_secs = float(ctx.get("clip_secs") or 4.0)
                bed = stem_dir / ("bed-%s.wav" % tag)
                bb = _ambient_bed(bed, bed_secs)
                if not bb.get("ok"):
                    raise RuntimeError("和声垫合成失败")
                a = stem_dir / ("stem-a-%s.wav" % tag)
                if not _synth_tone(a, 220, max(4, int(bed_secs))):
                    raise RuntimeError("自产基础轨合成失败")
                res = amix_run("mix", sources=[str(a), str(bed)], volumes=[0.22, 0.78],
                               format="wav", out=rel)
                res["bed_seconds"] = bb.get("seconds")
                ok = bool(res.get("ok"))
            elif cap == "audio_mix.master":
                src = ctx.get("master_src") or ctx.get("audio")
                if not src:
                    raise RuntimeError("上一步没产出可施加的源（audio 那步没跑成？）")
                fmt = "flac" if ext == "flac" else "wav"
                res = amix_run("master", src=src, format=fmt, target="streaming",
                               genre="electronic", out=rel)
                ok = bool(res.get("ok"))
            elif cap == "edit_pipeline.render":
                from . import edit_core as EC
                clip = ctx.get("assets") or ctx.get("shots")
                if not clip:
                    raise RuntimeError("上一步没产出可剪的素材")
                tl = {"version": 1, "unit": "second",
                      "canvas": {"w": 1080 if kind == "short_video" else 1920,
                                 "h": 1920 if kind == "short_video" else 1080,
                                 "fps": 30, "bg": "black"},
                      "tracks": {"video": [{"src": str(_ROOT / clip), "t0": 0.0,
                                            # 🔴 2026-10-09：时长取**素材真时长**（原来写死 3s，
                                            #    与脚本 60s/72s 对不上 ⇒ 成片被截成 3 秒）。
                                            "dur": float(ctx.get("clip_secs") or 3.0),
                                            "src_start": 0.0, "fit": "cover"}]}}
                v = EC.run("validate", timeline=tl)
                if not v.get("ok"):
                    res = {"ok": False, "error": "时间线校验没过", "detail": v}
                    ok = False
                else:
                    res = EC.run("render", timeline=tl, out=rel)
                    ok = bool(res.get("ok"))
                    # 🔴 **渲染完必须清场**（第 53 轮真跑抓到的）：
                    #    `edit_core.render` 会在产物同目录留下中间件（`_gbt_concat.txt`、`_seg00.mp4` …）。
                    #    而抽屉是**有家规的地方**：那些件① 命名不合规 ② 没许可 ⇒
                    #    当场把 `film/05-edit` 判成 P0（"成品格许可没记到件 1/3"）。
                    #    ⇒ 中间件是**过程垃圾**，不该留在抽屉里。清到回收站（可还原），并如实记进报告。
                    if ok:
                        # ⚠️ 中间件在**子目录**里（`_work/`）—— 第一版我只 glob 了一层，
                        #    结果"清出 0 件"而门上照样红：**判据用的是 rglob，我却用 glob**
                        #    （本仓第 N 次"看着对、匹配的是别的东西"）。凡清场一律**递归**。
                        workdirs = [p for p in dst.parent.glob("_*") if p.is_dir()]
                        strays = [p for p in dst.parent.rglob("_*") if p.is_file()]
                        targets = workdirs + strays
                        if targets:
                            try:
                                from importlib.util import module_from_spec, spec_from_file_location
                                _p = _ROOT / "tools" / "codex-scripts" / "clean_residue.py"
                                _s = spec_from_file_location("gbt_cr", _p)
                                _cr = module_from_spec(_s)
                                _s.loader.exec_module(_cr)
                                moved, bad, _skip = _cr._recycle_batch(targets)
                                res["cleaned_intermediates"] = {
                                    "moved": moved, "failed": len(bad),
                                    "names": [p.name for p in targets]}
                            except Exception as ce:                      # noqa: BLE001
                                res["cleaned_intermediates"] = {"error": str(ce)[:120],
                                                                "names": [p.name for p in targets]}
                        # U0001f534 2026-10-09 主人指出的缺口：**灯光师 / 调色 / 修饰全没进工作流**。
                        #    本机其实有共用外观库 `tools/filmgrade.py`（7 种味道 + 词即指令 + QC），
                        #    但三方向链**一次都没调过它** ⇒ 成片是「没打灯、没修过」的原始渲染。
                        #    现在：编辑之后过一遍外观链，并把**每一维的真读数**（哪个味、怎么取的味、
                        #    链长什么样、修饰五科目各自在不在、QC 读数）写进报告。
                        if ok:
                            grade = _apply_grade(dst, _style_intent(ctx.get("storyboard")))
                            res["color_grade"] = grade
                            res["dimensions"] = {
                                "edit": {"engine": "edit_core.render",
                                         "dur": tl["tracks"]["video"][0]["dur"]},
                                "color_grade": {k: grade.get(k) for k in ("intent", "look", "how", "chain")},
                                "finish": grade.get("finish"),
                                "qc": grade.get("qc"),
                            }
                            ok = bool(grade.get("ok"))
            elif cap == "copy.of_edit":
                src = ctx.get("edit") or ctx.get("shots")
                if not src:
                    raise RuntimeError("上一步没产出可导出的成片")
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes((_ROOT / src).read_bytes())
                ok = dst.stat().st_size > 0
                res = {"ok": ok, "out": rel, "bytes": dst.stat().st_size,
                       "copied_from": src}
            else:
                res, ok = {"ok": False, "error": "执行器不认的 cap：%s" % cap}, False
        except Exception as e:                                    # noqa: BLE001
            res, ok = {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:120])}, False
        # 🔴 2026-10-09：**先打钢印再登记许可** —— 否则登记的 sha 是打钢印**之前**的字节，
        #    账↔盘当场对不上（`media_license check` 会报 sha 不一致）。
        if ok:
            res["gbt_stamp"] = _stamp_media(dst, work, kind, step)
            ok = bool(res["gbt_stamp"].get("ok")) or bool(res["gbt_stamp"].get("skipped"))
        entry = {"step": step, "status": "ran" if ok else "failed", "cap": cap, "out": rel,
                 # U0001f534 习惯·逐步细节化：每一步都要答满五问（由 detail-check.py 咬）
                 "详细": _quintet(step, cap, None, None, res, rel,
                                     last_out),
                 "secs": round(time.time() - t0, 1), "result": res}
        if ok:
            ctx[step] = rel
            last_out = rel
            if step == "master":
                ctx["master_src"] = rel
            lic = _register(dst, kind, step, "本仓 ffmpeg 自产：三方向工作流自检（%s 步 %s）" % (kind, step))
            entry["license"] = {"ok": lic.get("ok"), "sha16": (lic.get("entry") or {}).get("sha256", "")[:16]}
        report.append(entry)
    ran = [r for r in report if r["status"] == "ran"]
    prepared = [r for r in report if r["status"] == "prepared"]
    awaiting = [r for r in report if r["status"] == "awaiting_input"]
    return {"ok": bool(ran), "kind": kind, "work": work, "report": report,
            "summary": {"ran": len(ran),
                        "prepared": len(prepared),
                        "awaiting_input": len(awaiting),
                        "failed": len([r for r in report if r["status"] == "failed"]),
                        "not_implemented": len([r for r in report if r["status"] == "not_implemented"]),
                        "total": len(report)},
            "note": "**跑完一遍 ≠ 整条链都通了**：`awaiting_input` 是**人写的步**（模板见 `.scratch/`，"
                    "填好放进抽屉即算过）· `not_implemented` 是本机没有实现器 · "
                    "`prepared` = 发布包备好了、**停在主人的授权门**（不是已发布）。如实分开计数。"}


def run(op: str = "status", **kw) -> dict:
    op = str(op or "status")
    if op == "status":
        return {"ok": True, "impl": "media_run", "version": _IMPL_VERSION,
                "kind": "media_run", "domain": "video",
                "read_ops": list(READ_OPS), "write_ops": list(WRITE_OPS),
                "chains": {k: [s["step"] for s in v] for k, v in CHAINS.items()},
                "runnable_steps": {k: [s["step"] for s in v if s["cap"]] for k, v in CHAINS.items()},
                "ffmpeg": _have("ffmpeg"),
                # 🔴 第 80 轮补：`release` 原来只活在 `run` 的入参里，**面板上点不到** ——
                #    一个没进面板的能力 = 半个能力。写进 status，面板才有得显示。
                "run_params": {
                    "kind": "方向（short_video / film / music）",
                    "work": "作品名（默认 pipeline-selftest）",
                    "release": "布尔。**缺省 false = 彩排**（落 `-rehearsal` 名）；"
                               "true = **工序成品**（落 `NNstep` 名，闸门才看得见「成品」）。"
                               "⚠️ 成品名 **≠ 可发布** —— 发布提交仍卡主人授权门。"},
                "release_note": "`_name()` 只吐彩排名 ⇒ 不加 `release` 时链子**结构上产不出成品**，"
                                "闸门会一直报「只有彩排件，没有该工序成品」。",
                "note": "一次调用跑完一条链；每步落真件 + 同批登记许可；没有实现器的步如实标 not_implemented。"}
    if op == "plan":
        return plan(str(kw.get("kind") or ""))
    if op == "template":
        return scaffold(str(kw.get("kind") or ""), str(kw.get("step") or ""),
                        str(kw.get("work") or "pipeline-selftest"))
    if op == "run":
        kind = str(kw.get("kind") or "")
        if kind not in CHAINS:
            return {"ok": False, "error": "不认的方向 %r（认这些：%s）" % (kind, "、".join(CHAINS))}
        if not _have("ffmpeg"):
            return {"ok": False, "status": "needs_dependency", "missing": "ffmpeg",
                    "why": "本机没有 ffmpeg ⇒ 跑不了（不假装能跑）"}
        return _run_chain(kind, str(kw.get("work") or "pipeline-selftest"),
                          release=bool(kw.get("release")))
    return {"ok": False, "error": "不认的 op：%s（读 %s / 写 %s）"
                                 % (op, "/".join(READ_OPS), "/".join(WRITE_OPS))}
