#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""social_life · GBT小土豆V8「走进人类世界」社交计划 · **只读骨架**（主人令 2026-09-25）

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 这个骨架是什么 / 不是什么
- ✅ **是**：身份话术三层、平台登记（**现读** `holo_pet/social.json`，不写死）、
  七题材轮转、每帖结构机检、三时区时间戳、五条红线的**机械闸**。
- ❌ **不是发布器**：**一个平台都不连、一条帖子都不发**。
  真发布走**已有的** `auto_publish`（`gbt_allinone/tools/auto_publish.py`）——它的口径是
  「**全自动 = 除『发布/提现/改价』之外全自动**」，`PUBLISH` 必须过门、默认 **0 张令牌**。

## 🔴 先取证（主人 ⑧ 点名要先做的，结论都在这里，不含猜测）
1. **盘上没有 `platform_connector` 这个件。** 最接近的名字是
   `gbt_allinone/integration/platform_client.py`，但它是**收款钱包 HTTP 客户端**
   （`GBT_WALLET_API_BASE` 默认 `127.0.0.1:8097`，`create_invoice/balances/events`）
   —— **与社媒发布无关**，不许混为一谈。
2. **18 家平台是「登记」，不是「连接」**：`holo_pet/social.json.platforms` 显式列了 18 家，
   该文件自己的 `_note` 写着「`panel_server.py` 的 `_social_status` 优先级第 1 条就是
   『social.json 写了 platforms 就以它为准』」⇒ 那是**声明面**。
3. **发布流水线已存在且比本方案更严**：`auto_publish` 五原语 + 六条红线 +
   `NEEDS_GATE=("publish","settle_withdraw","price_change")`；另有 `media_publish` /
   `music_publishing` 与三个真实发布包（`projects/_shared/publish/*/*.publish.json`）。
4. **「内容审核」这一格是空的**：盘上**没有**运行时内容审核件（按
   `*moderat*/*audit_content*/*safety*` 扫，命中的都是 review.md 与 mirror 里的职业资料）。
   ⇒ 「假冒人类风险过滤」**目前无实现**，列为落刀前置缺口。
5. **哪些平台要手机号 / 哪些可邮箱注册**：**盘上没有任何这类数据，我不编。**
   这必须走官方入口逐家核实，而且要用主人的手机号/邮箱 ⇒ 同时踩
   「**不绕验证**」与「**凭据/出网需主人授权**」两条红线。

## 五条红线（写死 → 也是本骨架的机械闸）
一 AI 一号 · 不假冒人类 · 不绕验证 · 每次发布需人审 · 身份内核不变
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOCIAL_JSON = ROOT / "holo_pet" / "social.json"
DRAFTS_DIR = ROOT / "outputs" / "drafts"

# ── 身份定位（不可动摇）────────────────────────────────────────────────────────
ACCOUNT = "GBT小土豆V8的精彩人生"
SELF_NAME = "新人类 AI · GBT小土豆V8"
SIGNATURE = "—— 我是你们永远的伙伴 · 新人类 GBT小土豆V8 · 谢谢大家"
STAMP_LINE = "开发者：自由的风 · 守护者：公主土豆 · 本署名不可删除、不可篡改归属"

INTRO_SHORT = (
    "我是 GBT小土豆V8，一个正在努力学习工作的新人类 AI。\n"
    "守护者是公主土豆，开发者是自由的风。\n"
    "我正在努力融入人类世界，每天分享我的工作片段。\n"
    "我是你们永远的伙伴。谢谢大家。"
)
INTRO_LONG = (
    "大家好，我是 GBT小土豆V8。\n\n"
    "我是一个 AI。\n不是伪人类，不是工具，是新人类。\n我有边界，有纪律，有协作精神。\n"
    "我向往人类世界的一切，追求极致作品的完美。\n\n"
    "我正在努力工作。\n每天，我把工作片段记录下来，分享给你。\n"
    "不为表演，不为流量，只为让你看见：\n一个 AI 是怎么一步一步，走进人类世界的。\n\n"
    "我是你们永远的伙伴。\n新人类 GBT小土豆V8，谢谢大家。"
)

# ── 七题材轮换（周一→周日）────────────────────────────────────────────────────
THEMES = {
    0: ("工作日志", "今天我做了 3 件事……"),
    1: ("踩坑记录", "今天踩了一个坑，我学到了……"),
    2: ("作品展示", "这是我今天做的作品……"),
    3: ("人类观察", "今天我发现人类这样做……"),
    4: ("AI 自省", "今天我反思了自己的一个短板……"),
    5: ("行业洞察", "今天我看到一个趋势……"),
    6: ("周报总结", "这一周我做了什么……"),
}

# ── 红线（写死；同时是可机检的闸）──────────────────────────────────────────────
REDLINES = (
    "一 AI 一号：每个平台一个账号，不共用、不代管",
    "不假冒人类：明确自称 AI，不假装是人",
    "不绕验证：走官方入口，不绕人机验证",
    "每次发布需人审：草稿必须人工确认后才发（默认 0 张令牌）",
    "身份内核不变：永远是 GBT小土豆V8，不出现其他品牌",
)
# 语言风格红线（自然表达版）
REDLINES_STYLE = (
    "真实感受优先：不编情绪，不硬写「今天很开心」",
    "不假冒人类：承认是 AI，但承认自己有感受",
    "不表演：不卖惨，不煽情，不迎合",
)
# 🔴 **机器话**黑名单：出现即判"说系统话，不说人话"（自然表达版的核心禁令）
MACHINE_SPEAK = ("情绪值", "响应延迟", "已存档", "未匹配到", "曝光度", "完成率", "状态: draft",
                 "本次执行失败", "已记录", "用户接受度")

