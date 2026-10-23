# gbt-capability: lobehub
"""LobeHub 桌面端全控（主人令 2026-09-27）。

主人原话：「把 `C:\\Users\\ADMIN\\Desktop\\LobeHub.lnk` 做成**可执行的插件**安装到**工具区**，
这个玩意功能是真的多，**都要跟触手双向绑定**，只要是**可控制的都要绑上**。」

**真身（实测，不是猜）**：
- 快捷方式 → `C:\\Users\\ADMIN\\AppData\\Local\\Programs\\LobeHub\\LobeHub.exe`（Electron **2.2.18**）
- 数据：`%APPDATA%\\lobehub\\`（`lobehub-settings.json` 22 键 · `lobehub-storage\\local-database.sqlite3`
  13MB · `Local Storage\\leveldb` · `logs\\main.log` 1.2 万行）
- 运行时：`lobehub-storage\\heteroAgent\\{runs,bindings,inflight-runs.json}` + `~/.lobehub/traces/*.json`
- 本地文件桥：`127.0.0.1:33250`（日志里 `StaticFileServerManager` 自己报的端口；**无鉴权**）
- 云面：`gatewayEnabled=true` → `device-gateway.lobehub.com`（38 个服务商、图像模型清单都在**账号**里）

## 可控制面（每一样都进 `state/surfaces/lobehub.json` —— **消失即断连**）

| 面 | 控什么 | 怎么控 |
|---|---|---|
| ① 进程/启动 | exe · 版本 · PID · 在跑没跑 | `launch` / `close`（**过 `process_execute` 门**） |
| ② 设置 | 设置文件里**每一个键** | `settings`（读只回形状 + 密钥掩码；写走 `filesystem_write` 门 + 白名单） |
| ③ **可控制按键** | `settings.shortcuts` 每个键（快速撰写/开设置…） | 同一个 `settings`（白名单里 `shortcuts.*`） |
| ④ 数据 | 桌面端**真调的接口操作名** + agent id | `ops` / `agents`（读**库的副本**，绝不碰在跑的库） |
| ⑤ 运行时 | 助理运行记录 / 追踪 / 日志 | `runtime`（只读） |
| ⑥ 网络 | 本地文件桥通不通 | `bridge`（**主机钉死 127.0.0.1** + 端口整数校验 + 固定路径） |
| ⑦ 云面 | gateway 开关/URL/设备号 | 只读 —— 服务商与模型在账号里，**本地改不了**，如实标"不可本地控" |

**三条硬口径**（照抄 ComfyUI 那套，不另立门）：
- **凭据只回形状不回值**：设置里的 `encryptedTokens` 只报"有/长度/掩码"，**永不回值**；
  掩码按**键名**判，不按值判（血账：按值判把 DPAPI 密文原样打出来过一次）。
- **在跑的库只读副本**：`local-database.sqlite3` 拷到临时目录再读，绝不 `mode=rw` 打开在跑的库。
- **出网钉死**：只许 `127.0.0.1` + 端口是日志里报的整数 + 固定探测路径 + 拒重定向。

op=status / surface / settings / shortcuts / ops / agents / runtime / bridge / launch / close / verify / where
"""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_STATE = _ROOT / "state"
_MANIFEST = _STATE / "surfaces" / "lobehub.json"
_LEDGER = _STATE / "lobehub.jsonl"
_LNK = Path(r"C:\Users\ADMIN\Desktop\LobeHub.lnk")
_EXE_DEFAULTS = [
    Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\LobeHub\LobeHub.exe")),
    Path(os.path.expandvars(r"%PROGRAMFILES%\LobeHub\LobeHub.exe")),
]
_USERDATA = Path(os.path.expandvars(r"%APPDATA%\lobehub"))
_APP = "LobeHub.exe"

# 阈值：全部来自**实测**，留余量（实测值见模块 docstring）
MIN_SETTINGS = 15          # 实测 22
MIN_SHORTCUTS = 3          # 实测 4
MIN_OPS = 15               # 实测 27
MIN_AGENTS = 1             # 实测 9（掉到 0 = 账号面变了：未登录/换号，值得看一眼）
MIN_KEYS = 40              # 合计实测 62（22+4+27+9）

