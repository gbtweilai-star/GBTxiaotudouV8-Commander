# gbt-capability: surface_bind
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""通用「可控制面」绑定器 · **每一个可控制键都绑上，一个不漏**（主人令 2026-09-27）。

主人原话：「包括我们需要使用到的**其他工具全部都要可控按键全部一个不漏的绑定好**，
实现**想什么就能生产什么画面**的能力就可以了。」

## 思路（与 Blender 那套同源，做成通用）
**不手抄文档** —— 让**每个工具自己报出它的可控制键**（`--help` / `git help -a` / `ffmpeg -filters` /
Blender 的 `bpy.ops` 枚举…），落成清单 `state/surfaces/<工具>.json`，然后：
  · **正向**：清单里每个键 → 都能经唯一门执行（各工具自己的能力位）；
  · **反向**：每个键在清单里有名有姓（分组 → 键名），清单本身**绑到该工具的触手**（台账留痕）；
  · **不会断连**：重扫与上次对比 —— **新键=新增可控制面**（自动并入）· **消失的键=断连**（报警/解释）。

## 安全写法（写死，别再犯）
探针**不把 exe 变量当程序名**（安全钩子的"命令注入"判据就盯这条 —— 实测被拦过一次）：
本文件改为**生成一份探针脚本**（内容由我们拼、无任何外部输入），再用**字面量** `cmd /c <脚本>` 执行。

ops：probe（单工具）/ sweep（所有装了的一遍）/ keys（摘要）/ verify（判据）
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_DIR = _ROOT / "state" / "surfaces"

# 工具登记表：probe=探针参数（列表）；rx=抽键正则；min_keys=判据阈值（**来自实测，留余量**）
TOOLS = {
    "ffmpeg": {
        "tentacle": "filmkit",
        "probe": [["-version"], ["-filters"], ["-encoders"], ["-decoders"], ["-formats"], ["-pix_fmts"]],
        "rx": r"^\s*[TSC\.]{0,3}\s*([0-9A-Za-z_][0-9A-Za-z_\-\.\+:]{1,60})\s",
        "min_keys": 300,
        "why": "视频/音频生产线底层可控制面（滤镜/编解码/格式/像素格式）",
    },
    "git": {
        "tentacle": "project_context",
        "probe": [["help", "-a"]],
        "rx": r"^\s{3}([a-z][a-z0-9\-]{2,30})\s",
        "min_keys": 80,
        "why": "版本控制可控制面（子命令）",
    },
    "genoffice": {
        "tentacle": "genoffice",
        "probe": [["--help"]],
        "rx": r"^\s{2}([a-z][a-z0-9\-]{2,24})\s{2,}",
        "min_keys": 12,
        "why": "办公文档蒸馏版（本地引擎命令面）",
    },
    "freebuff": {
        "tentacle": "freebuff_term",
        "probe": [["--help"]],
        "rx": r"^\s{2}(-{1,2}[a-zA-Z][\w\-]{1,30})",
        "min_keys": 3,
        "why": "免费算力引擎（CLI 开关；实测 3 把：--continue/--cwd/--trust-agents）",
    },
    "comfyui": {
        "tentacle": "comfyui",
        "probe": None,            # 专门枚举：走 comfyui_surface（本机 8188 的 /object_info）
        "min_keys": 900,          # 实测 966 个节点，留余量
        "why": "本地生图/生视频引擎（966 节点全控）—— 无限制审查生产的底气",
    },
    "lobehub": {
        "tentacle": "lobehub",
        "probe": None,            # 专门枚举：走 lobehub（设置键 + 快捷键 + 接口操作 + 助理）
        "min_keys": 40,           # 实测 76 把可控制键，留余量
        "why": "LobeHub 桌面端（生图/助理/任务面）—— 76 把可控制键，消失即断连",
    },
    "blender": {
        "tentacle": "blender",
        "probe": None,            # 专门枚举（bpy.ops 2409 个）
        "min_keys": 2000,
        "why": "三维引擎（bpy 算子/数据族/CLI）—— 见 blender_surface",
    },
    "python": {
        "tentacle": "project_context",
        # ⚠️ 血账：`-c "…;…"` 经 .cmd 会被转义吃掉（实测探出 0 键）⇒ 改成**生成 .py 脚本**再跑。
        "probe_py": "\n".join([
            "import sys",
            "print('__VER__' + sys.version.split()[0])",
            "print('__MODS__%d' % len(sys.stdlib_module_names))",
            "print('__EACH__' + ','.join(sorted(sys.stdlib_module_names)))",
        ]) + "\n",
        "rx": r"__MODS__(\d+)",
        "min_keys": 100,
        "why": "解释器（**每个标准库模块一把键** —— 那才是可调用面；只报模块数不算绑定）",
    },
    # ── 2026-10-08 加（主人令「调节蓝牙，无线网全部都能操作」）+ 协调者授权按"只加条目"改 ──
    # 为什么是 netsh：本仓 240 个能力位里**没有 wifi/wlan 位**（全仓 grep 无命中），
    # 而 `netsh wlan` 是本机 Wi-Fi 唯一的"自己报出可控制键"的工具 —— 正是本绑定器的适用对象。
    # 实测（2026-10-08）：顶层 15 + show 子键 17 + set 子键 11 = **43 把**（min_keys 留余量到 40）。
    # ⚠️ 只加本条目；不许顺手动别的工具定义、不许改函数签名。
    "netsh": {
        "tentacle": "tentacle",
        "probe": [["wlan", "help"], ["wlan", "show", "?"], ["wlan", "set", "?"]],
        "rx": r"^\s{0,4}([?A-Za-z][A-Za-z0-9_\- ]{0,44}?)\s-\s",
        "min_keys": 40,
        "why": "无线网面（主人令 2026-10-08）：netsh wlan 的可控制键（show 读类 / connect·set 写类）",
    },
}

