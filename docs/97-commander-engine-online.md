# 97 · 本机指挥官大模型接入（2026-11-01 闭环验收）

> 主人令：「把我们的无限制指挥官大模型接入我们这里」
> 结论：**引擎已起、框架已用、读数已核**。下面每个数字都是现读。

## 一、接的是什么

| 项 | 读数 |
|---|---|
| 权重 | `gbt-v8-v82-q5_0.gguf`（5.24 GB） |
| 引擎 | `vendor/llama-server.exe`（llama.cpp 官方 Windows 包） |
| 监听 | `http://127.0.0.1:8792`（OpenAI 兼容：/v1/chat/completions、/v1/models） |
| 健康 | /health = `ok` |
| 模型 id | `['C:\\Users\\Lenovo E14 Gen 5\\Documents\\deepseek-harness\\default-workspace\\GBTxiaotudouV8-Commander\\GBTxiaotudouV8-Commander-main\\state\\weights\\gbt-v8-v82-q5_0.gguf']` |
| 启动参数 | `-c 4096 -t 12 -ngl 0 --no-webui --sleep-idle-seconds 600`（4 slots，纯 CPU） |

## 二、闭环验收（真问真答）

| 路径 | 结果 |
|---|---|
| `energy_core.think()`（唯一取电口） | ok，9.9 秒，prompt 41 / completion 40 tokens，4.0 tok/s |
| `commander.ask()` | ok，9.0 秒，模型返回中文回答 |
| `commander.route()`（模型真选能力位） | ok，选中 `legacy_guard`（confidence 0.997，1011 prompt tokens；CPU 上 123.6s — 是这个模型在本机的真实速度） |
| 回答样例 | 「定制模型 v2.12：DPO 9B，加载在 **GBT小土豆V8**（gbt_allinone，V8.2.2.17）」 |

## 三、顺手抓到并修掉的真问题

`trunk_reason advise` 在接入后立刻报 **P0 假绿**：

> `dispatch_gap`：有能力的 handler 不在分派表内 —— 登记了却调不到，等于假绿。
> 具体：[('mcp_health','mcp_bridge'), ('mcp_register','mcp_bridge'), ('mcp_servers','mcp_bridge'), ('mcp_unregister','mcp_bridge')]

根因：上一轮新增的 4 个 MCP 能力位，registry 里 handler 写的是 `mcp_bridge`，而 api 是按 kind 分派。
**修法**：handler 改成各自的 kind（`mcp_register` / `mcp_servers` / `mcp_unregister` / `mcp_health`）。
复测：P0 清零，`trunk_reason` 从 red(91.7) → **yellow(100.0)**，只剩 1 条 P1（state_flip，下一跳复核）。

## 四、怎么启停（双击即可）

| 脚本 | 作用 |
|---|---|
| `tools/engine-on.cmd` | 起引擎（幂等：已在服务就复用，不重复起第二个进程） |
| `tools/engine-off.cmd` | 停引擎（只停本仓起的那个 pid，不误杀别的服务） |

命令行等价：
```bash
python -c "from gbt_allinone.tentacle import commander as C; print(C.start(wait=180))"
python -c "from gbt_allinone.tentacle import commander as C; print(C.stop())"
```

## 五、接进 DSH（本会话）的说明

引擎是 **OpenAI 兼容**的：`http://127.0.0.1:8792/v1/chat/completions`。
DSH 侧要用它当模型，需要在 `~/.dsh/profiles/web/cordis.patch.yml` 里加一个 provider（pi-ai 适配），
这会动到当前 GUI 的 profile —— **没有主人点头我不擅自改**；要接就说一声，我改完就地验证再回滚说明。

## 六、边界（如实）

- 纯 CPU、`-ngl 0`：长 prompt 的首字延迟很高（1011 tokens ≈ 123s），适合**短指令 + 明确候选**
  （route 只回一个能力名，3 个 completion tokens）；
- 模型对"自我介绍"类开放问题会答得飘（样例见上），但**路由/取数/记账**这类确定性任务稳定；
- 熔断器已挂：连续 3 次失败 60s 内 ⇒ open 30s，不会让 40 个触手各等 300s。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
