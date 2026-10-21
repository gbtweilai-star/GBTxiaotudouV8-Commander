# 变更记录

格式：`日期 · 版本 · 一句话`。只记**对外可见**的变化。

## 2026-10-21 · 第二批公开（GBT天真 / 五维合一 / 多域监控）

### 新增文档（每页都有可复跑的数据源脚本，不是手抄）
- `docs/10-gbt-tianzhen.md` —— **GBT天真**（`comfy_native`）：27 个原生算子，其中 **18 个与 ComfyUI 同名同契约**；
  对齐契约面 1495 个节点（覆盖率 1.2%，1477 个未接按原因分类）；离线 `validate` 正反例；写面真跑 + fail-closed 反证。
- `docs/11-five-dim.md` —— **五维合一**（`brain_unify`）：route → execute → verify → health 顺序串链；
  五条真跑回执，含两条**被门挡住**的完整拒绝回执（`missing_scopes` 点名）。
- `docs/12-multidomain-monitor.md` —— **多域监控**：29 域 236 位只读位逐位真调，221 通过 / 15 要票（按票种点名）/ 未跑 105；
  基线 + `--diff`：立完基线后改了三处代码，整面重跑**回归 0 / 修好 0**。
- 新增数据：`data/gbt-tianzhen-live.json` · `data/five-dim-live.json` · `data/multidomain-monitor-live.json`
  （分别由 `gen-native-live.py`、`multi-domain-monitor.py --out` 生成）。
- 新增图：`assets/fig-tianzhen.png` · `assets/fig-monitor.png`。

### 修复（这批文档逼出来的真问题）
- **契约保真三处**（`comfy_native`）：`LoadImage` 只认内部别名 `path`（ComfyUI 叫 `image`）、把落点 `out` 当必填、
  连边按字面名取产物（`image->image` 取不到 `out`）⇒ 修到**标准 ComfyUI 图能过校验并真跑通**，反例仍被抓。
- **拒绝回执被省掉**（`brain_exec`）：五维合一的执行层只留 `status=denied`，缺的作用域与原话全丢 ⇒ 现在两层都透传。
- **监控读数被省掉**（`multi-domain-monitor`）：`missing_scopes` 嵌在 `result` 层而只读了顶层，15 条拒绝全变 `(未报)` ⇒ 两层都读并从原话兜底提取。
- **图鉴文案落后于盘**：`comfy_native` 写「18 个算子 / 962 把节点」，盘上现读 **27 / 1495** ⇒ 文案改为现读值并注明口径。

## 2026-10-21 · v83 发布版

### 模型
- 现役权重 `v83`（bf16 合并，15.25 GB，Qwen2-7B 底座 + LoRA r=64）。
- 线上评测：335 题 · mean cov **0.9908** · PASS45 **99.10%** · 零覆盖 2。
- 已知未过：`health`（样本不足）、`voice_studio`（判据与数据不同源）。

### 文档
- 首次公开发布：能力位全量 341 位 / 30 域，逐位说明由注册表现读生成（`data/capabilities.json`）。
- 补：模型卡、架构（单门 + 授权 + 审计）、评测口径、部署路径。

### 修复（发布前）
- **端点 502 真因**：客户端传友好别名而 vLLM 只认 served id → 统一按现役 served id 传参。
- **原生车道选不上**：选路只看环境变量、看不见保险箱里的钥 → 显式点名时回退保险箱取钥。
- **缩容太急**：端点 `idleTimeout=5s` 导致请求排队挂死（实测 90s 队列不动） → 对齐到 300s，实测 150s 内 worker 稳定在岗。
- **挂热是死路**：心跳硬编码打一个不存在的本机桥 → 改为「先本机桥，不通直打端点」并把走哪条路记进日志。

## 2026-10-18 及以前（内部迭代）
- 多轮容量/配方实验（LoRA r=16→64、词表补齐、bf16 合并、量化对比）。
- 能力位从 172 扩到 341；评测从 118 题扩到 335 题。
- 详见仓库历史（本页只保留对外可读的摘要）。
