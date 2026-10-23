# -*- coding: utf-8 -*-
# gbt-capability: filesystem_write  ⬻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""出图交付门（figure_gate）—— 把两个开源 Skill 的铁律落成可核判据。

蒸馏来源（只借规矩，不搬代码）：
  · `wheresryan22/anatomy`（MIT）——「**The object is the explanation**」；
    它的 `kit/audit.mjs` 会**证明几何**（余隙 / 端点 / 松线 / 深度序），`verify.md` 是验收篇。
  · `AirsupHQ/machine-skill`（MIT）——「**real numbers or nothing**」与
    「§8 Look at it like a critic（**required**）」：至少四轮看图，**清单为空才停**。

三条设计取舍（诚实标注，不许假绿）：
  ① 能机检的才进判据（M）；只能人看的不假装能机检（H）；需产物才能判的标（A）。
  ② **numbers 必须声明出处**：交付前必须说清“屏幕上的数由哪个模型/脚本产出”，未声明 = 不可交付。
  ③ **四轮门**：至少 4 轮看图记录，且**最新一轮的问题清单必须为空**，否则 fail-closed。

不是替人看图：本件只管“**该看的看了没、该列的列了没、该声明的声明了没**”。
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

READ_OPS = ("checklist", "verdict", "rounds", "evidence")
WRITE_OPS = ("declare_numbers", "record_round", "record_evidence", "require_evidence")
MIN_ROUNDS = 4

# 两份 SKILL.md 里写死的“不算完成”清单（machine 「The bar」）—— 逐条标能不能机检
NOT_DONE = (
    {"id": "missing_part", "text": "机械师会期待的零件缺失",
     "grade": "H", "why": "需要对这台机器的领域知识：人看图断言，本件不假装能自己数零件"},
    {"id": "float_intersect", "text": "悬浮 / 穿模 / 可见接缝或缺口",
     "grade": "A", "why": "有几何数据时可机检（anatomy 的 audit.mjs 就是这件）；只有图时只能人看"},
    {"id": "one_grey", "text": "该是金属却像塑料，或全部同一种灰",
     "grade": "M", "why": "可数：场景里出现过的材质种数与各自占比，少于两种就报"},
    {"id": "typed_numbers", "text": "屏幕上有一个数是手打的而不是算出来的",
     "grade": "M", "why": "本件的 declare_numbers 就是这道门：没声明来源 = 不可交付"},
    {"id": "hollow_cut", "text": "剖面里是空壳而不是实心截面",
     "grade": "H", "why": "需要看剖图的截面是否封口；几何数据里无法区分“空壳”与“实心”的意图"},
    {"id": "ugly_first_frame", "text": "片子的第一帧不美",
     "grade": "H", "why": "美丑是人的判断；本件只能要求你把它看了并记下结论"},
)


def _store() -> Path:
    try:
        from ._paths import STORE_DIR
        base = Path(STORE_DIR)
    except Exception:                                       # noqa: BLE001
        base = Path(__file__).resolve().parent / "store"
    return base / "figure_gate"


def _state_path() -> Path:
    return _store() / "state.json"


def _now() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _load() -> dict:
    try:
        return json.loads(_state_path().read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}


def _save(state: dict) -> None:
    d = _store()
    d.mkdir(parents=True, exist_ok=True)
    _state_path().write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def checklist() -> dict:
    """“不算完成”清单 + 每条的可检度（M/A/H）。只读。"""
    counts = {"M": 0, "A": 0, "H": 0}
    for row in NOT_DONE:
        counts[row["grade"]] = counts.get(row["grade"], 0) + 1
    return {"ok": True, "op": "checklist", "items": list(NOT_DONE),
            "machine_checkable": counts["M"], "needs_artifact": counts["A"],
            "human_only": counts["H"], "min_rounds": MIN_ROUNDS,
            "doctrine": "能机检的进判据；只能人看的如实标 H，不假装能自动判美丑"}


def declare_numbers(source: str, artifact: str = "", note: str = "") -> dict:
    """声明“屏幕上的数由谁算出来”。空声明 = 拒收。"""
    src = str(source or "").strip()
    if not src:
        return {"ok": False, "op": "declare_numbers", "reason": "needs_source",
                "detail": "必须说清模型/脚本在哪（例：gbt_allinone/xxx.py 或 tools/yyy.py）"}
    st = _load()
    st["numbers"] = {"source": src, "artifact": str(artifact or ""),
                     "note": str(note or ""), "at": _now()}
    _save(st)
    return {"ok": True, "op": "declare_numbers", "source": src}


def record_round(viewed, issues=None, artifact: str = "") -> dict:
    """记一轮“像批评家一样看图”：看了哪几样、列了哪些问题。"""
    if isinstance(viewed, str):
        viewed = [viewed]
    viewed = [str(v) for v in (viewed or []) if str(v).strip()]
    issues = [str(x) for x in (issues or []) if str(x).strip()]
    if not viewed:
        return {"ok": False, "op": "record_round", "reason": "needs_viewed",
                "detail": "一轮必须说明看了哪几张（全身/剖面/爆炸/关节特写/静帧）"}
    st = _load()
    rounds = st.get("rounds") or []
    rounds.append({"n": len(rounds) + 1, "at": _now(), "viewed": viewed,
                   "issues": issues, "artifact": str(artifact or "")})
    st["rounds"] = rounds
    _save(st)
    return {"ok": True, "op": "record_round", "n": len(rounds),
            "open_issues": len(issues), "at": rounds[-1]["at"]}


