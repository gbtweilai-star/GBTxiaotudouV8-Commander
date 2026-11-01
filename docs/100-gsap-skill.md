# 100 · 把 GSAP 蒸馏成一个技能（不是搬 8 份原文）

> 主人 2026-11-01：「下一步」——上一轮把 Agent Skills 规范吸进来了，这一轮按规范**实战一次**：
> 把 [greensock/gsap-skills](https://github.com/greensock/gsap-skills) 的 8 个官方技能蒸馏成我们自己的 1 个。

## 一、蒸馏结果

| 项 | 值 |
|---|---|
| 技能名 | `gsap`（符合 Agent Skills：name=目录名、≤64、a-z0-9-） |
| 位置 | `skills/gsap/SKILL.md` + `references/upstream-map.md` |
| 覆盖 | 核心 tween / timeline 位置参数 / ScrollTrigger / React useGSAP / 插件注册 / 性能取舍 / 5 个高频坑 |
| 上游 | 8 个技能（gsap-core、timeline、scrolltrigger、react、plugins、performance、frameworks、utils）压缩成"何时用 + 最小片段 + 坑" |
| 许可 | MIT（© GreenSock），frontmatter `license: MIT`，不复制原文 |

## 二、为什么不是 8 个全搬

- 上游是**领域百科**（8 份共 ~1,300 行），我们只要"做法清单"；
- 8 个目录会带来 8 次匹配噪音（我们 `match` 是按技能名/描述打分）；
- 蒸馏后 `match("给面板加滚动动画")` → **gsap 3.2 分排第一**（实测），够用。

## 三、闭环验证（全部真跑）

```
skills_hub op=validate   → clean，23 个技能，0 errors（gsap 合规）
skills_hub op=list       → 23 个（含 gsap）
skills_hub op=match      → "给面板加滚动动画" → gsap(3.2) 第一
skills_hub op=pack       → state/tmp/skill-packs/gsap.zip（<名>/SKILL.md + references/）
skills_hub op=read       → references/upstream-map.md 829 字可读
skills_hub op=install    → dry_run 到 ~/.claude/skills/gsap（只演练，不写盘）
```

## 四、我们自己的使用口径

- 面板动效：`holo_pet_w3/` 静态页引入 GSAP；
- 验证不靠嘴：headless Chrome 截图前后对比（`assets/panels/*.webp` 就是这么来的）；
- 数字人舞台：只动 `transform/opacity`，不碰布局属性；
- 想再深入某一块时，按 `references/upstream-map.md` 回读对应上游技能，不预载全文。

## 五、顺带确立的一条规矩

**技能库的数字也有真源**：`skills_hub.op=list` 的 `count` = 现在 23。
以后任何文档写"多少个技能"，都以它为现读数（和 `cap_self op=docs` 对能力位是同一套纪律）。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
