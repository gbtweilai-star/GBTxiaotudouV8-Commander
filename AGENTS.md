# AGENTS.md · GBT小土豆V8 便携版 —— 给接手这个仓的 AI 的作业须知

> 本文件是**入口**。真源是 `PROJECT_BLUEPRINT.md`（进度/依赖/风险，162 KB 全量蓝图）。
> 两者冲突时以 `PROJECT_BLUEPRINT.md` + 代码为准，本文只写「上手就要知道的硬口径」。

## 1. 这是什么

GBT小土豆V8 是一个**协议式认知体**：`gbt_allinone/` 里约 426 个**能力位**（capability slot），
每个位有独立的 `run(op=..., **kw)` 契约，由一个统一的 `api.run_task(cap, params)` 分派。
外层是 `holo_pet_w3/` 的界面 + `state/` 的数据。整个目录拷走即可迁移。

**不要**把这里当普通 Python 项目改：能力位是契约，动一处会连带动到别人。

## 2. 三条硬口径（违反即回归）

### 2.1 失败三态，不是「成功/失败」两种

| 状态 | 含义 | 谁的问题 |
|---|---|---|
| `denied` | 缺票，会点名 `missing_scopes` | 授权 |
| `needs_dependency` / `needs_input` | 缺依赖 / 缺参数，带原因 | 环境或调用方 |
| `failed` | 真失败，回执带上游原话 | 代码 |

**不许**把「缺参数」包装成 `failed`，**不许**把「上游没给」写成假成功。

### 2.2 信封 `status=ok` ≠ 本体 `ok=true`

`api.run_task()` 返回的是信封：

```python
{"ok": True, "status": "ok", "kind": "<cap>", "result": {...}, "error": None}
```

**信封 ok 只说明「分派成功」**，本体可能在里面说 `ok: false`。
读结果必须往下钻一层（有时是两层：`result.result`）。

### 2.3 钢印文件不许删

文件头带 `# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除` 的，一律不动。

## 2.4 三条默认（**不用提醒，每次自动**）

> 主人令 2026-11-04：「把这三个调用设置成默认使用，别一直要我提醒你自己什么水平心里没点逼数吗？」

这三条不是「建议」，是**做完的判据**。少一条就等于没做完。

| 默认 | 什么时候必须自动跑 | 不跑会怎样 |
|---|---|---|
| **万能插 `omni_plug`** | 要碰触手以外的任何东西（文件 / 进程 / HTTP / 端口 / 页面 / GUI）**之前** | 自己写 `subprocess` / `urllib` / 裸 `open` 去干，等于绕开插座与作用域门 |
| **多域监控 `impact_check`** | 改任何 `.py` / 配置 / 图的**之前**，以及万能插**每次动作之后** | 不知道会撞到谁就动手 = 拿运气换进度；`op=recent` 会告诉你这一动影响了多少个节点 |
| **原子替换** | 写任何**别处会读**的文件（`wiring.json` / 索引 / 图 / 台账 / 指针） | `write_text` 直接覆盖：崩一次留坏档；且「旧权重配新边」**不报错**，只是悄悄算偏 |

### 原子替换的唯一写法

```python
tmp = path.with_name("%s.tmp-%d" % (path.name, os.getpid()))
with open(tmp, "w", encoding="utf-8", newline="") as fh:
    fh.write(text)
    fh.flush()
    os.fsync(fh.fileno())      # 先落盘
os.replace(tmp, path)          # 同卷原子
```

**而且必须**：写前校验内容、写后读回校验。

> 血账：`np.savez_compressed(rows=None)` **不报错**，它把 150 KB 的好图
> 替换成一个 323 字节的壳，`os.replace` 照样执行 ——
> 原子性只保证「要么旧的、要么新的」，**保证不了「新的有意义」**。

多文件产物还有顺序要求：**先数据、后标记**（图先写，`meta.json` 最后写），
于是「meta 存在 ⇒ 全部就绪」成立，中途崩只会留下旧 meta 触发自动重建。

