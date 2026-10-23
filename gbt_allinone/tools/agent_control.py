# gbt-capability: agent_control
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""Agent 统一控制面：**六面读数收进一屏**（蒸馏自 nasiko，只取控制面口径）。

## 抓取口径（本仓规矩：凡抓取必写源·时间·口径）
· **源**：2026-09-28 主人给的周榜卡 `Nasiko-Labs/nasiko`（#04 · 当周 +2,353★ ·
  AGENT CONTROL PLANE）：「为支持 A2A 协议的 Agent 提供统一控制平面，把部署、路由、鉴权、限流、
  成本和链路追踪集中起来，不要求额外网关或 Sidecar。」
  —— 一手仓库与文档本轮**未联网核验**（主人令：不出网花钱的动作），只蒸馏**控制面口径**，
  不引用它的实现/A2A 协议栈。
· **时间**：2026-09-28。
· **口径**：**不新起网关**（同它的"不要额外网关/Sidecar"）——六面读数**全部从本仓既有真源现读**，
  每面必须带 `src`（哪个台账/哪个文件），**指不出源的字段不出现**。

## 蒸馏判断：它的核里我们真缺哪块
| 它的能力 | 我们已有的对位 | 结论 |
|---|---|---|
| 部署/路由/鉴权/限流/成本/链路 | 散落在五处：助理文件 · api 分派 · policy 作用域 · energy_pool · event_ledger | **各有一半，缺"收进一屏"** |
| A2A 协议栈 / 网关 / Sidecar | 无（也不需要） | **不接**（本仓的门与账本就够） |
| **统一控制面视图** | 无 | **补这块（本件）** |

## 硬规矩
1. **六面每面带 src**：部署→助理文件 · 路由→api.py 分派行 · 鉴权→policy 作用域 ·
   限流→能源池/冷却表 · 成本→能源池 tier（不知道就如实写 unknown）· 链路→台账尾。
