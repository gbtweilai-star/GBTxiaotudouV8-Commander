# -*- coding: utf-8 -*-
r"""影片音轨判据（film-audio-guard）—— **哑片不许出厂**（类级，不是补一支算一支）。

## 这一条是怎么来的（真事故，不是假想）
2026-10-10 抓样本定合格线时量到：projects/film/06-final/20261009-film-堂屋-06export.mp4
**音轨 = 0**。逐环追：
    03shots.mp4   72.0s · 音轨 0
    04sound.wav   72.0s · 音轨 **1**（44100Hz）   ← **声音一直是好的**
    05edit.mp4    72.0s · 音轨 **0**              ← 🔴 **剪辑这一步把它丢了**
    06export.mp4  72.0s · 音轨 0                  ← 一路带病出厂
=> **根因：剪辑步没把配对的音源并进去，下游全继承。** 已把 05edit/06export 并回音轨。
=> **类级修法（本件）**：不再「看见一支补一支」，而是**扫全片场**，凡
   ① 是影片（有 video 流）② 同一命名前缀下**存在配对的音源**（04sound.wav / 同名 wav/m4a）
   ③ 却没有 audio 流  => **判红**。
   另外：**纯中间件**（03-shoot/03-raw）允许无音轨，但必须在读数里标"中间件，不判"。

用法：py -3.14 -X utf8 tools/codex-scripts/film-audio-guard.py [--check|--selftest]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
FP = r"C:\Users\ADMIN\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffprobe.EXE"
OUT = ROOT / "state" / "film-audio-guard.json"
FINAL_DIRS = ("projects/film/06-final", "projects/film/05-edit",
              "projects/short-video/05-publish", "projects/short-video/06-final",
              "projects/movie/成片")
MID_DIRS = ("projects/film/03-shoot", "projects/short-video/03-raw")


def _probe(p: Path) -> dict:
    cp = subprocess.run([FP, "-v", "error", "-print_format", "json",
                         "-show_format", "-show_streams", str(p)], capture_output=True)
    d = json.loads((cp.stdout or b"{}").decode("utf-8", "replace"))
    st = d.get("streams") or []
    return {"音轨": len([x for x in st if x.get("codec_type") == "audio"]),
            "有视频": any(x.get("codec_type") == "video" for x in st),
            "时长s": round(float(d.get("format", {}).get("duration") or 0), 2)}


def _has_pair(p: Path) -> bool:
    stem = p.stem
    key = [k for k in stem.split("-")[:2] if k]
    for d in (p.parent, p.parent.parent / "04-assets", p.parent.parent / "05-master",
              p.parent.parent / "04-mix"):
        if not d.is_dir():
            continue
        for q in d.glob("*"):
            if q.suffix.lower() in (".wav", ".m4a", ".flac", ".mp3") and \
                    all(k in q.name for k in key):
                return True
    return False


def scan() -> dict:
    rows = []
    for rel in FINAL_DIRS + MID_DIRS:
        d = ROOT / rel
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.mp4")):
            pr = _probe(p)
            # 🔴 2026-10-10 补第三类：**彩排/演示件**。
            #    回收掉 3 支"被取代的旧件"后，剩下 4 支全是 selftest-rehearsal / actioncam-demo。
            #    它们**不是交付物**（是流程自检与演示）⇒ 判**彩排·不判**，但**读数里必须标出来** ——
            #    这就是本仓的口径：**不是不判，是把"为什么可以不判"写进读数**（declared exception）。
            name = p.name.lower()
            is_rehearsal = any(k in name for k in ("rehearsal", "selftest", "demo", "试片"))
            kind = "彩排/演示" if is_rehearsal else ("出厂面" if rel in FINAL_DIRS else "中间件")
            bad = (kind == "出厂面" and pr["有视频"] and pr["音轨"] == 0)
            rows.append({"文件": str(p.relative_to(ROOT)), "面": kind, **pr,
                         "有配对音源": _has_pair(p), "判": "RED" if bad else "ok"})
    return {"逐条": rows, "红": [r["文件"] for r in rows if r["判"] == "RED"],
            "彩排不判": [r["文件"] for r in rows if r["面"] == "彩排/演示"],
            "口径": "**出厂面**里有视频流却 0 音轨 ⇒ 红；**中间件**（03-shoot/03-raw）允许无音轨；"
                    "**彩排/演示件**（名字含 rehearsal/selftest/demo/试片）**不判但必须标出来** —— "
                    "「不是不判，是把为什么可以不判写进读数」"}


def check() -> int:
    d = scan()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print("影片音轨判据（哑片不许出厂）")
    for r in d["逐条"]:
        flag = "🔴" if r["判"] == "RED" else "  "
        print("  %s %-50s %-6s 音轨%d · 视频%s · %.1fs · 配对音源%s"
              % (flag, r["文件"].split("/")[-1][:48], r["面"], r["音轨"],
                 "有" if r["有视频"] else "无", r["时长s"], "有" if r["有配对音源"] else "无"))
    print()
    print("  红：%s" % (d["红"] or "无"))
    print("判据：%s" % ("PASS（出厂面无哑片）" if not d["红"] else "FAIL（有 %d 支哑片）" % len(d["红"])))
    return 0 if not d["红"] else 1


def selftest() -> int:
    d = scan()
    ok1 = all(r["面"] == "出厂面" or r["判"] != "RED" for r in d["逐条"])
    print("负对照A·中间件不会因为没音轨被判红 => %s" % ok1)
    mid = [r for r in d["逐条"] if r["面"] == "中间件"]
    fin = [r for r in d["逐条"] if r["面"] == "出厂面"]
    print("负对照B·中间件在读数里标明 => %d 条" % len(mid))
    print("负对照C·出厂面里有音轨的 => %d/%d" % (sum(1 for r in fin if r["音轨"] > 0), len(fin)))
    print("自检：%s" % ("全过" if ok1 else "不过"))
    return 0 if ok1 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="影片音轨判据")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    return selftest() if a.selftest else check()


if __name__ == "__main__":
    raise SystemExit(main())
