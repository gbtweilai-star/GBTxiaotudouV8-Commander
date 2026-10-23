# -*- coding: utf-8 -*-
"""mail-takeover —— 用触手（眼睛+手）直接接管浏览器，把「别名密码」取回来并封起来。

主人令（2026-10-21）：「使用万能插直接接管浏览器操作」。
所以这里**不碰 CDP、不另起 Chrome**：走 `run_task("tentacle", ...)` 唯一门，
看真实屏幕、点真实窗口、读真实剪贴板 —— 与主人所见同源。

一条铁律：**密码永远不进对话、不进 stdout**。
  · `seal-at X Y` 双击取词 → Ctrl+C → 剪贴板读回那个值 → **进程内**封进 DPAPI
    再写 HKCU\\Environment（mail-bind 的 env2 会从注册表兜底读到）；
    终端只打前 4 位掩码 + sha256 前 8 位，够比对、不够泄露。

用法：
  py -3.14 -X utf8 tools/codex-scripts/mail-takeover.py shot  step0
  py -3.14 -X utf8 tools/codex-scripts/mail-takeover.py go    "https://forwardemail.net/..."
  py -3.14 -X utf8 tools/codex-scripts/mail-takeover.py click 640 300
  py -3.14 -X utf8 tools/codex-scripts/mail-takeover.py type  "hello"
  py -3.14 -X utf8 tools/codex-scripts/mail-takeover.py key   ctrl+l
  py -3.14 -X utf8 tools/codex-scripts/mail-takeover.py seal-at 640 300
"""
from __future__ import annotations

import base64
import hashlib
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:                     # 从 tools/codex-scripts 里跑也能 import 引擎
    sys.path.insert(0, str(ROOT))
OUT = ROOT / "outputs" / "mail"
ENV_NAME = "GBT_SMTP_PASS"
VAULT_PROFILE = "imap"


def call(action: str, args=None, kwargs=None) -> dict:
    """挖到**最里层**那一层再返回。

    血泪：信封有两层 —— 外层 {gate,kind,status,result}，里层 {status,kind,result}，
    真正的载荷在 `result.result.result`（少挖一层就会念成"没拿到画面"，而其实画面取到了）。
    """
    from gbt_allinone import run_task
    env = run_task("tentacle", {"action": action,
                                "args": list(args or []),
                                "kwargs": dict(kwargs or {})}) or {}
    node = env
    for _ in range(4):
        if isinstance(node, dict) and isinstance(node.get("result"), dict):
            node = node["result"]
        else:
            break
    inner = dict(node) if isinstance(node, dict) else {"raw": str(node)[:400]}
    inner.setdefault("_env_status", env.get("status"))
    inner.setdefault("_denied", bool(env.get("denied")))
    return inner


def shot(name: str) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    r = call("see")
    b64 = r.get("image_base64") or ""
    if not b64:
        print(json.dumps({"ok": False, "why": "没拿到画面", "回执": {k: r.get(k) for k in
              ("ok", "error", "reason", "_env_status", "_denied")}}, ensure_ascii=False))
        return 2
    ext = "jpg" if (r.get("fmt") or "jpeg").lower() in ("jpeg", "jpg") else "png"
    path = OUT / ("%s.%s" % (name, ext))
    path.write_bytes(base64.b64decode(b64))
    print(json.dumps({"ok": True, "path": str(path), "size": r.get("size"),
                      "kb": round(path.stat().st_size / 1024, 1),
                      "capture_ms": r.get("capture_ms"), "engine": r.get("engine")},
                     ensure_ascii=False))
    return 0


def act(action: str, args, label: str) -> int:
    r = call(action, args)
    keep = {k: r.get(k) for k in ("ok", "found", "at", "text", "reason", "error",
                                  "saw_first", "_denied", "_env_status") if k in r}
    print(json.dumps({"action": label, "回执": keep}, ensure_ascii=False))
    return 0 if r.get("ok") else 2


def go(url: str) -> int:
    act("hotkey", ["ctrl", "l"], "hotkey ctrl+l")
    time.sleep(0.3)
    act("type", [url], "type url")
    time.sleep(0.3)
    act("press", ["enter"], "press enter")
    time.sleep(3.0)
    return 0


def _slurp_clipboard() -> str:
    """剪贴板读回（走触手，同一个门）。"""
    r = call("clipboard_read")
    txt = r.get("text") or r.get("clipboard") or ""
    return str(txt)


def seal_at(x: int, y: int) -> int:
    """双击取词 → Ctrl+C → 读剪贴板 → 进程内封存 → 只报掩码。"""
    r = call("copy_text_at", [x, y])
    val = str(r.get("text") or _slurp_clipboard() or "").strip()
    if not val:
        print(json.dumps({"ok": False, "why": "剪贴板空（双击没取到词？）",
                          "回执": {k: r.get(k) for k in ("ok", "reason", "error")}},
                         ensure_ascii=False))
        return 2
    shape = {"len": len(val), "has_space": any(c.isspace() for c in val),
             "classes": "".join(sorted({("d" if c.isdigit() else "a" if c.isalpha() else "o")
                                        for c in val}))}
    if shape["has_space"] or not (8 <= shape["len"] <= 256):
        print(json.dumps({"ok": False, "why": "取到的不是单行长串，不封", "shape": shape},
                         ensure_ascii=False))
        return 3

    from gbt_allinone.deepseek_key import store_key
    report = store_key(val, VAULT_PROFILE)
    reg = {}
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                            winreg.KEY_SET_VALUE | winreg.KEY_READ) as k:
            winreg.SetValueEx(k, ENV_NAME, 0, winreg.REG_SZ, val)
        reg = {"写注册表": "ok", "键": "HKCU\\Environment\\" + ENV_NAME}
    except Exception as exc:                              # noqa: BLE001
        reg = {"写注册表": "failed", "why": "%s: %s" % (type(exc).__name__, str(exc)[:120])}

    print(json.dumps({
        "ok": bool(report.get("ok")),
        "封存": {"profile": VAULT_PROFILE, "dpapi": report.get("ok"),
                 "path": report.get("path"), "bytes": report.get("bytes")},
        "注册表": reg,
        "掩码": (val[:4] + "*" * 8),
        "sha256_8": hashlib.sha256(val.encode()).hexdigest()[:8],
        "shape": shape,
        "_纪律": "值只在进程内出现过；stdout 只有掩码与 sha256 前 8 位",
    }, ensure_ascii=False))
    return 0 if report.get("ok") else 4


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    try:
        if cmd == "shot":
            return shot(argv[2] if len(argv) > 2 else "shot")
        if cmd == "go":
            return go(argv[2])
        if cmd == "click":
            return act("click", [int(argv[2]), int(argv[3])], "click %s,%s" % (argv[2], argv[3]))
        if cmd == "clicktext":
            return act("click_text", [argv[2]], "click_text %r" % argv[2])
        if cmd == "type":
            return act("type", [argv[2]], "type")
        if cmd == "key":
            keys = argv[2].split("+")
            return act("hotkey", keys, "hotkey " + "+".join(keys))
        if cmd == "seal-at":
            return seal_at(int(argv[2]), int(argv[3]))
    except IndexError:
        print("参数不够：", cmd)
        return 1
    print("未知子命令：", cmd)
    return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main(sys.argv))