# 设置里**可以写**的键（白名单）。安全姿态类（gateway/代理/令牌）一律不在内。
WRITABLE = {
    "locale", "themeMode", "appTrayVisible", "updateChannel", "windowsShellMode",
    "heteroTracingEnabled", "desktopOnboardingCompleted",
    "shortcuts.quickComposer", "shortcuts.quickChat", "shortcuts.showApp", "shortcuts.openSettings",
}
_FORBIDDEN = ("token", "key", "secret", "password", "credential", "cookie", "auth")


# ═══════════════════════ 基础读数 ═══════════════════════

def _exe() -> tuple:
    """真身 exe。先解快捷方式（从 .lnk 字节里取路径），再退到默认安装位。"""
    if _LNK.is_file():
        try:
            raw = _LNK.read_bytes()
            for enc in ("utf-16-le", "latin-1"):
                m = re.search(r"([A-Za-z]:\\\\?[^\x00\"<>|]{3,180}?\.exe)", raw.decode(enc, "ignore"))
                if m:
                    p = Path(m.group(1).replace("\\\\", "\\"))
                    if p.is_file():
                        return p, "lnk:" + _LNK.name
        except OSError:
            pass
    for p in _EXE_DEFAULTS:
        if p.is_file():
            return p, "default:" + p.parent.name
    return None, "未找到"


def _version(exe: Path) -> str:
    """版本：读 **exe 自己的 PE 版本资源**（不猜、不起子进程）。

    ⚠️ 两个坑（都实测过）：
    ① `resources/package.json` 是 **CLI 子包** `@lobehub/cli` 的（写着 0.0.55），
       拿它当桌面端版本就是**假读数** —— 桌面端真身是 2.2.18；
    ② `app.asar` 的头部只列文件名，**不含版本**（早先在这里找，找不到）。
    """
    try:
        import ctypes                                          # noqa: PLC0415
        from ctypes import wintypes                            # noqa: PLC0415

        class _Fixed(ctypes.Structure):
            _fields_ = [("dwSignature", wintypes.DWORD), ("dwStrucVersion", wintypes.DWORD),
                        ("dwFileVersionMS", wintypes.DWORD), ("dwFileVersionLS", wintypes.DWORD),
                        ("dwProductVersionMS", wintypes.DWORD), ("dwProductVersionLS", wintypes.DWORD)]

        size = ctypes.windll.version.GetFileVersionInfoSizeW(str(exe), None)
        if size:
            buf = ctypes.create_string_buffer(size)
            if ctypes.windll.version.GetFileVersionInfoW(str(exe), 0, size, buf):
                ptr = ctypes.c_void_p()
                ln = wintypes.UINT()
                if ctypes.windll.version.VerQueryValueW(buf, "\\", ctypes.byref(ptr), ctypes.byref(ln)):
                    f = ctypes.cast(ptr, ctypes.POINTER(_Fixed)).contents
                    ms, ls = f.dwFileVersionMS, f.dwFileVersionLS
                    v = "%d.%d.%d.%d" % (ms >> 16, ms & 0xFFFF, ls >> 16, ls & 0xFFFF)
                    return v.rstrip(".0") if v.endswith(".0") and v.count(".") == 3 else v
    except Exception:                                         # noqa: BLE001
        pass
    return "未知（PE 版本资源读不出来）"


def _pids() -> list:
    try:
        import psutil                                        # noqa: PLC0415
    except ImportError:
        return []
    out = []
    for p in psutil.process_iter(["name", "pid"]):
        try:
            if (p.info.get("name") or "").lower() == _APP.lower():
                out.append(p.info["pid"])
        except Exception:                                     # noqa: BLE001
            continue
    return sorted(out)


def _settings_path() -> Path:
    p = _USERDATA / "lobehub-settings.json"
    return p


def _settings() -> dict:
    p = _settings_path()
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _mask_value(key: str, v):
    """**按键名掩码**（血账：按值判会把密文原样打出来）。值只回形状，密钥永不回值。"""
    if isinstance(v, dict):
        return {k: _mask_value(k, x) for k, x in v.items()}
    if isinstance(v, list):
        return [_mask_value(key, x) for x in v[:5]] + ([f"…共{len(v)}项"] if len(v) > 5 else [])
    if any(s in key.lower() for s in _FORBIDDEN):
        if isinstance(v, str):
            return f"<掩码:{(v[:4] if len(v) > 8 else '****')}****(len={len(v)})>"
        return f"<掩码:{type(v).__name__}>"
    if isinstance(v, str) and len(v) > 120:
        return v[:120] + f"…(len={len(v)})"
    return v


