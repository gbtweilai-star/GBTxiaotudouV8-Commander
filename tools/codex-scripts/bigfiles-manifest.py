#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""大件搬运清单（**搬之前先立账**：字节 + sha256 + 来源）

## 为什么先立账再搬
"搬过去了"这句话最容易糊：搬了一半、搬的时候被截断、搬的是旧版本 —— 三种都能看着像成功。
⇒ 所以先算 **每个文件的 sha256**，落一份 `state/bigfiles-manifest.json`；
搬完（或哪天搬回来）**再算一次**，对不上就是没搬成。**没有清单的搬运不算搬运。**

## 口径（三条）
1. **字节数是权威**（`os.path.getsize`），不靠"大概 4 GB"这种话；
2. **sha256 逐文件算**，流式读，不把 2 GB 文件读进内存（本机只有 7.4 GB 内存，这点很要紧）；
3. **分两类写清楚**：`可再下载`（模型/权重，公开源）与 `丢了就没`（自己产出的东西）——
   搬运的优先级完全不同，混在一起就会"花大力气搬回一堆能再下的东西"。

用法：
```
python tools/codex-scripts/bigfiles-manifest.py --scan          # 自动扫候选集
python tools/codex-scripts/bigfiles-manifest.py --paths a b c   # 指定文件
python tools/codex-scripts/bigfiles-manifest.py --verify state/bigfiles-manifest.json  # 搬后/搬回后核对
```
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "state" / "bigfiles-manifest.json"
HOME = Path(os.path.expanduser("~"))

# 候选集：值不值得搬 + 能不能再下载，都写在数据里（不写在注释里）
CANDIDATES = [
    ("可再下载", "模型", HOME / "ComfyUI/models/checkpoints/Realistic_Vision_V5.1_fp16-no-ema.safetensors",
     "HuggingFace SG161222/Realistic_Vision_V5.1"),
    ("可再下载", "模型", HOME / "ComfyUI/models/controlnet/control_openpose-fp16.safetensors",
     "HuggingFace lllyasviel/ControlNet-v1-1"),
    ("可再下载", "模型", HOME / "ComfyUI/models/loras/lcm-lora-sdv1-5.safetensors",
     "HuggingFace latent-consistency/lcm-lora-sdv1-5"),
    ("可再下载", "模型", HOME / "ComfyUI/models/checkpoints/v1-5-pruned-emaonly-fp16.safetensors",
     "HuggingFace runwayml/stable-diffusion-v1-5（fp16 变体）"),
    ("可再下载", "姿态检测权重", ROOT / ".scratch/hf/hub/models--lllyasviel--Annotators/snapshots/"
     "982e7edaec38759d914a963c48c4726685de7d96/body_pose_model.pth", "HuggingFace lllyasviel/Annotators"),
    ("可再下载", "姿态检测权重", ROOT / ".scratch/hf/hub/models--lllyasviel--Annotators/snapshots/"
     "982e7edaec38759d914a963c48c4726685de7d96/hand_pose_model.pth", "HuggingFace lllyasviel/Annotators"),
    ("可再下载", "姿态检测权重", ROOT / ".scratch/hf/hub/models--lllyasviel--Annotators/snapshots/"
     "982e7edaec38759d914a963c48c4726685de7d96/facenet.pth", "HuggingFace lllyasviel/Annotators"),
]


def sha256_stream(p, chunk=1 << 20):
    """流式算 sha256（**不整file读进内存**——本机内存紧，2 GB 文件读进去会直接把机器拖死）。"""
    h = hashlib.sha256()
    n = 0
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
            n += len(b)
    return h.hexdigest(), n


def rec_of(path, kind, why, note, do_hash=True):
    p = Path(path)
    if not p.exists():
        return {"路径": str(p), "在盘": False, "类别": kind, "用途": why, "来源": note}
    r = {"路径": str(p), "在盘": True, "类别": kind, "用途": why, "来源": note,
         "字节": p.stat().st_size, "MB": round(p.stat().st_size / 1e6, 1),
         "改于": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(p.stat().st_mtime))}
    if do_hash:
        r["sha256"], n = sha256_stream(p)
        r["_哈希字节数一致"] = (n == r["字节"])
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true", help="按内置候选集扫")
    ap.add_argument("--paths", nargs="*", default=[], help="指定文件（不给类别）")
    ap.add_argument("--verify", default="", help="拿清单核对现状（搬回后/搬完后都该跑）")
    ap.add_argument("--no-hash", action="store_true", help="只算字节，不算 sha256（快）")
    a = ap.parse_args()

    if a.verify:
        man = json.loads(Path(a.verify).read_text(encoding="utf-8"))
        rows, bad = [], []
        for f in man.get("文件", []):
            p = Path(f["路径"])
            if not p.exists():
                rows.append({"路径": f["路径"], "结论": "不在盘"})
                continue
            h, n = sha256_stream(p)
            ok = (h == f.get("sha256")) and (n == f.get("字节"))
            rows.append({"路径": f["路径"], "字节": n, "对得上": ok})
            if not ok:
                bad.append(p.name)
        print(json.dumps({"ok": not bad, "status": "verify",
                          "verdict": ("✅ 逐字节对得上（%d 件）" % len(rows)) if not bad
                          else "❗对不上：" + "、".join(bad), "逐件": rows},
                         ensure_ascii=False, indent=1))
        return 0 if not bad else 1

    files = []
    if a.scan:
        for kind, why, p, note in CANDIDATES:
            files.append(rec_of(p, kind, why, note, do_hash=not a.no_hash))
    for ps in a.paths:
        files.append(rec_of(ps, "(未分类)", "(指定)", "", do_hash=not a.no_hash))

    on = [f for f in files if f.get("在盘")]
    total = sum(f["字节"] for f in on)
    by_kind = {}
    for f in on:
        by_kind.setdefault(f["类别"], {"件数": 0, "MB": 0})
        by_kind[f["类别"]]["件数"] += 1
        by_kind[f["类别"]]["MB"] = round(by_kind[f["类别"]]["MB"] + f["MB"], 1)
    man = {"清单时间": time.strftime("%Y-%m-%dT%H:%M:%S"), "根": str(ROOT),
           "合计字节": total, "合计GB": round(total / 1e9, 3), "合计GiB": round(total / (1 << 30), 3),
           "按类别": by_kind, "文件": files,
           "_口径": ("sha256 为**流式**全文件哈希（不整file读内存）；「来源」是被搬走之后**怎么再拿回来**；"
                   "「可再下载」与「丢了就没」必须分开看 —— 前者搬走是省地方，后者搬走才是备份。")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(man, ensure_ascii=False, indent=1), "utf-8")
    print(json.dumps({"ok": True, "status": "manifest", "落点": str(OUT),
                      "合计": "%s B = %.2f GB (%.2f GiB)" % (total, total / 1e9, total / (1 << 30)),
                      "按类别": by_kind,
                      "逐件": [{"MB": f.get("MB"), "在盘": f.get("在盘"),
                              "类别": f.get("类别"), "文件": Path(f["路径"]).name} for f in files]},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
