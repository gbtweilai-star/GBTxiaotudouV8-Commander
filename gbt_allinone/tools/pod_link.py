# gbt-capability: pod_link
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""pod_link —— **云卡触手**（本机 ⇄ 租来的 GPU 卡：来回传文件 · 在卡上跑命令 · 看状态）。

## 来历（主人令：「把触手GPU-CPU传输让她学会不要每次都要我提醒」）

之前每次上云都要**现写临时脚本**（`.scratch/_up_lora.py` / `_dl_lora.py`），
还要主人提醒才想起来 —— 那就不是器官，是**一次性的手工活**。本件把它做成**一根触手**：

    status → 卡上现在有什么、多少钱、连不连得上（读）
    ls     → 卡上某个目录里有什么（读）
    up     → **本机 → 卡**（字节级，回读对账 sha256）
    down   → **卡 → 本机**（字节级，回读对账 sha256）
    run    → **在卡上跑一段 Python**（JupyterLab 内核通道 · WebSocket）

## 走的路（现成的两条，不新造）

- **文件**：JupyterLab HTTP —— `PUT /api/contents/<path>`（base64，任何文件都行）· `GET /files/<path>` 取回
- **命令**：JupyterLab **内核通道** —— `POST /api/kernels` 建核 + `wss://…/api/kernels/<id>/channels` 发 `execute_request`
- **卡在哪**：RunPod REST（`/v1/pods`）现读 —— 钥匙取 `GBT_RUNPOD_API_KEY` 或 `.scratch/.runpod_key`

## 铁律

1. **令牌一律不回显**：只报「已配/未配」；pod 的 `JUPYTER_PASSWORD` 从 API 现读、**不打进任何返回**。
2. **传完必须回读对账**（`sha256` 两头比）—— 不许拿"完成"文案当成功。
3. **不替人做花钱决定**：创建/开关卡（`create` / `start` / `stop`）是**花钱动作** ——
   一律**必须**带 `confirm="主人已授权"`，缺 confirm 当场 fail-closed（`need_owner_confirm`）；
   **AI 无权自放行**。`gpus` 是只读列卡。
   （2026-10-17 补正：本文档此前写「不创建、不删除、不重启」，与同文件的
   `start/stop/create` 实现**自相矛盾**；实际是主人令 2026-10-16 加了这三个 op 并上了
   owner-confirm 闸。现按**代码实况 + 人闸**如实改写，供 `test_pod_link` 逐条咬。）
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_OPS = ("status", "ls", "up", "down", "run", "where", "start", "stop", "gpus", "create", "account", "logs", "ports")
_API = "https://rest.runpod.io/v1"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")


def _key() -> str:
    """钥匙：先环境变量，再仓内 `.scratch/.runpod_key`（**只报已配/未配，不回显**）。"""
    k = (os.environ.get("GBT_RUNPOD_API_KEY") or "").strip()
    if k:
        return k
    p = _ROOT / ".scratch" / ".runpod_key"
    return p.read_text(encoding="utf-8").strip() if p.is_file() else ""


def _pods() -> list:
    k = _key()
    if not k:
        return []
    r = urllib.request.Request(_API + "/pods", headers={"Authorization": "Bearer " + k,
                                                        "User-Agent": _UA})
    return json.loads(urllib.request.urlopen(r, timeout=30).read().decode())


def _pick(pod: str = "", require_running: bool = True) -> dict:
    """选卡：显式给 → `GBT_POD_ID` → `.scratch/.pod_id` → 第一条 RUNNING。

    🔴 2026-10-20 修（**实测踩到，血的教训**）：显式点名一张 **EXITED** 的卡时，旧逻辑 `break` 之后
       回落到「第一条 RUNNING」—— 于是 `start` 想唤醒 4090，实际给**正在跑的训练卡** `gbt-v8-v82x`
       发了 resume（HTTP 200 空操作，幸好它在 RUNNING）。「点名 A 却动了 B」是最坏的一类读数错误。
       ⇒ 现口径：**点名且找到，就按点名的来**；只有「点名但要求活卡而它没活」才回落，且回落要在回执里留痕。
    """
    want = str(pod or os.environ.get("GBT_POD_ID") or "").strip()
    if not want:
        p = _ROOT / ".scratch" / ".pod_id"
        want = p.read_text(encoding="utf-8").strip() if p.is_file() else ""
    pods = _pods()
    if want:
        for x in pods:
            if x.get("id") == want:
                if x.get("desiredStatus") == "RUNNING" or not require_running:
                    return x
                # 2026-10-17 的教训仍有效：过期指针指向 EXITED 卡会让 run/down 假失败（Jupyter 404）
                fb = next((y for y in pods if y.get("desiredStatus") == "RUNNING"), None)
                if fb:
                    fb = dict(fb)
                    fb["_picked_fallback"] = "点名的 %s 不是 RUNNING，按活卡回落" % want
                    return fb
                return {}
        return {}                      # 点名却没这张卡：不回落到别的卡（点名不许被悄悄改）
    for x in pods:
        if x.get("desiredStatus") == "RUNNING":
            return x
    return {} if require_running else (pods[0] if pods else {})


