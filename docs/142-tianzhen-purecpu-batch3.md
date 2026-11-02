# 142 · GBT天真第三批：字符串/设备/列表/图像结构 9 节点

## 一、补了什么
从核心面剩余 `unknown` 里挑**不碰模型/云端**的 9 个节点：

`StringFormat` · `SelectCLIPDevice` · `SelectModelDevice` · `SelectVAEDevice` ·
`MergeImageLists` · `MergeTextLists` · `PadImageNode` · `ResizeImageMaskNode` ·
`ComfyMathExpression`

- `ComfyMathExpression` 用 AST 白名单，不执行任意 Python；
- `PadImageNode`/`ResizeImageMaskNode` 用 Pillow，纯 CPU；
- `Select*Device` 是值透传，**不加载设备/模型**，不冒充 GPU。

## 二、实测
| 节点 | 读数 |
|---|---|
| `StringFormat` | `{}-{}` + `["a","b"]` → `a-b` |
| `ComfyMathExpression` | `2*(3+4)` → `14` |
| `MergeTextLists` | `["a"]+["b"]` → `["a","b"]` |
| `SelectModelDevice` | `cpu` → `cpu` |
| `PadImageNode` | 512→**528×528**，355,959 B |
| `ResizeImageMaskNode` | 512→**128×128**，26,050 B |
| 引擎 | `test_comfy_engine.py` **ALL OK** |

## 三、覆盖读数（参照核心面 1000）
| 指标 | 上轮 | 现在 |
|---|---|---|
| 天真节点 | 139 | **148** |
| 同名覆盖 | 122 | **131** |
| 覆盖率 | 12.2% | **13.1%** |
| traditional 缺口 | 0 | **0** |
| 可补 useful | 0 | **0** |
| needs_model / cloud / unknown | 404/367/107 | **402/365/102** |

## 四、边界
- 参照仍是核心面 **1000**，不是秋叶整包 ~1495；
- 402 模型面 / 365 云端：无 CUDA/key，不假接；
- `Select*Device` 只是选择值，不是“真的用了 GPU”；
- 真·秋叶一比一仍要真快照。

## 五、下一步
1. 继续从 `unknown 102` 找纯 CPU 结构节点；
2. 秋叶真快照到手后按 schema 校准；
3. 不再靠编节点名冲覆盖率。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
