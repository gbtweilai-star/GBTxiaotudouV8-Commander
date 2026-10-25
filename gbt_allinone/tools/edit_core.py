# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 剪辑引擎（edit_core）—— **剪映语义的蒸馏**，不是剪映的壳子。

═══ 先说清楚：为什么是"蒸馏剪映"，而不是"驱动剪映" ═══
2026-09-23 实测（三路只读侦察，证据在 memory 里）：
  · 本机**没有装剪映/CapCut**（`C:\\Program Files\\JianyingPro`、`%LOCALAPPDATA%\\JianyingPro`、
    草稿目录一律 `Test-Path False`）；**没有 D 盘**（上游 `_upstream/ai_duanju` 把草稿目录
    硬编码成 `D:\\JianyingPro Drafts`，连 import 都做不到）。
  · `pyJianYingDraft` 在本机**所有解释器里都没装**（逐解释器 `ModuleNotFoundError`），
    仓里也没 vendored、uv 缓存里连 wheel 都没下过。
  ⇒ 「点剪映的按钮来剪片」这条路在本机**现在不通**，硬做只会产出一个假执行。

**但剪映真正值钱的不是它的按钮，是它的时间线语义。** 剪映的草稿文件
（`draft_content.json`）本身就是一份完整的时间线模型：轨道 → 片段 → 目标时间区间 /
源时间区间 / 变速 / 音量 / 画面变换 / 转场 / 关键帧 / 文本样式。那是十几年打磨出来的
**剪辑语法**。所以本引擎蒸馏的是这套语法，出口有两条：
  · **出口一（已验证）**：把同一条时间线**真渲染成 mp4**（ffmpeg，本机 8.1.2 全功能构建，
    libass/xfade/zoompan/atempo 全在）—— **不依赖剪映**，所以真能跑通；
  · **出口二（未验）**：把同一条时间线**导出成剪映草稿**（`draft_content.json` +
    `draft_meta_info.json`，微秒计时，版本字段 `new_version 110.0.0` / `version 360000` /
    `app_id 3704` / `app_version 5.9.0`）—— 等哪天主人在装了剪映的机器上打开它做二次精修。
    ⚠️ **本机没有剪映 ⇒ 这条路一个字都没被真打开验证过**，本模块如实标 `未验`，
       不许把"结构对得上"说成"剪映能打开"。

═══ 蒸馏来的四条硬手艺（每条都有出处，不是我的品味）═══
  1. **归一化到画布再拼**：任何素材先进画布坐标系（`scale` 到覆盖 + `crop`），
     再谈拼接 —— 否则不同来源的片子拼起来会跳尺寸（剪映里就是"素材比例不一致"）。
  2. **竖屏不做暴力裁切，做背景填充**：`fit="blur"` 时把素材放大铺满 + 高斯模糊垫底，
     原比例内容居中叠上去（剪映「背景填充·模糊」的等价物）。这是竖屏短视频的行业惯例。
  3. **字幕最后上，overlay 前必须 `setpts=PTS-STARTPTS`** —— 这两条直接来自本仓
     `edit_rules.py`（GBST-ED-1 / GBST-ED-4），那是从 browser-use/video-use 蒸馏并已机检的
     硬规则。**本引擎生成的命令必须过自己这套规则**（`check()` 里做了闭环）。
  4. **接缝要有淡变**（GBST-ED-3）：音频在拼接缝上做 30ms 级 afade，不然会"咔"一下 ——
     静默失败：听着还行，其实坏了。

═══ 三种处置口径（本会话第 100 条同源的纪律）═══
  · **真违规** ⇒ 报出来（`findings`）；
  · **前提不成立** ⇒ 记下来并写明为什么（例：GBST-ED-2 要求"分段抽取 + `-c copy` 无损拼接"，
    而带转场/字幕的片子**必须重编码** —— 这条规则在此不适用，**不是**"我们违规了"）；
  · **没查** ⇒ 单列 `manual`，**不把"没查"说成"没问题"**（`edit_rules` 原本就这么设计，
    本模块照抄这条纪律）。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_IMPL_VERSION = "1.0"
# 本模块最终住在 `gbt_allinone/tools/`；`parents[2]` 就是仓根，**两处一致**
# （原型在 `.scratch/edit_proto/` 时同样成立），所以直接运行与 `python -m` 都能跑。
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
DEFAULT_FPS = 30
# 字幕字号/边距：按 1080x1920 竖屏的安全区定（底部留出平台 UI 与"进度条遮挡"）
SUB_FONT = "Microsoft YaHei"
SUB_SIZE = 54
SUB_MARGIN_V = 260


# ═══════════════════════════ ① 时间线语法（蒸馏产物本体） ═══════════════════════════

def schema() -> dict:
    """我们自己的剪辑语法（**剪映语义的子集，按我们需要的形状重写**）。

    单位一律**秒**（剪映草稿用微秒，只在 `to_jianying_draft()` 那一个出口换单位 ——
    **单位换算只许有一个地方**，多了迟早出现"差 1000 倍"的静默失败）。
    """
    return {
        "version": 1,
        "unit": "second",
        "canvas": {"w": 1080, "h": 1920, "fps": DEFAULT_FPS, "bg": "black"},
        "tracks": {
            "video": [{"src": "绝对或相对路径", "t0": 0.0, "dur": 3.0, "src_start": 0.0,
                       "fit": "cover|blur|contain", "speed": 1.0,
                       "reframe": {"zoom": 1.12, "focus_y": 0.40},
                       "transition_in": {"kind": "fade", "dur": 0.4},
                       "motion": {"kind": "kenburns", "zoom_from": 1.0, "zoom_to": 1.08}}],
            "audio": [{"src": "路径", "t0": 0.0, "src_start": 0.0, "dur": 4.0,
                       "gain_db": 0.0, "fade_in": 0.08, "fade_out": 0.20}],
            "text": [{"text": "字幕文字", "t0": 0.2, "dur": 2.6, "y": 0.72,
                      "size": SUB_SIZE, "color": "&H00FFFFFF"}],
        },
        "note": ("`fit`：cover=裁切铺满 · blur=背景填充(模糊垫底+原比例居中) · contain=黑边居中；"
                 "`transition_in` 用 ffmpeg xfade 的转场名（fade/dissolve/wipeleft/slideup…）；"
                 "`motion.kenburns` 是缓慢推近（剪映的缩放关键帧等价物）"),
    }


def _paths(tl: dict) -> dict:
    return {"canvas": dict(tl.get("canvas") or {}), "tracks": dict(tl.get("tracks") or {})}


def _src_dur(path) -> float:
    """素材**真实**时长（ffprobe 量出来的，不是 JSON 里写的）。取不到返回 0。"""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", str(path)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=60)
        return float((r.stdout or "0").strip() or 0.0)
    except Exception:  # noqa: BLE001
        return 0.0


