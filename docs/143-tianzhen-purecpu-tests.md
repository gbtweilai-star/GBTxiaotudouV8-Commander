# 143 · 天真纯 CPU 节点回归：注册 ≠ 能用

## 一、新增测试
`tests/test_comfy_purecpu.py` 真调用新增节点，不只看 `NODES` 里有没有名字：

- 注册检查 10 个关键节点；
- `ImageAddNoise` 真写图；
- `PadImageNode` 32×24 → **40×32**；
- `ResizeImageMaskNode` 32×24 → **16×12**；
- `StringFormat`、`StringConcatenate`、`JsonExtractString`、
  `ComfyMathExpression`、`MergeTextLists`、`ComfySwitchNode` 逐条判值；
- 节点总数 ≥148。

## 二、结果
`tests/test_comfy_purecpu.py` → **ALL PASS**  
`tests/test_comfy_engine.py` → **ALL OK**

## 三、当前 GBT天真 读数
| 指标 | 数值 |
|---|---|
| 节点 | **148** |
| 核心面同名覆盖 | **131** |
| 覆盖率 | **13.1%** |
| traditional 缺口 | **0** |
| 可补 useful | **0** |
| needs_model / cloud / unknown | 402 / 365 / 102 |

## 四、意义
新增节点不是“注册了但跑不动”的孤儿：
- 图像节点真写文件、读回宽高；
- 字符串/JSON/数学/开关节点真判值；
- 引擎回归仍全绿。

## 五、边界
- 覆盖参照仍是核心面 1000，不是秋叶 1495；
- 模型面/云端不接；
- 真·一比一仍需秋叶真快照。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
