# 148 · 桌面版接 GBT天真只读 API（status/coverage）

## 一、加了什么
桌面版 `console-server.py` 新增只读接口：

```
GET /api/tianzhen?op=status
GET /api/tianzhen?op=nodes
GET /api/tianzhen?op=coverage
GET /api/tianzhen?op=harvest
GET /api/tianzhen?op=contract
GET /api/tianzhen?op=gate
GET /api/tianzhen?op=runs
```

- 只读白名单；`op=run` 不开放；
- 调用 `gbt_allinone.tools.comfy_native.run`；
- 桌面 payload 补了 `comfy_native` / `comfy_nodes_extra` / `state/comfyui_ref_nodes.json` / `PIL 13.0.0`。

## 二、实测（桌面版真实进程）
| 接口 | 读数 |
|---|---|
| `/api/tianzhen?op=status` | 200，PIL=13.0.0，nodes=165 |
| `/api/tianzhen?op=coverage` | 200，native=148，coverage=0.148 |
| `/api/proactive` | 200 |

## 三、意义
- GBT天真不再只活在源码/工具脚本里，桌面版能直接查状态与覆盖率；
- 覆盖率读数 **14.8%** 与源码工具一致；
- 只读接口不会误跑工作流。

## 四、边界
- 这是**只读查询**，不是桌面 UI 出图入口；
- 参照仍是核心面 1000，不是秋叶 1495；
- 模型/云端面不接；
- 桌面版仍未打包 torch/kornia（不需要，会报缺失）。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
