# 121 · 控制台 3D 视图：three.js vendor 缺失 → 已补回（含 core 分块）

日期：2026-11-02 · 状态：**六个 3D 视图已恢复渲染** · 截图：`outputs/screens-20261102/`

## 症状（实测）
打开 http://127.0.0.1:8766/console/index.html 后切到 3D 星图/大脑/万能插/协作/导图/扫描：
中间画布全空，只留一句 "Failed to fetch dynamically imported module: .../console/space3d.js"。
`console-data.js` 与页面本身都正常，**不是渲染器、不是 CSP、不是 canvas 尺寸**问题。

## 根因
`holo_pet_w3/console/*3d.js` 用 importmap 引 `three` 与 `three/addons/`：
```
"three": "../../assets/vendor/three/three.module.js"
"three/addons/": "../../assets/vendor/three/"
```
但这个 checkout 里 `holo_pet_w3/assets/vendor/three/` **整个目录不存在**（MANIFEST 也不含它，属 vendored 大文件）。
而 `holo_pet_w3/brain/vendor/` 里那份 `three.module.min.js` 是 r180 的**入口壳**，
内部 `import "./three.core.min.js"`，且那份 core **没跟过来** —— 直接拿它当 three.module.js 仍然 404。

## 修法（本轮）
1. `holo_pet_w3/assets/vendor/three/three.module.js` ← `brain/vendor/three.module.min.js`（r180 入口壳，原样）；
2. `three.core.min.js` ← three@0.180.0 官方构建（**381,124 B**，与入口壳同版本，缺它入口壳就废）；
3. addon 按 importmap 的 `three/addons/xxx` 路径落盘，并把 `from "./three.module.min.js"` 改回裸名 `from "three"`（由 importmap 解析，避免两套 three 实例）：
   · `controls/OrbitControls.js`
   · `postprocessing/{EffectComposer,RenderPass,UnrealBloomPass,Pass,ShaderPass,MaskPass,CopyShader,LuminosityHighPassShader}.js`
4. 校验：所有相对 import 均可解析（0 处未解析）；页面里动态 `import(".../console/space3d.js")` → **OK**。

## 已验证
- 6 个 3D 视图 dataset 状态：`space3d=ok:*`、`brain3d=ok:7臂+审计环`、`plug3d=ok:8插口+数字结`、
  `team3d=ok:8臂+16协作链`、`mindmap` 渲染、`scan3d=no-scan-data`（见下）；
- `tests/test_console.py` 新增两条回归判据：
  「three.core.min.js 分块在位（入口库的依赖）」「addon 裸模块名已接 importmap」；
- 截图 12 张落在 `outputs/screens-20261102/`（1600×1000）。

## 仍然缺的（本 checkout 的生成产物，不是页面 bug）
- `state/scan-data.json` 缺 ⇒ 穿透扫描画布空、HUD 停"扫描中"；跑 `py -3.14 tools/export-scan-data.py` 生成；
- `gbt_allinone/store/audit.jsonl` 缺 ⇒ 右栏"行动日志"空、心跳"0 次数"（SSE 没事件可推，不是断连）；
- `state/orchestration-ledger.jsonl` 缺 ⇒ 仪表盘"编排流水 0 条"；
- `state/console-data.js` 缺 ⇒ `tests/test_console.py` 第 138 行读它时 FileNotFoundError（页面走 /api/data 直读，不影响使用）。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
