# -*- coding: utf-8 -*-
"""四根电缆一次接满：出片 + 批量出图 + 本机 CPU 基准 + 我们的模型（云端算力），各带产物 sha256 与耗时。

电缆模型（主人 2026-10-21 口径）：**触手=电缆 · 密钥=通电 · 云端有算力就能通 · 能通就能反向调用**。

四根：
  ① 我们的模型 —— agnes-2.5-flash 走云端算力（只需钥，不需要连云卡）
  ② 批量出图 —— agnes-image-2.5-flash ×N → 逐张落 png，记每张 sha256/耗时
  ③ 本机 CPU —— numpy float32 matmul（裸算力，零模型零出网）→ GFLOP/s/耗时
  ④ 出片   —— agnes-video-2.5-flash（视频算力）→ 提交任务+轮询+取片，落 mp4

失败也记：端点/参数/上游原话全留，不粉饰。
产物：outputs/cloud/cable-all/… · 回执 data/cable-all-live.json
用法：
  py -3.14 -X utf8 tools/codex-scripts/probe-cable-all.py                    # 四根全跑
  py -3.14 -X utf8 tools/codex-scripts/probe-cable-all.py --only video       # 只补出片那根
  py -3.14 -X utf8 tools/codex-scripts/probe-cable-all.py --only video --task <task_id>  # 接着轮询已有任务
"""
from __future__ import annotations

import base64
import hashlib
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "outputs" / "open-source-release" / "data"
OUT = ROOT / "outputs" / "cloud" / "cable-all"
BASE = "https://apihub.agnes-ai.com/v1"
UA = "gbt-v8/1.0"


def _tok() -> tuple[str, str]:
    from gbt_allinone import deepseek_key as DK
    return DK.load_key("agnes")


