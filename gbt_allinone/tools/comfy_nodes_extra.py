# -*- coding: utf-8 -*-
"""comfy_nodes_extra —— 脚手架生成的新节点（由 tools/comfy-add-node.py 追加）。

为什么要独立模块：`comfy_native.py` 已经很大，**自动往主模块追加代码是维护灾难**。
这里的节点会在 comfy_native import 时合并进 NODES（见主模块末尾的 merge）。

可用的父级助手（从主模块借，不复制）：NODES / _out_path / _save / _store
注意：本模块在 comfy_native **末尾**被 import，所以届时那些名字都已定义。
"""
import pathlib  # noqa: F401  （生成骨架里会用到）

from .comfy_native import NODES, _out_path, _save, _store  # noqa: F401

def _n_ImageFlipX(inputs: dict, ctx: dict) -> dict:
    """水平翻转（PIL FLIP_LEFT_RIGHT）"""
    from PIL import Image
    src = inputs.get("image") or inputs.get("path")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    img = Image.open(str(src)).convert("RGBA")
    from PIL import ImageOps
    img = ImageOps.mirror(img)
    out = _out_path(inputs, "imageflipx")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return {"ok": True, "out": out, "width": img.width, "height": img.height}

NODES["ImageFlipX"] = {"fn": _n_ImageFlipX, "in": ["image", "out"], "out": ["IMAGE"], "writes": True,
                   "desc": "水平翻转（PIL FLIP_LEFT_RIGHT）（image 族脚手架生成 2026-11-01）"}


# ── 2026-11-01 批次 A：从取食清单里挑的**纯 CPU 传统算子**（12 个）──
# 契约按 ComfyUI 语义写（输入名尽量对齐）；精确 schema 等秋叶真快照到手再逐条校准。
def _n_AdjustBrightness(inputs: dict, ctx: dict) -> dict:
    """亮度调整（factor：1.0 原样）。"""
    import pathlib
    from PIL import Image, ImageEnhance
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    img = ImageEnhance.Brightness(Image.open(str(src)).convert("RGBA")).enhance(
        float(inputs.get("factor") or inputs.get("brightness") or 1.0))
    out = _out_path(inputs, "adjustbr")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return {"ok": True, "out": out, "width": img.width, "height": img.height}


def _n_AdjustContrast(inputs: dict, ctx: dict) -> dict:
    """对比度调整（factor：1.0 原样）。"""
    import pathlib
    from PIL import Image, ImageEnhance
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    img = ImageEnhance.Contrast(Image.open(str(src)).convert("RGBA")).enhance(
        float(inputs.get("factor") or inputs.get("contrast") or 1.0))
    out = _out_path(inputs, "adjustct")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return {"ok": True, "out": out}


def _n_CaseConverter(inputs: dict, ctx: dict) -> dict:
    """字符串大小写转换（upper/lower/title/capitalize）。"""
    txt = str(inputs.get("text") or "")
    mode = str(inputs.get("mode") or inputs.get("case") or "lower").lower()
    fn = {"upper": str.upper, "lower": str.lower, "title": str.title,
          "capitalize": str.capitalize}.get(mode, str.lower)
    return {"ok": True, "text": fn(txt), "mode": mode}


def _n_CenterCropImages(inputs: dict, ctx: dict) -> dict:
    """居中裁剪到正方形（边长 = 短边，可再乘以 scale）。"""
    import pathlib
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    from PIL import Image
    img = Image.open(str(src)).convert("RGBA")
    side = min(img.width, img.height)
    left, top = (img.width - side) // 2, (img.height - side) // 2
    out = _out_path(inputs, "centercrop")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.crop((left, top, left + side, top + side)).save(out)
    return {"ok": True, "out": out, "size": side}


def _n_ColorToRGBInt(inputs: dict, ctx: dict) -> dict:
    """颜色 → 0xRRGGBB 整数（ComfyUI 里常用于给 SolidMask/EmptyImage 传色）。"""
    c = inputs.get("color")
    if isinstance(c, str) and c.startswith("#"):
        return {"ok": True, "rgb_int": int(c[1:], 16)}
    if isinstance(c, (list, tuple)) and len(c) >= 3:
        r, g, b = (int(float(x)) for x in c[:3])
        return {"ok": True, "rgb_int": (r << 16) | (g << 8) | b}
    if isinstance(c, int):
        return {"ok": True, "rgb_int": c}
    return {"ok": False, "error": "user_error: color 要 #RRGGBB / [r,g,b] / int"}


def _n_ComfyNumberConvert(inputs: dict, ctx: dict) -> dict:
    """数值类型转换（int/float）。"""
    v = inputs.get("value", inputs.get("number"))
    to = str(inputs.get("to") or "float").lower()
    try:
        out = int(float(v)) if to == "int" else float(v)
    except Exception:  # noqa: BLE001
        return {"ok": False, "error": "user_error: 不是数值：%r" % (v,)}
    return {"ok": True, "value": out, "type": to}


def _n_GrowMask(inputs: dict, ctx: dict) -> dict:
    """遮罩膨胀（PIL MaxFilter 近似，radius 像素）。"""
    import pathlib
    src = inputs.get("mask") or inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 mask"}
    from PIL import Image, ImageFilter
    m = Image.open(str(src)).convert("L")
    r = max(0, int(inputs.get("expand") or inputs.get("radius") or 4))
    if r:
        m = m.filter(ImageFilter.MaxFilter(size=min(9, max(3, r * 2 + 1))))
    out = _out_path(inputs, "growmask")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    m.convert("RGBA").save(out)
    return {"ok": True, "out": out, "expand": r}


def _n_ImageFlip(inputs: dict, ctx: dict) -> dict:
    """翻转（horizontal/vertical）。"""
    import pathlib
    from PIL import ImageOps
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    from PIL import Image
    img = Image.open(str(src)).convert("RGBA")
    mode = str(inputs.get("mode") or inputs.get("direction") or "horizontal").lower()
    img = ImageOps.mirror(img) if mode.startswith("h") else ImageOps.flip(img)
    out = _out_path(inputs, "imageflip")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return {"ok": True, "out": out, "mode": mode}


def _n_ImageFromBatch(inputs: dict, ctx: dict) -> dict:
    """从批次取第 index 张（我们是单图流水，index=0 原样出）。"""
    import pathlib
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    from PIL import Image
    idx = int(inputs.get("index") or 0)
    if idx != 0:
        return {"ok": False,
                "error": "unsupported: 单图流水没有批次，index=%d（只支持 0）" % idx}
    img = Image.open(str(src)).convert("RGBA")
    out = _out_path(inputs, "frombatch")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return {"ok": True, "out": out, "index": idx}


