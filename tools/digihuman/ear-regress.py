# -*- coding: utf-8 -*-
"""ear-regress.py —— 耳朵的回归尺：正例命中率 / 负例误收率（先量再改门槛）

## 为什么必须先量
上一轮实测同一句「走过来」的置信度在 0.479~0.659 之间抖。要决定「门槛放不放、要不要双次确认」，
不能凭感觉 —— 必须同时看两个数：**正例命中率**（越高越好）与**负例误收率**（必须为 0）。
只放门槛不看负例，就会出现"说什么她都动"。

## 做法
1. 用 edge-tts 合成**正例**（命令词）与**负例**（日常话，绝不该触发动作）；
2. 逐条喂 `ear-listen.ps1`（不经过麦克风，纯文件，可复现）；
3. 统计：
   - 正例命中率 = 命中动作数 / 正例数
   - 负例误收率 = 被采纳的负例数 / 负例数（**必须 0**）
   - 每条 conf 明细（用来判断抖动幅度）
4. 支持 `--min-conf` 与 `--confirm N`（双次确认模拟：同一句合成 N 遍，N 次都命中同动作才算过）。

## 用法
  py -3.14 tools/digihuman/ear-regress.py --min-conf 0.55
  py -3.14 tools/digihuman/ear-regress.py --min-conf 0.50 --confirm 2
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PS1 = ROOT / "tools" / "digihuman" / "ear-listen.ps1"
VENV = ROOT / ".venv-sadtalker" / "Scripts" / "python.exe"

# 2026-10-20 扩：把后来接上的动作也纳入正例（口令词必须与 ear-listen.ps1 的语法表逐字一致）。
# 扩之前只有 5 条，坐下/跳舞/比心这些"身体能做了"的动作从来没进过回归。
POS = [("走过来", "come"), ("挥挥手", "wave"), ("坐下", "sit"),
       ("站起来", "stand"), ("转一圈", "spin"), ("跳一下", "jump"),
       ("跳舞", "dance"), ("比心", "heart"), ("鼓掌", "clap"), ("抱抱", "hug")]
NEG = ["今天天气不错", "我们去吃饭吧", "这个文件在哪里", "他昨天回家了", "会议改到明天下午"]

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                                   # noqa: BLE001
        pass


def synth(text: str, tag: str, out: Path, voice: str = "zh-CN-XiaoxiaoNeural") -> Path | None:
    mp3 = out / (tag + ".mp3")
    wav = out / (tag + ".wav")
    r = subprocess.run([str(VENV), "-m", "edge_tts", "--voice", voice, "--text", text,
                        "--write-media", str(mp3)], capture_output=True)
    if r.returncode != 0 or not mp3.is_file():
        return None
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mp3), "-ac", "1",
                        "-ar", "16000", str(wav)], capture_output=True)
    return wav if r.returncode == 0 and wav.is_file() else None


def hear(wav: Path, min_conf: float) -> dict:
    r = subprocess.run(["pwsh", "-NoProfile", "-File", str(PS1), "-Wave", str(wav),
                        "-MinConf", str(min_conf), "-Json"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=90)
    raw = (r.stdout or "") + (r.stderr or "")
    i, j = raw.find("{"), raw.rfind("}")
    if i < 0 or j <= i:
        return {"ok": False, "why": "识别器没回 JSON", "tail": raw.strip().splitlines()[-3:]}
    try:
        return json.loads(raw[i:j + 1])
    except ValueError:
        return {"ok": False, "why": "回执解析失败"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-conf", type=float, default=0.55)
    ap.add_argument("--attempts", type=int, default=1, help="每条试几次（模拟客户端重听）")
    ap.add_argument("--require", choices=["any", "all"], default="any",
                    help="any=任一次成功即算过（客户端行为）· all=每次都成功才算过（双次确认）")
    ap.add_argument("--confirm", type=int, default=0, help="(旧参) 等价于 --attempts N --require all")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.confirm:
        a.attempts, a.require = max(2, a.confirm), "all"
    attempts = max(1, a.attempts)

    if not PS1.is_file() or not VENV.is_file():
        print(json.dumps({"ok": False, "why": "识别器或 venv 不在"}, ensure_ascii=False))
        return 2

    tmp = Path(tempfile.mkdtemp(prefix="gbt-earreg-"))
    pos_rows, neg_rows = [], []

    for idx, (text, want) in enumerate(POS):
        hits, confs = 0, []
        for k in range(attempts):
            wav = synth(text, "p%d_%d" % (idx, k), tmp)
            if wav is None:
                break
            j = hear(wav, a.min_conf)
            confs.append(j.get("conf"))
            if j.get("accepted") and j.get("action") == want:
                hits += 1
        need = attempts if a.require == "all" else 1
        ok = hits >= need
        pos_rows.append({"text": text, "want": want, "hits": hits,
                         "need": need, "require": a.require, "ok": ok,
                         "conf": [None if c is None else round(float(c), 3) for c in confs]})

    for idx, text in enumerate(NEG):
        accepted_any, acts, confs = False, [], []
        for k in range(attempts):
            wav = synth(text, "n%d_%d" % (idx, k), tmp)
            if wav is None:
                continue
            j = hear(wav, a.min_conf)
            confs.append(j.get("conf"))
            if j.get("accepted"):
                accepted_any = True
                acts.append(j.get("action"))
        neg_rows.append({"text": text, "accepted": accepted_any,
                         "action": acts or None, "conf": confs,
                         "ok": not accepted_any})

    pos_ok = sum(1 for r in pos_rows if r["ok"])
    neg_bad = sum(1 for r in neg_rows if r.get("accepted"))
    rep = {"ok": neg_bad == 0 and pos_ok == len(pos_rows),
           "min_conf": a.min_conf, "attempts": attempts, "require": a.require,
           "正例命中率": "%d/%d" % (pos_ok, len(pos_rows)),
           "负例误收率": "%d/%d" % (neg_bad, len(neg_rows)),
           "判据": "负例必须 0 误收；正例命中越多越好（不是唯一目标）",
           "pos": pos_rows, "neg": neg_rows}
    print(json.dumps(rep if a.json else
                     {k: v for k, v in rep.items() if k not in ("pos", "neg")},
                     ensure_ascii=False, indent=1))
    if not a.json:
        print("正例明细：")
        for r in pos_rows:
            print("  %s → %s  命中 %d/%d  conf=%s %s" % (
                r["text"], r["want"], r["hits"], r["need"], r["conf"], "✅" if r["ok"] else "🔴"))
        print("负例明细：")
        for r in neg_rows:
            print("  %s  accepted=%s conf=%s %s" % (
                r["text"], r.get("accepted"), r.get("conf"), "✅" if r["ok"] else "🔴误收"))
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
