# W7 · EigenFlux 独立窗口接入方案

> 状态：**出稿待复核 · 未动刀**（生产代码零改动 · 未起任何 GUI）
> 上游依据：《EigenFlux集成设计.md》§3.1（D2 / D2b / D2c 已批）+ 风哥本批批复原句：
> 「批。三件一个原子单元：`windows.json` 追加 `eigenflux` 条目 · 同批落 `holo_pet_w3/eigenflux/index.html` 最小页 · 同批改 `README.md:17`（O26）。**三件缺一件就是"给一扇不存在的窗加内容"**。出稿报我，不动手。」

---

## §一 开工基线（本轮实测 · 不引用上一版数字）

| 项 | 实测值 | 怎么测的 |
|---|---|---|
| 维度 / reality / 工作区根 三副本 | 12 文件 · 81,206 B · **逐文件 sha16 链式累加（rel + sha）= `a77d1125b76eb94d`** | 本轮现算（`.scratch/_r65_w7_baseline.json`） |
| 三副本是否一致 | **一致**（`dim==reality==work`，差集 `[]`） | 同上 |
| 署名守卫 | clean · **63 页** · missing `[]` · restored `[]` | 本轮现跑 `signature.audit()` |
| 维度树总文件 | **15**（`holo_pet_w3/` 12 + `holo_pet_w25/` 3） | 目录实读 |
| timelines | v1 … **v23**（24 份） | 目录实读 |
| 面板服务 | 常驻 · `ok:true`（launcher 21656 / python 22520） | R64 移交状态 |

**算法口径声明（宪章第二十一章 · 指纹算法必须同名）**：上表指纹是「逐文件 sha16 链式累加（rel + sha）」。
R64 报的 `2206c8c2681fc67b` 是「清单 JSON 序列化取 sha」——**两套算法不可比**，本稿不把它们并列对照。
可比的三项：文件数 12 · 总字节 81,206 · 三副本一致。

---

## §二 取证：这条链路上今天真有什么（逐条带行号）

被测对象：`holo_pet_w3/shell/main.cjs`（18,149 B / 477 行）· `shell/windows.json`（769 B / 1 条）· `holo_pet_w3/README.md`（2,617 B / 46 行）。

| # | 事实 | 位置 |
|---|---|---|
| 1 | 注册表读取：读 `shell/windows.json`，**只认 `parsed.windows` 数组**；解析失败回落空表、**不抛** | `main.cjs:44-53` |
| 2 | 建窗：启动时把注册表里**每一扇**都建出来 | `main.cjs:438`（`registry.windows.forEach(...)`） |
| 3 | `transparent / frame / resizable / alwaysOnTop` 四个字段**都实现**了 | `main.cjs:348-351`、`:361` |
| 4 | 页面加载：`win.loadFile(path.join(HERE, entry.file))` —— `file` 是**相对 `shell/`** 的路径 | `main.cjs:362` |
| 5 | 托盘菜单按注册表逐条生成；**窗口不存在时点击即建窗**，已存在则 hide / show + focus | `main.cjs:388-397` |
| 6 | 单例锁：第二个实例不建新窗，把**所有**窗口 `show + focus` | `main.cjs:430`、`:433-435` |
| 7 | 全关不退：注册表里没有 `role:"main"` → 全关只退托盘 | `main.cjs:456-460` |

### 关键发现一 · `default.visible` 是「声明了没人用」

同一条 entry 里，`alwaysOnTop:false` **有**实现（`:351` / `:361`），`default.visible:false` **没有**：
`main.cjs` 全文对 `visible` 的 6 处引用（`:335` `:382` `:389` `:393` `:394` `:434`）**全是运行时 `isVisible()` 或持久化字段**，
建窗时**从不读 `placed.visible`**，`new BrowserWindow(...)` 也没传 `show:`。

