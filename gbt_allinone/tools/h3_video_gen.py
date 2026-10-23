# gbt-capability: h3_video_gen
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""H3mini 视频生成（h3_video_gen）· R-H250 只读骨架。

主人口径（2026-09-20）：**官方仓库里它就已经是技能了** —— 官方自带 9 个 SKILL.md
（`h3-prompt-writing` 纯 Markdown 零依赖 + 8 个风格化视频生成技能）。
所以本刀的原则是 **引用，不复制**：引用官方仓库与技能名，**不抄它的 SKILL.md 内容**。

四原语（视频生成的四种入口）：
  T2VA  文生视频      I2VA  图生视频      FL2VA 首尾帧      Ref2VA 参考生视频

三条带牙用例（都做成机械闸）：
  ① 密钥不走明文            → `check_no_plaintext_key`
  ② 结果必须落盘            → `check_must_localize`
  ③ 提示词必须走官方六段式   → `check_prompt_structure`（**不接受散文式**）

五条红线（写死）：
  ① 密钥只存 DPAPI（不许明文落盘、不许进返回值）
  ② 结果必须落盘（不许只留远程链接 ⇒ 链接会失效）
  ③ 不绕官方入口（走官方技能/官方 API，不许自己拼请求）
  ④ **硬件门槛先验**（本地跑要 32GB+，峰值 31.7GB ⇒ 先验再跑，验不到就不许说能跑）
  ⑤ 每次操作留痕（trace_store）

🔴 取证读数（R-H250，实测）：显存**读数拿不到**（nvidia-smi 不在 PATH + 沙箱身份下
   Win32_VideoController 被拒）；本机 RAM 7.4GB / 负载 93% ⇒ **本地模式当下不可用**；
   盘上 **0 个可用 MINIMAX_API_KEY**（env 空、DPAPI 无此密钥）⇒ API 模式需主人给钥匙。
   本模块**只登记契约与判据**，不装技能、不出网、不落盘、不发密钥。

来源：**主人提供**（官方仓库 / 四原语 / 六段式 / 硬件门槛 / 9 个 SKILL.md）·
      出网受限 ⇒ 一律标「主人提供 · 未独立取证」，不写进「已确认」。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

CAP_KIND = "h3_video_gen"
DOMAIN = "video"
CAP_TYPE = "external"
TRACE_SOURCE_KIND = "h3mini"

PRIMITIVES = (
    {"key": "T2VA", "cn": "文生视频", "input": "文本提示词", "note": "最基础入口"},
    {"key": "I2VA", "cn": "图生视频", "input": "一张参考图 + 提示词"},
    {"key": "FL2VA", "cn": "首尾帧", "input": "首帧 + 尾帧（+ 提示词）",
     "note": "两端锚定 ⇒ 中间由模型补"},
    {"key": "Ref2VA", "cn": "参考生视频", "input": "参考图/参考物 + 提示词",
     "note": "保对象一致性"},
)

# R-H251：维度表 —— **输入这一行主人已给全**（逐字登记，不改写）
INPUT_MODALITIES = ("文本", "图片", "视频", "音频")
INPUT_NOTE = ("全模态统一理解 —— **四模态进同一个理解层**"
              "（来源：主人提供 · 2026-09-20 · 逐字登记）")

# R-H252：**输出这一行主人已给全** —— 逐字登记
OUTPUT_MODALITIES = ("视频", "原生双声道音频")
OUTPUT_NOTE = "一次生成，不用后期配音（来源：主人提供 · 2026-09-20 · 逐字登记）"

# 🔴 两处措辞**并排记，不擅自合并**（a1.art 那刀的老规矩：防两处真相）
OUTPUT_WORDING_VARIANTS = (
    {"at": "2026-09-20 前一条消息", "text": "原生立体声"},
    {"at": "2026-09-20 本条（逐字）", "text": "原生双声道音频"},
    {"at": "2026-09-20 音频行（逐字）", "text": "立体声"},
)
OUTPUT_WORDING_NOTE = ("三处都指向「两声道、随视频一起生成」（**立体声 ×2 · 双声道 ×1**）；"
                       "**谁为准以官方原文定** —— 本骨架并排记，不合并、不替官方定名")

# R-H253：**分辨率这一行主人已给全** —— 逐字登记（「通过」二字照留，不改成「支持」）
RESOLUTION = "最高 2K"
RESOLUTION_NOTE = ("通过 **H3-Regenerate-2K** 达成（来源：主人提供 · 2026-09-20 · 逐字登记）；"
                   "「通过」二字照留 —— 2K 是经**该机制**拿到，不是随口写个数字；"
                   "具体口径（是否二次生成 / 是否算额外额度）**以官方为准**")

# R-H254：**时长这一行主人已给全** —— 逐字登记（en dash「–」原样保留，不转成连字符）
DURATION = "2–15 秒"
DURATION_NOTE = ("逐字登记（来源：主人提供 · 2026-09-20）；en dash **原样保留**；"
                 "**区间含端点** ⇒ 2 秒 ~ 15 秒（「含不含端点」以官方原文为准）")
# 从逐字文本**机械提取**的数字（不是另写一处真相：由 check_duration_verbatim 守着两者一致）
DURATION_SECONDS_RANGE = (2, 15)

# R-H255：**帧率这一行主人已给全** —— 逐字登记
FRAME_RATE = "24 FPS"
FRAME_RATE_NOTE = ("逐字登记（来源：主人提供 · 2026-09-20）；单位照留 **FPS** 大写；"
                   "是否恒定帧率（CFR）以官方为准")
FRAME_RATE_FPS = 24          # 从逐字文本机械提取（由 gate_verbatim 守着两者一致）

# R-H256：**音频这一行主人已给全** —— 逐字登记
AUDIO = "32 kHz 立体声"
AUDIO_NOTE = ("逐字登记（来源：主人提供 · 2026-09-20）；单位照留 **kHz** 写法；"
              "**立体声**在此行再次出现（措辞并排表第 3 条）")
AUDIO_SAMPLE_RATE_KHZ = 32   # 从逐字文本机械提取（gate_verbatim 守着两者一致）

# R-H257：**语言这一行主人已给全** —— 逐字登记
LANGUAGE = "稳定支持 11 种语言的对话"
LANGUAGE_NOTE = ("逐字登记（来源：主人提供 · 2026-09-20）；**「稳定」二字照留**"
                 "（不是「支持」而是「稳定支持」）；**具体是哪 11 种以官方为准**，"
                 "本骨架只登记条数，不列清单")
LANGUAGE_COUNT = 11          # 从逐字文本机械提取（gate_verbatim 守着两者一致）

# R-H259：**参数规模这一行主人已给全** —— 逐字登记
PARAM_SCALE = "33.1B DiT（扩散 Transformer）"
PARAM_SCALE_NOTE = ("逐字登记（来源：主人提供 · 2026-09-20）；**33.1B 含一位小数照留**；"
                    "架构标注「DiT（扩散 Transformer）」照留；"
                    "「不是文生视频，是一次生成带声音的完整视频片段」这句口径"
                    "**与输出行一致**（输出=视频+原生双声道音频）")
PARAM_SCALE_B = 33.1        # 从逐字文本机械提取（**本刀起支持小数**）

# 🔴 R-H260：主人**只给了新行名「作用」，内容截断** ⇒ 行名登记、内容**留空 + 写明理由**
#    （§57 有理由的空：不许猜、不许沉默；八行齐的表被这一行打开一格）
# R-H262：主人给了**内容**「文本 → 带音频视频」（逐字，箭头原样）
PURPOSE = "文本 → 带音频视频"
PURPOSE_NOTE = ("逐字登记（来源：主人提供 · 2026-09-20）；**箭头「→」原样保留**；"
                "**三处互证**：① 与输出行（视频 + 原生双声道音频）一致 "
                "② 与参数规模注记（「一次生成带声音的完整视频片段」）一致 "
                "③ 与 H3 模式 T2VA（文生视频）呼应 ⇒ 三条口径同向")
# 🔴 但**归属是推断**：主人没明说这句话就是『作用』那行的内容 ⇒ 单独登记待确认
PURPOSE_ATTRIBUTION = None
PURPOSE_ATTRIBUTION_PENDING_REASON = (
    "主人本条给的是**内容**（文本 → 带音频视频），**未明说它就是『作用』那一格** ⇒ "
    "已按推断填入，但**归属待主人一句话确认**（确认前不删候选标记）；"
    "确认「就是作用那行」⇒ 关掉本项；说「不是」⇒ 回退为两行并排")

# R-H261：新行**『对应 H3 模式』= T2VA**（逐字；恰好与四原语第一个 T2VA 对上 ⇒ 互证）
H3_MODE = "T2VA"
H3_MODE_NOTE = ("逐字登记（来源：主人提供 · 2026-09-20）；"
                "与原语表第一项 **T2VA（文生视频）逐字一致** ⇒ 两处互证，"
                "**不改写原语表、也不把它并进『作用』那一格**")

# 🔴 R-H263：主人本条**只给了值 I2VA，行名没给** ⇒ 暂存为候补行
H3_MODE_2 = "I2VA"
H3_MODE_2_NOTE = ("逐字登记（来源：主人提供 · 2026-09-20）；"
                  "与原语表第二项 **I2VA（图生视频）逐字一致** ⇒ 两处互证")
H3_MODE_2_ATTRIBUTION = None
H3_MODE_2_PENDING_REASON = (
    "主人本条**只给了值 I2VA，行名没给**（消息里只有这一个词）⇒ 暂存为候补行；"
    "它是不是『对应 H3 模式』那一行的**第二个值**、或另起一行的行名/值，**待主人补**；"
    "**不猜、不擅自并进上一行**；"
    "R-H264 新增证据：主人随后给了「图片 → 带音频视频」⇒ **第二组两侧都到位**"
    "（图片 → I2VA 图生视频，语义吻合）⇒ 已记为**推论配对**，但**仍待主人一句话确认**")

# R-H264：第二组的「作用」值 —— 逐字
PURPOSE_2 = "图片 → 带音频视频"
PURPOSE_2_NOTE = ("逐字登记（来源：主人提供 · 2026-09-20）；**箭头「→」原样保留**；"
                  "与第一组「文本 → 带音频视频」**结构对仗**；"
                  "**推论配对**到候补行 I2VA（图片 → 图生视频，语义吻合）；"
                  "与输出行 / 参数规模注记同向（互证）⇒ **配对是推论，待主人确认**")

# 🔴 R-H265：**第三个候补值 FL2VA**（同样只有值、行名没给）
H3_MODE_3 = "FL2VA"
H3_MODE_3_NOTE = ("逐字登记（来源：主人提供 · 2026-09-20）；"
                  "与原语表第三项 **FL2VA（首尾帧）逐字一致** ⇒ 两处互证")
