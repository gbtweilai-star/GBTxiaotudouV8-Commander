# 158 · 桌面 `/api/tianzhen` 接原生 SD-Turbo：缓存后 512 出图

## 一、实现
桌面 `/api/tianzhen` 新增 `op=t2i_sdturbo`：
- 通过 `gbt_allinone/native_t2i_bridge.py` 启动**常驻 SD-Turbo worker**（JSONL stdin/stdout）；
- worker 只加载一次模型；
- 之后 256/512 请求复用同一进程缓存。

调用：
```json
{"op":"t2i_sdturbo",
 "prompt":"a red apple on a wooden table, photo, detailed",
 "out":"...\\api-t2i-512.png",
 "size":512,"steps":1,"seed":7}
```

## 二、实测（桌面真实进程，两连发）
| 请求 | load_s | generation_s | 输出 |
|---|---|---|---|
| 256 | 4.68 | 13.07 | 121,432 B |
| **512（缓存复用）** | **4.68（未重载）** | **27.13** | **437,495 B** |

- 引擎：`diffusers SD-Turbo CPU（本地权重）`；
- 无 ComfyUI、无云端；
- 512 图确实生成，不是把 256 放大冒充。

## 三、本地链路
```
桌面 POST /api/tianzhen
→ native_t2i_bridge
→ 常驻 native_t2i_worker（live pyembed + vendor/pylibs torch/diffusers）
→ SD-Turbo 本地权重
→ PNG
```

## 四、坑
- worker 由 live pyembed 跑，对 `Desktop`/`Public` 直接写可能 `PermissionError`；
- 实测用 workspace `.scratch/lead` 输出成功；
- 所以 API 传输出路径时要用 **worker 可写的本地目录**。

## 五、当前状态
- 天真节点 167（含 `t2i_sdturbo`）；
- ComfyUI 已删、8188 down；
- 本地 512 出图可用；
- 云端不碰。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
