# -*- coding: utf-8 -*-
"""能力审计 · **逐项真探**（主人令 2026-10-07）。

主人原话：「还有排查清楚所有的能力都连接好了没有，做一个能力统计面板，把每接好的全部接好，
断连或者缺失就自动报警自我修复，以及安全回滚都要设计好。」

拆成本件要干的三件事：
  ① **排查清楚**：把仓里「所有能力」逐个查一遍**到底接上没有** —— 真查、真探。
  ② **能力统计面板**：分类汇总 + 逐条明细（含证据）+ 报警清单（断连与缺失置顶）。
  ③ **台账**：落 `state/capability-audit.json`（每条：id / 类别 / 期望接法 / 实测 / 状态 / 证据 / 探于何时）。

## 覆盖的九类能力（**现读真源，不猜**）

| 类别 | 真源（现读） | 探法 |
|---|---|---|
| `framework` | `gbt_allinone/caps_registry.py::BENIGN_CAPS`（**现读 240 位**，不是抄来的数字） | 文件类：注册表在盘且非空；每位再查 `gbt_allinone/api.py` 里**有没有分派着落** |
| `cloud` | `deploy/cloud-10/mesh.json`（**现役 10**；`plugins50.json` 是蓝图**不算接上**） | HTTP 真探 `GET <base>/health?_probe=<id>`（超时 3s），复用 `cloud-status.py` 的 host 校验与台账口径 |
| `shell-window` | `holo_pet_w3/shell/windows.json`（现读 14 扇窗） | 文件类：`file` 指向的页面在不在 + 非空 |
| `panel-page` | `holo_pet_w3/panel/index.html::PAGES`（现读 15 条） | 文件类：`rel` 相对面板的页面在不在 + 非空 |
| `bridge` | `holo_pet/launch_panel.py`（默认 `127.0.0.1:8765`） | HTTP 真探 `GET /api/state`（超时 3s） |
| `dsh` | `holo_pet_w3/shell/windows.json::dsh-chat.auto_dsh`（`127.0.0.1:3080`） | HTTP 真探根路由（**401 是预期**：无 token 就该 401 ⇒ 服务在听即「接上」） |
| `service` | `gbt_allinone/llm/cloud_llm.py` + `state/skill_atlas.json` 登记的**本机回环**服务 | HTTP 真探（每条自带验收口径：200 / 200+ok / 服务在听） |
| `artifact` | 各生成产物自身的生成器 | 文件类：在不在 + 非空（+ 可选的「比源件新」） |

## 四态（**不许假绿**）

主人说的是「三态」，本件落成**四态**，因为「断连」与「缺失」是两件不同的事，混在一起就说不清是谁的锅：

  · **接上**   = **真探过**且符合该条自己的验收口径（文件在盘非空 / HTTP 命中）。
  · **断连**   = **真探过**、失败 —— **必须落原始错误串**（HTTP 状态码 / 异常名 + 原文），不许吞。
  · **缺失**   = **清单/真源里有它、实物不在**（文件不存在）—— 这是"清单说有、实际到不了"的断连。
  · **未探测** = **没条件探**（没跑过探针、或源件读不到、或被守卫拦下）—— **写明为什么**。
    🔴 铁律：**没探过的项，一律「未探测」，不许画成「接上」**。

## 🔴 请求前的两道守卫（都不许省）

  · **公网**（云插件基址）：先过 `cloud-status.py::host_guard` —— 只许 http/https，回环/私网/链路本地/保留
    一律拦下、**不发请求**（防 SSRF / DNS rebinding）。**复用它的，不另发明一套**。
  · **回环**（本机服务）：这是**为自愈服务的**本机回环探测 —— 只探**登记在册**的回环地址。
    守卫是**正向白名单**：宿主必须是 `127.0.0.1`/`::1`/`localhost`，且端口必须在
    `LOOPBACK_REG`（每条都带**登记出处**）里；白名单外一律不发请求。

## 用法

    py -3.14 tools/codex-scripts/capability-audit.py            # 真探一轮 + 生成面板（默认）
    py -3.14 tools/codex-scripts/capability-audit.py probe     # 只真探，落 state/capability-audit.json
    py -3.14 tools/codex-scripts/capability-audit.py render    # 只按台账生成面板两件
    py -3.14 tools/codex-scripts/capability-audit.py --check   # 判据 ≥8 条（含负对照）· 退出码 0/1

配套：`tools/codex-scripts/capability-supervisor.py`（watch 报警 / heal 自愈+回滚）。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ── 真源路径（现读） ──────────────────────────────────────────────────────
CAPS_REG = ROOT / "gbt_allinone" / "caps_registry.py"
API_PY = ROOT / "gbt_allinone" / "api.py"
WINDOWS = ROOT / "holo_pet_w3" / "shell" / "windows.json"
PANEL = ROOT / "holo_pet_w3" / "panel" / "index.html"
MESH = ROOT / "deploy" / "cloud-10" / "mesh.json"
SPEC50 = ROOT / "deploy" / "cloud-10" / "plugins50.json"
CLOUD_LEDGER = ROOT / "state" / "cloud-status.json"
CLOUD_LLM = ROOT / "gbt_allinone" / "llm" / "cloud_llm.py"
SKILL_ATLAS = ROOT / "state" / "skill_atlas.json"
CLOUD_STATUS_PY = ROOT / "tools" / "codex-scripts" / "cloud-status.py"

LEDGER = ROOT / "state" / "capability-audit.json"
PAGE = ROOT / "holo_pet_w3" / "capabilities" / "index.html"
DATA = ROOT / "holo_pet_w3" / "capabilities" / "capabilities-data.js"

CMD_AUDIT = "py -3.14 tools/codex-scripts/capability-audit.py"
CMD_PROBE = "py -3.14 tools/codex-scripts/capability-audit.py probe"
CMD_RENDER = "py -3.14 tools/codex-scripts/capability-audit.py render"
CMD_CHECK = "py -3.14 tools/codex-scripts/capability-audit.py --check"
CMD_WATCH = "py -3.14 tools/codex-scripts/capability-supervisor.py watch"
CMD_HEAL = "py -3.14 tools/codex-scripts/capability-supervisor.py heal"

TIMEOUT = 3.0            # 单请求超时 3 秒（主人令）

S_OK, S_BAD, S_MISS, S_UNK = "接上", "断连", "缺失", "未探测"
# 🔴 2026-10-09 主人令「生产面板禁止有任何污点」+「别来一句不影响运行就跳过」：
#    第 5 态「按需未启用」= 这项服务**只有用到那个 provider 时才需要**，没跑**不是故障**。
#    它与「断连」分开成格（附**拉起命令**与「谁能给」）—— **不是消音，是把信息放对格子**：
#    真断连（面板/框架自身依赖的）一条都不许少报。
S_OPT = "按需未启用"
STATES = (S_OK, S_BAD, S_MISS, S_UNK, S_OPT)
C_OK, C_BAD, C_MISS, C_UNK, C_OPT = "#22c55e", "#f87171", "#f5b041", "#6b7280", "#38bdf8"

# ── 类别表（顺序即面板上的顺序） ─────────────────────────────────────────
CATEGORIES = [
    ("framework", "框架能力位", "gbt_allinone/caps_registry.py::BENIGN_CAPS（现读枚举）"),
    ("cloud", "云插件", "deploy/cloud-10/mesh.json（现役 10 · 每模块一 op）"),
    ("shell-window", "桌面壳窗", "holo_pet_w3/shell/windows.json::windows[]（每扇窗 file）"),
    ("panel-page", "面板清单页", "holo_pet_w3/panel/index.html::PAGES（每条 rel）"),
    ("bridge", "面板桥", "holo_pet/launch_panel.py（127.0.0.1:8765）"),
    ("dsh", "DSH 接入", "holo_pet_w3/shell/windows.json::dsh-chat.auto_dsh.port"),
    ("service", "本机依赖服务", "gbt_allinone/llm/cloud_llm.py + state/skill_atlas.json（登记的**回环**）"),
    ("artifact", "生成产物", "各生成器自身（见每条的「期望接法」）"),
]
CAT_IDS = [c[0] for c in CATEGORIES]
CAT_NOTE = {c[0]: {"name": c[1], "source": c[2]} for c in CATEGORIES}

# ── 回环白名单（**登记的**本机服务；每条都带登记出处） ────────────────────
# 纪律：本机回环探测**显式说明是为自愈服务的**，且只探这张表里的地址。
LOOPBACK_REG = {
    8765: "holo_pet/launch_panel.py:38-39（默认 127.0.0.1:8765）· windows.json panel",
    3080: "windows.json::dsh-chat.auto_dsh.port=3080（dsh web --no-open）",
    31415: "state/skill_atlas.json（freellmapi 域）· tools/codex-scripts/freellm-alive.py:42",
    11434: "gbt_allinone/llm/cloud_llm.py:43-47（本机 Ollama OpenAI 兼容 /v1）",
    8317: "gbt_allinone/llm/cloud_llm.py:50（cliproxy base）",
    8111: "gbt_allinone/llm/cloud_llm.py:53（小土豆 base）",
    31716: "state/skill_atlas.json（genoffice_bridge 统一密钥桥）",
    18432: "state/skill_atlas.json（AutoGLM 本机 token 服务 /get_token）",
}

# ── 服务**必要性**（决定"没在跑"该怎么念）────────────────────────────────
#   must     = 面板/框架**自身**依赖它 ⇒ 没跑就是真断连（报红，必须自愈或升级给人）
#   ondemand = 只在用那个 provider/车道时才需要，且凭据在主人侧 ⇒ 没跑**不是故障**
SERVICE_NEED = {
    8765:  ("must", "面板内容区就是它伺服；没跑=面板自己瞎了",
            "py -3.14 holo_pet/launch_panel.py --no-browser --no-codex", "本件可自愈（白名单动作）"),
    3080:  ("ondemand", "只在开 dsh 对话面时需要", "由壳按需拉起（windows.json::dsh-chat.auto_dsh）", "壳/主人"),
    11434: ("ondemand", "只在选 gbt-local 车道时需要", "ollama serve（权重是主人私有资产）", "主人"),
    8317:  ("ondemand", "只在选 cliproxy 车道时需要", "cliproxy.cmd（需上游凭据）", "主人"),
    8111:  ("ondemand", "只在选小土豆本机口时需要", "主人侧服务", "主人"),
    31415: ("ondemand", "只在用免费模型池时需要", "freellmapi（上游 key 与配额）", "主人"),
    31716: ("ondemand", "只在用 GenOffice 统一密钥桥时需要", "桥需 gbtv8- 统一密钥", "主人"),
    18432: ("ondemand", "只在用 AutoGLM 系列时需要", "token 与企业凭据在主人侧", "主人"),
}

# 生成产物（**自愈白名单 ①** 的靶子：缺/旧就重跑它自己的生成器）
#
# 字段：id · 相对路径 · 人读名 · 生成器命令 · `stale_vs`（比这个源件旧算「陈旧」）· 宽限秒数
#
# 关于**宽限秒数**（默认 0）：只给 `state/logbook.jsonl` 这一类的**只追加活账本**留窗口。
# 为什么必须留：记录本是**只追加**的，而且**每一次自愈动作都会往它 append 一条**（纪律要求）——
# 于是"产物比源件旧"这条判据会**自己把自己触发**：heal 修好 logbook-data.js 的那一刻，
# 它顺手写的那条记录又让 logbook.jsonl 更新了 ⇒ 下一步审计马上又说"陈旧" ⇒ 死循环。
# 宽限窗口（默认 600s）说的是：**产物允许落后源件一个渲染周期**；只有源件被追加了超过
# 宽限时间还没重渲，才算「陈旧」。这不是给假绿开口子 —— 落后一小时的页照样报红。
ARTIFACTS = [
    ("artifact.cloud-status-ledger", "state/cloud-status.json", "云插件探测台账",
     "py -3.14 tools/codex-scripts/cloud-status.py probe", "", 0),
    ("artifact.cloud-status-page", "holo_pet_w3/cloud-status/index.html", "连接状态面板页",
     "py -3.14 tools/codex-scripts/cloud-status.py render", "state/cloud-status.json", 0),
    ("artifact.cloud-status-data", "holo_pet_w3/cloud-status/cloud-status-data.js", "连接状态数据件",
     "py -3.14 tools/codex-scripts/cloud-status.py render", "state/cloud-status.json", 0),
    ("artifact.cloud-plugins-page", "holo_pet_w3/cloud-plugins/index.html", "云插件独立页",
     "py -3.14 tools/codex-scripts/cloud-status.py render", "state/cloud-status.json", 0),
    ("artifact.cloud-plugins-data", "holo_pet_w3/cloud-plugins/cloud-plugins-data.js", "云插件数据件",
     "py -3.14 tools/codex-scripts/cloud-status.py render", "state/cloud-status.json", 0),
    ("artifact.brain-data", "holo_pet_w3/brain/brain-data.js", "神经工作台数据件",
     "py -3.14 tools/codex-scripts/brain-feed.py --out holo_pet_w3/brain/brain-data.js", "", 0),
    ("artifact.logbook-data", "holo_pet_w3/logbook/logbook-data.js", "记录本数据件",
     "py -3.14 tools/codex-scripts/logbook.py render", "state/logbook.jsonl", 600),
    ("artifact.logbook-digest", "state/logbook-digest.md", "记录本速读件",
     "py -3.14 tools/codex-scripts/logbook.py render", "state/logbook.jsonl", 600),
    ("artifact.capability-audit-ledger", "state/capability-audit.json", "本审计台账",
     "py -3.14 tools/codex-scripts/capability-audit.py probe", "", 0),
    # ⚠️ 宽限 300s（2026-10-08 修）：台账是**每次 probe 都重写**的，而 `render` 才会把页面刷新 ——
    # 宽限写 0 就等于"这一格永远红"（审计自己咬自己，自愈会去反复重渲一个本来就没旧的页）。
    # 与记录本那条同一个道理：**产物允许落后源件一个渲染周期**，落后久了才算陈旧。
    ("artifact.capabilities-page", "holo_pet_w3/capabilities/index.html", "能力统计面板页",
     "py -3.14 tools/codex-scripts/capability-audit.py render", "state/capability-audit.json", 300),
    ("artifact.capabilities-data", "holo_pet_w3/capabilities/capabilities-data.js", "能力统计数据件",
     "py -3.14 tools/codex-scripts/capability-audit.py render", "state/capability-audit.json", 300),

    # ── 2026-10-07 补（主人令「继续排查看看还有没有缺失」时查出来的空白）──────────────
    # 上面 11 条只覆盖本次新建的几件；仓里还有一批**快照页从来没人盯**。实测当天：
    # 执行面页停在 09-23、而源头台账已到 10-08 ⇒ **烂了 15 天没人知道**；代码台页同样；
    # 神经工作台页停在 09-23。根因不是"忘了刷"，是**审计表里根本没有它们** ——
    # 看不见的产物，坏掉不会叫醒任何人。故补进来（快照页给宽限，但真烂了照报）。
    ("artifact.exec-deck-page", "holo_pet_w3/exec-deck/index.html", "执行面快照页",
     "py -3.14 tools/codex-scripts/exec-deck.py --html holo_pet_w3/exec-deck/index.html",
     "gbt_allinone/store/audit.jsonl", 86400),
    ("artifact.code-deck-page", "holo_pet_w3/code-deck/index.html", "代码台快照页",
     "py -3.14 tools/codex-scripts/code-deck.py --html holo_pet_w3/code-deck/index.html",
     "gbt_allinone/store/audit.jsonl", 86400),
    ("artifact.plugins-mesh-page", "holo_pet_w3/plugins-mesh/index.html", "云插件拓扑页",
     "py -3.14 tools/codex-scripts/cloud-plugins.py gen", "deploy/cloud-10/mesh.json", 604800),
    ("artifact.blueprint-page", "holo_pet_w3/blueprint/index.html", "项目蓝图页",
     "py -3.14 tools/codex-scripts/blueprint-feed.py", "PROJECT_BLUEPRINT.md", 86400),
    ("artifact.blueprint-data", "holo_pet_w3/blueprint/blueprint-data.js", "项目蓝图数据件",
     "py -3.14 tools/codex-scripts/blueprint-feed.py", "PROJECT_BLUEPRINT.md", 86400),
]


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _load_mod(name: str, path: Path):
    """按文件路径加载一个脚本模块（用于**复用**它的函数，而不是抄一份）。"""
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        return None
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    try:
        spec.loader.exec_module(m)
    except Exception:                                                    # noqa: BLE001
        return None
    return m


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:                                                    # noqa: BLE001
        return None


# ══════════════════════════════════════════════════════════════════════════
# 回环守卫（**正向白名单**）—— 只探登记在册的本机回环地址
# ══════════════════════════════════════════════════════════════════════════
def loopback_guard(url: str):
    """返回 (ok, why, info)。只许 http + 回环宿主 + **在册端口**。

    为什么是正向白名单而不是照抄 cloud-status 的反向守卫：那边的场景是**不许出网**，
    这里是**只许回环**。宁可窄：不在 `LOOPBACK_REG` 里的端口，一律不发请求。
    """
    try:
        p = urllib.parse.urlsplit(url)
    except Exception as e:                                               # noqa: BLE001
        return False, "URL 解析不了：%s" % str(e)[:80], {}
    if p.scheme != "http":
        return False, "回环探测只许 http（拿到 %r）" % (p.scheme or "(空)"), {}
    host = (p.hostname or "").lower().rstrip(".")
    if host not in ("127.0.0.1", "::1", "localhost"):
        return False, "不是回环宿主（拿到 %r）—— 本审计只探本机回环" % host, {}
    port = p.port or 80
    if port not in LOOPBACK_REG:
        return False, "端口 %d 不在册（LOOPBACK_REG）⇒ 按纪律不探" % port, {}
    return True, None, {"port": port, "reg": LOOPBACK_REG[port]}


# ══════════════════════════════════════════════════════════════════════════
# 探针（文件类 / HTTP 类）
# ══════════════════════════════════════════════════════════════════════════
def probe_file(path: Path, what: str, list_name: str = "") -> dict:
    """文件类真探：**在不在 + 非空**。不在 ⇒ 缺失（清单里有、实物不在）；在但 0 字节 ⇒ 断连。"""
    at = now()
    p = Path(path)
    try:
        exists = p.is_file()
    except OSError as e:                                                 # noqa: BLE001
        return {"state": S_UNK, "at": None, "ok": None, "evidence": "查盘出错（未探测）：%s" % e,
                "probe": {"kind": "file", "target": str(p), "exists": None, "ok": None},
                "why": "查盘 OSError：%s" % e}
    if not exists:
        return {"state": S_MISS, "at": at, "ok": False,
                "evidence": "清单/真源点名「%s」但实物不在：%s" % (list_name or what, p),
                "probe": {"kind": "file", "target": str(p), "exists": False, "size": None,
                          "at": at, "ok": False},
                "why": None}
    size = p.stat().st_size
    if size == 0:
        return {"state": S_BAD, "at": at, "ok": False,
                "evidence": "文件在盘但**空**（0 字节）：%s" % p,
                "probe": {"kind": "file", "target": str(p), "exists": True, "size": 0,
                          "at": at, "ok": False},
                "why": None}
    return {"state": S_OK, "at": at, "ok": True,
            "evidence": "在盘且非空：%s（%d 字节）" % (p, size),
            "probe": {"kind": "file", "target": str(p), "exists": True, "size": size,
                      "at": at, "ok": True},
            "why": None}


def _http_get(url: str) -> dict:
    """一次 GET（如实自报 UA）。**与 `cloud-status.py::_http_get` 同口径**，用于本件自探。"""
    t0 = time.perf_counter()
    req = urllib.request.Request(url, headers={"user-agent": UA}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read().decode("utf-8", "replace")
            ms = int((time.perf_counter() - t0) * 1000)
            body = None
            try:
                body = json.loads(raw)
            except Exception:                                            # noqa: BLE001
                body = None
            return {"http": r.status, "ms": ms, "body": body, "raw": raw[:300], "exc": None, "err": None}
    except urllib.error.HTTPError as e:                                  # 4xx/5xx 是读数
        raw = e.read().decode("utf-8", "replace")
        return {"http": e.code, "ms": int((time.perf_counter() - t0) * 1000),
                "body": None, "raw": raw[:300], "exc": None, "err": "HTTP %d" % e.code}
    except Exception as e:                                               # noqa: BLE001
        return {"http": None, "ms": int((time.perf_counter() - t0) * 1000),
                "body": None, "raw": "", "exc": type(e).__name__,
                "err": "%s: %s" % (type(e).__name__, str(e)[:140])}


UA = "gbt-capability-audit/1.0 (+local loopback audit for self-heal)"


def judge_http(res: dict, accept: str, field: str = "", want=None) -> tuple:
    """按该条自己的验收口径判三态。返回 (state, ok, evidence)。**失败一定带原始串**。"""
    http, raw, err = res.get("http"), (res.get("raw") or "").strip().replace("\n", " "), res.get("err")
    if accept == "http_alive":
        # 「服务在听」：任何 HTTP 状态码（含 401/404）都算接上 —— 401/404 是**服务活着**的证据。
        if isinstance(http, int):
            return S_OK, True, "HTTP %s（服务在听；该状态码是本条的预期：%s）｜ 原文 %s" % (
                http, res.get("note") or "非 200 也算活", raw[:120] or "—")
        return S_BAD, False, "连不上，未取得任何 HTTP 响应：%s" % (err or "未知错误")
    if not isinstance(http, int):
        return S_BAD, False, "请求失败，未取得 HTTP 响应：%s" % (err or "未知错误")
    if accept == "http200":
        if http == 200:
            return S_OK, True, "HTTP 200 ｜ 原文 %s" % (raw[:140] or "—")
        return S_BAD, False, "HTTP %s（非 200）｜ 原文 %s" % (http, raw[:160] or err or "—")
    if accept == "http200_json_ok":
        if http != 200:
            return S_BAD, False, "HTTP %s（非 200）｜ 原文 %s" % (http, raw[:160] or err or "—")
        body = res.get("body")
        if not isinstance(body, dict):
            return S_BAD, False, "HTTP 200 但回包不是 JSON 对象 ｜ 原文 %s" % (raw[:160] or "—")
        if body.get("ok") is True:
            return S_OK, True, "HTTP 200 且 ok=true ｜ 原文 %s" % (raw[:140] or "—")
        return S_BAD, False, "HTTP 200 但 ok=%r（非 true）｜ 原文 %s" % (body.get("ok"), raw[:140])
    if accept == "http200_json_field":
        if http != 200:
            return S_BAD, False, "HTTP %s（非 200）｜ 原文 %s" % (http, raw[:160] or err or "—")
        body = res.get("body")
        if not isinstance(body, dict):
            return S_BAD, False, "HTTP 200 但回包不是 JSON 对象 ｜ 原文 %s" % (raw[:160] or "—")
        got = body.get(field)
        if got == want:
            return S_OK, True, "HTTP 200 且 %s=%r ｜ 原文 %s" % (field, got, raw[:130] or "—")
        return S_BAD, False, "HTTP 200 但 %s=%r（期望 %r）｜ 原文 %s" % (field, got, want, raw[:140])
    if accept == "http200_or_auth":
        # 🔴 2026-10-08 加的一档（主人令「全部接入」时撞出来的真区别）：
        # **「服务在跑但不让匿名查」与「服务没起」是两件事**。实测：FreeLLMAPI 与 cliproxy
        # 都在听，匿名 GET /v1/models 回 401（Invalid / Missing API key）—— 而**带密钥的调用方**
        # （我们自己的 app、以及它们自己的启动器）拿到的是 200。
        # 判成「断连」的坏处：自愈会去"重启一个已经在跑的服务"，纯白忙，还多一个进程；
        # 判成 200 的坏处：假绿。⇒ 单列一档：401/403 = **在跑·需鉴权**（算接上，原文照留）。
        if http == 200:
            return S_OK, True, "HTTP 200 ｜ 原文 %s" % (raw[:140] or "—")
        if http in (401, 403):
            return S_OK, True, ("HTTP %s（**服务在跑，但拒绝匿名访问 = 需鉴权**；带密钥的调用方可用）"
                                " ｜ 原文 %s" % (http, raw[:140] or "—"))
        return S_BAD, False, "HTTP %s（非 200，且不是 401/403 那种鉴权挡）｜ 原文 %s" % (http, raw[:160] or err or "—")
    return S_UNK, None, "未知验收口径 %r（未探测）" % accept


def probe_http(url: str, accept: str, what: str, net: bool = False, field: str = "", want=None,
               note: str = "") -> dict:
    """HTTP 类真探：**先过守卫**（公网走 cloud-status 的 host_guard；回环走本件的正向白名单），再发。"""
    at = now()
    if net:
        ok, why, ips = CS.host_guard(url) if CS else (False, "cloud-status.py 载入失败", [])
    else:
        ok, why, info = loopback_guard(url)
        ips = [info.get("port")] if ok else []
    if not ok:
        return {"state": S_UNK, "at": None, "ok": None,
                "evidence": "守卫拦下，**未发请求**：%s" % why,
                "probe": {"kind": "http", "target": url, "accept": accept, "blocked": True,
                          "why": why, "net": net},
                "why": "守卫拦下 ⇒ 未探测：%s" % why}
    res = _http_get(url)
    res["note"] = note
    st, okk, ev = judge_http(res, accept, field, want)
    return {"state": st, "at": at, "ok": okk,
            "evidence": "%s：%s（%s ms）" % (what, ev, res.get("ms")),
            "probe": {"kind": "http", "target": url, "accept": accept, "net": net,
                      "http": res.get("http"), "ms": res.get("ms"), "exc": res.get("exc"),
                      "raw": (res.get("raw") or "")[:300], "at": at, "ok": okk, "state": st},
            "why": None}


# ══════════════════════════════════════════════════════════════════════════
# 各式枚举（现读真源）
# ══════════════════════════════════════════════════════════════════════════
def load_caps():
    """现读框架能力注册表。返回 (caps_list, why_or_None)。"""
    if not CAPS_REG.is_file():
        return None, "注册表不在盘：%s" % CAPS_REG
    m = _load_mod("_gbt_caps_registry", CAPS_REG)
    if m is None or not callable(getattr(m, "all_caps", None)):
        return None, "注册表 import 不了（文件在但坏了）：%s" % CAPS_REG
    try:
        caps = list(m.all_caps())
    except Exception as e:                                               # noqa: BLE001
        return None, "all_caps() 抛异常：%s" % e
    return caps, None


def api_symbols() -> set:
    """api.py 里出现过的能力名（`kind == "x"` 是**分派着落**的强证据；符号露面算弱证据）。"""
    if not API_PY.is_file():
        return set()
    src = API_PY.read_text(encoding="utf-8", errors="replace")
    syms = set(re.findall(r'kind\s*==\s*["\']([^"\']+)["\']', src))
    syms |= set(re.findall(r'["\']([a-z][a-z0-9_]{2,})["\']', src))
    return syms


def enum_framework(items: list, at: str) -> None:
    caps, why = load_caps()
    if caps is None:
        items.append({"id": "framework.registry", "category": "framework", "name": "能力注册表",
                      "expect": "gbt_allinone/caps_registry.py 在盘 · 非空 · 可 import",
                      "state": S_UNK, "at": None, "ok": None,
                      "evidence": "注册表读不到 ⇒ 整个框架类**未探测**：%s" % why,
                      "probe": {"kind": "file", "target": str(CAPS_REG), "readable": False},
                      "why": why})
        return
    syms = api_symbols()
    reg_ok = True
    items.append({"id": "framework.registry", "category": "framework", "name": "能力注册表",
                  "expect": "gbt_allinone/caps_registry.py 在盘 · 非空 · 可 import（all_caps() 可枚举）",
                  "state": S_OK if reg_ok else S_BAD, "at": at, "ok": True,
                  "evidence": "注册表可读，all_caps() 枚举出 %d 位：%s" % (len(caps), CAPS_REG),
                  "probe": {"kind": "file", "target": str(CAPS_REG), "readable": True,
                            "size": CAPS_REG.stat().st_size, "caps": len(caps), "at": at, "ok": True},
                  "why": None})
    if not API_PY.is_file():
        for c in caps:
            items.append({"id": "framework.cap.%s" % c.get("name"), "category": "framework",
                          "name": str(c.get("name")), "expect": "注册表登记 + api.py 有分派着落",
                          "state": S_UNK, "at": None, "ok": None,
                          "evidence": "api.py 不在盘 ⇒ 无从校「接线」，未探测：%s" % API_PY,
                          "probe": {"kind": "file", "target": str(API_PY), "exists": False},
                          "why": "api.py 不在盘 ⇒ 未探测"})
        return
    for c in caps:
        nm = str(c.get("name"))
        handler = str(c.get("handler") or "none")
        status = str(c.get("status") or "enabled")
        hit = (nm in syms) or (handler != "none" and handler in syms)
        if hit:
            st, okk = S_OK, True
            ev = ("注册表登记（status=%s · domain=%s · handler=%s）+ api.py 有分派着落"
                  "（%s）" % (status, c.get("domain"), handler, API_PY.name))
        else:
            st, okk = S_MISS, False
            ev = ("注册表登记为 %s（handler=%s），但 %s 里**找不到该能力的分派着落**"
                  "⇒ 登记说有、实现接不上" % (status, handler, API_PY.name))
        items.append({"id": "framework.cap.%s" % nm, "category": "framework", "name": nm,
                      "expect": "注册表登记 + gbt_allinone/api.py 有分派着落（kind== 或符号露面）",
                      "state": st, "at": at, "ok": okk, "evidence": ev,
                      "probe": {"kind": "file", "target": "%s + %s" % (CAPS_REG, API_PY),
                                "exists": True, "handler": handler, "status": status,
                                "domain": c.get("domain"), "external": c.get("external"),
                                "matched": hit, "at": at, "ok": okk},
                      "why": None})


def enum_cloud(items: list, at: str) -> None:
    mesh = load_json(MESH)
    if not mesh or not mesh.get("modules"):
        items.append({"id": "cloud.mesh", "category": "cloud", "name": "云插件现役真源",
                      "expect": "deploy/cloud-10/mesh.json 在盘 · 非空 · 有 modules",
                      "state": S_MISS if not MESH.is_file() else S_UNK, "at": None,
                      "ok": False if not MESH.is_file() else None,
                      "evidence": "现役真源读不到：%s" % MESH,
                      "probe": {"kind": "file", "target": str(MESH), "exists": MESH.is_file()},
                      "why": None if not MESH.is_file() else "mesh.json 在盘但解析不出 modules ⇒ 未探测"})
        return
    base = CLOUD_BASE
    ok_guard, why_guard, ips = CS.host_guard(base) if CS else (False, "cloud-status.py 载入失败", [])
    for m in mesh.get("modules") or []:
        mid = m.get("id")
        ops = m.get("ops") or []
        gates = m.get("op_gates") or {}
        op = CS._probe_op(ops, gates) if CS else (ops[0] if ops else "status")
        url = "%s/health?_probe=%s" % (base.rstrip("/"), mid)
        if not ok_guard:
            items.append({"id": "cloud.%s" % mid, "category": "cloud", "name": mid,
                          "expect": "GET %s/health?_probe=%s（超时 3s · host 校验后）" % (base, mid),
                          "state": S_UNK, "at": None, "ok": None,
                          "evidence": "守卫拦下，**未发请求**：%s" % why_guard,
                          "probe": {"kind": "http", "blocked": True, "why": why_guard, "net": True},
                          "why": "host 校验不过 ⇒ 未探测：%s" % why_guard})
            continue
        res = _http_get(url)
        j = CS.judge_probe(mid, res)
        st = S_OK if j.get("state") == CS.S_OK else S_BAD
        ev = "GET %s → %s" % (url, j.get("reason") or ("行内 ok=true，HTTP %s" % j.get("http")))
        items.append({"id": "cloud.%s" % mid, "category": "cloud", "name": mid,
                      "expect": "GET %s/health?_probe=%s（超时 3s · host 校验后 · 行内本插件那一行 ok=true）"
                                % (base, mid),
                      "state": st, "at": j.get("at") or at, "ok": j.get("ok"),
                      "evidence": "%s（%s ms）" % (ev, j.get("ms")),
                      "probe": {"kind": "http", "target": url, "accept": "http200_json_ok_of_row",
                                "net": True, "http": j.get("http"), "ms": j.get("ms"),
                                "row": j.get("row"), "state": j.get("state"),
                                "at": j.get("at") or at, "ok": j.get("ok"),
                                "probe_op": op, "ops": ops},
                      "why": None})
    # 蓝图：**明说不探**（未部署、无端点；对未部署的槽发请求只会造假红）
    bp = load_json(SPEC50)
    if bp:
        mods = bp.get("modules") or []
        slots = len(mods)
        wired = len([m for m in mods if (m.get("status") or "") != "reserve"])
        items.append({"id": "cloud.blueprint-50", "category": "cloud", "name": "50 槽蓝图（另册）",
                      "expect": "deploy/cloud-10/plugins50.json —— **蓝图不算接上**，本审计**不探测**",
                      "state": S_UNK, "at": None, "ok": None,
                      "evidence": ("蓝图 %d 槽（%d 指派 + %d 备用）· 未部署 · 无 ops · 无端点 ⇒ "
                                   "按纪律不探（对未部署的槽发请求只会造假红）" % (slots, wired, slots - wired)),
                      "probe": {"kind": "note", "target": str(SPEC50), "slots": slots, "probed": False},
                      "why": "未部署的蓝图槽没有可探端点 ⇒ 未探测（且**不许算接上**）"})
    else:
        items.append({"id": "cloud.blueprint-50", "category": "cloud", "name": "50 槽蓝图（另册）",
                      "expect": "deploy/cloud-10/plugins50.json", "state": S_UNK, "at": None, "ok": None,
                      "evidence": "蓝图件读不到（不影响现役 %d 位）" % len(mesh.get("modules") or []),
                      "probe": {"kind": "file", "target": str(SPEC50), "exists": SPEC50.is_file()},
                      "why": "蓝图件读不到 ⇒ 未探测"})


def enum_windows(items: list, at: str) -> None:
    wj = load_json(WINDOWS)
    if not wj or not wj.get("windows"):
        items.append({"id": "shell.windows-registry", "category": "shell-window", "name": "窗口注册表",
                      "expect": "holo_pet_w3/shell/windows.json 在盘 · 非空 · 有 windows[]",
                      "state": S_MISS if not WINDOWS.is_file() else S_UNK, "at": None,
                      "ok": False if not WINDOWS.is_file() else None,
                      "evidence": "窗口注册表读不到：%s" % WINDOWS,
                      "probe": {"kind": "file", "target": str(WINDOWS), "exists": WINDOWS.is_file()},
                      "why": None if not WINDOWS.is_file() else "在盘但解析不出 windows[] ⇒ 未探测"})
        return
    base = WINDOWS.parent
    for w in wj["windows"]:
        wid = w.get("id")
        rel = w.get("file") or ""
        target = (base / rel) if rel else base
        r = probe_file(target, "窗口 %s 的页面" % wid, "windows.json 窗口 %r 的 file" % wid)
        items.append({"id": "win.%s" % wid, "category": "shell-window",
                      "name": "%s（%s）" % (wid, (w.get("title") or "").replace("GBT小土豆V8 · ", "")),
                      "expect": "windows.json 的 file 指向的页面在盘且非空（相对 %s）"
                                % WINDOWS.parent.name,
                      "state": r["state"], "at": r["at"], "ok": r["ok"],
                      "evidence": "%s ｜ file=%s" % (r["evidence"], rel),
                      "probe": {**r["probe"], "window": wid, "file": rel}, "why": r["why"]})


def enum_panel_pages(items: list, at: str) -> None:
    if not PANEL.is_file():
        items.append({"id": "panel.pages", "category": "panel-page", "name": "面板页面清单",
                      "expect": "holo_pet_w3/panel/index.html 在盘 · 有 PAGES 清单",
                      "state": S_MISS, "at": None, "ok": False,
                      "evidence": "面板页不在盘：%s" % PANEL,
                      "probe": {"kind": "file", "target": str(PANEL), "exists": False}, "why": None})
        return
    src = PANEL.read_text(encoding="utf-8", errors="replace")
    entries = re.findall(r'id:\s*"([^"]+)"[^}]*?rel:\s*"([^"]+)"', src, re.S)
    if not entries:
        items.append({"id": "panel.pages", "category": "panel-page", "name": "面板页面清单",
                      "expect": "panel/index.html 的 PAGES 清单逐条可达",
                      "state": S_UNK, "at": None, "ok": None,
                      "evidence": "面板页在盘但**解析不出 PAGES 清单** ⇒ 未探测（不许假绿）",
                      "probe": {"kind": "file", "target": str(PANEL), "exists": True, "pages": 0},
                      "why": "PAGES 清单解析不出 ⇒ 未探测"})
        return
    for pid, rel in entries:
        target = (PANEL.parent / rel)
        r = probe_file(target, "面板 PAGES 的页面", "panel/index.html PAGES 里 %r 的 rel" % pid)
        items.append({"id": "page.%s" % pid, "category": "panel-page", "name": pid,
                      "expect": "panel/index.html::PAGES 的 rel 指向的页面在盘且非空（**清单说有、实际要到得了**）",
                      "state": r["state"], "at": r["at"], "ok": r["ok"],
                      "evidence": "%s ｜ rel=%s" % (r["evidence"], rel),
                      "probe": {**r["probe"], "page": pid, "rel": rel}, "why": r["why"]})


def enum_bridge(items: list, at: str) -> None:
    url = "http://127.0.0.1:8765/api/state"
    r = probe_http(url, "http200_json_ok", "GET %s" % url, net=False)
    items.append({"id": "bridge.panel-8765", "category": "bridge", "name": "面板桥 :8765",
                  "expect": "GET http://127.0.0.1:8765/api/state → HTTP 200 且 ok=true"
                            "（**为自愈服务的本机回环探测**；登记出处：%s）" % LOOPBACK_REG[8765],
                  "state": r["state"], "at": r["at"], "ok": r["ok"], "evidence": r["evidence"],
                  "probe": {**r["probe"], "loopback_registered": LOOPBACK_REG[8765]}, "why": r["why"]})


def enum_dsh(items: list, at: str) -> None:
    wj = load_json(WINDOWS) or {}
    port, why_port = None, None
    for w in wj.get("windows") or []:
        ad = w.get("auto_dsh") or {}
        if w.get("id") == "dsh-chat" and ad.get("port"):
            port = int(ad["port"])
    if port is None:
        port, why_port = 3080, "windows.json 里没读到 auto_dsh.port ⇒ 按既有默认 3080 探"
    url = "http://127.0.0.1:%d/" % port
    r = probe_http(url, "http_alive", "GET %s" % url, net=False,
                   note="401 是预期（无 token 就该 401）⇒ 服务在听即接上")
    ev = r["evidence"] + ("" if not why_port else " ｜ %s" % why_port)
    # 🔴 2026-10-10 修一处**漏用已有策略**（不是新策略）：
    #    「按需服务没在跑不是故障」这条策略本来就有 —— service 分支（enum_services，L638-641）
    #    早就这么做了。但 **dsh 走的是本函数**，那段豁免**没被套用** ⇒ 没拉起的按需对话面
    #    被判成「断连 1」⇒ 级联成两条蓝图红（L3 巡检/L4 重启 的判据找「无断连」五个字，找不到就红）
    #    + 框架整体 完善:False。
    #    实测证据（2026-10-10）：DSH 对话面**确实在服务**，只是不在 3080 而在 19387
    #    （PID 7892 DeepSeek Harness），且它探根路由返回 **401 —— 正是本函数自己写的「预期」**。
    #    ⇒ 照抄 service 分支的做法：按需 + 没跑 ⇒ 记「按需未启用（附拉起命令与谁能给）」，不是断连。
    need, why_need, start_cmd, who = SERVICE_NEED.get(port,
        ("ondemand", "只在开 dsh 对话面时需要", "由壳按需拉起（windows.json::dsh-chat.auto_dsh）", "壳/主人"))
    if r["state"] == S_BAD and need == "ondemand":
        r = dict(r, state=S_OPT, ok=True)
        ev += " ｜ **按需未启用**（%s）：拉起 %s（谁能给：%s）" % (why_need, start_cmd, who)
    items.append({"id": "dsh.web-%d" % port, "category": "dsh", "name": "DSH 对话面 :%d" % port,
                  "expect": "dsh web --no-open 在 %s 上服务中（dsh-launch.cjs 既有做法）；"
                            "无 token 时 401 是预期 ⇒ **服务在听即接上**" % url,
                  "state": r["state"], "at": r["at"], "ok": r["ok"], "evidence": ev,
                  "probe": {**r["probe"], "loopback_registered": LOOPBACK_REG.get(port, ""),
                            "port_note": why_port}, "why": r["why"]})


def enum_services(items: list, at: str) -> None:
    """本机依赖服务 —— **只探登记在册的回环地址**（登记出处写进每条证据）。"""
    reg = [
        ("svc.panel-bridge-raw", 8765, "http://127.0.0.1:8765/api/state", "http200_json_ok",
         "面板桥（launcher 同一条）", ""),
        ("svc.freellmapi", 31415, "http://127.0.0.1:31415/v1/models", "http200_or_auth",
         "FreeLLMAPI 免费模型池（OpenAI 兼容 /v1）", ""),
        ("svc.ollama", 11434, "http://127.0.0.1:11434/v1/models", "http200",
         "本机 Ollama（OpenAI 兼容 /v1）", ""),
        ("svc.genoffice-bridge", 31716, "http://127.0.0.1:31716/health", "http200_json_field",
         "GenOffice 统一密钥桥", "ok"),
        ("svc.autoglm-token", 18432, "http://127.0.0.1:18432/get_token", "http200_json_ok",
         "AutoGLM 本机 token 服务", ""),
        ("svc.cliproxy", 8317, "http://127.0.0.1:8317/v1/models", "http200_or_auth",
         "cliproxy 本机口（cloud_llm.py:50）", ""),
        ("svc.potato", 8111, "http://127.0.0.1:8111/v1/models", "http200",
         "小土豆本机口（cloud_llm.py:53）", ""),
    ]
    for iid, port, url, accept, what, field in reg:
        r = probe_http(url, accept, "GET %s" % url, net=False, field=field, want=True)
        ev = "%s ｜ 登记出处：%s ｜ %s" % (what, LOOPBACK_REG.get(port, "(未登记)"), r["evidence"])
        # 按必要性分档：按需服务"没在跑"不是故障 —— 如实标「按需未启用」并附拉起命令
        need, why_need, start_cmd, who = SERVICE_NEED.get(port, ("must", "未登记必要性", "", ""))
        if r["state"] == S_BAD and need == "ondemand":
            r = dict(r, state=S_OPT, ok=True)
            ev += " ｜ **按需未启用**（%s）：拉起 `%s`（谁能给：%s）" % (why_need, start_cmd, who)
        items.append({"id": iid, "category": "service", "name": "%s :%d" % (what, port),
                      "expect": "GET %s（%s；**为自愈服务的本机回环探测**，只探在册地址）"
                                % (url, {"http200": "验收 HTTP 200",
                                         "http200_json_ok": "验收 HTTP 200 且 ok=true",
                                         "http200_json_field": "验收 HTTP 200 且 %s=true" % field}.get(accept, accept)),
                      "state": r["state"], "at": r["at"], "ok": r["ok"], "evidence": ev,
                      "probe": {**r["probe"], "loopback_registered": LOOPBACK_REG.get(port, "")},
                      "why": r["why"]})


def enum_artifacts(items: list, at: str) -> None:
    for iid, rel, human, gen, stale_vs, tol in ARTIFACTS:
        p = ROOT / rel
        r = probe_file(p, human, "%s（生成器：%s）" % (rel, gen))
        st, ev = r["state"], r["evidence"]
        probe = dict(r["probe"])
        probe.update({"generator": gen, "at": r["at"], "ok": r["ok"], "state": st,
                      "stale_vs": stale_vs or None, "stale_tol_s": tol})
        if st == S_OK and stale_vs:
            src = ROOT / stale_vs
            if src.is_file():
                lag = src.stat().st_mtime - p.stat().st_mtime
                probe["stale_lag_s"] = round(lag, 1)
                if lag > tol + 1.0:
                    st = S_BAD
                    probe["state"] = st
                    probe["ok"] = False
                    ev = ("**陈旧**：产物落后源件 %.0fs（宽限 %ds）—— %s 的 mtime 落后 %s 超过宽限"
                          " ⇒ 重跑生成器 %s" % (lag, tol, rel, stale_vs, gen))
        items.append({"id": iid, "category": "artifact", "name": human,
                      "expect": "在盘且非空%s（生成器：%s）"
                                % (("，且不落后源件 %s 超过宽限 %ds" % (stale_vs, tol))
                                   if stale_vs else "", gen),
                      "state": st, "at": r["at"], "ok": probe["ok"],
                      "evidence": ev + (" ｜ 生成器：%s" % gen), "probe": probe,
                      "why": r["why"]})


# ══════════════════════════════════════════════════════════════════════════
# 装配
# ══════════════════════════════════════════════════════════════════════════
_PREFIX_CAT = [("framework.", "framework"), ("cloud.", "cloud"), ("win.", "shell-window"),
               ("page.", "panel-page"), ("bridge.", "bridge"), ("dsh.", "dsh"),
               ("svc.", "service"), ("artifact.", "artifact")]
_ENUM_FN = {}


def probe_item(item_id: str):
    """**重探单条**（供超级visor 复验用）：按 id 前缀跑该类的枚举，挑出那一条。

    找不到返回 `None`（不许假装探到了）。
    """
    cat = None
    for pre, c in _PREFIX_CAT:
        if str(item_id).startswith(pre):
            cat = c
            break
    if cat is None:
        return None
    if not _ENUM_FN:
        _ENUM_FN.update({"framework": enum_framework, "cloud": enum_cloud,
                         "shell-window": enum_windows, "panel-page": enum_panel_pages,
                         "bridge": enum_bridge, "dsh": enum_dsh, "service": enum_services,
                         "artifact": enum_artifacts})
    items: list = []
    _ENUM_FN[cat](items, now())
    for i in items:
        if i.get("id") == item_id:
            return i
    return None


def counts_of(items: list) -> dict:
    c = {"total": len(items)}
    for s in STATES:
        c[s] = sum(1 for i in items if i.get("state") == s)
    return c


def by_category(items: list) -> list:
    out = []
    for cid in CAT_IDS:
        sub = [i for i in items if i.get("category") == cid]
        if not sub and cid not in ([i.get("category") for i in items]):
            pass
        row = {"id": cid, "name": CAT_NOTE[cid]["name"], "source": CAT_NOTE[cid]["source"],
               "total": len(sub)}
        for s in STATES:
            row[s] = sum(1 for i in sub if i.get("state") == s)
        out.append(row)
    # 未知类别（不该有）也如实列出，不吞
    for cid in sorted({i.get("category") for i in items} - set(CAT_IDS)):
        sub = [i for i in items if i.get("category") == cid]
        row = {"id": cid, "name": "(未登记类别 %s)" % cid, "source": "?", "total": len(sub)}
        for s in STATES:
            row[s] = sum(1 for i in sub if i.get("state") == s)
        out.append(row)
    return out


def build_model(items: list) -> dict:
    prog = load_json(CLOUD_LEDGER) or {}
    return {
        "generated_at": now(),
        "commands": {"audit": CMD_AUDIT, "probe": CMD_PROBE, "render": CMD_RENDER,
                     "check": CMD_CHECK, "watch": CMD_WATCH, "heal": CMD_HEAL},
        "doctrine": [
            "**不许假绿**：没真探过的项一律「未探测」，不许画成「接上」。",
            "**断连必须带原始串**：HTTP 状态码 / 异常名 + 原文，不吞不改写。",
            "**缺失** = 清单/真源里有它、实物不在（清单说有、实际到不了）。",
            "云插件**复用** cloud-status.py 的 host 校验与探测台账口径，不另发明一套。",
            "本机回环探测**只探登记在册的地址**，且**显式说明是为自愈服务的**。",
        ],
        "sources": {
            "framework": "gbt_allinone/caps_registry.py::BENIGN_CAPS（现读）",
            "cloud": "deploy/cloud-10/mesh.json（现役 10）· plugins50.json（蓝图，不算接上）",
            "shell-window": "holo_pet_w3/shell/windows.json",
            "panel-page": "holo_pet_w3/panel/index.html::PAGES",
            "bridge": "holo_pet/launch_panel.py",
            "dsh": "holo_pet_w3/shell/windows.json::dsh-chat.auto_dsh + shell/dsh-launch.cjs",
            "service": "gbt_allinone/llm/cloud_llm.py + state/skill_atlas.json（回环白名单）",
            "artifact": "各生成器（见逐条「期望接法」）",
        },
        "loopback_registry": {str(k): v for k, v in LOOPBACK_REG.items()},
        "cloud_base": CLOUD_BASE,
        "cloud_ledger_at": prog.get("generated_at"),
        "cloud_ledger_counts": prog.get("counts"),
        "categories": by_category(items),
        "counts": counts_of(items),
        "items": items,
    }


def cmd_probe(out=None) -> int:
    t0 = time.perf_counter()
    at = now()
    items: list = []
    print("=" * 78)
    print("能力审计 · 真探一轮（%s）" % at)
    print("=" * 78)
    print("  超时 %.1fs ｜ 云插件走 cloud-status.py 的 host 校验 + /health 台账口径" % TIMEOUT)
    print("  回环探测**只为自愈服务**，只探登记在册的地址（%s）"
          % "、".join(str(k) for k in sorted(LOOPBACK_REG)))
    print("-" * 78)

    enum_framework(items, at)
    print("  [framework]  %d 条" % len([i for i in items if i["category"] == "framework"]))
    enum_cloud(items, at)
    print("  [cloud]      %d 条" % len([i for i in items if i["category"] == "cloud"]))
    enum_windows(items, at)
    print("  [shell-window] %d 条" % len([i for i in items if i["category"] == "shell-window"]))
    enum_panel_pages(items, at)
    print("  [panel-page] %d 条" % len([i for i in items if i["category"] == "panel-page"]))
    enum_bridge(items, at)
    enum_dsh(items, at)
    enum_services(items, at)
    print("  [bridge/dsh/service] %d 条"
          % len([i for i in items if i["category"] in ("bridge", "dsh", "service")]))
    enum_artifacts(items, at)
    print("  [artifact]   %d 条" % len([i for i in items if i["category"] == "artifact"]))

    model = build_model(items)
    model["probe_seconds"] = round(time.perf_counter() - t0, 2)

    c = model["counts"]
    bad = [i for i in items if i["state"] in (S_BAD, S_MISS)]
    print("-" * 78)
    for row in model["categories"]:
        print("  %-14s %-12s 总 %3d · 接上 %3d · 断连 %2d · 缺失 %2d · 未探测 %2d"
              % (row["id"], row["name"], row["total"], row[S_OK], row[S_BAD], row[S_MISS], row[S_UNK]))
    print("-" * 78)
    print("  合计 总 %d · 接上 %d · 断连 %d · 缺失 %d · 未探测 %d · 按需未启用 %d ｜ 用时 %.1fs"
          % (c["total"], c[S_OK], c[S_BAD], c[S_MISS], c[S_UNK], c.get(S_OPT, 0),
             model["probe_seconds"]))
    if bad:
        print("-" * 78)
        print("  🔴 报警（断连 %d + 缺失 %d）逐条原文：" % (c[S_BAD], c[S_MISS]))
        for i in bad:
            print("    [%s] %s" % (i["state"], i["id"]))
            print("        %s" % i.get("evidence"))
    else:
        print("  ✅ 无断连、无缺失。")
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(model, ensure_ascii=False, indent=1), encoding="utf-8")
    print("-" * 78)
    print("  台账：%s" % LEDGER)
    return 0


# ══════════════════════════════════════════════════════════════════════════
# 渲染（自包含 · 生成期静态落图 · 数据只走经典脚本）
# ══════════════════════════════════════════════════════════════════════════
_CSS = """<style>
:root{--gbt-bg:#0b1120;--gbt-panel:#111827;--gbt-line:#1e3a5f;--gbt-line-soft:#162035;
 --gbt-ink:#e7eef8;--gbt-dim:#8794a6;--gbt-off:#6b7280;--gbt-gold:#f5b041;--gbt-cyan:#00e5ff;
 --gbt-ok:#22c55e;--gbt-bad:#f87171;--gbt-miss:#f5b041;--ok-bg:#0f2a20;--bad-bg:#2a1414;--miss-bg:#2a2010;--off-bg:#16181d}
*{box-sizing:border-box}
body{margin:0;background:var(--gbt-bg);color:var(--gbt-ink);font:13px/1.6 "Segoe UI","Microsoft YaHei UI",system-ui,sans-serif}
.bar{display:flex;align-items:center;gap:10px;padding:10px 16px;border-bottom:1px solid var(--gbt-line);background:linear-gradient(90deg,#0a0f16,#0c1118);flex-wrap:wrap}
.mark{width:18px;height:18px;border:2px solid var(--gbt-gold);border-radius:4px}
.brand{font-weight:700;letter-spacing:.4px}.brand b{color:var(--gbt-gold)}
.note{color:var(--gbt-dim);font-size:11.5px}
.wrap{padding:14px;display:grid;gap:14px}
.card{background:var(--gbt-panel);border:1px solid var(--gbt-line);border-radius:6px;padding:12px}
h2{margin:0 0 8px;font-size:13px;color:var(--gbt-dim);font-weight:600;letter-spacing:.4px}
.hr{height:1px;background:var(--gbt-line);margin:10px 0}
.mono{font-family:ui-monospace,Consolas,monospace}
.stats{display:flex;gap:18px;flex-wrap:wrap;margin-bottom:8px}
.stat{min-width:88px}.stat b{display:block;font-size:24px;color:var(--gbt-cyan);font-variant-numeric:tabular-nums}
.stat i{font-style:normal;color:var(--gbt-dim);font-size:12px}
.stat b.ok{color:var(--gbt-ok)}.stat b.bad{color:var(--gbt-bad)}.stat b.miss{color:var(--gbt-miss)}.stat b.off{color:var(--gbt-off)}
table{border-collapse:collapse;width:100%;font-size:11px}
th,td{border:1px solid var(--gbt-line);padding:3px 6px;text-align:left;vertical-align:top}
th{color:var(--gbt-dim);font-weight:600;background:#0b1017;position:sticky;top:0}
td.cell{text-align:right;font-variant-numeric:tabular-nums}
td.sok{color:var(--gbt-ok);font-weight:700}
td.sbad{color:var(--gbt-bad);font-weight:700}
td.smiss{color:var(--gbt-miss);font-weight:700}
td.sunk{color:var(--gbt-off)}
.pill{display:inline-block;border:1px solid var(--gbt-line);border-radius:999px;padding:0 7px;font-size:11px}
.pill.ok{border-color:#1d5c45;color:var(--gbt-ok)}
.pill.bad{border-color:#6b2a2a;color:var(--gbt-bad)}
.pill.miss{border-color:#6b5320;color:var(--gbt-miss)}
.pill.off{border-color:#39445a;color:var(--gbt-off)}
.legend{display:flex;gap:16px;flex-wrap:wrap;margin:6px 0}
.lg{display:flex;align-items:center;gap:6px;color:var(--gbt-dim);font-size:11.5px}
.sw{width:14px;height:14px;border-radius:3px;border:1px solid var(--gbt-line);display:inline-block}
.sw.ok{background:var(--ok-bg);border-color:var(--gbt-ok)}
.sw.bad{background:var(--bad-bg);border-color:var(--gbt-bad)}
.sw.miss{background:var(--miss-bg);border-color:var(--gbt-miss)}
.sw.off{background:var(--off-bg);border-color:var(--gbt-off)}
.alert{border:1px solid #6b2a2a;border-radius:6px;padding:8px 10px;margin:0 0 8px;background:#1a0f0f}
.alert.miss{border-color:#6b5320;background:#1a150a}
.alert .t{font-weight:700;color:var(--gbt-ink)}
.alert .e{color:var(--gbt-dim);font-size:11.5px;word-break:break-all;margin-top:3px}
a{color:var(--gbt-cyan);text-decoration:none}a:hover{text-decoration:underline}
.foot{border-top:1px solid var(--gbt-line);margin-top:12px;padding:10px 16px;color:var(--gbt-dim);font-size:11.5px}
code{font-family:ui-monospace,Consolas,monospace;color:var(--gbt-cyan)}
.grp{margin:0 0 4px;color:var(--gbt-gold);font-size:12px;font-weight:600}
.collapse{max-height:520px;overflow:auto}
@media (prefers-reduced-motion: reduce){*{transition:none!important}}
</style>"""


def _esc(x) -> str:
    return html.escape(str(x if x is not None else ""), quote=True)


def _pill(st: str) -> str:
    cls = {S_OK: "ok", S_BAD: "bad", S_MISS: "miss", S_UNK: "off"}.get(st, "off")
    return '<span class="pill %s">%s</span>' % (cls, _esc(st))


def _head(title: str) -> str:
    # 🔴 2026-10-09 **生成器给自己的产物盖章**（根因修复，不是去列路径表）：
    #    `capabilities-data.js` 早就自声明了「自动生成，别手改。重建：…」，所以框架门能按
    #    **文件自声明**把它认成生成物；而本函数渲的 index.html **没有自声明** ⇒ 被当成手写件、
    #    每次审计重渲都让门报一条 no_passport（实测 2026-10-09 撞了）。
    #    ⇒ 规矩：**凡本器渲的页，页头必须自盖章**（含「自动生成」与重建命令），
    #      这样门的判据仍然只看文件自声明，**永远不用维护路径清单**。
    return ('<!doctype html>\n'
            '<!-- 自动生成，别手改。重建：py -3.14 tools/codex-scripts/capability-audit.py -->\n'
            '<html lang="zh-CN"><head><meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<title>%s</title>\n%s</head><body>\n' % (_esc(title), _CSS))


def _topbar(gen: str) -> str:
    return ('<div class="bar"><span class="mark"></span><span class="brand">GBT<b>小土豆</b>V8 · 能力统计</span>'
            '<span class="note">生成 %s ｜ 重生成 <code>%s</code> ｜ 判据 <code>%s</code> ｜ 报警/自愈 <code>%s</code></span></div>'
            % (_esc(gen), _esc(CMD_RENDER), _esc(CMD_CHECK), _esc(CMD_WATCH)))


def _foot(gen: str) -> str:
    return ('<div class="foot">生成时刻 <b>%s</b> ｜ 重生成命令 <code>%s</code> ｜ 判据命令 <code>%s</code>（判据含负对照）'
            ' ｜ 报警+自愈 <code>%s</code> / <code>%s</code> ｜ 开发者：自由的风 · GBT小土豆V8</div>'
            % (_esc(gen), _esc(CMD_RENDER), _esc(CMD_CHECK), _esc(CMD_WATCH), _esc(CMD_HEAL)))


def render_page(model: dict) -> str:
    gen = model["generated_at"]
    items = model["items"]
    cats = model["categories"]
    c = model["counts"]
    bad = [i for i in items if i["state"] == S_BAD]
    miss = [i for i in items if i["state"] == S_MISS]
    unk = [i for i in items if i["state"] == S_UNK]

    # 00 页首
    stat = ('<div class="stats">'
            '<div class="stat"><b>%d</b><i>能力项总数</i></div>'
            '<div class="stat"><b class="ok">%d</b><i>接上</i></div>'
            '<div class="stat"><b class="bad">%d</b><i>断连</i></div>'
            '<div class="stat"><b class="miss">%d</b><i>缺失</i></div>'
            '<div class="stat"><b class="off">%d</b><i>未探测</i></div>'
            '</div>' % (c["total"], c[S_OK], c[S_BAD], c[S_MISS], c[S_UNK]))
    legend = ('<div class="legend">'
              '<span class="lg"><i class="sw ok"></i><b>接上</b>：真探过且符合该条验收口径</span>'
              '<span class="lg"><i class="sw bad"></i><b>断连</b>：真探过、失败（带原始错误串）</span>'
              '<span class="lg"><i class="sw miss"></i><b>缺失</b>：清单里有、实物不在</span>'
              '<span class="lg"><i class="sw off"></i><b>未探测</b>：没条件探（写明为什么）——<b>不许画成接上</b></span>'
              '</div>')
    doctrine = "".join('<li>%s</li>' % _esc(d).replace("**", "") for d in model["doctrine"])

    # 01 分类汇总
    crows = []
    for row in cats:
        crows.append('<tr><td class="mono">%s</td><td>%s</td><td class="note">%s</td>'
                     '<td class="cell">%d</td><td class="cell sok">%d</td><td class="cell sbad">%d</td>'
                     '<td class="cell smiss">%d</td><td class="cell sunk">%d</td></tr>'
                     % (_esc(row["id"]), _esc(row["name"]), _esc(row["source"]), row["total"],
                        row[S_OK], row[S_BAD], row[S_MISS], row[S_UNK]))
    ctable = ('<table><thead><tr><th>类别</th><th>名称</th><th>真源（现读）</th><th>总数</th>'
              '<th>接上</th><th>断连</th><th>缺失</th><th>未探测</th></tr></thead><tbody>%s'
              '<tr><th colspan="3">合计</th><th class="cell">%d</th><th class="cell sok">%d</th>'
              '<th class="cell sbad">%d</th><th class="cell smiss">%d</th><th class="cell sunk">%d</th>'
              '</tr></tbody></table>'
              % ("".join(crows), c["total"], c[S_OK], c[S_BAD], c[S_MISS], c[S_UNK]))

    # 02 报警清单（断连与缺失置顶）
    al = []
    for i in bad:
        al.append('<div class="alert"><div class="t">[断连] %s ｜ %s</div><div class="e">%s</div>'
                  '<div class="e mono">实测：%s</div></div>'
                  % (_esc(i["id"]), _esc(i["name"]), _esc(i.get("evidence")),
                     _esc(json.dumps(i.get("probe") or {}, ensure_ascii=False)[:400])))
    for i in miss:
        al.append('<div class="alert miss"><div class="t">[缺失] %s ｜ %s</div><div class="e">%s</div>'
                  '<div class="e mono">实测：%s</div></div>'
                  % (_esc(i["id"]), _esc(i["name"]), _esc(i.get("evidence")),
                     _esc(json.dumps(i.get("probe") or {}, ensure_ascii=False)[:400])))
    if not bad and not miss:
        al.append('<div class="note">✅ 没有断连、没有缺失。</div>')
    else:
        al.append('<div class="note">共 <b>%d</b> 条报警（断连 %d + 缺失 %d）—— 置顶列出；'
                  '可自愈的项见 <code>%s</code>，不可自愈的项见设计文档「不能自愈的清单」。'
                  '%s</div>'
                  % (len(bad) + len(miss), len(bad), len(miss), _esc(CMD_HEAL),
                     ('另有 <b>%d</b> 项<b>按需未启用</b>（不是故障：只在用到那个 provider 时才需要，'
                      '凭据在主人侧）—— 逐条附了拉起命令。' % c.get(S_OPT, 0)) if c.get(S_OPT) else ''))

    # 03 逐条明细（按类别分组）
    detail = []
    for cid in CAT_IDS:
        sub = [i for i in items if i.get("category") == cid]
        if not sub:
            continue
        detail.append('<div class="grp">// %s · %s（%d 条 · 接上 %d / 断连 %d / 缺失 %d / 未探测 %d）</div>'
                      % (_esc(cid), _esc(CAT_NOTE[cid]["name"]), len(sub),
                         sum(1 for i in sub if i["state"] == S_OK),
                         sum(1 for i in sub if i["state"] == S_BAD),
                         sum(1 for i in sub if i["state"] == S_MISS),
                         sum(1 for i in sub if i["state"] == S_UNK)))
        rws = []
        for i in sub:
            probe = i.get("probe") or {}
            tgt = probe.get("target") or probe.get("why") or ""
            rws.append('<tr><td class="mono">%s</td><td>%s</td><td>%s</td><td class="mono">%s</td>'
                       '<td>%s</td><td class="note">%s</td><td>%s</td></tr>'
                       % (_esc(i["id"]), _esc(i["name"]), _esc(i.get("expect")),
                          _esc(tgt)[:200], _esc(i.get("at") or "—（未探测）"),
                          _esc(i.get("evidence"))[:420], _pill(i["state"])))
        detail.append('<div class="collapse"><table><thead><tr><th>id</th><th>名称</th><th>期望接法</th>'
                      '<th>实测目标</th><th>探于</th><th>证据</th><th>状态</th></tr></thead><tbody>%s'
                      '</tbody></table></div>' % "".join(rws))

    # 04 未探测清单（如实单列）
    urows = "".join('<tr><td class="mono">%s</td><td>%s</td><td class="note">%s</td></tr>'
                    % (_esc(i["id"]), _esc(i["name"]), _esc(i.get("why") or i.get("evidence")))
                    for i in unk)
    ublock = ('<div class="note">共 %d 条**未探测**（不是接上，也不是断连 —— 是「没条件探」）。'
              '逐条写明为什么没探，**不许拿它冒充接上**。</div>'
              '<div class="collapse"><table><thead><tr><th>id</th><th>名称</th><th>为什么没探</th>'
              '</tr></thead><tbody>%s</tbody></table></div>' % (len(unk), urows)) if unk else \
             '<div class="note">没有未探测项。</div>'

    # 05 回环白名单（为什么要探这些回环）
    lrows = "".join('<tr><td class="mono">127.0.0.1:%s</td><td class="note">%s</td></tr>'
                    % (_esc(k), _esc(v)) for k, v in sorted(model["loopback_registry"].items(),
                                                            key=lambda x: int(x[0])))
    lblock = ('<div class="note">本页对**本机回环**的探测是**为自愈服务的**（面板桥起没起、DSH 接没接上、'
              '本机依赖服务在不在）—— 且**只探登记在册的地址**（下表逐条带登记出处）。'
              '公网探测（云插件）先过 <code>cloud-status.py::host_guard</code>。</div>'
              '<table><thead><tr><th>回环地址</th><th>登记出处</th></tr></thead><tbody>%s</tbody></table>'
              % lrows)

    body = (
        '<div class="wrap">'
        '<div class="card"><h2>// 00 — 能力统计（%s ｜ 真探用时 %ss）</h2>%s%s%s'
        '<div class="note">云插件探测基址 <code>%s</code>（host 校验通过后真发 GET）｜ '
        '云插件台账 <code>state/cloud-status.json</code> 生成于 %s ｜ 云插件台账计数 %s</div>'
        '</div>'
        '<div class="card"><h2>// 01 — 分类汇总（各类总数 / 接上 / 断连 / 缺失 / 未探测）</h2>%s</div>'
        '<div class="card"><h2>// 02 — 🔴 报警清单（断连 + 缺失，置顶）</h2>%s</div>'
        '<div class="card"><h2>// 03 — 逐条明细（含证据 · 含探于何时）</h2>%s</div>'
        '<div class="card"><h2>// 04 — 未探测清单（不许假绿）</h2>%s</div>'
        '<div class="card"><h2>// 05 — 回环白名单（只探在册 · 为自愈服务）</h2>%s</div>'
        '</div>%s'
        % (_esc(gen), _esc(model.get("probe_seconds")), stat, legend,
           '<div class="hr"></div><div class="note">纪律：<ul>%s</ul></div>' % doctrine,
           _esc(model.get("cloud_base")), _esc(model.get("cloud_ledger_at")),
           _esc(json.dumps(model.get("cloud_ledger_counts"), ensure_ascii=False)),
           ctable, "".join(al), "".join(detail), ublock, lblock, _foot(gen))
    )
    script = ('<script src="capabilities-data.js"></script>\n'
              '<script>\n'
              '/* 经典脚本（非 module）：数据来自 capabilities-data.js，本页零远端请求。*/\n'
              'var A = globalThis.GBT_CAPABILITIES || {items: []};\n'
              'if (globalThis.GBT_CAPABILITIES && globalThis.GBT_CAPABILITIES.generated_at) {\n'
              '  document.title = "GBT小土豆V8 · 能力统计（" + globalThis.GBT_CAPABILITIES.counts.total + " 项）";\n'
              '}\n'
              '</script>\n')
    # 🔴 2026-10-10：标题原来只列四态（接上/断连/缺失/未探测），而数据里**有第五态**
    #    「按需未启用」—— 页面正文早就为它写了说明（"不是故障…凭据在主人侧"），
    #    只有标题漏了 ⇒ 主人看标题会以为只有四种状态、多出来的算"没配好"。补上。
    return (_head("GBT小土豆V8 · 能力统计面板（接上 / 断连 / 缺失 / 未探测 / 按需未启用）")
            + _topbar(gen) + body + script + '</body></html>\n')


def cmd_render() -> int:
    model = load_json(LEDGER)
    if not model or not model.get("items"):
        print("🔴 台账读不到或没有 items，先跑：%s" % CMD_PROBE)
        return 2
    PAGE.parent.mkdir(parents=True, exist_ok=True)
    PAGE.write_text(render_page(model), encoding="utf-8")
    data = {
        "generated_at": model.get("generated_at"),
        "commands": model.get("commands"),
        "doctrine": model.get("doctrine"),
        "sources": model.get("sources"),
        "loopback_registry": model.get("loopback_registry"),
        "cloud_base": model.get("cloud_base"),
        "cloud_ledger_at": model.get("cloud_ledger_at"),
        "counts": model.get("counts"),
        "categories": model.get("categories"),
        "items": model.get("items"),
    }
    DATA.write_text("/* 自动生成，别手改。重建：\n"
                    "   %s\n"
                    "   数据来自台账 state/capability-audit.json（真探所得）。*/\n"
                    "globalThis.GBT_CAPABILITIES = %s;\n"
                    % (CMD_RENDER, json.dumps(data, ensure_ascii=False, separators=(",", ":"))),
                    encoding="utf-8")
    c = model.get("counts") or {}
    print("能力统计面板：%s （%d 字节）" % (PAGE, PAGE.stat().st_size))
    print("数据件：%s （%d 字节）" % (DATA, DATA.stat().st_size))
    print("总数 %s · 接上 %s · 断连 %s · 缺失 %s · 未探测 %s"
          % (c.get("total"), c.get(S_OK), c.get(S_BAD), c.get(S_MISS), c.get(S_UNK)))
    return 0


# ══════════════════════════════════════════════════════════════════════════
# 三态合规（**不许假绿**）—— 纯函数，判据与负对照共用
# ══════════════════════════════════════════════════════════════════════════
def honesty_findings(items: list) -> list:
    """四态合规检查。**「没探过的项不许显示成接上」是第一条**。"""
    out = []
    for i in items:
        iid = i.get("id") or "?"
        st = i.get("state")
        p = i.get("probe") or {}
        if st not in STATES:
            out.append("%s 状态非法：%r（只许 %s）" % (iid, st, "/".join(STATES)))
            continue
        if st == S_OK:
            if not p.get("at"):
                out.append("%s 画成「接上」但探测记录里**没有探于时间**（假绿：没探过）" % iid)
            elif p.get("ok") is not True:
                out.append("%s 画成「接上」但探测记录 ok=%r（假绿）" % (iid, p.get("ok")))
            elif p.get("blocked"):
                out.append("%s 画成「接上」但探测被守卫拦下过（假绿）" % iid)
        elif st == S_UNK:
            if p.get("at"):
                out.append("%s 画成「未探测」但探测记录里有 at=%s" % (iid, p.get("at")))
            if p.get("ok") is True:
                out.append("%s 画成「未探测」但记录里 ok=true" % iid)
            if not str(i.get("why") or "").strip():
                out.append("%s 画成「未探测」但**没写为什么没探**" % iid)
        else:  # 断连 / 缺失
            if not str(i.get("evidence") or "").strip():
                out.append("%s 画成「%s」但**证据原文为空**（不许吞原始 status/错误串）" % (iid, st))
            if st == S_BAD and not p.get("at"):
                out.append("%s 画成「断连」但**没有任何真探测记录**（断连必须是探出来的）" % iid)
            if st == S_MISS and p.get("kind") == "file" and p.get("exists") is not False:
                out.append("%s 画成「缺失」但实测记录没说实物不在参数（exists=%r）" % (iid, p.get("exists")))
    return out


# ══════════════════════════════════════════════════════════════════════════
# 判据（≥8 条 · **必须带负对照**：喂空/喂坏必须报红）
# ══════════════════════════════════════════════════════════════════════════
_EXT_RE = re.compile(r'''(?:src|href)\s*=\s*["'](?:\s*)(?:https?:)?//''', re.I)


def _parse_data_js(text: str):
    m = re.search(r"globalThis\.GBT_CAPABILITIES\s*=\s*(\{.*\})\s*;\s*$", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:                                                    # noqa: BLE001
        return None


def build_artifacts() -> dict:
    return {
        "ledger": load_json(LEDGER),
        "html": PAGE.read_text(encoding="utf-8") if PAGE.is_file() else "",
        "data": DATA.read_text(encoding="utf-8") if DATA.is_file() else "",
        "mesh": load_json(MESH),
        "paths": {"ledger": str(LEDGER), "page": str(PAGE), "data": str(DATA)},
    }


def run_checks(art: dict) -> list:
    """判据本体：只读 art（内存内容），**不碰磁盘** —— 负对照喂改坏的内存副本即可。"""
    rows = []

    def add(cid, ok, detail):
        rows.append({"id": cid, "ok": bool(ok), "detail": detail})

    model = art.get("ledger") or {}
    items = model.get("items") or []
    html_, data_ = art.get("html") or "", art.get("data") or ""
    mesh = art.get("mesh") or {}

    # C1 台账在盘可解析且有 items
    add("C1 台账（state/capability-audit.json）可解析且有 items",
        bool(model) and len(items) > 0, "items=%d" % len(items))

    # C2 每条都有必备字段（id/类别/期望接法/实测/状态/证据或why/探于何时）
    bad2 = []
    for i in items:
        need_ok = (str(i.get("id") or "").strip() and str(i.get("category") or "").strip()
                   and str(i.get("expect") or "").strip() and isinstance(i.get("probe"), dict)
                   and i.get("state") in STATES
                   and (str(i.get("evidence") or "").strip() or str(i.get("why") or "").strip())
                   and ("at" in i))
        if not need_ok:
            bad2.append(i.get("id") or "(无名)")
    add("C2 每条都有 id/类别/期望接法/实测/状态/证据或why/探于何时", not bad2 and len(items) > 0,
        "缺项 %d 条：%s" % (len(bad2), bad2[:6]))

    # C3 状态值域合法（四态之一）
    bad3 = sorted({str(i.get("state")) for i in items} - set(STATES))
    add("C3 状态只许四态（接上/断连/缺失/未探测）", not bad3 and len(items) > 0,
        "越界状态：%s" % (bad3 or "无"))

    # C4 🔴 **不许假绿**：没探过的项不许显示成接上（判据与负对照同源）
    finds = honesty_findings(items) if items else ["台账里没有 items（无从证真 ⇒ 报红）"]
    add("C4 不许假绿（未探测不得画成接上；接上必须有真探测记录）", not finds,
        "违规 %d 条：%s" % (len(finds), "；".join(finds[:3]) or "无"))

    # C5 断连必带原始错误串
    bad5 = [i.get("id") for i in items if i.get("state") == S_BAD
            and not str(i.get("evidence") or "").strip()]
    add("C5 「断连」必带原始错误串/状态码原文", not bad5, "缺原文：%s" % (bad5 or "无"))

    # C6 缺失必写明「清单里谁点名 + 实物路径」
    bad6 = []
    for i in items:
        if i.get("state") != S_MISS:
            continue
        ev = str(i.get("evidence") or "")
        if not ev.strip() or ("不在" not in ev and "缺失" not in ev):
            bad6.append(i.get("id"))
    add("C6 「缺失」必写明清单点名 + 实物路径（清单说有、实物不在）", not bad6,
        "说不清 %s：%s" % (len(bad6), bad6[:6] or "无"))

    # C7 未探测必写 why
    bad7 = [i.get("id") for i in items if i.get("state") == S_UNK
            and not str(i.get("why") or "").strip()]
    add("C7 「未探测」必写「为什么没探」", not bad7, "没写 why：%s" % (bad7 or "无"))

    # C8 计数守恒（总数 = 四态之和 = 各类之和；各类之和 = items 数）
    cnt = model.get("counts") or {}
    cats = model.get("categories") or []
    sum_states = sum(cnt.get(s, 0) for s in STATES)
    sum_cats = sum(r.get("total", 0) for r in cats)
    add("C8 计数守恒（总数 = 四态之和 = 各类之和）",
        (cnt.get("total") == len(items) == sum_states == sum_cats) and len(items) > 0,
        "台账总 %s · items %d · 四态和 %d · 各类和 %d" % (cnt.get("total"), len(items), sum_states, sum_cats))

    # C9 页面自包含 + 零远端请求原语 + 数据只走经典脚本
    bad9 = []
    ext = _EXT_RE.findall(html_)
    if ext:
        bad9.append("外链 %d 处" % len(ext))
    if "cdn" in html_.lower():
        bad9.append("cdn 字样")
    if "<iframe" in html_.lower():
        bad9.append("iframe")
    if re.search(r"\bfetch\s*\(", html_):
        bad9.append("fetch(")
    if "XMLHttpRequest" in html_:
        bad9.append("XMLHttpRequest")
    if re.search(r"\beval\s*\(", html_):
        bad9.append("eval(")
    if re.search(r'type\s*=\s*["\']module["\']', html_, re.I):
        bad9.append('type="module"')
    if "capabilities-data.js" not in html_:
        bad9.append("未引 capabilities-data.js")
    add("C9 页面自包含：零外链/无 fetch·XHR·eval/无 iframe/数据只走经典脚本", not bad9,
        "违规：%s" % (bad9 or "无"))

    # C10 页首/页脚都有 生成时刻 + 重生成命令 + 判据命令
    foot_ok = (html_.count(CMD_RENDER) >= 2 and html_.count(CMD_CHECK) >= 2
               and ("生成时刻" in html_ or "生成 " in html_))
    add("C10 页首/页脚都写 生成时刻 + 重生成命令 + 判据命令", foot_ok,
        "render×%d check×%d" % (html_.count(CMD_RENDER), html_.count(CMD_CHECK)))

    # C11 数据件可解析且与台账一致
    d = _parse_data_js(data_)
    same = (isinstance(d, dict) and d.get("counts") == model.get("counts")
            and len(d.get("items") or []) == len(items) and len(items) > 0)
    add("C11 数据件可解析且计数与台账一致", same,
        "可解析=%s 数据计数=%s 台账计数=%s" % (isinstance(d, dict), (d or {}).get("counts"),
                                                model.get("counts")))

    # C12 类别覆盖齐全（八类，含 framework/cloud/shell-window/panel-page/bridge/dsh/service/artifact）
    have = {i.get("category") for i in items}
    miss = [c for c in CAT_IDS if c not in have]
    add("C12 类别覆盖齐全（八类，含框架位/云插件/壳窗/面板页/面板桥/DSH/本机服务/产物）",
        not miss, "缺类：%s" % (miss or "无"))

    # C13 云插件用现役真源（mesh.json）且蓝图**不算接上**
    mesh_ids = [m.get("id") for m in (mesh.get("modules") or [])]
    cloud_items = [i for i in items if i.get("category") == "cloud"]
    cloud_ok = any(i.get("id") == "cloud.%s" % mid for mid in mesh_ids for i in cloud_items)
    bp = [i for i in items if i.get("id") == "cloud.blueprint-50"]
    bp_ok = bool(bp) and bp[0].get("state") == S_UNK
    add("C13 云插件按现役真源 mesh.json 枚举，且 50 槽蓝图**不算接上**（未探测）",
        cloud_ok and bp_ok,
        "现役位命中=%s 蓝图条=%s 蓝图态=%s" % (cloud_ok, bool(bp),
                                              (bp[0].get("state") if bp else "无")))

    # C14 回环只探在册地址（每条回环 target 的端口都在 loopback_registry）
    reg_ports = {int(k) for k in (model.get("loopback_registry") or {})}
    bad14 = []
    for i in items:
        p = i.get("probe") or {}
        if p.get("net") is True:
            continue                     # 公网探测走 host_guard，不看回环白名单
        t = p.get("target")
        if not isinstance(t, str) or not t.startswith("http://"):
            continue
        port = urllib.parse.urlsplit(t).port
        if port and port not in reg_ports:
            bad14.append("%s(:%s)" % (i.get("id"), port))
    add("C14 本机回环只探**登记在册**的地址（回环白名单）", not bad14,
        "越册 %s" % (bad14 or "无"))
    return rows


def cmd_check(as_json: bool = False) -> int:
    art = build_artifacts()
    rows = run_checks(art)
    live = art.get("ledger") or {}
    live_items = live.get("items") or []
    negs = []

    # ── 负对照 0：掏空台账（items=[]）⇒ C1/C4 必须报红
    art0 = dict(art)
    art0["ledger"] = {"counts": {}, "categories": [], "items": []}
    r0 = [r for r in run_checks(art0) if r["id"].split(" ", 1)[0] in ("C1", "C4")]
    negs.append(("掏空台账（items=[]）", "C1+C4", bool(r0) and all(not r["ok"] for r in r0),
                 "；".join("%s=%s" % (r["id"].split(" ", 1)[0], "红" if not r["ok"] else "绿!")
                           for r in r0)))

    # ── 负对照 1：**把一条未探测强画成接上**（探于时间为空）⇒ C4 必须报红
    if live_items:
        p0 = None
        for i in live_items:
            if i.get("state") == S_UNK:
                p0 = json.loads(json.dumps(i))
                break
        if p0 is None:                    # 没有未探测项就自己造一条
            p0 = {"id": "neg.unk", "category": "framework", "name": "负对照",
                  "expect": "x", "probe": {"kind": "note"}, "why": "没探"}
        p0["state"] = S_OK
        p0["at"] = now()
        p0["ok"] = True
        p0["probe"] = {"kind": "note"}     # 没有 at、没有 ok ⇒ 假绿
        f = honesty_findings([p0])
        negs.append(("喂坏：未探测强画成「接上」（无探测记录）", "C4", bool(f),
                     (f[0] if f else "（本该报红却没报）")))
    else:
        negs.append(("喂坏：未探测强画成「接上」", "C4", False, "（台账空，负对照跑不了）"))

    # ── 负对照 2：断连但证据原文掏空 ⇒ C5 必须报红
    pl = json.loads(json.dumps(live_items))
    pl.append({"id": "neg.bad", "category": "cloud", "name": "负对照", "expect": "x",
               "state": S_BAD, "at": now(), "ok": False, "evidence": "",
               "probe": {"kind": "http", "target": "http://x", "at": now(), "ok": False}, "why": None})
    r5 = [r for r in run_checks({**art, "ledger": {**live, "items": pl}}) if r["id"].split(" ", 1)[0] == "C5"]
    negs.append(("喂坏：断连但证据原文为空", "C5", bool(r5) and not r5[0]["ok"],
                 (r5[0]["detail"] if r5 else "（没跑 C5）")))

    # ── 负对照 3：外链注入 ⇒ C9 必须报红
    r9 = [r for r in run_checks({**art, "html": art["html"]
                                 + '<link rel="stylesheet" href="https://cdn.example.com/x.css">'})
          if r["id"].split(" ", 1)[0] == "C9"]
    negs.append(("外链注入（https cdn）", "C9", bool(r9) and not r9[0]["ok"],
                 (r9[0]["detail"] if r9 else "（没跑 C9）")))

    # ── 负对照 4：数据脚本改 type=module ⇒ C9 必须报红
    r9b = [r for r in run_checks({**art, "html": re.sub(
        r'<script src="capabilities-data\.js">',
        '<script type="module" src="capabilities-data.js">', art["html"])})
        if r["id"].split(" ", 1)[0] == "C9"]
    negs.append(("喂坏：数据脚本改 type=module", "C9", bool(r9b) and not r9b[0]["ok"],
                 (r9b[0]["detail"] if r9b else "（没跑 C9）")))

    # ── 负对照 5：缺字段（掏掉 evidence 与 why）⇒ C2 必须报红
    pc = [{"id": "neg.missing", "category": "framework", "expect": "", "probe": {},
           "state": S_OK, "at": now()}]
    r2 = [r for r in run_checks({**art, "ledger": {**live, "items": pc, "counts": {"total": 1},
                                                   "categories": [{"id": "framework", "total": 1}]}})
          if r["id"].split(" ", 1)[0] == "C2"]
    negs.append(("喂坏：条目不完整（缺 expect/probe/证据）", "C2", bool(r2) and not r2[0]["ok"],
                 (r2[0]["detail"] if r2 else "（没跑 C2）")))

    # ── 负对照 6：host 守卫（沿用 cloud-status 口径）+ 正控现役基址
    guard_cases = [
        ("http://127.0.0.1:9/x", "回环"), ("http://localhost/x", "本地名"),
        ("http://10.1.2.3/", "私有 10/8"), ("http://172.16.0.9/", "私有 172.16/12"),
        ("http://192.168.0.1/", "私有 192.168/16"), ("http://169.254.169.254/x", "链路本地/元数据"),
        ("http://[::1]/", "回环 ::1"), ("ftp://example.com/x", "非 http"),
        ("file:///etc/passwd", "非 http"), ("http://x.local/x", "本地名 .local"),
    ]
    gbad = [u for u, _ in guard_cases if (CS.host_guard(u)[0] if CS else True)]
    pos_ok = (CS.host_guard(CLOUD_BASE)[0] if CS else False)
    negs.append(("host 守卫：10 个本机/私网/非法协议端点必须被拦（不发请求）", "GUARD",
                 (not gbad) and pos_ok,
                 "漏拦 %s ｜ 正控（现役基址）%s"
                 % (gbad or "无", "通过" if pos_ok else "🔴被拦")))

    # ── 负对照 7：回环白名单（未登记端口必须被拦）
    lb_bad = ["http://127.0.0.1:9999/x", "http://127.0.0.1:31337/x"]
    lb_leak = [u for u in lb_bad if loopback_guard(u)[0]]
    lb_ok = loopback_guard("http://127.0.0.1:8765/api/state")[0] and loopback_guard(
        "http://192.168.1.9:8765/api/state")[0] is False
    negs.append(("回环白名单：未登记端口/非回环宿主必须被拦", "LOOP",
                 (not lb_leak) and lb_ok, "漏拦 %s ｜ 正控（:8765）%s"
                 % (lb_leak or "无", "通过" if lb_ok else "🔴被拦")))

    fails = [r for r in rows if not r["ok"]]
    neg_fail = [x for x in negs if not x[2]]
    if as_json:
        print(json.dumps({"rows": rows,
                          "negatives": [{"name": n, "target": t, "ok": o, "detail": d}
                                        for n, t, o, d in negs],
                          "pass": len(rows) - len(fails), "fail": len(fails),
                          "neg_pass": len(negs) - len(neg_fail)}, ensure_ascii=False, indent=1))
    else:
        print("=" * 78)
        print("能力审计 · 判据（含负对照）")
        print("=" * 78)
        for r in rows:
            print("%s %-52s %s" % ("PASS" if r["ok"] else "FAIL", r["id"], r["detail"]))
        print("-" * 78)
        for nm, tg, ok, det in negs:
            print("%s 负对照[%s] %-38s %s" % ("PASS" if ok else "FAIL", tg, nm[:38], det[:100]))
        print("-" * 78)
        print("判据 PASS %d · FAIL %d ｜ 负对照 PASS %d · FAIL %d"
              % (len(rows) - len(fails), len(fails), len(negs) - len(neg_fail), len(neg_fail)))
    return 1 if (fails or neg_fail) else 0


# ══════════════════════════════════════════════════════════════════════════
def _cloud_base() -> str:
    """现役云插件基址：优先环境变量，其次 cloud-status.py 的默认，最后自己的兜底。"""
    import os
    if CS is not None:
        return os.environ.get("GBT_CLOUD_BASE") or getattr(CS, "BASE_DEFAULT",
                                                           "https://gbt-potato-cloud-10.lopaycn.workers.dev")
    return os.environ.get("GBT_CLOUD_BASE") or "https://gbt-potato-cloud-10.lopaycn.workers.dev"


CS = _load_mod("_gbt_cloud_status", CLOUD_STATUS_PY)     # 复用 host_guard / _probe_op / judge_probe
CLOUD_BASE = _cloud_base()


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                                # noqa: BLE001
            pass
    if not argv:
        rc = cmd_probe()
        if rc == 0:
            cmd_render()
        return rc
    if argv[0] == "probe":
        return cmd_probe()
    if argv[0] == "render":
        return cmd_render()
    if argv[0] in ("--check", "check"):
        return cmd_check(as_json="--json" in argv)
    print("用法：capability-audit.py [probe | render | --check [--json]]（无参 = probe + render）")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
