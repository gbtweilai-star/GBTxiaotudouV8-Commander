# -*- coding: utf-8 -*-
"""试听曲渲染器 —— 给「AI 音乐」面板做一件**真能听**的排练垫乐。

## 为什么要自己合成，而不是拿现成的

面板上要能试听，先得盘上有东西可听。本机现读：
· 别人的素材（`_upstream/.../warm-pad.mp3`）—— **不是我们的**，拿来当"我们的歌"是冒充
· 浏览器扩展自带的 mp3 —— 第三方，不许用
· TTS 语音缓存 —— 是说话不是音乐
· `music/06-release/…-rehearsal.flac` —— 我上一轮 ffmpeg 合成的**正弦音**，不是音乐
⇒ 没有成品歌曲。所以本器**自产**一件：出处无歧义 ⇒ 许可可以**如实**写「自有」。

## 它是什么、不是什么（这句话必须跟着产物走）

· **是**：本机 numpy 加法合成 + 仓内 `audio_mix` 母带（-14 LUFS 流媒体目标）的**排练垫乐**
· **不是**：`music-production` §6 明写「生成在**第三方 Suno** 上做」—— 生成端**未接线**
  （框架自报 `external_generators_connected=False`）
· **尤其是**：它**不是**《夜航》的编曲。仓里那份歌词件写着情绪线
  「闷 → 松开 → 短暂的自由 → 舍不得结束 → 还是得回去」—— 本器**照着这条情绪线**做段落，
  但旋律/编曲仍标**未做**（`02-compose` / `03-arrange` 无实现器）。

## 跑法

    py -3.14 tools/codex-scripts/audition-render.py
"""

import io
import struct
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
sys.path.insert(0, str(ROOT))

SR = 48000
DUR = 52.0
STEM = ROOT / ".scratch" / "_audition"
MASTER_REL = "projects/music/05-master/20260923-music-试听垫乐-rehearsal.wav"
SHARE_DIR = ROOT / "projects" / "_shared" / "audition"
OPUS_NAME = "20260923-music-试听垫乐-rehearsal.opus"

# 记谱：A 小调。频率按十二平均律从 A4=440 算，**不手抄频率表**。
_NAMES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def hz(name: str) -> float:
    """`A3` / `F#4` → Hz。算出来的，不是抄来的。"""
    base, octv = name[0].upper(), int(name[-1])
    semi = _NAMES[base] + (1 if "#" in name else 0)
    return 440.0 * (2.0 ** ((semi - 9) / 12.0 + (octv - 4)))


# 五段，照着《夜航》件里那条情绪线走
SECTIONS = [
    ("闷",           "Am7",  ["A2", "E3", "A3", "C4", "G4"],            None,                     0.32),
    ("松开",         "Fmaj7", ["F2", "C3", "F3", "A3", "E4"],           None,                     0.52),
    ("短暂的自由",   "Cmaj7", ["C3", "G3", "C4", "E4", "B4"],           ["A4", "C5", "B4", "E5"], 0.72),
    ("舍不得结束",   "G6",    ["G2", "D3", "G3", "B3", "E4"],           ["D5", "E5", "B4", "G4"], 0.88),
    ("还是得回去",   "Am7",   ["A2", "E3", "A3", "C4", "G4"],           None,                     0.40),
]
HARM = (1.0, 0.45, 0.22, 0.12, 0.06, 0.03)
T60 = 2.4
WET = 0.26


def _env(n: int, atk: float, rel: float, sr: int = SR) -> np.ndarray:
    """软起音 + 长释放的包络（余弦升降，不会有咔哒声）。"""
    a = max(1, int(atk * sr))
    r = max(1, int(rel * sr))
    e = np.ones(n)
    e[:a] = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, a))
    e[-r:] *= 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, r))
    return e