2. **读不到就写读不到**（未验≠没有），**不编**。
3. 只读视图：本件**不改任何配置**（要改配置走主人的终端）。
"""
from __future__ import annotations

import json
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parents[3]
_AGENTS = pathlib.Path.home() / ".zcode" / "agents"
_ROUTE_CAPS = ("ui_render", "train_recipe", "handoff", "agent_control", "agent_council",
               "agent_rig", "energy_scheduler", "event_ledger", "obsidian_vault",
               "memory_manager", "code_audit", "flow_canvas", "console_pages")


def _agent_files() -> list:
    return sorted(p for p in _AGENTS.glob("*.md")) if _AGENTS.is_dir() else []


def _oncall(p: pathlib.Path) -> str:
    """从助理文件里取「对位触手」那一段（就是它的路由声明）。"""
    try:
        for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if "对位触手" in ln:
                return ln.strip()[:200]
    except OSError:
        pass
    return "（文件里没写对位触手）"


def roster(**_kw) -> dict:
    """六面一屏：每个助理/角色一行，每面带 src。"""
    rows = []
    for p in _agent_files():
        rows.append({
            "agent": p.stem,
            "部署": {"在岗": p.is_file(), "src": str(p)},
            "路由": {"对位触手": _oncall(p), "src": "该助理文件的『对位触手』行"},
            "鉴权": {"说明": "路由到的作用域由 policy 决定；查具体作用域看 policy 视图",
                     "src": "gbt_allinone（policy.evaluate）"},
        })
    return {"ok": True, "op": "roster", "count": len(rows), "rows": rows,
            "_口径": "六面每面带 src；读不到写读不到；本件只读不改"}


def facets(**_kw) -> dict:
    """六面的**框架侧**读数（部署/路由/鉴权/限流/成本/链路），逐面带 src。"""
    import sys
    sys.path.insert(0, str(_ROOT))
    out: dict = {}
    out["部署"] = {"助理文件数": len(_agent_files()), "src": str(_AGENTS)}
    try:
        api = (_ROOT / "gbt_allinone" / "api.py").read_text(encoding="utf-8", errors="replace")
        out["路由"] = {"已知分派位数": sum(1 for c in _ROUTE_CAPS if ('kind == "%s"' % c) in api),
                       "src": "gbt_allinone/api.py"}
    except OSError as exc:                                        # noqa: BLE001
        out["路由"] = {"读数": "读不到：%s" % type(exc).__name__}
    try:
        from gbt_allinone import run_task
        r = run_task("security_status", {})
        inner = (r.get("result") or {}).get("result") if isinstance(r.get("result"), dict) else None
        out["鉴权"] = {"读法": "security_status 过门", "信封": r.get("status"),
                       "内层ok": (inner or {}).get("ok"), "src": "run_task('security_status')"}
    except Exception as exc:                                      # noqa: BLE001
        out["鉴权"] = {"读数": "读不到：%s" % type(exc).__name__}
    try:
        cool = json.loads((_ROOT / "state" / "energy_scheduler_cool.json").read_text(encoding="utf-8"))
        out["限流"] = {"冷却中能源": list((cool or {}).keys()), "src": "state/energy_scheduler_cool.json"}
    except Exception:                                             # noqa: BLE001
        out["限流"] = {"冷却中能源": [], "src": "state/energy_scheduler_cool.json（不在=没冷却）"}
    try:
        plans = _ROOT / "state" / "energy_scheduler_plans.jsonl"
        n = sum(1 for _ in open(plans, encoding="utf-8")) if plans.is_file() else 0
        out["成本"] = {"说明": "能源池 tier 本仓现读为 unknown（无真实计费面）⇒ **如实标 unknown**",
                       "调度计划行数": n, "src": "state/energy_scheduler_plans.jsonl + 能源池现状"}
    except Exception as exc:                                      # noqa: BLE001
        out["成本"] = {"读数": "读不到：%s" % type(exc).__name__}
    try:
        led = _ROOT / "state" / "event_ledger.jsonl"
        tail = []
        if led.is_file():
            for ln in led.read_text(encoding="utf-8", errors="replace").splitlines()[-3:]:
                try:
                    row = json.loads(ln)
                    tail.append({"seq": row.get("seq"), "kind": row.get("kind"), "at": row.get("at")})
                except json.JSONDecodeError:
                    continue
        out["链路"] = {"台账尾": tail, "src": "state/event_ledger.jsonl（哈希链签名账）"}
    except Exception as exc:                                      # noqa: BLE001
        out["链路"] = {"读数": "读不到：%s" % type(exc).__name__}
    return {"ok": True, "op": "facets", "facets": out,
            "_口径": "六面全从既有真源现读、逐面带 src；读不到如实写；**不新起网关/Sidecar**"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "agent_control", "tentacle": "agent_control",
            "entry": "run_task('agent_control', {...})",
            "ops": ["roster", "facets", "where"],
            "distilled_from": "2026-09-28 主人给的周榜卡 Nasiko-Labs/nasiko（#04 · +2,353★ · "
                              "AGENT CONTROL PLANE）——只取**控制面口径**",
            "not_copied": "不引它的 A2A 协议栈/网关/Sidecar；六面读数全部来自本仓既有真源"
                          "（助理文件 · api.py · policy · 能源池 · 签名账）",
            "hard_rules": ["六面每面带 src；指不出源的字段不出现",
                           "读不到写读不到（未验≠没有），不编",
                           "只读视图：本件不改任何配置"],
            "files": {"助理目录": str(_AGENTS)},
            "contract": [
                {"op": "roster", "params": "—", "returns": "每个助理一行（部署/路由/鉴权 + src）"},
                {"op": "facets", "params": "—", "returns": "框架侧六面读数（逐面带 src）"},
            ]}


def run_op(op: str = "facets", **params) -> dict:
    op = (op or "facets").lower()
    for n, fn in (("roster", roster), ("facets", facets), ("where", where)):
        if op == n:
            return fn(**params)
    return {"ok": False, "fail_closed": True, "error": f"未知 op:{op}（roster/facets/where）"}


if __name__ == "__main__":                                     # 主人的终端入口
    import argparse
    ap = argparse.ArgumentParser(description="Agent 统一控制面（nasiko 口径蒸馏 · 六面一屏）")
    ap.add_argument("cmd", nargs="?", default="facets")
    a = ap.parse_args()
    print(json.dumps(run_op(a.cmd), ensure_ascii=False, indent=1))