H3_MODE_3_ATTRIBUTION = None
H3_MODE_3_PENDING_REASON = (
    "主人本条**只给了值 FL2VA，行名没给**（消息里只有这一个词）⇒ 暂存为候补行；"
    "它与哪一行的「作用」配对（预计是「首尾帧 → 带音频视频」这类），**待主人补**；"
    "**不猜、不擅自补行名**")

# 🔴 R-H267：**第四个候补值 Ref2VA**（同样只有值、行名没给）
H3_MODE_4 = "Ref2VA"
H3_MODE_4_NOTE = ("逐字登记（来源：主人提供 · 2026-09-20）；"
                  "与原语表第四项 **Ref2VA（参考生视频）逐字一致** ⇒ 两处互证")
H3_MODE_4_ATTRIBUTION = None
H3_MODE_4_PENDING_REASON = (
    "主人本条**只给了值 Ref2VA，行名没给**（消息里只有这一个词）⇒ 暂存为候补行；"
    "它与哪一行的「作用」配对（预计是「参考 → 带音频视频」这类），**待主人补**；"
    "**不猜、不补行名**")

# 候补行汇总（**只报读数，不替主人定论**）
CANDIDATE_MODES = ("I2VA", "FL2VA", "Ref2VA")
CANDIDATE_SUMMARY_NOTE = ("原语表四项中，**候补值三项全部到达**（I2VA / FL2VA / Ref2VA），"
                          "加上第一组已确认的 T2VA ⇒ **四个模式名都出现过**；"
                          "但三项**配对**与第三组**尾段措辞差异**仍待主人确认 —— "
                          "「出现」不等于「对上了」")

# R-H266：第三组的「作用」值 —— 逐字（**注意：后半段与前两行不一样**）
PURPOSE_3 = "首尾帧 → 视频"
PURPOSE_3_NOTE = ("逐字登记（来源：主人提供 · 2026-09-20）；箭头「→」原样保留；"
                  "🔴 **与前两行结构不同**：第一、二行后半段是「**带音频视频**」，"
                  "本行写的是「**视频**」⇒ **逐字保留、不擅自补成「带音频视频」**；"
                  "是否同义（音频被省略）**待主人确认**；"
                  "并记为与候补行 FL2VA 的**推论配对**（首尾帧 → FL2VA 首尾帧，语义吻合）")
PURPOSE_3_ATTRIBUTION = None
PURPOSE_3_PENDING_REASON = (
    "两件待确认：① 归属（这句话是不是『作用』那一格）② **措辞差异**"
    "（前两行「带音频视频」vs 本行「视频」）⇒ 都不许猜；"
    "确认「就是作用那行且音频按输出行算」⇒ 关掉本项")

# R-H268：第四组的「作用」值 —— 逐字（输入是**双形态**：参考图 / 视频）
PURPOSE_4 = "参考图/视频 → 视频"
PURPOSE_4_NOTE = ("逐字登记（来源：主人提供 · 2026-09-20）；**斜杠「/」与箭头「→」都原样保留**"
                  "（输入是**双形态**：参考图 / 视频 —— 与「参考生视频」语义吻合）；"
                  "尾段同样是「**视频**」（与第三行同类）；"
                  "并记为与候补行 Ref2VA 的**推论配对**")
PURPOSE_4_ATTRIBUTION = None
PURPOSE_4_PENDING_REASON = (
    "两件待确认：① 归属（这句话是不是『作用』那一格）② **输入双形态**的读法"
    "（「参考图/视频」是二选一还是两者皆可）⇒ 都不许猜；"
    "确认「就是作用那行」⇒ 关掉本项")

# 尾段措辞并排（**不合并**，与前例「立体声/双声道」同一套办法）
TAIL_VARIANTS = ("带音频视频", "带音频视频", "视频", "视频")
TAIL_NOTE = ("四行尾段并排记：前两行「带音频视频」×2 · 后两行「视频」×2；"
             "**计数只是读数**，是否同义（音频被省略 / 由输出行兜底）以主人/官方为准")

# 四组汇总读数
GROUPS_NOTE = ("四组「作用 + 对应模式」**两侧都已到位**（各组值都出现过）；"
               "但这是**出现**层面的齐，**不是确认层面的齐** —— "
               "配对与措辞仍以待确认项为准")

# 🔴 R-H269：主人只给了两个字「用例」⇒ **两种读法并排登记，不擅自判定**
PENDING_ROW_LABEL = "用例"
PENDING_ROW_LABEL_ATTRIBUTION = None
PENDING_ROW_LABEL_REASON = (
    "主人只给两个字『用例』⇒ **两种读法并排记，不擅自判定**："
    "① 它是**维度表的新行名**（内容被截断）⇒ 等主人补内容；"
    "② 或者是在**要求看用例** ⇒ 那就直接给读数（见 test_case_reading）。"
    "**两种都不许猜成第三种**；"
    "R-H270 新增证据：主人随后给了第一条条目『密钥不走明文』⇒ **读法① 证据 +1**"
    "（但仍**未明说**，故本项仍留空）")

# R-H270 / R-H271：主人给的**三条用例条目** —— 逐字（第一条 R-H270；第二三条 R-H271）
CASE_ITEMS = ("密钥不走明文",
              "返回值不许带明文 MINIMAX_API_KEY",
              "结果必须落盘",
              "生成的视频必须下载到本地，不许只留远程链接",
              "提示词必须走官方结构")
# 配对表：主人条目 → 我方带牙用例（**逐条配**，不是笼统说"对上了"）
CASE_PAIRING = (
    {"owner": "密钥不走明文",
     "ours": "plaintext_key", "how": "原理层（不出现明文密钥）"},
    {"owner": "返回值不许带明文 MINIMAX_API_KEY",
     "ours": "plaintext_key", "how": "**key 具体化**层（点了 MINIMAX_API_KEY 的名 —— "
                                     "与 LibTV 那条「返回值不许带明文 LIBTV_ACCESS_KEY」同一手法）"},
    {"owner": "结果必须落盘",
     "ours": "result_not_localized / audio_not_localized", "how": "结果（含音轨）必须落本地"},
    {"owner": "生成的视频必须下载到本地，不许只留远程链接",
     "ours": "result_not_localized", "how": "**视频具体化**层（原话里「不许只留远程链接」"
                                           "与我们那条同义）"},
    {"owner": "提示词必须走官方结构",
     "ours": "prose_prompt_rejected / prompt_sections_incomplete",
     "how": "提示词结构化 —— 🔴 **界宽不同**：主人说「**结构**」，我方落「**六段式**」"
            "（更具体）⇒ 是否同指**待主人确认**"},
)
# R-H272：上一轮标出的"我方多一条"**清零** —— 主人本轮把提示词那条也列上了（措辞为「官方结构」）
OUR_EXTRA_CASES = ()
OUR_EXTRA_NOTE = ("R-H271 曾标「我方多一条（六段式）」；R-H272 主人也列了它"
                  "（逐字为『提示词必须走官方结构』）⇒ **多出项清零**；"
                  "但两句**界宽不同** ⇒ 单独立账（见 CASE_WORDING_GAPS），"
                  "**既不擅自提级也不降级**")
CASE_WORDING_GAPS = (
    {"owner": "提示词必须走官方结构",
     "ours": "提示词必须官方六段式",
     "gap": "主人说「结构」（宽），我方落「六段式」（窄/更具体）⇒ **是否同指待主人确认**；"
            "确认前**两种措辞并排**，不擅自把「结构」当「六段式」，也不把「六段式」降成「结构」"},
)
# 🔴 R-H273：主人**明示** ⇒ 这笔差异**闭合**
CASE_WORDING_GAPS[0]["closed"] = True
CASE_WORDING_GAPS[0]["closed_by"] = (
    "主人 R-H273 明示：「H3 有**文档化的六段式输出格式**」⇒ **官方结构 = 六段式**（同指）；"
    "并给了散文被拒的**理由**：散文会省略结构显式化的关系")

# R-H273：散文式被拒的**理由出处**（接到闸的返回值里，不只写在文档里）
PROSE_REJECT_REASON = ("散文会省略**结构显式化**的关系（来源：主人提供 · 2026-09-20）"
                       "⇒ 所以「散文式提示词」必须拒，而不是「风格偏好」")

# 🔴 R-H273：新行名「五条红线」（同 R-H269/R-H260 的老规矩：两读法并排，不擅自判定）
PENDING_ROW_LABEL_2 = "五条红线"
PENDING_ROW_LABEL_2_ATTRIBUTION = None
PENDING_ROW_LABEL_2_REASON = (
    "主人只给了行名『五条红线』⇒ **两种读法并排记**："
    "① 它是**新的行名/小节**（五条内容待给）；"
    "② 或者是在**宣告红线清单** ⇒ 那就与我方已落的五条红线对账（见 RED_LINES，恰好 5 条）。"
    "**不擅自判定**；两者都不得凭空补内容；"
    "R-H274 新增证据：主人开始逐条给了（第 ① 条『密钥只存 DPAPI』）⇒ **读法② 证据 +1**"
    "（但仍未明说，故本项仍留空）")

# 🔴 R-H279：新行名「本地部署的硬件门槛」+ 表头「项目」（内容截断 ⇒ 留空带理由）
PENDING_ROW_LABEL_3 = "本地部署的硬件门槛"
PENDING_ROW_LABEL_3_TABLE_HEADER = "项目"
PENDING_ROW_LABEL_3_ATTRIBUTION = None
PENDING_ROW_LABEL_3_REASON = (
    "主人给到的是：行名『本地部署的硬件门槛（必须先说清）』+ 表头『项目』+ **内容截断** ⇒ "
    "**两种读法并排记**："
    "① 它是**新的一行/小节**（表内容待给）；"
    "② 或者是在**重复/展开**红线⑥⑦那条（硬件门槛先验 / 32GB 显存起步）——"
    "若如此，就与 HARDWARE + RED_LINES[3] + check_hw_threshold() 对账，不另立一处真相。"
    "**不擅自判定**；"
    "🔴 **「实测读数」四个字到了、读数本身没到** ⇒ 本刀**不填任何数字**"
    "（空样本不按绿：拿「实测」二字当读数就是假绿）；"
    "**（必须先说清）**是主人的语气/约束 ⇒ 照留，不当成数值 ⇒ 如实标")

# 🔴 R-H274：主人给的**第一条红线条目** —— 逐字
RED_LINE_ITEMS = ("密钥只存 DPAPI",
                  "MINIMAX_API_KEY 走密钥池，不许明文落盘",
                  "结果必须落盘",
                  "不绕官方入口",
                  "必须走官方 skill 脚本，不许自己拼 API 请求",
                  "硬件门槛先验",
                  "本地跑需要 32GB 显存起步，先验再装",
                  "每次操作留痕")   # R-H278：主人 **8 条**，归并后与我方五条一一对应
