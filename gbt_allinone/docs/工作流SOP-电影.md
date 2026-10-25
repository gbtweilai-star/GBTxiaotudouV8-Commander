# 工作流 SOP · AI 电影（初学到专业）

> 口径取自 `media_pipeline.MEDIA_KNOWLEDGE["film"]` · `media_run.CHAINS["film"]` · `drama` R1–R5 ·
> `projects/film/_intel/forbidden_lists.md`。

## 1. 目标与交付标准

- **目标**：用**连续**的角色、空间、声音与因果，构建可持续观看的长叙事。
- **质量**：角色与场景连续 · 台词与口型可接受 · 镜头无闪烁崩坏 · 声画同步 · 章节转折清晰 · 版权与人物授权完整。
- **指标**：章节留存 · 平均观看时长 · 单分钟成本 · 二次观看率 · 项目净收益。

## 2. 六步链

| 步 | 谁做 | 判据 | 产物 |
|---|---|---|---|
| `concept` | **人/模型** | 主题·**欲望**·**阻力**·**变化**四件齐 · 目标观众 · **受众证据**（只有结论没依据＝没证据）· **成本上限**（「待定」不算） | `01-screenplay/…-01concept.md` |
| `script` | **人/模型** | 同 `drama` R1/R3；缺字段**留空**，不许拿默认值顶上 | `01-screenplay/…-02script.md` |
| `shots` | **机器** `ffmpeg` | 时长取脚本 total_dur | `03-shoot/…-03shots.mp4` |
| `sound` | **机器** `audio_mix` | 和声垫时长**对齐镜头** | `04-assets/…-04sound.wav` |
| `edit` | **机器** `edit_pipeline` | 时间线校验 · 素材真时长 | `05-edit/…-05edit.mp4` |
| `export` | **机器** `copy.of_edit` | 非空 | `06-final/…-06export.mp4` |
| `publish` | 停在授权门 | 只到 `prepared` | `_shared/publish/` |

## 3. 初学 → 专业

**L1**：先会写**一句话立意（logline）**；一场戏只做一件事（信息变或关系变，二者至少有一）。
**L2**：会给角色建**连续性护照**（形象/声音/服饰/场景），会排场次表并核对时长总和；
会用「每场戏必须改变信息或关系」当删除线剪场。
**L3**：把声音当叙事元素而不是伴奏（先定声音意图，再定画面）；用**章节留存**定位崩点；
连续性交独立审计，**角色一致性不自己判**；成本按单分钟核算并设上限。

## 4. 硬判据

`concept`：四件 + 观众 + 证据 + 数字成本上限（`_validate_concept`，判据取自 `craft[0]` + `COMMON_GATES` 头两道）。
`script`：`drama.parse_timed` R1/R3。
`sound`/`shots`/`edit`：时长一致性 + 非空 + 无 `_*` 残留。

## 5. 红线

同三方向共用 7 条 + 电影专属：连续性不许断（角色/场景）· 不许拿未授权的真人形象做角色 ·
**不许用「大致对得上」代替声画同步的量测**。

## 6. 执行卡

```
py -3.14 tools/codex-scripts/five-dim.py cap media_run '{"op":"template","kind":"film","step":"concept","work":"<作品>"}'
py -3.14 tools/codex-scripts/five-dim.py cap media_run '{"op":"run","kind":"film","work":"<作品>","release":true}'
```

## 7. 已知边界

- `concept` 与 `script` **共用** `01-screenplay` 一格，而闸门把该格映射到 `script` ⇒
  历史上出现过「两步都看不见同一件真成品」。命名务必带**唯一工序词**（`01concept` / `02script`）。
- 同短视频：无 AI 出片端，画面是设计字卡。

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
