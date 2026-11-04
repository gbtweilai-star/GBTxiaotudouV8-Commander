# -*- coding: utf-8 -*-
# gbt-capability: body_control  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""body_control（身体控制 / 触手 / 全息投影）—— **如实报缺，不假装能动**。

主人 2026-11-02 定名与纪律：
  「这个能力域叫 body_control（身体控制/触手/全息投影），我现读：not_supported（未接线）。
   深度学习 + 无模型不等于能动——缺感觉/缺执行器（未绑定或已被主人拔掉）时如实报缺，不假装能动。」

本件只做**状态/清单/判据**（零作用域纯数据）：
  · 传感器清单：camera / microphone / screen / depth / tentacle_bus；
  · 执行器清单：tentacle_bus / holographic_projection / digital_human_display / robot_arm；
  · 绑定来源：调用方传入 `bindings`（服务端读 state/body_control.json）；没有=未绑定；
  · 状态只有 `not_supported`（未接线）/ `partial`（有绑定但执行器未接）；**没有 ready**；
  · `move()` 永远 returned `executed=false`；不在这里驱动任何硬件。
"""
from __future__ import annotations

import hashlib

DOMAIN = "body_control"
SENSORS = ("camera", "microphone", "screen", "depth", "tentacle_bus")
ACTUATORS = ("tentacle_bus", "holographic_projection", "digital_human_display", "robot_arm")
NOTE = ("缺感觉/执行器（未绑定或已被主人拔掉）时如实报缺；深度学习 + 无模型不等于能动，"
        "不假装能动、不伪造动作回执。")


def inventory(bindings=None) -> dict:
    b = bindings if isinstance(bindings, dict) else {}
    def table(names, section):
        src = b.get(section) if isinstance(b.get(section), dict) else {}
        return {n: bool(src.get(n)) for n in names}
    return {"domain": DOMAIN, "sensors": table(SENSORS, "sensors"),
            "actuators": table(ACTUATORS, "actuators"),
            "binding_source": (b.get("source") if isinstance(b.get("source"), str) else "") or "调用方未提供"}


def status(bindings=None) -> dict:
    inv = inventory(bindings)
    sensor_missing = [k for k, ok in inv["sensors"].items() if not ok]
    actuator_missing = [k for k, ok in inv["actuators"].items() if not ok]
    any_sensor = len(sensor_missing) < len(SENSORS)
    any_actuator = len(actuator_missing) < len(ACTUATORS)
    if not any_sensor and not any_actuator:
        st = "not_supported"
        reason = "未接线：感觉与执行器都没绑定（not_supported）"
    elif not any_actuator:
        st = "not_supported"
        reason = "有部分感觉但执行器未接；仍不能动（not_supported）"
    elif not any_sensor:
        st = "not_supported"
        reason = "有执行器但缺感觉；不能闭环，仍报 not_supported"
    else:
        st = "partial"
        reason = "有绑定，但本件没有执行器驱动/安全闭环，动作仍不执行（partial）"
    return {"ok": True, "domain": DOMAIN, "status": st, "wired": False,
            "sensors": inv["sensors"], "actuators": inv["actuators"],
            "missing": {"sensors": sensor_missing, "actuators": actuator_missing},
            "executor": "not_wired", "note": NOTE,
            "binding_source": inv["binding_source"]}


def move(action=None, **params) -> dict:
    """动作口：永远如实拒绝（没有执行器/没有安全闭环）。"""
    return {"ok": False, "status": "not_supported", "executed": False,
            "domain": DOMAIN, "requested": str(action or params.get("action") or ""),
            "reason": "body_control 未接线：没有绑定执行器/安全闭环，动作不执行",
            "note": NOTE}


def verify() -> dict:
    checks = []

    def ck(name, cond, got=None):
        checks.append({"name": name, "ok": bool(cond), "got": got})

    s0 = status({})
    ck("默认 not_supported", s0["status"] == "not_supported" and s0["wired"] is False, s0["status"])
    ck("默认缺感觉", "camera" in s0["missing"]["sensors"])
    ck("默认缺执行器", "tentacle_bus" in s0["missing"]["actuators"])
    ck("不假装 ready", s0["status"] != "ready")
    m = move("wave")
    ck("动作不执行", m["ok"] is False and m["executed"] is False and m["status"] == "not_supported", m)
    ck("拒绝带原因", "未接线" in m["reason"])
    s1 = status({"sensors": {"camera": True}, "actuators": {}})
    ck("只有感觉仍 not_supported", s1["status"] == "not_supported")
    ck("部分感觉列出缺执行器", "tentacle_bus" in s1["missing"]["actuators"])
    s2 = status({"sensors": {k: True for k in SENSORS},
                 "actuators": {k: True for k in ACTUATORS}})
    ck("全绑定也只 partial", s2["status"] == "partial" and s2["wired"] is False, s2["status"])
    ck("全绑定仍不执行", move("walk")["executed"] is False)
    ck("清单含全部传感器", set(inventory({})["sensors"]) == set(SENSORS))
    ck("清单含全部执行器", set(inventory({})["actuators"]) == set(ACTUATORS))
    ck("schema 有 domain", run("schema")["domain"] == DOMAIN)
    ck("status 可读", run("status")["ok"] is True)
    ck("inventory 可读", set(run("inventory")["sensors"]) == set(SENSORS))
    ck("schema 有 note", "note" in run("schema"))
    ck("未知 op 拒", _raises(lambda: run("teleport")))
    return {"ok": all(c["ok"] for c in checks), "checks": len(checks),
            "failed": [c for c in checks if not c["ok"]],
            "sha": hashlib.sha256(str(checks).encode()).hexdigest()[:12]}


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except ValueError:
        return True


def run(op="status", **params):
    op = str(op or "status").lower()
    if op == "schema":
        return {"ok": True, "domain": DOMAIN, "sensors": list(SENSORS),
                "actuators": list(ACTUATORS), "statuses": ["not_supported", "partial"],
                "note": NOTE}
    if op == "status":
        return status(params.get("bindings"))
    if op == "inventory":
        return {"ok": True, **inventory(params.get("bindings"))}
    if op == "move":
        return move(params.get("action"), **{k: v for k, v in params.items() if k != "action"})
    if op == "verify":
        return verify()
    raise ValueError("未知 op: %s（schema/status/inventory/move/verify）" % op)
