# gbt-capability: control_loop
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""快慢双脑控制回路（蒸馏自 Jev / TypeSafe「System One」+ browser-use/jev-ultrafast 的架构）。

## 抓取口径（本仓规矩：凡抓取必写源·时间·口径）
· **源**：`typesafe.ai/blog/introducing-system-one-models-and-jev`（一手公告）
  与 `github.com/browser-use/jev-ultrafast`（一手仓库 README）。
· **时间**：2026-09-27 抓取。
· **口径**：**官方自述**。它自己写明的 caveat 一并承接下来 —— 评测在美西的笔记本上跑、
  定价可持续性未证（可能补贴）、演示查询被简化且键名对人类友好、工作流评测由自家团队造的
  "可能有偏差"、193.6x/444.6x 是"真实收益区间的高端"、wikiracing 的加速"少得多"。
  ⇒ 我们**只移植架构**，不引用它的绝对性能数字当我们的业绩。

## 移植过来的四条（这才是"突破瓶颈"的部分）
  1. **动作是枚举，不是自由文本**：`CLICK · TYPE_TEXT · SELECT · SCROLL_UP · SCROLL_DOWN ·
     WAIT · DONE · BLOCKED`（它只有这些）。枚举之外的动作**不存在** ⇒ 天生没有"删库"这类动作位。
  2. **两个头、一次往返**：一次观测里同时算「选哪个操作」和「选哪个目标」（它的关键提速：
     浏览器协议调用 1,092 → 101，−91%；中位任务 9.450s → 7.092s）。
     ⇒ 我们的实现：**一次观测喂给快脑，同时出 op 头与 target 头**，不串行多轮调用。
  3. **只为"要文本"的动作叫生成模型**：只有 `TYPE_TEXT` 需要文本，且文本必须先能解析才准输入
     （宁可 BLOCKED，也不乱打字）。
  4. **执行前两查 + DONE 独立验证**：目标必须**新鲜度**（观测没过期）与**遮挡**（没被挡）双查；
     **`DONE` 不能自己宣布成功**（它自己把"需要独立结果验证"写进 limitation）——
     ⇒ 我们把它做成硬判据：没有验证证据的 DONE 一律拒绝。

## 我们的门（它没有、我们必须有）
  · 动作全部走既有授权门（`desktop_control` 等作用域）；本工具**只做决策与审计**，不自己动手；
  · **预算闸**：单次决策时延上限 + 每分钟决策上限（对着它的成本口径：每秒 10 次 = 每小时
    36,000 次 ≈ $7；我们记自己的账，不按它宣传的价目表折算）；
  · **审计链**：每次决策写 `state/control_loop.jsonl`（一次写入不回改 = Raw 层）；
  · **低置信度不许硬猜**：快脑置信度低于阈值 ⇒ 升级慢脑；慢脑没配 ⇒ 如实 `BLOCKED`。

命令：
  python tools/control_loop.py demo                       # 跑一遍脚本化场景（不碰真实桌面）
  python tools/control_loop.py selftest                    # 判据自检（含四路反向自检）
  python tools/control_loop.py decide --obs <obs.json>     # 单次决策（干跑，不出动作）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
TRACE = ROOT / "state" / "control_loop.jsonl"

# 动作空间（枚举，照移植；**枚举之外的动作不存在** —— 这是安全的第一层）
OPS = ("CLICK", "TYPE_TEXT", "SELECT", "SCROLL_UP", "SCROLL_DOWN", "WAIT", "DONE", "BLOCKED")
DEFAULT_THRESHOLD = 0.60        # 快脑置信度低于此值 ⇒ 升级慢脑
DEFAULT_MAX_AGE_MS = 1500       # 观测新鲜度上限（超过即拒执行，要求重新观测）
BUDGET = {"max_ms_per_decision": 1200, "max_calls_per_min": 600}


def _trace(row: dict) -> None:
    TRACE.parent.mkdir(parents=True, exist_ok=True)
    with open(TRACE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row},
                            ensure_ascii=False) + "\n")


class Budget:
    """预算闸：单次时延 + 每分钟次数。超了**降级**（不许硬撑）。"""

    def __init__(self, spec: dict | None = None):
        self.spec = {**BUDGET, **(spec or {})}
        self.calls: list[float] = []

    def check(self, elapsed_ms: float) -> tuple[bool, str]:
        now = time.time()
        self.calls = [t for t in self.calls if now - t < 60]
        if elapsed_ms > self.spec["max_ms_per_decision"]:
            return False, f"单次决策 {elapsed_ms:.0f}ms 超上限 {self.spec['max_ms_per_decision']}ms"
        if len(self.calls) >= self.spec["max_calls_per_min"]:
            return False, f"每分钟决策数 {len(self.calls)} 已达上限 {self.spec['max_calls_per_min']}"
        self.calls.append(now)
        return True, "在预算内"


