# 88 · GitHub 全量清扫完成（2026-11-01）

> 主人：「是必须全面清扫而不是表面做样子」「做事别偷奸耍滑」。
> 这一轮不是补丁，是**以本地真身为唯一真相的全量对齐**。

## 一、清扫前后（GitHub HEAD 实测）

| 项 | 第一轮后 | 全量对齐后 |
|---|---|---|
| HEAD 文件数 | 2588 | **2752** |
| 提交 | 19d2b06 | **3851410**（+ fc8742c） |
| 同路径旧内容 | 470 个 | **0**（全部被本地版覆盖） |
| 远程缺的新件 | 1503 个 | **0** |
| 远程多出的旧件 | 3 个 | **0**（已删） |
| `state/ dist/ runtime/ logs/ vaults/ vendor/ C:\…` | 0 | **0** |
| `交付成片/`、`outputs/`（产物） | — | **0**（移入 outputs/ 且加 .gitignore） |
| README | 旧版（Caps 368、错仓链接、重复段、坏路径） | **新版**（Caps 375、链接正确、无重复段） |

## 二、怎么做的（可复现）

1. `tools/github-full-sync.py`：用 git blob sha 逐文件对账（远程 vs 本地），算上传/删除清单；
2. 1095 次 API 上传太慢（跑了 10 分钟未提交）⇒ 改走**便携 git**：
   `tools/git-portable-sync.py` —— 下载 MinGit → 匿名 clone → 用本地真身覆盖 → 一次 commit → 一次 push；
3. 结果：`fc8742c`（全量对齐）+ `3851410`（删产物目录 `交付成片/` 并补 `.gitignore`）。

## 三、口径（写死）

- **唯一真相 = 本地工作仓当前文件**；远程一律向它看齐；
- 排除运行态/产物/二进制：`state/ store/ dist/ runtime/ logs/ vaults/ vendor/ outputs/ 交付成片/ .scratch/ __pycache__/`
  以及 `*.pyc *.gguf *.zip *.mp4 *.db *.jsonl`；
- 产物目录**永不进仓**（`交付成片/`、`outputs/` 已进 `.gitignore`）。

## 四、还没做的（需主人点头）

仓库体积仍显示 **~200MB**：那是**历史**里第一轮之前的旧 blob。
要真正变小必须重写历史：
- 方案 A：`git filter-repo --path state --path dist --path vendor --invert-paths --force` + `push --force`；
- 方案 B：起一个干净新仓，把当前 HEAD（2752 文件）推过去。

两条都会改历史/地址，所以我停在这里等指令。

## 五、安全

本轮与上一轮的 token 都已用完，请到 https://github.com/settings/tokens 全部 **Revoke**。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
