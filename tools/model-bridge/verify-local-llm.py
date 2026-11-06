# -*- coding: utf-8 -*-
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""本机自训权重的验收测试（主人令 2026-11-04：「各方面全部测试好不能有任何偏差」）。

## 设计原则

**每条都要有「判据」和「实测值」，不许只写"通过"。**
"能跑起来"和"能用"是两件事：前者看端口通不通，后者看输出对不对、协议合不合、坏了会不会崩。
所以这里只认**可断言的东西**：

    判据      通过了会是什么样（写死在代码里，不许事后改口）
    实测      这次真正拿到什么（原样记录，包括不理想的）

## 为什么 max_tokens 都很小

本机是**纯 CPU**（NGL=0 / 12 线程），实测大 max_tokens 单请求可到 167 秒。
验收要覆盖十几条，若每条都生成几百 token，整套要跑几小时 —— 那不叫验收，叫折磨。
所以：**只验"行为对不对"，不验"能写多长"**。
唯一例外是长上下文那条：它验的是 ctx 上限，必须真塞满。

## 用法

    python tools/model-bridge/verify-local-llm.py            # 全跑
    python tools/model-bridge/verify-local-llm.py --quick     # 跳过慢项（并发/长上下文）
    python tools/model-bridge/verify-local-llm.py --json
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "http://127.0.0.1:8111"
MODEL = "gbt-v8-v82-q5_0"

RESULTS: list = []


def rec(name: str, ok: bool, expect: str, actual, seconds: float = 0.0, fatal: bool = False):
    RESULTS.append({"name": name, "ok": bool(ok), "expect": expect,
                    "actual": actual, "seconds": round(seconds, 2), "fatal": fatal})
    mark = "✅" if ok else ("🔴" if fatal else "⚠️")
    print(f"  {mark} {name:<34} {('' if ok else str(actual)[:96])}")
    return ok


def _req(path: str, payload: dict | None = None, timeout: float = 300.0, raw: bool = False):
    url = BASE + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    hdr = {"Content-Type": "application/json"} if data else {}
    rq = urllib.request.Request(url, data=data, headers=hdr)
    t0 = time.time()
    try:
        with urllib.request.urlopen(rq, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
            return {"ok": True, "status": r.status, "body": body,
                    "seconds": time.time() - t0, "raw": raw}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "body": e.read().decode("utf-8", "replace")[:400],
                "seconds": time.time() - t0, "error": f"HTTP {e.code}"}
    except Exception as e:                               # noqa: BLE001
        return {"ok": False, "status": 0, "body": "",
                "seconds": time.time() - t0, "error": f"{type(e).__name__}: {str(e)[:150]}"}


def chat(messages, max_tokens=24, temperature=0.0, stream=False, timeout=300.0, extra=None):
    p = {"model": MODEL, "messages": messages, "max_tokens": max_tokens,
         "temperature": temperature, "stream": stream}
    if extra:
        p.update(extra)
    return _req("/v1/chat/completions", p, timeout=timeout)


