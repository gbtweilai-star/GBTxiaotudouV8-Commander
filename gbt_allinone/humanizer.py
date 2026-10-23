# -*- coding: utf-8 -*-
"""humanizer -- 去 AI 味改写器（蒸馏自 skills.sh humanizer-zh：只蒸思想）。
**与判据同源**：直接加载 tools/codex-scripts/human-tone-check.py，改写前后用同一把尺。
2026-10-17 第二版：整短语最长优先 + 句级清理。
"""
from __future__ import annotations
import importlib.util, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_JUDGE = ROOT / "tools" / "codex-scripts" / "human-tone-check.py"
BS = chr(92)
COMMA = "，"
IDEO = "。"

CN_FIX = {
    "在当今快节奏下": "现在",
    "在这个日新月异的时代": "现在",
    "在这个日新月异": "现在",
    "值得一提的是": "",
    "不仅仅是": "不只是",
    "综上所述": "总的说",
    "全面提升": "改好",
    "打造闭环": "跑通",
    "赋能": "支持",
    "手握手": "一起",
}
EN_FIX = {
    "delve into": "look at", "delve": "dig into", "landscape": "field", "realm": "area",
    "tapestry": "mix", "testament to": "proof of", "navigate the complexities": "handle the tricky parts",
    "underscore": "show", "pivotal": "key", "embark on a journey": "start", "unlock the potential": "get more out of",
    "game-changer": "big change", "cutting-edge": "new", "seamless": "smooth", "robust": "solid",
    "leverage": "use", "foster": "grow", "holistic": "whole", "elevate": "lift",
}


def _judge():
    spec = importlib.util.spec_from_file_location("human_tone_judge", str(_JUDGE))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _sentence_cleanup(s: str) -> str:
    s = re.sub("[" + COMMA + "\u3001]{2,}", COMMA, s)
    s = re.sub("^[" + COMMA + "\u3001" + IDEO + BS + "s]+", "", s)
    s = s.replace(COMMA + IDEO, IDEO)
    s = re.sub(COMMA + "[" + BS + "s]*" + IDEO, IDEO, s)
    s = s.replace(COMMA + COMMA, COMMA)
    s = re.sub("[" + BS + "s]+" + COMMA, COMMA, s)
    s = re.sub(BS + "s{2,}", " ", s)
    return s.replace(" " + IDEO, IDEO).strip()


def rewrite_text(t: str):
    j = _judge()
    before = j.check(t)
    out = t
    fixes = []
    pairs = sorted(list(CN_FIX.items()) + list(EN_FIX.items()), key=lambda kv: -len(kv[0]))
    for k, v in pairs:
        if k in out:
            out = out.replace(k, v)
            fixes.append(("替换", k, v))
    for o in j.OPENERS:
        pat = r"(^|[.!?]" + BS + "s+)" + re.escape(o) + BS + "s*,?" + BS + "s*"
        new = re.sub(pat, lambda m: m.group(1), out)
        if new != out:
            out = new
            fixes.append(("删连接词", o, ""))
    out = _sentence_cleanup(out)
    after = j.check(out)
    return {"before_hits": before, "after_hits": after, "fixes": fixes, "text": out}


def run(payload: dict) -> dict:
    p = payload or {}
    op = p.get("op") or "rewrite"
    if op != "rewrite":
        return {"ok": False, "status": "user_error", "message": "未知 op：%s（本位只有 rewrite）" % op}
    if p.get("file"):
        t = Path(p["file"]).read_text(encoding="utf-8", errors="replace")
    else:
        t = p.get("text") or ""
    if not t.strip():
        return {"ok": False, "status": "user_error", "message": "缺少 text 或 file"}
    r = rewrite_text(t)
    out_path = None
    if p.get("out"):
        op_ = Path(p["out"])
        op_.parent.mkdir(parents=True, exist_ok=True)
        op_.write_text(r["text"], encoding="utf-8")
        out_path = str(op_)
    return {"ok": True, "before_hits": [list(x) for x in r["before_hits"]],
            "after_hits": [list(x) for x in r["after_hits"]], "fixes": [list(x) for x in r["fixes"]],
            "text": r["text"], "out": out_path, "clean": len(r["after_hits"]) == 0,
            "note": "词级替换 + 句级清理；句长与逗号类命中不能靠替换消掉，如实列在 after_hits"}
