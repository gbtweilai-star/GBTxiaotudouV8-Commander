"""GBT小土豆V8 · 服务巡检（两大体系合流第一步：纳入观察，只看不动）。

立场：修复会话（GBT小土豆树 + 量化树）的服务与 V8 并行共存（端口零重叠已验证）。
本模块不启停、不杀、不改任何外部进程——只把已登记的服务纳入统一观察与审计：
探活端口、记录状态快照、异常落审计。启停控制永远是 Owner 的显式指令。

服务清单：services.json（按名登记 host/port/归属/备注，可增删）。
"""
import json
import socket
import time
from pathlib import Path

_STORE = __import__("gbt_allinone._paths", fromlist=["STORE_DIR"]).STORE_DIR
_SVC_FILE = _STORE / "services.json"

# 出厂预置：修复会话当前实测在跑的服务（2026-09-11 01:47 巡检确认）
DEFAULT_SERVICES = {
    "payment_gateway":    {"host": "127.0.0.1", "port": 8081, "owner": "GBT小土豆", "note": "支付网关"},
    "blockchain_bridge":  {"host": "127.0.0.1", "port": 8082, "owner": "GBT小土豆", "note": "链上桥"},
    "social_trading_v2":  {"host": "127.0.0.1", "port": 8084, "owner": "GBT小土豆", "note": "社交易"},
    "monitor_service":    {"host": "127.0.0.1", "port": 8085, "owner": "GBT小土豆", "note": "监控服务"},
    "backtest_api_v2":    {"host": "127.0.0.1", "port": 8089, "owner": "量化收割引擎", "note": "回测API"},
    "cis_harvesting_v2":  {"host": "127.0.0.1", "port": 8090, "owner": "量化收割引擎", "note": "CIS收割"},
    "quant_api":          {"host": "127.0.0.1", "port": 8091, "owner": "量化收割引擎", "note": "量化API"},
    "cis_v42_trader":     {"host": "127.0.0.1", "port": 8092, "owner": "量化收割引擎", "note": "CIS交易"},
    "crypto_gateway":     {"host": "127.0.0.1", "port": 8094, "owner": "GBT小土豆", "note": "交易所网关"},
    "gbt_wallet_api":     {"host": "127.0.0.1", "port": 8097, "owner": "GBT小土豆", "note": "钱包API"},
    "gbt_cap_bridge":     {"host": "127.0.0.1", "port": 18900, "owner": "GBT小土豆", "note": "能力桥"},
    "hcl_control":        {"host": "127.0.0.1", "port": 19090, "owner": "GBT小土豆", "note": "万能插控制"},
    "gate_daemon":        {"host": "127.0.0.1", "port": 25485, "owner": "GBT小土豆", "note": "门禁守护"},
    "v8_isolated":        {"host": "127.0.0.1", "port": 8098, "owner": "GBT小土豆V8", "note": "V8隔离实例（预留）", "optional": True},
}


def _load() -> dict:
    if _SVC_FILE.exists():
        try:
            return json.loads(_SVC_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return dict(DEFAULT_SERVICES)


def _save(data: dict):
    _STORE.mkdir(parents=True, exist_ok=True)
    _SVC_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def register(name: str, host: str, port: int, owner: str = "", note: str = "") -> dict:
    if not name or not host or not (0 < int(port) < 65536):
        raise ValueError("需要 name/host/port(1-65535)")
    data = _load()
    data[name] = {"host": host, "port": int(port), "owner": owner, "note": note}
    _save(data)
    return {"ok": True, "name": name}


def unregister(name: str) -> dict:
    data = _load()
    if name not in data:
        raise ValueError(f"服务未登记: {name}")
    data.pop(name)
    _save(data)
    return {"ok": True, "removed": name}


_optional_state = {}  # 预留服务状态记忆 {name: bool}


def _probe(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def inspect(name=None, timeout=0.6, quiet=False) -> dict:
    """探活：单服务或全部（线程池并发，可选服务超时减半）。返回快照并落审计。

    quiet=True（纯探活查询：selfscan 恢复判定等观察者场景）：只返回快照，不落 svc_down——
    观察者不制造被观察的记录（防自放大循环：svc_down越多→探活越多→svc_down更多）。
    optional 标记的服务（如预留端口）探活失败不算 down、不落审计——如实标注为 optional_down。
    """
    from .store import audit
    from concurrent.futures import ThreadPoolExecutor
    data = _load()
    if name and name not in data:
        raise ValueError(f"服务未登记: {name}")
    targets = {name: data[name]} if name else data
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")

    def _one(item):
        svc, s = item
        if s.get("optional"):
            # 预留服务：首次探测后记住状态，确认未启动则跳过真实连接（0ms，不等超时）
            prev = _optional_state.get(svc)
            if prev is False:
                return svc, False
            up = _probe(s["host"], s["port"], min(timeout, 0.4))
            _optional_state[svc] = up
            return svc, up
        return svc, _probe(s["host"], s["port"], timeout)

    with ThreadPoolExecutor(max_workers=min(16, max(1, len(targets)))) as pool:
        results = dict(pool.map(_one, targets.items()))

    snap = {}
    for svc, s in targets.items():
        up = results.get(svc, False)
        snap[svc] = {"host": s["host"], "port": s["port"], "owner": s.get("owner", ""),
                     "up": up, "optional": bool(s.get("optional")),
                     "checked_at": ts}
    # down 只算非可选服务；可选掉线单独归 optional_down（如实但不误报）
    down = [k for k, v in snap.items() if not v["up"] and not v["optional"]]
    opt_down = [k for k, v in snap.items() if not v["up"] and v["optional"]]
    if down and not quiet:
        audit("svc_down", {"services": down})
    return {"services": snap, "total": len(snap),
            "up": len(snap) - len(down) - len(opt_down),
            "down": down, "optional_down": opt_down}
