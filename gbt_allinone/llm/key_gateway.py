# gbt-capability: key_gateway
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""统一密钥网关（Key Gateway）· 🥔GBT小土豆V8

════════════════════════════════════════════════════════════════════════
【为什么存在 —— 血账】
旧链路 `cloud_llm._KEY_CHAIN` 在**模块导入时**执行一次：
    找到第一个有 key 的 provider 就 break，把 PROVIDER/API_KEY/BASE_URL/MODEL
    四个模块级全局**定型**，此后整个进程生命周期不再变；
且 `cloud_llm._safe_json` 在 status>=400 时抛 RuntimeError，
被外层 `except Exception` 直接吞成 `{"ok": False}` —— **不重试、不换道**。

⇒ 额度耗尽(402) / 限流(429) / 密钥失效(401) **任一发生 = 硬断连**。
   这就是主人说的「一直失灵」。

【本模块做什么】把「选路」从**导入时一次性**改为**每次调用可重算**，
并把「失败」按**错误分类**处置：能换道的换道，不能换道的（400/422）如实报错，
全不可用时 fail-closed（不瞎挑、不静默降级）。

════════════════════════════════════════════════════════════════════════
【三条硬不变量】（与 energy-router 同律，不变量是机械闸不是口号）
    I1 同一 provider 内**不自动换 key** —— 跨 provider 排队才是合规降级
    I2 **400 / 422 不换道** —— 换道会把「参数写错」伪装成「模型不行」
    I3 **不榨干储备** —— 声明了配额的通道，预留 20% 作备用能源

【密钥来源：唯一真相源，本模块不另开第二条路】
    本模块**不自己解 DPAPI**、不新造取 key 的入口 —— 一律经 `deepseek_key.load_key`
    （判据出处：`tests/test_vision_key_path.py`「不许再有第二条取 key 的路」）。
    本模块只管**声明、排序、健康、记账**，不碰密文、不落明文。

【品牌标志】🥔GBT小土豆V8 —— 出现在五处：
    ① 本模块身份 `BRAND` ② 密钥掩码 `mask()` ③ 铸造前缀 `gbtv8-`
    ④ 审计账本每行 `brand` 字段 ⑤ 统一密钥库表名
    （注：DPAPI 熵值 `GBTxiaotudouV8:<name>:v1` 里品牌**早已内嵌**，
      那是密码学层的固化 —— 本模块只是把它**显示**出来。）
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path

# ── 品牌 ────────────────────────────────────────────────────────────────
BRAND = "GBT小土豆V8"
BRAND_TAG = "🥔GBT小土豆V8"
MINT_PREFIX = "gbtv8-"          # 铸造出来的统一密钥前缀（带品牌）
CAP = "key_gateway"

_RUNTIME_TTL_S = 0.0            # 0 = 每次都重算（旧链路的病根就是"算一次存一辈子"）
DEFAULT_COOLDOWN_S = 120        # 限流冷却
RESERVE_RATIO = 0.20            # I3：预留 20% 不榨干
_GLOBAL_ACTIVE = "__active__"   # 运行态里的「当前落点」—— 全局一条，切换判定靠它
_GLOBAL_SWITCHES = "__switches__"   # 累计切换次数（跨通道）

# ── 错误分类表 ──────────────────────────────────────────────────────────
#   字段序：(同家重试, 该换道, 记耗尽, 记失效, 重试耗尽后继续下一家)
#
#   ⚠️⚠️ 血账：原先是四字段，`transient` 写成 (True, False, False, False) ——
#     「可重试但不可换道」。实弹一跑才看清：**编排层在 `not failover` 处立即 return**，
#     于是重试分支成了**死代码** ⇒ 一次网络抖动 = 硬失败 ⇒ 等于把「断连」又请回来。
#     根因是**决策维度没拆开**：「同家再试一次」与「换一家试试」是两件事。
#     拆成五字段后语义清楚：能同家试的先试，试不动就往下走，只有
#     `bad_request/unknown` 才是**硬停**（因为我们自己错了，换谁都没用）。
#     最终若全链路失败，返回值带完整 `tried` 轨迹 —— **不静默降级**。
ERR_TABLE = {
    "ok":              (False, False, False, False, False),
    "rate_limited":    (False, True,  False, False, True),    # 429      → 冷却换道
    "quota_exhausted": (False, True,  True,  False, True),    # 402/余额 → 标耗尽换道
    "key_invalid":     (False, True,  False, True,  True),    # 401/403  → 禁用该条换道
    "not_found":       (False, True,  False, False, True),    # 404      → 该家没这模型
    "upstream_error":  (True,  False, False, False, True),    # 5xx      → 同家重试再换
    "transient":       (True,  False, False, False, True),    # 超时/连接 → 同家重试再换
    "bad_request":     (False, False, False, False, False),   # 400/422  → **硬停**（I2）
    "unknown":         (False, False, False, False, False),   # 分类不明 → 硬停，不拿换道掩盖
}

# 文本兜底判据（状态码缺失时用；**顺序即优先级**，先判额度再判限流）
# ⚠️ 血账：`bad_request` 这一条是**实弹逼出来的**（2026-09-27）——
#    把 `temperature` 传成字符串，agnes 回的是 **HTTP 500** 而正文写着
#    `code: invalid_request`。上游把「请求本身有错」报成 5xx ⇒ 只看状态码会
#    误判成 upstream_error（可重试）⇒ 白重试三次、还差点换道把参数缺陷
#    伪装成「模型不行」。所以必须认正文里的 invalid_request。
_TEXT_HINTS = (
    ("quota_exhausted", ("insufficient", "quota", "balance", "credit", "额度",
                         "余额不足", "已用尽", "欠费", "billing", "钱包", "充值")),
    ("rate_limited",    ("rate limit", "too many requests", "限流", "请求过于频繁",
                         "rpm", "tpm limit")),
    ("key_invalid",     ("invalid api key", "invalid_api_key", "unauthorized",
                         "authentication", "api key not valid", "密钥无效", "鉴权失败")),
    ("bad_request",     ("invalid_request", "invalid request", "invalid value",
                         "cannot unmarshal", "missing required", "validation error",
                         "field validation", "参数错误")),
    # ⚠️ 血账（2026-09-28 实弹）：`not_found` 必须认「**该通道不服务这个模型**」这类正文。
    #    实测 `api.teamorouter.com` 对过期模型名回的是 **HTTP 400**：
    #        {"error":{"message":"模型 'gpt-4o-mini' 暂不支持调用，请改用 GET /v1/models …"}}
    #    400 落进 unset 分支 ⇒ 归 `bad_request` ⇒ 按 I2 **硬停** ⇒
    #    **一条声明过期模型名（或被重新路由过）的通道，会把整单打死**，
    #    哪怕 agnes / deepseek 都健康。而它的语义明明是 `not_found`（这家的模型表里没有）
    #    ⇒ 换道就对了。
    #    ⚠️ 措辞必须**窄**：绝不加泛化的 "not supported" ——
    #    「temperature not supported」这类**真参数缺陷**若被拐进 not_found，
    #    就会换道掩盖掉自己的 bug，正好打穿 I2。
    ("not_found",       ("model_not_found", "not found", "no available channel",
                         "does not exist", "no such model",
                         "暂不支持调用", "不支持调用", "模型不支持",
                         "unsupported model", "model_not_supported")),
    ("upstream_error",  ("internal server error", "bad gateway", "service unavailable",
                         "upstream", "overloaded")),
    ("transient",       ("timed out", "timeout", "connection", "temporarily unavailable")),
)

