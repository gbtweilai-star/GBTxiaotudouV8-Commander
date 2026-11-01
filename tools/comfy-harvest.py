# -*- coding: utf-8 -*-
"""秋叶版取食器（comfy-harvest）：**只取我们缺的、且用得上的**。

主人口径（2026-11-01）：「秋叶版机器跑一次，这一步不需要直接吞噬我们需要的权重即可，
没用且我们有的不需要」。

## 三条取食规则（先筛后取，绝不整包吞）

| 类 | 判据 | 处置 |
|---|---|---|
| **已有** | 我们的 `NODES` 里同名已实现 | ❌ 不要（重复） |
| **可用缺口** | 我们没有 + 纯 CPU 传统算子（PIL 可长） | ✅ **取**（进待实现清单） |
| **现在用不上** | 采样/加载/VAE/条件/ControlNet（要 GPU 与权重） | ❌ 不取（本机无 CUDA） |
| 云端 | 需要 key 的 API 节点 | ❌ 不取 |

**权重不吞**：模型文件（checkpoints/lora/vae）一个都不下 —— 本机跑不动，吞了只是占盘。
我们取的是**契约（节点 schema）**，好让她的 workflow.json 能用 ComfyUI 节点名。

## 用法

```powershell
# ① 在秋叶版机器上采一次（只读 GET，一条命令）
powershell -NoProfile -ExecutionPolicy Bypass -File tools\\collect-object-info.ps1

# ② 回到仓库，只筛我们要的
py -3 -X utf8 tools/comfy-harvest.py
py -3 -X utf8 tools/comfy-harvest.py --top 40     # 多看几条
```

产出 `state/comfy-harvest.json`：`useful`（要补的清单，按族排序）、`have`、`skip_model`、`skip_cloud`。
没有真快照时退到核心面参照，并明确标注（不冒充秋叶整包）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

REAL = os.path.join(ROOT, "state", "comfyui_object_info.json")
CORE = os.path.join(ROOT, "state", "comfyui_ref_nodes.json")

MODEL_HINTS = ("sampler", "checkpoint", "loader", "clip", "vae", "lora", "latent",
               "conditioning", "controlnet", "unet", "model", "attention", "gligen",
               "hypernetwork", "diffusion", "inpaint", "upscale_model", "freeu",
               "style_model", "guider", "sigmas", "noise", "merge", "sampling",
               # 视频/3D/媒体栈：本机没有 av/ffmpeg 与几何管线 ⇒ 归模型面（不制造假缺口）
               "video", "3d", "glb", "splat", "pointcloud", "temporal", "keyframe",
               "wan", "ltxv", "hunyuan", "dancer", "humo", "sound", "encode", "training", "mediapipe", "hidream", "hitpaw", "hyper", "sdr", "hdr", "timbre", "moss", "sam3", "scail", "sheet", "rope", "sfx", "music", "mp3", "opus", "webm", "textgenerate", "record", "imagetosvg")
CLOUD_HINTS = ("API", "Gemini", "OpenAI", "Sora", "Flux", "Ideogram", "Runway",
               "Luma", "Pika", "Kling", "Recraft", "Veo", "BFL", "Midjourney")
TRAD_EXTRA = ("Adjust", "Center", "Convert", "Resize", "Tile", "Stitch", "Flip",
              "RGB", "HSV", "Audio")
TRAD_HINTS = ("Image", "Mask", "Text", "Color", "Blur", "Crop", "Scale", "Pad",
              "Invert", "Batch", "Empty", "Solid", "Levels", "Gamma", "Quantize",
              "Posterize", "Contrast", "Brightness", "Saturation", "Sharpen", "Rotate",
              "Transpose", "Composite", "Blend", "Stitch", "Preview", "Save", "Load")


def classify(name: str) -> str:
    # ① ComfyUI v3 云端 API 节点统一以 Node 结尾（comfy_api_nodes/*）
    if name.endswith("Node") and not name.startswith(("Image", "Mask", "Batch", "Empty")):
        return "skip_cloud"
    # ② 厂商前缀/API 字样 ⇒ 云端（Bria/ByteDance/ElevenLabs/Fish/Grok/HappyHorse…）
    _VENDORS = ("Bria", "ByteDance", "ElevenLabs", "FishAudio", "Fish", "Grok", "Kling", "Luma", "Minimax", "Ideogram", "Recraft", "Veo", "Sora", "Pika", "Runway", "Mage", "Flux", "ComfyCloud", "OpenAI", "Gemini", "HappyHorse", "Beeble", "Tripo", "Meshy", "Rodin", "StabilityStable", "Stability", "Kandinsky", "WanImage", "WanVideo", "QwenImage", "Qwen", "MiniMax", "Suno", "Udio", "Krea", "Topaz", "BFL", "PiAPI", "GrokImage", "GrokVideo")
    if any(name.startswith(x) or ("Api" in name) for x in _VENDORS):
        return "skip_cloud"
    # ③ 3D/几何面：本机没有几何管线，归 unknown（不算"能补"）
    _GEOM = ("Mesh", "Voxel", "Texture", "Bone", "Rig", "Skeleton", "Animate3D", "UV")
    if any(x in name for x in _GEOM):
        return "unknown"
    # ④ 模型面（采样/加载/VAE/条件/合并）
    if any(h.lower() in name.lower() for h in MODEL_HINTS):
        return "skip_model"
    # ⑤ 云端关键字兜底
    if any(h in name for h in CLOUD_HINTS):
        return "skip_cloud"
    if any(h in name for h in TRAD_HINTS + TRAD_EXTRA):
        return "useful"
    return "unknown"


def _load_ref() -> tuple[set, str]:
    if os.path.isfile(REAL):
        d = json.load(open(REAL, encoding="utf-8"))
        names = set(d.keys()) if isinstance(d, dict) else set(d.get("nodes") or [])
        return names, "秋叶版 /object_info 真快照"
    if os.path.isfile(CORE):
        d = json.load(open(CORE, encoding="utf-8"))
        return set(d.get("nodes") or []), "ComfyUI 核心面（非秋叶整包，插件面未含）"
    raise SystemExit("没有参照快照：先跑 tools/collect-object-info.ps1")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--json", default="state/comfy-harvest.json")
    args = ap.parse_args()

    from gbt_allinone.tools import comfy_native as CN

    ours = set(getattr(CN, "NODES", {}) or {})
    ref, source = _load_ref()

    buckets = {"have": [], "useful": [], "skip_model": [], "skip_cloud": [], "unknown": []}
    for n in sorted(ref):
        if n in ours:
            buckets["have"].append(n)
            continue
        buckets[classify(n)].append(n)

    useful = buckets["useful"]
    out = {
        "reference": source,
        "reference_total": len(ref),
        "ours_total": len(ours),
        "have": len(buckets["have"]),
        "useful": len(useful),
        "skip_model": len(buckets["skip_model"]),
        "skip_cloud": len(buckets["skip_cloud"]),
        "unknown": len(buckets["unknown"]),
        "useful_list": useful,
        "skip_model_sample": buckets["skip_model"][:20],
        "skip_cloud_sample": buckets["skip_cloud"][:10],
        "unknown_sample": buckets["unknown"][:20],
        "rule": "已有不要 / 模型与云端不取（无 CUDA 无 key）/ 只取纯 CPU 传统算子的契约；权重一个不下",
    }
    dst = args.json if os.path.isabs(args.json) else os.path.join(ROOT, args.json)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("== 秋叶版取食器（只取缺的、用得上的）==")
    print("参照：", source, "· 共", len(ref), "把")
    print("已有（不取）        %3d" % out["have"])
    print("可用缺口（要取）    %3d" % out["useful"])
    print("模型面（不取）      %3d   ← 本机无 CUDA，权重一个不下" % out["skip_model"])
    print("云端（不取）        %3d   ← 无 key" % out["skip_cloud"])
    print("不认识（先不动）    %3d" % out["unknown"])
    print()
    print("要补的清单（前 %d）：" % args.top)
    for n in useful[: args.top]:
        print("   -", n)
    print("落盘：", dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
