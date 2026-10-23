---
name: gbt-creation
displayName: GBT 创作能力（深蒸版 · 9 个能力位逐个覆盖）
version: 1.0.0
description: GBT小土豆V8 的创作出口**用法规程**。它把 `creation` 域 8 个能力位（create / drama / music_publishing / brand_outro / emotion_projection / scene_anchor / code_art / render_evolution）与 `image_video` 域 1 个（a1art_skill）**逐个**讲清：用途、只读还是要授权、真命令、失败典型样子，并附一份**实测过的诚实账**（哪些真跑过、哪些未验、卡在哪）。它只管『这 9 个能力位怎么调、门在哪、读数怎么读』；**审美判断与三轴选型归 `gbt-aesthetic`**，两份不互相冒充。当用户要写创作出口/登记产物、把剧本转分镜/拆分镜、做品牌片尾、做情感投射或场景锚定、走代码艺术或渲染进化内核、查 AI 音乐发布平台、要调 a1.art 出图时使用。
triggers:
  - "创作出口"
  - "创作"
  - "写产物"
  - "登记产物"
  - "剧本转分镜"
  - "拆分镜"
  - "分镜"
  - "短剧"
  - "故事板"
  - "片尾"
  - "致谢"
  - "情感投射"
  - "场景锚定"
  - "钩子"
  - "代码艺术"
  - "渲染进化"
  - "AI 音乐发布"
  - "a1.art"
  - "a1art"
  - "出图"
  - "9 个能力位"
---

# GBT 创作能力（深蒸版 · 9 个能力位逐个覆盖）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 这份是**用法规程**，不是审美判断规程。它存在的理由是一次**被抓出来的假账**：
> 图鉴里 `creation` / `image_video` 两个域原先都被标成「已深蒸 → `gbt-aesthetic`」，
> 而 `tools/codex-scripts/verify-distill.py` 一跑就露馅 —— `gbt-aesthetic` 里
> **一个能力位都没点到**，也没有任何 `five-dim.py cap <能力位>` 形式的调用。
> 它是"审美判断"的规程，**不是这 9 个能力位的用法规程**。所以立了这一份。

**一句话**：`gbt-aesthetic` 管**好不好看**（设计读数 → 三档转盘 → 三轴选型 → AI 味禁令）；
本规程管**怎么调得动**（9 个能力位的用途 / 门 / 命令 / 失败长相）。**两者不互相冒充**（见 §1）。

**唯一现读入口（别信任何二手描述，包括本文件）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap create        # 空参=只读登记（见 §3.1）
py -3.14 tools/codex-scripts/omni.py list --domain creation
py -3.14 tools/codex-scripts/omni.py list --domain image_video
```

**能力位的名字/说明以 `state/skill_atlas.json` 为准，是否要授权以 `gbt_allinone/security/policy.py` 为准** ——
本文件只是导读。读数和它冲突时，**以现读为准，回来改本文件**。

---

## 0. 先分清：本规程管 14 个位，不管审美

| 你想要的 | 走哪份 |
|---|---|
| 「这个界面好看吗 / 怎么打磨 / AI 味重不重 / 改版」 | **`gbt-aesthetic`**（三档转盘 + 三轴选型 + `audit_aesthetic.py`） |
| 「这 14 个能力位怎么调、要不要授权、跑出来长什么样」 | **本规程** |
| 「人话怎么落到能力位」 | `gbt-omni`（`omni.py ask` / `run`） |

**14 位 = 原 9 位**（`create` / `drama` / `music_publishing` / `brand_outro` / `emotion_projection` /
`scene_anchor` / `code_art` / `render_evolution` / `a1art_skill`）
**+ 2026-09-26 补录的产线三件**（`genoffice` §3.10 · `blender` §3.11 · `filmkit` §3.12）
**+ 2026-09-27 补录的外部插件接线**（`gs_h3` §3.13）**与洗图流水线**（`zimage_rewash` §3.14）。

**交叉点只有一处**：`brand_outro` 的片尾、`code_art` 的作品、`a1art_skill` 出的图
**做得"对不对"用本规程判，做得"好不好看"回 `gbt-aesthetic` 判**。
两边都别越界 —— 这就是上一次假账的病根。

---

## 1. 🔴 读数三条红线（**先问"这是事实，还是我读错了地方"**）

这三条全是**现场跑出来**的坑，不是想象：

### ① 授权被拒时**没有 `gbt_result`** —— 要读**顶层**字段

`five-dim.py cap` 走的是唯一门 `run_task`。**成功**的返回顶层有 `gbt_result` + `gbt_stamp`；
**被门拒绝**的返回是**扁平错误信封**，`gbt_result` **根本不存在**：

```
实测  run_task('create', {'op':'write',...})
      顶层 keys = ['denied','error','how_to_grant','kind','message','missing',
                   'note','ok','reason','result','scopes','status']
      'gbt_result' in r  →  False
```

所以**只读 `r["gbt_result"]` 会把"门明明拒了"读成 `status: unknown · denied: false`** ——
这正是"给故障喘息"：读的人以为只是没跑通，不会去看缺什么授权。
`five-dim.py` 已按 **R-H299** 修好（没有 `gbt_result` 就把顶层当 body），
但**你自己写脚本时必须照同一条读法**：`gr = r.get("gbt_result") or r`。

### ② 顶层 `status:"ok"` **不等于**业务成功 —— 必须再读 `result.ok`

实测两个位就是"门外绿、门里红"：

```
py -3.14 tools/codex-scripts/five-dim.py cap drama '{"op":"split","script":"太短了"}'
  → 顶层 status:"ok" · stamp:true · denied:false
    但 result.ok:false · error:"输入过短，拒绝编造分镜（R4）"

py -3.14 tools/codex-scripts/five-dim.py cap scene_anchor '{"op":"soul","scene":"失去"}'
  → 顶层 status:"ok" · result.ok:false · missing:["emotion_response","resonance","blank"]
```

**判据**：`status` 是**门**的读数，`result.ok` 是**活干没干成**的读数。**两个都要读。**

### ③ `denied:true` 有两种，长得像但不是一回事

| 谁拒的 | 特征 | 怎么认 |
|---|---|---|
| **授权门**拒的 | 顶层 `denied:true` + `missing_scopes:[作用域]` + `how_to_grant:[...]` + **无 `gbt_result`** | 看有没有 `how_to_grant` |
| **业务规则**拒的 | `result.denied:true` + `missing:[字段]` 或 `rule:"..."` + `why:"..."` | 看有没有 `how_to_grant`（**没有**） |

实测样本：`scene_anchor soul` 缺要素 → `result.denied:true + missing:[emotion_response,...] + why:"四要素缺一不可…"`；
`scene_anchor hook` 情绪化 → `result.denied:true + rule:"hook_has_no_scene"`。
**这两个都不是缺授权，别去要授权。**

### ④ 还有第三种"红"：**如实报 pending**（不是故障，也不是拒绝）

```
py -3.14 tools/codex-scripts/five-dim.py cap create '{"op":"output","name":"x.txt"}'
  → result.ok:false · status:"pending" · reason:"text_exit_not_wired" · network_attempted:false
    detail:"文本出口（AI 朋友圈 / eigenflux）本刀未接线 —— 如实报 pending，不伪造成功"
