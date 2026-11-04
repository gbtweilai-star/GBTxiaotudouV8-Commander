# -*- coding: utf-8 -*-
"""hand_onnx_chunked_chain — 长视频分 chunk 进程回收 + 手部 IK/HAL 同链。

每个 chunk 子进程只做视觉（OpenCV DNN，模型一次），父进程拿 landmarks 做 IK + loopback。
这样长跑不会在单进程里退化，同时保留手部动作。
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORKER = os.path.join(ROOT, "tools", "model-bridge", "hand_onnx_chunk_worker.py")
PY = sys.executable


def run_video(path: str = "", frames: int = 150, chunk: int = 60, solver: str = "geometric",
              timeout: float = 300, force_limit: float = 0.0, stiffness: float = 100.0,
              external: float = 0.3, joint: str = "index_mcp", adapt: bool = False,
              k_min: float = 10.0, k_max: float = 200.0, compliance_every: int = 10,
              debounce: int = 2, dense_frames: int = 3, feedforward: bool = False,
              rate_threshold: float = 5.0, external_amp: float = 0.0, external_period: int = 20, pre_clamp: bool = True):
    from . import hand_retarget as HR
    from . import hand_bridge as HB

    # 安全闸：有力量限幅时，禁止关闭 pre-clamp 裸奔；前馈不能替代主保护
    if force_limit and not pre_clamp:
        return {"ok": False, "op": "onnx_chunked", "status": "unsafe_rejected",
                "error": "force_limit>0 时 pre_clamp 必须为 true；裸奔模式禁止进入实时写路径",
                "safety_guard": True}
    if feedforward and force_limit and not pre_clamp:
        return {"ok": False, "op": "onnx_chunked", "status": "unsafe_rejected",
                "error": "feedforward 不能替代 pre-clamp", "safety_guard": True}

    py = PY
    env = dict(os.environ)
    env["GBT_PYLIBS"] = os.path.join(ROOT, "vendor", "pylibs")
    env["GBT_HAND_MODELS"] = os.path.join(ROOT, "vendor", "hand-tracking")
    c = HB.run("connect", transport="loopback", profile="generic_20dof")
    if not c.get("ok"):
        return {"ok": False, "op": "onnx_chunked", "stage": "connect", "error": c.get("error")}
    sid = c["session"]
    chunks, lm_total, ik_ok, moved = [], 0, 0, 0
    lat, forces = [], []
    pre_clamped = adjustments = 0
    k = float(stiffness)
    contact = False
    on_count = off_count = 0
    events = []
    k_trace = []
    compliance_calls = 0
    last_event_i = -999
    last_comp_i = -999
    last_f = None
    last_f_t = None
    last_rate = 0.0
    ff_hits = 0
    t_all = time.perf_counter()
    done = 0
    try:
        while done < frames:
            n = min(chunk, frames - done)
            fd, lf = tempfile.mkstemp(prefix="handchunk-", suffix=".json", dir=os.path.join(ROOT, ".scratch", "lead"))
            os.close(fd)
            r = subprocess.run([py, "-B", "-X", "utf8", WORKER, "--video", path,
                                "--start", str(done), "--count", str(n), "--landmarks-out", lf],
                               capture_output=True, text=True, timeout=timeout, env=env)
            lines = (r.stdout or "").strip().splitlines()
            d = {}
            if lines:
                try:
                    d = json.loads(lines[-1])
                except Exception:  # noqa: BLE001
                    d = {"ok": False, "error": lines[-1][-200:]}
            chunk_lms = []
            try:
                with open(lf, encoding="utf-8") as f:
                    chunk_lms = json.load(f)
            except Exception:  # noqa: BLE001
                pass
            finally:
                try:
                    os.remove(lf)
                except OSError:
                    pass
            got = 0
            for item in chunk_lms:
                lm = item.get("landmarks") or []
                if len(lm) != 21:
                    continue
                t = time.perf_counter()
                ik = HR.run("ik" if str(solver).lower() == "ik" else "retarget",
                            landmarks=lm, model="generic_20dof", unit="rad")
                lat.append((time.perf_counter() - t) * 1000.0)
                if not ik.get("ok"):
                    continue
                ik_ok += 1
                targets = dict(ik["joints"])
                if force_limit and joint in targets:
                    fi = lm_total + got
                    ext = external
                    ext_next = external
                    if external_amp:
                        ext = external + float(external_amp) * math.sin(2.0 * math.pi * fi / max(1, int(external_period)))
                        ext_next = external + float(external_amp) * math.sin(2.0 * math.pi * (fi + 1) / max(1, int(external_period)))
                    eff_limit = force_limit
                    ext_use = ext
                    if feedforward and abs(ext_next - ext) > float(rate_threshold) * 1e-3:
                        # 位置前馈：按下一帧外力预判，不等力撞上来
                        ext_use = ext_next
                        ff_hits += 1
                    pred = k * (float(targets[joint]) - ext_use)
                    if pre_clamp and abs(pred) > eff_limit:
                        targets[joint] = max(-1.2, min(1.8, ext_use + (eff_limit / max(k, 1e-9)) * (1.0 if pred >= 0 else -1.0)))
                        pre_clamped += 1
                ok_move = HB.run("move", session=sid, targets=targets, dry_run=False).get("ok")
                if force_limit and joint in targets:
                    ct = HB.run("contact", session=sid, joint=joint, external=ext, stiffness=k)
                    f = float(ct.get("force") or 0.0)
                    now_t = time.perf_counter()
                    if last_f is not None and last_f_t is not None:
                        last_rate = (abs(f) - abs(last_f)) / max(1e-6, now_t - last_f_t)
                    last_f, last_f_t = f, now_t
                    forces.append(f)
                    on_raw = abs(f) > force_limit * 0.8
                    if debounce <= 1:
                        on = on_raw
                    else:
                        on_count = on_count + 1 if on_raw else 0
                        off_count = 0 if on_raw else off_count + 1
                        on = contact or on_count >= debounce
                        if contact and off_count >= debounce:
                            on = False
                    if on and not contact:
                        events.append({"i": lm_total + got, "type": "contact_on", "force": round(f, 3)})
                        last_event_i = lm_total + got
                    elif not on and contact:
                        events.append({"i": lm_total + got, "type": "contact_off", "force": round(f, 3)})
                        last_event_i = lm_total + got
                    contact = on
                    if abs(f) > force_limit:
                        safe = max(-1.2, min(1.8, ext + (force_limit / max(k, 1e-9)) * (1.0 if f >= 0 else -1.0)))
                        targets[joint] = safe
                        ok_move = HB.run("move", session=sid, targets=targets, dry_run=False).get("ok")
                        ct2 = HB.run("contact", session=sid, joint=joint, external=ext, stiffness=k)
                        forces.append(float(ct2.get("force") or 0.0))
                        adjustments += 1
                    if adapt:
                        fi = lm_total + got
                        # 接触事件后密调（每 2 帧），稳态降频（compliance_every）
                        interval = 2 if (fi - last_event_i) <= int(dense_frames) else max(1, int(compliance_every))
                        if fi - last_comp_i >= interval:
                            if abs(f) >= force_limit * 0.98:
                                k = max(float(k_min), k * 0.9)
                            elif not contact:
                                k = min(float(k_max), k * 1.02)
                            HB.run("compliance", session=sid, stiffness=k, damping=0.05)
                            compliance_calls += 1
                            last_comp_i = fi
                            k_trace.append(round(k, 3))
                if ok_move and HB.run("read_state", session=sid).get("ok"):
                    moved += 1
                got += 1
            lm_total += got
            chunks.append({**d, "chunk": len(chunks) + 1, "hand_frames": got})
            done += int(d.get("frames") or 0)
            if not d.get("ok"):
                break
    finally:
        HB.run("stop", session=sid)
        HB.run("disconnect", session=sid)
    el = time.perf_counter() - t_all
    return {"ok": moved > 0 and done >= frames, "op": "onnx_chunked", "frames": done,
            "hand_frames": lm_total, "ik_ok": ik_ok, "moved": moved,
            "chunks": chunks, "seconds": round(el, 2),
            "fps": round(moved / max(el, 1e-6), 2),
            "ik_ms_mean": round(sum(lat) / len(lat), 2) if lat else None,
            "force_limit": force_limit, "force_peak": round(max((abs(x) for x in forces), default=0.0), 3),
            "pre_clamped": pre_clamped, "adjustments": adjustments,
            "adapt": bool(adapt), "stiffness_start": round(float(stiffness), 2),
            "stiffness_end": round(k, 2), "contact_events": events[:20],
            "compliance_every": int(compliance_every), "compliance_calls": compliance_calls,
            "dense_frames": int(dense_frames), "debounce": int(debounce), "k_trace": k_trace[-10:],
            "feedforward": bool(feedforward), "ff_hits": ff_hits,
            "last_force_rate": round(last_rate, 3), "external_amp": float(external_amp), "external_period": int(external_period), "pre_clamp": bool(pre_clamp), "safety_guard": True,            "realtime_ok": bool(moved >= frames * 0.8 and el / max(1, frames) * 1000 <= 100),
            "boundary": "chunk 子进程视觉 + 父进程 IK/HAL + loopback；真机需标定"}