# 逐条配对表（主人条目 → 我方红线）——**逐条配，不笼统说"对上了"**
RED_LINE_PAIRING = (
    {"owner": "密钥只存 DPAPI",
     "ours": "RED_LINES[0]", "how": "**原理层**（存哪）"},
    {"owner": "MINIMAX_API_KEY 走密钥池，不许明文落盘",
     "ours": "RED_LINES[0]", "how": "**同一条的具体化层** —— 主人①+② 合起来正好是我方第一条的整句"
                                   "（我方还多「不许进返回值」一句）"},
    {"owner": "结果必须落盘",
     "ours": "RED_LINES[1]", "how": "前缀一致；**我方更具体**（视频 + 音轨都要落到本地）"},
    {"owner": "不绕官方入口",
     "ours": "RED_LINES[2]", "how": "前缀一致；**我方更具体**（走官方技能 / 官方 API、"
                                   "不许自己拼请求）"},
    {"owner": "必须走官方 skill 脚本，不许自己拼 API 请求",
     "ours": "RED_LINES[2]", "how": "**同一条的具体化层** —— 主人④原理 + ⑤形态"
                                   "**合起来** ≈ 我方第三条整句"
                                   "（走官方技能 / 官方 API、不许自己拼请求）"},
    {"owner": "硬件门槛先验",
     "ours": "RED_LINES[3]", "how": "前缀一致；**我方更具体**（本地要 32GB+、峰值 31.7GB；"
                                   "验不到就不许说「能本地跑」）"},
    {"owner": "本地跑需要 32GB 显存起步，先验再装",
     "ours": "RED_LINES[3]", "how": "**同一条的具体化层** —— ⑥原理 + ⑦形态**合起来** ≈ "
                                   "我方第四条；**主人多一句「先验再装」**（顺序约束）⇒ 如实标"},
    {"owner": "每次操作留痕",
     "ours": "RED_LINES[4]", "how": "前缀一致；**我方更具体**（写 trace_store，"
                                   "source_kind=h3mini）—— 这正是我方那条**主人一直到 "
                                   "R-H277 都没提**的红线，R-H278 主人补上了 ⇒ 我方多出项**清零**"},
)
# 🔴 R-H278：归并**映射表**（唯一真相源）—— 归并读数、双射判定、算术全从它派生，不手写
#    为什么：R-H277 的「配对表」与「读数」是两处手写 ⇒ 迟早会各漂各的；R-H278 合成一处
RED_LINE_MERGE_MAP = (
    {"key": "密钥", "owner_items": ("密钥只存 DPAPI",
                                    "MINIMAX_API_KEY 走密钥池，不许明文落盘"),
     "ours": "RED_LINES[0]"},
    {"key": "结果落盘", "owner_items": ("结果必须落盘",), "ours": "RED_LINES[1]"},
    {"key": "官方入口", "owner_items": ("不绕官方入口",
                                        "必须走官方 skill 脚本，不许自己拼 API 请求"),
     "ours": "RED_LINES[2]"},
    {"key": "硬件门槛", "owner_items": ("硬件门槛先验",
                                        "本地跑需要 32GB 显存起步，先验再装"),
     "ours": "RED_LINES[3]"},
    {"key": "留痕", "owner_items": ("每次操作留痕",), "ours": "RED_LINES[4]"},
)
# 🔴 R-H277「归并读数」立 · R-H278 升级为**双射闸**：主人 **8 条** − **3 对** = **5 组**，
#    5 组与我方 5 条红线**一一对应** ⇒ 与行名「五条红线」吻合；
#    但它**仍是推论**（主人没明说「这五组就是行名那条清单」）⇒ derived=True，待主人一句话定性
RED_LINE_MERGE_READING = {
    "owner_count": 8,
    "ours_count": 5,
    "merged_owner_count": 5,          # 8 条 − 3 对 = 5 组
    "ours_unmatched": (),             # R-H278 起为**空**，理由见下一行（§57 有理由的空）
    "ours_unmatched_reason": (
        "R-H278：主人把**最后一条**「每次操作留痕」也给了 ⇒ 我方 5 条红线**全部**在主人条目里"
        "有对应 ⇒ 这一格是**有理由的空**，不是未处理的残留"),
    "arithmetic": "8 - 3 = 5",
    "plus_unmatched": "5 + 0 = 5",
    "row_label": PENDING_ROW_LABEL_2,     # 「五条红线」
    "matches_row_label": True,
    "bijective": True,
    "derived": True,
    "derivation_note": (
        "主人 **8 条**里识别出 **3 对（原理 + 具体化）**："
        "①+②（密钥）· ④+⑤（官方入口）· ⑥+⑦（硬件门槛）⇒ 归并后 = **5** 组；"
        "**与行名「五条红线」数量吻合**，且归并后的 5 组与**我方 5 条红线一一对应（双射）**——"
        "一条不剩、一条不重 ⇒ 「行名 = 宣告这份清单」这个读法**证据大增**。"
        "🔴 但这**仍是推论**：主人没明说「这五组就是行名那条清单」"
        "⇒ **待主人一句话定性**；**不擅自提级也不降级**。"),
}
RED_LINE_ITEMS_NOTE = ("逐字登记（来源：主人提供 · 2026-09-20，分五轮到达）；"
                       "主人现共 **8 条**，与我方红线**逐条配对**（见 RED_LINE_PAIRING）；"
                       "**三对是「原理 + 具体化」**（①密钥 + ②密钥池 / ④不绕入口 + ⑤走官方 skill 脚本 / "
                       "⑥硬件门槛先验 + ⑦32GB 显存起步先验再装）"
                       "⇒ 三对各自**合起来** ≈ 我方第一 / 第三 / 第四条整句；"
                       "**归并读数见 RED_LINE_MERGE_READING**（8 条 − 3 对 = 5 组，"
                       "**与行名「五条红线」数量吻合**，且与我方 5 条**一一对应（双射）**；"
                       "仍**标为推论**）；**我方多出项已清零**"
                       "（主人把最后一条「每次操作留痕」也给了）；"
                       "**我方更具体**（MINIMAX_API_KEY / 走密钥池 / 不许明文落盘 / 不许进返回值；"
                       "官方技能 / 官方 API；32GB+ 峰值 31.7GB）⇒ **如实标，不删不缩**；"
                       "**主人多一句**「先验**再装**」（顺序约束）⇒ 如实标；"
                       "**⑧ 的具体化另立 TRACE_KIND_GAP 并排记**（主人给 source_kind=h3、"
                       "盘上钉 h3mini，**取值不同且未定** ⇒ **不并入本清单**，归属待主人定）；"
                       "**「是否还有下一条」⇒ 待主人确认**（不猜、不擅自补齐）")
# 🔴 R-H279：主人给红线⑧「每次操作留痕」的**具体化** —— 逐字（注意取值）
TRACE_ITEM_SPEC = '写 trace_store，source_kind="h3"'
TRACE_KIND_GAP = {
    "owner_spec": TRACE_ITEM_SPEC,
    "owner_kind": "h3",
    "ours_kind": "h3mini",      # 与上方 TRACE_SOURCE_KIND 一起被闸盯着（不许各漂各的）
    "prefix_agreed": "写 trace_store",
    "kind_differs": True,       # 闸会**机械重算**这一格，手写的它不认
    "resolution": None,         # 谁对 ⇒ **待主人定**（不擅自改盘上常量，也不擅自改写主人那条）
}
TRACE_KIND_ROW_ATTRIBUTION = None
TRACE_KIND_ROW_REASON = (
    "主人给的是「写 trace_store，source_kind=h3」⇒ **两种读法并排记**："
    "① 它是红线⑧「每次操作留痕」的**具体化层**（同 ①② / ④⑤ / ⑥⑦ 那三对的形态）；"
    "② 或者它是一条**独立条目**（那就要并进 RED_LINE_ITEMS，归并读数跟着重算）。"
    "**不擅自判定** ⇒ 本刀**不把它并入 RED_LINE_ITEMS**（并入就等于替主人定了读法①）；"
    "🔴 **取值差异照报**：主人 h3 vs 盘上 h3mini ⇒ 见 TRACE_KIND_GAP，**待主人一句话定**；"
    "**不擅自改盘上常量，也不擅自把主人那条改写成 h3mini**")
CASE_ITEMS_NOTE = ("逐字登记（来源：主人提供 · 2026-09-20，分两轮到达）；主人现共 **5 条**；"
                   "与我方带牙用例**逐条配对**（key 原理 + key 具体化 · 结果落盘原理 + 视频具体化 · "
                   "提示词结构化）；**我方多出项已清零**（主人也列了提示词那条）；"
                   "单独立账一处**措辞界宽差异**（见 CASE_WORDING_GAPS）；"
                   "**是否还有更多条 ⇒ 待主人确认**")

# 用例读数（**机器数出来的**，不是手写数字）
TEST_FILE = "gbt_allinone/tests/test_h3_video_gen.py"
TEETH_CASES = (
    "密钥不走明文 → plaintext_key",
    "结果必须落盘（视频 + 音轨）→ result_not_localized / audio_not_localized",
    "提示词必须官方六段式（不接受散文式）→ prose_prompt_rejected",
)

# 待补位登记：凡"该有值但现在没有"的字段，都必须在这里带理由
OPEN_FIELDS: Dict[str, str] = {
    "purpose_attribution": "purpose_attribution_pending_reason",
    "h3_mode_2_attribution": "h3_mode_2_pending_reason",
    "h3_mode_3_attribution": "h3_mode_3_pending_reason",
    "purpose_3_attribution": "purpose_3_pending_reason",
    "h3_mode_4_attribution": "h3_mode_4_pending_reason",
    "purpose_4_attribution": "purpose_4_pending_reason",
    "pending_row_label_attribution": "pending_row_label_reason",
    "pending_row_label_2_attribution": "pending_row_label_2_reason",
    "pending_row_label_3_attribution": "pending_row_label_3_reason",
    "trace_kind_row_attribution": "trace_kind_row_reason",
}


def test_case_reading(root: Any = None) -> dict:
    """用例读数：**从盘上真数** `def test_` 的条数（不手写数字、不凭记忆）。"""
    from . import framework_gate as fg
    base = Path(root) if root else Path(fg.ROOT)
    p = base / TEST_FILE
    if not p.is_file():
        return {"ok": False, "denied": True, "rule": "test_file_missing",
                "file": TEST_FILE,
                "why": "用例文件读不到 ⇒ **不许报数字**（空样本不按绿）"}
    try:
        src = p.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as e:  # noqa: BLE001
        return {"ok": False, "denied": True, "rule": "test_file_unreadable",
                "file": TEST_FILE, "why": str(e)[:80]}
    n = src.count("def test_")
    return {"ok": True, "readonly": True, "file": TEST_FILE, "count": n,
            "teeth_cases": list(TEETH_CASES),
            "note": "读出来的条数；**样本数为 0 就不算测到**（坑册 §45）"}

