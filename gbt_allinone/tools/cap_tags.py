# gbt-capability: cap_tags
"""GBT 技能标签 + 主人许可门（主人令 2026-09-27）。

主人原话：「将**所有的原生能力注册出专属的 GBT 技能标签**，**只有我允许了才能调用我的能力**。」

## 两件事，拆开说清

1. **专属标签**：每个能力位一个稳定标签 `GBT-<域>-<能力位>`（域大写、能力位原名大写，`domain:llm`
   这类域标签写成 `GBT-DOMAIN-LLM-*`）。标签是**从注册表现算的**，不是手抄清单 —— 新增能力位
   自动就有标签（配 `tools/binding_hook.py` 的新增钩子）。
2. **调用许可**：标签带一个**权限类**，来源是**框架自己的判据**，不是我手写的名单：
   - `policy.evaluate(kind, {op})` 逐 op 问出**要哪些作用域**（唯一真相仍在 `security/policy.py`）；
   - 叠加图鉴里既有的声明（`safe` / `needs_confirmation`）；
   - 读不出来 ⇒ **一律按 `owner` 处理**（**默认严**，不许"读不到就当开放"）。
   - `open`：读类，随便调；`owner`：**只有主人允许了才能调**。

## 许可怎么发（我只能给命令，不能自己发）

- 主人手写 `store/owner_permits.jsonl`（一行一条，格式见下），或
- 终端跑 `python -m gbt_allinone.tools.cap_tags permit --tag GBT-CREATION-LOBEHUB --ttl 600`，
  它**要求 TTY + 手打 YES**（非交互会话直接拒 —— AI 拿不到 TTY，也就**发不出许可**）。

```jsonl
{"tag": "GBT-CREATION-LOBEHUB", "ttl": 600, "by": "owner", "at": "2026-09-27T23:00:00"}
```

op=tags / check / permits / how / audit / verify / where
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_STATE = _ROOT / "state"
_TAGS = _STATE / "cap_tags.json"
_LEDGER = _STATE / "cap_tags.jsonl"
_PERMITS = _ROOT / "gbt_allinone" / "store" / "owner_permits.jsonl"
_OPEN, _OWNER = "open", "owner"


def _caps() -> dict:
    try:
        sys.path.insert(0, str(_ROOT))
        from gbt_allinone.caps_registry import BENIGN_CAPS
        return dict(BENIGN_CAPS)
    except ImportError:
        return {}


def _policy():
    try:
        from ..security import policy as P
        return P
    except ImportError:
        sys.path.insert(0, str(_ROOT))
        from gbt_allinone.security import policy as P      # type: ignore
        return P


def _ops_of(kind: str, spec: dict) -> list:
    """图鉴/注册表里写的 op 清单（`op=a/b/c` 形状）；没写就给几个通用动作名去问。"""
    hint = str(spec.get("params_hint") or "")
    m = re.search(r"op=([A-Za-z0-9_|/,]+)", hint)
    ops = [x.strip() for x in re.split(r"[/,|]", m.group(1)) if x.strip()] if m else []
    # 再补几个"一定会被问"的动作名，避免 op 清单写得少就漏判
    for probe in ("write", "set", "launch", "submit", "remember", "provision", "run", "delete"):
        if probe not in ops:
            ops.append(probe)
    return ops[:24]


def tag_of(kind: str, spec: dict | None = None) -> str:
    d = str((spec or _caps().get(kind) or {}).get("domain") or "misc").upper()
    return "GBT-%s-%s" % (re.sub(r"[^0-9A-Za-z]+", "-", d).strip("-"), kind.upper().replace("_", "-"))


def _classify(kind: str, spec: dict) -> dict:
    """权限类：**默认严**（读不出来就是 owner）。"""
    P = _policy()
    scopes: list = []
    for op in _ops_of(kind, spec):
        try:
            d = P.evaluate(kind, {"op": op})
            for s in (getattr(d, "scopes", ()) or ()):
                if s not in scopes:
                    scopes.append(s)
        except Exception as exc:                               # noqa: BLE001
            return {"permission": _OWNER, "scopes": [],
                    "why": f"问不出作用域（{type(exc).__name__}: {str(exc)[:80]}）⇒ 按 owner 处理",
                    "unknown": True}
    safe = spec.get("safe") is True
    conf = bool(spec.get("needs_confirmation"))
    if scopes or conf or not safe:
        why = []
        if scopes:
            why.append("policy 要求作用域：" + "、".join(scopes))
        if conf:
            why.append("图鉴标了 needs_confirmation")
        if not safe:
            why.append("图鉴标了 safe=false")
        return {"permission": _OWNER, "scopes": scopes, "why": "；".join(why)}
    return {"permission": _OPEN, "scopes": [], "why": "policy 无作用域 + 图鉴 safe 且无需确认"}


def tags(**_kw) -> dict:
    """现算全部专属标签 → state/cap_tags.json（生成物，随注册表变）。"""
    caps = _caps()
    out = {}
    for kind, spec in caps.items():
        c = _classify(kind, spec)
        out[kind] = {"tag": tag_of(kind, spec), "domain": spec.get("domain"),
                     "permission": c["permission"], "scopes": c["scopes"], "why": c["why"]}
    by_perm = {}
    for v in out.values():
        by_perm[v["permission"]] = by_perm.get(v["permission"], 0) + 1
    dup = {}
    for v in out.values():
        dup[v["tag"]] = dup.get(v["tag"], 0) + 1
    dup = {k: n for k, n in dup.items() if n > 1}
    doc = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "count": len(out),
           "by_permission": by_perm, "duplicate_tags": dup, "tags": out,
           "_口径": "标签=从注册表现算；权限类=policy.evaluate 逐 op 问作用域 + 图鉴声明；**读不到就是 owner**"}
    _TAGS.parent.mkdir(parents=True, exist_ok=True)
    tmp = _TAGS.with_name(_TAGS.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, _TAGS)
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": doc["at"], "event": "tags", **by_perm}, ensure_ascii=False) + "\n")
    return {"ok": True, "op": "tags", "count": len(out), "by_permission": by_perm,
            "duplicate_tags": dup, "file": str(_TAGS.relative_to(_ROOT))}


def _permits() -> dict:
    """读主人发的许可（**只读**：本能力没有任何写它的代码 —— 见 how）。"""
    now = time.time()
    live, expired, bad = [], [], []
    if not _PERMITS.is_file():
        return {"exists": False, "live": [], "expired": 0, "bad": 0}
    for i, ln in enumerate(_PERMITS.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            bad.append(i)
            continue
        exp = r.get("expires_at")
        if exp is None and r.get("ttl"):
            exp = r.get("at_ts") or now
            exp = float(exp) + float(r["ttl"])
        if exp is None:
            exp = now + 600          # 没写就按默认 10 分钟窗口
        if float(exp) > now:
            live.append({**r, "expires_at": float(exp), "left_s": int(float(exp) - now)})
        else:
            expired.append(r.get("tag") or r.get("kind"))
    return {"exists": True, "live": live, "expired": len(expired), "bad": len(bad)}


def check(kind: str = "", op: str = "", **_kw) -> dict:
    """这个能力位现在能不能调？—— 只读判定，**不消耗任何授权**。"""
    if not kind:
        return {"ok": False, "op": "check", "fail_closed": True, "error": "要给 kind"}
    caps = _caps()
    spec = caps.get(kind)
    if spec is None:
        return {"ok": False, "op": "check", "fail_closed": True,
                "error": f"没这个能力位：{kind}", "known": len(caps)}
    c = _classify(kind, spec)
    tag = tag_of(kind, spec)
    pm = _permits()
    have = [p for p in pm["live"] if (p.get("tag") or p.get("kind")) in (tag, kind)]
    allowed = c["permission"] == _OPEN or bool(have)
    out = {"ok": True, "op": "check", "kind": kind, "tag": tag,
           "permission": c["permission"], "scopes": c["scopes"], "why": c["why"],
           "allowed": allowed, "permits_live": len(have),
           "how_to_permit": (f"主人终端：python -m gbt_allinone.tools.cap_tags permit --tag {tag} --ttl 600"
                             if not allowed else ""),
           "_口径": "owner 类**默认拒绝**，只有主人发的许可（store/owner_permits.jsonl）能开；AI 无自发权限"}
    return out


def how(**_kw) -> dict:
    """许可怎么发（我给命令，**发不了**）。"""
    return {"ok": True, "op": "how",
            "文件": str(_PERMITS.relative_to(_ROOT)),
            "一行一条": '{"tag": "GBT-CREATION-LOBEHUB", "ttl": 600, "by": "owner"}',
            "终端命令": "python -m gbt_allinone.tools.cap_tags permit --tag <TAG> --ttl 600",
            "硬口径": ("本能力的代码里**没有任何写 owner_permits.jsonl 的路径**；"
                       "终端命令要求 TTY + 手打 YES ⇒ **非交互会话（AI）发不出许可**"),
            "issuers": ["主人手写文件", "主人终端交互确认"],
            "ai_can_issue": False}


def permits(**_kw) -> dict:
    """看现在有哪些许可（只读，掩掉正文只留标签/剩余秒数）。"""
    pm = _permits()
    return {"ok": True, "op": "permits", "exists": pm["exists"],
            "live": [{k: v for k, v in p.items() if k in ("tag", "kind", "ttl", "by", "left_s")}
                     for p in pm["live"]],
            "expired": pm["expired"], "bad_lines": pm["bad"], "ai_can_issue": False,
            "how_to": how()["终端命令"]}


def audit(**_kw) -> dict:
    """审计：哪些 `owner` 类能力位**现在没有许可**（= 主人没允许就谁都别调）。"""
    if not _TAGS.is_file() or json.loads(_TAGS.read_text(encoding="utf-8")).get("at") is None:
        tags()
    doc = json.loads(_TAGS.read_text(encoding="utf-8"))
    pm = _permits()
    live = {(p.get("tag") or p.get("kind")) for p in pm["live"]}
    owner_caps = {k: v for k, v in doc["tags"].items() if v["permission"] == _OWNER}
    no_permit = sorted(k for k, v in owner_caps.items() if v["tag"] not in live and k not in live)
    with_permit = sorted(k for k, v in owner_caps.items() if k not in no_permit)
    return {"ok": True, "op": "audit", "owner_class": len(owner_caps),
            "with_permit": with_permit, "without_permit": len(no_permit),
            "without_permit_sample": no_permit[:8],
            "note": ("`open` 类不受影响；`owner` 类**没许可就不许调**。"
                     "这份清单也是给主人的**待批列表**（要开哪个就发哪个标签的许可）"),
            "_口径": "许可是**时段窗**：TTL 到点自动失效，不用手动撤"}


def verify(**_kw) -> dict:
    problems = []
    if not _TAGS.is_file():
        problems.append("没有标签表（先跑 tags）")
        return {"ok": False, "op": "verify", "problems": problems}
    doc = json.loads(_TAGS.read_text(encoding="utf-8"))
    caps = _caps()
    miss = [k for k in caps if k not in (doc.get("tags") or {})]
    if miss:
        problems.append(f"**{len(miss)} 个能力位没有专属标签**（例：{miss[:4]}）")
    if len(doc.get("tags") or {}) < len(caps):
        problems.append("标签数少于能力位数 ⇒ 有漏")
    if doc.get("duplicate_tags"):
        problems.append(f"标签撞车：{doc['duplicate_tags']}")
    if not any(v["permission"] == _OWNER for v in (doc.get("tags") or {}).values()):
        problems.append("一个 owner 类都没有 ⇒ 权限分类可疑（默认应当是严的）")
    pm = _permits()
    if pm.get("bad"):
        problems.append(f"许可文件有 {pm['bad']} 行读不动 ⇒ 修掉（宁可重发也不要含糊）")
    # 硬口径（**结构性**，不是"有没有出现"）：写许可只允许**一处**，且必须在
    # `sys.stdin.isatty()` 闸**之后** —— 非交互会话永远走不到那一行 ⇒ AI 发不出许可。
    # 早先这条只查"代码里有没有写"，把主人终端那条合法路径也判红了（判据自己先假红）。
    src = Path(__file__).read_text(encoding="utf-8")
    writes = [m.start() for m in re.finditer(r'open\(_PERMITS\s*,\s*"a"', src)]
    if not writes:
        problems.append("许可只读不写？那主人也没法发 —— 少了唯一那条 TTY 写入路径")
    elif len(writes) > 1:
        problems.append(f"写许可的路径有 {len(writes)} 处 ⇒ 只许 1 处（其余都是旁路）")
    else:
        fn = src[src.find("def permit("):]
        nxt = fn.find("\ndef ", 1)
        fn = fn[:nxt] if nxt > 0 else fn
        i_guard, i_write = fn.find("isatty"), fn.find("open(_PERMITS")
        if i_guard == -1 or i_write == -1 or i_guard > i_write:
            problems.append("写许可的那一行**不在 isatty 闸之后** ⇒ AI 可自批，立刻改")
    return {"ok": not problems, "op": "verify", "problems": problems,
            "counts": {"caps": len(caps), "tags": len(doc.get("tags") or {}),
                       **doc.get("by_permission", {})},
            "permits_exists": pm.get("exists", False),
            "_口径": "标签齐 + 分类非空 + 许可文件可读 + **没有自批路径**"}


def permit(tag: str = "", ttl: int = 600, **_kw) -> dict:
    """发许可 —— **只在主人终端**（TTY + 手打 YES）能跑；非交互会话直接拒。"""
    if not tag:
        return {"ok": False, "op": "permit", "fail_closed": True, "error": "要给 --tag"}
    if not sys.stdin.isatty():
        return {"ok": False, "op": "permit", "denied": True, "fail_closed": True,
                "error": "**非交互会话不许发许可**（AI 永远无权给自己发授权）",
                "how": "请主人在终端跑；或手写 gbt_allinone/store/owner_permits.jsonl"}
    print(f"即将给 {tag} 发 {ttl}s 的调用许可。输入 YES 确认：", end=" ", flush=True)  # noqa: T201
    if (sys.stdin.readline() or "").strip() != "YES":
        return {"ok": False, "op": "permit", "error": "没确认 ⇒ 不发"}
    _PERMITS.parent.mkdir(parents=True, exist_ok=True)
    row = {"tag": tag, "ttl": int(ttl), "by": "owner", "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "at_ts": time.time()}
    with open(_PERMITS, "a", encoding="utf-8") as fh:      # 只有走到 TTY 确认才会执行到这里
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": row["at"], "event": "permit", "tag": tag, "ttl": int(ttl)},
                            ensure_ascii=False) + "\n")
    return {"ok": True, "op": "permit", "tag": tag, "ttl": int(ttl), "file": str(_PERMITS)}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "cap_tags", "tentacle": "cap_tags",
            "entry": "run_task('cap_tags', {...})",
            "ops": ["tags", "check", "permits", "how", "audit", "verify", "where", "permit"],
            "tag_shape": "GBT-<域大写>-<能力位大写，下划线转横线>",
            "permission_classes": {_OPEN: "读类：policy 无作用域 + 图鉴 safe → 随便调",
                                   _OWNER: "**只有主人允许了才能调**（默认严：读不出来也是 owner）"},
            "permit_file": str(_PERMITS.relative_to(_ROOT)),
            "ai_can_issue": False,
            "contract": [
                {"op": "tags", "returns": "count + by_permission + 每个能力位的标签/权限类/作用域"},
                {"op": "check", "params": "kind", "returns": "allowed + how_to_permit"},
                {"op": "audit", "returns": "owner 类里现在没许可的清单（= 待批列表）"},
            ]}


def run_op(op: str = "tags", **params) -> dict:
    op = (op or "tags").lower()
    for name, fn in (("tags", tags), ("check", check), ("permits", permits), ("how", how),
                     ("audit", audit), ("verify", verify), ("where", where), ("permit", permit)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（tags/check/permits/how/audit/verify/where/permit）"}


if __name__ == "__main__":                                     # 主人的终端入口
    import argparse
    ap = argparse.ArgumentParser(description="GBT 能力标签与调用许可（只有主人能发许可）")
    ap.add_argument("cmd", nargs="?", default="verify")
    ap.add_argument("--tag", default="")
    ap.add_argument("--ttl", type=int, default=600)
    a = ap.parse_args()
    print(json.dumps(run_op(a.cmd, tag=a.tag, ttl=a.ttl), ensure_ascii=False, indent=1))
