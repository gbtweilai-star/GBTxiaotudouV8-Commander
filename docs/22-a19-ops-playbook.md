# A19 运维手册（一页纸）

> 用途：**容器一起来，照着念就能跑完验收**。不用回忆、不用试错。
> 2026-10-26 立。配套文档：`docs/17-phone-a19-runtime.md`（口径与踩坑全集）

---

## 0. 三句话认清现状

1. **LM Pocket 是容器**，不是"另一个 App"。image = `gbt-v8-v82-q5_0.gguf`（5.24 GB · Metal），
   port = `127.0.0.1:1234`，auth = `Bearer gbt`（小写），ctx = `4096`。
2. **容器不常驻**。宿主一进后台，服务被 iOS 收走（约 50 秒宽限）。所以任何"常驻"假设都不成立。
3. **容器外的入口只有两条**：`lmpocket://` 能把 App 拉到前台，**按钮必须人点**；
   网页/CLI 都无法启动它的 server（`start / load / server / ?action=start` 四条深链全证伪）。

---

## 1. 容器一起来，按顺序跑这四条

```bash
cd /var/minis/shared/gbtv8
./tools/ensure_bridge.sh                 # ⓿ 桥自愈（不在就起，已在就返回）

python3 tools/a19_ctl.py status          # ① 在不在、装的是什么、ctx 多大
python3 tools/her.py "你是谁，谁开发的，谁守护的"   # ② 身份自述（最要紧的一条）
python3 tools/a19_prefill.py --window 45 # ③ prefill 阶梯 → 窗口预算 N
python3 tools/a19_switch.py              # ④ 判定「本框能不能整个切过去」
```

④ 出 `✓ 可以切` 才加 `--apply`，否则**继续走旁路**（只送问题本身，4096 够）。

---

## 2. 输出 → 结论（判定表）

| 命令输出 | 结论 | 动作 |
|---|---|---|
| `A19_OFF / ConnectionRefused` | 容器没起 | 去 LM Pocket 点 Load & Start Server |
| `容器 UP · models=[]` | 端口开了但没装载模型 | 等装载 / 重新 Load |
| `401` 或 `key_ready=false` | 钥不对 | 钥必须**小写** `gbt` |
| 身份自述里出现 `OpenAI` / `ChatGPT` | 提示词没立住 | 检查页面 `#system` 是否被改回默认 |
| 身份自述里出现 `手在键盘上打字` 之类 | 纯指代短语没带上文 | 已在页面修（`CONT` 前缀），确认用的是新页面 |
| `prefill_tok_s` 很低（<50） | 窗口预算会很小 | 看 `a19_switch` 的判定，别硬切 |
| `直连 A19 失败：Load failed` | 容器没开 **或** 没发 CORS 头 | 先把上游切回「🧠 经桥」再判断 |

---

## 3. 四个常用动作

```bash
python3 tools/her.py "问题"            # 她答一句（原话返回，且落盘）
python3 tools/her.py --tail 6          # 读回最近 6 条（页面写的也在里面）
python3 tools/a19_ctl.py queue add "问题"   # 容器不在，先存着
python3 tools/a19_ctl.py queue drain        # 容器在，一次跑完
```

**主执行器入口**（不是我手写 curl 的那套）：

```python
run_task('omni_plug', {'op':'a19','do':'status'})              # 1.65s 永不卡
run_task('omni_plug', {'op':'a19','do':'ask','prompt':'…'})    # 不在 ⇒ status=offline
run_task('omni_plug', {'op':'a19','do':'queue','prompt':'…'})  # 入队
run_task('omni_plug', {'op':'a19','do':'up','wait':60})        # 唤起+等就绪
```

---

## 4. 验收：两条命令

```bash
python3 tools/test_a19_chain.py     # 25 个连接点（当前 24 过 1 红 = 容器本身）
python3 tools/test_page_probe.py    # 页面回归 10 条（自动起假桥、跑完恢复真桥）
```

两条都全绿（或只剩「容器 :1234 监听」一条红）时，说明**除了容器本身，其它全是通的**。

---

## 5. 五条纪律（写死在代码里，不是口号）

1. **A19 优先，探不到就如实报错**，绝不静默降级到云端/第三方
   （桥：`FALLBACK["selfhost"]=[]`，要旧行为另设 `GBT_ALLOW_CLOUD_FALLBACK=1`）。
2. **择活不许冒充**：`@cloud / @engine` 只准显式指定（`MANUAL_ONLY`），
   修前 A19 一掉就会报 `ok:true · 云端自有权重`。
3. **没发生的对话不落盘**：容器不在时 `her.py` 只回实话，不写账本。
4. **报"谁答的"**：每个回包都带 `upstream` 与 `weights_ours`，不掩盖。
5. **一台设备只有一个容器**（URL scheme 实测：只有 `lmpocket` 在装），别再找第二个。

---

## 6. 文件在哪

| 东西 | 路径 |
|---|---|
| 容器控制面 | `tools/a19_ctl.py` |
| 她的嘴（说话 + 落盘） | `tools/her.py` |
| 窗口预算测量 | `tools/a19_prefill.py` |
| 容器一通自动验收 | `tools/a19_sentinel.py` |
| 能不能切 | `tools/a19_switch.py` |
| 连接点断言 | `tools/test_a19_chain.py` |
| 页面回归 | `tools/test_page_probe.py` + `tools/mock_bridge.py` |
| 桥自愈启动 | `tools/ensure_bridge.sh` |
| 她的页面 | `holo_pet_w3/model-chat/index.html` |
| 模型桥 | `runtime/model_bridge.py` |
| 对话账本 | `state/her_transcript.jsonl` |
| 口径全集 | `docs/17-phone-a19-runtime.md` |

---

## 7. 为什么落盘要"本地优先"（2026-10-26 实测）

桥跑在 Minis 里（iSH）。她在 **Safari** 里聊天时 Minis 是后台 ⇒ **桥根本不在**，
直接 POST 会全部丢掉（实测：账本 0 行，一条都没落）。

所以页面改成：

```
写 localStorage（立即、不依赖任何服务）
   ↓ 每 10 秒 / 每次加载 / 每条新消息
补传 POST /_log/message → 桥回 200 才从本地删
```

配套：每条记录带 `id`，桥上按 id 去重（补传可能"提交成功但回包丢了"，重试会写重复行）。
实测：同 id 连发两次 → 第二次 `{"saved": false, "dup": true}`。

**这条同样解释了另一件事**：页面走「经桥」那条车道在 Safari 里本来就不可用，
能用的只有「⚡ 直连 A19」—— 它只依赖 LM Pocket 活着。
