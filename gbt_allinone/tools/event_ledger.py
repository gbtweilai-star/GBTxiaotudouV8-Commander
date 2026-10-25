# gbt-capability: event_ledger
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""签名事件账：**哈希链 + HMAC 签名，每条都是签名记录**（蒸馏自 buzz，只取账本纪律）。

## 抓取口径（本仓规矩：凡抓取必写源·时间·口径）
· **源**：2026-09-28 主人给的周榜卡 `buzz`（block/buzz · Rust · Apache-2.0 · 立项 2026 ·
  当日 +339 · 共 34,934★）的公开一句话介绍：「人和 AI 智能体同处一室的协作工作台 ·
  **基于 Nostr 中继，所有消息和事件都是签名记录**」。
  —— 一手仓库与文档本轮**未联网核验**（主人令：不出网花钱的动作），只蒸馏**账本纪律**这一面，
  不引用它的 Nostr 实现与代码。
· **时间**：2026-09-28。
· **口径**：本仓已有 `store` 审计账（append-only），但**没有密码学完整性**——
  事后改一行审计账，没有任何东西会报。buzz 的核正是这个：**每条事件都签名、
  事件间成链**，篡改任意一条 ⇒ 校验当场报出第几条被改。

## 蒸馏判断：buzz 的核里我们真缺哪块
| buzz 的能力 | 我们已有的对位 | 结论 |
|---|---|---|
| 人机同室协作台 | `collab_gateway`（房间/收发件） | **已有，不重造** |
| Nostr 中继（网络传输面） | 不做（出网面归门与它自己的闸） | **不要** |
| **签名事件账**（每条签名 + 事件成链） | 无 | **补这块（本件）** |

## 硬规矩
1. **无明文钥匙**：HMAC 钥匙首用时随机生成，**DPAPI 加密落盘**（复用仓内
   `deepseek_key` 的 DPAPI 帮手）⇒ 盘上永远没有可用明文钥匙；DPAPI 不可用 ⇒ **fail-closed**。
2. **成链**：第 n 条 = `{seq, at, kind, payload, prev, hash, sig}`；
   `hash = sha256(prev + 规范化body)`，`sig = HMAC(key, hash)`——改任意一条，
   它之后的**每一条** hash 都对不上 ⇒ 定位到**第一条**被改的。
