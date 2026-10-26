#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""taste_gate —— 把吞噬来的 taste-skill **融合进 GBT天真**：出版前先过闸。

它不是"再画一遍"，是把家规变成**可量的阈值**，让天真在交付前自己判：
    ①三个色以内  ②对比够  ③焦点唯一  ④不靠渐变  ⑤留白成块  ⑥边缘不吵

由来（诚实边界）：taste-skill 的原始判据是**前端口径**（字号比/间距/发丝线/emoji）。
插画能直接借用的只有构图与色光这一半，所以这里只实现那几条，并且每条都给**读数**，
凑不出的（人体结构、布料、透视）**不假装能判**，直接标 not_measurable。

用法：
    python3 tools/taste_gate.py --judge /var/minis/attachments/x.png
    python3 tools/taste_gate.py --brief "齐天大圣 力劈华山"
"""
import argparse
import json
import sys
from collections import Counter

try:
    from PIL import Image, ImageFilter, ImageStat
except Exception:                                                 # noqa: BLE001
    print("需要 Pillow")
    raise SystemExit(2)

# 阈值来自 taste-skill 里能对插图生效的那一半（不是拍脑袋）
LIMITS = {
    "colors_max": 4,          # 一底一墨一强调 + 断面
    "contrast_min": 45.0,     # 亮度标准差（Laws · 色/光比）
    "focus_min": 0.0015,      # 最亮点占比下限（太小就没有焦点）
    "focus_max": 0.050,       # 上限（太大就是曝光过度，v1 的月亮就是 7.8%）
    "edge_min": 0.006,        # 太干净 = 没内容
    "edge_max": 0.050,        # 太吵 = 靠细节堆装饰
    "void_min": 0.12,         # 留白下限（成块的空，不是碎屑）
    "void_max": 0.62,
    "gradient_row_frac": 0.55,  # 相邻行几乎不变的占比超过它 ⇒ 判为靠渐变过渡
}

NOT_MEASURABLE = ["人体结构", "布料走向", "透视一致", "材质纹理"]


def _blobs(mask, w, h, min_ratio=0.0004):
    """粗估连通块数量（4 邻域，网格下采样，够用且快）。"""
    import numpy as np
    small = mask.resize((96, 128))
    a = (np.array(small) > 128).astype("uint8")
    seen = np.zeros_like(a)
    n, areas = 0, []
    for y in range(a.shape[0]):
        for x in range(a.shape[1]):
            if a[y, x] and not seen[y, x]:
                stack, area = [(y, x)], 0
                seen[y, x] = 1
                while stack:
                    cy, cx = stack.pop()
                    area += 1
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < a.shape[0] and 0 <= nx < a.shape[1] \
                                and a[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = 1
                            stack.append((ny, nx))
                if area / (a.shape[0] * a.shape[1]) >= min_ratio:
                    n += 1
                    areas.append(area)
    return n, sorted(areas, reverse=True)[:3]


PROFILES = {
    # 平面海报：家规原味，色数/渐变卡死
    "poster": dict(LIMITS),
    # 摄影/插画：色数与渐变不作数（照片天然 16 色以上、天然有长坡），
    #          但"焦点唯一、留白成块、边缘不吵"仍然要卡。
    "photo": {**LIMITS, "colors_max": 16, "gradient_row_frac": 1.01,
              "contrast_min": 28.0, "focus_min": 0.0004},
}


def judge(path, profile="poster"):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    g = im.convert("L")
    st = ImageStat.Stat(g)
    L = PROFILES.get(profile, PROFILES["poster"])
    luma_mean, luma_std = st.mean[0], st.stddev[0]

    # ① 色数：量化后覆盖 >2% 面积的色
    q = im.resize((160, 213)).quantize(colors=16, method=Image.MEDIANCUT).convert("RGB")
    px = list(q.getdata())
    cnt = Counter(px)
    total = len(px)
    dominant = [c for c, n in cnt.most_common() if n / total >= 0.02]

    # ② 焦点：最亮点占比 + 连通块
    # 🔴 2026-10-26 修：原来用绝对 238，任何亮色低于它的画面都判"没焦点"。
    #    改成相对——取亮度直方图 99.5 分位往下 6 个灰阶作为"最亮档"。
    import numpy as np
    hist = np.array(g.histogram(), dtype="float64")
    cum = hist.cumsum() / hist.sum()
    p995 = int(np.searchsorted(cum, 0.995))
    thr = max(200, p995 - 6)
    hot = g.point(lambda v: 255 if v >= thr else 0)
    focus_ratio = sum(1 for v in hot.getdata() if v) / (w * h)
    nblob, areas = _blobs(hot, w, h)

    # ③ 边缘密度
    e = g.filter(ImageFilter.FIND_EDGES)
    edge = sum(1 for v in e.getdata() if v > 40) / (w * h)

    # ④ 渐变嫌疑：相邻行均值几乎不变的比例
    import numpy as np
    rows = np.array(g.resize((64, 256)), dtype="float32").mean(axis=1)
    d = np.abs(np.diff(rows))
    # 🔴 2026-10-26 修误判：原来用 (d<0.8) 判渐变，其实测的是"平涂"。
    #    真渐变是**小幅但连续**的变化（长坡），硬边是大幅跳变，平涂是 0。
    smooth_frac = float(((d > 0.15) & (d < 2.0)).mean())

    # ⑤ 留白：与画面主色差 <6 的像素占比
    bg = cnt.most_common(1)[0][0]
    void = sum(1 for p in px if max(abs(p[i] - bg[i]) for i in range(3)) <= 6) / total

    axes = [
        ("色数", len(dominant), "≤%d" % L["colors_max"], len(dominant) <= L["colors_max"]),
        ("对比(亮度sd)", round(luma_std, 1), "≥%.0f" % L["contrast_min"], luma_std >= L["contrast_min"]),
        ("焦点占比", round(focus_ratio, 4), "%.4f~%.3f" % (L["focus_min"], L["focus_max"]),
         L["focus_min"] <= focus_ratio <= L["focus_max"]),
        ("焦点块数", nblob, "=1 最好", nblob in (1, 2)),
        ("边缘密度", round(edge, 4), "%.3f~%.3f" % (L["edge_min"], L["edge_max"]),
         L["edge_min"] <= edge <= L["edge_max"]),
        ("留白占比", round(void, 3), "%.2f~%.2f" % (L["void_min"], L["void_max"]),
         L["void_min"] <= void <= L["void_max"]),
        ("渐变嫌疑", round(smooth_frac, 2), "<%.2f" % L["gradient_row_frac"],
         smooth_frac < L["gradient_row_frac"]),
    ]
    fails = [a[0] for a in axes if not a[3]]
    return {
        "image": path, "size": [w, h],
        "readings": {"luma_mean": round(luma_mean, 1), "luma_std": round(luma_std, 1),
                     "colors": len(dominant), "palette": ["#%02x%02x%02x" % c for c in dominant],
                     "focus_ratio": round(focus_ratio, 4), "focus_blobs": nblob,
                     "edge": round(edge, 4), "void": round(void, 3),
                     "smooth_frac": round(smooth_frac, 2)},
        "axes": [{"axis": a[0], "value": a[1], "limit": a[2], "pass": a[3]} for a in axes],
        "verdict": "PASS" if not fails else "FAIL", "profile": profile,
        "fails": fails,
        "not_measurable": NOT_MEASURABLE,
    }


def brief(subject):
    """把判据反推成"出图前的硬参数"—— 这就是"融合"的那一半：先给约束，再画。"""
    return {
        "subject": subject,
        "canvas": "768x1024",
        "palette": {"ground": "#0b0f16", "ink": "#05070b", "accent": "#d9a44c",
                    "extra_max": 1, "note": "第 4 色只给断面/材质，不许当第二个强调"},
        "contrast_target_luma_std": LIMITS["contrast_min"],
        "focus": {"count": 1, "ratio": [L["focus_min"], L["focus_max"]],
                  "where": "主对角线上，距画面中心 1/4 处"},
        "void_ratio": [L["void_min"], L["void_max"]],
        "edge_density": [L["edge_min"], L["edge_max"]],
        "forbidden": ["渐变", "发光", "暗角", "emoji", "装饰性放射线超过 6 道", "碎屑雨"],
        "not_measurable": NOT_MEASURABLE,
        "note": "闸只能保证不犯禁；像不像画，取决于模型有没有材质与解剖",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge")
    ap.add_argument("--brief")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--profile", default="poster", choices=["poster", "photo"])
    a = ap.parse_args()

    if a.brief:
        print(json.dumps(brief(a.brief), ensure_ascii=False, indent=1))
        return 0
    if not a.judge:
        print("用法: taste_gate.py --judge <图> | --brief \"题材\"")
        return 1

    r = judge(a.judge, a.profile)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["verdict"] == "PASS" else 1

    print("被试 %s · %dx%d · 档=%s" % (a.judge.split("/")[-1], r["size"][0], r["size"][1], r["profile"]))
    print("%-14s %-10s %-14s %s" % ("轴", "读数", "阈值", "结果"))
    print("-" * 52)
    for x in r["axes"]:
        print("%-14s %-10s %-14s %s" % (x["axis"], x["value"], x["limit"], "OK" if x["pass"] else "FAIL"))
    print("-" * 52)
    print("判定 %s%s" % (r["verdict"], (" · 不过：" + "、".join(r["fails"])) if r["fails"] else ""))
    print("不可判（不假装能判）：%s" % "、".join(r["not_measurable"]))
    return 0 if r["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
