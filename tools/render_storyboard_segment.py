# -*- coding: utf-8 -*-
"""render_storyboard_segment — 把 shuohao storyboard JSON 真正接到 GBT 本地 t2i + i2v 渲染。

一次跑完：storyboard JSON → t2i_sdturbo(SD-Turbo CPU) → i2v_svd(SVD-XT CPU 真运动)
→ 按 cut 时长循环/放大到 1080×1920@25fps → 拼接 → 本地合成环境音 → aac 封装 → ffprobe 复核。

用法：
  <py> tools/render_storyboard_segment.py --storyboard <sb.json> --segment E01-01 \
      --out <out.mp4> --work <workdir> [--prompts <en prompts.json>] [--dry-run]

关键设计（都是踩过的坑）：
  · **只认 storyboard 里的真实 cuts**：秒数来自 cut.seconds，cutStarts = 累加（若 JSON 里自带就核对）；
  · **英文提示词**：优先级 --prompts 文件 > cut.prompt_en > segment.h3Prompt 的英文 [Shot N] 段
    > 按 size/camera 的英文兜底；检测到 CJK 直接拒绝喂给 SD-Turbo（中文 prompt 会出糊图/乱码）；
  · **分两段跑模型**：t2i 全部出完 → 释放 SD-Turbo 管道 → 再加载 SVD-XT；
    本机内存只够一份大模型常驻（SD-Turbo fp32 ≈4.8GB，SVD-XT fp32 ≈9GB）；
  · **SVD 真帧短**（CPU 限制，2 帧 128×256）：用 ffmpeg 循环填满 cut 时长，
    lanczos 放大 + 轻锐化，读数里如实标 "循环真帧"；
  · **每 cut 出运动读数**：解 SVD 原始帧，算相邻帧平均绝对差（真动数字，不用肉眼）；
  · **ffprobe 复核**：时长/分辨率/音频流三条硬判据，不过就退出码 2。

只写 --out / --work / --report 指定的路径；不改仓内源码、不碰交付 docs。
"""
from __future__ import annotations

import argparse
import gc
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = r"C:\Users\Lenovo E14 Gen 5\Documents\deepseek-harness\default-workspace\GBTxiaotudouV8-Commander"
LIVE = os.path.join(WS, "GBTxiaotudouV8-Commander-main")

CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")

SIZE_EN = {
    "extreme-wide": "extreme wide shot",
    "wide": "wide shot",
    "medium": "medium shot",
    "medium-close": "medium close-up",
    "close-up": "close-up",
    "extreme-close-up": "extreme close-up",
}
CAM_EN = {
    "Tracking Shot": "tracking shot",
    "Static Shot": "static shot",
    "Push In": "slow push-in",
    "Pull Out": "slow pull-out",
    "Pan": "panning shot",
    "Tilt": "tilting shot",
    "Handheld": "handheld camera",
}
PERIOD_EN = "early 20th century rural China, muted grey-green palette, atmospheric river fog"


# ─────────────────────────────────────────────────────────────────────────────
# 工具
# ─────────────────────────────────────────────────────────────────────────────
def _find_bin(name: str) -> str:
    cands = [
        os.path.join(WS, "vendor", "ffmpeg", "bin", name),
        os.path.join(ROOT, "vendor", "ffmpeg", "bin", name),
        os.path.join(LIVE, "vendor", "ffmpeg", "bin", name),
    ]
    for p in cands:
        if os.path.isfile(p):
            return p
    found = shutil.which(name)
    if found:
        return found
    raise SystemExit("找不到 %s" % name)


def _ensure_temp(work: str) -> dict:
    """TEMP/TMP 不可写时（沙箱）退到 work/tmp；torch/_dynamo 导入前就得好。"""
    info = {"env_TEMP": os.environ.get("TEMP", ""), "used": "", "switched": False}

    def usable(d: str) -> bool:
        try:
            os.makedirs(d, exist_ok=True)
            p = os.path.join(d, ".wtest")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("x")
            os.remove(p)
            return True
        except Exception:  # noqa: BLE001
            return False

    target = os.environ.get("TEMP") or ""
    if not target or not usable(target):
        target = os.path.join(work, "tmp")
        os.makedirs(target, exist_ok=True)
        os.environ["TEMP"] = target
        os.environ["TMP"] = target
        tempfile.tempdir = target
        info["switched"] = True
    info["used"] = target
    info["usable"] = usable(target)
    return info


