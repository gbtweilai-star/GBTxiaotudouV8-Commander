# 84 · 远程接管授权内核（remote_controller）

> 2026-11-01 · 主人硬规矩：**接管电脑控制器做远程协助，必须远端用户点击同意授权。**
> 这不是“动作 API”，也不是“静默远控”；先把**同意**做成硬门。

## 一、两码事

| 单纯操控（RPA） | 接管控制器（远程协助） |
|---|---|
| 发点击/键盘/截图 | 拥有远端会话：屏幕、输入、剪贴板、语音、进程/OS 控制 |
| 一次性动作 | 会话级所有权，可撤销、可审计、可重连 |
| 不需要远端人同意 | **必须远端用户显式点击同意** |

本件只做第二件的**授权层**；媒体/隧道层还没接，不冒充。

## 二、状态机

```
request  → pending（一次性 code + agent_secret，只交给远端 agent）
approve  → approved（必须 remote_user.confirmed=true + 持 secret 的 HMAC 签名；请求方不能自批）
session  → session（只有 approved/未撤销/未过期才发；否则 denied）
revoke   → revoked（立即失效，下次必须重新同意）
audit    → 每条 request/approve/deny/session/revoke 留痕
```

硬门：
- 请求方自己 approve ⇒ `needs_remote_consent` / `bad_signature`；
- code 错/过期/重复批准 ⇒ 拒；
- 未批准就 `session` ⇒ `denied`；
- 撤销后再 `session` ⇒ `denied`。

## 三、实测（`tests/test_remote_controller.py` ALL PASS）

- 只 request，session 被拒；
- 无远端 confirmed → 拒；有 confirmed 但无 agent 签名 → 拒；
- code 错 → 拒；
- 远端 agent 签名 + 用户确认 → approved → session；
- revoke 后 session 拒；audit 有记录。

## 四、还没接的（不假装）

- **媒体通道**：屏幕帧、输入注入、剪贴板、语音；
- **传输**：远端 agent GUI、端到端加密、公网 relay/永久隧道；
- **OS 级控制**：UAC/安全桌面、多屏、文件传输、进程服务控制。

这些必须在“同意内核”之上单独建；没有远端同意，任何通道都不开。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
