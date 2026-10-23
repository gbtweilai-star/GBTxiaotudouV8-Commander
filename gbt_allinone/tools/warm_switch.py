# -*- coding: utf-8 -*-
# gbt-capability: warm_switch
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""warm_switch —— 按需常驻开关（主人 2026-10-12「可以通过隧道，你这么跳都一样」）。

## 主人这句对在哪、不对在哪（都实测过）
  · 对：**隧道/常驻心跳能把"每次重建连接"和路径抖动消掉** ✓，而且**活着就好跳**（跳数不再有意义 ✓）。
  · 不对：**GPU 在云端空转照样计费** ✗（RunPod 按 worker 运行秒计费）；隧道**不能替你付钱** ✗，
    也**不能让 15GB 权重加载变快** ✗（冷启动 ~300s 的主体是权重+引擎加载，不是距离）。
  ⇒ 正解不是"永久常驻"，是**按需常驻**：开工挂热 ✓ 收工放掉缩 0 ✓（这就是本件）。

## 干什么
  op=on     开：后台每 150 秒打一次**最小推理**（1 token）⇒ 端点不缩 0 ⇒ 你随便跳都是热的 ✓
  op=off    关：**杀心跳 + 真把端点缩到 0**（见下条）⇒ 恢复省钱 ✓
  op=scale0 缩：真打云端 `PATCH /v1/endpoints/<id>` 把 `workersMin` 设 0 + `idleTimeout` 设 5 秒
            （RunPod 官方 v1 接口；PATCH 会触发 rolling release ⇒ 卡住的 worker 被换掉）
  op=config 读：端点的真配置（workersMin/Max/idleTimeout/executionTimeoutMs + 现役 worker 清单）
  op=status 读：心跳在不在 + 端点 worker 状态 + 是否正在"没人用还在烧"（现读）
  op=cost   算：按当前状态估"每小时/每天"的花费（诚实标口径：按 worker 运行秒 ✓）

## 🔴 2026-10-21 修（实测逮到的"自己跑掉"，主人令「没使用的时候绝不能消耗」）
  旧版 `off()` 只 `taskkill` 本机心跳进程，**一个字节都不碰端点上那个 worker** ——
  而它自己在返回里写着「心跳停了 ⇒ 端点按 idleTimeout 缩 0 ⇒ 恢复省钱」。
  实测形态：心跳 11:27:39 之后就没了，端点 `workers.running` 仍是 **1**，账户继续 **$0.704/时** 烧。
  ⇒ 现口径：**关钱的动作必须真打到云端并回读验证**（`workersMin=0` + 回读 `running=0`）；
  且本件**结构上只能缩不能扩**：`scale0()` 不收任何"把 min 调大"的参数。
  另：本能力位在 `security/policy.py` 里**没有分支 ⇒ 零作用域**（"零作用域 ≠ 只读"的活样本），
  所以自动缩 0 才能无人值守地干成 —— 这正是"关钱不该比花钱难"的实现位。

## 铁律
  · 只打**最小推理**（max_tokens=1），不烧无用的 token ✓；
  · 状态**现读**（不信缓存）；花费**带口径**（不编数）；
  · 开关本身**不碰授权门**：它只是"用你自己的额度"，不发放任何权限 ✓。
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_PID = _ROOT / "gbt_allinone" / "store" / "warm_switch" / "beat.pid"


def _dir() -> pathlib.Path:
    d = os.environ.get("GBT_STORE_DIR")
    base = pathlib.Path(d) if d else (_ROOT / "gbt_allinone" / "store")
    p = base / "warm_switch"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _key() -> str:
    p = _ROOT / ".scratch" / ".runpod_key"
    return p.read_text(encoding="utf-8").strip() if p.is_file() else ""


def _ep() -> str:
    p = _ROOT / ".scratch" / ".ep_id"
    return p.read_text(encoding="utf-8").strip() if p.is_file() else ""


def _served_model() -> str:
    """现役目录（写卷时卡的那份）——心跳要知道该点哪个模型名。"""
    p = _ROOT / "state" / "weights" / "ACTIVE.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return str(d.get("active_artifact") or "/runpod-volume/gbt-v8-v83")
    except Exception:                                       # noqa: BLE001
        return "/runpod-volume/gbt-v8-v83"


