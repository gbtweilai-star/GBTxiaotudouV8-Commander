# 81 · 唯一真相：不分清谁新谁旧，就永远在绕弯（2026-11-01）

> 主人原话（意思）：「让你清旧的不是洁癖，是你每次都被旧副本搞懵，分不清谁是谁新的，
> 不用旧的就非要去找旧的在哪里绕弯。」

## 一、旧副本真正的危害

不是占空间，是**制造歧义**：

- 同一个文件有好几份（live / 交付树 / sync-backup / refresh*-work / _archive-*）；
- 被覆盖后 mtime 可能保留旧时间 ⇒ 连"哪个更新"都看不出来；
- 于是每次判断都要"去旧地方找线索"，越找越懵，最后拿旧内容当依据 ⇒ 假结论。

## 二、唯一真相（写死）

| 用途 | 唯一可信来源 |
|---|---|
| 现在是什么 | **live 工作仓的当前文件** |
| 改过什么 | `state/orchestration-ledger.jsonl`、git 历史 |
| 交付 | `~/Desktop/GBT小土豆V8` 只是**镜像**，不作判断依据 |
| **禁止读** | `state/sync-backup/**`、`_archive-*/**`、`*-v1/**`、`*.bak/.old/.orig`、`refresh*-work/**` |

代码里落成 `legacy_guard op=authority`，并把这条写进记忆条（每次路由都会看到）。

## 三、从源头掐断

1. **同步脚本不再写旧备份**：`tools/two-way-sync.ps1` 的 `Backup-Copy` 默认**不落备份**；
   真要留底必须显式 `-KeepBackup`（默认关）；
2. `state/sync-backup/` 出现即被 `legacy_guard` 报出并清掉；
3. 旧工作树/归档目录同样六类扫描；
4. 需要"历史"就看账本与 git —— 那才是**有语义**的历史，不是文件副本。

## 四、判断顺序（以后不用绕）

```
① 只看 live 仓当前文件（grep/read 直接读）
② 要知道"上一轮改了什么" → 查 state/orchestration-ledger.jsonl
③ 要复现"当时怎么跑的" → state/comfy-runs/、state/blueprints/*.runs.jsonl
④ 绝不：去 sync-backup / 归档 / 旧工作树里找
```

## 五、验收

- `legacy_guard op=status` → 六类全 0（clean）；
- `legacy_guard op=authority` → 明确列出唯一真相与禁止读路径；
- 同步脚本里搜不到 `sync-backup` 写入（除 `-KeepBackup` 分支）。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

---

## 六、同轮补的三条（都在代码里）

| 动作 | 落点 |
|---|---|
| 同步**默认不写旧备份** | 	ools/two-way-sync.ps1 的 Backup-Copy：备份仅在 -KeepBackup 分支 |
| **淘汰清单**（删了会被 push 推回 ⇒ 同步后按清单再删） | state/obsolete-files.json + ps1 的 Clear-Obsolete |
| **交付产物不算异物** | inventory._classify：根下 交付* 与 outputs/** 归 data（她记得的产物） |

## 七、验收（本轮实测）

`
legacy_guard op=status → clean（六类全 0）
inventory → clean（异物 0，45 项：43 框架 + 1 环境 + 交付产物归 data）
test_legacy_guard / test_blueprint / test_inventory_checkout → ALL OK
