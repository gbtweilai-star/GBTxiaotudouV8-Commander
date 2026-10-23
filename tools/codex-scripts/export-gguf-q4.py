# -*- coding: utf-8 -*-
"""把我们自己的权重导成 **GGUF（Q4_0）** —— 给 llama.cpp 的 CPU 内核用。

## 为什么必须换引擎（读数说话，不是换着玩）
我方前向已与官方**逐 logit 对齐**，但本机速度 0.03 tok/s：瓶颈不是算法，是
「每 token 把 12.5 GB fp16 从盘读进内存、再转 fp32 做矩阵乘」——7.4 GB 内存装不下，
于是不停地读盘 + 反复做 dtype 转换。
llama.cpp 的 Q4_0 权重**打包存在**（7B ≈ 4 GB），内存映射 + 解包在寄存器里做，
同价位机器常见 2–4 tok/s。我们只需要把权重**换个容器**，模型还是我们自己的。

## 输入 / 输出
· 输入：`state/weights/_fp16mmap/layer_XX.npz`（我方已解量化的 fp16 层）+ 原始 embed/lm_head/norm
· 输出：`state/weights/gbt-v8-v82-q4_0.gguf`（llama.cpp 直接可跑）

## 张量命名（llama.cpp 的 qwen2 约定）
    token_embd.weight · output_norm.weight · output.weight
    blk.N.attn_norm.weight / ffn_norm.weight
    blk.N.attn_q.weight|bias · attn_k · attn_v · attn_output
    blk.N.ffn_gate · ffn_up · ffn_down
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import gguf

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "state", "weights", "gbt-v8-v82-stream")
FP16 = os.path.join(ROOT, "state", "weights", "_fp16mmap")
OUT = os.path.join(ROOT, "state", "weights",
                   "gbt-v8-v82-fp16.gguf" if os.environ.get("GBT_GGUF_FP16") == "1"
                   else ("gbt-v8-v82-q4_0-io16.gguf" if os.environ.get("GBT_GGUF_KEEP_IO") == "1"
                         else "gbt-v8-v82-%s.gguf" % os.environ.get("GBT_GGUF_TYPE", "q4_0").lower()))

# 我方 npz 里的键 → llama.cpp 张量名
PROJ_MAP = {
    "self_attn.q_proj": "attn_q",
    "self_attn.k_proj": "attn_k",
    "self_attn.v_proj": "attn_v",
    "self_attn.o_proj": "attn_output",
    "mlp.gate_proj": "ffn_gate",
    "mlp.up_proj": "ffn_up",
    "mlp.down_proj": "ffn_down",
}
SMALL_MAP = {
    "input_layernorm.weight": "attn_norm.weight",
    "post_attention_layernorm.weight": "ffn_norm.weight",
    "self_attn.q_proj.bias": "attn_q.bias",
    "self_attn.k_proj.bias": "attn_k.bias",
    "self_attn.v_proj.bias": "attn_v.bias",
}


FP16_ONLY = os.environ.get("GBT_GGUF_FP16") == "1"
# 🔴 2026-10-24 03:14 A/B 实测：整份 Q4_0 ⇒ 输出崩（vanavana）；整份 fp16 ⇒ 通顺（'哪里？'）。
#    llama.cpp 的惯例也是「embed / output / norm 不进低比特量化」（官方 quantize 把 output 留 Q6_K）。
#    KEEP_IO_FP16=1 ⇒ token_embd / output / 所有 norm 保 fp16，其余 Q4_0。
KEEP_IO_FP16 = os.environ.get("GBT_GGUF_KEEP_IO") == "1"
# 2026-10-24 03:24 A/B：fp16 通顺 / Q4_0 崩 ⇒ 换 Q8_0（8.5 bit，7.5GB）验证量化位宽阈值
GGUF_TYPE = os.environ.get("GBT_GGUF_TYPE", "Q4_0").upper()
QK_ELEMS = 32
_ROW_BYTES = {"Q4_0": 18, "Q4_1": 20, "Q5_0": 22, "Q5_1": 24, "Q8_0": 34}
_QTYPE = {"Q4_0": gguf.GGMLQuantizationType.Q4_0,
          "Q8_0": gguf.GGMLQuantizationType.Q8_0,
          "Q5_0": gguf.GGMLQuantizationType.Q5_0,
          "Q5_1": gguf.GGMLQuantizationType.Q5_1}.get(GGUF_TYPE, gguf.GGMLQuantizationType.Q4_0)   # 1 = 导出 fp16（不量化），用于 A/B 对照


def add_tensor(w: gguf.GGUFWriter, name: str, arr: np.ndarray, quantize: bool):
    """大矩阵按需激活（分块量化），小张量（norm/bias）保持 F32。

    🔴 2026-10-24 实测：整块 astype(float32) 对 down_proj (18944×3584) 要 259 MiB，
    加上 quantize 内部的临时数组，7.4 GB 机器在写到第 7 层时就 MemoryError。
    改成 2048 行一块：峰值从 ~800 MiB 降到 ~40 MiB。
    """
    if arr.ndim == 2 and quantize and not FP16_ONLY:
        keep = KEEP_IO_FP16 and (name in ("token_embd.weight", "output.weight")
                                 or name.endswith("_norm.weight"))
        if not keep:
            rows, k = arr.shape
            nb = k // QK_ELEMS
            row_bytes = {"Q4_0": 18, "Q4_1": 20, "Q5_0": 22, "Q5_1": 24, "Q8_0": 34}.get(GGUF_TYPE, 18)
            out = np.empty((rows, nb * row_bytes), dtype=np.uint8)
            for lo in range(0, rows, 2048):
                hi = min(lo + 2048, rows)
                a = np.ascontiguousarray(arr[lo:hi].astype(np.float32))
                out[lo:hi] = gguf.quants.quantize(a, _QTYPE)
                del a
            w.add_tensor(name, out, raw_dtype=_QTYPE)
            return
    a = np.ascontiguousarray(arr.astype(np.float32))
    # 🔴 2026-10-24 02:23 实测修正：ggml 的二维张量约定是 **ne0 = 输入维**，
    #   而 PyTorch 权重是 [out, in]。不转置就会「能加载、能跑、但输出 vanavana 这种乱码」。
    # 2026-10-24 02:30 实测：gguf 库写 dims 时会把 numpy shape **反着写**，
    #   于是 numpy [out, in] 正好落成 llama.cpp 要的 ne0=in。**不要转置**
    #   （转置后 llama.cpp 报 token_embd 期望 3584,152064 却得到 152064,3584）。
    if not quantize or a.ndim != 2:
        w.add_tensor(name, a)
        return
    if FP16_ONLY:                                     # A/B 对照用：保持 fp16，不量化
        w.add_tensor(name, a.astype(np.float16))
        return
    if KEEP_IO_FP16 and (name in ("token_embd.weight", "output.weight") or name.endswith("_norm.weight")):
        w.add_tensor(name, a.astype(np.float16))      # IO 与 norm 保精度，不量化
        return
    q = gguf.quants.quantize(a, _QTYPE)
    w.add_tensor(name, q, raw_dtype=_QTYPE)


def resolve_special_ids(tcfg: dict, tok: dict, n_vocab: int) -> dict:
    """从 tokenizer_config.json + tokenizer.json 里解析 bos/eos/pad 的 id。

    🔴 关键：Qwen 的特殊 token（<|im_end|>/<|endoftext|>/<|im_start|>）**不在** model.vocab
    （那里只有 151643 条），它们在 added_tokens 里。只用 vocab 查 = 永远查不到 =
    GGUF 缺这三个键 = llama.cpp 回落 eos=11（逗号）= 生成到第一个逗号就截断。
    """
    vocab = tok["model"]["vocab"]
    added = tok.get("added_tokens") or []
    name2id = dict(vocab)
    for a in added:
        i = int(a["id"])
        if i < n_vocab:
            name2id[a["content"]] = i

    def _tid(v):
        if isinstance(v, dict):
            v = v.get("content")
        return name2id.get(v) if isinstance(v, str) else None

    eos_id = _tid(tcfg.get("eos_token"))
    pad_id = _tid(tcfg.get("pad_token")) or _tid("<|endoftext|>")
    bos_id = _tid(tcfg.get("bos_token")) or pad_id      # Qwen2 惯例：bos 缺省 = <|endoftext|>
    return {"bos": bos_id, "eos": eos_id, "pad": pad_id}


def add_int8_matrix(w: gguf.GGUFWriter, name: str, shard, qkey: str, skey: str,
                    chunk: int = 4096) -> None:
    """把 int8 权重矩阵（q × 每行尺度 s）**分块**解量化后写盘。

    🔴 2026-10-24 实测修正：embed 是 152064×3584 = 5.45 亿参数，原来的
    "q.astype(float32) 再 q*s" 要一口气吃 ~4.4 GB —— 7.4 GB 的机器直接 OOM
    （numpy: Unable to allocate 520 MiB / 2.18 GB）。分块后峰值只有 chunk×k×4 字节。
    """
    qm = shard.get_mmap(qkey) if hasattr(shard, "get_mmap") else shard.get(qkey)
    s = np.asarray(shard.get(skey), dtype=np.float32).reshape(-1)
    rows, k = qm.shape
    if s.size == rows:
        pass                                  # 每行一个尺度
    elif s.size == 1:
        s = np.full((rows,), float(s[0]), dtype=np.float32)
    else:
        raise ValueError("%s 的尺度个数 %d 与行数 %d 对不上" % (name, s.size, rows))

    keep_fp16 = FP16_ONLY or (KEEP_IO_FP16 and name in ("token_embd.weight", "output.weight"))
    if keep_fp16:
        out = np.empty((rows, k), dtype=np.float16)
        for lo in range(0, rows, chunk):
            hi = min(lo + chunk, rows)
            out[lo:hi] = (qm[lo:hi].astype(np.float32) * s[lo:hi, None]).astype(np.float16)
        w.add_tensor(name, out)
        print("  %s → fp16 %s" % (name, out.shape), flush=True)
        return

    nb = k // 32
    if k % 32:
        raise ValueError("%s 的 ne0=%d 不是 32 的倍数" % (name, k))
    # 🔴 每块字节数随量化类型变：Q4_0=18 · Q4_1=20 · Q5_0=22 · Q5_1=24 · Q8_0=34
    #   原写死 18，跑 Q5_0 时报 "could not broadcast (4096,2464) into (4096,2016)"。
    row_bytes = {"Q4_0": 18, "Q4_1": 20, "Q5_0": 22, "Q5_1": 24, "Q8_0": 34}.get(GGUF_TYPE, 18)
    out = np.empty((rows, nb * row_bytes), dtype=np.uint8)
    t0 = time.time()
    # 🔴 自适应分块：这台机器的 commit 会突然塌到几十 MB，固定 4096 行（56 MiB）会半路 OOM。
    #   失败就减半重试，成功后再慢慢加回去。
    lo, cur = 0, chunk
    while lo < rows:
        hi = min(lo + cur, rows)
        try:
            a = qm[lo:hi].astype(np.float32) * s[lo:hi, None]
            out[lo:hi] = gguf.quants.quantize(a, _QTYPE)
            del a
        except MemoryError:
            if cur <= 64:
                raise
            cur = max(64, cur // 2)
            continue
        lo = hi
        if cur < chunk:
            cur = min(chunk, cur * 2)
    w.add_tensor(name, out, raw_dtype=_QTYPE)
    print("  %s → %s 分块量化 %s · %.0fs" % (name, GGUF_TYPE, out.shape, time.time() - t0), flush=True)


def load_npz(i: int):
    return np.load(os.path.join(FP16, "layer_%02d.npz" % i))


def main() -> int:
    cfg = json.load(open(os.path.join(SRC, "config.json"), encoding="utf-8"))
    tok = json.load(open(os.path.join(SRC, "tokenizer.json"), encoding="utf-8"))
    n_layers = cfg["num_hidden_layers"]
    hidden = cfg["hidden_size"]

    # 🔴 2026-10-24 实测：use_temp_file=False 时 writer 把所有张量**攒在内存里**，
    #   到最后才落盘 —— 4 GB 的模型就要 4 GB 常驻，7.4 GB 机器必然 OOM。
    #   置 True 后超过 256 MB 自动滚到临时文件，内存只留一个 chunk。
    w = gguf.GGUFWriter(OUT, "qwen2", use_temp_file=True)
    w.add_name("gbt-v8-v82")
    w.add_context_length(int(cfg.get("max_position_embeddings") or 32768))
    w.add_block_count(n_layers)
    w.add_embedding_length(hidden)
    w.add_feed_forward_length(cfg["intermediate_size"])
    w.add_head_count(cfg["num_attention_heads"])
    w.add_head_count_kv(cfg["num_key_value_heads"])
    w.add_rope_freq_base(float(cfg.get("rope_theta") or 1e6))
    w.add_layer_norm_rms_eps(float(cfg.get("rms_norm_eps") or 1e-6))
    w.add_file_type(gguf.LlamaFileType.MOSTLY_F16 if FP16_ONLY else gguf.LlamaFileType.MOSTLY_Q4_0)
    # 🔴 2026-10-24 02:05 实测补：llama.cpp 加载器要求 tokenizer.model / tokenizer.pre 两个键，
    #   缺了会报 "key not found in model: tokenizer.ggml.model"（模型本身没毛病）。
    w.add_tokenizer_model("gpt2")     # Qwen2 用 BPE（gpt2 语义）
    w.add_tokenizer_pre("qwen2")      # 预分词规则名

    # ---- tokenizer ----
    vocab = tok["model"]["vocab"]                      # token -> id
    # 🔴 2026-10-24 02:07 实测修正：词表长度必须取 **config.vocab_size**（152064），
    #   不能取 max(vocab)+1（151643）。否则 ① 特殊 token（<|im_start|>/<|im_end|>）被挤掉、
    #   ② token_embd 行数(152064)与词表长度(151643)对不上，llama.cpp 直接拒载：
    #   "tensor 'token_embd.weight' has wrong shape; expected 3584, 151643, got 3584, 152064"
    n_vocab = int(cfg["vocab_size"])
    tokens = [""] * n_vocab
    scores = [0.0] * n_vocab
    ttype = [1] * n_vocab                              # 1 = NORMAL
    for t, i in vocab.items():
        tokens[i] = t
    added = tok.get("added_tokens") or []              # 22 个特殊 token 全在这里（不在 model.vocab）
    for a in added:                                    # 特殊 token 覆盖
        i = int(a["id"])
        if i < n_vocab:
            tokens[i] = a["content"]
            ttype[i] = 3 if a.get("special") else 1     # 3 = CONTROL
    w.add_token_list(tokens)
    w.add_token_scores(scores)
    w.add_token_types([gguf.TokenType(t) for t in ttype])
    merges = tok["model"].get("merges") or []
    if merges:
        w.add_token_merges([m if isinstance(m, str) else " ".join(m) for m in merges])
    # 🔴 2026-10-24 02:14 实测补：chat 模板与特殊 token 在 tokenizer_config.json 里，
    #   不写进 GGUF ⇒ llama.cpp 用默认模板拼 prompt，模型会输出 "vanavana…" 这种乱码。
    tcfg_path = os.path.join(SRC, "tokenizer_config.json")
    tcfg = json.load(open(tcfg_path, encoding="utf-8")) if os.path.isfile(tcfg_path) else {}
    ct = tcfg.get("chat_template")
    if ct:
        w.add_chat_template(ct)
        print("已写入 chat_template（%d 字符）" % len(ct), flush=True)
    # 🔴 2026-10-24 实测修正（本机复现）：特殊 token（<|im_end|>/<|endoftext|>/<|im_start|>）
    #    **不在** tokenizer.json 的 model.vocab 里（那里只有 151643 条），它们在 added_tokens 里。
    #    原来用 "v in vocab" 判断 ⇒ 永远为假 ⇒ GGUF 里根本没有 bos/eos/pad 三个键，
    #    llama.cpp 回落到默认 eos=11（实测解出来是逗号），**生成到第一个逗号就停**。
    #    症状：fp16 只吐 "哪里？" 两个 token 就收尾，看着像"通顺"，其实是截断。
    special = resolve_special_ids(tcfg, tok, n_vocab)
    for k in ("bos", "eos", "pad"):
        i = special[k]
        if i is None:
            print("  🔴 %s_token_id 取不到，未写入（llama.cpp 会回落默认值，生成会被截断）" % k, flush=True)
        else:
            getattr(w, "add_%s_token_id" % k)(i)
            print("  %s_token_id = %d (%r)" % (k, i, tokens[i]), flush=True)
    w.add_add_bos_token(False)

    # ---- 小张量 & embed / lm_head ----
    sys.path.insert(0, os.path.join(ROOT, "tools", "codex-scripts"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gli", os.path.join(ROOT, "tools", "codex-scripts", "gbt-local-infer.py"))
    gli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gli)

    sh = gli.Shard(os.path.join(SRC, "embed_int8.safetensors"))
    add_int8_matrix(w, "token_embd.weight", sh, "model.embed_tokens.weight.q",
                    "model.embed_tokens.weight.s")
    del sh

    lsh = gli.Shard(os.path.join(SRC, "lm_head_int8.safetensors"))
    add_int8_matrix(w, "output.weight", lsh, "lm_head.weight.q", "lm_head.weight.s")
    del lsh

    nsh = gli.Shard(os.path.join(SRC, "norm.safetensors"))
    add_tensor(w, "output_norm.weight", nsh.get("model.norm.weight"), False)

    # ---- 逐层 ----
    t0 = time.time()
    for li in range(n_layers):
        z = load_npz(li)
        for src_key, dst in PROJ_MAP.items():
            add_tensor(w, "blk.%d.%s.weight" % (li, dst), z[src_key], True)
        for src_key, dst in SMALL_MAP.items():
            add_tensor(w, "blk.%d.%s" % (li, dst), z[src_key], False)
        del z
        print("层 %02d 已写入 · %.0fs · 输出 %.1f GB" % (
            li, time.time() - t0, os.path.getsize(OUT) / 1024**3 if os.path.exists(OUT) else 0), flush=True)

    w.write_header_to_file()
    w.write_kv_data_to_file()
    w.write_tensors_to_file()
    w.close()
    print("完成: %s · %.2f GB" % (OUT, os.path.getsize(OUT) / 1024**3), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