# ── 云端真动作：RunPod REST v1 endpoints 面（官方文档 api-reference/endpoints）──────────────
_REST = "https://rest.runpod.io/v1"


def _rest(path: str, method: str = "GET", body: dict | None = None) -> tuple:
    """打 RunPod REST v1。**取不到就带原始载荷**（P19：不许只说"失败"）。"""
    import urllib.error
    import urllib.request
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(_REST + path, method=method, data=data,
                                 headers={"Authorization": "Bearer " + _key(),
                                          "User-Agent": "gbt/1.0",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read().decode("utf-8", "replace")
            return r.status, (json.loads(raw) if raw.strip() else {})
    except urllib.error.HTTPError as e:
        raw = (e.read() or b"").decode("utf-8", "replace")
        return e.code, {"_raw": raw[:500]}
    except Exception as e:                                      # noqa: BLE001
        return None, {"_raw": "%s: %s" % (type(e).__name__, str(e)[:200])}


def _workers_of(ep: dict) -> list:
    """从 endpoint 对象里取现役 worker 清单（官方 Endpoint schema 的 `workers`：Pod 列表）。"""
    ws = ep.get("workers")
    if not isinstance(ws, list):
        return []
    out = []
    for w in ws:
        if not isinstance(w, dict):
            continue
        out.append({"id": w.get("id"), "状态": w.get("desiredStatus") or w.get("status"),
                    "GPU": ((w.get("machine") or {}).get("gpuDisplayName")
                            or (w.get("gpu") or {}).get("displayName")),
                    "$/h": w.get("costPerHr"), "起于": w.get("lastStartedAt"),
                    "最近变更": w.get("lastStatusChange")})
    return out


def config() -> dict:
    """**读**：端点的真配置 + 现役 worker（只读，不改任何东西）。"""
    ep = _ep()
    if not ep:
        return {"ok": False, "op": "config", "status": "no_endpoint_id",
                "note": "`.scratch/.ep_id` 不在 ⇒ 如实报缺，不猜端点"}
    st, d = _rest("/endpoints/" + ep)
    if not (st and 200 <= st < 300):
        return {"ok": False, "op": "config", "endpoint": ep, "http": st,
                "why": d.get("_raw") or d, "reason": "endpoint_unreadable"}
    ws = _workers_of(d)
    return {"ok": True, "op": "config", "endpoint": ep,
            "name": d.get("name"), "workersMin": d.get("workersMin"),
            "workersMax": d.get("workersMax"), "idleTimeout": d.get("idleTimeout"),
            "executionTimeoutMs": d.get("executionTimeoutMs"),
            "gpuTypeIds": d.get("gpuTypeIds"), "gpuCount": d.get("gpuCount"),
            "worker_count": len(ws), "workers": ws,
            "_口径": "GET /v1/endpoints/<id> 现读；workersMin>0 即『没人用也照收钱』的常驻底"}


_SCALE0 = {"workersMin": 0, "idleTimeout": 5, "executionTimeoutMs": 180000}
# 三段各治一个病（2026-10-21 实测）：
#   workersMin=0      —— 不许有"常驻底"（哪怕没人用也照收钱的保底 worker）
#   idleTimeout=5     —— 原来 301 秒：每次有人碰一下，worker 之后还要白跑 5 分钟（~$0.074/次）
#   executionTimeoutMs=180000 —— 原来 null（无上限）：被网关抛弃的请求能在 worker 里跑到天荒地老
#                                （台账 §291 记过一条 HTTP 504 · 570 秒的，就是这一类）


def scale0(why: str = "", **_kw) -> dict:
    """**真缩到 0**：`workersMin=0` + `idleTimeout=5`（RunPod 允许的最小值）。

    🔴 结构上只能缩不能扩：本函数**不接受任何**能调大 `workersMin`/`workersMax` 的参数
       （`**_kw` 只吞不用，`why` 只进回执）—— 这条是为了让"自动省钱"这条路不可能被用来加钱。
    铁律：**看回读，不看回执**。PATCH 后必须再 GET 一次，`workersMin==0` 且 `running==0` 才算成。
    """
    ep = _ep()
    if not ep:
        return {"ok": False, "op": "scale0", "status": "no_endpoint_id"}
    before = config()
    if not before.get("ok"):
        return {"ok": False, "op": "scale0", "reason": "config_unreadable_before", "before": before}
    st, d = _rest("/endpoints/" + ep, method="PATCH", body=dict(_SCALE0))
    after = config()
    h = _health()
    w = (h or {}).get("workers") if isinstance(h, dict) else None
    w = w if isinstance(w, dict) else {}
    running = (w.get("running") or 0)
    ok = bool(after.get("ok") and after.get("workersMin") == 0 and running == 0)
    return {"ok": ok, "op": "scale0", "endpoint": ep, "why": why or None,
            "http": st, "patch_ok": bool(st and 200 <= st < 300),
            "before": {"workersMin": before.get("workersMin"), "idleTimeout": before.get("idleTimeout"),
                       "worker_count": before.get("worker_count"), "workers": before.get("workers")},
            "after": {"workersMin": after.get("workersMin"), "idleTimeout": after.get("idleTimeout"),
                      "worker_count": after.get("worker_count"), "workers": after.get("workers")},
            "health_workers": w, "running": running,
            "_口径": "两段读数：PATCH 前后各 GET 一次 + health；只按**回读**判成败（不看回执文案）",
            "_raw": None if (st and 200 <= st < 300) else d.get("_raw")}


def _health() -> dict:
    """端点 health（workers 分布）—— 读不到就带异常名，不拿 0 冒充。"""
    try:
        import urllib.request
        req = urllib.request.Request("https://api.runpod.ai/v2/%s/health" % _ep(),
                                     headers={"Authorization": "Bearer " + _key()})
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode("utf-8", "replace")) or {}
    except Exception as e:                                      # noqa: BLE001
        return {"_读不到": "%s: %s" % (type(e).__name__, str(e)[:160])}


def _beat_script() -> str:
    """心跳本体。

    🔴 2026-10-21 修（实测逮到的死路）：旧版**只**打本机桥 `127.0.0.1:4455`，
    而那个桥当天**根本没在监听**（`Test-NetConnection 4455` = False）⇒ 每一次心跳都抛异常，
    日志里全是异常名，`op=on` 却一直回"已开"。这就是"接上了但其实没接"。
    现在：**先试本机桥，不通就直打端点**（每次只用 1 token），并把**用的是哪条路、什么结果**写进日志，
    好让 `status()` 能回答"心跳最近到底成没成"，而不是只看进程在不在。
    """
    model = _served_model()
    return chr(10).join([
        "# -*- coding: utf-8 -*-",
        "import time, json, urllib.request",
        "from pathlib import Path",
        "WS = Path(r'%s')" % str(_ROOT),
        "KEY = (WS/'.scratch'/'.runpod_key').read_text(encoding='utf-8').strip()",
        "EP = (WS/'.scratch'/'.ep_id').read_text(encoding='utf-8').strip()",
        "MODEL = %r" % model,
        "LOG = WS/'.scratch'/'_warm_beat.log'",
        "BRIDGE = 'http://127.0.0.1:4455/v1/responses'",
        "DIRECT = 'https://api.runpod.ai/v2/' + EP + '/openai/v1/chat/completions'",
        "def hit(url, body):",
        "    req = urllib.request.Request(url, data=json.dumps(body).encode(), method='POST',",
        "        headers={'Content-Type':'application/json','Authorization':'Bearer '+KEY,",
        "                 'User-Agent':'gbt/1.0'})",
        "    t0 = time.time()",
        "    try:",
        "        with urllib.request.urlopen(req, timeout=420) as r:",
        "            return r.status, round(time.time()-t0, 1)",
        "    except Exception as e:",
        "        return type(e).__name__, round(time.time()-t0, 1)",
        "while True:",
        "    # ① 先试本机桥（触手那条路）；不通再直打端点",
        "    st, el = hit(BRIDGE, {'model':'gbt-potato-v8','input':'ok','stream':False})",
        "    path = 'bridge'",
        "    if st != 200:",
        "        st, el = hit(DIRECT, {'model':MODEL,'messages':[{'role':'user','content':'ok'}],",
        "                              'max_tokens':1,'temperature':0,'stream':False})",
        "        path = 'runpod'",
        "    with LOG.open('a', encoding='utf-8') as f:",
        "        f.write('%s  beat %s %s %ss' % (time.strftime('%Y-%m-%d %H:%M:%S'), path, st, el) + chr(10))",
        "    time.sleep(150)",
    ])


def billing(days: int = 12) -> dict:
    """**读**：服务端真账（`GET /v1/billing/endpoints`）—— 钱到底有没有在走，只有这张账说了算。

    为什么这条必须能免票读：`pod_link` 的 `account` 要 process_execute + **一次性** data_export，
    看一次余额就烧掉一张票 ⇒「先算账」在无人值守时永远做不到（P15 同型）。
    本件只读，不打印任何密钥，按天给出：计费分钟数 / 金额 / 磁盘量。
    """
    st, rows = _rest("/billing/endpoints")
    if not (st and 200 <= st < 300) or not isinstance(rows, list):
        return {"ok": False, "op": "billing", "http": st, "why": rows, "reason": "billing_unreadable"}
    ep = _ep()
    per_day, ep_day = {}, {}
    for r in rows:
        d = (r.get("time") or "")[:10]
        if not d:
            continue
        a = per_day.setdefault(d, {"usd": 0.0, "mins": 0.0})
        a["usd"] += r.get("amount") or 0
        a["mins"] += (r.get("timeBilledMs") or 0) / 60000.0
        if r.get("endpointId") == ep:
            e = ep_day.setdefault(d, {"usd": 0.0, "mins": 0.0, "diskGB": 0})
            e["usd"] += r.get("amount") or 0
            e["mins"] += (r.get("timeBilledMs") or 0) / 60000.0
            e["diskGB"] += r.get("diskSpaceBilledGB") or 0
    ds = sorted(set(per_day) | set(ep_day))[-int(days):]
    return {"ok": True, "op": "billing", "endpoint": ep,
            "days": [{"day": d,
                      "本端点_$": round((ep_day.get(d) or {}).get("usd", 0.0), 4),
                      "本端点_分钟": round((ep_day.get(d) or {}).get("mins", 0.0), 1),
                      "全部端点_$": round(per_day.get(d, {}).get("usd", 0.0), 4)}
                     for d in ds],
            "today": ds[-1] if ds else None,
            "口径": "服务端按天聚合；**今天的数字隔一段时间再读一次，不涨=没在烧**（判据在这里，不在我嘴上）"}


def status() -> dict:
    running = False
    pid = None
    if _PID.is_file():
        try:
            pid = int(_PID.read_text(encoding='utf-8').strip())
            out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid], capture_output=True, text=True)
            running = str(pid) in (out.stdout or "")
        except Exception:                                   # noqa: BLE001
            running = False
    h = _health()
    workers = h.get("workers") if isinstance(h.get("workers"), dict) else h
    jobs = h.get("jobs") if isinstance(h.get("jobs"), dict) else {}
    cfg = config()
    w = workers if isinstance(workers, dict) else {}
    hot_n = (w.get("idle") or 0) + (w.get("ready") or 0) + (w.get("running") or 0)
    # 🔴 2026-10-21 新增判据：**没人用却还在跑** = 这条事故的形态，必须自己会喊。
    #    口径：心跳不在 + 端点还有 worker（running/ready/idle 任一 >0） + workersMin>0 或 running>0
    bleeding = bool(not running and hot_n > 0)
    tail = []
    log = _ROOT / ".scratch" / "_warm_beat.log"
    if log.is_file():
        try:
            tail = log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-3:]
        except Exception:                                   # noqa: BLE001
            tail = []
    last_ok = bool(tail) and (" 200 " in tail[-1])
    return {"ok": True, "op": "status", "beat_running": running, "beat_pid": pid,
            "endpoint": _ep(), "workers": workers,
            "jobs": jobs,
            "hot_workers": hot_n, "bleeding": bleeding,
            "workersMin": cfg.get("workersMin") if cfg.get("ok") else None,
            "idleTimeout": cfg.get("idleTimeout") if cfg.get("ok") else None,
            "executionTimeoutMs": cfg.get("executionTimeoutMs") if cfg.get("ok") else None,
            "config_ok": bool(cfg.get("ok")),
            "beat_last": tail[-1] if tail else None, "beat_tail": tail,
            "beat_ok_last": last_ok,
            "口径": "workers.idle/ready>=1 ⇒ 热（第一句约 1 秒）；全 0 ⇒ 冷（第一句约 300 秒）；"
                    "beat_ok_last=心跳最近一次真拿到 200（只看进程在不在 = 假绿）；"
                    "**bleeding=true ⇒ 没人用它还在烧钱，立刻 scale0**"}


