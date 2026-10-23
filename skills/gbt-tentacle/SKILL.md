---
name: gbt-tentacle
displayName: GBT 手 · 眼 · 网 · 耳（触手实操规程）
version: 1.0.0
description: GBT小土豆V8 的「手眼网耳」实操规程 —— 这套东西让框架能像人一样看屏幕、点界面、读网、出声与听声。规定三条主通道的机制与调用方式、六条铁律（先看再动/动后等稳定/找不到就滚/遇弹窗必关/每步亲眼验证/不确定就对比前后截图）、以及一份**实测过的诚实账**（哪些真能用、哪些用不了，包括麦克风 0 活动端点这种不许说反的事实）。当用户要「帮我点一下/看一下屏幕/操作这个界面/读这个网页/播放声音/听电脑在放什么」，或触手动作找不到元素、被弹窗挡住、怀疑界面没动时使用。
triggers:
  - "点一下"
  - "看一下屏幕"
  - "操作界面"
  - "帮我操作"
  - "读网页"
  - "截图"
  - "听电脑在放"
  - "播放声音"
  - "触手"
  - "桌面"
  - "鼠标键盘"
  - "找不到元素"
---

# GBT 手 · 眼 · 网 · 耳（触手实操规程）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 这是「人类视角操控一切」里**真正动手的那一半**：`gbt-omni` 负责"人话落到哪条能力位"，
> 本规程负责"手怎么动、眼怎么看、动错了怎么发现"。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```powershell
python tools/codex-scripts/five-dim.py cap tentacle_manifest   # 能力总纲（66 项 + 域 + 六铁律，**注入大脑上下文的那份**）
python tools/codex-scripts/five-dim.py cap tentacle_status     # 自诊断：硬件就绪度 + 依赖分层 + 邻域覆盖
```

**总纲会自我纠错** —— 它已经当场改过一次自己的假声明（见 §4）。**以它的实时输出为准，本文件只是导读。**

---

## 1. 三条主通道（机制，不是比喻）

| 通道 | 机制 | 为什么重要 |
|---|---|---|
| 👁 **视觉** | **DXGI 直读显卡帧缓冲** —— 与显示屏**同源** | 大脑看到的 = 人类看到的。不是"另截一张图"，是同一条流（`vision_buffer` 大脑影院） |
| 🖐 **操作** | **cyborg 五维合一穿透 = UIA 直操作，无视遮挡**（`domain_act` / `domain_type` / `domain_index`） | 窗口被挡住也能操作到目标元素，不靠坐标硬点 |
| 🌐 **读网** | `web_read` / `web_fetch` **真出网读原始 HTML**；`web_adaptive` 页面改版后仍能找回元素 | 读的是源码不是渲染后的近似；改版不失效 |

另有音频域（第 10 域）：`audio_speak`（Windows SAPI）· `audio_play_wav` / `audio_beep` / `audio_stop` ·
`audio_devices` · `audio_wav_info` · `audio_vad_energy` · `audio_loopback`（WASAPI 回环）。

---

## 2. 🔴 六条铁律（**这就是实操纪律，照做**）

> 原文：①先看再动 ②动后等稳定 ③找不到就滚 ④遇弹窗必关 ⑤每步亲眼验证 ⑥不确定就对比前后截图

1. **先看再动** —— 动手前必须先取一帧。不知道屏幕现在什么样就点，等于闭着眼点。
2. **动后等稳定** —— 动作发出后**等界面稳定**再取下一帧；立刻截到的是过渡态，据此判断会误判。
3. **找不到就滚** —— 目标不在当前视口，**滚动去找**，不要瞎猜坐标。
4. **遇弹窗必关** —— 弹窗会吃掉后续所有操作。**先关掉它**，再继续原任务（关之前看清它问的是什么）。
5. **每步亲眼验证** —— 每一步都要有"我看到了结果"的证据，**不许凭"应该成功了"往下走**。
6. **不确定就对比前后截图** —— 拿不准有没有生效，就**前后两张图比**；这是唯一可靠的判据。

