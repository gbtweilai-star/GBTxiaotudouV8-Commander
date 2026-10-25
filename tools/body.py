# -*- coding: utf-8 -*-
"""化身 · 身体模式（body schema）—— 设备即肉身

主人的话：「不管安装在什么设备上，设备都可化作实体身体，
          设备所有能力同等她的原生能力来使用」

设计：**器官是抽象的，实现是探出来的**。
  ① 器官（ORGANS）只有名字和语义 —— 眼/耳/嘴/手/记忆/本体/位置/环境/内感受/情绪
  ② 每个器官挂一串**候选实现**（按优先级），装在哪台设备就用哪台的
  ③ 启动时真探一遍，取不到就写"缺这个器官"，**绝不假装有**
  ④ 对外只有两个动作：feel（一次性感知全身）· use（用某个器官做一件事）

平台自适应：iOS 走 apple-* 桥；没有就回落到通用 CLI（tesseract / ffmpeg / say…）；
都没有 ⇒ 该器官标记为缺，如实报。

用法：
  python3 tools/body.py                       # 全身自检：每个器官通不通
  python3 tools/body.py feel                  # 感知一次（本体/位置/环境/内感受）
  python3 tools/body.py use 眼 ocr <图片>      # 用"眼"做一件事
  python3 tools/body.py organs                # 器官表
"""
from __future__ import annotations
import json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = "/usr/local/bin"

# ── 器官 → 候选实现（按优先级）──────────────────────────────
# 每条: (工具, 命令, 额外参数, 读/写, 语义)
ORGANS = {
    "眼": {
        "cn": "看", "desc": "读图、认字、识物、看照片库",
        "impls": [
            ("apple-vision", "analyze", [], "read", "一张图全分析"),
            ("apple-vision", "ocr", [], "read", "只认字"),
            ("apple-vision", "classify", [], "read", "只认类别"),
            ("apple-vision", "faces", [], "read", "只找人脸"),
            ("apple-photos", "stats", [], "read", "看自己有多少照片"),
        ],
    },
    "耳": {
        "cn": "听", "desc": "把说话转成文字",
        "impls": [
            ("apple-speech", "status", [], "read", "听的能力在不在"),
            ("apple-speech", "languages", [], "read", "能听哪些语言"),
        ],
    },
    "嘴": {
        "cn": "说", "desc": "出声、念出来",
        "impls": [
            ("apple-speak", "voices", [], "read", "有多少嗓子"),
        ],
    },
    "手": {
        "cn": "动手", "desc": "开链接、写剪贴板、记日程提醒",
        "impls": [
            ("apple-clipboard", "", [], "read", "手里现在捏着什么"),
            ("apple-open", "", [], "write", "打开一个东西（要 URL）"),
            ("apple-reminders", "create", [], "write", "记一条待办"),
            ("apple-calendar", "create", [], "write", "排一个日程"),
        ],
    },
    "记忆": {
        "cn": "记得", "desc": "照片库、剪贴板、日历都是她的外置记忆",
        "impls": [
            ("apple-photos", "stats", [], "read", "照片库规模"),
            ("apple-photos", "albums", [], "read", "相册清单"),
            ("apple-calendar", "list", [], "read", "过去与将来的事"),
        ],
    },
    "本体": {
        "cn": "本体感", "desc": "自己的电量/内存/温度/芯片",
        "impls": [
            ("apple-device", "info", [], "read", "自己这具身体的状态"),
        ],
    },
    "位置": {
        "cn": "空间感", "desc": "自己在哪",
        "impls": [
            ("apple-location", "", [], "read", "GPS + 地址"),
        ],
    },
    "环境": {
        "cn": "外环境", "desc": "天气、家居",
        "impls": [
            ("apple-weather", "", [], "read", "外面什么样"),
            ("apple-homekit", "list", [], "read", "家里有什么设备"),
        ],
    },
    "内感受": {
        "cn": "内感受", "desc": "心率、步数、睡眠 —— 身体内部的读数",
        "impls": [
            ("apple-healthkit", "steps", [], "read", "走了多少"),
            ("apple-healthkit", "heart-rate", [], "read", "心跳"),
            ("apple-healthkit", "sleep", [], "read", "睡了多久"),
        ],
    },

    "推理": {
        "cn": "想", "desc": "用自己权重思考 —— 云端 / 本机原生 App / 本地引擎，一个器官三条实现",
        # 主人的设计：把苹果的两条路合并成一条 —— 在这里，三条实现共用一个器官名
        "impls": [
            # args = [model, key]
            ("@app",    "http://127.0.0.1:1234/v1",
             ["", "gbt"], "read",
             "本机 LM Pocket · Metal · A19 真算力（实测 176ms）"),
            ("@cloud",  "https://gbt-potato-cloud-10.paysssk.workers.dev/v1",
             ["gbt-potato-v8", ""], "read", "云端 RunPod 自有权重"),
            ("@engine", "http://127.0.0.1:8077/v1",
             ["gbt-v8", ""], "read", "本地自写引擎"),
        ],
    },
    "情绪": {
        "cn": "情绪", "desc": "读出语言里的情绪",
        "impls": [
            ("apple-nlp", "sentiment", ["--text", "我很开心"], "read", "情绪判读"),
        ],
    },
}



