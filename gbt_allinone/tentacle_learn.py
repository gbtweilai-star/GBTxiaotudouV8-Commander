# -*- coding: utf-8 -*-
# GBT小土豆V8 永久钢印 · 开发者：自由的风 · 守护者：公主土豆
"""tentacle_learn -- 触手扫描·采集·学习（主人令 2026-10-16：这是必要的）

四步闭环：**scan 扫描 → collect 采集 → extract 提炼 → learn 入库**，最后复验“真的进了语料/名册”。
红线：只扫授权/公开面 · 隐私脱敏 · **采集物与语料不外发** · 每步留痕 · 取不到就写未读到。
op：scan / collect / extract / learn / loop / check / route（**全只读·零作用域·不出网**）
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "触手扫描采集学习-蒸馏.md"
OPS = ("scan", "collect", "extract", "learn", "loop", "check", "route")
SURFACES = ["能力面（capability-audit / 名册）", "页面面（holo_pet_w3 / state）",
            "文件面（本仓可读文件）", "设备面（屏幕/摄像头/麦）", "网面（只对授权域）"]


def scan(surface: str = "") -> dict:
    return {"ok": True, "op": "scan", "kind": "tentacle_learn", "surface": (surface or "").strip() or "（未限定，扫全面）",
            "surfaces": SURFACES,
            "rule": "**先看后动（第 37 条）**：扫描本身就是“看”，但只能看**授权/公开**面",
            "steps": ["列出可扫面与各面需要的授权", "逐面现读（读不到就写未读到）",
                      "产出**可采清单**（面 · 数量 · 来源 · 是否含隐私）"],
            "judges": ["每个面能指出现读命令", "没授权的面一律列为“不扫”并说明缺哪把钥匙"], "docs": str(DOC)}


def collect(surface: str = "", scope: str = "") -> dict:
    if not (scope or "").strip():
        return {"ok": False, "reason": "need_scope", "how": "采集必须先写清**范围与用途**（fail-closed）"}
    return {"ok": True, "op": "collect", "kind": "tentacle_learn", "surface": (surface or "").strip(), "scope": scope,
            "rule": "**只采授权/公开面**；去重 · 带**来源 URL/路径 + 时间戳** · 落我们自己的库",
            "redlines": ["不采隐私（报报护带、私人通讯、凭据）", "不绕验证码/不撞库",
                         "采集物**不外发**", "每批留痕", "取不到就写未读到"]}


def extract(material: str = "") -> dict:
    return {"ok": True, "op": "extract", "kind": "tentacle_learn", "material": (material or "").strip() or "（未给采集物）",
            "outputs": ["事实（带出处）", "规则/启发式（if 情形 then 做法）",
                        "反模式（坑）", "待验项（拿不准的标出来）"],
            "judges": ["每条能指回采集物的具体位置", "**拿不准的不进入 learn**（先标待验）"]}


def learn(family: str = "", material: str = "") -> dict:
    return {"ok": True, "op": "learn", "kind": "tentacle_learn", "family": (family or "").strip() or "（未给族）",
            "material": (material or "").strip() or "（未给提炼物）",
            "rule": "入库必须**带出处 + 计入语料族 + 登记索引**；新增即清旧",
            "steps": ["写成语料条（instruction/output/family）", "跑配比器（防淹没）",
                      "登记索引 + 记账", "复验：真的能被检索/能被现读到"],
            "judges": ["入库后**能被现读验证**（否则不算学到）", "与既有族去重"]}


def loop(surface: str = "", scope: str = "") -> dict:
    return {"ok": True, "op": "loop", "kind": "tentacle_learn", "surface": surface, "scope": scope,
            "loop": ["① scan（列可扫面）", "② collect（只采授权面）", "③ extract（提炼与标待验）",
                     "④ learn（入库 + 登记）", "⑤ **复验**（能检索到吗？能现读到吗？）", "⑥ 回到 ①（新面会不断出现）"],
            "guard": ["每轮记耗时（时间/采集量）", "连续两轮无新面 ⇒ 如实报停",
                      "**不允许把“扫了很久”当成果**"],
            "note": "与既有位的分工：devour_scan/devour_reflect（吞仓）· book_skill（书→技能）· workflow_forge/tdd_loop（工作流）；本件管**触手面**的扫采学"}


def check() -> dict:
    return {"ok": True, "op": "check", "kind": "tentacle_learn",
            "rules": ["只扫/只采 **授权与公开**面；未授权一律不扫并说明缺哪把钥匙",
                      "**隐私脱敏**；采集物与语料**不外发**", "每步留痕（无痕即不存在）",
                      "**拿不准的不进入 learn**", "入库后必须可现读验证（否则不算学到）",
                      "本 op 集**全只读**；真扫真采走既有位（browser / native_browser / sec_sweeper / 触手眼）"], "docs": str(DOC)}


def route(surface: str = "") -> dict:
    return {"ok": True, "op": "route", "kind": "tentacle_learn", "surface": (surface or "").strip(),
            "map": [{"要什么": "看有哪些面可扫", "走": "op=scan"},
                    {"要什么": "真采集", "走": "op=collect（带 scope）+ browser/sec_sweeper"},
                    {"要什么": "从采集物提炼", "走": "op=extract"},
                    {"要什么": "进语料库", "走": "op=learn + 配比器"},
                    {"要什么": "一条龙闭环", "走": "op=loop"}], "direct": True}


def run(op: str = "scan", **kw) -> dict:
    o = (op or "scan").strip().lower()
    if o == "scan":
        return scan(kw.get("surface") or "")
    if o == "collect":
        return collect(kw.get("surface") or "", kw.get("scope") or "")
    if o == "extract":
        return extract(kw.get("material") or "")
    if o == "learn":
        return learn(kw.get("family") or "", kw.get("material") or "")
    if o == "loop":
        return loop(kw.get("surface") or "", kw.get("scope") or "")
    if o == "check":
        return check()
    if o == "route":
        return route(kw.get("surface") or "")
    return {"ok": False, "reason": "unknown_op", "op": o, "known": list(OPS)}