**这六条与 `gbt-omni` 的"默认拒绝"是同一条精神**：宁可不做，也不假装做了。

---

## 3. 怎么调

```powershell
# 触手本体（66 项能力，给意图会自动命中；给方法名也行）
python tools/codex-scripts/five-dim.py cap tentacle '{"action":"see"}'
python tools/codex-scripts/five-dim.py cap tentacle '{"action":"click","text":"保存"}'
# 桌面动作常见几种：see / read_text / click / type / list_windows

# 桌面指挥官（终端 + 文件系统全能力触手，支持本地 stdio 与 remote 设备模式）
python tools/codex-scripts/five-dim.py cap desktop_commander

# MCP 契约层（"学会契约协议 = 接入整个 MCP 生态"）
python tools/codex-scripts/five-dim.py cap mcp_tools      # 列已连服务器的工具契约（只读）
python tools/codex-scripts/five-dim.py cap mcp_connect    # ⚠ 要 process_execute
python tools/codex-scripts/five-dim.py cap mcp_call       # ⚠ 要 process_execute
```

**这一域的门（静态查出来的）**：`mcp_connect` / `mcp_call` 要 **`process_execute`**；
其余 8 个（`desktop_commander` / `tentacle` / `tentacle_manifest` / `agency_tentacles` /
`tentacle_pipeline` / `long_run_supervisor` / `mcp_tools` / `tentacle_status`）**不要作用域**。
⇒ 所以 `omni run` 能自动跑只读的 `tentacle_status` / `tentacle_manifest`；
**动作类（click/type）虽然不要作用域，但它会改屏幕状态** —— 按 `gbt-omni` 的默认拒绝，
`omni run` 不替你自动点，**必须人明确要它点**。

**长程任务**用 `long_run_supervisor`（租约/心跳/检查点/有界重试/断点续作/主人升级），别自己写循环硬扛。

---

## 4. 🔴 诚实账（**这一段是拿一次假声明换来的，不许改回旧说法**）

**总纲自己记着这件事**：

> ⚠️ **听觉：一半补上了，另一半仍然没有**（2026-09-22 实测更正）
> 本清单此前写着「👂 听觉: WASAPI回环 = 与扬声器同源，能听电脑播放的任何声音」—— **那是假的**。

**现在真有**：说话（`audio_speak`，本机实测 3 个发音人）· 播放 wav/beep/stop ·
设备枚举（`audio_devices`：扬声器 Realtek ×1）· WAV 头解析 · 轻量 VAD 能量 ·
**听电脑在放什么：`audio_loopback`（WASAPI 回环）本机实测已通** ——
48000Hz/2ch/32bit，放 440Hz 时抓到峰值 32767、均方根 17750.8（非静音），落 WAV 复读一致。
依据 Microsoft Learn《Loopback Recording》：`eRender` + `AUDCLNT_STREAMFLAGS_LOOPBACK` + **只能共享模式**。

**现在仍然没有**：❌ **麦克风** —— 准确口径（按 WASAPI 状态掩码实测）：
**活动录音端点 = 0**；在册 5 个（DISABLED 1 / NOTPRESENT 3 / UNPLUGGED 1）。
⚠️ **既不是"没有麦克风硬件"，也不是"有麦克风"** —— **这两种说法都不准**。
要启用得主人去「声音设置 → 录制 → 显示禁用的设备」里开；**那是改系统设置，不擅自做**。

**教训（写死）**：能力清单里**每一句"能"都要有实测读数撑着**；
拿不准就写"未实测"，**不许写成能**。这份总纲已经把假声明改掉了 —— **别再传旧版本**。

