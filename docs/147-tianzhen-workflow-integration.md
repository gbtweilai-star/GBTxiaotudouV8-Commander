# 147 · 天真纯 CPU 节点接入真正执行引擎

## 一、不是只测单函数
`tests/test_comfy_workflow_purecpu.py` 跑完整 workflow：

```
EmptyImage(64×64)
→ ImageAddNoise(seed=7,strength=0.1)
→ PadImageNode(+2 四边)
→ Canny(low=50,high=150)
→ SaveImage
```

## 二、结果
| 项 | 读数 |
|---|---|
| workflow ok | **true** |
| trace 节点 | **5** |
| 输出 | 68×68 RGBA PNG |
| bytes | 209 |
| sha256 | `43bed9819b60e718…` |
| gate | pass |

`tests/test_comfy_purecpu.py` 与 `tests/test_comfy_engine.py` 也继续 ALL PASS。

## 三、覆盖读数（核心面 1000）
| 指标 | 数值 |
|---|---|
| 天真节点 | **165** |
| 同名覆盖 | **148** |
| 覆盖率 | **14.8%** |
| traditional 缺口 | **0** |
| 可补 useful | **0** |
| needs_model / cloud / unknown | 399 / 365 / 88 |

## 四、意义
- 新节点不是“注册了但引擎不认”；
- 图像链真过 gate，产物有 sha256；
- Canny/AddNoise/Pad 都能在 workflow 里按拓扑跑。

## 五、边界
- 参照仍是核心面 1000，不是秋叶 1495；
- 模型/云端面不假接；
- 64×64 是测试尺寸，不代表出图质量。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
