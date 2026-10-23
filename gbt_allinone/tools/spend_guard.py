# gbt-capability: spend_guard
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""花费守卫：**按维度追踪调用与 token + 阈值三态判定**（蒸馏自 paperclip 的"成本治理"架构）。

## 抓取口径（凡抓取必写源·时间·口径）
· **源**：2026-10-01 主人给的 GitHub 飙升榜 #5 截图 `paperclipai/paperclip`（团队智能体管理台）。
  README 原文要点：「Token and cost tracking by company, agent, project, goal, issue, provider, and model」；
  「Scoped budget policies with warning thresholds and **hard stops**」；
  「**Enforcement uses recorded spend**; usage reporting and in-flight work can delay a stop」。
· **时间**：2026-10-01。MIT · TypeScript · ★95,396（API 现读）。

## 蒸馏判断：paperclip 的核里我们真缺哪块
| 它的架构 | 我们已有的对位 | 结论 |
|---|---|---|
| 组织架构/任务签出/审批/防重复 | `command_chain`（防重复：work_key + 开放分派互斥）· `agent_council` · `console_hub` | **已有，不重造** |
| 运行期技能注入 | 388 技能 + 六条腿绑定 | **已有** |
| **按维度追踪 token 与花费** | 无（`energy_pool` 只管"选哪个源"，不管"花了多少"） | **补这块** |
| **阈值告警 + 硬停判定（用已记录花费）** | 无 | **补这块** |

## 硬规矩
1. **账里有什么读什么**：只读 `store/key_gateway/ledger.jsonl` 与 `store/audit.jsonl` 的现成字段；
   免费通道 token 记 0 就**报 0**（**不编花费、不按价目表脑补**）。
2. **只判定不拦**：`verdict` 只给三态（ok / warn / stop）——**拦仍走现有门**（本件不新增任何拦截面）。
3. **策略是数据**：阈值落 `spend_guard/policy.json`（主人可改）；缺策略 ⇒ 用默认并**如实标"默认"**。
4. **读不到如实报**：账不在 ⇒ 结构化说明（不许拿 0 冒充"零花费"）。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
_CAP = "spend_guard"
_DEFAULT_POLICY = {"warn_calls_per_day": 500, "stop_calls_per_day": 2000,
                   "warn_tokens_per_day": 2_000_000, "stop_tokens_per_day": 10_000_000}


def _store_root() -> Path:
    env = __import__("os").getenv("GBT_STORE_DIR")
    if env:
        return Path(env)
    try:
        from gbt_allinone._paths import STORE_DIR
        return Path(STORE_DIR)
    except Exception:  # noqa: BLE001
        return ROOT / "gbt_allinone" / "store"


def _rel(p) -> str:
    try:
        return str(Path(p).relative_to(ROOT))
    except Exception:  # noqa: BLE001
        return str(p)


def _read_jsonl(p: Path, limit: int = 20000) -> list:
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        try:
            out.append(json.loads(line))
        except Exception:  # noqa: BLE001
            continue
    return out


def policy(set_policy: dict | None = None) -> dict:
    """读/写**阈值策略**（数据文件，主人可改；写=显式给 set_policy）。"""
    f = _store_root() / _CAP / "policy.json"
    if set_policy:
        cur = {}
        if f.is_file():
            try:
                cur = json.loads(f.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                cur = {}
        cur.update({k: v for k, v in dict(set_policy).items() if k in _DEFAULT_POLICY})
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"ok": True, "op": "policy", "wrote": _rel(f), "policy": cur}
    if f.is_file():
        try:
            # 🔴 **默认打底再覆盖**（2026-10-01 修）：盘上策略可能只写了几个键
            #    （set_policy 只落调用方给的键）⇒ 不合并的话 verdict 会 KeyError。
            merged = {**_DEFAULT_POLICY, **json.loads(f.read_text(encoding="utf-8"))}
            return {"ok": True, "op": "policy", "source": _rel(f), "默认": False, "policy": merged}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "op": "policy", "error": "策略文件读不动：%s" % str(exc)[:80]}
    return {"ok": True, "op": "policy", "source": "内置默认（盘上无策略文件 ⇒ 如实标『默认』）",
            "默认": True, "policy": dict(_DEFAULT_POLICY)}


