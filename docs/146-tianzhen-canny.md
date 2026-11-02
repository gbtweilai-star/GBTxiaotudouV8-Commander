# 146 · GBT天真第六批：Canny 边缘（numpy 实现）

## 一、补了什么
`Canny`（ComfyUI 同名）：
- 输入 `image`、`out`、`low_threshold?`、`high_threshold?`；
- Pillow 高斯模糊 + numpy Sobel；
- 非极大值抑制 + 双阈值 + 两轮滞后生长；
- 不依赖 cv2，纯 CPU。

## 二、实测
| 项 | 读数 |
|---|---|
| hand-21.png 512×512 | `edge_pixels=331` |
| 输出 PNG | 2,993 B |
| 合成半黑白图 | 测试能出边 |
| `tests/test_comfy_purecpu.py` | **ALL PASS** |
| `tests/test_comfy_engine.py` | **ALL OK** |

## 三、覆盖读数（参照核心面 1000）
| 指标 | 上轮 | 现在 |
|---|---|---|
| 天真节点 | 164 | **165** |
| 同名覆盖 | 147 | **148** |
| 覆盖率 | 14.7% | **14.8%** |
| traditional 缺口 | 0 | **0** |
| 可补 useful | 0 | **0** |
| needs_model / cloud / unknown | 399/365/89 | **399/365/88** |

## 四、边界
- 这是 numpy 版 Canny，不是 OpenCV 的 `cv2.Canny` 二进制；
- 阈值/滞后参数是简化实现；
- 参照仍是核心面 1000，不是秋叶 1495；
- 模型/云端面不假接。

## 五、下一步
继续从 `unknown 88` 挑纯 CPU 节点；秋叶真快照到后校准 schema。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
