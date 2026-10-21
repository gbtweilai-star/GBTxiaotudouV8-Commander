# 05 · 部署：从权重到一条能打的线上接口

> 这条链在真实环境跑通过，下面的读数都是实测值，不是估计。

## 一、形态总览

```
权重（bf16 合并，15.25 GB）
   │  挂到带网络的卷（如 RunPod Network Volume）
   ▼
vLLM 0.30（OpenAI 兼容服务，served id = 权重目录）
   │  无服务器化：闲时缩 0，request 到达即冷启动
   ▼
边缘代理（Cloudflare Worker）：令牌门 + 限流 + 兜底
   │
   ▼
客户端（任何 OpenAI SDK）
```

## 二、起 vLLM（最小可用）

```bash
python -m vllm.entrypoints.openai.api_server \
  --model /runpod-volume/gbt-v8-v83 \
  --served-model-name /runpod-volume/gbt-v8-v83 \
  --max-model-len 32768 \
  --dtype bfloat16 \
  --gpu-memory-utilization 0.92 \
  --trust-remote-code false
```

要点（都是踩过的坑）：

1. **`--served-model-name` 必须等于客户端要传的 `model`**。vLLM 只认 served id，
   传一个"友好别名"会直接 **HTTP 502**（我们就是这么踩的）。
2. **`max_model_len` 别超权重本身**：32k 是这个权重的实测上限。
3. **不要开 `--trust-remote-code`**：权重来自我们自己的合并产物，不需要执行远端代码。

## 三、Serverless（RunPod）关键参数

| 参数 | 建议值 | 为什么 |
|---|---|---|
| `workersMin` | `0` | 闲时不烧钱 |
| `workersMax` | `1` | 我们的并发是 1 路；要并发就加副本，而不是把单副本拉满 |
| `idleTimeout` | **`300`** | 这条最容易被忽略：设成 5 秒，worker 干完活立刻被回收，下个请求重载 15 GB ⇒ 用户看到的是"卡死" |
| `flashboot` | `true` | 快照启动，减少冷启动 |
| 模板环境变量 | `MODEL_NAME=<权重目录>` | 让 worker 启动即指向现役权重 |

**冷/热读数（实测）**

| 状态 | 首字延迟 |
|---|---|
| 端点在岗（热） | **≈ 1.1 s** |
| 端点缩 0（冷启动，需重载 15.25 GB） | **≈ 107 s**（文本口径约 300 s） |

> 结论：**"慢"通常是端点冷，不是模型慢。** 要"秒级"，先挂热（下一节）。

## 四、挂热（按需常驻，别常开）

```bash
# 开工：每 150 秒打一次最小推理（max_tokens=1），端点在 idleTimeout 内不会缩 0
curl -sS "https://api.runpod.ai/v2/$EP/openai/v1/chat/completions" \
  -H "Authorization: Bearer $RUNPOD_KEY" -H "Content-Type: application/json" \
  -d '{"model":"/runpod-volume/gbt-v8-v83","messages":[{"role":"user","content":"ok"}],
       "max_tokens":1,"temperature":0}'

# 收工：停掉心跳，让它缩 0（省钱）
```

成本口径：挂热期间按 worker 运行秒计费（约 **$0.89/小时** 量级，随卡型浮动）。**用完必须停。**

## 五、边缘代理 + 令牌门（强烈建议）

直接把 RunPod 地址交给客户端有三个问题：暴露端点 id、没法限流、客户端拿的是你的 GPU 密钥。
推荐加一层 Worker：

```
客户端 --(自己的令牌)--> Worker --(你的 GPU 密钥)--> RunPod
```

Worker 只需要做四件事：

1. **令牌校验**：`Authorization: Bearer <token>` 不在白名单 → 401（**说清是哪一步拦的**）；
2. **改写 model**：把客户端传的 `gbt-potato-v8` 改写成真实 served id（客户端不必知道卷路径）；
3. **流式透传**：`stream: true` 时原样透传 SSE，不要自己缓冲（否则"流式"是假的）；
4. **失败兜底要留标注**：如果上游不可用而回落到别的模型，**回包里必须标出来**，不许冒充。

> 血账：曾经出现过"`weights_ours_configured: true` 但实际答话的是托管模型"——
> 读数全绿、用户体验全错。所以**兜底必须自曝**。

## 六、上线自检（五段，缺一段都不算通）

```bash
# ① 端点自报（不是看配置，是问 worker 自己）
curl -sS "$EP/openai/v1/models" -H "Authorization: Bearer $RUNPOD_KEY"
#   期望：data[0].id == 权重目录

# ② 真推理（身份取回包 model 字段）
curl -sS "$EP/openai/v1/chat/completions" -H "Authorization: Bearer $RUNPOD_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"/runpod-volume/gbt-v8-v83","messages":[{"role":"user","content":"ping"}],
       "max_tokens":8,"temperature":0}'
#   期望：HTTP 200 且回包 model == 权重目录

# ③ 经代理（客户端令牌）
curl -sS "$PROXY/v1/chat/completions" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model":"gbt-potato-v8","messages":[{"role":"user","content":"只回两个字：收到"}],
       "max_tokens":16,"temperature":0}'

# ④ 流式（必须真收到增量，不是只看到 text/event-stream）
curl -N -sS "$PROXY/v1/chat/completions" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"model":"gbt-potato-v8","messages":[{"role":"user","content":"数到五"}],
       "stream":true,"max_tokens":40}'
#   期望：能看到多个 data: {"choices":[{"delta":{"content":"…"}}]}

# ⑤ 本地框架（如果你用我们的框架）
py -3.14 tools/codex-scripts/chain-check.py
#   期望：五段全 ✓（本地框架 / 云插件 / 直连 / 流式）
```

## 七、常见故障对照表

| 现象 | 真因 | 修法 |
|---|---|---|
| HTTP **502** 但 `/models` 正常 | 客户端传的 `model` ≠ served id | 传 served id，或让代理改写 |
| 首次请求卡 100+ 秒 | 端点缩 0 冷启动 | 挂热，或把 `idleTimeout` 调大 |
| 401 `invalid api key` | 钥匙不对（换过端点/卷没换钥） | 换正确钥；**别只查"地址对不对"** |
| 流式只回一大段 | 代理做了缓冲 | 透传 SSE，别聚合 |
| 读数全绿但答案不像本模型 | 兜底静默换道 | 兜底必须在回包里标注 |
