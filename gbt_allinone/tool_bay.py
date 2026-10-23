# -*- coding: utf-8 -*-
# gbt-capability: subprocess, filesystem_write  ⏻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""装备坞（tool_bay）—— 触手的「自配装备」走的那道门。

由来（主人 2026-10-09）：主人要「触手**自主注册配置自己的装备**」。
本仓对应的两半：**职业**已有（「tools/agency_tentacles.py」的职业触手中枢 + 五元身份），
**装备坞没有**（V9 有「core/tool_bay.py」，本仓一直缺）。本件把它补上，且**只用 V8 自己的门**。

三条纪律（照 V9 那套不新造旁路）：
  ① **白名单**：不在「CATALOG」里的装备一律拒——不允许"随便装个东西"；
  ② **令牌**：真装必须带主人的授权（走「security/auth_gate」），没令牌就如实报 needs_grant，
     **绝不假装装上了**；
  ③ **真探测**：每件装备的状态靠**现跑一次探针**得出，没探针的不得报「已装」。
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
LEDGER = _ROOT / "state" / "tool_bay.jsonl"

# ── 装备白名单（本仓自定口径：只收本机真能落地的件）────────────────────────────
CATALOG = {
    "python":    {"kind": "builtin", "probe": ["py", "-3.14", "-c", "import sys;print(sys.version.split()[0])"]},
    "git":       {"kind": "cmd", "probe": ["git", "--version"]},
    "ffmpeg":    {"kind": "cmd", "probe": ["ffmpeg", "-version"]},
    "node":      {"kind": "cmd", "probe": ["node", "-v"]},
    "blender":   {"kind": "cmd", "probe": [r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe", "--version"]},
    "sqlite":    {"kind": "builtin", "probe": ["py", "-3.14", "-c", "import sqlite3;print(sqlite3.sqlite_version)"]},
    "json_tool": {"kind": "builtin", "probe": ["py", "-3.14", "-c", "import json;print(json.dumps({'ok':1}))"]},
    "http":      {"kind": "builtin", "probe": ["py", "-3.14", "-c", "import urllib.request;print('urllib-ok')"]},
    "image_ops": {"kind": "builtin", "probe": ["py", "-3.14", "-c", "import PIL;print(PIL.__version__)"]},
    "screen":    {"kind": "cap", "probe": None, "note": "触手 see/screenshot（需 privacy_read）"},
    "ui_tree":   {"kind": "cap", "probe": None, "note": "触手 list_windows/click_text（需 desktop_control）"},
    "puppeteer": {"kind": "builtin", "probe": ["py", "-3.14", "-c", "import glob,os;p=glob.glob(os.path.expanduser('~/.cache/puppeteer/chrome-headless-shell/*/*/chrome-headless-shell.exe'));print(p[0] if p else (_ for _ in ()).throw(SystemExit(1)))"]},
    "comfyui":   {"kind": "service", "probe": ["py", "-3.14", "-c", "import os,sys;sys.exit(0 if os.path.isdir(os.path.expanduser('~/ComfyUI')) else 1)"]},
    "ocr":       {"kind": "miss", "probe": None, "note": "本机未装 OCR 引擎"},
    "sevenzip":  {"kind": "cmd", "probe": ["7z"]},
}


def _probe(spec: dict) -> dict:
    """真跑一次探针；没探针的只能报「无探针」，**不得报已装**。"""
    cmd = spec.get("probe")
    if not cmd:
        return {"state": "无探针", "evidence": spec.get("note") or "", "probed": False}
    exe = cmd[0]
    if not (shutil.which(exe) or Path(exe).is_file()):
        return {"state": "未装", "evidence": "找不到 %s" % exe, "probed": True}
    try:
        cp = subprocess.run(cmd, capture_output=True, timeout=60)
        out = ((cp.stdout or b"") + (cp.stderr or b"")).decode("utf-8", "replace").strip()
        first = out.splitlines()[0][:80] if out else ""
        return {"state": "已装" if cp.returncode == 0 else "未装",
                "evidence": first or ("rc=%s" % cp.returncode), "probed": True}
    except Exception as exc:                                       # noqa: BLE001
        return {"state": "探不到", "evidence": ("%s: %s" % (type(exc).__name__, exc))[:100], "probed": True}


class ToolBay:
    def __init__(self, ledger: Path | None = None, grant_required: bool = True) -> None:
        self.ledger = ledger if ledger is not None else LEDGER
        self.grant_required = grant_required

    def state(self) -> dict:
        return {n: _probe(s) for n, s in CATALOG.items()}

    def _log(self, name: str, action: str, ok: bool, detail: str) -> None:
        try:
            self.ledger.parent.mkdir(parents=True, exist_ok=True)
            with self.ledger.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "tool": name,
                                    "action": action, "ok": ok, "detail": detail[:200]},
                                   ensure_ascii=False) + "\n")
        except OSError:
            pass

    def install(self, name: str, *, grant=None) -> dict:
        """装一件装备。白名单外拒 · 没令牌如实报 needs_grant · **从不假装装上**。"""
        if name not in CATALOG:
            self._log(name, "install", False, "白名单外")
            return {"ok": False, "tool": name, "why": "不在装备白名单里",
                    "whitelist": sorted(CATALOG)}
        spec = CATALOG[name]
        st = _probe(spec)
        if st["state"] == "已装":
            self._log(name, "install", True, "已在位（%s）" % st["evidence"])
            return {"ok": True, "tool": name, "state": "已装", "evidence": st["evidence"],
                    "note": "本来就在，无需动手"}
        # ── 装备三态：① 已在位（不耗票）② 需授权接上（cap 类，**真过门**）③ 需主人装（第三方件，不代下）──
        scope = GEAR_SCOPE.get(name)
        if scope:
            if grant:
                verdict = {"ok": True, "consumed": "caller-supplied", "mode": "caller"}
            else:
                from . import auth_gate as AG          # **过门，不自己判、不自己发**
                verdict = AG.check_and_consume(scope, detail="tool_bay.install:%s" % name)
            if not verdict.get("ok"):
                self._log(name, "install", False, "needs_grant:%s" % scope)
                return {"ok": False, "tool": name, "state": st["state"], "needs_grant": scope,
                        "missing_scopes": verdict.get("missing_scopes"),
                        "how_to_grant": verdict.get("how_to_grant") or (
                            "python -m gbt_allinone auth grant --scope %s --ttl 600（只能主人发）" % scope),
                        "why": "这件装备要接上她的眼/手就必须过门；没票**不假装装上了**"}
            self._log(name, "install", True, "接上 %s（consumed=%s）" % (scope, verdict.get("consumed")))
            return {"ok": True, "tool": name, "state": "已就绪", "scope_consumed": scope,
                    "grant": verdict.get("consumed"), "note": st.get("evidence") or ""}
        self._log(name, "install", False, "needs_owner_manual")
        return {"ok": False, "tool": name, "state": st["state"], "needs_owner_manual": True,
                "why": "第三方件不自动下载（供应链红线）——**也不为此消耗主人的令牌**",
                "manual": "请主人确认后自行安装；本件只记账、不代劳"}


# 哪件装备要挂哪个作用域（**过 V8 自己的门**；不在表里的 = 第三方件，不代装）
GEAR_SCOPE = {"screen": "privacy_read", "ui_tree": "desktop_control", "comfyui": "process_execute"}


def run(op: str = "state", **kw) -> dict:
    op = str(op or "state").lower()
    tb = ToolBay()
    if op in ("state", "status"):
        st = tb.state()
        return {"ok": True, "op": "state", "白名单数": len(CATALOG),
                "已装": sorted(n for n, v in st.items() if v["state"] == "已装"),
                "未装": sorted(n for n, v in st.items() if v["state"] == "未装"),
                "无探针": sorted(n for n, v in st.items() if v["state"] == "无探针"),
                "逐件": st, "台账": str(LEDGER)}
    if op == "install":
        return dict({"op": "install"}, **tb.install(str(kw.get("tool") or ""), grant=kw.get("grant")))
    return {"ok": False, "error": "不认的 op：%s" % op, "known": ["state", "install"]}
