# 187 · 控制台布局：PAGE MESH 不再压住右栏

> 主人截图：`PAGE MESH · 页 20 · 双向链 380 · …` 浮在「身体控制 / 触手 / 全息投影」和 `not_supported` 上，右栏挤成一团。

## 根因

`page-mesh.js` 把 HUD 用 `position: fixed; right: 18px; bottom: 8px` 挂在 `<body>` 上，右栏 `#panel-l2` 底部又有 BODY CONTROL / CONTEXT INJECT 模块；两者空间重叠，HUD 就盖在正文上。

## 修法

- console 里新增**布局槽** `#mesh-hud-slot`（在 tabs 下方，占正常文档流）；
- `page-mesh.js` 优先 `slot.appendChild(hud)`，只有找不到槽才退回 body；
- CSS 把 `#page-mesh-hud` 从 `position: fixed` 改成 `position: static`，去掉 `right/bottom` 浮位；
- HUD 变成一条细状态线（页/链/pulse/对端/cache/＋窗口），不再盖右栏。

## 真机验证

- `inSlot=true`；HUD 与 `.body-module` 矩形 `overlap=false`；
- 布局槽在 tabs 之后，正常流式占位；
- 右栏「身体控制 / 触手 / 全息投影」不再被遮。

## 同时清掉的旧状态

APP payload 的 `selfscan/signature/inventory` 之前读的是 **payload 自己的旧 store/文档**，所以左侧还显示 P0 / missing / foreign。已：

- 补 `payload/gbt_allinone/store/wf_runs` 等目录；
- 对 payload 执行 `signature_guard restore`；
- 补 `payload/pyproject.toml` + `payload/state/repo-layout.json`；
- 重启后 `/api/state`：`selfscan=clean · signature=clean · inventory=clean`；`legacy=legacy_found` 仅剩重复文档编号，继续留案。

## 验收

`tests/test_console_layout.py` 全绿：
- HUD 槽存在、JS 优先塞槽；
- HUD 规则无 `fixed/right/bottom`；
- 槽在 tabs 之后。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
