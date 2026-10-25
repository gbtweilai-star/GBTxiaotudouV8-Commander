#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OpenPose+LoRA **批量**驱动（多姿势 × 多提示词）· 建在**已验的那套**之上

## 它与 `comfy-pose-lora.py` 的关系
单个客户端（`comfy-pose-lora.py`）已经验过（一单真跑 1366.3 s）。本件**不重写**任何东西：
用 `importlib` 把它的 `build()` / `Spec` / `get_json` / `post_json` 直接**复用**，
只加"**批量 + 可续跑 + 先算账**"这一层。⇒ 图怎么建、入参怎么按 `/object_info` 过滤，只有一处真相。

## 三条纪律（写死）
1. 🔴 **先算账再跑**：本机是 CPU 出图（实测 8 步 ≈ 1366–1546 s/张）。
   开跑**前**把"张数 × 单张实测秒"摊出来；超过 `--max-minutes` 就**拒跑并说明**，
   不许嘴上说"无限生产"、手上把机器占死。
2. 🔴 **可续跑**：每张落一行 `state/pose-batch/<批次>.jsonl`（含 pose/prompt/seed/参数/产物 sha256）。
   重跑同批次时**跳过已完成的组合**（同 pose+同 prompt+同参数）。
3. 🔴 **不许谎报**：产物是否合格要另判 —— `_口径` 里写死「出图 ≠ 姿势对 ≠ 审美合格」；
   姿势咬合要另用骨架叠图比对（`openpose-extract.py joints/compare`），审美另走 `gbt-aesthetic`。

用法：
```
python tools/codex-scripts/pose-batch.py --dry-run                      # 只算账（不用起服务）
python tools/codex-scripts/pose-batch.py --poses stand,walk --prompts prompts.txt \
       --limit 4 --max-minutes 120
python tools/codex-scripts/pose-batch.py --poses stand --prompt "a photo of ..." --size 256x256 --steps 1
```
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
STATE = ROOT / "state" / "pose-batch"
OUTDIR = ROOT / "render" / "pose-batch"
INPDIR = Path.home() / "ComfyUI" / "input"


