# -*- coding: utf-8 -*-
"""GBT 自有权重 · **按需激活**本机推理（不装 CUDA、不装 bitsandbytes、不联网）。

## 主人令（2026-10-24，逐字）
「**量化权重按需激活使用** … 我的电脑足够了」

## 为什么自己写（不是重复造轮子）
本机现读：AMD R7-5800H（**无 AVX512**）· 内存 7.4 GB · 显卡 RX 6500M 4 GB。
bitsandbytes 的 4bit 内核要求 **Intel + AVX512** ⇒ 本机用不了（实测报 CPU 不支持）。
但我们的权重本来就是**按层分片**的（`state/weights/*-stream/`：31 个分片，单层 125 MB，
`stream_manifest.json` 逐片列出张量清单）—— 这正是「按需激活」的物理基础：
**一次只把一层从盘上解到内存，算完就丢**，峰值内存由「一层」决定，不由「整个模型」决定。

## 量化格式（现读 safetensors 头部确认，不是猜的）
· 每层每个线性层：`weight`(U8, 打包 nf4 双 nibble) + `weight.absmax`(F32, 每 64 元素一块)
  + `weight.quant_map`(F32[16], 码本) + `weight.quant_state.bitsandbytes__nf4`(U8[~82], 元信息)
  ⇒ **bitsandbytes nf4**：块 64，元素 = code[nibble] × absmax[block]
· `embed_tokens` / `lm_head`：I8 + 每行一个 F16 缩放（`weight.q` / `weight.s`）
· `model.norm`：F16

## 用法
    py -3 tools/codex-scripts/gbt-local-infer.py --spike          # 量：解一层要多久
    py -3 tools/codex-scripts/gbt-local-infer.py --prompt "你好" --max-new 8
    py -3 tools/codex-scripts/gbt-local-infer.py --serve 8077     # OpenAI 兼容口（桥的 selfhost 车道）

## 判据（不看感觉）
· `--spike` 打印 dequant 吞吐 MB/s 与单层耗时
· 生成时打印 **首字时延** 与 **tok/s**；这两个数是唯一该信的速度口径
"""
from __future__ import annotations

import argparse
import json
import math
import os
import struct
import sys
import time

import numpy as np
import torch

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_DIR = os.path.join(ROOT, "state", "weights", "gbt-v8-v82-stream")

# bnb nf4 的 16 值码本（取自 bitsandbytes 官方实现；分片里也存了 quant_map，二者应一致）
NF4_CODEBOOK = np.array([
    -1.0, -0.6961928009986877, -0.5250730514526367, -0.39491748809814453,
    -0.28444138169288635, -0.18477343022823334, -0.09105003625154495, 0.0,
    0.07958029955625534, 0.16093020141124725, 0.24611230194568634, 0.33791524171829224,
    0.44070982933044434, 0.5626170039176941, 0.7229568362236023, 1.0,
], dtype=np.float32)

DT = {"F32": ("<f4", 4), "F16": ("<f2", 2), "I8": ("i1", 1), "U8": ("u1", 1),
      "I32": ("<i4", 4), "I64": ("<i8", 8), "BF16": ("<u2", 2)}


class Shard:
    """单个 safetensors 分片：只读需要的张量字节，不整文件读入。"""

    def __init__(self, path: str):
        self.path = path
        with open(path, "rb") as fh:
            n = struct.unpack("<Q", fh.read(8))[0]
            self.header = json.loads(fh.read(n).decode("utf-8"))
            self.data_start = 8 + n
        self.fh = open(path, "rb")
        self.header.pop("__metadata__", None)

    def names(self):
        return list(self.header)

    def has(self, name: str) -> bool:
        return name in self.header

    def get(self, name: str) -> np.ndarray:
        h = self.header[name]
        a, b = h["data_offsets"]
        dtype, itemsize = DT[h["dtype"]]
        shape = h["shape"]
        n_items = int(np.prod(shape)) if shape and shape != [1] else 1
        self.fh.seek(self.data_start + a)
        buf = self.fh.read(b - a)
        arr = np.frombuffer(buf, dtype=dtype).copy() if itemsize > 1 else np.frombuffer(buf, dtype=dtype).copy()
        return arr.reshape(shape) if len(shape) > 1 else arr

    def get_mmap(self, name: str) -> np.ndarray:
        """只读映射，不占 Python 堆。

        🔴 2026-10-24 实测：7.4 GB 机器上 commit 只剩 1.2 GB 时，
        get() 里 "read 520 MB + copy 520 MB" 会直接 MemoryError。
        文件映射走页缓存，可回收，不会失败。导出脚本用它读 embed / lm_head。
        """
        h = self.header[name]
        a, b = h["data_offsets"]
        dtype, itemsize = DT[h["dtype"]]
        shape = tuple(h["shape"])
        return np.memmap(self.path, dtype=dtype, mode="r",
                         offset=self.data_start + a, shape=shape)

    def close(self):
        self.fh.close()


