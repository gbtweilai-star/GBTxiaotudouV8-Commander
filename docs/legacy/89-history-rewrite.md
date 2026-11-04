# 89 · 方案 A：GitHub 历史重写（2026-11-01）

> 主人选择 A：重写历史让仓库真正变小（不是只清 HEAD）。

## 一、做了什么

1. 便携 git（MinGit）+ `git-filter-repo`；
2. 全量克隆（含 362 个提交，`.git` 193.1 MB）；
3. `--invert-paths` 从**所有历史**里剔除：
   `state/ store/ dist/ runtime/ logs/ vaults/ vendor/ outputs/ 交付成片/ "C:\Users\ADMIN\Desktop\GBT小土豆V8"`；
4. 重写结果：**362 → 351 提交**，`.git` 193.1 → **177.2 MB**，HEAD 文件数 **2752 不变**（逐文件比对过）；
5. `git push --force origin HEAD:main` 强推成功。

## 二、远程核对（实测）

| 项 | 结果 |
|---|---|
| 新 HEAD | **`d57a406`**（旧 `19d2b06` / `3851410` 已不在 main） |
| 文件数 | **2752** |
| `state/ store/ dist/ runtime/ logs/ vaults/ vendor/ outputs/ 交付成片/ C:\` | **全部 0** |
| README | `Caps-375` ✅、错仓链接已无 ✅ |

## 三、为什么 GitHub 显示体积还没立刻变

GitHub 的 `size` 字段是**异步**统计的：force push 后旧提交变成**不可达**，
但不是立刻删除——要等 GitHub 后台 `git gc`（通常几小时到几天）。
可以确认的是：旧提交已从 main 树上移除（直接按 SHA 仍可访问是 GitHub 的正常保留策略）。

想立刻看到小体积：**方案 B —— 新建一个干净仓**，只推当前 2752 文件（单提交），体积约 100MB 以内。

## 四、还能再小的空间（方案 C，需另行点头）

当前 HEAD 里的大资产（即使 B 也照样占体积）：

| 文件 | 体积 |
|---|---|
| `holo_pet_w3/voice-theater/assets/dh-v7-detail.glb` | 10.4 MB |
| `…/dh-v2-rigged.glb.b64.js`（同一模型的 base64 编码，**可删**） | 8.2 MB |
| `…/dh-v6-skin.glb` | 7.1 MB |
| `…/dh-v2-rigged.glb` | 6.1 MB |
| `holo_pet/assets/…/HERO-4096.png` | 5.1 MB |
| `docs/gallery/` 两张展示图 | 7.8 MB |

把大资产移出 Git（GitHub Releases / CDN / `assets/` 外置）后，仓库可降到 ~50MB。

## 五、工具

- `tools/git-portable-sync.py` —— 便携 git 全量同步（clone→覆盖→commit→push）
- `tools/push-rewritten-history.py` + `tools/push-history.cmd` —— 强推重写后的历史
- `.scratch/git-sync/` 是过程目录（MinGit + 克隆），任务完成后已删，不留垃圾。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
