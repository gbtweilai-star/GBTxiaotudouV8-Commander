# 132 · 万能插（omni_plug）能力默认开合审计

日期：2026-11-02 · 入口：`GET /api/omni?op=status|sockets|energy|selftest`

## 审计结论：不是“默认全开”，按设计分层
| 插座 | 默认状态 | 实测 |
|---|---|---|
| process | ✅ 开（真执行） | `plug_and_run('py:print(6*7)')` → rc=0 stdout=42 |
| file | ✅ 开（读）/ 写限 projects·outputs·.scratch | read README ok · write outputs/.omni-audit.txt ok |
| api / web | ✅ 协议开；**HTTPS 需 CA** | 原报 CERTIFICATE_VERIFY_FAILED；装 certifi 并设 SSL_CERT_FILE 后 `https://example.com/` → ok |
| ai | ⚠️ 半开：可插 https，但没有钥匙 | 4 个钥匙槽（GBT_LLM/ABLITERATION/OPENAI/DEEPSEEK）全未配 → 只能 plug，不能输能 |
| app | ⚠️ 半开：要窗口 + privacy_read | CLI 审计时当前会话窗口数 0 → “先 plug 成功再驱动”；桌面进程里需过 privacy_read 票 |
| dh（数字人执行器） | ✅ 开（仅 app 服务进程注册） | `/api/dh/status` 里 `omni_plug.plugged=true`，帧帧走执行器 |

## 自检
- `op=selftest`：`ok=true`，插上 5 个插座，真驱动 `print(6*7)`→42、端点拼接 9/9 全对；
- 唯一“失败”是反向用例 `not_a_kind`（故意喂非法类型，验证 fail-closed），不是缺陷。

## 仍按主令保留的人工门
- G1 隐私：`privacy_read`（读屏/摄像头/麦克风）；
- 付款：`external_llm` / `data_export`；
- 生产面板：`deploy_publish` / `deploy_force`；
- 机制层：`filesystem_write`（写盘自收窄到 projects/outputs/.scratch）、`process_execute`。
- `desktop_control` 已按 2026-11-01 主令移出人工门（身体能力，不再要票）。

## 本次改动
- `tools/console-server.py` 启动时自动加载 certifi CA（便携 Python 自带 CA 不全的根因修法）；
- certifi 同步进桌面版 `payload/pyembed`，应用已重启。
