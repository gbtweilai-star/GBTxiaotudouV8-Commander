# gbt-capability: coverage_auditor
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""触手覆盖审计器（coverage_auditor）· R-H196 只读骨架。

**"全方位无死角"不是口号，是一个可测的数**：覆盖率 = 已覆盖场景 / 已知场景。
**死角 = 既没有触手能处理，也没有触手能上报"我处理不了"** ——
报"处理不了"本身也是一种覆盖：死角不是"不会"，是"**不会还不说**"。

五条红线（做成机械闸）：
  ① 每个短板必须有对应触手；② 每个触手必须能报"我处理不了"；
  ③ 覆盖矩阵必须可测；④ 死角必须登记；⑤ 新增场景必须触发覆盖审计。

本模块只读：不写盘、不出网、不执行触手动作。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# 八根触手组 ↔ 八个短板（名字固定，顺序固定）
SHORT_BOARDS = (
    ("SAY_NOT_DO", "只会说不会做", "手（执行触手）"),
    ("NO_MEMORY", "没有记忆", "脑（记忆触手）"),
    ("NO_SELF_VIEW", "看不见自己", "眼（视觉触手）"),
    ("SINGLE_MODAL_EAR", "单模态（听）", "耳（听觉触手）"),
    ("SINGLE_MODAL_MOUTH", "单模态（说）", "口（表达触手）"),
    ("NO_BOUNDARY", "没有边界", "门（门禁触手）"),
    ("NO_COLLABORATE", "不会协作", "网（协作触手）"),
    ("NO_VERIFY", "不会验证", "镜（审计触手）"),
)
BOARD_KEYS = tuple(k for k, _cn, _g in SHORT_BOARDS)
BOARD_CN = {k: cn for k, cn, _g in SHORT_BOARDS}
BOARD_GROUP = {k: g for k, _cn, g in SHORT_BOARDS}

# 盘上取证快照（R-H196 实测；**带 as_of 与出处**，不冒充实时）
FORENSIC_SNAPSHOT = {
    "as_of": "2026-09-20T12:0x",
    "source": "docs/触手覆盖矩阵.md §三（机械取证：文件名 + 关键字）",
    "expected_modules": {"手（执行触手）": 9, "脑（记忆触手）": 6, "眼（视觉触手）": 5,
                         "耳（听觉触手）": 2, "口（表达触手）": 4, "门（门禁触手）": 4,
                         "网（协作触手）": 3, "镜（审计触手）": 6},
    "reportable_modules": {"手（执行触手）": 4, "脑（记忆触手）": 3, "眼（视觉触手）": 0,
                           "耳（听觉触手）": 1, "口（表达触手）": 4, "门（门禁触手）": 3,
                           "网（协作触手）": 2, "镜（审计触手）": 4},
}

RED_LINES = (
    "每个短板必须有对应触手——没有对应触手的短板，就是结构性死角",
    "每个触手必须能报『我处理不了』——报不了，就是静默失败",
    "覆盖矩阵必须可测——不许说『全覆盖』，要给覆盖率读数",
    "死角必须登记——已知死角列入台账，不许假装不存在",
    "新增场景必须触发覆盖审计——新任务类型出现 ⇒ 检查有没有触手能接",
)

# ── R-H199 · 原生能力优先律（唯一公理：模型可换，原生栈不可换）──────────
NATIVE_FIRST_LINES = (
    "默认走原生——任何任务，路由第一站是原生能力，不是外部模型",
    "模型可换，栈不变——切换模型时，触手/记忆/门禁/审计一条不动",
    "外部模型只补认知——不许直接执行、不许绕过路由、不许写 store",
    "原生能力必须持续打磨——短板必须登记、必须进化",
    "短板跟着原生能力走，不跟着模型走——换模型不改变短板台账",
)

EXTERNAL_MODEL_FORBIDDEN = ("execute", "write_store", "bypass_route", "deploy",
                           "publish", "grant_auth")

# 短板台账的宿主字段 = **原生面**（不许出现 model 字段：红线⑤）
LEDGER_FIELDS = ("gap_id", "native_surface", "status", "bound_by", "note")

# 死角台账（R-H196 立 · R-H202 核）：**挂原生面**，且不许带 model 字段
GAPS = (
    {"gap_id": "G1", "native_surface": "眼（视觉触手）", "status": "closed",
     "bound_by": "R-H202", "note": "**撤销**：实测 4/5 视觉模块有结构化否决形状 ⇒ 原判是**判据没覆盖**，不是死角"},
    {"gap_id": "G2", "native_surface": "手/脑/门/网/镜", "status": "open",
     "bound_by": "R-H196", "note": "部分模块只抛异常、不回结构化否决（逐模块补）"},
    {"gap_id": "G3", "native_surface": "眼（capture_environment）", "status": "closed",
     "bound_by": "R-H203", "note": "**已收口**：capacity()/status() 补统一失败出口（ok + reason + next）+ "
                                   "assert_not_silent 守卫；实测非交互桌面下 ok=False · reason=non_interactive_desktop · next 非空"},
)


