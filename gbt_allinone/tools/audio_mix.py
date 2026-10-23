# -*- coding: utf-8 -*-
# gbt-capability: audio-mix
"""混音与母带（native 能力位 `audio_mix`）—— 本机 ffmpeg，**零出网**。

## 它填的是哪两个空格

`media_flow` 的三方向 18 格里，**AI音乐一整条线一格成品都没有**：
`02-compose / 03-arrange / 04-mix / 05-master / 06-release` 全空。
本能力位先把**本机能做的那两格**做掉：

    music/04-mix      ↔ 框架工序 `audio`      ← `mix`（多轨混合）
    music/05-master   ↔ 框架工序 `master`     ← `master`（响度归一 / 母带）
    film/04-assets    ↔ 框架工序 `sound`      ← `mix`（对白 + 配乐 + 音效 三轨合）

## 专业口径（蒸馏出来的，不是随口定的）

**响度标准**（母带这一步真正的专业内容 —— 不同平台按不同 LUFS 收）：

| 目标 | 积分响度 I | 说明 |
|---|---|---|
| `streaming`（默认）| **-14 LUFS** | Spotify / YouTube / Apple Music 一类的通行目标 |
| `podcast` | **-16 LUFS** | Apple Podcasts 的口径 |
| `broadcast` | **-23 LUFS** | EBU R128（欧洲广播）|
| `cinema` | **-27 LUFS** | 影院对白基准（比流媒体低得多）|

**真峰**（True Peak）默认 **-1.0 dBTP**（给转码留 headroom；流媒体常要 -1，广播要 -2）。

**两遍法**：母带用 **2-pass loudnorm**（先量 → 再按量到的值施加）。
一遍法（single-pass）是动态模式，**结果是"大概"**；两遍法才是"按测量值精确施加"。
本实现走两遍；**第一遍量到的四个数会随结果一起返回**（那是证据，不是过程日志）。

## 红线（与 `audio_extract` 同一套，**代码也是同一份**）

写面自收窄 / 零出网 / 不吞坏因 / 产出即验证 / 不许编 —— 五条都**直接复用**
`audio_extract` 里已经写好并有判据的那几个函数（`write_guard` · `_run` · `probe` · `_verify` …），
**不另写一份**：一件事实两处实现 = 两套口径（本仓最贵的教训）。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 🔴 复用，不重写 —— 见模块头最后一段
from .audio_extract import (  # noqa: E402
    DEFAULT_BITRATE, DEFAULT_FORMAT, FORMATS, MUXERS,
    _have, _run, _tail, _verify, probe, write_guard,
)

_IMPL_VERSION = "1.0"

READ_OPS = ("status", "loudness_targets", "qc")
WRITE_OPS = ("mix", "master")
WRITE_ROOTS = ("projects", "outputs", ".scratch")

# 响度标准表（母带这一步的专业内容）
#
# 🔴 **与已有蒸馏技能对齐**（2026-09-23 第 48 轮核过，不另立第二套口径）：
#   托管技能 `music-production`（`.openclaw-autoclaw\skills\music-production\SKILL.md`，
#   蒸馏自 `bitwize-music-studio/claude-ai-music-skills`，**CC0 公有领域**）第 56 行写着
#   「响度 | 目标 **-14 LUFS**（流媒体标准）」—— 与本表 `streaming` **一致**（-14.0）。
#   它还给了本表原先缺的一条专业判断（第 64 行）：
#   「**母带要按曲风取 EQ 曲线与响度目标** —— 不是一套参数打天下」。
#   ⇒ 落成下面的 `BY_GENRE`：平台口径决定"交付响度"，**曲风决定动态预算**（同一 -14 下，
#     古典/爵士留的动态比 EDM 多得多；给 EDM 按古典留动态 = 听着没劲）。
LOUDNESS_TARGETS = {
    "streaming": {"I": -14.0, "TP": -1.0, "why": "Spotify / YouTube / Apple Music 一类的通行目标"},
    "podcast":   {"I": -16.0, "TP": -1.0, "why": "Apple Podcasts 口径"},
    "broadcast": {"I": -23.0, "TP": -2.0, "why": "EBU R128（欧洲广播）"},
    "cinema":    {"I": -27.0, "TP": -2.0, "why": "影院对白基准 —— 比流媒体低得多"},
}
DEFAULT_TARGET = "streaming"

# 曲风 → 动态预算（同一交付响度下"留多少动态"）。出处见上面那条对齐说明。
BY_GENRE = {
    "classical": {"lra": 15, "why": "留最大动态 —— 强弱对比是作品的一部分，压扁就毁了"},
    "jazz":      {"lra": 14, "why": "同古典一档，稍紧一点"},
    "acoustic":  {"lra": 12, "why": "人声/吉他为主，别把呼吸感压掉"},
    "pop":       {"lra": 9,  "why": "流行为主：一致性强、副歌要有推力"},
    "rock":      {"lra": 8,  "why": "鼓与失真本身占动态，别再加"},
    "electronic": {"lra": 6, "why": "EDM/电子：低动态是**风格特征**，不是缺陷"},
    "hiphop":    {"lra": 7,  "why": "低频占能，动态留窄换冲击力"},
    "speech":    {"lra": 7,  "why": "口播/旁白：可懂度优先，动态留窄"},
}
DEFAULT_GENRE_LRA = 11


def _measure(src: str) -> dict:
    """第一遍：量。返回 loudnorm 的测量块（input_i / input_tp / input_lra / input_thresh）。"""
    rc, _o, err = _run(["ffmpeg", "-hide_banner", "-i", str(src),
                        "-af", "loudnorm=I=-14:TP=-1:LRA=11:print_format=json",
                        "-f", "null", "-"], 900)
    if rc != 0:
        return {"ok": False, "error": "第一遍测量失败（rc=%d）" % rc, "stderr_tail": _tail(err)}
    # loudnorm 把测量 JSON 打到 **stderr 尾部**（不是 stdout）—— 这里如实取 stderr
    m = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", err or "", re.S)
    if not m:
        return {"ok": False, "error": "量到了但解析不出测量块", "stderr_tail": _tail(err, 600)}
    try:
        d = json.loads(m[-1])
    except ValueError:
        return {"ok": False, "error": "测量块不是 JSON", "raw": m[-1][:200]}
    return {"ok": True, "measured": {k: d.get(k) for k in
                                     ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}}


def _master_filter(target: str, measured: dict | None = None, genre: str = "") -> str:
    """拼 loudnorm 滤镜串。`measured` 有值就是**第二遍**（按测量值精确施加）。

    `genre` 决定 **LRA（动态预算）** —— 见 BY_GENRE 的出处说明。不传就用中性值 11。
    """
    t = LOUDNESS_TARGETS.get(target) or LOUDNESS_TARGETS[DEFAULT_TARGET]
    lra = (BY_GENRE.get(genre) or {}).get("lra", DEFAULT_GENRE_LRA)
    base = "loudnorm=I=%s:TP=%s:LRA=%s" % (t["I"], t["TP"], lra)
    if not measured:
        return base
    return (base + ":measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s"
                   ":offset=%s:linear=true:print_format=summary"
            % (measured.get("input_i"), measured.get("input_tp"),
               measured.get("input_lra"), measured.get("input_thresh"),
               measured.get("target_offset") or 0.0))


def _mix_filter(n: int, volumes, duration: str) -> str:
    """拼 amix 滤镜链：每路可选音量，再合成。

    ⚠️ `amix` 默认 `normalize=1`（会自动把每路音量压低到 1/n，专治削波但也让整体变小）。
    本实现**显式 `normalize=0`**：混音后的响度由 `master` 那一步负责，
    不在这里偷偷改 —— 否则"混完再归一"会把两次增益叠起来，读数就不是你要的了。
    """
    parts = []
    for i, v in enumerate(volumes or []):
        if v is None:
            continue
        parts.append("[%d:a]volume=%s[a%d]" % (i, v, i))
    if parts:
        labels = "".join("[a%d]" % i for i in range(n))
        return ";".join(parts) + ";" + labels + "amix=inputs=%d:duration=%s:normalize=0[out]" % (n, duration)
    return "".join("[%d:a]" % i for i in range(n)) + "amix=inputs=%d:duration=%s:normalize=0[out]" % (n, duration)


# ── 7 项音频 QC（第 68 轮）──────────────────────────────────────────────────
# 出处 = 托管技能 `music-production`（蒸馏自 bitwize-music-studio/claude-ai-music-skills · **CC0**）§4:
#
#   | 项 | 判据 |
#   | 响度 | 目标 **-14 LUFS**（流媒体标准） |
#   | 削波 | 不允许 |
#   | 静音 | 不允许（非艺术意图的） |
#   | 相位 | 不许反相抵消 |
#   | 立体声宽度 | **按曲风** |
#   | 频谱平衡 | **按曲风** |
#   | 动态范围 | **按曲风** |
#
# §4 还有一句定调：「**母带要按曲风取 EQ 曲线与响度目标** —— 不是一套参数打天下。」
#
# 🔴 本器把判据分成两档，**这是这一轮最重要的设计决定**：
#   · **绝对档**（契约原文是"不允许 / 不许 / 目标值"）⇒ 机器**判否**
#     ：响度（对目标 ±0.5 LU，沿用本仓 `hit_target` 的既有口径）· 削波 · 静音 · 相位
#   · **参考档**（契约原文是"**按曲风**"）⇒ 机器**只报数、不判否**
#     ：立体声宽度 · 频谱平衡 · 动态范围
#     **曲风该是什么样，本机没有权威口径** —— 拿我编的数去判否，就是替上游立规矩。
#     曲风给了 LRA 就用本仓 `BY_GENRE` 比对一下（那也是这个仓自己的表），**仍只作参考**。
#
# 每一条都带 `怎么量的`：本仓自己的教训（真成品《夜航》第 63–66 行）写着
# 「**判据里出现数字，就必须有对应的量测步骤**」。
QC_CLIP_LEVEL = 0.999          # ≈ -0.0087 dBFS，样本级削波门
QC_SILENCE_DB = -60.0          # 静音门（相对满刻度）
QC_WIN_MS = 100                # 静音按 100 ms 窗看
QC_SILENCE_FLAG_S = 3.0        # 中段连续静音超过这个秒数 ⇒ 提示（艺术意图机器判不了）
QC_PHASE_FAIL = 0.0            # 相关系数 < 0 ⇒ 反相（契约原文"不许反相抵消"）
QC_PHASE_WARN = 0.2
QC_LU_TOL = 0.5                # 响度命中容差（与本仓 `hit_target` 同口径）
QC_BANDS = ((20, 60, "超低"), (60, 250, "低"), (250, 500, "低中"),
            (500, 2000, "中"), (2000, 6000, "中高"), (6000, 16000, "高"))
QC_ITEMS = ("响度", "削波", "静音", "相位", "立体声宽度", "频谱平衡", "动态范围")
QC_HARD = ("响度", "削波", "相位")     # **绝对档**：契约原文是"目标值/不允许/不许"
QC_SOFT = ("立体声宽度", "频谱平衡", "动态范围")   # **参考档**：契约原文是"按曲风"


def _decode_f32(src: str, ch: int, sr: int = 48000):
    """把音频解成 float32 PCM（**不写盘**）。返回 (np.ndarray[ch, n], 采样率) 或错误 dict。"""
    try:
        import numpy as np
    except ImportError:
        return {"ok": False, "status": "needs_dependency", "missing": "numpy",
                "why": "信号域那几项要 numpy 才算得动；**不假装能算**（响度那一项仍可单独量）"}
    # ⚠️ **不能走 `_run`**：它把 stdout 当文本解码（`errors="replace"`），
    #    拿它接原始 PCM 会把字节流毁掉（第一版就死在 `np.frombuffer` 收到 str）。
    #    这里直接 `subprocess.run` 取 **bytes**（本模块没在模块级 import subprocess）。
    import subprocess
    p = subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-i", str(src),
                        "-f", "f32le", "-acodec", "pcm_f32le", "-ac", str(ch),
                        "-ar", str(sr), "-"], capture_output=True, timeout=900)
    if p.returncode != 0 or not p.stdout:
        return {"ok": False, "error": "解码失败（rc=%d）" % p.returncode,
                "stderr_tail": (p.stderr or b"").decode("utf-8", "replace")[-300:]}
    a = np.frombuffer(p.stdout, dtype="<f4")
    if a.size < ch:
        return {"ok": False, "error": "解出来的样本不够（%d）" % a.size}
    n = a.size // ch
    return {"ok": True, "x": a[:n * ch].reshape(n, ch).T, "sr": sr}


def qc(src: str, target: str = "", genre: str = "") -> dict:
    """7 项音频 QC（只读 · 不写任何东西）。`run_task("audio_mix", {"op": "qc", "src": ...})`。"""
    if not src:
        return {"ok": False, "error": "op=qc 需要 src"}
    if not _have("ffmpeg"):
        return {"ok": False, "status": "needs_dependency", "missing": "ffmpeg",
                "why": "本机没有 ffmpeg ⇒ 做不了 QC（不假装能做）"}
    info = probe(src)
    if not info.get("ok"):
        return info
    if not info.get("has_audio"):
        return {"ok": False, "error": "源没有音轨", "src": info.get("src")}
    tgt = str(target or DEFAULT_TARGET)
    items, fails, warns, na = [], [], [], []

    def add(name, verdict, measured, how, src_txt, hard):
        items.append({"项": name, "判定": verdict, "量得": measured,
                      "怎么量的": how, "出处": src_txt, "硬判据": hard})
        if verdict == "不合格":
            fails.append("%s：%s" % (name, measured))
        elif verdict == "注意":
            warns.append("%s：%s" % (name, measured))
        elif verdict == "不适用":
            na.append(name)

    # ① 响度（绝对档）—— 复用 `_measure`，口径与本仓 `master` 的 hit_target 一致
    meas = _measure(str(src))
    spec = LOUDNESS_TARGETS.get(tgt) or LOUDNESS_TARGETS[DEFAULT_TARGET]
    m = meas.get("measured") or {}          # ⚠️ 必须在分支外先取出来：下面几项都要用
    if meas.get("ok"):
        m = meas["measured"]
        got = float(m.get("input_i"))
        want = float(spec["I"])
        d = got - want
        add("响度", "合格" if abs(d) <= QC_LU_TOL else "不合格",
            "%.2f LUFS（目标 %s = %.1f LUFS · 差 %+.2f LU）" % (got, tgt, want, d),
            "ffmpeg `loudnorm` 打印测量块，读 **stderr 尾部**的 input_i（不是 stdout）",
            "`music-production` §4 响度行 + 本仓 `hit_target` 的 ±%.1f LU 口径" % QC_LU_TOL, True)
    else:
        add("响度", "不合格", "量不到：%s" % (meas.get("error") or "")[:60],
            "同上（这一次没量出来）", "同上", True)

    # ⚠️ `probe` 把声道数放在**流字典**里（`info["audio"][0]["channels"]`），不在顶层。
    #    第一版我读 `info.get("channels")` ⇒ 读成 None，整个 QC 直接短路成「声道数读不到」。
    _a0 = (info.get("audio") or [{}])[0]
    ch = int(_a0.get("channels") or info.get("channels") or 0)
    if ch < 1:
        return {"ok": False, "error": "声道数读不到", "probe": info}
    dec = _decode_f32(str(src), min(2, ch))
    if not dec.get("ok"):
        # numpy 缺 ⇒ 只给响度那一条，其余如实标"未判"，**不假装全绿**
        for name, why in (("削波", "要 numpy"), ("静音", "要 numpy"), ("相位", "要 numpy"),
                          ("立体声宽度", "要 numpy"), ("频谱平衡", "要 numpy"), ("动态范围", "要 numpy")):
            add(name, "不适用", "未判（%s）" % why, "本机缺 numpy ⇒ 算不动", "`music-production` §4", False)
        return {"ok": False, "status": dec.get("status") or "error", "items": items,
                "fails": fails, "warns": warns, "unjudged": na, "missing": dec.get("missing"),
                "note": "只量到了响度；其余 6 项要 numpy —— **判不了就不算合格**"}

    import numpy as np
    x = dec["x"]
    dur = x.shape[1] / float(dec["sr"])

    # ② 削波（绝对档）
    peak = float(np.abs(x).max())
    nclip = int((np.abs(x) >= QC_CLIP_LEVEL).sum())
    tp = m.get("input_tp") if meas.get("ok") else None
    add("削波", "合格" if nclip == 0 else "不合格",
        "样本峰值 %.2f dBFS · 顶到门的样本 %d 个%s"
        % (20 * np.log10(max(1e-9, peak)), nclip,
           (" · 真峰值 %s dBTP" % tp) if tp is not None else ""),
        "解码成 f32 PCM 后数 |样本| ≥ %.3f 的个数；真峰值另取 `loudnorm` 的 input_tp"
        % QC_CLIP_LEVEL, "`music-production` §4 削波行（原文：不允许）", True)

    # ③ 静音（绝对档）—— 但**艺术意图机器判不了**，这一句必须跟着读数走
    win = max(1, int(dec["sr"] * QC_WIN_MS / 1000.0))
    nw = x.shape[1] // win
    if nw:
        env = np.abs(x[:, :nw * win]).reshape(x.shape[0], nw, win).max(axis=(0, 2))
        quiet = env < (10 ** (QC_SILENCE_DB / 20.0))
        best = cur = 0
        for q in quiet:
            cur = cur + 1 if q else 0
            best = max(best, cur)
        longest = best * QC_WIN_MS / 1000.0
    else:
        longest = 0.0
    add("静音", "合格" if longest <= QC_SILENCE_FLAG_S else "注意",
        "最长连续静音 %.2f s（门 %.0f dBFS · 窗 %.0f ms · 全片 %.2f s）"
        % (longest, QC_SILENCE_DB, QC_WIN_MS, dur),
        "按 %.0f ms 窗取窗内峰值，找连续低于 %.0f dBFS 的最长一段"
        % (QC_WIN_MS, QC_SILENCE_DB),
        "`music-production` §4 静音行（原文：不允许**非艺术意图的**）—— "
        "**艺术意图机器判不了**，故超门只报「注意」不判否", False)

    # ④ 相位（绝对档）
    if x.shape[0] >= 2:
        L, R = x[0].astype("f8"), x[1].astype("f8")
        if L.std() > 1e-9 and R.std() > 1e-9:
            corr = float(np.corrcoef(L, R)[0, 1])
        else:
            corr = float("nan")
        v = ("不合格" if corr < QC_PHASE_FAIL else
             ("注意" if corr < QC_PHASE_WARN else "合格"))
        add("相位", v, "L/R 相关系数 %+.3f" % corr,
            "整片左右声道做 Pearson 相关；**< %.1f 判反相**（契约原文「不许反相抵消」的操作化）"
            % QC_PHASE_FAIL, "`music-production` §4 相位行", True)
        # ⑤ 立体声宽度（参考档 — 原文「按曲风」）
        mid = (L + R) / 2.0
        side = (L - R) / 2.0
        em, es = float((mid ** 2).mean()), float((side ** 2).mean())
        wdb = 10 * np.log10(max(1e-12, es) / max(1e-12, em))
        add("立体声宽度", "参考", "side/mid 能量比 %+.1f dB" % wdb,
            "mid=(L+R)/2 · side=(L-R)/2，比两者均方能量（dB）",
            "`music-production` §4 立体声宽度行（原文：**按曲风**）—— 曲风口径本机没有权威来源，**只报不判**",
            False)
    else:
        add("相位", "不适用", "单声道（%d ch）" % ch, "单声道没有左右关系", "`music-production` §4 相位行", False)
        add("立体声宽度", "不适用", "单声道（%d ch）" % ch, "单声道没有 side 分量",
            "`music-production` §4 立体声宽度行", False)

    # ⑥ 频谱平衡（参考档）
    mono = x.mean(axis=0).astype("f8")
    nfft = 32768
    hop = nfft // 2
    acc = None
    for s0 in range(0, max(1, mono.size - nfft), hop):
        seg = mono[s0:s0 + nfft]
        if seg.size < nfft:
            break
        w = np.hanning(nfft)
        p = np.abs(np.fft.rfft(seg * w)) ** 2
        acc = p if acc is None else acc + p
    if acc is None:
        add("频谱平衡", "不适用", "样本太短，配不出谱", "分块 Hann 窗 FFT 求平均功率谱",
            "`music-production` §4 频谱平衡行", False)
    else:
        f = np.fft.rfftfreq(nfft, 1.0 / dec["sr"])
        tot = float(acc.sum()) or 1e-12
        parts = []
        for lo, hi, cn in QC_BANDS:
            band = float(acc[(f >= lo) & (f < hi)].sum())
            parts.append("%s %.1f" % (cn, 10 * np.log10(max(1e-12, band / tot))))
        add("频谱平衡", "参考", "各频段占总能量 dB：" + " · ".join(parts),
            "分块 Hann 窗 FFT 求平均功率谱，按 %d 个频段求和后取相对总能量的 dB"
            % len(QC_BANDS),
            "`music-production` §4 频谱平衡行（原文：**按曲风**）—— **只报不判**", False)

    # ⑦ 动态范围（参考档；给了曲风就用本仓 BY_GENRE 的表对一下）
    rms = float(np.sqrt((x ** 2).mean()))
    crest = 20 * np.log10(max(1e-9, peak)) - 20 * np.log10(max(1e-12, rms))
    lra = m.get("input_lra") if meas.get("ok") else None
    g = str(genre or "").strip()
    extra = ""
    if g and g in BY_GENRE and lra is not None:
        extra = " ｜ 曲风 %s 的本仓 LRA 表 = %.0f LU，实测 %s" % (g, BY_GENRE[g], lra)
    add("动态范围", "参考",
        "峰值因数 %.1f dB%s%s" % (crest, (" · LRA %s LU" % lra) if lra is not None else "", extra),
        "峰值因数 = 样本峰值 dBFS − 全片 RMS dBFS；LRA 取 `loudnorm` 的 input_lra",
        "`music-production` §4 动态范围行（原文：**按曲风**）—— **只报不判**"
        + ("；曲风表用本仓 `BY_GENRE`（`loudness_targets` 里那份）" if g else ""), False)

    judged = [i for i in items if i["硬判据"]]
    return {
        "ok": (not fails) and len(judged) == len(QC_HARD),
        "impl": "audio_mix.qc", "src": info.get("src"), "target": tgt, "genre": g,
        "duration_s": round(dur, 3), "channels": ch, "sample_rate": dec["sr"],
        "items": items, "counts": {"合格": sum(1 for i in items if i["判定"] == "合格"),
                                   "不合格": len(fails), "注意": len(warns),
                                   "参考": sum(1 for i in items if i["判定"] == "参考"),
                                   "不适用": len(na)},
        "fails": fails, "warns": warns, "unjudged": na,
        "hard_items": [i["项"] for i in judged],
        # ⚠️ 按**契约**列（不按判定列）：单声道时「立体声宽度」会判「不适用」，
        #    若按判定统计，它就会从这个名单里消失 —— 而它**在契约上仍属参考档**。
        "soft_items": [i for i in QC_SOFT],
        "soft_verdicts": {i["项"]: i["判定"] for i in items if i["项"] in QC_SOFT},
        "note": "**绝对档**（响度/削波/静音/相位）才判否；**参考档**（立体声宽度/频谱平衡/动态范围）"
                "契约原文写的是「按曲风」—— 曲风口径本机没有权威来源，**只报数不判否**。"
                "每一条都带「怎么量的」。",
    }


def run(op: str = "status", **kw) -> dict:
    """万能插入口：`run_task("audio_mix", {"op": ..., ...})` 落到这里。"""
    op = str(op or "status")

    if op == "status":
        return {"ok": True, "impl": "audio_mix", "version": _IMPL_VERSION,
                "kind": "audio_mix", "domain": "video",
                "read_ops": list(READ_OPS), "write_ops": list(WRITE_OPS),
                "write_roots": list(WRITE_ROOTS),
                "ffmpeg": _have("ffmpeg"), "ffprobe": _have("ffprobe"),
                "default_target": DEFAULT_TARGET, "targets": sorted(LOUDNESS_TARGETS),
                "fills_drawers": ["music/04-mix（↔ audio）", "music/05-master（↔ master）",
                                  "film/04-assets（↔ sound）"],
                "note": "复用 audio_extract 的写面守卫与验证器（**不重写**）；母带走 **2-pass loudnorm**，"
                        "第一遍量到的四个数随结果返回。",
                "qc_items": list(QC_ITEMS),
                "qc_hard": list(QC_HARD),
                "qc_soft": list(QC_SOFT),
                "qc_note": "`op=qc` 是**只读**的 7 项音频质量判据（出处 `music-production` §4）。"
                           "绝对档（%s）才判否；参考档（%s）契约原文是「按曲风」，"
                           "本机没有曲风权威口径 ⇒ **只报数不判否**。每一条都带「怎么量的」。"
                           % ("、".join(QC_HARD), "、".join(QC_SOFT))}

    if op == "loudness_targets":
        return {"ok": True, "default": DEFAULT_TARGET, "targets": LOUDNESS_TARGETS,
                "by_genre": BY_GENRE, "default_genre_lra": DEFAULT_GENRE_LRA,
                "aligned_with": "托管技能 `music-production`（蒸馏自 bitwize-music-studio/claude-ai-music-skills · CC0）"
                                "第 56 行 -14 LUFS / 第 64 行「按曲风取 EQ 与响度目标」—— **不另立第二套口径**",
                "why_it_matters": "同一条音频在不同平台按不同 LUFS 收 —— 母带这一步就是把它对齐到目标，"
                                  "既别让平台再压一次（过头=动态被压扁），也别比目标小一截（听感发闷）。",
                "two_pass": "一遍法是动态模式（结果≈大概）；两遍法先量后施加，才是按测量值精确对齐。"}

    if op == "qc":
        return qc(kw.get("src") or kw.get("path") or "",
                  target=kw.get("target") or "", genre=kw.get("genre") or "")

    if op == "master":
        src = kw.get("src") or kw.get("path")
        if not src:
            return {"ok": False, "error": "op=master 需要 src"}
        if not _have("ffmpeg"):
            return {"ok": False, "status": "needs_dependency", "missing": "ffmpeg",
                    "why": "本机没有 ffmpeg ⇒ 做不了母带（不假装能做）"}
        info = probe(src)
        if not info.get("ok"):
            return info
        if not info.get("has_audio"):
            return {"ok": False, "error": "源没有音轨", "src": info.get("src")}
        fmt = str(kw.get("format") or DEFAULT_FORMAT).lower().lstrip(".")
        if fmt not in FORMATS:
            return {"ok": False, "error": "不认的格式 %r（认这些：%s）" % (fmt, "、".join(sorted(FORMATS)))}
        out = kw.get("out") or "outputs/audio/%s-master.%s" % (Path(src).stem, FORMATS[fmt]["ext"].lstrip("."))
        g = write_guard(out, kw.get("root"))
        if not g.get("ok"):
            return {"ok": False, "error": g["why"], "refused": True}
        dst = Path(g["abs"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        target = str(kw.get("target") or DEFAULT_TARGET)
        genre = str(kw.get("genre") or "")
        # 第一遍：量（**第二遍要用它**，所以先把读数拿出来）
        meas = _measure(str(src))
        if not meas.get("ok"):
            return meas
        filt = _master_filter(target, meas.get("measured"), genre)
        f = FORMATS[fmt]
        br = str(kw.get("bitrate") or f.get("default_bitrate") or DEFAULT_BITRATE)
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
               "-vn", "-af", filt, "-c:a", f["codec"]]
        # 🔴 保住源采样率（**实测抓到**）：`loudnorm` 内部会把信号升到 192 kHz，
        #    不显式 `-ar` 的话**产物就变成 192 kHz** —— 本机实测同一条 3.0 s 音轨：
        #    源 44.1 kHz / 265 KB，母带后**变成 192 kHz / 1.15 MB**（体积翻四倍多），
        #    而"母带"这件事**从来不包括改采样率**。⇒ 默认跟随源；要改必须显式传 rate。
        src_rate = str(kw.get("rate") or (info["audio"][0] or {}).get("sample_rate") or "")
        if src_rate:
            cmd += ["-ar", src_rate]
        if f["kind"] != "未压缩" and f["codec"] != "flac":
            cmd += ["-b:a", br]
        cmd += ["-f", MUXERS.get(fmt, "mp3"), str(dst)]
        rc, _o, err = _run(cmd, int(kw.get("timeout") or 1200))
        if rc != 0:
            return {"ok": False, "error": "ffmpeg 施加失败（rc=%d）" % rc, "stderr_tail": _tail(err)}
        v = _verify(dst)
        # 🔴 **产出即验证 —— 而且要量"到了没有"**（第 51 轮补）：
        #    只报 "target=-14" 却只量了**施加之前**，那还是"我们跑了 loudnorm"，不是"产物真的 -14"。
        #    这一步把产物再量一遍：没有它，"母带做到 -14"就是一句没根据的话。
        after = _measure(str(dst))
        delta = None
        if after.get("ok"):
            try:
                delta = round(float((after["measured"] or {}).get("input_i"))
                              - float((LOUDNESS_TARGETS.get(target) or {}).get("I")), 2)
            except (TypeError, ValueError):
                delta = None
        return {"ok": bool(v.get("ok")), "out": g["rel"], "format": fmt,
                "target": target, "target_spec": LOUDNESS_TARGETS.get(target),
                "genre": genre or None,
                "genre_lra": (BY_GENRE.get(genre) or {}).get("lra", DEFAULT_GENRE_LRA),
                "measured_before": meas.get("measured"), "product": v, "verified": bool(v.get("ok")),
                "measured_after": (after.get("measured") if after.get("ok") else after),
                "delta_lu": delta,
                "hit_target": (None if delta is None else abs(delta) <= 0.5),
                "two_pass": True,
                "note": "**两遍施加 + 一遍复核**：measured_before 是施加前量到的，"
                        "measured_after 是**产物**再量一遍；delta_lu 是它与目标的差（±0.5 LU 内算命中）。"}

    if op == "mix":
        srcs = kw.get("sources") or kw.get("srcs") or []
        if isinstance(srcs, str):
            srcs = [srcs]
        if len(srcs) < 2:
            return {"ok": False, "error": "op=mix 至少两条 sources（**一条不叫混音**）"}
        if not _have("ffmpeg"):
            return {"ok": False, "status": "needs_dependency", "missing": "ffmpeg",
                    "why": "本机没有 ffmpeg ⇒ 混不了（不假装能混）"}
        fmt = str(kw.get("format") or DEFAULT_FORMAT).lower().lstrip(".")
        if fmt not in FORMATS:
            return {"ok": False, "error": "不认的格式 %r" % fmt}
        out = kw.get("out") or "outputs/audio/mix-%s.%s" % (
            "-".join(Path(s).stem for s in srcs)[:60], FORMATS[fmt]["ext"].lstrip("."))
        # 🔴 **落点守卫放在最前**（第 52 轮，测试逼出来的一个真改进）：
        #    原来它排在"逐个 probe 源"之后 ⇒ 一个非法落点要先等所有源都被读一遍才被拒，
        #    而且源要是读不动，**你根本看不到"落点非法"这句话**（先报的是源的问题）。
        #    落点合不合法**不需要读任何源就能判** ⇒ 先判，fail fast，报的话也更准。
        g = write_guard(out, kw.get("root"))
        if not g.get("ok"):
            return {"ok": False, "error": g["why"], "refused": True}
        for s in srcs:
            i = probe(s)
            if not i.get("ok"):
                return {"ok": False, "error": "源读不动：%s" % s, "detail": i}
            if not i.get("has_audio"):
                return {"ok": False, "error": "源 **%s** 没有音轨" % Path(s).name}
        first_rate = str(((probe(srcs[0]).get("audio") or [{}])[0] or {}).get("sample_rate") or "")
        dst = Path(g["abs"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        duration = str(kw.get("duration") or "longest")
        if duration not in ("longest", "shortest", "first"):
            return {"ok": False, "error": "duration 只认 longest/shortest/first"}
        chain = _mix_filter(len(srcs), kw.get("volumes"), duration)
        if kw.get("master"):
            chain = chain.replace("[out]", "[mixed];[mixed]" + _master_filter(str(kw["master"])) + "[out]")
        f = FORMATS[fmt]
        br = str(kw.get("bitrate") or f.get("default_bitrate") or DEFAULT_BITRATE)
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
        for s in srcs:
            cmd += ["-i", str(s)]
        cmd += ["-filter_complex", chain, "-map", "[out]", "-c:a", f["codec"]]
        # 同 master：链里若带 loudnorm，不锁采样率就会被动升到 192 kHz
        rate = str(kw.get("rate") or first_rate or "")
        if rate:
            cmd += ["-ar", rate]
        if f["kind"] != "未压缩" and f["codec"] != "flac":
            cmd += ["-b:a", br]
        cmd += ["-f", MUXERS.get(fmt, "mp3"), str(dst)]
        rc, _o, err = _run(cmd, int(kw.get("timeout") or 1200))
        if rc != 0:
            return {"ok": False, "error": "ffmpeg 混音失败（rc=%d）" % rc,
                    "stderr_tail": _tail(err), "filter": chain[:200]}
        v = _verify(dst)
        return {"ok": bool(v.get("ok")), "out": g["rel"], "format": fmt, "inputs": len(srcs),
                "duration_mode": duration, "mastered_to": kw.get("master") or None,
                "product": v, "verified": bool(v.get("ok")),
                "note": "`normalize=0` 是刻意的：混音不偷偷改总响度，归一是 `master` 那一步的事。"}

    return {"ok": False, "error": "不认的 op：%s（读 %s / 写 %s）"
                                 % (op, "/".join(READ_OPS), "/".join(WRITE_OPS))}
