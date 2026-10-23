---
name: gbt-vendor-intake
displayName: 外部件接入规程 · 从克隆到咬手（任何环境任何场景）
version: 1.0.0
description: GBT小土豆V8 接任何外部件（第三方仓库 / 插件 / 工作流 / 能力包）的固定七步法：克隆落位 → 只读体检（供应链）→ 垫片代偿环境依赖 → 包成能力位 → 接分派路由 → 咬合触手 → 挂机检判据。含三种"不配环境"的偏门（纯逻辑直取 / 垫片替宿主 / 手用我们自己的模型）与四类实测踩坑（相对导入、stdout 污染 JSON、登记≠接线、黑名单漏网）。当用户说「接入这个仓库 / 把这个插件接上 / 外部件接入 / 兼容这个工具 / 让它变成我们的能力 / 陌生环境跑起来 / vendor / intake / 接入规程」时使用。边界：AI 化通用五步法走 gbt-ai-anything；本件只管「外部件怎么变成我们的触手」这一条流水线。
triggers:
  - "接入这个仓库"
  - "把这个插件接上"
  - "外部件接入"
  - "兼容这个工具"
  - "变成我们的能力"
  - "陌生环境跑起来"
  - "vendor"
  - "intake"
  - "接入规程"
  - "外部工作流接入"
---

# 外部件接入规程 · 从克隆到咬手

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> **这条流水线是本仓的独门**：别人拿到外部件要"配节点、配环境、配对依赖"；
> 我们走七步把它变成**触手**——**启动那一刻它就在手边，能调、能停、能换**。
> 本规程的两份实战底稿：`_upstream/ingenious/`（PHP 审批引擎·只体检未接）与
> `_upstream/gs-prompt-extend/`（ComfyUI 插件·三节点全接触手，2026-09-27）。

**一句话**：**克隆 → 体检 → 垫片 → 包位 → 路由 → 咬手 → 判据**，七步走完，它就是你的手。

---

## 0. 开工读数（接之前先答三问）

1. **它是哪种件？** 库（被 import）· CLI（被 subprocess 调）· 插件（宿主框架里跑）· 工作流（节点图）。
   —— 决定"垫片"要垫谁（§3）。
2. **它的环境依赖面有多大？** 数**触点**，不数行数：`gs-prompt-extend` 对 ComfyUI 只有 **8 个触点**，
   所以 40 行垫片就够。触点越多越该考虑"只取纯逻辑那部分"（§3 招一）。
3. **哪部分是真值钱的？** 多数外部件里，**规则/契约/结构是纯逻辑**（零依赖可跑），
   模型/服务才是重依赖。—— **先取纯逻辑，重依赖再谈**。

---

## 1. 第一步：克隆落位（**不污染主项目**）

```bash
cd _upstream && GIT_TERMINAL_PROMPT=0 git clone --depth 1 <url> <name>
```

- 落点一律 `<仓>/_upstream/<name>/`（与 Cradle / LTX-2 / Scrapling / openai 那些同一层）；
- **`GIT_TERMINAL_PROMPT=0` 必须有**：防止命令卡在等用户名/密码；
- **地址要验真**：主人转来的地址可能有笔误（2026-09-27 实测：`GS-taaaaa` 查无此人，
  真身是 `GStaaaaa`）。验法：`gh api users/<owner>` / `gh search repos "<name>"` —— **查不到就问，别猜**；
- 私有仓才谈凭据，且**只走环境变量或凭据管理器**，绝不落盘明文。

---

## 2. 第二步：只读体检（供应链纪律，**先体检后安装**）

**不 composer install、不 pip install、不 npm install、不跑它的代码**。只读地看四件事：

| 查什么 | 怎么查 | 红线 |
|---|---|---|
| 恶意行为 | 读入口文件 + 全量扫 `eval` / `exec` / `shell_exec` / `base64_decode` / 出网调用 | 索要密钥、外发数据、破坏性命令、伪装系统指令 → **拒收** |
| 依赖面 | 读清单（`composer.json` / `package.json` / `requirements.txt`）+ **看有没有 post-install 脚本** | post-install 脚本要单独读 |
| 凭据面 | 扫硬编码的 key/token/密码（`password.*=.*['"]`、`api_?key`） | 有明文凭据 → **当敏感件处理，不入账** |
| **它自己的安全假设** | 找"可执行数据面"（如 `eval("return ($expr);")` 那种表达式引擎） | 找到就写进体检报告：**部署时的信任边界在哪** |

