# -*- coding: utf-8 -*-
"""本地自动绑骨 · 第 1 步：从网格**量出**人形骨架（不联网、不花积分、不猜轴）

输入：低模 GLB（本仓现有 28382 顶点级；**不要求 T-pose**）
输出：skeleton.json（关节名/层级/坐标）+ 剪影叠加验收图

🔴 2026-09-25 改造（实测教训，本文件的核心）：
   旧稿的四肢定位是"按**臂轴跨度**分段找肩/肘/腕"。那只在 **T-pose** 成立。
   Owner 本轮给的样板是**自然站姿（手垂在身侧）**，旧法把四个手臂关节**全挤在肩高**
   （实测 y≈0.33 · x 从 0.021 排到 0.087），而真手在髋侧 y≈-0.1
   —— 也就是说：**骨架画出来好看，但手臂链整条是假的**，蒙皮必然把手臂糊在肩上。
   现在改成 **沿表面测地线追踪**（Dijkstra）：
     · 从躯干种子点出发，取"该侧 + 该高度窗内测地最远"的顶点当**肢端**（手 / 脚）；
     · 回溯最短路径，按路径长度比例放关节（肩/肘/腕、髋/膝/踝/趾）。
   手垂着、平伸、叉腰都不影响 —— 因为它跟的是**表面连通**，不是坐标方向。
⚠️ 高度比例（FR 表）仍用于**躯干**：那一段本来就靠解剖比例，站姿不影响。
"""
import heapq
import json
import pathlib
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw

WS = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
GLB = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else WS / "holo_pet/assets/digital-human/raw/avatarmesh/avatar-lowpoly.glb"
OUT_JSON = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else WS / "holo_pet/assets/digital-human/raw/rig/skeleton.json"
OUT_IMG = WS / "render/绑骨-骨架落在实体上.png"
OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

raw = GLB.read_bytes()
jl, = struct.unpack_from("<I", raw, 12)
J = json.loads(raw[20:20 + jl].decode("utf-8"))
off = 20 + jl + ((-jl) % 4)
bl, = struct.unpack_from("<I", raw, off)
BIN = raw[off + 8: off + 8 + bl]


def acc(i, comps):
    a = J["accessors"][i]
    bv = J["bufferViews"][a["bufferView"]]
    dt = {5126: np.float32, 5125: np.uint32, 5123: np.uint16}[a["componentType"]]
    return np.frombuffer(BIN, dt, a["count"] * comps,
                         bv.get("byteOffset", 0)).reshape(a["count"], comps).astype(np.float64)


pr0 = J["meshes"][0]["primitives"][0]
P = acc(pr0["attributes"]["POSITION"], 3)
IDX = acc(pr0["indices"], 1).astype(np.int64).reshape(-1, 3)
print(f"网格顶点 {len(P)} · 三角 {len(IDX)}")

# ① 定轴：高度=Y；臂轴=水平方向跨度大者；深度轴=另一个
ext = P.max(axis=0) - P.min(axis=0)
axis_h = 1
axis_arm = 0 if ext[0] >= ext[2] else 2
axis_dep = 2 if axis_arm == 0 else 0
AX = {"h": axis_h, "arm": axis_arm, "dep": axis_dep}
y_top, y_bot = P[:, 1].max(), P[:, 1].min()
H = y_top - y_bot
print(f"高度 {H:.3f} · 臂轴 = {'XYZ'[axis_arm]}（跨度 {ext[axis_arm]:.3f}）· "
      f"深度轴 = {'XYZ'[axis_dep]}（跨度 {ext[axis_dep]:.3f}）")