def _base(p: dict) -> tuple:
    """(JupyterLab base url, token) —— token 只在这里活着，不进任何返回。"""
    pid = p.get("id") or ""
    tok = (p.get("env") or {}).get("JUPYTER_PASSWORD") or ""
    return ("https://%s-8888.proxy.runpod.net" % pid, tok)


def _req(url: str, method: str = "GET", body: bytes | None = None,
         ctype: str = "application/json", timeout: int = 120) -> tuple:
    r = urllib.request.Request(url, method=method, data=body,
                               headers={"User-Agent": _UA, "Content-Type": ctype,
                                        "Accept": "application/json",
                                        # 2026-10-16 实测修：原来**没带 Authorization** ⇒ 模块所有写调用（create/start/stop）被 RunPod 回 401，
                                        #   而直连能成（create 201 / start 500 容量）—— 这是“模块报假错”的根源。
                                        "Authorization": ("Bearer " + _key()) if _key() else ""})
    try:
        resp = urllib.request.urlopen(r, timeout=timeout, context=ssl.create_default_context())
        return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


def _q(base: str, path: str, tok: str) -> str:
    return base + path + ("?token=" + urllib.parse.quote(tok) if tok else "")


_GQL = "https://api.runpod.io/graphql"
_GQL_GPUS = ("query { gpuTypes { id displayName memoryInGb communityCloud secureCloud "
             "communityPrice securePrice } }")


def _graphql(query: str) -> dict:
    """查 RunPod **GraphQL**（REST v1 没有 /gpus 这条路，2026-10-20 实测 400 原文见账）。

    返回值一律 `{"ok": bool, "data"/"why": ...}`，**取不到就带原始载荷**（P19：不许只说"失败"）。
    """
    body = json.dumps({"query": query}).encode()
    st, b = _req(_GQL, method="POST", body=body)
    raw = (b or b"").decode("utf-8", "replace")
    if not (st and 200 <= st < 300):
        return {"ok": False, "http": st, "why": raw[:300]}
    try:
        j = json.loads(raw)
    except ValueError:
        return {"ok": False, "http": st, "why": "not_json: " + raw[:200]}
    if j.get("errors"):
        return {"ok": False, "http": st, "why": json.dumps(j["errors"], ensure_ascii=False)[:300]}
    return {"ok": True, "data": j.get("data") or {}, "http": st}


def _gpu_rows() -> dict:
    """现读可选 GPU 型与价（GraphQL）。**只把报了价的算"可选"**：没价 = 该池没货，不许当 0 元。"""
    g = _graphql(_GQL_GPUS)
    if not g.get("ok"):
        return {"ok": False, "reason": "graphql_unreadable", "why": g.get("why"), "http": g.get("http")}
    items = ((g.get("data") or {}).get("gpuTypes") or [])
    if not items:
        return {"ok": False, "reason": "empty_gpuTypes", "raw_keys": []}
    rows = []
    for t in items:
        cp = t.get("communityPrice")
        sp = t.get("securePrice")
        if cp in (None, 0) and sp in (None, 0):
            continue                      # 两个池都没报��� ⇒ 当前不可选（不是"免费"）
        rows.append({"id": t.get("id"), "name": t.get("displayName") or t.get("id"),
                     "显存G": t.get("memoryInGb"), "社区价": cp, "安全价": sp})
    rows.sort(key=lambda x: (x.get("社区价") if x.get("社区价") not in (None, 0) else 9e9))
    return {"ok": bool(rows), "count": len(rows), "rows": rows,
            "总类型数": len(items),
            "_口径": "只列报了价的（没价=该池没货）；社区价升序"}