**后果**：`{"visible": false}` 写进注册表 → 下次起壳 EigenFlux 窗**照样弹出来**。
这与 D3「默认不开」、与《宿主不打扰律》第 1 条直接冲突；且与 R63「`--gbt-violet` 声明了、`var()` 0 引用」是**同一类缺陷**：
**声明 ≠ 生效**。

### 关键发现二 · 置顶口径会让「开了看不见」

- 本机实测显示区：**1536×864**（工作区 1536×816）——R64 探针落盘 `.scratch/_r64_w3_live_result.json` → `displays`。
- 上帝视角是 `alwaysOnTop:true` → `setAlwaysOnTop(true, "screen-saver")`（`main.cjs:361`），**系统级置顶**。
- EigenFlux 若照设计稿写 `alwaysOnTop:false` → 开窗后被上帝视角**盖住**：用户点「显示 AI 朋友圈」，看到的还是上帝视角
  —— **窗开了，看不见**，这就是「假绿」在窗口层的形态。
- 屏幕上放不下两扇（1120×720 + 900×640 > 1536×816）→ **重叠不可避免**。所以问题不是"选个坐标"，是**置顶层级**。

### 关键发现三 · 同文件里还有一处同性质假话（不扩批次）

`windows.json` 的 `registry_note` 原文：「窗口注册表数据。W3 只登记『上帝视角』一扇；W4 云电脑 / W5 克劳德另批追加。」
—— 追加 eigenflux 那一刻，前半句即过期。**它在本批文件范围内**（同一份 `windows.json`），随本刀一起改（见 §三.2）。

### 关键发现四 · 署名守卫**覆盖不到** `holo_pet_w3/*.html`

`signature.py::_scan_pages()` 只收三类：① `gbt_allinone/**/*.md` ②家根 framework `.md` ③生产管线产物。
**不收 `holo_pet_w3/`** —— 所以 `holo_pet_w3/index.html` 的署名是「自己守的纪律」，不是守卫强制的。

新最小页**照样必须带署名**，但保证它的**不是** `signature.audit`，而是 `mirror_space.scan()` 的第 3 道门
（维度树内 `.html/.md/.txt` 必须含 `开发者：自由的风`）。**这条区别要写进验收**——不许拿 `signature.audit` 当这条的判据。

---

## §三 逐字段 diff：`holo_pet_w3/shell/windows.json`

现状：769 B · `windows[]` **1 条**（`godview`）。追加后 **2 条**。

### 3.1 新增条目（逐字段）

```json
{
  "id": "eigenflux",
  "title": "GBT小土豆V8 · AI 朋友圈",
  "file": "../eigenflux/index.html",
  "role": "child",
  "alwaysOnTop": true,
  "transparent": true,
  "frame": false,
  "resizable": true,
  "default": { "x": 560, "y": 120, "w": 900, "h": 640, "visible": false },
  "note": "窗口 5 · 批次 W7（D2）。默认不开：由托盘菜单或口令唤起（《宿主不打扰律》）。"
}
```

字段依据（每条都对着代码，不是"惯例"）：

- `id: "eigenflux"` —— 与 `godview` 同形制（小写单词）。**窗口号 5 / 批次 W7 不进 id**：id 是机器键，
  改 id = 换窗口身份，会让 `userData/window-layout.json` 里已存的布局记录失效。
- `file: "../eigenflux/index.html"` —— 相对 `shell/`（`main.cjs:362` 的 `path.join(HERE, entry.file)`）。
- `role: "child"` —— 与 godview 一致。这条**决定「全关 ≠ 退出」**（`:456-460` 只对 `role:"main"` 退出）。
- `title` —— 用户可见文案，用中文「AI 朋友圈」；不出现内部代号（同化口径：用户视野里不出现品牌）。
- `default.w/h = 900×640` —— 都 ≥ `createWindow` 的 `minWidth 720 / minHeight 480`（`:347`）；
  也落在实测工作区 1536×816 内（y 120 + 640 = 760 ≤ 816），**比设计稿的 980×700 收小**，理由在此。
