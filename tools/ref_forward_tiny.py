#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ref_forward_tiny.py —— 单 token 参考前向（numpy），用来给浏览器实现定病灶

为什么不复用 tools/ref_forward_gguf.py：那一份是**诊断脚本**（硬编码 qwen2、
模块级执行、只打 top-k），不是一个能 import 的参考实现。硬改它会破坏它原有用途。

本器只做一件事：**同一 token，逐层打 |x| 均值**，好和浏览器里的读数一格一格对。
口径：只走 pos=0（单 token）⇒ 注意力退化成 ctx=v，把 RoPE/掩码/缓存这些变量先摘掉。

用法： python3 tools/ref_forward_tiny.py [--model /tmp/tiny.gguf] [--token 504]
"""
from __future__ import annotations

import argparse
import struct
import sys

import numpy as np

GGUF_T = {0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
SIZES = {0:'<f4',1:'<f2'}


def parse(path):
    f = open(path, 'rb')
    assert f.read(4) == b'GGUF'
    ver, = struct.unpack('<I', f.read(4))
    nt, = struct.unpack('<Q', f.read(8))
    nkv, = struct.unpack('<Q', f.read(8))

    def rs():
        n, = struct.unpack('<Q', f.read(8))
        return f.read(n).decode('utf-8', 'replace')

    def rv(t):
        if t == 8:
            return rs()
        if t == 9:
            et, = struct.unpack('<I', f.read(4))
            n, = struct.unpack('<Q', f.read(8))
            if et == 8:
                return [rs() for _ in range(n)]
            if et in (4, 5):
                f.read(4 * n); return None
            if et in (0, 1, 7):
                f.read(n); return None
            if et == 6:
                f.read(4 * n); return None
            for _ in range(n):
                rv(et)
            return None
        sz = struct.calcsize('<' + GGUF_T[t])
        return struct.unpack('<' + GGUF_T[t], f.read(sz))[0]

    kv = {}
    for _ in range(nkv):
        k = rs(); t, = struct.unpack('<I', f.read(4)); kv[k] = rv(t)
    tens = {}
    for _ in range(nt):
        name = rs()
        nd, = struct.unpack('<I', f.read(4))
        dims = [struct.unpack('<Q', f.read(8))[0] for _ in range(nd)]
        ty, = struct.unpack('<I', f.read(4))
        off, = struct.unpack('<Q', f.read(8))
        tens[name] = (dims, ty, off)
    al = kv.get("general.alignment", 32)
    data = ((f.tell() + al - 1) // al) * al
    f.seek(0)
    blob = f.read()
    return kv, tens, data, blob


def f16arr(u8):
    return np.frombuffer(u8, dtype='<f2').astype(np.float32)


def deq(blob, off, ty, n):
    b = blob
    if ty == 0:
        return np.frombuffer(b[off:off + 4 * n], dtype='<f4').astype(np.float32)
    if ty == 1:
        return np.frombuffer(b[off:off + 2 * n], dtype='<f2').astype(np.float32)
    if ty == 8:                                  # Q8_0（32 值/34 字节）向量化
        nb = n // 32
        blk = np.frombuffer(b[off:off + nb * 34], dtype=np.uint8).reshape(nb, 34)
        d = blk[:, :2].copy().view('<f2').astype(np.float32).reshape(nb, 1)
        q = blk[:, 2:34].copy().view(np.int8).astype(np.float32)
        return (d * q).reshape(-1)
    if ty == 6:                                  # Q5_0（32 值/22 字节）向量化
        nb = n // 32
        blk = np.frombuffer(b[off:off + nb * 22], dtype=np.uint8).reshape(nb, 22)
        d = blk[:, :2].copy().view('<f2').astype(np.float32).reshape(nb)
        qh = blk[:, 2:6].copy().view('<u4').reshape(nb)
        qs = blk[:, 6:22]
        bits = ((qh[:, None] >> np.arange(16)[None, :]) & 1).astype(np.uint8)
        bits2 = ((qh[:, None] >> (np.arange(16)[None, :] + 16)) & 1).astype(np.uint8)
        lo = ((qs & 0x0f) | (bits << 4)).astype(np.float32) - 16
        hi = ((qs >> 4) | (bits2 << 4)).astype(np.float32) - 16
        out = np.empty((nb, 32), np.float32)
        out[:, :16] = lo * d[:, None]
        out[:, 16:] = hi * d[:, None]
        return out.reshape(-1)
    if ty == 14:                                 # Q6_K（256 值/210 字节）——照 llama.cpp
        nb = n // 256
        blk = np.frombuffer(b[off:off + nb * 210], dtype=np.uint8).reshape(nb, 210)
        ql = blk[:, 0:128]
        qh = blk[:, 128:192]
        sc = blk[:, 192:208].copy().view(np.int8).astype(np.float32)   # (nb,16)
        d = blk[:, 208:210].copy().view('<f2').astype(np.float32).reshape(nb)
        out = np.empty((nb, 256), np.float32)
        for g in range(2):                       # 两个 128 组：ql+64 qh+32 sc+8
            for l in range(32):
                isb = l // 16
                qhb = qh[:, g * 32 + l].astype(np.int32)
                q1 = ((ql[:, g*64 + l].astype(np.int32) & 0x0F) | (((qhb >> 0) & 3) << 4)) - 32
                q2 = ((ql[:, g*64 + l + 32].astype(np.int32) & 0x0F) | (((qhb >> 2) & 3) << 4)) - 32
                q3 = ((ql[:, g*64 + l].astype(np.int32) >> 4) | (((qhb >> 4) & 3) << 4)) - 32
                q4 = ((ql[:, g*64 + l + 32].astype(np.int32) >> 4) | (((qhb >> 6) & 3) << 4)) - 32
                s1 = sc[:, g*8 + isb + 0] * d
                s2 = sc[:, g*8 + isb + 2] * d
                s3 = sc[:, g*8 + isb + 4] * d
                s4 = sc[:, g*8 + isb + 6] * d
                base = g * 128
                out[:, base + l +  0] = s1 * q1
                out[:, base + l + 32] = s2 * q2
                out[:, base + l + 64] = s3 * q3
                out[:, base + l + 96] = s4 * q4
        return out.reshape(-1)[:n]
    if ty == 12:                                 # Q4_K（256 值/144 字节）向量化
        nb = n // 256
        blk = np.frombuffer(b[off:off + nb * 144], dtype=np.uint8).reshape(nb, 144)
        d = blk[:, 0:2].copy().view('<f2').astype(np.float32).reshape(nb)
        dmin = blk[:, 2:4].copy().view('<f2').astype(np.float32).reshape(nb)
        sc = blk[:, 4:16]
        qs = blk[:, 16:144]
        out = np.empty((nb, 256), np.float32)

        def gsm(j):
            if j < 4:
                return (sc[:, j] & 63).astype(np.float32), (sc[:, j + 4] & 63).astype(np.float32)
            return (((sc[:, j + 4] & 0x0f) | ((sc[:, j - 4] >> 6) << 4)).astype(np.float32),
                    ((sc[:, j + 4] >> 4) | ((sc[:, j] >> 6) << 4)).astype(np.float32))
        for g in range(4):
            s0, m0 = gsm(g * 2); s1, m1 = gsm(g * 2 + 1)
            q = qs[:, g * 32:(g + 1) * 32]
            out[:, g * 64: g * 64 + 32] = (d * s0)[:, None] * (q & 0x0f) - (dmin * m0)[:, None]
            out[:, g * 64 + 32: g * 64 + 64] = (d * s1)[:, None] * (q >> 4) - (dmin * m1)[:, None]
        return out.reshape(-1)
    raise SystemExit("  未实现类型 %s" % ty)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="/tmp/tiny.gguf")
    ap.add_argument("--token", type=int, default=504)
    ap.add_argument("--tokens", default="", help="逗号分隔的 token id 序列")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--track", default="Paris,ĠParis, Paris")
    ap.add_argument("--noattn", action="store_true", help="消融：把注意力上下文清零")
    ap.add_argument("--normone", action="store_true", help="对照：norm 权重强制为 1")
    a = ap.parse_args()
    kv, tens, data, blob = parse(a.model)
    arch = kv.get("general.architecture", "llama")
    nL = kv[arch + ".block_count"]; nE = kv[arch + ".embedding_length"]
    nH = kv[arch + ".attention.head_count"]; nKV = kv[arch + ".attention.head_count_kv"]
    nFF = kv[arch + ".feed_forward_length"]
    eps = kv.get(arch + ".attention.layer_norm_rms_epsilon", 1e-5)
    theta = kv.get(arch + ".rope.freq_base", 10000.0)
    hd = nE // nH
    cache = {}

    def T(name):
        if name in cache:
            return cache[name]
        dims, ty, off = tens[name]
        n = 1
        for d in dims:
            n *= d
        arr = deq(blob, data + off, ty, n)
        cache[name] = arr
        return arr

    def rms(x, w):
        if a.normone:
            w = np.ones_like(w)
        return (x / np.sqrt((x * x).mean() + eps)) * w

    def matvec(W, x, nin, nout):
        return (W.reshape(nout, nin) @ x).astype(np.float32)

    def rope1(x, nh, pos=0):
        x = x.reshape(nh, hd).copy()
        half = hd // 2
        i = np.arange(half)
        inv = theta ** (-2 * i / hd)
        ang = pos * inv
        c, s = np.cos(ang), np.sin(ang)
        a_ = x[:, :half].copy(); b_ = x[:, half:].copy()
        x[:, :half] = a_ * c - b_ * s
        x[:, half:] = a_ * s + b_ * c
        return x.reshape(-1)

    if a.tokens:
        ids = [int(t) for t in a.tokens.split(",") if t.strip()]
    else:
        ids = [a.token]
    print("  序列:", ids)

    # KV cache：每层两份 [pos][nKV*hd]
    kc = [np.zeros((len(ids), nKV * hd), np.float32) for _ in range(nL)]
    vc = [np.zeros((len(ids), nKV * hd), np.float32) for _ in range(nL)]
    x = None
    for pos, tid in enumerate(ids):
        x = T("token_embd.weight")[tid * nE:(tid + 1) * nE].copy()
        for l in range(nL):
            pre = "blk.%d." % l
            h = rms(x, T(pre + "attn_norm.weight"))
            q = rope1(matvec(T(pre + "attn_q.weight"), h, nE, nE), nH, pos)
            k = rope1(matvec(T(pre + "attn_k.weight"), h, nE, nKV * hd), nKV, pos)
            v = matvec(T(pre + "attn_v.weight"), h, nE, nKV * hd)
            kc[l][pos] = k
            vc[l][pos] = v
            ctx = np.empty(nE, np.float32)
            scale = 1.0 / np.sqrt(hd)
            for hh in range(nH):
                kvh = int(hh * nKV / nH)
                qh_ = q[hh * hd:(hh + 1) * hd]
                ks = kc[l][:pos + 1, kvh * hd:(kvh + 1) * hd]      # (pos+1, hd)
                sc = (ks @ qh_) * scale
                sc = sc - sc.max()
                p_ = np.exp(sc); p_ /= p_.sum()
                ctx[hh * hd:(hh + 1) * hd] = p_ @ vc[l][:pos + 1, kvh * hd:(kvh + 1) * hd]
            if a.noattn:
                ctx = np.zeros(nE, np.float32)
            ao = matvec(T(pre + "attn_output.weight"), ctx, nE, nE)
            x = x + ao
            h2 = rms(x, T(pre + "ffn_norm.weight"))
            g = matvec(T(pre + "ffn_gate.weight"), h2, nE, nFF)
            u = matvec(T(pre + "ffn_up.weight"), h2, nE, nFF)
            act = (g / (1 + np.exp(-g))) * u
            dn = matvec(T(pre + "ffn_down.weight"), act, nFF, nE)
            x = x + dn
        if pos < 4:
            print("  pos %d tok %-6d |x|=%.5f" % (pos, tid, np.abs(x).mean()))

    xf = rms(x, T("output_norm.weight"))
    logits = (T("token_embd.weight").reshape(-1, nE) @ xf).astype(np.float32)
    top = np.argsort(-logits)[:a.top]
    toks = kv["tokenizer.ggml.tokens"]
    for want in [w for w in a.track.split(",") if w]:
        if want in toks:
            wi = toks.index(want)
            rank = int((logits > logits[wi]).sum()) + 1
            print("  追踪 %-10r id=%-6d logit=%.4f rank=%d" % (want, wi, logits[wi], rank))
    print("  末位 top-%d:" % a.top)
    for i2 in top:
        t = str(toks[i2]).replace("Ġ", " ").replace("Ċ", "\\n")
        print("    %-14r %.4f" % (t[:14], float(logits[i2])))
    return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
