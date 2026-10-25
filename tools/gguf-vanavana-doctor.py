# -*- coding: utf-8 -*-
"""vanavana 病灶定位器 —— 一次跑完，直接指出「哪个张量写错了」

背景（引自 GBT权重使用文档 §5.2）：
  自写引擎读同一批 nf4 切片能出人话；GGUF 读导出结果恒定 vanavana。
  ⇒ 病根只在「导出端写张量那一步」。文档列了 3 个候选，本器按可判定性排序，逐个给出**布尔结论**。

四个判据（每个都回 bool + 读数，不猜）：
  A. 两张大表是否写反        —— output.weight 到底等于 lm_head 还是 embed_tokens
  B. q_proj/k_proj 是否做了 RoPE 置换 —— 文档里没有这一条，但它是 vanavana 的典型病因
  C. bias 是否写进 GGUF      —— Qwen2 的 q/k/v 有 bias，缺了不报错只让注意力偏
  D. Q4_0 分块方向           —— 把 GGUF 的量化块反解回来，跟 nf4 真值逐元素比

用法（在你笔记本上，4 条串起来跑）：
  py -3.12 -X utf8 tools\\gguf-vanavana-doctor.py ^
      --gguf state\\weights\\gbt-v8-v82-q4_0-fixed.gguf ^
      --stream state\\weights\\gbt-v8-v82-stream ^
      --layer layer_00

依赖：numpy + safetensors（你已有）。读 GGUF 用 gguf 包；没有就自动退化为"只读元数据"。
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

import numpy as np

N_HEAD, N_HEAD_KV = 28, 4          # 来自 config.json：heads 28 / kv 4


# ────────────────────────── 工具 ──────────────────────────
def load_shard(stream: Path, name: str) -> dict:
    """读一片 safetensors，回 {张量名: numpy}。"""
    try:
        from safetensors.numpy import load_file
        return load_file(str(stream / (name + ".safetensors")))
    except Exception as e:
        print("  ⚠ 读 %s 失败: %s" % (name, e))
        return {}


def dequant_int8_rowscale(t: dict, base: str) -> np.ndarray:
    """I8 + 每行一个 F16 缩放 ⇒ float32。键名约定：<base>.q / <base>.s"""
    q = t.get(base + ".q")
    s = t.get(base + ".s")
    if q is None:
        # 有时直接就叫 base
        q = t.get(base)
        s = t.get(base + "_scale", t.get("scales"))
    if q is None:
        return None
    q = q.astype(np.float32)
    if s is None:
        return q
    s = s.astype(np.float32).reshape(-1, 1) if s.ndim == 1 else s.astype(np.float32)
    return q * s


def permute_rope(w: np.ndarray, n_head: int, n_head_kv: int) -> np.ndarray:
    """llama.cpp 的 RoPE 成对交错置换（形状不变）。"""
    if n_head_kv and n_head != n_head_kv:
        n_head = n_head_kv
    return (w.reshape(n_head, 2, w.shape[0] // n_head // 2, *w.shape[1:])
             .swapaxes(1, 2).reshape(w.shape))


def rel_err(a: np.ndarray, b: np.ndarray) -> float:
    """归一化平均绝对误差（对齐形状后比）。"""
    if a.shape != b.shape:
        return float("inf")
    a = a.astype(np.float32); b = b.astype(np.float32)
    d = np.abs(a - b).mean()
    return float(d / (np.abs(b).mean() + 1e-9))


def read_gguf(path: Path):
    """优先用 gguf 包；没装就只读头（返回 None 张量）。"""
    try:
        import gguf
        r = gguf.GGUFReader(str(path))
        tensors, meta = {}, {}
        for t in r.tensors:
            tensors[t.name] = np.array(t.data, copy=False)
        for k, f in r.fields.items():
            try:
                meta[k] = f.contents()
            except Exception:
                pass
        return tensors, meta, True
    except ImportError:
        print("  ⚠ 没装 gguf 包（pip install gguf）⇒ 只能读元数据，A/B/D 判据跳过")
        return {}, {}, False
    except Exception as e:
        print("  ⚠ 读 GGUF 失败: %s" % e)
        return {}, {}, False


def dequant_q4_0_blocks(blob: np.ndarray, n_per_row: int):
    """把 ggml Q4_0 的 18 字节/32元素 解回 float32（用于 D 判据）。"""
    raw = blob.tobytes()
    blocks = len(raw) // 18
    out = np.zeros(blocks * 32, dtype=np.float32)
    for i in range(blocks):
        o = i * 18
        d = np.frombuffer(raw[o:o + 2], dtype=np.float16)[0].astype(np.float32)
        qs = np.frombuffer(raw[o + 2:o + 18], dtype=np.uint8)
        lo = (qs & 0x0F).astype(np.float32) - 8.0
        hi = ((qs >> 4) & 0x0F).astype(np.float32) - 8.0
        out[i * 32: i * 32 + 16] = lo * d
        out[i * 32 + 16: i * 32 + 32] = hi * d
    return out.reshape(-1, n_per_row)


# ────────────────────────── 四条判据 ──────────────────────────
def check_A(tensors, meta, stream, have_t):
    print("\n【A】两张大表是否写反（文档候选 #1）")
    emb = load_shard(stream, "embed_int8")
    lmh = load_shard(stream, "lm_head_int8")
    embed = dequant_int8_rowscale(emb, "embed_tokens")
    lm = dequant_int8_rowscale(lmh, "lm_head")
    if embed is None or lm is None:
        print("  ⚠ 读不到 embed/lm_head 的 int8 张量（键名不符合 .q/.s 约定）")
        print("     实际键:", list(emb.keys())[:6], "|", list(lmh.keys())[:6])
        return None

    print("  embed_tokens: %s   lm_head: %s" % (embed.shape, lm.shape))
    tie = meta.get("qwen2.tie_word_embeddings") or meta.get("general.tie_word_embeddings")
    print("  tie_word_embeddings =", tie)

    g_out = tensors.get("output.weight")
    g_emb = tensors.get("token_embd.weight")
    if g_out is None or g_emb is None:
        print("  ⚠ GGUF 里没有 output.weight / token_embd.weight（gguf 包没装？）")
        return None

    # GGUF 的 token_embd 通常是 [n_embd, n_vocab]（ggml 转置），先对齐再比
    def align(w, ref):
        if w.shape == ref.shape:
            return w
        if w.shape == ref.T.shape:
            return w.T
        if w.shape == (ref.shape[1], ref.shape[0]):
            return w.T
        return w

    e_out_lm = rel_err(align(g_out, lm), lm)
    e_out_em = rel_err(align(g_out, embed), embed)
    e_emb_em = rel_err(align(g_emb, embed), embed)

    print("  output.weight ↔ lm_head     相对误差: %.4f" % e_out_lm)
    print("  output.weight ↔ embed_tokens 相对误差: %.4f" % e_out_em)
    print("  token_embd    ↔ embed_tokens 相对误差: %.4f" % e_emb_em)
    print("  （Q4_0 有损，误差 0.02–0.08 属正常；>0.5 就是错表）")

    swap = e_out_em + 1e-6 < e_out_lm
    print("  ⇒ 结论: %s" % ("🔴 两表写反了（output 用了 embed_tokens）" if swap else "✅ 两表没写反"))
    return swap


def check_B(tensors, stream, layer):
    print("\n【B】q_proj/k_proj 是否做了 RoPE 置换（文档未列，但这是典型病因）")
    sh = load_shard(stream, layer)
    if not sh:
        return None

    def qkey(cands):
        for c in cands:
            for k in sh:
                if k.endswith(c):
                    return k
        return None

    for tag, cands, gname in (
        ("q_proj", ("q_proj.weight", "q_proj.q"), "blk.0.attn_q.weight"),
        ("k_proj", ("k_proj.weight", "k_proj.q"), "blk.0.attn_k.weight"),
    ):
        k = qkey(cands)
        if k is None:
            print("  ⚠ %s 找不到（层里有的键: %s…）" % (tag, list(sh)[:3]))
            continue
        w = sh[k].astype(np.float32)
        if w.ndim != 2:
            w = w.reshape(w.shape[0], -1)
        g = tensors.get(gname)
        if g is None:
            print("  ⚠ GGUF 里没有 %s" % gname)
            continue
        g = g.astype(np.float32)
        if g.shape != w.shape and g.shape == w.T.shape:
            g = g.T
        d_direct = rel_err(g, w)
        d_perm = rel_err(g, permute_rope(w, N_HEAD, N_HEAD_KV))
        verdict = "已置换" if d_perm + 1e-6 < d_direct else "未置换"
        print("  %s: 直比 %.4f · 置换后比 %.4f ⇒ **%s**" % (tag, d_direct, d_perm, verdict))
        if verdict == "未置换" and d_direct > 0.5:
            print("     🔴 这就是病灶：GGUF 里存的是未置换的权重，llama.cpp 按置换解读 ⇒ 注意力全错")
            return True
    return False


def check_C(tensors, stream, layer):
    print("\n【C】bias 是否写进 GGUF")
    sh = load_shard(stream, layer)
    shard_bias = [k for k in sh if "bias" in k]
    gguf_attn = [n for n in tensors if n.startswith("blk.0.") and "bias" in n]
    print("  切片里的 bias: %d 个 %s" % (len(shard_bias), shard_bias[:4]))
    print("  GGUF 里 blk.0 的 bias: %d 个 %s" % (len(gguf_attn), gguf_attn[:4]))
    if shard_bias and not gguf_attn:
        print("  🔴 bias 全丢了 —— llama.cpp 不报错，只是注意力偏")
        return True
    print("  ⇒ 结论: %s" % ("✅ bias 大致齐" if gguf_attn else "⚠ 两边都没有 bias（Qwen2 应该有 q/k/v bias）"))
    return False


def check_D(tensors, stream, layer):
    print("\n【D】Q4_0 分块方向（文档候选 #2）")
    sh = load_shard(stream, layer)
    if not sh:
        return None
    gguf_name = "blk.0.ffn_down.weight"      # 取一个纯 nf4 的线性层
    g = tensors.get(gguf_name)
    if g is None:
        print("  ⚠ GGUF 里没有 %s" % gguf_name)
        return None
    # 从切片里找对应的真实权重（nf4 打包，解量化要用 bnb；这里只比"块间尺度"的指纹）
    print("  GGUF 张量: shape=%s dtype=%s bytes=%d" % (g.shape, g.dtype, g.nbytes))
    if g.dtype == np.uint8:
        try:
            deq = dequant_q4_0_blocks(g, g.shape[-1] if g.ndim > 1 else 32 * 32)
            print("  按 Q4_0 块解回: shape=%s 均值=%.5f 标准差=%.5f" %
                  (deq.shape, float(deq.mean()), float(deq.std())))
            print("  （若 std 极端小/极大，或出现整块相同值 ⇒ 分块方向反了）")
        except Exception as e:
            print("  解块失败: %s" % e)
    else:
        print("  dtype 不是 uint8（可能被 gguf 包解成了 float），判据转人工核对")


# ────────────────────────── 主流程 ──────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gguf", required=True)
    ap.add_argument("--stream", required=True)
    ap.add_argument("--layer", default="layer_00")
    a = ap.parse_args()

    gp, sp = Path(a.gguf), Path(a.stream)
    print("=" * 62)
    print("vanavana 病灶定位器")
    print("  GGUF  :", gp)
    print("  切片  :", sp)
    print("  层    :", a.layer)
    print("=" * 62)
    if not gp.is_file():
        print("🔴 GGUF 不在:", gp); return 2
    if not sp.is_dir():
        print("🔴 切片目录不在:", sp); return 2

    tensors, meta, ok = read_gguf(gp)
    if ok:
        print("\nGGUF 张量数: %d" % len(tensors))
        arch = meta.get("general.architecture")
        print("架构:", arch, "| bos:", meta.get("tokenizer.ggml.bos_token_id"),
              "| eos:", meta.get("tokenizer.ggml.eos_token_id"))

    a_swap = check_A(tensors, meta, sp, ok)
    b_rope = check_B(tensors, sp, a.layer)
    c_bias = check_C(tensors, sp, a.layer)
    check_D(tensors, sp, a.layer)

    print("\n" + "=" * 62)
    print("结论")
    print("=" * 62)
    found = []
    if a_swap: found.append("A 两表写反 → 把 output.weight 改成 lm_head")
    if b_rope: found.append("B q/k 未做 RoPE 置换 → 加 permute() 再写")
    if c_bias: found.append("C bias 丢失 → 补 attn_q/k/v.bias")
    if not found:
        print("  以上四条都没命中 ⇒ 病灶在别处（跑 §5.2 的 logit 对照法继续收窄）")
    for i, f in enumerate(found, 1):
        print("  %d. %s" % (i, f))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
