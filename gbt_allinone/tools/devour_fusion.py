# gbt-capability: devour_fusion
"""吞天 × 原生能力 融合台账（主人令 2026-09-27）。

主人原话：「把**蒸馏提炼出契合自己的原生能力**和**吞天**融合到一起，让触手的吞天拥有永久记忆 Obsidian，
以及**记入能力**。」

## 融合的判据：吞进来的东西必须**三件齐**才算"融合"，否则只是"见过"

| 件 | 判据 | 为什么 |
|---|---|---|
| ① **原生位** | 有对应能力位，且**三处齐**（注册表 / api 分派 / 图鉴） | 吞了却不接线 = 见过没用过（本仓老账） |
| ② **触手** | 归到一根**有效触手标签**（能绑、能用） | 没触手 = 谁都够不着 |
| ③ **永久记忆** | 触手库里有一页记着它（Obsidian），且**链回本体** | 没记 = 下次还得重新吞一遍 |

`intake` 登记、`audit` 逐条查这三件、`fuse` 把缺的记忆页补齐（调用 `obsidian_vault.remember`）。

**诚实标注（2026-10-13 更新 · 2026-10-17 现读翻正）**：图片里那三个开源件已**真吞**
（`devour_github` 落胶囊，不必先装上）——`Windows-MCP` / `CyberStrike` 另蒸出原生位
（`desktop_distill` / `pentest_distill`）⇒ `已融合`。
🔴 2026-10-17 现读翻正（留痕 · 原口径 / 为什么翻 / 现口径）：
  原句：「`DataEase` / `FreeCAD-MCP` 只落胶囊、还没蒸 ⇒ `已吸收`」。
  为什么翻：现读盘上，`bi_distill`（DataEase）/ `cad_distill`（FreeCAD-MCP）**已三处齐**
    （注册表 + 模块 + api 分派 + 图鉴，均实测 in_registry=True / module=1 / in_api=True / in_atlas=True）
    ⇒ 它们**也蒸出来了**，旧句过期；写「只落胶囊」反而是新的假话。
  现口径：四件一律以 `list` 从盘上**算出来的** `fused` 为准；状态只有
    `待吞`（没吞）/ `已融合`（三件齐、算得出来）两种真值，`已吸收` 仅作历史中间态保留。
状态一律以 `list` **从盘上算出来的** `fused` 为准，不看台账里写的字。

op=intake / list / audit / fuse / verify / where
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_STATE = _ROOT / "state"
_LEDGER = _STATE / "devour_fusion.jsonl"
_VIEW = _STATE / "devour_fusion.json"

STATUSES = ("待吞", "已吸收", "已融合")


def _caps() -> dict:
    try:
        sys.path.insert(0, str(_ROOT))
        from gbt_allinone.caps_registry import BENIGN_CAPS
        return dict(BENIGN_CAPS)
    except ImportError:
        return {}


def _labels() -> set:
    try:
        sys.path.insert(0, str(_ROOT))
        from gbt_allinone.caps_registry import BENIGN_CAPS
        doms = {str(v.get("domain") or "") for v in BENIGN_CAPS.values()} - {""}
        return set(BENIGN_CAPS) | {"domain:" + d for d in doms}
    except ImportError:
        return set()


def _three_places(kind: str) -> dict:
    reg = (_ROOT / "gbt_allinone" / "caps_registry.py").read_text(encoding="utf-8")
    api = (_ROOT / "gbt_allinone" / "api.py").read_text(encoding="utf-8")
    atlas = _STATE / "skill_atlas.json"
    in_atlas = False
    if atlas.is_file():
        try:
            in_atlas = kind in {c["kind"] for c in json.loads(atlas.read_text(encoding="utf-8"))["caps"]}
        except (json.JSONDecodeError, KeyError):
            in_atlas = False
    return {"registry": f'"{kind}"' in reg, "api": f'kind == "{kind}"' in api, "atlas": in_atlas}


def _vault_has_note(tentacle: str, name: str) -> bool:
    """触手库里有没有那一页（查索引 + 盘上文件）。"""
    idx = _STATE / "obsidian_vaults.json"
    if not idx.is_file():
        return False
    try:
        d = json.loads(idx.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    meta = (d.get("vaults") or {}).get(tentacle)
    if not meta:
        return False
    import re
    safe = re.sub(r"[^0-9A-Za-z_\u4e00-\u9fff-]+", "-", tentacle).strip("-")
    p = Path(meta["dir"]) / f"{name}.md"
    if p.is_file():
        return True
    mem = Path(meta["dir"]) / "记忆.md"
    return mem.is_file() and name in mem.read_text(encoding="utf-8", errors="replace")


def _rows() -> list:
    out = []
    if _LEDGER.is_file():
        for ln in _LEDGER.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    # 台账是追加式的：同 id 取最后一条
    latest = {}
    for r in out:
        if r.get("event") in ("intake", "status") and r.get("id"):
            latest[r["id"]] = r
    return [latest[k] for k in sorted(latest)]


def _log(row: dict) -> None:
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row}, ensure_ascii=False) + "\n")


def intake(id: str = "", source: str = "", native_cap: str = "", tentacle: str = "",
           status: str = "待吞", note: str = "", **_kw) -> dict:
    """登记一次吞入。**不要求三件齐就能登记**（承认"刚吞进来还没接线"），
    但 `status` 只能写 `待吞`；写成 `已融合` 必须三件齐 —— 假账在这里就拦下。"""
    if not id or not source:
        return {"ok": False, "op": "intake", "fail_closed": True, "error": "id 与 source 都要给"}
    if status not in STATUSES:
        return {"ok": False, "op": "intake", "fail_closed": True, "error": f"status 只能是 {STATUSES}"}
    if status == "已融合":
        miss = []
        if not native_cap or not all(_three_places(native_cap).values()):
            miss.append(f"原生位没三处齐（{native_cap or '未给'}）")
        if not tentacle or tentacle not in _labels():
            miss.append(f"触手无效（{tentacle or '未给'}）")
        if tentacle and not _vault_has_note(tentacle, native_cap or id):
            miss.append("触手库里没有这一页（永久记忆缺件）")
        if miss:
            return {"ok": False, "op": "intake", "refused": True, "id": id, "status": status,
                    "missing": miss, "why": "**三件齐才算融合**：少一件只能记 `待吞`",
                    "hint": "补齐后重登；或先记 `已吸收`（接好线但还没进永久记忆）"}
    _log({"event": "intake", "id": id, "source": source[:200], "native_cap": native_cap,
          "tentacle": tentacle, "status": status, "note": note[:200]})
    return {"ok": True, "op": "intake", "id": id, "status": status,
            "native_cap": native_cap, "tentacle": tentacle}


def list(**_kw) -> dict:
    rows = _rows()
    out = []
    for r in rows:
        tp = _three_places(r.get("native_cap") or "")
        tent = r.get("tentacle") or ""
        out.append({**r, "three_places": tp,
                    "tentacle_valid": tent in _labels(),
                    "vault_note": _vault_has_note(tent, r.get("native_cap") or r.get("id") or "")
                    if tent else False})
    for r in out:
        r["fused"] = bool(all(r["three_places"].values()) and r["tentacle_valid"] and r["vault_note"])
    _VIEW.parent.mkdir(parents=True, exist_ok=True)
    tmp = _VIEW.with_name(_VIEW.name + ".tmp")
    tmp.write_text(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "rows": out},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, _VIEW)
    return {"ok": True, "op": "list", "count": len(out),
            "待吞": sum(1 for r in out if r.get("status") == "待吞"),
            "已吸收": sum(1 for r in out if r.get("status") == "已吸收"),
            "已融合": sum(1 for r in out if r["fused"]), "rows": out,
            "_口径": "**已融合 = 三件齐在盘上算出来的**，不看台账里写的 status（写的可以吹，算的不会）"}


def audit(**_kw) -> dict:
    """逐条查三件：缺哪件、怎么补。"""
    r = list()
    problems = []
    for row in r["rows"]:
        miss = []
        tp = row["three_places"]
        if not all(tp.values()):
            miss.append("原生位三处齐" + f"（缺：{[k for k, v in tp.items() if not v]}）")
        if not row["tentacle_valid"]:
            miss.append("有效触手标签")
        if not row["vault_note"]:
            miss.append("触手库里的永久记忆页")
        if miss:
            problems.append({"id": row.get("id"), "status": row.get("status"),
                             "missing": miss, "how": "补三件 → devour_fusion op=fuse / "
                                                     "binding_hook.py after-add"})
    return {"ok": not problems, "op": "audit", "count": len(r["rows"]),
            "not_fused": len(problems), "problems": problems[:20],
            "_口径": "没融合的**都要有名有姓**（id + 缺件 + 怎么补）"}


def fuse(id: str = "", **_kw) -> dict:
    """把缺的**永久记忆页**补齐（三件里的第三件）；前两件缺的话如实报缺，不假装。"""
    rows = [r for r in _rows() if not id or r.get("id") == id]
    if not rows:
        return {"ok": False, "op": "fuse", "error": f"没有这条吞入记录：{id or '（空）'}"}
    import importlib.util as _iu
    sp = _iu.spec_from_file_location("ov_fuse", _ROOT / "gbt_allinone" / "tools" / "obsidian_vault.py")
    ov = _iu.module_from_spec(sp)
    sp.loader.exec_module(ov)
    done, blocked = [], []
    for r in rows:
        tent, cap = r.get("tentacle") or "", r.get("native_cap") or ""
        tp = _three_places(cap) if cap else {}
        if not tent or tent not in _labels() or not cap or not all(tp.values()):
            blocked.append({"id": r.get("id"),
                            "missing": ([k for k, v in tp.items() if not v] if cap else []) +
                                       ([] if tent in _labels() else ["有效触手"]) +
                                       ([] if cap else ["原生位"]),
                            "how": "先把原生位接进三处（api 分派 + 图鉴）再回来 fuse"})
            continue
        txt = (f"**吞入**：{r.get('source')}\n\n"
               f"- 原生位：`{cap}`（三处齐）\n- 触手：`{tent}`\n"
               f"- 状态：{r.get('status')}\n- 备注：{r.get('note') or '（无）'}\n"
               f"- 来源：devour_fusion 台账 `{_LEDGER.name}`")
        out = ov.remember(tentacle=tent, text=txt, shared=True)
        (done if out.get("ok") else blocked).append({"id": r.get("id"), "vault": out.get("vault"),
                                                     "error": out.get("error")})
    _log({"event": "fuse", "done": len(done), "blocked": len(blocked)})
    return {"ok": bool(done) and not blocked, "op": "fuse", "fused": done, "blocked": blocked,
            "note": "补的是**永久记忆**那一件；前两件缺着就不会假装融合"}


def verify(**_kw) -> dict:
    problems = []
    r = list()
    if not r["rows"]:
        problems.append("吞入台账是空的 ⇒ 融合钩子没动过")
    for row in r["rows"]:
        if row.get("status") == "已融合" and not row["fused"]:
            problems.append(f"台账写 `已融合` 但三件不齐：{row.get('id')} ⇒ 假账，改回 `待吞`/`已吸收`")
    return {"ok": not problems, "op": "verify", "problems": problems,
            "counts": {"rows": r["count"], "待吞": r["待吞"], "已吸收": r["已吸收"],
                       "真融合": r["已融合"]},
            "_口径": "台账说的必须与盘上算的**对得上**（说融合了就得三件齐）"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "devour_fusion", "tentacle": "devour_fusion",
            "entry": "run_task('devour_fusion', {...})",
            "ops": ["intake", "list", "audit", "fuse", "verify", "where"],
            "三件": ["原生位（三处齐）", "有效触手标签", "触手库永久记忆页（链回本体）"],
            "files": {"台账": str(_LEDGER.relative_to(_ROOT)), "视图": str(_VIEW.relative_to(_ROOT))},
            "contract": [
                {"op": "intake", "params": "id + source [+ native_cap + tentacle]",
                 "returns": "登记；写 `已融合` 时三件不齐直接拒"},
                {"op": "audit", "returns": "未融合清单（缺哪件 + 怎么补）"},
                {"op": "fuse", "params": "id", "returns": "补永久记忆页"},
            ]}


def run_op(op: str = "list", **params) -> dict:
    op = (op or "list").lower()
    for name, fn in (("intake", intake), ("list", list), ("audit", audit), ("fuse", fuse),
                     ("verify", verify), ("where", where)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（intake/list/audit/fuse/verify/where）"}
