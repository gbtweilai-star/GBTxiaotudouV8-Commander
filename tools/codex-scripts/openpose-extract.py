#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""OpenPose 检测器（**照片 → 骨架**）+ 闭环回检（骨架 vs 骨架）

## 这件补的是哪半截
`memory/OpenPose-LoRA-组合技-配方与上云.md` §七 的 🔴：**「姿势检测器（照片 → 骨架）未做」** ——
当时用的是**手画的标准骨架**，不是"从照片抽出来的"。本件把那半截补上。
（跑在隔离 venv `.scratch/pose-venv`：`controlnet-aux 0.0.10` + 6 个 `--no-deps` 小包，
 模型 `body_pose_model.pth` 209,267,595 B 落在 `.scratch/hf`，**不污染仓 python**。）

## 两个子命令
- `extract`：照片 → OpenPose 骨架 PNG + 18 关键点 JSON
- `compare`：**两张骨架图对比**（闭环回检：把检测器跑在"当初用骨架生成的那张图"上，
  再看它能不能把那条骨架找回来）—— 这是**把闭环真正闭上**的那一步

## 对比怎么量（两把尺，都要报）
1. **掩膜一致性**：两张骨架图都二值化 → 交并比 IoU + **单向 Chamfer 距离**（用距离变换算，
   比 IoU 更能说明"偏了多少像素"）
2. **关键点质心逐色解码**：OpenPose 是**按关键点序号配色**的 ⇒ 可以按 18 个官方色反解质心。
   ⚠️ **这个尺子有偏**：肢体线也用**子关节**的颜色画 ⇒ 同色像素=关节圆点+半条肢体
   ⇒ 质心会沿肢体偏。**所以它只作旁证，判据以第 1 把尺为准**（写在这里免得下一个人拿它当准的）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# 模型落点**钉在仓内**（209 MB 不散到系统目录）——必须在 import huggingface_hub 之前设
os.environ.setdefault("HF_HOME", str(ROOT / ".scratch" / "hf"))

import cv2                                                        # noqa: E402
import numpy as np                                                # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 官方 18 色（与 openpose-skeleton.py 同一张表 ⇒ 两边可互相解码）
COLORS = [(255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0), (85, 255, 0),
          (0, 255, 0), (0, 255, 85), (0, 255, 170), (0, 255, 255), (0, 170, 255), (0, 85, 255),
          (0, 0, 255), (85, 0, 255), (170, 0, 255), (255, 0, 255), (255, 0, 170), (255, 0, 85)]
KPT = ["nose", "neck", "Rshoulder", "Relbow", "Rwrist", "Lshoulder", "Lelbow", "Lwrist",
       "Rhip", "Rknee", "Rankle", "Lhip", "Lknee", "Lankle", "Reye", "Leye", "Rear", "Lear"]


def imread_u(path):
    """读图 —— **必须走 imdecode**。

    🔴 第 71 轮踩到并记下的经典坑：**`cv2.imread` 在 Windows 上读不了含非 ASCII 的路径**，
    而本仓路径就是 `...\\GBT小土豆V8\\...` ⇒ 直接 `imread` 会返回 `None`（报
    `can't open/read file: check file path/integrity`），看起来像"文件没了"。
    相对路径之所以能过，是因为**传给 cv2 的字符串本身是纯 ASCII**（`render/comfy-pose/x.png`）。
    ⇒ 统一用 `np.fromfile + imdecode`（官方推荐做法），相对/绝对/中文路径全都行。
    """
    try:
        buf = np.fromfile(str(path), dtype=np.uint8)
        if buf.size == 0:
            return None
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)
    except Exception:                                                      # noqa: BLE001
        return None


def imwrite_u(path, img):
    """写图 —— 同理走 `imencode + tofile`（`cv2.imwrite` 也吃不了中文路径）。"""
    ext = os.path.splitext(str(path))[1] or ".png"
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        return False
    buf.tofile(str(path))
    return True


def to_mask(img, thr=24):
    """骨架掩膜：非黑即骨架。

    🔴 第 70 轮修的一把**带色偏的尺子**：原来用 `灰度 > thr` 判"是不是骨架像素"，
    而**蓝色在灰度里很暗**（纯蓝 ≈ 29、半透明蓝 ≈ 15）⇒ 阈值一卡就**把蓝线的抗锯齿边吃掉**，
    于是"同一几何、只换通道顺序"的两张图会算出 **IoU 0.92**（看着像几何变了，其实没变）。
    实测对照：`colored_px` 两版都是 **8163，完全相同** ⇒ 几何一个像素都没动。
    ⇒ 改成**任一分量非黑**（与通道顺序无关）。
    """
    return (img.max(axis=2) > thr).astype(np.uint8)


