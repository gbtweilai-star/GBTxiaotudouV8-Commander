# 161 · t2i_fused 节点：融合权重真正接成能力

## 一、节点
- 名称：`t2i_fused`
- 位置：`gbt_allinone/tools/comfy_nodes_extra.py`
- 权重：`vendor/hf/gbt-fused-sd15`（4,071 MB / 12 文件）
- 引擎：本地 Diffusers SD1.5，CPU float32
- 不碰 ComfyUI、不碰云端

## 二、实测
| 测试 | 加载 | 生成 | 结果 |
|---|---|---|---|
| 64×64 / 1 步 | 7.22s | 8.89s | 7,736 B，正常 |
| 256×256 / 8 步 | 6.83s | 89.03s | 128,086 B，苹果正常 |

- 提示词：`a red apple on a wooden table, photo, detailed`
- 产物：`.scratch/lead/t2i-fused-256.png`
- 节点返回 `ok=True`，`engine=本地融合权重 gbt-fused-sd15（RV5.1×Tiny-SD）`

## 三、边界
- 融合权重是 **RV5.1 × Tiny-SD**，不是秋叶权重；
- 共同 UNet key 148，部分层融合；
- CPU 出图慢：256/8步约 89s；
- 不冒充云端/秋叶。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
