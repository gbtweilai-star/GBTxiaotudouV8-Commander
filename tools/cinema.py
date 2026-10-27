#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cinema —— 「投影看电影」的可行版：**手机当幕布 / AirPlay 投到真投影仪**。

先把话说死（不搞错）：
  iPhone 没有光学投影器，光不会射到墙上。想"投到墙上"只有两条：
    ① 接一台真投影仪或电视，用系统的 **AirPlay/屏幕镜像**（这是唯一的光学路径）
    ② 手机屏幕全屏播放，本身当幕布（本工具做的就是这条，且**顺手把片子规格调好**）

它做的事：
  ① 转码成播放器最稳的规格（H.264 + AAC + faststart，1080p 上限）
  ② 用原生 AVPlayer 全屏播放（AirPlay 按钮在播放器里就有）
  ③ 印出投屏指引

用法：
    python3 tools/cinema.py <视频文件> [--1080]
    python3 tools/cinema.py --list
"""
import argparse, json, os, subprocess, sys

OUTDIR = "/var/minis/attachments/cinema"


def probe(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "stream=codec_name,width,height,r_frame_rate:format=duration",
                        "-of", "json", p], capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
        v = next((s for s in d.get("streams", []) if s.get("codec_name")), {})
        return {"w": v.get("width"), "h": v.get("height"), "codec": v.get("codec_name"),
                "dur": round(float(d.get("format", {}).get("duration") or 0), 1)}
    except Exception:                                             # noqa: BLE001
        return {}


def transcode(src, max_h=1080):
    os.makedirs(OUTDIR, exist_ok=True)
    base = os.path.splitext(os.path.basename(src))[0]
    dst = os.path.join(OUTDIR, base + "_cinema.mp4")
    scale = "scale=-2:'min(%d,ih)'" % max_h
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", src,
           "-vf", scale, "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
           "-movflags", "+faststart", dst]
    subprocess.run(cmd, check=True)
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?")
    ap.add_argument("--1080", dest="hd", action="store_true", help="上限 1080p（默认）")
    ap.add_argument("--no-transcode", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    if a.list:
        subprocess.run(["apple-player", "list"])
        return 0
    if not a.src or not os.path.exists(a.src):
        print("给一个视频文件路径。没有片子？可以用我们生成的：")
        print("  /var/minis/attachments/strike_huashan_v7.mp4")
        return 2

    info = probe(a.src)
    print("片源 %s · %sx%s · %s · %ss" % (os.path.basename(a.src), info.get("w"),
                                       info.get("h"), info.get("codec"), info.get("dur")))
    play = a.src
    if not a.no_transcode:
        print("转码中（H.264/AAC/faststart）…")
        play = transcode(a.src, 1080 if a.hd else int(info.get("h") or 1080))
        print("成品 %s · %.1f MB" % (play, os.path.getsize(play) / 1024 / 1024))

    r = subprocess.run(["apple-player", "play", play], capture_output=True, text=True)
    print(r.stdout.strip()[:300])

    print("\n要投到墙上（真投影仪/电视）：")
    print("  ① 先在控制中心 → 屏幕镜像 / AirPlay，连上投影仪或 Apple TV")
    print("  ② 播放器右上角的 AirPlay 图标就能把画面送过去")
    print("  ③ 没有投影设备时，手机全屏就是幕布（现在这步已经做了）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
