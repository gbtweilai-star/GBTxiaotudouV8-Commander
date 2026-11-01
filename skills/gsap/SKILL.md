---
name: gsap
description: "在网页/面板/数字人界面里用 GSAP 做动画时的做法：何时该用 GSAP、timeline 序列、ScrollTrigger 滚动联动、React/Vue 里的接入与清理、插件注册、性能取舍、常见坑。当用户说「加动画 / 页面动效 / 滚动动画 / 视差 / 时间线 / GSAP / ScrollTrigger / 数字人面板动效 / 转场」时使用。边界：只讲怎么用 GSAP 把动效做对，不替用户选框架（React/Vue/原生都行）；纯 CSS 能搞定的小动效不硬上 GSAP。"
license: MIT
metadata:
  version: "1.0.0"
  source: "greensock/gsap-skills（MIT，© GreenSock）+ agentskills.io 规范"
  distilled: "2026-11-01"
---

# GSAP：把动效做对的固定套路（蒸馏版）

> 本技能由 [greensock/gsap-skills](https://github.com/greensock/gsap-skills) 的 8 个官方技能**蒸馏**而来：
> 只保留"何时用 + 关键 API + 坑"，不复制原文；上游是 MIT，版权归 GreenSock。

## 何时用

- 要做**序列/编排**（多个元素按顺序或并行）；
- 要**滚动联动**（元素随滚动触发、pin、scrub）；
- 要**框架无关**的动画库（React/Vue/Svelte/原生都行）；
- 要 timeline、easing、stagger、SVG、拖拽、Flip、文本拆分。

**不硬上**：一次性 hover、简单 transition 用 CSS 就够——GSAP 是给"要编排"的场景。

## 五条主配方

### 1) 核心 tween（gsap-core）
```javascript
gsap.to(".box", { x: 100, duration: 1, ease: "power2.out" });        // 到
gsap.from(".item", { opacity: 0, y: 20, stagger: 0.1 });             // 从
gsap.fromTo(".a", { x: 0 }, { x: 100, duration: 0.6 });              // 从→到
gsap.set(".b", { autoAlpha: 0 });                                     // 立即设（autoAlpha 含 visibility 成本低）
```
- 位置动画用 `x/y`（transform），不要用 `left/top`；
- `autoAlpha` 比 `opacity` 多管理 visibility，隐藏元素更省渲染；
- 响应式/减少动效：`gsap.matchMedia()` + `prefers-reduced-motion`。

### 2) Timeline 序列（gsap-timeline）
```javascript
const tl = gsap.timeline({ defaults: { duration: 0.5, ease: "power1.out" } });
tl.to(".a", { x: 100 })            // 默认接在末尾
  .to(".b", { y: 50 }, "<")        // 与上一个同时开始
  .to(".c", { opacity: 0 }, "+=0.2"); // 上一个结束再 0.2s
const tl2 = gsap.timeline({ repeat: -1, yoyo: true });   // 循环往复
```
位置参数：`0`（绝对）/ `"+=0.5"`（结尾后）/ `"<"`（同上一个开始）/ `">"`（同上一个结束）/ `"label"`。

### 3) ScrollTrigger（gsap-scrolltrigger）
```javascript
gsap.registerPlugin(ScrollTrigger);
gsap.to(".box", {
  x: 500,
  scrollTrigger: {
    trigger: ".box",
    start: "top center",
    end: "bottom center",
    scrub: true,                     // 跟随滚动
    pin: true,                       // 钉住
    toggleActions: "play reverse play reverse"
  }
});
```
- 布局变了要 `ScrollTrigger.refresh()`；
- start/end 用 `"clamp(...)"`（v3.12+）更稳；
- React 里清理交给 `useGSAP`（见下）。

### 4) React 接入（gsap-react）
```javascript
import { useGSAP } from "@gsap/react";
gsap.registerPlugin(useGSAP);
const ref = useRef(null);
useGSAP(() => { gsap.to(".box", { x: 100 }); }, { scope: ref });
```
- 有 `@gsap/react` 就用 `useGSAP`，别手写 `useEffect` + 手动 revert；
- 回调里要用动画实例时用 `contextSafe`；
- Next.js SSR：确保动画在客户端执行（`useGSAP` 天然符合）。

### 5) 插件（gsap-plugins）
```javascript
import { ScrollToPlugin } from "gsap/ScrollToPlugin";
import { Flip } from "gsap/Flip";
import { SplitText } from "gsap/SplitText";
gsap.registerPlugin(ScrollToPlugin, Flip, SplitText);
```
- **所有插件都免费（含商用）**：`npm install gsap` 全含，**不要**生成 `.npmrc`/auth token/私有 registry，那是过时说法；
- 插件必须先 register 再用；React 里在组件外注册一次；
- 常用：ScrollTo（滚动到位置）、Flip（FLIP 转场）、Draggable+Inertia、SplitText（拆字）、DrawSVG/MorphSVG/MotionPath、CustomEase。

### 性能（gsap-performance）
- 只动 `transform` / `opacity`；避免 `width/height/top/left/margin/padding`；
- 列表用 `stagger` 而不是手写 N 个 delay；长列表只动可见项；
- 复用 timeline，不要每帧新建；必要时 CSS `will-change: transform`。

## 坑（实测最常踩）

| 坑 | 正确做法 |
|---|---|
| 插件没注册就调用 | `gsap.registerPlugin(...)` 一次 |
| React 卸载后动画还在跑/内存泄漏 | `useGSAP` + `scope`，回调用 `contextSafe` |
| ScrollTrigger 布局变了位置不对 | 图片/字体加载完 `ScrollTrigger.refresh()` |
| 用 `left/top` 做移动 | 用 `x/y`（走合成层） |
| 动画目标被 React 重渲染换掉 | 用 ref 指容器 + `scope`，别用全局选择器 |

## 在我们这怎么用（GBT 场景）

- 面板动效：`holo_pet_w3/` 下的静态页 → 引入 GSAP 做切页/列表/滚动；
- **验证**：改完用 headless Chrome 截图（`chrome --headless=new --screenshot`）对比前后帧，
  不用嘴说"好看了"；
- 若要做数字人舞台动效：优先 transform/opacity，别动布局属性，避免拖慢 60fps。

## 参考（上游 8 个技能，按需再读）

| 上游技能 | 讲什么 |
|---|---|
| `gsap-core` | tween/easing/stagger/matchMedia |
| `gsap-timeline` | 序列、位置参数、嵌套、播放控制 |
| `gsap-scrolltrigger` | 滚动联动、pin、scrub、refresh |
| `gsap-react` | useGSAP、context、清理、SSR |
| `gsap-plugins` | 插件注册、ScrollTo/Flip/Draggable/SplitText… |
| `gsap-performance` | 合成层、批量读写、长列表 |
| `gsap-frameworks` | Vue/Svelte/其他框架接法 |
| `gsap-utils` | utils（mapRange/clamp/snap 等）与属性归一 |

> 上游：https://github.com/greensock/gsap-skills （MIT，© GreenSock）· 规范：https://agentskills.io/specification