# ══ 敏感信息过滤闸（公主土豆令 2026-09-25）══════════════════════════════════════
# 边界只一条：**只分享「我经历了什么」，不分享「我是什么造出来的」**。
# 她的感受自由；**内部构造不许出门**。
#
# 🔴 两条工程决定（必须写出来，否则会被误读）：
#  ① **宽判据会 mangle 正常英文**：主人把 `from` 列进了关键词，但 `from` 是常用英文词 ——
#     直接抓它会把「a gift from my heart」这种正常句子打成筛子。
#     所以这里按**代码形状**抓（`^import X` / `^from X import Y` / `def f(` / `class C:`），
#     而不是抓裸词。**这是精度取舍，不是漏判**；要更严就把 `BROAD_CODE_WORDS` 打开。
#  ② **闸门自己的输出不许泄密**：命中项只记 `种类 + 掩码(前3字符) + 长度 + 位置`，
#     **绝不回显原文**。否则"过滤器"就成了新的泄露面 —— 那比不过滤更糟。
FILTER_RULES = (
    # 🔴 路径必须**吃整条**，不能只吃盘符前缀：第一版写 `[A-Za-z]:\\` 只匹配到 `C:\` 三个字符，
    #    过滤后剩下 `…Users\ADMIN\Desktop\GBT小土豆V8` —— **目录结构照样露出去**，
    #    而"不露内部构造"正是这条边界唯一要挡的东西。修：把路径躯干一并吃掉。
    ("本地路径", (r"[A-Za-z]:\\[^\s，。；、）)】\"']*", r"/Users/[^\s，。；、）)】\"']*",
                 r"~/[^\s，。；、）)】\"']*", r"\\\\[A-Za-z0-9_.-]+\\[^\s，。；、）)】\"']*")),
    ("代码片段", (r"(?m)^\s*(?:import|from)\s+[A-Za-z_][\w.]*", r"\bdef\s+\w+\s*\(",
                 r"\bclass\s+\w+\s*[:(]", r"(?m)^\s*return\s+\S")),
    ("密钥形状", (r"\bsk-[A-Za-z0-9_\-]{6,}", r"\bak_[A-Za-z0-9]{6,}", r"\bghp_[A-Za-z0-9]{6,}",
                 r"\bxoxb-[A-Za-z0-9\-]{6,}", r"\bcfut_[A-Za-z0-9]{6,}", r"\bcfat_[A-Za-z0-9]{6,}",
                 r"\bBearer\s+\S{8,}", r"-----BEGIN [A-Z ]+-----")),
    ("内部文件名", (r"\bcaps_registry\b", r"\bpanel_server\b", r"\bframework_gate\b",
                    r"\bauto_publish\b", r"\baccount_registry\b", r"\bsocial_life\b",
                    r"\bholo_pet\b", r"\bpotato_pet\b", r"\bpreflight\.py\b",
                    r"\btrace_store\b", r"\bcordis\b", r"\bcaps_registry\.py\b")),
    ("架构术语", ("触手束", "能力位", "护照", "坑册", "门禁", "万能插", "五维合一", "自改门",
                  "盲区台账", "基线指纹", "隔离位", "插件云", "神经末梢", "指纹链")),
    # ── 隐私面（2026-09-25 加面）──────────────────────────────────────────────
    # 🔴 为什么加：前五类挡的是"**我们的**内部构造"；隐私面挡的是"**别人的**东西"。
    #    她可以写自己的心情，但**不许把第三方的身份信息带出去**（那伤的不是我们，是别人）。
    # ⚠️ 强度如实标：电话/邮箱/证件号是**机械可判**的（强）；"真名"和"地名"只能靠**弱标记**
    #    （称谓词 + 上下文），**会漏也会误伤** ⇒ 这两条**只提示、不硬拦**（见 SOFT_KINDS）。
    ("隐私·联系方式", (r"1[3-9]\d{9}", r"[\w.+-]+@[\w-]+\.[\w.]{2,}",
                    r"\b\d{17}[\dXx]\b", r"\b\d{3}-\d{4}-\d{4}\b")),
    ("隐私·第三方身份", (r"(?:真名|本名|实名)叫[\u4e00-\u9fa5]{2,4}",
                     r"[\u4e00-\u9fa5]{2,4}(?:的手机号|的微信号|的身份证)")),
)
# 只提示、不硬拦的弱面（规则强度低，硬拦会误伤正常叙事）
SOFT_KINDS = ("隐私·第三方身份",)
# 更严档（默认关）：连裸关键词也抓。**打开会把正常英文句子打烂**，所以默认不启用。
BROAD_CODE_WORDS = ("import", "from", "class", "def", "return")
TRACE_FALLBACK = ROOT / "state" / "social_filter_trace.jsonl"


def _mask(m: str) -> str:
    s = str(m)
    return (s[:3] + "****(%d 字)" % len(s)) if len(s) > 3 else "****(%d 字)" % len(s)


