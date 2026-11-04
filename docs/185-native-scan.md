# 185 · 原生扫描深度体检（2026-11-03）

> 用她自己的扫描器，不拿自写 UI 当结论。
> 本轮真实动作：`selfscan / file_hygiene / signature_guard / inventory / page_scan / cap_self / truth_scan / legacy_guard / capability_net / cross_scan / page_scan scan`。
> **扫到的问题当场修；修不了的如实留案，不粉饰。**

## 一、修掉的

| 发现 | 动作 | 复扫 |
|---|---|---|
| `selfscan` P0：缺 `store/wf_runs` | 补建 `gbt_allinone/store/wf_runs` | `selfscan clean` |
| 25 个 Python 文件带 UTF‑8 BOM（`api.py` / `caps_registry.py` / `policy.py` / hand_* 等），`file_hygiene` 报 unparsed | 逐文件去 BOM；`compileall gbt_allinone tools` 通过 | `file_hygiene clean` |
| `legacy_guard` 21 个浏览器 `LOG.old` | 清理 `gbt_allinone/store/native_browser/profile/**/LOG.old` | backup-files 0 |
| 页面绑定源缺失 | 补 `tools/bind_pages.py` + `state/page-bindings.json` | `page_scan status 20/20/0` |

## 二、复扫结果

| 原生扫描 | 结果 |
|---|---|
| `selfscan` | **clean**（routing/modules/store/audit/stub_gaps 在本轮范围内） |
| `file_hygiene` | **clean** |
| `signature_guard` | **clean** |
| `inventory` | **clean**（foreign=0） |
| `truth_scan` | **clean**（REAL=1 / FAKE=0 / HONEST_STUB=0） |
| `cap_self verify` | registry=410 / snapshot=410 / dispatched=410 |
| `page_scan status` | 页 20 / 绑好 20 / 未绑好 0 |
| `page_scan scan`（分片） | **359 绿 / 50 黄 / 0 红**；黄=缺依赖/需参数/需确认，不是红 |
| `page_scan scan`（分片） | **359 绿 / 50 黄 / 0 红**；黄=缺依赖/需参数/需确认，不是红 |
| `legacy_guard` | **legacy_found**：backup=0，**dup-doc-numbers=66 组**（只报不删，需人看内容） |
| `capability_net` | **entry_known 410/410、reachable 410/410**（修掉了“只认顶层同名 .py”的假阴性）；`verified(readonly) 5/410`、`has_test 2/410` 仍如实留案 |
| `cross_scan` | clean，但仍有 **latent 影子目录** `assets/`、`deploy/` 等（与包内同名） |
| `page_scan scan` | 改成**分片**：41 片×10 位 + 2 个超长分片单独补跑；**342 绿 / 47 黄 / 0 红**（41 片）＋尾部 17 绿 / 3 黄 / 0 红（20 位长超时补跑），合计 **359 绿 / 50 黄 / 0 红** |

## 三、还没解决的真缺口

1. **capability_net 已从 70/410 修到 410/410**：根因是入口只认 `gbt_allinone/<handler>.py`，漏了 api 分派键和 tools/tentacle 子目录；`verified(readonly) 5/410`、`has_test 2/410` 仍是真实留案；
2. **66 组重复文档编号**：需主人/人工决定保留哪一版，不能自动删；
3. **cross_scan 影子目录**：根 `assets/`、`deploy/` 与包内同名，属 latent，不是当前故障，但会让扫描读数分叉；
4. **page_scan scan 已分片完成**：不再整轮 180s 超时；重扫描用 `tools/page_scan_chunks.py` + `tools/page_scan_tail.py`；
5. **cap_smoke 全量探针**（410 项）另见 `state/cap-smoke/report.json`：`failed/op_mismatch/timeout` 仍有，需逐项看是真坏还是探针 op 选错。

## 四、口径

- `clean` 只代表**本轮覆盖范围**内没发现问题，不等于五维全量；
- `page_scan status` 只证明绑定关系无漏网，**不证明运行时全绿**；
- `page_scan scan` 超时就是超时，不写成通过；
- 不删除重复文档、不掩盖 latent 影子目录。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
