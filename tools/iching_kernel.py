#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""iching_kernel · 周易**决策内核**（不是算命器）· 主人令 2026-09-25

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 数学本质（把话说清）
    阴=0 阳=1 ｜ 八卦 = 3-bit（8 态）｜ 六十四卦 = 6-bit（64 态）｜ 爻变 = 某位 0↔1
    六爻 = 6 个决策维度 ｜ 384 个转换点 = 64 态 × 6 位

## 🔴 三条必须先说清的诚实边界
1. **它不算命、不预测未来**。它把「想清楚」变成算法：提 6 个问题 → 组成 6-bit → 查表 → 得方向。
2. **卦名与卦义是两层，分开如实报**：
   - **卦名覆盖 64/64** —— 来自一份**可核对来源**（Wikipedia 王序表，`state/iching-king-wen.json`
     与 `tools/iching_king_wen.py` 头部记着 URL + sha256 + 12 道硬闸读数）。**只取三个不歧义字段**
     （卦名/下卦/上卦），**六爻位串由本仓推导**（下三爻+上三爻，爻自下而上）——不抄别人的位序约定。
   - **卦义覆盖 8/64** —— 只有 8 个纯卦有吉凶读法。**其余 56 卦的名称与结构有据、卦辞吉凶不编**：
     输出 `risk="未评分"`、动作挂 `吝⇒confirm`（要过 auth_gate），**判断交回给人**。
3. **风险分级不另起一套门**：`policy.PolicyDecision.risk` 现读只有 `low/medium/high`（3 档，在
   `evaluate()` 里算出来的），**不是可扩展注册表** ⇒ 本内核把吉凶悔吝**映射到现有的
   「动作 + 要不要过门」**，而不是自造一套并行风险体系。

## 五条红线（写死成代码）
不算命 · 不替人拍板 · **凶卦必停** · 每次咨询留痕（`source_kind="iching"`，⚠️ 需进
`trace_store` 的 origin 白名单才会被收）· 身份内核不变
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── 六十四卦全表（**自动生成**，见 tools/iching_king_wen.py 头部出处）────────────────
# 🔴 位序约定**必须与 bits() 一致**：`bits[0]` = **初爻**（下三爻 + 上三爻）。
#    上一版 bits() 发的是「上→初」，与卦表键「初→上」**反了** ⇒ 震↔艮、巽↔兑 被镜像
#    （坎/离/乾/坤是回文，侥幸对了 ⇒ 8 条自检全绿却带着真缺陷）。见 selftest 第 ⑨ 条。
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from iching_king_wen import KING_WEN, PROVENANCE as KW_PROVENANCE
except Exception as _kw_err:                       # 表没生成过 ⇒ 退回 8 纯卦，**如实报未加载**
    KING_WEN, KW_PROVENANCE = {}, {"未加载": repr(_kw_err)}

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HONEST_BOUNDARY = ("保证「决策结构化 · 状态可迁移 · 风险可分级」；"
                   "**保证不了「预测未来」** —— 它给框架，不给预言。所有决策最终由人拍板。")

# ── 八卦：3-bit，**爻自下而上**（初爻在最右）──────────────────────────────────
# 乾☰=111 兑☱=110 离☲=101 震☳=100 巽☴=011 坎☵=010 艮☶=001 坤☷=000
TRIGRAMS = {
    "111": ("乾", "天"), "110": ("兑", "泽"), "101": ("离", "火"), "100": ("震", "雷"),
    "011": ("巽", "风"), "010": ("坎", "水"), "001": ("艮", "山"), "000": ("坤", "地"),
}
TRIGRAM_ORDER = ("111", "110", "101", "100", "011", "010", "001", "000")

# ── 六爻维度（下→上：初/二/三/四/五/上）───────────────────────────────────────
DIMENSIONS = (
    ("timing", "时机", "时机未到，等待", "时机已到，出手"),
    ("resource", "资源", "资源不足，精简", "资源充足，扩张"),
    ("risk", "风险", "风险可控，继续", "风险偏高，谨慎"),
    ("collab", "协作", "独自执行", "需要协作"),
    ("authority", "决策权", "授权给触手", "主脑亲自决策"),
    ("exit", "退出", "可以终止", "必须坚持"),
)

