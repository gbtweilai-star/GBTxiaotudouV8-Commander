# -*- coding: utf-8 -*-
"""视频流水线 · 单一编排器（模型无关 · 真门 · 账本）
对应封面「给 Harness 装上这六个插件，整条流程自动完成」。

    python tools/video/pipeline.py map            # 阶段地图（能力位/判据/回退）
    python tools/video/pipeline.py providers      # 后端可用性（本机实测）
    python tools/video/pipeline.py status         # 全链门检 + 写账本
    python tools/video/pipeline.py probe <mp4>    # 单片客观读数（时长/分辨率/帧率/音轨）
    python tools/video/pipeline.py run S3 --dry   # 看某阶段会落到谁、跑什么

六个插件 → 七个阶段（剪/批量/动效/素材/创意/精修 + 验收发布）：
  S0 素材       Generative Media（media-use / autoglm 生图族）
  S1 创意       Seedance Art（Ark：arkcli-gen → Seedance/Seedream；计费动作须先报价确认）
  S2 剪         Video Cut（videocut-skills 或 ffmpeg 兜底）
  S3 动效       HyperFrames（HTML→确定性 MP4）
  S4 批量       Remotion（React 模板 × N 数据）
  S5 精修       Video Use（EDL 混剪+自评估）或 ffmpeg 收尾
  S6 验收       客观读数（ffprobe）+ 人眼（截图/预览）
  S7 发布       账本 + 清单（废物不上线）
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import time

# 🔴 2026-09-26 补：Windows 管道/重定向下 stdout 回落 GBK，emoji 一打印就崩；与 self_model.py 同一款补丁
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


WS = pathlib.Path(__file__).resolve().parents[2]
OUT = WS / "video-out"                      # 成片/中间件落点（不入仓核心目录）
LEDGER = WS / ".video/ledger.json"
# 控制夹具落点（**与交付目录分开**）：selftest 的正/负例件放这儿，不放 video-out
CTRL = WS / "state" / "video-controls"

# ── 能力位（阶段只认它，不写死厂商）────────────────────────────────────────
CAPS = {
    "media.assets": "素材：生图/抠图/找图/BGM/SFX/图标",
    "media.creative": "创意：文/图 → 视频片段（云端模型）",
    "video.cut": "剪：切分/删段/拼接/口播清理",
    "video.motion": "动效：HTML/代码 → 确定性 MP4",
    "video.batch": "批量：模板 × 数据 → N 条成片",
    "video.finish": "精修：混剪/调色/字幕/音频收尾",
    "video.probe": "客观读数：时长/分辨率/帧率/音轨",
}

PROVIDERS = {
    "hyperframes": {
        "caps": ["video.motion"],
        "probe": ["npx", "--yes", "hyperframes@latest", "--version"],
        "notes": "Apache-2.0 · HTML+data-* → headless Chrome 逐帧 seek → FFmpeg 编码（确定性：同输入同输出）· 需 Node≥22+FFmpeg",
        "cmds": {"video.motion": "cd \"{project}\" && npx hyperframes render"},
    },
    "remotion": {
        "caps": ["video.batch", "video.motion"],
        "probe": ["npm", "view", "remotion", "version"],   # 引擎按项目安装；这里判"包可达+网络通"
        "notes": "帧编程（React）· 1 模板 × N 数据 = N 视频 · ⚠️ 本体为 source-available 许可，商用需确认",
        "cmds": {"video.batch": "cd \"{project}\" && npx remotion render {comp} \"{out}\""},
    },
    "ffmpeg": {
        "caps": ["video.cut", "video.finish", "video.probe"],
        "probe": ["ffmpeg", "-version"],
        "notes": "本机 8.1.2 · 无依赖、离线、可作任何环节的兜底",
        "cmds": {
            "video.cut": "ffmpeg -y -i \"{in}\" -ss {start} -to {end} -c copy \"{out}\"",
            "video.finish": "ffmpeg -y -i \"{in}\" -vf \"scale={w}:{h}\" -c:v libx264 -crf 18 -pix_fmt yuv420p \"{out}\"",
            "video.probe": "ffprobe -v error -show_entries format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate -of json \"{in}\"",
        },
    },
    "videocut": {
        "caps": ["video.cut"],
        "probe": None,          # 需 Codex 宿主 + Runtime ≥0.5.9（公开 v0.4.11 不满足）
        "notes": "中文口播专精（口误/停顿/重复句）；⚠️ 需 Codex CLI 宿主 + 独立 Runtime≥0.5.9 —— 公开版 0.4.11 不达标，暂不可用",
        "cmds": {},
    },
    "video-use": {
        "caps": ["video.finish", "video.cut"],
        "probe": None,          # 需 uv + ELEVENLABS_API_KEY（付费）⇒ 未装
        "notes": "多素材混剪 · 转录→EDL→渲染→**自评估**（每刀边界查跳切/爆音）· 需 uv + ElevenLabs Key（可换本仓 openai-whisper 免付费）",
        "cmds": {},
    },
    "arkcli": {
        "caps": ["media.creative", "media.assets"],
        "probe": ["arkcli", "--version"],
        "notes": "Seedance/Seedream（Ark 云端）· 走 gbt-arkcli 规程：调用前缀 + 登录闸 + 账号闸 + **计费先报价后确认**",
        "cmds": {"media.creative": "arkcli +gen ...（按 gbt-arkcli 规程；计费动作须人确认）"},
    },
    "autoglm": {
        "caps": ["media.assets"],
        "probe": ["python", "-c", "import PIL"],
        "notes": "本仓已装：autoglm-generate-image / -seedream / -remove-bg / -search-image",
        "cmds": {"media.assets": "（技能调用，不出命令行）"},
    },
}


def probe(provider: str):
    p = PROVIDERS[provider]
    if p["probe"] is None:
        return None, "需人工/额外前置（见 notes）"
    exe = p["probe"][0]
    found = shutil.which(exe)
    if found:
        exe = found
    else:
        import os
        cand = [pathlib.Path(os.environ.get("APPDATA", "")) / "npm" / f"{exe}.cmd"]
        hit = next((c for c in cand if c.exists()), None)
        if hit is None:
            return False, f"命令不在 PATH：{p['probe'][0]}"
        exe = str(hit)
    try:
        argv = [exe] + list(p["probe"][1:])
        shell = exe.lower().endswith((".cmd", ".bat", ".ps1"))
        r = subprocess.run(" ".join(f'"{x}"' if " " in x else x for x in argv) if shell else argv,
                           shell=shell, capture_output=True, text=True, timeout=90,
                           encoding="utf-8", errors="replace")
        return r.returncode == 0, ((r.stdout or r.stderr or "").strip().splitlines() or [""])[-1][:70]
    except Exception as e:
        return False, f"探测异常 {type(e).__name__}"


def resolve(cap: str, prefer: str | None = None):
    order = ([prefer] if prefer else []) + [k for k in PROVIDERS if k != prefer]
    tried = []
    for k in order:
        if cap not in PROVIDERS[k]["caps"]:
            continue
        ok, note = probe(k)
        if ok is True:
            return k, None
        tried.append(f"{k}({note})")
    return None, "无可用后端；已试：" + "; ".join(tried)


# ── 真门（ffprobe 读数，不认我写的字）──────────────────────────────────────
def video_probe(path: pathlib.Path):
    if not path.exists() or path.stat().st_size == 0:
        return None, f"缺文件 {path.name}"
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate",
                        "-of", "json", str(path)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        return None, f"ffprobe 失败：{(r.stderr or '')[:80]}"
    d = json.loads(r.stdout or "{}")
    streams = d.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    dur = float((d.get("format") or {}).get("duration") or 0)
    return {"duration": round(dur, 3), "video": v, "audio": a,
            "size": int((d.get("format") or {}).get("size") or path.stat().st_size)}, None


def gate_assets() -> tuple:
    """S0 素材：**真看素材在不在**（原来永久绿）。

    素材面 = video-out / media-use / assets/media。一个都没有 ⇒ 红并说清去哪找，
    **不许报"素材就位"**。
    """
    cands = [WS / "video-out", WS / "media-use", WS / "holo_pet" / "assets" / "media"]
    hit = []
    for d in cands:
        if d.is_dir():
            fs = [f for f in d.rglob("*") if f.is_file() and f.stat().st_size > 1024]
            if fs:
                hit.append("%s(%d 件)" % (d.name, len(fs)))
    return ((True, "素材面: " + ", ".join(hit)) if hit
            else (False, "**一个素材目录都没有**（找 media-use / video-out / assets/media）"))


def gate_creative() -> tuple:
    """S1 创意：**没做就必须说没做**（原来永久绿）。

    这一格的产物是"云上生成的片段"，而生成是**计费动作**（Ark/Seedance 须先报价确认）。
    ⇒ 判据不是"有没有云片段"（那要花钱），而是**如实**：
       · 有云片段            ⇒ 绿（附出处）
       · 没做（等主人确认计费）⇒ **红**，读数里写清"未做 + 卡在哪个确认"
    这正是本仓反静默律：**未做 ≠ 做了**，不许静默变绿。
    """
    d = WS / "video-out"
    # 🔴 2026-10-10 负对照咬出来的洞：原来 glob 写 "creative*"，把 creative-local.bak
    #    这种**非视频件**也算成片段 ⇒ 成片被挪走后仍然绿。
    #    ⇒ 收紧成**真视频后缀**，并且必须**能被 ffprobe 解出视频流**才算片段（不认文件名）。
    vids = []
    if d.is_dir():
        for p in d.glob("creative*"):
            if not p.is_file() or p.stat().st_size <= 1024:
                continue
            if p.suffix.lower() not in (".mp4", ".mov", ".mkv", ".webm"):
                continue
            info, err = video_probe(p)
            if not err and info.get("video"):
                vids.append(p)
    clips = vids
    if clips:
        # 🔴 2026-10-10 修标签：原来一律写「云片段」，而 creative-local.mp4 是**本地触手录的**
        #    ⇒ 把本地的说成云上的，又是"读数与事实不符"。**按文件名如实分**。
        local = [p for p in clips if "local" in p.name.lower()]
        cloud = [p for p in clips if "local" not in p.name.lower()]
        parts = []
        if local:
            parts.append("**本地录制**: " + ", ".join(p.name for p in local[:3])
                         + "（触手 see · desktop_control · 不花钱）")
        if cloud:
            parts.append("云片段: " + ", ".join(p.name for p in cloud[:3]) + "（计费动作）")
        return True, " · ".join(parts)
    return False, ("**未做** —— 两条路都还没走：云生成是**计费动作**（须主人先确认报价）；"
                   "本地录制走 tools/video/tentacle-record.py --frames N（触手 see，已授权、不花钱）")


def gate_hf_check() -> tuple:
    """S3 的**前置门**：读**声明后端自己那道六域门**的判决（绑工程哈希）。

    🔴 2026-10-10 补（目标①"用本仓编排器/声明后端，不手搓平行实现"）：
    S3 原来只有我自己写的两条（能解码 + 真有画面变化）—— 那只覆盖**我看得见的两个维度**。
    声明后端 hyperframes 自己有一道**六域门**（Lint / Runtime / Layout / Motion / Contrast / Snapshots），
    其中 **Layout（含接缝处瞬时重叠）与 Contrast（WCAG AA）是我根本没想到要查的**。
    ⇒ 判决由 tools/video/hf-check.py 跑并落盘（约 74s，不能塞进每次 status）；
      本门只读判决 + **核新鲜度**：**工程哈希不符 ⇒ 判决作废、必须重跑**（与 S2/S12 同一套反静默手法）。
    """
    import importlib.util as _u
    p = WS / "tools" / "video" / "hf-check.py"
    if not p.is_file():
        return False, "缺 tools/video/hf-check.py（六域门没得跑）"
    sp = _u.spec_from_file_location("_hfchk", p)
    m = _u.module_from_spec(sp)
    sp.loader.exec_module(m)
    st = m.status()
    if not st.get("新鲜"):
        return False, "**六域门判决不新鲜**：%s（记录 %s… / 现在 %s…）⇒ 跑 hf-check.py run" % (
            st.get("为什么") or st.get("why"), st.get("记录哈希"), st.get("现在哈希"))
    if not st.get("ok"):
        return False, "六域门**没过**：%s" % st.get("逐域")
    d = st.get("逐域") or {}
    return True, ("六域门（声明后端自己的）: " + " · ".join("%s %s" % (k, v) for k, v in d.items())
                  + " · %.0fs前跑的" % (st.get("耗时s") or 0))


def gate_motion(path: pathlib.Path, min_motion=0.2, fps=4) -> tuple:
    """S3 动效：**产物必须真有画面变化**（视频域的真读数，不靠文件名）。

    🔴 2026-10-10 补：现读发现 video-out/motion.mp4（S3「动效(HyperFrames)」那一格的产物）
    **帧间差平均 0.000、最大 0.000** —— 也就是**一动不动**。
    而 S3 原来的门只查"文件在且能解码"⇒ **全程绿**。
    ⇒ 阶段名叫"动效"、产物是死帧，这是比门报错更坏的一类：门全绿、东西不能看。
    判法：抽 4fps 缩到 64x36 灰度，逐帧算与前一帧的平均绝对差；低于阈值即红。

    🔴 阈值怎么定的（**现读三个真件，不是我拍的**，同一把尺子 64x36 灰度）：
        · 死帧（旧的 motion.mp4）           平均 **0.000**  ← 要拒的就是它
        · 慢动效（hyperframes 渲的 title card，淡入+光晕呼吸）平均 **0.474**
        · 强运动（横移+进度条走满的版本）     平均 **3.202**
      ⇒ 阈值取 **0.2**：把"恒为 0 的死帧"和"确实在变的画面"分开。
      **不取 1.5** —— 那会把合法的慢动效（淡入）也误杀；也不取 0 —— 那等于不判。
      口径：**这条判据管的是"有没有在动"，不是"动得够不够好看"**；好不好看是审美，归人看。
    """
    import tempfile
    if not path.is_file():
        return False, "缺 %s" % path.name
    td = pathlib.Path(tempfile.mkdtemp(prefix="gbt_mot_"))
    pat = td / "f%05d.png"
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(path),
                        "-vf", f"fps={fps},scale=64:36", str(pat)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        return False, "抽帧失败：%s" % (r.stderr or "")[:80]
    try:
        from PIL import Image
    except Exception:                                                  # noqa: BLE001
        return False, "PIL 不在，画面变化判不了"
    files = sorted(td.glob("*.png"))
    ds, prev = [], None
    for f in files:
        cur = list(Image.open(f).convert("L").getdata())
        if prev is not None:
            ds.append(sum(abs(a - b) for a, b in zip(cur, prev)) / len(cur))
        prev = cur
    n = len(files)
    for f in files:
        f.unlink()
    try:
        td.rmdir()
    except OSError:
        pass
    if not ds:
        return False, "抽到的帧不够算变化（%d 帧）" % n
    avg, mx = sum(ds) / len(ds), max(ds)
    ok = avg >= min_motion
    return ok, ("画面变化 平均 %.3f / 最大 %.3f（阈 %.1f）%s"
                % (avg, mx, min_motion, "" if ok else " ⇒ **一动不动，这不叫动效**"))


def gate_video(path: pathlib.Path, min_dur=0.4, need_audio=False, min_w=320):
    info, err = video_probe(path)
    if err:
        return False, err
    v = info["video"]
    if not v:
        return False, "无视频流"
    w, h = int(v.get("width") or 0), int(v.get("height") or 0)
    checks = [info["duration"] >= min_dur, min(w, h) >= min_w, (info["audio"] is not None) or not need_audio]
    note = (f"{info['duration']}s · {w}x{h} · {v.get('r_frame_rate')} · "
            f"音轨{'有' if info['audio'] else '无'} · {info['size']/1024:.0f}KB")
    return all(checks), note


S = lambda **kw: kw                                                      # noqa: E731
STAGES = [
    # 🔴 2026-10-10 **这三条原来是永久绿**（gate=lambda: (True, "……")）——
    #    无论有没有产物都报 ✅。这与在数字人 S2 上抓到的假绿是**同一类病**：
    #    判据不对着产物量，就只是装饰。三条各自装上真判据。
    S(id="S0", name="素材", cap="media.assets", gate=lambda: gate_assets(),
      note="生图/抠图/找图/BGM/SFX", fallback="media-use 目录 + autoglm 技能"),
    S(id="S1", name="创意(生成)", cap="media.creative", gate=lambda: gate_creative(),
      note="Seedance/Seedream（Ark）", fallback="本地录制/录屏代替"),
    S(id="S2", name="剪", cap="video.cut",
      gate=lambda: gate_video(OUT / "cut-demo.mp4") if (OUT / "cut-demo.mp4").exists()
      else (False, "待产出 video-out/cut-demo.mp4"),
      note="videocut（中文口播）或 ffmpeg", fallback="ffmpeg -c copy 无损切"),
    # 🔴 2026-10-10 加第二道：光"有文件能解码"不够 —— **必须有画面变化**。
    #    现读抓到 motion.mp4 帧间差恒 0.000（死帧）却全程绿 ⇒ 现在它会红。
    S(id="S3", name="动效(HyperFrames)", cap="video.motion",
      # 三层一起判（**不是替掉谁，是叠上去**）：
      #   ① 声明后端自己的六域门（工程改了就作废）② 产物能解码 ③ 产物真有画面变化
      gate=lambda: (lambda a, b, c: ((a[0] and b[0] and c[0]),
                                     " · ".join(x[1] for x in (a, b, c) if x[1])))(
          gate_hf_check(),
          gate_video(OUT / "motion.mp4") if (OUT / "motion.mp4").exists()
          else (False, "待产出 video-out/motion.mp4"),
          gate_motion(OUT / "motion.mp4") if (OUT / "motion.mp4").exists()
          else (False, "待产出 video-out/motion.mp4")),
      note="HTML → 确定性 MP4", fallback="Remotion 渲染同段"),
    S(id="S4", name="批量(Remotion)", cap="video.batch",
      gate=lambda: gate_video(OUT / "batch.mp4") if (OUT / "batch.mp4").exists() else (False, "待产出 video-out/batch.mp4"),
      note="模板 × 数据", fallback="HyperFrames 循环出多条"),
    S(id="S5", name="精修", cap="video.finish",
      gate=lambda: gate_video(OUT / "final.mp4", need_audio=False) if (OUT / "final.mp4").exists() else (False, "待产出 video-out/final.mp4"),
      note="混剪/调色/字幕/音频", fallback="ffmpeg 收尾（scale+crf18+yuv420p）"),
    S(id="S6", name="验收", cap="video.probe",
      gate=lambda: gate_video(OUT / "final.mp4") if (OUT / "final.mp4").exists() else (False, "无成片可验"),
      note="客观读数（ffprobe）+ 人眼预览", fallback="人工看片"),
    # 🔴 2026-10-10 改：原来这条是 lambda: (LEDGER.exists(), ...) —— **装饰门**（judge-map 当场标出
    #    「文件存在性（只查在不在，不查内容）」）。现改成查**账本会不会撒谎**：合法 JSON · 覆盖全阶段 ·
    #    pass 字段现算吻合 · **自称 ok 的阶段其声明产物必须真在**（废物不上线）。
    S(id="S7", name="发布与账本", cap=None,
      gate=lambda: gate_publish(),
      note="清单/来源/许可；废物不上线", fallback="—"),
]


# S7「发布与账本」要核的**声明产物**：谁自称过了，这个东西就必须真在。
# 口径：这是**两个独立来源的交叉核对** —— 账本的"我过了" vs 文件系统的"东西在不在"。
# 所以它**不是**自指判据（自指 = 拿判据自己的输出去验判据自己）。
PUBLISH_ARTIFACTS = {
    "S2": ("cut-demo.mp4", OUT / "cut-demo.mp4"),
    "S3": ("motion.mp4", OUT / "motion.mp4"),
    "S4": ("batch.mp4", OUT / "batch.mp4"),
    "S5": ("final.mp4", OUT / "final.mp4"),
    "S6": ("final.mp4", OUT / "final.mp4"),
}


def gate_publish() -> tuple:
    """S7 发布与账本 —— **查账本会不会撒谎**，不是只查"它在不在"。

    🔴 2026-10-10 改。原来的门是 lambda: (LEDGER.exists(), "账本已落盘") ——
    judge-map 一眼把它标成「**文件存在性（只查在不在，不查内容）**」：一个**装饰门**。
    它「发布」二字管的事（**废物不上线**）一条都没判。现改成四条，逐条从文件里算：
      ① 账本是**合法 JSON**（不是半截写坏的件）
      ② 覆盖**全阶段**（每个 STAGES 的 id 都得有一行 —— 少一行说明账本不完整）
      ③ **pass 字段 == 现算的 ok 数**（防"硬编码一个漂亮的数"）
      ④ 🔴 **自称 ok 的阶段，其声明产物必须真在且非空** —— 这就是「废物不上线」的可执行形态：
         账本说"我过了"，而文件系统说"没这东西" ⇒ **当场判红**。
    ==这是两个独立来源的交叉核对，不是自指判据。==
    """
    if not LEDGER.is_file():
        return False, "缺 .video/ledger.json（跑一次 status 即生成）"
    try:
        d = json.loads(LEDGER.read_text(encoding="utf-8"))
    except Exception as e:                                             # noqa: BLE001
        return False, "账本**不是合法 JSON**（%s）—— 半截写坏的件不算账本" % type(e).__name__
    rows = d.get("stages") or []
    bad = []
    have = {r.get("id") for r in rows}
    miss = [s["id"] for s in STAGES if s["id"] not in have]
    if miss:
        bad.append("账本**不完整**，缺阶段 %s" % miss)
    real_pass = sum(1 for r in rows if r.get("ok"))
    if d.get("pass") != real_pass:
        bad.append("账本 pass 字段 %s ≠ **现算** %d（硬编码的数不许信）" % (d.get("pass"), real_pass))
    if d.get("total") != len(rows):
        bad.append("total %s ≠ 行数 %d" % (d.get("total"), len(rows)))
    # ④ 废物不上线：自称过的，产物必须真在
    for r in rows:
        if not r.get("ok"):
            continue
        aid = r.get("id")
        if aid not in PUBLISH_ARTIFACTS:
            continue
        nm, path = PUBLISH_ARTIFACTS[aid]
        if not path.is_file():
            bad.append("%s 自称过，但产物 %s **不在**（废物不许上线）" % (aid, nm))
        elif path.stat().st_size == 0:
            bad.append("%s 自称过，但 %s 是**空文件**" % (aid, nm))
    ok = not bad
    return ok, ("账本 %s · %d 行 · 自称过 %d/%d · pass 字段吻合 · 声明产物齐"
                % (d.get("updated", "?"), len(rows), real_pass, len(rows))
                + ("" if ok else " · ✗ " + "; ".join(bad)))


def selftest() -> int:
    """视频链各门的负控（正例必过 · 负例必红）—— **用仓里真件配对，不造假的凑数**。

    🔴 2026-10-10 补。起因：把数字人那张判据面表泛化到视频链一看，
    八格里**六格是「无 selftest」**，而 S7 那格连类型都判不出（它的门是 lambda: (LEDGER.exists(), …)
    —— 只查账本在不在）。按本仓律（判据没有负控就是摆设），这一串门都证明不了自己会响。
    正负例都用**现成真件**：
      · gate_video 负例 = 把非视频内容改名成 .mp4（**这正是我先前修过的那个假绿**：
        原来只按文件名匹配 creative*，改名成 .bak 也照样"过"）
      · gate_motion 负例 = motion.static-old.mp4（**帧间差恒 0.000 的死帧**）
      · gate_motion 正例 = motion.ffmpeg-fallback.mp4（帧间差 3.202 的强运动件）
    """
    import tempfile
    fails, n = [], [0]

    def c(name, got, want):
        n[0] += 1
        ok = (got == want)
        print("  %-56s %s" % (name, "✅" if ok else "❌ 期望 %s 得到 %s" % (want, got)))
        if not ok:
            fails.append(name)

    # ── gate_video
    c("gate_video 负例·缺件 ⇒ 红", gate_video(OUT / "_nope.mp4")[0], False)
    with tempfile.TemporaryDirectory() as td:
        fake = pathlib.Path(td) / "fake.mp4"
        fake.write_text("这不是视频，只是改了个后缀", encoding="utf-8")
        c("gate_video 负例·**非视频改名 .mp4** ⇒ 红", gate_video(fake)[0], False)
    live = OUT / "motion.mp4"
    if live.is_file():
        c("gate_video 正例·真 motion.mp4 ⇒ 过", gate_video(live)[0], True)

    # ── gate_motion：**死帧 vs 强运动**（这一对是这条链上最值钱的负控）
    # 🔴 2026-10-10 夹具**搬出交付目录**：它们原先躺在 video-out（那是产物落点），
    #    等于把"测试夹具"和"交付物"混在一块 —— 正是主人令「证据目录与在役件混淆」那一类。
    dead = CTRL / "motion.static-old.mp4"          # 负例：帧间差恒 0 的死帧
    strong = CTRL / "motion.ffmpeg-fallback.mp4"   # 正例：帧间差 3.202 的强运动件
    if dead.is_file():
        c("gate_motion 负例·死帧（帧间差恒 0）⇒ 红", gate_motion(dead)[0], False)
    if strong.is_file():
        c("gate_motion 正例·强运动件 ⇒ 过", gate_motion(strong)[0], True)
    if live.is_file():
        c("gate_motion 正例·真 motion.mp4 ⇒ 过", gate_motion(live)[0], True)

    # ── gate_publish：**真账本先备份，测完必还原**（负控不能把真件弄坏）
    if LEDGER.is_file():
        bak = LEDGER.read_bytes()
        try:
            LEDGER.write_text("{半截", encoding="utf-8")
            c("gate_publish 负例·账本不是合法 JSON ⇒ 红", gate_publish()[0], False)
            d0 = json.loads(bak.decode("utf-8"))
            LEDGER.write_text(json.dumps({**d0, "stages": d0["stages"][:-1]}, ensure_ascii=False),
                              encoding="utf-8")
            c("gate_publish 负例·账本缺阶段 ⇒ 红", gate_publish()[0], False)
            LEDGER.write_text(json.dumps({**d0, "pass": 999}, ensure_ascii=False), encoding="utf-8")
            c("gate_publish 负例·pass 字段硬编码 999 ⇒ 红", gate_publish()[0], False)
            # ④ **核心负控**：账本自称过，但产物被挪走 ⇒ 必须红（废物不上线）
            src = OUT / "motion.mp4"
            if src.is_file():
                hid = OUT / "_selftest_hidden_motion.mp4"
                src.replace(hid)
                try:
                    LEDGER.write_bytes(bak)
                    c("gate_publish 负例·自称过但产物被挪走 ⇒ 红", gate_publish()[0], False)
                finally:
                    hid.replace(src)
        finally:
            LEDGER.write_bytes(bak)
        c("gate_publish 正例·真账本 ⇒ 过（已还原）", gate_publish()[0], True)

    # ── gate_creative：假件必须红（它是"按文件名分流 + 真视频后缀 + ffprobe 有视频流"三条一起判的）
    ok, note = gate_creative()
    print("  %-56s %s" % ("gate_creative 现状读数（只报，因为它扫的是整目录）", note[:44]))
    # ── gate_assets 现状读数（同样只报）
    ok, note = gate_assets()
    print("  %-56s %s" % ("gate_assets 现状读数（只报）", note[:44]))
    print()
    print("video 门自检: %s（%d 条）"
          % ("**全部通过**" if not fails else "**%d 条失败**" % len(fails), n[0]))
    return 0 if not fails else 1


def run_gates(verbose=True):
    rows = []
    for st in STAGES:
        try:
            ok, note = st["gate"]()
        except Exception as e:
            ok, note = False, f"门异常 {type(e).__name__}: {str(e)[:50]}"
        rows.append((st["id"], st["name"], ok, note))
        if verbose:
            print(f"  {'✅' if ok else '❌'} {st['id']:>3} {st['name']:<20} {note}")
    return rows


def ledger_write(rows):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    data = {"updated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "stages": [{"id": i, "name": n, "ok": o, "note": t} for i, n, o, t in rows],
            "pass": sum(1 for r in rows if r[2]), "total": len(rows),
            "providers": {k: probe(k)[0] for k in PROVIDERS}}
    LEDGER.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def main():
    a = sys.argv[1:]
    cmd = a[0] if a else "status"
    if cmd == "selftest":
        return selftest()
    if cmd == "map":
        print("视频流水线 · 阶段地图（能力位驱动）")
        for st in STAGES:
            print(f"\n{st['id']} · {st['name']}   能力位 {st['cap'] or '（人工）'}")
            print(f"  判据: {st['gate']()[1]}\n  说明: {st['note']}\n  回退: {st['fallback']}")
        return
    if cmd == "providers":
        print("后端可用性（本机实测）")
        for k, p in PROVIDERS.items():
            ok, note = probe(k)
            flag = "✅" if ok is True else ("⚠️" if ok is None else "❌")
            print(f"  {flag} {k:<12} {note}")
        print("\n能力位 → 当前落到谁")
        for cap in CAPS:
            who, why = resolve(cap)
            print(f"  {'✅' if who else '❌'} {cap:<16} → {who or ('无可用：' + (why or ''))}")
        return
    if cmd == "probe":
        if len(a) < 2:
            print("用法: probe <video>"); return
        ok, note = gate_video(pathlib.Path(a[1]))
        print(f"{'✅' if ok else '❌'} {note}")
        return
    if cmd == "status":
        print("视频流水线 · 全链门检（ffprobe 真读数）")
        d = ledger_write(run_gates())
        print(f"\n  通过 {d['pass']}/{d['total']} · 账本 → {LEDGER.relative_to(WS)}")
        return
    if cmd == "run":
        if len(a) < 2:
            print("用法: run <S0..S7> [--dry] [--provider <k>]"); return
        st = next((s for s in STAGES if s["id"].lower() == a[1].lower()), None)
        if not st:
            print("无此阶段"); return
        prefer = a[a.index("--provider") + 1] if "--provider" in a else None
        who, why = resolve(st["cap"], prefer) if st["cap"] else (None, "人工阶段")
        if st["cap"] and not who:
            print(f"❌ {st['id']} 需要 {st['cap']}：{why}"); return
        print(f"[{st['id']}] {st['name']} · 能力位 {st['cap']} → {who or '人工'}")
        if who:
            print(f"  坑: {PROVIDERS[who]['notes']}\n  命令: {(PROVIDERS[who]['cmds'] or {}).get(st['cap'], '（见 notes）')}")
        if "--dry" in a:
            return
        ok, note = st["gate"]()
        print(f"  门: {'✅' if ok else '❌'} {note}")
        return
    print(__doc__)


if __name__ == "__main__":
    main()