def status(pod: str = "", **_kw) -> dict:
    """**读**：卡清单（id/状态/价/卷/端口）+ 钥匙是否已配 + 目标卡的 Jupyter 通不通。"""
    key_ok = bool(_key())
    if not key_ok:
        return {"ok": False, "status": "needs_key",
                "note": "没配卡钥匙 ⇒ 放 `GBT_RUNPOD_API_KEY` 或 `.scratch/.runpod_key`（只报已配/未配）"}
    pods = _pods()
    # 2026-10-16 主人令「开炉选社区卡」：**云属（社区/安全）必须呈出来** —— 不呈现就无法选。
    rows = [{"id": p.get("id"), "name": p.get("name"), "状态": p.get("desiredStatus"),
             "云": p.get("cloudType") or (p.get("machine") or {}).get("cloudType"),
             "GPU": p.get("gpuTypeId") or (p.get("machine") or {}).get("gpuTypeId"),
             "$/h": p.get("costPerHr"), "卷": p.get("networkVolumeId"),
             "盘G": p.get("containerDiskInGb"), "端口": p.get("portMappings") or {},
             "公网IP": p.get("publicIp"),
             "img": (p.get("imageName") or "").split(":")[0].split("/")[-1],
             "机": (p.get("machine") or {})} for p in pods]
    tgt = _pick(pod)
    jup = None
    if tgt:
        base, tok = _base(tgt)
        st, b = _req(_q(base, "/api/status", tok), timeout=25)
        jup = {"http": st, "body": (b or b"")[:120].decode("utf-8", "replace") if st == 200 else ""}
    return {"ok": True, "op": "status", "kind": "pod_link", "key_configured": True,
            "pods": rows, "pod_count": len(rows),
            "_原始键": sorted((pods[0] or {}).keys()) if pods else [],
            "目标卡": tgt.get("id"), "jupyter": jup, "ops": list(_OPS),
            "_口径": "只读；token 取卡 env 的 JUPYTER_PASSWORD，**永不出现在返回里**"}


def ls(path: str = "/", pod: str = "", **_kw) -> dict:
    """**读**：列卡上某个目录。"""
    tgt = _pick(pod)
    if not tgt:
        return {"ok": False, "status": "no_pod", "error": "没选到卡"}
    base, tok = _base(tgt)
    st, b = _req(_q(base, "/api/contents/" + path.strip("/"), tok), timeout=40)
    if st != 200:
        return {"ok": False, "http": st, "error": b[:200].decode("utf-8", "replace")}
    d = json.loads(b)
    items = [{"name": x.get("name"), "type": x.get("type"), "bytes": x.get("size")}
             for x in (d.get("content") or [])]
    return {"ok": True, "op": "ls", "pod": tgt.get("id"), "path": path, "count": len(items),
            "items": items[:200]}


def up(local: str = "", remote: str = "", pod: str = "", **_kw) -> dict:
    """**本机 → 卡**：字节级上传（base64），**传完回读对账 sha256**。"""
    if not local or not remote:
        return {"ok": False, "fail_closed": True, "error": "要 local（本机文件）与 remote（卡上路径）"}
    src = Path(local)
    if not src.is_absolute():
        src = _ROOT / src
    if not src.is_file():
        return {"ok": False, "status": "not_found", "error": "本机没有：%s" % local}
    raw = src.read_bytes()
    tgt = _pick(pod)
    if not tgt:
        return {"ok": False, "status": "no_pod", "error": "没选到卡"}
    base, tok = _base(tgt)
    payload = json.dumps({"type": "file", "format": "base64",
                          "content": base64.b64encode(raw).decode()}).encode()
    st, b = _req(_q(base, "/api/contents/" + remote.strip("/"), tok), "PUT", payload, timeout=300)
    if st not in (200, 201):
        return {"ok": False, "http": st, "error": b[:220].decode("utf-8", "replace")}
    # 🔴 回读对账（不许拿"完成"文案当成功）
    st2, back = _req(_q(base, "/files/" + remote.strip("/"), tok), timeout=300)
    ok = (st2 == 200 and _sha(back) == _sha(raw) and len(back) == len(raw))
    return {"ok": ok, "op": "up", "pod": tgt.get("id"), "local": str(src.relative_to(_ROOT))
            if src.is_relative_to(_ROOT) else str(src), "remote": remote,
            "bytes": len(raw), "sha256_16": _sha(raw), "回读": {"http": st2, "bytes": len(back),
            "sha256_16": _sha(back)}, "_口径": "回读哈希一致才算成；不一致 ⇒ ok=false（不许念成成功）"}


def down(remote: str = "", local: str = "", pod: str = "", **_kw) -> dict:
    """**卡 → 本机**：字节级取回（`/files`），落盘后**对账 sha256**。"""
    if not remote or not local:
        return {"ok": False, "fail_closed": True, "error": "要 remote 与 local"}
    tgt = _pick(pod)
    if not tgt:
        return {"ok": False, "status": "no_pod", "error": "没选到卡"}
    base, tok = _base(tgt)
    st, b = _req(_q(base, "/files/" + remote.strip("/"), tok), timeout=600)
    if st != 200:
        return {"ok": False, "http": st, "error": b[:220].decode("utf-8", "replace")}
    dst = Path(local)
    if not dst.is_absolute():
        dst = _ROOT / dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(b)
    back = dst.read_bytes()
    ok = _sha(back) == _sha(b) and len(back) == len(b)
    return {"ok": ok, "op": "down", "pod": tgt.get("id"), "remote": remote,
            "local": str(dst.relative_to(_ROOT)) if dst.is_relative_to(_ROOT) else str(dst),
            "bytes": len(b), "sha256_16": _sha(b), "落盘": {"bytes": len(back), "sha256_16": _sha(back)}}


