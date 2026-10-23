# 主脑语音对讲 · **宿主侧那一段**（待接）

> 页面侧已经落盘：`intercom.js` + `intercom.css` + `brain/index.html` 的 `#rail-voice`。
> 本文件是**宿主侧那一段的规格**，写在这里的唯一理由是：主人说过「别又忘记部署了」。
> 规格不落盘 = 下次真的会忘。

## 一、为什么必须有宿主侧

`brain/index.html` 的 CSP 是：

```
default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:;
font-src 'self'; connect-src 'none'
```

`connect-src 'none'` ⇒ **页面不能 fetch/XHR**（这是那页"离线自包含"的硬保证，**不放宽**）。
所以页面**发不出请求**，只能：
- 读**同源脚本**（`script-src 'self'` 放行）—— 这条已经用上了：`brain-data.js` 靠重注入拿新快照；
- 走**宿主桥**（Electron IPC 不受 CSP 管）—— 这就是本文件要补的那一段。

## 二、要补的桥面（契约已冻结，页面侧按这个写好了）

`window.gbtW3.intercom(op, args) -> Promise`：

| op | args | 返回 |
|---|---|---|
| `start` | `{}` | `{ok, listening:true}` 或 `{ok:false, status, reason, legs}` |
| `stop` | `{}` | `{ok:true, listening:false}` |
| `state` | `{}` | `{ok, listening, rounds, last:{text,ts}, last_reason, legs:{capture,asr,tts}, grant_hint}` |
| `say` | `{text}` | 走门 TTS 的结果（被拒就原样带 `missing` / `how_to_grant`） |

## 三、三条硬纪律（违反任何一条，这段就不该上）

1. **一切走唯一门**：监听与出声都要 `gbt_allinone.api.run_task("voice", {...})`，
   **禁止**直接 `from gbt_allinone import voice_cap` 调函数 —— 那是绕门（本仓 2026-09-19 有过一次实测教训）。
2. **监听会话绑到发起它的 webContents**：
   ```js
   ipcMain.handle('gbt:w3:intercom', (event, op, args) => { /* … */ });
   // start 时：
   const wc = event.sender;
   wc.once('destroyed', () => stopSession(wc.id));   // ← 「关页面她也跟着关」靠这一句
   ```
   只靠页面 `pagehide` 发一句 `stop` **不够** —— 页面被强杀时那句发不出去，麦克风就留在那儿开着。
3. **不许做常驻守护**：主人 2026-09-23 定的是**页面生命周期即监听生命周期**
   （「我打开页面就自动监听，关闭她也跟着关闭，但是大脑后台是在运行的」）。
   大脑后台照常跑是 DSH 的事，**不归这一段管**；页面不在时这段什么都不做。

## 四、监听循环的写法（含退避与三种"不静默"）

```
每轮：r = run_task("voice", {op:"listen", seconds:N, culture:"zh-CN"})
  r.ok && r.heard             → 记一条 {text, confidence, ts}，交给主脑
  r.ok && !r.heard            → **安静**：不是坏。只写进 state.last_reason，不刷屏
  r.status == "no_input"      → **没有可用录音设备**：退避重试（3s → 5s → 10s → 15s 封顶），
                                并把真实原因原样带出（本机现读就是这个）
  r.status == "no_recognizer" → 没有该语言的离线识别器：停止重试，如实报，别空转
```

🔴 **安静 ≠ 坏了 ≠ 被门拒**，三件事在 `state` 里必须是三个不同字段，不许合并成一句"对讲不可用"。

## 五、出声（主脑回话）那条腿

`run_task("voice", {op:"tts", text})` **需要 `audio_output`**，而现读 `grants_available = 0`
⇒ 现在必被拒。被拒时**原样**把门给的两行带出来（不要自己编措辞）：

```
missing: ["audio_output"]
how_to_grant: ["终端运行: python -m gbt_allinone auth grant --scope audio_output --ttl 600", …]
```

⚠️ 授权是**一次性消耗**：一次授权 = 一次出声。页面读数里要显示还剩几次
（`run_task("auth_gate_status")` 现读 `grants_available`），别让主人以为授一次能对讲一整晚。

## 六、只有主人能做的三件事（我做不了，也不许自己发）

| # | 事项 | 命令 / 动作 |
|---|---|---|
| 1 | **出声**这条腿的授权 | `python -m gbt_allinone auth grant --scope audio_output --ttl 600` |
| 2 | **麦克风**：本机现在**没有可用录音设备**（SAPI 与 ffmpeg 两条独立探针一致） | 插一个物理麦/耳机麦，或让 iPhone 免提处于连接态 |
| 3 | （可选）让门**看见**麦克风 | 在 `gbt_allinone/security/policy.py` 的 `voice` 分支加：`if op == "listen": add("privacy_read")`。**AI 不许改这个文件** —— 所以现在 `op=listen` 不挂任何作用域，`voice_cap.py` 的返回里带 `gate_blind_spot` 字段如实写着这件事 |