def _rss_mb() -> float:
    try:
        import psutil  # noqa: PLC0415
        return round(psutil.Process().memory_info().rss / 1048576, 1)
    except Exception:  # noqa: BLE001
        try:
            import ctypes
            from ctypes import wintypes
            class _PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
            pmc = _PMC(); pmc.cb = ctypes.sizeof(pmc)
            ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),
                                                    ctypes.byref(pmc), pmc.cb)
            return round(pmc.WorkingSetSize / 1048576, 1)
        except Exception:  # noqa: BLE001
            return -1.0


def _run(cmd: list, what: str) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit("%s 失败 rc=%s\ncmd=%s\nstderr=%s" %
                         (what, r.returncode, " ".join(cmd), (r.stderr or "")[-3000:]))
    return r


# ─────────────────────────────────────────────────────────────────────────────
# storyboard 解析
# ─────────────────────────────────────────────────────────────────────────────
def load_segment(sb_path: str, segment_id: str) -> tuple:
    sb = json.load(open(sb_path, encoding="utf-8"))
    for ep in sb.get("episodes", []):
        for seg in ep.get("segments", []):
            if seg.get("id") == segment_id:
                return sb, ep, seg
    raise SystemExit("segment not found: %s（有：%s）" % (
        segment_id, [s.get("id") for ep in sb.get("episodes", []) for s in ep.get("segments", [])]))


def cut_timing(seg: dict) -> dict:
    cuts = seg.get("cuts") or []
    if not cuts:
        raise SystemExit("segment %s 没有 cuts" % seg.get("id"))
    secs = [float(c.get("seconds") or 3.0) for c in cuts]
    starts = [round(sum(secs[:i]), 3) for i in range(len(secs))]
    declared = seg.get("cutStarts")
    out = {"cuts": len(cuts), "seconds": secs, "cutStarts": starts,
           "total_seconds": round(sum(secs), 3), "declared_cutStarts": declared,
           "cutStarts_match": None}
    if isinstance(declared, list) and len(declared) == len(starts):
        out["cutStarts_match"] = all(abs(float(a) - b) < 1e-6 for a, b in zip(declared, starts))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 英文提示词
# ─────────────────────────────────────────────────────────────────────────────
def _clean_en(text: str) -> str:
    # 只取画面描述：声音/配乐段落不属于文生图提示词
    text = re.split(r"overall_soundscape\s*:", text, flags=re.I)[0]
    text = re.split(r"non_diegetic_music\s*:", text, flags=re.I)[0]
    text = re.sub(r"<Picture\s+\d+>", "", text)
    text = re.sub(r"</?d>", "", text)
    text = re.sub(r"At\s+00:\d\d\.\d+,?\s*", "", text)
    text = re.sub(r"\[Chinese\][^\n]*", "", text)          # 台词行整行去掉（中文字幕不进 prompt）
    text = re.sub(r"\[Shot\s+\d+\]", "", text)
    text = re.sub(r"\s*:\s*", ": ", text)
    text = re.sub(r"\s*:\s*(?=$|[.;])", "", text)         # 收尾悬空冒号
    text = re.sub(r"[。，、；：！？“”‘’（）]+", " ", text)  # 中文标点清掉（CJK 残留也会被拦）
    text = re.sub(r"\b(follows|cuts to|shows)\s*:\s*", r"\1 ", text)
    text = re.sub(r"\s+", " ", text).strip(" ,.;:")
    return text


def _en_from_h3(seg: dict, shot_no: int) -> str:
    h3 = seg.get("h3Prompt") or ""
    for m in re.finditer(r"\[Shot\s+(\d+)\](.*?)(?=\[Shot\s+\d+\]|\Z)", h3, re.S):
        if int(m.group(1)) == shot_no:
            text = _clean_en(m.group(2))
            # 取前 2 句 / 最多 ~58 词（CLIP 77 token 上限，超了等于白写）
            sents = re.split(r"(?<=[.!?])\s+", text)
            pick = ""
            for s in sents:
                if len((pick + " " + s).split()) <= 58:
                    pick = (pick + " " + s).strip()
                else:
                    break
            return pick or " ".join(text.split()[:58])
    return ""


def _en_generic(cut: dict) -> str:
    size = SIZE_EN.get(str(cut.get("size") or ""), "medium shot")
    cam = CAM_EN.get(str(cut.get("camera") or ""), str(cut.get("camera") or "static shot").lower())
    return "cinematic film still, %s, %s, thick river fog, misty morning light, %s" % (size, cam, PERIOD_EN)


