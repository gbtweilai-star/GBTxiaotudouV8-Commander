# 102 · 认知界面：照着上游参考项目做 1:1 布局，装我们自己的原生能力（含土豆 Logo）

> 主人 2026-11-01：「去看看开源的上游项目，按照她那样做把我们自己的原生能力排布进去，
> 一比一做一个属于我们自己品牌的」+「她自己的土豆 Logo 别忘了哈」。
> 本文记录：拆了什么、照搬了什么骨架、装了什么内容、怎么验的。

## 一、先拆：28 个旧面板全部拆除（不是藏起来）

- 29 个页面目录 → `.archive/panels-20261101/`（**71.91 MB，可恢复**）；
- `holo_pet_w3` 只剩：`assets/ theme/ shell/ tests/ console/`；
- 壳注册表 `shell/windows.json`：**20 窗 → 2 窗**（console 主窗 + dsh-chat 对话页）；
- `shell/nav-index.json`：几十项 → **2 项**；
- `holo_pet_w3/index.html` → 0 秒跳转新控制台；仓库根 `index.html` 里 3 处旧面板链接已改指控制台。

## 二、1:1 到哪一步了（设计令牌与布局逐项对齐）

第一版只是「三栏感觉像」，主人一眼看出不对劲。这版**直接照它的 CSS 令牌与布局规则来**：

| 维度 | 参考布局 | 我们的认知界面 |
|---|---|---|
| 主色令牌 | `--bg0:#111821` · `--bg1:#172231` · `--panel:rgba(20,28,40,.78)` · `--console-bg:rgba(22,31,44,.78)` | **逐个照抄**（同名同值） |
| 强调色 | `--warm:#ff9f1c` · `--cool:#4f8cff` · `--ok:#39d98a` | 同值 |
| 边框/阴影 | `--line` · `--line-strong` · `--shadow-soft` · `--shadow-console` · `--shadow-inset` | 同值 |
| 侧栏宽度 | `--side-panel-width: clamp(260px,25vw,362px)` | 同值 |
| 中栏左右缩进 | `--side-panel-console-inset: calc(side + 40px)` | 同值 |
| 布局方式 | `.panel{position:fixed; top:20px; bottom:20px; width:…}`；`#panel-l1{left:20px}`；`#panel-l2{right:20px; 透明 rail}`；`.console{left/right: side+40px; bottom:22px}` | **同结构同数值** |
| 右栏模块 | `.l2-module` 各自卡面（radius 12 / padding 16 18 / blur 20 / shadow-soft+inset） | 同构 |
| 心跳图 | 高 92px、暖色网格背景 + `heartbeat-gridline` / `heartbeat-wave` / `heartbeat-sweep` | 同构同命名 |
| 行动日志 | `height: clamp(180px,25vh,220px)`；`.action-log-surface` 卡面 + 细行 | 同构 |
| 字体 | Inter + JetBrains Mono（8–15px kicker/stat 体系） | 同一套字体与外链 |
| 顶栏 | 38px 空白拖拽区（非视觉元素） | 同（38px 空条 + 底边线） |
| 图谱 | `#graph` 默认 `display:none` | 同默认隐藏；点「重置节点图」才开（我们额外的能力域图谱） |

**仍然不同（故意的，也是该不同的）**：

1. 内容是我们的：能力 385 / 技能 23 / 守卫 4/4 / 本机指挥官 / 编排账本；不是聊天记忆图；
2. 它有语音球、热点地球、文档/人物卡、世界杯/台风面板 —— 这些模块对应它自己的领域能力，我们没有就不摆空壳；
3. 它没有页脚；我们的**署名**放在左栏底部一行小字（本仓铁律：每页带署名，不删除）；
4. 它的图谱是记忆节点图（需要后端 graph 数据）；我们改成能力域图谱，默认关。


### 2.1 实测几何（不是目测，像素级量出来的）

| 边界 | 外部参考渲染 | 我们（修正后） |
|---|---|---|
| 左栏 top / bottom | **20 / 979** | **20 / 979** |
| 左栏 left / right | **20 / 381** | **20 / 381** |
| 右栏 left / right | **1218 / 1579** | **1218 / 1579** |
| 中栏 inset | left 402 / right 1197 | 同 |

> 第一版我们多了 38px Electron 标题栏偏移（面板从 y=38 开始）——这是「看着不对劲」的最大来源；
> 浏览器形态下参考页没有这个偏移，已去掉，现在 top=20 与参考一致。

