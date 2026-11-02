# 155 · 本地 ComfyUI 真快照：1033 节点，traditional 再次清零

## 一、这次不是“核心面 zip”，是本地 ComfyUI 真 `/object_info`
- 用 `vendor/ComfyUI/launch_cpu.py` 启动 ComfyUI CPU（torch CPU，`--cpu --port 8188`）；
- `GET http://127.0.0.1:8188/object_info` → **1,033 节点**；
- 去掉 BOM 后落 `state/comfyui_object_info.json`。

## 二、真快照暴露的最后一个 traditional 缺口
`SaveImageWebsocket`（`custom_nodes.websocket_image_save`，纯 CPU）：
- 输入 `images`；
- 已实现本地等效：把 images 写到 `out`，返回 `ui.images`；
- 实测写图 **318,808 B**；
- 不真开 websocket，只做本地落盘。

## 三、覆盖读数（参照：本地 ComfyUI 1033）
| 指标 | 之前（核心面1000） | 现在（本地1033） |
|---|---|---|
| 天真节点 | 165 | **166** |
| 同名覆盖 | 148 | **146** |
| 覆盖率 | 14.8% | **14.1%** |
| traditional 缺口 | 0 | **0** |
| 可补 useful | 0 | **0** |
| needs_model / cloud / unknown | 399/365/88 | **425/368/94** |

覆盖率下降不是退步：参照从核心面 1000 换成**本地实际 1033**，读数更真。

## 四、桌面版同步
`/api/tianzhen?op=status` → nodes **166**；  
`/api/tianzhen?op=coverage` → native **146 / 1033 = 0.1413**，traditional **0**。

## 五、边界
- 本地 ComfyUI 是 **CPU 模式**，不是秋叶 GPU 整包；
- 秋叶 ~1495 仍没有；本地实际 1033；
- 模型/云端面不硬接；
- `SaveImageWebsocket` 是本地落盘等效，不是真 websocket 推流。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