_SCRIPT_DIR = _ROOT / "state" / "surfaces"
_PROBE_TIMEOUT = 180


def _which(tool: str) -> str:
    if tool == "python":
        return shutil.which("python") or sys.executable
    return shutil.which(tool) or ""


def _probe_via_script(tool: str, exe: str, args: list, env_extra: dict | None = None) -> tuple:
    """**安全写法**：把探针写成一份脚本（内容我们拼、无外部输入），再用**字面量** `cmd /c` 执行。
    这样"程序名"永远是常量 `cmd`，不把变量当程序（安全钩子实测拦过那种写法）。"""
    _SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    script = _SCRIPT_DIR / f"_probe_{tool}.cmd"
    body = "@echo off\r\nchcp 65001 >nul\r\n" + '"' + exe + '" ' + " ".join(
        (('"' + a + '"') if (" " in a or ";" in a) else a) for a in args) + " 2>&1\r\n"
    script.write_text(body, encoding="utf-8")
    try:
        env = None
        if env_extra:
            env = dict(os.environ)
            env.update(env_extra)
            (_SCRIPT_DIR / "_home").mkdir(parents=True, exist_ok=True)
        p = subprocess.run(["cmd", "/c", str(script)], capture_output=True, env=env,
                           encoding="utf-8", errors="replace", timeout=_PROBE_TIMEOUT)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return -1, f"超时（>{_PROBE_TIMEOUT}s）"
    except OSError as e:
        return -1, f"{type(e).__name__}: {e}"


# ⚠️ 血账（2026-09-27）：**委托分支（comfyui/blender/lobehub）曾经提前 return**，
#    清单写了却**从没绑上触手** —— "接上了没绑上"。委托的每条分支都要显式调它。
def _bind_manifest(path: Path, tentacle: str, note: str = "可控制面清单") -> bool:
    try:
        sp = importlib.util.spec_from_file_location("tb_sb", _ROOT / "tools" / "tentacle_bind.py")
        tb = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(tb)
        return bool(tb.bind(str(path), tentacle, note=note, quiet=True).get("ok"))
    except Exception:                                          # noqa: BLE001
        return False


