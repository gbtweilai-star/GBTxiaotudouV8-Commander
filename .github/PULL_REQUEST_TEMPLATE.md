<!--
  本模板与 AGENTS.md 的纪律对齐：只写跑出来的东西，不写"大概/应该"。
  不适用的条目请写「不适用」并说明原因，不要删条目。
-->

## 这个 PR 改了什么

<!-- 一句话说清。改了多处就分条列。 -->

## 根因（不是现象）

<!--
  为什么必须写：本仓的历史教训是"改了现象、根因还在"。
  例：不是"图上的数字旧了"，而是"渲染脚本的 data_dir 没回退到根 data/，
      找不到就静默跳过，所以图永远停在旧文件上"。
-->

## 怎么验证的（贴回执）

<!-- 命令 + 真实输出。没有回执的"已验证"不算验证。 -->

```text
$ ...
```

## 影响面

- [ ] 动到了能力位（caps_registry / 某位的 desc 或 handler）
- [ ] 动到了文档口径（README / docs / 图）
- [ ] 动到了数据快照（data/*.json）
- [ ] 只动界面/样式
- [ ] 只动测试/CI

<!-- 勾了前四项的，请确认：docs/capabilities/*.md 是否需同步？ -->

## 自检清单

- [ ] 全量语法通过（`python -c "import py_compile,pathlib;[py_compile.compile(str(p),doraise=True,cfile=None) for p in pathlib.Path('.').rglob('*.py') if not {'pyembed','__pycache__','state','outputs'} & set(p.parts)]"`）
- [ ] 受影响的位跑过一次**真 op**，错误从「路径不存在」变成了「真问题」（或已修好）
- [ ] `python tools/codex-scripts/sync-readme-figures.py --check` 全绿
- [ ] 若改了页面/图：已走 `mirror_scan → simulate → parity → rehearse → release`（或说明为何不适用）
- [ ] CI 绿（不是"应该会绿"）

## 边界 / 已知未做

<!--
  故意没做的、做不了的，写在这里并说明阻塞项。
  禁止把"没做"包装成"已完成"。
-->

## 关联

<!-- Closes #编号 / 相关 docs -->
