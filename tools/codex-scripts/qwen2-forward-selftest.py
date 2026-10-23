# -*- coding: utf-8 -*-
"""自检：我方前向 vs transformers 官方 Qwen2（同一个**随机小模型**，逐 logit 比对）。

## 为什么要这一件（P1：判据不能拿自己比自己）
本机跑真权重时输出 `'在位面'` —— 「不对」是确定的，但**错在前向还是错在权重**分不出来。
所以造一个 2 层 × hidden 64 的随机 Qwen2，把同一份权重喂给我方前向和官方前向，
**同一个输入逐 logit 比**：差异 > 1e-4 就说明我方前向有 bug（与权重无关）。

用法：py -3 tools/codex-scripts/qwen2-forward-selftest.py
"""
from __future__ import annotations

import importlib.util
import os
import sys

import numpy as np
import torch

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "gli", os.path.join(ROOT, "tools", "codex-scripts", "gbt-local-infer.py"))
gli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gli)


def build_reference():
    from transformers import Qwen2Config, Qwen2ForCausalLM
    cfg = Qwen2Config(vocab_size=128, hidden_size=64, num_hidden_layers=2,
                      num_attention_heads=4, num_key_value_heads=2, intermediate_size=128,
                      max_position_embeddings=64, rope_theta=10000.0, rms_norm_eps=1e-6,
                      tie_word_embeddings=False)
    torch.manual_seed(0)
    m = Qwen2ForCausalLM(cfg).eval()
    return cfg, m


class Adapter(gli.Model):
    """把我方前向接到官方小模型的权重上（不走分片、不进量化）。"""

    def __init__(self, cfg, ref):
        self.fp16_dir = None
        self._npz_i = -1
        self._npz = None
        self.cfg = {"model_type": "qwen2", "hidden_size": cfg.hidden_size,
                    "num_hidden_layers": cfg.num_hidden_layers,
                    "num_attention_heads": cfg.num_attention_heads,
                    "num_key_value_heads": cfg.num_key_value_heads,
                    "rms_norm_eps": cfg.rms_norm_eps, "rope_theta": cfg.rope_theta}
        self.hidden = cfg.hidden_size
        self.n_layers = cfg.num_hidden_layers
        self.n_heads = cfg.num_attention_heads
        self.n_kv = cfg.num_key_value_heads
        self.head_dim = self.hidden // self.n_heads
        self.eps = cfg.rms_norm_eps
        self.rope_theta = cfg.rope_theta
        self.verbose = False
        self.ref = ref
        self.norm_w = ref.model.norm.weight.detach().numpy().astype(np.float32)

    # —— 数据面全部取自官方模型 ——
    def embed_rows(self, ids):
        return self.ref.model.embed_tokens(torch.tensor(ids)).detach()

    def layer_weight(self, i, proj):
        return self.ref.model.layers[i].get_submodule(proj).weight.detach().clone()

    def layer_small(self, i, name):
        path, attr = name.rsplit(".", 1)          # 例：input_layernorm.weight
        mod = self.ref.model.layers[i]
        if path:
            mod = mod.get_submodule(path)
        return getattr(mod, attr).detach().clone()

    def lm_head_logits(self, x):
        return self.ref.lm_head(x.unsqueeze(0))[0].detach()


def main() -> int:
    cfg, ref = build_reference()
    ids = [5, 9, 11, 40, 77]
    with torch.no_grad():
        ref_out = ref(torch.tensor([ids])).logits[0, -1]     # 官方：最后位置 logits
    ad = Adapter(cfg, ref)
    kv = [(None, None) for _ in range(ad.n_layers)]
    mine, _ = ad.forward_step(ids, kv, 0)
    d = (mine - ref_out).abs()
    print("官方 logits 前 6:", np.round(ref_out.numpy()[:6], 4))
    print("我方 logits 前 6:", np.round(mine.numpy()[:6], 4))
    print("最大绝对差: %.6f · 平均绝对差: %.8f" % (d.max(), d.mean()))
    ok = float(d.max()) < 1e-4
    print("结论:", "✅ 前向与官方一致" if ok else "🔴 前向有 bug（逐层再查）")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
