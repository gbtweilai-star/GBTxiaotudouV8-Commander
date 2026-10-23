# -*- coding: utf-8 -*-
"""voice-emote.py — 会「动情」的配音：逐句标情绪 → 逐句合成 → 实测情感幅度。

## 为什么不是"多加点语气词"
主人令（2026-10-20）：「包括语音七情六欲，人情世故，喜怒哀乐都要融入进去」。
"有感情"最容易自欺：听感是主观的，代码里多几个"喔/啦"也能自称有情感。所以本件把情感钉成**读数**：

| 维度 | 怎么量 | 达标线 |
|---|---|---|
| 音高起伏 | 逐帧 F0（自相关法）在**每一句内**的标准差 | ≥ 平铺基线 ×1.15 |
| 力度起伏 | 逐帧 RMS 包络的标准差 | ≥ 平铺基线 ×1.10 |
| 语速变化 | 四句的"字/秒"极差 | ≥ 8%（同一句速念完 = 没有情绪） |
| 停顿呼吸 | 句间插入的停顿数与时值 | ≥ 1 处 > 0.25s（人情世故里的"想一想"） |
| 情绪覆盖 | 剧本里出现的情绪种类 | ≥ 2 种（全片一个调 = 七情六欲没进来） |

**平铺基线**＝同一段文字、不带情绪参数、一次念完 —— 拿它当负对照，证明"起伏是真加上去的"。

## 情绪表（zh-TW-HsiaoChenNeural 实测可用参数：rate / pitch / volume）
七情六欲收敛成 8 档，每档给 rate/pitch/volume 与**句后停顿**：

| 情绪 | rate | pitch | volume | 句后停顿 | 用在哪 |
|---|---|---|---|---|---|
| 平（叙述） | +0% | +0Hz | +0% | 0.22s | 交代事实 |
| 喜 | +8% | +12Hz | +6% | 0.18s | 高兴、亲近 |
| 怒 | +14% | +6Hz | +14% | 0.10s | 生气、压人 |
| 哀 | -12% | -14Hz | -10% | 0.45s | 难过、失落 |
| 惧（慌） | +18% | +18Hz | -4% | 0.12s | 害怕、急 |
| 柔（哄） | -8% | -5Hz | -6% | 0.35s | 哄人、亲密 |
| 疑（试探） | -4% | +8Hz | -2% | 0.40s | 人情世故的试探 |
| 叹（无奈） | -10% | -8Hz | -8% | 0.50s | 无奈、感慨 |

## 用法
剧本（每行 `情绪|台词`，`#` 开头是注释）：
    喜|雨还没停耶，我一定要走到那栋楼啦。
    忧|你连伞都没带，走到一半一定会后悔喔。
    疑|我就是不想后悔，才来的啊。
    急|那你最好跑快一点喔，她只等三分钟耶。

    py -3.14 tools/digihuman/voice-emote.py --script dialog.txt \
        --voice zh-TW-HsiaoChenNeural --out outputs/voice-studio/short-video/emo.wav

产出：`emo.wav`（16k 单声道）+ `emo.srt`（**时间轴由实际合成时长算出，不是估的**）+ 回执 json（含上面五项读数与判决）。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]

# 情绪 → (rate, pitch, volume, 句后停顿秒)
# 🔴 2026-10-20 第一版实测未过线（音高起伏 1.13×、力度起伏 0.97×）：真因是**整句只用了一个参数**，
#    句内没有起伏 —— 人说话不是整句一个调。这一版把幅度加大 + 句内分块（见 split_chunks），
#    幅度是"能听出来的"而不是"改了个数字"。改动后必须重跑量具，不许凭改完就报过。
EMO = {
    "平": ("+0%", "+0Hz", "+0%", 0.22),
    "喜": ("+10%", "+26Hz", "+14%", 0.18),
    "怒": ("+16%", "+12Hz", "+26%", 0.10),
    "哀": ("-14%", "-30Hz", "-22%", 0.45),
    "忧": ("-14%", "-28Hz", "-20%", 0.45),      # 忧 与 哀 同档，便于剧本口语
    "惧": ("+20%", "+34Hz", "-10%", 0.12),
    "急": ("+20%", "+32Hz", "-8%", 0.12),       # 急 与 惧 同档
    "柔": ("-10%", "-14Hz", "-14%", 0.35),
    "疑": ("-6%", "+18Hz", "-6%", 0.40),
    "叹": ("-12%", "-20Hz", "-16%", 0.50),
}

# 句内分块：把一句按逗号类标点拆成 2~3 块，逐块给**不同**的音高/力度/语速，
# 让起伏落在句子内部（这是"起伏"的来源，不是整体加音量）。
_CHUNK_SPLIT = re.compile(r"(?<=[，、,；;：:])")

# 每块相对句子基准的偏移（块数 → 依次偏移；+ 是往上/更快）
CHUNK_PITCH = {2: (-4.0, +7.0), 3: (-5.0, +2.0, +9.0)}
CHUNK_VOL = {2: (-2.0, +4.0), 3: (-4.0, +1.0, +6.0)}
CHUNK_RATE = {2: (-2.0, +3.0), 3: (-3.0, 0.0, +4.0)}


for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                                 # noqa: BLE001
        pass


def synth(text: str, voice: str, rate: str, pitch: str, volume: str, out_mp3: Path) -> dict:
    # 🔴 必须用 `--x=值` 的等号形式：`--pitch -14Hz` 里的负号会被 argparse 当成开关名
    #    （报 `argument --pitch: expected one argument`）。这一条是实跑踩出来的，不是猜的。
    cmd = [sys.executable, "-m", "edge_tts", "--voice", voice,
           "--rate=%s" % rate, "--pitch=%s" % pitch, "--volume=%s" % volume,
           "--text", text, "--write-media", str(out_mp3)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=300)
    return {"ok": r.returncode == 0 and out_mp3.is_file(),
            "tail": ((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-3:]}


def to_wav(mp3: Path, wav: Path, sr: int = 16000) -> bool:
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mp3), "-ac", "1",
                        "-ar", str(sr), str(wav)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode == 0 and wav.is_file()


def read_wav(p: Path) -> tuple:
    with wave.open(str(p), "rb") as w:
        sr, n, ch, sw = w.getframerate(), w.getnframes(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    return a, sr


def write_wav(p: Path, a: np.ndarray, sr: int = 16000) -> None:
    x = np.clip(a, -1.0, 1.0)
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((x * 32767.0).astype(np.int16).tobytes())


# ── 量具：F0（自相关）+ 八度纠正 + 半音刻度；能量用 dB ────────────────────
# 🔴 2026-10-20 第一版量具是错的（本仓 P1「判据错尺」）：单一人声量出 f0_std=45.8Hz、
#    f0_range=426.9Hz —— 那是**八度跳变噪声**，不是情感。修法三件：
#    ① 窗口加长到 2048、自相关先归一化、峰值 <0.3 判为无浊音；
#    ② 中值滤波 + 相邻帧倍频纠正（1.6× / 0.625× 阈值），把跳八度摁掉；
#    ③ 音高起伏改用**半音（12·log2）**的标准差；能量改用 **dB 包络**的 p95-p10 ——
#       线性 RMS 的标准差会被整体音量大小带偏，dB 不会。
def f0_track(a: np.ndarray, sr: int, win: int = 2048, hop: int = 256,
             fmin: float = 70.0, fmax: float = 520.0) -> np.ndarray:
    lo, hi = int(sr / fmax), int(sr / fmin)
    out = []
    for i in range(0, max(1, len(a) - win), hop):
        fr = a[i:i + win]
        if fr.size < win or float(np.sqrt((fr ** 2).mean())) < 0.012:
            out.append(np.nan)                       # 静音/太轻不算音高
            continue
        fr = fr - fr.mean()
        c = np.correlate(fr, fr, "full")[win - 1:]
        if c.size <= hi or c[0] <= 0:
            out.append(np.nan)
            continue
        c = c / c[0]                                  # 归一化：不同响度的句子可比
        seg = c[lo:hi]
        if seg.size < 3 or not np.isfinite(seg).all():
            out.append(np.nan)
            continue
        k = int(np.argmax(seg)) + lo
        peak = float(seg.max())
        out.append(sr / k if (k > 0 and peak >= 0.30) else np.nan)
    return _fix_octaves(np.array(out, dtype=np.float32))


def _fix_octaves(f0: np.ndarray) -> np.ndarray:
    """中值滤波 + 倍频纠正：把自相关偶发跳八度的帧拉回来。"""
    v = np.array(f0, dtype=np.float32, copy=True)
    idx = np.where(np.isfinite(v))[0]
    if idx.size == 0:
        return v
    sm = v.copy()
    for i in idx:                                     # 中值滤波（窗口 5）
        lo, hi = max(0, i - 2), min(len(v), i + 3)
        w = v[lo:hi]
        w = w[np.isfinite(w)]
        if w.size:
            sm[i] = float(np.median(w))
    for i in range(1, len(sm)):                        # 相邻帧倍频纠正
        a0, b0 = float(sm[i - 1]), float(sm[i])
        if not (np.isfinite(a0) and np.isfinite(b0)) or a0 <= 0:
            continue
        r = b0 / a0
        if r > 1.6:
            cand = (b0 / 2.0, b0)
        elif r < 0.625:
            cand = (b0 * 2.0, b0)
        else:
            continue
        sm[i] = min(cand, key=lambda x: abs(x - a0))
    return sm


def rms_env(a: np.ndarray, win: int = 1024, hop: int = 256) -> np.ndarray:
    out = []
    for i in range(0, max(1, len(a) - win), hop):
        fr = a[i:i + win]
        out.append(float(np.sqrt((fr.astype(np.float64) ** 2).mean())) if fr.size else 0.0)
    return np.array(out, dtype=np.float32)


def metrics(a: np.ndarray, sr: int, n_chars: int, dur: float) -> dict:
    f0 = f0_track(a, sr)
    v = f0[np.isfinite(f0)]
    r = rms_env(a)
    voiced = r[r > 0.02]
    db = 20.0 * np.log10(voiced + 1e-9) if voiced.size else np.array([])
    st = 12.0 * np.log2(v / 100.0) if v.size else np.array([])      # 半音刻度（参考 100Hz 不影响 std）
    return {
        "dur_s": round(dur, 3),
        "f0_median_hz": round(float(np.median(v)), 1) if v.size else None,
        "f0_std_st": round(float(np.std(st)), 2) if st.size else None,        # ← 主判据：半音起伏
        "f0_range_st": round(float(st.max() - st.min()), 2) if st.size else None,
        "db_std": round(float(np.std(db)), 2) if db.size else None,
        "db_range": round(float(np.percentile(db, 95) - np.percentile(db, 10)), 2) if db.size else None,
        "chars_per_s": round(n_chars / dur, 2) if dur > 0 else None,
    }


def parse_script(p: Path) -> list:
    rows = []
    for ln, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "|" in s:
            emo, txt = s.split("|", 1)
            emo, txt = emo.strip(), txt.strip()
        else:
            emo, txt = "平", s
        if emo not in EMO:
            raise SystemExit("第 %d 行情绪「%s」不在情绪表里（可用：%s）"
                             % (ln, emo, "、".join(EMO)))
        if not txt:
            continue
        rows.append({"line": ln, "emotion": emo, "text": txt})
    return rows


def _num(s: str) -> float:
    """'+26Hz' / '-30Hz' / '+10%' → 数值（不带单位）。"""
    return float(re.sub(r"[^0-9.+-]", "", str(s)) or 0)


def split_chunks(text: str) -> list:
    """按逗号类标点把一句拆成 2~3 块（太多就不拆，块太碎反而假）。"""
    parts = [p for p in _CHUNK_SPLIT.split(text or "") if p.strip()]
    if len(parts) <= 1:
        return [text]
    if len(parts) > 3:                      # 超过 3 块就合并尾部，别碎成机器味
        parts = parts[:2] + ["".join(parts[2:])]
    return parts


def synth_cue(text: str, voice: str, rate: str, pitch: str, volume: str,
              tmp: Path, idx: int, sr: int = 16000) -> tuple:
    """一句之内再分块，逐块给不同的音高/力度/语速 —— 起伏要落在**句内**。"""
    chunks = split_chunks(text)
    n = len(chunks)
    pr, pp, pv = _num(rate), _num(pitch), _num(volume)
    pitchs = CHUNK_PITCH.get(n)
    vols = CHUNK_VOL.get(n)
    rates = CHUNK_RATE.get(n)
    segs, detail = [], []
    for j, ch in enumerate(chunks):
        p2 = pp + (pitchs[j] if pitchs else 0.0)
        v2 = pv + (vols[j] if vols else 0.0)
        r2 = pr + (rates[j] if rates else 0.0)
        mp3 = tmp / ("c%02d_%d.mp3" % (idx, j))
        wav = tmp / ("c%02d_%d.wav" % (idx, j))
        s = synth(ch, voice, "%+d%%" % round(r2), "%+dHz" % round(p2), "%+d%%" % round(v2), mp3)
        if not s["ok"] or not to_wav(mp3, wav, sr):
            return None, {"chunk": j, "text": ch, "tail": s["tail"]}
        a, _ = read_wav(wav)
        segs.append(a)
        detail.append({"chunk": j, "text": ch, "rate": "%+d%%" % round(r2),
                       "pitch": "%+dHz" % round(p2), "volume": "%+d%%" % round(v2)})
        if j < n - 1:                       # 块间留一口气，不要连成一坨
            segs.append(np.zeros(int(0.07 * sr), dtype=np.float32))
    return (np.concatenate(segs) if segs else np.zeros(1, dtype=np.float32)), detail


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True, help="剧本文件：每行 情绪|台词")
    ap.add_argument("--voice", default="zh-TW-HsiaoChenNeural")
    ap.add_argument("--out", required=True, help="输出 wav（同名 .srt 与 .json 一起落）")
    ap.add_argument("--base-rate", default="+12%", help="整体基准语速（叠在情绪参数之上）")
    ap.add_argument("--no-baseline", action="store_true", help="不跑平铺基线（省 10 秒）")
    a = ap.parse_args()

    rows = parse_script(Path(a.script))
    if not rows:
        print(json.dumps({"ok": False, "why": "剧本是空的"}, ensure_ascii=False))
        return 2

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="gbt-emote-"))
    sr = 16000

    cues, parts = [], []
    t = 0.0
    base = int(a.base_rate.strip("%+") or 0)
    for i, r in enumerate(rows):
        rate, pitch, vol, gap = EMO[r["emotion"]]
        # 基准语速与情绪语速叠加（都是 "+N%" 形式，直接相加）
        emo_n = int(rate.strip("%+") or 0)
        rate2 = "%+d%%" % (base + emo_n)
        seg, detail = synth_cue(r["text"], a.voice, rate2, pitch, vol, tmp, i, sr)
        if seg is None:
            print(json.dumps({"ok": False, "why": "第 %d 句合成失败" % (i + 1),
                              "line": r["line"], "chunk": detail}, ensure_ascii=False))
            return 3
        d = len(seg) / sr
        cues.append({"idx": i + 1, "emotion": r["emotion"], "text": r["text"],
                     "start": round(t, 3), "end": round(t + d, 3),
                     "rate": rate2, "pitch": pitch, "volume": vol, "gap_after": gap,
                     "chunks": detail})
        t += d
        parts.append(seg)
        # 句后停顿（情绪越沉越长）—— 这是"人情世故"里那半秒的犹豫
        if i < len(rows) - 1 and gap > 0:
            silence = np.zeros(int(gap * sr), dtype=np.float32)
            parts.append(silence)
            t += gap

    full = np.concatenate(parts) if parts else np.zeros(1, dtype=np.float32)
    write_wav(out, full, sr)
    total = len(full) / sr

    # 字幕：时间轴由**实际合成时长**算出，不是估的
    srt = out.with_suffix(".srt")
    lines = []
    for c in cues:
        lines += [str(c["idx"]), "%s --> %s" % (_ts(c["start"]), _ts(c["end"])), c["text"], ""]
    srt.write_text("\n".join(lines), encoding="utf-8")

    # 逐句量（起伏在句内）
    per_cue = []
    for c in cues:
        s0, s1 = int(c["start"] * sr), int(c["end"] * sr)
        seg = full[s0:s1]
        m = metrics(seg, sr, len(c["text"]), (s1 - s0) / sr)
        m.update({"idx": c["idx"], "emotion": c["emotion"]})
        per_cue.append(m)

    voices = {c["emotion"] for c in cues}
    cps = [m["chars_per_s"] for m in per_cue if m["chars_per_s"]]
    rate_spread = (max(cps) - min(cps)) / (sum(cps) / len(cps)) if len(cps) > 1 else 0.0
    long_pauses = [c["gap_after"] for c in cues[:-1] if c["gap_after"] >= 0.25]

    rep = {"ok": True, "voice": a.voice, "out": str(out), "srt": str(srt),
           "cues": len(cues), "dur_s": round(total, 3), "emotions": sorted(voices),
           "rate_spread_pct": round(rate_spread * 100, 1),
           "long_pauses": len(long_pauses), "base_rate": a.base_rate,
           "per_cue": per_cue, "台词": cues}

    # 负对照（**同对象比**）：同样的每一句、同样的切分、不加情绪参数念一遍。
    # 🔴 第一版拿"整段一次念完"当基线去比"逐句均值" —— 那是拿 A 量 B（本仓 P1 实证），
    #    基线自己带 14 秒的长停顿与换气，起伏天然更大，怎么加情绪都赢不了。必须一句对一句。
    if not a.no_baseline:
        flat_cues, flat_fail = [], None
        for i, c in enumerate(cues):
            mp3 = tmp / ("f%02d.mp3" % i)
            wav = tmp / ("f%02d.wav" % i)
            s = synth(c["text"], a.voice, a.base_rate, "+0Hz", "+0%", mp3)
            if not s["ok"] or not to_wav(mp3, wav, sr):
                flat_fail = {"idx": i + 1, "tail": s["tail"]}
                break
            fa, _ = read_wav(wav)
            flat_cues.append(metrics(fa, sr, len(c["text"]), len(fa) / sr))
        if flat_fail or not flat_cues:
            rep["baseline"] = {"ok": False, "why": "逐句平铺基线合成失败", "detail": flat_fail}
            rep["情感达标"] = None
            rep["判决"] = "基线缺失 ⇒ 无法判（不折绿）"
        else:
            def _mean(rows, key):
                xs = [r[key] for r in rows if r.get(key) is not None]
                return (sum(xs) / len(xs)) if xs else None

            emo_f0 = _mean(per_cue, "f0_std_st")
            flat_f0 = _mean(flat_cues, "f0_std_st")
            emo_db = _mean(per_cue, "db_range")
            flat_db = _mean(flat_cues, "db_range")
            f0_ratio = (emo_f0 / flat_f0) if (emo_f0 and flat_f0) else None
            db_ratio = (emo_db / flat_db) if (emo_db and flat_db) else None
            rep["baseline"] = {
                "口径": "逐句同文同切分的平铺版（一句对一句）",
                "flat_cues": flat_cues,
                "emo_mean_f0_std_st": None if emo_f0 is None else round(emo_f0, 2),
                "flat_mean_f0_std_st": None if flat_f0 is None else round(flat_f0, 2),
                "emo_mean_db_range": None if emo_db is None else round(emo_db, 2),
                "flat_mean_db_range": None if flat_db is None else round(flat_db, 2),
                "f0_std_ratio": None if f0_ratio is None else round(f0_ratio, 2),
                "db_range_ratio": None if db_ratio is None else round(db_ratio, 2),
            }
            checks = {
                "音高起伏≥1.15×": (f0_ratio is not None and f0_ratio >= 1.15,
                                    None if f0_ratio is None else round(f0_ratio, 2), 1.15),
                "力度起伏≥1.10×": (db_ratio is not None and db_ratio >= 1.10,
                                    None if db_ratio is None else round(db_ratio, 2), 1.10),
                "语速极差≥8%": (rate_spread >= 0.08, round(rate_spread * 100, 1), 8.0),
                "有长停顿≥1": (len(long_pauses) >= 1, len(long_pauses), 1),
                "情绪≥2种": (len(voices) >= 2, len(voices), 2),
            }
            rep["每条"] = {k: {"读数": v[1], "线": v[2], "过": bool(v[0])} for k, v in checks.items()}
            rep["情感达标"] = all(v[0] for v in checks.values())
            rep["判决"] = ("情感读数全绿" if rep["情感达标"]
                           else "未达标：" + "、".join(k for k, v in checks.items() if not v[0]))
    else:
        rep["情感达标"] = None
        rep["判决"] = "未跑基线 ⇒ 无法判（不折绿）"

    jout = out.with_suffix(".json")
    jout.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in rep.items() if k not in ("per_cue", "台词")},
                     ensure_ascii=False, indent=1))
    print("REPORT " + str(jout))
    return 0 if rep.get("情感达标") else 7


def _ts(t: float) -> str:
    t = max(0.0, float(t))
    h, m, s = int(t // 3600), int((t % 3600) // 60), t % 60
    return "%02d:%02d:%06.3f" % (h, m, s)


if __name__ == "__main__":
    sys.exit(main())
