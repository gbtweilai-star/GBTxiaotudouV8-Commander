# -*- coding: utf-8 -*-
# gbt-capability: none  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""对话附图（chat_image）—— 把聊天里 `+` 附图接成「真看见」。

定位：只做**本地视觉读数**（PIL/numpy，零出网、零写盘），给 `/api/chat` 用：
  · 用户只想看图（无文字 / 「看看这张图」）⇒ 直接回本地视觉读数；
  · 用户带问题附图 ⇒ 把读数当上下文拼进对话（模型能读到「附图多大/多亮/主色」）；
  · 云端语义识图仍走 `vision op=cloud`（需配置），本件不假装会识别语义。

数据入参兼容：data URL（`data:image/...;base64,...`）· base64 串 · 路径/bytes（转交 vision_cap）。
边界：单图 ≤ 8MB；读不出就如实报错，不编。
"""
from __future__ import annotations

import base64
import re

MAX_BYTES = 8 * 1024 * 1024
_IMG_ASK_RX = re.compile(
    r"(看图|看下|看看|看一眼|图片|照片|图像|图里|画面|截图|分析.*图|描述.*图|"
    r"是什么|什么内容|里面.*什么)", re.I)


def _data_url_bytes(data_url: str):
    try:
        head, b64 = str(data_url).split(",", 1)
        return head, base64.b64decode(b64)
    except Exception:                                            # noqa: BLE001
        return "", b""


def _brief(r: dict) -> str:
    size = r.get("size") or [0, 0]
    bits = ["附图：%sx%s" % (size[0], size[1])]
    if r.get("format"):
        bits.append("格式 %s" % r.get("format"))
    if r.get("brightness") is not None:
        bits.append("亮度 %s" % r.get("brightness"))
    if r.get("contrast") is not None:
        bits.append("对比度 %s" % r.get("contrast"))
    if r.get("edge_density") is not None:
        bits.append("边缘密度 %s" % r.get("edge_density"))
    cols = r.get("top_colors") or []
    if cols:
        try:
            c0 = cols[0].get("rgb") or []
            if len(c0) == 3:
                bits.append("主色 #%02x%02x%02x（占 %.0f%%）" % (
                    int(c0[0]), int(c0[1]), int(c0[2]),
                    100.0 * float(cols[0].get("share") or 0)))
        except Exception:                                        # noqa: BLE001
            pass
    return " · ".join(bits)


def looks_image_question(text: str) -> bool:
    """这句话是不是在问图（带图时用来决定回读数还是回对话模型）。"""
    return bool(_IMG_ASK_RX.search(str(text or "")))


def analyze(image) -> dict:
    """附图 → 本地视觉读数。返回 {ok, brief, analysis} 或如实报错。"""
    if image in (None, "", b""):
        return {"ok": False, "error": "user_error: 没有收到图片", "missing": ["image"]}
    raw = image
    if isinstance(image, str) and image.startswith("data:"):
        head, raw = _data_url_bytes(image)
        if not head:
            return {"ok": False, "error": "user_error: data URL 解不开", "missing": ["image"]}
    nbytes = len(raw) if isinstance(raw, (bytes, bytearray)) else len(str(raw))
    if nbytes > MAX_BYTES * (1.4 if isinstance(raw, str) else 1):
        return {"ok": False, "error": "user_error: 图片太大（> 8MB）", "missing": ["image"],
                "bytes": nbytes}
    try:
        from . import vision_cap as V
        r = V.run(op="analyze", image=image)
        if r.get("ok"):
            return {"ok": True, "brief": _brief(r), "analysis": r, "via": "vision:local"}
        return {"ok": False, "error": str(r.get("error") or r.get("status")
                                          or "视觉分析失败")[:200],
                "missing": r.get("missing") or ["image_read"], "analysis": r}
    except Exception as exc:                                     # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, str(exc)[:180]),
                "missing": ["vision_dependency"]}
