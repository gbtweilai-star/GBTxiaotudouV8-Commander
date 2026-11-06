# -*- coding: utf-8 -*-
"""codex-deepseek-apply —— 按 DeepSeek 官方《接入 Codex》改 ~/.codex/config.toml。

官方依据：https://api-docs.deepseek.com/zh-cn/quick_start/agent_integrations/codex

## 与官方脚本的差别（都写理由，不是自己发挥）
  ① **不加 `preferred_auth_method`**：`codex exec --strict-config` 在本机
     codex-cli 0.166.0-alpha.5.1 上直接报
         unknown configuration field `preferred_auth_method`
     加了等于让整份配置加载失败。
  ② **默认不加 `forced_login_method = "api"`**：本版本执行它时会**登出 ChatGPT 账号**
     （实测日志：`API key login is required, but ChatGPT is currently being used.
     Logging out.`，且 ~/.codex/auth.json 被直接删除）。要加请显式 --force-api-login，
     并且先自己跑过一次 `codex login` 确保能登回来。
  ③ **加 `requires_openai_auth = false`**：本仓早前实测过，它能让 Codex
     不往请求上附加 OpenAI 的 auth 头（日志里 `auth.header_attached=false`），
     否则 DeepSeek 请求可能带上 ChatGPT 的 token。

## 安全
  · `--dry-run` 只打印将要写入的内容，不动任何文件；
  · 真写之前把 config.toml 备份到 ~/.codex/backup-deepseek/；
  · `--restore` 从最近一次备份还原；
  · key 默认从本仓 DPAPI 保险箱取（gbt_allinone.deepseek_key），不进 argv、不回显。
"""
from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:                                        # noqa: BLE001
    pass

CODEX_HOME = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
CFG = CODEX_HOME / "config.toml"
BACKUP_DIR = CODEX_HOME / "backup-deepseek"
MODELS = CODEX_HOME / "models.json"

TOP_KEYS = [
    ("model", '"deepseek-flash"'),
    ("model_provider", '"deepseek"'),
    ("model_reasoning_effort", '"high"'),
    ("web_search", '"disabled"'),
    ("show_raw_agent_reasoning", "true"),
    ("model_catalog_json", '"%s"' % str(MODELS).replace("\\", "/")),
]


def _mask(k: str) -> str:
    return (k[:5] + "****") if len(k) >= 5 else "****"


def _take_key() -> tuple[str, str]:
    try:
        from gbt_allinone.deepseek_key import load_key
    except Exception as exc:                             # noqa: BLE001
        return "", "保险箱模块导入失败：%s" % str(exc)[:100]
    return load_key("deepseek")


def _provider_block(key: str, force_api_login: bool) -> list[str]:
    out = [
        "",
        "[model_providers.deepseek]",
        'name = "deepseek"',
        'base_url = "https://api.deepseek.com/"',
        'wire_api = "responses"',
        "requires_openai_auth = false",
        'experimental_bearer_token = "%s"' % key,
    ]
    if force_api_login:
        out += ["", "# 注意：本行会让 Codex 登出 ChatGPT 账号（见脚本头注 ②）",
                'forced_login_method = "api"']
    return out


