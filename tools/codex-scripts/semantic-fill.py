import argparse, json, subprocess, sys, time
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
def sh(a, t=600):
    r = subprocess.run(a, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT), timeout=t)
    return r.returncode, (r.stdout or "") + (r.stderr or "")
def cap(name, payload, t=600):
    rc, o = sh([PY, "-X", "utf8", "tools/codex-scripts/five-dim.py", "cap", name, json.dumps(payload, ensure_ascii=False), "--full"], t)
    return ("\"status\": \"ok\"" in o and "\"denied\": true" not in o), o
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    v = Path(a.video)
    doc = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "video": str(v), "lanes": {}, "semantic": {}}
    # ① 技术层：ffprobe
    rc, o = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration,size,bit_rate", "-of", "json", str(v)], 120)
    doc["lanes"]["ffprobe"] = {"ok": rc == 0, "readout": o.strip()[:300]}
    # ② 语音层：ffmpeg 抽音频
    wav = ROOT / ".scratch" / ("sf_" + v.stem + ".wav")
    rc, o = sh(["ffmpeg", "-y", "-i", str(v), "-vn", "-ac", "1", "-ar", "16000", str(wav)], 300)
    doc["lanes"]["extract_audio"] = {"ok": rc == 0 and wav.is_file(), "file": str(wav.name)}
    # ③ 离线 ASR（零密钥，走 voice 位 listen）
    if doc["lanes"]["extract_audio"]["ok"]:
        ok, o = cap("voice", {"op": "listen", "wav": str(wav), "seconds": 60, "min_confidence": 0.0})
        doc["lanes"]["asr_listen"] = {"ok": ok, "readout": o[-400:]}
    else:
        doc["lanes"]["asr_listen"] = {"ok": False, "why": "音频未抽出"}
    # ④ 视觉车道现读
    ok_v, o_v = cap("vision", {"op": "probe"})
    doc["lanes"]["vision"] = {"ok": ok_v, "why": ("可用" if ok_v else "未读到（缺 privacy_read 钥匙）")}
    # 重点：语义层逐字段写清来源或缺什么
    doc["semantic"] = {
        "duration_sec": "取 ffprobe",
        "dialogue": "取车道② ASR（本机离线）" if doc["lanes"]["asr_listen"]["ok"] else "未读到（ASR 车道）",
        "audio_events": "取车道② ASR/音频分析",
        "subjects": "未读到（缺车道① vision 的 privacy_read 钥匙，或车道③ 外部端点/密钥）",
        "actions": "同 subjects 的缺口",
        "mood": "需 ASR 文本 + 视觉描述两路；目前只有前者",
    }
    out = Path(a.out) if a.out else (ROOT / ".scratch" / ("semantic_" + v.stem + ".json"))
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\u8bed\u4e49\u8865\u9f50\u7ba1\u7ebf\u5df2\u8dd1\uff1a" + str(out))
    for k in ("ffprobe", "extract_audio", "asr_listen", "vision"):
        d = doc["lanes"][k]
        print("  %-14s %s %s" % (k, "OK " if d.get("ok") else "RED", str(d.get("why") or d.get("readout") or "")[:90]))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
