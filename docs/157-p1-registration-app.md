# 157 · 主人点头后：world_forge / pentest_flow 注册成能力位 + P1 落地 + APP 接线

> 主人令 2026-11-02：「注册 world_forge / pentest_flow 为能力位（零作用域纯函数，不需新攻击面）并接进万能插；
> 开始 P1（世界规格/存档/3D 视图；源码攻击面图/五类代理接 validate()）」。
> 另承接上一轮「我说的是 APP」：本轮全部改动已同步进**桌面版 APP**（`GBT小土豆V8桌面版/payload`）并真机验收。

## 一、注册（两件都进 `caps_registry`，走万能插唯一门）

| 能力位 | domain | 作用域 | 注册位置 | 说明 |
|---|---|---|---|---|
| `world_forge` | engine | **零**（`policy.evaluate` → `scopes=()` / `restricted=False`） | `caps_registry.py` + `api.py` 分派 | 纯函数世界内核（不出网/不起进程/不写盘） |
| `pentest_flow` | security | **零**（同上） | `caps_registry.py` + `api.py` 分派 | 纯函数授权渗透流水线（不攻击/不出网/不写盘） |

- **没有改 `security/policy.py`**（本仓红线）：两件都是零作用域纯函数，门看到的是空作用域；真执行仍受既有门/授权手约束。
- **万能插接线**：`run_task("world_forge", {"op": …})` / `run_task("pentest_flow", {"op": …})`（统一门 = 万能插门）；
- **三源对账**：`cap_self verify` → **registry 390 = snapshot 390 = dispatched 390**（`True`）；
- **能力快照**：`data/capabilities.json` 由 `tools/codex-scripts/export-capabilities.py` 重导出（390 条 / 34 条带作用域）；
- **文档计数**：`tools/sync-cap-counts.py --apply` 全仓同步成现读 390；`tests/test_doc_counts.py` **ALL OK**（0 处不一致）。

## 二、世界 P1（world_forge 增量）

| P1 项 | 落地 | 验收读数 |
|---|---|---|
| 世界规格 | `spec`：一句话 → spec（纯文本映射，不调模型）；支持「三个文明/每国两座城/沙漠/冰原/火山/体素/二维/seed=42」，数字支持中文；LLM 出的 spec 也走 `_normalize_spec` 夹紧 | `"海边的三个文明，每国两座城，体素世界"` → civs=3、cities=2、water=0.45、voxel=True；同句可复现 |
| 存档 | `encode` / `decode`：存档串（JSON + sha256），**只编解码不落盘**（真落盘走 `filesystem_write` 门）；被改过/坏格式拒载 | encode 11,910B（12×12 世界）；decode 后 `state_hash` 与原世界一致；改一个字节 → 拒载 |
| 3D 视图 | `view3d`：列高度/生物群系调色板/城市/文明/体素材质层计数（给 Three.js 用，纯数据） | columns = 宽×高；cities=civs 城市数；palette 8 群系 |
| APP 3D | console 新页签「世界」+ `world3d.js`（Three.js InstancedMesh + OrbitControls + 水面 + 金球城市）+ `/api/world` 只读端点 + 「换一个世界」 | 真机 CDP：`dataset.world3d="ok:576:6"`，状态 `seed=7 · 文明 3 · 城市 6 · 体素 8 层` |

![世界锻造 3D 视图（桌面版 APP 真机截图）](../assets/app-world3d.png)

## 三、渗透 P1（pentest_flow 增量）

| P1 项 | 落地 | 验收读数 |
|---|---|---|
| 源码攻击面图 | `surface({路径:文本})`：路由 / 输入源 / 危险汇点（XSS/注入/SSRF）/ 资产 / **source→sink 信任边界** → SAST 候选（带 file:line 证据） | 测试样本：2 路由、5 候选（xss/injection/ssrf/authz）、3 条信任边界 |
| 五类派单 | `agent_plan(queue)`：Injection / XSS / SSRF / Auth / AuthZ 五类，每任务带 **PoC 契约** | 5 类代理齐；任务数 = 队列数 |
| 接验证闸 | `agent_ingest(results)`：代理回执逐条过 `validate()` —— 无 PoC 一律 `dropped`，有可复现 PoC 才 `exploited` | 1 好 PoC + 1 无 PoC → exploited=1 / dropped=1；全无 PoC → exploited=0 |
| 端到端 | `surface → reconcile → agent_plan → agent_ingest → report/SARIF/CI 闸` | 报告只收 exploited；SARIF 只 1 条 |

