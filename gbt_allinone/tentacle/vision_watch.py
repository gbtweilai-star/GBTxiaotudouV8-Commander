# -*- coding: utf-8 -*-
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 · 看电影引擎（vision_watch）——原生视觉持续流

本源: 原版 caps/vision_buffer（大脑影院）。定位不变:
  显示屏数据 → DXGI 实时帧流 → 环形缓冲 → 边看边清理 → 大脑取帧
  对齐人类视觉: 持续接收 / 滑动窗口 / 重要性评分 / 焦点输出 / 事件流

三条线程（与原版同构）:
  capture  连续采帧(默认4fps, tick门控) → 变化量评分 → 环形缓冲(默认60帧) → 事件
  stream   独立推流(默认3fps) → frame_stream 帧流上总线（压缩不拖慢采集）
  text     后台读字(默认20s) → 纯缓存读, 绝不阻塞采集/推流

⛔ 2026-09-14 P2 修复（只加不删）:
  1. 原版 _stream_loop 第490行 `continue` 之后整段推流是死代码（缩进挂在 else 里）——
     frame_stream 从未发出、streamed 恒为 0、视觉记忆沉淀与持续理解从未启动。
     本端口把推流线接活: 画面变化或≥1s 推一帧, 静止自动降频。
  2. 帧本体接入 P1 帧库（内容寻址 frame_id）——推出去的画面可溯源、可回放。
  3. access lost 自愈保留（release + 清状态立即重建, 不走60s冷却）。
  4. 采集失败不再空转热循环; 无显卡会话时如实报 vision_failed, 不假称 running。
