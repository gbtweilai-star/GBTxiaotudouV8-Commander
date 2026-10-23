# gbt-capability: policy_delta
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""策略影响预检：**"这个改动会放行什么"**（蒸馏自 OpenShell 的"策略变更形式化预检"）。

## 抓取口径（凡抓取必写源·时间·口径）
· **源**：2026-10-01 主人给的 GitHub 飙升榜 #2 截图 `NVIDIA/OpenShell`（智能体安全运行时）。
  README 原文要点：「You declare what each agent can touch in a policy, and OpenShell enforces it」；
  「Each agent runs in an isolated sandbox」；「it **instruments the kernel** to enforce policy on every
  file access, system call, and network connection at runtime」；「**Agents never see real credentials**;
  OpenShell adds them only to requests bound for approved endpoints」；
  「it uses **formal verification to check what a policy change would allow before it is applied**」。
· **时间**：2026-10-01。Apache-2.0 · Rust · ★12,959（API 现读）。

## 蒸馏判断：OpenShell 的核里我们真缺哪块
| 它的架构 | 我们已有的对位 | 结论 |
|---|---|---|
| 策略声明 + 执行前强制（唯一的门） | `security/policy.py`（唯一门）· `preflight`（写盘/改状态预检）· `ghost_guard` · `hook_enforcer` | **已有，不重造** |
| 凭证不给智能体看（只在批准的请求上注入） | `key_gateway`（只存引用/只回掩码/真密钥走池） | **已有** |
| 每 agent 隔离沙箱 | `room_space`（隔离房间）· `mirror_space`（镜像演练）· worktree 舰队 | **已有** |
| 内核级强制（file/syscall/network 每一处） | **不接**：那要内核 instrumentation（eBPF/驱动），Windows 上更不是本仓能做到的；**如实记不吞** | 不接 |
| **策略变更的形式化预检：改前先算"会放行什么"** | 无 | **补这块** |

## 硬规矩
1. **只读**：本件**绝不写** `security/policy.py`（改它=主人专属）；只读三张表 + 历史账**算影响面**。
2. **影响面用真账现算**：拟放行动作在历史审计账里出现过几次 —— 现读现数，不估。
3. **必带"需主人授权"**：`propose` 的输出里固定写明「改表层需主人在终端批准」（AI 无权自授）。
4. **不猜**：表读不到 ⇒ 结构化报"未读到"，不拿空表当"没有影响"。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
_CAP = "policy_delta"


def _tables() -> dict:
    """现读三张权限表层（**只读**）：门的只读白名单 · 预检的只读白名单 · 作用域表。"""
    out = {"读不到": []}
    try:
        from gbt_allinone.security import policy as POL   # noqa: N806
        out["门（policy）·只读免卡动作"] = sorted(getattr(POL, "_READ_ONLY_TENTACLE", set()))
        out["作用域表（前 6）"] = sorted(getattr(POL, "SCOPES", {}) or {})[:6]
        out["作用域总数"] = len(getattr(POL, "SCOPES", {}) or {})
    except Exception as exc:  # noqa: BLE001
        out["读不到"].append("policy: %s" % str(exc)[:80])
    try:
        from gbt_allinone import preflight as PF               # noqa: N806
        out["预检（preflight）·只读免卡动作"] = sorted(getattr(PF, "_READ_ONLY_TENTACLE", set()))
    except Exception as exc:  # noqa: BLE001
        out["读不到"].append("preflight: %s" % str(exc)[:80])
    return out


def tables() -> dict:
    t = _tables()
    a = set(t.get("门（policy）·只读免卡动作") or [])
    b = set(t.get("预检（preflight）·只读免卡动作") or [])
    diff = {"只在门里": sorted(a - b), "只在预检里": sorted(b - a)} if a and b else None
    return {"ok": not t["读不到"], "op": "tables", "表": t,
            "两表分叉": diff or "**未读到**（两表没同时读到 ⇒ 不比，不猜）",
            "_口径": "只读现读；分叉 = 两套账（一处收卡、另一处说只读）——本件只报不改"}


