# -*- coding: utf-8 -*-
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""做梦技能 dream_replay · 第 3 步第一小刀（**只读骨架** · Owner 2026-09-19 图纸 §4）。

五原语：日间念 OBSESS → 召回 RECALL → 变异 MUTATE → 模拟 SIMULATE → 巩固 CONSOLIDATE。

本刀只做**能安全做的那部分**：
  · **日间念**取自 `trace_store` 的 `traces`／`obsessions`（**不另立一份表**）；
  · 表是空的 ⇒ **报"0 条候选"**，绝不编一条假的念出来；
  · **巩固默认不写**（起步期）—— 只在显式 `consolidate=True` 且通过检查时才写；
  · **零外部动作**：源码里不出现 `run_task(` / `subprocess` / 出网原语（用例扫描锁死）；
  · **做梦不执行**：召回/变异/模拟全在内存里跑完，只回一份记录。

用法：
    py -3.10 -m gbt_allinone.tools.dream_replay            # 跑一次闭环（不写）
    py -3.10 -m gbt_allinone.tools.dream_replay --json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from enum import Enum
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from gbt_allinone import trace_store as TS  # noqa: E402

DEFAULT_HALF_LIFE_S = 24 * 3600      # 默认短：一天内自然淡掉（§4.13 默认档）
RECALL_TOP_N = 5


class DreamPrimitive(Enum):
    OBSESS = "日间念"        # 白天：记录"惦记"——未了结的痕迹 / 反复出现的信号 / 没升格的波动
    RECALL = "召回"          # 夜里：优先召回"念"最强的那批痕迹
    MUTATE = "变异"          # 围绕"念"做反事实：如果当时没拒？如果换参数？
    SIMULATE = "模拟"        # 在内存/沙盘推演一遍，不执行外部动作
    CONSOLIDATE = "巩固"     # 只有"念"+模拟双超阈值的，才升格常驻；其余一闪而逝


def obsess() -> dict:
    """日间念：**只读**地从已有痕迹里浮现"念"。表空就报空 —— 不许凭空造念。"""
    traces = TS._load("traces")
    obs = TS._load("obsessions")
    if not traces and not obs:
        return {"ok": True, "primitives": [p.value for p in DreamPrimitive],
                "obsessions": [], "count": 0,
                "note": "痕迹库是空的 ⇒ 今天没有念（不编、不补）"}
    out = []
    for r in obs:
        ids = [str(x) for x in (r.get("source_trace_ids") or [])]
        known = {str(t.get("id") or t.get("evidence_ref")) for t in traces}
        if not ids or any(i not in known for i in ids):
            continue          # 无源/悬空 ⇒ 这条念不成立（第四条硬约束）
        out.append(r)
    return {"ok": True, "primitives": [p.value for p in DreamPrimitive],
            "obsessions": out, "count": len(out),
            "note": "只收 source_trace_ids 全部可查的念；悬空的当场剔除"}


def recall(limit: int = RECALL_TOP_N) -> dict:
    """召回：按 `intensity` 排序取前 N（**顺序由强度决定，不由随机决定**）。"""
    got = obsess()
    ranked = sorted(got["obsessions"], key=lambda r: float(r.get("intensity") or 0), reverse=True)
    return {"ok": True, "recalled": ranked[:limit], "count": len(ranked[:limit]),
            "note": "按 intensity 降序；无源念已在 obsess 阶段剔除"}


def mutate(obs: dict) -> dict:
    """变异：围绕**同一个念**做反事实推演（对象不随机；随机只落在"选哪条分支"上）。"""
    subject = str(obs.get("subject") or "?")
    branches = ["如果当时没拒？", "如果换参数？", "如果换时机？"]
    idx = int(time.time() * 1000) % len(branches)      # 随机只作用在"选分支"
    return {"ok": True, "subject": subject, "branch": branches[idx],
            "source_trace_ids": list(obs.get("source_trace_ids") or []),
            "note": "对象固定为该念；产物必须带源指针（不许无源生成）"}


def simulate(mutation: dict) -> dict:
    """模拟：在内存里推演一遍。**不触发任何外部动作，只回一份内部记录。**"""
    return {"ok": True, "subject": mutation.get("subject"),
            "ask": mutation.get("branch"),
            "finding": "（骨架阶段：无外部动作、无出网、无写盘）",
            "external_action": False}


def should_consolidate(sim: dict, intensity: float) -> tuple:
    """巩固闸：**靠念的强度**（口径＝念＋模拟双超阈；阈值待拍，先用 0.6 占位并标出）。"""
    thr = 0.6
    return (float(intensity) > thr, "threshold_placeholder_0.6")


def dream_once(*, consolidate: bool = False) -> dict:
    """一次闭环：日间念 → 召回 → 变异 → 模拟 →（默认**不巩固**）。"""
    got = obsess()
    rec = recall()
    steps = [{"primitive": DreamPrimitive.OBSESS.value, "count": got["count"]}]
    if not rec["recalled"]:
        return {"ok": True, "steps": steps, "consolidated": 0,
                "note": "没有念 ⇒ 没有梦（无源之梦不成立）",
                "external_action": False}
    replayed = []
    for obs in rec["recalled"]:
        mut = mutate(obs)
        sim = simulate(mut)
        ok_cons, why = should_consolidate(sim, float(obs.get("intensity") or 0))
        replayed.append({"subject": obs.get("subject"), "branch": mut["branch"],
                         "simulate": sim, "qualified": ok_cons, "qualified_by": why,
                         "half_life_s": int(obs.get("half_life_s") or DEFAULT_HALF_LIFE_S)})
    steps += [{"primitive": DreamPrimitive.RECALL.value, "count": rec["count"]},
              {"primitive": DreamPrimitive.MUTATE.value, "count": rec["count"]},
              {"primitive": DreamPrimitive.SIMULATE.value, "count": rec["count"]}]
    # 巩固默认**不开**：即便够格也只排队（§4.13 两道闸）
    if consolidate:
        note = "本刀不实现写路径：巩固要走授权门 —— 这里如实返回'未写'"
    else:
        note = "起步期：只重演不巩固（默认闪逝）；够格的只排进待升格队列"
    return {"ok": True, "steps": steps, "replayed": replayed, "consolidated": 0,
            "note": note, "external_action": False}


def run(op="status", **params) -> dict:
    """能力入口（只读 · R-H193 补）：status / once。

    为什么补这个入口：本能力位此前**没有 `run()`**，编排内核接不上它
    ⇒ 它一直是"连自我介绍以外都没有"的孤儿。补上标准入口后即可被真调用。
    **不写盘、不执行、默认不巩固**（consolidate 默认 False）。
    """
    op = str(op or "status")
    if op == "status":
        return {"ok": True, "readonly": True,
                "primitives": [p.value for p in DreamPrimitive],
                "recall_top_n": RECALL_TOP_N, "default_consolidate": False}
    if op in ("once", "dream_once"):
        return dream_once(consolidate=bool(params.get("consolidate", False)))
    raise ValueError("未知 op %r（可用：status/once）" % (op,))


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="做梦技能（只读骨架：重演不执行）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    out = dream_once()
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print("闭环：%s" % " → ".join("%s(%s)" % (s["primitive"], s["count"]) for s in out["steps"]))
        print("巩固=%d · 外部动作=%s · %s" % (out["consolidated"], out["external_action"], out["note"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
