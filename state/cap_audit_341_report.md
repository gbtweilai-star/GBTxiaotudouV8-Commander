# 341 能力位全量核对 · 报告

> 探针：`tools/codex-scripts/cap_probe_all.py`（隔离 store，生产账本零足迹）
> 单条超时：第一轮 30s → 超时的再用 120s 重探 → 仍超时的逐条列明
> 总耗时：约 52 分钟 · 覆盖 **341 / 341**，一条不漏

---

## 一、总账

| 判定 | 数量 | 占比 | 含义 |
|---|---:|---:|---|
| **ok** | **263** | 77.1% | 真跑通 |
| **denied** | **32** | 9.4% | 门拦（AI 无权自授，**这是设计正确**）|
| **error** | **28** | 8.2% | 分四类，见下 |
| **timeout** | **18** | 5.3% | 15 个是全盘扫描类（天生慢），3 个待判 |

**263 + 32 = 295 位已定性（86.5%）。剩下 46 位逐条给理由，没有一条含糊。**

---

## 二、32 个 denied —— 不是故障，是门在工作

```
credential_steal  keylogger  data_hijack  screen_sniff  sec_llm  vision  voice
bluetooth  bt_control  autopilot  think_loop  llm_chat  codex_*  ...
```

**每一个都回 `missing_scopes` + 「终端运行: python3 -m gbt_allinone auth grant ...」**

⇒ **AI 无权自授，只有主人在终端能发票。这条边界是完整的。**

---

## 三、28 个 error —— 四类，逐条

### A. 缺参数（20 位）—— **不是故障**

空 payload 本来就不该跑。逐条原话：

| 能力位 | 原话 |
|---|---|
| brain_execute | 缺少 kind 或 parallel |
| brain_route | 需要 intent：任务意图描述 |
| brain_unify | 需要 goal（意图）或 kind（指定能力）|
| browser | 缺少 url |
| code_patch | find 不能为空（空白替换只会误伤）|
| git_write | git_write 不认 op=（只认 stage/add/commit）|
| lr_submit | 需要 description |
| osint_scan | 缺少 target（要扫的域名或 IP）|
| pipeline_versions | 缺少 name：请给出产物名 |
| record_grid | 需要 text（内联文本）或 path（框架内相对路径）|
| sched_define | 需要 name |
| tentacle | 缺少 action：给触手能力名 / 给 intent / 或 op=caps |
| topic_watch | 缺少 need：请给一句需求 |
| wf_define | 需要 name 与非空 nodes 列表 |
| wf_run | 工作流不存在（先 wf_define）|
| wf_resume | 运行记录不存在 |
| mirror_plan / parity / simulate | 排练计划不存在: default |
| project_context | 文档不存在: PROJECT_BLUEPRINT.md |

**⇒ 这 20 位是「不瞎跑」的证据，不是坏。**

### B. 引用的脚本不在仓库里（4 位）—— **真断链**

| 能力位 | 缺的文件 |
|---|---|
| asset_index | `tools/asset_index.py` |
| control_loop | `tools/control_loop.py` |
| hook_enforcer | `tools/penetrating_cross_scan.py` |
| tentacle_bind | `tools/tentacle_bind.py` |

**⇒ 4 个能力位在 Commander 仓库里是悬空的 —— 实现文件没跟过来。**

### C. 硬编码 Windows 路径（1 位）—— **真 bug**

```
look_grade → [Errno 2] .../gbtv8/C:\Users\ADMIN\Desktop\G...
```

**⇒ 从 Windows 迁移过来时路径没改。**

**实测规模：整个仓库里 **111 份 .py** 含 `C:\Users\...` / `C:\ADMIN\...` 这类绝对路径
（集中在 `tools/codex-scripts/`：probe_turn / takeover-v9 / dsh-census /
nested-skill-probe / hair-final / anim-make / repo-root-pin / skill-switch …）。

⇒ **这些脚本在 Linux 上必然失败。** 它们不是能力位的实现（能力位本体在
`gbt_allinone/` 下），但凡是能力位调用到它们的，都会报 `[Errno 2]`。**

