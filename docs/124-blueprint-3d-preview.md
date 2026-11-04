# 124 · 蓝图 3D 立体呈现（成品预览页）

日期：2026-11-02 · 入口：http://127.0.0.1:8766/blueprint3d/ · 控制台左栏「成品预览」
截图：`outputs/screens-20261102/scene-final-1.png` / `-4` / `-8` / `-drawer.png`

## 它解决什么（主人的原话）
> 「以做出来什么样就是什么样的方式呈现」——不是示意图、不是摆设；不懂代码的人也能一眼看懂自己即将拿到什么，看完能随时改，改完她自己去做到完。

## 怎么做到「就是做出来那样」
- 展板里放的是**本机 8766 现跑出来的真实截图**（console 各视图 / 记忆 API 卡片 / 本页），不是效果图；
- 每页用一句人话说清「这是什么、你能拿它干嘛」：聊天窗口 / 它会做的事 / 能力星图 / 分工网络 / 任务指引 / 仪表盘 / 职业分工 / 这一页 / 它会记住的事；
- 页面往下滚 = 镜头穿过一页页成品（CSS 3D 景深 + GSAP 缓动），当前页在正前方，前后页退到景深里；
- 右上「打开实际页面 →」直接开真身；底部「提整改」随时写（不用懂代码），写进 `state/blueprints/<id>.revise.json`，落地前照改。

## 数据面（都是真数据）
| 面 | 来源 | 用途 |
|---|---|---|
| 模块清单/状态 | 页面内 9 个模块清单（每块对应真实页面/接口） | 已做好 8 / 9（本页在建） |
| 落地进度 | `GET /api/blueprint`（读 `state/blueprints/*`） | `落地清单 N / 16 项 · 下一步 …` |
| 记忆数字 | `GET /api/memory?op=stats` | 记忆卡显示 563 条 / 563 trigram / version 563 |
| 执行器 | `GET /api/omni`（omni_plug 万能插） | 顶部「她自己来」= 原生执行器在线 |
| 批准/自走 | `POST /api/blueprint {op:approve|land}` | 批准一次 → 后台跑到落地；只在 danger/transfer 才找主人 |
| 整改 | `POST /api/blueprint {op:revise|revise_ack}` | 记录/销项，不改代码也能提 |

## 万能插（原生执行器）实测
- `GET /api/omni?op=status` → `ok:true`，六类插座 process/file/api/web/app/ai；
- `?op=selftest` → `ok:true`：真起进程 `print(6*7)=42`、文件/URL 真探测、9 种端点拼接全对；
- `?op=sockets` → 已插 3 个（file/process/api）真探活；
- 门口径：process→process_execute · file写→filesystem_write · api→external_llm+data_export · web→app→desktop_control+privacy_read，未知 fail-closed。

## 怎么用
1. 打开 `/blueprint3d/`：滚轮往下 → 一页页看成品；
2. 不满意：点「提整改」写一句 → 提交；或点页签跳转；
3. 认可：点「批准开工」→ 再点「自动做到完」；进度实时反映在顶部「完成度/落地清单」，中途可继续提整改；
4. 拆解可见：`landing.state=running` 时每 1.5s 轮询，方块/清单随跑随亮。

## 技术落点
- 页面：`holo_pet_w3/blueprint3d/{index.html,bp3d.css,bp3d.js}` + `previews/*.png`（真实渲染图）；
- 数据/动效：`tools/console-server.py` 新增 `/api/blueprint`、`/api/omni`；GSAP 用本仓已 vendor 的 `assets/gsap.min.js`（没往 App 加依赖）；
- 设计：按已装的 tasteskill（app screen 规范：真数据、单一强调色、少装饰）+ 滚动场景（sticky stage / CSS 3D）实现；没引 CDN。

## 已知边界（如实）
- 模块清单是 9 项固定清单，落地任务（16 项）来自蓝图主链，两者是「成品面」和「施工单」两个视角，尚未自动对应；
- 截图是「当时真跑」的快照：UI 改完要重截（`outputs/screens-20261102/` → `blueprint3d/previews/`）；
- 自动跑到落地依赖 `state/blueprints/<id>.approved.json` 与安全能力位；危险/转账永远留票，不会自己越权。

## 试用台（2026-11-02 加）
主人：「如果能把落地方案进行类似试用的方式在里面使用一下就完美了」——加了「试用一下」，三个页签：

| 页签 | 干什么 | 走什么 | 实测 |
|---|---|---|---|
| 记忆 | 真写一句、再真查回来 | `POST /api/memory op=write` + `GET ?op=recall` | 写：版本 564（src=trial）→ 查「项目代号」：**1 条命中，覆盖率 1/1=100%** |
| 对话 | 直接问她一句 | `POST /api/chat`（真模型） | 「用一句话介绍你自己」→ **9500 ms** 真回答；超时会如实报，不编 |
| 看真页面 | 同源 iframe 打开真页面，可点可用 | `/console/index.html#…` | 功能表页面在 iframe 里可直接操作；可新窗口打开 |

入口：任意展板右下角「试用」按钮，或「提整改」旁边。真实写入会进统一记忆链（src=trial，可在 recall 里查到），不是假演示。
截图：`outputs/screens-20261102/try-memory.png`、`try-chat.png`、`try-page-wide.png`。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
