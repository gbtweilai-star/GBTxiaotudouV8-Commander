# Codex 生成脚本集

## 来源
本文件夹收录 GBT小土豆V8 构建/验证/渲染/探测链路上生成的辅助脚本，原位于 `.scratch/`。

## 分类

### build_* — 版本构建器
对应 V3–V21 各版本的双交付物（画布 + 原型）生成链。
- `build_v{N}.py` + `build_v{N}_manifest.py` + 可选 `build_v{N}_canvas.py`
- 早期版本用 `build_manifest.py` / `build_deliverables.py` 等通用名

### verify_* — 校验器
每版交付物的自检脚本，输出 PASS/WARN/FAIL 计数。
- `verify_v{N}.py` — 后端 Python 断言
- `verify_v{N}_runtime.js` — 运行时 DOM/CSS 检查
- 可选 `verify_v{N}_canvas_runtime.js` — 画布页校验

### panels_v{N}.js — 面板代码
嵌入原型 HTML 的各版本能力面板 JS 片段（V6–V20）。

### probe_* — 探头脚本
运行时真调探活：大脑五维、语音/蓝牙状态、能力接线、策略门等。

### render_* — 浏览器渲染
Playwright 截图链：单面板 / 全画布 / 上帝视角 / 响应式多视口。

### export_* — 导出
`export_renders.py` — 汇总渲染产物出目录。

### make_* — 辅助素材
品牌预览、字体预览、Logo 素材、能量报告等一次性生成脚本。

## 使用
**必须在仓库根执行**（脚本用根标记 `gbt_allinone/` 向上找根；本目录已不在 `.scratch/`，
深度比脚本原来假设的多一级）：

```powershell
cd C:\Users\ADMIN\Desktop\GBT小土豆V8
py tools\codex-scripts\verify_active.py           # ★ 现役代门：自动判代次并派发（见下）
py tools\codex-scripts\verify_v22.py              # 现役 V22 静态/契约/红线/对比度/结构（50 项）
py tools\codex-scripts\audit_craft_gate.py        # craft-gate 只读复核
```

### 🔴 现役代门：`verify_active.py`（2026-09-22 补，踩过才有的）

那排 `verify_v{N}.py` **每支按死自己那代的文件名**。现役换到 V22 之后发生了两件事：
`verify_v21.py` **一跑就 `FileNotFoundError` 崩在第二行**（读的人容易当成"现役交付件坏了"），
而 **`verify_v22.py` 根本不存在** ⇒ **现役两件长期没有任何内容门**。

现在：

| 命令 | 作用 | 现读 |
|---|---|---|
| `py tools/codex-scripts/verify_active.py` | 读根目录 `V*.html` 判现役代次 → 有验脚本就跑它、透传退出码；没有就 exit 2 并点名缺哪支、照谁抄 | 派发到 `verify_v22.py`，**50 项全过** |
| （同伴件清单） | 顺带列出同代应有的 `verify_v{N}.py` / `verify_v{N}_runtime.js` / `verify_v{N}_canvas_runtime.js` | **只报告不判红**：V22 的静态那支已补，两支运行期还没写 |
| `py tools/codex-scripts/verify_v21.py` | 旧代门 | 代际不符时 **exit 2 + 指路**（不再崩栈） |

**emoji 口径（写死在 `verify_v22.py` 里，别退回宽扫）**：只认**图形类** emoji
（`U+1F000–1FAFF / U+2600–27BF / U+2B00–2BFF / U+FE0F`），且只有
**元素文本整体就是 emoji**（`<span>🔴</span>`）或 **alt/title/aria-label/placeholder/content 里带 emoji** 才算"当图标用"。
**箭头（→ ← ↔ ⇒）、序号（① ②）、几何符号（◇）在正文里是标点，不算违规** ——
第一版宽扫把它们全算进去，原型误报 1、画布误报 6（**假红**）；而正文里的 🔴 会**逐条列出**（不判红、也不藏）。

自检口径：`verify_v22.py` 的"两文件都在且够大"一行给出实际读到的 KB 数；缺件时**代际守卫先拦**（exit 2），
不会走到 `FileNotFoundError`。

### 🧪 仓库自带测试：`run-tests.py`（2026-09-22 补，踩过才有的）

仓库里有真测试 —— **`holo_pet/tests` 157 项 + `gbt_allinone/tests` 1,606 项（合计 1,763 项）**，
其中包含正是这几轮在找的那些门（例如「`APP_SURFACE` 与真实路由双向对账」）。但它们**一直没有入口**，而且**默认跑不起来**：

```
py -3.14 -m pytest gbt_allinone/tests -q        # ⇒ Interrupted: 80 errors during collection
RuntimeError: 拒绝在绑定【生产 store】的进程里跑测试：… \gbt_allinone\store
```

