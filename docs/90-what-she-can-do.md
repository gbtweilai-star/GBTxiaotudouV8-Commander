# 90 · 她能干嘛：30 域 410 位能力（现读版）

> 本文由 `gbt_allinone/caps_registry.py` **实时生成**（不是手写宣传语）。
> 想知道某一位到底能干什么，看命令 `gbt.run_task('<名字>', {'op':'status'})`。

## 一、一句话

**给她一句话，她自己选能力位、过授权门、真跑、留审计、出结果。**

```python
import gbt_allinone as gbt
gbt.run_task("cap_self", {"op": "brief"})   # 她现读的自述：我能干什么、部署在哪
```

## 二、30 个域（按能力数量排序）

| 域 | 能力数 | 代表能力 | 一句话 |
|---|---|---:|---|
| **创作（视频/图像/音乐/剧本）** | 57 | `viral_forge`, `drama_forge`, `taste_guard`, `forge_mastery` | 爆款拆解·克隆配方 |
| **系统（自检/编排/修复）** | 56 | `mirror_stage`, `health`, `selfscan`, `alerts` | 镜像工作空间（2026-11-01 主人口径 |
| **大模型（本机/云端/上下文）** | 42 | `codex_status`, `codex_tools`, `codex_thread_new`, `codex_turn_send` | 官方 Codex 只读状态 |
| **触手（总指挥/脉冲/覆盖）** | 30 | `remote_controller`, `desktop_commander`, `tentacle`, `tentacle_manifest` | 远程接管授权内核（2026-11-01 主人硬规矩 |
| **安全（测绘/扫描/防御）** | 30 | `dual_gate`, `sec_surface`, `sec_scan`, `sec_chain` | 双脑确认 |
| **心智（记忆/人格/情绪）** | 21 | `experience_forge`, `brain_vault`, `self_intake`, `mind` | 成长闭环（2026-11-01 主人判据 |
| **情报（OSINT/研究/学习）** | 18 | `osint_scan`, `research_intel`, `tentacle_learn`, `spider_ops` | OSINT 扫描（DNS/WHOIS/子域名/端口/指纹/邮箱/IP归属/社交 |
| **管线（镜像/部署/回滚）** | 18 | `one_key_deploy`, `deploy_queue`, `mirror_shape`, `mirror_scan` | 一指定江山乾坤换位 |
| **视频（生成/剪辑/混音）** | 16 | `hunyuan_video`, `media_pipeline`, `edit_pipeline`, `audio_extract` | 混元视频 HunyuanVideo 1.5（8.3B）**只读骨架** |
| **身体（看/说/按/敲）** | 12 | `body_map`, `body_see`, `body_say`, `body_type` | 身体·清单 |
| **数据（审计/图表/检索）** | 12 | `echo`, `count_words`, `audit_query`, `record_grid` | 联调回显位 |
| **引擎（DAG/能源/缓存）** | 11 | `wf_define`, `wf_run`, `wf_status`, `wf_resume` | 工作流引擎 |
| **集成（飞书/TG/WA/Notion）** | 11 | `mcp_register`, `mcp_servers`, `mcp_unregister`, `mcp_health` | MCP 注册 |
| **工具（投影卡/仓库/补丁）** | 9 | `projection_card`, `capability_net`, `freebuff_term`, `repo_publish` | 空间投射只读卡片 |
| **吞噬（GitHub→知识→进化）** | 6 | `devour_auto`, `devour_scan`, `devour_github`, `devour_reflect` | 自主吞食 |
| **视觉（流/差异/打印）** | 5 | `vision_loop`, `vision`, `vlx_flow`, `vision_grounding` | **原生四觉闭环**（主人令 2026-10-09 |
| **金融（量化策略/回测）** | 4 | `quant_strategy`, `quant_backtest`, `quant_params`, `quant` | 【量化·策略信号】读取真实量化引擎 |
| **长跑（长任务/战术建议）** | 4 | `lr_submit`, `lr_tick`, `lr_status`, `tactics_advise` | 长程任务层 |
| **语音（TTS/合唱/工作室）** | 4 | `voice`, `voice_orchestra`, `hf_voice`, `voice_studio` | 本机语音入口（良性子集） |
| **项目（同步/平台画像）** | 3 | `sync_guard`, `platform_profile`, `project_context` | 双仓同步巡检（2026-11-01） |
| **自动化（浏览器/n8n）** | 2 | `browser`, `n8n_wf` | 浏览器自动化入口（良性子集） |
| **脑（梦回放/吸收）** | 2 | `dream_replay`, `absorb_loop` | 做梦技能只读重演 |
| **协作（网关/痕迹）** | 2 | `collab_gateway`, `stigmergy` | 协作网关（多智能体会话/信箱/同伴注册） |
| **桌面（控制环/远控）** | 2 | `control_loop`, `ul_tars_desktop` | 快慢双脑控制回路 |
| **基础设施（云插件/云机）** | 2 | `cloud_plugin`, `cloud_pc` | 云插件（只读骨架） |
| **社交（发布/流量）** | 2 | `eigenflux`, `auto_publish` | AI 朋友圈 |
| **通信（邮件）** | 1 | `coze_mail` | 通信域 |
| **生活** | 1 | `life` | 生命档案 |
| **图生视频** | 1 | `a1art_skill` | a1.art API 技能（只读骨架·门） |
| **框架（门可见性）** | 1 | `gate_visibility` | 门可见性审计（只读骨架·门） |

