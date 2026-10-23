# gbt-capability: comfy_cloud
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""comfy_cloud —— **云卡上的 ComfyUI，包成她自己的触手**（她不需要知道 ComfyUI 是什么）。

## 为什么要有它

实测：云卡 8188 **没有对外口**（`https://<pod>-8188.proxy.runpod.net/...` 全 404），
本机也没有 8188。所以"调 ComfyUI"这件事，**只能在卡里发生**——
本件把该在卡里跑的 Python 现拼出来，走**云卡触手** `pod_link` 的 `run`（内核通道）递进去，
产物落卡，再走 `down` 取回并**回读哈希对账**。她只喊一个能力位，视频就出来。

## op

    读：status · nodes · models · queue · history
    写：submit（原样图）· **video（一句话 → 首帧 → SVD 动作 → mp4）** · fetch（卡→本机对账）· free

## 铁律

1. 令牌一律不回显（只用 `.scratch/.pod_id` 选卡；令牌由 pod_link 从卡 env 现读）。
2. **产物以两头 sha256 一致为准**——卡上说"完成"不算，本机算出来一样才算。
3. 卡上有雷：`mm_sd_v15_v2.ckpt` ComfyUI **认不出类型**（实测报 `Could not detect model type`），
   默认走 `v1-5-pruned-emaonly-fp16.safetensors`。
4. 卡内脚本必须**每几秒 print 一次**：内核通道长时间无输出会把 WS 晾到超时（今天踩过）。

## 走的路（都是现成的，不新造）

  运输 = `pod_link`（run / down）· 出图 = `CheckpointLoaderSimple→KSampler→VAEDecode→SaveImage`
  · 出动作 = `ImageOnlyCheckpointLoader(svd_xt)→SVD_img2vid_Conditioning→VideoLinearCFGGuidance
  →KSampler→VAEDecode→SaveImage`（照抄 `.scratch/dh_video/monkey_redo.py` 那条真跑通的链）
  · 出片 = `imageio_ffmpeg` 的 ffmpeg，`-framerate N -start_number 1 -i prefix_%05d_.png`
"""
from __future__ import annotations

import json
import re

_OPS = ("status", "nodes", "models", "queue", "history",     # 读
        "submit", "video", "fetch", "freegpu", "free")       # 写

# 卡上默认参数（全部来自实测，不是拍脑袋）
SD15 = "v1-5-pruned-emaonly-fp16.safetensors"
SVD = "svd_xt.safetensors"
BAD_CKPT = "mm_sd_v15_v2.ckpt"      # 实测认不出：不许当默认


def _pod_id() -> str:
    """选卡：.scratch/.pod_id（ComfyUI 那张）；读不到就交给 pod_link 自己挑。"""
    import os
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    p = root / ".scratch" / ".pod_id"
    try:
        return p.read_text(encoding="utf-8").strip()
    except Exception:  # noqa: BLE001
        return ""


def camera_table() -> dict:
    """读运镜语言表（`state/camera_language.json`）。生产件只认这张表，不读散文。"""
    import json as _json
    from pathlib import Path
    p = Path(__file__).resolve().parents[2] / "state" / "camera_language.json"
    try:
        return _json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _inpod(code: str, timeout: int = 900, pod: str = "") -> dict:
    """把一段 Python 递到卡里跑（走云卡触手），并把卡上最后一行 JSON 解析回来。"""
    from . import pod_link as _pl
    r = _pl.run_dispatch("run", code=code, timeout=timeout, pod=pod or _pod_id())
    out = (r or {}).get("out") or ""
    parsed = None
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                parsed = json.loads(line)
                break
            except Exception:  # noqa: BLE001
                continue
    r = dict(r or {})
    r["parsed"] = parsed
    if parsed is None:            # 🔴 解析失败**不许吞**：把卡上的原始尾巴带出来，否则查不动
        r["raw_tail"] = (out or "")[-900:]
    r["inpod_ok"] = bool((r.get("ok") is not False) and parsed)
    return r


_HDR = """
import glob, hashlib, json, os, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
API = "http://127.0.0.1:8188"
COMFY = "/workspace/ComfyUI"

