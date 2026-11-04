---
name: ref-to-3d
displayName: 参考图 → 可拆解 3D 交互页（我们的数字人 DH-V7）
version: 2.0.0
description: 把参考图做成可拆解、可交互的 3D 网页，并换成**我们自己的数字人 DH-V7**：页面加载我们自己的 GLB（1 skinned mesh/66 bones），可旋转/缩放/皮肤透明/骨架/线框/拆解层/动作；参考图只提供配色/比例/氛围，不改资产结构。用于「参考图做成 3D / 数字人 3D / 可拆解 3D 网页 / teardown / DH-V7 / 参考图建模」。
triggers:
  - "参考图做成3D"
  - "可拆解3D"
  - "3D交互网页"
  - "数字人3D"
  - "DH-V7"
  - "teardown"
  - "拆解3D"
  - "参考图建模"
source: "主人 2026-11-03：不要 Salticus 蜘蛛，换成我们自己的数字人"
tags: [3d, threejs, digital-human, glb, teardown, reference-image, skill]
---

# 参考图 → 可拆解 3D 交互页（我们的数字人 DH-V7）

## 什么时候用
主人给一张参考图，要求「做成可拆解的 3D 交互网页」「换成我们自己的数字人」。
**不承诺照片级还原**：参考图只给外观/配色/比例；主体是**我们自己的资产**。

## 我们自己的数字人
- 资产：`holo_pet_w3/assets/dh/dh-v7-detail.glb`（来自 voice-theater，我们自己的 GLB）
- 真机：**1 个 skinned mesh / 66 根骨骼 / idle 动画**；
- 页面：`/teardown/`（console「拆解3D」同页）；
- 依赖：Three.js + GLTFLoader **本地**，零网络；不用外部模型/贴图。

## 三步
1. **加载自己的资产**：GLTFLoader 读 `dh-v7-detail.glb`，自动居中/缩放到 1.78m、落地；
2. **外观参考**：参考图 6×4 采样 → 主色/比例/氛围；只改 rim 光、HUD 色、材质微 emissive，**不改骨骼/网格结构**；
3. **拆解交互**：皮肤透明度、骨架显影（SkeletonHelper）、线框、拆解层滑杆、待机/挥手/行走/重置、拖拽/缩放。

## 硬判据
- [ ] `/teardown/` 能加载 **我们自己的** `dh-v7-detail.glb`
- [ ] `window.__dh3d` 暴露 state/model/meshes/bones/buildFromImage
- [ ] 真机读到 `meshes=1 · bones=66 · idle`
- [ ] 皮肤透明、骨架、线框、拆解层都生效
- [ ] 参考图只改外观，不改资产结构
- [ ] 页面零网络、GLB/Three 本地

## 边界
- 不是视觉大模型重建；不把参考图变成新人物；
- 不是物理仿真；拆解是**透视/分层可视化**，不是真拆成机械零件；
- GLB 是已有资产，换人物要换 GLB；
- 参考图不上传网络。