def voice(f: float, dur: float, amp: float, detune_cents: float = 0.0) -> np.ndarray:
    """加法合成一条声部（含轻微失谐 —— 两声道各给一点，出来就有宽度）。"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f * (2.0 ** (detune_cents / 1200.0))
    out = np.zeros(n)
    for k, a in enumerate(HARM, 1):
        if f * k > SR / 2.2:
            break
        # 每个泛音给一点点随机相位，避免所有声部叠成一根尖脉冲
        ph = (k * 1.7 + f * 0.013) % (2 * np.pi)
        out += a * np.sin(2 * np.pi * f * k * t + ph)
    return out * _env(n, 1.1, 2.6) * amp


def render() -> np.ndarray:
    n = int(DUR * SR)
    left = np.zeros(n)
    right = np.zeros(n)
    seg = DUR / len(SECTIONS)

    for si, (cn, chord, tones, mel, level) in enumerate(SECTIONS):
        t0 = si * seg
        start = int(t0 * SR)
        # 段落之间留一点交叠（前一节的释放盖到后一节里），听起来才连得上
        dur = seg + 3.2
        for vi, tn in enumerate(tones):
            v = voice(hz(tn), dur, level / (1.0 + 0.5 * vi))
            # 按声部高低铺开声场：低的靠中间，高的往两边去
            width = 0.12 + 0.72 * (vi / max(1, len(tones) - 1))
            seg_len = v.shape[0]
            end = min(n, start + seg_len)
            cut = end - start
            left[start:end] += v[:cut] * (0.5 - 0.5 * width)
            right[start:end] += v[:cut] * (0.5 + 0.5 * width)
        # 低音：根音低八度（`Am7` → A2，再取一半作超低），居中
        root_f = hz(chord_tones_root(chord) + "2")
        bass = voice(root_f, dur, level * 0.85)
        sub = voice(root_f / 2.0, dur, level * 0.55)
        end = min(n, start + bass.shape[0])
        cut = end - start
        left[start:end] += (bass[:cut] + sub[:cut]) * 0.5
        right[start:end] += (bass[:cut] + sub[:cut]) * 0.5
        # 旋律：只在后三段进
        if mel:
            step = seg / len(mel)
            for mi, mn in enumerate(mel):
                ms = start + int(mi * step * SR)
                mv = voice(hz(mn), step * 1.9, level * 0.34, detune_cents=3.0)
                mv = mv * (1.0 + 0.004 * np.sin(2 * np.pi * 4.6 * np.arange(mv.shape[0]) / SR))
                e2 = min(n, ms + mv.shape[0])
                c2 = e2 - ms
                pan = 0.5 + 0.18 * (1 if mi % 2 else -1)
                left[ms:e2] += mv[:c2] * (1.0 - pan) * 2
                right[ms:e2] += mv[:c2] * pan * 2

    st = np.stack([left, right])
    return reverb(st)


def chord_tones_root(chord: str) -> str:
    """`Am7` → `A`，`Fmaj7` → `F` —— 低音只要根音名。"""
    return chord[0].upper()


def reverb(x: np.ndarray) -> np.ndarray:
    """一个朴素的指数衰减噪声脉冲响应 + FFT 卷积（不引第三方混响）。"""
    ir_n = int(T60 * SR)
    rng = np.random.default_rng(20260923)
    t = np.arange(ir_n) / SR
    env = np.exp(-6.9078 * t / T60)                    # -60 dB 处到 T60
    ir = rng.standard_normal((2, ir_n)) * env
    ir[:, :int(0.012 * SR)] = 0.0                      # 12 ms 预延迟
    ir /= np.sqrt((ir ** 2).sum(axis=1, keepdims=True))
    n = 1
    while n < x.shape[1] + ir_n:
        n *= 2
    wet = np.fft.irfft(np.fft.rfft(x, n, axis=1) * np.fft.rfft(ir, n, axis=1), n, axis=1)
    wet = wet[:, :x.shape[1]]
    wet /= max(1e-9, np.abs(wet).max())
    wet *= np.abs(x).max()
    return x * (1.0 - WET) + wet * WET


def master_chain(x: np.ndarray) -> np.ndarray:
    """软限幅 + 首尾淡入淡出。**不做响度对齐** —— 那是 `audio_mix.master` 的活（两遍法）。"""
    x = np.tanh(x * 1.25) / np.tanh(1.25)
    x /= max(1e-9, np.abs(x).max())
    x *= 0.89                                          # 留 ~1 dB 余量给 loudnorm
    f = int(1.6 * SR)
    x[:, :f] *= np.linspace(0, 1, f) ** 2
    o = int(5.5 * SR)
    x[:, -o:] *= np.linspace(1, 0, o) ** 1.5
    return x


def write_wav_f32(path: Path, x: np.ndarray) -> None:
    """手写 32-bit float WAV —— `wave` 模块不认浮点，而浮点是这里唯一诚实的中间格式。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    ch, n = x.shape
    data = np.ascontiguousarray(x.T.astype("<f4")).tobytes()
    hdr = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt "
    hdr += struct.pack("<IHHIIHH", 16, 3, ch, SR, SR * ch * 4, ch * 4, 32)
    hdr += b"data" + struct.pack("<I", len(data))
    with io.open(path, "wb") as fh:
        fh.write(hdr + data)