def mask_agreement(a, b):
    """两把量：IoU + 单向 Chamfer（像素）。b 相对 a 的偏差。"""
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_NEAREST)
    inter = int(np.logical_and(a, b).sum())
    union = int(np.logical_or(a, b).sum())
    iou = round(inter / union, 4) if union else 0.0
    # a 上每个骨架点到 b 最近骨架点的距离（距离变换）
    dt = cv2.distanceTransform((1 - b).astype(np.uint8), cv2.DIST_L2, 3)
    d = dt[a > 0]
    ch = {"a→b 中位": round(float(np.median(d)), 2) if d.size else None,
          "a→b 均值": round(float(d.mean()), 2) if d.size else None,
          "a→b 90分位": round(float(np.percentile(d, 90)), 2) if d.size else None}
    return iou, ch


def decode_keypoints(img, tol=60):
    """按 18 官方色反解关键点质心（**有偏，见文件头**）。返回归一化坐标。"""
    h, w = img.shape[:2]
    out = {}
    for i, c in enumerate(COLORS):
        tgt = np.array([c[2], c[1], c[0]], dtype=np.int16)      # COLORS 是 RGB，cv2 是 BGR
        diff = np.abs(img.astype(np.int16) - tgt).sum(axis=2)
        ys, xs = np.nonzero(diff < tol)
        out[KPT[i]] = [round(float(xs.mean()) / w, 4), round(float(ys.mean()) / h, 4), len(xs)] \
            if len(xs) >= 4 else None
    return out