# 逐字 ↔ 提取值 的对账表（R-H255 起**通用**：新增字段只加一行，闸不用改）
VERBATIM_FIELDS = {
    "duration": ("DURATION", "DURATION_SECONDS_RANGE"),
    "frame_rate": ("FRAME_RATE", "FRAME_RATE_FPS"),
    "audio": ("AUDIO", "AUDIO_SAMPLE_RATE_KHZ"),
    "language": ("LANGUAGE", "LANGUAGE_COUNT"),
    "param_scale": ("PARAM_SCALE", "PARAM_SCALE_B"),
}

# 官方技能包（**只引用名字与作用，不复制内容**）
OFFICIAL_SKILLS = {
    "repo": "https://github.com/MiniMax-AI/MiniMax-H3",
    "count": 9,
    "core": "h3-prompt-writing",
    "core_note": "纯 Markdown · 零外部依赖 ⇒ 引用它，不抄它",
    "install_hint": "npx skills add https://github.com/MiniMax-AI/MiniMax-H3 "
                    "--skill h3-prompt-writing",
    "evidenced": False,
    "evidence_note": "主人提供 · 盘上 0 命中 · 未独立取证（出网受限）",
    "ref_not_copy": "引用官方仓库技能，**不复制 SKILL.md 内容**",
}

HARDWARE = {
    "local_min_vram_gb": 32.0,
    "local_peak_vram_gb": 31.7,
    "local_slim_checkpoint": "精简 INT8 检查点（官方给的低配路径）",
    "this_machine_vram_gb": None,
    "this_machine_note": "读数拿不到（nvidia-smi 不在 PATH · 沙箱身份下 WMI 被拒）",
    "mode": "api",           # local / api
    "mode_reason": "本机 RAM 7.4GB / 负载 93% ⇒ 带不动 31.7GB 峰值；走 API 不占本地显存",
}

# 🔴 R-H279 主人给了行名「本地部署的硬件门槛」+ 表头「项目」；
#    R-H280 给到**表的第一行行名**「峰值显存」⇒ 行名到了、**行值没到** ⇒ 留空带理由（§57），
#    并加一条闸防「旧数顶新读数」（数是真的，但它的来源不是这个 —— 假绿族里最像真的那种）
HW_TABLE_HEADER = "项目"
HW_TABLE_ROWS = (
    {"label": "峰值显存",
     "scope": "**实测峰值**：跑满时显存吃到多少",
     "value": 31.7,
     "value_verbatim": "31.7 GB（三个检查点都一样）",
     "units": ("GB",), "extra_numbers": (), "ignored_numbers": (),
     "ignored_reason": None,
     "source": "主人提供 · R-H281 · 逐字",
     "reaffirmed_by_owner": "主人 R-H281 重新给出（与立项那轮旧数同值，但这是**重新给的**）",
     "prefix_sibling": None,
     "pending_reason": "（历史）R-H280 时行值截断；R-H281 主人给了逐字值 ⇒ 已填",
     "note": None},
    {"label": "系统内存",
     "scope": "**系统内存预算**（不是显存、也不是本机内存）",
     "value": 128,
     "value_verbatim": "128 GB 预算（完整 INT8 峰值 93.1 GiB）",
     "units": ("GB", "GiB"), "extra_numbers": (93.1,), "ignored_numbers": (8,),
     "ignored_reason": "INT8 里的 8 是**型号**的一部分，不是读数（豁免必须写明）",
     "source": "主人提供 · R-H282 · 逐字",
     "reaffirmed_by_owner": None,
     "prefix_sibling": None,
     "pending_reason": "（历史）R-H281 时值截断；R-H282 主人给了逐字值 ⇒ 已填",
     "note": "一格两数两单位：128 GB（预算）与 93.1 GiB（完整 INT8 峰值）—— 不合并、不换算"},
    {"label": "推荐检查点",
     "scope": "**推荐用哪个检查点**（不是显存、不是内存）",
     "value": "精简 INT8",
     "value_verbatim": "精简 INT8（约 21 GB，速度最快）",
     "units": ("GB",), "extra_numbers": (21,), "ignored_numbers": (8,),
     "ignored_reason": "INT8 里的 8 是型号的一部分，不是读数",
     "source": "主人提供 · R-H283 · 逐字",
     "reaffirmed_by_owner": None,
     "prefix_sibling": ("与盘上旧记录「精简 INT8 检查点（官方给的低配路径）」**前缀一致"
                        "（精简 INT8）但整串不同** ⇒ **并排记、不合并、不顶替**"),
     "pending_reason": "（历史）R-H282 时值截断；R-H283 主人给了逐字值 ⇒ 已填",
     "note": "非数值行值（名字）⇒ 值必须原样出现在逐字里；同格的数 21 GB 也照样记账"},
    {"label": "8 秒片段耗时",
     "scope": "**跑一个 8 秒片段要多久**（按分辨率分档；不是「能生成多长」）",
     "value": "0.3MP 约 2 分钟 / 1.0MP 约 13 分钟",
     "value_verbatim": "0.3MP 约 2 分钟 / 1.0MP 约 13 分钟",
     "units": ("MP", "分钟", "MP", "分钟"),
     "extra_numbers": (0.3, 2, 1.0, 13),   # 🔴 含黏字母的 0.3 / 1.0（上一刀那把尺子会漏掉）
     "ignored_numbers": (), "ignored_reason": None,
     "source": "主人提供 · R-H286 · 逐字",
     "reaffirmed_by_owner": None,
     "prefix_sibling": None,
     "pending_reason": "（历史）R-H283 时值截断；R-H286 主人给了逐字值 ⇒ 已填",
     "note": ("两档**分辨率 ↔ 两档耗时**：分辨率越高越慢 —— 这两对是**同一句里的两组**，"
              "不许拆开记、也不许只留耗时")},
    {"label": "32GB 显存",
     "scope": ("**32GB 显存档**（预定规格 / 门槛）—— ⚠️ 它与第一行「峰值显存 31.7 GB」"
               "**不是同一个量**（一个规格、一个实测），与红线④「本地要 32GB+」也是两回事 ⇒ "
               "**三者关系待主人定，不擅自合并**）"),
     "value": None, "value_verbatim": None,
     "units": None, "extra_numbers": None, "ignored_numbers": None,
     "ignored_reason": None,
     "source": None, "reaffirmed_by_owner": None, "prefix_sibling": None,
     "pending_reason": ("主人给到『32GB 显存』⇒ **两种读法并排记**："
                        "① 它是**新的一行/一档规格**（值待给）；"
                        "② 或者是对第一行 / 红线④的**补充说明**（若如此则并入说明，不另立一行）。"
                        "**不擅自判定**；本刀按读法①登记为一行（值仍截断 ⇒ 留空带理由）")},
)

RED_LINES = (
    "密钥只存 DPAPI：MINIMAX_API_KEY 走密钥池，不许明文落盘、不许进返回值",
    "结果必须落盘：**视频 + 音轨**都要落到本地，不许只留远程链接（R-H252：输出含音频 ⇒ 音轨也算结果）",
    "不绕官方入口：走官方技能 / 官方 API，不许自己拼请求",
    "硬件门槛先验：本地要 32GB+（峰值 31.7GB）；验不到就不许说「能本地跑」",
    "每次操作留痕：写 trace_store，source_kind=h3mini",
)

# 官方六段式：**名字未取证** ⇒ 拿不到定义就不许凭记忆写（与 LibTV 的 schema 口径同族）
PROMPT_SECTIONS_EVIDENCED = False
PROMPT_SECTIONS_NOTE = ("主人说「必须走官方六段式」；但六段**分别叫什么**要按官方技能包为准 —— "
                        "出网受限 ⇒ 本骨架只判「有没有按段给」，**不编段名**")

_KEYISH = re.compile(r"\b(?:sk|ak|eyJ|mm|minimax)[-_][A-Za-z0-9_\-]{16,}\b")


def check_no_plaintext_key(payload: Any = None) -> dict:
    """带牙用例①：密钥不走明文。"""
    m = _KEYISH.search(str(payload or ""))
    if m:
        return {"ok": False, "denied": True, "rule": "plaintext_key",
                "seen": m.group(0)[:8],
                "why": "密钥只从 DPAPI / 密钥池取；返回值只许带 key_id / 掩码"}
    return {"ok": True, "readonly": True}


def _is_remote(t: str) -> bool:
    return str(t).lower().startswith(("http://", "https://", "oss://"))


def check_must_localize(targets: Optional[Sequence[str]] = None,
                        audio: Optional[Sequence[str]] = None) -> dict:
    """带牙用例②：结果必须落盘（本地可控落点），不许只留远程链接。

    R-H252：输出含**原生双声道音频** ⇒ 音轨也算结果 ⇒ `audio` 只给远程 ⇒ 拒
    （判据叫 `audio_not_localized`，与视频那条分开报，免得"视频落了音轨没落"被吞掉）。
    """
    ts = [str(t).strip() for t in (targets or []) if str(t or "").strip()]
    if not ts:
        return {"ok": False, "denied": True, "rule": "result_not_localized",
                "why": "没有任何本地落点 ⇒ 结果只在远端（链接会失效，且不在我们的盘上）"}
    remote = [t for t in ts if _is_remote(t)]
    if len(remote) == len(ts):
        return {"ok": False, "denied": True, "rule": "result_not_localized",
                "remote_only": remote[:3],
                "why": "只给了远程链接 = 没落盘；必须下载到本地（工作区 / 本地 CDN）"}
    aus = [str(a).strip() for a in (audio or []) if str(a or "").strip()]
    a_remote = [a for a in aus if _is_remote(a)]
    if aus and len(a_remote) == len(aus):
        return {"ok": False, "denied": True, "rule": "audio_not_localized",
                "remote_only": a_remote[:3],
                "why": "音轨只给了远程链接 ⇒ 视频落了、音轨没落（输出是「视频 + 原生双声道音频」，"
                       "两样都得在本地）"}
    return {"ok": True, "readonly": True,
            "local": [t for t in ts if not _is_remote(t)],
            "audio_local": [a for a in aus if not _is_remote(a)]}