def _n_ImageGrid(inputs: dict, ctx: dict) -> dict:
    """把多张图拼成网格（images 逗号分隔路径；columns 列数）。"""
    import pathlib
    raw = inputs.get("images") or inputs.get("image")
    if not raw:
        return {"ok": False, "error": "user_error: 要 images（逗号分隔）"}
    paths = [x.strip() for x in str(raw).split(",") if x.strip()]
    from PIL import Image
    imgs = [Image.open(p).convert("RGBA") for p in paths]
    cols = max(1, int(inputs.get("columns") or 2))
    rows = (len(imgs) + cols - 1) // cols
    cw = max(i.width for i in imgs)
    ch = max(i.height for i in imgs)
    grid = Image.new("RGBA", (cw * cols, ch * rows), (0, 0, 0, 0))
    for k, im in enumerate(imgs):
        grid.paste(im, ((k % cols) * cw, (k // cols) * ch))
    out = _out_path(inputs, "imagegrid")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    grid.save(out)
    return {"ok": True, "out": out, "count": len(imgs), "columns": cols}


def _n_ImageScaleToMaxDimension(inputs: dict, ctx: dict) -> dict:
    """按最长边缩放到 max_dimension。"""
    import pathlib
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    from PIL import Image
    img = Image.open(str(src)).convert("RGBA")
    md = int(inputs.get("max_dimension") or inputs.get("size") or 1024)
    if md <= 0:
        return {"ok": False, "error": "user_error: max_dimension>0"}
    scale = md / max(img.width, img.height)
    w, h = max(1, int(img.width * scale)), max(1, int(img.height * scale))
    out = _out_path(inputs, "scalemax")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.resize((w, h), Image.LANCZOS).save(out)
    return {"ok": True, "out": out, "width": w, "height": h}


def _n_ImageStitch(inputs: dict, ctx: dict) -> dict:
    """横向/纵向拼接两张图。"""
    import pathlib
    a, b = inputs.get("image1"), inputs.get("image2")
    if not a or not b:
        return {"ok": False, "error": "user_error: 要 image1/image2"}
    from PIL import Image
    i1, i2 = Image.open(str(a)).convert("RGBA"), Image.open(str(b)).convert("RGBA")
    direction = str(inputs.get("direction") or "right").lower()
    if direction in ("right", "left", "horizontal"):
        w = i1.width + i2.width
        canvas = Image.new("RGBA", (w, max(i1.height, i2.height)), (0, 0, 0, 0))
        if direction == "left":
            canvas.paste(i2, (0, 0)); canvas.paste(i1, (i2.width, 0))
        else:
            canvas.paste(i1, (0, 0)); canvas.paste(i2, (i1.width, 0))
    else:
        h = i1.height + i2.height
        canvas = Image.new("RGBA", (max(i1.width, i2.width), h), (0, 0, 0, 0))
        canvas.paste(i1, (0, 0)); canvas.paste(i2, (0, i1.height))
    out = _out_path(inputs, "stitch")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return {"ok": True, "out": out, "size": list(canvas.size)}


NODES.update({
    "AdjustBrightness": {"fn": _n_AdjustBrightness, "in": ["image", "out", "factor?"],
                         "out": ["IMAGE"], "writes": True, "desc": "亮度（factor=1 原样）"},
    "AdjustContrast": {"fn": _n_AdjustContrast, "in": ["image", "out", "factor?"],
                       "out": ["IMAGE"], "writes": True, "desc": "对比度（factor=1 原样）"},
    "CaseConverter": {"fn": _n_CaseConverter, "in": ["text", "mode?"], "out": ["STRING"],
                      "writes": False, "desc": "字符串大小写转换"},
    "CenterCropImages": {"fn": _n_CenterCropImages, "in": ["image", "out"], "out": ["IMAGE"],
                         "writes": True, "desc": "居中裁成正方形（边长=短边）"},
    "ColorToRGBInt": {"fn": _n_ColorToRGBInt, "in": ["color"], "out": ["INT"],
                      "writes": False, "desc": "颜色 → 0xRRGGBB 整数"},
    "ComfyNumberConvert": {"fn": _n_ComfyNumberConvert, "in": ["value", "to?"],
                           "out": ["NUMBER"], "writes": False, "desc": "数值类型转换（int/float）"},
    "GrowMask": {"fn": _n_GrowMask, "in": ["mask", "out", "expand?"], "out": ["MASK"],
                 "writes": True, "desc": "遮罩膨胀（MaxFilter 近似）"},
    "ImageFlip": {"fn": _n_ImageFlip, "in": ["image", "out", "mode?"], "out": ["IMAGE"],
                  "writes": True, "desc": "翻转（horizontal/vertical）"},
    "ImageFromBatch": {"fn": _n_ImageFromBatch, "in": ["image", "out", "index?"],
                       "out": ["IMAGE"], "writes": True, "desc": "从批次取第 index 张（单图只支持 0）"},
    "ImageGrid": {"fn": _n_ImageGrid, "in": ["images", "out", "columns?"], "out": ["IMAGE"],
                  "writes": True, "desc": "多图拼网格"},
    "ImageScaleToMaxDimension": {"fn": _n_ImageScaleToMaxDimension,
                                 "in": ["image", "out", "max_dimension?"], "out": ["IMAGE"],
                                 "writes": True, "desc": "最长边缩放到 max_dimension"},
    "ImageStitch": {"fn": _n_ImageStitch, "in": ["image1", "image2", "out", "direction?"],
                    "out": ["IMAGE"], "writes": True, "desc": "横/纵向拼接两张图"},
})


# ── 2026-11-01 批次 B：又 10 个纯 CPU 传统算子（从 106 条缺口里挑）──
def _n_ConvertArrayToString(inputs: dict, ctx: dict) -> dict:
    """数组 → 字符串（可指定分隔符）。"""
    arr = inputs.get("array", inputs.get("value"))
    if isinstance(arr, str):
        arr = [x.strip() for x in arr.split(",") if x.strip()]
    if not isinstance(arr, (list, tuple)):
        arr = [arr] if arr is not None else []
    sep = str(inputs.get("separator") or inputs.get("delimiter") or ",")
    return {"ok": True, "text": sep.join(str(x) for x in arr), "count": len(arr)}


def _n_ConvertDictionaryToString(inputs: dict, ctx: dict) -> dict:
    """字典 → JSON 字符串（保证可读、可回灌）。"""
    import json as _j
    d = inputs.get("dict", inputs.get("dictionary", inputs.get("value")))
    try:
        return {"ok": True, "text": _j.dumps(d, ensure_ascii=False, sort_keys=True)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "user_error: 不能 JSON 化：%s" % str(e)[:80]}


def _n_CropByBBoxes(inputs: dict, ctx: dict) -> dict:
    """按 bbox 裁剪（bbox = "x,y,w,h" 或 [[x,y,w,h], ...]，取第一个）。"""
    import pathlib
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    raw = inputs.get("bboxes") or inputs.get("bbox")
    box = None
    if isinstance(raw, str):
        nums = [float(x) for x in raw.replace(";", ",").split(",") if x.strip()]
        if len(nums) >= 4:
            box = [int(nums[0]), int(nums[1]), int(nums[2]), int(nums[3])]
    elif isinstance(raw, (list, tuple)):
        if len(raw) >= 4 and all(isinstance(x, (int, float)) for x in raw[:4]):
            box = [int(x) for x in raw[:4]]
        elif raw and isinstance(raw[0], (list, tuple)) and len(raw[0]) >= 4:
            box = [int(x) for x in raw[0][:4]]
    if not box or box[2] <= 0 or box[3] <= 0:
        return {"ok": False, "error": "user_error: 要 bboxes（x,y,w,h）"}
    from PIL import Image
    img = Image.open(str(src)).convert("RGBA")
    x, y, w, h = box
    out = _out_path(inputs, "cropbbox")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.crop((x, y, x + w, y + h)).save(out)
    return {"ok": True, "out": out, "box": box}


def _n_ImageHistogram(inputs: dict, ctx: dict) -> dict:
    """直方图读数（不落盘）：每通道 256 桶，返回非零桶数与峰值。"""
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    from PIL import Image
    img = Image.open(str(src)).convert("RGB")
    out = {}
    for ch, name in zip(range(3), ("r", "g", "b")):
        hist = img.histogram()[ch * 256:(ch + 1) * 256]
        out[name] = {"peak": max(hist), "peak_at": hist.index(max(hist)),
                     "nonzero": sum(1 for v in hist if v)}
    return {"ok": True, "histogram": out}


def _n_ImageCropV2(inputs: dict, ctx: dict) -> dict:
    """裁剪 v2（x/y/width/height，越界自动夹紧）。"""
    import pathlib
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    from PIL import Image
    img = Image.open(str(src)).convert("RGBA")
    x, y = max(0, int(inputs.get("x") or 0)), max(0, int(inputs.get("y") or 0))
    w = int(inputs.get("width") or img.width - x)
    h = int(inputs.get("height") or img.height - y)
    box = (x, y, min(img.width, x + max(1, w)), min(img.height, y + max(1, h)))
    out = _out_path(inputs, "cropv2")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.crop(box).save(out)
    return {"ok": True, "out": out, "box": list(box)}


def _n_EmptyAudio(inputs: dict, ctx: dict) -> dict:
    """生成静音 wav（时长秒 × 采样率；16bit 单声道）。纯 stdlib wave。"""
    import pathlib
    import wave
    dur = float(inputs.get("duration") or inputs.get("seconds") or 1.0)
    rate = int(inputs.get("sample_rate") or 16000)
    frames = max(1, int(dur * rate))
    out = _out_path(inputs, "emptyaudio")
    if not str(out).lower().endswith(".wav"):
        out = str(pathlib.Path(out).with_suffix(".wav"))
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(out, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * frames)
    return {"ok": True, "out": out, "duration": dur, "sample_rate": rate}


def _n_ImageCompare(inputs: dict, ctx: dict) -> dict:
    """两图对比（尺寸不一时先对齐到小图）：返回平均绝对差与是否相同。"""
    import pathlib
    a, b = inputs.get("image1"), inputs.get("image2")
    if not a or not b:
        return {"ok": False, "error": "user_error: 要 image1/image2"}
    from PIL import Image, ImageChops
    i1, i2 = Image.open(str(a)).convert("RGB"), Image.open(str(b)).convert("RGB")
    if i1.size != i2.size:
        i2 = i2.resize(i1.size)
    diff = ImageChops.difference(i1, i2)
    hist = diff.convert("L").histogram()
    total = sum(i * v for i, v in enumerate(hist))
    px = max(1, i1.width * i1.height)
    mean = total / px
    return {"ok": True, "mean_abs_diff": round(mean, 3), "identical": mean == 0,
            "size": list(i1.size)}


def _n_ColorTransfer(inputs: dict, ctx: dict) -> dict:
    """色彩迁移（把 image2 的均值/方差搬到 image1；numpy + PIL）。"""
    import pathlib
    a, b = inputs.get("image1") or inputs.get("target"), inputs.get("image2") or inputs.get("source")
    if not a or not b:
        return {"ok": False, "error": "user_error: 要 image1/image2"}
    try:
        import numpy as np
    except Exception:  # noqa: BLE001
        return {"ok": False, "error": "needs_dependency: numpy 缺失"}
    from PIL import Image
    t = np.asarray(Image.open(str(a)).convert("RGB"), dtype=np.float32)
    s = np.asarray(Image.open(str(b)).convert("RGB"), dtype=np.float32)
    if s.shape[:2] != t.shape[:2]:
        s = np.asarray(Image.open(str(b)).convert("RGB").resize(
            (t.shape[1], t.shape[0])), dtype=np.float32)
    for c in range(3):
        tm, ts = t[:, :, c].mean(), t[:, :, c].std() + 1e-6
        sm, ss = s[:, :, c].mean(), s[:, :, c].std() + 1e-6
        t[:, :, c] = (t[:, :, c] - tm) / ts * ss + sm
    out = _out_path(inputs, "colortransfer")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(t, 0, 255).astype(np.uint8)).save(out)
    return {"ok": True, "out": out}


def _n_ImageCropToMask(inputs: dict, ctx: dict) -> dict:
    """裁出一块并给出它的遮罩（整块为白）。"""
    import pathlib
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    from PIL import Image
    img = Image.open(str(src)).convert("RGBA")
    x, y = int(inputs.get("x") or 0), int(inputs.get("y") or 0)
    w, h = int(inputs.get("width") or img.width), int(inputs.get("height") or img.height)
    cropped = img.crop((x, y, x + w, y + h))
    p_out = _out_path(inputs, "croptomask_img")
    pathlib.Path(p_out).parent.mkdir(parents=True, exist_ok=True)
    cropped.save(p_out)
    m_out = str(pathlib.Path(p_out).with_name(pathlib.Path(p_out).stem + "_mask.png"))
    Image.new("L", cropped.size, 255).convert("RGBA").save(m_out)
    return {"ok": True, "out": p_out, "mask": m_out, "size": list(cropped.size)}


def _n_ImageColorSpace(inputs: dict, ctx: dict) -> dict:
    """颜色空间转换（RGB/HSV/LAB/L/CMYK 标签互转，落回 RGB PNG 供后续节点用）。"""
    import pathlib
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    space = str(inputs.get("color_space") or inputs.get("to") or "HSV").upper()
    from PIL import Image
    img = Image.open(str(src)).convert("RGBA")
    try:
        converted = img.convert(space).convert("RGBA")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "user_error: 不支持的颜色空间 %s（%s）" % (space, str(e)[:60])}
    out = _out_path(inputs, "colorspace")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    converted.save(out)
    return {"ok": True, "out": out, "color_space": space}


NODES.update({
    "ConvertArrayToString": {"fn": _n_ConvertArrayToString, "in": ["array", "separator?"],
                             "out": ["STRING"], "writes": False, "desc": "数组 → 字符串（可选分隔符）"},
    "ConvertDictionaryToString": {"fn": _n_ConvertDictionaryToString, "in": ["dict"],
                                  "out": ["STRING"], "writes": False, "desc": "字典 → JSON 字符串"},
    "CropByBBoxes": {"fn": _n_CropByBBoxes, "in": ["image", "out", "bboxes"], "out": ["IMAGE"],
                     "writes": True, "desc": "按 bbox 裁剪（取第一个框）"},
    "ImageHistogram": {"fn": _n_ImageHistogram, "in": ["image"], "out": ["HISTOGRAM"],
                       "writes": False, "desc": "直方图读数（非零桶/峰值）"},
    "ImageCropV2": {"fn": _n_ImageCropV2, "in": ["image", "out", "x?", "y?", "width?", "height?"],
                    "out": ["IMAGE"], "writes": True, "desc": "裁剪 v2（越界夹紧）"},
    "EmptyAudio": {"fn": _n_EmptyAudio, "in": ["out", "duration?", "sample_rate?"],
                   "out": ["AUDIO"], "writes": True, "desc": "生成静音 wav（16bit 单声道）"},
    "ImageCompare": {"fn": _n_ImageCompare, "in": ["image1", "image2"], "out": ["DIFF"],
                     "writes": False, "desc": "两图对比（平均绝对差/是否相同）"},
    "ColorTransfer": {"fn": _n_ColorTransfer, "in": ["image1", "image2", "out"], "out": ["IMAGE"],
                      "writes": True, "desc": "色彩迁移（均值/方差；需 numpy）"},
    "ImageCropToMask": {"fn": _n_ImageCropToMask,
                        "in": ["image", "out", "x?", "y?", "width?", "height?"],
                        "out": ["IMAGE", "MASK"], "writes": True, "desc": "裁块并给出遮罩"},
    "ImageColorSpace": {"fn": _n_ImageColorSpace, "in": ["image", "out", "color_space?"],
                        "out": ["IMAGE"], "writes": True, "desc": "颜色空间转换（RGB/HSV/LAB/L/CMYK）"},
})


# ── 2026-11-01 批次 C：音频/图像/文本三族又 14 个（纯 stdlib + PIL + numpy）──
def _wav_read(path):
    import wave
    wf = wave.open(str(path), "rb")
    params = (wf.getnchannels(), wf.getsampwidth(), wf.getframerate())
    data = wf.readframes(wf.getnframes())
    wf.close()
    return params, data


def _wav_write(path, params, data):
    import pathlib
    import wave
    pth = pathlib.Path(str(path))
    if pth.suffix.lower() != ".wav":
        pth = pth.with_suffix(".wav")
    pth.parent.mkdir(parents=True, exist_ok=True)
    ch, sw, fr = params
    with wave.open(str(pth), "wb") as wf:
        wf.setnchannels(ch)
        wf.setsampwidth(sw)
        wf.setframerate(fr)
        wf.writeframes(data)
    return str(pth)


def _n_AudioAdjustVolume(inputs: dict, ctx: dict) -> dict:
    """音频音量调整（factor）。"""
    import array
    import io
    src = inputs.get("audio") or inputs.get("path")
    if not src:
        return {"ok": False, "error": "user_error: 要 audio（wav）"}
    params, data = _wav_read(src)
    f = float(inputs.get("factor") or inputs.get("volume") or 1.0)
    samples = array.array("h")
    samples.frombytes(data)
    for i in range(len(samples)):
        v = int(samples[i] * f)
        samples[i] = max(-32768, min(32767, v))
    out = _wav_write(_out_path(inputs, "audiovol"), params, samples.tobytes())
    return {"ok": True, "out": out, "factor": f, "samples": len(samples)}


def _n_AudioConcat(inputs: dict, ctx: dict) -> dict:
    """拼接多段 wav（逗号分隔；采样率不一致如实报错）。"""
    srcs = [x.strip() for x in str(inputs.get("audios") or inputs.get("audio") or "").split(",") if x.strip()]
    if len(srcs) < 2:
        return {"ok": False, "error": "user_error: 至少两段音频（逗号分隔）"}
    params0, data0 = _wav_read(srcs[0])
    chunks = [data0]
    for s in srcs[1:]:
        pr, d = _wav_read(s)
        if pr != params0:
            return {"ok": False, "error": "user_error: 采样参数不一致 %s vs %s" % (params0, pr)}
        chunks.append(d)
    out = _wav_write(_out_path(inputs, "audioconcat"), params0, b"".join(chunks))
    return {"ok": True, "out": out, "segments": len(srcs)}


def _n_TrimAudioDuration(inputs: dict, ctx: dict) -> dict:
    """裁剪音频时长（start/end 秒）。"""
    src = inputs.get("audio") or inputs.get("path")
    if not src:
        return {"ok": False, "error": "user_error: 要 audio"}
    params, data = _wav_read(src)
    ch, sw, fr = params
    frame = ch * sw
    total = len(data) // frame
    start = max(0.0, float(inputs.get("start") or 0.0))
    end = float(inputs.get("end") or inputs.get("duration") or (total / fr))
    a = min(total, int(start * fr))
    b = min(total, int(end * fr))
    if b <= a:
        return {"ok": False, "error": "user_error: end 必须大于 start"}
    out = _wav_write(_out_path(inputs, "audiotrim"), params, data[a * frame:b * frame])
    return {"ok": True, "out": out, "start": a / fr, "end": b / fr}


def _n_ImageCompositor(inputs: dict, ctx: dict) -> dict:
    """合成：把 image2 按 mask 叠到 image1 上。"""
    import pathlib
    a, b = inputs.get("image1") or inputs.get("destination"), inputs.get("image2") or inputs.get("source")
    if not a or not b:
        return {"ok": False, "error": "user_error: 要 image1/image2"}
    from PIL import Image
    dst = Image.open(str(a)).convert("RGBA")
    src = Image.open(str(b)).convert("RGBA")
    if src.size != dst.size:
        src = src.resize(dst.size)
    m = inputs.get("mask")
    if m:
        mask = Image.open(str(m)).convert("L").resize(dst.size)
    else:
        mask = src.split()[-1]
    out = _out_path(inputs, "compositor")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    Image.composite(src, dst, mask).save(out)
    return {"ok": True, "out": out}


def _n_ImageDeduplication(inputs: dict, ctx: dict) -> dict:
    """去重：按 8×8 灰度均值指纹判断重复，返回唯一列表与重复项。"""
    import pathlib
    raw = inputs.get("images") or inputs.get("image")
    if not raw:
        return {"ok": False, "error": "user_error: 要 images（逗号分隔）"}
    from PIL import Image
    paths = [x.strip() for x in str(raw).split(",") if x.strip()]
    seen, unique, dup = {}, [], []
    for pth in paths:
        try:
            im = Image.open(pth).convert("L").resize((8, 8))
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": "user_error: 读不到 %s（%s）" % (pth, str(e)[:50])}
        px = list(im.getdata())
        avg = sum(px) / len(px)
        fp = "".join("1" if v >= avg else "0" for v in px)
        if fp in seen:
            dup.append(pth)
        else:
            seen[fp] = pth
            unique.append(pth)
    first = unique[0] if unique else None
    return {"ok": True, "unique": unique, "duplicates": dup,
            "unique_count": len(unique), "dup_count": len(dup),
            "out": first if first else None}


def _n_NormalizeImages(inputs: dict, ctx: dict) -> dict:
    """对比度归一（拉伸到 0–255 全量程；按通道最小/最大）。"""
    import pathlib
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    from PIL import Image
    img = Image.open(str(src)).convert("RGB")
    px = list(img.getdata())
    rs = [p[0] for p in px]
    gs = [p[1] for p in px]
    bs = [p[2] for p in px]
    lo, hi = min(min(rs), min(gs), min(bs)), max(max(rs), max(gs), max(bs))
    span = max(1, hi - lo)
    lut = [max(0, min(255, int((i - lo) * 255 / span))) for i in range(256)]
    out = _out_path(inputs, "normalize")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.point(lut * 3).save(out)
    return {"ok": True, "out": out, "min": lo, "max": hi}


def _n_RepeatImageBatch(inputs: dict, ctx: dict) -> dict:
    """重复 N 张（单图流水里只产出一张，但如实报 amount）。"""
    import pathlib
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    amount = max(1, int(inputs.get("amount") or inputs.get("times") or 2))
    from PIL import Image
    img = Image.open(str(src)).convert("RGBA")
    out = _out_path(inputs, "repeat")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return {"ok": True, "out": out, "amount": amount,
            "note": "单图流水：只落一张（批次概念见 op=run 的 times）"}


def _n_ResizeImagesByLongerEdge(inputs: dict, ctx: dict) -> dict:
    """按**长边**缩放到指定像素。"""
    import pathlib
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    from PIL import Image
    img = Image.open(str(src)).convert("RGBA")
    edge = max(1, int(inputs.get("longer_edge") or inputs.get("size") or 1024))
    scale = edge / max(img.width, img.height)
    size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
    out = _out_path(inputs, "longeredge")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.resize(size, Image.LANCZOS).save(out)
    return {"ok": True, "out": out, "size": list(size)}


def _n_ResizeAndPadImage(inputs: dict, ctx: dict) -> dict:
    """等比缩放到目标框内 + 居中补边。"""
    import pathlib
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    from PIL import Image
    img = Image.open(str(src)).convert("RGBA")
    tw = max(1, int(inputs.get("width") or 1024))
    th = max(1, int(inputs.get("height") or 1024))
    scale = min(tw / img.width, th / img.height)
    size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
    resized = img.resize(size, Image.LANCZOS)
    canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    canvas.paste(resized, ((tw - size[0]) // 2, (th - size[1]) // 2))
    out = _out_path(inputs, "resizepad")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return {"ok": True, "out": out, "size": [tw, th]}


def _n_TextOverlay(inputs: dict, ctx: dict) -> dict:
    """在图上写字（默认字体；位置/大小/颜色可调）。"""
    import pathlib
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    text = str(inputs.get("text") or "")
    from PIL import Image, ImageDraw, ImageFont
    img = Image.open(str(src)).convert("RGBA")
    draw = ImageDraw.Draw(img)
    size = int(inputs.get("font_size") or 16)
    try:
        font = ImageFont.load_default(size=size)
    except Exception:  # noqa: BLE001
        font = ImageFont.load_default()
    color = inputs.get("color") or "#FFFFFF"
    if isinstance(color, int):
        color = "#%06X" % color
    draw.text((int(inputs.get("x") or 4), int(inputs.get("y") or 4)), text,
              fill=str(color), font=font)
    out = _out_path(inputs, "textoverlay")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return {"ok": True, "out": out, "text": text[:60]}


def _n_TextToLowercase(inputs: dict, ctx: dict) -> dict:
    return {"ok": True, "text": str(inputs.get("text") or "").lower()}


def _n_TextToUppercase(inputs: dict, ctx: dict) -> dict:
    return {"ok": True, "text": str(inputs.get("text") or "").upper()}


def _n_TruncateText(inputs: dict, ctx: dict) -> dict:
    text = str(inputs.get("text") or "")
    n = max(0, int(inputs.get("max_length") or inputs.get("length") or 100))
    return {"ok": True, "text": text[:n], "truncated": len(text) > n}


def _n_ReplaceText(inputs: dict, ctx: dict) -> dict:
    text = str(inputs.get("text") or "")
    find = str(inputs.get("find") or inputs.get("old") or "")
    repl = str(inputs.get("replace") or inputs.get("new") or "")
    if not find:
        return {"ok": False, "error": "user_error: 要 find"}
    return {"ok": True, "text": text.replace(find, repl),
            "replaced": text.count(find)}


NODES.update({
    "AudioAdjustVolume": {"fn": _n_AudioAdjustVolume, "in": ["audio", "out", "factor?"],
                          "out": ["AUDIO"], "writes": True, "desc": "音量调整（wav 增益）"},
    "AudioConcat": {"fn": _n_AudioConcat, "in": ["audios", "out"], "out": ["AUDIO"],
                    "writes": True, "desc": "拼接多段 wav（参数须一致）"},
    "TrimAudioDuration": {"fn": _n_TrimAudioDuration, "in": ["audio", "out", "start?", "end?"],
                          "out": ["AUDIO"], "writes": True, "desc": "裁剪音频时长（start/end 秒）"},
    "ImageCompositor": {"fn": _n_ImageCompositor, "in": ["image1", "image2", "out", "mask?"],
                        "out": ["IMAGE"], "writes": True, "desc": "按遮罩把 image2 叠到 image1"},
    "ImageDeduplication": {"fn": _n_ImageDeduplication, "in": ["images"], "out": ["IMAGE", "LIST"],
                           "writes": False, "desc": "按 8×8 指纹去重（返回唯一/重复）"},
    "NormalizeImages": {"fn": _n_NormalizeImages, "in": ["image", "out"], "out": ["IMAGE"],
                        "writes": True, "desc": "对比度归一（拉伸全量程）"},
    "RepeatImageBatch": {"fn": _n_RepeatImageBatch, "in": ["image", "out", "amount?"],
                         "out": ["IMAGE"], "writes": True, "desc": "重复 N 张（单图只落一张）"},
    "ResizeImagesByLongerEdge": {"fn": _n_ResizeImagesByLongerEdge,
                                 "in": ["image", "out", "longer_edge?"], "out": ["IMAGE"],
                                 "writes": True, "desc": "按长边缩放"},
    "ResizeAndPadImage": {"fn": _n_ResizeAndPadImage,
                          "in": ["image", "out", "width?", "height?"], "out": ["IMAGE"],
                          "writes": True, "desc": "等比缩放 + 居中补边"},
    "TextOverlay": {"fn": _n_TextOverlay, "in": ["image", "out", "text", "x?", "y?", "font_size?", "color?"],
                    "out": ["IMAGE"], "writes": True, "desc": "在图上写字"},
    "TextToLowercase": {"fn": _n_TextToLowercase, "in": ["text"], "out": ["STRING"],
                        "writes": False, "desc": "转小写"},
    "TextToUppercase": {"fn": _n_TextToUppercase, "in": ["text"], "out": ["STRING"],
                        "writes": False, "desc": "转大写"},
    "TruncateText": {"fn": _n_TruncateText, "in": ["text", "max_length?"], "out": ["STRING"],
                     "writes": False, "desc": "截断到 max_length"},
    "ReplaceText": {"fn": _n_ReplaceText, "in": ["text", "find", "replace"], "out": ["STRING"],
                    "writes": False, "desc": "替换文本（返回替换次数）"},
})


# ── 2026-11-01 批次 D：音频通道/裁切/文本落盘又 11 个（只挑真的能实现的，不凑数）──
def _n_LoadAudio(inputs: dict, ctx: dict) -> dict:
    """读 wav（只读）：返回路径与参数，不落盘。"""
    src = inputs.get("audio") or inputs.get("path") or inputs.get("audio_file")
    if not src:
        return {"ok": False, "error": "user_error: 要 audio 路径"}
    try:
        params, data = _wav_read(src)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "user_error: 读不到 wav（%s）" % str(e)[:60]}
    ch, sw, fr = params
    return {"ok": True, "audio": str(src), "channels": ch, "sample_width": sw,
            "sample_rate": fr, "frames": len(data) // (ch * sw),
            "duration": round(len(data) / (ch * sw * fr), 3)}


def _n_SaveAudio(inputs: dict, ctx: dict) -> dict:
    """落盘音频（wav 原样拷贝，过闸前先写临时？这里直写 out）。"""
    import pathlib
    import shutil
    src = inputs.get("audio") or inputs.get("path")
    if not src:
        return {"ok": False, "error": "user_error: 要 audio"}
    out = _out_path(inputs, "saveaudio")
    pth = pathlib.Path(str(out))
    if pth.suffix.lower() != ".wav":
        pth = pth.with_suffix(".wav")
    pth.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(src), str(pth))
    return {"ok": True, "out": str(pth), "bytes": pth.stat().st_size}


def _n_PreviewAudio(inputs: dict, ctx: dict) -> dict:
    """预览音频（拷一份到 preview_*.wav，不动原文件）。"""
    import pathlib
    import shutil
    src = inputs.get("audio") or inputs.get("path")
    if not src:
        return {"ok": False, "error": "user_error: 要 audio"}
    d = _store() / "comfy_native"
    d.mkdir(parents=True, exist_ok=True)
    out = d / ("preview_%d.wav" % (int(time.time() * 1000) % 1000000))
    shutil.copyfile(str(src), str(out))
    return {"ok": True, "out": str(out), "preview": True}


def _n_SplitAudioChannels(inputs: dict, ctx: dict) -> dict:
    """立体声拆左右（写出 L，返回 R 路径）；单声道原样。"""
    import array
    import pathlib
    src = inputs.get("audio") or inputs.get("path")
    if not src:
        return {"ok": False, "error": "user_error: 要 audio"}
    params, data = _wav_read(src)
    ch, sw, fr = params
    if ch < 2:
        out = _wav_write(_out_path(inputs, "splitch"), params, data)
        return {"ok": True, "out": out, "channels": 1, "note": "单声道无需拆分"}
    samples = array.array("h")
    samples.frombytes(data)
    left = array.array("h", samples[0::2])
    right = array.array("h", samples[1::2])
    mono = (1, 2, fr)
    out_l = _wav_write(_out_path(inputs, "splitch_L"), mono, left.tobytes())
    out_r = _wav_write(str(pathlib.Path(out_l).with_name(pathlib.Path(out_l).stem + "_R.wav")),
                       mono, right.tobytes())
    return {"ok": True, "out": out_l, "right": out_r, "channels": 2}


def _n_JoinAudioChannels(inputs: dict, ctx: dict) -> dict:
    """左 + 右 → 立体声（参数须一致）。"""
    import array
    left = inputs.get("left") or inputs.get("audio1")
    right = inputs.get("right") or inputs.get("audio2")
    if not left or not right:
        return {"ok": False, "error": "user_error: 要 left/right"}
    pl, dl = _wav_read(left)
    pr, dr = _wav_read(right)
    if pl[2] != pr[2] or pl[1] != pr[1]:
        return {"ok": False, "error": "user_error: 采样率/位宽不一致"}
    al = array.array("h"); al.frombytes(dl)
    ar = array.array("h"); ar.frombytes(dr)
    n = min(len(al), len(ar))
    out = array.array("h")
    for i in range(n):
        out.append(al[i]); out.append(ar[i])
    pth = _wav_write(_out_path(inputs, "joinch"), (2, 2, pl[2]), out.tobytes())
    return {"ok": True, "out": pth, "channels": 2, "frames": n}


def _n_AudioEqualizer3Band(inputs: dict, ctx: dict) -> dict:
    """三频段均衡（低/中/高增益，dB；numpy FFT 实现）。"""
    try:
        import numpy as np
    except Exception:  # noqa: BLE001
        return {"ok": False, "error": "needs_dependency: numpy 缺失"}
    import array
    src = inputs.get("audio") or inputs.get("path")
    if not src:
        return {"ok": False, "error": "user_error: 要 audio"}
    params, data = _wav_read(src)
    ch, sw, fr = params
    samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    if ch > 1:
        samples = samples.reshape(-1, ch).mean(axis=1)
    spec = np.fft.rfft(samples)
    freqs = np.fft.rfftfreq(len(samples), d=1.0 / fr)
    low_g = 10 ** (float(inputs.get("low") or 0.0) / 20.0)
    mid_g = 10 ** (float(inputs.get("mid") or 0.0) / 20.0)
    high_g = 10 ** (float(inputs.get("high") or 0.0) / 20.0)
    gains = np.ones_like(freqs)
    gains[freqs < 250] = low_g
    gains[(freqs >= 250) & (freqs < 4000)] = mid_g
    gains[freqs >= 4000] = high_g
    out_s = np.fft.irfft(spec * gains, n=len(samples))
    out_i = np.clip(out_s, -32768, 32767).astype(np.int16)
    pth = _wav_write(_out_path(inputs, "eq3"), (1, 2, fr), out_i.tobytes())
    return {"ok": True, "out": pth, "low_db": float(inputs.get("low") or 0.0),
            "mid_db": float(inputs.get("mid") or 0.0), "high_db": float(inputs.get("high") or 0.0)}


def _n_RebatchImages(inputs: dict, ctx: dict) -> dict:
    """重分批（单图流水：如实报 batch_size，只落一张）。"""
    import pathlib
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    size = max(1, int(inputs.get("batch_size") or 1))
    from PIL import Image
    img = Image.open(str(src)).convert("RGBA")
    out = _out_path(inputs, "rebatch")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return {"ok": True, "out": out, "batch_size": size,
            "note": "单图流水：只落一张"}


def _n_RandomCropImages(inputs: dict, ctx: dict) -> dict:
    """随机裁剪（seed 可复现；返回实际框）。"""
    import pathlib
    import random
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    from PIL import Image
    img = Image.open(str(src)).convert("RGBA")
    w = min(img.width, int(inputs.get("width") or img.width))
    h = min(img.height, int(inputs.get("height") or img.height))
    rnd = random.Random(int(inputs.get("seed") or 0))
    x = rnd.randint(0, max(0, img.width - w))
    y = rnd.randint(0, max(0, img.height - h))
    out = _out_path(inputs, "randcrop")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.crop((x, y, x + w, y + h)).save(out)
    return {"ok": True, "out": out, "box": [x, y, w, h], "seed": int(inputs.get("seed") or 0)}


def _n_ResizeImagesByShorterEdge(inputs: dict, ctx: dict) -> dict:
    """按**短边**缩放到指定像素。"""
    import pathlib
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    from PIL import Image
    img = Image.open(str(src)).convert("RGBA")
    edge = max(1, int(inputs.get("shorter_edge") or inputs.get("size") or 512))
    scale = edge / min(img.width, img.height)
    size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
    out = _out_path(inputs, "shorteredge")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.resize(size, Image.LANCZOS).save(out)
    return {"ok": True, "out": out, "size": list(size)}


def _n_ImageScaleToTotalPixels(inputs: dict, ctx: dict) -> dict:
    """缩放到目标总像素数（如 1MP = 1000000）。"""
    import math
    import pathlib
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    from PIL import Image
    img = Image.open(str(src)).convert("RGBA")
    target = float(inputs.get("megapixels") or inputs.get("total_pixels") or 1.0)
    if target <= 10:          # 传的是 MP
        target = target * 1_000_000
    scale = math.sqrt(target / (img.width * img.height))
    size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
    out = _out_path(inputs, "totalpixels")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.resize(size, Image.LANCZOS).save(out)
    return {"ok": True, "out": out, "size": list(size),
            "pixels": size[0] * size[1]}


def _n_SaveText(inputs: dict, ctx: dict) -> dict:
    """把文本落盘（.txt/.md 由 out 决定）。"""
    import pathlib
    text = str(inputs.get("text") or "")
    out = _out_path(inputs, "savetext")
    pth = pathlib.Path(str(out))
    if pth.suffix.lower() not in (".txt", ".md", ".json"):
        pth = pth.with_suffix(".txt")
    pth.parent.mkdir(parents=True, exist_ok=True)
    pth.write_text(text, encoding="utf-8")
    return {"ok": True, "out": str(pth), "chars": len(text)}


NODES.update({
    "LoadAudio": {"fn": _n_LoadAudio, "in": ["audio?"], "out": ["AUDIO", "INFO"],
                  "writes": False, "desc": "读 wav（只读，回参数）"},
    "SaveAudio": {"fn": _n_SaveAudio, "in": ["audio", "out"], "out": ["AUDIO"],
                  "writes": True, "desc": "落盘 wav"},
    "PreviewAudio": {"fn": _n_PreviewAudio, "in": ["audio"], "out": ["AUDIO"],
                     "writes": True, "desc": "预览音频（拷一份 preview_*.wav）"},
    "SplitAudioChannels": {"fn": _n_SplitAudioChannels, "in": ["audio", "out"], "out": ["AUDIO"],
                           "writes": True, "desc": "立体声拆 L/R（写出 L，返回 R）"},
    "JoinAudioChannels": {"fn": _n_JoinAudioChannels, "in": ["left", "right", "out"],
                          "out": ["AUDIO"], "writes": True, "desc": "L+R → 立体声"},
    "AudioEqualizer3Band": {"fn": _n_AudioEqualizer3Band,
                            "in": ["audio", "out", "low?", "mid?", "high?"], "out": ["AUDIO"],
                            "writes": True, "desc": "三频段均衡（dB，numpy FFT）"},
    "RebatchImages": {"fn": _n_RebatchImages, "in": ["image", "out", "batch_size?"],
                      "out": ["IMAGE"], "writes": True, "desc": "重分批（单图流水只落一张）"},
    "RandomCropImages": {"fn": _n_RandomCropImages,
                         "in": ["image", "out", "width?", "height?", "seed?"], "out": ["IMAGE"],
                         "writes": True, "desc": "随机裁剪（seed 可复现）"},
    "ResizeImagesByShorterEdge": {"fn": _n_ResizeImagesByShorterEdge,
                                  "in": ["image", "out", "shorter_edge?"], "out": ["IMAGE"],
                                  "writes": True, "desc": "按短边缩放"},
    "ImageScaleToTotalPixels": {"fn": _n_ImageScaleToTotalPixels,
                                "in": ["image", "out", "megapixels?"], "out": ["IMAGE"],
                                "writes": True, "desc": "缩放到目标总像素（MP）"},
    "SaveText": {"fn": _n_SaveText, "in": ["text", "out"], "out": ["STRING"],
                 "writes": True, "desc": "文本落盘（.txt/.md/.json）"},
})


# ── 2026-11-01 批次 E：数据集/瓦片/SVG 落盘又 11 个（复核后只留真能纯 CPU 的）──
def _n_FlipSigmas(inputs: dict, ctx: dict) -> dict:
    """翻转 sigma 序列（列表）；传字符串则按逗号拆。"""
    raw = inputs.get("sigmas", inputs.get("values"))
    if isinstance(raw, str):
        raw = [float(x) for x in raw.replace(";", ",").split(",") if x.strip()]
    if not isinstance(raw, (list, tuple)):
        return {"ok": False, "error": "user_error: 要 sigmas（列表或逗号串）"}
    out = list(reversed([float(x) for x in raw]))
    return {"ok": True, "sigmas": out, "count": len(out)}


def _n_BatchImagesNode(inputs: dict, ctx: dict) -> dict:
    """多图合成一批（单图流水：校验路径存在并返回首个）。"""
    import pathlib
    raw = inputs.get("images") or inputs.get("image")
    if not raw:
        return {"ok": False, "error": "user_error: 要 images"}
    paths = [x.strip() for x in str(raw).split(",") if x.strip()]
    missing = [p for p in paths if not pathlib.Path(p).exists()]
    if missing:
        return {"ok": False, "error": "user_error: 文件不在：%s" % missing[:3]}
    return {"ok": True, "count": len(paths), "images": paths, "out": paths[0]}


def _n_BatchMasksNode(inputs: dict, ctx: dict) -> dict:
    """多遮罩合成一批（同上，校验存在）。"""
    import pathlib
    raw = inputs.get("masks") or inputs.get("mask")
    if not raw:
        return {"ok": False, "error": "user_error: 要 masks"}
    paths = [x.strip() for x in str(raw).split(",") if x.strip()]
    missing = [p for p in paths if not pathlib.Path(p).exists()]
    if missing:
        return {"ok": False, "error": "user_error: 文件不在：%s" % missing[:3]}
    return {"ok": True, "count": len(paths), "masks": paths, "out": paths[0]}


def _n_SplitImageToTileList(inputs: dict, ctx: dict) -> dict:
    """把图切成 tile 并落盘，返回 tile 列表（rows×cols）。"""
    import pathlib
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    from PIL import Image
    img = Image.open(str(src)).convert("RGBA")
    cols = max(1, int(inputs.get("columns") or 2))
    rows = max(1, int(inputs.get("rows") or 2))
    tw, th = img.width // cols, img.height // rows
    if tw <= 0 or th <= 0:
        return {"ok": False, "error": "user_error: tile 尺寸为 0（rows/cols 太大）"}
    base = pathlib.Path(str(_out_path(inputs, "tile")))
    base.parent.mkdir(parents=True, exist_ok=True)
    tiles = []
    for r in range(rows):
        for c in range(cols):
            tp = base.with_name("%s_t%02d.png" % (base.stem, r * cols + c))
            img.crop((c * tw, r * th, (c + 1) * tw, (r + 1) * th)).save(tp)
            tiles.append(str(tp))
    return {"ok": True, "out": tiles[0], "tiles": tiles, "tile_size": [tw, th],
            "count": len(tiles)}


def _n_SaveImageAdvanced(inputs: dict, ctx: dict) -> dict:
    """落盘图（可指定质量/压缩级别；PNG 用 compress_level）。"""
    import pathlib
    src = inputs.get("image")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    from PIL import Image
    img = Image.open(str(src)).convert("RGBA")
    out = _out_path(inputs, "saveadv")
    pth = pathlib.Path(str(out))
    pth.parent.mkdir(parents=True, exist_ok=True)
    fmt = pth.suffix.lower().lstrip(".") or "png"
    kwargs = {}
    if fmt in ("jpg", "jpeg", "webp"):
        kwargs["quality"] = max(1, min(100, int(inputs.get("quality") or 90)))
    elif fmt == "png":
        kwargs["compress_level"] = max(0, min(9, int(inputs.get("compress_level") or 6)))
    img.save(str(pth), **kwargs)
    return {"ok": True, "out": str(pth), "format": fmt, "kwargs": kwargs}


def _n_LoadImageDataSetFromFolder(inputs: dict, ctx: dict) -> dict:
    """扫文件夹里的图（只读）：返回清单与数量。"""
    import pathlib
    folder = inputs.get("folder") or inputs.get("directory") or inputs.get("path")
    if not folder:
        return {"ok": False, "error": "user_error: 要 folder"}
    d = pathlib.Path(str(folder))
    if not d.is_dir():
        return {"ok": False, "error": "user_error: 不是目录：%s" % d}
    exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    files = sorted(str(p) for p in d.rglob("*") if p.suffix.lower() in exts)
    return {"ok": True, "images": files, "count": len(files), "folder": str(d)}


def _n_LoadImageTextDataSetFromFolder(inputs: dict, ctx: dict) -> dict:
    """扫「图 + 同名 txt」配对数据集（只读）。"""
    import pathlib
    folder = inputs.get("folder") or inputs.get("directory")
    if not folder:
        return {"ok": False, "error": "user_error: 要 folder"}
    d = pathlib.Path(str(folder))
    if not d.is_dir():
        return {"ok": False, "error": "user_error: 不是目录：%s" % d}
    exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
    pairs, unpaired = [], []
    for p in sorted(d.rglob("*")):
        if p.suffix.lower() not in exts:
            continue
        cap = p.with_suffix(".txt")
        if cap.exists():
            pairs.append({"image": str(p), "text": str(cap)})
        else:
            unpaired.append(str(p))
    return {"ok": True, "pairs": pairs, "count": len(pairs), "unpaired": len(unpaired)}


def _n_SaveImageDataSetToFolder(inputs: dict, ctx: dict) -> dict:
    """把图集合存到目标文件夹（复制；同名跳过）。"""
    import pathlib
    import shutil
    raw = inputs.get("images") or inputs.get("image")
    folder = inputs.get("folder") or inputs.get("directory")
    if not raw or not folder:
        return {"ok": False, "error": "user_error: 要 images 与 folder"}
    d = pathlib.Path(str(folder))
    d.mkdir(parents=True, exist_ok=True)
    saved, skipped = [], 0
    for src in [x.strip() for x in str(raw).split(",") if x.strip()]:
        p = pathlib.Path(src)
        if not p.exists():
            skipped += 1
            continue
        dst = d / p.name
        if dst.exists():
            skipped += 1
            continue
        shutil.copy2(str(p), str(dst))
        saved.append(str(dst))
    return {"ok": True, "saved": saved, "count": len(saved), "skipped": skipped}


def _n_SaveImageTextDataSetToFolder(inputs: dict, ctx: dict) -> dict:
    """把「图 + 文本」配对存到目录（img 复制 + 同名 txt 写入）。"""
    import pathlib
    import shutil
    raw = inputs.get("images") or inputs.get("image")
    text = str(inputs.get("text") or "")
    folder = inputs.get("folder") or inputs.get("directory")
    if not raw or not folder:
        return {"ok": False, "error": "user_error: 要 images/text/folder"}
    d = pathlib.Path(str(folder))
    d.mkdir(parents=True, exist_ok=True)
    saved = []
    for src in [x.strip() for x in str(raw).split(",") if x.strip()]:
        p = pathlib.Path(src)
        if not p.exists():
            continue
        dst = d / p.name
        shutil.copy2(str(p), str(dst))
        cap = dst.with_suffix(".txt")
        cap.write_text(text, encoding="utf-8")
        saved.append({"image": str(dst), "text": str(cap)})
    return {"ok": True, "pairs": saved, "count": len(saved)}


def _n_ShuffleImageTextDataset(inputs: dict, ctx: dict) -> dict:
    """打乱「图+文本」配对（seed 可复现；只重排，不动文件）。"""
    import random
    raw = inputs.get("pairs") or inputs.get("dataset")
    if isinstance(raw, str):
        raw = [x.strip() for x in raw.split(",") if x.strip()]
    if not isinstance(raw, (list, tuple)):
        return {"ok": False, "error": "user_error: 要 pairs（列表或逗号串）"}
    items = list(raw)
    random.Random(int(inputs.get("seed") or 0)).shuffle(items)
    return {"ok": True, "pairs": items, "count": len(items), "seed": int(inputs.get("seed") or 0)}


def _n_QuiverTextToSVGNodeV2(inputs: dict, ctx: dict) -> dict:
    """文本 → 简单 SVG（只做纯文本排布，不依赖模型）。"""
    import pathlib
    text = str(inputs.get("text") or "")
    if not text:
        return {"ok": False, "error": "user_error: 要 text"}
    lines = text.splitlines() or [text]
    w = int(inputs.get("width") or 512)
    lh = int(inputs.get("line_height") or 20)
    h = max(lh, lh * len(lines) + 20)
    esc = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    body = "".join(
        '<text x="10" y="%d" font-family="sans-serif" font-size="%d" fill="#fff">%s</text>'
        % (20 + i * lh, lh - 4, ln.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        for i, ln in enumerate(lines))
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">'
           '<rect width="100%%" height="100%%" fill="#111"/>%s</svg>' % (w, h, body))
    out = _out_path(inputs, "svg")
    pth = pathlib.Path(str(out))
    if pth.suffix.lower() != ".svg":
        pth = pth.with_suffix(".svg")
    pth.parent.mkdir(parents=True, exist_ok=True)
    pth.write_text(svg, encoding="utf-8")
    return {"ok": True, "out": str(pth), "lines": len(lines), "chars": len(esc)}


NODES.update({
    "FlipSigmas": {"fn": _n_FlipSigmas, "in": ["sigmas"], "out": ["SIGMAS"],
                   "writes": False, "desc": "翻转 sigma 序列"},
    "BatchImagesNode": {"fn": _n_BatchImagesNode, "in": ["images"], "out": ["IMAGE", "LIST"],
                        "writes": False, "desc": "多图成批（校验存在，返回首个）"},
    "BatchMasksNode": {"fn": _n_BatchMasksNode, "in": ["masks"], "out": ["MASK", "LIST"],
                       "writes": False, "desc": "多遮罩成批（校验存在）"},
    "SplitImageToTileList": {"fn": _n_SplitImageToTileList, "in": ["image", "out", "columns?", "rows?"],
                             "out": ["IMAGE", "LIST"], "writes": True,
                             "desc": "切成 tile 并返回列表"},
    "SaveImageAdvanced": {"fn": _n_SaveImageAdvanced, "in": ["image", "out", "quality?", "compress_level?"],
                          "out": ["IMAGE"], "writes": True, "desc": "落盘（质量/压缩可调）"},
    "LoadImageDataSetFromFolder": {"fn": _n_LoadImageDataSetFromFolder, "in": ["folder"],
                                   "out": ["LIST"], "writes": False, "desc": "扫文件夹里的图"},
    "LoadImageTextDataSetFromFolder": {"fn": _n_LoadImageTextDataSetFromFolder, "in": ["folder"],
                                       "out": ["LIST"], "writes": False,
                                       "desc": "扫图+txt 配对数据集"},
    "SaveImageDataSetToFolder": {"fn": _n_SaveImageDataSetToFolder, "in": ["images", "folder"],
                                 "out": ["LIST"], "writes": True, "desc": "图集合存目录（同名跳过）"},
    "SaveImageTextDataSetToFolder": {"fn": _n_SaveImageTextDataSetToFolder,
                                     "in": ["images", "text", "folder"], "out": ["LIST"],
                                     "writes": True, "desc": "图+文本配对存目录"},
    "ShuffleImageTextDataset": {"fn": _n_ShuffleImageTextDataset, "in": ["pairs", "seed?"],
                                "out": ["LIST"], "writes": False, "desc": "打乱配对（seed 可复现）"},
    "QuiverTextToSVGNodeV2": {"fn": _n_QuiverTextToSVGNodeV2, "in": ["text", "out", "width?"],
                              "out": ["SVG"], "writes": True, "desc": "文本 → 简单 SVG"},
})


# ── 2026-11-01 批次 F：纯 CPU 收尾 4 个（Porter-Duff / 动图 PNG·WEBP / 音频高级落盘）──
def _n_PorterDuffImageComposite(inputs: dict, ctx: dict) -> dict:
    """Porter-Duff 合成（source-over / multiply / screen / add / difference 子集）。"""
    import pathlib
    a = inputs.get("image1") or inputs.get("destination")
    b = inputs.get("image2") or inputs.get("source")
    if not a or not b:
        return {"ok": False, "error": "user_error: 要 image1/image2"}
    from PIL import Image, ImageChops
    dst = Image.open(str(a)).convert("RGBA")
    src = Image.open(str(b)).convert("RGBA")
    if src.size != dst.size:
        src = src.resize(dst.size)
    mode = str(inputs.get("mode") or inputs.get("blend_mode") or "source-over").lower()
    if mode in ("source-over", "source_over", "over"):
        out_img = Image.alpha_composite(dst, src)
    elif mode == "multiply":
        out_img = ImageChops.multiply(dst.convert("RGB"), src.convert("RGB")).convert("RGBA")
    elif mode == "screen":
        out_img = ImageChops.screen(dst.convert("RGB"), src.convert("RGB")).convert("RGBA")
    elif mode == "add":
        out_img = ImageChops.add(dst.convert("RGB"), src.convert("RGB")).convert("RGBA")
    elif mode == "difference":
        out_img = ImageChops.difference(dst.convert("RGB"), src.convert("RGB")).convert("RGBA")
    else:
        return {"ok": False, "error": "user_error: 不支持的 mode %s（source-over/multiply/screen/add/difference）" % mode}
    out = _out_path(inputs, "porterduff")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    out_img.save(out)
    return {"ok": True, "out": out, "mode": mode}


def _n_SaveAnimatedPNG(inputs: dict, ctx: dict) -> dict:
    """把多帧存成动图 PNG（APNG；PIL 支持 save_all）。"""
    import pathlib
    raw = inputs.get("images") or inputs.get("frames")
    if not raw:
        return {"ok": False, "error": "user_error: 要 images（逗号分隔的帧）"}
    from PIL import Image
    paths = [x.strip() for x in str(raw).split(",") if x.strip()]
    if len(paths) < 2:
        return {"ok": False, "error": "user_error: 至少两帧"}
    frames = [Image.open(p).convert("RGBA") for p in paths]
    out = _out_path(inputs, "apng")
    pth = pathlib.Path(str(out))
    if pth.suffix.lower() != ".png":
        pth = pth.with_suffix(".png")
    pth.parent.mkdir(parents=True, exist_ok=True)
    dur = int(inputs.get("duration") or 100)
    frames[0].save(str(pth), save_all=True, append_images=frames[1:],
                   duration=dur, loop=int(inputs.get("loop") or 0))
    return {"ok": True, "out": str(pth), "frames": len(frames), "duration_ms": dur}


def _n_SaveAnimatedWEBP(inputs: dict, ctx: dict) -> dict:
    """把多帧存成动图 WEBP。"""
    import pathlib
    raw = inputs.get("images") or inputs.get("frames")
    if not raw:
        return {"ok": False, "error": "user_error: 要 images（逗号分隔的帧）"}
    from PIL import Image
    paths = [x.strip() for x in str(raw).split(",") if x.strip()]
    if len(paths) < 2:
        return {"ok": False, "error": "user_error: 至少两帧"}
    frames = [Image.open(p).convert("RGB") for p in paths]
    out = _out_path(inputs, "awebp")
    pth = pathlib.Path(str(out))
    if pth.suffix.lower() != ".webp":
        pth = pth.with_suffix(".webp")
    pth.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(str(pth), save_all=True, append_images=frames[1:],
                   duration=int(inputs.get("duration") or 100),
                   loop=int(inputs.get("loop") or 0),
                   quality=int(inputs.get("quality") or 80))
    return {"ok": True, "out": str(pth), "frames": len(frames)}


def _n_SaveAudioAdvanced(inputs: dict, ctx: dict) -> dict:
    """音频高级落盘（wav 原样拷 + 如实回参数；MP3/Opus 需 ffmpeg，这里明确不接）。"""
    import pathlib
    import shutil
    src = inputs.get("audio") or inputs.get("path")
    if not src:
        return {"ok": False, "error": "user_error: 要 audio"}
    out = _out_path(inputs, "saveaudioadv")
    pth = pathlib.Path(str(out))
    if pth.suffix.lower() != ".wav":
        return {"ok": False, "error": "needs_dependency: 只接 wav；%s 需要 ffmpeg（本机没有）"
                % pth.suffix.lower()}
    pth.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(src), str(pth))
    params, _data = _wav_read(src)
    return {"ok": True, "out": str(pth), "channels": params[0],
            "sample_rate": params[2], "bytes": pth.stat().st_size}


