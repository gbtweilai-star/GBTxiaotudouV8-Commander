# -*- coding: utf-8 -*-
"""校验 GLB 引用完整性（越界/缺字段）。加载器报怪错时先用它，别猜。
用法: python tools/codex-scripts/validate-glb.py <文件.glb>"""
import json
import pathlib
import struct
import sys
p = pathlib.Path(sys.argv[1])
raw = p.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20+jl].decode("utf-8"))


def n(k):
    return len(J.get(k) or [])


bad = []
for i, a in enumerate(J.get("accessors") or []):
    if "bufferView" in a and not (0 <= a["bufferView"] < n("bufferViews")):
        bad.append(f"accessor[{i}].bufferView={a['bufferView']} 越界")
for i, m in enumerate(J.get("meshes") or []):
    for k, pr in enumerate(m.get("primitives") or []):
        for key, v in (pr.get("attributes") or {}).items():
            if not (0 <= v < n("accessors")):
                bad.append(f"mesh[{i}].prim[{k}].{key}={v} 越界")
        if "indices" in pr and not (0 <= pr["indices"] < n("accessors")):
            bad.append(f"mesh[{i}].prim[{k}].indices 越界")
for i, s in enumerate(J.get("skins") or []):
    for j in s.get("joints") or []:
        if not (0 <= j < n("nodes")):
            bad.append(f"skin[{i}].joints 含越界节点 {j}")
for i, nd in enumerate(J.get("nodes") or []):
    if "skin" in nd and not (0 <= nd["skin"] < n("skins")):
        bad.append(f"node[{i}].skin={nd['skin']} 越界（skins={n('skins')}）")
    for c in nd.get("children") or []:
        if not (0 <= c < n("nodes")):
            bad.append(f"node[{i}].children 含越界 {c}")
print(f"{p.name}: accessors={n('accessors')} bufferViews={n('bufferViews')} nodes={n('nodes')} skins={n('skins')}")
print("引用检查:", "全部合法 ✓" if not bad else "发现问题 ↓")
for b in bad[:12]:
    print("  ✗", b)
raise SystemExit(1 if bad else 0)
