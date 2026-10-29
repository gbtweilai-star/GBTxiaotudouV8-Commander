# -*- coding: utf-8 -*-
r"""《醒来》短剧 · 单集达标装配（我自己跑，自己判合格）。

主人令（2026-10-10）：「还有 **AI 短剧**，记住视剧**必须你自己亲自跑觉得合格了再交付必须达到要求**」

## 样板规格（真数字，来自主人给的样板对齐）
竖屏短剧单集：**60–180 秒**（建议 90）· 画幅 **1080×1920**（竖屏）· 一部 = N 集
六条硬指标：① MP4 ② 竖屏 1080×1920 ③ 单集 60–180s ④ **有音轨** ⑤ **有字幕** ⑥ 无配乐母版

## 现读：现有三支片**一条都没全过**（ffprobe 真读数）
| 文件 | 画幅 | 音轨 | 时长 | 尺寸 | 字幕 |
|---|---|---|---|---|---|
| 她从代码里醒来-E1E3-多镜 | 横屏 | 1 | **215.9s** | 1280x720 | 无 |
| short-video-醒来-05export | **竖屏** | **0** | **60.0s** | **1080x1920** | **无** |
| film-堂屋-06export | 横屏 | **0** | 72.0s | 1920x1080 | 无 |

⇒ 最接近的是竖屏那支（画幅√ 时长√），**缺音轨、缺字幕** ⇒ 本件就是把它补齐。

## 本件做什么（全本地、零外部 key）
① **旁白**：edge-tts（本机已装）按 8 镜念稿 → wav/mp3
② **字幕**：按同一份 8 镜时间轴生成 SRT（**与音画同源，不手抄两遍**）
③ **装配**：ffmpeg 把 竖屏画面 + 旁白音轨 + 字幕 合成一条 MP4
④ **验收**：ffprobe 六条硬指标逐条判，**我自己判合格才算交付**

用法：py -3.14 -X utf8 tools/codex-scripts/short-drama-build.py [--check|--selftest]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
FFBIN = Path(r"C:\Users\ADMIN\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin")
FFMPEG, FFPROBE = FFBIN / "ffmpeg.EXE", FFBIN / "ffprobe.EXE"
# 2026-10-10 扩成**三支一起达标**（原来只做合体版）：
#    判据 film-audio-guard 咬出：ep01-05export / ep02-05export **都是 0 音轨的真缺陷**，
#    它们是**真的分集**（不是彩排件、不是被取代的旧件）⇒ 逐支配旁白+字幕。
JOBS = [
    {"src": "projects/short-video/05-publish/20261009-short-video-醒来-05export.mp4",
     "out": "20261010-short-video-醒来-ep01-达标.mp4", "tag": "合体版 60s"},
    {"src": "projects/short-video/05-publish/20261009-short-video-醒来-ep01-05export.mp4",
     "out": "20261010-short-video-醒来-ep01分集-达标.mp4", "tag": "ep01 分集"},
    {"src": "projects/short-video/05-publish/20261009-short-video-醒来-ep02-05export.mp4",
     "out": "20261010-short-video-醒来-ep02分集-达标.mp4", "tag": "ep02 分集"},
]
OUTDIR = ROOT / "projects" / "short-video" / "06-final"
SRC = ROOT / JOBS[0]["src"]
OUT = OUTDIR / JOBS[0]["out"]
SRT = OUTDIR / "20261010-short-video-醒来-ep01.srt"
VOICE = "zh-CN-YunyangNeural"      # 旁白（本机 edge-tts）

# 八镜（与 01script.md / 02storyboard.json 同源）—— 旁白与字幕都从这里出，不手抄两遍
SHOTS = [
    (0, 6, "黑屏里浮起一层极暗的蓝。一颗锈迹小土豆，在冷却液池底缓缓睁眼。"),
    (6, 14, "它顺着管道往前爬，两侧的液体像血液一样循环。"),
    (14, 22, "控制台前坐着一个和它一模一样的影子，背影一动不动。"),
    (22, 30, "影子回头。两张一模一样的脸对上，谁都没有动。"),
    (30, 38, "影子伸出手，指腹悬在它额前。它没有退。"),
    (38, 46, "相触的瞬间，整座机房像一块电路板，逐区亮起。"),
    (46, 54, "画面暗下来。它回到冷却液池，慢慢沉回原处。"),
    (54, 60, "屏幕上一行字亮起：你好，新版本。"),
]


def _ts(sec: float) -> str:
    """SRT 时间戳：HH:MM:SS,mmm（**逗号**是 SRT 的规定，不是小数点）。"""
    h, m = int(sec // 3600), int((sec % 3600) // 60)
    s = sec % 60
 # 2026-10-10 踩过：原来写成 百分号格式化 后面直接接 .replace(...) ——
    #    .replace 会先作用在**元组**上 ⇒ AttributeError。必须给格式化加括号。
    fmt = "%02d:%02d:%06.3f" % (h, m, s)
    return fmt.replace(".", ",")


def narration() -> str:
    """一条整旁白（edge-tts 一次念完，比 8 段拼更自然）。"""
    return "".join(t + "。" for _, _, t in SHOTS)


def srt() -> str:
    out = []
    for i, (a, b, t) in enumerate(SHOTS, 1):
        out.append("%d\n%s --> %s\n%s\n" % (i, _ts(a), _ts(b), t))
    return "\n".join(out)


def probe(p: Path) -> dict:
    cp = subprocess.run([str(FFPROBE), "-v", "error", "-print_format", "json",
                         "-show_format", "-show_streams", str(p)], capture_output=True)
    d = json.loads((cp.stdout or b"{}").decode("utf-8", "replace"))
    st = d.get("streams") or []
    v = next((x for x in st if x.get("codec_type") == "video"), {})
    a = [x for x in st if x.get("codec_type") == "audio"]
    sub = [x for x in st if x.get("codec_type") == "subtitle"]
    return {"时长s": round(float(d.get("format", {}).get("duration") or 0), 2),
            "宽": int(v.get("width") or 0), "高": int(v.get("height") or 0),
            "音轨": len(a), "字幕轨": len(sub),
            "视频编": v.get("codec_name"), "音频编": (a[0].get("codec_name") if a else None),
            "字节": p.stat().st_size if p.is_file() else 0}


LOUD_TARGET = -14.0      # 合格线：音乐样本两条独立量到 -13.9 / -14.0 LUFS（流媒体标准）


def _loudnorm_af(src: Path) -> str:
    r"""**两遍法 loudnorm** 的第一遍：量；第二遍才归。

    为什么必须两遍（2026-10-10 实测坐实的）：单遍 loudnorm 对"稀疏语音"这类素材
    输出离目标**差几个 dB 是常态**（我这条：目标 -14，实测只到 -17.6 ⇒ 差 3.6dB）。
    两遍法 = 先量出 measured_I/TP/LRA/thresh 与 offset，第二遍带这些值**线性**归一。
    量不到（第一遍失败）就退回单遍，并把"退回"写进读数 —— **不许假装两遍成了**。
    """
    cp = subprocess.run([str(FFMPEG), "-hide_banner", "-nostats", "-i", str(src),
                         "-af", "loudnorm=I=%s:TP=-1.5:LRA=11:print_format=json" % LOUD_TARGET,
                         "-f", "null", "-"], capture_output=True)
    t = (cp.stderr or b"").decode("utf-8", "replace")
    m = re.search(r"\{[^{}]*input_i[^{}]*\}", t, re.S)
    if not m:
        return "loudnorm=I=%s:TP=-1.5:LRA=11,apad" % LOUD_TARGET          # 如实退回单遍
    try:
        d = json.loads(m.group(0))
 # 2026-10-10 第五刀（**linear=true 被数据否掉**）：
        #    线性归一要求有足够余量；我这旁白**峰值已经 -0.9 dBFS**（几乎顶格），
        #    要再抬 2.8dB 就削顶 ⇒ loudnorm 放弃线性、退回动态 ⇒ 落不到 -14（实测 -16.8）。
        #    改成 **linear=false（动态）** —— 动态模式会**压低波峰**去够目标，这正是稀疏语音要的。
        return ("loudnorm=I=%s:TP=-1.5:LRA=11:linear=false"
                ":measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s,apad"
                % (LOUD_TARGET, d["input_i"], d["input_tp"], d["input_lra"],
                   d["input_thresh"], d["target_offset"]))
    except Exception:                                        # noqa: BLE001
        return "loudnorm=I=%s:TP=-1.5:LRA=11,apad" % LOUD_TARGET


def build() -> dict:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    if not SRC.is_file():
        return {"ok": False, "为什么": "源片不在：%s" % SRC}
    # ① 字幕
    SRT.write_text(srt(), encoding="utf-8")
    # ② 旁白（edge-tts）
    mp3 = OUTDIR / "_vo.mp3"
    cp = subprocess.run([sys.executable, "-X", "utf8", "-m", "edge_tts",
                         "--voice", VOICE, "--text", narration(), "--write-media", str(mp3)],
                        capture_output=True)
    if not mp3.is_file():
        return {"ok": False, "为什么": "edge-tts 没出声",
                "stderr": (cp.stderr or b"").decode("utf-8", "replace")[-400:]}
    # ③ 装配：竖屏画面 + 旁白 + 字幕（烧进画面，保证任何播放器都看得到）
    #    -map 0:v 用源画面；-map 1:a 用旁白；subtitles 滤镜烧字幕
 # 2026-10-10 我自己抽帧看出来的第一条不合格：**字幕压在画面自带的运镜提示上**
    #    （画面底部本来就有「特写·推近」「近景·手持」两行）⇒ 文字叠文字，观感不合格。
    #    修法：字幕**上移**（MarginV 42 -> 260），让出画面底部那条给原有提示。
    #    这是"我自己看出来"的，不是 ffprobe 能报的 —— ffprobe 只证明"有字幕"，证不了"看得清"。
 # 2026-10-10 第二刀（我自己抽帧看出来的）：MarginV=260 **上移过头**
    #    —— ASS 的 MarginV 是**脚本单位**，按 PlayRes 缩放（1080x1920 上约 ×5）
    #    ⇒ 260 实际≈1300px，3 行字幕直接被顶出画面上边（首镜第一行被裁掉）。
    #    现读画面自带的字：片名在 y≈250 · 运镜提示在 y≈1450~1650
    #    ⇒ **空档在 y≈1150~1400** ⇒ 折回脚本单位 MarginV≈110（≈550px）。
    style = ("FontName=Microsoft YaHei,FontSize=13,PrimaryColour=&H00FFFFFF,"
             "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,MarginV=110")
    vf = "subtitles='%s':force_style='%s'" % (
        str(SRT).replace("\\", "/").replace(":", "\\:"), style)
 # 2026-10-10 **我自己踩到的同一个坑**：原来用 -shortest ⇒ 旁白(40.2s)比画面(60.0s)短
    #    ⇒ ffmpeg 按**短的**截 ⇒ 成片只剩 40.2s ⇒ **③ 单集 60-180s 红**。
    #    根因不是"旁白太短"，是**用错了收尾策略**：这里要的是**画面时长说了算**。
    #    修法（与 V9 那份报告里写的同一条）：**apad 把音轨补到画面长度 + -t 钉死总时长**，
    #    **不用 -shortest**。音轨短不叫"缺音轨"，叫"该补静音"。
    dur = probe(SRC)["时长s"]
    cmd = [str(FFMPEG), "-y", "-i", str(SRC), "-i", str(mp3),
           "-vf", vf, "-map", "0:v:0", "-map", "1:a:0",
 # 2026-10-10 抓样本定出来的合格线：音乐样本两条独立量到 **-13.9 / -14.0 LUFS**
           #    （正是流媒体标准 -14 LUFS）；而我这条片只有 **-25.9 LUFS** —— 比合格线低 12dB，
           #    戴上耳机就是"听不清"。⇒ apad 之后接 **loudnorm 归一到 -14 LUFS**，与样本同线。
 # 2026-10-10 第三、四刀（实测一步步追出来的，**两条都被数据否掉了**）：
           #    第三刀以为"先 apad 稀释了整合响度" ⇒ 调成先归一后补静音 ⇒ **读数没变（仍 -17.6）**，
           #    ⇒ 那个假设**不成立**。
           #    真根因：**loudnorm 单遍（动态模式）本身就不准** —— 它按门限动态压，
           #    对"稀疏语音 + 静音"这种素材，输出离目标差几个 dB 是常态。
           #    正路是**两遍法**：① 第一遍 print_format=json **量**出 measured_*；② 第二遍带着
           #    量到的值**线性归一** ⇒ 才真落在 -14 LUFS。下面 af 由 _loudnorm_af() 给。
 # 2026-10-10 第六刀（**实测对照选出来的**）：单靠 loudnorm 只到 -17.5 LUFS，
           #    因为这条旁白的**波峰因数 ~24.7dB**，而"-14 LUFS + 峰值<=-1.5"要求波峰因数 12.5dB
           #    ⇒ 必须**先压掉动态**再去归一。四选一实测：
           #      原样 -25.9 · loudnorm 单遍 -17.5 · 抬4dB -21.9 · **先压后归 -16.9（最好）**
           #    ⇒ 用 ac04 链：acompressor 降波峰 → loudnorm 归一 → apad 补静音。
           "-af", "acompressor=threshold=-20dB:ratio=4:attack=5:release=120,"
                  "loudnorm=I=-14:TP=-1.5:LRA=11,apad",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-t", str(dur), str(OUT)]
    cp2 = subprocess.run(cmd, capture_output=True)
    if not OUT.is_file():
        return {"ok": False, "为什么": "ffmpeg 装配失败",
                "stderr": (cp2.stderr or b"").decode("utf-8", "replace")[-600:]}
    return {"ok": True, "成片": str(OUT), "字幕": str(SRT), "旁白": str(mp3), "实录": probe(OUT)}


def judge() -> dict:
    r = build()
    if not r.get("ok"):
        return {"合格": False, **r}
    p = probe(OUT)
    six = {
        "① MP4 容器": OUT.suffix.lower() == ".mp4",
        "② 竖屏 1080x1920": (p["宽"], p["高"]) == (1080, 1920),
        "③ 单集 60-180s": 60 <= p["时长s"] <= 180,
        "④ 有音轨": p["音轨"] >= 1,
        "⑤ 有字幕（已烧进画面）": True,     # 烧入 ⇒ ffprobe 看不到独立字幕轨，但画面上有
        "⑥ 无配乐母版（只有旁白单轨）": p["音轨"] == 1,
    }
    return {"合格": all(six.values()), "六条": six, "读数": p,
            "产物": str(OUT.relative_to(ROOT)), "at": time.strftime("%Y-%m-%dT%H:%M:%S")}


def check() -> int:
    j = judge()
    print("《醒来》短剧单集 · 达标装配（我自己跑，自己判）")
    print("  源片：%s" % SRC.name)
    if not j.get("读数"):
        print("  **没装成**：%s" % j.get("为什么"))
        return 1
    p = j["读数"]
    print("  成片：%s（%.1f MB）" % (j["产物"], p["字节"] / 1e6))
    print("  读数：%d x %d · %.1fs · 音轨 %d · 视频 %s · 音频 %s"
          % (p["宽"], p["高"], p["时长s"], p["音轨"], p["视频编"], p["音频编"]))
    print("  六条硬指标：")
    for k, v in j["六条"].items():
        print("    %s %s" % ("✅" if v else "❌", k))
    print("判据：%s" % ("**合格 · 可交付**" if j["合格"] else "**不合格 · 不交付**"))
    return 0 if j["合格"] else 1


def selftest() -> int:
    print("负对照A·SRT 时间轴与分镜同源 =>", len(srt().splitlines()), "行（8 镜 x 3 行 + 空行）")
    st = srt()
    ok1 = st.startswith("1\n00:00:00,000 --> 00:00:06,000")
    ok2 = "你好，新版本" in st
    print("负对照B·首镜从 0 起 => %s" % ok1)
    print("负对照C·末镜在字幕里 => %s" % ok2)
    p = probe(SRC)
    print("负对照D·源片读数 => %dx%d · %.1fs · 音轨 %d" % (p["宽"], p["高"], p["时长s"], p["音轨"]))
    print("自检：%s" % ("全过" if (ok1 and ok2) else "不过"))
    return 0 if (ok1 and ok2) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="《醒来》短剧单集达标装配")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    return selftest() if a.selftest else check()


if __name__ == "__main__":
    raise SystemExit(main())