NODES.update({
    "PorterDuffImageComposite": {"fn": _n_PorterDuffImageComposite,
                                 "in": ["image1", "image2", "out", "mode?"], "out": ["IMAGE"],
                                 "writes": True, "desc": "Porter-Duff 合成（over/multiply/screen/add/difference）"},
    "SaveAnimatedPNG": {"fn": _n_SaveAnimatedPNG, "in": ["images", "out", "duration?", "loop?"],
                        "out": ["IMAGE"], "writes": True, "desc": "多帧 → 动图 PNG（APNG）"},
    "SaveAnimatedWEBP": {"fn": _n_SaveAnimatedWEBP, "in": ["images", "out", "duration?", "loop?", "quality?"],
                         "out": ["IMAGE"], "writes": True, "desc": "多帧 → 动图 WEBP"},
    "SaveAudioAdvanced": {"fn": _n_SaveAudioAdvanced, "in": ["audio", "out"], "out": ["AUDIO"],
                          "writes": True, "desc": "音频落盘（只接 wav；MP3/Opus 如实不接）"},
})


# ── 2026-11-02 · 秋叶取食清单唯一 remaining useful：ImageAddNoise ──
def _n_ImageAddNoise(inputs: dict, ctx: dict) -> dict:
    """ComfyUI 同名：给图像加高斯噪声（seed 可复现，strength 0~1）。"""
    import numpy as np
    from PIL import Image

    src = inputs.get("image") or inputs.get("path")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    strength = float(inputs.get("strength") if inputs.get("strength") is not None else 0.1)
    strength = max(0.0, min(1.0, strength))
    seed = int(inputs.get("seed") or 0)
    img = Image.open(str(src)).convert("RGBA")
    arr = np.asarray(img).astype(np.float32)
    rng = np.random.default_rng(seed)
    noise = rng.normal(0.0, 255.0 * strength, arr[:, :, :3].shape)
    arr[:, :, :3] = np.clip(arr[:, :, :3] + noise, 0, 255)
    out_img = Image.fromarray(arr.astype(np.uint8), "RGBA")
    out = _save(out_img, inputs, "addnoise")
    return {"ok": True, "out": out, "seed": seed, "strength": strength,
            "width": out_img.width, "height": out_img.height}


