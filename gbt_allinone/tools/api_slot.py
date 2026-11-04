# -*- coding: utf-8 -*-
# gbt-capability: api_slot  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""动态 API 槽（api_slot）—— 只登记定义，不偷偷发请求。

对照上游参考项目的动态 API / 工具市场：只蒸**槽定义契约**，不搬它的执行器/secret store。
铁律：
  · 只许 https；拒 localhost/私网/保留地址/URL 内凭据（不新建 SSRF 面）；
  · 密钥只存**环境变量引用名**（如 GBT_API_X_KEY），绝不存明文；
  · 参数 schema 白名单（string/number/bool），≤10 个；超时 1..30s；上限 20 槽；
  · `call()` 永远 `not_supported`：执行器未接（需要 network egress 门 + 注入），
    只登记定义、不假装调通；真执行另建门/授权链。
"""
from __future__ import annotations

import hashlib
import ipaddress
import re
import urllib.parse

MAX_SLOTS = 20
MAX_PARAMS = 10
NAME_RX = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
ENV_RX = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
METHODS = ("GET", "POST")
PARAM_TYPES = ("string", "number", "bool")
BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"}
END_NOTE = "执行器未接（需要 network egress 门 + 密钥注入）；只登记定义，不假装调通"


class SlotError(ValueError):
    pass


def _host_allowed(host: str) -> tuple[bool, str]:
    h = str(host or "").strip().lower().rstrip(".")
    if not h:
        return False, "host 为空"
    if h in BLOCKED_HOSTS or h.endswith(".localhost") or h.endswith(".local"):
        return False, "host 被拒（本机/内网/metadata）"
    try:
        ip = ipaddress.ip_address(h)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False, "IP 被拒（私网/保留/回环）"
        return True, ""
    except ValueError:
        pass
    if h.isdigit():
        return False, "host 非法"
    return True, ""


def validate_slot(slot) -> dict:
    if not isinstance(slot, dict):
        raise SlotError("slot 必须是对象")
    name = str(slot.get("name") or "").strip()
    if not NAME_RX.match(name):
        raise SlotError("name 只许小写字母开头 + 小写字母数字_（2..32）")
    method = str(slot.get("method") or "GET").upper()
    if method not in METHODS:
        raise SlotError("method 只许 GET/POST")
    url = str(slot.get("url") or "").strip()
    try:
        u = urllib.parse.urlparse(url)
    except Exception:  # noqa: BLE001
        raise SlotError("url 解析失败")
    if u.scheme != "https":
        raise SlotError("只许 https（不新增明文/SSRF 面）")
    ok, why = _host_allowed(u.hostname or "")
    if not ok:
        raise SlotError("url " + why)
    if u.username or u.password:
        raise SlotError("url 不许内嵌凭据")
    if len(url) > 2000:
        raise SlotError("url 超长（>2000）")
    try:
        timeout = float(slot.get("timeout", 8))
    except (TypeError, ValueError):
        raise SlotError("timeout 必须是数字")
    if not (1.0 <= timeout <= 30.0):
        raise SlotError("timeout 范围 1..30 秒")
    secret_env = str(slot.get("secret_env") or "").strip()
    if secret_env and not ENV_RX.match(secret_env):
        raise SlotError("secret_env 只许环境变量引用名（大写字母数字_）")
    params = slot.get("params") or []
    if not isinstance(params, list):
        raise SlotError("params 必须是数组")
    if len(params) > MAX_PARAMS:
        raise SlotError("params 最多 %d 个" % MAX_PARAMS)
    out_params, seen = [], set()
    for p in params:
        if not isinstance(p, dict):
            raise SlotError("param 必须是对象")
        pn = str(p.get("name") or "").strip()
        if not NAME_RX.match(pn):
            raise SlotError("param.name 非法: %s" % pn)
        if pn in seen:
            raise SlotError("param.name 重复: %s" % pn)
        seen.add(pn)
        pt = str(p.get("type") or "string").lower()
        if pt not in PARAM_TYPES:
            raise SlotError("param.type 只许 string/number/bool")
        out_params.append({"name": pn, "type": pt, "required": bool(p.get("required")),
                           "desc": str(p.get("desc") or "")[:120]})
    return {"name": name, "method": method, "url": url, "timeout": timeout,
            "secret_env": secret_env, "params": out_params,
            "desc": str(slot.get("desc") or "")[:200],
            "created_at": float(slot.get("created_at") or 0)}


def call(name) -> dict:
    return {"ok": False, "status": "not_supported", "executed": False,
            "name": str(name or ""), "reason": "动态 API " + END_NOTE}


class SlotRegistry:
    def __init__(self, max_slots: int = MAX_SLOTS):
        self.max_slots = int(max_slots)
        self.slots = {}
        self.events = []

    def register(self, raw) -> dict:
        slot = validate_slot(raw)
        if slot["name"] not in self.slots and len(self.slots) >= self.max_slots:
            return {"ok": False, "error": "too_many_slots"}
        self.slots[slot["name"]] = slot
        self.events.append({"type": "register", "name": slot["name"]})
        return {"ok": True, "slot": slot, "count": len(self.slots)}

    def remove(self, name) -> dict:
        if str(name) not in self.slots:
            return {"ok": False, "error": "no_such_slot"}
        slot = self.slots.pop(str(name))
        self.events.append({"type": "remove", "name": str(name)})
        return {"ok": True, "removed": str(name), "count": len(self.slots)}

    def list(self) -> dict:
        return {"ok": True, "slots": list(self.slots.values()), "count": len(self.slots),
                "max": self.max_slots, "executor": "not_wired"}


_REG = SlotRegistry()


def verify() -> dict:
    checks = []

    def ck(name, cond, got=None):
        checks.append({"name": name, "ok": bool(cond), "got": got})

    good = {"name": "weather_api", "method": "GET", "url": "https://api.example.com/v1/weather",
            "timeout": 8, "secret_env": "GBT_WEATHER_KEY",
            "params": [{"name": "city", "type": "string", "required": True}]}
    s = validate_slot(good)
    ck("合法槽归一", s["name"] == "weather_api" and s["method"] == "GET")
    ck("https 放行", s["url"].startswith("https://"))
    for bad in (
        {"name": "x", "url": "http://api.example.com"},
        {"name": "x", "url": "https://localhost/x"},
        {"name": "x", "url": "https://127.0.0.1/x"},
        {"name": "x", "url": "https://192.168.1.2/x"},
        {"name": "x", "url": "https://user:pass@api.example.com/x"},
        {"name": "Bad Name", "url": "https://api.example.com"},
        {"name": "x", "url": "https://api.example.com", "method": "DELETE"},
        {"name": "x", "url": "https://api.example.com", "timeout": 999},
        {"name": "x", "url": "https://api.example.com", "secret_env": "sk-live-xxx"},
        {"name": "x", "url": "https://api.example.com",
         "params": [{"name": "p%d" % i, "type": "string"} for i in range(11)]},
        {"name": "x", "url": "https://api.example.com", "params": [{"name": "p", "type": "bad"}]},
    ):
        try:
            validate_slot(bad)
            ck("坏槽拒 " + str(bad.get("url")), False, bad)
        except SlotError:
            ck("坏槽拒 " + str(list(bad)[:2]), True)
    reg = SlotRegistry()
    ck("注册", reg.register(good)["ok"] and reg.list()["count"] == 1)
    ck("删除", reg.remove("weather_api")["ok"] and reg.list()["count"] == 0)
    ck("不存在删除", reg.remove("nope")["ok"] is False)
    r2 = SlotRegistry(max_slots=1)
    r2.register(good)
    ck("上限", r2.register(dict(good, name="second", url="https://api2.example.com"))["ok"] is False)
    c = call("weather_api")
    ck("call 永远 not_supported", c["ok"] is False and c["status"] == "not_supported"
       and c["executed"] is False)
    ck("call 带原因", "未接" in c["reason"] or "not" in c["reason"].lower())
    ck("schema 可达", "methods" in run("schema") and "param_types" in run("schema"))
    ck("list 只读", run("list")["ok"] and "executor" in run("list"))
    ck("未知 op 拒", _raises(lambda: run("teleport")))
    ck("secret 不存值", "sk-live" not in str(validate_slot(good)))
    return {"ok": all(c["ok"] for c in checks), "checks": len(checks),
            "failed": [c for c in checks if not c["ok"]],
            "sha": hashlib.sha256(str(checks).encode()).hexdigest()[:12]}


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except (SlotError, ValueError):
        return True


def run(op="schema", **params):
    op = str(op or "schema").lower()
    if op == "schema":
        return {"ok": True, "name_rx": NAME_RX.pattern, "methods": list(METHODS),
                "param_types": list(PARAM_TYPES), "max_slots": MAX_SLOTS,
                "max_params": MAX_PARAMS, "executor": "not_wired", "note": END_NOTE}
    if op == "validate":
        try:
            return {"ok": True, "slot": validate_slot(params.get("slot"))}
        except SlotError as e:
            return {"ok": False, "error": "user_error: %s" % e}
    if op == "register":
        try:
            return _REG.register(params.get("slot"))
        except SlotError as e:
            return {"ok": False, "error": "user_error: %s" % e}
    if op == "remove":
        return _REG.remove(params.get("name"))
    if op == "list":
        return _REG.list()
    if op == "call":
        return call(params.get("name"))
    if op == "verify":
        return verify()
    raise ValueError("未知 op: %s（schema/validate/register/remove/list/call/verify）" % op)
