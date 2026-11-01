# 114 · 无死角扫描口径（覆盖率 100% 才允许说"扫完"）

> 主人 2026-11-01：「每一次扫描都必须是无死角扫描」。

## 一、口径写死（扫描器侧）

| 判据 | 行为 |
|---|---|
| `coverage = hooked / units` | 原样返回，不四舍五入粉饰 |
| `full_coverage` | `coverage >= 1.0` 才为 true |
| `dead_spots` / `dead_spot_count` | 补扫后仍未钩住的 unit，**如实红**，绝不折叠成绿 |
| 补扫轮次 | 2 → **3 轮**（`RESCAN_ROUNDS = 3`）；仍钩不住 → `ok=false` + 死角清单 |
| 口径字符串 | 明写："missing/dead_spots 非空 ⇒ 不许念成通过；full_coverage=false ⇒ 不算无死角" |

## 二、可视化侧（scan3d.js）

- HUD 增加 **覆盖 / 死角** 两个实时字段（`data-scan3d-coverage` / `data-scan3d-dead`）；
- 扫描线扫完一轮时计算 **漏扫数**（`data-scan3d-missed`，每帧都会写），三者都为 0 且覆盖 100% 才显示
  **「无死角 · 385/385 · …」**；否则显示 **「仍有死角 N 个（如实报，不折叠）」**；
- **现场重扫**按钮（HUD 右上「现场重扫」）：点一下真调 `GET /api/scan?target=…`；
  若返回 `coverage < 1` → 自动补扫（最多 3 轮），状态栏写"发现死角，补扫第 N 轮…"；
- 服务端白名单：`bindings | registry | tree:<仓库内目录>`，非法 target 直接 400，防穿越。

## 三、实测（端到端）

```
GET /api/scan?target=registry
  → ok, units=1, coverage=1.0, full_coverage=True, dead_spot_count=0, ms=116

导出三目标（重导后）：
  bindings(1913) coverage=1.0 full=True
  registry(1)    coverage=1.0 full=True
  tree:gbt_allinone(943) coverage=1.0 full=True

页面 ?rescan=1（自动现场重扫）：
  data-scan3d            = ok:bindings:1913单元+0疑点
  data-scan3d-coverage   = 100
  data-scan3d-dead       = 0
  data-scan3d-missed     = 0
  data-scan3d-rescan     = ok:bindings:1913单元:10ms:补扫1轮:覆盖1
```

## 四、抓到并修掉的真死角（无死角口径自己抓的）

对页面做 `?fast=1` 快扫复核时发现：
`data-scan3d-remaining` 永远剩 **70 个**节点扫不到 —— 根因不是扫描器，是**可视化扫描线边界**：
节点 y 范围是 ±10（H=20），而扫描线只走到 ±9.4 ⇒ 上下边缘各 35 个节点**永远在死角里**。

修法：扫描线边界改 ±**10.6**（盖过全部节点）。修后实测：

```
data-scan3d-remaining = 0
data-scan3d-missed    = 0     ← 整轮扫完的漏扫数，必须 0
data-scan3d-coverage  = 100
data-scan3d-dead      = 0
```

这条正好印证"无死角"不是口号：**它真的把 70 个死角抓出来并要求修掉**。

## 五、边界（如实）

- 无死角 = **扫描单元层面** 100% 钩住（覆盖率 1.0 + 0 死角 + 可视化 0 漏扫）；
  不代表"文件里每一行都语义理解过"，后者要靠 `security_pass` 的 line-level 扫描；
- 补扫仍是同一目标同一引擎重跑，不会换更细粒度目标（换目标=改 target，例如 tree: 指到更深目录）；
- 目前三份真实扫描覆盖率都是 100%，所以 UI 不会出现红死角；真出现会红并写 `dead_spot_count>0`。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
