# -*- coding: utf-8 -*-
"""一键合成成片（帧序列 → mp4）—— 「一键无限生成视频」的**后半件**

## 为什么单独做它
主人 2026-09-23 的令是「**一**定要可以一键无限生成视频」，我当时把这件事拆成两半并说清：
  ① 无限出**帧**（真生成，靠 genrouter 轮询池）—— 已落地
  ② 一键合**成片**（帧 → mp4）—— **本件补的就是它**
并在当时就说明：本机无 CUDA / 内存 7.4GB ⇒ **逐帧生成式视频不现实**，
所以"视频"落在"真生成的帧 + 真合成的运动"上。这条口径不变，**不许含糊成"逐帧生成"**。

## 它做什么
  读一目录的图（或显式给一组）→ 每帧做**推移/缩放**（Ken Burns）→ 帧间**交叉溶解** →
  可选**字幕**（.srt）与**配乐**（音频文件）→ 输出 H.264 mp4 → **ffprobe 回读校验**。

## 依赖与口径
  · 只用 **ffmpeg/ffprobe**（本机现读 8.1.2 在 PATH）+ 标准库，不引新包。
  · **逐字节**不碰：本件只调 ffmpeg，不自己读写图像字节。
  · 退出码：0=出了片且 ffprobe 校验通过 · 2=缺 ffmpeg · 3=没有可用帧 · 4=合成失败 · 5=校验失败。

用法：
    python tools/codex-scripts/make-video.py --frames render/router --out render/video/demo.mp4
    python tools/codex-scripts/make-video.py --frames a.png b.png --sec 4 --fps 30 --zoom
    python tools/codex-scripts/make-video.py --frames render/router --music bgm.mp3 --srt cap.srt
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


def ffprobe(path):
    """回读成片：**校验**用（不是"ffmpeg 说成功就算成功"）。"""
    try:
        cp = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", str(path)],
            capture_output=True, timeout=60)
        j = json.loads((cp.stdout or b"{}").decode("utf-8", "replace") or "{}")
        v = next((s for s in (j.get("streams") or []) if s.get("codec_type") == "video"), {})
        a = next((s for s in (j.get("streams") or []) if s.get("codec_type") == "audio"), None)
        return {"dur": float((j.get("format") or {}).get("duration") or 0),
                "size": int((j.get("format") or {}).get("size") or 0),
                "vcodec": v.get("codec_name"), "w": v.get("width"), "h": v.get("height"),
                "fps": v.get("r_frame_rate"), "frames": v.get("nb_frames"),
                "has_audio": bool(a)}
    except Exception as e:                                                # noqa: BLE001
        return {"error": "%s: %s" % (type(e).__name__, str(e)[:140])}


def collect(frames, limit):
    if len(frames) == 1 and Path(frames[0]).is_dir():
        d = Path(frames[0])
        imgs = sorted([p for p in d.iterdir() if p.suffix.lower() in EXTS],
                      key=lambda p: p.name)
    else:
        imgs = [Path(x) for x in frames]
    imgs = [p for p in imgs if p.is_file()]
    return imgs[:limit] if limit else imgs


def main() -> int:
    ap = argparse.ArgumentParser(description="帧序列 → mp4（Ken Burns + 交叉溶解 + 可选字幕/配乐）")
    ap.add_argument("--frames", nargs="+", required=True, help="图片目录，或一组图片路径")
    ap.add_argument("--out", default="render/video/out.mp4")
    ap.add_argument("--sec", type=float, default=3.0, help="每帧停留秒数")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--zoom", action="store_true", default=True,
                    help="推移/缩放（Ken Burns）；默认开，--no-zoom 关")
    ap.add_argument("--no-zoom", dest="zoom", action="store_false")
    ap.add_argument("--music", default="", help="配乐音频文件（可选）")
    ap.add_argument("--srt", default="", help="字幕（可选，硬字幕）")
    ap.add_argument("--limit", type=int, default=0, help="最多用几张（0=全部）")
    a = ap.parse_args()

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print(json.dumps({"ok": False, "status": "no_ffmpeg",
                          "hint": "ffmpeg/ffprobe 不在 PATH"}, ensure_ascii=False, indent=1))
        return 2

    imgs = collect(a.frames, a.limit)
    if not imgs:
        print(json.dumps({"ok": False, "status": "no_frames",
                          "looked": a.frames}, ensure_ascii=False, indent=1))
        return 3

    out = Path(a.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.parent / ("_mv_" + out.stem)
    tmp.mkdir(exist_ok=True)

    # ── ① 每帧一条 Ken Burns 片段（zoompan）───────────────────────────────
    segs = []
    for i, p in enumerate(imgs):
        seg = tmp / ("seg%03d.mp4" % i)
        # 缩放比：奇数帧推近、偶数帧拉远 —— 交替方向，避免"每帧都一个方向"的机械感
        zdir = "in" if i % 2 == 0 else "out"
        if a.zoom:
            z = ("zoompan=z='if(eq(on,1),1.0001,min(zoom+0.0009,1.18))'"
                 ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                 if zdir == "in" else
                 "zoompan=z='if(eq(on,1),1.18,max(zoom-0.0009,1.0001))'"
                 ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'")
            vf = ("scale=1280:-2," + z + ",trim=duration=%.3f,setpts=PTS-STARTPTS" % a.sec)
        else:
            vf = "scale=1280:-2,trim=duration=%.3f,setpts=PTS-STARTPTS" % a.sec
        cp = subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(p),
                             "-vf", vf, "-r", str(a.fps), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                             "-t", "%.3f" % a.sec, str(seg)],
                            capture_output=True, timeout=300)
        if cp.returncode != 0 or not seg.is_file():
            print(json.dumps({"ok": False, "status": "segment_failed", "frame": str(p),
                              "err": (cp.stderr or b"").decode("utf-8", "replace")[-300:]},
                             ensure_ascii=False, indent=1))
            return 4
        segs.append(seg)

    # ── ② 拼接：单帧直接拷；多帧用交叉溶解串联 ────────────────────────────
    merged = tmp / "merged.mp4"
    xf = 0.6
    if len(segs) == 1:
        shutil.copyfile(segs[0], merged)
    else:
        inputs = []
        for s in segs:
            inputs += ["-i", str(s)]
        parts, prev = [], "0:v"
        for i in range(1, len(segs)):
            outl = ("v%d" % i) if i < len(segs) - 1 else "vout"
            off = a.sec * i - xf * i
            parts.append("[%s][%d:v]xfade=transition=fade:duration=%.2f:offset=%.3f[%s]"
                         % (prev, i, xf, max(0.01, off), outl))
            prev = outl
        cp = subprocess.run(["ffmpeg", "-v", "error", "-y"] + inputs +
                            ["-filter_complex", ";".join(parts), "-map", "[vout]",
                             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(a.fps),
                             str(merged)],
                            capture_output=True, timeout=600)
        if cp.returncode != 0 or not merged.is_file():
            print(json.dumps({"ok": False, "status": "concat_failed",
                              "err": (cp.stderr or b"").decode("utf-8", "replace")[-400:]},
                             ensure_ascii=False, indent=1))
            return 4

    # ── ③ 可选：字幕 / 配乐（都不给就直出）───────────────────────────────
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(merged)]
    extra = []
    if a.music and Path(a.music).is_file():
        cmd += ["-i", a.music]
        extra += ["-map", "0:v", "-map", "1:a", "-shortest", "-c:a", "aac", "-b:a", "160k"]
    else:
        extra += ["-map", "0:v", "-an"]
    if a.srt and Path(a.srt).is_file():
        extra += ["-vf", "subtitles=%s" % str(a.srt).replace("\\", "/").replace(":", "\\:")]
    cmd += extra + ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(a.fps), str(out)]
    cp = subprocess.run(cmd, capture_output=True, timeout=900)
    if cp.returncode != 0 or not out.is_file():
        print(json.dumps({"ok": False, "status": "final_failed",
                          "err": (cp.stderr or b"").decode("utf-8", "replace")[-400:]},
                         ensure_ascii=False, indent=1))
        return 4

    # ── ④ **回读校验**（不拿"ffmpeg 说成功"当结论）────────────────────────
    info = ffprobe(out)
    ok = (info.get("dur", 0) > 0 and info.get("size", 0) > 0 and info.get("vcodec") == "h264")
    for s in segs:
        try:
            s.unlink()
        except Exception:                                                 # noqa: BLE001
            pass
 # **临时目录也要清** —— 本仓成品规矩：「无 `_*.py` / `.tmp` / `__pycache__` 残留」。
    #    实测踩过：只 unlink 段文件、没删 `_mv_<stem>/` ⇒ `outputs/…/_mv_out/` 留在成品目录里。
    for _ in range(2):
        try:
            tmp.rmdir()
        except Exception:                                                 # noqa: BLE001
            # 里面可能还有 merged.mp4 之类的中间件；再强清一次
            try:
                for f in tmp.iterdir():
                    if f.is_file():
                        f.unlink()
            except Exception:
                pass
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
 # **名义时长 vs 实际时长**：`--sec` 是**每段**时长，而段间**交叉溶解会吃掉重叠**
    #    ⇒ 成片 = n×sec − (n−1)×xf，**比 n×sec 短**。实测：3 段 × 2.0 s − 2 × 0.6 s = **4.8 s**
    #    （144 帧 @30fps，与 ffprobe 分毫不差）。以前只吐 ffprobe 读数，**没点明这件事**，
    #    使用者按 `--sec 2 × 3 张 = 6 s` 去期待就会觉得"少了两秒"。
    n = len(imgs)
    nominal = n * a.sec
    actual = info.get("dur", 0)
    overlap = (n - 1) * (xf if n > 1 else 0)
    print(json.dumps({
        "ok": ok, "status": "done" if ok else "verify_failed",
        "out": str(out), "frames": len(imgs), "sec_each": a.sec,
        "zoom": a.zoom, "xfade_s": xf if len(segs) > 1 else 0,
        "music": a.music or None, "srt": a.srt or None,
        "时长账（**别按 n×sec 期待**）": {
            "名义": "%.3f s（%d 段 × %.3f s）" % (nominal, n, a.sec),
            "重叠": "%.3f s（%d 处交叉溶解 × %.2f s）" % (overlap, max(n - 1, 0), xf if n > 1 else 0),
            "实际": "%.3f s（= 名义 − 重叠）" % actual,
            "对得上吗": (abs(actual - (nominal - overlap)) <= 0.06
                     or "⚠️ 差 %.3f s（超出容差，要查）" % abs(actual - (nominal - overlap))),
        },
        "ffprobe": info,
        "_口径": ("**真生成的帧 + 真合成的运动**：帧来自生成模型，帧间运动由 ffmpeg 算（Ken Burns/溶解）。"
                "本机无 CUDA、内存 7.4GB ⇒ **逐帧生成式视频不做**，不把这条含糊成'逐帧生成'。"),
    }, ensure_ascii=False, indent=1))
    return 0 if ok else 5


if __name__ == "__main__":
    raise SystemExit(main())
