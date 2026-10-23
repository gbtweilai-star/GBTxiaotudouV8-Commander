# gbt-capability: handoff
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""跨体接续包：**架构背景 / 失败尝试 / 未完成任务 三桶 + 每条带出处**（蒸馏自 ai-memory）。

## 抓取口径（本仓规矩：凡抓取必写源·时间·口径）
· **源**：2026-09-28 主人给的周榜卡 `akitaonrails/ai-memory`（#08 · 当周 +1,224★ ·
  AGENT MEMORY）：「为二十多种编程 Agent 提供共享长期记忆和跨工具交接，让不同机器、不同 Agent
  都能接续架构背景、失败尝试和未完成任务。」
  —— 一手仓库与文档本轮**未联网核验**（主人令：不出网花钱的动作），只蒸馏**交接三桶**，
  不引用它的存储/同步实现。
· **时间**：2026-09-28。
· **口径**：本仓已有 `memory_bank`（印章/别名/迁移）· `obsidian_vault`（255 库）·
  `memory_manager`（FTS5 秒搜）· `event_ledger`（签名账）——**但它们都不回答"下一个人接手时
  该先读哪三句话"**。本件补的就是这三桶：**架构背景 / 失败尝试 / 未完成任务**，
  且**每条必须带 src**（没出处的交接 = 传闻，不收）。

## 蒸馏判断：它的核里我们真缺哪块
| 它的能力 | 我们已有的对位 | 结论 |
|---|---|---|
| 跨 Agent 长期记忆 | memory_bank / obsidian_vault / memory_manager | **已有，不重造** |
| 跨工具/跨机器接续 | skills_sync + 助理文件 + 台账（boot 注入） | **部分有** |
| **交接三桶（架构/失败/未完成）+ 出处** | 无专门件 | **补这块（本件）** |

## 硬规矩
1. **三桶齐**才算一条完整交接：`arch`（架构背景）· `failed`（失败尝试）· `todo`（未完成任务）
   —— 缺桶可以，但**必须显式写空数组**（"没有"也是个结论，不许留白）。
2. **没 src 不收**：每条交接必须写清出处（文件/台账/命令），**传闻不入账**。
3. **只追加不删**：`handoff.jsonl` 追加式；作废走 `retract` 追加一条引用原 id。
4. **读侧给"先读这三句"**：`read` 返回每桶最新一条 + 未完成任务的计数（接手先看这个）。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_LEDGER = _ROOT / "state" / "handoff.jsonl"
_BUCKETS = ("arch", "failed", "todo")


def _rel(p) -> str:
    """台账路径的安全显示：在仓内给相对路径，**在仓外给绝对路径**（不许抛）。

    实测（2026-09-28）：判据把 `_LEDGER` 重定向到临时目录后，`relative_to(_ROOT)`
    直接抛 `ValueError: ... is not in the subpath of ...` ⇒ read/verify 全崩。
    教训：显示用的路径换算**必须容错**——盘在哪不是错，报不出盘才是错。
    """
    try:
        return str(Path(p).relative_to(_ROOT))
    except ValueError:
        return str(p)


def _rows() -> list:
    if not _LEDGER.is_file():
        return []
    out = []
    for ln in _LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def write(topic: str = "", agent: str = "", arch=None, failed=None, todo=None,
          src: str = "", **_kw) -> dict:
    """写一条接续包：三桶（缺的**必须显式空数组**）+ **src 必给**。"""
    if not str(topic or "").strip():
        return {"ok": False, "fail_closed": True, "error": "topic 要给（这条交接是关于什么的）"}
    if not str(src or "").strip():
        return {"ok": False, "fail_closed": True,
                "error": "src 要给（出处：文件/台账/命令）——**没出处的交接 = 传闻，不收**"}
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "id": "ho-%d" % int(time.time() * 1000),
           "topic": str(topic)[:120], "agent": str(agent or "未知"),
           "arch": list(arch or []), "failed": list(failed or []), "todo": list(todo or []),
           "src": str(src)[:200]}
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "op": "write", "id": row["id"],
            "计数": {k: len(row[k]) for k in _BUCKETS}}


