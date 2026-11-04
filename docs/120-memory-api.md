# 120 · /api/memory：recall / write（同步层 chain+version）/ subscribe

日期：2026-11-02 · 状态：**三 op 实测通过** · 服务：`http://127.0.0.1:8766`

## 一句话
8766 现在有记忆接口了：**write 走同步层拿 version + 哈希链**，**recall 查统一索引给 hits + 覆盖率**，
**subscribe 用 SSE 广播写入**。中文子串（>=3 字）靠 **trigram** 索引，2 字仍靠拆词 LIKE（如实口径）。

## 为什么上次"挂住"
不是接口问题：
1. 这台机器**没有真 Python**（只有 Microsoft Store 的 `python.exe` 占位符，exit 9009）；
2. 用 `Start-Process` 起隐藏窗口时调用方被拖住 ⇒ 本轮改用仓库里已有的
   `gbt_allinone/console_service.py start`（`Popen` + `DETACHED_PROCESS|CREATE_NO_WINDOW`，
   `stdout/stderr=DEVNULL`，1 秒内返回 pid），**不阻塞 pwsh**。
3. 顺手补了嵌入式解释器：`pyembed/python.exe`（Python 3.13.9 embeddable，含 sqlite 3.50.4 + FTS5）。
   这正好对上 `console_service._python()` 的首选路径 `ROOT/pyembed/python.exe`。

## 复核抓到两个真问题（2026-11-02 05:28–05:33，收到实测输出后抓的）

**① 双开抢端口（比"挂住"更严重）**
现象：`console_service start` 报 `already:false` 并起了新 pid，但 `netstat` 显示 **2784 和 3560 同时在听 8766**。
根因：健康检查只探 `/api/state`，冷缓存建数据 >0.9s ⇒ **假阴性**；Windows 的 `SO_REUSEADDR` 允许第二个进程**真绑上**同一端口 ⇒ 两个 server 抢请求，**订阅者收不到另一个进程的广播**（SSE 订阅是进程内内存态）。
修：
- 服务端加轻量 `/api/ping`（不建数据），`console_service.ping` 先探它（2s），通了再取 `/api/state`（8s，取不到就留空不编）；
- Windows 上 `allow_reuse_address = False`（宁可 bind 失败也不双开）；
- `start` 先看谁在听端口：有人听但 ping 不通 ⇒ 报"僵死/旧进程，不双开"+ `stale_pids`，不硬起；
- `start` 的 already 分支把 **真 pid** 写进状态文件（原来写 0，导致 `stop` 报"状态文件里没有 pid"）；
- `stop` 先验命令行含 `console-server.py` 才杀（按状态文件的端口，不误杀正式端口的进程）；
- 回归测试：`tests/test_console_service.py` 加 [2b]（连 start 两次 already=true、只有一个监听 pid、ping pid==监听 pid、状态文件 pid≠0）；
- 同类假阴性一并修：`tools/install-autostart.py` 的 `probe()` 原来也只探 `/api/state`（1.2s），现改为先探 `/api/ping` 再退回（实测 status 从"服务在线: False"变 True）。

**② 投影游标竞态（索引漂移）**
现象：并发压测后 `sync_total=346` 但 `index_memory_sync=344` —— 漏了 2 条，且**永远补不回来**。
根因：`index_into_unify` 先 `select rows > cursor`、再`select max(version)` 当新游标；两次查询之间别的写提交 ⇒ 游标被推过那条，漏投。
修：游标 = **实际投到的最后一条 version**（不是全局 head）；`ATTACH` 统一库到链库连接，一个 `BEGIN IMMEDIATE` 内"取增量→投→对账→推游标→COMMIT"（DELETE journal 下多库事务原子）；对账用不变量 **统一库条数 == 游标**（O(1) 次扫描而不是逐条 NOT EXISTS），不等就从 0 对齐重投；对账仍不平则 `ok:false` 并说明（不假绿）。
效果：64 并发写压测后 `sync_total == index == 558`，且压测吞吐从 9.2 rps 回到 16–46 rps（快慢主要看磁盘 fsync，两个库各一次提交）。

**③ 重复文本占满召回窗口（不是检索坏了）**
现象：同一句测试文本写了 8 次后，`coverage` 从 0.857 掉到 0.571 —— 前 5 条 hits 全是同一句话，`哈希链/漂移` 两个词没进命中集。
修：`recall` 对正文归一化去重（保留排名靠前那条），返回 `dedup.before/after` 如实记账。不删链（链只追加），也不为了数字改检索。

## 接口契约
| 方法 | 路径 | 参数 | 返回 |
|---|---|---|---|
| GET | `/api/memory` | `op=recall&q=...&k=10[&include_test=1]` | `total/by_src/hits/coverage{terms,matched,rate,matched_terms,hits}/index/fts/ms` |
| GET | `/api/memory` | `op=subscribe`（SSE） | 先 `event: hello`（当前 version/h），之后每条写入 `event: write` |
| GET | `/api/memory` | `op=stats` | 同步层 version/count/by_src + 统一索引 total/trigram 行数 |
| GET | `/api/memory` | `op=verify` | 只读验链：`ok/checked/head`；断链回 409 + `broken_at/reason` |
| POST | `/api/memory` | `{"op":"write","text":"...","src":"console","name":"console-web","role":"user","tag":"real"}` | `version/h/prev/chain/chain_len/ref/indexed`（支持 `entries: [...]` 批量，单次 <=50） |

