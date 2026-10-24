# 工具与改代码 · `tools`（9 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出；**必填载荷**与**常见错误**两列只写注册表登记过的（没登记就写「无必填」/通用三态），不猜。

| 能力位 | 类型 | 需参数 | 必填载荷 | 常见错误 | 它做什么 |
|---|---|---|---|---|---|
| `awesome_tools_index` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | Awesome Tools 蒸馏索引（只读骨架·地图）：四原语 INDEX/LOOKUP/MAP/VERIFY；三条带牙判据（**索引只读** index_not_readonly / **映射可追** map_without_source / **未核实不标绿** unveri… |
| `capability_net` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 穿透网七栏只读读数：indexed/entry_known/reachable/verified×2/has_test/penetrate_ready |
| `code_patch` | **需授权** | 是 | —（空载荷走该位默认 op） | `user_error` / `failed` | **改代码的唯一过门入口**（2026-09-23 接）：此前 agent 直接 edit/write 落盘 ⇒ **不过门、没审计、没信封、没改前改后凭据**。三原语 dry_run（**默认，只算不写**）/ apply（落盘，挂 filesystem_write）/ rol… |
| `freebuff_term` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | freebuff 终端集成（主人令 2026-09-28「把 freebuff 这个终端集成进我们的对话面板，编程就走这个」）：**正常 HOME 下 EPERM 起不来**（只认 $HOME/.config/manicode），隔离 HOME（%LOCALAPPDATA%\gb… |
| `git_read` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **版本库只读面**（2026-09-23 接，补 `code_patch` 的另一半：「改完要能看、要能回滚」）：op=status/diff/log/show/branch_list/stash_list。七道机械闸：**绝不过 shell**（一律 shell=False）… |
| `git_write` | **需授权** | 是 | —（空载荷走该位默认 op） | `denied: missing_scopes` / `user_error` | **版本库写面**（只两个 op，且**永远要点名路径**）：stage（`git add -- <paths>`）· commit（**pathspec-limited**：`git commit -m … -- <paths>`，只提交点名的路径，**不动索引里别的暂存内容*… |
| `projection_card` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | 空间投射只读卡片：5 原语全标未核实 + ARM ≠ LIVE 红线（只呈现不执行） |
| `pulse_direct` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **脉冲直达**（主人令 2026-10-11「把脉冲给大模型，让她把所有的能力按触手双向绑定的部署方式**急速运行**、**省去不必要的多绕** —— 本来向前跨一步就到的东西，别跑一大圈才跨那一步」）：一句意图 => **一步**解析到能力位 => 给出那一条命令与要过的门，… |
| `repo_publish` | 只读 | — | —（空载荷走该位默认 op） | `user_error` | **远端发布面**（补 `git_write` 的另一半 · 主人 2026-10-11 当场指出：tools 域只有 `git_read` 与只能 stage/commit 的 `git_write`⇒ **push 到远端 / 建仓 / 发 Release 根本没有能力位**… |

> 表格里是**摘要**（超过 140 字截断）；下面每位还有**逐位详解**（完整原文 / 要哪张票 / 真调用命令 / 缺什么会怎么报）。

---

## 逐位详解

### `awesome_tools_index`

- **域**：`tools`（工具与改代码）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：Awesome Tools 蒸馏索引（只读骨架·地图）：四原语 INDEX/LOOKUP/MAP/VERIFY；三条带牙判据（**索引只读** index_not_readonly / **映射可追** map_without_source / **未核实不标绿** unverified_green）+ 五条红线（只读/映射带出处/未核实不标绿/只引用不复制/不绕官方入口）；主人明确配对的六个重点工具（CC Switch→auto_switch · MoneyPrinterTurbo/Huobao Drama/LocalMiniDrama→video_pipeline · CowAgent→im_multiplex · OpenClaw Monitor→god_view）**全部 unverified（盘上 0 命中）**；仓库内容未取证 ⇒ 索引池为空且**不编**；type=external
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap awesome_tools_index '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `capability_net`

- **域**：`tools`（工具与改代码）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：穿透网七栏只读读数：indexed/entry_known/reachable/verified×2/has_test/penetrate_ready
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap capability_net '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `code_patch`

- **域**：`tools`（工具与改代码）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：是 —— path=仓内相对路径；find=必须**恰好出现一次**的原文；replace=新文；默认 op=dry_run（只算不写），要落盘给 op=apply（要 filesystem_write 授权）
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**改代码的唯一过门入口**（2026-09-23 接）：此前 agent 直接 edit/write 落盘 ⇒ **不过门、没审计、没信封、没改前改后凭据**。三原语 dry_run（**默认，只算不写**）/ apply（落盘，挂 filesystem_write）/ rollback（按回执退回）。九道机械闸：**仓内**（路径解析后必须在仓内）· **find 恰好一次**（0 次 not_found；>1 次 ambiguous —— **绝不替你挑一个**）· **空改动拒写** · `expect_sha256` 对不上拒（防拿陈旧内容改）· **二进制拒改**（前 8KB 有 NUL）· >4MB 拒改 · **逐字节替换**（换行/BOM 一个字节不动 —— 文本层替换会把整个文件行尾改掉）· **原子写**（tmp+os.replace）· **回执可回滚**（记 find/replace/改前改后哈希；回滚前先核 after_sha256，对不上就拒）。type=internal
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap code_patch '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `freebuff_term`

