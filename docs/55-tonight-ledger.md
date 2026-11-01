# 55 · 今晚补齐清单与闭环固化（2026-11-01）

> 主人规矩（逐字）：「**每次跑通闭环之后必须顺带把固化做好，不能丢一边就不管了**」。
> 这份就是今晚的固化账：做了哪些、读数多少、怎么复跑。

---

## 一、能力位从 354 → 362（+8）

| 新能力位 | 域 | 干什么 | 读数 |
|---|---|---|---|
| `commander` | tentacle | 本机权重总指挥：路由/判决/起停引擎 | 冷启 2.6s；route 24–50s |
| `pulse_core` | tentacle | 量化·脉冲·直达·按需四合一 + 器官图 | `verify` 四条全过 |
| `cap_self` | tentacle | 自知：has/list/brief/ask/verify | 362=362=362，漂移会红 |
| `omni_open` | tentacle | 万能插动态发现（不写死六类） | 35 插头，diff 报警 |
| `trunk_cover` | tentacle | **每个代码文件归哪根触手** | 2503 文件 · orphan **0** · cap_coverage **1.0** |
| `body_sense` | device | 本体感觉 / 痛觉 / 神经邻域 | 14 肢体 · 机构已接 **0**（如实） |
| `trunk_reason` | tentacle | 接 `brain_exec` 五维链的"想" | 规则指令 + LLM 推断分开报 |
| `context_guard` | llm | 上下文守卫**正式成位**（原来只是脚本） | 窗口 2644/12000 · 异常 0 |
| `devour_auto` | devour | 自主吞食（锁缺口才吃，必须有转化物） | 吞 2 · 转化 2 · 白吃 **0** |
| `energy_core` | engine | 能源核心：一块电池、4 个取电口、电表 | ports=4 · 4 并发实测 32.6s |

（其余能力位为既有；`knowledge_lib` / `brain_supervisor` **不登记** —— 它们是已登记位的模块外壳，重复登记会双计数。）

## 二、四个关键机制（都带读数）

### 1. 脉冲直达（提速的来源，不是加并发）

```
命中四级：精确真名 → 意图别名 → 人工词表唯一高权重 → 唯一子串
24 条人写基准：直达命中 15/24，其中正确 13，平均 4ms
对照：权重判决 16/24，平均 66s
```

### 2. 能源核心（一块电池，多个取电口）

```
/props → total_slots=4
4 个触手同时取电：全部 32.6s 内完成，等待 2–4ms（旧全局锁下会排队 100s+）
代价：单路从 5.7s 变 32.6s —— 并发是真，提速是假；吞吐共享
```

### 3. 无限制上下文（不是把 ctx 调大）

```
push 120 条 → 窗口恒定 72 条 / 3996 字符（预算 4000）
溢出 48 条落 sqlite，recall 秒查（seq=7 命中）
energy_core.think(context="名字") 已接：进环 → 有界窗口 → 回复回环
```

### 4. 门政策收窄（主人 2026-11-01 令）

```
41 → 31 个能力位要票
移出：看/听/说/动手/只读抓取（本机自己的感官不是攻击面）
仍要票：process_execute / remote_device / privacy_read（看别人） / deploy_* / external_llm / data_export
```

## 三、部署反查（查"设计了没部署"）

新增 `tools/codex-scripts/audit-deployed.py`，三张清单：

| 清单 | 首跑 | 收紧后 | 真值 |
|---|---|---|---|
| A 标了 `gbt-capability` 但没登记 | 89 | 28 | **11 候选 → 2 真缺**（`research_intel`、`hunyuan_video`，已部署） |
| B 文档提了但没登记 | 193 | 29 | 多为普通词（`user_error`/`build`/`find`），待人工判 |
| C 登记了但没实现 | 0 | 0 | **干净** |

## 四、固化产物（谁能复跑）

| 件 | 位置 |
|---|---|
| 记忆条（每次判决自动带） | `cap_self brief` → 844 字符，含 energy_core/trunk_cover/body_sense… |
| 快照 | `data/capabilities.json`（362）· `docs/capabilities/*.md`（30 域） |
| 判决账本 | `state/commander/coverage-rows.jsonl` · `bench-lexicon-full.json` |
| 代码覆盖 | `state/trunk-cover.json` |
| 痛觉账本 | `state/body-pain.jsonl` |
| 吞食账本 | `state/devour-auto.jsonl` · `devour-todo.md` |
| 电表 | `state/energy-ledger.jsonl` |
| 双插 | `state/context-bindings.json` |
| 心跳/上下文 | `state/context-guard.json` |

## 五、复跑命令（一条一条可验）

