# 145 · GBT天真第五批：图层/形态学/空洞/列表 7 节点

## 一、补了什么
`AddLayer` · `Morphology` · `FillHoles` · `ResolutionBucket` ·
`ShuffleDataset` · `CreateBoundingBoxes` · `LayersFromBoundingBoxes`

- `AddLayer`：Pillow alpha composite + opacity；
- `Morphology`：灰度膨胀/腐蚀（PIL MaxFilter/MinFilter）；
- `FillHoles`：边界背景泛洪，填闭合孔洞；
- `ShuffleDataset`：seed 固定可复现；
- 其余为列表/分辨率结构节点。

## 二、实测
| 节点 | 读数 |
|---|---|
| AddLayer | 真写图 161,908 B |
| Morphology | dilate/kernel3 真写图 |
| FillHoles | 真写遮罩 |
| ShuffleDataset seed=7 | `[1,2,3]` → `[3,1,2]` |
| ResolutionBucket | 1280×720 → `landscape` |
| test_comfy_purecpu | **ALL PASS** |
| test_comfy_engine | **ALL OK** |

## 三、覆盖读数（参照核心面 1000）
| 指标 | 上轮 | 现在 |
|---|---|---|
| 天真节点 | 157 | **164** |
| 同名覆盖 | 140 | **147** |
| 覆盖率 | 14.0% | **14.7%** |
| traditional 缺口 | 0 | **0** |
| 可补 useful | 0 | **0** |
| needs_model / cloud / unknown | 399/365/96 | **399/365/89** |

## 四、边界
- Morphology 是 PIL 灰度形态学，不是任意彩色形态学；
- FillHoles 只处理二值遮罩；
- 参照仍是核心面 1000，不是秋叶 1495；
- 模型/云端面不假接。

## 五、下一步
继续从 `unknown 89` 挑纯 CPU 节点；秋叶真快照到后校准 schema。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
