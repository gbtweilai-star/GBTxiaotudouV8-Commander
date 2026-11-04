# -*- coding: utf-8 -*-
"""vision_ui -- 界面元素识别（把"画面上有什么"变成"能看到什么、能点什么"）

主人令（2026-11-04）：必须让她聪明点，懂得识别所有东西。

做法：把两个已有能力拼起来，**不新增模型**。
  · `vision_ocr.ocr_boxes()`  → 每行文字 + 精确包围盒
  · `vision_arsenal.region_scan()` → 画面里像"一块块"的矩形（按钮/输入框/卡片）

为什么要"文字打底 + 区块补漏"，而不是只靠轮廓：
  真实界面里大量按钮**没有边框**，openCV 轮廓根本扫不出来。反过来只靠文字，
  又拿不到图标、卡片、容器这些没有文字的块。所以两条腿必须都走。

── 元素模型 ──────────────────────────────────────────────
  button    可点按钮（有字、块高 22~64、字占地 > 45%）
  input     输入框/搜索框（有字、块高 22~64、横向很宽或字靠左）
  text      纯文本行（没被任何区块框住）
  icon      无字的小方块（比例接近 1、面积不大）
  container 容器/卡片（大块，或含 2 行以上文字）

── 铁律 ──────────────────────────────────────────────────
1. **只回结构化数据**：类型 + 文字 + 坐标，绝不回图。
2. **不编造**：OCR 读不到字就留空，不做猜测性补全。
3. **可直接点**：每个元素给 `cx/cy`，调用方拿起来就能点。
"""
from __future__ import annotations

import os

# 阈值（按真实界面截图调过）
_BTN_MIN_H, _BTN_MAX_H = 20, 72
_BTN_MAX_W = 360
_ICON_MAX_SIDE = 64
_TEXT_FILL = 0.45          # 文字宽度 / 元素宽度，超过算"字撑满了"→ 更像按钮
_CONTAIN_MIN_LINES = 2


def _iou(a, b) -> float:
    ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
    bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]
    ix = max(0, min(ax2, bx2) - max(a["x"], b["x"]))
    iy = max(0, min(ay2, by2) - max(a["y"], b["y"]))
    inter = ix * iy
    if inter <= 0:
        return 0.0
    ua = a["w"] * a["h"] + b["w"] * b["h"] - inter
    return inter / float(ua + 1e-9)


def _center_in(inner, outer, pad: int = 2) -> bool:
    cx = inner["x"] + inner["w"] / 2.0
    cy = inner["y"] + inner["h"] / 2.0
    return (outer["x"] - pad <= cx <= outer["x"] + outer["w"] + pad and
            outer["y"] - pad <= cy <= outer["y"] + outer["h"] + pad)


def _merge_overlaps(rects, thr: float = 0.85):
    """轮廓法会产出大量套娃矩形，先按 IoU 去重（保留面积大的）。"""
    rects = sorted(rects, key=lambda r: -r["w"] * r["h"])
    kept = []
    for r in rects:
        if any(_iou(r, k) >= thr for k in kept):
            continue
        kept.append(r)
    return kept


def _classify(region, lines):
    """猜元素类型。宁可用保守规则，也不乱贴标签。"""
    h, w = region["h"], region["w"]
    if not lines:
        if max(w, h) <= _ICON_MAX_SIDE and 0.4 <= w / float(h or 1) <= 2.5:
            return "icon"
        return "container"

    text_w = max((ln["x"] + ln["w"]) for ln in lines) - min(ln["x"] for ln in lines)
    fill = text_w / float(w or 1)

    if _BTN_MIN_H <= h <= _BTN_MAX_H:
        if w >= 320 and fill < 0.55:
            return "input"
        if fill >= _TEXT_FILL and w <= _BTN_MAX_W:
            return "button"
        if fill >= 0.30 and w <= _BTN_MAX_W:
            return "button"
    if len(lines) >= _CONTAIN_MIN_LINES and h > _BTN_MAX_H:
        return "container"
    return "text"


