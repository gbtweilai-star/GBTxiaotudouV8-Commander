# 195 · APP 全页面能力对齐体检（2026-11-07）

主人原话：「你在看看 APP 所有页面很多地方能力都没有对齐和实现」。

## 1. 怎么查的（可复跑）

不是靠看截图猜，是拿同一份 `payload` 代码在 Chrome 无头里真跑：

- `http://127.0.0.1:8766/console/index.html` 起真页面（与 Electron 同一套 `console-server`）；
- CDP 逐个点 21 个页签，每页等 5 秒（给 3D 模块和异步取数留时间）；
- 每页记录：渲染文本量、canvas 尺寸、`documentElement.dataset.*` 状态位、可见空态、控制台异常、4xx/5xx 请求。

结果：**21 个页签，0 个 JS 异常、0 个失败请求**。问题不在“报错”，在**数据没接上**。

## 2. 查出并修掉的断点（4 处）

| # | 页面 | 症状 | 根因 | 修法 |
|---|---|---|---|---|
| 1 | 职业 | `触手职业 · 0 种职业`，卡片区全空 | `/api/data` 里 `professions` 是 `None`：产品副本缺 `data/professions.json` | 把该文件同步进 payload（21 职业 / 385 覆盖）；前端 0 条时给出“跑 tools/gen-professions.py”的明示空态，不再白屏 |
| 2 | 穿透扫描 | `目标 — / 扫过 0/0 / 覆盖 —`，卡在“扫描中” | 页面只读 `window.GBT_CONSOLE.scan`（来自 `state/scan-data.json`），产品副本没这个快照；而 `/api/scan` 本来就能现场出 1395 条明细 | `scan3d.start()` 没数据时自动 `fetch("/api/scan?target=bindings")` 补一份，`dataset.scan3dSource=api`；并修掉 `init()` 二次 `loadData()` 把实时数据清空的先后顺序 |
| 3 | 3D 星图 | `ok:0+0+0+0`（应 427 位） | `/api/data` 成功后没有写回 `window.GBT_CONSOLE`，而星图/扫描等 3D 模块读的是这个全局 | 成功取数后 `window.GBT_CONSOLE = j.data` ⇒ `ok:427+32+17080+2` |
| 4 | 技能栏 | 副标题只有一个 `broken` | 校验确实有 1 项不过（`skills/taste-skill/SKILL.md` 的 `name` 与目录名不一致），但页面没说是什么 | 数据层带上 `errors/warnings`；前端显示「30 个 · 1 项待修」，悬停给出具体文件与原因 |

附带修了一处体验坑：**一次刷新失败就把整页打回“离线”**。现在保留上一份真数据，只把连接行标成「本机 · 刷新失败，显示上次数据」；没有过真数据才退回内联快照。

## 3. 修后实测（同一套 CDP 口径）

```
职业      ok:21职业+编程首席     21 张卡片 · 覆盖 385/385 · 域 30/30
穿透扫描  ok:bindings:1395单元+0疑点   覆盖 100% · 死角 0 · 来源 api
3D 星图   ok:427+32+17080+2
技能栏    30 个 · 1 项待修（悬停：design-taste-frontend 与目录 taste-skill 不一致）
全链路    started（427 能力位 / 423 触手 / 24.2k 绑定对）
其余页    0 异常、0 4xx/5xx
```

## 4. 仍然“空”但属实的页（不是坏了）

- **赏金**：`ok:0项目:0发现` —— 没有授权项目就是 0，不编数据。
- **浏览器**：`原生浏览器（Chrome CDP）：未检测` —— 依赖本机 Chrome 调试口，按钮可现场检测/启动。
- **AI 朋友圈**：读 `state/moments.json`，有内容就渲染（当前 10 动态 / 2 广播）。
- **数字人 3D**：iframe 指向 `/teardown/`，200 可开。

## 5. 判据

```powershell
$env:PYTHONIOENCODING='utf-8'
node .scratch/audit2.mjs          # 21 页逐个点，输出异常/失败请求/data 状态位
node .scratch/probe-visual.mjs    # 职业 / 技能 / 扫描 三页截图 + 状态位
```

收尾跑过：`gbt_allinone.tests.test_console_chat_print` 7 条 OK、`tests/test_chat_live_steps.py` 23 条 ALL OK。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