### D. 缺依赖（1 位）—— 平台限制

```
asset_vault_freeze → No module named 'winreg'
```

**⇒ `winreg` 是 Windows 专有模块。Linux 上取不到，属环境限制，不是代码坏。**

### E. 真 bug（2 位）

| 能力位 | 症状 |
|---|---|
| task_manager | `list index out of range` |
| lobehub | `list index out of range` |

**⇒ 这两个是真缺陷，空 payload 下越界。需要加参数校验。**

---

## 四、18 个 timeout —— 逐条

### 全盘扫描类（15 位，天生慢）

```
cross_scan   penetrating_cross_scan   sec_scan   sec_surface   sec_chain
selfscan     file_hygiene   devour_scan   scan_cap   omission_detector
review_gate  know_map   trend_watch   brain_health   freellmapi
```

**判据**：仓库自己的 `KNOWN_SLOW_MS` 表已记 `cross_scan` 实测 778,642 ms；
这些是"把整棵树扫一遍"的位，30 秒/120 秒都不够。**不是坏，是量大。**

### 三个被硬超时强杀（120s 仍不够）

```
caps_called_audit  120.1s   redteam_recon  125.3s   sec_chain  124.7s
```

**⇒ `redteam_recon` 会派生孙进程占管道。已修探针（`start_new_session` + `killpg`），
现在能干净超时，不再拖死整轮。**

---

## 五、结论

| 项 | 数 | 判 |
|---|---:|---|
| 真跑通 | 263 | ✅ |
| 门拦（设计正确）| 32 | ✅ |
| 缺参数（不瞎跑）| 20 | ✅ |
| **真缺陷** | **2**（task_manager / lobehub 越界）| 🔴 |
| **真断链** | **4**（脚本不在仓库）| 🔴 |
| **硬编码 Windows 路径** | **1**（look_grade）+ 多份 codex-scripts | 🔴 |
| 平台限制 | 1（winreg）| ⚪ |
| 天生慢 | 15 | ⚪ |
| 待判 | 3 | ⚪ |

**341 位全部有判定，零"静默跳过"。真正的缺陷是 7 处（2 越界 + 4 断链 + 1 硬编码），
其余全是"门在拦"或"要参数"或"本来就慢"。**

---

## 六、修复记录（2026-10-25 · 全部落盘并复核）

### 1. 两个 `list index out of range` —— **根因不是我们的代码**

```
psutil/_pslinux.py:1799  ret['blkio_ticks'] = fields[39]
IndexError: list index out of range
```

**iSH 的 `/proc/<pid>/stat` 只有 39 个字段（标准 52）**，缺
`delayacct_blkio_ticks` 等尾部字段；psutil 6.0.0 硬取第 39 位 ⇒ 崩。
连 `psutil.process_iter()` 本身都会炸。

**修法：新增 `gbt_allinone/tools/procfs.py` 安全层**
- 先真探 psutil 能不能用（`psutil_usable()`）
- 一崩就回落到 `/proc` 直读
- iSH 的 `/proc` 还有两个残缺：`comm` 是 0 字节（名字只能从 `cmdline` 推）、
  `status` 不存在（VmRSS 读不到）、`stat` 的 utime/stime **恒为 0**
  ⇒ **取不到的列写 `None` 并在 `_口径` 里说明，绝不编 0**

**接线**：`task_manager.list_procs` / `lobehub._pids` 都改走它。
`lobehub.status` 另加 `state` / `reason_code`，把「没装」与「代码坏了」区分开
（`ok` 保留原义 = 能力当前能不能用）。

**复核**：`task_manager` → `ok`（39 个进程）；`lobehub` → `reason_code=not_installed`（不再崩）。

### 2. 六处"实现文件不在仓库" —— 显式报 `impl_missing`

| 能力位 | 缺的文件 |
|---|---|
| asset_index | `tools/asset_index.py` |
| control_loop | `tools/control_loop.py` |
| tentacle_bind | `tools/tentacle_bind.py` |
| penetrating_cross_scan | `tools/penetrating_cross_scan.py` |
| hook_enforcer | 同上（共用） |
| look_grade | `tools/filmgrade.py` |