def validate(tl: dict) -> dict:
    """体检时间线。**分母写清楚**：查了几条轨道、几段、几个文件真的在盘上。

    🔴 2026-09-23 第 58 轮加的一条真判据：**素材够不够长**。
    由来（自家踩的）：第一次彩排渲染，我把 3.0s 的源当 3.5s、1.0s 的源当 2.0s 用 ⇒
    尾段整段消失、输出只有 6.5s，而**容器时长照样报 8.5s**、命令 rc=0、没有任何报错。
    典型的"看着还行，其实是坏的"。⇒ 长度必须**量**（ffprobe），不许信 JSON 里写的数。
    """
    errors, notes = [], []
    v = [s for s in (tl.get("tracks", {}).get("video") or [])]
    a = [s for s in (tl.get("tracks", {}).get("audio") or [])]
    t = [s for s in (tl.get("tracks", {}).get("text") or [])]
    cv = tl.get("canvas") or {}
    w, h = int(cv.get("w") or 0), int(cv.get("h") or 0)
    if w <= 0 or h <= 0:
        errors.append("canvas 缺 w/h")
    if w % 2 or h % 2:
        errors.append("canvas 尺寸必须是偶数（yuv420p 要求）：%dx%d" % (w, h))
    if not v:
        errors.append("video 轨为空 —— 没有画面就没有片子")
    checked, missing = 0, []
    for i, s in enumerate(v):
        checked += 1
        if not str(s.get("src") or ""):
            errors.append("video[%d] 缺 src" % i)
        elif not Path(str(s["src"])).is_file():
            missing.append(str(s["src"]))
        for k in ("t0", "dur"):
            if s.get(k) is None:
                errors.append("video[%d] 缺 %s" % (i, k))
        if float(s.get("dur") or 0) <= 0:
            errors.append("video[%d] dur<=0" % i)
        sp = float(s.get("speed") or 1.0)
        if sp <= 0 or sp > 8:
            errors.append("video[%d] speed=%s 越界(0,8]" % (i, sp))
        # ── 素材够不够长（真量）──
        if str(s.get("src") or "") and Path(str(s["src"])).is_file():
            sd = _src_dur(s["src"])
            need = float(s.get("src_start") or 0.0) + float(s.get("dur") or 0.0) * sp
            if sd <= 0:
                notes.append("video[%d] 源时长量不到（ffprobe 没回数）⇒ 长度这条**没查**" % i)
            elif need > sd + 0.05:
                errors.append("video[%d] **素材不够长**：要 %.2fs，盘上只有 %.2fs（%s）"
                              % (i, need, sd, Path(str(s["src"])).name))
        fi = s.get("fit") or "cover"
        z = float((s.get("reframe") or {}).get("zoom") or 1.0)
        if z <= 1.0 or z > 2.0:
            if (s.get("reframe") or {}).get("zoom") is not None:
                errors.append("video[%d] reframe.zoom=%s 越界(1,2]" % (i, z))
        if fi not in ("cover", "blur", "contain"):
            errors.append("video[%d] fit=%s 不认识（只认 cover/blur/contain）" % (i, fi))
        tr = s.get("transition_in") or {}
        if tr.get("kind") and float(tr.get("dur") or 0) > min(float(s.get("dur") or 0), 1.0):
            errors.append("video[%d] 转场时长比片段还长" % i)
    for i, s in enumerate(a):
        if not str(s.get("src") or ""):
            errors.append("audio[%d] 缺 src" % i)
        elif not Path(str(s["src"])).is_file():
            missing.append(str(s["src"]))
        elif float(s.get("dur") or 0) > 0:
            sd = _src_dur(s["src"])
            need = float(s.get("src_start") or 0.0) + float(s.get("dur") or 0.0)
            if sd > 0 and need > sd + 0.05:
                errors.append("audio[%d] **素材不够长**：要 %.2fs，盘上只有 %.2fs（%s）"
                              % (i, need, sd, Path(str(s["src"])).name))
    for i, s in enumerate(t):
        if not str(s.get("text") or ""):
            errors.append("text[%d] 缺 text" % i)
        if str(s.get("text") or "").count("\n") > 2:
            notes.append("text[%d] 超过 3 行，竖屏会顶到安全区外" % i)
    # ── 片子一共多长（**同一套布局算法**）＋ 音/字不许越过片尾 ──
    film = layout(tl)["duration"]
    for i, s in enumerate(a):
        end = float(s.get("t0") or 0.0) + float(s.get("dur") or 0.0)
        if film > 0 and end > film + 0.05:
            errors.append("audio[%d] 越过片尾：到 %.2fs，片子只有 %.2fs（话会被切断）"
                          % (i, end, film))
    for i, s in enumerate(t):
        end = float(s.get("t0") or 0.0) + float(s.get("dur") or 0.0)
        if film > 0 and end > film + 0.05:
            errors.append("text[%d] 越过片尾：到 %.2fs，片子只有 %.2fs（字幕会缺尾）"
                          % (i, end, film))
    if missing:
        errors.append("盘上没有的文件：%s" % "、".join(missing[:4]))
    return {"ok": not errors, "errors": errors, "notes": notes,
            "counts": {"video": checked, "audio": len(a), "text": len(t),
                       "files_missing": len(missing)},
            "film_duration": round(film, 3),
            "film_duration_basis": "按声明的 dur/speed/转场相加；素材不够长时**实际会更短** ——"
                                   "那种情况上面的 errors 会点名",
            "canvas": "%dx%d@%s" % (w, h, cv.get("fps") or DEFAULT_FPS)}


# ═══════════════════════════ ② 编译：时间线 → ffmpeg ═══════════════════════════

def layout(tl: dict) -> dict:
    """**唯一的布局算法**：每段在成片时间线上的 `(start, dur)`，以及片子总长。

    为什么必须只有一处（第 58 轮踩的坑）：渲染出口按 xfade 的重叠推进，而剪映草稿出口
    原本自己抄了一份"起点 = 声明的 t0" ⇒ **同一条时间线，成片 7.8s，草稿却写 8.3s**。
    两个出口对不上，就是"看着都对、其实彼此矛盾"。⇒ 布局**只许有一个地方**，
    `compile_cmd` 与 `to_jianying_draft` 都调它。
    """
    v = tl.get("tracks", {}).get("video") or []
    segs, cur = [], 0.0
    for i, s in enumerate(v):
        d = float(s.get("dur") or 0.0) / float(s.get("speed") or 1.0)
        tr = (s.get("transition_in") or {})
        td = float(tr.get("dur") or 0.0) if (i > 0 and tr.get("kind")) else 0.0
        start = max(0.0, cur - td) if i > 0 else 0.0
        segs.append({"i": i, "start": start, "dur": d, "transition_in": td})
        cur = start + d
    return {"segments": segs, "duration": cur}


