# gbt-quickscan · 全维度扫描故障问题速扫

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> 固化自 **2026-09-23 全树穿透扫描第 1 轮**（111,626 文件 / 7.22 GB / 723 s 深扫 +
> 万能插最大档 147 能力位逐个过筛 / 412 s）。把那一轮的六步走法炼成**一件能反复跑的速扫器**。

**一句话**：一条命令，**约 35–50 秒**（本机实测 33.3 / 38.9 / 44.5 s，7.4 万文件）把七个面的故障全摆出来，
并且告诉你**比上一轮新增了几条、修好了几条** —— 让"扫不完"变成"已收敛"这个可判定的状态。

---

## 1. 什么时候用它（触发）

- 说「速扫 / 全维度扫描 / 扫故障 / 体检一下 / 有没有新毛病 / 今天扫一遍」
- 任何一次大改动**之后**要确认没添新病
- 心跳里当作固定体检项（它带收敛判据，适合周期跑）
- 想要 cross_scan 之外的**第二把异质尺**（cross_scan 只看生产代码面，本件看另外四面）

**不该用它**：要逐字节解析全树内容（那是 `deep_scan` 的活）· 要验技能蒸馏覆盖
（那是 `verify-distill.py`）· 要判"能力接没接上"（那是 `cross_scan`）。

---

## 2. 怎么跑（真命令）

### 2.0 🔴 cwd 契约（这一条是拿一次真实失败换来的）

**`tools/codex-scripts/quick_scan.py` 是仓内相对路径。**
在 `C:\Users\ADMIN` 下敲 `py -3.14 tools/codex-scripts/quick_scan.py` 会有两种下场：

```
can't open file 'C:\\Users\\ADMIN\\tools\\codex-scripts\\quick_scan.py': [Errno 2] No such file or directory
```

**三种正确姿势，任选：**

```powershell
# ① 最省事：用仓根的一键启动器（从**任何目录**都能跑；已逐字节验证纯 ASCII）
& "C:\Users\ADMIN\Desktop\GBT小土豆V8\quick-scan.cmd"              # 速扫
& "C:\Users\ADMIN\Desktop\GBT小土豆V8\quick-scan.cmd" --with-gates
& "C:\Users\ADMIN\Desktop\GBT小土豆V8\quick-scan.cmd" --accept
& "C:\Users\ADMIN\Desktop\GBT小土豆V8\quick-scan.cmd" --quiet      # 只看退出码

# ② 或者先 cd 到仓根，再用相对路径
cd C:\Users\ADMIN\Desktop\GBT小土豆V8
.\quick-scan.cmd
#   等价： py -3.14 tools\codex-scripts\quick_scan.py

# ③ 或者用**绝对路径**（工具按 __file__ 定位仓根，与 cwd 无关）
py -3.14 "C:\Users\ADMIN\Desktop\GBT小土豆V8\tools\codex-scripts\quick_scan.py"
```

### 2.1 全部开关