_STATUS_MAP = {
    400: "bad_request", 422: "bad_request",
    401: "key_invalid", 403: "key_invalid",
    402: "quota_exhausted",
    404: "not_found",
    408: "transient",
    429: "rate_limited",
    500: "upstream_error", 502: "upstream_error", 503: "upstream_error",
    504: "upstream_error", 529: "upstream_error",
}


# ══════════════════════════════════════════════════════════════════════
#  PROVIDERS —— 声明层（**顺序即默认优先级**）
#  ⚠️ agnes 必须第一：`cloud_llm._KEY_CHAIN[0]` 被 tests/test_framework.py
#     第 264-266 行**钉死**（Owner 2026-09-19 契约）。本表与之**同源同序**，
#     不另立一套优先级 —— 声明只有一处真相。
#  字段：vault=deepseek_key 的 profile 名（""=无保险箱，只认 env）
#        envs =环境变量候选（按序，第一个非空即命中）
#        url  =base_url    model=默认模型    wire=协议族    tier=档次（排序权重用）
# ══════════════════════════════════════════════════════════════════════
def _served_artifact() -> str:
    """现役权重目录（唯一指针 `state/weights/ACTIVE.json`）。读不到就空串并**记下原因**，绝不编默认值。"""
    global _SERVED_ERR
    try:
        p = Path(__file__).resolve().parents[2] / "state" / "weights" / "ACTIVE.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        v = str(d.get("active_artifact") or "").strip()
        _SERVED_ERR = "" if v else "ACTIVE.json 里没有 active_artifact"
        return v
    except Exception as exc:                            # noqa: BLE001
        _SERVED_ERR = "%s: %s" % (type(exc).__name__, str(exc)[:120])
        return ""


def _potato_model() -> str:
    """原生车道的模型名：**由地址决定**，不让人在同一条链上填两份。

    · 走**云端插件**（`*.workers.dev`）⇒ 用别名 `gbt-potato-v8`：
      插件按自己的 `LLM_MODEL` 改写成现役 served id（那是它的职责，见 deploy/cloud-10）。
    · **直连 RunPod**（`api.runpod.ai`）⇒ 必须用现役 served id：vLLM 只认它，
      拿别名去打是 HTTP 502（2026-10-21 实测）。
    · 其它地址（本机 8111 / 自建路由）⇒ 尊重 `GBT_POTATO_MODEL`。
    """
    env_model = os.environ.get("GBT_POTATO_MODEL", "").strip()
    base = os.environ.get("GBT_POTATO_BASE_URL", "").strip().lower()
    if "workers.dev" in base:
        return env_model or "gbt-potato-v8"
    served = _served_artifact()
    if served:
        return served
    return env_model or "gbt-potato-v8"