# ── 工具 → 器官：让派活能说"用眼睛看"，而不是"调 apple-vision" ──
TOOL_ORGAN = {
    "apple-vision": "眼", "apple-photos": "记忆",
    "apple-speech": "耳",
    "apple-speak": "嘴", "apple-player": "嘴", "apple-media": "嘴",
    "apple-clipboard": "手", "apple-open": "手", "apple-reminders": "手",
    "apple-alarm": "手", "apple-notification": "手", "apple-nfc": "手",
    "apple-calendar": "记忆",
    "apple-device": "本体", "apple-bluetooth": "本体",
    "apple-location": "位置", "apple-maps": "位置",
    "apple-weather": "环境", "apple-homekit": "环境",
    "apple-healthkit": "内感受",
    "apple-nlp": "情绪",
}


def organ_for(tool: str, cmd: str | None = None) -> dict:
    """给定 (工具, 命令)，回答：这属于哪个器官、该器官有没有这条实现。"""
    organ = TOOL_ORGAN.get(tool)
    if not organ:
        return {"organ": None, "why": "%s 没有归属器官" % tool}
    impls = ORGANS[organ]["impls"]
    hit = any(t == tool and (cmd is None or c == cmd) for t, c, *_ in impls)
    return {"organ": organ, "cn": ORGANS[organ]["cn"],
            "in_body": hit,
            "avail_cmds": [c for t, c, *_ in impls if t == tool]}


# ── 器官意图表：**器官自己认领**，不靠"工具名反查" ──────────────
# 主人口径：「设备即肉身」—— 那就得先问"这是哪个器官的事"，再问"用哪根实现"。
ORGAN_INTENT = {
    "眼":    ("看", "读图", "识别", "认字", "ocr", "截图", "图里", "照片里", "看一下"),
    "耳":    ("听", "录音", "转写", "语音转文字", "听见"),
    "嘴":    ("说", "念", "朗读", "出声", "配音", "播放", "唱"),
    "手":    ("打开", "记一下", "提醒我", "安排", "写进", "发到", "点开", "帮我记"),
    "记忆":  ("日程", "日历", "照片", "相册", "过去", "历史", "我记得", "存过"),
    "本体":  ("电量", "内存", "温度", "我的设备", "机器", "芯片", "几核"),
    "位置":  ("在哪", "位置", "定位", "附近", "坐标", "周围"),
    "环境":  ("天气", "气温", "下雨", "外面", "家居", "室内", "湿度"),
    "内感受": ("步数", "心率", "睡眠", "走了", "消耗", "心跳", "身体", "卡路里"),
    "情绪":  ("情绪", "心情", "态度", "语气", "情感", "开心", "难过"),
    # 主人令（2026-10-24）：「权重凝练成触手的一部分直通 A19」——
    # 「想」是器官，不是外部服务。凡是"用脑子"的话都落在这里。
    "推理":  ("想一想", "想想", "思考", "推理", "分析", "判断", "解释", "为什么",
              "怎么办", "你是谁", "你觉得", "帮我写", "总结", "翻译", "回答我"),
}

