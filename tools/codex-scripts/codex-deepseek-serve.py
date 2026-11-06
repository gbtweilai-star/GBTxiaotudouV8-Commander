# -*- coding: utf-8 -*-
"""codex-deepseek-serve —— 起「DeepSeek → Codex」的本地 Responses 桥。

## 为什么需要它
Codex 0.166 只认 `wire_api = "responses"`，`wire_api = "chat"` 已被该版本废弃；
而 DeepSeek 官方只提供 `/chat/completions`。所以中间必须有一座桥：
    听 127.0.0.1:4455 的 `POST /v1/responses`
    → 转 `POST <上游>/chat/completions`
    → 再把答案改写成 Codex 要的 SSE（response.created → … → response.completed）
桥本体在 `gbt_allinone/tools/responses_bridge.py`；
本文件只负责**把环境变量配齐 + 起桥前先探活**。

## 三步走
    # ① 存 key（一次性；DPAPI 加密，明文不进 argv / 不进日志 / 不落明文盘）
    "sk-xxx" | .\\pyembed\\python.exe -m gbt_allinone.deepseek_key set
    # ② 起桥（前台，窗口别关）
    .\\pyembed\\python.exe tools\\codex-scripts\\codex-deepseek-serve.py
    # ③ 另开一个窗口
    codex --profile deepseek

## 铁律
  · key 只从 DPAPI 保险箱 / 环境变量取，**不落明文、不回显**（只报掩码）；
  · **起桥之前先探活上游**：key 不行、model 不认，当场如实报，不装成「已就绪」；
  · 探活失败**不阻断**启动（有的上游不开放 /models），但必须明确写「未验证」，
    不许把它写成「已验证通过」。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:                                        # noqa: BLE001
    pass

DEFAULT_UPSTREAM = "https://api.deepseek.com/v1"
DEFAULT_PORT = 4455
PROFILE_TOML = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")) / "deepseek.config.toml"


def _profile_model() -> str:
    """从 ~/.codex/deepseek.config.toml 读 model。

    只用 regex 读这一行（不引第三方 toml 依赖，也不去解析整份配置 ——
    那份文件的归属是 Codex，改动它的主键不是本脚本的事）。
    """
    try:
        text = PROFILE_TOML.read_text(encoding="utf-8")
    except Exception:                                    # noqa: BLE001
        return ""
    m = re.search(r'^\s*model\s*=\s*"([^"]+)"', text, re.M)
    return m.group(1) if m else ""


def _take_key() -> tuple[str, str]:
    """取 DeepSeek key。返回 (key, source)；source 用于如实报告来源。"""
    try:
        from gbt_allinone.deepseek_key import load_key
    except Exception as exc:                             # noqa: BLE001
        env = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if env:
            return env, "env:DEEPSEEK_API_KEY（保险箱模块不可用）"
        return "", "missing（保险箱模块也导入不了：%s）" % str(exc)[:80]
    key, source = load_key("deepseek")
    return key, source


def _probe(upstream: str, key: str, model: str, timeout: float = 12.0) -> dict:
    """探活上游：能拿到模型清单就算「通」；拿不到如实报原因。"""
    url = upstream.rstrip("/") + "/models"
    req = urllib.request.Request(url, method="GET",
                                 headers={"Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode("utf-8", "replace") or "{}")
    except Exception as exc:                             # noqa: BLE001
        return {"ok": False, "why": "%s: %s" % (type(exc).__name__, str(exc)[:160]), "url": url}

    ids = [str(it.get("id")) for it in (body.get("data") or []) if isinstance(it, dict) and it.get("id")]
    return {
        "ok": True,
        "url": url,
        "count": len(ids),
        "ids": ids,
        "model_listed": (model in ids) if model else None,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="起 DeepSeek → Codex 的本地 Responses 桥")
    ap.add_argument("--upstream", default=os.environ.get("GBT_BRIDGE_UPSTREAM") or DEFAULT_UPSTREAM,
                    help="上游 OpenAI 兼容地址（默认 %s）" % DEFAULT_UPSTREAM)
    ap.add_argument("--model", default=os.environ.get("GBT_BRIDGE_MODEL") or "",
                    help="发给上游的 model 名（默认取 ~/.codex/deepseek.config.toml 的 model）")
    ap.add_argument("--port", type=int, default=int(os.environ.get("GBT_BRIDGE_PORT") or DEFAULT_PORT))
    ap.add_argument("--probe-only", action="store_true", help="只探活上游，不起桥")
    args = ap.parse_args(argv)

    model = args.model or _profile_model()
    upstream = args.upstream.rstrip("/")

    print("上游   :", upstream)
    print("model  :", model or "(未指定 —— 桥会回落到它自己的 GBT_BRIDGE_MODEL)")
    print("端口   :", args.port)

    key, source = _take_key()
    if not key:
        print()
        print("[缺 key] source =", source)
        print("本机没有 DeepSeek 密钥。先存一份（DPAPI 加密，明文不进 argv/日志）：")
        print('  "sk-xxx" | .\\pyembed\\python.exe -m gbt_allinone.deepseek_key set')
        print("存完再跑本脚本。**不会**用 OpenAI 的 key 冒名顶替。")
        return 2

    masked = (key[:5] + "****") if len(key) >= 5 else "****"
    print("key    :", masked, "（来源：%s）" % source)
    print()

    print("探活上游 /models …")
    probe = _probe(upstream, key, model)
    if probe.get("ok"):
        print("  通：上游返回 %d 个模型" % probe.get("count", 0))
        if probe.get("model_listed") is False:
            print("  [!] 但清单里**没有** %r —— 直接发 /chat/completions 很可能 404。" % model)
            print("      上游给的可用 id：", ", ".join(probe.get("ids") or [])[:400])
            print("      处置：把 ~/.codex/deepseek.config.toml 的 model 改成上面某个 id（只改这一行）。")
        elif probe.get("model_listed") is True:
            print("  model %r 在清单里 ✓" % model)
    else:
        print("  未能验证：", probe.get("why"))
        print("  （不阻断启动；但「未验证」不等于「已验证通过」，别当成功看。）")

    if args.probe_only:
        return 0 if probe.get("ok") else 1

    print()
    print("起桥（前台运行，这个窗口关掉桥就没了）…")
    os.environ["GBT_BRIDGE_UPSTREAM"] = upstream
    os.environ["GBT_BRIDGE_KEY"] = key
    if model:
        os.environ["GBT_BRIDGE_MODEL"] = model
    os.environ["GBT_BRIDGE_PORT"] = str(args.port)
    try:
        sys.stdout.flush()
    except Exception:                                    # noqa: BLE001
        pass

    from gbt_allinone.tools.responses_bridge import main as bridge_main
    return bridge_main()


if __name__ == "__main__":
    raise SystemExit(main())
