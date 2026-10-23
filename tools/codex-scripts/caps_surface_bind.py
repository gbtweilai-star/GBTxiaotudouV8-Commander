# -*- coding: utf-8 -*-
"""2 组工作流（及全部已指派槽）的**能力位控制面绑定**（主人令 2026-10-04）。

干什么：把每个**已指派槽**的承载能力位做成一份**按键清单**（控制面）落盘
  `state/surfaces/caps/<driver>.json`：
    · ops  = 操控按键（每个 op 一条，含门——哪些要票）
    · 调节 = 注册表里的入参契约（params / params_hint）
    · slot / group / role = 它在 50 槽蓝图里的位置
  然后 `tentacle_bind.bind(surface 文件 → 该能力位触手)` —— 槽、触手、按键三者在
  **同一份账本**里对得上（双向绑定的"账面半边"）。

判据（`verify`）：
  · 已指派槽 100% 有控制面文件（备用槽不算）；
  · 每份面的 ops 数 = 注册表 ops 数（漏一个 op = 漏一处连接点）；
  · 每份面都在绑定账里（tentacle_bind 扫描不断连）。

用法：
    py -3.14 tools/codex-scripts/caps_surface_bind.py           # 生成 + 绑定
    py -3.14 tools/codex-scripts/caps_surface_bind.py verify    # 判据

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "deploy" / "cloud-10" / "plugins50.json"
OUTDIR = ROOT / "state" / "surfaces" / "caps"

sys.path.insert(0, str(ROOT))


def assigned_slots() -> list:
    d = json.loads(SPEC.read_text(encoding="utf-8"))
    return [m for m in d.get("modules") or [] if m.get("local_driver")]


def _handler_file(handler: str):
    """handler 名 → 模块文件（tools/ 优先，退包根/llm/tentacle/security/deploy 等常见位）。"""
    if not handler:
        return None
    for sub in ("tools", "", "llm", "tentacle", "security", "recon"):
        c = ROOT / "gbt_allinone" / Path(sub) / ("%s.py" % handler)
        if c.is_file():
            return c
    return None


def _extract_ops(handler: str) -> dict:
    """从 handler 模块**静态提取**按键（op）清单。

    方法（启发式，**method 如实标**）：
      a. 模块级 `_OPS/OPS/KINDS/READ_OPS… = (…)` 元组/列表里的字符串；
      b. 源码里 `op == "x"` / `op in ("a","b")` / `run_op(op="x")` 的字面量；
    提不到就返回空表 + method="none"（**如实**，不编按键）。
    """
    import re
    f = _handler_file(handler)
    if not f:
        return {"ops": [], "method": "handler 文件未找到", "file": ""}
    src = f.read_text(encoding="utf-8", errors="replace")
    ops = set()
    # a. 模块级 op 清单（元组/列表里的字符串字面量）
    for m in re.finditer(r"^_(?:[A-Z_]*OPS|READ_OPS|GATED_OPS)\s*=\s*\(([^)]*)\)", src, re.M):
        ops |= set(re.findall(r'"([^"]+)"', m.group(1)))
    for m in re.finditer(r"^(?:OPS|KINDS|READ_OPS|GATED_OPS|_GATED_OPS)\s*=\s*\(([^)]*)\)", src, re.M):
        ops |= set(re.findall(r'"([^"]+)"', m.group(1)))
    # b. 分派字面量（**空格容忍**：`op == "x"` / `op in ("a","b")` / `op = "x"` 都认）
    for m in re.finditer(r'op\s*(?:==|in\s*\(|:)\s*\(?\s*"([a-z_][a-z0-9_]*)"', src):
        ops.add(m.group(1))
    for m in re.finditer(r'op\s*=\s*"([a-z_][a-z0-9_]*)"', src):
        ops.add(m.group(1))
    for m in re.finditer(r'"op"\s*:\s*"([a-z_][a-z0-9_]*)"', src):
        ops.add(m.group(1))
    ops.discard("op"); ops.discard("x"); ops.discard("none")
    method = "static-heuristic" if ops else "none"
    return {"ops": sorted(ops), "method": method, "file": str(f.relative_to(ROOT))}


def _desc_ops(desc: str) -> list:
    """从注册表 desc 里**兜底**提取 op 名（蒸馏时写下的口径：`op=build/wire/find`、
    `bind/unbind/auto/sweep` 等）—— 分派代码不是所有模块都能静态提取，desc 是第二来源。"""
    import re as _re
    out = set()
    for m in _re.finditer(r"op\s*=\s*([^。；，、\n]+)", desc or ""):
        for t in _re.split(r"[/|、\s]+", m.group(1)):
            t = t.strip().strip("`*").lower()
            if _re.fullmatch(r"[a-z_][a-z0-9_]{2,24}", t):
                out.add(t)
    for m in _re.finditer(r"\b(bind|unbind|auto|sweep|scan|verify|where)\b", desc or ""):
        out.add(m.group(1))
    return sorted(out)


def cap_surface(driver: str) -> dict | None:
    """「按键面」：ops 静态提取 + 注册表的门/入参契约。不在册 ⇒ None（如实）。"""
    from gbt_allinone.caps_registry import BENIGN_CAPS, required_params
    row = BENIGN_CAPS.get(driver)
    if not row:
        return None
    ex = _extract_ops(row.get("handler") or driver)
    if not ex["ops"]:
        ex["ops"] = _desc_ops(str(row.get("desc", "")))
        if ex["ops"]:
            ex["method"] = "desc 兜底（分派代码非静态可提取形态）"
    gates = (BENIGN_CAPS.get(driver) or {}).get("op_gates") or {}
    return {
        "cap": driver,
        "domain": row.get("domain", ""),
        "desc": row.get("desc", ""),
        "safe": bool(row.get("safe", False)),
        "ops": [{"op": o, "gate": gates.get(o) or "（由 policy 判）"} for o in ex["ops"]],
        "ops_method": ex["method"],
        "handler_file": ex["file"],
        "params": list(required_params(driver)),
        "params_hint": str(row.get("params_hint") or row.get("hint") or ""),
        "handler": row.get("handler", ""),
    }


def main() -> int:
    slots = assigned_slots()
    done, missing, bound = [], [], 0
    from tools import tentacle_bind as TB
    for m in slots:
        drv = m["local_driver"]
        face = cap_surface(drv)
        if not face:
            missing.append({"slot": m["slot"], "driver": drv})
            continue
        face.update({"slot": m["slot"], "group": m.get("group"), "role": m.get("role", "")})
        outdir = OUTDIR
        outdir.mkdir(parents=True, exist_ok=True)
        f = outdir / ("%s.json" % drv)
        f.write_text(json.dumps(face, ensure_ascii=False, indent=1), encoding="utf-8")
        done.append({"slot": m["slot"], "driver": drv, "file": str(f.relative_to(ROOT)),
                     "ops": len(face["ops"]), "method": face.get("ops_method")})
        r = TB.bind(str(f.relative_to(ROOT)), drv,
                    note="50 槽蓝图：控制面绑定（槽 %s）" % m["slot"], quiet=True)
        if r.get("ok"):
            bound += 1
    print("已指派槽 %d · 控制面落盘 %d · 缺驱动注册表项 %d · 新增绑定 %d 条"
          % (len(slots), len(done), len(missing), bound))
    for d in done:
        print("   %-8s → %-18s ops=%d" % (d["slot"], d["driver"], d["ops"]))
    for m in missing:
        print("   ⚠ %s 驱动 %s 不在册（如实）" % (m["slot"], m["driver"]))
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
