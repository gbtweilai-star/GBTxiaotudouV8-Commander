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
| `omni_plug` | 万能插：`op=universal` 现场认接口生成适配器；`op=all` 全开 |
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
| **写产品目录 `payload/`（= 拉取/发布源码）** | **要** |

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



## 4.3 修复纪律（主人令 2026-11-04，三条都是硬要求）

> 「每次必须使用万能插和多域监控，以及修复必须走镜像多维度空间原子替换。」

| 时机 | 必须做 | 不做的后果 |
|---|---|---|
| **动手前** | `omni_plug` 先认接口（`op=universal` 现场识别 target），不要猜它的类型 | 猜错就是把开放面当封闭面读（2026-11-04 把万能插说成「7 类插座」，被主人当面纠正） |
| **改完** | `python tools/codex-scripts/multi-domain-monitor.py --diff` 跑整面复查 | 改一处坏一处没人知道；且「未通过」必须逐条点名，不许只说个数 |
| **落地** | 走镜像维度原子替换：`mirror_shape` → `mirror_scan` → `mirror_simulate` → `mirror_parity` → `mirror_rehearse` → `mirror_release` | 直接写生产等于没有回滚点 |

**镜像流程的两条铁律**（2026-11-04 实测）：

1. `mirror_release` 返回 `blocked: true`（"生产前排练未全绿，禁止晋升"）时**停手**，不许绕过、不许调高判据。当轮它就拦住了一次不合格晋升——原因是产物页面缺「开发者：自由的风」署名。
2. 产物页面必须自带署名。`console_pages.py` 的 `_shell()` 现在在 `<body>` 后写一行 HTML 注释钢印；新写任何生成器都要照做，否则 `mirror_scan` 的 `signature` 项会红。

**本轮实测数据**：scan 5/5 · simulate 9/9 · parity ok · rehearse ok · release **version 16 / 23 文件**（dimension 从 11 文件扩到 23，把 `holo_pet/assets` 12 个页面纳入维度层）。

## 5. 改完必须自查

```powershell
# ① 全量语法
.\pyembed\python.exe -c "import py_compile,pathlib;[py_compile.compile(str(p),doraise=True,cfile=None) for p in pathlib.Path('.').rglob('*.py') if not {'pyembed','__pycache__','state','outputs'} & set(p.parts)]"

# ② 导入冒烟（排除 store/ 这个第三方仓库快照目录）
# ③ 受影响的位跑一次真 op，看错误有没有从「路径不存在」变成「真问题」
```

`gbt_allinone/store/` 是**下载来的第三方仓库快照**（无 `__init__.py`），不是本框架代码，别去 import 它。
`gbt_allinone/tests/` 会**故意拒绝**在已绑定生产 store 的进程里跑测试 —— 那是设计，不是 bug。

## 6. 目录速查

| 路径 | 是什么 |
|---|---|
| `pyembed/` | 内置 Python 3.13，不用另装 |
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