**另一条当场抓到的读数陷阱（2026-09-22 复核音频账时实测）**：
`cap tentacle '{"method":"audio_devices"}'` 回来的**同一个信封**里，顶层说
`status ok` · `ok true` · `activated:["audio_devices"]`，而内层 `cognition.focus` 却写着
`denied: true` · `rule "unknown_capability"` · `why "激活了不存在的能力：audio_devices"`。
**两句话互相打脸** —— 内层那格是认知层自己的账，**不是调用结果**。
⇒ **以顶层 `status`/`ok` 与 `result` 里的真实数据为准**；看见 `focus` 那格别当成"失败"。
（本次同一发实测数据：`inputs []` · `count_in 0` · `outputs [扬声器 (Realtek(R) Audio)]` · `count_out 1`
—— 与上面"麦克风 0 活动端点 / 扬声器 1 个"的账**对得上**。）

**再一条差点记反的账：分清"被门拒"和"把授权烧掉了"**（2026-09-22 审计原文为证）：

- **被门拒 = 没执行 = 不消耗**。审计里只多一条 `auth_denied`，账上那张授权**还在**。
- **放行后真执行才消耗**。审计里出现 `auth_consumed` 才是真花掉；`desktop_control` 是**一次性**的，
  花掉之后**紧接着的下一个动作就会被拒** —— 实测同一轮里：
  `tentacle:focus_window` 放行 ⇒ 当场 `auth_consumed`；0.02 秒后 `tentacle:type_to_window` 直接 `auth_denied`。
  同一批里另一些调用（`audio_devices` / `audio_voices`）全程只有 `auth_denied`，**一张都没花**。
- ⇒ **别把"我被拒了"写成"我把授权用掉了"**，也别把"这轮有拒绝"当成"这轮烧了授权"。
  要看花没花，**只认 `auth_consumed` 那一条审计**（`gbt_allinone/store/audit.jsonl`）。
- ⇒ 派并发任务前先问一句：**它要碰的门是不是一次性的**？一次性授权只配给它本意那一件事，**并且当轮就用掉**。

---

## 5. 验收（做完怎么证明真的做了）

1. **`cap tentacle_status`** —— 硬件层就绪度 + 依赖分层 + 邻域覆盖（自诊断，只读）；
2. **动作类一律前后对比截图**（铁律⑥）—— 不是"我点了"，是"点上之后屏幕变了"；
3. **视觉类必须确认真取到帧**（空白帧 ≠ 没问题）；
4. **找不到元素**：先滚动（铁律③）→ 再 `read_text`/`list_windows` 确认目标真名 → 还不行就**如实报找不到**，
   不要拿坐标硬点一个"大概位置"；
5. **遇弹窗先关**（铁律④），并在报告里说明"中途关了哪个弹窗"。

---

