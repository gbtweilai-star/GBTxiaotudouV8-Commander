# -*- coding: utf-8 -*-
"""免费 GPU 上跑我们自己的权重 —— Colab / Kaggle 一键服务脚本。

## 口径（主人令 2026-10-24：走免费 GPU，不花钱；不需要把权重"部署到别家"）
本脚本在**免费 GPU 会话**里跑，做三件事：
  ① 用 transformers + bitsandbytes 4bit 加载我们本地的模型目录（Qwen2 架构 · nf4 · 4.43 GB）
  ② 起一个 **OpenAI 兼容** /v1/chat/completions（回包带 `gbt.weights_ours=true`，明示跑的是我们自己的权重）
  ③ 用 cloudflared 快速隧道把它暴露成公网 https 地址（本机桥当"电缆"插过去：`GBT_OURS_BASE_URL`）

## 在 Colab 里怎么用（只有两步是人手）
  1) 把 `pack-weights.py` 打出来的 zip 上传到 Colab（左侧文件面板 / 或 `files.upload()`）
  2) 新建单元格，粘贴下面整段（`BASE_URL` 出来后你会看到一行 `https://xxxx.trycloudflare.com`）

```python
!pip -q install "transformers>=4.44" accelerate bitsandbytes fastapi uvicorn
!wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared
!unzip -q /content/gbt-weights.zip -d /content/gbt-weights
!python run_gbt_gpu.py --model-dir /content/gbt-weights
```

（本文件就是 `run_gbt_gpu.py` 的内容：拷成同名文件，或直接 `!curl` 到此环境。）
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time

# 编码守门（2026-10-24 补 · encoding-guard-check 报的「新增违规」之一）
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True, help="解压后的权重目录（含 config.json / *.safetensors / stream_manifest.json）")
    ap.add_argument("--port", type=int, default=8077)
    ap.add_argument("--max-new-tokens", type=int, default=512)
    a = ap.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print("[gbt] device =", dev, "· torch =", torch.__version__, flush=True)
    if dev == "cuda":
        print("[gbt] gpu =", torch.cuda.get_device_name(0),
              "· vram = %.1f GB" % (torch.cuda.get_device_properties(0).total_memory / 1024**3), flush=True)

    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(a.model_dir, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        a.model_dir, device_map="auto", trust_remote_code=True,
        torch_dtype=torch.float16 if dev == "cuda" else torch.float32,
        # 目录里已带 nf4 量化配置（config.json.quantization_config）⇒ bitsandbytes 会按它加载
    )
    model.eval()
    print("[gbt] 模型已加载 · %.1f 秒 · %.2f GB" % (
        time.time() - t0, sum(p.numel() * p.element_size() for p in model.parameters()) / 1024**3), flush=True)

    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    import uvicorn

    app = FastAPI()

    @app.get("/health")
    def health():
        return {"ok": True, "weights_ours": True, "model": a.model_dir,
                "device": dev, "at": time.strftime("%Y-%m-%dT%H:%M:%S")}

    @app.get("/v1/models")
    def models():
        return {"object": "list", "data": [{"id": "gbt-v8", "object": "model", "owned_by": "gbt"}]}

    @app.post("/v1/chat/completions")
    async def chat(body: dict):
        msgs = body.get("messages") or [{"role": "user", "content": ""}]
        max_new = int(body.get("max_tokens") or a.max_new_tokens)
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        ids = tok(text, return_tensors="pt").to(model.device)
        t1 = time.time()
        with torch.no_grad():
            out = model.generate(**ids, max_new_tokens=max_new, do_sample=bool(body.get("temperature")),
                                 temperature=float(body.get("temperature") or 0.7), top_p=0.9,
                                 pad_token_id=tok.eos_token_id)
        gen = out[0][ids["input_ids"].shape[1]:]
        ans = tok.decode(gen, skip_special_tokens=True)
        return JSONResponse({
            "id": "gbt-" + str(int(time.time())), "object": "chat.completion", "model": "gbt-v8",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": ans}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": int(ids["input_ids"].shape[1]), "completion_tokens": int(gen.shape[0])},
            "gbt": {"weights_ours": True, "host": "free-gpu", "ms": int((time.time() - t1) * 1000)},
        })

    def tunnel():
        time.sleep(1.5)
        p = subprocess.Popen(["cloudflared", "tunnel", "--url", "http://127.0.0.1:%d" % a.port, "--no-autoupdate"],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in p.stdout:                                  # noqa: BLE001
            if "trycloudflare.com" in line:
                print("\n[gbt] === 把这一行地址发给主人 ===  " +
                      [w for w in line.split() if "trycloudflare.com" in w][0] + "\n", flush=True)

    threading.Thread(target=tunnel, daemon=True).start()
    print("[gbt] 服务起在 127.0.0.1:%d · 隧道启动中…" % a.port, flush=True)
    uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
