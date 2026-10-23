# -*- coding: utf-8 -*-
"""万能插 · Awesome Tools 蒸馏索引（Awesome Tools Index）· 只读骨架 v1.0

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

🔴 核心命题（R-H285 主人定）：

    **这个仓库不是「代码」，是「地图」。**
    它告诉你「有哪些工具可以用」；本框架要做的，是把这些工具**接进万能插变成能力位**。

    地图上的每一个工具，都是一条潜在的触手。
    —— 关键是：**不照搬，只引用；不复制，只映射。工具可以换，身份不变。**

本模块**只读**：INDEX / LOOKUP / MAP / VERIFY 四个原语都不写盘、不出网、不装东西。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

CAP_KIND = "awesome_tools_index"
DOMAIN = "tools"
CAP_TYPE = "external"
TRACE_SOURCE_KIND = "awesome_tools"

CORE_PROPOSITION = ("这个仓库不是「代码」，是「地图」：只引用不复制、只映射不照搬；"
                    "地图上的每个工具都是一条潜在的触手 —— **工具可以换，身份不变**")

PRIMITIVES = (
    {"key": "INDEX", "cn": "检索", "writes": False,
     "note": "**按分类检索工具**（只读）"},
    {"key": "LOOKUP", "cn": "详情", "writes": False,
     "note": "看单个工具的形状：它是什么、干什么用（只读）"},
    {"key": "MAP", "cn": "映射", "writes": False,
     "note": "**工具 → 能力位** —— 每条都必须带**出处**，无出处不许进映射"},
    {"key": "VERIFY", "cn": "核实", "writes": False,
     "note": "**验证工具是否已安装 / 可接入** —— 未核实不许标 green"},
)

# 分类（**主人逐字给的**，未独立取证）
CATEGORIES_OWNER = (
    "编程工作区", "智能体生态", "视频创作流水线", "可视化面板", "文档工具",
    "环境配置", "网络加速", "文本工具", "数据层", "版本控制", "调试工具",
    "测试工具", "部署工具", "网络工具", "安全工具", "多媒体", "扩展生态",
)
CATEGORIES_NOTE = ("分类名来自**主人提供**（Awesome Tools 仓库的目录结构）⇒ "
                   "标『主人提供 · 未独立取证』；本骨架**不补分类、不改分类名**")

# 🔴 主人**明确配对**的六个重点工具（逐字 + 出处 = 主人这轮的话）
KEY_TOOLS = (
    {"name": "CC Switch", "owner_use": "直接对接自动切换引擎（供应商路由 + 一键切换）",
     "maps_to": "auto_switch", "status": "unverified", "evidence": None,
     "evidence_note": "盘上 **0 命中**（2026-09-20 取证）"},
    {"name": "MoneyPrinterTurbo", "owner_use": "视频创作流水线能力位",
     "maps_to": "video_pipeline", "status": "unverified", "evidence": None,
     "evidence_note": "盘上 **0 命中**（2026-09-20 取证）"},
    {"name": "Huobao Drama", "owner_use": "视频创作流水线能力位",
     "maps_to": "video_pipeline", "status": "unverified", "evidence": None,
     "evidence_note": "盘上 **0 命中**（2026-09-20 取证）"},
    {"name": "LocalMiniDrama", "owner_use": "视频创作流水线能力位",
     "maps_to": "video_pipeline", "status": "unverified", "evidence": None,
     "evidence_note": "盘上 **0 命中**（2026-09-20 取证）"},
    {"name": "CowAgent", "owner_use": "多平台接入能力（微信 / 飞书 / 钉钉 / QQ）",
     "maps_to": "im_multiplex", "status": "unverified", "evidence": None,
     "evidence_note": "盘上 **0 命中**（2026-09-20 取证）"},
    {"name": "OpenClaw Monitor", "owner_use": "上帝视角的监控组件",
     "maps_to": "god_view", "status": "unverified", "evidence": None,
     "evidence_note": "盘上 **0 命中**（2026-09-20 取证）"},
)
KEY_TOOLS_NOTE = ("六条都是**主人提供 · 未独立取证** —— 本骨架只登记「主人怎么配的」，"
                  "**一条都不标绿**（未核实不标绿）")

# 主人给的、但**没有明确配对**的碎片 ⇒ 待归位（**有理由的空**，不硬配）
OWNER_FRAGMENTS = (
    "作为本地编程能力的备选引擎", "本地代码补全引擎", "本地模型备选",
    "外部增强（可选）", "短视频创作流水线", "短剧生成能力位", "短剧专线",
    "本地视频创作", "多平台接入能力", "上帝视角的监控组件",
    "知识库层备选", "外部知识库",
    # 🔺 R-H351 **追溯补登记**：它出自主人**早前那条长消息**，当时**漏登记**
    #    （实测：模块与文档对「命令行」都是 **0 命中**）⇒ 补进**待归位**，**不硬配**
    "命令行版本",
)
OWNER_FRAGMENTS_NOTE = ("这些短语出自主人这轮消息，但**没有「哪个短语配哪个工具」的明确说法** ⇒ "
                        "只登记为**待归位**，**不硬配**（硬配就是造第二处真相）；"
                        "待主人一句话归位或授权取证后补；"
                        "⚠️ **R-H351 追溯补登记**：末条『命令行版本』出自主人**早前那条长消息**，"
                        "当时**漏登记**（模块与文档实测 **0 命中**）⇒ 本刀**补进待归位**、"
                        "**不硬配**；它与 R-H351 那句的句头『命令行版』"
                        "**同前缀、不同尾** ⇒ **并排记、不许当同一个**")

# 取证读数（2026-09-20 · 本刀现场取）
EVIDENCE_2026_09_20 = {
    "checked": "六个重点工具名 + 两个技能目录",
    "hits": {t["name"]: 0 for t in KEY_TOOLS},
    "skills_dirs": {
        "~/.openclaw-autoclaw/skills": {"exists": True, "count_seen": 73,
                                        "note": "已装技能面（含 ffmpeg-video-editor / cursor-agent 等）"},
        "~/.openclaw/skills": {"exists": True, "count_seen": 28,
                               "note": "全是 lark-* 技能"},
    },
    "conclusion": "六个重点工具**一个都不在盘上**；技能目录存在但它装的是别的东西 "
                  "⇒ 六条一律 unverified",
    "repo_evidenced": False,
    "repo_note": "Awesome Tools 仓库内容**未独立取证**（出网受限）⇒ 不引内容、不补清单",
}

RED_LINES = (
    "索引只读：INDEX / LOOKUP 不许带任何**写动作**（只呈现，不执行）",
    "映射可追：每条「工具 → 能力位」必须带**出处**，无出处不许进映射",
    "未核实不标绿：只有**核实过**的才允许 green；没核实一律 unverified",
    "只引用不复制：**不把仓库内容抄进本仓**（引用 ≠ 复制）",
    "不绕官方入口：工具要走它**自己的**官方入口，不许替它拼请求",
)

_WRITE_WORDS = re.compile(r"(安装|下载|执行|运行|写入|删除|修改|install|execute|rm )")


def check_index_readonly(payload: Any = None) -> dict:
    """带牙用例①：**索引只读** —— 检索里混进写动作 ⇒ 拒。"""
    text = str(payload or "")
    m = _WRITE_WORDS.search(text)
    if m:
        return {"ok": False, "denied": True, "rule": "index_not_readonly",
                "hit": m.group(0),
                "why": "INDEX / LOOKUP 只呈现不执行 —— 带写动作的检索等于把地图当扳手用"}
    return {"ok": True, "readonly": True, "checked": "payload", "hit": 0}


def check_map_traceable(entries: Optional[Sequence[Any]] = None) -> dict:
    """带牙用例②：**映射可追** —— 每条映射必须有出处，无出处 ⇒ 拒。"""
    if entries is None:
        return {"ok": True, "readonly": True,
                "note": "未提供映射 ⇒ 本闸不适用（不扩大化）"}
    bad: List[str] = []
    for row in entries:
        r = dict(row)
        if not str(r.get("name") or "").strip():
            bad.append("缺 name")
        if not str(r.get("maps_to") or "").strip():
            bad.append("%s：缺 maps_to" % r.get("name"))
        if not str(r.get("evidence") or "").strip():
            bad.append("%s：缺 evidence（出处）" % r.get("name"))
    if bad:
        return {"ok": False, "denied": True, "rule": "map_without_source",
                "bad": bad,
                "why": "**映射可追**：每条「工具 → 能力位」都要有出处 —— "
                       "没有出处的映射就是猜的，猜的会被当成已知的用"}
    return {"ok": True, "readonly": True, "entries": len(list(entries))}


_GREEN = ("green", "绿", "ok", "verified", "已核实")


def check_verify_status(status: Any = None, evidence: Any = None) -> dict:
    """带牙用例③：**未核实不标绿** —— green 必须带核实证据。"""
    s = str(status or "").strip().lower()
    if not s:
        return {"ok": True, "readonly": True, "status": "unverified",
                "note": "没给状态 ⇒ 一律按 unverified（默认不绿）"}
    if s in _GREEN:
        if not str(evidence or "").strip():
            return {"ok": False, "denied": True, "rule": "unverified_green",
                    "status": s,
                    "why": "**未核实不标绿**：标 green 必须给出核实证据（什么时候、怎么核的）"}
        return {"ok": True, "readonly": True, "status": "green", "evidence": evidence}
    return {"ok": True, "readonly": True, "status": "unverified",
            "note": "非 green 状态照收（本闸只拦『没证据就标绿』）"}


# 🔴 R-H287：主人开始**逐节**给蒸馏稿（「一、仓库定位与架构」+ 表头「维度」…）
#    ⇒ 每节一格：标题 / 表头 / 条目 / **留空必须带理由**（§57），并有闸守着
SECTIONS_OWNER = (
    {"no": "一", "heading": "仓库定位与架构", "table_header": "维度",
     "intro": None,
     "items": (), "source": "主人提供 · R-H287 · 逐字",
     "pending_reason": None},
    {"no": "二", "heading": "分类体系蒸馏", "table_header": "分类",
     "intro": "仓库按开发全生命周期组织，核心分类如下：",
     "items": (), "source": "主人提供 · R-H293 · 逐字",
     "pending_reason": ("主人给到章节标题『二、分类体系蒸馏』+ 引言逐字 + 表头『分类』，"
                        "**表内容截断** ⇒ 留空带理由（§57）；**不许凭标题编分类**")},
)
SECTIONS_NOTE = ("**逐节登记**：节到了就建格，内容没到就留空带理由；"
                 "**不许凭标题编内容**；有内容的节必须能追到出处")

# 主人这轮的两句**逐字**（与我方命题**并排记、不合并**）
OWNER_20260920_R287 = (
    "这个仓库我已经深度蒸馏提炼完毕。它不是一个代码项目，而是一份 Awesome Tools 精选工具清单，"
    "收录了程序员常用的高效实用工具和软件资源。",
)
# ⚠️ 本定义**必须在 CORE_CROSSCHECK 之前** —— 模块级常量不许引用后文才定义的常量
#    （R-H274 记过这条；R-H290 又踩一次 ⇒ 说明它该进「写前自检」清单，见坑册）
CORE_SOURCES = (
    {"by": "主人", "round": "R-H287",
     "says": "它不是一个代码项目，而是一份 Awesome Tools 精选工具清单，收录了程序员常用的高效实用工具和软件资源"},
    {"by": "主人", "round": "R-H290",
     "says": "Awesome 清单——不是代码，是工具索引"},
    {"by": "我方", "round": "R-H285",
     "says": "这个仓库不是「代码」，是「地图」"},
    {"by": "主人", "round": "R-H293",
     "says": ("它本身没有技术架构，但它是一张能力地图——"
              "告诉我们有哪些现成的工具可以接入 GBT小土豆V8。")},
)

CORE_CROSSCHECK = {
    "owner_says": "不是一个代码项目，而是一份…**清单**（收录…工具和软件资源）",
    "ours_says": "这个仓库不是「代码」，是「**地图**」",
    "same_direction": True,
    "wording_differs": True,
    "note": ("同向、措辞不同（**清单 / 资源** vs **地图 / 能力位**）⇒ "
             "**并排记、不擅自合并**；哪一张作为正式口径 ⇒ 待主人定"),
    "sources": CORE_SOURCES,
    "common_claim": "不是代码",
    "common_claims": ("不是代码", "地图"),
    "divergence": ("后半句措辞：**清单 / 工具索引**（主人 R-H287/R-H290）⇔ "
                   "**地图 / 能力位**（我方 R-H285）—— R-H293 主人也说了「能力地图」⇒ "
                   "「是地图」这一条**从分歧变成了共同主张**（仍并排留原文，不合并）"),
    "merged": False,
}


def check_sections() -> dict:
    """闸⑪（R-H287）：**逐节蒸馏稿**三条 —— 空必带理由 · 有内容必须有出处 · 空样本不按绿。

    为什么单立：主人是**一节一节**给的，节与节之间隔着时间 ——
    没有这一格，「哪节到了、哪节还空着、为什么空」就会散在对话里，过期即丢。
    """
    secs = list(SECTIONS_OWNER)
    # 节的内容**也可以来自字段格**（R-H293 现场：第一节的 items 是空的，
    # 它的六个字段全在 SECTION_ROWS_OWNER 里 ⇒ 不能因此判它「空且没理由」）
    owns = {str(r.get("section") or "").strip() for r in SECTION_ROWS_OWNER}
    if not secs:
        return {"ok": False, "denied": True, "rule": "sections_empty",
                "why": "一节都没有 ⇒ **空样本不按绿**"}
    out = []
    for s in secs:
        heading = str(s.get("heading") or "").strip()
        items = list(s.get("items") or ())
        reason = str(s.get("pending_reason") or "").strip()
        source = str(s.get("source") or "").strip()
        if not heading:
            return {"ok": False, "denied": True, "rule": "section_without_heading",
                    "why": "每节必须有标题（否则事后对不上是哪一节）"}
        has_rows = heading and str(s.get("no") or "").strip() in owns
        if not items and not reason and not has_rows:
            return {"ok": False, "denied": True, "rule": "section_blank_without_reason",
                    "heading": heading,
                    "why": "节的条目留空必须写明理由（§57：有理由的空 ≠ 未处理的残留）"}
        if items and not source:
            return {"ok": False, "denied": True, "rule": "section_without_source",
                    "heading": heading, "items": len(items),
                    "why": "有内容的节必须能追到**出处**（谁给的、哪一轮）"}
        out.append({"no": str(s.get("no") or "").strip(), "heading": heading,
                    "table_header": str(s.get("table_header") or "") or None,
                    "intro": str(s.get("intro") or "") or None,
                    "items": items, "has_items": bool(items),
                    "has_rows": bool(has_rows),
                    "source": source or None,
                    "pending_reason": reason or None})
    return {"ok": True, "readonly": True, "sections": out, "count": len(out),
            "complete": all(x["has_items"] or x["has_rows"] for x in out),
            "core_crosscheck": dict(CORE_CROSSCHECK),
            "note": SECTIONS_NOTE}

# 🔴 R-H288：主人开始给**节内字段名**（第一个：『仓库名』）⇒ 一格一字段，值没到就留空带理由
SECTION_ROWS_OWNER = (
    {"section": "一", "field": "仓库名",
     "scope": "**被索引仓库的正式标识**（owner/repo）",
     "value": "paysssk-creator/AIfuzhugongju",
     "value_verbatim": "paysssk-creator/AIfuzhugongju",
     "numbers": (),
     "source": "主人提供 · R-H289 · 逐字",
     "note": ("🔴 **同 owner、不同仓库**：`paysssk-creator` 底下有两个 —— "
              "`AIfuzhugongju` 是**这份工具清单**，`GBT-V8` 是**本框架自己** ⇒ "
              "**不许混**（前缀一致 ≠ 同一个）"),
     "pending_reason": None},
    {"section": "一", "field": "本质",
     "scope": "**这份清单是什么**（定性），不是它的用法也不是它的规模",
     "value": "Awesome 清单——不是代码，是工具索引",
     "value_verbatim": "Awesome 清单——不是代码，是工具索引",
     "numbers": (),
     "source": "主人提供 · R-H290 · 逐字",
     "note": ("主人这句与我方 R-H285 命题『不是代码，是地图』**同向** —— "
              "**「不是代码」两边都在说**（互证成立的部分）；但后半句措辞不同"
              "（工具索引 ⇔ 地图 / 能力位）⇒ **并排记、不合并**（见 CORE_CROSSCHECK）"),
     "pending_reason": None},
    {"section": "一", "field": "规模",
     "scope": ("**README 的篇幅**（行数 / 体积）—— **不是**收录条数、**不是** star、"
               "**不是**贡献者数（三种常被当成「规模」的东西，这里都不是）"),
     "value": "README.md 约 949 行 / 159 KB",
     "value_verbatim": "README.md 约 949 行 / 159 KB",
     "numbers": (949, 159),
     "source": "主人提供 · R-H291 · 逐字",
     "note": ("🔴 这是**被索引仓库的 README 读数**，**不是本仓（GBT-V8）的读数**；"
              "949 / 159 由主人提供、**未独立取证** ⇒ **不标绿**")},
    {"section": "一", "field": "目录结构",
     "scope": ("**这份清单怎么组织的**（散文分类 + 表格列）——"
               "🔴 **不是文件目录树**（我方上一刀默认理解成目录树，主人给的是表格 ⇒ 照主业记）"),
     "value": "按工具类型分类的表格（工具名 / 详细介绍 / 下载地址）",
     "value_verbatim": "按工具类型分类的表格（工具名 / 详细介绍 / 下载地址）",
     "numbers": (),
     "columns": ("工具名", "详细介绍", "下载地址"),
     "source": "主人提供 · R-H292 · 逐字",
     "note": ("三个列名 = **列契约**：将来每条工具条目按 `工具名 / 详细介绍 / 下载地址` 三列落；"
              "组织方式是「**按工具类型分类**」⇒ 分类名沿用 CATEGORIES_OWNER（主人提供）")},
    {"section": "一", "field": "核心价值",
     "scope": "**这份清单对我们的价值**（它解决了什么）",
     'value': '一份"按开发-测试-部署-运维-协作链路"分类的工具导航',
     'value_verbatim': '一份"按开发-测试-部署-运维-协作链路"分类的工具导航',
     "numbers": (), "ignored_numbers": (), "ignored_reason": None,
     "columns": None, "ours_says": None,
     "source": "主人提供 · R-H293 · 逐字",
     "note": ("逐字里的双引号是**英文双引号** ⇒ 原样留（我方不改成中文引号）"),
     "pending_reason": None},
    {"section": "一", "field": "关键定性",
     "scope": "**这份清单的定性判语**（它是/不是什么样的东西）",
     "value": ("它本身没有技术架构，但它是一张能力地图——"
               "告诉我们有哪些现成的工具可以接入 GBT小土豆V8。"),
     "value_verbatim": ("它本身没有技术架构，但它是一张能力地图——"
                        "告诉我们有哪些现成的工具可以接入 GBT小土豆V8。"),
     "numbers": (), "ignored_numbers": (8,),
     "ignored_reason": "「GBT小土豆**V8**」里的 8 是**版本号的一部分**，不是读数",
     "columns": None, "ours_says": None,
     "source": "主人提供 · R-H293 · 逐字",
     "note": ("🔴 主人这句里**也说了「一张能力地图」** ⇒ 与我方 R-H285『是地图』互证"
              "（共同主张第二条，见 CORE_CROSSCHECK.common_claims）；"
              "另：『它本身没有技术架构』是**主人的定性**，我方**不替它引申**")},
)

# 🔴 R-H289：本框架**自己**的仓库名 —— 用来把「被索引的仓库」与「跑索引的仓库」分开
SELF_REPO = "paysssk-creator/GBT-V8"
SELF_REPO_NOTE = ("来自主人早前给本仓 remote 的口径；**它是本框架自己**，"
                  "不是被索引的那份工具清单 —— 两者同 owner，最容易被当成一个")
SECTION_ROWS_NOTE = ("**节内字段格**：格必须挂在**已登记的节**下（不许挂空）；"
                     "值没到就留空带理由；有值必须能追到出处")


def check_section_rows() -> dict:
    """闸⑫（R-H288）：**节内字段格**四条 —— 不许挂空 · 空必带理由 · 有值必须有出处 · 空样本不按绿。

    为什么要有「不许挂空」：节是**一节一节**到的，字段是**一格一格**到的 ——
    两者对不上时（格挂在没登记的节上），事后没人数得清，也没人发现得了。
    """
    rows = list(SECTION_ROWS_OWNER)
    if not rows:
        return {"ok": False, "denied": True, "rule": "rows_empty",
                "why": "一格都没有 ⇒ **空样本不按绿**"}
    known = {str(s.get("no") or "").strip() for s in SECTIONS_OWNER}
    out = []
    for r in rows:
        sec = str(r.get("section") or "").strip()
        field = str(r.get("field") or "").strip()
        value = r.get("value")
        reason = str(r.get("pending_reason") or "").strip()
        source = str(r.get("source") or "").strip()
        if not sec or not field:
            return {"ok": False, "denied": True, "rule": "row_without_section_or_field",
                    "section": sec, "field": field,
                    "why": "每格都要写清**挂在哪一节、叫什么字段**"}
        if sec not in known:
            return {"ok": False, "denied": True, "rule": "row_section_unregistered",
                    "section": sec, "field": field, "registered": sorted(known),
                    "why": "格必须挂在**已登记的节**下 —— 挂空 = 事后数不清"}
        if value is None and not reason:
            return {"ok": False, "denied": True, "rule": "row_blank_without_reason",
                    "section": sec, "field": field,
                    "why": "字段值留空必须写明理由（§57）"}
        ours = str(r.get("ours_says") or "").strip()
        if value is None and ours and "不许拿我方" not in reason:
            return {"ok": False, "denied": True, "rule": "row_inference_guard_missing",
                    "section": sec, "field": field,
                    "ours_says": ours,
                    "why": "这格**我方已经有说法**，而值还没到 ⇒ 理由必须写明"
                           "「**不许拿我方推论顶上**」（否则我方说法会静悄悄变成主人的）"}
        if value is not None and not source:
            return {"ok": False, "denied": True, "rule": "row_value_without_source",
                    "section": sec, "field": field, "value": value,
                    "why": "有值必须能追到**出处**（谁给的、哪一轮）"}
        if value is not None:
            v = str(value)
            if "/" in v:
                if v == SELF_REPO:
                    return {"ok": False, "denied": True,
                            "rule": "row_repo_is_self", "value": v,
                            "self_repo": SELF_REPO,
                            "why": "**被索引的仓库不许是本仓自己** —— "
                                   "拿自己当第三方工具清单，会把整张地图指歪"}
                owner = v.split("/")[0]
                if owner == SELF_REPO.split("/")[0] and not str(r.get("note") or "").strip():
                    return {"ok": False, "denied": True,
                            "rule": "row_repo_owner_prefix_unstated",
                            "value": v, "self_repo": SELF_REPO, "owner": owner,
                            "why": "与 **SELF_REPO 共享 owner 前缀** ⇒ 必须在 note 里写清"
                                   "「同 owner、不同仓库，不许混」"
                                   "（前缀一致 ≠ 同一个 —— 与『前缀一致必须并排记』同族）"}
        if value is not None:
            if not source:
                return {"ok": False, "denied": True, "rule": "row_value_without_source",
                        "section": sec, "field": field, "value": value,
                        "why": "有值必须能追到**出处**（谁给的、哪一轮）"}
            scope = str(r.get("scope") or "").strip()
            if not scope:
                return {"ok": False, "denied": True, "rule": "row_scope_missing",
                        "section": sec, "field": field,
                        "why": "**已填的格必须写明 scope（这格说的是什么量）** —— "
                               "「规模」这种词最容易被三种东西轮流冒充"}
            nums_here = sorted(float(x) for x in _numbers(str(r.get("value_verbatim") or "")))
            nums_kept = sorted(float(x) for x in (r.get("numbers") or ()))
            ign = sorted(float(x) for x in (r.get("ignored_numbers") or ()))
            ignore_reason = str(r.get("ignored_reason") or "").strip()
            if ign and not ignore_reason:
                return {"ok": False, "denied": True,
                        "rule": "row_ignore_without_reason",
                        "section": sec, "field": field, "ignored_numbers": ign,
                        "why": "要豁免某个数可以，但**豁免必须写明理由**（不写就是静默丢数）"}
            if nums_here != sorted(nums_kept + ign):
                return {"ok": False, "denied": True, "rule": "row_numbers_unaccounted",
                        "section": sec, "field": field,
                        "in_verbatim": nums_here, "numbers": nums_kept,
                        "ignored_numbers": ign,
                        "why": "逐字里的数**双向对账**：一个不许漏、一个不许多"
                               "（要豁免就走 ignored_numbers 并给理由）"}
            cols = tuple(str(x) for x in (r.get("columns") or ()))
            if cols:
                missing = [c for c in cols if c not in str(r.get("value_verbatim") or "")]
                if missing:
                    return {"ok": False, "denied": True, "rule": "row_columns_unaccounted",
                            "section": sec, "field": field, "missing": missing,
                            "why": "登记了列契约 ⇒ 每个列名都必须在**逐字**里真的出现"}
        out.append({"section": sec, "field": field, "value": value,
                    "has_value": value is not None, "source": source or None,
                    "scope": str(r.get("scope") or "") or None,
                    "numbers": list(r.get("numbers") or ()) or None,
                    "columns": list(r.get("columns") or ()) or None,
                    "ours_says": str(r.get("ours_says") or "") or None,
                    "pending_reason": reason or None})
    return {"ok": True, "readonly": True, "rows": out, "count": len(out),
            "complete": all(x["has_value"] for x in out),
            "note": SECTION_ROWS_NOTE}

_QUOTES = "「」『』\"\""

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def _numbers(text: Any) -> List[Any]:
    """抽数字（**含黏字母的**：`949 行 / 159 KB` 两个都要，`33.1B` 里的 33.1 也算）。"""
    return [float(x) if "." in x else int(x) for x in _NUM_RE.findall(str(text or ""))]


def _bare(text: Any) -> str:
    """去掉引号再看（「代码」与 代码 是同一件事 —— 判据别被排版绊住）。"""
    out = str(text or "")
    for ch in _QUOTES:
        out = out.replace(ch, "")
    return out


def check_core_crosscheck() -> dict:
    """闸⑬（R-H290）：**同一件事多种说法**的三条 —— 共同主张要真在多边出现 ·
    分歧必须写出来 · **不许静默合并**。

    为什么单立：这是今天第三次遇到「像但不等于」——
    前两次是「前缀一致的两条记录」「同 owner 的两个仓库」，这次是「同一件事的三句话」。
    共同点与分歧点**都要显式**：只记共同点会静默合并，只记分歧点会看不见其实是同一件。
    """
    srcs = list(CORE_SOURCES)
    if len(srcs) < 2:
        return {"ok": False, "denied": True, "rule": "crosscheck_sources_missing",
                "count": len(srcs), "why": "少于两方就说不上「并排」"}
    cc = CORE_CROSSCHECK
    claims = tuple(str(x) for x in (cc.get("common_claims")
                                   or (cc.get("common_claim"),)) if str(x).strip())
    if not claims:
        return {"ok": False, "denied": True, "rule": "crosscheck_no_common",
                "why": "必须显式写出**共同主张**（否则并排就只剩分歧，看不出是同一件事）"}
    claim = claims[0]
    if not claim:
        return {"ok": False, "denied": True, "rule": "crosscheck_no_common",
                "why": "必须显式写出**共同主张**（否则并排就只剩分歧，看不出是同一件事）"}
    hits_all = {}
    for c in claims:
        h = [s["round"] for s in srcs if c in _bare(s["says"])]
        if len(h) < 2:
            return {"ok": False, "denied": True, "rule": "crosscheck_common_not_shared",
                    "common_claim": c, "appears_in": h,
                    "why": "写的共同主张必须**真的**在多边原句里出现 —— "
                           "否则那是我们自封的共同点"}
        hits_all[c] = h
    hits = hits_all.get(claim, [])
    if len(hits) < 2:
        return {"ok": False, "denied": True, "rule": "crosscheck_common_not_shared",
                "common_claim": claim, "appears_in": hits,
                "why": "写的共同主张必须**真的**在多边原句里出现 —— 否则那是我们自封的共同点"}
    if not str(cc.get("divergence") or "").strip():
        return {"ok": False, "denied": True, "rule": "crosscheck_divergence_missing",
                "why": "分歧点也必须写出来（只记共同点 = 静默合并）"}
    if bool(cc.get("merged")):
        return {"ok": False, "denied": True, "rule": "crosscheck_silently_merged",
                "why": "**不许静默合并**：措辞不同的几张说法并排留，哪张作正式口径由主人定"}
    return {"ok": True, "readonly": True, "sources": len(srcs),
            "common_claim": claim, "appears_in": hits,
            "divergence": cc.get("divergence"), "merged": False,
            "note": "**共同点与分歧点都显式**：共同点靠机械核（真的在多边出现），分歧点靠人写"}

# 🔴 R-H352：主人给的那段正文里含**中文引号** ⇒ 用**单引号字面量**逐字保留
#    （本仓预检只盯「同一行里同时有中文引号与英文双引号」⇒ 单引号行不触雷）
PARA_R_H352 = ('这是本仓库与 GBT 最直接相关的部分——CC Switch 的本质就是'
               '“供应商路由 + 一键切换”，这正是自动化切换引擎需要的。')

# 🔴 R-H360：这句含**中文引号** ⇒ 用**单引号字面量**逐字保留（同 R-H352 的处理）
HUOBAO_DETAIL_R_H360 = ('Go + Vue3，覆盖“剧本解析 → 角色/分镜生成 → 视频合成”全链路')

# 🔴 R-H366：**呼应要可算**（现算，不靠感觉）——把两边都去掉空白/标点后，
#    看「介绍」与「我方 `owner_use`」有没有 **≥4 字连续重合**。
#    ⚠️ 只用于**读数**：命中只说明「像」，**永远不当许可**。
_ECHO_STRIP = re.compile(r"[\s\u3000/（）()\[\]【】、，,。.·\-—+\|｜]+")
_ECHO_MIN = 4


def _echo_norm(text: object) -> str:
    return _ECHO_STRIP.sub("", str(text or ""))


def _echo_hit(a: object, b: object, n: int = _ECHO_MIN) -> bool:
    """两边去噪后是否存在 **≥n 字连续重合**（一个方向即可）。"""
    A, B = _echo_norm(a), _echo_norm(b)
    if len(A) < n or len(B) < n:
        return False
    return any(A[i:i + n] in B for i in range(0, len(A) - n + 1))


def _owner_use_map() -> dict:
    return {str(t.get("name") or ""): str(t.get("owner_use") or "") for t in KEY_TOOLS}


# 🔴 R-H294：主人给了四个字『代表工具』，**没说是哪一格** ⇒ 两种读法并排，**不擅自判定**
PENDING_ATTRIBUTION = (
    {"token": "代表工具",
     "readings": ("① 第一节表（表头「维度」）的**第七个字段名**（值待给）",
                  "② 第二节（表头「分类」）那张表的**列名**（分类表的一列）"),
     "ours_says": ("我方在 R-H285 按主人另一段话登记过六个重点工具"
                   "（CC Switch / MoneyPrinterTurbo / Huobao Drama / LocalMiniDrama / "
                   "CowAgent / OpenClaw Monitor）"),
     "pending_reason": ("两读法并排、**不擅自判定** ⇒ 本刀既不塞进第一节、也不塞进第二节；"
                        "🔴 **不许拿我方那六个工具顶上** —— 它们是我方按另一段话登记的，"
                        "不是这格给的『代表工具』）。"
                        "🔺 R-H295 **证据 +1**：主人又给了一个同族列名『对应 GBT 能力域』"
                        "⇒ 读法②（分类表列名）更像了，但**仍不擅自定论**（主人没明说）；"
                        "🔺 R-H296 行为证据再 +1 ⇒ **仍在等主人一句话**（证据再强也不自解）"),
     "action_evidence": ("🔺 **行为证据（R-H296）**：主人把这份工具清单直接填进了"
                         "『代表工具』**这一列** ⇒ 读法②（第二节列名）**得到强支持**"),
     "resolved": None},  # 🔴 证据再强也不自解 —— 仍在等主人一句话
    {"token": "IDE & 代码编辑器",
     "readings": ("① 第一个分类『AI辅助编程工具』的**『对应 GBT 能力域』格**的值",
                  "② **第五个分类名**（Awesome 清单里常见的一类：IDE 与代码编辑器）"),
     "ours_says": None,
     "pending_reason": ("两读法并排、**不擅自判定** ⇒ 本刀**两个都不填**："
                        "既没塞进第一个分类的『对应 GBT 能力域』格，也没建第五个分类；"
                        "🔺 R-H305 **行为证据 +1**：主人紧接着给了一份工具清单"
                        "（VS Code / Trae 等）⇒ 强烈支持**读法②**"
                        "（它是第五个分类名，那份清单是它的『代表工具』）；"
                        "🔴 但**仍不擅自定论** —— **仍在等主人一句话**；"
                        "本刀把那份清单**暂存**在 `staged_value`（**不落进任何表**）"),
     "staged_value": "VS Code / Trae 等",
     "staged_note": ("⏸ **暂存、不落表**：主人给的清单不能丢，但归属没定 ⇒ "
                     "**既不许建第五个分类、也不许塞进任何格**；等一句话再落"),
     "resolved": None},
    {"token": "特点",
     "readings": ("① **第一节表**（表头「维度」）的**第八个字段名**（值待给）",
                  "② **源表**（R-H334 那三列）之外的**第四个列名** —— 若源表不止三列",
                  "③ 某个分类下**工具那一行的属性名**（与「详细介绍」同族的一栏）"),
     "ours_says": None,
     "pending_reason": ("主人只给了一个词『特点』、**没说挂哪儿** ⇒ 三读法并排、"
                        "**不擅自判定**；🔴 **不许拿我方的『作用 / 判据』那类顶上** —— "
                        "它们是我方按另一段话写的，不是这个词给的；"
                        "⚠️ 若读法②成立，**源表列契约要追加一列** —— 但追加**只能由主人逐字给**"
                        "（本刀已把冻结点从「字面三列」改成「基列锁死 + 末尾可追加、"
                        "追加必须带出处」）；🔺 行为证据：无 —— **仍在等主人一句话**；"
                        "🔺 **R-H347**：它**第二次出现**（R-H335 / R-H347）—— "
                        "仍**两读法并排、不擅自判定**；"
                        "🔺 **R-H354 第三次出现**（R-H335 / R-H347 / R-H354）—— "
                        "三次都给同一个词 ⇒ **仍是读数、不是许可**；"
                        "🔺 **R-H364 第四次出现**（R-H335 / R-H347 / R-H354 / R-H364）—— "
                        "**四次都给同一个词** ⇒ 仍**不新立条目、不落表、不自解**；"
                        "🔺 **R-H370 第五次出现**（R-H335 / R-H347 / R-H354 / R-H364 / R-H370）"
                        "—— **五次都给同一个词** ⇒ 仍**不新立、不落表、不自解**；"
                        "📌 读数：它现在**只差一种处理**（主人给值 / 主人撤回）—— "
                        "**我这边没有任何「再等下去会自己好」的路径**；"
                        "📌 读数：反复投喂**不等于**授权，但说明它**卡在我们之间**了"
                        "（处理办法只有两种：**主人一句话**，或**主人撤回**）；"
                        "🔴 **再给一次也不等于可以落表**（重复 ≠ 许可）；"
                        "🔺 **仍在等主人一句话**"),
     "resolved": None},
    {"token": "与 GBT 的对接",
     "readings": ("① **源仓库每个工具**『详细介绍』里的**一个小节名**（讲这个工具怎么接我方的）",
                  "② **某个分类的『对应 GBT 能力域』格**的值（意思相近：对接 = 落到哪个能力域）",
                  "③ **第一节表**（表头「维度」）里的一个字段名"),
     "ours_says": None,
     "pending_reason": ("主人给的是**一个短语、没说挂哪儿** ⇒ 三读法并排、**不擅自判定**；"
                        "🔴 **不许拿我方的 `KEY_TOOLS[].owner_use`**（那六条「直接对接…」）顶上 —— "
                        "它们是我方按另一段话登记的，不是这个短语给的；"
                        "🔺 **R-H337 行为证据 +1**：它紧跟在**工具名『Trae』**之后、"
                        "与那句**详细介绍**相邻出现 ⇒ 支持读法①"
                        "（源仓库**每个工具**『详细介绍』里的**一个小节名**）；"
                        "🔴 但**仍不自解、仍不落表** —— 证据再强也不自解 ⇒ **仍在等主人一句话**；"
                        "🔺 **R-H348**：它**第二次出现**（R-H336 / R-H348）—— "
                        "仍**三读法并排、不擅自判定**；"
                        "🔴 **再给一次也不等于可以落表**（重复 ≠ 许可）；"
                        "🔺 **R-H350 行为证据 +1（支持读法①）**：主人给了它的**内容**"
                        "（见 staged_value）⇒ 「**小节名 + 内容成对**」出现 ⇒ "
                        "它更像**源仓库里每个工具的那个小节名**；"
                        "⚠️ 并与**我方 R-H285 存的 `owner_use`**"
                        "（『直接对接自动切换引擎（供应商路由 + 一键切换）』）"
                        "**同前缀、不同尾** ⇒ **跨源同向**；两处**并排记、不许当同一个**"
                        "（前缀一致 ≠ 同一个）；"
                        "⚠️ 「它就是模型路由的 UI 层」与本行『对应 GBT 能力域』**语义呼应**，"
                        "但**不是**那一格的值 ⇒ **不硬凑**；"
                        "🔺 **R-H355 第三次出现**（R-H336 / R-H348 / R-H355）—— "
                        "仍是**三读法并排、不擅自判定**；**不新立条目、不落表**；"
                        "🔺 **R-H365 第四次出现**（R-H336 / R-H348 / R-H355 / R-H365）—— "
                        "**四次都给同一个短语** ⇒ 仍**不新立条目、不落表、不自解**；"
                        "🔺 **R-H371 第五次出现**（R-H336 / R-H348 / R-H355 / R-H365 / R-H371）"
                        "—— **五次都给同一个短语** ⇒ 仍**不新立、不落表、不自解**；"
                        "📌 读数：它与『特点』并列为**被反复投喂的两条**，"
                        "**五次一致 ≠ 可以落表**（见 `awaiting` 一页读数）；"
                        "📌 读数：它与『特点』并列为**被反复投喂的两条**"
                        "（见闸的 `repeated_but_unresolved`）⇒ 处理办法只有**主人一句话**"
                        "（或**主人撤回**）；"
                        "🔺 **R-H352 跨源呼应第三处**：主人新给的那段里，"
                        "『供应商路由 + 一键切换』与我方 `owner_use` **括号里的那半段逐字一致** ⇒ "
                        "两处**并排记、不合并**（同前缀那处见 R-H350，本处是**中段逐字一致**）；"
                        "🔺 **仍在等主人一句话**"),
     "staged_value": "直接对接自动切换引擎——它就是模型路由的 UI 层",
     "staged_note": ("⏸ **暂存、不落表**：这段是那个小节的**内容**；"
                     "小节挂哪儿**没定** ⇒ 一个字都不落进任何表"
                     "（它**不是**『对应 GBT 能力域』的值）；等主人一句话再落"),
     "resolved": None},
    {"token": "智谱华章，AI 代码生成与补全",
     "readings": ("① **『CodeGeeX』的详细介绍**（它紧跟在『CodeGeeX』之后给出，"
                  "形态与前两次一致；且『智谱华章』与 CodeGeeX 的出品方同源）",
                  "② **别的工具（或一个新工具）的介绍** —— 主人**没点名是哪个工具**"),
     "ours_says": None,
     "pending_reason": ("主人给的是一句**介绍**、**没点名是谁的** ⇒ 两读法并排、"
                        "**不擅自判定**；"
                        "🔴 **不许挂到 CodeGeeX 上就当定了**（**形态像 ≠ 就是**）；"
                        "🔴 也**不许把它当作『对应 GBT 能力域』**（那是另一格）；"
                        "🔺 行为证据：形态 **+1**（前两次都是「工具名 → 它的介绍」）—— "
                        "**仍在等主人一句话**；"
                        "⚠️ **R-H349 并排记（两种处理并存）**：同族的 Trae / Fitten Code / "
                        "CC Switch **三句当时挂在条目上**（推断归属 + 暂存），"
                        "本句与下一句**留在待归属** ⇒ **如实并排、不迁移、不合并**；"
                        "🔺 统一口径**等主人一句话**"),
     "staged_value": "智谱华章，AI 代码生成与补全",
     "staged_note": ("⏸ **暂存、不落表**：这句一个字都不落进任何表；"
                     "归属没定 ⇒ **不许挂上任何一行**；等主人一句话再落"),
     "resolved": None},
    {"token": "阿里，代码智能生成 + 研发智能问答 + 任务自主执行",
     "readings": ("① **『通义灵码』的详细介绍**（它紧跟在『通义灵码』之后给出，"
                  "与上一句**同形态**；且『阿里』与通义灵码的出品方同源）",
                  "② **别的工具（或一个新工具）的介绍** —— 主人**没点名是哪个工具**"),
     "ours_says": None,
     "pending_reason": ("主人给的是一句**介绍**、**没点名是谁的** ⇒ 两读法并排、"
                        "**不擅自判定**；"
                        "🔴 **不许挂到通义灵码上就当定了**（**形态像 ≠ 就是**）；"
                        "🔴 也**不许把它当作『对应 GBT 能力域』**（那是另一格）；"
                        "🔺 行为证据：形态 **+1**（这已是**第二句**「工具名 → 它的介绍」）—— "
                        "**仍在等主人一句话**；"
                        "⚠️ **R-H349 并排记（两种处理并存）**：同族的 Trae / Fitten Code / "
                        "CC Switch **三句挂在条目上**，本句与上一句**留在待归属** ⇒ "
                        "**如实并排、不迁移、不合并**；🔺 统一口径**等主人一句话**"),
     "staged_value": "阿里，代码智能生成 + 研发智能问答 + 任务自主执行",
     "staged_note": ("⏸ **暂存、不落表**：这句一个字都不落进任何表；"
                     "归属没定 ⇒ **不许挂上任何一行**；等主人一句话再落"),
     "resolved": None},
    {"token": "编程 Agent 能力",
     "readings": ("① **『GitHub Copilot』的能力描述**（与工具名在**同一条消息**里给出）",
                  "② **某个分类的『对应 GBT 能力域』格**的值（「能力」二字像那一格）",
                  "③ **源仓库某处的一个小节名 / 字段名**（是一个短语、不是一句话）"),
     "ours_says": None,
     "pending_reason": ("主人给的是**一个短语**、**没说挂哪儿** ⇒ 三读法并排、"
                        "**不擅自判定**；"
                        "⚠️ **本句与那两句介绍的位置相反**：那两句在**工具名之后**、"
                        "本句在**工具名之前** ⇒ **形态不完全同** ⇒ "
                        "**不记「证据 +1」**（如实写明，不许把两件事凑成一件事）；"
                        "🔴 也**不许把它当作『对应 GBT 能力域』**（那是另一格）；"
                        "🔺 **仍在等主人一句话**"),
     "staged_value": "编程 Agent 能力",
     "staged_note": ("⏸ **暂存、不落表**：这个短语一个字都不落进任何表；"
                     "归属没定 ⇒ **不许挂上任何一行**；等主人一句话再落"),
     "resolved": None},
    {"token": "老牌 AI 编码助手",
     "readings": ("① **『GitHub Copilot』的简介 / 能力描述**（紧跟其后给出）",
                  "② **某个分类的『对应 GBT 能力域』格**的值（是短语、像在描述一类工具）",
                  "③ **源仓库某处的一个小节名 / 标签**（不是一句话，是个短标签）"),
     "ours_says": None,
     "pending_reason": ("主人给的是**一个短名词短语**、**没说挂哪儿** ⇒ 三读法并排、"
                        "**不擅自判定**；"
                        "⚠️ **位置在工具名之后**（与那几句介绍同），但**句型不同** —— "
                        "那几句是「公司开头 + 逗号」的句子，本句是**短短语** ⇒ "
                        "**不记「证据 +1」**（**不许只看位置一项就凑数**）；"
                        "🔴 也**不许把它当作『对应 GBT 能力域』**（那是另一格）；"
                        "🔺 **仍在等主人一句话**"),
     "staged_value": "老牌 AI 编码助手",
     "staged_note": ("⏸ **暂存、不落表**：这个短语一个字都不落进任何表；"
                     "归属没定 ⇒ **不许挂上任何一行**；等主人一句话再落"),
     "resolved": None},
    {"token": "自动切换引擎的 CLI 入口",
     "readings": ("① **一个「小节名」**（源仓库每个工具条目里的小节标题那一类）",
                  "② **某个分类的『对应 GBT 能力域』格**的值（「CLI 入口」像在指能力）",
                  "③ **对某个工具的一句描述**（与那几句介绍同族、但更短）"),
     "ours_says": None,
     "pending_reason": ("主人给的是**一个短语**、**没说挂哪儿** ⇒ 三读法并排、"
                        "**不擅自判定**；"
                        "🔴 也**不许把它当作『对应 GBT 能力域』**（那是另一格）；"
                        "⚠️ 与它**同批来的那段正文**（见 staged_value）"
                        "**形态像「小节名 + 内容」成对** ⇒ 两件**并排记、不合并**；"
                        "🔺 **仍在等主人一句话**"),
     "staged_value": PARA_R_H352,
     "staged_note": ("⏸ **暂存、不落表**：这段是一个小节的**内容**；"
                     "小节挂哪儿**没定** ⇒ 一个字都不落进任何表"
                     "（它**不是**『对应 GBT 能力域』的值）；等主人一句话再落"),
     "resolved": None},
    {"token": "FastMovieAI",
     "readings": ("① **一个新工具的「工具名」**（若源仓库是「一工具一行」，它可能是新的一行）",
                  "② **某个分类『代表工具』格的追加项**（例如第 4 行再加一个代表工具）",
                  "③ **与 R-H285 那批某个能力位对应**的名字（若它是一条能力位）"),
     "ours_says": None,
     "pending_reason": ("主人**只给了一个名字、没说挂哪儿** ⇒ 三读法并排、"
                        "**不擅自判定**；"
                        "🔺 **取证（本刀现场）：全盘 0 命中**"
                        "（模块 / 文档 / 分类名 / 格值 / 源表列 / 第二节列 / "
                        "待归位碎片 / 再现名字 —— 都查过）⇒ 它是**新面孔**"
                        "（**盘上首次出现**）；"
                        "🔴 **不许**因为「像视频类工具」就塞进第 4 行"
                        "（**看着像 ≠ 就是**）；🔴 也**不许**因此新立一行分类；"
                        "🔺 **R-H358**：主人又给了它的**一句介绍**（见 staged_value）⇒ "
                        "与那五条同族（**工具名 / 名字 → 紧接着一句介绍**）；"
                        "🔺 **仍在等主人一句话**"),
     "staged_value": "功能完整的开源短剧/短视频创作平台，前后端分离，集成用户管理、支付、内容管理、视频生成",
     "staged_note": ("⏸ **暂存、不落表**：**归属依据** = **形态**"
                     "（**紧跟其后** + 平台类语义吻合）—— "
                     "⚠️ 但主人**没点名** ⇒ 这只是**推断**，不是判定；"
                     "🔸 **第二种读法并排**：也可能是**另一个项目 / 新工具**的介绍，"
                     "或**第 4 行那个分类的能力描述**；"
                     "**一个字都不落进任何表**（它**不是**『对应 GBT 能力域』的值）；"
                     "🔺 **等主人一句话**再落"),
     "resolved": None},
)
PENDING_ATTRIBUTION_NOTE = ("**待归属区**：主人给了一个词、没说挂哪儿 ⇒ "
                            "至少写出**两种读法**、写明理由、**不许自己替它定归属**")


# 🆕 R-H354：从理由里抽「第N次出现」的**最大 N**（派生读数用；不手写）
_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_REPEAT_RE = re.compile(r"第([一二三四五六七八九十]+)次出现")


def _max_repeat(text: str) -> int:
    """理由里「第N次出现」的最大 N（没有就 0）。"""
    best = 0
    for m in _REPEAT_RE.finditer(str(text or "")):
        best = max(best, _CN_NUM.get(m.group(1), 0))
    return best


def _known_names() -> set:
    """盘上**已经出现过**的名字集合（R-H357 立）：分类名 / 格值分段 / 源表列 / 第二节列 /
    待归位碎片 / 再现名字 —— 用来自动算出「哪些待归属项是**新面孔**」。

    ⚠️ **自维护**：名字一旦真落进某个数据面，它就自动从 `newcomers` 里消失（不需要人工维护）。
    """
    known = set()
    for r0 in CATEGORY_ROWS_OWNER:
        known.add(str(r0.get("category") or "").strip())
        for v0 in dict(r0.get("cells") or {}).values():
            for seg in str(v0 or "").split("/"):
                seg = seg.strip()
                if seg:
                    known.add(seg)
    for c0 in tuple(SOURCE_TABLE_COLUMNS) + tuple(SECTION2_COLUMNS):
        known.add(str(c0).strip())
    for f0 in OWNER_FRAGMENTS:
        known.add(str(f0).strip())
    for t0 in REAPPEARING_TOKENS:
        known.add(str(t0.get("token") or "").strip())
    # 🔧 R-H359 补缺口：**我方 R-H285 那批（KEY_TOOLS）也是「盘上已有」** ——
    #    原来没算进去 ⇒ 会把『Huobao Drama』这种**已知名字**误判成「新面孔」
    for k0 in KEY_TOOLS:
        known.add(str(k0.get("name") or "").strip())
    known.discard("")
    return known


def check_pending_attribution() -> dict:
    """闸⑭（R-H294）：**待归属区**四条 —— 读法要两条以上 · 理由要写 · 不许自解归属 · 空样本不按绿。

    为什么单立：主人已经好几次给「一个词/一个行名」而不说挂哪儿（行名、字段名、列名）。
    若每次都靠我临场判断，迟早有一次会把它挂错地方 —— 挂错了比留空更难发现。
    """
    items = list(PENDING_ATTRIBUTION)
    if not items:
        return {"ok": False, "denied": True, "rule": "pending_all_resolved_or_empty",
                "why": "一条待归属都没有：要么全解了（那就该清空），要么根本没登记 ⇒ **空样本不按绿**"}
    out = []
    for it in items:
        token = str(it.get("token") or "").strip()
        readings = tuple(str(x) for x in (it.get("readings") or ()))
        reason = str(it.get("pending_reason") or "").strip()
        resolved = it.get("resolved")
        if not token:
            return {"ok": False, "denied": True, "rule": "pending_token_missing",
                    "why": "待归属项必须写明**是哪个词**"}
        if len(readings) < 2:
            return {"ok": False, "denied": True, "rule": "pending_readings_missing",
                    "token": token, "readings": list(readings),
                    "why": "至少写出**两种读法**（只写一种 = 已经替主人定了）"}
        if not reason:
            return {"ok": False, "denied": True, "rule": "pending_reason_missing",
                    "token": token,
                    "why": "待归属必须写明理由（§57：有理由的空 ≠ 未处理的残留）"}
        if resolved is not None:
            return {"ok": False, "denied": True, "rule": "pending_self_resolved",
                    "token": token, "resolved": resolved,
                    "why": "**不许自己替它定归属** —— 归属只能由主人一句话定"}
        act_ev = str(it.get("action_evidence") or "").strip()
        # 🆕 R-H305：暂存值（主人给了清单但归属没定）必须写明「暂存、不落表」
        staged = str(it.get("staged_value") or "").strip()
        staged_note = str(it.get("staged_note") or "").strip()
        if staged and ("暂存" not in staged_note or "不落" not in staged_note):
            return {"ok": False, "denied": True, "rule": "staged_without_hold_note",
                    "token": token, "staged_value": staged,
                    "why": "**暂存的清单必须写明「暂存、不落表」** —— "
                           "否则暂存会悄悄变成已落（归属还没人定呢）"}
        # 🆕 R-H358：**暂存值必须写明「这是谁的 / 不知道是谁」**（与再现侧的 `staged_detail_without_owner_basis` **对称**）
        #    认这几种写法之一：归属依据 / 未点名 / 不明 / 没定 ——
        #    ⚠️ 不收「任何含字」的宽松写法（那是判据扩大化），也不许**不写**（那是沉默）
        if staged and not any(k in staged_note for k in
                               ("归属依据", "未点名", "不明", "没定")):
            return {"ok": False, "denied": True,
                    "rule": "staged_value_owner_unstated", "token": token,
                    "why": "暂存值必须写明**这是谁的**（归属依据）或**不知道是谁**"
                           "（未点名 / 不明 / 没定）—— 不许沉默"}
        # 🆕 R-H341：暂存值**不许落进任何数据面** ——
        #    「暂存、不落表」原来只有**写字**那条牙（写没写那两句）；
        #    但**写对了字、照样落表**是可能的 ⇒ 补一条**机械**牙。
        if staged:
            surfaces = []
            # 🔧 R-H348：面名**带行号**（与再现闸统一口径 —— 两处不许各说各话）
            for i2, r2 in enumerate(CATEGORY_ROWS_OWNER, 1):
                surfaces.append(("分类名", str(r2.get("category") or "")))
                for k2, v2 in dict(r2.get("cells") or {}).items():
                    surfaces.append(("第%d行 格 %s" % (i2, k2), str(v2 or "")))
            for c2 in SOURCE_TABLE_COLUMNS:
                surfaces.append(("源表列名", str(c2)))
            for c2 in SECTION2_COLUMNS:
                surfaces.append(("第二节列名", str(c2)))
            landed = [name for name, val in surfaces if staged in val]
            if landed:
                return {"ok": False, "denied": True,
                        "rule": "pending_staged_value_landed",
                        "token": token, "where": landed,
                        "why": "待归属的**暂存值落进了表** ⇒ 归属没定就一个字都不许落"
                               "（**暂存 ≠ 已落**：写了「暂存」两个字也要机械核过）"}
        # 🆕 R-H347：**第二次出现 ≠ 许可** —— 「再给一次」最容易被顺手当成「可以落了」
        #    ⇒ 写了「第二次出现」，就必须同时写「仍在等一句话」与「不擅自」
        #    🔧 R-H348 放宽（**判据别扩大化**）：「**不擅自**判定」与「**不自解**」是
        #    **同族两种写法**，都该算 —— 只认一种会把另一种误伤
        if "第二次出现" in reason and (
                "等主人一句话" not in reason
                or not ("不擅自" in reason or "不自解" in reason)):
            return {"ok": False, "denied": True,
                    "rule": "pending_repeat_not_license", "token": token,
                    "why": "写了「第二次出现」，却没写「仍在等主人一句话 / 不擅自」⇒ "
                           "**再给一次也不等于可以落表**（**重复 ≠ 许可**）"}
        # 判据别扩大化：这两种写法都是「还在等」，都算
        if act_ev and ("待主人一句话" not in reason and "等主人一句话" not in reason):
            return {"ok": False, "denied": True,
                    "rule": "pending_evidence_without_wait",
                    "token": token,
                    "why": "**证据到位也不许自解**：行为证据只把可能性推高，"
                           "理由里必须写明「仍在等主人一句话」"}
        out.append({"token": token, "readings": list(readings),
                    "action_evidence": act_ev or None,
                    "staged_value": staged or None,
                    "staged_note": staged_note or None,
                    "pending_reason": reason, "resolved": None})
    return {"ok": True, "readonly": True, "items": out, "count": len(out),
            # 🆕 R-H343：**派生读数** —— 哪几条带暂存值（让「有几条在暂存」看得见，不手写）
            "staged_items": [x["token"] for x in out if x.get("staged_value")],
            # 🆕 R-H354：**派生读数** —— 谁被重复投喂、最多几次（正则**现算**，不手写）
            "repeat_topics": {x["token"]: _max_repeat(x["pending_reason"])
                              for x in out
                              if _max_repeat(x["pending_reason"]) >= 2},
            # 🆕 R-H364：**反复投喂、但仍未自解**的待归属项（派生 · 现算不手写）——
            #    把「积压在哪」变成数字：这些**不是我做不动**，是**等主人拍板**
            "repeated_but_unresolved": sorted(
                x["token"] for x in out
                if _max_repeat(x["pending_reason"]) >= 2 and x.get("resolved") is None),
            # 🆕 R-H357：**新面孔**（自维护派生读数）：不在任何数据面里的待归属项 ——
            #    「哪些名字是**盘上首次出现**」一眼可见；名字一旦真落进数据面，自动消失
            "newcomers": [x["token"] for x in out
                          if str(x["token"]).strip() not in _known_names()],
            "note": PENDING_ATTRIBUTION_NOTE}

# 🔴 R-H295：第二节（表头「分类」）的**列名**开始到货 ⇒ 先立列契约，再落分类行
SECTION2_COLUMNS = ("代表工具", "对应 GBT 能力域")
SECTION2_COLUMNS_NOTE = ("列契约（两个列名都是主人给的）：代表工具（R-H294）· "
                         "对应 GBT 能力域（R-H295）—— 将来每个分类按这些列落")
# 🔴 R-H373：本仓第二节里**名字列**只有『代表工具』；
#    『对应 GBT 能力域』是**描述**列（它的斜杠是并列项，但**不是**并列工具名）
#    ⇒ 任何「按名字切分」的读数都只该看**名字列**（否则就是判据扩大化）
NAME_COLUMNS = ("代表工具",)

# 🔴 R-H379：**介绍相对「它那个名字」在主人消息里的位置**（两种合法形态）——
#    `after_name`        主人**先说名字、后给介绍**（此前所有条目都是这种）
#    `before_next_name`  主人**先给介绍、后给另一个名字**（介绍在**名字之前**）
#    ⚠️ 本刀的现场：介绍紧接在**下一个名字之前**，却属于**上一个**名字 ⇒
#    「紧跟其后」**不再是唯一形态**；位置只是**证据**，语义才是判据。
#    🔴 R-H380 **口径定死**：`detail_position` 一律相对**它挂的那个名字（owner）**而言 ——
#    第一版（R-H379）我用了 `before_next_name`，那说的是「相对**紧随其后的名字**」，
#    **混了两个框架**（与 owner 的关系 vs 与下一个名字的关系）⇒ 本刀**拆成两件事**：
#      · `detail_position`（**相对 owner**）：after_name / before_owner_name
#      · 读数 `detail_next_name_side`（**相对紧随其后的名字**）：before_next_name / none
DETAIL_POSITIONS = ("after_name", "before_owner_name")
#    🔴 R-H379 同刀自查（**同一族第 3 次**）：第一版我用「紧跟其后 / 在名字之前」这种
#    **自然语言短语**做标记 ⇒ 被**否定句**喂响（Watt 那条写着「不是紧跟其后」，
#    牙却当成「说了紧跟其后」⇒ 该红不红）。
#    ⇒ 改成**结构化标记**（能结构化的就结构化 —— 与 R-H376 同族）：
#    正文必须照抄 `位置读数：<说法>` 这一整串；否定句**抄不出这个标记**。
DETAIL_POSITION_WORDS = {"after_name": ("位置读数：跟在名字之后",),
                         "before_owner_name": ("位置读数：在名字之前",)}
# 🔴 R-H380：**与紧随其后的那个名字**的关系（读数 · 不是位置判据）——
#    它正是 R-H379 把我带偏的那个框架 ⇒ **显式记下来**，而不是丢掉。
DETAIL_NEXT_NAME_SIDES = ("before_next_name", "none")

# 🔴 R-H375：**我方真身表**（固定词表）—— 主人若在介绍里**点名**它们，
#    那个真身必须**真的在盘上**（否则就是拿一个盘上不存在的东西当呼应证据）。
#    ⚠️ 词表**只收已落地的东西**；没进词表的名字**不进这个判据**（判据别扩大化）。
_REPO = Path(__file__).resolve().parents[2]
LOCAL_ASSETS = (("context_vault", "gbt_allinone/tools/context_vault.py"),)
LOCAL_ASSETS_NOTE = (
    "**我方真身表**：名字 → **相对本仓的真实路径**；"
    "🔴 判据 `local_ref_unverified`：介绍里点名了 ⇒ 该真身必须**在盘上且非空**；"
    "⚠️ 它与再现侧的「说『已在』就必须真在盘上」**对称** —— 两侧都不许空口指认。"
)


def _asset_ok(rel: str) -> bool:
    """真身在盘上且非空 ⇒ True（只读检查：不写盘、不出网）。"""
    try:
        p = _REPO / rel
        return p.is_file() and p.stat().st_size > 0
    except OSError:
        return False


def _local_refs(text) -> list:
    """介绍里点名了哪些**我方真身**（只认 `LOCAL_ASSETS` 词表）。"""
    s = str(text or "")
    return [name for name, _rel in LOCAL_ASSETS if name in s]

# 🔴 R-H334：主人给了**源仓库**里「每个分类下那张表」的表结构 ⇒ 先立**源表列契约**
#    主人逐字：核心结构 = 每个分类下是一张表格，包含 工具名 | 详细介绍 | 下载地址
#    ⚠️ 顺序即主人给的顺序 ⇒ 判据挂在**冻结点**（SOURCE_TABLE_COLUMNS_OWNER）上，不挂可变的那份
SOURCE_TABLE_COLUMNS_OWNER = ("工具名", "详细介绍", "下载地址")
# ⚠️ R-H335：冻结点**不许挡住主人给的新数据** —— 它只该挡住「我臆造 / 我重排」。
#    所以拆成两段：**基列**（主人逐字给过，顺序固定、不许重排/删/改）
#    + **末尾追加**（也必须主人逐字给，且**每条都要写出处**）。
SOURCE_TABLE_COLUMNS_APPENDS = ()   # 追加项：[{"name": "…", "source": "主人提供 · R-? · 逐字"}]
SOURCE_TABLE_COLUMNS = SOURCE_TABLE_COLUMNS_OWNER + tuple(
    a["name"] for a in SOURCE_TABLE_COLUMNS_APPENDS)
SOURCE_TABLE_COLUMNS_NOTE = (
    "**源表列契约**（主人 R-H334 逐字）： Awesome Tools **每个分类下就是一张表**，列按此顺序 —— "
    "⚠️ 它与本仓第二节的列契约（代表工具 / 对应 GBT 能力域）是**两张不同的表**："
    "位置像（都是「分类下的列」）、内容不同（3 列 vs 2 列，列名一个都不重合）⇒ "
    "**并排记、不许当同一个**（「像但不等于」族第八次现场）；"
    "🔴 源表的三列**不许直接拿来当本仓第二节的列**，本仓的列只认主人给过的列名；"
    "🔧 R-H335 改判据：**基列锁死**（不许重排/删/改）+ **末尾可追加**，"
    "但追加**必须也是主人逐字给的、且每条写出处**（冻结点不该挡住主人给的新数据）。"
)

# 🔴 R-H384：主人给的**融合设计（第四节）**—— 7 条「工具/分类 → GBT 能力位」映射，**逐字**。
#    先取证：这一段在盘上**0 命中**（『编程工作区的备选引擎』『记忆层的备选方案』
#    『环境优化工具』『自动切换引擎的 UI 层』全都没有）⇒ **不是文档回流**，是一条**新事据**；
#    ⚠️ 至于是不是源仓库的文档，**未取证**（没出网 ⇒ 不许说「源仓库原文如此」）。
#    🔴 纪律：每条都必须写**与盘上对照**（不许裸登记）；🔴 **一条都不许落进任何表**。
FUSION_ROWS = (
    {"no": 1, "left": "AI辅助编程工具", "right": "编程工作区的备选引擎",
     "left_from": "分类表第1行", "right_from": "旧批分类名",
     "crosscheck": "左边**逐字**等于本仓**第 1 行**的分类名；右边含**旧批分类名**"
                   "『编程工作区』（CATEGORIES_OWNER）⇒ **跨批对应**"
                   "（与 R-H334 那条「两批疑似对应」**同向**，仍**不自解谁作准**）"},
    {"no": 2, "left": "CC Switch", "right": "自动切换引擎的 UI 层",
     "left_from": "再现区:CC Switch", "right_from": "KEY_TOOLS:CC Switch",
     "crosscheck": "左边**逐字**等于再现区条目名；右边与我方 `owner_use`"
                   "『直接对接自动切换引擎（供应商路由 + 一键切换）』**前缀/同向**"
                   "（共享『自动切换引擎』）—— ⚠️ **不是逐字**，如实记"},
    {"no": 3, "left": "AI短剧生成工具", "right": "视频创作流水线的能力位",
     "left_from": "分类表第4行", "right_from": "KEY_TOOLS:MoneyPrinterTurbo",
     "crosscheck": "左边**逐字**等于本仓**第 4 行**的分类名；右边与我方 `owner_use`"
                   "『视频创作流水线能力位』**一字之差**（多一个『的』）⇒ **近似**、不许当同一个"},
    {"no": 4, "left": "CowAgent", "right": "多平台接入能力",
     "left_from": "再现区:CowAgent", "right_from": "KEY_TOOLS:CowAgent",
     "crosscheck": "左边**逐字**等于再现区条目名；右边是我方 `owner_use`"
                   "『多平台接入能力（微信 / 飞书 / 钉钉 / QQ）』的**前缀（逐字）**⇒ **前缀一致**"},
    {"no": 5, "left": "OpenClaw Monitor", "right": "上帝视角的监控组件",
     "left_from": "再现区:OpenClaw Monitor", "right_from": "KEY_TOOLS:OpenClaw Monitor",
     "crosscheck": "左边**逐字**等于再现区条目名；右边与我方 `owner_use`『上帝视角的监控组件』"
                   "**逐字一致**（R-H285 那批的原话）⇒ **逐字**"},
    {"no": 6, "left": "文档工具", "right": "记忆层的备选方案",
     "left_from": "旧批分类名", "right_from": "分类表第6行",
     "crosscheck": "左边**逐字**是**旧批分类名**（CATEGORIES_OWNER）；右边含『记忆层』"
                   "—— 它正是本仓**第 6 行**『对应 GBT 能力域（记忆层 / 知识库）』里的词"
                   "⇒ **跨源呼应**（并排记，**不硬配**）"},
    {"no": 7, "left": "网络加速工具", "right": "环境优化工具",
     "left_from": "顺序读数:网络加速工具", "right_from": "顺序读数:网络加速工具",
     "crosscheck": "左边**逐字**等于**顺序读数第五条**（源 6）的分类名；"
                   "右边含『环境优化』—— 它正是那条读数的**括号词**（`paren`）"
                   "⇒ 🔺 **跨刀呼应**：R-H377 记的「括号词不是旧批名」在本刀**有了落点**"
                   "（它是这条映射的**目标词**）—— 仍**并排记、不硬配**"},
)
FUSION_ROWS_NOTE = (
    "**融合设计区（R-H384 · 主人逐字）**：第四节『与 GBT小土豆V8 的融合设计』的 4.1 映射表，7 条；"
    "**7 条**；每条都带**与盘上对照**（逐字 / 前缀 / 一字之差 / 旧批名 / 跨源呼应）；"
    "🔴 **一条都不许落进任何表**（它是**设计稿**，不是表数据）；"
    "🔴 对照**不许沉默**：写了「同向/近似」的，必须**说清是哪种**。"
)
FUSION_KINDS = ("逐字", "前缀", "一字之差", "对应", "呼应")
# 🔴 R-H384 同刀修正：**每个边一个 kind**（结构化）—— 第一版拿散文里的「逐字」二字判，
#    被第 2 条那句「⚠️ **不是**逐字」**喂响**（否定句）⇒ 散文只给人看，机器只读字段。
#    「对应 / 呼应」是**关系**，不做字符串校验（如实写在 why 里，不许假装校过）。
# 🔴 R-H385：主人给的**4.2 原语**（『蒸馏为技能：awesome_tools_index』下面的那条）——
#    ⚠️ 『原语』那个**碎片**（R-H384）**不是**数据；`INDEX` 才是 ⇒ **碎片不许当原语**。
#    INDEX **已在**盘上：本仓 `PRIMITIVES` 的**第 1 条**（逐字）⇒ 顺位读数 = **一致**。
# 🔴 R-H389：主人给的**设计稿小节**（4.1 / 4.2 是 R-H384 给的，4.3 是本刀给的）——
#    小节标题**逐字**登记；🔴 牙：编号必须**递增且不重** · 一条都不许落表。
# 🔴 R-H390：4.3『三条带牙用例』的**内容**逐条登记（上一刀只给了标题）——
#    每条都要写**与盘上对照**的出处标签（不许裸登记、不许编）；🔴 一条都不许落表。
# 🔴 R-H391：把「**带牙**」做成机械 —— 用例可以声明**管着它的牙名**（teeth），
#    牙名必须真的在本模块里（现扫源码里所有 `"rule": "..."` 得到 KNOWN_RULES）。
#    现扫 ⇒ 不给「手写牙名」留空子。
# 🔴 R-H393：**未到齐的输入**专区 —— 主人给的东西**没说完**时，只登记
#    「它到了 / 到哪儿 / 盘上取证读数」，**内容一个字不编**（截断 ≠ 数据）。
INCOMING_DISTILLS = (
    {"topic": "TeamoRouter（三层工程哲学）", "at": "R-H393",
     # 🔴 R-H396：**主人逐字**单独成字段 —— 重合只在这上面算（`got` 里还混着我写的状态标注）
     "row1": ("L1", "路由策略层", "按用户声明的优先级选择路由方向"),
     # 🆕 R-H407：**通用行登记**（每行逐格）—— L1 行已满、L2 行只到第一格
     "rows": (("L1", "路由策略层", "按用户声明的优先级选择路由方向"), ("L2", "智能匹配层", "模型映射 + 通道粘性 + 缓存热度感知"), ("L3", "健康检测层", "智能心跳 + 稀释率检测 + 丢包率监控"), ("L4", "故障切换层", "电路断路器 + 灰度降级"), ("L5", "兜底层", "最终兜底方案")),
     # 🔺 R-H411 对照读数：本刀这格与「五层名序列」里的『健康检测层』**逐字一致**
     #    （L2 那格则是「智能匹配层 ↔ 匹配层」**一字之差**）⇒ **两种关系并排记、都不硬配**
     "name_relations": (("L3 · 健康检测层", "逐字一致（与五层名序列）"),
     ("L4 · 故障切换层", "逐字一致（与五层名序列）"),
                        ("L2 · 智能匹配层", "一字之差（与五层名序列的『匹配层』）")),
     # 🔺 R-H410：**说明 ≠ 改写** —— 「STICKY（粘性）」是对『通道粘性』的**英文标注**，
     #    我不把它**填进**那一格（那会改主人原话），只在旁边**并排记**（见 verbatim）。
     # 🔴 R-H420：**形态待定** —— 到货了，但**挂不上结构**（两种读法并排、都不硬判）
     # 🔸 R-H434：3.4 矩阵的第一行（**推断形态**：位置 + 内容形态 ⇒ 不是判定）
     "matrix_rows": (("代码补全 / 单行生成",),),
     # 🔧 R-H431：**框图那五层**（层号 / 名称 / 职责 —— 每格必须在 verbatim 里）
     "frame_layers": (("L1", "策略层", "用户声明 gbt-best / gbt-balanced / gbt-eco"),
                      ("L2", "匹配层", "模型映射 + 会话粘性 + 本地缓存热度感知"),
                      ("L3", "健康层", "本地模型健康 + 能源池可用性 + 显存监控"),
                      ("L4", "切换层", "本地模型不可用 → 能源池兜底 → 降级上报"),
                      ("L5", "兜底层", "全部不可用 → 返回 needs_external_key")),
     "shape_pending": (("对应优先级", "读法①：3.2 那张表的**第二个列名**（与『预设』同族）",      "读法②：3.2 那张表**第一行的格**（那我连它属于哪列都还不知道）"),
                     # 🔺 R-H421：**同族第二个**（仍挂不上结构 ⇒ 仍不硬判）
                     ("本地行为", "读法①：3.2 那张表的**第三个列名**（与『预设』『对应优先级』同族）",      "读法②：3.2 那张表**第一行的格**"),
                     # 🔺 R-H422：到货第三个 —— 形态待定（两读法）+ ⚠️ 盘上那条是**我自己写的摘要**
                     ("gbt-best", "读法①：3.2 那张表**第一行的格**（『预设』列的值）",      "读法②：与『teamo-*』构成**两套前缀**（R-H397 记过）⇒ 两种读法并排、不硬判"),
                     # 🔺 R-H423：第四条（与 gbt-best 同族 ⇒ 仍不硬判）
                     ("质量优先", "读法①：3.2 那张表**第一行第二格**（『对应优先级』列的值）",      "读法②：与『gbt-best』配对的**说明**（预设名 ↔ 优先级）⇒ 并排、不硬判"),
                     # 🔺 R-H424：第五条 —— 语义明确，但**挂不上结构**（仍不硬判）
                     ("本地模型不够时，上云端最强模型", "读法①：3.2 那张表某行的**格值**",      "读法②：**一条独立的降级原则/说明**（不属那张表）⇒ 并排、不硬判"),
                     # 🔺 R-H425：第六条（与 gbt-best 同族 ⇒ 仍不硬判）
                     ("gbt-balanced", "读法①：3.2 那张表**第二行第一格**（预设列）",      "读法②：与早前那套『gbt-best / gbt-balanced / gbt-eco』**同源**（那套是我自己写的摘要 ⇒ 不是主人的原话事据）⇒ 并排、不硬判"),
                     # 🔺 R-H426：第七条（与质量优先同族 ⇒ 仍不硬判）
                     ("平衡优先", "读法①：3.2 那张表**第二行第二格**（『对应优先级』列的值）",
                      "读法②：与『gbt-balanced』配对的**说明**（预设名 ↔ 优先级）⇒ 并排、不硬判"),
                     # 🔺 R-H427：第八条 —— 与 R-H424 那句**同向**（同主题第二次说法）
                     ("本地模型优先，不够再上云端", "读法①：3.2 那张表某行的**格值**",
                      "读法②：**一条独立的降级原则/说明** ⇒ 与 R-H424 那句**同向但字面不同**"
                      "⇒ 并排记、**不许当同一个**"),
                     # 🔺 R-H428：第九条（与 gbt-best / gbt-balanced 同族 ⇒ 仍不硬判）
                     ("gbt-eco", "读法①：3.2 那张表**第三行第一格**（预设列）",
                      "读法②：与早前那套（**我自己写的摘要**）同源 ⇒ 并排、不硬判"),
                     # 🔺 R-H429：第十条（与质量优先/平衡优先同族）⇒ **三对「像一对」都齐了**
                     ("成本优先", "读法①：3.2 那张表**第三行第二格**（『对应优先级』列的值）",
                      "读法②：与『gbt-eco』配对的**说明** ⇒ 并排、不硬判（**三对都不落位**）"),
                     # 🔴 R-H435：第十二条 —— **弱推断**（单字 · 不落位）
                     ("低", "读法①：3.4 矩阵第一行第二格（『复杂度』列的值）",
                      "读法②：也可能是**截断**（只有 1 个字）或别的表的值 ⇒ 不硬判"),
                     ("本地 Qwen2.5-Coder-7B", "读法①：3.4 矩阵第一行**第三格**（推荐能源列的值）", "读法②：也可能是**本地模型清单**里的一条 ⇒ 但**第二格（复杂度）还没到** ⇒ 落位会错位 ⇒ **缺格不许跳**、不硬判"),
                     # 🔺 R-H437：第十四条 —— 一条**原则**（与「显式声明」同族）仍不硬判
                     ("不管做什么必须注重细节", "读法①：3.1『核心设计原则』那一组的**又一条**",
                      "读法②：也可能是一条**通用嘱咐**（不属那份设计稿）⇒ 并排、不硬判"),
                     # 🔺 R-H438：第十五条 —— 仍不硬判（判不出来就不判）
                     ("工具函数 / 脚本", "读法①：3.4 矩阵**第二行第一格**（『任务类型』列 = 工具函数 / 脚本）",
                      "读法②：也可能是第一行『任务类型』的另一半读法 ⇒ 并排、不硬判"),
                     # 🔺 R-H439：第十六条 —— 仍不硬判（且缺格不许跳）
                     ("低-中", "读法①：3.4 矩阵**第二行第二格**（『复杂度』列）",
                      "读法②：也可能是**第一行第二格**（补 R-H435 那个弱推断『低』）"
                      "⇒ 两读法并排 · 🔴 因**第一格未落位** ⇒ **缺格不许跳** · 与『低』相关但不许当同一个"),
                     # 🔺 R-H440：第十七条 —— 仍不硬判（与 Coder 那条同前缀、不同尾）
                     ("本地 Qwen2.5-7B", "读法①：3.4 矩阵某行**第三格**（『推荐能源』列）",
                      "读法②：**本地模型清单**里的一条 ⇒ 与『本地 Qwen2.5-Coder-7B』"
                      "**同前缀、不同尾**（差一个 Coder）⇒ 并排、🔴 **不许当同一个**"
                       "（🔁 **R-H451**：主人**第二次**给『本地 Qwen2.5-7B』—— 与上面这句**逐字相同**"
                       "⇒ 只**补记次数**、**不新立第二条**、**不落位**（**重复 ≠ 许可**）；"
                       "🔴 同时重申：与『本地 Qwen2.5-Coder-7B』**仍不许当同一个**（同前缀、不同尾））"),
                     # 🔺 R-H441：第十八条 —— 仍不硬判（「任务类型」的候选第三个）
                     ("Bug 定位与修复", "读法①：3.4 矩阵**某行第一格**（『任务类型』列）",
                      "读法②：也可能是**别的表**的任务类型 ⇒ 并排、不硬判"
                      "（『任务类型』的候选已 3 个：代码补全 / 单行生成 · 工具函数 / 脚本 · 本句）"),
                     # 🔺 R-H442：第十九条 —— 仍不硬判（复杂度候选第三个）
                     ("中-高", "读法①：3.4 矩阵某行『复杂度』列的值",
                      "读法②：别处的复杂度档 ⇒ 并排、不硬判"
                      "（『复杂度』的候选已 3 个：低 · 低-中 · 中-高 ⇒ **全在待定格**）"),
                     # 🔺 R-H443：第二十条 —— 仍不硬判（本地模型第三个）
                     ("本地 DeepSeek-R1-7B", "读法①：3.4 矩阵某行**第三格**（『推荐能源』列）",
                      "读法②：**本地模型清单**里的一条 ⇒ 并排、不硬判"
                      "（本地模型名已 3 个：Qwen2.5-Coder-7B · Qwen2.5-7B · 本句 ⇒ **全在待定格**）"),
                     # 🔺 R-H444：第二十一条 —— 仍不硬判（「任务类型」候选第四个）
                     ("系统架构设计", "读法①：3.4 矩阵某行**第一格**（『任务类型』列）",
                      "读法②：也可能是**别的表**的任务类型 ⇒ 并排、不硬判"
                      "（『任务类型』的候选已 4 个 ⇒ **4/3/3 不对称了，照实写**）"),
                     # 🔺 R-H445：第二十二条 —— 仍不硬判（复杂度候选第四个）
                     ("高", "读法①：3.4 矩阵某行『复杂度』列的值",
                      "读法②：别处的复杂度档 ⇒ 并排、不硬判"
                      "（『复杂度』候选已 4 个：低 · 低-中 · 中-高 · 本句 **正好补齐梯子**"
                      "⇒ 现 **4/4/3**）"
                      "（🔁 **R-H448**：主人**第二次**给『高』—— 与上面这句**逐字相同**"
                      "⇒ 只**补记次数**、**不新立第二条待定项**、**不落位**"
                      "（**重复 ≠ 许可**；段内的『4/4/3』是**当时**的读数，本刀**不改写**它）"),
                     # 🔴 R-H446：第二十三条 —— 仍不硬判 · **带条件的候选**（如可用）
                     ("云端 Agnes（如可用）", "读法①：3.4 矩阵某行**第三格**（『推荐能源』列）",
                      "读法②：**能源池/外部增强**里的一条 ⇒ 并排、不硬判"
                      "（🔴 **带条件**：「如可用」⇒ 与「未核实不标绿」同族，**不许当已可用**；"
                      "『推荐能源』候选已 4 个：3 本地 + 1 云端 ⇒ 现 **4/4/4** —— **齐 ≠ 许可**）"),
                     # 🔴 R-H447：第二十四条 —— 仍不硬判 · **一段章标题**（不是格值）
                     ("Agent 编排", "读法①：主人设计稿里的**又一段 / 又一个小节标题**（与『一、』『二、』『三、』『3.x』同族）",
                      "读法②：**编排内核**那件事的**另一种说法** ⇒ 并排、不硬判"
                      "（🔴 **同名 ≠ 同物**：盘上『Agent 编排』只有 1 行"
                      "（docs/钩子矩阵.md:7 的设计基准行），而『编排』是**既有概念**"
                      "（tools/orchestration_kernel.py 的『编排内核』）⇒ 都不许当同一个）"),
                     # 🔴 R-H449：第二十五条 —— 仍不硬判 · **两件事拼在一句里**（带 `+`）
                     ("本地模型 + 编排内核", "读法①：**一段 / 一个小节标题**（与『Agent 编排』同族）",
                      "读法②：**两件事并列**（『本地模型』与『编排内核』各一件）"
                      "⇒ 🔴 但**不许我擅自把它拆成两条**（拆了就改了主人的话）",
                      "读法③：**一件事** —— 『本地模型』**接进**『编排内核』的衔接关系"
                      "（🔴 **重合**：与第二十四条『Agent 编排』那条**部分重合**"
                      "（重合串『编排内核』）⇒ 并排记、**不许当同一个**；"
                      "取证：rg 编排内核 => **114 行 / 36 文件** · rg 本地模型 => **69 行 / 12 文件**"
                      "· 复合串**整体** => **0 行**）"),
                     # 🔴 R-H450：第二十六条 —— 仍不硬判 · 与已登记的『兜底层』**相关但不同物**
                     ("默认兜底", "读法①：3.2 那张表里**又一条**（与『本地模型不够时，上云端最强模型』"
                      "『只用本地模型，不够就降级』同族 —— 一条**降级 / 兜底**的说明）",
                      "读法②：**一条独立的设计原则**（与『五层防护，逐层兜底』同族）",
                      "读法③：与已登记的 **L5『兜底层』/『最终兜底方案』相关**"
                      "（都含『兜底』）⇒ 并排记、🔴 **不许当同一个**"
                      "（🔴 **同名 ≠ 同物**：取证 rg 默认兜底 => **3 行 / 3 文件**，"
                      "而三处**不是同一件事**：`INDEX.md:50` 讲 PPT 模板兜底 · "
                      "`voice_orchestra.py:161` 是代码里的分支 · `memory/2026-09-18.md:1330`"
                      "是**我早前写的自检摘要** ⇒ 都不许当同一个、也都不许当「已落位」）"),
                     # 🔴 R-H452：第二十七条 —— **编号小节标题**（递增读数 · 不落表）
                     ("3.5 与已有系统的对接", "形态：**编号小节标题**（与 3.1 / 3.2 / 3.3 / 3.4 同族）",
                      "顺位读数：3.4 → 3.5 **递增**（三章小节现 5/5 连续）",
                      "🔴 **不许塞进 FUSION_SECTIONS**（那张表是『四、』的 4.1-4.3 ⇒ "
                      "塞『三、』会破坏递增）· 取证 rg 3.5 与已有系统的对接 => **0 行**（新事据）"),
                     # 🔴 R-H452：第二十八条 —— 仍不硬判（**表头 or 正文**两读法）
                     ("已有模块", "读法①：**3.5 那张表的表头 / 列名残片**"
                      "（与『层级』『名称』『核心职责』同族）",
                      "读法②：**3.5 正文里的一句残片**（不是表头）"
                      "（🔴 **同名 ≠ 同物**：盘上 4 行 / 4 文件，其中两处**正是当表头用**"
                      "（`docs/能源观.md:147` 的『挂已有模块』· `docs/代码艺术内核设计.md:44` 的表头），"
                      "另两处是 `memory` 抄录与 `sources.json` 的一句 note ⇒ 都不许当同一个）"
                      "· 🔴 **不擅自塞进 TRUNCATED_FRAGMENTS**（碎片契约 7 条 + 用例钉着"
                      "⇒ 塞进去 = **改契约** = 判定；要改等主人一句话）"),
                     # 🔴 R-H453：第二十九条 —— 仍不硬判 · **版本号对不上**（v2.0 ↔ v3.0）
                     ("自动化切换引擎 v3.0", "读法①：**既有模块的升级** —— 盘上`docs/自动化切换引擎.md` 现在写的是 **v2.0**",
                      "（『v2.0 四层+回灌 + 19 条短板已登记』）⇒ 主人给的是 **v3.0**"
                      "⇒ 🔴 **版本号对不上**（差一个版本）",
                      "读法②：**另一件东西**（与盘上同名模块**同名 ≠ 同物**）"
                      "⇒ 两读法并排、不硬判（🔴 不许把 v3.0 当『已在盘上』；"
                      "也不许把本段**挂到**那份文档上 —— 挂 = 判定）"),
                     # 🔴 R-H454：第三十条 —— 🔴 与前面几刀**相反的情形**：盘上**真有同名物**
                     ("能源池", "读法①：**指名一个既有模块** —— 盘上真有同名物**且已接线**"
                      "（`tools/energy_pool.py` · `api.py:412` 的 `kind == \"energy_pool\"` 出口 · "
                      "`caps_registry.py` 已登记 · `tests/test_energy_pool.py` 有用例 · "
                      "`docs/能源观.md`『③ 能源池』里有 lease_energy / hogging_not_allowed）",
                      "读法②：与设计稿 3.4 矩阵的『**推荐能源**』列**同向但不同物**"
                      "（都讲能源 ⇒ 并排记、🔴 **不许当同一个**；R-H432 已记过这条呼应）"
                      "⇒ 🔴 **既不许当新事据**（盘上早就有）、**也不许当「许可落位」**"
                      "（到齐 ≠ 许可）；也可能是主人**下一段的节名** ⇒ 待续、不硬判"),
                     # 🔴 R-H455：第三十一条 —— 仍不硬判（紧跟 3.5 + 『已有模块』之后）
                     ("路由层从池中 pick() 能源，按优先级",
                      "读法①：**3.5『与已有系统的对接』那张表里的一行**"
                      "（紧跟 3.5 与『已有模块』之后 ⇒ **位置推断**，不许当判定）",
                      "读法②：**一条独立的说明 / 原则**（讲「怎么用池」）"
                      "（🔸 盘上真有对应写法：`tools/energy_pool.py:311` 的 "
                      "`def pick(self, capability=\"text\", prefer=\"免费\")`"
                      "与 `:436` 的 `pool.pick(cap, prefer)` ⇒ **这条不是空话**；"
                      "但『按优先级』这四个字**盘上没有同名原话** ⇒ 不硬判）"),
                     # 🔴 R-H455：第三十二条 —— 与 R-H454「能源池」**同型**（盘上真有文档概念）
                     ("弹性触手池", "读法①：**既有文档概念**（`docs/模型密钥池设计.md` 架构行："
                      "『大脑 → 万能插 → 弹性触手池 → 密钥池』· `:29` 执行末端 lease/release"                      "『**不拥有密钥**』）",
                      "读法②：**另一件东西**（若主人指的是别处 ⇒ 并排、不硬判）"
                      "（🔴 取证：rg 弹性触手池 => **3 行**，**全在该设计文档里**；"
                      "rg 触手池 => 只 docs + memory ⇒ **代码物未见** ⇒ "
                      "既不许当『已实现』、也不许当新事据；顺序读数 `:92` 『排在弹性触手池之后、"
                      "编排内核之前』）"),
                     # 🔴 R-H456：第三十三条 —— 仍不硬判（与上一句**像一对**、但不许当同一个）
                     ("路由层决定用哪个能源，触手负责执行",
                      "读法①：**3.5 那张表里的一行**（紧跟 pick() 那条之后 ⇒ 同一节 ⇒ "
                      "**位置推断**，不许当判定）",
                      "读法②：**一条独立的分工原则**（谁决定 / 谁执行）"
                      "（🔺 与 R-H455『路由层从池中 pick() 能源，按优先级』**同向、像一对**"
                      "⇒ 并排记、🔴 **不许当同一个**、**也不许我擅自调和**；"
                      "🔸 另与盘上 `local_brain.py:6`『大脑（主机）= 纪律 + 门禁 + 审计 + "
                      "身份内核 + 决策权』**同向**（都讲分工）⇒ 呼应、不硬配）"),
                     # 🔴 R-H456：第三十四条 —— 与『能源池』同型，但**多一档：有闸**
                     ("身份内核", "读法①：**既有模块 / 架构位**"
                      "（`local_brain.py:6` 主机五件之一）",
                      "读法②：**红线族里的那一条** —— 『身份内核不许被模型改写』"
                      "（🔴 已带机械闸：`check_identity_text` → `identity_rewritten`；"
                      "同族还有 `auto_switch.py:185/358` · `cloud_pc.py:60`『身份源仍在本地』）"
                      "⇒ 🔴 **既不许当新事据**（盘上 34 行 / 12 文件、且有闸），"
                      "**也不许当「许可落位」**；另：`docs/能源观.md:64-72` 已把它与能源层"
                      "写成**根与叶**（『能源层是叶，身份内核是根；换叶不换根』）⇒ 呼应、不硬配"),
                     # 🔴 R-H457：第三十五条 —— 形态待定（**下划线英文标识符**，不像中文小节名）
                     ("trace_store", "读法①：**指名该既有模块**"
                      "（模块在 `gbt_allinone/trace_store.py` —— ⚠️ **不在 tools/ 下**）",
                      "读法②：**3.5 那张表里的一行**（『已有模块』= trace_store）"
                      "⇒ **位置推断**，不许当判定"
                      "（🔸 **三处同名且形态一致**：模块 / `caps_registry.py:659` 的注册名 / "
                      "`api.py:319` 出口的 `kind == \"trace_store\"` ⇒ **只记读数**、"
                      "🔴 **不下「就是同一个」的判定**）"
                      "⇒ **既不许当新事据**（盘上 132 行 / 54 文件、四件齐）、"
                      "**也不许当「许可落位」**（到齐 ≠ 许可）"),
                     # 🔴 R-H458：第三十六条 —— 盘上**已实现且带闸**（与 R-H454/R-H457 同型）
                     ("每次切换写 model_used + dispatch_reason",
                      "读法①：**红线清单里的一条**（盘上原文是**两句**：『每次切换必须记 "
                      "`model_used`（无痕即未发生）』+『每次调度写 `dispatch_reason`』"
                      "⇒ 主人这句是把**两条并成一句**）",
                      "读法②：**那张表里的一行**（位置推断）"
                      "（🔴 盘上**已有机械闸**：`auto_switch.py:471` `must_dispatch_reason`"
                      "→ 缺则 `no_dispatch_reason`（短板⑧已登记）· `model_used` 见 "
                      "`auto_switch.py` / `caps_registry.py` / `docs/自动化切换引擎.md` ⇒ **不许当新事据**、"
                      "⚠️ **本刀自报**：这一处我先**凭印象**写成 `local_brain.py`，实测**不在**它里面"
                      "⇒ 当场改正（**不许凭印象写出处** —— 出处必须 rg 出来的）"
                      "**也不许当「许可落位」**；"
                      "⚠️ **并句 ≠ 原文**：盘上是两句、主人是一句 ⇒ 并排记、不硬配）"),
                     # 🔴 R-H458：第三十七条 —— **章节标题**（中文数字序号）
                     ("️ 四、五条红线（写死）",
                      "形态：**章节标题**（中文数字序号『四、』⇒ 与『一、』『二、』『三、』同族）"
                      "· 顺位读数：**第四段 · 递增**",
                      "🔴 段首带一个**不可见字符 U+FE0F（变体选择符）** ⇒ "
                      "**逐字保留、不擅自删**（只记读数；删了就是改写主人原话）"
                      "（取证：整串 => **0 行** ⇒ 新事据；盘上『五条红线』=> 117 行 / 37 文件"
                      "（**既有体例**，但**整串没有**）⇒ 不许当同一个）"),
                     # 🔴 R-H458：第三十八条 —— 仍不硬判（孤立一词）
                     ("红线", "读法①：**那张表的表头 / 列名残片**"
                      "（若如此，它会是**第 8 个**表头候选）",
                      "读法②：**正文里的一句残片**（不是表头）"
                      "（🔴 **不擅自塞进 TRUNCATED_FRAGMENTS** —— 碎片契约 7 条 + "
                      "用例钉着 ⇒ 塞进去 = **改契约** = 判定；要改等主人一句话）"
                      "· 取证：rg 红线 => **825 行 / 158 文件**（全仓体例用词）"),
                     # 🔴 R-H460：第三十九条 —— 与 R-H397 那句**两处不同**（前缀 + 模态）
                     ("用户选 gbt-best，网关不许在高峰期偷偷降档",
                      "读法①：3.1/3.2 那条原则的**另一种说法**（**gbt-*** 前缀版）",
                      "读法②：**一条独立的原则行**"
                      "（🔴 与 R-H397『用户选 **teamo-best** / …，网关**不会**在高峰期偷偷降档』"
                      "**两处不同**：① 前缀 `teamo-*` → **`gbt-*`** ② 模态 **不会（陈述）→ 不许（禁止）**"
                      "⇒ **并排记、不许当同一个、不许我擅自调和**（两处差异都不许我抹平）；"
                      "🔸 这正好**印证 R-H422 记的『两套前缀』**（teamo-* ↔ gbt-*））"),
                     # 🔴 R-H460：第四十条 —— 与 R-H398 那句**一字之差**，且**已是既有原则行的一段**
                     ("五层逐级兜底", "读法①：**既有原则行的一段**"
                      "（『用户显式声明优先级 → 网关绝不偷换 → **五层逐级兜底** → 每次切换留痕』的逐字子串）",
                      "读法②：**一条独立的原则行**"
                      "（🔴 与 R-H398『五层防护，**逐层**兜底』**一字之差**（逐级 ↔ 逐层）"
                      "⇒ 三方并排、**不许当同一个**；"
                      "⚠️ 它**已在 verbatim 里**（作为那条原则行的一段）⇒ 既不是新事据、"
                      "也不是整句重发 ⇒ **三种关系并排记**、不硬判）"),
                     # 🔴 R-H461：第四十一条 —— 『**半句落地、整句未落**』
                     ("每一层都有明确的兜底策略，不许静默失败",
                      "读法①：**四、那张表 / 红线清单里的又一条**（位置推断）",
                      "读法②：**一条独立的原则**"
                      "（🔴 **半句已在盘上落地**：『不许静默失败』=> 5 行"
                      "（`holo_pet/app.js:1878` R-H169『出问题必须在页面上写红字』· "
                      "`gbt_allinone/tentacle/capture_environment.py:484` R-H203『统一失败出口』）"
                      "而**整句 0 行** ⇒ 记「**半句落地、整句未落**」、"
                      "🔴 **不许把半句当整句的许可**）"),
                     # 🔴 R-H461：第四十二条 —— 已是**红线第一条**，但同仓另有**同名不同物**
                     ("本地优先", "读法①：主人早前给的**五条红线的第一条**"
                      "（已落成表行 + **带判据**：`docs/自给自足大脑.md:69`"
                      "『本地优先（默认纯本地，外部增强需显式启用）』+'mode 默认 LOCAL_ONLY'）",
                      "读法②：**另一件东西** "
                      "（🔴 **同名 ≠ 同物**：同仓 `docs/AwesomeTools蒸馏.md:2310/2316` 里那个"
                      "『本地优先』讲的是 **Obsidian 的招牌**"
                      "⇒ 并排记、**不许当同一个** ⇒ 不许当新事据、也不许当「许可落位」）"),
                     # 🔴 R-H462：第四十三条 —— **新事据**，但是『本地/云端』主题的**第 4 次说法**
                     ("默认走本地模型，云端只在任务需要时启用",
                      "读法①：**红线清单 / 3.1 原则里的又一条**（位置推断）",
                      "读法②：**一条独立的原则**"
                      "（🔴 **第 4 次说法**：盘上已有三处（都在 verbatim 的 3.2 表里）——"
                      "R-H424『本地模型不够时，上云端最强模型』· R-H427『本地模型优先，不够再上云端』"
                      "· R-H430『只用本地模型，不够就降级』⇒ **四次并排、不许当同一个、"
                      "不许我擅自调和**（R-H430 那次已记『**可能不同向**』——"
                      "前两句说『上云端』、第三句说『降级』、本句说『**只在需要时启用**』）"
                      "· 🔸 与 R-H461『本地优先』（红线第一条 + `LOCAL_ONLY`）**同向**"
                      "⇒ 呼应、不硬配）"),
                     # 🔴 R-H462：第四十四条 —— 与 R-H460 **同型**（子串到货）
                     ("每次切换留痕", "形态：**已是既有原则行的一段**"
                      "（『用户显式声明优先级 → 网关绝不偷换 → 五层逐级兜底 → **每次切换留痕**』的逐字子串）"
                      "⇒ 与 R-H460『五层逐级兜底』**同型**（那次的第二种形态：**子串到货**）"
                      "—— 本刀是**同型第 2 次** ⇒ 并排记",
                      "⇒ 既**不是新事据**（6 行、且已在 verbatim）、也**不是整句重发**"
                      "⇒ **三种关系并排**、不硬判；🔸 与刚登记的"
                      "『每次切换写 model_used + dispatch_reason』**呼应、不硬配**"),
                     # 🔴 R-H463：第四十五条 —— 『**三件都落地、拼句未落**』（与 R-H461 半句落地同族）
                     ("写 trace_store，记 model_used + dispatch_reason",
                      "读法①：**红线清单 / 留痕口径里的又一条**（位置推断）",
                      "读法②：**一条独立的原则**"
                      "（🔴 **三件分别在盘上都在**：`trace_store`（四件齐）· `model_used`（23 行）"
                      "· `dispatch_reason`（13 行、**带闸** `must_dispatch_reason`）；另 "
                      "`auto_switch.py:190`『每次执行 → log: trace_store』"
                      "⇒ 记「**三件都落地、拼句未落**」（与 R-H461『半句落地』**同族但不同**）"
                      "⇒ 🔴 **不许当新事据**、**也不许把三件当整句的许可**；"
                      "🔸 与 R-H458『每次切换写 model_used + dispatch_reason』**高度重合**"
                      "（重合串『model_used + dispatch_reason』）⇒ 并排、**不许当同一个**（本句多了『写 trace_store』））"),
                     # 🔴 R-H463：第四十六条 —— 与 R-H456 **相关但不同** + **子串到货（同型第 3 次）**
                     ("身份内核不变", "形态：**官方红线⑤ 行的一段**"
                      "（`docs/自给自足大脑.md:73`『| 5 | **身份内核不变**（永远是 GBT小土豆） | "
                      "`identity_rewritten`（同族） |』—— **带判据**）",
                      "⇒ **子串到货**（R-H460『五层逐级兜底』→ R-H462『每次切换留痕』→ 本刀 = **同型第 3 次**）"
                      "· 🔸 与 R-H456 登记的『身份内核』**相关但不逐字同**"
                      "（那边是**名词/模块**，本句是**断言式**）⇒ 并排、**不许当同一个**"
                      "· 同族真事据：`cloud_pc.py:60` · `docs/云电脑与全自动发布设计.md:52` · "
                      "`caps_registry.py:871`（云电脑能力位的五条红线之一）"),
                     # 🔴 R-H430：第十一条 —— **同主题第三次说法，但未必同向**（不许我调和）
                     ("只用本地模型，不够就降级", "读法①：3.2 那张表某行的**格值**",
                      "读法②：**一条独立的降级原则/说明** ⇒ 与 R-H424 / R-H427 是**同主题第三次**"
                      "—— ⚠️ 但那两句都说「**上云端**」，本句只说「**降级**」"
                      "⇒ **可能不同向**（降级 ≠ 上云端）⇒ 三次并排、**不许当同一个**、"
                      "🔴 **更不许我擅自调和**"),),
     "alias_notes": ("STICKY（粘性）↔ L2 行第三格里已有的『通道粘性』⇒ 同义标注、并排记、不许当同一个",
                     # 🔺 R-H413：**又一个英文标注**（说明 ≠ 改写）⇒ 并排记
                     "HEALTH（健康）↔ L3 行的『健康检测层』⇒ 同义标注、并排记、不许当同一个",
                     # 🔴 R-H416：**标注先到、名字未到** —— FALLBACK（兜底）此刻**没有对应的中文名**
                     #    （L5 行只到层格）⇒ 只记「它到了」，**不许替它编一个名字**
                     "FALLBACK（兜底）⇒ **标注先到、对应的中文名还没到**（L5 行未成行）"
                     "⇒ **不许替它编名字**",
                     # 🔺 R-H417：**名字后到了** ⇒ 标注与名字**对上了**（第三种情形）
                     "🔺 R-H417：『兜底层』到了 ⇒ FALLBACK（兜底）↔ 『兜底层』"
                     "**现在对上了**（标注先到 · 名字后到 · **并排记、不合并**）"),
     "verbatim": ("一、核心能力蒸馏：三层工程哲学 | 层级 | 第一层：路由策略 | 显式声明，绝不偷换 | "
                  "用户选 teamo-best / teamo-balanced / teamo-eco，网关不会在高峰期偷偷降档 | "
                  "第二层：调度架构 | 五层防护，逐层兜底 | "
                  "策略层 → 匹配层 → 健康检测层 → 故障切换层 → 兜底层，"
                  "500+ 供应商每个模型独立健康评分 | 第三层：成本控制 | 靠工程优化，不靠掺水 | "
                  ">99% 缓存命中率，把重复请求的成本压到最低，而不是偷换模型 | "
                  "二、五层调度系统的蒸馏提炼 | "
                  "TeamoRouter 最核心的架构，是一套能管理 500+ 供应商的五层调度系统： | L1 | 路由策略层 | 按用户声明的优先级选择路由方向 | L2 | 智能匹配层 | 模型映射 + 通道粘性 + 缓存热度感知 | STICKY（粘性） | L3 | 健康检测层 | 智能心跳 + 稀释率检测 + 丢包率监控 | HEALTH（健康） | L4 | 故障切换层 | 电路断路器 + 灰度降级 | FALLBACK（兜底） | L5 | 兜底层 | 最终兜底方案 | 这五层，就是 GBT 原生路由层要照抄的骨架。 | 三、为 GBT 设计的原生路由层 | 3.1 核心设计原则 | text | 用户显式声明优先级 → 网关绝不偷换 → 五层逐级兜底 → 每次切换留痕 | 关键：与 TeamoRouter 不同的是，我们的路由层不依赖外部网关，而是内置于万能插，由本地大脑直接调度。 | 3.2 三层路由预设（照抄 TeamoRouter 的命名逻辑） | 预设 | 对应优先级 | 本地行为 | gbt-best | 质量优先 | 本地模型不够时，上云端最强模型 | gbt-balanced | 平衡优先 | 本地模型优先，不够再上云端 | gbt-eco | 成本优先 | 只用本地模型，不够就降级 | 3.3 五层本地路由架构 | text | L1 策略层：用户声明 gbt-best / gbt-balanced / gbt-eco | L2 匹配层：模型映射 + 会话粘性 + 本地缓存热度感知 | L3 健康层：本地模型健康 + 能源池可用性 + 显存监控 | L4 切换层：本地模型不可用 → 能源池兜底 → 降级上报 | L5 兜底层：全部不可用 → 返回 needs_external_key | 3.4 路由决策矩阵（结合我们的能源池） | 任务类型 | 复杂度 | 推荐能源 | 代码补全 / 单行生成 | 低 | 本地 Qwen2.5-Coder-7B | 不管做什么必须注重细节 | 工具函数 / 脚本 | 低-中 | 本地 Qwen2.5-7B | Bug 定位与修复 | 中-高 | 本地 DeepSeek-R1-7B | 系统架构设计 | 高 | 云端 Agnes（如可用） | Agent 编排 | 本地模型 + 编排内核 | 默认兜底 | 3.5 与已有系统的对接 | 已有模块 | 自动化切换引擎 v3.0 | 能源池 | 路由层从池中 pick() 能源，按优先级 | 弹性触手池 | 路由层决定用哪个能源，触手负责执行 | 身份内核 | trace_store | 每次切换写 model_used + dispatch_reason | ️ 四、五条红线（写死） | 红线 | 用户选 gbt-best，网关不许在高峰期偷偷降档 | 五层逐级兜底 | 每一层都有明确的兜底策略，不许静默失败 | 本地优先 | 默认走本地模型，云端只在任务需要时启用 | 每次切换留痕 | 写 trace_store，记 model_used + dispatch_reason | 身份内核不变"),
     "got": "开头：『一、核心能力蒸馏：三层工程哲学』⇒ 止于『层级』（**未到齐**）；"
                    "🔺 **R-H395 到货第一层**：『**第一层：路由策略**』"
                    "（三层只到一层、且每层的内容还没到 ⇒ **仍未到齐**）；"
                    "🔺 **R-H396 到货第二条**：『**显式声明，绝不偷换**』"
                    "（形态：第一层下的**一条原则/红线**）⇒ **仍未到齐**；"
                     "（🔁 **R-H459**：主人**第二次**给这句 —— 与上面**逐字相同** ⇒ "
                     "**只补记次数、不新立在待定格、不落位**（**重复 ≠ 许可**）；"
                     "待定格仍 **38 条**（本刀**不许**把它变成第 39 条））"
                    "🔺 **R-H397 到货第三/第四条**：『**用户选 teamo-best / teamo-balanced / teamo-eco，"
                    "网关不会在高峰期偷偷降档**』（第一层的内容）·『**第二层：调度架构**』"
                    "⇒ **三层到二层**，仍**未到齐**；"
                    "🔺 **R-H400 到货第五条**：『**靠工程优化，不靠掺水**』"
                    "（形态：**第三层『成本控制』的内容**）"
                    "🔺 **R-H401 到货（第二节）**：『**>99% 缓存命中率…而不是偷换模型**』·『**二、五层调度系统的蒸馏提炼**』·『**TeamoRouter 最核心的架构，是一套能管理 500+ 供应商的五层调度系统：**』⇒ 又**止于『层级』**（表头）⇒ **仍未到齐**；"
                    "⇒ 📌 读数：**三层各有一句内容了**（路由策略 / 调度架构 / 成本控制）"
                    "—— ⚠️ 但**我不敢宣布整段到齐**（主人没说到此为止）⇒ 仍按**未到齐**处理",
     "disk_check": "rg TeamoRouter 全仓 => **0 行**（盘上 0 命中）；"
                   "🔺 **R-H397 复证**：rg gbt-best/teamo- 全仓 => **1 行**"
                   "（`memory/2026-09-20.md:3690`：**我早前记的**『三层预设 gbt-best / gbt-balanced / "
                   "gbt-eco』）· rg 调度架构 => **0 行**；"
                   "🔺 **R-H398 复证**：rg 五层防护/逐层兜底 => **0 行**；rg 兜底 => 命中**别处**"
                   "（CHARTER.md 的『不许加兜底让测试变绿』等 4+ 条）"
                   "⇒ 盘上**没有**『五层防护』这个词 —— 但**我早前记过『五层架构 L1-L5』**"
                   "（见 memory:3690 同一行）⇒ **像但不等于、不许当同一个**；"
                   "🔺 **R-H422 复证**：rg gbt-best 全仓 => **3 行**"
                   "（`memory:3690` + 本刀与 R-H397 的记录 —— **全部是我自己写的**）"
                   "—— ⚠️ 那条是**我自己写的对话摘要**，**不是主人的原话事据** ⇒ 不许当「已在盘上」用；"
                   "🔺 **R-H399 复证**：rg 策略层/匹配层/…/500+ => 命中的**全是别处**"
                   "（`api.py` 讲 GBT 自己的**策略层** · `panel_server.py` 同族 · `INDEX.md` 的『500+ 子目录』）"
                   "⇒ 🔴 **同名 ≠ 同物**（别人的『策略层』不是这一层的『策略层』）⇒ 不许当同一个"
                   # 🔺 R-H446：本刀现场取证（Agnes 在盘上**早就有** ⇒ 不抹掉、也不据此当「已可用」）
                   "；🔺 **R-H446 复证**：rg Agnes 全仓 => **51 行 / 20 个文件**（本刀现场取）"
                   "—— 其中**真事据 4 处**（`tools/auto_switch.py:173,176` 切换规则里的"
                   "『alt：云端 Agnes』『prefer：云端 Agnes』+ `docs/自动化切换引擎.md:60,63`）"
                   "⇒ 🔴 **同名 ≠ 同物**：那边是『切换规则里的备选能源』，本刀这个是『3.4 矩阵某格候选』"
                   "⇒ 并排记、**不许当同一个**；⚠️ 但『盘上早有 Agnes』本身是**真读数**"
                   "⇒ 不抹、也不据此当「已可用」"
                   "；🔺 **R-H447 复证**：rg Agent 编排 全仓 => **1 行**（`docs/钩子矩阵.md:7` 的设计基准行）· rg 编排 => **多处**"
                   "（`tools/orchestration_kernel.py` 编排内核 · `README.md` 等）"
                   "⇒ 盘上『编排』是**既有概念** ⇒ 🔴 **同名 ≠ 同物**，并排记、不硬配"
                   "；🔺 **R-H448 复证**：待定格里名字为『高』的条目 => **1 条**"
                   "（实测 · **无重名**）· rg -c 高（本模块）=> **15 行**"
                   "⇒ 主人第二次给的东西**没有变成第二条**（重复只补记、不新立）"
                   "；🔺 **R-H449 复证**：rg 编排内核 => **114 行 / 36 文件**"
                   "（`tools/orchestration_kernel.py:5` · `docs/编排内核设计.md:4` 等）"
                   "· rg 本地模型 => **69 行 / 12 文件** · 复合串『本地模型 + 编排内核』**整体**"
                   "=> **0 行** ⇒ 两件事**各自在盘上都有**，拼在一句里这个**形态是新的**"
                   "⇒ 🔴 既不许当「已落位」、也不许当「已有概念的回流」"
                   "；🔺 **R-H450 复证**：rg 默认兜底 => **3 行 / 3 文件**"
                   "（`INDEX.md:50` 泛 PPT 默认兜底 · `voice_orchestra.py:161` 代码分支 ·"
                   "`memory/2026-09-18.md:1330` **我早前的自检摘要**）"
                   "· rg 兜底 => **406 行 / 125 文件** · rg 兜底层 => **26 行** ·"
                   "rg 最终兜底方案 => **10 行** ⇒ 🔴 **同名 ≠ 同物**：三处**不是同一件事**"
                   "⇒ 并排记、不硬配；也**不许**拿它当 L5 那两格（兜底层 / 最终兜底方案）的同一个"
                   "；🔺 **R-H451 复证**：待定格里名字为『本地 Qwen2.5-7B』的条目 => **1 条**"
                   "（实测 · **无重名**）· 名字为『本地 Qwen2.5-Coder-7B』的条目 => **1 条**"
                   "· rg Qwen2.5-7B => **24 行 / 8 文件**（`tools/local_brain.py` · "
                   "`docs/本地原生脑.md` · `docs/自给自足大脑.md` 等）"
                   "⇒ 它是**既有事据**、但**与 R-H440 那条同处待定格** ⇒ 第二次到货只补记、不新立"
                   "；🔺 **R-H452 复证**：rg 3.5 与已有系统的对接 => **0 行**（新事据）"
                   "· rg 已有模块 => **4 行 / 4 文件**（`docs/能源观.md:147`『挂已有模块』"
                   "· `docs/代码艺术内核设计.md:44` 表头 · `memory/2026-09-20.md:7835` 抄录"
                   "· `sources.json:546` 一句 note）⇒ 🔴 **同名 ≠ 同物**（四处用法不同）"
                   "· rg 3.4 路由决策矩阵 => **3 行** · rg 3.3 五层本地路由架构 => **4 行**"
                   "⇒ 3.x 小节序列在盘上本来就有影子，本刀补 3.5 ⇒ **递增连续**"
                   "；🔺 **R-H453 复证**：rg 自动化切换引擎 => **11 行 / 7 文件**"
                   "（真事据 · `docs/自动化切换引擎.md`）· 复合串『自动化切换引擎 v3.0』"
                   "**整体** => **0 行** · rg v3.0 => **49 行 / 30 文件**（均**不带**『自动化切换引擎』）"
                   "· 🔴 **盘上那份文档写的是 v2.0**（`:133` `:194` 行）⇒ **v2.0 ↔ v3.0 对不上**"
                   "⇒ 既不许当「已有」、也不许当「已升级」"
                   "；🔺 **R-H454 复证**：rg 能源池 => **36 行 / 9 文件**（**既有真物**）"
                   "—— `tools/energy_pool.py`（10 行命中）· `tests/test_energy_pool.py` ·"
                   "`api.py:412`（`kind == \"energy_pool\"`）· `caps_registry.py` 登记 ·"
                   "`docs/能源观.md`（『③ 能源池』+ lease_energy / hogging_not_allowed）"
                   "· rg energy_pool => **7 个文件**（已接线）⇒ 🔴 与 R-H453 那种"
                   "『版本号对不上』**是相反的情形**：这个是**同名且真有** ⇒ 既不新、也不可当许可"
                   "；🔺 **R-H455 复证**：rg pick( => **20 行 / 9 文件**（真事据 "
                   "`tools/energy_pool.py:311` `def pick(...)` · `:436` 调用）"
                   "· rg 弹性触手池 => **3 行 / 1 文件**（全部在 `docs/模型密钥池设计.md`"
                   "：`:19` 架构行 · `:29` 执行末端 · `:92` 顺序）· rg 触手池 => 4 行"
                   "（**只 docs + memory · 代码物未见**）⇒ 🔴 与 R-H454 同型：**盘上真有，但有名字面"
                   "；🔺 **R-H456 复证**：整句『路由层决定用哪个能源，触手负责执行』=> **0 行**"
                   "（『触手负责执行』0 行 · 『路由层决定』0 行）⇒ **新事据** ；"
                   "rg 身份内核 => **34 行 / 12 文件**（`local_brain.py` 6 行 · `能源观.md` 4 行 · "
                   "`本地原生脑.md` 4 行 · `auto_switch.py` 3 行 · `cloud_pc.py` 2 行 等）"
                   "—— **不只文档：有闸**（`check_identity_text` → `identity_rewritten`）"
                   "⇒ 与『能源池』同型（盘上真有），比『弹性触手池』**强一档**（那个只见文档）"
                   "；🔺 **R-H457 复证**：rg trace_store => **132 行 / 54 文件**（**四件齐**）"
                   "—— 模块 `gbt_allinone/trace_store.py`（**不在 tools/ 下**）· 注册 "
                   "`caps_registry.py:659` · 只读出口 `api.py:319`（`kind == \"trace_store\"` → `status()`）"
                   "· 用例 `tests/test_trace_store.py` · 被 `h3_video_gen`(8) `feishu_embed`(3) "
                   "`libtv_skill`(3) `local_brain`(4) `dream_replay`(2) `wave_probe`(2) 等引用"
                   "⇒ 🔴 比『能源池』(9 文件) **更重**：**54 个文件**提到它 ⇒ 但**仍然不许当许可**"
                   "；🔺 **R-H458 复证**：rg model_used => **23 行 / 4 文件** · "
                   "rg dispatch_reason => **13 行 / 5 文件**（**带闸**：`auto_switch.py:471` "
                   "`must_dispatch_reason` → `no_dispatch_reason`）· rg 五条红线 => "
                   "**117 行 / 37 文件**（既有体例）· 但整串『（U+FE0F）四、五条红线』"
                   "=> **0 行**（新事据）· rg 红线 => **825 行 / 158 文件**"
                   "⇒ 🔴 三行里**两行的依据是盘上真物**、一行的依据是**不可见字符**"
                   "（U+FE0F）⇒ 逐字保留"
                   "；🔺 **R-H459 复证**：这句**逐字相同**地第二次到货（R-H396 已在 "
                   "09-20 23:33 登记）· 待定格里名字为它的条目 => **0 条** · "
                   "verbatim 里出现 => **1 次** · `got` 里出现 => **1 次** · "
                   "全仓 rg 显式声明，绝不偷换 => **19 行 / 4 文件**"
                   "（`memory/2026-09-20.md` 摘要 · `docs/AwesomeTools蒸馏.md:3066` 小节 · "
                   "本模块两处）⇒ 🔴 **重复 ≠ 许可**：本刀**一个新条目都没立**"
                   "；🔺 **R-H460 复证**：rg 偷偷降档 => **6 行**（**全部是我自己写的**：`docs/AwesomeTools蒸馏.md:3086-3180`"
                   "的 R-H397 小节与语义同向链）· rg gbt-best => **37 行** · rg teamo-best => **7 行**"
                   "· rg 五层逐级兜底 => **3 行**（**全部是本仓自己写的**：module verbatim · `docs:3296`"
                   "· `tests:914`）⇒ 它**已是既有原则行的一段** · rg 逐层兜底 => **15 行**"
                   "（含 R-H398 那句）⇒ 🔴 两句都**不是新事据**、也都**不是整句重发**"
                   "⇒ 三种关系并排：本条 ↔ R-H397/R-H398 ↔ 既有原则行的一段"
                   "；🔺 **R-H461 复证**：整句『每一层都有明确的兜底策略，不许静默失败』=> **0 行**；"
                   "但『不许静默失败』=> **5 行**（`holo_pet/app.js:1878` · "
                   "`holo_pet/tests/test_panel_cards.py` · `memory/2026-09-19.md:1887/1903` · "
                   "`gbt_allinone/tentacle/capture_environment.py:484`）· 『兜底策略』=> 2 行 · "
                   "『静默』=> **527 行 / 142 文件** · rg 本地优先 => **18 行 / 7 文件** "
                   "（`docs/自给自足大脑.md:69` 是**红线第一条 + 带判据 LOCAL_ONLY**；"
                   "；🔺 **R-H462 复证**：整句『默认走本地模型，云端只在任务需要时启用』"
                   "=> **0 行**（『云端只在』也 0 行）⇒ **新事据**；但它是『本地/云端』主题的"
                   "**第 4 次说法**（前三次已在 verbatim：『本地模型不够时，上云端最强模型』"
                   "『本地模型优先，不够再上云端』『只用本地模型，不够就降级』）· "
                   "rg 每次切换留痕 => **6 行**，**已是既有原则行的一段**（与 R-H460 同型）· "
                   "rg 默认纯本地 => **3 行**（红线第一条那一族）"
                   "；🔺 **R-H463 复证**：整句『写 trace_store，记 model_used + dispatch_reason』"
                   "=> **0 行**（新事据），但**三件分别在盘上都在**（`trace_store` 四件齐 · "
                   "`model_used` 23 行 / 4 文件 · `dispatch_reason` 13 行 / 5 文件带闸）· "
                   "`auto_switch.py:190`『每次执行 → log: trace_store』· "
                   "rg 身份内核不变 => **4 行 / 4 文件**（`docs/自给自足大脑.md:73` 是**红线⑤ 行 + "
                   "带判据 `identity_rewritten`** · `cloud_pc.py:60` · `docs/云电脑与全自动发布设计.md:52` · "
                   "`caps_registry.py:871`）⇒ 一句是「三件都落地、拼句未落」、"
                   "一句是**子串到货（同型第 3 次）**"
                   "`docs/AwesomeTools蒸馏.md:2310` 那处是 **Obsidian 的**⇒ 同名 ≠ 同物）"
                   "（文档）≠ 有实现（代码）** ⇒ 不许当「已实现」",
     "note": "🔴 **未到齐**（截断在『层级』）⇒ 内容**一个字都不编**；"
             "✅ 盘上 **0 命中** ⇒ **不是回流**、是**新事据**；"
             "🔺 **R-H394**：它与后来那条『工程哲学』**逐字重合**（重合串『工程哲学』）"
             "⇒ 可能是**重发**/续写 ⇒ **并排记、不合并**（**重合 ≠ 同一个**）；"
             "🔺 **等主人补全**"},
    {"topic": "TeamoRouter · 工程哲学（孤立一词）", "at": "R-H394",
     "verbatim": "工程哲学",
     "got": "孤立一个词：『工程哲学』（上一段**止于**『层级』）⇒ **仍未到齐**",
     "disk_check": "rg 工程哲学 全仓 => **5 行，且全部是 R-H393 本刀自己写下的**"
                   "（盘上原无 ⇒ **不算外部命中**）",
     "note": "🔺 与第 1 条 `got` 里的『三层工程哲学』**逐字重合**（重合串『工程哲学』）"
             "⇒ 可能是**重发**、也可能是**续写** ⇒ 两者**并排记、不合并**（**重合 ≠ 同一个**）；"
             "🔴 **仍未到齐** ⇒ 内容**一个字都不编**；"
             "🔺 **同一件事两套前缀**：盘上那行是 `gbt-*`，主人本刀给的是 `teamo-*`"
             "⇒ **并排记、不硬配**（**不许当同一个**，也**不许擅自改盘上那行**）；"
             "🔺 **R-H398 又一处两套说法**：主人说『**五层防护**』，我早前记的是『**五层架构 L1-L5**』"
             "⇒ 同向但**不是同一个词** ⇒ **并排记**（一格都没合并）；"
             "🔺 **等主人补全**"},
)
INCOMING_DISTILLS_NOTE = (
    "**未到齐专区（R-H393）**：主人给的输入**没说完**时进这里 —— 只登记「到哪儿 / 盘上取证读数」，"
    "🔴 **内容不许编**；🔴 **一条都不许落表**；到齐后再谈归属（**到齐 ≠ 许可**）。"
)
FUSION_CASES = (
    {"no": 1, "text": "索引只读", "at": "R-H390", "teeth": (),
     "from": "PRIMITIVES:INDEX",
     "teeth_note": "⚠️ **目前没有牙**（「只读」是**设计约束**，不是机械牙）⇒ **如实记**、不硬凑",
     "crosscheck": "本仓 `PRIMITIVES` 的 **INDEX** 原语正是 `writes: False`、"
                   "note 写着「（只读）」⇒ **逐字对得上**（同族还有 LOOKUP/MAP/VERIFY 三条也都只读）"},
    {"no": 2, "text": "映射可追", "at": "R-H391",
     "from": "PRIMITIVES:MAP",
     "teeth": ("fusion_row_from_unknown", "fusion_row_crosscheck_unverified"),
     "crosscheck": "本仓 `MAP` 原语的 note 逐字就是「**每条都必须带出处，无出处不许进映射**」"
                   "⇒ 与「映射可追」**对得上**；而且盘上**已经有两条牙**在管它"
                   "（出处标签不许编 · 声称「逐字」就得真对得上）⇒ **有牙**"},
    {"no": 3, "text": "未核实不标绿", "at": "R-H392",
     "from": "PRIMITIVES:VERIFY",
     "teeth": ("unverified_green",),
     "crosscheck": "本仓 `VERIFY` 原语的 note 逐字就是「**验证工具是否已安装 / 可接入** —— "
                   "未核实不许标 green」⇒ 与「未核实不标绿」**对得上**；"
                   "而且盘上**有真牙**在管它：`unverified_green` ⇒ **有牙**"},
)
FUSION_CASES_NOTE = (
    "**用例区（R-H390 · 主人逐字）**：4.3 的用例逐条登记；"
    "🔴 每条都要写**出处标签**（`PRIMITIVES:INDEX` 这种）且标签必须真的存在；"
    "🔴 一条都不许落表；⚠️ 小节标题说**三条** ⇒ 到齐前不合并、到齐后也**不擅自落表**。"
)
FUSION_SECTIONS = (
    {"no": "4.1", "title": "工具清单 → 能力位映射", "at": "R-H384",
     "note": "小节标题（逐字）；它的内容已按 **FUSION_ROWS** 登记（7 条映射）"},
    {"no": "4.2", "title": "蒸馏为技能：awesome_tools_index", "at": "R-H384",
     "note": "小节标题（逐字）；它的内容已按 **FUSION_PRIMITIVES** 登记（四原语 4/4）"},
    {"no": "4.3", "title": "三条带牙用例", "at": "R-H389",
     "note": "🔺 **R-H389 新给的小节标题**（逐字）—— ⚠️ **内容还没到**"
             "（紧跟其后的是残片『用例』）⇒ **不许替它编三条用例**"},
)
FUSION_SECTIONS_NOTE = (
    "**小节区（R-H384/R389 · 主人逐字）**：设计稿的小节标题逐条登记；"
    "🔴 编号必须**递增且不重**（不许跳号、不许重号）；🔴 一条都不许落表；"
    "⚠️ 只有标题、没有内容的，**内容不许替主人编**。"
)
FUSION_PRIMITIVES = (
    {"at": "R-H385", "name": "INDEX",
     "note": "🔺 **后继词，不是补全**：它**紧跟**碎片『原语』之后 —— "
             "主人**没有**把『原语』改成别的字 ⇒ 那条碎片**仍留空不编**；"
             "📌 **已在**盘上：本仓 `PRIMITIVES` 的**第 1 条**（逐字 `INDEX`）"
             "⇒ **顺位一致**（主人给的顺序 = 本仓顺序）；"
             "⚠️ 它是**原语名**、不是工具/分类名 ⇒ **不许塞进再现区**"
             "（那里要求 token 能在分类行/名单里按整段找到）"},
    {"at": "R-H386", "name": "LOOKUP",
     "detail": "查工具详情（介绍 + 下载地址）",
     "detail_round": "R-H387",
     "detail_note": ("⏸ **暂存、不落表**：**归属依据** = **结构**（主人上一轮先给名字、这一轮给介绍）"
                     "**+ 语义完全对得上**（「查工具详情」= 本仓 `LOOKUP` 的职能）"
                     "⇒ **结构 + 语义同向**；⚠️ 主人**没点名** ⇒ 仍只是**推断**；"
                     "🔸 第二种读法：也可能是**另一个技能的详情口**；🔴 **不落表**"),
     "note": "📌 **已在**盘上：本仓 `PRIMITIVES` 的**第 2 条**（逐字 `LOOKUP`）"
             "⇒ **顺位一致**（主人给的顺序 = 本仓顺序）；"
             "🔺 **R-H387**：主人给了它的**介绍**（见 `detail`）；"
             "⚠️ 与 INDEX 同族：**原语名不许塞进再现区**（它不是工具/分类名）"},
    {"at": "R-H387", "name": "MAP",
     "detail": "工具 → 能力位映射",
     "detail_round": "R-H388",
     "detail_note": ("⏸ **暂存、不落表**：**归属依据** = **结构**（上轮给名字、这轮给介绍）"
                     "**+ 语义完全对得上**（本仓 `MAP` 的 note 逐字就是「**工具 → 能力位**」）"
                     "⇒ **同向**；⚠️ 主人**没点名** ⇒ 仍只是**推断**；"
                     "🔺 **跨刀呼应**：它正是 R-H384 那节 **4.1 的标题**"
                     "（『工具清单 → 能力位映射』）⇒ **并排记、不硬配**；🔴 **不落表**"),
     "note": "📌 **已在**盘上：本仓 `PRIMITIVES` 的**第 3 条**（逐字 `MAP`）"
             "⇒ **顺位一致**（3/4）；🔺 **R-H388**：主人给了它的**介绍**（见 `detail`）；"
             "⚠️ 同族：原语名**不许塞进再现区**"},
    {"at": "R-H388", "name": "VERIFY",
     "note": "📌 **已在**盘上：本仓 `PRIMITIVES` 的**第 4 条**（逐字 `VERIFY`）"
             "⇒ **顺位一致**（4/4）；📌 **读数：四原语全部到齐（4/4）**"
             "—— ⚠️ **到齐 ≠ 许可**（不合并、不落表、不擅自当成「技能已定义完」）；"
             "🔸 它的介绍**还没到** ⇒ **一个字都没替它编**"},
)
FUSION_PRIMITIVES_NOTE = (
    "**原语区（R-H385/R386 · 主人逐字）**：4.2『蒸馏为技能：awesome_tools_index』下面的原语，"
    "**逐个**登记；🔴 每条都必须**真的在本仓 `PRIMITIVES` 里**（不许编）；"
    "🔴 **碎片不许当原语**（碎片是「没说完」，原语是**盘上已有的四原语**）；"
    "🔴 一条都不许落进任何表。"
)


def _known_rules() -> tuple:
    """现扫**本模块源码**里所有 `"rule": "..."` ⇒ 牙名的真表（不给手写留空子）。"""
    import re as _re
    src = _re.sub(r"\\r\\n", "\\n", open(__file__, encoding="utf-8-sig", errors="replace").read())
    return tuple(sorted(set(_re.findall(r'"rule":\s*"([a-z0-9_]+)"', src))))


# 🔴 R-H395：**重合读数自己的模板句**要先排除 —— 否则「并排记」「等主人补全」这些
#    我两处都写的**固定用语**会被当成重合（上一刀实测：50+ 片段 ⇒ 噪音淹没信号）。
OVERLAP_IGNORE = ("并排记", "等主人补全", "一个字都不编", "未到齐", "重合", "不合并",
                  "止于", "内容", "读数", "主人")


def _overlap_longest(it, items, min_len: int = 4) -> str:
    """两条未到齐输入之间的**最长**逐字重合（≥4 字）——读数用，**不许当同一个**。

    ⚠️ 收窄两次：① 排除**我自己的模板句**（OVERLAP_IGNORE）② 只留**最长的一条**
    （上一刀返回 50+ 片段 ⇒ 那个读数**没法用**）。
    """
    # 🔴 R-H396 口径收窄（兑现上一刀的承诺）：**只在 `got` 上算** ——
    #    `note` 是**我自己写的模板**（两条都用同一套话）⇒ 拿它算重合，剪出来的全是模板碎片。
    mine = str(it.get("verbatim") or "")
    best = ""
    for other in items:
        if other is it:
            continue
        theirs = str(other.get("verbatim") or "")
        for _n in range(len(mine) - min_len + 1):
            for _m in range(min_len, len(mine) - _n + 1):
                frag = mine[_n:_n + _m]
                if frag not in theirs:
                    break
                if any(w in frag for w in OVERLAP_IGNORE):
                    break
                if len(frag) > len(best):
                    best = frag
    return best


def _re_cells() -> list:
    """现算那张表到货的**层格**（L1 / L2 …）——⚠️ 一格不成行，**仍算未到齐**。"""
    import re as _re
    _seen = []
    for _it in INCOMING_DISTILLS:
        for _m in _re.findall(r"L\d+", str(_it.get("verbatim") or "")):
            if _m not in _seen:
                _seen.append(_m)
    return _seen


def _re_layers() -> list:
    """现算「第N层：」到货几次（读数 · 到齐 ≠ 许可）。"""
    import re as _re
    _seen = []
    for _it in INCOMING_DISTILLS:
        for _m in _re.findall(r"第[一二三四五六七八九十]+层：([^|\n]+)", str(_it.get("verbatim") or "")):
            _s = _m.strip()
            if _s and _s not in _seen:
                _seen.append(_s)
    return _seen


def check_incoming_distills() -> dict:
    """闸㉔（R-H393）：**未到齐的输入** —— 必须写明未到齐 + 必须带盘上取证读数 + 不许落表。"""
    items = list(INCOMING_DISTILLS)
    if not items:
        return {"ok": False, "denied": True, "rule": "incoming_empty",
                "why": "没有未到齐的输入也**不许空样本按绿**（确无请显式记一条「无」）"}
    out = []
    for it in items:
        topic = str(it.get("topic") or "").strip()
        got = str(it.get("got") or "")
        note = str(it.get("note") or "")
        chk = str(it.get("disk_check") or "")
        if not topic:
            return {"ok": False, "denied": True, "rule": "incoming_incomplete",
                    "why": "要写明**是哪件事**"}
        if ("未到齐" not in got and "未到齐" not in note
                and "止于" not in got and "截断" not in note):
            return {"ok": False, "denied": True, "rule": "incoming_gap_unstated",
                    "topic": topic,
                    "why": "未到齐的输入必须写明「**未到齐 / 止于 / 截断**」"}
        if "=>" not in chk:
            return {"ok": False, "denied": True, "rule": "incoming_without_disk_check",
                    "topic": topic,
                    "why": "必须带**盘上取证读数**（命令 => 读数）—— 不许凭印象说「盘上没有」"}
        if _overlap_longest(it, items) and not any(
                w in (got + note) for w in ("重发", "续写", "重合")):
            return {"ok": False, "denied": True, "rule": "incoming_overlap_unstated",
                    "topic": topic, "overlap": _overlap_longest(it, items),
                    "why": "与另一条未到齐输入**逐字重合** ⇒ 必须写明「重发 / 续写 / 重合」"
                           "（**重合 ≠ 同一个**，但要摆出来）"}
        if topic in [str(r.get("category") or "") for r in CATEGORY_ROWS_OWNER]:
            return {"ok": False, "denied": True, "rule": "incoming_landed",
                    "topic": topic, "why": "未到齐的输入**不许落进分类表**"}
        out.append({"topic": topic, "at": it.get("at"), "got": got,
                    "verbatim": str(it.get("verbatim") or ""),
                    # 🆕 R-H410：**说明/别名**也要带出来（判据/用例读它，就得带）
                    "alias_notes": [str(_a) for _a in (it.get("alias_notes") or ())],
                    "disk_check": chk, "note": note})
    _layers = _re_layers()
    _cells = _re_cells()
    # 🔴 R-H431：**两套五层名并排对照**（表那套 vs 框图那套）—— ⚠️ 结果只作读数，不合并
    _tbl = [str(_c) for _it in items for _r in (_it.get("rows") or ()) for _c in [_r[1] if len(_r) > 1 else ""]]
    _frm = [str(_r[1]) for _it in items for _r in (_it.get("frame_layers") or ())]
    _diff = []
    for _i, (_a, _b) in enumerate(zip(_tbl, _frm), 1):
        _diff.append({"L%d" % _i: "逐字一致" if _a == _b else "一字之差（表：%s ↔ 框图：%s）" % (_a, _b)})
    for _it in items:
        _vb = str(_it.get("verbatim") or "")
        for _r in (_it.get("frame_layers") or ()):
            for _c in _r:
                if str(_c) and str(_c) not in _vb:
                    return {"ok": False, "denied": True, "rule": "frame_layer_unverified",
                            "cell": str(_c), "why": "框图登记的格**在 verbatim 里找不到** ⇒ 不许编"}

    for _it in items:
        _vb = str(_it.get("verbatim") or "")
        _cells_all = list(_it.get("row1") or ())
        for _row in (_it.get("rows") or ()):
            _cells_all += [str(_c) for _c in (_row or ())]
        for _c in _cells_all:
            if str(_c) and str(_c) not in _vb:
                return {"ok": False, "denied": True,
                        "rule": "incoming_row1_unverified", "cell": str(_c),
                        "why": "登记的第一行格**在 verbatim 里找不到** ⇒ 不许编格值"}

    _ov = {str(x["topic"]): _overlap_longest(x, items) for x in items}
    _ov = {k: v for k, v in _ov.items() if v}
    return {"ok": True, "readonly": True, "items": out, "count": len(out),
            "layers": _layers, "layers_complete": len(_layers) >= 3,
            "cells": _cells, "cells_of": 5,
            "frame_layers": [[str(_c) for _c in _r] for _it in items for _r in (_it.get("frame_layers") or ())],
            "frame_layers_complete": len([_r for _it in items for _r in (_it.get("frame_layers") or ())]) == 5,
            "layer_name_diff": _diff,
            "matrix_rows": [[str(_c) for _c in (_r or ())] for _it in items for _r in (_it.get("matrix_rows") or ())],
            "matrix_cells": len([_c for _it in items for _r in (_it.get("matrix_rows") or ()) for _c in _r if _c]),
            "matrix_note": "🔸 3.4 矩阵：**行数未知**（主人没给总数）⇒ 只记「到货几格 / 有无成行」",
            "row1": [str(_c) for _it in items for _c in (_it.get("row1") or ())],
            "row1_of": 3,
            "rows": [[str(_c) for _c in (_r or ())] for _it in items for _r in (_it.get("rows") or ())],
            "rows_of": 5,
            "rows_complete_rows": len([1 for _it in items for _r in (_it.get("rows") or ())
                                       if len([_c for _c in (_r or ()) if _c]) >= 3]),
            # 🆕 R-H418：**表到齐读数**（现算）· 🔴 **齐 ≠ 许可**（仍不落表）
            "table_complete": (len([1 for _it in items for _r in (_it.get("rows") or ())
                                    if len([_c for _c in (_r or ()) if _c]) >= 3]) >= 5),
            "table_note": "🔴 **表齐 ≠ 许可**：到齐只说明主人把五层都给了 ⇒ 仍**不落表**、内容不编",
            "row1_complete": len([str(_c) for _it in items for _c in (_it.get("row1") or ())]) >= 3,
            "row1_note": "⚠️ **一行成行 ≠ 表完成**（L2-L5 还没到）⇒ 仍不落表",
            "cells_note": "那张表到货的**层格**（L 编号）· ⚠️ **一格不成行**（表头三列 + 至少一格才算一行）",
            "overlap": _ov, "note": INCOMING_DISTILLS_NOTE}


def check_fusion_cases() -> dict:
    """闸㉓（R-H390）：4.3 用例 —— 必须带**真出处** + 不许落表 + 到齐读数。"""
    items = list(FUSION_CASES)
    if not items:
        return {"ok": False, "denied": True, "rule": "fusion_cases_empty",
                "why": "一条用例都没有 ⇒ **空样本不按绿**"}
    known = ["PRIMITIVES:%s" % p["key"] for p in PRIMITIVES]
    out = []
    for it in items:
        text = str(it.get("text") or "").strip()
        tag = str(it.get("from") or "").strip()
        cc = str(it.get("crosscheck") or "")
        if not text:
            return {"ok": False, "denied": True, "rule": "fusion_case_incomplete",
                    "why": "用例要写明**是哪一条**"}
        if not tag:
            return {"ok": False, "denied": True, "rule": "fusion_case_without_from",
                    "text": text, "why": "用例**不许裸登记** ⇒ 必须写出处标签"}
        if tag not in known:
            return {"ok": False, "denied": True, "rule": "fusion_case_from_unknown",
                    "text": text, "from": tag, "known": known,
                    "why": "出处标签**在盘上找不到**（不许编出处）"}
        if "对应" not in cc and "对得上" not in cc:
            return {"ok": False, "denied": True, "rule": "fusion_case_crosscheck_unstated",
                    "text": text, "why": "每条都要写**与盘上对照**（不许沉默）"}
        if text in [str(r.get("category") or "") for r in CATEGORY_ROWS_OWNER]:
            return {"ok": False, "denied": True, "rule": "fusion_case_landed",
                    "text": text, "why": "用例**落进了分类表** ⇒ 它是图纸，不是分类名"}
        _teeth = [str(x) for x in (it.get("teeth") or ())]
        _known = _known_rules()
        for _t in _teeth:
            if _t not in _known:
                return {"ok": False, "denied": True, "rule": "fusion_case_teeth_unknown",
                        "text": text, "teeth": _t,
                        "why": "声明的牙**在模块里找不到**（不许编牙名）"}
        out.append({"no": it.get("no"), "text": text, "from": tag, "crosscheck": cc,
                    "teeth": _teeth, "teeth_note": it.get("teeth_note")})
    _n = len(out)
    return {"ok": True, "readonly": True, "items": out, "count": _n,
            "progress": {"given": _n, "of": 3, "complete": _n == 3},
            # 🆕 R-H391：**哪几条用例已经有牙**（读数 · 现算不手写）
            "with_teeth": [x["text"] for x in out if x["teeth"]],
            "note": FUSION_CASES_NOTE}


def check_fusion_sections() -> dict:
    """闸㉒（R-H389）：设计稿**小节** —— 编号递增不重 + 不许落表。"""
    items = list(FUSION_SECTIONS)
    if not items:
        return {"ok": False, "denied": True, "rule": "fusion_sections_empty",
                "why": "一个小节都没有 ⇒ **空样本不按绿**"}
    seen, last = [], ""
    for it in items:
        no = str(it.get("no") or "").strip()
        title = str(it.get("title") or "").strip()
        if not no or not title:
            return {"ok": False, "denied": True, "rule": "fusion_section_incomplete",
                    "no": no, "why": "小节要写明**编号**与**标题**"}
        if no in seen:
            return {"ok": False, "denied": True, "rule": "fusion_section_duplicate",
                    "no": no, "why": "同一个编号登记了两遍 ⇒ 计数会虚高"}
        if last and no <= last:
            return {"ok": False, "denied": True, "rule": "fusion_section_out_of_order",
                    "no": no, "after": last, "why": "小节编号必须**递增**（不许倒着登记）"}
        seen.append(no); last = no
        if title in [str(r.get("category") or "") for r in CATEGORY_ROWS_OWNER]:
            return {"ok": False, "denied": True, "rule": "fusion_section_landed",
                    "no": no, "why": "小节标题**落进了分类表** ⇒ 它是设计稿，不是分类名"}
    return {"ok": True, "readonly": True, "count": len(items),
            "items": [dict(x) for x in items],
            "nos": [str(x["no"]) for x in items], "note": FUSION_SECTIONS_NOTE}


def check_fusion_primitives() -> dict:
    """闸㉑（R-H385）：**4.2 原语** —— 必须真的在本仓 PRIMITIVES 里 + 不许落表 + 碎片不算。"""
    items = list(FUSION_PRIMITIVES)
    if not items:
        return {"ok": False, "denied": True, "rule": "fusion_primitives_empty",
                "why": "一条原语都没有 ⇒ **空样本不按绿**"}
    for _it in items:
        _d = str(_it.get("detail") or "").strip()
        if _d and not str(_it.get("detail_round") or "").strip():
            return {"ok": False, "denied": True,
                    "rule": "fusion_primitive_detail_without_round", "name": _it.get("name"),
                    "why": "挂了介绍，却说不出是**哪一轮**给的 ⇒ 与「有值的格必须有出处」同族"}
    _seen_names = []
    for _x in items:
        _n = str(_x.get("name") or "").strip()
        if _n and _n in _seen_names:
            return {"ok": False, "denied": True, "rule": "fusion_primitive_duplicate",
                    "name": _n, "why": "同一个原语登记了两遍 ⇒ 计数会虚高（一个名字一条）"}
        _seen_names.append(_n)
    frag_tokens = [str(x.get("token") or "") for x in TRUNCATED_FRAGMENTS]
    known = [str(p.get("key") or "") for p in PRIMITIVES]
    out = []
    for it in items:
        name = str(it.get("name") or "").strip()
        if not name:
            return {"ok": False, "denied": True, "rule": "fusion_primitive_incomplete",
                    "why": "原语要写明**是哪个**"}
        # ① 碎片不许当原语（没说完 ≠ 原语）
        if name in frag_tokens:
            return {"ok": False, "denied": True, "rule": "fusion_primitive_is_fragment",
                    "name": name,
                    "why": "这是**碎片**（没说完）⇒ **不许当原语**（原语只认盘上那几条）"}
        # ② 必须真的在本仓 PRIMITIVES 里
        if name not in known:
            return {"ok": False, "denied": True, "rule": "fusion_primitive_unknown",
                    "name": name, "known": known,
                    "why": "本仓 `PRIMITIVES` 里没有这一条 ⇒ 不许编原语"}
        # ③ 一条都不许落表
        landed = [str(r.get("category") or "") for r in CATEGORY_ROWS_OWNER
                  if name == str(r.get("category") or "")]
        if landed:
            return {"ok": False, "denied": True, "rule": "fusion_primitive_landed",
                    "name": name, "where": landed,
                    "why": "原语**落进了分类表** ⇒ 它是技能原语，不是分类名"}
        out.append({"name": name, "at": it.get("at"), "detail": it.get("detail"),
                    "detail_round": it.get("detail_round"),
                    "order": known.index(name) + 1, "of": len(known),
                    "note": str(it.get("note") or "")})
    _given = [x["name"] for x in out]
    _same = _given == known[:len(_given)]
    return {"ok": True, "readonly": True, "items": out, "count": len(out),
            "known": known, "given": _given, "order_same": _same,
            "with_detail": [x["name"] for x in out if x.get("detail")],
            # 🆕 R-H388：**到齐读数**（派生 · 现算不手写）—— 到齐 ≠ 许可
            "progress": {"given": len(out), "of": len(known),
                         "complete": [x["name"] for x in out] == known[:len(out)]
                         and len(out) == len(known)},
            "detail_rounds": {x["name"]: x.get("detail_round") for x in out if x.get("detail")},
            "note": FUSION_PRIMITIVES_NOTE}


FUSION_KIND_MAP = {1: ("逐字", "对应"), 2: ("逐字", "呼应"),
                   3: ("逐字", "一字之差"), 4: ("逐字", "前缀"),
                   5: ("逐字", "逐字"), 6: ("对应", "呼应"), 7: ("逐字", "呼应")}


def check_fusion_rows() -> dict:
    """闸⑳（R-H384）：**融合设计映射** —— 逐字登记 + 逐条对照 + 不许落表。"""
    items = list(FUSION_ROWS)
    if not items:
        return {"ok": False, "denied": True, "rule": "fusion_rows_empty",
                "why": "一条映射都没有：要么没登记，要么全清了 ⇒ **空样本不按绿**"}
    surfaces = _fusion_surfaces()
    out = []
    for it in items:
        left = str(it.get("left") or "").strip()
        right = str(it.get("right") or "").strip()
        cc = str(it.get("crosscheck") or "")
        if not left or not right:
            return {"ok": False, "denied": True, "rule": "fusion_row_incomplete",
                    "no": it.get("no"), "why": "每条映射都要写清**左边是什么 / 右边是什么**"}
        # ① 对照不许沉默（🔴 同刀修正：改成**字段**判，不再看散文）
        if not cc.strip():
            return {"ok": False, "denied": True, "rule": "fusion_row_without_crosscheck",
                    "no": it.get("no"), "left": left, "right": right,
                    "why": "每条都要写**与盘上对照**（不许沉默）"}
        _kinds = FUSION_KIND_MAP.get(it.get("no"))
        if not _kinds:
            return {"ok": False, "denied": True, "rule": "fusion_row_kind_missing",
                    "no": it.get("no"),
                    "why": "每条都要在 `FUSION_KIND_MAP` 里写明**左右各是哪种对照**"
                           "（%s）" % " / ".join(FUSION_KINDS)}
        for _k in _kinds:
            if _k not in FUSION_KINDS:
                return {"ok": False, "denied": True, "rule": "fusion_row_kind_unknown",
                        "no": it.get("no"), "value": _k,
                        "why": "对照形态只能是 %s 之一" % " / ".join(FUSION_KINDS)}
        # ② 标签必须真的存在（不许编出处）
        for _side, _tag in (("left", it.get("left_from")), ("right", it.get("right_from"))):
            if not _fusion_tag_ok(str(_tag or "")):
                return {"ok": False, "denied": True,
                        "rule": "fusion_row_from_unknown", "no": it.get("no"),
                        "side": _side, "from": str(_tag or ""),
                        "why": "出处标签**在盘上找不到**（不许编出处）"
                               "—— 可用：分类表第N行 / 旧批分类名 / 再现区:X / "
                               "KEY_TOOLS:X / 顺序读数:X"}
        # ③ 按 kind **逐边**校验：逐字 / 前缀 / 一字之差都要真的对得上
        #    （「对应 / 呼应」是**关系**，不做字符串校验 —— 不假装校过）
        for _side, _txt, _kind, _tag in (
                ("left", left, _kinds[0], str(it.get("left_from") or "")),
                ("right", right, _kinds[1], str(it.get("right_from") or ""))):
            if _kind in ("逐字", "前缀", "一字之差") and not _fusion_verify(
                    _kind, _txt, _tag, surfaces):
                return {"ok": False, "denied": True,
                        "rule": "fusion_row_crosscheck_unverified",
                        "no": it.get("no"), "side": _side, "kind": _kind,
                        "text": _txt, "from": _tag,
                        "why": "这条声称「%s」，可**在那个出处里对不上** ⇒ 对照是编的" % _kind}
        # ④ 一条都不许落表
        #    🔴 R-H384 同刀修正 2：第一版把**出处面**（KEY_TOOLS / 再现区 / 顺序读数）
        #    也算成「表」⇒ 第 5 条右边与 `owner_use` **逐字一致**（那本来就是**出处**）
        #    被误判成「落表」⇒ 只扫**表 / 名单**的面。
        #    🔴 同刀修正 3：用**包含**判（格值是多段拼起来的 ⇒ 相等判不出来）
        landed = [name for name, val in surfaces.items()
                  if (name.startswith("分类表第") or name == "旧批分类名")
                  and right in str(val)]
        if landed:
            return {"ok": False, "denied": True, "rule": "fusion_row_landed",
                    "no": it.get("no"), "where": landed,
                    "why": "映射**落进了表**（它是设计稿，不是表数据）⇒ 一个字都不许落"}
        out.append({"no": it.get("no"), "left": left, "right": right,
                    "left_from": it.get("left_from"), "right_from": it.get("right_from"),
                    "crosscheck": cc})
    return {"ok": True, "readonly": True, "items": out, "count": len(out),
            "kinds": list(FUSION_KINDS),
            # 🆕 R-H384：每条左右的对照形态**随条目带出来**（判据读它，就得带）
            "kind_map": {str(k): list(v) for k, v in FUSION_KIND_MAP.items()},
            "note": FUSION_ROWS_NOTE}


def _fusion_verify(kind: str, text: str, tag: str, surfaces: dict) -> bool:
    """按 kind 逐边校验（**只认字段，不读散文**）。"""
    val = surfaces.get(tag, "")
    if kind == "逐字":
        return bool(val) and text in val
    if kind == "前缀":
        return bool(val) and val.startswith(text)
    if kind == "一字之差":
        return any((text[:_i] + text[_i + 1:]) in val for _i in range(len(text)))
    return True


def _fusion_label_known(tag: str) -> bool:
    return tag.startswith("KEY_TOOLS:") or tag.startswith("再现区:") \
        or tag.startswith("顺序读数:") or tag.startswith("分类表第")


def _fusion_tag_ok(tag: str) -> bool:
    if tag in ("旧批分类名",):
        return True
    if tag.startswith("分类表第") and tag.endswith("行"):
        try:
            _i = int(tag[len("分类表第"):-1])
        except ValueError:
            return False
        return 1 <= _i <= len(CATEGORY_ROWS_OWNER)
    if tag.startswith("KEY_TOOLS:"):
        return tag.split(":", 1)[1] in [t["name"] for t in KEY_TOOLS]
    if tag.startswith("再现区:"):
        return tag.split(":", 1)[1] in [t["token"] for t in REAPPEARING_TOKENS]
    if tag.startswith("顺序读数:"):
        return tag.split(":", 1)[1] in [t["category"] for t in SOURCE_ORDER_READINGS]
    return False


def _fusion_surfaces() -> dict:
    surfaces = {"旧批分类名": " / ".join(CATEGORIES_OWNER)}
    for _i, _r in enumerate(CATEGORY_ROWS_OWNER, 1):
        surfaces["分类表第%d行" % _i] = " / ".join(
            [str(_r.get("category") or "")] + [str(_v or "")
                                             for _v in dict(_r.get("cells") or {}).values()])
    for _t in KEY_TOOLS:
        surfaces["KEY_TOOLS:%s" % _t["name"]] = str(_t.get("owner_use") or "")
    for _t in REAPPEARING_TOKENS:
        surfaces["再现区:%s" % _t["token"]] = str(_t.get("token") or "")
    for _t in SOURCE_ORDER_READINGS:
        surfaces["顺序读数:%s" % _t["category"]] = " / ".join(
            [str(_t.get("category") or ""), str(_t.get("paren") or ""),
             str(_t.get("near_row") or "")])
    return surfaces


# 🔴 R-H334：主人消息在『工具』处断掉 ⇒ **留空不编**（截断 ≠ 待归属：截断是「没说完」）
TRUNCATED_FRAGMENTS = (
    {"token": "工具", "kind": "truncated",
     "at": "R-H334 · R-H346 · R-H352 · R-H363 · R-H369 · R-H377 · R-H381",
     "ctx": "（消息在『工具』处断掉，疑是『工具名』列名的前半截，或某个工具名的开头）",
     "note": "**留空不编**：截断碎片**不许当数据**（不许当列名、不许当分类名、不许当格值）⇒ "
             "**等主人补全**；它与「待归属区」不同 —— 待归属是**说完了但没说挂哪**，"
             "截断是**没说完**，两件事不许混；"
             "🔺 **R-H346**：它**第二次出现**（紧跟在**带编号的分类头**之后）⇒ "
             "**仍留空不编**（两次都是**没说完**）；"
             "🔺 **R-H352 第三次出现**（又紧跟在一个**带编号的分类头**之后）⇒ "
             "**仍留空不编**；"
             "🔺 **R-H363 第四次出现**（**第四次**都在带编号的分类头之后）⇒ "
             "**仍留空不编** —— 四次位置**完全一致** ⇒ "
             "**更像「源仓库每分类下的表头 / 字段名」**，但**仍不编**；"
             "🔺 **R-H369 第五次出现**（**五次**都在带编号的分类头之后）⇒ "
             "**仍留空不编**（五次一致**也只是读数**：位置像不等于它就是表头）；"
             "**更像「源仓库每分类下的表头 / 字段名」**，但**仍不编**（没说完就是没说完）；"
             "🔺 **R-H377 第六次出现**（**六次**都在带编号的分类头之后）⇒ "
             "**仍留空不编** —— ⚠️ 六次一致**仍然只是读数**："
             "**位置像不等于它就是表头**（「像但不等于」族）；"
             "🔴 也**不许**因为「六次都一样」就把它**当数据**用（没说完就是没说完）"
             "—— 处理它只有两种：**主人补全** / **主人撤回**；"
             "🔺 **R-H381 第七次出现**（**七次**都在带编号的分类头之后）⇒ "
             "**仍留空不编** —— ⚠️ 七次一致**仍然只是读数**（位置像 ≠ 就是表头）", },
    {"token": "原语", "kind": "truncated", "at": "R-H384",
     "ctx": "（紧跟『4.2 蒸馏为技能：awesome_tools_index』之后 ⇒ 疑是「原语」列表的开头）",
     "note": "**留空不编**：它**紧跟一个带编号的小节标题**（4.2）之后，"
             "疑是**小节内容的开场词**（本仓 PRIMITIVES 就叫「四原语」）"
             "—— ⚠️ 但**位置像 ≠ 就是** ⇒ **没说完就是没说完**；"
             "🔴 不许拿它当分类名 / 列名 / 格值；🔺 **等主人补全**", },
    {"token": "工程哲学", "kind": "truncated", "at": "R-H394",
     "ctx": "（孤立一词；上一段止于『层级』，而上一段里恰好有『三层工程哲学』⇒ 逐字重合）",
     "note": "**留空不编**：它**不是一个完整输入**（孤立短语）⇒ 与『层级』同段；"
             "🔺 与上一段的『三层工程哲学』**逐字重合** ⇒ 可能是重发/续写 ⇒ **并排记、不合并**；"
             "🔴 不许拿它当分类名 / 列名 / 格值；🔺 **等主人补全**"},
    {"token": "层级", "header": True, "kind": "truncated", "at": "R-H393 · R-H401",
     "ctx": "（主人那段 TeamoRouter 蒸馏**止于此**：『一、核心能力蒸馏：三层工程哲学』下面的『层级』）",
     "note": "**留空不编**：它不是「一个词没说完」，而是**整段输入到此为止**"
             "（后面本该有「层级」表/列表）⇒ **内容一个字都不编**；"
             "🔴 不许拿它当分类名 / 列名 / 格值；🔺 **等主人补全**；"
             "🔺 **R-H401 第二次出现**（第二节又**止于**同一个表头）⇒ **仍留空不编**"
             "（**两次同位置也不能当它是数据**）"},
    {"token": "核心职责", "header": True, "kind": "truncated", "at": "R-H403",
     "ctx": "（紧接『层级』『名称』之后 ⇒ 形态：那张表的**第三列列名**）",
     "note": "**留空不编**：表头/列名残片（不是内容）—— "
             "🔴 对照两个既有列契约（第二节 2 列 · 源表 3 列）⇒ **都不含『核心职责』** "
             "⇒ 不许拿它当任何表的列名；"
             "📌 读数：那张表的**列名在逐个到货**（层级 → 名称 → **核心职责**）"
             "（见 `header_fragments`）⇒ **仍不编**；🔺 **等主人补全**"},
    {"token": "推荐能源", "header": True, "kind": "truncated", "at": "R-H433",
     "ctx": "（紧跟『复杂度』之后 ⇒ 形态：3.4 矩阵表的**第三个列名**）",
     "note": "**留空不编**：表头/列名残片（**第六个**）—— 🔴 不是本仓任何既有列契约里的列名 "
             "⇒ 不许当列名；🔸 与盘上『**能源池**』（本仓既有概念）**语义同向** "
             "⇒ **呼应、不许当同一个**；🔸 疑是 3.4 矩阵的第三列；🔺 **等主人补全**"},
    {"token": "复杂度", "header": True, "kind": "truncated", "at": "R-H432",
     "ctx": "（紧跟『任务类型』之后 ⇒ 形态：3.4 矩阵表的**第二个列名**）",
     "note": "**留空不编**：表头/列名残片（**第五个**）—— 🔴 不是本仓任何既有列契约里的列名 "
             "⇒ 不许当列名；🔸 疑是 3.4 矩阵的第二列；🔺 **等主人补全**"},
    {"token": "任务类型", "header": True, "kind": "truncated", "at": "R-H431",
     "ctx": "（紧跟『3.4 路由决策矩阵（结合我们的能源池）』之后 ⇒ 形态：那张矩阵表的**第一个列名**）",
     "note": "**留空不编**：表头/列名残片（**第四个**）—— 🔴 不是本仓任何既有列契约里的列名 "
             "⇒ 不许当列名；🔸 疑是 **3.4 矩阵**的列；🔺 **等主人补全**"},
    {"token": "预设", "header": True, "kind": "truncated", "at": "R-H419",
     "ctx": "（紧跟『3.2 三层路由预设（照抄 TeamoRouter 的命名逻辑）』之后 ⇒ 形态：那张小表的**表头/列名**）",
     "note": "**留空不编**：表头/列名残片（**第三个**：层级 / 名称 / 核心职责 → **预设**）—— "
             "🔴 对照：它**不是**本仓任何既有列契约里的列名（第二节 2 列 · 源表 3 列 · 都无）"
             "⇒ 不许拿它当列名；🔸 疑是 **3.2 那张新表**的列；🔺 **等主人补全**"},
    {"token": "名称", "header": True, "kind": "truncated", "at": "R-H402",
     "ctx": "（紧跟『层级』之后 ⇒ 形态：那张表的**第二列列名**）",
     "note": "**留空不编**：它是**表头/列名残片**（不是内容）—— "
             "🔴 对照本仓**两个既有列契约**：① 第二节『代表工具 / 对应 GBT 能力域』"
             "② 源表『工具名 / 详细介绍 / 下载地址』⇒ **两个都不含『名称』**"
             "⇒ 不许拿它当**任何**表的列名；"
             "🔸 读数：疑是**第三个表**（『层级 | 名称 | …』）的列名；🔺 **等主人补全**"},
    {"token": "用例", "kind": "truncated", "at": "R-H389",
     "ctx": "（紧跟『4.3 三条带牙用例』这个小节标题之后）",
     "note": "**留空不编**：它与『原语』**同型**（紧跟一个小节标题之后 ⇒ 疑是小节内容的开场词）"
             "—— ⚠️ 位置像 ≠ 就是 ⇒ **没说完就是没说完**；"
             "🔴 不许拿它当用例名 / 分类名 / 列名；🔺 **等主人补全**"},
    {"token": "text", "kind": "fence", "at": "R-H384 · R-H419",
     "ctx": "（夹在『4.1 工具清单 → 能力位映射』与那段树形映射之间）",
     "note": "🔺 **新形态：围栏语言标记残片**（不是「没说完」，是**格式残片**）—— "
             "它正是 Markdown 代码围栏的语言名（本仓文档里到处都是 ` ```text `）"
             "⇒ 强烈提示：主人那轮是**从一份 Markdown 里复制粘贴**的"
             "⚠️ 但**是不是我们自己的文档，未取证**（盘上这一段 **0 命中**）"
             "🔴 **留空不编**：格式残片**不许当数据**（不许当分类名 / 列名 / 格值）", },
)
# 🔴 R-H384：碎片**两种形态** —— `truncated`（没说完，等主人补全）/ `fence`（格式残片，
#    复制粘贴痕迹）⇒ 处理纪律不同，**不许混**（与 `local_row`/`near_row` 那些形态同族）
FRAGMENT_KINDS = ("truncated", "fence")
TRUNCATED_FRAGMENTS_NOTE = (
    "**截断碎片区**：主人消息被截断是常态 ⇒ 碎片单独登记 + **留空不编** + 等主人补全；"
    "⚠️ 比对只认**整串相等**：碎片多半是某个更长串的**前缀**（工具 ⊂ 工具名 ⊂ AI辅助编程工具），"
    "用包含比对会大面积误报 —— 判据要卡在真问题上"
)

# 🔴 R-H346：主人给了**源仓库的编号**（『2. AI 模型管理工具』）⇒ 立**顺序读数**（源编号 vs 本仓位置）
#    ⚠️ 读数 ≠ 许可：**不许拿源编号去重排本仓表**（顺序以主人为准，重排要主人一句话）
#    ⚠️ `our_index` **不手写** —— 由闸按当前表**现算**（表若被重排过，这条读数会当场红）
SOURCE_ORDER_READINGS = (
    {"category": "AI模型管理工具", "source_no": 2, "at": "R-H346",
     "note": ("源仓库**编号 = 2**；本仓它在**第 3 行** ⇒ **顺序不一致**"
              "（本仓第 1 行是『AI辅助编程工具』、第 2 行『AI实用效率工具』）⇒ "
              "**只记读数、不擅自重排**（重排要主人一句话）；"
              "⚠️ 括号词『自动切换核心』与本行『对应 GBT 能力域（模型路由 / 供应商切换）』"
              "**语义呼应**，但它**不是** R-H285 那批的分类名 ⇒ "
              "**不记跨批映射证据**（不硬凑）；"
              "🔺 **R-H381 补记（判定不改）**：源 7 那条（`source_no = 7`）"
              "与本条**只差一个空格**（主人给源 7 是**带空格**逐字"
              "『AI 模型管理工具』；本条当年存成了**无空格**写法 —— **是我吃掉了空格**）"
              "⇒ 两条是**同一个名字的两种写法** ⇒ **不许当同一个、也不许合并**；"
              "🔸 要不要把本条改成**逐字带空格** + 走「疑似对应」形态"
              "⇒ **等主人一句话**（改它会动到本条读数的键与措辞，不擅自动）"), },
    {"category": "AI短剧生成工具", "source_no": 3, "at": "R-H352",
     "note": ("源仓库**编号 = 3**；本仓它在**第 4 行** ⇒ **顺序不一致** ⇒ "
              "**只记读数、不擅自重排**（重排要主人一句话）；"
              "🔺 **括号词『视频创作流水线』恰好等于** R-H285 那批里的一条分类名 ⇒ "
              "**跨批对应（强证据）**——但 🔴 **仍不擅自合并**（谁作准待主人定）；"
              "⚠️ 与 R-H346 那条（括号词**不是**旧批分类名）**并排对照**，"
              "两条都只到读数为止"), },
    {"category": "智能体生态工具", "source_no": 4, "at": "R-H363",
     "local_row": None,
     "note": ("源仓库**编号 = 4**，名字 = 『智能体生态工具』；"
              "🔴 **本仓无此行** —— 本仓第 5 行是『实用画图工具』，"
              "**与源 4 不是同一个**（既不**同前缀**、也不同类）⇒ "
              "⚠️ **更重要的读数**：**源表分类序列与本仓分类序列不是「错位一格」，而是内容不同**"
              "⇒ 从此**不许**再把「源编号」直接当「本仓行号」用；"
              "🔴 **不一致**：源 4 **无对应行** ⇒ 只记读数、**不许重排、不许新增行**；"
              "🔺 括号核：『智能体生态工具』与 R-H285 那批的『智能体生态』"
              "**对应**（同前缀）但**不同尾** ⇒ **像但不等于、不许当同一个**"), },
    {"category": "文档与知识库工具", "source_no": 5, "at": "R-H369",
     "local_row": None,
     "near_row": "文档和知识库工具",
     "note": ("源仓库**编号 = 5**，名字 = 『文档与知识库工具』；"
              "⚠️ 本仓**没有这一行的逐字名**，但第 6 行是『文档**和**知识库工具』"
              "⇒ **一字之差**（『与』↔『和』）⇒ **疑似对应、但不许当同一个**；"
              "🔴 **不一致**：源名与本仓行名**不同** ⇒ "
              "**不许重排、不许新增行、🔴 更不许拿源名去改本仓行名**"
              "（本仓第 6 行仍叫『文档和知识库工具』）；"
              "🔺 括号核：『记忆层』**不是** R-H285 那批的分类名，"
              "但与本仓第 6 行的『对应 GBT 能力域（记忆层 / 知识库）』**语义呼应**"
              "⇒ 只记读数（**语义像 ≠ 就是**）"), },
    {"category": "网络加速工具", "source_no": 6, "at": "R-H377",
     "local_row": None,
     "paren": "环境优化",
     "near_names": ("GitHub 加速工具", "网络管理工具"),
     "note": ("源仓库**编号 = 6**，名字 = 『网络加速工具』（括号词『环境优化』）；"
              "🔴 **本仓无此行** —— 本仓第 7 行是『Markdown 编辑器』，"
              "**与源 6 不是同一个**（既不同前缀、也不同类）⇒ "
              "⚠️ **再印证一次**：源表分类序列与本仓分类序列**不是「错位一格」，而是内容不同**"
              "（与源 4 那次同型）⇒ 仍**不许**把「源编号」当「本仓行号」用；"
              "🔴 **不一致**：源 6 **无对应行** ⇒ 只记读数、**不许重排、不许新增行**；"
              "🔺 **括号核（真·括号词）**：『环境优化』**不是** R-H285 那批的分类名"
              "（那批里有个相近的『环境配置』⇒ 两字之差、像但不等于、**不许当同一个**）；"
              "🆕 **该记「对应」的是另一处**：**源名里的『网络加速』恰好等于**"
              "R-H285 那批的一条分类名 ⇒ **跨批对应（同前缀、不同尾）** —— "
              "这条「对应」是**给源名的**，**不是给括号词的**"
              "（本刀把两件事**分开写**，并让 `source_order_paren_audit` 把"
              "「到底是什么喂响了括号核」摆出来）；"
              "⚠️ 仍**只到读数为止**：不合并、不自解谁作准；"
              "🔸 **R-H378 追加 · 像但不等价的候选**（`near_names`）：本仓有**两处像**的行 —— "
              "第 10 行『GitHub 加速工具』（**主人刚给的名字『Watt Toolkit』正住在这里**）、"
              "第 22 行『网络管理工具』⇒ **像但不等于、不许当同一个**，也**不许硬配**"
              "（🔴 **无对应行就是无对应行**：判定仍是「不一致 / 本仓无此行」）"), },
    {"category": "AI 模型管理工具", "source_no": 7, "at": "R-H381",
     "local_row": None,
     "near_row": "AI模型管理工具",
     "note": ("源仓库**编号 = 7**，名字 = 『AI 模型管理工具』"
              "（⚠️ **逐字**：AI 与 模型 之间有**一个空格**）；"
              "⚠️ 本仓**没有这一行的逐字名**，但**第 3 行**是『AI模型管理工具』"
              "（**无空格**）⇒ **只差一个空格** ⇒ **疑似对应、但不许当同一个**"
              "（⚠️ 准确说是**一个空格之差**，**不是「一字之差」** —— 口径要写准）；"
              "🔴 **不一致**：源名与本仓行名**不同** ⇒ **不许重排、不许新增行、"
              "🔴 更不许拿源名去改本仓行名**（本仓第 3 行仍叫『AI模型管理工具』）；"
              "🔺 括号核：本条**没有括号词** ⇒ 只记**不是**旧批分类名"
              "（不许默认沉默）；"
              "🔴 **同刀自查（同源名再现）**：它与**源 2** 那条（`source_no = 2`）"
              "**只差一个空格** —— 源 2 那条**当年存成了无空格写法**"
              "（主人当时给的是**带空格**的逐字，**是我吃掉了空格**）"
              "⇒ 两条本质上是**同一个名字的两种写法** ⇒ "
              "**不许当同一个**、**也不许合并**（见 `duplicate_source_names`）；"
              "🔸 **不擅自改已关账那条**（源 2）：改它会动到那条读数的键与措辞"
              "⇒ **等主人一句话**（要不要把源 2 改成逐字带空格 + 走「疑似对应」形态）"), },
)
SOURCE_ORDER_READINGS_NOTE = (
    "**顺序读数区**：主人给的**源仓库编号**只当读数 —— 记下「源编号 vs 本仓位置」，"
    "**不一致就写明**；🔴 **不许拿编号去重排本仓表**（顺序以主人为准）。"
    "⚠️ 本区**双向带牙**：① 编号与位置不一致、却没写「不一致」⇒ 红；"
    "② 写了「不一致」、而盘上其实一致（表被人重排过）⇒ **也红**（旧读数不许留着装样子）"
)

# 🔴 R-H336：主人又给了一个**盘上已经有**的名字 ⇒ 记「再现」（不是新工具）
REAPPEARING_TOKENS = (
    {"token": "Trae", "at": "R-H336 · R-H337",
     "note": "**已在**盘上：第 1 行『AI辅助编程工具』的『代表工具』那串的**首位** ⇒ "
             "记为**再现**（**不是新工具**）；🔴 **不许另起一行、也不许当重复丢掉** ⇒ 并排记；"
             "⚠️ 同一个名字还**前缀命中**了待归属『IDE & 代码编辑器』的暂存值"
             "（『VS Code / Trae 等』里的『Trae 等』**整段不等**）⇒ **像但不等于**、两处并排；"
             "🔺 **R-H337 证据 +1**：主人又给了它的**详细介绍一句话**（见 staged_detail）"
             "⇒ 它更像**源表里的一行工具**（工具名 + 详细介绍两列都到过）；"
             "🔴 但**仍不擅自落表** —— 源表行的归属没经主人确认，只**暂存**",
     "staged_detail": "字节跳动，深度集成 Doubao-1.5-pro 与 DeepSeek，支持中文一键生成代码框架",
     "staged_detail_note": ("⏸ **暂存、不落表**：主人给的这句是『Trae』的详细介绍；"
                            "**归属依据** = **形态**（**紧跟其后**）—— 主人**没点名** ⇒ "
                            "这只是**推断**；"
                            "归属（进哪张表、哪一行）**没经主人确认** ⇒ "
                            "**一个字都不落进任何表**；🔴 也**不许把它当作『对应 GBT 能力域』**"
                            "（那是另一格），**等主人一句话**再落"), },
    {"token": "Fitten Code", "at": "R-H338 · R-H339",
     "note": "**已在**盘上：第 1 行『AI辅助编程工具』的『代表工具』那串的**第二个** ⇒ "
             "记为**再现**（**不是新工具**）；🔴 **不许另起一行、也不许当重复丢掉** ⇒ 并排记；"
             "🔺 **R-H338 读数**：这是**同一格里的名字被逐个再给**的**第二个**"
             "（前一个是 Trae）⇒ 疑似源仓库是「**一个工具一行**」；"
             "🔴 但**仍不定论、不拆行** —— 「一个格里的五个名字」现在仍是**一个格**；"
             "🔺 **R-H339 读数 +1**：主人又给了它的**详细介绍一句话**（见 staged_detail）"
             "⇒ **两个工具各自都带一句介绍**（Trae / Fitten Code）"
             "⇒ 更支持「一工具一行」；🔴 **仍不定论、仍不落表**",
     "staged_detail": "免费，支持 80+ 语言，自动生成代码、调试 Bug",
     "staged_detail_note": ("⏸ **暂存、不落表**：主人给的这句是『Fitten Code』的详细介绍；"
                            "**归属依据** = **形态**（**紧跟其后**）—— 主人**没点名** ⇒ "
                            "这只是**推断**；"
                            "归属（进哪张表、哪一行）**没经主人确认** ⇒ "
                            "**一个字都不落进任何表**；🔴 也**不许把它当作『对应 GBT 能力域』**"
                            "（那是另一格），**等主人一句话**再落"), },
    {"token": "CodeGeeX", "at": "R-H340",
     "note": "**已在**盘上：第 1 行『AI辅助编程工具』的『代表工具』那串的**第三个** ⇒ "
             "记为**再现**（**不是新工具**）；🔴 **不许另起一行、也不许当重复丢掉** ⇒ 并排记；"
             "🔺 **R-H340 读数**：同一格被**逐个再给**的**第三个**"
             "（Trae → Fitten Code → CodeGeeX）⇒ 仍**只是读数、不是定论**；"
             "🔴 那一格里的五个名字现在仍是**一个格**，不许拆行", },
    {"token": "通义灵码", "at": "R-H342",
     "note": "**已在**盘上：第 1 行『AI辅助编程工具』的『代表工具』那串的**第四个** ⇒ "
             "记为**再现**（**不是新工具**）；🔴 **不许另起一行、也不许当重复丢掉** ⇒ 并排记；"
             "🔺 **R-H342 读数**：同一格被**逐个再给**的**第四个**"
             "（Trae → Fitten Code → CodeGeeX → 通义灵码）⇒ 仍**只是读数、不是定论**；"
             "🔴 那一格里的五个名字现在仍是**一个格**，不许拆行", },
    {"token": "GitHub Copilot", "at": "R-H344",
     "note": "**已在**盘上：第 1 行『AI辅助编程工具』的『代表工具』那串的**第五个**（**末位**）⇒ "
             "记为**再现**（**不是新工具**）；🔴 **不许另起一行、也不许当重复丢掉** ⇒ 并排记；"
             "🔺 **R-H344 读数**：**那一格五个名字全部**被逐个再给"
             "（Trae → Fitten Code → CodeGeeX → 通义灵码 → GitHub Copilot）⇒ "
             "仍**只是读数、不是定论**；"
             "🔴 那一格仍是**一个格** —— 五个名字**全到**也**不等于**可以拆行", },
    {"token": "CC Switch", "at": "R-H348 · R-H382",
     "reappearance_times": 2,
     # 🔴 R-H383：介绍句的**骨架家族**（人工判定 + 写明依据）—— 它与它的变体
     #    `CC-Switch CLI` 的介绍句**同骨架**（都在说「管理 CLI 工具的供应商配置」）
     "detail_family": "cli_供应商配置",
     "note": "**已在**盘上：**第 3 行**『AI模型管理工具』的『代表工具』那串的**首位** ⇒ "
             "记为**再现**（**不是新工具**）；🔴 **不许另起一行、也不许当重复丢掉** ⇒ 并排记；"
             "🔺 **R-H348 读数**：这是**第一个不来自第 1 行**的再现 ⇒ "
             "**当场暴露旧读数的一处扩大化**（按**列名**分组会把第 1 行与第 3 行混成一组）"
             "⇒ 本刀把面名改成**带行号**（`第N行 格 X`）；"
             "⚠️ 它的同格伙伴正是它的**变体** `CC-Switch CLI`（差「空格 ↔ 连字符」+ 后缀 CLI）"
             "⇒ **像但不等于**、并排记；"
             "🔺 **R-H349**：主人给了它的一句**详细介绍**（见 staged_detail）"
             "⇒ 与 Trae / Fitten Code 同族（**紧跟工具名之后的介绍**）；"
             "🔺 **R-H382 补记（第二次投喂）**：主人**又一次**给了『CC Switch』—— "
             "它仍**已在**盘上（第 3 行首位）⇒ **不许另起一行、也不许当重复丢掉** ⇒ "
             "仍是**并排记**（🔴 **一个名字一条**：`reappearing_token_duplicate` 卡着，"
             "本轮**不新增条目**、**不落表**）；"
             "📌 **读数**：**同一个名字被投喂第二次**（R-H348 → **R-H382**）"
             "（见 `reappearance_repeat`）；"
             "⚠️ 第二次**不新增任何事实**：它的介绍仍是 R-H349 那句、"
             "📌 另一条读数：它其实是**两处来源**（第 3 行那格 + "
             "**我方 R-H285 工具名单**）⇒ 见 `where` 两项（同 CowAgent / OpenClaw Monitor）；"
             "同格伙伴仍是它的**变体** `CC-Switch CLI` ⇒ **像但不等于**、并排记；"
             "🔴 也**不许**把「又说了一遍」当成「主人确认了」"
             "（**重复 ≠ 许可**）",
     "staged_detail": "桌面应用，统一管理 Claude Code / Codex / Gemini CLI / OpenCode / OpenClaw 的供应商配置，内置 50+ 供应商预设，一键切换",
     "staged_detail_note": ("⏸ **暂存、不落表**：**归属依据** = **形态**"
                            "（**紧跟其后** + 语义吻合：它管的正是 CLI 供应商配置，与本行"
                            "『对应 GBT 能力域（模型路由 / 供应商切换）』正对）—— "
                            "⚠️ 但主人**没点名** ⇒ 这只是**推断**，不是判定；"
                            "🔸 **第二种读法并排**：也可能是一个**新工具**（「桌面应用」本身）的介绍；"
                            "**一个字都不落进任何表**；"
                            "🔴 也**不许把它当作『对应 GBT 能力域』**（那是另一格）；"
                            "🆕 **R-H383 同家族**：本条与它的**变体** `CC-Switch CLI`"
                            "的介绍句**同骨架**（都在说「管理 CLI 工具的供应商配置」）"
                            "⇒ 记**同骨架**（见 `detail_family`）、**不新增事实**；"
                            "🔺 **等主人一句话**再落"), },
    {"token": "CC-Switch CLI", "at": "R-H350 · R-H383",
     "reappearance_times": 2,
     "detail_position": "after_name",
     "detail_family": "cli_供应商配置",
     "staged_detail_extra": "桌面应用，管理 5 大 CLI 工具的供应商配置，一键切换",
     "staged_detail_extra_round": "R-H383",
     "note": "**已在**盘上：**第 3 行**『AI模型管理工具』的『代表工具』那串的**第二个** ⇒ "
             "记为**再现**（**不是新工具**）；🔴 **不许另起一行、也不许当重复丢掉** ⇒ 并排记；"
             "🔺 **变体**：它是 `CC Switch` 的**变体** —— "
             "**差「空格 ↔ 连字符」+ 后缀 CLI**（抹平后**前缀一致、整串更长**）⇒ "
             "**既不许当同一个、也不许当成另一个新工具**（两侧都错）；"
             "⚠️ 同格伙伴 = `CC Switch` ⇒ **像但不等于**、并排记；"
             "🔺 **R-H351**：主人给了它的一句**详细介绍**（见 staged_detail）"
             "⇒ 与 Trae / Fitten Code / CC Switch 同族；"
             "⚠️ 本句句头『命令行版』与主人**早前那条长消息**里的碎片『命令行版本』"
             "**同前缀、不同尾** ⇒ **并排记**（那条本刀已**追溯补登记**进待归位，**不硬配**）；"
             "🔺 **R-H383 补记（第二次投喂）**：主人**又一次**给了『CC-Switch CLI』"
             "（它仍**已在**盘上：第 3 行那格的**第二个**）⇒ **不许另起一行、也不许当重复丢掉**"
             "⇒ 仍是**并排记**（**一个名字一条**）⇒ **不新增条目**；"
             "📌 读数：**同一个名字被投喂第二次**（R-H350 → **R-H383**，见 `reappearance_repeat`）；"
             "🔺 **R-H383 第二句**：主人又给了它一句介绍（见 `staged_detail_extra`）——"
             "⚠️ 但**位置与语义打架**：位置（**在名字之前** ⇒ 按列序跟**它前面最近的名字**"
             "= 本条目）指向**它**，可句头『**桌面应用**』指向的却是 **CC Switch**"
             "（它是**变体**、桌面版 vs 命令行版）⇒ **如实写明冲突**、**不硬配**；"
             "🔸 **第二种读法并排**：整句属于 **CC Switch**（『桌面应用』+ 『一键切换』"
             "与 R-H349 那句的骨架也吻合）；"
             "🔴 **它不新增事实**：这是同一件事的**第三遍**表述"
             "（R-H349 → R-H351 → **R-H383**，三句**同骨架**：管理 CLI 工具的供应商配置）",
     "staged_detail": "命令行版，统一管理五大 CLI 工具的供应商配置",
     "staged_detail_note": ("⏸ **暂存、不落表**：**归属依据** = **形态**"
                            "（**紧跟其后** + 「命令行版」正好对上名字里的「CLI」）—— "
                            "⚠️ 但主人**没点名** ⇒ 这只是**推断**，不是判定；"
                            "🔸 **第二种读法并排**：也可能是**另一个 CLI 工具**（或新工具）的介绍；"
                            "**一个字都不落进任何表**；"
                            "🔴 也**不许把它当作『对应 GBT 能力域』**（那是另一格）；"
                            "🆕 **R-H383 第二句（并排 · 不覆盖）**：主人又给了它一句"
                            "📌 **位置读数 `after_name`**"
                            "（**位置读数：跟在名字之后**）—— "
                            "（见 `staged_detail_extra`）—— **第一句说「命令行版」、"
                            "第二句说「桌面应用」（且管理 5 大 CLI）** ⇒ 两句"
                            "**同骨架**（都在说「管理 CLI 工具的供应商配置」）"
                            "⇒ **并排记、不合并、不许覆盖第一句**、**不新增事实**；"
                            "⚠️ 仍**没点名** ⇒ 仍只是**推断**；"
                            "🔸 **第二读法并排**：这句也可能属于 **CC Switch**"
                            "（『桌面应用』那半句更像它）⇒ **不硬配**；"
                            "🔺 **等主人一句话**再落"), },
    {"token": "MoneyPrinterTurbo", "at": "R-H355",
     "note": "**已在**盘上：**第 4 行**『AI短剧生成工具』的『代表工具』**那一个** ⇒ "
             "记为**再现**（**不是新工具**）；🔴 **不许另起一行、也不许当重复丢掉** ⇒ 并排记；"
             "🔺 **R-H355 读数**：这是**第一个来自第 4 行**的再现"
             "（第 1 行 5 个 · 第 3 行 2 个 · 第 4 行 1 个）⇒ 该格**只有一个名字**、"
             "所以 `cell_mates` 为空（**这本身就是读数**）；"
             "🔺 它同时在我方 `KEY_TOOLS` 里（R-H285 那批）⇒ "
             "**重叠**已在第 4 行的 note 里写明（并排记、不合并）；"
             "🔺 **R-H356**：主人也给了它的一句**详细介绍**（见 staged_detail）"
             "⇒ 与 Trae / Fitten Code / CC Switch / CC-Switch CLI **同族**；"
             "📌 读数：**每个被逐个再给的工具后面都跟着一句介绍**"
             "（第 4 行这个也不例外）⇒ 支持「一工具一行」（**仍不定论**）",
     "staged_detail": "输入主题/关键词，全自动生成视频文案、素材、字幕、背景音乐，合成高清短视频",
     "staged_detail_note": ("⏸ **暂存、不落表**：**归属依据** = **形态**"
                            "（**紧跟其后** + 语义**完全对得上**：它就是这个功能）—— "
                            "⚠️ 但主人**没点名** ⇒ 这只是**推断**，不是判定；"
                            "🔸 **第二种读法并排**：也可能是**一个新工具**，"
                            "或**第 4 行那个分类的能力描述**；"
                            "**一个字都不落进任何表**；"
                            "🔴 也**不许把它当作『对应 GBT 能力域』**（那是另一格）；"
                            "🔺 **等主人一句话**再落"), },
    {"token": "Huobao Drama", "at": "R-H359",
     "note": "**已在**盘上：在**我方 R-H285 那批**（`KEY_TOOLS` 六条之一 · 映射 "
             "`video_pipeline`）⇒ 记为**再现**（**不是新工具**）；"
             "🔴 **不许另起一行、也不许当重复丢掉** ⇒ 并排记；"
             "📌 **读数**：它**不在任何分类行的格值里**（第 4 行只有 `MoneyPrinterTurbo`）⇒ "
             "**「源表格值」与「我方 R-H285 名单」是两处**，本刀把后者也**算作盘上来源**"
             "（面名 = `我方 R-H285 工具名单`）⇒ 从此**不会被误判成「找不到」**；"
             "⚠️ 两处**并排、不合并**（源表那处仍空着就是空着）；"
             "🔺 **R-H360**：主人给了它的一句**详细介绍**（见 staged_detail）"
             "⇒ 与 Trae / Fitten Code / CC Switch / CC-Switch CLI / MoneyPrinterTurbo 同族；"
             "📌 读数：**第 6 条「名字 → 紧接着一句介绍」**（本条的来源是**名单**而非行格）",
     "staged_detail": HUOBAO_DETAIL_R_H360,
     "staged_detail_note": ("⏸ **暂存、不落表**：**归属依据** = **形态**"
                            "（**紧跟其后** + 技术栈/全链路语义吻合：短剧全链路）—— "
                            "⚠️ 但主人**没点名** ⇒ 这只是**推断**，不是判定；"
                            "🔸 **第二种读法并排**：也可能是**另一个项目 / 新工具**的介绍，"
                            "或 R-H285 名单里**别的条目**的介绍；"
                            "**一个字都不落进任何表**；"
                            "🔴 也**不许把它当作『对应 GBT 能力域』**（那是另一格）；"
                            "🔺 **等主人一句话**再落"), },
    {"token": "LocalMiniDrama", "at": "R-H361",
     "note": "**已在**盘上：在**我方 R-H285 那批**（`KEY_TOOLS` 六条之一 · 映射 "
             "`video_pipeline`）⇒ 记为**再现**（**不是新工具**）；"
             "🔴 **不许另起一行、也不许当重复丢掉** ⇒ 并排记；"
             "📌 **读数**：R-H285 的**短剧三件套到齐** —— "
             "`MoneyPrinterTurbo`（**行来源**·第 4 行）· `Huobao Drama`（名单来源）· "
             "`LocalMiniDrama`（名单来源）⇒ 三件都到，但**只有一件在源表格值里**"
             "（**两处仍并排、不合并**）；"
             "🔺 **R-H362**：主人也给了它的一句**详细介绍**（见 staged_detail）"
             "⇒ **短剧三件套三句全齐**（MoneyPrinterTurbo / Huobao Drama / LocalMiniDrama）；"
             "📌 读数：本条除「**紧跟其后**」外还有**名字词义呼应**"
             "（名字里的 `Local` ↔ 句里的「本地 / 数据不出本机 / 无订阅费」）",
     "staged_detail": "本地 AI 短剧/漫剧生成，数据不出本机，无订阅费",
     "staged_detail_note": ("⏸ **暂存、不落表**：**归属依据** = **形态**"
                            "（**紧跟其后**）**+ 名字词义呼应**"
                            "（`Local` ↔ 本地 / 数据不出本机 / 无订阅费）—— "
                            "⚠️ 但主人**没点名** ⇒ 仍只是**推断**，不是判定"
                            "（**词义呼应也只是证据，不是许可**）；"
                            "🔸 **第二种读法并排**：也可能是**另一个项目 / 新工具**的介绍，"
                            "或「本地化短剧」这一**类能力**的描述；"
                            "**一个字都不落进任何表**；"
                            "🔴 也**不许把它当作『对应 GBT 能力域』**（那是另一格）；"
                            "🔺 **等主人一句话**再落"), },
    {"token": "CowAgent", "at": "R-H365",
     "note": "**已在**盘上：在**我方 R-H285 那批**（`KEY_TOOLS` 六条之**第五** · 映射 "
             "`im_multiplex` · 主人原话是「多平台接入能力（微信 / 飞书 / 钉钉 / QQ）」）⇒ "
             "记为**再现**（**不是新工具**）；"
             "🔴 **不许另起一行、也不许当重复丢掉** ⇒ 并排记；"
             "📌 **读数**：R-H285 六条进度 **5 / 6** —— "
             "还剩 `OpenClaw Monitor`（第六 · `god_view`）⇒ "
             "⚠️ 但**到齐也不等于**可以合并/落表（**重复与齐全都不是许可**）；"
             "🔺 **R-H366**：主人给了它的一句**详细介绍**（见 staged_detail）"
             "⇒ 与 Trae / Fitten Code / CC Switch / CC-Switch CLI / MoneyPrinterTurbo / "
             "Huobao Drama / LocalMiniDrama 同族；"
             "⚠️ **跨源呼应第四处**：句尾『微信/飞书/钉钉/QQ』与我方 R-H285 给它的"
             "`owner_use`（多平台接入能力（微信 / 飞书 / 钉钉 / QQ））**同向**"
             "⇒ 两处**并排记、不合并**（呼应也只是证据，不是许可）",
     "staged_detail": "基于大模型的超级 AI 助理，支持主动思考、任务规划、访问操作系统、创造和执行 Skills，支持微信/飞书/钉钉/QQ 接入",
     "echo_claim": True,
     "staged_detail_note": ("⏸ **暂存、不落表**：**归属依据** = **形态**（**紧跟其后**）"
                            "**+ 与 `owner_use` 同向**（句尾四个平台名正对我方原话）—— "
                            "⚠️ 但主人**没点名** ⇒ 仍只是**推断**，不是判定"
                            "（**呼应也只是证据，不是许可**）；"
                            "🔸 **第二种读法并排**：也可能是**另一个项目 / 新工具**的介绍，"
                            "或「超级助理」这一类能力的描述；"
                            "**一个字都不落进任何表**；"
                            "🔴 也**不许把它当作『对应 GBT 能力域』**（那是另一格）；"
                            "🔺 **等主人一句话**再落"), },
    {"token": "OpenClaw Monitor", "at": "R-H367",
     "note": "**已在**盘上：**两处都有** —— "
             "① **第 2 行**『AI实用效率工具』的『代表工具』那串里"
             "（`CowAgent / OpenClaw Monitor`）；"
             "② **我方 R-H285 那批**（`KEY_TOOLS` 六条之**第六/末条** · 映射 "
             "`god_view` · 主人原话「上帝视角的监控组件」）⇒ "
             "记为**再现**（**不是新工具**）；"
             "🔴 **不许另起一行、也不许当重复丢掉** ⇒ 并排记；"
             "📌 **读数**：R-H285 六条**全部到齐（6 / 6）** —— "
             "⚠️ 但**到齐 ≠ 许可**：六条**仍不合并、仍不落表**"
             "（「齐了」只说明主人把六条**逐个再给过一遍**，不说明它们该落哪）；"
             "🔺 **R-H368**：主人给了它的一句**详细介绍**（见 staged_detail）"
             "⇒ 与那几条同族；"
             "⚠️ **诚实处**：这句与我方 `owner_use`（上帝视角的监控组件）**语义同向**，"
             "但**按 ≥4 字可算口径并不命中**（两边没有 4 字连续重合）⇒ "
             "note 里如实写「语义同向但可算未命中」，**不许口头声称「呼应命中」**",
     "staged_detail": "监控 OpenClaw 智能体的运行情况，实时显示会话状态、Token 使用量和任务执行进度",
     "echo_claim": False,
     "staged_detail_note": ("⏸ **暂存、不落表**：**归属依据** = **形态**（**紧跟其后**）"
                            "**+ 语义同向**（监控 / 实时显示 ↔ 我方 `owner_use` 的「监控组件」）—— "
                            "⚠️ **但按 ≥4 字可算口径**：**未命中**（如实写，不许说成「呼应命中」）；"
                            "⚠️ 且主人**没点名** ⇒ 只是**推断**，不是判定；"
                            "🔸 **第二种读法并排**：也可能是**另一个项目 / 新工具**的介绍，"
                            "或「监控面板」这一类能力的描述；"
                            "**一个字都不落进任何表**；"
                            "🔴 也**不许把它当作『对应 GBT 能力域』**（那是另一格）；"
                            "🔺 **等主人一句话**再落"), },
    {"token": "PandaWiki", "at": "R-H371",
     "note": "**已在**盘上：**第 6 行**『文档和知识库工具』的『代表工具』那串的**首位**"
             "（`PandaWiki / Obsidian / Notion`）⇒ 记为**再现**（**不是新工具**）；"
             "🔴 **不许另起一行、也不许当重复丢掉** ⇒ 并排记；"
             "📌 **读数**：**第 6 行开始被逐个投喂**（那格**三个名字**，它先到）——"
             "与第 1 行（5 个）· 第 2 行（2 个）· 第 3 行（2 个）同款；"
             "⚠️ 但**逐个投喂 ≠ 拆行**：那一格仍是**一个格**（逐个给不改变它）；"
             "🔺 **R-H372**：主人给了它的一句**详细介绍**（见 staged_detail）"
             "⇒ 与那几条同族；"
             "⚠️ **诚实处**：这句与本行『对应 GBT 能力域（记忆层 / 知识库）』**语义呼应**，"
             "但**按 ≥4 字可算口径未命中**（两边没有 4 字连续重合）⇒ 如实写，不许说成命中",
     "staged_detail": "AI 驱动的开源知识库搭建系统，支持 AI 创作、AI 问答、AI 搜索",
     "staged_detail_note": ("⏸ **暂存、不落表**：**归属依据** = **形态**（**紧跟其后**）"
                            "**+ 与本行能力域语义呼应**"
                            "（AI 知识库 ↔ 本行『对应 GBT 能力域（记忆层 / 知识库）』）—— "
                            "⚠️ **但按 ≥4 字可算口径：未命中**（如实写）；"
                            "⚠️ 且主人**没点名** ⇒ 只是**推断**，不是判定；"
                            "🔸 **第二种读法并排**：也可能是**另一个项目 / 新工具**的介绍，"
                            "或「知识库 + AI」这一类能力的描述；"
                            "**一个字都不落进任何表**；"
                            "🔴 也**不许把它当作『对应 GBT 能力域』**（那是另一格）；"
                            "🔺 **等主人一句话**再落"), },
    {"token": "Obsidian", "at": "R-H373",
     "note": "**已在**盘上：**第 6 行**『文档和知识库工具』的『代表工具』那串的**第二个**"
             "（`PandaWiki / Obsidian / Notion`）⇒ 记为**再现**（**不是新工具**）；"
             "🔴 **不许另起一行、也不许当重复丢掉** ⇒ 并排记；"
             "📌 **读数**：第 6 行被逐个投喂的**第二个**（PandaWiki → **Obsidian**）⇒ "
             "那一格进度 **2 / 3**（还剩 `Notion`）；"
             "⚠️ 仍未拆行：那一格仍是**一个格**；"
             "🔺 **R-H374**：主人给了它的一句**详细介绍**（见 staged_detail）"
             "⇒ 与那几条同族；"
             "⚠️ 语义**完全对得上**（本地优先 / Markdown / 数据自控 正是它的招牌）"
             "—— 但**对得上也只是证据**，没点名就**仍是推断**",
     "staged_detail": "本地优先的知识管理，Markdown 格式，数据完全由你掌控",
     "staged_detail_note": ("⏸ **暂存、不落表**：**归属依据** = **形态**（**紧跟其后**）"
                            "**+ 语义完全对得上**（本地优先 / Markdown / 数据自控）—— "
                            "⚠️ 但主人**没点名** ⇒ 只是**推断**，不是判定；"
                            "🔸 **第二种读法并排**：也可能是**另一个项目 / 新工具**的介绍，"
                            "或「本地优先 + Markdown」这一类能力的描述；"
                            "**一个字都不落进任何表**；"
                            "🔴 也**不许把它当作『对应 GBT 能力域』**（那是另一格）；"
                            "🔺 **等主人一句话**再落"), },
    {"token": "Notion", "at": "R-H375",
     "note": "**已在**盘上：**第 6 行**『文档和知识库工具』的『代表工具』那串的**第三个**"
             "（`PandaWiki / Obsidian / Notion`）⇒ 记为**再现**（**不是新工具**）；"
             "🔴 **不许另起一行、也不许当重复丢掉** ⇒ 并排记；"
             "📌 **读数**：第 6 行被逐个投喂的**第三个**（PandaWiki → Obsidian → **Notion**）"
             "⇒ 那一格进度 **3 / 3**（**这格喂完了**）；"
             "⚠️ **喂完 ≠ 拆行 ≠ 落表**：那一格仍是**一个格**；"
             "🔺 **R-H375**：主人给了它一句**关系式的话**（见 staged_detail）"
             "⇒ 与那几条同族；"
             "⚠️ 但它是**「这工具与我方真身的关系」**，**不是「它是什么」**"
             "（那句里点名了我方盘上的 `context_vault`）"
             "—— 点名也只是证据，**主人没点名这是谁的介绍**就**仍是推断**；"
             "🔺 **R-H376**：主人又给了它**第二句**（**「是什么」**的那句，见 "
             "`staged_detail_extra`）⇒ 两句**并排**"
             "（**第一句说「关系」· 第二句说「身份」**）；"
             "⚠️ **第二句不许覆盖第一句**，且仍**没点名** ⇒ 仍只是**推断**；"
             "🔺 **R-H379 追认（判定不改）**：本刀出现**归属反转**现场 —— "
             "主人给的介绍句紧接在**下一个名字之前**，而它属于**上一个**名字"
             "⇒ 回过头看这一条：第一句『与 context_vault 互补』也是**在名字之前**"
             "⇒ **第二种读法的权重上升**（它也可能是**上一轮那个名字** Obsidian 的介绍）"
             "🔴 但**判定一个字不改**：仍挂在 Notion 上、仍是**推断**、仍**不落表**",
     "staged_detail": "与 context_vault 互补",
     # 🔴 R-H380 正字：主人**先给这句、后给名字『Notion』** ⇒ 相对 owner 是**之前**
     "detail_position": "before_owner_name",
     "staged_detail_extra": "一体化工作空间，集笔记、数据库、任务管理于一体",
     "staged_detail_extra_round": "R-H376",
     "staged_detail_note": ("⏸ **暂存、不落表**：**归属依据** = "
                            "**位置读数 `before_next_name`**"
                            "（**位置读数：在名字之前**）"
                            "**+ 点名了我方盘上的真身**（`context_vault` 在盘上："
                            "⚠️ **R-H379 正字**：R-H375 当时把依据写成『紧跟其后』"
                            "—— 按消息次序**实际是「在名字之前」** ⇒ **照实改正**"
                            "（措辞与事实不符是**我自己的**问题）；"
                            "`gbt_allinone/tools/context_vault.py`）—— "
                            "⚠️ 但主人**没点名这是谁的介绍** ⇒ 只是**推断**，不是判定；"
                            "⚠️ 第二层诚实：这句是**关系描述**（互补），"
                            "**不是身份判定** —— 「与 X 互补」说明它们**不是同一个**，"
                            "**没说这个工具就是 X**；"
                            "🔸 **第二种读法并排**：也可能是主人**对我方架构的一句评论**"
                            "（第 6 行这一类工具与本地的记忆真库互补），"
                            "**不一定是**『Notion』的介绍；"
                            "📌 **读数**：本句与我方 **R-H285 那批的对接说明**"
                            "**没有可比对象**（`Notion` 不在那六条里）"
                            "⇒ 呼应读数**不适用**，**不许拿它当呼应证据**"
                            "⇒ `echo_claim` 留空、**不许拿它当命中**；"
                            "**一个字都不落进任何表**；"
                            "🆕 **R-H376 第二句（并排 · 不覆盖）**：主人又给了它"
                            "**「是什么」**的一句（见 `staged_detail_extra`）—— "
                            "**第一句说「关系」（与我方真身互补）、"
                            "第二句说「身份」（一体化工作空间）** ⇒ 两句**互补而不重叠**，"
                            "**并排记、不合并、不许覆盖第一句**；"
                            "⚠️ 仍**没点名** ⇒ 仍只是**推断**；"
                            "🔸 **第二种读法并排**：也可能是一条**新工具**的介绍；"
                            "🔺 **等主人一句话**再落"), },
    {"token": "Watt Toolkit", "at": "R-H378",
     "note": "**已在**盘上：**第 10 行**『GitHub 加速工具』的『代表工具』那串的**首位**"
             "（`Watt Toolkit / FastGithub / dev-sidecar`）⇒ 记为**再现**（**不是新工具**）；"
             "🔴 **不许另起一行、也不许当重复丢掉** ⇒ 并排记；"
             "📌 **读数**：**第 10 行开始被逐个投喂**（那格 3 个名字，它先到）⇒ "
             "那一格进度 **1 / 3**；"
             "⚠️ **仍是一个格**：喂到一个名字 **≠ 拆行**；"
             "📌 **跨源读数**：这一行**正好**是上一刀（R-H377）源 6『网络加速工具』"
             "**像但不等于**的候选之一（见源 6 的 `near_names`）"
             "—— **像但不等于、不许当同一个**；"
             "🔺 **R-H379**：主人给了它一句**详细介绍**（见 staged_detail）——"
             "⚠️ 但**位置读数**是 **`before_next_name`**（介绍在**名字之前**，不是紧跟其后）"
             "⇒ **位置只是证据、语义才是判据**（见下）",
     # 🔴 R-H380 正字：介绍确实出现在**下一个名字（FastGithub）之前**，
     #    但位置口径一律**相对它挂的那个名字** —— 相对 Watt Toolkit 它是**之后**来的
     "detail_position": "after_name",
     "detail_next_name_side": "before_next_name",
     "staged_detail": "C# 开源，跨平台 GitHub 加速 + Steam 工具箱",
     "staged_detail_note": ("⏸ **暂存、不落表**：**归属依据** = "
                            "**语义完全对得上**（『Steam 工具箱』这半句"
                            "**只对得上 Watt Toolkit**；`FastGithub` **不做** Steam 工具箱）"
                            "**+ 位置读数 `after_name`**"
                            "（**位置读数：跟在名字之后**；"
                            "📌 它**恰好**出现在**下一个名字（FastGithub）之前**"
                            "⇒ 那是 `detail_next_name_side` 的读数，**不是**位置判据）—— "
                            "⚠️ 主人**没点名** ⇒ 仍只是**推断**；"
                            "⚠️ **位置与语义打架时按语义挂**：本句紧跟的是**下一个名字**"
                            "『FastGithub』（**在名字之前**），但**语义只对得上这一条** ⇒ "
                            "按语义挂，并把位置读数**照实写上**（不许只挑顺眼的证据）；"
                            "🔸 **第二种读法并排**：也可能属于**紧随其后的**『FastGithub』"
                            "—— **本刀不取**，理由：**FastGithub 不做 Steam 工具箱**"
                            "（取它就得把「Steam 工具箱」这句砍掉才能自圆其说）；"
                            "**一个字都不落进任何表**；🔺 **等主人一句话**再落"), },
    {"token": "FastGithub", "at": "R-H379",
     "note": "**已在**盘上：**第 10 行**『GitHub 加速工具』的『代表工具』那串的**第二个**"
             "（`Watt Toolkit / FastGithub / dev-sidecar`）⇒ 记为**再现**（**不是新工具**）；"
             "🔴 **不许另起一行、也不许当重复丢掉** ⇒ 并排记；"
             "📌 **读数**：第 10 行被逐个投喂的**第二个**（Watt Toolkit → **FastGithub**）⇒ "
             "那一格进度 **2 / 3**（还剩 `dev-sidecar`）；"
             "⚠️ **仍是一个格**：喂到两个名字 **≠ 拆行**；"
             "📌 **诚实处**：R-H379 那句介绍**没有**挂在它头上"
             "（主人给的那句说『+ Steam 工具箱』⇒ 只对得上 Watt Toolkit）"
             "—— **一个字都没替它编**；"
             "🔺 **R-H380**：主人给了它一句**详细介绍**（见 staged_detail）—— "
             "⚠️ 这一刀**语义不排他**（三个工具都说得通）⇒ "
             "改由**结构**定归属：**源表列序 = 工具名 → 详细介绍**"
             "⇒ 介绍跟的是**它前面最近的那个名字**（= 本条目）",
     "detail_position": "after_name",
     "staged_detail": "GitHub 加速，解决打不开、头像无法加载、clone/push 失败等问题",
     "staged_detail_note": ("⏸ **暂存、不落表**：**归属依据** = "
                            "**结构（源表列序：工具名 → 详细介绍）**"
                            "**+ 语义相容（但不排他）** —— "
                            "⚠️ 本句讲的是「GitHub 加速」的**通病**，"
                            "**三个工具都说得通** ⇒ **语义这次定不了归属**，"
                            "它只能**排除**明显不合的；归属交给**结构**；"
                            "⚠️ 主人**没点名** ⇒ 仍只是**推断**（**结构也只是证据**）；"
                            "🔸 **第二种读法并排**：也可能属于**紧随其后的**『dev-sidecar』；"
                            "🔸 **第三种读法并排**：也可能是**第 10 行这一整类的描述**"
                            "（不属任何单个工具）—— 三种读法**并排**、**不硬配**；"
                            "🔕 **位置读数**：`after_name`"
                            "（**位置读数：跟在名字之后**）—— "
                            "🔴 **两种证据谁都不是许可**：R-H379 那次是**语义**说了算，"
                            "这次是**结构**说了算 ⇒ 谁强用谁，**都不许单独当许可**；"
                            "**一个字都不落进任何表**；🔺 **等主人一句话**再落"), },
    {"token": "dev-sidecar", "at": "R-H380",
     "note": "**已在**盘上：**第 10 行**『GitHub 加速工具』的『代表工具』那串的**第三个**"
             "（`Watt Toolkit / FastGithub / dev-sidecar`）⇒ 记为**再现**（**不是新工具**）；"
             "🔴 **不许另起一行、也不许当重复丢掉** ⇒ 并排记；"
             "📌 **读数**：第 10 行被逐个投喂的**第三个**"
             "（Watt Toolkit → FastGithub → **dev-sidecar**）⇒ 那一格进度 **3 / 3**"
             "（**这格喂完了**）；"
             "⚠️ **喂完 ≠ 拆行 ≠ 落表**：那一格仍是**一个格**；"
             "📌 **诚实处**：R-H380 那句介绍**没有**挂在它头上"
             "（按结构挂在**它前面最近的名字** FastGithub 上，见那条的 `staged_detail_note`）"
             "—— **一个字都没替它编**；"
             "🔺 **R-H381**：主人给了它一句**详细介绍**（见 staged_detail）—— "
             "📌 本刀**三种证据第一次同向**：**结构**（它前面最近的名字就是它）"
             "· **位置**（`after_name`）· **语义相容**"
             "—— ⚠️ **同向也只是证据**：主人**没点名** ⇒ 仍只是**推断**",
     "detail_position": "after_name",
     "staged_detail": "GitHub / git clone / releases 下载 / stackoverflow 加速",
     "staged_detail_note": ("⏸ **暂存、不落表**：**归属依据** = "
                            "**结构（源表列序：工具名 → 详细介绍）**"
                            "**+ 位置读数 `after_name`（位置读数：跟在名字之后）**"
                            "**+ 语义相容** —— "
                            "📌 **三种证据第一次同向**（R-H379 语义赢、R-H380 结构赢，"
                            "本刀三者同向）；"
                            "⚠️ 但**同向 ≠ 许可**：主人**没点名** ⇒ 仍只是**推断**；"
                            "🔸 **第二种读法并排**：也可能属于**上一刀那个名字**（FastGithub）"
                            "—— 本刀**不取**，理由：R-H380 那句「GitHub 打不开/头像/clone push」"
                            "已经把 FastGithub 那一格占了，**同一个名字不挂两句**"
                            "（与 `staged_detail_duplicated_across_names` 同一纪律）；"
                            "🔸 **第三种读法并排**：也可能是**第 10 行这一整类的描述**；"
                            "**一个字都不落进任何表**；🔺 **等主人一句话**再落"), },
)
REAPPEARING_TOKENS_NOTE = (
    "**再现名字区**：主人第二次给同一个名字时有两个对称的失手 —— ① **另起一行**"
    "（把已有的当成新的 ⇒ 重复建行）② **当重复丢掉**（把主人这次的话当噪音 ⇒ 证据丢）"
    "⇒ 两条都不许，只能**并排记** + 写清「**已在**哪儿」；"
    "⚠️ 判据卡在真问题上：条目说「已在」，就必须**真的在盘上按整段找得到**"
    "（用包含比对会把「Trae 等」也算成「Trae」⇒ 假命中）。"
)

# 分类行：分类名到了、其余格未到 ⇒ 留空带理由
CATEGORY_ROWS_OWNER = (
    {"section": "二", "category": "AI辅助编程工具",
     "cells": {"代表工具": "Trae / Fitten Code / CodeGeeX / 通义灵码 / GitHub Copilot"},
     "source": "主人提供 · R-H296 · 逐字",
     "note": ("🔺 **R-H334 行为证据 +1**：主人把本分类与 R-H285 那批的『编程工作区』"
              "**并列写**（『AI 辅助编程工具（编程工作区核心）』）⇒ 两批**疑似对应**；"
              "🔴 但**仍不擅自合并、不自解谁作准** ⇒ 待主人一句话；"
              "🔺 **R-H336 再现证据**：主人又单独给『Trae』—— 它**已经在本行『代表工具』那串里**"
              "（首位）⇒ 记为**再现**（**不是新工具**）：🔴 **不许另起一行、也不许当重复丢掉**；"
              "⚠️ 同一个名字还**前缀命中**了待归属『IDE & 代码编辑器』的暂存值"
              "（『VS Code / Trae 等』里的『Trae 等』**整段不等**）⇒ **像但不等于**、两处并排"),
     "pending_reason": ("『代表工具』已到、**『对应 GBT 能力域』仍缺** ⇒ 留空带理由（§57）；"
                        "**不许拿我方 R-H285 那份六个工具顶这一格**；"
                        "⚠️ 这个分类名**不在** R-H285 那批分类名（CATEGORIES_OWNER）里 ⇒ "
                        "**两批并存**，关系待主人定（**不许用一批覆盖另一批**）")},
    {"section": "二", "category": "AI实用效率工具",
     "cells": {"代表工具": "CowAgent / OpenClaw Monitor"},
     "source": "主人提供 · R-H298 · 逐字",
     "pending_reason": ("『代表工具』已到、**『对应 GBT 能力域』仍缺** ⇒ 留空带理由（§57）；"
                        "**不许凭分类名编工具**；"
                        "⚠️ 同样**不在** R-H285 那批分类名里 ⇒ **两批并存**，关系待主人定；"
                        "🔺 与 **R-H285** 那批**重叠**：CowAgent / OpenClaw Monitor 都在我方"
                        "R-H285 登记的重点工具里 ⇒ **两批首次交叉**（并排记，不合并）")},
    {"section": "二", "category": "AI模型管理工具",
     "cells": {"代表工具": "CC Switch / CC-Switch CLI",
               "对应 GBT 能力域": "模型路由 / 供应商切换"},
     "source": "主人提供 · R-H301（代表工具）+ R-H302（对应域）· 逐字",
     "pending_reason": None,
     "note": ("🔺 与 **R-H285** 重叠：CC Switch 在我方那条里；且多一个 **变体** `CC-Switch CLI`"
              "（前缀一致但整串不同 —— 差的是「空格 ↔ 连字符」+ 后缀 CLI）⇒ "
              "**并排记，不合并、不当同一个**；"
              "🔺 **R-H346**：主人把它写成『**2.** AI 模型管理工具（自动切换核心）』⇒ "
              "① 源仓库编号 **2**（本仓在**第 3 行** ⇒ 顺序不一致，见 `SOURCE_ORDER_READINGS`）；"
              "② 括号词『自动切换核心』与本行『对应 GBT 能力域』**语义呼应**，"
              "但**不是** R-H285 那批的分类名 ⇒ **不记跨批证据**（不硬凑）")},
    {"section": "二", "category": "AI短剧生成工具",
     "cells": {"代表工具": "MoneyPrinterTurbo"},
     "source": "主人提供 · R-H303 · 逐字",
     "pending_reason": ("『代表工具』已到、**『对应 GBT 能力域』仍缺** ⇒ 留空带理由（§57）；"
                        "**不许凭分类名编工具**；"
                        "🔺 与 **R-H285** 重叠：MoneyPrinterTurbo 在我方那条里"
                        "（映射到 video_pipeline）⇒ **并排记，不合并**")},
    {"section": "二", "category": "实用画图工具",
     "cells": {},
     "source": "主人提供 · R-H306 · 逐字",
     "pending_reason": ("分类名到了，**其余格（代表工具 / 对应 GBT 能力域）都未到** ⇒ "
                        "留空带理由（§57）；**不许凭分类名编工具**；"
                        "⚠️ **落表顺序可能错位**：『IDE & 代码编辑器』仍在待归属 —— "
                        "若它也是分类名，按主人给的先后应排在**本行之前** ⇒ "
                        "顺序以主人为准，本行位置**暂记不等于最终序**")},
    {"section": "二", "category": "文档和知识库工具",
     "cells": {"代表工具": "PandaWiki / Obsidian / Notion",
               "对应 GBT 能力域": "记忆层 / 知识库"},
     "source": "主人提供 · R-H308（代表工具）+ R-H309（对应域）· 逐字",
     "pending_reason": None,
     "note": ("🔸 **第二种读法并排记**：这个分类名也可能本是**某行的『对应 GBT 能力域』"
              "值** ⇒ 待主人一句确认；"
              "（三个工具名**都不在** R-H285 那批里 ⇒ 无重叠、无变体）")},
    {"section": "二", "category": "Markdown 编辑器",
     "cells": {"代表工具": "MarkText / Typora"},
     "source": "主人提供 · R-H310 · 逐字",
     "pending_reason": ("『代表工具』已到、**『对应 GBT 能力域』仍缺** ⇒ 留空带理由（§57）；"
                        "**不许凭分类名编工具**；"
                        "（两个名字都**不在** R-H285 那批里 ⇒ 无重叠、无变体）")},
    {"section": "二", "category": "Markdown 文件转换器",
     "cells": {},
     "source": "主人提供 · R-H311 · 逐字",
     "pending_reason": ("分类名到了，**其余格（代表工具 / 对应 GBT 能力域）都未到** ⇒ "
                        "留空带理由（§57）；**不许凭分类名编工具**；"
                        "🔸 **第二种读法并排记**：它也可能本是**第七行『Markdown 编辑器』的"
                        "『对应 GBT 能力域』值** —— 命名形态与已有分类一致故按分类落，"
                        "**待主人一句确认**")},
    {"section": "二", "category": "开发环境管理工具",
     "cells": {},
     "source": "主人提供 · R-H312 · 逐字",
     "pending_reason": ("分类名到了，**其余格（代表工具 / 对应 GBT 能力域）都未到** ⇒ "
                        "留空带理由（§57）；**不许凭分类名编工具**；"
                        "🔸 **第二种读法并排记**：它也可能本是某行的『对应 GBT 能力域』值"
                        " —— 命名形态与已有分类一致故按分类落，**待主人一句确认**")},
    {"section": "二", "category": "GitHub 加速工具",
     "cells": {"代表工具": "Watt Toolkit / FastGithub / dev-sidecar"},
     "source": "主人提供 · R-H314 · 逐字",
     "pending_reason": ("『代表工具』已到、**『对应 GBT 能力域』仍缺** ⇒ 留空带理由（§57）；"
                        "**不许凭分类名编工具**；"
                        "（三个名字都**不在** R-H285 那批里 ⇒ 无重叠、无变体）")},
    {"section": "二", "category": "文本编辑器工具",
     "cells": {"代表工具": "Notepad++ / Notepads"},
     "source": "主人提供 · R-H316 · 逐字",
     "pending_reason": ("『代表工具』已到、**『对应 GBT 能力域』仍缺** ⇒ 留空带理由（§57）；"
                        "**不许凭分类名编工具**；"
                        "（两个名字都**不在** R-H285 那批里 ⇒ 无重叠、无变体）"),
     "note": ("🔸 **只差一个 s，但是两个不同的工具**：`Notepad++` 与 `Notepads` ⇒ "
              "**并排留、不许当同一个**（前缀一致 ≠ 同一个）；"
              "🔸 本条第二种读法仍并排记：这个分类名也可能本是某行的『对应 GBT 能力域』值")},
    {"section": "二", "category": "数据库管理工具",
     "cells": {},
     "source": "主人提供 · R-H317 · 逐字",
     "pending_reason": ("分类名到了，**其余格（代表工具 / 对应 GBT 能力域）都未到** ⇒ "
                        "留空带理由（§57）；**不许凭分类名编工具**；"
                        "🔸 **第二种读法并排记**：它也可能本是某行的『对应 GBT 能力域』值"
                        " —— 命名形态与已有分类一致故按分类落，**待主人一句确认**")},
    {"section": "二", "category": "数据库设计工具",
     "cells": {},
     "source": "主人提供 · R-H318 · 逐字",
     "pending_reason": ("分类名到了，**其余格（代表工具 / 对应 GBT 能力域）都未到** ⇒ "
                        "留空带理由（§57）；**不许凭分类名编工具**；"
                        "🔸 **第二种读法并排记**：它也可能本是某行的『对应 GBT 能力域』值"
                        " —— 命名形态与已有分类一致故按分类落，**待主人一句确认**")},
    {"section": "二", "category": "Git 管理工具",
     "cells": {},
     "source": "主人提供 · R-H319 · 逐字",
     "pending_reason": ("分类名到了，**其余格（代表工具 / 对应 GBT 能力域）都未到** ⇒ "
                        "留空带理由（§57）；**不许凭分类名编工具**；"
                        "🔸 **第二种读法并排记**：它也可能本是某行的『对应 GBT 能力域』值"
                        " —— 命名形态与已有分类一致故按分类落，**待主人一句确认**")},
    {"section": "二", "category": "抓包调试工具",
     "cells": {},
     "source": "主人提供 · R-H320 · 逐字",
     "pending_reason": ("分类名到了，**其余格（代表工具 / 对应 GBT 能力域）都未到** ⇒ "
                        "留空带理由（§57）；**不许凭分类名编工具**；"
                        "🔸 **第二种读法并排记**：它也可能本是某行的『对应 GBT 能力域』值"
                        " —— 命名形态与已有分类一致故按分类落，**待主人一句确认**")},
    {"section": "二", "category": "性能压测工具",
     "cells": {},
     "source": "主人提供 · R-H321 · 逐字",
     "pending_reason": ("分类名到了，**其余格（代表工具 / 对应 GBT 能力域）都未到** ⇒ "
                        "留空带理由（§57）；**不许凭分类名编工具**；"
                        "🔸 **第二种读法并排记**：它也可能本是某行的『对应 GBT 能力域』值"
                        " —— 命名形态与已有分类一致故按分类落，**待主人一句确认**")},
    {"section": "二", "category": "Redis 管理工具",
     "cells": {},
     "source": "主人提供 · R-H322 · 逐字",
     "pending_reason": ("分类名到了，**其余格（代表工具 / 对应 GBT 能力域）都未到** ⇒ "
                        "留空带理由（§57）；**不许凭分类名编工具**；"
                        "🔸 **第二种读法并排记**：它也可能本是某行的『对应 GBT 能力域』值"
                        " —— 命名形态与已有分类一致故按分类落，**待主人一句确认**")},
    {"section": "二", "category": "文件同步工具",
     "cells": {},
     "source": "主人提供 · R-H323 · 逐字",
     "pending_reason": ("分类名到了，**其余格（代表工具 / 对应 GBT 能力域）都未到** ⇒ "
                        "留空带理由（§57）；**不许凭分类名编工具**；"
                        "🔸 **第二种读法并排记**：它也可能本是某行的『对应 GBT 能力域』值"
                        " —— 命名形态与已有分类一致故按分类落，**待主人一句确认**")},
    {"section": "二", "category": "报表制作工具",
     "cells": {},
     "source": "主人提供 · R-H324 · 逐字",
     "pending_reason": ("分类名到了，**其余格（代表工具 / 对应 GBT 能力域）都未到** ⇒ "
                        "留空带理由（§57）；**不许凭分类名编工具**；"
                        "🔸 **第二种读法并排记**：它也可能本是某行的『对应 GBT 能力域』值"
                        " —— 命名形态与已有分类一致故按分类落，**待主人一句确认**")},
    {"section": "二", "category": "文件下载工具",
     "cells": {},
     "source": "主人提供 · R-H325 · 逐字",
     "pending_reason": ("分类名到了，**其余格（代表工具 / 对应 GBT 能力域）都未到** ⇒ "
                        "留空带理由（§57）；**不许凭分类名编工具**；"
                        "🔸 **第二种读法并排记**：它也可能本是某行的『对应 GBT 能力域』值"
                        " —— 命名形态与已有分类一致故按分类落，**待主人一句确认**")},
    {"section": "二", "category": "Docker 管理工具",
     "cells": {},
     "source": "主人提供 · R-H326 · 逐字",
     "pending_reason": ("分类名到了，**其余格（代表工具 / 对应 GBT 能力域）都未到** ⇒ "
                        "留空带理由（§57）；**不许凭分类名编工具**；"
                        "🔸 **第二种读法并排记**：它也可能本是某行的『对应 GBT 能力域』值"
                        " —— 命名形态与已有分类一致故按分类落，**待主人一句确认**")},
    {"section": "二", "category": "网络管理工具",
     "cells": {},
     "source": "主人提供 · R-H327 · 逐字",
     "pending_reason": ("分类名到了，**其余格（代表工具 / 对应 GBT 能力域）都未到** ⇒ "
                        "留空带理由（§57）；**不许凭分类名编工具**；"
                        "🔸 **第二种读法并排记**：它也可能本是某行的『对应 GBT 能力域』值"
                        " —— 命名形态与已有分类一致故按分类落，**待主人一句确认**")},
    {"section": "二", "category": "内网穿透工具",
     "cells": {},
     "source": "主人提供 · R-H328 · 逐字",
     "pending_reason": ("分类名到了，**其余格（代表工具 / 对应 GBT 能力域）都未到** ⇒ "
                        "留空带理由（§57）；**不许凭分类名编工具**；"
                        "🔸 **第二种读法并排记**：它也可能本是某行的『对应 GBT 能力域』值"
                        " —— 命名形态与已有分类一致故按分类落，**待主人一句确认**")},
    {"section": "二", "category": "堡垒机工具",
     "cells": {},
     "source": "主人提供 · R-H329 · 逐字",
     "pending_reason": ("分类名到了，**其余格（代表工具 / 对应 GBT 能力域）都未到** ⇒ "
                        "留空带理由（§57）；**不许凭分类名编工具**；"
                        "🔸 **第二种读法并排记**：它也可能本是某行的『对应 GBT 能力域』值"
                        " —— 命名形态与已有分类一致故按分类落，**待主人一句确认**")},
    {"section": "二", "category": "实用建站工具",
     "cells": {},
     "source": "主人提供 · R-H330 · 逐字",
     "pending_reason": ("分类名到了，**其余格（代表工具 / 对应 GBT 能力域）都未到** ⇒ "
                        "留空带理由（§57）；**不许凭分类名编工具**；"
                        "🔸 **第二种读法并排记**：它也可能本是某行的『对应 GBT 能力域』值"
                        " —— 命名形态与已有分类一致故按分类落，**待主人一句确认**")},
    {"section": "二", "category": "Kafka 管理工具",
     "cells": {},
     "source": "主人提供 · R-H331 · 逐字",
     "pending_reason": ("分类名到了，**其余格（代表工具 / 对应 GBT 能力域）都未到** ⇒ "
                        "留空带理由（§57）；**不许凭分类名编工具**；"
                        "🔸 **第二种读法并排记**：它也可能本是某行的『对应 GBT 能力域』值"
                        " —— 命名形态与已有分类一致故按分类落，**待主人一句确认**")},
    {"section": "二", "category": "图像处理软件",
     "cells": {},
     "source": "主人提供 · R-H332 · 逐字",
     "pending_reason": ("分类名到了，**其余格（代表工具 / 对应 GBT 能力域）都未到** ⇒ "
                        "留空带理由（§57）；**不许凭分类名编工具**；"
                        "🔸 **第二种读法并排记**：它也可能本是某行的『对应 GBT 能力域』值"
                        " —— 命名形态与已有分类一致故按分类落，**待主人一句确认**")},
    {"section": "二", "category": "Edge/Chrome/VS Code 插件",
     "cells": {},
     "source": "主人提供 · R-H333 · 逐字",
     "pending_reason": ("分类名到了，**其余格（代表工具 / 对应 GBT 能力域）都未到** ⇒ "
                        "留空带理由（§57）；**不许凭分类名编工具**；"
                        "🔸 **第二种读法并排记**：它也可能本是某行的『对应 GBT 能力域』值"
                        " —— 命名形态与已有分类一致故按分类落，**待主人一句确认**；"
                        "🔸 **第三种读法并排记**：它也可能本是某行的『代表工具』格的值"
                        "（形态上是「浏览器/编辑器 插件」这一类工具名）；"
                        "⚠️ 与 R-H285 那批里的『扩展生态』**像但不等于** —— "
                        "含义相近、整串不同 ⇒ **并排记、不许当同一个**")},
)
CATEGORY_VS_REGISTRY_NOTE = ("**两批分类名并存**：R-H285 记的那批（编程工作区 / 智能体生态 / …）"
                             "与第二节实际给的（AI辅助编程工具 / AI实用效率工具 / …）"
                             "⇒ **并排记、不合并**，谁作准待主人定；"
                             "🔺 **R-H334 证据 +1**：主人把第 1 个分类与『编程工作区』**并列写**"
                             "（括号里）⇒ 两批**疑似对应**，但 🔴 **仍不擅自合并、仍不自解谁作准**"
                             "⇒ 待主人一句话")
# 🔴 R-H306：待归属未决会让**落表顺序**悄悄失真（后到的先落、先到的还悬着）
CATEGORY_ORDER_NOTE = ("⚠️ **落表顺序可能错位**：待归属里还有『IDE & 代码编辑器』——"
                       "若它也是分类名，按主人给的先后应排在『实用画图工具』**之前** ⇒ "
                       "**顺序以主人为准**，当前落表位置**不等于最终序**")
CATEGORY_ROWS_NOTE = ("**分类行**：分类名到了就建行；格没到就留空带理由；"
                      "有值的格必须能追到出处")


def check_category_rows() -> dict:
    """闸⑮（R-H295）：**分类行**四条 —— 名非空 · 未到的格要带理由 · 有值的格要有出处 · 空样本不按绿。

    为什么单立：第二节是**分类表**（按工具类型分类），一行一个分类。
    分类名最容易「看着就知道该填什么」—— 于是最容易凭常识把工具名编进去。
    """
    rows = list(CATEGORY_ROWS_OWNER)
    if not rows:
        return {"ok": False, "denied": True, "rule": "categories_empty",
                "why": "一行分类都没有 ⇒ **空样本不按绿**"}
    cols = tuple(SECTION2_COLUMNS)
    seen_names: set = set()
    out = []
    for r in rows:
        name = str(r.get("category") or "").strip()
        cells = dict(r.get("cells") or {})
        reason = str(r.get("pending_reason") or "").strip()
        source = str(r.get("source") or "").strip()
        if not name:
            return {"ok": False, "denied": True, "rule": "category_without_name",
                    "why": "每行必须写明**分类名**"}
        # 🆕 R-H299：分类名不许重复（防复制粘贴把同一分类建两遍）
        if name in seen_names:
            return {"ok": False, "denied": True, "rule": "category_duplicate",
                    "category": name,
                    "why": "**分类名重复**：同一个分类被建了两行（复制粘贴最容易出这个）"}
        seen_names.add(name)
        unknown = [c for c in cells if c not in cols]
        if unknown:
            return {"ok": False, "denied": True, "rule": "category_cell_unknown_column",
                    "category": name, "unknown": unknown, "columns": list(cols),
                    "why": "格必须落在**已登记的列契约**里（不许自己加列）"}
        filled = [c for c in cols if str(cells.get(c) or "").strip()]
        if len(filled) < len(cols) and not reason:
            return {"ok": False, "denied": True, "rule": "category_without_reason",
                    "category": name, "filled": filled, "columns": list(cols),
                    "why": "还有格没到 ⇒ 必须写明理由（§57：有理由的空 ≠ 未处理的残留）"}
        if filled and not source:
            return {"ok": False, "denied": True, "rule": "category_cell_without_source",
                    "category": name, "filled": filled,
                    "why": "有值的格必须能追到**出处**（谁给的、哪一轮）"}
        # 🆕 R-H297：分类名不在此前那批里时，必须写明「两批并存」——
        # 🆕 R-H306：待归属里若有「可能是分类」的条目 ⇒ 后到的分类行必须写明「顺序可能错位」
        #    （否则落表顺序会悄悄不等于主人给的顺序 —— 又一个静默失真）
        #    否则两批分类名会被当成一批（一个静默合并的现场）。
        #    ⚠️ 放在**最后**：否则会抢在「半填必须带理由」前面，把旧判据盖掉。
        # ⚠️ 「两批并存」是**全局事实**（不是每行各自的属性）⇒ 判据挂**全局说明**，
        #    不挂每行理由 —— 否则行一填满（pending_reason 变 None）判据就落空（R-H302 现场）
        if name not in CATEGORIES_OWNER \
                and "两批" not in CATEGORY_VS_REGISTRY_NOTE:
            return {"ok": False, "denied": True,
                    "rule": "category_name_vs_registry_unstated",
                    "category": name,
                    "why": "这个分类名**不在** R-H285 那批里 ⇒ 必须写明"
                           "「两批并存、关系待主人定」（**不许用一批覆盖另一批**）"}
        # 🆕 R-H298：格里的工具名若命中我方 R-H285 那批 ⇒ 必须写明「重叠」
        # 用 " / " 拼：不然相邻两格会黏成一片，变体探测会多带一截（R-H302 现场）
        blob = " / ".join(str(cells.get(c) or "") for c in cols)
        hits = [t["name"] for t in KEY_TOOLS if t["name"] in blob]
        # ⚠️ 判据认「理由 + note」两处：行填满后 pending_reason 会是 None，
        #    而「与 R-H285 重叠」是**行级事实**，不该随理由消失（R-H302 现场）
        note_txt = str(r.get("note") or "")
        where = reason + "\n" + note_txt
        if hits and "R-H285" not in where and "重叠" not in where:
            return {"ok": False, "denied": True,
                    "rule": "category_overlap_with_rh285_unstated",
                    "category": name, "hits": hits,
                    "why": "这些名字**已经在我方 R-H285 那批里** ⇒ 必须写明重叠"
                           "（否则同一批工具会被两处各自当成新发现）"}
        # 🆕 R-H301：**变体** —— 值里出现「R-H285 某名字」的变形（前缀一致、整串更长）
        #    却没写明「变体」⇒ 红（与「前缀一致必须并排记」同族）
        # ⚠️ 归一化后比对：`CC-Switch CLI` 与 `CC Switch` 差的是**空格↔连字符**，
        #    不是纯前缀 ⇒ 先把空格/连字符/大小写抹平再比（判据要卡在真关系上）
        def _norm(s: str) -> str:
            return str(s or "").replace(" ", "").replace("-", "").lower()
        variants = []
        for t in KEY_TOOLS:
            base = _norm(t["name"])
            for piece in str(blob).split("/"):
                p = piece.strip()
                if p and _norm(p) != base and _norm(p).startswith(base):
                    variants.append(p)
        if variants and "变体" not in where:
            return {"ok": False, "denied": True,
                    "rule": "category_variant_unstated",
                    "category": name, "variants": variants,
                    "why": "这些是 R-H285 那条的**变体**（前缀一致、整串更长）⇒ "
                           "必须写明「变体」（**不许当成同一个，也不许当成新的**）"}
        out.append({"section": str(r.get("section") or "").strip(),
                    "category": name, "cells": {c: cells.get(c) for c in cols},
                    "has_all": len(filled) == len(cols),
                    "note": str(r.get("note") or "") or None,
                    "source": source or None, "pending_reason": reason or None})
    # 🆕 R-H306：待归属里若有「可能是分类」的条目 ⇒ 必须写明「落表顺序可能错位」
    #    ⚠️ 判据挂**全局说明**（不挂各行理由：理由会被测试临时改，也会随行填满而消失）
    maybe_cat = any("分类名" in "".join(str(x) for x in (p.get("readings") or ()))
                    for p in PENDING_ATTRIBUTION)
    if maybe_cat and "顺序" not in CATEGORY_ORDER_NOTE:
        return {"ok": False, "denied": True,
                "rule": "category_order_maybe_shifted",
                "why": "待归属里还有**可能是分类**的条目 ⇒ 分类表里必须有一处写明"
                       "「落表顺序可能错位」（顺序以主人为准）"}
    return {"ok": True, "readonly": True, "rows": out, "count": len(out),
            "columns": list(cols),
            "vs_registry_note": CATEGORY_VS_REGISTRY_NOTE,
            "order_note": CATEGORY_ORDER_NOTE,
            "complete": all(x["has_all"] for x in out),
            # ⚠️ 用**包含**比对，不用等值：格子里是「A / B」拼起来的一串
            "overlap_with_rh285": sorted({t["name"] for t in KEY_TOOLS
                                           if any(t["name"] in str(c or "")
                                                  for r2 in rows
                                                  for c in dict(r2.get("cells") or {}).values())}),
            "variants_of_rh285": sorted({p.strip() for r2 in rows
                                          for c in dict(r2.get("cells") or {}).values()
                                          for p in str(c or "").split("/")
                                          if any(_norm(p).startswith(_norm(t["name"]))
                                                 and _norm(p) != _norm(t["name"])
                                                 for t in KEY_TOOLS)}),
            "note": CATEGORY_ROWS_NOTE}


def check_source_table_columns() -> dict:
    """闸⑯（R-H334）：**源表列契约** —— 列非空 · 顺序须是主人给的顺序 · 不许与本仓列混为一谈 · 空样本不按绿。

    为什么单立：主人给的是**源仓库**里「每个分类下那张表」的列（工具名/详细介绍/下载地址），
    而我方第二节另有一张表（代表工具/对应 GBT 能力域）。两张表**位置像、内容不同** ——
    最危险的失手是「把源表三列直接当我方第二节的列」，那样两套口径就被悄悄合并了。
    """
    if not SOURCE_TABLE_COLUMNS:
        return {"ok": False, "denied": True, "rule": "source_columns_empty",
                "why": "源表列一条都没有 ⇒ **空样本不按绿**（空清单不是通过，是没测到）"}
    cols = tuple(str(c) for c in SOURCE_TABLE_COLUMNS)
    blank = [c for c in cols if not c.strip()]
    if blank:
        return {"ok": False, "denied": True, "rule": "source_column_blank",
                "columns": list(cols), "why": "列名里有空串 ⇒ 列契约不许留空"}
    if len(set(cols)) != len(cols):
        return {"ok": False, "denied": True, "rule": "source_column_duplicate",
                "columns": list(cols), "why": "同一个列名出现两次 ⇒ 列契约不许重复"}
    base = tuple(SOURCE_TABLE_COLUMNS_OWNER)
    if list(cols[:len(base)]) != list(base):
        return {"ok": False, "denied": True, "rule": "source_column_order_changed",
                "columns": list(cols), "owner": list(base),
                "why": "**基列**（主人逐字给过的那三列）不许重排、不许删、不许改 ⇒ "
                       "只允许在**末尾追加**"}
    extra = [c for c in cols[len(base):]]
    if extra:
        appends = [dict(a) for a in SOURCE_TABLE_COLUMNS_APPENDS]
        named = [str(a.get("name") or "") for a in appends]
        if named != extra:
            return {"ok": False, "denied": True,
                    "rule": "source_column_append_unsourced",
                    "extra": extra, "registered": named,
                    "why": "追加的列**没登记**（没写明是谁给的）⇒ 列契约不许我臆造"}
        missing = [str(a.get("name")) for a in appends
                   if not str(a.get("source") or "").strip()]
        if missing:
            return {"ok": False, "denied": True,
                    "rule": "source_column_append_without_source",
                    "missing": missing,
                    "why": "追加的列**没有出处** ⇒ 每条追加都要能追到『谁给的、哪一轮』"}
    mixed = sorted(set(cols) & set(SECTION2_COLUMNS))
    if mixed:
        return {"ok": False, "denied": True, "rule": "source_columns_merged_into_local",
                "mixed": mixed,
                "why": "源表的列**混进了**本仓第二节的列 ⇒ 两张表被合并"
                       "（**并排记，不许当同一个**）"}
    note = str(SOURCE_TABLE_COLUMNS_NOTE or "")
    if "并排记" not in note or "不许当同一个" not in note:
        return {"ok": False, "denied": True, "rule": "source_columns_vs_local_unstated",
                "why": "必须写明源表列与本仓第二节列**并排记、不许当同一个**"}
    return {"ok": True, "readonly": True, "columns": list(cols), "count": len(cols),
            "owner_columns": list(SOURCE_TABLE_COLUMNS_OWNER),
            "appends": [dict(a) for a in SOURCE_TABLE_COLUMNS_APPENDS],
            "local_columns": list(SECTION2_COLUMNS), "same_table": False,
            "note": SOURCE_TABLE_COLUMNS_NOTE}


def check_truncated_fragments() -> dict:
    """闸⑰（R-H334）：**截断碎片** —— 必写「留空不编」与「等主人补全」 · 碎片**不许落进任何数据面** · 空样本不按绿。

    为什么单立：主人消息被截断是常态。碎片最容易被当数据用（『工具』看着就像列名或工具名）。
    ⚠️ 比对**只认整串相等**：碎片多半是某个更长串的**前缀**（工具 ⊂ 工具名 ⊂ AI辅助编程工具），
    用包含比对会大面积误报 —— 判据要卡在真问题上。
    """
    items = list(TRUNCATED_FRAGMENTS)
    if not items:
        return {"ok": False, "denied": True, "rule": "truncated_all_resolved_or_empty",
                "why": "一条截断碎片都没有：要么全补全了（那就该清空），要么根本没登记"
                       "⇒ **空样本不按绿**"}
    surfaces = []
    for r in CATEGORY_ROWS_OWNER:
        surfaces.append(("分类名", str(r.get("category") or "").strip()))
        for k, v in dict(r.get("cells") or {}).items():
            surfaces.append(("格 %s" % k, str(v or "").strip()))
    for c in SOURCE_TABLE_COLUMNS:
        surfaces.append(("源表列名", str(c).strip()))
    for c in SECTION2_COLUMNS:
        surfaces.append(("第二节列名", str(c).strip()))
    for c in CATEGORIES_OWNER:
        surfaces.append(("R-H285 分类名", str(c).strip()))
    out = []
    for it in items:
        tok = str(it.get("token") or "").strip()
        note = str(it.get("note") or "").strip()
        if not tok:
            return {"ok": False, "denied": True, "rule": "truncated_token_missing",
                    "why": "截断碎片必须写明**截断出来的原文**"}
        if "留空不编" not in note:
            return {"ok": False, "denied": True, "rule": "truncated_without_hold_note",
                    "token": tok, "why": "截断碎片必须写明「**留空不编**」（碎片不是数据）"}
        # 🔴 R-H384 同刀修正：这条牙原来对**所有**碎片都要求「等主人补全」，
        #    可 `fence`（格式残片）**没有「补全」这一说** ⇒ 按形态分流
        #    （与 `local_row`/`near_row` 那种「两种形态不许混」同族）。
        if str(it.get("kind") or "") != "fence" and "补全" not in note:
            return {"ok": False, "denied": True, "rule": "truncated_without_wait_note",
                    "token": tok, "why": "截断碎片必须写明「**等主人补全**」（不许替主人补）"}
        # 🆕 R-H384：碎片**加 `kind`**（truncated = 没说完 / fence = 格式残片）——
        #    两种形态的**处理纪律不同**：截断等主人补全、格式残片是**复制粘贴痕迹**；
        #    ⚠️ 只在**写了 kind** 时才管（判据别扩大化）；排在本闸判据的最后。
        _kind = str(it.get("kind") or "").strip()
        if _kind and _kind not in FRAGMENT_KINDS:
            return {"ok": False, "denied": True, "rule": "fragment_kind_unknown",
                    "token": tok, "value": _kind,
                    "why": "碎片形态只能是 %s 之一" % " / ".join(FRAGMENT_KINDS)}
        if _kind == "fence" and ("留空不编" not in note or "格式" not in note):
            return {"ok": False, "denied": True, "rule": "fence_fragment_note_incomplete",
                    "token": tok,
                    "why": "格式残片必须写明「**留空不编**」+「**格式**残片」"
                           "（它是复制粘贴痕迹，不是数据）"}
        landed = [where for where, val in surfaces if val == tok]
        if landed:
            return {"ok": False, "denied": True, "rule": "truncated_fragment_landed",
                    "token": tok, "where": landed,
                    "why": "截断碎片**落进了数据面** ⇒ 碎片不许当分类名 / 列名 / 格值（留空不编）"}
        out.append({"token": tok, "at": str(it.get("at") or "") or None,
                    "ctx": str(it.get("ctx") or "") or None,
                    "note": note, "resolved": None})
    # 🆕 R-H403：**表头残片一族**（现算不手写）—— 那张表的列名在逐个到货
    # 🔴 同刀修正：第一版按 **note 里的「表头/列名」** 找 ⇒ 把「**不像**表头」那种话也吃进来
    #    （实测混进 工具/原语/工程哲学/用例/text 等 5 条）⇒ 改成**结构化字段** `header`
    _hdr = [str(_i.get("token")) for _i in items if _i.get("header")]
    return {"ok": True, "readonly": True, "items": out, "count": len(out),
            "header_fragments": _hdr, "note": TRUNCATED_FRAGMENTS_NOTE}


def check_source_order_readings() -> dict:
    """闸⑲（R-H346）：**顺序读数** —— 源编号 vs 本仓位置，**双向带牙**。

    为什么单立：主人给的**源仓库编号**（『2. AI 模型管理工具』）是一条**新事据**，
    但它最容易被顺手当成「许可」—— 拿编号去重排本仓表。**读数 ≠ 许可**。
      · 编号与位置**不一致** ⇒ 必须写明「不一致」（不许静默）
      · 写了「不一致」而盘上**其实一致** ⇒ 也红（旧读数不许留着装样子）
    `our_index` **由本闸现算、不手写** ⇒ 表一旦被重排，这条读数立刻见红（逼你显式更新）。
    """
    items = list(SOURCE_ORDER_READINGS)
    if not items:
        return {"ok": False, "denied": True, "rule": "source_order_readings_empty",
                "why": "一条顺序读数都没有：要么没登记，要么全清了 ⇒ **空样本不按绿**"}
    order = [str(r.get("category") or "").strip() for r in CATEGORY_ROWS_OWNER]
    out = []
    for it in items:
        cat = str(it.get("category") or "").strip()
        if not cat:
            return {"ok": False, "denied": True, "rule": "source_order_category_missing",
                    "why": "顺序读数必须写明**是哪个分类**"}
        # 🆕 R-H363：允许**显式声明「本仓无此行」**（`local_row: None`）——
        #    现场：源编号 4 的名字本仓没有 ⇒ 那不叫「读数悬空」，那叫**一条读数**；
        #    但**必须写明**「本仓无此行」，否则仍判红（不许默认沉默）
        # ⚠️ R-H363 现场：新判据**必须放在 `note` 赋值之后** ——
        #    第一版插在前面 ⇒ 循环里读到的是**上一条的 note**（变量泄漏）⇒ 四条用例一起红
        source_no = it.get("source_no")
        note = str(it.get("note") or "")
        # ⚠️ R-H369 现场：`no_local` 与 `near_row` 是**两种互斥形态** ——
        #    第一版没互斥 ⇒ 「近似行」那条被 no_local 分支拦住（要求写「本仓无此行」，可它是近似行）
        near_row = str(it.get("near_row") or "").strip()
        no_local = ((not near_row) and ("local_row" in it)
                    and (it.get("local_row") is None))
        if no_local:
            if "本仓无此行" not in note:
                return {"ok": False, "denied": True,
                        "rule": "source_order_no_local_row_unstated",
                        "category": cat,
                        "why": "声明了 local_row=None（本仓无此行），就必须**写明**"
                               "「本仓无此行」（不许默认沉默）"}
        # 🆕 R-H378：**像但不等价的候选行** `near_names`（与 `near_row` 对称的第四种形态）——
        #    `near_row` 是「本仓有一行**几乎就是它**」；`near_names` 是「本仓有**几处像的**，
        #    但**一行都不是它**」。三条牙：候选必须**真的在本仓** / 候选不许**等于源名**
        #    （那说明本仓其实有这一行）/ 必须写明「像但不等于」或「不许当同一个」。
        #    ⚠️ 只在**写了候选**时才管（判据别扩大化）。
        _near_names = [str(_c).strip() for _c in (it.get("near_names") or ())
                       if str(_c).strip()]
        # 🔴 R-H378 同刀自查（**判据顺序**）：第一版我先判「候选在不在本仓」、再判
        #    「候选是不是源名本身」⇒ 那条「候选=源名」的牙**永远打不到**：
        #    候选名等于源名时，源名必然**不在**本仓（这正是 no_local 的前提）
        #    ⇒ 先被 `..._unknown` 拦住 ⇒ 那条牙**空转**（一条永远不会响的牙 = 假纪律）。
        #    改成**先判「是不是源名本身」，再判「在不在本仓」**。
        #    （同一族第 3 次：判据的**顺序**自己就是判据的一部分 —— R-H338 / R-H376 各一次）
        for _nn in _near_names:
            if _nn == cat:
                return {"ok": False, "denied": True,
                        "rule": "source_order_near_names_is_row",
                        "category": cat, "near_name": _nn,
                        "why": "候选名**与源名一样** ⇒ 说明本仓**其实有这一行**"
                               "⇒ 那就该走 `local_row`，不许一边写「无此行」一边把它当候选"}
            if _nn not in order:
                return {"ok": False, "denied": True,
                        "rule": "source_order_near_names_unknown",
                        "category": cat, "near_name": _nn,
                        "why": "写了候选行，但它**不在本仓表里** ⇒ 候选必须是真的"
                               "（不许拿一个不存在的行来凑）"}
        if _near_names and "像但不等于" not in note and "不许当同一个" not in note:
            return {"ok": False, "denied": True,
                    "rule": "source_order_near_names_unstated",
                    "category": cat, "near_names": _near_names,
                    "why": "写了候选行，就必须写明「**像但不等于**」或「**不许当同一个**」"
                           "（像但不等于要摆出来）"}
        if not no_local and not near_row and cat not in order:
            return {"ok": False, "denied": True, "rule": "source_order_category_unknown",
                    "category": cat,
                    "why": "这条读数指着**本仓表里没有的分类** ⇒ 读数悬空"
                           "（确属「本仓无此行」请**显式**写 local_row=None）"}
        # 🆕 R-H369：**近似行** near_row —— 源名与本仓某行**像但不等于**时用；
        #    现场：源『文档与知识库工具』 vs 本仓『文档和知识库工具』（**一字之差**）
        if near_row:
            if near_row not in order:
                return {"ok": False, "denied": True,
                        "rule": "source_order_near_row_unknown",
                        "category": cat, "near_row": near_row,
                        "why": "写了近似行，但它**不在本仓表里** ⇒ 近似行必须是真的"
                               "（不许拿一个不存在的行来凑）"}
            if "一字之差" not in note and "疑似对应" not in note:
                return {"ok": False, "denied": True,
                        "rule": "source_order_near_row_unstated",
                        "category": cat, "near_row": near_row,
                        "why": "写了近似行，就必须写明「**一字之差**」或「**疑似对应**」"
                               "（像但不等于要摆出来）"}
            if near_row == cat:
                return {"ok": False, "denied": True,
                        "rule": "source_order_renamed_local_row",
                        "category": cat, "near_row": near_row,
                        "why": "近似行**与源名一模一样** ⇒ 说明本仓行名被**拿源名改过**"
                               "（🔴 不许拿源名改本仓行名）"}
        our_index = None if (no_local or near_row) else (order.index(cat) + 1)
        # 🆕 R-H363：`our_index=None`（本仓无此行）**也算不一致**
        mismatch = (our_index is None) or (not isinstance(source_no, int)) \
            or (source_no != our_index)
        if mismatch and "不一致" not in note:
            return {"ok": False, "denied": True, "rule": "source_order_mismatch_unstated",
                    "category": cat, "source_no": source_no, "our_index": our_index,
                    "why": "源编号与本仓位置**不一致** ⇒ 必须写明「不一致」（不许静默）"}
        # 🆕 R-H352：**括号词与旧批的机械判定**（**双向**，两条各写各的）
        #    命中旧批分类名 ⇒ 必须写明「对应」（跨批对应是**强证据**，不许含糊）
        #    没命中        ⇒ 必须写明「不是」（不许默认沉默，R-H346 现场）
        # 🔴 R-H377 同刀自查（**牙名与实现不符**）：这条牙叫「**括号词**与旧批的机械判定」，
        #    实现却是「**整条 note** 里有没有出现旧批分类名」——
        #    现场：源 6 的**源名**里就含旧批名『网络加速』，而**括号词**『环境优化』一个都没命中
        #    ⇒ 牙是被**源名**（以及我自己写的括号核说明里的『环境配置』）喂响的，
        #    **不是**被括号词喂响的 ⇒ 本刀**只报不改**（收窄它会牵动 4 条历史读数的措辞，
        #    属「不为读数好看批量改历史」），改为加**派生读数**把「是什么喂响的」摆出来；
        #    要不要收窄这条牙，**等主人一句话**。
        _paren = str(it.get("paren") or "").strip()
        hit_old = [c for c in CATEGORIES_OWNER if c in note]
        hit_in_paren = [c for c in hit_old if _paren and c in _paren]
        if hit_old and "对应" not in note:
            return {"ok": False, "denied": True,
                    "rule": "source_order_old_batch_hit_unstated",
                    "category": cat, "hit": hit_old,
                    "why": "括号词**命中了 R-H285 那批的分类名** ⇒ 必须写明「**对应**」"
                           "（跨批对应是**强证据**，不许含糊）"}
        if not hit_old and "不是" not in note:
            return {"ok": False, "denied": True,
                    "rule": "source_order_old_batch_miss_unstated",
                    "category": cat,
                    "why": "括号词**没命中**那批分类名 ⇒ 必须写明「**不是**」"
                           "（不许默认沉默）"}
        if not mismatch and "不一致" in note:
            return {"ok": False, "denied": True, "rule": "source_order_stale_note",
                    "category": cat, "source_no": source_no, "our_index": our_index,
                    "why": "note 里写着「不一致」，但盘上**其实一致** ⇒ 旧读数不许留着装样子"
                           "（表若被重排过，请**显式**更新这条读数）"}
        # 🆕 R-H381：**同一个源名出现两次**（源 2 与源 7 只差一个空格）——
        #    归一化（抹掉空格）后同名 ⇒ **必须在 note 里写明「只差一个空格/同名」**，
        #    且 🔴 **不许当同一个、不许合并**。
        #    ⚠️ 只在**真的出现重复**时才管（判据别扩大化）；
        #    🔧 同刀修正：它**排在最后**（先具体后通用 —— 与 R-H338/R-H376 同族：
        #    第一版放在最前 ⇒ 老用例（想验「旧批」「位置不一致」那些具体牙）全被它先拦住）
        _norm = cat.replace(" ", "")
        _dups = [str(_o.get("source_no")) for _o in items
                 if str(_o.get("category") or "").replace(" ", "") == _norm]
        if len(_dups) > 1 and ("只差一个空格" not in note and "同名" not in note):
            return {"ok": False, "denied": True,
                    "rule": "source_order_duplicate_name_unstated",
                    "category": cat, "source_nos": _dups,
                    "why": "源表里出现了**归一化后同名**的两条读数"
                           "⇒ 必须写明「同名」或「只差一个空格」，"
                           "且**不许当同一个、不许合并**"}
        out.append({"category": cat, "source_no": source_no, "our_index": our_index,
                    "mismatch": mismatch, "note": note, "resorted": False,
                    # 🆕 R-H377：括号词（主人逐字给的）与「旧批命中来源」都带出来，
                    #    否则审计读数只能靠猜（R-H368 教训：判据读的字段必须带出来）
                    "paren": _paren or None,
                    "old_batch_hits": hit_old,
                    "old_batch_hits_in_paren": hit_in_paren,
                    # 🆕 R-H378：候选行（像但不等价）也带出来（判据读它，就得带）
                    "near_names": _near_names,
                    # 🆕 R-H369：形态字段要**随条目带出来**（否则用例/复核读到 None；
                    #    与 R-H368 的 `echo_claim` 是同一处教训：**出口与判据不许各说各话**）
                    "local_row": it.get("local_row", "auto"),
                    "near_row": str(it.get("near_row") or "") or None})
    return {"ok": True, "readonly": True, "items": out, "count": len(out),
            "mismatched": [x["category"] for x in out if x["mismatch"]],
            # 🆕 R-H377：**括号核审计**（派生 · 现算不手写）——
            #    「旧批命中」到底来自**括号词**，还是来自**源名 / 我自己的说明**？
            #    ⚠️ 它只是读数（判据仍是那两条 `...old_batch_*_unstated`）
            "source_order_paren_audit": {x["category"]: {
                "paren": x["paren"], "hits_in_note": x["old_batch_hits"],
                "hits_in_paren": x["old_batch_hits_in_paren"]} for x in out},
            # 🆕 R-H378：**像但不等价的候选行**（派生 · 现算不手写）——
            #    「哪些源分类在本仓连一行都不对应、但有几处像的」一眼可见；
            #    ⚠️ 它只是读数（判据仍是那三条 `...near_names_*`）
            "source_order_near_names": {x["category"]: x["near_names"]
                                        for x in out if x["near_names"]},
            # 🆕 R-H381：**归一化（抹空格）后同名的源分类**（派生 · 现算不手写）——
            #    「源表里同一个名字（的两种写法）出现了几次」一眼可见；
            #    ⚠️ 它只是读数（判据是 `source_order_duplicate_name_unstated`）
            "duplicate_source_names": {
                _n: sorted(x["source_no"] for x in out
                           if str(x["category"]).replace(" ", "") == _n)
                for _n in sorted({str(x["category"]).replace(" ", "") for x in out})
                if len({x["source_no"] for x in out
                        if str(x["category"]).replace(" ", "") == _n}) > 1},
            "note": SOURCE_ORDER_READINGS_NOTE}


# 🔴 R-H383：**近似介绍句**的机械口径（只给读数用，**不当判据**）——
#    去掉空白/标点后，两句的最长公共子串长度 ≥ `NEAR_MIN` 就算「近」。
#    ⚠️ 它会被**共用专有名词**喂饱（实测两例）⇒ **判据另立**（`detail_family` 是人工判的骨架家族）。
NEAR_MIN = 6
_NORM_RE = re.compile(r"[\s\W_]+", re.UNICODE)


def _norm_text(s) -> str:
    return _NORM_RE.sub("", str(s or ""))


def _lcs(a: str, b: str) -> str:
    """最长公共子串（只给读数用）。"""
    best = ""
    prev = [0] * (len(b) + 1)
    for _i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for _j in range(1, len(b) + 1):
            if a[_i - 1] == b[_j - 1]:
                cur[_j] = prev[_j - 1] + 1
                if cur[_j] > len(best):
                    best = a[_i - cur[_j]:_i]
            else:
                cur[_j] = 0
        prev = cur
    return best


def _near_pairs(out) -> list:
    """近似介绍句配对（读数）：样例 + 长度都摆出来，**好让人一眼看出它被什么喂饱**。"""
    pairs = []
    _with = [(x["token"], _norm_text(x.get("staged_detail"))) for x in out
             if x.get("staged_detail")]
    for _i in range(len(_with)):
        for _j in range(_i + 1, len(_with)):
            _a, _b = _with[_i][1], _with[_j][1]
            _c = _lcs(_a, _b)
            if len(_c) >= NEAR_MIN:
                pairs.append({"a": _with[_i][0], "b": _with[_j][0],
                              "len": len(_c), "sample": _c})
    return pairs


def check_reappearing_tokens() -> dict:
    """闸⑱（R-H336）：**再现名字** —— 主人又给了一个**盘上已经有**的名字。

    为什么单立：同一个名字第二次出现时有两个**对称**的失手 ——
      ① **另起一行**（把已有的当成新的 ⇒ 重复建行 / 重复登记）
      ② **当重复丢掉**（把主人这次的重复当噪音 ⇒ 证据丢了）
    两条都不许 ⇒ 只能**并排记** + 写清「已在哪儿」。
    ⚠️ 判据卡在真问题上：条目说「已在」，就必须**真的在盘上按整段找得到** ——
    用包含比对会把『Trae 等』也算成『Trae』（前缀假命中）。
    """
    items = list(REAPPEARING_TOKENS)
    if not items:
        return {"ok": False, "denied": True, "rule": "reappearing_all_resolved_or_empty",
                "why": "一条再现名字都没有：要么没登记（= 把主人这次的话丢了），"
                       "要么全清了 ⇒ **空样本不按绿**"}
    surfaces = []
    # 🔧 R-H348：**面名带行号** —— 原来只写「格 代表工具」⇒ 第 1 行与第 3 行**同名**，
    #    于是 `same_cell_groups` 按列名分组会把两行**混成一组**（跨行扩大化，实测已见）。
    cell_pieces = []
    for i, r in enumerate(CATEGORY_ROWS_OWNER, 1):
        surfaces.append(("分类名", str(r.get("category") or "").strip()))
        for k, v in dict(r.get("cells") or {}).items():
            surfaces.append(("第%d行 格 %s" % (i, k), str(v or "")))
            for piece in str(v or "").split("/"):
                piece = piece.strip()
                if piece:
                    cell_pieces.append((str(r.get("category") or ""), k, piece))
    for it in PENDING_ATTRIBUTION:
        if it.get("staged_value"):
            surfaces.append(("待归属暂存值", str(it.get("staged_value"))))
    for c in SOURCE_TABLE_COLUMNS:
        surfaces.append(("源表列名", str(c)))
    for c in SECTION2_COLUMNS:
        surfaces.append(("第二节列名", str(c)))
    # 🆕 R-H359：**我方 R-H285 那批（KEY_TOOLS）也算「盘上已有」的一处来源**
    #    现场：「Huobao Drama」只在 KEY_TOOLS 里、不在任何格值里
    #    ⇒ 不补这一处，它会被判成「写了已在却找不到」（假红）
    for t in KEY_TOOLS:
        surfaces.append(("我方 R-H285 工具名单", str(t.get("name") or "")))
    out = []
    seen: set = set()
    for it in items:
        tok = str(it.get("token") or "").strip()
        note = str(it.get("note") or "")
        # 🆕 R-H340：**同一个名字不许在再现区登记两遍**（重复登记会让计数虚高）
        if tok and tok in seen:
            return {"ok": False, "denied": True,
                    "rule": "reappearing_token_duplicate", "token": tok,
                    "why": "**同一个名字在再现区登记了两遍** ⇒ 计数会虚高"
                           "（再现区是**去重**的：一个名字一条）"}
        seen.add(tok)
        if not tok:
            return {"ok": False, "denied": True, "rule": "reappearing_token_missing",
                    "why": "再现条目必须写明**是哪个名字**"}
        if "已在" not in note or "再现" not in note:
            return {"ok": False, "denied": True, "rule": "reappearance_note_incomplete",
                    "token": tok,
                    "why": "必须写明「**已在**…」与「**再现**」两件（不然它会被当成新工具）"}
        # 🆕 R-H350：**变体必须写明「变体」** —— 一个名字若是我方 KEY_TOOLS 某条的**变形**
        #    （抹平空格 / 连字符 / 大小写后**前缀一致、整串更长**）⇒ note 里要写「变体」，
        #    否则会被当成「同一个」或「另一个新工具」（**两侧都错**）
        def _nz(s: str) -> str:
            return str(s or "").replace(" ", "").replace("-", "").lower()
        variant_of = [t["name"] for t in KEY_TOOLS
                      if _nz(tok) != _nz(t["name"])
                      and _nz(tok).startswith(_nz(t["name"]))]
        if variant_of and "变体" not in note:
            return {"ok": False, "denied": True,
                    "rule": "reappearance_variant_unstated", "token": tok,
                    "of": variant_of,
                    "why": "这是 KEY_TOOLS 某条的**变体**（前缀一致、整串更长）⇒ "
                           "note 必须写明「**变体**」（与谁、差在哪）"}
        # 🆕 R-H337：主人给的**详细介绍**只许**暂存**，且**一个字都不许落表**
        #    ⚠️ 长句用**整句包含**比对（短词才用整段相等）—— 两种口径各自写清，别混
        staged = str(it.get("staged_detail") or "").strip()
        # 🆕 R-H376：**第二句**（并排的那句）—— 它也是主人给的资料，同受「暂存不落表」管
        staged_x = str(it.get("staged_detail_extra") or "").strip()
        snote = str(it.get("staged_detail_note") or "").strip()
        if staged:
            # 🆕 R-H349：**归属依据必须写明** —— 主人**没点名**时，
            #    「为什么挂在这条上」是**推断**，不许当判定（牙只认「有没有写」，不认哪种依据）
            if "归属依据" not in snote:
                return {"ok": False, "denied": True,
                        "rule": "staged_detail_without_owner_basis", "token": tok,
                        "why": "挂了详细介绍，却**没写明归属依据** ⇒ 推断会被当成判定"}
            if "暂存" not in snote or "不落" not in snote:
                return {"ok": False, "denied": True,
                        "rule": "staged_detail_without_hold_note", "token": tok,
                        "why": "暂存的详细介绍必须写明「**暂存、不落表**」"
                               "（否则它会悄悄变成已落）"}
            # 🆕 R-H376：**两句一起查**（空串会「命中一切」⇒ 必须各自非空才算）
            landed = [name for name, val in surfaces
                      if (staged and staged in str(val))
                      or (staged_x and staged_x in str(val))]
            if landed:
                return {"ok": False, "denied": True, "rule": "staged_detail_landed",
                        "token": tok, "where": landed,
                        "why": "主人给的**详细介绍落进了表** ⇒ 归属没定就一个字都不许落"
                               "（**暂存 ≠ 已落**）"}
        dup = [str(r.get("category") or "").strip() for r in CATEGORY_ROWS_OWNER
               if str(r.get("category") or "").strip() == tok]
        if dup:
            return {"ok": False, "denied": True,
                    "rule": "reappearing_token_became_new_row", "token": tok,
                    "why": "**另起了一行**（把已有的名字当新分类建行）⇒ 再现的名字不许建新行"}
        where = [name for name, val in surfaces
                 if any(seg.strip() == tok for seg in str(val).split("/"))]
        if not where:
            return {"ok": False, "denied": True,
                    "rule": "reappearance_claim_without_match", "token": tok,
                    "claimed_in": [name for name, val in surfaces if tok in str(val)],
                    "why": "写了「已在」但盘上**按整段比对找不到**（只有前缀巧合）⇒ "
                           "这条『再现』就是编的"}
        near = [name for name, val in surfaces
                if tok in str(val) and name not in where]
        # ⚠️ R-H338 现场：第一版写成「按**列名**取」⇒ 把**别的行**的同名列也串进来
        #    （19 个「伙伴」里混进了别的行的工具）—— 判据扩大化。
        #    改成：只从 **token 整段所在的那一格**取伙伴。
        mate_vals = [str(val) for name, val in surfaces
                     if name in where
                     and any(seg.strip() == tok for seg in str(val).split("/"))]
        mates = sorted({p.strip() for val in mate_vals for p in str(val).split("/")
                        if p.strip() and p.strip() != tok})
        # 🆕 R-H382：**同一个名字被投喂几次，必须写出来** ——
        #    重复投喂最容易出的两种失手：① **静默吞掉**（当噪音）② **当成新证据**
        #    ⇒ 次数 ≥2 时，note 里必须写明「第二次 / 再次 / 多次」；
        #    ⚠️ 只在**次数 ≥2** 时才管（判据别扩大化）；
        #    🔧 排在**每条判据的最后**（先具体后通用 —— 本族第 5 次的教训：R-H338/R-H376/R-H378/R-H381）。
        _times = it.get("reappearance_times", 1)
        if not isinstance(_times, int) or _times < 1:
            return {"ok": False, "denied": True, "rule": "reappearance_times_invalid",
                    "token": tok, "value": _times,
                    "why": "「被投喂次数」必须是 ≥1 的整数（不许自造）"}
        if _times >= 2 and not any(w in note for w in ("第二次", "再次", "多次")):
            return {"ok": False, "denied": True, "rule": "reappearance_repeat_unstated",
                    "token": tok, "times": _times,
                    "why": "同一个名字被投喂了 **%d 次**，note 里却看不出重复 "
                           "⇒ 重复既不许**静默吞掉**、也不许被当成**新证据**"
                           "（必须写明「第二次 / 再次 / 多次」）" % _times}
        # 🆕 R-H383：**同骨架的介绍句**（`detail_family`）——
        #    现场：R-H360 的牙只抓**逐字相同**，**近似（同骨架）它抓不到** ⇒ 那是个口子。
        #    自动近似检测（最长公共子串）会**被专有名词喂饱**
        #    （实测：CC Switch ↔ OpenClaw Monitor 命中的是「OpenClaw」这个词；
        #      Watt Toolkit ↔ FastGithub 命中的是「GitHub加速」）
        #    ⇒ **不立自动牙**，改**结构化**：家族由人判、写进 `detail_family`，
        #    牙齿只查「同一家族的条目有没有写明『同骨架』」。
        #    ⚠️ 只在**真的出现同家族 ≥2 条**时才管（判据别扩大化）。
        _fam = str(it.get("detail_family") or "").strip()
        if _fam:
            _same = [str(_o.get("token")) for _o in items
                     if str(_o.get("detail_family") or "").strip() == _fam]
            if len(_same) > 1:
                _tr = note + "\n" + str(it.get("staged_detail_note") or "")
                if "同骨架" not in _tr and "不新增事实" not in _tr:
                    return {"ok": False, "denied": True, "rule": "detail_family_unstated",
                            "token": tok, "family": _fam, "same_family": _same,
                            "why": "同一骨架家族有 %d 条，却**没写明「同骨架」或"
                                   "「不新增事实」** ⇒ 近似重复会被当成**两条独立介绍**"
                                   % len(_same)}
        out.append({"token": tok, "at": str(it.get("at") or "") or None,
                    # 🆕 R-H382：次数也带出来（判据读它，就得带）
                    "reappearance_times": _times,
                    # 🆕 R-H383：介绍句骨架家族也带出来（判据读它，就得带）
                    "detail_family": (str(it.get("detail_family") or "") or None),
                    "where": where, "near_miss": near,
                    "duplicated_elsewhere": len(where) > 1,
                    "staged_detail": staged or None,
                    "staged_detail_extra": staged_x or None,
                    # 🆕 R-H376：第二句**自己那一轮**要跟着条目带出来（判据读它，就得带）
                    "staged_detail_extra_round": (str(it.get("staged_detail_extra_round") or "")
                                                 or None),
                    # 🆕 R-H379：位置读数也带出来（判据读它，就得带）
                    "detail_position": (str(it.get("detail_position") or "") or None),
                    # 🆕 R-H380：「与紧随其后的名字」的关系也带出来（那是**读数**）
                    "detail_next_name_side": (str(it.get("detail_next_name_side") or "")
                                              or None),
                    "staged_detail_note": snote or None,
                    "cell_mates": mates or None,
                    # 🆕 R-H368：呼应声明要**随条目带出来**，否则牙与用例都读到 None
                    "echo_claim": it.get("echo_claim"),
                    "note": note, "resolved": None})
    # 🆕 R-H374：**带介绍必须能说出「哪一轮给的」**（可追溯）——
    #    与「有值的格必须能追到出处」同族：介绍也是**主人给的资料**，必须有出处。
    for x in out:
        if not x.get("staged_detail"):
            continue
        _trace = str(x.get("note") or "") + "\n" + str(x.get("staged_detail_note") or "")
        if not re.search(r"R-H\d{3}", _trace):
            return {"ok": False, "denied": True, "rule": "detail_without_round",
                    "token": x["token"],
                    "why": "这条挂着介绍，却说不出是**哪一轮**给的 ⇒ 与「有值的格必须有出处」"
                           "同族（介绍也是主人给的资料，必须有出处）"}
    # 🆕 R-H375：**介绍里点名了我方真身，就必须真的在盘上**（机械）——
    #    与再现侧「条目说『已在』就必须真在盘上按整段找得到」**对称**：
    #    不许拿一个**盘上不存在**的东西当呼应证据（那叫口说无凭）。
    _asset_map = dict(LOCAL_ASSETS)
    for x in out:
        for _name in _local_refs(x.get("staged_detail")):
            if not _asset_ok(_asset_map[_name]):
                return {"ok": False, "denied": True, "rule": "local_ref_unverified",
                        "token": x["token"], "asset": _name,
                        "why": "这条介绍点名了我方真身，可它在盘上**找不到**（或为空）"
                               "⇒ 不许拿不存在的东西当呼应证据"}
    # 🆕 R-H376：**第二句的规矩**（同一介绍再补一句时）——
    #    ① 不许**覆盖**第一句：第一句留在 `staged_detail`、第二句进 `staged_detail_extra`，
    #       且 note 必须写明「**第二句**」（否则第二句会被当成第一句的改写）；
    #    ② 第二句不许与第一句**逐字相同**（同一句记两遍 = 假增）；
    #    ③ **每句都要能说出自己那一轮** ⇒ trace 里必须出现**两个不同的** R-H3xx。
    for x in out:
        _x = str(x.get("staged_detail_extra") or "").strip()
        if not _x:
            continue
        if "第二句" not in str(x.get("staged_detail_note") or ""):
            return {"ok": False, "denied": True,
                    "rule": "detail_extra_without_second_mark", "token": x["token"],
                    "why": "挂了**第二句**却没写明「第二句」 ⇒ 它会被当成第一句的"
                           "**改写**（并排记 ≠ 悄悄换掉）"}
        if _x == str(x.get("staged_detail") or "").strip():
            return {"ok": False, "denied": True,
                    "rule": "detail_extra_duplicating_first", "token": x["token"],
                    "why": "**第二句**与第一句逐字相同 ⇒ 同一句记两遍，不是新证据"}
        # 🔴 R-H376 同刀自查（**判据太松**）：第一版我写成「trace 里出现 ≥2 个不同的
        #    R-H3xx」⇒ 被**无关的轮次引用**喂饱 —— 那条 note 里本来就有「R-H285 那批」
        #    ⇒ 我把 R-H376 抹掉之后，读数仍是 {R-H285, R-H375} 两条，**牙不响**（假过）。
        #    改成**结构化**：第二句必须自带 `staged_detail_extra_round`（形如 R-H3xx），
        #    且那个轮次必须**在正文里也说得出**（不许只挂在字段上）。
        _xr = str(x.get("staged_detail_extra_round") or "").strip()
        if not re.fullmatch(r"R-H\d{3}", _xr):
            return {"ok": False, "denied": True,
                    "rule": "detail_extra_without_own_round", "token": x["token"],
                    "value": _xr or None,
                    "why": "**第二句没写明自己那一轮**"
                           "（`staged_detail_extra_round` 必须是 R-H3xx）"
                           "⇒ 每句都要能说出自己那一轮（与「有值的格必须有出处」同族）"}
        if _xr not in (str(x.get("note") or "") + "\n"
                       + str(x.get("staged_detail_note") or "")):
            return {"ok": False, "denied": True,
                    "rule": "detail_extra_round_unstated", "token": x["token"],
                    "round": _xr,
                    "why": "第二句的出处只写在**字段**上 ⇒ 正文里也要说得出那一轮"
                           "（字段与正文不许各说各话）"}
    # 🆕 R-H379：**位置读数**（介绍相对它那个名字**在消息里的位置**）——
    #    现场：本刀那句介绍紧接在**下一个名字之前**，却属于**上一个**名字 ⇒
    #    「紧跟其后」**不再是唯一形态** ⇒ 位置提成**字段**，正文必须与它**同一口径**。
    #    ① 值必须合法（after_name / before_next_name）；
    #    ② 声明了位置 ⇒ 正文里必须写出**对应说法**（不许字段与正文两套话）。
    for x in out:
        _pos = str(x.get("detail_position") or "").strip()
        if not _pos:
            continue
        if _pos not in DETAIL_POSITIONS:
            return {"ok": False, "denied": True, "rule": "detail_position_unknown",
                    "token": x["token"], "value": _pos,
                    "why": "位置读数只能是 %s 之一 ⇒ 不许自造第三种"
                           % " / ".join(DETAIL_POSITIONS)}
        _trace = str(x.get("note") or "") + "\n" + str(x.get("staged_detail_note") or "")
        _side = str(x.get("detail_next_name_side") or "").strip()
        if _side and _side not in DETAIL_NEXT_NAME_SIDES:
            return {"ok": False, "denied": True,
                    "rule": "detail_next_name_side_unknown", "token": x["token"],
                    "value": _side,
                    "why": "「与紧随其后的名字」的读数只能是 %s 之一"
                           % " / ".join(DETAIL_NEXT_NAME_SIDES)}
        _want = DETAIL_POSITION_WORDS[_pos]
        if not any(_w in _trace for _w in _want):
            return {"ok": False, "denied": True, "rule": "detail_position_unstated",
                    "token": x["token"], "position": _pos, "want_any": list(_want),
                    "why": "声明了位置读数，正文里却**没写出对应说法**"
                           "⇒ 字段与正文不许各说各话"}
    # 🆕 R-H368：**呼应的声明必须与可算读数一致** —— ⚠️ 第一版拿**文字**判（note 里有没有
    #    「呼应命中」）⇒ 被**否定句**（「不许说成『呼应命中』」）误伤 ⇒ **40 条用例一起红**。
    #    ⇒ 改成**结构化字段** `echo_claim`：机器只比「声明」与「可算读数」，**不猜文字语义**。
    _own_use = _owner_use_map()
    _echo_map = {x["token"]: _echo_hit(x.get("staged_detail"), _own_use.get(x["token"]))
                 for x in out}
    for x in out:
        _claim = x.get("echo_claim")
        if _claim is True and not _echo_map.get(x["token"]):
            return {"ok": False, "denied": True,
                    "rule": "echo_claim_without_computation", "token": x["token"],
                    "why": "声明 `echo_claim=True`，但**可算读数**（≥4 字连续重合）为 False"
                           "⇒ 口说无凭（要么改成 False，要么附上真命中）"}
        if _claim is False and _echo_map.get(x["token"]):
            return {"ok": False, "denied": True,
                    "rule": "echo_denial_against_computation", "token": x["token"],
                    "why": "声明 `echo_claim=False`，但**可算读数**为 True"
                           "⇒ 把真命中说成没命中（同样是口说无凭）"}
    # 🆕 R-H360：**同一句介绍不许挂在两个名字下**（机械）——
    #    一份介绍不能认两个主：真撞上 ⇒ 说明我**挂错了**，或者主人给的其实**不是介绍**。
    _seen_detail: dict = {}
    for x in out:
        # 🆕 R-H376：**第二句也一起查重**（同一句既不许认两个主，也不许换个字段重记）
        for _d in (str(x.get("staged_detail") or "").strip(),
                   str(x.get("staged_detail_extra") or "").strip()):
            if not _d:
                continue
            if _d in _seen_detail and _seen_detail[_d] != x["token"]:
                return {"ok": False, "denied": True,
                        "rule": "staged_detail_duplicated_across_names",
                        "token": x["token"], "also": _seen_detail[_d],
                        "why": "同一句介绍挂在**两个名字**下 ⇒ 一份介绍不能认两个主"
                               "（要么我挂错了，要么它根本不是介绍）"}
            _seen_detail.setdefault(_d, x["token"])
    # 🆕 R-H338 立 · R-H340 移位：**一串里的名字不许被拆成多行**（**通用**：不限已登记的那几个）
    #    ⚠️ 原来写在**循环里面** ⇒ 会被**前一条 item**先撞上，于是「登记名建行」报的是
    #      这条通用牙、而不是更具体的 `reappearing_token_became_new_row`。
    #      移到**循环外**：**先具体、后通用**（判据的**优先级**要写清，不然报出来的不是最对症那条）。
    cat_names = {str(r.get("category") or "").strip() for r in CATEGORY_ROWS_OWNER}
    split_rows = sorted(p for p in {p for _c, _k, p in cell_pieces} if p in cat_names)
    if split_rows:
        return {"ok": False, "denied": True,
                "rule": "cell_pieces_split_into_rows",
                "rows": split_rows,
                "why": "**把一串里的名字拆成了分类行** ⇒ 一个格里的名字仍是**一个格**，"
                       "不许拆成多行（拆行 = 悄悄改了结构）"}
    return {"ok": True, "readonly": True, "items": out, "count": len(out),
            # 🆕 R-H339：**带详细介绍的条目**（派生读数，不手写）—— 让「几个工具带介绍」看得见
            "with_detail": [x["token"] for x in out if x.get("staged_detail")],
            # 🆕 R-H356：**证据强度**（派生 · 不手写）：带介绍的条数 / 再现总条数
            #    让「每个工具是不是都跟着一句介绍」这件事**可算**，而不是靠感觉
            # 🆕 R-H382：**被重复投喂的名字**（派生 · 现算不手写）——
            #    与待归属侧的 `repeat_topics` **对称**；
            #    「谁被主人又给了一遍」一眼可见；⚠️ 它只是读数（**重复 ≠ 许可**）
            "reappearance_repeat": {x["token"]: x["reappearance_times"] for x in out
                                    if x.get("reappearance_times", 1) > 1},
            # 🆕 R-H383：**介绍句骨架家族**（结构化 · 现算不手写）
            "detail_family_map": {x["token"]: x["detail_family"]
                                  for x in out if x.get("detail_family")},
            # 🆕 R-H383：**近似介绍句配对**（读数 · **明确不是判据**）——
            #    口径：去掉空白与标点后，两句的**最长公共子串 ≥ 6 字**；
            #    ⚠️ 实测它**会被共用专有名词喂饱**（CC Switch ↔ OpenClaw Monitor 命中的是
            #    「OpenClaw」；Watt Toolkit ↔ FastGithub 命中的是「GitHub加速」）
            #    ⇒ **它只是读数**：不许拿它当「近似重复」的判据（判据是 `detail_family` 那条）。
            "detail_near_pairs": _near_pairs(out),
            "detail_ratio": {"with_detail": len([x for x in out if x.get("staged_detail")]),
                             "total": len(out),
                             "ratio": round(len([x for x in out
                                                 if x.get("staged_detail")])
                                            / max(1, len(out)), 2)},
            # 🆕 R-H362：**带介绍的名字按来源分组**（派生 · 现算不手写）——
            #    「行来源带几句 / 名单来源带几句」一眼可见 ⇒ 支持或削弱「一工具一行」都能看
            "detail_by_row": {row: sorted({x["token"] for x in out
                                           if x.get("staged_detail")
                                           and any(str(n).startswith(row + " ")
                                                   for n in (x.get("where") or []))})
                              for row in sorted({str(n).split(" ")[0] for x in out
                                                 for n in (x.get("where") or [])
                                                 if str(n).startswith("第")})},
            "detail_elsewhere": sorted({x["token"] for x in out
                                        if x.get("staged_detail")
                                        and not any(str(n).startswith("第")
                                                    for n in (x.get("where") or []))}),
            # 🆕 R-H372：**归属依据一览**（派生 · 按**固定词表**统计，只作读数）——
            #    「哪几句只靠位置、哪几句还有别的证据」一眼可见；
            #    ⚠️ 固定词表 = 我自己写的稳定用语；本读数**不当判据**（判据是 echo_claim 那条）
            "detail_evidence_summary": {x["token"]: [kw for kw in
                                                     ("紧跟其后", "在名字之前", "源表列序", "名字词义呼应", "owner_use",
                                                      "语义同向", "语义吻合", "未命中")
                                                     if kw in str(x.get("staged_detail_note") or "")]
                                        for x in out if x.get("staged_detail")},
            # 🆕 R-H366：**呼应可算**（现算不手写）——介绍与我方 `owner_use` 是否有
            #    ≥4 字连续重合；只用于读数（命中只说明「像」，**永远不当许可**）
            "detail_owner_use_echo": {t: hit for t, hit in _echo_map.items()
                                      if t in _own_use
                                      and any(x["token"] == t and x.get("staged_detail")
                                              for x in out)},
            # 🆕 R-H375：**介绍里点名了我方真身**（派生 · 只认固定词表）——
            #    「哪几句提到了盘上的实物」一眼可见；⚠️ 它只是读数，
            #    判据是同族的 `local_ref_unverified`（点名了就必须真的在盘上）
            "detail_local_refs": {x["token"]: _local_refs(x.get("staged_detail"))
                                 for x in out if _local_refs(x.get("staged_detail"))},
            "local_assets_on_disk": {name: _asset_ok(rel) for name, rel in LOCAL_ASSETS},
            # 🆕 R-H376：**每条的介绍句数**（派生 · 现算不手写）——
            #    「哪几条只有一句、哪几条有两句」一眼可见；⚠️ 它只是读数
            "detail_sentence_count": {x["token"]: (1 if x.get("staged_detail") else 0)
                                               + (1 if x.get("staged_detail_extra") else 0)
                                      for x in out if x.get("staged_detail")},
            # 🆕 R-H379：**每条介绍的位置读数**（派生 · 现算不手写）——
            #    「哪几句是名字之后来的、哪几句是名字之前来的」一眼可见
            "detail_position_map": {x["token"]: x["detail_position"]
                                    for x in out if x.get("detail_position")},
            "detail_positions": list(DETAIL_POSITIONS),
            # 🆕 R-H380：**相对「紧随其后的名字」**的关系（读数 · 现算不手写）
            #    —— 它就是 R-H379 把我带偏的那个框架，**显式记下来**；
            #    ⚠️ 它与 `detail_position`（相对 owner）**是两件事**，不许混
            "detail_next_name_side_map": {x["token"]: x["detail_next_name_side"]
                                          for x in out if x.get("detail_next_name_side")},
            "detail_next_name_sides": list(DETAIL_NEXT_NAME_SIDES),
            # 🆕 R-H340：**按来源格分组**（派生读数）—— 让「同一个格被逐个再给」这件事看得见，
            #    但**不替主人下结论**（分组只是读数，不是「拆行」）
            "same_cell_groups": {k: sorted({x["token"] for x in out
                                            if k in (x.get("where") or [])})
                                 for k in sorted({n for x in out
                                                 for n in (x.get("where") or [])})},
            # 🆕 R-H355：**按行**统计再现条数（派生 · 不手写）—— 哪些行开始被逐个投喂，一眼可见
            # 🔧 R-H359：by_row **只收「行来源」**（面名以「第」开头）—— 否则出处不是行的
            #    再现名字会在这里冒出一个怪 key ⇒ 它们改由 `reappearing_elsewhere` 报出
            "reappearing_by_row": {row: sorted({x["token"] for x in out
                                                 if any(str(n).startswith(row + " ")
                                                        for n in (x.get("where") or []))})
                                   for row in sorted({str(n).split(" ")[0]
                                                      for x in out
                                                      for n in (x.get("where") or [])
                                                      if str(n).startswith("第")})},
            # 🆕 R-H359：**不在行里的再现**（例如只在我方 R-H285 名单里出现过的名字）
            "reappearing_elsewhere": sorted({x["token"] for x in out
                                             if not any(str(n).startswith("第")
                                                        for n in (x.get("where") or []))}),
            # 🆕 R-H373：**每个「多名字格」喂到几成**（派生 · 现算不手写）——
            #    只看**分段数 ≥2** 的格：给定 = 该段已在再现区登记 ⇒ 「还有哪些格没喂完」一眼可见
            "cell_feed_progress": {("第%d行 格 %s" % (i, k)): {
                "given": len([p for p in str(v).split("/")
                              if p.strip() and p.strip() in {str(t.get("token") or "")
                                                              for t in REAPPEARING_TOKENS}]),
                "total": len([p for p in str(v).split("/") if p.strip()])}
                for i, r in enumerate(CATEGORY_ROWS_OWNER, 1)
                for k, v in dict(r.get("cells") or {}).items()
                if k in NAME_COLUMNS
                and len([p for p in str(v).split("/") if p.strip()]) >= 2},
            # 🆕 R-H361：**我方 R-H285 六条的投喂进度**（派生 · 现算不手写）
            #    六条里哪些已被主人逐个再给过 —— 一眼可见，且**名字表仍只在 KEY_TOOLS 一处**
            "rh285_covered": sorted({x["token"] for x in out
                                     if x["token"] in {str(t.get("name") or "")
                                                       for t in KEY_TOOLS}}),
            "rh285_total": len(KEY_TOOLS),
            # 🆕 R-H367：**到齐与否**（派生 · 现算）—— ⚠️ 到齐**只当读数**，不是许可
            "rh285_complete": (len({x["token"] for x in out
                                     if x["token"] in {str(t.get("name") or "")
                                                       for t in KEY_TOOLS}})
                               == len(KEY_TOOLS)),
            # 🆕 R-H367：**按来源统计**（派生 · 现算）：行来源 / 名单来源 / 两处都有，各几条
            "source_summary": {
                "in_row": len([x for x in out
                               if any(str(n).startswith("第") for n in (x.get("where") or []))]),
                "in_rh285_list": len([x for x in out
                                      if "我方 R-H285 工具名单" in (x.get("where") or [])]),
                "both": len([x for x in out
                             if any(str(n).startswith("第") for n in (x.get("where") or []))
                             and "我方 R-H285 工具名单" in (x.get("where") or [])]),
                "total": len(out)},
            "note": REAPPEARING_TOKENS_NOTE}


def awaiting_owner() -> dict:
    """**一页「等你拍板」**（R-H370 · 只读）：把散在各区、**只能由主人处理**的东西聚起来。

    为什么单列：这些东西**不会因为再等一会儿就自己变好**；聚成一页是为了让主人
    **一眼看到卡在哪**（也避免我看起来在忙、其实在等）。🔴 本函数**只读、不落表**。
    """
    pend = check_pending_attribution()
    order = check_source_order_readings()
    trunc = check_truncated_fragments()
    reap = check_reappearing_tokens()
    pending_tokens = [str(x["token"]) for x in (pend.get("items") or [])]
    mismatched = [str(c) for c in (order.get("mismatched") or [])]
    truncated = [{"token": str(x["token"]), "at": x.get("at")}
                 for x in (trunc.get("items") or [])]
    with_detail = [str(t) for t in (reap.get("with_detail") or [])]
    repeated = [str(t) for t in (pend.get("repeated_but_unresolved") or [])]
    return {"ok": True, "readonly": True,
            "pending_unresolved": pending_tokens,
            "order_mismatched": mismatched,
            "repeated_but_unresolved": repeated,
            "truncated_fragments": truncated,
            "details_still_unowned": with_detail,
            "counts": {"pending": len(pending_tokens),
                       "order_mismatched": len(mismatched),
                       "repeated": len(repeated),
                       "truncated": len(truncated),
                       "details_unowned": len(with_detail),
                       "total_items_needing_owner": (len(pending_tokens)
                                                     + len(mismatched)
                                                     + len(repeated)
                                                     + len(truncated)
                                                     + len(with_detail))},
            "note": ("**一页「等你拍板」**：全部**只读、不落表**；"
                     "这些东西**不会因为再等一会儿就自己变好** —— "
                     "处理只能由**主人**做（我不自解、不硬配、不为好看而落表）")}


def index(category: Optional[str] = None) -> dict:
    """INDEX（只读）：按分类检索 —— **本骨架只有主人给的那批，不编仓库内容**。"""
    cat = str(category or "").strip()
    pool = [] if not cat else []
    return {"ok": True, "readonly": True, "primitive": "INDEX",
            "category": cat or None, "categories": list(CATEGORIES_OWNER),
            "items": pool,
            "note": "仓库内容**未取证** ⇒ 索引池为空且**不编**（空样本不按绿："
                    "所以这里不给任何『已收录』的错觉）"}


def lookup(name: Any = None) -> dict:
    """LOOKUP（只读）：看单个工具的详情 —— 只查主人给的那六个。"""
    n = str(name or "").strip().lower()
    for t in KEY_TOOLS:
        if t["name"].lower() == n:
            return {"ok": True, "readonly": True, "primitive": "LOOKUP", "tool": dict(t)}
    return {"ok": False, "denied": True, "rule": "not_in_index", "name": name,
            "why": "不在主人给的重点清单里 ⇒ **不编一个出来**（未取证不引外部）"}


def mapping() -> dict:
    """MAP（只读）：工具 → 能力位 —— 只给**主人明确配对**的那几条。"""
    rows = [{"name": t["name"], "maps_to": t["maps_to"],
             "evidence": t["evidence"], "status": t["status"],
             "owner_use": t["owner_use"]} for t in KEY_TOOLS]
    return {"ok": True, "readonly": True, "primitive": "MAP", "rows": rows,
            "pending_fragments": list(OWNER_FRAGMENTS),
            "note": "只有主人**明确配对**的才进映射；其余碎片进待归位（**不硬配**）"}


def run(op="status", **params) -> dict:
    """能力入口（只读骨架）：status / primitives / categories / tools / map /
    fragments / evidence / redlines / index / lookup /
    gate_readonly / gate_map / gate_verify /
    source_columns / gate_source_columns / truncated / gate_truncated /
    reappearing / gate_reappearing / source_order / gate_source_order / awaiting。"""
    op = str(op or "status")
    if op == "status":
        return {"ok": True, "readonly": True, "kind": CAP_KIND, "domain": DOMAIN,
                "type": CAP_TYPE,
                "core": CORE_PROPOSITION,
                "primitives": [dict(p) for p in PRIMITIVES],
                "red_lines": list(RED_LINES),
                "categories_owner": list(CATEGORIES_OWNER),
                "categories_note": CATEGORIES_NOTE,
                "key_tools": [dict(t) for t in KEY_TOOLS],
                "key_tools_note": KEY_TOOLS_NOTE,
                "owner_fragments": list(OWNER_FRAGMENTS),
                "owner_fragments_note": OWNER_FRAGMENTS_NOTE,
                "evidence": dict(EVIDENCE_2026_09_20),
                "verified_green": 0,
                "repo_evidenced": bool(EVIDENCE_2026_09_20["repo_evidenced"]),
                "sections": [dict(s) for s in SECTIONS_OWNER],
                "sections_note": SECTIONS_NOTE,
                "owner_20260920_r287": list(OWNER_20260920_R287),
                "core_crosscheck": dict(CORE_CROSSCHECK),
                "gate_sections": check_sections(),
                "section_rows": [dict(r) for r in SECTION_ROWS_OWNER],
                "section_rows_note": SECTION_ROWS_NOTE,
                "self_repo": SELF_REPO,
                "self_repo_note": SELF_REPO_NOTE,
                "gate_section_rows": check_section_rows(),
                "core_sources": [dict(s) for s in CORE_SOURCES],
                "gate_crosscheck": check_core_crosscheck(),
                "pending_attribution": [dict(x) for x in PENDING_ATTRIBUTION],
                "gate_pending": check_pending_attribution(),
                "section2_columns": list(SECTION2_COLUMNS),
                "category_rows": [dict(r) for r in CATEGORY_ROWS_OWNER],
                "gate_categories": check_category_rows(),
                "source_table_columns": list(SOURCE_TABLE_COLUMNS),
                "source_table_columns_note": SOURCE_TABLE_COLUMNS_NOTE,
                "gate_source_columns": check_source_table_columns(),
                "truncated_fragments": [dict(x) for x in TRUNCATED_FRAGMENTS],
                "truncated_fragments_note": TRUNCATED_FRAGMENTS_NOTE,
                "gate_truncated": check_truncated_fragments(),
                "source_order_readings": [dict(x) for x in SOURCE_ORDER_READINGS],
                "source_order_readings_note": SOURCE_ORDER_READINGS_NOTE,
                "gate_source_order": check_source_order_readings(),
                "reappearing_tokens": [dict(x) for x in REAPPEARING_TOKENS],
                "reappearing_tokens_note": REAPPEARING_TOKENS_NOTE,
                "gate_reappearing": check_reappearing_tokens()}
    if op == "primitives":
        return {"ok": True, "readonly": True, "primitives": [dict(p) for p in PRIMITIVES]}
    if op == "categories":
        return {"ok": True, "readonly": True, "categories": list(CATEGORIES_OWNER),
                "note": CATEGORIES_NOTE}
    if op == "tools":
        return {"ok": True, "readonly": True, "tools": [dict(t) for t in KEY_TOOLS],
                "note": KEY_TOOLS_NOTE}
    if op == "map":
        return mapping()
    if op == "incoming_distills":
        d = check_incoming_distills()
        return {"ok": d.get("ok"), "readonly": True, **({"rule": d.get("rule"),
                "why": d.get("why")} if not d.get("ok") else {}),
                "items": d.get("items") or [], "count": d.get("count", 0),
                "layers": d.get("layers") or [],
                "layers_complete": d.get("layers_complete"),
                "cells": d.get("cells") or [], "cells_of": d.get("cells_of"),
                "frame_layers": d.get("frame_layers") or [],
                "frame_layers_complete": d.get("frame_layers_complete"),
                "layer_name_diff": d.get("layer_name_diff") or [],
                "matrix_rows": d.get("matrix_rows") or [], "matrix_cells": d.get("matrix_cells"),
                "matrix_note": d.get("matrix_note"),
                "row1": d.get("row1") or [], "row1_of": d.get("row1_of"),
                "rows": d.get("rows") or [], "rows_of": d.get("rows_of"),
                "rows_complete_rows": d.get("rows_complete_rows"),
                "table_complete": d.get("table_complete"), "table_note": d.get("table_note"),
                "row1_complete": d.get("row1_complete"), "row1_note": d.get("row1_note"),
                "cells_note": d.get("cells_note"),
                "overlap": d.get("overlap") or {},
                "note": INCOMING_DISTILLS_NOTE}
    if op == "gate_incoming_distills":
        return check_incoming_distills()
    if op == "fusion_cases":
        d = check_fusion_cases()
        return {"ok": d.get("ok"), "readonly": True, **({"rule": d.get("rule"),
                "why": d.get("why")} if not d.get("ok") else {}),
                "items": d.get("items") or [], "count": d.get("count", 0),
                "progress": d.get("progress") or {},
                "with_teeth": d.get("with_teeth") or [], "note": FUSION_CASES_NOTE}
    if op == "gate_fusion_cases":
        return check_fusion_cases()
    if op == "fusion_sections":
        d = check_fusion_sections()
        return {"ok": d.get("ok"), "readonly": True, **({"rule": d.get("rule"),
                "why": d.get("why")} if not d.get("ok") else {}),
                "items": d.get("items") or [], "count": d.get("count", 0),
                "nos": d.get("nos") or [], "note": FUSION_SECTIONS_NOTE}
    if op == "gate_fusion_sections":
        return check_fusion_sections()
    if op == "fusion_primitives":
        d = check_fusion_primitives()
        return {"ok": d.get("ok"), "readonly": True, **({"rule": d.get("rule"),
                "why": d.get("why")} if not d.get("ok") else {}),
                "items": d.get("items") or [], "count": d.get("count", 0),
                "known": d.get("known") or [], "given": d.get("given") or [],
                "with_detail": d.get("with_detail") or [],
                "progress": d.get("progress") or {},
                "detail_rounds": d.get("detail_rounds") or {},
                "order_same": d.get("order_same"), "note": FUSION_PRIMITIVES_NOTE}
    if op == "gate_fusion_primitives":
        return check_fusion_primitives()
    if op == "fusion_rows":
        d = check_fusion_rows()
        return {"ok": d.get("ok"), "readonly": True, **({"rule": d.get("rule"),
                "why": d.get("why")} if not d.get("ok") else {}),
                "items": d.get("items") or [], "count": d.get("count", 0),
                "kinds": d.get("kinds") or [], "note": FUSION_ROWS_NOTE}
    if op == "gate_fusion_rows":
        return check_fusion_rows()
    if op == "fragments":
        return {"ok": True, "readonly": True, "fragments": list(OWNER_FRAGMENTS),
                "note": OWNER_FRAGMENTS_NOTE}
    if op == "evidence":
        return {"ok": True, "readonly": True, "evidence": dict(EVIDENCE_2026_09_20)}
    if op == "redlines":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES)}
    if op == "sections":
        return {"ok": True, "readonly": True,
                "sections": [dict(s) for s in SECTIONS_OWNER],
                "note": SECTIONS_NOTE,
                "core_crosscheck": dict(CORE_CROSSCHECK)}
    if op == "gate_sections":
        return check_sections()
    if op == "section_rows":
        return {"ok": True, "readonly": True,
                "rows": [dict(r) for r in SECTION_ROWS_OWNER],
                "self_repo": SELF_REPO,
                "self_repo_note": SELF_REPO_NOTE,
                "note": SECTION_ROWS_NOTE}
    if op == "gate_section_rows":
        return check_section_rows()
    if op == "core_sources":
        return {"ok": True, "readonly": True,
                "sources": [dict(s) for s in CORE_SOURCES],
                "crosscheck": dict(CORE_CROSSCHECK)}
    if op == "gate_crosscheck":
        return check_core_crosscheck()
    if op == "pending":
        return {"ok": True, "readonly": True,
                "items": [dict(x) for x in PENDING_ATTRIBUTION],
                "note": PENDING_ATTRIBUTION_NOTE}
    if op == "gate_pending":
        return check_pending_attribution()
    if op == "columns2":
        return {"ok": True, "readonly": True,
                "columns": list(SECTION2_COLUMNS),
                "note": SECTION2_COLUMNS_NOTE}
    if op == "category_rows":
        # ⚠️ 名字要跟已有的 op "categories"（那是个分类名清单）区分开 ⇒ 不复用那个名字
        return {"ok": True, "readonly": True,
                "rows": [dict(r) for r in CATEGORY_ROWS_OWNER],
                "columns": list(SECTION2_COLUMNS), "note": CATEGORY_ROWS_NOTE}
    if op == "gate_categories":
        return check_category_rows()
    if op == "source_columns":
        return {"ok": True, "readonly": True,
                "columns": list(SOURCE_TABLE_COLUMNS),
                "owner_columns": list(SOURCE_TABLE_COLUMNS_OWNER),
                "appends": [dict(a) for a in SOURCE_TABLE_COLUMNS_APPENDS],
                "local_columns": list(SECTION2_COLUMNS),
                "same_table": False,
                "note": SOURCE_TABLE_COLUMNS_NOTE}
    if op == "gate_source_columns":
        return check_source_table_columns()
    if op == "truncated":
        # ⚠️ 形状必须与**闸里那份**一致（闸算出来的就是唯一形状源）——
        #    否则「出口有的字段、闸里没有」这种不一致会绕过判据
        d = check_truncated_fragments()
        out = {"ok": bool(d.get("ok")), "readonly": True,
               "items": list(d.get("items") or []),
               "note": TRUNCATED_FRAGMENTS_NOTE}
        if not d.get("ok"):
            out["rule"] = d.get("rule")
            out["why"] = d.get("why")
        return out
    if op == "gate_truncated":
        return check_truncated_fragments()
    if op == "reappearing":
        d = check_reappearing_tokens()
        out = {"ok": bool(d.get("ok")), "readonly": True,
               "items": list(d.get("items") or []),
               "note": REAPPEARING_TOKENS_NOTE}
        if not d.get("ok"):
            out["rule"] = d.get("rule")
            out["why"] = d.get("why")
        return out
    if op == "gate_reappearing":
        return check_reappearing_tokens()
    if op == "source_order":
        d = check_source_order_readings()
        return {"ok": bool(d.get("ok")), "readonly": True,
                "items": list(d.get("items") or []),
                "mismatched": list(d.get("mismatched") or []),
                "note": SOURCE_ORDER_READINGS_NOTE, **({"rule": d.get("rule"),
                                                       "why": d.get("why")}
                                                      if not d.get("ok") else {})}
    if op == "gate_source_order":
        return check_source_order_readings()
    if op == "awaiting":
        return awaiting_owner()
    if op == "index":
        return index(params.get("category"))
    if op == "lookup":
        return lookup(params.get("name"))
    if op == "gate_readonly":
        return check_index_readonly(params.get("payload"))
    if op == "gate_map":
        return check_map_traceable(params.get("entries"))
    if op == "gate_verify":
        return check_verify_status(params.get("status"), params.get("evidence"))
    raise ValueError("未知 op %r（可用：status/primitives/categories/tools/map/"
                     "fragments/evidence/redlines/index/lookup/gate_readonly/"
                     "gate_map/gate_verify/source_columns/gate_source_columns/"
                     "truncated/gate_truncated/reappearing/gate_reappearing/"
                     "source_order/gate_source_order）" % (op,))


HONEST_BOUNDARY = (
    "本骨架保证『四原语 / 三条带牙判据 / 五条红线 / 主人给的六个重点工具与分类名』可查、可判；"
    "它**保证不了**「这些工具你现在就能用」—— 六个工具盘上**全部 0 命中**、"
    "仓库内容**未独立取证** ⇒ 一律 unverified。"
    "另外：本模块**只呈现不执行** —— 它不会替你装工具、不会替你跑工具、不会替你拼请求。"
)
