# -*- coding: utf-8 -*-
"""触手主干 · 原生指挥官（GBT 自有权重 → 本机推理 → 主干路由决策）。

**这一层要解决的那件事**：主干原来把「意图 → 哪个方法」的判决**外包给了云端大模型**
（`gbt_allinone/llm/unified.py` 的七家 key 链，过 `external_llm` 人工授权门）。
外包有三笔账：**要票**（主人不在就停摆）、**要网**（断网即降级到词表启发式）、
**要钱**（按 token 计费）。而 GBT 自己的总指挥权重就在盘上（`state/weights/`）。

本模块把这三笔账一次性结掉：

    权重（state/weights/*.gguf） → 引擎（vendor 里的 llama-server / 本仓 local_llm_server）
    → 本机 127.0.0.1:8792（OpenAI 兼容） → 主干路由判决（**只在真名表里选**）

三条纪律（与全仓同源，不新造尺子）：

1. **不许假绿**：权重没到位 / 引擎没起来 / 模型没在真名表里选 ⇒ 一律如实 `ok: False`
   并说清缺哪一步，**绝不**退化成「猜一个名字」冒充「模型说的」。
2. **幻觉防护**：模型返回的名字**必须**在本次召回的真名候选里（`semantic_route.method_table()`
   现读，89 只），否则判 `invalid_method` —— 与 semantic_route 对云端模型同一把尺。
3. **可审计**：每次进入都留读数（权重文件/大小/引擎/耗时/tok），失败也留 —— 上层
   `bridge.invoke` / `run_task` 的账本照旧记这一笔。

它**不是**第二套路由权威：权威仍是 `semantic_route`。本模块只做「主路的一个本地车道」，
`semantic_route.available()` 认它、`semantic_route.choose()` 先走它、失败才落到云端车道
与词表辅路 —— 降级链的每一档都如实标注（`path` / `degraded_reason`）。

用法（主干内）：

    from gbt_allinone.tentacle import commander as C
    C.status()                     # 权重/引擎/模型 三项现读
    C.start()                      # 起本机引擎（幂等）
    C.route("帮我把这段文字塞进剪贴板")   # → {"ok": True, "method": "clipboard_copy", ...}

用法（唯一门上）：

    gbt.run_task("commander", {"op": "status"})
    gbt.run_task("commander", {"op": "route", "intent": "看看现在有哪些窗口"})
"""
from __future__ import annotations

import json
import math
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

# ── 路径（与 LAYOUT.md 对齐：权重在 state/weights，二进制在 vendor/，运行态在 state/commander）──
ROOT = pathlib.Path(__file__).resolve().parents[2]
WEIGHTS_DIR = ROOT / "state" / "weights"
RUN_DIR = ROOT / "state" / "commander"
ACTIVE_JSON = WEIGHTS_DIR / "ACTIVE.json"
PID_FILE = RUN_DIR / "engine.pid"
LOG_FILE = RUN_DIR / "engine.log"

# 同一个文件可能以多种扩展名列在盘上；顺序 = 主观优先级（q5_0 是 WEIGHTS.md 的主道档位）
PREFERRED = (
    "gbt-v8-v82-q5_0.gguf",
    "gbt-v8-v82-q8_0.gguf",
    "gbt-v8-v82-fp16-fixed.gguf",
    "gbt-v8-v82-q4_0-fixed.gguf",
)

DEFAULT_BASE = "http://127.0.0.1:8792"
DEFAULT_CTX = 2048
DEFAULT_IDLE_S = 600          # 按需激活：10 分钟没人用就睡（卸权重、让内存），下次请求再醒
DEFAULT_THREADS = max(4, (os.cpu_count() or 8) - 4)   # 16 核 → 12：留 4 核给系统与触手，别把机器吃干

SYSTEM = (
    "你是 GBT小土豆V8 的总指挥模型。任务：从候选清单里挑出最贴合意图的那一个。"
    "只输出那个名字本身，一行，不加解释、不加序号、不加标点、不写成 JSON。"
    "清单里没有合适的就只输出：none"
)


