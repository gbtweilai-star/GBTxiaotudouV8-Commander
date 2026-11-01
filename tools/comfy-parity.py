# -*- coding: utf-8 -*-
"""GBT天真 ↔ 秋叶版 ComfyUI 一比一（comfy-parity）。

## 口径（必须先看清，否则数字会骗人）

「秋叶版」= ComfyUI 核心 + 第三方插件。要**真一比一**，必须在装了秋叶版的机器上跑
`GET /object_info` 取全量节点（约 1495 把），落成 `state/comfyui_object_info.json`。

本工具优先读这个真快照；**读不到时**退到 `state/comfyui_ref_nodes.json`
（ComfyUI 官方核心面，可复现来源：codeload zip 解析），并在输出里**明确标注参照来源**——
不会把"核心面 127 把"冒充成"秋叶整包 1495 把"。

## 分类（未实现的节点为什么没实现）

    traditional   纯 CPU 图像算子（PIL 可长）     → 可补
    needs_model   采样/加载/条件/VAE/ControlNet   → 本机无 CUDA，需 GPU 或云端
    needs_cloud   云端 API 节点                    → 需 key
    unknown       无法归类                        → 如实标 unknown

用法：
    python tools/comfy-parity.py                 # 读数 + 落 state/comfy-parity.json
    python tools/comfy-parity.py --json x.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

REAL_SNAP = os.path.join(ROOT, "state", "comfyui_object_info.json")
CORE_REF = os.path.join(ROOT, "state", "comfyui_ref_nodes.json")

MODEL_HINTS = ("sampler", "checkpoint", "loader", "clip", "vae", "lora", "latent",
               "conditioning", "controlnet", "unet", "model", "attention", "tti",
               "gligen", "hypernetwork", "diffusion", "inpaint", "upscale_model",
               "freeu", "style_model", "guider", "sigmas", "noise", "merge",
               # 视频/3D/媒体栈（本机无 av/ffmpeg 与几何管线）
               "video", "3d", "glb", "splat", "pointcloud", "temporal", "keyframe",
               "wan", "ltxv", "hunyuan", "dancer", "humo", "sound", "encode", "training", "mediapipe", "hidream", "hitpaw", "hyper", "sdr", "hdr", "timbre", "moss", "sam3", "scail", "sheet", "rope", "sfx", "music", "mp3", "opus", "webm", "textgenerate", "record", "imagetosvg")
CLOUD_HINTS = ("API", "api", "Gemini", "OpenAI", "Sora", "Flux", "Ideogram", "Runway",
               "Luma", "Pika", "Kling", "Recraft", "Veo", "BFL", "Midjourney")
TRAD_HINTS = ("Adjust", "Center", "Convert", "Resize", "Tile", "Stitch", "Flip",
              "RGB", "HSV", "Audio", "Image", "Mask", "Text", "Color", "Blur", "Crop", "Scale", "Pad",
              "Invert", "Batch", "Empty", "Solid", "Levels", "Gamma", "Quantize",
              "Posterize", "Contrast", "Brightness", "Saturation", "Sharpen", "Rotate",
              "Transpose", "Composite", "Blend", "Stitch", "Preview", "Save", "Load")


def _nodes_of(mod) -> set:
    return set(getattr(mod, "NODES", {}) or {})


def _classify(name: str) -> str:
    # ① ComfyUI v3 云端 API 节点统一以 Node 结尾（comfy_api_nodes/*）
    if name.endswith("Node") and not name.startswith(("Image", "Mask", "Batch", "Empty")):
        return "needs_cloud"
    # ② 厂商前缀/API 字样 ⇒ 云端（Bria/ByteDance/ElevenLabs/Fish/Grok/HappyHorse…）
    _VENDORS = ("Bria", "ByteDance", "ElevenLabs", "FishAudio", "Fish", "Grok", "Kling", "Luma", "Minimax", "Ideogram", "Recraft", "Veo", "Sora", "Pika", "Runway", "Mage", "Flux", "ComfyCloud", "OpenAI", "Gemini", "HappyHorse", "Beeble", "Tripo", "Meshy", "Rodin", "StabilityStable", "Stability", "Kandinsky", "WanImage", "WanVideo", "QwenImage", "Qwen", "MiniMax", "Suno", "Udio", "Krea", "Topaz", "BFL", "PiAPI", "GrokImage", "GrokVideo")
    if any(name.startswith(x) or ("Api" in name) for x in _VENDORS):
        return "needs_cloud"
    # ③ 3D/几何面：本机没有几何管线，归 unknown（不算"能补"）
    _GEOM = ("Mesh", "Voxel", "Texture", "Bone", "Rig", "Skeleton", "Animate3D", "UV")
    if any(x in name for x in _GEOM):
        return "unknown"
    # ④ 模型面（采样/加载/VAE/条件/合并）
    if any(h.lower() in name.lower() for h in MODEL_HINTS):
        return "needs_model"
    # ⑤ 云端关键字兜底
    if any(h in name for h in CLOUD_HINTS):
        return "needs_cloud"
    if any(h in name for h in TRAD_HINTS):
        return "traditional"
    return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="state/comfy-parity.json")
    args = ap.parse_args()

    from gbt_allinone.tools import comfy_native as CN

    ours = _nodes_of(CN)
    if os.path.isfile(REAL_SNAP):
        ref = json.load(open(REAL_SNAP, encoding="utf-8"))
        names = set(ref.keys()) if isinstance(ref, dict) else set(ref.get("nodes") or [])
        source = "秋叶版 /object_info 真快照（%s）" % os.path.basename(REAL_SNAP)
    elif os.path.isfile(CORE_REF):
        ref = json.load(open(CORE_REF, encoding="utf-8"))
        names = set(ref.get("nodes") or [])
        source = "ComfyUI 核心面（%s）—— 非秋叶整包，插件面未含" % ref.get("source", "")
    else:
        print("没有参照快照：既无 %s 也无 %s" % (REAL_SNAP, CORE_REF))
        return 2

    covered = sorted(ours & names)
    missing = sorted(names - ours)
    gaps = {"traditional": [], "needs_model": [], "needs_cloud": [], "unknown": []}
    for n in missing:
        gaps[_classify(n)].append(n)

    total = len(names)
    parity = len(covered) / total if total else 0.0
    out = {
        "reference_source": source,
        "reference_total": total,
        "ours_total": len(ours),
        "covered": len(covered),
        "parity": round(parity, 4),
        "covered_names": covered,
        "gaps": {k: {"count": len(v), "sample": v[:12]} for k, v in gaps.items()},
        "note": ("traditional 面可用纯 CPU 继续长；needs_model 面本机无 CUDA；"
                 "要真实一比一请把秋叶版 /object_info 放到 state/comfyui_object_info.json"),
    }
    dst = args.json if os.path.isabs(args.json) else os.path.join(ROOT, args.json)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("== GBT天真 ↔ 秋叶版 一比一（comfy-parity）==")
    print("参照：", source)
    print("参照节点 %d · 我们 %d · 同名覆盖 %d = **%.1f%%**"
          % (total, len(ours), len(covered), parity * 100))
    print("缺口按类：", {k: len(v) for k, v in gaps.items()})
    print("可补（traditional 前 12）：", gaps["traditional"][:12])
    print("落盘：", dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
