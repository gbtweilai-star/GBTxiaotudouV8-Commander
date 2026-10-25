# -*- coding: utf-8 -*-
"""GBT小土豆V8 · FreeLLMAPI 接入层（本地免费大模型池）

把本机 FreeLLMAPI（34 家免费供应商 / 635 个免费端点，汇成一个 OpenAI 兼容 /v1）
接进我们的框架：既能让框架**吃免费算力**，也能**自动配置密钥**。

═══ 两条线严格分开（读对方源码得到，不是猜）═══
  ① 吃免费能力：`/v1/*`
     只要**统一 API key**，**不需要 dashboard 登录**。
     证据：`middleware/requireAuth.ts:6-7` 注释明写「The /v1 proxy is NOT gated
     by this — it keeps its own unified-API-key auth for app clients.」

  ② 配密钥：`/api/*`
     **需要 dashboard 会话 token**。
     证据：`server/src/app.ts:212` `app.use('/api/keys', requireAuth, keysRouter);`
     取证：`POST /api/auth/login` → 拿 token → 放 `Authorization: Bearer <token>`

═══ 纪律（三条，不商量）═══
  1. **绝不从 SQLite 掏 session token 绕过登录**。那是绕门。
     要配置就让主人登录一次，走官方 `/api/auth/login`。
  2. **绝不打印/返回明文密钥**。一律经 `mask()` 打码；写到磁盘的更是一个字都不留。
  3. **不改 FreeLLMAPI 的源码**。它是别人的项目，改了就没法升级。

═══ 已知限制（作者原话，必须转达，不许美化）═══
  · "personal experimentation and learning, not production" —— 上线要换付费 API
  · 各家免费额度受**你注册时接受的服务条款**约束
  · 无前沿模型、延迟不稳、无 SLA
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

# ═══ 端口发现（2026-09-22 实测教训）═══
# 我原先写死 `http://localhost:3001`（README 的默认值）—— **错的**。
# 实测：本机桌面版跑在 **127.0.0.1:31415**（4 个进程，9/21 起就在跑，日志当天还在写）。
# 它的 `%APPDATA%\FreeLLMAPI\config.json` 里明写 {"port": 31415}。
# ⇒ 绝不写死端口，按「环境变量 → 桌面版 config.json → 默认 3001」三级发现。
_ENV_URL = os.getenv("GBT_FREELLMAPI_URL", "").rstrip("/")

_CONFIG_CANDIDATES = [
    Path(os.getenv("APPDATA", "")) / "FreeLLMAPI" / "config.json",       # Windows 桌面版
    Path.home() / ".config" / "FreeLLMAPI" / "config.json",              # Linux 桌面版
    Path.home() / "Library" / "Application Support" / "FreeLLMAPI" / "config.json",  # macOS
]

# 对方声明的供应商数（拿来做对账，不是写死依赖）
EXPECTED_PROVIDERS = 34

_IMPL_VERSION = "1.1"


def discover_base_url() -> tuple:
    """返回 (base_url, 来源)。顺序：环境变量 → 桌面版 config.json → 默认 3001。"""
    if _ENV_URL:
        return _ENV_URL, "env:GBT_FREELLMAPI_URL"
    for c in _CONFIG_CANDIDATES:
        try:
            if c.is_file():
                d = json.loads(c.read_text(encoding="utf-8-sig"))
                port = int(d.get("port") or 0)
                if port:
                    return f"http://127.0.0.1:{port}", f"desktop-config:{c}"
        except Exception:                                           # noqa: BLE001
            continue
    return "http://localhost:3001", "default(README)"


def base_url() -> str:
    """当前基址（每次现算，端口换了也能跟上）。"""
    return discover_base_url()[0]


# 兼容旧写法：模块级常量取一次当前值（新代码应调 base_url()）
BASE_URL = base_url()


def mask(secret: str, keep: int = 6) -> str:
    """密钥打码。任何要显示/落盘的地方都必须先过这里。"""
    s = str(secret or "")
    if not s:
        return ""
    if len(s) <= keep:
        return "*" * len(s)
    return s[:keep] + "*" * 8 + f"({len(s)}B)"


def _req(method: str, path: str, *, token: str = "", body: dict | None = None,
         timeout: float = 15.0) -> dict:
    """统一请求。返回 {ok, status, data|error}，**异常不外抛**，如实带原因。"""
    url = base_url() + path
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return {"ok": True, "status": r.status, "data": json.loads(raw)}
            except Exception:                                       # noqa: BLE001
                return {"ok": True, "status": r.status, "data": {"raw": raw[:400]}}
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            raw = e.read().decode("utf-8", "replace")
            # 对方错误体是 {"error":{"message":"..."}}，抽干净的话术，
            # 别把半截 JSON 直接甩给人看（实测会截出 `Authentication requ"` 这种尾巴）。
            try:
                j = json.loads(raw)
                err = j.get("error")
                detail = (err.get("message") if isinstance(err, dict) else str(err)) or raw[:200]
            except Exception:                                       # noqa: BLE001
                detail = raw[:200]
        except Exception:                                           # noqa: BLE001
            pass
        hint = ("（需要 dashboard 登录：/api/* 走 requireAuth）"
                if e.code == 401 else "")
        return {"ok": False, "status": e.code,
                "error": f"HTTP {e.code} {hint} {detail}".strip()}
    except Exception as e:                                          # noqa: BLE001
        return {"ok": False, "status": 0,
                "error": f"{type(e).__name__}: {str(e)[:160]}"}


# ═══════════════════════ ① 探活（无需登录）═══════════════════════

def probe(timeout: float = 5.0) -> dict:
    """服务在不在。用 `/api/ping`（app.ts:226）——**明确无鉴权**的探活口。

    为什么不拿别的当探活：`/api/*` 基本都要登录，拿它们探活会把
    「没登录」误判成「服务没起」。
    """
    r = _req("GET", "/api/ping", timeout=timeout)
    if r["ok"]:
        d = r.get("data") or {}
        url, src = discover_base_url()
        return {"up": True, "base_url": url, "discovered_from": src,
                "status": d.get("status"), "timestamp": d.get("timestamp")}
    url, src = discover_base_url()
    return {"up": False, "base_url": url, "discovered_from": src,
            "error": r["error"],
            "note": "服务没起？桌面版端口看 %APPDATA%\\FreeLLMAPI\\config.json"}


def docs_available(timeout: float = 5.0) -> dict:
    """`/v1/docs` 与 `/v1/openapi.json` 是**静态无鉴权**的（app.ts:230-234）。"""
    spec = _req("GET", "/v1/openapi.json", timeout=timeout)
    return {"ok": spec["ok"], "has_spec": bool((spec.get("data") or {}).get("openapi")),
            "error": spec.get("error", "")}


# ═══════════════════════ ② 登录（拿会话 token）═══════════════════════

def login(email: str, password: str, timeout: float = 15.0) -> dict:
    """走官方 `POST /api/auth/login` 换会话 token。

    **token 只在这里返回，不落盘、不打日志**。调用方自己决定放哪（建议内存）。
    """
    if not email or not password:
        return {"ok": False, "error": "需要 email 与 password"}
    r = _req("POST", "/api/auth/login",
             body={"email": email, "password": password}, timeout=timeout)
    if not r["ok"]:
        return {"ok": False, "status": r["status"], "error": r["error"]}
    d = r.get("data") or {}
    token = d.get("token") or d.get("session") or d.get("sessionToken") or ""
    return {"ok": bool(token), "token": token,
            "user": (d.get("user") or {}).get("email") if isinstance(d.get("user"), dict) else None,
            "error": "" if token else f"登录返回里没找到 token，字段有: {sorted(d)[:8]}"}


# ═══════════════════════ ③ 密钥管理（需 token）═══════════════════════

def providers(token: str) -> dict:
    """34 家供应商 + 已配/未配汇总。`GET /api/keys/providers`（keys.ts:178）。"""
    r = _req("GET", "/api/keys/providers", token=token)
    if not r["ok"]:
        return {"ok": False, "error": r["error"], "status": r["status"]}
    d = r.get("data") or {}
    ps = d.get("providers") or []
    return {"ok": True, "summary": d.get("summary") or {},
            "providers": ps,
            "unconfigured": [p.get("platform") for p in ps if not p.get("configured")],
            "expected": EXPECTED_PROVIDERS,
            "matches_expected": len(ps) == EXPECTED_PROVIDERS}


def list_keys(token: str) -> dict:
    """已配密钥（**对方返回里只有 maskedKey，没有明文**）。`GET /api/keys/`（keys.ts:218）。"""
    r = _req("GET", "/api/keys/", token=token)
    if not r["ok"]:
        return {"ok": False, "status": r["status"], "error": r["error"]}
    d = r.get("data")
    keys = d if isinstance(d, list) else (d or {}).get("keys") or []
    return {"ok": True, "count": len(keys), "keys": keys}


def add_key(token: str, platform: str, key: str = "", label: str = "") -> dict:
    """加一把密钥。`POST /api/keys/` body `{platform,key,label}`（keys.ts:481）。

    注意：keyless 供应商（如 Kilo 匿名）可以不传 key —— 对方会用哨兵值占位。
    """
    if not platform:
        return {"ok": False, "error": "需要 platform"}
    r = _req("POST", "/api/keys/",
             token=token, body={"platform": platform, "key": key, "label": label})
    if not r["ok"]:
        return {"ok": False, "platform": platform, "status": r["status"], "error": r["error"]}
    d = r.get("data") or {}
    return {"ok": True, "platform": platform, "id": d.get("id"),
            "masked": d.get("maskedKey") or mask(key),
            "status": d.get("status"), "notice": d.get("notice", "")}


def health_check(token: str, key_id) -> dict:
    """验一把密钥能不能用。`POST /api/health/check/:keyId`（health.ts:61）。

    **写完必须验**：没验过的不许叫「配好了」。
    """
    if key_id in (None, ""):
        return {"ok": False, "error": "需要 key_id"}
    r = _req("POST", f"/api/health/check/{key_id}", token=token)
    if not r["ok"]:
        return {"ok": False, "key_id": key_id, "error": r["error"]}
    return {"ok": True, "key_id": key_id, "result": r.get("data")}


def set_enabled(token: str, key_id, enabled: bool) -> dict:
    """启用/停用一把密钥。`PATCH /api/keys/:id`（keys.ts:1245）。"""
    r = _req("PATCH", f"/api/keys/{key_id}", token=token, body={"enabled": bool(enabled)})
    return {"ok": r["ok"], "key_id": key_id, "error": r.get("error", "")}


def remove_key(token: str, key_id) -> dict:
    """删一把密钥。`DELETE /api/keys/:id`（keys.ts:1163）。**破坏性动作，调用方负责确认**。"""
    r = _req("DELETE", f"/api/keys/{key_id}", token=token)
    return {"ok": r["ok"], "key_id": key_id, "error": r.get("error", "")}


# ═══════════════════════ ④ 接入框架（吃免费算力）═══════════════════════

def unified_key(token: str) -> dict:
    """取统一 key。`GET /api/settings/api-key`（settings.ts:229）。**返回值一律打码**。"""
    r = _req("GET", "/api/settings/api-key", token=token)
    if not r["ok"]:
        return {"ok": False, "status": r["status"], "error": r["error"]}
    k = (r.get("data") or {}).get("apiKey") or ""
    return {"ok": bool(k), "masked": mask(k), "length": len(k),
            "error": "" if k else "没取到统一 key"}


def models(unified: str, timeout: float = 20.0) -> dict:
    """列免费池里可用的模型。`GET /v1/models` —— **只要统一 key，不用登录**。"""
    r = _req("GET", "/v1/models", token=unified, timeout=timeout)
    if not r["ok"]:
        return {"ok": False, "error": r["error"]}
    d = r.get("data") or {}
    items = d.get("data") if isinstance(d, dict) else d
    return {"ok": True, "count": len(items or []),
            "sample": [m.get("id") for m in (items or [])[:8] if isinstance(m, dict)]}


def framework_env(unified: str, base_url: str | None = None) -> dict:
    """给框架 LLM 网关用的环境变量（**只算出来，不写盘**）。

    与 `gbt_allinone/llm/cloud_llm.py` 的 provider 表对齐：
    它认 `GBT_LLM_API_KEY / GBT_LLM_BASE_URL / GBT_LLM_MODEL` 这一路。
    """
    return {
        "GBT_LLM_BASE_URL": (base_url or BASE_URL).rstrip("/") + "/v1",
        "GBT_LLM_API_KEY": unified,
        "GBT_LLM_PROVIDER": "freellmapi",
    }


def status_report(token: str = "") -> dict:
    """她自检用的一张总表。没 token 就只报探活那一段（**不假装拿到了别的东西**）。"""
    out = {"version": _IMPL_VERSION, "base_url": BASE_URL, "probe": probe()}
    if not out["probe"].get("up"):
        out["note"] = "服务没起，后面的都无从谈起"
        return out
    out["docs"] = docs_available()
    if not token:
        out["authed"] = False
        out["note"] = ("只探到服务在。要读供应商/密钥需 dashboard 会话 —— "
                       "走 /api/auth/login，我不绕登录")
        return out
    out["authed"] = True
    out["providers"] = providers(token)
    lk = list_keys(token)
    out["keys"] = {"ok": lk.get("ok"), "count": lk.get("count", 0),
                   "error": lk.get("error", "")}
    return out


if __name__ == "__main__":
    import sys
    print(json.dumps(status_report(sys.argv[1] if len(sys.argv) > 1 else ""),
                     ensure_ascii=False, indent=2))


# ── 2026-10-04 丢失腿复原轮：以下常量与三入口（_gate / run_op / run）从基线工作树
#    （.scratch/_baseline_wt）逐字接回 —— 活树这份模块此前只有 `status_report` 等底层函数、
#    缺能力位入口 ⇒ 注册表里有名字、真调却 `module has no attribute 'run'`。
#    复原工具：tools/codex-scripts/restore_missing_caps.py（可复跑）。 ──
_REPO = Path(__file__).resolve().parents[2]

_GATE_WRITE = ("filesystem_write",)   # 改对方配置 / 传凭据（与 automation_keys 的 set/unset 同口径）

_READ_OPS = ("status", "probe", "docs", "models", "framework_env", "where")
_GATED_OPS = ("login", "unified_key", "providers", "list_keys", "add_key",
              "health_check", "set_enabled", "remove_key")


def _gate(scopes, detail: str) -> dict:
    """`security/policy.py` 无 `freellmapi` 分支（owner-only，AI 无权改）
    ⇒ 门层零作用域 ⇒ 本模块走授权门的**唯一校验入口** `auth_gate.check_and_consume_many`
    （与 `policy.authorize` 同一个）—— **不是绕门，是补门**。"""
    try:
        from .. import auth_gate
        from ..security import policy as _policy
    except ImportError:                                           # 独立加载
        sys.path.insert(0, str(_REPO))
        from gbt_allinone import auth_gate                        # type: ignore
        from gbt_allinone.security import policy as _policy        # type: ignore
    if _policy.is_trusted():
        return {"ok": True, "trusted": True, "scopes": list(scopes)}
    return auth_gate.check_and_consume_many(list(scopes), detail=detail)


def run_op(op: str = "status", **params) -> dict:
    """能力位 op 分派。只读面不过门；写面/传凭据过 `filesystem_write`。"""
    op = str(op or "status").strip().lower()
    if op in ("where", "help"):
        return {"ok": True, "op": "where", "cap": "freellmapi",
                "base_url": base_url(), "discovered_from": discover_base_url()[1],
                "read_ops": list(_READ_OPS), "gated_ops": list(_GATED_OPS),
                "gate_scope": list(_GATE_WRITE),
                "_口径": "只读面（探活/文档/模型列表）不过门；写面（配密钥）过 filesystem_write"}
    if op == "status":
        return status_report(str(params.get("token") or ""))
    if op == "probe":
        return probe(float(params.get("timeout") or 5.0))
    if op == "docs":
        return docs_available(float(params.get("timeout") or 5.0))
    if op == "models":
        return models(str(params.get("unified") or params.get("key") or ""),
                      timeout=float(params.get("timeout") or 20.0))
    if op == "framework_env":
        unified = str(params.get("unified") or params.get("key") or "")
        return {"ok": bool(unified), "op": "framework_env",
                "env": framework_env(unified, params.get("base_url")),
                "_口径": "只算出来，不写盘（与 automation_keys 同一纪律）"}
    if op not in _GATED_OPS:
        return {"ok": False, "op": op,
                "error": "未知 op：%s（只读：%s；需授权：%s）"
                         % (op, ", ".join(_READ_OPS), ", ".join(_GATED_OPS))}
    gate = _gate(_GATE_WRITE, "freellmapi %s → 改对方配置/传凭据" % op)
    if not gate.get("ok"):
        return {"ok": False, "op": op, "denied": True, "fail_closed": True,
                "error_class": "needs_authorization",
                "error": gate.get("error"), "missing": gate.get("missing") or list(_GATE_WRITE),
                "how_to_grant": gate.get("how_to_grant"),
                "why": "配密钥 = 改对方服务的状态 ⇒ 要授权",
                "口径": "缺授权如实报缺；**不绕门**"}
    tok = str(params.get("token") or "")
    if op == "login":
        return login(str(params.get("email") or ""), str(params.get("password") or ""))
    if op == "unified_key":
        return unified_key(tok)
    if op == "providers":
        return providers(tok)
    if op == "list_keys":
        return list_keys(tok)
    if op == "add_key":
        return add_key(tok, str(params.get("platform") or ""),
                       str(params.get("key") or ""), str(params.get("label") or ""))
    if op == "health_check":
        return health_check(tok, params.get("key_id"))
    if op == "set_enabled":
        return set_enabled(tok, params.get("key_id"), bool(params.get("enabled")))
    return remove_key(tok, params.get("key_id"))


def run(payload: dict | None = None) -> dict:
    """能力位入口（api.py 分派到这里）。op 默认 status（**只读**探活）。"""
    p = dict(payload or {})
    op = str(p.pop("op", None) or p.pop("action", None) or "status").lower()
    return run_op(op, **p)