# ══════════════════════════════════════════════════════════════════════════
# 权重：现读盘上，不编默认值
# ══════════════════════════════════════════════════════════════════════════
def weights() -> dict:
    """现读「本机有没有指挥官权重」。

    三档来源，**先显式后惯例**：
      ① 环境变量 `GBT_COMMANDER_GGUF`（换版权重只改这一处，不碰代码）
      ② `state/weights/ACTIVE.json`（框架自己的唯一指针：`{"model": "xxx.gguf", ...}`）
      ③ 按 `PREFERRED` 顺序扫 `state/weights/*.gguf`

    读不到就 `ok: False` 并列出**看过哪些位置** —— 不猜、不回落到"大概在哪儿"。
    """
    seen = []
    env = os.environ.get("GBT_COMMANDER_GGUF", "").strip()
    if env:
        seen.append(env)
        p = pathlib.Path(env)
        if p.is_file():
            return _w_ok(p, "env:GBT_COMMANDER_GGUF")
    if ACTIVE_JSON.is_file():
        try:
            rec = json.loads(ACTIVE_JSON.read_text(encoding="utf-8"))
            # 仓里既有口径叫 `active_artifact`（key_gateway 的现役权重指针），三个名字都认。
            name = str(rec.get("active_artifact") or rec.get("model")
                       or rec.get("path") or rec.get("file") or "").strip()
            if name:
                p = pathlib.Path(name)
                if not p.is_absolute():
                    p = WEIGHTS_DIR / name
                seen.append(str(p))
                if p.is_file():
                    return _w_ok(p, "state/weights/ACTIVE.json")
        except Exception as e:  # noqa: BLE001
            seen.append("ACTIVE.json 读不动: %s" % type(e).__name__)
    for name in PREFERRED:
        p = WEIGHTS_DIR / name
        seen.append(str(p))
        if p.is_file():
            return _w_ok(p, "state/weights 惯例扫描")
    if WEIGHTS_DIR.is_dir():
        for p in sorted(WEIGHTS_DIR.glob("*.gguf")):
            seen.append(str(p))
            return _w_ok(p, "state/weights 任意 *.gguf")
    return {"ok": False, "reason": "盘上没有指挥官权重（.gguf）",
            "looked": seen, "dir": str(WEIGHTS_DIR),
            "how": "把权重放到 state/weights/，或设 GBT_COMMANDER_GGUF=<路径>；"
                   "分片下载+合并见 WEIGHTS.md"}


def _w_ok(p: pathlib.Path, source: str) -> dict:
    st = p.stat()
    return {"ok": True, "path": str(p), "size_gb": round(st.st_size / 1e9, 2),
            "mtime": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime)),
            "source": source, "name": p.name}


# ══════════════════════════════════════════════════════════════════════════
# 引擎：先探活，再决定要不要起
# ══════════════════════════════════════════════════════════════════════════
def endpoint() -> str:
    return (os.environ.get("GBT_COMMANDER_BASE") or DEFAULT_BASE).rstrip("/")


def _http(url: str, body: dict | None = None, timeout: float = 5.0) -> dict:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="GET" if body is None else "POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "gbt-commander/1.0")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "replace")
    return json.loads(raw) if raw.strip().startswith(("{", "[")) else {"raw": raw}


def alive(base: str | None = None, timeout: float = 1.5) -> dict:
    """引擎活没活：**真打一次 HTTP**，不看进程名（进程在 ≠ 能服务）。"""
    base = (base or endpoint()).rstrip("/")
    last = "不可达"
    for path in ("/health", "/v1/models"):
        try:
            r = _http(base + path, timeout=timeout)
            if path == "/v1/models":
                models = [m.get("id") for m in (r.get("data") or []) if isinstance(m, dict)]
                return {"ok": True, "base": base, "models": models, "via": path}
            return {"ok": True, "base": base, "health": r, "via": path}
        except Exception as e:  # noqa: BLE001
            last = "%s: %s" % (type(e).__name__, str(e)[:120])
    return {"ok": False, "base": base, "error": last}


