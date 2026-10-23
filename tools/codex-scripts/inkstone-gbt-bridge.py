# -*- coding: utf-8 -*-
"""inkstone-gbt-bridge.py —— 把 GBT 全部能力位接进端砚（inkstone）的 Orbit MCP 宿主。

## 口径（Owner 2026-10-21 定：按域分组）
30 个域 → 30 个工具（`gbt_<域>`），工具内传 `capability` + `payload`；
另加 3 个通用口（`gbt_cap_list` / `gbt_cap_run` / `gbt_omni`）。
执行只走 GBT 唯一门 `tools/codex-scripts/five-dim.py cap <能力位>` —— 授权/审计/票留在 GBT，壳不越权。

## 用法
  py -3.14 tools/codex-scripts/inkstone-gbt-bridge.py            # 生成 + 登记 + 自检
  py -3.14 tools/codex-scripts/inkstone-gbt-bridge.py --check    # 只报域/能力位数
  py -3.14 tools/codex-scripts/inkstone-gbt-bridge.py --restore  # catalog 还原成装机原样
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = Path(__file__).resolve().parents[2]
PY = os.environ.get("GBT_PY", r"C:\Users\ADMIN\AppData\Roaming\uv\python\cpython-3.14.0-windows-x86_64-none\python.exe")
SCI = Path(r"C:\Program Files\inkstone\resources\science-mcp")
SCI_PY = Path(r"C:\Program Files\inkstone\resources\science-pack\python\python.exe")
PKG = SCI / "lib" / "mcp_gbt"
CATALOG = SCI / "catalog.json"
BACKUP = ROOT / "state" / "inkstone-catalog.orig.json"
ROSTER = ROOT / "state" / "caps-roster.json"
LINE = re.compile(r"^\s*-\s+(\S+)\s+\[([^\]]+)\]\s*(.*)$")


def roster() -> list:
    if ROSTER.is_file():
        return json.loads(ROSTER.read_text(encoding="utf-8"))
    r = subprocess.run([PY, "-m", "gbt_allinone", "list"], cwd=str(ROOT),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out, caps = (r.stdout or ""), []
    for ln in out.splitlines():
        m = LINE.match(ln)
        if m:
            caps.append({"name": m.group(1), "domain": m.group(2), "desc": m.group(3).strip()})
    seen, uniq = set(), []
    for c in caps:
        if c["name"] not in seen:
            seen.add(c["name"])
            uniq.append(c)
    ROSTER.parent.mkdir(parents=True, exist_ok=True)
    ROSTER.write_text(json.dumps(uniq, ensure_ascii=False, indent=1), encoding="utf-8")
    return uniq


def by_domain(caps: list) -> dict:
    d = {}
    for c in caps:
        d.setdefault(c["domain"], []).append((c["name"], c["desc"][:200]))
    return {k: sorted(v) for k, v in sorted(d.items())}


SERVER = '''# -*- coding: utf-8 -*-
"""mcp_gbt —— GBT小土豆V8 的**按域分组**MCP 工具，接进端砚（Orbit）。

**由 tools/codex-scripts/inkstone-gbt-bridge.py 生成，手改会被覆盖。**
生成时间 @@STAMP@@ · 域 @@NDOM@@ 个 · 能力位 @@NCAP@@ 个

每个 `gbt_<域>`：`capability`（留空=列该域能力位）+ `payload`（JSON 字符串）。
执行一律 `five-dim.py cap <能力位>`（GBT 唯一门）。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

GBT_ROOT = Path(os.environ.get("GBT_ROOT", r"@@ROOT@@"))
FIVE = GBT_ROOT / "tools" / "codex-scripts" / "five-dim.py"
PY = os.environ.get("GBT_PY", r"@@PY@@")
DOMAINS = @@DOMAINS@@