PROVIDERS = [
    # ── 主路（Owner 指定契约，顺序不许动）───────────────────────────
    # 🔴 2026-10-04 优化：agnes-2.5 是**思考型** —— 实测 max_tokens=512 时 token 全烧在
    #    reasoning_content 上、content 返回空（"ok 但空答"）。给下限 1024（调用方给更小值时抬到它），
    #    与 nvidia 两条深推理道同款口径（那两条是 512）。
    dict(name="agnes",     vault="agnes",    envs=["AGNES_API_KEY"],
         url="https://apihub.agnes-ai.com/v1", model="agnes-2.5-flash",
         wire="openai", tier="primary", quota_tokens=0, weight=1.00,
         min_max_tokens=1024),
    dict(name="deepseek",  vault="deepseek", envs=["DEEPSEEK_API_KEY"],
         url="https://api.deepseek.com/v1", model="deepseek-flash",
         wire="openai", tier="primary", quota_tokens=0, weight=0.95),
    # ── 深度推理备用（NVIDIA NIM · OpenAI 兼容 · 2026-09-27 实弹确认可达）
    #    实测读数：glm-5.3 冷启动 >240s；glm-5.3-flash 65s 可回。
    #    ⚠️ 推理模型坑：max_tokens 太小会被 reasoning 吃光 ⇒ content 空但 HTTP 200。
    #    故 tier=deep（只当备用，不抢主路），且由调用方保证 max_tokens>=512。
    dict(name="nvidia-glm", vault="", envs=["NVIDIA_API_KEY"],
         url="https://integrate.api.nvidia.com/v1", model="z-ai/glm-5.3",
         wire="openai", tier="deep", quota_tokens=0, weight=0.45,
         min_max_tokens=512),
    dict(name="nvidia-flash", vault="", envs=["NVIDIA_API_KEY"],
         url="https://integrate.api.nvidia.com/v1", model="z-ai/glm-5.3-flash",
         wire="openai", tier="deep", quota_tokens=0, weight=0.50,
         min_max_tokens=512),
    # ── 标准备用 ────────────────────────────────────────────────────
    # ⚠️ kimi 与 moonshot **本来就是一家**：`cloud_llm._KEY_CHAIN` 的声明是
    #    `("kimi", ["MOONSHOT_API_KEY","KIMI_API_KEY"], …)` —— 一个 provider、两个 env 名。
    #    我早先拆成两家，实弹立刻报出「同一把钥匙挂两名下」（指纹一致）：
    #    一家被限流，另一家**必然同样被限** ⇒ 换道白跳一次。
    #    现在合并回一家（声明只有一处真相），`vaults` 支持多保险箱依次取。
    dict(name="kimi",      vaults=["kimi", "moonshot"],
         envs=["KIMI_API_KEY", "MOONSHOT_API_KEY"],
         url="https://api.moonshot.cn/v1", model="kimi-k2-0905-preview",
         wire="openai", tier="standard", quota_tokens=0, weight=0.70),
    # ⚠️ 实测记录（2026-09-28）：本机 `OPENAI_BASE_URL` 实为**路由器**
    #    `https://api.teamorouter.com/v1`（44 个模型，owned_by 横跨 anthropic /
    #    deepseek / google / openai / xai / moonshot…），**不服务 `gpt-4o-mini`** ——
    #    对它的回应是 400 `模型 'gpt-4o-mini' 暂不支持调用`。
    #    ⇒ 声明里的模型名对这个地址已过期。**故意不改名**，理由两条：
    #      ① `cloud_llm._KEY_CHAIN` 的同名项被既有测试钉着，改它有回归面；
    #      ② 更根本的是**这个账号当前 0 余额** —— 实测 `gpt-5.4-mini` /
    #         `glm-5.3-flash-free` / `deepseek-flash-free` 一律回
    #         「钱包余额不足，需先充值后调用」。**改名不会让它能用**，
    #         只会把「模型名错」换成「余额不足」。
    #    ⇒ 正确的机械处置已由 `_TEXT_HINTS` 承担：
    #         过期模型名 → `not_found` → 换道；
    #         余额不足   → `quota_exhausted` → 标记耗尽 + 换道。
    #      两条都不会再把整单打死。**充上余额后本通道会自己活过来，无需改代码。**
    dict(name="openai",    vault="openai",   envs=["OPENAI_API_KEY"],
         url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
         model="gpt-4o-mini", wire="openai", tier="standard",
         quota_tokens=0, weight=0.60),
    dict(name="freellmapi", vault="freellmapi", envs=["FREELLMAPI_API_KEY"],
         url="", model="", wire="openai", tier="standard",
         quota_tokens=0, weight=0.55, url_from="freellmapi"),
    dict(name="custom",    vault="custom", envs=["GBT_LLM_API_KEY"],
         url=os.environ.get("GBT_LLM_BASE_URL", ""),
         model=os.environ.get("GBT_LLM_MODEL", ""),
         wire="openai", tier="standard", quota_tokens=0, weight=0.58),
    dict(name="anthropic", vault="", envs=["ANTHROPIC_API_KEY"],
         url="https://api.anthropic.com", model="claude-sonnet-4-20250514",
         wire="anthropic", tier="standard", quota_tokens=0, weight=0.62),
    dict(name="gemini",    vault="", envs=["GEMINI_API_KEY"],
         url="https://generativelanguage.googleapis.com/v1beta",
         model="gemini-2.0-flash", wire="gemini", tier="standard",
         quota_tokens=0, weight=0.62),
    # ── 统一模型路由（CLIProxyAPI · 主人令 2026-10-04「做双向绑定，不逐条填钥」）──────
    # 一条 base-url 用全部车道（自家模型 / 本机免费池 / 各 CLI 账户，见 deploy/cliproxy/README.md）。
    # 钥匙 = **统一密钥**：key_gateway 铸一把，路由器 access.api-keys（我们→路由器）与云端 GW_AUTH
    # （路由器→云端）用**同一个值**（明文只落应用数据区，库里只存摘要）⇒ 双向绑定、不逐条填。
    # ⚠️ 与 `cloud_llm._KEY_CHAIN` 的同名项**两处都要有**（那两张表是两处口径，历史遗留；本表带 tier/权重）。
    # ── 本机模型车道（组1 · 本机 Ollama，权重在本地）──────
    dict(name="gbt-local", vault="", envs=["GBT_LOCAL_LLM_API_KEY"],
         url=os.environ.get("GBT_LOCAL_LLM_BASE_URL", "http://127.0.0.1:11434/v1"),
         model=os.environ.get("GBT_LOCAL_LLM_MODEL", "qwen3:latest"),
         wire="openai", tier="standard", quota_tokens=0, weight=0.55),
    dict(name="cliproxy", vault="", envs=["GBT_CLIPROXY_KEY"],
         url=os.environ.get("GBT_CLIPROXY_BASE_URL", "http://127.0.0.1:8317/v1"),
         model=os.environ.get("GBT_CLIPROXY_MODEL", "gbt-potato-v8"),
         wire="openai", tier="standard", quota_tokens=0, weight=0.60),
    # ── 本地兜底（本机原生端点；tier=local 权重最低，不抢云端主路）──────
    # 🔴 2026-10-11（实测教训）：她走的是 **Serverless（闲时缩到 0）** ⇒ 冷启动/排队会超过
    #    框架默认 60s；一超时就被记失败 ⇒ `plan` 自动换道到 agnes，于是**托管模型顶着她的
    #    提示词替她说话**（实测：问"请自我介绍"答"我是 Agnes-2.5-Flash"）——这犯「不许拿托管
    #    模型冒充」的规矩。⇒ 给她一条**长超时**兜住冷启动（点名时更不许静默换道，见 cloud_llm）。
    # 🔴 2026-10-21 修（实测：原生车道 502 的真因 = **模型名写死成旧别名**）：
    #    直连 RunPod 时 vLLM 只认现役 served id（`/runpod-volume/gbt-v8-v83`），
    #    拿 `gbt-potato-v8` 去打 ⇒ HTTP 502（实测 2.6s）；换 served id ⇒ 200 / 0.9s。
    #    ⇒ 模型名**按地址决定**，并直连时从 `state/weights/ACTIVE.json` 现读（换版权重自动跟）。
    dict(name="potato",    vault="potato", envs=["GBT_POTATO_API_KEY"],
         url=os.environ.get("GBT_POTATO_BASE_URL", "http://127.0.0.1:8111/v1"),
         model=_potato_model(),
         wire="openai", tier="local", quota_tokens=0, weight=0.20, timeout_s=300, retries=6,
         # 🔴 2026-10-21 甲（Owner 拍板：「自动循环用免费池，端点只留给『她要本人回答』时用」）：
         #    这条 = **付费 + 冷启动 ~300 秒**的自家端点（按 worker 运行秒计费，实测 ~$0.69/时）。
         #    ⇒ 标 `owner_only`：**默认不进自动选路**，只有「点名」才走
         #      （`plan(prefer="potato")` / `GBT_LLM_PROVIDER=potato` / params.provider="potato"）。
         #    为什么必须这样：它曾是自动兜底 ⇒ 每一次 LLM 调用都把它叫醒一次，每次 ~$0.07 且要等 5 分钟。
         owner_only=True),
]
_BY_NAME = {p["name"]: p for p in PROVIDERS}
_ORDER = [p["name"] for p in PROVIDERS]


# ══════════════════════════════════════════════════════════════════════
#  存储位置（运行态与配置分离 —— 这样「自检只读」才成立）
# ══════════════════════════════════════════════════════════════════════
def _store_dir() -> Path:
    from gbt_allinone._paths import STORE_DIR
    d = Path(STORE_DIR) / "key_gateway"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _runtime_file() -> Path:
    return _store_dir() / "runtime.json"


def _ledger_file() -> Path:
    return _store_dir() / "ledger.jsonl"


def _vault_file() -> Path:
    return _store_dir() / "unified_keys.db"


# ══════════════════════════════════════════════════════════════════════
#  运行态（用量 / 冷却 / 禁用 / 耗尽 / 上次选中）
# ══════════════════════════════════════════════════════════════════════
def _rload() -> dict:
    f = _runtime_file()
    if not f.is_file():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8")) or {}
    except Exception:                                   # noqa: BLE001
        return {}                                       # 运行态坏了不许拖垮调用


def _rsave(rt: dict) -> None:
    f = _runtime_file()
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(rt, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(f)


def _slot(rt: dict, name: str) -> dict:
    st = rt.setdefault(name, {})
    for k, dflt in (("used", {}), ("cooldown", {}), ("disabled", []),
                    ("exhausted", []), ("active", ""), ("switches", 0),
                    ("calls", 0), ("fails", 0)):
        st.setdefault(k, dflt)
    return st


def _audit(row: dict) -> None:
    """追加一行账本（**只记元数据，绝不记密钥正文**）。"""
    try:
        row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "brand": BRAND, **row}
        with _ledger_file().open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:                                   # noqa: BLE001
        pass                                            # 记账失败不许反向打断调用


# ══════════════════════════════════════════════════════════════════════
#  密钥读取 —— **唯一真相源**：deepseek_key（不另开第二条路）
# ══════════════════════════════════════════════════════════════════════
def _vault_key(profile: str) -> tuple:
    """经 deepseek_key 取 (key, source)。source ∈ env:… / dpapi / missing / unreadable。"""
    if not profile:
        return "", "n/a"
    try:
        from gbt_allinone import deepseek_key as _dk
        return _dk.load_key(profile)
    except Exception as exc:                            # noqa: BLE001
        return "", "error:" + str(exc)[:40]


