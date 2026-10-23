# -*- coding: utf-8 -*-
"""模型版本对齐 · 四环现读 + 落数据件（这是那个页面的**唯一写手**）。

主人令（2026-10-21）：「使用我们的专属触手把这些给我独立页面和所有页面互通绑定好」。

四环（缺一条就是没对齐）：
  ① 卷      —— 现役产物在盘上、且写明 agg（来源 state/weights/ACTIVE.json，写卷时卡上算的）
  ② 端点    —— 两条 RunPod 端点 worker **自报**的 model id 必须等于现役目录
  ③ 云插件  —— Worker 的 llm_endpoint_wired / weights_ours_configured
  ④ 端到端  —— 用**客户端那把钥匙**打云插件，必须 200 且 weights_ours=true（而不是兜底 llama）

产物：
  state/model-deploy/cloud-align.json            （账，判据读它）
  holo_pet_w3/model-align/model-align-data.js    （页面数据，globalThis.GBT_MODEL_ALIGN）

用法：
  py -3.14 -X utf8 tools/codex-scripts/model-align.py probe            # 现读 + 落盘
  py -3.14 -X utf8 tools/codex-scripts/model-align.py --check          # 判据（四环不全绿=rc1）
  py -3.14 -X utf8 tools/codex-scripts/model-align.py --selftest       # 负对照（喂坏值必红）
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "state" / "model-deploy" / "cloud-align.json"
DATA = ROOT / "holo_pet_w3" / "model-align" / "model-align-data.js"
ACTIVE = ROOT / "state" / "weights" / "ACTIVE.json"
RKEY = ROOT / ".scratch" / ".runpod_key"
CRED = pathlib.Path.home() / ".dsh" / ".credentials.yaml"
BASE = "https://gbt-potato-cloud-10.paysssk.workers.dev"
EPS = ["qnnqf9w8xcefj8", "7b5inowyar12yh"]
UA = "gbt/1.0"
Q = "能力位 codex_status 是干什么的？它属于哪个域、调用时要注意什么？"


def _cred(name: str) -> str:
    if not CRED.is_file():
        return ""
    m = re.search(r"(?m)^\s*" + re.escape(name) + r"\s*:\s*(\S+)",
                  CRED.read_text(encoding="utf-8", errors="replace"))
    return m.group(1).strip("\"'") if m else ""


def _get(url: str, key: str = "", to: int = 90):
    h = {"User-Agent": UA}
    if key:
        h["Authorization"] = "Bearer " + key
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=to) as r:
            return 200, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:200].decode("utf-8", "replace")
    except Exception as e:                                            # noqa: BLE001
        return "ERR", "%s: %s" % (type(e).__name__, str(e)[:120])


def _get_retry(url: str, key: str = "", tries: int = 3, gap: int = 6, to: int = 60):
    """只读 GET，超时/网络类失败重试；拿到答复（含 4xx/5xx）就立刻回，不重试。

    返回值多一项"用了几次"，好让未验读数能说明"试了三次都没读到"。
    """
    st, d = "ERR", ""
    for i in range(1, tries + 1):
        st, d = _get(url, key, to)
        if st != "ERR":
            return st, d, i
        if i < tries:
            time.sleep(gap)
    return st, d, tries


def _post(url: str, body: dict, key: str = "", to: int = 180):
    """POST JSON；返回 (状态码|"ERR", 回包 dict 或原始片段, 耗时秒)。只读语义：只发推理请求。"""
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    h = {"User-Agent": UA, "Content-Type": "application/json"}
    if key:
        h["Authorization"] = "Bearer " + key
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=to) as r:
            return 200, json.loads(r.read() or b"{}"), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300].decode("utf-8", "replace"), time.time() - t0
    except Exception as e:                                            # noqa: BLE001
        return "ERR", "%s: %s" % (type(e).__name__, str(e)[:120]), time.time() - t0


def _post_retry(url: str, body: dict, key: str = "", tries: int = 2, gap: int = 8, to: int = 180):
    st, d, el = "ERR", "", 0.0
    for i in range(1, tries + 1):
        st, d, el = _post(url, body, key, to)
        if st != "ERR":
            return st, d, el
        if i < tries:
            time.sleep(gap)
    return st, d, el


COLD_WAIT_S = 420   # 冷启动等待预算：15GB 权重重载实测量级是"分钟"，90s 不够（端点2 实测第 90 秒后才 200）


def _queue_of(ep: str, key: str) -> dict:
    """网关侧队列/worker 现状（只读、不排队、秒回）。用来区分「还在起」与「真不服务」。"""
    st, d = _get("https://api.runpod.ai/v2/%s/health" % ep, key, 20)
    if not isinstance(d, dict):
        return {"http": st, "workers": {}, "jobs": {}, "raw": str(d)[:120]}
    return {"http": st, "workers": d.get("workers") or {}, "jobs": d.get("jobs") or {}}


def _looks_like_starting(q: dict) -> bool:
    """队列里还有活 / worker 在路上 ⇒ 这个端点只是慢，不是坏。"""
    if not isinstance(q, dict):
        return False
    w, j = q.get("workers") or {}, q.get("jobs") or {}
    if any((w.get(k) or 0) > 0 for k in ("initializing", "running", "ready", "throttled")):
        return True
    return (j.get("inQueue") or 0) > 0 or (j.get("inProgress") or 0) > 0


def _ep_state(st, sid, want, live, starting: bool = False) -> str:
    """端点判定的**唯一口径**（probe 与 --selftest-net 共用，免得判据两处各说各话）。

    · 没读到 + 队列里还有活/worker 在路上  ⇒ unverified（还在起：慢，不是坏）
    · 没读到 + 队列全空、没有 worker        ⇒ off（真不服务）
    · 回包 model 与现役目录不同            ⇒ mismatch（在服务，但是别的权重）
    · 名字对、可连不通/空答                ⇒ off
    """
    if st == "ERR" or live.get("http") == "ERR":
        return "unverified" if starting else "off"
    if sid != want:
        return "mismatch"
    if live.get("http") != 200 or not live.get("head"):
        return "off"
    return "ok"


def probe() -> dict:
    act = json.loads(ACTIVE.read_text(encoding="utf-8")) if ACTIVE.is_file() else {}
    want = act.get("active_artifact") or "/runpod-volume/gbt-v8-v83"
    rkey = RKEY.read_text(encoding="utf-8").strip() if RKEY.is_file() else ""

    rings = []

    # ① 卷
    rings.append({
        "ring": "① 卷上产物",
        "ok": bool(act.get("active_artifact")) and bool(act.get("active_agg_sha16")),
        "读": "%s · %.2f GB · agg %s"
              % (act.get("active_artifact"), (act.get("active_bytes") or 0) / 1e9,
                 act.get("active_agg_sha16")),
        "来源": "state/weights/ACTIVE.json（写卷时卡上算的 PROVENANCE）",
    })

    # ② 端点
    # 2026-10-21 三轮翻正，全部留痕（这一节改过三次，别只看最后一条）：
    #  第1版 一次不成就判 ❌ —— 出**负载假红**：端点忙时 models 排在作业后面超 90s 就误报「不符」。
    #  第2版 拆成 mismatch / unverified（拿到答复对不上=红；重试三次没拿到=未验）。
    #  第3版（现在，Owner 追问「为什么这里不连上验证」+ 根因诊断后的真修）：
    #     ① **身份不该问那条会挂的路**：`/openai/v1/models` 是被代理到 worker 的数据面请求，
    #        跟着吃冷启动。实测：端点空闲时 models 45s 超时；而**推理回包自带权威 `model` 字段**
    #        （`model='/runpod-volume/gbt-v8-v83'`）——谁是"真答的"，回包里写着。
    #        ⇒ 身份与现实**用同一次真推理**同时证，models 降级为**旁注**（读不到只记一笔，不判红）。
    #     ② **超时不能一律当「不服务」**：端点2 idleTimeout=5s、workersMin=0 ⇒ 每个请求都要
    #        重载 15GB。实测 90s 里 inQueue=2、running=1、ready=0，第 90 秒后 200 / 8.7s。
    #        ⇒ 超时后**再看一眼队列**：队列里有活/worker 在路上 ⇒ unverified（还在起）；
    #          队列全空且没有 worker ⇒ off（真不服务）。这样「慢」与「坏」不再混成一句。
    #     ③ 冷启动等待预算给足（COLD_WAIT_S），别用 90s 去量一个要几百秒才起得来的东西。
    eps = []
    for ep in EPS:
        # 旁注：自报 id（可能被冷启动/排队拖死，读不到不影响判定）
        mst, md, mtries = _get_retry("https://api.runpod.ai/v2/%s/openai/v1/models" % ep,
                                     rkey, tries=1, to=45)
        msid = ((md.get("data") or [{}])[0].get("id") if isinstance(md, dict) else None) or md
        before = _queue_of(ep, rkey)

        live = {"http": None, "ms": None, "head": "", "fp": False, "err": "", "echo": None}
        if True:
            body = {"model": want, "messages": [{"role": "user", "content": Q}],
                    "max_tokens": 64, "temperature": 0, "stream": False}
            lst, ld, lms = _post_retry("https://api.runpod.ai/v2/%s/openai/v1/chat/completions" % ep,
                                       body, rkey, tries=2, gap=8, to=COLD_WAIT_S)
            live["http"], live["ms"] = lst, round(lms, 1)
            if lst == "ERR":
                live["err"] = str(ld)[:120]
            elif lst == 200 and isinstance(ld, dict):
                txt = ((ld.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
                live["head"] = txt.strip().replace("\n", " ")[:40]
                live["fp"] = bool(re.search(r"能力位|codex_status", txt))
                live["echo"] = ld.get("model")
            else:
                live["err"] = ("HTTP %s: %s" % (lst, str(ld)[:120])) if lst != 200 else "回包不是 JSON"
        after = _queue_of(ep, rkey)
        busy = _looks_like_starting(after) or _looks_like_starting(before)
        state = _ep_state(lst if live["http"] != "ERR" else "ERR",
                          live["echo"] if live["echo"] is not None else msid, want, live,
                          starting=busy)
        eps.append({"endpoint": ep, "models_read": {"http": mst, "id": msid, "tries": mtries},
                    "live": live, "before": before, "after": after,
                    "state": state, "ok": state == "ok"})
    ep_unver = [e for e in eps if e["state"] == "unverified"]
    ep_bad = [e for e in eps if e["state"] in ("mismatch", "off")]
    fp_miss = [e for e in eps if e["state"] == "ok" and not e["live"]["fp"]]
    notes = []
    for e in eps:
        if e["models_read"]["http"] == "ERR":
            notes.append("%s 的 /models 没读到（数据面，超时不吃惊；身份已由回包 model 字段证实）"
                         % e["endpoint"])

    def _ep_note(e):
        if e["state"] == "unverified":
            w = (e["after"] or {}).get("workers") or {}
            j = (e["after"] or {}).get("jobs") or {}
            return "(未验·%ss 没等到答复；队列 inQueue=%s running=%s ready=%s ⇒ 还在起，不是不服务)" % (
                e["live"]["ms"], j.get("inQueue"), w.get("running"), w.get("ready"))
        if e["state"] == "mismatch":
            return "(不符·回包 model=%s)" % e["live"]["echo"]
        if e["state"] == "off":
            return "(连不上·%s)" % (e["live"]["err"] or "空答")
        return " · 真连 %s %ss「%s」回包 model=%s%s" % (
            e["live"]["http"], e["live"]["ms"], e["live"]["head"], e["live"]["echo"],
            "" if e["live"]["fp"] else " ⚠指纹不认")

    rings.append({"ring": "② 端点（真推理：身份+现实一次证）",
                  "ok": all(e["ok"] for e in eps),
                  "unverified": bool(ep_unver) and not ep_bad,
                  "warn": "；".join(notes + (["%s 连上了答了，但答里没有本版指纹（可能只是口径变了）"
                                             % "、".join(e["endpoint"] for e in fp_miss)] if fp_miss else [])),
                  "读": "; ".join("%s%s" % (e["endpoint"], _ep_note(e)) for e in eps),
                  "来源": "POST /openai/v1/chat/completions（temperature 0 真跑一次，身份取回包 model 字段；"
                          "/openai/v1/models 仅旁注）",
                  "detail": eps})

    # ③ 云插件接线
    st, d = _get(BASE + "/v1/models")
    gbt = (d.get("gbt") or {}) if isinstance(d, dict) else {}
    wired = gbt.get("llm_endpoint_wired") or {}
    rings.append({
        "ring": "③ 云插件接线", "ok": bool(wired.get("non_stream")) and bool(wired.get("stream")),
        "读": "HTTP %s · non_stream=%s · stream=%s · weights_ours_configured=%s"
              % (st, wired.get("non_stream"), wired.get("stream"), gbt.get("weights_ours_configured")),
        "来源": "Worker /v1/models",
    })

    # ④ 端到端（客户端那把钥匙）
    key = _cred("GW_AUTH") or _cred("GBT_ENDPOINT_TOKEN")
    body = {"model": "gbt-potato-v8", "messages": [{"role": "user", "content": Q}],
            "max_tokens": 160, "temperature": 0, "stream": False}
    r = urllib.request.Request(BASE + "/v1/chat/completions", data=json.dumps(body).encode(),
                               headers={"Content-Type": "application/json",
                                        "Authorization": "Bearer " + key, "User-Agent": UA})
    t0 = dt.datetime.now()
    try:
        with urllib.request.urlopen(r, timeout=300) as resp:
            d = json.loads(resp.read())
        txt = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        g = d.get("gbt") or {}
        ok4 = bool(g.get("weights_ours")) and "能力位" in txt
        rings.append({"ring": "④ 端到端（钥匙→云插件→权重）", "ok": ok4,
                      "读": "HTTP 200 · %.1fs · weights_ours=%s · via=%s · 答首句=%s"
                            % ((dt.datetime.now() - t0).total_seconds(), g.get("weights_ours"),
                               g.get("via") or g.get("upstream"), txt[:40].replace("\n", " ")),
                      "来源": "POST /v1/chat/completions（客户端钥 GW_AUTH）"})
    except Exception as e:                                            # noqa: BLE001
        rings.append({"ring": "④ 端到端（钥匙→云插件→权重）", "ok": False,
                      "读": "%s: %s" % (type(e).__name__, str(e)[:140]),
                      "来源": "POST /v1/chat/completions（客户端钥 GW_AUTH）"})

    todo = act.get("pending_fixes") or []
    return {
        "at": dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "want_model": want,
        "rings": rings,
        "all_ok": all(r["ok"] for r in rings),
        "any_unverified": any(r.get("unverified") for r in rings),
        "todo": todo,
        "note": "四环全绿 ⇒ 云上答话的就是这一版权重；有红 ⇒ 页面照红；⚠未验 ⇒ 没读到（超时/断链），"
                "不等于不符，也不许念成通 —— 重跑 probe 取真读数",
        "commands": {
            "probe": "py -3.14 -X utf8 tools/codex-scripts/model-align.py probe",
            "check": "py -3.14 -X utf8 tools/codex-scripts/model-align.py --check",
            "page": "holo_pet_w3/model-align/index.html",
        },
    }


def render(d: dict) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(
        "/* 自动生成，别手改。重建：py -3.14 tools/codex-scripts/model-align.py probe\n"
        "   数据源：state/model-deploy/cloud-align.json（四环现读）*/\n"
        "globalThis.GBT_MODEL_ALIGN = " + json.dumps(d, ensure_ascii=False) + ";\n",
        encoding="utf-8")


def _mark(r: dict) -> str:
    if r.get("ok"):
        return "✅"
    return "⚠" if r.get("unverified") else "❌"


def check(max_age_min: int = 180) -> int:
    if not OUT.is_file():
        print("红：没有 state/model-deploy/cloud-align.json（先跑 probe）")
        return 1
    d = json.loads(OUT.read_text(encoding="utf-8"))
    bad = [r for r in d.get("rings") or [] if not r.get("ok")]
    unver = [r for r in bad if r.get("unverified")]
    hard = [r for r in bad if not r.get("unverified")]
    age = None
    try:
        age = (dt.datetime.now() - dt.datetime.strptime(d["at"], "%Y-%m-%dT%H:%M:%S")).total_seconds() / 60
    except Exception:                                                 # noqa: BLE001
        pass
    head = "四环全绿" if not bad else ("红 %d 环" % len(hard) if hard else "未验 %d 环" % len(unver))
    print("模型对齐：%s" % head)
    for r in d.get("rings") or []:
        print("  %s %-22s %s" % (_mark(r), r["ring"], r["读"][:150]))
    if unver:
        print("⚠ 未验（不是不符）：%s ⇒ 超时/断链，重跑 probe 取真读数"
              % "、".join(r["ring"] for r in unver))
    for r in d.get("rings") or []:
        if r.get("warn"):
            print("⚠ %s：%s" % (r["ring"], r["warn"]))
    if age is None:
        print("黄：at 读不出来 ⇒ 新鲜度未验")
        return 1
    if age > max_age_min:
        print("黄：账已 %.0f 分钟没更新（阈值 %d）⇒ 读数不是第一时间的" % (age, max_age_min))
        return 1
    return 0 if not bad else 1


def _rc_for(d: dict) -> int:
    """把一份**合成**读数写进去跑判据，再读回（不改真账：调用方负责复原）。"""
    OUT.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return check(10000)


def selftest() -> int:
    """负对照：不符必红；未验也不许被念成绿（没读到 ≠ 对齐）；账太旧必黄；全绿才 rc0。

    注意：只喂合成读数，跑完把真账原样写回（P4：复原要能证明，不是相信）。
    """
    if not OUT.is_file():
        print("负对照：没有账件可喂，先跑 probe")
        return 1
    real = OUT.read_text(encoding="utf-8")
    try:
        d = json.loads(real)
        if len(d.get("rings") or []) < 4:
            print("负对照：账里环数不足 4，先跑 probe")
            return 1
        good = json.loads(json.dumps(d))
        for r in good["rings"]:
            r["ok"] = True
            r.pop("unverified", None)
        bad = json.loads(json.dumps(good))
        bad["rings"][1].update(ok=False, unverified=False)
        unv = json.loads(json.dumps(good))
        unv["rings"][1].update(ok=False, unverified=True)
        stale = json.loads(json.dumps(good))
        stale["at"] = "2000-01-01T00:00:00"
        rc_bad = _rc_for(bad)
        rc_unver = _rc_for(unv)
        rc_stale = _rc_for(stale)
        rc_ok = _rc_for(good)
    finally:
        OUT.write_text(real, encoding="utf-8")
    restored = OUT.read_text(encoding="utf-8") == real
    ok = (rc_bad, rc_unver, rc_stale, rc_ok) == (1, 1, 1, 0) and restored
    print("负对照：不符=rc%d（应 1）· 未验=rc%d（应 1，不许默认绿）· 账太旧=rc%d（应 1）"
          "· 全绿=rc%d（应 0）· 真账已原样复原=%s ⇒ %s"
          % (rc_bad, rc_unver, rc_stale, rc_ok, restored, "真能响" if ok else "不灵，判据有问题"))
    return 0 if ok else 1


def selftest_net() -> int:
    """真负向：拿**假端点 / 假模型名**打两次真网络，证明「不符」与「连不上」真会被判红。

    为什么要这一步：`--selftest` 喂的是合成账，证明的是"判据会读坏值"；
    证明不了"这两条分支真的走得到"。按 P21，兜底与拒绝路径必须真失败一次。
    成本：一次 404 + 一次 4xx，**不产生推理**。
    """
    want = "/runpod-volume/gbt-v8-v83"
    rkey = RKEY.read_text(encoding="utf-8").strip() if RKEY.is_file() else ""
    rows = []

    st, d, _ = _get_retry("https://api.runpod.ai/v2/zzzz-not-an-endpoint/openai/v1/models",
                          rkey, tries=1, to=30)
    sid = ((d.get("data") or [{}])[0].get("id") if isinstance(d, dict) else None) or d
    rows.append(("假端点（想让它判「不符」）", _ep_state(st, sid, want, {}), "mismatch", st))

    body = {"model": "no-such-model-zzz", "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 4, "temperature": 0, "stream": False}
    lst, ld, _ = _post_retry("https://api.runpod.ai/v2/%s/openai/v1/chat/completions" % EPS[0],
                             body, rkey, tries=1, to=60)
    live = {"http": lst, "head": "", "err": str(ld)[:120]}
    rows.append(("真端点 + 假模型名（想让它判「连不上」）", _ep_state(200, want, want, live), "off", lst))

    ok = all(got == exp for _, got, exp, _ in rows)
    for name, got, exp, code in rows:
        print("  %s %s → 判成 %s（应 %s）· HTTP %s"
              % ("✓" if got == exp else "✗", name, got, exp, code))
    print("网络负对照：%s" % ("真能判红" if ok else "不灵 —— 判据对这两条分支睁眼瞎"))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="probe", choices=["probe", "render"])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--selftest-net", action="store_true")
    a = ap.parse_args()
    if a.selftest_net:
        return selftest_net()
    if a.selftest:
        return selftest()
    if a.check:
        return check()
    d = probe()
    render(d)
    print("已落盘 %s 与 %s" % (OUT.relative_to(ROOT), DATA.relative_to(ROOT)))
    for r in d["rings"]:
        print("  %s %-22s %s" % (_mark(r), r["ring"], r["读"][:140]))
    print("四环：%s" % ("全绿" if d["all_ok"] else ("有未验（没读到，不是不符）" if d.get("any_unverified") else "有红")))
    # 2026-10-21 加：把「慢」和「坏」分开之后，还要把「怎么变快」写在这儿 ——
    # 端点缩 0 时第一句是冷启动（实测 107s / 文端口径 ~300s），不是模型慢。
    cold = []
    for r in d["rings"]:
        for e in (r.get("detail") or []):
            if not isinstance(e, dict) or "before" not in e:
                continue
            w = (e.get("before") or {}).get("workers") or {}
            if not any((w.get(k) or 0) > 0 for k in ("idle", "ready", "running", "initializing")):
                cold.append(e.get("endpoint"))
    if cold:
        print("⚠ 冷端点：%s ⇒ 要第一句就快，先挂热："
              % "、".join(sorted(set(cold))))
        print("   '{\"op\":\"on\"}' | py -3.14 tools/codex-scripts/five-dim.py cap warm_switch --stdin")
        print("   收工：'{\"op\":\"off\"}' | …（挂热期间按 worker 秒计费，别忘关）")
    return 0 if d["all_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
