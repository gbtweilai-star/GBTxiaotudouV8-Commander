# -*- coding: utf-8 -*-
"""皮肤微细节层（v7）：给**只在皮肤掩膜内**加"毛孔级"细节，治"特写像塑料"。

为什么这么做（不用 AI 超分）：
  · 现有 color 贴图 4096²，皮肤区大约 1 texel ≈ 1 屏幕像素（半身档）—— 分辨率够，
    **缺的是"细节本身"**：纹理由 Tripo 烘出来，皮肤是一块近乎均匀的色斑，没有毛孔/微起伏。
  · 所以用**程序化细节**补：多层噪声做色斑（mottling）+ 稀疏暗点（毛孔）+ 法线微起伏（凹凸）。
    这是游戏/影视里标准的 "detail map" 做法，不改几何、不改绑定、不改动作。

只动 skin 掩膜（色相 0–40° / 有彩度 / 不黑不白），衣领金色饰边、头发、皮衣一律不碰。
产物：holo_pet_w3/voice-theater/assets/dh-v7-detail.glb（在役件只有一份）
用法：python tools/digihuman/dh-skin-detail.py            # 只报
      python tools/digihuman/dh-skin-detail.py --apply    # 写盘
"""
import argparse
import io
import json
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ASSET_DIR = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\holo_pet_w3\voice-theater\assets"
SRC = os.path.join(ASSET_DIR, "dh-v6-skin.glb")
OUT = os.path.join(ASSET_DIR, "dh-v7-detail.glb")
EVID = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\state\hd\tex"

ap = argparse.ArgumentParser()
ap.add_argument("--apply", action="store_true")
ap.add_argument("--color-amp", type=float, default=0.075, help="色斑幅度（相对亮度）")
ap.add_argument("--pore-amp", type=float, default=0.13, help="毛孔压暗幅度")
ap.add_argument("--pore-density", type=float, default=0.012, help="毛孔像素占比")
ap.add_argument("--normal-strength", type=float, default=0.55, help="法线细节混合强度 0..1")
ap.add_argument("--normal-fmt", default="jpeg", choices=["jpeg", "png"], help="法线贴图编码：jpeg 保体积，png 无损但会涨到 10MB+")
ap.add_argument("--seed", type=int, default=20261021)
a = ap.parse_args()


def parse_glb(raw):
    magic, ver, length = struct.unpack_from("<III", raw, 0)
    off, js, bn = 12, None, None
    while off < len(raw):
        clen, ctype = struct.unpack_from("<II", raw, off)
        body = raw[off + 8: off + 8 + clen]
        if ctype == 0x4E4F534A:
            js = body
        elif ctype == 0x004E4942:
            bn = body
        off += 8 + clen + ((4 - clen % 4) % 4 if clen % 4 else 0)
    return json.loads(js.decode("utf-8")), bn


def img_bytes(g, bn, idx):
    im = g["images"][idx]
    bv = g["bufferViews"][im["bufferView"]]
    o = bv.get("byteOffset", 0)
    return bn[o: o + bv["byteLength"]], im["bufferView"]


rng = np.random.default_rng(a.seed)


def value_noise(size, cells, rng):
    """可无缝平铺的值噪声：低分辨率随机网格 + 双三次放大（用 PIL 平滑），再平铺裁回。"""
    g = rng.random((cells + 1, cells + 1)).astype(np.float32)
    g[-1, :] = g[0, :]
    g[:, -1] = g[:, 0]
    im = Image.fromarray((g * 255).astype(np.uint8)).resize((size, size), Image.BICUBIC)
    return np.asarray(im).astype(np.float32) / 255.0


def fbm(size, octaves, base_cells, rng, persistence=0.55):
    out = np.zeros((size, size), np.float32)
    amp, tot, cells = 1.0, 0.0, base_cells
    for _ in range(octaves):
        out += amp * value_noise(size, int(cells), rng)
        tot += amp
        amp *= persistence
        cells *= 2
    return out / max(tot, 1e-6)