def _env_key(envs) -> tuple:
    for e in (envs or []):
        v = os.environ.get(e, "").strip()
        if v:
            return v, "env:" + e
    return "", "missing"


def _vaults_of(p: dict) -> list:
    """该 provider 可用的保险箱 profile 列表（`vault` 单个 / `vaults` 多个都认）。"""
    v = p.get("vaults")
    if isinstance(v, list):
        return [str(x) for x in v if str(x or "").strip()]
    one = str(p.get("vault") or "").strip()
    return [one] if one else []


def key_for(name: str) -> tuple:
    """取某 provider 的 (key, source)。保险箱优先走 deepseek_key，无 vault 才认 env。

    ⚠️ 顺序是刻意的：**有保险箱就只走保险箱那条路**（env 由 deepseek_key.load_key
    内部先查，那是同一条路，不构成「第二条取 key 的路」）。
    """
    p = _BY_NAME.get(name)
    if not p:
        return "", "unknown-provider"
    for v in _vaults_of(p):
        k, src = _vault_key(v)
        if k:
            return k, src
    if _vaults_of(p):
        # 保险箱都没货 → 才退回该 provider 自己声明的 env（仍同一口子）
        return _env_key(p.get("envs"))
    return _env_key(p.get("envs"))


def _present(name: str) -> tuple:
    """(是否在位, source)。只判在不在，**不解密**时也安全。"""
    p = _BY_NAME.get(name)
    if not p:
        return False, "unknown-provider"
    try:
        from gbt_allinone import deepseek_key as _dk
        for v in _vaults_of(p):
            spec = _dk._PROFILES.get(v)
            if not spec:
                continue
            env_hit = os.environ.get(spec["env"], "").strip()
            if not env_hit and spec.get("proxy"):
                env_hit = os.environ.get(spec["proxy"], "").strip()
            if env_hit:
                return True, "env:" + spec["env"]
            try:
                if Path(_dk._secret_file(v)).is_file():
                    return True, "dpapi:" + v
            except Exception:                            # noqa: BLE001
                pass
    except Exception:                                    # noqa: BLE001
        pass
    k, src = _env_key(p.get("envs"))
    return bool(k), src


def _url_of(p: dict) -> str:
    if p.get("url_from") == "freellmapi":
        try:
            from . import freellmapi as _fl
            return _fl.base_url().rstrip("/") + "/v1"
        except Exception:                                # noqa: BLE001
            return ""
    return str(p.get("url") or "")


# ══════════════════════════════════════════════════════════════════════
#  掩码与品牌
# ══════════════════════════════════════════════════════════════════════
def fingerprint(key: str) -> str:
    """BLAKE2b 前 8 位十六进制 —— 用来**比对是不是同一把钥匙**，且不可反推。"""
    if not key:
        return ""
    return hashlib.blake2b(key.encode("utf-8"), digest_size=4).hexdigest()


def mask(key: str, provider: str = "") -> str:
    """带品牌标志的掩码。**永不含明文**，也不可能从掩码还原。

    形态：🥔GBT小土豆V8|agnes|sk-a…9f2c|#4b1e77a0
    """
    if not key:
        return ""
    head = key[:4]
    tail = key[-4:] if len(key) > 8 else ""
    return "%s|%s|%s…%s|#%s" % (BRAND_TAG, provider or "?", head, tail, fingerprint(key))


# ══════════════════════════════════════════════════════════════════════
#  错误分类（机械闸）
# ══════════════════════════════════════════════════════════════════════
def classify(status=None, error: str = "") -> str:
    """把「失败」归类。分类决定换不换道 —— 不由调用方心情决定。"""
    if status:
        cls = _STATUS_MAP.get(int(status))
        if cls:
            # 402/429 已经明确；其余先看文本有没有更精确的提示
            if cls in ("bad_request", "not_found", "upstream_error"):
                for name, hints in _TEXT_HINTS:
                    if any(h in str(error).lower() for h in hints):
                        return name
            return cls
    low = str(error or "").lower()
    if not low:
        return "unknown"
    for name, hints in _TEXT_HINTS:
        if any(h in low for h in hints):
            return name
    return "unknown"


def decide(err_class: str) -> dict:
    """分类 → 处置。返回 {retry_same, failover, exhaust, disable, escalate, action}。

    * `retry_same`  同一条通道再试一次（网络抖动/上游 5xx）
    * `failover`    判定为**通道级**故障 ⇒ 该换下一家（也用于对外语义）
    * `escalate`    同家重试耗尽后**继续往下走**（否则一次抖动=硬断连）
    * `bad_request/unknown` 三项全 False ⇒ **硬停**：我们自己错了，换谁都没用
    """
    row = ERR_TABLE.get(err_class) or ERR_TABLE["unknown"]
    retry, failover, exhaust, disable, escalate = row
    action = {
        "ok": "通过",
        "rate_limited": "冷却 %ds 后换到下一条有能源的通道" % DEFAULT_COOLDOWN_S,
        "quota_exhausted": "标记额度耗尽并换道（**自动补给**）",
        "key_invalid": "禁用该条并换道（曾报 401/403）",
        "not_found": "该通道没有这个模型 → 换道",
        "upstream_error": "上游 5xx → 同通道重试，耗尽后换道（不硬断连）",
        "transient": "网络瞬时故障 → 同通道重试，耗尽后换道（不硬断连）",
        "bad_request": "**硬停**：400/422 是请求本身有错，换道会把参数缺陷伪装成『模型不行』",
        "unknown": "**硬停**：分类不明时宁可如实报错，不拿换道掩盖",
    }.get(err_class, "未知分类")
    return {"retry_same": retry, "failover": failover,
            "exhaust": exhaust, "disable": disable, "escalate": escalate,
            "action": action}


# ══════════════════════════════════════════════════════════════════════
#  候选枚举 + 健康排序
# ══════════════════════════════════════════════════════════════════════
def candidates(slot_names=None, include_empty: bool = True, allow_self: bool = False) -> list:
    """枚举候选。只在位 / 不在位都返回；`alive` 由健康态再判。

    `allow_self=False`（默认）⇒ `owner_only` 车道（自家付费端点）**不参与自动选路**。
    """
    names = slot_names or _ORDER
    out = []
    for i, n in enumerate(names):
        p = _BY_NAME.get(n)
        if not p:
            continue
        pres, src = _present(n)
        out.append({"provider": n, "index": _ORDER.index(n) if n in _ORDER else i,
                    "present": pres, "source": src,
                    "url": _url_of(p), "model": p.get("model", ""),
                    "wire": p.get("wire", "openai"), "tier": p.get("tier", "standard"),
                    "weight": float(p.get("weight", 0.5)),
                    "owner_only": bool(p.get("owner_only")),
                    "quota_tokens": int(p.get("quota_tokens", 0) or 0),
                    "min_max_tokens": int(p.get("min_max_tokens", 0) or 0)})
    if not include_empty:
        out = [c for c in out if c["present"]]
    return out


