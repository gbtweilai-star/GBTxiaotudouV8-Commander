# 141 · GBT天真第二批：核心面纯 CPU 结构/字符串节点 20 个

## 一、补了什么
从 ComfyUI 核心面（1000 把参照）补 20 个**不碰模型/云端**的纯 CPU 节点：

`PrimitiveString` · `PrimitiveStringMultiline` · `PrimitiveInt` · `PrimitiveFloat` ·
`PrimitiveBoolean` · `PrimitiveBoundingBox` · `InvertBooleanNode` · `StringCompare` ·
`StringConcatenate` · `StringContains` · `StringLength` · `StringReplace` ·
`StringSubstring` · `StringTrim` · `JsonExtractString` · `KSamplerSelect` ·
`ResolutionSelector` · `ComfySwitchNode` · `ComfySoftSwitchNode` · `ConvertStringToComboNode`

全部注册进 `comfy_nodes_extra.py`，无权重、无网络、无 CUDA。

## 二、直接实测
| 节点 | 输入 | 输出 |
|---|---|---|
| PrimitiveString | `"abc"` | `"abc"` |
| StringConcatenate | a=a,b=b,sep=- | `"a-b"` |
| StringLength | `"abcd"` | `4` |
| JsonExtractString | `{"a":{"b":"c"}}`, key=a.b | `"c"` |
| ComfySwitchNode | true/yes/no | `"yes"` |

## 三、覆盖读数（参照仍为核心面 1000）
| 指标 | 之前 | 现在 |
|---|---|---|
| 我们节点 | 119 | **139** |
| 同名覆盖 | 102 | **122** |
| 覆盖率 | 10.2% | **12.2%** |
| traditional 缺口 | 0 | **0** |
| 可补 useful | 0 | **0** |
| needs_model / cloud / unknown | 405/371/122 | **404/367/107** |

`test_comfy_engine.py`：**ALL OK**（skip/times/回滚/continue、复跑 sha256 全同）。

## 四、边界（不吹）
- 参照是 **ComfyUI 核心面 1000**，不是秋叶整包 ~1495；
- 404 模型面 / 367 云端没有 CUDA/key，**不假接**；
- 本轮补的是值传递/字符串/结构节点，不提升出图质量；
- 真·秋叶一比一仍要 `/object_info` 真快照。

## 五、下一步
1. 继续从 `unknown 107` 里挑纯 CPU 结构节点；
2. 拿秋叶真快照后按真实 schema 校准；
3. GPU/云端面保持如实不接。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