# ② 表面邻接（CSR）：测地线要它
n = len(P)
# 🔴 必须先**按位置焊接**：本网格是逐顶点 UV 口径，UV 缝两侧是**重复顶点**，
#    直接拿顶点索引建图，表面会沿缝断成好几个岛 —— 实测那样跑出来"胸->最远 = inf"、
#    回溯路径只有 1 个点（等于根本没走到手）。焊接后图才连成一张完整的皮。
key = np.round(P / 1e-5).astype(np.int64)
uniq_pos, gid = np.unique(key, axis=0, return_inverse=True)
GN = len(uniq_pos)
GP = np.zeros((GN, 3))
for d in range(3):
    GP[:, d] = np.bincount(gid, weights=P[:, d], minlength=GN) / np.bincount(gid, minlength=GN)
GIDX = gid[IDX]
print(f"位置焊接：顶点 {n} → 焊点 {GN}（缝上重复顶点 {n - GN} 个已并）")

# 每个"面角"给该焊点贡献 **2 条**有向出边（同三角的另外两个角）⇒ 出度 = 面角数 × 2
deg = np.bincount(GIDX.reshape(-1), minlength=GN) * 2
ptr = np.concatenate([[0], np.cumsum(deg)])
fill = ptr.copy()
adj = np.zeros(ptr[-1], np.int64)
for a, b, c in GIDX:
    for u, v in ((a, b), (a, c), (b, c), (b, a), (c, a), (c, b)):
        adj[fill[u]] = v
        fill[u] += 1
print(f"表面邻接：边 {len(adj)}（平均度 {len(adj)/GN:.1f}）")


