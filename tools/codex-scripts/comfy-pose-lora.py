#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ComfyUI「OpenPose + LoRA」组合技 · 闭环客户端（只用标准库）

这是主人 2026-09-23 要的那条链的**后半截**：
    骨架图 + 逼真底模 + ControlNet(OpenPose) + LoRA  →  一张真图（逐字节落盘）

## 五步一步不跳（每步都有读数）
 ① 探活   GET /system_stats                          服务在不在、CPU 还是 GPU
 ② 认件   GET /object_info/<节点>                     **问服务**盘上有哪些 ckpt / controlnet / lora / 图
 ③ 提工作流 POST /prompt                             拿 prompt_id
 ④ 等结果 GET /history/<id>                          轮询到出现为止（CPU 慢，默认等 40 分钟）
 ⑤ 取图   GET /view?filename=…                       **逐字节**写 PNG（不当文本读写）

## 两条纪律（写在代码里，不靠记性）
 ① **模型名一律问服务**。写死文件名的话，换模型时不会报错，只会静默用错东西。
 ② **节点入参按 `/object_info` 过滤**。ComfyUI 各版本 ControlNet/LoRA 节点入参有增删
    （例如 `ControlNetApplyAdvanced` 有没有 `vae`），多传一个不存在的键会被直接拒。
    漏传必填键也要**当场报出来**，不许让它变成一条看不懂的报错。

## 用法
  python tools/codex-scripts/comfy-pose-lora.py --probe
  python tools/codex-scripts/comfy-pose-lora.py --list
  python tools/codex-scripts/comfy-pose-lora.py --pose gbt-pose.png \
      --prompt "photo of a young woman standing, full body, cinematic light" \
      --lora lcm-lora-sdv1-5.safetensors --steps 8 --cfg 2.0 --sampler lcm
  python tools/codex-scripts/comfy-pose-lora.py --pose gbt-pose.png --no-lora   # 只验 ControlNet
  python tools/codex-scripts/comfy-pose-lora.py --pose gbt-pose.png --no-controlnet  # 只验 LoRA

退出码：0 出图 · 2 服务没起 · 3 提交前自查失败/被拒 · 4 等超时 · 5 没取到图
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE_DEFAULT = "http://127.0.0.1:8188"
HERE = Path(__file__).resolve().parent