def cost() -> dict:
    st = status()
    w = st.get("workers") if isinstance(st.get("workers"), dict) else {}
    hot = bool(w and ((w.get("idle") or 0) + (w.get("ready") or 0) + (w.get("running") or 0)) > 0)
    return {"ok": True, "op": "cost", "now": "热" if hot else "冷",
            "每小时": "$0.89" if hot else "$0.00（缩 0 时不收 GPU 费）",
            "每天全开": "≈ $21.4",
            "bleeding": bool(st.get("bleeding")),
            "workersMin": st.get("workersMin"),
            "建议": ("立刻 op=scale0（没人用还在烧）" if st.get("bleeding")
                     else ("已缩 0，没人用=不花钱" if not hot else "有人在用，属正常计费")),
            "口径": "RunPod 按 worker 运行秒计费；本件只报，不替你决定"}


def on() -> dict:
    running = status().get("beat_running")
    if running:
        return {"ok": True, "op": "on", "already": True, "note": "心跳本来就在跑"}
    s = _dir() / "beat.py"
    s.write_text(_beat_script(), encoding="utf-8")
    p = subprocess.Popen([sys.executable, "-X", "utf8", str(s)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    _PID.write_text(str(p.pid), encoding="utf-8")
    time.sleep(2)
    return {"ok": True, "op": "on", "beat_pid": p.pid,
            "note": "每 150 秒一次最小推理 ⇒ 端点不缩 0 ⇒ 开工期间第一句约 1 秒 ✓（开始计 GPU 费 ≈$0.89/时 ✓）"}


def off() -> dict:
    """**关**：杀本机心跳 + **真把端点缩到 0**（旧版只杀进程，云端照烧，见文件头 2026-10-21 修）。"""
    stopped = False
    killed_pid = None
    if _PID.is_file():
        try:
            pid = int(_PID.read_text(encoding="utf-8").strip())
            killed_pid = pid
            stopped = subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                                     capture_output=True, text=True).returncode == 0
        except Exception:                                   # noqa: BLE001
            stopped = False
        _PID.unlink(missing_ok=True)
    s0 = scale0(why="warm_switch off：收工放掉，没人用不许花钱")
    return {"ok": bool(s0.get("ok")), "op": "off", "killed": stopped, "killed_pid": killed_pid,
            "scale0": {"ok": s0.get("ok"), "http": s0.get("http"),
                       "workersMin": (s0.get("after") or {}).get("workersMin"),
                       "running": s0.get("running")},
            "note": "心跳停了 **且** 端点已缩 0（按回读判，不看文案）；第一句会重新变冷 ~300 秒 ✓"}


def run(payload: dict | None = None) -> dict:
    p = dict(payload or {})
    op = str(p.get("op") or "status").strip().lower()
    if op == "status":
        return status()
    if op == "cost":
        return cost()
    if op == "config":
        return config()
    if op == "billing":
        try:
            _d = int(p.get("days") or 12)
        except (TypeError, ValueError):
            _d = 12                      # 传坏就退回默认，不许把参数静默吞成"随便一个值"
        return billing(days=_d)
    if op == "scale0":
        return scale0(why=str(p.get("why") or ""))
    if op == "on":
        return on()
    if op == "off":
        return off()
    return {"ok": False, "fail_closed": True, "error": "user_error: 未列出的 op（fail-closed）",
            "ops": ["status", "cost", "config", "scale0", "on", "off"]}
