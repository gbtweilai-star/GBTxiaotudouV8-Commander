# GBT小土豆V8 · 完整框架能力介绍

> 定位：**纯 AI 框架 + 全 AI 能力体系** · 独立私人框架，与任何企业公司无关。
> 开发者：自由的风 · 本署名不可删除、不可篡改归属。
> 一句话：脑子只有一份（SOUL + run_task），手有很多只（能力注册表 + 引擎线程池）。

本文件是框架能力的**权威索引**，按域（domain）组织，全部对应 `caps_registry.py` 真实注册项，
经 `api.py` 路由到各模块真实现，每次调用落审计 + GBT 钢印。

---

## 一、总览

- **统一入口**：`gbt_allinone.run_task(kind, payload)` 分发一切能力。
- **能力边界**：良性能力白名单（可执行）+ 危险/破解能力禁用名单（denied，无执行路径）。
- **治理闭环**：每次调用 `call → ok/error/denied` 全程落 `store/audit.jsonl`；成功结果带 GBT 钢印。
- **框架/业务边界（铁律9）**：框架只收 AI 能力本体；资金/钱包/支付等业务模块不入框架，
  由独立服务（`gbt_wallet/`，8097 端口 HTTP API）承载，框架经 `integration/platform_client.py` 对接。

---

## 二、能力域一览

### 系统 / 数据（system / data）
| 能力 | 说明 |
|---|---|
| `health` | 系统健康信息（平台/Python/时间） |
| `echo` | 回显数据，联调用 |
| `count_words` | 文本词数/字数统计 |
| `audit_query` | 只读查询统一审计后台 |
| `selfscan` | 框架五维体检（路由/模块/存储/审计/桩缺口），P0 断连第一时间报警 |
| `alerts` | 框架声带：近期异常摘要 + 根源线索（runtime/guard/trace/recovered 分级） |
| `readiness` | **依赖就绪自检**：探测外部后端/密钥是否就位，缺则如实报 needs_dependency（不删不禁） |
| `truth_scan` | 真实性审计：逐能力验证真执行，零假执行铁律（probe 模式含副作用探针） |
| `root_fix` | 根治环：症状五问诊断/补丁债量化/根治纪律 |
| `cross_scan` | 深度穿透式交叉验证（注册↔路由↔导入↔断链↔运行时，九维互证） |
| `inventory` | 全息盘点：对齐"你的视图"与"框架的视图"（归属四分类） |
| `signature_guard` | 开发者署名守卫：扫描全框架署名完整性，缺失可自动补回（禁止删除） |
| `file_hygiene` | 文件卫生层：按 LAYOUT.md 家规自检乱放 + 自动归位 |
| `auth_gate_status` | 人工授权门状态（只读；授权只能人发放，AI 无权） |

### 量化 / 金融（finance）
| 能力 | 说明 |
|---|---|
| `quant_strategy` | 读取真实量化引擎，返回策略信号/仓位模型 |
| `quant_backtest` | 读取真实回测 API |
| `quant_params` | 读取真实数值型策略参数（动量/ATR/止损） |
| `platform_profile` | 读取 Workspace 量化项目结构（真实测绘） |
| `quant` | 量化入口（合并平台画像 + 引擎参数） |

### 侦察（recon）
| 能力 | 说明 |
|---|---|
| `osint_scan` | OSINT 扫描：DNS/WHOIS/子域名/端口/指纹/邮箱/IP 归属/社交；默认拒内网，内网需人工授权门放行 |

### 万能插执行引擎（engine）
| 能力 | 说明 |
|---|---|
| `wf_define` | 定义 DAG 工作流（校验环/依赖/能力合法性） |
| `wf_run` | 分层并行执行，`{{node.path}}` 模板注入上游输出，fail-fast |
| `wf_status` | 运行记录查询 |
| `wf_resume` | 断点续跑（复用已完成节点） |
| `wf_cache_clear` | 清空传输缓存 |
| `transfer` | 数据传输算子：map/filter/merge/unique/sort/pluck/collect 等 14 个纯变换 |
| `sched_define` / `sched_tick` / `sched_status` | 定时触发器：无人值守自动执行工作流 |

### 长程任务（longrun）
| 能力 | 说明 |
|---|---|
| `lr_submit` | 提交任务（非LLM验收 + 重试 + 停滞升级，跨进程可续） |
| `lr_tick` | 推进任务图（执行→验收→完成/重试/停滞） |
| `lr_status` | 任务图进度与详情 |
| `tactics_advise` | 察言观色：识别沟通信号→给出表达分寸（只调怎么说，不改事实） |