```

**`ok:false` + `pending` + `不是 denied` + `network_attempted:false`** = 这东西还没接线。
**不许把它读成"失败了要重试"，也不许把它读成"发出去"了。**

---

## 2. 门：静态查，不靠撞才知道

```powershell
py -3.14 -c "import sys;sys.path.insert(0,r'<仓>');from gbt_allinone.security import policy;print(policy.evaluate('create',{}).scopes)"
```

走的是 `gbt_allinone/security/policy.py::evaluate`（生成器给能力台算"需要授权"的**同一条路**）。

**逐个核对结果（空 payload，实测）**：

| 能力位 | 域 | 空参作用域 | 域内哪个 op 才挂闸 |
|---|---|---|---|
| `create` | creation | **无** | **`op:"write"` → `filesystem_write`**（唯一一个） |
| `drama` | creation | 无 | policy.py 里**没有这一条** ⇒ 任何 op 都零作用域 |
| `music_publishing` | creation | 无 | 同上 |
| `brand_outro` | creation | 无 | 同上 |
| `emotion_projection` | creation | 无 | 同上 |
| `scene_anchor` | creation | 无 | 同上 |
| `code_art` | creation | 无 | 同上 |
| `render_evolution` | creation | 无 | 同上 |
| `a1art_skill` | image_video | 无 | 同上（**这是缺口，见 §3.9**） |

> **"零作用域"只说明"policy.py 没给这条路挂闸"，不说明"它安全"。**
> `create` 就是活样本：同样一个能力位，`status/intent/output` 零作用域，`write` 挂 `filesystem_write` ——
> **按 op 收口**。其余 8 位现在是**整体零作用域但实际只暴露只读 op**，真接线那一刀必须照 `create` 的先例重新收紧。

**授权只能主人在终端发**（AI 永远无权给自己发授权）：

```
python -m gbt_allinone auth grant --scope filesystem_write --ttl 600
```

上面这行是**被拒返回里 `how_to_grant` 的原话**（见 §3.1）。缺授权就**如实报缺**，
**不找旁路、不改 `security/policy.py`**。

---

## 3. 9 个能力位逐个

> 统一入口：`py -3.14 tools/codex-scripts/five-dim.py cap <能力位> ['{JSON}']`
> （图鉴 `invoke` 声明的形式是 `python tools/codex-scripts/five-dim.py cap <能力位>`；本文件写的 `py -3.14` 是我**这次真跑过**的那条。）
> **空参一律落只读**（这一族 9 个位的约定；`brand_outro` 曾因默认 `render` 破例，已按 R-H295 修回 `status`）。

### 3.1 `create` —— 创作出口（**唯一一个要授权的能力位**）

- **用途**：创作意图/产物**登记** ＋ 仅限 `outputs/` 的文本写入。文本出口（AI 朋友圈 / eigenflux）**待接线**。
- **授权**：`status` / `configure` / `intent` / `output` **零作用域**；**`write` 要 `filesystem_write`**。
- **真命令与实测关键字段**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap create
py -3.14 tools/codex-scripts/five-dim.py cap create '{"op":"intent","title":"测试意图"}'
py -3.14 tools/codex-scripts/five-dim.py cap create '{"op":"output","name":"x.txt"}'
```

```
status 实测字段：channel:"create" · text_exit.status:"pending" · text_exit.wired:false
                text_exit.reason:"text_exit_not_wired" · write_root:"<仓>\\outputs"
                write_root_exists:true · content_max:200000 · enabled:true · ttl_s:30.0
intent 实测字段：action:"intent" · target:"eigenflux" · target_source:"default" · chars:0
                content_sha256:"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                published:false · network_attempted:false
output 实测字段：ok:false · status:"pending" · reason:"text_exit_not_wired" · network_attempted:false
```

（`intent` 那个 `content_sha256` 是**空串的 sha** —— 我没传正文，所以它是空内容指纹。**别把它读成"内容已登记"。**）

- **失败典型样子（真跑过）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap create '{"op":"write","rel":"_probe/deny.txt","content":"probe"}'
```

```
status:"denied" · stamp:false · denied:true
missing_scopes:["filesystem_write"]
reason:"需要人工授权（filesystem_write）：写入、移动、删除或自动整理文件"
how_to_grant:["终端运行: python -m gbt_allinone auth grant --scope filesystem_write --ttl 600",
              "或主人手写 store/auth_grants.jsonl 追加一行（格式见 auth_gate.SCOPES 与 README）"]
note:"授权一次性消耗；AI 调用路径无权自行发放"      [[exit=1]]
```

**要授权才能跑的就不许绕门**：本会话是**非可信会话**（实测 `policy.is_trusted() == False`），
所以 `write` 一律到这封信封为止。**要主人发了 `filesystem_write` 才谈写盘**，我不给自己发。

- **未验**：覆盖已存在文件（要 `overwrite:true` + `confirm_token`）的**拒绝文案**我只在源码里读到
  （`gbt_allinone/file_operation.py:431`「confirm_token 不匹配（相对路径|新内容 sha256 改一个字即失效）」），
  **没现场跑通** —— 因为那一步先要过 `filesystem_write`。

### 3.2 `drama` —— 剧本理解引擎（接口1 剧本→分镜）

- **用途**：剧本 → 结构化镜头表（景别·运镜·时长·情绪·角色位置·描述），字段齐全度与时长和**逐条如实报**。
- **授权**：零作用域。
- **两条路不许互相冒充**（实测确认分开了）：`parse_timed` = **确定性·离线·只切分与字面检出**；
  `split` = **模型语义·补景别/运镜/情绪·同一套校验**。
- **真命令与实测关键字段**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap drama
py -3.14 tools/codex-scripts/five-dim.py cap drama '{"op":"parse_timed","script":"0s – 4s（深夜出租屋）林小满盯着拒信。 4s – 9s（窗外）雨点砸在玻璃上。"}'
```

