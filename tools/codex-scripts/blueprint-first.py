# -*- coding: utf-8 -*-
"""blueprint-first -- 接令先出立体蓝图，主人确认后才推进（主人令 2026-10-16）。

流程：① cap brain_route（大脑执行层分析推理）
      ② cap showcase_ops（立体蓝图：会动的实物 + 零件 + 画框四件 + 读数同源）
      ③ cap forge_mastery（节点触手图 + 六轴判据 + 无限递归环）
      ④ 落 state/blueprints/<id>.json + <id>.html（活页）并打印「等主人确认」
      ⑤ **未确认不许推进**：check 会拒绝；确认由主人做（AI 不许自我批准）
用法：
  py -3.14 tools/codex-scripts/blueprint-first.py new --task "..." [--slug x]
  py -3.14 tools/codex-scripts/blueprint-first.py show <id>
  py -3.14 tools/codex-scripts/blueprint-first.py check <id>          # \u672a\u786e\u8ba4\u975e\u96f6\u9000\u51fa
  py -3.14 tools/codex-scripts/blueprint-first.py approve <id> --by owner --yes   # \u4e3b\u4eba\u5728\u7ec8\u7aef\u786e\u8ba4
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys, time
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
BDIR = ROOT / "state" / "blueprints"
SIG = "开发者：自由的风 · 守护者：公主土豆 · 本署名不可删除、不可篡改归属"


MEM_FLOOR_GB = 0.5


def avail_gb():
    try:
        import ctypes

        class M(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = M()
        m.dwLength = ctypes.sizeof(M)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return round(m.ullAvailPhys / 1024 ** 3, 2)
    except Exception:
        return -1.0

def cap(name, payload, timeout=420):
    p = subprocess.run([PY, "-X", "utf8", "tools/codex-scripts/five-dim.py", "cap", name, json.dumps(payload, ensure_ascii=False), "--full"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT), timeout=timeout)
    o = (p.stdout or "") + (p.stderr or "")
    ok = "\"status\": \"ok\"" in o or "\"ok\": true" in o
    return ok, o


def new(task, slug):
    mem = avail_gb()
    minimal = (mem >= 0 and mem < MEM_FLOOR_GB)
    BDIR.mkdir(parents=True, exist_ok=True)
    bid = time.strftime("%Y%m%d-%H%M%S") + "-" + (slug or "task")
    ok1, brain = cap("brain_route", {"intent": task})
    ok2, sc = cap("showcase_ops", {"op": "concept", "idea": task})
    ok3, fm = cap("forge_mastery", {"op": "plan", "goal": task})
    doc = {"id": bid, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "task": task, "sig": SIG,
           "seg1_brain_ok": ok1, "seg2_showcase_ok": ok2, "seg3_forge_ok": ok3,
           "brain": brain[-1500:], "showcase": sc[-1500:], "forge": fm[-1500:], "approved": False}
    (BDIR / (bid + ".json")).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    html = ("<!doctype html><meta charset=\"utf-8\"><title>立体蓝图 " + bid + "</title>"
            "<style>body{background:#0b0d10;color:#e8ecf1;font:15px/1.6 system-ui;padding:28px;max-width:900px;margin:auto}"
            "h1{font-size:22px}code{background:#171b21;padding:2px 6px;border-radius:4px}"
            ".card{background:#12161c;border:1px solid #232a33;border-radius:10px;padding:16px;margin:14px 0}"
            ".k{color:#8ab4ff}.w{color:#f5c26b}.sig{color:#7d8794;font-size:12px;margin-top:22px}</style>"
            "<h1>立体蓝图 · " + bid + "</h1>"
            "<div class=card><b class=k>① 标题</b><br>" + task + "</div>"
            "<div class=card><b class=k>② 怎么看</b><br>先读「会动的实物」对应哪一步，再看「节点触手图」的边（数据契约），最后看六轴判据。</div>"
            "<div class=card><b class=w>③ 实时读数</b><br>大脑执行层 ok=" + str(ok1) + " · showcase_ops ok=" + str(ok2) + " · forge_mastery ok=" + str(ok3) + "</div>"
            "<div class=card><b class=k>④ 六轴判据</b><br>构图与镜头 · 光比与影调 · 材质与细节 · 物理与逻辑一致 · 风格锁定 · 交付规格</div>"
            "<div class=card><b class=w>等主人确认</b><br>python -m gbt_allinone <i>确认后</i>：py -3.14 tools/codex-scripts/blueprint-first.py approve " + bid + " --by owner --yes</div>"
            "<div class=sig>" + SIG + "</div>")
    (BDIR / (bid + ".html")).write_text(html, encoding="utf-8")
    print("立体蓝图已出：" + bid)
    print("  大脑执行层=" + str(ok1) + " · 立体蓝图=\"会动的实物+四件齐\" · 节点触手图=\u516d轴判据+无限递归")
    print("  活页：" + str((BDIR / (bid + ".html")).relative_to(ROOT)))
    print("  **等主人确认后才动手**：py -3.14 tools/codex-scripts/blueprint-first.py approve " + bid + " --by owner --yes")
    return 0


def check(bid):
    f = BDIR / (bid + ".json")
    if not f.is_file():
        print("未读到蓝图 " + bid + " ⇒ 拒绝推进")
        return 2
    d = json.loads(f.read_text(encoding="utf-8"))
    ap = BDIR / (bid + ".approved")
    if not ap.is_file():
        print("蓝图 " + bid + " **尚未确认** ⇒ 拒绝推进（主人确认：approve " + bid + " --by owner --yes）")
        return 1
    print("蓝图 " + bid + " 已确认，可推进（确认人：" + ap.read_text(encoding="utf-8").strip()[:40] + "）")
    return 0


def approve(bid, by, yes):
    if by != "owner" or not yes:
        print("拒绝：确认只能由主人做（需 --by owner --yes）。AI 不许自我批准。")
        return 1
    f = BDIR / (bid + ".json")
    if not f.is_file():
        print("未读到蓝图 " + bid)
        return 2
    (BDIR / (bid + ".approved")).write_text("owner @ " + time.strftime("%Y-%m-%dT%H:%M:%S"), encoding="utf-8")
    print("已确认 " + bid + "（主人）⇒ 可推进")
    return 0


def main():
    ap = argparse.ArgumentParser(description="接令先出立体蓝图，主人确认后才推进")
    ap.add_argument("cmd", choices=("new", "show", "check", "approve"))
    ap.add_argument("arg", nargs="?", default="")
    ap.add_argument("--task", default="")
    ap.add_argument("--slug", default="task")
    ap.add_argument("--by", default="")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    if a.cmd == "new":
        return new(a.task or a.arg, a.slug)
    if a.cmd == "check":
        return check(a.arg)
    if a.cmd == "approve":
        return approve(a.arg, a.by, a.yes)
    print((BDIR / (a.arg + ".json")).read_text(encoding="utf-8")[:900] if (BDIR / (a.arg + ".json")).is_file() else "未读到")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