def check_prompt_structure(sections: Optional[Sequence[str]] = None,
                           prompt: Optional[str] = None,
                           required: int = 6) -> dict:
    """带牙用例③：提示词必须走**官方六段式**结构 —— **不接受散文式**。

    判据（不编段名）：
      · 给了 `sections`：必须齐 `required` 段、段内不许空 ⇒ 通过；
      · 只给 `prompt`：散文式（一整段、没有分段标记）⇒ 拒；
      · 两个都没给 ⇒ 拒（拿不到结构就不许发请求）。
    """
    if sections:
        ss = [str(s).strip() for s in sections]
        missing = [i + 1 for i, s in enumerate(ss) if not s]
        if len(ss) < required or missing:
            return {"ok": False, "denied": True, "rule": "prompt_sections_incomplete",
                    "got": len(ss), "required": required, "empty_index": missing,
                    "why": "官方六段式要齐；缺段 / 空段 ⇒ 不许发请求",
                    "sections_note": PROMPT_SECTIONS_NOTE}
        return {"ok": True, "readonly": True, "sections": len(ss),
                "sections_note": PROMPT_SECTIONS_NOTE}
    text = str(prompt or "").strip()
    if not text:
        return {"ok": False, "denied": True, "rule": "prompt_missing",
                "why": "既没给分段，也没给提示词 ⇒ 无从判",
                "sections_note": PROMPT_SECTIONS_NOTE}
    # 散文式识别：一个自然段（无换行、无编号、无小标题冒号）⇒ 拒
    has_breaks = ("\n" in text) or re.search(r"(^|\n)\s*(?:\d+[.、)]|[-*·]|[①-⑩])", text)
    has_labels = len(re.findall(r"[：:]", text)) >= 2
    if not (has_breaks or has_labels):
        return {"ok": False, "denied": True, "rule": "prose_prompt_rejected",
                "why": "散文式提示词被拒：必须按官方六段式分段给（段名以官方技能包为准）；"
                       + PROSE_REJECT_REASON,
                "sections_note": PROMPT_SECTIONS_NOTE}
    return {"ok": True, "readonly": True, "style": "structured",
            "note": "看起来是分段结构；**段名是否等于官方六段**未取证 ⇒ 交官方技能包核",
            "sections_note": PROMPT_SECTIONS_NOTE}


def check_hardware(mode: str = "api",
                   vram_gb: Optional[float] = None,
                   min_gb: Optional[float] = None) -> dict:
    """红线④：硬件门槛先验 —— 验不到就不许说「能本地跑」。"""
    need = float(min_gb if min_gb is not None else HARDWARE["local_min_vram_gb"])
    m = str(mode or "").lower()
    if m == "local":
        if vram_gb is None:
            return {"ok": False, "denied": True, "rule": "hardware_unverified",
                    "need_gb": need,
                    "why": "本地模式读数拿不到（显存没测出来）⇒ **不许说能跑**；"
                           "要本地跑先拿读数，否则走 API 模式"}
        if float(vram_gb) < need:
            return {"ok": False, "denied": True, "rule": "hardware_below_threshold",
                    "have_gb": float(vram_gb), "need_gb": need,
                    "why": "显存不够（官方口径：本地要 32GB+，峰值 31.7GB）"}
        return {"ok": True, "readonly": True, "mode": "local",
                "have_gb": float(vram_gb), "need_gb": need}
    if m == "api":
        return {"ok": True, "readonly": True, "mode": "api",
                "requires_external_key": True, "local_vram_needed": False,
                "why": "API 模式不占本地显存；**需要 MINIMAX_API_KEY**（当前盘上没有）"}
    return {"ok": False, "denied": True, "rule": "bad_mode",
            "why": "模式只能是 local / api"}


def check_via_official(entry: Optional[str] = None) -> dict:
    """红线③：不绕官方入口。"""
    e = str(entry or "").strip()
    if not e:
        return {"ok": False, "denied": True, "rule": "entry_unspecified",
                "why": "没说走哪个入口 ⇒ 不许发请求"}
    if e.lower() in ("handmade_api_request", "self_written_request", "curl"):
        return {"ok": False, "denied": True, "rule": "not_via_official",
                "why": "必须走官方技能 / 官方 API；自己拼请求 = 绕过官方入口"}
    if e in ("h3-prompt-writing", "official_skill", "official_api"):
        return {"ok": True, "readonly": True, "entry": e}
    return {"ok": False, "denied": True, "rule": "unknown_entry",
            "entry": e, "allowed": ["h3-prompt-writing", "official_skill", "official_api"],
            "why": "入口必须在白名单里（官方技能 / 官方 API）"}


def _numbers(text: Any) -> List[Any]:
    """从逐字文本里抽数字。**R-H259 起支持小数**（33.1B ⇒ 33.1；2–15 ⇒ 2, 15）。"""
    out: List[Any] = []
    for x in re.findall(r"\d+(?:\.\d+)?", str(text or "")):
        out.append(float(x) if "." in x else int(x))
    return out


# R-H286：单位记号扩到 **MP / 分钟 / 秒 / FPS / kHz**（主人那格给了「0.3MP 约 2 分钟」）
# 去掉 \b（中文没有词边界）；交替顺序保证 GiB 先于 GB 匹配、不互相吃
_UNIT_RE = re.compile(r"GiB|GB|MP|MiB|MB|KiB|kB|FPS|kHz|分钟|秒")


def _units(text: Any) -> List[str]:
    """从逐字里抽**单位记号**（**原样**取出，不换算）。

    为什么要它：R-H282 主人给的格子里有 GB 与 GiB 两个单位 ——
    它们**不相等**（1 GiB ≠ 1 GB），一旦被「顺手统一」就再也看不出来了。
    """
    return _UNIT_RE.findall(str(text or ""))


_SOLO_NUM_RE = re.compile(r"(?<![A-Za-z0-9])\d+(?:\.\d+)?(?![A-Za-z0-9])")


def _standalone_numbers(text: Any) -> List[Any]:
    """抽**独立数字**：不黏字母的数（**INT8 里的 8 不算**）。

    为什么单立一个（R-H282 当场踩到）：通用提取器 `_numbers` 会把
    「完整 INT8 峰值 93.1 GiB」抽成 [8, 93.1] —— 那个 8 是**型号的一部分**，不是读数；
    而 `_numbers` 本身不能改（`gate_verbatim` 要靠它抓 **33.1B** 这种黏字母的数）。
    ⇒ 两个用途两种尺子，各用各的，不许拿同一把量。
    """
    out: List[Any] = []
    for x in _SOLO_NUM_RE.findall(str(text or "")):
        out.append(float(x) if "." in x else int(x))
    return out


def _common_prefix(a: str, b: str) -> str:
    """两串的**公共前缀**（逐字取，不做任何规整）。

    为什么要它（R-H283 现场）：主人给的「精简 INT8（约 21 GB，速度最快）」与盘上旧记录
    「精简 INT8 检查点（官方给的低配路径）」**前缀一致、整串不同** ——
    这种「像但不等于」最容易被顺手合并成一条，两条证据就都没了。
    """
    n = 0
    for x, y in zip(str(a or ""), str(b or "")):
        if x != y:
            break
        n += 1
    return str(a or "")[:n]


def check_verbatim_fields(field: Optional[str] = None) -> dict:
    """**通用自校验闸**（R-H255 起）：逐字文本 ↔ 机械提取值，必须对得上。

    不许两处真相：改了原文没改提取值（或相反）⇒ 红。
    新字段要纳进来，只在 `VERBATIM_FIELDS` 加一行，**闸本身不用改**。
    """
    names = [field] if (field and field in VERBATIM_FIELDS) else list(VERBATIM_FIELDS)
    g = globals()
    checked = {}
    for name in names:
        text_key, value_key = VERBATIM_FIELDS[name]
        text = g.get(text_key)
        declared = g.get(value_key)
        nums = _numbers(text)
        if not nums:
            return {"ok": False, "denied": True, "rule": "%s_unparsable" % name,
                    "text": text,
                    "why": "逐字文本里读不出数字 ⇒ 机械提取失效，登记形状不对"}
        got = tuple(nums) if isinstance(declared, (tuple, list)) else nums[0]
        want = tuple(declared) if isinstance(declared, (tuple, list)) else declared
        if got != want:
            return {"ok": False, "denied": True, "rule": "%s_mismatch" % name,
                    "from_text": got, "declared": want,
                    "why": "逐字文本与提取值不一致 ⇒ 不许两处真相"}
        checked[name] = {"text": text, "value": want}
    return {"ok": True, "readonly": True, "checked": checked}


def check_duration_verbatim() -> dict:
    """（R-H254 的旧入口，**保留兼容**）等价于 `check_verbatim_fields("duration")`。

    兼容契约：R-H254 起返回值带 `range`（旧调用方与探针按它写），这里照样给 ——
    **同一条读数两种形状**，不是两处真相。
    """
    r = check_verbatim_fields("duration")
    if r.get("ok"):
        r["range"] = tuple(r["checked"]["duration"]["value"])
    return r


def check_open_fields() -> dict:
    """闸⑤（坑册 §57 的机械形态）：**空必须带理由** —— 不许出现无标注的空。"""
    g = globals()
    bad = []
    for field, reason_key in OPEN_FIELDS.items():
        value = g.get(field.upper())
        reason = str(g.get(reason_key.upper()) or "").strip()
        if (value is None or value == "" or value == ()) and not reason:
            bad.append(field)
    if bad:
        return {"ok": False, "denied": True, "rule": "blank_without_reason",
                "blank": bad,
                "why": "留空的字段必须写明理由（§57：有理由的空 ≠ 未处理的残留）"}
    return {"ok": True, "readonly": True, "open_fields": sorted(OPEN_FIELDS),
            "table_complete": not OPEN_FIELDS}


_CN_NUMERALS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
                "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _row_label_count(label: Any) -> Any:
    """从行名里机械取数（「五条红线」⇒ 5）—— **取不到就返回 None，不猜**。"""
    for ch in str(label or ""):
        if ch in _CN_NUMERALS:
            return _CN_NUMERALS[ch]
    return None


