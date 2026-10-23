---
name: gbt-potato
displayName: GBT小土豆V8 数字人
description: 启动 / 停止 / 重启 / 自检 GBT小土豆V8 桌面数字人（holo_pet 面板 + 桌面壳），并读它的只读面（面板状态 / 能力总目录 / 项目树 / 旁观者）。当用户说「启动数字人」「打开小土豆」「面板」「桌宠」，或面板连不上、要重启面板、要看能力清单时使用。
triggers:
  - "启动数字人"
  - "打开小土豆"
  - "数字人"
  - "桌宠"
  - "面板"
  - "holo_pet"
  - "重启面板"
---

# GBT小土豆V8 数字人

用户入口只有一个：**`holo_pet`**（3D 数字人面板 + Electron 桌面壳）。
工作区根：`C:\Users\ADMIN\Desktop\GBT小土豆V8`

## 一、启动 / 重启（**默认用重启那个，不要用原启动器**）

```
holo_pet\restart-digital-human.bat     ← 一键重启：先关 8765 上的旧面板，再起新的
holo_pet\启动桌面数字人.bat              ← 原启动器（总是再起一个进程，旧的不关就不生效）
```

**为什么默认用重启版**：原启动器总是 spawn 一个新面板进程，但 `launch_panel.py` 发现
`127.0.0.1:8765` 已被占用时会**复用旧的** ⇒ 改了代码却不生效。

桌面上有同名快捷方式，指向的就是 `restart-digital-human.bat`。

## 二、自检

```
py -3.10 holo_pet\deploy_check.py        # 逐解释器依赖矩阵 + 启动件 + 面板 + 凭据
```

## 三、只读面（面板在跑时可直接读）

| 地址 | 用途 |
|---|---|
| `GET 127.0.0.1:8765/api/state` | 聚合状态（内核 / 心智 / 设备 / 能力层） |
| `GET /api/capabilities` | 能力总目录：现读 **158 项（147 可用 / 11 禁用 / 30 域）** + APP 自身路由 |
| `GET /api/tree?depth=3` | 项目树（只给目录名与文件大小，噪声目录已截断） |
| `GET /api/observer` | 旁观者：握手状态 / 只读档是否配上 / 三件职能出声 / 卡点 |
| `GET /api/events` | SSE 事件流（带 `boot+seq`，重连只补差量） |

写入口（都走她自己的策略层，面板不放宽任何作用域）：

```
POST /api/message          受理一句话（幂等：client_msg_id / 文本指纹）
POST /api/capability       {kind, payload, confirm} 通用能力调用
POST /api/observer/voice   {kind, text} 旁观者出声 —— 只收「提醒 / 意见 / 建议」，零执行权
```

## 四、已知约束（**约束 ≠ bug**，都是实测过的）

1. **面板必须由主人双击启动**：沙箱身份（`codexsandboxoffline`）**没有出站网络**
   （`WinError 10013`），且**停不掉主人身份的进程**（Access denied）⇒ 代理代劳会得到
   一个"连不出去"的面板。GUI 窗口同理：沙箱起的窗口主人看不见。
2. **控制台是 GBK**：入口脚本必须 `sys.stdout.reconfigure(encoding='utf-8')`；
   `.bat` 只用 ASCII（含中文注释会被读歪）。
3. **DPAPI 保险箱绑定用户**：`store/secrets/*.dpapi` 跨 Windows 用户**解不开**，
   所以保险箱只能由主人身份写。
4. **3.12 起不来**是本机环境约束（首选 3.10）。

## 五、大脑与密钥

- 密钥链首位 = **agnes**（Custom Provider · `https://apihub.agnes-ai.com/v1` · `agnes-2.5-flash`），
  由环境变量 `AGNES_API_KEY` 提供；失败会在进程内冷却 5 分钟并**自动降级**到 deepseek。
- 想临时改回：设 `GBT_LLM_PROVIDER=deepseek`。
- 密钥落保险箱（由主人身份执行，密钥走 stdin，不进 argv/日志）：

```
"sk-真钥" | py -3.10 -m gbt_allinone.deepseek_key set --profile agnes
py -3.10 -m gbt_allinone.deepseek_key status --profile agnes
```

## 六、验收口径

面板起来之后，最硬的两条证据是：

