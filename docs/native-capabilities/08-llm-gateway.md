# 08 · LLM网关 (`llm`)

> 15+ 能力位 · 密钥链路由 · 自主编排 · 多模态端口 · 统一密钥网关
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 架构设计

```
    ┌─────────────────────────────────────────────────┐
    │              llm.unified (统一口)                 │
    │    框架内所有模块必须经此口调用模型                 │
    └──────────────────┬──────────────────────────────┘
                       │
    ┌──────────────────▼──────────────────────────────┐
    │            key_gateway (密钥网关)                 │
    │   链序/冷却/禁用/耗尽/换道 + 触手统一密钥铸造      │
    └──────────────────┬──────────────────────────────┘
                       │
    ┌──────────┬────────┼────────┬────────────────────┐
    │          │        │        │                    │
    ▼          ▼        ▼        ▼                    ▼
  DeepSeek   Kimi    OpenAI   Agnes             GenOffice
  密钥链      密钥链   密钥链   云端算力            本地桥
```

## 能力清单

| 能力位 | 类型 | 说明 |
|---|---|---|
| `llm_chat` | 只读 | 操控其他AI：DeepSeek/Kimi/OpenAI密钥链自动路由 |
| `llm_status` | 只读 | LLM网关密钥链配置状态（不调LLM） |
| `cloud_llm` | 只读 | 调用Agnes AI云端算力 |
| `autopilot` | 只读 | 自主编排环：目标→LLM拆解→本地校验→执行→自检→修复循环 |
| `brain_route` | 只读 | 大脑·路由维：意图→能力动态路由 |
| `brain_execute` | 只读 | 大脑·执行维：单能力直调或多能力并行 |
| `brain_verify` | 只读 | 大脑·验证维：触手肉眼验证 |
| `brain_health` | 只读 | 大脑·健康维：五维自检评分 |
| `brain_unify` | 只读 | 大脑·五维合一 |
| `think_loop` | 只读 | 推演环：完整心智循环七步 |
| `key_gateway` | 需授权 | 统一密钥网关：唯一密钥真源+触手密钥铸造 |
| `multimodal_port` | 需授权 | 多模态维度×触手密钥Y字端口 |
| `genoffice_bridge` | 需授权 | GenOffice AI线→统一密钥网关的本地OpenAI兼容桥 |
| `codex_chat` | 需授权 | 官方Codex同步对话 |
| `codex_status` | 只读 | 官方Codex只读状态 |
| `codex_tools` | 只读 | 官方Codex可用动态工具清单 |
| `train_ground` | 需授权 | 回炉训练场：直达万能插训练大模型 |

## 密钥链路由

```python
import gbt_allinone as gbt

# 自动路由：DeepSeek → Kimi → OpenAI
result = gbt.run_task("llm_chat", {
    "prompt": "解释量子计算的基本原理",
    "max_tokens": 500
})
# 返回: {ok, reply, provider: "deepseek", model: "deepseek-flash", drift: false}

# 指定provider
result = gbt.run_task("llm_chat", {
    "prompt": "...",
    "provider": "kimi"
})
```

**密钥链纪律**：
- 链序优先级自动路由
- 冷却：密钥用过冷却期不复用
- 禁用：错误密钥自动标记禁用
- 耗尽：全链耗尽如实报`needs_dependency`
- 换道：主链路不通自动换备用链路

## 自主编排环（Autopilot）

```python
result = gbt.run_task("autopilot", {
    "goal": "扫描example.com并生成安全报告",
    "max_rounds": 5
})
```

**流程**：
1. LLM拆解目标为工作流节点
2. 本地校验（LLM只是提案人，无权限）
3. 执行工作流
4. 自检结果
5. 失败→修复循环（轮数上限防失控）

**纪律**：
- LLM方案必须落在已注册能力上（未注册一律拒绝）
- 全程审计+产出走管线带钢印
- 空回复重试+JSON截断容错

## 统一密钥网关（key_gateway）

```python
# 状态
gbt.run_task("key_gateway", {"op": "status"})

# 密钥链清单
gbt.run_task("key_gateway", {"op": "keys"})

# 铸造触手统一密钥
gbt.run_task("key_gateway", {"op": "mint", "label": "tentacle-01"})

# 验证密钥
gbt.run_task("key_gateway", {"op": "verify", "key": "gbtv8-..."})
```

**密钥格式**：`gbtv8-<32hex>`，库内只存blake2b摘要，不存明文。

## 多模态端口（multimodal_port）

```python
# 端口状态
gbt.run_task("multimodal_port", {"op": "status"})

# 目录
gbt.run_task("multimodal_port", {"op": "catalog"})

# 探测端点（真出网）
gbt.run_task("multimodal_port", {"op": "probe", "dim": "vision"})
```

**五维度**：text / vision / image / video / code

**七道闸**（Y0-Y6机械把关）：
- 请求在一处分叉、一次只走一臂
- 独立臂（维度专属密钥）/ 共享臂（共享密钥对按维度分账）
- 返回值永不含明文（只key_id/掩码/指纹）

## 安全边界

- `external_llm` 授权：把当前任务数据发送到外部大模型服务
- `key_gateway.materialize` 是唯一返回明文密钥的路
- GenOffice桥 `serve` 不在能力位上（常驻会挂住调用方）

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