- `default.x/y = 560/120` —— 偏向屏幕右下，右侧留 76px 余量；两扇必然重叠，**重叠不是缺陷，置顶层级才是**（§六②）。
- `default.visible: false` —— **已拍：补进 `main.cjs` 让它生效**（`show: placed.visible !== false`；
  `second-instance` 跳过 `default.visible === false` 的窗）。契约测试见 §七 G9。

### 3.2 顶层 `registry_note` 改法

- 原文：「窗口注册表数据。W3 只登记『上帝视角』一扇；W4 云电脑 / W5 克劳德另批追加。」
- 改为：「窗口注册表数据。已登记窗口见 `windows[]`（**不在本句里写死数量**——写死一次就过期一次）。
  窗口号 N 指位置、批次号 W<n> 指施工序，两套编号见《holo_pet多窗口架构设计.md》§11.1.1。」

`version` / `shell` / `id_convention` 三键**不动**。

---

## §四 最小页 `holo_pet_w3/eigenflux/index.html`（内容逐段）

### 4.1 三条原则

**零脚本 · 零新色值 · 零网络**。只复用 `../window.css` 里**已存在**的类（已逐个核对，共 **29** 个
`.gbt-*` 类：`gbt-body / gbt-topbar / gbt-brand / gbt-grow / gbt-badge / gbt-btn / gbt-main / gbt-card / gbt-wide /
gbt-dim / gbt-json / gbt-statusbar / gbt-signature / …`）。

### 4.2 明确不做（三条，理由在括号里）

- **不画四个空 tab**（动态流 / 私信 / 好友 / 档案）—— 没数据还摆 tab 就是空壳（《反空壳律》）。
- **不引 `window.js`** —— 它绑的是 godview 的 DOM id（`card-self` / `matrix-body` / `tree-host` …），引过来只会报错。
- **不 fetch 面板** —— 本批不接数据链路（`store/health/eigenflux/` 还没建）；页面里出现"数据"就是假绿。

### 4.3 页面结构（8 段 · 逐段）

1. `<!DOCTYPE html>` + `<html lang="zh-CN">` + `<meta charset="utf-8">`
2. CSP：`default-src 'none'; style-src 'self'; connect-src 'none'` —— **因为零脚本，连 `script-src` 都不给**
   （比样板更紧：样板有脚本所以开了 `script-src 'self'`）
3. `<link rel="stylesheet" href="../window.css">` —— 品牌三色 / 顶栏 / 卡片样式**继承，不复制**
4. 顶栏 `.gbt-topbar`：`.gbt-brand`「GBT小土豆V8 · AI 朋友圈」+ `.gbt-grow` + 状态芯片
   `.gbt-badge[data-state="gray"]`「未连接」
5. 主区 `.gbt-main` → `.gbt-card.gbt-wide`：
   - `<h2>`「本窗口还没接数据 —— 如实说」
   - 一段 `.gbt-dim`：「本批只落地『窗 + 最小页』；数据链路（独立审计通道 `store/health/eigenflux/*.jsonl` ·
     轮询 · 草稿确认）走后续批次。**本页不拿占位数据顶替**。」
   - 一张**纯文字**「未接清单」（**不假装按钮**）：动态流 / 私信 / 好友 / 档案 / 草稿确认 —— 各标「未接」
6. 状态栏 `.gbt-statusbar`：左「通道：未建」· 右 `.gbt-badge[data-state="gray"]`「实时流：未接」
7. 署名 footer（与样板同形）：
   `<footer class="gbt-signature" data-developer="自由的风">开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属</footer>`
8. **不写 `<script>` 标签**；行尾与同目录 `.html` 一致（**CRLF**：实测 `holo_pet_w3/index.html` = CRLF 102 行）

---

## §五 `README.md:17` 改法（O26 · 治根不换数字）

