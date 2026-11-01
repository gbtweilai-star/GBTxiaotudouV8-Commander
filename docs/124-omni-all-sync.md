# 124 · 万能插：全部能力全开 + 同步执行

> 主人 2026-11-02：「把万能插的全部能力设为同步执行，必须每次使用都是打开全部能力。」

## 一、口径（写死）

| 项 | 做法 |
|---|---|
| **全开** | 每次使用枚举**全部 385 个能力位**（一个不漏），`full_open=true`；子集只用于测试/排查 |
| **同步** | 按顺序逐个在独立子进程执行（不并发、不异步），带超时；超时 kill |
| **需授权位** | 85 个需授权位**没票不执行**，进 `blocked_by_ticket`（打开但被票挡，不假装跑过）；带票才执行 |
| **留痕** | 每轮写 `state/omni-plug.json`（含逐条结果）+ `state/omni-plug.jsonl` + orchestration-ledger |
| **进度** | 执行中每 5 个位更新一次 state（`running=true, progress=N`），界面可轮询进度 |

## 二、实现

- `gbt_allinone/omni_all.py`：`run_all_sync(caps=None, timeout, ticket)`；
- `tools/omni-run.py`：CLI 全开执行 / `--status`；
- `POST /api/omni`：`confirm=true` 后台起全开执行（不阻塞 HTTP）；`op=status` 查进度；
- `#plug`（万能插）视图：**「全开同步执行（385 位）」**按钮 + 实时状态条（全开数/ok/fail/票挡/耗时）。

## 三、实测

```
口径：注册表 385 位，全开 = caps=None（full_open=True）
子集自测：body_map / body_see / body_say 顺序执行，results 顺序 == 入参顺序（同步，无并发）
票挡：需授权位 hand_bridge 无票 → executed=0，进 blocked_by_ticket（不假装执行）
落盘：state/omni-plug.json + jsonl 都写
API：POST /api/omni {confirm:true} → started run_id + pid；op=status 可查（跑的过程中显示 progress）
tests/test_omni_all.py ALL OK
```

## 四、真跑一轮全开（2026-11-02 02:19）

```
run_id 20261102-021542 · full_open=true · caps_opened=385
executed=300（85 个需授权位无票，进 blocked_by_ticket）
ok=251 · fail=49 · elapsed=224,446ms（约 3.7 分钟，同步逐个）
```

失败位如实统计（49 个），不折叠成成功。跑完自动清掉某能力位写进仓根的 `gbt_cross_scan*` 临时产物，
避免污染后续巡检（此前曾让 inventory/blueprint/chain_kernel 三个测试误红，已复跑转绿）。

## 五、边界（如实）

- 全开 385 位**耗时不短**（每位的子进程耗时累加）；界面轮询显示进度，不假装秒完；
- 需授权位（85）没票只"打开"不执行——这是危险边界，不能因为"全开"就绕；
- 全开执行结果里失败的位会如实统计 `fail_count`，不折叠成成功。

## 五、下一步

1. 全开结果按域/职业汇总（哪个域失败多）；
2. 把全开同步执行接到"万能插每次使用"的默认动作（已做 UI 按钮；如需自动触发可加开关）；
3. 对失败位做自动重试（有上限）并写重试账本。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