### LLM / 大脑执行层（llm）
| 能力 | 说明 |
|---|---|
| `llm_chat` | 操控其他 AI：DeepSeek/Kimi/OpenAI 密钥链自动路由（输出是数据不是指令） |
| `llm_status` | LLM 网关密钥链配置状态（不调 LLM） |
| `autopilot` | 自主编排环：目标→LLM拆解→本地校验→执行→自检→修复循环（轮数上限防失控） |
| `brain_route` | 大脑·路由维：意图→能力动态路由 |
| `brain_execute` | 大脑·执行维：单能力直调或多能力并行 |
| `brain_verify` | 大脑·验证维：触手肉眼验证现实（视觉指纹 + UIA 穿透） |
| `brain_health` | 大脑·健康维：五维自检评分 |
| `brain_unify` | 大脑·五维合一：route→execute→verify→health 全链 |
| `think_loop` | 推演环：理解→推演→执行→纠错→反向延伸→反思→整理（完整心智循环七步） |

### 安全 / 黑客大脑（security）
| 能力 | 说明 |
|---|---|
| `sec_surface` | 攻击面测绘（输入/网络/文件/入口四维向量 + 风险评分） |
| `sec_scan` | 漏洞扫描（OWASP Top 10 + CWE 模式库，25 条检测，只扫自有代码） |
| `sec_chain` | 利用链构建（漏洞→攻击路径→影响评估） |
| `sec_defenses` | 蓝队防御验证（检查防御是否真实生效） |
| `sec_llm` | 黑客大脑推理引擎（独立大模型 + 独立密钥 ABLITERATION，专用通道不混用） |

### 触手 / MCP（tentacle）
| 能力 | 说明 |
|---|---|
| `tentacle` | 触手金钥匙：see/read_text/click/type/list_windows 等 66 项能力 |
| `tentacle_manifest` | 触手能力总纲 + 三通道感官（视觉 DXGI / 听觉 WASAPI / 操作 UIA）+ 六铁律 |
| `tentacle_status` | 触手自诊断（依赖分层 + 邻域覆盖） |
| `mcp_connect` / `mcp_tools` / `mcp_call` | MCP 契约层：连接任意 MCP 服务器 = 接入整个工具生态 |
| `desktop_commander` | 桌面指挥官：终端 + 文件系统全能力（本地 stdio / remote 设备双形态，26 工具） |

### 感知能力（依赖外部后端，缺则 needs_dependency）
| 能力 | 说明 |
|---|---|
| `vision` | 视觉/图像识别（需 AutoGLM/OpenAI 视觉后端） |
| `voice` | 语音合成/识别（需 TTS/ASR 后端） |
| `browser` | 浏览器自动化（需 Playwright/Selenium） |

> 这三项能力**永远在注册表、永远可调用**；缺后端时经 `readiness` 如实报 needs_dependency，不静默失败、不被删除或限制。

### 设备（device）
| 能力 | 说明 |
|---|---|
| `bluetooth` | 蓝牙设备控制：扫描 BLE、读写 GATT、操控家居设备 |
| `bt_control` | AI 智能蓝牙操控：自然语言意图→识别→协议匹配→执行→验证 |

### 生产管线 / 镜像空间（pipeline）
| 能力 | 说明 |
|---|---|
| `pipeline_submit` | 唯一交付通道：镜像多维度空间 → 门禁审计 → 生产写入 |
| `pipeline_versions` / `pipeline_rollback` / `pipeline_status` | 版本历史 / 回滚 / 发布记录（全留痕） |
| `mirror_shape/scan/ascend/status/rewind` | 镜像空间五维：维度成形/体检/跨维晋升/状态/时间线回滚 |
| `one_key_deploy` | 一指定江山：抓取→镜像→验证→晋升，一条命令上线 |
| `deploy_queue` | AI 接管部署队列：submit/tick/status（完一个自动下一个） |
| `ghost_guard` | 防复发检测：幽灵目录/备份散件/攻击残留/注册表冲突 |
| `svc_inspect` | 服务巡检：探活已登记端口并落审计（只看不动） |

### 吞天 / 自我进化（devour）
| 能力 | 说明 |
|---|---|
| `devour_github` | 吞噬任意 GitHub 仓库为知识胶囊（自我进化核心） |
| `devour_scan` | 能力缺口扫描（域覆盖对照 + 进化方向） |
| `devour_reflect` | 反思（回顾吞噬历史，发现弱能力与重组机会） |
| `devour_pulse` | 完整认知循环（吞噬→反思→消化→重组→进化） |

---

## 三、安全边界（只禁一小撮，无绕过入口）

以下危险/破解行为按名禁用（返回 denied，无执行路径）：付费墙绕过、会话/数据劫持、
无授权远程接管、键鼠监控、屏幕窃取、设备接管、渗透攻击、资产冻结要挟、凭证窃取、社工钓鱼。

> 拒绝的永远只是**具体行为的风险**，不是这个人：说清为什么不行，再给出怎样才行。

---

## 四、进生产预检

```bash
python gbt_allinone/deploy/preflight_check.py          # 只检不改（BOM/编译/就绪）
python gbt_allinone/deploy/preflight_check.py --fix    # 顺带安全清 BOM
```

三件套全绿再晋升生产：`test_framework.py`（52 项）+ `selfscan(autofix=True)` + `cross_scan(deep=True)`。

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