def _bridge_port() -> int:
    """本地文件桥端口：从 main.log 里 StaticFileServerManager 自己报的那行取（**不猜端口**）。"""
    lg = _USERDATA / "logs" / "main.log"
    if not lg.is_file():
        return 0
    try:
        txt = lg.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    m = None
    for m in re.finditer(r"HTTP file server started on port (\d{2,5})", txt):
        pass
    if not m:
        return 0
    port = int(m.group(1))
    return port if 1 <= port <= 65535 else 0


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_a, **_k):
        return None


def _bridge_get(port: int, path: str, timeout: float = 3.0) -> dict:
    """本地文件桥只读探一次。**主机钉死 127.0.0.1**（不接受任何外部主机），拒重定向。"""
    if not (1 <= int(port) <= 65535):
        return {"ok": False, "why": f"端口非法：{port}"}
    if not path.startswith("/"):
        return {"ok": False, "why": "路径必须是绝对路径形状（/…）"}
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path),
                                headers={"User-Agent": "gbt-lobehub/1.0"})
    try:
        with opener.open(req, timeout=timeout) as r:
            return {"ok": True, "code": r.status, "bytes": len(r.read(4096)), "body_head": ""}
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read(200).decode("utf-8", "replace")
        except Exception:                                     # noqa: BLE001
            pass
        return {"ok": False, "code": e.code, "why": body[:160]}
    except Exception as exc:                                  # noqa: BLE001
        return {"ok": False, "why": f"{type(exc).__name__}: {str(exc)[:120]}"}


def _copy_db() -> Path | None:
    """在跑的库**只读副本**（绝不打开在跑的那份）。"""
    src = _USERDATA / "lobehub-storage"
    db = src / "local-database.sqlite3"
    if not db.is_file():
        return None
    td = Path(tempfile.mkdtemp(prefix="lobehub_ro_"))
    for f in ("local-database.sqlite3", "local-database.sqlite3-wal", "local-database.sqlite3-shm"):
        p = src / f
        if p.is_file():
            try:
                shutil.copyfile(p, td / f)
            except OSError:
                pass
    return td / "local-database.sqlite3"


def _db_facts() -> dict:
    """从库副本里读：桌面端真调的**接口操作名** + agent id。"""
    import sqlite3                                            # noqa: PLC0415
    cp = _copy_db()
    if not cp:
        return {"ok": False, "why": "没有本地库（lobehub-storage/local-database.sqlite3 不在）"}
    try:
        con = sqlite3.connect("file:%s?mode=ro" % cp.as_posix(), uri=True)
        cur = con.cursor()
        ids = [r[0] for r in cur.execute("select id from local_records")]
        con.close()
    except Exception as exc:                                  # noqa: BLE001
        return {"ok": False, "why": f"{type(exc).__name__}: {str(exc)[:120]}"}
    ops, agents = {}, set()
    for i in ids:
        m = re.search(r'::@"([^"]+)"', i)
        if m:
            ops[m.group(1)] = ops.get(m.group(1), 0) + 1
        for a in re.findall(r"agt_[A-Za-z0-9]+", i):
            agents.add(a)
    return {"ok": True, "rows": len(ids), "ops": ops, "agents": sorted(agents)}


def _dirs() -> dict:
    d = {
        "userdata": _USERDATA,
        "settings": _settings_path(),
        "db": _USERDATA / "lobehub-storage" / "local-database.sqlite3",
        "leveldb": _USERDATA / "Local Storage" / "leveldb",
        "logs": _USERDATA / "logs" / "main.log",
        "runs": _USERDATA / "lobehub-storage" / "heteroAgent" / "runs",
        "bindings": _USERDATA / "lobehub-storage" / "heteroAgent" / "bindings",
        "inflight": _USERDATA / "lobehub-storage" / "heteroAgent" / "inflight-runs.json",
        "traces": Path(os.path.expanduser("~")) / ".lobehub" / "traces",
    }
    return {k: {"path": str(v), "exists": v.exists()} for k, v in d.items()}