### 一条命令验这三条

```powershell
.\pyembed\python.exe tools\codex-scripts\guard-three.py
```

现在这道闸有 **5 项**：万能插 / 多域监控 / 原子替换 / 探测超时 / **运行时**。

最后那项是 2026-11-06 加的牙，专治本文档 §3.1 坑 C 那类事故：它当场回答
「跑的是不是仓内 pyembed」「采集三路（dxcam/mss/pyautogui）齐不齐」「真能不能出一帧」。
口径：跑错解释器 = **fail**（用错工具，不是缺件）；仓内没有 pyembed = `needs_dependency`
（开发仓本来就不携带运行时，不许因此恒红）。

## 3. 路径规则（2026-11-04 全仓整治后）

**禁止**写死 `C:\Users\<某个人>\...`。本机曾散落 146 处指向不存在用户的路径，全部失效。

| 要什么 | 怎么写 |
|---|---|
| 包内某文件 | `ROOT = Path(__file__).resolve().parents[N]`（N = 该文件到 `payload/` 的层数） |
| 用户家目录下的东西 | `Path.home() / "..."` |
| 找外部程序（如 ComfyUI） | 先看环境变量，再 `Path.home()`，再包内；**都找不到就如实说找不到**，不要编路径 |

`tools/codex-scripts/fix-admin-paths.py` 是配套的修路器（支持干跑 / `--apply`）。

## 3.1 两个「OpenCV + 中文路径 + PowerShell 编码」的坑（已踩过两次）

### 坑 A · OpenCV 对非 ASCII 路径会**静默失败**

本仓路径含「GBT小土豆V8桌面版」。在 Windows 上：

| 调用 | 行为 |
|---|---|
| `cv2.imwrite(str(p), img)` | **返回 False，不抛异常** → 以为写好了，其实盘上没有 |
| `cv2.imread(str(p))` | **返回 None** → 以为图坏了，其实图是好的 |

**正确写法**：

```python
# 写：编码走内存，写盘走 Python
ok, buf = cv2.imencode(".png", frame)
p.write_bytes(buf.tobytes())

# 读：PIL 走 Python 文件句柄，不吃字符集这一套
from PIL import Image
img = np.asarray(Image.open(str(p)).convert("RGB"))[:, :, ::-1].copy()   # RGB → BGR
```

### 坑 B · `.ps1` 必须存成 **UTF-8 带 BOM**

PowerShell 5.1 读**无 BOM 的 UTF-8** 会按系统 ANSI(GBK) 解码：
中文变乱码，还可能吃掉字符串的结束引号，报 `The string is missing the terminator`。

```python
# 写 .ps1 一律用 utf-8-sig
Path("x.ps1").write_text(src, encoding="utf-8-sig")
```

同理，读仓里的 UTF-8 文本文件时，PowerShell 侧要显式 `Get-Content -Encoding UTF8`，
否则 `Select-String` 出来的都是乱码。

### 坑 C · `pyembed` 是 **embeddable 包**，`-m` 与 `PYTHONPATH` 都失效

`pyembed/` 根下有个 `python312._pth`（内容就三行：`python312.zip` / `.` / `Lib\site-packages`）。
**只要 `._pth` 存在，解释器就进 isolated 模式**：

| 做法 | 结果 |
|---|---|
| `.\pyembed\python.exe -m unittest ...` | ❌ `No module named 'gbt_allinone'` —— cwd 不进 `sys.path` |
| 设 `$env:PYTHONPATH` | ❌ **被整个忽略**，报错一字不差（实测过，别浪费时间） |
| `.\pyembed\python.exe xxx.py` | ✅ 但要脚本自己 `sys.path.insert(0, os.getcwd())`（`sys.path[0]` 是**脚本目录**，不是 cwd） |
| `.\pyembed\python.exe -c "..."` | ✅ 但 PowerShell 会吃掉内容里的双引号 → `SyntaxError` |