def resolve_prompts(seg: dict, prompts_file: str = "") -> list:
    cuts = seg.get("cuts") or []
    file_prompts = []
    if prompts_file:
        data = json.load(open(prompts_file, encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("prompts") or data.get("prompt") or []
        file_prompts = [str(x) if not isinstance(x, dict) else str(x.get("prompt") or "")
                        for x in data]
    out = []
    for i, cut in enumerate(cuts):
        cand = []
        if i < len(file_prompts) and file_prompts[i].strip():
            cand.append(("prompts_file", file_prompts[i].strip()))
        for k in ("prompt_en", "promptEn", "en"):
            if cut.get(k):
                cand.append(("cut." + k, str(cut[k]).strip()))
        h3 = _en_from_h3(seg, i + 1)
        if h3:
            cand.append(("h3Prompt[Shot %d]" % (i + 1), h3))
        cand.append(("generic_en", _en_generic(cut)))
        chosen, source = None, None
        for src, txt in cand:
            if CJK.search(txt):
                continue  # 中文 prompt 绝对不喂 SD-Turbo
            chosen, source = txt, src
            break
        if chosen is None:
            raise SystemExit("cut %d 拿不到任何英文提示词" % (i + 1))
        out.append({"cut": i + 1, "source": source, "prompt": chosen,
                    "zh_frame_len": len(str(cut.get("frame") or ""))})
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 模型两段跑
# ─────────────────────────────────────────────────────────────────────────────
def load_cn():
    for p in (os.path.join(WS, "vendor", "pylibs"), LIVE):
        if p not in sys.path:
            sys.path.insert(0, p)
    from gbt_allinone.tools import comfy_native as CN  # noqa: PLC0415
    for node in ("t2i_sdturbo", "i2v_svd"):
        if node not in CN.NODES:
            raise SystemExit("CN.NODES 缺 %s（实际 %d 个节点）" % (node, len(CN.NODES)))
    return CN


def free_sdturbo_pipe() -> dict:
    """t2i 出完后释放 SD-Turbo 管道，给 SVD 腾内存（管道是 comfy_nodes_extra 的模块级缓存）。"""
    info = {"rss_before_mb": _rss_mb(), "freed": False}
    try:
        from gbt_allinone.tools import comfy_nodes_extra as EX  # noqa: PLC0415
        if getattr(EX, "_SD_TURBO_PIPE", None):
            EX._SD_TURBO_PIPE.update({"path": None, "pipe": None})
            info["freed"] = True
        gc.collect()
        if str(sys.version_info[0]) == "3":
            try:
                import torch
                if hasattr(torch, "cpu") and hasattr(torch.cpu, "empty_cache"):
                    pass
            except Exception:  # noqa: BLE001
                pass
    except Exception as e:  # noqa: BLE001
        info["error"] = str(e)[:200]
    info["rss_after_mb"] = _rss_mb()
    return info


def clip_motion(ffmpeg: str, clip: str, width: int, height: int) -> dict:
    """解 SVD 原始帧 → 相邻帧平均绝对差（真正"有运动"的数字证据）。"""
    try:
        import numpy as np  # noqa: PLC0415
        raw = subprocess.run([ffmpeg, "-v", "error", "-i", clip, "-f", "rawvideo",
                              "-pix_fmt", "gray", "-"], capture_output=True).stdout
        n = len(raw) // (width * height)
        if n < 2:
            return {"frames": n, "mean_abs_diff": -1.0, "note": "不足 2 帧"}
        arr = np.frombuffer(raw[:n * width * height], dtype=np.uint8).reshape(n, height, width).astype("float32")
        diffs = [float(np.abs(arr[i + 1] - arr[i]).mean()) for i in range(n - 1)]
        return {"frames": n, "mean_abs_diff": round(sum(diffs) / len(diffs), 3),
                "per_pair": [round(d, 3) for d in diffs]}
    except Exception as e:  # noqa: BLE001
        return {"frames": -1, "mean_abs_diff": -1.0, "error": str(e)[:200]}


def probe(ffprobe: str, path: str) -> dict:
    r = _run([ffprobe, "-v", "error", "-print_format", "json",
              "-show_format", "-show_streams", path], "ffprobe")
    j = json.loads(r.stdout or "{}")
    streams = j.get("streams") or []
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    a = next((s for s in streams if s.get("codec_type") == "audio"), {})
    fmt = j.get("format") or {}
    return {
        "duration_s": float(fmt.get("duration") or 0),
        "size_bytes": int(fmt.get("size") or 0),
        "video": {"codec": v.get("codec_name"), "width": v.get("width"),
                  "height": v.get("height"), "fps": v.get("r_frame_rate"),
                  "nb_frames": v.get("nb_frames"), "pix_fmt": v.get("pix_fmt")},
        "audio": {"codec": a.get("codec_name"), "channels": a.get("channels"),
                  "sample_rate": a.get("sample_rate"), "duration_s": float(a.get("duration") or 0)},
        "has_audio": bool(a),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--storyboard", required=True)
    ap.add_argument("--segment", default="E01-01")
    ap.add_argument("--out", required=True)
    ap.add_argument("--work", default="")
    ap.add_argument("--prompts", default="", help="可选：按 cut 顺序的英文提示词 JSON 数组")
    ap.add_argument("--frames", type=int, default=2, help="SVD 真帧数（CPU 建议 2）")
    ap.add_argument("--width", type=int, default=128)
    ap.add_argument("--height", type=int, default=256)
    ap.add_argument("--steps", type=int, default=1, help="SVD 步数")
    ap.add_argument("--fps", type=int, default=8, help="SVD 输出 fps")
    ap.add_argument("--motion-bucket", type=int, default=127)
    ap.add_argument("--t2i-size", type=int, default=512)
    ap.add_argument("--t2i-steps", type=int, default=1)
    ap.add_argument("--t2i-seed", type=int, default=700)
    ap.add_argument("--i2v-seed", type=int, default=900)
    ap.add_argument("--fps-out", type=int, default=25)
    ap.add_argument("--crf", type=int, default=20)
    ap.add_argument("--sharpen", default="unsharp=5:5:0.7:3:3:0.25")
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--report", default="")
    ap.add_argument("--dry-run", action="store_true", help="只解析/出提示词计划，不跑模型")
    args = ap.parse_args()

    t_all = time.time()
    sb_path = os.path.abspath(args.storyboard)
    out_path = os.path.abspath(args.out)
    work = os.path.abspath(args.work) if args.work else os.path.join(os.path.dirname(out_path), "work-" + args.segment)
    cuts_dir = os.path.join(work, "cuts")
    os.makedirs(cuts_dir, exist_ok=True)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    report_path = os.path.abspath(args.report) if args.report else os.path.join(work, "render-report.json")

    temp_info = _ensure_temp(work)
    ffmpeg = _find_bin("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    ffprobe = _find_bin("ffprobe.exe" if os.name == "nt" else "ffprobe")

    sb, ep, seg = load_segment(sb_path, args.segment)
    timing = cut_timing(seg)
    prompts = resolve_prompts(seg, args.prompts)

    print("[plan] storyboard=%s" % sb_path, flush=True)
    print("[plan] segment=%s scene=%s episode=%s" % (args.segment, seg.get("sceneIndex"), ep.get("ep")), flush=True)
    print("[plan] cuts=%d seconds=%s cutStarts=%s total=%.3fs match=%s" % (
        timing["cuts"], timing["seconds"], timing["cutStarts"], timing["total_seconds"],
        timing["cutStarts_match"]), flush=True)
    print("[plan] temp=%s switched=%s" % (temp_info["used"], temp_info["switched"]), flush=True)
    for p in prompts:
        print("[plan] cut%d prompt(%s)=%s" % (p["cut"], p["source"], p["prompt"]), flush=True)

    plan = {"storyboard": sb_path, "segment": args.segment, "timing": timing,
            "prompts": prompts, "args": {k: v for k, v in vars(args).items()},
            "temp": temp_info, "ffmpeg": ffmpeg, "ffprobe": ffprobe,
            "env": {"python": sys.version.split()[0]}}
    if args.dry_run:
        print(json.dumps({"ok": True, "dry_run": True, "plan": plan}, ensure_ascii=False), flush=True)
        return

    CN = load_cn()
    report = {"ok": True, "segment": args.segment, "storyboard": sb_path,
              "engine": "shuohao storyboard JSON → GBT 本地 t2i_sdturbo + i2v_svd",
              "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
              "plan": plan, "cuts": [], "node_readings": {},
              "env": {"python": sys.version.split()[0], "rss_start_mb": _rss_mb()}}

    # ── 第一段：t2i（SD-Turbo）─────────────────────────────────────────────
    t2i_list = []
    for i, p in enumerate(prompts):
        img = os.path.join(cuts_dir, "f%d.png" % (i + 1))
        t = time.time()
        r = CN.NODES["t2i_sdturbo"]["fn"]({"prompt": p["prompt"], "out": img,
                                           "size": args.t2i_size, "steps": args.t2i_steps,
                                           "seed": args.t2i_seed + i}, {})
        wall = round(time.time() - t, 2)
        if not r.get("ok"):
            raise SystemExit("t2i cut%d 失败：%s" % (i + 1, json.dumps(r, ensure_ascii=False)[:800]))
        item = {"cut": i + 1, "png": img, "bytes": os.path.getsize(img),
                "wall_s": wall, "node": r, "prompt_source": p["source"], "prompt": p["prompt"]}
        t2i_list.append(item)
        print("[t2i] cut%d %dx%d steps=%d wall=%.1fs load=%ss gen=%ss bytes=%d" % (
            i + 1, args.t2i_size, args.t2i_size, args.t2i_steps, wall,
            r.get("load_s"), r.get("generation_s"), item["bytes"]), flush=True)

    free_info = free_sdturbo_pipe()
    print("[mem] free SD-Turbo pipe: %s" % json.dumps(free_info), flush=True)
    report["node_readings"]["t2i"] = t2i_list
    report["node_readings"]["free_sdturbo"] = free_info
    report["env"]["rss_after_t2i_mb"] = _rss_mb()

    # ── 第二段：i2v（SVD-XT 真运动）────────────────────────────────────────
    svd_list = []
    for i, p in enumerate(prompts):
        img = t2i_list[i]["png"]
        clip = os.path.join(cuts_dir, "c%d.mp4" % (i + 1))
        t = time.time()
        r = CN.NODES["i2v_svd"]["fn"]({"image": img, "out": clip,
                                       "frames": args.frames, "width": args.width,
                                       "height": args.height, "steps": args.steps,
                                       "fps": args.fps, "seed": args.i2v_seed + i,
                                       "motion": args.motion_bucket}, {})
        wall = round(time.time() - t, 2)
        if not r.get("ok"):
            raise SystemExit("i2v cut%d 失败：%s" % (i + 1, json.dumps(r, ensure_ascii=False)[:800]))
        mot = clip_motion(ffmpeg, clip, args.width, args.height)
        item = {"cut": i + 1, "mp4": clip, "bytes": os.path.getsize(clip),
                "wall_s": wall, "node": r, "motion": mot}
        svd_list.append(item)
        print("[i2v] cut%d frames=%d %dx%d steps=%d wall=%.1fs load=%ss gen=%ss bytes=%d motion_mean_abs_diff=%s" % (
            i + 1, args.frames, args.width, args.height, args.steps, wall,
            r.get("load_s"), r.get("generation_s"), item["bytes"], mot.get("mean_abs_diff")), flush=True)
    report["node_readings"]["i2v"] = svd_list
    report["env"]["rss_after_svd_mb"] = _rss_mb()

    # ── 每 cut：循环真帧 → 1080×1920 → 精确定长 ───────────────────────────
    clips = []
    for i, dur in enumerate(timing["seconds"]):
        clip = svd_list[i]["mp4"]
        clip_dur = args.frames / float(args.fps)
        loops = max(0, int(math.ceil(dur / clip_dur)) - 1)
        outclip = os.path.join(cuts_dir, "o%d.mp4" % (i + 1))
        vf = ("scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,"
              "crop=1080:1920,%s,fps=%d,format=yuv420p" % (args.sharpen, args.fps_out))
        cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
               "-stream_loop", str(loops), "-i", clip, "-t", "%.3f" % dur,
               "-vf", vf, "-r", str(args.fps_out), "-c:v", "libx264",
               "-preset", "veryfast", "-crf", str(args.crf), outclip]
        t = time.time()
        _run(cmd, "ffmpeg cut%d 放大/定长" % (i + 1))
        pinfo = probe(ffprobe, outclip)
        clips.append({"cut": i + 1, "mp4": outclip, "seconds": dur,
                      "loop_repeats": loops, "src_clip_s": round(clip_dur, 3),
                      "wall_s": round(time.time() - t, 2), "probe": pinfo, "cmd": cmd})
        print("[clip] cut%d loop=%d src_clip=%.3fs -> %.3fs %dx%d" % (
            i + 1, loops, clip_dur, pinfo["duration_s"],
            pinfo["video"].get("width") or 0, pinfo["video"].get("height") or 0), flush=True)
    report["clips"] = clips

    # ── 拼接 ────────────────────────────────────────────────────────────────
    lst = os.path.join(work, "concat.txt")
    with open(lst, "w", encoding="utf-8") as fh:
        for c in clips:
            fh.write("file '%s'\n" % c["mp4"].replace("\\", "/"))
    silent = os.path.join(work, "silent.mp4")
    concat_cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                  "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent]
    _run(concat_cmd, "concat")
    total = timing["total_seconds"]

    # ── 本地环境音（低通棕噪河水 + 两下远处梆子）───────────────────────────
    if args.no_audio:
        final_tmp = silent
        audio_info = {"enabled": False}
    else:
        amb = os.path.join(work, "amb.wav")
        d = total + 0.4
        fc = (
            "[0]lowpass=f=240,highpass=f=42,volume=1.0[amb];"
            "[1]volume=0.22,afade=t=out:st=0:d=0.12,adelay=3200|3200[k1];"
            "[2]volume=0.18,afade=t=out:st=0:d=0.16,adelay=4050|4050[k2];"
            "[amb][k1][k2]amix=inputs=3:normalize=0,"
            "afade=t=in:st=0:d=0.5,afade=t=out:st=%.2f:d=0.6[a]" % max(0.0, total - 0.6)
        )
        amb_cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                   "-f", "lavfi", "-i", "anoisesrc=color=brown:amplitude=0.05:duration=%f" % d,
                   "-f", "lavfi", "-i", "sine=f=170:d=0.12",
                   "-f", "lavfi", "-i", "sine=f=150:d=0.16",
                   "-filter_complex", fc, "-map", "[a]", "-ar", "44100", "-ac", "1", amb]
        t = time.time()
        _run(amb_cmd, "环境音")
        audio_info = {"enabled": True, "amb_wav": amb, "bytes": os.path.getsize(amb),
                      "wall_s": round(time.time() - t, 2), "layers": "brown-noise river + 2 distant wooden claps",
                      "cmd": amb_cmd}
        final_tmp = os.path.join(work, "with-audio.mp4")
        mux_cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                   "-i", silent, "-i", amb, "-c:v", "copy", "-c:a", "aac",
                   "-b:a", "160k", "-shortest", "-movflags", "+faststart", final_tmp]
        _run(mux_cmd, "封装音轨")
        audio_info["mux_cmd"] = mux_cmd

    if os.path.abspath(final_tmp) != out_path:
        shutil.copyfile(final_tmp, out_path)
    report["audio"] = audio_info

    # ── ffprobe 复核 ────────────────────────────────────────────────────────
    fin = probe(ffprobe, out_path)
    checks = {
        "duration_about_15s": abs(fin["duration_s"] - total) <= 0.5,
        "width_1080": (fin["video"].get("width") == 1080),
        "height_1920": (fin["video"].get("height") == 1920),
        "has_audio": fin["has_audio"],
        "cut_count": len(clips) == timing["cuts"],
        "cut_timing_sum": abs(sum(c["probe"]["duration_s"] for c in clips) - total) <= 0.3,
        "svd_real_motion": all(s["motion"].get("mean_abs_diff", -1) > 0.05 for s in svd_list),
        "prompts_have_no_cjk": all(not CJK.search(p["prompt"]) for p in prompts),
    }
    ok = all(checks.values())
    report.update({"out": out_path, "ffprobe": fin, "checks": checks, "ok": ok,
                   "total_wall_s": round(time.time() - t_all, 1),
                   "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print("[probe] %s" % json.dumps(fin, ensure_ascii=False), flush=True)
    print("[checks] %s" % json.dumps(checks, ensure_ascii=False), flush=True)
    print("[report] %s" % report_path, flush=True)
    print(json.dumps({"ok": ok, "segment": args.segment, "out": out_path,
                      "seconds": fin["duration_s"], "size": fin["size_bytes"],
                      "cuts": len(clips), "total_wall_s": report["total_wall_s"],
                      "checks": checks}, ensure_ascii=False), flush=True)
    if not ok:
        sys.exit(2)


if __name__ == "__main__":
    main()