## 同步层（`gbt_allinone/tools/memory_sync.py`）
- 库：`gbt_allinone/store/memory_sync/chain.sqlite3`；表 `writes(version PK, h, prev, at, src, name, role, tag, text)`；
- `version`：**单调 +1**（BEGIN IMMEDIATE + 进程内锁 ⇒ 并发写不重号）；
- `h = sha1(canonical(version,at,src,name,role,tag,text))`，`prev` 指向上一条 h；
- 写完**投影**进 `tools/memory_unify.py` 的统一索引（`src=memory_sync`、`ref=memchain#version=N`），
  只追加、不碰原库；投影串行（`_PROJ_LOCK`）避免并发写统一库互相锁死；
- `verify()` 只读重算：版本连续 + prev 接得上 + h 一致。

## 中文索引（`tools/memory_unify.py`）
新增 `mem_fts_tri`（`fts5(tokenize='trigram')`）：**>=3 字**的中文词可按**子串**命中；
2 字仍走原来的「按 2 字滑窗 + LIKE」兜底 —— 不假装 2 字可子串搜。老行首次 recall 时自动回填（幂等）。

## 实测数字（2026-11-02 05:23，本机）
- 服务：pid 20504，`127.0.0.1:8766` 单实例监听（`netstat` 只有 1 个 pid），`/api/ping` 秒回 pid，`/api/state` → caps 385 / skills 23；
- **write**：version 1→558 连续；#493 `h=ec74d5a2…`；`chain_len == version`，`prev` 逐条接上；
- **recall**：`q="记忆统一层 哈希链 漂移"` → hits 5、`by_src={memory_sync:5}`、`coverage 6/7=0.857`、9–34 ms；
- **subscribe**：hello 带当前 version → 另一次 write 的 `event: write` **1 s 内收到**；
- **trigram**：3 字子串「试会话」：unicode61 **0** 命中、trigram 有命中、接口 recall 去重后 **2** 条（coverage 1.0）；fts 行数 494/494；
- **漂移压测**（558 条链上跑）：8 线程 × 8 写 = 64 条，1.4–3.9 s（16–46 rps，取决于磁盘 fsync），**重号 0 / 断号 0 / 链断 0**，
  同步层 558 条 == 统一索引 558 条（unicode61 558 / trigram 558），压测后 recall 50 命中（coverage 1.0）；
- **检测器自证**：把链库**副本**改一个字 → verify 红（`broken_at=558, h 重算不一致`），原库仍绿（checked 558）。

## 测试（可复跑）
```powershell
.\pyembed\python.exe -X utf8 tests\test_memory_api.py --port 8766        # recall/write/subscribe
.\pyembed\python.exe -X utf8 tests\test_memory_trigram.py --port 8766    # 中文 trigram
.\pyembed\python.exe -X utf8 tests\stress_memory_drift.py --port 8766    # 并发 + 漂移 + 篡改自证
.\pyembed\python.exe -X utf8 tests\test_console_service.py              # 启停/防双开回归（含 18766 隔离端口）
```

## 登录自启（2026-11-02 装好并实测）

安装位置：`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\GBT-console.cmd`
（`.pyembedpython.exe toolsinstall-autostart.py --install`；删掉该文件即取消）

包装器做什么（渲染自 `tools/install-autostart.py` 的 `render()`）：
```bat
@echo off
chcp 65001 >nul
rem GBT小土豆V8 · 认知界面服务 :8766 登录自启（删掉本文件即取消）
cd /d "<仓库绝对路径>"
"<仓库>\pyembed\python.exe" -X utf8 "gbt_allinone\console_service.py" start >> "<仓库>\state\console-server.log" 2>&1
```
为什么走 `console_service.py start` 而不是直接起 `console-server.py`：
- **幂等**：服务已在跑就 `already=true` 退出 ⇒ 不双开、不多一个进程；
- **状态文件写真 pid** ⇒ `status`/`stop` 有依据（实测 status.last.pid=3700 / waited_ms=832）；
- 服务进程由 `CREATE_NO_WINDOW` 拉起 ⇒ 任务栏不挂一个最小化控制台；
- 输出落 `state/console-server.log` ⇒ 起不来时看得见原因，不静默失败；
- 文件是 UTF-8（路径含中文）⇒ 首行 `chcp 65001` 兜底非 UTF-8 代码页的机器。

实测（05:37–05:38）：
- 模拟登录：`Push-Location $env:USERPROFILE` 后跑包装器（不是仓库 cwd）→ **1 s 内 /api/ping 通**，pid 3700；
- 已在线时再跑一次包装器 → 监听仍只有 1 个 pid（3700），**不双开**；
- `console_service.py status` → `up:true / last.pid:3700`；`tests/test_console_service.py`（含 18766 真起真停 + 双开回归）ALL OK。

## 纪律
- 链是**只追加**的：测试写进去的 74 条（含 64 条压测）**不删** —— 删了就断链，等于把"可验"砍掉；
  要区分来源看 `src` / `name`（`console` / `stress` / `trigram-test`）；
- subscribe 的订阅者只在内存里，服务重启即断（SSE 断开是事实，不补历史重放；重连拿 hello 的 version 续上）。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
