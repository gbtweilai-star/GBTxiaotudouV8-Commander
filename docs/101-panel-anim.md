> ⚠️ **2026-11-01**：本页接的三块面板（panel/capabilities/welcome）已归档，
> 现役界面见 [docs/102-cognitive-console.md](102-cognitive-console.md)（控制台入场改用纯 CSS 动画）。
> 本页保留为动效验证记录。

# 101 · 面板动效真落地（GSAP 接进三块面板 + 截图对比验证）

> 主人 2026-11-01：「APP 面板真闹心」→ 上一轮吸了 GSAP 技能，这一轮**真接进面板**并验证"动没动"。

## 一、接了什么

| 文件 | 作用 |
|---|---|
| `assets/gsap.min.js` | GSAP 3.12.5（72,214 B，官方 dist，**离线内置，不挂 CDN**） |
| `holo_pet_w3/assets/panel-anim.js` | 入场动效：`[data-anim]` 优先，否则取 `main/.wrap/.grid` 直接子元素；timeline 交错 y+opacity |
| `panel/` `capabilities/` `welcome/` 三页 `</body>` 前 | 引上面两个脚本（各一行） |

**纪律（写进代码）**：
- 只动 `transform/opacity`（合成层 60fps），不碰 `width/height/top/left`；
- 尊重 `prefers-reduced-motion` → 标 `skipped`，不动；
- gsap 没加载 → 标 `failed`，**不做假动画**；
- 同步标记 `data-anim="started"` + `data-anim-count=N`（能区分"没接线"和"没跑完"）；
- 完成标 `data-anim="done"`；2.5s 未完标 `timeout`（不假装）。

## 二、验证（真跑，不是口说）

### 1) 接线（headless DOM 断言）
```
panel        anim=started  count=2
capabilities anim=started  count=6
welcome      anim=started  count=2
```

### 2) 真动没动（headless 截图对比：t≈250ms vs t≈3000ms，1440×900）
| 页面 | 变化的像素 | 占比 | 平均亮度差 |
|---|---:|---:|---:|
| `panel` | 74,531 | **5.75%** | 6.93 |
| `capabilities` | 204,898 | **15.81%** | 9.62 |

> 像素真的在变 = 动效真的在跑（不是"写了个 JS 就算完"）。

### 3) 静态判据
`tests/test_panel_anim.py`（3 组 11 条全绿）：库在位、三页接线、reduced-motion/只动 transform/失败如实。

## 三、产物

- `assets/panels/panel-final.webp`、`assets/panels/capabilities-final.webp`（截图定稿，可直接放 README/docs）
- 想现场看：直接双击 `holo_pet_w3/panel/index.html`（或任意面板），当场就有入场动效

## 四、边界（如实）

- `capabilities` 面板数据来自本地 JSON 拉取，file:// 下会被浏览器安全策略挡住一部分 —— 这是**页面数据问题**，不是动效问题；要完整看数据请用本地 http 服务：
  `python -m http.server 8765 --directory holo_pet_w3`；
- 动效只做"入场"，滚动联动（ScrollTrigger）还没接 —— 下一轮再做，且必须有"滚动中截图"对比。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
