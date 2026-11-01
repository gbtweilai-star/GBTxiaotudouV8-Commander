# 一键双向同步（two-way-sync）

> 2026-11-01 · 把「交付树 ↔ live 工作仓」的同步从一次性脚本收成仓内工具。
> 位置：`tools/two-way-sync.ps1`（执行器）+ `tools/codex-scripts/two-way-sync.py`（计划/校验器）+ `tests/test_two_way_sync.py`。

## 为什么拆两层

Windows 上**Python 写不了 `Desktop\GBT小土豆V8`**（文件属主/权限），但 PowerShell 能写；
反过来 **PowerShell 不适合做注册表文本插入/刷新链**，Python 能做。所以：

| 层 | 文件 | 职责 |
|---|---|---|
| 执行器 | `tools/two-way-sync.ps1` | 文件复制、备份、静默窗口守卫、调计划器、跑刷新链 |
| 计划器 | `tools/codex-scripts/two-way-sync.py` | 源码面 diff（sha1）、排除/保留规则、注册表分派插入、verify、refresh |

## 怎么用

```powershell
# 看两边差多少（只读）
powershell -NoProfile -ExecutionPolicy Bypass -File tools\two-way-sync.ps1 status

# 预览（不写盘）
powershell ... -File tools\two-way-sync.ps1 plan-pull
powershell ... -File tools\two-way-sync.ps1 plan-push

# 拉取：live → 交付树（旧版自动备份到 live\state\sync-backup\<时间>-pull\）
powershell ... -File tools\two-way-sync.ps1 pull -Apply

# 推送：交付树 → live（先过静默窗口守卫；写盘前自动备份）
powershell ... -File tools\two-way-sync.ps1 push -Apply -Refresh

# 终检：源码面 sha1 对齐 + 能力位计数一致
powershell ... -File tools\two-way-sync.ps1 verify
```

参数：`-Live <仓根>`（默认自动找）、`-Delivery <交付树>`（默认 `$env:GBT_DELIVERY` 或 `~/Desktop/GBT小土豆V8`）、`-Apply`、`-Force`、`-Refresh`。

## 同步口径（写死在计划器里，不靠人记）

- **排除**：`state/` `store/` `vendor/` `dist/` `logs/` `outputs/` `vaults/` `__pycache__`、`holo_pet_w3/_archive-20261021`、`tools/_retired`、`holo_pet_w3/wgpu/_retired`、`digital-human/raw`、`eye/frames`、`archived_logs`，以及去重删除件（`arms/omni_arm.py`、`source-copy.png`、`kaleido/v2|v3c|v9c|v12`、`ninfer_verify.ps1`）。
- **交付档案不推**：`MANIFEST.json`、`整理说明.md`、`整理报告/`（交付树独有）。
- **拉取保留交付成果**：349 页 boot 修复、6 处代码修复、手部两枚原生位、`deploy/`、待授权清单页等（`KEEP_PULL`）；live 的 boot 页面不覆盖交付版。
- **推送前静默守卫**：live 最近 60s 仍有源码写入就拒绝（防并发覆盖）；确认安全可 `-Force`。
- **备份**：每次写盘前把被覆盖文件备份到 `live\state\sync-backup\<时间>-{pull|push}\`。
- **注册表/分派**：`apply-push-caps` 幂等插入 `hand_retarget` / `hand_bridge` 两段（缺才插）。
- **刷新链**：`-Refresh` 跑 `export-capabilities → gen-open-source-caps → capability-bindings → capability-audit probe/render → gen-authz-page`。

## verify 判据

`ALIGNED` 需同时满足：
1. 排除口径下 **only_live=0**、**differ=0**；
2. 两边 `data/capabilities.json` 的 `count` 相等（当前 **368**）。

`DRIFT` 时打印前 20 条差异；退出码 1（可进 CI/巡检）。

## 边界（如实）

- 只同步**源码面**：运行数据 `state/`、权重/引擎 `vendor/`、归档/退役**永不同步**。
- 交付档案（报告/说明/MANIFEST）**只留交付树**，不回推 live。
- 推送是"交付树为准"的覆盖式同步；若 live 有未合并的源码改动，先 `pull` 再 `push`（工具会先报差异，不静默覆盖）。
- 刷新链会重生成 docs/capabilities/pages；live 侧跑完请再看 `cap_self verify`（367=367=367）。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
