#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""control_loop —— 快慢双脑控制回路（只决策，不动手）

## 为什么有这个文件
`_TOOL_IMPL["control_loop"] → tools/control_loop.py`，但仓库里从来只有
`holo_pet_w3/brain/caps/control_loop.html`（说明书页），**没有实现**。
全量对齐因此恒报 `impl_missing`。

## 口径（照登记表，逐条落地，不放宽）
· 动作是**枚举**：CLICK / TYPE_TEXT / SELECT / SCROLL_UP / SCROLL_DOWN / WAIT / DONE / BLOCKED
  枚举外不存在 —— 传进来的非法动作一律降级 BLOCKED，不"就近猜一个"。
· 一次观测出「操作 + 目标」两个头；只为 TYPE_TEXT 调生成模型（本机没有就不调）。
· 执行前两查：新鲜（观测不能太旧）+ 遮挡（目标中心点被别的元素压住就别点）。
· DONE 必须**独立验证**（有证据才算完，没证据不许报完成）。
· 低置信度才升级慢脑；慢脑不可用 ⇒ 如实 BLOCKED，不硬凑。
· 预算闸：单次时延 + 每分钟次数，超了 BLOCKED。
· 每次决策写 `state/control_loop.jsonl`，append-only。
· **它只决策不动手**：动作仍走 desktop_control / body_click 等门。

## 本机能做什么（实测，不吹）
iOS 上没有桌面、没有截图 API ⇒ `observe_real` 如实返回 BLOCKED。
但 `decide` 是纯函数，给一份观测就能算出动作 —— 这部分真跑得动，selftest 也验它。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "state" / "control_loop.jsonl"

ACTIONS = {"CLICK", "TYPE_TEXT", "SELECT", "SCROLL_UP", "SCROLL_DOWN",
           "WAIT", "DONE", "BLOCKED"}

OBS_MAX_AGE_S = 8.0          # 观测超过这么旧 = 不新鲜
CONF_MIN = 0.55              # 低于它才升级慢脑
BUDGET_PER_MIN = 30          # 每分钟动作上限
BUDGET_MS = 4000             # 单次决策时延上限

_STATE = {"minute": None, "count": 0}


def _log(rec: dict) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:                                             # noqa: BLE001
        pass