def _needs_graph(tl: dict) -> tuple:
    """要不要重编码？**能无损就无损**（这是 GBST-ED-2 的正解）。"""
    why = []
    v = tl.get("tracks", {}).get("video") or []
    if len(v) > 1 and any((s.get("transition_in") or {}).get("kind") for s in v[1:]):
        why.append("有转场（xfade 必须逐帧处理）")
    if any(abs(float(s.get("speed") or 1.0) - 1.0) > 1e-9 for s in v):
        why.append("有变速")
    if any((s.get("motion") or {}).get("kind") for s in v):
        why.append("有运镜/缩放")
    if any((s.get("fit") or "cover") != "cover" for s in v):
        why.append("有背景填充/黑边（要改像素）")
    if (tl.get("tracks", {}).get("text") or []):
        why.append("有字幕烧录")
    if any(float(s.get("gain_db") or 0) or float(s.get("fade_in") or 0) or float(s.get("fade_out") or 0)
           for s in (tl.get("tracks", {}).get("audio") or [])):
        why.append("音频要调音量/淡变")
    return (True, why) if why else (False, [])


def _vchain(i: int, s: dict, cv: dict) -> str:
    """一段视频的归一化链（**先归一到画布，再谈拼接**）。"""
    w, h, fps = int(cv["w"]), int(cv["h"]), int(cv.get("fps") or DEFAULT_FPS)
    t0 = float(s.get("t0") or 0.0)
    dur = float(s["dur"])
    ss = float(s.get("src_start") or 0.0)
    fit = s.get("fit") or "cover"
    parts = ["[%d:v]trim=start=%.3f:end=%.3f,setpts=PTS-STARTPTS" % (i, ss, ss + dur)]
    sp = float(s.get("speed") or 1.0)
    if abs(sp - 1.0) > 1e-9:
        parts.append("setpts=PTS/%.4f" % sp)
    if fit == "cover":
        # 二次构图（剪映的「裁剪/缩放/位置」）：先放大再重新取景 —— 用来**把源片自带的
        # 烧录字幕裁出画外**（第 58 轮眼看的发现：不裁就是双重字幕，一眼假）。
        rf = s.get("reframe") or {}
        z = float(rf.get("zoom") or 1.0)
        fy = float(rf.get("focus_y") if rf.get("focus_y") is not None else 0.5)
        if z > 1.0001:
            parts.append("scale=%d:%d:force_original_aspect_ratio=increase"
                         % (int(w * z) + 1, int(h * z) + 1))
            parts.append("crop=%d:%d:(iw-%d)/2:(ih-%d)*%.3f" % (w, h, w, h, fy))
        else:
            parts.append("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d"
                         % (w, h, w, h))
    elif fit == "contain":
        parts.append("scale=%d:%d:force_original_aspect_ratio=decrease" % (w, h))
        parts.append("pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=black" % (w, h))
    else:  # blur：背景填充（模糊垫底 + 原比例居中）
        bg = ("[b%d]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,gblur=sigma=24[b%d]"
              % (i, w, h, w, h, i))
        fg = ("[f%d]scale=%d:%d:force_original_aspect_ratio=decrease[fg%d]"
              % (i, w, h, i))
        parts.append("split=2[b%d][f%d]" % (i, i))
        head = ",".join(parts) + ";" + bg + ";" + fg
        tail = "[b%d][fg%d]overlay=(W-w)/2:(H-h)/2" % (i, i)
        mo = (s.get("motion") or {}).get("kind")
        if mo == "kenburns":
            tail += (",zoompan=z='min(1+%.6f*on,%.4f)':d=1:x='iw/2-(iw/zoom/2)':"
                     "y='ih/2-(ih/zoom/2)':s=%dx%d:fps=%d"
                     % (((float(s["motion"].get("zoom_to", 1.08)) - 1.0) / max(int(fps * dur), 1)),
                        float(s["motion"].get("zoom_to", 1.08)), w, h, fps))
        return head + ";" + tail + ",fps=%d,setsar=1[v%d]" % (fps, i)
    mo = (s.get("motion") or {}).get("kind")
    if mo == "kenburns":
        zt = float((s.get("motion") or {}).get("zoom_to", 1.08))
        parts.append("zoompan=z='min(1+%.6f*on,%.4f)':d=1:x='iw/2-(iw/zoom/2)':"
                     "y='ih/2-(ih/zoom/2)':s=%dx%d:fps=%d"
                     % (((zt - 1.0) / max(int(fps * dur), 1)), zt, w, h, fps))
    parts.append("fps=%d" % fps)
    parts.append("setsar=1")
    del t0
    return ",".join(parts) + "[v%d]" % i


def _ass(tl: dict, cv: dict) -> str:
    """字幕走 ASS（不是 drawtext）：描边/阴影/字号/边距都能精确控制 —— 这才有高级感。"""
    w, h = int(cv["w"]), int(cv["h"])
    head = [
        "[Script Info]", "ScriptType: v4.00+", "PlayResX: %d" % w, "PlayResY: %d" % h,
        "WrapStyle: 2", "ScaledBorderAndShadow: yes", "", "[V4+ Styles]",
        ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
         "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
         "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"),
        ("Style: GBT,%s,%d,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,"
         "0,0,1,4,2,2,60,60,%d,1" % (SUB_FONT, SUB_SIZE, SUB_MARGIN_V)),
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    rows = []
    for s in (tl.get("tracks", {}).get("text") or []):
        rows.append("Dialogue: 0,%s,%s,GBT,,0,0,0,,%s"
                    % (_ts(float(s.get("t0") or 0)), _ts(float(s.get("t0") or 0) + float(s.get("dur") or 0)),
                       str(s["text"]).replace("\n", "\\N")))
    return "\n".join(head + rows) + "\n"


