# 75 · 改一次被打回一次：双向同步回滚的排查与修复（2026-11-01）

> 现象：改 `tests/test_blueprint.py`，改完 grep 有、过几十秒又变回旧内容；edit 工具连续报
> 「file changed since it was read」。

---

## 一、排查（按证据走，不猜）

| 步骤 | 结果 |
|---|---|
| 看进程 | 只有一个 powershell；无 python 在跑 |
| 看计划任务 | 无 gbt/sync 相关 |
| 看启动项 | **Startup\GBT-SyncGuard.cmd** → `tools\sync-guard-patrol.ps1` |
| 看仓内 | `tools/two-way-sync.ps1` + `docs/74-two-way-sync.md` + `state/sync-backup/`（09:22 有 pull 备份） |
| 文件 mtime | 被覆盖后 mtime 被**保留成旧时间**（Copy-Item 会带时间戳）⇒ 看不出来，但内容回退 |

**根因**：`two-way-sync pull`（live → 交付树）只按"文件列表"复制，**不看时间** ⇒
交付树上刚写的新文件被 live 里的旧副本覆盖。

## 二、修复

### A. 同步器：目标更新就不覆盖（newer wins）

`tools/two-way-sync.ps1` 的 `Backup-Copy` 增加：

```powershell
if (目标.LastWriteTimeUtc > 源.LastWriteTimeUtc + 5s) { 跳过（目标更新） }
```

这样"刚改的"不会被"更旧的"打回；要强制就以 `-Force` 语义走别的模式。

### B. 判据测试：全局自清

`tests/test_blueprint.py`：

1. 开局记录 `state/blueprints`、`state/blueprint-templates` 快照；
2. 结束删掉**本次新增**全部文件（只留真实蓝图 `gbt小土豆v8触手主-5d1942`）。

## 三、验证

```
连跑两遍 test_blueprint：蓝图 6 → 6、6 → 6（不再增长）
改完文件等 45 秒：getpid / _KEEP_BP 标记仍在（不再被回滚）
```

## 四、教训

1. **先怀疑进程，再怀疑工具**：连续"改了又没了"不是 edit 的问题，是有别的写者；
2. **备份目录就是时间线**：`state/sync-backup/<stamp>-pull` 直接指出是谁覆盖的；
3. **同仓双写必须有 newer-wins**：否则任何"新建即被回滚"，而且 mtime 还被保留，极难查。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
