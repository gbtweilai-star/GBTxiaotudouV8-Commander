# 工作流 SOP · AI 音乐（初学到专业）

> 口径取自 `media_pipeline.MEDIA_KNOWLEDGE["music"]` · `media_run.CHAINS["music"]` · `_validate_lyrics` ·
> `_validate_arrangement` · `music-production`（§1 溯源 / §2 十三闸 / §3 生成前闸 / §4 QC）·
> `projects/music/_intel/forbidden_lists.md`。

## 1. 目标与交付标准

- **目标**：创作具有明确情绪、记忆点、结构与**可商业交付版权链**的音乐。
- **质量**：无爆音/削波/异常噪声 · 响度与真峰值合格 · 人声可懂度 · 段落动态有对比 · 样本/声纹/旋律来源可追溯。
- **指标**：完整收听率 · 收藏率 · 授权转化 · 单曲制作成本 · 版权净收益。

## 2. 五步链

| 步 | 谁做 | 判据 | 产物 |
|---|---|---|---|
| `lyrics` | **人/模型** | 十三项歌词闸逐条自查（押韵·韵律·发音风险·视角一致·事实准确…）· 生成前四闸（来源已核验/标志位/风格提示词/**艺人名已清**） | `01-lyrics/…-01lyrics.md` |
| `arrangement` | **人**（DAW/MIDI 工程件） | 本机**只判 `.mid`**：`MThd` 头 · 可解析 · **写了 tempo** · **写了调号** · 有音符 · 读出通道/音色 · ≥8 音符 | `03-arrange/…-02arrangement.mid` |
| `audio` | **机器** | 有 `.mid` ⇒ **真渲染编曲**（numpy 合成） | `04-mix/…-03audio.wav` |
| `master` | **机器** `audio_mix.master` | 两遍法 loudnorm（先量后施加） | `05-master/…-04master.wav` |
| `export` | **机器** | 非空 | `06-release/…-05export.flac` |
| `publish` | 停在授权门 | 只到 `prepared` | `_shared/publish/` |

## 3. 初学 → 专业

**L1**：先把「情绪曲线 + 速度 + 调性 + 参考边界」四样说明白，再动笔。副歌只做一件事：给一个可记住的动机。
**L2**：会写**韵脚方案**与**段落结构**；会给难念字写**音标修正建议**（不是打回了事）；
会自查十三闸，且**上游没列全的项如实写「未判」，不许编判据、不许写「通过」**。
**L3**：把数字变成量测——韵律写「**实测逐行非空白字数**：min/max/均值」并写清**怎么量的**；
编曲按目标平台定动态预算（streaming −14 / podcast −16 / broadcast −23 / cinema −27 LUFS）；
母带用两遍法并把四个测量值随结果返回；版权链（样本/声纹/旋律来源）逐条可追溯。

## 4. 硬判据

- 歌词：`_validate_lyrics` 十三闸表存在且结论**逐条**给出。
- 编曲 `.mid`：A1 `MThd` · A2 可解析 · A3 **tempo 事件**（没有 tempo ⇒ 只是规范默认 120，不算写了）·
  A4 **key signature**（没有就进 missing，**不许替你猜调**）· A5 有音符 · A6 读出通道/音色 · A7 ≥8 音符。
- QC（§4）：响度/削波/静音/相位/立体声宽度/频谱/动态范围 —— **没有真音频时七项全标「未判」**。

## 5. 红线

共用 7 条 + 音乐专属：纪实类**先核验后作词**（每条主张可追到已捕获来源；虚构类须如实标「不适用」）·
艺人名必须清 · 削波不允许、相位不许反相抵消 · 响度按目标平台对齐。

## 6. 执行卡

```
py -3.14 tools/codex-scripts/five-dim.py cap media_run '{"op":"template","kind":"music","step":"lyrics","work":"<作品>"}'
# 放好 01lyrics.md 与 02arrangement.mid（真 DAW/MIDI 工程件），再：
py -3.14 tools/codex-scripts/five-dim.py cap media_run '{"op":"run","kind":"music","work":"<作品>","release":true}'
```

## 7. 已知边界

- `arrangement` 只判得动 `.mid`；`.als`/`.flp` 如实标 `input_unjudged`（**判不了 ≠ 合格，也不等于不合格**）。
- 本机**无 GPU 演唱端**：人声需云路线（出网 + 可能计费）或带 GPU 的机器；
  当前 `audio` 步渲染的是**器乐编曲**，人声轨留空。

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