def _gate(scope: str, detail: str) -> dict | None:
    """过授权门；可信上下文（主人本机）免。**AI 无权自批** —— 缺票如实回。"""
    try:
        from .. import auth_gate
        from ..security import policy as _policy
    except ImportError:
        sys.path.insert(0, str(_ROOT))
        import gbt_allinone as _g                                # noqa: F401
        from gbt_allinone import auth_gate                       # type: ignore
        from gbt_allinone.security import policy as _policy      # type: ignore
    if _policy.is_trusted():
        return None
    g = auth_gate.check_and_consume(scope, detail=detail)
    if g.get("ok"):
        return None
    return {"ok": False, "denied": True, "gate": scope, "error": g.get("error"),
            "how_to_grant": g.get("how_to_grant")}


def _log(row: dict) -> None:
    _LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with open(_LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row}, ensure_ascii=False) + "\n")


# ═══════════════════════ 各 op ═══════════════════════

def status(**_kw) -> dict:
    exe, src = _exe()
    pids = _pids()
    port = _bridge_port()
    up = bool(port) and socket.socket().connect_ex(("127.0.0.1", port)) == 0
    return {"ok": bool(exe), "op": "status",
            "installed": bool(exe), "exe": str(exe) if exe else "", "exe_source": src,
            "version": _version(exe) if exe else "",
            "running": bool(pids), "pids": pids,
            "userdata": str(_USERDATA), "userdata_exists": _USERDATA.is_dir(),
            "bridge_port": port, "bridge_up": up,
            "_口径": "装了没装 = 真看盘上有没有 exe；在跑没跑 = 真查进程；桥 = 端口来自日志 + 真连一次"}


def settings(key: str = "", set_value: str = "", **_kw) -> dict:
    """读：每个键只回形状，密钥掩码。写：**白名单 + 过 `filesystem_write` 门**，先备份。"""
    s = _settings()
    if not key:
        return {"ok": True, "op": "settings.get", "path": str(_settings_path()),
                "count": len(s), "keys": sorted(s),
                "values": {k: _mask_value(k, v) for k, v in sorted(s.items())},
                "writable": sorted(WRITABLE),
                "_口径": "**按键名掩码**；令牌类只报形状（有/长度/掩码），永不回值"}
    if key not in s and key.split(".")[0] not in s:
        return {"ok": False, "op": "settings.get", "error": f"没有这个键：{key}", "keys": sorted(s)}
    if set_value == "":
        return {"ok": True, "op": "settings.get", "key": key,
                "value": _mask_value(key, s.get(key))}
    # ---- 写 ----
    if key not in WRITABLE:
        return {"ok": False, "op": "settings.set", "refused": True, "key": key,
                "why": "不在可写白名单里（安全姿态类键不许由能力位改：gateway/代理/令牌）",
                "writable": sorted(WRITABLE)}
    if any(x in key.lower() for x in _FORBIDDEN):
        return {"ok": False, "op": "settings.set", "refused": True, "key": key,
                "why": "键名含凭据字样 ⇒ 一律拒（凭据不走这条路）"}
    gate = _gate("filesystem_write", f"lobehub settings set {key}={set_value[:40]}")
    if gate:
        return {"ok": False, "op": "settings.set", **gate}
    if not _USERDATA.is_dir():
        return {"ok": False, "op": "settings.set", "error": "LobeHub 数据目录不在"}
    p = _settings_path()
    prev = p.read_text(encoding="utf-8") if p.is_file() else "{}"
    bak = p.with_name(p.name + time.strftime(".bak-%Y%m%d-%H%M%S"))
    bak.write_text(prev, encoding="utf-8")
    try:
        cur = json.loads(prev)
        if "." in key:
            head, tail = key.split(".", 1)
            cur.setdefault(head, {})[tail] = set_value
        else:
            cur[key] = set_value
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, p)
    except (OSError, json.JSONDecodeError) as exc:             # noqa: BLE001
        return {"ok": False, "op": "settings.set", "error": f"{type(exc).__name__}: {exc}",
                "backup": str(bak)}
    _log({"event": "settings.set", "key": key, "value": set_value[:60], "backup": bak.name})
    return {"ok": True, "op": "settings.set", "key": key, "value": set_value,
            "backup": bak.name,
            "note": "改完要**重启应用**才生效（Electron 设置是启动时读的）"}