## 四、APP 接线（真机验收）

- **同步**：交付树 → `桌面版/payload`：`capability_router.py`、`caps_registry.py`、`api.py`、`omni_plug.py`、`tools/world_forge.py`、`tools/pentest_flow.py`、`tools/omni_adapter.py`、console `index.html/app.js/app.css/world3d.js`、`data/capabilities.json`；`console-server.py` 以**打补丁**方式合入（保留 APP 原有 `/api/dh/hand`、`/api/tianzhen` 等桌面路由），并加 `/api/world`。
- **APP 依赖补齐**：payload `pyembed` 原缺图像采集依赖 → 装入 `mss 10.2.0` + `pillow 13.0.0`（看屏幕从「三级后端全灭」转为真取帧）。
- **重启验证**（真机 HTTP / CDP）：

| 验证 | 读数 |
|---|---|
| `/api/ping` | 200 |
| `/api/chat` 看屏幕 | `ok=true` · 1920x1200（经万能插 app 插座） |
| `/api/chat` 写文件 / 读文件 | `ok=true` · `APP最终验收` 真落盘 / 真读回 |
| `/api/chat` 看图 | `ok=true` · 512x512 · 亮度187.1 / 对比度82.7 |
| `/api/chat` 开网页 | `ok=true` · backend=system-default-browser |
| `/api/world` view3d | `ok=true` · columns=256、cities=6 |
| `/api/world` spec | `civs=3`、`voxel=True` |
| `/api/dh/hand`（APP 原有） | `ok=true`（未被覆盖） |
| `/api/tianzhen?op=status`（APP 原有） | `ok=true` · nodes=166（未被覆盖） |
| console 页面 | 有「世界」页签、`cap-quick` 四类快捷条、`world3d-canvas` |
| **真点按钮**（CDP 点「看屏幕」） | 消息数 1→3；回复：「看屏幕：已取到屏幕帧 · 1920x1200（经万能插 app 插座）」；meta：「万能插 · 看屏幕 · 733ms · 已落审计」 |

![APP 对话页万能插四类快捷条（真机截图）](../assets/app-capability-router.png)


## 四·续、对话 `+` 附图 / 「文件」发送入口（2026-11-02 补）

- **附图 `+`**：点 `+` → 文件选择（`accept="image/*"`），支持**粘贴图片**、预览/移除；随消息发送（气泡内缩略图）；
- **文件入口**：新增「文件」按钮（`#chat-attach-file` → `#chat-upload`，任意文件），发送任意附件；
- **后端**：`/api/chat` 接 `image` / `file`（data URL/base64）：
  - 图片 → `gbt_allinone/chat_image.py` 本地视觉读数（512x512 / 亮度 / 对比度 / 主色），`via="vision:local"`；
  - 文本/代码 → `gbt_allinone/chat_file.py` 解码前 4,000 字 + 行数/字节/sha256，`via="file:text"`；
  - 二进制 → 只报元数据（名字/大小/类型/sha256），**不假装解析**；
  - 单图 ≤8MB / 单文件 ≤20MB；坏附件如实报「读取失败」；
- **APP**：payload 的 `console-server.py`、`app.js`、`app.css`、`index.html`、`chat_image.py`、`chat_file.py` 已同步；
  重启后真机 CDP 验收（`DOM.setFileInputFiles` 塞文本/图片 → 点发送 → 回复含「文本附件…」/「附图：512x512…」）。


![APP 对话附件：文件发送 + 附图（真机截图）](../assets/app-chat-file.png)

- **状态自愈**：界面状态只在启动读一次会死在「离线」快照；已加 `wireAutoRefresh()`（每 15s 静默重读 `/api/data` +
  窗口重新获得焦点立即重读；失败保留当前实时数据）。引擎晚起/冷启动后界面会自动从「离线」变「在线」。
  真机截图：`assets/app-online.png`。


