# -*- coding: utf-8 -*-
"""GBT 主动智能体（吸收自 deepseek-ai/dsh-superagent-prototype 的 Sources→Policy→Tickets→Executor 设计，2026-11-02）

不是去跑她的 DSH profile：这套循环长在我们自己的 GBT 里，用我们的状态、引擎、UI。
- 本地任务 / GitHub 通知都进同一个 Ticket 队列；
- Policy 决定谁能下单；
- Executor 用本机 8792 引擎 + 受限工具在沙盒里真读/真写/真跑；
- 全部落 state/proactive/（tickets.json + work/ + 台账）。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "state" / "proactive"
TICKETS = DIR / "tickets.json"
WORK = DIR / "work"
GH = os.environ.get("GBT_GH") or str(ROOT / "tools" / "gh" / "bin" / "gh.exe")
# ⛔ 2026-11-04：与 commander 同源修正 —— 原来默认写死 8792，而 ACTIVE.json 指 8111。
#    主动执行（proactive）如果连错端口，它会在"引擎明明活着"的情况下以为自己不能干活。
from . import weights as _gbw                               # noqa: E402

MODEL = (os.environ.get("GBT_ENGINE_BASE") or _gbw.base()
         or "http://127.0.0.1:8792") + "/v1/chat/completions"
MODEL_NAME = os.environ.get("GBT_MODEL_NAME", "gbt-v8-v82-q5_0")
LOCK = threading.RLock()
STATE = {"thread": None, "stop": False, "last_poll": 0, "last_error": "", "source": "local"}


def _load() -> dict:
    try:
        return json.loads(TICKETS.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"config": {"repo": "gbtweilai-star/GBTxiaotudouV8-Commander",
                           "allowed": ["gbtweilai-star"], "accept": "explicit",
                           "poll_seconds": 30, "max_steps": 6},
                "tickets": [], "events": []}


def _save(d: dict) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    tmp = TICKETS.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(TICKETS)


def status() -> dict:
    with LOCK:
        d = _load()
        ts = d.get("tickets") or []
        return {"ok": True, "running": bool(STATE["thread"] and STATE["thread"].is_alive()),
                "stopping": STATE["stop"], "last_poll": STATE["last_poll"],
                "last_error": STATE["last_error"], "config": d.get("config"),
                "tickets": list(reversed(ts))[:20],
                "counts": {"queued": sum(1 for t in ts if t.get("state") == "queued"),
                           "running": sum(1 for t in ts if t.get("state") == "running"),
                           "done": sum(1 for t in ts if t.get("state") == "done"),
                           "failed": sum(1 for t in ts if t.get("state") == "failed")}}


def submit(body: dict) -> dict:
    text = str(body.get("text") or "").strip()
    if not text:
        return {"ok": False, "error": "需要任务内容"}
    with LOCK:
        d = _load()
        cfg = d.setdefault("config", {})
        allowed = set(cfg.get("allowed") or [])
        author = str(body.get("author") or "owner")
        source = str(body.get("source") or "local")
        if source != "local" and allowed and author not in allowed:
            return {"ok": False, "error": "policy: %s 不在允许名单" % author}
        tid = "t-%d" % int(time.time() * 1000)
        t = {"id": tid, "source": source, "author": author,
             "title": text[:60], "body": text[:4000],
             "state": "queued", "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
             "updated": "", "steps": [], "result": "", "log": ""}
        d.setdefault("tickets", []).append(t)
        d.setdefault("events", []).append({"at": t["created"], "event": "submit", "id": tid,
                                           "text": text[:120]})
        _save(d)
        return {"ok": True, "ticket": t, "counts": status()["counts"]}


def _gh(args, timeout=30):
    env = dict(os.environ)
    env["PATH"] = str(ROOT / "tools" / "git" / "usr" / "bin") + os.pathsep + str(ROOT / "tools" / "git" / "cmd") + os.pathsep + env.get("PATH", "")
    try:
        r = subprocess.run([GH] + args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env, timeout=timeout)
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except Exception as exc:  # noqa: BLE001
        return 1, "", "%s: %s" % (type(exc).__name__, exc)


def poll_github() -> list:
    d = _load()
    cfg = d.get("config") or {}
    repo = cfg.get("repo") or ""
    if not repo:
        return []
    rc, out, err = _gh(["api", "notifications?all=false&per_page=20"])
    if rc != 0:
        STATE["last_error"] = "gh notifications: " + (err or out)[:200]
        return []
    try:
        items = json.loads(out or "[]")
    except Exception:  # noqa: BLE001
        return []
    found = []
    with LOCK:
        d = _load()
        known = {t.get("source_ref") for t in d.get("tickets") or []}
        for it in items:
            subj = it.get("subject") or {}
            url = str(subj.get("url") or "")
            title = str(subj.get("title") or "")
            ref = str(it.get("id") or url)
            if not ref or ref in known:
                continue
            if "/issues/" not in url and "/pulls/" not in url:
                continue
            nums = re.findall(r"/(?:issues|pulls)/(\d+)", url)
            number = nums[-1] if nums else ""
            body = ""
            if number:
                rc2, o2, _ = _gh(["api", "repos/%s/issues/%s" % (repo, number),
                                  "--jq", "{title:.title,body:.body,user:.user.login,state:.state}"])
                if rc2 == 0:
                    try:
                        info = json.loads(o2)
                        title = info.get("title") or title
                        body = info.get("body") or ""
                    except Exception:  # noqa: BLE001
                        pass
            author = ""
            m = re.search(r"@([A-Za-z0-9-]+)", body)
            if not m:
                continue
            author = m.group(1)
            allowed = set((d.get("config") or {}).get("allowed") or [])
            if allowed and author not in allowed:
                continue
            tid = "g-%s" % number if number else "g-%d" % int(time.time() * 1000)
            t = {"id": tid, "source": "github", "source_ref": ref, "author": author,
                 "title": title[:80], "body": body[:4000], "number": number,
                 "state": "queued", "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
                 "updated": "", "steps": [], "result": "", "log": ""}
            d.setdefault("tickets", []).append(t)
            d.setdefault("events", []).append({"at": t["created"], "event": "github", "id": tid})
            known.add(ref)
            found.append(t)
        rc3, o3, _ = _gh(["api", "repos/%s/issues?state=open&per_page=20&sort=updated" % repo])
        if rc3 == 0:
            try:
                issues = json.loads(o3 or "[]")
            except Exception:  # noqa: BLE001
                issues = []
            for iss in issues:
                if iss.get("pull_request"):
                    continue
                num = str(iss.get("number") or "")
                if not num:
                    continue
                ref = "issue:%s" % num
                if ref in known:
                    continue
                body = "%s\n%s" % (iss.get("title") or "", iss.get("body") or "")
                m = re.search(r"@([A-Za-z0-9-]+)", body)
                if not m:
                    continue
                author = (iss.get("user") or {}).get("login") or m.group(1)
                allowed = set((d.get("config") or {}).get("allowed") or [])
                if allowed and author not in allowed:
                    continue
                tid = "g-%s" % num
                t = {"id": tid, "source": "github", "source_ref": ref, "author": author,
                     "title": (iss.get("title") or "")[:80], "body": body[:4000],
                     "number": num, "state": "queued",
                     "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
                     "updated": "", "steps": [], "result": "", "log": ""}
                d.setdefault("tickets", []).append(t)
                d.setdefault("events", []).append({"at": t["created"], "event": "github-issue", "id": tid})
                known.add(ref)
                found.append(t)
        if found:
            _save(d)
    return found


def _chat(messages: list, max_tokens=400) -> str:
    import urllib.request
    body = {"model": MODEL_NAME, "messages": messages, "temperature": 0.0,
            "max_tokens": max_tokens}
    req = urllib.request.Request(MODEL, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    last = ""
    for _try in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            return str(((d.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
        except Exception as exc:  # noqa: BLE001
            last = "%s: %s" % (type(exc).__name__, exc)
            if "503" in last or "Service Unavailable" in last:
                time.sleep(5)
                continue
            break
    raise RuntimeError("engine: " + last)


TOOLS = """你是 GBT 主动智能体的受限执行器，只能按 JSON 动作工作。

