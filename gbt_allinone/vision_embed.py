# -*- coding: utf-8 -*-
"""vision_embed -- 图像语义特征 + 相似度（CLIP ViT-B/32 视觉编码器 · ONNX 路线）

不走 torch：本机 onnxruntime 早就装好了，官方的 CLIP 视觉编码器 onnx 直下即可，
输出已经是投影后的 **512 维 image_embeds**，拿来算余弦相似度正好。

── 为什么要它（实测数据支撑，不是拍脑袋）──────────────────────────────
拿真实界面截图做了三组对照：

  变体              CLIP-512   aHash
  多一条报错条        0.9875    0.9531   ← 局部变化：aHash 更敏感，它更好
  反色(深色主题)      0.9404    0.0000   ← 主题切换：aHash 归零，CLIP 认得出
  缩放 50%            1.0000    1.0000   ← 缩放：两者都行

结论很清楚：**aHash 的软肋不是缩放和调色，是主题/反色切换。**
所以本模块不取代 aHash，而是补它的盲区：语义同一性判定用 CLIP，像素级微调用 aHash。
`similarity()` 会同时回这两个数，并在两者打架时给出人话解释。

── 铁律 ──────────────────────────────────────────────
1. **只回向量与分数，绝不回图**。
2. **不编判定**：阈值写在明面上，分数照实回，让调用方自己判断。
3. **不做无根据的相似**：图读不到就如实报错，不用零向量充数。
"""
from __future__ import annotations

import os
import threading

MODEL_REL = "state/models/clip_vision.onnx"
ENV_MODEL = "GBT_CLIP_ONNX"

# CLIP ViT-B/32 官方预处理参数（与 HF CLIPImageProcessor 一致）
_SIZE = 224
_MEAN = (0.48145466, 0.4578275, 0.40821073)
_STD = (0.26862954, 0.26130258, 0.27577711)

# 判定阈值（基于实测标定：同图 1.0000 · 深色主题 0.9404 · 异图 0.3813）
TH_SAME = 0.97       # ≥ 判"同一画面"
TH_SEMANTIC = 0.90   # ≥ 判"语义同一（可能有主题/配色变化）"
TH_NEAR = 0.70       # ≥ 判"相近"

_SESSION = None
_SESSION_PATH = None
_LOCK = threading.Lock()


def _payload_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def model_path() -> str:
    override = os.environ.get(ENV_MODEL)
    if override:
        return override
    return os.path.join(_payload_root(), *MODEL_REL.split("/"))


def model_ready() -> bool:
    p = model_path()
    return os.path.exists(p) and os.path.getsize(p) > 50_000_000


def _session():
    global _SESSION, _SESSION_PATH
    with _LOCK:
        path = model_path()
        if _SESSION is not None and _SESSION_PATH == path:
            return _SESSION
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        _SESSION = ort.InferenceSession(path, sess_options=so,
                                        providers=["CPUExecutionProvider"])
        _SESSION_PATH = path
        return _SESSION


def _load(path: str):
    from PIL import Image
    if not os.path.exists(path):
        raise FileNotFoundError("图片不存在: %s" % path)
    return Image.open(path).convert("RGB")


def _prep(im):
    import numpy as np
    im = im.convert("RGB")
    w, h = im.size
    s = _SIZE / float(min(w, h))
    im = im.resize((max(1, round(w * s)), max(1, round(h * s))), _BICUBIC())
    w, h = im.size
    left, top = (w - _SIZE) // 2, (h - _SIZE) // 2
    im = im.crop((left, top, left + _SIZE, top + _SIZE))
    a = np.asarray(im, dtype="float32") / 255.0
    a = (a - np.array(_MEAN, dtype="float32")) / np.array(_STD, dtype="float32")
    return a.transpose(2, 0, 1)[None].astype("float32")


def _BICUBIC():
    from PIL import Image
    return getattr(Image, "Resampling", Image).BICUBIC


def _cos(a, b) -> float:
    import numpy as np
    a = np.asarray(a, dtype="float32").ravel()
    b = np.asarray(b, dtype="float32").ravel()
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def _ahash(im, n: int = 8):
    import numpy as np
    from PIL import Image
    g = im.convert("L").resize((n, n), getattr(Image, "Resampling", Image).BILINEAR)
    a = np.asarray(g, dtype="float32")
    return (a > a.mean()).astype("uint8").ravel()


def _hsim(a, b) -> float:
    import numpy as np
    return 1.0 - float(np.count_nonzero(a != b)) / float(len(a))


