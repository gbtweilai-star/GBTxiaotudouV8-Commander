"""硬性规则钩子：**新增就触发双向绑定，并连通每一页的触手**（主人令 2026-09-27）。

主人原话：「以及**硬性规则钩子触发新增就触发双向绑定并且连接好每一页的触手**。」

## 为什么是钩子，不是一句规矩

规矩不会自己红。本仓的血账：`surface_bind` 的委托分支（comfyui/blender/lobehub）**清单写了却没绑触手** ——
"接上了没绑上"，谁都没发现，因为没人查。所以新增一件东西，必须**当场**把这六条腿走完，
走不完就**记红**：

| 腿 | 查什么 | 缺了怎么补 |
|---|---|---|
| ① 登记 | `caps_registry.py` 里有这个 kind | 加注册条目 |
| ② 分派 | `api.py` 有 `kind == "<kind>"` 分支 | 加分支（登记了却调不到 = 门看不见它） |
| ③ 图鉴 | `state/skill_atlas.json` 收录 | `omni.py build` |
| ④ 触手 | kind 是有效触手标签（能绑、能用） | 注册即自动成立（标签集 = 能力位 ∪ domain:*） |
| ⑤ 绑定 | 资产/清单绑到该触手（绑定账里查得到） | `surface_bind op=probe` 或 `tentacle_bind autobind` |
| ⑥ 记忆 | 触手库里有一页（永久记忆，链回本体） | `obsidian_vault op=provision/remember` |

用法：
    python tools/binding_hook.py after-add --kind <kind> [--tool <工具区名>]
    python tools/binding_hook.py sweep          # 自愈：给所有缺页/缺绑的能力位补上
    python tools/binding_hook.py verify         # 台账 + 现状复核（红了就说明有新增漏走钩子）
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
LEDGER = STATE / "binding_hook.jsonl"
ATLAS = STATE / "skill_atlas.json"
TOOLS_DIR = ROOT / "gbt_allinone" / "tools"


def _load(name: str, path: Path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def _caps() -> dict:
    sys.path.insert(0, str(ROOT))
    from gbt_allinone.caps_registry import BENIGN_CAPS
    return dict(BENIGN_CAPS)


def _labels() -> set:
    caps = _caps()
    doms = {str(v.get("domain") or "") for v in caps.values()} - {""}
    return set(caps) | {"domain:" + d for d in doms}


def _atlas_kinds() -> set:
    if not ATLAS.is_file():
        return set()
    try:
        return {c["kind"] for c in json.loads(ATLAS.read_text(encoding="utf-8"))["caps"]}
    except (json.JSONDecodeError, KeyError):
        return set()


def _bound_to(kind: str) -> list:
    """绑定账里有没有东西绑到这个触手（正向：资产→触手）。"""
    p = STATE / "asset_bindings.json"
    if not p.is_file():
        return []
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [k for k, v in d.items() if kind in ((v or {}).get("tentacles") or [])]


def _log(row: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row}, ensure_ascii=False) + "\n")


def _manifest_bound(tool: str) -> bool:
    """清单文件（`state/surfaces/<tool>.json` 或 `state/<tool>_surface.json`）在绑定账里吗。"""
    if not tool:
        return False
    led = STATE / "asset_bindings.json"
    if not led.is_file():
        return False
    try:
        d = json.loads(led.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    for cand in (STATE / "surfaces" / f"{tool}.json", STATE / f"{tool}_surface.json"):
        if cand.is_file() and str(cand.relative_to(ROOT)).replace("\\", "/") in d:
            return True
    return False


def legs(kind: str, tool: str = "") -> dict:
    """六条腿逐条查（只读）。"""
    caps = _caps()
    api = (ROOT / "gbt_allinone" / "api.py").read_text(encoding="utf-8")
    # ② 分派：**两种写法都算**（与 tools/framework_state.py 同一把尺，别各算各的）
    #    血账：我先前只认 `kind == "x"`，而 api.py 里大量能力位是**成组元组**写法
    #    （`if kind in ("redteam_recon", "pentest", "keylogger", …)`）⇒ 一口气假报 25 条"没分派"。
    dispatched = bool(re.search(r'kind\s*==\s*"%s"' % re.escape(kind), api)
                      or re.search(r'kind\s+in\s+\([^)]*"%s"' % re.escape(kind), api))
    out = {
        "①登记": kind in caps,
        "②分派": dispatched,
        "③图鉴": kind in _atlas_kinds(),
        "④触手": kind in _labels(),
        "⑤绑定": bool(_bound_to(kind)) or _manifest_bound(tool),
        "⑥记忆页": False,
    }
    # ⑥ 触手库有没有这一页（README + 记忆.md 都在，且库里认得它）
    idx = STATE / "obsidian_vaults.json"
    if idx.is_file():
        try:
            d = json.loads(idx.read_text(encoding="utf-8"))
            meta = (d.get("vaults") or {}).get(kind)
            if meta:
                mem = Path(meta["dir"]) / "记忆.md"
                out["⑥记忆页"] = (Path(meta["dir"]) / "README.md").is_file() and mem.is_file()
        except json.JSONDecodeError:
            pass
    return out


def after_add(kind: str = "", tool: str = "", fix: bool = True) -> dict:
    """新增一件东西之后**立刻**走完六条腿；缺的当场补（能补的），补不了记红。"""
    if not kind:
        return {"ok": False, "op": "after-add", "fail_closed": True, "error": "要给 --kind"}
    if kind not in _caps():
        return {"ok": False, "op": "after-add", "fail_closed": True,
                "error": f"{kind} 还没登记在 caps_registry ⇒ 先登记（钩子不替你造能力位）",
                "how": "加注册条目 + api.py 分派，再跑本钩子"}
    before = dict(legs(kind, tool))
    fixed = []
    # 补 ③ 图鉴
    if fix and not before["③图鉴"]:
        try:
            subprocess.run([sys.executable, str(ROOT / "tools" / "codex-scripts" / "omni.py"), "build"],
                           cwd=str(ROOT), capture_output=True, timeout=900)
            fixed.append("③图鉴：重建")
        except Exception as exc:                               # noqa: BLE001
            fixed.append(f"③图鉴：重建失败 {type(exc).__name__}")
    # 补 ⑥ 记忆页（触手库 + 记忆一条）
    if fix and not before["⑥记忆页"]:
        try:
            ov = _load("ov_hook", TOOLS_DIR / "obsidian_vault.py")
            r = ov.provision(only=kind)
            if r.get("ok"):
                fixed.append("⑥记忆页：建库")
            w = ov.remember(tentacle=kind,
                            text=f"**新增能力位** `{kind}`：钩子 `tools/binding_hook.py` 在新增时自动建页（{time.strftime('%Y-%m-%d')}）。")
            if w.get("ok"):
                fixed.append("⑥记忆页：记一条")
            ov.bind()
        except Exception as exc:                               # noqa: BLE001
            fixed.append(f"⑥记忆页：失败 {type(exc).__name__}: {str(exc)[:80]}")
    # 补 ⑤ 绑定（2026-10-13 机械加固：没有工具区清单时，绑**本位自己的产物**）
    # 病：原先只有 `tool` 给了才补 ⇒ 纯判据件永远 ⑤=false，靠人"记得"去 tentacle_bind.bind。
    if fix and not tool and not before["⑤绑定"]:
        # 2026-10-13 根因修：文档名是中文（蒸馏-X），按名字 glob 匹配不到 ⇒ 改成**按内容找**
        _docs = [p for p in sorted((ROOT / "docs").glob("*.md"))
                 if kind in p.name or kind in p.read_text(encoding="utf-8", errors="ignore")]
        for _a in [ROOT / "gbt_allinone" / "tools" / (kind + ".py")] + _docs:
            if _a.is_file():
                subprocess.run([sys.executable, str(ROOT / "tools" / "tentacle_bind.py"), "bind",
                                _a.relative_to(ROOT).as_posix(), kind],
                               cwd=str(ROOT), capture_output=True, timeout=120)
                fixed.append("⑤绑定：绑本位产物 " + _a.name)
    # 补 ⑤ 绑定（走工具区探针绑定清单）
    if fix and tool and not before["⑤绑定"]:
        try:
            sys.path.insert(0, str(ROOT))
            import gbt_allinone as g
            r = g.run_task("surface_bind", {"op": "probe", "tool": tool})
            fixed.append(f"⑤绑定：探针 bound={r.get('bound')}")
        except Exception as exc:                               # noqa: BLE001
            fixed.append(f"⑤绑定：失败 {type(exc).__name__}: {str(exc)[:80]}")
    after = legs(kind, tool)
    bad = [k for k, v in after.items() if k.startswith(("①", "②", "③", "④", "⑤", "⑥")) and not v]
    _log({"event": "after-add", "kind": kind, "tool": tool, "legs": after,
          "missing": bad, "fixed": fixed})
    return {"ok": not bad, "op": "after-add", "kind": kind, "tool": tool,
            "legs": after, "missing": bad, "fixed": fixed,
            "note": ("六条腿齐 ⇒ 双向绑定与触手页都在盘上"
                     if not bad else "**有腿没接上**：上面 missing 列表就是缺口（钩子已尽力补，剩下要人补）")}


def sweep() -> dict:
    """自愈：给所有能力位补齐触手页（每页触手都连通），缺清单绑定的报出来。"""
    ov = _load("ov_sweep", TOOLS_DIR / "obsidian_vault.py")
    st = ov.status()
    missing = st.get("missing_sample") or []
    r = ov.provision()
    b = ov.bind()
    v = ov.verify()
    no_bind = [k for k in _caps() if not _bound_to(k)]
    _log({"event": "sweep", "provisioned": r.get("made"), "skipped": r.get("skipped"),
          "verify_ok": v.get("ok"), "no_asset_binding": len(no_bind)})
    return {"ok": bool(r.get("ok")) and bool(v.get("ok")), "op": "sweep",
            "made": r.get("made"), "skipped": r.get("skipped"),
            "verify": v.get("ok"), "problems": v.get("problems")[:4],
            "no_asset_binding_sample": no_bind[:8],
            "note": ("每个能力位都有触手页了；`no_asset_binding` 是**还没有具体资产绑到它**的能力位"
                     "（读类能力位正常就没有资产，要资产的是产出型）"),
            "was_missing_sample": missing}


def verify() -> dict:
    """复核：台账非空 + 每个能力位六条腿都能过（漏走钩子的新增会在这里露出来）。"""
    problems = []
    caps = sorted(_caps())
    bad = {}
    for k in caps:
        L = legs(k)
        miss = [x for x, v in L.items() if x.startswith(("①", "②", "③", "④", "⑥")) and not v]
        if miss:
            bad[k] = miss
    if bad:
        problems.append(f"{len(bad)} 个能力位有腿没接上：{list(bad.items())[:4]}")
    rows = 0
    if LEDGER.is_file():
        rows = sum(1 for ln in LEDGER.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip())
    if not rows:
        problems.append("钩子台账是空的（一次都没跑过）")
    return {"ok": not problems, "op": "verify", "caps": len(caps), "bad": bad,
            "ledger_rows": rows, "problems": problems}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="硬性规则钩子：新增即触发双向绑定 + 连通每一页触手")
    ap.add_argument("cmd", nargs="?", default="verify",
                    choices=["after-add", "sweep", "verify", "legs"])
    ap.add_argument("--kind", default="")
    ap.add_argument("--tool", default="")
    ap.add_argument("--no-fix", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "after-add":
        r = after_add(kind=a.kind, tool=a.tool, fix=not a.no_fix)
    elif a.cmd == "legs":
        r = {"ok": True, "kind": a.kind, "legs": legs(a.kind, a.tool)}
    elif a.cmd == "sweep":
        r = sweep()
    else:
        r = verify()
    print(json.dumps(r, ensure_ascii=False, indent=1))          # noqa: T201
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
