<p align="center">
  <a href="https://github.com/gbtweilai-star/GBTxiaotudouV8-Commander">
    <img src="assets/social-preview.png" alt="GBT小土豆V8 · 独立数字人框架" width="100%">
  </a>
</p>

<h1 align="center">GBT小土豆V8 · 独立数字人框架</h1>

<p align="center">
  <b>统一入口 <code>run_task</code> · 全行为落审计 · 能力位现读可核 · 触手层可插拔</b>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-%E2%89%A5_3.10-3776AB?logo=python&logoColor=white">
  <img alt="Core" src="https://img.shields.io/badge/Core-stdlib_only-22C55E">
  <img alt="Caps" src="https://img.shields.io/badge/Capabilities-427-F5B041">
  <a href="https://github.com/gbtweilai-star/GBTxiaotudouV8-Commander/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/gbtweilai-star/GBTxiaotudouV8-Commander/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Docs" src="https://img.shields.io/badge/Docs-364_pages-00E5FF">
  <img alt="License" src="https://img.shields.io/badge/License-Apache--2.0-blue">
  <img alt="Status" src="https://img.shields.io/badge/Status-active-7C4DFF">
</p>

<p align="center">
  <a href="#-快速开始">快速开始</a> ·
  <a href="#-它是什么">它是什么</a> ·
  <a href="#-架构">架构</a> ·
  <a href="#-能力面">能力面</a> ·
  <a href="#-实测读数">实测读数</a> ·
  <a href="#-文档">文档</a> ·
  <a href="#-参与">参与</a>
</p>

<p align="center">
  <sub><b>开发者：自由的风</b> · 本署名不可删除、不可篡改归属</sub>
</p>

---

## 🥔 它是什么

一个**本地优先的独立数字人框架**：大脑（大模型）+ 触手（操作系统能力）+ 审计账（每次调用可追），
所有能力通过**唯一入口** `run_task(kind, payload)` 调度，写盘 / 花钱 / 出网一律过授权门。

- **不是聊天壳**：427 个能力位落在 32 个域，本机真跑、真留痕。其中 **389 位零作用域可直接调**、**38 位挂了票要先授权**；按 `safe` 字段另算则是 **339 位不改状态 / 88 位会写盘或出网**——两套口径都写在 `docs/03-capabilities.md`，不混着说。
- **不是玩具**：每次调用落 `audit.jsonl`（call / ok / error / denied），可查、可计数。
- **不依赖云**：核心只用标准库；大模型可换本机 GGUF，也可以接任意 OpenAI 兼容端点。
- **可自检**：`selfscan` 五维扫描、`trunk_cover` 代码全覆盖、`legacy_guard` 旧物六类扫描。

<p align="center">
  <img src="assets/demo.gif" alt="30 秒 demo（真跑回放）" width="720">
  <br>
  <sub>30 秒 demo：真跑回放，不是录屏剪的（2026-11-01 录制，位数为当时读数）</sub>
</p>

## 🚀 快速开始

```bash
git clone https://github.com/gbtweilai-star/GBTxiaotudouV8-Commander.git
cd GBTxiaotudouV8-Commander
```

```python
import sys; sys.path.insert(0, ".")
import gbt_allinone as gbt

print(len(gbt.list_capabilities()))                 # 427
print(gbt.run_task("health"))                       # 环境自检
print(gbt.run_task("cap_self", {"op": "brief"}))    # 她自己的自述（现读）
print(gbt.run_task("selfscan"))                     # 五维自检
```

Windows 一键启动：双击 `启动-GBT.cmd`；桌面壳（现役）：`cd holo_pet_w3 && npx --no-install electron shell/main.cjs`。

### 30 秒看到什么

不给 `--endpoint` 时它**完全不调模型**，纯关键字兜底——下面这段是真跑输出，不是示意：