```powershell
py -3 -X utf8 tools/codex-scripts/export-capabilities.py
foreach ($t in 'test_commander_trunk','test_pulse_core','test_cap_self','test_lexicon_scope',
               'test_code_graph','test_omni_open','test_omni_open_diff','test_alerts_sockets',
               'test_inventory_checkout') { py -3 -X utf8 tests\$t.py }
py -3 -X utf8 -c "import gbt_allinone as g; print(g.run_task('cap_self',{'op':'verify'},probe=True))"
py -3 -X utf8 -c "import gbt_allinone as g; print(g.run_task('trunk_cover',{'op':'verify','force':True},probe=True))"
py -3 -X utf8 -c "import gbt_allinone as g; print(g.run_task('pulse_core',{'op':'verify'},probe=True))"
py -3 -X utf8 tools/codex-scripts/audit-deployed.py
```

## 六、闭环终值（2026-11-01 05:4x）

| 检查 | 读数 |
|---|---|
| 契约测试 | 9/9 全绿 |
| `cap_self verify` | **362 = 362 = 362** |
| `selfscan` | clean |
| `signature_guard scope=all` | clean · 106 页 |
| `trunk_cover verify` | **ok** · orphan 0 · 2503 文件 |
| `pulse_core verify` | ok · failed [] |
| `body_sense` | 痛：酸 2 点（需票）；肢体 14；机构已接 0 |
| `devour_auto` | 吞 2 / 转化 2 / 白吃 0 |
| `context_guard` | 窗口 2644 / 预算 12000 · 异常 0 |
| 合成基准 | 450/481 已跑，353 命中 |
| 人写基准 | 16/24，召回 24/24 |

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

---

## 七、编排账本与面板（主人 2026-11-01：「重启看一遍编排面板就一目了然」）

新增能力位 `orchestration`（第 363 位）+ `gbt_allinone/orchestration.py`。

**六类动作**只追加落 `state/orchestration-ledger.jsonl`：

| 动作 | 记什么 |
|---|---|
| `scan` | 扫描（覆盖/自检/反查/插口/器官/基准） |
| `add` | 新增（能力位/文件/账本/工具） |
| `edit` | 修改（注册表/分派/策略/文档/代码） |
| `deploy` | 部署（登记 + 分派 + 快照） |
| `fix` | 修复（回滚/纠正/补丁） |
| `run` | 有产出的执行（判决/推理/吞食） |

**自动记账**：闸门 `run_task` 对**非 probe** 调用自动记一条 `run`（probe 不记，避免噪音）；
`trunk_cover.scan`、`cap_self.verify` 各自记 `scan`。

**面板 `op=panel` 一屏给全**：
本会话动作计数 · 最近条目 · 各类扫描**最后时间** · 能力位 vs 快照**漂移** · 自上次看图以来新增。

**今晚补记 20 条**（当时的动作真实发生过，只是账本刚建，补记时标注「会话当时账本未建」）：
add×6（body_sense/trunk_cover/trunk_reason/context_guard/devour_auto/energy_core）、
deploy×3（research_intel/hunyuan_video/orchestration）、
edit×3（policy 门收窄、commander 脉冲+记忆、cap_self 记忆条）、
fix×3（词表冲突、重复登记、policy 恢复）、
scan×5（trunk_cover/cap_self/audit-deployed/覆盖率/focus 吞食）。

重启后的第一屏应该长这样（本次实测）：

```
ledger 24 · session 1
by_action {scan:0 add:0 edit:0 deploy:0 fix:0 run:1}   ← 新会话只算本会话
caps {registry:363, snapshot:363, drift:0}
last_scan {trunk_cover:…, cap_self:…, audit-deployed:…, commander-coverage:…, devour_auto.focus:…}
```

---

## 八、速度总账（2026-11-01 收尾，已写进记忆条）

| 路径 | 覆盖 | 耗时 | token |
|---|---|---|---|
| **脉冲直达（主干默认）** | **322 / 358 = 89.9%** | ≈4 ms | **0** |
| 权重判决 | 剩 10.1% | 15–50 s | 本机电池 |

人写 24 条基准（真实短句形态）：**直达 24/24，正确 22/24**（此前 17/24 命中、15 正确）。

**记忆条已写入**（`cap_self brief`，910 字符，每次判决默认注入）：

> 速度：十次请求约九次直达（322/358 = 89.9%，0 token、≈4ms），剩下才叫醒电池；人写短句 22/24 正确。

⇒ **重启后的她，第一眼就知道自己现在有多快**，不需要谁提醒。

## 九、longrun 收尾（4/4）

`lr_status` 之前打不中，原因是「长程任务看板」这个说法**被自动别名占着**（且与人工条目重复）。
把该词从自动条目摘掉、留给人工条目后，longrun 域 **4/4 直达**。

## 十、本轮的判据变化（要留痕）

`pulse_core.direct` ③ 增加**整串命中例外**：查询本身等于词表某条 `say` 时，
只要最高权重**严格大于**次高就直达（不再要求 2 倍）。
理由：整串命中一条 `say` 是最强证据，2 倍率会把正确答案卡掉（24 条人写里有 7 条栽在这）。
实测副作用：全量直达 321→322、正确 288→289，**没有多出错直达**。
