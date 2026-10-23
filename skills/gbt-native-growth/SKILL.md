# gbt-native-growth · 原生能力成长栈

> 主人令（2026-09-27）一句话版：**吞天要和契合自己的原生能力融合、每根触手一本永久记忆 Obsidian 并与本体互通、
> 要有短板钩子和自主进化钩子、做事先看再动脑不许无脑和盲猜、原生能力要有 GBT 专属标签且只有主人允许才能调、
> 新增就触发双向绑定并连通每一页触手。**

这套栈有六个件，**彼此有依赖顺序**（记忆是底、钩子是鞭、闸是刹车、标签是钥匙）：

```
obsidian_vault（永久记忆·227 本触手库 ↔ 本体库双向）
      ↑ 记
devour_fusion（吞天×原生：三件齐才算融合）
      ↑ 查
tools/binding_hook.py（硬性规则钩子：新增六条腿，缺了就红）
      ↑ 逼
growth_hooks（短板钩子 + 自主进化钩子）
      ↑ 拦
action_gate（先看 → 动脑 → 执行）
      ↑ 管
cap_tags（GBT 专属标签 + 主人许可门）
```

## 一、永久记忆（`obsidian_vault` · 触手 `obsidian_vault`）

- **触手库**：每一根触手（= 能力位 kind ∪ `domain:<域>`，实测 **232** 个标签）**各一本独立库**，
  落在本仓 `vaults/<触手>/`：`README.md`（MOC）· `记忆.md`（追加式）· `.obsidian/app.json`（Obsidian 直接开）。
  为什么在仓内：**永久记忆要和源码一样受保护**（仓外的东西没人扫、不进版本），且它是框架**自己的**记忆。
- **本体库**：`brain_vault` 认的那本（`Documents\Codex\ObsidianVault`）—— 不动它的既有笔记。
- **双向绑定**：触手页链回 `[[GBT本体记忆]]`，本体 `[[触手总索引]]` 链到每一本；`verify` 两条都查。
  **不是复制**（复制只会分叉，本仓吃过技能双真身的亏）：各自的内容留在各自的库，互相**指得到**。
- 共享页 `sync_page`：同一篇在触手库与本体库各一份，**两侧同 sha**。
- 写「主人的 Documents」走 `root=documents`，**过 `filesystem_write` 门**；仓内默认不过门（同 `state/`）。

## 二、吞天 × 原生融合（`devour_fusion` · 触手 `devour_fusion`）

**三件齐才算融合**：①原生位三处齐（注册/分派/图鉴）②有效触手标签 ③触手库永久记忆页。
`status=已融合` 而三件不齐 **当场拒**（假账在门口拦下）；`fuse` 只补第三件，前两件缺着不假装。
台账 `state/devour_fusion.jsonl`；`list` 的输出里 `已融合` 是**盘上算出来的**，不看台账里写的。

## 三、短板钩子 + 自主进化钩子（`growth_hooks` · 触手 `growth_hooks`）

- `shortboard`：短板**从读数算**（六面 + 未清故障 + 未实现 + 触手库覆盖 + 许可缺口），**每条带 `src`**。
- `evolve`：拿最短板 → 生成步骤（标 `safe`/`needs_owner`）→ **只自动做不带门的**，其余列给主人。
- 两条纪律写死在代码里：**不自批授权**；**撞 `state/holdout.json` 封存验收集的步骤一律拦下**
  （判据不许既当训练又当验收）。

## 四、先看 → 动脑 → 执行（`action_gate` · 触手 `action_gate`）

| 规矩 | 判据 |
|---|---|
| 先看 | `evidence` 非空且**真在盘上**（`observe` 记 sha + 龄） |
| 看的是新的 | 证据龄 ≤ `fresh_s`（默认 600s）；旧了要么重看，要么显式 `stale_ok=true` 说理由 |
| 动脑 | `hypothesis` ≥8 字（写出"我预期发生什么"）—— **不许盲猜** |
| 有票 | 写/执行类要给 `scope`，或能力位是 `owner` 类 |

