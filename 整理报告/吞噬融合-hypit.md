# 吞噬融合记录 · hypit（2026-11-01）

> 主人发来一条 TikTok：**Hypit —— Clone any viral video with AI agents**（"这个专门拆解爆款视频的 Skill"）。
> 指令：**把这个能力吞噬融合进 GBT天真**。

## 一、吞了什么（走万能插 `devour_github`，不是手抄 README）

| 项 | 读数 |
|---|---|
| 仓库 | [`hypit-ai/hypit`](https://github.com/hypit-ai/hypit) · **27,145★** · TypeScript · 3,117 fork |
| 定位 | "Clone any viral video with AI agents" · 1 command / 100 variants |
| 许可 | **Hypit Open Source License**（GitHub 标 NOASSERTION）⇒ **只吸收设计，不复制代码** |
| 吞噬回执 | `cap=devoured_hypit-ai_hypit` · `knowledge_chars=6,553` · `readme_chars=20,135` |
| 胶囊 | `gbt_allinone/store/devoured/devoured_hypit-ai_hypit/absorbed_knowledge.md` |

## 二、融合成什么（原生位 `viral_forge`，369 位）

| 吸收的设计 | 落地 |
|---|---|
| SVML 用语言描述视频 | `recipe` 用**词锚**（word anchor），不是秒锚 |
| 组件化（换人不动字幕） | `variant_slots`：host/product/language/hook_angle/broll/cta |
| 一套 composition 变 100 个 | `variants`：按 brief 生成 N 条模板钩子（纯模板，不调模型） |
| 可纯代码渲染、模型可选 | 本件零依赖纯计算；**不下载/不生成/不发布** |

能力：`status / teardown / blueprint / where`；输入 SRT/VTT/逐句稿，输出爆款拆解 + `viral_clone_v1` 配方 + 变体钩子。

## 三、为什么不是"照搬 Hypit"

- Hypit 是 TypeScript 全家桶（SVML 编译器 + 64 进程 Chromium 渲染 + 模型服务编排），**体量/依赖/许可**都不适合直接搬进 GBT 的零依赖原生位；
- 本仓要的是**可解释、可审计、可离线**：先做"拆解 + 配方"，成片交给已有 `edit_pipeline`/人工；
- 红线写进配方：**只用自有/授权素材、不复制原片画面音频、不自动发布、模型需授权**。

## 四、判据与同步

- `tests/test_viral_forge.py`：**ALL PASS**（SRT 解析/钩子/段落/CTA/配方/变体/红线/缺输入/未知 op）。
- 能力位 **368 → 369**；`cap_self verify` 369=369=369；`capability-audit` 仍 14/0（项数 +1）。
- 双仓同步：`two-way-sync verify` = **ALIGNED**（369/369）。

## 五、没做的（诚实）

- 不做原视频下载/解析画面、不做 AI 换脸/换声、不做自动发布、不复制原片内容；
- `video` 仅用 ffprobe 读时长；没有字幕就 `needs_input`；
- 变体钩子是模板，不是大模型创意。


## 六、融合台账（`devour_fusion` 现读）

- `intake hypit` → `status=待吞`（原生位 `viral_forge`，触手 `domain:creation`）。
- `audit hypit` → **未融合**：缺 **`atlas`**（`state/skill_atlas.json` 运行时图鉴未生成）与 **触手库永久记忆页**；原生位三处里注册表/api 已齐，只差图鉴。
- 诚实口径：**吞噬 + 蒸馏成原生位已完成；"三件齐"的融合还差运行时图鉴/记忆页**，这两件是运行数据生成器的事，不伪造台账。


## 七、视频帧分析（2026-11-01 补）

- `viral_forge` 新增 `op=analyze`（也支持 `teardown/blueprint` 带 `video`）：
  - **ffprobe**：时长/分辨率/fps/码率/音视频编码；
  - **ffmpeg**：`select='gt(scene,0.35)',showinfo` 场景切分 → `visual.cuts`；`volumedetect` → 音量；
  - 汇总 `shot_stats`：镜头数/首镜时长/平均镜头/每分钟切点。
- 只读：不写文件、不复制画面/音频；缺 ffmpeg/ffprobe 时 `needs_dependency`，绝不猜画面。
- 本机现状：已安装 **ffmpeg 9.0.2 essentials** 到工作区 `vendor/ffmpeg/bin/`（源码交付不含 vendor）；能力优先从 `vendor/ffmpeg/bin` / `GBT_FFMPEG` `GBT_FFPROBE` / PATH 找。实测 6 秒三色片：`cuts=[2.0, 4.0]` · `shots=3` · `first=2s` · `cuts/min=20` · `keyframes=[0.0, 2.0]` · 亮度均值 67.67 / 饱和度均值 96.67（经 live 唯一门 `run_task` 实跑）。
- 判据：`test_viral_forge` 新增 4 组解析器断言（showinfo/音量/镜头统计/缺依赖）**ALL PASS**。

## 八、一条链 + 工作流（本轮补）

- `op=pipeline`：一次调用串起 **analyze → teardown → recipe**；实测 `ok=true`，`chain` 如实三段。
- **切点对齐字幕**：`align=true` 按场景切点拆字幕；实测 cuts=2 → shots=3、每镜 caption 已对齐。
- **导帧**：`thumbs=true` 导出 `cover.jpg` + 关键帧 jpg 到 `outputs/viral-forge/<片名>/`；实测 3 张（6 秒片）。
- **DAG 工作流**：`爆款拆解流水线` = `analyze → pipeline → alerts`；`wf_run` 三节点 **全 ok（0.75s）**；`sched_define` 每天 86400s；`sched_tick` 首跑 **status=ok**（run_id 已落 state/wf_runs）。
- **心跳共用**：`sync-guard-patrol.ps1` 巡检后自动 `sched_tick`；GBT-SyncGuard 每 6h + 登录启动项驱动；实测 `sched: {ran: [], count: 0}`（无到期项），`sched_status` 两条调度 last_status=ok。
- **inbox 目录投放（本轮补）**：`outputs/viral-forge/inbox/` 丢视频（同名 srt/vtt 自动用），`op=inbox` 自动拆；实测处理 2 条：报告 `reports/test-viral.md/.json`、`test-viral2.md/.json` + 缩略图 + `state/viral_forge_done.json` 台账；工作流 `爆款拆解流水线` 改为 `inbox → alerts`，`wf_run` 两节点全 ok。
- **无人登录（备好）**：`tools/setup-system-task.ps1` 管理员运行 → `GBT-SyncGuard-System`（SYSTEM/开机/6h）；非管理员只打印提权命令。
- 边界不变：只读本地视频、只写 outputs 缩略图；不下载/不复制/不发布。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