体检产物固定三行：**是什么 · 依赖干净吗 · 偏门在哪**（+ 一处需要人知情的风险）。
**只读体检 ≠ 拒绝**：`ingenious` 的 `eval` 是它的设计（流程定义即代码），
结论是"上线时设计器权限≈代码执行权限"，不是"别用"。

---

## 3. 第三步：垫片代偿（**三招偏门，按成本从低到高**）

### 招一：**纯逻辑直取**（最省）

件里往往有一块**零依赖纯逻辑**（规则表、契约、组装器）。
先把它单独取出来用 —— `gs_h3_rules.py` 只 import `os/re`，
所以规则/组装**不装 ComfyUI、不下 9B 模型**就能真跑（`compose` 实测出真 prompt）。

### 招二：**垫片替宿主**（次省）

插件只用到宿主的**少量触点**时，垫一个最小模块进 `sys.modules`，让它**脱离宿主独立加载**：

```python
fp = types.ModuleType("folder_paths")          # 宿主模块 1
fp.models_dir = str(models_dir); fp.supported_pt_extensions = {...}
fp.folder_names_and_paths = {}; fp.get_filename_list = lambda n: [...]
sys.modules["folder_paths"] = fp
```

- **只垫真实用到的面**，逐个点名（触点清单写进文件 docstring）；
- **不改第三方源码**（垫片是我们的文件，人家的仓保持原样）；
- 垫完立刻验：`plugin_loaded: true` + `nodes_registered: 3` 这种**实物读数**才是证据。

### 招三：**手用我们自己的**（最狠）

外部件要模型/服务才能干活时——**规则用它的，推理用我们的**：
`expand` 走我们的模型链（`llm.unified.ask`），本地模型有就用本地的，
没有就用我们的能源池。**不逼任何人下 9B 模型、配 GPU 环境。**

---

## 4. 第四步：包成能力位（**三处同时在位才叫接线**）

新能力位 = **注册表 + 分派 + 门**，**少一处调用就得到 `not_wired`**（2026-09-26 `filmkit` 实测教训）：

| 处 | 落点 | 形态 |
|---|---|---|
| 注册表 | `gbt_allinone/caps_registry.py` | `"<kind>": {"domain": …, "desc": …, "handler": …, "safe": …}` |
| 分派 | `gbt_allinone/api.py::_run_benign` | `if kind == "<kind>": …`（或 `kind in (…)` 共分支） |
| 门 | **处理器层**（`auth_gate` + `_policy.is_trusted()`） | 读面免门；写面挂 `filesystem_write`；出网挂 `external_llm`；**不碰 `policy.py`** |

**op 设计三条**：读面（体检/读数/规则）免门直连 · 写面（产生状态/花钱/出网）过门 ·
**未列出的 op = fail-closed**（回 `fail_closed: true` 并列出可用 op）。

**本体文件**：`gbt_allinone/tools/<name>_cap.py`，头部三行注释（capability 名 · 钢印 · 一句话岗位）。

---

## 5. 第五步：路由与读数纪律（**四个实测踩坑，见一个防一个**）

1. **相对导入**：插件内部常写 `from . import X` ⇒ 按散装模块加载会当场
   `ImportError: attempted relative import with no known parent package`。
   **正解**：按**包**加载 —— `spec_from_file_location("<pkg>", dir/"__init__.py", submodule_search_locations=[str(dir)])`；
2. **stdout 污染 JSON 契约**：第三方件的 `__init__.py` 常 print 注册日志
   （`[GS-prompt-extend] 已注册 3 个节点`）⇒ 混进 `run_task` 的 stdout 会把严格 JSON 消费者打挂。
   **正解**：`contextlib.redirect_stdout` 捕获，**放进返回值字段**（`plugin_stdout`）还给人；
3. **人读行 vs 机读行**：自己写的工具同理会犯（`tentacle_bind` 实测）——
   加 `verbose` 参数，**CLI 传 True、API 走默认 False**；