def parse(image: str, max_elements: int = 300, min_area: int = 400) -> dict:
    """解析一张界面截图，回元素列表（按阅读顺序：先上后下、先左后右）。"""
    if not image:
        return {"ok": False, "reason": "需要 image：本地截图路径"}
    if not os.path.exists(image):
        return {"ok": False, "reason": "图片不存在: %s" % image}

    from . import vision_ocr, vision_arsenal

    # ① 文字：每行 + 包围盒
    ocr_res = vision_ocr.ocr_boxes(image)
    lines = []
    if ocr_res.get("ok"):
        for b in ocr_res.get("boxes") or []:
            t = (b.get("text") or "").strip()
            if not t or b.get("w", 0) <= 0 or b.get("h", 0) <= 0:
                continue
            lines.append({"text": t, "x": int(b["x"]), "y": int(b["y"]),
                          "w": int(b["w"]), "h": int(b["h"])})

    # ② 区块：轮廓法找"没文字也能看见"的块
    scan = vision_arsenal.region_scan(image, min_area=min_area)
    regions = []
    if scan.get("ok"):
        regions = _merge_overlaps([
            {"x": int(r["x"]), "y": int(r["y"]), "w": int(r["w"]), "h": int(r["h"])}
            for r in scan.get("rects") or []
        ])

    # ③ 把文字挂到最内层区块上
    assigned = set()
    elements = []
    for reg in regions:
        inside = []
        for i, ln in enumerate(lines):
            if i in assigned:
                continue
            if _center_in(ln, reg) and (ln["w"] * ln["h"]) < 0.92 * (reg["w"] * reg["h"]):
                inside.append(ln)
                assigned.add(i)
        etype = _classify(reg, inside)
        # 文字顺序按 y 再按 x
        inside.sort(key=lambda l: (l["y"], l["x"]))
        elements.append({
            "type": etype,
            "text": " ".join(l["text"] for l in inside).strip(),
            "x": reg["x"], "y": reg["y"], "w": reg["w"], "h": reg["h"],
            "cx": reg["x"] + reg["w"] // 2, "cy": reg["y"] + reg["h"] // 2,
            "text_lines": len(inside),
            "source": "block",
        })

    # ④ 没被区块框住的文字行 → 独立 text 元素（保证"所有看得见的字"都在）
    for i, ln in enumerate(lines):
        if i in assigned:
            continue
        elements.append({
            "type": "text", "text": ln["text"],
            "x": ln["x"], "y": ln["y"], "w": ln["w"], "h": ln["h"],
            "cx": ln["x"] + ln["w"] // 2, "cy": ln["y"] + ln["h"] // 2,
            "text_lines": 1, "source": "text",
        })

    # ⑤ 去重：同一样东西别数两遍
    #    · 图标被文字元素包住 ⇒ 它和那段文字是同一个对象（如"🔷 标题"）
    #    · 无字的小容器 ⇒ 轮廓噪声，不是可交互对象
    def _covered(outer, inner, thr: float = 0.70) -> bool:
        ix = max(0, min(outer["x"] + outer["w"], inner["x"] + inner["w"]) - max(outer["x"], inner["x"]))
        iy = max(0, min(outer["y"] + outer["h"], inner["y"] + inner["h"]) - max(outer["y"], inner["y"]))
        return (ix * iy) >= thr * (inner["w"] * inner["h"] + 1e-9)

    with_text = [e for e in elements
                 if e["type"] in ("text", "button", "input") and e.get("text")]
    kept = []
    for e in elements:
        if e["type"] == "icon" and any(_covered(t, e) for t in with_text):
            continue
        if e["type"] == "container" and not e.get("text") and e["w"] * e["h"] < 4000:
            continue
        kept.append(e)
    elements = kept

    # ⑥ 阅读顺序 + 截断
    elements.sort(key=lambda e: (e["y"] // 12, e["x"]))
    elements = elements[:max_elements]
    for idx, e in enumerate(elements):
        e["id"] = "e%d" % (idx + 1)

    counts: dict = {}
    for e in elements:
        counts[e["type"]] = counts.get(e["type"], 0) + 1

    return {
        "ok": True,
        "image": image,
        "counts": counts,
        "total": len(elements),
        "ocr_lines": len(lines),
        "regions": len(regions),
        "elements": elements,
        "note": "" if lines else "OCR 没读到字，只有形状块；可考虑换 ocr 单独排查",
    }


def find(image: str, query: str, limit: int = 8) -> dict:
    """按文字找元素，回坐标 —— 这是"点那个写着 XX 的按钮"的入口。"""
    if not query:
        return {"ok": False, "reason": "需要 query：要找的文字"}
    parsed = parse(image)
    if not parsed.get("ok"):
        return parsed

    q = str(query).strip()
    hits = []
    for e in parsed["elements"]:
        t = e.get("text") or ""
        if not t:
            continue
        if q == t:
            score = 3.0
        elif q in t:
            score = 2.0
        elif t in q:
            score = 1.0
        else:
            # 逐字覆盖率兜底（OCR 偶有断字）
            cov = sum(1 for ch in q if ch in t) / float(len(q))
            if cov < 0.75:
                continue
            score = cov
        # 可点的块优先于纯文本
        if e["type"] in ("button", "input"):
            score += 0.5
        hits.append((score, e))
    hits.sort(key=lambda x: (-x[0], x[1]["y"], x[1]["x"]))

    out = [{"score": round(s, 2), **e} for s, e in hits[:limit]]
    return {"ok": True, "query": q, "count": len(out),
            "best": out[0] if out else None, "hits": out}


def outline(image: str) -> dict:
    """只要轮廓：按类型分组的一句话摘要（给大脑先看个大概，不必吃全量元素）。"""
    parsed = parse(image)
    if not parsed.get("ok"):
        return parsed
    by_type: dict = {}
    for e in parsed["elements"]:
        if e.get("text"):
            by_type.setdefault(e["type"], []).append(e["text"])
    return {
        "ok": True,
        "counts": parsed["counts"],
        "buttons": by_type.get("button", [])[:20],
        "inputs": by_type.get("input", [])[:20],
        "texts": by_type.get("text", [])[:30],
    }


def run(op: str = "parse", **kw) -> dict:
    op = str(op or "parse")
    if op in ("parse", "elements", "all"):
        return parse(kw.get("image"), int(kw.get("max_elements") or 300))
    if op in ("find", "locate", "where"):
        return find(kw.get("image"), kw.get("query") or kw.get("text"))
    if op in ("outline", "summary", "brief"):
        return outline(kw.get("image"))
    return {"ok": False, "reason": "未知 op: %s（支持 parse/find/outline）" % op}
