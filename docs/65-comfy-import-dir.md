# 65 · 批量导入：一个目录的图，一次说清能不能跑（2026-11-01）

> 秋叶版机器上通常有一整个 workflow 文件夹。一张张导不现实，所以加 `op=import_dir`。

---

## 一、做什么

```python
run_task("comfy_native", {"op": "import_dir", "folder": "D:/秋叶/workflows", "limit": 200})
# → {files, runnable, needs_gpu, unknown_only, invalid, samples...}
```

对目录里每个 `.json`：**转换（原生格式也能认）→ 校验 → 四分类**：

| 类 | 判据 | 意味着 |
|---|---|---|
| `runnable` | 全部节点都在我们的 `NODES` 里，无未知节点 | 本机**能直接跑** |
| `needs_gpu` | 有节点在契约里但我们没实现（模型/采样/VAE） | 要 GPU 与权重 |
| `unknown_only` | 有既不在原生表也不在契约的节点 | 可能是前端节点（Reroute/Note）或插件节点 |
| `invalid` | 不是 JSON / 读不出 nodes / 缺必填 | 坏文件 |

只读：**不执行任何图**；结果落 `state/comfy-import-manifest.json`（含逐文件明细 rows）。

## 二、实测（合成目录：可跑 / 要 GPU / 坏文件 各一）

```
files 3 · runnable 1 · needs_gpu 1 · unknown_only 0 · invalid 1
runnable   → ok_workflow.json
needs_gpu  → gpu_workflow.json · needs: [KSampler]
invalid    → broken.json（不是 JSON）
```

## 三、顺手修的一个真问题

`folder` 传相对路径时按**调用方 CWD** 解析，而调用方不一定是仓库根 ⇒ 第一次跑报「不是目录」。
现在**相对路径一律按仓库根解析**（`_ROOT / folder`），绝对路径照旧。

## 四、判据（`test_comfy_engine` 第 [16] 组 3 条）

- 批量导入能读
- 分类正确（1 可跑 / 1 要 GPU / 1 坏）
- manifest 落盘

## 五、边界

- `limit` 默认 200（防一次扫几万个文件）；
- 只做**校验**，不做"自动补节点"——补节点仍走 `harvest → 脚手架 → 填实现`；
- `needs_gpu` 的依据是"契约里有、我们没实现"，不是"一定有 GPU 就能跑"（可能还缺权重文件）。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