def rank(slot_names=None, allow_self: bool = False) -> list:
    """健康排序：在位 → 未禁用 → 未冷却 → 未耗尽，再按「余量比 × 权重 × 序位」。

    返回元素多两个字段：`alive`（能不能用）与 `why`（不能用的原因）。
    **本函数不改任何状态**（自检只读的判据就靠这条）。
    `allow_self=False` ⇒ `owner_only`（自家付费冷启动端点）判成不可用，
        why 写明「仅限点名」；读总览（energy）时传 True，让它照样看得见。
    """
    rt = _rload()
    now = time.time()
    out = []
    for c in candidates(slot_names, allow_self=allow_self):
        n = c["provider"]
        st = (rt.get(n) or {})
        used = int((st.get("used") or {}).get(n, 0) or 0)
        cd = float((st.get("cooldown") or {}).get(n, 0) or 0)
        dis = set(st.get("disabled") or [])
        exh = set(st.get("exhausted") or [])
        quota = c["quota_tokens"]
        headroom = max(0, quota - used) if quota else None
        reserve = int(quota * RESERVE_RATIO) if quota else 0

        why, alive = "", True
        if c["owner_only"] and not allow_self:
            why, alive = ("仅限点名（付费冷启动 ~300s；主人令 2026-10-21「没使用绝不能消耗」）",
                          False)
        elif not c["present"]:
            why, alive = "密钥不在位（%s）" % c["source"], False
        elif not c["url"]:
            why, alive = "未声明 base_url", False
        elif n in dis:
            why, alive = "已禁用（曾报 401/403）", False
        elif n in exh:
            why, alive = "额度已耗尽（显式标记）", False
        elif cd > now:
            why, alive = "冷却中 %ds" % int(cd - now), False
        elif quota and used >= quota:
            why, alive = "额度已耗尽（%d/%d）" % (used, quota), False

        ratio = (headroom / quota) if (quota and headroom is not None) else 1.0
        prio = 1.0 / (1.0 + c["index"] * 0.25)          # 声明序位即优先级
        out.append({**c, "used": used, "quota": quota, "headroom": headroom,
                    "reserve": reserve,
                    "in_reserve": bool(quota and headroom is not None and headroom <= reserve),
                    "score": ratio * c["weight"] * prio,
                    "alive": alive, "why": why})

    alive_rows = [x for x in out if x["alive"]]
    first = [x for x in alive_rows if not x["in_reserve"]]   # I3：先不碰储备
    pool = first if first else alive_rows
    pool.sort(key=lambda x: x["score"], reverse=True)
    seen = {id(x) for x in pool}
    return pool + [x for x in out if id(x) not in seen]


# ══════════════════════════════════════════════════════════════════════
#  plan —— 给调用方的「本次该按什么顺序试」
# ══════════════════════════════════════════════════════════════════════
def plan(need_tokens: int = 0, prefer: str = "", slot_names=None,
         allow_self: bool = False) -> dict:
    """返回本次调用的**试路顺序**（不含密钥正文）。每次调用现算 —— 这是治病的那一刀。

    `persist=True` 语义已内建：把「上次选中」记进运行态（与配置分离，故自检仍只读）。

    🔴 2026-10-21 甲（Owner 拍板）：`owner_only` 车道（自家付费端点 potato）
       **默认不进自动选路**；只有**点名**（`prefer="potato"`）才放进来 ——
       点名 = 主人要「她本人回答」，那时才允许叫醒付费端点（冷启动 ~300s / ~$0.07 一次）。
    """
    rt = _rload()
    pf = str(prefer or "").strip().lower()
    if pf and (_BY_NAME.get(pf) or {}).get("owner_only"):
        allow_self = True
    rows = rank(slot_names, allow_self=allow_self)
    if prefer:
        if pf not in _BY_NAME:
            return {"ok": False, "fail_closed": True,
                    "error": "未知 provider %r（可用：%s）" % (prefer, _ORDER)}
        pinned = [x for x in rows if x["provider"] == pf]
        rows = pinned + [x for x in rows if x["provider"] != pf]

    usable = [x for x in rows if x["alive"]]
    if need_tokens:
        usable = [x for x in usable
                  if not x["quota"] or (x["headroom"] or 0) >= need_tokens] or usable

    if not usable:
        return {"ok": False, "fail_closed": True, "brand": BRAND_TAG,
                "error": "所有通道都不可用（密钥缺失/禁用/冷却/耗尽）",
                "candidates": [{"provider": x["provider"], "why": x["why"]} for x in rows],
                "how_to_fix": "补密钥（deepseek_key set --profile <名>）/ 等冷却到期 "
                              "/ op=reset 清运行态 / op=switch 手动指定"}

    chosen = usable[0]
    # ⚠️ 血账：早先把「当前落点」记在 `rt[<provider>]["active"]` 里 —— 那等于
    #    「每家各自记自己」，**永远比不出切换**（实测 429 换道确实发生了，
    #    但 auto_switched 恒为 False，因为新家的格子里根本没有上一次的落点）。
    #    落点必须是**全局一条**。每个 provider 自己的 `active` 只保留作
    #    「这家被选中过」的标记（`_service_names` 在用）。
    prev = str(rt.get(_GLOBAL_ACTIVE) or "")
    st = _slot(rt, chosen["provider"])
    st["active"] = chosen["provider"]
    rt[_GLOBAL_ACTIVE] = chosen["provider"]
    if prev and prev != chosen["provider"]:
        st["switches"] = int(st.get("switches", 0) or 0) + 1
        rt[_GLOBAL_SWITCHES] = int(rt.get(_GLOBAL_SWITCHES, 0) or 0) + 1
    _rsave(rt)

    key, src = key_for(chosen["provider"])
    _audit({"event": "plan", "provider": chosen["provider"], "source": src,
            "fp": fingerprint(key), "candidates": len(usable),
            "switched_from": prev or None})
    return {"ok": True, "brand": BRAND_TAG, "chosen": chosen["provider"],
            "wire": chosen["wire"], "url": chosen["url"], "model": chosen["model"],
            "min_max_tokens": chosen["min_max_tokens"],
            "masked": mask(key, chosen["provider"]), "fp": fingerprint(key),
            "source": src, "auto_switched": bool(prev and prev != chosen["provider"]),
            "switched_from": prev or None,
            "order": [{"provider": x["provider"], "score": round(x["score"], 4),
                       "masked": "", "alive": x["alive"], "why": x["why"]}
                      for x in rows],
            "skipped": [{"provider": x["provider"], "why": x["why"]}
                        for x in rows if not x["alive"]]}


def materialize(name: str) -> dict:
    """把某个 provider 的**明文密钥**取出来，仅限进程内直用（绝不入返回值之外的地方）。"""
    p = _BY_NAME.get(name)
    if not p:
        return {"ok": False, "error": "未知 provider %r" % name}
    key, src = key_for(name)
    if not key:
        return {"ok": False, "error": "该通道密钥不在位", "source": src}
    return {"ok": True, "provider": name, "key": key, "source": src,
            "url": _url_of(p), "model": p.get("model", ""),
            "wire": p.get("wire", "openai"), "masked": mask(key, name),
            "min_max_tokens": int(p.get("min_max_tokens", 0) or 0)}