def fast_policy(obs: dict) -> dict:
    """**快脑**：规则策略（纯函数、可测、0 成本）。一次观测 → op 头 + target 头。

    真实系统里这一层可以换成任何快决策模型（本地小模型 / 类型化决策 API）——
    本函数就是那个"契约的形状"：**输入观测，输出 {op, target_index, confidence}**。
    """
    goal = (obs.get("goal") or "").lower()
    nodes = obs.get("nodes") or []
    for n in nodes:
        name = (n.get("name") or "")
        role = (n.get("role") or "").lower()
        idx = n.get("index")
        if "type_text" in goal or "输入" in goal or "搜索" in goal:
            if role in ("textbox", "combobox", "searchbox") and "search" in name.lower():
                return {"op": "TYPE_TEXT", "target_index": idx, "confidence": 0.9,
                        "text_hint": obs.get("text") or ""}
        if ("click" in goal or "点击" in goal or "打开" in goal) and name.lower() in goal:
            return {"op": "CLICK", "target_index": idx, "confidence": 0.8}
    if "收工" in goal or "完成" in goal or "done" in goal:
        return {"op": "DONE", "target_index": None, "confidence": 0.95,
                "evidence": obs.get("done_evidence")}   # 可能是 None ⇒ 由守卫来拒（不许自己宣布成功）
    return {"op": "BLOCKED", "target_index": None, "confidence": 0.3,
            "why": "快脑没有匹配到可用动作（枚举内无解）"}


def guard(obs: dict, decision: dict, max_age_ms: int = DEFAULT_MAX_AGE_MS) -> tuple[bool, str]:
    """**执行前两查 + DONE 独立验证**（移植自它的两条硬要求）。"""
    op = decision.get("op")
    if op not in OPS:
        return False, f"动作 {op!r} 不在枚举内（枚举之外的动作不存在）"
    if op in ("BLOCKED", "WAIT"):
        return True, "无需两查（不是落点动作）"
    if op == "DONE":
        ev = decision.get("evidence")
        if not ev:
            return False, "DONE 缺独立验证证据 ⇒ 拒绝（不许自己宣布成功）"
        return True, f"DONE 带验证证据：{str(ev)[:60]}"
    age = int(obs.get("age_ms") or 0)
    if age > max_age_ms:
        return False, f"观测已过期 {age}ms > {max_age_ms}ms ⇒ 拒绝执行，要求重新观测"
    nodes = obs.get("nodes") or []
    ti = decision.get("target_index")
    tgt = next((n for n in nodes if n.get("index") == ti), None)
    if tgt is None:
        return False, f"目标 {ti} 不在本次观测里 ⇒ 拒绝（防点错）"
    if tgt.get("occluded"):
        return False, f"目标 {ti} 被遮挡 ⇒ 拒绝（它自己写明的遮挡复查）"
    return True, "两查通过（新鲜 + 未遮挡 + 目标真实存在）"


def decide(obs: dict, slow_planner=None, threshold: float = DEFAULT_THRESHOLD,
           budget: Budget | None = None, max_age_ms: int = DEFAULT_MAX_AGE_MS) -> dict:
    """一次决策周期：快脑 → 预算闸 → （低置信度）慢脑 → 两查 → 留痕。**不出动作。**"""
    t0 = time.perf_counter()
    b = budget or Budget()
    fast = fast_policy(obs)
    path = "fast"
    if fast.get("confidence", 0) < threshold:
        if slow_planner is None:
            fast = {**fast, "op": "BLOCKED",
                    "why": f"置信度 {fast.get('confidence')} < {threshold} 且**没有慢脑** ⇒ 如实 BLOCKED（不许硬猜）"}
        else:
            fast = slow_planner(obs)
            path = "slow"
    elapsed = (time.perf_counter() - t0) * 1000
    ok_b, why_b = b.check(elapsed)
    if not ok_b:
        out = {"ok": False, "decision": {"op": "BLOCKED", "why": f"预算闸：{why_b}"},
               "path": path, "elapsed_ms": round(elapsed, 1), "budget": "超"}
        _trace({"goal": obs.get("goal"), **out})
        return out
    ok_g, why_g = guard(obs, fast, max_age_ms)
    out = {"ok": ok_g, "decision": fast if ok_g else {"op": "BLOCKED", "why": why_g},
           "path": path, "elapsed_ms": round(elapsed, 1), "guard": why_g,
           "budget": why_b, "threshold": threshold}
    _trace({"goal": obs.get("goal"), "op": fast.get("op"), "path": path,
            "ok": ok_g, "elapsed_ms": round(elapsed, 1), "guard": why_g})
    return out


