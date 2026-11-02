# gbt-capability: hand_bridge
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""hand_bridge — 灵巧手硬件桥（原生位 · 2026-11-01 蒸馏自 dexterous-hand 知识胶囊）。

## 它是什么（以及不是什么）
一个**与厂商解耦的手部 HAL**：统一 `connect / read_state / move / stop / disconnect`，
底下可换传输（loopback 仿真 / Modbus TCP / 串口 / CAN），上面统一关节名+限位+单位。
- **是**：真协议帧（Modbus TCP 自己组 MBAP+PDU，纯 stdlib）、真限位夹取、真回读、
  真 dry_run；loopback 是可跑通的仿真手（不是"假成功"——它明白写着 simulated）。
- **不是**：不是厂商 SDK 复刻。**寄存器映射/关节名/标定**必须由使用者按 datasheet 提供
  （`register_map`）；我们吞噬的 5 个硬件仓只给了 README/接口概念，**没有**把某家寄存器表
  当成事实写死 —— 未提供映射就 `needs_config`，**不猜**。

## 吸收来源
`rh56dfx_description`（16★, MIT）· `inspire-hand-rh56-py`（5★, MIT）· `rp_dexhand`（10★）·
`dexterous_hand_ros2`（4★, MIT）· `tesollo_ros2`（4★, BSD-3）五份知识胶囊（2026-11-01 吞噬）：
共同模式 = **关节表 + 传输（Modbus/CAN/串口）+ 限位**，本件按这个模式自写，未复制代码。

## 契约
op（默认 status）：
  · `status`     只读：传输可用性 / 会话数 / 安全口径
  · `transports` 只读：各传输与依赖
  · `profiles`   只读：内置关节表
  · `connect`    payload: transport=loopback|modbus_tcp|serial|can · profile=generic_6dof|generic_20dof
  · `read_state` payload: session
  · `move`       payload: session · targets={关节: 弧度} · dry_run（默认 True）· confirm
  · `stop`       payload: session
  · `disconnect` payload: session
  · `where`      只读