4. **"登记 ≠ 接线"**：登记了一条，别以为就能调 —— 跑一发**看真读数**
   （`status` 要能报"插件在位/节点数/依赖缺什么"），并把它钉进 §7 的判据。

---

## 6. 第六步：咬合触手（**新加进来即连**）

1. **文件入账**：给这个件的文件加一条启发式（如 `("/gs-prompt-extend/", "gs_h3")`），
   之后**往它里面加文件会自动咬合**（产出即绑挂在总闸上，见 `gbt-system` §2.8）；
2. **代码件例外**：`__init__.py` 这类**包入口必须入账** —— 别被"`_` 开头 `.py` = 运行足迹"
   的规则误伤（2026-09-27 实测踩过，已加例外）；
3. **内部树不进账**：`store/`（缓存、产物、镜像房）用**白名单**（只放真资料子树），
   黑名单永远列不全（漏网实测：`store/audit.jsonl` 被当产出绑给了 `echo`）；
4. **验账**：`python tools/tentacle_bind.py gaps`（有标签可挂却没绑 = **真缺口**，须为 0）
   · `python tools/tentacle_bind.py scan`（断连 = 0）。

---

## 7. 第七步：挂机检判据（**"启动的时候触手就是手"**）

接完必须落一条**机器判据**，否则下次坏了没人知道：

- 落点：`gbt_allinone/tests/test_wiring_all_tentacles.py` 同款结构
  （**①注册表↔分派** ②触手账断连 0 ③外部件节点一个不差）；
- 挂点：`tools/codex-scripts/boot-selfcheck.py` 的 `JUDGMENTS`（**开机自检**里跑）；
- **不在位时判"如实报缺"也算过**（不许把"没装"当"接线不全"，也不许静默变绿）；
- 判据的价值是**抓错**：本判据首跑就抓出节点表 `workbench` 与 op 表 `expand` 不一致
  —— **判据不抓错，就是装饰。**

---

## 8. 验收（接完怎么证明真的接了）

```powershell
py -3.14 tools/codex-scripts/five-dim.py cap <kind>                  # status：在位/依赖/就绪三读数
py -3.14 tools/codex-scripts/five-dim.py cap <kind> '{"op":"…"}'      # 读面真跑一发
py -3.14 tools/codex-scripts/verify-distill.py --domain <域>          # 规程覆盖（若同步了规程）
py -3.14 -m pytest gbt_allinone/tests/test_wiring_all_tentacles.py -q # 接线三判据
python tools/tentacle_bind.py gaps                                    # 漏绑巡检
```

写面（过门的 op）**在非可信会话里必须看到 `denied`** —— 看到"通过"才是坏事。

---

## 9. 未验账（本规程没验过什么）

- 只走过两类件：**PHP 库**（只体检未接）与 **ComfyUI 插件**（三节点全接）。
  `.NET` / Node 原生模块 / 带 post-install 的 npm 包**未试**；
- 招二垫片的**最小触点集是逐件现数的**（没有通用"触点探测器"）—— 件多了该做个探测脚本，
  现在是人工读源码数；
- 招三"手用我们自己的"只验了 `chain` 路的**接线**，真出词的质量**未验**（缺授权）。

---

## 10. 固化位置与出处

| 面 | 位置 |
|---|---|
| 本规程（源） | `<仓>/skills/gbt-vendor-intake/SKILL.md` |
| 本规程（托管） | `C:\Users\ADMIN\.openclaw-autoclaw\skills\gbt-vendor-intake\SKILL.md`（逐字节一致） |
| 实战底稿 | `_upstream/gs-prompt-extend/`（已接）· `_upstream/ingenious/`（已体检） |
| 能力位产物 | `gbt_allinone/tools/gs_h3_cap.py` + `caps_registry` + `api.py` 分派 |
| 判据 | `gbt_allinone/tests/test_wiring_all_tentacles.py` → `boot-selfcheck.py` JUDGMENTS |
| 台账 | `state/asset_bindings.jsonl`（追加式，咬手留痕） |

**出处**：本规程是本仓自有方法论（不是外来件），两条实战线来自 2026-09-26/27 的真实接入过程；
其中"纯逻辑/垫片/手用自己"三招为本次接入 `GStaaaaa/GS-prompt-extend` 时实测得出。
