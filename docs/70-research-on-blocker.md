# 70 · 卡点自查资料：研究环（2026-11-01）

> 主人：「遇到真实卡点不在你的认知范围之内就要懂得全网查阅资料，核心资料，以及论文，
> 学习分析推理然后再次生成思维导图任务指引给触手继续推进，然后固化焊死」。

---

## 一、卡点出现时她做什么（全自动，不问人）

```
dispatch 某轮失败（非票类）
   ↓
① 判定卡点类型   dependency / permission / timeout / missing_asset / unwired / unknown
   ↓
② 只读查资料     白名单：raw.githubusercontent / arxiv / docs.python（不传自己的数据）
   ↓
③ 学习落知识     state/knowledge/<topic>-<id>.md（来源 + 摘录 + 卡点类型）
   ↓
④ 重排任务       往思维导图追加「研究.N」任务（能力位 orchestration，验收=结论已落库并记账）
   ↓
⑤ 继续下一轮    失败项重试；**不停下问主人**
```

## 二、实测

单次研究：

```
op=research topic="quantization q5_0 dequantize"
→ ok=True · sources=2 · knowledge=state/knowledge/quantization-91631.md
→ digest: "1.5-bit … 8-bit integer quantization for faster inference…"
```

卡点触发（造一张必然失败的蓝图）：

```
land（2 轮）→ 第 1 轮 research: {ok: true, sources: 2,
              knowledge: state/knowledge/实现1-91638.md}
           → 第 2 轮仍未通过 ⇒ 如实报「跑了 2 轮仍未落地（如实报，不装完成）」
```

**关键**：它**没有**停下来问"要不要我查一下？"——它自己去查了，落了知识，重排了任务，
然后把"仍然没落地"如实报出来。

## 三、纪律

1. **只读白名单**（与 devour_auto 同一口径）：只发 URL、不发自己的数据、限 300KB；
2. **知识必落盘**：每次研究写 `state/knowledge/*.md` + `state/research-ledger.jsonl`；
3. **研究不是免死金牌**：查完还是失败就如实报失败，**不许**拿"我查过了"当落地；
4. **重排任务要留痕**：追加的「研究.N」任务进思维导图，账本里能追。

## 四、判据（`test_blueprint` 第 [8][9] 组）

- 研究能跑（或明确失败不抛）
- 落了知识文件 / 有来源
- 卡点触发研究（不是停下问主人）
- 研究账本落盘

## 五、边界

- 网络不通时研究返回 `ok=False` 并记 `failed` 来源；**不会**因此停下，会继续重试任务；
- 摘录是"关键词命中行"，不是精确答案——真正的推理仍靠 `trunk_reason`/权重（受上下文限制）；
- 白名单是硬约束：想查新站点要改代码（防止被"全网"带到任意网络）。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

---

## 六、深推理：让本机权重读摘录、判断怎么改任务（同轮跟进）

研究环原本只摘关键词。这一轮加 `deep_reason()`：把**卡点类型 + 摘录 + 候选能力位**喂给
本机权重，要它输出 `{"diagnosis": "...", "tasks":[{title,cap,payload,acceptance}]}`，
然后把任务写进思维导图（`深推理.N`）。

### 实测（诚实版）

| 输入 | 结果 |
|---|---|
| "No module named psutil 导致自检失败" | 29–53s，`source=energy_core`，**diagnosis 有输出**，但 **tasks=[]** |
| 同一卡点在 land 循环里 | 同样 tasks=[]，随后**规则兜底**补一条可执行任务 |

**7.6B 在"按 schema 输出任务"上不稳**：两次实测都给了 `tasks: []`，诊断文本还夹带胡话
（如"成年礼版 GBT-LLM 微软营"）。所以：

1. **不逼它编**（逼出来的是假诊断）；
2. **规则兜底**：按卡点类型落一条真能执行的任务（依赖→`cap_self verify`、未接线→`comfy_native coverage`、
   超时→`pulse_core verify`、权限→`autonomy status`、缺资产→`inventory`、其他→`orchestration panel`）；
3. **来源分开标**：`source=energy_core` / `fallback_rule`，不把兜底说成"模型推理出来的"。

### 实测（兜底链路）

```
land（必然失败蓝图，1 轮）→ landed=False（如实报）
research.deep = {ok: true, source: fallback_rule, diagnosis: <模型那句>, tasks: 1}
思维导图新增：深推理.1
```

## 七、判据（`test_blueprint` 第 [10] 组）

- 兜底按卡点类型给任务
- 兜底任务带可执行能力位
- 兜底标明来源（`fallback_rule`，不冒充模型）
- `deep_reason` 不抛且带 source（模型不通也回退）

---

## 八、诊断质量门：胡话不采信（同轮跟进）

实测发现 7.6B 会输出"成年礼版 GBT-LLM 微软营"这种与资料毫无关系的诊断。
如果直接把它写进任务，就是**拿胡话当推理**。所以加一道门：

`_score_diagnosis(diagnosis, digest, topic)`：

1. 取诊断里的词（ASCII 单词 + 中文二元组）；
2. 与 **摘录 + 卡点** 的词集算重合率；
3. `score < 0.08` 或零重合 ⇒ `supported=False`；
4. 不 supported ⇒ `deep_reason` 返回 `source="energy_core_unsupported"`、`tasks=[]`，
   交给**规则兜底**（来源仍如实标）。

### 实测

| 诊断文本 | 结果 |
|---|---|
| "成年礼版 GBT-LLM 微软营 不含 AI" | `supported=false` · score 0.0 · 无依据 |
| "psutil 模块未安装，需要 install" | `supported=true` · score 0.25 · hits=[install, psutil] |
| ""（空） | `supported=false` · "诊断为空" |

真实卡点链路（必然失败蓝图 → land 1 轮）：

```
deep = {source: fallback_rule, source_was: energy_core_unsupported,
        diagnosis: "规则判类：unknown", quality: {supported: false, score: 0.0}}
思维导图新增：深推理.1
```

**关键**：胡话被**拦住**了（没进任务），兜底任务照常产出，来源三处都标清楚。

## 九、判据（`test_blueprint` 第 [11] 组）

- 胡话判 unsupported
- 有依据判 supported
- 空诊断判 unsupported
- 兜底任务按卡点类型（dependency → `cap_self verify`）
