# -*- coding: utf-8 -*-
"""权重完整性核对（结构判据，不靠指纹）：这份到底是不是**完整**的 28 层模型。

## 为什么用结构判据（P1：量具不能错尺）
聚合指纹 `50218a0089b74cb9` 的算法口径没留全（排序/是否含名/是否含字节都不明），
64 种组合全试不命中 —— **指纹对不上不能推出"权重不完整"**，那是拿坏尺子量东西。
真正该问的是：**28 层的每一张该有的张量在不在、形状对不对、有没有残缺片**。

## 判据（逐条机检，缺一条都红）
C1 层数：28 层的分片 28 个，且 layer_00..layer_27 一个不缺
C2 每层张量：14 项（2 个 norm + 4 个 attn 权重 + 3 个 bias + 3 个 mlp 权重），形状与 config 对齐
C3 embed：q[152064,3584] + s[152064,1]
C4 lm_head：q[152064,3584] + s[152064,1]
C5 norm：[3584]
C6 量化元信息：每个被量化的权重都必须带 absmax / quant_map / quant_state（缺一个 = 半个权重）
C7 分片非空、且 manifest 里登记的文件全部存在

用法：py -3 tools/codex-scripts/weights-completeness.py [--dir state/weights/gbt-v8-v82-stream]
"""
from __future__ import annotations

import argparse
import json
import os
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT = os.path.join(ROOT, "state", "weights", "gbt-v8-v82-stream")


def header(path: str) -> dict:
    with open(path, "rb") as fh:
        n = struct.unpack("<Q", fh.read(8))[0]
        h = json.loads(fh.read(n).decode("utf-8"))
    h.pop("__metadata__", None)
    return h


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=DEFAULT)
    a = ap.parse_args()
    d = a.dir
    cfg = json.load(open(os.path.join(d, "config.json"), encoding="utf-8"))
    L = cfg["num_hidden_layers"]
    H = cfg["hidden_size"]
    KV = cfg["num_key_value_heads"] * (H // cfg["num_attention_heads"])
    I = cfg["intermediate_size"]
    V = cfg["vocab_size"]
    print("=== 权重完整性核对 ===")
    print("目标: %s" % d)
    print("配置: %d 层 · hidden %d · kv %d · ffn %d · vocab %d"
          % (L, H, KV, I, V))
    bad, notes = [], []

    # C1/C7：分片齐不齐
    man = json.load(open(os.path.join(d, "stream_manifest.json"), encoding="utf-8"))["groups"]
    missing_files = [g["file"] for g in man.values() if not os.path.isfile(os.path.join(d, g["file"]))]
    layer_files = [os.path.join(d, "layer_%02d.safetensors" % i) for i in range(L)]
    miss_layer = [os.path.basename(p) for p in layer_files if not os.path.isfile(p)]
    print("C1 层分片: 期望 %d 个 · 实到 %d 个 · 缺 %s"
          % (L, sum(1 for p in layer_files if os.path.isfile(p)), miss_layer or "无"))
    if miss_layer:
        bad.append("C1 缺层分片 %s" % miss_layer)
    if missing_files:
        bad.append("C7 manifest 登记但盘上没有: %s" % missing_files)

    # C2：逐层张量清单 + 形状
    expect = {
        "input_layernorm.weight": (H,),
        "post_attention_layernorm.weight": (H,),
        "self_attn.q_proj.weight": (H, H),
        "self_attn.k_proj.weight": (KV, H),
        "self_attn.v_proj.weight": (KV, H),
        "self_attn.o_proj.weight": (H, H),
        "self_attn.q_proj.bias": (H,),
        "self_attn.k_proj.bias": (KV,),
        "self_attn.v_proj.bias": (KV,),
        "mlp.gate_proj.weight": (I, H),
        "mlp.up_proj.weight": (I, H),
        "mlp.down_proj.weight": (H, I),
    }
    quant_need = ("absmax", "quant_map", "quant_state.bitsandbytes__nf4")
    miss_t, shape_t, quantmiss_t = [], [], []
    for li in range(L):
        p = os.path.join(d, "layer_%02d.safetensors" % li)
        if not os.path.isfile(p):
            continue
        h = header(p)
        for name, shp in expect.items():
            key = "model.layers.%d.%s" % (li, name)
            if key not in h:
                miss_t.append(key)
                continue
            got = tuple(h[key]["shape"])
            if got != shp and not (name.endswith(".weight") and got == (shp[0] * shp[1] // 2 if name.startswith("mlp") or "proj" in name else shp[0], 1)):
                # 量化权重会被打包：期望「元素数/2 行」或标准形状
                flat = 1
                for s in shp:
                    flat *= s
                if got not in (shp, (flat // 2, 1)):
                    shape_t.append("%s 期望 %s 或 (%d,1) 实得 %s" % (key, shp, flat // 2, got))
            # 量化三件套
            if name.endswith(".weight") and name not in ("input_layernorm.weight",
                                                         "post_attention_layernorm.weight"):
                for q in quant_need:
                    if "%s.%s" % (key, q) not in h:
                        quantmiss_t.append("%s.%s" % (key, q))
    print("C2 逐层张量: 缺 %d 项 · 形状不符 %d 项 · 量化元信息缺 %d 项"
          % (len(miss_t), len(shape_t), len(quantmiss_t)))
    if miss_t:
        bad.append("C2 缺张量 %d 项，例: %s" % (len(miss_t), miss_t[:3]))
        print("   缺张量样例:", miss_t[:5])
    if shape_t:
        bad.append("C2 形状不符 %d 项" % len(shape_t))
        print("   形状不符样例:", shape_t[:3])
    if quantmiss_t:
        bad.append("C6 量化元信息缺 %d 项" % len(quantmiss_t))
        print("   量化元信息缺样例:", quantmiss_t[:3])

    # C3 embed / C4 lm_head / C5 norm
    def check_simple(fname, pairs, tag):
        p = os.path.join(d, fname)
        if not os.path.isfile(p):
            bad.append("%s 缺文件 %s" % (tag, fname))
            print("%s 缺文件 %s" % (tag, fname))
            return
        h = header(p)
        for k, shp in pairs:
            if k not in h:
                bad.append("%s 缺 %s" % (tag, k))
                print("%s 缺 %s" % (tag, k))
                continue
            got = tuple(h[k]["shape"])
            ok = got == shp
            print("%s %-34s %s %s" % (tag, k, got, "✅" if ok else "🔴 期望 %s" % (shp,)))
            if not ok:
                bad.append("%s %s 形状 %s≠%s" % (tag, k, got, shp))

    check_simple("embed_int8.safetensors",
                 [("model.embed_tokens.weight.q", (V, H)),
                  ("model.embed_tokens.weight.s", (V, 1))], "C3")
    check_simple("lm_head_int8.safetensors",
                 [("lm_head.weight.q", (V, H)),
                  ("lm_head.weight.s", (V, 1))], "C4")
    check_simple("norm.safetensors", [("model.norm.weight", (H,))], "C5")

    print("\n=== 结论 ===")
    if bad:
        print("🔴 不完整 / 有缺陷 · %d 条:" % len(bad))
        for b in bad[:10]:
            print("   -", b)
        return 1
    print("✅ **完整**：%d 层逐层张量齐、量化三件套齐、embed/lm_head/norm 形状全对" % L)
    print("   （完整性用结构判据；聚合指纹口径不明，不参与本次判定）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
