"""本机真出图：驱动 ComfyUI 的 API 出一张真图（CPU）。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要它
主人 2026-09-25 的标准是「**所有的东西都要跑起来了才算合格**」。
图像面此前一直是「管道通了、端点没接」——这个脚本让**本机真的出一张图**：
用 ComfyUI（已装）+ 本机真 SD1.5 权重 + LCM-LoRA（4~6 步，CPU 上快得多）。

## 口径
- 输出**必须是一张真图**：解析出字节、验 PNG 签名、报出尺寸与耗时。
- 出不来就如实报**卡在哪一步**（ComfyUI 没起 / 节点报错 / 超时），**不许**回占位图。
- 这不是"顶尖质量"：CPU + 6 步 LCM 只是**跑得通**的证据；质量修饰是后面的事。

用法：
  python tools/codex-scripts/local-comfy-image.py once  [--steps 6] [--size 512] [--out .scratch/img]
  python tools/codex-scripts/local-comfy-image.py selftest
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HOST = os.environ.get("COMFY_HOST", "http://127.0.0.1:8188")
UA = "gbt-comfy-probe/1.0 (+local)"
CKPT = "v1-5-pruned-emaonly-fp16.safetensors"
LORA = "lcm-lora-sdv1-5.safetensors"


def http(url: str, method: str = "GET", payload=None, timeout: float = 60.0):
    data = None
    headers = {"user-agent": UA}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["content-type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return {"ok": True, "status": r.status, "bytes": raw}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "bytes": e.read()}
    except Exception as e:                                   # noqa: BLE001
        return {"ok": False, "err": "%s: %s" % (type(e).__name__, e)}


def build_workflow(prompt: str, negative: str, size: int, steps: int, seed: int, prefix: str) -> dict:
    """ComfyUI 的节点图（txt2img + LCM-LoRA）。**纯函数**，好上控制。"""
    return {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "10": {"class_type": "LoraLoader", "inputs": {"model": ["4", 0], "clip": ["4", 1], "lora_name": LORA,
                                                      "strength_model": 1.0, "strength_clip": 1.0}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": size, "height": size, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["10", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["10", 1]}},
        "3": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": steps, "cfg": 1.5, "sampler_name": "lcm",
                                                   "scheduler": "sgm_uniform", "denoise": 1.0,
                                                   "model": ["10", 0], "positive": ["6", 0], "negative": ["7", 0],
                                                   "latent_image": ["5", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["8", 0]}},
    }


def is_png(b: bytes) -> bool:
    """PNG 签名（纯函数）。只认字节，不认文件名。"""
    return len(b) >= 8 and b[:8] == b"\x89PNG\r\n\x1a\n"


def png_size(b: bytes) -> tuple:
    """从 IHDR 读宽高（纯函数）；读不到返回 (None, None)。PNG: 宽高在偏移 16/20，大端 4 字节。"""
    if not is_png(b) or len(b) < 24:
        return (None, None)
    try:
        w = int.from_bytes(b[16:20], "big")
        h = int.from_bytes(b[20:24], "big")
        return (w, h)
    except Exception:                                        # noqa: BLE001
        return (None, None)


def once(prompt: str, negative: str, size: int, steps: int, outdir: Path, timeout: float) -> int:
    st = http(HOST + "/system_stats", timeout=10)
    if not st["ok"]:
        print("ComfyUI 未就绪（未读到）：%s" % st.get("err"))
        print("  起法：cd C:\\Users\\ADMIN\\ComfyUI; .\\.venv\\Scripts\\python.exe main.py --cpu --port 8188")
        return 2
    dev = json.loads(st["bytes"].decode("utf-8", "replace")).get("devices") or [{}]
    print("ComfyUI 就绪 · 设备=%s" % dev[0].get("name"))
    wf = build_workflow(prompt, negative, size, steps, 12345, "gbt_probe")
    t0 = time.time()
    r = http(HOST + "/prompt", method="POST", payload={"prompt": wf, "client_id": "gbt-probe"}, timeout=30)
    if not r["ok"]:
        print("提交失败（未读到）：HTTP %s %s" % (r.get("status"), r["bytes"][:200]))
        return 1
    pid = json.loads(r["bytes"].decode("utf-8", "replace")).get("prompt_id")
    print("已提交 prompt_id=%s · 生成中（CPU，耐心等）…" % pid)
    img = None
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(3)
        h = http(HOST + "/history/" + str(pid), timeout=20)
        if not h["ok"]:
            continue
        hist = json.loads(h["bytes"].decode("utf-8", "replace"))
        entry = hist.get(pid)
        if not entry:
            continue
        outs = (entry.get("outputs") or {}).get("9", {}).get("images") or []
        if outs:
            img = outs[0]
            break
    if not img:
        print("超时（%.0fs）未拿到图 —— 如实报未读到，不编" % timeout)
        return 1
    q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img.get("subfolder", ""), "type": img.get("type", "output")})
    v = http(HOST + "/view?" + q, timeout=60)
    if not v["ok"]:
        print("取图失败：HTTP %s" % v.get("status"))
        return 1
    data = v["bytes"]
    w, h2 = png_size(data)
    outdir.mkdir(parents=True, exist_ok=True)
    dest = outdir / ("comfy-" + img["filename"])
    dest.write_bytes(data)
    print("✅ 真出图：%s" % dest)
    print("   字节=%d · PNG=%s · 尺寸=%sx%s · 耗时=%.1fs · 步数=%d · 尺寸参数=%d"
          % (len(data), is_png(data), w, h2, time.time() - t0, steps, size))
    return 0


def selftest() -> int:
    ok = 0
    total = 0
    fails = []

    def ck(name, cond, detail=""):
        nonlocal ok, total
        total += 1
        if cond:
            ok += 1
        else:
            fails.append("%s :: %s" % (name, detail))

    wf = build_workflow("a", "b", 512, 6, 1, "p")
    ck("正控·节点图有 8 个节点且含 KSampler/SaveImage", len(wf) == 8 and wf["3"]["class_type"] == "KSampler" and wf["9"]["class_type"] == "SaveImage", str(sorted(wf)))
    ck("正控·参数进了图里（步数/尺寸/提示词）", wf["3"]["inputs"]["steps"] == 6 and wf["5"]["inputs"]["width"] == 512 and wf["6"]["inputs"]["text"] == "a", "params")
    ck("正控·LCM 采样器与 LoRA 接在模型链上", wf["3"]["inputs"]["sampler_name"] == "lcm" and wf["10"]["inputs"]["lora_name"].endswith(".safetensors"), "lcm")
    ck("正控·KSampler 的 model 来自 LoRA 节点（不是直连 checkpoint）", wf["3"]["inputs"]["model"] == ["10", 0], str(wf["3"]["inputs"]["model"]))

    ck("正控·真 PNG 签名认得出", is_png(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32), "png")
    ck("负控·空字节/JPEG 不算 PNG", not is_png(b"") and not is_png(b"\xff\xd8\xff\xe0" + b"\x00" * 16), "png-negative")
    ck("负控·尺寸读不出来就返回 None（不许编宽高）", png_size(b"not a png") == (None, None), str(png_size(b"not a png")))

    print("local-comfy-image selftest：%d/%d" % (ok, total))
    for f in fails:
        print("  ✗ " + f)
    return 0 if ok == total else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="本机真出图（驱动 ComfyUI · CPU）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("once")
    o.add_argument("--prompt", default="a potato wearing sunglasses, studio light, high quality, sharp focus")
    o.add_argument("--negative", default="blurry, low quality, watermark, text")
    o.add_argument("--steps", type=int, default=6)
    o.add_argument("--size", type=int, default=512)
    o.add_argument("--timeout", type=float, default=900.0)
    o.add_argument("--out", default=str(ROOT / ".scratch" / "img"))
    sub.add_parser("selftest")
    a = ap.parse_args()
    if a.cmd == "once":
        return once(a.prompt, a.negative, a.size, a.steps, Path(a.out), a.timeout)
    if a.cmd == "selftest":
        return selftest()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
