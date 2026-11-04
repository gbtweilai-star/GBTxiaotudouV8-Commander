# 162 · 我们自己的原生浏览器（browser_embed · Electron WebContentsView 宿主）

> 主人令（2026-11-02）：「这都不是我们自己的原生浏览器啊」「把没有的都吞噬过来成为我们自己的原生能力」。
> 之前两版都不算：`<webview>` 只是网页里塞个 Chromium 标签；`native_browser.py` 是外部 Chrome CDP。
> 本件是 **P0**：Electron `WebContentsView` 宿主，浏览器成为 APP 自己的面板，不再是系统 Chrome。

## 一、落地形状

```
APP 主进程 resources/app/main.js
  └─ browser-embed-host.cjs（WebContentsView 宿主）
       · 私有分区 persist:gbt-browser
       · 标签（≤12）· 地址栏/前进/后退/刷新 · 下载 · 权限 deny · URL 白名单
       · IPC browser:embed → preload window.gbtBrowser
console 页面（/console/index.html「浏览器」页）
  · 标签条（新建/切换/关闭）
  · 地址栏/工具栏 → gbtBrowser.navigate/back/forward/reload
  · 宿主不可用时自动降级回 <webview>（浏览器直开）
契约真源：gbt_allinone/tools/browser_embed.py（纯函数：URL/边界/标签/下载名）
```

## 二、为什么这次算「我们自己的」

| 对比项 | 之前 | 现在 |
|---|---|---|
| 宿主 | 外部 Chrome（CDP）或页面内 `<webview>` | **APP 主进程 `WebContentsView` 子视图**，随 APP 窗口布局/隐藏 |
| 地址栏/后退/刷新 | 自己画但页面还是 `<webview>` | 宿主真实导航，`state` 回传 URL/title/canGoBack |
| 标签 | 无 | 多标签（新建/切换/关闭，独立 `WebContentsView`） |
| 下载 | 交给系统浏览器 | `will-download` 统一落到 `Downloads/GBT浏览器/`，文件名清洗 |
| 权限 | 无统一收窄 | 分区级 `setPermissionRequestHandler` 全 deny（摄像头/定位/通知等） |
| 边界 | 页面内嵌死 | 渲染进程传页面矩形，主进程 clamp 后 `setBounds`（防越界 IPC） |
| 页面文字 | 未区分 | AI 读页面仍走 `browser` 能力位（外部内容纪律），**不**因内嵌而放宽 |

## 三、真机读数（2026-11-02 APP）

| 项 | 读数 |
|---|---|
| `window.gbtBrowser` | 存在；`show/navigate/state/newTab/switchTab/closeTab` 全部可调 |
| 打开 example.com | `state.url=https://example.com/` · `title="Example Domain"` · `loading=false` |
| 标签 | `newTab('https://example.org')` → tabs=2；`switchTab(1)` → active=1；`closeTab(2)` → tabs=1 |
| URL 安全 | `navigate('javascript:alert(1)')` → `{ok:false, error:"scheme_not_allowed"}`，页面不动 |
| 截图 | 宿主内嵌 example.com + 标签条 + 地址栏（`assets/app-native-browser.png`） |

![我们自己的原生浏览器（APP 内 WebContentsView 宿主，真机）](../assets/app-native-browser.png)

## 四、边界（说死）

1. **下载只接线未真下大文件**：`will-download` 路径/清洗/回执已写，本轮只验 URL/标签/边界；真下载要下一次补读数；
2. **OAuth 弹窗先 deny**：`setWindowOpenHandler` 只允许同标签 http/https 导航，第三方登录弹窗暂不开（安全优先）；
3. 历史记录 UI、书签、页面内查找还没做；地址栏只做「打开」；
4. APP 用的是打包目录 `resources/app/` 的副本：仓库源 `holo_pet_w3/shell/browser-embed-host.cjs`，改完必须同步到 APP（本轮已同步并重启验证）；
5. 契约（`browser_embed.py`）与宿主（JS）是两份实现，测试两边都查；宿主行为以真机读数为准。

## 五、复跑

```bash
py -3.14 -X utf8 tests/test_browser_embed.py       # 契约 + 宿主/APP 接线
# APP 内：顶部「浏览器」→ 地址栏输入 example.com；标签 + / ×
# CDP 验：window.gbtBrowser.state() / newTab / switchTab / closeTab
```

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