def _post(path: str, body: dict, tok: str, timeout: int = 240):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method="POST",
                                headers={"Authorization": "Bearer " + tok,
                                         "Content-Type": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, (e.read() or b"")[:400]
    except Exception as exc:                                   # noqa: BLE001
        return -1, ("%s: %s" % (type(exc).__name__, str(exc)[:200])).encode()


def _save(data: bytes, name: str) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    p.write_bytes(data)
    return {"artifact": str(p.relative_to(ROOT)).replace("\\", "/"),
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _fetch(url: str, timeout: int = 240) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _get(path: str, tok: str, timeout: int = 60):
    req = urllib.request.Request(BASE + path, headers={"Authorization": "Bearer " + tok,
                                                       "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, (e.read() or b"")[:400]
    except Exception as exc:                                   # noqa: BLE001
        return -1, ("%s: %s" % (type(exc).__name__, str(exc)[:200])).encode()


def cable_video(tok: str, task_id: str | None = None, max_wait: int = 900) -> dict:
    """出片：**真契约**（2026-10-21 现场探明，逐字段带上游原话）。

    ① 提交 POST /video/generations  body = {model, prompt, mode:"text"}
       · `mode` 必填；实测允许值 `text`、`keyframe`（keyframe 另需 first_frame/last_frame）
       · `duration` 不是允许字段（上游原话：duration is not an allowed request field）
       · `seconds`/`size` 由服务端定（本次实测 5s / 720P），别自己传
    ② 轮询 GET /videos/<task_id> → status: in_progress | completed | failed，read 进度
    ③ 取片  GET /videos/<task_id>/content（退回载荷里的 url 字段）

    ⚠️ 历史坑（2026-10-21 前的假读数）：旧版把 body 写成 {size, seconds} 且不带 mode，
    上游回的是 `invalid_json · Failed to read request body` —— 那是**上游把读不出的体折成
    invalid_json**，不是"端点不通"。按字段一个个问上游（空体→缺 model→缺 prompt→缺 mode→
    duration 不许→mode 非法）才问出真契约。"""
    tried: list[dict] = []
    t_all = time.perf_counter()

    if not task_id:
        body = {"model": "agnes-video-2.5-flash",
                "prompt": "a calm potato on a wooden desk, slow dolly-in, soft window light, cinematic",
                "mode": "text"}
        st, raw = _post("/video/generations", body, tok, timeout=120)
        text = raw.decode("utf-8", "replace")
        tried.append({"step": "submit", "path": "/video/generations", "http": st,
                      "seconds": round(time.perf_counter() - t_all, 1),
                      "response": text[:300]})
        if st != 200:
            return {"ok": False, "cable": "出片", "socket": "agnes-video-2.5-flash",
                    "tried": tried, "key_slot": "vault:agnes"}
        try:
            d = json.loads(text)
        except Exception:                                      # noqa: BLE001
            tried[-1]["note"] = "200 但载荷不是 JSON"
            return {"ok": False, "cable": "出片", "socket": "agnes-video-2.5-flash",
                    "tried": tried, "key_slot": "vault:agnes"}
        task_id = d.get("task_id") or d.get("id") or (d.get("data") or {}).get("task_id")
        if not task_id:
            tried[-1]["note"] = "200 但没有任务号"
            return {"ok": False, "cable": "出片", "socket": "agnes-video-2.5-flash",
                    "tried": tried, "key_slot": "vault:agnes"}

    # ② 轮询
    state, last = "unknown", {}
    deadline = time.time() + max_wait
    while time.time() < deadline:
        st, raw = _get("/videos/" + task_id, tok)
        if st != 200:
            tried.append({"step": "poll", "http": st,
                          "response": raw.decode("utf-8", "replace")[:220]})
            time.sleep(5)
            continue
        last = json.loads(raw.decode("utf-8", "replace"))
        state = str(last.get("status") or "").lower()
        tried.append({"step": "poll", "http": st, "status": state,
                      "progress": last.get("progress")})
        if state in ("completed", "succeeded", "success"):
            break
        if state in ("failed", "error", "cancelled"):
            tried.append({"step": "poll", "error": last.get("error")})
            return {"ok": False, "cable": "出片", "socket": "agnes-video-2.5-flash",
                    "task_id": task_id, "state": state, "tried": tried[-6:],
                    "key_slot": "vault:agnes"}
        time.sleep(6)
    else:
        tried.append({"step": "poll", "note": "轮询到 %ds 仍未完成" % max_wait})
        return {"ok": False, "cable": "出片", "socket": "agnes-video-2.5-flash",
                "task_id": task_id, "state": state, "tried": tried[-6:],
                "key_slot": "vault:agnes"}

    # ③ 取片（内容端点会先回 200 + {"detail":"Not Found"} 这种"上游还没挂上"的体 ⇒ 重试）；
    #    另外从任务详情里取 result_url（网关自己发布的那条地址）作为第二条路。
    st, raw = _get("/video/generations/" + task_id, tok)
    result_url, finish_s = "", None
    if st == 200:
        try:
            _dd = json.loads(raw.decode("utf-8", "replace")).get("data") or {}
            result_url = _dd.get("result_url") or ""
            if _dd.get("finish_time") and _dd.get("submit_time"):
                finish_s = _dd["finish_time"] - _dd["submit_time"]
        except Exception:                                      # noqa: BLE001
            pass
    urls = ["/videos/%s/content" % task_id] + ([result_url] if result_url else [])
    data, last_err = None, ""
    for attempt in range(12):
        for u in urls:
            path = u
            if path.startswith("http"):
                path = path.split("apihub.agnes-ai.com", 1)[-1]
            if path.startswith("/v1/"):
                path = path[3:]                                  # BASE 里已经带 /v1
            st, raw = _get(path, tok, timeout=300)
            is_mp4 = st == 200 and len(raw) > 10000 and (raw[4:8] == b"ftyp" or raw[:1] == b"\x00")
            tried.append({"step": "content", "attempt": attempt + 1, "path": path, "http": st,
                          "bytes": len(raw), "is_mp4": bool(is_mp4),
                          "head": "mp4" if is_mp4 else raw[:40].decode("utf-8", "replace")})
            if is_mp4:
                data = raw
                break
            last_err = raw[:200].decode("utf-8", "replace")
        if data:
            break
        time.sleep(5)
    if not data:
        return {"ok": False, "generated": True, "cable": "出片",
                "socket": "agnes-video-2.5-flash",
                "endpoint": BASE + "/video/generations", "task_id": task_id,
                "state": state, "seconds_spec": last.get("seconds"),
                "size_spec": last.get("size"), "result_url": result_url,
                "finish_seconds": finish_s,
                "elapsed_s": round(time.perf_counter() - t_all, 1),
                "upstream": last_err, "tried": tried[-6:], "key_slot": "vault:agnes",
                "note": "任务 100% 完成但取片端点不吐 mp4（上游 result_url 自己回 Not Found）——"
                        "反向调用通、回传链接坏，两件事分开记"}
    saved = _save(data, "cable-video-%s-%s.mp4" % (task_id.replace("task_", "")[:10],
                                                   time.strftime("%Y%m%dT%H%M%S")))
    return {"ok": True, "cable": "出片", "socket": "agnes-video-2.5-flash",
            "endpoint": BASE + "/video/generations", "task_id": task_id,
            "state": state, "seconds_spec": last.get("seconds"), "size_spec": last.get("size"),
            "elapsed_s": round(time.perf_counter() - t_all, 1),
            "key_slot": "vault:agnes", **saved, "tried": tried[-8:]}


def cable_images(tok: str, n: int = 3) -> dict:
    prompts = ["a calm potato on a wooden desk, soft window light",
               "a potato wearing tiny glasses, studio photo",
               "potato slices on a cutting board, top-down, warm light"][:n]
    rows = []
    for i, pr in enumerate(prompts, 1):
        t0 = time.perf_counter()
        st, raw = _post("/images/generations",
                        {"model": "agnes-image-2.5-flash", "prompt": pr, "n": 1,
                         "size": "1024x1024"}, tok, timeout=240)
        dt = round(time.perf_counter() - t0, 1)
        if st != 200:
            rows.append({"n": i, "ok": False, "http": st, "seconds": dt,
                         "upstream": raw[:200].decode("utf-8", "replace")})
            continue
        item = (json.loads(raw).get("data") or [{}])[0]
        data = base64.b64decode(item["b64_json"]) if item.get("b64_json") else _fetch(item["url"])
        saved = _save(data, "cable-image-%d-%s.png" % (i, time.strftime("%Y%m%dT%H%M%S")))
        rows.append({"n": i, "ok": True, "http": st, "seconds": dt, "prompt": pr, **saved})
    ok = [r for r in rows if r.get("ok")]
    return {"ok": bool(ok), "cable": "批量出图", "socket": "agnes-image-2.5-flash",
            "endpoint": BASE + "/images/generations", "count": len(rows), "ok_count": len(ok),
            "total_seconds": round(sum(r.get("seconds", 0) for r in rows), 1),
            "key_slot": "vault:agnes", "rows": rows}


def cable_our_model(tok: str) -> dict:
    """我们的模型走云端算力：只要钥，不连云卡。

    契约：POST /chat/completions {model:"agnes-2.5-flash", messages:[…], max_tokens}
    ⚠️ max_tokens 给太小会把预算全烧在 reasoning 上 ⇒ text 空、只回 reasoning_tokens（踩过）。
    """
    body = {"model": "agnes-2.5-flash",
            "messages": [{"role": "user",
                          "content": "用一句话解释：为什么一根电缆加上密钥就能反向调用云端算力？"}],
            "max_tokens": 900, "temperature": 0.3}
    t0 = time.perf_counter()
    st, raw = _post("/chat/completions", body, tok, timeout=180)
    dt = round(time.perf_counter() - t0, 1)
    text = raw.decode("utf-8", "replace")
    if st != 200:
        return {"ok": False, "cable": "我们的模型（云端算力，不需要云卡）",
                "socket": "agnes-2.5-flash", "endpoint": BASE + "/chat/completions",
                "http": st, "elapsed_s": dt, "upstream": text[:300], "key_slot": "vault:agnes"}
    d = json.loads(text)
    u = d.get("usage") or {}
    msg = ((d.get("choices") or [{}])[0]).get("message") or {}
    return {"ok": True, "cable": "我们的模型（云端算力，不需要云卡）",
            "socket": "agnes-2.5-flash", "endpoint": BASE + "/chat/completions",
            "http": st, "elapsed_s": dt, "key_slot": "vault:agnes",
            "text": (msg.get("content") or "")[:400],
            "chars": len(msg.get("content") or ""),
            "usage": {"prompt": u.get("prompt_tokens"), "completion": u.get("completion_tokens"),
                      "total": u.get("total_tokens")},
            "artifacts": 0, "note": "无产物文件；只有文本，执行耗时 %.1fs / %s tokens"
                                    % (dt, u.get("total_tokens"))}


def cable_freegpu(agnes: dict | None = None) -> dict:
    """出片**真落片**：走唯一门 `run_task(kind="comfy_cloud", op="freegpu")`
    → 先量付费卡（现读 RUNNING 0）→ 自动转 HF 免费 GPU 出 mp4 → 逐字节落盘 + sha256 对账。

    纪律：缺 `network_private` 票就**如实返回 missing_scopes**，不绕门、不假装出了片。
    `agnes` 是同一个"出片"插座上 Agnes 云端的回执（反向调用通 / 回传链接坏），并排留档。
    """
    out = {"cable": "出片（免费 GPU）", "socket": "comfy_cloud op=freegpu",
           "agnes": agnes or {}}
    try:
        from gbt_allinone import run_task                       # 唯一门，不是旁路
        env = run_task("comfy_cloud", {"op": "freegpu",
                                       "prompt": "a calm potato on a wooden desk, "
                                                 "soft window light, cinematic",
                                       "seconds": 2, "height": 480, "width": 480}) or {}
    except Exception as exc:                                    # noqa: BLE001
        out.update({"ok": False, "error": "%s: %s" % (type(exc).__name__, str(exc)[:160])})
        return out
    # 信封是多层的（run_task 包一层、能力位自己再包一层）⇒ 往里挖到「带 ok 与 op 的那一层」，
    # 不许只读第一层就当结论（本仓栽过：读错一层得到空 dict）。
    inner, cur, hops = {}, env, 0
    while isinstance(cur, dict) and hops < 4:
        if "ok" in cur and ("op" in cur or "route" in cur or "reason" in cur):
            inner = cur
            break
        nxt = cur.get("result") if isinstance(cur.get("result"), dict) else None
        if nxt is None:
            break
        cur, hops = nxt, hops + 1
    if not inner:
        inner = env.get("result") if isinstance(env.get("result"), dict) else {}
    if not inner.get("ok"):
        out.update({"ok": False,
                    "reason": inner.get("reason") or inner.get("error") or "未出片",
                    "missing_scopes": env.get("missing_scopes") or inner.get("missing_scopes"),
                    "how_to_grant": env.get("how_to_grant"),
                    "upstream": json.dumps(inner, ensure_ascii=False)[:300]})
        return out
    out.update({"ok": True, "route": inner.get("route"), "space": inner.get("space"),
                "hardware": inner.get("hardware"), "seconds_used": inner.get("seconds_used"),
                "size_spec": "%sx%s" % (inner.get("width"), inner.get("height")),
                "elapsed_s": inner.get("elapsed_s"), "artifact": inner.get("artifact"),
                "bytes": inner.get("bytes"), "sha256": inner.get("sha256"),
                "sha256_match": inner.get("sha256_match"), "paid_pod": inner.get("paid_pod"),
                "key_slot": "vault:hf"})
    return out


def cable_cpu() -> dict:
    try:
        import numpy as np
    except Exception as exc:                                   # noqa: BLE001
        return {"ok": False, "cable": "本机 CPU", "error": "numpy 缺：%s" % type(exc).__name__}
    n = 2048
    a = np.random.rand(n, n).astype("float32")
    b = np.random.rand(n, n).astype("float32")
    a @ b
    t0 = time.perf_counter()
    _ = a @ b
    dt = time.perf_counter() - t0
    return {"ok": True, "cable": "本机 CPU", "socket": "numpy float32 matmul %dx%d" % (n, n),
            "seconds": round(dt, 4), "gflops": round(2 * n ** 3 / dt / 1e9, 1),
            "artifacts": 0, "note": "裸算力：零模型、零出网、无产物文件（只出读数）"}


def main() -> int:
    only = ""
    task_id = None
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == "--only" and i + 1 < len(argv):
            only = argv[i + 1]
        if a == "--task" and i + 1 < len(argv):
            task_id = argv[i + 1]
    tok, slot = _tok()
    p = DATA / "cable-all-live.json"
    doc = {}
    if p.is_file() and only:
        doc = json.loads(p.read_text(encoding="utf-8"))
    doc.update({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "schema": "cable-all-live-v1",
                "cable_model": "触手=电缆 · 密钥=通电 · 云端有算力就能通 · 能通就能反向调用",
                "key_slot": "vault:" + str(slot).split(":")[-1] if slot else "vault:agnes",
                "endpoint": BASE})
    if only in ("", "model"):
        doc["our_model"] = cable_our_model(tok)
    if only == "agnesvideo":
        doc["video"] = dict(doc.get("video") or {}, agnes=cable_video(tok, task_id=task_id))
    if only == "video":
        prev = doc.get("video") or {}
        ag = prev.get("agnes") or (prev if prev.get("task_id") else None)
        doc["video"] = cable_freegpu(ag)
    if only == "":
        doc["video"] = cable_freegpu(cable_video(tok, task_id=task_id))
    if only in ("", "images"):
        doc["images"] = cable_images(tok, 3)
    if only in ("", "cpu"):
        doc["cpu"] = cable_cpu()
    DATA.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"our_model": {k: doc.get("our_model", {}).get(k) for k in
                                    ("ok", "socket", "http", "elapsed_s", "chars", "usage")},
                      "video": {k: doc.get("video", {}).get(k) for k in
                                ("ok", "route", "socket", "elapsed_s", "seconds_used",
                                 "size_spec", "bytes", "sha256", "sha256_match",
                                 "missing_scopes")},
                      "images": {k: doc.get("images", {}).get(k) for k in
                                 ("ok", "ok_count", "count", "total_seconds")},
                      "cpu": {k: doc.get("cpu", {}).get(k) for k in ("ok", "seconds", "gflops")}},
                     ensure_ascii=False, indent=1)[:1600])
    print("落账 →", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