这不是框架坏了，是**保护**：`gbt_allinone/tests/__init__.py` 有一条生产 store 隔离守卫
（历史上真把 `t-sched-run` 写进过生产 `schedules.json`）。pytest 收集时会**先 import 父包**，
父包在 import 期就把 `STORE_DIR` 绑死，于是守卫**故意报错停下**。
解法就是守卫自己写的解法①：**起 Python 之前**设好 `GBT_STORE_DIR`（还有 `GBT_CREATE_ROOT`）。

```powershell
# ★ 推荐：本器替你把隔离根设好（临时目录，一跑一换）并打印出来
py tools\codex-scripts\run-tests.py                      # 全部测试根
py tools\codex-scripts\run-tests.py holo_pet/tests       # 只跑一个根
```

| 测试根 | 项数 | 耗时 | 现读 |
|---|---|---|---|
| `holo_pet/tests` | 157 | ~10 s | ✅ |
| `gbt_allinone/tests` | 1,606（+7 skipped） | **~9 min** | ✅ |
| **合计** | **1,763 passed · 0 failed** | ~9.5 min | ✅ |

⚠️ 两点口径：① 「没收集到测试」**不等于通过**（本器会标「空」）；② pytest 缺失时**exit 3（前置不可用）**，
不与"测试失败"混为一谈。**体量说明**：这套要 9–10 分钟 ⇒ 它**不放进** `gbt-checkup.py` 那类快记分牌，
单独跑。

**构建器不许重跑**：`build_v3.py` ~ `build_v21.py` 都是一次性版本构建器，重跑会原地
覆盖已发布版本（`build_v21.py` 已加 `--allow-overwrite` 守卫，无该参数即拒绝写入）。
它们引用的是**上一版**的根目录文件（如 `build_v8_canvas.py` 读 V7 画布），而 V7~V20
早已从根目录移入 `archive/`，所以重跑会在取源那一步就失败。

### 🔬 门的自证约定：`--negctl`（2026-09-22 晚补，踩过才有的）

**纪律**：**没被证明能红的门，不算门**。一个检查器只要判据写窄了、基准写宽了、或者
`continue` 跳过头了，坏输入照样"通过"，而输出与真的通过**一模一样**。所以凡是承载结论的
检查器，都要自带一支能把状态**现造出来**的负控（夹具写在临时目录里，**不碰真件**）：

| 工具 | 负控做什么 | 期望 |
|---|---|---|
| `audit-dh-status.py --negctl` | 自造一份状态源，引用一个必然不在盘的路径 | `--strict` 判红（exit 1）；`--no-receipt` 保证不盖真回执 |
| `design-inventory.py --negctl` | 在**自己的临时副本**上塞一条死路径 | 判红（exit 1）；判完核真身 sha 未变、副本已清 |
| `plugins/gbt-master/tools/check-panel-syntax.py --negctl` | 5 支夹具：坏 importmap ×3 + JS 语法错 + 干净页正对照 | 坏的判红、干净的保持绿 |
| `plugins/gbt-master/tools/shot-skeleton.py --negctl` | viewer 指向不存在的模型 | 必须红字报出、不落 `__shot` |

另有两只**只读候选稿**用的开关（不写回执，不动现役件）：

```
py -3.14 tools/codex-scripts/audit-dh-status.py --status <候选稿.json> --no-receipt
```

**为什么非要"副本 + sha 核对"**：负控要制造坏状态。若改的是真身、靠 `finally` 还原，
中途被 kill / 断电就把真件留在坏状态里 —— 而这道门判的正是"声明与盘上一致"，
自己坏了会把整条线的验收带偏。**改副本、跑副本、删副本**最坏也只是删掉一个临时文件。

## 已知损坏留痕（不要试图「修」）
`verify_v3~v7_out.txt` 等 10 份日志是合法 UTF-8 但含 590~1089 个 U+FFFD 替换符
（不可逆丢失），另有 10 份 `.out` 根本不是合法 UTF-8。成因已定位：`verify_v3~v7.py`
没有 `sys.stdout.reconfigure(encoding="utf-8")` 这一句，在 GBK 控制台重定向时输出被
就地损坏；`verify_v8.py` 起都有了这一句，所以 V8 以后的日志干净。这些记录无法复查，
只能标注。今后统一 `py -X utf8 <脚本> > 日志` 或脚本内直接写文件。
**2026-09-22 晚又踩一次同一坑**（这次是**临时负控脚本**：`print` 里一个 `⇒` 就直接
`UnicodeEncodeError` 崩在第一条输出上）⇒ 结论写死：**凡是要 print 的仓内脚本，第一行防御就是**
`sys.stdout.reconfigure(encoding="utf-8", errors="replace")`，别等到日志被损坏才发现。

## 清理
`.scratch/` 里剩余的 backup 目录（138 个）可安全删除；本文件夹脚本保留作为历史构建链参考。
