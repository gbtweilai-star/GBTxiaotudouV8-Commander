# 117 · 安全闸：禁止 pre_clamp=false 裸奔

## 一、为什么加
- 动态外力 + 位置前馈裸奔时，force_peak **6.68**，远超 limit 0.5；
- 前馈不能替代 pre-clamp；
- 这种配置不能进入实时写路径。

## 二、实现
`onnx_chunked` 启动即校验：
```python
if force_limit and not pre_clamp:
    return {"ok": False, "status": "unsafe_rejected",
            "error": "force_limit>0 时 pre_clamp 必须为 true；裸奔模式禁止进入实时写路径"}
```
- 拒绝发生在连接/推理/写手之前；
- 响应带 `safety_guard: true`；
- 安全配置仍返回 `pre_clamp=true / safety_guard=true`。

## 三、实测
| 配置 | 结果 |
|---|---|
| `force_limit=0.5, pre_clamp=false` | **unsafe_rejected** |
| `force_limit=0.5, pre_clamp=true` | 正常 40fps 级，force_peak=limit |

## 四、边界
- 安全闸是**软件防线**，不是真机急停；
- 真机还需要硬件急停/力矩上限/看门狗；
- 摄像头未通，loopback 仿真。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