### 2.2 输入框：按 DSH（现在这个对话）的样式，不用上游参考项目那条

主人令：「我们的这个对话输入框要跟我们现在对话这个一样，不要他那种太难看了」。

| 项 | 做法（对齐 DSH 设计令牌） |
|---|---|
| 卡片 | 圆角 **20px**（DSH `--dsw-radius-xl`），边框 `--dsw-alias-border-l1`（暗色 = `#ffffff0f`），底色取 DSH 暗色 `bluish-800 #353638` 低透明叠加 |
| 输入 | 无边框 textarea，14px/22px，placeholder `#81858c`（DSH bluish-600） |
| 工具行 | 左：附件占位 + 模型 chip（本机权重 · 无限上下文）；右：**圆形发送键 32px**（brand-primary `#f9fafb` 底 + `#151517` 箭头，禁用态 `#2c2c2e`） |
| 位置 | 居中 `width: min(calc(100% - 16px), 952px)`（同 DSH `--dsh-composer-card-max-width`） |
| 座席 | 外层 `composerSeat` 同款底部渐变（transparent → `--bg0`），不再画上游参考项目那种整条框 |

## 三、她的开源头像（不是我自己画的文字图标）

主人提醒：「她开源头像你看不到吗？」—— 看得到，已接：

| 项 | 内容 |
|---|---|
| 来源 | GitHub 用户 `gbtweilai-star`（名字「GBT小土豆」）的头像 `https://avatars.githubusercontent.com/u/304471788?s=512` |
| 品牌资产 | `icons/avatar-src.jpg`（原图）/ `icons/avatar.png`（512）/ `icons/avatar-96.png` |
| 控制台 | 左栏 `brand-mark` = **圆形头像**（不是文字「土」）；favicon = `avatar-96.png` |
| 应用图标 | `icon-512/192/apple-touch/favicon-32` 全部由她的头像生成（`tools/gen-potato-logo.py` 已改为用头像） |

> 诚实说明：上一版我自造了「GBT / 小土豆V8 / 385 caps」文字图标 —— 那是错的方向，已作废；
> 品牌标识现在就是**她自己的头像**，数字不再画进图标（数字有 `cap_self` 真源，不靠图标记）。

## 四、「无限制上下文 → 稳定输出」怎么落到界面

| 环节 | 做法 |
|---|---|
| 无限上下文 | 每轮对话 `energy_core.think(context="console-web")` → `llm/ring_context`：模型只吃**有界窗口（12,000 字符）**，全量历史落 sqlite，可随时 recall |
| 稳定输出 | `temperature=0.0`、`max_tokens=512`；同一问题同一回答 |
| 界面可见 | 顶部副标 + 引擎行都写「无限制上下文 · 稳定输出(temperature=0)」；每条回答附 `tok / ms / temperature=0 / 上下文 seq / 历史轮数` |
| 实测 | 同一个问题连问两次：**回答逐字一致**（稳定）；`ring.seq=48 · db_turns=48 · window=12000`（上下文在长） |

> 如实说明：本机 5GB 小模型**自己回答**「不支持无限 context」——那是它对自己没见过的东西的瞎猜；
> **提供无限上下文的是框架（ring_context + sqlite recall），不是模型自述**。界面展示的是框架能力与真实读数。

## 五、怎么开

| 方式 | 命令 | 形态 |
|---|---|---|
| 实时（真数据 + 真对话） | `python tools/console-server.py --port 8766` → 打开 `http://127.0.0.1:8766/` | `/api/data` 现读、`/api/chat` 走本机指挥官 |
| 离线快照 | 双击 `holo_pet_w3/console/index.html` | 读 `state/console-data.js`（`python tools/gen-console-data.py` 生成） |
| 桌面壳 | 双击 `启动-GBT.cmd`（壳注册表已改为 console 主窗） | 壳内加载同一页 |

## 六、验证（真跑）

```
tests/test_console.py  ALL OK（5 组 17 条：面板拆净 / 三件套在位 / Logo / 无限上下文口径 / 注册表 2 窗）
截图: assets/panels/console.webp（离线）、console-online.webp（本地服务，实时）
数据: caps.total=385 == 注册表；console-data.js 现读生成
对话实测: 两次同问，回答 100% 一致；ring seq 48 / db_turns 48 / window 12000
```

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
