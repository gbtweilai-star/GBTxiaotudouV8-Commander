# -*- coding: utf-8 -*-
"""vision_eye —— 身体·眼睛：把散装视觉能力收成一个入口

主人令（2026-11-04）：视觉必须能被调用，不能只在终端里跑得通。

── 为什么要有这一层 ────────────────────────────────────────
接线前实况（2026-11-04 已核实，勿再误传「视觉是 0 个」）：
   · `ocr`、`vision_arsenal` **早已在册**，各是一个能力位、各一套参数
   · 但新做的 `vision_detect`(YOLO) / `vision_embed`(CLIP) / `vision_ui`(界面元素)
     **没有注册位** —— 模块能 import、能跑，可 `api.run_task(kind, payload)` 调不到
     【2026-11-04 补正（这一条已过时，留作病史）】六位已全部建位，能力 417→423：
     `vision_detect` / `vision_embed` / `vision_segment` / `vision_pose` /
     `vision_track` / `uia_tree`，`api.run_task` 直调实测全部通过。
     `vision_ui` **仍不单独建位**（有意为之，不是漏）：它的产出就是本文件的
     `parse`/`find` 两步，拆成独立位只会多一套调用形状，与「收成一个入口」相反。
   · 而且同一件事（看懂屏幕）被拆成 3 个入口、3 套调用形状，大脑得先记住用哪个
这一层只做三件事，**不新增模型、不新增依赖**：
  1. **归一**：一个 `run(op, **kw)` 接住全部 5 个模块，op 名即路由
  2. **补洞**：`see` 一步到位 —— 截屏 + 理解 + 给坐标，大脑不用先存图再传路径
  3. **如实**：模块缺依赖/模型不在位，原样透出 `ok=False` 与原因，绝不假装看得见

── 语义边界（写死在代码里，防止被当成万能眼）──────────────
   · `ocr`    读字（每行带坐标）—— 界面文字走这条
   · `ui`     界面元素（按钮/输入框/文本/图标/容器）
   · `find`   按文字找位置 —— 「点那个写着 XX 的按钮」的正解
   · `detect` 真实照片里的物体（COCO 80 类）—— **不适用于界面截图**
   · `embed`  图像特征向量（反色/深色主题下判同的补盲区）
   · `region` 找矩形区块、`template` 找图标模板

铁律：只回结构化数据 + 坐标，**绝不回图**。
"""
from __future__ import annotations

import os
import tempfile
import time

# op → (模块名, 该模块内的 op 名)
# 同一个模块的多个别名都指向它自己的 op，避免调用方记混。
_OPS = {
    "ocr":     ("ocr",     "read"),
    "read":    ("ocr",     "read"),
    "text":    ("ocr",     "read"),
    "boxes":   ("ocr",     "boxes"),

    "ui":      ("ui",      "parse"),
    "parse":   ("ui",      "parse"),
    "elements": ("ui",     "parse"),
    "outline": ("ui",      "outline"),
    "brief":   ("ui",      "outline"),
    "find":    ("ui",      "find"),
    "locate":  ("ui",      "find"),
    "where":   ("ui",      "find"),

    "detect":  ("detect",  "detect"),
    "objects": ("detect",  "detect"),

    "pose":    ("pose",    "pose"),
    "keypoints": ("pose",  "pose"),
    "skeleton": ("pose",   "pose"),

    # 跟踪：给 boxes 就关联（update），给 frames 就逐帧检测+关联（track）
    # 抠图：点在主体上或给 box（box 明显更好用 —— 实测点提示 iou .688/覆盖1.1%，
    # 框提示 iou .913/覆盖31.3%）
    "segment": ("segment", "segment"),
    "cut":     ("segment", "segment"),
    "matte":   ("segment", "segment"),

    "track":   ("track",   "update"),
    "follow":  ("track",   "update"),
    "track_frames": ("track", "track"),
    "track_images": ("track", "track"),

    "embed":   ("embed",   "embed"),
    "vector":  ("embed",   "embed"),
    "similarity": ("embed", "similarity"),
    "nearest": ("embed",   "nearest"),

    # 注意：arsenal 的 op 名是 region_scan / template_match（不是 region / template），
    # 写错了会被它自己判成"未知 op"——已实测踩过一次。
    "region":  ("arsenal", "region_scan"),
    "regions": ("arsenal", "region_scan"),
    "scan":    ("arsenal", "region_scan"),
    "region_scan": ("arsenal", "region_scan"),
    "template": ("arsenal", "template_match"),
    "template_match": ("arsenal", "template_match"),
    "decide":  ("arsenal", "decide"),
}