# 每个器官的默认命令（没说具体要什么时用它）
ORGAN_DEFAULT = {
    "眼": "analyze", "耳": "status", "嘴": "voices", "手": "", "记忆": "list",
    "本体": "info", "位置": "", "环境": "", "内感受": "steps", "情绪": "sentiment",
    "推理": "",        # 空 ⇒ 走 HTTP 那条（@app / @cloud / @engine 自动择活）
}


def route_organ(text: str, limit: int = 3) -> list:
    """一句话 → 哪个器官认领（含打分与默认命令）。**只路由，不执行。**"""
    t = str(text or "").lower()
    out = []
    for organ, kws in ORGAN_INTENT.items():
        score = sum(1 for k in kws if k.lower() in t)
        if not score:
            continue
        dflt = ORGAN_DEFAULT.get(organ, "")
        # @app/@cloud 这类是 HTTP 实现（不是 /usr/local/bin 里的可执行件），
        # 早先这里直接 _has("@app") ⇒ 永远 False ⇒「推理」器官永远不被认领。
        _first = ORGANS[organ]["impls"][0][0] if ORGANS[organ]["impls"] else ""
        has = True if _first.startswith("@") else _has(_first)
        out.append({"organ": organ, "cn": ORGANS[organ]["cn"], "score": score,
                    "cmd": dflt, "organ_ready": has,
                    "how": "omni_plug op=body do=use organ=%s cmd=%s" % (organ, dflt or "-")})
    out.sort(key=lambda x: -x["score"])
    return out[:limit]




# ── iOS 现实：本地推理 App 一切后台就挂起 ────────────────────
# 所以每次调 @app 之前，先用 URL scheme 把它拉到前台，再发请求。
# 实测：唤起后约 50 秒窗口内可正常推理（单次请求 0.2–0.4 秒，够用）。
APP_WAKE = {"@app": "lmpocket://"}


def _wake(tool: str, wait: float = 2.0) -> bool:
    sch = APP_WAKE.get(tool)
    if not sch:
        return True
    import subprocess as _sp, time as _t
    try:
        _sp.run(["/usr/local/bin/apple-open", sch, "--compact"],
                capture_output=True, timeout=8)
    except Exception:
        return False
    _t.sleep(wait)
    return True


def _probe_http(base: str, key: str = "", timeout: float = 4.0) -> dict:
    """探一个 OpenAI 兼容口：能回 /models 就算活。"""
    import urllib.request
    try:
        u = base.rstrip("/") + "/models"
        _h = {"User-Agent": "gbt-body"}
        if key:
            _h["Authorization"] = "Bearer " + key
        req = urllib.request.Request(u, headers=_h)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(400).decode("utf-8", "replace")
        return {"ok": r.status == 200, "status": r.status, "sample": body[:80]}
    except Exception as e:
        return {"ok": False, "status": type(e).__name__, "why": str(e)[:60]}


def _has(tool: str) -> bool:
    return Path(BIN + "/" + tool).is_file()


def _run(tool, cmd, args, timeout=15):
    argv = [BIN + "/" + tool] + ([cmd] if cmd else []) + [str(a) for a in args]
    t0 = time.time()
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "status": "timeout", "ms": round((time.time() - t0) * 1000)}
    except Exception as e:
        return {"ok": False, "status": "exception", "why": type(e).__name__}
    ms = round((time.time() - t0) * 1000)
    try:
        j = json.loads((p.stdout or "").strip() or "{}")
    except Exception:
        j = {}
    return {"ok": bool(j.get("ok")), "ms": ms,
            "data": j.get("data"),
            "err": (j.get("error") or {}).get("message") if isinstance(j.get("error"), dict) else None}





