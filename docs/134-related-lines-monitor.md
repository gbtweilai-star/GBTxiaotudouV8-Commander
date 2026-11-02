# 134 · 万能插关联线路监控（能力不得丢）

主人令（2026-11-02）：修一个地方，就把它关联的所有线路都用触手监控起来，有任何变化第一时间发现。

## 实现
- `gbt_allinone/omni_lines.py`：扫运行路径代码建依赖图（py 绝对/相对 import、html script/link、js import()/fetch(/api/…)、路由 ↔ 前端 fetch、loader.load 资产）；
- 每个被监控文件记 mtime+size；变化时对依赖图做 BFS **关联闭包**，把「变了 → 连带 n 条线路」写进台账；
- 图谱与事件持久化：`state/omni-lines.json`（图谱 + 最近 120 次涟漪），重启自动加载/重建（120s 过期重建）；
- 并入 `omni_monitor.py` 的 `lines` 域，`/api/omni?op=monitor` 与 `/api/omni?op=lines` 可查；
- 页面：万能插 → 多域监控 → “关联线路”卡片（监控文件/关联边/本轮变化/最近涟漪），变化进“最近变化·细微级”。

## 实测
- 图谱：981 节点（运行域）/ 1473 边 / 24 路由 / 645 监控文件；
- 触碰 `gbt_allinone/dh_tentacle.py` → 立刻识别，关联闭包 **406 条**（含 dh_omni_loop、omni_monitor、hand_retarget、omni_plug、hand_bridge、console-server…）。

## 不丢的保证
- 能力在图谱文件和监控模块里，不依赖会话；app 重启后重建/加载继续跑；
- 台账 `state/omni-monitor.jsonl` 追加式记录，可追溯。