# ══════════════════════════════════════════════════════════════════════
#  note_result —— 记账 + 按分类处置（这是「自动补给」的执行点）
# ══════════════════════════════════════════════════════════════════════
def note_result(provider: str, ok: bool = True, status=None, error: str = "",
                tokens: int = 0, cooldown_s: int = 0) -> dict:
    """记一次调用结果，并按错误分类决定后续处置。**这是自动切换的落点。**"""
    if provider not in _BY_NAME:
        return {"ok": False, "error": "未知 provider %r" % provider}
    rt = _rload()
    st = _slot(rt, provider)
    st["calls"] = int(st.get("calls", 0) or 0) + 1
    if tokens:
        st["used"][provider] = int(st["used"].get(provider, 0) or 0) + int(tokens)

    if ok:
        st["fails"] = 0
        st["cooldown"].pop(provider, None)
        _rsave(rt)
        _audit({"event": "call_ok", "provider": provider, "tokens": int(tokens or 0)})
        return {"ok": True, "err_class": "ok", "failover": False,
                "action": "通过", "cooldown_s": 0}

    cls = classify(status=status, error=error)
    d = decide(cls)
    st["fails"] = int(st.get("fails", 0) or 0) + 1

    cd = int(cooldown_s or DEFAULT_COOLDOWN_S)
    if cls == "rate_limited":
        st["cooldown"][provider] = time.time() + cd
    elif cls == "quota_exhausted" or d["exhaust"]:
        if provider not in st["exhausted"]:
            st["exhausted"].append(provider)
    elif cls == "key_invalid" or d["disable"]:
        if provider not in st["disabled"]:
            st["disabled"].append(provider)
    elif cls in ("upstream_error", "transient"):
        st["cooldown"][provider] = time.time() + min(cd, 30)   # 同家短暂退避
    _rsave(rt)
    _audit({"event": "call_fail", "provider": provider, "err_class": cls,
            "status": status, "failover": d["failover"],
            "err": str(error or "")[:200]})
    return {"ok": False, "brand": BRAND_TAG, "provider": provider,
            "err_class": cls, "status": status, **d,
            "cooldown_s": cd, "fails": st["fails"]}


def reset(provider: str = "") -> dict:
    """清运行态（冷却/禁用/耗尽/用量）。**只清运行态，不碰密钥。**"""
    rt = _rload()
    if provider:
        if provider not in _BY_NAME:
            return {"ok": False, "fail_closed": True,
                    "error": "未知 provider %r" % provider}
        rt.pop(provider, None)
        _rsave(rt)
        _audit({"event": "reset", "provider": provider})
        return {"ok": True, "brand": BRAND_TAG, "reset": provider}
    f = _runtime_file()
    if f.is_file():
        f.unlink()
    _audit({"event": "reset_all"})
    return {"ok": True, "brand": BRAND_TAG, "reset": "all"}


# ══════════════════════════════════════════════════════════════════════
#  energy —— 能源总览（主人令：不能出现能源补给不够）
# ══════════════════════════════════════════════════════════════════════
def energy() -> dict:
    rows = rank(allow_self=True)      # 总览要看得见付费端点，但必须**标明它只等点名**
    slots = []
    for x in rows:
        if x["alive"]:
            status = "储备" if x["in_reserve"] else (
                "仅点名（付费·冷启动 ~300s）" if x.get("owner_only") else "可用")
        else:
            status = x["why"]
        slots.append({"provider": x["provider"], "status": status,
                      "alive": x["alive"], "tier": x["tier"],
                      "owner_only": bool(x.get("owner_only")),
                      "masked": "", "used": x["used"],
                      "quota": x["quota"], "headroom": x["headroom"],
                      "source": x["source"], "url": x["url"], "model": x["model"]})
    # 补掩码（要看得出「哪把钥匙」，但不泄明文）
    for s in slots:
        k, _src = key_for(s["provider"])
        s["masked"] = mask(k, s["provider"]) if k else ""
    alive = [s for s in slots if s["alive"]]

    # ⚠️ 实测发现（2026-09-27）：链上会出现**同一把钥匙挂多名下**（指纹一致）。
    #    分两种语义，**必须分开报** —— 混一起会把「合理的多模型」误判成浪费：
    #      · 纯重复：同 key + 同地址 + 同模型 ⇒ 一家被限另一家必然同样被限，
    #                换道**白跳一次**（该合并；本次 kimi/moonshot 就是这种，已合并）
    #      · 共享额度：同 key + 不同模型 ⇒ 额度共享（换道有意义，但会一起被限；
    #                NVIDIA 的 glm-5.3 / glm-5.3-flash 属这种，保留是对的）
    by_fp = {}
    for s in slots:
        if s["alive"] and s["masked"]:
            by_fp.setdefault(s["masked"].rsplit("#", 1)[-1], []).append(s)
    pure_dup, shared_quota = [], []
    for fp, grp in by_fp.items():
        if len(grp) < 2:
            continue
        if len({(g["url"], g["model"]) for g in grp}) == 1:
            pure_dup.append({"providers": [g["provider"] for g in grp], "fp": fp,
                             "why": "同一把钥匙 + 同一地址 + 同一模型 ⇒ 换道会白跳一次"})
        else:
            shared_quota.append({"providers": [g["provider"] for g in grp], "fp": fp,
                                 "models": [g["model"] for g in grp],
                                 "why": "同一把钥匙、不同模型 ⇒ 额度共享，会一起被限"})
    return {"ok": True, "brand": BRAND_TAG, "cap": CAP,
            "summary": ("能源充足：全网 %d 条通道可用（主路 %d / 深推理 %d / 本地 %d）"
                        % (len(alive),
                           sum(1 for s in alive if s["tier"] == "primary"),
                           sum(1 for s in alive if s["tier"] == "deep"),
                           sum(1 for s in alive if s["tier"] == "local"))
                        if alive else "⚠️ 能源枯竭：没有任何通道可用 —— 会 fail-closed（不瞎挑）"),
            "alive": len(alive), "total": len(slots), "slots": slots,
            "pure_duplicates": pure_dup,
            "shared_quota_keys": shared_quota,
            "duplicate_note": ("；".join([d["why"] + "：%s" % "/".join(d["providers"])
                                          for d in pure_dup] +
                                         ["%s（额度共享，保留合理）" % "/".join(d["providers"])
                                          for d in shared_quota])
                               or "无重复钥匙，每条通道都是独立的能源"),
            "invariants": ["I1 同一 provider 内不自动换 key",
                           "I2 400/422 不换道",
                           "I3 不榨干储备（预留 %d%%）" % int(RESERVE_RATIO * 100)],
            "runtime_file": str(_runtime_file())}


# ══════════════════════════════════════════════════════════════════════
#  统一密钥库（铸造/校验/吊销）—— 长文「兼容密钥」那一层
#  BLAKE2b 摘要入 SQLite，**原始密钥永不落库**；铸造前缀带品牌
# ══════════════════════════════════════════════════════════════════════
def _db() -> sqlite3.Connection:
    con = sqlite3.connect(str(_vault_file()))
    con.execute("""CREATE TABLE IF NOT EXISTS gbt_xiaotudou_v8_unified_keys (
        key_id     TEXT PRIMARY KEY,
        label      TEXT NOT NULL,
        hash       TEXT NOT NULL UNIQUE,
        algo       TEXT NOT NULL,
        scopes     TEXT NOT NULL DEFAULT 'llm.chat',
        created_at TEXT NOT NULL,
        expires_at TEXT,
        last_used  TEXT,
        calls      INTEGER NOT NULL DEFAULT 0,
        revoked    INTEGER NOT NULL DEFAULT 0,
        brand      TEXT NOT NULL
    )""")
    con.commit()
    return con