NODES["ImageAddNoise"] = {
    "fn": _n_ImageAddNoise,
    "in": ["image", "out", "seed?", "strength?"],
    "out": ["IMAGE"],
    "writes": True,
    "desc": "图像加高斯噪声（ComfyUI 同名；seed 可复现）",
}


# ── 2026-11-02 · 天真第二批：核心面纯 CPU 结构/字符串节点（20 个）──
# 这些节点不产图、不碰模型/云端，只用 Python 类型与字符串；可安全接秋叶图的值传递。
def _n_PrimitiveString(inputs, ctx):
    return {"ok": True, "value": str(inputs.get("value") or "")}


def _n_PrimitiveStringMultiline(inputs, ctx):
    return {"ok": True, "value": str(inputs.get("value") or "")}


def _n_PrimitiveInt(inputs, ctx):
    try:
        return {"ok": True, "value": int(inputs.get("value") or 0)}
    except (TypeError, ValueError):
        return {"ok": False, "error": "user_error: PrimitiveInt 要整数"}


def _n_PrimitiveFloat(inputs, ctx):
    try:
        return {"ok": True, "value": float(inputs.get("value") or 0.0)}
    except (TypeError, ValueError):
        return {"ok": False, "error": "user_error: PrimitiveFloat 要数字"}