```powershell
# ── 扫描档位 ────────────────────────────────────────────────
py -3.14 tools/codex-scripts/quick_scan.py                 # 速扫（实测 55–65 s，37 条故障，含安全面）
py -3.14 tools/codex-scripts/quick_scan.py --with-tests     # 真跑 pytest --collect-only ×2（+16 s）
py -3.14 tools/codex-scripts/quick_scan.py --with-host      # 接入仓内已有主机六层 L3-L5（+6 s）
py -3.14 tools/codex-scripts/quick_scan.py --host-sign      # 配合 --with-host：进程签名核验（+150 s，很慢）
py -3.14 tools/codex-scripts/quick_scan.py --with-gates     # 追加跑框架自带的只读门（+90~270 s）
py -3.14 tools/codex-scripts/quick_scan.py --av-scan        # 🔴 真跑一次 Defender 按需扫描（慢，需你知情）
py -3.14 tools/codex-scripts/quick_scan.py --no-security    # 跳过安全面(S)
py -3.14 tools/codex-scripts/quick_scan.py --no-ledger      # 不往台账追加本轮

# ── 自动进化层（三个只读子命令，各自退出）──────────────────────
py -3.14 tools/codex-scripts/quick_scan.py --selftest       # 负对照自检：种假故障验判据真会响
py -3.14 tools/codex-scripts/quick_scan.py --discover       # 病因对账：该进化什么 + 判据死活三分
py -3.14 tools/codex-scripts/quick_scan.py --trend          # 自动收集台账：首见/末见/次数/常驻/闪断

# ── 基线与输出 ──────────────────────────────────────────────
py -3.14 tools/codex-scripts/quick_scan.py --accept         # 把本轮定为新基线（收敛判据归零）
py -3.14 tools/codex-scripts/quick_scan.py --quiet          # 只给退出码（心跳 / CI 用）
py -3.14 tools/codex-scripts/quick_scan.py --json PATH      # 指定输出路径
$env:GBT_QUICKSCAN_OUT="D:\somewhere"                       # 改输出目录（默认 %TEMP%\gbt-quickscan\）
```

> ⚠️ **基线与开关必须配套**：`--accept` 把当时的开关集一起存进基线；之后换开关复跑会打
> **`不可比`**（按家规不得直接判为"新增故障"），而不是假报新增。

**退出码就是门**：`0` 只有 P2/无故障 · `1` 有 P0 · `2` 有 P1 · `3` 扫描器自身出错。

**典型输出（2026-09-23 现读，默认档）**：
```
故障：P0=5  P1=14  P2=18  合计=37
安全面：反病毒在位=True · **本仓被排除=True** · 排除 12 条 · 远控自启 1 · IOC 8
进化层：台账 5 轮 · 目录 78 条 · **待进化 10** · 休眠 5 · 可疑 29 · 未登记 0
收敛：新增 8 · 已修 0 · 未变 26 ｜ 读数变化 3（基线 … ｜ 口径 {'with_gates': False, 'with_tests': False}）
```

**`--with-tests` 的硬证据长这样**（今天最大发现的机器化）：
```
[P1][T] TEST_COLLECT_ZERO  默认姿势收不到任何用例（设隔离 store 才收得到）
      证据: 不设 GBT_STORE_DIR：collected=0 errors=81 ｜ 设了：collected=1623
```

---

## 3. 它扫哪几面（R1 先切面再扫）

| 面 | 判据（闭集） | 主要检查 |
|---|---|---|
| **P1 生产代码面** | 能不能跑 | `.py` 语法 · 绝对/相对导入断链 · 依赖声明 vs 实际导入 · 裸 except · TODO 阈值 · 无效转义 · BOM/非UTF8/乱码/混合换行/NUL · JSON·YAML·TOML 解析 |
| **P2 运行数据面** | 该不该住在代码树里 | `gbt_allinone/store/` 体量与文件数（含 `mirror_space` 副本） |
| **P3 作业临时面** | 该不该在索引里 | `.scratch/` `.trash/` `.backups/` 体量 · 临时残骸名 · 空文件 · 空目录 |
| **P4 第三方参考面** | 是不是同内容多份 | `node_modules` 份数 · 同名同体积大文件多份 · 超 5 MB 大文件 · **`.shadow-repo` 与真身漂移** |
| **P5 装机系统面** | 指向对不对 | 五个技能根各有多少 `gbt-*` · **本会话读得到哪几个** · 计划任务目标是否在仓外/是否缺失 · 兄弟工作区 · 解释器口径 · **宿主版本 vs 盘上包声明** · **0.0.0.0 上的应用端口** |
| **T 测试口径面** | 结论由谁决定 | 仓内有无自证配置 · **仓外配置是否劫持 rootdir/超时** · `--with-tests` 时真跑 `--collect-only` 拿 `0 vs N` |
| **G 索引面** | 索引里该有什么 | 跟踪数/残骸占比/残骸 MB · 脏行分布 · **索引里的真格式密钥（像真的 vs 夹具分开判）** · 入库大文件 · **生产面各顶层入库比例** · **未入库散件（含根级交付物）** |
| **F 框架门面**（`--with-gates`） | 框架自己怎么判 | `selfscan` `truth_scan` `file_hygiene` `inventory` `signature_guard` `auth_gate_status` `health` `ghost_guard` `caps_called_audit` `coverage_auditor` `sec_surface` `sec_defenses` `sec_scan` `sec_chain`（全走**隔离 store**，生产零足迹；挂死即报 `GATE_RED`） |
| **S 安全面**（默认开，`--no-security` 关） | 病毒木马与暴露面 | **反病毒「在位」与「在看你」**（排除项遮蔽）· 持久化与**远控自启** · 内容 IOC（下载执行/编码命令/关防护…）· npm 供应链 · hosts 与代理 · **扩展名伪装**（读文件头）·（可选）MegaScan 按需扫描 ·（可选）主机六层 L3-L5 |
| **进化层**（每次都跑，只读） | 覆盖是否在长 | **台账**（每轮追加）· **病因对账**（该进化什么 / 判据死活三分）· **负对照自检**（种假故障验判据真会响） |
| **辅助读数**（不单独报警，随报告输出） | —— | 时钟口径（本机 UTC+7 vs 面板读数走 UTC）· 面板登记表 ↔ 盘上实物 · 监听端口清单 |