```text
$ python demo.py "把这次发布推到生产"

① 这台机器的能力目录（机器可读，不是截图）
   427 位能力 · 32 个域 · 只读 339 · 会改状态 88 · 挂作用域 38

② 按你的那句话，落点候选（关键字打分，不是模型决策）：
   [1000.0] one_key_deploy   pipeline  会改状态  要票：deploy_publish,process_execute,filesystem_write
            一指定江山乾坤换位：抓取→镜像→验证→晋升，一条命令

③ 在这台机器上，它就是这么被调用的（唯一门，绕过它没有留痕）：
   py -3.14 tools/codex-scripts/five-dim.py cap one_key_deploy '{}'
   ⚠️ 这一位挂了作用域 ⇒ 门会先拒，等主人发票（AI 不能给自己发）
```

一句话看清三件事：**有多少能力位、这句话落到哪一位、这一位要不要票。**

## 🏛 架构

<p align="center">
  <img src="assets/architecture.svg" alt="架构：大脑 → 唯一门 → 能力位 → 触手 → 审计" width="820">
</p>

```
run_task(kind, payload)
   │
   ├─ 授权门 security/policy.py（15 个作用域：付款/隐私/生产写入/远控/发声/出网…）
   ├─ 能力位 caps_registry.py（427 个，32 域）
   ├─ 触手层 tentacle/（识别 / 执行 / 自检 / 编排 / 蓝图 / 脉冲直达）
   └─ 审计 store/audit.jsonl（call / ok / error / denied 全程落盘）
```

## 🧠 她能干嘛（32 域 · 427 位）

**给她一句话，她自己选能力位、过授权门、真跑、留审计、出结果。**

| 域 | 数量 | 代表能力 |
|---|---:|---|
| 创作（视频/图像/音乐/剧本） | 58 | viral_forge drama_forge shot_director |
| 系统（自检/编排/修复） | 60 | selfscan orchestration root_fix |
| 大模型（本机/云端/上下文） | 43 | codex_* context_guard energy_core |
| 安全（测绘/扫描/防御） | 34 | sec_surface sec_scan sec_defenses |
| 触手（总指挥/脉冲/覆盖） | 30 | tentacle pulse_core trunk_cover |
| 心智（记忆/人格/情绪） | 27 | experience_forge brain_vault persona_kernel |
| 情报（OSINT/研究/学习） | 18 | osint_scan research_intel topic_web |
| 管线（镜像/部署/回滚） | 18 | one_key_deploy mirror_* deploy_queue |
| 视频（生成/剪辑/混音） | 18 | hunyuan_video media_pipeline audio_mix |
| 身体（看/说/按/敲） | 19 | body_see body_click body_type |

完整 32 域 + 10 个可抄用法 + 边界说明：[**docs/90-what-she-can-do.md**](docs/90-what-she-can-do.md)

> 边界：危险动作（转账/隐私/生产写入/远控/外发）一律要主人发授权；缺钥/缺依赖**如实报**，不装成功。

## 🖥 认知界面（一个控制台，三栏骨架）

旧 28 个面板已全部拆除（归档在 `.archive/panels-20261101/`，71.9MB 可恢复），
换成一个三栏「认知界面」：左=品牌/守卫/事件流，中=对话（本机指挥官），右=心跳/行动日志/守卫与能力，
背景是能力域图谱。
内容全部换成我们自己的原生能力读数。

<p align="center">
  <img src="assets/panels/console.webp" width="96%" alt="GBT小土豆V8 认知界面">
</p>

打开：`python tools/console-server.py` → <http://127.0.0.1:8766/>（实时数据 + 真对话）；
或双击 `holo_pet_w3/console/index.html`（离线快照）。
细节：[**docs/legacy/102-cognitive-console.md**](docs/legacy/102-cognitive-console.md)

## 🧩 能力面