def run(code: str = "", path: str = "", timeout: int = 300, pod: str = "", **_kw) -> dict:
    if str(_kw.get("confirm") or "").strip() not in ("主人已授权", "owner_ok", "yes"):
        return {"ok": False, "reason": "need_owner_confirm",
                "how": "2026-10-16 主人令：执行类动作必须带确认；payload 加 confirm：主人已授权"}

    """**在卡上跑一段 Python**（JupyterLab 内核通道）。`path` 给本机 .py 文件则读它；其余见下文。"""
    if path and not code:
        p = Path(path)
        if not p.is_absolute():
            p = _ROOT / p
        if not p.is_file():
            return {"ok": False, "status": "not_found", "error": "本机没有：%s" % path}
        code = p.read_text(encoding="utf-8")
    if not code:
        return {"ok": False, "fail_closed": True, "error": "要 code 或 path"}
    tgt = _pick(pod)
    if not tgt:
        return {"ok": False, "status": "no_pod", "error": "没选到卡"}
    base, tok = _base(tgt)
    # ── 建 kernel：**重试 3 次**（2026-10-20 实测：RunPod 代理刚起时 POST /api/kernels 会慢/抖）
    st, b, kid, tries = 0, b"", None, []
    for i in range(3):
        st, b = _req(_q(base, "/api/kernels", tok), "POST",
                     json.dumps({"name": "python3"}).encode(), timeout=90)
        try:
            kid = (json.loads(b) or {}).get("id")
        except Exception:                                       # noqa: BLE001
            kid = None
        tries.append({"try": i + 1, "http": st, "kernel": kid,
                      "raw": (b or b"")[:120].decode("utf-8", "replace")})
        if st in (200, 201) and kid:
            break
        time.sleep(3 * (i + 1))
    if not kid:
        return {"ok": False, "status": "kernel_create_failed", "attempts": tries,
                "_口径": "三次都没拿到 kernel id ⇒ 通道侧问题（不是脚本问题）"}
    try:
        import websocket                                        # websocket-client
    except Exception:                                           # noqa: BLE001
        return {"ok": False, "status": "needs_dependency", "missing": ["websocket-client"],
                "note": "在卡上跑命令要 WebSocket：`py -3.14 -m pip install websocket-client`"}
    ws_url = "wss://%s-8888.proxy.runpod.net/api/kernels/%s/channels%s" % (
        tgt.get("id"), kid, ("?token=" + urllib.parse.quote(tok)) if tok else "")
    mid = "gbt-%d" % int(time.time() * 1000)
    out, t0 = [], time.time()
    # ── 连 WebSocket：**连接超时 30s 太短**（2026-10-20 实测两次都是 30.1s 超时、卡上日志零增长），
    #    改成可配置 + 最多试 3 次（指数退避）。总等待仍受 timeout 约束。
    #    2026-10-20 第三次实测：RunPod 代理会**丢掉 URL 上的 ?token=**，握手直接 404（不是 403），
    #    所以除了 query 还要备一条 **header 带 token** 的路（Jupyter 两种都认），先 query 后 header。
    conn_to = int(_kw.get("ws_timeout") or 90)
    ws, last_err = None, ""
    variants = [("query", ws_url)]
    if tok:
        variants.append(("header", "wss://%s-8888.proxy.runpod.net/api/kernels/%s/channels"
                         % (tgt.get("id"), kid)))
    for how, url in variants:
        hdr = ["Authorization: token %s" % tok] if (how == "header" and tok) else None
        for i in range(3):
            try:
                ws = websocket.create_connection(url, timeout=conn_to, header=hdr)
                break
            except Exception as e:                              # noqa: BLE001
                last_err = "%s[%s]: %s" % (type(e).__name__, how, str(e)[:140])
                time.sleep(2 * (i + 1))
        if ws is not None:
            break
    if ws is None:
        return {"ok": False, "status": "ws_connect_failed", "ws_timeout": conn_to, "tries": 3,
                "error": last_err, "kernel": kid, "variants": [v[0] for v in variants],
                "_口径": "连不上内核通道；卡是活的（HTTP 200）但 wss 不通 —— 通道侧问题"}
    try:
        ws.send(json.dumps({
            "header": {"msg_id": mid, "username": "gbt", "session": "gbt",
                       "msg_type": "execute_request", "version": "5.3"},
            "parent_header": {}, "metadata": {},
            "content": {"code": code, "silent": False, "store_history": False,
                        "user_expressions": {}, "allow_stdin": False}, "channel": "shell"}))
        while time.time() - t0 < int(timeout):
            m = json.loads(ws.recv())
            t = (m.get("header") or {}).get("msg_type")
            c = m.get("content") or {}
            if t == "stream":
                out.append(c.get("text") or "")
            elif t in ("execute_result", "display_data"):
                out.append((c.get("data") or {}).get("text/plain") or "")
            elif t == "error":
                out.append("ERROR %s: %s" % (c.get("ename"), c.get("evalue")))
            elif t == "status" and c.get("execution_state") == "idle" \
                    and (m.get("parent_header") or {}).get("msg_id") == mid:
                break
        ws.close()
    except Exception as e:                                      # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:160]),
                "seconds": round(time.time() - t0, 1), "out": "".join(out)[:2000]}
    finally:
        _req(_q(base, "/api/kernels/" + str(kid), tok), "DELETE", None, timeout=30)
    return {"ok": True, "op": "run", "pod": tgt.get("id"), "seconds": round(time.time() - t0, 1),
            "out": "".join(out)[-4000:], "chars": sum(len(x) for x in out)}


