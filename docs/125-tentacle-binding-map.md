# 125 · 触手双向绑定 · 技术图纸（黑白 schematic 版）

日期：2026-11-02 · 入口：http://127.0.0.1:8766/tentacle3d/ · 控制台左栏「触手绑定」
截图：`outputs/screens-20261102/tp-dwg2-overview.png`、`tp-dwg2-select.png`、`tp-dwg2-coverage.png`

## 这一版是什么
按主人给的**黑白技术图纸**参考重做：深色图纸底、白色细线、PCB 模块板 + 24 针脚 + 密集垂直线束 + 右侧打字机清单 + 图框/尺寸标注；不再用发光/彩色。

## 图上怎么读
- **M01–M06 模块板**：按绑定数排序的前 6 根触手（domain:docs / project_context / filmkit / domain:tools / domain:recon / domain:tentacle），板上芯片格写的是它绑的资产样例，右侧 24 针出线；
- **中间密集垂线**：线束（每块板 24 根），落到 ASSET BUS；
- **页面/文档/代码/图片/其他 五个分组块**：资产按类型聚合，点一下过滤右侧清单；
- **右侧 TENTACLE INDEX / MANIFEST**：默认是触手索引（名字+绑定数），点模块后换成该触手绑定的资产清单（最多 252 行，每行可点，反向查它被哪些触手绑）；
- **CAP REGISTER 385/385**：左下角 385 个点阵，点开看 385 项能力逐项绑定数（全部已连）；
- **图框**：PROJECT / DRAWING / DATA / PAIRS / COVERAGE / REV，全部现读；
- **缩放**：滚轮或右上 ＋/－，FIT 复位；**拖动**平移；搜索框按路径/能力名过滤。

## 数据现状（2026-11-02 清理后）
| 指标 | 值 |
|---|---|
| 资产 | 1905 |
| 绑定对 | 3460 |
| 触手 | 393（域 8 · 能力位 385） |
| 能力覆盖 | **385 / 385，未连 0** |
| 断连 | 0 |
| 台账 | 追加式 `state/asset_bindings.jsonl` |

本次为补齐覆盖做过的事：126 项原本没有绑定的能力全部补到真实页面/实现文件（4 个 mcp_* 补到 `tools/mcp-demo-server.py` 与 MCP 文档），不留未连项；
清理时删掉的截图对应绑定用 `tentacle_bind.py prune` 剪掉 46 条，账不变量（账上资产都在盘上）保持成立。

## 维护
```powershell
.\pyembed\python.exe tools\tentacle_bind.py sweep .        # 新资产补绑（追加式）
.\pyembed\python.exe tools\tentacle_bind.py scan         # 体检：断连清单
.\pyembed\python.exe tools\tentacle_bind.py coverage .   # 穿透率
.\pyembed\python.exe tools\tentacle_bind.py prune        # 剪掉已不在盘上的绑定
```
接口：`GET /api/tentacle`（stats + coverage + tentacles + assets）。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