# 需要在入参里给出 image 的 op（`see` 例外，它自己截）
_NEED_IMAGE = {
    "ocr", "read", "text", "boxes", "ui", "parse", "elements", "outline", "brief",
    "find", "locate", "where", "detect", "objects", "pose", "keypoints", "skeleton",
    "segment", "cut", "matte",
    "embed", "vector", "similarity",
    "nearest", "region", "regions", "scan", "region_scan", "template", "template_match",
}


# 入参别名归一：调用方不该为了「喂一张图」去背每个模块的形参名。
# 实测踩过：similarity 要 image_a/image_b，传 a/b 直接 TypeError —— 这种摩擦不该外溢给大脑。
_ALIAS = {
    "similarity": {"a": "image_a", "b": "image_b", "img_a": "image_a", "img_b": "image_b",
                   "image1": "image_a", "image2": "image_b",
                   "path_a": "image_a", "path_b": "image_b",
                   "img1": "image_a", "img2": "image_b"},
    "nearest": {"image": "base", "path": "base", "image_base": "base",
                "list": "candidates", "images": "candidates", "pool": "candidates"},
    "find": {"text": "query", "q": "query", "label": "query", "target": "query"},
    "detect": {"path": "image", "file": "image"},
    "region": {"path": "image", "file": "image"},
    "template": {"path": "image", "file": "image"},
}


def _norm_params(op: str, params: dict) -> dict:
    """把别名换成模块真正认的形参名；不认识的键原样留着，让模块自己决定收不收。"""
    alias = _ALIAS.get(op) or {}
    out = {}
    for k, v in params.items():
        out[alias.get(k, k)] = v
    return out


def _mod(name: str):
    """惰性取模块 —— 某个模块缺依赖时，不该连带把整层拖垮。"""
    from . import (vision_ocr, vision_detect, vision_embed, vision_ui,
                   vision_arsenal, vision_pose, vision_track, vision_segment)
    return {"ocr": vision_ocr, "detect": vision_detect, "embed": vision_embed,
            "ui": vision_ui, "arsenal": vision_arsenal, "pose": vision_pose,
            "track": vision_track, "segment": vision_segment}[name]


_KEEP_SHOTS = 20


def _gc_shots(keep: int = _KEEP_SHOTS) -> int:
    """`see` 每调一次就落一张 png，长期跑会把 temp 撑满。

    只留最近 keep 张 —— 新图不能删（调用方可能还要拿坐标去点），老图留着没用。
    这是本层自己的「排泄」，不碰框架的 excrete。
    """
    try:
        d = tempfile.gettempdir()
        files = [os.path.join(d, f) for f in os.listdir(d)
                 if f.startswith("eye_") and f.endswith(".png")]
        if len(files) <= keep:
            return 0
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        n = 0
        for f in files[keep:]:
            try:
                os.remove(f)
                n += 1
            except OSError:
                pass
        return n
    except Exception:                                              # noqa: BLE001
        return 0


def shot(monitor: int = 0) -> dict:
    """截当前屏幕落 png。优先 PIL 直截（零子进程），失败再回落 body 子进程。"""
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        if monitor:
            try:
                from PIL import ImageGrab as _g
                allmon = _g.grab(all_screens=True)
                img = allmon
            except Exception:
                pass
        fd, out = tempfile.mkstemp(prefix="eye_", suffix=".png")
        os.close(fd)
        img.save(out)
        _gc_shots()          # 顺手排掉旧图，别让 temp 无声涨满
        return {"ok": True, "image": out, "w": img.size[0], "h": img.size[1],
                "via": "pil"}
    except Exception as exc:                                       # noqa: BLE001
        err = "%s: %s" % (type(exc).__name__, str(exc)[:120])

    # 回落：身体·看（子进程截屏，路径落在 state 里，稳定但慢一些）
    try:
        from . import body_bridge
        r = body_bridge.run("see", {"monitor": monitor} if monitor else {})
        if r.get("ok"):
            path = r.get("image") or r.get("path") or r.get("file")
            if path and os.path.exists(path):
                return {"ok": True, "image": path, "via": "body_see"}
        err2 = r.get("error") or "body_see 没给可用路径"
        return {"ok": False, "error": "截屏失败：%s；回落 body_see 也不行：%s" % (err, err2)}
    except Exception as exc:                                       # noqa: BLE001
        return {"ok": False, "error": "截屏失败：%s；回落也失败：%s: %s"
                % (err, type(exc).__name__, str(exc)[:120])}


def see(query: str = "", op: str = "", monitor: int = 0, **kw) -> dict:
    """一步到位：截屏 → 理解 → 回结构化结果（给了 query 就直接定位坐标）。

    这是大脑最常用的形状：不用先要一张图、再攒一个路径、再调第二个能力。
    """
    t0 = time.time()
    g = shot(monitor)
    if not g.get("ok"):
        return g

    use = str(op or "").strip()
    if not use:
        use = "find" if query else "ui"

    tgt = _OPS.get(use)
    if not tgt:
        return {"ok": False, "reason": "见（see）不支持 op=%s" % use,
                "image": g["image"], "supported": sorted(_OPS)}

    params = dict(kw)
    params["image"] = g["image"]
    if query:
        params["query"] = query

    r = run(use, **params)
    if isinstance(r, dict):
        r["image"] = g["image"]
        r["screen"] = {"w": g.get("w"), "h": g.get("h")}
        r["elapsed_ms"] = int((time.time() - t0) * 1000)
        r.setdefault("shot_via", g.get("via"))
    return r