def start(pod: str = "", confirm: str = "", **_kw) -> dict:
    """**开卡（resume）**：把 EXITED 的卡唤醒 —— 花钱动作，必须带 confirm=「主人已授权」。

    2026-10-16 实测踩过：原来不看 HTTP 状态码 ⇒ 401 也返回 ok:true（**空的成功**）。
    本仓铁律「顶层 status:ok ≠ 本体 ok:true」—— 现在 **fail-closed**。
    """
    if confirm not in ("主人已授权", "owner_ok", "yes"):
        return {"ok": False, "reason": "need_owner_confirm",
                "how": 'payload 里带 confirm: "主人已授权"（主人当轮点头后才能给）'}
    tgt = _pick(pod, require_running=False)
    if not tgt:
        return {"ok": False, "reason": "pod_not_found", "pod": pod,
                "_口径": "点名却没这张卡就如实报缺，不回落到别的卡（2026-10-20 修）"}
    pid = tgt.get("id")
    before = tgt.get("状态") or tgt.get("desiredStatus") or ""
    if before == "RUNNING":
        # 2026-10-20 加：已经 RUNNING 就不发 resume —— 这一步就是为了不让「点名要唤醒 A」变成
        # 「给正在跑的 B 发一次空 resume」。空操作也是动别人的卡，账上说不清。
        return {"ok": True, "op": "start", "pod": pid, "name": tgt.get("name"), "before": before,
                "skipped": "already_running", "_口径": "已在 RUNNING，没发 resume（不是失败）"}
    try:
        st, b = _req(_API + "/pods/" + str(pid) + "/start", method="POST", body=b"{}")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": "start_failed", "pod": pid, "before": before,
                "err": type(e).__name__ + ": " + str(e)[:160]}
    if not (st and 200 <= st < 300):
        return {"ok": False, "op": "start", "pod": pid, "before": before, "http": st,
                "reason": "start_rejected_by_api",
                "raw": (b or b"")[:200].decode("utf-8", "replace"),
                "_口径": "看 http；非 2xx 一律不算成功"}
    return {"ok": True, "op": "start", "pod": pid, "name": tgt.get("name"), "before": before, "http": st,
            "价": tgt.get("$/h"),
            "note": "已发 resume（HTTP 2xx）；卡在起（Jupyter 要等 30~90s），用 op=status 复查 200"}
def stop(pod: str = "", confirm: str = "", **_kw) -> dict:
    """**关卡（stop）**：把在跑的卡关掉不再烧 GPU 费 —— 写操作，必须带 confirm=「主人已授权」。

    为什么要有这个 op：主人令「换新卡记得关旧的别浪费钱」——
    以前关卡只能直接打 API（绕门、无审计）；现在它是能力位里的一个 op。
    读数只认 HTTP：非 2xx 一律不算成功。
    """
    if confirm not in ("主人已授权", "owner_ok", "yes"):
        return {"ok": False, "reason": "need_owner_confirm",
                "how": 'payload 带 confirm: "主人已授权"'}
    tgt = _pick(pod)
    if not tgt:
        return {"ok": False, "reason": "pod_not_found", "pod": pod}
    pid = str(tgt.get("id") or "")
    before = tgt.get("状态") or tgt.get("desiredStatus") or ""
    try:
        st, b = _req(_API + "/pods/" + pid + "/stop", method="POST", body=b"{}")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": "stop_failed", "pod": pid, "err": type(e).__name__ + ": " + str(e)[:160]}
    if not (st and 200 <= st < 300):
        return {"ok": False, "op": "stop", "pod": pid, "before": before, "http": st,
                "reason": "stop_rejected_by_api", "raw": (b or b"")[:200].decode("utf-8", "replace")}
    return {"ok": True, "op": "stop", "pod": pid, "name": tgt.get("name"), "before": before, "http": st,
            "note": "已发 stop（HTTP 2xx）；稍后用 op=status 复查状态=E XITED"}

