# -*- coding: utf-8 -*-
"""finish-clip.py — 数字人闭环唯一的**入口件**：一句话/一张图 → 出片 → 只过达标才上云。

## 为什么收敛成一条命令（2026-10-20 主人令「跑通闭环固化」）
两条片子跑下来，同一件事要手敲 6 条命令、手切字幕、手动看字号 —— 那不叫闭环，叫手工活。
这一件把「配音 → 字幕 → 渲染 → 微动 → 交付 → 三口径验收 → 上云 → 记账」焊成**一次调用**：

  ① **配音**（`--text`）：edge-tts `zh-TW-HsiaoChenNeural`（台湾腔）或 `zh-CN-XiaoxiaoNeural`
  ② **字幕**（`--text` 未给 srt 时自动切）：靠 `silencedetect` 找停顿，按停顿切句，**不猜时间轴**
  ③ **渲染**（`--render` + `--image`）：SadTalker + `--enhancer gfpgan`（**高清=GFPGAN upscale=2**）+ `--no-still`（否则头不动）
  ④ **微动**（默认开）：`body-motion.py` 逐行 S 形重心转移，音频驱动
  ⑤ **交付**：`deliver.py` 只编一次 x264 crf16 + 中文字幕（字号**按画面宽**自动算）
  ⑥ **验收**：`qc-video.py` 三条口径（画质/动作/嘴），`--max-width 736 --ref-width 736`
  ⑦ **上云**：只在上一步**全绿**时发布（`--allow-fail-publish` 才放行失败件），公网回下载比 sha256
  ⑧ **记账**：每次一行进 `state/dh-loop.jsonl`（含每一步秒数、读数、判决、产物 sha16）

## 口径（写死，不许悄悄放宽）
- 画质 ratio ≥ 0.90 · 动作 head_move ≥ 0.15 且 flicker ≤ 0.08 · 嘴 r ≥ 0.55 且 |lag| ≤ 2 帧 且负控 ≤ 0.15
- **等不到原始件就如实退出**；任一步失败就停在那一步并把上游原话打出来（不带着坏件往下走）
- **中间件与成品分名**：`<id>-raw.mp4`（渲染原始）/ `<id>-sway.mp4`（微动版）/ `<id>.mp4`（交付件）
  —— 踩过的坑：三者撞名时交付件会**覆盖**原始件，重做字幕就得再等两小时。

## 用法
一条命令出片（台湾腔 + 全身 + 自动字幕）：
  py -3.14 tools/digihuman/finish-clip.py --render \
     --image outputs/ref/character-ref.png \
     --text "雨还没停耶，我一定要走到那栋楼啦。你连伞都没带……" \
     --source outputs/ref/character-ref.png \
     --id fullbody-tw-v6 --title "全身・台灣腔" --framing full-body --voice "台灣腔（曉臻）"

只跑收尾（片子已在渲/已渲完）：
  py -3.14 tools/digihuman/finish-clip.py --raw outputs/dh-talk/x-raw.mp4 \
     --audio outputs/voice-studio/short-video/tw-chen15.wav --srt ... --source ... --id x

先看要跑什么（不执行）：
  py -3.14 tools/digihuman/finish-clip.py --render --image ... --text "..." --id x --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VENV_PY = ROOT / ".venv-sadtalker" / "Scripts" / "python.exe"
OUTDIR = ROOT / "outputs" / "dh-talk"
VEDIR = ROOT / "outputs" / "voice-studio" / "short-video"
LOOP_LEDGER = ROOT / "state" / "dh-loop.jsonl"

# 三条达标线 —— 写死在这里，改它必须同时改 qc-video 与技能文档，并在账本里写清为什么翻
GATE = {"ratio": 0.90, "head_move": 0.15, "flicker": 0.08, "r": 0.55, "lag": 2, "neg": 0.15}

VOICES = {
    "tw": "zh-TW-HsiaoChenNeural",       # 台湾腔女声（曉臻）
    "tw_yun": "zh-TW-YunJheNeural",      # 台湾腔男声
    "cn": "zh-CN-XiaoxiaoNeural",        # 普通話女声（曉曉）
}

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                                 # noqa: BLE001
        pass


def run(tag: str, cmd: list, timeout: int = 7200) -> dict:
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout)
    out = (r.stdout or "") + (r.stderr or "")
    rec = {"step": tag, "rc": r.returncode, "secs": round(time.time() - t0, 1),
           "tail": out.strip().splitlines()[-6:] if out.strip() else []}
    print("STEP " + json.dumps(rec, ensure_ascii=False), flush=True)
    return {**rec, "text": out}


def _sha16(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.is_file() else ""


def _dur(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    try:
        return float((r.stdout or "0").strip())
    except ValueError:
        return 0.0


# ── ① 配音 ────────────────────────────────────────────────────────────────
def tts(text: str, voice: str, rate: str, out_wav: Path) -> dict:
    """edge-tts 合成：先落 mp3 再转 16k 单声道 wav（qc 与 SadTalker 都吃这个口径）。"""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    mp3 = out_wav.with_suffix(".mp3")
    cmd = [str(VENV_PY), "-m", "edge_tts", "--voice", voice, "--rate", rate,
           "--text", text, "--write-media", str(mp3)]
    r = run("tts", cmd, timeout=600)
    if r["rc"] != 0 or not mp3.is_file():
        return {"ok": False, "tail": r["tail"]}
    r = run("tts.wav", ["ffmpeg", "-y", "-v", "error", "-i", str(mp3),
                        "-ac", "1", "-ar", "16000", str(out_wav)], timeout=600)
    if r["rc"] != 0 or not out_wav.is_file():
        return {"ok": False, "tail": r["tail"]}
    return {"ok": True, "wav": str(out_wav), "secs": round(_dur(out_wav), 3),
            "bytes": out_wav.stat().st_size}


# ── ② 自动字幕（按停顿切句，不猜时间轴）────────────────────────────────────
_CLAUSE = re.compile(r"[^。！？!?…]+[。！？!?…]*")


def _clauses(text: str) -> list:
    parts = [c.strip() for c in _CLAUSE.findall(text or "") if c.strip()]
    # 太短的并进上一句（"耶。" 这种单独成条会闪一下）
    out: list = []
    for c in parts:
        if out and len(c) <= 4:
            out[-1] += c
        else:
            out.append(c)
    return out


def _pauses(wav: Path, noise: str = "-30dB", dur_s: float = 0.25) -> list:
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(wav),
                        "-af", "silencedetect=noise=%s:d=%s" % (noise, dur_s),
                        "-f", "null", "-"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    log = (r.stderr or "")
    starts = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", log)]
    return [{"start": s, "end": (ends[i] if i < len(ends) else None)}
            for i, s in enumerate(starts)]


def auto_srt(wav: Path, text: str, out_srt: Path) -> dict:
    """按"最长的那几段停顿"切句：句数由文本标点定，切点由停顿定 —— 两边都不许瞎编。"""
    dur = _dur(wav)
    cs = _clauses(text)
    if not cs:
        return {"ok": False, "why": "文本里没有可分句的内容"}
    need = len(cs) - 1
    ps = _pauses(wav)
    if need > 0 and len(ps) < need:
        # 停顿不够就按字数比例硬分（仍然落在音频时长内，不越界）
        bounds = [dur * (i + 1) / (len(cs)) for i in range(need)]
        how = "字数均分（停顿只找到 %d 段，不够 %d 个切点）" % (len(ps), need)
    else:
        picked = sorted(ps, key=lambda p: ((p["end"] or dur) - p["start"]), reverse=True)[:need]
        picked.sort(key=lambda p: p["start"])
        bounds = [((p["start"] + (p["end"] or p["start"])) / 2.0) for p in picked]
        how = "停顿切句（取了 %d 段最长停顿的中点）" % len(picked)
    lines = []
    for i, c in enumerate(cs):
        t0 = 0.0 if i == 0 else bounds[i - 1]
        t1 = bounds[i] if i < len(bounds) else dur
        lines += [str(i + 1), "%s --> %s" % (_ts(t0), _ts(t1)), c, ""]
    out_srt.parent.mkdir(parents=True, exist_ok=True)
    out_srt.write_text("\n".join(lines), encoding="utf-8")
    return {"ok": True, "srt": str(out_srt), "cues": len(cs), "how": how, "dur": round(dur, 3)}


def _ts(t: float) -> str:
    t = max(0.0, float(t))
    h, m, s = int(t // 3600), int((t % 3600) // 60), t % 60
    return "%02d:%02d:%06.3f" % (h, m, s)


# ── ③ 渲染 ────────────────────────────────────────────────────────────────
def render(image: Path, wav: Path, raw: Path, size: int, enhancer: str) -> dict:
    """SadTalker：`--enhancer gfpgan`（高清=upscale×2）与 `--no-still`（头才会动）都是**必须**的。"""
    cmd = [str(VENV_PY), str(ROOT / "tools" / "digihuman" / "talk-photo.py"),
           "--image", str(image), "--audio", str(wav), "--out", str(raw),
           "--size", str(size)]
    if enhancer:
        cmd += ["--enhancer", enhancer]
    cmd += ["--no-still"]
    r = run("render", cmd, timeout=6 * 3600)
    return {"ok": r["rc"] == 0 and raw.is_file(), "tail": r["tail"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    # 输入
    ap.add_argument("--image", default="", help="参考图（--render 时必填）")
    ap.add_argument("--text", default="", help="要念的文本（自动配音+自动字幕）")
    ap.add_argument("--text-file", default="", help="长文本落文件时用这个（避免命令行转义地狱）")
    ap.add_argument("--voice", default="tw", help="tw | cn | tw_yun | 或直接给 edge-tts voice id")
    ap.add_argument("--rate", default="+15%", help="语速，默认 +15%%（台湾腔实测 13.7s/150字）")
    ap.add_argument("--raw", default="", help="已有的渲染原始件（跳过渲染与配音）")
    ap.add_argument("--audio", default="", help="已有的配音 wav（跳过配音）")
    ap.add_argument("--srt", default="", help="已有的字幕（跳过自动切句）")
    ap.add_argument("--source", default="", help="画质比对的源图（默认取 --image）")
    # 开关
    ap.add_argument("--render", action="store_true", help="没有 --raw 时自己起渲染")
    ap.add_argument("--size", type=int, default=256, help="人脸生成尺寸 256/512")
    ap.add_argument("--enhancer", default="gfpgan", help="默认 gfpgan；空字符串=不增强（画质会掉到 0.54）")
    ap.add_argument("--no-sway", action="store_true")
    ap.add_argument("--no-publish", action="store_true")
    ap.add_argument("--allow-fail-publish", action="store_true",
                    help="不过达标线也发布（默认**不**发；要发必须显式）")
    ap.add_argument("--wait", type=int, default=9000, help="等原始件最多多少秒（外部渲染时）")
    ap.add_argument("--dry-run", action="store_true")
    # 上云元数据
    ap.add_argument("--id", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--framing", default="")
    ap.add_argument("--voice-label", default="")
    a = ap.parse_args()

    text = a.text
    if a.text_file:
        text = Path(a.text_file).read_text(encoding="utf-8").strip()
    voice_id = VOICES.get(a.voice, a.voice)
    # 🔴 2026-10-20 实测（P14 被前置条件挡住的代码）：带 --raw 复跑时没人给 --image/--source，
    #    结果 QC 命令里根本没有 --source ⇒ qc-video.py 直接 usage error，画质无从比对。
    #    兜底顺序：显式 --source → --image → 标准参考图（存在才算）。
    src = Path(a.source) if a.source else (Path(a.image) if a.image else None)
    if src is None:
        _ref = ROOT / "outputs" / "ref" / "character-ref.png"
        if _ref.is_file():
            src = _ref

    raw = Path(a.raw) if a.raw else (OUTDIR / ("%s-raw.mp4" % a.id))
    audio = Path(a.audio) if a.audio else (VEDIR / ("%s.wav" % a.id))
    srt = Path(a.srt) if a.srt else (VEDIR / ("%s.srt" % a.id))

    plan = {"id": a.id, "raw": str(raw), "audio": str(audio), "srt": str(srt),
            "voice": voice_id, "rate": a.rate, "size": a.size, "enhancer": a.enhancer,
            "sway": not a.no_sway, "publish": not a.no_publish, "gate": GATE}
    if a.dry_run:
        print("PLAN " + json.dumps(plan, ensure_ascii=False, indent=1))
        return 0
    print("PLAN " + json.dumps(plan, ensure_ascii=False), flush=True)

    ok_steps: list = []
    t_start = time.time()

    # ①② 配音 + 字幕
    if not a.audio:
        if not text:
            print("FAIL " + json.dumps({"why": "既没 --audio 也没 --text，没有配音就没片子"},
                                       ensure_ascii=False))
            return 2
        r = tts(text, voice_id, a.rate, audio)
        if not r.get("ok"):
            print("FAIL " + json.dumps({"step": "tts", "tail": r.get("tail")}, ensure_ascii=False))
            return 2
        ok_steps.append({"step": "tts", **{k: v for k, v in r.items() if k != "ok"}})
    if not Path(a.srt).is_file() and not a.srt:
        if not text:
            print("WARN " + json.dumps({"note": "没有文本，自动字幕跳过（要烧字幕请给 --srt）"},
                                       ensure_ascii=False))
            srt = None
        else:
            r = auto_srt(audio, text, srt)
            if not r.get("ok"):
                print("FAIL " + json.dumps({"step": "auto_srt", **r}, ensure_ascii=False))
                return 2
            ok_steps.append({"step": "auto_srt", **{k: v for k, v in r.items() if k != "ok"}})
    elif a.srt:
        srt = Path(a.srt)

    # ③ 渲染
    if not raw.is_file():
        if not (a.render and a.image):
            deadline = time.time() + a.wait
            while not raw.is_file() and time.time() < deadline:
                print("WAIT " + json.dumps({"raw": str(raw),
                                            "left_s": int(deadline - time.time())},
                                           ensure_ascii=False), flush=True)
                time.sleep(60)
            if not raw.is_file():
                print("FAIL " + json.dumps({"why": "等不到原始件", "raw": str(raw),
                                            "hint": "要自己起渲染就加 --render 与 --image"},
                                           ensure_ascii=False))
                return 3
        else:
            r = render(Path(a.image), audio, raw, a.size, a.enhancer)
            if not r.get("ok"):
                print("FAIL " + json.dumps({"step": "render", "tail": r.get("tail")},
                                           ensure_ascii=False))
                return 3
            ok_steps.append({"step": "render", "out": str(raw), "sha16": _sha16(raw),
                             "bytes": raw.stat().st_size})
    print("RAW " + json.dumps({"raw": str(raw), "bytes": raw.stat().st_size,
                               "sha16": _sha16(raw)}, ensure_ascii=False), flush=True)

    # ④ 微动
    cur = raw
    if not a.no_sway:
        sway = OUTDIR / ("%s-sway.mp4" % a.id)
        cmd = [str(VENV_PY), str(ROOT / "tools" / "digihuman" / "body-motion.py"),
               "--in", str(cur), "--out", str(sway), "--crf", "10",
               "--bend", "0.006", "--lean", "0.003", "--breath", "0.003", "--hz", "0.12"]
        if audio.is_file():
            cmd += ["--audio", str(audio)]
        r = run("body-motion", cmd, timeout=3600)
        if r["rc"] != 0 or not sway.is_file():
            print("FAIL " + json.dumps({"step": "body-motion", "tail": r["tail"]},
                                       ensure_ascii=False))
            return 4
        ok_steps.append({"step": "body-motion", "secs": r["secs"], "sha16": _sha16(sway)})
        cur = sway

    # ⑤ 交付（只编一次）
    out = OUTDIR / ("%s.mp4" % a.id)
    cmd = [str(VENV_PY), str(ROOT / "tools" / "digihuman" / "deliver.py"),
           "--raw", str(cur), "--out", str(out), "--no-qc"]
    if srt and Path(srt).is_file():
        cmd += ["--srt", str(srt)]
    r = run("deliver", cmd, timeout=3600)
    if r["rc"] != 0 or not out.is_file():
        print("FAIL " + json.dumps({"step": "deliver", "tail": r["tail"]}, ensure_ascii=False))
        return 5
    ok_steps.append({"step": "deliver", "secs": r["secs"], "bytes": out.stat().st_size,
                     "sha16": _sha16(out)})

    # ⑥ 三条口径
    qc = ROOT / "state" / "digital_human" / ("qc-%s.json" % a.id)
    cmd = [str(VENV_PY), str(ROOT / "tools" / "digihuman" / "qc-video.py"),
           "--video", str(out), "--audio", str(audio)]
    if src and Path(src).is_file():
        cmd += ["--source", str(src)]
    cmd += ["--track", "--max-width", "736", "--ref-width", "736", "--out", str(qc)]
    r = run("qc", cmd, timeout=7200)
    gate = None
    if qc.is_file():
        q = json.loads(qc.read_text(encoding="utf-8"))
        sx = (q.get("画质清晰") or {}).get("ratio")
        mv = (q.get("动作自然") or {}).get("head_move_mean")
        fl = (q.get("动作自然") or {}).get("flicker_ratio")
        mo = q.get("语音嘴对齐") or {}
        r_pk, lag, neg = mo.get("r_peak"), mo.get("lag_frames"), mo.get("neg_control_r")
        checks = {
            "画质": (sx is not None and sx >= GATE["ratio"], sx, GATE["ratio"]),
            "动作": (mv is not None and mv >= GATE["head_move"], mv, GATE["head_move"]),
            "尖峰": (fl is not None and fl <= GATE["flicker"], fl, GATE["flicker"]),
            "嘴r": (r_pk is not None and r_pk >= GATE["r"], r_pk, GATE["r"]),
            "lag": (lag is not None and abs(lag) <= GATE["lag"], lag, GATE["lag"]),
            "负控": (neg is None or neg <= GATE["neg"], neg, GATE["neg"]),
        }
        gate = {"ratio": sx, "head_move": mv, "flicker": fl, "r": r_pk, "lag": lag, "neg": neg,
                "pass": all(v[0] for v in checks.values()),
                "每条": {k: {"读数": v[1], "线": v[2], "过": bool(v[0])} for k, v in checks.items()}}
        print("QC " + json.dumps(gate, ensure_ascii=False), flush=True)
    else:
        print("WARN " + json.dumps({"qc": "回执没落盘，按未通过处理", "tail": r["tail"]},
                                   ensure_ascii=False), flush=True)

    # ⑦ 上云（失败件默认不发）
    published = None
    if not a.no_publish:
        passed = bool(gate and gate.get("pass"))
        if not passed and not a.allow_fail_publish:
            print("HOLD " + json.dumps({"why": "三条口径未全绿 ⇒ 不上云（要发请显式 --allow-fail-publish）",
                                        "gate": gate}, ensure_ascii=False), flush=True)
        else:
            cmd = [sys.executable, str(ROOT / "tools" / "digihuman" / "motion-publish.py"), "add",
                   str(out), "--id", a.id, "--title", a.title or a.id,
                   "--framing", a.framing, "--voice", a.voice_label or voice_id]
            if qc.is_file():
                cmd += ["--qc", str(qc)]
            r = run("publish", cmd, timeout=1800)
            if r["rc"] != 0:
                print("FAIL " + json.dumps({"step": "publish", "tail": r["tail"]},
                                           ensure_ascii=False))
                return 6
            published = "https://pub-3b817fc945aa4e1c8d7cce0ea93fa725.r2.dev/index.html"
            ok_steps.append({"step": "publish", "secs": r["secs"]})

    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "id": a.id, "total_secs":
           round(time.time() - t_start, 1), "out": str(out), "out_sha16": _sha16(out),
           "gate": gate, "passed": bool(gate and gate.get("pass")),
           "published": published, "steps": ok_steps, "plan": plan}
    LOOP_LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LOOP_LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print("DONE " + json.dumps({"out": str(out), "qc": str(qc) if qc.is_file() else None,
                                "gate": gate, "published": published,
                                "ledger": str(LOOP_LEDGER), "total_secs": rec["total_secs"]},
                               ensure_ascii=False))
    # 🔴 2026-10-20 实测：原来 `or a.no_publish` 让"没判决"也 rc=0 —— 无人值守会把失败当成功（fail-open）。
    #    现在：gate 为 None（QC 没给判决）⇒ rc=3；有判决但没过 ⇒ rc=7；只有真过才是 0。
    if gate is None:
        print("FAIL " + json.dumps({"why": "QC 没有给出判决（gate=null）—— 按失败退出，不许当成功",
                                    "qc": str(qc) if qc.is_file() else None}, ensure_ascii=False), flush=True)
        return 3
    return 0 if gate.get("pass") else 7


if __name__ == "__main__":
    sys.exit(main())