| 域 | 代表能力 | 一句话 |
|---|---|---|
| 大脑 | `commander` · `energy_core` · `trunk_reason` | 本机 GGUF 总指挥 + 能源核心（取电口池）+ 触手推理环 |
| 执行 | `tentacle` · `omni_*` · `body_*` | 看屏 / 点按 / 键入 / 窗口 / 进程 / 剪贴板（万能插即插即用） |
| 自检 | `selfscan` · `trunk_cover` · `legacy_guard` | 路由对账 / 代码全覆盖 / 旧物六类 |
| 编排 | `orchestration` · `blueprint` · `wf_*` | 编排账本 / 架构→蓝图→派遣→落地 / DAG 工作流 |
| 图像 | `comfy_native` | 118 个纯 CPU 算子（音频/图像/文本），契约面覆盖 10.1% |
| 安全 | `signature_guard` · `sec_*` | 署名守卫 / 攻击面测绘 / 漏洞扫描 / 防御验证 |

完整清单：`gbt.run_task("caps_list")`，或看 [docs/capabilities](docs/capabilities/)。

## 📊 实测读数

> 只写跑出来的数字，改一次代码重新读一次。

| 指标 | 读数 | 复核命令 |
|---|---|---|
| 能力位 | **427** | `cap_self verify` |
| 逐位真调 | **301 / 427 通过**（88 位需授权、30 位需参数、5 位缺前置计划、1 位缺 cv2；**0 位无法归因、0 超时**） | `python tools/codex-scripts/probe-caps-live.py --timeout 120` |
| 审计条数 | 现读 | `gbt.log_count()` |
| 自检 | clean | `selfscan` |
| 代码覆盖 | orphan = 0 | `trunk_cover status` |
| 脉冲直达 | ≈90% 请求 0 token 命中（≈4ms） | `pulse_core verify` |
| 图像算子 | 118 个（纯 CPU） | `comfy_native status` |

<table>
<tr>
  <td><img src="assets/fig-caps.png" alt="能力面 · 341 位时期实测快照"></td>
  <td><img src="assets/fig-concurrency.png" alt="并发实测"></td>
</tr>
<tr>
  <td><img src="assets/fig-eval.png" alt="评测"></td>
  <td><img src="assets/fig-dispatch-ok.png" alt="真跑回执"></td>
</tr>
</table>

> **插图时点**：上述插图为 **341 位时期（2026-10-21）** 的历史回执快照，图中位数为当时读数 —— **不是当前状态**。427 位的逐位真调已于 **2026-11-04** 全量重跑完毕，读数见上表「逐位真调」行与 `data/capability-live-test.json`；插画待下次重绘替换。

## 📚 文档

索引：[docs/legacy/README.md](docs/legacy/README.md)（364 页，含 docs/legacy 归档 67 页，按编号）

- [模型卡](docs/01-model-card.md) · [架构](docs/02-architecture.md) · [能力面](docs/03-capabilities.md)
- [部署](docs/05-deployment.md) · [并发实测](docs/08-concurrency.md) · [安全与控制](docs/14-security-and-control.md)
- [蓝图主链](docs/68-blueprint-chain.md) · [跑到落地](docs/69-run-to-landing.md) · [旧物守卫](docs/79-legacy-guard.md) · [仓库整理](docs/legacy/87-repo-cleanup-done.md)

## 🤝 参与

- 提 Bug / 需求：[Issues](https://github.com/gbtweilai-star/GBTxiaotudouV8-Commander/issues)
- 贡献流程：[CONTRIBUTING.md](CONTRIBUTING.md) · PR 模板见 [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md)
- 安全披露：[SECURITY.md](SECURITY.md)
- 行为准则：[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- 引用：[CITATION.cff](CITATION.cff)

## 🪪 许可与署名

Apache-2.0（见 [LICENSE](LICENSE) 与 [NOTICE](NOTICE)）。
**开发者：自由的风** —— 框架每一页（文档 / 网页 / 产物）自动携带署名，禁止删除、禁止篡改归属。

<p align="center"><sub>GBT小土豆V8 · 独立私人框架 · 与任何企业公司无关</sub></p>