def main() -> int:
    t0 = time.time()
    int(DUR * SR)
    print("=" * 74)
    print("试听曲渲染 · 排练垫乐（自产 · 出处无歧义）")
    print("=" * 74)
    print("  段落（照《夜航》件里那条情绪线）：")
    for cn, chord, tones, mel, lv in SECTIONS:
        print("    %-12s %-6s %s%s" % (cn, chord, " ".join(tones),
                                       ("  + 旋律 " + " ".join(mel)) if mel else ""))
    x = master_chain(render())
    peak = float(np.abs(x).max())
    rms = float(np.sqrt((x ** 2).mean()))
    print("\n  合成读数：采样率 %d Hz · 声道 %d · %.1f s · 峰值 %.2f dBFS · RMS %.2f dBFS"
          % (SR, x.shape[0], x.shape[1] / SR, 20 * np.log10(max(1e-9, peak)),
             20 * np.log10(max(1e-9, rms))))

    mix = STEM / "试听垫乐-mix.wav"
    write_wav_f32(mix, x)
    print("  中间件：%s（%.2f MB）" % (mix.relative_to(ROOT), mix.stat().st_size / 1e6))

    from gbt_allinone.tools import audio_mix as AM
 # `format` **必须显式给**：`master` 的默认格式是 **mp3**，
    #    第一版我没传 ⇒ 落了一个 **内容 mp3、名字 .wav** 的件（扩展名与内容不符），
    #    而且它还被当成源又编了一遍 Opus（**有损转有损**）。
    r = AM.run("master", src=str(mix), out=MASTER_REL, format="wav",
               target="streaming", genre="ambient", root=str(ROOT))
    if not r.get("ok"):
        print("  ❌ 母带失败：%s" % r)
        return 1
    before = r.get("measured_before") or {}
    after = r.get("measured_after") or {}
    print("  母带  ：%s" % MASTER_REL)
    print("          目标 %s（I=%s LUFS · TP=%s dBTP）"
          % (r.get("target"), (r.get("target_spec") or {}).get("I"),
             (r.get("target_spec") or {}).get("TP")))
    print("          施加前 %s LUFS / TP %s dBTP ｜ 施加后 %s LUFS / TP %s dBTP"
          % (before.get("input_i"), before.get("input_tp"),
             after.get("input_i"), after.get("input_tp")))
    print("          与目标差 %.2f LU ｜ 命中(±0.5 LU) = %s ｜ 产物复核 = %s"
          % (r.get("delta_lu", float("nan")), r.get("hit_target"), r.get("verified")))
    prod = r.get("product") or {}
    print("          产物：%s · %s ch · %s Hz · %s s · %.1f MB"
          % (prod.get("codec"), prod.get("channels"), prod.get("sample_rate"),
             prod.get("duration_s"), (prod.get("bytes") or 0) / 1e6))

    SHARE_DIR.mkdir(parents=True, exist_ok=True)
    opus = SHARE_DIR / OPUS_NAME
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(ROOT / MASTER_REL), "-c:a", "libopus", "-b:a", "128k",
                    "-vbr", "on", "-application", "audio", "-ar", "48000",
                    str(opus)], check=True)
    print("  试听件：%s（%.0f KB · Opus 128 kbps）"
          % (opus.relative_to(ROOT), opus.stat().st_size / 1024))

    # 读数副档：面板据此显示，并**自己再 ffprobe 复核一遍**（两侧对不上就如实报）
    import hashlib
    import json
    side = SHARE_DIR / "audition.json"
    side.write_text(json.dumps({
        "件": OPUS_NAME,
        "母带": MASTER_REL,
        "产出器": "tools/codex-scripts/audition-render.py",
        "这是": "本机 numpy 加法合成的**排练垫乐**，走《夜航》件里那条情绪线",
        "这不是": ["不是 Suno 或任何生成端的产物（框架自报 external_generators_connected=False）",
                "不是《夜航》的编曲 —— 旋律/编曲仍标**未做**",
                "不是成品歌曲，是**试听用排练件**"],
        "段落": [{"情绪": cn, "和弦": chord, "声部": tones, "旋律": mel or []}
               for cn, chord, tones, mel, _lv in SECTIONS],
        "许可": {"source": "本机自产（numpy 加法合成 + 仓内 audio_mix 母带）", "license": "自有"},
        "采样率": SR, "时长_s": round(float(prod.get("duration_s") or DUR), 3),
        "声道": int(prod.get("channels") or 2),
        "母带格式": prod.get("codec"),
        "母带字节": prod.get("bytes"),
        "响度": {"目标": r.get("target"), "目标I": (r.get("target_spec") or {}).get("I"),
               "目标TP": (r.get("target_spec") or {}).get("TP"),
               "施加前LUFS": before.get("input_i"), "施加前TP": before.get("input_tp"),
               "施加后LUFS": after.get("input_i"), "施加后TP": after.get("input_tp"),
               "差LU": r.get("delta_lu"), "命中": r.get("hit_target"),
               "曲风LRA": r.get("genre_lra")},
        "试听件字节": opus.stat().st_size,
        "试听件sha256": hashlib.sha256(opus.read_bytes()).hexdigest()[:16],
        "母带sha256": hashlib.sha256((ROOT / MASTER_REL).read_bytes()).hexdigest()[:16],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("  读数副档：%s" % side.relative_to(ROOT))
    print("  用时 %.1f s" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