# ── 离线排队：iOS 会把后台 App 的本地服务收走 ──────────────────
# 所以「她不在线」不该让任务丢掉 —— 入队，等 App 回到前台自动跑完。
QUEUE = "/tmp/a19_queue.jsonl"
DONE = "/tmp/a19_done.jsonl"


def enqueue(text: str) -> dict:
    """把任务塞进 A19 队列（工作器 a19_worker.py 会在端口一通时批量跑完）。"""
    import json as _j, time as _t
    try:
        with open(QUEUE, "a", encoding="utf-8") as f:
            job = {"id": int(_t.time() * 1000), "q": str(text)}
            f.write(_j.dumps(job, ensure_ascii=False) + "\n")
        n = sum(1 for ln in open(QUEUE, encoding="utf-8") if ln.strip())
        return {"ok": True, "status": "queued", "id": job["id"], "队列条数": n,
                "说明": "A19 现在不在线（App 在后台）。打开 LM Pocket → Load & Start Server，"
                        "工作器会自动把队列跑完。"}
    except Exception as e:
        return {"ok": False, "why": "%s: %s" % (type(e).__name__, str(e)[:80])}


def drain_done() -> dict:
    """读 A19 已跑完的结果。"""
    import json as _j
    out = []
    try:
        for ln in open(DONE, encoding="utf-8"):
            ln = ln.strip()
            if ln:
                try:
                    out.append(_j.loads(ln))
                except Exception:
                    pass
    except FileNotFoundError:
        return {"ok": True, "完成": 0, "结果": []}
    return {"ok": True, "完成": len(out), "结果": out[-20:]}


def _discover_model(base: str, key: str = "") -> str:
    """问 A19 那边"你现在加载的是哪个模型"，不写死 model 名。
    主人的口径：权重是触手的一部分 —— 换哪份权重，她都不用改代码。"""
    import json as _j, urllib.request
    try:
        h = {"User-Agent": "gbt-body"}
        if key:
            h["Authorization"] = "Bearer " + key
        req = urllib.request.Request(base.rstrip("/") + "/models", headers=h)
        with urllib.request.urlopen(req, timeout=4) as r:
            d = _j.loads(r.read().decode("utf-8", "replace"))
        ms = d.get("data") or []
        if ms:
            return str(ms[0].get("id") or "")
    except Exception:
        pass
    return ""