def gpus(**_kw) -> dict:
    """**读**：现役可选的 GPU 型与价钱（走 GraphQL；REST v1 没有 /gpus 这条路）。

    2026-10-20 修（**实测踩到**）：原实现打 `GET https://rest.runpod.io/v1/gpus`，RunPod 回
    **400 + OpenAPI 原文「that path ... does not exist in the specification」** —— 所以
    "让它自己挑一张有货的卡"这条路**从来没通过**（`create` 不点名 GPU 必报 no_community_gpu_readable）。
    现口径：改走 GraphQL `gpuTypes`；只把**报了价的**算可选（没价 = 该池当下没货，不许当 0 元/免费）；
    取不到 fail-closed 并带原始载荷（P19）。
    """
    if not _key():
        return {"ok": False, "status": "needs_key"}
    r = _gpu_rows()
    if not r.get("ok"):
        return {"ok": False, "op": "gpus", "status": "unreadable",
                "why": r.get("why"), "reason": r.get("reason"),
                "_口径": "取不到就写未读到 —— 不许拿空当读数"}
    return {"ok": True, "op": "gpus", "count": r["count"], "gpus": r["rows"][:40],
            "_口径": r["_口径"]}


def _pick_gpu(prefer: str = "", n: int = 4) -> dict:
    """**选卡**：先看 `prefer`（主人点名的型号，例如 4090 前缀匹配），再按社区价从低到高补齐。

    返回 `cands`（按尝试顺序）；`create` 会**在同一个门调用里**逐张试到有货为止 ——
    「社区池没库存」不该反复要票。
    """
    r = _gpu_rows()
    if not r.get("ok"):
        return {"ok": False, "reason": r.get("reason"), "why": r.get("why")}
    rows = r["rows"]
    ordered = []
    if prefer:
        key = str(prefer).lower()
        ordered += [x for x in rows if key in str(x.get("id", "")).lower()]
    ordered += [x for x in rows if x not in ordered]
    return {"ok": bool(ordered), "count": len(ordered), "cands": ordered[:max(1, n)],
            "picked": ordered[0] if ordered else None, "top": rows[:6]}