# ────────────────────────── 对外 ──────────────────────────
def embed(image: str, full: bool = False) -> dict:
    """取 512 维语义向量。默认不把完整向量塞进返回值（省 token），只回指纹。"""
    if not image:
        return {"ok": False, "reason": "需要 image：本地图片路径"}
    if not model_ready():
        return {"ok": False, "status": "needs_dependency",
                "reason": "缺模型文件: %s（可设 %s 指定别处）" % (model_path(), ENV_MODEL)}
    import hashlib
    import numpy as np
    sess = _session()
    vec = sess.run(None, {"pixel_values": _prep(_load(image))})[0][0]
    out = {
        "ok": True, "backend": "clip-vit-base-patch32-onnx",
        "dim": int(vec.shape[0]),
        "l2": round(float(np.linalg.norm(vec)), 6),
        "fingerprint": hashlib.sha256(vec.tobytes()).hexdigest()[:16],
    }
    if full:
        out["vector"] = [round(float(x), 6) for x in vec]
    return out


def similarity(image_a: str, image_b: str) -> dict:
    """两张图像不像。CLIP 语义分 + aHash 像素分一起回，打架时说人话。"""
    if not image_a or not image_b:
        return {"ok": False, "reason": "需要 image_a 与 image_b 两个本地路径"}
    if not model_ready():
        return {"ok": False, "status": "needs_dependency",
                "reason": "缺模型文件: %s" % model_path()}
    try:
        ia, ib = _load(image_a), _load(image_b)
    except Exception as exc:
        return {"ok": False, "reason": "%s: %s" % (type(exc).__name__, str(exc)[:120])}

    sess = _session()
    va = sess.run(None, {"pixel_values": _prep(ia)})[0][0]
    vb = sess.run(None, {"pixel_values": _prep(ib)})[0][0]
    cos = _cos(va, vb)

    ah = _hsim(_ahash(ia), _ahash(ib))

    if cos >= TH_SAME:
        verdict = "同一画面"
    elif cos >= TH_SEMANTIC:
        verdict = "语义同一（可能有主题/配色变化）"
    elif cos >= TH_NEAR:
        verdict = "相近"
    else:
        verdict = "不同"

    note = ""
    if cos >= TH_SEMANTIC and ah < 0.5:
        note = ("aHash 只有 %.2f 但语义 %.2f —— 典型主题切换/反色，"
                "这个判断该信语义分，别信像素分" % (ah, cos))
    elif cos < TH_NEAR and ah > 0.85:
        note = ("aHash 高达 %.2f 但语义只有 %.2f —— 布局相同但内容不同，"
                "别被像素分骗了" % (ah, cos))

    return {"ok": True, "backend": "clip-vit-base-patch32-onnx",
            "cosine": round(cos, 4), "ahash": round(ah, 4),
            "verdict": verdict,
            "thresholds": {"same": TH_SAME, "semantic": TH_SEMANTIC, "near": TH_NEAR},
            "note": note,
            "use": "主题/语义判断信 cosine；微小局部改动看 ahash"}


def nearest(base: str, candidates) -> dict:
    """在候选图里找最像 base 的那张（用于"这还是刚才那个页面吗"）。"""
    if not base or not candidates:
        return {"ok": False, "reason": "需要 base 与 candidates（路径列表）"}
    rows = []
    for c in candidates:
        r = similarity(base, c)
        if r.get("ok"):
            rows.append({"image": c, "cosine": r["cosine"],
                         "ahash": r["ahash"], "verdict": r["verdict"]})
        else:
            rows.append({"image": c, "error": r.get("reason")})
    rows.sort(key=lambda x: -(x.get("cosine") or -1))
    return {"ok": True, "count": len(rows), "ranked": rows,
            "best": rows[0] if rows else None}


def run(op: str = "similarity", **kw) -> dict:
    op = str(op or "similarity")
    if op in ("similarity", "compare", "diff"):
        return similarity(kw.get("image_a") or kw.get("a") or kw.get("image"),
                          kw.get("image_b") or kw.get("b") or kw.get("template"))
    if op in ("embed", "vector", "fingerprint"):
        return embed(kw.get("image"), bool(kw.get("full")))
    if op in ("nearest", "rank"):
        return nearest(kw.get("base") or kw.get("image"), kw.get("candidates") or [])
    if op in ("status", "health"):
        return {"ok": True, "model": model_path(), "ready": model_ready(),
                "size_mb": round(os.path.getsize(model_path()) / 1e6, 2) if model_ready() else 0,
                "dim": 512, "backend": "clip-vit-base-patch32-onnx"}
    return {"ok": False, "reason": "未知 op: %s（支持 similarity/embed/nearest/status）" % op}
