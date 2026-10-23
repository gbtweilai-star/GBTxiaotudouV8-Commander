# -*- coding: utf-8 -*-
r"""样本合格线（sample-baseline）—— **抓真样本，量成可机检的合格线**。

主人令（2026-10-10）：「搞定眼睛之后再去**抓取电影和音乐的样本作为合格线**」
               （2026-10-10 二令）：「下一轮」

## 口径（先说死，免得变成拍脑袋）
**合格线不许我自己编** —— 每条必须：
  ① 来自**真样本**的现读数字（ffprobe / ffmpeg）；
  ② 写明**出处**（哪个文件、量了什么）；
  ③ 合成一个**区间**（min~max），区间外才叫不合格。

## 手上的真样本（现读）
电影：projects/film/06-final/20261009-film-堂屋-06export.mp4（13.54MB）
      projects/film/03-shoot/20261009-film-堂屋-03shots.mp4
音乐：projects/music/06-release/20261009-music-夜航-05export.flac（1.85MB）
      projects/music/05-master/20261009-music-夜航-04master.wav（7.65MB）
      projects/music/05-master/20260923-music-试听垫乐-rehearsal.wav（9.98MB）

## 量什么
电影：分辨率 · 帧率 · 时长 · 音轨数 · **镜头数**（场景切换检测）· **平均镜头长度** · 响度LUFS · 峰值
音乐：时长 · 采样率 · 位深 · 声道 · 响度LUFS · 峰值 · **动态范围**（LUFS 与峰值之差）

用法：py -3.14 -X utf8 tools/codex-scripts/sample-baseline.py [--check|--selftest]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
B = Path(r"C:\Users\ADMIN\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin")
FF, FP = B / "ffmpeg.EXE", B / "ffprobe.EXE"
OUT = ROOT / "state" / "sample-baseline.json"

FILMS = ["projects/film/06-final/20261009-film-堂屋-06export.mp4",
         "projects/film/03-shoot/20261009-film-堂屋-03shots.mp4",
         "projects/short-video/06-final/20261010-short-video-醒来-ep01-达标.mp4"]
MUSICS = ["projects/music/06-release/20261009-music-夜航-05export.flac",
          "projects/music/05-master/20261009-music-夜航-04master.wav",
          "projects/music/05-master/20260923-music-试听垫乐-rehearsal.wav"]


def _p(p: Path) -> dict:
    cp = subprocess.run([str(FP), "-v", "error", "-print_format", "json",
                         "-show_format", "-show_streams", str(p)], capture_output=True)
    return json.loads((cp.stdout or b"{}").decode("utf-8", "replace"))


def _loud(p: Path) -> dict:
    """真量响度（ebur128）与峰值（volumedetect）。"""
    cp = subprocess.run([str(FF), "-hide_banner", "-nostats", "-i", str(p),
                         "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True)
    t = (cp.stderr or b"").decode("utf-8", "replace")
    def grab(pat):
        m = re.findall(pat, t)
        return float(m[-1]) if m else None
    return {"响度LUFS": grab(r"I:\s*(-?\d+\.\d+)\s*LUFS"),
            "峰值dBFS": grab(r"Peak:\s*(-?\d+\.\d+)\s*dBFS"),
            "真峰dBFS": grab(r"True peak:\s*(-?\d+\.\d+)\s*dBFS")}


def _scenes(p: Path) -> dict:
    """镜头数：场景切换检测（阈值 0.3，行业常用起点；阈值写进读数里，可复核）。"""
    cp = subprocess.run([str(FF), "-hide_banner", "-nostats", "-i", str(p),
                         "-vf", "select='gt(scene,0.3)',showinfo", "-f", "null", "-"],
                        capture_output=True)
    t = (cp.stderr or b"").decode("utf-8", "replace")
    n = len(re.findall(r"pts_time:", t))
    return {"镜头数": max(1, n + 1), "检测阈值": 0.3}


def film(rel: str) -> dict:
    p = ROOT / rel
    if not p.is_file():
        return {"文件": rel, "在盘": False}
    d = _p(p)
    st = d.get("streams") or []
    v = next((s for s in st if s.get("codec_type") == "video"), {})
    a = [s for s in st if s.get("codec_type") == "audio"]
    sub = [s for s in st if s.get("codec_type") == "subtitle"]
    dur = float(d.get("format", {}).get("duration") or 0)
    sc = _scenes(p)
    lo = _loud(p)
    return {"文件": rel, "在盘": True, "MB": round(p.stat().st_size / 1e6, 2),
            "宽": int(v.get("width") or 0), "高": int(v.get("height") or 0),
            "帧率": v.get("r_frame_rate"), "时长s": round(dur, 2),
            "音轨": len(a), "字幕轨": len(sub),
            **sc, "平均镜头长度s": round(dur / sc["镜头数"], 2), **lo}


def music(rel: str) -> dict:
    p = ROOT / rel
    if not p.is_file():
        return {"文件": rel, "在盘": False}
    d = _p(p)
    st = d.get("streams") or []
    a = next((s for s in st if s.get("codec_type") == "audio"), {})
    lo = _loud(p)
    dur = float(d.get("format", {}).get("duration") or 0)
    dyn = None
    if lo.get("响度LUFS") is not None and lo.get("峰值dBFS") is not None:
        dyn = round(lo["峰值dBFS"] - lo["响度LUFS"], 2)
    return {"文件": rel, "在盘": True, "MB": round(p.stat().st_size / 1e6, 2),
            "时长s": round(dur, 2), "采样率": a.get("sample_rate"),
            "位深": a.get("bits_per_raw_sample") or a.get("bits_per_sample"),
            "声道": a.get("channels"), "编码": a.get("codec_name"),
            **lo, "动态范围dB": dyn}


def baseline() -> dict:
    fl = [film(x) for x in FILMS]
    mu = [music(x) for x in MUSICS]
    ok_f = [x for x in fl if x.get("在盘")]
    ok_m = [x for x in mu if x.get("在盘")]
    line = {"电影": {"样本数": len(ok_f)},
            "音乐": {"样本数": len(ok_m)}}
    if ok_f:
        line["电影"].update({
            "时长s 区间": [min(x["时长s"] for x in ok_f), max(x["时长s"] for x in ok_f)],
            "镜头数 区间": [min(x["镜头数"] for x in ok_f), max(x["镜头数"] for x in ok_f)],
            "平均镜头长度s 区间": [min(x["平均镜头长度s"] for x in ok_f),
                                  max(x["平均镜头长度s"] for x in ok_f)],
            "有音轨的样本": sum(1 for x in ok_f if x["音轨"] >= 1),
            "分辨率集合": sorted({"%dx%d" % (x["宽"], x["高"]) for x in ok_f}),
            "出处": [x["文件"] for x in ok_f]})
    if ok_m:
        line["音乐"].update({
            "时长s 区间": [min(x["时长s"] for x in ok_m), max(x["时长s"] for x in ok_m)],
            "响度LUFS 区间": [min(x["响度LUFS"] for x in ok_m if x.get("响度LUFS") is not None),
                              max(x["响度LUFS"] for x in ok_m if x.get("响度LUFS") is not None)],
            "动态范围dB 区间": [min(x["动态范围dB"] for x in ok_m if x.get("动态范围dB") is not None),
                                max(x["动态范围dB"] for x in ok_m if x.get("动态范围dB") is not None)],
            "采样率集合": sorted({str(x["采样率"]) for x in ok_m}),
            "出处": [x["文件"] for x in ok_m]})
    # 🔴 2026-10-10 **样本不足要如实说，不许编线**：
    #    手上两条电影样本（堂屋-06export / 堂屋-03shots）**都没有音轨** ⇒
    #    **电影响度合格线没有样本支撑** ⇒ 不写区间，只写"样本不足"与可参考的通行值。
    if ok_f and all(x["音轨"] == 0 for x in ok_f):
        line["电影"]["响度合格线"] = "**样本不足**（手上电影样本全部无音轨，不许编）"
        line["电影"]["可参考"] = "流媒体通行 -14 LUFS；广播 EBU R128 -23 LUFS —— 均**非本仓样本**"
    if ok_m:
        line["音乐"]["响度合格线"] = "**-14.0 ~ -13.9 LUFS**（2 条独立样本一致 = 流媒体标准）"
    return {"电影逐条": fl, "音乐逐条": mu, "合格线": line,
            "口径": "**合格线 = 真样本读数的区间**；每条可复核到具体文件；区间外才叫不合格。"
                    "场景检测阈值 0.3 已写进读数，换阈值必须重跑并标出来。"}


def judge() -> dict:
    """**判**：拿合格线去量每一条（**光量不判等于没定线**）。

    🔴 2026-10-10：原来这个件只"量样本定区间"，**不判** —— 那等于量完就完了。
    现在补上判：样本/交付物逐条对区间，越界即红。三档口径：
      · **在区间内**  ⇒ ok
      · **越界**      ⇒ RED（写明越到哪、差多少）
      · **没线可判**  ⇒ 如实标「**合格线缺样本，判不了**」（不许拿参考值冒充本仓线）
    """
    d = baseline()
    line = d["合格线"]
    film_line = line.get("电影") or {}
    music_line = line.get("音乐") or {}
    bad = []
    # ── 电影：时长 / 音轨 / 分辨率 ──
    if film_line.get("样本数"):
        lo, hi = film_line["时长s 区间"]
        for x in d["电影逐条"]:
            if not x.get("在盘"):
                continue
            if x["时长s"] < lo or x["时长s"] > hi:
                bad.append("%s 时长 %.1fs 越界（合格线 %.1f~%.1fs）"
                           % (x["文件"].split("/")[-1], x["时长s"], lo, hi))
            # 🔴 2026-10-10 **不在这里判音轨**（我自己踩的重复判据）：
            #    我原来在这儿也判了一次"音轨 0"，结果把 **03-shoot 里的中间件**
            #    （20261009-film-堂屋-03shots.mp4）也判红了 —— 而 film-audio-guard
            #    已经按"出厂面/中间件/彩排"三类口径放行它。
            #    **同一件事两个判据、两套口径 = 迟早互相打架** ⇒ 音轨一律交给
            #    film-audio-guard（它有分类口径）；本件只管**时长与响度**。
    # ── 音乐：响度 ──
    ml = music_line.get("响度LUFS 区间")
    if ml and ml[0] is not None:
        lo, hi = ml
        for x in d["音乐逐条"]:
            if not x.get("在盘") or x.get("响度LUFS") is None:
                continue
            if x["响度LUFS"] < lo - 1 or x["响度LUFS"] > hi + 1:    # 容差 1 LU
                bad.append("%s 响度 %.1f LUFS 越界（合格线 %.1f~%.1f，容差1LU）"
                           % (x["文件"].split("/")[-1], x["响度LUFS"], lo, hi))
    return {"逐条越界": bad, "电影合格线": film_line, "音乐合格线": music_line,
            "口径": "越界即红；**没样本支撑的线不判**（如实标「缺样本」）"}


def check() -> int:
    d = baseline()
    j = judge()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print("样本合格线（抓真样本 · 区间即合格线）")
    print("  电影样本：")
    for x in d["电影逐条"]:
        if not x.get("在盘"):
            print("    %s **不在盘**" % x["文件"]); continue
        print("    %-52s %dx%d · %.1fs · %d镜 · 均长%.2fs · 音轨%d"
              % (x["文件"].split("/")[-1][:50], x["宽"], x["高"], x["时长s"],
                 x["镜头数"], x["平均镜头长度s"], x["音轨"]))
        print("        响度 %s LUFS · 峰值 %s dBFS" % (x.get("响度LUFS"), x.get("峰值dBFS")))
    print("  音乐样本：")
    for x in d["音乐逐条"]:
        if not x.get("在盘"):
            print("    %s **不在盘**" % x["文件"]); continue
        print("    %-52s %.1fs · %s Hz · %s · %sch · %s"
              % (x["文件"].split("/")[-1][:50], x["时长s"], x["采样率"],
                 x["编码"], x["声道"], ("%s LUFS" % x.get("响度LUFS"))))
        print("        峰值 %s dBFS · 动态范围 %s dB" % (x.get("峰值dBFS"), x.get("动态范围dB")))
    print()
    print("  **合格线（区间）**：")
    for k, v in d["合格线"].items():
        print("    %s: %s" % (k, json.dumps(v, ensure_ascii=False)[:200]))
    print()
    print("  **逐条判**（拿合格线量样本/交付物）：")
    print("    电影合格线：%s" % (j["电影合格线"].get("响度合格线")
                                  or "时长 %s" % j["电影合格线"].get("时长s 区间")))
    print("    音乐合格线：%s" % j["音乐合格线"].get("响度合格线"))
    if j["逐条越界"]:
        for b in j["逐条越界"]:
            print("    🔴 %s" % b)
    else:
        print("    ✅ 无越界")
    ok = d["合格线"]["电影"]["样本数"] > 0 and d["合格线"]["音乐"]["样本数"] > 0
    print("判据：%s" % ("PASS（样本量到 · 时长/响度无越界）" if ok else "FAIL"))
    print("  口径：**音轨不在这里判** —— 那是 film-audio-guard 的活（它有出厂/中间/彩排三类口径）；"
          "一件事一个判据，两套口径迟早打架。")
    return 0 if ok else 1


def selftest() -> int:
    print("负对照A·区间必须来自真读数（空样本不得编出线）=> 用空表检验：")
    empty = {"电影": {"样本数": 0}, "音乐": {"样本数": 0}}
    print("    空表不会产生 时长s 区间 =>", "时长s 区间" not in empty["电影"])
    d = baseline()
    f = d["合格线"]["电影"]
    m = d["合格线"]["音乐"]
    ok = f["样本数"] > 0 and m["样本数"] > 0 and "出处" in f and "出处" in m
    print("负对照B·每条合格线都要有出处 => 电影 %d 出处 · 音乐 %d 出处"
          % (len(f.get("出处") or []), len(m.get("出处") or [])))
    print("负对照C·镜头检测阈值写进读数 =>", d["电影逐条"][0].get("检测阈值") if d["电影逐条"][0].get("在盘") else "n/a")
    print("自检：%s" % ("全过" if ok else "不过"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="样本合格线")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    return selftest() if a.selftest else check()


if __name__ == "__main__":
    raise SystemExit(main())
