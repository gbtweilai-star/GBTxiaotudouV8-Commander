# -*- coding: utf-8 -*-
"""native_shortfilm — 本地 SD-Turbo 分镜 + Hanhan 旁白 + ASS 字幕 + ffmpeg 竖屏成片。"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(ROOT)
PYLIBS = os.path.join(WS, "vendor", "pylibs")
FFMPEG = os.path.join(WS, "vendor", "ffmpeg", "bin", "ffmpeg.exe")
FFPROBE = os.path.join(WS, "vendor", "ffmpeg", "bin", "ffprobe.exe")
POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
OUT = os.path.join(WS, ".scratch", "lead", "film-nightlight")
DELIVERY = os.path.join(r"C:\Users\Lenovo E14 Gen 5\Desktop\GBT小土豆V8", "交付成片", "夜灯-Native")

SCENES = [
    ("s1", "cinematic rainy city street at 2am, neon reflections, empty road, moody, film still"),
    ("s2", "small convenience store glowing on an empty street at night, warm windows, rain, cinematic"),
    ("s3", "young Chinese woman with short black hair, beige cardigan, behind a convenience store counter, warm light, medium shot, film still"),
    ("s4", "a stray cat sitting outside a convenience store glass door in the rain, warm interior light, cinematic"),
    ("s5", "young Chinese woman with short black hair, beige cardigan, opening the store glass door with a cup of warm milk, rain, cinematic"),
    ("s6", "close-up of a young Chinese woman with short black hair smiling gently, warm convenience store bokeh, cinematic"),
]
NARRATION = "凌晨两点，城市还没睡。街角便利店的灯，是整条街最温柔的眼睛。她给流浪猫留了一口热牛奶，也给自己留了一盏不灭的灯。"
SUBS = [
    "凌晨两点，城市还没睡。",
    "街角便利店的灯，",
    "是整条街最温柔的眼睛。",
    "她给流浪猫留了一口热牛奶，",
    "也给自己留了一盏不灭的灯。",
    "—— 夜灯 · 本地生成",
]


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    if r.returncode != 0:
        raise RuntimeError("cmd failed %s\n%s\n%s" % (cmd[:4], (r.stdout or "")[-800:], (r.stderr or "")[-800:]))
    return r


def tts(path):
    txt = path + ".txt"
    open(txt, "w", encoding="utf-8").write(NARRATION)
    ps1 = path + ".ps1"
    open(ps1, "w", encoding="utf-8").write(r'''
param([string]$TextFile,[string]$Out)
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice("Microsoft Hanhan Desktop")
$s.Rate = -1
$s.SetOutputToWaveFile($Out)
$s.Speak((Get-Content -Raw -Encoding UTF8 $TextFile))
$s.Dispose()
''')
    if (not os.path.isfile(path)) or os.path.getsize(path) < 1000:
        run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1, "-TextFile", txt, "-Out", path])
    if (not os.path.isfile(path)) or os.path.getsize(path) < 1000:
        run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1, "-TextFile", txt, "-Out", path])
    if (not os.path.isfile(path)) or os.path.getsize(path) < 1000:
        raise RuntimeError("TTS 输出为空：%s" % path)
    dur = float(json.loads(run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "json", path]).stdout)["format"]["duration"])
    return dur


def make_subs(path, shot_dur):
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Microsoft YaHei,54,&H00FFFFFF,&H000000FF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,80,80,170,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for i, text in enumerate(SUBS):
        st = i * shot_dur
        en = min((i + 1) * shot_dur, len(SUBS) * shot_dur)
        def ts(x):
            h = int(x // 3600); m = int((x % 3600) // 60); s = x % 60
            return "%d:%02d:%05.2f" % (h, m, s)
        lines.append("Dialogue: 0,%s,%s,Default,,0,0,0,,%s" % (ts(st), ts(en), text))
    open(path, "w", encoding="utf-8").write("\n".join(lines))


def main():
    os.makedirs(OUT, exist_ok=True)
    for d in ("images", "clips"):
        os.makedirs(os.path.join(OUT, d), exist_ok=True)
    sys.path.insert(0, ROOT)
    from gbt_allinone.tools import comfy_native as CN
    if PYLIBS not in sys.path:
        sys.path.insert(0, PYLIBS)

    wav = os.path.join(OUT, "narration.wav")
    audio_dur = tts(wav)
    shot_dur = max(3.0, (audio_dur + 0.6) / len(SCENES))
    total = shot_dur * len(SCENES)
    print("audio", round(audio_dur, 2), "shot", round(shot_dur, 2), flush=True)

    imgs, clips = [], []
    for i, (sid, prompt) in enumerate(SCENES):
        img = os.path.join(OUT, "images", sid + ".png")
        t = time.time()
        r = CN.NODES["t2i_sdturbo"]["fn"]({"prompt": prompt, "out": img, "size": 512,
                                            "steps": 1, "seed": 100 + i}, {})
        if not r.get("ok"):
            raise RuntimeError("t2i failed %s: %s" % (sid, r))
        print("img", sid, round(time.time() - t, 1), r.get("generation_s"), flush=True)
        imgs.append(img)

    for i, img in enumerate(imgs):
        clip = os.path.join(OUT, "clips", "s%d.mp4" % (i + 1))
        fd = max(1, int(shot_dur * 25))
        vf = ("[0:v]split=2[bg][fg];"
              "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=18:5[bg2];"
              "[fg]scale=1080:1080[fg2];[bg2][fg2]overlay=(W-w)/2:(H-h)/2,"
              "zoompan=z='min(zoom+0.002,1.18)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=%d:s=1080x1920:fps=25,"
              "format=yuv420p" % fd)
        run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-loop", "1", "-i", img,
             "-t", "%.3f" % shot_dur, "-r", "25", "-filter_complex", vf,
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", clip])
        clips.append(clip)
        print("clip", i + 1, flush=True)

    concat = os.path.join(OUT, "concat.mp4")
    lst = os.path.join(OUT, "clips.txt")
    open(lst, "w", encoding="utf-8").write("".join("file '%s'\n" % c.replace("\\", "/") for c in clips))
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", lst, "-c", "copy", concat])

    ass = os.path.join(OUT, "subs.ass")
    make_subs(ass, shot_dur)
    final = os.path.join(OUT, "夜灯-Native-1080x1920.mp4")
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", concat, "-i", wav,
         "-vf", "subtitles=subs.ass",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
         "-shortest", "-movflags", "+faststart", final], cwd=OUT)
    probe = json.loads(run([FFPROBE, "-v", "error", "-show_entries",
                            "format=duration,size:stream=codec_type,width,height,r_frame_rate",
                            "-of", "json", final]).stdout)
    os.makedirs(DELIVERY, exist_ok=True)
    shutil.copyfile(final, os.path.join(DELIVERY, os.path.basename(final)))
    shutil.copyfile(wav, os.path.join(DELIVERY, "narration.wav"))
    shutil.copyfile(ass, os.path.join(DELIVERY, "subs.ass"))
    print(json.dumps({"ok": True, "audio_s": round(audio_dur, 2), "shot_s": round(shot_dur, 2),
                      "total_s": round(total, 2), "mp4": final, "delivery": DELIVERY,
                      "probe": probe}, ensure_ascii=False))


if __name__ == "__main__":
    main()