所以跑测试一律用壳：`.\pyembed\python.exe tools\codex-scripts\run-tests.py <模块名> ...`

> `._pth` 里全是相对路径，因此整个 `pyembed/` 可以整包搬走。
> 2026-11-05 就是这么把它从 `Documents\deepseek-harness\...\pyembed` 搬到本仓根下的
> （1568 文件 / 84.3 MB / Python 3.12.10），搬完 `mss` / `uiautomation` / `pyautogui` /
> `numpy` / `PIL` 全都在 —— **屏幕采集靠的就是这几个，别拿系统别的 Python 去跑本仓**。


### 坑 D · `grep` / `readFile` 的输出经过转义，判断不了源码的引号结构

`grepContent` 与 `readFile` 的文本结果都可能带 JSON 转义 —— 你在屏幕上看到的反斜杠数量
**和源码里不一样**：

| 屏幕上看到 | 源码里其实是 |
|---|---|
| `\"` | 一个 `"` |
| `\\\"` | `\"`（反斜杠 + 引号） |
| `\\n` | `\n`（反斜杠 + 字母 n，不是换行） |

于是「这个 `"` 是字符串的边界，还是字符串内部的一个转义引号」—— 这件事在屏幕上**看不出来**。

**血账（2026-11-05）**：改 `impact_check` 里「两种口径」的说明文字，把新句子和旧文本残片
拼在了一起 —— `逐字对齐"` 提前闭合了字符串、`"强边"` 这个 key 直接丢了。`grep` 看了、
`readFile` 也看了，屏幕上一切正常；文件其实 `SyntaxError`，**整个能力位 import 不了**，
而且一整天没人发现（后来是靠 `ast.parse` 逮出来的）。

**判据**：凡**动过源码里的字符串或注释文本**，收尾一律

```python
import ast, io
ast.parse(io.open(p, encoding="utf-8").read(), filename=p)   # 一秒钟指到行号
```

`ast` 会精确指出第几行、哪个 token 出问题；`grep` 会安静地骗你。
（本仓现成的机器判据：`gbt_allinone/tests/test_diag_kou_jing.py`。）

**配套**：PowerShell 下 `python -c "..."` 的双引号会被吃掉（见坑 C），
要验这类东西一律用 here-string 走 stdin：

```powershell
@'
import ast, io
ast.parse(io.open("x.py", encoding="utf-8").read(), filename="x.py")
print("OK")
'@ | .\pyembed\python.exe -
```

## 4. 怎么调能力位

```powershell
# 统一入口
.\pyembed\python.exe -c "import sys;sys.path.insert(0,'.');from gbt_allinone import api;print(api.run_task('look_grade',{'op':'list'}))"

# 五维台（人读用）
.\pyembed\python.exe tools\codex-scripts\five-dim.py cap look_grade '{"op":"list"}'
```

常用位速查：

| 位 | 干什么 |
|---|---|
| `impact_check` | **多域监控**＝影响面检查（改 X 会连带动到谁），读 `state/model-pack/wiring.json` |
| `tentacle_cognition` | 触手认知包（五件 + 三问 + 五红线）。**`op=standards` 取工程规范**：8 工序 / 9 不变量 / 10 步证据阶梯 / 28 章宪章 / 5 红线 / AGENTS 三条硬口径 / docs 律系列，**按 `scene` 挑**（不给就 verify）。实现在 `gbt_allinone/tools/standards_pack.py`；**触手启动时已由 `tentacle/bridge.build_cognition()` 自动带上**，不用手动调 |
| `omni_plug` | 万能插：`op=universal` 现场认接口生成适配器；**「全开」是 `op=surface_audit` + `op=full_sweep` + `op=discover`**（**没有 `op=all`** —— 曾写错在这里，照它调会得到 `不认的 op：all`） |
| `body_eye` / `body_see` | 看**屏幕**（截屏 → 理解 → 回坐标） |
| `vision_loop` | 眼→耳→嘴→手原生闭环（`look/hear/speak/think/act/verify/loop`） |
| `look_grade` | 外观库（调色），实现在 `tools/filmgrade.py` |
| `bounty_ops` | 安全众测闭环门面（自带 op 级门禁） |

