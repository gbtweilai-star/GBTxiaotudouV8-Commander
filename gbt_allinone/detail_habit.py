# -*- coding: utf-8 -*-
"""细节化习惯（**调用侧**门口）：一步/一段文本就地判，不合格就如实标缺什么。

主人令（2026-10-12）：「对比一下把 V8 缺少的能力在自己项目树上生出，别去搬过来」。

同源声明（先读这一段，免得长出第二份）：V8 早有这件东西 ——
`tools/codex-scripts/detail-check.py`（主人令 2026-10-09，报头逐字写着「逐步细节化判据」），
口径是**五问**：输入 · 动作 · 明细 · 判据 · 接点；它的判据在
`gbt_allinone/tests/test_detail_habit.py`。那件查的是**报告**（report.json 的 steps），
本件查的是**调用现场**（单步 dict / 一段文本 / 一批步骤）。**同一套口径，两个面**：
五问以 `detail-check.py` 为准，本件只读它的常量做同源比对（op=same_source），
比对不过就红 —— 这就是仓规第 11 条要的「由判据盯着」，不是靠人记。

本件另加**三条扩展**（V8 既有件没有、V9 有）：模糊词禁用 · 回读三件 · 一步产出上限。
扩展归扩展，**五问才是底**：底不齐，扩展齐了也不算完成。

只读：本件不写盘（要留痕走既有账本位 store/work_log.jsonl / logbook.py，不另造第二本账）。

用法（经唯一门）：
    python tools/codex-scripts/five-dim.py cap detail_habit "{\"op\":\"habit\"}"
    python tools/codex-scripts/five-dim.py cap detail_habit "{\"op\":\"same_source\"}"
    python tools/codex-scripts/five-dim.py cap detail_habit "{\"op\":\"check_step\",\"step\":{\"输入\":\"x\"}}"

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import re
from pathlib import Path

# 五问：**以 tools/codex-scripts/detail-check.py 为准**（改这里之前先改那件）
QUINTET = ("输入", "动作", "明细", "判据", "接点")

# 扩展三条（本件独有；不覆盖五问）
READBACK = ("命令", "退出码", "读数")
VAGUE = (
    "应该可以", "应该行", "应该没问题", "大概", "差不多", "基本上",
    "可能是", "估计", "后续优化", "先这样", "暂时这样", "暂时先",
    "不影响", "问题不大", "看着还行", "差不多了", "优化一下",
    "再看看", "感觉可以", "理论上", "应该够用", "一般没问题",
    # 主人令 2026-10-13：**猜想类词**也算"没亲测"的语言指纹 —— 依据只能是亲测跑通的原始读数
    "假设", "猜想", "假如", "设想", "从架构上讲", "架构上", "按架构",
    "推演一下", "我觉得", "我感觉", "多半是", "想必",
)
MAX_ARTIFACTS = 3

_ROOT = Path(__file__).resolve().parents[1]
_CHECK_TOOL = _ROOT / "tools" / "codex-scripts" / "detail-check.py"

_ALIASES = {
    "input": "输入", "inputs": "输入",
    "action": "动作", "step": "动作",
    "detail": "明细", "details": "明细", "items": "明细",
    "judge": "判据", "criterion": "判据", "criteria": "判据", "acceptance": "判据",
    "point": "接点", "join": "接点", "handoff": "接点", "output": "接点",
    "cmd": "命令", "command": "命令", "commands": "命令",
    "rc": "退出码", "exit_code": "退出码", "returncode": "退出码",
    "reading": "读数", "readings": "读数", "observed": "读数",
}


def _norm(step: dict) -> dict:
    """别名键归一到规范键（同义冲突保留先出现的，不覆盖）。"""
    out = {}
    for k, v in (step or {}).items():
        out.setdefault(_ALIASES.get(str(k).strip().lower(), str(k).strip()), v)
    return out


def _text_of(v) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, (list, tuple, set)):
        return " ".join(_text_of(x) for x in v)
    if isinstance(v, dict):
        return " ".join(_text_of(x) for x in v.values())
    return str(v)


def _present(v) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, tuple, set, dict)):
        return len(v) > 0
    return True


def _vague_hits(text: str) -> list:
    hits = []
    for w in VAGUE:
        for m in re.finditer(re.escape(w), text or ""):
            hits.append({"词": w, "位置": m.start()})
    return sorted(hits, key=lambda h: h["位置"])


def same_source() -> dict:
    """同源判据：本件的五问必须与 detail-check.py 的 QUINTET 逐字相同。

    读不到那件（改名/挪走）就判红并说明读不到，**不许默认过**（fail-closed）。
    """
    if not _CHECK_TOOL.is_file():
        return {"ok": False,
                "为什么": "读不到真源 %s（**判据没跑，不是通过**）" % _CHECK_TOOL,
                "本件五问": list(QUINTET)}
    src = _CHECK_TOOL.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"QUINTET\s*=\s*\(([^)]*)\)", src)
    if not m:
        return {"ok": False,
                "为什么": "真源里读不到 QUINTET 定义（**判据没跑，不是通过**）",
                "本件五问": list(QUINTET)}
    parts = [x.strip().strip('"').strip("'") for x in m.group(1).split(",")]
    theirs = tuple(p for p in parts if p)
    ok = theirs == QUINTET
    return {
        "ok": ok,
        "真源": str(_CHECK_TOOL),
        "真源五问": list(theirs),
        "本件五问": list(QUINTET),
        "为什么": ("逐字相同" if ok
                   else "**两处口径分叉了** —— 改一处必须改另一处（仓规第 11 条）"),
    }


def habit() -> dict:
    """习惯全文（人可读）：五问为主，扩展三条随附。"""
    return {
        "ok": True,
        "名字": "细节化",
        "一句话": "每一步答满五问、明细必须逐项；形容词落成数值，做完必须回读。",
        "五问": list(QUINTET),
        "五问真源": {"件": "tools/codex-scripts/detail-check.py",
                     "查什么": "报告（report.json 的 steps）",
                     "判据": "gbt_allinone/tests/test_detail_habit.py",
                     "同源判据": "op=same_source"},
        "本件覆盖面": "调用现场（单步 dict / 一段文本 / 一批步骤）",
        "扩展三条": {"回读三件": list(READBACK), "模糊词": list(VAGUE),
                     "一步产出上限": MAX_ARTIFACTS},
        "判定入口": {"同源": "op=same_source", "整段文本": "op=check_text（给 text）",
                     "单步": "op=check_step（给 step）", "多步": "op=check（给 steps 数组）"},
        "只读声明": "本件不写盘；要留痕走 store/work_log.jsonl 或 logbook.py（不另造第二本账）",
    }


def check_text(text: str) -> dict:
    """查一段文本里的模糊词（只报命中，不改写、不判语义）。"""
    hits = _vague_hits(text or "")
    return {
        "ok": not hits,
        "判定": "过" if not hits else "驳回",
        "长度": len(text or ""),
        "命中数": len(hits),
        "命中": hits,
        "为什么": ("没有模糊词" if not hits
                   else "命中模糊词 —— 形容词必须落成数值（例：更快 到 快多少 ms）"),
    }


def check_step(step: dict) -> dict:
    """查一步：五问齐不齐 · 明细是否逐项 · 回读三件齐不齐 · 模糊词 · 产出上限。

    部分合格不算合格：缺哪件点哪件，本件不替调用方补。
    """
    s = _norm(step if isinstance(step, dict) else {})
    miss5 = [f for f in QUINTET if not _present(s.get(f))]

    bad = []
    detail = s.get("明细")
    if detail is not None and (not isinstance(detail, (list, tuple)) or len(detail) < 1):
        bad.append("明细不是逐项（必须是 >=1 条的列表，现在是 %s）—— 只报一个合计数 = 没有细节"
                   % type(detail).__name__)
    judge = s.get("判据")
    if isinstance(judge, dict) and "过" not in judge:
        bad.append("判据没给「过/不过」")

    miss_rb = [f for f in READBACK if not _present(s.get(f))]
    hits = _vague_hits(" ".join(_text_of(s.get(f)) for f in QUINTET + READBACK))

    n_art = len(detail) if isinstance(detail, (list, tuple)) else (1 if _present(detail) else 0)
    over = n_art > MAX_ARTIFACTS

    ok = not (miss5 or bad or miss_rb or hits or over)
    return {
        "ok": ok,
        "判定": "完成" if ok else "草稿（缺件）",
        "缺五问": miss5,
        "明细/判据不合规": bad,
        "缺回读": miss_rb,
        "模糊词命中": hits,
        "明细条数": n_art,
        "超产出上限": over,
        "为什么": (("五问齐 · 明细逐项 · 回读齐 · 无模糊词 · 明细 <=%d" % MAX_ARTIFACTS) if ok
                   else "缺件/不合规/模糊词/超限 —— 逐条见上，缺什么补什么，不许用「应该可以」糊过去"),
    }


def check(steps) -> dict:
    """批量查（每步单独判；不做平均、不把部分合格说成合格）。"""
    items = list(steps) if isinstance(steps, (list, tuple)) else []
    rows = [check_step(x if isinstance(x, dict) else {}) for x in items]
    bad = [i for i, r in enumerate(rows) if not r["ok"]]
    return {
        "ok": bool(items) and not bad,
        "步数": len(items),
        "不合格步": bad,
        "逐条": rows,
        "为什么": ("全部合格" if items and not bad
                   else ("没有给 steps（0 步，判不过，fail-closed）" if not items
                         else "第 %s 步不合格" % bad)),
    }