def main():
    raw = open(SRC, "rb").read()
    g, bn = parse_glb(raw)
    print("[GLB] %s  %d 字节" % (os.path.basename(SRC), len(raw)))

    # 找 color 与 normal 贴图
    mi = g["materials"][0]
    pbr = mi["pbrMetallicRoughness"]
    cimg = g["textures"][pbr["baseColorTexture"]["index"]]["source"]
    nimg = g["textures"][mi["normalTexture"]["index"]]["source"]
    cbytes, cbv = img_bytes(g, bn, cimg)
    nbytes, nbv = img_bytes(g, bn, nimg)
    color = Image.open(io.BytesIO(cbytes)).convert("RGB")
    normal = Image.open(io.BytesIO(nbytes)).convert("RGB")
    W, H = color.size
    print("[贴图] color %dx%d (%d B) · normal %dx%d (%d B)" % (color.size[0], color.size[1], len(cbytes),
                                                             normal.size[0], normal.size[1], len(nbytes)))

    # ── 皮肤掩膜（与 dh-grade-texture.py 同一口径）──────────────────────────────
    arr = np.asarray(color).astype(np.float32) / 255.0
    r, gg, b = arr[..., 0], arr[..., 1], arr[..., 2]
    mx, mn = arr.max(axis=2), arr.min(axis=2)
    v = mx
    s = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0)
    d = np.maximum(mx - mn, 1e-6)
    h = np.zeros_like(mx)
    m = (mx == r)
    h[m] = (60 * ((gg - b) / d) % 360)[m]
    m = (mx == gg) & (mx != r)
    h[m] = (60 * ((b - r) / d) + 120)[m]
    m = (mx == b) & (mx != r) & (mx != gg)
    h[m] = (60 * ((r - gg) / d) + 240)[m]
    mask = (h >= 0) & (h <= 40) & (s > 0.08) & (s < 0.55) & (v > 0.25) & (v < 0.96)
    print("[掩膜] 皮肤像素 %.2f%%（%d px）" % (100 * mask.mean(), int(mask.sum())))
    fk = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))
    feather = (np.asarray(fk).astype(np.float32) / 255.0)[..., None]

    # ── ① 色斑（低频，多倍频）+ 毛孔（高频稀疏暗点）──────────────────────────────
    mottle = fbm(W, 6, 24, rng, 0.6)          # 粗糙的肤色不均
    mottle = (mottle - mottle.mean()) / max(mottle.std(), 1e-6)     # 归一化到 ~N(0,1)
    pores = fbm(W, 3, 512, rng, 0.75)          # 高频（细颗粒）
    speck = (pores > np.quantile(pores, 1.0 - a.pore_density)).astype(np.float32)
    speck = np.asarray(Image.fromarray((speck * 255).astype(np.uint8))
                       .filter(ImageFilter.GaussianBlur(0.6))).astype(np.float32) / 255.0

    col = arr.copy()
    shade = 1.0 + a.color_amp * 0.5 * mottle - a.pore_amp * speck
    shade = shade[..., None]
    # 只在掩膜内生效（羽化边界）
    col = arr * (1 - feather) + (arr * shade) * feather
    col = np.clip(col, 0, 1)
    color_out = Image.fromarray((col * 255).round().astype(np.uint8))

    # ── ② 法线细节：从"高频高度场"生成切线空间法线，再与原法线混合 ────────────────
    hgt = fbm(W, 4, 640, rng, 0.7) * 0.6 + speck * 0.4
    gy, gx = np.gradient(hgt)
    strength = 6.0
    nx, ny = -gx * strength, -gy * strength
    nz = np.ones_like(nx)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    n_det = np.stack([nx / ln, ny / ln, nz / ln], axis=-1)

    nrm = np.asarray(normal).astype(np.float32) / 255.0 * 2.0 - 1.0
    n_old = nrm / np.maximum(np.linalg.norm(nrm, axis=2, keepdims=True), 1e-6)
    k = a.normal_strength * feather
    n_mix = n_old * (1 - k) + n_det * k
    n_mix /= np.maximum(np.linalg.norm(n_mix, axis=2, keepdims=True), 1e-6)
    n_out = Image.fromarray((((n_mix + 1) * 0.5) * 255).round().clip(0, 255).astype(np.uint8))

    # 细节量读数：全局 std 会被"肤色本身的大范围明暗"淹没（实测只 +0.3），
    # 所以量**高频能量**（拉普拉斯响应，只在掩膜内）—— 这才是"有没有毛孔级细节"的判据。
    def stat(img, name):
        ar = np.asarray(img).astype(np.float32).mean(axis=2)
        lap = (ar[1:-1, 1:-1] * 4 - ar[:-2, 1:-1] - ar[2:, 1:-1] - ar[1:-1, :-2] - ar[1:-1, 2:])
        mk = mask[1:-1, 1:-1]
        hf = float(np.abs(lap[mk]).mean())
        v_ = np.asarray(img).astype(np.float32)[mask]
        print("  %-6s 掩膜内 std=%.1f · 高频(拉普拉斯)%.2f" % (name, v_.std(), hf))
        return hf

    print("[细节量] color:")
    s0 = stat(color, "原")
    s1 = stat(color_out, "新")
    print("[细节量] normal:")
    n0 = stat(normal, "原")
    n1 = stat(n_out, "新")
    print("[增量] 高频能量 color x%.2f · normal x%.2f" % (s1 / max(s0, 1e-6), n1 / max(n0, 1e-6)))

    buf_c, buf_n = io.BytesIO(), io.BytesIO()
    color_out.save(buf_c, format="JPEG", quality=94, subsampling=0)
    if a.normal_fmt == "jpeg":
        n_out.save(buf_n, format="JPEG", quality=95, subsampling=0)
    else:
        n_out.save(buf_n, format="PNG", optimize=True)
    nc, nn = buf_c.getvalue(), buf_n.getvalue()
    print("[重编码] color %d → %d · normal %d → %d" % (len(cbytes), len(nc), len(nbytes), len(nn)))

    if not a.apply:
        print("[写盘] 跳过（没给 --apply）")
        return

    os.makedirs(EVID, exist_ok=True)
    color_out.save(os.path.join(EVID, "v7-color.jpg"), quality=94, subsampling=0)
    n_out.save(os.path.join(EVID, "v7-normal." + ("jpg" if a.normal_fmt == "jpeg" else "png")))

    # ── 重封 GLB：替换两块 bufferView，其余按原偏移顺序原样搬 ─────────────────────
    # 🔴 mimeType 必须跟着编码一起改：上一版把 PNG 字节换成 JPEG 却没改 mimeType，
    # GLB 里写着 image/png 而字节是 FFD8 开头 —— 浏览器靠嗅探能读，但这是**账不实**。
    repl = {cbv: nc, nbv: nn}
    g["images"][cimg]["mimeType"] = "image/jpeg"
    g["images"][nimg]["mimeType"] = "image/jpeg" if a.normal_fmt == "jpeg" else "image/png"
    bvs = g["bufferViews"]
    order = sorted(range(len(bvs)), key=lambda i: bvs[i].get("byteOffset", 0))
    new_bin = bytearray()
    for i in order:
        blk = bvs[i]
        data = repl.get(i)
        if data is None:
            o0 = blk.get("byteOffset", 0)
            data = bn[o0: o0 + blk["byteLength"]]
        while len(new_bin) % 4:
            new_bin.append(0)
        blk["byteOffset"] = len(new_bin)
        blk["byteLength"] = len(data)
        new_bin.extend(data)
    while len(new_bin) % 4:
        new_bin.append(0)
    g["buffers"][0]["byteLength"] = len(new_bin)

    js = json.dumps(g, separators=(",", ":")).encode("utf-8")
    while len(js) % 4:
        js += b" "
    out = bytearray()
    out.extend(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(new_bin)))
    out.extend(struct.pack("<II", len(js), 0x4E4F534A))
    out.extend(js)
    out.extend(struct.pack("<II", len(new_bin), 0x004E4942))
    out.extend(new_bin)
    open(OUT, "wb").write(out)
    import hashlib
    print("[导出] %s  %d 字节 · sha16 %s" % (OUT, len(out), hashlib.sha256(out).hexdigest()[:16]))


main()
