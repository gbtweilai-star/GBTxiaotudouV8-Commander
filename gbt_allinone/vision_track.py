# -*- coding: utf-8 -*-
"""vision_track -- 跨帧跟踪同一目标（零依赖，不装 supervision）

背景：19 位里的 `track` 一直缺 `supervision`（roboflow 的关联库）。
但跟踪的核心只是「上一帧的框 ↔ 这一帧的框怎么配对」，是**取最大值的问题**，
不需要一个 50k star 的库来兜。这里用贪心 IoU 关联实现，纯计算、零依赖。

用法两种：
  ① `update_boxes([框...])` —— 只做关联（调用方自己有检测结果时用这个）
  ② `track(frames=[图...])` —— 内部逐帧 detect 再关联（拿现成的 vision_detect）

── 为什么用贪心而不是匈牙利 ──
几十个框、IoU 阈值 0.3 的场景，贪心与最优解差异极小，但代码少一个数量级。
真到需要最优匹配的规模（上百目标），再换也不迟 —— 现在不提前复杂化。

── 铁律 ──
1. **只回 id 与坐标**，绝不回图。
2. **不硬凑**：IoU 不过阈值就是新目标，不回「大概还是它」。
3. 状态是**进程内**的；调用方要跨进程续跟，自己存 boxes + ids 再喂回来。
"""
from __future__ import annotations

import threading

_LOCK = threading.Lock()
_STATE = {"next_id": 1, "tracks": {}}      # id -> 上一帧的框


def _iou(a: dict, b: dict) -> float:
    ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
    bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]
    ix = max(0, min(ax2, bx2) - max(a["x"], b["x"]))
    iy = max(0, min(ay2, by2) - max(a["y"], b["y"]))
    inter = ix * iy
    if inter <= 0:
        return 0.0
    union = a["w"] * a["h"] + b["w"] * b["h"] - inter
    return inter / float(union + 1e-9)


def _associate(prev: dict, curr: list, iou_thr: float):
    """贪心 IoU 关联：回 (匹配对, 未匹配的旧 id, 未匹配的新框下标)。"""
    pairs = []
    for pid, pb in prev.items():
        for ci, cb in enumerate(curr):
            s = _iou(pb, cb)
            if s >= iou_thr:
                pairs.append((s, pid, ci))
    pairs.sort(key=lambda t: -t[0])

    used_p, used_c, matched = set(), set(), []
    for s, pid, ci in pairs:
        if pid in used_p or ci in used_c:
            continue
        used_p.add(pid)
        used_c.add(ci)
        matched.append((pid, ci, round(s, 3)))

    lost = [pid for pid in prev if pid not in used_p]
    new = [ci for ci in range(len(curr)) if ci not in used_c]
    return matched, lost, new


def update_boxes(boxes, iou_thr: float = 0.30, max_age: int = 3,
                 reset: bool = False) -> dict:
    """喂一帧的框，回带 track_id 的框。跨帧调用同一函数即可。"""
    if reset:
        with _LOCK:
            _STATE["next_id"] = 1
            _STATE["tracks"] = {}

    if boxes is None:
        return {"ok": False, "reason": "需要 boxes：本帧的框列表 [{x,y,w,h}...]"}

    cur = []
    for b in boxes:
        try:
            cur.append({"x": int(b["x"]), "y": int(b["y"]),
                        "w": int(b["w"]), "h": int(b["h"]),
                        "label": b.get("label") or b.get("name") or ""})
        except (KeyError, TypeError, ValueError):
            return {"ok": False, "reason": "框格式不对，需要 {x,y,w,h} 四个整数字段"}

    with _LOCK:
        prev = _STATE["tracks"]
        matched, lost, new = _associate(prev, cur, float(iou_thr))

        out = []
        next_tracks = {}
        for pid, ci, s in matched:
            b = dict(cur[ci])
            b["track_id"] = pid
            b["iou"] = s
            b["age"] = int((prev.get(pid) or {}).get("age", 0)) + 1
            bo = dict(b)
            next_tracks[pid] = bo
            out.append(b)

        for ci in new:
            pid = _STATE["next_id"]
            _STATE["next_id"] += 1
            b = dict(cur[ci])
            b["track_id"] = pid
            b["iou"] = None
            b["age"] = 0
            next_tracks[pid] = dict(b)
            out.append(b)

        # 丢失的目标保留 max_age 帧，超时才真的移除（避免抖一下就换 id）
        keep_lost = []
        for pid in lost:
            pb = dict(prev[pid])
            pb["age"] = int(pb.get("age", 0)) + 1
            if pb["age"] <= int(max_age):
                next_tracks[pid] = pb
                keep_lost.append(pid)

        _STATE["tracks"] = next_tracks
        alive = len(next_tracks)

    out.sort(key=lambda b: b["track_id"])
    return {"ok": True, "count": len(out), "tracks": out,
            "matched": len(matched), "new": len(new), "lost": keep_lost,
            "alive": alive, "iou_thr": float(iou_thr),
            "note": "age=已连续跟踪帧数；lost 里的 id 会在 max_age 帧内保留"}


def track(frames, iou_thr: float = 0.30, conf: float = 0.35,
          max_age: int = 3) -> dict:
    """给一串图片路径，逐帧 detect 再关联 —— 「这还是刚才那个东西吗」。"""
    if not frames:
        return {"ok": False, "reason": "需要 frames：图片路径列表"}
    from . import vision_detect as VD

    update_boxes([], reset=True)
    rows = []
    for i, path in enumerate(frames):
        d = VD.run("detect", image=path, conf=conf)
        if not d.get("ok"):
            rows.append({"frame": i, "image": path, "ok": False,
                         "reason": d.get("reason") or d.get("error")})
            continue
        boxes = [x for x in (d.get("detections") or d.get("items") or [])]
        r = update_boxes(boxes, iou_thr=iou_thr, max_age=max_age)
        rows.append({"frame": i, "image": path, "ok": True,
                     "count": r.get("count"), "tracks": r.get("tracks"),
                     "new": r.get("new"), "lost": r.get("lost")})

    ids = sorted({t["track_id"] for row in rows for t in (row.get("tracks") or [])})
    return {"ok": True, "frames": len(frames), "track_ids": ids,
            "id_count": len(ids), "rows": rows,
            "note": "同一 track_id 跨帧出现 ⇒ 同一个目标；id 变化说明 IoU 掉了（目标移动太快或换了东西）"}


def status() -> dict:
    with _LOCK:
        alive = len(_STATE["tracks"])
        nid = _STATE["next_id"]
    return {"ok": True, "backend": "贪心 IoU 关联 · 零依赖（不装 supervision）",
            "alive_tracks": alive, "next_id": nid,
            "ops": ["update", "track", "status", "reset"],
            "limits": "进程内状态；贪心匹配在目标极密集时不如匈牙利最优；不做外观特征（纯几何）"}


def run(op: str = "status", **kw) -> dict:
    o = str(op or "status").strip()
    if o in ("status", "health"):
        return status()
    if o in ("reset", "clear"):
        return update_boxes([], reset=True)
    if o in ("update", "boxes", "step"):
        return update_boxes(kw.get("boxes") or [], float(kw.get("iou_thr") or 0.30),
                            int(kw.get("max_age") or 3), bool(kw.get("reset")))
    if o in ("track", "frames"):
        return track(kw.get("frames") or [], float(kw.get("iou_thr") or 0.30),
                     float(kw.get("conf") or 0.35), int(kw.get("max_age") or 3))
    return {"ok": False, "reason": "未知 op: %s" % o,
            "supported": ["update", "track", "status", "reset"]}
