# -*- coding: utf-8 -*-
"""finish-clip.py — 一条片子渲完之后，把「微动 → 交付 → 验收 → 上云」一口气跑完。

## 为什么要有这一件
长片渲完往往是几小时后，人不在场；而收尾有四步、每步都可能踩坑（见 gbt-digital-human-video）。
这一件把这四步串成**一次无人值守的收尾**：等文件 → 微动 → 一次编码+字幕 → 三条口径 → 上云。

## 口径
- 等不等到就**如实退出**（不假装成功）；
- 任一步失败就停在那一步并把上游原话打出来（不带着坏件往下走）；
- 验收用 `--max-width 736`（MAR 是比值，缩放不变；全身 1472×2496 不缩会跑到一小时）。

用法：
  py -3.14 tools/digihuman/finish-clip.py --raw outputs/dh-talk/x-raw.mp4 \
     --audio outputs/voice-studio/short-video/tw-chen15.wav \
     --srt outputs/voice-studio/short-video/dialogue-tw.srt \
     --source outputs/ref/character-ref.png \
     --id x --title "全身・台灣腔" --framing full-body --voice "台灣腔（曉臻）" --wait 9000
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VENV_PY = ROOT / ".venv-sadtalker" / "Scripts" / "python.exe"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                                 # noqa: BLE001
        pass


def step(tag: str, cmd: list, timeout: int = 7200) -> dict:
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout)
    out = (r.stdout or "") + (r.stderr or "")
    rec = {"step": tag, "rc": r.returncode, "secs": round(time.time() - t0, 1),
           "tail": out.strip().splitlines()[-6:] if out.strip() else []}
    print("STEP " + json.dumps(rec, ensure_ascii=False), flush=True)
    return {**rec, "text": out}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--srt", default="")
    ap.add_argument("--source", required=True)
    ap.add_argument("--id", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--framing", default="")
    ap.add_argument("--voice", default="")
    ap.add_argument("--wait", type=int, default=9000, help="等原始件最多多少秒")
    ap.add_argument("--no-sway", action="store_true")
    ap.add_argument("--no-publish", action="store_true")
    a = ap.parse_args()

    raw = Path(a.raw)
    deadline = time.time() + a.wait
    while not raw.is_file() and time.time() < deadline:
        print("WAIT " + json.dumps({"raw": str(raw), "left_s": int(deadline - time.time())},
                                   ensure_ascii=False), flush=True)
        time.sleep(60)
    if not raw.is_file():
        print("FAIL " + json.dumps({"why": "等不到原始件", "raw": str(raw)}, ensure_ascii=False))
        return 2
    print("RAW " + json.dumps({"raw": str(raw), "bytes": raw.stat().st_size}, ensure_ascii=False))

    cur = raw
    if not a.no_sway:
        sway = ROOT / "outputs" / "dh-talk" / ("%s-sway.mp4" % a.id)
        # 用 body-motion（逐行 S 形重心转移），比整帧仿射更像"人自己挪重心"；
        # 有音频就让它跟着重音稍微加摆幅。
        cmd = [str(VENV_PY), str(ROOT / "tools" / "digihuman" / "body-motion.py"),
               "--in", str(cur), "--out", str(sway), "--crf", "10",
               "--bend", "0.006", "--lean", "0.003", "--breath", "0.003", "--hz", "0.12"]
        if a.audio:
            cmd += ["--audio", a.audio]
        r = step("body-motion", cmd, timeout=3600)
        if r["rc"] != 0 or not sway.is_file():
            print("FAIL " + json.dumps({"step": "body-motion", "tail": r["tail"]}, ensure_ascii=False))
            return 3
        cur = sway

    out = ROOT / "outputs" / "dh-talk" / ("%s.mp4" % a.id)
    cmd = [str(VENV_PY), str(ROOT / "tools" / "digihuman" / "deliver.py"),
           "--raw", str(cur), "--out", str(out), "--no-qc"]
    if a.srt:
        cmd += ["--srt", a.srt]
    r = step("deliver", cmd, timeout=3600)
    if r["rc"] != 0 or not out.is_file():
        print("FAIL " + json.dumps({"step": "deliver", "tail": r["tail"]}, ensure_ascii=False))
        return 4

    qc = ROOT / "state" / "digital_human" / ("qc-%s.json" % a.id)
    r = step("qc", [str(VENV_PY), str(ROOT / "tools" / "digihuman" / "qc-video.py"),
                    "--video", str(out), "--audio", a.audio, "--source", a.source,
                    "--track", "--max-width", "736", "--ref-width", "736",
                    "--out", str(qc)], timeout=7200)
    qc_ok = qc.is_file()
    gate = None
    if qc_ok:
        q = json.loads(qc.read_text(encoding="utf-8"))
        sx = (q.get("画质清晰") or {}).get("ratio")
        mv = (q.get("动作自然") or {}).get("head_move_mean")
        mo = q.get("语音嘴对齐") or {}
        gate = {"ratio": sx, "head_move": mv, "r": mo.get("r_peak"),
                "lag": mo.get("lag_frames"), "neg": mo.get("neg_control_r"),
                "pass": bool(sx and sx >= 0.90 and mv and mv >= 0.15 and mo.get("r_peak")
                             and mo["r_peak"] >= 0.55 and abs(mo.get("lag_frames") or 0) <= 2)}
        print("QC " + json.dumps(gate, ensure_ascii=False))

    if not a.no_publish:
        cmd = [sys.executable, str(ROOT / "tools" / "digihuman" / "motion-publish.py"), "add",
               str(out), "--id", a.id, "--title", a.title or a.id,
               "--framing", a.framing, "--voice", a.voice]
        if qc_ok:
            cmd += ["--qc", str(qc)]
        r = step("publish", cmd, timeout=1800)
        if r["rc"] != 0:
            print("FAIL " + json.dumps({"step": "publish", "tail": r["tail"]}, ensure_ascii=False))
            return 5

    print("DONE " + json.dumps({"out": str(out), "qc": str(qc) if qc_ok else None,
                                "gate": gate, "player": "https://pub-3b817fc945aa4e1c8d7cce0ea93fa725.r2.dev/index.html"},
                               ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
