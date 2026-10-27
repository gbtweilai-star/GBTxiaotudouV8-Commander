# 37 · 终端授权指令（直接抄，2026-10-28 现算）

> 授权**只能由人在终端发**。我试过，命令会如实回
> `"终端不可用——授权只能由人亲手发放"`。
>
> 每条命令都会问 `人工确认请输入 YES`，**敲 YES 才算发出去**。

---

## 〇、已装成本机命令，从哪都能跑

```sh
gbt-auth                              # 不带参数 → 列出 16 个作用域与剩余可用次数
gbt-auth process_execute 600 "跑命令"   # 发一个作用域
gbt-auth deploy_publish 600 "晋升"
```

脚本在 `/usr/local/bin/gbt-auth`，内部自己 `cd` 到仓库，**不用记路径、不用设 PYTHONPATH**。

**下面两种写法也都能用**（万一 gbt-auth 被清了）：

```sh
cd /var/minis/shared/gbtv8 && python3 -m gbt_allinone auth grant --scope <s> --ttl 600 --purpose "…"
PYTHONPATH=/var/minis/shared/gbtv8 python3 -m gbt_allinone auth grant --scope <s> --ttl 600 --purpose "…"
```

> ⚠ **不要在 `/var/minis` 直接跑 `python3 -m gbt_allinone`** —— 会报
> `No module named gbt_allinone`（仓库在 `shared/gbtv8` 下面，不是根）。

---

## 原写法（等价，需要先 cd）

```sh
cd /var/minis/shared/gbtv8
```

---

## 一、单条顶全部（最省事）

```sh
python3 -m gbt_allinone auth grant --scope owner_control --ttl 600 --purpose "主人总控：一次性放行当前动作所需的全部未授权作用域"
```

**`owner_control` 的定位**：「一条可替代该次动作所需的全部未授权作用域（**一次性消耗**）」。
发一次 = 放行一个动作，用完就没了。安全性比一次性发一摞 scope 高。

**适合**：你现在就想把某件事跑通，不想一条条发。

---

## 二、按用途分别发（推荐，最小权限）

### ① 跑命令 / 用 Codex / MCP（解锁 9 个位）

```sh
python3 -m gbt_allinone auth grant --scope process_execute --ttl 600 --purpose "跑本机命令与 Codex 会话"
```

解锁：`codex_chat` `codex_interrupt` `codex_thread_new` `codex_turn_send`
`codex_tools` `mcp_call` `body_open` …

### ② 镜像晋升 / 部署（解锁 4 个位）

```sh
python3 -m gbt_allinone auth grant --scope deploy_publish --ttl 600 --purpose "镜像晋升与回滚"
```

解锁：`mirror_ascend` `mirror_release` `mirror_rewind` `pipeline_submit`

> ⚠ 这条**建议等真要晋升时再发** —— 时效短、用完即弃更安全。

### ③ 让她说话 / 出声（解锁 3 个位）

```sh
python3 -m gbt_allinone auth grant --scope audio_output --ttl 600 --purpose "TTS 合成与播放"
```

解锁：`body_say` `body_volume` `voice`

### ④ 外部大模型（解锁 4 个位）

```sh
python3 -m gbt_allinone auth grant --scope external_llm --ttl 600 --purpose "把任务数据发到外部大模型"
```

解锁：`autopilot` `codex_models` `llm_chat` `think_loop`

### ⑤ 蓝牙 / 外设（解锁 2 个位）

```sh
python3 -m gbt_allinone auth grant --scope device_control --ttl 600 --purpose "蓝牙与外设控制"
```

### ⑥ 屏幕 / 摄像头 / 麦克风（解锁 3 个位）

```sh
python3 -m gbt_allinone auth grant --scope privacy_read --ttl 600 --purpose "读屏幕与摄像头"
```

解锁：`vision` `credential_steal` `data_hijack`

> ⚠ 这三个位名字看着凶，实际是**安全演练位**（渗透/窃取类演练），
> 不是真的去偷东西。但仍建议只在需要时发。

### ⑦ 桌面操控（解锁 3 个位）

```sh
python3 -m gbt_allinone auth grant --scope desktop_control --ttl 600 --purpose "桌面输入与窗口控制"
```

解锁：`body_click` `body_type` `tentacle`

### ⑧ 数据外发（解锁 1 个位）

```sh
python3 -m gbt_allinone auth grant --scope data_export --ttl 600 --purpose "数据外发与落地框架外"
```

解锁：`devour_pulse`

---

## 三、发之前/之后怎么查

```sh
# 看每个作用域还有几次可用（grants_available）
python3 -m gbt_allinone auth

# 看谁在等授权
python3 tools/brain_attention.py | head -40
```

---

## 四、别忘了 A19（不是授权能解决的）

授权是授权，A19 是**另一个 App 的开关**，得你自己点：

1. 打开 **LM Pocket**
2. 开启服务
3. API 密钥栏填 **`gbt`**（小写；大写会 401）

做完 `state/a19_ready.json` 会自己变成 `ok: true` —— 哨兵每 5 秒探一次，不用重启任何东西。

---

## 五、发完立刻能看到的验证

```sh
cd /var/minis/shared/gbtv8
sh tools/up.sh status                 # 八路
python3 -m gbt_allinone auth          # 各 scope 的 grants_available 变了没
python3 tools/brain_attention.py      # 队列里"等授权"那批会消失
```

**验收口径**：`brain_attention` 里 `[主人] 上报` 和 `等授权` 的条目减少 ⇒ 授权生效。
条目没减少 ⇒ 没生效，别以为是别的原因。