def _run(args, timeout=900):
    try:
        r = subprocess.run([PY] + args, cwd=str(GBT_ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except Exception as e:                                          # noqa: BLE001
        return {"ok": False, "why": "spawn_failed", "err": "%s: %s" % (type(e).__name__, str(e)[:300])}
    out = (r.stdout or "").strip()
    try:
        payload = json.loads(out[out.index("{"):]) if "{" in out else None
    except Exception:                                               # noqa: BLE001
        payload = None
    return {"ok": r.returncode == 0, "rc": r.returncode,
            "stdout": out[-6000:], "stderr": (r.stderr or "")[-2000:], "result": payload}


def _cap(cap, payload):
    return _run([str(FIVE), "cap", cap, payload or "{}"], timeout=900)


def _serve():
    from mcp.server.fastmcp import FastMCP
    srv = FastMCP("gbt-tudou")

    @srv.tool(name="gbt_cap_list", description="列出 GBT小土豆V8 全部能力位（按域分组，只读）")
    def gbt_cap_list() -> str:
        return json.dumps(DOMAINS, ensure_ascii=False)

    @srv.tool(name="gbt_cap_run", description="按名字调用任意 GBT 能力位（通用口；缺授权返回缺票原文）")
    def gbt_cap_run(capability: str, payload: str = "{}") -> str:
        return json.dumps(_cap(capability, payload), ensure_ascii=False)

    @srv.tool(name="gbt_omni", description="让 GBT 判断一句话该落在哪里（本地工具/能力位/agent 技能）")
    def gbt_omni(text: str) -> str:
        return json.dumps(_run([str(GBT_ROOT / "tools" / "codex-scripts" / "omni.py"), "ask", text], 300),
                          ensure_ascii=False)

    for dom, items in DOMAINS.items():
        names = [n for n, _ in items]
        desc = "、".join(names[:12]) + ("…" if len(names) > 12 else "")

        def _mk(dom=dom, names=names):
            def _t(capability: str = "", payload: str = "{}") -> str:
                if not capability:
                    return json.dumps({"domain": dom, "capabilities": names}, ensure_ascii=False)
                if capability not in names:
                    return json.dumps({"ok": False, "why": "cap_not_in_domain",
                                       "domain": dom, "valid": names}, ensure_ascii=False)
                return json.dumps(_cap(capability, payload), ensure_ascii=False)
            _t.__name__ = "gbt_" + str(dom)
            return _t
        srv.add_tool(_mk(), name="gbt_" + str(dom),
                     description="[%s] 域内 %d 个能力位：%s（参数 capability + payload）" % (
                         dom, len(names), desc))
    srv.run()


def main() -> None:
    try:
        _serve()
    except Exception as e:                                          # noqa: BLE001
        sys.stderr.write("[mcp-gbt] failed: %s: %s\\n" % (type(e).__name__, e))
        raise SystemExit(3)


if __name__ == "__main__":
    main()
'''


def write_server(caps: list) -> dict:
    doms = by_domain(caps)
    PKG.mkdir(parents=True, exist_ok=True)
    (PKG / "__init__.py").write_text("# GBT小土豆V8 转接包（server.py 由 inkstone-gbt-bridge.py 生成）\n",
                                     encoding="utf-8")
    src = SERVER
    for k, v in {"@@STAMP@@": time.strftime("%Y-%m-%dT%H:%M:%S"), "@@NDOM@@": str(len(doms)),
                 "@@NCAP@@": str(len(caps)), "@@ROOT@@": str(ROOT), "@@PY@@": PY,
                 "@@DOMAINS@@": json.dumps(doms, ensure_ascii=False)}.items():
        src = src.replace(k, v)
    (PKG / "server.py").write_text(src, encoding="utf-8")
    return {"server": str(PKG / "server.py"), "bytes": (PKG / "server.py").stat().st_size,
            "domains": len(doms), "caps": len(caps)}


def write_catalog(caps: list) -> dict:
    if not BACKUP.is_file():
        shutil.copyfile(CATALOG, BACKUP)
    data = [d for d in json.loads(BACKUP.read_text(encoding="utf-8"))
            if d.get("server") != "mcp_gbt"]
    doms = by_domain(caps)
    tools = [
        {"annotations": {"readOnlyHint": True},
         "description": "列出 GBT小土豆V8 全部能力位（按域分组，只读）",
         "inputSchema": {"type": "object", "properties": {}, "title": "gbt_cap_listArguments"},
         "name": "gbt_cap_list", "outputSchema": None, "title": "gbt_cap_list"},
        {"annotations": {"readOnlyHint": False},
         "description": "按名字调用任意 GBT 能力位（通用口；缺授权返回缺票原文）",
         "inputSchema": {"type": "object", "title": "gbt_cap_runArguments",
                         "properties": {"capability": {"type": "string"},
                                        "payload": {"type": "string", "default": "{}"}},
                         "required": ["capability"]},
         "name": "gbt_cap_run", "outputSchema": None, "title": "gbt_cap_run"},
        {"annotations": {"readOnlyHint": True},
         "description": "让 GBT 判断一句话该落在哪里（本地工具/能力位/agent 技能）",
         "inputSchema": {"type": "object", "title": "gbt_omniArguments",
                         "properties": {"text": {"type": "string"}}, "required": ["text"]},
         "name": "gbt_omni", "outputSchema": None, "title": "gbt_omni"},
    ]
    for dom, items in doms.items():
        names = [n for n, _ in items]
        tools.append({
            "annotations": {"readOnlyHint": False},
            "description": "[%s] 域内 %d 个能力位：%s（参数 capability + payload）" % (
                dom, len(names), "、".join(names[:12]) + ("…" if len(names) > 12 else "")),
            "inputSchema": {"type": "object", "title": "gbt_%sArguments" % dom,
                            "properties": {"capability": {"type": "string", "default": ""},
                                           "payload": {"type": "string", "default": "{}"}}},
            "name": "gbt_" + dom, "outputSchema": None, "title": "gbt_" + dom,
        })
    data.append({"implementation": {"icons": None, "name": "gbt-tudou", "title": "GBT小土豆V8",
                                    "version": "3.0.0", "websiteUrl": None},
                 "server": "mcp_gbt", "tools": tools})
    CATALOG.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return {"catalog": str(CATALOG), "servers": len(data), "tools": len(tools), "backup": str(BACKUP)}


def selftest(probe_dom: str, probe_cap: str) -> dict:
    req = "\n".join([
        '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"0"}}}',
        '{"jsonrpc":"2.0","method":"notifications/initialized"}',
        '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}',
        '{"jsonrpc":"2.0","id":9,"method":"tools/call","params":{"name":"gbt_%s","arguments":{"capability":"%s","payload":"{}"}}}'
        % (probe_dom, probe_cap)])
    r = subprocess.run([str(SCI_PY), str(SCI / "run_server.py"), "mcp_gbt"], input=req,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    names, call = [], None
    for ln in (r.stdout or "").splitlines():
        if '"id":2' in ln and '"tools"' in ln:
            try:
                names = [t["name"] for t in json.loads(ln[ln.index("{"):])["result"]["tools"]]
            except Exception:                                       # noqa: BLE001
                pass
        if '"id":9' in ln:
            call = ln[ln.index("{"):][:700]
    return {"tools": len(names), "sample": names[:10], "call": call,
            "ok": bool(names) and call is not None and '"ok": true' in (call or ""),
            "stderr": (r.stderr or "")[-200:]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--restore", action="store_true")
    a = ap.parse_args()
    if a.restore:
        if not BACKUP.is_file():
            print(json.dumps({"ok": False, "why": "no_backup", "path": str(BACKUP)}, ensure_ascii=False))
            return 2
        shutil.copyfile(BACKUP, CATALOG)
        print(json.dumps({"ok": True, "restored": str(CATALOG)}, ensure_ascii=False))
        return 0
    caps = roster()
    doms = by_domain(caps)
    if a.check:
        print(json.dumps({"caps": len(caps), "domains": len(doms),
                          "domain_tools": {k: len(v) for k, v in doms.items()}},
                         ensure_ascii=False, indent=1))
        return 0
    rep = {"server": write_server(caps), "catalog": write_catalog(caps)}
    probe = "system" if "system" in doms else next(iter(doms))
    names = [n for n, _ in doms[probe]]
    probe_cap = "health" if "health" in names else names[0]
    rep["probe"] = {"domain": probe, "capability": probe_cap}
    rep["selftest"] = selftest(probe, probe_cap)
    rep["ok"] = bool(rep["selftest"]["ok"])
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0 if rep["ok"] else 5


if __name__ == "__main__":
    sys.exit(main())
