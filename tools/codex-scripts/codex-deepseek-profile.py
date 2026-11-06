# -*- coding: utf-8 -*-
"""Install an opt-in Codex profile for DeepSeek (OpenAI-compatible).

为什么用 **profile** 而不是改 `config.toml`：
  `~/.codex/config.toml` 是 Codex 桌面版**自己会重写**的主配置
  （本机实测：它里面塞满了 desktop / plugins / mcp_servers 段）。
  往里塞自定义 provider，下次应用重写配置就可能被抹掉 —— `gbt_allinone/deepseek_key.py`
  的注释里记着那次事故：「Codex 的 config.toml 里写的是 env_key = "DEEPSEEK_API_KEY"…
  现在能跑，是因为密钥还有一份明文副本…」⇒ 那份 provider 段后来确实不见了。
  而 `<CODEX_HOME>/<名>.config.toml` 是**独立的 opt-in profile**，`codex --profile <名>` 才生效，
  桌面版重写主配置时不会动它。

用法：
    ./pyembed/python.exe tools/codex-scripts/codex-deepseek-profile.py install
    ./pyembed/python.exe tools/codex-scripts/codex-deepseek-profile.py install --model deepseek-chat
    ./pyembed/python.exe tools/codex-scripts/codex-deepseek-profile.py show
    ./pyembed/python.exe tools/codex-scripts/codex-deepseek-profile.py uninstall

装好之后：
    codex --profile deepseek          # 用 DeepSeek 跑这一会话
    想让它成为**默认**：把主 config.toml 里加两行（本工具**不**替你改默认）
        model = "DeepSeek-V4.1-Flash-1017"
        model_provider = "deepseek"

⚠ 缺 key 就跑不了：`env_key = "DEEPSEEK_API_KEY"` 要求这个环境变量真实存在。
  本机实测**没有**（auth.json 里只有 OpenAI 的 OAuth token；`.deepseek_key` 与 DPAPI 箱都不在）。
  安全放法见 `gbt_allinone/deepseek_key.py`（DPAPI 箱 + inject），别把明文 key 写进 config。
"""
from __future__ import annotations

import argparse
import os
import sys
import tomllib
from pathlib import Path

# Windows 控制台默认 GBK，打印 ✅/🔴 会 UnicodeEncodeError 直接崩。
# 工具自己负责自己的输出编码 —— 不能要求调用方先 chcp 65001。
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:            # 老解释器/被重定向到不支持的对象
    pass

PROFILE = "deepseek"
MARKER = "# Managed by tools/codex-scripts/codex-deepseek-profile.py"

DEFAULTS = {
    "model": "DeepSeek-V4.1-Flash-1017",
    # ⚠ Codex 0.166 **不再支持 `wire_api = "chat"`**（实测报错：
    #   `wire_api = "chat"` is no longer supported. How to fix: set `wire_api = "responses"`）
    # 而 DeepSeek 官方 API 只有 /chat/completions ⇒ **直连接不进来**。
    # 唯一现成通路是仓里的 `gbt_allinone/tools/responses_bridge.py`：
    #   它听 127.0.0.1:4455 的 /v1/responses，转成 <上游>/chat/completions，
    #   再把答案改写成 Codex 要的 SSE 事件序列（response.completed 收尾）。
    # 所以这里指向**本地桥**，桥的上游设成 DeepSeek（见 install 输出的启动命令）。
    "base_url": "http://127.0.0.1:4455/v1",
    "wire_api": "responses",
    "env_key": "",               # 桥不需要 key；key 由桥从环境变量取
    "display": "DeepSeek（经本地 Responses 桥）",
}

PROFILE_TEXT = """{marker}
# Opt-in profile. 不改变 Codex 的默认 provider（默认仍是主 config.toml 里那套）。
# 启用：codex --profile {profile}
#
# 关于 `model`：这个字符串会**原样**作为 `model` 参数发给上游。
# 上游不认就会 404 —— 那时只改这一行，别动其它。可用值以上游 /models 返回为准。
model = "{model}"
model_provider = "deepseek"

[model_providers.deepseek]
name = "{display}"
base_url = "{base_url}"
wire_api = "{wire_api}"
{env_line}requires_openai_auth = false
supports_websockets = false
request_max_retries = 0
stream_idle_timeout_ms = 240000
"""


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))


