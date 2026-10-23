# -*- coding: utf-8 -*-
"""万能插 · 协作层加装：**Stigmergy**（共识主动性 / 信息素场地）。

与 `collab_gateway` **并排、不替代**：

  · `collab_gateway` = **直连通道**：会话 / 对等方 / 提案收件箱 —— 解决「我知道要找谁」；
  · `stigmergy`     = **间接通道**：把痕迹留在环境里，别人**按痕迹**行动 —— 解决
    「找不清谁、或好多方同时在场」时也能协同（蚂蚁不商量，靠场地）。

四原语（只读优先，只有 DEPOSIT 会写，且**只追加**）：
  DEPOSIT 留信息素 · READ 读场地（含挥发计算）· DECAY 挥发**读数**（**不删行**）· FORAGE 按浓度选路（只给读数）

五条红线（全做成机械闸）：
  ① **无源不许留**（每次留痕必须写明 `source`）
  ② **种类白名单**（不许乱塞，每条有半衰期）
  ③ **只追加、不删不覆盖**（挥发是**读数**，账本可回放）—— 静态核自己的源码
  ④ **不留明文密钥**（粗筛 `sk-` / `ghp_` / `AKIA` 等）
  ⑤ **只给读数、不自动执行**（FORAGE 只排序，不许替谁动手）
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .._paths import STORE_DIR
from ..safe_io import locked_append_text

CAP_KIND = "stigmergy"
DOMAIN = "collab"
CAP_TYPE = "internal"
TRACE_SOURCE_KIND = "stigmergy"

PRIMITIVES = (
    {"name": "DEPOSIT", "作用": "留一条信息素（**只追加**，必带 source）",
     "判据": "无源不许留 · 种类在白名单 · 强度 0<·<=1 · 不留明文密钥"},
    {"name": "READ", "作用": "读场地：按 subject 汇总**有效强度**（= 强度 × 半衰期衰减）",
     "判据": "只读；没留过就如实返回空，**不编**"},
    {"name": "DECAY", "作用": "挥发**读数**：给出还活着 / 已淡出的条数",
     "判据": "**不删任何行**（挥发是算术，不是删除）"},
    {"name": "FORAGE", "作用": "按有效强度排序，给出「下一步更值得去哪」的**读数**",
     "判据": "只排序、**不自动执行**；无人留痕 ⇒ 明确说「场地是空的」"},
)

RED_LINES = (
    "无源不许留：每次留痕必须写明 source（谁留的）",
    "种类白名单：kind 必须在 KINDS 里，且每条都有半衰期",
    "只追加：账本**不许删行 / 不许覆写**（挥发是读数）",
    "不留明文密钥：正文粗筛 sk- / ghp_ / AKIA 等",
    "只给读数：FORAGE / READ 不许触发任何外部动作",
)

# 白名单：借「真实蚂蚁的四类信息素」当上限，避免乱塞
KINDS = {
    "task": 6.0,      # 任务信息素：半衰期 6 小时
    "path": 2.0,      # 路径信息素：半衰期 2 小时
    "danger": 12.0,   # 危险信息素：半衰期 12 小时（留得久一点）
    "resource": 8.0,  # 资源信息素：半衰期 8 小时
}

MAX_STRENGTH = 1.0
MIN_STRENGTH = 0.0
MIN_EFFECTIVE = 0.05      # 有效强度低于它 ⇒ 视为「已淡出」
MAX_NOTE_LEN = 500
MAX_SUBJECT_LEN = 120

_SECRET_RE = re.compile(r"(sk-[A-Za-z0-9]{6,}|ghp_[A-Za-z0-9]{6,}|AKIA[0-9A-Z]{8,})")


def _store_dir(root: Optional[str] = None) -> Path:
    """信息素场地：放在**现有协作区**下（`store/collab/stigmergy/`）。"""
    if root:
        return Path(root)
    return Path(STORE_DIR) / "collab" / "stigmergy"


def ledger_path(root: Optional[str] = None) -> Path:
    return _store_dir(root) / "pheromones.jsonl"


def _now(now: Any = None) -> float:
    if now is None:
        return time.time()
    try:
        value = float(now)
    except (TypeError, ValueError):
        return time.time()
    return value


def _decay_factor(kind: str, age_hours: float) -> float:
    half = float(KINDS.get(kind) or 0.0)
    if half <= 0:
        return 0.0
    return 0.5 ** (max(0.0, age_hours) / half)


def _load_rows(root: Optional[str] = None) -> List[dict]:
    path = ledger_path(root)
    if not path.exists():
        return []
    rows: List[dict] = []
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            # 坏行**不许静默**：留一条可核的标记（但仍不删）
            rows.append({"kind": "?", "subject": "?", "strength": 0.0,
                         "source": "?", "at": 0.0, "_broken": True})
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def deposit(kind: str, subject: str, note: str = "", strength: float = 0.5,
            source: str = "", now: Any = None, root: Optional[str] = None) -> dict:
    """DEPOSIT：留一条信息素（**只追加一行**）。五条红线在这条上先过一遍。"""
    kind = str(kind or "").strip()
    subject = str(subject or "").strip()
    note = str(note or "").strip()
    source = str(source or "").strip()
    if not source:
        return {"ok": False, "denied": True, "rule": "deposit_without_source",
                "why": "**无源不许留**：留痕必须写明 source（谁留的）—— 否则场地会变谣言"}
    if kind not in KINDS:
        return {"ok": False, "denied": True, "rule": "deposit_kind_not_allowed",
                "kind": kind, "allowed": sorted(KINDS),
                "why": "种类不在白名单 ⇒ 不许留（白名单每条都有半衰期）"}
    if not subject:
        return {"ok": False, "denied": True, "rule": "deposit_subject_missing",
                "why": "必须写明 subject（**留在哪儿**）"}
    if len(subject) > MAX_SUBJECT_LEN:
        return {"ok": False, "denied": True, "rule": "deposit_subject_too_long",
                "len": len(subject), "max": MAX_SUBJECT_LEN,
                "why": "subject 太长 ⇒ 场地会被噪声塞满"}
    try:
        strength = float(strength)
    except (TypeError, ValueError):
        return {"ok": False, "denied": True, "rule": "deposit_strength_not_number",
                "why": "强度必须是数字"}
    if not (MIN_STRENGTH < strength <= MAX_STRENGTH):
        return {"ok": False, "denied": True, "rule": "deposit_strength_out_of_range",
                "strength": strength, "range": [MIN_STRENGTH, MAX_STRENGTH],
                "why": "强度必须 0 < 强度 <= 1（0 等于没留，>1 会把场地压死）"}
    if len(note) > MAX_NOTE_LEN:
        return {"ok": False, "denied": True, "rule": "deposit_note_too_long",
                "len": len(note), "max": MAX_NOTE_LEN,
                "why": "正文太长 ⇒ 只留摘要（**引用不复制**）"}
    hit = _SECRET_RE.search(note)
    if hit:
        return {"ok": False, "denied": True, "rule": "plaintext_key_in_pheromone",
                "masked": hit.group(0)[:4] + "****",
                "why": "**正文里不许有明文密钥**（粗筛；命中即拒，不写盘）"}
    row = {"kind": kind, "subject": subject, "strength": strength,
           "note": note, "source": source, "at": _now(now)}
    path = ledger_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    locked_append_text(path, json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "readonly": False, "primitive": "DEPOSIT",
            "row": row, "ledger": str(path),
            "note_zh": "**只追加一行**（挥发靠读数，不删行）"}


def read(subject: Optional[str] = None, kind: Optional[str] = None,
         now: Any = None, min_effective: float = MIN_EFFECTIVE,
         root: Optional[str] = None) -> dict:
    """READ：读场地（**只读**）。有效强度 = 强度 × 0.5^(龄期 / 半衰期)。"""
    t = _now(now)
    rows = _load_rows(root)
    subject = str(subject).strip() if subject is not None else None
    kind = str(kind).strip() if kind is not None else None
    groups: Dict[str, dict] = {}
    faded = 0
    for row in rows:
        if subject and str(row.get("subject")) != subject:
            continue
        if kind and str(row.get("kind")) != kind:
            continue
        rk = str(row.get("kind") or "")
        age_h = max(0.0, (t - float(row.get("at") or 0.0)) / 3600.0)
        eff = float(row.get("strength") or 0.0) * _decay_factor(rk, age_h)
        if eff < float(min_effective):
            faded += 1
            continue
        key = str(row.get("subject") or "")
        g = groups.setdefault(key, {"subject": key, "effective": 0.0, "count": 0,
                                    "kinds": set(), "last_at": 0.0, "sources": set()})
        g["effective"] += eff
        g["count"] += 1
        g["kinds"].add(rk)
        g["last_at"] = max(g["last_at"], float(row.get("at") or 0.0))
        g["sources"].add(str(row.get("source") or ""))
    out = []
    for g in groups.values():
        out.append({"subject": g["subject"], "effective": round(g["effective"], 4),
                    "count": g["count"], "kinds": sorted(g["kinds"]),
                    "last_at": g["last_at"], "sources": sorted(g["sources"])})
    out.sort(key=lambda x: (-x["effective"], x["subject"]))
    return {"ok": True, "readonly": True, "primitive": "READ",
            "subjects": out, "count": len(out), "faded_below": faded,
            "min_effective": float(min_effective),
            "note_zh": "场地是空的也照实说（**不编**）"}


def decay(now: Any = None, root: Optional[str] = None) -> dict:
    """DECAY：挥发**读数**（**不删任何行**）。"""
    t = _now(now)
    rows = _load_rows(root)
    alive = 0
    faded = 0
    for row in rows:
        rk = str(row.get("kind") or "")
        age_h = max(0.0, (t - float(row.get("at") or 0.0)) / 3600.0)
        eff = float(row.get("strength") or 0.0) * _decay_factor(rk, age_h)
        if eff >= MIN_EFFECTIVE:
            alive += 1
        else:
            faded += 1
    return {"ok": True, "readonly": True, "primitive": "DECAY",
            "rows": len(rows), "alive": alive, "faded": faded,
            "deleted": 0,
            "note_zh": "**挥发是读数，不是删除**：账本可回放，行只增不减"}


def forage(subject_prefix: Optional[str] = None, top: int = 5,
            now: Any = None, root: Optional[str] = None) -> dict:
    """FORAGE：按有效强度排序，给出「下一步更值得去哪」的**读数**（不执行）。"""
    data = read(now=now, root=root)
    subjects = list(data["subjects"])
    if subject_prefix:
        pfx = str(subject_prefix)
        subjects = [s for s in subjects if str(s["subject"]).startswith(pfx)]
    try:
        top = max(1, int(top))
    except (TypeError, ValueError):
        top = 5
    picked = subjects[:top]
    if not picked:
        return {"ok": True, "readonly": True, "primitive": "FORAGE",
                "suggestions": [], "reason": "场地是空的（**没人留过痕**）⇒ **不编方向**"}
    return {"ok": True, "readonly": True, "primitive": "FORAGE",
            "suggestions": [{"subject": s["subject"], "effective": s["effective"],
                             "why": "浓度最高（%s）" % "、".join(s["kinds"])} for s in picked],
            "note_zh": "**只排序、不自动执行**；决定权仍在调用方"}


def trail(limit: int = 20, root: Optional[str] = None) -> dict:
    """TRAIL：原始账本尾部（只读）。"""
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 20
    rows = _load_rows(root)
    return {"ok": True, "readonly": True, "rows": len(rows),
            "tail": rows[-limit:], "ledger": str(ledger_path(root))}


def collab_bridge() -> dict:
    """与 `collab_gateway` 的关系（**只读**；不改协作状态）。"""
    return {"ok": True, "readonly": True,
            "direct_channel": "collab_gateway（会话 / 对等方 / 提案收件箱）——**我知道找谁**",
            "indirect_channel": "stigmergy（信息素场地）——**我只知道场地**",
            "relationship": "**并排、不替代**：直连解决点对点；间接解决「找不清谁 / 多方同时在场」",
            "shared_store": str(_store_dir()),
            "no_side_effect": "本函数**不读写** collab 的会话/对等方/收件箱"}


def check_kinds() -> dict:
    """闸A：种类白名单必须每种都有**正半衰期**（否则那种信息素永不淡出）。"""
    if not KINDS:
        return {"ok": False, "denied": True, "rule": "kinds_empty",
                "why": "白名单为空 ⇒ **没测到**（空样本不按绿）"}
    bad = sorted(k for k, v in KINDS.items() if float(v or 0) <= 0)
    if bad:
        return {"ok": False, "denied": True, "rule": "kind_without_half_life",
                "kinds": bad, "why": "没有正半衰期 ⇒ 那条信息素**永不淡出**（场地会被压死）"}
    return {"ok": True, "readonly": True, "kinds": sorted(KINDS),
            "half_life_hours": {k: KINDS[k] for k in sorted(KINDS)}}


def check_append_only() -> dict:
    """闸B（**静态核**）：本模块**不许**出现删行 / 覆写账本的写法。

    为什么静态核：这条红线是「**未来别写坏**」——只有看源码才卡得住。
    """
    src = Path(__file__).read_text(encoding="utf-8-sig", errors="replace")
    # ⚠️ 模式必须**拆到变量里**：否则「模式字面量本身」就出现在源码里 ⇒ **判据自匹配自己** ⇒ 假红
    #    （现场：第一版把「双引号 + w + 双引号」直接写进注释 ⇒ 那个三字符仍**连续出现在文件里**
    #      ⇒ 自己命中自己；第二版才改成变量拼装 + 注释只做**文字描述**）
    _q = chr(34)          # 双引号（不写成字面量，避免自匹配）
    _wmode = chr(119)     # 写模式那个字母（同上：连**它自己**都不能以字面量出现）
    banned = []
    for pat, why in (("un" + "link(", "删文件"),
                     ("trun" + "cate(", "截断文件"),
                     ("open(path, " + _q + _wmode + _q + ")", "覆写账本"),
                     (_q + _wmode + _q, "写模式覆写"),
                     ("write_" + "text(", "整体覆写（本模块只准 locked_append_text）")):
        if pat in src:
            banned.append({"pattern": pat, "why": why})
    if banned:
        return {"ok": False, "denied": True, "rule": "pheromone_deleted_or_overwritten",
                "found": banned,
                "why": "账本必须**只追加**（挥发是读数）⇒ 不许出现删/截/覆写写法"}
    # 🔴 2026-09-22 修：原来 `"locked_append_text" not in src` 是**文本关键词** ——
    # 注释里提一句就过关，于是"我没读到真源码"这层保护**失效**（假绿）。
    # 现走 AST 真引用判据；**文本先当廉价前置筛**（真引用必然含该文本），没提到就不解析。
    # `None`（解析不了）**也**按未测处理 ⇒ 保持 fail-closed。
    from .source_judge import uses_name as _uses
    _u = _uses(src, "locked_append_text") if "locked_append_text" in src else False
    if _u is not True:
        return {"ok": False, "denied": True, "rule": "append_path_missing",
                "why": ("既没有删除写法、也没有**追加写法** ⇒ 说明我没读到真源码（**未测不按绿**）"
                        if _u is False else
                        "源码解析不了 ⇒ 追加写法**判不了**（**未测不按绿**）")}
    return {"ok": True, "readonly": True,
            "append_only": True, "writer": "locked_append_text",
            "checked": "本模块源码静态核（不许删行 / 不许覆写）"}


def run(op: str = "status", **params) -> dict:
    """能力入口：status / primitives / redlines / kinds / deposit / read / decay /
    forage / trail / collab_bridge / gate_kinds / gate_append_only。"""
    op = str(op or "status")
    if op == "status":
        return {"ok": True, "readonly": True, "kind": CAP_KIND, "domain": DOMAIN,
                "type": CAP_TYPE, "primitives": [dict(p) for p in PRIMITIVES],
                "red_lines": list(RED_LINES), "kinds": sorted(KINDS),
                "ledger": str(ledger_path()),
                "rows": len(_load_rows()),
                "bridge": collab_bridge(),
                "gate_kinds": check_kinds(),
                "gate_append_only": check_append_only()}
    if op == "primitives":
        return {"ok": True, "readonly": True, "primitives": [dict(p) for p in PRIMITIVES]}
    if op == "redlines":
        return {"ok": True, "readonly": True, "red_lines": list(RED_LINES)}
    if op == "kinds":
        return check_kinds()
    if op == "deposit":
        return deposit(params.get("kind", ""), params.get("subject", ""),
                       note=params.get("note", ""), strength=params.get("strength", 0.5),
                       source=params.get("source", ""), now=params.get("now"),
                       root=params.get("root"))
    if op == "read":
        return read(subject=params.get("subject"), kind=params.get("kind"),
                    now=params.get("now"), root=params.get("root"))
    if op == "decay":
        return decay(now=params.get("now"), root=params.get("root"))
    if op == "forage":
        return forage(subject_prefix=params.get("subject_prefix"),
                      top=params.get("top", 5), now=params.get("now"),
                      root=params.get("root"))
    if op == "trail":
        return trail(limit=params.get("limit", 20), root=params.get("root"))
    if op == "collab_bridge":
        return collab_bridge()
    if op == "gate_kinds":
        return check_kinds()
    if op == "gate_append_only":
        return check_append_only()
    raise ValueError("未知 op %r（可用：status/primitives/redlines/kinds/deposit/read/"
                     "decay/forage/trail/collab_bridge/gate_kinds/gate_append_only）" % (op,))


HONEST_BOUNDARY = (
    "它保证「痕迹**可留、可读、可按半衰期挥发**，且账本**只增不减、可回放**」；"
    "它保证不了「协同一定更聪明」—— 信息素会被**错误痕迹带偏**（这正是蚂蚁也会绕远路的原因）"
    "⇒ 所以本模块**只给读数、不自动执行**，并且每条留痕**必须带源**（好追责、好回滚判断）。"
    "它与 collab_gateway **并排**：直连解决点对点，间接解决「找不清谁」——**不是替代**。"
)