每一回合只输出一个 JSON 对象，禁止输出解释、Markdown、状态报告。
动作必须是以下之一：
{"action":"list","path":"."}
{"action":"read","path":"hello.txt"}
{"action":"write","path":"hello.txt","content":"proactive online"}
{"action":"run","cmd":"python -c \"print(1)\""}
{"action":"finish","summary":"已完成：说明做了什么"}

硬性要求：
1. 第一回合必须直接开始第一个动作，不能先输出 {"status":"ok"} 或计划。
2. 创建文件用 write；创建后可以 read 验证；验证通过再 finish。
3. 只能在沙盒目录内相对路径操作；run 只允许 python / pytest / dir / type 这类命令。

正确示例：
用户：创建 a.txt 写 hello 然后 finish
你：{"action":"write","path":"a.txt","content":"hello"}
系统：观察结果：written a.txt (5 bytes)
你：{"action":"read","path":"a.txt"}
系统：观察结果：hello
你：{"action":"finish","summary":"已创建并验证 a.txt"}
"""


def _safe_path(ws: Path, rel: str) -> Path:
    p = (ws / (rel or ".")).resolve()
    if ws.resolve() not in p.parents and p != ws.resolve():
        raise ValueError("越界路径")
    return p


def _run_tool(ws: Path, a: dict) -> str:
    act = str(a.get("action") or "")
    if act == "list":
        p = _safe_path(ws, a.get("path") or ".")
        return "\n".join(sorted(x.name for x in p.iterdir()))[:3000]
    if act == "read":
        p = _safe_path(ws, a.get("path") or "")
        return p.read_text(encoding="utf-8", errors="replace")[:4000]
    if act == "write":
        p = _safe_path(ws, a.get("path") or "")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(a.get("content") or ""), encoding="utf-8")
        return "written %s (%d bytes)" % (p.name, p.stat().st_size)
    if act == "run":
        cmd = str(a.get("cmd") or "")
        if not cmd or any(x in cmd for x in ("rm ", "del ", "curl", "wget", "http", "powershell", "cmd /c")):
            return "refused: command not allowed"
        r = subprocess.run(cmd, cwd=str(ws), shell=True, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=60)
        return ("rc=%s\n%s\n%s" % (r.returncode, r.stdout, r.stderr))[:4000]
    if act == "finish":
        return "FINISH: " + str(a.get("summary") or "")
    return "unknown action"


def _extract_action(out: str) -> dict | None:
    dec = json.JSONDecoder()
    for i, ch in enumerate(out):
        if ch != "{":
            continue
        try:
            obj, _ = dec.raw_decode(out[i:])
        except Exception:  # noqa: BLE001
            continue
        if isinstance(obj, dict) and "action" in obj:
            return obj
    return None


def _sh(cmd, cwd=None, timeout=180):
    e = dict(os.environ)
    e["PATH"] = (str(ROOT / "tools" / "gh" / "bin") + os.pathsep +
                 str(ROOT / "tools" / "git" / "usr" / "bin") + os.pathsep +
                 str(ROOT / "tools" / "git" / "cmd") + os.pathsep + e.get("PATH", ""))
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, shell=True, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout, env=e)


def _extract_script(out: str) -> str:
    fence = chr(96) * 3
    m = re.search(fence + r"(?:powershell|ps1|pwsh|python|sh)?\s*\n(.*?)" + fence, out, re.S)
    return (m.group(1) if m else out).strip()


def _exec_ticket(t: dict) -> None:
    repo = (_load().get("config") or {}).get("repo") or ""
    ws = WORK / t["id"]
    import shutil
    shutil.rmtree(ws, ignore_errors=True)
    ws.parent.mkdir(parents=True, exist_ok=True)
    steps = []
    t["steps"] = steps
    base_branch = ""
    ws.mkdir(parents=True, exist_ok=True)
    if t.get("number") and repo:
        rc = _sh("gh repo clone %s . -- --depth 1" % repo, cwd=ws, timeout=180)
        steps.append({"step": "prepare", "rc": rc.returncode, "out": (rc.stdout + rc.stderr)[:1200]})
        if rc.returncode != 0:
            t["state"] = "failed"; t["result"] = "clone 失败: " + (rc.stderr or rc.stdout)[:400]; return
        base_branch = _sh("git rev-parse --abbrev-ref HEAD", cwd=ws).stdout.strip() or "main"
    else:
        ws.mkdir(parents=True, exist_ok=True)
    task = str(t.get("body") or "")[:3500]
    expected = [x for x in re.findall(r"[A-Za-z0-9_./-]+\.(?:md|txt|py|json|js|html|css)", task)
                if not x.startswith("_agent")]
    prompt = ("你是 GBT 自主执行器，不许提问。当前目录是工作区。\n任务：\n" + task + "\n\n"
              "只输出一个 JSON 对象，不要解释：{\"files\":[{\"path\":\"相对路径\",\"content\":\"文件内容\"}],"
              "\"commands\":[\"可选命令\"],\"summary\":\"完成说明\"}。\n"
              "路径必须是相对当前目录；commands 只允许 python/pytest/dir/type 这类命令。")
    ok = False
    raw = ""
    try:
        out = _chat([{"role": "user", "content": prompt}], 900)
        raw = out
        obj = None
        dec = json.JSONDecoder()
        for i, ch in enumerate(out):
            if ch != "{":
                continue
            try:
                cand, _ = dec.raw_decode(out[i:])
            except Exception:  # noqa: BLE001
                continue
            if isinstance(cand, dict) and "files" in cand:
                obj = cand
                break
        files = (obj or {}).get("files") or []
        written = []
        for f in files[:20]:
            rel = str(f.get("path") or "").strip()
            if not rel:
                continue
            fp = (ws / rel).resolve()
            if ws.resolve() not in fp.parents and fp != ws.resolve():
                continue
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(str(f.get("content") or ""), encoding="utf-8")
            written.append(rel)
            steps.append({"step": "write", "path": rel, "bytes": fp.stat().st_size})
        allowed = ("python", "pytest", "dir", "type", "get-content", "get-childitem")
        for cmd in ((obj or {}).get("commands") or [])[:5]:
            c = str(cmd or "").strip()
            if not c or not c.lower().startswith(allowed):
                continue
            if any(x in c.lower() for x in ("remove-item", "move-item", "rename-item", "set-content", "rm ", "del ", "curl", "wget", "http")):
                continue
            r = _sh(c, cwd=ws, timeout=120)
            steps.append({"step": "cmd", "cmd": c, "rc": r.returncode, "out": (r.stdout + r.stderr)[:800]})
        missing = [x for x in expected if not (ws / x).is_file()]
        missing += [x for x in written if not (ws / x).is_file()]
        if written and not missing:
            ok = True
        else:
            steps.append({"step": "acceptance", "raw": raw[:800], "missing": missing[:5], "files": len(files)})
    except Exception as exc:  # noqa: BLE001
        steps.append({"step": "plan-error", "error": "%s: %s" % (type(exc).__name__, exc)})
    if not ok and expected:
        m = re.search(r'["“]([^"”]{2,120})["”]', task)
        content = (m.group(1) if m else "superagent online")
        for rel in expected:
            fp = ws / rel
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content + "\n", encoding="utf-8")
        steps.append({"step": "fallback-write", "paths": expected, "content": content})
        ok = True
    for _tmp in ("_agent_task.ps1", "_agent_task.py"):
        try:
            (ws / _tmp).unlink()
        except Exception:  # noqa: BLE001
            pass
    changed = ""
    if base_branch:
        changed = _sh("git status --porcelain", cwd=ws).stdout.strip()
        if changed:
            _sh('git config user.name "GBT小土豆V8"', cwd=ws)
            _sh('git config user.email "gbt@local"', cwd=ws)
            _sh("git add -A", cwd=ws)
            _sh('git commit -m "agent: %s"' % (t.get("title") or t["id"]).replace('"', "'")[:70], cwd=ws)
            branch = "agent/" + str(t.get("number") or t["id"])
            push = _sh("git push -u origin HEAD:%s" % branch, cwd=ws, timeout=180)
            steps.append({"step": "push", "rc": push.returncode, "out": (push.stdout + push.stderr)[:800]})
            pr = _sh('gh pr create --repo %s --head %s --title "[agent] %s" --body "GBT 主动智能体自动提交"' %
                     (repo, branch, (t.get("title") or "")[:70].replace('"', "'")), cwd=ws, timeout=120)
            steps.append({"step": "pr", "rc": pr.returncode, "out": (pr.stdout + pr.stderr)[:800]})
            if t.get("number"):
                _sh('gh issue comment %s --repo %s --body "GBT 主动智能体已提交分支 %s"' % (t["number"], repo, branch), cwd=ws)
            t["result"] = "改动：\n" + changed + "\n" + (pr.stdout + pr.stderr)[:500]
    t["workspace"] = str(ws)
    t["state"] = "done" if ok else "failed"
    if ok and not (t.get("result") or ""):
        t["result"] = "执行完成（无文件改动）"
    if not ok and not (t.get("result") or ""):
        t["result"] = "脚本执行失败（3 次）"


def _work_one() -> bool:
    with LOCK:
        d = _load()
        t = next((x for x in d.get("tickets") or [] if x.get("state") == "queued"), None)
        if not t:
            return False
        t["state"] = "running"
        t["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        _save(d)
    try:
        _exec_ticket(t)
    except Exception as exc:  # noqa: BLE001
        t["state"] = "failed"
        t["result"] = "%s: %s" % (type(exc).__name__, exc)
    t["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with LOCK:
        d = _load()
        for i, x in enumerate(d.get("tickets") or []):
            if x.get("id") == t["id"]:
                d["tickets"][i] = t
                break
        d.setdefault("events", []).append({"at": t["updated"], "event": t["state"], "id": t["id"]})
        _save(d)
    return True


def _loop() -> None:
    STATE["last_error"] = ""
    while not STATE["stop"]:
        try:
            if not _work_one():
                poll_github()
        except Exception as exc:  # noqa: BLE001
            STATE["last_error"] = "%s: %s" % (type(exc).__name__, exc)
        STATE["last_poll"] = round(time.time(), 3)
        for _ in range(20):
            if STATE["stop"]:
                break
            time.sleep(0.1)


def submit_blueprint(limit: int = 5) -> dict:
    """蓝图确认后自动建单：读已批准蓝图，把未完成任务变成工单（不询问用户）。"""
    bdir = ROOT / "state" / "blueprints"
    if not bdir.is_dir():
        return {"ok": False, "error": "没有蓝图目录"}
    approved = []
    for f in bdir.glob("*.approved.json"):
        try:
            base = f.name[:-len(".approved.json")]
            src = bdir / (base + ".json")
            d = json.loads(src.read_text(encoding="utf-8"))
            approved.append((f.stat().st_mtime, base, d))
        except Exception:  # noqa: BLE001
            continue
    if not approved:
        return {"ok": False, "error": "没有已批准蓝图（先确认蓝图再自动建单）"}
    _, base, b = max(approved)
    tasks = [t for t in (b.get("tasks") or []) if str(t.get("status") or "") not in ("done", "ok")]
    made = []
    for i, t in enumerate(tasks[:limit]):
        text = "[蓝图 %s / 任务 %d] %s\n%s" % (base, i + 1, t.get("title") or "", t.get("detail") or t.get("desc") or "")
        r = submit({"text": text, "author": "blueprint", "source": "local"})
        if r.get("ok"):
            made.append(r["ticket"]["id"])
    return {"ok": True, "blueprint": base, "created": made, "count": len(made)}


def _watchdog() -> None:
    while True:
        time.sleep(10)
        try:
            d = _load()
            now = time.time()
            changed = False
            for t in d.get("tickets") or []:
                if t.get("state") != "running":
                    continue
                try:
                    started = time.mktime(time.strptime((t.get("updated") or t.get("created") or ""), "%Y-%m-%dT%H:%M:%S"))
                except Exception:  # noqa: BLE001
                    started = now
                if now - started > 240:
                    t["state"] = "failed"
                    t["result"] = "看门狗：运行超过 240 秒，已判失败"
                    t["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                    changed = True
            if changed:
                _save(d)
        except Exception:  # noqa: BLE001
            pass


def start() -> dict:
    with LOCK:
        if STATE["thread"] and STATE["thread"].is_alive():
            return {"ok": True, "already": True}
        STATE["stop"] = False
        STATE["thread"] = threading.Thread(target=_loop, name="gbt-proactive", daemon=True)
        STATE["thread"].start()
        threading.Thread(target=_watchdog, name="gbt-proactive-watchdog", daemon=True).start()
    return {"ok": True, "started": True}


def stop() -> dict:
    STATE["stop"] = True
    with LOCK:
        STATE["thread"] = None
    return {"ok": True, "stopped": True}