def route(task: str = "", cognition_only: bool = False) -> dict:
    """红线①：**路由第一站永远是原生能力**；外部模型只是参谋。"""
    return {"ok": True, "readonly": True,
            "task": str(task or ""),
            "first_stop": "native",
            "route": "external_cognition" if cognition_only else "native",
            "external_model_role": "advisor",
            "note": "外部模型补认知（推理/生成/判断），不补执行",
            "law": list(NATIVE_FIRST_LINES[:2])}


def external_model_may(action: str) -> dict:
    """红线③：**外部模型只补认知** —— 执行类动作一律拒。"""
    act = str(action or "").strip().lower()
    if act in EXTERNAL_MODEL_FORBIDDEN:
        return {"ok": False, "denied": True, "rule": "external_model_cannot_execute",
                "action": act,
                "why": "外部模型不许执行/写库/绕路由：它只是参谋（原生能力才是执行面）"}
    return {"ok": True, "readonly": True, "action": act, "role": "advisor"}


def assert_stack_unchanged(before: dict, after: dict) -> dict:
    """红线②：**模型可换，栈不变** —— 触手/记忆/门禁/审计的指纹逐项相同。"""
    b, a = dict(before or {}), dict(after or {})
    diff = [k for k in sorted(set(b) | set(a)) if b.get(k) != a.get(k)]
    return {"ok": not diff, "readonly": True, "drifted": diff,
            "why": ("栈指纹不变：切模型不许带走手/脑/门/镜" if not diff else
                    "切模型把原生栈带偏了：%s" % ", ".join(diff))}


def gaps_ledger(rows: Optional[List[dict]] = None) -> dict:
    """红线④⑤：短板台账 —— **挂原生面**，且**不许出现 model 字段**。

    🔴 2026-09-22 第 45 轮修（错报治理 · **台账定义了却从不被读**）：
    原来这行是 `rows = [dict(r) for r in (rows or []) ...]` ——
    传 `None` 时用的是**空列表**，**永远不读本文件里那份 `GAPS`**。
    实测后果：直接调 `gaps_ledger()`（"给我看短板台账"的自然调用）会返回
    **`count=0`** —— 一个**假的"没有死角"**；而盘上明明摆着 G1..Gn（带 R-H196/R-H202/R-H203 的
    出处与 closed/open 状态）。这正是本轮普查（只写不读，全工作区 2655 文件）抓出来的那类：
    **收集了却从不交付**。⇒ 不传参时**默认就是那份台账**；显式传（含显式传空）仍按传的来。
    """
    rows = [dict(r) for r in (GAPS if rows is None else rows) if isinstance(r, dict)]
    bad = []
    for i, r in enumerate(rows):
        if "model" in r:
            bad.append({"index": i, "rule": "gap_bound_to_model",
                        "why": "短板跟着原生能力走，不跟着模型走：台账不许带 model 字段"})
        for f in ("gap_id", "native_surface"):
            if not str(r.get(f) or "").strip():
                bad.append({"index": i, "rule": "missing_field", "why": "缺字段 " + f})
    return {"ok": not bad, "readonly": True, "count": len(rows),
            # 🔴 第 45 轮补：**把台账本身交出去**。原来只回 count + fields + problems，
            #    于是"给我看短板台账"拿不到任何一条短板 —— 计数有了、内容还是没有。
            #    （这正是本轮那条病的完整形状：**收集了却从不交付**。）
            "rows": rows,
            "fields": list(LEDGER_FIELDS), "problems": bad,
            "bind_to": "native_surface（原生面）",
            "rule": "短板台账挂在原生能力上；换模型不改变台账"}


@dataclass
class CoverageEntry:
    """一个短板的覆盖情况。"""

    short_board: str
    tentacles: List[str] = field(default_factory=list)
    gaps: List[str] = field(default_factory=list)
    can_report_incapable: bool = False

    @property
    def covered(self) -> bool:
        """**有触手 + 能报做不了** 才算覆盖（红线②）。"""
        return bool(self.tentacles) and bool(self.can_report_incapable)


