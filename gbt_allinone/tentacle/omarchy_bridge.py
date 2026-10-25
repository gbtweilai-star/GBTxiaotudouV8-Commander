# -*- coding: utf-8 -*-
# gbt-capability: process_execute, filesystem_write  ⬻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""Omarchy 桥（omarchy_bridge）—— 把小土豆接到 Omarchy 桌面的三根官方线上。

来源与口径（2026-10-15 现读官方文档 + 官方仓 omacom/omarchy，默认分支 quattro）：
  · CLI        ：`omarchy <group> <command>`；机读面 `omarchy commands --json`。
  · shell IPC  ：`omarchy-shell <target> <method> [args]`，转发给运行中的 shell；
                 socket = $XDG_RUNTIME_DIR/omarchy-shell-<md5(OMARCHY_PATH/shell + WAYLAND_DISPLAY)>.sock
  · Hyprland   ：hyprctl + $XDG_RUNTIME_DIR/hypr/*.sock。官方警告：socket **同步求值**，
                 连接不关会让 Hyprland 冻结到 5 秒超时 ⇒ 本件一律一次性调用、用完即断。

三条纪律（照本仓既有口径，不是新发明）：
  ① **没装就如实报**：探不到 Omarchy / 没有活动 Wayland 会话 ⇒ ok=false + reason；
  ② **门按 op 挂**：本件每个 op 都会起探针（which / wsl / hyprctl）⇒ 读类也挂 process_execute；
     只有改状态的 op（set_theme / plugin_add / dispatch / eval）才追加 filesystem_write；
     未知 op **fail-closed**（只回错，不执行任何东西）。
  ③ **门保留**：AI 无权自授；缺票就回 needs_grant 并给 auth grant 的原文命令。

⚠ 边界：**WSL2 里跑不了 Hyprland**（没有 DRM/KMS 与独立显示会话），WSL 那一栏只做
"装没装"的探针，不做"接上桌面"的承诺。本件也不装 Omarchy、不写它的配置。
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

READ_OPS = ("assess", "list", "discover", "events", "window", "clients", "observe_history",
            "shell_targets", "shell_call")
# observe 默认会落盘（可 write=False）⇒ 单列一组，不混进纯读里
WRITE_OPS = ("set_theme", "theme_install", "plugin_add", "plugin_rm",
             "plugin_enable", "plugin_disable", "dispatch", "eval")
_ALLOW_ROUTE = {
    "theme": ("list", "current", "set", "install"),   # install 走 theme_install op（needs_owner_confirm）
    "plugin": ("list", "enable", "disable", "add", "remove"),
    "agent": ("list", "status"),
    "bar": ("status", "notch"),
    "debug": ("info", "logs"),
    "config": ("show", "get"),
    "commands": ("",),
    "capture": ("screenshot", "screenrecording", "qr"),
    "clipboard": ("list", "show", "read"),
    "notify": ("send", "show"),
    "audio": ("status", "list"),
    "battery": ("status", "list"),
    "brightness": ("status", "get"),
    "monitors": ("list", "status"),
}
_MAX_OUT = 4000


def _run(cmd, timeout=25, env_extra=None):
    """一次性调用，绝不挂长连接（Hyprland socket 同步求值，挂着会冻 5 秒）。"""
    env = None
    if env_extra:
        env = dict(os.environ)
        env.update(env_extra)
    try:
        cp = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env)
        out = ((cp.stdout or b"") + (cp.stderr or b"")).decode("utf-8", "replace")
        return {"ok": cp.returncode == 0, "rc": cp.returncode, "out": out[:_MAX_OUT]}
    except Exception as exc:                                       # noqa: BLE001
        return {"ok": False, "rc": None,
                "out": ("%s: %s" % (type(exc).__name__, exc))[:300]}


def _runtime_dir(home: Path) -> Path:
    """XDG_RUNTIME_DIR：Linux 常规是 /run/user/<uid>；探不到就退回 home 下的推断位。"""
    return Path(os.environ.get("XDG_RUNTIME_DIR") or (home / ".cache"))


def socket_name(omarchy_path: str, wayland_display: str) -> str:
    """官方 socket 名 = omarchy-shell-<md5(OMARCHY_PATH/shell + WAYLAND_DISPLAY)>.sock。

    写死路径必挂 —— 这里照官方算法现算（出处 bin/omarchy-shell）。
    """
    raw = ("%s/shell%s" % (omarchy_path.rstrip("/"), wayland_display)).encode("utf-8")
    return "omarchy-shell-%s.sock" % hashlib.md5(raw).hexdigest()


def _local() -> dict:
    """宿主现读（不是猜）：三个 bin、配置目录、运行时会话标记。"""
    home = Path(os.path.expanduser("~"))
    bins = {n: shutil.which(n) for n in ("omarchy", "omarchy-shell", "hyprctl")}
    conf = home / ".config" / "omarchy"
    rt = _runtime_dir(home)
    wayland = os.environ.get("WAYLAND_DISPLAY") or ""
    his = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") or ""
    omp = os.environ.get("OMARCHY_PATH") or ""
    sock = ""
    if omp and wayland:
        cand = rt / socket_name(omp, wayland)
        sock = str(cand) if cand.exists() else ""
    shells = []
    try:
        shells = sorted(p.name for p in rt.glob("omarchy-shell-*.sock"))
    except OSError:
        shells = []
    hypr = []
    try:
        hypr = sorted(p.name for p in (rt / "hypr").glob("*.sock")) if (rt / "hypr").is_dir() else []
    except OSError:
        hypr = []
    return {
        "bin": bins,
        "config_dir": {"path": str(conf), "exists": conf.is_dir()},
        "omarchy_path": omp,
        "wayland_display": wayland,
        "hyprland_instance": his,
        "session_markers": {"wayland": bool(wayland), "hyprland": bool(his)},
        "shell_socket": {"computed": sock, "found": shells},
        "hypr_sockets": hypr,
        "usable": bool(bins.get("omarchy") and (sock or shells or bins.get("hyprctl"))),
        "installed": bool(bins.get("omarchy") or conf.is_dir() or omp),
    }


def _wsl_distros() -> list:
    if not shutil.which("wsl"):
        return []
    d = _run(["wsl", "-l", "-q"], timeout=30)
    return [x.strip() for x in (d.get("out") or "").replace("\x00", "").splitlines() if x.strip()]


_WSL_PROBE = (
    "echo 'OMARCHY_PATH='\"$OMARCHY_PATH\";"
    "echo 'WAYLAND_DISPLAY='\"$WAYLAND_DISPLAY\";"
    "echo 'OMARCHY_CLI='$(command -v omarchy 2>/dev/null || echo none);"
    "echo 'HYPRCTL='$(command -v hyprctl 2>/dev/null || echo none);"
    "if [ -d \"$HOME/.config/omarchy\" ]; then echo 'OMARCHY_CONFIG=yes'; else echo 'OMARCHY_CONFIG=no'; fi;"
    "if [ -f /usr/share/omarchy/VERSION ]; then echo 'OMARCHY_SHARE=yes'; else echo 'OMARCHY_SHARE=no'; fi"
)

def _wsl_side(distro: str) -> dict:
    """WSL 里**只探装没装**，不承诺接上桌面（WSL2 没有 DRM/KMS，Hyprland 起不来）。"""
    r = _run(["wsl", "-d", distro, "-e", "bash", "-lc", _WSL_PROBE], timeout=60)
    out = (r.get("out") or "").replace("\x00", "")
    got = {}
    for line in out.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            got[k.strip()] = v.strip()
    # 空值与未设置都算"没有"（bash 里 ${VAR} 两者都是空串）——
    #   旧写法用"含 .config/omarchy"判装没装，回显一出现就会假绿（本仓口径：假绿比报错更坏）。
    has_path = bool(got.get("OMARCHY_PATH", "").strip())
    has_cli = got.get("OMARCHY_CLI", "none").strip() not in ("", "none")
    has_conf = got.get("OMARCHY_CONFIG") == "yes"
    has_share = got.get("OMARCHY_SHARE") == "yes"
    return {"distro": distro, "probe_ok": bool(r.get("ok")), "raw": out[:600],
            "omarchy_path": got.get("OMARCHY_PATH", "none"),
            "wayland_display": got.get("WAYLAND_DISPLAY", "none"),
            "installed": bool(has_cli or has_conf or has_share or has_path),
            "note": "WSL2 无显示会话 ⇒ 只探装没装；要接桌面得用真机/双系统"}


def assess() -> dict:
    """现读两侧：宿主能不能接、WSL 里装没装。只读，不改任何状态。"""
    loc = _local()
    wsl = [{"distro": x, "installed": None} for x in _wsl_distros()]
    return {"ok": True, "op": "assess", "host": loc, "wsl": wsl,
            "verdict": ("host_ready" if loc["usable"] else
                        ("host_installed_no_session" if loc["installed"] else "host_not_found")),
            "how_to_install": "官方 ISO 装机（Arch+Hyprland+Quickshell）；支持 cidata 无人值守装、"
                              "支持与 Windows 双系统；装机需在 BIOS 关 Secure Boot/TPM"}


def probe_wsl(distro: str = "") -> dict:
    """探一个 WSL 发行版里 Omarchy 的痕迹（只读）。不给 distro 就用第一个。"""
    ds = _wsl_distros()
    if not ds:
        return {"ok": False, "op": "probe_wsl", "reason": "no_wsl_distro",
                "detail": "本机没有 WSL 发行版"}
    target = distro or ds[0]
    if target not in ds:
        return {"ok": False, "op": "probe_wsl", "reason": "unknown_distro",
                "detail": "可选：%s" % ", ".join(ds)}
    return {"ok": True, "op": "probe_wsl", "wsl": _wsl_side(target)}


def _cli(bin_: str, route: str, sub: str = "", extra=None) -> dict:
    if route not in _ALLOW_ROUTE:
        return {"ok": False, "reason": "route_not_allowed", "detail": "白名单外：%s" % route}
    if sub and sub not in _ALLOW_ROUTE[route]:
        return {"ok": False, "reason": "subcommand_not_allowed",
                "detail": "%s 只放行：%s" % (route, ", ".join(x or "(空)" for x in _ALLOW_ROUTE[route]))}
    cmd = [bin_, route] + ([sub] if sub else []) + list(extra or [])
    return _run(cmd, timeout=30)


def list_commands(bin_: str = "") -> dict:
    """机读命令表（omarchy commands --json，失败退回逐行文本）。只读。"""
    b = bin_ or shutil.which("omarchy")
    if not b:
        return {"ok": False, "op": "list", "reason": "omarchy_not_in_path",
                "detail": "宿主现读：PATH 里没有 omarchy"}
    j = _run([b, "commands", "--json"], timeout=30)
    if j["ok"] and (j["out"] or "").lstrip().startswith(("[", "{")):
        try:
            return {"ok": True, "op": "list", "format": "json", "commands": json.loads(j["out"])}
        except ValueError:
            pass
    t = _run([b, "commands"], timeout=30)
    lines = [x.strip() for x in (t.get("out") or "").splitlines() if x.strip()]
    return {"ok": bool(t.get("ok")), "op": "list", "format": "text",
            "count": len(lines), "commands": lines[:200]}


def _guard_write(op: str) -> dict:
    """写类 op 的前闸：**没接上就拒**，并把缺的东西说清楚（fail-closed）。"""
    loc = _local()
    if not loc["installed"]:
        return {"ok": False, "reason": "omarchy_not_installed", "op": op,
                "detail": "本机没有 omarchy 命令、没有 ~/.config/omarchy、没有 OMARCHY_PATH",
                "enable": "先按官方 ISO 装 Omarchy（或双系统），再把本件指向那台机器"}
    if not (loc["shell_socket"]["computed"] or loc["shell_socket"]["found"] or loc["bin"].get("hyprctl")):
        return {"ok": False, "reason": "no_active_session", "op": op,
                "detail": "装了但当前没有活动 Wayland/Hyprland 会话（Omarchy 的 IPC 只在本机会话内有效）",
                "enable": "在 Omarchy 桌面会话里调用本件（WAYLAND_DISPLAY / HYPRLAND_INSTANCE_SIGNATURE 必须在）"}
    return {"ok": True}


def set_theme(name: str) -> dict:
    """改主题（写类）：只调官方 omarchy theme set，不自己拼配置。"""
    g = _guard_write("set_theme")
    if not g["ok"]:
        return g
    if not name:
        return {"ok": False, "op": "set_theme", "reason": "needs_name"}
    r = _cli(shutil.which("omarchy") or "omarchy", "theme", "set", [name])
    return {"ok": bool(r.get("ok")), "op": "set_theme", "theme": name, "raw": r.get("out", "")}


def plugin(op_action: str, plugin_id: str = "", source: str = "") -> dict:
    """插件面：enable/disable/list/add/remove —— **add 会执行第三方代码**，必须主人点头。"""
    b = shutil.which("omarchy") or "omarchy"
    if op_action == "list":
        if not shutil.which("omarchy"):
            return {"ok": False, "op": "plugin_list", "reason": "omarchy_not_in_path"}
        r = _cli(b, "plugin", "list", ["--json"])
        if r["ok"] and (r["out"] or "").lstrip().startswith(("[", "{")):
            try:
                return {"ok": True, "op": "plugin_list", "plugins": json.loads(r["out"])}
            except ValueError:
                pass
        return {"ok": bool(r.get("ok")), "op": "plugin_list", "format": "text", "raw": r.get("out", "")}
    g = _guard_write("plugin_%s" % op_action)
    if not g["ok"]:
        return g
    if op_action in ("enable", "disable"):
        if not plugin_id:
            return {"ok": False, "op": "plugin_%s" % op_action, "reason": "needs_plugin_id"}
        r = _cli(b, "plugin", op_action, [plugin_id])
        return {"ok": bool(r.get("ok")), "op": "plugin_%s" % op_action,
                "plugin": plugin_id, "raw": r.get("out", "")}
    if op_action in ("add", "remove"):
        if not source:
            return {"ok": False, "op": "plugin_%s" % op_action, "reason": "needs_source"}
        if op_action == "add":
            return {"ok": False, "op": "plugin_add", "reason": "needs_owner_confirm",
                    "detail": "插件在 omarchy-shell 进程内以无沙箱任意代码运行（官方原文）；"
                              "装前必须过 gbt-vendor-intake 供应链体检 + 主人点头",
                    "next": "主人点头后再执行：omarchy plugin add %s" % source}
        r = _cli(b, "plugin", "remove", [source])
        return {"ok": bool(r.get("ok")), "op": "plugin_remove", "raw": r.get("out", "")}
    return {"ok": False, "reason": "unknown_plugin_action", "detail": str(op_action)}


def dispatch(cmd: str) -> dict:
    """Hyprland 控制（写类）：hyprctl dispatch —— 排窗/切工作区走这条。"""
    g = _guard_write("dispatch")
    if not g["ok"]:
        return g
    h = shutil.which("hyprctl")
    if not h:
        return {"ok": False, "op": "dispatch", "reason": "hyprctl_not_in_path"}
    if not cmd:
        return {"ok": False, "op": "dispatch", "reason": "needs_command"}
    r = _run([h, "dispatch", str(cmd)], timeout=15)
    return {"ok": bool(r.get("ok")), "op": "dispatch", "command": str(cmd), "raw": r.get("out", "")}


def evaluate(lua: str) -> dict:
    """Hyprland eval（写类）：**这门只留给主人自己**，本件不做自动放行。"""
    g = _guard_write("eval")
    if not g["ok"]:
        return g
    return {"ok": False, "op": "eval", "reason": "needs_owner_confirm",
            "detail": "hyprctl eval 会当场执行 Lua —— 本件不自判、不自授权；"
                      "取得授权后**由框架自己执行**（不要求用户动手）",
            "how_to_grant": ["终端运行: python -m gbt_allinone auth grant --scope process_execute --ttl 600"],
            "given": (lua or "")[:200]}




# ============================================================================
# 原生态：命令面**现读 + 自己分档**（借官方 CLI router 的“配置即命令”思想，
#   但档位由本仓自己定 —— 不把安全判断交给外部件）。
#
#   官方原文：“every executable bin/omarchy-* file is a command”，“There is no registry
#   to maintain” —— 所以高档位的做法不是把命令表拄死，而是**到真机上现读**。
#   本件只保留一层**只读探测**的 route 白名单（_ALLOW_ROUTE），写类动作一律走点名 op。
# ============================================================================

# 分档规则（本仓自定，可核可改）：拿 route 字面量匹配。
# —— 有元数据时用的两张表 + 单点名危险 route（取舍照官方：它 16 项 guarded / 55 项 safe）
_GUARDED_GROUPS = frozenset((
    "install", "remove", "reinstall", "migrate", "setup", "pkg", "upgrade", "update",
    "dev", "drive", "hibernation", "snapshot", "provision", "apply", "channel", "plugin",
))
_SAFE_GROUPS = frozenset((
    "agent", "audio", "bar", "battery", "bluetooth", "branding", "brightness", "capture",
    "chromium", "clipboard", "cmd", "crash", "default", "disk", "display", "dns", "done",
    "file", "font", "games", "git", "hook", "hw", "hyprland", "installed", "launch", "menu",
    "mise", "monitor", "network", "notification", "osd", "plymouth", "power", "powerprofiles",
    "refresh", "reminder", "restart", "screensaver", "share", "shell", "show", "state",
    "system", "tailscale", "theme", "toggle", "transcode", "tui", "version", "voxtype",
    "weather", "webapp", "windows",
))
# 单点名的危险 route（官方把它们从 safe 里剔出来单独拿掉）—— 本仓只留经验上会断服务的那几条。
_DENY_ROUTES = frozenset((
    "omarchy restart shell", "omarchy theme remove", "omarchy system shutdown",
    "omarchy system reboot", "omarchy system logout", "omarchy toggle hybrid gpu",
))
_DENY_PAT = ("lock", "suspend", "shutdown", "reboot", "poweroff", "logout", "hibernate")
_GUARDED_PAT = ("install", "uninstall", "remove", "update", "upgrade", "enable", "disable",
                "set", "add", "rm", "delete", "write", "edit", "restart", "start", "stop",
                "toggle", "reset", "migrate", "switch", "apply", "run")
_SAFE_PAT = ("list", "status", "show", "current", "info", "get", "check", "debug", "print",
             "help", "search", "which", "version", "read", "dump", "commands")


def _route_text(entry) -> str:
    """把一条命令条目摘成小写文本（兼容字典/字符串两种回还）。"""
    if isinstance(entry, dict):
        for k in ("route", "command", "name", "id", "path", "cmd"):
            v = entry.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip().lower()
        return json.dumps(entry, ensure_ascii=False).lower()
    return str(entry).strip().lower()


def classify_cmd(cmd) -> str:
    """有元数据就用元数据的分档（**借鉴**：判据绑在上游字段上，不靠手拄命令清单）。

    顺序写死（与官方同构）：
      1. `requires_sudo` ⇒ **一律 deny**（本仓无控制终端，口令永远没人答；任何规则都不能提升）；
      2. group 在 `_GUARDED_GROUPS` 或 route 在单点名危险表 ⇒ guarded；
      3. group 在 `_SAFE_GROUPS` ⇒ safe；
      4. **两张表都没点名 ⇒ guarded**（safe 是白名单，不是黑名单："**没被禁**"≠"**可以不问就跑**"）。
    """
    if not isinstance(cmd, dict):
        return classify_route(_route_text(cmd))
    route = _route_text(cmd)
    if cmd.get("requires_sudo") or cmd.get("requiresSudo") or cmd.get("sudo"):
        return "deny"
    grp = str(cmd.get("group") or cmd.get("groupName") or "").strip().lower()
    if grp in _GUARDED_GROUPS or route in _DENY_ROUTES:
        return "guarded"
    if grp in _SAFE_GROUPS:
        return "safe"
    return "guarded"


def classify_route(route: str) -> str:
    """把一条 route 分成 safe / guarded / deny —— **本仓口径**。

    deny 优先：凡是能把人关在外面或断电的，不管叫什么都不转发。
    """
    raw = [t for t in (route or "").lower().replace("-", " ").replace("_", " ")
           .replace("/", " ").split() if t]
    # 剔掉开关与它跟着的值（`--json` / `-q foo`）—— 它们不是动作。
    toks, skip = [], False
    for t in raw:
        if skip:
            skip = False
            continue
        if t.startswith("-"):
            skip = True
            continue
        toks.append(t)
    # 全局 deny 扫：只要任一词是“把人关在外面/断电”，不管位置一律拒。
    if any(p in toks for p in _DENY_PAT):
        return "deny"
    # 主动词 = **最后一个词**（官方 route 职责：`theme set` 的动作是 set）。
    #   先看最后一个词；不认识才回退到全词扫“动作词”。
    if toks and toks[-1] in _SAFE_PAT:
        return "safe"
    if toks and (toks[-1] in _GUARDED_PAT or toks[-1] in _DENY_PAT):
        return "guarded"
    if any(t in _SAFE_PAT for t in toks) and not any(t in _GUARDED_PAT for t in toks):
        return "safe"
    # 认不出来的 ⇒ 当需审批（fail-closed，宁紧不松）
    return "guarded"


def discover(bin_: str = "", sample: int = 40) -> dict:
    """现读命令面并逐条分档（只读）。真机上跑，本机回如实的“没装”。"""
    lst = list_commands(bin_=bin_)
    if not lst.get("ok"):
        lst["op"] = "discover"
        return lst
    cmds = lst.get("commands") or []
    buckets = {"safe": [], "guarded": [], "deny": []}
    for e in cmds:
        # 有元数据（group / requires_sudo）就走元数据分档；否则退回 route 模式分档
        buckets[classify_cmd(e)].append(_route_text(e))
    return {"ok": True, "op": "discover", "source_format": lst.get("format"),
            "total": len(cmds),
            "counts": {k: len(v) for k, v in buckets.items()},
            "rules": {"deny": list(_DENY_PAT), "guarded": list(_GUARDED_PAT), "safe": list(_SAFE_PAT)},
            "buckets": {k: v[:sample] for k, v in buckets.items()},
            "note": "档位由本仓 classify_route 定，不用外部件的分类；"
                    "不认识的一律 guarded（fail-closed）"}


def theme_list() -> dict:
    """主题表（只读）：omarchy theme list。"""
    b = shutil.which("omarchy")
    if not b:
        return {"ok": False, "op": "theme_list", "reason": "omarchy_not_in_path"}
    r = _cli(b, "theme", "list")
    return {"ok": bool(r.get("ok")), "op": "theme_list", "raw": r.get("out", "")}




# ============================================================================
# 窗口事件流（.socket2.sock）—— "知道你在开什么窗口"，而不是截图猜
#
#   Hyprland 官方：事件流在 $XDG_RUNTIME_DIR/hypr/[HIS]/.socket2.sock，逐行 EVENT>>DATA。
#   U0001f534 一次性读取：读满 duration 或行数就**当场断开**——官方说过该 socket 同步求值，
#   挂着不放会让 Hyprland 冻结。本件不开长连接、不做常驻监听。
# ============================================================================

_LINUX_EVENTS_SCRIPT = r'''
import base64, json, os, socket, sys, time

raw = json.loads(base64.b64decode(sys.argv[1]).decode("utf-8"))
dur = float(raw.get("duration") or 5.0)
dur = 0.5 if dur < 0.5 else (30.0 if dur > 30.0 else dur)
maxn = int(raw.get("max") or 200)
sock = (raw.get("socket") or "").strip()
rt = os.environ.get("XDG_RUNTIME_DIR") or ("/run/user/%d" % os.getuid())
if not sock:
    his = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") or ""
    owd = os.environ.get("OMARCHY_PATH") or ""
    wd = os.environ.get("WAYLAND_DISPLAY") or ""
    cands = []
    if his:
        cands.append(os.path.join(rt, "hypr", his, ".socket2.sock"))
    if owd and wd:
        cands.append(os.path.join(rt, "omarchy-shell-%s.sock"
                     % __import__("hashlib").md5(("%s/shell%s" % (owd.rstrip("/"), wd)).encode()).hexdigest()))
    for c in cands:
        if os.path.exists(c):
            sock = c
            break
    if not sock:
        base = os.path.join(rt, "hypr")
        if os.path.isdir(base):
            for d in sorted(os.listdir(base)):
                p = os.path.join(base, d, ".socket2.sock")
                if os.path.exists(p):
                    sock = p
                    break
if not sock or not os.path.exists(sock):
    print(json.dumps({"ok": False, "reason": "no_event_socket",
                      "candidates": cands if "cands" in dir() else [],
                      "runtime_dir": rt}))
    sys.exit(0)

lines = []
err = ""
t0 = time.time()
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(0.4)
try:
    s.connect(sock)
    buf = b""
    while (time.time() - t0) < dur and len(lines) < maxn:
        try:
            chunk = s.recv(4096)
        except socket.timeout:
            continue
        except OSError as exc:
            err = type(exc).__name__
            break
        if not chunk:
            break
        buf += chunk
        while b"\n" in buf:
            one, _, buf = buf.partition(b"\n")
            lines.append(one.decode("utf-8", "replace").strip())
            if len(lines) >= maxn:
                break
except OSError as exc:
    err = "%s: %s" % (type(exc).__name__, exc)
finally:
    try:
        s.close()
    except OSError:
        pass

types = {}
for ln in lines:
    t = ln.split(">>", 1)[0].strip() if ">>" in ln else ln.strip()
    types[t] = types.get(t, 0) + 1
print(json.dumps({"ok": True, "socket": sock, "elapsed": round(time.time() - t0, 3),
                  "count": len(lines), "types": types, "lines": lines[:maxn],
                  "error": err}, ensure_ascii=False))
'''


_LINUX_WINDOW_SCRIPT = r'''
import base64, json, subprocess, sys

raw = json.loads(base64.b64decode(sys.argv[1]).decode("utf-8"))
kind = (raw.get("kind") or "activewindow").strip()
if kind not in ("activewindow", "clients", "workspaces", "monitors"):
    print(json.dumps({"ok": False, "reason": "kind_not_allowed", "detail": kind}))
    sys.exit(0)
try:
    cp = subprocess.run(["hyprctl", "-j", kind], capture_output=True, timeout=20)
except FileNotFoundError:
    print(json.dumps({"ok": False, "reason": "hyprctl_not_installed"}))
    sys.exit(0)
out = (cp.stdout or b"").decode("utf-8", "replace").strip()
err = (cp.stderr or b"").decode("utf-8", "replace").strip()
if out.startswith("{") or out.startswith("["):
    print(json.dumps({"ok": True, "kind": kind, "raw": out[:6000]}))
else:
    print(json.dumps({"ok": False, "reason": "hyprctl_failed", "kind": kind,
                      "detail": (err or out)[:300]}))
'''


def _b64_script(script: str) -> str:
    return base64.b64encode(script.encode("utf-8")).decode("ascii")


def _shquote(s: str) -> str:
    """单引号包裹（base64 字符集里没有单引号，但保险起见转一下）。"""
    return "'%s'" % str(s).replace("'", "'\\''")


def _linux_via_wsl(script: str, payload: dict = None, timeout: int = 60, distro: str = "") -> dict:
    """在 WSL 里跑段脚本（**宿主没有会话时的委派路**）。没 WSL 就如实报。"""
    ds = _wsl_distros()
    if not ds:
        return {"ok": False, "reason": "no_wsl_distro", "detail": "宿主没有 Omarchy 会话，也没有 WSL 发行版可委派"}
    d = distro or ds[0]
    if d not in ds:
        return {"ok": False, "reason": "unknown_distro", "detail": "可选：%s" % ", ".join(ds)}
    script_b64 = _b64_script(script)
    arg_b64 = _b64_script(json.dumps(payload or {}, ensure_ascii=False))
    # 注意：脚本必须用 `python3 -c <code> <argv1>` 跑 —— 用 `python3 -`（读 stdin）时
    #   payload 没法作为 argv 传进去，脚本里的 sys.argv[1] 会 IndexError（实测踩过）。
    #   两段都用 base64 传，避开嵌套引号与转义。
    shell = "exec python3 -c \"$(echo %s | base64 -d)\" %s" % (script_b64, _shquote(arg_b64))
    r = _run(["wsl", "-d", d, "-e", "bash", "-lc", shell], timeout=timeout)
    out = (r.get("out") or "").replace("\x00", "").strip()
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                data = json.loads(line)
                data["via"] = "wsl:%s" % d
                return data
            except ValueError:
                continue
    return {"ok": False, "reason": "wsl_no_json", "via": "wsl:%s" % d,
            "detail": out[-400:] or "（无输出）", "rc": r.get("rc")}


def events(duration: float = 5.0, max_events: int = 200, distro: str = "",
           socket_path: str = "") -> dict:
    """读窗口事件流（只读）。宿主有会话就本地读；否则委派给 WSL。"""
    loc = _local()
    # 本机就有 Hyprland 会话 ⇒ 直接读；否则委派 WSL（委派不成功就如实报）
    if loc["session_markers"]["hyprland"] or loc["hypr_sockets"] or shutil.which("hyprctl"):
        return _events_local(duration, max_events, socket_path)
    return _linux_via_wsl(_LINUX_EVENTS_SCRIPT,
                          {"duration": duration, "max": max_events, "socket": socket_path},
                          timeout=int(min(90, max(15, duration + 45))), distro=distro)


def _events_local(duration: float, max_events: int, socket_path: str) -> dict:
    """宿主（Linux）直接跑脚本；Windows 宿主这条路会回如实的无会话。"""
    script = _LINUX_EVENTS_SCRIPT
    arg = _b64_script(json.dumps({"duration": duration, "max": max_events,
                                  "socket": socket_path}, ensure_ascii=False))
    try:
        cp = subprocess.run(["python3", "-c", script, arg],
                            capture_output=True, timeout=60)
        out = ((cp.stdout or b"") + (cp.stderr or b"")).decode("utf-8", "replace").strip()
        for line in reversed(out.splitlines()):
            if line.strip().startswith("{"):
                return json.loads(line.strip())
        return {"ok": False, "reason": "script_no_json", "detail": out[-300:]}
    except FileNotFoundError:
        return {"ok": False, "reason": "python3_not_found",
                "detail": "宿主没有 python3（Windows）⇒ 请走 WSL 委派路"}
    except Exception as exc:                                       # noqa: BLE001
        return {"ok": False, "reason": "events_failed", "detail": str(exc)[:200]}


def _hypr_ctl_json(args: list) -> dict:
    h = shutil.which("hyprctl")
    if not h:
        return {"ok": False, "reason": "hyprctl_not_in_path"}
    r = _run([h, "-j"] + list(args), timeout=15)
    out = (r.get("out") or "").strip()
    if out.startswith(("{", "[")):
        try:
            return {"ok": True, "data": json.loads(out)}
        except ValueError:
            pass
    return {"ok": bool(r.get("ok")), "format": "text", "raw": out[:1500]}


def window(distro: str = "") -> dict:
    """当前活动窗口（只读）：hyprctl -j activewindow。"""
    loc = _local()
    if loc["session_markers"]["hyprland"] or shutil.which("hyprctl"):
        r = _hypr_ctl_json(["activewindow"])
        r.update({"op": "window", "via": "host"})
        return r
    d = _linux_via_wsl(_LINUX_WINDOW_SCRIPT, {"kind": "activewindow"}, distro=distro)
    if d.get("ok") and not d.get("data"):
        d["data"] = d.get("raw")
    d["op"] = "window"
    return d


def clients(distro: str = "") -> dict:
    """全部打开的窗口（只读）：hyprctl -j clients。"""
    loc = _local()
    if loc["session_markers"]["hyprland"] or shutil.which("hyprctl"):
        r = _hypr_ctl_json(["clients"])
        if r.get("ok") and isinstance(r.get("data"), list):
            r["count"] = len(r["data"])
            r["titles"] = [c.get("title") for c in r["data"][:50] if isinstance(c, dict)]
        r.update({"op": "clients", "via": "host"})
        return r
    d = _linux_via_wsl(_LINUX_WINDOW_SCRIPT, {"kind": "clients"}, distro=distro)
    d["op"] = "clients"
    return d




# ============================================================================
# 常驻感知：短周期观测 + 变化差（**不碰长连接**）
#
#   为什么是轮询而不是监听：官方说 `.socket2.sock` **同步求值**，长连接会让 Hyprland 冻结。
#   本件只做“每次开一下、读一下、关掉”—— 常驻那一层交给本仓现有的受管环
#   （`tentacle/vision_watch.py` 已有 start/stop/frame/events/stats/status，不另造第二个 watcher）。
#
#   落点在 `store/`（而不是仓根）：因为它可被 `GBT_STORE_DIR` 隔离 —— 判据跑时不污染本仓。
# ============================================================================

OBSERVE_OPS = ("observe", "observe_history")


def _observe_dir() -> Path:
    """观测落点：store/omarchy_watch/（受 GBT_STORE_DIR 隔离）。"""
    try:
        from .._paths import STORE_DIR
        base = Path(STORE_DIR)
    except Exception:                                              # noqa: BLE001
        base = Path(__file__).resolve().parent.parent / "store"
    return base / "omarchy_watch"


def _now_iso() -> str:
    import datetime as _dt
    return _dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _snapshot(distro: str = "") -> dict:
    """一次观测：当前活动窗口 + 打开的窗口名单。只读。"""
    w = window(distro=distro)
    c = clients(distro=distro)
    titles = []
    if c.get("ok"):
        data = c.get("data")
        if isinstance(data, list):
            titles = [str(x.get("title") or x.get("class") or "?") for x in data
                      if isinstance(x, dict)][:60]
        elif isinstance(c.get("titles"), list):
            titles = [str(t) for t in c["titles"]][:60]
    act = ""
    if w.get("ok"):
        d = w.get("data")
        if isinstance(d, dict):
            act = str(d.get("title") or d.get("class") or d.get("initialTitle") or "")
        elif isinstance(w.get("raw"), str):
            act = w["raw"][:120]
    ok = bool(w.get("ok") or c.get("ok"))
    return {"ok": ok, "active": act, "titles": titles, "count": len(titles),
            "reasons": [r for r in (w.get("reason"), c.get("reason")) if r]}


def _fingerprint(snap: dict) -> str:
    payload = json.dumps({"a": snap.get("active"), "t": snap.get("titles")},
                         ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def observe(distro: str = "", write: bool = True) -> dict:
    """短周期观测一次（一次性），给出**上次到这次的变化差**。

    没会话就如实报：不会把“读不到”写成“没变化”（也不落盘）。
    落盘（`write=True` 默认）：state.json 记最新快照与指纹，observations.jsonl 只追加。
    """
    snap = _snapshot(distro=distro)
    fp = _fingerprint(snap) if snap.get("ok") else ""
    d = _observe_dir()
    st_path = d / "state.json"
    prev = {}
    try:
        prev = json.loads(st_path.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        prev = {}
    changed = bool(fp) and (fp != prev.get("fingerprint"))
    out = {"ok": bool(snap.get("ok")), "op": "observe",
           "active": snap.get("active"), "windows": snap.get("titles")[:20],
           "count": snap.get("count"), "fingerprint": fp,
           "prev_fingerprint": prev.get("fingerprint") or "",
           "changed": changed, "first_observation": not bool(prev.get("fingerprint")),
           "prev_read_at": prev.get("read_at") or "", "written": False}
    if not snap.get("ok"):
        out["reasons"] = snap.get("reasons")
        out["detail"] = "没有可读的 Omarchy 会话 ⇒ **不写盘、不说“没变化”**（读不到 ≠ 没变）"
        return out
    if write:
        try:
            d.mkdir(parents=True, exist_ok=True)
            rec = {"at": _now_iso(), "fingerprint": fp, "active": out["active"],
                   "count": out["count"], "changed": changed}
            with (d / "observations.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            st_path.write_text(json.dumps({
                "fingerprint": fp, "active": out["active"], "count": out["count"],
                "read_at": rec["at"],
                "prev_fingerprint": prev.get("fingerprint") or ""},
                ensure_ascii=False, indent=1), encoding="utf-8")
            out["written"] = True
            out["path"] = str(d)
        except OSError as exc:
            out["written"] = False
            out["write_error"] = str(exc)[:200]
    return out


def observe_history(limit: int = 20) -> dict:
    """读观测历史（只读）。"""
    p = _observe_dir() / "observations.jsonl"
    if not p.exists():
        return {"ok": True, "op": "observe_history", "count": 0, "items": [],
                "detail": "还没有任何观测记录（未读到 ≠ 没变化）"}
    rows = []
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    except OSError as exc:
        return {"ok": False, "op": "observe_history", "reason": "read_failed",
                "detail": str(exc)[:200]}
    return {"ok": True, "op": "observe_history", "count": len(rows),
            "items": rows[-max(1, int(limit)):]}




# ============================================================================
# 第二根线：`omarchy-shell <target> <method>` 的 IPC（本会话内有效）
#
#   官方原文：“IPC is the canonical way for CLIs to talk to a running shell — `omarchy-shell`
#   forwards a call and **fails when the shell is not running**”。
#
#   安全形态取舍（受第三方件启发，但档位由本仓定）：
#     · **只读 method 才转发**（status/recent/list/… 见 _SHELL_READ_METHODS）；
#     · 写类 method 一律 fail-closed ⇒ 只回 needs_owner_confirm + 把命令给主人，本件不代跑；
#     · target 不能含空白/引号（防拼接注入）。
# ============================================================================

# 允许透传的只读 method（字面量白名单；不在里面的一律当写类处理）
_SHELL_READ_METHODS = frozenset((
    "status", "recent", "list", "targets", "info", "get", "state", "version",
))


def _shell_bin() -> str:
    return shutil.which("omarchy-shell") or ""


def _shell_call_cmd(target: str, method: str, args=None) -> list:
    """拼命令（不进 shell：list 形式）。"""
    b = _shell_bin() or "omarchy-shell"
    return [b, str(target), str(method)] + [str(x) for x in (args or [])]


def _leaf_method(method: str) -> str:
    """取方法名的最后一段（`Foo.status` ⇒ `status`）。"""
    m = str(method or "").strip().lower()
    return m.rsplit(".", 1)[-1] if "." in m else m


def shell_targets(refresh: bool = False) -> dict:
    """列 shell 的 IPC target 与方法（只读）。`refresh=True` 转调官方 targets 命令。"""
    loc = _local()
    out = {"ok": False, "op": "shell_targets",
           "socket": {"computed": loc["shell_socket"]["computed"],
                      "found": loc["shell_socket"]["found"]},
           "wayland_display": loc["wayland_display"],
           "omarchy_path": loc["omarchy_path"],
           "how_to_enable": "在 Omarchy 桌面会话里调用（WAYLAND_DISPLAY 与 OMARCHY_PATH 必须在）"}
    if not (loc["shell_socket"]["computed"] or loc["shell_socket"]["found"]
            or loc["session_markers"]["hyprland"]):
        out["reason"] = "no_active_session"
        out["detail"] = "宿主没有活动 Wayland/Hyprland 会话 ⇒ shell IPC 只在本机会话内有效（官方）"
        return out
    b = _shell_bin()
    if not b:
        out["reason"] = "omarchy_shell_not_in_path"
        out["detail"] = "PATH 里没有 omarchy-shell"
        return out
    r = _run([b, "targets"] if not refresh else [b, "targets", "--refresh"], timeout=25)
    out["ok"] = bool(r.get("ok"))
    out["format"] = "text"
    out["raw"] = (r.get("out") or "")[:2000]
    if not r.get("ok"):
        out["reason"] = "targets_failed"
    return out


def shell_call(target: str, method: str, args=None) -> dict:
    """调一个 shell IPC 方法。**只读 method 才转发**；写类 fail-closed。"""
    t = str(target or "").strip()
    m = str(method or "").strip()
    if not t or not m:
        return {"ok": False, "op": "shell_call", "reason": "needs_target_and_method"}
    # 防拼接注入：target/method 只允许安全字符集
    import re as _re
    if not _re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", t) or not _re.fullmatch(r"[A-Za-z0-9_.-]{1,120}", m):
        return {"ok": False, "op": "shell_call", "reason": "unsafe_identifier",
                "detail": "target/method 只允许字母数字与 . _ : -"}
    if _leaf_method(m) not in _SHELL_READ_METHODS:
        return {"ok": False, "op": "shell_call", "reason": "needs_owner_confirm",
                "detail": "写类 shell 方法不转发（此位只放行只读方法：%s）"
                          % ", ".join(sorted(_SHELL_READ_METHODS)),
                "next": "主人手动：omarchy-shell %s %s %s"
                        % (t, m, " ".join(str(x) for x in (args or [])))}
    loc = _local()
    if not (loc["shell_socket"]["computed"] or loc["shell_socket"]["found"]):
        return {"ok": False, "op": "shell_call", "reason": "no_active_session",
                "detail": "探不到活动的 shell socket（官方：调用会在 shell 未运行时失败）",
                "socket_computed": loc["shell_socket"]["computed"],
                "socket_found": loc["shell_socket"]["found"]}
    if not _shell_bin():
        return {"ok": False, "op": "shell_call", "reason": "omarchy_shell_not_in_path"}
    r = _run(_shell_call_cmd(t, m, args), timeout=25)
    return {"ok": bool(r.get("ok")), "op": "shell_call", "target": t, "method": m,
            "raw": (r.get("out") or "")[:2000],
            "socket": loc["shell_socket"]["computed"] or (loc["shell_socket"]["found"] or [""])[0],
            **({} if r.get("ok") else {"reason": "call_failed"})}


def run(op: str = "assess", **kw) -> dict:
    """能力位统一入口（api.run_task 分派到这里）。未知 op **fail-closed**。"""
    o = (op or "assess").strip().lower()
    known = list(READ_OPS) + list(WRITE_OPS) + ["probe_wsl", "plugin_list", "theme_list", "discover", "observe"]
    if o == "assess":
        return assess()
    if o == "events":
        return events(duration=float(kw.get("duration", 5.0)),
                      max_events=int(kw.get("max_events", kw.get("max", 200))),
                      distro=kw.get("distro", ""), socket_path=kw.get("socket", ""))
    if o == "window":
        return window(distro=kw.get("distro", ""))
    if o == "clients":
        return clients(distro=kw.get("distro", ""))
    if o == "list":
        return list_commands(bin_=kw.get("bin", ""))
    if o == "discover":
        return discover(bin_=kw.get("bin", ""), sample=int(kw.get("sample", 40)))
    if o == "observe":
        return observe(distro=kw.get("distro", ""), write=bool(kw.get("write", True)))
    if o == "observe_history":
        return observe_history(limit=int(kw.get("limit", 20)))
    if o == "shell_targets":
        return shell_targets(refresh=bool(kw.get("refresh", False)))
    if o == "shell_call":
        return shell_call(kw.get("target", ""), kw.get("method", ""),
                          args=kw.get("args") or [])
    if o == "probe_wsl":
        return probe_wsl(distro=kw.get("distro", ""))
    if o == "theme_list":
        return theme_list()
    if o == "set_theme":
        return set_theme(kw.get("name", ""))
    if o == "theme_install":
        # 装第三方主题：官方说这条**会主动丢掉会执行代码的文件**（只保留颜色），
        #   但它仍然是"从别人仓库拉东西"⇒ 与 plugin_add 同级，只回 needs_owner_confirm。
        nm = str(kw.get("name") or kw.get("source") or "").strip()
        if not nm:
            return {"ok": False, "op": "theme_install", "reason": "needs_source"}
        return {"ok": False, "op": "theme_install", "reason": "needs_owner_confirm",
                "detail": "从外部仓库装主题：官方会丢掉 .lua/终端配置/vscode.json 等**会执行代码的文件**，\n"
                          "但仍需过 gbt-vendor-intake 供应链体检 + 主人点头",
                "next": "主人点头后执行：omarchy theme install %s" % nm}
    if o == "dispatch":
        return dispatch(kw.get("command", ""))
    if o == "eval":
        return evaluate(kw.get("lua", ""))
    if o == "plugin_list":
        return plugin("list")
    if o in ("plugin_add", "plugin_rm", "plugin_enable", "plugin_disable"):
        act = {"plugin_rm": "remove"}.get(o, o.replace("plugin_", ""))
        return plugin(act, plugin_id=kw.get("plugin", kw.get("plugin_id", "")),
                      source=kw.get("source", ""))
    return {"ok": False, "reason": "unknown_op", "op": o, "known": known,
            "detail": "未知 op 只回错，不执行任何东西（fail-closed）"}
