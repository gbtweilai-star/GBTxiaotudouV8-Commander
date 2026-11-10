---
name: gsap-official
description: "GSAP 官方 Agent Skills（greensock/gsap-skills 原样安装，MIT © GreenSock）：gsap-core / timeline / ScrollTrigger / plugins / performance / react / frameworks / utils。当用户要求用 GSAP 做动画、时间线、滚动联动、React/Vue 接入时，先读这里再查 official/*.md。"
license: MIT
metadata:
  version: "1.0.0"
  source: "greensock/gsap-skills（MIT，© GreenSock）"
  installed: "2026-11-02"
---

# GSAP 官方技能（原样安装）

这些是 greensock/gsap-skills 仓库里的官方 SKILL.md **原文件**，放在 `official/` 下：

| 文件 | 讲什么 |
|---|---|
| `official/gsap-core.md` | tween/时间线基础、ease、stagger、响应式 |
| `official/gsap-timeline.md` | timeline、label、嵌套、控制 |
| `official/gsap-scrolltrigger.md` | 滚动联动、pin、scrub |
| `official/gsap-plugins.md` | 插件注册与常用插件 |
| `official/gsap-performance.md` | 性能与 `will-change`、transform 优先级 |
| `official/gsap-react.md` | React 里 useGSAP / 清理 |
| `official/gsap-frameworks.md` | Vue/Svelte 等接入 |
| `official/gsap-utils.md` | gsap.utils 工具箱 |

## 本项目里的既有资产
- 仓库里已 vendor：`assets/gsap.min.js`（原生页面可直接 `<script>` 引）；
- 已有蒸馏版 `skills/gsap/SKILL.md`（本仓自用速查）—— 两者不冲突：速查看蒸馏版，细节看 official/。

## 用之前先问三件事
1. 这段动效是不是**只用 CSS 就够**？够就别上 GSAP。
2. 它是不是**在表达状态变化**（执行到哪、哪一步亮）？不是就别加。
3. 有没有**清理**（组件卸载/页面切走时 kill 掉 tween/timeline）？没有就会泄漏。
