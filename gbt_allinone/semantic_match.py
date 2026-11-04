# -*- coding: utf-8 -*-
"""semantic_match —— 中文语义匹配（bge-small-zh-v1.5 · ONNX · 零 torch）。

**定位：第二个视角，不是替代品。** 依据是实测（2026-11-04，63 条真触发词评估集）：

    生产 router（2-gram + L1）  明显更高
    bge 语义 top1              低 47.6 pp

    语义赢的 4 条全是组合词：UI 组件 / 动画 / 动效 / 出作品
    语义输的 38 条全是极短词：读字→body_volume · OCR→codebuddy · 抠图→image_scout
                              检测→selfscan · 控件→comfyui · 按钮→body_click

所以规矩写死在这里：
  · **短词（≤4 字）不要问它** —— 那正是它错得最狠的地方，2-gram 更准；
  · 只在「关键词完全没候选」或「长句自然表达」时用它给 top-k **参考**；
  · **只给候选，不拍板** —— 采纳与否由调用方决定（本模块永不返回"就用这个"）。

零重依赖：onnxruntime + tokenizers + numpy（本机已有，无需 torch / transformers）。
"""
from __future__ import annotations

import os
import json
import hashlib

_MODEL_DIR_REL = os.path.join("state", "models", "bge-small-zh")
_VEC_CACHE = "caps_vec.npy"
_SIG_CACHE = "caps_sig.txt"
_DIM = 512

_sess = None
_tok = None
_mats = None          # (caps_list, ndarray)
_load_err = ""


def _root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _atomic_write(path: str, text: str, encoding: str = "utf-8") -> None:
    """原子替换：写临时 → fsync → os.replace。避免半截文件被当成"有效缓存"读进来。"""
    d = os.path.dirname(path) or "."
    tmp = os.path.join(d, ".tmp.%s.%d" % (os.path.basename(path), os.getpid()))
    try:
        with open(tmp, "w", encoding=encoding) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def _atomic_save_npy(path: str, arr) -> None:
    """向量矩阵也原子落盘。

    ⚠️ np.save 有个坑：文件名**不以 .npy 结尾**时它会自动补 `.npy`
    （写 `x.tmp` 实际生成 `x.tmp.npy`），所以临时名必须自带 `.npy`，
    否则 os.replace 找不到文件。这条是实测踩出来的，不是想当然。
    """
    import numpy as np
    d = os.path.dirname(path) or "."
    tmp = os.path.join(d, ".tmp.caps_vec.%d.npy" % os.getpid())
    try:
        np.save(tmp, arr)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def model_dir() -> str:
    return os.path.join(_root(), _MODEL_DIR_REL)


def model_ready() -> bool:
    d = model_dir()
    return (os.path.exists(os.path.join(d, "model.onnx"))
            and os.path.exists(os.path.join(d, "tokenizer.json")))


def _load():
    """懒加载：第一次真要用才进内存（模型 95MB，不该拖慢 import）。"""
    global _sess, _tok, _load_err
    if _sess is not None:
        return True
    if not model_ready():
        _load_err = "模型文件缺失（%s）" % model_dir()
        return False
    try:
        import onnxruntime as ort
        from tokenizers import Tokenizer
        _sess = ort.InferenceSession(os.path.join(model_dir(), "model.onnx"),
                                     providers=["CPUExecutionProvider"])
        _tok = Tokenizer.from_file(os.path.join(model_dir(), "tokenizer.json"))
        return True
    except Exception as e:                                        # noqa: BLE001
        _load_err = "%s: %s" % (type(e).__name__, str(e)[:160])
        _sess = None
        return False


def _encode(text: str):
    """bge 官方推荐：CLS pooling + L2 normalize（不是 mean pooling）。"""
    import numpy as np
    names = [i.name for i in _sess.get_inputs()]
    ids = _tok.encode(str(text)).ids[:200]
    n = len(ids)
    feed = {}
    if "input_ids" in names:
        feed["input_ids"] = np.array([ids], dtype=np.int64)
    if "attention_mask" in names:
        feed["attention_mask"] = np.ones((1, n), dtype=np.int64)
    if "token_type_ids" in names:
        feed["token_type_ids"] = np.zeros((1, n), dtype=np.int64)
    out = _sess.run([_sess.get_outputs()[0].name], feed)[0][0, 0]
    return out / (np.linalg.norm(out) + 1e-9)


_HUMAN = None


def _human_map() -> dict:
    """能力 → 一句人话摘要（数据文件，不改代码，可增量补）。

    为什么要单独一份：实测同一模型下，编码**技术 desc** 的区分度只有 +0.104
    （top1 3/5），编码**人话摘要**后升到 +0.231（top1 5/5）；而且异类均分几乎不动
    （0.408→0.412）——说明是人话在**精准提升该匹配的那个**，不是把整体拉近。
    desc 是写给人看的技术文档（塞满"主人令「…」"和括号），不是"用户想干什么"。
    """
    global _HUMAN
    if _HUMAN is not None:
        return _HUMAN
    p = os.path.join(_root(), "state", "human_abstracts.json")
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        _HUMAN = {k: str(v) for k, v in d.items() if not str(k).startswith("_")}
    except Exception:
        _HUMAN = {}
    return _HUMAN


def _cap_text(cap: str, desc: str) -> str:
    """能力 → 待编码文本。**人话摘要优先**；没有才退回 desc（截 180 字）。"""
    h = _human_map().get(cap)
    if h:
        return h
    return "%s %s" % (cap.replace("_", " "), (desc or "")[:180])