## 4. 六条硬规则（固化的核心，不许删）

| # | 规则 | 本件怎么实现的 |
|---|---|---|
| **R1** | 先切面再扫，每面一条闭集判据 | §3 的七个面，各有独立判据与独立读数 |
| **R2** | **扫描器产物落树外** —— 永不给被扫树加料 | 默认写 `%TEMP%\gbt-quickscan\`；`GBT_QUICKSCAN_OUT` 可改；**任何情况下不写被扫目录** |
| **R3** | **每轮必须给收敛判据** | 与 `baseline.json` 逐条对账，输出 `新增 / 已修 / 未变`；`--accept` 才推进基线 |
| **R4** | 声明必须机检，禁止手抄 | 技能根条数、依赖声明、计划任务目标、解释器口径**全部现扫**；本件本身不手抄任何数字 |
| **R5** | 每条结论换一把异质尺重验 | 索引尺 `git grep --cached`（读索引，不受工作区影响）· 工作区尺（全树 stat）· 忽略感知尺（Python 直走，不尊重 `.gitignore`）**三把并用** |
| **R6** | 输出必带"没扫到什么" | `blind_spots` 字段固定随报告输出，终端也打印 |

## 5. 已踩过的坑（不要让下一个人再踩）

1. **`git grep --cached` 不带 pathspec 会挂死 >120 s** —— 它会把入库的 225 MB
   `electron.exe` 从 pack 里解出来。密钥只可能住在文本里，所以**显式收敛到文本扩展名**。
   这不是降低覆盖，是去掉不可能的分母。
2. 🔴 **`git grep` 的开关必须放在 `--` 之前** —— 写成
   `git grep -E <正则> -- *.json *.py -l` 时，`-l` 被当成**路径**，git 退回按行输出，
   **报告里会把真密钥明文打出来**。本工具在 2026-09-23 初版就犯过这个错并被自查抓到。
   规矩：开关全放 `--` 前；所有匹配**一律经 `masked()` 再入报告**。
3. **"像真密钥"和"像占位符"必须在工具里分开判** —— 62 条命中里只有 1 条是真的：
   其余是 `sk-abc…`/`sk-live-abcdef…` 这类测试夹具。判据（写出来，不装神）：
   **真凭据 = 无 ≥6 字符的连续递增字母跑 且 ≥30 字符**；`private_key` 另需 base64 体 ≥200。
   **不能用"路径里有没有 test"来判** —— 真密钥恰恰躺在 `.scratch/_m4_autoclaw_backup_*/openclaw.json` 里，
   按路径剔噪会把真密钥一起剔掉。
4. **"生产面"必须是显式白名单，不能是"非垃圾即生产"** —— 初版把 `.openclaw/tmp` 的临场脚本
   算成生产代码，于是把 `PySide6`/`live2d`/`engineering_details` 误报成"活代码缺依赖"。
   改白名单后，`PySide6` 仍报缺（因为 `potato_pet/*.py` **真的**在导入它，10 个文件），
   但 `live2d`/`engineering_details` 这类噪声消失了。
5. **`_utils.py` / `_base.py` 不是残骸** —— `_*.py` 这条家规只适用于**作业临时面**的临场脚本；
   在第三方树和正规包里它是合法的私有模块命名。同理 `__init__.py` 空、`.gitkeep` 空都是约定。
6. **平面② 的 `.tmp` 不算残骸** —— `gbt_allinone/store/native_browser/profile/` 里的
   `VariationsSeedV2*.tmp` 是 Chromium 自己的缓存，属数据面。
7. **PowerShell `Get-ChildItem -Recurse` 数这棵树会少算 28%**（报 80,266，实际 111,626），
   且多目录递归查询会 120 s 超时。**一律用 Python `os.walk`/`os.scandir` 计数。**
8. **`grep` 类工具尊重 `.gitignore`** —— `gbt_allinone/store/` 被忽略时会"看不见"，
   于是同一件事在"忽略感知尺"与"直扫尺"下结论相反。**两个结论都要拿，再判。**
9. **过滤器里的"排除名单"本身就是一条待验证的假设** —— 曾把 `.backups` 当噪声剔掉，
   于是漏报了正躺在索引里的密钥。**剔噪用的尺，必须与发现用的尺不同。**
10. **最刺眼的红可能是外部配置造成的** —— 默认 `pytest` 报 0 用例/80 错误，
    给足 `GBT_STORE_DIR` + 放宽超时后 1606 全绿。**下结论前先换口径复跑一次。**

## 5.1 免二次 stat 与线程池（为什么它能进"速"字）

- 全树遍历用 `os.scandir` 递归 + `DirEntry.stat()`（一次系统调用拿全），不用 `os.walk` + `Path.stat()`。
- **跳过 `.git` 子树**（含 `_upstream/*/.git` 这类嵌套的），体量改由 `git count-objects -vH` 自报。
- 索引面的 3.8 万条 stat 走 12 线程池（NTFS 上 stat 是 I/O 密集）。
- 兄弟工作区探测有**预算上限**（默认 1500 个 `.py` 就停），否则 4 个兄弟仓合计 27 万文件会拖死。
- 实测阶段耗时（38.9 s 那轮）：`walk 6.6 · 生产面 9.1 · 装机面 7.9 · 索引面 15.2`。

## 6. 红线（不许越）

- 🔴 **只读**：不改被扫目录、不改既有文件、不需要任何授权作用域。
- 🔴 **产物必须落树外**（R2）。想留档就 `--json` 指到树外或用 `%TEMP%`。
- 🔴 **不做有后果的动作**：不 deploy / 不 release / 不 shape / 不 rehearse / 不装包 / 不发网络请求。
- 🔴 **不代替授权门**：本件只**报**要过哪道门；真动生产必须走 `run_task` + 主人在终端发授权。
- 🔴 **不手抄数字**（R4）：报告里每个数都要能从 JSON 复算出来。
- 🔴 **署名**：本规程与工具的输出必须保留「开发者：自由的风」。

## 7. 未验账（诚实边界，这段不许删）

1. **只 stat 全树，只读生产面内容**：平面②③④的内容不做逐文件解析
   （4 万+ 文件的第三方/残骸内容逐读 = 违背"速"字）。
2. **重复检测分两把尺**：大文件"同名同体积"（全树、免哈希，抓 `electron.exe` 那类）·
   精确重复**仅限生产面**。跨全树的逐字节查重**没做**。
3. **没做**：动态导入追踪 / 密钥有效性验证（只判形状，不判是否还有效）/
   二进制格式校验 / 权限位 / 提交历史逐笔审计 / 符号链接目标 / `.git` 内部对象逐字节。
4. **F 面口径**：框架门以**隔离 store** 计，与生产 store 读数**不同口径**；
   `selfscan` 在隔离 store 下必报 `P0`（数据态），本件照报不豁免 ——
   **豁免决定由人做，不由扫描器替人做**。
5. **`--with-gates` 会慢**（实测 60–240 s 量级，取决于各门）。
6. **收敛判据依赖基线**：没跑过 `--accept` 就没有 `新增/已修` 读数，
   此时只报绝对故障数（不是"没变化"）。**换开关要重新 `--accept`**，否则会打 `不可比`。
7. **S 面是启发式，不是杀毒引擎**：IOC 命中只说明"这段代码长得像那些手法"，
   **不等于恶意**；一律只报不判。真正的特征库比对只有 `--av-scan`（Defender）才有。
8. **S 面拿不到的层标 `unavailable`，绝不用空结果冒充"干净"**：
   反病毒读不到 / hosts 读不到 / 链接表读不到（普通权限常见）都如实标出。
   **`unavailable` ≠ `clean`** —— 这是本面存在的第一理由。
9. **`--av-scan` 默认不跑**，且跑时必须 `-DisableRemediation`（只报不动手）。
   理由有实证：本机 Defender 历史检出里那 1 条，**就是它把本框架自己的 `pwsh` 自动化判成了威胁**
   （`ThreatID 2147941383`）。自动触发处置有可能把你自己的工具当场隔离掉。
10. **自动进化层不写代码**：它把"该进化什么"算准（`--discover`）、把"已覆盖"证伪（`--selftest`）、
    把每轮读数留痕（`ledger.jsonl`），**但不动判据、不改自身**。
    一个会自我改写的扫描器无法被审计 —— 这条边界是设计，不是没做完。
11. **`--selftest` 只覆盖"能用夹具复现"的判据**：环境类的（反病毒是否被排除、远控自启、
    依赖缺失）没法种假故障，只做正对照记录。**别把自检全绿读成"所有判据都验过"。**
7. 🔴 **新装的技能在本会话内不可见** —— 技能目录是**会话启动时快照**的。
   本规程已同步进 `<repo>/.dsh/skills` 与 `~/.agents/skills`（本会话真读的两个根，
   四处 sha256 一致），但 `skill gbt-quickscan` 在当前会话仍报 unknown，
   **必须下次会话才认**。想当场确认，用文件哈希比对，而不是调 `skill`。
8. **"未入库"是一条通用判据，不是 `plugins/` 专属** —— 初版只查了 `plugins/`，
   漏掉 `skills/`（59 条规程）、`tools/codex-scripts/`、`.dsh/`、`archive/`、`delivery/`、
   `projects/` 同样整棵未跟踪。现泛化成"生产面每个顶层的入库比例"：
   **凡 ≥20 个文件且入库 0 个 ⇒ 报 `PROD_TOPS_UNTRACKED`（P0）**。
9. **`.cmd` 启动器里一个非 ASCII 字节都不能有** —— cmd.exe 按控制台代码页（本机 GBK/936）
   解析批处理；`rem` 行里的中文会被误解码、**把后半句当命令执行**。
   实测两次：退出码 3 + `'<乱码>' is not recognized`。规矩：**批处理保持 7-bit ASCII，
   中文文档放 SKILL.md**；写完必须**逐字节验证**（`非 ASCII 字节 == 0`）。
10. **只 reconfigure stdout 不够，还得切控制台代码页** —— GBK 控制台下直接 `print` 中文会
    `UnicodeEncodeError` 崩掉；只把 stdout 设成 utf-8 又会让中文以 UTF-8 写出、控制台按 GBK 解
    ⇒ **乱码**（实测路径显示成 `GBTС����V8`）。正确做法：
    `SetConsoleOutputCP(65001)` + `SetConsoleCP(65001)`，再 `reconfigure(encoding="utf-8")`。
    （同一条教训在 `tools/codex-scripts/five-dim.py` 第 23–30 行已记过一次。）
11. **`urllib` 请求 `127.0.0.1` 也会走代理** —— 本机有 `http_proxy` 环境变量时，
    取宿主 `/gbt-master` 会 `TimeoutError`。要显式装一个空代理 opener：
    `urllib.request.build_opener(urllib.request.ProxyHandler({}))`。
12. **家规说该缺席的模块，别报成断链** —— `..bridge` / `wallet` / `ledger` 这类资金模块
    按家规第 10 条**本就该在框架里缺席**（已移出家 Workspace）。把它们算成"相对导入断链"
    就是**把设计当故障**。工具里用 `KNOWN_ABSENT` 白名单分开报，不进故障清单。
13. **基线与开关必须配套** —— `--accept` 存基线时要连开关集一起存；换开关复跑必须打
    **`不可比`**，否则每次加开关都会假报一堆"新增故障"（本仓家规：跨口径打 `not_comparable`）。
14. **自己的工具也会漏，而且漏的方式和你批评别人时一模一样** —— 本工具第一版只查了
    `plugins/` 未入库、只把 16 条故障焊进判据，于是"我要全维度"这句声明与实现脱钩。
    **规矩：每次说"全维度/全覆盖"之前，先把「哪些病因还没进判据」列出来点清。**
    —— 这条现在由 `--discover` 自动执行，不再靠自觉。
15. **含盘符路径的 docstring 必须用 `r"""`** —— `C:\Users\...` 里的 `\U` 会被当成
    Unicode 转义 ⇒ `SyntaxError: truncated \UXXXXXXXX escape`。
    **本目标轮我自己的 `quickscan_security.py` 就犯了这个错**，而它正是本工具在扫的那一类缺陷。
16. **`write_text` 在 Windows 上会把 `\n` 翻成 `\r\n`** —— 负对照夹具用 `write_text` 写
    `"a\r\nb\n"` 会被抹平成全 CRLF，于是 `MIXED_EOL` "没响"。
    **那不是判据死了，是夹具造错了。夹具必须 `write_bytes(...encode("utf-8"))`。**
    负对照的价值恰恰在于它能区分这两种可能。
17. **`str.strip()` 不会去掉 `\ufeff`** —— hosts 首行是 `\ufeff# Copyright ...`，
    于是一条注释被当成"非默认映射"报成 `HOSTS_TAMPERED`。用 `utf-8-sig` 读或显式 `lstrip("\ufeff")`。
18. **Windows 自带件要进白名单** —— WMI 的 `SCM Event Log Filter`、`BVTFilter` 是系统内置，
    不白名单就会把每个正常 Windows 报成"WMI 持久化"。
19. **`Path.relative_to(ROOT)` 对仓外文件会抛异常** —— 负对照的夹具树在 `%TEMP%` 下，
    一调就 `ValueError`。**判断路径是否在仓内要封装安全版**（`_rel()` 退回绝对路径）。
20. **别把"从未响过"直接读成"判据死了"** —— 判据分三种：**命中过** / **休眠（自检证实会响）** /
    **可疑（未命中且未验证）**。只有第三种需要处置。混为一谈会让人误删好判据。

## 8. 门（要过哪道门）

| 动作 | 作用域 |
|---|---|
| 跑本件（默认，不含 `--with-gates`） | **无需任何授权**（只读、无参、静态查出 `scopes=()`） |
| 跑本件 `--with-gates` | 仍无需授权：只挑 `safe` 且 `policy.evaluate` 无作用域且不在 `PROBE_SKIP_KINDS` 的门 |
| 按本件的结论去**修** | **看修什么**：清索引 / 改自启 / 装包 / 动技能根 —— 全部**有后果**，须主人点头 |
| 动生产/镜像 | 走 `run_task` + `deploy_publish` 等作用域，**授权只能主人在终端发** |

## 9. 出处（现读证据）

| 什么 | 在哪 |
|---|---|
| 工具本体 | `<仓>/tools/codex-scripts/quick_scan.py` |
| 固化来源（第 1 轮全树穿透扫描报告） | `<仓>/.scratch/scan-20260923/SCAN-REPORT.md` |
| 固化来源（蒸馏与六条硬规则） | `<仓>/.scratch/scan-20260923/DISTILL-2026-09-23.md` |
| 深扫器（内容面全量，慢） | `<仓>/.scratch/scan-20260923/deep_scan.py` |
| 万能插最大档执行器 | `<仓>/.scratch/scan-20260923/omni_max.py` |
| 平面①的既有扫描器（异质尺） | 万能插 `cross_scan`（`gbt_allinone/cross_scan.py`） |
| 安全面模块（本目标轮新增） | `<仓>/tools/codex-scripts/quickscan_security.py` |
| 进化层模块（本目标轮新增） | `<仓>/tools/codex-scripts/quickscan_evolve.py` |
| 病因总目录（声明式，本目标轮新增） | `<仓>/tools/codex-scripts/quickscan_causes.json` |
| 主机六层（安全面**复用**，不重造） | `<仓>/gbt_allinone/tools/host_security_scan.py` |
| 产物（树外） | `%TEMP%\gbt-quickscan\latest.json` · `baseline.json` · `ledger.jsonl` · `selftest.json` |

---

## 10. 自动进化 + 病毒木马扫描（2026-09-23 目标轮新增）

### 10.1 三个能力的边界（**先说清它不能做什么**）

| 能力 | 做什么 | **不做什么** |
|---|---|---|
| **自动收集** | 每轮往 `ledger.jsonl` 追一条（时刻/开关/分数/判据码集）；`--trend` 出**首见/末见/次数/常驻/闪断** | 不联网、不上报、不外传 |
| **自动进化** | 用 `quickscan_causes.json` 病因总目录与实现做差集 ⇒ **自动算出"该进化什么"**；`--selftest` 用负对照**证伪**"已覆盖" | **不自己写代码、不自己改判据**。它把"该进化什么"算准，**动手仍由人决定** —— 一个会自我改写的扫描器无法被审计 |
| **病毒木马扫描** | 反病毒**可见性**（排除项遮蔽）· 持久化与**远控自启** · 内容 IOC 19 条 · npm 供应链 · hosts/代理 · **扩展名伪装**（读文件头）·（可选）Defender 真扫 ·（可选）主机六层 L3-L5 | **不做**：全盘哈希比对病毒库（不用外部库）· 实时行为监控 · 内核 rootkit · 内存注入 · 已删除痕迹。IOC 是**启发式**：命中只说明「长得像」，**只报不判** |

### 10.2 三条命令怎么配合（这就是"不会像瞎子一样"的操作法）

```powershell
# ① 每轮跑完，台账自动记一条 ——「到底有没有变好」不靠记忆
& "C:\Users\ADMIN\Desktop\GBT小土豆V8\quick-scan.cmd"
& "C:\Users\ADMIN\Desktop\GBT小土豆V8\quick-scan.cmd" --trend     # 常驻病 vs 闪断

# ② 想扩大覆盖时，先问系统「我该进化什么」，而不是凭感觉加检查
& "C:\Users\ADMIN\Desktop\GBT小土豆V8\quick-scan.cmd" --discover

# ③ 每加一条判据，必须过负对照；没过不许写进"已覆盖"
& "C:\Users\ADMIN\Desktop\GBT小土豆V8\quick-scan.cmd" --selftest
```

### 10.3 判据死活三分（`--discover` 的口径）

| 分类 | 含义 | 该怎么办 |
|---|---|---|
| **todo**（待进化） | 目录已登记、判据还没实现 | 下一轮该做的。**现读 10 条，每条都写了"怎么做"** |
| **dormant**（休眠） | 从未响过，但**自检证实会响** | 正常 —— 当前树没这毛病，**不是判据死了** |
| **suspect**（可疑） | 从未响过且没被自检验过 | 跑 `--selftest`；仍不响就从"已覆盖"里划掉 |
| **unregistered** | 引擎报了但目录没登记 | 把目录补上，**别让目录落后于实现** |

### 10.4 一条判据的完整生命周期

```
① 发现病因（人工 / 深扫 / 别人报）
      ↓ 写进 quickscan_causes.json，implemented=false
② --discover 把它列进「待进化」
      ↓ 写判据代码 + 在目录里置 implemented=true
③ --selftest 种一条假故障，验证这条判据**真的会响**
      ↓ 响了 → 进 verified_rules；不响 → 死判据，回炉
④ 每轮把命中它的判据写进 ledger.jsonl
      ↓ --trend 给出首见时刻（这条病第一次出现在什么时候）
⑤ 修掉后它从结果里消失，--discover 归入 dormant（休眠），**不是删除**
```

**这条链是闭的**：目录 → 判据 → 负对照 → 台账 → 对账。
少任何一环，"全维度覆盖"就退回成一句无法证伪的口号。

### 10.5 本目标轮已销账的进化（带证据）

| 病因 | 从哪来 | 现在的判据 | 现读 |
|---|---|---|---|
| `EXT_MISMATCH_PE` | 新增 | 读文件头判 PE/ELF/ZIP 与后缀是否相符 | 已实现，未命中（休眠） |
| `AV_ONDEMAND_SCAN` / `AV_ONDEMAND_THREAT` | 新增 | `--av-scan` 调 MpCmdRun（`-DisableRemediation` 只报不动手） | 已实现，需显式开启 |
| `PROC_UNSIGNED` · `PORT_UNUSUAL_LISTEN` · `EXEC_IN_SUSPICIOUS_DIR` · `NET_EGRESS_UNKNOWN` | **复用** `host_security_scan` L3-L5 | `--with-host` 把它的输出变成判据 | **已命中**：非典型端口监听 · 外连待核 · TEMP/AppData 可执行 |

⇒ `--discover` 的「待进化」**从 16 降到 10**。剩下 10 条：`DUP_EXACT_CONTENT` ·
`WORKSPACE_UNSIGNED_BIN` · `DNS_SERVER_ODD` · `BROWSER_EXTENSION_INVENTORY` ·
`CERT_STORE_UNKNOWN_ROOT` · `TASK_SYSTEM_WRITABLE_SCRIPT` · `MTIME_ANOMALY` ·
`CONFIG_PRECEDENCE_SHADOW` · `EVIDENCE_STAMP_MISSING` · `SKILL_DECLARED_NOT_LOADABLE`。

### 10.6 安全面的现读结论（2026-09-23，必须原文照读）

- 🔴 **`AV_EXCLUSION_BLINDSPOT`（P0）**：Defender 全程在位（`RealTimeProtection=True`、
  篡改保护开、特征库 1.459.335.0），但 **`C:\Users\ADMIN` 整条在排除项里** ⇒
  **本工作区不在实时防护视野内**。仓内 `host_security_scan.py` 的 L1 只读
  `Get-MpComputerStatus`（在位），**从不读 `Get-MpPreference -ExclusionPath`（在不在看你）** ——
  「在位」与「在看你」是两件事，只报前者就是假的覆盖感。
- 🔴 **`PERSIST_REMOTE_CONTROL`（P1）**：开机自启里有 **TightVNC（`tvncontrol`）+ AweSun/向日葵** ——
  这台机器长期可被外部接管。**不是病毒判定，是暴露面判定**。
- 🟠 **`AV_DETECTION_HISTORY`**：历史 1 条检出 `ThreatID 2147941383`，**是 Defender 把本框架自己的
  `pwsh` 自动化判成了威胁** —— 这也是 `--av-scan` 默认不跑、且必须 `-DisableRemediation` 的理由。
- 🟡 `AV_NEVER_FULL_SCAN`（从未全盘）· `PERSIST_USER_WRITABLE` ×4 · `PERSIST_STARTUP_FILE` ×5。
