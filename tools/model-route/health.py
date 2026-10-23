# -*- coding: utf-8 -*-
"""模型路由体检（model-route health）· 把"路由到底通不通"变成一条命令 + 一张表。

为什么要有它（2026-09-22 真实教训）：
  代理返回 **503 Service Unavailable** 时，我差点又去改 `settings.yaml` ——
  **503 是上游故障，不是配置错**。所以先量状态码，再决定动不动配置。

判据（门必须能失败）：
  ① 每个 provider 的**聊天端点**（DSH 实际走的 `/v1/messages`）必须返回 200 才算通
  ② 明确区分 **503(上游不可用) / 超时(慢或挂) / 404(路径或型号不对) / 401(密钥) / 429(限流)**
  ③ 任一 provider 通 ⇒ 退出码 0；全不通 ⇒ 非 0（这样它能当门用）

    python tools/model-route/health.py                 # 体检 settings.yaml 里全部 provider
    python tools/model-route/health.py --models        # 顺带列出该代理的全部型号
    python tools/model-route/health.py --provider unified
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

# 🔴 2026-09-26 补：Windows 管道/重定向下 stdout 回落 GBK，emoji 一打印就崩；与 self_model.py 同一款补丁
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


SETTINGS = pathlib.Path(os.path.expanduser("~")) / ".dsh" / "settings.yaml"
TIMEOUT = 40

CODES = {401: "密钥无效(AUTH)", 403: "被拒", 404: "路径/型号不对", 429: "限流",
         500: "上游内部错误", 502: "网关错误", 503: "**上游不可用**", 504: "网关超时"}


def load_providers():
    try:
        import yaml
    except ImportError:
        print("❌ 缺 pyyaml —— 用 C:\\Python312\\python.exe 跑（310 没装）")
        sys.exit(2)
    d = yaml.safe_load(SETTINGS.read_text(encoding="utf-8"))
    return d.get("llm-pi-ai", {}).get("providers", {}), d.get("agent-default-model", {})


def key_of(prov):
    """密钥：先查进程/用户环境变量（apiKeyEnv），拿不到就如实说"app 内部注入"。"""
    env = prov.get("apiKeyEnv")
    if not env:
        return None, "未声明 apiKeyEnv"
    v = os.environ.get(env) or ""
    if not v:
        import subprocess
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                f"[Environment]::GetEnvironmentVariable('{env}','User')"],
                               capture_output=True, text=True, timeout=20)
            v = (r.stdout or "").strip()
        except Exception:
            v = ""
    return (v or None), (env if v else f"{env}（不在环境里 · app 内部注入）")


def post_chat(base, key, model, stream=True):
    url = base.rstrip("/") + "/v1/messages"
    body = {"model": model, "max_tokens": 8, "stream": stream,
            "messages": [{"role": "user", "content": "说：通"}]}
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "x-api-key": key or "", "Authorization": f"Bearer {key or ''}",
                                          "anthropic-version": "2023-06-01"}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
            return r.status, len(raw), round((time.time() - t0) * 1000)
    except urllib.error.HTTPError as e:
        return e.code, 0, round((time.time() - t0) * 1000)
    except Exception as e:
        return None, type(e).__name__, round((time.time() - t0) * 1000)


def list_models(base, key):
    url = base.rstrip("/") + "/v1/models"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key or ''}", "x-api-key": key or ""})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
            return [m.get("id") for m in d.get("data", [])]
    except Exception as e:
        return [f"<取不到: {type(e).__name__}>"]


def main():
    a = sys.argv[1:]
    provs, default = load_providers()
    if "--provider" in a:
        want = a[a.index("--provider") + 1]
        provs = {k: v for k, v in provs.items() if k == want}
    print(f"模型路由体检 · {SETTINGS}")
    print(f"默认模型：{default.get('provider')} / {default.get('model')}\n")
    any_ok = False
    for name, p in provs.items():
        base = p.get("baseURL") or "?"
        models = [m["id"] for m in p.get("models", [])]
        if a.count("--models") or "--models" in a:
            pass
        key, knote = key_of(p)
        # 每个 provider 先探第一个型号（最像能代表它的那个）
        probe_model = models[0] if models else "?"
        st, extra, ms = post_chat(base, key, probe_model)
        if st == 200:
            any_ok = True
            verdict = f"✅ 通（{probe_model} · {ms}ms · {extra} 字节）"
        elif st is None:
            verdict = f"❌ 连接层失败（{extra} · {ms}ms）"
        else:
            verdict = f"❌ HTTP {st} {CODES.get(st, '')}（{ms}ms）"
        print(f"[{name}]")
        print(f"   baseURL : {base}   ← 结尾不能带 /v1（客户端自己会拼 /v1/messages）")
        print(f"   密钥    : {knote if key else '❌ ' + knote}")
        print(f"   型号({len(models)}) : {', '.join(models[:6])}{' …' if len(models) > 6 else ''}")
        print(f"   聊天    : {verdict}")
        if "--models" in a:
            ids = list_models(base, key)
            print(f"   池      : {len(ids)} 个 → {', '.join(ids[:10])}{' …' if len(ids) > 10 else ''}")
        print()
    if not any_ok:
        print("S-路由门: ❌ 所有 provider 的聊天端点都不通 —— **先看状态码再动配置**：")
        print("   503/504 ⇒ 上游故障（等它恢复，别改 baseURL/型号）")
        print("   401     ⇒ 密钥问题（换 key，不是改 URL）")
        print("   404     ⇒ baseURL 多了 /v1，或型号不在池里")
        sys.exit(1)
    print("S-路由门: ✅ 至少一个 provider 聊天端点通")
    sys.exit(0)


if __name__ == "__main__":
    main()