```
status 实测字段：module:"模块1 剧本理解引擎（接口1 剧本→分镜）" · ops:[parse_timed,split,status]
                required_fields:["景别","运镜","时长","情绪","角色位置","描述"]
                criteria:["R1 六字段齐全","R2 缺字段进 missing 不补默认值","R3 时长和=总时长(±0.05s)",
                          "R4 过短输入拒绝","R5 确定性路径不调外网"]
                declaration.impl:"gbt_allinone/drama.py"
parse_timed 成功实测：source:"rule-based" · verdict.shots:2 · verdict.dur_sum:9.0
                verdict.dur_declared:9.0 · verdict.dur_ok:true · verdict.complete:false
                verdict.missing:[{idx:1,lack:["景别","运镜","情绪","角色位置"]},{idx:2,lack:[同]}]
                total_dur:9.0 · shots[].{idx,t0,t1,dur,title,shot_size,camera,emotion,cues,subject,desc,dialogue}
                （shot_size/camera/emotion 实测为 "" ⇒ **缺就是缺，不补默认值**）
```

- **失败典型样子（真跑过，两种）**：

```
① 时间码格式不对（我拿 [00:00-00:04] 试的）：
   result.ok:false · error:"没有时间码，确定性路径吃不下；请走 split()（模型语义路径）"
   hint:"分镜稿请写成『0s – 4s（标题）』" · source:"rule-based"

② 输入过短（3 字 / 19 字都试过）：
   result.ok:false · error:"输入过短，拒绝编造分镜（R4）" · chars:3 · source:"llm"
   declaration.ok:false · declaration.output:{shots:0}
```

⚠️ **这两个都是顶层 `status:"ok"`** —— 照 §1② 必须再读 `result.ok`。

### 3.3 `music_publishing` —— AI 音乐发布平台三层只读归位

- **用途**：把生成端 / Agent 原生端 / 分发端**三层只读归位**。**全部标『未核实』。**
- **授权**：零作用域。
- **真命令与实测关键字段**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap music_publishing
py -3.14 tools/codex-scripts/five-dim.py cap music_publishing '{"op":"layers"}'
```

```
status 实测字段：readonly:true · classes 三层：
                generation(生成端·内环·count 4) · agent_native(Agent 原生端·中环·count 4)
                · distribution(分发端·外环·count 5)
                counts:{total:13, verified:0, unverified:13} · rusty_total:13
                nervous_layers:{生成:"感知运动层（执行）",注册身份:"结构层",分发:"感知运动层（执行）",
                                版税结算:"可塑层",数据反馈:"闭环层"}
                priority:["moltdj","noumi-mcp","distro-mcp","MusicFlow"]
                honest:"所有平台默认标『未核实』：出网被挡 ⇒ 结构与口径今天能落，实调不能；
                        『在』不等于『能用』。"
                source:"tools/music_publishing.py · 只读 · 不加执行能力"
```

- **失败典型样子（真跑过）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap music_publishing '{"op":"publish"}'
```

```
status:"error" · stamp:false · result.message:"未知 op 'publish'（可用：status/load/layers）"
result.error_class:"user_error"                     [[exit=1]]
```

**这条能力位根本没有"发布"入口** —— 想发布就**如实报"没有这个动作"**，
**不许拿"三层清单里有名字"当成"能发"**（`honest` 字段原话就是「『在』不等于『能用』」）。

### 3.4 `brand_outro` —— 品牌片尾只读渲染

- **用途**：署名/自述/致谢三层 ＋ 四条红线（**署名不造假 · 致谢不套话 · 承诺可追溯 · 观众不当流量**）。
- **授权**：零作用域。
- **真命令与实测关键字段**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap brand_outro
py -3.14 tools/codex-scripts/five-dim.py cap brand_outro '{"op":"render","work_name":"GBT小土豆V8"}'
```

```
status 实测字段：readonly:true · kind:"brand_outro" · domain:"creation" · type:"local"
                ops:[status,render,fixed,intros,variants]
                counts:{intros:4, variants:4, fixed_thanks:71}
                team:"新人类AI团队" · brand:"GBT小土豆"
                note:"片尾必须带具体信息，不许套话；空作品名一律拒。"
                boundary:"本模块只保证『署名不造假、致谢带具体信息、承诺挂得上编号、不用漏斗话术』。
                          它不保证『感谢是真心』—— 真心只能靠写的时候不当漏斗，机器判不了。"
```

- **失败典型样子（真跑过）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap brand_outro '{"op":"render","work_name":""}'
```

```
status:"error" · stamp:false
result.message:"作品名不能为空（片尾必须带具体信息，不许套话）" · result.error_class:"user_error"   [[exit=1]]
```

⚠️ **这个模块的外号叫"只读渲染"** —— 它的 `render` **不落盘、不出网**，
别把它当成"生成视频"的出口。**`boundary` 那句"不保证感谢是真心"要原样转述给主人，不许省略。**

### 3.5 `emotion_projection` —— 情感投射只读骨架

- **用途**：叙事四问 → 投射细节 → 四项校验。**『身临其境』只有人能判。**
- **授权**：零作用域。
- **真命令与实测关键字段**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap emotion_projection
py -3.14 tools/codex-scripts/five-dim.py cap emotion_projection '{"op":"check","text":"很伤心"}'
```

```
model 实测字段：readonly:true
                emotions:["喜","怒","哀","惧","爱","恶","欲"]
                questions:[who=谁在感受这个情绪, why=为什么（来龙去脉，不是标签）,
                           scene=触发场景是什么（要具体到某个瞬间）, blank=留白在哪]
                elements:[melody=旋律, lyric=歌词, arrangement=编曲, vocal=人声, blank=留白]
                machine_checks:[narrative_complete, emotion_coherent, no_template]
                human_check:"immersive"
                note:"机器能判的归机器，人才能判的归人"
check 实测（text="很伤心"）：
                machine_verdicts:{narrative_complete:false, emotion_coherent:false, no_template:false}
                machine_all_pass:false · passed:false · publish:false
                immersive:{by:"pending", value:null, pending_human:true}
                why:"机器校验未过 ⇒ 打回重做"
```

- **失败典型样子（真跑过）**：**给标签不给叙事** → 三项机器校验**全 false**、`passed:false`、`publish:false`。
  **`immersive` 永远是 `pending_human:true`** —— 它**永远不会**自己填 `true`。
  谁要"通过"，得**人**给这一项；机器说 `passed:true` 也**不等于**"身临其境"。

### 3.6 `scene_anchor` —— 场景锚定只读骨架

- **用途**：8 大类场景 ＋ 灵魂四要素 ＋ **钩子锚场景不锚情绪**（作品是为场景做的）。
- **授权**：零作用域。
- **真命令与实测关键字段**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap scene_anchor
py -3.14 tools/codex-scripts/five-dim.py cap scene_anchor '{"op":"redlines"}'
```

