# -*- coding: utf-8 -*-
"""离线语音输入那条腿 · 把本机识别器（Windows System.Speech）接起来。

主人令（2026-10-08）：「数字人必须慢慢了解用户懂用户，数字人语音交互就可以操控整台电脑…」
本轮任务：**试着把离线识别器接起来**，做成能跑的一条命令，并**真跑一次**贴原文。

## 本机现读（两侧一致的硬读数）
  · 识别器**在位**：`zh-CN|MS-2052-80-DESK`（win-speech 桌面识别器 8.0，Windows 自带）
  · **活动录音端点 = 0**（在册 5：禁用 1 / 不存在 3 / 未插 1）· `waveInGetNumDevs() = 0`
  · SAPI 识别未接（无 funasr/sherpa；Whisper 未装）
⇒ 所以本件的职责就是**如实分开报三件事**：
    ① 识别器这条腿（在位 ⇒ 能加载、能吃 WAV 真识别）；
    ② 输入这条腿（设备直连**在本机是死的** ⇒ 原文照贴，不许说成"安静"）；
    ③ 两者都对上之后，"能听写"的**确切边界**（能听 WAV / 不能听麦，因为没有麦端点）。

## 为什么复用 `asr-listen.ps1` 而不另写一份识别实现
那是**仓内唯一**的离线识别实现（`voice_cap.asr_local` 的腿②就是它），有输出契约
`{ok, heard, text, confidence, culture, seconds, reason}` + 退出码分级（0/3/4/5/6）。
再写一份 = 第二套口径，早晚漂移。本件只做**调度 + 取证 + 判据**，识别本体仍走它。

## 用法（全部只读或"开了也必然报原文"，不写任何框架数据）
    py -3.14 tools/codex-scripts/asr-offline.py status
    py -3.14 tools/codex-scripts/asr-offline.py listen --wav <某.wav>     # 真识别一个真文件
    py -3.14 tools/codex-scripts/asr-offline.py listen --device --seconds 3
    py -3.14 tools/codex-scripts/asr-offline.py selfcheck --json          # 判据 + 负对照

## 🔴 纪律（写死）
  · **绝不伪造**：听不到写 heard=false + 原文；拿不到麦写 no_input + 原文（不许用假音频充数）。
  · **不启用被禁用的录音设备**：那是改系统设置 ⇒ **只有主人能做**（设置→系统→声音→录制→
    显示禁用的设备）。本件只探测，不代劳、不放宽。
  · 不落任何"识别结果"到框架 store；证据只在 stdout 与 `--json` 里给。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import ctypes
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
PS1 = ROOT / "tools" / "codex-scripts" / "asr-listen.ps1"

# 复用的两条"真文件"（仓内既有、非本轮生成；负对照用）
REAL_WAVS = [
    ROOT / "gbt_allinone" / "store" / "vision" / "tts_test.wav",
]
NEG_NOT_AUDIO = PS1            # 负对照①：把脚本自己当"WAV"喂进去，必须报打不开
NEG_MISSING = ROOT / "state" / "_no_such_file_negative_control.wav"   # 负对照②：不存在的文件

_OUT = {"at": time.strftime("%Y-%m-%dT%H:%M:%S")}


def _ps_exe() -> str:
    """asr-listen.ps1 里有 PowerShell 7 的 `if` 表达式语法（5.1 直接解析失败，实测踩过）
    ⇒ 优先 pwsh；只有 5.1 时如实标注为已知限制。"""
    return shutil.which("pwsh") or shutil.which("powershell") or ""


def wavein_count() -> int:
    """旧版 waveIn 映射器可见的输入设备数（只数，不开）。"""
    try:
        return int(ctypes.windll.winmm.waveInGetNumDevs())
    except Exception:                                   # noqa: BLE001
        return -1


def recognizers() -> dict:
    """枚举本机离线识别器（**只枚举，不开任何设备**）。"""
    ps = _ps_exe()
    if not ps:
        return {"ok": False, "error": "本机没有 pwsh / powershell"}
    code = ("Add-Type -AssemblyName System.Speech; "
            "[System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() | "
            "ForEach-Object { $_.Id + ' | ' + $_.Culture.Name }")
    try:
        p = subprocess.run([ps, "-NoProfile", "-Command", code],
                           capture_output=True, encoding="utf-8", errors="replace", timeout=60)
    except Exception as e:                              # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
    rows = [ln.strip() for ln in (p.stdout or "").splitlines() if ln.strip()]
    zh = [r for r in rows if "zh" in r.lower()]
    return {"ok": bool(rows), "ps": ps, "all": rows, "zh": zh,
            "exit": p.returncode, "stderr": (p.stderr or "").strip()[:200]}


def run_listen(args: list, timeout: float) -> dict:
    """跑一次 asr-listen.ps1，**原文进证据**（命令、退出码、stdout 原样）。"""
    ps = _ps_exe()
    if not ps:
        return {"ok": False, "status": "no_shell",
                "reason": "本机没有 pwsh / powershell，asr-listen.ps1 拉不起来"}
    if not PS1.is_file():
        return {"ok": False, "status": "missing_script",
                "reason": "tools/codex-scripts/asr-listen.ps1 不在盘上"}
    cmd = [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PS1)] + args
    _OUT["last_cmd"] = " ".join(['"%s"' % c if " " in c else c for c in cmd])
    try:
        p = subprocess.run(cmd, capture_output=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "status": "timeout", "reason": "识别超时（%ss）" % timeout}
    except Exception as e:                              # noqa: BLE001
        return {"ok": False, "status": "error", "reason": "%s: %s" % (type(e).__name__, e)}
    raw = (p.stdout or "").strip()
    last = ""
    for ln in reversed(raw.splitlines()):
        if ln.strip().startswith("{"):
            last = ln.strip()
            break
    try:
        out = json.loads(last) if last else {}
    except Exception:                                   # noqa: BLE001
        out = {}
    out.setdefault("ok", False)
    if not out.get("ok") and not out.get("reason"):
        out["reason"] = "没拿到识别器 JSON（exit=%s）：%s" % (
            p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()[:300] or "(无输出)")
    out["_exit"] = p.returncode
    out["_raw"] = raw[:600]
    return out


# ───────────────────────────── ops ─────────────────────────────

def op_status() -> dict:
    rec = recognizers()
    w = wavein_count()
    return {
        "ok": bool(rec.get("ok")),
        "op": "status",
        "at": _OUT["at"],
        "ps": rec.get("ps", ""),
        "ps_note": "asr-listen.ps1 需要 PowerShell 7（pwsh）；5.1 会解析失败（实测）",
        "recognizers": rec.get("all", []),
        "recognizers_zh": rec.get("zh", []),
        "recognizer_ready": bool(rec.get("zh")),
        "wavein_devices": w,
        "capture_ready": (isinstance(w, int) and w > 0),
        "device_leg": "死的（wavein_devices=0 ⇒ SetInputToDefaultAudioDevice 必抛原文）" if w == 0 else "可见设备",
        "wav_leg": "可用（真 WAV 喂进去真识别）" if rec.get("zh") else "缺 zh 识别器",
        "how_to_enable_mic": "只有主人能做：设置 → 系统 → 声音 → 录制 → 显示禁用的设备 → 启用；"
                             "我（AI）不代劳、不改系统设置",
        "honesty": "识别器在位 ≠ 能听麦：本机活动录音端点 0 ⇒ 能听写 WAV，不能听写麦克风",
    }


def op_listen(wav: str, device: bool, seconds: float, culture: str) -> dict:
    if wav:
        out = run_listen(["-WavFile", wav, "-Culture", culture], timeout=max(120.0, seconds + 90))
        out["leg"] = "wav"
        out["wav"] = wav
        return out
    if device:
        out = run_listen(["-Seconds", str(seconds), "-Culture", culture],
                         timeout=max(120.0, seconds + 90))
        out["leg"] = "device"
        return out
    return {"ok": False, "status": "no_input_specified",
            "reason": "要 --wav <文件> 或 --device 二选一（两条输入腿，别混）"}


# ─────────────────────── 判据 + 负对照（selfcheck） ───────────────────────
#
# 口径（两条，分开说）：
#   判据 = "这条必须成立"；不成立 ⇒ 报红。
#   负对照 = **把数据变异坏**，同一条判据函数**必须报红**（证明判据有牙，不是恒真）。
#   ⇒ 每条判据都跑两遍：真读数一遍（应成立）· 变异体一遍（应报红）。两次都对才算 pass。

def _probe_case(case: dict) -> dict:
    return op_listen(wav=case.get("wav", ""), device=bool(case.get("device")),
                     seconds=case.get("seconds", 3), culture="zh-CN")


# 每条判据 = 一个纯函数：返回 True 表示"这条成立"；False 表示"该报红"。
RULES = [
    ("C1 识别器在位：zh-CN 至少一条",
     lambda d: bool(d.get("recognizers_zh")),
     lambda d: dict(d, recognizers_zh=[])),
    ("C2 输入腿读数如实：wavein_devices 为非负整数",
     lambda d: isinstance(d.get("wavein_devices"), int) and d["wavein_devices"] >= 0,
     lambda d: dict(d, wavein_devices=None)),
    ("C3 设备腿带原文：no_input 必带 reason；若出声则必有 text（不许静默）",
     lambda d: (d.get("status") == "no_input" and str(d.get("reason") or "").strip() != "")
               or (d.get("heard") and str(d.get("text") or "").strip() != ""),
     lambda d: dict(d, status="no_input", reason="")),
    ("C4 WAV 腿真跑：ok 且（有 text 或带 reason），不许空手 ok",
     lambda d: bool(d.get("ok")) and (str(d.get("text") or "").strip() != ""
                                      or str(d.get("reason") or "").strip() != ""),
     lambda d: dict(d, ok=True, heard=True, text="", reason="")),
    ("C5 不存在的 WAV 必须 no_input 且带原文",
     lambda d: d.get("status") == "no_input" and str(d.get("reason") or "").strip() != "",
     lambda d: dict(d, status="ok", heard=True)),
    ("C6 非音频文件（拿 .ps1 当 WAV）必须报打不开/识别不了",
     lambda d: d.get("status") in ("no_input", "error") and str(d.get("reason") or "").strip() != "",
     lambda d: dict(d, status="ok", heard=True, text="听到了")),
    ("C7 拿不到麦的口径写明：wavein=0 时必须说清'能听 WAV、不能听麦'",
     lambda d: (d.get("wavein_devices") != 0)
               or ("WAV" in str(d.get("honesty") or "") and "麦" in str(d.get("honesty") or "")),
     lambda d: dict(d, honesty="")),
]


def selfcheck() -> dict:
    rec = recognizers()
    w = wavein_count()
    status = op_status()

    # 真跑三条腿（这就是任务要的"真跑一次"）
    wav_case = _probe_case({"wav": str(REAL_WAVS[0])}) if REAL_WAVS[0].is_file() else \
        {"ok": False, "status": "fixture_missing",
         "reason": "仓内既有 WAV 不在：%s" % REAL_WAVS[0]}
    dev_case = _probe_case({"device": True, "seconds": 3})
    miss_case = _probe_case({"wav": str(NEG_MISSING)})
    notaudio_case = _probe_case({"wav": str(NEG_NOT_AUDIO)})

    cases = {  # 判据吃哪份读数
        "C1": status, "C2": status, "C3": dev_case, "C4": wav_case,
        "C5": miss_case, "C6": notaudio_case, "C7": status,
    }
    results = []
    for name, pred, mutate in RULES:
        key = name[:2]
        data = cases[key]
        holds = bool(pred(data))
        mutant_red = not bool(pred(mutate(dict(data))))     # 变异体必须被判红
        results.append({
            "name": name,
            "real_holds": holds, "mutant_red": mutant_red,
            "pass": holds and mutant_red,
            "detail": ("真读数=%s（应成立）· 变异体=%s（应报红）" %
                       ("成立" if holds else "**报红**", "报红(抓到)" if mutant_red else "**漏报!**")),
        })
    ok = all(x["pass"] for x in results)
    return {
        "ok": ok, "op": "selfcheck", "at": _OUT["at"],
        "status": status,
        "runs": {
            "wav_real": wav_case,
            "device": dev_case,
            "neg_missing": miss_case,
            "neg_not_audio": notaudio_case,
        },
        "criteria": results,
        "negative_controls": [{"name": x["name"], "mutant_became_red": x["mutant_red"],
                               "pass": x["pass"]} for x in results],
        "honesty": [
            "识别器在位只证明'能加载 + 能吃 WAV'；麦克风那条腿的缺口（活动录音端点 0）如实另报",
            "未用任何假音频：喂进去的是仓内既有真 WAV（tts_test.wav，此前某次 TTS 测试产物，非主人语音）",
            "启用被禁用的录音设备 = 改系统设置 ⇒ 只有主人能做，本件不代劳",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="离线语音输入（Windows System.Speech）· 接起来 + 真跑 + 取证")
    ap.add_argument("op", nargs="?", default="status",
                    choices=["status", "listen", "selfcheck"])
    ap.add_argument("--wav", default="")
    ap.add_argument("--device", action="store_true")
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--culture", default="zh-CN")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.op == "status":
        out = op_status()
    elif args.op == "listen":
        out = op_listen(args.wav, args.device, args.seconds, args.culture)
    else:
        out = selfcheck()

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        if args.op == "listen":
            print("命令：%s" % _OUT.get("last_cmd", ""))
            print("原文：%s" % json.dumps(out, ensure_ascii=False))
        else:
            print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