def _build_matrix(force: bool = False):
    """构建/加载 424 个能力的向量矩阵（带指纹缓存：能力表没变就不重算）。"""
    global _mats
    import numpy as np
    from .caps_registry import BENIGN_CAPS

    caps = sorted(BENIGN_CAPS)
    texts = [_cap_text(c, str(BENIGN_CAPS[c].get("desc") or "")) for c in caps]
    sig = hashlib.md5("\n".join(texts).encode("utf-8")).hexdigest()[:16]

    d = model_dir()
    vp = os.path.join(d, _VEC_CACHE)
    sp = os.path.join(d, _SIG_CACHE)

    if not force and os.path.exists(vp) and os.path.exists(sp):
        try:
            with open(sp, "r", encoding="utf-8") as f:
                if f.read().strip() == sig:
                    arr = np.load(vp)
                    if arr.shape[0] == len(caps):
                        _mats = (caps, arr)
                        return {"ok": True, "cached": True, "caps": len(caps), "sig": sig}
        except Exception:
            pass

    arr = np.zeros((len(caps), _DIM), dtype=np.float32)
    for i, t in enumerate(texts):
        arr[i] = _encode(t)
    # 原子落盘：这个矩阵 425×512 约 0.9MB，写一半挂掉会留下形状对但数值坏的缓存，
    # 读进来不会报错，只会让语义匹配悄悄变差 —— 最难查的那种坏。
    _atomic_save_npy(vp, arr)
    _atomic_write(sp, sig)
    _mats = (caps, arr)
    return {"ok": True, "cached": False, "caps": len(caps), "sig": sig}


def status() -> dict:
    d = model_dir()
    out = {
        "ok": True,
        "ready": model_ready(),
        "dir": d,
        "model_mb": (round(os.path.getsize(os.path.join(d, "model.onnx")) / 1048576.0, 1)
                     if os.path.exists(os.path.join(d, "model.onnx")) else 0),
        "vec_cache": os.path.exists(os.path.join(d, _VEC_CACHE)),
        "load_error": _load_err,
        "backend": "onnxruntime + tokenizers（零 torch）",
        "positioning": "第二个视角：只给候选不拍板；短词(≤4字)请走 2-gram",
        "human_abstracts": {
            "covered": len(_human_map()),
            "file": os.path.join(_root(), "state", "human_abstracts.json"),
            "note": "缺摘要的能力会回退用 desc 编码 —— 那时准确率明显下降（实测区分度 0.231→0.104）",
        },
        "measured": {"eval_n": 63, "sem_top1_vs_router": "-47.6 pp",
                     "wins": ["UI 组件", "动画", "动效", "出作品"],
                     "loses": ["读字", "OCR", "抠图", "检测", "控件", "按钮"]},
    }
    if _mats:
        out["caps_cached"] = len(_mats[0])
    return out


def match(text: str, top_k: int = 3, min_score: float = 0.0) -> dict:
    """把一句话和 N 个能力描述算余弦，返回 top-k **参考**候选。

    铁律（写在返回值里，防下游误用）：
      · 只给候选，不拍板 —— 没有 "best"/"chosen" 字段；
      · 短词（≤4 字）会额外标注 `short_query_warning`，因为实测那里它最不准。
    """
    import numpy as np
    t = str(text or "").strip()
    if not t:
        return {"ok": False, "reason": "需要 text：要匹配的一句话"}
    if not _load():
        return {"ok": False, "reason": "语义模型不可用", "detail": _load_err,
                "hint": "检查 state/models/bge-small-zh/ 下 model.onnx 与 tokenizer.json"}
    if _mats is None:
        st = _build_matrix()
        if not st.get("ok"):
            return st
    caps, arr = _mats
    v = _encode(t)
    sims = arr @ v
    order = np.argsort(-sims)[:max(1, min(int(top_k), 10))]

    from .caps_registry import BENIGN_CAPS as _BC
    cands = []
    for i in order:
        s = float(sims[i])
        if s < float(min_score):
            continue
        cap = caps[int(i)]
        cands.append({"cap": cap, "score": round(s, 4),
                      "desc": str(_BC.get(cap, {}).get("desc") or "")[:60]})
    out = {
        "ok": True,
        "query": t[:120],
        "candidates": cands,
        "count": len(cands),
        "is_reference_only": True,
        "rule": "本模块只提供参考候选，不改变任何现有路由排序；采纳与否由调用方判断",
    }
    if len(t) <= 4:
        out["short_query_warning"] = ("短词（≤4 字）在实测中语义匹配错误率最高"
                                     "（读字→body_volume / OCR→codebuddy / 抠图→image_scout）；"
                                     "这种输入请优先用关键词精确匹配")
    return out


def run(op: str = "match", **kw) -> dict:
    o = str(op or "match").strip()
    if o in ("status", "probe"):
        return status()
    if o in ("match", "semantic", "find"):
        return match(kw.get("text") or kw.get("query") or kw.get("q"),
                     int(kw.get("top_k") or kw.get("k") or 3),
                     float(kw.get("min_score") or 0.0))
    if o in ("build", "rebuild"):
        if not _load():
            return {"ok": False, "reason": "语义模型不可用", "detail": _load_err}
        return _build_matrix(force=bool(kw.get("force")))
    return {"ok": False, "reason": "未知 op: %s" % o,
            "supported": ["match", "status", "build"]}