# ── 风险词 → 动作/门（**映射到现有门禁机制**，不另起一套）──────────────────────
RISK_MAP = {
    "吉":   {"level": "green",  "action": "proceed", "gate": "none",      "说人话": "可执行，正常走"},
    "无咎": {"level": "gray",   "action": "proceed", "gate": "none",      "说人话": "中性，可执行"},
    "悔":   {"level": "yellow", "action": "adjust",  "gate": "none",      "说人话": "调整策略后继续"},
    "吝":   {"level": "orange", "action": "confirm", "gate": "auth_gate", "说人话": "有代价，需确认"},
    "厉":   {"level": "amber",  "action": "confirm", "gate": "auth_gate", "说人话": "高风险，二次确认"},
    "凶":   {"level": "red",    "action": "halt",    "gate": "block",     "说人话": "立即停止并上报"},
}

# ── 六十四卦表：**只录可推导的 8 个纯卦**（上卦=下卦）──────────────────────────
# 🔴 出处可核：六爻 = 下三爻 + 上三爻；纯卦 = 同一八卦叠两次。
#    ⚠️ 主人给的草稿里 `100100` 标「艮」、`011011` 标「兑」—— 按三爻组成，
#    100100 = 震下震上（震为雷）、011011 = 巽下巽上（巽为风）。**本表按可推导的来，不照抄错标。**
HEXAGRAMS = {
    "111111": {"name": "乾", "intent": "全力推进", "risk": "厉", "advice": "自强不息，防亢龙有悔"},
    "110110": {"name": "兑", "intent": "沟通协作", "risk": "吉", "advice": "和悦以进，朋友讲习"},
    "101101": {"name": "离", "intent": "清晰展示", "risk": "吉", "advice": "明两作，光明正大"},
    "100100": {"name": "震", "intent": "果断行动", "risk": "无咎", "advice": "震惊百里，动而后定"},
    "011011": {"name": "巽", "intent": "柔性渗透", "risk": "无咎", "advice": "随风巽入，柔而能进"},
    "010010": {"name": "坎", "intent": "冒险突破", "risk": "厉", "advice": "重险之中，需谨慎前行"},
    "001001": {"name": "艮", "intent": "停止等待", "risk": "无咎", "advice": "时止则止，时行则行"},
    "000000": {"name": "坤", "intent": "全面守成", "risk": "吉", "advice": "厚德载物，顺势而为"},
}
NAMED = len(HEXAGRAMS)
MISSING_NOTE = ("**卦名覆盖 %d/64**（全表来自可核对来源，见 iching_king_wen.py 头部）；"
                "**卦义覆盖 %d/64** —— 卦辞吉凶**不编**：没入库的只管结构，判断交回给人。"
                % (len(KING_WEN), NAMED))


@dataclass
class DecisionContext:
    """六爻决策上下文（每维 0/1）。

    🔴 **「没想清」是**推导**出来的，不是调用方填的**（实测踩过）：第一版把 `stuck` 做成可传入字段
    ⇒ 直接构造 `DecisionContext(timing=2)` 时它默认为空 ⇒ 非法值**绕过拒单**落到查表 ⇒
    `KeyError: '002'`。修：改为**由取值推导**（凡 ∉{0,1} 即"没想清"），调用方填不出不一致的状态。
    """
    timing: int = 0
    resource: int = 0
    risk: int = 0
    collab: int = 0
    authority: int = 0
    exit: int = 0

    def stuck_dims(self) -> list:
        return [cn for k, cn, _, _ in DIMENSIONS if getattr(self, k) not in (0, 1)]

    def bits(self) -> str:
        """6-bit：**下三爻 → 上三爻**，`bits[0]` = **初爻**。

        🔴 上一版这里发的是「上→初」（`exit` 打头），而卦表键是「初→上」——
        **两套约定反着**，于是**震的局势查出艮**（实测：`--timing 1 --collab 1` 回「艮」）。
        根因不是表错，是**自检从没问过「上下文指的那个卦，表里叫什么」**。
        """
        return "".join("%d" % getattr(self, k) for k, _, _, _ in DIMENSIONS)

    def as_payload(self) -> dict:
        return {k: getattr(self, k) for k, _, _, _ in DIMENSIONS}


