# 工具与改代码 · `tools`（9 位）

> 自动生成，数据源 `gbt_allinone/caps_registry.py`。只读 = 不改状态、不出网；其余调用前需人工授权（作用域门）。参数以 `requires_params` 标出。

| 能力位 | 类型 | 需参数 | 它做什么 |
|---|---|---|---|
| `awesome_tools_index` | 只读 | — | Awesome Tools 蒸馏索引（只读骨架·地图）：四原语 INDEX/LOOKUP/MAP/VERIFY；三条带牙判据（**索引只读** index_not_readonly / **映射可追** map_without_source / **未核实不标绿** unveri… |
| `capability_net` | 只读 | — | 穿透网七栏只读读数：indexed/entry_known/reachable/verified×2/has_test/penetrate_ready |
| `code_patch` | **需授权** | 是 | **改代码的唯一过门入口**（2026-09-23 接）：此前 agent 直接 edit/write 落盘 ⇒ **不过门、没审计、没信封、没改前改后凭据**。三原语 dry_run（**默认，只算不写**）/ apply（落盘，挂 filesystem_write）/ rol… |
| `freebuff_term` | 只读 | — | freebuff 终端集成（主人令 2026-09-28「把 freebuff 这个终端集成进我们的对话面板，编程就走这个」）：**正常 HOME 下 EPERM 起不来**（只认 $HOME/.config/manicode），隔离 HOME（%LOCALAPPDATA%\gb… |
| `git_read` | 只读 | — | **版本库只读面**（2026-09-23 接，补 `code_patch` 的另一半：「改完要能看、要能回滚」）：op=status/diff/log/show/branch_list/stash_list。七道机械闸：**绝不过 shell**（一律 shell=False）… |
| `git_write` | **需授权** | 是 | **版本库写面**（只两个 op，且**永远要点名路径**）：stage（`git add -- <paths>`）· commit（**pathspec-limited**：`git commit -m … -- <paths>`，只提交点名的路径，**不动索引里别的暂存内容*… |
| `projection_card` | 只读 | — | 空间投射只读卡片：5 原语全标未核实 + ARM ≠ LIVE 红线（只呈现不执行） |
| `pulse_direct` | 只读 | — | **脉冲直达**（主人令 2026-10-11「把脉冲给大模型，让她把所有的能力按触手双向绑定的部署方式**急速运行**、**省去不必要的多绕** —— 本来向前跨一步就到的东西，别跑一大圈才跨那一步」）：一句意图 => **一步**解析到能力位 => 给出那一条命令与要过的门，… |
| `repo_publish` | 只读 | — | **远端发布面**（补 `git_write` 的另一半 · 主人 2026-10-11 当场指出：tools 域只有 `git_read` 与只能 stage/commit 的 `git_write`⇒ **push 到远端 / 建仓 / 发 Release 根本没有能力位**… |

> 表格里是**摘要**（超过 140 字截断）；完整原文见 [`data/capabilities.json`](../../data/capabilities.json) 的 `desc` 字段。

---

返回 [能力总表](../03-capabilities.md)