"""
import base64 as _b64
import ctypes
import importlib
import io
import json
import sys
import threading
import time
from pathlib import Path

try:
    import numpy
except ImportError:  # pragma: no cover - 无 numpy 时降级, 不阻断
    numpy = None

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

DEFAULT_FPS = 4              # 采集帧率（tick门控动态驱动）
DEFAULT_STREAM_FPS = 3       # 推流帧率（数据线连续帧流）
DEFAULT_MAX_FRAMES = 60      # 环形缓冲 ≈ 15s @4fps
MAX_EVENTS = 30
MAX_FRAME_BYTES = 200_000    # 单帧 b64 上限 ~150KB（护栏）
BIG_CHANGE = 15.0            # 变化量阈值 → big_change 事件
ENCODE_THRESHOLD = 2.0       # 变化量阈值 → 才编码画面
SNAPSHOT_EVERY_S = 5.0       # 周期性画面上总线（静态屏也持续送）
TEXT_REFRESH_S = 20.0        # 后台读字节流
UNDERSTAND_EVERY_S = 60.0    # 原生画面理解节流
UNDERSTAND_MIN_FREE_MB = 1200  # 推理内存门槛（原版守护曾因此崩过）

_BUFFER = {
    "running": False,
    "capture_thread": None,
    "stream_thread": None,
    "text_thread": None,
    "frames": [],            # 环形帧队列: {ts, score, kb, delta, engine, image_base64, gpu_ts}
    "events": [],            # 视觉事件队列
    "max_frames": DEFAULT_MAX_FRAMES,
    "max_events": MAX_EVENTS,
    "fps": 0.0,
    "captured": 0,
    "cleaned": 0,            # 边看边清理计数
    "streamed": 0,           # 已推流帧计数
    "recovered": 0,          # access lost 自愈次数
    "started_at": 0.0,
    "last_raw": None,        # 最新裸帧（推流线程取它压缩）
    "last_b64": "",          # 统一编码：全链路每帧只编码一次
    "last_b64_kb": 0,
    "last_gpu_ts": None,
    "fps_target": DEFAULT_FPS,
    "stream_fps": DEFAULT_STREAM_FPS,
    "eye": None,             # 触手实例（读字契约层用）
    "lock": threading.RLock(),
}

# 可注入取帧源（测试 / 无显卡会话兜底）: () -> (frame_raw, gpu_ts)
_FRAME_SOURCE = None

_TEXT_CACHE = {"t": 0.0, "text": ""}
_TEXT_LOCK = threading.Lock()
_UNDERSTAND_LOCK = threading.Lock()
_UNDERSTAND_BUSY = False
_LAST_DESC_B64 = ""
_LAST_DESC_TS = 0.0


# ═══════════ 基础工具 ═══════════

def _import_first(candidates):
    for modpath in candidates:
        try:
            return importlib.import_module(modpath)
        except Exception:  # noqa: BLE001
            continue
    return None


def _omni_core():
    return _import_first(("gbt_allinone.tentacle.omni_core", "omni_core"))


def _capture_diagnostic() -> dict:
    """Read-only capture boundary diagnostic, safe to call from status/watchdog."""
    try:
        mod = _import_first(("gbt_allinone.tentacle.capture_environment",
                             "tentacle.capture_environment",
                             "capture_environment"))
        if mod is None:
            return {"capture_ready": False, "backends": {}, "likely_failure_roots": ["capture_environment module not found"]}
        return mod.status()
    except Exception:
        return {}


def _tx_visual(payload: dict, priority: str = "normal") -> None:
    """视觉事件入传输总线（眼睛→视神经→大脑）。失败静默: 传输层绝不阻断采集。"""
    mod = _import_first(("gbt_allinone.tentacle.brain.tentacle_transmission",
                         "brain.tentacle_transmission", "tentacle_transmission"))
    if mod is None:
        return
    try:
        mod.transmit(payload, source="vision_watch", channel="visual", priority=priority)
    except Exception:  # noqa: BLE001
        pass


def _vision_bus():
    return _import_first(("gbt_allinone.tentacle.vision_bus", "vision_bus"))


def _visual_memory():
    return _import_first((
        "gbt_allinone.tentacle.brain.visual_memory",
        "brain.visual_memory",
        "visual_memory",
    ))


def _remember_frame(payload: dict) -> dict:
    mod = _visual_memory()
    if mod is None:
        return {"ok": False, "error": "visual_memory unavailable"}
    try:
        return mod.remember(payload)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:120]}


def _mem_system_free_mb(need_mb: int) -> bool:
    """系统空闲物理内存 ≥ need_mb → True（查不到→放行，不误伤）"""
    try:
        class _MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = _MS()
        m.dwLength = ctypes.sizeof(_MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return (m.ullAvailPhys // (1024 * 1024)) >= need_mb
    except Exception:  # noqa: BLE001
        return True


def _encode_raw(frame_raw, max_px: int = 360, quality: int = 60) -> dict:
    """裸帧 → 缩略 JPEG b64（负载控制 + 上限护栏）"""
    try:
        from PIL import Image
        img = Image.fromarray(frame_raw)
        img.thumbnail((max_px, max_px))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        raw = buf.getvalue()
        if len(raw) > MAX_FRAME_BYTES:
            img.thumbnail((240, 240))
            buf2 = io.BytesIO()
            img.save(buf2, format="JPEG", quality=55)
            raw = buf2.getvalue()
        return {"frame_b64": _b64.b64encode(raw).decode(), "frame_kb": len(raw) // 1024,
                "frame_raw_bytes": raw}
    except Exception:  # noqa: BLE001
        return {"frame_b64": "", "frame_kb": 0, "frame_raw_bytes": b""}


def _persist_to_frame_store(frame_b64: str) -> dict:
    """⛔ P2×P1: 推出去的画面同步进帧库 —— 看电影的每一帧可溯源、可回放。"""
    vb = _vision_bus()
    if vb is None or not frame_b64:
        return {}
    try:
        r = vb.persist_frame(frame_b64)
        return {"frame_id": r.get("frame_id")} if r.get("ok") else {}
    except Exception:  # noqa: BLE001
        return {}


def _get_screen_text() -> str:
    """读当前屏幕文本 — 纯缓存读（后台线程刷新），绝不阻塞调用方"""
    with _TEXT_LOCK:
        return _TEXT_CACHE["text"]


def _text_refresh_loop():
    """后台读字 — 读屏契约层（UIA），独立线程不卡采集/推流"""
    while _BUFFER["running"]:
        try:
            eye = _BUFFER.get("eye")
            rt = eye.read_text_fast("active") if eye is not None else None
            if rt:
                with _TEXT_LOCK:
                    _TEXT_CACHE["text"] = (rt.get("text") or "")[:1500]
                    _TEXT_CACHE["t"] = time.time()
        except Exception:  # noqa: BLE001
            pass  # 读字不可用不阻断看电影
        time.sleep(TEXT_REFRESH_S)


def _understand_loop(frame_b64: str, frame_id: str = None):
    """原生画面理解（单飞）: 视觉皮层本地契约优先, 云视觉可用时增强语义。"""
    global _UNDERSTAND_BUSY, _LAST_DESC_B64, _LAST_DESC_TS
    try:
        if not frame_b64 or frame_b64 == _LAST_DESC_B64:
            return
        if not _mem_system_free_mb(UNDERSTAND_MIN_FREE_MB):
            return
        cortex = _import_first((
            "gbt_allinone.tentacle.brain.visual_cortex",
            "brain.visual_cortex",
            "visual_cortex",
        ))
        if cortex is None:
            return
        r = cortex.understand_screen(frame_b64, use_cache=True)
        if r.get("ok") and (r.get("description_cn") or r.get("description")):
            _LAST_DESC_B64 = frame_b64
            _LAST_DESC_TS = time.time()
            frame_ref = {"frame_id": frame_id} if frame_id else _persist_to_frame_store(frame_b64)
            payload = {
                "type": "native_vision",
                "description": str(r.get("description_cn") or r.get("description"))[:2000],
                "description_native": str(r.get("description") or "")[:2000],
                "engine": r.get("engine") or "visual-cortex-v8",
                "cached": bool(r.get("cached")),
                "fingerprint": r.get("fingerprint"),
                "text_blocks": (r.get("text_blocks") or [])[:40],
                "ok": True,
            }
            payload.update(frame_ref)
            _tx_visual(payload, priority="normal")
            _remember_frame({
                "channel": "vision_native",
                "image_base64": frame_b64,
                "description": payload["description"],
                "frame_id": payload.get("frame_id") or frame_ref.get("frame_id"),
                "text": "\n".join(
                    str(block.get("text", ""))
                    for block in payload.get("text_blocks") or []
                    if isinstance(block, dict)
                ),
                "ocr": {
                    "ok": bool(payload.get("text_blocks")),
                    "text": "\n".join(
                        str(block.get("text", ""))
                        for block in payload.get("text_blocks") or []
                        if isinstance(block, dict)
                    ),
                    "block_count": len(payload.get("text_blocks") or []),
                },
            })
    except Exception:  # noqa: BLE001
        pass  # 容错: 画面理解不可用不阻断看电影
    finally:
        with _UNDERSTAND_LOCK:
            _UNDERSTAND_BUSY = False


# ═══════════ 采集循环 ═══════════

def _grab_capture():
    """取一帧裸画面。返回 (frame_raw, gpu_ts, tick, cam)。

    生产路径: dxcam 最新帧（带显卡呈现时间戳）；
    注入路径: _FRAME_SOURCE（测试 / 无桌面会话兜底），不改变生产行为。
    """
    if _FRAME_SOURCE is not None:
        r = _FRAME_SOURCE()
        if isinstance(r, tuple):
            return r[0], (r[1] if len(r) > 1 else None), None, None
        return r, None, None, None
    mod = _omni_core()
    if mod is None:
        return None, None, None, None
    cam = mod._get_dxcam()
    if not cam:
        return None, None, None, None
    frame_raw, gpu_ts = None, None
    try:
        r = cam.get_latest_frame(with_timestamp=True)
        if isinstance(r, tuple) and r[0] is not None:
            frame_raw, gpu_ts = r
        elif r is not None and not isinstance(r, tuple):
            frame_raw = r
    except TypeError:
        frame_raw = cam.get_latest_frame()      # 旧版 dxcam 无 with_timestamp
    tick = None
    try:
        tick = int(cam.latest_frame_ticks or 0)
    except Exception:  # noqa: BLE001
        tick = None
    return frame_raw, gpu_ts, tick, cam


def _capture_loop(interval: float):
    """后台采集循环 — 裸帧持续采, 变化量评分, 边看边清理, access lost 自愈"""
    last_time = time.time()
    snap_last = 0.0
    last_tick = None
    recover_err_ts = 0.0
    while _BUFFER["running"]:
        try:
            t0 = time.time()
            frame_raw, gpu_ts, tick, cam = None, None, None, None
            try:
                frame_raw, gpu_ts, tick, cam = _grab_capture()
            except Exception as e_cam:  # noqa: BLE001
                # access lost 自愈: 桌面切换/分辨率变更/独占全屏/会话断开
                #   → release + 清模块状态, 下轮立即重建（DisplayRecovery式, 不等60s冷却）
                try:
                    mod = _omni_core()
                    if mod is not None:
                        cam_r = getattr(mod, "_DXCAM", None)
                        if cam_r is not None:
                            try:
                                cam_r.release()
                            except Exception:  # noqa: BLE001
                                pass
                        mod._DXCAM = None
                        mod._DXCAM_FAIL_TS = 0.0
                        mod._DXCAM_BASE = None
                        mod._DXCAM_BASE_TIME = 0
                    with _BUFFER["lock"]:
                        _BUFFER["recovered"] += 1
                    if time.time() - recover_err_ts > 60:
                        recover_err_ts = time.time()
                        _tx_visual({"type": "vision_recovered", "ok": True,
                                    "error": str(e_cam)[:100]}, priority="high")
                except Exception:  # noqa: BLE001
                    pass  # 容错: 非关键路径

            if frame_raw is None:
                # 无帧: 心跳计数 + 退避（不空转热循环）
                with _BUFFER["lock"]:
                    _BUFFER["captured"] += 1
                time.sleep(max(interval, 0.25))
                continue

            # tick门控: 显卡未呈现新帧 → 零计算跳过（静态屏连 diff 都省）
            if last_tick is not None and tick and tick == last_tick:
                with _BUFFER["lock"]:
                    _BUFFER["captured"] += 1
                if time.time() - snap_last >= SNAPSHOT_EVERY_S:
                    snap_last = time.time()
                    with _BUFFER["lock"]:
                        sb64, skb = _BUFFER["last_b64"], _BUFFER["last_b64_kb"]
                    if sb64:
                        ev = {"type": "screen_snapshot", "text": _get_screen_text(),
                              "score": 10, "ok": True, "gpu_ts": gpu_ts,
                              "frame_b64": sb64, "frame_kb": skb}
                        ev.update(_persist_to_frame_store(sb64))
                        _tx_visual(ev, priority="normal")
                time.sleep(interval * 3)   # 静态省电
                continue
            if tick:
                last_tick = tick

            # 变化量评分: 1/4 分辨率 diff（阈值语义不变, 计算量 ÷4）
            diff = None
            prev_raw = _BUFFER.get("last_raw")
            if numpy is not None and prev_raw is not None:
                try:
                    if prev_raw.shape == frame_raw.shape:
                        diff = float(numpy.abs(numpy.subtract(
                            prev_raw[::2, ::2], frame_raw[::2, ::2],
                            dtype=numpy.int16)).mean())
                except Exception:  # noqa: BLE001
                    diff = 50.0
            if diff is None:
                diff = 50.0
            score = min(100, int(diff * 20)) if diff > 0.5 else 10

            # 画面有实质变化才编码（静态屏不重复编码相同像素）
            b64, kb = "", 0
            if diff > ENCODE_THRESHOLD:
                enc = _encode_raw(frame_raw)
                b64, kb = enc["frame_b64"], enc["frame_kb"]
            delta = diff < ENCODE_THRESHOLD
            dt_ms = (time.time() - t0) * 1000

            with _BUFFER["lock"]:
                ts = time.time()
                _BUFFER["captured"] += 1
                _BUFFER["last_raw"] = frame_raw
                _BUFFER["last_gpu_ts"] = gpu_ts
                frame = {"ts": ts, "score": score, "kb": kb, "delta": delta,
                         "engine": "dxcam", "image_base64": b64, "gpu_ts": gpu_ts,
                         "change_score": round(diff, 2)}
                _BUFFER["frames"].append(frame)
                # 环形缓冲: 追加 + 边看边清理
                if len(_BUFFER["frames"]) > _BUFFER["max_frames"]:
                    removed = len(_BUFFER["frames"]) - _BUFFER["max_frames"]
                    _BUFFER["frames"] = _BUFFER["frames"][-_BUFFER["max_frames"]:]
                    _BUFFER["cleaned"] += removed
                if b64:
                    _BUFFER["last_b64"] = b64
                    _BUFFER["last_b64_kb"] = kb
                if diff > BIG_CHANGE:
                    _BUFFER["events"].append({"ts": ts, "type": "big_change",
                                              "score": score, "change": round(diff, 1)})
                    if len(_BUFFER["events"]) > _BUFFER["max_events"]:
                        _BUFFER["events"] = _BUFFER["events"][-_BUFFER["max_events"]:]
                now = time.time()
                if _BUFFER["started_at"] and now - last_time >= 1.0:
                    _BUFFER["fps"] = _BUFFER["captured"] / (now - _BUFFER["started_at"])
                    last_time = now

            # 大幅变化事件穿透 → 大脑实时感知（帧本体随事件走）
            if diff > BIG_CHANGE and b64:
                ev = {"type": "big_change", "score": score, "change": round(diff, 1),
                      "fps": round(_BUFFER["fps"], 1), "text": _get_screen_text(),
                      "ok": True, "gpu_ts": gpu_ts, "frame_b64": b64, "frame_kb": kb}
                ev.update(_persist_to_frame_store(b64))
                _tx_visual(ev, priority="high")

            # 周期性快照: 静态屏也持续送（大脑持续 snapshot 即看到画面随时间流动）
            if time.time() - snap_last >= SNAPSHOT_EVERY_S:
                snap_last = time.time()
                with _BUFFER["lock"]:
                    sb64 = _BUFFER["last_b64"] or b64
                    skb = _BUFFER["last_b64_kb"] or kb
                if sb64:
                    ev = {"type": "screen_snapshot", "text": _get_screen_text(),
                          "score": score, "ok": True, "gpu_ts": gpu_ts,
                          "frame_b64": sb64, "frame_kb": skb}
                    ev.update(_persist_to_frame_store(sb64))
                    _tx_visual(ev, priority="normal")

            time.sleep(max(0.0, interval - dt_ms / 1000))
        except Exception:  # noqa: BLE001
            time.sleep(interval)


# ═══════════ 推流循环（原版此处被 continue 掐死, 本端口接活）═══════════

def _stream_loop(interval: float):
    """数据线推流: 持续把最新画面推进 visual 通道 —— 连续帧流。

    对齐主机→显示屏: 显示器持续收到显卡信号, 大脑持续收到画面帧。
    推流线程独立于采集线程, 压缩不拖慢采集。
    """
    global _UNDERSTAND_BUSY
    last_push = 0.0
    last_mem = 0.0
    last_tx = 0.0
    last_tx_b64 = ""
    while _BUFFER["running"]:
        try:
            t0 = time.time()
            with _BUFFER["lock"]:
                raw = _BUFFER["last_raw"]
                ring_b64 = _BUFFER["last_b64"]
                ring_kb = _BUFFER["last_b64_kb"]
            if raw is None:
                time.sleep(min(5.0, max(1.0, interval)))   # 无新帧: 会话未就绪, 退避
                continue
            enc = ({"frame_b64": ring_b64, "frame_kb": ring_kb}
                   if ring_b64 else _encode_raw(raw))
            if not enc.get("frame_b64"):
                time.sleep(interval)
                continue
            txt = ""
            if time.time() - last_push >= 5.0:
                txt = _get_screen_text()
                last_push = time.time()
            if enc["frame_b64"] != last_tx_b64 or time.time() - last_tx >= 1.0:
                ev = {"type": "frame_stream", "frame_b64": enc["frame_b64"],
                      "frame_kb": enc["frame_kb"], "text": txt, "score": 50, "ok": True}
                ev.update(_persist_to_frame_store(enc["frame_b64"]))
                _tx_visual(ev, priority="normal")
                last_tx_b64 = enc["frame_b64"]
                last_tx = time.time()
                with _BUFFER["lock"]:
                    _BUFFER["streamed"] += 1
                if time.time() - last_mem >= 5.0:
                    try:
                        shape = raw.shape
                        width, height = int(shape[1]), int(shape[0])
                    except Exception:  # noqa: BLE001
                        width = height = 0
                    _remember_frame({
                        "channel": "vision_watch",
                        "size": [width, height],
                        "image_base64": enc["frame_b64"],
                        "frame_id": ev.get("frame_id"),
                        "text": txt,
                        "ocr": {
                            "ok": bool(txt),
                            "text": txt,
                            "block_count": 0,
                        },
                    })
                    last_mem = time.time()
                # 原生持续理解（单飞, 不堆积线程, 不阻塞推流）
                if time.time() - _LAST_DESC_TS >= UNDERSTAND_EVERY_S:
                    launch = False
                    with _UNDERSTAND_LOCK:
                        if not _UNDERSTAND_BUSY:
                            _UNDERSTAND_BUSY = True
                            launch = True
                    if launch:
                        threading.Thread(target=_understand_loop,
                                         args=(enc["frame_b64"], ev.get("frame_id")),
                                         daemon=True).start()
            dt_ms = (time.time() - t0) * 1000
            sleep_s = max(0.0, interval - dt_ms / 1000)
            if enc["frame_b64"] == last_tx_b64:
                sleep_s = interval * 6      # 静态: 降频, 变化自动恢复
            time.sleep(sleep_s)
        except Exception:  # noqa: BLE001
            time.sleep(interval)


def _first_frame_watchdog(fps: int, stream_fps: int):
    """首帧确认: 8s 窗口内落地 → vision_started; 超时 → 自停并报 vision_failed。

    不假称 running —— 无桌面会话时如实上报。
    """
    deadline = time.time() + 8.0
    while time.time() < deadline:
        with _BUFFER["lock"]:
            first_ok = _BUFFER["captured"] > 0 and bool(_BUFFER["frames"])
            thread = _BUFFER["capture_thread"]
        if first_ok:
            break
        if thread is not None and not thread.is_alive():
            break
        time.sleep(0.2)
    if first_ok:
        _tx_visual({"type": "vision_started", "fps_target": fps,
                    "stream_fps": stream_fps, "engine": "dxcam", "ok": True},
                   priority="normal")
        return
    _BUFFER["running"] = False
    diagnostic = _capture_diagnostic()
    roots = ", ".join(diagnostic.get("likely_failure_roots") or [])
    _tx_visual({"type": "vision_failed", "ok": False,
                "error": "视觉缓冲启动失败: 8s内未采集到首帧 (dxcam不可用)",
                "hint": (
                    "检查 capture_env；环境根因: " + roots
                    if roots else
                    "无桌面会话/显卡不可用时属预期; 检查 DXGI 采集链路"
                ),
                "capture_environment": diagnostic},
               priority="high")


# ═══════════ 对外 API ═══════════

def start(eye=None, fps: int = DEFAULT_FPS, stream_fps: int = DEFAULT_STREAM_FPS,
          max_frames: int = DEFAULT_MAX_FRAMES, wait_s: float = 1.0) -> dict:
    """启动看电影引擎（线程即启即返, 首帧由 watchdog 后台确认）。"""
    with _BUFFER["lock"]:
        if _BUFFER["running"]:
            return {"ok": True, "already": True, "stats": stats().get("stats", {})}
        _BUFFER.update({
            "running": True, "frames": [], "events": [], "captured": 0, "cleaned": 0,
            "streamed": 0, "recovered": 0, "started_at": time.time(),
            "last_raw": None, "last_b64": "", "last_b64_kb": 0, "fps": 0.0,
            "max_frames": max(2, int(max_frames or DEFAULT_MAX_FRAMES)),
            "fps_target": int(fps or DEFAULT_FPS),
            "stream_fps": max(1, int(stream_fps or DEFAULT_STREAM_FPS)),
            "eye": eye,
        })
    _BUFFER["capture_thread"] = threading.Thread(
        target=_capture_loop, args=(1.0 / _BUFFER["fps_target"],), daemon=True)
    _BUFFER["capture_thread"].start()
    _BUFFER["stream_thread"] = threading.Thread(
        target=_stream_loop, args=(1.0 / _BUFFER["stream_fps"],), daemon=True)
    _BUFFER["stream_thread"].start()
    _BUFFER["text_thread"] = threading.Thread(target=_text_refresh_loop, daemon=True)
    _BUFFER["text_thread"].start()

    deadline = time.time() + max(0.0, wait_s)
    first_ok = False
    while time.time() < deadline:
        with _BUFFER["lock"]:
            first_ok = bool(_BUFFER["frames"])
        if first_ok:
            break
        if not _BUFFER["capture_thread"].is_alive():
            break
        time.sleep(0.05)
    if not first_ok:
        threading.Thread(target=_first_frame_watchdog,
                         args=(_BUFFER["fps_target"], _BUFFER["stream_fps"]),
                         daemon=True).start()
        return {"ok": True, "running": True, "warming": True,
                "fps_target": _BUFFER["fps_target"],
                "stream_fps": _BUFFER["stream_fps"],
                "buffer_capacity": _BUFFER["max_frames"],
                "first_frame": False, "captured": _BUFFER["captured"]}
    _tx_visual({"type": "vision_started", "fps_target": _BUFFER["fps_target"],
                "stream_fps": _BUFFER["stream_fps"], "engine": "dxcam", "ok": True},
               priority="normal")
    return {"ok": True, "running": True, "fps_target": _BUFFER["fps_target"],
            "stream_fps": _BUFFER["stream_fps"], "buffer_capacity": _BUFFER["max_frames"],
            "first_frame": True, "captured": _BUFFER["captured"]}


def stop() -> dict:
    """停止看电影引擎（并行 join, 各 ≤1s）。"""
    _BUFFER["running"] = False
    threads = [t for t in (_BUFFER.get("capture_thread"), _BUFFER.get("stream_thread"),
                           _BUFFER.get("text_thread")) if t is not None]
    joiners = [threading.Thread(target=t.join, kwargs={"timeout": 1.0}, daemon=True)
               for t in threads]
    for j in joiners:
        j.start()
    for j in joiners:
        j.join()
    with _BUFFER["lock"]:
        out = {"captured": _BUFFER["captured"], "cleaned": _BUFFER["cleaned"],
               "fps": round(_BUFFER["fps"], 1), "streamed": _BUFFER["streamed"],
               "recovered": _BUFFER["recovered"]}
        _BUFFER["frames"] = []
        _BUFFER["events"] = []
        _BUFFER["last_raw"] = None
        _BUFFER["last_b64"] = ""
        _BUFFER["last_b64_kb"] = 0
    _BUFFER["capture_thread"] = None
    _BUFFER["stream_thread"] = None
    _BUFFER["text_thread"] = None
    return {"ok": True, "stopped": True, "stats": out}


def frame() -> dict:
    """取当前最重要帧（大脑视觉焦点: 注意力 + 边看边清理）。"""
    with _BUFFER["lock"]:
        if not _BUFFER["running"]:
            return {"ok": False, "error": "看电影引擎未启动, 先调用 vision_watch_start"}
        if not _BUFFER["frames"]:
            return {"ok": False, "error": "缓冲为空（首帧尚未落地）"}
        focus = max(_BUFFER["frames"], key=lambda f: f["score"])
        before = len(_BUFFER["frames"])
        # 边看边清理: 焦点帧取出后, 移除更早的低价值帧
        _BUFFER["frames"] = [f for f in _BUFFER["frames"] if f["ts"] >= focus["ts"] - 0.5]
        _BUFFER["cleaned"] += before - len(_BUFFER["frames"])
        remaining = len(_BUFFER["frames"])
        copy = {"ts": focus["ts"], "score": focus["score"], "kb": focus["kb"],
                "delta": focus["delta"], "engine": focus["engine"],
                "gpu_ts": focus.get("gpu_ts"), "change_score": focus.get("change_score"),
                "image_base64": focus["image_base64"]}
    copy["screen_text"] = _get_screen_text()
    copy["note"] = "视觉=DXGI帧流与显示屏同源, 大脑原生理解画面（看电影同原理）"
    ev = {"type": "focus_frame", "score": copy["score"], "kb": copy["kb"],
          "delta": copy["delta"], "engine": copy["engine"],
          "gpu_ts": copy.get("gpu_ts"), "ok": True}
    if copy["image_base64"]:
        ev.update(_persist_to_frame_store(copy["image_base64"]))
    _tx_visual(ev, priority="high")
    return {"ok": True, "frame": copy, "buffer_remaining": remaining}


def events() -> dict:
    """取视觉事件队列（取走即清, 防重复处理）"""
    with _BUFFER["lock"]:
        evts = list(_BUFFER["events"])
        _BUFFER["events"] = []
    return {"ok": True, "events": evts, "count": len(evts)}


def stats() -> dict:
    """引擎状态"""
    with _BUFFER["lock"]:
        return {"ok": True, "stats": {
            "running": _BUFFER["running"],
            "fps": round(_BUFFER["fps"], 1),
            "fps_target": _BUFFER["fps_target"],
            "captured": _BUFFER["captured"],
            "cleaned": _BUFFER["cleaned"],
            "buffer_frames": len(_BUFFER["frames"]),
            "buffer_capacity": _BUFFER["max_frames"],
            "events_pending": len(_BUFFER["events"]),
            "stream_fps": _BUFFER["stream_fps"],
            "streamed": _BUFFER["streamed"],
            "recovered": _BUFFER["recovered"],
            "uptime_s": round(time.time() - _BUFFER["started_at"], 1) if _BUFFER["started_at"] else 0,
        }}


def status() -> dict:
    return {"ok": True, "cap": "vision_watch", "status": "ready",
            "running": _BUFFER["running"],
            "capture_environment": _capture_diagnostic()}


__all__ = ["start", "stop", "frame", "events", "stats", "status",
           "DEFAULT_FPS", "DEFAULT_STREAM_FPS"]