_LUT_CACHE: dict[bytes, np.ndarray] = {}


def _lut(code: np.ndarray) -> np.ndarray:
    """256 → 2 值查找表：**一个字节一次索引**，顺带把低位/高位交错成 [256,2]。

    这是「按需激活」能不能跑得动的关键：原版按 nibble 两次 gather + 交错赋值，
    实测只有 35–45 MB/s；换成一字节一次查表后，解量化不再是瓶颈。
    """
    key = code.astype(np.float32).tobytes()
    hit = _LUT_CACHE.get(key)
    if hit is not None:
        return hit
    c = code.astype(np.float32)
    tab = np.empty((256, 2), dtype=np.float32)
    for b in range(256):
 # 2026-10-24 01:33 实测校正（拿 bitsandbytes 官方 dequantize_4bit 当对照）：
        #   原来按「低位=偶数位」写，对照结果**正好成对颠倒**（max 差 0.62、一致率 7.3%）。
        #   官方是 **高 nibble = 偶数位元素、低 nibble = 奇数位元素**。改成这样就逐元素对齐。
        tab[b, 0] = c[(b >> 4) & 0x0F]   # 高 nibble = 偶数位元素
        tab[b, 1] = c[b & 0x0F]          # 低 nibble = 奇数位元素
    _LUT_CACHE[key] = tab
    return tab


def dequant_nf4(packed: np.ndarray, absmax: np.ndarray, code: np.ndarray, shape, block=64) -> np.ndarray:
    """bnb nf4 → fp16（LUT 版）。低 nibble 是偶数元素，高 nibble 是奇数元素（与 bnb 一致）。"""
    n = int(np.prod(shape))
    u = packed.reshape(-1).view(np.uint8)
    if u.size * 2 < n:
        raise ValueError("打包字节数不够: %d*2 < %d" % (u.size, n))
    tab = _lut(code)
    vals = tab[u].reshape(-1)[:n]                            # 一次查表得到交错值
    nb = math.ceil(n / block)
    am = absmax.reshape(-1).astype(np.float32)[:nb]
    out = vals.reshape(nb, block) * am[:, None]              # 每 64 元素一块，整块乘 absmax
    return out.astype(np.float16).reshape(shape)


