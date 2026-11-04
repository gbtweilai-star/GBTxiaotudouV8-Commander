# 186 · git_write 高级写面（push / rebase / reset 真跑）

> 主人 2026-11-03：不要再用“诚实边界：不做 push/rebase/reset”当工作成果。
> 这次把高级写面补齐，**真跑临时仓 + 本地裸远端**，不是只写说明。

## 一、现在能做什么

| op | 真实动作 | 闸/标记 |
|---|---|---|
| `push` | `git push <remote> <branch>` | `confirm=true`；`network=true` |
| `force_push` | `git push --force-with-lease` | `confirm=true`；只允许 lease，拒绝裸 `--force` |
| `rebase` | `git rebase <onto>` | `confirm=true`；**工作区必须干净**；冲突返回 `conflict=true`，不自动 abort |
| `reset` | `git reset --hard <rev>` | `confirm=true`；必须点名 rev；`destructive=true` |
| `stage`/`commit` | 原能力保留 | 仍点名 paths；commit pathspec-limited |

没有 `confirm=true` 一律 `confirm_required` 拒绝，不接受默认。

## 二、真机测试（临时仓 + 本地裸远端）

`gbt_allinone/tests/test_git_advanced.py` 全绿：

```
push 真推 ✓ · push 标 network ✓ · push 拒绝无 confirm ✓
reset --hard 真跑 ✓ · reset 标 destructive ✓
rebase 真跑 ✓ · rebase 标 conflict=false ✓
reset/rebase 拒绝无 confirm ✓
```

## 三、Windows 路径修复

本机刚装 Git，但当前进程 PATH 未刷新 → `git_read` 曾报“本机找不到 git”。
已在 `git_repo.py` 增加 `_git_exe()`：`shutil.which` + `C:\Program Files\Git\cmd\git.exe`
等常见落点兜底；现在 git 能力可用，不再靠“环境没 PATH”当失败理由。

## 四、边界（这次不是不做，是做了但说清风险）

1. `force_push` 只用 `--force-with-lease`，绝不裸 `--force`；
2. `push` 会真出网：返回 `network=true`，是否放行由调用方/出网门决定；
3. `rebase` 不自动解决冲突，也不自动 `--abort`；调用方看 text 决定；
4. `reset --hard` 只动本地工作区/索引，不推远端、不删远端历史；
5. 所有写面仍走 `filesystem_write` 门；高级 op 额外要求 `confirm=true`。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