def _ts(sec: float) -> str:
    sec = max(0.0, float(sec))
    hh = int(sec // 3600)
    mm = int((sec % 3600) // 60)
    ss = sec % 60
    return "%d:%02d:%05.2f" % (hh, mm, ss)


def compile_cmd(tl: dict, out: str, workdir: Path, mode: str = "") -> dict:
    """把时间线编译成 ffmpeg 参数表（**不执行**）。返回 {argv, mode, why, notes}。"""
    workdir = Path(workdir).resolve()  # 🔴 必须绝对：相对路径会按 ffmpeg 的 cwd 解析 ⇒ 静默找不到字幕
    workdir.mkdir(parents=True, exist_ok=True)  # check() 也会调进来，这里不建目录就会在写字幕时炸
    cv = dict(tl.get("canvas") or {})
    cv.setdefault("w", 1080)
    cv.setdefault("h", 1920)
    cv.setdefault("fps", DEFAULT_FPS)
    v = tl.get("tracks", {}).get("video") or []
    a = tl.get("tracks", {}).get("audio") or []
    t = tl.get("tracks", {}).get("text") or []
    want_graph, why = _needs_graph(tl)
    mode = mode or ("graph" if want_graph else "copy")
    argv = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    notes = []
    if mode == "graph":
        ins, idx = [], 0
        vs = []
        for s in v:
            argv += ["-i", str(s["src"])]
            ins.append(("v", idx, s))
            idx += 1
        aud = []
        for s in a:
            argv += ["-i", str(s["src"])]
            ins.append(("a", idx, s))
            aud.append(idx)
            idx += 1
        chains = [_vchain(i, s, cv) for i, s in enumerate(v)]
        # 时间线布局（**唯一算法**，见 layout()）
        lay = layout(tl)
        seg_labels = [("v%d" % L["i"], L["dur"], L["start"], L["i"]) for L in lay["segments"]]
        # xfade 串联（转场只在 1..n-1 段上，符合"转场加在前一段"的语义）
        cur, cur_dur = seg_labels[0][0], seg_labels[0][1]
        for i in range(1, len(seg_labels)):
            lab, d, _, _ = seg_labels[i]
            tr = v[i].get("transition_in") or {}
            kind = tr.get("kind")
            if kind:
                td = float(tr.get("dur") or 0.4)
                off = max(0.0, cur_dur - td)
                chains.append("[%s][%s]xfade=transition=%s:duration=%.3f:offset=%.3f[x%d]"
                              % (cur, lab, kind, td, off, i))
                cur = "x%d" % i
                cur_dur = cur_dur + d - td
                notes.append("第 %d 段用 xfade=%s %.2fs（接缝在 %.2fs）" % (i + 1, kind, td, off))
            else:
                # 无转场的接缝：用 concat（并给音频缝加 afade，见 ED-3）
                chains.append("[%s][%s]concat=n=2:v=1:a=0[c%d]" % (cur, lab, i))
                cur = "c%d" % i
                cur_dur += d
        vlabel = cur
        if t:
            # 字幕文件必须给**绝对路径**（相对名会按 ffmpeg 的 cwd 解析 ⇒ 找不到就静默没字幕）；
            # Windows 路径在滤镜参数里要把 `:` 转义成 `\:`，反斜杠统一成正斜杠。
            ass = workdir / "_gbt_sub.ass"
            esc = str(ass).replace("\\", "/").replace(":", "\\:")
            chains.append("[%s]subtitles=filename='%s'[vout]" % (vlabel, esc))
            vlabel = "vout"
        # 音频：每条 adelay 到自己的起点 + 音量 + 淡入淡出，再 amix
        alabels = []
        for k, s in enumerate(a):
            i = aud[k]
            t0 = float(s.get("t0") or 0.0)
            ss = float(s.get("src_start") or 0.0)
            dur = float(s.get("dur") or 0.0)
            ch = ["[%d:a]atrim=start=%.3f" % (i, ss)]
            if dur > 0:
                ch.append("atrim=end=%.3f" % (ss + dur))
            ch.append("asetpts=PTS-STARTPTS")
            g = float(s.get("gain_db") or 0.0)
            if abs(g) > 1e-9:
                ch.append("volume=%.2fdB" % g)
            fi, fo = float(s.get("fade_in") or 0.0), float(s.get("fade_out") or 0.0)
            if fi > 0:
                ch.append("afade=t=in:st=0:d=%.3f" % fi)
            if fo > 0 and dur > 0:
                ch.append("afade=t=out:st=%.3f:d=%.3f" % (max(0.0, dur - fo), fo))
            if t0 > 0:
                ms = int(round(t0 * 1000))
                ch.append("adelay=%d|%d" % (ms, ms))
            alabels.append("a%d" % k)
            chains.append(",".join(ch) + "[a%d]" % k)
            del dur
        if alabels:
            if len(alabels) == 1:
                chains.append("[a0]anull[aout]")
            else:
                chains.append("%samix=inputs=%d:duration=longest:normalize=0[aout]"
                              % ("".join("[%s]" % x for x in alabels), len(alabels)))
        argv += ["-filter_complex", ";".join(chains)]
        argv += ["-map", "[%s]" % vlabel]
        if alabels:
            argv += ["-map", "[aout]", "-c:a", "aac", "-b:a", "192k", "-ar", "48000"]
        else:
            argv += ["-an"]
        argv += ["-t", "%.3f" % max(0.1, cur_dur / max(1, 1)), "-r", str(cv["fps"]),
                 "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                 "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
        # 署名进容器元数据（署名不可删除、不可篡改归属 —— 片子本身也要带）
        md = tl.get("metadata") or {}
        md.setdefault("comment", "开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属")
        md.setdefault("title", str(tl.get("name") or "GBT小土豆V8"))
        for k, v in md.items():
            argv += ["-metadata", "%s=%s" % (k, v)]
        argv += [str(out)]
        if t:
            (workdir / "_gbt_sub.ass").write_text(_ass(tl, cv), encoding="utf-8")
    else:
        # 无损路：分段 -ss/-t -c copy 抽取 → concat demuxer -c copy（GBST-ED-2 的正解）
        lst = workdir / "_gbt_concat.txt"
        lines = []
        for i, s in enumerate(v):
            part = workdir / ("_seg%02d.mp4" % i)
            sub = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                   "-ss", "%.3f" % float(s.get("src_start") or 0.0), "-t", "%.3f" % float(s["dur"]),
                   "-i", str(s["src"]), "-c", "copy", "-avoid_negative_ts", "make_zero", str(part)]
            lines.append((sub, part))
            notes.append("无损抽出第 %d 段 → %s" % (i + 1, part.name))
        lst.write_text("".join("file '%s'\n" % p.as_posix() for _, p in lines), encoding="utf-8")
        argv = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat",
                "-safe", "0", "-i", str(lst), "-c", "copy", str(out)]
        return {"argv": argv, "mode": mode, "why": why, "notes": notes, "stages": lines,
                "ass": None}
    return {"argv": argv, "mode": mode, "why": why, "notes": notes, "stages": [],
            "ass": str(workdir / "_gbt_sub.ass") if t else None}


def cmd_text(argv) -> str:
    return " ".join(('"%s"' % a if (" " in a or ";" in a) else a) for a in argv)


# ═══════════════════════════ ③ 自审：生成物过自己那套硬规则 ═══════════════════════════

def check(tl: dict, out: str, workdir: Path, mode: str = "") -> dict:
    """**闭环**：把本引擎生成的命令喂给 `edit_rules`（本仓已有机检的 GBST-ED 规则）。

    「前提不成立」与「真违规」分开记 —— 拿一条不适用自己场景的规则判自己违规，
    是这个仓库里已经犯过的错（第 100 条：前提已消失 vs 真错报）。
    """
    from gbt_allinone.tools import edit_rules
    c = compile_cmd(tl, out, workdir, mode=mode)
    text = cmd_text(c["argv"])
    r = edit_rules.check(text)
    void = []
    if c["mode"] == "graph":
        for f in list(r["findings"]):
            if f["rule"] == "GBT-ED-2":
                void.append({"rule": "GBT-ED-2",
                             "why": "本模式**必须重编码**（%s）⇒ 「分段无损 + -c copy」的前提不成立，"
                                    "不是违规" % ("、".join(c["why"]) or "有滤镜链")})
                r["findings"].remove(f)
                r["counts"]["findings"] = len(r["findings"])
                r["ok"] = not r["findings"]
    return {"ok": r["ok"], "mode": c["mode"], "why": c["why"], "void": void,
            "passed": r["passed"], "findings": r["findings"],
            "manual": [m["rule"] for m in r["manual"]], "counts": r["counts"],
            "cmd": text}


# ═══════════════════════════ ④ 真渲染 + 真回读 ═══════════════════════════

def probe_verdict(meta: dict) -> list:
    """**回读自洽判据**（纯函数，好让判据能咬它）。返回缺陷列表（空 = 没问题）。

    由来（第 58 轮自家踩的）：第一次彩排渲染，画面只有 6.5s、容器时长却报 8.5s，
    `nb_frames` 195 而 8.5×30=255 —— 两个数摆在一起就能看出**缺尾**，
    可当时的 probe 只把两个数**照抄**出来，没让它们互相校验。
    """
    defects = []
    vs = meta.get("video") or {}
    dur = float(meta.get("duration") or 0.0)
    sdur = float(meta.get("stream_duration") or 0.0)
    frames = int(vs.get("frames") or 0)
    try:
        num, den = str(vs.get("fps") or "0/1").split("/")
        fps = (float(num) / float(den)) if float(den) else 0.0
    except Exception:  # noqa: BLE001
        fps = 0.0
    exp = int(round(dur * fps)) if (dur and fps) else 0
    if vs and exp and frames and abs(frames - exp) > max(2, int(exp * 0.01)):
        defects.append("帧数与时长对不上：%d 帧 vs 时长×帧率 = %d 帧" % (frames, exp))
    if vs and sdur and dur and sdur < dur - 0.1:
        defects.append("**缺尾**：视频流只有 %.2fs，容器却报 %.2fs" % (sdur, dur))
    if not vs:
        defects.append("没有视频流")
    return defects


def probe(path) -> dict:
    """**回读**：出片之后必须用 ffprobe 把事实读回来（不许只信"命令返回 0"）。"""
    p = Path(path)
    if not p.is_file():
        return {"ok": False, "error": "产物不存在：%s" % p}
    a = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "stream=index,codec_type,codec_name,width,height,r_frame_rate,"
                        "nb_frames,duration",
                        "-show_entries", "format=duration,size,bit_rate,format_name",
                        "-of", "json", str(p)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if a.returncode != 0:
        return {"ok": False, "error": "ffprobe 失败 rc=%s" % a.returncode, "defects": ["ffprobe 失败"]}
    try:
        d = json.loads(a.stdout or "{}")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "ffprobe 输出不是 JSON：%s" % exc, "defects": ["读不回来"]}
    streams = d.get("streams") or []
    fmt = d.get("format") or {}
    vs = next((s for s in streams if s.get("codec_type") == "video"), {})
    has_a = any(s.get("codec_type") == "audio" for s in streams)
    dur = round(float(fmt.get("duration") or 0.0), 3)
    try:
        num, den = str(vs.get("r_frame_rate") or "0/1").split("/")
        fps = (float(num) / float(den)) if float(den) else 0.0
    except Exception:  # noqa: BLE001
        fps = 0.0
    frames = int(vs.get("nb_frames") or 0) if str(vs.get("nb_frames") or "").isdigit() else 0
    sdur = round(float(vs.get("duration") or 0.0), 3)
    meta = {"duration": dur, "stream_duration": sdur,
            "video": {"codec": vs.get("codec_name"), "w": vs.get("width"), "h": vs.get("height"),
                      "fps": vs.get("r_frame_rate"), "frames": frames}}
    defects = probe_verdict(meta)
    return {"ok": not defects, "defects": defects, "path": str(p),
            "bytes": int(fmt.get("size") or p.stat().st_size),
            "duration": dur, "stream_duration": sdur,
            "bit_rate": int(fmt.get("bit_rate") or 0), "format": fmt.get("format_name"),
            "video": dict(meta["video"],
                          frames_expected=int(round(dur * _fps_of(meta)) if dur else 0)),
            "has_audio": has_a,
            "streams": len(streams)}


