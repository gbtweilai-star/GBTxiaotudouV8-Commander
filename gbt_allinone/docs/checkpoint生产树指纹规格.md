# checkpoint 覆盖生产树 · 规格（v1）

> 性质：**规格（只出稿，不动刀）** · 批次：**下一份 checkpoint = 00002** · 出稿：2026-09-17
> 批复：风哥 2026-09-17「拍：下一份 checkpoint 把生产树三份文件的指纹打进去」
> 依据：`checkpoints/00001` 冻的是**镜像维度 + reality**，覆盖不到生产树；
> 而第一刀改的正是生产树（`holo_pet/`），回滚凭据只有 `.scratch/` 备份 —— **备份是文件级，checkpoint 是世界级，两者互补**。

---

## 一、范围（拍板口径）

| 项 | 口径 |
|---|---|
| 覆盖对象 | **生产树**（仓库根）下的源码与文档 |
| 是否拷文件 | **不拷**。只打指纹 —— 生产树大，镜像 checkpoint 不背这个包袱 |
| 指纹三件套 | `path` · `sha256` · `mtime`（外加 `bytes` 便于人眼对照） |
| 落点 | `checkpoints/<id>/production_tree_manifest.json` **（与 `record.json` 同级，不塞进 record 里，避免改既有 schema）** |
| 冻结的既有部分 | `dimension/` + `reality/` 全树照旧（不因本规格改动） |

### 覆盖路径（白名单目录）

```
holo_pet/        （含 shell/ tests/，排除 node_modules/ 与 archive/）
gbt_allinone/    （排除 store/、__pycache__/）
potato_pet/
config/
```

### 排除规则（**七条**，一条都不许省 · 2026-09-17 由六条扩为七条）

| # | 排除 | 理由 |
|---|---|---|
| E1 | `node_modules/` | 体积大、可重装，不属于"我的代码" |
| E2 | `__pycache__/` | 派生文件 |
| E3 | `.git/` | 独立性：manifest 不该把版本库本身算进去 |
| E4 | `.scratch/` | **一次性工作区**（含备份/暂存/探针产物），按设计会天天变 |
| E5 | `store/` 及其子目录 | 账本与生活档案自身高频写，指纹无意义且会天天漂 |
| E6 | 单文件 > 5 MB | 防 manifest 爆掉；命中则在 manifest 里记一条 `skipped_too_large` |
| E7 | **pip 生成的 vendored 依赖目录**（当前落点 `.pylibs/`） | 不是手写源码 · 由 pip 管理（可重装） · 不在 git 索引 · 88 MB / 4152 文件的纯负担 |

**边界 1（规则写"为什么"，不写死路径）**：E7 在代码里写成
`"排除 pip 生成的 vendored 依赖目录：…；当前落点 .pylibs/，将来迁移则规则跟随"`——
将来 vendored 依赖换目录，**只改这一行规则，不改判据**。manifest 的
`summary.exclude_rules` 会把**每一条规则连同理由**一起落盘（工件自描述，不靠人记）。

**边界 2（排除不许把判据也排掉）**：加一条判据 —— **排除后的 manifest 仍能判生产树漂移**。

| 臂 | 动作 | 期望 |
|---|---|---|
| 正对照 | 改一个**手写文件** | `--diff` 报 `modified` |
| 负对照 | 改 `.pylibs/` 里一个文件 | `--diff` **不报** |

两组结果必须不同（《扫描器自证律》）。**理由**：排除之后不能"什么都报不出来"——那排除就变成了静默失效。
契约测试：`gbt_allinone/tests/test_checkpoint.py::TestProductionTreeManifest::test_boundary2_exclusion_does_not_blind_the_drift_check`。

---

## 二、manifest 形状

```json
{
  "schema": "production-tree-manifest/1",
  "created_at": "2026-09-17T17:30:00+07:00",
  "root": "C:/Users/ADMIN/Desktop/GBT小土豆V8",
  "files": [
    {"path": "holo_pet/panel_server.py", "bytes": 62249,
     "sha256": "cb6f8f64e21e29081d86b716ba3a562ebc7696348f95f07a3dddd090f0781570",
     "mtime": "2026-09-17T16:57:12+07:00"}
  ],
  "summary": {"files": 1234, "bytes": 9876543,
              "skipped_too_large": [], "excluded_dirs": ["node_modules", "__pycache__", ".git", ".scratch"]}
}
```

**写盘口径**：一律 UTF-8 无 BOM；这是**快照类工件**，不参与 `record.json` 的哈希自证。

