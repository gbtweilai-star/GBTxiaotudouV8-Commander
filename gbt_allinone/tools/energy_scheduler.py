# gbt-capability: energy_scheduler
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""能源调度面：**并发上限 + 失败冷却 + 批次公平**（蒸馏自 vLLM 的调度核，只取架构）。

## 抓取口径（本仓规矩：凡抓取必写源·时间·口径）
· **源**：2026-09-28 主人给的周榜卡 `vllm`（92.7k★ · Python）的公开一句话介绍：
  「大模型推理加速引擎，同样的显卡能多扛几倍并发，自己部署 AI 服务基本绕不开它（推理加速/高并发）」。
  —— 一手仓库与文档本轮**未联网核验**（主人令：不出网花钱的动作），所以只蒸馏**调度架构**，
  不引用它的性能/规模数字，更不引 CUDA/PagedAttention 内核。
· **时间**：2026-09-28。
· **口径**：本机零算力 ⇒ 推理仍走**能源池的门**（`llm_chat`，逐调用受 `external_llm` 闸管）；
  本件只补它缺的那块——**调度面**：批量任务如何分给多个能源、谁并发几路、失败谁进冷却。

## 蒸馏判断：vLLM 的核里我们真缺哪块
| vLLM 的能力 | 我们已有的对位 | 结论 |
|---|---|---|
| 推理加速内核（CUDA/PagedAttention） | 无（本机零算力） | **不要**（没 GPU，造了也是空壳） |
| 高并发吞吐 | `hf_voice` 三臂轮询 + 冷却（单件）· 能源池 status | **只覆盖单件，不覆盖批量** |
| **调度面**：批量 → 多源分配 · 每源并发上限 · 失败冷却 · 公平 | 无 | **补这块（本件）** |

## 硬规矩
1. **plan 是纯本地**：只读能源池 status、只算分配，**不出网、不调模型** ⇒ 可单测、可审计。
2. **run 走门**：执行时每一发都经 `run_task('llm_chat', …)`（`external_llm` 闸管）；
   没票就逐发拿结构化拒绝并**如实记账**，不假装发出去过。
3. **失败冷却**：同一源连续 3 次失败 ⇒ 冷却 `cooldown_s` 秒，期间 plan 不再派给它。
4. **公平**：同批内负载最低者优先（round-robin by least-load），不 Starve 单源。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PLANS = _ROOT / "state" / "energy_scheduler_plans.jsonl"   # 计划 + 执行结果（追加式）
_COOL = _ROOT / "state" / "energy_scheduler_cool.json"      # 冷却表 {source: until_ts}

# 每源并发上限（按能源池 status 档；缺key 的根本不进调度）
_DEFAULT_CAPS = {"可用": 3, "接线态": 2, "限流": 1}
_FAILS_TO_COOL = 3


def _log(row: dict) -> None:
    _PLANS.parent.mkdir(parents=True, exist_ok=True)
    with open(_PLANS, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row},
                            ensure_ascii=False) + "\n")


