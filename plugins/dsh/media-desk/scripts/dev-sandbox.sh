#!/bin/sh
# 在隔离的 DSH_HOME 里重新安装插件并启动 Web 版，不碰 ~/.dsh。用法：scripts/dev-sandbox.sh [端口]
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SANDBOX="${DSH_SANDBOX:-$ROOT/../.dsh-sandbox}"
PORT="${1:-4311}"
mkdir -p "$SANDBOX"
SANDBOX="$(cd "$SANDBOX" && pwd)"
cd "$ROOT"
npm run --silent build
unset DSH_SESSION_ID DSH_SHELL DSH_WEB_URL DSH_PROFILE DSH_PROFILE_DIR
export DSH_HOME="$SANDBOX"
dsh plugin --profile web remove dsh-media-desk >/dev/null 2>&1 || true
dsh plugin --profile web add "file:$ROOT" >/dev/null
exec dsh --profile web --no-open --port "$PORT"