过了发 `gate_id` → 动手 → `close(gate_id, result, saw)`：**`saw` 不许空**（做完必须看到结果，exit 0 不算）。

## 五、GBT 专属标签 + 主人许可（`cap_tags` · 触手 `cap_tags`）

- 标签 `GBT-<域>-<能力位>`（例：`GBT-CREATION-LOBEHUB`），**从注册表现算**，新增自动就有。
- 权限类**不是手写名单**：`policy.evaluate(kind, {op})` 逐 op 问作用域 + 图鉴 `safe`/`needs_confirmation`；
  **读不出来一律按 `owner`**（默认严）。`open`=读类随便调，`owner`=**只有主人允许了才能调**。
- 许可：`gbt_allinone/store/owner_permits.jsonl`（一行一条），或主人终端
  `python -m gbt_allinone.tools.cap_tags permit --tag <TAG> --ttl 600`
  —— **要求 TTY + 手打 YES**，非交互会话直接拒 ⇒ **AI 发不出许可**（本模块里也**没有**第二条写许可的路径，
  `verify` 会结构性地查这一点：写的那一行必须在 `isatty` 闸之后）。
- `audit` 输出的是**待批清单**（哪些 owner 类还没许可）。

## 六、硬性规则钩子（`tools/binding_hook.py`）

新增一件东西，**当场**走完六条腿，缺哪条补哪条，补不了记红：

| 腿 | 查什么 | 缺了怎么补 |
|---|---|---|
| ① 登记 | `caps_registry.py` 有 kind | 加注册条目（钩子**不替你造**能力位） |
| ② 分派 | `api.py` 有 `kind == "<kind>"` | 加分支 |
| ③ 图鉴 | `state/skill_atlas.json` 收录 | `omni.py build` |
| ④ 触手 | kind 是有效触手标签 | 注册即成立 |
| ⑤ 绑定 | 绑定账里查得到（资产或清单） | `surface_bind op=probe` / `tentacle_bind autobind` |
| ⑥ 记忆 | 触手库里有一页 | `obsidian_vault op=provision/remember` |

```
python tools/binding_hook.py after-add --kind <kind> [--tool <工具区名>]
python tools/binding_hook.py sweep      # 自愈：给所有能力位补齐触手页
python tools/binding_hook.py verify     # 复核（漏走钩子的新增在这里露出来）
```

**血账**：`surface_bind` 的委托分支（comfyui/blender/lobehub）曾**提前 return** ⇒ 清单写了**却从没绑上触手**。
"接上了没绑上"就是这个钩子要防的事。

## 这轮抓出来的四个真问题（都属"判据/闸自己先坏"）

1. **判据往真库里写**：`sync_page` 的自检一度往本体库写了张 `自检页.md` —— 判据必须全程在临时目录里做。
2. **自审太钝**：`cap_tags.verify` 只查"代码里有没有写许可"，把主人终端那条合法路径也判红 ⇒ 改成**结构性**检查
   （唯一一处 + 必须在 `isatty` 之后）。
3. **反盲区判据立功**：新加 `vaults/` 后顶层树 60→63，`test_coverage_readings_fresh` 当场红 ⇒ 重扫矩阵，
   新面被登记（不是被忽略）。
4. **假账拦截要真试**：`intake(status='已融合')` 用**真有那三件**的能力位去试，当然会过 —— 要拿"缺件"的去试。


## 七、常设调用者（谁在跑它们 · 防"摆设"）

能力位**光登记不算接上**：框架自带的 `test_caps_called_audit` 会把"内调型却没人调"的能力位报成**孤儿**。
这套栈的常设调用者（都是真调用，不是为过判据摆的）：