def consult(ctx: DecisionContext) -> dict:
    """提 6 个问题 → 一个卦象 → 一个方向。**不算命**：没卦义就说没卦义。"""
    bits = ctx.bits()
    stuckd = ctx.stuck_dims()
    if stuckd or len(bits) != 6 or any(c not in "01" for c in bits):
        return {"ok": False, "reason_code": "missing_context",
                "why": "**盲猜即违规**：这几维还没想清 ⇒ 拒出决策", "缺": stuckd,
                "bits": bits}
    trig_low, trig_up = bits[:3], bits[3:]          # bits[0] = 初爻 ⇒ 前三=下卦
    gua = {"下": TRIGRAMS[trig_low][0], "上": TRIGRAMS[trig_up][0]}
    kw = KING_WEN.get(bits)                          # (王序号, 卦名, 下卦, 上卦, 卦符)
    trace = {"source_kind": "iching", "注意": "trace_store 有 origin 白名单，需先登记"}
    h = HEXAGRAMS.get(bits)

    if h:                                            # ① 有卦义 ⇒ 给完整方向
        return {"ok": True, "bits": bits, "上下卦": gua,
                "卦名": h["name"], "intent": h["intent"], "risk": h["risk"],
                "advice": h["advice"], "action": RISK_MAP[h["risk"]],
                "凶卦必停": h["risk"] == "凶", "卦义": "已收录", "留痕": trace}

    if kw:                                           # ② 有名有结构、**但没卦义** ⇒ 不编吉凶
        return {"ok": True, "bits": bits, "上下卦": gua,
                "卦名": kw[1], "王序号": kw[0], "卦符": kw[4],
                "risk": "**未评分**", "action": RISK_MAP["吝"],      # 吝 ⇒ confirm/auth_gate
                "卦义": "**未收录**（卦名与结构有据，吉凶卦辞不编）",
                "advice": "此卦**名与结构有据，卦辞吉凶未入库** ⇒ 只给结构，"
                          "**判断交回给人**（不替你拍板）",
                "留痕": trace}

    return {"ok": True, "bits": bits, "上下卦": gua,   # ③ 连表都没加载 ⇒ 如实说
            "卦名": "**未收录**", "risk": "**未评分**", "action": RISK_MAP["吝"],
            "卦义": "**未收录**",
            "advice": "全表未加载 ⇒ 按常规决策执行（**不猜卦义**）",
            "留痕": trace}


def change_path(cur: DecisionContext, tgt: DecisionContext) -> dict:
    """爻变引擎：从当前态到目标态**要变哪几爻**（= 汉明距离与位置）。"""
    a, b = cur.bits(), tgt.bits()
    changes = []
    for i, (c, t) in enumerate(zip(a, b)):          # i=0 是**初爻**（与 bits() 同步）
        if c != t:
            key, cn, yin, yang = DIMENSIONS[i]
            changes.append({"位": i + 1, "维度": cn, "从": yin if c == "0" else yang,
                            "到": yin if t == "0" else yang,
                            "变": "阴→阳(守→进)" if c == "0" else "阳→阴(进→守)"})
    return {"ok": True, "当前": a, "目标": b, "要变几爻": len(changes), "路径": changes,
            "读法": "变爻越少 ⇒ 越容易从当前态走到目标态（汉明距离就是代价的代理）"}


def coverage() -> dict:
    """**覆盖率如实报**：卦名覆盖 / 卦义覆盖**分开报**（别把两个数混成一个）。"""
    named, read = len(KING_WEN), len(HEXAGRAMS)
    return {"卦名覆盖": named, "卦义覆盖": read, "总数": 64,
            "卦名覆盖率": "%.1f%%" % (100.0 * named / 64),
            "卦义覆盖率": "%.1f%%" % (100.0 * read / 64),
            "说明": MISSING_NOTE,
            "全表出处": KW_PROVENANCE,
            "384 转换点": "64 态 × 6 位 = 384（结构就在 change_path 里，与卦名是否收录无关）"}


def cmd_consult(a) -> int:
    ctx = DecisionContext(timing=a.timing, resource=a.resource, risk=a.risk,
                          collab=a.collab, authority=a.authority, exit=a.exit_)
    print(json.dumps(dict(consult(ctx), **{"边界": HONEST_BOUNDARY}), ensure_ascii=False, indent=1))
    return 0