def _chat_http(base: str, text: str, model: str = "gbt-potato-v8",
               key: str = "", timeout: float = 180.0) -> dict:
    """对一个 OpenAI 兼容口说一句话，拿回回答。这是「推理」器官的肌肉。"""
    import json as _j, urllib.request, os, time
    t0 = time.time()
    if not key:                      # 没给就用我们的统一钥（云端那条路）
        for f in ("/var/minis/shared/gateway-token.txt",
                  str(ROOT / "vaults" / "own_model" / "unified_key")):
            try:
                key = Path(f).read_text().strip()
                if key:
                    break
            except Exception:
                continue
    if not model:
        model = _discover_model(base, key)          # 不写死，问它现在加载的是哪个
    body = _j.dumps({"model": model,
                     "messages": [{"role": "user", "content": text}],
                     "max_tokens": 512}).encode()
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions", data=body, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": "gbt-body",
                 **({"Authorization": "Bearer " + key} if key else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = _j.loads(r.read().decode("utf-8", "replace"))
        msg = (d.get("choices") or [{}])[0].get("message", {})
        _ans = str(msg.get("content") or "")
        for _t in ("<|im_end|>", "<|endoftext|>", "<|im_start|>"):
            _ans = _ans.replace(_t, "")          # 剥掉 chat 模板残留
        return {"ok": True, "ms": round((time.time() - t0) * 1000),
                "answer": _ans.strip(), "model": d.get("model"),
                "gbt": d.get("gbt"), "usage": d.get("usage")}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")[:200]
        return {"ok": False, "ms": round((time.time() - t0) * 1000),
                "http": e.code, "upstream_error": raw}
    except Exception as e:
        return {"ok": False, "ms": round((time.time() - t0) * 1000),
                "why": "%s: %s" % (type(e).__name__, str(e)[:80])}


def resolve(organ: str) -> dict:
    """为某个器官挑一根能用的实现（按优先级真探）。"""
    o = ORGANS.get(organ)
    if not o:
        return {"organ": organ, "ok": False, "why": "没有这个器官"}
    tried = []
    for tool, cmd, args, rw, desc in o["impls"]:
        if tool.startswith("@"):
            _k = (list(args) + ["", ""])[1] if args else ""
            r = _probe_http(str(cmd), key=_k, timeout=1.5)
            if r.get("ok"):
                return {"organ": organ, "cn": o["cn"], "ok": True,
                        "impl": "%s %s" % (tool, cmd), "rw": rw, "desc": desc}
            tried.append({"impl": tool, "why": r.get("status") or r.get("why")})
            continue
        if not _has(tool):
            tried.append({"impl": "%s %s" % (tool, cmd), "why": "不在本机"})
            continue
        r = _run(tool, cmd, args)
        # 只读实现：能把默认动作跑通就算这件器官在
        if r.get("ok") or (r.get("err") and "No input" in str(r.get("err"))):
            return {"organ": organ, "cn": o["cn"], "ok": True,
                    "impl": "%s %s" % (tool, cmd or "-"), "rw": rw,
                    "desc": desc, "ms": r.get("ms")}
        tried.append({"impl": "%s %s" % (tool, cmd), "why": (r.get("err") or r.get("status"))[:40]})
    return {"organ": organ, "cn": o["cn"], "ok": False, "why": "没有可用实现", "tried": tried}


def body() -> dict:
    """全身自检：每个器官通不通、用哪根实现。"""
    rows = [resolve(k) for k in ORGANS]
    ok = sum(1 for r in rows if r.get("ok"))
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "器官数": len(ORGANS), "可用": ok, "缺": len(ORGANS) - ok,
            "body": rows}


def feel() -> dict:
    """感知一次：本体 / 位置 / 环境 / 内感受 —— 她"此刻"的状态。"""
    out = {}
    for organ in ("本体", "位置", "环境", "内感受"):
        o = ORGANS[organ]
        for tool, cmd, args, rw, desc in o["impls"][:1]:
            if not _has(tool):
                out[organ] = {"ok": False, "why": "本机没有这个器官"}
                break
            r = _run(tool, cmd, args)
            out[organ] = {"ok": r.get("ok"), "impl": "%s %s" % (tool, cmd or "-"),
                          "ms": r.get("ms"), "data": r.get("data"), "err": r.get("err")}
            break
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "feel": out}