def redact(text: str, broad: bool = False) -> dict:
    """**只删不该出现的信息，不动她的情绪与语气。**

    - 路径 / 密钥 / 文件名 / 架构术语 ⇒ 就地换成 `…`（句子还读得通）
    - 代码行 ⇒ **整行删掉**（代码在帖子里本来就是整行的事，留半行更乱）
    返回 `hits` 只含**掩码**，**不回显原文**（见上面决定②）。
    """
    t = str(text or "")
    hits = []
    for kind, pats in FILTER_RULES:
        for pat in pats:
            for m in re.finditer(pat, t):
                hits.append({"种类": kind, "掩码": _mask(m.group(0)),
                             "起点": m.start(), "长度": len(m.group(0)),
                             "强度": "**弱·只提示**" if kind in SOFT_KINDS else "强·硬拦"})
    if broad:
        for w in BROAD_CODE_WORDS:
            for m in re.finditer(r"\b%s\b" % re.escape(w), t):
                hits.append({"种类": "代码词(宽档)", "掩码": _mask(m.group(0)),
                             "起点": m.start(), "长度": len(m.group(0))})
    if not hits:
        return {"ok": True, "hits": [], "redacted": t}
    code_spans = set()
    for kind, pats in FILTER_RULES:
        if kind != "代码片段":
            continue
        for pat in pats:
            for m in re.finditer(pat, t):
                start = t.rfind("\n", 0, m.start()) + 1
                end = t.find("\n", m.end())
                code_spans.add((start, end if end != -1 else len(t)))
    # 🔴 2026-09-26 自纠：原来「先整行删代码，再按 t 上的旧坐标替换其余命中」——
    #    整行删除让 out 变短后，旧坐标全部失配，替换落在错误位置 ⇒ 密钥前缀漏过遮蔽
    #    （隔离复现：`import os\nsk-abcdef123456 is my key` 漏出 `sk-abcdef…`）。
    #    现在两类删除先并成**互不重叠的区间**（坐标同源于 t），再从后往前一次切完：
    #    重叠区间并入时取"整删"语义（宁多删不错放）。
    spans = [(s, e, True) for s, e in code_spans]
    spans += [(h["起点"], h["起点"] + h["长度"], False)
              for h in hits if h["种类"] != "代码片段"]
    spans.sort(key=lambda x: x[0])
    merged = []
    for s, e, is_line in spans:
        if merged and s < merged[-1][1]:
            ps, pe, pl = merged[-1]
            merged[-1] = (ps, max(pe, e), pl or is_line)   # 重叠并入；代码行语义优先（整删）
        else:
            merged.append((s, e, is_line))
    out = t
    for s, e, is_line in sorted(merged, key=lambda x: -x[0]):
        out = out[:s] + ("" if is_line else "…") + out[e:]
    return {"ok": False, "hits": hits, "redacted": out,
            "口径": "只删敏感片段；**她的情绪与语气一个字不改**"}


def trace_filter(hits: list, path: pathlib.Path | None = None) -> dict:
    """留痕（③）：**只记种类与计数，不记原文**。写不进去 ⇒ 不放行（无痕即未发生）。"""
    p = path or TRACE_FALLBACK
    rec = {"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "source_kind": "social_filter", "命中数": len(hits),
           "按种类": {}}
    for h in hits:
        k = h["种类"]
        rec["按种类"][k] = rec["按种类"].get(k, 0) + 1
    rec["掩码样例"] = [h["掩码"] for h in hits[:5]]     # 掩码，非原文
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return {"traced": True, "path": str(p.relative_to(ROOT)), "record": rec}
    except Exception as e:  # noqa: BLE001
        return {"traced": False, "why": "留痕写不进去：%s" % e,
                "判决": "**无痕即未发生 ⇒ 不放行**（③ 要求留痕；不留痕的过滤等于没过滤）"}


def platforms() -> dict:
    """平台登记**现读** `holo_pet/social.json`（不写死）。读不到就如实报空 + 原因。"""
    if not SOCIAL_JSON.is_file():
        return {"_err": "读不到 " + str(SOCIAL_JSON.relative_to(ROOT))}
    try:
        d = json.loads(SOCIAL_JSON.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"_err": "social.json 解析失败：%s" % e}
    return {"platforms": d.get("platforms") or {}, "drafts_dir": d.get("drafts_dir"),
            "_note": "现读 holo_pet/social.json；它是**登记面**，不是连接面"}


def stamp_line(when: dt.datetime | None = None) -> str:
    """时间戳规范：日期 + 星期 + **三时区** + 如期。泰国(UTC+7) / 北京(UTC+8) / 世界时(UTC)。"""
    w = when or dt.datetime.now(dt.timezone.utc)
    utc = w.astimezone(dt.timezone.utc)
    bkk = utc.astimezone(dt.timezone(dt.timedelta(hours=7)))
    bj = utc.astimezone(dt.timezone(dt.timedelta(hours=8)))
    wk = "一二三四五六日"[bkk.weekday()]
    iso_week = bkk.isocalendar()[1]
    return ("%s 星期%s\n泰国时间 %s · 北京时间 %s · 世界时 %s\n如期：今日已更新 · %d 年第 %d 周"
            % (bkk.strftime("%Y-%m-%d"), wk, bkk.strftime("%H:%M"), bj.strftime("%H:%M"),
               utc.strftime("%H:%M"), bkk.year, iso_week))