# ── 接真能力：过唯一门取观测 / 落动作（2026-09-27 加）──────────────────
def _gate(kind: str, payload: dict) -> dict:
    """**过唯一门**调一个能力位（观察面与动作面都走这里，**不许直连模块**）。"""
    sys.path.insert(0, str(ROOT))
    import gbt_allinone as g
    r = g.run_task(kind, payload)
    d = r.get("result") if isinstance(r, dict) else None
    return {"ok": bool(isinstance(r, dict) and r.get("ok", True)),
            "status": (r.get("status") if isinstance(r, dict) else None),
            "error": (r.get("error") if isinstance(r, dict) else None),
            "raw": d, "gate": "run_task"}


_ELEM_RX = re.compile(r"([\w\u4e00-\u9fa5][\w\u4e00-\u9fa5 ._/\-]{1,40}?)\s*(?:@|at|位于|坐标)\s*\(?\s*(\d{1,5})\s*[,，]\s*(\d{1,5})")


def adapt_to_nodes(via: str, raw) -> tuple[list, str]:
    """把能力位吐出来的东西规范成**带索引元素表**（Jev 那种形状：index/name/role/pos）。

    **诚实口径**：认不出来就返回空表并说明原因 —— **不许硬编元素**（编出来的点点错人）。
    """
    txt = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
    nodes, seen = [], set()
    for i, m in enumerate(_ELEM_RX.finditer(txt), start=1):
        name, x, y = m.group(1).strip(), int(m.group(2)), int(m.group(3))
        if name in seen:
            continue
        seen.add(name)
        low = name.lower()
        role = ("textbox" if any(k in low for k in ("input", "search", "textbox", "输入", "搜索"))
                else "button" if any(k in low for k in ("btn", "button", "按钮", "link", "链"))
                else "node")
        nodes.append({"index": i, "name": name, "role": role, "pos": [x, y],
                      "occluded": False, "source": via})
    why = (f"从 {via} 的读数里认出 {len(nodes)} 个可落点元素"
           if nodes else f"{via} 的读数里**没认出**可落点元素（没有「名字 at (x,y)」形状）⇒ 空表")
    return nodes, why


def observe_real(via: str, payload: dict, goal: str = "", text_hint: str = "") -> dict:
    """**真观测**：过门调观察面，产出可直接喂快脑的观测（带真实新鲜度时间戳）。"""
    t0 = time.time()
    r = _gate(via, payload)
    nodes, why = adapt_to_nodes(via, r.get("raw"))
    return {"goal": goal, "text": text_hint, "nodes": nodes,
            "age_ms": int((time.time() - t0) * 1000), "via": via,
            "gate_ok": r["ok"], "gate_status": r["status"], "gate_error": r.get("error"),
            "adapt": why, "raw_head": (str(r.get("raw"))[:280] if r.get("raw") is not None else "")}


def act_real(via: str, decision: dict, execute: bool = False) -> dict:
    """**真动作**：默认只算不动；要执行必须显式 `--execute`，且**动作仍走门** ——
    门拒了就如实报「缺什么作用域、谁有权给」，**不绕门**。"""
    payload = {"op": decision.get("op"), "target": decision.get("target_index"),
               "text": decision.get("text_hint") or ""}
    if not execute:
        return {"executed": False, "why": "dry（未加 --execute）", "would_call": via, "payload": payload}
    r = _gate(via, payload)
    return {"executed": True, "via": via, "payload": payload,
            "gate_ok": r["ok"], "gate_status": r["status"], "result": str(r.get("raw"))[:400]}


# ── 脚本化场景（不碰真实桌面）─────────────────────────────────────────
SCENES = {
    "正常：搜索框输入": {"goal": "在搜索框输入关键词", "age_ms": 120,
                   "nodes": [{"index": 3, "role": "textbox", "name": "SearchBox", "occluded": False}],
                   "text": "gbt"},
    "过期观测：拒绝执行": {"goal": "在搜索框输入关键词", "age_ms": 9000,
                    "nodes": [{"index": 3, "role": "textbox", "name": "SearchBox"}], "text": "x"},
    "遮挡：拒绝执行": {"goal": "点击 SearchBox 打开", "age_ms": 100,
                  "nodes": [{"index": 7, "role": "button", "name": "searchbox", "occluded": True}]},
    "低置信度：升级慢脑/如实阻断": {"goal": "随便做点什么", "age_ms": 100, "nodes": []},
    "DONE 无证据：拒绝": {"goal": "这单收工", "age_ms": 100, "nodes": [], "done_evidence": None},
}


