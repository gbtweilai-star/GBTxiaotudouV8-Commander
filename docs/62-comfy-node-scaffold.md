# 62 · 补节点脚手架（2026-11-01）

> 按清单补节点时，每个节点都是同一形态：`_n_<Name>(inputs, ctx)` + `NODES` 注册行。
> 手写 15 个能忍，补 800 个不能忍；而且手抄最容易出错（少一个 `?`、少一个 `writes`）。

---

## 一、结构（不往主模块追加代码）

```
tools/comfy-add-node.py            # 生成器（三族模板：image / mask / passthrough）
gbt_allinone/tools/comfy_nodes_extra.py   # 生成节点的落点（独立模块）
gbt_allinone/tools/comfy_native.py        # 末尾 import extras 并 NODES.update(...)
```

为什么独立模块：`comfy_native.py` 已经很大，**自动往主模块追加代码是维护灾难**。

## 二、用法

```powershell
py -3 -X utf8 tools/comfy-add-node.py --name ImageFlipX --family image --dry-run
py -3 -X utf8 tools/comfy-add-node.py --name ImageFlipX --family image --desc "..." --apply
```

生成的骨架里留 `# TODO 实现`，人填完跑冒烟即可。

## 三、实测（第一个用脚手架补的节点）

`ImageFlipX`（水平翻转）：

```
① 生成骨架（image 族，in [image, out]，out [IMAGE]，writes=True）
② 填实现：PIL ImageOps.mirror
③ workflow：EmptyImage(16×8) → ImageFlipX ⇒ ok=True，产物 2 个
④ 节点数 55 → 56
```

**顺带修了生成器的坑**：骨架用到 `pathlib` 但模板没 import ⇒ 第一次跑报
`NameError: name 'pathlib' is not defined`（回滚机制正确删掉了半成品）。
现在模板与 extras 头都显式 `import pathlib`，判据 [9] 钉住"脚手架节点能跑通"。

## 四、判据

`tests/test_comfy_engine.py` 第 [9] 组：
- `ImageFlipX` 在 `NODES` 里（说明 extras 合并生效）
- 用它在 workflow 里真跑一次，必须 ok

## 五、接下来补节点就快了

拿到秋叶真快照后，`op=harvest` 出清单 → 每条：
`comfy-add-node.py --name X --family <族> --apply` → 填实现 → 跑判据。每节点约 1 分钟。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

---

## 六、批量模式：`--from-harvest`（一次生成几十个**待审**骨架）

拿到秋叶真快照后，`op=harvest` 会给出 `useful_list`；这时用批量模式：

```powershell
py -3 -X utf8 tools/comfy-add-node.py --from-harvest
# → state/tmp/comfy-scaffold-<时间>.py   待审骨架（**不 import**）
# → state/comfy-scaffold-<时间>.md       待办清单（复选框）
```

**为什么不直接追加进 `comfy_nodes_extra.py`**：骨架函数体是 TODO，直接进去会变成
「**能跑但做错事**」的节点（image 族会原样落盘、mask 族会原样输出）——那是最坏的一种假绿。
所以批量模式只生成**待审文件**，逐个人工填实现、再合并、再跑判据。

实测（用模拟清单 3 个名字验证流程）：

```
生成骨架 3 个 → state/tmp/comfy-scaffold-20261101-063416.py
待办清单      → state/comfy-scaffold-20261101-063416.md
跳过 0 个
（随后清掉演示件，并用真实 op=harvest 覆盖回空 useful_list，不留假清单）
```

## 七、三档用法（从少到多）

| 场景 | 命令 |
|---|---|
| 补 1 个（已知道名字） | `--name X --family image --apply` → 填实现 |
| 补一批（有真清单） | `--from-harvest` → 逐个填 → 合并 → 跑判据 |
| 只想看看 | `--name X --family image --dry-run` |