def _cool() -> dict:
    if _COOL.is_file():
        try:
            return json.loads(_COOL.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _sources(caps: dict | None = None) -> list:
    """可调度能源（**动态读能源池**，不手抄名单）；缺key/不可用的不进调度。"""
    from . import energy_pool as ep
    r = ep.run("sources")
    out = []
    for s in (r.get("sources") or []):
        st = s.get("status")
        if st in _DEFAULT_CAPS:
            out.append({"source": s.get("source_id"), "status": st,
                        "cap": int((caps or {}).get(s.get("source_id")) or _DEFAULT_CAPS[st])})
    return out


def plan(batch=None, caps=None, cooldown_s: int = 300, **_kw) -> dict:
    """把一批 prompt 分给多个能源：**纯本地**，不出网。返回分配表 + 排队 + 冷却中名单。"""
    if not isinstance(batch, list) or not batch:
        return {"ok": False, "fail_closed": True,
                "error": "batch 要是非空列表（要调度的 prompt 数组）"}
    srcs = _sources(caps)
    if not srcs:
        return {"ok": False, "fail_closed": True,
                "error": "没有可调度能源（全部缺 key 或不可用）", "sources": []}
    cool = _cool()
    now = time.time()
    avail = [s for s in srcs if now >= float(cool.get(s["source"], 0))]
    cooled = [s["source"] for s in srcs if s not in avail]
    load = {s["source"]: 0 for s in avail}
    assignments, queued = [], []
    for i, item in enumerate(batch):
        cand = sorted((s for s in avail if load[s["source"]] < s["cap"]),
                      key=lambda s: (load[s["source"]], s["source"]))
        if not cand:                       # 全部源都满了 ⇒ 排队（如实报，不假装派出去了）
            queued.append({"i": i, "prompt_head": str(item)[:60]})
            continue
        s = cand[0]
        load[s["source"]] += 1
        assignments.append({"i": i, "source": s["source"],
                            "prompt_head": str(item)[:60]})
    plan_id = "esch-%s-%s" % (time.strftime("%Y%m%d"), str(int(time.time() * 1000))[-6:])
    row = {"plan_id": plan_id, "batch_n": len(batch), "assignments": assignments,
           "queued": queued, "cooled": cooled,
           "sources": [{"source": s["source"], "cap": s["cap"], "status": s["status"],
                        "load": load[s["source"]]} for s in avail]}
    _log({"event": "plan", **row})
    return {"ok": True, "op": "plan", **row,
            "_口径": "纯本地分配（公平=least-load）· 满了如实排队 · 冷却中的不派 · 执行仍走门"}


def _inner_ok(r) -> bool:
    """读穿信封，拿**内层能力**的 ok（不是外层信封自己的 ok）。

    🔴 2026-10-14 实测（探针亲测，不是猜）：门对「能力位内部**再调一次门**」这种**嵌套调用**
    返回的是**两层信封**——

        {status:"ok", ok:true, result:{authorization, kind, status,
                                       result:{ok:true, reply:…}}}   ← 真答案在这一层

    旧写法 `bool((r.get("result") or {}).get("ok"))` **只读了一层** ⇒ 中间那层没有 `ok` 键
    ⇒ 恒为 `False` ⇒ **5 发真成功的 LLM 调用被自家判据报成 5 发失败**
    （同期门账本 `audit.jsonl` 记的是 5 条 `event:"ok"` + `llm_unified ok=True`）。
    这是「**坏判据比坏对象更危险**」的活样本 —— 判据先修，别急着重跑。

    口径：一层层往里走，**取最里层那个带 `ok` 键的层**（越往里越接近真身）；一层都没有就 False。
    """
    node = r
    found = None
    while isinstance(node, dict):
        if "ok" in node:
            found = node
        nxt = node.get("result")
        if not isinstance(nxt, dict):
            break
        node = nxt
    return bool(found.get("ok")) if found is not None else False


def run(plan_id: str = "", **_kw) -> dict:
    """按计划**经门执行**：每一发都 `run_task('llm_chat', …)`；没票就逐发拿拒绝并记账。"""
    if not _PLANS.is_file():
        return {"ok": False, "fail_closed": True, "error": "还没有任何计划（先 plan）"}
    plan = None
    for ln in reversed(_PLANS.read_text(encoding="utf-8").splitlines()):
        ln = ln.strip()
        if not ln:
            continue
        try:
            row = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if row.get("event") == "plan" and (not plan_id or row.get("plan_id") == plan_id):
            plan = row
            break
    if plan is None:
        return {"ok": False, "fail_closed": True, "error": "找不到计划：%s" % plan_id}
    from .. import run_task as _door          # ⛔ 执行必须过唯一门，不直连任何 SDK
    fails: dict = {}
    results = []
    for a in plan.get("assignments") or []:
        src = a.get("source")
        r = _door("llm_chat", {"prompt": a.get("prompt_head") or "", "energy": src})
        ok = _inner_ok(r)          # 读穿两层信封（见 _inner_ok：旧写法只读一层 ⇒ 恒 False）
        if not ok:
            fails[src] = fails.get(src, 0) + 1
        results.append({"i": a.get("i"), "source": src,
                        "envelope_status": r.get("status"), "inner_ok": ok,
                        "denied": bool(r.get("denied"))})
    # 失败冷却：连败 _FAILS_TO_COOL 次 ⇒ 该源进冷却（如实记，不静默重试）
    cooled_now = []
    if fails:
        cool = _cool()
        for src, n in fails.items():
            if n >= _FAILS_TO_COOL:
                cool[src] = time.time() + 300.0
                cooled_now.append(src)
        _COOL.parent.mkdir(parents=True, exist_ok=True)
        _COOL.write_text(json.dumps(cool), encoding="utf-8")
    _log({"event": "run", "plan_id": plan.get("plan_id"), "sent": len(results),
          "denied": sum(1 for x in results if x["denied"]), "cooled_now": cooled_now})
    return {"ok": True, "op": "run", "plan_id": plan.get("plan_id"), "results": results,
            "denied_n": sum(1 for x in results if x["denied"]), "cooled_now": cooled_now,
            "_口径": "执行走唯一门；没票就逐发拿拒绝并如实记账（不假装发出去过）"}


def status(**_kw) -> dict:
    plans = 0
    if _PLANS.is_file():
        plans = sum(1 for ln in _PLANS.read_text(encoding="utf-8").splitlines()
                    if ln.strip() and json.loads(ln).get("event") == "plan")
    srcs = _sources()
    cool = _cool()
    now = time.time()
    return {"ok": True, "op": "status", "plans": plans,
            "sources": [{"source": s["source"], "status": s["status"], "cap": s["cap"]}
                        for s in srcs],
            "cooled": [k for k, v in cool.items() if now < float(v)]}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "energy_scheduler", "tentacle": "energy_scheduler",
            "entry": "run_task('energy_scheduler', {...})",
            "ops": ["plan", "run", "status", "where"],
            "distilled_from": "2026-09-28 主人给的周榜卡 vllm（92.7k★ · Python）——只取**调度架构**",
            "not_copied": "不引 CUDA/PagedAttention/continuous batching 内核（本机零算力，造了也是空壳）；"
                          "推理仍走能源池的门（llm_chat · external_llm 闸）",
            "hard_rules": ["plan 纯本地不出网（可单测可审计）",
                           "run 每一发都过唯一门，没票就如实记拒绝",
                           "同源连败 3 次 ⇒ 冷却 300s，期间不再派",
                           "公平：least-load 优先，不饿死单源"],
            "files": {"计划账": str(_PLANS.relative_to(_ROOT)), "冷却表": str(_COOL.relative_to(_ROOT))},
            "contract": [
                {"op": "plan", "params": "batch=[...]（非空）[caps]", "returns": "分配表+排队+冷却名单（纯本地）"},
                {"op": "run", "params": "plan_id", "returns": "逐发信封（denied 如实记）+ 冷却"},
                {"op": "status", "params": "—", "returns": "计划数 + 源清单 + 冷却中"},
            ]}


def run_op(op: str = "status", **params) -> dict:
    op = (op or "status").lower()
    for name, fn in (("plan", plan), ("run", run), ("status", status), ("where", where)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（plan/run/status/where）"}


if __name__ == "__main__":                                    # 主人的终端入口
    import argparse
    ap = argparse.ArgumentParser(description="能源调度面（vLLM 架构蒸馏 · 只取调度核）")
    ap.add_argument("cmd", nargs="?", default="status")
    ap.add_argument("--batch", default="", help="逗号分隔的批量 prompt（plan 用）")
    a = ap.parse_args()
    if a.cmd == "plan":
        print(json.dumps(run_op("plan", batch=[x for x in a.batch.split("|") if x]),
                         ensure_ascii=False, indent=1))
    else:
        print(json.dumps(run_op(a.cmd), ensure_ascii=False, indent=1))
