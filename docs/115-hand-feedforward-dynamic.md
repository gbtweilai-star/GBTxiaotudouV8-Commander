# 115 · 动态外力下测前馈：有 pre-clamp 时 force 恒定，ff 不触发；去掉 pre-clamp 峰值失控

## 一、两次实验
| 配置 | force_peak | pre_clamped | adjustments | ff_hits | fps |
|---|---|---|---|---|---|
| 动态 external，**pre_clamp=true** | **0.5** | 120 | 56 | **0** | 12.46 |
| 动态 external，**pre_clamp=false** | **20.527** | 0 | 120 | 待查（有触发） | 11.27 |

## 二、结论
- **pre-clamp 是主保护**：它把力压在 limit，导致力恒定、rate≈0，前馈没有触发空间；
- 去掉 pre-clamp 后力变化率出现，前馈有机会触发，但单靠前馈**峰值冲到 20.5**，远超 0.5；
- 所以顺序必须是：**先 pre-clamp 保底，再用前馈提前量**，不能反过来；
- 当前前馈没有证明“降低峰值”，只证明“没有 pre-clamp 会失控”。

## 三、下一步
1. 前馈只在前置预判之上做**小提前量**（不超过 limit 的 20%）；
2. 动态 external 下测峰值/恢复时间，和纯 pre-clamp 对比；
3. 不允许再用 pre_clamp=false 的裸奔模式跑生产。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
