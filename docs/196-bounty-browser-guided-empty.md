# 196 · 赏金 / 浏览器两页的「有引导空态」

日期：2026-11-07
范围：`holo_pet_w3/console/{index.html,app.js,app.css}`

## 为什么要改

这两个页面前面能跑，但第一次打开的状态是「一片空」：

- **赏金**：`programs=0` 时只剩一排 0 计数，看不出要先「建授权项目」才能做任何事；
  建项目的入口在弹窗里，新用户不知道点哪。
- **浏览器**：`/api/browser` 的 `status` 只在点「检测」时才查，进页面不查；
  没开 Chrome 调试口时，用户看到的是空屏，不知道是「坏了」还是「没开」。

这就是「能力有、但入口不可发现」——功能不算缺失，体验算缺失。

## 改了什么

### 赏金：空态三步 + 就地建靶场

1. `#bounty-empty`（在计数条下方）：`programs=0` 时显示，写明三条路径——
   填名称+范围建项目 → 选中后做范围检查 → 通过后再录发现/出报告；
   同时点明「本模块不扫网络，扫描走安全能力位」。
2. `#bounty-new` 输入行（发现列表上方）：靶场名称 / 授权范围（逗号分隔）/ 授权依据 +
   「建自有靶场」按钮。提交走 `POST /api/bounty {op:"add_program"}`；
   范围按 `[,，\s]+` 切分；授权依据留空时默认填「本机自建靶场」（后端要求该字段非空）。
3. 结果落在 `#bounty-new-result`，并用 `documentElement.dataset.bountyCreate = ok|fail|error`
   给自动化留判据；成功后 `ensureBounty()` 刷新计数与列表。

### 浏览器：进页面自动探一次调试口

- 新增 `bwNativeProbe(force)`：跑 `bwNative("status")`，按三种结果写 `#bw-native-state`、
  `#bw-native-hint` 与 `dataset.bwNative`：
  - `ok` → 已连接 `127.0.0.1:9222`
  - `needs_browser_debug` → 明确写「点『启动 Chrome』（自动带 --remote-debugging-port=9222）」，
    并给出手工加快捷方式参数的补救路径
  - 其它 → 把后端原话带出来
- `switchView("browser")` 里调 `bwNativeProbe()`（只探一次，`BW_PROBED` 去重）；
  「检测」按钮改成 `bwNativeProbe(true)` 强制重探。
- `#bw-native-hint` 常驻一行说明，进页面之前就有话可说。

## 判据（可复跑）

CDP 1600×1000 打开 `/console/index.html`：

```
赏金：emptyVisible=true  emptyHidden=false  name/scope/authref/create 四个节点齐全
      拦截 /api/bounty 后点「建自有靶场」→ payload =
      {"op":"add_program","name":"…","scope":["127.0.0.1","localhost"],"authorization_ref":"本机自建靶场"}
      dataset.bountyCreate = "ok"
浏览器：进页面后 dataset.bwNative = "needs_browser_debug"（本机没开 9222 时）
      #bw-native-state = "未启动（Chrome 调试口未开）"
      #bw-native-hint  = "Chrome 没开调试口：点「启动 Chrome」（自动带 --remote-debugging-port=9222）…"
```

- **副作用隔离**：验证「建靶场」时把 `window.fetch` 对 `/api/bounty` 换成假响应，
  只验接线不写 `state/bounty/programs.json`；真实记录没有被污染。
- 探针：`.scratch/probe-guided.mjs`（空态+建靶场+浏览器页）、`.scratch/probe-bw2.mjs`（轮询等探活）。
- 截图：`.scratch/app-guided-bounty.png`、`.scratch/app-guided-browser.png`。

## 回归

```
tools/codex-scripts/run-tests.py gbt_allinone.tests.test_console_chat_print   → 7 tests OK
tests/test_chat_live_steps.py                                               → ALL OK
```

## 注意

`/api/browser` 只有 POST（GET 会 404），所以「自动探」必须走 POST，不能靠 GET 轮询。
`status` 探测要连 127.0.0.1:9222，本机无调试口时约 1–3 秒才回，前端不要用「立刻可见」断言。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