class Model:
    def __init__(self, model_dir: str = MODEL_DIR, verbose: bool = True, fp16_dir: str | None = None):
        self.fp16_dir = fp16_dir
        self._npz_i = -1
        self._npz = None
        self.dir = model_dir
        self.cfg = json.load(open(os.path.join(model_dir, "config.json"), encoding="utf-8"))
        man = json.load(open(os.path.join(model_dir, "stream_manifest.json"), encoding="utf-8"))["groups"]
        self.groups = {k: v["file"] for k, v in man.items()}
        self.hidden = self.cfg["hidden_size"]
        self.n_layers = self.cfg["num_hidden_layers"]
        self.n_heads = self.cfg["num_attention_heads"]
        self.n_kv = self.cfg["num_key_value_heads"]
        self.head_dim = self.hidden // self.n_heads
        self.eps = float(self.cfg.get("rms_norm_eps") or 1e-6)
        self.rope_theta = float(self.cfg.get("rope_theta") or 1e6)
        self.verbose = verbose
        if verbose:
            print("[gbt] %s · %d 层 · hidden %d · heads %d/%d · nf4 按需激活"
                  % (self.cfg["model_type"], self.n_layers, self.hidden, self.n_heads, self.n_kv), flush=True)
        self._shards: dict[str, Shard] = {}
        # 常驻：norm + lm_head（小）
        self.norm_w = self._small("norm", "model.norm.weight").astype(np.float32)

    # ---------- 读取 ----------
    def _shard(self, group: str) -> Shard:
        if group not in self._shards:
            self._shards[group] = Shard(os.path.join(self.dir, self.groups[group]))
        return self._shards[group]

    def _small(self, group: str, name: str) -> np.ndarray:
        return self._shard(group).get(name)

    def _layer_npz(self, i: int):
        """按需激活的第二形态：一层一个 .npz（fp16），读到就留一层，用完即弃。"""
        if self._npz_i != i:
            self._npz = np.load(os.path.join(self.fp16_dir, "layer_%02d.npz" % i))
            self._npz_i = i
        return self._npz

    def layer_weight(self, i: int, proj: str) -> torch.Tensor:
        """按需激活：现场读分片 → nf4 解量化 → fp16。算完由调用方丢弃。"""
        if self.fp16_dir:
            return torch.from_numpy(self._layer_npz(i)[proj])
        g = "layer_%02d" % i
        sh = self._shard(g)
        base = "model.layers.%d.%s" % (i, proj)
        packed = sh.get(base + ".weight")
        absmax = sh.get(base + ".weight.absmax")
        code = sh.get(base + ".weight.quant_map").astype(np.float32)
        st = sh.get(base + ".weight.quant_state.bitsandbytes__nf4")
        try:
            qs = json.loads(st.tobytes().decode("utf-8", "ignore").rstrip("\x00"))
            shape = tuple(qs.get("shape") or [])
        except Exception:                                     # noqa: BLE001
            shape = ()
        if len(shape) != 2:
            out_f = absmax.size * 64 // self.hidden
            shape = (self.hidden, self.hidden) if "attn" in proj else (int(out_f), self.hidden)
        w = dequant_nf4(packed, absmax, code, shape)
        return torch.from_numpy(w)

    def layer_small(self, i: int, name: str) -> torch.Tensor:
        if self.fp16_dir:
            return torch.from_numpy(self._layer_npz(i)[name].astype(np.float32))
        arr = self._shard("layer_%02d" % i).get("model.layers.%d.%s" % (i, name))
        return torch.from_numpy(arr.astype(np.float32))

    def embed_rows(self, ids: list[int]) -> torch.Tensor:
        sh = self._shard("embed")
        q = sh.get("model.embed_tokens.weight.q")             # I8 [V, H]
        s = sh.get("model.embed_tokens.weight.s")             # F16 [V, 1]
        rows = torch.from_numpy(q[ids].astype(np.float32))
        sc = torch.from_numpy(s[ids].reshape(-1, 1).astype(np.float32))
        return rows * sc

    def lm_head_logits(self, x: torch.Tensor) -> torch.Tensor:
        sh = self._shard("lm_head")
        name = "lm_head.weight.q" if sh.has("lm_head.weight.q") else "model.lm_head.weight.q"
        q = sh.get(name)
        sname = name.replace(".q", ".s")
        s = sh.get(sname)
        # 按 4096 行一批算，避免一次 152064×3584 全解（省内存）
        out = []
        step = 8192
        for i in range(0, q.shape[0], step):
            wq = torch.from_numpy(q[i:i + step].astype(np.float32))
            ws = torch.from_numpy(s[i:i + step].reshape(-1, 1).astype(np.float32))
            out.append((wq @ x) * ws.reshape(-1))
        return torch.cat(out)

    # ---------- 前向 ----------
    @staticmethod
    def _rms(x: torch.Tensor, w: torch.Tensor, eps: float) -> torch.Tensor:
        v = x.pow(2).mean(-1, keepdim=True)
        return x / torch.sqrt(v + eps) * w

    def _rope(self, t: torch.Tensor, pos0: int) -> torch.Tensor:
        """t: [heads, seq, head_dim]"""
        seq = t.shape[1]
        half = self.head_dim // 2
        inv = 1.0 / (self.rope_theta ** (torch.arange(0, half, dtype=torch.float32) * 2.0 / self.head_dim))
        pos = torch.arange(pos0, pos0 + seq, dtype=torch.float32)
        freqs = torch.outer(pos, inv)                          # [seq, half]
        cos = torch.cos(freqs).unsqueeze(0)                    # [1, seq, half]
        sin = torch.sin(freqs).unsqueeze(0)
        x1, x2 = t[..., :half], t[..., half:]
        return torch.cat([x1 * cos - x2 * sin, x1 * sin + x2 * cos], dim=-1)

    def forward_step(self, ids: list[int], kv: list, pos0: int, logits_for_last: bool = True):
        """跑一次前向：prefill 时 ids 可多，decode 时 1 个。返回 (logits 或 None, 更新后的 kv)。"""
        x = self.embed_rows(ids)                              # [S, H]
        seq = x.shape[0]
        for li in range(self.n_layers):
            ln1 = self.layer_small(li, "input_layernorm.weight")
            h = self._rms(x, ln1, self.eps)                   # [S, H]

            # 逐个线性层：取 → 算 → 丢（按需激活的核心）
            def lin(proj: str, inp: torch.Tensor) -> torch.Tensor:
                w = self.layer_weight(li, proj).to(torch.float32)
                out = inp @ w.T
                del w
                return out

            q = lin("self_attn.q_proj", h) + self.layer_small(li, "self_attn.q_proj.bias")
            k = lin("self_attn.k_proj", h) + self.layer_small(li, "self_attn.k_proj.bias")
            v = lin("self_attn.v_proj", h) + self.layer_small(li, "self_attn.v_proj.bias")

            q = q.view(seq, self.n_heads, self.head_dim).transpose(0, 1)
            k = k.view(seq, self.n_kv, self.head_dim).transpose(0, 1)
            v = v.view(seq, self.n_kv, self.head_dim).transpose(0, 1)
            q = self._rope(q, pos0)
            k = self._rope(k, pos0)

            kc, vc = kv[li]
            kc = torch.cat([kc, k], dim=1) if kc is not None else k
            vc = torch.cat([vc, v], dim=1) if vc is not None else v
            kv[li] = (kc, vc)

            rep = self.n_heads // self.n_kv
            kx = kc.repeat_interleave(rep, dim=0)
            vx = vc.repeat_interleave(rep, dim=0)

            # 逐头注意力：[heads, S, hd] @ [heads, hd, T] → [heads, S, T]
            att = (q @ kx.transpose(1, 2)) / math.sqrt(self.head_dim)
            if seq > 1:                                    # prefill 必须带因果掩码（否则是双向注意力）
                T = att.shape[-1]
                causal = torch.ones(seq, T, dtype=torch.bool).tril(diagonal=pos0)
                att = att.masked_fill(~causal.unsqueeze(0), float("-inf"))
            att = torch.softmax(att, dim=-1)
            o = (att @ vx).transpose(0, 1).reshape(seq, self.hidden)
            x = x + lin("self_attn.o_proj", o)

            ln2 = self.layer_small(li, "post_attention_layernorm.weight")
            h2 = self._rms(x, ln2, self.eps)
            g = lin("mlp.gate_proj", h2)
            u = lin("mlp.up_proj", h2)
            act = torch.nn.functional.silu(g) * u
            x = x + lin("mlp.down_proj", act)
            if self.verbose and seq > 1:
                print("   层 %2d/%d 完成" % (li + 1, self.n_layers), flush=True)

        if not logits_for_last:
            return None, kv
        xn = self._rms(x[-1:], torch.from_numpy(self.norm_w), self.eps)
        return self.lm_head_logits(xn[0]), kv


