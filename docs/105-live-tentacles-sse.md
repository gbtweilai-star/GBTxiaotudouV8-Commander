# 105 · 实时触手：SSE 推送审计事件，3D 当场点亮

> 主人 2026-11-01 选「2」：不用刷新页面，真实调用发生时 3D 触手**当场亮起**。

## 一、链路

```
run_task(...)  →  gbt_allinone/store/audit.jsonl 追加事件
                        │
        console-server.py  /api/events  (SSE, 1.2s 轮询文件尾部)
                        │  data: {"cap":"inventory","iso":"...","meta":{...}}
                        ▼
   浏览器 space3d.js  EventSource  →  liveBurst(cap)
                        │
                        ▼
        该能力位的 40 根触手叠加暖金层，6 秒淡出；data-space3d 的"+N"实时更新
```

## 二、实测（真跑，不是演示动画）

```
1) 连上 /api/events（从当前 EOF 开始，不重放历史）
2) 调用 run_task("inventory")
   audit 增长: 1,857,892 → 1,858,384 字节
3) SSE 立即收到:
   data: {"cap": "inventory", "iso": "2026-11-01T16:59:05",
          "meta": {"verdict": "clean", "foreign": 0}}
```

页面侧：`EventSource` 收到 → `liveBurst("inventory")` → 该能力位触手点亮，6s 淡出；
巡检标记从 `ok:385+30+15400+<点亮数>` 的最后一节实时变化。

## 三、怎么自己试

1. 浏览器打开 `http://127.0.0.1:8766/console/index.html#space`；
2. 另开一个终端跑任意能力，例如：
   ```bash
   python -c "import gbt_allinone as g; g.run_task('inventory')"
   ```
3. 看 3D 星图：对应能力位的触手会**暖金亮一下再淡出**；右上角「账本」/行动日志同步更新。

## 四、边界（如实）

- 只在 `http://` 下工作（`EventSource` 同源）；`file://` 直开走静态 pulse，不假装实时；
- 服务端只推"连上之后"的新事件（EOF 起点），不会一上来把历史全点亮；
- 断线由浏览器自动重连；`data-live="reconnecting"` 可查；
- 触手视觉仍是"每能力位 40 根"的密度示意，真实调用次数以 `audit.jsonl` 为准。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
