# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""filmgrade · 共用外观库（调色中枢）—— 一处定义 N 种味道，actioncam / filmkit / look_grade 同款引用。

【为什么存在】
  主人的口径是「**词即指令**」：想让她是什么样，她就变成什么样。
  所以这里不是「贴一个风格标签」，而是**一条真调色链**：

      colorbalance → eq → curves → cas 锐化 → gblur/blend 辉光 → vignette 暗角 → noise 颗粒

  链上的每一项都能单独读数（锐化 / 辉光 / 暗角 / 颗粒 / 对比曲线 / 色平衡），
  **不报合计** —— 合计会掩盖「哪一项其实没生效」。

【口径】
  · `pick` 认不出就**如实标回落**，且回落到 `none`（原样）——
    宁可不动，也不拿一个不搭的味去改主人的画面；
  · `preview` 只出**单帧试看**，定了再上全片；
  · `qc` 出 `black / freeze / yavg / verdict` —— 这一关照的是
    「看着完成 ≠ 过得去」（实测照出过 `不通过 · black=1 · freeze=3`）。

【边界】
  · 本件只管**外观与审计**；拍子表/装配走 `actioncam`，剧本走 `filmkit`。
  · 视频 QC 需要逐帧解，走 cv2；图片走 PIL/numpy。缺依赖就如实 `needs_dependency`。

【历史】
  该文件在桌面包里**曾经缺失**（`16-capability-audit-341.md` 记为
  `look_grade → tools/filmgrade.py` · `how_to_fix: 把 tools/filmgrade.py 一起纳入仓库`）。
  2026-11-04 按 `video.md` / `能力总表.md` 的权威描述补回，词表与 op 契约照原文，不自造。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_DEFAULT_ROOTS = [Path(__file__).resolve().parents[1]]
ROOT = next((r for r in _DEFAULT_ROOTS if (r / "state").is_dir() or (r / "gbt_allinone").is_dir()),
            _DEFAULT_ROOTS[0])

__all__ = ["LOOKS", "looks_list", "pick", "pick_explain", "grade_chain",
           "preview", "qc", "status"]


def _dep(name: str):
    """延迟取依赖：缺了就如实说缺哪个，不在模块导入期炸。"""
    spec = importlib.util.find_spec(name)
    if spec is None:
        raise RuntimeError(f"needs_dependency: 缺 {name}")
    return importlib.import_module(name)


# ──────────────────────────────────────────────────────────────────────
# 外观库：词表照 `能力总表.md` / `video.md` 原文，不增不减
#   chain 里每一项都是**真参数**，preview 会逐项施加并逐项读数
# ──────────────────────────────────────────────────────────────────────
LOOKS: dict[str, dict] = {
    "filmic": {
        "label": "电影感",
        "brief": "中性偏冷的电影底，对比拉一点，轻微暗角",
        "colorbalance": (1.03, 1.00, 0.97),
        "eq": (1.00, 1.10, 0.96),
        "curves": 1.06,
        "sharp": 0.55,
        "bloom": 0.18,
        "vignette": 0.22,
        "grain": 6.0,
        "words": ["电影感", "电影", "cinematic", "胶片感", "有质感", "高级"],
    },
    "aged": {
        "label": "做旧",
        "brief": "发黄、低饱和、颗粒重，像压了很久的底片",
        "colorbalance": (1.08, 1.00, 0.86),
        "eq": (0.98, 1.02, 0.72),
        "curves": 1.14,
        "sharp": 0.30,
        "bloom": 0.10,
        "vignette": 0.30,
        "grain": 12.0,
        "words": ["做旧", "旧", "老照片", "老照片感", "复古", "怀旧", "年代感", "泛黄"],
    },
    "cold_damp": {
        "label": "潮湿阴冷",
        "brief": "青蓝压下去、对比收一点、暗角重，潮气贴脸",
        "colorbalance": (0.90, 0.98, 1.10),
        "eq": (0.96, 1.04, 0.82),
        "curves": 1.10,
        "sharp": 0.35,
        "bloom": 0.26,
        "vignette": 0.34,
        "grain": 8.0,
        "words": ["潮湿", "阴冷", "冷", "湿", "阴天", "压抑", "冰凉", "湿冷", "寒"],
    },
    "teal_orange": {
        "label": "热血橙青",
        "brief": "暗部推青、亮部推橙，肤色暖，商业大片味",
        "colorbalance": (1.10, 1.00, 0.92),
        "eq": (1.02, 1.14, 1.10),
        "curves": 1.04,
        "sharp": 0.60,
        "bloom": 0.22,
        "vignette": 0.18,
        "grain": 4.0,
        "words": ["热血", "橙青", "teal", "商业", "大片", "燃", "爽", "阳光"],
    },
    "faded": {
        "label": "褪色胶片",
        "brief": "抬黑、低对比、低饱和，旧胶片洗过一遍",
        "colorbalance": (1.02, 1.00, 0.98),
        "eq": (1.06, 0.90, 0.68),
        "curves": 0.90,
        "sharp": 0.25,
        "bloom": 0.30,
        "vignette": 0.24,
        "grain": 10.0,
        "words": ["褪色", "旧胶片", "胶片", "冲洗", "低饱和", "淡", "发白"],
    },
    "bw_doc": {
        "label": "黑白纪实",
        "brief": "去色 + 硬朗对比，纪实感",
        "colorbalance": (1.00, 1.00, 1.00),
        "eq": (1.00, 1.22, 0.0),
        "curves": 1.12,
        "sharp": 0.70,
        "bloom": 0.08,
        "vignette": 0.26,
        "grain": 9.0,
        "gravity": True,
        "words": ["黑白", "纪实", "灰阶", "单色", "bw", "mono", "新闻"],
    },
    "cyber_neon": {
        "label": "赛博霓虹",
        "brief": "高饱和、推洋红与青、辉光重、暗角硬",
        "colorbalance": (1.08, 0.94, 1.14),
        "eq": (1.00, 1.18, 1.34),
        "curves": 1.02,
        "sharp": 0.65,
        "bloom": 0.44,
        "vignette": 0.32,
        "grain": 5.0,
        "words": ["赛博", "霓虹", "cyber", "科技感", "未来", "朋克", "紫", "夜店"],
    },
    "none": {
        "label": "原样",
        "brief": "不动任何一档（认不出时的归属，绝不乱调）",
        "colorbalance": (1.0, 1.0, 1.0),
        "eq": (1.0, 1.0, 1.0),
        "curves": 1.0,
        "sharp": 0.0,
        "bloom": 0.0,
        "vignette": 0.0,
        "grain": 0.0,
        "words": ["原样", "不动", "不调", "原图", "保持"],
    },
}

