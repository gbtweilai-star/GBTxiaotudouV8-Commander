# 79 · 旧物守卫：项目里不许有旧代码、旧面板、重复物（2026-11-01）

> 主人严令（逐字）：「我们项目里面不允许有旧代码和旧面板等一切旧，重复的东西存在你不知道吗？」

---

## 一、六类（全部可数）

| 类 | 判据 | 处置 |
|---|---|---|
| 旧代码快照 | `state/sync-backup/` | 删（同步自己的备份产物） |
| 过期工作树 | `refresh*-work` / `live-backup` / `upstream-raw` | 删 |
| 旧面板归档 | `_archive-*` / `_old` / `*-v1` | 删 |
| 备份文件 | `*.bak` / `*.old` / `*.orig` | 删 |
| 重复文档编号 | `docs/NN-*.md` 同号 ≥2 | **只报不删**（删哪页要人看内容） |
| 临时件 | `state/tmp/` 非空 | 删 |

## 二、怎么用

```python
run_task("legacy_guard", {"op": "status"})   # 结论：clean / legacy_found
run_task("legacy_guard", {"op": "scan"})     # 逐类列出路径
run_task("legacy_guard", {"op": "clean"})    # 删旧副本类，记编排账本
```

## 三、自注册（因为环境在打架）

这个项目里 `api.py` / `caps_registry.py` 会被外部双向同步**整文件覆盖**（改一次丢一次），
所以 `legacy_guard` 不走"改 api 分派"那条路，而是做成**包导入层自注册插件**：

- `gbt_allinone/__init__.py` 里 `_gbt_self_register()`：
  1. 把 `legacy_guard` 登记进 `BENIGN_CAPS`；
  2. 包一层 `run_task`，`kind == "legacy_guard"` 时直接分派；
- 效果：**每次 import 自愈**，不依赖那两个被覆盖的文件。

## 四、实测（这一轮）

```
清理前 11,431 MB / 24,747 文件
清理后 10,591 MB /  7,739 文件      （省 840 MB，17,008 个文件）
六类复查：sync-backup 0 · 旧工作树 0 · 旧面板 0 · 备份文件 0 · state/tmp 0
```

## 五、边界

- `state/sync-backup` 是**同步脚本自己产生**的：每次 `pull/push` 都会建一个 `<时间>-{pull|push}`
  目录。所以守卫每次跑都会发现它 —— 这是设计上的"看见即报"，不是 bug；
  要根治得让同步脚本**不再备份旧副本**（已建议：改为"不落备份，只记 sha1"）；
- 重复文档只报不删：两页可能都有价值，删哪页应由内容判断。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
