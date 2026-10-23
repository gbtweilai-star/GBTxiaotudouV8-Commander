# gbt-capability: observer_anchor
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""观察者锚点律（observer_anchor）· R-H703 只读骨架。

机器可以守基线、守边界、守覆盖，但机器**不能证明自己没漏**。
证明需要站在外面，而机器永远在里面 —— 所以递归的终点只能是人。

三公理：观察者与被观察者分离 · 观察者本身也要被观察 · 递归必须有终止点。
五条红线（机械闸）：
  ① 同一方不许既扫又报  ② 审计器必须被审  ③ 递归深度封顶
  ④ 终止点只能由人设    ⑤ 关键节点人在场

本模块只读：不写盘、不出网、不执行任何动作。它只**读数与判定**。
它自己也不免检 —— 它被 `test_observer_anchor.py` 审，那条用例又被独立复核审。
"""
from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

AXIOMS = (
    {"no": 1, "key": "separation", "name": "观察者与被观察者分离",
     "rule": "同一方不许既扫又报。自证不是证据。"},
    {"no": 2, "key": "self_audit", "name": "观察者本身也要被观察",
     "rule": "审计器也要被审；没有哪个观察者天生免疫。"},
    {"no": 3, "key": "termination", "name": "递归必须有终止点",
     "rule": "观察的观察的观察……必须停。停在**人**身上。"},
)
AXIOM_KEYS = tuple(a["key"] for a in AXIOMS)

SHORT_BOARDS = (
    {"key": "mixed_observer", "short": "观察者混同", "fix": "强制换 checker"},
    {"key": "observer_blindspot", "short": "观察者自身死角", "fix": "审计器也要被审"},
    {"key": "endless_recursion", "short": "递归无终点", "fix": "递归深度封顶"},
    {"key": "machine_terminal", "short": "终止点被机器自称", "fix": "终止点只能由人设"},
    {"key": "human_unrepeatable", "short": "人的判断不可复现", "fix": "拍板留痕"},
    {"key": "human_absent", "short": "人的缺席", "fix": "关键节点强制人在场"},
)
BOARD_KEYS = tuple(b["key"] for b in SHORT_BOARDS)

RED_LINES = (
    {"no": 1, "key": "no_self_report", "name": "同一方不许既扫又报",
     "rule": "观察者与被观察者必须分离"},
    {"no": 2, "key": "auditor_must_be_audited", "name": "审计器必须被审",
     "rule": "没有免检的观察者"},
    {"no": 3, "key": "recursion_must_be_capped", "name": "递归深度封顶",
     "rule": "递归必须有硬上限"},
    {"no": 4, "key": "terminal_is_human_only", "name": "终止点只能由人设",
     "rule": "机器不许自称『这就是终点』"},
    {"no": 5, "key": "human_present_at_key_nodes", "name": "关键节点人在场",
     "rule": "不可逆动作必须由人拍板"},
)
RED_KEYS = tuple(r["key"] for r in RED_LINES)

CORE_LAW = (
    "系统最终要靠一个「不会被系统自己改写」的锚点，这个锚点只能是人。"
)

# ── 红线① 同一方不许既扫又报 ────────────────────────────────
def check_separation(observer: str, checker: str, *, observed: str = "") -> dict:
    """观察者与复核者必须是**两方**。同一方既扫又报 ⇒ 拒绝。"""
    obs = str(observer or "").strip().lower()
    chk = str(checker or "").strip().lower()
    if not obs or not chk:
        return {"ok": False, "denied": True, "red": "no_self_report",
                "why": "观察者与复核者都必须署名 —— 匿名不算分离"}
    if obs == chk:
        return {"ok": False, "denied": True, "red": "no_self_report",
                "observer": obs, "checker": chk,
                "why": f"『{obs}』既扫又报 ⇒ 单方证据，不是证据",
                "fix": "换一个 checker（强制换）"}
    return {"ok": True, "readonly": True, "red": "no_self_report",
            "observer": obs, "checker": chk, "observed": str(observed or ""),
            "why": "观察者与复核者分离"}


# ── 红线② 审计器必须被审 ────────────────────────────────────
_AUDITOR_HINTS = ("audit", "check", "scan", "verify", "inspect", "guard")
_SCAN_DIRS = ("gbt_allinone", "holo_pet")
_SKIP_PARTS = {".pylibs", "node_modules", "store", "__pycache__", ".git", "tests"}


def _sources():
    for base in _SCAN_DIRS:
        root = _ROOT / base
        if not root.is_dir():
            continue
        for p in root.rglob("*.py"):
            if any(s in p.parts for s in _SKIP_PARTS):
                continue
            yield p


def auditors() -> dict:
    """扫出仓里的审计器模块，逐个报『它自己被谁审』（只读）。

    判定口径与 `caps_called_audit` 同源：**在别的模块里被引用**才算被审。
    找不到独立引用方 ⇒ 报 orphan（免检观察者 = 死角）。
    """
    cands = {}
    for p in _sources():
        name = p.stem
        if any(h in name.lower() for h in _AUDITOR_HINTS):
            try:
                cands[p.relative_to(_ROOT).as_posix()] = p.read_text(
                    encoding="utf-8", errors="replace")
            except OSError:
                continue
    rows, orphans = [], []
    for rel, _text in sorted(cands.items()):
        stem = Path(rel).stem
        callers = []
        for other in _sources():
            if other.relative_to(_ROOT).as_posix() == rel:
                continue
            try:
                if stem in other.read_text(encoding="utf-8", errors="replace"):
                    callers.append(other.relative_to(_ROOT).as_posix())
            except OSError:
                continue
        row = {"auditor": rel, "audited_by": sorted(callers)[:6], "count": len(callers)}
        rows.append(row)
        if not callers:
            orphans.append(rel)
    return {"ok": True, "readonly": True, "red": "auditor_must_be_audited",
            "auditors": rows, "total": len(rows), "orphans": orphans,
            "orphan_count": len(orphans),
            "note": "免检的观察者 = 死角；orphan 必须登记或被接上独立复核方"}


# ── 红线③ 递归深度封顶 ──────────────────────────────────────
_CAP_PAT = re.compile(r"^[A-Z_]*MAX[A-Z_]*DEPTH[A-Z_]*\s*=\s*(\d+)|"
                      r"\bmax_depth\s*[:=]\s*(\d+)|"
                      r"\bcontrol_depth\s*[:=]\s*(\d+)", re.M)


def depth_caps() -> dict:
    """扫出源码里所有递归/嵌套深度封顶（只读）。报得出才算封顶。"""
    caps = []
    for p in _sources():
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in _CAP_PAT.finditer(text):
            val = next((g for g in m.groups() if g), None)
            if val is None:
                continue
            line_no = text[:m.start()].count("\n") + 1
            caps.append({"file": p.relative_to(_ROOT).as_posix(),
                         "line": line_no, "cap": int(val)})
    return {"ok": True, "readonly": True, "red": "recursion_must_be_capped",
            "caps": caps, "total": len(caps),
            "note": "有封顶才叫封顶；没有硬上限的递归 = 无终点"}


# ── 红线④ 终止点只能由人设 ──────────────────────────────────
def terminals() -> dict:
    """报出『终止点由谁设』：机器自称的终止点一律不算（只读）。"""
    return {"ok": True, "readonly": True, "red": "terminal_is_human_only",
            "machine_may_declare": False,
            "human_only": True,
            "law": CORE_LAW,
            "why": ("机器不能证明自己没漏：证明需要站在外面，而机器永远在里面。"
                    "所以『到此为止、已经没漏了』这句话只能由人说。"),
            "machine_may_declare_list": [],
            "note": "机器可以报『我查了哪些、没查哪些』，不许报『已经没漏了』"}


# ── 红线⑤ 关键节点人在场 ────────────────────────────────────
def presence() -> dict:
    """报出不可逆动作当前是否强制人拍板（只读取证）。"""
    from ..security import policy as _pol
    trusted = bool(_pol.is_trusted())
    return {"ok": True, "readonly": True, "red": "human_present_at_key_nodes",
            "trusted_owner_session_now": trusted,
            "known_gap": ("可信主人会话下 `policy.authorize()` 直接放行受限动作"
                          "（`if not decision.restricted or is_trusted(): return ok=True`）"
                          "—— 不可逆动作在主人会话里不经人拍板。"),
            "untrusted_path": "未受信路径消耗一次性人工授权（auth_gate）",
            "note": "这是**已知缺口**，照实登记；不是本模块能自行补上的 —— 要人拍板"}


# ── 总闸 ────────────────────────────────────────────────────
def check(*, observer: str = "", checker: str = "", observed: str = "") -> dict:
    """五条红线的机械闸（能机械判的判，判不了的如实说判不了）。"""
    verdicts = {}
    verdicts["no_self_report"] = check_separation(observer, checker, observed=observed)
    for key in ("auditor_must_be_audited", "recursion_must_be_capped",
                "terminal_is_human_only", "human_present_at_key_nodes"):
        verdicts[key] = {"ok": True, "readonly": True, "deferred_to_readout": key,
                         "why": "这条要看全仓读数，不由单次调用判定（用对应 op 取读数）"}
    blocked = [k for k, v in verdicts.items() if v.get("denied")]
    return {"ok": not blocked, "readonly": True, "denied": bool(blocked),
            "blocked": blocked, "verdicts": verdicts,
            "note": ("五条红线里只有『同一方不许既扫又报』能单次机械判定；"
                     "其余四条是**全仓读数**，靠对应 op 取证，不假装一次调用就能判完")}


def run(op: str = "axioms", **params) -> dict:
    """能力入口：axioms / boards / red_lines / check / auditors / depth_caps / terminals / presence。"""
    o = str(op or "axioms")
    if o == "axioms":
        return {"ok": True, "readonly": True, "axioms": [dict(a) for a in AXIOMS],
                "core_law": CORE_LAW}
    if o == "boards":
        return {"ok": True, "readonly": True,
                "short_boards": [dict(b) for b in SHORT_BOARDS]}
    if o == "red_lines":
        return {"ok": True, "readonly": True,
                "red_lines": [dict(r) for r in RED_LINES],
                "core_law": CORE_LAW}
    if o == "check":
        return check(observer=params.get("observer", ""),
                     checker=params.get("checker", ""),
                     observed=params.get("observed", ""))
    if o == "auditors":
        return auditors()
    if o == "depth_caps":
        return depth_caps()
    if o == "terminals":
        return terminals()
    if o == "presence":
        return presence()
    raise ValueError("未知 op %r（可用：axioms/boards/red_lines/check/auditors/"
                     "depth_caps/terminals/presence）" % (o,))


HONEST_BOUNDARY = (
    "本律能保证的是：形式分离、封顶存在、终止点被登记为人。"
    "它保证不了：复核者实质上是否独立、人拍板是否明智、封顶数值是否合适。"
    "——机器不能证明自己没漏，所以递归的终点只能是人。"
)