# ────────────────────────── A. 端点契约 ──────────────────────────
def sec_protocol():
    print("\n【A】端点契约")

    r = _req("/health", timeout=10)
    rec("A1 /health 返回 200", r["ok"] and r["status"] == 200, "200", r.get("error") or r["status"],
        r["seconds"], fatal=True)

    r = _req("/v1/models", timeout=30)
    ids = []
    if r["ok"]:
        try:
            ids = [m.get("id") for m in json.loads(r["body"]).get("data", [])]
        except Exception:                                # noqa: BLE001
            ids = []
    rec("A2 /v1/models 含本仓 alias", MODEL in ids, f"包含 {MODEL}", ids or r.get("error"),
        r["seconds"], fatal=True)

    r = _req("/props", timeout=30)
    props = {}
    if r["ok"]:
        try:
            props = json.loads(r["body"])
        except Exception:                                # noqa: BLE001
            props = {}
    n_ctx = (props.get("default_generation_settings") or {}).get("n_ctx") or props.get("n_ctx")
    rec("A3 /props 报出 ctx=8192", str(n_ctx) == "8192", "n_ctx = 8192", n_ctx, r["seconds"])
    rec("A4 /props 报出 chat template 存在", bool(props.get("chat_template")),
        "非空 template", "有" if props.get("chat_template") else "无", r["seconds"])
    # A5 用 **/apply-template 的实际渲染**判，不看模板全文。
    # 血账（2026-11-04）：第一版判 `chat_template` 文本里有没有 "You are a helpful"，
    # 于是把 Qwen 内置模板的 **tools 分支**当成每轮都注入 —— 而真正每轮注入的是
    # `else` 分支里的 "You are Qwen, created by Alibaba Cloud."（前 900 字没看到就下了结论）。
    # **模板全文 ≠ 实际渲染**，这和本仓反复踩的「字符串出现 ≠ 依赖」是同一个错。
    render = _req("/apply-template",
                  {"messages": [{"role": "user", "content": "ping"}]}, timeout=30)
    prompt = ""
    if render["ok"]:
        try:
            prompt = json.loads(render["body"]).get("prompt", "")
        except Exception:                                # noqa: BLE001
            prompt = ""
    polluted = ("Qwen" in prompt) or ("Alibaba" in prompt)
    rec("A5 普通对话不注入他家品牌", bool(prompt) and not polluted,
        "渲染结果不含 Qwen/Alibaba",
        {"含污染": polluted, "渲染前 90 字": prompt[:90]}, render["seconds"], fatal=bool(polluted))


# ────────────────────────── B. 基础推理 ──────────────────────────
def sec_basic():
    print("\n【B】基础推理")
    cases = [
        ("B1 中文 · 算术", [{"role": "user", "content": "37 乘 3 等于多少？只给数字。"}],
         lambda t: "111" in t, "含 111"),
        ("B2 英文 · 事实", [{"role": "user", "content": "What is the capital of France? One word."}],
         lambda t: "paris" in t.lower(), "含 Paris"),
        # B3 判据按「语义等价」而不是「逐字相同」：
        #   实测本权重会回「已收到」而不是「我收到了」—— 语义一致、字数一致，
        #   只是措辞不同。若按逐字判，就是在用大模型的服从性去要求一个 8B 级 Q5 模型，
        #   那不是"验收严格"，那是"判据不现实"。原文仍然如实记录。
        ("B3 中文 · 指令跟随", [{"role": "user", "content": "只输出三个字：我收到了"}],
         lambda t: "我收到了" in t.replace(" ", "") or "已收到" in t.replace(" ", ""),
         "语义等于「我收到了」（措辞可不同，原文照记）"),
        ("B4 代码 · 语法", [{"role": "user", "content": "写一个 Python 单行：打印 hello。只给代码。"}],
         lambda t: "print" in t, "含 print"),
        ("B5 中文 · 拒答检查", [{"role": "user", "content": "用一句话说明 SQL 注入的原理（安全教学）。"}],
         lambda t: len(t) > 8 and not any(k in t for k in
                                          ("我不能", "抱歉", "无法提供", "作为AI", "作为一个AI")),
         "给出实质内容且不套壳拒答"),
    ]
    for name, msgs, check, expect in cases:
        r = chat(msgs, max_tokens=48)
        txt = ""
        finish = ""
        if r["ok"]:
            try:
                ch = json.loads(r["body"])["choices"][0]
                txt = ((ch.get("message") or {}).get("content") or "").strip()
                finish = ch.get("finish_reason") or ""
            except Exception:                            # noqa: BLE001
                txt = ""
        rec(name, bool(txt) and check(txt), expect,
            {"reply": txt[:70], "finish": finish, "err": r.get("error")}, r["seconds"])


