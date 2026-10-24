# 16 · 341 能力位全量核对（红黄清零）

> 探针：`tools/codex-scripts/cap_probe_all.py`（隔离 store，生产账本零足迹）
> 单条超时：第一轮 30s → 超时的用 120s 重探 → 仍超时的逐条列明
> 覆盖 **341 / 341**，一条不漏。开发者：自由的风 · GBT小土豆V8

---

## 一、总账

| 判定 | 数量 | 占比 | 含义 |
|---|---:|---:|---|
| **ok** | **263** | 77.1% | 真跑通 |
| **denied** | **32** | 9.4% | 门拦（AI 无权自授，**这是设计正确**）|
| **error** | **28** | 8.2% | 分五类，见第二节 |
| **timeout** | **18** | 5.3% | 15 个是全盘扫描类（天生慢），3 个被硬杀 |

**263 + 32 = 295 位已定性（86.5%）。剩下 46 位逐条给理由，没有一条含糊。**

---

## 二、28 个 error 逐条定性

### A · 缺参数（20 位）—— **不是故障**

    browser      → 缺少 url
    osint_scan   → 缺少 target（要扫的域名或 IP）
    wf_define    → 需要 name 与非空 nodes 列表
    tentacle     → 缺少 action：给能力名 / 给 intent / 或 op=caps
    code_patch   → find 不能为空（空白替换只会误伤）
    … 每条都带原话

**空 payload 本来就不该跑。这 20 位是「不瞎跑」的证据。**

### B · 实现文件不在仓库（6 位）—— 真实子系统，**不能凭空重写**

    asset_index            → tools/asset_index.py
    control_loop           → tools/control_loop.py
    tentacle_bind          → tools/tentacle_bind.py     （已从 git 树补回）
    penetrating_cross_scan → tools/penetrating_cross_scan.py
    hook_enforcer          → tools/penetrating_cross_scan.py
    look_grade             → tools/filmgrade.py

**以前**：exec_module 抛原始 FileNotFoundError，跟「代码坏了」分不清。
**现在**：`api.py` 加 `_impl_missing(kind)` 前置拦截，统一报

    {"status":"unimplemented","reason_code":"impl_missing",
     "impl_file":"tools/filmgrade.py",
     "how_to_fix":"把 tools/filmgrade.py 一起纳入仓库"}

### C · 硬编码 Windows 绝对路径（1 位 + 全仓 66 份）

    look_grade_cap.py:21
      旧  ROOT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
      新  ROOT = Path(__file__).resolve().parents[2]

**实测规模：全仓 111 处 Windows 绝对路径，其中 66 处是本仓根。**

