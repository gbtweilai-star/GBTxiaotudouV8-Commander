# -*- coding: utf-8 -*-
"""把 Arm B 契约落进镜像副本 api_mirror.py（生产 api.py 一行不动）。"""
import ast
import os
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = r"gbt_allinone\api.py"
DST = r".scratch\codex_v2_mirror\api_mirror.py"
lines = open(SRC, encoding="utf-8").read().splitlines()

# ---------- 锚点校验 ----------
assert "官方 Codex 能力化" in lines[483], repr(lines[483])
assert "codex_interrupt" in lines[485], repr(lines[485])
assert lines[494].strip() == "return _CB.get_shared_server().start_thread()", repr(lines[494])
assert lines[499].strip().startswith("return _CB.get_shared_server().steer("), repr(lines[499])
assert lines[49].startswith("def _run_benign("), repr(lines[49])
print("anchors OK")

# ---------- Hunk B：codex 分支重组装 ----------
new_branch = '''
    # ── 官方 Codex 能力化（B 档 · 注册与路由是同一个原子单元，一次落地）──
    if kind in ("codex_status", "codex_tools", "codex_thread_new",
                "codex_turn_send", "codex_interrupt"):
        from . import codex_bridge as _CB
        p = payload or {}
        if kind == "codex_status":
            return _CB.status()
        if kind == "codex_tools":
            return {"ok": True, "tools": [t.get("name") for t in _CB.dynamic_tool_specs()]}
        thread_id = str(p.get("thread_id") or "").strip()
        if kind == "codex_thread_new":
            # thread/start 只认白名单（app-server v2 无 effort），effort 显式拒绝 + 落审计；
            # 盲传会在出网前一帧都发不出就 TypeError，并被上层 except 静默降级。
            return _CB.get_shared_server().start_thread(**_codex_thread_params(p, kind))
        if not thread_id:
            raise ValueError("缺少 thread_id：请先调用 codex_thread_new")
        if kind == "codex_turn_send":
            return _CB.get_shared_server().start_turn(
                thread_id, str(p.get("text") or ""), effort=p.get("effort"))
        return _CB.get_shared_server().interrupt(thread_id, p.get("turn_id"))
'''.strip("\n").splitlines()
lines[483:500] = new_branch

# ---------- Hunk A：白名单常量 + 告警 helper ----------
helper = '''
# codex thread/start 的官方 Schema（app-server v2）参数白名单：effort 只属于 turn/start。
CODEX_THREAD_PARAMS = ("model", "sandbox", "approval_policy", "approvals_reviewer",
                       "developer_instructions", "base_instructions", "ephemeral",
                       "runtime_workspace_roots", "dynamic_tools")


def _codex_thread_params(payload, kind):
    """thread/start 白名单透传；effort 显式拒绝并落审计，不再盲传导致静默降级。"""
    params = {k: payload[k] for k in CODEX_THREAD_PARAMS if k in payload}
    if "effort" in payload:
        audit("codex_param_deprecated", {
            "kind": kind,
            "param": "effort",
            "raw_value": payload.get("effort"),
            "type": type(payload.get("effort")).__name__,
            "note": "thread/start（app-server v2）无 effort；已拒绝下发，"
                    "推理强度请放到 codex_turn_send",
        })
    return params
'''.strip("\n").splitlines()
lines[49:49] = helper + [""]

text = "\n".join(lines) + "\n"
ast.parse(text)
open(DST, "w", encoding="utf-8", newline="\n").write(text)
print("mirror written:", DST, os.path.getsize(DST), "B; PARSE_OK")
print("branch now at line", [i + 1 for i, ln in enumerate(lines) if "codex_thread_new" in ln][:3])