## 6. 固化与出处

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-tentacle/SKILL.md` |
| 本规程（装机） | `~/.agents/skills/gbt-tentacle/` · `~/.openclaw-autoclaw/skills/gbt-tentacle/` |
| 能力总纲（**唯一真相**） | `cap tentacle_manifest`（源码在 `gbt_allinone/tentacle/`）· 回环实现在 `gbt_allinone/tentacle/wasapi_loop.py` |
| 感知/操作解码 | `gbt_allinone/tentacle/omni_*.py`（`omni_vision` / `omni_mouse` / `omni_keyboard` / `omni_window` / `omni_reader` / `omni_process` / `omni_domain` / `omni_audio` / `omni_tentacle`） |
| 人话落点 | `python tools/codex-scripts/omni.py ask "看一下屏幕现在什么样"` → 落到 `tentacle`（`omnipulg` 通道） |

**依赖是真硬件与真桌面**：无显示器 / 无桌面会话时视觉通道起不来，**如实报起不来**，不要假装看到。

---

## 🔴 默认使用：穿透遮挡（Owner 2026-09-22 定 · **不许再说"看不到/够不着"**）

**口径（实时总纲原文，非二手描述）**：
> 🖐 操作: cyborg五维合一穿透 = **UIA 直操作无视遮挡**（`domain_act` / `domain_type` / `domain_index`）

**默认三步（以后任何"界面被挡住 / 窗口不在前台 / 元素够不着"的任务都走这条）**：
1. **先看**（只读 · **不需授权**）：`cap tentacle '{"action":"see"}'` / `{"action":"list_windows"}` —— 拿真帧、拿真窗口表；
2. **动**（走穿透能力位，**不要用坐标硬点**）：
   `domain_index`（定位元素）→ `domain_act` / `domain_type`（操作元素）· 或 `click_window_occluded` / `type_to_window`；
3. **验**（铁律⑤⑥）：操作后**读回证据**（`domain_read` / `read_text_fast`）或**前后截图对比**；不许"应该成功了"。

**被授权门挡住时的正确说法（唯一正确姿势）**：
- 输入/鼠标/键盘/窗口控制类要 **`desktop_control`** 作用域；**AI 无权自授**，门只有一处、不许绕。
- **不要**说"我做不到 / 看不到 / 够不着"；要**直接报缺哪个作用域 + 给出主人要跑的那一行**：
  ```powershell
  python -m gbt_allinone auth grant --scope desktop_control --ttl 600 --purpose "穿透遮挡操作（跨窗口 UIA 直操作）"
  ```
  （要一次覆盖多项可用 `--scope owner_control`；`auth status` 可查当前持有，`grants_available: 0` 表示没有可用授权。）
- 只读类（`see` / `list_windows` / `web_read` / `tentacle_status` / `tentacle_manifest`）**不需要作用域**，
  任何时候都该先跑起来 —— **"没授权"不能成为"没看屏幕"的借口**。

**实测记录（2026-09-22 · 本机）**：
| 动作 | 结果 |
|---|---|
| `{"action":"list_windows"}` | ✅ ok · 列出真实窗口（Chrome / GBT小土豆 / 记事本 …） |
| `{"action":"see"}` | ✅ ok · 取到真帧（DXGI 直读） |
| `{"action":"focus_window","target":"Chrome"}` | ✅ ok · 置前（用它把目标窗口盖住，用于穿透演示） |
| `{"action":"read"}` | ❌ denied（要作用域） |
| `{"action":"type_to_window",...}` | ❌ denied · `missing: ["desktop_control"]` —— **这就是"看不到"的真因：是门，不是能力** |

**一句话纪律**：**先看（不需授权）→ 要动手就报"缺 desktop_control + 给命令行"，绝不退回"我看不到"。**

---

## 触手舰队 · 按任务启动 N 根（主人令 2026-09-27）

主人原话：「每次执行任务都要启动触手根数来执行任务，比如任务需要一次性启动 5 根…
一定要做好隔离启动，端口隔离各做各的不妨碍…你负责以总工程师的身份实时监控在工作的自己。」

**说人话的用法**：任务要 5 根，就一句话 ——

```powershell
python tools/tentacle_fleet.py plan   --n 5 --task "把 A 模块测试补齐"   # 先看落点（端口/工作区）
python tools/tentacle_fleet.py launch --n 5 --task "..."                # 真起（默认引擎 auto）
python tools/tentacle_fleet.py status                                   # 总工程师看板（活着没/在听没/最后一行）
python tools/tentacle_fleet.py logs T03 --tail 20                       # 单根动静
python tools/tentacle_fleet.py stop all ; python tools/tentacle_fleet.py reap
```

**四条隔离（缺一条都不叫隔离；下面是本机实测读数）**

| 隔离 | 手段 | 实测（2026-09-27 · 5 根） |
|---|---|---|
| 工作区 | 每根一份 `git worktree`（独立分支 `fleet/T0N`） | 5/5 建起；探针逐根自证 `cwd == 自己的 worktree` ✅ |
| 端口 | 每根一段专属（31000 起 · 步长 10），**启动前真 bind 探测** | 5 段全独占：31000/31010/31020/31030/31040 |
| 身份 | 独立 `HOME`/`USERPROFILE`/`XDG_CONFIG_HOME` + 各自 `.freebuff/project-id` | 5 个匿名 UUID，**去重 = 5**，并写进 `state/fleet.jsonl` |
| 日志 | 每根 `.fleet/<id>/worker.log` + 退出码 `exit.code` + 追加台账 | 看板报「已退出（退出码 0）」，不是含糊的"未知" |

**关于"每根注册专属账号"—— 先读实物再说话（实测）**：
`freebuff` 的 npm 客户端里 **login / signup / oauth / quota / credits 全部零命中**，
本机身份就是 `.freebuff/project-id` 一个随机 UUID ⇒ **"专属身份" = 独立工作区，不需要注册**。
而**批量注册账号是本仓红线**（主人 9·23 令：不批量注册 / 不刷平台积分），且违反对方条款 ——
所以舰队走的是**匿名身份 + 真隔离**，不是"多账号薅额度"。

**引擎现状（如实报，不美化）**：`freebuff` 本机**装不起来** —— 它要写
`~/.config/manicode/`（实测 `EPERM` / `Permission denied`），下不了自己的二进制。
舰队预检直接复现这个原因，并**如实降级**为内置探针（`.cmd` 与日志里都写明原因），
**不许假装 freebuff 在跑**。要真用 freebuff，二选一：
① 主人在自己的 PowerShell 里跑一次 `freebuff`（主人的身份能写那个目录，装完舰队直接用它）；
② 走 freebuff 的 Cloud 终端（$0，不需要本机安装）。

**与既有并行的关系**：「五根同时跑」框架里**早就有** —— `five-dim.py multi --file jobs.json`
（实测：峰值并发 5 · 墙钟 8.9s < 各件之和 12.2s · 5 个隔离位 · 逐件仍走唯一门 `run_task`）。
舰队补的正是它当时**明说没做的那一层**：**进程级隔离（worktree）+ 端口段 + 身份目录 + 看板与台账**。

### 远程薄终端：把触手伸到别的机器（主人令：云端终端 + 万能插）

`tools/fleet_terminal.py` = **终端那一半**：**零框架体积**（不 import 本仓模块、不带凭据文件），
只把一条能力调用**送进本体的唯一门**（`run_task`）再把结果拿回来 ⇒ 本地压力与体积都留在本体一侧。

```powershell
python tools/fleet_terminal.py guard https://your-host/            # 单看一个 URL 过不过闸
python tools/fleet_terminal.py call --gateway https://your-host --cap mirror_status --dry-run
python tools/fleet_terminal.py selftest                            # 闸门用例（不出网）
python tools/fleet_terminal.py selftest --loopback                 # 本机桩真往返（仅自测）
```

**四条红线（写死在代码里，实测读数在后）**：
1. **只许 http/https，且主机必须是公网** —— 拒 `localhost`/`127.0.0.0/8`/`::1`/`10/8`/`172.16/12`/
   `192.168/16`/`169.254/16`/`0.0.0.0`/`*.local`/`.internal`，**域名解析到内网段也拒**（防 DNS 穿透）；
   自测读数：**13 条必拒全拒 · 2 条必放全放 · 失败 0**。
2. **令牌只从环境变量读**（`GBT_TERMINAL_TOKEN`），不落盘、不打印、不进日志；**没有令牌直接拒绝发送**
   —— 自测读数：无令牌 → 拒 ✅；dry-run 里的头是 `Bearer <令牌（不回显）>`。
3. **能力白名单**：默认只给**只读安全集**；`one_key_deploy` 这类高危**默认被拒**（自测已验）；
   要放开必须显式 `--allow`，`--allow-all` 只归主人并会打印警告 + 写台账。
4. **不批量注册任何账号**（主人 9·23 令）：终端只装到**主人自己合法持有的主机**上 ——
   所以本工具**不"抓免费服务器"**，而是做成**任何一台您已有的机器插上就能用**（Cloudflare 容器、
   任何云主机、任何常开机器）。

**本体那一半（网关）需要主人授权才能部署，我没有部署任何东西**。网关必须实现：
`POST /terminal/exec`（`Authorization: Bearer <token>`，体为 `{terminal_id, cap, payload}`），
且**必须**校验令牌 → 校验能力范围 → **走 `run_task`**（直连模块 = 绕过授权门 = 违规）。