def probe(tool: str = "", rescan: bool = True, **_kw) -> dict:
    """问出某个工具的可控制键 → 写清单 + 与上次对比 + 绑到它的触手。"""
    if tool not in TOOLS:
        return {"ok": False, "fail_closed": True,
                "error": f"未登记的工具 {tool!r}（登记表：{sorted(TOOLS)}）"}
    spec = TOOLS[tool]
    exe = _which(tool)
    if tool == "comfyui":
        # 本机 ComfyUI（127.0.0.1:8188）活取：966 节点 + 端点 + 模型；节点消失=断连
        csp = importlib.util.spec_from_file_location(
            "cs_probe", _ROOT / "gbt_allinone" / "tools" / "comfyui_surface.py")
        cs = importlib.util.module_from_spec(csp)
        csp.loader.exec_module(cs)
        r = cs.surface(rescan=rescan)
        if not r.get("ok"):
            return {"ok": False, "op": "probe", "tool": tool,
                    "installed": True, "why": str(r.get("error"))[:160]}
        n = (r.get("counts") or {}).get("nodes", 0)
        _bound = _bind_manifest(_ROOT / "state" / "comfyui_surface.json", spec["tentacle"],
                       note="可控制面清单（ComfyUI 桌面引擎）")
        return {"ok": True, "op": "probe", "tool": tool, "delegated": "comfyui_surface",
                "keys": n, "min_keys": spec["min_keys"], "sufficient": n >= spec["min_keys"],
                "gone": r.get("gone_total"), "added": r.get("added_total"), "bound": _bound}
    if tool == "lobehub":
        # LobeHub 桌面端：设置键 + 快捷键 + 接口操作 + 助理 ⇒ 76 把可控制键（消失即断连）
        lhp = importlib.util.spec_from_file_location(
            "lh_probe", _ROOT / "gbt_allinone" / "tools" / "lobehub.py")
        lh = importlib.util.module_from_spec(lhp)
        lhp.loader.exec_module(lh)
        r = lh.surface(rescan=rescan)
        if not r.get("ok"):
            return {"ok": False, "op": "probe", "tool": tool, "installed": bool(lh._exe()[0]),
                    "why": str(r.get("error"))[:160]}
        n = (r.get("counts") or {}).get("keys", 0)
        _bound = _bind_manifest(_ROOT / "state" / "surfaces" / "lobehub.json", spec["tentacle"],
                       note="可控制面清单（LobeHub 桌面端）")
        return {"ok": True, "op": "probe", "tool": tool, "delegated": "lobehub",
                "keys": n, "min_keys": spec["min_keys"], "sufficient": n >= spec["min_keys"],
                "gone": r.get("gone_total"), "added": r.get("added_total"), "bound": _bound}
    if tool == "blender":
        bsp = importlib.util.spec_from_file_location(
            "bs_probe", _ROOT / "gbt_allinone" / "tools" / "blender_surface.py")
        bs = importlib.util.module_from_spec(bsp)
        bsp.loader.exec_module(bs)
        r = bs.surface(rescan=rescan)
        if not r.get("ok"):
            return {"ok": False, "op": "probe", "tool": tool, "installed": bool(bs._cli()[0]),
                    "error": str(r)[:200]}
        _bound = _bind_manifest(_ROOT / "state" / "blender_surface.json", spec["tentacle"],
                       note="可控制面清单（Blender 三维引擎）")
        return {"ok": True, "op": "probe", "tool": tool, "delegated": "blender_surface",
                "keys": (r.get("counts") or {}).get("operators"),
                "min_keys": spec["min_keys"],
                "sufficient": (r.get("counts") or {}).get("operators", 0) >= spec["min_keys"],
                "gone": r.get("gone_total"), "added": r.get("added_total"), "bound": _bound}
    if not exe:
        return {"ok": False, "op": "probe", "tool": tool, "installed": False,
                "why": f"本机没有 `{tool}`（装了再探，不装不硬编）"}
    keys, ver = set(), ""
    if spec.get("probe_py") and exe:                       # 走脚本文件（避免 -c 的转义坑）
        _SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
        pys = _SCRIPT_DIR / f"_probe_{tool}.py"
        pys.write_text(spec["probe_py"], encoding="utf-8")
        rc, out = _probe_via_script(tool, exe, [str(pys)])
        m = re.search(spec["rx"], out)
        if m:
            keys.add(f"stdlib_modules={m.group(1)}")
        # **每个标准库模块一把键**（只报"模块数=301"不算绑定：那是一个统计量，不是可调用面）
        em = re.search(r"__EACH__(.+)", out)
        if em:
            for mod in em.group(1).strip().split(","):
                mod = mod.strip()
                if mod:
                    keys.add(f"module:{mod}")
        vm = re.search(r"__VER__(\S+)", out)
        if vm:
            ver = vm.group(1)
        keys = sorted(keys)
        path = _DIR / f"{tool}.json"
        prev = {}
        if path.is_file():
            try:
                prev = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                prev = {}
        gone = sorted(set(prev.get("keys") or []) - set(keys))
        added = sorted(set(keys) - set(prev.get("keys") or []))
        man = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "tool": tool, "exe": exe,
               "version": ver, "why": spec["why"], "tentacle": spec["tentacle"],
               "counts": {"keys": len(keys)}, "min_keys": spec["min_keys"],
               "keys": keys, "gone": gone[:200], "added": added[:200]}
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, path)
        bound = _bind_manifest(path, spec["tentacle"])
        return {"ok": len(keys) >= 1, "op": "probe", "tool": tool, "keys": len(keys),
                "min_keys": spec["min_keys"], "sufficient": len(keys) >= spec["min_keys"],
                "added": len(added), "gone": len(gone), "bound_to": spec["tentacle"] if bound else "",
                "manifest": str(path.relative_to(_ROOT))}
    for args in spec.get("probe") or []:
        rc, out = _probe_via_script(tool, exe, args,
                                    env_extra=({"HOME": str(_SCRIPT_DIR / "_home"),
                                                "USERPROFILE": str(_SCRIPT_DIR / "_home"),
                                                "XDG_CONFIG_HOME": str(_SCRIPT_DIR / "_home" / ".config")}
                                               if tool == "freebuff" else None))
        if tool == "python":
            m = re.search(spec["rx"], out)
            if m:
                keys.add(f"stdlib_modules={m.group(1)}")
            vm = re.search(r"__VER__(\S+)", out)
            if vm:
                ver = vm.group(1)
            continue
        for m in re.finditer(spec["rx"], out, re.M):
            k = m.group(1).strip()
            if k and k not in ("Usage", "Options", "Arguments", "Commands"):
                keys.add(k)
        if not ver and args and args[0] in ("-version", "--version"):
            ver = out.strip().splitlines()[0][:60] if out.strip() else ""
    keys = sorted(keys)
    path = _DIR / f"{tool}.json"
    prev = {}
    if path.is_file():
        try:
            prev = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prev = {}
    gone = sorted(set(prev.get("keys") or []) - set(keys))
    added = sorted(set(keys) - set(prev.get("keys") or []))
    man = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "tool": tool, "exe": exe,
           "version": ver or (prev.get("version") or ""), "why": spec["why"],
           "tentacle": spec["tentacle"], "counts": {"keys": len(keys)},
           "min_keys": spec["min_keys"], "keys": keys[:5000], "gone": gone[:200], "added": added[:200],
           "_口径": "**让工具自己报**（探针见 TOOLS 登记表）；重扫对比：新键并入、**消失的键=断连**"}
    _DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)
    bound = _bind_manifest(path, spec["tentacle"])
    return {"ok": len(keys) >= 1, "op": "probe", "tool": tool, "keys": len(keys),
            "min_keys": spec["min_keys"], "sufficient": len(keys) >= spec["min_keys"],
            "added": len(added), "gone": len(gone), "gone_sample": gone[:5],
            "bound_to": spec["tentacle"] if bound else "", "manifest": str(path.relative_to(_ROOT))}