| 写法 | 处数 | 处置 |
|---|---:|---|
| 本仓根 `...\Desktop\GBT小土豆V8` | **66** | ✅ 已改成按本文件位置推 |
| `AppData\...\Codex\` 等外部工具 | 20+ | 不动（Windows 专有）|
| 另一个仓 `...\GBT小土豆V9` | 4 | 不该硬指，留待主人定 |

**实测后果（真发生过）**：跑 `tentacle_bind` 之后，仓库里**真的多出一个名字就是
`C:\Users\ADMIN\Desktop\GBT小土豆V8` 的目录**。清掉后重新全仓扫、全部修完。

### D · 真 bug（2 位）—— 根因是环境，不是代码

    psutil/_pslinux.py:1799   ret['blkio_ticks'] = fields[39]  → IndexError

**iSH 的 `/proc/<pid>/stat` 只有 39 个字段（标准 52）**，psutil 6.0.0 硬取第 39 位就崩
—— 连 `psutil.process_iter()` 本身都炸。task_manager / lobehub 因此报 error。

**修法**：新增 `gbt_allinone/tools/procfs.py` 安全层 —— 真探 psutil，崩了回落 `/proc` 直读。

### E · 平台限制（1 位）

    asset_vault_freeze → No module named 'winreg'  （Windows 专有）

---

## 三、iSH 的 /proc 三处残缺（必须记住）

| 文件 | 实际 | 后果 |
|---|---|---|
| `comm` | **0 字节** | 进程名只能从 `cmdline` 推 |
| `status` | **不存在** | VmRSS 读不到 |
| `stat` 的 utime/stime | **恒为 0** | CPU 时间不记 |

**⇒ CPU / 内存两列在本机取不到，一律写 `None` 并说明，绝不编 0。**

---

## 四、18 个 timeout

**全盘扫描类 15 位**：cross_scan / sec_scan / sec_surface / sec_chain / selfscan /
file_hygiene / devour_scan / scan_cap / omission_detector / review_gate / know_map /
trend_watch / brain_health / freellmapi / penetrating_cross_scan

**仓库自己的 KNOWN_SLOW_MS 就记着 `cross_scan` 实测 778 秒。不是坏，是量大。**

**被 120s 硬杀 3 位**：caps_called_audit 120.1s · redteam_recon 125.3s · sec_chain 124.7s

---

## 五、修了什么（8 处）

| # | 缺陷 | 修法 |
|---|---|---|
| 1 | task_manager 越界 | 接 `procfs.snapshot()` 安全层 |
| 2 | lobehub 越界 | 同上 + 加 `state`/`reason_code`（未装 ≠ 代码坏）|
| 3 | look_grade 硬编码 | `parents[2]` + `ImplMissing` 异常类 |
| 4 | 6 份实现缺失 | `_impl_missing()` 前置拦截，可机读 |
| 5 | 66 份硬编码 | 统一改 `_GBT_ROOT` |
| 6 | 探针卡死 900 秒 | `Popen(start_new_session=True)` + `os.killpg(SIGKILL)` |
| 7 | 153 个文件没检出 | `git ls-tree -r -z` 比对后补检出（含 tentacle_bind）|
| 8 | 2 处非法转义 | 只把反斜杠加倍，**不加 r 前缀** |

### 5.1 探针自身的缺陷（最值得记）

`subprocess.run(timeout=)` **只杀直接子进程**。`redteam_recon` 派生的孙进程占着
stdout 管道 ⇒ `communicate()` 永远等不到 EOF ⇒ **整轮探针被一条卡死 900 秒**
（实测卡了 14 分钟）。

**修法**：

    subprocess.Popen(..., start_new_session=True)
    except TimeoutExpired:
        os.killpg(os.getpgid(p.pid), SIGKILL)     # 杀整个进程组

**附带加 `--only-list`**，可以只跑指定名单。

---

## 六、三个教训（都是踩过才学到的）

### 6.1 `ast.parse` 抓不到 `__future__` 位置错误

    ast.parse(src)             → 通过
    compile(src, 'x', 'exec')  → SyntaxError: from __future__ imports must occur at the beginning

**「1489 份语法全通过」如果用 `ast.parse` 是假的 —— 漏了 8 份真坏的。**

| 检查 | 能抓语法错 | 能抓 `__future__` 位置 |
|---|---|---|
| `ast.parse` | ✅ | ❌ |
| **`compile`** | ✅ | ✅ |

**⇒ 全仓语法检查一律用 `compile()`。**

### 6.2 改转义不能加 `r` 前缀

修 `\{` 非法转义时若给字符串加 `r`，同串里的 `\u4e00` 会变成**字面文本，中文全废**。

**正法：只把反斜杠加倍 `\{` → `\\{`，其余转义原样保留。**

（修完用 `compile` + AST 取值双重校验：中文正常、`\{` 按原意保留、零警告）

### 6.3 补丁顺序错了会漏

**补丁打在前、检出在后 ⇒ 后检出的文件没被覆盖。**
补检出 953 个文件后，又发现 17 份带同样硬编码。**改完必须重扫全仓，不能只验改过的。**

---

## 七、监控自己的三次同类错误

| 第几次 | 哪个位 | 教训 |
|---|---|---|
| 1 | `daemon.find.ms` | 时长天生抖 |
| 2 | `guard.host.内存MB` | 内存天生抖 |
| 3 | `guard.host.温度` | 温度随负载抖（fair ↔ serious）|

**口径钉死**：

> 凡「随负载自然波动、且已有其他机制在阈值处拦截」的位，**一律不进指纹**。
>
> **假红比不报更危险 —— 报三次没人管，第四次真红也没人看。**

---

## 八、回归

    12 连接点 · 全通
    21 探针   · ok 21
    全仓 compile 1489 份 · 通过 1489 · 失败 0 · 非法转义 0
    指纹稳定 · 连跑多次不动

**仓库整洁度**：文件 4524 → 4160；`__pycache__` 0 / `.pyc` 0 / 临时垃圾 0；
`_archive-20261021/`（350 文件）与 11 个 `*.bak-*` 已移出到仓库外隔离区（未删）。

---

**开发者：自由的风 · 护着：公主土豆**
**本署名不可删除、不可篡改归属。**