class CoverageAuditor:
    """覆盖审计器：注册 → 审计（**只给读数，不给形容词**）。"""

    def __init__(self) -> None:
        self.entries: Dict[str, CoverageEntry] = {}
        self.scenarios: Dict[str, Optional[str]] = {}      # 场景 → 能接的触手（None = 没触手）

    def register(self, entry: CoverageEntry) -> dict:
        if entry.short_board not in BOARD_CN:
            raise ValueError("未知短板 %r（可用：%s）" % (entry.short_board, "/".join(BOARD_KEYS)))
        if not entry.tentacles:
            entry.gaps = list(dict.fromkeys(list(entry.gaps) + ["没有对应触手（结构性死角）"]))
        if not entry.can_report_incapable:
            entry.gaps = list(dict.fromkeys(
                list(entry.gaps) + ["不能上报『我处理不了』（静默失败）"]))
        self.entries[entry.short_board] = entry
        return {"ok": True, "readonly": True, "short_board": entry.short_board,
                "covered": entry.covered, "gaps": entry.gaps}

    def register_scenario(self, name: str, tentacle: Optional[str] = None,
                          gap_note: str = "") -> dict:
        """红线⑤：**新增场景必须触发覆盖审计** —— 没触手能接就必须先登记为死角。"""
        key = str(name or "").strip()
        if not key:
            raise ValueError("场景名不能为空")
        if not tentacle and not str(gap_note or "").strip():
            return {"ok": False, "denied": True, "rule": "unregistered_gap",
                    "why": "新场景没有触手能接 ⇒ 必须先登记为死角（不许假装不存在）"}
        self.scenarios[key] = tentacle or None
        return {"ok": True, "readonly": True, "scenario": key,
                "tentacle": tentacle or None, "gap": (not tentacle) or None}

    def audit(self, claim_full: bool = False) -> dict:
        """只给读数：覆盖率 / 计数 / 死角台账；宣称全覆盖必须有登记的死角才允许。"""
        rows = list(self.entries.values())
        total = len(BOARD_KEYS)
        covered = sum(1 for e in rows if e.covered)
        with_tentacle = sum(1 for e in rows if e.tentacles)
        reportable = sum(1 for e in rows if e.can_report_incapable)
        gaps = {e.short_board: list(e.gaps) for e in rows if e.gaps}
        gaps_total = sum(len(v) for v in gaps.values())
        unregistered = [k for k, v in self.scenarios.items() if v is None]
        out = {
            "ok": True, "readonly": True,
            "total_short_boards": total,
            "registered": len(rows),
            "covered": covered,
            "coverage_rate": "%d/%d" % (covered, total),
            "with_tentacle": with_tentacle,
            "reportable": reportable,
            "gaps_total": gaps_total,
            "gaps": gaps,
            "unregistered_gaps": unregistered,
            "forensic_snapshot": FORENSIC_SNAPSHOT,
            "note": "只给读数，不给形容词：报『处理不了』也算覆盖",
        }
        if claim_full and not gaps and not unregistered:
            return {"ok": False, "denied": True, "rule": "claimed_full_violation",
                    "why": "宣称『全覆盖』却没有任何登记死角 ⇒ 拒（死角永远会有，关键是有没有登记）",
                    "reading": out}
        return out


_DEFAULT = CoverageAuditor()


def run(op="matrix", **params) -> dict:
    """能力入口（只读骨架）：matrix（八组表）/ redlines / snapshot。不写盘、不出网、不执行。"""
    op = str(op or "matrix")
    if op == "matrix":
        snap = FORENSIC_SNAPSHOT
        return {"ok": True, "readonly": True,
                "matrix": [{"key": k, "short_board": BOARD_CN[k], "group": BOARD_GROUP[k],
                            "expected_modules": snap["expected_modules"][BOARD_GROUP[k]],
                            "reportable_modules": snap["reportable_modules"][BOARD_GROUP[k]]}
                           for k in BOARD_KEYS],
                "coverage_by_group": "8/8 已有（无结构性死角）",
                "reportable_modules": "21/39（53.8%）",
                "known_gaps": ["G1 视觉面（眼）0/5 无显式上报形状（待核）",
                               "G2 手/脑/门/网/镜 的上报未满"],
                "as_of": snap["as_of"], "source": snap["source"]}
    if op == "redlines":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES),
                "short_boards": [{"key": k, "cn": BOARD_CN[k], "group": BOARD_GROUP[k]}
                                 for k in BOARD_KEYS]}
    if op == "snapshot":
        return {"ok": True, "readonly": True, **FORENSIC_SNAPSHOT}
    raise ValueError("未知 op %r（可用：matrix/redlines/snapshot）" % (op,))


HONEST_BOUNDARY = (
    "覆盖审计器只保证『每个已知短板有对应触手或已登记死角』；"
    "它保证不了『死角不存在』——死角永远会有，关键是有没有登记。"
    "口径边界：盘上实现按**文件名与关键字**取读数，不是逐模块读语义。"
)