诚实出口：`needs_dependency`（缺 pyserial/python-can）、`needs_config`（真机缺 register_map）、
`user_error`（未知关节/非法值）。写面（move/stop）挂 `filesystem_write` 之外的
`process_execute`？不 —— 本件不启子进程；真机写由传输层做，cap 注册 `safe: False` 由 policy 收口。
"""
from __future__ import annotations

import importlib.util
import json
import math
import socket
import struct
import time

__all__ = ["run", "STATUS", "PROFILES", "TRANSPORTS", "modbus_build_read",
           "modbus_build_write", "modbus_parse"]

PI = math.pi

# ── 内置关节表（通用命名；厂商表由 register_map 提供）──────────────────────
def _joints(names, lo=-0.2, hi=1.8):
    return [{"name": n, "limit": [lo, hi]} for n in names]


PROFILES = {
    "generic_6dof": {"dof": 6, "joints": _joints(
        ["thumb_flex", "index_flex", "middle_flex", "ring_flex", "pinky_flex", "thumb_rot"],
        lo=-1.2, hi=1.8)},
    "generic_20dof": {"dof": 20, "joints": _joints(
        [f"{f}_{j}" for f in ("thumb", "index", "middle", "ring", "pinky")
         for j in ("mcp", "pip", "dip", "abd")], lo=-1.2, hi=1.8)},
}

TRANSPORTS = {
    "loopback": {"available": True, "needs": [], "note": "仿真手：真跑状态机，不驱动硬件"},
    "modbus_tcp": {"available": True, "needs": ["stdlib socket"], "note": "纯 stdlib 组 MBAP/PDU；需 register_map"},
    "serial": {"available": importlib.util.find_spec("serial") is not None,
               "needs": ["pyserial"], "note": "串口；缺依赖时如实 needs_dependency"},
    "can": {"available": importlib.util.find_spec("can") is not None,
            "needs": ["python-can"], "note": "CAN/CAN-FD；缺依赖时如实 needs_dependency"},
}

STATUS = {
    "cap": "hand_bridge", "tier": "native",
    "ops": ["status", "transports", "profiles", "connect", "read_state",
            "move", "stop", "disconnect", "contact", "read_force", "compliance", "where"],
    "transports": TRANSPORTS,
    "profiles": sorted(PROFILES),
    "safety": {"move_default_dry_run": True, "limits_clamped": True,
               "real_device_requires": ["register_map（寄存器映射）", "confirm=true"],
               "loopback": "simulated（不是真手）"},
}

_SESSIONS = {}


def _next_sid():
    return "hb%04d" % (len(_SESSIONS) + 1)


def _profile_of(payload):
    prof = payload.get("profile")
    if isinstance(prof, dict):
        return prof
    if isinstance(prof, str) and prof in PROFILES:
        return PROFILES[prof]
    return None


def _limits(profile):
    return {j["name"]: (j.get("limit") or [-PI, PI])[:2] for j in profile.get("joints") or []}


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


# ── Modbus TCP（真帧；纯 stdlib）───────────────────────────────────────────
def _mbap(unit, pdu):
    return struct.pack(">HHHB", 0, 0, len(pdu) + 1, unit & 0xFF) + pdu


def modbus_build_read(unit, addr, count=1):
    """FC03 读保持寄存器。"""
    return _mbap(unit, struct.pack(">BHH", 3, addr & 0xFFFF, count & 0xFFFF))


def modbus_build_write(unit, addr, values):
    """FC16 写多寄存器。"""
    vals = [int(v) & 0xFFFF for v in values]
    pdu = struct.pack(">BHHB", 16, addr & 0xFFFF, len(vals), len(vals) * 2)
    pdu += b"".join(struct.pack(">H", v) for v in vals)
    return _mbap(unit, pdu)


def modbus_parse(frame):
    """解析 MBAP+PDU；返回 {ok, unit, fc, addr, values|error}。"""
    if len(frame) < 9:
        return {"ok": False, "error": "frame too short"}
    tid, proto, length, unit = struct.unpack(">HHHB", frame[:7])
    pdu = frame[7:7 + length - 1]
    if not pdu:
        return {"ok": False, "error": "empty pdu"}
    fc = pdu[0]
    if fc & 0x80:
        return {"ok": False, "unit": unit, "fc": fc, "error": "exception code %d" % pdu[1]}
    if fc == 3:
        n = pdu[1]
        vals = [struct.unpack(">H", pdu[2 + 2 * i:4 + 2 * i])[0] for i in range(n // 2)]
        return {"ok": True, "unit": unit, "fc": fc, "values": vals}
    if fc == 16:
        addr, cnt = struct.unpack(">HH", pdu[1:5])
        return {"ok": True, "unit": unit, "fc": fc, "addr": addr, "count": cnt}
    return {"ok": True, "unit": unit, "fc": fc, "raw": pdu.hex()}


class _Loopback:
    """仿真手：有状态、可读、可写；明写 simulated。"""
    simulated = True

    def __init__(self, profile):
        self.profile = profile
        self.state = {j["name"]: 0.0 for j in profile.get("joints") or []}
        self.force = {j["name"]: 0.0 for j in profile.get("joints") or []}
        self.stiffness = 1.0
        self.damping = 0.05

    def write(self, targets):
        self.state.update(targets)
        return {"ok": True, "written": dict(targets)}

    def read(self):
        return {"ok": True, "joints": dict(self.state), "simulated": True,
                "force": dict(self.force), "stiffness": self.stiffness}

    def contact(self, joint, external, stiffness=None, damping=None):
        """虚拟接触：力 = k*(关节位置 - 外部位置)；仅仿真。"""
        if joint not in self.state:
            return {"ok": False, "status": "user_error", "error": "未知关节 %s" % joint}
        k = float(self.stiffness if stiffness is None else stiffness)
        d = float(self.damping if damping is None else damping)
        f = k * (float(self.state[joint]) - float(external))
        self.force[joint] = round(f, 6)
        return {"ok": True, "simulated": True, "joint": joint, "force": round(f, 6),
                "stiffness": k, "damping": d, "external": float(external),
                "contact": abs(f) > 1e-6}

    def set_compliance(self, stiffness=None, damping=None):
        if stiffness is not None:
            self.stiffness = max(0.0, float(stiffness))
        if damping is not None:
            self.damping = max(0.0, float(damping))
        return {"ok": True, "simulated": True, "stiffness": self.stiffness, "damping": self.damping}


class _ModbusTcp:
    simulated = False

    def __init__(self, host, port=502, unit=1, timeout=3.0):
        self.host, self.port, self.unit, self.timeout = host, int(port), int(unit), float(timeout)
        self.sock = None

    def open(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.settimeout(self.timeout)
        return {"ok": True, "host": self.host, "port": self.port, "unit": self.unit}

    def _txn(self, frame):
        if not self.sock:
            return {"ok": False, "error": "not connected"}
        self.sock.sendall(frame)
        head = self.sock.recv(7)
        if len(head) < 7:
            return {"ok": False, "error": "short mbap"}
        _, _, length, _ = struct.unpack(">HHHB", head)
        body = self.sock.recv(max(2, length - 1))
        return modbus_parse(head + body)

    def close(self):
        try:
            if self.sock:
                self.sock.close()
        finally:
            self.sock = None
        return {"ok": True}

    def write(self, targets, register_map):
        """按 register_map 把关节弧度换成寄存器值写下去。"""
        jm = (register_map or {}).get("joints") or {}
        vals, addrs = [], []
        for name, rad in targets.items():
            spec = jm.get(name)
            if not spec:
                return {"ok": False, "status": "needs_config",
                        "error": "register_map 缺关节 %s（不猜寄存器）" % name}
            raw = int(round(float(rad) * float(spec.get("scale", 1.0)) + float(spec.get("offset", 0.0))))
            vals.append(raw)
            addrs.append(int(spec.get("reg")))
        if not vals:
            return {"ok": False, "error": "没有可写目标"}
        start = min(addrs)
        if addrs != list(range(start, start + len(addrs))):
            return {"ok": False, "status": "needs_config", "error": "寄存器不连续：本件只写连续块"}
        res = self._txn(modbus_build_write(self.unit, start, vals))
        return {"ok": bool(res.get("ok")), "transport": "modbus_tcp", "reg_start": start,
                "values": vals, "reply": res}

    def read(self, register_map):
        rm = (register_map or {}).get("read") or {}
        start, count = int(rm.get("start", 0)), int(rm.get("count", 1))
        res = self._txn(modbus_build_read(self.unit, start, count))
        return {"ok": bool(res.get("ok")), "transport": "modbus_tcp",
                "raw": res, "reg_start": start, "count": count}


def _apply_move(profile, targets, dry_run, max_step=0.0):
    lim = _limits(profile)
    applied, clamped, rejected, step_limited = {}, [], [], []
    for name, raw in (targets or {}).items():
        if name not in lim:
            rejected.append(name)
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError):
            rejected.append(name)
            continue
        lo, hi = lim[name]
        if not (lo <= val <= hi):
            clamped.append(name)
            val = _clamp(val, lo, hi)
        applied[name] = round(val, 6)
    if max_step and applied:
        # 单步限幅：没有读回当前状态时以 0 为基准（保守）
        over = [n for n, v in applied.items() if abs(v) > max_step]
        for n in over:
            applied[n] = round(max(-max_step, min(max_step, applied[n])), 6)
        step_limited = over
    return applied, clamped, rejected, step_limited


def run(op="status", **kw):
    op = str(op or "status").strip().lower()
    if op == "status":
        return {"ok": True, "op": "status", **STATUS,
                "sessions": [{"session": sid, "transport": s["transport"],
                              "profile": s["profile"].get("name"),
                              "simulated": s["dev"].simulated} for sid, s in _SESSIONS.items()]}
    if op == "transports":
        return {"ok": True, "op": "transports", "transports": TRANSPORTS}
    if op == "profiles":
        return {"ok": True, "op": "profiles", "profiles": [
            {"name": name, "dof": p.get("dof", len(p.get("joints") or [])),
             "joints": [j["name"] for j in p.get("joints") or []]}
            for name, p in PROFILES.items()]}
    if op == "where":
        return {"ok": True, "op": "where", "cap": "hand_bridge",
                "entry": "py -3.14 tools/codex-scripts/five-dim.py cap hand_bridge '{\"op\":\"status\"}'",
                "module": "gbt_allinone/tentacle/hand_bridge.py",
                "loopback_example": "{\"op\":\"connect\",\"transport\":\"loopback\",\"profile\":\"generic_6dof\"}",
                "real_example": "connect(transport=modbus_tcp, host=192.168.1.10, port=502, register_map={...})",
                "诚实边界": "loopback 是仿真；真机必须给 register_map（厂商 datasheet 未吸收）"}
    if op == "connect":
        transport = str(kw.get("transport") or "loopback").lower()
        profile = _profile_of(kw)
        if profile is None:
            return {"ok": False, "op": op, "status": "needs_input",
                    "error": "未知 profile（内置：%s，或传 dict）" % ", ".join(PROFILES)}
        if transport == "loopback":
            dev = _Loopback(profile)
            sid = _next_sid()
            _SESSIONS[sid] = {"transport": transport, "profile": profile, "dev": dev,
                              "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            return {"ok": True, "op": op, "session": sid, "transport": transport,
                    "profile": profile.get("name"), "simulated": True,
                    "note": "仿真手（loopback）：真状态机，不驱动真硬件"}
        if transport == "modbus_tcp":
            host = kw.get("host")
            if not host:
                return {"ok": False, "op": op, "status": "needs_input", "error": "modbus_tcp 需要 host"}
            dev = _ModbusTcp(host, kw.get("port", 502), kw.get("unit", 1), kw.get("timeout", 3.0))
            try:
                opened = dev.open()
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "op": op, "status": "failed",
                        "error": "%s: %s" % (type(e).__name__, str(e)[:160])}
            sid = _next_sid()
            _SESSIONS[sid] = {"transport": transport, "profile": profile, "dev": dev,
                              "register_map": kw.get("register_map"),
                              "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
            return {"ok": True, "op": op, "session": sid, "transport": transport,
                    "profile": profile.get("name"), "simulated": False, **opened}
        if transport in ("serial", "can"):
            tr = TRANSPORTS[transport]
            if not tr["available"]:
                return {"ok": False, "op": op, "status": "needs_dependency",
                        "error": "缺依赖 %s（不假装能连）" % "、".join(tr["needs"]),
                        "how_to_fix": "pip install %s" % ("pyserial" if transport == "serial" else "python-can")}
            return {"ok": False, "op": op, "status": "needs_config",
                    "error": "%s 传输已登记但本件未实现厂商适配（未吸收其协议）" % transport,
                    "honesty": "未实现就不许报成功；需要按 datasheet 补适配层"}
        return {"ok": False, "op": op, "status": "user_error",
                "error": "未知 transport：%s" % transport,
                "available": list(TRANSPORTS)}
    sid = str(kw.get("session") or "")
    sess = _SESSIONS.get(sid)
    if not sess:
        return {"ok": False, "op": op, "status": "user_error",
                "error": "会话不存在（先 connect）：%r" % sid,
                "sessions": list(_SESSIONS)}
    dev = sess["dev"]
    if op == "contact":
        if sess["transport"] != "loopback":
            return {"ok": False, "op": op, "status": "needs_hardware",
                    "error": "真机接触/力反馈需要传感器；本件不伪造力",
                    "session": sid, "transport": sess["transport"]}
        return {**dev.contact(str(kw.get("joint")), kw.get("external", 0.0),
                              kw.get("stiffness"), kw.get("damping")), "op": op, "session": sid}
    if op == "read_force":
        if sess["transport"] != "loopback":
            return {"ok": False, "op": op, "status": "needs_hardware",
                    "error": "真机力反馈需要传感器；本件不伪造力", "session": sid}
        return {"ok": True, "op": op, "session": sid, "simulated": True,
                "force": dict(dev.force), "stiffness": dev.stiffness}
    if op == "compliance":
        if sess["transport"] != "loopback":
            return {"ok": False, "op": op, "status": "needs_hardware",
                    "error": "真机柔顺控制需要厂商接口；本件不伪造", "session": sid}
        return {**dev.set_compliance(kw.get("stiffness"), kw.get("damping")),
                "op": op, "session": sid}
    if op == "read_state":
        if sess["transport"] == "loopback":
            res = dev.read()
        else:
            res = dev.read(sess.get("register_map"))
        return {"ok": bool(res.get("ok")), "op": op, "session": sid,
                "transport": sess["transport"], "profile": sess["profile"].get("name"),
                "state": res, "simulated": dev.simulated}
    if op == "move":
        targets = kw.get("targets") or kw.get("joints") or {}
        if not isinstance(targets, dict) or not targets:
            return {"ok": False, "op": op, "status": "needs_input",
                    "error": "需要 targets={关节: 弧度}"}
        dry_run = kw.get("dry_run", True) is not False
        applied, clamped, rejected, step_limited = _apply_move(
            sess["profile"], targets, dry_run, float(kw.get("max_step") or 0.0))
        if rejected:
            return {"ok": False, "op": op, "status": "user_error",
                    "error": "未知关节（按 profile 拒收）：%s" % rejected,
                    "known": sorted(_limits(sess["profile"]))}
        if dry_run:
            return {"ok": True, "op": op, "session": sid, "dry_run": True,
                    "would_apply": applied, "clamped": clamped, "step_limited": step_limited,
                    "note": "dry_run：没有写硬件；确认真机时传 dry_run=false + confirm=true"}
        if not dev.simulated and kw.get("confirm") is not True:
            return {"ok": False, "op": op, "status": "needs_confirm",
                    "error": "真机写必须 confirm=true（防误动）",
                    "would_apply": applied, "clamped": clamped}
        if sess["transport"] == "loopback":
            res = dev.write(applied)
        else:
            if not sess.get("register_map"):
                return {"ok": False, "op": op, "status": "needs_config",
                        "error": "真机写需要 register_map（寄存器映射未吸收，不猜）",
                        "how_to_fix": "按厂商 datasheet 提供 {joints:{name:{reg,scale,offset}}, read:{start,count}}"}
            res = dev.write(applied, sess["register_map"])
        return {"ok": bool(res.get("ok")), "op": op, "session": sid,
                "transport": sess["transport"], "simulated": dev.simulated,
                "applied": applied, "clamped": clamped, "step_limited": step_limited,
                "transport_reply": res,
                "honesty": "loopback=仿真；真机回读见 read_state" if dev.simulated else None}
    if op == "stop":
        lim = _limits(sess["profile"])
        zeros = {n: 0.0 for n in lim}
        if dev.simulated:
            dev.write(zeros)
            return {"ok": True, "op": op, "session": sid, "simulated": True,
                    "stopped": True, "applied": zeros}
        if kw.get("confirm") is not True:
            return {"ok": False, "op": op, "status": "needs_confirm",
                    "error": "真机 stop 也需 confirm=true"}
        if sess["transport"] == "modbus_tcp":
            res = dev.write(zeros, sess.get("register_map") or {})
            return {"ok": bool(res.get("ok")), "op": op, "session": sid,
                    "transport": sess["transport"], "transport_reply": res}
        return {"ok": False, "op": op, "status": "needs_config",
                "error": "该传输的 stop 未实现（不假装）"}
    if op == "disconnect":
        try:
            if hasattr(dev, "close"):
                dev.close()
        finally:
            _SESSIONS.pop(sid, None)
        return {"ok": True, "op": op, "session": sid, "disconnected": True}
    return {"ok": False, "op": op, "status": "unknown_op",
            "error": "未知 op：%s" % op, "available": STATUS["ops"], "fail_closed": True}