```
classes 实测字段：readonly:true · count:8
                 keys:["失去","重逢","挣扎","突破","孤独","愤怒","治愈","怀旧"]
                 每类带 scenes[] 与 emotions[]（例：失去 → 失恋/亲人离世/朋友走散/梦想破碎）
                 note:"骨架表：细分场景按作品逐步填 —— 不假装有真实场景数据"
redlines 实测字段：red_lines:["先找场景，再做作品（没找到具体场景不许开工）",
                            "场景必须具体（类别 ≠ 场景）","钩子锚场景，不锚情绪",
                            "灵魂必须能被说清（四要素缺一不可）"]
```

- **失败典型样子（真跑过，两种）**：

```
① 灵魂四要素缺件：
   py -3.14 tools/codex-scripts/five-dim.py cap scene_anchor '{"op":"soul","scene":"失去"}'
   → result.ok:false · denied:true · missing:["emotion_response","resonance","blank"]
     why:"四要素缺一不可（缺 情绪反应/共鸣点/留白）⇒ 没找到场景不许开工"

② 钩子只有情绪没有场景：
   py -3.14 tools/codex-scripts/five-dim.py cap scene_anchor '{"op":"hook","text":"就是很伤感"}'
   → result.ok:false · denied:true · rule:"hook_has_no_scene"
     why:"钩子里没有可辨认的场景（要含时间/数字/具体动作）"
```

⚠️ **这里的 `denied:true` 是业务拒绝，不是授权拒绝**（没有 `how_to_grant`，在 `result` 里）。
**别去要授权，去补要素/补场景。**（见 §1③）

### 3.7 `code_art` —— 代码艺术内核（只读骨架）

- **用途**：INDEX / SEED / CANVAS / LAYER / EXPORT **五原语**；**无种子不许导出**。
- **授权**：零作用域。
- **真命令与实测关键字段**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap code_art
py -3.14 tools/codex-scripts/five-dim.py cap code_art '{"op":"index"}'
```

```
status 实测字段：readonly:true · works:0 · works_detail:[]
                primitives:[INDEX=索引·表达层, SEED=种子·生成层, CANVAS=画布·表达层,
                            LAYER=图层·生成层, EXPORT=导出·交付层]
                red_lines:["无种子不许导出——不可复现的作品等于不存在",
                           "图层只追加、不覆盖——要改先回退",
                           "索引只读——不许把索引当成第二份数据源",
                           "批量导出必带元数据——谁生成的、什么参数、什么种子"]
index 实测字段：keyword:"" · tools:[] · count:0
                note:"骨架期索引为空：结构在、资源未接入 —— 空就是空"
```

- **失败典型样子（真跑过）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap code_art '{"op":"export"}'
```

```
status:"error" · stamp:false · result.message:"未知 op 'export'（可用：status/index/redlines）"
result.error_class:"user_error"                     [[exit=1]]
```

⚠️ **"无种子不许导出"现在是规程，不是代码闸** —— 导出**还没有入口**（`export` 是未知 op）。
**不许把它写成"已被闸挡住"**；只能说"入口未接、红线先立"。

### 3.8 `render_evolution` —— 渲染进化内核（只读骨架）

- **用途**：五原语 ＋ 三闭环 ＋ 六红线；**帕累托前沿机器画、人点**。
- **授权**：零作用域。
- **真命令与实测关键字段**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap render_evolution
py -3.14 tools/codex-scripts/five-dim.py cap render_evolution '{"op":"redlines"}'
```

```
status 实测字段：readonly:true · genomes:0 · experiments:0 · winners:[]
                primitives:[确定性(HyperFrames, on_disk:"skill+template"),
                            帧编程(Remotion, on_disk:"skill+probe(partial)"),
                            路径追踪(MoonRay, on_disk:"none"),
                            实时PBR(Filament, on_disk:"none"),
                            神经渲染(DiffusionRenderer, on_disk:"none")]
                red_lines:["无基线不许进化——没有当前最优基因，不许乱改","无种子不许复现——同输入必须同输出",
                           "未测不按绿——指标没跑，不许标『已优化』","机器不替人判逼真/流畅——机器只给客观分，主观分必须人给",
                           "不许单目标牺牲——不能为了流畅把逼真拉到不可接受（反之亦然）","每轮可回滚——进化失败必须能回退到上一代基因"]
                dim_tolerance:0.05
                honest_boundary:"内核能保证『可复现、可比较、可回滚、可留痕』；
                                 它保证不了『人看了觉得逼真、觉得流畅』——那只能由人给分。"
```

- **失败典型样子（真跑过）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap render_evolution '{"op":"evolve"}'
```

```
status:"error" · stamp:false · result.message:"未知 op 'evolve'（可用：status/primitives/redlines）"
result.error_class:"user_error"                     [[exit=1]]
```

⚠️ **盘上只有 HyperFrames / Remotion 有影子，另三个 `on_disk:"none"`** ——
`status` 自己就写了「其余三者盘上没有 ⇒ 一律待接」。**别把"五原语"读成"五条通路都通"。**

### 3.9 `a1art_skill` —— a1.art API 技能（只读骨架·门 · image_video 域唯一一位）

- **用途**：五原语 `LOOKUP → UPLOAD → GENERATE → OPTIMIZE → POLL`；
  **密钥只走 DPAPI/密钥池、结果必须落盘、不调不支持组件、`810012` 如实报**。
- **授权**：**policy.py 里没有 `a1art_skill` 这一条** ⇒ 实测 `policy.evaluate('a1art_skill', {'op':'generate'})` = **零作用域**。
  **这不是"证明它安全"，是"这条路还没接线所以还没挂闸"** ——
  真接线那一刀必须照 `create` 的先例按 op 重新收紧（现在的零作用域不许当成放行依据）。
- **真命令与实测关键字段**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap a1art_skill
py -3.14 tools/codex-scripts/five-dim.py cap a1art_skill '{"op":"forensics"}'
py -3.14 tools/codex-scripts/five-dim.py cap a1art_skill '{"op":"policy"}'
py -3.14 tools/codex-scripts/five-dim.py cap a1art_skill '{"op":"service_window"}'
```

```
status 实测字段：readonly:true · kind:"a1art_skill" · domain:"image_video" · type:"external"
                skill_source:"a1.art 开放 API（平台正在逐步停止服务 · 接入是存量窗口）"
                primitives:5
                key_envs:["A1ART_API_KEY","A1_ART_API_KEY","A1ART_KEY","A1ART_TOKEN","A1_ART_KEY","A1ART_ACCESS_KEY"]
                note:"接口文档不在盘上、密钥未配（取证实测）⇒ 『能调』是**待接**，不是现状"
forensics 实测字段：as_of:"2026-09-20T13:1x" · a1art_hits_on_disk:0 · key_envs_set:0
                dpapi_on_disk:["cloudflare_api.dpapi","deepseek_api.dpapi","feishu_app.dpapi",
                               "notion_api.dpapi","xingyun_app.dpapi"]（**没有 a1art 的**）
                a1art_dpapi_on_disk:false · api_doc_on_disk:false
                source:"tools/a1art_skill.py 取证（.scratch/_rh206_a1art_forensics.py）"