def _engine_bin() -> dict:
    """找 llama-server：先环境变量，再 vendor/ 下递归找（llama.cpp 官方 Windows 包）。"""
    env = os.environ.get("GBT_COMMANDER_ENGINE", "").strip()
    if env and pathlib.Path(env).is_file():
        return {"ok": True, "path": env, "kind": "llama-server", "source": "env"}
    for cand in (ROOT / "vendor").glob("**/llama-server.exe") if (ROOT / "vendor").is_dir() else []:
        return {"ok": True, "path": str(cand), "kind": "llama-server", "source": "vendor 扫描"}
    return {"ok": False, "reason": "vendor/ 下没有 llama-server.exe",
            "how": "下 llama.cpp 官方 win-cpu 包解到 vendor/，或设 GBT_COMMANDER_ENGINE=<exe>"}


def start(ctx: int = DEFAULT_CTX, threads: int = DEFAULT_THREADS,
          base: str | None = None, wait: float = 120.0, force: bool = False,
          idle_s: int = DEFAULT_IDLE_S) -> dict:
    """起本机引擎（幂等）：已经在服务就直接复用，不重复起第二个进程。

    `idle_s`：**按需激活**的那一半 —— 传 `--sleep-idle-seconds N`，N 秒没人用引擎自己睡
    （卸权重、让出内存），下一次请求来了再醒来加载。0 = 不睡（常驻）。
    """
    base = (base or endpoint()).rstrip("/")
    here = alive(base)
    if here.get("ok") and not force:
        return {"ok": True, "already": True, "base": base, "models": here.get("models")}

    w = weights()
    if not w.get("ok"):
        return {"ok": False, "stage": "weights", **w}
    eng = _engine_bin()
    if not eng.get("ok"):
        return {"ok": False, "stage": "engine", **eng}

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    port = base.rsplit(":", 1)[-1]
    cmd = [eng["path"], "-m", w["path"], "--host", "127.0.0.1", "--port", port,
           "-c", str(int(ctx)), "-t", str(int(threads)), "-ngl", "0", "--no-webui"]
    if idle_s and int(idle_s) > 0:
        cmd += ["--sleep-idle-seconds", str(int(idle_s))]
    log = open(LOG_FILE, "ab")                                   # noqa: SIM115
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                            cwd=str(ROOT), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")

    deadline = t0 + wait
    while time.time() < deadline:
        if proc.poll() is not None:
            tail = _tail(LOG_FILE)
            return {"ok": False, "stage": "boot", "exit": proc.returncode, "log_tail": tail,
                    "cmd": cmd, "hint": "看 state/commander/engine.log 尾部"}
        h = alive(base, timeout=1.0)
        if h.get("ok"):
            return {"ok": True, "already": False, "pid": proc.pid, "base": base,
                    "boot_s": round(time.time() - t0, 1), "weights": w, "engine": eng,
                    "models": h.get("models")}
        time.sleep(1.0)
    return {"ok": False, "stage": "timeout", "waited_s": wait, "pid": proc.pid,
            "log_tail": _tail(LOG_FILE)}


def stop() -> dict:
    """停引擎：只停**我们自己起的那一个**（按 pid 文件），不误杀别人的服务。"""
    if not PID_FILE.is_file():
        return {"ok": True, "stopped": False, "reason": "没有 pid 文件（不是本模块起的）"}
    try:
        pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        PID_FILE.unlink(missing_ok=True)
        return {"ok": False, "reason": "pid 文件读不懂，已清掉"}
    if sys.platform == "win32":
        r = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           capture_output=True, text=True)
        ok = r.returncode == 0
    else:
        import signal
        try:
            os.kill(pid, signal.SIGTERM)
            ok = True
        except Exception:  # noqa: BLE001
            ok = False
    PID_FILE.unlink(missing_ok=True)
    return {"ok": ok, "stopped": True, "pid": pid}


def _tail(path: pathlib.Path, n: int = 12) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-n:]
    except Exception:  # noqa: BLE001
        return []


