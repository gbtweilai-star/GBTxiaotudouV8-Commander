# 114 · 力变化率前馈（实现 + 静态接触下未触发）

> 下一步：接触瞬间提前收力，而不是只靠位置预判。

## 一、实现
`onnx_chunked` 新增：
- `feedforward=true`；
- 记录力变化率 `last_force_rate`；
- `|rate| > rate_threshold` 时，本帧有效限值降到 **0.5×limit**；
- 输出 `ff_hits`、`last_force_rate`。

## 二、实测（60 帧 / limit=0.5 / external=0 / 静态接触）
| 项 | 数值 |
|---|---|
| moved | 60/60 |
| fps | **35.29** |
| force_peak | **0.5** |
| stiffness | 100→43.05 |
| compliance_calls | 8 |
| **ff_hits** | **0** |
| last_force_rate | 0.0 |
| realtime_ok | true |

## 三、结论
- 前馈逻辑已接，但**静态接触下力恒定，rate=0，不触发**；
- 不能拿“有 feedforward 字段”说“抑制了冲击”；
- 需要**动态接触/外部位置变化**的测试才能验证。

## 四、下一步
1. 造一个 external 随时间变化的力曲线（模拟接触/滑移）；
2. 测 ff_hits、峰值超调、恢复时间；
3. 摄像头/真机后再谈真实冲击。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