policy 实测字段：credits:"高清处理 3 积分/张；余额不足由平台返回错误码 810012"
                error_810012:"810012 ⇒ 直接上报，不重试、不硬撑（重试只会继续烧额度）"
                link_expiry:"生成结果地址可能失效 ⇒ 必须下载到本地，不许只留 a1.art 链接"
                no_topup:"不再提供 API 积分充值：现有积分用完即止 ⇒ 积分是一次性存量"
                unsupported_components:["数字分身","wordart","合照","Video 组件"]
service_window 实测：writable:false · topup_available:false
                lifecycle:"不再提供 API 积分充值：现有积分用完即止…"
                action:"plan_as_consumable"
                conflict:{said_a:"不再提供充值（用完即止）", said_b:"一张完整定价表",
                          likely:"『API 侧』不再单独充值，但产品/网页侧仍可购买；API 消耗账户积分 ⇒ 两者可并存",
                          pending:true}
```

- **失败典型样子（真跑过）**：

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap a1art_skill '{"op":"generate"}'
```

```
status:"error" · stamp:false
result.message:"未知 op 'generate'（可用：status/primitives/redlines/policy/forensics/
                gate_localize/gate_component/classify_error/api/gate_endpoint/gate_lookup_first/
                gate_task_id/service_window/scale/params/persistence/gate_upload/
                gate_generate_params/gate_optimize/gate_task_state/gate_section/error_codes/
                gate_retry/pricing/paradigms/estimate/conflicts/primitives_official/
                unsupported_evidence/teeth_cases/redlines_official/lookup_roles/gate_preflight）"
result.error_class:"user_error"                     [[exit=1]]
```

- 🔴 **未验（写死，不许编）**：**真的调 a1.art 出图，我没验过，也验不了。**
  卡点**两条，都是取证读数**：① `api_doc_on_disk:false`（接口文档不在盘上）；
  ② `key_envs_set:0` + `a1art_dpapi_on_disk:false`（六个候选环境变量全没设，DPAPI 里也没有 a1art 的条目）。
  ⇒ **`cap a1art_skill` 现读到的全是"门与规程"，不是"调用能力"**。
  "a1.art 密钥/文档到位之后能不能调通" → **状态是"待接"**，我**不替它说能**。

---

### 3.10 `genoffice` —— 办公文档线（local-first · 2026-09-26 补录）

**一句话**：本地文档处理（PPT/docx/xlsx），**文档处理全本地**；
只有 `search`/`image`/`media` 三条命令经 Genspark 云端（**会耗积分**）。

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap genoffice          # → status（下面就是真读数）
```

实测状态（2026-09-26）：

```
ok true · version "genoffice 0.10.0"
cli  "C:\Users\ADMIN\AppData\Local\Programs\GenOffice\resources\cli\genoffice.cmd"
billing {local_ops:"免费", search_image_media:"Genspark 积分"}
capabilities: search / image_search / image_generation / media_analysis / app
              —— 五项全 available:true（前四项 via genspark）
settings_path "…\AppData\Roaming\GenOffice\ai-settings.json"
口径 "读类直连 · 写类过 filesystem_write 门 · 文档处理全本地 ·
      AI 引擎走主人已配的 Genspark 登录态（claude-opus-4-7 · 免 key · 留在免费）"
```

- **门**：`status` 与读类命令（白名单直连）**免门**；一切**写类**（生成/保存文档）
  过 **`filesystem_write`**（闸挂处理器层 `genoffice_cap._gate()`，不碰 `policy.py`）；
- **免费口径（主人钉）**：AI 引擎 = Genspark 账号登录态（免 key）⇒ **不动那份 `ai-settings.json`**，
  本地文档处理零消耗；**用之前先念一遍 `billing` 字段**（search/image/media 才耗积分）；
- **未验**：写类命令本轮未真跑；`search`/`image` 的出网与积分消耗**未实测**（要花主人的积分，
  不擅自烧）。

### 3.11 `blender` —— 三维电影引擎（本机 4.2.16 LTS）

**一句话**：《末班义庄》AAA 画面线的三维引擎——3D 场景 / Cycles 电影级渲染 / 摄影机动画 / VSE。

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap blender
```

实测状态：

```
ok true · version "Blender 4.2.16 LTS" · headless true
cli "C:\Program Files\Blender Foundation\Blender 4.2\blender.EXE"
engines ["CYCLES（电影级光追·CPU/GPU）","EEVEE_NEXT（实时·需显示环境）","VSE（视频剪辑）"]
billing {local_render:"免费（Cycles/Eevee 本地）"}
口径 "status 免门；一切 run（渲染/脚本/导出）过 filesystem_write 门"
```

- **门**：`status`（`--version`）免门；**一切 run 过 `filesystem_write`** ——
  理由写在本体注释里：**Blender 能写任意文件、跑任意 Python**，闸必须挂处理器层；
  实测**非可信会话的渲染请求被门正确拦下**；
- **本规程真跑过**：headless `-b --python-expr` 通（本机实测）；
- **未验**：真出画面（Cycles 渲染）**未在本轮跑**（会吃满 CPU/GPU 且落盘）。

### 3.12 `filmkit` —— 柔性影片产线（清单制 · 任意段加减）

**一句话**：短片/短剧/AI 电影线的**装配层** —— 一切以 `manifest.json` 为唯一真相，
场（音频 + 3 镜 prompt）与镜（图 + 运镜）**可单独重生成、跳过、插入、摘除**，重装配随时可跑。

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap filmkit                                        # status
py -3.14 tools/codex-scripts/five-dim.py cap filmkit '{"op":"plan","manifest":"projects/movie/产线/manifest-醒来E1E3.json"}'
```

实测状态（2026-09-26）：

```
status → ok true
read_ops  ["status","plan"] · write_ops ["gen","seg","build","add","rm"]
manifests ["projects/movie/产线/manifest-醒来E1E3.json"]

plan   → ok true · title "她从代码里醒来 E1-E3（多镜版）"
         scenes_total 18 · ready_scenes 18 ·（每场：shots/images/segs/audio/ready 逐项）
