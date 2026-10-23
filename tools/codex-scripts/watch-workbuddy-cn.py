#!/usr/bin/env python3
"""watch-workbuddy-cn.py —— 等 WorkBuddy **中国站**桌面凭据落盘。

背景（2026-10-17 现读，不是猜）：
  dsh-workbuddy-connect 有两个 provider，各自认**不同的**桌面凭据文件：
    · workbuddy    (中国站) → %LOCALAPPDATA%\\CodeBuddyExtension\\Data\\Public\\auth\\workbuddy-desktop.info
    · workbuddy-ai (国际站) → 同目录 workbuddy-desktop-ai.info
  现读：AI 那份在（domain=www.workbuddy.ai），CN 那份**不在** ⇒ CN 恒 signed-out。
  插件 CLI 只有 doctor/status/logout，**没有 login** —— 它只复用桌面 App 已登好的态。
  所以「中国站」的唯一入场券 = 在那个 App 里用腾讯账号登一次，让 CN 那份文件出现。

本器只做一件事：盯着 CN 凭据文件出现（appear），并做**不碰密钥**的旁证：
  · 文件大小 / 修改时间
  · JSON 顶层字段名（不打印任何值）
  · 只把 `auth.domain` 这一个非密字段打出来，用来确认落的是中国站还是国际站
  🔴 绝不打印 accessToken / refreshToken / 任何凭据值。

退出码：0 = 文件已出现；1 = 等到超时仍未出现（如实报，不编）。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


AUTH_DIR = Path.home() / "AppData" / "Local" / "CodeBuddyExtension" / "Data" / "Public" / "auth"
CN_FILE = "workbuddy-desktop.info"
AI_FILE = "workbuddy-desktop-ai.info"


def describe(path: Path) -> dict:
    """Non-secret facts about one credential file."""
    st = path.stat()
    info: dict = {
        "path": str(path),
        "bytes": st.st_size,
        "modified": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime)),
    }
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:  # noqa: BLE001 - report, never crash on shape
        info["parse"] = f"failed: {type(exc).__name__}"
        return info
    if isinstance(data, dict):
        info["top_keys"] = sorted(data.keys())
        auth = data.get("auth")
        if isinstance(auth, dict):
            # Only the non-secret service domain: it decides CN vs international.
            info["auth_domain"] = auth.get("domain")
            info["auth_token_type"] = auth.get("tokenType")
    return info


def probe(auth_dir: Path) -> dict:
    cn = auth_dir / CN_FILE
    ai = auth_dir / AI_FILE
    return {
        "cn_present": cn.is_file(),
        "ai_present": ai.is_file(),
        "cn": describe(cn) if cn.is_file() else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="wait for the WorkBuddy China desktop credential")
    ap.add_argument("--timeout", type=int, default=900, help="seconds to wait (default 900)")
    ap.add_argument("--interval", type=float, default=3.0, help="poll seconds (default 3)")
    ap.add_argument("--json", action="store_true", help="emit one JSON line per state change")
    args = ap.parse_args()

    started = time.time()
    last = None
    print(f"[watch] looking for {AUTH_DIR / CN_FILE}", flush=True)
    while True:
        state = probe(AUTH_DIR)
        if args.json:
            print(json.dumps({"at": time.strftime("%H:%M:%S"), **state}, ensure_ascii=False), flush=True)
        elif state["cn_present"]:
            if last is not True:
                print(f"[watch] CN credential appeared: {json.dumps(state['cn'], ensure_ascii=False)}", flush=True)
        elif last is None:
            print("[watch] CN credential not present yet (international one: "
                  f"{'present' if state['ai_present'] else 'absent'})", flush=True)
        last = state["cn_present"]

        if state["cn_present"]:
            print("[watch] DONE — now run: "
                  "dsh plugin --profile web exec dsh-workbuddy-connect status --provider workbuddy --json",
                  flush=True)
            return 0
        if time.time() - started > args.timeout:
            print(f"[watch] TIMEOUT after {args.timeout}s — CN credential still absent", flush=True)
            return 1
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
