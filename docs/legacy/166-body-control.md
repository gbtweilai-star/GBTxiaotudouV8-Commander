# 166 · body_control（身体控制 / 触手 / 全息投影）—— 如实报缺

> 主人 2026-11-02 定名与纪律：
> 「这个能力域叫 body_control（身体控制/触手/全息投影），我现读：not_supported（未接线）。
> 深度学习 + 无模型不等于能动——缺感觉/缺执行器（未绑定或已被主人拔掉）时如实报缺，不假装能动。」

## 一、我们落成的（只读状态，不驱动硬件）

| 件 | 落点 |
|---|---|
| 模块/契约 | [`gbt_allinone/tools/body_control.py`](../../gbt_allinone/tools/body_control.py) · `verify()` **17 项** |
| 统一门 | 注册能力位 **`body_control`**（zero-scope 状态/清单；`policy.py` 未改） |
| API | `GET/POST /api/body`：status / inventory / verify / move；真实读 `state/body_control.json`（不存在=未绑定） |
| APP 接线 | console 右栏「身体控制 / 触手 / 全息投影」状态块：`not_supported` + 缺项 + `wired=false` |
| 验收 | [`tests/test_body_control.py`](../../tests/test_body_control.py) |

## 二、状态口径（没有 ready）

| 绑定情况 | status | 说明 |
|---|---|---|
| 感觉和执行器都没绑 | **not_supported** | 未接线；缺项全部列出 |
| 只有部分感觉 | not_supported | 有感觉没执行器，仍不能动 |
| 只有执行器没感觉 | not_supported | 不能闭环，仍报缺 |
| 全绑（bindings 全 true） | **partial** 且 `wired=false` | 本件没有执行器驱动/安全闭环，动作**仍不执行** |

- 传感器：`camera / microphone / screen / depth / tentacle_bus`
- 执行器：`tentacle_bus / holographic_projection / digital_human_display / robot_arm`
- `move()` **永远** `{ok:false, status:"not_supported", executed:false}`，带原因，不伪造动作回执。

## 三、真机读数（2026-11-02 APP）

`GET /api/body` → `status=not_supported · wired=false · executor=not_wired`；缺感觉 5 项、缺执行器 4 项；右栏显示同一读数。`POST /api/body {"op":"move","action":"wave"}` → `ok=false · executed=false · reason=body_control 未接线…`。

![body_control 如实 not_supported（APP 真机右栏）](../assets/app-focus-body.png)

## 四、边界（说死）

1. 本件**不驱动任何硬件**；没有真实执行器与安全闭环前，永远不出现 ready；
2. `state/body_control.json` 只是绑定声明面；即使全 true 也只 partial，动作仍拒；
3. 没有新增出网/进程/写盘；注册为 zero-scope 状态口；
4. 真正的身体动作要另建执行器链 + 安全门 + 急停/权限，本轮不做、也不假装。

## 五、复跑

```bash
py -3.14 -X utf8 tests/test_body_control.py
# GET/POST http://127.0.0.1:8766/api/body
```

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