def status() -> dict:
    """这一层现在能干什么：5 个模块在位情况 + 19 位视觉矩阵。"""
    out = {"ok": True, "ops": sorted(set(_OPS) | {"see", "status", "arsenal"}),
           "modules": {}, "cameras": {}}
    try:
        from . import vision_arsenal
        out["arsenal"] = vision_arsenal.status("")
    except Exception as exc:                                       # noqa: BLE001
        out["arsenal"] = {"ok": False, "error": "%s: %s" % (type(exc).__name__, str(exc)[:100])}

    for name in ("ocr", "detect", "embed", "ui", "pose", "track", "segment"):
        try:
            m = _mod(name)
            probe = getattr(m, "model_ready", None)
            out["modules"][name] = {"import_ok": True,
                                    "model_ready": bool(probe()) if callable(probe) else True}
        except Exception as exc:                                   # noqa: BLE001
            out["modules"][name] = {"import_ok": False,
                                    "error": "%s: %s" % (type(exc).__name__, str(exc)[:100])}
    out["note"] = ("detect 只认真实照片的 COCO 80 类，界面截图请用 ui/find；"
                   "embed 是 aHash 的补盲区（反色/深色主题）")
    return out


def run(op: str = "status", **kw) -> dict:
    """统一入口。op 名即路由；`see` 是截屏+理解的组合位。"""
    o = str(op or "status").strip()

    if o in ("status", "arsenal", "matrix"):
        if o == "matrix":
            try:
                from . import vision_arsenal
                return {"ok": True, "matrix": vision_arsenal.matrix()}
            except Exception as exc:                               # noqa: BLE001
                return {"ok": False, "error": "%s: %s" % (type(exc).__name__, str(exc)[:120])}
        return status()

    if o in ("see", "look", "screenshot"):
        return see(query=str(kw.pop("query", "") or ""),
                   op=str(kw.pop("op2", "") or kw.pop("then", "") or ""),
                   monitor=int(kw.pop("monitor", 0) or 0), **kw)

    tgt = _OPS.get(o)
    if not tgt:
        return {"ok": False, "reason": "未知 op: %s" % o,
                "supported": sorted(set(_OPS) | {"see", "status", "arsenal", "matrix"})}

    mod_name, inner_op = tgt

    # 先把别名归一，再校验缺参 —— 否则 `a/b` 会被当成"没给图"误报
    params = _norm_params(o, {k: v for k, v in kw.items()})
    if "path" in params and "image" not in params:
        params["image"] = params.pop("path")

    # 缺参检查按 op 的真实必需项（similarity 要两张图，只查 image 会误报）
    need_map = {
        "similarity": ("image_a", "image_b"),
        "nearest": ("base", "candidates"),
        "find": ("image", "query"), "locate": ("image", "query"), "where": ("image", "query"),
        "decide": ("intent",),
    }
    need = need_map.get(o)
    if need:
        miss = [n for n in need if not params.get(n)]
        if miss:
            return {"ok": False, "reason": "%s 缺参数：%s" % (o, ",".join(miss)),
                    "given": sorted(params), "hint": "op=status 可看能力清单"}
    elif o in _NEED_IMAGE and not params.get("image"):
        return {"ok": False, "reason": "%s 需要 image：本地图片路径（或用 op=see 自动截屏）" % o}

    try:
        m = _mod(mod_name)
    except Exception as exc:                                       # noqa: BLE001
        return {"ok": False, "error": "模块 %s 载入失败：%s: %s"
                % (mod_name, type(exc).__name__, str(exc)[:140])}

    try:
        # ocr 的 boxes 是独立函数，其余模块走自己的 run
        if mod_name == "ocr" and inner_op == "boxes":
            r = m.ocr_boxes(params.get("image"))
            return r if isinstance(r, dict) else {"ok": True, "result": r}
        if hasattr(m, "run"):
            r = m.run(inner_op, **params)
        else:
            r = {"ok": False, "error": "模块 %s 没有 run()" % mod_name}
        return r if isinstance(r, dict) else {"ok": True, "result": r}
    except TypeError as exc:
        return {"ok": False, "error": "入参不被 %s 接受：%s" % (mod_name, str(exc)[:160]),
                "hint": "检查是否多给了参数；op=status 可看能力清单"}
    except Exception as exc:                                       # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, str(exc)[:160])}
