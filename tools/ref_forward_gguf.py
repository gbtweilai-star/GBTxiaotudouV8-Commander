# -*- coding: utf-8 -*-
"""参考实现：直接读 GGUF 权重，用 numpy 亲手算一次 Qwen2 前向。

目的：绕开「引擎说好、llama.cpp 说坏」的僵局，用第三把尺子判定权重到底对不对。
它不依赖 llama.cpp、不依赖 transformers，只用 numpy + gguf 两个包。

用法：
    GGUF_PATH=/path/to/model.gguf python3 ref_forward_gguf.py "105043,100165,11319"
    # 参数是逗号分隔的 token id；给单个 id 也行
    # 支持 Q4_0(18字节/32值) / Q5_0 / Q8_0(34字节/32值) / F16 / F32

输出：
    · 逐层激活值 |x| 均值  —— 这是判别量化档够不够的核心读数
    · 最后一位的 top-10 词与 logit  —— 分布尖不尖，一眼看出模型困不困惑

实例（2026-10-24 实测，v82 7.6B）：
    Q4_0：层16 |x|=63.5 → 层27 |x|=605（爆炸）· top-10 平坦（vana/Modificar…）
    Q8_0：层16 |x|=2.78 → 层27 |x|=6.19（稳定）· top-1 ' ' logit 29.39
    ⇒ 同一份权重，只换量化档，一个崩一个通。
"""
import os
import struct
import sys
import time

import numpy as np
from gguf.quants import dequantize

F = os.environ.get("GGUF_PATH", "model.gguf")
S = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8, 13: 8}
BLK_BYTES = {2: 18, 8: 34}      # Q4_0=18, Q8_0=34 字节 / 32 值


def parse(fp):
    f = open(fp, "rb")
    f.read(4)
    ver, nt, nkv = struct.unpack("<IQQ", f.read(20))

    def rs():
        n = struct.unpack("<Q", f.read(8))[0]
        return f.read(n).decode("utf-8", "replace")

    align = 32
    kv = {}
    for _ in range(nkv):
        k = rs()
        t = struct.unpack("<I", f.read(4))[0]
        if t == 8:
            kv[k] = rs()
            continue
        if t == 9:
            et = struct.unpack("<I", f.read(4))[0]
            n = struct.unpack("<Q", f.read(8))[0]
            if et == 8:
                arr = [rs() for _ in range(n)]
                if k == "tokenizer.ggml.tokens":
                    kv[k] = arr
            else:
                f.read(n * S.get(et, 1))
            continue
        sz = S.get(t, 0)
        v = f.read(sz) if sz else None
        if k == "general.alignment" and t == 4:
            align = struct.unpack("<I", v)[0]
        kv[k] = v
    T = {}
    for _ in range(nt):
        name = rs()
        nd = struct.unpack("<I", f.read(4))[0]
        dims = tuple(int(x) for x in struct.unpack("<%dQ" % nd, f.read(8 * nd)))
        typ = struct.unpack("<I", f.read(4))[0]
        off = struct.unpack("<Q", f.read(8))[0]
        T[name] = (dims, typ, off)
    pos = f.tell()
    return f, T, kv, (pos + align - 1) // align * align


f, T, kv, D0 = parse(F)
print("  数据起点 %d · 张量 %d" % (D0, len(T)), flush=True)