- **域**：`tools`（工具与改代码）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：freebuff 终端集成（主人令 2026-09-28「把 freebuff 这个终端集成进我们的对话面板，编程就走这个」）：**正常 HOME 下 EPERM 起不来**（只认 $HOME/.config/manicode），隔离 HOME（%LOCALAPPDATA%\gbt-freebuff\home）下装成并验活（0.1.2）。`status` 真身/版本/登录态 · `flags` 现跑 --help（**钉住"TUI-only、无一次性 prompt"**）· `launch` 用隔离 HOME 起真终端（过 process_execute 门）· `login_hint` 给主人登录命令。op=status/flags/launch/login_hint/verify/where
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap freebuff_term '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `git_read`

- **域**：`tools`（工具与改代码）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**版本库只读面**（2026-09-23 接，补 `code_patch` 的另一半：「改完要能看、要能回滚」）：op=status/diff/log/show/branch_list/stash_list。七道机械闸：**绝不过 shell**（一律 shell=False）· **反选项注入**（rev/path 不许以 `-` 开头）· **路径必须在仓内** · **每条命令带 `--`** · **超时 60s + 输出上限 200KB** · status 只报数量与前 40 条（本仓脏行上万，全量灌回来没意义）· **零作用域**（policy 里不挂任何 scope）。⚠️ 不做 rebase/reset --hard/push —— 那些是「改历史/出网」，要单独设计。type=internal
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap git_read '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `git_write`

- **域**：`tools`（工具与改代码）
- **类型**：**需授权**（会写盘 / 花钱 / 出网） · **需参数**：是 —— paths=要动的仓内路径列表（**必填、不许空**）；commit 还要 message；op=stage|commit
- **要哪张票（静态）**：`filesystem_write`
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：缺票 → `denied`，回执点名 `missing_scopes`（本行静态票：`filesystem_write`）；参数非法 → `user_error`；依赖不在位 → `needs_dependency`；上游不给 → `needs_input` / `failed`（带上游原话）
- **它做什么**：**版本库写面**（只两个 op，且**永远要点名路径**）：stage（`git add -- <paths>`）· commit（**pathspec-limited**：`git commit -m … -- <paths>`，只提交点名的路径，**不动索引里别的暂存内容**）。为什么必须点名：本仓脏行可能上万，`commit -a` 一次就把不相干的全卷进去。**永远挂 `filesystem_write`**（不按 op 判 —— 拆成独立能力位就是为了让门的判据平凡正确）。与 `git_read` 分开登记：`safe` 是按能力位记的，不是按 op 记的。type=internal
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap git_write '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `projection_card`

- **域**：`tools`（工具与改代码）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：空间投射只读卡片：5 原语全标未核实 + ARM ≠ LIVE 红线（只呈现不执行）
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap projection_card '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `pulse_direct`

- **域**：`tools`（工具与改代码）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**脉冲直达**（主人令 2026-10-11「把脉冲给大模型，让她把所有的能力按触手双向绑定的部署方式**急速运行**、**省去不必要的多绕** —— 本来向前跨一步就到的东西，别跑一大圈才跨那一步」）：一句意图 => **一步**解析到能力位 => 给出那一条命令与要过的门，并把 **hops（绕弯数）写进账**：hops=1 直接命中 / hops=2 命中页面包装层（该收敛）/ hops=0 没命中（如实报，不编）。op=audit 读回**一步命中率** => 「省多绕」变成可量的事。三根支柱现读：能力位册 / 双向绑定(cap-bindings+page-caps) / 唯一门 run_task。与既有 tools/pulse.py（每日情报调研执行层）不是一件东西，不覆盖不合并。op=resolve/audit
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap pulse_direct '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

### `repo_publish`

- **域**：`tools`（工具与改代码）
- **类型**：只读（不改状态、不出网） · **需参数**：否
- **要哪张票（静态）**：零作用域（空 payload 下不需要票）
- **必填载荷**：无必填（空载荷落到该位默认 op；位内更细的 op 参数见模块）
- **常见错误**：参数非法 → `user_error`
- **它做什么**：**远端发布面**（补 `git_write` 的另一半 · 主人 2026-10-11 当场指出：tools 域只有 `git_read` 与只能 stage/commit 的 `git_write`⇒ **push 到远端 / 建仓 / 发 Release 根本没有能力位** ⇒ 前面全靠手搓 git push/wrangler ✗）。口径：**不可逆外部动作 ⇒ 过 `deploy_publish` 一次性门**；出网硬钉（只许 https + github.com/api.github.com/huggingface.co）；**凭据永不回显**（本件第一版吃过把 token 带进报错的亏）；只追加落账 store/repo_publish/ledger.jsonl；不假装（没权限如实报）。op=status/plan/push
- **怎么调**：`py -3.14 tools/codex-scripts/five-dim.py cap repo_publish '<json>'`
- **失败三态**（本仓统一口径，不是这一位特有）：`denied` = 缺票，会点名`missing_scopes`；`needs_*` = 缺参/缺依赖，会带原因；`failed` = 真失败，回执带上游原话。**信封 `status=ok` ≠ 本体 `ok=true`。**

---

返回 [能力总表](../03-capabilities.md)
