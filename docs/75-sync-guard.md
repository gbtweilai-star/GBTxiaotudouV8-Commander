# 双仓同步巡检（sync_guard）

> 2026-11-01 · `sync_guard` 原生位：把「交付树 ↔ live 工作仓」的对账做成可调用、可巡检、可进工作流的能力位。
> 依赖 `tools/codex-scripts/two-way-sync.py`（计划器）与 `tools/two-way-sync.ps1`（执行器，见 `74-two-way-sync.md`）。

## 一、能力位契约

| op | 作用 |
|---|---|
| `status` | 只报差异：only_live / only_delivery / differ 计数 + 前 20 条路径 |
| `verify` | 判 **ALIGNED**（only_live=0 · differ=0 · 两边 cap 计数相等）；DRIFT 出 alerts |
| `patrol` | verify + 可选写 `state/sync_guard.jsonl` 运行台账（`record=true` 才写） |
| `where` | 入口/默认路径/命令 |

**只读**：不自动 pull/push；修复交给 `tools/two-way-sync.ps1`（防自动覆盖）。
交付树路径默认 `~/Desktop/GBT小土豆V8`，可用 payload `delivery=...` 或环境变量 `GBT_DELIVERY` 覆盖。

## 二、调用

```powershell
# 直接调能力位（唯一门）
py -3.14 -c "import sys;sys.path.insert(0,'.');from gbt_allinone import api;print(api.run_task('sync_guard',{'op':'verify'}))"

# 巡检并落台账（live 侧才写 state）
py -3.14 -c "import sys;sys.path.insert(0,'.');from gbt_allinone import api;print(api.run_task('sync_guard',{'op':'patrol','record':True}))"
```

返回要点：`ok` / `verdict`（ALIGNED|DRIFT）/ `alerts[]`（`sync_drift`、`caps_mismatch`）/ `reading`
（计数 + 前 20 条路径）/ `fix`（下一句命令）。

## 三、进工作流（DAG）

```python
from gbt_allinone import api
nodes = [
    {"id": "guard", "kind": "sync_guard", "params": {"op": "verify"}},
    {"id": "voice", "kind": "alerts", "params": {}, "depends_on": ["guard"]},
]
print(api.run_task("wf_define", {"name": "双仓同步巡检", "nodes": nodes}))
print(api.run_task("wf_run", {"name": "双仓同步巡检"}))      # 结果如实落 state/wf_runs
```

- `guard` 失败（DRIFT）时，DAG `fail_fast` 默认 True 会停；`voice` 只在上游 ok 时读近期异常。
- 定时：项目里用调度/引擎的定时位（如 `engine` 域或外部计划任务）每天跑一次
  `api.run_task('wf_run', {'name':'双仓同步巡检'})` 即可；**没有自动 push**。

## 四、告警口径

| alert | 触发 | 处置 |
|---|---|---|
| `sync_drift` | only_live ≠ 0 或 differ ≠ 0 | `tools\two-way-sync.ps1 status` 看差异 → `pull -Apply` 或 `push -Apply -Refresh` |
| `caps_mismatch` | 两边 `data/capabilities.json` 计数不等 | 先对齐源码，再跑刷新链（export/docs/pages/authz） |

## 四·五、主动喊（notify）与定时巡检

```powershell
# 巡检 + 台账 + 写审计（DRIFT→error；ALIGNED→ok，alerts 能读到/标恢复）
py -3.14 -c "import sys;sys.path.insert(0,'.');from gbt_allinone import api;print(api.run_task('sync_guard',{'op':'patrol','record':True,'notify':True}))"

# 一条命令跑巡检（适合 Windows 计划任务；ALIGNED=0，DRIFT=1）
powershell -NoProfile -ExecutionPolicy Bypass -File tools\sync-guard-patrol.ps1
```

**桌面/外部推送**：DRIFT 且 `notify=true` 时按环境变量优先级推送——`GBT_SYNC_PUSH_WEBHOOK`（任意 JSON POST，n8n/自建网关）→ `GBT_FEISHU_WEBHOOK`（飞书群机器人）→ `GBT_N8N_WEBHOOK`（n8n）；都没配就弹 Windows 桌面通知（WinRT toast，子进程无包身份时退回托盘气泡）。`push=false` 可关。

