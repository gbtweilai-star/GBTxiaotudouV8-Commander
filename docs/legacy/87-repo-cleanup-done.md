# 83 · 原始仓库整理完成（GitHub）(2026-11-01)

> 主人：「把原始仓库也整理一下，看的我头疼！」
> 仓库：https://github.com/gbtweilai-star/GBTxiaotudouV8-Commander
> 结果 commit：`19d2b06796a4620065c33ed33cf04c9eae0c532e`

## 一、做了什么（一次 commit，只删不清源码）

用 Git Data API（本机无 git）读 `main` 树 → 生成删除清单 → 建新树（要删的置 `sha=null`）
→ 建 commit → 更新 `main`。**不 clone、不 push、不碰本地工作仓**。

删除口径（运行态/产物/二进制）：
`state/`、`dist/`、`runtime/`、`logs/`、`vaults/`、`vendor/`、`store/`、
`gbt_allinone/store/`、`gbt_allinone/archived_logs/`、`worker.html`(symlink)、
以 Windows 绝对路径命名的目录 `C:\Users\ADMIN\Desktop\GBT小土豆V8`、
以及 >2MB 的二进制大文件（如 `assets/demo.gif`、`dist/**/deck.mp4`）。

## 二、前后对比（实测）

| 指标 | 整理前 | 整理后 |
|---|---|---|
| HEAD 文件数 | **5108** | **2708** |
| 删除 | — | **2323 个文件 / 154.1 MB** |
| `state/` | 1876 | **0** |
| `dist/` | 20（40.6 MB） | **0** |
| `runtime/` `logs/` `vaults/` `vendor/` | 有 | **0** |
| `C:\Users\ADMIN\...` 目录 | 1 | **0** |

保留：`gbt_allinone/`(868)、`tools/`(1014)、`docs/`(98)、`holo_pet_w3/`(540)、
`holo_pet/`(67)、`assets/`、`data/`、`ios/`、`mobile/` 等源码与文档。

`.gitignore` 已追加阻断块（`state/ store/ dist/ runtime/ logs/ vaults/ vendor/ *.gguf *.zip
*.png *.mp4 *.bin *.db *.jsonl C:*/` …），**以后不会再被这些路径弄脏**。
（已核对 commit 里的 blob：marker 在、`C:*/` 在；raw.githubusercontent 有 CDN 缓存，看 blob API 为准。）

## 三、诚实说明：仓库体积显示还是 ~200MB

GitHub 的 `size` 是**含历史**的体积。删掉 HEAD 里的文件不会立刻缩历史 ——
旧 blob 还在 commit 历史里。要真正变小得做历史重写：

```powershell
# 需要本地 git（这台机器没装）；或用新仓库
git filter-repo --path state --path dist --path vendor --invert-paths --force
git push --force
```

或者最省事：**建一个干净新仓库**，把当前 HEAD（已是干净的 2708 文件）推过去。
这两条我都能做，但都需要你决定，因为会改仓库历史/地址。

## 四、可选的下一步（等你点头）

1. `holo_pet_w3/` 还有 540 文件 / 74MB（3D 资产）。要不要把它挪到 `assets/` 或外置？
2. 历史瘦身（filter-repo / 新仓库）。
3. 把本地 `state/`、`dist/` 等也加进 `.gitignore` 之外的**本地清理**（本地已做过，见 docs/71/79）。

## 五、工具与判据

- 工具：`tools/github-repo-clean.py`（`--dry-run` 预览 / `--prompt` 静默输入 token / `--apply`）；
- 清单：`state/github-clean-plan.json`（2323 条，可复查）；
- 计划：`docs/82-github-cleanup.md`；
- 本次结果：本文件。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