def rounds(limit: int = 20) -> dict:
    """读回记录（只读）。"""
    st = _load()
    rs = st.get("rounds") or []
    return {"ok": True, "op": "rounds", "count": len(rs),
            "items": rs[-max(1, int(limit)):],
            "numbers": st.get("numbers") or {}}


def verdict() -> dict:
    """**fail-closed 交付判据**：清单未清空 / 轮次不足 / 数未声明 ⇒ 不可交付。"""
    st = _load()
    rs = st.get("rounds") or []
    nums = st.get("numbers") or {}
    reasons = []
    if not nums.get("source"):
        reasons.append("numbers_not_declared：没声明屏幕上的数由谁算出来")
    if len(rs) < MIN_ROUNDS:
        reasons.append("rounds_insufficient：%d/%d 轮" % (len(rs), MIN_ROUNDS))
    open_issues = list((rs[-1].get("issues") if rs else []) or [])
    if open_issues:
        reasons.append("open_issues：最新一轮还有 %d 条未清" % len(open_issues))
    # 机械证据：要求了就必须有、而且必须绿（fail-closed）
    ev = st.get("evidence") or {}
    for k in (st.get("required_evidence") or []):
        row = ev.get(k)
        if not row:
            reasons.append("evidence_missing：要求了 %s 证据但没记" % k)
        elif not row.get("passed"):
            reasons.append("evidence_failed：%s 未通过" % k)
    return {"ok": not reasons, "op": "verdict", "deliverable": not reasons,
            "rounds": len(rs), "min_rounds": MIN_ROUNDS,
            "open_issues": open_issues, "numbers": nums, "reasons": reasons,
            "human_still_required": [r["id"] for r in NOT_DONE if r["grade"] != "M"],
            "note": "本判据只管“该看的看了没、该声明的声明了没”；"
                    "标 H 的那几条**仍需人看**（本件不假装能自动判美丑）"}




# ============================================================================
# 机械化证据：把两份 Skill 里“能跑成退码”的那几条接进来
#
#   · anatomy：`build.mjs --audit` 必须打 `audit passed`（余隙/端点/松线/折叠/自重叠/深度序…）
#     · `lines.mjs` 必须打 `line ends: 0`（每条线都落在某个东西上）
#   · machine：出片扫描“**粉帧**”，任一帧发粉即**非零退出**；工况与公开值偏差 >20% ⇒ 改模型不改数字
#
#   本件不代替它们跑那些脚本（那需要装它们）；本件只管“**该验的验了没、结果是不是绿**”。
# ============================================================================

EVIDENCE_KINDS = ("audit", "lines", "pinkscan", "operating_point")


def require_evidence(kinds, note: str = "") -> dict:
    """声明这份交付**必须拿出哪几项机械证据**。传空则清空。"""
    if isinstance(kinds, str):
        kinds = [kinds]
    kinds = [str(k).strip().lower() for k in (kinds or []) if str(k).strip()]
    bad = [k for k in kinds if k not in EVIDENCE_KINDS]
    if bad:
        return {"ok": False, "op": "require_evidence", "reason": "unknown_kind",
                "detail": "不认识：%s；可选：%s" % (", ".join(bad), ", ".join(EVIDENCE_KINDS))}
    st = _load()
    st["required_evidence"] = kinds
    if note:
        st["required_evidence_note"] = str(note)
    _save(st)
    return {"ok": True, "op": "require_evidence", "required": kinds}


def record_evidence(kind: str, passed: bool, detail: str = "", command: str = "") -> dict:
    """记一条机械证据（跑了什么命令、结果是不是绿）。"""
    k = str(kind or "").strip().lower()
    if k not in EVIDENCE_KINDS:
        return {"ok": False, "op": "record_evidence", "reason": "unknown_kind",
                "detail": "可选：%s" % ", ".join(EVIDENCE_KINDS)}
    st = _load()
    ev = st.get("evidence") or {}
    ev[k] = {"passed": bool(passed), "detail": str(detail or "")[:400],
             "command": str(command or "")[:300], "at": _now()}
    st["evidence"] = ev
    _save(st)
    return {"ok": True, "op": "record_evidence", "kind": k, "passed": bool(passed)}


def evidence() -> dict:
    """读回证据与要求（只读）。"""
    st = _load()
    return {"ok": True, "op": "evidence", "kinds": list(EVIDENCE_KINDS),
            "required": st.get("required_evidence") or [],
            "recorded": st.get("evidence") or {}}


def run(op: str = "verdict", **kw) -> dict:
    """能力位统一入口。未知 op **fail-closed**。"""
    o = (op or "verdict").strip().lower()
    known = list(READ_OPS) + list(WRITE_OPS)
    if o == "checklist":
        return checklist()
    if o == "verdict":
        return verdict()
    if o == "rounds":
        return rounds(limit=int(kw.get("limit", 20)))
    if o == "declare_numbers":
        return declare_numbers(kw.get("source", ""), kw.get("artifact", ""), kw.get("note", ""))
    if o == "record_round":
        return record_round(kw.get("viewed"), kw.get("issues"), kw.get("artifact", ""))
    if o == "evidence":
        return evidence()
    if o == "record_evidence":
        return record_evidence(kw.get("kind", ""), kw.get("passed", False),
                               kw.get("detail", ""), kw.get("command", ""))
    if o == "require_evidence":
        return require_evidence(kw.get("kinds"), kw.get("note", ""))
    return {"ok": False, "reason": "unknown_op", "op": o, "known": known,
            "detail": "未知 op 只回错，不执行任何东西（fail-closed）"}
