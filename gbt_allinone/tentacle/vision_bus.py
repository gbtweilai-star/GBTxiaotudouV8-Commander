# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 视觉传输总线（Vision Bus）——原生视觉的传输进化。

定位（Owner 定调 2026-09-11）：视觉也是传输——眼睛的每一帧都应可缓存、可对比、
可定位、可回放、可进万能插流水线。视觉数据不再是孤立快照，而是框架传输总线上的一等公民。

能力：
  snapshot        带指纹的视觉快照（同画面命中缓存零成本复用）
  diff_regions    变化区域定位（网格哈希 → 变化矩形列表，非只说"变了"）
  stream_record   视觉流记录（帧哈希时间线落 store，可回放可统计）
  stream_replay   视觉流回放（帧时间线 + 变化段提取）
"""

import base64
import hashlib
import json
import time
from pathlib import Path

_BASE = Path(__file__).resolve().parent          # tentacle/


def _resolve_store() -> Path:
    """store 基址单一来源（O35 扩展）：视觉总线可能被 spec_from_file_location
    独立加载（无包上下文），故按 [包内导入 -> 同目录 _paths.py -> env/默认] 三级回退。"""
    try:
        from .. import _paths as _p          # gbt_allinone.tentacle.vision_bus
        return Path(_p.STORE_DIR)
    except Exception:
        pass
    try:
        import importlib.util as _ilu
        _spec = _ilu.spec_from_file_location(
            "gbt_vision_bus__paths", Path(__file__).resolve().parents[1] / "_paths.py")
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        return Path(_mod.STORE_DIR)
    except Exception:
        pass
    _env = __import__("os").getenv("GBT_STORE_DIR")
    return Path(_env).resolve() if _env else (_BASE.parent / "store")


_STORE = _resolve_store()
_VISION_DIR = _STORE / "vision"
_STREAM_FILE = _VISION_DIR / "streams.json"
_CACHE_FILE = _STORE / "transfer_cache.json"

# 变化定位网格（把画面切成 GxG 块，逐块哈希对比）
GRID = 4


def _b64_decode(b64):
    return base64.b64decode(b64)


def _sha(b) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


def _audit(event, meta):
    # 防御式导入：omni_* 层以 spec_from_file_location 独立加载（无包上下文），
    # 相对导入不可用——多形态尝试，任一成功即可。
    import importlib
    for modpath in ("gbt_allinone.store", "store"):
        try:
            mod = importlib.import_module(modpath)
            mod.audit(event, meta)
            return
        except Exception:
            continue


# ── 视觉快照缓存（同画面零成本复用）──

def _full_frame(eye, region=None, fmt=None):
    """全屏帧采集：绕过增量 delta 局部图（局部图会破坏感知指纹与对比语义）。

    _screen_capture 是 omni_core 的模块级函数——先经实例取用，
    兜底按模块寻址（omni_* 层的加载形态多样）。
    """
    fn = getattr(eye, "_screen_capture", None)
    if fn is None:
        import importlib as _il
        for mp in ("gbt_allinone.tentacle.omni_core", "omni_core"):
            try:
                fn = getattr(_il.import_module(mp), "_screen_capture")
                break
            except Exception:
                continue
    if fn is None:
        return eye.see(region)
    try:
        if fmt:
            return fn(region, fmt=fmt, incremental=False)
        return fn(region, incremental=False)
    except TypeError:
        return fn(region)


_VISION_MISSING = ("display", "frame_source")


def _refuse(cap, action: str) -> dict:
    """R-H295 · ⑥ G1/G2：视觉面的**结构化"做不了"**。

    《触手覆盖矩阵.md》§三 实测眼组「能报做不了 0/5」—— 本文件此前是 `ok:False` 原样返回，
    或直接 `cap["image_base64"]` 取键（取不到就 KeyError）。调用方分不清
    "没显示 / 没帧源 / 形状异常"。失败一律经这里，形状与门禁的 denied 同族。
    """
    cap = cap if isinstance(cap, dict) else {}
    return {
        "ok": False,
        "unavailable": True,
        "denied": False,
        "rule": "vision_bus_cannot_capture",
        "action": action,
        "missing": list(_VISION_MISSING),
        "why": str(cap.get("error") or cap.get("why") or "取帧失败（原因未报）")[:200],
        "cap": cap,
        "note": "视觉总线做不了时结构化上报：缺什么写在 missing 里，不抛 KeyError。",
    }


def _require_frame(cap, action: str):
    """成功返回 (cap, None)；失败或形状异常返回 (None, 结构化拒绝)。"""
    if not isinstance(cap, dict) or not cap.get("ok"):
        return None, _refuse(cap, action)
    if not cap.get("image_base64"):
        return None, _refuse({"error": "取帧成功但无 image_base64（形状异常）"}, action)
    return cap, None


def snapshot(eye, region=None, ttl=60):
    """带缓存的视觉快照：画面指纹命中缓存则直接复用（不重新截屏）。

    返回: {ok, cached, fingerprint, size, kb, image_base64, ...}
    """
    cap, refusal = _require_frame(_full_frame(eye, region), "snapshot")
    if refusal:
        return refusal
    # R-H295：`_ahash` 要把 base64 解码成图再算感知指纹 —— **帧损坏/截断时它抛 OSError**，
    # 而这里原来没有任何保护：一帧坏了就把整条视觉路径打崩，且不带分类。
    # 实测就是这么炸的（`OSError: broken data stream when reading image file`）。
    try:
        fp = _ahash(cap["image_base64"])[:16]   # 感知指纹（编码噪声免疫）
    except Exception as exc:  # noqa: BLE001
        return _refuse({"error": "帧无法解码（损坏/截断）: %s: %s"
                                 % (type(exc).__name__, str(exc)[:80])}, "snapshot")
    result = dict(cap)
    result["fingerprint"] = fp

    # 查传输缓存（视觉快照走同一总线）
    cache_file = _STORE / "transfer_cache.json"
    if cache_file.exists():
        try:
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
            hit = cache.get("vision:" + fp)
            if hit and (time.time() - hit.get("ts", 0)) <= ttl:
                result["cached"] = True
                result["cache_age_s"] = round(time.time() - hit["ts"], 1)
                return result
        except Exception:
            pass

    # 写入缓存（存元数据，不存图本体——图可由指纹溯源）
    try:
        cache = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}
        cache["vision:" + fp] = {"ts": time.time(),
                                 "result": {"ok": True, "size": cap.get("size"),
                                            "kb": cap.get("image_kb"), "vision_snapshot": True}}
        if len(cache) > 500:
            for k in sorted(cache, key=lambda k: cache[k].get("ts", 0))[:100]:
                cache.pop(k, None)
        _STORE.mkdir(parents=True, exist_ok=True)
        # 🔴 2026-10-13 修（selfscan P0 的根因 · 治本那一刀）：
        #    实测残件 `store/transfer_cache.json` 尾部多出 **3 个 `}`**（"合法 JSON + 多余数据"）。
        #    本句用的是 `json.dumps`，本身不会多括号 ⇒ 真因是**同一个缓存文件被两处各读-改-写**
        #    （`engine.py:_CACHE_FILE` 与 `vision_bus.py` 共用一份），无锁并发下写出"半截 + 残留"。
        #    修法两条一起上：① **原子写**（先写 .tmp 再 os.replace，读者永远看不到半截）；
        #    ② **写完读回自证**（fail-closed：读不回就抛，由下面的 except 记 cached=None，不糊弄）。
        _tmp = cache_file.with_name(cache_file.name + ".tmp")
        _tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        json.loads(_tmp.read_text(encoding="utf-8"))       # 读回自证：解析不了就当场抛
        _tmp.replace(cache_file)                            # 原子替换（Path.replace，本文件没 import os）
        result["cached"] = False
    except Exception:
        result["cached"] = None
    _audit("vision_snapshot", {"fingerprint": fp, "size": cap.get("size"), "kb": cap.get("image_kb")})
    return result


# ── 变化区域定位（网格哈希）──

def _ahash(image_b64, size=16):
    """感知哈希（aHash）：解码像素 → 灰度 → 缩放到 size×size → 均值二值化 → 64位指纹。

    JPEG 编码噪声在此被抹平（灰度+缩放+二值化），同画面指纹稳定。
    """
    import base64 as _b64
    import io as _io
    from PIL import Image as _PILImage
    raw = _b64.b64decode(image_b64)
    img = _PILImage.open(_io.BytesIO(raw))
    g = img.convert("L").resize((size, size))
    px = list(g.getdata())
    avg = sum(px) / len(px)
    bits = "".join("1" if v > avg else "0" for v in px)
    return bits


def _ahash_blocks(image_b64, grid=GRID, cell=16):
    """像素级网格哈希：把画面均分为 grid×grid 块，每块独立 aHash → 编码噪声免疫的块对比。"""
    import base64 as _b64
    import io as _io
    from PIL import Image as _PILImage
    raw = _b64.b64decode(image_b64)
    img = _PILImage.open(_io.BytesIO(raw)).convert("L")
    w, h = img.size
    hashes = []
    for r in range(grid):
        for cix in range(grid):
            box = (cix * w // grid, r * h // grid, (cix + 1) * w // grid, (r + 1) * h // grid)
            cell_img = img.crop(box).resize((cell, cell))
            px = list(cell_img.getdata())
            avg = sum(px) / len(px) if px else 0
            # 绝对参考（128 亮度阈值）—— 块间可比，才能检出"白底出现黑块"
            bits = "".join("1" if v > 128 else "0" for v in px)
            hashes.append((round(avg, 1), hash(bits)))
    return hashes


def _grid_hashes(image_b64, grid=GRID):
    """兼容旧名：现返回感知块哈希列表（像素级，编码噪声免疫）。"""
    return _ahash_blocks(image_b64, grid)


def diff_regions(current_b64, previous_b64, grid=GRID):
    """变化区域定位：返回变化块列表（含归一化矩形）。

    返回: {ok, changed, changed_ratio, regions: [{row, col, rect}, ...]}
    rect 为归一化坐标 (0~1)：{x, y, w, h}
    """
    try:
        cur = _grid_hashes(current_b64, grid)
        prev = _grid_hashes(previous_b64, grid)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:100]}

    changed_blocks = []
    for i, (a, b) in enumerate(zip(cur, prev)):
        if a != b:
            row, col = divmod(i, grid)
            changed_blocks.append({
                "row": row, "col": col,
                "rect": {"x": round(col / grid, 3), "y": round(row / grid, 3),
                          "w": round(1 / grid, 3), "h": round(1 / grid, 3)},
            })
    changed = bool(changed_blocks)
    return {"ok": True, "changed": changed,
            "changed_blocks": len(changed_blocks),
            "changed_ratio": round(len(changed_blocks) / (grid * grid), 3),
            "regions": changed_blocks}


def diff_with_previous(eye, grid=GRID):
    """与上一次快照对比 + 变化区域定位（内部维护基准帧）。"""
    cur, refusal = _require_frame(_full_frame(eye), "diff_with_previous")
    if refusal:
        return refusal
    try:
        cur_fp = _ahash(cur["image_base64"])[:16]   # 感知指纹
    except Exception as exc:  # noqa: BLE001
        return _refuse({"error": "帧无法解码（损坏/截断）: %s: %s"
                                 % (type(exc).__name__, str(exc)[:80])}, "diff_with_previous")
    prev_fp = getattr(eye, "_vision_last_fp", None)
    prev_b64 = getattr(eye, "_vision_last_b64", None)

    result = {"ok": True, "current_fingerprint": cur_fp}
    if prev_b64:
        d = diff_regions(cur["image_base64"], prev_b64, grid)
        result.update(d)
        result["previous_fingerprint"] = prev_fp
    else:
        result["note"] = "首次快照，无对比基准"

    eye._vision_last_fp = cur_fp
    eye._vision_last_b64 = cur["image_base64"]
    _audit("vision_diff", {"fingerprint": cur_fp, "changed": result.get("changed"),
                            "changed_blocks": result.get("changed_blocks")})
    return result


# ── 视觉流记录与回放 ──

def stream_record(eye, duration_s=10, interval_ms=500, stream_name=None):
    """视觉流记录：帧时间线（指纹+变化块数）落 store，可回放可统计。"""
    name = stream_name or time.strftime("%Y%m%d-%H%M%S")
    end = time.time() + duration_s
    frames = []
    last_fp = None
    while time.time() < end:
        t0 = time.time()
        cap = _full_frame(eye)
        if not cap.get("ok"):
            continue
        fp = _ahash(cap["image_base64"])[:16]
        changed_vs_prev = None if last_fp is None else (fp != last_fp)
        frames.append({"ts": time.time(), "fingerprint": fp,
                        "kb": cap.get("image_kb"), "changed": changed_vs_prev})
        last_fp = fp
        elapsed = (time.time() - t0) * 1000
        sleep_s = max(0, interval_ms - elapsed) / 1000
        if sleep_s > 0:
            time.sleep(sleep_s)

    changes = sum(1 for f in frames if f["changed"])
    stream = {"name": name, "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "duration_s": duration_s, "interval_ms": interval_ms,
              "frames": len(frames), "changes": changes,
              "fps": round(len(frames) / max(duration_s, 0.1), 1),
              "timeline": frames}
    _VISION_DIR.mkdir(parents=True, exist_ok=True)
    (_VISION_DIR / f"{name}.json").write_text(
        json.dumps(stream, ensure_ascii=False), encoding="utf-8")
    _audit("vision_stream", {"name": name, "frames": len(frames), "changes": changes})
    return {"ok": True, "name": name, "frames": len(frames), "changes": changes,
            "fps": stream["fps"], "file": str(_VISION_DIR / f"{name}.json")}


def stream_replay(name=None, limit=50):
    """视觉流回放：读回帧时间线 + 变化段提取。"""
    if not _VISION_DIR.exists():
        return {"ok": False, "error": "无视觉流记录"}
    if name:
        f = _VISION_DIR / f"{name}.json"
        if not f.exists():
            return {"ok": False, "error": f"流不存在: {name}"}
        streams = [f]
    else:
        streams = sorted(_VISION_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:1]
        if not streams:
            return {"ok": False, "error": "无视觉流记录"}
    data = json.loads(streams[0].read_text(encoding="utf-8"))
    timeline = data.get("timeline", [])
    # 变化段提取（连续 changed=True 的帧区间）
    segments, cur = [], None
    for f in timeline:
        if f.get("changed"):
            if cur is None:
                cur = {"start": f["ts"], "frames": 1}
            else:
                cur["frames"] += 1
        else:
            if cur is not None:
                segments.append(cur)
                cur = None
    if cur is not None:
        segments.append(cur)
    return {"ok": True, "stream": data.get("name"), "frames": data.get("frames"),
            "changes": data.get("changes"), "fps": data.get("fps"),
            "change_segments": len(segments),
            "timeline_sample": timeline[:limit]}
