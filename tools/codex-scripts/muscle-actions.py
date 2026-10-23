# -*- coding: utf-8 -*-
"""muscle-actions -- 第二轮动作目录（只读优先 · 逐条真跑 + 回读）

每条 = {"argv": [...], "why": "..."}；有副作用/出网/花钱的**不放进这里**（放 muscle-drill 的 ACTIONS 并标 gated）。
"""

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass

EXPAND = {
    "git": [["--version"], ["status", "--short"], ["log", "--oneline", "-3"], ["branch", "--list"],
            ["remote", "-v"], ["rev-parse", "--is-inside-work-tree"], ["config", "--list", "--local"]],
    "node": [["--version"], ["-e", "console.log(1+1)"], ["-e", "console.log(process.platform)"],
             ["-p", "process.versions.v8"]],
    "npm": [["--version"], ["ls", "--depth=0"], ["config", "get", "registry"], ["outdated", "--depth=0"]],
    "pnpm": [["--version"], ["list", "--depth=0"], ["config", "get", "registry"]],
    "python": [["--version"], ["-c", "print(1+1)"], ["-c", "import sys;print(sys.executable)"],
               ["-c", "import sys;print(sys.prefix)"]],
    "py": [["-3.14", "-c", "import sys;print(sys.version.split()[0])"], ["-3.14", "-c", "import sys;print(sys.executable)"],
           ["-3.14", "-m", "site", "--user-site"]],
    "pip": [["--version"], ["list", "--format=freeze"], ["show", "pip"], ["config", "list"],
            ["cache", "dir"]],
    "uv": [["--version"], ["pip", "list"], ["python", "find"], ["cache", "dir"]],
    "go": [["version"], ["env", "GOPATH"], ["env", "GOROOT"], ["env", "GOOS"], ["env", "GOARCH"]],
    "rustc": [["--version"], ["--print", "sysroot"]],
    "cargo": [["--version"], ["--list"], ["metadata", "--no-deps", "--format-version", "1"]],
    "dotnet": [["--version"], ["--info"], ["--list-sdks"], ["--list-runtimes"]],
    "ffmpeg": [["-version"], ["-hide_banner", "-filters"], ["-hide_banner", "-codecs"],
               ["-hide_banner", "-formats"], ["-hide_banner", "-devices"]],
    "ffprobe": [["-version"], ["-hide_banner", "-show_formats"]],
    "gh": [["--version"], ["auth", "status"], ["config", "get", "editor"], ["repo", "list", "--limit", "3"]],
    "wrangler": [["--version"], ["whoami"], ["deployments", "list"]],
    "docker": [["--version"], ["ps"], ["images"], ["info"], ["context", "ls"]],
    "rg": [["--version"], ["--files"], ["--stats", "--files"], ["--type-list"]],
    "jq": [["--version"], ["-n", "1+1"], ["-n", "[1,2]|add"], ["--help"]],
    "sqlite3": [["--version"], [":memory:", "select 1;"], [":memory:", ".tables"]],
    "nvidia-smi": [["--query-gpu=name,memory.total,driver_version", "--format=csv"],
                   ["--query-gpu=temperature.gpu", "--format=csv"]],
    "code": [["--version"], ["--list-extensions"]],
    "ollama": [["--version"], ["list"], ["ps"]],
    "terraform": [["--version"], ["providers", "mirror", "-help"]],
    "aws": [["--version"], ["configure", "list"]],
    "gcloud": [["--version"], ["config", "list"]],
    "az": [["--version"], ["account", "show"]],
    "vercel": [["--version"], ["whoami"]],
    "blender": [["--version"], ["--background", "--python-expr", "print('ok')"]],
    "pandoc": [["--version"], ["--list-input-formats"], ["--list-output-formats"]],
    "tesseract": [["--version"], ["--list-langs"]],
    "7z": [["i"]],
    "adb": [["version"], ["devices"]],
    "powershell": [["-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"],
                   ["-NoProfile", "-Command", "Get-Date -Format o"]],
    "pwsh": [["-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"]],
    "wsl": [["--status"], ["--list", "--verbose"]],
    "ssh": [["-V"]],
    "scp": [["-V"]],
    "tar": [["--version"]],
    "copilot": [["--version"]],
    "where": [["/?"]],
    "tasklist": [["/?"]],
}


