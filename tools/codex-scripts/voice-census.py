# -*- coding: utf-8 -*-
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
"""语音面普查（只读）：把「配音 / 复刻 / 生成 / 识别」这条链上**真实存在**的东西量出来。

口径：每一项都要有现读来源（框架能力位 / 磁盘技能 / 可执行文件 / Python 包 / 钥匙）。
不写"应该支持"，只写"读到什么"。
"""
import importlib
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(_GBT_ROOT)
SKILLS = Path(r"C:\Users\ADMIN\.openclaw-autoclaw\skills")
sys.path.insert(0, str(ROOT))

print("=" * 78)
print("① 框架能力位：voice / voice_orchestra")
print("=" * 78)
try:
    import gbt_allinone as gbt

    def leaf(e):
        r = e.get("result") if isinstance(e, dict) else None
        if isinstance(r, dict) and isinstance(r.get("result"), dict):
            r = r["result"]
        return r if isinstance(r, dict) else e

    for kind in ("voice", "voice_orchestra"):
        try:
            r = leaf(gbt.run_task(kind, {"op": "status"}))
            s = json.dumps(r, ensure_ascii=False, default=str)
            print("  [%s] %s" % (kind, s[:600]))
        except Exception as exc:
            print("  [%s] 调用失败: %s: %s" % (kind, type(exc).__name__, exc))
except Exception as exc:
    print("  导入 gbt_allinone 失败:", exc)

print()
print("=" * 78)
print("② 磁盘上的语音相关技能（托管目录）")
print("=" * 78)
pat = ("voice", "tts", "speech", "audio", "asr", "whisper", "clone", "dub", "sovits",
       "rvc", "vits", "vocoder", "speak", "sound")
hits = []
if SKILLS.exists():
    for d in sorted(SKILLS.iterdir()):
        if not d.is_dir():
            continue
        n = d.name.lower()
        if any(p in n for p in pat):
            sk = d / "SKILL.md"
            desc = ""
            if sk.exists():
                for line in sk.read_text(encoding="utf-8", errors="replace").splitlines()[:8]:
                    if line.strip().startswith("description:"):
                        desc = line.split(":", 1)[1].strip()[:110]
                        break
            hits.append((d.name, desc))
for n, desc in hits:
    print("  %-34s %s" % (n, desc))
print("  合计 %d 条" % len(hits))

print()
print("=" * 78)
print("③ 本机可执行/可用的语音后端")
print("=" * 78)
for exe in ("ffmpeg", "ffprobe", "espeak", "espeak-ng", "say", "edge-tts", "whisper",
            "whisper-cli", "main", "sox", "piper", "ollama"):
    p = shutil.which(exe)
    print("  %-12s %s" % (exe, p or "—（不在 PATH）"))

print()
print("  --- Windows SAPI 声音（真出声那条路的底子）---")
try:
    import subprocess
    ps = ("Add-Type -AssemblyName System.Speech;"
          "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
          "$s.GetInstalledVoices()|ForEach-Object{$_.VoiceInfo.Name+'|'+$_.VoiceInfo.Culture}")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                         capture_output=True, text=True, timeout=40)
    vs = [ln.strip() for ln in (out.stdout or "").splitlines() if ln.strip()]
    for v in vs:
        print("     ", v)
    print("      SAPI 声音数:", len(vs))
except Exception as exc:
    print("      取不到:", type(exc).__name__, exc)

print()
print("=" * 78)
print("④ Python 语音相关包")
print("=" * 78)
for m in ("torch", "torchaudio", "TTS", "TTS.api", "coqui_tts", "pyttsx3", "edge_tts",
          "whisper", "faster_whisper", "openai_whisper", "vosk", "speech_recognition",
          "soundfile", "librosa", "sounddevice", "pydub", "transformers", "onnxruntime",
          "numpy", "scipy", "webrtcvad", "resemblyzer", "torch_directml"):
    try:
        mod = importlib.import_module(m)
        v = getattr(mod, "__version__", "?")
        print("  %-20s 已装  %s" % (m, v))
    except Exception:
        print("  %-20s —" % m)

print()
print("=" * 78)
print("⑤ 云侧语音通道的钥匙（只报是否已配 + 位数）")
print("=" * 78)
for k in ("VENICE_API_KEY", "FAL_KEY", "AGNES_API_KEY", "ELEVENLABS_API_KEY",
          "OPENAI_API_KEY", "AZURE_SPEECH_KEY", "DEEPGRAM_API_KEY", "MINIMAX_API_KEY",
          "FREELLMAPI_API_KEY", "GBT_POTATO_API_KEY"):
    v = os.environ.get(k) or os.environ.get(k.upper())
    print("  %-22s %s" % (k, ("已配（%d 位）" % len(v)) if v else "—"))

print()
print("=" * 78)
print("⑥ 本机有没有已下的语音模型权重（按目录名粗扫）")
print("=" * 78)
roots = [ROOT / "store", ROOT / "holo_pet" / "assets", Path(r"C:\Users\ADMIN\.cache"),
         Path(os.environ.get("LOCALAPPDATA", "")) / "huggingface"]
pat2 = ("whisper", "vits", "sovits", "rvc", "xtts", "tortoise", "bark", "piper",
        "vocoder", "speech", "tts", "wav2vec", "hubert")
found = 0
for r in roots:
    if not r.exists():
        continue
    for p in r.rglob("*"):
        if p.is_dir() and any(x in p.name.lower() for x in pat2):
            print("  ", p)
            found += 1
            if found > 25:
                break
    if found > 25:
        break
print("  命中目录 %d 个" % found)