def _profile_path(name: str = PROFILE) -> Path:
    return _codex_home() / (name + ".config.toml")


def _render(model: str, base_url: str, wire_api: str, env_key: str, display: str) -> str:
    env_line = ('env_key = "%s"\n' % env_key) if env_key else ""
    return PROFILE_TEXT.format(marker=MARKER, profile=PROFILE, model=model,
                               base_url=base_url, wire_api=wire_api,
                               env_line=env_line, display=display)


def _atomic_write(path: Path, content: str) -> None:
    """原子写 + 结构校验 + 回读校验（照 `codex-local-profile.py` 的做法）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp-%d" % os.getpid())
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        parsed = tomllib.loads(tmp.read_text(encoding="utf-8"))
        prov = (parsed.get("model_providers") or {}).get("deepseek") or {}
        if parsed.get("model_provider") != "deepseek" or not parsed.get("model"):
            raise ValueError("生成的 profile 未通过结构校验：缺 model / model_provider")
        if prov.get("wire_api") != "responses" or not prov.get("base_url"):
            raise ValueError("生成的 profile 未通过结构校验：provider 段不完整"
                             "（Codex 0.166 只认 wire_api=responses）")
        os.replace(tmp, path)
        if path.read_text(encoding="utf-8") != content:
            raise OSError("profile 写后回读校验不一致")
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def install(model: str, base_url: str, wire_api: str, env_key: str, display: str) -> int:
    path = _profile_path()
    if path.exists() and MARKER not in path.read_text(encoding="utf-8", errors="replace"):
        print("拒绝覆盖已有的非本工具 profile：%s" % path)
        print("  （如果那是你手写的，先备份再删，或换一个 --name）")
        return 2
    text = _render(model, base_url, wire_api, env_key, display)
    _atomic_write(path, text)
    print("已安装 profile：%s" % path)
    print("  model        = %s" % model)
    print("  model_provider = deepseek")
    print("  base_url     = %s" % base_url)
    print("  wire_api     = %s" % wire_api)
    print("  env_key      = %s" % env_key)
    print()
    print("启用：codex --profile %s" % PROFILE)
    print("缺 key 会 401 —— 先确认环境变量 %s 存在（本工具不碰密钥）" % env_key)
    return 0


def show() -> int:
    path = _profile_path()
    if not path.is_file():
        print("没装：%s" % path)
        return 1
    print(path.read_text(encoding="utf-8"))
    print("—" * 40)
    env_key = "GBT_BRIDGE_KEY"
    try:
        env_key = (tomllib.loads(path.read_text(encoding="utf-8"))
                   .get("model_providers", {}).get("deepseek", {}).get("env_key") or env_key)
    except Exception:                                   # noqa: BLE001
        pass
    has = bool(os.environ.get(env_key))
    print("%s %s（%s）" % ("✅ 环境变量已设置:" if has else "🔴 环境变量未设置:",
                          env_key, "长度 %d" % len(os.environ.get(env_key, "")) if has else "codex 会 401"))
    return 0


def uninstall() -> int:
    path = _profile_path()
    if not path.is_file():
        print("没装：%s" % path)
        return 1
    if MARKER not in path.read_text(encoding="utf-8", errors="replace"):
        print("拒绝删除非本工具生成的 profile：%s" % path)
        return 2
    path.unlink()
    print("已删除：%s" % path)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="给 Codex 装一个 DeepSeek 的 opt-in profile")
    ap.add_argument("cmd", nargs="?", default="install",
                    choices=["install", "show", "uninstall"])
    ap.add_argument("--model", default=DEFAULTS["model"])
    ap.add_argument("--base-url", default=DEFAULTS["base_url"])
    ap.add_argument("--wire-api", default=DEFAULTS["wire_api"], choices=["chat", "responses"])
    ap.add_argument("--env-key", default=DEFAULTS["env_key"])
    ap.add_argument("--display", default=DEFAULTS["display"])
    a = ap.parse_args(argv)
    if a.cmd == "install":
        return install(a.model, a.base_url, a.wire_api, a.env_key, a.display)
    if a.cmd == "show":
        return show()
    return uninstall()


if __name__ == "__main__":
    raise SystemExit(main())