## 三、十个真实用法（可直接抄）

### 看她的能力面

```python
import gbt_allinone as gbt
r = gbt.run_task('cap_self', {'op': 'brief'})
print(r.get('gbt_result', {}).get('result'))
```

### 自检（五维）

```python
import gbt_allinone as gbt
r = gbt.run_task('selfscan', {})
print(r.get('gbt_result', {}).get('result'))
```

### 代码覆盖率（每一处归到触手）

```python
import gbt_allinone as gbt
r = gbt.run_task('trunk_cover', {'op': 'status'})
print(r.get('gbt_result', {}).get('result'))
```

### 旧物/重复六类扫描

```python
import gbt_allinone as gbt
r = gbt.run_task('legacy_guard', {'op': 'status'})
print(r.get('gbt_result', {}).get('result'))
```

### 脉冲直达（0 token 命中）

```python
import gbt_allinone as gbt
r = gbt.run_task('pulse_core', {'op': 'direct', 'intent': '审计'})
print(r.get('gbt_result', {}).get('result'))
```

### 编排面板（上一轮动了什么）

```python
import gbt_allinone as gbt
r = gbt.run_task('orchestration', {'op': 'panel', 'limit': 5})
print(r.get('gbt_result', {}).get('result'))
```

### 图像引擎（纯 CPU 算子）

```python
import gbt_allinone as gbt
r = gbt.run_task('comfy_native', {'op': 'status'})
print(r.get('gbt_result', {}).get('result'))
```

### 架构→蓝图

```python
import gbt_allinone as gbt
r = gbt.run_task('blueprint', {'op': 'make', 'arch': '触手主干 + 全自主到落地'})
print(r.get('gbt_result', {}).get('result'))
```

### 视频生成（需云端 key，缺钥如实报）

```python
import gbt_allinone as gbt
r = gbt.run_task('hunyuan_video', {'op': 'status'})
print(r.get('gbt_result', {}).get('result'))
```

### 量化回测

```python
import gbt_allinone as gbt
r = gbt.run_task('quant_backtest', {'op': 'status'})
print(r.get('gbt_result', {}).get('result'))
```

## 四、边界（如实说）

- **危险动作要票**：转账/付款、隐私读取、生产写入、远控、外发内容 —— 走 `security/policy.py` 的 15 个作用域，
  授权只能主人终端发放（`python -m gbt_allinone auth grant --scope <域> --ttl <秒>`），AI 无权自批。
- **云端能力缺钥就报缺钥**，不假装成功；本机没 CUDA 就不下权重。
- **做不到的会明说**：`needs_dependency` / `needs_key` / `unimplemented`，都有明确字段。

## 五、怎么自己核

```bash
python -c "import sys;sys.path.insert(0,'.');import gbt_allinone as g;print(len(g.list_capabilities()))"   # 410
python -m gbt_allinone list                                                                          # 逐位列出
```

---

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
