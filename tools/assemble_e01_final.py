# -*- coding: utf-8 -*-
"""assemble_e01_final — 用返工后的 cut3 + 台词/字幕层重装 E01-01。

只做装配，不生成模型：
  o1(3s) + o2(3s) + hero cut3(4s) + o4(5s) → 1080×1920/25fps
  + E01-01-audio.wav
  + E01-01-subs.ass（相对路径，cwd 到字幕目录）
"""
from __future__ import annotations

import argparse
import os
import subprocess

WS = r"C:\Users\Lenovo E14 Gen 5\Documents\deepseek-harness\default-workspace\GBTxiaotudouV8-Commander"
FFMPEG = os.path.join(WS, "vendor", "ffmpeg", "bin", "ffmpeg.exe")


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit("ffmpeg failed:\n%s\n%s" % (" ".join(cmd), (r.stderr or "")[-3000:]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cuts", required=True, help="work-E01-01/cuts")
    ap.add_argument("--hero", default="", help="cut3-4f.mp4；为空则用 o3.mp4")
    ap.add_argument("--audio", required=True)
    ap.add_argument("--subs", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    o1 = os.path.join(args.cuts, "o1.mp4")
    o2 = os.path.join(args.cuts, "o2.mp4")
    o3 = args.hero or os.path.join(args.cuts, "o3.mp4")
    o4 = os.path.join(args.cuts, "o4.mp4")
    for p in (o1, o2, o3, o4, args.audio, args.subs):
        if not os.path.isfile(p):
            raise SystemExit("missing: " + p)
    work = os.path.dirname(args.out)
    os.makedirs(work, exist_ok=True)
    # hero 先定长到 4s，统一 1080×1920/25fps
    hero = os.path.join(work, "hero4s.mp4")
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
         "-stream_loop", "20", "-i", o3, "-t", "4",
         "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=25,format=yuv420p",
         "-r", "25", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", hero])
    # 拼视频
    vid = os.path.join(work, "concat.mp4")
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
         "-i", o1, "-i", o2, "-i", hero, "-i", o4,
         "-filter_complex", "[0:v][1:v][2:v][3:v]concat=n=4:v=1:a=0,format=yuv420p[v]",
         "-map", "[v]", "-r", "25", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "18", vid])
    # 字幕 + 音频
    cwd = os.path.dirname(os.path.abspath(args.subs)) or "."
    sub = os.path.basename(args.subs)
    final = args.out
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
         "-i", vid, "-i", args.audio,
         "-vf", "subtitles=" + sub.replace("\\", "/") + ",fade=t=in:st=0:d=0.4,fade=t=out:st=14.6:d=0.4",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", final],
        cwd=cwd)
    print("ok", final)


if __name__ == "__main__":
    main()