def _demo_done(obs):
    return {"op": "DONE", "target_index": None, "confidence": 0.9}      # 故意不带 evidence


def selftest() -> int:
    bad = 0
    print("── 场景跑批（脚本化观测，不碰桌面）──")
    for name, obs in SCENES.items():
        r = decide(obs)
        op = r["decision"].get("op")
        detail = r["decision"].get("why") if op in ("BLOCKED", "WAIT") else r.get("guard")
        print(f"  [{name}] → {op} · path={r['path']} · {detail}")
        expect_blocked = name != "正常：搜索框输入"
        if expect_blocked and r["decision"].get("op") != "BLOCKED":
            print("     🔴 本该阻断却放行"); bad += 1
        if not expect_blocked and r["decision"].get("op") != "TYPE_TEXT":
            print("     🔴 本该 TYPE_TEXT"); bad += 1
    print("── 反向自检：四条硬规矩各咬一口 ──")
    # ① 枚举外动作必须拒
    ok, why = guard({"age_ms": 0, "nodes": []}, {"op": "DELETE_EVERYTHING"})
    print(f"  {'✅' if not ok else '🔴'} 枚举外动作：{why}"); bad += 0 if not ok else 1
    # ② 过期观测必须拒
    ok, why = guard({"age_ms": 99999, "nodes": [{"index": 1}]}, {"op": "CLICK", "target_index": 1})
    print(f"  {'✅' if not ok else '🔴'} 观测过期：{why}"); bad += 0 if not ok else 1
    # ③ DONE 无证据必须拒
    ok, why = guard({"age_ms": 0, "nodes": []}, {"op": "DONE"})
    print(f"  {'✅' if not ok else '🔴'} DONE 无证据：{why}"); bad += 0 if not ok else 1
    # ④ 预算闸必须拦
    b = Budget({"max_ms_per_decision": -1})
    ok, why = b.check(1.0)
    print(f"  {'✅' if not ok else '🔴'} 预算闸：{why}"); bad += 0 if not ok else 1
    # ⑤ 低置信度 + 无慢脑 ⇒ 如实 BLOCKED（不许硬猜）
    r = decide({"goal": "无解任务", "age_ms": 10, "nodes": []})
    good = r["decision"].get("op") == "BLOCKED" and "慢脑" in str(r["decision"].get("why"))
    print(f"  {'✅' if good else '🔴'} 低置信度无慢脑：{r['decision'].get('why')}"); bad += 0 if good else 1
    # ⑥ 有慢脑时应当升级
    r = decide({"goal": "无解任务", "age_ms": 10, "nodes": []},
               slow_planner=_demo_done)
    good = r["path"] == "slow" and r["decision"].get("op") == "BLOCKED"
    print(f"  {'✅' if good else '🔴'} 升级慢脑后仍被 DONE 证据闸挡住：{r['decision'].get('why')}"); bad += 0 if good else 1
    print(f"\n自检结论：{'全过' if bad == 0 else f'🔴 失败 {bad} 项'}")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="快慢双脑控制回路（决策+守卫+预算+审计；不动手）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    sub.add_parser("demo")
    s = sub.add_parser("decide"); s.add_argument("--obs", required=True)
    s = sub.add_parser("observe")
    s.add_argument("--via", default="vision")
    s.add_argument("--payload-json", default="{}")
    s.add_argument("--goal", default="")
    s = sub.add_parser("act")
    s.add_argument("--via", default="desktop_control")
    s.add_argument("--decision-json", default="{}")
    s.add_argument("--execute", action="store_true", help="不加就是干跑")
    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        return 0 if selftest() == 0 else 1
    if a.cmd == "demo":
        for name, obs in SCENES.items():
            r = decide(obs)
            print(f"{name:<26} op={r['decision'].get('op'):<10} "
                  f"{r.get('guard') or r['decision'].get('why')}")
        return 0
    if a.cmd == "observe":
        obs = observe_real(a.via, json.loads(a.payload_json), goal=a.goal)
        print(json.dumps(obs, ensure_ascii=False, indent=1))
        return 0 if obs["gate_ok"] else 1
    if a.cmd == "act":
        out = act_real(a.via, json.loads(a.decision_json), execute=a.execute)
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0 if (out.get("executed") is False or out.get("gate_ok")) else 1
    obs = json.loads(Path(a.obs).read_text(encoding="utf-8"))
    print(json.dumps(decide(obs), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