def get_json(base, path, timeout=25):
    with urllib.request.urlopen(base + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def post_json(base, path, obj, timeout=90):
    req = urllib.request.Request(base + path, data=json.dumps(obj).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


class Spec:
    """节点入参白名单：从服务自己要，避免版本差异把入参写错。"""

    def __init__(self, base):
        self.base = base
        self.cache = {}

    def inputs_of(self, cls):
        if cls not in self.cache:
            info = get_json(self.base, "/object_info/" + urllib.parse.quote(cls))
            node = info.get(cls) or {}
            req = ((node.get("input") or {}).get("required") or {})
            opt = ((node.get("input") or {}).get("optional") or {})
            self.cache[cls] = (req, opt)
        return self.cache[cls]

    def choices(self, cls, key):
        req, opt = self.inputs_of(cls)
        v = req.get(key) or opt.get(key)
        if not v:
            return []
        first = v[0]
        return list(first) if isinstance(first, list) else []

    def mk(self, cls, **kw):
        """按服务声明的入参过滤；返回 (inputs, 被丢掉的键, 缺的必填键)"""
        req, opt = self.inputs_of(cls)
        allowed = set(req) | set(opt)
        kept = {k: v for k, v in kw.items() if k in allowed}
        dropped = sorted(k for k in kw if k not in allowed)
        miss = sorted(k for k in req if k not in kept)
        return kept, dropped, miss


def build(spec, ckpt, pose, prompt, negative, steps, w, h, seed, cfg, sampler, scheduler,
          lora, lora_strength, cn_name, cn_strength, cn_start, cn_end, prefix, notes):
    g = {}
    g["4"] = {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}}
    model_src, clip_src = ["4", 0], ["4", 1]

    if lora:
        ins, drop, miss = spec.mk("LoraLoader", lora_name=lora,
                                  strength_model=lora_strength, strength_clip=lora_strength,
                                  model=model_src, clip=clip_src)
        if miss:
            raise SystemExit(json.dumps({"ok": False, "status": "node_input_missing",
                                         "node": "LoraLoader", "missing": miss}, ensure_ascii=False))
        g["13"] = {"class_type": "LoraLoader", "inputs": ins}
        notes.append({"leg": "lora", "file": lora, "strength": lora_strength, "dropped_inputs": drop})
        model_src, clip_src = ["13", 0], ["13", 1]

    g["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": clip_src}}
    g["7"] = {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": clip_src}}

    pos, neg = ["6", 0], ["7", 0]
    if cn_name:
        g["10"] = {"class_type": "ControlNetLoader", "inputs": {"control_net_name": cn_name}}
        g["11"] = {"class_type": "LoadImage", "inputs": {"image": pose}}
        kw = dict(positive=pos, negative=neg, control_net=["10", 0], image=["11", 0],
                  strength=cn_strength, start_percent=cn_start, end_percent=cn_end)
        req, opt = spec.inputs_of("ControlNetApplyAdvanced")
        if "vae" in (set(req) | set(opt)):
            kw["vae"] = ["4", 2]          # 有些版本/union 模型吃 vae，声明了才给
        ins, drop, miss = spec.mk("ControlNetApplyAdvanced", **kw)
        if miss:
            raise SystemExit(json.dumps({"ok": False, "status": "node_input_missing",
                                         "node": "ControlNetApplyAdvanced", "missing": miss},
                                        ensure_ascii=False))
        g["12"] = {"class_type": "ControlNetApplyAdvanced", "inputs": ins}
        notes.append({"leg": "controlnet", "file": cn_name, "pose": pose,
                      "strength": cn_strength, "start": cn_start, "end": cn_end,
                      "dropped_inputs": drop})
        pos, neg = ["12", 0], ["12", 1]

    ins, drop, miss = spec.mk("KSampler", seed=seed, steps=steps, cfg=cfg,
                              sampler_name=sampler, scheduler=scheduler, denoise=1.0,
                              model=model_src, positive=pos, negative=neg, latent_image=["5", 0])
    if miss:
        raise SystemExit(json.dumps({"ok": False, "status": "node_input_missing",
                                     "node": "KSampler", "missing": miss}, ensure_ascii=False))
    g["3"] = {"class_type": "KSampler", "inputs": ins}
    g["5"] = {"class_type": "EmptyLatentImage",
              "inputs": {"width": w, "height": h, "batch_size": 1}}
    g["8"] = {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}}
    g["9"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["8", 0]}}
    return g


