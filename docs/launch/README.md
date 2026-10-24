# 首发冷启动包（照抄即可发）

> 用途：把仓库从「0 曝光」推到「有人点进来」。**GitHub 本身不带流量**，Trending 只看「某时间窗内新增 star 的速度」，
> 所以顺序是：**先给可点入口 → 再发帖 → 前 6 小时把速度顶起来**。
>
> 现状读数（2026-10-21 10:16 现读）：浏览 0 · 克隆 0 · 来路 0 · star 0 · 主语言已从 HTML 掰回 **Python**（39,968 B）·
> 落地页已上线 <https://gbtweilai-star.github.io/GBTxiaotudouV8-Commander/>

---

## 一、发布前 6 项（3 分钟能做完）

1. **社交预览图**：仓库 `Settings → General → Social preview` 上传 `assets/social-preview.png`（1280×640，仓库里已有）。
2. **About 栏**：Description 已改成双语句（现读确认过）；Topics 建议再加三个：
   `capability-routing` 已有，补 `ai-agents` `audit-log` `chinese-llm` `vllm` `tool-calling`（任选 3 个，别超 20 个）。
3. **Pin 仓库**：个人主页 `Customize your pins` 把它放到第一个。
4. **Release 说明**：现读 1 个 release —— 把 body 换成「一句话 + 三张图 + 一条命令」。
5. **Discussions 已开**：置顶一条 `Welcome / 你想让它先接哪个能力位？`（有讨论区会显著提高转化）。
6. **自己先点一次落地页**，确认手机上也能看（`index.html` 是零外部依赖的静态页）。

---

## 二、帖子（按投放顺序，越靠前越重要）

### ① Hacker News · Show HN（英文，工作日美东 8–10 点发，标题决定 80% 成败）

**标题**：`Show HN: 7.6B Chinese model that routes requests to 348 gated capabilities`

**正文**：

```
We trained a 7.6B model (Qwen2-7B base) whose job is not to answer, but to delegate:
given "turn this Markdown into a PPT", it names the exact capability bit, the args it
needs, and whether the action requires a human ticket before it runs.

What's actually verifiable in the repo:
- 341 capability bits across 30 domains, machine-readable catalog (data/capabilities.json)
- every bit live-tested: 340 pass, 0 fail, 1 needs extra input (docs/07)
- 335-item benchmark, greedy decoding, PASS45 = 99.10% / 98.51% on two full runs
- a runtime where a single gate (run_task) is the only way in, so auth + audit can't be bypassed
- a dependency-free Python client + 30s demo that runs WITHOUT the weights:
  `python demo.py "..."` -> cap name, gate status, exact command
- negative controls in the tests: a hallucinated capability name is rejected, not executed

Not in the repo yet: the 7.6B weights themselves (deployment doc describes serving).
Happy to answer anything about the routing benchmark or the gate design.
```

### ② Reddit · r/LocalLLaMA（英文，标题温和一点，正文放图）

**标题**：`A 7.6B Chinese "commander" model: 348 capability bits, one gate, and a live-run proof for every bit`

**正文**（在 HN 版本基础上加两段）：

```
The part I think this sub will care about: every capability claim has a receipt file under
data/*.json — including the ones that failed. Nothing here is a screenshot of a benchmark.

Also included: a reverse-call demo where a key + a network path is enough to drive cloud
compute (text, image, video, and a local CPU baseline), with sha256 of every artifact.
```

### ③ X / Twitter（短，三条串，配 `social-preview.png` 与 `fig-caps.png`）

```
1/ Most models answer "how do I do X". This one answers "X belongs to capability #217,
   it needs these args, and it will write to disk, so ask a human first." 7.6B, Chinese, open.

2/ 348 capability bits · 30 domains · every bit live-tested (340 pass / 0 fail / 1 needs input)
   335-item benchmark: PASS45 99.10% · single gate `run_task` — auth+audit can't be bypassed
   No weights needed to try it: `python demo.py "..."`

3/ Repo: <link>  · Live page: <pages link>
   What I want from you: tell me which capability you'd want wired to your own stack first.
```

### ④ 知乎 / 掘金（中文长文，标题党但别失真）

**标题**：`我们把「派活」这件事从提示词挪进了权重：7.6B 中文总指挥模型开源`

结构：① 一个问题（模型会聊不会派）→ ② 我们怎么训（落到能力位 + 授权判断）→ ③ 怎么验（335 题 + 341 位逐位真跑，放两张图）→
④ 30 秒自己跑（`python demo.py`）→ ⑤ 已知缺口（权重未放、1 位 needs_input、词表 24 条）→ ⑥ 求反馈。

> 关键差异点别写空话：**「341 位逐位真跑，0 失败」**、**「单门执行，绕不过去」**、**「失败也照实写在文档里」** —— 这三句是中英文都稀缺的。

### ⑤ V2EX（`/go/create` 或 `/go/programmer`）

标题：`开源了一个 7.6B 中文「总指挥」模型：341 位能力位、单门执行、逐位真跑证据`

正文用 ④ 的精简版（500 字内），末尾放仓库 + 落地页链接，并明确「求骂，尤其想要『这套路由口径有没有硬伤』的意见」。

### ⑥ 微信群 / 朋友圈（一句话 + 一张图）

> 开源了：7.6B 中文「总指挥」模型 —— 不只会聊，它把活落到 341 位能力上，写盘/花钱/出网先过人闸。
> 341 位逐位真跑过（0 失败），不用下权重也能试：`python demo.py "我要把 Markdown 变成 PPT"`。
> 仓库：<链接> · 在线页：<链接>

---

## 三、前 6 小时 checklist（Trending 只看速度）

- [ ] 发帖顺序：HN → Reddit → X → 中文三站（**别一次性全丢，间隔 15–30 分钟**，否则前一条还没起量）
- [ ] 每条帖子发出后 **15 分钟内必须有人回复**（你自己回第一条："what's the most useful capability to wire first?"）
- [ ] 请 5–10 个**真人朋友**先 star（不是互赞群；Trending 会看账号质量）
- [ ] 当天要有一个新 commit（Trending 也看「今天有人动过」）
- [ ] 24 小时后看 `traffic/views` 与 `referrers`：哪个渠道真带来了人，第二天只在那一个渠道加码

---

## 四、评论预回答（省得临场手忙脚乱）

| 会被问 | 老实回答 |
|---|---|
| 权重在哪？ | 还没放。`docs/05` 写了怎么 serve。**不放权重是当前最大短板**，我在补。 |
| 99.10% 怎么来的？会不会过拟合？ | 335 题是我们自己的能力位口径题，不是通用 benchmark；两轮全量 + `temperature=0`，逐题预算。已写进 `docs/04`。 |
| 341 位是不是凑数？ | 有 `data/capabilities.json` 逐位可查，且 `docs/07` 给了逐位真跑回执；有 1 位仍是 `needs_input`，没算通过。 |
| 单门执行有什么了不起？ | 它让「授权 + 审计」变成架构保证而不是自觉：绕开 `run_task` 就没有留痕，这在多触手系统里是主要事故源。 |
| 中文模型对英文用户有什么用？ | 路由口径与审计模型是语言无关的；目录、门、回执都可以复用到英文栈上。 |