- 原文（`:17` 末段）：「…· 无边框 + 透明 + 置顶 · 关一扇不影响其他（**W3 只登记上帝视角一扇**，所以全关 = 退到托盘，不等于退出）。」
- 改为：「…· 无边框 + 透明 + 置顶 · 关一扇不影响其他；**全关 ≠ 退出**（壳退到托盘常驻）。
  **登记了哪几扇以 `shell/windows.json` 为准** —— 本文件不写死窗口数（写死一次就过期一次，见 O26）。」

**理由**：这条假话的根因是「把当前状态写进文档」，与 R64 的 `README:34` 是同一类。
治法同一条：**改动态口径，不换数字**（改成 `rewind(20)` 只会明天再过期）。

---

## §六 待拍 → 已拍（三条 · 风哥 2026-09-17 批复）

> 下表**保留**作决策记录（原建议不删，避免两条口径打架）；批复结果见表后。

| # | 事项 | 我的建议 | 不采纳的后果 |
|---|---|---|---|
| ① | `default.visible:false` 今天**不生效**（发现一）→ 要不要把"可见性"补进 `main.cjs` | **要补（乙案）**：建窗时按 `placed.visible` 传 `show:`；`second-instance`（`:433-435`）跳过 `default.visible===false` 的窗 | 甲案（只走三件）→ 下次起壳**两扇一起弹**，D3「默认不开」落空，`visible:false` 变成"声明了没人用" |
| ② | 置顶口径（发现二） | **`alwaysOnTop: true`**（与上帝视角同级，开窗即在前） | 照设计稿写 `false` → 开窗被上帝视角盖住，**开了看不见**；若坚持 `false`，须同批加"开窗即 `focus()` + 默认位置避开重叠区"，**仍然要动 `main.cjs`** |
| ③ | 是否同批加常驻契约测试 `tests/test_w7_eigenflux.cjs`（注册表条目形状 + 最小页静态闸门） | **本批不加** —— 本轮静态闸门跑在落地脚本里；**下一批（数据链路）再固化** | 不加 → 这轮靠一次性脚本守门（一次性脚本会被归档，下轮没有守门人）；加 → 批次从 3 件变 4/5 件 |

**关于 ① 的边界声明（《原子单元边界必须来自方案原文》）**：
采乙案 → 本批**从三件变四件**（多 `shell/main.cjs`，两处共 3 行）。按宪章第二十章，**我不自己扩边界**，这条请风哥拍。
若拍"只走三件"：我把 `default.visible` **从条目里去掉**，并把 `README:17` 改成"起壳会开两扇"——**不留假话**。

**批复结果（2026-09-17）**：
- ① **认甲 · 补**（批次 **3 件 → 4 件**，风哥：'让声明生效'比'删掉声明'是治根；与 R64 紫色 token 治同一类病：**声明 ≠ 生效**）。
- ② **认甲 · `alwaysOnTop: true`**（同级置顶，最后点的在前，用户自己切换）；附观察项 **O27**。
- ③ **认不加**：**不新立 `tests/test_w7_*.cjs`**（静态接入批不加常驻测试套；**数据链路那一批必须补**）。

**契约测试落点（按「default.visible 补进 main.cjs —— 契约测试必须跟上」）**：挂进**已有**的
`tests/test_layout_snap.cjs` **第 8 例**（① 纯函数层 `layout.normalize` 的 visible 语义 ② 源码层 `main.cjs` 有没有真的用它）。
因此本刀实际改动 **5 份**：`shell/windows.json` · `README.md` · `shell/main.cjs` · `tests/test_layout_snap.cjs` ·
新增 `eigenflux/index.html` —— 比批复的四件**多一份**，多的正是「契约测试必须跟上」那条的落点（**不新立文件**，守③）。

---

## §七 验收判据（动刀时**现测**，不引用本稿数字）

