# 95 · 能力包（cap_pack）：把"能力"从框架代码里解耦

> 第三轮蒸馏，来源：GBT-JXDWD 的 `sandbox/capability_protocol.py`
> 结论先行：**一份文档重复、一个机制值得吸**。

## 一、先说不吸的：`docs/pipeline_gate.md` 与我们的 `chain_kernel` 是同一件事

| v5 pipeline_gate.md | 我们的 `chain_kernel` |
|---|---|
| Step 0 任务登记 | Step 0 理解（目标原文落账） |
| Step 1 影响面分析（用 glob/grep 确认，不可猜） | Step -1 邻域感知（selfscan/body/pulse 读数） |
| Step 2 每个涉及文件必须 read | Step 1 计划（blueprint 生成任务） |
| Step 3 方案设计 | Step 1 计划（不自动过目） |
| Step 4 逐子任务执行 + 立即验证 | Step 2 执行（默认只读面）/ Step 3 验证 |
| Step 5/6 收口 | Step 4 固化 / Step 5 报告 |

**结论**：它那套"七个 box 图"就是我们已经落成的七步链，再吸一遍等于两套纪律打架 ⇒ 拒收。

## 二、吸的：清单发现 + 动态装载（改造后）

v5 的做法：目录里有 `capability.json` 就当一个能力模块（manifest: name/version/entry/actions/
auto_exec），运行时按 entry 起子进程。我们**不搬它的引擎**（我们已有 caps_registry + api 分派），
只取两件对我们有用的，落成第 380 位 `cap_pack`：

### 1) 外挂包发现：能力与框架代码解耦
```
packs/<包名>/capability.json    ← 丢一个目录 = 多一个能力
packs/<包名>/任意脚本
```
扫描根：`packs/` · `state/packs/` · 环境变量 `GBT_CAP_PACKS`（冒号/分号分隔）。
`op=discover` 列全部（含非法 manifest 的报错清单、重名检查），`op=info` 看单个，`op=status` 一句话。

### 2) 安全默认：只登记，不执行
- manifest 里 **`auto_exec` 默认 false** ⇒ `op=run` 直接 `refused`（说明要显式开）；
- 即使 `auto_exec: true`，**还要主人发 `process_execute` 票**（与 `body_open` 同一道门）；
- 子进程走上一轮蒸馏出的 `proc_guard`：超时杀整棵树 / 输出封顶 200KB / 环境变量净化。

### manifest 格式（我们认的）
```json
{
  "name": "example-hello",
  "version": "1.0.0",
  "description": "一句话",
  "language": "python",
  "entry": {"program": "python", "args": ["hello.py"]},
  "actions": ["greet"],
  "auto_exec": false,
  "timeout_s": 60
}
```

## 三、示例（已进仓）

| 包 | auto_exec | 用途 |
|---|---|---|
| `packs/example-hello/` | false | 演示"发现但不执行" |
| `packs/example-echo/` | true | 演示"可执行但仍要票"（无票时明确 denied） |

## 四、判据

`tests/test_cap_pack.py`（5 组 10 条全绿）：
发现 ≥2 个包 · info 读到 actions · auto_exec=false 被拒 · auto_exec=true 无票被 denied · status 可读。

## 五、为什么这条值得吸

- 以后加能力**不用改框架代码**（不碰 registry/api），减少"改一处漏一处"的五处纪律负担；
- 但默认不执行，危险动作仍走同一道 `process_execute` 门 —— **松耦合，不松门**。

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