def main() -> int:
    ap = argparse.ArgumentParser(description="ComfyUI OpenPose+LoRA 闭环客户端")
    ap.add_argument("--base", default=BASE_DEFAULT)
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--list", action="store_true", help="只列服务上有哪些 ckpt/controlnet/lora/图")
    ap.add_argument("--prompt", default="")
    ap.add_argument("--negative", default=("lowres, blurry, watermark, text, extra fingers, "
                                           "deformed hands, cartoon, anime, 3d render, painting"))
    ap.add_argument("--pose", default="", help="ComfyUI input/ 里的骨架图文件名")
    ap.add_argument("--auto-pose", default="", help="骨架图不在就先按这个预设生成（stand/tpose/walk/sit）")
    ap.add_argument("--lora", default="", help="LoRA 文件名（问服务要名单）")
    ap.add_argument("--lora-strength", type=float, default=1.0)
    ap.add_argument("--no-lora", action="store_true")
    ap.add_argument("--no-controlnet", action="store_true")
    ap.add_argument("--cn-strength", type=float, default=1.0)
    ap.add_argument("--cn-start", type=float, default=0.0)
    ap.add_argument("--cn-end", type=float, default=1.0)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--cfg", type=float, default=7.0)
    ap.add_argument("--sampler", default="euler")
    ap.add_argument("--scheduler", default="normal")
    ap.add_argument("--size", default="512x512")
    ap.add_argument("--seed", type=int, default=-1)
    ap.add_argument("--ckpt", default="")
    ap.add_argument("--out", default="render/comfy-pose")
    ap.add_argument("--timeout", type=float, default=2400.0)
    a = ap.parse_args()

    try:
        st = get_json(a.base, "/system_stats", timeout=8)
    except Exception as e:                                                # noqa: BLE001
        print(json.dumps({"ok": False, "status": "server_down", "base": a.base,
                          "error": "%s: %s" % (type(e).__name__, str(e)[:120]),
                          "hint": "先起服务：pwsh -File tools/codex-scripts/comfy-serve.ps1"},
                         ensure_ascii=False, indent=1))
        return 2
    spec = Spec(a.base)
    print("[① 探活] 通 · 版本 %s · 设备 %s"
          % ((st.get("system") or {}).get("comfyui_version"),
             ", ".join(str(d.get("name")) for d in (st.get("devices") or [])) or "(未报)"))

    ckpts = spec.choices("CheckpointLoaderSimple", "ckpt_name")
    cns = spec.choices("ControlNetLoader", "control_net_name")
    loras = spec.choices("LoraLoader", "lora_name")
    imgs = spec.choices("LoadImage", "image")
    if a.list or a.probe:
        print(json.dumps({"ok": True, "status": "up", "checkpoints": ckpts,
                          "controlnets": cns, "loras": loras, "input_images": imgs},
                         ensure_ascii=False, indent=1))
        return 0

    if not ckpts:
        print(json.dumps({"ok": False, "status": "no_checkpoint",
                          "hint": "放进 ~/ComfyUI/models/checkpoints/"}, ensure_ascii=False))
        return 3

    # ② 认件：默认挑"逼真底模"（Realistic），挑不到才退回第一个，并**把选择念出来**
    ckpt = a.ckpt
    if not ckpt:
        real = [n for n in ckpts if "realistic" in n.lower()]
        ckpt = (real or ckpts)[0]
    print("[② 认件] ckpt=%s（盘上 %d 个）" % (ckpt, len(ckpts)))
    print("        controlnet=%d 个 · lora=%d 个 · input 图=%d 张" % (len(cns), len(loras), len(imgs)))

    if not a.prompt:
        print(json.dumps({"ok": False, "status": "no_prompt"}, ensure_ascii=False))
        return 3

    # 骨架图：给的优先；不在就按需生成（生成器与客户端分开，便于单测）
    pose = a.pose
    if a.auto_pose:
        gen = HERE / "openpose-skeleton.py"
        dst = Path(os.environ.get("USERPROFILE", "~")) / "ComfyUI" / "input" / (a.auto_pose + ".png")
        p = subprocess.run([sys.executable, str(gen), "--pose", a.auto_pose, "--out", str(dst)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print("[②b 生成骨架] %s" % (p.stdout or "").strip().splitlines()[-1:])
        if p.returncode != 0:
            print(json.dumps({"ok": False, "status": "pose_gen_failed", "rc": p.returncode,
                              "stderr": (p.stderr or "")[:300]}, ensure_ascii=False))
            return 3
        pose = dst.name

    cn = "" if a.no_controlnet else (cns[0] if cns else "")
    lora = "" if a.no_lora else (a.lora or (loras[0] if loras else ""))
    if not a.no_controlnet and not cn:
        print(json.dumps({"ok": False, "status": "no_controlnet",
                          "hint": "models/controlnet/ 里没有 ControlNet"},
                         ensure_ascii=False))
        return 3
    if cn and not pose:
        print(json.dumps({"ok": False, "status": "no_pose",
                          "hint": "ControlNet 要 --pose <文件名> 或 --auto-pose <预设>"},
                         ensure_ascii=False))
        return 3
    if pose and pose not in imgs:
        print(json.dumps({"ok": False, "status": "pose_not_on_server", "pose": pose,
                          "available": imgs,
                          "hint": "骨架图要放进 ~/ComfyUI/input/"}, ensure_ascii=False))
        return 3

    m = re.match(r"^(\d+)x(\d+)$", a.size.strip())
    w, h = (int(m.group(1)), int(m.group(2))) if m else (512, 512)
    seed = a.seed if a.seed >= 0 else int(time.time()) % 2_000_000_000
    notes = []
    wf = build(spec, ckpt, pose, a.prompt, a.negative, a.steps, w, h, seed, a.cfg,
               a.sampler, a.scheduler, lora, a.lora_strength, cn, a.cn_strength,
               a.cn_start, a.cn_end, "gbt_pose_lora", notes)
    print("[③ 提交] %dx%d steps=%d cfg=%s sampler=%s seed=%d · 腿：%s"
          % (w, h, a.steps, a.cfg, a.sampler, seed,
             " + ".join([n["leg"] for n in notes]) or "(无附加腿)"))

    t0 = time.time()
    try:
        res = post_json(a.base, "/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print(json.dumps({"ok": False, "status": "rejected", "http": e.code,
                          "body": body[:1200]}, ensure_ascii=False, indent=1))
        return 3
    pid = res.get("prompt_id")
    print("[③ 提交] prompt_id=%s" % pid)

    hist, waited, gap = None, 0.0, 2.0
    while waited < a.timeout:
        time.sleep(gap)
        waited += gap
        gap = min(gap * 1.15, 8.0)
        try:
            h = get_json(a.base, "/history/" + urllib.parse.quote(pid), timeout=20)
        except Exception:                                                 # noqa: BLE001
            continue
        if pid in h and h[pid]:
            hist = h[pid]
            break
        if int(waited) % 30 < 8:
            print("    …等了 %.0fs（CPU 出图慢是正常的）" % waited)
    if hist is None:
        print(json.dumps({"ok": False, "status": "timeout", "waited_s": round(waited, 1),
                          "prompt_id": pid}, ensure_ascii=False, indent=1))
        return 4

    status = hist.get("status") or {}
    if status.get("status_str") == "error" or status.get("completed") is False:
        print(json.dumps({"ok": False, "status": "node_error", "prompt_id": pid,
                          "detail": status}, ensure_ascii=False, indent=1)[:1800])
        return 5

    imgs_out = []
    for _nid, out in (hist.get("outputs") or {}).items():
        for im in (out.get("images") or []):
            imgs_out.append(im)
    if not imgs_out:
        print(json.dumps({"ok": False, "status": "no_image", "prompt_id": pid,
                          "outputs": list((hist.get("outputs") or {}).keys())},
                         ensure_ascii=False, indent=1))
        return 5

    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    saved = []
    for im in imgs_out:
        q = urllib.parse.urlencode({"filename": im.get("filename", ""),
                                    "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        with urllib.request.urlopen(a.base + "/view?" + q, timeout=180) as r:
            blob = r.read()
        ext = Path(im.get("filename", "out.png")).suffix or ".png"
        tag = "lora" if (lora and cn) else ("cn" if cn else ("lora" if lora else "base"))
        dst = outdir / ("%d-%s-%s%s" % (int(t0), tag, re.sub(r"[^\w\-]+", "_", a.prompt[:20]) or "img", ext))
        dst.write_bytes(blob)
        saved.append({"file": str(dst), "bytes": len(blob),
                      "sha256_head": hashlib.sha256(blob).hexdigest()[:16]})

    print(json.dumps({"ok": True, "status": "done", "prompt_id": pid,
                      "elapsed_s": round(time.time() - t0, 1), "seed": seed,
                      "size": [w, h], "steps": a.steps, "cfg": a.cfg,
                      "sampler": a.sampler, "scheduler": a.scheduler, "ckpt": ckpt,
                      "legs": notes, "images": saved,
                      "_口径": ("CPU 路线，耗时是真读数。**出图 ≠ 姿势对 ≠ 审美合格**："
                              "姿势是否咬合要另用骨架叠图比对，审美另走 gbt-aesthetic")},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