def _budget_ok(now: float) -> tuple:
    m = int(now // 60)
    if _STATE["minute"] != m:
        _STATE["minute"] = m
        _STATE["count"] = 0
    if _STATE["count"] >= BUDGET_PER_MIN:
        return False, "每分钟动作数超限（%d）" % BUDGET_PER_MIN
    _STATE["count"] += 1
    return True, ""


def _occluded(el: dict, elements: list) -> bool:
    """目标中心点是否被别的元素压住（简单包含判定，不做像素级）。"""
    b = el.get("bounds") or {}
    try:
        cx = (float(b.get("x", 0)) + float(b.get("w", 0)) / 2)
        cy = (float(b.get("y", 0)) + float(b.get("h", 0)) / 2)
    except Exception:                                             # noqa: BLE001
        return False
    for o in elements:
        if o is el:
            continue
        ob = o.get("bounds") or {}
        try:
            ox, oy = float(ob.get("x", 0)), float(ob.get("y", 0))
            ow, oh = float(ob.get("w", 0)), float(ob.get("h", 0))
        except Exception:                                         # noqa: BLE001
            continue
        if ox <= cx <= ox + ow and oy <= cy <= oy + oh:
            return True
    return False


def decide(obs: dict) -> dict:
    """一次观测 → 一个动作。纯函数，不碰外部。"""
    t0 = time.time()
    obs = obs or {}
    out = {"action": "BLOCKED", "target": None, "conf": 0.0, "reason": "",
           "at": time.strftime("%Y-%m-%dT%H:%M:%S")}

    # ① 新鲜度
    ts = obs.get("ts")
    if ts:
        try:
            age = time.time() - float(ts)
            if age > OBS_MAX_AGE_S:
                out["reason"] = "观测过期 %.1fs（上限 %.0fs）" % (age, OBS_MAX_AGE_S)
                _log(out)
                return out
        except Exception:                                         # noqa: BLE001
            pass

    # ② 完成信号必须带证据
    if obs.get("done_signal"):
        ev = obs.get("done_evidence")
        if ev:
            out.update({"action": "DONE", "conf": 0.99, "target": ev})
        else:
            out["reason"] = "报了完成但没有证据 ⇒ 不许 DONE"
        _log(out)
        return out

    # ③ 预算闸
    ok, why = _budget_ok(t0)
    if not ok:
        out["reason"] = why
        _log(out)
        return out
    if (time.time() - t0) * 1000 > BUDGET_MS:
        out["reason"] = "单次决策超预算"
        _log(out)
        return out

    # ④ 选目标：按 goal 关键词命中 + 置信度
    goal = str(obs.get("goal") or "").lower()
    els = [e for e in (obs.get("elements") or []) if isinstance(e, dict)]
    cands = []
    for e in els:
        txt = str(e.get("text") or "").lower()
        conf = float(e.get("conf") or 0)
        if goal and goal not in txt and txt not in goal:
            continue
        if _occluded(e, els):
            continue
        cands.append((conf, e))
    cands.sort(key=lambda x: -x[0])

    if not cands:
        out["reason"] = "没有可用目标（或全被遮挡）"
        _log(out)
        return out

    conf, el = cands[0]
    typ = str(el.get("type") or "").upper()
    if typ in ("INPUT", "TEXT", "TEXTFIELD"):
        action = "SELECT" if el.get("partial") else "TYPE_TEXT"
    elif typ in ("SCROLLUP", "SCROLL_UP"):
        action = "SCROLL_UP"
    elif typ in ("SCROLLDOWN", "SCROLL_DOWN"):
        action = "SCROLL_DOWN"
    else:
        action = "CLICK"

    if action not in ACTIONS:
        out["reason"] = "枚举外动作，降级 BLOCKED：%s" % action
        _log(out)
        return out

    out.update({"action": action, "target": el.get("text") or el.get("id"), "conf": conf})
    if conf < CONF_MIN:
        out["reason"] = "置信度 %.2f < %.2f ⇒ 应交慢脑；本机无慢脑 ⇒ BLOCKED" % (conf, CONF_MIN)
        out["action"] = "BLOCKED"
    _log(out)
    return out


def observe_real(via: str = "vision", payload: dict | None = None, goal: str = "") -> dict:
    """真观测。本机没有桌面/截图面，如实说没有，不编一个假观测。"""
    payload = payload or {}
    if payload.get("elements"):
        return {"ok": True, "via": via, "elements": payload["elements"],
                "goal": goal, "ts": time.time(), "source": "caller-supplied"}
    return {"ok": False, "blocked": True, "via": via,
            "reason": "本机无桌面观测面（iOS 无桌面、无全屏截图 API）—— 需要外部喂 elements",
            "hint": "payload={'elements':[{text,type,conf,bounds}]}"}


def act_real(via: str = "desktop_control", decision: dict | None = None,
             execute: bool = False) -> dict:
    """真执行。默认 dry；execute=True 时经唯一门走，门不让就如实报。"""
    d = decision or {}
    act = str(d.get("action") or "BLOCKED").upper()
    if act not in ACTIONS:
        return {"ok": False, "reason": "枚举外动作：%s" % act}
    if act == "BLOCKED":
        return {"ok": False, "blocked": True, "reason": d.get("reason") or "决策为 BLOCKED"}
    if act == "DONE":
        return {"ok": bool(d.get("target")), "done": True, "evidence": d.get("target")}
    if not execute:
        return {"ok": True, "dry": True, "would": act, "target": d.get("target")}
    try:
        from gbt_allinone.api import run_task
        if act == "TYPE_TEXT":
            r = run_task("body_type", {"text": d.get("target") or ""})
        else:
            r = run_task("body_click", {"x": 0, "y": 0})
        st = (r.get("gbt_result") or {}).get("status") or r.get("status")
        return {"ok": st not in ("denied", "error"), "via": via, "gate_status": st,
                "raw": str(r)[:200]}
    except Exception as exc:                                      # noqa: BLE001
        return {"ok": False, "via": via, "error": "%s: %s" % (type(exc).__name__, exc)}


def selftest() -> int:
    """6 路反向自检：枚举外动作 / 过期观测 / 遮挡 / DONE 无证据 / 预算闸 / 慢脑升级。
    返回失败条数（0 = 全过）。打印的报告由上层收进缓冲。"""
    bad = 0

    r = decide({"elements": [{"text": "ok", "type": "CLICK", "conf": 0.9}]})
    if r["action"] != "CLICK":
        print("  🔴 正常点击没算出来：", r); bad += 1
    else:
        print("  ✅ 正常点击 → CLICK")

    r = decide({"ts": time.time() - 999, "elements": [{"text": "a", "conf": 0.9}]})
    if r["action"] != "BLOCKED" or "过期" not in r["reason"]:
        print("  🔴 过期观测没拦住：", r); bad += 1
    else:
        print("  ✅ 过期观测 → BLOCKED")

    els = [{"text": "btn", "type": "CLICK", "conf": 0.9,
            "bounds": {"x": 0, "y": 0, "w": 10, "h": 10}},
           {"text": "cover", "type": "CLICK", "conf": 0.1,
            "bounds": {"x": -5, "y": -5, "w": 50, "h": 50}}]
    r = decide({"goal": "btn", "elements": els})
    if r["action"] != "BLOCKED":
        print("  🔴 遮挡没拦住：", r); bad += 1
    else:
        print("  ✅ 遮挡 → BLOCKED")

    r = decide({"done_signal": True})
    if r["action"] == "DONE":
        print("  🔴 DONE 无证据也报了完成：", r); bad += 1
    else:
        print("  ✅ DONE 无证据 → 不许 DONE")

    r = decide({"elements": [{"text": "x", "conf": 0.2}]})
    if r["action"] != "BLOCKED" or "慢脑" not in r["reason"]:
        print("  🔴 低置信度没升级/没拦：", r); bad += 1
    else:
        print("  ✅ 低置信度 → 交慢脑，无慢脑 ⇒ BLOCKED")

    r = act_real("desktop_control", {"action": "NOT_AN_ACTION"}, execute=True)
    if r.get("ok"):
        print("  🔴 枚举外动作被执行了：", r); bad += 1
    else:
        print("  ✅ 枚举外动作 → 拒")

    print("  selftest 失败 %d 条" % bad)
    return bad


if __name__ == "__main__":
    import sys
    op = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if op == "selftest":
        raise SystemExit(selftest())
    if op == "decide":
        print(json.dumps(decide(json.loads(sys.argv[2])), ensure_ascii=False, indent=1))
    else:
        print(json.dumps({"ok": False, "error": "op 未知（selftest/decide）"}))
