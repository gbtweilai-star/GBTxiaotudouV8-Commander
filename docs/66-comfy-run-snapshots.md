# 66 · 可复跑快照：每张图都留指纹（2026-11-01）

> 以前跑过的图只留在 `store/comfy_native/runs.jsonl`（一行摘要），
> **"这张图当时到底怎么跑的、产物是不是同一个"** 复现不了。这一轮补上。

---

## 一、每跑一张图，落一份快照

`state/comfy-runs/<workflow_hash>.json`：

```json
{"at": "...", "hash": "f05d968414c5", "ok": true,
 "workflow": {...原图...},
 "products": [{"path": "...", "sha256": "...", "bytes": 123}],
 "seconds": 0.02, "nodes": 2,
 "gates": [{"id": "n1", "pass": true, "problems": []}],
 "deps": {"PIL": "13.0.0", "numpy": "2.5.4", ...}}
```

hash = 图规范化后的 sha1 前 12 位 ⇒ **同一张图永远同一个 hash**，可直接当回归用例名。

## 二、两个只读 op

| op | 作用 |
|---|---|
| `runs` | 列出跑过的图（时间倒序）：hash / 节点数 / 产物数 / 耗时 |
| `replay` | 给 hash 或文件，**重跑一遍并比对产物 sha256** |

实测：

```
run     → snapshot f05d968414c5（2 节点 / 2 产物）
replay  → reproducible=True · same=2 · diff=0
runs    → count=1，最近一条 {hash, ok, nodes, products, seconds}
```

**reproducible 的意义**：同图同参若 sha256 不一致，说明存在不确定性（时间戳写进图、
随机种子、压缩器版本差异）—— 这类问题以前只能靠"感觉一样"，现在能抓。

## 三、判据（`test_comfy_engine` 第 [17] 组 3 条）

- 运行落快照（有 hash）
- 复跑结果可复现（sha256 全同）
- `runs` 列表能读

## 四、边界

- 快照只记录**我们格式**的图（原生图会先被 `import` 转成我们的格式再落）；
- 产物被删/改后再 replay，`diff` 会如实列出 old/now，不会报"可复现"；
- 快照目录不自动清理（它是对账资产），需要清理时手动删 `state/comfy-runs/`。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