def create(name: str = "", gpu: str = "", image: str = "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04",
           volume: str = "", disk: int = 40, ports: str = "8888/http,22/tcp",
           cloud: str = "COMMUNITY", confirm: str = "", start_cmd="", gpu_try=None,
           prefer_gpu: str = "", try_n: int = 4, **_kw) -> dict:
    """**新建一张卡**（默认**社区云** COMMUNITY）—— 花钱动作，必须带 confirm=\u300c\u4e3b\u4eba\u5df2\u6388\u6743\u300d\u3002"""
    if confirm not in ("\u4e3b\u4eba\u5df2\u6388\u6743", "owner_ok", "yes"):
        return {"ok": False, "reason": "need_owner_confirm",
                "how": 'payload \u5e26 confirm: "\u4e3b\u4eba\u5df2\u6388\u6743"',
                "_\u94c1\u5f8b": "\u5efa\u5361\u662f\u82b1\u94b1\u52a8\u4f5c\uff1b\u4e3b\u4eba 2026-10-16 \u4ee4\u300c\u5f00\u7089\u9009\u793e\u533a\u5361\u300d\u5373\u4e3a\u6b64\u6b21\u6388\u6743"}
    # 候选次序：显式 gpu_try 列表 > 主人点名的型号(prefer_gpu) + 社区价补齐 > 只点名 gpu
    cands = []
    if isinstance(gpu_try, (list, tuple)) and gpu_try:
        cands = [{"id": str(x), "来源": "调用方给的 gpu_try"} for x in gpu_try]
    elif gpu:
        cands = [{"id": gpu, "来源": "主人指定"}]
    if not cands:
        pick = _pick_gpu(prefer=prefer_gpu, n=try_n)
        if not pick.get("ok"):
            return {"ok": False, "reason": "no_gpu_list_readable", "pick": pick,
                    "_口径": "库存表读不到 ≠ 没货（P1）"}
        cands = [dict(x, 来源="社区价升序/点名优先") for x in pick["cands"]]
    attempts = []
    picked_info = cands[0]
    import secrets as _secrets   # 2026-10-16 实测踩过：建卡不带 JUPYTER_PASSWORD ⇒ Jupyter 不起（404），无法传文件/跑命令
    _env = dict(_kw.get("env") or {}) if isinstance(_kw.get("env"), dict) else {}
    _env.setdefault("JUPYTER_PASSWORD", _secrets.token_urlsafe(18))
    body = {"name": name or "gbt-v8-train-v26", "imageName": image, "gpuTypeIds": [gpu],
            "env": _env,
            "gpuCount": 1, "cloudType": (cloud or "COMMUNITY").upper(),
            "containerDiskInGb": int(disk),
            "ports": [x.strip() for x in str(ports).split(",") if x.strip()], "volumeInGb": 0, "volumeMountPath": "/workspace"}
    if volume:
        body["networkVolumeId"] = volume
    # 2026-10-17: devel 镜像不自带 Jupyter ⇒ 支持 start_cmd 拉起（与历史模板卡等价）
    if start_cmd:
        body["dockerStartCmd"] = (start_cmd if isinstance(start_cmd, list) else [str(start_cmd)])
    # 逐张试：社区池"没库存"是常态（no instances currently available），不该一次失败就整轮要票
    st, b, j = 0, b"", {}
    for cand in cands:
        body["gpuTypeIds"] = [cand.get("id")]
        st, b = _req(_API + "/pods", method="POST", body=json.dumps(body).encode())
        try:
            j = json.loads((b or b"{}").decode())
        except ValueError:
            j = {}
        attempts.append({"gpu": cand.get("id"), "来源": cand.get("来源"), "http": st,
                         "pod": (j or {}).get("id"),
                         "raw": (b or b"")[:160].decode("utf-8", "replace")})
        if st and 200 <= st < 300 and (j or {}).get("id"):
            picked_info = cand
            break
    return {"attempts": attempts, "tried": len(attempts),
            "ok": bool(st and 200 <= st < 300 and (j or {}).get("id")), "op": "create", "http": st, "cloud": body["cloudType"],
            "env_keys": sorted(_env.keys()),
            "picked": picked_info,
            "pod": j.get("id"), "name": j.get("name"), "gpu": gpu,
            "note": "\u5df2\u53d1\u5efa\u5361\uff1b\u8d77\u6765\u540e\u7528 op=status \u770b Jupyter 200\uff0c\u518d up \u8bed\u6599 + run \u8bad\u7ec3" if st and 200 <= st < 300 else "\u5efa\u5361\u672a\u6210\u529f\uff0c\u770b http/\u56de\u5305",
            "raw": (b or b"")[:200].decode("utf-8", "replace")}

def ports(pod: str = "", **_kw) -> dict:
    """**读端口映射**（GraphQL pod.runtime.ports）—— SSH 到底连哪个地址就靠这张表。

    为什么必须有这一件：REST v1 的 pod 对象里 ports/publicIp 全是空，
    而 ssh.runpod.io 的用户名要 <podId>-<公网端口>，端口只能从 runtime.ports 里读。
    """
    tgt = _pick(pod, require_running=False)
    pid = (tgt.get("id") if tgt else "") or str(pod or "")
    if not pid:
        return {"ok": False, "op": "ports", "error": "没给 pod id"}
    q = ('query { pod(input: {podId: "%s"}) { id name runtime { ports { ip publicPort '
         'privatePort type isIpPublic } } } }')
    g = _graphql(q % pid)
    if not g.get("ok"):
        return {"ok": False, "op": "ports", "pod": pid, "status": "unreadable", "why": g.get("why")}
    d = (g.get("data") or {}).get("pod") or {}
    rt = (d.get("runtime") or {})
    rows = rt.get("ports") or []
    if not rows:
        return {"ok": False, "op": "ports", "pod": pid, "status": "empty_ports",
                "raw": json.dumps(d, ensure_ascii=False)[:400]}
    return {"ok": True, "op": "ports", "pod": pid, "ports": rows,
            "ssh_hint": ["%s-%s@ssh.runpod.io" % (pid, r.get("publicPort"))
                          for r in rows if str(r.get("privatePort")) == "22"]}