# ══════════════════════════════════════════════════════════════════════════
# 对话：OpenAI 兼容，一次一问
# ══════════════════════════════════════════════════════════════════════════
def ask(messages: list[dict], *, temperature: float = 0.0, max_tokens: int = 256,
        timeout: float = 240.0, base: str | None = None, grammar: str | None = None,
        logprobs: bool = False) -> dict:
    """问本机权重一句话。**不重试、不静默兜底**：失败就把原话带回来。"""
    base = (base or endpoint()).rstrip("/")
    body = {"messages": messages, "temperature": temperature, "max_tokens": int(max_tokens),
            "stream": False}
    if logprobs:
        # 置信度来源：llama-server 的 OpenAI 形状（choices[0].logprobs.content[i].logprob）
        body["logprobs"] = True
        body["top_logprobs"] = 1
    if grammar:
        # GBNF 约束解码（llama.cpp 原生支持）：**输出只可能是候选里的名字或 none**。
        # 实测动因：204 项里 18 个 miss，其中 13 个是"模型自己造名字"（如 operate_on_thing），
        # 这是格式问题不是判断问题 —— 用文法把它从"可能"变成"不可能"。
        body["grammar"] = grammar
    t0 = time.time()
    try:
        r = _http(base + "/v1/chat/completions", body, timeout=timeout)
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": "HTTP %s" % e.code,
                "detail": (e.read() or b"").decode("utf-8", "replace")[:300]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:200]),
                "hint": "引擎没起？`commander op=start` 或 GBT_COMMANDER_BASE 指到在跑的服务"}
    elapsed = int((time.time() - t0) * 1000)
    try:
        choice = (r.get("choices") or [{}])[0]
        text = ((choice.get("message") or {}).get("content") or "").strip()
    except Exception:  # noqa: BLE001
        return {"ok": False, "error": "响应形状不对", "resp": json.dumps(r)[:300]}
    usage = r.get("usage") or {}
    _lp = None
    if logprobs:
        try:
            _lp = (choice.get("logprobs") or {}).get("content") or []
        except Exception:  # noqa: BLE001
            _lp = None
    return {"ok": bool(text), "text": text, "ms": elapsed, "logprobs": _lp,
            "usage": {k: usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens") if k in usage},
            "model": r.get("model")}


# ══════════════════════════════════════════════════════════════════════════
# 主干路由：召回 → 让权重选 → 校验 → 如实返回
# ══════════════════════════════════════════════════════════════════════════
def catalog_caps() -> list[dict]:
    """本体能力位清单（**现读**）：以 `caps_registry.BENIGN_CAPS` 为真源，
    拿 `data/capabilities.json` 补 desc/域（那个文件是生成的，可能略旧）。

    「全方位不能遗漏」（主人 2026-10-31）要求候选空间覆盖**每一位能力**，
    所以这里不做任何过滤：哪怕它自述是骨架，也进候选——能不能选得中由读数说话。
    """
    caps: dict[str, dict] = {}
    try:
        from ..caps_registry import BENIGN_CAPS
        for name, meta in BENIGN_CAPS.items():
            caps[name] = {"name": name, "domain": str(meta.get("domain") or "?"),
                          "desc": str(meta.get("desc") or "")}
    except Exception:  # noqa: BLE001
        pass
    try:
        p = ROOT / "data" / "capabilities.json"
        if p.is_file():
            for rec in json.loads(p.read_text(encoding="utf-8")).get("capabilities") or []:
                name = str(rec.get("name") or "")
                if not name:
                    continue
                caps.setdefault(name, {"name": name, "domain": str(rec.get("domain") or "?"),
                                       "desc": str(rec.get("desc") or "")})
                if not caps[name].get("desc"):
                    caps[name]["desc"] = str(rec.get("desc") or "")
    except Exception:  # noqa: BLE001
        pass
    return [caps[k] for k in sorted(caps)]


def _shortlist(intent: str, k: int = 10, space: str = "auto",
               restrict: set | None = None) -> list[dict]:
    """从**真名表**里召回 k 个候选（不扩表、不造句）。

    打分只用事实：名字 / 别名 / 邻域（能力另有 desc 前段）的 2-gram 命中数 + 最长公共子串。
    名字命中权重最高（名字是"这东西叫什么"，比描述更硬）。

    `space`: `method`=只要触手方法 · `cap`=只要本体能力 · `auto`=两边都要（默认）。
    「全方位不能遗漏」就落在这个 `auto` 上：候选池 = 95 只手 + 351 位能力。
    """
    from .. import semantic_route as SR
    from . import bridge as TB
    pool: list[dict] = []
    if space in ("auto", "method"):
        table = (SR.method_table() or {}).get("items") or []
        if not table:                                # 退一步：直接读 bridge 的邻域表
            table = [{"method": m, "neighborhood": dom, "hint": ""}
                     for dom, info in TB.TENTACLE_NEIGHBORHOOD_MAP.items()
                     for m in info["powered_by"]]
        for rec in table:
            name = str(rec.get("method") or "")
            if not name:
                continue
            pool.append({"space": "method", "name": name,
                         "hint": str(rec.get("hint") or TB.INTENT_ALIASES.get(name, "") or ""),
                         "dom": str(rec.get("neighborhood") or "")})
    if space in ("auto", "cap"):
        for rec in catalog_caps():
            pool.append({"space": "cap", "name": rec["name"], "hint": rec["desc"][:120],
                         "dom": rec["domain"]})
    if restrict:
        # 人工词表命中时，候选池收窄到**人自己点名的那几位**（少而准，模型只需在 2-3 个里挑）
        narrowed = [p for p in pool if p["name"] in restrict]
        if narrowed:
            pool = narrowed
    low = str(intent or "").lower()
    toks = SR.grams(str(intent or "")) | set(low.split())

    # ① 人工词表强权重（data/intent-lexicon.json）：它的 note 写得很清楚 ——
    #    「命中即给强权重，未命中退回按稀有度加权的全文检索」。这不是我新造的尺子，
    #    是仓里原有的那一把；这里只是把它接进本机权重车道的召回。
    boost = _lexicon_boost(low)

    # ② 稀有度（IDF）：池子里越少见的词越有区分度（「漏洞」比「一下」值钱得多）
    faces = []
    df: dict[str, int] = {}
    for rec in pool:
        face = " ".join([rec["name"].replace("_", " "), rec["hint"][:90], rec["dom"]]).lower()
        ftoks = SR.grams(face) | set(face.split())
        faces.append(ftoks)
        for t in ftoks:
            df[t] = df.get(t, 0) + 1
    n = max(1, len(pool))
    import math

    def idf(t: str) -> float:
        return math.log(1.0 + n / (1.0 + df.get(t, 0)))

    rows = []
    for rec, ftoks in zip(pool, faces):
        name = rec["name"]
        ntoks = SR.grams(name.replace("_", " ")) | set(name.split("_"))
        body = sum(idf(t) for t in (toks & ftoks))
        nmatch = sum(idf(t) for t in (toks & ntoks))
        norm = math.sqrt(max(1, len(ftoks)))
        score = (body / norm) + 2.0 * (nmatch / math.sqrt(max(1, len(ntoks))))
        score += 0.35 * boost.get(name, 0.0)
        score += 0.02 * _lcs(name.replace("_", " "), low)
        rows.append((score, nmatch, boost.get(name, 0.0), name, rec))
    rows.sort(key=lambda r: (-r[0], -r[1], -r[2], r[3]))
    return [dict(r[4]) for r in rows[:k]]


_LEX_CACHE: dict | None = None


def _lexicon_boost(low: str) -> dict:
    """人工词表命中 → 给对应能力位加权（`{cap: 权重}`）。读不到就空表，不猜。"""
    global _LEX_CACHE
    if _LEX_CACHE is None:
        _LEX_CACHE = {}
        try:
            p = ROOT / "data" / "intent-lexicon.json"
            if p.is_file():
                for entry in json.loads(p.read_text(encoding="utf-8")).get("intents") or []:
                    for caps in (entry.get("caps") or {}).items():
                        _LEX_CACHE.setdefault(str(caps[0]), []).append(
                            (list(entry.get("say") or []), float(caps[1] or 0)))
        except Exception:  # noqa: BLE001
            _LEX_CACHE = {}
    out: dict[str, float] = {}
    for cap, rules in _LEX_CACHE.items():
        for says, w in rules:
            hits = sum(1 for s in says if s and str(s).lower() in low)
            if hits:
                out[cap] = out.get(cap, 0.0) + w * hits
    return out


def _lcs(a: str, b: str) -> int:
    best = 0
    for i in range(len(a)):
        for j in range(i + best + 1, len(a) + 1):
            if a[i:j] in b:
                best = j - i
            else:
                break
    return best


def _parse_json(text: str) -> dict | None:
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return None
    return data if isinstance(data, dict) else None


_MEMORY_CACHE: dict = {"at": 0.0, "text": ""}


def memory_text(max_chars: int = 1200) -> str:
    """常驻记忆条：能力面 + 部署规则，**默认进每次判决的 system**（60s 缓存）。

    主人 2026-11-01：「部署规则和原生能力每一项都刻入大模型的肌肉记忆」——
    肌肉记忆 = 不用问就摆在 prompt 里。代价：约 700 字符（≈350 token），
    在 2048 上下文里可接受；`route(..., use_memory=False)` 可关（对照用）。
    """
    now = time.time()
    if _MEMORY_CACHE["text"] and now - _MEMORY_CACHE["at"] < 60:
        return _MEMORY_CACHE["text"]
    try:
        from . import cap_self as CS
        txt = (CS.brief(max_chars=max_chars) or {}).get("text") or ""
    except Exception:  # noqa: BLE001
        txt = ""
    _MEMORY_CACHE.update({"at": now, "text": txt})
    return txt


def _match_name(raw: str, by_name: dict) -> str | None:
    """从模型的一行输出里认出**候选里的真名**；认不出就 None（绝不模糊替它猜一个）。

    为什么要有这一层：实测本模型（v82）是用「JSON 动作」训练的，给 `{"pick": ...}`
    的格式它会回 `{"op":"clip",...}` —— 换成人话「只输出名字」它反而一次就中
    （实测 `clipboard_copy`）。所以这里既认纯名字，也认名字外面裹了标点/括号的写法。
    """
    t = str(raw or "").strip().strip("`'\"。.，,：: \n\r\t")
    if not t:
        return None
    if t in by_name:
        return t
    low = t.lower()
    hits = [n for n in by_name if n.lower() in low]
    if hits:
        return max(hits, key=len)
    return None



def _confidence(name: str, content: list) -> float | None:
    """被选名字那一段 token 的**联合概率**（exp(Σ logprob)）。

    口径：只累计到「拼起来还是 name 的前缀」的那些 token —— 名字后面爱写什么不管，
    但名字本身要是靠猜的，这条就会很低。读不到 logprobs 就返回 None（不编）。
    """
    if not name or not content:
        return None
    acc, total = "", 0.0
    for item in content:
        tok = str(item.get("token") or "")
        if not tok:
            continue
        if name.startswith(acc + tok):
            acc += tok
            total += float(item.get("logprob") or 0.0)
            if acc == name:
                return math.exp(total)
        elif acc:
            break
        else:
            # 第一个 token 就不是名字的开头 ⇒ 直接判低置信
            return None
    return math.exp(total) if acc else None


def route(intent: str, *, k: int = 10, space: str = "auto", timeout: float = 240.0,
          use_grammar: bool = False, min_conf: float | None = None,
          use_lexicon: bool = True, use_memory: bool = True,
          pulse: bool = True) -> dict:
    """意图 → 一个**真名**（触手方法或本体能力位）。判决必须落在候选里，落不进去就如实判无效。

    `space` 由调用方决定：主干 `semantic_route` 要的是"哪只手"（method），
    而「全方位不能遗漏」的核对要的是"能力/手都算"（auto，默认）。
    """
    text = str(intent or "").strip()
    if not text:
        return {"ok": False, "path": "commander", "error": "需要 intent"}
    h = alive()
    if not h.get("ok"):
        return {"ok": False, "path": "commander", "error": "本机引擎不可达",
                "base": h.get("base"), "detail": h.get("error")}

    # 人工词表（data/intent-lexicon.json）命中就收窄候选：
    # 2026-11-01 实测动因：短意图（"审计"/"镜像"/"字数"）模型选错兄弟，
    # 而人早已把「审计→audit_query(10)/caps_called_audit(4)」写死在词表里 —— 那是人的判断，
    # 比 7.6B 在 12 个候选里瞎挑可靠。收窄只**减少候选**，最终仍由权重选，不替它拍板。
    _lex = _lexicon_boost(text.lower()) if use_lexicon else {}
    _restrict = set(_lex) if _lex else None
    cands = _shortlist(text, k, space, restrict=_restrict)
    if not cands:
        return {"ok": False, "path": "commander", "error": "候选池为空，无法召回"}
    by_name = {c["name"]: c for c in cands}
    menu = "\n".join("%d. %s —— %s" % (i + 1, c["name"], (c["hint"] or "无说明")[:30])
                     for i, c in enumerate(cands))
    # 2026-11-01：先过**脉冲直达**（0 token、毫秒级）。人写 24 条实测：直达 17/24、正确 15、
    # 平均 2.3ms；同批权重判决 16/24、平均 66s。⇒ 能直达就不取电，直接省掉一次 40s 级调用。
    if pulse:
        try:
            from . import pulse_core as _PC
            d = _PC.direct(text)
            if d.get("hit"):
                return {"ok": True, "path": "pulse_direct", "name": d.get("name"),
                        "space": "auto", "confidence": None, "lexicon_scoped": False,
                        "memory_chars": 0, "tokens": 0, "pulse": True,
                        "why": d.get("why"), "ambiguous": d.get("ambiguous", False),
                        "candidates": [d.get("name")], "ms": d.get("ms")}
        except Exception:  # noqa: BLE001
            pass
    _mem = memory_text() if use_memory else ""
    _sys = SYSTEM + ("\n\n" + _mem if _mem else "")
    msg = [{"role": "system", "content": _sys},
           {"role": "user", "content": "意图：%s\n\n候选：\n%s\n\n"
                                       "只从上面这些名字里**逐字抄一个**；都不合适就输出 none。"
                                       "一行，不要别的字。"
                                       % (text[:300], menu)}]

    # 约束解码：输出只可能是候选名或 none（llama.cpp 原生 GBNF）。
    # 为什么：204 项实测里 18 个 miss，13 个是"造名字"——那是格式毛病，用文法直接消灭；
    # 同时把 none 留在文法里 ⇒ 模型拿不准时仍能**如实说没有**，不逼它硬选。
    _alts = ["none"] + list(by_name)
    grammar = "root ::= " + " | ".join('"%s"' % n for n in _alts)

    # 2026-11-01（实测驱动，**结论是不加重试**）：
    # 7.6B 模型会自己造名字（实测「回车确认键」回了 operate_on_thing，不在候选里）。
    # 试过「纠正一次」，同 4 条实测：救回 2 条（grab_pixel / absorb_loop），却把 1 条
    # **从诚实失败变成错误答案**（回车 → absorb_loop，只因它排在清单第一个）。
    # ⇒ 按本仓铁律「宁可如实报错，绝不静默造假」：**回退成单次判决**，认不出就判无效。
    #    另外补一个 JSON 兜底键 action（它训练时用 action 命名动作）。
    # ⚠️ 2026-11-01 实测后**默认关闭**（use_grammar=False）：
    #    开文法确实消灭了"造名字"（无效输出 13/18 → 0），但同 4 条实测里 3 条从
    #    「诚实失败」变成「自信的错误答案」（回车→action_gate、撤销→pulse_direct），
    #    而且单次耗时从 25–40s 涨到 70–95s。按本仓铁律「宁可如实报错」，默认走裸判决；
    #    要开：route(..., use_grammar=True)，并配置信度门（logprobs）再谈默认。
    r = ask(msg, temperature=0.0, max_tokens=24, timeout=timeout,
            grammar=(grammar if use_grammar else None), logprobs=True)
    if not r.get("ok"):
        return {"ok": False, "path": "commander", "error": r.get("error"),
                "detail": r.get("detail"), "candidates": sorted(by_name),
                "ms": r.get("ms")}
    raw = (r.get("text") or "").strip()
    if raw.strip().lower() == "none":
        return {"ok": False, "path": "commander", "error": "模型判定候选里没有合适的（none）",
                "candidates": sorted(by_name), "ms": r.get("ms"),
                "attempts": [{"attempt": 1, "raw": raw[:80], "ok": False}]}
    picked = _match_name(raw, by_name)
    data: dict | None = None
    if not picked:
        data = _parse_json(raw)
        if isinstance(data, dict):
            picked = _match_name(str(data.get("pick") or data.get("method")
                                     or data.get("name") or data.get("action")
                                     or data.get("op") or ""), by_name)
    if not picked:
        return {"ok": False, "path": "commander", "error": "模型没有给出候选里的名字 ⇒ 不采信",
                "raw": raw[:200], "attempts": [{"attempt": 1, "raw": raw[:80], "ok": True}],
                "candidates": sorted(by_name), "ms": r.get("ms")}
    hit = by_name[picked]
    conf = _confidence(picked, r.get("logprobs") or [])
    # 可选置信度门（默认 None = 不拦）。为什么默认不拦：2026-11-01 实测三例孪生位误选，
    # 置信度分别是 0.993 / 0.999 / 0.458 —— **高置信地错**，门拦不住"选错兄弟"，
    # 只拦得住"本来就没把握"（那种多数表现为给出候选外的名字，已经被判无效）。
    if min_conf is not None and conf is not None and conf < float(min_conf):
        return {"ok": False, "path": "commander",
                "error": "低置信（p=%.3f < 门 %.2f）⇒ 不直达，交上层降级" % (conf, float(min_conf)),
                "confidence": round(conf, 3), "candidates": sorted(by_name),
                "ms": r.get("ms")}
    out = {"ok": True, "path": "commander", "space": hit["space"], "name": picked,
           "confidence": (round(conf, 3) if conf is not None else None),
           "lexicon_scoped": bool(_lex),
           "memory_chars": len(_mem),
           "why": str((data or {}).get("why") or "")[:60], "candidates": sorted(by_name),
           "weights": weights().get("name"), "ms": r.get("ms"), "usage": r.get("usage"),
           "attempts": [{"attempt": 1, "raw": raw[:80], "ok": True}]}
    out["method" if hit["space"] == "method" else "capability"] = picked
    return out


def status() -> dict:
    """三件套现读：权重 / 引擎 / 模型。缺哪件说哪件，不含糊。"""
    w = weights()
    h = alive()
    eng = _engine_bin()
    return {"ok": bool(w.get("ok") and h.get("ok")),
            "weights": w, "engine_bin": eng,
            "endpoint": h, "base": endpoint(),
            "threads_default": DEFAULT_THREADS, "ctx_default": DEFAULT_CTX,
            "lane": "gbt-commander（本机权重 · 不出网 · 不要 external_llm 票）",
            "gate": "op=start/stop 起停本机进程 ⇒ process_execute；route/ask/status 本地只读 ⇒ 零作用域"}


def run(op: str = "status", **kw) -> dict:
    """能力位入口（`api._run_benign` 的 `kind == "commander"` 分支调这里）。"""
    op = str(op or "status").lower()
    if op == "status":
        return status()
    if op == "route":
        return route(kw.get("intent") or kw.get("text") or "",
                     space=str(kw.get("space") or "auto").lower())
    if op == "ask":
        msg = kw.get("messages")
        if not msg and kw.get("text"):
            msg = [{"role": "user", "content": str(kw["text"])}]
        if not msg:
            return {"ok": False, "error": "ask 需要 messages 或 text"}
        return ask(msg, temperature=float(kw.get("temperature") or 0.0),
                   max_tokens=int(kw.get("max_tokens") or 256))
    if op == "start":
        return start(ctx=int(kw.get("ctx") or DEFAULT_CTX),
                     threads=int(kw.get("threads") or DEFAULT_THREADS),
                     idle_s=int(kw.get("idle_s") if kw.get("idle_s") is not None else DEFAULT_IDLE_S),
                     force=bool(kw.get("force")))
    if op == "stop":
        return stop()
    return {"ok": False, "error": "commander 不认 op=%s（status/route/ask/start/stop）" % op}