| 门 | 判据 | 为什么 |
|---|---|---|
| G0 | 动刀前三副本 12 文件一致；备份目录 `BACKUP_MANIFEST.json` 逐文件 sha/size 独立复算一致 | 回滚要有裁判 |
| G1 | 维度写完 → `scan()` **5/5** | 含第 3 道署名门（发现四：**这条才是**新页署名的判据） |
| G2 | `windows.json` 解析闸门：JSON 合法 · `windows[].id` **无重复** · id 集合含 `godview` 与 `eigenflux` | 判据从被测对象推导，**不写死"2 条"**（宪章第二十二章） |
| G3 | 最小页静态闸门：署名在位 · `<script` **0 命中** · 裸色值 **0 命中** · `<link ... ../window.css>` 在位 · CSP 在位 | 零脚本 / 零新样式是承诺，要能自动判 |
| G4 | `node --check` 全部 `.cjs` 0 错 · `py -3.10 holo_pet_w3/tests/run_tests.py` 全绿（通过/失败/总数**现测**） | 既有 11 例不许被新文件带红 |
| G5 | `ascend()` → 新版本号；护照 `files` == 维度文件数（**现测**） | 一次性全量 |
| G6 | 落地工作区根：源 == 目标逐文件 sha 一致 · 生产漂移 `[]` | 三副本一致 |
| G7 | **反假绿负对照**（《扫描器自证律》）：a) 删掉新页署名 → `scan()` 必须**红**（署名门）b) `windows.json` 改坏一处括号 → 解析必须回落空表 c) 两组结果与对照组**必须不同** | 闸门不在岗 = 假绿 |
| G8 | 账本：过程事件逐条在（维度写 / 晋升 / 落地）；`signature.audit` 页数 **63 → 64**（现测） | 新 `.md` 进守卫范围 |
| G9 | **窗口可见性契约**：`tests/test_layout_snap.cjs` 第 8 例全绿；**判别性负对照**用写盘前的旧 `main.cjs` → 必须红（两组不同） | 「声明 ≠ 生效」这类缺陷要能自动抓（本轮已实测 `RED_AS_EXPECTED`） |

---

## §八 回滚口径

- 生产树 `holo_pet_w3/` **不在镜像检查点覆盖范围**（`checkpoints/` 只冻 dimension + reality + 生产树指纹）
  → 走《主控台品牌清洗方案》§九 口径：动刀前把 **12 文件整树**备份到 `.scratch/_r65_backup_holo_pet_w3_<ts>/`，
  并落 `BACKUP_MANIFEST.json`（逐文件 sha + size）。
- 回滚 = **逐文件拷回 + 重算 SHA 比对**；**不比对通过不算回滚成功**。回滚前 / 回滚后 / 原件**三份 sha 都留**
  （宪章第二十章 · 双向 SHA 对照）。
- 镜像侧回滚走 `rewind(该版本号)`；**版本号不许按数字推断** —— 先 `mirror_status()` 读 `timelines/` 实际值
  （这正是 `README:34` 那条假话的治法）。

---

## §九 本批不做（边界 · 逐条）

- 不动 `holo_pet/` / `potato_pet/` / `gbt_allinone/*.py`——尤其 **`codex_bridge.py`（桥接层第二刀另批）**。
- 不接数据链路：不建 `store/health/eigenflux/` · 不写轮询 · 不补 `POST /api/eigenflux` 的 `owner_session()`（G4 门禁项，属门禁批）。
- 不做口令开窗（D4 白名单词表）· 不做数字人反应（D5）· 不做提示分级（D6）——**窗先存在，才谈这些**。
- **不跑 GUI**（本批零启动；真窗口验证另排"一次启动 · 一次抓取"）。
- 不复制第二份 Electron（225 MB）。
- 不并 `holo_pet_w25/`（O24 另开刀）· 不动 `.mirror.lock` 那 1 B 文件。

---

## §十 施工序（每步之间停下报告）