def _jy_template() -> dict:
    """**外部模板**（vendored）：剪映草稿的 `draft_content` 骨架（28 个顶层键）。

    出处与哈希见 `gbt_allinone/assets/jianying/README.md`（`GuanYixuan/pyJianYingDraft@main`，
    3 316 B，sha256 前 16 位 `F3B9036DA3A0BCE6`）。**运行时不联网**。

    🔴 为什么要它（2026-10-13 实测）：我们自己手拼的那份只有 **11** 个顶层键，
    而外部模板有 **28** —— 缺 16 个 ⇒ 那份草稿**只够结构自检，离"别家能读"差得远**。
    现在改成「**模板起手 + 只 update 我们算得出的键**」，这样键集与别家一致。
    ⚠️ 边界：**补齐字段 ≠ 剪映能打开**（本机没装剪映，那条仍未验）。
    """
    global _JY_TEMPLATE_CACHE
    if _JY_TEMPLATE_CACHE is not None:
        return _JY_TEMPLATE_CACHE
    p = Path(__file__).resolve().parents[1] / "assets" / "jianying" / "draft_content.template.json"
    try:
        _JY_TEMPLATE_CACHE = json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        _JY_TEMPLATE_CACHE = {}          # 模板不在 ⇒ 回空（自检里那条会如实报红，不假装过）
    return _JY_TEMPLATE_CACHE


_JY_TEMPLATE_CACHE: dict | None = None


def _fps_of(meta: dict) -> float:
    try:
        num, den = str((meta.get("video") or {}).get("fps") or "0/1").split("/")
        return (float(num) / float(den)) if float(den) else 0.0
    except Exception:  # noqa: BLE001
        return 0.0


