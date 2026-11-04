# 122 · 触手协作视图重做（星座网络版）

日期：2026-11-02 · 参考：主人给的 `WhatsApp Video 2026-11-02 at 6.08.32 AM.mp4`（2.66s / 500×500）
截图：`outputs/screens-20261102/team-final.png`、`team-final2.png`、`team-pulse-live.png`；参考帧在 `outputs/screens-20261102/video-frames/`

## 参考视频是什么（抽帧看出来的）
黑底 + 白色发光节点（点大小不一、带柔光）+ 细白线拉成 3D 网络；节点缓慢漂移，线会**成片淡出再长回来**；
中途有一两帧线几乎全没了（只剩点），然后重新连上 —— 这是"呼吸"而不是断链。没有中心太阳、没有底座环、没有文字标签。

## 旧版的问题（对照截图 `team.png`）
· 8 条彩色粗管 + 彩色泡泡 + 中文标签 + 底座三环 ⇒ 更像"示意图"，不是参考视频那种"活的网络"；
· 中心一个橙色核 + 大光晕，抢画面；
· 线的明暗几乎不变，没有参考视频里的"散开/收拢"节奏。

## 重做后的映射（不是装饰）
· 8 个角色锚点（球面分布）= 8 个协作角色；每角色 11 颗卫星节点 = 该角色手里的能力位（共 96 点）；
· 线三类：卫星→锚点（触手纤维 88 条）· 锚点→锚点（协作链 16 条，相邻 2 环/对角 1 环）· 跨角色长弦（临时协同 24 条）；
· 呼吸：每条线有独立相位 + 全局呼吸（约 11s 一轮）⇒ 整片网络周期性收拢/散开；
· 金色脉冲：真实事件（`/api/events`）→ 点亮对应角色锚点（变金）+ 冲击波环 + 沿协作链飞一颗金色光点；
· 中心只留"一颗稍亮的节点"（共享任务），不做太阳。

## 踩到的坑（别再犯）
**Bloom 的 `radius` 必须是 0。** UnrealBloomPass 的宽 mip 会把中心亮像素糊成一大片灰盘（实测直径约画布 40%），
怎么调 strength/threshold 都去不掉；把 `radius` 设 0、threshold 抬到 0.85 后，只留节点柔光、细线保持锐利 —— 才对上参考视频。
旧参数：strength 0.95 / radius 0.62 / threshold 0.42（灰盘）；新参数：strength 0.5 / radius 0.0 / threshold 0.85。

## 验证
- `documentElement.dataset.team3d` = `ok:8臂+16协作链`（初始），事件后追加 `+脉冲N`；
- `window.__team3d.lightRole("inventory")` → 返回 `审计`，标记立刻变 `脉冲1`；`team3dLast` = `inventory→审计`；
- 画面：`team-final.png`（线较暗的呼吸相位）、`team-final2.png`（线亮相位）、`team-pulse-live.png`（点亮瞬间）；
- 交互保留：拖动旋转 / 滚轮缩放（OrbitControls，autoRotate 0.5）；
- 测试口径保留：`name:`×8、`pulses`、`getPointAt`、`data-team3d`、`team3dPulses`、`ringSprite`、`waves`、`selftest`。

## 待办 / 可选
- 真实 SSE 事件源现在没有 `audit.jsonl`（本 checkout 缺），所以金色脉冲只能靠 `?pulse=1` 或手动 `lightRole` 演示；
- 想更贴近视频可以再上一个"整片线瞬间归零再重连"的强节奏（当前是平滑呼吸）；
- 移动端横屏时点数可再降（现在 96 点 + 200 条线，手机可能掉帧）。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