def read(topic: str = "", agent: str = "", limit: int = 5, **_kw) -> dict:
    """读接续包：**每桶最新一条 + 未完成任务计数**（接手先看这屏）。"""
    rows = _rows()
    if topic:
        rows = [r for r in rows if topic in str(r.get("topic") or "")]
    if agent:
        rows = [r for r in rows if str(r.get("agent") or "") == agent]
    rows = rows[-int(limit):]
    latest = {}
    for b in _BUCKETS:
        picked = None
        for r in reversed(rows):
            if r.get(b):
                picked = {"from": r.get("id"), "topic": r.get("topic"), "items": r[b]}
                break
        latest[b] = picked or {"items": [], "note": "该桶在所选范围内为空（空也是结论）"}
    open_todo = sum(len(r.get("todo") or []) for r in rows)
    return {"ok": True, "op": "read", "rows": len(rows), "latest": latest,
            "未完成任务总数": open_todo, "src": _rel(_LEDGER),
            "_口径": "三桶各给最新一条；未完成计数用于接手第一眼；空桶写空不写无"}


def retract(entry_id: str = "", why: str = "", src: str = "", **_kw) -> dict:
    """作废一条（**只追加不删**）：追加一条引用原 id 的 retract。"""
    if not str(entry_id or "").strip():
        return {"ok": False, "fail_closed": True, "error": "entry_id 要给（要作废哪条）"}
    if not str(src or "").strip():
        return {"ok": False, "fail_closed": True, "error": "src 要给（是谁判定它该作废）"}
    row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "id": "ho-retract-%d" % int(time.time() * 1000),
           "topic": "RETRACT", "agent": "", "arch": [], "failed": [], "todo": [],
           "ref": entry_id, "why": str(why)[:160], "src": str(src)[:200]}
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "op": "retract", "ref": entry_id}


def verify(**_kw) -> dict:
    """自查：① 每条都有 src；② 三桶键齐（空数组也要在）；③ 只追加（不出现改写痕迹）。"""
    rows = _rows()
    problems = []
    for i, r in enumerate(rows):
        if not str(r.get("src") or "").strip():
            problems.append("第 %d 条没 src（%s）" % (i + 1, r.get("id")))
        for b in _BUCKETS:
            if b not in r:
                problems.append("第 %d 条缺桶 %s（空也要显式写）" % (i + 1, b))
    return {"ok": not problems, "op": "verify", "rows": len(rows), "problems": problems,
            "_口径": "交接的地板：每条带 src + 三桶键齐；只追加不删"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "handoff", "tentacle": "handoff",
            "entry": "run_task('handoff', {...})",
            "ops": ["write", "read", "retract", "verify", "where"],
            "distilled_from": "2026-09-28 主人给的周榜卡 akitaonrails/ai-memory（#08 · +1,224★）"
                              "——只取**交接三桶**",
            "not_copied": "不引它的存储/同步实现；长期记忆仍走 memory_bank / obsidian_vault / "
                          "memory_manager（已有，不重造）",
            "hard_rules": ["三桶显式（缺桶写空数组，不留白）",
                           "没 src 不收（传闻不入账）",
                           "只追加不删（作废走 retract）"],
            "files": {"交接账": str(_LEDGER.relative_to(_ROOT))},
            "contract": [
                {"op": "write", "params": "topic [agent arch failed todo] + **src**", "returns": "id + 三桶计数"},
                {"op": "read", "params": "[topic agent limit]", "returns": "每桶最新一条 + 未完成计数"},
                {"op": "retract", "params": "entry_id + why + src", "returns": "追加作废（不删原条）"},
            ]}


def run_op(op: str = "read", **params) -> dict:
    op = (op or "read").lower()
    for n, fn in (("write", write), ("read", read), ("retract", retract),
                  ("verify", verify), ("where", where)):
        if op == n:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（write/read/retract/verify/where）"}


if __name__ == "__main__":                                     # 主人的终端入口
    import argparse
    ap = argparse.ArgumentParser(description="跨体接续包（ai-memory 三桶蒸馏 · 没 src 不收）")
    ap.add_argument("cmd", nargs="?", default="read")
    a = ap.parse_args()
    print(json.dumps(run_op(a.cmd), ensure_ascii=False, indent=1))
