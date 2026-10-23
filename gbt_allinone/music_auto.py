# -*- coding: utf-8 -*-
# ⬻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""music_auto —— **音乐自动化**（主人令 2026-10-16：把 Folia 蒸馏到音乐自动化里）

蒸自 **chthollyphile/folia-major**（AGPL-3.0）的**思想**，**不搬代码**：
  核心不是“做个播放器”，是**四条时间轴对齐**：歌词 · 音频 · 主题（配色）· 动画。

六步流水线：选源 → 匹词 → 定题 → 出片 → 分发 → 验收。
op：plan / sources / lyrics / theme / export / route / check（**全只读·零作用域·不出网**）
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "Folia-音乐自动化-蒸馏.md"
READ_OPS = ("plan", "sources", "lyrics", "theme", "export", "route", "check")


def plan(goal: str = "") -> dict:
    g = (goal or "").strip()
    if not g:
        return {"ok": False, "reason": "need_goal", "how": "给一句话，例：把这张专辑做成歌词视频"}
    steps = [
        {"n": 1, "what": "选源", "op": "sources", "判据": "能读到歌曲元信息（来源+标题+时长）"},
        {"n": 2, "what": "匹词", "op": "lyrics", "判据": "歌词与时间轴都对上；对不上就写未匹配"},
        {"n": 3, "what": "定题", "op": "theme", "判据": "主色取自封面，对比度 ≥ 4.5:1（WCAG 2.2）"},
        {"n": 4, "what": "出片", "op": "export", "判据": "字幕与画面同步，导出端实测可放"},
        {"n": 5, "what": "分发", "op": "route", "判据": "对外只开只读面；音频与歌词不外发"},
        {"n": 6, "what": "验收", "op": "check", "判据": "边界四条全绿"},
    ]
    return {"ok": True, "op": "plan", "kind": "music_auto", "goal": g, "steps": steps,
            "出处": str(DOC), "来源仓": "chthollyphile/folia-major（AGPL-3.0，只蒸思想）"}


def sources() -> dict:
    nav = bool(os.environ.get("NAVIDROME_URL") or os.environ.get("NAVIDROME_BASE"))
    netease = bool(os.environ.get("NETEASE_API_BASE") or os.environ.get("VITE_NETEASE_API_BASE"))
    return {"ok": True, "op": "sources", "kind": "music_auto",
            "sources": [
                {"name": "本地音乐库", "凭据": "不需", "现读": "可用（走本机目录）"},
                {"name": "Navidrome", "凭据": "NAVIDROME_URL + 账号", "现读": "已配" if nav else "未配"},
                {"name": "网易云（api-enhanced）", "凭据": "自建 API 地址", "现读": "已配" if netease else "未配"},
                {"name": "酷狗 / QQ", "凭据": "各自 API", "现读": "未配"},
            ],
            "_口径": "平台能力需凭据就如实报「未配」；凭据不入仓不入日志"}


def lyrics() -> dict:
    return {"ok": True, "op": "lyrics", "kind": "music_auto",
            "口径": ["先匹逐字（LRC 带时间轴），没有就用整行 LRC，再没有就降级为纯音频",
                     "**对不上就写「未匹配」，不编时间轴**",
                     "多语言：原文 + 译文可并存，各自带时间轴",
                     "纯音乐：不假造歌词，转“仅音频”模式"],
            "判据": "时间轴单调递增 · 首句时间 ≤ 时长 · 末句时间 ≥ 0"}


def theme() -> dict:
    return {"ok": True, "op": "theme", "kind": "music_auto",
            "口径": ["主色取自封面（主色+辅色+强调色 三档）",
                     "对比度必须过 **WCAG 2.2**：正文 ≥ 4.5:1 · 大字 ≥ 3:1 · 非文本 ≥ 3:1",
                     "深浅两套主题（沉浸暗 / 亮堂白），同一套取色母子"],
            "相关胶囊": "wcag-2-2-对比度算法 · 休谟美学（真裁判）"}


def export() -> dict:
    return {"ok": True, "op": "export", "kind": "music_auto",
            "路线": [
                {"产物": "歌词视频（全屏）", "走哪": "渲染链（帧同步）", "判据": "字幕与音频同步导出可放"},
                {"产物": "字幕文件（lrc/srt）", "走哪": "文档能力位", "判据": "回读后时间轴不变"},
                {"产物": "静态歌词卡", "走哪": "文档/图片能力位", "判据": "对比度过 WCAG"},
            ],
            "_口径": "本位**不出片**；只给路线与判据，真出片走已有能力位"}


def route(goal: str = "") -> dict:
    return {"ok": True, "op": "route", "kind": "music_auto", "goal": (goal or "").strip(),
            "steps": [
                {"where": "意图", "via": "一句话"},
                {"where": "能力位", "via": "cap music_auto"},
                {"where": "取歌", "via": "本地库 / Navidrome / 平台 API（凭据就报已配）"},
                {"where": "出片", "via": "渲染链"},
            ], "直达": True, "no_local_model": True}


def check() -> dict:
    return {"ok": True, "op": "check", "kind": "music_auto",
            "rules": ["边界1 AGPL-3.0 ⇒ 只蒸思想不搬代码",
                      "边界2 音频与歌词不外发（版权）",
                      "边界3 平台凭据只报已配/未配，不入仓",
                      "边界4 不编时间轴（对不上就写未匹配）"],
            "出处": str(DOC)}


def run(op: str = "plan", **kw) -> dict:
    o = (op or "plan").strip().lower()
    if o == "plan":
        return plan(kw.get("goal") or "")
    if o == "sources":
        return sources()
    if o == "lyrics":
        return lyrics()
    if o == "theme":
        return theme()
    if o == "export":
        return export()
    if o == "route":
        return route(kw.get("goal") or "")
    if o == "check":
        return check()
    return {"ok": False, "reason": "unknown_op", "op": o, "known": list(READ_OPS)}

