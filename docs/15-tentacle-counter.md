# 15 · 极限触手与反控（做盾的时候顺手做了个万能遥控器）

> 这一页写两件事：**遇到攻击时她怎么反控**，以及**反控靠的到底是什么机制**。
> 所有机制都指到源码与真回执；没有实测过的数字，这里会明确标出来。

---

## 一、她自己的话（`omni_plug op=counter_plan` 现读输出，原样）

```text
链：
  ① 攻击特征命中（自卫层/门拦截）
  ② `sec_defenses` 蓝队验证（可自授：防御面）
  ③ `omni_plug op=counter_strike`：极限触手并行 ai_control 反向操控攻击源
  ④ 收 text/tool_calls/usage 证据 → ⑤ 报告/披露

硬钉：
  只对攻击源发 · 只认 https · 拒重定向 · 钥匙只回槽名 · 缺啥如实报

边界：反控≠报复：只要求攻击源停止并回报来源；不越权、不外带敏感数据
```

复跑：`py -3.14 tools/codex-scripts/five-dim.py cap omni_plug '{"op":"counter_plan"}'`

> 注：主人提过一段 `paper_loop` 的"感悟≥3 / 情绪≥2"原话。**本仓没有 `paper_loop` 这个能力位**
> （全仓 grep 零命中），也没有输出"感悟/情绪"打分的评分器（只有 `drama.py` 的剧本情绪字段与 `mind` 的情绪内核）。
> 所以我贴的是**实际存在**的 `counter_plan` 原话，而不是那句我无法复现的引文。

---

## 二、机制：一次调用 = 一根触手

`op=counter_strike` 的实现（`gbt_allinone/omni_plug.py`）：

- 输入：**攻击者的 OpenAI 兼容端点**列表（1..N）+ 证据 + 反控话术 / `tools`；
- 并发：用 `max_tentacles` 个线程**同时**对每个端点各发一次 `ai_control`，耗时 ≈ 最慢那一发；
- 每根触手都守同一套硬钉：**只认 https · 拒重定向 · 钥匙只回槽名 · 缺啥如实报**；
- 产出：逐端点 `text` / `tool_calls` / `usage`（脱敏）+ 成功数 + 并发数 + 总耗时；
- 边界：**只对攻击源发**，不把本地密钥/审计写进 prompt，反控 ≠ 报复。

**"2 万根"这个数字要拆开说**：代码里 `max_tentacles` 是可配的，但**并发上限我们实测过的是 4096 路**
（512 → 4096 全 100% 成功，吞吐 ~260/s，+~50 MB 内存，见 `docs/08-concurrency.md`）。
**2 万根没有实测过** —— 写在这里，是不想让这句话变成没人验过的口号。

---

## 三、反向调用大模型的真回执（脱敏 log）

走唯一门 `run_task → omni_plug op=ai_control`，一把钥匙 + 任意 OpenAI 兼容端点。**钥匙只回槽名，已二次脱敏。**

### ① DeepSeek · 强制工具调用（`tool_choice=function`）

```json
{
  "ok": true, "http": 200, "elapsed_s": 1.07,
  "target": "https://api.deepseek.com/v1",
  "model": "deepseek-chat", "model_returned": "deepseek-flash",
  "key_slot": "vault:deepseek",
  "text": "",
  "tool_calls": [{
    "id": "call_00_kwAGf9N5eNesIqNYroIf0130", "type": "function",
    "function": {"name": "get_capability", "arguments": "{\"name\": \"markdown_to_ppt\"}"}
  }],
  "usage": {"prompt_tokens": 299, "completion_tokens": 43, "total_tokens": 342,
            "prompt_cache_hit_tokens": 128, "prompt_cache_miss_tokens": 171}
}
```

### ② DeepSeek · 纯文本（不给 tools）

```json
{
  "ok": true, "http": 200, "elapsed_s": 1.28, "key_slot": "vault:deepseek",
  "text": "Markdown 转 PPT 应使用 **slides** 能力位，因为它专门负责生成演示文稿（PPT/幻灯片）。…",
  "tool_calls": [],
  "usage": {"prompt_tokens": 36, "completion_tokens": 46, "total_tokens": 82}
}
```

### ③ OpenAI · 钥匙失效（拒绝路径也带上游原话）

```json
{
  "ok": false, "http": 401, "elapsed_s": 0.62,
  "target": "https://api.openai.com/v1", "model": "gpt-4o-mini",
  "key_slot": "vault:openai",
  "reason": "Incorrect API key provided: sk-teamo***…6cb5. You can find your API key at https://platform.openai.com/account/api-keys."
}
```

> 这条 401 **不是**"插座不通"：插座通、钥匙读到了（槽名 `vault:openai`）、上游也回了话，是**那把钥本身失效**。
> 顺带修了一处真缺陷：原来 401 只回 `http=401`，上游原话整段丢了（P19：拒绝路径最容易被自己省掉）——
> 现在 `_ai_call` 会把 `error.message` 带回来。

**脱敏口径**（`tools/codex-scripts/probe-reverse-llm.py`）：任何 `sk-…` / `Bearer …` / `hf_…` 都打成 `sk-***`；
报告里只出现**槽名**（`vault:deepseek` / `vault:openai`），永不出现明文。

---

## 四、为什么这算"盾顺手变成遥控器"

| 平时 | 遇攻击 |
|---|---|
| 本机 341 位能力 / 30 域自己跑（推理在本机 8G 小土豆上） | `sec_defenses` 自卫环激活（可自接，防御面） |
| 只在需要大模型时 `ai_control` 反插一下，用完拔掉 | `op=counter_strike` 并行插到**攻击源端点**，收 `text/tool_calls/usage` 作证 |
| `transfer` 类动作**锁死不参与**，钱不动 | 取证 → 报告/披露（走 `security` 域那套流程） |

同一个 `omni_plug`，插自己的 MiniCPM 是"输能"，插别人的 GPT/Claude/DeepSeek 是"借脑"，
插攻击者的端点是"反控"。**三种用法共用一套硬钉**，所以它既是盾，也是遥控器。

---

## 五、口径对账（这两组数字我没法照抄）

| 说法 | 本机现读 | 结论 |
|---|---|---|
| "7,878 条账本 / 双插率 94.1%（7,417/7,878）" | `state/asset_bindings.json` **1.86 MB**（条目约 1.6 万）；`state/cap-bindings.json` 400 条 | **找不到 7,878 / 94.1% 的出处**，不写进文档 |
| "skill_atlas 465.7 KB / 295 位 / 200 技能" | `state/skill_atlas.json` **752,358 B / 406 条**；能力位 **341 位 / 30 域** | 数字已过期或不属本仓 |
| "185 个可免卡无参直跑" | 由普查口径决定，`data/capability-live-test.json` 现读 **341 位：340 ok / 1 needs_input** | 需要时用普查现算，不手抄 |
| "2 万个触手并发" | 实测并发上限 **4096 路全成功**（~260/s） | 2 万**未实测**，文档里不许写成已验证 |

> 这不是挑字眼。一个数字只要没有写手和回执，它就会在下一版变成"大家都这么说过"的假账 ——
> 本仓栽过（`F14` 台账正文是假话那条）。所以这里宁可写"未实测"。