def build(text: str, key: str, force_api_login: bool) -> str:
    lines = text.splitlines()

    # ── 1. 顶层键：必须落在第一个 [表] 之前 ─────────────────────────────
    first_table = None
    for i, ln in enumerate(lines):
        if ln.strip().startswith("["):
            first_table = i
            break
    if first_table is None:
        first_table = len(lines)

    keys = {k for k, _ in TOP_KEYS}
    preamble = [ln for i, ln in enumerate(lines[:first_table])
                if not (re.match(r"^\s*([A-Za-z0-9_\-]+)\s*=", ln)
                        and re.match(r"^\s*([A-Za-z0-9_\-]+)\s*=", ln).group(1) in keys)]
    insert = ["%s = %s" % (k, v) for k, v in TOP_KEYS]
    new_lines = preamble + insert + lines[first_table:]

    # ── 2. 去掉已存在的 [model_providers.deepseek] 段 ─────────────────
    out, skipping = [], False
    for ln in new_lines:
        s = ln.strip()
        if s.startswith("["):
            skipping = (s == "[model_providers.deepseek]")
        if not skipping:
            out.append(ln)

    # ── 3. [desktop] 段内补 enabled-reasoning-efforts（不新建重复段）──
    idx = None
    for i, ln in enumerate(out):
        if ln.strip() == "[desktop]":
            idx = i
            break
    if idx is not None:
        end = len(out)
        for j in range(idx + 1, len(out)):
            if out[j].strip().startswith("["):
                end = j
                break
        seg = [ln for ln in out[idx + 1:end]
               if not ln.strip().startswith("enabled-reasoning-efforts")]
        out = out[:idx + 1] + [
            'enabled-reasoning-efforts = ["low", "medium", "high", "xhigh", "ultra", "max"]'
        ] + seg + out[end:]
    else:
        out += ["", "[desktop]",
                'enabled-reasoning-efforts = ["low", "medium", "high", "xhigh", "ultra", "max"]']

    # ── 4. 追加 provider 段 ────────────────────────────────────────────
    out += _provider_block(key, force_api_login)
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="按官方文档把 DeepSeek 写进 Codex 主配置")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    ap.add_argument("--restore", action="store_true", help="从最近一次备份还原 config.toml")
    ap.add_argument("--force-api-login", action="store_true",
                    help="额外写 forced_login_method=\"api\"（会登出 ChatGPT，务必先登录过一次）")
    ap.add_argument("--key", default="", help="临时给一个 key（不推荐，会进命令历史）")
    args = ap.parse_args(argv)

    if not MODELS.is_file():
        print("[X] 缺 %s —— 先跑 .scratch/extract-models-json.py 或官方脚本" % MODELS)
        return 2

    if args.restore:
        if not BACKUP_DIR.is_dir():
            print("[X] 没有备份目录：%s" % BACKUP_DIR)
            return 2
        baks = sorted(BACKUP_DIR.glob("config.toml.*"))
        if not baks:
            print("[X] 备份目录里没有 config.toml.*")
            return 2
        src = baks[-1]
        shutil.copy2(src, CFG)
        print("已还原:", src, "->", CFG)
        return 0

    key, source = (args.key, "argv") if args.key else _take_key()
    if not key:
        print("[缺 key] source =", source)
        print('先把 key 存进 DPAPI 保险箱（明文不进 argv/日志）：')
        print('  "sk-xxx" | .\\pyembed\\python.exe -m gbt_allinone.deepseek_key set')
        return 2
    print("key:", _mask(key), "（来源：%s）" % source)

    text = io.open(CFG, encoding="utf-8", newline="").read() if CFG.is_file() else ""
    new = build(text, key, args.force_api_login)

    # 语法自检（tomllib 是 Python 3.11+ 标准库）
    try:
        import tomllib
        tomllib.loads(new)
        print("TOML 语法: OK")
    except Exception as exc:                             # noqa: BLE001
        print("[X] 生成结果不是合法 TOML：%s" % exc)
        return 3

    if args.dry_run:
        print("\n===== DRY RUN：以下内容**不会**写入 =====\n")
        for ln in new.splitlines():
            if "experimental_bearer_token" in ln:
                ln = re.sub(r'= ".*"', '= "%s"' % _mask(key), ln)
            print(ln)
        return 0

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if CFG.is_file():
        bak = BACKUP_DIR / ("config.toml." + time.strftime("%Y%m%d-%H%M%S"))
        shutil.copy2(CFG, bak)
        print("已备份:", bak)

    tmp = CFG.with_name("%s.tmp-%d" % (CFG.name, os.getpid()))
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(new)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, CFG)
    print("已写入:", CFG)
    print("还原: python tools/codex-scripts/codex-deepseek-apply.py --restore")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
