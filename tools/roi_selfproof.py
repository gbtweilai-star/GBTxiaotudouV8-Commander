# -*- coding: utf-8 -*-
# gbt-capability: roi_selfproof  ⬻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""清晰度读数 **ROI 自证器** —— 治「测的不是人脸」这个坑。

由来（她早就写下的 pitfall）：自动 ROI 取到了 **HUD 文字区**，测的不是脸。
⇒ 本件把「ROI 必须自证」做成**可机检的三件套**：
   ① 肤色占比（**阈值 0.015 由正负对照标定，不是猜的**）
   ② 排除 HUD（四边留白带扫描）
   ③ **输出裁图**　供人眼复核（缺这张图，前两项都不算）

阈值出处（2026-10-15 实测）：
  正样本（真脸）：HSV 0.036~0.071 · YCrCb 0.056~0.113
  负样本（6 张 UI 截图）：HSV 0.000~0.002 · YCrCb 0.001~0.002
  ⇒ 可判别阈值 HSV 0.019 / YCrCb 0.029 ⇒ **判据取 0.015 留余量**
  ⚠️ 第一版写 0.15 是拍脑袋，连真脸都过不去（实测 0.064）

🔴 2026-10-15 两条纪律（都是踩出来的）：
  1. **判据工具绝不许崩** —— 崩了就没法判。任何异常都要落成「FAIL + 原因」。
     实测：负样本（UI 截图）把 `np.diff` 跑出空数组 ⇒ 整个进程 Traceback ⇒
     **假缺口**（看着像「工具坏了」，其实只是判据该给 FAIL）。
  2. 单行/单列带会让 `np.diff` 出空 ⇒ 每边独立 try，取不到给 0.0（**偏向放过而非误杀**）。

用法：
  py -3.14 tools/roi_selfproof.py <图> [--out 裁图.png] [--json]
  退出码：0 = 自证 PASS · 1 = FAIL（含异常）· 2 = 文件不在
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

# 🔴 Windows GBK 控制台防护：**判据工具绝不许因打印崩**（本 bug 已出现 3 次）
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SKIN_MIN = 0.015          # 标定值（见文件头）
HUD_EDGE = 0.06           # 四边 6% 带内算「界面带」
HUD_MAX = 6.0             # 四边带方差上限（≥ 判为像 HUD）


def skin_ratio(rgb, mode="hsv"):
    """肤色占比。hsv 口径偏严（她原用的），ycc 口径对影棚光更稳"""
    r = rgb[:, :, 0].astype(np.int16)
    g = rgb[:, :, 1].astype(np.int16)
    b = rgb[:, :, 2].astype(np.int16)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    v = mx
    s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1) * 255, 0)
    d = np.maximum(mx - mn, 1)
    hue = np.where(mx == r, ((g - b) * 42 // d) % 256,
                   np.where(mx == g, ((b - r) * 42 // d) + 85, ((r - g) * 42 // d) + 170))
    if mode == "hsv":
        m = (((hue < 25) | (hue > 160)) & (s > 30) & (s < 190) & (v > 70))
    else:
        cr = (0.5 * r - 0.418688 * g - 0.081312 * b) + 128
        cb = (-0.168736 * r - 0.331264 * g + 0.5 * b) + 128
        m = (cr > 133) & (cr < 180) & (cb > 77) & (cb < 133)
    return float(m.mean()), m


def hud_bands(rgb):
    """四边带内的「像界面」程度。**每边独立 try**，取不到给 0.0（偏向放过）"""
    out = {"top": 0.0, "bottom": 0.0, "left": 0.0, "right": 0.0, "max": 0.0}
    try:
        g = np.asarray(rgb, dtype=np.float32).mean(2)
        h, w = g.shape
        eh = max(2, int(h * HUD_EDGE))
        ew = max(2, int(w * HUD_EDGE))
        bands = (("top", g[:eh], 1), ("bottom", g[-eh:], 1),
                 ("left", g[:, :ew], 0), ("right", g[:, -ew:], 0))
        for k, b, ax in bands:
            try:
                prof = b.mean(ax)
                if prof.size >= 2:
                    out[k] = float(np.abs(np.diff(prof)).mean())
            except Exception:
                out[k] = 0.0
        out["max"] = max(out["top"], out["bottom"], out["left"], out["right"])
    except Exception:
        pass
    return out


def _run(a):
    im = Image.open(a.img).convert("RGB")
    W, H = im.size
    if W > 1400:
        im = im.resize((1400, max(1, int(1400 * H / W))), Image.LANCZOS)
        W, H = im.size
    rgb = np.array(im)
    r_hsv, mask = skin_ratio(rgb, "hsv")
    r_ycc, _ = skin_ratio(rgb, "ycc")
    hb = hud_bands(rgb)

    box = None
    try:
        ys, xs = np.where(mask)
        if len(xs) > 50:
            x0, x1 = int(xs.min()), int(xs.max())
            y0, y1 = int(ys.min()), int(ys.max())
            pw = int((x1 - x0) * 0.08) + 4
            ph = int((y1 - y0) * 0.08) + 4
            box = (max(0, x0 - pw), max(0, y0 - ph),
                   min(W, x1 + pw), min(H, y1 + ph))
    except Exception:
        box = None

    out = {
        "file": os.path.basename(a.img), "size": [W, H],
        "skin_ratio_hsv": round(r_hsv, 4), "skin_ratio_ycc": round(r_ycc, 4),
        "阈值": SKIN_MIN,
        "肤色过线": bool(max(r_hsv, r_ycc) > SKIN_MIN),
        "hud_bands": {k: round(v, 2) for k, v in hb.items()},
        "hud_excluded": bool(hb["max"] < HUD_MAX),
        "crop_box": box, "裁图": "",
    }
    ok = out["肤色过线"] and out["hud_excluded"] and bool(box)
    out["自证结论"] = "PASS" if ok else "FAIL"
    if not out["肤色过线"]:
        out["为什么"] = ("肤色占比 %.4f ≤ 阈值 %.3f ⇒ **ROI 不是人脸**"
                         "（很可能取到了 UI）" % (max(r_hsv, r_ycc), SKIN_MIN))
    elif not out["hud_excluded"]:
        out["为什么"] = "四边带内像界面（max %.2f ≥ %.1f）⇒ 取到了 HUD" % (hb["max"], HUD_MAX)
    elif not box:
        out["为什么"] = "肤色像素不足以定框 ⇒ 无法输出裁图（缺这张图，前两项都不算）"

    if a.out and box:
        try:
            im.crop(box).save(a.out)
            out["裁图"] = a.out
        except Exception as e:
            out["裁图写入失败"] = str(e)[:80]
            out["自证结论"] = "FAIL"

    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        for k, v in out.items():
            print("  %-16s %s" % (k, v))
    return 0 if out["自证结论"] == "PASS" else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("img")
    ap.add_argument("--out", default="")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if not os.path.isfile(a.img):
        print("图不在：%s" % a.img)
        return 2
    try:
        return _run(a)
    except Exception as e:
        # ★ 判据工具**绝不崩**：出错也要给「FAIL + 原因」
        o = {"file": os.path.basename(a.img), "自证结论": "FAIL",
             "为什么": "自证器异常：%s: %s" % (type(e).__name__, str(e)[:110])}
        print(json.dumps(o, ensure_ascii=False, indent=1) if a.json
              else "\n".join("  %-16s %s" % (k, v) for k, v in o.items()))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
