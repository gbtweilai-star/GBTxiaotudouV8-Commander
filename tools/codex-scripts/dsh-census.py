#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DSH 隐藏能力普查探针（**全程只读**）

把《docs/DSH隐藏能力普查与接入方案.md》里 ①逐族清单 与 ③我方能力核对 的读数
**可复跑地**算出来 —— 不抄文档里的数字，每次现读现算：

  ① 装了哪些包        ~/.dsh/profiles/node_modules/@deepseek-ai/（+ web profile 本地的）
  ② 现役启用了哪些    三层补丁现读：bundle 层（dsh-base / dsh-web-app / dsh-llm-qwen-local）
                      + 用户层（profiles/web/cordis.patch.yml）；按 id 逐行 last-write-wins
  ③ 未启用的（隐藏）   装了的包里，既没有挂载行、也不在任何挂载包依赖闭包里的
  ④ 我方 240 能力位    gbt_allinone list 现跑计数 + state/cap-bindings.json 三边绑定读数

纪律（与壳的 w3ConnectDsh 同源）：
  · **只读**：不改 ~/.dsh/** 任何文件、不改本仓除 --out 指定路径外的文件；
  · 不读凭据内容：settings.yaml 只当"有没有这个键"看，绝不进报告；
  · 不试任何需授权的作用域：本探针只读盘、只跑本仓只读命令（list）。

用法：
  py -3.14 tools/codex-scripts/dsh-census.py            # 人读总表
  py -3.14 tools/codex-scripts/dsh-census.py --json     # 机器可读（stdout）
  py -3.14 tools/codex-scripts/dsh-census.py --out state/dsh-census.json

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]          # 仓根 C:/Users/ADMIN/Desktop/GBT小土豆V8
DSH_HOME = Path(os.path.expanduser("~")) / ".dsh"
PROFILE = DSH_HOME / "profiles" / "web"
PKG_DIR = DSH_HOME / "profiles" / "node_modules" / "@deepseek-ai"
WEB_NM = PROFILE / "node_modules"

# ── 族规则（有序；先具体后泛化；全不中 → 兜底族）─────────────────────────────
FAMILY_RULES = [
    ("框架底座·cordis", lambda n: n in {
        "cordis", "cordis-plugin-group", "cordis-plugin-hmr", "cordis-plugin-include",
        "cordis-plugin-loader", "cordis-plugin-timer", "cosmokit", "schemastery",
        "node-addon-system", "dsh-base"}),
    ("CLI/引导", lambda n: n in {
        "dsh", "dsh-app-boot", "dsh-cmdline", "dsh-home-paths", "dsh-launch-environment",
        "dsh-package-manifest"}),
    ("agent 平面", lambda n: n.startswith("dsh-agent")),
    ("动态插件（cordis 双半）", lambda n: n.startswith("dsh-cordis-")),
    ("工作区", lambda n: n in {"dsh-workspace", "dsh-util-workspace-path"}),
    ("引用（@文件/@会话）", lambda n: n.startswith("dsh-file-reference")),
    ("浏览器 UI 插件", lambda n: n.startswith("dsh-client-ui-")),
    ("浏览器内核/传输", lambda n: n.startswith("dsh-client-")),
    ("Host RPC 控制器", lambda n: n.startswith("dsh-api-")),
    ("外部钩子桥", lambda n: n.startswith("dsh-hook")),
    ("代码运行时", lambda n: n.startswith("dsh-code-runtime")),
    ("LLM 适配器", lambda n: n.startswith("dsh-llm")),
    ("模型工具", lambda n: n.startswith("dsh-tool-") or n == "dsh-tools"),
    ("会话与投影", lambda n: n.startswith("dsh-session")),
    ("子代理", lambda n: n.startswith("dsh-subagent")),
    ("工作流", lambda n: n.startswith("dsh-workflow")),
    ("上下文压缩", lambda n: n.startswith("dsh-compaction")),
    ("独立 profile 面（sdk/acp/headless）", lambda n: n.startswith("dsh-sdk-") or n.startswith("dsh-acp") or n == "dsh-headless"),
    ("Web 面", lambda n: n.startswith("dsh-web")),
    ("Host 服务", lambda n: n.startswith("dsh-host-")),
    ("文件系统", lambda n: n.startswith("dsh-fs")),
    ("技能", lambda n: n.startswith("dsh-skill")),
    ("沙箱", lambda n: n.startswith("dsh-sandbox")),
    ("进程与终端", lambda n: n in {
        "dsh-bash-local", "dsh-bash-sandbox", "dsh-pwsh-local", "dsh-pwsh-sandbox",
        "dsh-shell", "dsh-shell-env", "dsh-subprocess", "dsh-subprocess-local",
        "dsh-terminal", "dsh-terminal-bash", "dsh-win32-process", "dsh-http-proxy",
        "dsh-native-command"}),
    ("目标与命令", lambda n: n.startswith("dsh-goal") or n.startswith("dsh-command")),
    ("存储与溢出", lambda n: n in {
        "dsh-storage", "dsh-storage-domain", "dsh-storage-json", "dsh-spill",
        "dsh-spill-local", "dsh-spill-policy", "dsh-atomic-write", "dsh-chunked-list",
        "dsh-deque", "dsh-output-retention"}),
    ("设置与权限", lambda n: n in {
        "dsh-settings", "dsh-settings-file", "dsh-credentials", "dsh-credentials-local",
        "dsh-permission-presets", "dsh-user-approval", "dsh-user-questions",
        "dsh-authorization"}),
    ("附件", lambda n: n.startswith("dsh-attachment")),
    ("Typert 反射", lambda n: n.startswith("dsh-typert")),
    ("作业/调度/消息/Webhook", lambda n: n in {
        "dsh-jobs", "dsh-jobs-local", "dsh-schedule", "dsh-message-feedback",
        "dsh-webhook", "dsh-webhook-github"}),
    ("MCP 桥", lambda n: n.startswith("dsh-mcp")),
    ("人设/提示/上下文/时间", lambda n: n in {
        "dsh-persona", "dsh-system-prompt", "dsh-plan-mode", "dsh-token-meter",
        "dsh-time-context", "dsh-tmux-context", "dsh-repeat-tool-reminder"}),
    ("零依赖底座件", lambda n: n.startswith("dsh-util-") or n in {
        "dsh-timeout", "dsh-scope", "dsh-invariants", "dsh-brand",
        "dsh-anonymous-user-id", "dsh-plugin-package-inventory-deepseek",
        "dsh-deepseek-llm-api-extensions"}),
]


def family_of(name_base: str) -> str:
    for fam, pred in FAMILY_RULES:
        if pred(name_base):
            return fam
    return "其它（未归类）"


# ── YAML：官方补丁里有 !!js 标记；只留占位，不求值（我们只读结构）────────────
class _YamlLoose(yaml.SafeLoader):
    pass


def _js_scalar(loader, tag_suffix, node):
    """`!!js` 表达式的原样文本（**不求值**）—— 我们只认里面写死的平台判据，见 resolve_disabled。"""
    if isinstance(node, yaml.ScalarNode):
        return node.value
    return "<js>"


_YamlLoose.add_multi_constructor("tag:yaml.org,2002:js", _js_scalar)
_YamlLoose.add_multi_constructor("!", lambda l, s, n: "<tag:%s>" % s)


def resolve_disabled(val):
    """行的 disabled → (True/False/None, 原始表达式)。

    只解官方在 preset 里用的**两种平台判据**（原文里写死），别的一律留 None = 存疑，
    不当 True 也不当 False —— 普查不许替官方求值任意 JS。
    """
    if val is None:
        return False, None
    if isinstance(val, bool):
        return val, None
    s = str(val)
    win = sys.platform.startswith("win")
    if "platform === 'win32'" in s or 'platform === "win32"' in s:
        return (win), s
    if "platform !== 'win32'" in s or 'platform !== "win32"' in s:
        return (not win), s
    return None, s


def load_yaml(path: Path):
    with open(path, encoding="utf-8") as fh:
        return yaml.load(fh, Loader=_YamlLoose)


def sha256_file(path: Path) -> str:
    try:
        h = hashlib.sha256()
        h.update(path.read_bytes())
        return h.hexdigest()[:16]
    except OSError:
        return "<unreadable>"


# ── ① 装了什么 ──────────────────────────────────────────────────────────────
def read_installed() -> dict:
    """@deepseek-ai 作用域下 240 个包（现读 package.json 的 name/version/description）。"""
    out = {}
    if not PKG_DIR.is_dir():
        return out
    for entry in sorted(PKG_DIR.iterdir()):
        pj = entry / "package.json"
        if not pj.is_file():
            continue
        try:
            d = json.loads(pj.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out[entry.name] = {
            "name": d.get("name") or ("@deepseek-ai/" + entry.name),
            "version": d.get("version"),
            "desc": (d.get("description") or "").strip().replace("\n", " "),
        }
    return out


def read_profile_local() -> dict:
    """web profile 自己 node_modules 里的件（非 240 的：我们的包与 qwen-local bundle）。"""
    out = {}
    if not WEB_NM.is_dir():
        return out
    for entry in sorted(WEB_NM.iterdir()):
        if entry.name.startswith("@"):
            continue
        pj = entry / "package.json"
        if not pj.is_file():
            continue
        try:
            d = json.loads(pj.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out[entry.name] = {
            "name": d.get("name") or entry.name,
            "version": d.get("version"),
            "desc": (d.get("description") or "").strip().replace("\n", " "),
            "ours": bool(d.get("_gbt") or (d.get("name") or "").startswith("gbt-")),
        }
    return out


# ── ② 现役挂载图：三层补丁逐行解析 ──────────────────────────────────────────
def layer_paths() -> list:
    """按 dsh CLI 的合成顺序：profile.package.json 的 bundles 顺序 → 用户 cordis.patch.yml。"""
    layers = []
    try:
        prof = json.loads((PROFILE / "package.json").read_text(encoding="utf-8"))
        bundles = (prof.get("dsh", {}).get("profile", {}) or {}).get("bundles", []) or []
    except (OSError, ValueError):
        bundles = []
    for b in bundles:
        # 解析 bundle 包所在目录：@scope/name → scope 目录；裸名 → web/node_modules
        if b.startswith("@"):
            scope, _, base = b.partition("/")
            cand = [DSH_HOME / "profiles" / "node_modules" / scope / base, WEB_NM / scope / base]
        else:
            cand = [WEB_NM / b]
        pkgjson = next((c / "package.json" for c in cand if (c / "package.json").is_file()), None)
        if not pkgjson:
            layers.append({"layer": "bundle:" + b, "path": None, "rows": [], "overrides": []})
            continue
        try:
            meta = json.loads(pkgjson.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            meta = {}
        patch_rel = ((meta.get("dsh") or {}).get("bundle") or {}).get("patch") or "./cordis.patch.yml"
        patch = pkgjson.parent / patch_rel
        layers.append(parse_layer(patch, "bundle:" + b))
    layers.append(parse_layer(PROFILE / "cordis.patch.yml", "user"))
    return layers


def parse_layer(path: Path, layer_name: str) -> dict:
    rows, overrides = [], []
    if path is None or not path.is_file():
        return {"layer": layer_name, "path": None, "rows": [], "overrides": []}
    doc = load_yaml(path)
    for entry in doc or []:
        if not isinstance(entry, dict):
            continue
        if "insert" in entry and isinstance(entry["insert"], list):
            for row in entry["insert"]:
                if isinstance(row, dict):
                    dis, dis_expr = resolve_disabled(row.get("disabled"))
                    rows.append({
                        "id": row.get("id"),
                        "name": row.get("name"),
                        "disabled": bool(dis),
                        "disabled_raw": dis_expr,
                        "config_keys": sorted((row.get("config") or {}).keys())
                        if isinstance(row.get("config"), dict) else [],
                    })
        elif "id" in entry:
            dis, dis_expr = resolve_disabled(entry.get("disabled")) \
                if "disabled" in entry else (None, None)
            overrides.append({
                "id": entry.get("id"),
                "disabled": dis if "disabled" in entry else None,
                "disabled_raw": dis_expr,
                "config_keys": sorted((entry.get("config") or {}).keys())
                if isinstance(entry.get("config"), dict) else [],
            })
    return {"layer": layer_name, "path": str(path), "sha256_16": sha256_file(path),
            "rows": rows, "overrides": overrides}


def base_pkg(name: str) -> str:
    """行 name → 包裸名。'@deepseek-ai/dsh-tool-subagent/list-agents' → 'dsh-tool-subagent'。"""
    n = str(name or "")
    if n.startswith("@"):
        scope, _, rest = n.partition("/")
        rest = rest.split("/")[0]
        return rest
    return n.split("/")[0]


def build_effective(layers: list) -> dict:
    """逐行合成：insert 建行；override 按 id 改写（last-write-wins）。"""
    rows = {}
    for L in layers:
        for r in L["rows"]:
            if not r.get("id"):
                continue
            rows[r["id"]] = {"id": r["id"], "name": r.get("name"),
                             "disabled": bool(r.get("disabled")), "layer": L["layer"],
                             "config_keys": r.get("config_keys") or []}
        for o in L["overrides"]:
            rid = o.get("id")
            if rid not in rows:
                rows[rid] = {"id": rid, "name": None, "disabled": False,
                             "layer": L["layer"] + "(override-orphan)", "config_keys": []}
            rows[rid]["layer"] += "+" + L["layer"] + "(override)" if L["layer"] not in rows[rid]["layer"] else ""
            if o.get("disabled") is not None:
                rows[rid]["disabled"] = bool(o.get("disabled"))
            if o.get("config_keys"):
                rows[rid]["config_keys"] = o["config_keys"]
    return rows


# ── 依赖闭包（捆进现役树但无挂载行的"库件"）──────────────────────────────────
def dep_closure(seed_pkgs: set, installed: dict) -> set:
    """在**已装集合内**求传递依赖闭包（只看 @deepseek-ai 作用域内的包）。"""
    seen, stack = set(), list(seed_pkgs)
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        pj = (PKG_DIR / cur / "package.json") if (PKG_DIR / cur).is_dir() else (WEB_NM / cur / "package.json")
        if not pj.is_file():
            continue
        try:
            d = json.loads(pj.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for dep in list((d.get("dependencies") or {}).keys()) + list((d.get("peerDependencies") or {}).keys()):
            if dep.startswith("@deepseek-ai/"):
                nb = dep.split("/")[1]
                if nb in installed and nb not in seen:
                    stack.append(nb)
    return seen


# ── 会话面：agent preset（**Web 面的 agent 平面都在这后面**）──────────────────
def preset_usage() -> dict:
    """shipped presets（dsh-agent-presets/presets/*）+ 用户 presets（~/.dsh/.agent-presets/*）。

    为什么必须算这一层：web 补丁把 agent 平面的行（tool-bash / tool-fs / tool-subagent…）
    在宿主面**全部 disable**，改由每个会话按 preset 挂 —— 只看宿主行会把
    "现役会话正在用"的包误报成未启用。默认 preset 现读 settings.yaml 的
    `agent-presets.default`（只读这一个键，不碰其余内容）。
    """
    presets = {}
    shipped = PKG_DIR / "dsh-agent-presets" / "presets"
    user = DSH_HOME / ".agent-presets"
    for base, trust in ((shipped, "system"), (user, "user")):
        if not base.is_dir():
            continue
        for d in sorted(base.iterdir()):
            f = d / "agent.cordis.yml"
            if not f.is_file():
                continue
            doc = load_yaml(f)
            en, dis, unk = [], [], []

            def walk(rows):
                for r in rows or []:
                    if not isinstance(r, dict):
                        continue
                    nb = base_pkg(r.get("name") or "")
                    if nb:
                        if r.get("disabled") is None:
                            en.append(nb)
                        else:
                            v, expr = resolve_disabled(r.get("disabled"))
                            if v is True:
                                dis.append(nb)
                            elif v is False:
                                en.append(nb)
                            else:
                                unk.append([nb, expr])
                    if r.get("name") == "cordis:group" and isinstance(r.get("config"), list):
                        walk(r["config"])

            walk(doc)
            presets[d.name] = {"path": str(f), "trust": trust,
                               "sha256_16": sha256_file(f),
                               "enabled": sorted(set(en)), "disabled": sorted(set(dis)),
                               "unresolved": unk}
    default = None
    try:
        st = load_yaml(DSH_HOME / "settings.yaml") or {}
        default = (st.get("agent-presets") or {}).get("default")
    except Exception:  # noqa: BLE001 —— 读不到就如实留 None
        default = None
    return {"default": default, "presets": presets}


# ── ③ 我方能力（真源现读）────────────────────────────────────────────────────
def our_side() -> dict:
    out = {"why": "我方能力位的真源读数：gbt_allinone list 现跑 + state/cap-bindings.json 现读"}
    # 240 位：跑 list 数行（只读命令）
    try:
        r = subprocess.run([sys.executable, "-m", "gbt_allinone", "list"],
                           cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120)
        n = sum(1 for line in (r.stdout or "").splitlines() if line.startswith("  - "))
        out["gbt_allinone_list_count"] = n
        out["gbt_allinone_rc"] = r.returncode
    except Exception as e:  # noqa: BLE001 —— 探针不因外件失败而炸
        out["gbt_allinone_list_count"] = None
        out["gbt_allinone_error"] = str(e)[:200]
    # 三边绑定：读台账计数（不重算，引用真源）
    cb = ROOT / "state" / "cap-bindings.json"
    try:
        d = json.loads(cb.read_text(encoding="utf-8"))
        out["cap_bindings"] = {
            "path": "state/cap-bindings.json",
            "generated_at": d.get("generated_at"),
            "counts": d.get("counts"),
            "orphans_zero": {
                k: (len(v) if isinstance(v, list) else v)
                for k, v in (d.get("orphans") or {}).items()},
        }
    except (OSError, ValueError) as e:
        out["cap_bindings"] = {"error": str(e)[:200]}
    return out


# ── 主流程 ──────────────────────────────────────────────────────────────────
def census() -> dict:
    installed = read_installed()
    local = read_profile_local()
    layers = layer_paths()
    rows = build_effective(layers)
    presets = preset_usage()

    mounted = {}          # 包裸名 → [行 id…]
    for rid, r in sorted(rows.items()):
        nb = base_pkg(r.get("name") or "")
        if not nb or nb in ("cordis:group",):
            continue
        mounted.setdefault(nb, []).append(rid)

    seed = {nb for nb, rids in mounted.items()
            if any(not rows[r]["disabled"] for r in rids)}
    closure = dep_closure(seed | set(local.keys()), installed)

    pkgs = {}
    # 两个特殊态：bundle 层本身就是"现役"（它不是一个行，是补丁层本身）；
    # `dsh` 是入口 CLI（壳/主人敲的就是它），更不该算"未启用"。
    BUNDLE_PKGS = {"dsh-base", "dsh-web-app", "dsh-llm-qwen-local"}
    ENTRY_PKGS = {"dsh"}
    for nb, meta in installed.items():
        rids = mounted.get(nb, [])
        row_disabled = bool(rids) and all(rows[r]["disabled"] for r in rids)
        in_preset = any(nb in p["enabled"] for p in presets["presets"].values())
        if rids and not row_disabled:
            status = "mounted"                       # 现役行（宿主面挂载并启用）
        elif rids and row_disabled:
            status = "row-disabled"                  # 宿主行被本面禁用（web 面常态：agent 平面移到 preset）
        elif nb in BUNDLE_PKGS:
            status = "bundle"                        # 现役补丁层本身
        elif nb in ENTRY_PKGS:
            status = "entry"                         # 现役入口 CLI
        elif nb in closure:
            status = "dep"                           # 无行，但被现役树依赖
        elif in_preset:
            status = "preset"                        # 宿主面无行，但**会话预设挂了它**（现役）
        else:
            status = "dormant"                       # 哪一层都没启用（隐藏能力主清单）
        pkgs[nb] = {
            "name": meta["name"], "version": meta["version"], "desc": meta["desc"],
            "family": family_of(nb), "status": status,
            "row_ids": rids,
            "row_layer": rows[rids[0]]["layer"] if rids else None,
            "preset_enabled": sorted(pid for pid, p in presets["presets"].items()
                                     if nb in p["enabled"]),
            "preset_disabled": sorted(pid for pid, p in presets["presets"].items()
                                      if nb in p["disabled"]),
            "default_preset": bool(presets.get("default")
                                   and nb in (presets["presets"].get(presets["default"], {})
                                              .get("enabled") or [])),
        }

    fams = {}
    for nb, p in pkgs.items():
        f = fams.setdefault(p["family"], {"installed": 0, "mounted": 0, "row_disabled": 0,
                                          "dep": 0, "bundle": 0, "entry": 0, "preset": 0,
                                          "preset_mounted": 0, "dormant": 0,
                                          "dormant_list": [], "mounted_list": []})
        f["installed"] += 1
        f[p["status"].replace("-", "_")] += 1
        if p["preset_enabled"]:
            f["preset_mounted"] += 1
        if p["status"] == "dormant":
            f["dormant_list"].append(nb)
        if p["status"] == "mounted":
            f["mounted_list"].append(nb)

    # profile 本地件（我们自己的 + qwen-local）
    local_rows = []
    for nb, meta in local.items():
        rids = mounted.get(nb, [])
        local_rows.append({
            "pkg": nb, "name": meta["name"], "version": meta["version"],
            "ours": meta.get("ours"), "row_ids": rids,
            "row_disabled": bool(rids) and all(rows[r]["disabled"] for r in rids),
        })

    return {
        "probe": "tools/codex-scripts/dsh-census.py（只读；--json）",
        "sources": {
            "installed_dir": str(PKG_DIR),
            "profile_dir": str(PROFILE),
            "layers": [{"layer": L["layer"], "path": L["path"],
                        "sha256_16": L.get("sha256_16")} for L in layers],
        },
        # 官方 APP 面（`dsh web` = --profile web）在壳里的接入锚点 —— 只记文件与行，
        # **本次未执行任何改动**；改动方案见 docs/DSH隐藏能力普查与接入方案.md §②。
        "app_surface": {
            "what": "官方 APP = @deepseek-ai/dsh-web-app 的 Web GUI（dsh web = --profile web）",
            "shell_window": "dsh-chat（holo_pet_w3/shell/windows.json）",
            "anchors": [
                {"file": "holo_pet_w3/shell/windows.json", "line": "65",
                 "what": "file=../shell/connect.html（兜底引导页；默认隐藏）"},
                {"file": "holo_pet_w3/shell/windows.json", "line": "72-80",
                 "what": "auto_dsh：壳自拉 dsh web --no-open，就绪行 URL 交 w3ConnectDsh"},
                {"file": "holo_pet_w3/shell/main.cjs", "line": "1305-1324",
                 "what": "auto_dsh 接线（条件 + onUrl → w3ConnectDsh + 关窗收子进程）"},
                {"file": "holo_pet_w3/shell/main.cjs", "line": "1430-1469",
                 "what": "w3ConnectDsh：过回环白名单 → win.loadURL(tokenURL)；只回 host；落不含 token 回执"},
                {"file": "holo_pet_w3/shell/dsh-launch.cjs", "line": "27-50",
                 "what": "就绪行解析（缺 token 判失败）· 端口占用改 --port 0 另起"},
                {"file": "holo_pet_w3/panel/index.html", "line": "95-105",
                 "what": "面板左栏**故意不挂** dsh-chat 的原文理由（token 口不在 webview）"},
            ],
            "note": "以上为**现状锚点**；§② 的改动点（若要执行）全部落在这些文件上，本次未执行。",
        },
        "counts": {
            "installed": len(installed),
            "mounted": sum(1 for p in pkgs.values() if p["status"] == "mounted"),
            "row_disabled": sum(1 for p in pkgs.values() if p["status"] == "row-disabled"),
            "bundle": sum(1 for p in pkgs.values() if p["status"] == "bundle"),
            "entry": sum(1 for p in pkgs.values() if p["status"] == "entry"),
            "preset_status": sum(1 for p in pkgs.values() if p["status"] == "preset"),
            "dep": sum(1 for p in pkgs.values() if p["status"] == "dep"),
            "dormant": sum(1 for p in pkgs.values() if p["status"] == "dormant"),
            "rows_total": len(rows),
            "rows_enabled": sum(1 for r in rows.values() if not r["disabled"]),
            "profile_local": len(local),
            "preset_enabled_pkgs": sum(1 for p in pkgs.values() if p["preset_enabled"]),
            "default_preset_pkgs": sum(1 for p in pkgs.values() if p["default_preset"]),
            "presets": len(presets["presets"]),
            "preset_default": presets.get("default"),
        },
        "presets": presets,
        "families": {k: v for k, v in sorted(fams.items(), key=lambda kv: -kv[1]["installed"])},
        "packages": pkgs,
        "dormant": sorted(nb for nb, p in pkgs.items() if p["status"] == "dormant"),
        "row_disabled": sorted(nb for nb, p in pkgs.items() if p["status"] == "row-disabled"),
        "profile_local": local_rows,
        "rows": {rid: r for rid, r in sorted(rows.items())},
        "ours": our_side(),
    }


def render_text(c: dict) -> str:
    out = []
    out.append("DSH 隐藏能力普查（只读探针 · 现读现算）")
    out.append("=" * 74)
    out.append("层（合成顺序）：" + " → ".join(L["layer"] for L in
               ([{"layer": x["layer"]} for x in c["sources"]["layers"]])))
    cc = c["counts"]
    out.append("包：装 %d · 宿主面挂载 %d · 宿主行被禁 %d · 库件(闭包) %d · bundle %d · 入口 %d"
               " · 仅预设挂载 %d · **未启用 %d**"
               % (cc["installed"], cc["mounted"], cc["row_disabled"], cc["dep"],
                  cc.get("bundle", 0), cc.get("entry", 0), cc.get("preset_status", 0),
                  cc["dormant"]))
    out.append("行：共 %d · 启用 %d · 预设 %d 个（默认 %s）· 被预设挂载的包 %d"
               % (cc["rows_total"], cc["rows_enabled"], cc.get("presets", 0),
                  cc.get("preset_default"), cc.get("preset_enabled_pkgs", 0)))
    out.append("")
    out.append("逐族（装 / 宿主挂载 / 宿主行被禁 / 库件 / 被预设挂载 / 未启用）：")
    for fam, f in c["families"].items():
        out.append("  %-26s %3d / %3d / %2d / %3d / %3d / **%2d** %s"
                   % (fam, f["installed"], f["mounted"], f["row_disabled"], f["dep"],
                      f.get("preset_mounted", 0), f["dormant"],
                      ("  未启用：" + " ".join(f["dormant_list"])) if f["dormant_list"] else ""))
    out.append("")
    out.append("profile 本地件（非 240）：")
    for r in c["profile_local"]:
        out.append("  %-28s v%s ours=%s rows=%s" % (r["pkg"], r["version"], r["ours"], r["row_ids"]))
    out.append("")
    o = c["ours"]
    out.append("我方：gbt_allinone list = %s 位" % o.get("gbt_allinone_list_count"))
    cb = o.get("cap_bindings") or {}
    if cb.get("counts"):
        k = cb["counts"]
        out.append("      能力 %s · 触手承载 %s · 直连 %s · 未绑 %s · 触手域 %s（%s 项）"
                   " · 能量通道 %s（活 %s）· 标签 %s"
                   % (k.get("caps"), k.get("caps_tentacle"), k.get("caps_direct"),
                      k.get("caps_unbound"), k.get("tentacle_domains"), k.get("tentacle_items"),
                      k.get("energy_channels"), k.get("energy_alive"), k.get("labels")))
        out.append("      孤儿项读数：%s" % json.dumps(cb.get("orphans_zero"), ensure_ascii=False))
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="DSH 隐藏能力普查（只读）")
    ap.add_argument("--json", action="store_true", help="输出 JSON 到 stdout")
    ap.add_argument("--out", default=None, help="把 JSON 写到指定路径（相对仓根）")
    args = ap.parse_args()

    c = census()
    if args.out:
        dest = Path(args.out)
        if not dest.is_absolute():
            dest = ROOT / dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
        print("已写 %s（%d 字节）" % (dest, dest.stat().st_size))
    if args.json:
        print(json.dumps(c, ensure_ascii=False, indent=1))
    elif not args.out:
        print(render_text(c))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
