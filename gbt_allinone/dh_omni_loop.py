# -*- coding: utf-8 -*-
"""数字人 · 万能插细节操控 + 眼手脑实时闭环（2026-11-02）

主人令：「细节操控必须以万能插来实现」「眼手脑必须实时同步，边看边做」。

结构（三条并发流，不串行等）：
  · 眼（EYE）：前端每帧把**当前骨骼实测角度**报进来（/api/dh/frame 的 eye）；
  · 脑（BRAIN）：后台线程持续更新控制增益与相位预测（看误差调，不等动作做完）；
  · 手（HAND）：每帧把目标角度经**万能插**（omni_plug kind=dh，执行器 dh:rig）推进 rig。
前端拿到 targets 立刻叠骨；所以是"边看边做"，不是"看一眼停一下再动"。
"""
from __future__ import annotations

import json
import math
import threading
import time
from pathlib import Path

from . import dh_tentacle as DT

try:
    from . import omni_plug as OP
except Exception:  # noqa: BLE001
    OP = None

FPS = 30
PLAN_CACHE: dict = {}


def _plan(name: str) -> dict:
    name = str(name or "").strip().lower()
    if name not in PLAN_CACHE:
        PLAN_CACHE[name] = DT.plan(name)
    return PLAN_CACHE[name]


def _ease(p: float) -> float:
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