DEFAULT_LOOK = "filmic"
FALLBACK_LOOK = "none"


# ──────────────────────────────────────────────────────────────────────
# 只读面
# ──────────────────────────────────────────────────────────────────────
def looks_list() -> dict:
    """列出外观库。**条数现算**，不写死数字（描述里也一样）。"""
    items = [{"name": k, "label": v["label"], "brief": v["brief"]}
             for k, v in LOOKS.items()]
    return {"ok": True, "op": "list", "count": len(items), "looks": items}


def pick_explain(intent: str) -> dict:
    """人话 → 外观名，并**如实说明**是命中还是回落。

    命中的是词表里最长的那一个（避免「冷」抢走「湿冷」）。
    一个都没命中 ⇒ 回落到 `none`（原样），`fallback=True`，把原话带回去。
    """
    raw = (intent or "").strip()
    low = raw.lower()
    hits = []
    for key, look in LOOKS.items():
        for w in look["words"]:
            if w.lower() in low:
                hits.append((len(w), key, w))
    if hits:
        hits.sort(reverse=True)
        best = hits[0]
        return {"picked": best[1], "label": LOOKS[best[1]]["label"],
                "matched": best[2], "all_hits": sorted({h[2] for h in hits}),
                "fallback": False, "why": f"命中「{best[2]}」"}
    return {"picked": FALLBACK_LOOK, "label": LOOKS[FALLBACK_LOOK]["label"],
            "matched": None, "all_hits": [], "fallback": True,
            "why": f"词表里没有能对上「{raw}」的，回落到原样（宁可不动，也不乱调）"}


def pick(intent: str) -> str:
    """人话 → 外观 key。认不出回落 `none`。"""
    return pick_explain(intent)["picked"]


def status(**_kw) -> dict:
    return {"ok": True, "op": "status", "kind": "filmgrade", "root": str(ROOT),
            "looks": len(LOOKS), "chain": "colorbalance→eq→curves→cas→gblur/blend→vignette→noise",
            "default": DEFAULT_LOOK, "fallback": FALLBACK_LOOK,
            "口径": "pick 认不出回落原样；preview 单帧试看；qc 照 black/freeze/yavg/verdict"}


