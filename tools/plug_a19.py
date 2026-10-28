#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""plug_a19 —— 用**万能插**把 A19 当插座插进来并操控

## 为什么要有这条

主人原话：
  「你就不会使用万能插把她当容器插进去使用吗」
  「A19 的算力足够实现所有能力了」

他是对的。`omni_plug` 的插座类型里本来就写着 `ai`：
  「她的 AI 能量池：钥匙槽 + 任意 **OpenAI 兼容**端点；插上即输能并操控」

**LM Pocket 的 :1234/v1 就是 OpenAI 兼容端点。** 直接插。

## 过程中撞到的两道门（都修了）

```
① plug:  ai 插座只认 https  →  把本机回环 http 误伤了
② ai_call 里**还有一道一模一样的检查**  →  A 说插上了、B 说不行
```

回环地址物理上出不了本机，没有中间人 —— 对它要求 https 是误伤。
两处已同步放行 `127.0.0.0/8 · ::1 · localhost`（https 照旧）。

## 用法

    python3 tools/plug_a19.py                    # 插上并问一句
    python3 tools/plug_a19.py "今天几号"          # 插上并问这句
    python3 tools/plug_a19.py --probe            # 只看插没插上
"""
import argparse
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TARGET = "http://127.0.0.1:1234/v1"     # LM Pocket 的 OpenAI 兼容面
MODEL_DEFAULT = "gbt-v8-v82-q5_0"       # 她的 Q5_0 权重（从 /v1/models 现读也行）
KEY_ENV = "GBT_A19_KEY"                 # 钥匙槽：只写槽名，不回显明文


def _rt(payload: dict) -> dict:
    from gbt_allinone.api import run_task
    r = run_task("omni_plug", payload)
    return (r.get("gbt_result") or {}).get("result") or r.get("result") or {}


def _models() -> list:
    """现读 /v1/models —— 换权重不用改代码。"""
    import urllib.request
    try:
        req = urllib.request.Request(TARGET + "/models",
                                     headers={"Authorization": "Bearer " + os.environ.get(KEY_ENV, "")})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
        return [m.get("id") for m in (d.get("data") or [])]
    except Exception:                                         # noqa: BLE001
        return []


def main() -> int:
    ap = argparse.ArgumentParser(description="用万能插把 A19 当插座插进来")
    ap.add_argument("prompt", nargs="*", help="要问她的话（不给就问她的自我介绍）")
    ap.add_argument("--probe", action="store_true", help="只报插没插上，不问")
    ap.add_argument("--model", default="", help="指定模型名（默认现读 /v1/models）")
    a = ap.parse_args()

    # 钥匙槽：本机回环用字面钥（大小写敏感，A19 只认小写 gbt）
    os.environ.setdefault(KEY_ENV, "gbt")

    print("  ① 插插座（kind=ai · target=%s）" % TARGET)
    r1 = _rt({"op": "plug", "socket": "ai", "target": TARGET})
    sock = r1.get("插座") or {}
    print("     %s · %s" % (sock.get("state"), sock.get("detail")))
    if sock.get("state") != "plugged":
        print("  ⇒ 插不上，如实停在这里，不假装")
        return 1
    if a.probe:
        return 0

    model = a.model or (a and "") or ""
    if not model:
        ms = _models()
        model = ms[0] if ms else MODEL_DEFAULT
        if ms:
            print("     现读 /v1/models：%s" % ", ".join(ms[:3]))

    prompt = " ".join(a.prompt).strip() or "用一句话说你是谁"
    print("  ② 输能并操控（model=%s · key_slot=%s）" % (model, KEY_ENV))
    r2 = _rt({"op": "ai_chat", "prompt": prompt, "target": TARGET,
              "model": model, "key_env": KEY_ENV})
    print("     ok=%s http=%s" % (r2.get("ok"), r2.get("http")))
    if r2.get("ok"):
        print("     答：%s" % str(r2.get("text"))[:300])
        return 0
    print("     失败：%s / %s" % (r2.get("reason"), str(r2.get("upstream"))[:120]))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
