# 20 · 人工授权门 (`auth_gate`)

> 15 作用域 · 时段授权 / 一次性授权 · AI 永远无权发放
>
> 门是"主人的开关"，不是"技术限制"——门开着，技术全在。
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 核心设计

> 默认拒绝的能力不给AI绕过入口——要放行只能由人亲手授权，
> AI的任何调用路径（run_task / 工作流 / autopilot / 长程任务）都无权创建授权。

### 授权的唯二来源

1. **CLI交互确认**：`auth grant` 命令，终端人工输入 `YES`
2. **主人手写授权文件**：`store/auth_grants.jsonl` 追加一行，格式严格校验

## 15 个作用域

| 作用域 | 说明 | 消耗方式 |
|---|---|---|
| `osint_private` | OSINT扫描自有内网/保留地址 | 一次性 |
| `owner_control` | 主人总控：一条可替代该次动作所需全部未授权作用域 | 一次性 |
| `process_execute` | 启动进程、执行命令或连接MCP/终端服务器 | 时段 |
| `filesystem_write` | 写入、移动、删除或自动整理文件 | 时段 |
| `remote_device` | 启动/停止远程设备中继或外部接管通道 | 一次性 |
| `deploy_publish` | 部署、晋升、回滚或写入生产交付区 | 一次性 |
| `deploy_force` | 强制放行（未全绿晋升/未声明落点/公网中继） | 一次性 |
| `network_private` | 访问本机、内网、保留地址或非标准端口 | 时段 |
| `browser_control` | 操控系统浏览器或自动化浏览器 | 时段 |
| `desktop_control` | 桌面触手的输入、鼠标、键盘与窗口控制 | 时段 |
| `device_control` | 连接、写入或控制蓝牙及其他外部设备 | 时段 |
| `external_llm` | 把当前任务数据发送到外部大模型服务 | 时段 |
| `data_export` | 把数据发送到外部服务或持久化到框架外 | 一次性 |
| `privacy_read` | 读取屏幕、摄像头、麦克风或隐私载体 | 时段 |
| `audio_output` | 让本机发声（TTS合成/播放）或写入音频产物 | 时段 |
| `audit_read` | 读取审计、授权或运行历史 | 时段 |

## 三道护栏（只剩这些要票）

Owner 2026-10-19 定：**除了黑客全能力和转账要票，其他都去掉**。

| 组 | 作用域 | 说明 |
|---|---|---|
| **G1 黑客全能力（7）** | `browser_control` · `desktop_control` · `device_control` · `network_private` · `privacy_read` · `process_execute` · `remote_device` | 操控浏览器/桌面/外设/网络/隐私/进程/远控 |
| **G2 转账/付款（3）** | `audio_output` · `data_export` · `external_llm` | 常走外部服务、可能计费 |
| **G3 生产面板（2）** | `deploy_publish` · `deploy_force` | 部署/晋升/回滚/强制放行 |

**不在里面的作用域，一律直接放行**（记 `auto_passed`，进审计），不再要票。

## 授权分级

### 时段授权（日常技术动作）

TTL内可多次用，用一次在账本里记一次：

```json
{"scope": "process_execute", "granted_at": "2026-10-28T07:00:00", 
 "ttl": 600, "mode": "window", "reuse_count": 3, "last_used_at": "..."}
```

**为什么改**：改前实测 `voice → denied · 账本0行`——一次性消耗放在 `audio_output` 这类日常动作上，等于"每说一句话回终端敲一次YES"，语音对讲在物理上不可用。

### 一次性授权（危险动作）

用掉即从账本删行：

```python
ONE_SHOT_SCOPES = {"owner_control", "deploy_publish", "remote_device", 
                   "data_export", "deploy_force"}
```

## CLI 用法

### 发放授权

```bash
# 时段授权（10分钟）
python -m gbt_allinone auth grant --scope process_execute --ttl 600
# 终端提示: 确认发放? 输入 YES:

# 一次性授权（危险动作）
python -m gbt_allinone auth grant --scope deploy_publish --ttl 600

# 总控授权（替代该次全部未授权作用域）
python -m gbt_allinone auth grant --scope owner_control --ttl 600
```

### 查看状态

```bash
python -m gbt_allinone auth status
# 输出:
# scope              available  mode      expires
# process_execute    1          window    2026-10-28T07:10:00
# deploy_publish     0          -         -
# ...
```

### 撤销授权

```bash
python -m gbt_allinone auth revoke --scope process_execute
```

## 手写授权文件

```jsonl
// store/auth_grants.jsonl
{"scope": "process_execute", "granted_at": "2026-10-28T07:00:00", "ttl": 600, "mode": "window"}
{"scope": "deploy_publish", "granted_at": "2026-10-28T07:00:00", "ttl": 600, "mode": "one_shot"}
```

格式严格校验，不合规即拒。

## API参考

```python
import gbt_allinone as gbt

# 只读查状态
result = gbt.run_task("auth_gate_status", {})
# 返回: {
#   ok, scopes: {
#     process_execute: {available: 1, mode: "window", expires: "..."},
#     deploy_publish: {available: 0}
#   }
# }
```

## 纪律

1. **AI永远无权发放授权**——`auth_gate.py` 没有任何可供 `run_task` 调用的"创建授权"入口
2. **授权只能主人在终端发放**，或主人手写授权文件
3. **缺授权就如实报缺什么**，不许找旁路、不许改 `security/policy.py`
4. **分级改的是"用几次"，没碰"谁能发"这条红线**

## 审计留痕

| 事件 | 说明 |
|---|---|
| `auth_grant` | 授权发放（谁发的、什么作用域、TTL） |
| `auth_check` | 授权校验（通过/拒绝） |
| `auth_consume` | 授权消耗（时段授权记 reuse_count） |
| `auth_revoke` | 授权撤销 |
| `auto_passed` | 不在护栏内的作用域自动放行 |

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
