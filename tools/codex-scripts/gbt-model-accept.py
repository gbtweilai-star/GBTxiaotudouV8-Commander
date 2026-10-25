# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 自家模型「能带工具干活」全链验收（2026-10-14 固化的测试码）。

## 为什么有它
主人问「你有测试码？」——把之前散着跑的一次性探针固化成**可复跑、可机检**的一份：
每个判据都打真读数，任何一条红就非零退出（能进 CI / 能进看门狗）。

## 判据（逐条都有出处，不猜）
  C1 代理在役   ：GET 127.0.0.1:8317/v1/models → 200 且车道表含 gbt-potato-v8
  C2 纯聊有正文 ：POST /v1/chat/completions → 200 且 message.content 非空
                  （2026-10-14 病案：加了 reasoning-parser 后正文全落进 reasoning、content=null）
  C3 工具被解析 ：tools + tool_choice=auto → finish_reason == "tool_calls"
                  且 tool_calls[0].function.name == "calc"、arguments 里有 "1+1"
                  （病案：chat_template 里工具示范写成双花括号 ⇒ 被解析器吞成空消息）
  C4 工具闭环   ：把 assistant.tool_calls + tool 结果回喂 → 最终 content 里出现该结果
                  （只"发得出"不算通，回喂后能用才算）
  C5 长上下文   ：约 18k tokens 的提示 → 200（不再是 16384 上限那个 400；现上限 32768）
  C6 Codex 端到端（默认跑，--quick 跳过）：codex exec -m gbt-potato-v8 让它执行 shell 命令，
                  判据=最终答复里含实际命令输出

用法：
    py -3.14 tools/codex-scripts/gbt-model-accept.py            # 全跑
    py -3.14 tools/codex-scripts/gbt-model-accept.py --quick    # 只跑 C1~C5

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOST, PORT = "127.0.0.1", int(os.environ.get("GBT_CLIPROXY_PORT", "8317"))
BASE = "http://%s:%d/v1" % (HOST, PORT)
APPDIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "gbt-cliproxy"
MODEL = os.environ.get("GBT_ACCEPT_MODEL", "gbt-potato-v8")
CODEX = Path(os.environ.get("CODEX_CLI_PATH") or
             r"C:\Users\ADMIN\AppData\Local\OpenAI\Codex\bin\2e5e00daee91c61d\codex.exe")
RESULTS: list = []


def _user_env(name: str) -> str:
    v = (os.environ.get(name) or "").strip()
    if v or os.name != "nt":
        return v
    try:
        import winreg                                          # noqa: PLC0415
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return (winreg.QueryValueEx(k, name)[0] or "").strip()
    except Exception:                                          # noqa: BLE001
        return ""


def _key() -> str:
    return _user_env("GBT_CLIPROXY_KEY") or (APPDIR / "client-key.txt").read_text(encoding="utf-8").strip()


def _post(path: str, body: dict, timeout: float = 300.0) -> tuple:
    req = urllib.request.Request(BASE + path, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                 method="POST",
                                 headers={"Authorization": "Bearer " + _key(), "Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310
            return r.status, r.read().decode("utf-8", "replace"), int((time.perf_counter() - t0) * 1000)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:400], int((time.perf_counter() - t0) * 1000)
    except Exception as exc:                                     # noqa: BLE001
        return 0, "连不上：%s" % str(exc)[:160], int((time.perf_counter() - t0) * 1000)


def _get(path: str, timeout: float = 10.0) -> tuple:
    req = urllib.request.Request(BASE + path, headers={"Authorization": "Bearer " + _key()})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:300]
    except Exception as exc:                                     # noqa: BLE001
        return 0, str(exc)[:160]


def check(cid: str, name: str, ok: bool, detail: str) -> None:
    RESULTS.append({"id": cid, "name": name, "ok": bool(ok), "detail": detail})
    print("%s %-3s %-12s %s" % ("PASS" if ok else "FAIL", cid, name, detail))


TOOLS = [{"type": "function",
          "function": {"name": "calc", "description": "算数",
                       "parameters": {"type": "object", "properties": {"expr": {"type": "string"}},
                                      "required": ["expr"]}}}]


def c1() -> None:
    # 🔴 实测坑（2026-10-14）：上游 worker 冷启动/回收期间，CLIProxyAPI **会暂时不列车道**
    #    ⇒ 一次读不到就判红是误报。这里退避重试（最多 90s），仍然读不到才红。
    st, body, ids = 0, "", []
    for _ in range(9):
        st, body = _get("/models")
        if st == 200:
            try:
                ids = [m.get("id") for m in (json.loads(body).get("data") or [])]
            except Exception:                                    # noqa: BLE001
                ids = []
        if st == 200 and MODEL in ids:
            break
        time.sleep(10)
    st, body = st, body
    if st == 200:
        try:
            ids = [m.get("id") for m in (json.loads(body).get("data") or [])]
        except Exception:                                        # noqa: BLE001
            ids = []
    check("C1", "代理+车道", st == 200 and MODEL in ids, "HTTP %s · 车道 %s" % (st, ids))