def cmd_extract(a):
    t0 = time.time()
    img = imread_u(a.image)
    if img is None:
        print(json.dumps({"ok": False, "status": "cannot_read", "image": a.image}, ensure_ascii=False))
        return 2
    try:
        from controlnet_aux import OpenposeDetector
    except Exception as e:                                                 # noqa: BLE001
        print(json.dumps({"ok": False, "status": "needs_dependency",
                          "error": "%s: %s" % (type(e).__name__, str(e)[:200]),
                          "hint": "venv 在 .scratch/pose-venv；controlnet-aux 0.0.10"}, ensure_ascii=False))
        return 3
    try:
        det = OpenposeDetector.from_pretrained("lllyasviel/Annotators")
    except Exception as e:                                                 # noqa: BLE001
        print(json.dumps({"ok": False, "status": "model_unavailable",
                          "error": "%s: %s" % (type(e).__name__, str(e)[:220]),
                          "hf_home": os.environ.get("HF_HOME")}, ensure_ascii=False))
        return 4
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    from PIL import Image
    pil = Image.fromarray(rgb)
    if a.resize:
        pil = pil.resize((a.resize, a.resize))
    skel = det(pil, detect_resolution=a.detect_resolution, image_resolution=a.image_resolution,
               include_hand=a.hand, include_face=a.face)
    arr = np.array(skel)                                                   # RGB
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    outp = Path(a.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    imwrite_u(outp, bgr)
    m = to_mask(bgr)
    kp = decode_keypoints(bgr)
    found = [k for k, v in kp.items() if v]
    res = {"ok": True, "status": "extracted", "image": a.image, "out": str(outp),
           "size": [bgr.shape[1], bgr.shape[0]], "bytes": outp.stat().st_size,
           "skeleton_px": int(m.sum()), "keypoints_decoded": len(found), "of": 18,
           "keypoints": kp, "elapsed_s": round(time.time() - t0, 1),
           "include_hand": a.hand, "include_face": a.face,
           "_口径": ("**真检测器**（controlnet-aux + lllyasviel/Annotators body_pose_model.pth 209,267,595 B）"
                   "⇒ 这条是「照片→骨架」，不再是手画骨架。decoded 数 < 18 说明该关节没检出（如实报）")}
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if m.sum() > 100 else 5


def cmd_compare(a):
    A = imread_u(a.ref)
    B = imread_u(a.test)
    if A is None or B is None:
        print(json.dumps({"ok": False, "status": "cannot_read",
                          "ref": A is not None, "test": B is not None}, ensure_ascii=False))
        return 2
    ma, mb = to_mask(A), to_mask(B)
    iou, ch = mask_agreement(ma, mb)
    iou2, ch2 = mask_agreement(mb, ma)          # 反向，看对称性
    ka, kb = decode_keypoints(A), decode_keypoints(B)
    pairs, dists = [], []
    for k in KPT:
        if ka.get(k) and kb.get(k):
            dx = (ka[k][0] - kb[k][0]) * A.shape[1]
            dy = (ka[k][1] - kb[k][1]) * A.shape[0]
            d = (dx * dx + dy * dy) ** 0.5
            pairs.append({"关节": k, "ref": ka[k][:2], "test": kb[k][:2], "像素距离": round(d, 1)})
            dists.append(d)
    d = np.array(dists) if dists else np.array([])
    res = {"ok": True, "status": "compared", "ref": a.ref, "test": a.test,
           "掩膜一致性": {"IoU": iou, "ref→test": ch, "test→ref": ch2,
                     "骨架像素": [int(ma.sum()), int(mb.sum())]},
           "关键点质心距离（**旁证，有偏**）": {
               "可对比关节数": len(pairs),
               "中位像素距离": round(float(np.median(d)), 1) if d.size else None,
               "均值": round(float(d.mean()), 1) if d.size else None,
               "最大": round(float(d.max()), 1) if d.size else None},
           "逐关节": pairs,
           "_口径": ("判据以**掩膜一致性**为准（IoU + 单向 Chamfer 像素）；"
                   "关键点质心**有偏**（肢体线用子关节颜色画，质心沿肢体偏）⇒ 只作旁证。"
                   "对照的是**同一张 512 图内的像素**，不是真实世界尺度")}
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


def cmd_joints(a):
    """**关节级**读数：从一张骨架图解出 18 个关节位置，可选与内置姿势真值对比。

    ## 为什么这条能是**无偏**的
    这个检测器画出来的骨架，**每个颜色恰好 49 个像素 = 那个关节的圆点**（没有同色的肢体线）
    ⇒ 逐色质心**就是关节位置**，没有"沿肢体拖移"那个偏。
    （而我手画的骨架里，肢体线用的是**子关节**的颜色 ⇒ 那侧质心**有偏**，
     所以这侧一律用**内置真值表**，不用有偏质心 —— 两边都不将就。）
    """
    img = imread_u(a.skeleton)
    if img is None:
        print(json.dumps({"ok": False, "status": "cannot_read", "skeleton": a.skeleton},
                         ensure_ascii=False))
        return 2
    h, w = img.shape[:2]
    got = decode_keypoints(img)
    found = {k: v[:2] for k, v in got.items() if v}
    res = {"ok": True, "status": "joints", "skeleton": a.skeleton, "size": [w, h],
           "decoded": len(found), "of": 18, "joints": {k: {"x": v[0], "y": v[1]} for k, v in found.items()}}
    if a.truth:
        # 用**内置真值表**（并经 to_standard_lr 正名），不用有偏质心
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "osk", str(Path(__file__).with_name("openpose-skeleton.py")))
        osk = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(osk)
        if a.truth not in osk.POSES:
            res["truth_error"] = "未知预设：%s（有 %s）" % (a.truth, list(osk.POSES))
            print(json.dumps(res, ensure_ascii=False, indent=1))
            return 2
        truth = osk.to_standard_lr(osk.POSES[a.truth])
        rows, ds = [], []
        for k in KPT:
            if k in found and k in truth:
                dx = (found[k][0] - truth[k][0]) * w
                dy = (found[k][1] - truth[k][1]) * h
                d = (dx * dx + dy * dy) ** 0.5
                rows.append({"关节": k, "检出": [round(found[k][0], 4), round(found[k][1], 4)],
                             "真值": [round(truth[k][0], 4), round(truth[k][1], 4)],
                             "像素误差": round(d, 1),
                             "各轴": [round(dx, 1), round(dy, 1)]})
                ds.append(d)
        arr = np.array(ds) if ds else np.array([])
        np.sort(arr) if arr.size else arr
        res["关节级对齐"] = {
            "可对比关节数": len(rows),
            "中位像素误差": round(float(np.median(arr)), 1) if arr.size else None,
            "均值": round(float(arr.mean()), 1) if arr.size else None,
            "最大": round(float(arr.max()), 1) if arr.size else None,
            "P90": round(float(np.percentile(arr, 90)), 1) if arr.size else None,
            "最差的 5 个": [r["关节"] + " " + str(r["像素误差"]) for r in
                        sorted(rows, key=lambda r: -r["像素误差"])[:5]],
            "最好 3 个": [r["关节"] + " " + str(r["像素误差"]) for r in
                       sorted(rows, key=lambda r: r["像素误差"])[:3]],
            "_口径": ("真值 = 内置预设 `%s`（经标准 L/R 正名）· 检出 = 检测器输出的**圆点质心**（无偏）；"
                    "单位是**同一张 %dx%d 图内的像素**，不是真实世界尺度" % (a.truth, w, h))}
        res["逐关节"] = rows
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if found else 5


def main() -> int:
    ap = argparse.ArgumentParser(description="OpenPose 检测器 + 骨架闭环回检")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract", help="照片 → 骨架")
    e.add_argument("image")
    e.add_argument("--out", default="render/comfy-pose/detected-openpose.png")
    e.add_argument("--detect-resolution", type=int, default=512)
    e.add_argument("--image-resolution", type=int, default=512)
    e.add_argument("--resize", type=int, default=0)
    e.add_argument("--hand", action="store_true")
    e.add_argument("--face", action="store_true")
    e.set_defaults(fn=cmd_extract)
    c = sub.add_parser("compare", help="两张骨架图对比（闭环回检）")
    c.add_argument("ref")
    c.add_argument("test")
    c.set_defaults(fn=cmd_compare)
    j = sub.add_parser("joints", help="关节级读数（从骨架图解 18 关节；可对内置真值）")
    j.add_argument("skeleton")
    j.add_argument("--truth", default="", help="内置预设名（stand/tpose/walk/sit）⇒ 出关节级误差")
    j.set_defaults(fn=cmd_joints)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
