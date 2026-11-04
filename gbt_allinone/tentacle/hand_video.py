# -*- coding: utf-8 -*-
"""hand_video — 本地手部视频 → MediaPipe 21 点 → IK → loopback 手。

支持：
- 视频时间戳 / max_fps 丢帧 / 处理延迟 / 帧年龄；
- proc_width 降分辨率（降推理成本）；
- roi=True：用上一帧手部框裁 ROI 再推理（快，但首帧要全图）；
- smooth：EMA 平滑；
- 输出 jitter_raw/smoothed、latency、roi_hits。

边界：离线视频 + loopback 仿真；摄像头未接；真机需标定。
"""
from __future__ import annotations

import time


def _map_roi(lm, ox, oy, rw, rh, fw, fh):
    out = []
    for p in lm:
        out.append([round((ox + p.x * rw) / fw, 6),
                    round((oy + p.y * rh) / fh, 6),
                    round(p.z, 6)])
    return out


def _bbox(lm, margin=0.22):
    xs = [p[0] for p in lm]; ys = [p[1] for p in lm]
    x0, x1 = max(0.0, min(xs) - margin), min(1.0, max(xs) + margin)
    y0, y1 = max(0.0, min(ys) - margin), min(1.0, max(ys) + margin)
    return x0, y0, x1, y1


def run_video(path: str = "", solver: str = "ik", stride: int = 1, smooth: float = 0.0,
              max_fps: float = 0.0, proc_width: int = 0, roi: bool = False, **_kw):
    from . import hand_vision as HV
    from . import hand_retarget as HR
    from . import hand_bridge as HB
    import cv2

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return {"ok": False, "op": "video", "status": "needs_input", "error": "打不开视频: %s" % path}
    c = HB.run("connect", transport="loopback", profile="generic_20dof")
    if not c.get("ok"):
        cap.release()
        return {"ok": False, "op": "video", "stage": "connect", "error": c.get("error")}
    sid = c["session"]
    frames = detected = moved = dropped = 0
    roi_hits = 0
    last_ik = None
    prev_raw = prev_sm = None
    box = None
    jitter_raw, jitter_sm = [], []
    process_lat, frame_age = [], []
    a = max(0.0, min(1.0, float(smooth)))
    fps_cap = max(0.0, float(max_fps))
    pw = max(0, int(proc_width))
    use_roi = bool(roi)
    last_proc_ts = None
    t0 = time.perf_counter()
    try:
        with HV._hands(static=False, complexity=0) as hands:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                frames += 1
                fh, fw = frame.shape[:2]
                ts = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                if fps_cap and last_proc_ts is not None and (ts - last_proc_ts) < (1.0 / fps_cap):
                    dropped += 1
                    continue
                if stride > 1 and (frames - 1) % stride:
                    dropped += 1
                    continue
                last_proc_ts = ts
                p_start = time.perf_counter()
                ox = oy = 0; rw, rh = fw, fh
                if use_roi and box:
                    x0, y0, x1, y1 = box
                    ox, oy = int(x0 * fw), int(y0 * fh)
                    rw, rh = max(1, int((x1 - x0) * fw)), max(1, int((y1 - y0) * fh))
                    proc = frame[oy:oy + rh, ox:ox + rw]
                    roi_hits += 1
                else:
                    proc = frame
                if pw and proc.shape[1] > pw:
                    s = pw / float(proc.shape[1])
                    proc = cv2.resize(proc, (pw, max(1, int(proc.shape[0] * s))), interpolation=cv2.INTER_AREA)
                    if not (use_roi and box):
                        # 全图等比缩放：归一化坐标不变
                        pass
                res = hands.process(cv2.cvtColor(proc, cv2.COLOR_BGR2RGB))
                if not res.multi_hand_landmarks:
                    process_lat.append((time.perf_counter() - p_start) * 1000.0)
                    frame_age.append((time.perf_counter() - t0) - ts)
                    if use_roi:
                        box = None   # ROI 丢手 → 下一帧回全图重找
                    continue
                raw = _map_roi(res.multi_hand_landmarks[0].landmark, ox, oy, rw, rh, fw, fh) if (use_roi and box) else \
                    [[round(float(p.x), 6), round(float(p.y), 6), round(float(p.z), 6)]
                     for p in res.multi_hand_landmarks[0].landmark]
                box = _bbox(raw)
                if prev_raw is not None:
                    jitter_raw.append(sum(abs(raw[i][k] - prev_raw[i][k]) for i in range(21) for k in range(3)) / 63.0)
                if prev_sm is not None:
                    jitter_sm.append(sum(abs(raw[i][k] - prev_sm[i][k]) for i in range(21) for k in range(3)) / 63.0)
                prev_raw = raw
                lm = ([[a * raw[i][k] + (1 - a) * prev_sm[i][k] for k in range(3)] for i in range(21)]
                      if (a > 0 and prev_sm is not None) else raw)
                prev_sm = lm
                detected += 1
                ik = HR.run("ik" if str(solver).lower() != "geometric" else "retarget",
                            landmarks=lm, model="generic_20dof", unit="rad")
                if not ik.get("ok"):
                    process_lat.append((time.perf_counter() - p_start) * 1000.0)
                    frame_age.append((time.perf_counter() - t0) - ts)
                    continue
                m = HB.run("move", session=sid, targets=ik["joints"], dry_run=False)
                process_lat.append((time.perf_counter() - p_start) * 1000.0)
                frame_age.append((time.perf_counter() - t0) - ts)
                if m.get("ok"):
                    moved += 1
                    last_ik = ik
    finally:
        cap.release()
        HB.run("stop", session=sid)
        HB.run("disconnect", session=sid)
    el = time.perf_counter() - t0
    lat_sorted = sorted(process_lat)
    return {"ok": bool(detected and moved), "op": "video", "video": path,
            "frames": frames, "detected_frames": detected, "moved_frames": moved,
            "dropped_frames": dropped, "max_fps": fps_cap,
            "proc_width": pw, "roi": use_roi, "roi_hits": roi_hits,
            "solver": solver, "smooth": a, "session": sid,
            "process_latency_ms_mean": round(sum(process_lat) / len(process_lat), 2) if process_lat else None,
            "process_latency_ms_p95": round(lat_sorted[int(len(lat_sorted) * 0.95)] if lat_sorted else 0, 2),
            "frame_age_s_mean": round(sum(frame_age) / len(frame_age), 3) if frame_age else None,
            "jitter_raw_mean": round(sum(jitter_raw) / len(jitter_raw), 8) if jitter_raw else None,
            "jitter_smoothed_mean": round(sum(jitter_sm) / len(jitter_sm), 8) if jitter_sm else None,
            "joint_count": len((last_ik or {}).get("joints") or {}),
            "ik_last": (last_ik or {}).get("ik"),
            "fps": round(frames / max(el, 1e-6), 2),
            "boundary": "离线视频 + loopback 仿真；摄像头未接，真机需标定"}

