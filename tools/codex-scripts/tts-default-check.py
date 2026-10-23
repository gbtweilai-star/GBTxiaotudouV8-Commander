# -*- coding: utf-8 -*-
"""tts-default-check -- 默认语音判据（**运行层**，不只看代码声明）。"""
from __future__ import annotations
import json, re, subprocess, sys
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable


def static_lanes():
    out = []
    for rel in ("gbt_allinone/voice_cap.py", "gbt_allinone/tentacle/omni_audio.py",
                "gbt_allinone/tentacle/silero_vad.py", "gbt_allinone/tools/comfy_cloud.py"):
        p = ROOT / rel
        if not p.is_file():
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        speaks = bool(re.search(r"edge_tts|SpVoice|SpeechSynthesizer|voice_id|_edge_tts", t))
        tw = ("zh-TW-HsiaoChenNeural" in t) or ("zh-TW-HsiaoYuNeural" in t)
        beep_gated = ("allow_selftest" in t) or ("silero_vad" in rel)
        ok = (not speaks) or tw
        if "winsound.Beep" in t and not beep_gated:
            ok = False
        out.append((rel, ok, speaks, tw))
    return out


def runtime_lane():
    payload = json.dumps({"op": "tts", "text": "台灣腔女聲驗收"}, ensure_ascii=False)
    r = subprocess.run([PY, "-X", "utf8", "tools/codex-scripts/five-dim.py", "cap", "voice", payload, "--full"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT), timeout=300)
    o = (r.stdout or "") + (r.stderr or "")
    if '"denied": true' in o:
        return False, "被门拦（缺 audio_output）"
    try:
        d = json.loads(o[o.find("{"):])
        res = d.get("result") or {}
    except Exception:
        return False, "回执解析失败"
    backend = str(res.get("backend") or "")
    voice = str(res.get("voice") or res.get("engine") or "")
    if "edge" in backend.lower() or "zh-TW" in voice or "Hsiao" in voice:
        return True, "runtime backend=%s voice=%s" % (backend, voice)
    return False, "回落到 %s（音色 zh-CN，**不是台湾腔**）" % (backend or "?")


def main():
    red = 0
    for rel, ok, speaks, tw in static_lanes():
        print("  %-42s %s  说话=%s 台湾腔=%s" % (rel, "OK" if ok else "RED", speaks, tw))
        if not ok:
            red += 1
    ok_rt, note = runtime_lane()
    print("  %-42s %s  %s" % ("[运行层] 真发一次 tts", "OK" if ok_rt else "RED", note))
    if not ok_rt:
        red += 1
    print("== 语音默认（静态+运行）：红 %d ==" % red)
    return 0 if red == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
