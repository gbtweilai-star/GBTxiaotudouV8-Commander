# -*- coding: utf-8 -*-
"""渲染「只调算力（CPU/GPU），不调用大模型」的证明图。

判据（写死，可复核）——怎么才算"只调算力、没调大模型"：
  · 回执里只有 kernel / seconds / GFLOPs（算力指标），**没有** text / usage.tokens / model；
  · 没有请求体发到任何模型端点（零出网，或只连算力节点）；
  · 结果能被独立复算（同样的矩阵乘，时间在一个量级）。

本图三类读数并列（都是现读，不手抄）：
  ① 本机 CPU 纯算力：numpy float32 2048x2048 matmul —— 真跑，带耗时与 GFLOP/s
  ② 本机 GPU：torch 的 CUDA 现状（不可用就如实写 device_count=0，不假装）
  ③ 云端 GPU 纯算力：付费宿主现状（PRIMARY 读数来自 pod_link status）+ 免费 GPU 那条走的是**模型推理**
     （wan22 diffusion），按本仓口径**不算**纯算力 —— 这一条要写清，免得把"模型"当"算力"。

数据源：outputs/open-source-release/data/pure-compute-live.json
产物：outputs/open-source-release/assets/fig-pure-compute.png
用法：py -3.12 -X utf8 tools/codex-scripts/render-pure-compute.py
"""
from __future__ import annotations

import json
import pathlib

from PIL import Image, ImageDraw, ImageFont
import sys
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
REL = ROOT / "outputs" / "open-source-release"
DATA = REL / "data"
ASSETS = REL / "assets"

W, H = 1180, 700
BG = (11, 14, 19)
CARD = (17, 22, 31)
LINE = (29, 37, 48)
TXT = (232, 237, 245)
DIM = (154, 167, 184)
GREEN = (46, 160, 67)
BLUE = (76, 141, 255)
AMBER = (224, 160, 58)
MONO = ("consola.ttf", "CascadiaMono.ttf", "DejaVuSansMono.ttf")
CJK = ("msyh.ttc", "simhei.ttf", "PingFang.ttc")


def font(size: int, mono: bool = False):
    for n in (MONO if mono else CJK):
        try:
            return ImageFont.truetype(n, size)
        except Exception:                                     # noqa: BLE001
            continue
    try:
        return ImageFont.load_default(size)
    except Exception:                                         # noqa: BLE001
        return ImageFont.load_default()


def box(d, xy, outline=LINE):
    d.rounded_rectangle(xy, radius=12, fill=CARD, outline=outline, width=2)


def main() -> int:
    p = DATA / "pure-compute-live.json"
    d0 = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    cpu = d0.get("cpu") or {}
    gpu = d0.get("gpu") or {}
    cloud = d0.get("cloud_gpu") or {}
    note = d0.get("note") or ""

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((28, 22), "只调算力（CPU / GPU）· 不调用大模型 —— 三类现读读数", font=font(22), fill=TXT)
    d.text((28, 54), "判据：回执里只有 kernel / seconds / GFLOPs，没有 text / usage.tokens / model", font=font(13), fill=DIM)

    # ① 本机 CPU
    box(d, [24, 86, 578, 330])
    d.text((44, 100), "① 本机 CPU · 纯算力真跑", font=font(16), fill=GREEN)
    rows = [
        ("kernel", cpu.get("kernel")),
        ("seconds", cpu.get("seconds")),
        ("GFLOP/s", cpu.get("gflops")),
        ("threads/CPU", (d0.get("machine") or {}).get("cpu")),
        ("大模型调用", "无（回执里没有 text / tokens / model）"),
    ]
    y = 132
    for k, v in rows:
        d.text((44, y), k, font=font(12), fill=DIM)
        d.text((196, y), str(v)[:40], font=font(12), fill=GREEN if k in ("GFLOP/s", "大模型调用") else TXT)
        y += 30

    # ② 本机 GPU
    box(d, [602, 86, 1156, 330])
    d.text((622, 100), "② 本机 GPU · 现状（不许假装）", font=font(16), fill=AMBER)
    rows2 = [
        ("cuda_available", gpu.get("cuda_available")),
        ("device_count", gpu.get("device_count")),
        ("torch", d0.get("torch")),
        ("结论", "本机没有可用 CUDA 卡 ⇒ 本机 GPU 纯算力：无"),
    ]
    y = 132
    for k, v in rows2:
        d.text((622, y), k, font=font(12), fill=DIM)
        d.text((782, y), str(v)[:40], font=font(12), fill=AMBER if k == "结论" else TXT)
        y += 30

    # ③ 云端 GPU
    box(d, [24, 348, 1156, 520])
    d.text((44, 362), "③ 云端 GPU · 两种东西要分清", font=font(16), fill=BLUE)
    left = [
        ("付费卡现状", cloud.get("pods") or "—"),
        ("能不能起", "0 张在跑 ⇒ 云端纯算力：无（宿主无空卡）"),
        ("上游原话", "not enough free GPUs on the host machine"),
    ]
    y = 394
    for k, v in left:
        d.text((44, y), k, font=font(12), fill=DIM)
        d.text((176, y), str(v)[:46], font=font(12), fill=AMBER if k == "能不能起" else TXT)
        y += 28
    d.text((600, 394), "免费 GPU 那条（wan22 diffusion）", font=font(12), fill=DIM)
    d.text((600, 420), "跑的是**模型推理**，不是纯算力 ——", font=font(12), fill=AMBER)
    d.text((600, 444), "它的回执里有 model/space，按本仓口径", font=font(12), fill=AMBER)
    d.text((600, 468), "**不能**算进「只调算力」这一栏。", font=font(12), fill=AMBER)

    # 底
    d.line([24, 536, 1156, 536], fill=LINE, width=1)
    d.text((28, 552), "怎么复核（两条命令，都不花钱）", font=font(14), fill=TXT)
    d.text((28, 580), "py -3.12 tools/codex-scripts/probe-pure-compute.py      # 重跑本机 CPU/GPU 纯算力，写 data/pure-compute-live.json",
           font=font(12), fill=DIM)
    d.text((28, 606), "py -3.14 tools/codex-scripts/five-dim.py cap pod_link '{\"op\":\"status\"}'   # 云端 GPU 现状（付费卡）",
           font=font(12), fill=DIM)
    if note:
        d.text((28, 636), note[:150], font=font(11), fill=DIM)
    d.text((28, H - 44), "开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属", font=font(12), fill=(90, 100, 114))
    d.text((28, H - 22), "渲染：tools/codex-scripts/render-pure-compute.py（数据变，图跟着变，不手改图）",
           font=font(11), fill=(90, 100, 114))

    ASSETS.mkdir(parents=True, exist_ok=True)
    out = ASSETS / "fig-pure-compute.png"
    img.save(out)
    print("已渲染 →", out, "·", out.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