def logs(pod: str = "", tail: int = 40, **_kw) -> dict:
    """**读卡上容器日志**：GraphQL 字段名不写死，几种形状都试一遍（写死一个错的等于没这个口）。

    2026-10-20 实测：podLogs 在 Query 上**不存在**（GraphQL 原文 Cannot query field "podLogs" on type "Query"），
    所以这里按候选逐个试，谁通就用谁，并把每次的原文一起带回来（P19：拒绝路径要带上游原话）。
    """
    tgt = _pick(pod, require_running=False)
    pid = (tgt.get("id") if tgt else "") or str(pod or "")
    if not pid:
        return {"ok": False, "op": "logs", "error": "没给 pod id"}
    tries = []
    for name, q in (
        ("podLogs", 'query { podLogs(input: {podId: "%s"}) }'),
        ("pod.logs", 'query { pod(input: {podId: "%s"}) { id name logs } }'),
        ("pod.runtime.logs", 'query { pod(input: {podId: "%s"}) { runtime { logs } } }'),
    ):
        g = _graphql(q % pid)
        if not g.get("ok"):
            tries.append({"shape": name, "why": (g.get("why") or "")[:120]})
            continue
        d = g.get("data") or {}
        txt = d.get("podLogs")
        if txt is None and isinstance(d.get("pod"), dict):
            txt = d["pod"].get("logs") or ((d["pod"].get("runtime") or {}).get("logs"))
        if not txt:
            tries.append({"shape": name, "why": "通了但没内容"})
            continue
        lines = str(txt).splitlines()
        return {"ok": True, "op": "logs", "pod": pid, "shape": name, "lines": len(lines),
                "tail": "\n".join(lines[-int(tail):])[-6000:]}
    return {"ok": False, "op": "logs", "pod": pid, "status": "no_logs_field", "tries": tries}


def account(**_kw) -> dict:
    """**读**：账户余额与当前速率（GraphQL myself）—— 主人问过「充了 20 美金显示 0」，
    这一发就是为那句问话开的只读口。**读不到就说读不到**，不许拿 0 当余额。"""
    if not _key():
        return {"ok": False, "status": "needs_key"}
    g = _graphql("query { myself { clientBalance currentSpendPerHr } }")
    if not g.get("ok"):
        return {"ok": False, "op": "account", "status": "unreadable", "why": g.get("why")}
    me = ((g.get("data") or {}).get("myself") or {})
    if not me:
        return {"ok": False, "op": "account", "status": "empty_myself", "data": g.get("data")}
    return {"ok": True, "op": "account", "balance_usd": me.get("clientBalance"),
            "spend_per_hr": me.get("currentSpendPerHr"),
            "_口径": "GraphQL myself；null = 没这个字段，不是 0"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "pod_link",
            "entry": "run_task('pod_link', {'op':'up','local':'x.jsonl','remote':'/workspace/data/x.jsonl'})",
            "ops": list(_OPS),
            "what": "**云卡触手**：本机 ⇄ GPU 卡（传文件 · 在卡上跑命令 · 看状态）",
            "走的路": {"文件": "JupyterLab HTTP（PUT /api/contents base64 · GET /files）",
                       "命令": "JupyterLab 内核通道（POST /api/kernels + wss execute_request）",
                       "卡在哪": "RunPod REST /v1/pods（钥匙取 GBT_RUNPOD_API_KEY 或 .scratch/.runpod_key）"},
            "hard_rules": ["令牌不回显（只报已配/未配）；卡的 JUPYTER_PASSWORD 只在本件内部用",
                           "**传完回读对账 sha256**，不一致一律 ok=false",
                           "**创建/开关卡（create/start/stop）是花钱动作**：必须 "
                           "`confirm=\"主人已授权\"`，缺则 fail-closed —— **AI 无权自放行**"],
            "作用域": {"status/ls/down/where": "零（公网读）", "up": "filesystem_write + data_export",
                       "run": "process_execute",
                       "start/stop/create": "人闸：confirm=「主人已授权」（policy 未挂新作用域；要挂须主人批）",
                       "未知名": "fail-closed（挂满三项）"}}


def run_dispatch(op: str = "status", **params) -> dict:
    op = str(op or "status").lower()
    for nm, fn in (("status", status), ("ls", ls), ("up", up), ("down", down), ("start", start), ("stop", stop), ("gpus", gpus), ("create", create), ("account", account), ("logs", logs), ("ports", ports),
                   ("run", run), ("where", where)):
        if op == nm:
            return fn(**params)
    return {"ok": False, "fail_closed": True, "error": "未知 op：%s" % op, "ops": list(_OPS)}


if __name__ == "__main__":                                   # 主人的终端入口
    import argparse
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                                    # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="云卡触手（本机 ⇄ GPU 卡）")
    ap.add_argument("cmd", nargs="?", default="status")
    ap.add_argument("--json", default="{}")
    a = ap.parse_args()
    print(json.dumps(run_dispatch(a.cmd, **json.loads(a.json or "{}")), ensure_ascii=False, indent=1))

# 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
