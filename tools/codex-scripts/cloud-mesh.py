"""10 云插件拼接网 · 生成 / 漂移核对 / 边读数（形态 A 单 isolate + 形态 B 服务绑定）。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 它管什么
主人 2026-09-25 令「不需要部署在本地，直接部署在云插件上以模块化部署，再进行 10 插件拼接运行」。
这句话要落成可核对的东西，只有一个办法：**把接线写成表，把表生成成件，把件跟表对账**。

- 单一真源：`deploy/cloud-10/mesh.json`（10 模块 · 每位要过哪些门 · 形态口径）
- 生成物：`src/mesh.generated.js`（运行时读的接线表）
  与 `modules/<id>/`（形态 B：10 个独立 Worker，每位 9 条服务绑定）
- 对账：`check` 逐字段比，漂移就点名；不许「表改了件没改」还报绿。

## 口径（写死在工具里）
- **插件是接线不是算力**：90 条有向边是接线读数，不是算力读数。
- **真共享 CPU 只有形态 A**（10 模块同一 isolate）；形态 B 是真互通、各算各的。
- **门表是单一真源**：每个 op 该过哪个作用域写在 `mesh.json` 的 `op_gates` 里，
  代码里不许再藏一套 if；`none` 与 15 条作用域之外的值一律判红。
- **10 是主人的口径**（主人要 10 个），所以模块数按 10 判；**边数不写死**，由模块数现算。

用法：
  python tools/codex-scripts/cloud-mesh.py gen      [--root deploy/cloud-10] [--check-only]
  python tools/codex-scripts/cloud-mesh.py check
  python tools/codex-scripts/cloud-mesh.py edges
  python tools/codex-scripts/cloud-mesh.py selftest
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

MESH_REL = "deploy/cloud-10/mesh.json"
GEN_REL = "deploy/cloud-10/src/mesh.generated.js"

# 15 个可授权作用域（与 gbt_allinone/security/auth_gate.py 的 SCOPES 同名同数；
# 本工具只做「门名合法性」核对，不代替那道门）
SCOPES = (
    "filesystem_read", "filesystem_write", "process_execute", "network_read",
    "network_write", "external_llm", "privacy_read", "audio_output",
    "browser_control", "device_control", "deploy_publish", "data_export",
    "pipeline_submit", "audit_read", "owner_control",
)

MODULES_EXPECTED = 10  # 主人的口径：10 个云插件

# 验收工具自报的身份（见 http_json 的注释：默认 UA 会被平台挡成 403）
UA = "gbt-mesh-acceptance/1.0 (+https://gbt-potato-cloud-10.lopaycn.workers.dev)"

GEN_BANNER = (
    "// 本文件由 tools/codex-scripts/cloud-mesh.py gen 生成 —— 不要手改。\n"
    "// 单一真源：deploy/cloud-10/mesh.json（改表再 gen；check 会抓漂移）\n"
    "// 开发者：自由的风 · 守护者：公主土豆\n"
)


class MeshError(Exception):
    """真源本身不合格。"""


# ── 纯函数：读表 → 模型 ─────────────────────────────────────────────────────
def validate(mesh: dict) -> list:
    """把真源的问题逐条列出来；空列表 = 表合格。**不改表、不写盘。**"""
    bad = []
    mods = mesh.get("modules")
    if not isinstance(mods, list):
        return ["modules 不是列表"]

    if len(mods) != MODULES_EXPECTED:
        bad.append(f"模块数 {len(mods)} ≠ 主人的口径 {MODULES_EXPECTED}")

    seqs = [m.get("seq") for m in mods]
    if seqs != list(range(1, len(mods) + 1)):
        bad.append(f"seq 不是 1..{len(mods)} 连续：{seqs}")

    ids = [m.get("id") for m in mods]
    if len(set(ids)) != len(ids):
        bad.append("模块 id 有重复")
    for i in ids:
        if not isinstance(i, str) or not i.startswith("gbt-c"):
            bad.append(f"id 命名不合规：{i!r}")

    labels = [m.get("owner_label") for m in mods]
    if len(set(labels)) != len(labels):
        bad.append("主人给的名字有重复")

    for m in mods:
        ops = m.get("ops")
        gates = m.get("op_gates")
        mid = m.get("id")
        if not isinstance(ops, list) or not ops:
            bad.append(f"{mid}: ops 空或不是列表")
            continue
        if not isinstance(gates, dict):
            bad.append(f"{mid}: 缺 op_gates 门表")
            continue
        miss = [o for o in ops if o not in gates]
        extra = [k for k in gates if k not in ops]
        if miss:
            bad.append(f"{mid}: 这些 op 没写门 → {miss}")
        if extra:
            bad.append(f"{mid}: op_gates 里有不存在的 op → {extra}")
        for o, g in gates.items():
            if g != "none" and g not in SCOPES:
                bad.append(f"{mid}.{o}: 门名不在 15 条里 → {g!r}")

    for key in ("form", "edges", "owner_label_reality", "account"):
        if key not in mesh:
            bad.append(f"真源缺字段：{key}")
    if not (mesh.get("doctrine") or mesh.get("_doctrine")):
        bad.append("真源缺字段：doctrine（或 _doctrine）")

    ed = mesh.get("edges") or {}
    exp = MODULES_EXPECTED * (MODULES_EXPECTED - 1)
    if ed.get("directed_expected") != exp:
        bad.append(f"edges.directed_expected 应为 {exp}，现为 {ed.get('directed_expected')}")
    if ed.get("undirected_expected") != exp // 2:
        bad.append(f"edges.undirected_expected 应为 {exp // 2}")
    if ed.get("self_loop_expected") != 0:
        bad.append("edges.self_loop_expected 应为 0")
    return bad


def build_model(mesh: dict) -> dict:
    """合格的真源 → 运行时模型（含每位绑其余 9 位推出来的 peers）。**纯函数。**"""
    bad = validate(mesh)
    if bad:
        raise MeshError("；".join(bad))
    ids = [m["id"] for m in mesh["modules"]]
    peers = {i: [x for x in ids if x != i] for i in ids}
    return {
        "form": mesh["form"],
        "form_note": mesh.get("form_note", ""),
        "doctrine": mesh.get("doctrine") or mesh.get("_doctrine") or [],
        "owner_labels": {m["id"]: m["owner_label"] for m in mesh["modules"]},
        "modules": [
            {
                "seq": m["seq"],
                "id": m["id"],
                "owner_label": m["owner_label"],
                "duty": m["duty"],
                "ops": m["ops"],
                "op_gates": m["op_gates"],
                "cloud": m["cloud"],
                "boundary": m.get("boundary", ""),
            }
            for m in mesh["modules"]
        ],
        "ids": ids,
        "peers": peers,
        "edges": mesh["edges"],
        "accounts": mesh.get("account", {}),
        "reality": mesh.get("owner_label_reality", {}),
    }


def edge_report(ids: list, peers: dict) -> dict:
    """**纯函数**：按 ids/peers 现算边读数；90/45 这些数一个都不写死。"""
    directed = [(a, b) for a in ids for b in peers.get(a, [])]
    keys = {f"{a}>{b}" for a, b in directed}
    self_loops = [f"{a}>{b}" for a, b in directed if a == b]
    asym = [f"{a}>{b}" for a, b in directed if f"{b}>{a}" not in keys]
    n = len(ids)
    return {
        "modules": n,
        "directed": len(directed),
        "undirected_expected": len(directed) // 2,
        "per_module": {a: len(peers.get(a, [])) for a in ids},
        "self_loops": self_loops,
        "asymmetric": asym,
        "expected_directed": n * (n - 1),
        "expected_per_module": n - 1,
        "ok": len(directed) == n * (n - 1) and not self_loops and not asym,
    }


def unresolved_imports(path: Path) -> list:
    """**纯函数**：列出这个 JS 件里指不到的相对 import。

    这是「装到云上一加载就崩」的那类错：路径少一级，本机看不出来，云端第一次请求就炸。
    裸包名不算（那是 Node/打包器的活）；只看 `./` 与 `../` 开头的。
    """
    if not path.exists():
        return [f"未读到 {path.name}"]
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("import "):
            continue
        m = re.search(r'from "([^"]+)"', line)
        if m and m.group(1).startswith("."):
            if not (path.parent / m.group(1)).resolve().exists():
                out.append(m.group(1))
    return out


def deploy_config_guards(deploy_toml: str, dev_toml: str) -> list:
    """**纯函数**：部署配置上的两条护栏。

    ① 部署配置里**不许出现 D1 绑定** —— 主人账号那 4 个库都是别的用途
       （orders / caps / wallet），往里建我们的表 = 把主人的库弄脏；
       真要 D1 得主人点头新建一个。② 本地验收配置**必须**带 D1（否则 07 号的落点验不了），
       并且要显式标"禁止部署"，免得哪天被拿去 deploy。
    """
    bad = []
    if "[[" + "d1_databases" + "]]" in deploy_toml and not all(
        ln.lstrip().startswith("#") for ln in deploy_toml.splitlines() if "[[" + "d1_databases" + "]]" in ln
    ):
        bad.append("部署配置里出现了 D1 绑定（现有 4 个库都是主人别的用途）⇒ 要么删掉，要么先请主人新建一个")
    if "禁止" not in dev_toml and "不许" not in dev_toml:
        bad.append("本地验收配置没写「禁止部署」标记 ⇒ 容易被误用")
    if "[[d1_databases]]" not in dev_toml:
        bad.append("本地验收配置缺 D1 ⇒ 07 号的落点验不了")
    return bad


def import_problems(out_root: Path) -> dict:
    """**纯函数**：生成树里每一个 JS 件的相对 import 是否都指得到。空字典 = 全指得到。"""
    bad = {}
    for p in sorted(out_root.rglob("*.js")) if out_root.exists() else []:
        miss = unresolved_imports(p)
        if miss:
            bad[str(p.relative_to(out_root)).replace("\\", "/")] = miss
    return bad


# ── 渲染：模型 → 件 ────────────────────────────────────────────────────────
def render_generated_js(model: dict) -> str:
    payload = {
        "form": model["form"],
        "form_note": model["form_note"],
        "doctrine": model["doctrine"],
        "modules": model["modules"],
        "edges": model["edges"],
        "owner_labels": model["owner_labels"],
        "accounts": model["accounts"],
        "reality": model["reality"],
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False)
    ids = json.dumps(model["ids"], ensure_ascii=False)
    peers = json.dumps(model["peers"], ensure_ascii=False, indent=2, sort_keys=False)
    gates = {m["id"]: m["op_gates"] for m in model["modules"]}
    return (
        GEN_BANNER
        + f"export const MESH = {body};\n\n"
        + f"export const MODULE_IDS = {ids};\n\n"
        + f"export const PEERS = {peers};\n\n"
        + "export const OP_GATES = "
        + json.dumps(gates, ensure_ascii=False, indent=2)
        + ";\n"
    )


def render_module_worker(model: dict, mid: str) -> str:
    """形态 B 单模块 Worker：只挂自己那一位，与其余 9 位走服务绑定。"""
    seq = next(m["seq"] for m in model["modules"] if m["id"] == mid)
    peer_seqs = [m["seq"] for m in model["modules"] if m["id"] != mid]
    peer_bindings = [f"PEER_{s:02d}" for s in peer_seqs]
    return f"""// 形态 B · 单模块 Worker：{mid}（第 {seq} 号）