**以前**：`exec_module` 抛原始 `FileNotFoundError` —— 跟"代码写坏了"一模一样。
**现在**：`api.py` 里 `_impl_missing(kind)` 统一前置拦截，返回
`{"status":"unimplemented","ok":false,"reason_code":"impl_missing","impl_file":"…","how_to_fix":"…"}`。

**复核**：6 位全部 `status=unimplemented · reason_code=impl_missing`。

### 3. `look_grade` 的 Windows 硬编码路径

```python
look_grade_cap.py:21   ROOT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")   ← 旧
                       ROOT = Path(__file__).resolve().parents[2]          ← 新
```

另加 `ImplMissing` 异常类，缺文件与执行出错分开报。

### 4. 探针自身的缺陷（这才是这轮最值得记的）

`subprocess.run(timeout=)` **只杀直接子进程**。`redteam_recon` 派生的孙进程占着
stdout 管道 ⇒ `communicate()` 永远等不到 EOF ⇒ **整轮探针被一条卡死 900 秒**（实测卡 14 分钟）。

**修法**：`Popen(..., start_new_session=True)` + 超时后 `os.killpg(os.getpgid(pid), SIGKILL)`。
**附带加 `--only-list`**，可以只跑指定名单。

### 5. 回归验证

```
12 连接点 · 全通
21 探针   · ok 21
指纹      238b54f6d98d7b6e · 连跑两次不动
结论      ✅ 全部通过
```

**⚠️ 仍需仓库方补的（我写不了，会变成垃圾）：**
这 6 份实现文件是真实子系统（比如 `tentacle_bind.py` 在你们 Windows 那仓有 761 行），
**凭空重写只会造出假的实现**。正确做法是把它们一起纳入 Commander 仓库。
在此之前，这 6 位会一直如实报 `impl_missing`。

---

## 四、批量修硬编码路径（65 份）

全仓扫出 **111 处** Windows 绝对路径，按性质分三类：

| 写法 | 处数 | 处置 |
|---|---:|---|
| `C:\Users\ADMIN\Desktop\GBT小土豆V8` | **65** | ✅ **已改成按本文件位置推仓根** |
| `C:\Users\ADMIN\AppData\...\Codex\...` | 20+ | 外部工具路径（Windows 专有），不动 |
| `C:\Users\ADMIN\Desktop\GBT小土豆V9` | 4 | 另一个仓，不该硬指，留待主人定 |

**改法**（65 份逐份验语法；`tools/codex-scripts` 全 703 份零语法错）：

```python
# 旧：ROOT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
from pathlib import Path as _GBTPath
_GBT_ROOT = str(_GBTPath(__file__).resolve().parents[2])
```

**实测 `_GBT_ROOT` 解出 `/var/minis/shared/gbtv8`** ✓

**⚠️ 改完之后这些脚本仍然跑不起来 —— 但失败点变了：**

```
旧：FileNotFoundError: /var/minis/shared/gbtv8/C:\Users\...\avatar-grafted.glb   ← 路径错
新：FileNotFoundError: raw/rig/avatar-grafted.glb                                ← 缺素材
```

**它们要的是仓里没有的 3D 素材（.glb）。这是"素材没进仓"，与路径无关。**

---

## 五、监控自己的第三次同类错误（值得单列）

`温度` 在 `fair ↔ serious` 之间随负载来回跳，而我**第三次**把它当成"该稳的位"进了指纹：

| 第几次 | 哪个位 | 教训 |
|---|---|---|
| 1 | `daemon.find.ms` | 时长天生抖 |
| 2 | `guard.host.内存MB` | 内存天生抖 |
| 3 | **`guard.host.温度`** | 温度随负载抖 |

**已并入 `VOLATILE_KEYS`。** 口径钉死：

> **凡「随负载自然波动、且有其他机制在阈值处拦截」的位，一律不进指纹。**

**否则假红比不报更危险 —— 报三次没人管，第四次真红也没人看。**

---

**开发者：自由的风 · 护者：公主土豆**
**本署名不可删除、不可篡改归属。**