EXPORT_DIR = os.path.join(ROOT, "state", "weights", "_fp16mmap")


def export_fp16(model_dir: str = MODEL_DIR) -> int:
    """把所有层一次性解成 fp16 落盘（每层一个 .npy），之后推理只做**顺序读**。

    为什么这样做（读数驱动）：nv4 解量化实测 173 MB/s，一层 125 MB ⇒ 0.7 s，
    28 层光解量化就 20 s/token；落成 fp16 后每 token 只剩「读 7.5 GB + 矩阵乘」，
    读盘是顺序的（SSD 1–2 GB/s），比边读边解快一个数量级。
    """
    m = Model(model_dir)
    os.makedirs(EXPORT_DIR, exist_ok=True)
    t_all = time.perf_counter()
    projs = ["self_attn.q_proj", "self_attn.k_proj", "self_attn.v_proj", "self_attn.o_proj",
             "mlp.gate_proj", "mlp.up_proj", "mlp.down_proj"]
    for li in range(m.n_layers):
        out = os.path.join(EXPORT_DIR, "layer_%02d.npz" % li)
        if os.path.exists(out):
            print("层 %02d 已存在，跳过" % li, flush=True)
            continue
        t0 = time.perf_counter()
        arrays = {}
        for pr in projs:
            arrays[pr] = m.layer_weight(li, pr).numpy()          # fp16
        for nm in ("input_layernorm.weight", "post_attention_layernorm.weight",
                   "self_attn.q_proj.bias", "self_attn.k_proj.bias", "self_attn.v_proj.bias"):
            arrays[nm] = m.layer_small(li, nm).numpy().astype("float16")
        np.savez(out, **arrays)
        mb = os.path.getsize(out) / 1024 / 1024
        print("层 %02d 导出 %.0f MB · %.1fs" % (li, mb, time.perf_counter() - t0), flush=True)
    print("全部完成 %.1fs · 目录 %s" % (time.perf_counter() - t_all, EXPORT_DIR), flush=True)
    return 0


