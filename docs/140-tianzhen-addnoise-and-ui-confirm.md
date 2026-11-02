# 140 · 确认手部 UI 无孤儿 + GBT天真补 ImageAddNoise

## 一、先确认：桌面手部 UI 不是孤儿
CDP 在真实桌面页面读到：
```json
{"buttons":["手部图片","手部视频","相机chunks","监视目录","录相机5s"],
 "oldPanel":false,"modal":true,"bridge":["pick","pickDir","record"],
 "title":"GBT小土豆V8 · 认知界面"}
```
- 按钮在**左侧栏「手部工具」**，不再压输入框；
- 旧 `gbt-hand-panel` 浮动条已不存在；
- preload 桥三个方法齐全；
- 「录相机5s」已通过 CDP 触发：返回 `{ok:true,code:0}`，产出 5 个 chunk；
- 桌面版 `/api/proactive` 200。

## 二、回到 GBT天真
### 1. 当前真实覆盖（ComfyUI 核心面参照）
| 指标 | 之前 | 现在 |
|---|---|---|
| 我们节点 | 118 | **119** |
| 同名覆盖 | 101 | **102** |
| 覆盖率 | 10.1% | **10.2%** |
| traditional 缺口 | 0 | **0** |
| 可补 useful | 1（ImageAddNoise） | **0** |

### 2. 新补节点
`ImageAddNoise`（ComfyUI 同名）：
- 输入：`image`、`out`、`seed?`、`strength?`；
- 高斯噪声，seed 可复现；
- 实测 `seed=123, strength=0.2`：512×512 PNG，**879,399 B**，ok；
- 注册进 `comfy_nodes_extra.py`，`comfy_native` 节点 **118 → 119**。

### 3. 取食器读数
```
参照 1000 · 我们 119 · 覆盖 102 = 10.2%
缺口：traditional 0 · needs_model 405 · needs_cloud 371 · unknown 122
```
- **traditional 纯 CPU 面已 0 缺口**；
- 剩余 405 模型面 / 371 云端：本机无 CUDA、无 key，**不假接**；
- 要真·秋叶整包，必须把秋叶机 `/object_info`（~1495）放到 `state/comfyui_object_info.json`，否则只能报核心面。

## 三、边界
- 不是「已和秋叶 1495 一样」；是 **核心面 traditional 100% + 覆盖 10.2%**；
- 手部 UI 无孤儿；但真机/摄像头硬件仍不在；
- 测试：`tests/test_comfy_engine.py` **ALL OK**。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