MORE = {
    "ssh": [["-V"], ["-Q", "cipher"], ["-Q", "key"]],
    "scp": [["-V"]],
    "tar": [["--version"], ["--help"]],
    "copilot": [["--version"], ["--help"]],
    "where": [["/?"]],
    "tasklist": [["/?"]],
    "powershell": [["-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"],
                   ["-NoProfile", "-Command", "Get-Date -Format o"],
                   ["-NoProfile", "-Command", "(Get-ChildItem Env:).Count"],
                   ["-NoProfile", "-Command", "$Host.Version.ToString()"]],
    "pwsh": [["-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"],
             ["-NoProfile", "-Command", "$Host.Version.ToString()"]],
    "wsl": [["--status"], ["--list", "--verbose"], ["--list", "--online"]],
    "7z": [["i"], ["-h"]],
    "adb": [["version"], ["devices"], ["get-state"]],
    "vercel": [["--version"], ["whoami"], ["teams", "ls"]],
    "az": [["--version"], ["account", "show"], ["account", "list"]],
    "gcloud": [["--version"], ["config", "list"], ["auth", "list"]],
    "aws": [["--version"], ["configure", "list"], ["sts", "get-caller-identity"]],
    "terraform": [["--version"], ["version", "-json"], ["providers", "mirror", "-help"]],
    "ollama": [["--version"], ["list"], ["ps"]],
    "code": [["--version"], ["--list-extensions"], ["--status"]],
    "nvidia-smi": [["--query-gpu=name,memory.total,driver_version", "--format=csv"],
                   ["--query-gpu=temperature.gpu,utilization.gpu", "--format=csv"],
                   ["-L"]],
    "blender": [["--version"], ["--background", "--python-expr", "import bpy;print(bpy.app.version_string)"]],
    "docker": [["--version"], ["ps"], ["images"], ["info"], ["context", "ls"], ["volume", "ls"], ["network", "ls"]],
    "gh": [["--version"], ["auth", "status"], ["config", "get", "editor"], ["repo", "list", "--limit", "3"], ["pr", "status"]],
    "uv": [["--version"], ["pip", "list"], ["python", "find"], ["cache", "dir"], ["tool", "list"]],
    "pip": [["--version"], ["list", "--format=freeze"], ["show", "pip"], ["config", "list"], ["cache", "dir"], ["check"]],
    "rg": [["--version"], ["--files"], ["--type-list"], ["--help"]],
    "jq": [["--version"], ["-n", "1+1"], ["-n", "[1,2]|add"], ["--help"]],
    "sqlite3": [["--version"], [":memory:", "select 1;"], [":memory:", ".tables"], [":memory:", "select sqlite_version();"]],
    "pandoc": [["--version"], ["--list-input-formats"], ["--list-output-formats"], ["--list-highlight-languages"]],
    "tesseract": [["--version"], ["--list-langs"], ["--print-parameters"]],
    "wrangler": [["--version"], ["whoami"], ["deployments", "list"], ["kv:namespace", "list"]],
    "codex": [["--version"], ["--help"]],
    "claude": [["--version"], ["--help"]],
    "git": [["--version"], ["status", "--short"], ["log", "--oneline", "-3"], ["branch", "--list"],
            ["remote", "-v"], ["rev-parse", "--is-inside-work-tree"], ["config", "--list", "--local"],
            ["stash", "list"], ["tag", "--list"], ["worktree", "list"]],
}
for _k, _v in MORE.items():
    EXPAND.setdefault(_k, [])
    for _a in _v:
        if _a not in EXPAND[_k]:
            EXPAND[_k].append(_a)