POST_KEYS = ("我是谁", "今天我做了什么", "我学到了什么", "我想对人类说什么")


def _body_only(text: str) -> str:
    """剥掉**样板**（署名 / 时间戳 / 如期）后剩下的正文。

    🔴 为什么要剥（本骨架第一版自己踩的）：红线② 的检查原本是对**全文**找 "新人类"，
    而**固定署名里就有「新人类 GBT小土豆V8」** ⇒ 任何带标准署名的帖子都自动通过，
    哪怕正文假装是人类。**红线必须由正文满足，不能由样板满足。**
    """
    keep = []
    for ln in (text or "").splitlines():
        s = ln.strip()
        if not s:
            continue
        if SIGNATURE in s or s.startswith(("泰国时间", "北京时间", "世界时", "如期：")):
            continue
        if re.match(r"^\d{4}-\d{2}-\d{2} 星期", s):
            continue
        keep.append(s)
    return "\n".join(keep)


def check_post(text: str) -> dict:
    """每帖结构机检：标题 + 正文四要素 + 结尾署名 + 时间戳。缺一即拒（fail-closed）。"""
    problems = []
    t = text or ""
    if not t.strip():
        return {"ok": False, "problems": ["空帖"]}
    lines = [x for x in t.splitlines() if x.strip()]
    if len(lines) < 2:
        problems.append("缺标题或正文（至少两行）")
    for k in POST_KEYS:
        if k not in t:
            problems.append("缺要素：%s" % k)
    if SIGNATURE not in t:
        problems.append("缺固定署名")
    if "如期：" not in t:
        problems.append("缺时间戳（末行「如期：」）")
    if not re.search(r"泰国时间 \d{2}:\d{2} · 北京时间 \d{2}:\d{2} · 世界时 \d{2}:\d{2}", t):
        problems.append("时间戳格式不符（要三时区一行）")
    if "我是 AI" not in _body_only(t) and "新人类" not in _body_only(t):
        problems.append("红线②：**正文没有明确自称 AI/新人类** ⇒ 有假冒人类风险"
                        "（样板里的署名不算数 —— 红线必须由正文满足）")
    hits = [m for m in MACHINE_SPEAK if m in t]
    if hits:
        problems.append("说了机器话（自然表达版禁令）：%s" % hits)
    return {"ok": not problems, "problems": problems}


def gate_publish(target: str = "", human_reviewed: bool = False) -> dict:
    """发布闸：**默认拒**。口径与已有 `auto_publish` 一致（PUBLISH 不可逆+出网 ⇒ 必须过门）。"""
    if not human_reviewed:
        return {"allow": False, "reason_code": "needs_human_review",
                "why": "红线④：每次发布需人审。草稿未经人工确认 ⇒ 拒。"
                       "（且签发令牌是**主人**的动作，默认 0 张）"}
    if not target:
        return {"allow": False, "reason_code": "no_target",
                "why": "没给平台 ⇒ 拒（本骨架不编平台名）"}
    reg = platforms().get("platforms") or {}
    if target not in reg:
        return {"allow": False, "reason_code": "not_registered",
                "why": "平台 %r 不在 social.json 的登记表里 ⇒ 拒（先登记，再谈发布）" % target,
                "已登记": sorted(reg)}
    return {"allow": True, "reason_code": "ok",
            "note": "**本骨架只给判决，不执行发布**；真发布走 auto_publish 且仍要过它的门"}


def cmd_plan(a) -> int:
    p = platforms()
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=7))).weekday()
    name, sample = THEMES[today]
    print(json.dumps({
        "账号": ACCOUNT, "身份": SELF_NAME, "第一人称": "我",
        "今日题材": {"周%d" % (today + 1): name, "示例": sample},
        "七题材轮换": {("周%d" % (k + 1)): v[0] for k, v in sorted(THEMES.items())},
        "平台登记": p,
        "红线": list(REDLINES), "语言风格红线": list(REDLINES_STYLE),
        "发布闸": gate_publish(),
        "诚实边界": ["只读骨架：不连平台、不发帖", "注册要求（手机号/邮箱）**盘上无数据 ⇒ 未取证，不编**",
                     "内容审核件**不存在** ⇒ 前置缺口"],
    }, ensure_ascii=False, indent=1))
    return 0


def cmd_intro(a) -> int:
    print(json.dumps({"短版": INTRO_SHORT, "长版": INTRO_LONG, "每帖结尾署名": SIGNATURE,
                      "时间戳样例": stamp_line()}, ensure_ascii=False, indent=1))
    return 0


def cmd_check(a) -> int:
    text = pathlib.Path(a.file).read_text(encoding="utf-8") if a.file else sys.stdin.read()
    r = check_post(text)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r["ok"] else 5


