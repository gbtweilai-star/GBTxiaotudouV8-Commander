#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""reframe —— 本地能修的"构图两轴"：焦点收敛 + 留白扩展。

上一轮的结论是"精修改不了构图"。这句只对了一半：
  · 改不了 —— 主体姿态、机位、景深（需要重画）
  · 改得了 —— **次要高光**与**留白面积**（纯像素操作）

两个动作，都可测：
  ① 焦点收敛：找出所有"最亮档"的连通块，只留最大的一块，其余压暗并羽化
  ② 留白扩展：留白不足时，向主体相反的一侧**扩画布**（用主色填充），形成非对称负空间

用法： python3 tools/reframe.py 图.jpg --out 修后.png [--darken 0.62] [--no-pad]
"""
import argparse, os, sys
import numpy as np
from PIL import Image, ImageFilter

TOOLS = os.path.dirname(os.path.abspath(__file__))


def load_gate():
    import importlib.util
    spec = importlib.util.spec_from_file_location("tg", os.path.join(TOOLS, "taste_gate.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def bright_mask(im, pct=99.0):
    g = np.asarray(im.convert("L"), dtype=np.float32)
    thr = np.percentile(g, pct)
    return (g >= thr), g


def components(mask, min_ratio=0.0005):
    """4 邻域连通块（下采样网格上做，够快也够用）。"""
    small = Image.fromarray((mask * 255).astype(np.uint8)).resize((96, 128), Image.BILINEAR)
    a = (np.asarray(small) > 127).astype(np.uint8)
    seen = np.zeros_like(a); out = []
    for y in range(a.shape[0]):
        for x in range(a.shape[1]):
            if a[y, x] and not seen[y, x]:
                st = [(y, x)]; seen[y, x] = 1; pts = []
                while st:
                    cy, cx = st.pop(); pts.append((cy, cx))
                    for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)):
                        ny, nx = cy+dy, cx+dx
                        if 0 <= ny < a.shape[0] and 0 <= nx < a.shape[1] and a[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = 1; st.append((ny, nx))
                if len(pts)/(a.shape[0]*a.shape[1]) >= min_ratio:
                    out.append(pts)
    return out, a.shape


def converge_focus(im, darken=None):
    """只留最大的一块高光，其余压暗。

    v1 的错：darken 固定 0.62，暗调图（tz_A）被压到焦点块数 0 —— 主光也被压没了。
    v2：按画面亮度中位数自适应（暗图轻压、亮图重压），并且**给留下的那块补一点亮度**，
        保证它在相对阈值下仍然"最亮"。
    """
    g0 = np.asarray(im.convert("L"), dtype=np.float32)
    if darken is None:
        med = float(np.median(g0))
        darken = float(np.clip(0.92 - med / 255.0 * 0.55, 0.55, 0.90))
    mask, g = bright_mask(im)
    blobs, (gh, gw) = components(mask)
    if len(blobs) <= 1:
        return im, 0
    blobsz = sorted(blobs, key=len, reverse=True)
    H, W = im.size[1], im.size[0]
    m = Image.new("L", (gw, gh), 0)
    for (y, x) in [p for b in blobsz[1:] for p in b]:
        m.putpixel((x, y), 255)
    m = m.resize((W, H), Image.BILINEAR).filter(ImageFilter.GaussianBlur(6))
    f = np.asarray(m, dtype=np.float32) / 255.0
    a = np.asarray(im, dtype=np.float32)
    a = a * (1 - f[..., None] * (1 - darken))
    # 主光补 3%：避免压暗后整幅没有"最亮档"，闸会判焦点块数 0
    m_main = Image.new("L", (gw, gh), 0)
    for (y, x) in blobsz[0]:
        m_main.putpixel((x, y), 255)
    mm = np.asarray(m_main.resize((W, H), Image.BILINEAR).filter(ImageFilter.GaussianBlur(4)),
                    dtype=np.float32) / 255.0
    a = a * (1 + mm[..., None] * 0.03)
    # 兜底：压暗后若整幅最高亮度掉到 200 以下，闸的"最亮档"就找不到焦点（tz_A 就是这样归零的）
    cur_max = float(a.mean(axis=2).max())
    if cur_max < 200:
        a = np.clip(a * min(1.18, 200.0 / max(cur_max, 1.0)), 0, 255)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB"), len(blobs)-1


def dominant_color(im):
    q = im.resize((64, 64)).quantize(colors=8, method=Image.MEDIANCUT).convert("RGB")
    px = list(q.getdata()); from collections import Counter
    return Counter(px).most_common(1)[0][0]


def pad_space(im, target_void=0.16, side="right"):
    """留白不够就往一侧扩画布（主色填充），形成非对称负空间。"""
    a = np.asarray(im.convert("RGB"), dtype=np.float32)
    bg = dominant_color(im)
    # 估算当前留白：与主色接近的像素占比
    m = (np.abs(a - np.array(bg, dtype=np.float32)).max(axis=2) <= 8).mean()
    if m >= target_void:
        return im, m, False
    W, H = im.size
    need = int(W * (target_void - m) / max(target_void, 1e-6))
    need = max(0, min(int(W * 1.4), need))
    canvas = Image.new("RGB", (W + need, H), bg)
    canvas.paste(im, (0, 0) if side == "right" else (need, 0))
    return canvas, m, True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("--out")
    ap.add_argument("--darken", type=float, default=None, help="默认自适应：暗图轻压、亮图重压")
    ap.add_argument("--no-pad", action="store_true")
    a = ap.parse_args()
    tg = load_gate()
    dst = a.out or a.src.rsplit(".", 1)[0] + "_reframe.png"

    b = tg.judge(a.src, "photo")
    im = Image.open(a.src).convert("RGB")
    im, killed = converge_focus(im, a.darken)
    padded = False
    if not a.no_pad:
        im, void0, padded = pad_space(im)
    cand = dst.replace(".png", "_cand.png")
    im.save(cand, "PNG")
    aft_c = tg.judge(cand, "photo")
    # 🔴 自检回退：rz_A 那种暗调图，压暗后焦点块数会归零（3→0），比原图更糟。
    #    规则：候选的"不过项"不比原图少 ⇒ 不采纳，原图原样输出，并如实说明。
    if len(aft_c["fails"]) >= len(b["fails"]) or aft_c["readings"]["focus_blobs"] == 0:
        import shutil
        shutil.copy(a.src, dst)
        aft = tg.judge(dst, "photo")
        print("回退  候选更差（不过项 %d→%d，焦点块 %d）⇒ 未采纳，输出原图"
              % (len(b["fails"]), len(aft_c["fails"]), aft_c["readings"]["focus_blobs"]))
    else:
        import shutil
        shutil.move(cand, dst)
        aft = aft_c
        print("采纳  修后过闸项变化：不过项 %d→%d" % (len(b["fails"]), len(aft["fails"])))
    print("原图  %s  %s" % (b["verdict"], ",".join(b["fails"]) or "-"))
    print("修后  %s  %s" % (aft["verdict"], ",".join(aft["fails"]) or "-"))
    print("动作  压暗次要高光 %d 块 · 扩画布 %s · 尺寸 %s" % (killed, "是" if padded else "否", im.size))
    print("读数  焦点块数 %s→%s · 留白 %s→%s"
          % (b["readings"]["focus_blobs"], aft["readings"]["focus_blobs"],
             b["readings"]["void"], aft["readings"]["void"]))
    return 0 if aft["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
