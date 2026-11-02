# 149 · 桌面版天真 API 可执行 workflow（5 节点真跑）

## 一、接口
`POST /api/tianzhen`
```json
{"op":"run","workflow":{"nodes":[...],"edges":[...]}}
```
- 允许 `run / validate / gate / import / import_dir`；
- 只读 GET 仍允许 `status/nodes/coverage/harvest/contract/gate/runs`。

## 二、实测（桌面版真实进程）
`EmptyImage → ImageAddNoise → PadImageNode → Canny → SaveImage`

| 项 | 读数 |
|---|---|
| HTTP | **200** |
| ok | **true** |
| failed_at | null |
| trace | **5 节点** |
| 输出 | `C:\Users\Public\gbt-tianzhen-workflow.png` |
| 大小 | 209 B |
| sha256 | `43bed9819b60e718…` |
| status | PIL **13.0.0**、nodes **165** |
| coverage | native **148**、0.148 |

## 三、修的两个坑
1. payload 原 `PIL` 是 cp312 的，桌面 Python 3.13 导入 `_imaging` 失败；已换 **cp313 Pillow 13.0.0**；
2. 输出路径含中文时 `SaveImage` 报 `WinError 123`；本次验证改用 ASCII 路径 `C:\Users\Public\...`，不冒充“中文路径没问题”。

## 四、边界
- 这是**本地 CPU workflow**，不是秋叶 GPU 出图；
- 参照仍是核心面 1000，不是秋叶 1495；
- 模型/云端节点不接；
- 中文路径输出限制已如实记录。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