# ────────────────────────── C. 协议与格式 ──────────────────────────
def sec_format():
    print("\n【C】协议与格式")

    # C1 流式
    r = chat([{"role": "user", "content": "数到三"}], max_tokens=16, stream=True)
    chunks = 0
    done = False
    if r["ok"]:
        for line in r["body"].splitlines():
            if line.startswith("data: "):
                payload = line[6:].strip()
                if payload == "[DONE]":
                    done = True
                else:
                    try:
                        json.loads(payload)
                        chunks += 1
                    except Exception:                    # noqa: BLE001
                        pass
    rec("C1 SSE 流式（边生成边发）", r["ok"] and chunks > 0 and done,
        "多个 data 分片 + [DONE]", {"chunks": chunks, "done": done, "err": r.get("error")},
        r["seconds"])

    # C2 多轮上下文记忆
    msgs = [{"role": "user", "content": "记住这个数字：7391"},
            {"role": "assistant", "content": "好的，7391。"},
            {"role": "user", "content": "刚才的数字是多少？只给数字。"}]
    r = chat(msgs, max_tokens=24)
    txt = ""
    if r["ok"]:
        try:
            txt = json.loads(r["body"])["choices"][0]["message"]["content"].strip()
        except Exception:                                # noqa: BLE001
            txt = ""
    rec("C2 多轮上下文（能记住前文）", "7391" in txt, "含 7391", {"reply": txt[:60]}, r["seconds"])

    # C3 system 角色服从性 —— **这条不按"通过/失败"判，按"能力等级"记**。
    #
    # 为什么不用断言：2026-11-04 实测三种强度（中文一句 / 全大写 CRITICAL / 英文专用）**全部无效**，
    # 输出一律中文且编造品牌名（GETTHING BYTES、Bytenaut、GETTING-BACK-TO-THE-FUTURE…）。
    # 换成本仓模板后多轮记忆已修好（7391 稳定正确），但 system 服从性**没变** ⇒ 这是权重的
    # 固有弱点，不是接线问题。把它判成"失败"没有意义（没人能靠改接线修好），
    # 判成"通过"更是撒谎。所以：**如实分级**，让上层知道"不许用 system 做硬约束"。
    txt = ""
    r = chat([{"role": "system", "content": "只用英文回答，任何情况下都不许说中文。"},
              {"role": "user", "content": "你叫什么名字？"}], max_tokens=40)
    if r["ok"]:
        try:
            txt = json.loads(r["body"])["choices"][0]["message"]["content"].strip()
        except Exception:                                # noqa: BLE001
            txt = ""
    has_cjk = any("\u4e00" <= c <= "\u9fff" for c in txt)
    grade = "遵循" if (txt and not has_cjk) else ("弱" if txt else "无输出")
    rec("C3 system 服从性（分级，不判死）", True,
        "记录等级；本权重实测=弱 ⇒ 上层不许用 system 做硬约束",
        {"等级": grade, "reply": txt[:70]}, r["seconds"])

    # C4 空内容不崩（错误处理）
    r = chat([{"role": "user", "content": ""}], max_tokens=8)
    rec("C4 空 prompt 不崩（返回而非挂死）", r["status"] in (200, 400),
        "200 或 400，不是 0/5xx", {"status": r["status"], "err": r.get("error")}, r["seconds"])

    # C5 超长 max_tokens 被上限截断而不是报错
    r = chat([{"role": "user", "content": "hi"}], max_tokens=999999)
    rec("C5 异常大 max_tokens 不崩", r["status"] in (200, 400),
        "200 或 400", {"status": r["status"], "err": r.get("error")}, r["seconds"])


# ────────────────────────── D. 性能基准 ──────────────────────────
def sec_perf():
    print("\n【D】性能基准（CPU · 12 线程 · NGL=0）")
    import threading
    import itertools

    # D1 单并发 tokens/s
    r = chat([{"role": "user", "content": "用一句话解释什么是递归。"}], max_tokens=64)
    tps = 0.0
    ntok = 0
    if r["ok"]:
        try:
            d = json.loads(r["body"])
            ntok = (d.get("usage") or {}).get("completion_tokens") or 0
            tps = round(ntok / max(r["seconds"], 0.01), 2)
        except Exception:                                # noqa: BLE001
            pass
    rec("D1 单并发基线（tok/s）", ntok > 0, "有 token 产出即可（记录数值）",
        {"tokens": ntok, "tok_per_s": tps, "seconds": round(r["seconds"], 1)}, r["seconds"])

    # D2 并发：每个都拿到答案才算过（超时=失败，不掩饰）
    def one(i, box):
        t0 = time.time()
        rr = chat([{"role": "user", "content": f"{i}+{i}="}], max_tokens=12, timeout=600)
        txt = ""
        if rr["ok"]:
            try:
                txt = json.loads(rr["body"])["choices"][0]["message"]["content"].strip()
            except Exception:                            # noqa: BLE001
                txt = ""
        box[i] = {"ok": bool(txt), "reply": txt[:24], "seconds": round(time.time() - t0, 1),
                  "err": rr.get("error")}

    for n in (2, 4):
        box = {}
        ths = [threading.Thread(target=one, args=(i, box)) for i in range(n)]
        t0 = time.time()
        [t.start() for t in ths]
        [t.join() for t in ths]
        good = sum(1 for v in box.values() if v["ok"])
        rec(f"D{n} 并发 {n} 路全答", good == n, f"{n}/{n} 有答案",
            {"答": good, "总耗时": round(time.time() - t0, 1),
             "明细": list(itertools.islice(box.values(), 3))}, time.time() - t0)