1. **出稿**（本文件）→ 报风哥复核。
2. 复核通过 → 动刀：维度写（改 `windows.json` 2 处 + 新增 `eigenflux/index.html` + 改 `README.md:17`）→ `scan()` 5/5。
3. **`ascend()` S7 单独批**（R64 那次属特批，风哥明示"下不为例"）→ 新版本号。
4. 落地工作区根（七闸门骨架复用 `.scratch/archive/_r64_land_20260917T193343.py`）→ G6 / G7 / G8。
5. 报账；memory 追加本轮条目。

---

## §十一 红线（本批有效）

一次启动不重跑 · **S7 单独批** · 两套色不互相顶替（新页**不新立色值**）· 状态列不变紫 ·
内容原文永不入档 · 不碰桥接层 · **不跑 GUI** · 不复制第二份 Electron · 宿主规矩照旧（**串行、无并发、跑完即停**）。

---

## §十二 动刀实录（R66 · 维度侧 · 2026-09-17）

**只写镜像维度**（`store/mirror_space/dimension/holo_pet_w3/`）；`reality/` 与工作区根**一个字节没碰**（落地是下一批）。

| 文件 | 改前 | 改后 | sha16（改后） |
|---|---|---|---|
| `shell/windows.json` | 769 B | **1,429 B** | `40b67ecf76e03181` |
| `README.md` | 2,617 B | **2,720 B** | `3c1b32205c1a8a7d` |
| `shell/main.cjs` | 18,149 B | **18,521 B** | `b3c376befa508d5b` |
| `tests/test_layout_snap.cjs` | 5,123 B | **6,945 B** | `b4a8a3972fd21492` |
| `eigenflux/index.html` | ——（新） | **1,645 B** | `df66035618d4b329` |

树级：维度 `holo_pet_w3/` **12 → 13 文件 / 81,206 → 85,808 B**；**同算法**链式指纹
`a77d1125b76eb94d` → `0acb79505cdfcd9d`（宪章第二十一章：两侧同算法才可比）。全维度树 **15 → 16 文件**。

**闸门实测**：`scan()` **5/5**（16 文件 · 署名门全携带 · 入口含 `holo_pet_w3/eigenflux/index.html`）·
维度树测试 **12 通过 / 0 失败**（4 品牌 + 8 布局）· 判别性负对照 **`RED_AS_EXPECTED`**
（同一份新测试 + **写盘前备份里的旧 `main.cjs`** → 第 8 例正好红在 `show:` 那条断言上：7 过 1 红；两组结果不同）。

**写前备份**：`.scratch/_r66_backup_dimension_holo_pet_w3_20260917T195533/`（12 文件 · 逐文件复算一致 ·
链式指纹 `a77d1125b76eb94d`）。

**两条自伤（如实留档）**：

1. **锚点写成 LF 去对 CRLF 文件** → `sub_once` 返回 `None`，下一行接着拿 `None` 当字符串 → 崩在 `MAIN_SI` 那一步。
   修法：锚点统一走 `_crlf()`；`sub_once` 失败改为**返回原文本 + 计数 0**（不级联崩）。
   —— 《脚本编码律》同族的**假失配**：不是磁盘坏了，是脚本自己写法不对。
2. **`_audit()` 没插 `ROOT`** → 五条 `deploy_stage_write` **全失败**（`No module named 'gbt_allinone'`），
   而失败只 print 一行、`rc` 仍为 0 —— 与 R64 自伤 #2 同族（「说了写审计、实现里没落」）。
   修法：`_audit` 插 `ROOT` + 失败即 `rc=13`（不许静默）；五条账**按磁盘真实 sha 补写**，
   顺序差（先写文件、后补账）写进证据不藏（账本只加不改）。

**观察项**：**O27**（同级置顶需手动切换）· **O28**（`HEARTBEAT.md` 中段 17 行裸 LF，另开刀统一）
已落 `PROJECT_BLUEPRINT.md` §八；**O26** 标「已闭环 · 维度侧」——**真闭环要等 S7 + 落地**。

**下一步（未做 · 等批）**：`ascend()` **S7 单独批** → 落地工作区根（七闸门 + G8 页数 63 → 64）。

---
> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