def mint(label: str, scopes="llm.chat", ttl_days: int = 0) -> dict:
    """铸造一把统一密钥：`gbtv8-<32hex>`。**明文只回一次，库里只存摘要。**"""
    label = str(label or "").strip()
    if not label:
        return {"ok": False, "fail_closed": True, "error": "必须给 label（这密钥是给谁用的）"}
    raw = MINT_PREFIX + secrets.token_hex(16)
    kid = "key_" + secrets.token_hex(6)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    exp = (time.strftime("%Y-%m-%dT%H:%M:%S",
                         time.localtime(time.time() + ttl_days * 86400))
           if ttl_days else None)
    con = _db()
    con.execute(
        "INSERT INTO gbt_xiaotudou_v8_unified_keys"
        "(key_id,label,hash,algo,scopes,created_at,expires_at,revoked,brand)"
        " VALUES(?,?,?,?,?,?,?,0,?)",
        (kid, label, fingerprint(raw), "blake2b-32", str(scopes), now, exp, BRAND))
    con.commit()
    con.close()
    _audit({"event": "mint", "key_id": kid, "label": label, "fp": fingerprint(raw)})
    return {"ok": True, "brand": BRAND_TAG, "key_id": kid, "label": label,
            "key": raw, "masked": mask(raw, "unified"),
            "warning": "明文只出现这一次 —— 库里只有摘要，丢了找不回，只能重铸",
            "scopes": scopes, "created_at": now, "expires_at": exp}


def verify(raw: str) -> dict:
    """校验一把统一密钥（比对摘要 + 查吊销/过期），并记一次使用。"""
    fp = fingerprint(str(raw or "").strip())
    if not fp:
        return {"ok": False, "error": "空密钥"}
    con = _db()
    row = con.execute(
        "SELECT key_id,label,scopes,expires_at,calls,revoked FROM "
        "gbt_xiaotudou_v8_unified_keys WHERE hash=?", (fp,)).fetchone()
    if not row:
        con.close()
        return {"ok": False, "brand": BRAND_TAG, "error": "密钥不存在（摘要未命中）",
                "fp": fp}
    kid, label, scopes, exp, calls, revoked = row
    if revoked:
        con.close()
        return {"ok": False, "brand": BRAND_TAG, "error": "密钥已吊销", "key_id": kid}
    if exp and exp < time.strftime("%Y-%m-%dT%H:%M:%S"):
        con.close()
        return {"ok": False, "brand": BRAND_TAG, "error": "密钥已过期",
                "key_id": kid, "expires_at": exp}
    con.execute("UPDATE gbt_xiaotudou_v8_unified_keys SET calls=calls+1, last_used=? "
                "WHERE key_id=?", (time.strftime("%Y-%m-%dT%H:%M:%S"), kid))
    con.commit()
    con.close()
    _audit({"event": "verify", "key_id": kid, "fp": fp, "ok": True})
    return {"ok": True, "brand": BRAND_TAG, "key_id": kid, "label": label,
            "scopes": scopes, "calls": int(calls or 0) + 1,
            "masked": mask(str(raw).strip(), "unified")}


def revoke(key_id: str) -> dict:
    con = _db()
    cur = con.execute("UPDATE gbt_xiaotudou_v8_unified_keys SET revoked=1 WHERE key_id=?",
                      (str(key_id or "").strip(),))
    con.commit()
    n = cur.rowcount
    con.close()
    if not n:
        return {"ok": False, "error": "没有这把密钥：%s" % key_id}
    _audit({"event": "revoke", "key_id": key_id})
    return {"ok": True, "brand": BRAND_TAG, "revoked": key_id}


def keys() -> dict:
    con = _db()
    rows = con.execute(
        "SELECT key_id,label,scopes,created_at,expires_at,last_used,calls,revoked "
        "FROM gbt_xiaotudou_v8_unified_keys ORDER BY created_at DESC").fetchall()
    con.close()
    out = [{"key_id": r[0], "label": r[1], "scopes": r[2], "created_at": r[3],
            "expires_at": r[4], "last_used": r[5], "calls": r[6],
            "revoked": bool(r[7])} for r in rows]
    return {"ok": True, "brand": BRAND_TAG, "count": len(out), "keys": out}


def compat_adapters() -> dict:
    """兼容层形态说明：同一把 `gbtv8-` 密钥，在各宿主里怎么配。

    ⚠️ 这里只出**形态**，不出任何真实密钥。
    """
    return {"ok": True, "brand": BRAND_TAG,
            "styles": {
                "openai": {"env": "OPENAI_API_KEY", "base_url_key": "OPENAI_BASE_URL",
                           "shape": "%s<32hex>（Bearer）" % MINT_PREFIX},
                "anthropic": {"env": "ANTHROPIC_API_KEY",
                              "shape": "%s<32hex>（x-api-key）" % MINT_PREFIX},
                "gemini": {"env": "GEMINI_API_KEY",
                           "shape": "%s<32hex>（?key= 查询串）" % MINT_PREFIX},
                "framework": {"env": "GBT_LLM_API_KEY",
                              "extra": ["GBT_LLM_BASE_URL", "GBT_LLM_MODEL"],
                              "shape": "%s<32hex>（框架统一口）" % MINT_PREFIX},
            },
            "note": "兼容层只换『密钥形态』，不改协议；真实密钥一律经 op=mint 铸造"}


# ══════════════════════════════════════════════════════════════════════
#  能力入口
# ══════════════════════════════════════════════════════════════════════
def run(op: str = "status", **params) -> dict:
    """op ∈ status / energy / plan / note / reset / mask / classify / whoami
             / mint / verify / revoke / keys / compat
    """
    op = str(op or "status").strip().lower()
    if op in ("status", "whoami"):
        rt = _rload()
        rows = rank()
        active = str(rt.get(_GLOBAL_ACTIVE) or "")
        return {"ok": True, "cap": CAP, "brand": BRAND_TAG, "brand_name": BRAND,
                "order": _ORDER, "chain_source": "llm/cloud_llm.py::_KEY_CHAIN（同源同序）",
                "runtime_ttl_s": _RUNTIME_TTL_S,
                "note": "0 = 每次调用现算（旧链路的病根是『算一次存一辈子』）",
                "alive": sum(1 for x in rows if x["alive"]),
                "total": len(rows), "active": active,
                "switches": int(rt.get(_GLOBAL_SWITCHES, 0) or 0),
                "service": _service_names(rt)}
    if op == "energy":
        return energy()
    if op == "plan":
        return plan(need_tokens=int(params.get("need_tokens", 0) or 0),
                    prefer=str(params.get("prefer", "") or ""))
    if op == "materialize":
        return materialize(str(params.get("provider", "") or ""))
    if op in ("note", "note_result", "report"):
        return note_result(str(params.get("provider", "") or ""),
                           ok=bool(params.get("ok", True)),
                           status=params.get("status"),
                           error=str(params.get("error", "") or ""),
                           tokens=int(params.get("tokens", 0) or 0),
                           cooldown_s=int(params.get("cooldown_s", 0) or 0))
    if op == "reset":
        return reset(str(params.get("provider", "") or ""))
    if op == "mask":
        return {"ok": True, "brand": BRAND_TAG,
                "masked": mask(str(params.get("key", "") or ""),
                               str(params.get("provider", "") or ""))}
    if op == "classify":
        cls = classify(params.get("status"), str(params.get("error", "") or ""))
        return {"ok": True, "brand": BRAND_TAG, "err_class": cls, **decide(cls)}
    if op == "mint":
        return mint(str(params.get("label", "") or ""),
                    scopes=params.get("scopes", "llm.chat"),
                    ttl_days=int(params.get("ttl_days", 0) or 0))
    if op == "verify":
        return verify(str(params.get("key", "") or ""))
    if op == "revoke":
        return revoke(str(params.get("key_id", "") or ""))
    if op == "keys":
        return keys()
    if op == "compat":
        return compat_adapters()
    return {"ok": False, "fail_closed": True, "brand": BRAND_TAG,
            "error": "未知 op %r" % op,
            "available": ["status", "energy", "plan", "materialize", "note", "reset",
                          "mask", "classify", "mint", "verify", "revoke", "keys",
                          "compat", "selftest"]}


