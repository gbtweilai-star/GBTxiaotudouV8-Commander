# -*- coding: utf-8 -*-
"""app-surface-scan -- 现读本机软件面，产出通道台账（cli / gui），供万能插驱动。

口径（与 gbt-cli-ify 三档一致）：**有 CLI 走 CLI > 有 API 包 CLI > 只有 GUI 才走触手**。
只现读，不装、不改系统。
"""
from __future__ import annotations
import json, os, shutil, subprocess, sys, time
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "state" / "app_surfaces.json"
CLI_CANDIDATES = [
    "git", "node", "npm", "pnpm", "yarn", "python", "py", "pip", "uv", "go", "rustc", "cargo",
    "java", "dotnet", "gcc", "g++", "cmake", "make", "docker", "kubectl", "gh", "wrangler",
    "ffmpeg", "ffprobe", "magick", "curl", "wget", "ssh", "scp", "rsync", "7z", "tar",
    "code", "codex", "claude", "copilot", "rg", "fd", "jq", "yq", "sqlite3", "node",
    "ollama", "comfy", "nvidia-smi", "where", "tasklist", "wmic", "powershell", "pwsh",
    "wsl", "adb", "gradle", "mvn", "terraform", "aws", "gcloud", "az", "vercel", "netlify",
    "blender", "gimp", "inkscape", "libreoffice", "soffice", "pandoc", "tesseract",
]
GUI_DIRS = [
    r"C:\Program Files", r"C:\Program Files (x86)",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs"),
]


def which(name):
    p = shutil.which(name)
    if p:
        return p
    try:
        r = subprocess.run(["where.exe", name], capture_output=True, text=True, timeout=8)
        first = (r.stdout or "").strip().splitlines()
        return first[0] if first else ""
    except Exception:
        return ""


def scan_cli():
    out = []
    for n in CLI_CANDIDATES:
        p = which(n)
        if p:
            out.append({"name": n, "path": p, "channel": "cli"})
    return out


def scan_gui():
    apps = []
    for d in GUI_DIRS:
        base = Path(d)
        if not base.is_dir():
            continue
        try:
            for child in sorted(base.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    exes = list(child.glob("*.exe"))[:2]
                    if exes:
                        apps.append({"name": child.name, "path": str(exes[0]), "channel": "gui"})
        except Exception:
            continue
    return apps[:80]


def main():
    t0 = time.time()
    cli = scan_cli()
    gui = scan_gui()
    doc = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "host": os.environ.get("COMPUTERNAME", ""),
           "cli": cli, "gui": gui, "counts": {"cli": len(cli), "gui": len(gui)},
           "rule": "有 CLI 走 CLI > 有 API 包 CLI > 只有 GUI 才走触手（gbt-cli-ify）"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("软件面台账：" + str(OUT))
    print("  CLI 通道 %d 条 · GUI 目录 %d 个 · 用时 %.1fs" % (len(cli), len(gui), time.time() - t0))
    print("  样例 CLI：" + ", ".join(x["name"] for x in cli[:14]))
    print("  样例 GUI：" + ", ".join(x["name"] for x in gui[:8]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
