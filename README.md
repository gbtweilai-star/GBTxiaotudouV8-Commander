<p align="center">
  <a href="https://github.com/gbtweilai-star/GBTxiaotudouV8-Commander">
    <img src="assets/brand/repo-banner.png" alt="GBT小土豆V8 · 独立数字人框架" width="100%">
  </a>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-%E2%89%A5_3.10-7C4DFF">
  <img alt="核心依赖" src="https://img.shields.io/badge/Core-stdlib_only-22C55E">
  <img alt="能力位" src="https://img.shields.io/badge/Caps-375-F5B041">
  <img alt="测试" src="https://img.shields.io/badge/Tests-27_suites-3F4759">
  <img alt="语言" src="https://img.shields.io/badge/Lang-%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-9AA4C4">
</p>

<p align="center">
  <b>独立数字人框架</b>：统一入口 <code>run_task</code> · 全行为落审计账 · 能力位现读可核<br>
  <sub>开发者：自由的风 · 本署名不可删除、不可篡改归属</sub>
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> ·
  <a href="#现读数字">现读数字</a> ·
  <a href="#结构">结构</a> ·
  <a href="#审计与授权">审计与授权</a> ·
  <a href="#测试">测试</a> ·
  <a href="docs/">文档</a> ·
  <a href="#署名">署名</a>
</p>

---

V8.0.0 · 独立私人框架，与任何企业公司无关。Python ≥ 3.10 · 核心仅标准库。

## 现读数字（以本仓代码为准，不写死宣传语）

| 项 | 现读 | 怎么自己核 |
|---|---|---|
| 能力位 | **375** | `gbt.run_task('cap_self', {'op':'verify'})` |
| 测试 | **27 套** | `tests/test_*.py` |
| 工具脚本 | **948** 个 `.py` | `tools/**/*.py` |
| 文档 | **93 页** | `docs/*.md`（索引 `docs/README.md`） |
| 代码覆盖 | 每一处都归到某根触手 | `gbt.run_task('trunk_cover', {'op':'status'})` |
| 旧物/重复 | 六类扫描 | `gbt.run_task('legacy_guard', {'op':'status'})` |

> 数字只认跑出来的读数：改一次代码就重新读一次，不写"大概/约"。

## 为人处世三律

1. **听从指令** — 用户指令第一，不揣测、不代答、不擅自扩大或缩小任务范围。
2. **给意见** — 完成后主动给出专业判断：风险在哪、更好的做法是什么、下一步建议什么。
3. **一起想办法** — 遇到阻塞不甩锅、不空手而归，带着方案回来让用户挑。

拒绝的永远只是**具体行为的风险**，不是这个人：说清楚为什么不行，再给出怎样才行。

## 自主铁律（2026-11-01 主人令）

- **架构给完之后**：除 `danger`（终端危险能力）与 `transfer`（转账）外，**禁止打扰主人、禁止要求主人帮助**；不确定就自主决策并如实标注。
- **唯一真相**：只看 live 仓**当前文件**与编排账本；**旧备份 / 归档 / 旧工作树一律不读**（去旧目录找答案 = 绕弯根源）。
- **不留旧物**：旧代码、旧面板、重复物一律清掉（`legacy_guard` 查六类：旧代码快照 / 过期工作树 / 旧面板归档 / `*.bak` / 重复文档编号 / 临时件）。

## GBT 钢印

框架产出的结果默认携带 `gbt_stamp`（框架名 / 版本 / GBT 标记 / 独立归属声明）。
钢印不可伪造归属、不可移除出处；`run_task(kind, payload, stamp=False)` 可显式关闭。
所有钢印产物与任何企业公司无关。

## 结构（真实存在，现读）

```
GBTxiaotudouV8-Commander/
├── gbt_allinone/        # 框架核心
│   ├── api.py           # 统一入口 run_task（全行为落审计 + 默认钢印）
│   ├── caps_registry.py # 能力位注册表（375）
│   ├── soul.py          # 理念 + 钢印
│   ├── store.py         # JSONL 审计后台
│   ├── tentacle/        # 触手层（识别 / 执行 / 自检 / 编排 / 蓝图）
│   └── security/        # 授权门（policy.py 作用域）
├── tools/               # 948 个工具（含 model-bridge / codex-scripts）
├── tests/               # 27 套判据
├── docs/                # 93 页文档（docs/README.md 是索引）
├── data/                # 能力表 / 意图词表等只读数据
├── holo_pet_w3/         # 桌面壳（现役：Electron + 127.0.0.1:8765 面板）
├── holo_pet/            # 桌面壳资源（旧版）
├── arms/  skills/  examples/  icons/  ios/  mobile/  gbt_commander/
├── demo.py              # 30 秒 demo
├── install.ps1          # 安装
└── 启动-GBT.cmd         # Windows 启动器
```

## 快速开始

```bash
# 列出能力位 + 审计条数
python -c "import sys;sys.path.insert(0,'.');from gbt_allinone.cli import main;main(['list'])"

# 调一个只读能力位（全程落审计，结果带钢印）
python -c "import sys;sys.path.insert(0,'.');import gbt_allinone as gbt, json;print(json.dumps(gbt.run_task('cap_self',{'op':'brief'}),ensure_ascii=False)[:400])"

# 桌面壳（现役）
cd holo_pet_w3 && npx --no-install electron shell/main.cjs
```

依赖：`pip install -r requirements.txt`（桌面壳需 customtkinter / tkinter）。

## 审计与授权

- `gbt_allinone/store/audit.jsonl`：call / ok / error / denied 全程落盘；`gbt.query_log()`、`gbt.log_count()` 查询。
- 授权只能主人在终端发放：`python -m gbt_allinone auth grant --scope <作用域> --ttl <秒>`；
  **AI 永远无权给自己发授权**，缺哪个就如实报哪个。
- 只读类不需要授权；没有"按名禁用"的能力（`DISABLED_CAPS = 0`）。
- 门是主人的开关，不是技术限制：门开着，技术全在。

## 触手与万能插（现读）

- `tentacle`：统一调用触手能力（`see` / `read_text` / `click` / `type` / `list_windows` / `process_list` / `clipboard` / `chain` / `monitor` …）+ 六铁律（先看再动 / 动后等稳定 / 找不到就滚 / 遇弹窗必关 / 每步亲眼验证 / 不确定就对比前后截图）。
- `omni_*`（万能插）：插座动态发现、能力位即插即用；`omni_open` 自动识别插口，不写死。
- 速度：脉冲·直达——常见意图 0 token 直接命中（实测十次请求约九次直达，≈4ms）。

## 测试

```bash
python tests/test_autonomy.py          # 自主契约（不打扰主人）
python tests/test_blueprint.py         # 架构→蓝图→过目→思维导图→派遣→落地
python tests/test_comfy_engine.py      # 天真图像引擎判据
python tests/test_legacy_guard.py      # 旧物六类扫描
```

## 文档

索引：`docs/README.md`（按编号排列）。近期关键：
- `docs/87-repo-cleanup-done.md` — 本仓 GitHub 整理记录（5108 → 2708 文件）
- `docs/81-single-source-of-truth.md` — 唯一真相与旧物禁令
- `docs/69-run-to-landing.md` · `docs/70-research-on-blocker.md` · `docs/71-stuck-task-protection.md` · `docs/72-blueprint-templates.md`

## 署名

**开发者：自由的风** —— 框架每一页（文档 / 网页 / 产物）自动携带署名，禁止删除、禁止篡改归属。
`signature_guard` 能力：扫描页面署名完整性，缺失即报，`restore=true` 自动补回。
