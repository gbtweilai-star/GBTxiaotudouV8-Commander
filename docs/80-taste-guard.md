# 80 · 反-slop 设计闸（taste_guard）

> 来源：主人 2026-11-01 看到 **Taste Skill — The anti-slop frontend framework for AI agents**（`Leonxlnx/taste-skill`，MIT）后说「来继续让天真把这个吞噬了」。
> 本页是**蒸馏记录 + 本机原生位契约**：只蒸规则与检查口径，不搬上游代码/素材。

## 一、上游是什么（读数）

| 项 | 读数 |
|---|---|
| 仓库 | `Leonxlnx/taste-skill` · MIT · Copyright (c) 2026 Leonxlnx |
| 技能名 | `design-taste-frontend`（v2 / v2.1） |
| 方法 | 247 个精选站研究；脚本发 3 个方向 → 选 1 → 从题材找 idea → 真图/真界面 → Chrome 三宽度量 → 看截图修 3 轮 |
| 上游门槛 | Node 22+、Chrome/Edge/Chromium；不装依赖、无 API key；取图需网络 |
| 上游资产 | `library/`（directions/heroes/sections/type/palettes/photos/sites…）、`scripts/`（draw/assets/inspect/lint/scenes）、`assets/`（base.css/scenes/app/charts） |

## 二、天真吞了什么

本机原生位 **`taste_guard`**（creation，纯读，不写盘）：

| op | 作用 |
|---|---|
| `status` | 能力位/上游/未实现项/未检查项 |
| `rules` | **18 条** house rules（id/sev/rule/instead） |
| `audit` | 静态扫 HTML/CSS：渐变、玻璃、阴影、眉标大写、等宽、编号、图标卡阵、emoji、紫靛/奶油赭石、lorem、无 h1、真图不足、字体过多、动效不足；FAIL/WARN + 分数 |
| `brief` | 一次构建的硬约束（一底一墨一强调、两行标题、每节有题、真图 ≥4、动效 ≥8…） |
| `where` | 入口 |

判据：`tests/test_taste_guard.py` —— 干净页 PASS、烂大街页抓 8 类 FAIL、brief/边界 —— **ALL PASS**。

## 三、上游规则里最狠的 18 条（摘要）

- 标题最多两行（任何宽度）；首屏一个 `h1`，每节有标题；
- 无眉标/胶囊/New 标签；无渐变；无玻璃；静止元素无阴影/发光；
- 真代码块外无等宽；无 01/02 编号；无发丝线；无小字距大写标签；
- 无图标顶卡阵/同款卡片排；无 emoji/渐变球/灰条假仪表盘；
- 无紫靛“AI 助手色”、无奶油+赭石；标题里无单独变色/斜体/衬线重点词；
- 最多两种字体；真实图片 ≥4（SVG 不算）；动效元素 ≥8；无 lorem/占位。

## 四、没有冒充的部分（诚实）

- 上游 `inspect.mjs` 已吞进 `vendor/taste-skill/`，用本机 **Node v26 + Edge** 真跑（1440/768/390 三宽度，截图落 `outputs/taste-guard/`）；`deep_audit` 不是模拟。
- 本件 `not_implemented`：截图陪审/看片修片循环（人判）、`assets.mjs` 开放图库取图、`draw.mjs` 方向发牌库。
- 本件 `not_checked`：主观评审/评分、每节构图的人判；渲染数字由 `deep_audit` 量，静态 PASS 仍不等于真浏览器 PASS。
- 上游 `library/` 与 `assets/` 未搬；只蒸规则和口径。上游是 MIT，若后续要搬代码/素材，按 MIT 保留版权与许可声明。


## 五、真浏览器闸（deep_audit，已吞上游 inspect.mjs）

```python
run_task("taste_guard", {"op":"deep_audit","path":"holo_pet_w3/index.html"})
```
- Node v26 + Edge，三宽度 1440/768/390；产物 `outputs/taste-guard/inspect-*/report.json` + 截图；
- 实测 `holo_pet_w3/index.html`：**19 findings = 10 FAIL / 9 WARN**（no-title、few-pictures、blank-gap、edge-text、still-page、empty-screens、mono、shadow、text-shadow、hairline…），exit=1；
- 这就是上游说的“量出来才知道烂在哪”；`PASS` 也还不等于好看，最后仍要人看截图。
 
## 六、实测修复（2026-11-01）

- 修前：`holo_pet_w3/index.html` **10 FAIL / 9 WARN**（无 h1、0 张真图、首屏被 `.gbt-view` 绝对定位盖住、阴影/发丝线/等宽/贴边）。
- 修后：**PASS · 0 FAIL / 2 WARN · 94 分**；标题 1–2 行、真实图 5、边距 25/25、贴边 0、动效元素 17、体积填充 0.35–0.73。
- 改动只在 `holo_pet_w3/`：`index.html` + `taste-fix.css` + `taste-fix.js` + 4 张本地成片帧；明细 `整理报告/taste-guard-修复.md`。
- 剩余 WARN：字号 10 档、h1 名字式短句（非 FAIL，未强行清零）。
 > 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