def check_merge_reading() -> dict:
    """闸⑦（R-H277 立 · R-H278 升级为**双射闸**）：归并读数必须**算出来**。

    算法（**全部从 RED_LINE_MERGE_MAP 派生**，不手写）：
      ① **覆盖**：主人每一条都被归并用到 —— 一条不剩、一条不重、不许凭空多出
      ② **双射**：归并后的每组都指到我方红线，索引恰好是 0..N-1 的一个排列
      ③ **算术**：主人条数 − 多条目组数 = 归并组数；归并组数 + 我方未提项 = 我方红线数
      ④ **行名**：行名里的数（「五条红线」⇒ 5）与算出来的归并组数一致
    **任何一条对不上 ⇒ 当场红**（不许手写数字冒充算出来的）。

    🔴 注意它与别的闸不同：它守的是**我们自己的推论**，
    返回值里 `derived=True` 与 `note` 必须一路带着「这是推论」——
    **推论不许被读成主人逐字**。
    """
    mr = RED_LINE_MERGE_READING
    items = list(RED_LINE_ITEMS)
    groups = list(RED_LINE_MERGE_MAP)
    used = [x for g in groups for x in g["owner_items"]]
    extra = sorted({x for x in used if x not in items})
    unused = sorted({x for x in items if x not in used})
    dup = sorted({x for x in used if used.count(x) > 1})
    if extra or unused or dup:
        return {"ok": False, "denied": True, "rule": "merge_map_not_covering",
                "extra": extra, "unused": unused, "dup": dup,
                "why": "归并映射必须**覆盖**主人全部条目：不许漏、不许重、不许凭空多"}
    idx = []
    for g in groups:
        m = re.fullmatch(r"RED_LINES\[(\d+)\]", str(g.get("ours") or ""))
        if not m:
            return {"ok": False, "denied": True, "rule": "merge_map_bad_slot",
                    "slot": g.get("ours"),
                    "why": "每组必须指到我方红线，且写成 RED_LINES[i] 形状"}
        idx.append(int(m.group(1)))
    if sorted(idx) != list(range(len(RED_LINES))):
        return {"ok": False, "denied": True, "rule": "merge_map_not_bijective",
                "idx": idx, "ours": len(RED_LINES),
                "why": "归并组与我方红线必须**一一对应**（索引是 0..N-1 的排列）"
                       " ⇒ 多对一、少一个、指到界外都算红"}
    merged = len(groups)
    ours = len(RED_LINES)
    unmatched = list(mr["ours_unmatched"])
    computed_a = "%d - %d = %d" % (len(items), len(items) - merged, merged)
    computed_b = "%d + %d = %d" % (merged, len(unmatched), merged + len(unmatched))
    declared = {"owner_count": (mr["owner_count"], len(items)),
                "merged_owner_count": (mr["merged_owner_count"], merged),
                "ours_count": (mr["ours_count"], ours),
                "arithmetic": (mr["arithmetic"], computed_a),
                "plus_unmatched": (mr["plus_unmatched"], computed_b),
                "bijective": (mr["bijective"], True)}
    off = {k: {"written": v[0], "on_disk": v[1]}
           for k, v in declared.items() if v[0] != v[1]}
    if off:
        return {"ok": False, "denied": True, "rule": "merge_reading_stale",
                "off": off,
                "why": "手写的归并读数与盘上真值不一致 ⇒ 读数是**算出来的**，不是抄来的"}
    label_n = _row_label_count(mr["row_label"])
    matches = (label_n is None) or (label_n == merged)
    if bool(mr["matches_row_label"]) != bool(matches):
        return {"ok": False, "denied": True, "rule": "merge_row_label_mismatch",
                "declared": mr["matches_row_label"], "actual": matches,
                "why": "「与行名吻合」这句话必须被真算一遍"}
    return {"ok": True, "readonly": True,
            "owner_count": len(items), "pairs": len(items) - merged,
            "merged_owner_count": merged, "ours_unmatched": unmatched,
            "ours_unmatched_reason": str(mr.get("ours_unmatched_reason") or ""),
            "ours_count": ours, "arithmetic": computed_a,
            "plus_unmatched": computed_b, "bijective": True,
            "map": [{"key": g["key"], "owner_items": list(g["owner_items"]),
                     "ours": g["ours"]} for g in groups],
            "row_label": mr["row_label"], "row_label_count": label_n,
            "matches_row_label": bool(matches), "derived": bool(mr["derived"]),
            "note": "**推论**（主人未确认）⇒ 与「主人逐字」并排记，不合并"}


def check_hw_threshold() -> dict:
    """闸⑧（R-H278）：主人⑦给的**显存门槛数字**必须与盘上 HARDWARE 一致。

    为什么单独一条：⑦ 的实质是「本地跑需要 32GB 显存起步」——
    这个数**两边各写一遍就会漂**（一边 32 一边 24，谁也发现不了）。
    所以：从主人那条逐字条目里**机械抽出数字**，与 HARDWARE["local_min_vram_gb"] 对一次；
    再确认「先验**再装**」这个顺序写在条目里（验在装之前）。
    """
    owner = ""
    for x in RED_LINE_ITEMS:
        if str(x).startswith("本地跑需要"):
            owner = str(x)
            break
    if not owner:
        return {"ok": False, "denied": True, "rule": "hw_item_missing",
                "why": "主人那条『本地跑需要 32GB 显存起步，先验再装』必须真在条目里"}
    nums = _numbers(owner)
    on_disk = float(HARDWARE["local_min_vram_gb"])
    if not nums:
        return {"ok": False, "denied": True, "rule": "hw_threshold_not_parseable",
                "item": owner,
                "why": "条目里读不出数字 ⇒ 不许报『门槛一致』（空样本不按绿）"}
    given = float(nums[0])
    ordered = ("先验" in owner) and ("再装" in owner) and (owner.index("先验") < owner.index("再装"))
    if given != on_disk or not ordered:
        return {"ok": False, "denied": True, "rule": "hw_threshold_drift",
                "owner_item": owner, "owner_gb": given, "disk_gb": on_disk,
                "ordered_before_install": ordered,
                "why": "门槛数字两边不一致，或『先验再装』的顺序没写在条目里"}
    return {"ok": True, "readonly": True, "owner_item": owner,
            "owner_gb": given, "disk_gb": on_disk, "agreed": True,
            "ordered_before_install": True, "peak_gb": HARDWARE["local_peak_vram_gb"],
            "note": "主人给**门槛**（32GB 起步）· 盘上给**峰值**（31.7GB）⇒ 数字一致，"
                    "且顺序是**先验后装**"}


def check_source_kind(source_kind: Any = None) -> dict:
    """闸⑨（R-H279）：**写 trace_store 必须带 source_kind，且等于钉死的取值**。

    与 libtv_skill / feishu_embed **同族** —— 那两个早就有这条闸，H3mini 一直没有（本刀补上）。

    🔴 但它必须**自报争议**：主人 R-H279 给的是 `source_kind=h3`，
    盘上钉死的是 `h3mini`（见 TRACE_KIND_GAP），**两者不一致且未定**。
    所以：闸能拦错值，**但不许假装这个值没有争议** —— 返回值一路带 `kind_disputed`。

    另有一条**防静默统一**：只要没有主人一句话（`resolution` 为空），
    就不许让两边的取值变得一致 —— 把有争议的事悄悄抹平，比留个差异更糟。
    """
    gap = TRACE_KIND_GAP
    ours = str(TRACE_SOURCE_KIND)
    owner_kind = str(gap["owner_kind"])
    differs = ours != owner_kind
    resolved = bool(str(gap.get("resolution") or "").strip())
    if str(gap.get("ours_kind")) != ours or differs != bool(gap["kind_differs"]):
        return {"ok": False, "denied": True, "rule": "trace_kind_gap_stale",
                "written_ours": gap.get("ours_kind"), "disk_ours": ours,
                "written_differs": bool(gap["kind_differs"]), "actual_differs": differs,
                "why": "差异那几格必须**机械重算**，不许手写（手写迟早和盘上不一致）"}
    if not differs and not resolved:
        return {"ok": False, "denied": True, "rule": "trace_kind_silently_unified",
                "ours_kind": ours, "owner_kind": owner_kind,
                "why": "两边取值已经一样了，却**没有主人一句话** ⇒ 这叫「静默统一」："
                       "把有争议的事悄悄抹平 ⇒ 红"}
    disputed = bool(differs and not resolved)
    sk = str(source_kind or "").strip()
    if not sk:
        return {"ok": False, "denied": True, "rule": "source_kind_missing",
                "expected": ours, "kind_disputed": disputed,
                "why": "每次操作留痕必须**写 trace_store 且带 source_kind** —— "
                       "无源不许记（无痕即未发生）"}
    if sk != ours:
        return {"ok": False, "denied": True, "rule": "source_kind_mismatch",
                "source_kind": sk, "expected": ours, "owner_kind": owner_kind,
                "kind_disputed": disputed,
                "why": "事后按来源筛得出来才算留痕 ⇒ source_kind 必须等于钉死的取值"}
    return {"ok": True, "readonly": True, "source_kind": sk, "expected": ours,
            "owner_kind": owner_kind, "kind_disputed": disputed,
            "resolution": gap.get("resolution"),
            "note": "闸能拦错值，**但不假装这个值没有争议** —— 主人给 h3、盘上钉 h3mini，"
                    "**待主人一句话定**（见 TRACE_KIND_GAP）"}