# ──────────────────────────────────────────────────────────────────────
# 调色链（真参数，逐项可读）
# ──────────────────────────────────────────────────────────────────────
def grade_chain(spec: dict, grain: float | None = None, adjust: dict | None = None) -> list[str]:
    """返回这条链**实际施加了哪些档**（给读数用；不施加任何东西就不列）。"""
    applied = []
    g = spec.get("grain", 0.0) if grain is None else float(grain)
    if tuple(spec.get("colorbalance", (1, 1, 1))) != (1.0, 1.0, 1.0):
        applied.append("colorbalance")
    if tuple(spec.get("eq", (1, 1, 1))) != (1.0, 1.0, 1.0):
        applied.append("eq")
    if float(spec.get("curves", 1.0)) != 1.0:
        applied.append("curves")
    if float(spec.get("sharp", 0.0)) > 0:
        applied.append("cas")
    if float(spec.get("bloom", 0.0)) > 0:
        applied.append("bloom")
    if float(spec.get("vignette", 0.0)) > 0:
        applied.append("vignette")
    if g > 0:
        applied.append("grain")
    if adjust:
        applied.append("adjust")
    return applied


def _apply(img, spec: dict, grain: float | None, adjust: dict | None):
    """把外观真正压到像素上。返回 (新图, 逐项读数)。"""
    np = _dep("numpy")
    Image, ImageEnhance, ImageFilter = (_dep("PIL.Image"), _dep("PIL.ImageEnhance"),
                                        _dep("PIL.ImageFilter"))
    rgb = img.convert("RGB")
    a = np.asarray(rgb).astype(np.float32)
    readings: dict = {}

    # ① 色平衡（三通道增益）
    cb = tuple(float(x) for x in spec.get("colorbalance", (1, 1, 1)))
    if cb != (1.0, 1.0, 1.0):
        a *= np.array(cb, dtype=np.float32)
        readings["colorbalance"] = {"r": cb[0], "g": cb[1], "b": cb[2]}

    a = np.clip(a, 0, 255)
    rgb = Image.fromarray(a.astype(np.uint8), "RGB")

    # ② 均衡（亮度 / 对比 / 饱和）
    b, c, s = (float(x) for x in spec.get("eq", (1, 1, 1)))
    if adjust:
        b *= float(adjust.get("brightness", 1.0) or 1.0)
        c *= float(adjust.get("contrast", 1.0) or 1.0)
        s *= float(adjust.get("saturation", 1.0) or 1.0)
    if (b, c, s) != (1.0, 1.0, 1.0):
        if b != 1.0:
            rgb = ImageEnhance.Brightness(rgb).enhance(b)
        if c != 1.0:
            rgb = ImageEnhance.Contrast(rgb).enhance(c)
        if s != 1.0:
            rgb = ImageEnhance.Color(rgb).enhance(s)      # saturation=0 → 真去色
        readings["eq"] = {"brightness": round(b, 3), "contrast": round(c, 3),
                          "saturation": round(s, 3)}

    # ③ 对比曲线（gamma 单项，1.0 = 不动）
    gamma = float(spec.get("curves", 1.0))
    if adjust and adjust.get("gamma"):
        gamma *= float(adjust["gamma"])
    if gamma != 1.0:
        lut = [min(255, max(0, int(((i / 255.0) ** gamma) * 255))) for i in range(256)]
        rgb = rgb.point(lut * 3)
        readings["curves"] = {"gamma": round(gamma, 3)}

    # ④ cas 锐化
    sharp = float(spec.get("sharp", 0.0))
    if sharp > 0:
        rgb = rgb.filter(ImageFilter.UnsharpMask(radius=1.6, percent=int(60 * sharp * 2), threshold=3))
        readings["cas"] = {"percent": int(60 * sharp * 2)}

    # ⑤ 辉光（模糊层叠加）
    bloom = float(spec.get("bloom", 0.0))
    if bloom > 0:
        glow = rgb.filter(ImageFilter.GaussianBlur(radius=6))
        rgb = Image.blend(rgb, Image.blend(rgb, glow, 0.75), min(1.0, bloom))
        readings["bloom"] = {"radius": 6, "alpha": round(min(1.0, bloom), 3)}

    # ⑥ 暗角
    vig = float(spec.get("vignette", 0.0))
    if vig > 0:
        w, h = rgb.size
        yy, xx = np.mgrid[0:h, 0:w]
        d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
        mask = np.clip(1.0 - vig * np.clip(d / 1.4142, 0, 1) ** 1.6, 0, 1)[..., None]
        arr = (np.asarray(rgb).astype(np.float32) * mask)
        rgb = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
        readings["vignette"] = {"strength": round(vig, 3)}

    # ⑦ 颗粒
    g = float(spec.get("grain", 0.0)) if grain is None else float(grain)
    if g > 0:
        arr = np.asarray(rgb).astype(np.float32)
        noise = np.random.default_rng(12345).normal(0, g, arr.shape[:2])[..., None]
        rgb = Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8), "RGB")
        readings["grain"] = {"sigma": round(g, 2)}

    return rgb, readings


