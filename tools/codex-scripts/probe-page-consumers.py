# -*- coding: utf-8 -*-
# gbt-instrument: 本件是**量具** —— 它把候选页的路径当数据写在自己的源码里，
#   所以那些路径不算"有人引用"。不加这个标记，本探针会把自己的结论堵死
#   （实测：`deploy/gbt-prototype.html` 唯一"引用者"就是这个文件）。
"""一次性探针：把候选旧页的**三种消费者**逐个查出来（为建正式审计器取数）。

「谁在用这个文件」有三种形态，缺一种就会误删（2026-09-23 真出过事）：
  ① 进程正拿着 —— `clean_residue.live_paths()`
  ② **清单/注册表里点名** —— 面板清单 host.js / 窗口注册表 windows.json / state/*.json
  ③ 代码里引用 —— 全仓文本面 + 页内 href/src
用法: py -3.14 tools/codex-scripts/probe-page-consumers.py
"""
import json
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]

CANDIDATES = [
    "deploy/index.html", "deploy/canvas.html", "deploy/gbt-prototype.html",
    "agent-gvmz-gbtv8/.openclaw/tmp/ai_control_fix1.html",
    "agent-gvmz-gbtv8/.openclaw/tmp/ai_control_fix2.html",
    "agent-gvmz-gbtv8/.openclaw/tmp/platform_v92_fix.html",
    "agent-gvmz-gbtv8/.openclaw/tmp/temp_mail_fixed.html",
    "agent-gvmz-gbtv8/.openclaw/tmp/v11_fixed.html",
    "agent-gvmz-gbtv8/.openclaw/tmp/v92_wl2.html",
    ".scratch/_overlay_now.html",
    ".scratch/_hv/demo.html",
    ".scratch/_hv/trail-test.html",
    "infinite-canvas-output/index.html",
]
CODE_EXT = (".js", ".mjs", ".cjs", ".json", ".py", ".html", ".css", ".md")


def panels_and_windows():
    """② 声明式消费者：面板清单 + 窗口注册表 —— 点名过的文件一律不许动。"""
    declared = {}
    host = ROOT / "plugins" / "gbt-master" / "host.js"
    if host.is_file():
        t = host.read_text(encoding="utf-8", errors="replace")
        for pid, name, f in re.findall(
                r"id:\s*'([^']+)'\s*,\s*name:\s*'([^']+)'\s*,\s*file:\s*'([^']+)'", t):
            declared.setdefault(f.replace("\\", "/").lstrip("./"), []).append("面板 %s(%s)" % (name, pid))
    wj = ROOT / "holo_pet_w3" / "shell" / "windows.json"
    if wj.is_file():
        try:
            for w in json.loads(wj.read_text(encoding="utf-8")).get("windows", []):
                f = (w.get("file") or "").replace("../", "holo_pet_w3/").replace("\\", "/")
                if f:
                    declared.setdefault(f.lstrip("./"), []).append("窗口 %s(%s)" % (w.get("title"), w.get("id")))
        except Exception as e:                                       # noqa: BLE001
            declared["__windows_error__"] = [str(e)[:80]]
    for j in sorted((ROOT / "state").glob("*.json")) if (ROOT / "state").is_dir() else []:
        try:
            t = j.read_text(encoding="utf-8", errors="replace")
        except Exception:                                            # noqa: BLE001
            continue
        for m in re.finditer(r"[A-Za-z0-9_\-./\\\u4e00-\u9fff]+\.(?:html|htm)", t):
            declared.setdefault(m.group(0).replace("\\", "/").lstrip("./"),
                                []).append("state/%s" % j.name)
    return declared


def main():
    declared = panels_and_windows()
    print("=" * 100)
    print("候选旧页 · 三种消费者逐个查")
    print("=" * 100)
    print("【② 声明式消费者】面板清单 + 窗口注册表 点名过的页面：")
    for k, v in sorted(declared.items()):
        if k.startswith("__"):
            print("   ⚠️ %s → %s" % (k, v))
            continue
        print("   %-46s ← %s" % (k, ", ".join(sorted(set(v))[:3])))
    print()

    for cand in CANDIDATES:
        p = ROOT / cand
        if not p.is_file():
            print("— %-56s 缺失" % cand)
            continue
        name = p.name
        # ③ 代码/文本面引用
        r = subprocess.run(["git", "-C", str(ROOT), "grep", "-l", "--untracked", "-I", "-F", cand],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        bypath = [x for x in (r.stdout or "").splitlines() if x.strip() and cand not in x]
        r2 = subprocess.run(["git", "-C", str(ROOT), "grep", "-l", "--untracked", "-I", "-F", name],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
        byname = [x for x in (r2.stdout or "").splitlines()
                  if x.strip() and x != cand and x.endswith(CODE_EXT)][:6]
        d = declared.get(cand) or declared.get(name)
        print("— %-56s %7.0f KB" % (cand, p.stat().st_size / 1024))
        print("     ② 声明：%s" % ("**%s**" % ", ".join(d) if d else "无"))
        print("     ③ 按整路径引用：%s" % (bypath[:4] or "无"))
        print("     ③ 按文件名引用（代码文件）：%s" % (byname or "无"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
