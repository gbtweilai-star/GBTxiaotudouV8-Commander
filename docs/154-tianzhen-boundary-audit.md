# 154 · GBT天真边界审计：unknown 85 不再是纯 CPU

## 一、审计结论
核心面 1000 里，我们已接 **148**，traditional 缺口 **0**，可补 useful **0**。
剩余 **85 unknown** 全部落在以下面：

| 类型 | 样本 |
|---|---|
| 采样/调度/CFG | `AlignYourStepsScheduler` `BasicScheduler` `CFGNorm` `CFGOverride` `CFGZeroStar` `APG` |
| 3D/几何/烘焙 | `ApplyTextureToMesh` `BakeAmbientOcclusion` `BakeNormalMapFromMesh` `BakeTextureFromVoxel` `BuildPoseFile` `CameraAngle` `CreateCameraInfo` |
| 视频/训练/缓存 | `ContextWindowsManual` `ChromaRadianceOptions` 等 |

没有一个是“纯 CPU 图像/字符串/列表”安全节点。

## 二、为什么不再加节点
- 再加只能靠猜 schema，属于假成功率；
- 模型面 402 / 云端 365 需要 CUDA 或 key，本机没有；
- 秋叶整包参照 **~1495** 不在盘上，只有核心面 **1000**；
- 真·一比一必须先拿 `/object_info` 真快照。

## 三、当前可信能力
| 项 | 读数 |
|---|---|
| 天真节点 | **165** |
| 核心面覆盖 | **148 / 1000 = 14.8%** |
| traditional 缺口 | **0** |
| 可补 useful | **0** |
| 桌面 `/api/tianzhen` | status/coverage 200；POST workflow 5 节点过 gate |
| 手部 UI | 左栏 5 按钮 + 天真 2 按钮，无孤儿 |

## 四、下一步（外部输入）
1. 秋叶机跑 `GET /object_info`，放 `state/comfyui_object_info.json`；
2. 或给 CUDA 机器，模型/采样面才谈得上补；
3. 在此之前不新增“名字节点”。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