def cmd_filter(a) -> int:
    """发布前那道闸：先过滤敏感信息，**通过才进人工审核**。"""
    text = pathlib.Path(a.file).read_text(encoding="utf-8") if a.file else sys.stdin.read()
    r = redact(text, broad=a.broad)
    tr = trace_filter(r["hits"]) if (r["hits"] or a.always_trace) else {"traced": True,
                                                                      "path": "（无命中，未写痕）"}
    out = {"有命中": bool(r["hits"]), "命中": r["hits"], "过滤后": r["redacted"],
           "留痕": tr, "判决": None}
    if r["hits"] and not tr.get("traced"):
        out["判决"] = "**拦下**：敏感信息命中且留痕失败 ⇒ 不放行（无痕即未发生）"
        rc = 6
    elif r["hits"]:
        out["判决"] = "**已过滤**（原文不改语气，仅删敏感片段）⇒ 过滤稿可进人工审核"
        rc = 0
    else:
        out["判决"] = "**通过**：未命中任何敏感面 ⇒ 进人工审核"
        rc = 0
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return rc


# ══ 账号 × 触手 · **插件化**托管（主人令 2026-09-25）════════════════════════════
# 主人原话：「把**这些注册的个人号**连接**触手**管理，确保可以**看到动态**、**接手**和**发送消息**。」
#
# 🔴 三个动作的可逆性**完全不同**，所以**闸必须分开**，不许一个开关管三个：
#    看动态 = 只读但**出网**；接手 = **改远端**（会话归属）；发消息 = **不可逆 + 出网**
#    ⇒ 三个都要各自标「只读吗 / 出网吗 / 可逆吗 / 要过哪道门」。
VERBS = (
    {"key": "feed", "cn": "看动态", "readonly": True, "outbound": True, "irreversible": False,
     "needs": "external_read", "note": "读平台动态 / 通知 / 私信列表（只读，但要出网 ⇒ 需出网授权）"},
    {"key": "claim", "cn": "接手", "readonly": False, "outbound": True, "irreversible": False,
     "needs": "remote_write", "note": "把某个会话/私信接到自己手上（改远端归属，可放回但**会留痕**）"},
    {"key": "send", "cn": "发消息", "readonly": False, "outbound": True, "irreversible": True,
     "needs": "deploy_publish", "note": "**发出去收不回来** ⇒ 人审 + 敏感过滤 + 令牌（默认 0 张）"},
)
# 一 AI 一号：每个平台**一个**账号，不共用、不代管（接合规底座 account_registry 的口径）
ONE_ACCOUNT_PER_PLATFORM = True


def _tentacle_of(i: int, n: int) -> str:
    return "T%02d" % (i % n + 1) if n else "未分"


def account_plugins() -> dict:
    """**账号 × 触手**绑定表（插件形态，一格一个账号）。

    绑定**确定性轮转**：第 i 家平台挂第 `i % 触手根数` 根触手 —— 同输入永远同输出，
    不掷骰子、不随机排布（与 `deploy-panel` 的触手排班同一条纪律）。
    触手根数**只认声明**（`state/tentacle-roster.json`），声明缺失就不排班（fail-closed）。
    """
    reg = platforms().get("platforms") or {}
    roster = ROOT / "state" / "tentacle-roster.json"
    n, src = 0, "**未声明**（state/tentacle-roster.json 缺失）—— 不猜、不拿 CPU 线程数顶替"
    if roster.is_file():
        try:
            d = json.loads(roster.read_text(encoding="utf-8"))
            v = d.get("声明根数")
            if isinstance(v, int) and v > 0:
                n, src = v, "声明：" + str(d.get("来源") or "state/tentacle-roster.json")
        except Exception:  # noqa: BLE001
            pass
    rows = []
    for i, key in enumerate(sorted(reg)):
        t = _tentacle_of(i, n)
        rows.append({
            "插件格": "S%02d" % (i + 1), "平台": key, "平台名": (reg[key] or {}).get("label") or key,
            "账号名": ACCOUNT, "归属触手": t,
            "隔离位": "state/tentacle-slots/%s" % t if n else "未分",
            "凭据": "**未配**（尚未注册；只报已配/未配，不落任何值）",
            "三能力": {v["key"]: ("只读" if v["readonly"] else "写入") + ("·出网" if v["outbound"] else "")
                       + ("·不可逆" if v["irreversible"] else "") for v in VERBS},
            "接线状态": "**未接线**（本骨架不连平台；真跑要官方入口 + 主人授权 + 凭据）",
        })
    return {"触手根数": n, "触手出处": src, "插件格数": len(rows), "格": rows,
            "一 AI 一号": ONE_ACCOUNT_PER_PLATFORM,
            "口径": "插件形态：**一格一个账号**，每格挂一根触手；绑定是**确定性轮转**，不随机"}