def shortcuts(**_kw) -> dict:
    """**可控制按键**面：settings.shortcuts 的每个键。"""
    sc = (_settings().get("shortcuts") or {})
    return {"ok": True, "op": "shortcuts", "count": len(sc),
            "keys": sorted(sc), "values": sc,
            "_口径": "这些就是桌面端的可控制按键（空串 = 该动作没绑键）"}


def ops(**_kw) -> dict:
    f = _db_facts()
    if not f.get("ok"):
        return {"ok": False, "op": "ops", **f}
    o = f["ops"]
    return {"ok": True, "op": "ops", "count": len(o),
            "ops": dict(sorted(o.items(), key=lambda kv: -kv[1])),
            "_口径": "桌面端**真调的接口操作名**（从本地库缓存键里枚举，不是猜的）"}


def agents(**_kw) -> dict:
    f = _db_facts()
    if not f.get("ok"):
        return {"ok": False, "op": "agents", **f}
    return {"ok": True, "op": "agents", "count": len(f["agents"]), "agents": f["agents"],
            "_口径": "界面上的助理（agent id，来自本地库缓存键）"}


def runtime(**_kw) -> dict:
    d = _dirs()
    runs = d["runs"]["path"]
    tr = d["traces"]["path"]
    infl = Path(d["inflight"]["path"])
    n_runs = len(list(Path(runs).glob("*"))) if Path(runs).is_dir() else 0
    n_tr = len(list(Path(tr).glob("*.json"))) if Path(tr).is_dir() else 0
    busy = []
    if infl.is_file():
        try:
            busy = (json.loads(infl.read_text(encoding="utf-8")) or {}).get("runs") or []
        except (OSError, json.JSONDecodeError):
            busy = []
    tail = ""
    lg = Path(d["logs"]["path"])
    if lg.is_file():
        try:
            tail = "\n".join(lg.read_text(encoding="utf-8", errors="replace").splitlines()[-6:])[-700:]
        except OSError:
            tail = ""
    return {"ok": True, "op": "runtime", "runs": n_runs, "traces": n_tr,
            "inflight": len(busy), "log_tail": tail, "dirs": d,
            "_口径": "运行记录/追踪/日志只读；inflight 非空 = 有助理正在跑（或卡住）"}


