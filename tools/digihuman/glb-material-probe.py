# -*- coding: utf-8 -*-
"""glb-material-probe.py —— **只读逆向**：把 GLB 里的材质配方/贴图账读出来（不搬资源）。

规矩（gbt-rea 的四不许）：只读结构、只取**数值与索引**，**不导出、不复用别人的贴图资源**；
每一条读数都要能指回 `materials[i] / textures[i] / images[i]` 的下标，便于复核。

用法：
    py -3.14 tools/digihuman/glb-material-probe.py <a.glb> [b.glb ...]
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")


def read_glb(path: Path):
    b = path.read_bytes()
    if b[:4] != b"glTF":
        raise SystemExit("不是 GLB：%s" % path)
    off = 12
    js, bin_len = None, 0
    while off < len(b):
        ln, typ = struct.unpack_from("<II", b, off)
        off += 8
        if typ == 0x4E4F534A:
            js = b[off:off + ln]
        elif typ == 0x004E4942:
            bin_len = ln
        off += ln
    return json.loads(js.decode("utf-8")), bin_len, len(b)


def probe(path: Path) -> dict:
    g, bin_len, total = read_glb(path)
    mats = []
    for i, m in enumerate(g.get("materials") or []):
        pbr = m.get("pbrMetallicRoughness") or {}
        row = {
            "idx": i, "name": m.get("name"),
            "baseColorFactor": pbr.get("baseColorFactor"),
            "metallicFactor": pbr.get("metallicFactor"),
            "roughnessFactor": pbr.get("roughnessFactor"),
            "baseColorTexture": (pbr.get("baseColorTexture") or {}).get("index"),
            "metallicRoughnessTexture": (pbr.get("metallicRoughnessTexture") or {}).get("index"),
            "normalTexture": (m.get("normalTexture") or {}).get("index"),
            "emissiveTexture": (m.get("emissiveTexture") or {}).get("index"),
            "doubleSided": m.get("doubleSided", False),
            "alphaMode": m.get("alphaMode", "OPAQUE"),
            # 常见扩展（KHR_materials_*）也读出来，别漏掉 SSS/清漆这类
            "extensions": sorted((m.get("extensions") or {}).keys()),
        }
        mats.append(row)
    imgs = []
    for i, im in enumerate(g.get("images") or []):
        imgs.append({"idx": i, "name": im.get("name"), "mimeType": im.get("mimeType"),
                     "bufferView": im.get("bufferView"), "uri": (im.get("uri") or "")[:40]})
    skins = g.get("skins") or []
    return {
        "file": str(path), "bytes": total, "bin_chunk": bin_len,
        "meshes": len(g.get("meshes") or []), "skins": len(skins),
        "joints": len(skins[0].get("joints") or []) if skins else 0,
        "materials": mats, "images": imgs,
        "textures": len(g.get("textures") or []),
        "samplers": len(g.get("samplers") or []),
        "extensionsUsed": g.get("extensionsUsed") or [],
    }


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(__doc__)
        return 2
    out = []
    for a in args:
        p = Path(a)
        if not p.is_file():
            print("读不到：%s" % p)
            continue
        r = probe(p)
        out.append(r)
        print("═══ %s ═══" % p.name)
        print("  字节 %d · meshes %d · skins %d · joints %d · textures %d · images %d"
              % (r["bytes"], r["meshes"], r["skins"], r["joints"], r["textures"], len(r["images"])))
        for m in r["materials"]:
            print("  materials[%d] %-18s base=%s metal=%s rough=%s"
                  % (m["idx"], m["name"], m["baseColorFactor"], m["metallicFactor"], m["roughnessFactor"]))
            tex = {k: v for k, v in m.items() if k.endswith("Texture") and v is not None}
            if tex:
                print("     贴图：%s" % tex)
            if m["extensions"]:
                print("     扩展：%s" % m["extensions"])
        if r["images"]:
            print("  images：%s" % r["images"])
        if r["extensionsUsed"]:
            print("  extensionsUsed：%s" % r["extensionsUsed"])
    print()
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