def ledger(day: str = "", provider: str = "") -> dict:
    """**按维度聚合真实账**：key_gateway 账（plan/call_ok…）× provider × 日。"""
    src = _store_root() / "key_gateway" / "ledger.jsonl"
    rows = _read_jsonl(src)
    if not rows and not src.is_file():
        return {"ok": False, "fail_closed": True,
                "error": "账不在：%s ⇒ 读不到就是读不到（不拿 0 冒充零花费）" % _rel(src)}
    by_day: dict = {}
    by_provider: dict = {}
    for r in rows:
        ts = str(r.get("ts") or "")
        d = ts[:10]
        if day and d != str(day):
            continue
        p = str(r.get("provider") or "?")
        if provider and p != str(provider):
            continue
        ev = str(r.get("event") or "?")
        tk = int(r.get("tokens") or 0)
        for bucket, key in ((by_day, d), (by_provider, p)):
            b = bucket.setdefault(key, {"calls": 0, "tokens": 0, "events": {}})
            if ev.startswith("call"):
                b["calls"] += 1
            b["tokens"] += tk
            b["events"][ev] = b["events"].get(ev, 0) + 1
    return {"ok": True, "op": "ledger", "source": _rel(src), "rows": len(rows),
            "按日": by_day, "按源": by_provider,
            "_口径": "token 记多少报多少（免费通道常见 0）——**不按价目表脑补花费**"}


def verdict(**params) -> dict:
    """**三态判定**（只读）：ok / warn / stop —— 依「**已记录花费**」对阈值；拦仍走现有门。"""
    pol = policy()
    P = pol.get("policy") or dict(_DEFAULT_POLICY)
    led = ledger()
    if not led.get("ok"):
        return {"ok": False, "op": "verdict", "fail_closed": True,
                "error": led.get("error"), "verdict": "unknown",
                "note": "账读不到 ⇒ 判不了（**unknown ≠ ok**）"}
    today = time.strftime("%Y-%m-%d")
    d = (led.get("按日") or {}).get(today) or {"calls": 0, "tokens": 0, "events": {}}
    v = "ok"
    why = "今日 calls=%d tokens=%d，均在阈内" % (d["calls"], d["tokens"])
    if d["calls"] >= P["stop_calls_per_day"] or d["tokens"] >= P["stop_tokens_per_day"]:
        v, why = "stop", "**已到硬停线**（calls %d / tokens %d）" % (d["calls"], d["tokens"])
    elif d["calls"] >= P["warn_calls_per_day"] or d["tokens"] >= P["warn_tokens_per_day"]:
        v, why = "warn", "已过告警线（calls %d / tokens %d）" % (d["calls"], d["tokens"])
    return {"ok": True, "op": "verdict", "verdict": v, "why": why, "today": today,
            "读数": d, "策略": P, "策略来源": pol.get("source"),
            "_口径": "只判定不拦（拦走现有门）；基于**已记录**花费 —— 在飞/未上报会延迟触发"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": _CAP, "tentacle": _CAP,
            "entry": "run_task('spend_guard', {...})",
            "ops": ["ledger", "policy", "verdict", "where"],
            "distilled_from": "2026-10-01 主人给的飙升榜 #5 paperclip（团队智能体管理台）"
                              "——只取**成本治理**：按维度追踪 + 阈值三态 + 硬停判定（用已记录花费）",
            "not_copied": "组织架构/任务签出/审批 **已有对位**（command_chain/agent_council/console_hub）不重造；"
                          "不新增拦截面（只判定；拦仍走现有门）",
            "hard_rules": ["账里有什么读什么（免费通道 token=0 就报 0，不脑补花费）",
                           "只判定不拦（verdict 三态；拦走现有门）",
                           "策略是数据（store/spend_guard/policy.json，主人可改；缺则标『默认』）",
                           "账读不到 ⇒ verdict=unknown（unknown ≠ ok）"],
            "files": {"策略": "spend_guard/policy.json", "账": "key_gateway/ledger.jsonl"},
            "contract": [
                {"op": "ledger", "params": "[day] + [provider]", "returns": "按日/按源聚合（真账）"},
                {"op": "policy", "params": "[set_policy]", "returns": "读/写阈值策略"},
                {"op": "verdict", "params": "—", "returns": "ok/warn/stop 三态（只读判定）"},
            ]}


def run_op(op: str = "verdict", **params) -> dict:
    op = (op or "verdict").lower()
    for n, fn in (("ledger", ledger), ("policy", policy), ("verdict", verdict), ("where", where)):
        if op == n:
            return fn(**params)
    return {"ok": False, "fail_closed": True, "error": "未知 op:%s（ledger/policy/verdict/where）" % op}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="花费守卫（paperclip 成本治理蒸馏 · 只判定不拦）")
    ap.add_argument("cmd", nargs="?", default="verdict")
    ap.add_argument("--day", default="")
    ap.add_argument("--provider", default="")
    a = ap.parse_args()
    print(json.dumps(run_op(a.cmd, day=a.day, provider=a.provider), ensure_ascii=False, indent=1))