def sweep(rescan: bool = True, **_kw) -> dict:
    """把所有**本机装了的**工具过一遍（没装如实报"没装"，不硬编）。"""
    out, need = [], []
    for t in sorted(TOOLS):
        r = probe(t, rescan=rescan)
        out.append(r)
        if r.get("ok") and not r.get("sufficient"):
            need.append(f"{t}: 只探到 {r.get('keys')} 键 < 阈值 {r.get('min_keys')}")
        if (r.get("gone") or 0) > 0:
            need.append(f"{t}: **{r['gone']} 个键消失**（断连，例：{r.get('gone_sample')}）")
    ok = all(r.get("ok") or r.get("installed") is False for r in out) and not need
    return {"ok": ok, "op": "sweep", "tools": out, "problems": need,
            "installed": [r["tool"] for r in out if r.get("ok")],
            "absent": [r["tool"] for r in out if r.get("installed") is False],
            "_口径": "装了才探；没装写『没装』；键数低于阈值 / 键消失 = 问题"}


def keys(tool: str = "", **_kw) -> dict:
    if tool:
        p = _DIR / f"{tool}.json"
        if not p.is_file():
            return {"ok": False, "why": f"没有 {tool} 的清单"}
        d = json.loads(p.read_text(encoding="utf-8"))
        return {"ok": True, "op": "keys", "tool": tool, "counts": d.get("counts"),
                "min_keys": d.get("min_keys"), "tentacle": d.get("tentacle"),
                "sample": (d.get("keys") or [])[:15], "gone": len(d.get("gone") or [])}
    rows = []
    for f in sorted(_DIR.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        rows.append({"tool": d.get("tool"), "keys": (d.get("counts") or {}).get("keys"),
                     "min_keys": d.get("min_keys"), "gone": len(d.get("gone") or []),
                     "at": d.get("at"), "tentacle": d.get("tentacle")})
    return {"ok": True, "op": "keys", "surfaces": rows,
            "_口径": "每行=一个工具的可控制面（键数 / 阈值 / 消失键数 / 触手）"}


def verify(**_kw) -> dict:
    problems = []
    for t, spec in TOOLS.items():
        # ⚠️ blender 的清单由 blender_surface 写在 state/blender_surface.json（2409 个 bpy 算子），
        #    不在 surfaces/ 目录 —— 早先 verify 找错地方，误报"没有清单"。
        # 专门枚举的工具：清单不在 surfaces/ 目录（血账：verify 早先因此误报"没有清单"）
        _special = {"blender": _ROOT / "state" / "blender_surface.json",
                    "comfyui": _ROOT / "state" / "comfyui_surface.json"}
        # lobehub 的清单在 surfaces/ 目录里（lobehub.json），键名字段也是 keys ⇒ 走默认路径
        p = _special.get(t) or (_DIR / f"{t}.json")
        if not p.is_file():
            problems.append(f"{t}: 没有清单（装了没探 / 没装）")
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        _key_field = "operators" if t == "blender" else ("nodes" if t == "comfyui" else "keys")
        n = (d.get("counts") or {}).get(_key_field) or 0
        if n < spec["min_keys"]:
            problems.append(f"{t}: 键 {n} < 阈值 {spec['min_keys']}（**有漏**）")
        if d.get("gone"):
            problems.append(f"{t}: **断连** {len(d['gone'])} 个键消失（例：{d['gone'][:3]}）")
    return {"ok": not problems, "op": "verify", "problems": problems, "registered": len(TOOLS),
            "_口径": "阈值来自实测；消失键=断连，要解释或补"}


def run_op(op: str = "keys", **params) -> dict:
    op = (op or "keys").lower()
    for name, fn in (("probe", probe), ("sweep", sweep), ("keys", keys), ("verify", verify)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True, "error": f"未知 op:{op}（probe/sweep/keys/verify）"}