## 七、验收清单（**逐条对账，不是逐条许诺**）

第 66 轮把这张清单**对到证据上**；对账器：`python .scratch\_verify_intercom_acceptance.py`
（它同时清点 ⑥ 的 15 件成品，并**当场重跑**能跑的那些）。

| # | 清单原话 | 状态 | 证据 |
|---|---|---|---|
| 1 | 打开页面 → `state.listening === true` 且 `rounds` 递增 | **部分已验** | **本轮真跑**宿主用的同一条 watch 命令：16s 收到 4 条 JSONL，`rounds_total [1,2,3,4]` **严格递增**。⚠️ `listening` 来自 Electron 主进程的**会话表**，**未经真壳量到** ⇒ 只算一半 |
| 2 | 关掉页面 → 宿主侧会话数回到 0（量宿主，不是量页面） | **进程层已验 / 中间一环仅静态** | `intercom-kill-test.cjs`：起前 0 · 中 ≥1 · `child.kill()` 后 **0**。⚠️ 「`wc.once('destroyed')` 真会调到 `intercomStop`」这一环**只有读代码**（静态接线在位），**没在真壳里跑过** |
| 3 | 拔掉麦克风 → `legs.capture` 变 `no_input` 且带真实原因，页面显示为红 | **已验** | 真命令现读 `wavein_devices=0 · capture_ready=false`；页面那一格由 `_verify_ear_rail.py`（真 Chrome 两态）证明：态一**显示为红**且写「没有可用录音端点（winmm 数 0，与插不插麦无关）」 |
| 4 | 授权一次 → `say` 真出声；再 `say` 一次 → 又被拒 | **已验** | 账本原件：`auth_consumed @23:13:59`（grant-1790180022836 · `detail: voice:tts`）→ **8 秒后** `denied @23:14:07`；第 1 次 `spoken: true` 是真出声 |
| 5 | 账本里每一次 `voice` 调用都有 `run_task` 留痕（无绕门直调） | **已验** | `_verify_voice_ledger.py`：窗内**每一次 voice 调用都带门信封**，`calls_without_envelope = 0`（信封在 `meta.synced`，读错层会假红） |

### 7.1 🔴 对账当场抓出并修掉的一个**真缺陷**（假绿）

**症状**：`watch` 每轮都把状态念成 **`quiet`（安静，没听到，不是坏）**，
而本机 `wavein_devices = 0` —— **根本没有可用录音设备**。规格 §四 明写这种情况必须报 `no_input` 并退避。

**根因**（两处叠加，其中一处是我自己造的）：
1. `five-dim.py` 在结果 **>1100 字**时会把 `result` **收窄**成 `{"_摘要":…, "preview":…}`；
2. `intercom.py watch` 读的是**顶层** `r.get("status")` ⇒ 收窄后取不到 ⇒ 回落成
   `("heard" if heard else "quiet")` ⇒ **把「没有设备」念成「安静」**。

**而撑大结果的那 1100 字，是我第 59 轮给 `listen` 补的 `legs`**（两条腿各带**异常原文**）
⇒ **改一个地方，另一处静默失效**。这正是本仓最忌讳的一类假绿：
**安静 ≠ 坏了 ≠ 被门拒**，三件事不许混成一句。

**两道修**（都上，不只修一处）：
- **读法**：`intercom.py` 加 `_inner(env)` —— 认得出"被收窄"的结果（真值在 `preview` 里）；
- **体积**：`voice_cap.py` 加 `_clip()` —— 两条腿的异常原文截到 140 字，把结果压回收窄阈值以内。

**修后读数**：`收窄了吗 = False` · `status = 'no_input'` · 同样 16 秒内 JSONL 由 **9 条降到 4 条**
（**因为现在真的走退避**：`no_input → 3s→5s→10s`，不再在没设备时以 0.5 秒间隔空转）。

## 八、成品清点（15 件，缺 0）

`python .scratch\_verify_intercom_acceptance.py` 会连同 §七 一起印出来；落在盘的 15 件是：
能力位 `gbt_allinone/voice_cap.py` · 门 `gbt_allinone/api.py` · 宿主桥 `holo_pet_w3/shell/main.cjs` 与 `preload.cjs` ·
页面 `holo_pet_w3/brain/intercom.js` / `intercom.css` / `index.html` · 对讲件 `tools/codex-scripts/intercom.py` ·
离线识别助手 `asr-listen.ps1` · 录音件 `wasapi-record.py` · 本规格 ·
四个验收器 `_verify_inbox_render.py` / `_verify_voice_ledger.py` / `_verify_ear_rail.py` / `intercom-kill-test.cjs`。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