## 4.1 新增能力位：三道门，少一道就等于没建

这是本仓最容易漏的一步，2026-11-04 实测踩过：

| 门 | 做什么 | 漏了会怎样 |
|---|---|---|
| ① desc 里写「常用说法：A / B / C。」 | `extract_intents.py` 用正则从 desc 抽触发词 | 索引里查不到这个位，只有 L2 统计去猜 |
| ② 手工加进 `router.py` 的 `INTENT_MAP` | L1 规则层（人工策展） | 同样只能靠统计碰 |
| ③ **跑 `extract_intents.py` 重建 `intent_extracted.json`** | `router.load_caps()` 读的是**这个索引**，不是注册表 | **①②都做了也命中 0** —— 索引里根本没这个位 |

**血账（2026-11-04 · see_camera）**：①②都做完后实测仍是 `L1 规则命中: 0`，
因为 `load_caps()` 打开的是 `C:\...\Desktop\intent_extracted.json`（256 KB 索引）。
跑一次 `extract_intents.py`（0.2 秒，256876 → 258232 B）之后立刻全绿。

**加规则前 vs 后（同一批原话）**：

| 原话 | 加前 | 加后 |
|---|---|---|
| 打开摄像头 | `hand_vision` L2-STAT | `see_camera` **L1-RULE 100.0** |
| 陪我看看外面 | `vision_loop` L2-STAT | `see_camera` **L1-RULE 100.0** |
| 拍一张 | `vision_embed` L2-STAT | `see_camera` **L1-RULE 100.0** |
| 连拍几张 | `vision_embed` L2-SEM | `see_camera` **L1-RULE 100.0** |

**加规则时必须同时验邻居**，否则会互抢。`see_camera` 的边界是：

- 「看屏幕 / 截屏 / 看桌面」→ `body_see`（看屏）
- 「识别图片 / 看这个图」→ `vision`（看已有的图）
- 「摄像头 / 拍一张 / 手机当摄像头」→ `see_camera`（看真实世界）

**测试时别把探针写进台账**。跑 `router.py "<原话>"` 会往
`state/query_log.jsonl`、`state/route_cache.json`、`state/last_route.json` 记账。
正确做法：跑前备份这三个文件 + 跑后还原；已经写进去的按 `ts` + `query` 白名单精确删，
不要按时间盲删（同窗口可能有真实查询）。

## 4.2 拉取源码要点赞（2026-11-04 主人令）

> 「设置一个拉取源码要求点赞。」

工具：`tools/codex-scripts/atomic-sync.py`

| 动作 | 要不要点赞 |
|---|---|
| `dry-run`（只算不写、只看 diff） | **不要** |
| 写主仓内的文件（开发改动） | 不要（那是 `code_patch` 的门在管） |
| **写产品目录 `payload/`：危险件 / 资金件** | **要** |
| **写产品目录 `payload/`：普通件（文档/技能/素材/普通代码）** | 不要 —— GBT 自决，落 `auto_approve` 账 |

> 2026-11-06 主人令（逐字）：「只有危险能力使用和资金转账需要终端 YES，其他的 GBT 自己决策不需要人工」。
> 分级写在 `atomic-sync.py` 里，随时可查：`atomic-sync.py policy`（配 `--paths-file` 可试算一批）。
> **判不准一律升 danger**；一批里只要有一件危险/资金 ⇒ **整批**要 LIKE。
> 自改门也在危险白名单里（`api.py` / `auth_gate.py` / `security/` / `caps_registry.py` / 本工具自身）。
> 想恢复旧的「逐件点赞」：`GBT_SYNC_STRICT=1`。

