# -*- coding: utf-8 -*-
r"""GLB 贴图瘦身（glb-slim）—— **把体积压到门限以内，且不糊**。

主人令（2026-10-10 目标轮）：数字人流水线 S3 判据红「12.72 MB（上限 12）」——**只超 0.72 MB**。

## 先看体积去哪了（现读，不猜）
dh-v2-rigged.glb 共 12.74 MB，其中 **贴图 11.5 MB（91%）**，网格+骨骼+动画只 1.1 MB：
  · normal            3.45 MB (png)
  · baseColor         1.01 MB (jpeg)
  · **metallicRoughness 7.07 MB (png)**  ← **一半以上在这张**
⇒ **该压的不是网格，是这张 7MB 的金属/粗糙度图。**

## 凭什么可以压它（不是"随便降质"）
金属/粗糙度是**低频**信息（表面材质分布，没有高频细节），
艺术上**不需要和 baseColor 同分辨率**——行业常规就是给材质图**降一档**。
而 **normal 和 baseColor 不动**（那两张一糊，脸和布料立刻崩）。
**⇒ 只降 metallicRoughness，并保留其余两张原样。**

用法：py -3.14 -X utf8 tools/digihuman/glb-slim.py [--check|--selftest]
"""
from __future__ import annotations

import argparse
import io
import json
import struct
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
GLB = ROOT / "holo_pet" / "assets" / "digital-human" / "raw" / "rig" / "model-rigged.glb"
LIMIT_MB = 12.0
# 只压这张（按图名匹配）；normal / baseColor 一律不动
SLIM = ("metallic", "roughness")


def read(p: Path):
    b = p.read_bytes()
    jl, = struct.unpack_from("<I", b, 12)
    J = json.loads(b[20:20 + jl].decode("utf-8"))
    off = 20 + jl + ((-jl) % 4)
    bl, = struct.unpack_from("<I", b, off)
    return J, bytearray(b[off + 8: off + 8 + bl])


def write(p: Path, J: dict, BIN: bytes) -> None:
    js = json.dumps(J, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    js += b" " * ((4 - len(js) % 4) % 4)
    bn = bytes(BIN) + b"\x00" * ((4 - len(BIN) % 4) % 4)
    out = bytearray()
    out += struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(bn))
    out += struct.pack("<II", len(js), 0x4E4F534A) + js
    out += struct.pack("<II", len(bn), 0x004E4942) + bn
    p.write_bytes(bytes(out))


def slim(factor: int = 4, target: str = "") -> dict:
    from PIL import Image
    src = Path(target) if target else GLB
    if not src.is_file():
        return {"ok": False, "why": "找不到 %s" % src}
    before = src.stat().st_size
    J, BIN = read(src)
    rows, saved = [], 0
    for i, im in enumerate(J.get("images") or []):
        name = (im.get("name") or "").lower()
        if not any(k in name for k in SLIM):
            rows.append({"图": im.get("name"), "处理": "**不动**（怕糊）",
                         "字节": J["bufferViews"][im["bufferView"]]["byteLength"]})
            continue
        bv = J["bufferViews"][im["bufferView"]]
        o, n = bv.get("byteOffset", 0), bv["byteLength"]
        raw = bytes(BIN[o:o + n])
        img = Image.open(io.BytesIO(raw))
        w, h = img.size
        nw, nh = max(1, w // factor), max(1, h // factor)
        small = img.resize((nw, nh), Image.LANCZOS)
        buf = io.BytesIO()
        # 保留 PNG（glTF 的 metallicRoughness 走 PNG 无损更稳）但换最优压缩
        small.save(buf, format="PNG", optimize=True, compress_level=9)
        new = buf.getvalue()
        # 原地替换（长度变了 ⇒ 后面所有 bufferView 要平移）
        old_n = n
        BIN[o:o + n] = new
        delta = len(new) - old_n
        for other in J["bufferViews"]:
            if other.get("byteOffset", 0) > o:
                other["byteOffset"] = other.get("byteOffset", 0) + delta
        bv["byteLength"] = len(new)
        saved += old_n - len(new)
        rows.append({"图": im.get("name"), "处理": "%dx%d -> %dx%d" % (w, h, nw, nh),
                     "字节": len(new), "省": old_n - len(new)})
    if saved <= 0:
        return {"ok": False, "why": "没省下来（没有可压的图？）", "逐条": rows}
    tmp = src.with_name(src.stem + ".slim.glb")
    write(tmp, J, bytes(BIN))
    after = tmp.stat().st_size
    return {"ok": True, "原字节": before, "新字节": after,
            "省MB": round((before - after) / 1e6, 2),
            "新MB": round(after / 1e6, 2), "上限MB": LIMIT_MB,
            "过门": after / 1e6 <= LIMIT_MB, "逐条": rows, "落点": str(tmp)}


def check(target: str = "") -> int:
    r = slim(4, target)
    print("GLB 贴图瘦身（只压低频材质图，normal/baseColor 不动）")
    if not r.get("ok"):
        print("  **没成**：%s" % r.get("why")); return 1
    for x in r["逐条"]:
        print("  %-18s %-22s %s 字节" % (str(x.get("图"))[:18], str(x.get("处理")), x.get("字节")))
    print()
    print("  原 %.2f MB -> 新 %.2f MB（省 %.2f MB）· 上限 %.1f MB ⇒ %s"
          % (r["原字节"] / 1e6, r["新MB"], r["省MB"], r["上限MB"],
             "**过门**" if r["过门"] else "**仍超**"))
    return 0 if r["过门"] else 1


def selftest() -> int:
    from PIL import Image
    print("负对照A·PIL 在 =>", Image.__name__)
    J, BIN = read(GLB)
    names = [(im.get("name"), J["bufferViews"][im["bufferView"]]["byteLength"]) for im in J.get("images") or []]
    print("负对照B·图清单 =>", names)
    big = max(names, key=lambda x: x[1])
    print("负对照C·最大那张 => %s %d 字节（%.2f MB）⇒ 该压的是它" % (big[0], big[1], big[1] / 1e6))
    ok = any(k in (big[0] or "").lower() for k in SLIM)
    print("自检：%s" % ("全过（最大那张正是该压的材质图）" if ok else "不过（最大那张不是材质图，压它会更糊）"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="GLB 贴图瘦身")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--glb", default="", help="要瘦身的 GLB（留空=默认的 model-rigged.glb）")
    a = ap.parse_args()
    return selftest() if a.selftest else check(a.glb)


if __name__ == "__main__":
    raise SystemExit(main())