def _n_PrimitiveBoolean(inputs, ctx):
    v = inputs.get("value")
    if isinstance(v, str):
        v = v.strip().lower() in ("1", "true", "yes", "on")
    return {"ok": True, "value": bool(v)}


def _n_PrimitiveBoundingBox(inputs, ctx):
    return {"ok": True, "value": inputs.get("value") or [0, 0, 0, 0]}


def _n_InvertBooleanNode(inputs, ctx):
    v = inputs.get("value", inputs.get("boolean"))
    if isinstance(v, str):
        v = v.strip().lower() in ("1", "true", "yes", "on")
    return {"ok": True, "value": not bool(v)}


def _n_StringCompare(inputs, ctx):
    a = str(inputs.get("a", inputs.get("string_a", "")))
    b = str(inputs.get("b", inputs.get("string_b", "")))
    op = str(inputs.get("op") or "eq").lower()
    return {"ok": True, "value": (a == b) if op in ("eq", "==", "equal") else (a != b)}


def _n_StringConcatenate(inputs, ctx):
    a = str(inputs.get("a", inputs.get("string_a", "")))
    b = str(inputs.get("b", inputs.get("string_b", "")))
    sep = str(inputs.get("separator") or "")
    return {"ok": True, "value": a + sep + b}


def _n_StringContains(inputs, ctx):
    s = str(inputs.get("string") or inputs.get("text") or "")
    sub = str(inputs.get("substring") or inputs.get("find") or "")
    return {"ok": True, "value": sub in s}