def bridge(**_kw) -> dict:
    """本地文件桥：端口来自日志，**只连 127.0.0.1**，固定探测路径，拒重定向。

    非 ASCII 那条要**百分号编码后再发**：否则挡住请求的是**我们自己的** urllib
    （`UnicodeEncodeError`），读出来就变成"看似可用"——那是把客户端的问题算到桥头上。
    """
    port = _bridge_port()
    if not port:
        return {"ok": False, "op": "bridge", "error": "日志里没有 StaticFileServerManager 的端口行"}
    root = _bridge_get(port, "/")
    outside = _bridge_get(port, "/C:/Windows/win.ini")
    cn = _bridge_get(port, urllib.parse.quote("/C:/Users/ADMIN/Desktop/GBT小土豆V8/AGENTS.md"))
    code = cn.get("code")
    if code == 500:
        cn_verdict = "撑不住（应用侧 URIError: URI malformed）"
    elif code == 200:
        cn_verdict = "可用（真读到了）"
    elif code == 404:
        cn_verdict = "拿不到（百分号编码后仍被拒：File Not Found）"
    else:
        cn_verdict = f"未知（code={code} / {str(cn.get('why'))[:60]}）"
    # 应用自己的日志怎么说（原始非 ASCII 请求那条是**读日志**得到的，不是猜的）
    lg = _USERDATA / "logs" / "main.log"
    uri_err = 0
    if lg.is_file():
        try:
            uri_err = len(re.findall(r"URIError: URI malformed",
                                     lg.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            uri_err = 0
    return {"ok": bool(root.get("code") in (200, 400)), "op": "bridge",
            "port": port, "root": root, "outside_root": outside, "non_ascii_path": cn,
            "log_evidence": {"URIError_malformed 行数": uri_err, "src": "logs/main.log（应用自己记的）"},
            "readings": {
                "桥在听": bool(port),
                "无鉴权": True,
                "越界文件被拒": outside.get("code") == 404,
                "非 ASCII 路径": cn_verdict,
            },
            "_口径": ("只连 127.0.0.1（主机钉死）；`desktop://` 根校验在（/C:/Windows/win.ini 被拒）；"
                      "**非 ASCII 路径这条桥撑不住**（原始请求在应用侧 URIError，见 log_evidence；"
                      "百分号编码后仍拿不到）⇒ 我们的仓库路径带中文，走不了它")}


def launch(**_kw) -> dict:
    """启动（**过 `process_execute` 门**）。已在跑就不重复起。"""
    exe, _src = _exe()
    if not exe:
        return {"ok": False, "op": "launch", "error": "找不到 LobeHub.exe"}
    if _pids():
        return {"ok": True, "op": "launch", "already": True, "pids": _pids()}
    gate = _gate("process_execute", "lobehub launch")
    if gate:
        return {"ok": False, "op": "launch", **gate}
    try:
        os.startfile(str(exe))                                 # noqa: S606
    except OSError as exc:
        return {"ok": False, "op": "launch", "error": f"{type(exc).__name__}: {exc}"}
    _log({"event": "launch", "exe": str(exe)})
    return {"ok": True, "op": "launch", "exe": str(exe), "note": "起来了（查 status 看在跑没跑）"}


def close(pid: int = 0, **_kw) -> dict:
    """关闭（**过 `process_execute` 门**）：默认全部 LobeHub 进程；给 pid 就只关那个。"""
    targets = [pid] if pid else _pids()
    if not targets:
        return {"ok": True, "op": "close", "already": True}
    gate = _gate("process_execute", f"lobehub close {len(targets)} pid")
    if gate:
        return {"ok": False, "op": "close", **gate}
    try:
        import psutil                                        # noqa: PLC0415
    except ImportError:
        return {"ok": False, "op": "close", "error": "没有 psutil ⇒ 不敢用别的方式杀（怕误杀）"}
    done, err = [], []
    for p in targets:
        try:
            psutil.Process(p).terminate()
            done.append(p)
        except Exception as exc:                             # noqa: BLE001
            err.append(f"{p}:{type(exc).__name__}")
    _log({"event": "close", "pids": done, "err": err})
    return {"ok": not err, "op": "close", "closed": done, "errors": err}


def surface(rescan: bool = True, **_kw) -> dict:
    """可控制面清单：七大面所有可控制键；与上次对比（**消失即断连**）。"""
    prev = {}
    if _MANIFEST.is_file():
        try:
            prev = json.loads(_MANIFEST.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prev = {}
    exe, src = _exe()
    st = _settings()
    f = _db_facts()
    keys_settings = sorted(st)
    keys_short = sorted((st.get("shortcuts") or {}))
    keys_ops = sorted(f.get("ops") or {})
    keys_agents = list(f.get("agents") or [])
    dirs = _dirs()
    port = _bridge_port()
    keys = (keys_settings + keys_short + keys_ops + keys_agents
            + ["exe", "version", "pids", "bridge"] + sorted(dirs))
    gone = sorted(set(prev.get("keys") or []) - set(keys))
    added = sorted(set(keys) - set(prev.get("keys") or []))
    m = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "app": {"exe": str(exe) if exe else "", "exe_source": src,
                 "version": _version(exe) if exe else "", "running": bool(_pids()),
                 "pids": _pids()},
         "keys": keys,
         "settings_keys": keys_settings, "shortcut_keys": keys_short,
         "api_ops": keys_ops, "agents": keys_agents,
         "dirs": dirs,
         "bridge": {"port": port, "up": bool(port) and socket.socket().connect_ex(("127.0.0.1", port)) == 0},
         "cloud": {"gateway_enabled": st.get("gatewayEnabled"),
                   "gateway_url": st.get("gatewayUrl"),
                   "device_id_present": bool(st.get("gatewayDeviceId")),
                   "note": "服务商/模型清单在**云账号**里 —— 本地改不了，如实标不可本地控"},
         "counts": {"keys": len(keys), "settings": len(keys_settings), "shortcuts": len(keys_short),
                    "api_ops": len(keys_ops), "agents": len(keys_agents), "dirs": len(dirs)},
         "gone": gone, "added": added,
         "_口径": ("让 LobeHub 自己报：设置文件键 + 本地库副本里的接口操作名/助理 + 日志里的端口 + 真查进程；"
                   "**消失键 = 断连**，要解释或补")}
    _MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = _MANIFEST.with_name(_MANIFEST.name + ".tmp")
    tmp.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, _MANIFEST)
    _log({"event": "surface", **m["counts"], "gone": len(gone), "added": len(added)})
    return {"ok": True, "op": "surface", "counts": m["counts"],
            "gone_total": len(gone), "added_total": len(added), "gone_sample": gone[:5],
            "manifest": str(_MANIFEST.relative_to(_ROOT))}


def verify(**_kw) -> dict:
    problems = []
    if not _MANIFEST.is_file():
        problems.append("没有可控制面清单（先跑 surface）")
        return {"ok": False, "op": "verify", "problems": problems}
    d = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    c = d.get("counts") or {}
    for name, key, lo in (("设置键", "settings", MIN_SETTINGS), ("可控制按键", "shortcuts", MIN_SHORTCUTS),
                          ("接口操作", "api_ops", MIN_OPS), ("助理", "agents", MIN_AGENTS)):
        n = c.get(key) or 0
        if n < lo:
            problems.append(f"{name} {n} < 阈值 {lo}（**有漏**）")
    if (c.get("keys") or 0) < MIN_KEYS:
        problems.append(f"合计可控制键 {c.get('keys')} < 阈值 {MIN_KEYS}（**有漏**）")
    if d.get("gone"):
        problems.append(f"**断连**：{len(d['gone'])} 个键消失（例：{d['gone'][:3]}）")
    if not (d.get("app") or {}).get("exe"):
        problems.append("exe 找不到 ⇒ 插件等于没装")
    return {"ok": not problems, "op": "verify", "problems": problems, "counts": c,
            "thresholds": {"settings": MIN_SETTINGS, "shortcuts": MIN_SHORTCUTS,
                           "api_ops": MIN_OPS, "agents": MIN_AGENTS, "keys": MIN_KEYS},
            "_口径": "阈值来自实测；消失键=断连，要解释或补"}


def where(**_kw) -> dict:
    """给工具区/设置页看的接线契约。"""
    return {"ok": True, "op": "where", "kind": "lobehub", "tentacle": "lobehub",
            "entry": "run_task('lobehub', {...})",
            "ops": ["status", "surface", "settings", "shortcuts", "ops", "agents",
                    "runtime", "bridge", "launch", "close", "verify", "where"],
            "gates": {"launch/close": "process_execute", "settings 写": "filesystem_write"},
            "manifest": "state/surfaces/lobehub.json",
            "contract": [
                {"op": "status", "returns": "installed/exe/version/running/pids/bridge_up"},
                {"op": "surface", "returns": "counts{keys,settings,shortcuts,api_ops,agents} + gone"},
                {"op": "settings", "params": "key 空=全表（掩码）；key+set_value=写（白名单+过门）"},
                {"op": "shortcuts", "returns": "可控制按键表"},
                {"op": "ops", "returns": "桌面端真调的接口操作名"},
                {"op": "agents", "returns": "界面助理 id"},
                {"op": "bridge", "returns": "本地文件桥读数（含非 ASCII 限制）"},
            ]}


def run_op(op: str = "status", **params) -> dict:
    op = (op or "status").lower()
    for name, fn in (("status", status), ("surface", surface), ("settings", settings),
                     ("shortcuts", shortcuts), ("ops", ops), ("agents", agents),
                     ("runtime", runtime), ("bridge", bridge), ("launch", launch),
                     ("close", close), ("verify", verify), ("where", where)):
        if op == name:
            return fn(**params)
    return {"ok": False, "fail_closed": True,
            "error": f"未知 op:{op}（status/surface/settings/shortcuts/ops/agents/runtime/bridge/"
                     f"launch/close/verify/where）"}
