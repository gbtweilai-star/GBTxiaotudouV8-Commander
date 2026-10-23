# 工作流 SOP · AI 短视频（初学到专业）

> 本件把她自己的**短视频工作流**一次讲全：目标 → 五步链 → 三档进阶 → 硬判据 → 红线 → 执行卡。
> 口径**全部取自仓内契约**（`media_pipeline.MEDIA_KNOWLEDGE` · `media_run.CHAINS` · `drama` R1–R5 ·
> `video-pipeline` 分镜契约 · `projects/short-video/_intel/forbidden_lists.md`），**不另立一套**。

## 1. 目标与交付标准

- **目标**：在最短时间内建立注意力、交付**单一**明确价值并引导可归因行动。
- **质量**（机读项）：首屏可读 · 无黑帧/静音段 · 字幕不遮主体 · 音量与峰值稳定 · 素材授权可追溯。
- **指标**：前 3 秒留存 · 完播率 · 有效播放成本 · 转化率 · 净收益。

## 2. 五步链（步 → 谁做 → 判据 → 产物）

| 步 | 谁做 | 判据（机器） | 产物 |
|---|---|---|---|
| `script` | **人/模型**（输入口） | `drama.parse_timed` R1 六字段+字面检出 · R3 Σ时=末镜 t1（±0.05s）· R4 过短拒 | `01-script/<日期>-short-video-<作品>-01script.md` |
| `storyboard` | **人**（输入口） | 分镜四层 `render/eyeline/depth/reason` · 静帧 ≤8s · `share_text` 不得是「求转发」 · `att_copyright/att_safety/att_owner` 三条签署 | `02-storyboard/…-02storyboard.json` |
| `assets` | **机器** `ffmpeg` | 由**脚本 total_dur** 定时长；烧标题 + 逐镜字幕 | `03-raw/…-03assets.mp4` |
| `edit` | **机器** `edit_pipeline` | 时间线校验通过 · 素材真时长 | `04-cut/…-04edit.mp4` |
| `export` | **机器** `copy.of_edit` | 非空 | `05-publish/…-05export.mp4` |
| `publish` | **停在授权门** | 只到 `prepared`，`submit` **恒 blocked** | `_shared/publish/*.json` |

## 3. 初学 → 专业（三档）

**L1 上手**：会写定时分镜稿（`0s – 6s（小标题）` + 每镜正文含**景别·运镜·情绪**各一个词）。
把三样东西当硬约束而不是建议：① 首 3 秒必须有冲突或收益承诺；② 每镜只承载一个信息；③ 字幕不遮主体。

**L2 熟练**：会填**分镜契约**——逐镜写 `render`（渲染路由）与 `reason`（**为什么这么选**；抄别人的理由＝失败），
会按「同地点/同时间变化 → 优先 dip」选转场，会算预算闸，会签 HITL#1 三条（版权/安全/主人）。

**L3 专业**：把「术」换成「判」——
- 用 `metrics`（前 3 秒留存/完播/有效播放成本）反推脚本结构，而不是凭手感改片；
- 每一版改动只动一个变量，留一版对照；
- 素材许可**逐件**登记（`media_license register`），没有许可的素材**不许进成品格**；
- 交付前跑独立 checker，**自己不当自己的裁判**。

## 4. 硬判据清单（红了就是没做完）

1. 每镜**字面出现**景别/运镜/情绪三类词（`drama._SIZE_MAP/_CAM_MAP/_EMO_MAP`）。
2. 时间码连续且 Σ = 末镜 `t1`（R3）。
3. 分镜 `style` 非空（没有风格的分镜板一律打回）。
4. `share_text` 不是「求转发/求关注/求三连」这类**请求**（可转发物是一句能原样转出去的话）。
5. `att_*` 三条签署齐全（HITL#1）。
6. 成片非空 · 时长与脚本一致 · 无 `_*` 残留。

## 5. 绝对红线（摘自 `_intel/forbidden_lists.md`）

第三方版权素材不许进成品 · 真人肖像/声纹无可追溯授权不许用 · 不得留明文凭据 ·
发布不得绕授权门 · **不许把「没量到」念成「通过」** · 判据里的数字必须有量测步骤 · 不编造出处。

## 6. 执行卡

```
py -3.14 -X utf8 tools/codex-scripts/five-dim.py cap media_run '{"op":"plan","kind":"short_video"}'
py -3.14 tools/codex-scripts/five-dim.py cap media_run '{"op":"template","kind":"short_video","step":"script","work":"<作品>"}'
# 把填好的真件放进 projects/short-video/01-script/ 与 02-storyboard/，再：
py -3.14 tools/codex-scripts/five-dim.py cap media_run '{"op":"run","kind":"short_video","work":"<作品>","release":true}'
```

## 7. 已知边界（诚实）

- `assets` 步当前用**本机 ffmpeg 自产**（渐变底 + 烧字幕）：**没有接 AI 出图/出片端**，
  所以画面是**设计过的字卡**，不是场景渲染。要真画面须接生成端（本机 ComfyUI 未运行 / 无出网密钥）。
- 确定性路径**不产出「角色位置」**（`drama` 源码写死不猜）⇒ `verdict.complete` 恒 false，判据只压在它能负责的三项上。

## 8. 灯光 · 调色 · 精修（2026-10-09 接进链）

`edit` 步之后**真的过一遍共用外观库**（`tools/filmgrade.py`，此前三方向链一次都没调过它）：

- **灯光/调色**：`pick(style)` **人话取味**（实测：「…冷…」→ 潮湿阴冷）。链 = colorbalance + eq + curves
  + cas 锐化 + gblur/blend 辉光 + vignette 暗角 + noise 颗粒 —— 是**真调色**，不是贴标签。
- **精修五科目**逐项读数（每项 boolean/数值，**不报合计**）：锐化(cas) · 辉光(bloom) · 暗角(vignette) ·
  颗粒(grain=N) · 对比曲线(curves) · 色平衡(colorbalance)。
- **交付 QC**：`filmgrade.qc` 出 `black / freeze / yavg / verdict` ——
  🔴 实测它照出了合计视角看不见的东西：`verdict=不通过 · black=1 · freeze=3`。
  即「看着完成」不等于「过得去」；**这一关必须接**。

## 9. 集间首尾相连（主人令 2026-10-09：每一集首尾相连对齐）

- 命名走系列集：`<系列>-epNN`（如 `醒来-ep01` / `醒来-ep02`）。
- **第 N+1 集首镜的调色 = 第 N 集尾镜的调色**：渲染完把尾镜调色落 `.scratch/_media_run_series.json`，
  下一集读它当 `anchor`（`head_palette` 直接继承，`anchored=True`）。
- 集内/集间一律**硬切**；只有整部系列的**首集**才淡入（`fade_in=True`）。
- 实测：`ep01 tail=[0x0A1018,0x22303F]` → `ep02 head=[0x0A1018,0x22303F]`，`anchored=True`。

## 10. 习惯 · 逐步细节化（每一步都要细节化）

每一步（含红步与发布步）都要答满**五问**：**输入 · 动作 · 明细 · 判据 · 接点**；
其中**「明细」必须是逐项列表**（给一个合计数字 = 没细节）。
判据件：`tools/codex-scripts/detail-check.py`（`--selftest` 6 例：正例 1 + 负例 5）。
口径全文：`gbt_allinone/docs/习惯-逐步细节化.md`。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