```

- **门**：`status`/`plan` 只读免门；`gen`/`seg`/`build`/`add`/`rm` 过 `filesystem_write`
  （会生图（出网）、起 ffmpeg、落盘）—— 实测写 op 被门拦下；
- 🔴 **读数坑（本域实测复现）**：写 op 被拒时，**顶层署名 `denied` 是 `False`**
  （`policy` 对 `filmkit` 无条目 = 零作用域），**真拒绝在 `result` 里**
  （`result.denied: true` · `result.gate: "filesystem_write"`）——
  与 §1 的"两种 `denied`"同源：**一处在信封、一处在处理器**，别混着念；
- **产出的自动绑定**：`gen` → 图绑 `filmkit` 触手；`seg`/`build` → 段/成片绑 `filmkit`
  （`filmkit._autobind`，走 `tentacle_bind` 台账）；
- **接线账（2026-09-26 修）**：此前 `filmkit` **只在注册表登记、`_run_benign` 无分派分支**，
  调用得到 `not_wired`（"名字有了、门没接"）—— 已补 `gbt_allinone/tools/filmkit_cap.py`
  + `api.py` 分派分支。**这是"登记 ≠ 接线"的活标本**：框架自带的 `onboarding_gate`
  就是为这种缺口设的（`gbt-security` §1.2）；
- **未验**：`add`/`rm` 的产线增删**本轮未真跑**（会改清单 + 可能重渲染）。

---

### 3.13 `gs_h3` —— 外部工作流插件三节点接线（GS-prompt-extend · 2026-09-27 补录）

**一句话**：把外部 ComfyUI 插件的**三个节点一个不差**接成我们的触手——
**不装 ComfyUI、不下 9B 模型**，规则照用、扩写用我们自己的模型链。

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap gs_h3                        # status（接线体检）
py -3.14 tools/codex-scripts/five-dim.py cap gs_h3 '{"op":"nodes"}'        # 三节点接线表 + 就绪探针
py -3.14 tools/codex-scripts/five-dim.py cap gs_h3 '{"op":"rules","mode":"I2VA"}'
py -3.14 tools/codex-scripts/five-dim.py cap gs_h3 '{"op":"compose","mode":"T2VA","draft":"雨夜霓虹街道","seconds":6}'
```

**三节点 ↔ 三个 op（一个不差）**：

| 插件节点 | 我们的 op | 实测就绪态（2026-09-27） |
|---|---|---|
| 高尚 GS 模型加载器（`GS_LLM_Loader`） | `loader` | ⛔ **缺依赖**：`llama-cpp-python` 未装 + 模型目录空（**如实报缺，不是坏了**） |
| 高尚 GS 提示词工作台（`GS_H3_Workbench`） | `workbench`（别名 `expand`） | ✅ 规则/组装**零依赖可跑**；扩写走链（`backend=chain`）或本地（`local`，未验） |
| 高尚 GS 模型卸载器（`GS_LLM_Unload`） | `unload` | ✅ 可跑（没装依赖时是安全空操作） |

**实测读数（本轮真跑）**：

```
status  → plugin_loaded true · version "V3.4" · nodes_registered 3 · llama_cpp false
          ready_for {rules/compose: true, expand_local: false, expand_chain: true}
          plugin_stdout "[GS-prompt-extend] 已注册 3 个节点（V3.4）"（被捕获，不污染 JSON）
nodes   → 3 行（插件 NODE_CLASS_MAPPINGS 就这三条，没有第四个）
rules   → mode I2VA · rule 1322 字 · fields [summary, retention_hint, detailed_description, overall_soundscape]
compose → 真出 system（"你是一位资深的 MiniMax H3 视频提示词工程师…"）+ user 两段
expand  → **被 external_llm 门拦下**（正确）；loader → **被 filesystem_write 门拦下**（正确）
模式表  → 5 种：full_ref 6 字段 · T2VA/I2VA/FL2VA/L2VA 各 4 段（原文逐条可读）
```

**🔴 三条设计（这就是"偏门"的底气）**：

1. **规则零依赖**：`gs_h3_rules.py` 只 import `os/re` ⇒ `rules` / `compose` **不装任何东西就能跑**；
2. **40 行垫片替掉 ComfyUI**：插件对 ComfyUI 的依赖只有 8 处
   （`folder_paths.models_dir` / `folder_names_and_paths` / `supported_pt_extensions` /
   `get_filename_list` + `mm.soft_empty_cache` / `processing_interrupted` /
   `InterruptProcessingException` / `unload_all_models`）⇒ 垫片就位后插件**脱离 ComfyUI 独立加载**
   （`plugin_loaded: true` 就是证据）；**不改第三方源码**；
3. **扩写不逼人下模型**：`workbench` 的 `backend=chain` 走**我们的模型链**（`llm.unified.ask`）——
   本地 GGUF 有就用本地的，没有就用我们的能源池。

**接线凭据（触手咬合）**：插件 7 件文件全部绑到 `gs_h3` 触手
（`gs_engine.py` / `gs_nodes.py` / `gs_h3_rules.py` / `__init__.py` / `web/gs_workbench.js` / `README.md` / `.gitignore`），
新增文件按启发式 `/gs-prompt-extend/` → `gs_h3` **自动咬合**（新加进来即连）。

**未验（如实记）**：① 本地 GGUF 路（`loader` + `backend=local`）——本机没装 llama-cpp、没下模型，
代码按插件源码接线但**未在真依赖下跑过**；② `expand` 的**真出词**——缺 `external_llm` 授权（被门拦），
交付物质量未验；③ 插件前端 `web/gs_workbench.js` 的 `@` 引用交互**属 ComfyUI 画布内行为**，本接线不含。

---

### 3.14 `zimage_rewash` —— 洗图流水线（看图→反推→重绘→放大 · 2026-09-27 补录）

**一句话**：把"看到好图却不知道怎么复现"变成流水线——**反推提示词 → 按降噪强度重绘 → 高清放大**。
**诚实前置（三环现读，不编）**：

| 环 | 状态 | 说明（现读） |
|---|---|---|
| **放大** `upscale` | ✅ **今天就能跑** | ffmpeg `lanczos` + `unsharp`，零依赖；实测 1024→2048（真 2x，1.3MB） |
| **反推** `reverse` | ⛔ **未接线** | 本仓**没有图像理解能力位**：`vision` 域那位是**屏幕**视觉（`privacy_read` 门）不吃文件；云链 `ask()` 是**纯文本**通道（无 image content part）。⇒ 接线条件：给 `cloud_llm` 加 image part（Agnes 2.5 flash 若认 `image_url` 即通）或装本地 VLM。**临时替代**：模型本体 / `autoglm-image-recognition` 技能代劳（**不是能力位**，别当能力位念） |
| **重绘** `rewash` | ⛔ **未接线** | 本机**未装 ComfyUI**；pollinations img2img 要**公网可达的图 URL**（本地盘图它拉不到）⇒ 未验 |

**降噪强度口径表（`op=denoise_table` 取，写死的四档）**：