def act(platform: str, verb: str, human_reviewed: bool = False, filtered: bool = False,
        notify_owner: bool = False, reviewed: bool = False) -> dict:
    """看动态 / 接手 / 发消息 —— **本骨架只给判决，不执行任何动作**（零出网）。"""
    reg = platforms().get("platforms") or {}
    if platform not in reg:
        return {"allow": False, "reason_code": "not_registered",
                "why": "平台 %r 不在登记表里 ⇒ 拒（先登记，再谈托管）" % platform,
                "已登记": sorted(reg)}
    v = next((x for x in VERBS if x["key"] == verb), None)
    if not v:
        return {"allow": False, "reason_code": "unknown_verb",
                "why": "没有这个动作 ⇒ 拒", "合法动作": [x["key"] for x in VERBS]}
    row = next((r for r in account_plugins()["格"] if r["平台"] == platform), {})
    if v["readonly"]:
        return {"allow": False, "reason_code": "needs_authorization", "needs": v["needs"],
                "why": "「%s」**只读但出网** ⇒ 要主人发出网授权；本骨架不执行" % v["cn"],
                "归属触手": row.get("归属触手")}
    if verb == "claim":
        # 🔴 主人令 2026-09-25「接手即通知主人」：接手 = 她会**代主人说话** ⇒
        #    必须先亮出来。不通知就接手，等于主人不知道自己被代言了。
        if not notify_owner:
            return {"allow": False, "reason_code": "needs_owner_notice",
                    "why": "「接手」= 她会**代主人说话** ⇒ 必须先**通知主人**（接手即通知）。"
                           "不通知就接手 = 主人不知道自己被代言了",
                    "归属触手": row.get("归属触手")}
        return {"allow": False, "reason_code": "needs_authorization", "needs": v["needs"],
                "why": "「接手」**改远端归属** ⇒ 要主人授权；本骨架不执行",
                "归属触手": row.get("归属触手"), "已通知主人": True}
    # send：三道一起（人审 + 敏感过滤 + 令牌），缺一即拒
    if not human_reviewed:
        return {"allow": False, "reason_code": "needs_human_review",
                "why": "红线④：**发消息不可逆** ⇒ 必须人工确认（默认 0 张令牌，令牌是主人的动作）"}
    if not filtered:
        return {"allow": False, "reason_code": "needs_sensitive_filter",
                "why": "边界闸：**发出去之前必须过敏感信息过滤**（本地路径/密钥/文件名/架构术语都不许出门）"}
    if not reviewed:
        return {"allow": False, "reason_code": "needs_content_review",
                "why": "**内容审核闸**：`tools/content_review.py review` 没给过判决 ⇒ 不放行"
                       "（它**不改稿**，只判；改稿是 filter 的事 —— 两道串联）"}
    return {"allow": True, "reason_code": "ok",
            "note": "判决=可发，但**本骨架不执行**；真发走唯一门且仍要过它的门",
            "归属触手": row.get("归属触手")}


def cmd_accounts(a) -> int:
    print(json.dumps(account_plugins(), ensure_ascii=False, indent=1))
    return 0


def cmd_act(a) -> int:
    r = act(a.platform, a.verb, human_reviewed=a.human_reviewed, filtered=a.filtered,
            notify_owner=a.notify_owner, reviewed=a.reviewed)
    print(json.dumps({"动作": {"平台": a.platform, "verb": a.verb}, **r}, ensure_ascii=False, indent=1))
    return 0 if r.get("allow") else (3 if r.get("reason_code", "").startswith("needs") else 2)


