# -*- coding: utf-8 -*-
# 🔴 GBT 加固 2026-10-25：原来写死 Windows 绝对路径 `C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8`，
#    Linux/手机 上拼出来的路径不存在。改成按本文件位置推仓根，换机器零改动。
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
"""把嫁接件拆成「身体」与「头」两个 GLB（分区减面的前提）。
身体件 = 原身体 primitive（含 4K 材质）；头件 = 嫁接头 primitive（含胸像 2K 材质）。"""
import json
import pathlib
import struct

WS = pathlib.Path(_GBT_ROOT)
DH = WS / "holo_pet/assets/digital-human"
SRC = DH / "raw/rig/model-rigged-4k-graft.glb"
OUT_BODY = DH / "raw/rig/part-body.glb"
OUT_HEAD = DH / "raw/rig/part-head.glb"

raw = SRC.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = bytes(raw[off + 8: off + 8 + bl])
print(f"源 {SRC.name} · {len(raw)/1024/1024:.2f} MB · primitive {len(J['meshes'][0]['primitives'])}")


def write_sub(prim_index, path):
    J2 = json.loads(json.dumps(J))
    pr = J2["meshes"][0]["primitives"][prim_index]
    J2["meshes"][0]["primitives"] = [pr]
    # 只保留该 primitive 用到的 bufferView（保守：全部保留也无害，但体积会翻倍 ⇒ 精确裁剪）
    used_bv = set()
    acc_ids = list(pr["attributes"].values()) + ([pr["indices"]] if "indices" in pr else [])
    # 别漏 skin 的 inverseBindMatrices（实测 KeyError: 3 就是漏了它）
    _sk = (J2.get("skins") or [{}])[0]
    if "inverseBindMatrices" in _sk:
        acc_ids.append(_sk["inverseBindMatrices"])
    for ai in acc_ids:
        a = J2["accessors"][ai]
        if "bufferView" in a:
            used_bv.add(a["bufferView"])
    mat = J2["materials"][pr["material"]]
    pbr = mat.get("pbrMetallicRoughness", {})
    tex_idx = []
    for slot in ("baseColorTexture", "metallicRoughnessTexture"):
        if slot in pbr:
            tex_idx.append(pbr[slot]["index"])
    for slot in ("normalTexture", "occlusionTexture", "emissiveTexture"):
        if slot in mat:
            tex_idx.append(mat[slot]["index"])
    img_idx = [J2["textures"][t]["source"] for t in tex_idx]
    for ii in img_idx:
        used_bv.add(J2["images"][ii]["bufferView"])
    for im in J2["images"]:                       # v3：图片全留（避免另一件的图片重映射越界）
        used_bv.add(im["bufferView"])
    new_bin = bytearray()
    remap = {}
    for i, v in enumerate(J2["bufferViews"]):
        if i not in used_bv:
            continue
        while len(new_bin) % 4:
            new_bin.append(0)
        o = v.get("byteOffset", 0)
        data = BIN[o:o + v["byteLength"]]
        remap[i] = len(J2["bufferViews"]) if False else None
        v["byteOffset"] = len(new_bin)
        new_bin.extend(data)
    # 重建 bufferViews（只留用到的）+ **只保留本件用到的 accessor 并重编号**
    kept = [v for i, v in enumerate(J2["bufferViews"]) if i in used_bv]
    old2new = {old: new for new, old in enumerate(sorted(used_bv))}
    keep_acc = sorted(set(acc_ids))
    acc2new = {o: n for n, o in enumerate(keep_acc)}
    J2["accessors"] = [J2["accessors"][i] for i in keep_acc]
    for a in J2["accessors"]:
        if "bufferView" in a:
            a["bufferView"] = old2new[a["bufferView"]]
    J2["bufferViews"] = kept
    for k, v in list(pr["attributes"].items()):
        pr["attributes"][k] = acc2new[v]
    if "indices" in pr:
        pr["indices"] = acc2new[pr["indices"]]
    if "inverseBindMatrices" in _sk:
        _sk["inverseBindMatrices"] = acc2new[_sk["inverseBindMatrices"]]
    for im in J2["images"]:
        if "bufferView" in im:
            im["bufferView"] = old2new.get(im["bufferView"], im["bufferView"])
    J2["buffers"][0]["byteLength"] = len(new_bin)
    while len(new_bin) % 4:
        new_bin.append(0)
    js = json.dumps(J2, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    while len(js) % 4:
        js += b" "
    path.write_bytes(b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(new_bin))
                     + struct.pack("<I", len(js)) + b"JSON" + js
                     + struct.pack("<I", len(new_bin)) + b"BIN\x00" + bytes(new_bin))
    print(f"  {path.name} · {path.stat().st_size/1024/1024:.2f} MB · 材质 {mat.get('name')}")


write_sub(0, OUT_BODY)
write_sub(1, OUT_HEAD)
