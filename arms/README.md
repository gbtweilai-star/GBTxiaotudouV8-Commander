# Omni-Arm · 22 自由度手 + 9 骨手臂 + 8 段触手（真几何 · 真绑骨 · 真 GLB）

这个目录不是渲染图，是**能下载、能加载、带自检读数**的资产：

| 文件 | 是什么 | 现读 |
|---|---|---|
| `omni-arm-rigged.glb` | 绑好骨的 glTF 二进制（1 网格 / 1 蒙皮 / **40 骨**） | **60,444 B** · verts **1,080** · 高度 **0.6002 m** |
| `omni-arm-spec.json` | 骨架规格（**零随机**，可复现） | 40 骨 · 手指自由度 `dof_fingers` 在文件里 |
| `omni-arm-report.json` | 八条自检读数（可逐条复核） | 8/8 过 |
| `omni_arm.py` | 这一位能力的实现（`status`/`spec` 免门，`build` 挂 `filesystem_write`） | 7,375 B |
| `tentacle3d.html` | 2 万触手的 3D 看件页（自包含，零外部依赖，双击即开） | 110,549 B |
| `tentacle3d.png` | 上面那个页面的截图 | 645,175 B |

## 八条自检（`omni-arm-report.json` 原样摘录）

| 判据 | 读数 | 过 |
|---|---|---|
| GLB 已落盘 | `omni-arm-rigged.glb · 60444 字节` | ✅ |
| 骨数 = 40（skin.joints） | `joints=40 nodes=42` | ✅ |
| 单网格 + 单蒙皮 | `meshes=1 skins=1` | ✅ |
| 蒙皮关节数 = 40 | `joints=40` | ✅ |
| 无未绑顶点（权重和 > 0） | `未绑=0` | ✅ |
| 权重已归一（每顶点和 ≈ 1） | `非归一化=0` | ✅ |
| 顶点数 > 300（真几何不是空壳） | `verts=1080` | ✅ |
| 尺寸合理（0.2~2.0 m） | `高=0.6002 m` | ✅ |

构建环境现读：**Blender 4.2.16 LTS** · 360 顶点 / 270 面 · 40 个顶点组 · `ARMATURE` 修改器 · `blender_rc=0`。

## 怎么打开

- **看 3D**：双击 `tentacle3d.html`（或 `python -m http.server` 后打开），页里带骨架开关、骨骼树、资产 sha16 自证。
- **用 GLB**：任何 glTF 工具/引擎直接加载 `omni-arm-rigged.glb`（Babylon / three.js / Blender / Unity 都可）。
- **重建**：`python arms/omni_arm.py` 的 `build` 面会调 Blender 重新建件（需要本机装 Blender 4.2+）。

## 老实话（设计稿不能直接跑）

`vendor/omni-arm/source/` 里那几份原始设计稿（`Omni-Arm.py` / `Omni-Arm-3d-Rig.py` / `Omni-Arm-Blender.py` …）
**是不能直接跑的**，实测有三类硬伤：FK 只算 2D、IK 不是 CCD、骨架轴由 `random` 决定（不可复现），
生成的 Blender 脚本本身还有语法错、导出路径写死 `/mnt/data`。

这个目录里的 GLB 是**重写实现**的产物（确定性规格 → Blender 建骨/建几何/绑权重 → GLB），
所以它可复现、可自检；原始设计稿仍然逐字节归档，只当参考，不当可执行件。
