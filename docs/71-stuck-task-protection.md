# 71 · 死循环保护：连续两轮失败的任务标 stuck 并剔除（2026-11-01）

> 主人要「跑到落地、中途不停」。但**一条永远不可能通过的任务**会把链条拖到天荒地老。
> 解法不是"假装它过了"，而是：标 stuck、跳过、如实记账。

---

## 一、规则

```
某任务第 1 轮失败 → 计数 1，下一轮重试
某任务第 2 轮仍失败 → 标 stuck（写 state/blueprints/<id>.stuck.json）
后续轮次 → 跳过该任务（dispatch 的 skip_tasks）
```

**三条纪律**：

1. **不是悄悄吞掉**：stuck 写进账本（`orchestration.record("fix", "blueprint.stuck", ...)`），
   `status` 里能看到 `stuck` 列表；
2. **不冒充落地**：`landed` 仍要求全部任务通过 —— 有 stuck 就 `landed=False`，并说明；
3. **stuck 可追**：文件里记 `counts`（每个任务失败次数）与 `stuck`（已剔除列表），重启后仍生效。

## 二、实测（一条永远失败的任务，跑 3 轮）

```
轮1 dispatched=1 failed=1 stuck_new=None      ← 计数 1，重试
轮2 dispatched=1 failed=1 stuck_new=['实现.1'] ← 计数 2 ⇒ 标 stuck
轮3 dispatched=1 failed=0  stuck_new=None      ← 跳过，不再拖
landed=False · stuck=['实现.1'] · progress=0.0
```

**读法**：它没有"跑完成"，也没有"装完成"——它把死循环掐断，然后把"卡在哪"如实报出来。

## 三、判据（`test_blueprint` 第 [12] 组 5 条）

- 未落地（如实报）
- 任务被标 stuck
- rounds 里记了 stuck 事件
- 后续轮跳过（末轮 failed=0）
- `status` 带 stuck

## 四、边界

- stuck 阈值写死 2 轮（`STUCK_ROUNDS`）；改阈值只改一个常量；
- stuck 任务不会自动"复活"：要重试需删 `state/blueprints/<id>.stuck.json` 或换新蓝图；
- 这条保护只防"永远过不了"，不防"跑得慢"（慢任务靠 `max_rounds` 控制）。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
