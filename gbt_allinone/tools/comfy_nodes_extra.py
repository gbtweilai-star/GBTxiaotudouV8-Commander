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