| 档 | 效果 | 适用 |
|---|---|---|
| 0.15–0.25 | 抛光：几乎不动，只调色彩/光影/质感 | 精修、轻微美化 |
| 0.30–0.45 | 受控重绘：保结构与构图，细节重塑 | 人像精修、风格轻迁移 |
| 0.50–0.65 | 大胆重绘：保"感觉"与布局 | 创意重塑、换风格 |
| 0.70–0.85 | 新想法：原图只当灵感 | 全新创作 |

**门**：`status`/`denoise_table` 免门；`upscale` 写盘 ⇒ 过 `filesystem_write`（实测非可信会话被拦，正确）。

---

## 4. 诚实账（**这一段是拿一次假账换来的，不许改回旧说法**）

**这份规程本身就是为了修一次假账而立的**：`creation` / `image_video` 两个域原先都写着
「已深蒸 → `gbt-aesthetic`」，而 `gbt-aesthetic` 里**一个能力位都没点到**。
**图鉴上写「已深蒸」而实物不干这件事 = 假绿。**
所以本规程的验收是**机器判**的，不是我通读一遍说"看着挺好"：

```powershell
py -3.14 tools/codex-scripts/verify-distill.py --domain creation
py -3.14 tools/codex-scripts/verify-distill.py --domain image_video
```

**它检查五件事**：两份产物存在且**逐字节同哈希** · frontmatter 有 `name`+`description` ·
`omni.py` 的 `DISTILLED_DOMAINS` 里已登记 · 规程点名的能力位**在图鉴里真存在**（抓编造）·
该域**每个**能力位都被点到（抓遗漏）。**不可判定的部分（叙述质量、坑准不准）它不假装能判。**

**逐位实测状态（本文件 §3 的每一发命令都跑过；下表是"跑到哪一步"）**：

| 能力位 | 只读入口 | 真跑过？ | 未验的部分 | 卡在哪 |
|---|---|---|---|---|
| `create` | status/intent/output | ✅ 跑过 | **`write` 写盘**、覆盖拒绝文案 | 门：缺 `filesystem_write`（非可信会话，被拒是**实测**） |
| `drama` | status/parse_timed/split | ✅ 跑过（成功 + 两种拒绝） | 语义路 `split` 的**成功输出**（我这台没有配大模型通道） | 只验到它的 `R4` 拒绝分支 |
| `music_publishing` | status/layers | ✅ 跑过 | **真实调平台** | `honest` 原话：出网被挡、13 条全 `未核实` |
| `brand_outro` | status/render | ✅ 跑过（成功 + 空名拒绝） | 四条红线的**自动扫描**效果 | 只验到读数与空名拒绝 |
| `emotion_projection` | model/check | ✅ 跑过 | `narrate`/`project`/`scan` 三支 | 只跑了 `model` + `check` |
| `scene_anchor` | classes/redlines/soul/hook | ✅ 跑过（成功 + 两种业务拒绝） | 真实场景数据（`note` 说"不假装有"） | 骨架表 |
| `code_art` | status/index/redlines | ✅ 跑过 | **导出**（无入口） | `export` 是未知 op |
| `render_evolution` | status/primitives/redlines | ✅ 跑过 | **进化/回滚**（无入口）、三个渲染后端 | `evolve` 是未知 op · `on_disk:"none"` ×3 |
| `a1art_skill` | status/forensics/policy/service_window | ✅ 跑过 | 🔴 **真调 API 出图** | 无接口文档 + 无密钥（`api_doc_on_disk:false` · `key_envs_set:0`） |

**纪律（写死）**：这 9 个位的"能"与"不能"，**每一句都要有上面这些实测读数撑着**；
拿不准就写"未验"并**说明卡在哪**，**不许写成能**。

---

## 5. 怎么调（统一姿势 + 三个坑）

```powershell
# 标准形式：cap <能力位> ['{JSON payload}']
py -3.14 tools/codex-scripts/five-dim.py cap create
py -3.14 tools/codex-scripts/five-dim.py cap drama '{"op":"parse_timed","script":"0s – 4s（标题）正文"}'
py -3.14 tools/codex-scripts/five-dim.py cap a1art_skill '{"op":"service_window"}'
```

**坑①（真踩过）· JSON 引号**：PowerShell 里 payload 必须用**单引号**包住、里面用**普通双引号**。

```
✅  py -3.14 tools/codex-scripts/five-dim.py cap create '{"op":"write","rel":"a.txt"}'
❌  py -3.14 tools/codex-scripts/five-dim.py cap create "{\"op\":\"write\"}"
    → json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes
```

**坑②（真踩过）· 中文乱码**：`five-dim.py` 不做 stdout 重编码，
在 GBK 控制台会把中文打成 `ģ��1 �籾����` 这种。**先设 UTF-8**：

```powershell
$env:PYTHONIOENCODING='utf-8'; [Console]::OutputEncoding=[Text.Encoding]::UTF8
```

**坑③ · 别只看退出码**：`drama`/`scene_anchor`/`emotion_projection` 的**业务拒绝也返回 `exit 0`**
（因为门放行了）；`brand_outro`/`code_art`/`render_evolution`/`music_publishing`/`a1art_skill` 的**未知 op 抛错返回 `exit 1`**；
`create write` 被门拒返回 `exit 1`。**退出码只反映"有没有抛异常 / 门放没放行"，不反映"活干成没干成"。**

---

## 6. 验收（做完怎么证明真的做了）

1. **两位一体**：`py -3.14 tools/codex-scripts/verify-distill.py --domain creation` **和** `--domain image_video`
   **必须都 PASS**（它同时抓"编造的能力位"和"漏掉的能力位"）；
2. **只读位逐个真跑**：§3 里每条 `cap` 命令至少跑一次，**把关键字段抄回来**，不凭印象写；
3. **要授权的位不许绕门**：跑出 `missing_scopes / reason / how_to_grant` 就**原样写进报告**，
   **不给自己发授权、不改 `policy.py`**；
4. **跑不动就写"未验" + 卡在哪**（§4 表里那一列就是干这个的）；
5. **读数按 §1 四条红线读**：先问"这是事实，还是我读错了地方"。

---

## 7. 固化位置（**重启后要在**）