def _audit_counts(actions: list) -> dict:
    """历史账里这些动作出现过几次（现读现数，不估）。"""
    p = ROOT / "gbt_allinone" / "store" / "audit.jsonl"
    env = __import__("os").getenv("GBT_STORE_DIR")
    if env:
        p = Path(env) / "audit.jsonl"
    if not p.is_file():
        return {"未读到": str(p)}
    counts = {a: 0 for a in actions}
    hits = 0
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        hits += 1
        for a in actions:
            if a in line:
                counts[a] += 1
    return {"账条数": hits, "按动作出现次数": counts}


def propose(add: str = "", why: str = "") -> dict:
    """**只读影响预检**：`add` = 逗号分隔的拟放行动作（只读候选）⇒ 会改变什么 + 历史露面次数。"""
    acts = [a.strip() for a in str(add or "").split(",") if a.strip()]
    if not acts:
        return {"ok": False, "fail_closed": True,
                "error": "缺 add：要预检什么？（逗号分隔的拟放行动作，例：see_window,domain_index）"}
    t = _tables()
    free_now = set(t.get("门（policy）·只读免卡动作") or [])
    if not free_now:
        return {"ok": False, "fail_closed": True, "error": "表层读不到 ⇒ 不猜影响面（fail-closed）"}
    flips, already = [], []
    for a in acts:
        (already if a in free_now else flips).append(a)
    cnt = _audit_counts(acts)
    return {"ok": True, "op": "propose",
            "拟放行": acts,
            "会从『被收卡』变『免卡』": flips,
            "本来已免卡（无变化）": already,
            "历史露面": cnt,
            "风险分级": {"低": [a for a in flips if a.split("_")[0] in ("list", "get", "read", "see", "find")],
                       "待看": [a for a in flips if a.split("_")[0] not in ("list", "get", "read", "see", "find")]},
            "为什么": str(why or "（未写理由）")[:200],
            "🔴 下一步（写盘是主人专属）":
                "改 `security/policy.py::_READ_ONLY_TENTACLE` 需**主人在终端批准**（AI 无权自授）；"
                "改完必须复跑：`py -3.14 gbt_allinone/tests/test_desktop_loop_ironlaw.py -q`（门契约判据）。",
            "_口径": "只读预检：只算『会放行什么』与历史露面次数；**本件一个字都不写**"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": _CAP, "tentacle": _CAP,
            "entry": "run_task('policy_delta', {...})",
            "ops": ["tables", "propose", "where"],
            "distilled_from": "2026-10-01 主人给的飙升榜 #2 NVIDIA/OpenShell（智能体安全运行时）"
                              "——只取**策略变更预检**（改前先算会放行什么）",
            "not_copied": "内核级强制（eBPF/驱动）**不接**（本仓做不到，如实记）；"
                          "唯一门/预检/凭据不外露/隔离房间 **已有对位**，不重造",
            "hard_rules": ["只读：绝不写 security/policy.py（改它=主人专属）",
                           "影响面用**真账现算**（历史露面次数现读现数，不估）",
                           "输出必带『需主人授权』；表读不到 ⇒ fail-closed，不拿空表当没影响"],
            "contract": [
                {"op": "tables", "params": "—", "returns": "三张表层 + 两表分叉（只读）"},
                {"op": "propose", "params": "add=动作,动作 + [why]", "returns": "影响预检（会放行什么 + 历史露面）"},
            ]}


def run_op(op: str = "tables", **params) -> dict:
    op = (op or "tables").lower()
    for n, fn in (("tables", tables), ("propose", propose), ("where", where)):
        if op == n:
            return fn(**params)
    return {"ok": False, "fail_closed": True, "error": "未知 op:%s（tables/propose/where）" % op}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="策略影响预检（OpenShell 蒸馏 · 只读不写）")
    ap.add_argument("cmd", nargs="?", default="tables")
    ap.add_argument("--add", default="")
    ap.add_argument("--why", default="")
    a = ap.parse_args()
    print(json.dumps(run_op(a.cmd, add=a.add, why=a.why), ensure_ascii=False, indent=1))