3. **只增不删**：本件没有删除/改写路径（要作废就 append 一条 `retract`，账面永远完整）。
4. **传输另走门**：跨体传输仍走 `collab_gateway`；本件只管**账本本身**的真伪。
"""
from __future__ import annotations

import hashlib
import hmac as _hmac
import json
import secrets as _pysecrets
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PKG = Path(__file__).resolve().parents[1]
_LEDGER = _ROOT / "state" / "event_ledger.jsonl"
_KEY = _PKG / "secrets" / "event_ledger_key.dpapi"     # DPAPI 加密的 HMAC 钥匙（无明文）


def _key() -> bytes:
    """HMAC 钥匙：首用随机生成 + DPAPI 落盘；之后每次解出。**盘上无明文**。"""
    if _KEY.is_file():
        from .. import deepseek_key as _dk
        blob = _KEY.read_bytes()
        try:
            return _dk._unprotect_dpapi(blob)
        except Exception as e:                          # noqa: BLE001
            raise RuntimeError("钥匙解不开（DPAPI 故障）⇒ fail-closed，不降级：%s" % e)
    from .. import deepseek_key as _dk
    raw = _pysecrets.token_bytes(32)
    _KEY.parent.mkdir(parents=True, exist_ok=True)
    _KEY.write_bytes(_dk._protect_dpapi(raw))
    return raw


def _rows() -> list:
    if not _LEDGER.is_file():
        return []
    out = []
    for ln in _LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue                                    # 坏行如实跳过（verify 会报账面不连续）
    return out


def _body_hash(prev: str, kind: str, payload: dict, at: str, seq: int) -> str:
    body = json.dumps({"seq": seq, "at": at, "kind": kind, "payload": payload},
                      ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(("%s\0%s" % (prev, body)).encode("utf-8")).hexdigest()


def append(kind: str = "", payload=None, **_kw) -> dict:
    """追加一条**签名记录**。账面只增不删。"""
    if not str(kind or "").strip():
        return {"ok": False, "fail_closed": True, "error": "kind 要给（事件类型）"}
    if not isinstance(payload, dict):
        return {"ok": False, "fail_closed": True, "error": "payload 要是对象（dict）"}
    try:
        key = _key()
    except RuntimeError as e:
        return {"ok": False, "fail_closed": True, "error": str(e)}
    rows = _rows()
    prev = rows[-1]["hash"] if rows else "GENESIS"
    at = time.strftime("%Y-%m-%dT%H:%M:%S")
    seq = len(rows) + 1
    h = _body_hash(prev, kind, payload, at, seq)
    sig = _hmac.new(key, h.encode("utf-8"), hashlib.sha256).hexdigest()
    row = {"seq": seq, "at": at, "kind": kind, "payload": payload,
           "prev": prev, "hash": h, "sig": sig}
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True, "op": "append", "seq": seq, "hash": h[:16], "kind": kind}


def verify(**_kw) -> dict:
    """全链校验：逐条重算 hash + sig + prev；**定位第一条被改的**，之后的全部连坐。"""
    try:
        key = _key()
    except RuntimeError as e:
        return {"ok": False, "fail_closed": True, "error": str(e)}
    rows = _rows()
    prev, first_bad = "GENESIS", None
    for r in rows:
        h = _body_hash(prev, r.get("kind") or "", r.get("payload") or {},
                       r.get("at") or "", r.get("seq") or 0)
        sig = _hmac.new(key, h.encode("utf-8"), hashlib.sha256).hexdigest()
        if r.get("hash") != h or r.get("sig") != sig or r.get("prev") != prev:
            first_bad = r.get("seq")
            break
        prev = r.get("hash")
    return {"ok": first_bad is None, "op": "verify", "rows": len(rows),
            "first_bad_seq": first_bad,
            "verdict": ("全链一致（%d 条）" % len(rows)) if first_bad is None
                       else "**第 %s 条起被改过**（它之后的每一条都连坐）" % first_bad,
            "_口径": "逐条重算 hash+sig+prev；定位到第一条被改的（不是含糊地说账脏了）"}


def tail(n: int = 10, **_kw) -> dict:
    rows = _rows()[-int(n):]
    return {"ok": True, "op": "tail", "rows": [{"seq": r.get("seq"), "at": r.get("at"),
                                                "kind": r.get("kind"),
                                                "payload": r.get("payload")} for r in rows],
            "count": len(rows)}


def status(**_kw) -> dict:
    rows = _rows()
    kinds: dict = {}
    for r in rows:
        kinds[r.get("kind")] = kinds.get(r.get("kind"), 0) + 1
    return {"ok": True, "op": "status", "rows": len(rows), "kinds": kinds,
            "key_on_disk": _KEY.is_file()}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "event_ledger", "tentacle": "event_ledger",
            "entry": "run_task('event_ledger', {...})",
            "ops": ["append", "verify", "tail", "status", "where"],
            "distilled_from": "2026-09-28 主人给的周榜卡 buzz（block/buzz · Rust · 34,934★）"
                              "——只取**账本纪律**（每条消息都是签名记录）",
            "not_copied": "不引它的 Nostr 中继/网络面（出网归门与它自己的闸）；"
                          "人机同室协作仍走 collab_gateway——本件只管账本真伪",
            "hard_rules": ["无明文钥匙：HMAC 钥匙随机生成 + DPAPI 落盘（复用仓内 deepseek_key 帮手）",
                           "成链：改任意一条，它之后每一条 hash 都对不上 ⇒ 定位第一条被改的",
                           "只增不删：本件没有删除/改写路径（作废走 append retract）",
                           "DPAPI 不可用 ⇒ fail-closed，不降级成'不签也收'"],
            "files": {"事件账": str(_LEDGER.relative_to(_ROOT)),
                      "钥匙(DPAPI)": str(_KEY.relative_to(_ROOT))},
            "contract": [
                {"op": "append", "params": "kind + payload(dict)", "returns": "seq + hash[:16]"},
                {"op": "verify", "params": "—", "returns": "全链校验（定位第一条被改的）"},
                {"op": "tail", "params": "[n]", "returns": "最近 n 条"},
            ]}


def run_op(op: str = "status", **params) -> dict:
    op = (op or "status").lower()
    for name, fn in (("append", append), ("verify", verify), ("tail", tail),
                     ("status", status), ("where", where)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（append/verify/tail/status/where）"}


if __name__ == "__main__":                                    # 主人的终端入口
    import argparse
    ap = argparse.ArgumentParser(description="签名事件账（buzz 架构蒸馏 · 只取账本纪律）")
    ap.add_argument("cmd", nargs="?", default="status")
    ap.add_argument("--kind", default="")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    if a.cmd == "append":
        print(json.dumps(run_op("append", kind=a.kind, payload={"note": a.note}),
                         ensure_ascii=False, indent=1))
    else:
        print(json.dumps(run_op(a.cmd), ensure_ascii=False, indent=1))
