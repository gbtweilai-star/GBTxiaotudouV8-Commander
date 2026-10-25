# -*- coding: utf-8 -*-
"""vanavana 变体生成器 —— 不重导出，直接改现有 GGUF，逐个试哪条修对了

思路（比"重跑导出脚本"快得多）：
  你的 GGUF 已经能加载、能跑、形状全对，只是输出乱码。
  ⇒ 那就**只动可疑的那几个张量**，生成 3 个变体，各跑一句「你是谁？」，谁出人话谁赢。

三个变体：
  --fix permute  q/k 做 RoPE 成对交错置换（文档没列，最可能的病灶）
  --fix swap     token_embd 与 output 互换（文档候选 #1）
  --fix both     两个都做

用法：
  py -3.12 -X utf8 gguf-fix-variants.py --in state\\weights\\gbt-v8-v82-q4_0-fixed.gguf --fix permute

依赖：numpy + gguf（pip install gguf）
输出：<in>.permute.gguf / <in>.swap.gguf / <in>.both.gguf

⚠ 本器只做"张量级手术"，不动元数据（bos/eos/chat_template 原样搬）。
  Q4_0 是量化格式：permute 走"解量化→换行→重量化"，有量化误差（正常，不会改变结论）。
"""
from __future__ import annotations
import argparse, shutil, sys
from pathlib import Path

import numpy as np

N_HEAD, N_HEAD_KV = 28, 4     # config.json: heads 28 / kv 4


def permute_rope(w: np.ndarray, n_head: int, n_head_kv: int) -> np.ndarray:
    """llama.cpp 的 RoPE 成对交错置换：reshape → swapaxes(1,2) → reshape（形状不变）。"""
    if n_head_kv and n_head != n_head_kv:
        n_head = n_head_kv
    return (w.reshape(n_head, 2, w.shape[0] // n_head // 2, *w.shape[1:])
             .swapaxes(1, 2).reshape(w.shape))


def deq(tname: str, raw: np.ndarray, qt) -> np.ndarray:
    """把 GGUF 里可能被量化过的张量解回 float32。"""
    import gguf
    kind = str(qt)
    if "Q4_0" in kind:
        from gguf.quants import dequantize
        n = int(np.prod(raw.shape))
        flat = dequantize(raw.reshape(-1), gguf.GGMLQuantizationType.Q4_0, n)
        return np.asarray(flat, dtype=np.float32).reshape(raw.shape[0], raw.shape[1] if raw.ndim > 1 else 1)
    if "F16" in kind or "F32" in kind or "BF16" in kind:
        return np.asarray(raw, dtype=np.float32)
    from gguf.quants import dequantize
    n = int(np.prod(raw.shape))
    try:
        flat = dequantize(raw.reshape(-1), qt, n)
        return np.asarray(flat, dtype=np.float32).reshape(raw.shape)
    except Exception:
        return np.asarray(raw, dtype=np.float32)


def requant(data: np.ndarray, qt):
    """按原量化类型写回。"""
    import gguf
    from gguf.quants import quantize
    kind = str(qt)
    if "Q4_0" in kind:
        return quantize(data.astype(np.float32).reshape(-1), gguf.GGMLQuantizationType.Q4_0)
    return data.astype(np.float16)


def build(inp: Path, out: Path, fix: str) -> int:
    import gguf
    r = gguf.GGUFReader(str(inp))

    # ── 元数据原样搬 ──
    w = gguf.GGUFWriter(str(out), r.get_field("general.architecture").contents())
    for k, f in r.fields.items():
        if k.startswith("GGUF.") or k in ("general.architecture",):
            continue
        try:
            v = f.contents()
            if isinstance(v, (str, int, float, bool)):
                w.add_key_value(k, v, f.types[0] if hasattr(f, "types") else None)
            elif isinstance(v, (list, tuple)):
                w.add_key_value(k, list(v), f.types[0] if hasattr(f, "types") else None)
        except Exception:
            pass

    done = {"permute": 0, "swap": 0}
    tensors = {t.name: t for t in r.tensors}

    order = ["token_embd.weight", "output.weight"] if True else []
    names = [t.name for t in r.tensors]

    for name in names:
        t = tensors[name]
        raw = np.asarray(t.data)
        qt = t.tensor_type

        # ── swap：两张大表互换 ──
        if fix in ("swap", "both") and name in ("token_embd.weight", "output.weight"):
            other = "output.weight" if name == "token_embd.weight" else "token_embd.weight"
            if other in tensors:
                raw = np.asarray(tensors[other].data)
                qt = tensors[other].tensor_type
                done["swap"] += 1

        # ── permute：q/k 做 RoPE 置换 ──
        elif fix in ("permute", "both") and (
                ".attn_q.weight" in name or ".attn_k.weight" in name):
            data = deq(name, raw, qt)
            if data.ndim == 2:
                data = permute_rope(data, N_HEAD, N_HEAD_KV)
                raw = requant(data, qt)
                done["permute"] += 1

        w.add_tensor(name, raw, raw_dtype=qt)

    w.write_header_to_file()
    w.write_kv_data_to_file()
    w.write_tensors_to_file()
    w.close()
    print("  写出: %s" % out)
    print("  改动: permute %d 个张量 · swap %d 次" % (done["permute"], done["swap"]))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--fix", required=True, choices=["permute", "swap", "both"])
    a = ap.parse_args()

    src = Path(a.inp)
    if not src.is_file():
        print("🔴 输入不在:", src); return 2
    dst = src.with_suffix(".%s.gguf" % a.fix)

    print("=" * 58)
    print("变体生成: %s → %s" % (src.name, dst.name))
    print("=" * 58)
    try:
        return build(src, dst, a.fix)
    except ImportError as e:
        print("🔴 缺依赖:", e, "→ pip install gguf numpy"); return 2
    except Exception as e:
        print("🔴 失败:", type(e).__name__, e)
        print("   备用方案：直接改你的 export-gguf-q4.py（下面三处），重跑导出")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
