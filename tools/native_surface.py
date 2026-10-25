# -*- coding: utf-8 -*-
"""原生能力面 · 台账与探针（21 根桥 × 124 条命令）

主人的话：「把他的所有原生能力发挥到极致，不能被任何东西束缚」

本件做三件事，都是**现跑读数**、不抄文档：
  ① inventory : 把 21 根桥的命令面全抓出来（帮助走 stderr，**两个流都读**）
  ② probe     : 对**只读类**命令逐条真跑一次，记 ok/耗时/样例/失败原因
  ③ build     : 落 state/native_surface.json —— 这是"她的原生手"的活账

纪律：
  · 只探**只读**命令；写类（create/delete/set/schedule/play/export…）一律不动，如实标 skip
  · 需要硬件/权限的不猜，跑一次拿真结果（含 permission denied）
  · 取不到就写"未读到"，不编样例

用法：
  python3 tools/native_surface.py inventory
  python3 tools/native_surface.py probe
  python3 tools/native_surface.py build
  python3 tools/native_surface.py show
"""
from __future__ import annotations
import json, subprocess, sys, time, glob
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "state" / "native_surface.json"
BIN = "/usr/local/bin"

# 写类命令：只命中这些前缀就跳过（不越门）
WRITEY = ("create", "update", "delete", "set", "schedule", "cancel", "play", "pause",
          "resume", "seek", "stop", "export", "import", "add", "favorite", "trigger",
          "connect", "disconnect", "write", "notify", "complete", "remind", "scan")

# 逐条探测计划：只读、无必填参数、不会弹权限弹窗到不可收拾
PLAN = [
    ("apple-device", "info"),
    ("apple-weather", []),                 # 无参即 current
    ("apple-location", []),                # 无参即 current
    ("apple-clipboard", []),               # 无参即 get
    ("apple-media", []),                   # 无参即 now-playing
    ("apple-calendar", "calendars"),
    ("apple-calendar", "list"),
    ("apple-reminders", "lists"),
    ("apple-reminders", "list"),
    ("apple-photos", "stats"),
    ("apple-alarm", "list"),
    ("apple-notification", "pending"),
    ("apple-notification", "settings"),
    ("apple-homekit", "list"),
    ("apple-bluetooth", "status"),
    ("apple-speak", "voices"),
    ("apple-speech", "status"),
    ("apple-speech", "languages"),
    ("apple-player", "list"),
    ("apple-nlp", "language", ["--text", "这是一段中文测试文本"]),
    ("apple-nlp", "sentiment", ["--text", "这个模型跑得很快，我很满意"]),
    ("apple-nlp", "tokenize", ["--text", "GBT小土豆V8 是一个指挥官模型"]),
    ("apple-nlp", "ner", ["--text", "自由的风在北京开发了GBT小土豆V8"]),
    ("apple-nlp", "pos", ["--text", "我今天很开心"]),
    ("apple-maps", None),                  # 需要参数，只记"需参数"
    ("apple-vision", None),                # 需要图片
    ("apple-healthkit", "steps"),
    ("apple-nfc", None),                   # 需要硬件
    ("apple-open", None),                  # 需要 URL
]


def _run(argv, timeout=14):
    t0 = time.time()
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "status": "timeout", "ms": round((time.time() - t0) * 1000)}
    except Exception as e:
        return {"ok": False, "status": "exception", "why": type(e).__name__,
                "ms": round((time.time() - t0) * 1000)}
    raw = (p.stdout or "") + (p.stderr or "")
    ms = round((time.time() - t0) * 1000)
    try:
        j = json.loads((p.stdout or "").strip() or "{}")
    except Exception:
        j = {}
    return {"ok": bool(j.get("ok")), "ms": ms,
            "action": j.get("action"),
            "err": (j.get("error") or {}).get("message") if isinstance(j.get("error"), dict) else None,
            "sample": json.dumps(j.get("data"), ensure_ascii=False)[:150] if j.get("data") else None,
            "raw_head": None if j else raw.strip()[:120]}


def inventory() -> list:
    rows = []
    for t in sorted(glob.glob(BIN + "/apple-*")):
        name = t.split("/")[-1]
        try:
            p = subprocess.run([t], capture_output=True, text=True, timeout=10)
            out = (p.stdout or "") + (p.stderr or "")
        except Exception:
            out = ""
        cmds = []
        if "COMMANDS:" in out:
            for ln in out.split("COMMANDS:", 1)[1].splitlines():
                s = ln.strip()
                if not s:
                    if cmds:
                        break
                    continue
                if s.startswith(("COMMON OPTIONS", "USAGE", "OPTIONS")):
                    break
                cmds.append(s.split()[0])
        rows.append({"tool": name, "cmds": cmds, "n": len(cmds),
                     "mode": "help" if cmds else "default-action"})
    return rows


def probe() -> list:
    out = []
    for item in PLAN:
        tool, cmd = item[0], item[1]
        extra = list(item[2]) if len(item) > 2 else []
        argv = [BIN + "/" + tool] + ([cmd] if cmd else []) + extra
        if cmd is None:
            out.append({"tool": tool, "cmd": None, "status": "need-args",
                        "why": "该命令需要必填参数或硬件，未盲跑"})
            continue
        r = _run(argv)
        r.update({"tool": tool, "cmd": cmd})
        if r.get("ok") is False and not r.get("err") and r.get("status") is None:
            r["status"] = "fail"
        elif r.get("ok"):
            r["status"] = "ok"
        else:
            r.setdefault("status", "fail")
        out.append(r)
    return out


def build() -> dict:
    inv = inventory()
    pr = probe()
    ok = sum(1 for r in pr if r.get("status") == "ok")
    data = {
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "tools": len(inv), "commands": sum(x["n"] for x in inv),
        "probed": len(pr), "ok": ok, "fail": len(pr) - ok,
        "inventory": inv, "probes": pr,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def main() -> int:
    a = sys.argv[1:] or ["show"]
    c = a[0]
    if c == "inventory":
        for r in inventory():
            print("  %-22s %2d  %s" % (r["tool"], r["n"], ", ".join(r["cmds"][:9])))
    elif c == "probe":
        for r in probe():
            mark = "✅" if r.get("status") == "ok" else ("—" if r["status"] == "need-args" else "❌")
            print("  %s %-22s %-12s %6s  %s" % (mark, r["tool"], r["cmd"] or "-",
                  r.get("ms", ""), (r.get("sample") or r.get("why") or r.get("err") or "")[:60]))
    elif c == "build":
        d = build()
        print("  %d 工具 · %d 命令 · 探 %d 条 · ok %d / 非ok %d"
              % (d["tools"], d["commands"], d["probed"], d["ok"], d["fail"]))
        print("  落盘: %s" % OUT)
    else:
        if not OUT.is_file():
            print("  还没台账：python3 tools/native_surface.py build"); return 0
        d = json.loads(OUT.read_text(encoding="utf-8"))
        print("  建于 %s · %d 工具 · %d 命令 · 探 %d · ok %d"
              % (d["built_at"], d["tools"], d["commands"], d["probed"], d["ok"]))
        for r in d["probes"]:
            if r.get("status") == "ok":
                print("    ✅ %-22s %-10s %s" % (r["tool"], r["cmd"] or "-", (r.get("sample") or "")[:70]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