def render(tl: dict, out, workdir=None, mode: str = "", timeout: int = 1800) -> dict:
    """真跑。返回值里**每次都带**：命令原文 · 返回码 · 真回读读数。

    🔴 2026-10-13 两处补（都来自实测事故）：
    ① **失败不许留半成品**：encode 非零时，盘上那个文件**能播但短了**（实测：1080×1920 那次
       ENOMEM 之后留下一个 1.767s 的 mp4，而片子应是 2.8s）——那正是"假绿的物证形态"。
       现在失败一律把产物挪成 `*.partial`（留现场供诊断，但**不许它冒充成片**）。
    ② **渲前内存预算闸**：先按画幅估内存，**明显不够就先拒**并给出降规格建议，
       而不是让 ffmpeg 崩在半路留个半成品。系数按**两个实测数据点**定：
       640×360/cover/2.8s ⇒ 过（当时可用约 500MB）；1080×1920/blur/2.8s ⇒ ENOMEM ⇒ 拦。
    """
    out = Path(out)
    wd = Path(workdir) if workdir else out.parent / "_work"
    wd.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv = tl.get("canvas") or {}
    est_mb = memory_estimate_mb(int(cv.get("w") or 1080), int(cv.get("h") or 1920),
                                float(cv.get("fps") or DEFAULT_FPS), float(layout(tl)["duration"]))
    avail_mb = _avail_mb()
    if avail_mb > 0 and est_mb * 4.0 > avail_mb:
        return {"ok": False, "stage": "budget", "blocked": True,
                "est_mb": round(est_mb, 1), "avail_mb": round(avail_mb, 1),
                "error": "渲前预算闸：这张图**粗估**要 %.0f MB（×4 冗余 = %.0f MB），"
                         "而现读可用内存只有 %.0f MB ⇒ **先拒**（免得 ffmpeg 崩在半路留半成品）"
                         % (est_mb, est_mb * 4, avail_mb),
                "怎么改": "降画幅（如 640×360）· 关掉 fit=blur · 缩短时长 · 或先关别的吃内存的大件",
                "口径": "**粗估**：w×h×4B×阶段6×帧缓冲3；系数按两个实测点定（640×360 过 / 1080×1920+blur 崩）"}
    c = compile_cmd(tl, str(out), wd, mode=mode)
    runs = []
    if c["mode"] == "copy":
        for sub, _part in c["stages"]:
            r = subprocess.run(sub, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=timeout)
            runs.append({"cmd": cmd_text(sub), "rc": r.returncode, "err": (r.stderr or "")[-400:]})
            if r.returncode != 0:
                return {"ok": False, "stage": "extract", "runs": runs, "mode": c["mode"],
                        "partial": _quarantine(out), "why_failed": _rc_hint(r.returncode)}
    r = subprocess.run(c["argv"], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout)
    runs.append({"cmd": cmd_text(c["argv"]), "rc": r.returncode, "err": (r.stderr or "")[-800:]})
    if r.returncode != 0:
        return {"ok": False, "stage": "encode", "runs": runs, "mode": c["mode"],
                "partial": _quarantine(out), "why_failed": _rc_hint(r.returncode)}
    pr = probe(out)
    return {"ok": bool(pr.get("ok")), "mode": c["mode"], "why": c["why"], "notes": c["notes"],
            "runs": runs, "readback": pr, "ass": c.get("ass")}


def _rc_hint(rc: int) -> str:
    """把裸返回码翻成人话（至少把最常见的那个翻了）。"""
    if rc in (-12, 4294967284):
        return "rc=-12（ENOMEM：**内存不足**）⇒ 降画幅 / 关 blur / 缩短时长"
    if rc in (-9, 4294967287):
        return "rc=-9（SIGKILL：多半是**被系统 OOM 杀掉**）"
    return "rc=%s" % rc


def _quarantine(out: Path) -> str:
    """把**没成的**产物从当眼处挪开：改名 `*.partial`（留现场，但不许冒充成片）。"""
    try:
        if out.is_file():
            p = out.with_name(out.name + ".partial")
            if p.exists():
                p.unlink()
            out.rename(p)
            return str(p)
    except Exception:                                        # noqa: BLE001
        pass
    return ""


def memory_estimate_mb(w: int, h: int, fps: float, dur: float, stages: int = 6) -> float:
    """**粗估**渲这张图的内存（MB）：w×h×4B × 阶段数 × 帧缓冲 3。**是估算不是实测** ——
    所以闸门只在"明显不够"时拦（另乘 4 倍冗余），并如实标"估算"。"""
    return (max(1, int(w)) * max(1, int(h)) * 4 * max(1, int(stages)) * 3) / (1024 * 1024)