def check_hw_rows() -> dict:
    """闸⑩（R-H280 立 · R-H286 立「全数字记账」）：硬件门槛**表**的九条规矩。

    ① 行值留空 ⇒ 必须带理由（§57）
    ② 行值必须有**来源**（谁给的、哪一轮）
    ③ 行值必须带**逐字**；数值走抽数对账，非数值走「原样出现在逐字里」
    ④ 🔴 **逐字里每一个数都要有交代**：主数 + `extra_numbers` + `ignored_numbers`
       **双向对账** —— 漏一个就红。
       （R-H286 现场：上一刀为躲 `INT8` 的 8 而立的那把尺子，会把 `0.3MP` 的 0.3 也跳过 ⇒
        **读数被静默丢掉**。修法不是再改尺子，是**换成记账**：全量抽数，要豁免可以，
        但豁免必须**写出来并给理由**。）
    ⑤ `ignored_numbers` 非空 ⇒ `ignored_reason` 必须非空
    ⑥ 逐字里的**单位记号**必须原样，且与记录的 `units` 一致（1 GiB ≠ 1 GB）
    ⑦ 与盘上旧记录**整串相同** ⇒ 必须写「主人重新给的」
    ⑧ 与盘上旧记录**前缀一致但整串不同** ⇒ 必须记 `prefix_sibling`（并排记、不合并）
    ⑨ 🔴 每行必须有 `scope`：**这行说的是哪个量**
       （R-H286 现场：表里已经有两行都在说「显存」，加上红线④就是三处 ——
        不把「说的是哪个量」写下来，迟早有人拿 31.7 去顶 32。）

    跨行一条：**系统内存 ≠ 显存**。
    """
    rows = list(HW_TABLE_ROWS)
    if not rows:
        return {"ok": False, "denied": True, "rule": "hw_rows_empty",
                "why": "表一行都没有 ⇒ 空样本不按绿"}
    old_map = (("显存", HARDWARE["local_peak_vram_gb"]),
               ("检查点", HARDWARE["local_slim_checkpoint"]))
    out = []
    for r in rows:
        label = str(r.get("label") or "").strip()
        scope = str(r.get("scope") or "").strip()
        value = r.get("value")
        verbatim = str(r.get("value_verbatim") or "").strip()
        reason = str(r.get("pending_reason") or "").strip()
        source = str(r.get("source") or "").strip()
        reaffirmed = str(r.get("reaffirmed_by_owner") or "").strip()
        sibling = str(r.get("prefix_sibling") or "").strip()
        if not scope:
            return {"ok": False, "denied": True, "rule": "hw_row_scope_missing",
                    "label": label,
                    "why": "每行都要写明**这行说的是哪个量**（否则同族行各说各话，"
                           "迟早拿 A 的数去顶 B）"}
        if value is None and not reason:
            return {"ok": False, "denied": True, "rule": "hw_row_blank_without_reason",
                    "label": label, "why": "行值留空必须写明理由（§57）"}
        if value is not None:
            if not source:
                return {"ok": False, "denied": True, "rule": "hw_row_value_without_source",
                        "label": label, "value": value,
                        "why": "行值必须有**来源**（谁给的、哪一轮）"}
            if not verbatim:
                return {"ok": False, "denied": True, "rule": "hw_row_value_without_verbatim",
                        "label": label, "value": value,
                        "why": "行值必须同时留**逐字**（只留个数字 = 把主人多说的那半句丢了）"}
            numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
            if numeric and (not _standalone_numbers(verbatim)
                            or float(_standalone_numbers(verbatim)[0]) != float(value)):
                return {"ok": False, "denied": True, "rule": "hw_row_verbatim_mismatch",
                        "label": label, "value": value, "verbatim": verbatim,
                        "extracted": _standalone_numbers(verbatim),
                        "why": "逐字里抽出的主数与机器数对不上 ⇒ 两者必有一处被改过"}
            if (not numeric) and str(value) not in verbatim:
                return {"ok": False, "denied": True, "rule": "hw_row_verbatim_mismatch",
                        "label": label, "value": value, "verbatim": verbatim,
                        "extracted": [],
                        "why": "非数值的行值必须**原样**出现在逐字里（不许改写、不许简称）"}
            all_nums = [float(x) for x in _numbers(verbatim)]
            rest = list(all_nums)
            if numeric:
                for i, x in enumerate(rest):
                    if x == float(value):
                        rest.pop(i)
                        break
            kept = [float(x) for x in (r.get("extra_numbers") or ())]
            ign = [float(x) for x in (r.get("ignored_numbers") or ())]
            ignore_reason = str(r.get("ignored_reason") or "").strip()
            if ign and not ignore_reason:
                return {"ok": False, "denied": True, "rule": "hw_row_ignore_without_reason",
                        "label": label, "ignored_numbers": ign,
                        "why": "要豁免某个数可以，但**豁免必须写明理由**"
                               "（不写就是静默丢数）"}
            if sorted(rest) != sorted(kept + ign):
                return {"ok": False, "denied": True, "rule": "hw_row_number_unaccounted",
                        "label": label, "in_verbatim": sorted(rest),
                        "extra_numbers": sorted(kept), "ignored_numbers": sorted(ign),
                        "why": "**逐字里每个数都要有交代**：要么记进 `extra_numbers`，"
                               "要么进 `ignored_numbers` 并给理由 —— 漏一个就是静默丢读数"}
            units_here = tuple(_units(verbatim))
            units_kept = tuple(r.get("units") or ())
            if units_here != units_kept:
                return {"ok": False, "denied": True, "rule": "hw_row_unit_drift",
                        "label": label, "in_verbatim": list(units_here),
                        "kept": list(units_kept),
                        "why": "单位必须**原样**：GB 与 GiB 不相等 ⇒ 换算即失真"}
            same = [(k, o) for k, o in old_map if k in label and o is not None
                    and str(o) == str(value)]
            if same and not reaffirmed:
                return {"ok": False, "denied": True, "rule": "hw_row_old_number_reused",
                        "label": label, "value": value, "old_on_disk": same[0][1],
                        "source": source,
                        "why": "这个值与盘上**旧记录**一样，却没写清是主人**重新**给的 ⇒ "
                               "**旧数 ≠ 新读数**"}
            if not same:
                for k, o in old_map:
                    if o is None or k not in label:
                        continue
                    pre = _common_prefix(str(o), str(value))
                    if 4 <= len(pre) < max(len(str(o)), len(str(value))):
                        if not sibling:
                            return {"ok": False, "denied": True,
                                    "rule": "hw_row_prefix_sibling_unrecorded",
                                    "label": label, "value": value,
                                    "old_on_disk": o, "common_prefix": pre,
                                    "why": "与盘上旧记录**前缀一致但整串不同** ⇒ "
                                           "必须记 `prefix_sibling`（并排记、不合并）"}
                        break
        out.append({"label": label, "scope": scope, "value": value,
                    "value_verbatim": verbatim or None,
                    "units": list(r.get("units") or ()) or None,
                    "extra_numbers": list(r.get("extra_numbers") or ()) or None,
                    "ignored_numbers": list(r.get("ignored_numbers") or ()) or None,
                    "has_value": value is not None, "source": source or None,
                    "reaffirmed_by_owner": reaffirmed or None,
                    "prefix_sibling": sibling or None,
                    "pending_reason": reason or None,
                    "note": str(r.get("note") or "") or None})
    vram_vals = [float(x["value"]) for x in out
                 if "显存" in x["label"] and isinstance(x["value"], (int, float))
                 and not isinstance(x["value"], bool)]
    for x in out:
        if "内存" in x["label"] and isinstance(x["value"], (int, float)) \
                and not isinstance(x["value"], bool) \
                and any(float(x["value"]) == v for v in vram_vals):
            return {"ok": False, "denied": True, "rule": "hw_row_memory_equals_vram",
                    "label": x["label"], "value": x["value"], "vram_values": vram_vals,
                    "why": "**系统内存 ≠ 显存**：两个不同的量取到同一个数，必有一处是抄错"}
    return {"ok": True, "readonly": True, "table_header": HW_TABLE_HEADER,
            "rows": out, "row_count": len(out),
            "complete": all(x["has_value"] for x in out),
            "old_values_on_disk": {k: v for k, v in old_map},
            "note": "**行名到了 ≠ 行值到了** · **旧数不许顶新读数** · **逐字不许只留数字** · "
                    "**每个数都要有交代**（豁免也要理由）· **单位不许换算** · "
                    "**前缀一致必须并排记** · **每行要写 scope**"}


def pending_total() -> dict:
    """**一处看全**：待补位 = OPEN_FIELDS 的格数 + 硬件表里没填的行数。

    为什么要它（本刀自己造的风险）：R-H279/R-H280 起「待补位」分散在**两处**
    （字段格 + 表行）—— 分开看**迟早漏一处**。
    所以给一个合计数，并**同时列出两边的清单**（不是只给个数字）。
    """
    blank = check_open_fields()
    rows = check_hw_rows()
    fields = list(blank.get("open_fields") or [])
    row_labels = [str(x["label"]) for x in (rows.get("rows") or []) if not x["has_value"]]
    return {"ok": bool(blank.get("ok")) and bool(rows.get("ok")), "readonly": True,
            "open_fields": fields, "blank_rows": row_labels,
            "total": len(fields) + len(row_labels),
            "note": "**两处都要看**：字段格 + 表行；这里给合计数，防漏一处"}