class DHControl:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.action = ""
        self.plan = None
        self.started = 0.0
        self.eye: dict = {}
        self.targets: dict = {}
        self.last_err: float = 0.0
        self.kp = 0.55
        self.kd = 0.12
        self.samples = 0
        self.last_tick = 0.0
        self.brain_ticks = 0
        self.brain_err = 0.0
        self.mode = "idle"
        self.omni = {"plugged": False, "last": None}
        self.hand = {"pose": "", "session": "", "state": None, "ok": False,
                     "transport": "loopback", "error": ""}
        self.hand_ticks = 0
        self.thread = None
        self.stop = False
        if OP is not None:
            OP.register_actuator("dh:rig", self._actuator)
            try:
                self.omni["plug"] = OP.plug_and_run("dh:rig", kind="dh", action="status",
                                                    args={"probe": True}, timeout=2)
                self.omni["plugged"] = bool(self.omni["plug"].get("ok"))
            except Exception as exc:  # noqa: BLE001
                self.omni["plug"] = {"ok": False, "error": str(exc)[:160]}

    # ---- 万能插执行器：真正的"手" ----
    def _actuator(self, payload: dict) -> dict:
        ts = (payload or {}).get("targets") or {}
        with self.lock:
            self.targets = {k: float(v) for k, v in ts.items()}
            self.samples += 1
        return {"ok": True, "applied": len(ts), "via": "omni_plug:dh:rig",
                "at": time.time()}

    # ---- 灵巧手 HAL：吞入件 hand_bridge（loopback 仿真真跑） ----
    def _hand_apply(self, pose: str) -> dict:
        try:
            from .tentacle import hand_bridge as HB
            from . import dh_tentacle as DT
            if self.hand.get("session"):
                HB.run("disconnect", session=self.hand["session"])
            c = HB.run("connect", transport="loopback", profile="generic_20dof")
            sess = str(c.get("session") or "")
            joints = DT.hand_pose(pose)
            for k in ("thumb_abd", "index_abd", "middle_abd", "ring_abd", "pinky_abd"):
                joints.setdefault(k, 0.0)
            m = HB.run("move", session=sess, joints=joints, dry_run=False)
            st = HB.run("read_state", session=sess)
            self.hand = {"pose": pose, "session": sess, "ok": bool(m.get("ok")),
                         "state": (st.get("state") if st.get("ok") else None),
                         "transport": "loopback", "move": m.get("ok"),
                         "error": "" if m.get("ok") else str(m.get("error") or m)[:160]}
            return self.hand
        except Exception as exc:  # noqa: BLE001
            self.hand = {"pose": pose, "session": "", "state": None, "ok": False,
                         "transport": "loopback", "error": str(exc)[:160]}
            return self.hand

    # ---- 动作切换 ----
    def set_action(self, name: str) -> dict:
        p = _plan(name)
        with self.lock:
            self.action = str(name)
            self.plan = p
            self.started = time.time()
            self.eye = {}
            self.targets = {}
            self.mode = "gesture:" + str(name)
        if not p.get("ok"):
            return {"ok": False, "error": p.get("error"),
                    "available": p.get("available")}
        if p.get("hand"):
            self._hand_apply(str(p["hand"]))
        else:
            self.hand = {"pose": "", "session": "", "state": None, "ok": False,
                         "transport": "loopback", "error": ""}
        return {"ok": True, "gesture": name, "dur": p.get("dur"),
                "hand": p.get("hand") or "",
                "hand_bridge": {"pose": self.hand.get("pose"),
                                "ok": self.hand.get("ok"),
                                "session": self.hand.get("session"),
                                "transport": self.hand.get("transport")},
                "tracks": len(p.get("tracks") or []),
                "source": p.get("source"), "type": p.get("type")}

    # ---- 眼：前端报实测 ----
    def set_eye(self, eye: dict) -> None:
        with self.lock:
            self.eye = {str(k): float(v) for k, v in (eye or {}).items()}

    # ---- 每帧：脑预测 + 手执行（经万能插） ----
    def tick(self) -> dict:
        t0 = time.time()
        with self.lock:
            p = self.plan
            started = self.started
            action = self.action
            kp, kd = self.kp, self.kd
            eye = dict(self.eye)
        out = {"ok": True, "action": action, "mode": "closed-loop",
               "via": "omni_plug:dh:rig", "targets": [], "err": 0.0,
               "phase": 0.0, "fps": FPS, "omni_plugged": self.omni.get("plugged")}
        if not p or not p.get("ok"):
            out["reason"] = "没有动作（先 /api/dh/action）"
            return out
        if p.get("type") == "clip":
            out.update({"reason": "clip 动作（walk）由资产 clip 播放", "targets": [],
                        "phase": 0})
            return out
        dur = float(p.get("dur") or 2.0)
        phase = (time.time() - started)
        u = max(0.0, min(1.0, phase / dur))
        idx_ratio = phase / dur * (p.get("frames") or 2)
        idx = int(round(idx_ratio))
        targets = []
        err_sum = 0.0
        n = 0
        for tr in (p.get("tracks") or []):
            frames = tr.get("frames") or []
            if not frames:
                continue
            i = max(0, min(len(frames) - 1, idx))
            base = float(frames[i])
            key = tr["bone"]
            akey = key + "." + str(tr.get("axis"))
            measured = float(eye.get(akey, eye.get(key, 0.0))) if eye else 0.0
            err = base - measured
            err_sum += abs(err)
            n += 1
            # 前馈 + 反馈：看误差给一点提前量（不是等动作做完再补）
            cmd = base + max(-0.12, min(0.12, kp * err))
            targets.append({"bone": key, "axis": tr.get("axis"),
                            "sign": tr.get("sign"), "angle": round(cmd, 5),
                            "measured": measured,
                            "err": round(err, 4),
                            "lead": round(cmd - base, 4)})
        err_mean = (err_sum / n) if n else 0.0
        # 手：经万能插执行器推进 rig（每个 tick 都走 omni_plug，不绕过）
        if OP is not None:
            try:
                r = OP.plug_and_run("dh:rig", kind="dh", action="apply",
                                    args={"targets": {(x["bone"] + "." + str(x["axis"])): x["angle"] for x in targets}},
                                    timeout=2)
                self.omni["last"] = r
                out["omni"] = {k: r.get(k) for k in ("ok", "applied", "via", "error")
                               if k in r}
            except Exception as exc:  # noqa: BLE001
                out["omni"] = {"ok": False, "error": str(exc)[:120]}
        with self.lock:
            self.last_err = err_mean
            self.last_tick = time.time()
        self.hand_ticks += 1
        if self.hand.get("session") and self.hand_ticks % 5 == 0:
            try:
                from .tentacle import hand_bridge as HB
                st = HB.run("read_state", session=self.hand["session"])
                if st.get("ok"):
                    self.hand["state"] = st.get("state")
            except Exception:  # noqa: BLE001
                pass
        out.update({"targets": targets, "err": round(err_mean, 4),
                    "hand": {"pose": self.hand.get("pose"),
                             "ok": self.hand.get("ok"),
                             "session": self.hand.get("session"),
                             "transport": self.hand.get("transport")},
                    "phase": round(phase, 3),
                    "u": round(u, 3),
                    "latency_ms": int((time.time() - t0) * 1000)})
        return out

    # ---- 脑：后台持续调增益（不等帧） ----
    def _brain(self) -> None:
        while not self.stop:
            time.sleep(0.1)
            with self.lock:
                e = self.last_err
                self.brain_err = e
                self.brain_ticks += 1
                if e > 0.20:
                    self.kp = min(0.95, self.kp + 0.03)
                    self.kd = min(0.30, self.kd + 0.01)
                elif e < 0.04:
                    self.kp = max(0.35, self.kp - 0.02)
                    self.kd = max(0.06, self.kd - 0.005)

    def start_brain(self) -> None:
        if self.thread is None:
            self.thread = threading.Thread(target=self._brain, daemon=True)
            self.thread.start()

    def snapshot(self) -> dict:
        with self.lock:
            return {"ok": True, "mode": self.mode, "action": self.action,
                    "phase": round(time.time() - self.started, 3) if self.started else 0,
                    "kp": round(self.kp, 3), "kd": round(self.kd, 3),
                    "err": round(self.last_err, 4),
                    "frames_applied": self.samples,
                    "brain_ticks": self.brain_ticks,
                    "eye_bones": list(self.eye.keys())[:12],
                    "targets": len(self.targets),
                    "hand": self.hand,
                    "omni_plug": {"plugged": self.omni.get("plugged"),
                                  "last": self.omni.get("last")}}


CONTROL = DHControl()
CONTROL.start_brain()