def c2() -> None:
    st, body, ms = _post("/chat/completions",
                         {"model": MODEL, "messages": [{"role": "user", "content": "只回两个字：在的"}],
                          "max_tokens": 16, "stream": False})
    txt = ""
    if st == 200:
        try:
            txt = (json.loads(body)["choices"][0]["message"].get("content") or "")
        except Exception:                                        # noqa: BLE001
            txt = ""
    check("C2", "纯聊有正文", st == 200 and bool(txt.strip()), "HTTP %s · %sms · content=%r" % (st, ms, txt[:40]))


def c3() -> None:
    st, body, ms = _post("/chat/completions",
                         {"model": MODEL, "messages": [{"role": "user", "content": "请用 calc 工具算 1+1"}],
                          "tools": TOOLS, "tool_choice": "auto", "max_tokens": 128, "stream": False})
    fr, tc = "", None
    if st == 200:
        try:
            ch = json.loads(body)["choices"][0]
            fr = ch.get("finish_reason") or ""
            tc = ch["message"].get("tool_calls")
        except Exception:                                        # noqa: BLE001
            pass
    ok = st == 200 and fr == "tool_calls" and bool(tc) and tc[0]["function"]["name"] == "calc" \
        and "1+1" in tc[0]["function"].get("arguments", "")
    check("C3", "工具被解析", ok, "HTTP %s · %sms · finish=%s · tool_calls=%s"
          % (st, ms, fr, json.dumps(tc, ensure_ascii=False)[:110] if tc else "None"))


def c4() -> None:
    st, body, ms = _post("/chat/completions",
                         {"model": MODEL, "messages": [{"role": "user", "content": "请用 calc 工具算 1+1"}],
                          "tools": TOOLS, "tool_choice": "auto", "max_tokens": 128, "stream": False})
    final, used = "", False
    if st == 200:
        try:
            a = json.loads(body)["choices"][0]["message"]
            tc = a.get("tool_calls") or []
            if tc:
                used = True
                msgs = [{"role": "user", "content": "请用 calc 工具算 1+1"},
                        {"role": "assistant", "content": a.get("content") or "", "tool_calls": tc},
                        {"role": "tool", "tool_call_id": tc[0].get("id", "call_1"), "content": "2"}]
                st2, body2, _ = _post("/chat/completions",
                                      {"model": MODEL, "messages": msgs, "max_tokens": 64, "stream": False})
                if st2 == 200:
                    final = json.loads(body2)["choices"][0]["message"].get("content") or ""
        except Exception:                                        # noqa: BLE001
            pass
    check("C4", "工具闭环回喂", used and "2" in final, "回喂后 content=%r" % (final[:60],))


def c5() -> None:
    big = "hello world " * 9000
    st, body, ms = _post("/chat/completions",
                         {"model": MODEL, "messages": [{"role": "user", "content": big + " 只回两个字：在的"}],
                          "max_tokens": 16, "stream": False}, timeout=420.0)
    pt = 0
    if st == 200:
        try:
            pt = json.loads(body)["usage"]["prompt_tokens"]
        except Exception:                                        # noqa: BLE001
            pt = 0
    ok = st == 200 and pt > 16384
    check("C5", "长上下文", ok, "HTTP %s · %sms · prompt_tokens=%s（上限现为 32768）" % (st, ms, pt))


def c6() -> None:
    if not CODEX.is_file():
        check("C6", "Codex 端到端", False, "codex 不在：%s" % CODEX)
        return
    env = dict(os.environ)
    if not env.get("GBT_CLIPROXY_KEY"):
        env["GBT_CLIPROXY_KEY"] = _user_env("GBT_CLIPROXY_KEY")
    work = Path(os.environ.get("TEMP", ".")) / "gbt_model_accept"
    work.mkdir(parents=True, exist_ok=True)
    cmd = [str(CODEX), "exec", "-m", MODEL, "--sandbox", "read-only", "--skip-git-repo-check",
           "-C", str(work), "用 shell 工具执行 echo GBT-TOOL-OK，然后只回你看到的输出"]
    t0 = time.perf_counter()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=600, env=env)
        out = (p.stdout or "") + (p.stderr or "")
    except Exception as exc:                                     # noqa: BLE001
        out = "跑失败：%s" % exc
    ms = int((time.perf_counter() - t0) * 1000)
    ok = "GBT-TOOL-OK" in out and "exec" in out
    check("C6", "Codex 端到端", ok, "%sms · 见工具调用=%s · 见工具输出=%s"
          % (ms, "exec" in out, "GBT-TOOL-OK" in out))


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                        # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="自家模型全链验收（回环）")
    ap.add_argument("--quick", action="store_true", help="跳过 C6（Codex 端到端，最慢那条）")
    a = ap.parse_args(argv)
    print("=== GBT小土豆V8 · 自家模型验收 · model=%s · 入口=%s ===" % (MODEL, BASE))
    for fn in ((c1, c2, c3, c4, c5) + (() if a.quick else (c6,))):
        try:
            fn()
        except Exception as exc:                                 # noqa: BLE001
            check(fn.__name__.upper(), "异常", False, str(exc)[:160])
    bad = [r for r in RESULTS if not r["ok"]]
    print("\n判据 PASS %d · FAIL %d" % (len(RESULTS) - len(bad), len(bad)))
    doc = ROOT / "state" / "gbt-model-accept.json"
    try:
        doc.write_text(json.dumps({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "model": MODEL,
                                   "results": RESULTS}, ensure_ascii=False, indent=2), encoding="utf-8")
        print("读数已落：%s" % doc)
    except OSError:
        pass
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