def use(organ: str, cmd: str | None, args: list) -> dict:
    """用某个器官做一件事。写类器官照旧由上一层门决定放不放。"""
    o = ORGANS.get(organ)
    if not o:
        return {"ok": False, "why": "没有这个器官：%s" % organ}
    # 🔴 不指定 cmd ⇒ 先 resolve 择活，再取那条实现。
    #    早先这里直接取 impls[0]，结果「推理」永远撞死在本机没装的 @app 上。
    if cmd is None:
        # 🔴 A19 优先：先只探 impls[0]（@app）。通了就用它；
        #    不通就**排队**，绝不降级到云端 —— 主人要的是"用她自己的算力"，
        #    云端那条又慢又会静默兜底到别人的模型（实测 201 秒 + weights_ours:false）。
        first = o["impls"][0] if o["impls"] else None
        if first and first[0].startswith("@"):
            _m0, _k0 = (list(first[2]) + ["", ""])[:2]
            _p = _probe_http(str(first[1]), key=_k0, timeout=2.0)
            if _p.get("ok"):
                cand = [first]
            elif first[0] == "@app":
                _q = enqueue(" ".join(str(a) for a in args) or "你好")
                _q.update({"organ": organ, "impl": first[0]})
                return _q
            else:
                cand = [first]
        else:
            r = resolve(organ)
            if not r.get("ok"):
                return {"ok": False, "organ": organ, "why": r.get("why") or "没有可用实现",
                        "tried": r.get("tried")}
            _impl = str(r.get("impl") or "")
            _tool = _impl.split(" ")[0]
            cand = [x for x in o["impls"] if x[0] == _tool]
    else:
        cand = [x for x in o["impls"] if (cmd is None or x[1] == cmd)]
    if not cand:
        return {"ok": False, "why": "%s 没有命令 %s" % (organ, cmd),
                "有": [x[1] for x in o["impls"]]}
    tool, c, extra, rw, desc = cand[0]
    if tool.startswith("@"):
        _m0, _k0 = (list(extra) + ["", ""])[:2] if extra else ("", "")
        # 🔴 先探，不通就排队 —— **绝不能先唤醒**：
        #    唤醒会把 LM Pocket 拉到前台，Minis 一进后台，本进程立刻被 iOS 冻结。
        _p = _probe_http(str(c), key=_k0, timeout=2.0)
        if not _p.get("ok"):
            if tool == "@app":
                _q = enqueue(" ".join(str(a) for a in args) or "你好")
                _q.update({"organ": organ, "impl": tool})
                return _q
            return {"ok": False, "organ": organ, "impl": tool,
                    "why": "端点不活：%s" % (_p.get("status") or _p.get("why"))}
        _wake(tool)                      # 已通，才唤醒（补足前台窗口）
        text = " ".join(str(a) for a in args) or "你好"
        _m, _k = (list(extra) + ["", ""])[:2] if extra else ("", "")
        r = _chat_http(str(c), text, model=_m or "gbt-potato-v8", key=_k or "")
        r.update({"organ": organ, "impl": "%s %s" % (tool, c), "rw": rw})
        return r
    if not _has(tool):
        return {"ok": False, "why": "本机没有 %s" % tool}
    r = _run(tool, c, list(args) + extra)
    r.update({"organ": organ, "impl": "%s %s" % (tool, c or "-"), "rw": rw})
    return r


def main() -> int:
    a = sys.argv[1:] or ["body"]
    c = a[0]
    if c == "organs":
        for k, v in ORGANS.items():
            print("  %-6s %-6s %s" % (k, v["cn"], v["desc"]))
        return 0
    if c == "feel":
        d = feel()
        for k, v in d["feel"].items():
            mark = "✅" if v.get("ok") else "❌"
            print("  %s %-5s %-22s %sms  %s" % (mark, k, v.get("impl") or "",
                  v.get("ms", ""), str(v.get("data"))[:70] if v.get("ok") else v.get("err") or v.get("why")))
        return 0
    if c == "use":
        if len(a) < 2:
            print("  用法: body.py use <器官> [命令] [参数...]"); return 2
        organ = a[1]
        cmd = a[2] if len(a) > 2 else None
        print(json.dumps(use(organ, cmd, a[3:]), ensure_ascii=False, indent=1)[:600])
        return 0
    d = body()
    print("  化身自检 · %s" % d["at"])
    print("  %d 个器官 · 可用 %d / 缺 %d" % (d["器官数"], d["可用"], d["缺"]))
    for r in d["body"]:
        mark = "✅" if r.get("ok") else "❌"
        print("    %s %-6s %-22s %s" % (mark, r["organ"], r.get("impl") or "—",
              (r.get("desc") or r.get("why") or "")[:48]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
