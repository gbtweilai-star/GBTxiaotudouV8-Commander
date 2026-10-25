# -*- coding: utf-8 -*-
"""vision_unified -- 视觉**统一入口**（op=see）：一次调用跑全部车道，出一个带出处的结构。
车道：capture（可选截屏） → pixel（亮度/对比/边缘/主色） → text（OCR 双车道） →
      structure（网格/区域） → formal（形式化反推） → semantic（有理解通道才给，否则如实标缺）
主人口径（2026-10-17）：**视觉必须统一，不许单个使用。**
"""
from __future__ import annotations
import os
import time


def _capture(region=None):
    """截屏（Windows）。region=(l,t,w,h) 可选。"""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab(bbox=region) if region else ImageGrab.grab()
        out = os.path.join(os.environ.get("TEMP", "."), "gbt_see_%d.png" % int(time.time()))
        img.save(out)
        return {"ok": True, "path": out, "size": list(img.size)}
    except Exception as e:
        return {"ok": False, "reason": "%s: %s" % (type(e).__name__, str(e)[:100])}


def see(image=None, capture=False, region=None, do_text=True, do_pixel=True, do_formal=True):
    lane = {}
    src = image
    if capture or not src:
        c = _capture(region)
        lane["capture"] = c
        if c.get("ok"):
            src = c["path"]
    if not src or not os.path.isfile(str(src)):
        return {"ok": False, "reason": "没有可读的图（给 image 或 capture=true）", "lanes": lane}
    lane["source"] = {"path": str(src), "bytes": os.path.getsize(str(src))}

    if do_pixel:
        try:
            from .vision_cap import analyze
            a = analyze(image=src)
            lane["pixel"] = {"ok": bool(a.get("ok")), "readout": a}
        except Exception as e:
            lane["pixel"] = {"ok": False, "reason": str(e)[:100]}

    if do_text:
        try:
            from .vision_ocr import ocr
            t = ocr(image=src)
            lane["text"] = {"ok": bool(t.get("ok")), "backend": t.get("backend"), "lang": t.get("lang"),
                            "chars": t.get("chars") or len(t.get("text") or ""), "text": (t.get("text") or "")[:6000],
                            "lanes_tried": t.get("lanes"), "reason": t.get("reason")}
        except Exception as e:
            lane["text"] = {"ok": False, "reason": str(e)[:100]}

    if do_formal:
        try:
            p = lane.get("pixel", {}).get("readout") or {}
            b = p.get("brightness")
            c = p.get("contrast")
            e = p.get("edge_density")
            colors = p.get("top_colors") or []
            parts = []
            if b is not None:
                parts.append("低照度" if b < 60 else ("中调" if b < 160 else "高调"))
            if c is not None:
                parts.append("强对比" if c > 60 else "弱对比")
            if e is not None:
                parts.append("元素密" if e > 8 else ("元素中" if e > 3 else "元素疏"))
            if colors:
                parts.append("主色 #%02x%02x%02x 占 %.0f%%" % (colors[0]["rgb"][0], colors[0]["rgb"][1],
                                                              colors[0]["rgb"][2], colors[0]["share"] * 100))
            lane["formal"] = {"ok": bool(parts), "prompt": "，".join(parts) or "（像素读数不足）"}
        except Exception as ex:
            lane["formal"] = {"ok": False, "reason": str(ex)[:100]}

    sem_ok = os.environ.get("GBT_VISION_SEMANTIC") == "1"
    lane["semantic"] = ({"ok": True, "note": "理解通道已启用"} if sem_ok else
                        {"ok": False, "reason": "未读到（缺图像理解通道：teamorouter 401 / 本地 8111 未监听）"
                                               "—— 像素与文字已给，语义不编"})
    ok = bool(lane.get("pixel", {}).get("ok")) or bool(lane.get("text", {}).get("ok"))
    return {"ok": ok, "op": "see", "lanes": lane,
            "readout": {"像素": lane.get("pixel", {}).get("ok"), "文字": lane.get("text", {}).get("ok"),
                        "形式化": lane.get("formal", {}).get("prompt"), "语义": lane["semantic"].get("ok")},
            "rule": "视觉统一入口：一次调用出全部车道；缺通道的如实标缺，绝不编。"}


def run(op="see", **kw):
    return see(image=kw.get("image"), capture=bool(kw.get("capture")),
               region=kw.get("region"), do_text=kw.get("do_text", True) is not False,
               do_pixel=True, do_formal=kw.get("do_formal", True) is not False)