def _n_StringLength(inputs, ctx):
    s = str(inputs.get("string") or inputs.get("text") or "")
    return {"ok": True, "value": len(s)}


def _n_StringReplace(inputs, ctx):
    s = str(inputs.get("string") or inputs.get("text") or "")
    find = str(inputs.get("find") or inputs.get("old") or "")
    repl = str(inputs.get("replace") or inputs.get("new") or "")
    return {"ok": True, "value": s.replace(find, repl) if find else s}


def _n_StringSubstring(inputs, ctx):
    s = str(inputs.get("string") or inputs.get("text") or "")
    start = int(inputs.get("start") or 0)
    length = inputs.get("length")
    return {"ok": True, "value": s[start:start + int(length)] if length is not None else s[start:]}


def _n_StringTrim(inputs, ctx):
    return {"ok": True, "value": str(inputs.get("string") or inputs.get("text") or "").strip()}


def _n_JsonExtractString(inputs, ctx):
    import json as _json
    raw = inputs.get("json") if inputs.get("json") is not None else inputs.get("value")
    try:
        data = _json.loads(raw) if isinstance(raw, str) else raw
    except Exception:  # noqa: BLE001
        return {"ok": False, "error": "user_error: JsonExtractString 的 json 不合法"}
    key = str(inputs.get("key") or inputs.get("path") or "")
    cur = data
    for part in [p for p in key.replace("/", ".").split(".") if p]:
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            cur = cur[int(part)] if part.isdigit() and int(part) < len(cur) else None
        else:
            cur = None
    return {"ok": True, "value": "" if cur is None else str(cur)}


def _n_KSamplerSelect(inputs, ctx):
    return {"ok": True, "value": str(inputs.get("sampler_name") or inputs.get("value") or "euler")}


def _n_ResolutionSelector(inputs, ctx):
    return {"ok": True, "width": int(inputs.get("width") or 1024),
            "height": int(inputs.get("height") or 1024),
            "value": [int(inputs.get("width") or 1024), int(inputs.get("height") or 1024)]}


def _n_ComfySwitchNode(inputs, ctx):
    return {"ok": True, "value": inputs.get("on_true") if inputs.get("condition") else inputs.get("on_false")}


def _n_ComfySoftSwitchNode(inputs, ctx):
    return _n_ComfySwitchNode(inputs, ctx)


def _n_ConvertStringToComboNode(inputs, ctx):
    return {"ok": True, "value": str(inputs.get("value") or inputs.get("string") or "")}


NODES.update({
    "PrimitiveString": {"fn": _n_PrimitiveString, "in": ["value?"], "out": ["STRING"],
                        "writes": False, "desc": "字符串常量"},
    "PrimitiveStringMultiline": {"fn": _n_PrimitiveStringMultiline, "in": ["value?"], "out": ["STRING"],
                                 "writes": False, "desc": "多行字符串常量"},
    "PrimitiveInt": {"fn": _n_PrimitiveInt, "in": ["value?"], "out": ["INT"],
                     "writes": False, "desc": "整数常量"},
    "PrimitiveFloat": {"fn": _n_PrimitiveFloat, "in": ["value?"], "out": ["FLOAT"],
                       "writes": False, "desc": "浮点常量"},
    "PrimitiveBoolean": {"fn": _n_PrimitiveBoolean, "in": ["value?"], "out": ["BOOLEAN"],
                         "writes": False, "desc": "布尔常量"},
    "PrimitiveBoundingBox": {"fn": _n_PrimitiveBoundingBox, "in": ["value?"], "out": ["BBOX"],
                             "writes": False, "desc": "包围盒常量"},
    "InvertBooleanNode": {"fn": _n_InvertBooleanNode, "in": ["value?"], "out": ["BOOLEAN"],
                          "writes": False, "desc": "布尔取反"},
    "StringCompare": {"fn": _n_StringCompare, "in": ["a?", "b?", "op?"], "out": ["BOOLEAN"],
                      "writes": False, "desc": "字符串比较"},
    "StringConcatenate": {"fn": _n_StringConcatenate, "in": ["a?", "b?", "separator?"], "out": ["STRING"],
                          "writes": False, "desc": "字符串拼接"},
    "StringContains": {"fn": _n_StringContains, "in": ["string?", "substring?"], "out": ["BOOLEAN"],
                       "writes": False, "desc": "字符串包含"},
    "StringLength": {"fn": _n_StringLength, "in": ["string?"], "out": ["INT"],
                     "writes": False, "desc": "字符串长度"},
    "StringReplace": {"fn": _n_StringReplace, "in": ["string?", "find?", "replace?"], "out": ["STRING"],
                      "writes": False, "desc": "字符串替换"},
    "StringSubstring": {"fn": _n_StringSubstring, "in": ["string?", "start?", "length?"], "out": ["STRING"],
                        "writes": False, "desc": "字符串截取"},
    "StringTrim": {"fn": _n_StringTrim, "in": ["string?"], "out": ["STRING"],
                   "writes": False, "desc": "字符串去空白"},
    "JsonExtractString": {"fn": _n_JsonExtractString, "in": ["json?", "key?"], "out": ["STRING"],
                          "writes": False, "desc": "JSON 取字符串"},
    "KSamplerSelect": {"fn": _n_KSamplerSelect, "in": ["sampler_name?"], "out": ["STRING"],
                       "writes": False, "desc": "采样器名选择（不跑采样）"},
    "ResolutionSelector": {"fn": _n_ResolutionSelector, "in": ["width?", "height?"], "out": ["INT", "INT"],
                           "writes": False, "desc": "分辨率选择"},
    "ComfySwitchNode": {"fn": _n_ComfySwitchNode, "in": ["condition?", "on_true?", "on_false?"], "out": ["VALUE"],
                        "writes": False, "desc": "条件开关"},
    "ComfySoftSwitchNode": {"fn": _n_ComfySoftSwitchNode, "in": ["condition?", "on_true?", "on_false?"], "out": ["VALUE"],
                            "writes": False, "desc": "软条件开关"},
    "ConvertStringToComboNode": {"fn": _n_ConvertStringToComboNode, "in": ["value?"], "out": ["STRING"],
                                 "writes": False, "desc": "字符串转选择值"},
})


# ── 2026-11-02 · 天真第三批：字符串/设备选择/列表/图像边缘结构节点（9 个）──
def _n_StringFormat(inputs, ctx):
    tmpl = str(inputs.get("format") if inputs.get("format") is not None else inputs.get("template") or "")
    vals = inputs.get("values")
    try:
        if isinstance(vals, dict):
            return {"ok": True, "value": tmpl.format(**vals)}
        if isinstance(vals, (list, tuple)):
            return {"ok": True, "value": tmpl.format(*vals)}
        return {"ok": True, "value": tmpl.format(vals if vals is not None else "")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "user_error: StringFormat 失败 %s" % str(e)[:120]}


def _n_SelectDevice(inputs, ctx):
    return {"ok": True, "value": str(inputs.get("device") or inputs.get("value") or "default")}


def _n_MergeLists(inputs, ctx):
    out = []
    for k in ("list1", "list2", "lists", "images", "texts", "value"):
        v = inputs.get(k)
        if isinstance(v, list):
            out.extend(v)
        elif v is not None:
            out.append(v)
    return {"ok": True, "value": out, "count": len(out)}


def _n_PadImageNode(inputs, ctx):
    from PIL import ImageOps
    img, err = _rgba(inputs) if "_rgba" in globals() else (None, None)
    if img is None:
        from PIL import Image
        src = inputs.get("image") or inputs.get("path")
        if not src:
            return {"ok": False, "error": "user_error: 要 image"}
        img = Image.open(str(src)).convert("RGBA")
    l = int(inputs.get("left") or inputs.get("pad_left") or 0)
    t = int(inputs.get("top") or inputs.get("pad_top") or 0)
    r = int(inputs.get("right") or inputs.get("pad_right") or 0)
    b = int(inputs.get("bottom") or inputs.get("pad_bottom") or 0)
    color = inputs.get("color") or (0, 0, 0, 0)
    if isinstance(color, str):
        color = tuple(int(x) for x in color.replace("#", "").strip()) if color.startswith("#") else (0, 0, 0, 0)
    if len(color) == 3:
        color = (*color, 255)
    out_img = ImageOps.expand(img, border=(l, t, r, b), fill=tuple(color))
    out = _save(out_img, inputs, "padimage")
    return {"ok": True, "out": out, "width": out_img.width, "height": out_img.height}


def _n_ResizeImageMaskNode(inputs, ctx):
    from PIL import Image
    src = inputs.get("image") or inputs.get("path")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    img = Image.open(str(src)).convert("RGBA")
    w = int(inputs.get("width") or img.width)
    h = int(inputs.get("height") or img.height)
    method = str(inputs.get("method") or "lanczos").lower()
    m = {"nearest": Image.NEAREST, "bilinear": Image.BILINEAR, "bicubic": Image.BICUBIC,
         "area": Image.BOX, "lanczos": Image.LANCZOS}.get(method, Image.LANCZOS)
    out_img = img.resize((max(1, w), max(1, h)), m)
    out = _save(out_img, inputs, "resizeimagemask")
    return {"ok": True, "out": out, "width": out_img.width, "height": out_img.height}


def _n_ComfyMathExpression(inputs, ctx):
    import ast
    import operator
    expr = str(inputs.get("expression") or inputs.get("value") or "").strip()
    if not expr:
        return {"ok": True, "value": 0}
    ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
           ast.Mod: operator.mod, ast.Pow: operator.pow, ast.USub: operator.neg,
           ast.UAdd: operator.pos}
    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            return ops[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in ops:
            return ops[type(node.op)](ev(node.operand))
        raise ValueError("unsupported expression")
    try:
        return {"ok": True, "value": ev(ast.parse(expr, mode="eval"))}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "user_error: ComfyMathExpression 不支持 %s" % str(e)[:120]}


NODES.update({
    "StringFormat": {"fn": _n_StringFormat, "in": ["format?", "values?"], "out": ["STRING"],
                     "writes": False, "desc": "字符串格式化（Python format）"},
    "SelectCLIPDevice": {"fn": _n_SelectDevice, "in": ["device?"], "out": ["STRING"],
                         "writes": False, "desc": "CLIP 设备选择（值透传）"},
    "SelectModelDevice": {"fn": _n_SelectDevice, "in": ["device?"], "out": ["STRING"],
                          "writes": False, "desc": "模型设备选择（值透传）"},
    "SelectVAEDevice": {"fn": _n_SelectDevice, "in": ["device?"], "out": ["STRING"],
                        "writes": False, "desc": "VAE 设备选择（值透传）"},
    "MergeImageLists": {"fn": _n_MergeLists, "in": ["list1?", "list2?", "lists?"], "out": ["LIST"],
                        "writes": False, "desc": "合并图像列表"},
    "MergeTextLists": {"fn": _n_MergeLists, "in": ["list1?", "list2?", "lists?"], "out": ["LIST"],
                       "writes": False, "desc": "合并文本列表"},
    "PadImageNode": {"fn": _n_PadImageNode, "in": ["image", "out", "left?", "top?", "right?", "bottom?", "color?"],
                     "out": ["IMAGE"], "writes": True, "desc": "图像边缘填充"},
    "ResizeImageMaskNode": {"fn": _n_ResizeImageMaskNode, "in": ["image", "out", "width?", "height?", "method?"],
                            "out": ["IMAGE"], "writes": True, "desc": "图像/遮罩缩放"},
    "ComfyMathExpression": {"fn": _n_ComfyMathExpression, "in": ["expression?"], "out": ["FLOAT"],
                            "writes": False, "desc": "安全算术表达式"},
})


# ── 2026-11-02 · 天真第四批：列表/正则/颜色空间（9 个纯 CPU）──
def _n_CreateList(inputs, ctx):
    v = inputs.get("items", inputs.get("value", inputs.get("list")))
    if isinstance(v, list):
        return {"ok": True, "value": list(v), "count": len(v)}
    return {"ok": True, "value": [] if v is None else [v], "count": 0 if v is None else 1}


def _n_GetItemFromList(inputs, ctx):
    lst = inputs.get("list")
    if isinstance(lst, str):
        try:
            import json as _json
            lst = _json.loads(lst)
        except Exception:  # noqa: BLE001
            lst = []
    if not isinstance(lst, (list, tuple)):
        return {"ok": False, "error": "user_error: GetItemFromList 要 list"}
    try:
        i = int(inputs.get("index") or 0)
        return {"ok": True, "value": lst[i]}
    except Exception:  # noqa: BLE001
        return {"ok": False, "error": "user_error: index 越界"}


