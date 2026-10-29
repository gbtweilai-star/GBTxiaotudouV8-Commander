# -*- coding: utf-8 -*-
"""用 pymeshlab 的 **带纹理/缝保护的 QEM** 简化头部（正是我们自写近似做不好的那一层）。
用法：python tools/codex-scripts/pml-decimate.py <in.glb> <out.glb> <target_faces>"""
import pathlib
import sys
import pymeshlab as ml

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
SRC = sys.argv[1] if len(sys.argv) > 1 else str(WS / "holo_pet/assets/digital-human/raw/rig/part-head.glb")
OUT = sys.argv[2] if len(sys.argv) > 2 else str(WS / "holo_pet/assets/digital-human/raw/rig/head-pml-low.glb")
TARGET = int(sys.argv[3]) if len(sys.argv) > 3 else 75000

ms = ml.MeshSet()
ms.load_new_mesh(SRC)
print("载入：面", ms.current_mesh().face_number(), "顶点", ms.current_mesh().vertex_number())
ms.meshing_decimation_quadric_edge_collapse_with_texture(
    targetfacenum=TARGET,
    preserveboundary=True,        # 保边界
    preservenormal=True,
    planarquadric=True,
    selected=False,
)
m = ms.current_mesh()
print("简化后：面", m.face_number(), "顶点", m.vertex_number(), "· 有纹理坐标:", m.has_wedge_tex_coord())
ms.save_current_mesh(OUT, save_textures=True, save_vertex_color=False, save_wedge_texcoord=True)
p = pathlib.Path(OUT)
print(f"输出 {p.name} · {p.stat().st_size/1024/1024:.2f} MB")