def spike(model_dir=MODEL_DIR):
    m = Model(model_dir)
    print("\n=== 量：解一层（nf4 → fp16）要多久 ===", flush=True)
    for i in (0, 14):
        t0 = time.perf_counter()
        w = m.layer_weight(i, "self_attn.q_proj")
        dt = time.perf_counter() - t0
        mb = w.numel() * 2 / 1024 / 1024
        print("layer %02d q_proj: %dx%d · %.1f MB · %.2fs · %.0f MB/s"
              % (i, w.shape[0], w.shape[1], mb, dt, mb / max(dt, 1e-6)), flush=True)
    t0 = time.perf_counter()
    x = torch.randn(1, m.hidden)
    w = m.layer_weight(0, "self_attn.q_proj").to(torch.float32)
    y = x @ w.T
    print("一层 q_proj 前向: %.2fs · 输出范数 %.3f" % (time.perf_counter() - t0, float(y.norm())), flush=True)
    print("\n峰值内存占用（torch）: %.0f MB" % (torch.cuda.max_memory_allocated() if torch.cuda.is_available() else 0))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", default=MODEL_DIR)
    ap.add_argument("--spike", action="store_true")
    ap.add_argument("--export-fp16", action="store_true")
    ap.add_argument("--fp16", action="store_true", help="用已落盘的 fp16 层（快路径）")
    ap.add_argument("--prompt", default="只回三个字：我到了")
    ap.add_argument("--max-new", type=int, default=8)
    ap.add_argument("--serve", type=int, default=0, help="起 OpenAI 兼容口（端口）")
    a = ap.parse_args()

    if a.export_fp16:
        return export_fp16(a.model_dir)
    if a.spike:
        spike(a.model_dir)
        return 0

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(a.model_dir, trust_remote_code=True)
    m = Model(a.model_dir, fp16_dir=EXPORT_DIR if a.fp16 else None)

    text = tok.apply_chat_template([{"role": "user", "content": a.prompt}],
                                   tokenize=False, add_generation_prompt=True)
    ids = tok(text)["input_ids"]

    kv = [(None, None) for _ in range(m.n_layers)]
    t0 = time.perf_counter()
    logits, kv = m.forward_step(ids, kv, 0)
    first = time.perf_counter() - t0
    out = [int(torch.argmax(logits))]
    t1 = time.perf_counter()
    for _ in range(a.max_new - 1):
        logits, kv = m.forward_step([out[-1]], kv, len(ids) + len(out) - 1)
        out.append(int(torch.argmax(logits)))
        if out[-1] == tok.eos_token_id:
            break
    dt = time.perf_counter() - t1
    ans = tok.decode(out, skip_special_tokens=True)
    n = max(len(out) - 1, 1)
    print("\n=== 读数 ===")
    print("prompt tokens: %d" % len(ids))
    print("首字时延: %.1fs（含全部 %d 层按需激活）" % (first, m.n_layers))
    print("后续 %d token: %.1fs · **%.2f tok/s**" % (n, dt, n / max(dt, 1e-6)))
    print("回答: %r" % ans)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
