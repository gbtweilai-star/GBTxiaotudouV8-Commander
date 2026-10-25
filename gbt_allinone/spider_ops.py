# -*- coding: utf-8 -*-
# GBT小土豆V8 永久钢印 · 开发者：自由的风 · 守护者：公主土豆
"""spider_ops —— 自适应抓取编排（主人令 2026-10-16：把 Scrapling 蒸成原生能力）

蒸自 **D4Vinci/Scrapling**（BSD-3-Clause · Python · 88,008 星）的**思想**，不搬代码：
  核心是 **adaptive**：页面结构一变，原选择器就废，所以要**自适应回找**（多路径 + 结构指纹 + 相似度），
  并支持从**单请求**到**全站爬取**的连续形态；自带反检测能力（**我们只取其正当用法**）。
**我们的边界**：只抓授权目标 · 遵守 robots 与站点条款 · 不撞库 · 不绕验证码 · 不抓个人隐私 · 留痕。
op：plan / adaptive / fetch / parse / robots / check / route（**全只读·零作用域·不出网·不动手**）
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "Scrapling-自适应抓取-蒸馏.md"
OPS = ("plan", "adaptive", "fetch", "parse", "robots", "check", "route")


def plan(target: str = "", scope: str = "") -> dict:
    t = (target or "").strip()
    if not t:
        return {"ok": False, "reason": "need_target", "how": "给目标站点/页面；**并给抓取范围与用途**"}
    if not (scope or "").strip():
        return {"ok": False, "reason": "need_scope", "how": "**没范围不抓**：写清范围（哪些路径、多少页、什么用途）"}
    return {"ok": True, "op": "plan", "kind": "spider_ops", "target": t, "scope": scope,
            "shapes": ["单请求（一个页面取一次）", "列表页翻页", "分类树递归", "全站爬取（需限速与去重）"],
            "steps": ["定范围与用途", "先取样例页", "定字段表", "试抓 1 页", "全量抓（限速/去重/断点续抓）", "回读与出处登记"],
            "judges": ["每条数据能指回 URL 与取数时间", "空值如实空，不编", "遵守 robots 与站点条款"],
            "source": "D4Vinci/Scrapling（BSD-3-Clause · 只蒸思想）", "doc": str(DOC)}


def adaptive() -> dict:
    return {"ok": True, "op": "adaptive", "kind": "spider_ops",
            "problem": "页面结构一改，写死的选择器就废（抓取最常见的慢性故障）",
            "how": ["同一元素取**多条候选路径**（CSS 多写法 + XPath + 文本锚 + 相对结构）",
                    "存**结构指纹**（父链/属性集合/相邻文本）",
                    "页面变化时按**相似度回找**，命中即更新路径并留痕",
                    "找不到就如实报**未定位**，不许猜元素"],
            "judges": ["回找命中要给出相似度与依据", "路径更新必须留痕（新增即清旧：旧路径作废）"],
            "source": "D4Vinci/Scrapling 的 adaptive 思想（BSD-3-Clause）"}


def fetch() -> dict:
    return {"ok": True, "op": "fetch", "kind": "spider_ops",
            "rules": ["并发有上限 · 限速 · 失败重试带退避 · URL 去重 · **断点续抓**",
                      "真抓走既有能力位（browser / native_browser / omni_web / topic_web）",
                      "**不出网的能力位审批链照旧**：需要时由主人授权",
                      "抓取结果只落我们自己的目录，登记来源与时间"],
            "judges": ["同一 URL 不重复抓（去重台账）", "中断后能从断点续", "每批留痕"]}


def parse() -> dict:
    return {"ok": True, "op": "parse", "kind": "spider_ops",
            "schema_rule": "先定字段表再抓：字段名 · 类型 · 是否必填 · 出处（URL+选择器路径）",
            "rules": ["**空值如实空**，不用推测补", "数值带单位与量纲", "时间统一时区",
                      "第三方个人信息不入库（隐私红线）"]}


def robots() -> dict:
    return {"ok": True, "op": "robots", "kind": "spider_ops",
            "policy": ["先读 robots.txt 与站点条款，禁止区不抓", "限速不压垮对方服务",
                       "**不绕验证码、不撞库、不伪装他人身份**", "只抓公开可访问内容",
                       "被抓方表示反对即停"],
            "note": "Scrapling 的反检测能力我们**只用在正当场景**（如自有站点/授权站点），不用于规避正当限制"}


def check() -> dict:
    return {"ok": True, "op": "check", "kind": "spider_ops",
            "rules": ["BSD-3-Clause ⇒ 只蒸思想不搬代码", "只抓授权/公开目标 · 遵守 robots 与条款",
                      "不绕验证码 · 不撞库 · 不抓个人隐私", "每条数据可指回 URL 与时间",
                      "真抓走既有能力位；本 op 集全只读", "落点只走我们自己的目录"],
            "doc": str(DOC)}


def route(target: str = "") -> dict:
    return {"ok": True, "op": "route", "kind": "spider_ops", "target": (target or "").strip(),
            "map": [{"要什么": "定抓取计划", "走": "cap spider_ops op=plan"},
                    {"要什么": "页面改了怎么回找", "走": "cap spider_ops op=adaptive"},
                    {"要什么": "真抓", "走": "browser / native_browser / omni_web / topic_web"},
                    {"要什么": "抽取口径", "走": "cap spider_ops op=parse"},
                    {"要什么": "合规边界", "走": "cap spider_ops op=robots"}],
            "direct": True}


def run(op: str = "plan", **kw) -> dict:
    o = (op or "plan").strip().lower()
    if o == "plan":
        return plan(kw.get("target") or "", kw.get("scope") or "")
    if o == "adaptive":
        return adaptive()
    if o == "fetch":
        return fetch()
    if o == "parse":
        return parse()
    if o == "robots":
        return robots()
    if o == "check":
        return check()
    if o == "route":
        return route(kw.get("target") or "")
    return {"ok": False, "reason": "unknown_op", "op": o, "known": list(OPS)}
