# @gbt/dsh-cap-bridge

GBT小土豆V8 给 DeepSeek Harness 的**插件统一入口**。
它不碰 DSH 环境：不改 `dsh-home`、不改 `profiles/*`、不手塞 `node_modules`；
装/卸都走 DSH 自己的 `dpx plugin add/remove`。

## 它给 DSH 什么

| 工具 | 作用 | 是否改状态 |
|---|---|---|
| `gbt_caps` | 列出 428 个能力位，可按 `domain` / `keyword` 收窄 | 只读 |
| `gbt_cap` | 调一个能力位（`kind` + `payload`） | 取决于能力位：`safe: true` 直接过，其余必须 `confirm: true` |
| `gbt_health` | 桥在线状态、能力位总数、令牌文件位置 | 只读 |

## 三步装上（不改编她的环境）

```powershell
# ① 打 tarball（在 GBT 仓根）
.\pyembed\python.exe plugins\dsh\pack.py

# ② 先看会做什么（只打印，不落盘）
dpx plugin add --eac-beta `
  "C:\Users\Lenovo E14 Gen 5\Desktop\GBT小土豆V8\plugins\dsh\dist\gbt-dsh-cap-bridge-0.1.0.tgz" `
  --profile web-desktop --dry-run

# ③ 确认无误再真装
dpx plugin add --eac-beta `
  "C:\Users\Lenovo E14 Gen 5\Desktop\GBT小土豆V8\plugins\dsh\dist\gbt-dsh-cap-bridge-0.1.0.tgz" `
  --profile web-desktop
```

卸载同理：`dpx plugin remove --eac-beta @gbt/dsh-cap-bridge --profile web-desktop`。

## 起桥（GBT 侧，独立进程）

```powershell
.\pyembed\python.exe plugins\dsh\bridge\gbt_bridge.py
# 默认 http://127.0.0.1:8790；令牌自动生成：
#   state\dsh-plugin\bridge-token
```

插件默认读同一个地址与令牌文件；要换口/换令牌用环境变量：

- `GBT_DSH_BRIDGE`（插件侧，默认 `http://127.0.0.1:8790`）
- `GBT_DSH_BRIDGE_PORT` / `GBT_DSH_BRIDGE_TOKEN_FILE`（桥侧）

## 安全边界

- 桥**只绑回环**，非 `127.0.0.1/::1` 直接 403。
- `GET /caps`、`POST /run` 都要 `x-gbt-token`；`GET /health` 只回在线读数。
- **只读优先**：注册表里 `safe: true` 的能力位直接执行；`safe: false` 的返回
  `403 need_confirm`，必须重发 `confirm: true`。桥不替调用方猜“这次算不算改状态”。
- 桥只是**转发**：`gbt_allinone.api.run_task()` 原有的作用域/授权/审计门照旧生效，
  不会因为走了插件就多出权限。

## 它刻意不做的事

- 不把 GBT 的密钥/令牌回传给 DSH；
- 不缓存任何能力结果（除能力名清单）；
- 不在 DSH 侧落任何状态文件。
