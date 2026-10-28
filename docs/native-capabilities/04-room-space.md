# 04 · 房间空间 (`room_space`)

> **1 个能力位 · 16 个 op** · 隔离排练现实 · 镜像多维度空间里的隔离房间
>
> ⚠️ **口径更正（2026-10-28 按注册表现读）**：本文旧版把房间写成 19 个独立能力位
> （`room_create` / `room_enter` / …）。**那是错的**——注册表里只有**一个**能力位
> `room_space`（域 `system`，需授权），19 个动作是它的 **`op` 参数**，不是 19 个位。
> 按旧写法去调 `room_create` 这个名字（当作能力位）只会得到 `unknown capability`。
> 核验：`python docs/native-capabilities/verify_cap.py show room_space`
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 核心理念

> 会议室不是外挂服务，也不是第二套视觉总线。
> 它是镜像多维度空间里的一个隔离房间：每个房间都有自己的
> dimension / reality / timelines / passports，
> 复用原有原子写、树指纹、排练命令与视觉帧库。

**一句话**：房间是**隔离排练现实**——所有假设/模拟/推演/打磨一律在房间里跑，
**房间不覆盖全局 `mirror_space/reality`**。

---

## 能力位登记（现读）

| 项 | 值 |
|---|---|
| 能力位 | `room_space` |
| 域 | `system` |
| 类型 | **需授权** |
| 处理器 | `room_space` |
| 授权作用域 | `filesystem_write`（shape/scan/simulate/parity）· `process_execute` + `filesystem_write`（rehearse）· `deploy_publish`（release） |

---

## 16 个 op（注册表逐字）

| op | 作用 | 门 |
|---|---|---|
| `create` | 创建房间（隔离维度、现实区、时间线、护照目录） | filesystem_write |
| `enter` | 人和 AI 加入同一房间 | filesystem_write |
| `namespace` | 注册房间命名空间 | filesystem_write |
| `shape` | 在房间维度里写文件、方案和产物 | filesystem_write |
| `scan` | 房间维度体检 | filesystem_write |
| `define_plan` | 固化假设/架构/步骤/验收/回滚 | filesystem_write |
| `get_plan` | 读回已固化的计划 | 只读 |
| `simulate` | 静态推演（不碰现实） | filesystem_write |
| `parity` | 沙盒与目标环境契约核对 | filesystem_write |
| `rehearse` | 在房间维度内跑闭环命令 | process_execute + filesystem_write |
| `frame` | 绑定当前共享视觉帧 | filesystem_write |
| `gate` | 房间门禁（验证全绿才放行） | 只读 |
| `release` | 全绿后一次性写入房间现实区 + 护照 | deploy_publish |
| `snapshot` | 冻结房间时间线 | filesystem_write |
| `sync` | 同步房间状态 | filesystem_write |
| `status` | 房间全景状态 | 只读 |

> **F12 补齐（2026-10-18 真接完）**：第一版只说"按唯一门接线"，实际 `api.py` 只路由了前八个；
> `simulate`/`parity`/`rehearse`/`release` 等八个原语**模块里有、门上没有**
> ⇒ `gate` 永远报「没有房间排练报告」，房间正路走不完。
> 本轮补齐后「排练 → 盖章 → 原子替换」才真能在门上闭环。

---

## 正路闭环

```
    op=create     创建房间
         │
    op=enter      人和 AI 加入
         │
    op=shape      在房间维度写产物
         │
    op=define_plan 固化计划（假设/架构/步骤/验收/回滚）
         │
    op=simulate   静态推演
         │
    op=parity     环境契约核对
         │
    op=rehearse   跑闭环命令（真跑）
         │
    op=gate       门禁：验证全绿才放行
         │
    op=release    一次性写入房间现实区 + 护照
```

**缺任何一环**：`gate` 报「没有房间排练报告」，`release` 不放行。这是**故意的**——房间的价值就在"正路走不完就不许发布"。

---

## API 参考

### 创建并排练一个房间

```python
import gbt_allinone as gbt

# 1) 创建
gbt.run_task("room_space", {"op": "create", "room_id": "feature-ui-v2"})

# 2) 写入产物
gbt.run_task("room_space", {
    "op": "shape",
    "room_id": "feature-ui-v2",
    "path": "index.html",
    "content": "<html>...</html>"
})

# 3) 固化计划
gbt.run_task("room_space", {
    "op": "define_plan",
    "room_id": "feature-ui-v2",
    "assumptions": ["目标环境 Python 3.14"],
    "architecture": "静态页 + 单入口",
    "steps": ["写页面", "本地起服", "截图验收"],
    "acceptance": ["index.html 非空", "无空文件", "有入口"],
    "rollback": "回到上一个时间线"
})

# 4) 推演与核对
gbt.run_task("room_space", {"op": "simulate", "room_id": "feature-ui-v2"})
gbt.run_task("room_space", {"op": "parity", "room_id": "feature-ui-v2"})

# 5) 排练（真跑）
gbt.run_task("room_space", {
    "op": "rehearse",
    "room_id": "feature-ui-v2",
    "command": "python -m http.server 0"
})

# 6) 门禁
result = gbt.run_task("room_space", {"op": "gate", "room_id": "feature-ui-v2"})
# 返回: {ok, checks: {...}, all_green: true/false}

# 7) 发布到房间现实区
gbt.run_task("room_space", {"op": "release", "room_id": "feature-ui-v2"})
```

### 查状态

```python
result = gbt.run_task("room_space", {"op": "status", "room_id": "feature-ui-v2"})
# 返回: {ok, room_id, dimension_files, reality_files, timeline_count, last_gate}
```

### 快照与回放

```python
# 冻结时间线
gbt.run_task("room_space", {"op": "snapshot", "room_id": "feature-ui-v2"})

# 绑视觉帧
gbt.run_task("room_space", {"op": "frame", "room_id": "feature-ui-v2"})
```

---

## 边界（三条，写死）

1. **不删除原有能力**：不覆盖全局 `mirror_space/reality`
2. **不另起 vision_bus**：帧仍走现有 `vision_watch` / `vision_bus`
3. **房间现实区是隔离排练现实**：生产晋升仍必须显式走全局门禁

---

## 与全局镜像空间的关系

| 维度 | `mirror_*`（全局） | `room_space`（房间） |
|---|---|---|
| 影响范围 | 全局 | 单房间隔离 |
| 现实区 | `mirror_space/reality/` | `mirror_space/rooms/<id>/reality/` |
| 时间线 | `mirror_space/timelines/` | `mirror_space/rooms/<id>/timelines/` |
| 护照 | `mirror_space/passports/` | `mirror_space/rooms/<id>/passports/` |
| 生产晋升 | 直接走全局门禁 | 房间内排练 → **再走全局门禁** |
| 能力位形态 | **10 个独立能力位** | **1 个能力位 + 16 op** |

> 最后一行的差别很重要：镜像空间是**十个位**（`mirror_shape` / `mirror_ascend` / …），
> 房间是**一个位带 op**。别把两种形态混着记。

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