---

## 三、三条硬要求

1. **只读**：生成 manifest 的过程对生产树**只读**，一个字节都不写。
2. **不阻塞**：manifest 生成失败**不许**导致 checkpoint 失败 —— 但**必须**在 `record.json` 里留一条
   `production_tree_manifest: {"ok": false, "error": "..."}`，**不许静默跳过**（《静默失效律》）。
3. **可复算**：`--status` / `--diff` 提供一条只读路径，重算当前生产树指纹并与 manifest 对比，
   输出 `drift` 清单（哪些文件新增 / 改动 / 删除）。

---

## 四、与恢复（`--restore`）的关系

**恢复仍然只覆盖 `dimension/` + `reality/`**，**不**碰生产树 —— 生产树的回滚走既有备份口径
（第一刀：`.scratch/_r36_prewrite_*.bak` + SHA 比对）。

manifest 在生产树回滚里承担的是**裁判**角色：

1. 回滚前：重算指纹，与 manifest 对比 → 得到"现在离检查点有多远"的清单；
2. 回滚后：再算一次 → 与目标备份 SHA 逐个比对；
3. **不比对通过不算回滚成功**（同第一刀口径）。

---

## 五、验收

| # | 闸门 | 判据 |
|---|---|---|
| C1 | manifest 落盘 | `checkpoints/00002/production_tree_manifest.json` 存在且可解析 |
| C2 | 只读 | 生成前后，生产树三份关键文件 SHA256 不变 |
| C3 | 覆盖正确 | 抽查 `holo_pet/panel_server.py` 的 sha256 与磁盘实测一致；`node_modules` / `.scratch` 一条都不在 |
| C4 | 失败不静默 | 人为让 manifest 生成抛错 → `record.json` 里出现 `ok:false` 且 checkpoint 本身仍成功 |
| C5 | 可复算 | 改一个文件后跑 `--diff`，该文件出现在 drift 清单里；改回后消失 |

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

---

## 〇、落刀实测留痕（2026-09-17 傍晚 · 风哥批 S7 前置后执行）

**状态：已实现（本节由"只出稿"改写为"已落刀"）。** 落点两处：

| 文件 | 内容 |
|---|---|
| `gbt_allinone/checkpoint.py` | `production_root()`（`GBT_PROD_ROOT` > 包父目录）· `production_tree_manifest(root)` · `production_tree_drift(paths, rec)` · `do_checkpoint(..., prod_root=None)` 把结果写进 `record.json["production_tree_manifest"]` · `--status`/`--diff` 输出只读复算 |
| `gbt_allinone/tests/test_checkpoint.py` | 新增 `TestProductionTreeManifest`（C1–C5 逐条对应），套件总数 27 |

**00002 实测**：`seq=2` · dimension 14 / reality 12 / 护照 v20 · 生产树 **4311 文件 / 95,227,875 B** ·
manifest `sha256=9e0a7ebd08f6cbce687020ef04b2f8e8a54e45a8cee09cfdb77099a74cd946b6`（990,134 B）·
7 个超 5MB 文件按 E6 登记跳过 · `missing_roots=[]` · 排除零漏（node_modules / `__pycache__` / `.git` /
`.scratch` / `store` 全 0）· 只读闸门过 · 耗时 6.6 s。

**两条口径报备**（不硬套、不自己加规则）：

1. manifest 多一个 `root_source` 键（`GBT_PROD_ROOT` / `package_parent`）—— 自证"这份指纹打的是哪棵树"。
2. 差异词汇用 `added` / `removed` / `modified` —— 与 dimension·reality 那套
   `production_extra` / `not_yet_promoted` / `diverged` **不同轴**，不硬套。

**已拍（2026-09-17 · Owner）：加 E7，排除 pip 生成的 vendored 依赖目录（当前落点 `.pylibs/`）。**
规则写"为什么"不写死路径；并加判据"排除后 manifest 仍能判漂移"（正/负对照见 §一 边界 1 / 边界 2）。
**实测（真树空跑，以实测为准）**：

| | 文件数 | 字节 | 耗时 |
|---|---|---|---|
| E7 之前（00002 实际打点） | 4311 | 95,227,875（90.82 MB） | 6.6 s |
| E7 之后（空跑复算） | **342** | **13,116,383（12.51 MB）** | **4.3 s** |

（此前估的"约 160 文件 / 2 MB"是估算，错了，以本表为准——估算不许当账。）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