def preview(src: str, look: str = DEFAULT_LOOK, out: str = "",
            grain: float | None = None, adjust: dict | None = None) -> dict:
    """单帧试看：定了再上全片。逐项读数，**不报合计**。"""
    try:
        _dep("PIL.Image")
    except RuntimeError as e:
        return {"ok": False, "op": "preview", "status": "needs_dependency", "error": str(e)}

    sp = Path(src) if Path(src).is_absolute() else ROOT / src
    if not sp.is_file():
        return {"ok": False, "op": "preview", "status": "needs_input",
                "error": "源图不存在", "src": str(sp)}

    key = look if look in LOOKS else pick(str(look or ""))
    spec = LOOKS[key]

    try:
        from PIL import Image
        img = Image.open(sp)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "op": "preview", "status": "failed", "error": f"读不开源图：{e}"}

    graded, readings = _apply(img, spec, grain, adjust)

    if not out:
        out = str(ROOT / ".scratch" / "grade" / f"{sp.stem}_{key}.png")
    op = Path(out) if Path(out).is_absolute() else ROOT / out
    op.parent.mkdir(parents=True, exist_ok=True)
    graded.save(op)

    return {"ok": True, "op": "preview", "look": key, "label": spec["label"],
            "src": str(sp), "out": str(op), "size": list(graded.size),
            "chain_applied": grade_chain(spec, grain, adjust),
            # 精修六科目逐项读数（每项独立，不报合计）
            "readings": readings,
            "boundary": "只出单帧；上全片走 actioncam / filmkit"}


# ──────────────────────────────────────────────────────────────────────
# 交付 QC：照着「看着完成 ≠ 过得去」
# ──────────────────────────────────────────────────────────────────────
def qc(path, label: str = "") -> dict:
    """黑帧 / 卡帧 / 平均亮度 / 判定。视频逐帧解，图片按单帧算。"""
    try:
        np = _dep("numpy")
        _dep("PIL.Image")
    except RuntimeError as e:
        return {"ok": False, "op": "qc", "status": "needs_dependency", "error": str(e)}

    p = Path(path) if Path(path).is_absolute() else ROOT / path
    if not p.is_file():
        return {"ok": False, "op": "qc", "status": "needs_input",
                "error": "成片不存在", "film": str(p)}

    frames, kind = [], "image"
    # 先看后缀：图片直接走 PIL，不去惊动 cv2 的 ffmpeg（否则控制台会刷一串解码器报错）
    video_ext = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v", ".flv", ".wmv"}
    if p.suffix.lower() in video_ext:
        try:
            import cv2
            cap = cv2.VideoCapture(str(p))
            if cap.isOpened():
                kind = "video"
                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                step = max(1, total // 120) if total else 1     # 抽到 ~120 帧就够判
                i = 0
                while True:
                    ok, f = cap.read()
                    if not ok:
                        break
                    if i % step == 0:
                        frames.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
                    i += 1
                cap.release()
            else:
                return {"ok": False, "op": "qc", "status": "needs_dependency",
                        "error": "cv2 打不开这个视频（缺对应解码器）", "film": str(p)}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "op": "qc", "status": "needs_dependency",
                    "error": f"视频解码不可用：{e}", "film": str(p)}

    if not frames:
        try:
            from PIL import Image
            frames = [np.asarray(Image.open(p).convert("L"))]
            kind = "image"
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "op": "qc", "status": "failed", "error": f"解不开：{e}"}

    if not frames:
        return {"ok": False, "op": "qc", "status": "failed", "error": "抽不到帧"}

    means = [float(f.mean()) for f in frames]
    yavg = round(sum(means) / len(means), 2)

    # 黑帧：平均亮度 < 16
    black = sum(1 for m in means if m < 16.0)

    # 卡帧：相邻帧几乎完全一致（mean abs diff < 0.5）算连续段
    freeze = 0
    prev = None
    for f in frames:
        if prev is not None and float(np.abs(f.astype(np.int16) - prev.astype(np.int16)).mean()) < 0.5:
            freeze += 1
        prev = f

    reasons = []
    if black:
        reasons.append(f"black={black}")
    if freeze:
        reasons.append(f"freeze={freeze}")
    if yavg < 16.0:
        reasons.append(f"过暗(yavg={yavg})")
    elif yavg > 235.0:
        reasons.append(f"过曝(yavg={yavg})")

    verdict = "通过" if not reasons else "不通过"
    return {"ok": verdict == "通过", "op": "qc", "label": label, "film": str(p), "kind": kind,
            "frames": len(frames), "black": black, "freeze": freeze, "yavg": yavg,
            "verdict": verdict, "why": "；".join(reasons) if reasons else "无黑帧/无卡帧/亮度在范围内",
            "boundary": "抽帧判，不是逐帧全扫；判的是机械化指标，不判内容好坏"}