def cmd_table(a) -> int:
    print(json.dumps({"八卦": {k: {"名": v[0], "象": v[1]} for k, v in TRIGRAMS.items()},
                      "六爻维度": [{"键": k, "维度": cn, "0": yin, "1": yang}
                                   for k, cn, yin, yang in DIMENSIONS],
                      "有卦义之卦": HEXAGRAMS,
                      "六十四卦全表（卦名/上下卦·有据）": KING_WEN, "覆盖": coverage(),
                      "风险映射": RISK_MAP, "边界": HONEST_BOUNDARY},
                     ensure_ascii=False, indent=1))
    return 0


def cmd_selftest(a) -> int:
    lines, bad = [], 0

    def ck(name: str, cond: bool, detail: str) -> None:
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    # ① 八卦 3-bit 自洽：阴阳爻数 = 二进制里 1 的个数（乾三阳=3 … 坤三阴=0）
    # 🔴 这里原来结尾挂着 `or True` ⇒ **整条条件被短路成恒真**（判据假绿）。
    #    是 §一百一十二 的「判据质量台架」第一次真跑把它咬出来的（`or True` 命中本文件:223）。
    # 🔴 去掉 `or True` 后**当场变红**：期望值写的是 `[0,1,1,2,2,2,3]` **只有 7 个数**，
    #    而八卦有 8 个 —— 漏了一个「1」。实际是 **震(100)/坎(010)/艮(001) 各有一个阳爻**
    #    ⇒ 正确期望值是 `[0,1,1,1,2,2,2,3]`。
    #    **一个假判据底下压着一个错的期望值** —— 不把假的拆掉就永远看不见。
    ones = {k: k.count("1") for k in TRIGRAMS}
    ck("八卦·3-bit 与爻数自洽（乾 3 阳 / 坤 3 阴，8 态齐）",
       len(TRIGRAMS) == 8 and ones["111"] == 3 and ones["000"] == 0
       and sorted(ones.values()) == [0, 1, 1, 1, 2, 2, 2, 3],
       "1 的个数: %s" % json.dumps({TRIGRAMS[k][0]: v for k, v in ones.items()}, ensure_ascii=False))

    # ② 纯卦必须**上下卦相同**（可推导判据，不靠记名字）
    bad_pure = []
    for bits, h in HEXAGRAMS.items():
        if bits[:3] != bits[3:]:
            bad_pure.append((h["name"], bits))
    ck("六十四卦·已收录的**全是纯卦**（上卦==下卦，可推导）", not bad_pure,
       "非纯卦 %s" % (bad_pure or "无"))

    # ③ 纯卦的卦名必须与三爻组成一致（震=100、巽=011 —— 主人草稿这两处标反了）
    ck("卦名与三爻组成一致（震 100100 / 巽 011011，**不照抄错标**）",
       HEXAGRAMS["100100"]["name"] == "震" and HEXAGRAMS["011011"]["name"] == "巽",
       "100100=%s · 011011=%s" % (HEXAGRAMS["100100"]["name"], HEXAGRAMS["011011"]["name"]))

    # ④ 有名有结构、但**卦义未收录** ⇒ 只给结构、不编吉凶、交回给人
    r = consult(DecisionContext(timing=1, resource=1, risk=1, collab=1, authority=1, exit=0))
    ck("有名无卦义 ⇒ 只给结构、**不编吉凶**、交回给人",
       r["卦名"] == "夬" and r["risk"] == "**未评分**" and "不替你拍板" in r["advice"],
       "%s(第%s卦) risk=%s" % (r["卦名"], r.get("王序号"), r["risk"]))

    # ⑤ 缺上下文 ⇒ 拒（盲猜即违规）
    r_bad = consult(DecisionContext(timing=2))
    ck("缺上下文 ⇒ **拒出决策**（盲猜即违规）",
       r_bad["ok"] is False and r_bad["reason_code"] == "missing_context", r_bad["why"][:40])

    # ⑥ 凶卦必停（用 6-bit 直接查表验红旗）
    xiong = [k for k, v in HEXAGRAMS.items() if v["risk"] == "凶"]
    ck("凶卦必停·映射挂在 block + halt",
       RISK_MAP["凶"]["action"] == "halt" and RISK_MAP["凶"]["gate"] == "block"
       and all(RISK_MAP[v["risk"]]["level"] in ("green", "gray", "yellow", "orange", "amber", "red")
               for v in HEXAGRAMS.values()),
       "已收录里凶卦 %d 个（**未评分卦走 吝⇒confirm 过门**，不伪造凶吉）" % len(xiong))

    # ⑦ 爻变：汉明距离 = 要变几爻（384 转换点的结构判据）
    a1 = DecisionContext(timing=1)
    b1 = DecisionContext(timing=0, exit=1)
    cp = change_path(a1, b1)
    ck("爻变·要变几爻 == 两态 6-bit 的汉明距离", cp["要变几爻"] == 2,
       "%s → %s ⇒ %d 爻" % (cp["当前"], cp["目标"], cp["要变几爻"]))

    # ⑧ 覆盖如实（**卦名覆盖与卦义覆盖分开报**）
    cov = coverage()
    ck("覆盖·卦名 %d/64 与卦义 %d/64 **分开报**" % (cov["卦名覆盖"], cov["卦义覆盖"]),
       cov["卦名覆盖"] == len(KING_WEN) and cov["卦义覆盖"] == len(HEXAGRAMS)
       and "不编" in cov["说明"],
       "名 %s · 义 %s" % (cov["卦名覆盖率"], cov["卦义覆盖率"]))

    # ⑨ 🔴 **位序 join 判据** —— 上一版**缺的就是这条**，于是「震的局势查出艮」还能全绿。
    #    坎/离/乾/坤 是回文，位序反了也照样对 ⇒ 只有拿**非回文**的卦才咬得住。
    mirror = []
    for label, kw, want in (
            ("震", {"timing": 1, "collab": 1}, "震"),
            ("艮", {"risk": 1, "exit": 1}, "艮"),
            ("巽", {"resource": 1, "risk": 1, "authority": 1, "exit": 1}, "巽"),
            ("兑", {"timing": 1, "resource": 1, "collab": 1, "authority": 1}, "兑")):
        rr = consult(DecisionContext(**kw))
        if rr["卦名"] != want:
            mirror.append("%s 查出 %s" % (want, rr["卦名"]))
    ck("位序·**震/艮/巽/兑 不被镜像**（非回文卦才是真判据）", not mirror,
       "；".join(mirror) if mirror else "震100100 · 艮001001 · 巽011011 · 兑110110 全对")

    # ⑩ 全 64 态：上下文推导的上下卦 == 表里声明的上下卦（**逐态 join**）
    mism, notok = [], []
    for bits, ent in KING_WEN.items():
        vals = [int(c) for c in bits]
        cx = DecisionContext(**{k: vals[i] for i, (k, _, _, _) in enumerate(DIMENSIONS)})
        if cx.bits() != bits:
            mism.append("%s 回路成 %s" % (bits, cx.bits()))
            continue
        rr = consult(cx)
        if not rr.get("ok") or rr["上下卦"] != {"下": ent[2], "上": ent[3]}:
            notok.append("%s %s≠%s/%s" % (bits, rr["上下卦"], ent[2], ent[3]))
    ck("全 64 态·位串↔上下卦 **双向往返**都对", len(KING_WEN) == 64 and not mism and not notok,
       "表 %d 态 ｜ 回路错 %d ｜ 卦不符 %d" % (len(KING_WEN), len(mism), len(notok)))

    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines, "边界": HONEST_BOUNDARY}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="周易决策内核（不算命 · 不替人拍板 · 凶卦必停）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("consult", help="提 6 个问题 → 一个卦象 → 一个方向")
    for k in ("timing", "resource", "risk", "collab", "authority"):
        c.add_argument("--%s" % k, type=int, default=0, choices=[0, 1])
    c.add_argument("--exit", dest="exit_", type=int, default=0, choices=[0, 1])
    c.set_defaults(func=cmd_consult)
    sub.add_parser("table").set_defaults(func=cmd_table)
    sub.add_parser("coverage").set_defaults(
        func=lambda a: (print(json.dumps(coverage(), ensure_ascii=False, indent=1)), 0)[1])
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
