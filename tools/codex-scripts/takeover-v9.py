# -*- coding: utf-8 -*-
r"""接管外部件 V9（万能插 · 我们 → 她 的落地）—— **换脑 + 联能力，不破坏她一行**。

主人令（2026-10-10，逐字）：
  「我在给你讲一遍逻辑，你把这个当作是**外部的**，我们**穿透工作树找到这里，插入我们的**，
    这回明白了吗，**直接接管原来AI替换成我们的大模型接入联通所有能力**」

## 外部件在哪（穿透实测）
工作树 = C:/Users/ADMIN/Desktop/GBT小土豆V9（另有 .v9-dbs / .v9-sandbox / gbt-petato-v9）
入口   = GBT小土豆V9-总控台.cmd（它自己写着「[插座] 并一条我们的启动线（**原入口不动**）」）

## 它的 AI 位置（要换的就是这里）
core/brain.py —— 它的主脑，**唯一 LLM 出口**：
    BASE_URL = os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8317/v1")
    API_KEY  = os.environ.get("OPENAI_API_KEY",  "tk-brain-000")
    BRAIN_MODELS = os.environ.get("BRAIN_MODELS", "gpt-4o-mini,gpt-4o")
**实测：它的默认口现在是坏的** —— 8317 回 HTTP 401 Invalid API key
⇒ 换脑不是锦上添花，是把它救活。

## 怎么换（**不改她一行**）
只设三个环境变量，把它的**唯一出口**指到我们的口，然后原样调它的入口：
    OPENAI_BASE_URL=http://127.0.0.1:11434/v1   （我们的本地算力口）
    OPENAI_API_KEY=ollama
    BRAIN_MODELS=qwen3:0.6b                    （实测 8 秒出话）
⇒ 她的树**逐字节不变**，她的脑换成我们的。

## 联能力
枚举她的 core/*.py（她的能力模块）逐条登记，判据：**每条都要有名字与大小**（缺一即红）。

用法：py -3.14 -X utf8 tools/codex-scripts/takeover-v9.py [scan|brain|--check|--launch]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

V9 = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V9")
OUT = Path(__file__).resolve().parents[2] / "state" / "takeover-v9.json"
OUR_BRAIN = {"OPENAI_BASE_URL": "http://127.0.0.1:11434/v1",
             "OPENAI_API_KEY": "ollama",
             "BRAIN_MODELS": "qwen3:0.6b",
             "OMNIVOICE_PORT": "3900"}


def caps() -> list:
    """联能力：她的 core/*.py 就是她的能力模块（逐条登记，不猜）。"""
    out = []
    c = V9 / "core"
    if not c.is_dir():
        return out
    for p in sorted(c.glob("*.py")):
        if p.name == "__init__.py":
            continue
        out.append({"模块": p.name, "字节": p.stat().st_size})
    return out


def brain_check() -> dict:
    """她的脑现在通不通（实测，不猜）。"""
    def probe(base, key, model):
        body = json.dumps({"model": model,
                           "messages": [{"role": "user", "content": "只回两个字：在线"}],
                           "stream": False, "options": {"num_predict": 16}}).encode()
        req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=body,
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + key})
        try:
            import time as _t
            t0 = _t.time()
            with urllib.request.urlopen(req, timeout=180) as r:
                d = json.loads(r.read().decode("utf-8"))
            return {"通": True, "回": (d["choices"][0]["message"]["content"] or "").strip()[:30],
                    "秒": int(_t.time() - t0)}
        except Exception as e:                               # noqa: BLE001
            return {"通": False, "为什么": "%s: %s" % (type(e).__name__, str(e)[:70])}
    her = {"OPENAI_BASE_URL": os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8317/v1"),
           "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", "tk-brain-000"),
           "BRAIN_MODELS": os.environ.get("BRAIN_MODELS", "gpt-4o-mini")}
    return {"她的原口（未换脑）": dict(her, **probe(her["OPENAI_BASE_URL"], her["OPENAI_API_KEY"],
                                                   her["BRAIN_MODELS"].split(",")[0])),
            "我们的口（换脑用这个）": dict(OUR_BRAIN, **probe(OUR_BRAIN["OPENAI_BASE_URL"],
                                                             OUR_BRAIN["OPENAI_API_KEY"],
                                                             OUR_BRAIN["BRAIN_MODELS"].split(",")[0]))}


def launch() -> int:
    """原样调她的入口，只在**环境里**把脑换成我们的（她的树一行不改）。"""
    cmd = V9 / "GBT小土豆V9-总控台.cmd"
    if not cmd.is_file():
        print("找不到她的入口：%s" % cmd)
        return 2
    env = dict(os.environ, **OUR_BRAIN)
    print("换脑启动：%s" % cmd)
    print("  环境注入：%s" % json.dumps(OUR_BRAIN, ensure_ascii=False))
    return subprocess.call(["cmd", "/c", str(cmd)], env=env, cwd=str(V9))


def check() -> int:
    cs = caps()
    b = brain_check()
    bad = [c for c in cs if not c.get("模块") or not c.get("字节")]
    d = {"at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
         "外部件": {"工作树": str(V9), "入口": "GBT小土豆V9-总控台.cmd",
                    "在盘": V9.is_dir(), "入口在": (V9 / "GBT小土豆V9-总控台.cmd").is_file()},
         "她的AI位置": {"文件": "core/brain.py",
                        "原口径": "OPENAI_BASE_URL 默认 http://127.0.0.1:8317/v1 · API_KEY tk-brain-000"},
         "换脑口径": OUR_BRAIN, "脑实测": b,
         "能力模块数": len(cs), "能力逐条": cs,
         "口径": "**不改她一行**：只设环境变量把她的唯一 LLM 出口指到我们的口，然后原样调她的入口"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print("接管外部件 V9")
    print("  工作树：%s（在盘 %s · 入口 %s）" % (V9, d["外部件"]["在盘"], d["外部件"]["入口在"]))
    print("  她的脑（原口）：%s" % ("通" if b["她的原口（未换脑）"]["通"] else
                                   "**不通** " + b["她的原口（未换脑）"].get("为什么", "")))
    print("  我们的口（换脑）：%s %s" % ("通" if b["我们的口（换脑用这个）"]["通"] else "不通",
                                       b["我们的口（换脑用这个）"].get("回") or
                                       b["我们的口（换脑用这个）"].get("为什么", "")))
    print("  她的能力模块：%d 个（core/*.py）" % len(cs))
    print("判据：%s" % ("PASS" if not bad else "FAIL（有 %d 条能力没登记全）" % len(bad)))
    return 0 if not bad else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="接管外部件 V9（换脑 + 联能力）")
    ap.add_argument("cmd", nargs="?", default="scan", choices=["scan", "brain", "launch"])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.cmd == "launch":
        return launch()
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