def _service_names(rt: dict) -> list:
    """当前实际会出网的通道（供『谁在出网』审计用）。"""
    out = []
    for n in _ORDER:
        st = rt.get(n) or {}
        if st.get("active"):
            out.append(n)
    return out


HONEST_BOUNDARY = (
    "本网关保证：**选路是活的**（每次调用现算）、**失败分类是机械闸**（不由心情决定）、"
    "**全不可用时 fail-closed**（不瞎挑、不静默降级）、**密钥永不明文落库落账**。"
    "它保证不了：免费额度用不完（额度由平台给，不由网关给）；"
    "也保证不了 400/422 自动修好 —— 那是请求参数的问题，网关只会如实报错，"
    "**换道会把参数缺陷伪装成『模型不行』**。"
)


# ══════════════════════════════════════════════════════════════════════
#  自检（只读：不写运行态、不发密钥、不出网）
# ══════════════════════════════════════════════════════════════════════
def selftest() -> dict:
    checks = []

    def ck(name, cond, detail=""):
        checks.append({"ok": bool(cond), "name": name, "detail": str(detail)[:160]})

    ck("品牌标志在册", BRAND == "GBT小土豆V8" and BRAND_TAG.startswith("🥔"), BRAND_TAG)
    ck("铸造前缀带品牌", MINT_PREFIX == "gbtv8-", MINT_PREFIX)
    ck("agnes 仍是声明层第一位（test_framework 契约）",
       _ORDER[0] == "agnes" and _BY_NAME["agnes"]["url"] == "https://apihub.agnes-ai.com/v1"
       and _BY_NAME["agnes"]["model"] == "agnes-2.5-flash", _ORDER[0])
    ck("I2·400 不换道", decide("bad_request")["failover"] is False)
    ck("I2·422 不换道", decide(classify(422))["failover"] is False)
    ck("429 记限流并换道", decide(classify(429))["failover"] is True
       and classify(429) == "rate_limited")
    ck("402 记耗尽并换道", decide(classify(402))["exhaust"] is True)
    ck("401 记失效并换道", decide(classify(401))["disable"] is True)
    ck("403 同 401", classify(403) == "key_invalid")
    ck("5xx 同家重试（不硬断连）", decide(classify(503))["retry_same"] is True
       and decide(classify(503))["escalate"] is True)
    ck("transient 单次失败不致硬断连（同家重试 + 耗尽后继续下一家）",
       decide("transient")["retry_same"] is True
       and decide("transient")["escalate"] is True)
    ck("bad_request 是**硬停**（同家不试、也不往下走）",
       decide("bad_request")["retry_same"] is False
       and decide("bad_request")["escalate"] is False)
    ck("unknown 也是硬停（不拿换道掩盖）",
       decide("unknown")["escalate"] is False)
    ck("404 该家没这模型 → 换道", decide(classify(404))["failover"] is True)
    ck("文本兜底：余额不足", classify(None, "your balance is insufficient") == "quota_exhausted")
    ck("文本兜底：假端点 no available channel",
       classify(None, "503 model_not_found — No available channel for model X") == "not_found")
    # ⚠️ 回归钉（血账 2026-09-28 实弹）：400 + 「模型暂不支持调用」必须归 not_found 而不是
    #    bad_request —— 否则一条声明过期模型名的通道会把整单硬停打死。
    _tmr = ("400 {\"error\":{\"message\":\"模型 'gpt-4o-mini' 暂不支持调用，"
            "请改用 GET /v1/models 中的其他模型。\",\"type\":\"model_not_found\"}}")
    ck("文本兜底：400+「暂不支持调用」⇒ not_found（换道，不硬停）",
       classify(400, _tmr) == "not_found" and decide(classify(400, _tmr))["failover"] is True)
    ck("I2 未被放宽：400+「参数错误」仍是 bad_request（硬停）",
       classify(400, "invalid_request: temperature must be a number") == "bad_request"
       and decide(classify(400, "invalid_request: temperature must be a number"))["escalate"] is False)
    ck("文本兜底：余额不足/需充值", classify(400, "钱包余额不足，需先充值后调用") == "quota_exhausted")
    ck("I3·储备比例 20%%", RESERVE_RATIO == 0.20)
    ck("掩码不泄明文",
       (lambda k: k not in mask(k, "agnes") and BRAND_TAG in mask(k, "agnes"))("sk-abcdef1234567890xyz"))
    ck("同密钥同指纹", fingerprint("sk-abc") == fingerprint("sk-abc"))
    ck("异密钥异指纹", fingerprint("sk-abc") != fingerprint("sk-abd"))
    ck("不读密钥也能报在位（rank 只读）", isinstance(rank(), list))

    # 自检只读：跑前后运行态逐字节相同
    rf = _runtime_file()
    before = rf.read_bytes() if rf.is_file() else b""
    rank()
    energy()
    run("status")
    after = rf.read_bytes() if rf.is_file() else b""
    ck("判据·自检只读（运行态零改动）", before == after,
       "%d/%d bytes" % (len(before), len(after)))

    passed = sum(1 for c in checks if c["ok"])
    return {"ok": passed == len(checks), "brand": BRAND_TAG, "cap": CAP,
            "passed": passed, "total": len(checks), "checks": checks,
            "honest_boundary": HONEST_BOUNDARY}


if __name__ == "__main__":
    import sys
    # 直接跑本文件时，包根不在 sys.path —— 先补上（否则 gbt_allinone._paths 找不到）
    from pathlib import Path as _P
    _root = str(_P(__file__).resolve().parents[2])
    if _root not in sys.path:
        sys.path.insert(0, _root)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    r = selftest()
    for c in r["checks"]:
        print("  [%s] %s%s" % ("PASS" if c["ok"] else "FAIL", c["name"],
                               ("  ← " + c["detail"]) if not c["ok"] and c["detail"] else ""))
    print("\n%s 自检 %d/%d" % (BRAND_TAG, r["passed"], r["total"]))