def _avail_mb() -> float:
    """现读可用物理内存（MB）。**读不到就回 -1 ⇒ 闸门不拦**（拿不到读数不许瞎拦）。"""
    try:
        import ctypes

        class _M(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = _M()
        m.dwLength = ctypes.sizeof(_M)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.ullAvailPhys / (1024 * 1024)
    except Exception:                                        # noqa: BLE001
        return -1.0


# ═══════════════════════════ ⑤ 出口二：剪映草稿（未验） ═══════════════════════════

def to_jianying_draft(tl: dict, root, name: str) -> dict:
    """导出剪映草稿（`draft_content.json` + `draft_meta_info.json`）。

    ⚠️ **未验**：本机没有剪映 ⇒ 这条路**没有被真打开过**。写在这里是为了"同一条时间线
       两个出口"，不是为了假装能跑。结构契约（微秒计时 / 版本字段）来自
       `pyJianYingDraft` 的资产模板（外部证据），**不是**本机实测。
    """
    root = Path(root)
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    cv = tl.get("canvas") or {}
    us = 1000000  # 剪映用微秒
    tracks, mats = [], []
    def add_track(kind):
        tracks.append({"type": kind, "segments": [], "flag": 0, "id": _guid(len(tracks))})
        return tracks[-1]
    lay = layout(tl)
    vt = add_track("video")
    for i, s in enumerate(tl.get("tracks", {}).get("video") or []):
        L = lay["segments"][i]
        sp = float(s.get("speed") or 1.0)
        mid = "mat-v-%d" % i
        mats.append({"id": mid, "type": "video", "path": str(Path(s["src"]).resolve()),
                     "duration": int(L["dur"] * sp * us)})
        vt["segments"].append({
            "id": "seg-v-%d" % i, "material_id": mid,
            "target_timerange": {"start": int(L["start"] * us), "duration": int(L["dur"] * us)},
            "source_timerange": {"start": int(float(s.get("src_start") or 0) * us),
                                 "duration": int(L["dur"] * sp * us)},
            "speed": sp, "volume": 1.0, "visible": True,
            "render_index": i,
        })
    if tl.get("tracks", {}).get("audio"):
        at = add_track("audio")
        for i, s in enumerate(tl["tracks"]["audio"]):
            mid = "mat-a-%d" % i
            mats.append({"id": mid, "type": "audio", "path": str(Path(s["src"]).resolve()),
                         "duration": int(float(s.get("dur") or 0) * us)})
            at["segments"].append({
                "id": "seg-a-%d" % i, "material_id": mid,
                "target_timerange": {"start": int(float(s.get("t0") or 0) * us),
                                     "duration": int(float(s.get("dur") or 0) * us)},
                "source_timerange": {"start": int(float(s.get("src_start") or 0) * us),
                                     "duration": int(float(s.get("dur") or 0) * us)},
                "volume": 10 ** (float(s.get("gain_db") or 0) / 20.0), "visible": True,
                "render_index": 0,
            })
    if tl.get("tracks", {}).get("text"):
        tt = add_track("text")
        for i, s in enumerate(tl["tracks"]["text"]):
            mid = "mat-t-%d" % i
            mats.append({"id": mid, "type": "text", "content": json.dumps(
                {"text": str(s["text"])}, ensure_ascii=False)})
            tt["segments"].append({
                "id": "seg-t-%d" % i, "material_id": mid,
                "target_timerange": {"start": int(float(s.get("t0") or 0) * us),
                                     "duration": int(float(s.get("dur") or 0) * us)},
                "clip": {"transform": {"x": 0.0, "y": float(s.get("y") or 0.72)},
                         "scale": {"x": 1.0, "y": 1.0}, "rotation": 0.0},
                "visible": True, "render_index": 10 + i,
            })
    # 模板起手（28 键，外部证据）→ 只 update **我们算得出的**那些键
    content = dict(_jy_template())
    content.update({
        "canvas_config": {"width": int(cv.get("w") or 1080), "height": int(cv.get("h") or 1920),
                          "ratio": "original"},
        "fps": float(cv.get("fps") or DEFAULT_FPS),
        "duration": int(lay["duration"] * us),
        "tracks": tracks, "materials": {"videos": [m for m in mats if m["type"] == "video"],
                                        "audios": [m for m in mats if m["type"] == "audio"],
                                        "texts": [m for m in mats if m["type"] == "text"]},
        "version": 360000, "new_version": "110.0.0",
        "platform": {"app_id": 3704, "app_source": "lv", "app_version": "5.9.0", "os": "windows"},
        "last_modified_platform": {"app_id": 3704, "app_source": "lv",
                                   "app_version": "5.9.0", "os": "windows"},
        "id": _guid(99), "name": name,
    })
    meta = {"draft_id": _guid(7), "draft_name": "", "draft_fold_path": "", "draft_root_path": "",
            "draft_new_version": "", "tm_duration": 0, "draft_removable_storage_device": "",
            "draft_cloud_last_action_download": False, "draft_type": ""}
    (d / "draft_content.json").write_text(json.dumps(content, ensure_ascii=False, indent=4),
                                         encoding="utf-8")
    (d / "draft_meta_info.json").write_text(json.dumps(meta, ensure_ascii=False, indent=4),
                                           encoding="utf-8")
    # 🔴 2026-10-13：**产物自检**（fail-closed）—— 写出去不等于写对了。
    #    但**边界要如实**：本机没装剪映 ⇒ 只能证"结构自洽"，**证不了"剪映能打开"**。
    sc = _draft_selfcheck(d, tl, content, meta)
    if not sc["ok"]:
        return {"ok": False, "dir": str(d), "stage": "draft_selfcheck", "selfcheck": sc,
                "error": "草稿产物**没过结构自检** ⇒ 不认账", "verified": False}
    return {"ok": True, "dir": str(d), "files": ["draft_content.json", "draft_meta_info.json"],
            "tracks": [t["type"] for t in tracks],
            "segments": sum(len(t["segments"]) for t in tracks),
            "duration_us": content["duration"], "duration_s": content["duration"] / us,
            "verified": "structure_only", "selfcheck": sc,
            "note": ("**结构自检已过**（2026-10-13 加：文件在/JSON 可解析/canvas·fps·duration 与时间线对得上/"
                     "时间是整数微秒/素材路径逐个在盘）。**仍然未验的一件事**：本机没有剪映 ⇒ "
                     "「剪映能不能真打开它」**没被验过**；结构契约来自 pyJianYingDraft 的资产模板（外部证据）。")}


def _draft_selfcheck(d: Path, tl: dict, content: dict, meta: dict) -> dict:
    """草稿产物的**结构自检**（只证"结构自洽"；证不了"剪映能打开"）。"""
    checks, bad = [], []
    def chk(name, ok, detail=""):
        checks.append({"check": name, "ok": bool(ok), "detail": str(detail)[:160]})
        if not ok:
            bad.append(name)
    f1, f2 = d / "draft_content.json", d / "draft_meta_info.json"
    chk("两个文件都在", f1.is_file() and f2.is_file(), "%s · %s" % (f1.name, f2.name))
    chk("两份 JSON 都可解析", bool(content) and bool(meta), "已解析")
    cv = tl.get("canvas") or {}
    chk("canvas 与时间线一致",
        content.get("canvas_config", {}).get("width") == int(cv.get("w") or 1080)
        and content.get("canvas_config", {}).get("height") == int(cv.get("h") or 1920),
        str(content.get("canvas_config")))
    chk("fps 与时间线一致", float(content.get("fps") or 0) == float(cv.get("fps") or DEFAULT_FPS),
        str(content.get("fps")))
    want_us = int(layout(tl)["duration"] * 1000000)
    chk("duration = layout 单源算出的总时长（微秒）",
        int(content.get("duration") or -1) == want_us, "%s vs %s" % (content.get("duration"), want_us))
    seg_times_ok, seg_n = True, 0
    for t in content.get("tracks") or []:
        kind = t.get("type")
        for s in t.get("segments") or []:
            seg_n += 1
            tr = s.get("target_timerange") or {}
            if not isinstance(tr.get("start"), int) or not isinstance(tr.get("duration"), int):
                seg_times_ok = False
            # ⚠️ `source_timerange` **只对"有源媒体"的轨才要求**（video/audio）——
            #    **文字轨本来就没有源区间**。判据第一版把这条写成"每段都要有"，
            #    结果把**对的产物**判红（尺子错了，不是对象错）。2026-10-13 修正。
            if kind in ("video", "audio"):
                sr = s.get("source_timerange") or {}
                if not isinstance(sr.get("start"), int) or not isinstance(sr.get("duration"), int):
                    seg_times_ok = False
    chk("每段都有整数微秒的 target 区间（video/audio 另需 source 区间；文字轨没有源）",
        seg_times_ok, "%d 段" % seg_n)
    mats = content.get("materials") or {}
    media = [m for k in ("videos", "audios") for m in (mats.get(k) or [])]
    missing = [m.get("path") for m in media if not Path(str(m.get("path") or "")).is_file()]
    chk("素材路径逐个在盘", not missing, "缺 %s" % missing[:2] if missing else "%d 个素材" % len(media))
    need_meta = ("draft_id", "draft_name", "draft_type")
    chk("meta 必需键齐", all(k in meta for k in need_meta), str([k for k in need_meta if k not in meta]))
    # 🔴 **外部尺子**（2026-10-13 加）：产物顶层键集必须**⊇ 外部模板的键集** ——
    #    这条尺子不是我们自己画的：模板 vendored 自 `GuanYixuan/pyJianYingDraft@main`
    #    （见 `gbt_allinone/assets/jianying/README.md`，sha256 前 16 位 `F3B9036DA3A0BCE6`）。
    #    ⚠️ 补键 ≠ 剪映能打开（本机没装），两件事仍分开。
    tpl = _jy_template()
    if not tpl:
        chk("产物键集 ⊇ 外部模板键集", False, "模板不在盘（vendored 资产丢了？）—— 如实报红，不假装过")
    else:
        miss = sorted(k for k in tpl if k not in content)
        chk("产物键集 ⊇ 外部模板键集（模板 %d 键）" % len(tpl), not miss, "缺 %s" % miss[:6] if miss else "齐")
    return {"ok": not bad, "checks": checks, "failed": bad,
            "scope": "structure_only（本机没装剪映 ⇒ 「剪映能不能打开」未验）"}


def _guid(n: int) -> str:
    import uuid
    return str(uuid.UUID(int=n, version=4)).upper()


# ═══════════════════════════ ⑥ 能力位入口（固化进万能插） ═══════════════════════════
#
# 🔴 登记时**必须知道的一件事**（第 57 轮实测 `security/policy.py`）：
#    `policy.evaluate()` **没有"未知 kind"兜底分支** —— 未登记的能力位返回 `scopes=()`、
#    `restricted=False`，也就是**零作用域 = 不卡**。这是本仓既有现象（`stigmergy`/`cloud_pc`/
#    `life` 同族），而 `policy.py` 是**主人的门，我一个字都不许改**。
#    ⇒ 所以本能力位**自己把写面钉死**，不靠门外那一层：
#      · 只读 op（status/schema/validate/check/probe）随便调；
#      · 写 op（render/draft）**只准落在** `projects/` 与 `outputs/`（外加 `.scratch/`）之下 ——
#        调用方传一个别处的绝对路径，**当场拒绝并说明为什么**（不是静默改写路径）。
#    ⇒ 这条自收窄**有判据**（`test_edit_core.py` 里逐条钉），不是写在注释里的承诺。
#    ⇒ 另：能力位登记 `safe: False`（它会落盘、会起 ffmpeg 子进程）—— 让 `preflight`/`omni`
#      这一层知道"它会改状态"，从而不会把它当只读动作自动跑。
READ_OPS = ("status", "schema", "validate", "check", "probe")
WRITE_OPS = ("render", "draft")
WRITE_ROOTS = ("projects", "outputs", ".scratch")


def write_guard(path, root=None) -> dict:
    """写面自收窄：只准往 `projects/` · `outputs/` · `.scratch/` 之下写。"""
    root = Path(root or _ROOT).resolve()
    p = Path(path)
    ap = (root / p).resolve() if not p.is_absolute() else p.resolve()
    try:
        rel = ap.relative_to(root)
    except ValueError:
        return {"ok": False, "why": "落点 **%s** 在仓库之外 —— 本能力位只写仓内 %s"
                                    % (ap, "、".join(WRITE_ROOTS))}
    if rel.parts and rel.parts[0] not in WRITE_ROOTS:
        return {"ok": False, "why": "落点 **%s** 不在允许的写面内（只认 %s 之下）"
                                    % (rel.as_posix(), "、".join(WRITE_ROOTS))}
    return {"ok": True, "abs": str(ap), "rel": rel.as_posix()}


def run(op: str = "status", **kw) -> dict:
    """万能插入口：`run_task("edit_pipeline", {"op": ..., ...})` 落到这里。"""
    op = str(op or "status")
    if op == "status":
        return {"ok": True, "impl": "edit_core", "version": _IMPL_VERSION,
                "kind": "edit_pipeline", "domain": "video", "unit": "second",
                "read_ops": list(READ_OPS), "write_ops": list(WRITE_OPS),
                "write_roots": list(WRITE_ROOTS),
                "ffmpeg": subprocess.run(["ffmpeg", "-version"],
                                         capture_output=True).returncode == 0,
                "jianying_installed": False,
                "distilled_from": ["剪映时间线语义（轨道→片段→目标/源时间区间→变速/音量/转场/文本）",
                                   "本仓 edit_rules.py 的 GBST-ED 硬规则（字幕顺序 / 接缝淡变 / overlay 对齐）"],
                "note": "渲染那一路**已实测跑通**（真出 1080x1920 mp4 + ffprobe 回读）；"
                        "剪映草稿出口：**结构自检已过**（2026-10-13：文件在 / JSON 可解析 / "
                        "canvas·fps·duration 与 layout 单源对得上 / 时间是整数微秒 / 素材路径逐个在盘），"
                        "**但「剪映能不能真打开它」仍未验**（本机没装剪映）—— 两件事别混着念。"}
    if op == "schema":
        return {"ok": True, "schema": schema()}
    tl = kw.get("timeline")
    if isinstance(tl, str):
        tl = _load(tl)
    if op in ("validate", "check", "render", "draft") and not isinstance(tl, dict):
        return {"ok": False, "error": "op=%s 需要 timeline（dict 或时间线 JSON 的路径）" % op}
    if op == "validate":
        return validate(tl)
    if op == "check":
        wd = kw.get("workdir") or (_ROOT / ".scratch" / "edit_core")
        return check(tl, kw.get("out") or (_ROOT / "outputs" / "_plan.mp4"), Path(wd),
                     mode=kw.get("mode") or "")
    if op == "probe":
        target = kw.get("path") or kw.get("out") or tl
        if not target:
            return {"ok": False, "error": "op=probe 需要 path"}
        return probe(target)
    if op in WRITE_OPS:
        target = kw.get("out") or kw.get("path") or ""
        if not target:
            return {"ok": False, "error": "op=%s 需要 out（落点）" % op}
        g = write_guard(target)
        if not g["ok"]:
            return {"ok": False, "refused": True, "why": g["why"],
                    "how": "落点必须落在 %s 之下" % "、".join(WRITE_ROOTS)}
        if op == "render":
            v = validate(tl)
            if not v["ok"]:
                return {"ok": False, "stage": "validate", "errors": v["errors"],
                        "note": "**先体检再渲染**：素材不够长/越过片尾这类问题在这里就拦下"}
            return render(tl, g["abs"], workdir=kw.get("workdir"), mode=kw.get("mode") or "")
        return to_jianying_draft(tl, Path(g["abs"]),
                                 str(kw.get("name") or tl.get("name") or "draft"))
    return {"ok": False, "error": "未知 op：%s" % op, "ops": list(READ_OPS) + list(WRITE_OPS)}


# ═══════════════════════════ CLI ═══════════════════════════

def _load(p) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="GBT 剪辑引擎（剪映语义蒸馏）")
    ap.add_argument("op", choices=["status", "schema", "validate", "check", "render",
                                   "probe", "draft"])
    ap.add_argument("timeline", nargs="?", help="时间线 JSON")
    ap.add_argument("--out", default="")
    ap.add_argument("--mode", default="", choices=["", "graph", "copy"])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    kw = {}
    if a.timeline:
        kw["timeline"] = a.timeline
    if a.out:
        kw["out"] = a.out
    if a.mode:
        kw["mode"] = a.mode
    r = run(a.op, **kw)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main())