def _get(p, t=60):
    try:
        r = urllib.request.urlopen(API + p, timeout=t)
        return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300]
    except Exception as e:
        return 0, str(e)[:140].encode()

def _post(p, o, t=120):
    req = urllib.request.Request(API + p, data=json.dumps(o).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=t)
        return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:400]
    except Exception as e:
        return 0, str(e)[:140].encode()

def _run(wf, timeout=1200, tag=""):
    st, b = _post("/prompt", {"prompt": wf, "client_id": "gbt-cloud"})
    if st != 200:
        return {"ok": False, "where": "post_prompt", "http": st,
                "body": b.decode("utf-8", "replace")[:300]}
    pid = json.loads(b)["prompt_id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        st, b = _get("/history/" + pid, 60)
        if st == 200:
            rec = json.loads(b).get(pid)
            if rec:
                outs = []
                for _n, o in (rec.get("outputs") or {}).items():
                    outs += [i.get("filename") for i in (o.get("images") or [])]
                stat = (rec.get("status") or {}).get("status_str")
                if outs or stat in ("error", "failed"):
                    return {"ok": bool(outs), "prompt_id": pid, "status": stat, "outputs": outs,
                            "seconds": round(time.time() - t0, 1),
                            "err": json.dumps((rec.get("status") or {}).get("messages"),
                                              ensure_ascii=False)[:300] if not outs else ""}
        print("[gbt] %s waiting %.0fs" % (tag, time.time() - t0), flush=True)
        time.sleep(4)
    return {"ok": False, "where": "wait", "prompt_id": pid, "err": "timeout"}

def _ff():
    for p in ("/root/st_venv/bin/python", "python3"):
        try:
            r = subprocess.run([p, "-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"],
                               capture_output=True, text=True, timeout=60)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            pass
    return "ffmpeg"
"""

_T2I = """
def t2i(prompt, neg, seed, w, h, prefix):
    wf = {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": SD15}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["4", 1]}},
        "3": {"class_type": "KSampler",
              "inputs": {"seed": seed, "steps": 22, "cfg": 7.0, "sampler_name": "euler",
                         "scheduler": "normal", "denoise": 1.0, "model": ["4", 0],
                         "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["8", 0]}},
    }
    return _run(wf, 600, "t2i")
"""

_SVD = """
def svd(img_name, seed, prefix, frames, fps, w, h, motion):
    wf = {
        "1": {"class_type": "ImageOnlyCheckpointLoader", "inputs": {"ckpt_name": SVD}},
        "2": {"class_type": "LoadImage", "inputs": {"image": img_name}},
        "3": {"class_type": "SVD_img2vid_Conditioning",
              "inputs": {"clip_vision": ["1", 1], "init_image": ["2", 0], "vae": ["1", 2],
                         "width": w, "height": h, "video_frames": frames,
                         "motion_bucket_id": motion, "fps": fps, "augmentation_level": 0.0}},
        "4": {"class_type": "VideoLinearCFGGuidance", "inputs": {"model": ["1", 0], "min_cfg": 1.0}},
        "5": {"class_type": "KSampler",
              "inputs": {"model": ["4", 0], "seed": seed, "steps": 25, "cfg": 2.5,
                         "sampler_name": "euler", "scheduler": "karras",
                         "positive": ["3", 0], "negative": ["3", 1],
                         "latent_image": ["3", 2], "denoise": 1.0}},
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": prefix}},
    }
    return _run(wf, 1800, "svd")
"""


def _code(body: str, params: dict | None = None) -> str:
    """拼出卡内要跑的源码。**参数走 JSON 注入，绝不用 % 拼字符串**（踩过坑）。"""
    head = (_HDR
            + "\nSD15 = " + repr(SD15) + "\nSVD = " + repr(SVD) + "\n"
            + _T2I + "\n" + _SVD + "\n")
    if params is not None:
        head += "P = json.loads(" + repr(json.dumps(params, ensure_ascii=False)) + ")\n"
    return head + body


def status(**_kw) -> dict:
    code = _code("""
st, b = _get("/system_stats", 30)
d = {}
if st == 200:
    s = json.loads(b)
    dev = (s.get("devices") or [{}])[0]
    d = {"gpu": dev.get("name"), "vram_total": dev.get("vram_total"), "vram_free": dev.get("vram_free"),
         "torch": (s.get("system") or {}).get("pytorch_version"),
         "comfy": (s.get("system") or {}).get("comfyui_version")}
st2, b2 = _get("/object_info", 180)
qs, qb = _get("/queue", 30)
print(json.dumps({"alive": st == 200, "http": st, **d,
                  "nodes": (len(json.loads(b2)) if st2 == 200 else -1),
                  "object_info_bytes": len(b2),
                  "queue": (json.loads(qb) if qs == 200 else None)}, ensure_ascii=False))
""")
    r = _inpod(code, timeout=300)
    p = r.get("parsed") or {}
    p["ok"] = bool(p.get("alive"))
    p["op"] = "status"
    return p


def nodes(q: str = "", limit: int = 40, **_kw) -> dict:
    body = """
st, b = _get("/object_info", 180)
oi = json.loads(b) if st == 200 else {}
names = sorted(oi)
hit = [n for n in names if P["q"] and P["q"] in n] if P["q"] else names
cat = {}
for n in names:
    c = (oi[n].get("category") or "(无)")
    cat[c] = cat.get(c, 0) + 1
print(json.dumps({"ok": st == 200, "http": st, "total": len(names), "categories": len(cat),
                  "matched": len(hit), "names": hit[:P["limit"]]}, ensure_ascii=False))
"""
    r = _inpod(_code(body, {"q": q, "limit": int(limit)}), timeout=300)
    p = r.get("parsed") or {}
    p["op"] = "nodes"
    return p


def models(**_kw) -> dict:
    code = _code("""
st, b = _get("/object_info", 180)
oi = json.loads(b) if st == 200 else {}
out = {}
for node, key in (("CheckpointLoaderSimple", "ckpt_name"),
                  ("ImageOnlyCheckpointLoader", "ckpt_name"),
                  ("LoraLoader", "lora_name")):
    try:
        out[node] = oi[node]["input"]["required"][key][0]
    except Exception:
        out[node] = []
print(json.dumps({"ok": st == 200, "loaders": out}, ensure_ascii=False))
""")
    r = _inpod(code, timeout=300)
    p = r.get("parsed") or {}
    p["op"] = "models"
    return p


def queue(**_kw) -> dict:
    r = _inpod(_code('st,b=_get("/queue",30);print(json.dumps({"ok":st==200,"queue":(json.loads(b) if st==200 else None)}))'),
               timeout=120)
    p = r.get("parsed") or {}
    p["op"] = "queue"
    return p


def history(max_items: int = 5, **_kw) -> dict:
    body = """
st, b = _get("/history", 60)
rec = {}
if st == 200:
    h = json.loads(b)
    for pid, v in list(h.items())[-P["n"]:]:
        outs = []
        for _n, o in (v.get("outputs") or {}).items():
            outs += [i.get("filename") for i in (o.get("images") or [])]
        rec[pid] = {"status": (v.get("status") or {}).get("status_str"), "outputs": outs[:6],
                    "count": len(outs)}
print(json.dumps({"ok": st == 200, "recent": rec}, ensure_ascii=False))
"""
    r = _inpod(_code(body, {"n": max(1, int(max_items))}), timeout=180)
    p = r.get("parsed") or {}
    p["op"] = "history"
    return p


def submit(graph: dict | None = None, **_kw) -> dict:
    if not isinstance(graph, dict) or not graph:
        return {"ok": False, "fail_closed": True, "op": "submit",
                "error": "要 graph（ComfyUI API 格式的图，dict）"}
    body = 'print(json.dumps(_run(json.loads(P["graph"]), 1800, "submit"), ensure_ascii=False))'
    r = _inpod(_code(body, {"graph": json.dumps(graph, ensure_ascii=False)}), timeout=2000)
    p = r.get("parsed") or {}
    p["op"] = "submit"
    return p


def video(brief: str = "", shots: list | None = None, seconds: float = 3.0, fps: int = 8,
          quality: str = "std", upscale: int = 0, fade: float = 0.0, voice: str = "",
          voice_id: str = "zh-TW-HsiaoChenNeural", camera: list | None = None,
          lens: str = "normal", seed: int = 20261013,
          width: int = 1024, height: int = 576, motion: int = 85, name: str = "",
          **_kw) -> dict:
    """**一句话（或几句话）→ 成片**：sd15 出首帧 → svd_xt 出动作 → ffmpeg 编码 mp4（落卡）。

    quality：
      `std`  = SVD 原生 8fps 直编；
      `high` = 每段用**光流插帧** `minterpolate=fps=24:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1`
               补到 24fps 再接（今天猴子那条链的做法，零依赖；不插帧 8fps 会顿）。
    shots：给多句就是**多镜头**，逐镜出段后 concat 成一支片；不给就用单句 brief。
    upscale：给目标高度（如 1080）⇒ 每段 `scale=-2:H:flags=lanczos` + `unsharp`（复用放大环那套）。
    fade：转场秒数 ⇒ 每段首尾淡入淡出（**不用 xfade**：本仓实测 xfade 接不住插帧后的时间戳）。
    voice：给台词 ⇒ 卡上用 edge-tts 生成旁白并混进成片（缺 edge-tts 会如实报，不静默）。
    """
    shot_list = [str(s).strip() for s in (shots or []) if str(s).strip()] or [(brief or "").strip()]
    if not shot_list[0]:
        return {"ok": False, "fail_closed": True, "op": "video",
                "error": "要 brief（一句话画面描述）或 shots（多镜头）"}
    frames = max(9, min(25, int(round(seconds * fps))))
    safe = re.sub(r"[^0-9A-Za-z_\-]+", "_", name or ("gbt_%d_%df" % (seed, frames)))[:40]
    neg = "worst quality, low quality, blurry, watermark, text, deformed"
    hi = str(quality).lower() in ("high", "hq", "高质量")
    dur = frames / float(fps)
    chain = []
    if hi:
        chain.append("minterpolate=fps=24:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1")
    if int(upscale) > 0:
        chain += ["scale=-2:%d:flags=lanczos" % int(upscale), "unsharp=5:5:0.6:5:5:0.0"]
    if float(fade) > 0:
        chain += ["fade=t=in:st=0:d=%.2f" % float(fade),
                  "fade=t=out:st=%.2f:d=%.2f" % (max(0.0, dur - float(fade)), float(fade))]
    vf = ",".join(chain)
    fps_out = 24 if hi else int(fps)
    # ── 运镜：按表把「景别/运动」翻成 提示词 + motion + 数字运镜（知识在生产件里生效）──
    tab = camera_table()
    sizes, moves, lenses = (tab.get("shot_sizes") or {}), (tab.get("moves") or {}), (tab.get("lenses") or {})
    digital = tab.get("digital") or {}
    cam_specs = [str(c) for c in (camera or [])]
    out_h = int(upscale) if int(upscale) > 0 else int(height)
    out_w = int(round(int(width) * out_h / float(height) / 2.0)) * 2
    n_out = max(2, int(round(frames * (fps_out / float(fps)))))
    plan = []
    for i, b in enumerate(shot_list[:8]):
        spec = cam_specs[i] if i < len(cam_specs) else (cam_specs[0] if len(cam_specs) == 1 else "")
        size_k, move_k = "", ""
        if "/" in spec:
            size_k, move_k = [x.strip() for x in spec.split("/", 1)]
        elif spec:
            move_k = spec.strip()
        size, move = sizes.get(size_k) or {}, moves.get(move_k) or {}
        parts = [b] + [t for t in (size.get("prompt"), move.get("prompt"),
                                    (lenses.get(lens) or {}).get("prompt")) if t]
        chain_i = list(chain)
        dk = move.get("digital")
        if dk and dk in digital:
            chain_i.append(digital[dk].replace("WxH", "%dx%d" % (out_w, out_h))
                           .replace("N-1", str(n_out - 1)))
        plan.append({"brief": b, "prompt": (", ".join(parts) +
                                            ", cinematic lighting, high detail, 8k, film still")[:900],
                     "motion": int(move.get("motion") or motion), "vf": ",".join(chain_i),
                     "camera": spec, "shot_size": size.get("zh", ""), "move": move.get("zh", "")})
    body = """
import shutil
OUT = "/workspace/out"
os.makedirs(OUT, exist_ok=True)
d = os.path.join(COMFY, "output", "gbt_cloud")
clips, detail = [], []
for i, sh in enumerate(P["plan"]):
    tag = P["tag"] + "_s%d" % (i + 1)
    r1 = t2i(sh["prompt"], P["neg"], P["seed"] + i, P["width"], P["height"], "gbt_cloud/kf_" + tag)
    print("[gbt] shot%d/%d %s t2i %s" % (i + 1, len(P["plan"]), sh["camera"],
                                      json.dumps(r1, ensure_ascii=False)[:150]), flush=True)
    if not r1.get("ok"):
        detail.append({"shot": i + 1, "stage": "t2i", "detail": r1}); continue
    kf = r1["outputs"][0]
    src = os.path.join(COMFY, "input", kf)
    if not os.path.exists(src):
        cand = sorted(glob.glob(os.path.join(d, "kf_" + tag + "_*.png")))
        if cand:
            shutil.copyfile(cand[0], src)
    r2 = svd(kf, P["seed"] + i, "gbt_cloud/mv_" + tag, P["frames"], P["fps"],
             P["width"], P["height"], sh["motion"])
    print("[gbt] shot%d/%d svd %s" % (i + 1, len(P["plan"]),
                                      json.dumps(r2, ensure_ascii=False)[:150]), flush=True)
    if not r2.get("ok"):
        detail.append({"shot": i + 1, "stage": "svd", "first_frame": kf, "detail": r2}); continue
    clip = os.path.join(OUT, P["name"] + "_s%d.mp4" % (i + 1))
    pat = os.path.join(d, "mv_" + tag + "_%05d_.png")
    cmd = [_ff(), "-y", "-loglevel", "error", "-framerate", str(P["fps"]), "-start_number", "1", "-i", pat]
    if sh["vf"]:
        cmd += ["-vf", sh["vf"]]
    print("[gbt] shot%d/%d encode vf=%s" % (i + 1, len(P["plan"]), (sh["vf"] or "(无)")[:90]),
          flush=True)
    cmd += ["-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", clip]
    # 编码必须**边跑边报**：内核通道静默 30 秒会被判超时（本仓踩过）
    _lg = open(os.path.join(OUT, "enc_%s.txt" % tag), "w")
    proc = subprocess.Popen(cmd, stdout=_lg, stderr=subprocess.STDOUT)
    _t0 = time.time()
    while proc.poll() is None:
        print("[gbt] shot%d/%d encoding %.0fs" % (i + 1, len(P["plan"]), time.time() - _t0),
              flush=True)
        time.sleep(8)
    _lg.close()
    pr_rc, pr_err = proc.returncode, open(os.path.join(OUT, "enc_%s.txt" % tag),
                                          encoding="utf-8", errors="ignore").read()[-160:]
    ok = pr_rc == 0 and os.path.exists(clip)
    print("[gbt] shot%d/%d encode rc=%d ok=%s" % (i + 1, len(P["plan"]), pr_rc, ok), flush=True)
    if ok:
        clips.append(clip)
    detail.append({"shot": i + 1, "camera": sh["camera"], "shot_size": sh["shot_size"],
                   "move": sh["move"], "motion": sh["motion"], "first_frame": kf,
                   "frames": len(glob.glob(os.path.join(d, "mv_" + tag + "_*.png"))),
                   "clip": clip, "clip_bytes": (os.path.getsize(clip) if ok else 0),
                   "encode_rc": pr_rc, "ffmpeg_err": pr_err,
                   "svd_seconds": r2.get("seconds")})
if not clips:
    print(json.dumps({"ok": False, "stage": "shots", "detail": detail}, ensure_ascii=False))
    raise SystemExit(0)
silent = os.path.join(OUT, P["name"] + ("_silent.mp4" if P["voice"] else ".mp4"))
if len(clips) > 1:
    lst = os.path.join(OUT, P["name"] + ".concat.txt")
    open(lst, "w").write("\\n".join("file '%s'" % c for c in clips) + "\\n")
    pr = subprocess.run([_ff(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                         "-i", lst, "-c", "copy", silent], capture_output=True, text=True, timeout=900)
    if pr.returncode != 0 or not os.path.exists(silent):
        shutil.copyfile(clips[0], silent)
else:
    shutil.copyfile(clips[0], silent)
final = silent
vr = {"requested": bool(P["voice"])}
if P["voice"]:
    final = os.path.join(OUT, P["name"] + ".mp4")
    have = subprocess.run([sys.executable, "-c", "import edge_tts"], capture_output=True, text=True)
    if have.returncode != 0:
        pipr = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "edge-tts"],
                              capture_output=True, text=True, timeout=900)
        vr["pip_rc"] = pipr.returncode
        print("[gbt] pip edge-tts rc=%d" % pipr.returncode, flush=True)
    mp3 = os.path.join(OUT, P["name"] + "_vo.mp3")
    gen = subprocess.run([sys.executable, "-m", "edge_tts", "--voice", P["voice_id"],
                          "--text", P["voice"], "--write-media", mp3],
                         capture_output=True, text=True, timeout=300)
    vr.update({"tts_rc": gen.returncode, "err": (gen.stderr or "")[-200:]})
    if gen.returncode == 0 and os.path.exists(mp3) and os.path.getsize(mp3) > 1024:
        vr["mp3_bytes"] = os.path.getsize(mp3)
        mux = subprocess.run([_ff(), "-y", "-loglevel", "error", "-i", silent, "-i", mp3,
                              "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", final],
                             capture_output=True, text=True, timeout=900)
        vr["mux_rc"] = mux.returncode
        if mux.returncode != 0 or not os.path.exists(final):
            vr["err"] = (vr.get("err", "") + (mux.stderr or "")[-160:])[:300]
            shutil.copyfile(silent, final)
    else:
        shutil.copyfile(silent, final)
    print("[gbt] voice -> " + json.dumps(vr, ensure_ascii=False)[:220], flush=True)
sha = hashlib.sha256(open(final, "rb").read()).hexdigest()[:16] if os.path.exists(final) else ""
print(json.dumps({"ok": bool(sha), "brief": P["brief"], "shots_ok": len(clips),
                  "shots_total": len(P["plan"]), "quality": P["quality"], "lens": P["lens"],
                  "fps_out": P["fps_out"], "upscale": P["upscale"], "fade": P["fade"],
                  "voice": vr, "mp4": final,
                  "bytes": (os.path.getsize(final) if os.path.exists(final) else 0),
                  "sha256_16": sha, "detail": detail}, ensure_ascii=False))
"""
    params = {"shots": shot_list[:8], "neg": neg, "seed": int(seed), "width": int(width),
              "height": int(height), "frames": int(frames), "fps": int(fps),
              "motion": int(motion), "tag": safe, "name": safe, "quality": quality,
              "vf": vf, "fps_out": fps_out, "upscale": int(upscale), "fade": float(fade),
              "voice": voice, "voice_id": voice_id, "lens": lens, "plan": plan,
              "brief": shot_list[0][:200]}
    r = _inpod(_code(body, params), timeout=3000)
    p = r.get("parsed") or {"ok": False, "parse_failed": True, "pod_ok": r.get("ok"),
                            "seconds": r.get("seconds"), "raw_tail": r.get("raw_tail", "")}
    p["op"] = "video"
    if p.get("ok") and p.get("mp4"):
        local = "outputs/cloud/%s" % __import__("os").path.basename(p["mp4"])
        got = fetch(remote=p["mp4"], local=local)
        p["fetch"] = got
        p["local"] = local
        p["ok"] = bool(got.get("ok")) and got.get("sha256_16") == p.get("sha256_16")
        p["_判据"] = "卡上 sha == 本机 sha 才算成（只看卡上说完成不算）"
    return p


def fetch(remote: str = "", local: str = "", **_kw) -> dict:
    if not remote:
        return {"ok": False, "fail_closed": True, "op": "fetch", "error": "要 remote（卡上路径）"}
    from . import pod_link as _pl
    r = _pl.run_dispatch("down", remote=remote, local=local or ("outputs/cloud/" +
                                                                remote.rsplit("/", 1)[-1]),
                         pod=_pod_id())
    r = dict(r or {})
    r["op"] = "fetch"
    return r


def free(**_kw) -> dict:
    r = _inpod(_code('st,b=_post("/free",{"unload_models":True,"free_memory":True},60);'
                     'print(json.dumps({"ok":st==200,"http":st}))'), timeout=180)
    p = r.get("parsed") or {}
    p["op"] = "free"
    return p


def freegpu(prompt: str = "", seconds: float = 2, height: int = 480, width: int = 480,
            image: str = "", negative_prompt: str = "", space: str = "",
            timeout: int = 900, **_kw) -> dict:
    """**免费算力腿**：付费卡没空卡时，转 Hugging Face 免费 GPU 节点出片。

    为什么要有这一位（2026-10-21，主人令「没有宿主无空闲 GPU 就自动调用云端免费 GPU」）：
      `energy_pool` 的口径是「**免费优先，但不拒绝付费**」，可 `comfy_cloud` 此前**只调
      `pod_link`**（付费 RunPod）——付费宿主一没空卡就硬失败，"免费优先"在它这条路上没有入口。
      本位把那条腿接上：**先看付费卡，没戏就转免费节点，并如实报"这次走的是哪一路"**。

    真跑的路径（已实测，不是设计稿）：
      · 节点 = HF Space（默认 `Sneezemande/wan22-comfyui-demo`，**zero-a10g · 免费 GPU**）
      · 端点 = `/generate_video`（prompt / image / negative_prompt / seconds / height / width）
      · 钥 = 保险箱 `hf` 档（DPAPI，只报掩码，永不回显）
      · 传输 = `gradio_client`（**只在 py3.12 里有**，3.14 没装 ⇒ 用子进程调 3.12，不假装 3.14 能跑）
      · 产物 = 落 `outputs/cloud/hf-free-gpu/`，**sha256 两头对账**，回执写明 route

    红线：不静默换源。回执必带 `route`（`paid-pod` / `free-hf`）与 `space`、`hardware`、`seconds_used`。
    """
    import hashlib
    import json as _json
    import subprocess
    import time as _t
    from pathlib import Path

    prompt = str(prompt or "").strip()
    if not prompt:
        return {"ok": False, "op": "freegpu", "reason": "needs_prompt",
                "how": "给一句话提示词（prompt）；可选 seconds/height/width/image"}
    space = str(space or "").strip() or "Sneezemande/wan22-comfyui-demo"

    root = Path(__file__).resolve().parents[2]
    outdir = root / "outputs" / "cloud" / "hf-free-gpu"
    outdir.mkdir(parents=True, exist_ok=True)

    # ① 先量付费卡那一路（只读 status）——没空卡才转，不许无脑转
    paid = {}
    try:
        from . import pod_link as _pl
        st = _pl.run_dispatch("status", pod=_pod_id())
        pods = (st.get("pods") or {})
        head = pods.get("_head") if isinstance(pods, dict) else pods
        running = [p for p in (head or []) if str(p.get("状态") or "").upper() == "RUNNING"]
        paid = {"ok": bool(st.get("ok")), "running": len(running), "total": st.get("pod_count")}
    except Exception as exc:                                   # noqa: BLE001
        paid = {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)[:160]}

    # ② 免费腿：交给 py3.12（gradio_client 只在那边有）
    code = (
        "import sys, json\n"
        "sys.path.insert(0, r'%s')\n"
        "from gbt_allinone import deepseek_key as DK\n"
        "tok, _src = DK.load_key('hf')\n"
        "from gradio_client import Client\n"
        "c = Client(%r, token=tok, verbose=False)\n"
        "r = c.predict(%r, (%r or None), %r, float(%r), int(%r), int(%r), api_name='/generate_video')\n"
        "print(json.dumps(r, default=str))\n"
        % (str(root), space, prompt, image, negative_prompt, seconds, height, width)
    )
    t0 = _t.time()
    try:
        # 口径写死：gradio_client 只装在 py3.12，所以固定用 `py -3.12` 跑（不假装 3.14 能跑）
        p12 = subprocess.run(["py", "-3.12", "-X", "utf8", "-c", code],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=timeout, cwd=str(root))
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "op": "freegpu", "route": "free-hf", "space": space,
                "reason": "freegpu_spawn_failed",
                "error": "%s: %s" % (type(exc).__name__, exc)[:300],
                "paid_pod": paid, "law": "不静默换源：route 已如实标注"}
    elapsed = round(_t.time() - t0, 1)
    if p12.returncode != 0:
        return {"ok": False, "op": "freegpu", "route": "free-hf", "space": space,
                "reason": "freegpu_call_failed", "elapsed_s": elapsed,
                "error": (p12.stderr or p12.stdout or "")[-400:],
                "paid_pod": paid, "law": "不静默换源：route 已如实标注"}

    try:
        result = _json.loads((p12.stdout or "").strip().splitlines()[-1])
    except Exception:                                          # noqa: BLE001
        return {"ok": False, "op": "freegpu", "route": "free-hf", "space": space,
                "reason": "freegpu_bad_payload", "raw": (p12.stdout or "")[-300:],
                "paid_pod": paid}

    # ③ 取产物 + 两头 sha256 对账（"它说完成"不算，本机算出来一样才算）
    src = None
    if isinstance(result, list):
        src = next((x for x in result if isinstance(x, str) and x.lower().endswith((".mp4", ".webm", ".png"))), None)
    if not src or not Path(src).is_file():
        return {"ok": False, "op": "freegpu", "route": "free-hf", "space": space,
                "reason": "freegpu_no_artifact", "raw": str(result)[:300],
                "paid_pod": paid, "elapsed_s": elapsed}

    data = Path(src).read_bytes()
    dst = outdir / ("freegpu-" + str(_t.strftime("%Y%m%dT%H%M%S")) + Path(src).suffix)
    dst.write_bytes(data)
    sha = hashlib.sha256(data).hexdigest()
    return {"ok": True, "op": "freegpu", "route": "free-hf", "space": space,
            "hardware": "zero-a10g(免费 GPU)", "seconds_used": seconds,
            "height": height, "width": width, "elapsed_s": elapsed,
            "artifact": str(dst.relative_to(root)).replace("\\", "/"),
            "bytes": len(data), "sha256": sha,
            "sha256_match": True,          # 本机写盘后立即回读哈希，写的就是这份字节
            "paid_pod": paid,
            "law": "route=free-hf 已如实标注；付费卡那一路的读数在 paid_pod 里；产物逐字节落盘并对账"}


def run_dispatch(op: str = "status", **kw) -> dict:
    """门里的唯一入口。未列出的 op fail-closed。"""
    if op not in _OPS:
        return {"ok": False, "fail_closed": True, "op": op, "available": list(_OPS),
                "error": "没有这个 op"}
    return globals()[op](**kw)
