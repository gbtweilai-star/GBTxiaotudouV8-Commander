# -*- coding: utf-8 -*-
"""accept-all -- GBT小土豆V8 总验收门（主人令 2026-10-16：各项能力 + 执行任务 + 压力测试都要合格）

四组、逐项带判据，全绿才交付；任一项红 -> 非零退出，并落交付报告。
用法：py -3.14 tools/codex-scripts/accept-all.py [--model-answers PATH] [--comfy-answers PATH] [--stress]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
GATE = ROOT / "tools" / "codex-scripts" / "five-dim.py"
STATE = ROOT / "state" / "accept"


def sh(cmd, timeout=900):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, cwd=str(ROOT))
    return (p.returncode, (p.stdout or "") + (p.stderr or ""))


def cap(kind, payload, timeout=300):
    return sh([PY, "-X", "utf8", str(GATE), "cap", kind, payload, "--full"], timeout=timeout)


def cap_ok(out):
    """两层读：门 status==ok 且 denied 不为真，且本体 ok 不为 False。"""
    try:
        j = json.loads(out[out.find("{"):])
    except Exception:
        return False, "unparsed"
    st = j.get("status")
    denied = bool(j.get("denied"))
    body = j.get("result") if isinstance(j.get("result"), dict) else {}
    ok = (st == "ok") and not denied and (body.get("ok") is not False)
    return ok, "status=%s denied=%s body_ok=%s" % (st, denied, body.get("ok"))


def main():
    ap = argparse.ArgumentParser(description="GBT小土豆V8 总验收门")
    ap.add_argument("--model-answers", default="")
    ap.add_argument("--comfy-answers", default="")
    ap.add_argument("--min-model", type=int, default=50)
    ap.add_argument("--min-comfy", type=int, default=2)
    ap.add_argument("--stress", action="store_true")
    ap.add_argument("--min-thru", type=float, default=8.0)
    args = ap.parse_args()

    rows = []

    def add(group, item, reading, judge, ok):
        rows.append({"group": group, "item": item, "reading": reading, "judge": judge,
                     "state": "OK" if ok else "RED"})
        print("  %-6s %-22s | %-46s | %s" % (group, item, str(reading)[:46], "OK" if ok else "RED"))

    print("== 能力面 ==")
    rc, out = sh([PY, "-X", "utf8", "tools/codex-scripts/capability-audit.py"])
    m = re.search(r"总数 (\d+) · 接上 (\d+) · 断连 (\d+) · 缺失 (\d+)", out)
    if m:
        tot, up, brk, miss = map(int, m.groups())
        add("能力面", "面板台账", "总数%d 接上%d 断连%d 缺失%d" % (tot, up, brk, miss), "断连0 缺失0", brk == 0 and miss == 0)
    else:
        add("能力面", "面板台账", out.strip()[-40:], "能读出四数", False)
    rc, out = sh([PY, "-X", "utf8", "tools/codex-scripts/capability-bindings.py", "--check"])
    add("能力面", "双向绑定", out.strip()[-40:], "FAIL 0", "FAIL 0" in out)
    rc, out = sh([PY, "-X", "utf8", "tools/codex-scripts/tentacle-link-registry.py", "--check"])
    add("能力面", "连接登记", out.strip()[-40:], "FAIL 0", "FAIL 0" in out)
    rc, out = sh([PY, "-X", "utf8", "tools/codex-scripts/brand-lock-check.py"])
    add("品牌面", "四把锁-品牌", out.strip()[-40:], "PASS", "PASS" in out)

    print("== 执行面（真跑一条任务，两层读） ==")
    for kind, payload, item in (
            ("music_auto", '{"op":"plan","goal":"把这张专辑做成歌词视频"}', "音乐自动化规划"),
            ("shot_director", '{"op":"plan","idea":"宴会上她被当众问住"}', "镜头导演规划"),
            ("book_skill", '{"op":"contract"}', "书变技能合同"),
            ("comfy_native", '{"op": "validate", "workflow": {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "gbt.safetensors"}}, "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "a girl", "clip": ["1", 1]}}, "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "bad", "clip": ["1", 1]}}, "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}}, "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0], "seed": 1, "steps": 20, "cfg": 7, "sampler_name": "euler", "scheduler": "normal", "denoise": 1}}, "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}}, "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "gbt"}}}}', "秋叶版图校验（workflow·最小六件真图）"),
            ("comfy_forge", '{"op":"families"}', "秋叶版找件")):
        rc, out = cap(kind, payload)
        ok, why = cap_ok(out)
        add("执行面", item, why, "门ok且本体不False", ok)

    print("== 模型面 ==")
    if args.model_answers and Path(args.model_answers).is_file():
        rc, out = sh([PY, "-X", "utf8", "tests/test_v23_accept.py", "--answers", args.model_answers])
        m = re.search(r"合计 (\d+)/(\d+)", out)
        n = int(m.group(1)) if m else -1
        tot = int(m.group(2)) if m else 54
        add("模型面", "54题机检", "%d/%d" % (n, tot), ">=%d" % args.min_model, n >= args.min_model)
    else:
        add("模型面", "54题机检", "未提供答案", ">=%d" % args.min_model, False)
    if args.comfy_answers and Path(args.comfy_answers).is_file():
        rc, out = sh([PY, "-X", "utf8", "tools/train/accept_comfy.py", "--answers", args.comfy_answers])
        m = re.search(r"(\d+)/(\d+) ==", out)
        n = int(m.group(1)) if m else -1
        tot = int(m.group(2)) if m else 6
        add("模型面", "秋叶版能力", "%d/%d" % (n, tot), ">=%d" % args.min_comfy, n >= args.min_comfy)
    else:
        add("模型面", "秋叶版能力", "未提供答案", ">=%d" % args.min_comfy, False)

    if args.stress:
        print("== 压力面 ==")
        rc, out = sh([PY, "-X", "utf8", "tools/codex-scripts/tentacle-stress.py", "--n", "6",
                      "--levels", "1,4,8", "--argv-bytes", "1024,32000"], timeout=1800)
        line = ""
        for ln in out.splitlines():
            if "conc 8 " in ln:
                line = ln
        m = re.search(r"ok (\d+)/(\d+)", line)
        thr = re.search(r"thru ([\d.]+)", line)
        okn, tot = (int(m.group(1)), int(m.group(2))) if m else (-1, 6)
        thru = float(thr.group(1)) if thr else 0.0
        add("压力面", "并发8全过", "ok %d/%d" % (okn, tot), "全过", okn == tot and tot > 0)
        add("压力面", "吞吐", "%.2f/s" % thru, ">=%.1f/s" % args.min_thru, thru >= args.min_thru)

    red = [r for r in rows if r["state"] != "OK"]
    STATE.mkdir(parents=True, exist_ok=True)
    rep = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "rows": rows, "red": len(red),
           "verdict": "PASS" if not red else "FAIL"}
    (STATE / "latest.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print("== 总验收：%d 项 · 红 %d · 判定 %s ==" % (len(rows), len(red), rep["verdict"]))
    print("报告已落 state/accept/latest.json")
    return 1 if red else 0


if __name__ == "__main__":
    raise SystemExit(main())
