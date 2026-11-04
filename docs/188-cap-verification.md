# 188 · 能力核实台账 + 旧物清理（不是字面量标绿）

> **口径时点**：本文记录 **410 位**注册表时期的读数（verified_readonly 288/410、has_test 301/410）。现役注册表已到 **427 位**，本文数字仅作当时快照，不代表当前状态。

> 主人：66 组重复文档、latent 影子目录、`verified(readonly) 5/410`、`has_test 2/410` 都要清理。
> 这里只写**有证据的清理**：重复文档归档、核实台账由真实探针/测试引用生成。

## 一、66 组重复文档 → 已归档

- `docs/*.md` 同一数字前缀两页，共 **66 组 / 132 文件**；
- 每组保留**较新一版**在 `docs/` 顶层，旧版移到 [`docs/legacy/`](legacy/)；
- 内容不删，只换位置；`docs/legacy/README.md` 说明来源；
- 复扫：`legacy_guard = clean`，`dup-doc-numbers.groups = 0`。

## 二、核实台账：`state/cap-verification.json`

不再用 `GREEN` / `TESTED` 两个字面量集合冒充覆盖：

| 栏 | 来源 | 真机 |
|---|---|---|
| `verified_readonly` | `state/cap-smoke/report.json` 里 **safe 且 only-read 探针 responded** 的行 | **288/410** |
| `has_test` | `tests/` + `gbt_allinone/tests/` 里**真实引用该能力位名** | **301/410** |

`capability_net` 现在读这份台账：
```
entry_known 410/410 · reachable 410/410
verified(readonly) 288 口 / 288 位
has_test 301/410
penetrate_ready 288 口 / 288 位
```
不是 5/410、2/410。仍未到 410：未核实/不安全/无测试引用如实留案，不硬凑。

## 三、latent 影子目录

`assets/`、`deploy/` 是**真实项目根目录**（文档截图、云部署 mesh），不是包内同名影子；
`cross_scan` 标 latent 不等于故障。**没有为了扫描好看去搬走真实资产**；保留并在扫描口径里注明。

## 四、验收

[`tests/test_cap_verification.py`](tests/test_cap_verification.py)：
- 台账 410 位、verified≥260、has_test≥250、非 safe 不标只读；
- `capability_net` entry 410/410、verified 不再是 5、has_test 不再是 2；
- `docs` 顶层无重复编号；`legacy_guard clean`；`docs/legacy` 存在。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
