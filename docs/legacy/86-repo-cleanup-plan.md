# 82 · 原始仓库整理（GitHub）(2026-11-01)

> 主人：「把原始仓库也整理一下，看的我头疼！」
> 仓库：https://github.com/gbtweilai-star/GBTxiaotudouV8-Commander

## 一、体检结果（只读 API 拉的真实数据）

| 项 | 数值 |
|---|---|
| 文件总数 | **5108** |
| 仓库体积 | **约 200 MB**（GitHub `size` 204954 KB） |
| 建议删除 | **2323 个文件 / 154.1 MB** |

目录占用 Top（这就是"头疼"的来源）：

| 目录 | 文件 | 体积 | 判定 |
|---|---|---|---|
| `holo_pet_w3/` | 901 | 74.0 MB | 前端 3D 资产 + 运行态混放 |
| `dist/` | 20 | **40.6 MB** | 产物（含 30MB `deck.mp4`） |
| `holo_pet/` | 72 | 20.0 MB | 资产 |
| `state/` | **1876** | 18.3 MB | **运行态**（probe/bind/shards/audit 4.5MB jsonl…） |
| `docs/` | 101 | 17.1 MB | 文档（保留） |
| `gbt_allinone/` | 873 | 14.2 MB | 源码（保留） |
| `tools/` | 1021 | 9.8 MB | 工具（保留，含大量 codex 脚本） |
| `vendor/` | 95 | 4.2 MB | llama 二进制（不该进库） |
| **`C:\Users\ADMIN\Desktop\GBT小土豆V8/`** | — | — | **以 Windows 绝对路径命名的目录**（某脚本把路径当目录名提交了） |

## 二、清理口径（只删运行态/产物，不动源码与文档）

**删除**：`state/`、`dist/`、`runtime/`、`logs/`、`vaults/`、`vendor/`、`store/`、
`gbt_allinone/archived_logs/`、`worker.html`（symlink）、`C:*` 绝对路径目录、
以及 >2MB 的二进制大文件（如 `assets/demo.gif` 2.4MB）。

**保留**：`gbt_allinone/`、`docs/`、`tools/`、`tests/`、`assets/`（图标）、`README*`、
`LICENSE`、`CHANGELOG`、`pyproject.toml` 等源码与文档。

同时**改写 `.gitignore`**（追加阻断块），此后 `state/`、`dist/` 等路径不会再被提交 ——
**不二次变脏**才是整理的重点。

## 三、怎么执行（一次性，需要你的 token）

工具已写好：`tools/github-repo-clean.py`（纯 Python 标准库，**不依赖 git**）。

```powershell
# 1) 建一个仅有 repo 权限的 token：https://github.com/settings/tokens （勾 repo）
$env:GITHUB_TOKEN = "ghp_你的token"

# 2) 先预览（不需要 token 也能看清单）
py -3 -X utf8 tools\github-repo-clean.py --dry-run

# 3) 真提交（只提交"删除 + .gitignore"，不动源码）
py -3 -X utf8 tools\github-repo-clean.py --apply
```

预期：**2323 个文件 / 154 MB 从仓库消失**，仓库从 ~200MB 降到 ~46MB；
`state/` 那 1876 个运行态文件不再出现在 GitHub 首页。

> 说明：我在沙箱里**读**仓库没问题（API 只读），但**写**需要你的 token，
> 且这台机器没装 git，所以用 API 直接建 commit（不用 clone/push）。

## 四、为什么用 API 而不是 git

- 本机**没装 git**（`git` 命令不存在），无法 `git rm` + `push`；
- Git Data API 能做到同样的事：读树 → 建新树（要删的置 `sha=null`）→ 建 commit → 更新 `main`；
- 全程一次 commit，历史保留，随时可 revert。

## 五、边界

1. **只删运行态/产物**，不删源码；`holo_pet_w3` 的 3D 资产不在删除清单（除非你说要）；
2. `--big-mb 2` 之外的大文件靠你调阈值；`--keep` 可额外保留前缀；
3. 需要 repo 写权限的 token；用完请撤销；
4. 这个脚本**不会**改你的本地工作仓，只动 GitHub 上那一份。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
