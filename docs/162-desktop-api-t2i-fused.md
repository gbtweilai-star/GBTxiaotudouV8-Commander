# 162 · 桌面 API 接入 t2i_fused

## 一、改动
- `tools/native_t2i_worker.py`：按 `op=t2i_fused` / `model=fused` 路由到融合节点；
- `gbt_allinone/native_t2i_bridge.py`：透传 op/model，fused 默认 256×256 / 8 步；
- `tools/console-server.py`：POST `/api/tianzhen` 允许 `op=t2i_fused`；
- source、live repo、desktop payload 三处已同步。

## 二、实测
请求：
```json
{"op":"t2i_fused","prompt":"a red apple on a wooden table, photo",
 "out":"...\\.scratch\\lead\\api-fused-64.png","size":64,"steps":1,"seed":7}
```
响应：
```json
{"ok":true,"size":[64,64],"steps":1,"load_s":6.48,"generation_s":11.04,
 "engine":"本地融合权重 gbt-fused-sd15（RV5.1×Tiny-SD）"}
```
- 产物：`api-fused-64.png`（7,736 B）
- 接口：`http://127.0.0.1:8766/api/tianzhen`
- 不碰 ComfyUI/云端。

## 三、内存
- API 测试后已停常驻 worker（约 2,004MB 释放）；
- console-server 约 47MB；
- 下次调用再按需加载融合权重。

## 四、边界
- 融合权重是 RV5.1×Tiny-SD，不是秋叶；
- 64/1 仅接口验证，质量看 256/8；
- 真·秋叶权重仍需单独 checkpoint。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