def _n_CustomCombo(inputs, ctx):
    return {"ok": True, "value": str(inputs.get("value") or inputs.get("text") or "")}


def _n_StripWhitespace(inputs, ctx):
    return {"ok": True, "value": str(inputs.get("string") or inputs.get("text") or "").strip()}


def _n_RegexMatch(inputs, ctx):
    import re
    s = str(inputs.get("string") or inputs.get("text") or "")
    p = str(inputs.get("pattern") or "")
    try:
        return {"ok": True, "value": bool(re.search(p, s))}
    except re.error as e:
        return {"ok": False, "error": "user_error: 正则错误 %s" % e}


def _n_RegexExtract(inputs, ctx):
    import re
    s = str(inputs.get("string") or inputs.get("text") or "")
    p = str(inputs.get("pattern") or "")
    try:
        m = re.search(p, s)
        if not m:
            return {"ok": True, "value": ""}
        g = int(inputs.get("group") or 0)
        return {"ok": True, "value": m.group(g)}
    except (re.error, IndexError) as e:
        return {"ok": False, "error": "user_error: 正则提取失败 %s" % e}


def _n_RegexReplace(inputs, ctx):
    import re
    s = str(inputs.get("string") or inputs.get("text") or "")
    p = str(inputs.get("pattern") or "")
    r = str(inputs.get("replacement") or inputs.get("replace") or "")
    try:
        return {"ok": True, "value": re.sub(p, r, s)}
    except re.error as e:
        return {"ok": False, "error": "user_error: 正则错误 %s" % e}


def _n_ImageRGBToYUV(inputs, ctx):
    import numpy as np
    from PIL import Image
    src = inputs.get("image") or inputs.get("path")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    im = Image.open(str(src)).convert("RGBA")
    a = np.asarray(im).astype(np.float32)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    y = 0.299 * r + 0.587 * g + 0.114 * b
    u = -0.147 * r - 0.289 * g + 0.436 * b + 128.0
    v = 0.615 * r - 0.515 * g - 0.100 * b + 128.0
    out_arr = np.dstack([y, u, v, a[:, :, 3]]).clip(0, 255).astype(np.uint8)
    out_img = Image.fromarray(out_arr, "RGBA")
    out = _save(out_img, inputs, "rgb2yuv")
    return {"ok": True, "out": out, "space": "YUV"}


def _n_ImageYUVToRGB(inputs, ctx):
    import numpy as np
    from PIL import Image
    src = inputs.get("image") or inputs.get("path")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    im = Image.open(str(src)).convert("RGBA")
    a = np.asarray(im).astype(np.float32)
    y, u, v = a[:, :, 0], a[:, :, 1] - 128.0, a[:, :, 2] - 128.0
    r = y + 1.140 * v
    g = y - 0.395 * u - 0.581 * v
    b = y + 2.032 * u
    out_arr = np.dstack([r, g, b, a[:, :, 3]]).clip(0, 255).astype(np.uint8)
    out_img = Image.fromarray(out_arr, "RGBA")
    out = _save(out_img, inputs, "yuv2rgb")
    return {"ok": True, "out": out, "space": "RGB"}


NODES.update({
    "CreateList": {"fn": _n_CreateList, "in": ["items?", "value?"], "out": ["LIST"],
                   "writes": False, "desc": "创建列表"},
    "GetItemFromList": {"fn": _n_GetItemFromList, "in": ["list?", "index?"], "out": ["VALUE"],
                        "writes": False, "desc": "按索引取列表项"},
    "CustomCombo": {"fn": _n_CustomCombo, "in": ["value?"], "out": ["STRING"],
                    "writes": False, "desc": "自定义选择值"},
    "StripWhitespace": {"fn": _n_StripWhitespace, "in": ["string?"], "out": ["STRING"],
                        "writes": False, "desc": "去首尾空白"},
    "RegexMatch": {"fn": _n_RegexMatch, "in": ["string?", "pattern?"], "out": ["BOOLEAN"],
                   "writes": False, "desc": "正则匹配"},
    "RegexExtract": {"fn": _n_RegexExtract, "in": ["string?", "pattern?", "group?"], "out": ["STRING"],
                     "writes": False, "desc": "正则提取"},
    "RegexReplace": {"fn": _n_RegexReplace, "in": ["string?", "pattern?", "replacement?"], "out": ["STRING"],
                     "writes": False, "desc": "正则替换"},
    "ImageRGBToYUV": {"fn": _n_ImageRGBToYUV, "in": ["image", "out"], "out": ["IMAGE"],
                      "writes": True, "desc": "RGB→YUV 通道（BT.601）"},
    "ImageYUVToRGB": {"fn": _n_ImageYUVToRGB, "in": ["image", "out"], "out": ["IMAGE"],
                      "writes": True, "desc": "YUV→RGB 通道（BT.601）"},
})


# ── 2026-11-02 · 天真第五批：图层/形态学/空洞/分辨率/列表（7 个纯 CPU）──
def _n_AddLayer(inputs, ctx):
    from PIL import Image
    p1 = inputs.get("image1") or inputs.get("image") or inputs.get("base")
    p2 = inputs.get("image2") or inputs.get("layer")
    if not p1 or not p2:
        return {"ok": False, "error": "user_error: AddLayer 要 image1/image2"}
    a = Image.open(str(p1)).convert("RGBA")
    b = Image.open(str(p2)).convert("RGBA")
    if b.size != a.size:
        b = b.resize(a.size)
    opacity = max(0.0, min(1.0, float(inputs.get("opacity") if inputs.get("opacity") is not None else 1.0)))
    if opacity < 1.0:
        alpha = b.getchannel("A").point(lambda x: int(x * opacity))
        b.putalpha(alpha)
    out_img = Image.alpha_composite(a, b)
    out = _save(out_img, inputs, "addlayer")
    return {"ok": True, "out": out, "opacity": opacity, "width": out_img.width, "height": out_img.height}


def _n_Morphology(inputs, ctx):
    from PIL import Image, ImageFilter
    src = inputs.get("image") or inputs.get("mask") or inputs.get("path")
    if not src:
        return {"ok": False, "error": "user_error: Morphology 要 image/mask"}
    img = Image.open(str(src)).convert("L")
    k = max(1, int(inputs.get("kernel_size") or inputs.get("kernel") or 3))
    op = str(inputs.get("operation") or inputs.get("op") or "dilate").lower()
    f = ImageFilter.MaxFilter(k if k % 2 else k + 1) if op.startswith("dil") else ImageFilter.MinFilter(k if k % 2 else k + 1)
    out_img = img.filter(f).convert("RGBA")
    out = _save(out_img, inputs, "morphology")
    return {"ok": True, "out": out, "operation": op, "kernel": k}


def _n_FillHoles(inputs, ctx):
    import numpy as np
    from collections import deque
    from PIL import Image
    src = inputs.get("mask") or inputs.get("image") or inputs.get("path")
    if not src:
        return {"ok": False, "error": "user_error: FillHoles 要 mask"}
    img = Image.open(str(src)).convert("L")
    a = np.asarray(img).copy()
    h, w = a.shape
    bg = a < 128
    seen = np.zeros_like(bg, dtype=bool)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if bg[y, x] and not seen[y, x]:
                seen[y, x] = True; q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if bg[y, x] and not seen[y, x]:
                seen[y, x] = True; q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and bg[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True; q.append((ny, nx))
    filled = a.copy()
    filled[bg & ~seen] = 255
    out_img = Image.fromarray(filled, "L").convert("RGBA")
    out = _save(out_img, inputs, "fillholes")
    return {"ok": True, "out": out, "filled": int((bg & ~seen).sum())}


def _n_ResolutionBucket(inputs, ctx):
    w = int(inputs.get("width") or 1024)
    h = int(inputs.get("height") or 1024)
    bucket = "landscape" if w > h else ("portrait" if h > w else "square")
    return {"ok": True, "width": w, "height": h, "bucket": bucket, "value": [w, h]}


def _n_ShuffleDataset(inputs, ctx):
    import random
    data = inputs.get("dataset", inputs.get("items", inputs.get("list", [])))
    if not isinstance(data, list):
        return {"ok": False, "error": "user_error: ShuffleDataset 要 list"}
    out = list(data)
    seed = int(inputs.get("seed") or 0)
    random.Random(seed).shuffle(out)
    return {"ok": True, "value": out, "count": len(out), "seed": seed}


def _n_CreateBoundingBoxes(inputs, ctx):
    boxes = inputs.get("boxes", inputs.get("value", []))
    if not isinstance(boxes, list):
        boxes = []
    return {"ok": True, "value": boxes, "count": len(boxes)}


def _n_LayersFromBoundingBoxes(inputs, ctx):
    boxes = inputs.get("boxes", inputs.get("value", []))
    if not isinstance(boxes, list):
        boxes = []
    return {"ok": True, "value": boxes, "layers": len(boxes)}


NODES.update({
    "AddLayer": {"fn": _n_AddLayer, "in": ["image1", "image2", "out", "opacity?"], "out": ["IMAGE"],
                 "writes": True, "desc": "图层叠加（Pillow alpha composite）"},
    "Morphology": {"fn": _n_Morphology, "in": ["image", "out", "operation?", "kernel_size?"], "out": ["IMAGE"],
                    "writes": True, "desc": "灰度形态学（膨胀/腐蚀）"},
    "FillHoles": {"fn": _n_FillHoles, "in": ["mask", "out"], "out": ["MASK"],
                  "writes": True, "desc": "填遮罩孔洞（边界背景泛洪）"},
    "ResolutionBucket": {"fn": _n_ResolutionBucket, "in": ["width?", "height?"], "out": ["INT", "INT"],
                         "writes": False, "desc": "分辨率分桶"},
    "ShuffleDataset": {"fn": _n_ShuffleDataset, "in": ["dataset?", "seed?"], "out": ["LIST"],
                       "writes": False, "desc": "数据集洗牌（seed 可复现）"},
    "CreateBoundingBoxes": {"fn": _n_CreateBoundingBoxes, "in": ["boxes?"], "out": ["LIST"],
                            "writes": False, "desc": "包围盒列表"},
    "LayersFromBoundingBoxes": {"fn": _n_LayersFromBoundingBoxes, "in": ["boxes?"], "out": ["LIST"],
                                "writes": False, "desc": "包围盒转图层列表"},
})


# ── 2026-11-02 · 天真第六批：Canny 边缘（numpy 实现，不依赖 cv2）──
def _n_Canny(inputs, ctx):
    import numpy as np
    from PIL import Image, ImageFilter

    src = inputs.get("image") or inputs.get("path")
    if not src:
        return {"ok": False, "error": "user_error: 要 image"}
    low = float(inputs.get("low_threshold") if inputs.get("low_threshold") is not None else 100)
    high = float(inputs.get("high_threshold") if inputs.get("high_threshold") is not None else 200)
    img = Image.open(str(src)).convert("L").filter(ImageFilter.GaussianBlur(1.4))
    a = np.asarray(img, dtype=np.float32)
    p = np.pad(a, 1, mode="edge")
    gx = (p[:-2, 2:] + 2 * p[1:-1, 2:] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[1:-1, :-2] + p[2:, :-2])
    gy = (p[2:, :-2] + 2 * p[2:, 1:-1] + p[2:, 2:]) - (p[:-2, :-2] + 2 * p[:-2, 1:-1] + p[:-2, 2:])
    mag = np.hypot(gx, gy)
    ang = (np.rad2deg(np.arctan2(gy, gx)) + 180) % 180
    nms = np.zeros_like(mag)
    for y in range(1, mag.shape[0] - 1):
        for x in range(1, mag.shape[1] - 1):
            d = ang[y, x]
            if d < 22.5 or d >= 157.5:
                n1, n2 = mag[y, x - 1], mag[y, x + 1]
            elif d < 67.5:
                n1, n2 = mag[y - 1, x + 1], mag[y + 1, x - 1]
            elif d < 112.5:
                n1, n2 = mag[y - 1, x], mag[y + 1, x]
            else:
                n1, n2 = mag[y - 1, x - 1], mag[y + 1, x + 1]
            if mag[y, x] >= n1 and mag[y, x] >= n2:
                nms[y, x] = mag[y, x]
    strong = nms >= high
    weak = (nms >= low) & ~strong
    edges = strong.copy()
    for _ in range(2):
        grow = edges.copy()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            grow |= np.roll(edges, (dy, dx), axis=(0, 1))
        edges = grow & (strong | weak)
    out_img = Image.fromarray((edges * 255).astype(np.uint8), "L").convert("RGBA")
    out = _save(out_img, inputs, "canny")
    return {"ok": True, "out": out, "edge_pixels": int(edges.sum()),
            "low": low, "high": high, "width": out_img.width, "height": out_img.height}


NODES["Canny"] = {
    "fn": _n_Canny,
    "in": ["image", "out", "low_threshold?", "high_threshold?"],
    "out": ["IMAGE"],
    "writes": True,
    "desc": "Canny 边缘（numpy 实现，不依赖 cv2）",
}


# ── 2026-11-02 · 本地 ComfyUI object_info 真快照里的最后 traditional：SaveImageWebsocket ──
def _n_SaveImageWebsocket(inputs, ctx):
    """ComfyUI 自定义节点同名：保存 images 到本地（不真开 websocket）。"""
    import os
    import shutil
    src = inputs.get("images") or inputs.get("image") or inputs.get("path")
    if isinstance(src, (list, tuple)):
        src = src[0] if src else ""
    if not src:
        return {"ok": False, "error": "user_error: SaveImageWebsocket 要 images"}
    out = inputs.get("out")
    if not out:
        out = _out_path(inputs, "websocket_image")
    p = os.fspath(out)
    os.makedirs(os.path.dirname(p), exist_ok=True) if os.path.dirname(p) else None
    shutil.copyfile(str(src), p)
    return {"ok": True, "out": p, "bytes": os.path.getsize(p), "ui": {"images": [p]}}


NODES["SaveImageWebsocket"] = {
    "fn": _n_SaveImageWebsocket,
    "in": ["images", "out?"],
    "out": ["IMAGE"],
    "writes": True,
    "desc": "保存 images（ComfyUI websocket image save 的本地等效）",
}


# ── 2026-11-02 · 本地 Diffusers SD-Turbo：不装 ComfyUI 也能文生图 ──
_SD_TURBO_PIPE = {"path": None, "pipe": None, "load_s": None}


def _sd_turbo_path():
    import os
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    rel = os.path.join("vendor", "hf", "hub",
                       "models--stabilityai--sd-turbo", "snapshots",
                       "b261bac6fd2cf515557d5d0707481eafa0485ec2")
    for base in (root, os.path.dirname(root)):
        p = os.path.join(base, rel)
        if os.path.isdir(p):
            return p
    return ""


def _n_t2i_sdturbo(inputs, ctx):
    """本地 Diffusers SD-Turbo CPU 文生图（不依赖 ComfyUI）。"""
    import os
    import sys
    import time
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for base in (root, os.path.dirname(root)):
        pylibs = os.path.join(base, "vendor", "pylibs")
        if os.path.isdir(pylibs) and pylibs not in sys.path:
            sys.path.insert(0, pylibs)
    model = str(inputs.get("model") or _sd_turbo_path())
    if not model or not os.path.isdir(model):
        return {"ok": False, "status": "needs_dependency",
                "error": "本地 SD-Turbo 权重不在；需要 vendor/hf 下的 sd-turbo snapshot"}
    prompt = str(inputs.get("prompt") or inputs.get("text") or "").strip()
    if not prompt:
        return {"ok": False, "error": "user_error: 要 prompt"}
    try:
        import torch
        from diffusers import AutoPipelineForText2Image
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "needs_dependency",
                "error": "缺少 torch/diffusers：%s" % str(e)[:160]}
    t0 = time.time()
    if _SD_TURBO_PIPE["pipe"] is None or _SD_TURBO_PIPE["path"] != model:
        pipe = AutoPipelineForText2Image.from_pretrained(
            model, torch_dtype=torch.float32, local_files_only=True,
            safety_checker=None, requires_safety_checker=False)
        pipe.to("cpu")
        _SD_TURBO_PIPE.update({"path": model, "pipe": pipe,
                               "load_s": round(time.time() - t0, 2)})
    size = int(inputs.get("size") or inputs.get("width") or 256)
    size = max(64, min(512, size))
    steps = max(1, min(4, int(inputs.get("steps") or 1)))
    seed = int(inputs.get("seed") or 0)
    gen = torch.Generator(device="cpu").manual_seed(seed)
    t1 = time.time()
    img = _SD_TURBO_PIPE["pipe"](
        prompt=prompt, num_inference_steps=steps, guidance_scale=0.0,
        width=size, height=size, generator=gen).images[0]
    out = _save(img.convert("RGBA"), inputs, "sdturbo")
    return {"ok": True, "out": out, "prompt": prompt, "size": [size, size],
            "steps": steps, "seed": seed,
            "load_s": _SD_TURBO_PIPE["load_s"],
            "generation_s": round(time.time() - t1, 2),
            "engine": "diffusers SD-Turbo CPU（本地权重）"}


