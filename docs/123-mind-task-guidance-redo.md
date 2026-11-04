# 123 · 思维导图任务指引重做（意图 → 精细步骤 → 卡点回路 + 执行态特效）

日期：2026-11-02 · 参考：主人给的霓虹 HUD 图（橙/青光纤束、发光环节点、玻璃面板、浮动气泡、六边形地面）
截图：`outputs/screens-20261102/mind-final2-default.png`、`mind-final2-progress.png`、`mind-final2-blocker.png`

## 先装了技能（装给我自己，不是装进 App）
| 技能 | 来源 | 落地位置 |
|---|---|---|
| tasteskill v2（anti-slop 前端） | github.com/Leonxlnx/taste-skill（MIT） | `skills/taste-skill/`：SKILL.md + 13 篇 references + 10 个 library json + 6 个 scripts |
| GSAP 官方 8 个 Agent Skills | github.com/greensock/gsap-skills（MIT © GreenSock） | `skills/gsap-official/official/*.md`（原样）+ `skills/gsap-official/SKILL.md`（索引） |

没有往 App 里加任何 npm 依赖：页面用的是仓库里早就 vendor 的 `holo_pet_w3/assets/gsap.min.js`（72 KB），只在 index.html 多一行 `<script>`。

## 按 taste skill 改了什么（app screen 口径）
- **颜色收成一个强调色**：琥珀 `#ffb02e` 只给"已执行/正在执行"；未执行=灰 `#46536a`；卡点=红 `#d2453f`。去掉原来的绿/青/金三套状态色。
- **进度是真的，不是装饰**：命令条 `4 / 8` + 8 段进度条；3D 大面板的柱子按真实状态重画（灰矮 / 琥珀高 / 红），脚注 `已开始 4 / 8 步 · 完成 3`。
- **排版层级只留两级**：卡片标题 600/38px，正文 400/27px；HTML 详情面板 h3 13px + 行标签 11px + 正文 12px，去掉一堆同权重小字。
- **面板扁平化**：命令条/详情面板改为实色 `#0a1420` + 1px 边 `#1d3247`，去掉 backdrop-blur 玻璃；发光只留给"在执行的节点"（状态语义）。
- **详情面板结构化**：做法 / 判定 / 卡点 / 备用 四行固定列，不再是一段话堆着。

## 特效：执行到哪里亮哪里
- **未执行**：节点灰环、卡片灰、光缆暗灰、进度段空 —— 一眼能看出"还没做"。
- **执行中**：节点琥珀脉冲（scale/glow 呼吸）、卡片变白、对应光缆点亮、进度段描边。
- **已完成**：节点/线/卡片转琥珀实色，进度段实心。
- **卡点**：该步变红并保持闪烁，卡点回路（卡点→回大脑执行层→核心论文/资料→吸收→重生成）画出来；详情面板抖一下（GSAP），状态写明备用通道。
- **GSAP 只做 UI 微动效**：详情面板入场、进度段 pop、进度数字闪一下、卡点抖动；无 GSAP 时全部有降级（直接设值）。

## 交互与验证
- 命令条：输入任务 → 生成指引 → 推进（第 1 次点亮第 1 步；再按完成并推进）→ 标卡点 → 继续推进；可选"模型生成"走 `/api/chat`，失败如实回退离线模板。
- 标记：`data-mindmap`（`ok:6支+18叶` / `plan:意图:N步:offline|model`）、`data-mindmapProgress`、`data-mindmapStep`、`data-mindmapBlocker`。
- 默认仍是框架六步（18 条动作），点分支节点看 3 条动作；输入"帮我注册一个邮箱"得到 8 步精细步骤（选服务商→注册入口→填写→验证码→条款→测试邮件→2FA→留痕）。

## 已知可继续
- 其它视图（星图/大脑/万能插/协作）还是各自风格；要统一成同一套 token 需要再来一轮。
- 3D 卡点回路三张卡在窄屏会挤；移动端要降点数。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
