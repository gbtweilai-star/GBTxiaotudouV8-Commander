# -*- coding: utf-8 -*-
"""A19 驱动触手（2026-10-31 · 主人令「使用 A19 驱动我们的触手」）

这是一条线，不是三个零件：
    ★主脑 A19   ──决策──►   触手总线（唯一门 run_task）   ──执行──►   真实结果
        ▲                                                        │
        └──────────────── 把执行结果回灌给主脑 ◄──────────────────┘

我们自己的整机权重（ownweights）也是这总线上的一个能力：
A19 算不动/被限流时，由触手通道顶上 —— 同一条线，不换轨道。

用法：
    python3 tools/a19_drive.py "看看服务面现在怎么样"
    python3 tools/a19_drive.py --max-steps 3 "先查健康，再报结论"
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MODEL = "gbt-v8-v82-q5_0"
KEY = "gbt"

# 给主脑看的工具箱（来自真实登记表，不是写死的示范）
def toolbox(limit: int = 24) -> list:
    from gbt_allinone.caps_registry import BENIGN_CAPS as R
    from gbt_allinone.security import policy as P
    out = []
    for name, meta in R.items():
        if not meta.get("safe"):
            continue
        try:
            if list(getattr(P.evaluate(name, {}), "scopes", ()) or ()):
                continue
        except Exception:                                        # noqa: BLE001
            continue
        out.append({"cap": name, "domain": meta.get("domain"),
                    "desc": str(meta.get("desc") or "")[:60]})
        if len(out) >= limit:
            break
    return out


SYS = """你是总指挥。你只能通过**调用触手**来做事，不许编造结果。

可用触手（能力位）：
%s

规则：
1) 需要做事时，只输出一行 JSON：{"cap":"<能力位名>","payload":{...}}
2) 已经能回答时，输出：{"final":"<给主人的话>"}
3) 不要输出 JSON 以外的任何文字。"""


def _post(path, body, tmo=180):
    req = urllib.request.Request("http://127.0.0.1:1234" + path,
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer " + KEY})
    with urllib.request.urlopen(req, timeout=tmo) as r:
        return json.loads(r.read())


def ask_a19(messages, tmo=180):
    d = _post("/v1/chat/completions",
              {"model": MODEL, "messages": messages, "max_tokens": 256,
               "temperature": 0.1}, tmo)
    ch = (d.get("choices") or [{}])[0]
    return str((ch.get("message") or {}).get("content") or "")


def extract_json(text: str):
    """从主脑回话里抠出第一个 JSON 对象（它偶尔会带解释）。"""
    i = text.find("{")
    while i >= 0:
        for j in range(len(text), i, -1):
            try:
                return json.loads(text[i:j])
            except Exception:                                    # noqa: BLE001
                continue
        i = text.find("{", i + 1)
    return None


def run(task: str, max_steps: int = 3, verbose: bool = True) -> dict:
    from gbt_allinone.api import run_task
    tb = toolbox()
    msgs = [{"role": "system", "content": SYS % "\n".join(
                "- %s（%s）：%s" % (t["cap"], t["domain"], t["desc"]) for t in tb)},
            {"role": "user", "content": task}]
    steps = []
    for step in range(1, max_steps + 1):
        t0 = time.time()
        try:
            reply = ask_a19(msgs)
        except urllib.error.HTTPError as e:
            return {"ok": False, "stage": "brain", "http": e.code,
                    "note": "主脑不可用（429=限流，稍等再试）", "steps": steps}
        except Exception as e:                                   # noqa: BLE001
            return {"ok": False, "stage": "brain", "err": type(e).__name__, "steps": steps}
        act = extract_json(reply) or {}
        if verbose:
            print("  [%d] 主脑(%.1fs)：%s" % (step, time.time() - t0, reply.strip()[:90]))
        if "final" in act:
            steps.append({"step": step, "final": act["final"]})
            return {"ok": True, "final": str(act["final"]), "steps": steps}
        cap = str(act.get("cap") or "").strip()
        if not cap:
            msgs.append({"role": "assistant", "content": reply})
            msgs.append({"role": "user", "content": '只输出 JSON：{"cap":...} 或 {"final":...}'})
            continue
        payload = act.get("payload") or {}
        tr = time.time()
        try:
            r = run_task(cap, payload)
            res = (r.get("gbt_result") or r).get("result") or {}
            ok = bool(res.get("ok", True)) and r.get("status") != "denied"
            summary = json.dumps(res, ensure_ascii=False)[:400]
            if verbose:
                print("      触手 %s → %s %.2fs %s" % (cap, "ok" if ok else "fail",
                                                      time.time() - tr, summary[:80]))
        except Exception as e:                                   # noqa: BLE001
            ok, summary = False, "执行异常：%s" % type(e).__name__
        steps.append({"step": step, "cap": cap, "ok": ok, "result": summary[:300]})
        msgs.append({"role": "assistant", "content": reply})
        msgs.append({"role": "user", "content": "触手 %s 的结果：%s\n继续：要么再调一个，要么给 {\"final\":...}"
                                               % (cap, summary[:600])})
    return {"ok": False, "stage": "max_steps", "steps": steps}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mx = 3
    for a in sys.argv[1:]:
        if a.startswith("--max-steps="):
            mx = int(a.split("=")[1])
    task = args[0] if args else "看看服务面现在怎么样，一句话报结论"
    print(json.dumps(run(task, mx), ensure_ascii=False, indent=1))
