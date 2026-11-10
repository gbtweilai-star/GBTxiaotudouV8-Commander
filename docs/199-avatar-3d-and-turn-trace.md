# 199 · 数字人 3D 空白 / 轮次追踪显示 Python 字典

日期：2026-11-07
范围：`holo_pet_w3/console/{moments.js,turn-trace.js,skin-cube.css}`

## 起因

按「首屏内容质量」体检剩下六页（仪表盘 / 思维导图 / 轮次追踪 / 全链路 / AI 朋友圈 / 数字人 3D），
逐页抓 `innerText` + canvas 尺寸 + 控制台，发现两个硬伤。

## 硬伤一：数字人 3D 整页空白（两个 bug 叠在一起）

| 层 | 现象 | 原因 |
|---|---|---|
| 懒加载 | iframe 一直没有 `src`，`/teardown/` 从没被请求 | `moments.js` 里的懒加载监听还停在旧名字：`data-view='dh'` + `$("dh-frame")`，而视图/iframe 早已改名为 `teardown` / `teardown-frame` |
| 布局 | 即使手动写进 `src`，iframe 量出来也是 **0×0** | 改名的同时丢了显示规则：只有 `.view-dh { display:flex }`，没有 `.view-teardown`；`.view` 默认 `display:none` |

**改法**

1. `moments.js`：懒加载函数改成 `teardown-frame || dh-frame`，点击监听同时认 `data-view='teardown'` 与旧的 `'dh'`，
   并补一个 `gbt:view` 监听（走 `switchView` / hash 进入时也会加载）。
2. `skin-cube.css`：补
   `.console[data-view="teardown"] { top:20px; bottom:20px; background:#05070c; }`
   与 `.console[data-view="teardown"] .view-teardown { display:flex; min-height:0; }`。

**实测**：`#teardown-frame.src = "/teardown/"`，`getBoundingClientRect()` = **794×823**，子页标题
「我们的数字人 · DH-V7 · 可交互 3D」，页面内状态「在线 / 网格 1 / 骨骼 66 / 动画 idle」全部显示（截图 `.scratch/q2-teardown.png`）。

## 硬伤二：轮次追踪直接印 Python 字典

后端账本存的是 `str(payload)[:160]`（`api.py:3050`），前端原样显示：

```
{'op': 'catalog'}
{'op': 'select', 'query': '', 'candidates': [{'id': 'ledger:0', 'source': 'tool_result', …}
```

**改法（只改显示层，不动账本格式）**：`turn-trace.js` 加 `prettyDetail()`——
把 `{k: v, …}` 拆成 `k=v · k=v`，`None/null` 显示为空（只留 key），`True/False` → 是/否，
列表值截 28 字、普通值截 48 字，末尾补 `…`。上限 8 对。

顺带修了标题栏 `5 轮 · 总 5` 的冗余：`total > shown` 时显示「显示 N / 共 M 轮」，否则只显示「N 轮」。

**实测**：`op=status · bindings`、`op=select · query · candidates=[{'id': 'ledger:0' …`、`op=audit · records=[]…`。

## 判据（可复跑）

```
node .scratch/probe-six.mjs   # 六页首屏文本/canvas/空态/JSON 泄漏扫描
node .scratch/probe-tt2.mjs   # 数字人 iframe src/尺寸/子页标题 + 轮次 detail 文本
node .scratch/probe-pulse.mjs # 21 页角标遮挡复扫：{}（零相交）
node .scratch/audit2.mjs      # 21 页 errors:[] / net:[]
```

`probe-tt2.mjs` 期望：
- `teardown.src = "/teardown/"`、`rect = [794, 823]`、`title` 含 `DH-V7`
- `turns.details` 全部形如 `op=…`，不含 `{'`

## 回归

`test_console_chat_print` 7 条 OK；`test_chat_live_steps` ALL OK。

## 已知但本轮未动

- **全链路页**：三列 `.flow-col` 固定 300px，794px 面板里必然横向滚动（第三列被裁）。
  这是既定布局，改动会牵动连线 SVG 的坐标计算，留作单独一轮。
- **思维导图**：左侧根节点标签贴边有轻微裁切（同万能插那类 3D sprite 出界），未改。
- 后端 `api.py:3050` 仍在账本里写 Python repr；本轮只在显示层做转换，账本格式没动（改 api.py 属危险件，需主人点赞）。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