def dijkstra(seed):
    """焊点图上的表面测地距离（欧氏边长）。返回 (dist, prev)。"""
    dist = np.full(GN, np.inf)
    prev = np.full(GN, -1, np.int64)
    dist[seed] = 0.0
    pq = [(0.0, seed)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for k in range(ptr[u], ptr[u + 1]):
            v = adj[k]
            nd = d + float(np.linalg.norm(GP[v] - GP[u]))
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    return dist, prev


def trace(prev, end):
    out, cur = [], end
    while cur != -1:
        out.append(cur)
        cur = int(prev[cur])
    return out[::-1]


# ③ 躯干：按标准人形比例（站姿不影响这一段）
# 🔴 `head` 这一条是 2026-09-25 补的：旧稿把 Head 关节放在**头顶质心**（y=0.485），
#    于是 Head 骨段只剩 0.485→0.5 一小截 —— 蒙皮按"到骨段距离"分权时，
#    **整张脸都离 Neck 段更近**（Neck 段 0.386→0.485 正好盖住脸），
#    实测主导骨统计：Neck 4756 顶点 / **Head 只有 300 顶点**。后果是"头一转，脸不跟"。
#    正确口径：Head 关节在**颅底**（头顶往下约 0.095H），HeadTop 才在 0.5。
FR = dict(head_top=0.00, head=0.095, neck=0.135, shoulder=0.175, chest=0.28, waist=0.40,
          hip=0.52, knee=0.755, ankle=0.945, foot=0.995)


def at_height(frac, tol=0.02):
    y = y_top - frac * H
    return P[np.abs(P[:, 1] - y) < tol * H]


def centroid(pts):
    return pts.mean(axis=0) if len(pts) else None


def pick(c, fallback):
    return c if c is not None else fallback


J3 = {}
torso = pick(centroid(at_height(0.30)), P.mean(axis=0))
J3["Hips"] = list(pick(centroid(at_height(FR["hip"])), torso))
J3["Spine"] = list(pick(centroid(at_height(FR["waist"])), torso))
J3["Spine1"] = list(pick(centroid(at_height(FR["chest"])), torso))
J3["Neck"] = list(pick(centroid(at_height(FR["neck"])), torso))
# Head 在**颅底**（不是头顶）：这样 Head 骨段从颅底一直盖到头顶，脸才归 Head
J3["Head"] = list(pick(centroid(at_height(FR["head"])),
                       centroid(P[P[:, 1] > y_top - 0.12 * H])))
J3["HeadTop"] = [float(J3["Head"][0]), float(y_top), float(J3["Head"][2])]

# ④ 四肢：测地线追踪（全部在**焊点图**上做）


def nearest_weld(target):
    return int(np.argmin(((GP - target) ** 2).sum(axis=1)))


y_shoulder = y_top - FR["shoulder"] * H
y_hip = J3["Hips"][1]
below = GP[np.abs(GP[:, 1] - (y_top - 0.36 * H)) < 0.02 * H]
torso_half = float(np.abs(below[:, axis_arm]).max()) if len(below) else 0.1 * H

seed_chest = nearest_weld(np.array(J3["Spine1"]))
d_chest, prev_chest = dijkstra(seed_chest)
seed_hips = nearest_weld(np.array(J3["Hips"]))
d_hips, prev_hips = dijkstra(seed_hips)
reach = int(np.isfinite(d_chest).sum())
print(f"测地场：胸种子 #{seed_chest} · 髋种子 #{seed_hips} · "
      f"可达 {reach}/{GN} 焊点 · 胸->最远 {d_chest[np.isfinite(d_chest)].max():.3f}")
if reach < GN * 0.9:
    print(f"  ⚠️ 只有 {reach/GN:.1%} 焊点可达 ⇒ 网格仍有多连通块（毛发/鞋等分件属正常，整身断开才是问题）")

side_name = {1: "Left", -1: "Right"}
for sign, side in side_name.items():
    side_mask = np.sign(GP[:, axis_arm]) == sign
    # 肩：**肩高带内该侧最外的焊点**（解剖位置）。
    # 🔴 不能从"胸→手"的测地路径上截：胸种子 Spine1 在肩线**以下**（实测 y=0.22 vs 肩高 0.325），
    #    最短路径一路向下走，**根本够不到肩高**；上一版因此把肩放到 y=0.105 的腰侧。
    band = np.abs(GP[:, 1] - y_shoulder) < 0.03 * H
    bs = GP[band & side_mask]
    if len(bs):
        sh_pos = bs[int(np.argmax(np.abs(bs[:, axis_arm])))].copy()
    else:
        sh_pos = np.array([torso_half, y_shoulder, 0.0])
    sh_pos[axis_arm] = sign * abs(sh_pos[axis_arm])
    shoulder_i = nearest_weld(sh_pos)
    d_sh, prev_sh = dijkstra(shoulder_i)          # 从**肩**再起一次场：路径才只走手臂
    # 手：从肩出发、该侧、髋线以上的高度窗内测地最远；并要求够"外"
    win = side_mask & (GP[:, 1] < y_shoulder + 0.02 * H) & (GP[:, 1] > y_hip - 0.16 * H)
    cand = win & (np.abs(GP[:, axis_arm]) > torso_half * 0.45)
    if cand.sum() < 5:
        cand = win
    hand_i = int(np.argmax(np.where(cand, d_sh, -np.inf)))
    path = trace(prev_sh, hand_i)
    seg = path
    L = len(seg)

    def at(f):
        return seg[min(L - 1, max(0, int(round(f * (L - 1)))))]
    J3[f"{side}Shoulder"] = [float(x) for x in GP[seg[0]]]
    J3[f"{side}Arm"] = [float(x) for x in GP[at(0.45)]]
    J3[f"{side}ForeArm"] = [float(x) for x in GP[at(0.75)]]
    J3[f"{side}Hand"] = [float(x) for x in GP[at(0.97)]]
    print(f"  [{side}] 手焊点 #{hand_i} y={GP[hand_i, 1]:+.3f} |x|={abs(GP[hand_i, axis_arm]):.3f} · "
          f"路径 {L} 点（肩→手）"
          f"（肩 y={J3[f'{side}Shoulder'][1]:+.3f} → 手 y={J3[f'{side}Hand'][1]:+.3f}）")

    # ── 脚：该侧、底段高度窗内，从髋出发测地最远
    win2 = side_mask & (GP[:, 1] < y_bot + 0.12 * H)
    cand2 = win2 if win2.sum() > 5 else (GP[:, 1] < y_bot + 0.12 * H)
    dsel2 = np.where(cand2, d_hips, -np.inf)
    foot_i = int(np.argmax(dsel2))
    path2 = trace(prev_hips, foot_i)
    L2 = len(path2)

    def at2(f):
        return path2[min(L2 - 1, max(0, int(round(f * (L2 - 1)))))]
    J3[f"{side}UpLeg"] = [float(x) for x in GP[at2(0.28)]]
    J3[f"{side}Leg"] = [float(x) for x in GP[at2(0.62)]]
    J3[f"{side}Foot"] = [float(x) for x in GP[at2(0.90)]]
    lowest = GP[(GP[:, 1] < y_bot + 0.03 * H) & (np.sign(GP[:, axis_arm]) == sign)]
    if len(lowest):
        toe = lowest[np.argmax(lowest[:, axis_dep])]
        J3[f"{side}ToeBase"] = [float(toe[0]), float(y_bot + 0.01 * H), float(toe[2])]

PARENT = {"Hips": None, "Spine": "Hips", "Spine1": "Spine", "Neck": "Spine1",
          "Head": "Neck", "HeadTop": "Head"}
for side in ("Left", "Right"):
    PARENT[f"{side}Shoulder"] = "Spine1"
    PARENT[f"{side}Arm"] = f"{side}Shoulder"
    PARENT[f"{side}ForeArm"] = f"{side}Arm"
    PARENT[f"{side}Hand"] = f"{side}ForeArm"
    PARENT[f"{side}UpLeg"] = "Hips"
    PARENT[f"{side}Leg"] = f"{side}UpLeg"
    PARENT[f"{side}Foot"] = f"{side}Leg"
    PARENT[f"{side}ToeBase"] = f"{side}Foot"

print(f"关节 {len(J3)} 个（门限 ≥20 ⇒ {'过' if len(J3) >= 20 else '不过'}）")
for k in PARENT:
    if k in J3:
        print(f"  {k:16s} ← {str(PARENT[k]):14s}  {[round(v, 3) for v in J3[k]]}")
OUT_JSON.write_text(json.dumps({"joints": J3, "parent": PARENT, "axes": AX, "height": H},
                               ensure_ascii=False, indent=1), encoding="utf-8")

# ⑤ 验收图：网格剪影 + 骨架叠加


def shot(a_axis, tag, W=560, Hh=900):
    im = Image.new("RGB", (W, Hh), (14, 18, 28))
    d = ImageDraw.Draw(im)

    def to_px(v, ax):
        x = (v[ax] - P[:, ax].min()) / max(1e-9, ext[ax]) * (W - 60) + 30
        yy = (y_top - v[1]) / max(1e-9, H) * (Hh - 60) + 30
        return x, yy
    for v in P[::3]:
        x, yy = to_px(v, a_axis)
        d.point((x, yy), fill=(70, 84, 110))
    for k, par in PARENT.items():
        if k not in J3:
            continue
        x1, y1 = to_px(np.array(J3[k]), a_axis)
        d.ellipse([x1 - 4, y1 - 4, x1 + 4, y1 + 4], fill=(0, 229, 255))
        if par and par in J3:
            x0, y0 = to_px(np.array(J3[par]), a_axis)
            d.line([x0, y0, x1, y1], fill=(245, 176, 65), width=3)
        d.text((x1 + 6, y1 - 6), k, fill=(232, 236, 248))
    d.text((10, 8), tag, fill=(0, 229, 255))
    return im


front = shot(AX["arm"], "正视图（高度 × 臂轴）")
sidev = shot(AX["dep"], "侧视图（高度 × 深度轴）")
sheet = Image.new("RGB", (front.width + sidev.width + 20, 900), (14, 18, 28))
sheet.paste(front, (0, 0))
sheet.paste(sidev, (front.width + 20, 0))
sheet.save(OUT_IMG)
print("验收图:", OUT_IMG)