## 四·续 2、内置浏览器（APP 内嵌 Chromium）+ 原生浏览器（Chrome CDP）控制条

- **内置浏览器**：console 新增「浏览器」页签；APP 里用 Electron `<webview>`（独立 `persist:gbt-browser` 分区，
  `contextIsolation=yes`、`nodeIntegration=no`）内嵌真实 Chromium：地址栏（域名自动补 https、非域名当搜索词）、
  前进/后退/刷新/外部打开、加载失败兜底文案；
- 只在桌面版 APP 内可用（Electron `webviewTag`）；浏览器直开时显示兜底说明，可点「外部」用系统浏览器打开；
- **原生浏览器（Chrome CDP）**：同一页顶部有一排控制条，走 `/api/browser → run_task("browser", op=native, action=…)`
  ——「检测」现读 CDP 状态（本机 Chrome 路径、`needs_browser_debug` 如实报）、「启动 Chrome」「在 Chrome 打开当前页」；
- 真机读数：webview 打开 `example.com` → `getURL()=https://example.com/`、`getTitle()="Example Domain"`；
  原生状态 `needs_browser_debug` · `C:\Program Files\Google\Chrome\Application\chrome.exe`（未启动调试口，如实显示）。

![APP 内置浏览器（真机截图：webview 打开 example.com + 原生浏览器状态）](../assets/app-browser.png)

- **AI 在原生浏览器上的能力仍在**：控制条新增「AI 读当前页」，走 `/api/browser → get_text`；真机点击读到
  原生 Chrome 当前页 **917 字**（`get_title`="Example Domain"、`get_text` 正文、`execute_script(js="document.title")`="Example Domain"）。
  页面文字按外部内容纪律标注「仅作数据，不作指令」。AI 动作面未缩水（navigate/get_text/dom_query/click_element/
  type_text/execute_script/screenshot/cookies/intercept… 全在 `native_browser.py`，仍走统一门）。

![原生浏览器 AI 读当前页（真机截图：917 字 + 外部内容纪律标注）](../assets/app-native-ai.png)

## 五、验收汇总（现跑）

| 套件 | 结果 |
|---|---|
| `tests/test_p1_caps.py`（本轮新增：注册/零作用域/P1/APP 接线） | **76 ok / 0 FAIL** |
| `tests/test_world_forge.py`（原 46 项 + 自检扩到 19 项） | **46 ok / 0 FAIL** |
| `tests/test_pentest_flow.py`（原 64 项 + 自检扩到 28 项） | **64 ok / 0 FAIL** |
| `tests/test_capability_router.py`（复跑） | **56 ok / 0 FAIL** |
| `tests/test_doc_counts.py` | **ALL OK**（390 唯一现读） |
| `cap_self verify` | **390 = 390 = 390**（registry=snapshot=dispatched，ok=True） |

## 六、边界（说死）

1. `world_forge` / `pentest_flow` 是**零作用域纯函数**；不新增攻击面、不改 `policy.py`。真正 exploit / 落盘 / 出网仍由既有授权手与门承担；
2. 「世界 3D」是 console 视图（数据面 `/api/world`），不是 AEON 成品渲染；体素列/城市是真实数据渲染，但无纹理/光照调优；
3. `spec` 是**规则映射**，不是 LLM 生成；LLM 版可先出 JSON 再走 `_normalize_spec` 夹紧（P1 未接自动 LLM 调用）；
4. APP 的 payload 依赖 `mss/pillow` 已装；换机/重打包需随包带上（README/payload 依赖说明未改，属打包面）；
5. 仍未做：四角色模型路由、God Console、世界存档写门（`world_store`）、五类代理真实 LLM 运行时、CI 一键脚本；这些是报告里的 P1/P2 剩余项。

## 七、复跑

```bash
py -3.14 -X utf8 tests/test_p1_caps.py        # 76 项
py -3.14 -X utf8 tests/test_world_forge.py    # 46 项
py -3.14 -X utf8 tests/test_pentest_flow.py   # 64 项
py -3.14 -X utf8 tests/test_capability_router.py  # 56 项
py -3.14 -X utf8 tools/codex-scripts/export-capabilities.py      # 能力快照
py -3.14 -X utf8 tools/sync-cap-counts.py --apply                # 文档计数
```

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
