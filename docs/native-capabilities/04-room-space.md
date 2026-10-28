# 04 · 房间空间 (`room_space`)

> 19 能力位 · 隔离排练现实 · 镜像多维度空间里的隔离房间
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 核心理念

> 会议室不是外挂服务，也不是第二套视觉总线。
> 它是镜像多维度空间里的一个隔离房间：每个房间都有自己的
> dimension / reality / timelines / passports，
> 复用原有原子写、树指纹、排练命令与视觉帧库。

## 核心闭环

```
    room_create   创建房间（不触碰全局镜像维度）
         │
    room_enter    人和AI加入同一房间
         │
    room_shape    在房间维度里写文件、方案和产物
         │
    room_observe  把当前共享视觉帧绑定到房间事件
         │
    room_plan     固化假设/架构/步骤/验收/回滚
         │
    room_simulate 静态推演
         │
    room_parity   沙盒与目标环境契约核对
         │
    room_rehearse 在房间维度内跑闭环命令
         │
    room_release  全绿后一次性写入房间现实区 + 护照
```

## 能力清单

| 能力位 | 说明 |
|---|---|
| `room_create` | 创建房间（隔离维度、现实区、时间线、护照目录） |
| `room_enter` | 人和AI加入同一房间 |
| `room_shape` | 在房间维度里写文件 |
| `room_scan` | 房间维度体检 |
| `room_observe` | 绑定当前共享视觉帧到房间事件 |
| `room_frame` | 绑定帧ID |
| `room_snapshot` | 冻结房间时间线 |
| `room_replay` | 回放房间快照和帧ID |
| `room_plan` | 固化假设/架构/步骤/验收/回滚 |
| `room_simulate` | 静态推演 |
| `room_parity` | 沙盒与目标环境契约核对 |
| `room_rehearse` | 在房间维度内跑闭环命令 |
| `room_gate` | 房间门禁（验证全绿才放行） |
| `room_release` | 全绿后一次性写入房间现实区+护照 |
| `room_sync` | 同步房间状态 |
| `room_status` | 房间全景状态 |
| `room_namespace` | 房间命名空间注册 |
| `room_registry` | 房间注册表 |
| `room_resolve` | 房间引用解析 |

## API参考

### 创建房间并排练

```python
import gbt_allinone as gbt

# 创建房间
gbt.run_task("room_space", {"op": "create", "room_id": "feature-ui-v2"})

# 写入文件
gbt.run_task("room_space", {
    "op": "shape", "room_id": "feature-ui-v2",
    "path": "index.html", "content": "<html>...</html>"
})

# 排练
result = gbt.run_task("room_space", {
    "op": "rehearse", "room_id": "feature-ui-v2",
    "command": "python main.py"
})

# 发布（全绿才放行）
result = gbt.run_task("room_space", {
    "op": "release", "room_id": "feature-ui-v2"
})
```

## 边界

1. **不删除原有能力**：不覆盖全局`mirror_space/reality`
2. **不另起vision_bus**：帧仍走现有`vision_watch`/`vision_bus`
3. **房间现实区是隔离排练现实**：生产晋升仍必须显式走全局门禁

## 与镜像空间的关系

| 维度 | mirror_space | room_space |
|---|---|---|
| 影响范围 | 全局 | 单房间 |
| 现实区 | `mirror_space/reality/` | `mirror_space/rooms/<id>/reality/` |
| 时间线 | `mirror_space/timelines/` | `mirror_space/rooms/<id>/timelines/` |
| 护照 | `mirror_space/passports/` | `mirror_space/rooms/<id>/passports/` |
| 生产晋升 | 直接走全局门禁 | 房间内排练 → 再走全局门禁 |

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
