# 爆款拆解·克隆配方（viral_forge）

> 2026-11-01 · 吸收 `hypit-ai/hypit`（27,145★ · TypeScript · "Clone any viral video with AI agents"）的**设计**，
> 蒸馏成 GBT天真原生位 `viral_forge`。**未复制其代码**；只吞了 README/元数据 + 架构思想。

## 一、从 Hypit 吸收了什么（只吸收设计）

| Hypit 的做法 | GBT天真 的对应 |
|---|---|
| **SVML**：用语言描述视频，而不是时间线 | `recipe` 用**词锚**（caption/word）而不是秒锚 |
| **组件化**：换主持不动字幕，换产品不动结构 | `variant_slots`（host/product/language/hook_angle/broll/cta） |
| **一变多**：一套 composition 生成 100 个变体 | `variants`：按 brief 生成 N 条模板钩子 |
| **可选模型**：可以纯代码渲染、不调生成模型 | 本件纯计算零依赖；**不调模型、不生成素材** |
| Agent Skill 入口 | 本仓原生能力位（唯一门 `run_task`） |

**没吸收**：不下载/缓存视频、不做 AI 换脸/换声、不自动发布、不复制原画面/音频。

## 二、契约

| op | 作用 |
|---|---|
| `status` | 只读：输入/输出/边界/红线 |
| `teardown` | 字幕/逐句稿 → 拆解读数 + 配方 |
| `blueprint` | 同上，主交付 recipe + variants |
| `where` | 入口与调用例 |

输入：`text`（SRT/VTT）或 `cues:[{start,end,text}]`；可选 `duration`、`brief{product,audience,pain,promise,twist}`、`variants`、`video`（仅 ffprobe 读时长）。
输出：`reading`（时长/语速/黄金 3 秒钩子/钩子类型/每 5 秒节奏/段落角色/CTA）· `recipe`（`viral_clone_v1` 场景表 + 变体槽位 + 红线）· `variants`（模板钩子，不是模型生成）。

```python
api.run_task("viral_forge", {
  "op": "teardown", "text": srt, "duration": 18,
  "brief": {"product": "百元耳机", "audience": "学生", "pain": "预算低", "promise": "千元音质"},
  "variants": 3,
})
```

## 三、红线（写进 `recipe.guardrails`，不可删）

1. 只用**自有或已授权**素材；
2. **不复制**原视频画面/音频；
3. **不自动发布**；
4. 模型调用需主人授权；
5. **结构复刻 ≠ 内容抄袭**。

## 三·五、视频帧分析（可选，需 ffmpeg/ffprobe）

- `op=analyze` 或 `teardown/blueprint` 带 `video`：用 **ffprobe** 读时长/分辨率/fps/码率，用 **ffmpeg** 做
  `select='gt(scene,0.35)',showinfo` 场景切分 + `signalstats` 亮度/饱和度 + `volumedetect` 音量 + I 帧关键帧；
  输出 `visual.cuts`、`shot_stats`（镜头数/首镜时长/平均镜头/每分钟切点）、`keyframes_s`、`color`（yavg/satavg）、`loudness`。
- 只读：不写文件、不复制画面/音频；缺 ffmpeg/ffprobe 时 `needs_dependency`，绝不猜画面。
- 仅有视频、无字幕时也可做**纯视觉拆解**（段落无 caption）；字幕 + 视频都给时两者合并。
- 本机现状：已把 **ffmpeg 9.0.2 essentials** 放到工作区 `vendor/ffmpeg/bin/`（不在源码交付内）；能力优先从 `vendor/ffmpeg/bin`、`GBT_FFMPEG/GBT_FFPROBE`、PATH 找。实测 6 秒三色测试片：cuts=[2.0,4.0] · shots=3 · cuts/min=20 · keyframes=[0.0,2.0] · 亮度均值 67.67 / 饱和度均值 96.67。
## 三·六、一条链：analyze → teardown → recipe（`pipeline`）

- `op=pipeline`：一次调用返回 `{analysis, forge}`——`analysis` 是视频帧分析，`forge` 是拆解+配方+变体；`chain` 字段写明三段。
- 项目工作流：`wf_define` 定义 `爆款拆解流水线`（analyze → pipeline → alerts），`sched_define` 每天跑一次；**心跳源** = `tools\sync-guard-patrol.ps1`（GBT-SyncGuard 每 6h / 登录自启）巡检后自动 `sched_tick`，到期即执行——**示例**：
  ```python
  nodes = [
    {"id": "analyze", "kind": "viral_forge", "params": {"op": "analyze", "video": "D:/clip.mp4"}},
    {"id": "forge", "kind": "viral_forge", "params": {"op": "pipeline", "video": "D:/clip.mp4", "text": srt, "thumbs": True, "align": True}, "depends_on": ["analyze"]},
    {"id": "voice", "kind": "alerts", "params": {}, "depends_on": ["forge"]},
  ]
  ```
- 切点对齐字幕：`align=true`（默认）把跨场景切点的字幕按字符比例拆开，起始/结束对齐切点；`reading.shots` 给每镜的 caption。
- 导帧：`thumbs=true` → `outputs/viral-forge/<片名>/cover.jpg` + 每镜关键帧 jpg（只写 outputs，不写源码）；`op=frames` 可单独导。
## 三·七、目录投放（inbox）：不写代码也能拆

- 把视频丢进 **`outputs/viral-forge/inbox/`**（mp4/mov/mkv/webm/avi），同目录放同名 `.srt`/`.vtt` 会一起用；
- `op=inbox` 取最新一个未拆的：分析 + 拆解 + 配方 + 导帧 + 写报告；
- 报告落 **`outputs/viral-forge/reports/<片名>.md` + `.json`**；已拆台账 `state/viral_forge_done.json`；
- `op=batch` 一次拆多个（`limit` 控制）；目录空 → `status=empty`，不报错；
- 心跳：GBT-SyncGuard 每 6h / 登录自启 → patrol 后 `sched_tick` → 到期工作流 `爆款拆解流水线`（inbox）自动跑。
## 四、诚实边界

- 本件只做**结构分析 + 配方生成**；成片仍需 `edit_pipeline`/人工按配方制作。
- 没有字幕就没有拆解（`needs_input`）；不靠猜。
- `video` 只读时长；ffprobe 不在就如实 `needs_dependency`，不回退去猜。
- 变体钩子是**模板**，不是大模型生成——不冒充创意。

## 五、判据

`tests/test_viral_forge.py`：SRT 解析 / 钩子抓到 / 段落角色 / CTA / 配方格式 / 变体数 / 红线 / 缺输入 / 未知 op **ALL PASS**。
现读能力位总数见 `cap_self verify`（368 → **369**）。


## 六、实测读数（2026-11-01）

- 测试片：6 秒三色（红/蓝/绿），320×240@15fps。
- `analyze`：cuts=[2.0,4.0] · shots=3 · first=2s · avg=2s · cuts/min=20 · keyframes=[0.0,2.0] · 亮度 mean 67.67（41–81）· 饱和度 mean 96.67。
- `teardown`（视频+字幕，align=true, thumbs=true）：mode=video+subtitles · alignment cuts=2 · shots=3 · **导帧 3 张**（cover + 2 关键帧，落 `outputs/viral-forge/test-viral_mp4/`）。
- `pipeline`：ok=true · chain=["analyze","teardown","recipe"]。
- 工作流 `爆款拆解流水线`（analyze→pipeline→alerts）：`wf_run` 三节点全 ok（0.75s，缓存命中）· `sched_define` 86400s · `sched_tick` 首跑 **status=ok**。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