**配置推送（写 `state/`，计划任务也能读）**：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\setup-sync-push.ps1 -Webhook "https://.../hook" -Test
powershell ... -Feishu "https://open.feishu.cn/open-apis/bot/v2/hook/xxxx"
powershell ... -N8n "http://127.0.0.1:5678/webhook/gbt"
powershell ... -Clear
```
环境变量优先；文件 `state/sync_push.json` 兜底（计划任务不继承临时 env）；URL 属凭据，只写 state/、不进源码交付、控制台掩码显示。

**补开机触发（需管理员）**：`tools\setup-boot-trigger.ps1`；非管理员只打印提权命令、不动系统。

**登录自启（免管理员）**：`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\GBT-SyncGuard.cmd` 已放启动项，登录即跑一次 patrol；6 小时重复由计划任务负责。

**项目调度**（不依赖 Windows 任务）：

```python
from gbt_allinone import api
nodes = [
    {"id": "guard", "kind": "sync_guard",
     "params": {"op": "patrol", "record": True, "notify": True}},
    {"id": "voice", "kind": "alerts", "params": {}, "depends_on": ["guard"]},
]
api.run_task("wf_define", {"name": "双仓同步巡检", "nodes": nodes})
api.run_task("sched_define", {"name": "双仓同步巡检", "workflow": "双仓同步巡检",
                              "every_seconds": 86400})
api.run_task("sched_tick")     # 到期就执行；常驻循环/计划任务定时喂 tick 即可
```

**Windows 计划任务**（当前注册 `GBT-SyncGuard`：每 6 小时一次，退出码 1=DRIFT 在任务历史可见；开机/登录触发需管理员权限，必要时提权补）：

```powershell
schtasks /Create /SC HOURLY /MO 6 /F /TN "GBT-SyncGuard" ^
  /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File \"C:\Users\Lenovo E14 Gen 5\Desktop\GBT小土豆V8\tools\sync-guard-patrol.ps1\""
```

> `notify` 只在能写 `state/` 的 live 侧真正落审计；交付树只读时返回 `not_written`，不假装成功。

## 四·七、心跳：巡检 + 到期工作流共用

`tools\sync-guard-patrol.ps1`（以及 `sync-guard-run.py`）现在在巡检后**自动跑一次 `sched_tick`**：
- 巡检：`sync_guard patrol(record,notify)` → 对账/审计/推送；
- 心跳：`sched_tick` → 执行**到期**的调度工作流（如 `双仓同步巡检` 21600s、`爆款拆解流水线` 86400s）；
- 输出多一个 `sched: {ran, count}`；退出码仍只看巡检（ALIGNED=0 / DRIFT=1）。
- 共用定时源：Windows 计划任务 **GBT-SyncGuard**（每 6h，工作目录=live）+ 登录启动项 `Startup\GBT-SyncGuard.cmd`。
- 实测：`-Repo <live>` 跑 `sched: {ran: [], count: 0}`（当时无到期项）；`sched_status` 两条调度均 `last_status=ok`。
- 无人登录：管理员跑 `tools\setup-system-task.ps1` → `GBT-SyncGuard-System`（SYSTEM/开机/6h，共用同一 runner）；非管理员只打印提权命令。
## 五、边界（如实）

- 运行数据 `state/`、权重/引擎 `vendor/`、归档/退役**不参与对账**（计划器排除），所以 ALIGNED 只代表**源码面**对齐。
- 交付档案（`整理报告/`、`整理说明.md`、`MANIFEST.json`）只留交付树，不参与 push；所以 `only_delivery` 可能非空但被判为"档案"，不计入 DRIFT。
- `patrol` 写台账只在 live 侧；交付树运行时若 `state/` 不可写会返回 `not_writable`（不假装写成功）。
- 工具/判据：`tests/test_sync_guard.py`、`tests/test_two_way_sync.py`；现读 `verify` = **ALIGNED（368/368）**。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