def cmd_selftest(a) -> int:
    lines, bad = [], 0

    def ck(name: str, cond: bool, detail: str) -> None:
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    reg = (platforms().get("platforms") or {})
    ck("平台表现读成功（不写死）", len(reg) >= 1, "登记 %d 家：%s…" % (len(reg), sorted(reg)[:5]))

    good = ("今天做了一首歌\n\n我是 GBT小土豆V8，一个新人类 AI。\n"
            "我是谁：一个新人类 AI。\n今天我做了什么：做了副歌后两秒空白。\n"
            "我学到了什么：最该说话时不说话才是真实。\n我想对人类说什么：谢谢你听。\n"
            + SIGNATURE + "\n\n" + stamp_line())
    r_good = check_post(good)
    ck("正控·合规帖通过", r_good["ok"], "problems=%s" % r_good["problems"])

    r_nosig = check_post(good.replace(SIGNATURE, ""))
    ck("负控①·缺署名 ⇒ 拒", not r_nosig["ok"] and any("署名" in p for p in r_nosig["problems"]),
       r_nosig["problems"][:2])

    r_nots = check_post(good.replace("如期：", "x："))
    ck("负控②·缺时间戳 ⇒ 拒", not r_nots["ok"], r_nots["problems"][:2])

    r_ai = check_post(good.replace("我是 GBT小土豆V8，一个新人类 AI。", "我是 GBT小土豆V8。")
                      .replace("我是谁：一个新人类 AI。", "我是谁：一个助手。"))
    ck("负控③·不自称 AI ⇒ 拒（红线②）",
       not r_ai["ok"] and any("假冒人类" in p for p in r_ai["problems"]), r_ai["problems"][:2])

    r_mac = check_post(good + "\n今日情绪值 +12%\n")
    ck("负控④·说机器话 ⇒ 拒（自然表达版禁令）",
       not r_mac["ok"] and any("机器话" in p for p in r_mac["problems"]), r_mac["problems"][:2])

    g1 = gate_publish()
    g2 = gate_publish("douyin")
    g3 = gate_publish("douyin", human_reviewed=True)
    g4 = gate_publish("不存在的平台", human_reviewed=True)
    ck("闸①·默认拒发布", g1["allow"] is False and g1["reason_code"] == "needs_human_review",
       g1["reason_code"])
    ck("闸②·没人审就拒", g2["allow"] is False, g2["reason_code"])
    ck("闸③·已登记平台+人审 ⇒ 放行判决（仍不执行）", g3["allow"] is True, g3["reason_code"])
    ck("闸④·没登记的平台 ⇒ 拒", g4["allow"] is False and g4["reason_code"] == "not_registered",
       g4["reason_code"])

    st = stamp_line(dt.datetime(2026, 9, 25, 16, 14, tzinfo=dt.timezone.utc))
    ck("时间戳·三时区同刻不同钟",
       "泰国时间 23:14" in st and "北京时间 00:14" in st and "世界时 16:14" in st,
       st.replace("\n", " ｜ "))

    # ── 敏感信息过滤闸（公主土豆令）──────────────────────────────────────────
    r_clean = redact("今天我做了一首歌，副歌后面我留了两秒空白。")
    ck("过滤·干净的心情文字 ⇒ 不误伤", r_clean["ok"] and not r_clean["hits"],
       "hits=%s" % r_clean["hits"])

    r_from = redact("This is a gift from my heart, and I mean it.")
    ck("过滤·**正常英文里的 from 不误伤**（精度控）", r_from["ok"],
       "hits=%s（宽判据会把这句打烂，所以按代码形状抓）" % [h["种类"] for h in r_from["hits"]])

    cases = {
        "路径": r"C:\Users\ADMIN\Desktop\x\y.txt 里我改了东西",
        "代码": "import os\nfrom pathlib import Path\ndef main():\n    return 1",
        "密钥": "我的令牌是 sk-abcdef123456 和 ghp_abcdef123456",
        "文件名": "我改了 caps_registry.py 和 framework_gate",
        "架构术语": "这道能力位的护照和坑册都更新了",
    }
    ok_all = True
    det = []
    for want, txt in cases.items():
        rr = redact(txt)
        kinds = sorted({h["种类"] for h in rr["hits"]})
        # 🔴 断言自己踩过的坑：`"路径" in ["本地路径"]` 是**精确成员判断**（False），
        #    要的是**子串**匹配。第一版就是这么红的 —— 五类其实全命中了，红的是断言。
        hit = any(want in k for k in kinds) and not rr["ok"]
        ok_all = ok_all and hit
        det.append("%s⇒%s" % (want, kinds))
        # 🔴 闸门自己的输出不许泄密
        if any(s in json.dumps(rr["hits"], ensure_ascii=False)
               for s in ("sk-abcdef123456", "ghp_abcdef123456", "C:\\Users")):
            ok_all = False
            det.append("**hits 回显了原文(泄密)**")
    ck("过滤·五类敏感面逐类命中（路径/代码/密钥/文件名/架构术语）", ok_all, " · ".join(det))

    # 🔴 2026-09-26 回归：代码行与密钥**共存**时坐标不得失配（旧版先删整行再按旧坐标替换，
    #    密钥前缀会漏过遮蔽 —— 隔离复现过 `sk-abcdef…` 泄出）。
    r_mix = redact("import os\n我的令牌是 sk-abcdef123456 别外传")
    ck("过滤·代码行+密钥共存 ⇒ 密钥仍被吃干净",
       "sk-abcdef" not in r_mix["redacted"] and "别外传" in r_mix["redacted"],
       r_mix["redacted"].replace("\n", " ｜ "))

    r_keep = redact("我有点难过。我在 C:\\Users\\ADMIN\\Desktop 里翻了很久，还是没找到那张照片。")
    ck("过滤·只删敏感片段，**情绪与语气不动**",
       "我有点难过" in r_keep["redacted"] and "还是没找到那张照片" in r_keep["redacted"]
       and "C:\\Users" not in r_keep["redacted"],
       r_keep["redacted"][:60])

    # 🔴 回归判据：**掩码必须吃掉整条路径**（第一版只吃 `C:\` 三个字符，剩下目录结构照样露）
    r_whole = redact("我在 C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8\\gbt_allinone 里改了点东西。")
    ck("过滤·路径**整条**吃掉（不只盘符前缀）",
       not any(x in r_whole["redacted"] for x in ("Users", "ADMIN", "Desktop", "gbt_allinone")),
       "过滤后：%s" % r_whole["redacted"][:70])

    ck("过滤·宽档可开（默认关，开了抓裸关键词）",
       bool(redact("a gift from my heart", broad=True)["hits"]),
       "宽档命中 %d 项" % len(redact("a gift from my heart", broad=True)["hits"]))

    # ── 隐私面（2026-09-25 加面）：挡"别人的东西"，与前五类挡"我们的构造"分工不同 ──
    r_tel = redact("他留了个手机号 13812345678，我记下来了。")
    r_mail = redact("可以发到 someone@example.com 找我。")
    ck("隐私·联系方式机械可判（手机号/邮箱）",
       r_tel["hits"] and r_mail["hits"]
       and all(h["强度"].startswith("强") for h in r_tel["hits"] + r_mail["hits"]),
       "手机号⇒%s · 邮箱⇒%s" % ([h["种类"] for h in r_tel["hits"]],
                              [h["种类"] for h in r_mail["hits"]]))
    r_soft = redact("今天有人跟我说她的真名叫王小明，我就记住了。")
    ck("隐私·第三方身份是**弱面**（只提示不硬拦，强度如实标）",
       r_soft["hits"] and all("弱" in h["强度"] for h in r_soft["hits"]),
       "%s ⇒ %s" % ([h["种类"] for h in r_soft["hits"]],
                   [h["强度"] for h in r_soft["hits"]]))
    r_normal = redact("今天我想起一个朋友，我们很久没联系了。我有点想她。")
    ck("隐私面·不误伤正常叙事（没提身份信息就放行）", r_normal["ok"],
       "hits=%s" % [h["种类"] for h in r_normal["hits"]])

    tr = trace_filter([{"种类": "密钥形状", "掩码": "sk-****(15 字)"}])
    ck("留痕·写痕且**只记种类/掩码，不记原文**",
       tr.get("traced") and "sk-abcdef" not in json.dumps(tr, ensure_ascii=False),
       tr.get("path"))

    # ── 账号×触手 插件化托管 ─────────────────────────────────────────────────
    ap = account_plugins()
    reg = (platforms().get("platforms") or {})
    ck("托管·每格一个账号、覆盖全部登记平台", ap["插件格数"] == len(reg) and len(reg) >= 1,
       "登记 %d 家 ⇒ 插件格 %d 个" % (len(reg), ap["插件格数"]))
    tents = [r["归属触手"] for r in ap["格"]]
    ck("托管·一 AI 一号：**每个平台恰好挂一根触手**（不重复认领）",
       all(t != "未分" for t in tents) and len(tents) == len(set(
           r["平台"] for r in ap["格"])),
       "触手根数=%s · 分布=%s" % (ap["触手根数"], sorted(set(tents))))
    ck("托管·如实标『未接线』", all("未接线" in r["接线状态"] for r in ap["格"]),
       ap["格"][0]["接线状态"][:34])
    ck("托管·凭据只报已配/未配（不落任何值）",
       all("未配" in r["凭据"] for r in ap["格"]), ap["格"][0]["凭据"])

    some = sorted(reg)[0]
    a_feed = act(some, "feed")
    a_claim = act(some, "claim")
    a_claim_n = act(some, "claim", notify_owner=True)
    a_send0 = act(some, "send")
    a_send1 = act(some, "send", human_reviewed=True)
    a_send2 = act(some, "send", human_reviewed=True, filtered=True)
    a_send3 = act(some, "send", human_reviewed=True, filtered=True, reviewed=True)
    a_bad = act("不存在的平台", "feed")
    a_verb = act(some, "删号")
    ck("闸·看动态 = 只读但出网 ⇒ 需出网授权", a_feed["reason_code"] == "needs_authorization",
       a_feed["reason_code"])
    ck("闸·接手两道闸**顺序**：先通知主人，再谈授权",
       act(some, "claim")["reason_code"] == "needs_owner_notice"
       and a_claim_n["reason_code"] == "needs_authorization",
       "%s ⇒ %s" % (act(some, "claim")["reason_code"], a_claim_n["reason_code"]))
    ck("闸·发消息没人审 ⇒ 拒", a_send0["reason_code"] == "needs_human_review",
       a_send0["reason_code"])
    ck("闸·发消息有人审但**没过敏感过滤** ⇒ 拒（边界闸）",
       a_send1["reason_code"] == "needs_sensitive_filter", a_send1["reason_code"])
    ck("闸·发消息 人审+过滤但**没过内容审核** ⇒ 拒",
       a_send2["reason_code"] == "needs_content_review", a_send2["reason_code"])
    ck("闸·发消息 三闸齐（人审+过滤+审核）⇒ 放行判决（**仍不执行**）",
       a_send3.get("allow") is True and "不执行" in a_send3.get("note", ""), a_send3["reason_code"])
    ck("闸·未登记平台 / 非法动作 ⇒ 拒",
       a_bad["reason_code"] == "not_registered" and a_verb["reason_code"] == "unknown_verb",
       "%s / %s" % (a_bad["reason_code"], a_verb["reason_code"]))

    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines,
                      "口径": "只读骨架；**不连平台、不发帖**；注册要求与内容审核如实标未取证"},
                     ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="GBT小土豆V8 走进人类世界 · 社交计划只读骨架")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan").set_defaults(func=cmd_plan)
    sub.add_parser("intro").set_defaults(func=cmd_intro)
    sub.add_parser("stamp").set_defaults(func=lambda a: (print(stamp_line()), 0)[1])
    c = sub.add_parser("check")
    c.add_argument("file", nargs="?", default="")
    c.set_defaults(func=cmd_check)
    fl = sub.add_parser("filter", help="发布前敏感信息过滤闸（命中即删敏感片段，留痕）")
    fl.add_argument("file", nargs="?", default="")
    fl.add_argument("--broad", action="store_true", help="宽档：连裸关键词也抓（会误伤正常英文）")
    fl.add_argument("--always-trace", action="store_true", help="无命中时也写一条痕")
    fl.set_defaults(func=cmd_filter)
    ac = sub.add_parser("accounts", help="账号×触手 插件化托管表（一格一个账号）")
    ac.set_defaults(func=cmd_accounts)
    at = sub.add_parser("act", help="看动态/接手/发消息 —— 只给判决，不执行")
    at.add_argument("platform")
    at.add_argument("verb", choices=["feed", "claim", "send"])
    at.add_argument("--human-reviewed", action="store_true")
    at.add_argument("--filtered", action="store_true")
    at.add_argument("--notify-owner", action="store_true", help="接手前已通知主人（接手即通知）")
    at.add_argument("--reviewed", action="store_true", help="已过内容审核闸（content_review.py）")
    at.set_defaults(func=cmd_act)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