NODES["t2i_sdturbo"] = {
    "fn": _n_t2i_sdturbo,
    "in": ["prompt", "out", "size?", "steps?", "seed?", "model?"],
    "out": ["IMAGE"],
    "writes": True,
    "desc": "本地 Diffusers SD-Turbo CPU 文生图（不走 ComfyUI/云端）",
}


# ── 2026-11-03 · 融合权重节点：RV5.1 × Tiny-SD（本地 gbt-fused-sd15）──
_FUSED_PIPE = {"path": None, "pipe": None, "load_s": None}


def _fused_path():
    import os
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for base in (root, os.path.dirname(root)):
        p = os.path.join(base, "vendor", "hf", "gbt-fused-sd15")
        if os.path.isdir(p):
            return p
    return ""


def _n_t2i_fused(inputs, ctx):
    """用我们自己融合的 SD1.5 权重出图（本地，不碰云端/ComfyUI）。"""
    import os
    import sys
    import time
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for base in (root, os.path.dirname(root)):
        pylibs = os.path.join(base, "vendor", "pylibs")
        if os.path.isdir(pylibs) and pylibs not in sys.path:
            sys.path.insert(0, pylibs)
    model = str(inputs.get("model") or _fused_path())
    if not model or not os.path.isdir(model):
        return {"ok": False, "status": "needs_dependency",
                "error": "本地融合权重 gbt-fused-sd15 不在"}
    prompt = str(inputs.get("prompt") or inputs.get("text") or "").strip()
    if not prompt:
        return {"ok": False, "error": "user_error: 要 prompt"}
    try:
        import torch
        from diffusers import StableDiffusionPipeline
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "needs_dependency",
                "error": "缺少 torch/diffusers：%s" % str(e)[:160]}
    t0 = time.time()
    if _FUSED_PIPE["pipe"] is None or _FUSED_PIPE["path"] != model:
        pipe = StableDiffusionPipeline.from_pretrained(
            model, torch_dtype=torch.float32, local_files_only=True)
        pipe.to("cpu")
        pipe.enable_attention_slicing()
        _FUSED_PIPE.update({"path": model, "pipe": pipe,
                            "load_s": round(time.time() - t0, 2)})
    size = int(inputs.get("size") or 256)
    size = max(64, min(512, size))
    steps = max(1, min(20, int(inputs.get("steps") or 8)))
    seed = int(inputs.get("seed") or 0)
    g = torch.Generator(device="cpu").manual_seed(seed)
    t1 = time.time()
    img = _FUSED_PIPE["pipe"](prompt=prompt, num_inference_steps=steps,
                              guidance_scale=7.0, width=size, height=size,
                              generator=g).images[0]
    out = _save(img.convert("RGBA"), inputs, "t2ifused")
    return {"ok": True, "out": out, "prompt": prompt, "size": [size, size],
            "steps": steps, "seed": seed,
            "load_s": _FUSED_PIPE["load_s"],
            "generation_s": round(time.time() - t1, 2),
            "engine": "本地融合权重 gbt-fused-sd15（RV5.1×Tiny-SD）"}


NODES["t2i_fused"] = {
    "fn": _n_t2i_fused,
    "in": ["prompt", "out", "size?", "steps?", "seed?", "model?"],
    "out": ["IMAGE"],
    "writes": True,
    "desc": "本地融合权重文生图（RV5.1×Tiny-SD，不碰云/ComfyUI）",
}


# ── 2026-11-03 · 真图生视频：本地 SVD-XT（CPU fp32）──
_SVD_PIPE = {"path": None, "pipe": None, "load_s": None}


def _svd_model_dir():
    import os
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for base in (root, os.path.dirname(root)):
        p = os.path.join(base, "vendor", "hf", "svd-xt-fp16")
        if os.path.isdir(p):
            return p
    return ""


def _n_i2v_svd(inputs, ctx):
    """本地 SVD-XT 图生视频：真帧，不调用 ComfyUI/云端。"""
    import os
    import shutil
    import subprocess
    import sys
    import tempfile
    import time

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for base in (root, os.path.dirname(root)):
        pylibs = os.path.join(base, "vendor", "pylibs")
        if os.path.isdir(pylibs) and pylibs not in sys.path:
            sys.path.insert(0, pylibs)
    image = str(inputs.get("image") or inputs.get("path") or "").strip()
    if not image or not os.path.isfile(image):
        return {"ok": False, "error": "user_error: 要 image 本地图片路径"}
    model = _svd_model_dir()
    if not model:
        return {"ok": False, "status": "needs_dependency", "error": "本地 SVD-XT 不在"}
    out = str(inputs.get("out") or "").strip()
    if not out:
        out = os.path.join(root, "state", "i2v-%d.mp4" % int(time.time()))
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    try:
        import torch
        from diffusers import StableVideoDiffusionPipeline
        from PIL import Image
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "needs_dependency", "error": "缺少 torch/diffusers：%s" % str(e)[:160]}
    frames_n = max(2, min(25, int(inputs.get("frames") or 8)))
    width = max(128, min(1024, int(inputs.get("width") or 256)))
    height = max(128, min(1024, int(inputs.get("height") or 448)))
    steps = max(1, min(25, int(inputs.get("steps") or 2)))
    fps = max(4, min(30, int(inputs.get("fps") or 8)))
    seed = int(inputs.get("seed") or 42)
    t0 = time.time()
    if _SVD_PIPE["pipe"] is None:
        pipe = StableVideoDiffusionPipeline.from_pretrained(
            model, torch_dtype=torch.float32, local_files_only=True, variant="fp16")
        pipe.to("cpu")
        pipe.enable_attention_slicing()
        _SVD_PIPE.update({"path": model, "pipe": pipe,
                          "load_s": round(time.time() - t0, 2)})
    t1 = time.time()
    gen = torch.Generator(device="cpu").manual_seed(seed)
    frames = _SVD_PIPE["pipe"](Image.open(image).convert("RGB"),
                               num_frames=frames_n, decode_chunk_size=1,
                               motion_bucket_id=int(inputs.get("motion") or 127),
                               noise_aug_strength=0.02,
                               height=height, width=width,
                               num_inference_steps=steps, generator=gen).frames[0]
    gen_s = round(time.time() - t1, 2)
    tmp = tempfile.mkdtemp(prefix="gbt-i2v-")
    try:
        for i, fr in enumerate(frames):
            fr.save(os.path.join(tmp, "f%03d.png" % i))
        ffmpeg = ""
        for base in (root, os.path.dirname(root)):
            p = os.path.join(base, "vendor", "ffmpeg", "bin", "ffmpeg.exe")
            if os.path.isfile(p):
                ffmpeg = p
                break
        if not ffmpeg:
            return {"ok": False, "status": "needs_dependency", "error": "找不到 ffmpeg"}
        subprocess.run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                        "-framerate", str(fps), "-i", os.path.join(tmp, "f%03d.png"),
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"ok": True, "out": out, "image": image, "frames": frames_n,
            "size": [width, height], "fps": fps, "steps": steps, "seed": seed,
            "load_s": _SVD_PIPE["load_s"], "generation_s": gen_s,
            "engine": "StableVideoDiffusionPipeline CPU fp32（本地 SVD-XT）"}


NODES["i2v_svd"] = {
    "fn": _n_i2v_svd,
    "in": ["image", "out", "frames?", "width?", "height?", "steps?", "fps?", "seed?", "motion?"],
    "out": ["VIDEO"],
    "writes": True,
    "desc": "本地 SVD-XT 真图生视频（CPU fp32，不碰云/ComfyUI）",
}


# ── 2026-11-03 · 吞噬 shuohao-skills：GBT天真直接跑短剧制作 skill ──
def _n_shuohao_skill(inputs, ctx):
    """调用本地 shuohao-skills 的确定性 Node 脚本（无 npm 依赖、无云端）。"""
    import json
    import os
    import shlex
    import subprocess

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    base = os.path.join(root, "gbt_allinone", "skills", "shuohao")
    skill = str(inputs.get("skill") or "").strip()
    script = str(inputs.get("script") or "").strip()
    if not skill or not script:
        return {"ok": False, "error": "user_error: 要 skill 与 script"}
    if "/" in skill or "\\" in skill or ".." in skill:
        return {"ok": False, "error": "user_error: 非法 skill"}
    skdir = os.path.join(base, skill)
    spath = os.path.join(skdir, "scripts", script)
    if not os.path.isfile(spath):
        return {"ok": False, "status": "needs_dependency", "error": "脚本不存在：%s" % spath}
    args = inputs.get("args") or []
    if isinstance(args, str):
        args = shlex.split(args)
    if not isinstance(args, list):
        return {"ok": False, "error": "user_error: args 要是数组或字符串"}
    cmd = ["node", spath] + [str(x) for x in args]
    try:
        r = subprocess.run(cmd, cwd=skdir, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout: skill 脚本超过 120s"}
    out = (r.stdout or "")[-120000:]
    err = (r.stderr or "")[-120000:]
    return {"ok": r.returncode == 0, "skill": skill, "script": script,
            "cmd": cmd, "exit": r.returncode, "stdout": out, "stderr": err,
            "engine": "本地 shuohao-skills（Node，零 npm 依赖）"}


NODES["shuohao_skill"] = {
    "fn": _n_shuohao_skill,
    "in": ["skill", "script", "args?"],
    "out": ["JSON"],
    "writes": False,
    "desc": "跑本地 shuohao-skills 短剧 skill（大纲/角色/美术/剧本/站位/分镜）",
}