def get(name, r0=0, r1=None):
    """读张量第 r0..r1 行（dims[1] 方向），返回 [rows, ne0] float32。
    🔴 4 GB+ 的 GGUF 不能用 gguf.GGUFReader（mmap 会 OOM），所以这里手工解析 + 按需 seek。"""
    dims, typ, off = T[name]
    ne0 = dims[0]
    nrow = dims[1] if len(dims) > 1 else 1
    r1 = nrow if r1 is None else min(r1, nrow)
    rows = r1 - r0
    if typ == 0:
        f.seek(D0 + off + r0 * ne0 * 4)
        a = np.frombuffer(f.read(rows * ne0 * 4), dtype=np.float32)
        return a.reshape(rows, ne0).copy()
    if typ == 1:
        f.seek(D0 + off + r0 * ne0 * 2)
        a = np.frombuffer(f.read(rows * ne0 * 2), dtype=np.float16)
        return a.reshape(rows, ne0).astype(np.float32)
    blk = BLK_BYTES.get(typ)
    if blk is None:
        raise ValueError("unsupported quant type %d" % typ)
    rb = (ne0 // 32) * blk
    f.seek(D0 + off + r0 * rb)
    raw = np.frombuffer(f.read(rows * rb), dtype=np.uint8).reshape(rows, rb)
    out = dequantize(raw, typ)
    return np.asarray(out, dtype=np.float32).reshape(rows, ne0)


def rope(v, pos, nheads, theta=1e6, hd=128):
    """NEOX 半分割 RoPE（Qwen2 用的就是这种：pairs offset by n_rot/2）。
    ⚠️ 不要对它做「交错置换」—— llama.cpp 源码里 Qwen2 属于 LLAMA_ROPE_TYPE_NEOX，
       与 HF 的 rotate_half 一致，补置换反而更差（实测过）。"""
    half = hd // 2
    inv = 1.0 / (theta ** (np.arange(0, half, dtype=np.float32) * 2.0 / hd))
    fr = pos * inv
    c, s = np.cos(fr), np.sin(fr)
    vv = v.reshape(nheads, hd)
    x1, x2 = vv[:, :half], vv[:, half:]
    return np.concatenate([x1 * c - x2 * s, x1 * s + x2 * c], axis=1).reshape(-1)


def rms(x):
    return x / np.sqrt((x * x).mean(-1, keepdims=True) + 1e-6)

toks = kv.get("tokenizer.ggml.tokens")
target = sys.argv[1] if len(sys.argv) > 1 else "0"
IDS = [int(x) for x in target.split(",")] if "," in target else None
tid = None if IDS else (int(target) if target.isdigit() else None)
S_ = len(IDS) if IDS else 1
idx = IDS if IDS else [tid]
print("  输入 %d 个 token: %s" % (S_, idx), flush=True)

# Qwen2-7B 的几何（可从 GGUF 元数据读，这里写死是这份权重的实测值）
H, NH, NKV, HD, NL, FF = 3584, 28, 4, 128, 28, 18944
rep = NH // NKV
t0 = time.time()

x = np.stack([get("token_embd.weight", i, i + 1)[0] for i in idx])     # [S, H]
print("  embed 前 5 值 %s · %.1fs" % (np.round(x[:3, :3], 5).tolist(), time.time() - t0), flush=True)

for li in range(NL):
    p = "blk.%d." % li
    # ---- attention ----
    h = rms(x) * get(p + "attn_norm.weight")[0]
    q = (get(p + "attn_q.weight") @ h.T).T + get(p + "attn_q.bias")[0]
    k = (get(p + "attn_k.weight") @ h.T).T + get(p + "attn_k.bias")[0]
    v = (get(p + "attn_v.weight") @ h.T).T + get(p + "attn_v.bias")[0]
    q = np.stack([rope(q[s], s, NH) for s in range(S_)])
    k = np.stack([rope(k[s], s, NKV) for s in range(S_)])
    qh = q.reshape(S_, NH, HD).transpose(1, 0, 2)
    kh = k.reshape(S_, NKV, HD).transpose(1, 0, 2)
    vh = v.reshape(S_, NKV, HD).transpose(1, 0, 2)
    kx = np.repeat(kh, rep, axis=0)
    vx = np.repeat(vh, rep, axis=0)
    sc = (qh @ kx.transpose(0, 2, 1)) / np.sqrt(HD)
    if S_ > 1:                                    # prefill 必须带因果掩码
        mask = np.tril(np.ones((S_, S_), dtype=bool))
        sc = np.where(mask[None, :, :], sc, -1e9)
    sc = sc - sc.max(-1, keepdims=True)
    aw = np.exp(sc)
    aw /= aw.sum(-1, keepdims=True)
    o = (aw @ vx).transpose(1, 0, 2).reshape(S_, H)
    x = x + (get(p + "attn_output.weight") @ o.T).T
    # ---- SwiGLU（分块，省内存）----
    h2 = rms(x) * get(p + "ffn_norm.weight")[0]
    y = np.empty((S_, FF), dtype=np.float32)
    for s0 in range(0, FF, 4096):
        s1 = min(s0 + 4096, FF)
        g = (get(p + "ffn_gate.weight", s0, s1) @ h2.T).T
        u = (get(p + "ffn_up.weight", s0, s1) @ h2.T).T
        y[:, s0:s1] = g / (1.0 + np.exp(-g)) * u          # silu(g) * u
    x = x + (get(p + "ffn_down.weight") @ y.T).T
    if li % 4 == 0 or li == NL - 1:
        # 🔴 这个读数就是判别量化档够不够的核心：正常模型逐层缓慢增长，
        #    Q4_0 在这份权重上会一路翻到几百（爆炸）。
        print("    层 %02d · %.0fs · |x|=%.3f" % (li, time.time() - t0, float(np.abs(x).mean())), flush=True)

# ---- 输出层 ----
xn = rms(x[-1:])[0] * get("output_norm.weight")[0]
xn = np.asarray(xn, dtype=np.float32)
np.save("xn.npy", xn)
print("  output_norm 后 |x|=%.4f · %.0fs" % (float(np.abs(xn).mean()), time.time() - t0), flush=True)

V = T["output.weight"][0][1]
logits = np.empty(V, dtype=np.float32)
for s0 in range(0, V, 2048):
    s1 = min(s0 + 2048, V)
    w = np.asarray(get("output.weight", s0, s1), dtype=np.float32)
    logits[s0:s1] = w @ xn
    del w

print()
print("  === 参考实现 top-10（分布尖不尖，一眼看出模型困不困惑）===")
for i in np.argsort(-logits)[:10]:
    print("    id %-7d %-18r  logit %.4f" % (i, toks[i][:16], float(logits[i])))
print()
print("  总耗时 %.0fs" % (time.time() - t0))
f.close()