| 能力位 | 谁在调 | 调来干什么 |
|---|---|---|
| `obsidian_vault` | `binding_hook.py after-add` / `devour_fusion.fuse` / `gods_eye.daily` | 建页 · 记一条 · 日报读记忆覆盖 |
| `cap_tags` | `gods_eye.daily` · `action_gate._scope_needed` · `sec_sweeper.start` | 待批清单进日报 · 判"要不要主人许可" · 标签许可体检 |
| `action_gate` | `growth_hooks.evolve`（**每一步自动动作先过闸**） | 先看→动脑→执行 |
| `growth_hooks` | `sec_sweeper.start` · `gods_eye.daily` | 安全棒每轮算短板 · 日报带最短板 |
| `devour_fusion` | `sec_sweeper.start` · `gods_eye.daily` | 融合体检 · 未融合条数进日报 |
| `gods_eye` / `task_manager` / `sec_sweeper` | 互相挂进安全棒巡检（门面 / 进程面 / 健康账） | 一处启动、三面都读得到 |

**安全棒一轮现在读七面**：门面（创作页面 + 服务在听）· 进程面（按线归类 + 端口占用者）·
永久记忆 · 吞天融合 · 标签许可 · 成长钩子 · 控制回路。任一红 ⇒ 进 `alerts`。

## 八、绑定账的"悬空行"与剪枝（`tentacle_bind prune`）

绑定账的不变量是「**账里的资产都真在盘上**」。而产出即绑按 mtime 抓"此后新增"，会抓到**转瞬即逝**的东西：
血账 `gbt_allinone/recon/capability.json` 是吞天胶囊的中间产物，`ghost_guard` 按设计会清掉它
（「胶囊降威完整性」条款），于是那行绑定**永久把审计顶红**，人却找不到东西可修。

⇒ `autobind` 尾部顺手 `prune()`：**不在盘上的绑定自动剪掉**，理由进台账；
单独跑 `python tools/tentacle_bind.py prune` 也行。**这不是洗白数字**：剪的是"确实不在盘上"的行，
每次都记 `prune` 台账（asset + 原触手 + 理由），真要追还能从 git 里翻回来。


## 九、两条踩出来的坑（判据/钩子自己先坏）

1. **② 分派要认两种写法**：`api.py` 里大量能力位是**成组元组**（`if kind in ("a","b","c")`），
   不是逐个 `kind == "x"`。我第一版只认后者 ⇒ **一口气假报 25 条"没分派"**（blood account：
   `keylogger`/`film_intel`/`hook_enforcer` 都在元组里）。现在与 `tools/framework_state.py`
   同一把尺：**两种写法都算**，并立了回归判据 `test_d_grouped_dispatch_counts_as_wired`。
2. **同名不等于同一份**：给 `energy_pool` 写探针时按**文件路径**二次装载，拿到的是**第二个**模块对象，
   它内部注册表为 None ⇒ 探针自己抛 `AttributeError`，判据当场点出"探针坏了"。
   ⇒ 探针要**按包路径**导入（与判据同一份实例）。

## 十、和另一个同时在改这个仓的 agent 共存（2026-09-28 实测）

本轮跑测试时发现：**仓库里有另一个 agent 在同时改**（它新增了 `key_gateway` / `multimodal_port` /
`genoffice_bridge` 三个能力位、`deploy/vercel-brand/` 品牌站、改了 `security/policy.py` 声明作用域）。
由此吃过三类亏，记下来：

- **共用 `state/` 会互相踩**：两个测试进程同时跑时出现过假红（`TestAllNewCapsDispatchThroughDoor`
  单跑通过、并跑失败）。⇒ 跑全量回归时**只许一条在跑**；状态文件不是多进程安全的。
- **顶层树会凭空多出来**：`vercel-brand-protected/`（它打包品牌站时落在仓根）让反盲区判据 63→64 报红。
  处理：`.gitignore` 收掉 + `coverage_matrix sweep` 登记（**产出也要有人扫过**）。
- **`git add -A` 会把别人的半成品一起提交**：我那笔收尾提交里混进了它 25 个文件（3835 行）。
  不是丢东西，但**混账了**。⇒ 收尾提交前先 `git status` 逐条看清是谁的改动；跨 agent 共用仓时
  **按路径挑着加**，别一把 `-A`。

**别人的新能力位，我这套钩子照样管**：给它新增的三位走了一遍 `binding_hook after-add`
（补触手页 + 绑实现文件），现在 205 个能力位**六条腿全绿**、触手库 235/235。
