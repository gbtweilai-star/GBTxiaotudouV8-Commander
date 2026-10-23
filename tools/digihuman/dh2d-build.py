# -*- coding: utf-8 -*-
"""dh2d-build.py — 把主人指定的那张形象图做成 **2.5D 分层数字人**的素材件。

为什么要这条路（2026-10-19 定）：现役 3D 资产 dh-v2-rigged.glb 的脸贴图只够 200px、
嘴是焊死的（无颌骨/无形态键），三个要求（画质清晰 / 动作自然 / 语音嘴对齐）在 3D 那条路上
**没有新美术或新额度就到顶了**。主人给的这张图就是标准（CHARACTER-SPEC 里写死），
所以把这张图本身做成可动的分层件：像素级像、嘴是画出来的因此可控、清晰度只受显示尺寸影响。

产出（全部落在 holo_pet_w3/voice-theater/assets/dh2d/）：
  albedo.png   角色 RGBA（背景抠掉、边缘羽化）
  cavity.png   口腔内壁 + 上齿 + 舌（张嘴时从缝里露出来的那层）
  meta.json    锚点（嘴/眼/头/颈）与扣像读数

用法：py -3.14 tools/digihuman/dh2d-build.py [--crop-bottom 1190] [--print]
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, 'outputs', 'ref', 'character-ref.png')
OUT = os.path.join(ROOT, 'holo_pet_w3', 'voice-theater', 'assets', 'dh2d')
BG_KILLED = []


def arg(name, default=None):
    a = sys.argv
    if name in a:
        i = a.index(name)
        if i + 1 < len(a):
            return a[i + 1]
    return default


def bg_model(rgb):
    """二次曲面拟合背景（影棚灰是**径向渐变**，逐行线性插必错 —— 上一版就是这么把中间背景
    当成前景留了一大块）。样本只取左/右/上三边（下边被靴子压着，不能用来拟合，靠曲面外推）。
    """
    h, w, _ = rgb.shape
    k, top = 8, 24
    ys, xs = [], []
    for y in range(h):
        ys += [y] * (2 * k)
        xs += list(range(k)) + list(range(w - k, w))
    for y in range(top):
        for x in range(k, w - k, 3):
            ys.append(y)
            xs.append(x)
    ys = np.asarray(ys, np.float32)
    xs = np.asarray(xs, np.float32)
    xn, yn = xs / w, ys / h
    A = np.stack([np.ones_like(xn), xn, yn, xn * xn, yn * yn, xn * yn], axis=1)
    S = rgb[ys.astype(int), xs.astype(int), :]                 # (n,3)
    coef, *_ = np.linalg.lstsq(A, S, rcond=None)               # (6,3)

    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    xn, yn = xx / w, yy / h
    B = np.stack([np.ones_like(xn), xn, yn, xn * xn, yn * yn, xn * yn], axis=-1)
    return B @ coef                                            # (h,w,3)


def kill_enclosed_bg(fg, rgb, log=None):
    """GrabCut 会把**被身体包住的背景**判成前景（实测：两腿之间的灰楔子、脚边的地面反光）。
    背景是中性灰、皮肤偏暖、衣服与头发很暗 ⇒ 用「中性灰 + 不与画面边缘连通」把它摘出去。
    阈值写死为中性（|R-B|<=6），皮肤 R-B 普遍 20+、头发暗部 L<60，都碰不到。
    """
    import cv2
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    L = 0.299 * r + 0.587 * g + 0.114 * b
    mx = np.max(rgb, axis=2)
    mn = np.min(rgb, axis=2)
    # 中性 = 通道极差小（影棚灰带蓝偏 B-G≈11，所以不能按 |G-B|<=6 判，上一版就是这么漏的）
    # 且 **B 必须比 G 高**：影棚灰是冷调，皮肤（哪怕在暗部）永远是暖调 B<G ——
    # 少了这一条，大腿上的暗部皮肤会被当成背景挖出两条竖洞（真挖过）。
    neutral = ((mx - mn) <= 14) & (L >= 70) & (L <= 235) & ((b - g) >= 3)
    cand = (neutral & (fg > 0.5)).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(cand, 8)
    out = fg.copy()
    killed = []
    for i in range(1, n):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area < 600:
            continue            # 小的中性亮斑是靴子/扣环上的镜面高光，留着
        out[lab == i] = 0.0
        killed.append([int(stats[i, cv2.CC_STAT_LEFT]), int(stats[i, cv2.CC_STAT_TOP]),
                       int(stats[i, cv2.CC_STAT_WIDTH]), int(stats[i, cv2.CC_STAT_HEIGHT]), area])
    return out, killed


def matte(rgb, thr):
    """抠像：GrabCut（影棚灰是**打光渐变** —— 上暗下亮还有个亮地面，任何多项式都拟合不住，
    前两版就是这么把中间背景当前景留成一大块灰）。thr 在这里只当羽化后的软边阈值用。
    """
    import cv2
    h, w, _ = rgb.shape
    img = np.ascontiguousarray(rgb.astype(np.uint8))
    bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    mask = np.full((h, w), cv2.GC_PR_FGD, np.uint8)
    b = 3
    mask[:b, :] = cv2.GC_BGD
    mask[-b:, :] = cv2.GC_BGD
    mask[:, :b] = cv2.GC_BGD
    mask[:, -b:] = cv2.GC_BGD
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(bgr, mask, None, bgd, fgd, 5, cv2.GC_INIT_WITH_MASK)
    fg = np.isin(mask, [cv2.GC_FGD, cv2.GC_PR_FGD]).astype(np.float32)
    # 只留最大的连通块（地面反光/边角碎块一律不要）
    fgu = fg.astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(fgu, 8)
    if n > 1:
        big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        fg = (lab == big).astype(np.float32)
    # 填内部小洞（扣像常见的眼白/高光小洞）
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    fg2, killed = kill_enclosed_bg(fg, rgb)
    fg = fg2
    BG_KILLED.extend(killed)
    a = Image.fromarray((np.clip(fg, 0, 1) * 255).astype(np.uint8), 'L')
    a = a.filter(ImageFilter.GaussianBlur(1.1))
    arr = np.asarray(a).astype(np.float32) / 255.0
    soft = max(0.02, min(0.45, thr / 100.0))
    arr = np.clip((arr - soft) / max(1e-3, 1.0 - 2 * soft), 0.0, 1.0)
    arr = fill_small_holes(arr, 2000)
    return arr, fg


def fill_small_holes(a, max_area):
    """把被身体包住的**小**透明洞补回来（实测：嘴唇上有个高光被 GrabCut 判成背景，
    到深色舞台上就是嘴上破了个洞）。只补「不触边且面积小」的；两腿之间那块大楔子不补。"""
    import cv2
    hole = (a < 0.5).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(hole, 4)
    out = a.copy()
    h, w = a.shape
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if x == 0 or y == 0 or x + bw >= w or y + bh >= h:
            continue
        if area <= max_area:
            out[lab == i] = 1.0
    return out


def ring_erase(alpha, cx, cy, r0, r1):
    """把某圆环里的前景判为背景（本图右侧有一圈浅灰被当成前景时用）。"""
    h, w = alpha.shape
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    m = (d >= r0) & (d <= r1)
    alpha[m] = 0.0
    return alpha


def make_cavity(px_w, px_h, meta):
    """口腔层：上齿（有齿缝/有牙龈阴影/嘴角收暗）+ 口腔深处（有纵深）+ 舌。

    v=0 是开口上沿（上唇内侧），v=1 是开口下沿（下唇内侧）。
    打磨要点都是放大 5 倍才看得出来的：
      ① 牙不能等宽等高 —— 中间两颗宽、往两边渐窄，长短也不同；
      ② 牙根要有牙龈阴影、牙缝要有暗线，否则放大像小琴键；
      ③ 口腔深处要**有纵深**（越往里越暗、中间一道洞），不是一块平黑；
      ④ 开口上沿留一条上唇内侧暗影带，否则牙直接贴皮肤 = 一条硬边。
    """
    from PIL import ImageDraw
    import random
    rng = random.Random(20261019)          # 固定种子：每次重建结果一致
    W, H = int(px_w), int(px_h)
    img = Image.new('RGB', (W, H), (10, 4, 6))
    dr = ImageDraw.Draw(img)
    # ── 口腔底：上暖下黑的竖向渐变
    for y in range(H):
        t = y / (H - 1.0)
        c = (int(84 - 66 * t), int(28 - 22 * t), int(30 - 23 * t)) if t < 0.5 else (17, 5, 8)
        dr.line([(0, y), (W, y)], fill=c)
    # ── 纵深：中间一道更深的洞
    cx, cy = W / 2.0, H * 0.62
    for yy in range(H):
        for xx in range(0, W, 2):
            dx = (xx - cx) / (W * 0.42)
            dy = (yy - cy) / (H * 0.40)
            r = min(1.0, (dx * dx + dy * dy) ** 0.5)
            k = 1.0 - 0.72 * (1.0 - r) ** 1.5          # 中心最暗
            R, G, B = img.getpixel((xx, yy))
            dr.line([(xx, yy), (xx + 1, yy)], fill=(int(R * k), int(G * k), int(B * k)))
    # ── 上齿
    n = 6
    total = W * 0.64
    weights = [0.92, 1.06, 1.14, 1.14, 1.06, 0.92]
    wsum = sum(weights)
    gap = max(1, int(W * 0.006))
    usable = total - gap * (n - 1)
    x = (W - total) / 2.0
    gy0, gy1 = H * 0.05, H * 0.25                     # 牙龈线 / 牙尖线（牙只占开口两成，剩下给口腔）
    for k in range(n):
        tw = usable * weights[k] / wsum
        sag = abs(k - (n - 1) / 2.0) * H * 0.010       # 中间略低
        tilt = (0.02 if k < n / 2 else -0.02) * H      # 轻微扇开
        top = gy0 + sag
        bot = gy1 + sag + tilt
        x_l, x_r = x, x + tw
        pin = tw * 0.06                                # 上宽下略窄
        j = rng.randint(-7, 7)
        d = ImageDraw.Draw(img)
        d.polygon([(x_l, top), (x_r, top), (x_r - pin, bot), (x_l + pin, bot)],
                  fill=(176 + j, 167 + j, 158 + j))
        d.line([(x_l, top), (x_r, top)], fill=(120, 66, 64), width=max(1, H // 48))
        # （去掉了每颗牙上那道竖向高光：放大看是一条条白杠，反而假）
        d.line([(x_r, top), (x_r, bot)], fill=(58, 26, 28), width=gap)
        x = x_r + gap
    # ── 牙下暗带
    dr.rectangle([0, int(gy1 + H * 0.01), W, int(H * 0.60)], fill=(11, 3, 5))
    # ── 舌
    lg = (int(W * 0.24), int(H * 0.60), int(W * 0.76), int(H * 1.08))
    dr.ellipse(lg, fill=(150, 76, 86))
    dr.ellipse([lg[0] + W * 0.07, lg[1] + H * 0.06, lg[2] - W * 0.07, lg[3] - H * 0.10],
               fill=(174, 96, 106))
    _hx = [lg[0] + W * 0.17, lg[1] + H * 0.10, lg[2] - W * 0.17, lg[1] + H * 0.10 + H * 0.20]
    if _hx[3] > H - 1:
        _hx[3] = H - 1
    if _hx[3] > _hx[1] + 2:                     # PIL：y1 必须 ≥ y0（浮点取整会撞成相等）
        dr.ellipse(_hx, fill=(190, 112, 122))
    # ── 上唇内侧暗影带
    band = max(1, int(H * 0.10))
    for y in range(band):
        k = 0.10 + 1.15 * (y / float(band)) ** 1.4
        dr.line([(0, y), (W, y)], fill=(int(96 * k), int(34 * k), int(36 * k)))
    # ── 嘴角收暗（中间 1、两侧趋 0）
    px = img.load()
    for yy in range(H):
        for xx in range(W):
            u = abs(xx - (W - 1) / 2.0) / ((W - 1) / 2.0)
            kk = 0.42 + 0.58 * max(0.0, 1.0 - u * u)
            R, G, B = px[xx, yy]
            px[xx, yy] = (int(R * kk), int(G * kk), int(B * kk))
    # ── 不透明区：上沿满，只在左右与下沿收边
    a = np.zeros((H, W), np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    u = (xx - (W - 1) / 2.0) / ((W - 1) / 2.0)
    v = yy / (H - 1.0)
    side = np.clip((1.0 - np.abs(u)) / 0.16, 0.0, 1.0)
    bottom = np.clip((1.0 - np.clip((v - 0.90) / 0.10, 0.0, 1.0)), 0.0, 1.0)
    a = np.clip(side * bottom, 0.0, 1.0) ** 0.7
    out = np.dstack([np.asarray(img, np.float32), a * 255.0])
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), 'RGBA')


def color_bleed(rgb, alpha):
    """把不透明像素的颜色推到透明区（最近的 fg 像素），羽化边才不带背景灰。"""
    from scipy import ndimage
    a = np.clip(alpha, 0, 1)
    if a.shape[0] != rgb.shape[0]:
        a = a[:rgb.shape[0]]
    fg = a >= 0.5
    if not fg.any():
        return rgb
    _, idx = ndimage.distance_transform_edt(~fg, return_indices=True)
    src = idx[0], idx[1]
    out = rgb.copy()
    need = ~fg
    for c in range(3):
        ch = rgb[..., c]
        out[..., c] = np.where(need, ch[src], ch)
    return out


def main():
    crop_bottom = int(arg('--crop-bottom', '1190'))
    thr = float(arg('--thr', '13'))
    im = Image.open(SRC).convert('RGB')
    W, H = im.size
    rgb = np.asarray(im).astype(np.float32)
    alpha, dist = matte(rgb, thr)

    # 影棚地面那道投影：脚下一块暗斑，扣不掉也不该带进舞台 ⇒ 只在最底部裁掉
    if crop_bottom < H:
        alpha[crop_bottom:, :] = 0.0
        rgb = rgb.copy()

    a8 = np.clip(alpha * 255, 0, 255).astype(np.uint8)
    if crop_bottom < H:
        a8 = a8[:crop_bottom]
        rgb = rgb[:crop_bottom]
    # 颜色外扩（color bleed）：把不透明像素的颜色往透明区里推几像素。
    # 不这么做，羽化边上会混进影棚灰 —— 在深色舞台上就是一圈灰描边（"贴纸感"的来源）。
    rgb = color_bleed(rgb, alpha[:a8.shape[0]] if alpha.shape[0] != a8.shape[0] else alpha)
    out = np.dstack([rgb.astype(np.uint8), a8])

    os.makedirs(OUT, exist_ok=True)
    alb = Image.fromarray(out, 'RGBA')
    alb.save(os.path.join(OUT, 'albedo.png'), optimize=True)

    meta = {
        'schema': 'gbt-dh2d/v1',
        'source': 'outputs/ref/character-ref.png',
        'src_size': [W, H],
        'crop_bottom': crop_bottom,
        'size': [W, out.shape[0]],
        'thr': thr,
        'cov': round(float((a8 > 127).mean()), 4),
        'bg_killed': BG_KILLED,
        'anchors': {
            'mouth': [362.0, 170.0],
            'mouth_half_w': 27.0,
            'mouth_half_h': 9.0,
            'lip_line_y': 170.0,
            'chin_y': 197.0,
            'jaw_pivot': [362.0, 150.0],
            'eye_l': [341.0, 126.0],
            'eye_r': [378.5, 123.0],
            'eye_half_w': 11.0,
            'eye_half_h': 6.0,
            'head_c': [362.0, 140.0],
            'neck_y': 206.0,
            'head_top_y': 40.0,
            'shoulder_y': 300.0,
        },
    }
    cav = make_cavity(512, 256, meta)
    cav.save(os.path.join(OUT, 'cavity.png'), optimize=True)

    with open(os.path.join(OUT, 'meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)

    # 内联图集：Electron/file:// 下 <img> 直读同目录 PNG 会污染画布（texImage2D 抛 SecurityError），
    # 上一代 GLB 就是靠 base64 副本兜住的。这里直接只走 data URI，一条路，不搞双源。
    import base64
    def b64(p):
        with open(p, 'rb') as f:
            return 'data:image/png;base64,' + base64.b64encode(f.read()).decode('ascii')
    atlas = {
        'schema': 'gbt-dh2d-atlas/v1',
        'meta': meta,
        'albedo': b64(os.path.join(OUT, 'albedo.png')),
        'cavity': b64(os.path.join(OUT, 'cavity.png')),
    }
    ap = os.path.join(OUT, 'atlas.js')
    with open(ap, 'w', encoding='utf-8') as f:
        f.write('/* GBT小土豆V8 · 2.5D 数字人图集（由 tools/digihuman/dh2d-build.py 生成，勿手改）\n'
                ' * 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属 */\n')
        f.write('window.GBT_DH2D_ATLAS = ')
        json.dump(atlas, f, ensure_ascii=False)
        f.write(';\n')

    # 自检图：抠像结果放到深色底上看（P7 亲眼看之前先有一张能看的图）
    bgc = Image.new('RGBA', alb.size, (10, 12, 16, 255))
    bgc.alpha_composite(alb)
    bgc.convert('RGB').resize((alb.width // 2, alb.height // 2), Image.LANCZOS).save(
        os.path.join(ROOT, 'outputs', 'dh-probe', 'dh2d-albedo-on-dark.png'))

    print('<<<GBT-DH2D-BUILD>>>')
    print(json.dumps({'ok': True, 'out': OUT, 'size': meta['size'], 'cov': meta['cov'],
                      'albedo_bytes': os.path.getsize(os.path.join(OUT, 'albedo.png')),
                      'cavity_bytes': os.path.getsize(os.path.join(OUT, 'cavity.png'))},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()


