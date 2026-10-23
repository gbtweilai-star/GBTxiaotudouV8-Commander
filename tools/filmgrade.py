# -*- coding: utf-8 -*-
"""filmgrade · 电影级**外观库**与生产审计（actioncam / filmkit 共用一件）
⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印

主人令（2026-09-27）：「想让她是什么样她就能变成什么样，这才是我们独有的能力——
别人是把调试交给智能体，我们是**和工具合体**，把工具变成创造之手，如臂使唤。」

所以这一件不只是"一条调色链"，而是：
  · **外观库 LOOKS**：一处定义 N 种味道（filmic / 做旧 / 潮湿阴冷 / 热血橙青 / 褪色胶片 / 黑白纪实 / 赛博霓虹）；
  · **人话取味 pick()**：说「潮湿阴冷」就取湿冷味、说「热血」就取橙青味——**词即指令**；
  · **先看再定 preview()**：单帧出样，定了再上全片（不盲拍）；
  · **共用**：actioncam 与 filmkit 同款引用 ⇒ 换配方两线同时变；
  · **QC()**：黑帧/卡帧/亮度机械化审计（总监令工作流第 1 步）。

配方出处：三板块总监令（块二）+ 修饰工坊五科目 + `编剧室/AAA画面技术蒸馏手册`（ACES 调色/胶片颗粒/暗角）。
⚠️ 表达式零逗号纪律照旧（min/if/pow 一律不用）；`cas`/`colorbalance`/`curves`/`gblur`/`blend` 均已实测可用。
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
QC_LEDGER = ROOT / "state" / "film_qc.jsonl"

# ── 外观库（一处定义 · 全线下发）──────────────────────────────────────
# 每条 = 完整 -vf 链（可含 split/blend 内部分支；零逗号表达式）
LOOKS: dict[str, dict] = {
    # 2026-10-13 加（主人令「每一个调节都要触手可控」）：**只调旋钮、不套味道**的出口。
    # 没有它的话，"只想提一点亮"会被迫连带套上某个味道 —— 那是**替用户加戏**。
    "原样": {
        "label": "原样（不套味道 · 只给补光旋钮用）",
        "chain": "null",
    },
    "filmic": {
        "label": "电影感（ACES 近似 · 默认）",
        "chain": ("curves=preset=medium_contrast,"
                  "colorbalance=rs=-0.05:bs=0.09:rm=0.03:bm=-0.02,"
                  "eq=saturation=1.08:gamma=0.97,cas=0.35,"
                  "split[a][b];[b]gblur=sigma=10[bb];[a][bb]blend=all_mode=screen:all_opacity=0.10,"
                  "vignette=PI/5,noise=alls={grain}:allf=t+u"),
    },
    "做旧": {
        "label": "做旧（《末班义庄》原味 · 潮湿阴冷老片）",
        # 🔴 2026-10-13 修「每一个调节都要触手可控」：这条链里原来把颗粒**写死成 6**（`noise=alls=6`），
        #    而别的味道都走 `{grain}` 占位符 ⇒ **「做旧」的颗粒根本不可调**（藏在代码里的常数）。
        #    改成 `{grain}`：默认值仍是 `default_grain()=6` ⇒ **行为一字不变**，但现在能被旋钮调。
        "chain": ("eq=brightness='0.022*sin(2*PI*t/2.7)':eval=frame,"
                  "noise=alls={grain}:allf=t,vignette=PI/5,eq=saturation=0.9:gamma_b=1.03"),
    },
    "潮湿阴冷": {
        "label": "潮湿阴冷（雨夜/尸气 · 冷青压暗）",
        "chain": ("colorbalance=rs=-0.08:bs=0.14:bm=-0.04,"
                  "eq=saturation=0.92:contrast=1.06:gamma=0.95,cas=0.30,"
                  "vignette=PI/4.5,noise=alls={grain}:allf=t+u"),
    },
    "热血橙青": {
        "label": "热血橙青（动作大片 · 强对比双色调）",
        "chain": ("curves=preset=strong_contrast,"
                  "colorbalance=rs=-0.10:bs=0.16:rm=0.10:bm=-0.08,"
                  "eq=saturation=1.16:contrast=1.10,cas=0.45,"
                  "vignette=PI/5.5,noise=alls={grain}:allf=t"),
    },
    "褪色胶片": {
        "label": "褪色胶片（回忆/旧照 · 提黑降饱和）",
        "chain": ("curves=preset=vintage,eq=saturation=0.74:contrast=0.94:gamma=1.05,"
                  "colorbalance=rm=0.06:bm=0.06,noise=alls={grain}:allf=t+u,vignette=PI/4"),
    },
    "黑白纪实": {
        "label": "黑白纪实（粗粝 · 无彩高对比）",
        "chain": ("hue=s=0,eq=contrast=1.14:gamma=0.96,cas=0.40,"
                  "noise=alls={grain}:allf=t+u,vignette=PI/4.5"),
    },
    "赛博霓虹": {
        "label": "赛博霓虹（未来都市 · 品青饱和）",
        "chain": ("curves=preset=strong_contrast,"
                  "colorbalance=rs=0.06:bs=0.14:rm=0.10:bm=-0.06,"
                  "eq=saturation=1.22:contrast=1.08,cas=0.40,"
                  "noise=alls={grain}:allf=t"),
    },
    "none": {"label": "不调色（自备）", "chain": "null"},
}

# 人话取味表：词 → 外观（**词即指令**）
INTENT_MAP = [
    (r"潮湿|阴冷|雨|湿|尸|阴森|恐怖|怕|冷", "潮湿阴冷"),
    (r"做旧|义庄|老片|旧|年代|民国|古", "做旧"),
    (r"热血|燃|爆|爽|大片|橙青|动作|激", "热血橙青"),
    (r"褪色|老照片|回忆|怀旧|泛黄|往", "褪色胶片"),
    (r"黑白|纪实|粗粝|冷硬|素", "黑白纪实"),
    (r"赛博|霓虹|未来|电子|科幻|机械", "赛博霓虹"),
    (r"电影|默认|film|正常", "filmic"),
]


def default_grain() -> int:
    return 6


# ── 补光族：**可独立调的旋钮**（不整包走味道）────────────────────────────
# 主人令 2026-10-13「每一个调节都要触手可控」：原来只想"提一点亮"也得整包换味道 ——
# 没有独立旋钮 ＝ 那个调节不可控。这里给出四个，键名与 ffmpeg `eq` 同款（不另造词）。
ADJUST_LIMITS = {"brightness": (-1.0, 1.0), "contrast": (0.0, 3.0),
                 "saturation": (0.0, 3.0), "gamma": (0.1, 10.0)}


def adjust_chain(adjust: dict | None = None) -> str:
    """把 `{旋钮: 数值}` 编成 ffmpeg `eq` 片段。**只认那四个键**，越界/不认 ⇒ 抛（由调用方 fail-closed）。"""
    a = dict(adjust or {})
    if not a:
        return ""
    bad = sorted(k for k in a if k not in ADJUST_LIMITS)
    if bad:
        raise ValueError("adjust 里不认这些旋钮：%s（只认 %s）" % (bad, sorted(ADJUST_LIMITS)))
    parts = []
    for k, (lo, hi) in ADJUST_LIMITS.items():
        if k in a and a[k] is not None:
            v = float(a[k])
            if not (lo <= v <= hi):
                raise ValueError("adjust[%s]=%s 越界（只许 %s..%s）" % (k, v, lo, hi))
            parts.append("%s=%g" % (k, v))
    return ("eq=" + ":".join(parts)) if parts else ""


def grade_chain(spec: str = "filmic", grain: int | None = None) -> str:
    """取外观链（**共用件入口**）：`spec` 可以是外观名，也可以是人话（自动取味）。"""
    name = pick(spec)
    g = default_grain() if grain is None else int(grain)
    return LOOKS[name]["chain"].replace("{grain}", str(g))


def pick(intent: str) -> str:
    """人话 → 外观名。认得出就取味，认不出回落 `filmic`（并如实标回落）。"""
    s = (intent or "").strip()
    if s in LOOKS:
        return s
    for pat, name in INTENT_MAP:
        if re.search(pat, s):
            return name
    return "filmic"


def pick_explain(intent: str) -> dict:
    s = (intent or "").strip()
    if s in LOOKS:
        return {"intent": intent, "look": s, "how": "直接命中外观名"}
    for pat, name in INTENT_MAP:
        m = re.search(pat, s)
        if m:
            return {"intent": intent, "look": name, "how": f"命中词 {m.group(0)!r} → {LOOKS[name]['label']}"}
    return {"intent": intent, "look": "filmic", "how": "认不出 ⇒ 回落默认 filmic（如实标回落）"}


def looks_list() -> dict:
    return {"ok": True, "count": len(LOOKS),
            "looks": [{"name": k, "label": v["label"]} for k, v in LOOKS.items()],
            "口径": "外观名或人话都能用：pick('潮湿阴冷') → 潮湿阴冷；词即指令"}


def preview(src: str, spec: str = "filmic", out: str = "", grain: int | None = None,
            adjust: dict | None = None) -> dict:
    """**先看再定**：单帧出样（不盲拍）。给 src 图 + 外观（名或人话）→ 出一张样片。"""
    s = Path(src) if Path(src).is_absolute() else ROOT / src
    if not s.is_file():
        return {"ok": False, "error": f"源图不存在：{s}"}
    look = pick(spec)
    g = default_grain() if grain is None else int(grain)
    try:                                     # 补光族：味道链**后面**再追加独立旋钮
        adj = adjust_chain(adjust)
    except ValueError as e:                  # 越界/不认的键 ⇒ 当场拒（不许静默丢掉）
        return {"ok": False, "error": str(e), "adjust": dict(adjust or {})}
    chain = grade_chain(look, g) + (("," + adj) if adj else "")
    o = Path(out) if out else ROOT / "output" / f"look-preview-{look}.jpg"
    if not o.is_absolute():
        o = ROOT / o
    o.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["ffmpeg", "-y", "-i", str(s), "-vf", chain, "-frames:v", "1",
                        "-q:v", "2", str(o)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300, cwd=str(ROOT))
    ok = r.returncode == 0 and o.is_file() and o.stat().st_size > 0
    return {"ok": ok, "look": look, "label": LOOKS[look]["label"], "src": str(s),
            "out": str(o), "grain": g, "adjust": dict(adjust or {}), "how": pick_explain(spec)["how"],
            "error": (r.stderr or "")[-200:] if not ok else ""}


def structured_eval(film: Path, qc_result: dict | None = None) -> dict:
    """**结构化评估**（关键点 6：评估必须结构化、自动化，且**输出可路由的错误类型**）。

    四维（全部机械可判，不依赖 VLM）：
      · `technical`   技术缺陷：黑帧/卡帧（blackdetect + freezedetect）
      · `sharpness`   清晰度：`blurdetect` 的模糊置信度均值
      · `motion`      运动合理性：帧间差分（tblend=difference）的亮度均值 —— 太低=PPT、太高=崩
      · `consistency` 一致性：全片色度（U/V 均值）离散度 —— 越小说明色调越统一

    **差异化路由**（不是给一个总分就完事）：
      技术缺陷 → `rerender`（重渲该段）· 清晰度低 → `regen`（源图太软，重出图+降档）
      运动低 → `remount`（换运镜）· 一致性差 → `unify_look`（统一外观）
    """
    film = Path(film)
    if not film.is_file():
        return {"ok": False, "error": f"成片不在：{film}"}
    q = qc_result or qc(film, label="structured_eval")
    # 清晰度：**边缘能量**（edgedetect + signalstats 的 YAVG 均值）
    # 为什么不用 blurdetect：实测它对平滑画面退化出 `nan`（全帧 nan ⇒ 均值毒化 ⇒ 误路由重出图）；
    # 边缘能量的标定（2026-09-27 同片三档）：原片 1.4551 · gblur σ2 = 0.6828 · gblur σ6 = 0.129
    # ⇒ **阈值 0.6**（低于轻模糊档即判"太软"），方向：越大越锐。
    sharp = None
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(film), "-vf",
                            "edgedetect=low=0.05:high=0.15,signalstats,"
                            "metadata=print:key=lavfi.signalstats.YAVG",
                            "-f", "null", "-"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1800, cwd=str(ROOT))
        vals = [float(x.split("=")[-1]) for x in (r.stderr or "").splitlines()
                if "YAVG=" in x and x.split("=")[-1].strip()]
        vals = [v for v in vals if v == v and abs(v) != float("inf")]
        sharp = round(sum(vals) / len(vals), 4) if vals else None
    except Exception:                                          # noqa: BLE001
        sharp = None
    except Exception:                                          # noqa: BLE001
        blur = None
    # 运动（帧间差分亮度均值）
    motion = None
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(film), "-vf",
                            "tblend=all_mode=difference,signalstats,"
                            "metadata=print:key=lavfi.signalstats.YAVG",
                            "-f", "null", "-"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1800, cwd=str(ROOT))
        vals = [float(x.split("=")[-1]) for x in (r.stderr or "").splitlines()
                if "YAVG=" in x and x.split("=")[-1].strip()]
        motion = round(sum(vals) / len(vals), 3) if vals else None
    except Exception:                                          # noqa: BLE001
        motion = None
    # 一致性（U/V 均值离散度）
    cons = None
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(film), "-vf",
                            "signalstats,metadata=print:key=lavfi.signalstats.UAVG,"
                            "metadata=print:key=lavfi.signalstats.VAVG",
                            "-f", "null", "-"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1800, cwd=str(ROOT))
        us = [float(x.split("=")[-1]) for x in (r.stderr or "").splitlines()
              if "UAVG=" in x and x.split("=")[-1].strip()]
        if us:
            m = sum(us) / len(us)
            var = sum((u - m) ** 2 for u in us) / len(us)
            cons = round(var ** 0.5, 3)
    except Exception:                                          # noqa: BLE001
        cons = None
    scores = {
        "technical": {"black": q.get("black"), "freeze": q.get("freeze"),
                      "ok": q.get("black") == 0 and q.get("freeze") == 0},
        "sharpness": {"edge_energy": sharp, "calib": "原片1.455/σ2=0.683/σ6=0.129 ⇒ 阈值0.6",
                      "ok": (sharp is None) or (sharp >= 0.60)},
        "motion": {"frame_diff": motion,
                   # 标定（2026-09-27 三档）：纯静止幻灯片 0.001 · 剧情片慢推 1.185 · 动作片 7.228
                   # ⇒ 下端真基线是"零"不是"慢"：**下限 0.4**（只抓真静止/PPT 味），上限 60（抓抖动崩坏）。
                   #   ⚠️ 第一版下限定 1.5 ⇒ 剧情片被误判"运动太低→remount"（假红，已改）。
                   "calib": "静止0.001/剧情1.185/动作7.228 ⇒ 区间[0.4,60]",
                   "ok": (motion is None) or (0.4 <= motion <= 60)},
        "consistency": {"uv_spread": cons, "ok": (cons is None) or (cons <= 12.0)},
    }
    routes = []
    if not scores["technical"]["ok"]:
        routes.append({"dim": "technical", "route": "rerender", "why": "有黑帧/卡帧"})
    if not scores["sharpness"]["ok"]:
        routes.append({"dim": "sharpness", "route": "regen",
                       "why": f"边缘能量 {sharp} < 0.60（低于轻模糊档 ⇒ 源图太软）"})
    if not scores["motion"]["ok"]:
        routes.append({"dim": "motion", "route": "remount", "why": f"帧间差分 {motion} 不在健康区间 [1.5,60]"})
    if not scores["consistency"]["ok"]:
        routes.append({"dim": "consistency", "route": "unify_look", "why": f"色度离散 {cons} > 12（色调不统一）"})
    return {"ok": not routes, "film": str(film), "scores": scores, "routes": routes,
            "verdict": "通过" if not routes else "待路由重试",
            "口径": "四维机械可判；**输出可路由的错误类型**而非一个总分（关键点 6）"}


def deliver_check(film: Path) -> dict:
    """**交付编码三必查**（回读确认，不看自证）：
      ① `level` —— 虚高会让严格实现的硬件解码器**拒播**（用户看到"打不开"，不是"卡"）；
      ② 关键帧间隔 —— 太大则拖进度条要长段解码（"卡顿"）；-g 60（30fps 即 2s 上限）；
      ③ 音轨 —— `-c:a copy` 才**结构上不可能不同步**；重编码会引入采样点偏移（不可控）。
    """
    film = Path(film)
    if not film.is_file():
        return {"ok": False, "error": f"成片不在：{film}"}
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "stream=index,codec_type,codec_name,level,nb_frames:format=duration,size",
                        "-of", "json", str(film)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300, cwd=str(ROOT))
    try:
        info = json.loads(r.stdout or "{}")
    except Exception:                                          # noqa: BLE001
        return {"ok": False, "error": "ffprobe 读不出"}
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), {})
    # GOP：数关键帧（用 packet flags）
    r2 = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                         "-show_entries", "packet=flags", "-of", "csv=p=0", str(film)],
                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                        timeout=600, cwd=str(ROOT))
    flags = (r2.stdout or "").splitlines()
    kf = sum(1 for f in flags if "K" in f)
    gop = round(len(flags) / kf, 1) if kf else None
    # GOP 按**秒**判（手册口径：-g 60 在 30fps ≈ 2s 上限）——按帧数判会放走 25fps 的 112 帧（4.5s）
    fps = 25.0
    try:
        rr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                             "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", str(film)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=120, cwd=str(ROOT))
        num, den = (rr.stdout or "25/1").strip().split("/")
        fps = float(num) / float(den or 1) or 25.0
    except Exception:                                          # noqa: BLE001
        pass
    gop_sec = round(gop / fps, 2) if gop else None
    lvl = v.get("level")
    issues = []
    if lvl and int(lvl) > 40:
        issues.append({"项": "level", "读得": lvl, "应为": "1080p→40 / 720p→31",
                       "后果": "严格实现的硬件解码器可能拒播（文件好好的，用户打不开）"})
    if gop_sec and gop_sec > 2.5:
        issues.append({"项": "关键帧间隔", "读得": f"{gop} 帧 ≈ {gop_sec}s", "应为": "≤2.0s（-g 60@30fps）",
                       "后果": "拖进度条要长段解码，表现成卡顿"})
    return {"ok": not issues, "film": str(film), "fps": fps,
            "video": {"codec": v.get("codec_name"), "level": lvl, "nb_frames": v.get("nb_frames")},
            "audio": {"codec": a.get("codec_name")},
            "keyframes": kf, "gop_frames": gop, "gop_seconds": gop_sec,
            "size_mb": round(int(info.get("format", {}).get("size") or 0) / 1048576, 1),
            "issues": issues,
            "口径": "三必查=level/关键帧(按秒)/音轨；**回读确认**，不看脚本自证"}


def deliver_ladder(film: Path, out_dir: Path | None = None, ref_start: float = 0.0,
                   ref_secs: float = 20.0, audio_bitrate: str = "192k") -> dict:
    """**多档阶梯（先测曲线再定档）**：抽代表片段做无损参考 → 各档重编 → SSIM 量化损失。

    判据（手册口径）：≥0.99 视觉无损 / ≥0.98 极佳 / ≥0.97 良好（可作移动档）/ <0.96 仅弱网兜底。

    档位默认（对齐手册实测）：主档 1080p crf22 level4.0 · 移动 720p crf22 level3.1 ·
    省流 960x540 crf24 level3.1 · 兜底 640x360 crf24 level3.0；**全部 `-g 60` + `-c:a copy`**。
    """
    film = Path(film)
    if not film.is_file():
        return {"ok": False, "error": f"成片不在：{film}"}
    out_dir = Path(out_dir) if out_dir else ROOT / "output" / (film.stem + "-ladder")
    out_dir.mkdir(parents=True, exist_ok=True)
    T = [("主档", 1920, 1080, 22, 40), ("移动", 1280, 720, 22, 31),
         ("省流", 960, 540, 24, 31), ("兜底", 640, 360, 24, 30)]
    ref = out_dir / "_ref-lossless.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(ref_start), "-t", str(ref_secs),
                    "-i", str(film), "-c:v", "libx264", "-qp", "0", "-an", str(ref)],
                   capture_output=True, timeout=1200, cwd=str(ROOT))
    # ⚠️ 参考分辨率**必须现读**（2026-09-27 实测踩坑：写死 1080p，而 720p 母版的参考片是 720p
    #    ⇒ 候选升到 1080p 与参考尺寸不齐 ⇒ ssim 不吐数、四档全 None）。
    ref_w, ref_h = 1920, 1080
    try:
        rp = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                             "-show_entries", "stream=width,height", "-of", "csv=p=0", str(ref)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=120, cwd=str(ROOT))
        w0, h0 = (rp.stdout or "").strip().split(",")[:2]
        ref_w, ref_h = int(w0), int(h0)
    except Exception:                                          # noqa: BLE001
        pass
    rows = []
    for name, w, h, crf, level in T:
        cand = out_dir / f"{name}-{w}x{h}.mp4"
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(ref_start), "-t", str(ref_secs),
                            "-i", str(film), "-vf", f"scale={w}:{h}:flags=bicubic",
                            "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                            "-level", f"{level/10:.1f}", "-g", "60", "-an", str(cand)],
                           capture_output=True, timeout=1800, cwd=str(ROOT))
        if r.returncode != 0 or not cand.is_file():
            rows.append({"tier": name, "ok": False, "err": (r.stderr or "")[-160:]})
            continue
        # SSIM：候选升回参考分辨率再比（模拟观众在大屏上看低码率档的真实观感）
        # ⚠️ 两步走、**不用 `-lavfi` 带标签的图**：2026-09-27 实测那条图在本版 ffmpeg 上
        #    出不了帧（`Could not open encoder before EOF`），而最简 `-lavfi ssim` 正常。
        #    也不许 `-v error`（SSIM 摘要是 info 级，会被自己筛丢）。
        up = out_dir / f"_up-{name}.mp4"
        ru = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(cand),
                             "-vf", f"scale={ref_w}:{ref_h}:flags=lanczos",
                             "-c:v", "libx264", "-qp", "0", "-an", str(up)],
                            capture_output=True, timeout=1200, cwd=str(ROOT))
        ssim = None
        if ru.returncode != 0:
            rows.append({"tier": name, "ok": False,
                         "err": "升采样失败：" + (ru.stderr or "").strip()[-140:]})
            continue
        if ru.returncode == 0 and up.is_file():
            s = subprocess.run(["ffmpeg", "-i", str(up), "-i", str(ref), "-lavfi", "ssim",
                                "-f", "null", "-"], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=1800, cwd=str(ROOT))
            for tok in ((s.stderr or "") + (s.stdout or "")).replace("\n", " ").split():
                if tok.startswith("All:"):
                    try:
                        ssim = round(float(tok.split(":")[1]), 4)
                    except ValueError:
                        pass
            try:
                up.unlink()
            except OSError:
                pass
        verdict = ("视觉无损" if ssim and ssim >= 0.99 else "极佳" if ssim and ssim >= 0.98 else
                   "良好(移动档)" if ssim and ssim >= 0.97 else "仅弱网兜底" if ssim else "未测")
        rows.append({"tier": name, "size": f"{w}x{h}", "crf": crf, "level": level / 10,
                     "mb": round(cand.stat().st_size / 1048576, 1), "ssim": ssim,
                     "verdict": verdict, "file": cand.name})
    ok = all(r.get("ssim") for r in rows)
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "film": str(film),
           "ref_secs": ref_secs, "tiers": rows}
    try:
        p = ROOT / "state" / "deliver_ladder.jsonl"
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return {"ok": ok, "film": film.name, "out_dir": str(out_dir), "tiers": rows,
            "口径": "档位不靠感觉：SSIM 测曲线定档；≥0.99 视觉无损 / ≥0.97 良好 / <0.96 兜底"}


def qc(film: Path, label: str = "") -> dict:
    """生产审计（总监令工作流第 1 步机械化）：黑帧 / 卡帧 / 亮度区间；写追加式 QC 台账。"""
    film = Path(film)
    if not film.is_file():
        return {"ok": False, "error": f"成片不在：{film}"}
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(film), "-vf",
         "blackdetect=d=0.10:pix_th=0.06,freezedetect=n=-60dB:d=0.45,"
         "signalstats,metadata=print:key=lavfi.signalstats.YAVG",
         "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=1800, cwd=str(ROOT))
    err = r.stderr or ""
    black = [x for x in err.splitlines() if "black_start" in x]
    freeze = [x for x in err.splitlines() if "freeze_start" in x]
    yavg = [float(x.split("=")[-1]) for x in err.splitlines()
            if "YAVG=" in x and x.split("=")[-1].strip()]
    verdict = "通过" if (not black and not freeze and yavg) else "不通过"
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "label": label or film.name,
           "film": str(film), "black_segments": len(black), "freeze_segments": len(freeze),
           "yavg_min": min(yavg) if yavg else None, "yavg_max": max(yavg) if yavg else None,
           "verdict": verdict}
    try:
        QC_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with QC_LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return {"ok": verdict == "通过", "verdict": verdict, "black": len(black),
            "freeze": len(freeze),
            "yavg": [min(yavg), max(yavg)] if yavg else None,
            "sample": (black[:2] + freeze[:2]),
            "ledger": str(QC_LEDGER)}
