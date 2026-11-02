# 144 · GBT天真第四批：列表/正则/颜色空间 9 节点

## 一、补了什么
从 `unknown` 里挑出 9 个纯 CPU 节点：

`CreateList` · `GetItemFromList` · `CustomCombo` · `StripWhitespace` ·
`RegexMatch` · `RegexExtract` · `RegexReplace` · `ImageRGBToYUV` · `ImageYUVToRGB`

- 正则用 Python `re`，错误返回结构化 `user_error`；
- YUV 用 BT.601 做通道转换，不依赖模型/GPU；
- 列表/选择节点只做值传递。

## 二、实测
| 节点 | 读数 |
|---|---|
| CreateList | `[1,2]` → `[1,2]` |
| GetItemFromList | index=1 → `2` |
| RegexExtract | `abc123` + `[0-9]+` → `123` |
| RegexReplace | `a-b` → `a_b` |
| ImageRGBToYUV | 真写图 281,240 B |
| ImageYUVToRGB | 真写图 358,619 B |
| test_comfy_purecpu | **ALL PASS** |
| test_comfy_engine | **ALL OK** |

## 三、覆盖读数（参照核心面 1000）
| 指标 | 上轮 | 现在 |
|---|---|---|
| 天真节点 | 148 | **157** |
| 同名覆盖 | 131 | **140** |
| 覆盖率 | 13.1% | **14.0%** |
| traditional 缺口 | 0 | **0** |
| 可补 useful | 0 | **0** |
| needs_model / cloud / unknown | 402/365/102 | **399/365/96** |

## 四、边界
- YUV 是 BT.601 通道转换，不是“HDR/神经颜色增强”；
- 正则/列表节点不提升模型出图，只补值传递能力；
- 参照仍是核心面 1000，不是秋叶 1495；
- 模型/云端面不假接。

## 五、下一步
1. 继续清 `unknown 96` 纯 CPU 节点；
2. 秋叶真快照到后再校准 schema；
3. GPU/云端不硬接。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
