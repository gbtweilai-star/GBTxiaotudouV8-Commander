# -*- coding: utf-8 -*-
"""设置中心 · 数据聚合（只读）

一次请求把面板要的现读数据都取回来。三条原则：
  · **每个面板独立 try**：坏一个只影响自己，面板里带 `error` 字段，不假绿；
  · **慢项带 TTL 缓存 + 短超时**：回收站、模型列表、node 版本；
  · **只读**：唯一的写动作在 `act()` 里（通知测试 / 清空回收站 / 存主题）。

外部依赖只走本机：超级万能插 HTTP 网关（127.0.0.1:7788）与 llama-server（127.0.0.1:8794），
都不通就如实写 `up: false`，不补假读数。
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import sqlite3
import subprocess
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE = REPO / "state"
KIT = Path(r"C:\Users\Lenovo E14 Gen 5\Desktop\超级万能插")
DB = STATE / "projects.db"
PUBLIC = Path.home() / ".agents" / "skills"
PROJECT_SKILLS = REPO / ".agents" / "skills"
CODEX_SKILLS = Path.home() / ".codex" / "skills"
TENTACLE = "http://127.0.0.1:7788"
LLAMA = "http://127.0.0.1:8794"

_CACHE: dict = {}


def _cached(key: str, ttl: float, fn):
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    val = fn()
    _CACHE[key] = (time.time(), val)
    return val


def _safe(fn, default=None):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        return default if default is not None else {"error": "%s: %s" % (type(e).__name__, str(e)[:160])}


def _http_json(url: str, timeout: float = 1.2, body: dict | None = None):
    req = urllib.request.Request(
        url,
        data=(json.dumps(body).encode("utf-8") if body is not None else None),
        headers={"content-type": "application/json"},
        method=("POST" if body is not None else "GET"),
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _dir_size(p: Path) -> int:
    total = 0
    if not p.exists():
        return 0
    for root, _dirs, files in os.walk(p):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def _db():
    if not DB.is_file():
        return None
    c = sqlite3.connect("file:%s?mode=ro" % DB.as_posix(), uri=True)
    c.row_factory = sqlite3.Row
    return c


# ────────────────────────── 面板 ──────────────────────────

def sec_stats():
    """数据统计：项目 / 产物 / 链路 / 运行 + 每日活跃。"""
    out = {"ok": True}
    c = _db()
    if not c:
        return {"ok": True, "empty": True, "note": "还没有项目库（state/projects.db）"}
    try:
        q = lambda sql: c.execute(sql).fetchone()[0]  # noqa: E731
        out.update({
            "projects": q("SELECT COUNT(*) FROM projects"),
            "artifacts": q("SELECT COUNT(*) FROM artifacts"),
            "links": q("SELECT COUNT(*) FROM links"),
            "runs": q("SELECT COUNT(*) FROM runs"),
            "runs_ok": q("SELECT COUNT(*) FROM runs WHERE ok=1"),
            "run_ms": q("SELECT COALESCE(SUM(ms),0) FROM runs"),
            "first_at": q("SELECT COALESCE(MIN(created_at),'') FROM projects"),
            "last_at": q("SELECT COALESCE(MAX(created_at),'') FROM runs"),
        })
        days = {}
        for r in c.execute("SELECT substr(created_at,1,10) d, COUNT(*) n, COALESCE(SUM(ms),0) ms FROM runs GROUP BY d"):
            days[r["d"]] = {"n": r["n"], "ms": r["ms"]}
        out["by_day"] = days
    finally:
        c.close()

    # 触手侧真实调用量（审计日志行数；只读 0.4MB，不需要缓存）
    def tentacle_calls():
        logs = sorted((KIT / "logs").glob("audit-*.jsonl"))
        total = 0
        per_day = {}
        for f in logs:
            try:
                for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                    if not line.strip():
                        continue
                    total += 1
                    d = line[7:17] if len(line) > 18 else ""
                    if d[:4].isdigit():
                        per_day[d] = per_day.get(d, 0) + 1
            except OSError:
                pass
        return {"calls": total, "by_day": per_day, "files": len(logs)}

    out["tentacle"] = _safe(tentacle_calls, {"calls": 0, "by_day": {}})

    # 合并每日活跃（runs + 触手审计）
    merged = {}
    for src in (out.get("by_day") or {}, (out.get("tentacle") or {}).get("by_day") or {}):
        for d, v in src.items():
            n = v["n"] if isinstance(v, dict) else v
            merged[d] = merged.get(d, 0) + int(n or 0)
    out["heat"] = dict(sorted(merged.items())[-400:])
    out["peak_day"] = max(out["heat"].items(), key=lambda kv: kv[1]) if out["heat"] else ("", 0)
    return out


def sec_device():
    import ctypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

    st = MEMORYSTATUSEX()
    st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
    up = time.time() - ctypes.windll.kernel32.GetTickCount64() / 1000.0
    return {
        "ok": True,
        "host": platform.node(),
        "os": "%s %s" % (platform.system(), platform.release()),
        "cpu": platform.processor() or platform.machine(),
        "cores": os.cpu_count(),
        "mem_total_gb": round(st.ullTotalPhys / 1e9, 1),
        "mem_used_pct": int(st.dwMemoryLoad),
        "boot_at": time.strftime("%Y-%m-%d %H:%M", time.localtime(up)),
        "uptime_h": round((time.time() - up) / 3600.0, 1),
    }


def sec_env():
    def node_ver():
        exe = shutil.which("node") or ""
        if not exe:
            return ""
        r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=6)
        return r.stdout.strip()

    return {
        "ok": True,
        "python": platform.python_version(),
        "python_exe": os.sys.executable if hasattr(os, "sys") else "",
        "node": _cached("node_ver", 300, node_ver),
        "repo": str(REPO),
        "ports": {"console": 8766, "tentacle": 7788, "llama": 8794},
        "env_flags": {k: bool(os.environ.get(k)) for k in
                      ("GBT_LLM_API_KEY", "ABLITERATION_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY",
                       "HTTP_PROXY", "HTTPS_PROXY")},
        "cwd": os.getcwd(),
    }


def sec_storage():
    def disk(p):
        try:
            u = shutil.disk_usage(p)
            return {"total_gb": round(u.total / 1e9, 1), "free_gb": round(u.free / 1e9, 1),
                    "used_pct": round(100.0 * (u.total - u.free) / u.total)}
        except OSError:
            return None

    dirs = {}
    for name in ("state", "outputs", ".scratch", "logs", "holo_pet_w3"):
        p = REPO / name
        if p.exists():
            dirs[name] = round(_dir_size(p) / 1e6, 1)
    return {"ok": True, "disks": {"C:": disk("C:\\"), "D:": disk("D:\\")},
            "dirs_mb": dirs, "db_mb": round(DB.stat().st_size / 1e6, 2) if DB.is_file() else 0}


def sec_appearance():
    s = _read_settings()
    return {"ok": True, "theme": s.get("theme", "dark"), "accent": s.get("accent", "green"),
            "density": s.get("density", "cozy"), "updated_at": s.get("updated_at", ""),
            "themes": ["dark", "dim", "light"], "accents": ["green", "blue", "violet", "amber"]}


def sec_notify():
    s = _read_settings()
    return {"ok": True, "enabled": s.get("notify", True), "level": s.get("notify_level", "info"),
            "channel": "Windows 通知气泡（sys_notify，走触手）"}


def sec_hotkeys():
    def load():
        try:
            r = _http_json(TENTACLE + "/call", 1.4, {"tool": "pulse_list", "args": {}})
            body = r.get("result", r)
            b = body.get("bindings") if isinstance(body, dict) else None
            return {"ok": True, "bindings": b or {}, "daemon": (body or {}).get("daemon")}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "bindings": {}, "error": str(e)[:120]}

    return _cached("hotkeys", 10, load)


def sec_platforms():
    servers = []
    try:
        if (STATE / "mcp-servers.json").is_file():
            d = json.loads((STATE / "mcp-servers.json").read_text(encoding="utf-8"))
            for name, spec in (d or {}).items():
                servers.append({"name": name, "command": spec.get("command"), "cwd": spec.get("cwd"),
                                "description": spec.get("description", "")})
    except Exception as e:  # noqa: BLE001
        servers = [{"name": "(读取失败)", "error": str(e)[:100]}]

    def gateway():
        try:
            h = _http_json(TENTACLE + "/health", 1.0)
            return {"up": bool(h.get("ok")), "tools": h.get("tools")}
        except Exception:  # noqa: BLE001
            return {"up": False}

    return {"ok": True, "mcp_servers": servers, "gateway": _cached("gateway", 5, gateway),
            "bridge": {"clipboard_bridge": (KIT / "start-bridge.cmd").is_file(),
                       "http_gateway": (KIT / "runtime" / "server.mjs").is_file()}}


def sec_providers():
    cfg = {}
    try:
        cfg = json.loads((KIT / "secrets" / "model.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass

    def local():
        try:
            h = _http_json(LLAMA + "/health", 1.0)
            return {"up": True, "detail": h}
        except Exception as e:  # noqa: BLE001
            return {"up": False, "error": str(e)[:80]}

    return {"ok": True,
            "local": {"name": "本机视觉（llama.cpp + Vulkan）", "base": cfg.get("base", LLAMA + "/v1"),
                      "model": cfg.get("model", ""), "health": _cached("llama_h", 5, local)},
            "cloud": [{"name": "Abliteration", "env": "ABLITERATION_API_KEY",
                       "configured": bool(os.environ.get("ABLITERATION_API_KEY"))},
                      {"name": "GBT / DeepSeek", "env": "GBT_LLM_API_KEY",
                       "configured": bool(os.environ.get("GBT_LLM_API_KEY"))}],
            "note": "钥匙只看『槽位在不在』，不回显明文"}


def sec_models():
    def load():
        try:
            j = _http_json(LLAMA + "/v1/models", 1.2)
            return {"ok": True, "models": [m.get("id") for m in (j.get("data") or [])]}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "models": [], "error": str(e)[:100]}

    return _cached("models", 20, load)


def _skill_desc(p: Path) -> str:
    try:
        txt = (p / "SKILL.md").read_text(encoding="utf-8", errors="replace")
        for line in txt.splitlines():
            if line.startswith("description:"):
                return line.split("description:", 1)[1].strip()[:120]
    except OSError:
        pass
    return ""


def sec_skills():
    rows = []
    for root, group in ((PUBLIC, "个人"), (PROJECT_SKILLS, "项目"), (CODEX_SKILLS, "系统")):
        if not root.is_dir():
            continue
        for d in sorted(root.iterdir()):
            if not d.is_dir() or d.name.startswith("."):
                continue
            rows.append({"name": d.name, "group": group, "path": str(d),
                         "description": _skill_desc(d),
                         "scripts": sorted(x.name for x in (d / "scripts").glob("*")) if (d / "scripts").is_dir() else []})
    return {"ok": True, "count": len(rows), "skills": rows}


def sec_tags():
    kinds, metas = [], []
    c = _db()
    if c:
        try:
            kinds = [dict(r) for r in c.execute("SELECT kind, COUNT(*) n FROM links GROUP BY kind ORDER BY n DESC")]
            metas = [dict(r) for r in c.execute("SELECT name, json_extract(meta,'$.role') role FROM projects")]
        finally:
            c.close()
    cap_tags = 0
    try:
        cap_tags = len(json.loads((STATE / "cap_tags.json").read_text(encoding="utf-8")) or {})
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "link_kinds": kinds, "projects": metas, "cap_tags": cap_tags}


def sec_connectors():
    gw = sec_platforms()["gateway"]
    outbox = KIT / "bridge" / "outbox"
    return {"ok": True, "gateway": gw,
            "mcp": len(sec_platforms()["mcp_servers"]),
            "outbox_files": (len(list(outbox.glob("*"))) if outbox.is_dir() else 0),
            "bridge_cmd": (KIT / "start-bridge.cmd").is_file(),
            "pulse_cmd": (KIT / "start-pulse.cmd").is_file()}


def sec_memory():
    kn = STATE / "knowledge"
    files = (len(list(kn.rglob("*"))) if kn.is_dir() else 0)
    bank = STATE / "memory_bank.jsonl"
    lines = 0
    if bank.is_file():
        try:
            lines = sum(1 for _ in bank.open("rb"))
        except OSError:
            lines = 0
    km = STATE / "know_map.json"
    return {"ok": True, "knowledge_files": files,
            "memory_bank_lines": lines,
            "know_map_kb": round(km.stat().st_size / 1024, 1) if km.is_file() else 0,
            "note": "写记忆走 memory_sync（落链库拿 version/chain）"}


def sec_credentials():
    slots = ("GBT_LLM_API_KEY", "ABLITERATION_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY")
    vault = [p.name for p in STATE.glob("deepseek_key*")]
    return {"ok": True,
            "slots": [{"env": s, "configured": bool(os.environ.get(s))} for s in slots],
            "vault_files": vault,
            "note": "只报槽位与文件名，不回显任何明文"}


def sec_proxy():
    import winreg
    reg = {}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings") as k:
            for name in ("ProxyEnable", "ProxyServer", "ProxyOverride", "AutoConfigURL"):
                try:
                    reg[name] = winreg.QueryValueEx(k, name)[0]
                except OSError:
                    reg[name] = None
    except OSError as e:
        reg = {"error": str(e)[:100]}
    return {"ok": True, "system": reg,
            "env": {k: os.environ.get(k, "") for k in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY")}}


def sec_tools():
    groups = {}
    try:
        man = json.loads((KIT / "manifest.json").read_text(encoding="utf-8"))
        for t in (man.get("tools") or []):
            g = str(t.get("name", "")).split("_")[0]
            groups[g] = groups.get(g, 0) + 1
        total = len(man.get("tools") or [])
    except Exception:  # noqa: BLE001
        total = 0
    boot = {}
    try:
        boot = json.loads((STATE / "boot-selfcheck-last.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "tentacle_tools": total, "groups": groups, "boot_selfcheck": boot,
            "doctor": "node tests\\run-all.mjs / node runtime\\server.mjs --doctor"}


def sec_datastore():
    rows = {}
    c = _db()
    if c:
        try:
            for t in ("projects", "artifacts", "links", "runs"):
                rows[t] = c.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
        finally:
            c.close()
    backups = len(list((REPO / "state" / "backup").glob("*"))) if (REPO / "state" / "backup").is_dir() else 0
    return {"ok": True, "db": str(DB), "db_mb": round(DB.stat().st_size / 1e6, 2) if DB.is_file() else 0,
            "tables": rows, "backups": backups,
            "policy": "项目数据进库；大件只存路径 + sha256"}


def sec_recycle():
    def count():
        # ① 回收站命名空间：拿「项」数（目录 + 文件都算一项）
        ps1 = ("$sh=New-Object -ComObject Shell.Application; $rb=$sh.NameSpace(0xA); "
               "if($null -eq $rb){'null'}else{$rb.Items().Count}")
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps1],
                               capture_output=True, text=True, timeout=8)
            out = (r.stdout or "").strip().splitlines()
            if out and out[-1].strip() not in ("", "null"):
                return {"count": int(out[-1].strip()), "source": "shell"}
        except Exception:
            pass
        # ② 兜底：直接数 $Recycle.Bin 下的条目（Shell 拿不到时）
        ps2 = ("$p=Join-Path $env:SystemDrive '$Recycle.Bin'; $n=0; "
               "if(Test-Path -LiteralPath $p){$n=(Get-ChildItem -LiteralPath $p -Force -Recurse "
               "-ErrorAction SilentlyContinue | Measure-Object).Count}; $n")
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps2],
                               capture_output=True, text=True, timeout=25)
            out = (r.stdout or "").strip().splitlines()
            if out:
                return {"count": int(out[-1].strip()), "source": "fs"}
        except Exception as e:
            return {"count": None, "error": str(e)[:120]}
        return {"count": None, "error": "回收站读不到"}

    return {"ok": True, **_cached("recycle", 30, lambda: _safe(count, {"count": None}))}


def sec_about():
    boot = {}
    try:
        boot = json.loads((STATE / "boot-selfcheck-last.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "name": "GBT小土豆V8", "version": boot.get("version") or "8.0.0",
            "developer": "自由的风", "repo": str(REPO),
            "console": "http://127.0.0.1:8766/", "tentacle": TENTACLE,
            "boot_selfcheck_at": boot.get("iso") or boot.get("ts") or ""}


SECTIONS = {
    "stats": sec_stats, "device": sec_device, "env": sec_env, "storage": sec_storage,
    "appearance": sec_appearance,
    "notify": sec_notify, "hotkeys": sec_hotkeys, "platforms": sec_platforms,
    "providers": sec_providers, "models": sec_models, "skills": sec_skills, "tags": sec_tags,
    "connectors": sec_connectors, "memory": sec_memory, "credentials": sec_credentials,
    "proxy": sec_proxy, "tools": sec_tools, "datastore": sec_datastore,
    "recycle": sec_recycle, "about": sec_about,
}


def _read_settings() -> dict:
    p = STATE / "settings.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    except Exception:  # noqa: BLE001
        return {}


def _write_settings(d: dict) -> None:
    p = STATE / "settings.json"
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def build() -> dict:
    out = {"ok": True, "ts": time.time(), "iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "repo": str(REPO), "sections": {}}
    for key, fn in SECTIONS.items():
        t0 = time.time()
        try:
            val = fn()
        except Exception as e:  # noqa: BLE001
            val = {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:160])}
        val["ms"] = int((time.time() - t0) * 1000)
        out["sections"][key] = val
    return out


def act(payload: dict) -> dict:
    kind = str((payload or {}).get("kind") or "").strip()
    if kind == "notify":
        title = str(payload.get("title") or "GBT 通知测试")[:60]
        text = str(payload.get("text") or "这是一条来自设置中心的测试通知")[:160]
        try:
            r = _http_json(TENTACLE + "/call", 6.0, {"tool": "sys_notify", "args": {"title": title, "text": text}})
            body = r.get("result", r)
            return {"ok": bool(body.get("ok", True)), "result": body}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": "触手不可达：%s" % str(e)[:120]}

    if kind == "recycle_empty":
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", "Clear-RecycleBin -Force -ErrorAction Stop; 'ok'"],
                               capture_output=True, text=True, timeout=60)
            _CACHE.pop("recycle", None)
            return {"ok": r.returncode == 0, "stdout": (r.stdout or "").strip()[:80],
                    "stderr": (r.stderr or "").strip()[:160]}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)[:160]}

    if kind == "set_settings":
        cur = _read_settings()
        for k in ("theme", "accent", "density", "notify", "notify_level"):
            if k in (payload or {}):
                cur[k] = payload[k]
        cur["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        _write_settings(cur)
        return {"ok": True, "settings": cur}

    return {"ok": False, "error": "unknown kind: %s" % (kind or "(empty)")}


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False)[:2000])
