# -*- coding: utf-8 -*-
"""Install an opt-in Codex profile for GBT's local GGUF weights.

The profile is separate from config.toml and leaves Codex's normal provider untouched.
Use: py -3 tools/codex-scripts/codex-local-profile.py install
     codex --profile gbt-local
"""
from __future__ import annotations

import argparse
import os
import sys
import tomllib
from pathlib import Path

PROFILE = "gbt-local"
MARKER = "# Managed by tools/codex-scripts/codex-local-profile.py"
PROFILE_TEXT = """# Managed by tools/codex-scripts/codex-local-profile.py
# Opt-in profile. Does not change the default Codex provider.
model = "gbt-v8"
model_provider = "gbt_local"
model_context_window = 8192
model_max_output_tokens = 128

[model_providers.gbt_local]
name = "GBT小土豆V8 本机权重"
base_url = "http://127.0.0.1:8791/v1"
wire_api = "responses"
requires_openai_auth = false
supports_websockets = false
request_max_retries = 0
stream_idle_timeout_ms = 240000
"""


def _profile_path() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    return codex_home / (PROFILE + ".config.toml")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp-%d" % os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        # Verify the serialized profile before replacing the visible file.
        parsed = tomllib.loads(tmp.read_text(encoding="utf-8"))
        if parsed.get("model_provider") != "gbt_local" or \
                parsed.get("model_providers", {}).get("gbt_local", {}).get("wire_api") != "responses":
            raise ValueError("生成的 Codex profile 未通过结构校验")
        os.replace(tmp, path)
        if path.read_text(encoding="utf-8") != content:
            raise OSError("profile 写后回读校验不一致")
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def install() -> int:
    path = _profile_path()
    if path.exists() and MARKER not in path.read_text(encoding="utf-8", errors="replace"):
        print("拒绝覆盖已有的非 GBT profile：%s" % path)
        return 2
    _atomic_write(path, PROFILE_TEXT)
    print("已安装独立 profile：%s" % path)
    print("启用命令：codex --profile %s" % PROFILE)
    print("端点：仅本机 http://127.0.0.1:8791/v1/responses；请求固定走 selfhost，不会回落云端。")
    print("注意：profile 按当前 CPU 车道的 n_ctx=8192 配置；长 Codex 提示可能被本机 fit gate 拒绝。")
    return 0


def remove() -> int:
    path = _profile_path()
    if not path.exists():
        print("profile 不存在：%s" % path)
        return 0
    if MARKER not in path.read_text(encoding="utf-8", errors="replace"):
        print("拒绝删除非 GBT profile：%s" % path)
        return 2
    path.unlink()
    print("已移除 GBT profile：%s" % path)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="管理 GBT 本地权重的可选 Codex profile")
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("install", help="安装独立 profile，不改默认 config.toml")
    sub.add_parser("remove", help="移除本脚本创建的 profile")
    args = ap.parse_args(argv)
    return install() if args.command == "install" else remove()


if __name__ == "__main__":
    raise SystemExit(main())
