# 10 · 安全 / 黑客大脑 (`security`)

> 5+ 能力位 · 攻击面测绘 · 漏洞扫描 · 利用链 · 蓝队防御 · 红蓝双模
>
> 只扫自有代码，只对授权目标动手。
>
> 开发者：自由的风 · 本署名不可删除、不可篡改归属

---

## 架构设计

```
    ┌──────────────────────────────────────────────┐
    │              黑客大脑（红蓝双模）              │
    ├──────────┬──────────┬──────────┬─────────────┤
    │  红队     │  扫描     │  利用链   │  蓝队       │
    │ sec_surface│ sec_scan │ sec_chain│ sec_defenses│
    │ 攻击面测绘 │ 漏洞检测  │ 路径推演  │ 防御验证    │
    └──────────┴──────────┴──────────┴─────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   sec_llm         │
                    │ 独立大模型+独立密钥 │
                    │ 专用通道不混用      │
                    └───────────────────┘
```

## 能力清单

| 能力位 | 说明 |
|---|---|
| `sec_surface` | 攻击面测绘（输入/网络/文件/入口四维向量+风险评分） |
| `sec_scan` | 漏洞扫描（OWASP Top 10 + CWE模式库，25条检测） |
| `sec_chain` | 利用链构建（漏洞→攻击路径→影响评估） |
| `sec_defenses` | 蓝队防御验证（检查防御是否真实生效） |
| `sec_llm` | 黑客大脑推理引擎（独立大模型+独立密钥ABLITERATION） |
| `scan_cap` | 统一扫描位（蒸馏20个星标最高开源扫描器） |
| `offense_ops` | 自主渗透编排（多智能体分工+五道闸） |
| `llm_redteam` | LLM红队测试 |
| `pentest_distill` | 渗透知识蒸馏 |

## 25条检测模式库

### 密钥泄露（gitleaks智慧）

| 模式 | 检测 |
|---|---|
| AWS Key | `AKIA[0-9A-Z]{16}` |
| GitHub Token | `gh[pousr]_[A-Za-z0-9]{36}` |
| LLM API Key | `sk-[A-Za-z0-9]{20,}` |
| 私钥块 | `-----BEGIN (RSA\|EC\|OPENSSH) PRIVATE KEY-----` |
| Slack Token | `xox[baprs]-...` |

### 危险调用（bandit智慧）

| 编号 | 检测 |
|---|---|
| B602 | `subprocess` 的 `shell=True` |
| B108 | `tempfile.mktemp` |
| B101 | `assert` 用于安全校验 |
| B324 | 弱哈希 `md5`/`sha1` |
| B501 | `requests` 的 `verify=False` |
| B201 | Flask `debug=True` |
| B701 | Jinja2 无转义 |

### 逻辑缺陷（semgrep智慧）

| 检测 |
|---|
| `str.format` 拼接SQL |
| `chmod 777` |

## API参考

### 攻击面测绘

```python
import gbt_allinone as gbt

result = gbt.run_task("sec_surface", {"target": "."})
# 返回: {
#   ok, vectors: {
#     input: [{file, line, kind}],      # 用户输入点
#     network: [{file, line, kind}],    # 网络出入口
#     file: [{file, line, kind}],       # 文件操作
#     entry: [{file, line, kind}]       # 入口点
#   },
#   total_vectors: 4117,
#   risk_score: 0.62
# }
```

实测：V8仓库4117向量。

### 漏洞扫描

```python
result = gbt.run_task("sec_scan", {"target": "."})
# 返回: {
#   ok, findings: [{
#     pattern: "B602",
#     severity: "high",
#     file: "gbt_allinone/xxx.py",
#     line: 123,
#     snippet: "subprocess.call(cmd, shell=True)",
#     fix: "改用列表参数 shell=False"
#   }],
#   scanned_files: 598,
#   ms: 6000
# }
```

实测：6秒全仓扫描。

### 利用链构建

```python
result = gbt.run_task("sec_chain", {"findings": [...]})
# 返回: {
#   ok, chains: [{
#     entry: "web_input",
#     steps: ["未过滤输入", "拼接SQL", "数据库读取"],
#     impact: "数据泄露",
#     likelihood: 0.7
#   }]
# }
```

### 蓝队防御验证

```python
result = gbt.run_task("sec_defenses", {})
# 返回: {
#   ok, defenses: [
#     {name: "危险门禁", active: true},
#     {name: "内网护栏", active: true},
#     {name: "管线门禁", active: true},
#     {name: "注册表完整性", active: true},
#     {name: "写保护", active: true}
#   ],
#   score: "5/5"
# }
```

实测：V8真实防御矩阵5项，5/5全绿。

### 黑客大脑推理

```python
result = gbt.run_task("sec_llm", {
    "prompt": "分析这段代码的安全风险：..."
})
# 独立通道：abliteration.ai无限制模型
# 专用ABLITERATION_API_KEY，与通用LLM并行不混用
```

**三模型实测**：
| 模型 | 速度 | 说明 |
|---|---|---|
| abliterated-model | 157tk/s | 快 |
| large | 67tk/s | 中 |
| large-v2 | 54tk/s | **默认——最快最省** |

## 误报治理

1. **占位符豁免**：`YOUR_KEY_HERE` / `xxxxx` / `<token>` 不报
2. **模式库自引用豁免**：扫描器自己的模式定义文件不报
3. **上下文判断**：测试文件里的假密钥不报

## 安全边界

**只扫自有代码**：`sec_scan` 的 target 必须在框架目录内，越界即拒。

**五道闸（offense_ops）**：
1. 授权——没范围不动手
2. 不可回滚先问
3. 凭据只报已配
4. 只对授权目标出网
5. 无痕即不存在

**禁用名单**（按名禁用，无执行路径）：
- 付费墙绕过
- 会话/数据劫持
- 无授权远程接管
- 键鼠监控
- 屏幕窃取
- 设备接管
- 渗透攻击（非授权目标）
- 资产冻结要挟
- 凭证窃取
- 社工钓鱼

> 拒绝的永远只是具体行为的风险，不是这个人：说清为什么不行，再给出怎样才行。

> 开发者：自由的风 · GBT小土豆V8 · 独立私人框架，与任何企业公司无关