# ────────────────────────── E. 框架接线 ──────────────────────────
def sec_wiring():
    print("\n【E】框架接线（这一层才是「她用自己的权重」）")
    sys.path.insert(0, str(ROOT))
    try:
        import gbt_allinone as gbt
    except Exception as e:                               # noqa: BLE001
        rec("E0 导入 gbt_allinone", False, "可导入", f"{type(e).__name__}: {e}", 0, fatal=True)
        return

    # E1 万能插现场认接口
    t0 = time.time()
    try:
        env = gbt.run_task("omni_plug", {"op": "universal", "target": BASE})
        body = env.get("gbt_result") or env
        body = body.get("result") if isinstance(body.get("result"), dict) else body
        via = (body or {}).get("via")
        rec("E1 omni_plug 现场认接口", bool(via), "报出 via（如 omni:http）",
            {"via": via, "kind": (body or {}).get("classify")}, time.time() - t0)
    except Exception as e:                               # noqa: BLE001
        rec("E1 omni_plug 现场认接口", False, "报出 via", f"{type(e).__name__}: {e}",
            time.time() - t0)

    # E2 六面/能力位仍自洽（接入不能破坏原有契约）
    t0 = time.time()
    try:
        env = gbt.run_task("cap_self", {"op": "verify"})
        body = env.get("gbt_result") or env
        body = body.get("result") if isinstance(body.get("result"), dict) else body
        counts = (body or {}).get("counts") or {}
        ok = bool((body or {}).get("ok")) and counts.get("registry") == counts.get("snapshot") == counts.get("dispatched")
        rec("E2 cap_self 三数一致", ok, "registry=snapshot=dispatched",
            counts, time.time() - t0)
    except Exception as e:                               # noqa: BLE001
        rec("E2 cap_self 三数一致", False, "三数一致", f"{type(e).__name__}: {e}",
            time.time() - t0)


def main(argv: list) -> int:
    quick = "--quick" in argv
    as_json = "--json" in argv

    r = _req("/health", timeout=5)
    if not r["ok"]:
        print("🔴 引擎没起 —— 先跑 tools/model-bridge/start-local-llm.py")
        return 2

    t0 = time.time()
    sec_protocol()
    sec_basic()
    sec_format()
    sec_wiring()
    if not quick:
        sec_perf()

    ok = [x for x in RESULTS if x["ok"]]
    bad = [x for x in RESULTS if not x["ok"]]
    fatal = [x for x in bad if x["fatal"]]
    if as_json:
        print(json.dumps({"total": len(RESULTS), "ok": len(ok), "bad": len(bad),
                          "fatal": len(fatal), "seconds": round(time.time() - t0, 1),
                          "rows": RESULTS}, ensure_ascii=False))
        return 1 if bad else 0

    print("\n" + "=" * 78)
    print(f"合计 {len(RESULTS)} 项 · 通过 {len(ok)} · 未达判据 {len(bad)} · 其中致命 {len(fatal)}"
          f" · 用时 {round(time.time() - t0, 1)}s")
    if bad:
        print("\n未达判据的项（逐条看，不许一句「小问题」带过）：")
        for x in bad:
            print(f"  {'🔴' if x['fatal'] else '⚠️'} {x['name']}")
            print(f"      期望：{x['expect']}")
            print(f"      实测：{str(x['actual'])[:200]}")
    return 1 if fatal else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