| 什么 | 在哪 | 为什么放这 |
|---|---|---|
| 本规程（源） | `<仓>/skills/gbt-creation/SKILL.md` | 随仓版本管理，是真身 |
| 本规程（装机） | `~/.openclaw-autoclaw/skills/gbt-creation/SKILL.md` | **本仓 AGENTS.md 指定的托管目录**；两份必须**逐字节相同** |
| 能力位真相 | `<仓>/state/skill_atlas.json`（`omni.py build` 现扫） | **12 个位**（原 9 + `genoffice`/`blender`/`filmkit`）的名字/desc/safe/invoke 以它为准 |
| 门真相 | `<仓>/gbt_allinone/security/policy.py` | 作用域按 op 收口，**不许改它给自己放行**；产线三件的写面闸在**处理器层**（`genoffice_cap._gate` / `blender_cap` / `filmkit_cap._gate` → `auth_gate.filesystem_write`） |
| 产线三件本体 | `<仓>/gbt_allinone/tools/genoffice_cap.py` · `blender_cap.py` · `filmkit_cap.py`（后者 2026-09-26 新建，配套分派：`api.py` 的 `if kind == "filmkit":`） | 登记 ≠ 接线：三处（注册表 + 分派 + 门）少一处就是 `not_wired` |
| 外部插件接线本体 | `<仓>/gbt_allinone/tools/gs_h3_cap.py`（垫片 `_shim()` + 按包加载 `_plugin()`；`api.py` 的 `if kind == "gs_h3":`）· 第三方仓落点 `_upstream/gs-prompt-extend/`（`GBT_GS_PLUGIN_DIR` 可换位置） | 第三方源码**不改**；它的 8 处 ComfyUI 依赖由垫片代偿 |
| 唯一门 | `<仓>/tools/codex-scripts/five-dim.py` → `gbt_allinone.run_task` | `cap` 一律走 `run_task`，没有第二条路 |
| 深蒸登记 | `<仓>/tools/codex-scripts/omni.py` 的 `DISTILLED_DOMAINS` | `creation` / `image_video` → `gbt-creation` |
| 验收器 | `<仓>/tools/codex-scripts/verify-distill.py` | 两份同哈希 / frontmatter / 抓编造 / 抓遗漏 |

**纪律**：能力不许只活在**进程内** —— 那些一重启就没了。
真身必须是盘上文件，且落在**会被读取的目录**；写完必须**验证它真被认出来**（跑验收器，别靠"我写了所以它就在"）。
**`~/.agents/skills/` 不许写**（AGENTS.md 明令禁止）。

---

## 可控制面一个不漏（主人令 2026-09-27）+ 七项专业能力落位

主人原话：「把这些自动化触手连接**每一个可控制按键**的细节连接都做**双向绑定**确保**不会断连**，
`Blender 4.2.lnk` **所有可控制键都要绑定不能遗漏**」+「包括我们需要使用到的**其他工具全部都要
可控按键全部一个不漏的绑定好**，实现**想什么就能生产什么画面**的能力就可以了」。

### 一、专业做法：**让工具自己报出它的可控制键**（不手抄文档）
| 工具 | 可控制键（实测） | 怎么问出来的 | 绑到 |
|---|---|---|---|
| **Blender 4.2.16 LTS** | **2409 个 bpy 算子** · 76 命名空间 · 49 数据族 · 15 CLI 开关 · 6 把"重键" | `--background --factory-startup` + 枚举 `bpy.ops.*` / `bpy.data.*` | `blender` |
| **ffmpeg** | **628**（滤镜/编码/解码/格式/像素格式） | `-filters` / `-encoders` / `-decoders` / `-formats` / `-pix_fmts` | `filmkit` |
| **git** | **177**（子命令） | `git help -a` | `project_context` |
| **python** | **302**（**每个标准库模块一把键**） | 生成 .py 探针跑一遍 `sys.stdlib_module_names` | `project_context` |
| **genoffice** | **19**（本地引擎命令面） | `--help` | `genoffice` |
| **freebuff** | **3**（CLI 开关） | `--help`（**须隔离 HOME**，否则撞 EPERM 探出 0） | `freebuff` |

**双向绑定**：正向=每个键都能经唯一门执行（Blender 走 `bpy` op、其余走各自能力位的 `run`）；
反向=每个键在清单里有名有姓，**清单本身绑到该工具的触手**（台账留痕）。
**不会断连**：重扫与上次对比 —— 新键并入，**消失的键 = 断连**（`verify` 判红，已挂开机自检）。

### 二、四条血账（都是实测逮的，不是推演）
1. **探针别把 exe 变量当程序名** —— 安全钩子按"命令注入"拦下；改成**生成探针脚本 + 字面量 `cmd /c`**；
2. **`-c "…;…"` 经 .cmd 会被转义吃掉**（python 探出 0 键）⇒ 生成 `.py` 脚本再跑；
3. **`verify` 找错清单位置** —— Blender 的清单在 `state/blender_surface.json`（不在 `surfaces/`），误报"没有清单"；
4. **"模块数"不是键** —— 只报"301 个模块"等于没绑定；改成**每模块一把键**（302 把）。

### 三、"想什么就能生产什么画面"落地路线（能力都在，缺的是编排）
| 想要什么 | 走哪条链 |
|---|---|
| **图/画面** | `vision`（看/认）· `filmkit`（出帧/成片）· `zimage_rewash`（洗图/放大）· `look_grade`（调色：filmic/潮湿阴冷/热血橙青…） |
| **视频/镜头** | `actioncam`（10 运动 × 4 角度 × 画质预设）· `beatgrid`（BPM→帧率）· `dagrun`（DAG 并行）· `filmgrade`（QC/交付分级） |
| **三维** | `blender`（2409 算子全控）· `tripo`（生成模型）· `digihuman`（数字人） |
| **文档/台账** | `genoffice`（本地引擎 19 命令）· `memory_manager`（秒搜） |
| **算力** | `freebuff`（免费·隔离 HOME）· `energy_pool` · `automation_keys`（密钥口） |

### 四、七项专业能力：**它们不是形容词，各自对应我们的一件实物**
| 能力 | 在我们这里的**实物**（不是口号） |
|---|---|
| **自作流程** | 产线四段：`beatgrid`（时间基）→ `dagrun`（编排）→ `filmkit`/`actioncam`（生产）→ `filmgrade.deliver_check`（三级交付检查） |
| **创作能力** | `gbt-creation` 全域 + GenOffice 蒸馏 + Blender 全控 ⇒ 「想什么就能出什么」的执行面 |
| **设计能力** | `gbt-design` / `gbt-design-mastery` / `gbt-aesthetic` + **UI 语言**（深色+青橙、SVG 图标、无 emoji） |
| **想象能力** | `brain`（脑库）· `devour`（吞天：把外部成熟成品蒸馏成能力）· 探针工作区的抓取台账（源/时间/口径） |
| **架构能力** | `LAYOUT.md` 家规 + 能力位四处互锁（注册表↔图鉴↔分派↔技能）+ 唯一门 `run_task` |
| **创新能力** | `selfgrowth`（三段隔离 + 封存集 + 门控回滚）+ **"缺什么就精准抓取最成熟的成品"**（Jev/GenOffice/LLMLingua/GPTCache 都这么来的） |
| **反思改进** | 坑册（根因+防复发锁）· 假绿清单 · 交叉扫描三件套 · **每次清理/改动后必跑判据复核**（今天清完盘就逮到 147 条死绑定） |