1. `GET /api/state` → **HTTP 200**
2. 日志/事件里出现 `brain resolved: provider=AGNES_API_KEY model=agnes-2.5-flash`

只看到面板 200 不代表大脑通了；只看到解析成 agnes 不代表网络通 —— 两条都要。

---

## 七、报告层红线（读数纪律，别把"读错地方"报成故障）

1. **约束 ≠ bug**：§四那四条是**实测过的环境约束**（沙箱无出站网、控制台 GBK、DPAPI 绑用户、3.12 起不来）。
   把它们报成"面板坏了"是误报。
2. **HTTP 200 ≠ 大脑通**：`/api/state` 返回 200 只证明**面板进程活着**；
   大脑通不通要看 §六 第 2 条那句 `brain resolved: provider=…`。**两条都要，不许只报一条。**
3. **沙箱身份起的面板不算数**：沙箱身份**没有出站网络**（`WinError 10013`）且**停不掉主人身份的进程**
   ⇒ 那样起出来的面板是"连不出去"的，**不许拿它当验收证据**。
4. **进程在 ≠ 窗口在**：GUI 窗口主人看不见时，等于没起来。
5. 🔴 **任何能力数一律现读现报，不许引用旧读数** —— 本件 §三 那行数字**就是被现读推翻过的**
   （旧写 108 / 97 / 22，现读 158 / 147 / 30，见 §八）。

---

## 八、未验账（**本件自己没验过什么，别当成验过**）

**先说本件验过的那部分（2026-09-22 现读）**：
`127.0.0.1:8765` **有 1 条 LISTEN**（面板在跑）· `GET /api/state` → **HTTP 200 / 8,107 B** ·
`GET /api/capabilities` → **200 / 50,188 B**（`total 158 · enabled 147 · disabled 11 · domains 30`）·
`GET /api/observer` → **200 / 3,539 B**（`status: wired_not_verified` · `handshake: stale` · `handshake_at 2026-09-19`）·
`py -3.10` → **Python 3.10.11（在）** · `holo_pet` 三个启动/自检件都在盘上。

**没验过的（逐条）**：

| # | 没验什么 | 为什么 |
|---|---|---|
| 1 | **本会话没真启动 / 重启过面板** | 那两个 `.bat` 我一个都没跑；面板是**主人双击**起来的（只在 8765 上现读到一个 LISTEN） |
| 2 | `GET /api/tree?depth=3` · `GET /api/events`（SSE） | 本次只拉了 state / capabilities / observer **三条**，树与事件流没拉 |
| 3 | 三个写入口（`POST /api/message` · `/api/capability` · `/api/observer/voice`） | **一次都没调** —— 写动作要过门，不在"读规程"的范围内 |
| 4 | `holo_pet\deploy_check.py` | **没跑**（所以"逐解释器依赖矩阵 / 凭据"的真实读数不在本件里） |
| 5 | DPAPI 保险箱 + 密钥链（agnes 首位、失败降级 deepseek） | 只如实抄口径；`agnes-2.5-flash` 这次**是否真的被选中**没验 |
| 6 | "3.12 起不来" | 是历史约束，**本会话未复验**；只验了 `py -3.10` 在 |
| 7 | 面板自己的策略层是否真的"不放宽任何作用域" | 未逐条核（不拿"文档这么写"当"验过了"） |

---

## 九、出处与固化

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `C:\Users\ADMIN\Desktop\GBT小土豆V8\skills\gbt-potato\SKILL.md` |
| 装机副本（AutoClaw 口径） | `~/.openclaw-autoclaw/skills/gbt-potato/SKILL.md`（**现读与源同哈希**） |
| ⚠️ 本会话能不能自动加载 | **不能** —— 现读本机 DSH 的 `dsh-skill-filesystem` 只扫 `<项目>/.dsh/skills`、`<项目>/.agents/skills`、`preset/skills`、`$DSH_HOME/skills`、`~/.agents/skills`，**不含 `~/.openclaw-autoclaw/skills`**。本件当前**按路径读**；要让它在本会话里"点得到"，得镜像到 `<仓>/.dsh/skills/`（主人 2026-09-22 只授权了设计维度那 16 条，本件不在其中） |
| 读数时间 | 2026-09-22（本节所有数字都是那一刻现读的；**面板一变就得重读**） |
