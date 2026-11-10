# 198 · 3D 四页首屏：角标遮挡、按钮重合、标签裁切

日期：2026-11-07
范围：`holo_pet_w3/console/{app.css,skin-cube.css,plug3d.js,thought-stream.js}`

## 体检方法

1600×1000 CDP 逐页切换，对每一页做两件事：

1. **溢出扫描**：遍历 `.view-*` 内所有元素，比较 `getBoundingClientRect()` 与视图矩形，找越界。
2. **角标遮挡扫描**：把 `.page-pulse`（右上角 `PAGE MESH` 小角标，每页一个）的矩形与页内所有可交互元素
   （`button / input / select / a / textarea / [role=button]`）求交，报告重叠像素。

结果：世界 / 大脑 / 万能插 / 触手协作四个 3D 页**没有元素越界**（`overflow: []`），canvas 尺寸也都等于视图
（794×823），`dataset` 标记全部为 ok，控制台无报错。真正的问题集中在**角标遮挡**和**3D 标签裁切**。

## 改掉的 6 处

| # | 位置 | 问题（实测） | 改法 |
|---|---|---|---|
| 1 | 万能插页 | `#om-toggle`「多域监控」与 `#im-toggle`「改动影响」**坐标完全重合**（都在 1097,120），前者永远点不到 | 改成 34 / 74 两行；`#proactive-toggle` 56→114；`.proactive-panel` 96→154 |
| 2 | 功能表 | 搜索框/域选择与角标重叠 70×10px | `.view-caps .view-head { padding-right: 92px }` |
| 3 | 技能栏 | 搜索框与角标重叠 70×10px | `.view-skills .view-head { padding-right: 92px }` |
| 4 | 世界 | 「换一个世界」按钮被角标盖住 63×10px | `.world3d-tools { top: 12px → 34px }` |
| 5 | 浏览器 | 「打开 / 外部」被盖 20×4 / 46×4px | `.gbt-browser-bar { padding-right: 96px }` |
| 6 | 思考流 | 「刷新」被盖 40×10px | `.ts-bar { padding-right: 96px }` |

改完全 21 页复扫：**没有任何可交互元素与角标相交**（`{}`）。

## 3D 标签裁切（万能插）

HUD 看得到「creation-5…」「sys…」被画布右缘切掉。算了一下：相机 `z=20`、`fov=46`、画布 794×823（aspect 0.965），
视锥半宽 ≈ 8.19 世界单位；环半径 7.4 + 标签半宽 1.3 = 8.7 > 8.19 —— 最外圈插口标签必然出界。

改法：`camera.z 20 → 21.8`（半宽 ≈ 8.94）+ 标签 `scale 2.6×0.5 → 2.45×0.47`（半宽 1.225）。
改后最外圈 `creation-58` / `system-58` / `recon-18` 完整可见，结体尺寸基本没变。

## 顺带修的两处

- **万能插 3D 看门狗误报**：原 `setTimeout(..., 8000)` 只要 `inited` 还没置位就弹「未就绪（8s 未完成）」，原因字段直接印
  `imported`。实测冷启动在机器忙时确实会超过 8s（并行跑巡检时触发过一次），且提示文案对用户毫无意义。
  改成 15s + 人话原因（`imported` → 「three.js 模块与 /api/data 还在加载（冷启动编译着色器较慢）」），
  并在 3D 就绪时自动收起（原本就有 `fbx.hidden = true`）。
- **思考流标题吐 JSON**：`100 条 · {"thought":0,"action":100,"result":0,"guard":0,"system":0}` →
  `100 条 · 行动 100`（只列非零项，用「思考/行动/结果/闸门/系统」中文名）；
  空列表从「暂无事件」补成「还没有事件。对话或执行一次任务后，这里会出现 想 / 做 / 果 / 闸 / 系 五类记录；本页每 5 秒自动刷新」。

## 判据（可复跑）

```
node .scratch/probe-views.mjs   # 四页溢出/尺寸/标记：overflowN=0，canvas 794x823，ds 全 ok
node .scratch/probe-pulse.mjs   # 21 页 × 可交互元素 × 角标：{}（零相交）
node .scratch/probe-plug-time.mjs  # 万能插 3D 就绪耗时：0.5~0.6s（首屏冷启动实测）
node .scratch/probe-stream.mjs  # 有数据 "100 条 · 行动 100"；空数据 "0 条" + 引导文案
node .scratch/audit2.mjs        # 21 页 errors:[] / net:[]
```

## 回归

`test_console_chat_print` 7 条 OK；`test_chat_live_steps` ALL OK。

## 注意

- `plug3d.js` / `thought-stream.js` 带钢印，只改实现体，文件头未动。
- `plug3d.js` 的相机改动会影响观感，改动量控制在 9%（20 → 21.8），不要再靠继续拉远来解决排版问题；
  插口多于 14 个时应改成动态半径。
- 角标 `right:8 / top:6`、宽 78~88px 是当前几何前提；若改角标尺寸，`92px / 96px` 的留白要一起复核。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
