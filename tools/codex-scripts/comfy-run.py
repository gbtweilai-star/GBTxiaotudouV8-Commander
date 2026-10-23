# -*- coding: utf-8 -*-
"""ComfyUI 出图闭环 · 客户端（只用标准库，不引入任何新依赖）

闭环的五步（一步都不许跳，每步都有读数）：
    ① 探活     GET  /system_stats                 → 服务在不在、走的是 CPU 还是 GPU
    ② 认模型   GET  /object_info/CheckpointLoaderSimple
                                                  → **问服务**盘上有哪些 ckpt，不写死文件名
    ③ 提工作流 POST /prompt                        → 拿 prompt_id
    ④ 等结果   GET  /history/<prompt_id>           → 轮询到它出现为止（带超时）
    ⑤ 取图落盘 GET  /view?filename=…               → **逐字节**写 PNG（不当文本读写）

用法：
    python tools/codex-scripts/comfy-run.py --probe
    python tools/codex-scripts/comfy-run.py --prompt "a red apple on a table" --steps 20
    python tools/codex-scripts/comfy-run.py --prompt "…" --size 512x512 --seed 42 --out render/comfy

退出码（**"没起来"与"出图失败"必须分开报**，不许都写"失败"）：
    0=出了图 · 2=服务没起 · 3=提交被拒 · 4=等超时 · 5=没拿到图
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE_DEFAULT = "http://127.0.0.1:8188"


def get_json(base, path, timeout=20):
    with urllib.request.urlopen(base + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def post_json(base, path, obj, timeout=60):
    data = json.dumps(obj).encode("utf-8")
    req = urllib.request.Request(base + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def pick_ckpt(base):
    """**问服务**要 ckpt 名单（不写死文件名 —— 写死了换模型就静默失效）。"""
    info = get_json(base, "/object_info/CheckpointLoaderSimple")
    node = info.get("CheckpointLoaderSimple") or {}
    names = (((node.get("input") or {}).get("required") or {}).get("ckpt_name") or [[]])[0]
    if not isinstance(names, list) or not names:
        return None, []
    prefer = [n for n in names if "fp16" in n.lower()] or names
    return prefer[0], names


def build_workflow(ckpt, prompt, negative, steps, w, h, seed, cfg, sampler, prefix):
    return {
        "3": {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": steps, "cfg": cfg, "sampler_name": sampler,
            "scheduler": "normal", "denoise": 1.0,
            "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0],
            "latent_image": ["5", 0]}},
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "5": {"class_type": "EmptyLatentImage",
              "inputs": {"width": w, "height": h, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": prefix, "images": ["8", 0]}},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="ComfyUI 出图闭环客户端")
    ap.add_argument("--base", default=BASE_DEFAULT)
    ap.add_argument("--probe", action="store_true", help="只看服务状态，不出图")
    ap.add_argument("--prompt", default="")
    ap.add_argument("--negative", default="lowres, blurry, watermark, text, extra fingers")
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--size", default="512x512")
    ap.add_argument("--seed", type=int, default=-1)
    ap.add_argument("--cfg", type=float, default=7.0)
    ap.add_argument("--sampler", default="euler")
    ap.add_argument("--ckpt", default="")
    ap.add_argument("--out", default="render/comfy")
    ap.add_argument("--timeout", type=float, default=1800.0, help="等图的秒数上限（CPU 慢，默认 30 分钟）")
    a = ap.parse_args()

    # ① 探活 —— 服务没起就是**服务没起**，不是"出图失败"
    try:
        st = get_json(a.base, "/system_stats", timeout=8)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "status": "server_down", "base": a.base,
                          "error": "%s: %s" % (type(e).__name__, str(e)[:120]),
                          "hint": "先起服务：pwsh -File tools/codex-scripts/comfy-serve.ps1"},
                         ensure_ascii=False, indent=1))
        return 2
    dev = ", ".join(str(d.get("name")) for d in (st.get("devices") or []))
    print("[① 探活] 通 · 版本 %s · 设备 %s"
          % ((st.get("system") or {}).get("comfyui_version"), dev or "(未报)"))
    if a.probe:
        print(json.dumps({"ok": True, "status": "up", "devices": st.get("devices"),
                          "system": st.get("system")}, ensure_ascii=False, indent=1))
        return 0

    # ② 认模型
    ckpt = a.ckpt
    if not ckpt:
        ckpt, names = pick_ckpt(a.base)
        print("[② 认模型] 服务报盘上 %d 个 ckpt，选：%s" % (len(names), ckpt))
        if not ckpt:
            print(json.dumps({"ok": False, "status": "no_checkpoint",
                              "hint": "把模型放进 ~/ComfyUI/models/checkpoints/"},
                             ensure_ascii=False, indent=1))
            return 3
    if not a.prompt:
        print(json.dumps({"ok": False, "status": "no_prompt", "hint": "要 --prompt"},
                         ensure_ascii=False, indent=1))
        return 3

    m = re.match(r"^(\d+)x(\d+)$", a.size.strip())
    w, h = (int(m.group(1)), int(m.group(2))) if m else (512, 512)
    seed = a.seed if a.seed >= 0 else int(time.time()) % 2_000_000_000
    wf = build_workflow(ckpt, a.prompt, a.negative, a.steps, w, h, seed, a.cfg, a.sampler, "gbt")
    print("[③ 提交] %dx%d · steps=%d · cfg=%s · seed=%d · sampler=%s"
          % (w, h, a.steps, a.cfg, seed, a.sampler))

    t0 = time.time()
    try:
        res = post_json(a.base, "/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:600]
        print(json.dumps({"ok": False, "status": "rejected", "http": e.code, "body": body},
                         ensure_ascii=False, indent=1))
        return 3
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"ok": False, "status": "submit_error",
                          "error": "%s: %s" % (type(e).__name__, str(e)[:160])},
                         ensure_ascii=False, indent=1))
        return 3
    pid = res.get("prompt_id")
    print("[③ 提交] prompt_id=%s" % pid)

    # ④ 等结果（CPU 慢，轮询间隔渐进）
    hist = None
    waited = 0.0
    gap = 2.0
    while waited < a.timeout:
        time.sleep(gap)
        waited += gap
        gap = min(gap * 1.15, 6.0)
        try:
            h = get_json(a.base, "/history/" + urllib.parse.quote(pid), timeout=15)
        except Exception:  # noqa: BLE001
            continue
        if pid in h and h[pid]:
            hist = h[pid]
            break
        if int(waited) % 15 < 3:
            print("    …等了 %.0fs（CPU 出图慢是正常的）" % waited)
    if hist is None:
        print(json.dumps({"ok": False, "status": "timeout", "waited_s": round(waited, 1),
                          "prompt_id": pid, "hint": "CPU 出图可能要几分钟；确认服务还在跑"},
                         ensure_ascii=False, indent=1))
        return 4

    status = (hist.get("status") or {})
    if status.get("status_str") == "error" or status.get("completed") is False:
        print(json.dumps({"ok": False, "status": "node_error", "prompt_id": pid,
                          "detail": status}, ensure_ascii=False, indent=1)[:1500])
        return 5

    # ⑤ 取图落盘（**逐字节**）
    imgs = []
    for _nid, out in (hist.get("outputs") or {}).items():
        for im in (out.get("images") or []):
            imgs.append(im)
    if not imgs:
        print(json.dumps({"ok": False, "status": "no_image", "prompt_id": pid,
                          "outputs": list((hist.get("outputs") or {}).keys())},
                         ensure_ascii=False, indent=1))
        return 5
    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    saved = []
    for im in imgs:
        q = urllib.parse.urlencode({"filename": im.get("filename", ""),
                                    "subfolder": im.get("subfolder", ""),
                                    "type": im.get("type", "output")})
        with urllib.request.urlopen(a.base + "/view?" + q, timeout=120) as r:
            blob = r.read()
        ext = Path(im.get("filename", "out.png")).suffix or ".png"
        dst = outdir / ("%d-%s%s" % (int(t0), re.sub(r"[^\w\-]+", "_", a.prompt[:24]) or "img", ext))
        dst.write_bytes(blob)
        saved.append({"file": str(dst), "bytes": len(blob),
                      "sha256_head": __import__("hashlib").sha256(blob).hexdigest()[:16]})

    print(json.dumps({"ok": True, "status": "done", "prompt_id": pid,
                      "elapsed_s": round(time.time() - t0, 1), "seed": seed,
                      "size": [w, h], "steps": a.steps, "ckpt": ckpt,
                      "images": saved,
                      "_口径": "CPU 路线；耗时是真读数。出图不等于审美合格 —— 审美另走 gbt-aesthetic 的截图自证"},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