def run(op="status", **params) -> dict:
    """能力入口（只读骨架）：status / primitives / skills / hardware / mode /
    modalities / redlines / gate_key / gate_localize / gate_prompt / gate_hw /
    gate_official / gate_blank / gate_merge / gate_hw_threshold / gate_source_kind。"""
    op = str(op or "status")
    if op == "status":
        return {"ok": True, "readonly": True, "kind": CAP_KIND, "domain": DOMAIN,
                "type": CAP_TYPE,
                "primitives": [p["key"] for p in PRIMITIVES],
                "official": {"repo": OFFICIAL_SKILLS["repo"],
                             "skills": OFFICIAL_SKILLS["count"],
                             "core": OFFICIAL_SKILLS["core"]},
                "mode": HARDWARE["mode"], "mode_reason": HARDWARE["mode_reason"],
                "requires_external_key": True,
                "key_present": False,
                "input_modalities": list(INPUT_MODALITIES),
                "input_note": INPUT_NOTE,
                "output_modalities": list(OUTPUT_MODALITIES),
                "output_note": OUTPUT_NOTE,
                "output_wording_variants": [dict(v) for v in OUTPUT_WORDING_VARIANTS],
                "resolution": RESOLUTION,
                "resolution_note": RESOLUTION_NOTE,
                "duration": DURATION, "duration_note": DURATION_NOTE,
                "duration_seconds_range": list(DURATION_SECONDS_RANGE),
                "frame_rate": FRAME_RATE, "frame_rate_note": FRAME_RATE_NOTE,
                "frame_rate_fps": FRAME_RATE_FPS,
                "audio": AUDIO, "audio_note": AUDIO_NOTE,
                "audio_sample_rate_khz": AUDIO_SAMPLE_RATE_KHZ,
                "language": LANGUAGE, "language_note": LANGUAGE_NOTE,
                "language_count": LANGUAGE_COUNT,
                "param_scale": PARAM_SCALE, "param_scale_note": PARAM_SCALE_NOTE,
                "param_scale_b": PARAM_SCALE_B,
                "purpose": PURPOSE, "purpose_note": PURPOSE_NOTE,
                "purpose_attribution": PURPOSE_ATTRIBUTION,
                "purpose_attribution_pending_reason":
                    PURPOSE_ATTRIBUTION_PENDING_REASON,
                "purpose_2": PURPOSE_2, "purpose_2_note": PURPOSE_2_NOTE,
                "purpose_3": PURPOSE_3, "purpose_3_note": PURPOSE_3_NOTE,
                "purpose_3_attribution": PURPOSE_3_ATTRIBUTION,
                "purpose_3_pending_reason": PURPOSE_3_PENDING_REASON,
                "tail_variants": list(TAIL_VARIANTS), "tail_note": TAIL_NOTE,
                "purpose_4": PURPOSE_4, "purpose_4_note": PURPOSE_4_NOTE,
                "purpose_4_attribution": PURPOSE_4_ATTRIBUTION,
                "purpose_4_pending_reason": PURPOSE_4_PENDING_REASON,
                "groups_note": GROUPS_NOTE,
                "pending_row_label": PENDING_ROW_LABEL,
                "pending_row_label_attribution": PENDING_ROW_LABEL_ATTRIBUTION,
                "pending_row_label_reason": PENDING_ROW_LABEL_REASON,
                "case_items": list(CASE_ITEMS), "case_items_note": CASE_ITEMS_NOTE,
                "case_pairing": [dict(x) for x in CASE_PAIRING],
                "our_extra_cases": list(OUR_EXTRA_CASES),
                "our_extra_note": OUR_EXTRA_NOTE,
                "case_wording_gaps": [dict(x) for x in CASE_WORDING_GAPS],
                "prose_reject_reason": PROSE_REJECT_REASON,
                "pending_row_label_2": PENDING_ROW_LABEL_2,
                "pending_row_label_2_attribution": PENDING_ROW_LABEL_2_ATTRIBUTION,
                "pending_row_label_2_reason": PENDING_ROW_LABEL_2_REASON,
                "red_lines_count": len(RED_LINES),
                "red_line_items": list(RED_LINE_ITEMS),
                "red_line_items_note": RED_LINE_ITEMS_NOTE,
                "red_line_pairing": [dict(x) for x in RED_LINE_PAIRING],
                "red_line_merge_reading": RED_LINE_MERGE_READING,
                "red_line_merge_gate": check_merge_reading(),
                "trace_source_kind": TRACE_SOURCE_KIND,
                "trace_kind_gap": TRACE_KIND_GAP,
                "trace_kind_gate": check_source_kind(TRACE_SOURCE_KIND),
                "trace_kind_row_attribution": TRACE_KIND_ROW_ATTRIBUTION,
                "trace_kind_row_reason": TRACE_KIND_ROW_REASON,
                "pending_row_label_3": PENDING_ROW_LABEL_3,
                "pending_row_label_3_table_header": PENDING_ROW_LABEL_3_TABLE_HEADER,
                "pending_row_label_3_attribution": PENDING_ROW_LABEL_3_ATTRIBUTION,
                "pending_row_label_3_reason": PENDING_ROW_LABEL_3_REASON,
                "hw_table_header": HW_TABLE_HEADER,
                "hw_table_rows": [dict(x) for x in HW_TABLE_ROWS],
                "hw_rows_gate": check_hw_rows(),
                "pending": pending_total(),
                "test_cases": test_case_reading(params.get("root")),
                "h3_mode": H3_MODE, "h3_mode_note": H3_MODE_NOTE,
                "h3_mode_2": H3_MODE_2, "h3_mode_2_note": H3_MODE_2_NOTE,
                "h3_mode_2_attribution": H3_MODE_2_ATTRIBUTION,
                "h3_mode_2_pending_reason": H3_MODE_2_PENDING_REASON,
                "h3_mode_3": H3_MODE_3, "h3_mode_3_note": H3_MODE_3_NOTE,
                "h3_mode_3_attribution": H3_MODE_3_ATTRIBUTION,
                "h3_mode_3_pending_reason": H3_MODE_3_PENDING_REASON,
                "h3_mode_4": H3_MODE_4, "h3_mode_4_note": H3_MODE_4_NOTE,
                "h3_mode_4_attribution": H3_MODE_4_ATTRIBUTION,
                "h3_mode_4_pending_reason": H3_MODE_4_PENDING_REASON,
                "candidate_modes": list(CANDIDATE_MODES),
                "candidate_note": CANDIDATE_SUMMARY_NOTE,
                "table_complete": not OPEN_FIELDS,
                "source": OFFICIAL_SKILLS["evidence_note"],
                "ref_not_copy": OFFICIAL_SKILLS["ref_not_copy"]}
    if op == "primitives":
        return {"ok": True, "readonly": True,
                "primitives": [dict(p) for p in PRIMITIVES]}
    if op == "skills":
        return {"ok": True, "readonly": True, "official": dict(OFFICIAL_SKILLS),
                "note": "**只引用技能名与作用**；SKILL.md 内容不进本仓（引用 ≠ 复制）"}
    if op == "hardware":
        return {"ok": True, "readonly": True, "hardware": dict(HARDWARE),
                "gate": check_hardware(params.get("mode") or HARDWARE["mode"],
                                       params.get("vram_gb"))}
    if op == "modalities":
        return {"ok": True, "readonly": True,
                "input": list(INPUT_MODALITIES), "input_note": INPUT_NOTE,
                "output": list(OUTPUT_MODALITIES), "output_note": OUTPUT_NOTE,
                "output_wording_variants": [dict(v) for v in OUTPUT_WORDING_VARIANTS],
                "resolution": RESOLUTION, "resolution_note": RESOLUTION_NOTE,
                "duration": DURATION, "duration_note": DURATION_NOTE,
                "duration_seconds_range": list(DURATION_SECONDS_RANGE),
                "frame_rate": FRAME_RATE, "frame_rate_note": FRAME_RATE_NOTE,
                "frame_rate_fps": FRAME_RATE_FPS,
                "audio": AUDIO, "audio_note": AUDIO_NOTE,
                "audio_sample_rate_khz": AUDIO_SAMPLE_RATE_KHZ,
                "language": LANGUAGE, "language_note": LANGUAGE_NOTE,
                "language_count": LANGUAGE_COUNT,
                "param_scale": PARAM_SCALE, "param_scale_note": PARAM_SCALE_NOTE,
                "param_scale_b": PARAM_SCALE_B,
                "purpose": PURPOSE, "purpose_note": PURPOSE_NOTE,
                "purpose_attribution": PURPOSE_ATTRIBUTION,
                "purpose_attribution_pending_reason":
                    PURPOSE_ATTRIBUTION_PENDING_REASON,
                "purpose_2": PURPOSE_2, "purpose_2_note": PURPOSE_2_NOTE,
                "purpose_3": PURPOSE_3, "purpose_3_note": PURPOSE_3_NOTE,
                "purpose_3_attribution": PURPOSE_3_ATTRIBUTION,
                "purpose_3_pending_reason": PURPOSE_3_PENDING_REASON,
                "tail_variants": list(TAIL_VARIANTS), "tail_note": TAIL_NOTE,
                "purpose_4": PURPOSE_4, "purpose_4_note": PURPOSE_4_NOTE,
                "purpose_4_attribution": PURPOSE_4_ATTRIBUTION,
                "purpose_4_pending_reason": PURPOSE_4_PENDING_REASON,
                "groups_note": GROUPS_NOTE,
                "pending_row_label": PENDING_ROW_LABEL,
                "pending_row_label_attribution": PENDING_ROW_LABEL_ATTRIBUTION,
                "pending_row_label_reason": PENDING_ROW_LABEL_REASON,
                "case_items": list(CASE_ITEMS), "case_items_note": CASE_ITEMS_NOTE,
                "case_pairing": [dict(x) for x in CASE_PAIRING],
                "our_extra_cases": list(OUR_EXTRA_CASES),
                "our_extra_note": OUR_EXTRA_NOTE,
                "case_wording_gaps": [dict(x) for x in CASE_WORDING_GAPS],
                "prose_reject_reason": PROSE_REJECT_REASON,
                "pending_row_label_2": PENDING_ROW_LABEL_2,
                "pending_row_label_2_attribution": PENDING_ROW_LABEL_2_ATTRIBUTION,
                "pending_row_label_2_reason": PENDING_ROW_LABEL_2_REASON,
                "red_lines_count": len(RED_LINES),
                "red_line_items": list(RED_LINE_ITEMS),
                "red_line_items_note": RED_LINE_ITEMS_NOTE,
                "red_line_pairing": [dict(x) for x in RED_LINE_PAIRING],
                "red_line_merge_reading": RED_LINE_MERGE_READING,
                "red_line_merge_gate": check_merge_reading(),
                "trace_source_kind": TRACE_SOURCE_KIND,
                "trace_kind_gap": TRACE_KIND_GAP,
                "trace_kind_gate": check_source_kind(TRACE_SOURCE_KIND),
                "trace_kind_row_attribution": TRACE_KIND_ROW_ATTRIBUTION,
                "trace_kind_row_reason": TRACE_KIND_ROW_REASON,
                "pending_row_label_3": PENDING_ROW_LABEL_3,
                "pending_row_label_3_table_header": PENDING_ROW_LABEL_3_TABLE_HEADER,
                "pending_row_label_3_attribution": PENDING_ROW_LABEL_3_ATTRIBUTION,
                "pending_row_label_3_reason": PENDING_ROW_LABEL_3_REASON,
                "hw_table_header": HW_TABLE_HEADER,
                "hw_table_rows": [dict(x) for x in HW_TABLE_ROWS],
                "hw_rows_gate": check_hw_rows(),
                "pending": pending_total(),
                "test_cases": test_case_reading(params.get("root")),
                "h3_mode": H3_MODE, "h3_mode_note": H3_MODE_NOTE,
                "h3_mode_2": H3_MODE_2, "h3_mode_2_note": H3_MODE_2_NOTE,
                "h3_mode_2_attribution": H3_MODE_2_ATTRIBUTION,
                "h3_mode_2_pending_reason": H3_MODE_2_PENDING_REASON,
                "h3_mode_3": H3_MODE_3, "h3_mode_3_note": H3_MODE_3_NOTE,
                "h3_mode_3_attribution": H3_MODE_3_ATTRIBUTION,
                "h3_mode_3_pending_reason": H3_MODE_3_PENDING_REASON,
                "h3_mode_4": H3_MODE_4, "h3_mode_4_note": H3_MODE_4_NOTE,
                "h3_mode_4_attribution": H3_MODE_4_ATTRIBUTION,
                "h3_mode_4_pending_reason": H3_MODE_4_PENDING_REASON,
                "candidate_modes": list(CANDIDATE_MODES),
                "candidate_note": CANDIDATE_SUMMARY_NOTE,
                "table_complete": not OPEN_FIELDS,
                "note": "输入行 / 输出行=主人提供（逐字）；"
                        "分辨率=最高 2K（经 H3-Regenerate-2K）；"
                        "时长=2–15 秒（en dash 原样）；"
                        "帧率=24 FPS；"
                        "音频=32 kHz 立体声；"
                        "语言=稳定支持 11 种语言的对话；"
                        "参数规模=33.1B DiT（扩散 Transformer）；"
                        "对应 H3 模式=T2VA（与原语第一项互证）；"
                        "作用=文本 → 带音频视频（**归属为推断、待主人确认**）；"
                        "第二组：作用=图片 → 带音频视频（与候补行 I2VA **推论配对**、待确认）"}
    if op == "gate_blank":
        return check_open_fields()
    if op == "gate_merge":
        return check_merge_reading()
    if op == "gate_hw_threshold":
        return check_hw_threshold()
    if op == "gate_source_kind":
        return check_source_kind(params.get("source_kind"))
    if op == "gate_hw_rows":
        return check_hw_rows()
    if op == "pending":
        return pending_total()
    if op == "test_cases":
        return test_case_reading(params.get("root"))
    if op == "gate_duration":
        return check_duration_verbatim()
    if op == "gate_verbatim":
        return check_verbatim_fields(params.get("field"))
    if op == "redlines":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES)}
    if op == "gate_key":
        return check_no_plaintext_key(params.get("payload"))
    if op == "gate_localize":
        return check_must_localize(params.get("targets"), params.get("audio"))
    if op == "gate_prompt":
        return check_prompt_structure(params.get("sections"), params.get("prompt"),
                                      int(params.get("required") or 6))
    if op == "gate_hw":
        return check_hardware(params.get("mode") or "api", params.get("vram_gb"),
                              params.get("min_gb"))
    if op == "gate_official":
        return check_via_official(params.get("entry"))
    raise ValueError("未知 op %r（可用：status/primitives/skills/hardware/redlines/"
                     "modalities/gate_key/gate_localize/gate_prompt/gate_hw/"
                     "gate_official/gate_blank/gate_merge/gate_hw_threshold/"
                     "gate_source_kind/gate_hw_rows/gate_duration/gate_verbatim/"
                     "test_cases）" % (op,))


HONEST_BOUNDARY = (
    "本骨架保证『四原语 / 三条带牙用例 / 五条红线 / 硬件门槛』可查、可判；"
    "它**保证不了**「H3mini 能跑」—— 官方技能包未装、密钥盘上没有、"
    "显存读数拿不到（本地 32GB+ 门槛当下不满足）⇒ 结论是 **API 模式 + 等钥匙**。"
    "官方六段式的**段名**未取证 ⇒ 本模块只判「有没有按段给」，**不编段名**。"
    "本模块依据的细节来自主人提供 ⇒ 一律按「主人提供 · 待核」对待。"
)