### 怎么点赞（必须在主仓终端由主人执行）

```powershell
# 主人在真终端里跑，会要求输入 LIKE 确认
.\GBT小土豆V8桌面版\payload\pyembed\python.exe tools\codex-scripts\atomic-sync.py like --note "把 caps_registry 的 16 个能力位拉过去"

# 然后才允许写产品目录
... atomic-sync.py put --src <主仓文件> --dst <payload文件> --root <payload> --apply
```

### 门的四条牙

1. **一次性**：点赞用掉即作废（`used: true`），不能一次点赞刷一批
2. **10 分钟 TTL**：`LIKE_TTL = 600`，过期作废（对齐攻击模式的 TTL 做法）
3. **agent 不能自批**：`like` 子命令要求 `stdin` 是真实 TTY。agent 通过管道/重定向调用时直接 `denied`
   —— 沿用本仓既有口径：「approve 在 CLI/终端侧执行，agent 不能自批」
4. **全落账**：点赞与每次拒绝都写 `state/atomic-sync/ledger.jsonl`

### 被拦时长什么样

```json
{"ok": false, "status": "need_like", "error": "还没有点赞",
 "how": "在主仓终端执行：python tools/codex-scripts/atomic-sync.py like --note \"说明\"",
 "why": "2026-11-04 主人令：拉取源码要求点赞；agent 不得自批"}
```

**看到 `need_like` 就停手报告，别想办法绕过。** 这条门的价值就在于 agent 过不去。



## 5. 改完必须自查

```powershell
# ① 全量语法
.\pyembed\python.exe -c "import py_compile,pathlib;[py_compile.compile(str(p),doraise=True,cfile=None) for p in pathlib.Path('.').rglob('*.py') if not {'pyembed','__pycache__','state','outputs'} & set(p.parts)]"

# ①.5 判据反推（每条结论都要能回到一条可复跑的证据）
.\pyembed\python.exe tools\codex-scripts\claim-audit.py run

# ② 导入冒烟（排除 store/ 这个第三方仓库快照目录）
# ③ 受影响的位跑一次真 op，看错误有没有从「路径不存在」变成「真问题」
```

`gbt_allinone/store/` 是**下载来的第三方仓库快照**（无 `__init__.py`），不是本框架代码，别去 import 它。
`gbt_allinone/tests/` 会**故意拒绝**在已绑定生产 store 的进程里跑测试 —— 那是设计，不是 bug。

## 6. 目录速查

| 路径 | 是什么 |
|---|---|
| `pyembed/` | 内置 Python **3.12.10**（embeddable 包），不用另装。**跑仓内一切 python 都用它** —— 系统别处的 Python 没有 `mss`/`uiautomation`/`pyautogui`，用它就等于"屏幕采集全灭" |
| `gbt_allinone/` | 能力位本体 + 记忆链 |
| `tools/` | 工具与 CLI（`filmgrade.py`、`control_loop.py`、`codex-scripts/`） |
| `holo_pet_w3/` | 界面与 3D 视图 |
| `state/` | 数据、记忆、绑定、设置 —— **全部数据都在这，迁移只需拷它** |
| `outputs/` | 产物与归因报告 |
| `.scratch/` | 临时产物（可删） |

## 7. 语音与视觉的既定选择

- **语音**：`edge-tts` → `zh-TW-HsiaoChenNeural` @ `+15%`（主人 2026-10-04 定）。
  打不开时退 `SAPI zh-TW (Microsoft Hanhan)`，**仍不行就不出声并报原因** ——
  **不许**用大陆腔顶替（`Microsoft Huihui`）。
- **视觉**：屏幕走 `body_eye`；**摄像头**走 `see_camera`；两者都不许「凭想象描述」，
  拿不到帧就如实 `needs_camera`。