def load_client():
    """复用已验客户端（不改它一行）。文件名带连字符 ⇒ 只能走 importlib。"""
    spec = importlib.util.spec_from_file_location("cpl", HERE / "comfy-pose-lora.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ensure_pose(cpl, preset_or_file: str):
    """给预设名 ⇒ 骨架不在 input/ 就先按预设生成（与单发同一条路）。"""
    p = Path(preset_or_file)
    if p.suffix.lower() == ".png":
        return p.name
    dst = INPDIR / (preset_or_file + ".png")
    if not dst.exists():
        gen = HERE / "openpose-skeleton.py"
        cp = subprocess.run([sys.executable, str(gen), "--pose", preset_or_file, "--out", str(dst)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
        if cp.returncode != 0:
            raise SystemExit(json.dumps({"ok": False, "status": "pose_gen_failed",
                                         "preset": preset_or_file, "stderr": (cp.stderr or "")[:300]},
                                        ensure_ascii=False))
    return dst.name


def job_key(pose, prompt, args):
    raw = "|".join([pose, prompt, args.size, str(args.steps), str(args.cfg), args.sampler,
                    args.scheduler, str(args.seed), str(args.cn_strength), str(args.cn_end),
                    str(args.lora_strength)])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def done_keys(manifest: Path):
    if not manifest.exists():
        return set()
    out = set()
    for ln in manifest.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(ln)
        except Exception:                                                  # noqa: BLE001
            continue
        if r.get("ok") and r.get("key"):
            out.add(r["key"])
    return out


def main():
    ap = argparse.ArgumentParser(description="OpenPose+LoRA 批量驱动（先算账 · 可续跑 · 不谎报）")
    ap.add_argument("--base", default="")
    ap.add_argument("--poses", default="", help="预设名或骨架文件名，逗号分隔（stand/walk/sit/tpose）")
    ap.add_argument("--prompts", default="", help="提示词文件（每行一条，# 开头跳过）")
    ap.add_argument("--prompt", default="", help="单条提示词")
    ap.add_argument("--limit", type=int, default=0, help="最多跑几个组合（0=不限）")
    ap.add_argument("--max-minutes", type=float, default=90.0, help="预算上限（超过就拒跑）")
    ap.add_argument("--per-image-s", type=float, default=0.0,
                    help="单张预估秒（0=用 8 步实测 1450 s 按步数折算）")
    ap.add_argument("--size", default="512x512")
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--cfg", type=float, default=2.0)
    ap.add_argument("--sampler", default="lcm")
    ap.add_argument("--scheduler", default="sgm_uniform")
    ap.add_argument("--seed", type=int, default=20260923)
    ap.add_argument("--lora", default="")
    ap.add_argument("--lora-strength", type=float, default=1.0)
    ap.add_argument("--cn-strength", type=float, default=1.0)
    ap.add_argument("--cn-end", type=float, default=0.9)
    ap.add_argument("--timeout", type=float, default=2400.0, help="单张最长等多少秒")
    ap.add_argument("--batch", default="", help="批次名（默认按时间）")
    ap.add_argument("--dry-run", action="store_true", help="只算账 + 打印计划，不提交")
    ap.add_argument("--no-resume", action="store_true", help="不跳过已完成的组合")
    a = ap.parse_args()

    cpl = load_client()
    base = a.base or cpl.BASE_DEFAULT

    poses = [x.strip() for x in a.poses.split(",") if x.strip()]
    if not poses:
        print(json.dumps({"ok": False, "status": "no_poses",
                          "hint": "--poses stand,walk,sit 或 gbt-pose-xxx.png"}, ensure_ascii=False))
        return 2
    prompts = []
    if a.prompts:
        prompts = [ln.strip() for ln in Path(a.prompts).read_text(encoding="utf-8").splitlines()
                   if ln.strip() and not ln.strip().startswith("#")]
    elif a.prompt:
        prompts = [a.prompt]
    if not prompts:
        print(json.dumps({"ok": False, "status": "no_prompts",
                          "hint": "--prompt 一条 或 --prompts 文件"}, ensure_ascii=False))
        return 2

    batch = a.batch or time.strftime("batch-%Y%m%d-%H%M%S")
    STATE.mkdir(parents=True, exist_ok=True)
    manifest = STATE / (batch + ".jsonl")
    done = set() if a.no_resume else done_keys(manifest)

    # ── 先算账：把"张数 × 单张秒"摊开；超预算就拒跑（不许嘴上说"无限"）────────
    per = a.per_image_s or (1450.0 / 8.0 * a.steps)
    jobs = []
    for pz in poses:
        for pr in prompts:
            jobs.append((pz, pr))
    skipped = 0
    if done:
        kept = []
        for pz, pr in jobs:
            k = job_key(pz, pr, a)
            if k in done:
                skipped += 1
            else:
                kept.append((pz, pr))
        jobs = kept
    if a.limit:
        jobs = jobs[:a.limit]
    est_min = len(jobs) * per / 60.0
    plan = {"批次": batch, "账本": str(manifest), "组合数": len(jobs),
            "已完成跳过": skipped, "单张预估s": round(per, 1),
            "预估总时长min": round(est_min, 1), "预算上限min": a.max_minutes,
            "姿势": poses, "提示词条数": len(prompts),
            "尺寸": a.size, "步数": a.steps, "采样器": a.sampler, "调度器": a.scheduler,
            "_口径": ("本机是 **CPU 出图**：单张秒是按 8 步实测 1366–1546 s 折算的**预估**，"
                    "不是承诺；'无限生产'在本机不成立，本件只做'按预算排队跑'。"
                    "出图 ≠ 姿势对 ≠ 审美合格。")}
    if a.dry_run:
        plan["ok"] = True
        plan["status"] = "dry_run"
        plan["逐条"] = [{"pose": p, "prompt": q[:60]} for p, q in jobs[:20]]
        print(json.dumps(plan, ensure_ascii=False, indent=1))
        return 0
    if est_min > a.max_minutes:
        plan["ok"] = False
        plan["status"] = "over_budget"
        plan["_结论"] = ("预估 %.1f 分钟 > 预算 %.1f 分钟 ⇒ **拒跑**。"
                       "要么加 --max-minutes，要么减 --limit，要么等有 GPU／用云腿。" % (est_min, a.max_minutes))
        print(json.dumps(plan, ensure_ascii=False, indent=1))
        return 3

    # ── 起跑前的最低前提：服务在不在、件齐不齐（缺了就**报清楚**，不静默失败）──
    spec = cpl.Spec(base)
    try:
        ckpts = spec.choices("CheckpointLoaderSimple", "ckpt_name")
        cns = spec.choices("ControlNetLoader", "control_net_name")
        loras = spec.choices("LoraLoader", "lora_name")
        imgs = spec.choices("LoadImage", "image")
    except Exception as e:                                                 # noqa: BLE001
        print(json.dumps({"ok": False, "status": "server_unreachable", "base": base,
                          "why": str(e)[:200],
                          "hint": "先起服务：pwsh -File tools/codex-scripts/comfy-serve.ps1（**挂后台**）"},
                         ensure_ascii=False, indent=1))
        return 4
    ckpt = ([n for n in ckpts if "realistic" in n.lower()] or ckpts or [""])[0]
    cn = (cns or [""])[0]
    lora = a.lora or (loras[0] if loras else "")
    if not ckpt or not cn:
        print(json.dumps({"ok": False, "status": "assets_missing", "ckpt": ckpt, "controlnet": cn},
                         ensure_ascii=False, indent=1))
        return 4

    OUTDIR.mkdir(parents=True, exist_ok=True)
    results, t_all = [], time.time()
    for idx, (pz, pr) in enumerate(jobs, 1):
        key = job_key(pz, pr, a)
        try:
            pose_file = ensure_pose(cpl, pz)
        except SystemExit as e:
            print(str(e))
            continue
        if pose_file not in imgs:
            # 🔴 第 87 轮实测抓到的自己的 bug：`imgs` 是**循环之前**取的，
            #    而 `ensure_pose()` 可能**刚刚**把骨架生成进 input/ ⇒ 名单是陈旧的，
            #    于是新生成的骨架被判成"不在服务端"（假红）。⇒ 清掉那个节点的缓存再问一遍。
            spec.cache.pop("LoadImage", None)
            imgs = spec.choices("LoadImage", "image")
        if pose_file not in imgs:
            row = {"ok": False, "status": "pose_not_on_server", "pose": pose_file, "key": key,
                   "available": imgs[:8]}
            manifest.open("a", encoding="utf-8").write(json.dumps(row, ensure_ascii=False) + "\n")
            results.append(row)
            continue
        m = re.match(r"^(\d+)x(\d+)$", a.size.strip())
        w, h = (int(m.group(1)), int(m.group(2))) if m else (512, 512)
        notes = []
        wf = cpl.build(spec, ckpt, pose_file, pr, "", a.steps, w, h, a.seed, a.cfg,
                       a.sampler, a.scheduler, lora, a.lora_strength, cn, a.cn_strength,
                       0.0, a.cn_end, "gbt_pose_batch", notes)
        print("[%d/%d] pose=%s steps=%d seed=%d ⇒ 提交" % (idx, len(jobs), pose_file, a.steps, a.seed))
        t0 = time.time()
        try:
            res = cpl.post_json(base, "/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
            pid = res.get("prompt_id")
        except urllib.error.HTTPError as e:
            row = {"ok": False, "status": "rejected", "key": key, "pose": pose_file,
                   "http": e.code, "body": e.read(900).decode("utf-8", "replace")}
            print("   ❗ 被服务拒了：%s" % row["body"][:200])
            manifest.open("a", encoding="utf-8").write(json.dumps(row, ensure_ascii=False) + "\n")
            results.append(row)
            continue
        hist, waited, gap = None, 0.0, 2.0
        while waited < a.timeout:
            time.sleep(gap)
            waited += gap
            gap = min(gap * 1.15, 8.0)
            try:
                hh = cpl.get_json(base, "/history/" + urllib.parse.quote(pid), timeout=20)
            except Exception:                                              # noqa: BLE001
                continue
            if pid in hh and hh[pid]:
                hist = hh[pid]
                break
            if int(waited) % 60 < 8:
                print("      …等了 %.0fs" % waited)
        if hist is None:
            row = {"ok": False, "status": "timeout", "key": key, "pose": pose_file,
                   "waited_s": round(waited, 1)}
            manifest.open("a", encoding="utf-8").write(json.dumps(row, ensure_ascii=False) + "\n")
            results.append(row)
            continue
        st = hist.get("status") or {}
        if st.get("status_str") == "error" or st.get("completed") is False:
            row = {"ok": False, "status": "node_error", "key": key, "pose": pose_file,
                   "detail": str(st)[:600]}
            manifest.open("a", encoding="utf-8").write(json.dumps(row, ensure_ascii=False) + "\n")
            results.append(row)
            continue
        saved = []
        for _nid, out in (hist.get("outputs") or {}).items():
            for im in (out.get("images") or []):
                q = urllib.parse.urlencode({"filename": im.get("filename", ""),
                                            "subfolder": im.get("subfolder", ""),
                                            "type": im.get("type", "output")})
                with urllib.request.urlopen(base + "/view?" + q, timeout=180) as r:
                    blob = r.read()
                d = OUTDIR / ("%d-%s-%s%s" % (int(t0), re.sub(r"[^\w\-]+", "_", pz)[:16],
                                              key, Path(im.get("filename", ".png")).suffix or ".png"))
                d.write_bytes(blob)
                saved.append({"file": str(d.relative_to(ROOT)), "bytes": len(blob),
                              "sha256_head": hashlib.sha256(blob).hexdigest()[:16]})
        row = {"ok": True, "status": "done", "key": key, "pose": pose_file, "prompt": pr,
               "seed": a.seed, "size": [w, h], "steps": a.steps, "elapsed_s": round(time.time() - t0, 1),
               "images": saved}
        manifest.open("a", encoding="utf-8").write(json.dumps(row, ensure_ascii=False) + "\n")
        results.append(row)
        print("   ✅ %s（%.1fs）⇒ %s" % (saved[0]["sha256_head"] if saved else "无产物",
                                      row["elapsed_s"], saved[0]["file"] if saved else "-"))

    ok_n = sum(1 for r in results if r.get("ok"))
    print(json.dumps({"ok": ok_n == len(results) and bool(results), "status": "batch_done",
                      "批次": batch, "跑了几张": len(results), "成功": ok_n,
                      "失败": [r.get("status") for r in results if not r.get("ok")],
                      "总耗时s": round(time.time() - t_all, 1),
                      "账本": str(manifest), "产物目录": str(OUTDIR),
                      "_口径": "出图 ≠ 姿势对 ≠ 审美合格；姿势咬合另用 openpose-extract.py compare/joints 判。"},
                     ensure_ascii=False, indent=1))
    return 0 if ok_n == len(results) and results else 1


if __name__ == "__main__":
    raise SystemExit(main())