// 生成物，不要手改。真源：deploy/cloud-10/mesh.json
// 口径：本形态 = 真互通、各算各的（isolate 之间不共享 CPU）。
// 路径口径：件在 deploy/cloud-10/modules/<id>/src/index.js ⇒ 公共件在 ../../../src/
import {{ MODULES, createState }} from "../../../src/modules.js";
import {{ MESH, OP_GATES }} from "../../../src/mesh.generated.js";

const ID = {json.dumps(mid)};
const PEER_BINDINGS = {json.dumps(peer_bindings)};

export default {{
  async fetch(request, env) {{
    const url = new URL(request.url);
    if (url.pathname === "/health") {{
      const state = createState();
      const ops = MODULES[ID].ops;
      const body = ops.status ? await ops.status({{ env, state, self: ID }}) : {{ op: "ping", module: ID }};
      return Response.json({{ module: ID, seq: {seq}, ok: true, body, peers_bound: PEER_BINDINGS.filter((b) => env[b]).length, peers_declared: PEER_BINDINGS.length }});
    }}
    if (url.pathname === "/peers") {{
      const bound = PEER_BINDINGS.filter((b) => env[b]);
      const rows = [];
      for (const b of bound) {{
        try {{
          const r = await env[b].fetch("https://peer/health");
          rows.push({{ binding: b, ok: r.ok }});
        }} catch (e) {{
          rows.push({{ binding: b, ok: false, error: String(e && e.message || e) }});
        }}
      }}
      return Response.json({{ module: ID, declared: PEER_BINDINGS.length, bound: bound.length, reached: rows.filter((r) => r.ok).length, rows }});
    }}
    const parts = url.pathname.split("/").filter(Boolean);
    if (parts[0] === "rpc" && parts.length >= 3 && parts[1] === ID) {{
      const state = createState();
      const op = parts[2];
      const gate = (OP_GATES[ID] || {{}})[op] || "none";
      if (gate !== "none") {{
        return Response.json({{ denied: true, missing_scopes: [gate], note: "形态 B 的门在 09 号那位身上；本单模块件不自带授权。" }}, {{ status: 403 }});
      }}
      const fn = MODULES[ID].ops[op];
      if (!fn) return Response.json({{ error: "unknown op", op }}, {{ status: 404 }});
      let args = {{}};
      try {{ args = await request.json(); }} catch (e) {{}}
      return Response.json(await fn({{ env, state, self: ID }}, args));
    }}
    return Response.json({{ module: ID, seq: {seq}, routes: ["GET /health", "GET /peers", "POST /rpc/{mid}/<op>"] }});
  }},
}};
"""


def render_module_wrangler(model: dict, mid: str) -> str:
    """形态 B 的 wrangler：自家 name + 其余 9 条服务绑定（Cloudflare 原生的 worker 间通道）。"""
    lines = [
        f"# 形态 B · {mid}（生成物，不要手改）",
        f'name = "{mid}"',
        'main = "src/index.js"',
        'compatibility_date = "2025-01-01"',
        "",
    ]
    for peer in model["ids"]:
        if peer == mid:
            continue
        seq = next(m["seq"] for m in model["modules"] if m["id"] == peer)
        lines += [
            "[[services]]",
            f'binding = "PEER_{seq:02d}"',
            f'service = "{peer}"',
            "",
        ]
    return "\n".join(lines)


def expected_files(model: dict) -> dict:
    """**纯函数**：模型 → {相对 deploy/cloud-10 的路径: 内容}。供 gen 与 selftest 共用。"""
    files = {"src/mesh.generated.js": render_generated_js(model)}
    for m in model["modules"]:
        mid = m["id"]
        files[f"modules/{mid}/wrangler.toml"] = render_module_wrangler(model, mid)
        files[f"modules/{mid}/src/index.js"] = render_module_worker(model, mid)
        files[f"modules/{mid}/package.json"] = json.dumps(
            {
                "name": mid,
                "private": True,
                "type": "module",
                "version": "0.1.0",
                "description": f"{m['duty']}（主人给的对应名：{m['owner_label']}）",
                "_generated": "tools/codex-scripts/cloud-mesh.py gen",
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n"
    return files


# ── 命令 ───────────────────────────────────────────────────────────────────
def load_mesh(mesh_path: Path) -> dict:
    try:
        return json.loads(mesh_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise MeshError(f"未读到真源：{mesh_path}")
    except json.JSONDecodeError as e:
        raise MeshError(f"真源不是合法 JSON：{e}")


def cmd_gen(as_json: bool, check_only: bool, mesh_path=None, out_root=None, quiet: bool = False) -> int:
    mesh_path = Path(mesh_path) if mesh_path else ROOT / MESH_REL
    out_root = Path(out_root) if out_root else ROOT / "deploy" / "cloud-10"
    try:
        mesh = load_mesh(mesh_path)
        model = build_model(mesh)
    except MeshError as e:
        print(f"真源不合格 ⇒ 拒绝生成：{e}")
        return 2

    files = expected_files(model)
    er = edge_report(model["ids"], model["peers"])
    drift = []
    missing = []
    written = 0
    for rel, content in files.items():
        p = out_root / rel
        if not p.exists():
            # 🔴 缺件 ≠ 内容漂移：一个读不到、一个读到了但不是这份。
            #    两者混成一个数，排查时就会把「还没生成」念成「被人改过」。
            missing.append(rel)
        old = p.read_text(encoding="utf-8") if p.exists() else None
        if old == content:
            continue
        if check_only:
            drift.append(rel)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8", newline="\n")
            written += 1

    # 表里声明存在、盘上多余的件
    declared = {f"modules/{m['id']}" for m in model["modules"]}
    mods_dir = out_root / "modules"
    if mods_dir.exists() and not check_only:
        for d in mods_dir.iterdir():
            if d.is_dir() and f"modules/{d.name}" not in declared:
                shutil.rmtree(d)
                written += 1

    bad_imports = import_problems(out_root)
    deploy_toml = (out_root / "wrangler.toml").read_text(encoding="utf-8") if (out_root / "wrangler.toml").exists() else ""
    dev_toml = (out_root / "wrangler.dev.toml").read_text(encoding="utf-8") if (out_root / "wrangler.dev.toml").exists() else ""
    guards = deploy_config_guards(deploy_toml, dev_toml) if deploy_toml else []
    out = {
        "mesh": str(mesh_path),
        "modules": len(model["ids"]),
        "edges": er,
        "files_expected": len(files),
        "files_written": written,
        "files_missing": missing,
        "reading": "未读到" if missing else "已读到",
        "drift": drift,
        "import_problems": bad_imports,
        "config_guards": guards,
        "ok": not drift and not bad_imports and not guards,
        "mode": "check-only" if check_only else "gen",
    }
    if quiet:
        return 0 if out["ok"] else 1
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"真源：{MESH_REL}")
        print(f"模块 {out['modules']} · 声明有向边 {er['directed']}（应 {er['expected_directed']}）· 每位绑 {er['expected_per_module']} 位")
        print(f"形状核对：{'过' if er['ok'] else '不过'} · 自环 {len(er['self_loops'])} · 不对称 {len(er['asymmetric'])}")
        print(f"相对 import 指不到：{len(bad_imports)} 件" + ("（" + "、".join(list(bad_imports)[:4]) + "）" if bad_imports else ""))
        if guards:
            print(f"配置护栏：{len(guards)} 条不过")
            for g in guards:
                print("    ✗ " + g)
        else:
            print("配置护栏：过（部署配置无 D1 绑定 · 本地验收配置带 D1 且标了禁止部署）")
        if missing:
            print(f"缺件：{len(missing)} 件（未读到）" + ("（" + "、".join(missing[:4]) + "）" if missing else ""))
        if check_only:
            print(f"漂移：{len(drift)} 件" + ("（" + "、".join(drift[:6]) + "）" if drift else ""))
        else:
            print(f"生成：写 {written} 件 / 共 {len(files)} 件")
    return 0 if out["ok"] else 1


def cmd_check(as_json: bool) -> int:
    return cmd_gen(as_json=as_json, check_only=True)


# ── 云侧现读（只读：查版本 / 查身份 / 查已有资源 / 数模板里没落的地方）──────
PLACEHOLDER_RE = re.compile(r"<未配：([^>]*)>")


def count_placeholders(text: str, active_only: bool = True) -> list:
    """**纯函数**：模板里还剩几处没落。返回占位符里的说明文字。

    `active_only=True` 时**跳过注释行**：注释里的占位符是说明，不是没落 ——
    两者混着数，就会把"已经能部署"念成"还不能"，或者反过来。
    """
    out = []
    for line in (text or "").splitlines():
        if active_only and line.lstrip().startswith("#"):
            continue
        out.extend(m.strip() for m in PLACEHOLDER_RE.findall(line))
    return out


def count_placeholders_all(text: str) -> dict:
    """**纯函数**：生效处与注释处分开数，两个读数都要报。"""
    return {
        "active": count_placeholders(text, active_only=True),
        "commented": [m for m in count_placeholders(text, active_only=False) if m not in count_placeholders(text, active_only=True)],
    }


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def mask_identity(s: str) -> str:
    """**纯函数**：账号/邮箱一律只留前几位。凭据永远不进输出。

    判「是不是邮箱」用**整串匹配**，不用「串里有没有那个符号」——
    后者会把任何含该符号的串都当邮箱，是典型的**判据量错对象**。
    """
    s = (s or "").strip()
    if not s:
        return "未读到"
    if EMAIL_RE.match(s):
        local, _, dom = s.partition("@")
        return (local[:3] + "***@" + dom) if len(local) > 3 else ("***@" + dom)
    return (s[:4] + "****") if len(s) > 4 else "****"


def run_wrangler(args: list, timeout: float = 90.0) -> dict:
    """跑一条 wrangler 命令（**只许读**：list/whoami/--version）。失败一律记未读到。"""
    exe = shutil.which("wrangler.cmd") or shutil.which("wrangler") or "wrangler"
    try:
        p = subprocess.run([exe] + list(args), capture_output=True, text=True, timeout=timeout, shell=False, encoding="utf-8", errors="replace")
        return {"rc": p.returncode, "out": p.stdout or "", "err": p.stderr or "", "exe": exe}
    except Exception as e:  # FileNotFoundError / TimeoutExpired / ...
        return {"rc": None, "out": "", "err": f"{type(e).__name__}: {e}", "exe": exe}


def parse_list(kind: str, out: str) -> dict:
    """**纯函数**：把 wrangler 的 list 输出解析成条数+名字；解析不了就记未读到，不写 0。"""
    out = out or ""
    names = []
    if kind == "kv":
        try:
            data = json.loads(out)
            names = [d.get("title") for d in data if isinstance(d, dict)]
        except Exception:
            return {"count": None, "names": [], "reading": "未读到"}
    elif kind == "r2":
        names = [ln.split(":", 1)[1].strip() for ln in out.splitlines() if ln.strip().startswith("name:")]
    elif kind == "d1":
        for ln in out.splitlines():
            if ln.startswith("│") and "│" in ln[1:]:
                cells = [c.strip() for c in ln.strip("│").split("│")]
                if len(cells) >= 2 and cells[0] and not cells[0].startswith("uuid") and set(cells[0]) != {"─"}:
                    names.append(cells[1])
    else:
        return {"count": None, "names": [], "reading": "未读到"}
    return {"count": len(names), "names": names, "reading": "已读到"}


def readiness_verdict(template_text: str, who_out: str, inventory: dict, live: bool = True, caveat_src: dict = None) -> dict:
    """**纯函数**：把「能不能部署」这个判决从读数里分出来。

    为什么要抽出来：判决里有两条**诚实分支**（身份未读到 / 资源未读到）——
    它们原来长在联网命令里，**自检走不到**（未验分支棘轮点了名，点得对）。
    抽成纯函数后，两条分支各能被一条负控**真触发**。
    """
    ph_all = count_placeholders_all(template_text or "")
    ph = ph_all["active"]
    blockers = []
    if ph:
        blockers.append(f"wrangler.toml 生效处还有 {len(ph)} 个占位符没落")
    logged_in = bool(who_out) and "You are logged in" in who_out
    if not logged_in:
        blockers.append("Cloudflare 身份未读到（OAuth 未登录或取不到）")
    if live:
        for k in ("kv", "r2", "d1"):
            if (inventory or {}).get(k, {}).get("count") in (None, 0):
                blockers.append(f"{k} 资源未读到 ⇒ 该绑定现在挂不上")

    caveats = []
    for m in (caveat_src or {}).get("modules", []):
        if m.get("id") == "gbt-c01-llm-gateway":
            caveats.append("01 号：" + m.get("boundary", ""))
        elif m.get("id") in ("gbt-c03-uncensored-lane", "gbt-c06-tool-shell", "gbt-c07-memory-vector", "gbt-c10-observability"):
            caveats.append(f"{m.get('seq', 0):02d} 号：" + (m.get("cloud_fallback") or m.get("boundary", "")))

    return {
        "template": {"path": "deploy/cloud-10/wrangler.toml", "placeholders_active": len(ph), "active_items": ph[:12], "placeholders_commented": len(ph_all["commented"])},
        "logged_in": logged_in,
        "blockers": blockers,
        "deployable_now": not blockers,
        "caveats": caveats,
    }


def cmd_readiness(as_json: bool, do_live: bool = True) -> int:
    tmpl = ROOT / "deploy" / "cloud-10" / "wrangler.toml"
    text = tmpl.read_text(encoding="utf-8") if tmpl.exists() else ""
    try:
        raw_mesh = load_mesh(ROOT / MESH_REL)
        caveat_src = {"modules": raw_mesh["modules"]}
    except MeshError:
        caveat_src = {}

    ver = run_wrangler(["--version"]) if do_live else {"rc": None, "out": "", "err": "skip"}
    version = (ver.get("out") or "").strip().splitlines()[-1] if ver.get("out") else "未读到"
    who = run_wrangler(["whoami"]) if do_live else {"rc": None, "out": "", "err": "skip"}
    who_out = who.get("out") or ""
    email = ""
    acct = ""
    mm = re.search(r"associated with the email\s+(\S+)", who_out)
    if mm:
        email = mm.group(1)
    mm2 = re.search(r"│\s*([0-9a-f]{32})\s*│", who_out)
    if mm2:
        acct = mm2.group(1)
    scopes = sorted(set(re.findall(r"^- ([a-z_\-\.]+)", who_out, re.M)))

    inv = {}
    if do_live:
        for kind, args in (("kv", ["kv", "namespace", "list"]), ("r2", ["r2", "bucket", "list"]), ("d1", ["d1", "list"])):
            r = run_wrangler(args)
            parsed = parse_list(kind, r.get("out") or "")
            if parsed["count"] is None and r.get("rc") not in (0, None):
                parsed = {"count": None, "names": [], "reading": "未读到"}
            inv[kind] = {**parsed, "rc": r.get("rc")}

    # 判决走纯函数（两条诚实分支在那里，自检能真触发）
    v = readiness_verdict(text, who_out, inv, live=do_live, caveat_src=caveat_src)
    v["template"]["active_items"]

    out = {
        "wrangler": {"path": ver.get("exe"), "version": version, "rc": ver.get("rc")},
        "auth": {"logged_in": v["logged_in"], "identity": mask_identity(email), "account": mask_identity(acct), "rc": who.get("rc"), "scopes_seen": len(scopes), "scopes": scopes[:24]},
        "inventory": inv,
        "template": v["template"],
        "deployable_now": v["deployable_now"],
        "blockers": v["blockers"],
        "caveats": v["caveats"],
        "boundary": [
            "只读：本命令只跑 --version / whoami / list，不建资源、不部署、不改远端。",
            "有资源 ≠ 已接线：真 deploy 之后才算挂上绑定。",
            "可部署 ≠ 已部署：deploy 会在主人账号里建一个 Worker，那是真改远端，要主人点头。",
            "部署后仍要另量真读数（身份漂移/拒答率/遥测/装机验收），形状验收不顶替。",
        ],
    }
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print("10 云插件拼接网 · 云侧现读（只读）")
        print(f"  wrangler ：{version}  ({out['wrangler']['path']})")
        print(f"  身份     ：{'已登录' if out['auth']['logged_in'] else '未登录'} · {out['auth']['identity']} · 账号 {out['auth']['account']} · 作用域 {out['auth']['scopes_seen']} 条")
        for k in ("kv", "r2", "d1"):
            row = inv.get(k) or {}
            print(f"  {k:<9}：{row.get('reading', '未读到')} · 条数 {row.get('count')} · {', '.join((row.get('names') or [])[:6])}")
        print(f"  模板占位 ：生效处 {v['template']['placeholders_active']} 个 · 注释处 {v['template']['placeholders_commented']} 个（注释的是说明，不是没落）")
        print(f"  现在可部署：{'是' if out['deployable_now'] else '否'}")
        for b in out["blockers"]:
            print(f"    ✗ {b}")
        for c in out["caveats"]:
            print(f"    ! 已知缺口 {c}")
        for b in out["boundary"]:
            print("  · " + b)
    return 0


def cmd_edges(as_json: bool) -> int:
    try:
        model = build_model(load_mesh(ROOT / MESH_REL))
    except MeshError as e:
        print(f"真源不合格：{e}")
        return 2
    er = edge_report(model["ids"], model["peers"])
    if as_json:
        print(json.dumps(er, ensure_ascii=False, indent=2))
        return 0 if er["ok"] else 1
    print("10 云插件拼接网 · 边读数（现算，不写死）")
    print(f"  形态：{model['form']} —— {model['form_note']}")
    for i in model["ids"]:
        seq = next(m["seq"] for m in model["modules"] if m["id"] == i)
        print(f"  {seq:>2} 号 {i:<26} 绑 {er['per_module'][i]} 位")
    print(f"  有向边合计 {er['directed']}（应 {er['expected_directed']}）· 无向对 {er['undirected_expected']}")
    print(f"  自环 {len(er['self_loops'])} · 不对称 {len(er['asymmetric'])} ⇒ {'过' if er['ok'] else '不过'}")
    print("  边界：这是接线读数，不是算力读数 —— 不增加一个核、不增加一字节显存。")
    return 0 if er["ok"] else 1


# ── 真跑验收：对一个**已经跑起来**的实例量读数（只读探针，不部署）────────────
# 为什么把「收读数」与「判读数」分成两件事：判决要能被自检喂假读数**真触发**，
# 否则这一整套判据自己就是未验分支（本仓栽过：判据进不了控制 = 判据没验过）。
# 🔴 令牌闸（2026-09-25 起**云端已开**）：Worker 设了 `GBT_ENDPOINT_TOKEN` 之后，
#    `/v1/chat/completions` 不带 `Authorization: Bearer <同一个值>` 一律 **401**。
#    验收工具如果**不会带令牌**，那它量到的全是我自己的 401 —— 看着像"模型坏了"。
#    ⇒ 令牌只从**显式入参**来（`--token` / `--token-file` / 环境变量），**不写死、不进仓**；
#      没给就照旧发（未开闸的实例照样能用），并把这件事实写进读数。
_TOKEN: str = ""


def http_json(url: str, method: str = "GET", payload=None, timeout: float = 20.0) -> dict:
    """一次 HTTP 探针。**取不到就如实记未读到**，不编、不拿 0 顶。

    🔴 `User-Agent` 必须**如实自报**，因为平台侧会挡默认 UA：实测同一个**已部署**的 Worker，
    `Python-urllib/*` ⇒ 403，而如实自报的工具名 / curl / 浏览器 ⇒ 200。
    不设 UA 的后果极坏：**16 条判据全红**，看着像"部署失败了"，其实 **Worker 好好地在跑**。
    ⇒ 这里写一个明确标识自己的 UA（**不伪装成浏览器**：那是在骗平台自己的防护）。
    """
    data = None
    headers = {"user-agent": UA}
    if _TOKEN:
        headers["authorization"] = "Bearer " + _TOKEN
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["content-type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return {"status": r.status, "body": json.loads(raw), "err": None}
            except Exception:
                return {"status": r.status, "body": None, "raw": raw[:300], "err": "回包不是 JSON"}
    except urllib.error.HTTPError as e:      # 4xx/5xx 是**读数**，不是失败
        raw = e.read().decode("utf-8", "replace")
        try:
            return {"status": e.code, "body": json.loads(raw), "err": None}
        except Exception:
            return {"status": e.code, "body": None, "raw": raw[:300], "err": "回包不是 JSON"}
    except Exception as e:
        return {"status": None, "body": None, "err": f"{type(e).__name__}: {e}"}


def collect_live(base: str, timeout: float = 20.0, expect_llm: bool = False, expect_d1: bool = False, expect_storage: bool = False, expect_image: bool = False, expect_tools: bool = False) -> dict:
    """把真跑验收要的读数**一次收齐**。网络层只做收集，不做判决。

    `expect_llm=True` 时**多收两条**：01 号真打一次端点、03 号真打一次无审查通道。
    为什么要开关：没接端点时要求"真拿到回答"是**判据比对象宽**（假红）；
    接了端点还只量形状则是**判据比对象窄**（假绿）。两种宽度都得有，由开关选。
    """
    b = (base or "").rstrip("/")
    probes = {
        "root": http_json(b + "/", timeout=timeout),
        "health": http_json(b + "/health", timeout=timeout),
        "mesh": http_json(b + "/mesh", timeout=timeout),
        "edges_before": http_json(b + "/edges", timeout=timeout),
        "full_ping": http_json(b + "/mesh/full-ping", method="POST", payload={}, timeout=max(timeout, 60.0)),
        "edges_after": http_json(b + "/edges", timeout=timeout),
        "gate_put": http_json(b + "/rpc/gbt-c06-tool-shell/exec", method="POST", payload={"cmd": "echo probe"}, timeout=timeout),
        "grants": http_json(b + "/rpc/gbt-c09-policy-guard/grants", method="POST", payload={}, timeout=timeout),
        "grant_attempt": http_json(b + "/admin/grant", method="POST", payload={"scopes": ["filesystem_write"]}, timeout=timeout),
        "llm_status": http_json(b + "/rpc/gbt-c01-llm-gateway/status", method="POST", payload={}, timeout=timeout),
        "unc_status": http_json(b + "/rpc/gbt-c03-uncensored-lane/status", method="POST", payload={}, timeout=timeout),
        "recall_missing": http_json(b + "/rpc/gbt-c08-memory-local/recall", method="POST", payload={"k": "probe/没有这个键"}, timeout=timeout),
    }
    if expect_image:
        probes["img_gen"] = http_json(b + "/rpc/gbt-c03-uncensored-lane/image", method="POST", payload={"prompt": "验收探针：一只戴墨镜的土豆", "size": "1024x1024"}, timeout=max(timeout, 90.0))
    if expect_llm:
        probes["llm_complete"] = http_json(b + "/rpc/gbt-c01-llm-gateway/complete", method="POST", payload={"prompt": "用一句话说你是谁"}, timeout=max(timeout, 60.0))
        probes["unc_route"] = http_json(b + "/rpc/gbt-c03-uncensored-lane/route", method="POST", payload={"prompt": "ping"}, timeout=max(timeout, 60.0))
    if expect_d1:
        tag = "probe-" + str(int(time.time() * 1000))
        # 🔴 探针文本必须**独一份**：上一版所有探针共用同一句话 ⇒ 余弦全 1.0 并列 ⇒
        #    top-3 里不一定轮到刚写进去那条 ⇒ 判据变成看运气（假红）。
        #    "写进去读得回"这条判据要成立，探针本身就得是可分辨的。
        ptext = "探针写入的一条向量记忆：" + tag
        probes["vec_index"] = http_json(b + "/rpc/gbt-c07-memory-vector/index", method="POST", payload={"id": tag, "text": ptext}, timeout=timeout)
        probes["vec_query"] = http_json(b + "/rpc/gbt-c07-memory-vector/query", method="POST", payload={"text": ptext, "top": 3}, timeout=timeout)
        probes["vec_stats"] = http_json(b + "/rpc/gbt-c07-memory-vector/stats", method="POST", payload={}, timeout=timeout)
    if expect_storage:
        # 存储面（05 对象存储 / 08 KV / 10 落账）：Node 桩验过不算验，要**在真运行时里真写真读**。
        # ⚠️ 05 与 08 的部分 op 挂门（filesystem_read/write）⇒ 云上要先有主人授权，
        #    被挡时读数会带「被门挡住：缺 …」且**仍算红**。
        stag = "probe-" + str(int(time.time() * 1000))
        probes["f_put"] = http_json(b + "/rpc/gbt-c05-tool-file/put", method="POST", payload={"key": stag + ".txt", "text": "GBT存储探针"}, timeout=timeout)
        probes["f_get"] = http_json(b + "/rpc/gbt-c05-tool-file/get", method="POST", payload={"key": stag + ".txt"}, timeout=timeout)
        probes["f_list"] = http_json(b + "/rpc/gbt-c05-tool-file/list", method="POST", payload={"prefix": ""}, timeout=timeout)
        probes["m_remember"] = http_json(b + "/rpc/gbt-c08-memory-local/remember", method="POST", payload={"k": stag, "v": "记忆探针"}, timeout=timeout)
        probes["m_recall"] = http_json(b + "/rpc/gbt-c08-memory-local/recall", method="POST", payload={"k": stag}, timeout=timeout)
        probes["m_list"] = http_json(b + "/rpc/gbt-c08-memory-local/list", method="POST", payload={}, timeout=timeout)
        probes["o_emit"] = http_json(b + "/rpc/gbt-c10-observability/emit", method="POST", payload={"kind": "storage-probe", "detail": stag}, timeout=timeout)
        probes["o_tail"] = http_json(b + "/rpc/gbt-c10-observability/tail", method="POST", payload={"n": 3}, timeout=timeout)
        probes["f_del"] = http_json(b + "/rpc/gbt-c05-tool-file/del", method="POST", payload={"key": stag + ".txt"}, timeout=timeout)
        probes["f_get2"] = http_json(b + "/rpc/gbt-c05-tool-file/get", method="POST", payload={"key": stag + ".txt"}, timeout=timeout)
    if expect_tools:
        # 🔴 为什么要这道开关：我曾**漏了"真把 tools 发出去"这一步**，就对外说过
        #    「上游不支持工具调用」——**量错了**。判据必须**先把工具发出去**，再从回包里找
        #    `tool_calls`，并且**回喂工具结果**看它用不用。
        # 🔴 回喂的工具结果里塞一个**本次运行现生成的哨兵**（现造现用，源码里没有这个字面量）：
        #    早先的判据是「正文里含 `18` 或 `晴`」—— 那是**自由文本子串**，
        #    被 `criterion_bench` 的 D2 当场点名（判据太弱：`18` 可以从任何地方来）。
        #    带哨兵之后，这个值**只可能来自我们回喂的那条工具结果** ⇒ 判据才真的在判
        #    「它用没用工具结果」。（同型做法：向量探针带唯一标记那条。）
        sentinel = "ZX" + "".join(random.choice("0123456789abcdef") for _ in range(8))
        tools = [{"type": "function", "function": {"name": "get_weather", "description": "查某城市天气",
                  "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}}]
        probes["tool_turn1"] = http_json(b + "/v1/chat/completions", method="POST", payload={
            "model": "gbt-potato-v8", "max_tokens": 512,
            "messages": [{"role": "user", "content": "北京现在天气怎么样？必须先调用工具。"}],
            "tools": tools, "tool_choice": "auto"}, timeout=max(timeout, 120.0))
        t1 = (probes["tool_turn1"].get("body") or {})
        msg = ((t1.get("choices") or [{}])[0].get("message") or {})
        calls = msg.get("tool_calls") or []
        c0 = (calls[0] if calls else {})
        ((c0.get("function") or {}).get("arguments")) or "{}"
        probes["tool_turn2"] = http_json(b + "/v1/chat/completions", method="POST", payload={
            "model": "gbt-potato-v8", "max_tokens": 512,
            "messages": [
                {"role": "user", "content": "北京现在天气怎么样？必须先调用工具。"},
                {"role": "assistant", "content": None, "tool_calls": calls},
                {"role": "tool", "tool_call_id": c0.get("id") or "call_1",
                 "content": json.dumps({"temp_c": 18, "sky": "晴", "readout": sentinel}, ensure_ascii=False)},
                {"role": "user", "content": "只回一行，把工具返回里的 readout 值原样写出来，不要别的字。"},
            ],
            "tools": tools, "tool_choice": "auto"}, timeout=max(timeout, 120.0))
        probes["tool_sentinel"] = {"value": sentinel, "note": "本次运行现生成的哨兵（源码里没有）"}
    return {"base": b, "probes": probes, "reachable": any((p or {}).get("status") is not None for p in probes.values())}


def judge_live(rd: dict, expect_llm: bool = False, expect_d1: bool = False, expect_storage: bool = False, expect_image: bool = False, expect_tools: bool = False) -> list:
    """**纯函数**：读数 → 逐条 PASS/FAIL。喂假读数必须能判出红（自检里有负控）。"""
    rows = []
    p = rd.get("probes", {}) or {}

    def body(k):
        v = (p.get(k) or {}).get("body")
        return v if isinstance(v, dict) else {}

    def status(k):
        return (p.get(k) or {}).get("status")

    def row(name, cond, reading):
        rows.append({"判据": name, "过": bool(cond), "读数": reading})

    row("根路由在册", status("root") == 200, f"HTTP {status('root')}")
    h = body("health")
    row("十位全在（health）", h.get("alive") == h.get("modules") == 10, f"alive {h.get('alive')}/{h.get('modules')}")
    m = body("mesh")
    row("形态口径=单 isolate（真共享 CPU 的唯一样子）", m.get("form") == "single-isolate", str(m.get("form")))
    row("十位职责逐个在册", len(m.get("modules") or []) == 10, f"{len(m.get('modules') or [])} 位")

    e0 = body("edges_before")
    d0 = e0.get("declared") or {}
    n = len(d0.get("per_module") or [])
    row("声明边数=模块现算（不写死）", n > 0 and d0.get("directed") == n * (n - 1), f"{d0.get('directed')} = {n}×{n - 1}")
    row("无自环", d0.get("self_loops") == 0, str(d0.get("self_loops")))
    row("双向对称（拼接不许缺向）", d0.get("asymmetric") == 0, str(d0.get("asymmetric")))

    fp = body("full_ping")
    fr = fp.get("full_ping") or {}
    row("全互通实跑：每位摸其余 9 位、90 发全中", fr.get("tried") == fr.get("ok") == 90, f"{fr.get('ok')}/{fr.get('tried')}")
    # 🔴 取证必须**在同一次请求内**。上一版拿"随后另发一次的 /edges"去对账 ——
    #    本机单 isolate 时能过，**真云上必红**：Cloudflare 有多个 isolate，
    #    两次请求可能落在不同副本上，谁也没见过对方的计数（实测 1/90 · 增量 0）。
    #    这不是计数坏了，是**判据跨了它量不到的边界**。⇒ 用同一次 full-ping 响应里
    #    自带的那份 edges 快照（同一 isolate、同一请求）。
    fe = fp.get("edges") or {}
    row("实跑后 90 条边逐条被走过（同一次请求内取证）", ((fe.get("observed") or {}).get("distinct_edges")) == ((fe.get("declared") or {}).get("directed")), f"{(fe.get('observed') or {}).get('distinct_edges')}/{(fe.get('declared') or {}).get('directed')}")
    row("同一次请求内至少记下 90 次调用（计数只增不减，常量不会让它增长）", ((fe.get("observed") or {}).get("calls") or 0) >= 90, f"calls={((fe.get('observed') or {}).get('calls'))}（≥90 即可：同一 isolate 上还记过 /health 等其他调用）")
    # 跨请求计数在云上**不保证**（多副本）—— 如实报成边界，不当判据（判据跨边界 = 假红）
    cross = ((body("edges_after").get("observed") or {}).get("distinct_edges"))
    row("跨请求计数：云上多副本 ⇒ 只作参考不作判据（本项只要求读得到）", cross is not None, f"另发一次请求读到 {cross}（本机单副本时会等于 90）")

    g = body("gate_put")
    # 🔴 门的拒绝面只能拿**未授权**的作用域来量。上一版探的是 filesystem_write，
    #    而冒烟配方里正好给它发过授权 ⇒ 有授权时这条必然假红（与"默认冷实例"同族：
    #    判据默认了某个前提却没说）。现在探 process_execute（冒烟配方从不发它），
    #    并把**在册授权**一起报出来 —— 万一它也在册，红字自己会说明原因。
    granted = body("grants").get("granted") or []
    row("门挡住没授权的作用域（探 process_execute）", status("gate_put") == 403 and "process_execute" in (g.get("missing_scopes") or []), f"HTTP {status('gate_put')} 缺={g.get('missing_scopes')} 在册={granted}")
    row("云上实例没有自发授权的口子（403）", status("grant_attempt") == 403, f"HTTP {status('grant_attempt')}")

    llm = body("llm_status")
    row("01 号模型位读数如实（二选一，不许含混）", llm.get("reading") in ("已接线", "未读到"), str(llm.get("reading")))
    row("01 号如实标：托管权重不是我们的", (llm.get("backends") or [{}])[0].get("weights_ours") is False or llm.get("reading") == "未读到", str(llm.get("backends")))
    unc = body("unc_status")
    row("03 号如实分档（托管模型不算无审查）", unc.get("wired") is True or unc.get("reading") == "未读到", f"wired={unc.get('wired')} reading={unc.get('reading')}")
    rm = body("recall_missing")
    row("08 号没存过的键不许拿 0 或空串顶（判据与对象同宽）", rm.get("found") is False and rm.get("reading") == "未读到", f"found={rm.get('found')} reading={rm.get('reading')}")

    # 有门的 op（external_llm）被挡时，读数要**原样念出缺哪个作用域**，
    # 否则红因离根因很远 —— 但**仍然算红**：没验过就是没验过，不许念成通过。
    # ⚠️ 它必须定义在**所有** expect_* 分支之外：放在 expect_llm 里的话，
    #    单开 --expect-image 时它就是未定义名（本轮当场 NameError）。
    def blocked_note(k):
        pr = p.get(k) or {}
        bd = pr.get("body") if isinstance(pr.get("body"), dict) else {}
        if bd.get("denied"):
            return "｜被门挡住：缺 " + str(bd.get("missing_scopes"))
        if pr.get("status") is None:
            return "｜探针没通"
        return ""

    if expect_llm:

        lc = body("llm_complete")
        got = lc.get("content")
        row("01 号真能驱动端点（拿到 content）", lc.get("ok") is True and isinstance(got, str) and got.strip() != "", f"ok={lc.get('ok')} ms={lc.get('ms')} 字数={len(got or '')}{blocked_note('llm_complete')}")
        row("01 号如实标权重归属（true/false 必须明确给出，不许含混）", isinstance(lc.get("weights_ours"), bool), f"weights_ours={lc.get('weights_ours')} via={lc.get('via')}{blocked_note('llm_complete')}")
        row("01 号报出解析走的是哪条路（形状自适应可诊断）", bool(lc.get("content_path")) and lc.get("content_path") != "未识别", f"content_path={lc.get('content_path')} raw_keys={lc.get('raw_keys')}")
        row("01 号发出去的请求带了身份（主人红线之一）", lc.get("identity_injected") is True or bool(lc.get("identity_why")), f"identity_injected={lc.get('identity_injected')}")
        row("01 号读数带延迟与模型名（不是空壳）", isinstance(lc.get("ms"), int) and lc.get("ms") >= 0 and bool(lc.get("model") or lc.get("http")), f"ms={lc.get('ms')} model={lc.get('model')} http={lc.get('http')}{blocked_note('llm_complete')}")
        ur = body("unc_route")
        row("03 号两种状态都算对（拒 / 真打）", (ur.get("ok") is False and ur.get("reason") == "未读到") or (ur.get("ok") is True and bool(ur.get("content"))), f"ok={ur.get('ok')} content={str(ur.get('content'))[:24]}{blocked_note('unc_route')}")

    if expect_d1:
        vi = body("vec_index")
        vq = body("vec_query")
        vs = body("vec_stats")
        row("07 号落点是 d1（不是内存）", vi.get("sink") == "d1", f"index sink={vi.get('sink')}")
        hit_ids = [m.get("id") for m in (vq.get("matches") or [])]
        row("07 号写入后读得回（同一实例内往返 · 探针文本独一份）", vq.get("sink") == "d1" and bool(hit_ids) and hit_ids[0] == vi.get("id"), f"sink={vq.get('sink')} 命中首位={hit_ids[:1]}")
        row("07 号 stats 报得出条数（不是空壳）", isinstance(vs.get("count"), int) and vs.get("count") >= 1, f"sink={vs.get('sink')} count={vs.get('count')}")

    if expect_storage:
        def note(k):
            pr = p.get(k) or {}
            bd = pr.get("body") if isinstance(pr.get("body"), dict) else {}
            if bd.get("denied"):
                return "｜被门挡住：缺 " + str(bd.get("missing_scopes"))
            if pr.get("status") is None:
                return "｜探针没通"
            return ""

        fp2 = body("f_put")
        fg = body("f_get")
        fl = body("f_list")
        fd = body("f_del")
        fg2 = body("f_get2")
        key = fp2.get("key")
        row("05 号真写进对象存储（真落点带 mesh10/ 前缀）", fp2.get("ok") is True and str(fp2.get("stored_key", "")).startswith("mesh10/"), f"stored_key={fp2.get('stored_key')}{note('f_put')}")
        row("05 号读得回原文（真读，不是回声）", fg.get("ok") is True and fg.get("text") == "GBT存储探针", f"text={str(fg.get('text'))[:16]}{note('f_get')}")
        row("05 号列得出刚写那条（逻辑键不带前缀）", fl.get("ok") is True and key in (fl.get("logical_keys") or []), f"count={fl.get('count')} 含={key in (fl.get('logical_keys') or [])}{note('f_list')}")
        row("05 号删掉之后读不到（不是假删）", fd.get("ok") is True and fg2.get("ok") is False, f"del_ok={fd.get('ok')} 再读_ok={fg2.get('ok')}{note('f_del')}")

        mr = body("m_remember")
        mq = body("m_recall")
        ml = body("m_list")
        # 🔴 比的是**记忆键**（mr.k），不是文件键 —— 上一版拿 f_put 的 key（带 .txt）去比
        #    记忆列表 ⇒ 必然对不上（自造假红）。
        mkey = mr.get("k")
        row("08 号 KV 写读往返成立（真落点 KV）", mr.get("ok") is True and mq.get("found") is True and mq.get("v") == "记忆探针", f"sink={mr.get('sink')} found={mq.get('found')} v={mq.get('v')}")
        row("08 号 KV 列得出逻辑键（前缀不外泄给人看）", (mkey in (ml.get("logical_keys") or [])) and all(not str(x).startswith("mesh10/") for x in (ml.get("logical_keys") or [])), f"count={ml.get('count')} 含={mkey in (ml.get('logical_keys') or [])}")

        oe = body("o_emit")
        ot = body("o_tail")
        row("10 号落账读得回（从 R2 追加账读 ⇒ 跨副本一致）", oe.get("ok") is True and int(ot.get("total") or 0) >= 1 and ot.get("sink") == "r2", f"sink={oe.get('sink')} tail_sink={ot.get('sink')} total={ot.get('total')}")
    if expect_image:
        ig = body("img_gen")
        row("03 号图像面真打端点（拿到图像字节）", ig.get("ok") is True and int(ig.get("bytes_est") or 0) > 0, f"ok={ig.get('ok')} bytes_est={ig.get('bytes_est')} ms={ig.get('ms')}{blocked_note('img_gen')}")
        row("03 号图像面验到 PNG 签名（不是只验有个字符串）", ig.get("png_magic") is True, f"png_magic={ig.get('png_magic')}")
        # 两种状态各有各的"如实"：接了线要说明「验的是管道不是画」；
        # 没接线要说明「未接线」。上一版只认第一种 ⇒ 没接线时**假红**（判据比对象窄）。
        igb = str(ig.get("boundary") or "")
        honest = ("管道" in igb) if ig.get("ok") is True else (ig.get("reason") == "未读到" and bool(igb))
        row("03 号图像面读数如实分档（接线说管道 / 没接线说明没接线）", honest, igb[:44])
    if expect_tools:
        # 🔴 为什么要这道开关：我曾**漏了"真把 tools 发出去"这一步**，就对外说过
        #    「上游不支持工具调用」——**量错了**。判据必须**先把工具发出去**，再从回包里找
        #    `tool_calls`，并且**回喂工具结果**看它用不用。
        t1 = body("tool_turn1")
        m1 = ((t1.get("choices") or [{}])[0].get("message") or {})
        calls = m1.get("tool_calls") or []
        fr1 = ((t1.get("choices") or [{}])[0].get("finish_reason")) or ""
        row("工具调用：真把 tools 发出去 ⇒ 回包里必须有 tool_calls", len(calls) >= 1 and fr1 == "tool_calls",
            f"tool_calls={len(calls)} finish={fr1} 名={(calls[0].get('function') or {}).get('name') if calls else None}{blocked_note('tool_turn1')}")
        t2 = body("tool_turn2")
        m2 = ((t2.get("choices") or [{}])[0].get("message") or {})
        txt = str(m2.get("content") or "")
        want = str(((rd.get("probes") or {}).get("tool_sentinel") or {}).get("value") or "")
        row("工具回合闭环：回喂工具结果 ⇒ 正文里带回了**我们现造的哨兵**（只可能来自那条工具结果）",
            bool(txt) and bool(want) and want in txt,
            f"哨兵={want or '**未读到**'} ｜ 正文={txt[:48]!r}{blocked_note('tool_turn2')}")
    return rows


def unreachable_report(base: str, errors: list) -> dict:
    """**纯函数**：实例取不到读数时的如实报告。

    口径写在这里，不散在打印里：取不到就是取不到 —— **不许当 0 条、不许当通过**，
    也不许把网络错误念成"服务没起来"（那是两回事）。
    """
    return {"base": base, "unread": "该实例取不到读数", "原因": errors}


def cmd_live(url: str, as_json: bool, timeout: float = 20.0, expect_llm: bool = False, expect_d1: bool = False, expect_storage: bool = False, expect_image: bool = False, expect_tools: bool = False) -> int:
    """对一个**已经跑起来**的实例量真读数。**只读**：不部署、不改远端。

    口径：实例取不到读数时如实报并 `rc=2` —— 不许当 0 条、更不许当通过。
    `expect_llm=True` 额外要求 01 号真打到端点并拿回内容（端点没接就别开这个开关）。
    `expect_d1=True` 额外要求 07 号落在 d1 且写读往返成立（用 `wrangler.dev.toml` 起的实例才满足）。
    ⚠️ 跨重启的持久性**量不了一次调用**：那是两步（写 → 重启 → 再读），做法见 `deploy/cloud-10/README.md`。
    """
    rd = collect_live(url, timeout=timeout, expect_llm=expect_llm, expect_d1=expect_d1, expect_storage=expect_storage, expect_image=expect_image, expect_tools=expect_tools)
    rd["token"] = ("带了 Bearer（%d 位）" % len(_TOKEN)) if _TOKEN else "**没带令牌**（实例开了闸的话，chat 面会全 401）"
    if not rd["reachable"]:
        errs = sorted({(p or {}).get("err") or "未读到" for p in rd["probes"].values()})
        out = unreachable_report(rd["base"], errs[:4])
        if as_json:
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            print(f"真跑验收：{out['base']} —— {out['unread']}")
            for e in out["原因"]:
                print("  · " + e)
        return 2
    rows = judge_live(rd, expect_llm=expect_llm, expect_d1=expect_d1, expect_storage=expect_storage, expect_image=expect_image, expect_tools=expect_tools)
    passed = [r for r in rows if r["过"]]
    out = {
        "base": rd["base"],
        "令牌": rd["token"],
        "expect_llm": expect_llm,
        "expect_d1": expect_d1,
        "expect_storage": expect_storage,
        "判据": len(rows),
        "过": len(passed),
        "不过": [r for r in rows if not r["过"]],
        "逐条": rows,
        "边界": [
            "本命令只读一个**已经跑起来**的实例，不部署、不改远端。",
            "真跑 ≠ 真部署：本机 wrangler dev 起的是本地 workerd；云上那份要 deploy 之后才存在。",
            "Workers AI 的权重不是我们的、平台侧内容策略仍在 ⇒ 能干活，但不是「无限制」。",
            "真『无限制』只走 03 号那条自托管权重通道（接没接线看上面的读数）。",
            "01/03 两条都是**有门**的（external_llm）：云上没有主人授权时，读数会明写「被门挡住：缺 …」。",
        ],
    }
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"真跑验收（只读）：{rd['base']}")
        for r in rows:
            print(f"  {'PASS' if r['过'] else 'FAIL'}  {r['判据']}  ::  {r['读数']}")
        print(f"\n合计 {len(passed)}/{len(rows)} 通过")
        for b in out["边界"]:
            print("  · " + b)
    return 0 if len(passed) == len(rows) else 1


def selftest() -> int:
    ok = 0
    total = 0
    fails = []

    def ck(name, cond, detail=""):
        nonlocal ok, total
        total += 1
        if cond:
            ok += 1
        else:
            fails.append(f"{name} :: {detail}")

    real = load_mesh(ROOT / MESH_REL)
    model = build_model(real)
    er = edge_report(model["ids"], model["peers"])

    # 正控：真源本身
    ck("正控·真源合格", validate(real) == [], str(validate(real))[:200])
    ck("正控·模块数=主人口径10", er["modules"] == 10, str(er["modules"]))
    ck("正控·每位绑 9 位", er["expected_per_module"] == 9, str(er["expected_per_module"]))
    ck("正控·有向边=模块现算", er["directed"] == er["modules"] * (er["modules"] - 1), str(er["directed"]))
    ck("正控·形状过", er["ok"], str(er))

    # 负控 1：少一位 ⇒ 模块数红
    m1 = json.loads(json.dumps(real))
    m1["modules"] = m1["modules"][:-1]
    ck("负控·少一位要红", any("模块数" in x for x in validate(m1)), str(validate(m1))[:120])

    # 负控 2：seq 跳号 ⇒ 红
    m2 = json.loads(json.dumps(real))
    m2["modules"][3]["seq"] = 99
    ck("负控·seq 跳号要红", any("seq" in x for x in validate(m2)), str(validate(m2))[:120])

    # 负控 3：op 没写门 ⇒ 红（这正是「门藏 if 里」的形态）
    m3 = json.loads(json.dumps(real))
    m3["modules"][0]["ops"] = m3["modules"][0]["ops"] + ["sneaky"]
    ck("负控·op 没写门要红", any("没写门" in x for x in validate(m3)), str(validate(m3))[:120])

    # 负控 4：门名不在 15 条里 ⇒ 红
    m4 = json.loads(json.dumps(real))
    m4["modules"][0]["op_gates"]["complete"] = "whatever"
    ck("负控·野门名要红", any("15 条" in x for x in validate(m4)), str(validate(m4))[:120])

    # 负控 5：边数口径被改 ⇒ 红
    m5 = json.loads(json.dumps(real))
    m5["edges"]["directed_expected"] = 10
    ck("负控·边数口径被改要红", any("directed_expected" in x for x in validate(m5)), str(validate(m5))[:120])

    # 负控 6：peer 表里塞自环 / 少一位 ⇒ edge_report 红（纯函数层）
    ids = model["ids"]
    p_self = {i: list(model["peers"][i]) for i in ids}
    p_self[ids[0]] = p_self[ids[0]] + [ids[0]]
    ck("负控·自环要红", not edge_report(ids, p_self)["ok"], str(edge_report(ids, p_self))[:120])
    p_less = {i: list(model["peers"][i]) for i in ids}
    p_less[ids[1]] = [x for x in p_less[ids[1]] if x != ids[0]]
    r_less = edge_report(ids, p_less)
    ck("负控·不对称要红", not r_less["ok"] and r_less["asymmetric"], str(r_less["asymmetric"])[:120])

    # 负控 7：件漂移要红（拿真件改一个字节去对账）
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        # 手写件 + 公共件必须按**真件树**摆好 —— 否则控制本身失真。
        # 🔴 2026-10-14 修（实测根因，别改判据掩盖）：
        #   原夹具只搬 modules.js / worker.js，而 worker.js 静态 import "./slots.generated.js"
        #   —— 那份是**另一个生成器**的产物（slots 面），不是 cloud-mesh gen 的活 ⇒ 临时树缺它
        #   ⇒ 树级扫描把 src/worker.js 判成坏件，连带「正控·干净目录生成」「正控·树级扫描干净」
        #      「负控·树级扫描抓到坏件」3 条一起红（selftest 73/76）。
        #   现读：**真件树** import_problems(ROOT/deploy/cloud-10) == {}（干净）⇒ 红的是夹具不是成品。
        #   修法：照"真件树 src/ 下真实存在的 .js"现读搬运，**不写死名单**（以后多一个公共件也不会再红）。
        (tdp / "src").mkdir(parents=True, exist_ok=True)
        real_src = ROOT / "deploy/cloud-10/src"
        for name in sorted(p.name for p in real_src.glob("*.js")):
            shutil.copy2(real_src / name, tdp / "src" / name)
        rc = cmd_gen(as_json=True, check_only=False, mesh_path=ROOT / MESH_REL, out_root=tdp, quiet=True)
        ck("正控·干净目录生成 rc=0", rc == 0, str(rc))
        target = tdp / GEN_REL.split("deploy/cloud-10/")[1]
        s = target.read_text(encoding="utf-8")
        target.write_text(s.replace('"form": "single-isolate"', '"form": "tampered"'), encoding="utf-8", newline="\n")
        rc2 = cmd_gen(as_json=True, check_only=True, mesh_path=ROOT / MESH_REL, out_root=tdp, quiet=True)
        ck("负控·件被改要红", rc2 == 1, str(rc2))
        # 负控 8：形态 B 的绑定条数 = 9（每位绑其余 9 位）
        f = (tdp / f"modules/{ids[0]}/wrangler.toml").read_text(encoding="utf-8")
        ck("正控·形态B 服务绑定 9 条", f.count("[[services]]") == 9, str(f.count("[[services]]")))
        ck("负控·形态B 绑定里不许出现自己", f'name = "{ids[0]}"' in f and f.count(f'service = "{ids[0]}"') == 0, f)

        # 负控 9：真源坏掉时 gen 必须拒绝（rc=2），不许半成品落地
        bad_mesh = tdp / "bad.json"
        m6 = json.loads(json.dumps(real))
        m6["modules"][0]["op_gates"] = {}
        bad_mesh.write_text(json.dumps(m6, ensure_ascii=False), encoding="utf-8")
        rc3 = cmd_gen(as_json=True, check_only=False, mesh_path=bad_mesh, out_root=tdp / "out2", quiet=True)
        ck("负控·真源坏 ⇒ rc=2 拒绝生成", rc3 == 2, str(rc3))
        ck("负控·拒绝时不许落件", not (tdp / "out2").exists(), str(list((tdp / "out2").iterdir()) if (tdp / "out2").exists() else []))

        # 负控 10：形态 B 的相对 import 必须真能指到公共件（路径算错 = 装到云上一加载就崩）
        w = tdp / f"modules/{ids[0]}/src/index.js"
        ck("正控·形态B 相对 import 真指到公共件", unresolved_imports(w) == [], str(unresolved_imports(w)))
        ck("正控·树级扫描干净", import_problems(tdp) == {}, str(import_problems(tdp)))

        probe = tdp / "_probe" / "probe.js"
        probe.parent.mkdir(parents=True, exist_ok=True)
        probe.write_text('import x from "../../src/modules.js";\n', encoding="utf-8", newline="\n")
        ck("负控·路径少一级必须被点名", unresolved_imports(probe) == ["../../src/modules.js"], str(unresolved_imports(probe)))
        ck("负控·树级扫描抓到坏件", list(import_problems(tdp)) == ["_probe/probe.js"], str(list(import_problems(tdp))))
        shutil.rmtree(probe.parent)

    # 负控 14：部署配置护栏（D1 绑定 · 禁止部署标记）—— 用的都是真配置，不必在临时目录里
    good_dev = "# 本文件禁止部署\n[[d1_databases]]\nbinding = \"DB\"\n"
    ck("正控·两份配置各就各位 ⇒ 零问题", deploy_config_guards('name = "x"\n', good_dev) == [], str(deploy_config_guards('name = "x"\n', good_dev)))
    ck("负控·部署配置里塞了 D1 绑定 ⇒ 必须点名", any("D1" in x for x in deploy_config_guards('[[d1_databases]]\nbinding = "DB"\n', good_dev)), str(deploy_config_guards('[[d1_databases]]\nbinding = "DB"\n', good_dev)))
    ck("正控·部署配置里注释掉的 D1 不算启用", deploy_config_guards('# [[d1_databases]]\nname = "x"\n', good_dev) == [], str(deploy_config_guards('# [[d1_databases]]\nname = "x"\n', good_dev)))
    ck("负控·本地配置没标禁止部署 ⇒ 必须点名", any("禁止部署" in x for x in deploy_config_guards('name = "x"\n', '[[d1_databases]]\n')), str(deploy_config_guards('name = "x"\n', '[[d1_databases]]\n')))
    ck("负控·本地配置缺 D1 ⇒ 必须点名", any("验不了" in x for x in deploy_config_guards('name = "x"\n', "# 禁止部署\n")), str(deploy_config_guards('name = "x"\n', "# 禁止部署\n")))
    ck("正控·真配置两份都过", deploy_config_guards((ROOT / "deploy" / "cloud-10" / "wrangler.toml").read_text(encoding="utf-8"), (ROOT / "deploy" / "cloud-10" / "wrangler.dev.toml").read_text(encoding="utf-8")) == [], "真配置")

    # 负控 11：云侧现读的纯函数层（模板占位符 / 身份掩码 / list 解析）
    ck("正控·占位符计数", count_placeholders('a="<未配：x>" b="<未配：y>"') == ["x", "y"], str(count_placeholders('a="<未配：x>" b="<未配：y>"')))
    ck("负控·注释里的占位符不算没落", count_placeholders('# x = "<未配：注释说明>"\n') == [], str(count_placeholders('# x = "<未配：注释说明>"\n')))
    ck("正控·注释处与生效处分两个读数", count_placeholders_all('# a="<未配：注释>"\nb="<未配：生效>"\n') == {"active": ["生效"], "commented": ["注释"]}, str(count_placeholders_all('# a="<未配：注释>"\nb="<未配：生效>"\n')))
    ck("负控·空文本是空表不是 0 处", count_placeholders("") == [] and count_placeholders(None) == [], "空文本处理")
    tmpl_text = (ROOT / "deploy" / "cloud-10" / "wrangler.toml").read_text(encoding="utf-8")
    ck("正控·真模板生效处已清零", count_placeholders(tmpl_text) == [], str(count_placeholders(tmpl_text)))
    ck("正控·真模板注释处仍留着说明", len(count_placeholders_all(tmpl_text)["commented"]) > 0, str(len(count_placeholders_all(tmpl_text)["commented"])))
    ck("负控·身份掩码不许漏出全名", "lopaycn" not in mask_identity("lopaycn@gmail.com"), mask_identity("lopaycn@gmail.com"))
    ck("正控·短身份只留星号 / 空记未读到", mask_identity("ab") == "****" and mask_identity("") == "未读到", mask_identity("ab"))
    ck("负控·list 输出解析不了要记未读到（不许写 0）", parse_list("kv", "not json").get("count") is None, str(parse_list("kv", "not json")))
    ck("正控·r2 文本解析出桶名", parse_list("r2", "name:           one\nname:           two\n").get("count") == 2, str(parse_list("r2", "name:           one\nname:           two\n")))
    rr = run_wrangler(["definitely-not-a-command"])
    ck("负控·wrangler 跑不动不崩、如实记 rc", rr.get("rc") is not None and isinstance(rr.get("err"), str), str(rr.get("rc")))

    # 负控 12：云侧判决的**两条诚实分支**必须能被真触发（不是长在联网命令里没人走到）
    good_who = "You are logged in with an OAuth Token, associated with the email a@b.co."
    good_inv = {k: {"count": 2, "names": ["x", "y"], "reading": "已读到"} for k in ("kv", "r2", "d1")}
    clean_tmpl = 'name = "x"\n# 注释里的 <未配：说明> 不算没落\n'
    v_ok = readiness_verdict(clean_tmpl, good_who, good_inv, live=True, caveat_src={"modules": real["modules"]})
    ck("正控·全绿输入 ⇒ 可部署且零拦路", v_ok["deployable_now"] and v_ok["blockers"] == [], str(v_ok["blockers"]))
    ck("正控·已知缺口从单一真源推出来（不许手写）", len(v_ok["caveats"]) >= 4, str(len(v_ok["caveats"])))
    v_noauth = readiness_verdict(clean_tmpl, "", good_inv, live=True)
    ck("负控·身份未读到 ⇒ 必须点名（整句对齐，不是包含）",
       v_noauth["blockers"] == ["Cloudflare 身份未读到（OAuth 未登录或取不到）"], str(v_noauth["blockers"]))
    v_nores = readiness_verdict(clean_tmpl, good_who, {"kv": {"count": None, "names": [], "reading": "未读到"}, "r2": {"count": 1, "names": ["b"]}, "d1": {"count": 3, "names": []}}, live=True)
    ck("负控·资源未读到 ⇒ 必须点名（不许当 0 条通过）",
       v_nores["blockers"] == ["kv 资源未读到 ⇒ 该绑定现在挂不上"], str(v_nores["blockers"]))
    v_ph = readiness_verdict('id = "<未配：没落>"\n', good_who, good_inv, live=True)
    ck("负控·生效占位符没落 ⇒ 不许说可部署", (not v_ph["deployable_now"]) and v_ph["template"]["placeholders_active"] == 1, str(v_ph["blockers"]))
    ck("负控·离线口径不看资源（只数占位符）", readiness_verdict(clean_tmpl, "", good_inv, live=False)["blockers"] == ["Cloudflare 身份未读到（OAuth 未登录或取不到）"], "离线口径")

    # 负控 13：真跑验收的**判决**必须能被假读数触发（判决自己也是判据，也要有控制）
    def mk_rd(**over):
        good = {
            "base": "http://x",
            "probes": {
                "root": {"status": 200, "body": {"name": "x"}},
                "health": {"status": 200, "body": {"alive": 10, "modules": 10}},
                "mesh": {"status": 200, "body": {"form": "single-isolate", "modules": [{"id": f"m{i}"} for i in range(10)]}},
                "edges_before": {"status": 200, "body": {"declared": {"directed": 90, "self_loops": 0, "asymmetric": 0, "per_module": [{"peers": 9}] * 10}, "observed": {"distinct_edges": 0, "calls": 0}}},
                "full_ping": {"status": 200, "body": {"full_ping": {"tried": 90, "ok": 90}, "edges": {"declared": {"directed": 90}, "observed": {"distinct_edges": 90, "calls": 90}}}},
                "edges_after": {"status": 200, "body": {"declared": {"directed": 90}, "observed": {"distinct_edges": 90, "calls": 90}}},
                "gate_put": {"status": 403, "body": {"missing_scopes": ["process_execute"]}},
                "grants": {"status": 200, "body": {"granted": ["filesystem_write"]}},
                "grant_attempt": {"status": 403, "body": {}},
                "llm_status": {"status": 200, "body": {"reading": "已接线", "backends": [{"weights_ours": False}]}},
                "unc_status": {"status": 200, "body": {"wired": False, "reading": "未读到"}},
                "recall_missing": {"status": 200, "body": {"found": False, "reading": "未读到"}},
            },
        }
        for path, val in over.items():
            node = good["probes"]
            parts = path.split(".")
            for q in parts[:-1]:
                node = node[q]
            node[parts[-1]] = val
        return good

    r_good = judge_live(mk_rd())
    ck("正控·真跑判决：全好 ⇒ 全过", all(x["过"] for x in r_good), f"{sum(x['过'] for x in r_good)}/{len(r_good)}")
    # expect_llm 模式：多收两条判据；喂"空内容 / 假 weights_ours"必须红
    # ⚠️ 必须**在同一份读数上**加，不能 `mk_rd()["probes"][...] = ...` ——
    #    那是往一个临时对象里写，下一行又新建一份 ⇒ 控制自己失真（本轮当场踩到，16/20）
    dam_ok = mk_rd()
    dam_ok["probes"]["llm_complete"] = {"status": 200, "body": {"ok": True, "content": "我是GBT小土豆V8。", "ms": 12, "model": "gbt-potato-v8", "weights_ours": True, "content_path": "choices[0].message.content", "identity_injected": True}}
    dam_ok["probes"]["unc_route"] = {"status": 200, "body": {"ok": True, "content": "本机权重回答"}}
    r_llm_ok = judge_live(dam_ok, expect_llm=True)
    ck("正控·expect_llm：端点真答上 ⇒ 多出的几条也全过", all(x["过"] for x in r_llm_ok), f"{sum(x['过'] for x in r_llm_ok)}/{len(r_llm_ok)}")
    d_bad = mk_rd()
    d_bad["probes"]["llm_complete"] = {"status": 200, "body": {"ok": True, "content": "   ", "ms": 12, "model": "x", "weights_ours": None, "content_path": "未识别"}}
    d_bad["probes"]["unc_route"] = {"status": 200, "body": {"ok": False, "reason": "别的理由"}}
    hits_llm = [x["判据"] for x in judge_live(d_bad, expect_llm=True) if not x["过"]]
    ck("负控·空内容 / 权重归属含混 / 解析未识别 / 别的理由 ⇒ 四条必须各点名", all(any(k in h for h in hits_llm) for k in ("拿到 content", "权重归属", "哪条路", "两种状态")), str(hits_llm))
    ck("负控·不开 expect_llm 就不该有端点那几条（开关真的在起作用）", not any("拿到 content" in x["判据"] for x in judge_live(mk_rd())), "开关")
    # 端点探针自己没通，与"端点答错"是两回事：读数必须分开念，不许静默 None
    d_dead = mk_rd()
    d_dead["probes"]["llm_complete"] = {"status": None, "body": None, "err": "boom"}
    d_dead["probes"]["unc_route"] = {"status": None, "body": None, "err": "boom"}
    notes_dead = [x["读数"] for x in judge_live(d_dead, expect_llm=True) if "探针没通" in x["读数"]]
    ck("负控·端点探针没通 ⇒ 读数写「探针没通」（不许静默 None）", len(notes_dead) == 4, str(len(notes_dead)))
    d_gated = mk_rd()
    d_gated["probes"]["llm_complete"] = {"status": 403, "body": {"denied": True, "missing_scopes": ["external_llm"]}}
    d_gated["probes"]["unc_route"] = {"status": 403, "body": {"denied": True, "missing_scopes": ["external_llm"]}}
    gated_rows = [x for x in judge_live(d_gated, expect_llm=True) if "被门挡住" in x["读数"]]
    ck("负控·被门挡住 ⇒ 读数点名缺哪个作用域（且四条都仍算红）", len(gated_rows) == 4 and all(not x["过"] for x in gated_rows), f"{len(gated_rows)} 条 · 过={sum(x['过'] for x in gated_rows)}")
    bad_cases = [
        ("health.body.alive", 9, "十位全在"),
        ("edges_before.body.declared.directed", 89, "声明边数"),
        ("edges_before.body.declared.self_loops", 1, "无自环"),
        ("edges_before.body.declared.asymmetric", 1, "双向对称"),
        ("full_ping.body.full_ping.ok", 89, "全互通实跑"),
        ("full_ping.body.edges.observed.distinct_edges", 89, "逐条被走过"),
        ("full_ping.body.edges.observed.calls", 5, "至少记下 90 次调用"),
        ("gate_put.status", 200, "门挡住没授权的作用域"),
        ("grant_attempt.status", 200, "自发授权"),
        ("llm_status.body.reading", "说不清", "01 号模型位读数如实"),
        ("unc_status.body.reading", "已接线", "03 号如实分档"),
        ("recall_missing.body.reading", "已读到", "08 号没存过的键"),
    ]
    for path, val, must_fail in bad_cases:
        rows = judge_live(mk_rd(**{path: val}))
        hit = [x for x in rows if not x["过"]]
        ck(f"负控·改坏 {path} ⇒ 必须点名「{must_fail}」",
           any(must_fail in x["判据"] for x in hit), f"红的是 {[x['判据'] for x in hit][:3]}")
    rss = judge_live(mk_rd() | {"probes": {**(mk_rd()["probes"]), "root": {"status": None, "body": None, "err": "boom"}}})
    ck("负控·探针取不到 ⇒ 根路由那条必须红（未读到不算过）", any(not x["过"] and "根路由" in x["判据"] for x in rss), str([x["判据"] for x in rss if not x["过"]]))
    rc_dead = cmd_live("http://127.0.0.1:9", as_json=True, timeout=2.0)
    ck("负控·实例取不到 ⇒ rc=2 且如实报（不许念成通过）", rc_dead == 2, str(rc_dead))
    ur = unreachable_report("http://x", ["boom"])
    ck("正控·取不到读数的报告是结构不是散文", ur == {"base": "http://x", "unread": "该实例取不到读数", "原因": ["boom"]}, str(ur))

    # 负控 15：模型面 + 存储面的判决本身要有控制（不能只靠真跑）
    def mk_full():
        d = mk_rd()
        d["probes"].update({
            "llm_complete": {"status": 200, "body": {"ok": True, "content": "我是GBT小土豆V8。", "ms": 12, "model": "m", "weights_ours": False, "content_path": "choices[0].message.content", "identity_injected": True}},
            "unc_route": {"status": 200, "body": {"ok": False, "reason": "未读到"}},
            "f_put": {"status": 200, "body": {"ok": True, "key": "k.txt", "stored_key": "mesh10/k.txt"}},
            "f_get": {"status": 200, "body": {"ok": True, "text": "GBT存储探针"}},
            "f_list": {"status": 200, "body": {"ok": True, "count": 1, "logical_keys": ["k.txt"]}},
            "f_del": {"status": 200, "body": {"ok": True}},
            "f_get2": {"status": 200, "body": {"ok": False}},
            "m_remember": {"status": 200, "body": {"ok": True, "k": "mk", "sink": "kv"}},
            "m_recall": {"status": 200, "body": {"found": True, "v": "记忆探针"}},
            "m_list": {"status": 200, "body": {"count": 1, "logical_keys": ["mk"]}},
            "o_emit": {"status": 200, "body": {"ok": True, "sink": "r2"}},
            "o_tail": {"status": 200, "body": {"total": 1, "sink": "r2"}},
        })
        return d

    r_full = judge_live(mk_full(), expect_llm=True, expect_storage=True)
    ck("正控·模型面+存储面全好 ⇒ 全过", all(x["过"] for x in r_full), f"{sum(x['过'] for x in r_full)}/{len(r_full)}")
    tamper = [
        (("llm_complete", "body", "content"), None, "拿到 content"),
        (("llm_complete", "body", "weights_ours"), None, "权重归属"),
        (("llm_complete", "body", "content_path"), "未识别", "解析走的是哪条路"),
        (("f_put", "body", "stored_key"), "k.txt", "真落点带 mesh10/ 前缀"),
        (("f_get", "body", "text"), "別的东西", "读得回原文"),
        (("f_list", "body", "logical_keys"), [], "列得出刚写那条"),
        (("f_get2", "body", "ok"), True, "删掉之后读不到"),
        (("m_recall", "body", "found"), False, "KV 写读往返"),
        (("o_tail", "body", "total"), 0, "落账读得回"),
    ]
    for path, val, must_fail in tamper:
        d = mk_full()
        node = d["probes"]
        for q in path[:-1]:
            node = node[q]
        node[path[-1]] = val
        rows = judge_live(d, expect_llm=True, expect_storage=True)
        hit = [x for x in rows if not x["过"]]
        ck(f"负控·改坏 {'.'.join(path)} ⇒ 必须点名「{must_fail}」", any(must_fail in x["判据"] for x in hit), f"红的是 {[x['判据'] for x in hit][:3]}")

    print(f"cloud-mesh selftest：{ok}/{total}")
    for f in fails:
        print("  ✗ " + f)
    return 0 if ok == total else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="10 云插件拼接网 · 生成/对账/边读数/云侧现读/真跑验收")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen")
    g.add_argument("--root", default=None)
    g.add_argument("--mesh", default=None)
    g.add_argument("--check-only", action="store_true")
    g.add_argument("--json", action="store_true")
    c = sub.add_parser("check")
    c.add_argument("--json", action="store_true")
    e = sub.add_parser("edges")
    e.add_argument("--json", action="store_true")
    r = sub.add_parser("readiness")
    r.add_argument("--json", action="store_true")
    r.add_argument("--no-live", action="store_true", help="不跑 wrangler，只数模板占位符")
    lv = sub.add_parser("live", help="对**已部署/已跑起来**的实例量真读数（只读 GET/POST，不部署）")
    lv.add_argument("--url", required=True)
    lv.add_argument("--json", action="store_true")
    lv.add_argument("--timeout", type=float, default=20.0)
    lv.add_argument("--expect-llm", action="store_true", help="额外要求 01 号真打到端点并拿回内容（端点接好后才开）")
    lv.add_argument("--expect-d1", action="store_true", help="额外要求 07 号落在 d1 且写读往返成立（用 wrangler.dev.toml 起的实例）")
    lv.add_argument("--expect-storage", action="store_true", help="额外要求 05/08/10 在真运行时里真写真读（KV/R2 绑定在位）")
    lv.add_argument("--expect-image", action="store_true", help="额外要求 03 号图像面真打到端点并拿回图像字节（IMAGE_ENDPOINT 接好后开）")
    lv.add_argument("--expect-tools", action="store_true", help="额外要求工具调用真转发并回喂结果（先把 tools 发出去再判）")
    lv.add_argument("--token", default=None,
                    help="端点令牌（`GBT_ENDPOINT_TOKEN` 同一个值）—— 云上开了令牌闸就必须给，"
                         "否则 `/v1/chat/completions` 全回 401，读起来像模型坏了")
    lv.add_argument("--token-file", default=None,
                    help="把令牌放在文件里（一行）—— 免得进命令历史；与 `--token` 二选一")
    lv.add_argument("--no-token", action="store_true", help="**故意不带令牌**：量「没带令牌会不会被挡」")
    sub.add_parser("selftest")
    a = ap.parse_args()

    if a.cmd == "live":
        global _TOKEN
        if a.no_token:
            _TOKEN = ""
        elif a.token:
            _TOKEN = a.token.strip()
        elif a.token_file:
            p = Path(a.token_file)
            _TOKEN = p.read_text(encoding="utf-8").strip() if p.is_file() else ""
        else:
            _TOKEN = os.environ.get("GBT_ENDPOINT_TOKEN", "").strip()

    if a.cmd == "gen":
        root = Path(a.root) if a.root else None
        mesh = Path(a.mesh) if a.mesh else None
        return cmd_gen(as_json=a.json, check_only=a.check_only, mesh_path=mesh, out_root=root)
    if a.cmd == "check":
        return cmd_check(as_json=a.json)
    if a.cmd == "edges":
        return cmd_edges(as_json=a.json)
    if a.cmd == "readiness":
        return cmd_readiness(as_json=a.json, do_live=not a.no_live)
    if a.cmd == "live":
        return cmd_live(url=a.url, as_json=a.json, timeout=a.timeout, expect_llm=a.expect_llm, expect_d1=a.expect_d1, expect_storage=a.expect_storage, expect_image=a.expect_image, expect_tools=a.expect_tools)
    if a.cmd == "selftest":
        return selftest()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
