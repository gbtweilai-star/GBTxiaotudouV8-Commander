# 157 · 删掉 ComfyUI 后：天真用本地 Diffusers SD-Turbo 原生出图

## 一、先按你要求删本地 ComfyUI
- 停止 ComfyUI CPU 进程；
- `8188` 已 down；
- 删除 `vendor/ComfyUI`（**4,666 MB**，1,350 文件）；
- 不再用 ComfyUI 占内存。

## 二、天真原生文生图（无 ComfyUI、无云端）
新增节点 `t2i_sdturbo`：
- 权重：本机已有 `vendor/hf/hub/models--stabilityai--sd-turbo`（unet 3.3GB / text encoder 1.3GB / vae 319MB）；
- 运行时：`vendor/pylibs` 的 torch 2.15 CPU + diffusers 0.42.1；
- 纯本地 CPU，不连任何云。

实测：
```python
CN.NODES["t2i_sdturbo"]["fn"]({
  "prompt": "a red apple on a table, photo",
  "out": "...png", "size": 256, "steps": 1, "seed": 7
})
```
| 项 | 读数 |
|---|---|
| 模型加载 | **8.69s**（进程内缓存） |
| 编译/生成 | **24.24s** |
| 输出 | 256×256 PNG / **121,432 B** |
| 引擎 | `diffusers SD-Turbo CPU（本地权重）` |
| 云端 | **无** |

## 三、天真现在的本地能力
- 166 个原节点（本地 ComfyUI 真快照参照，traditional 0）；
- 新增 `t2i_sdturbo` → **167 个节点**；
- 本地纯 CPU 出图可用；
- 手部 28fps、桌面 UI/API 不受影响。

## 四、边界
- SD-Turbo 是 **1-step 小图（256）**，不是秋叶完整模型/插件生态；
- 更大分辨率/模型/视频需要更多权重与 GPU；
- 但“先能本地出图”不再是空话：不装 ComfyUI 也跑通。

## 五、下一步
1. 把 `t2i_sdturbo` 接桌面 `/api/tianzhen` POST 与 UI；
2. 用 cache 后的模型做 512 步数/批量；
3. 继续补本地图像后处理节点（不碰云）。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
