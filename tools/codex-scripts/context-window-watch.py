# -*- coding: utf-8 -*-
"""上下文触手 · 窗口自纠（Owner 令 2026-10-14：「插在上下文那里的触手要发现异常就自我纠正」）。

为什么分两段（照框架规矩，不是我偷懒）：
  ① 写仓外配置**被落点门明令挡住** —— omni_plug file 插座实测回执：
     reason="写面只限仓内，这条到仓外了：C:\\Users\\ADMIN\\.codex\\models.json"（WRITE_ROOTS=projects/outputs/.scratch）
  ② 所以 **仓内这一段我自己纠**（算值·出补丁·留痕·坏了自己回滚），**仓外那一跳归主人**（一条命令）。

自纠判据（fail-closed，全部机械）：
  W1 上游真实窗口测不到            -> 红（不许把"没测到"当"没漂移"）
  W2 声明窗口 > 实测窗口（会撞 5021）-> 红（这是今天真栽的坑）
  W3 漂移 > 20%                    -> 红
  W4 auto_compact_token_limit 为空 -> 红（自动压缩没开 = 没人拦）
  W5 无法读出声明面                -> 红
用法：
  py -3.14 tools/codex-scripts/context-window-watch.py            # 体检（红则非零退出）
  py -3.14 tools/codex-scripts/context-window-watch.py --fix      # 顺手把补丁写进 outputs/context-align/
  py -3.14 tools/codex-scripts/context-window-watch.py --selftest # 正例绿 / 负例红

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import struct
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "context-align"
MODELS = pathlib.Path(os.path.expanduser("~/.codex/models.json"))
ENDPOINT = "https://gbt-potato-cloud-10.lopaycn.workers.dev/v1/chat/completions"
# 2026-10-21 口径翻正（留痕 · 谁改的、为什么改、原期望是什么）：
#   原期望：「探上游真实输入上限」= 探**页面/Codex 真正在走的那条腿**。
#   实际情况：`ENDPOINT` 写死 **lopaycn 旧账号子域**；而 Codex 车道现读是
#     `GBT_POTATO_BASE_URL` = https://api.runpod.ai/v2/qnnqf9w8xcefj8/openai/v1（8317 翻译层转过去），
#     DSH 页面 2026-10-21 起也直连同一端点 ⇒ 体检打的是**第三方旧域**，量出来的
#     23,103 字符 ≈ 14,439 tokens 与真实车道无关，于是 W2/W3 天天红、还红错了对象。
#   ⇒ 现在：端点按 **HKCU\Environment\GBT_POTATO_BASE_URL** 现读（缺省才回落到上面的常量），
#     钥按 GBT_POTATO_API_KEY → GBT_CLIPROXY_KEY → DPAPI 保险箱 依次取；
#     并且**先问端点自己的 `/v1/models` 的 `max_model_len`**（服务端自报，权威），
#     二分只作交叉印证（量程抬到能测 32k 以上，原来 hi=14000 单位根本测不到）。
FIVE = ROOT / "tools" / "codex-scripts" / "five-dim.py"
DRIFT_RED = 0.20


def log(*a) -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                       # noqa: BLE001
            pass
    print(*a)


def declared() -> dict:
    """读声明面。优先走门（file 插座读，实测允许），失败才回落到直接读（并如实标注）。"""
    via = "direct"
    try:
        r = subprocess.run([sys.executable, str(FIVE), "cap", "omni_plug",
                            json.dumps({"op": "run", "socket": "file", "target": str(MODELS).replace("\\", "/"), "do": "read"})],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)
        doc = json.loads(r.stdout or "{}")
        raw = ((doc.get("result") or {}).get("read") or "")
        if raw.strip():
            via = "gate(omni_plug/file)"
            j = json.loads(raw)
        else:
            j = json.loads(MODELS.read_text(encoding="utf-8"))
    except Exception:                                           # noqa: BLE001
        j = json.loads(MODELS.read_text(encoding="utf-8"))
    found = []

    def walk(o):
        if isinstance(o, dict):
            if "context_window" in o or "auto_compact_token_limit" in o:
                found.append({"slug": o.get("slug") or o.get("model") or "?", "context_window": o.get("context_window"),
                              "auto_compact_token_limit": o.get("auto_compact_token_limit")})
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(j)
    return {"via": via, "entries": found}


def _env_or_reg(name: str) -> str:
    """环境变量 → User 注册表（setx 写的就在那层，门/沙箱起的进程常常是空环境）。"""
    v = os.environ.get(name) or ""
    if v:
        return v
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return str(winreg.QueryValueEx(k, name)[0] or "")
    except Exception:                                           # noqa: BLE001
        return ""


def _lane() -> tuple[str, str, str]:
    """现读「真正在走的那条腿」：端点 + 钥 + 钥来源。

    端点取 `GBT_POTATO_BASE_URL`（8317 翻译层与 DSH 页面都指向它）；缺省才回落到常量。
    钥：GBT_POTATO_API_KEY → GBT_CLIPROXY_KEY → DPAPI 保险箱 profile=potato。
    """
    base = _env_or_reg("GBT_POTATO_BASE_URL").rstrip("/")
    if not base:
        base = ENDPOINT.rsplit("/chat/completions", 1)[0]
    for name in ("GBT_POTATO_API_KEY", "GBT_CLIPROXY_KEY"):
        k = _env_or_reg(name)
        if k:
            return base, k, "env/reg:" + name
    try:
        v = str(((json.loads(subprocess.run(
            [sys.executable, str(FIVE), "cap", "deepseek_key", json.dumps({"op": "status", "profile": "potato"})],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60).stdout or "{}")
            .get("result") or {}).get("masked") or ""))
    except Exception:                                           # noqa: BLE001
        pass
    try:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone.deepseek_key import load_key      # noqa: PLC0415
        k, src = load_key("potato")
        if k:
            return base, k, "vault:" + src
    except Exception:                                           # noqa: BLE001
        pass
    return base, "", "missing"


def _server_window(base: str, key: str, ua: str) -> dict:
    """问端点自己：`/v1/models` 的 `max_model_len` —— 服务端自报，比任何手写常量权威。

    重试 3 次（每次 30s，间隔 5s）：实测这台机器偶发整机变慢，一次超时就把
    "取不到读数" 念成 "窗口=0" 是假读数（本仓 P1 那类错），必须分开报。
    """
    last = ""
    for attempt in range(3):
        req = urllib.request.Request(base + "/models",
                                     headers={"Authorization": "Bearer " + key, "User-Agent": ua})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                d = json.loads(resp.read().decode("utf-8", "replace"))
            row = (d.get("data") or [{}])[0]
            n = row.get("max_model_len") or row.get("context_length")
            return {"ok": bool(n), "max_model_len": n, "model_id": row.get("id")}
        except Exception as exc:                                # noqa: BLE001
            last = "%s: %s" % (type(exc).__name__, str(exc)[:120])
            if attempt < 2:
                time.sleep(5)
    return {"ok": False, "detail": "取不到 /v1/models 读数（%s）—— 不是窗口=0" % last}


def probe() -> dict:
    """量上游真实输入上限。

    🔴 2026-10-21 顺序翻正：**先读服务端自报的 `max_model_len`**（权威），
       二分只作交叉印证；量程抬到能覆盖 32k（原来 hi=14000 个"占位。"单位 ≈ 42k 字符，
       换算是它自己写死的 1.6 字符/token ⇒ 结构上测不出 32k，会把真窗口报小）。
    """
    base, key, src = _lane()
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    if not key:
        return {"ok": False, "detail": "缺钥（GBT_POTATO_API_KEY / GBT_CLIPROXY_KEY / DPAPI 都没取到）—— 不是上游不通",
                "base": base}
    win = _server_window(base, key, ua)
 # 2026-10-21：模型 id 必须用**端点自报的那个**（直连引擎只认 `/runpod-volume/gbt-v8-v83`，
    #   写 `gbt-potato-v8` 会被 vLLM 判 model not found ⇒ 二分全 False、把"不通"栽给上游）。
    probe_model = win.get("model_id") or "gbt-potato-v8"
 # 2026-10-21：服务端自报优先就**别默认二分**。实测无服务器冷启动一次 6 分钟没回
    #   （/models 秒回、/chat/completions 挂住）⇒ 默认二分会让开机自检卡到超时，读数还变成"不通"。
    #   要交叉印证就显式 `GBT_WATCH_BISECT=1`。
    if win.get("ok") and not os.environ.get("GBT_WATCH_BISECT"):
        return {"ok": True, "server": win, "lane": {"base": base, "key": src},
                "max_tokens_reported": win.get("max_model_len"), "partial": True,
                "chars": 0, "detail": "只采信服务端自报（`/v1/models` max_model_len=%s · 模型 %s）；"
                                       "要二分交叉印证请设 GBT_WATCH_BISECT=1" % (win.get("max_model_len"), probe_model)}

    def fits(n: int) -> bool:
        body = json.dumps({"model": probe_model,
                           "messages": [{"role": "user", "content": "占位。" * n}], "max_tokens": 16}).encode()
        req = urllib.request.Request(base + "/chat/completions", data=body,
                                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": ua})
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return resp.status == 200
        except Exception:                                       # noqa: BLE001
            return False

    t0 = time.time()
    BUDGET = float(os.environ.get("GBT_WATCH_BUDGET") or 120)
    # 量程：以字符算，1 单位 = 3 字符；hi 抬到 40,000 单位（12 万字符）才够看 32k token
    lo, hi = 100, 40000
    if not fits(lo):
        return {"ok": bool(win.get("ok")), "server": win, "lane": {"base": base, "key": src},
                "max_tokens_reported": win.get("max_model_len"),
                "detail": "连最小请求都不通（服务端自报窗口=%s）" % win.get("max_model_len"), "partial": False}
    partial = False
    while hi - lo > 400:
        if time.time() - t0 > BUDGET:
            partial = True
            break
        mid = (lo + hi) // 2
        if fits(mid):
            lo = mid
        else:
            hi = mid
    return {"ok": True, "max_units": lo, "chars": lo * 3, "model": MODEL_HINT,
            "partial": partial, "elapsed_s": round(time.time() - t0, 1), "budget_s": BUDGET,
            "server": win, "lane": {"base": base, "key": src},
            "max_tokens_reported": win.get("max_model_len")}


MODEL_HINT = "（回执里的 upstream_model）"


def judge(d: dict, p: dict) -> list:
    """五条判据，返回条条带红绿。"""
    rows = []
    ent = [e for e in d["entries"] if e.get("slug") == "gbt-potato-v8"] or d["entries"]
    decl = max([e.get("context_window") or 0 for e in ent] or [0])
    ac = ent[0].get("auto_compact_token_limit") if ent else None
    real_tokens = int(p.get("chars", 0) / 1.6) if p.get("ok") else 0     # 粗口径：约 1.6 字符/token（中文为主）
 # 2026-10-21 口径翻正（留痕）：**优先采信服务端自报的 `max_model_len`**。
    #   原口径：只信二分出来的字符数 ÷ 1.6。问题：二分撞到旧端点、量程也只到 42k 字符，
    #     于是把 32k 的引擎报成 14,439 tokens，W2/W3 天天红在错对象上。
    #   现口径：`max_tokens_reported`（`/v1/models` 的 max_model_len）> 0 就用它当"实测"，
    #     二分值只作旁证并列打印；两者都拿不到才退回旧口径。
    reported = int(p.get("max_tokens_reported") or 0)
    if reported > 0:
        real_tokens = reported
    lane = p.get("lane") or {}
    rows.append(("W1 上游真实窗口可测", bool(p.get("ok")),
                 p.get("detail") or ("服务端自报 max_model_len=%s · 二分交叉印证 %d 字符 ≈ %d tokens%s · 车道 %s"
                                    % (reported or "未报", p.get("chars", 0), int(p.get("chars", 0) / 1.6),
                                       ("（未收敛·预算 %ss 内测到 %.1fs）" % (p.get("budget_s"), p.get("elapsed_s"))) if p.get("partial") else "",
                                       lane.get("base") or "?"))))
 # 2026-10-15：1.1% 的测量误差被判成红 ⇒ 会天天误报、天天拦门（实测：声明 13361 / 实测 13218）。
    #     ⇒ W2 加 **5% 容差**；且"未收敛"归**黄**（报出来但放行）。
    _tol = 1.05
    _w2 = bool(p.get("ok")) and real_tokens > 0 and decl > 0 and decl <= real_tokens * _tol
    _w2_yellow = (not _w2) and bool(p.get("partial"))
    rows.append(("W2 声明 <= 实测×(1+5%)", _w2 or _w2_yellow,
                 "声明 %s / 实测 %s%s" % (decl, real_tokens,
                                        "（黄：未收敛，放行）" if _w2_yellow else "（容差 5%）")))
    drift = (abs(decl - real_tokens) / real_tokens) if real_tokens else None
 # 2026-10-18 加（**假红** · 留痕 · 原口径/为什么翻/现口径）：
    #   原口径：漂移 > 20% 一律判红，不管实测是否收敛。
    #   为什么翻：实测 W1 报"未收敛（预算 90s 内测到 105.5s）"时，实测值本身没测完 ⇒ 漂移 40% 是**测不准**
    #     不是真漂移（同一配置两次跑出 13218 / 17696 两个值）。用不可靠读数判红 = 假红。
    #   现口径：仅当实测**收敛**时才按漂移判红；未收敛 ⇒ 标"未收敛·不判红"（W1 已如实报未收敛）。
    converged = not bool(p.get("partial"))
    w3_ok = (drift is not None) and (drift <= DRIFT_RED or not converged)
    rows.append(("W3 漂移 <= %d%%" % int(DRIFT_RED * 100), w3_ok,
                 (("漂移 %.1f%%" % (drift * 100)) if drift is not None else "测得不可用")
                 + ("" if converged else "（实测未收敛 ⇒ 不判红）")))
    rows.append(("W4 自动压缩已开", bool(ac), "auto_compact_token_limit=%s" % ac))
    rows.append(("W5 声明面可读", bool(d["entries"]), "via=%s · 条目 %d" % (d["via"], len(d["entries"]))))
    return rows


def fix(d: dict, p: dict) -> dict:
    """仓内自纠：把修正值 + 一键套用脚本 + 备份写进 outputs/context-align/。"""
    OUT.mkdir(parents=True, exist_ok=True)
    real_tokens = int(p.get("chars", 0) / 1.6) if p.get("ok") else 0
    reported = int(p.get("max_tokens_reported") or 0)
 # 2026-10-21：服务端自报窗口就是权威 ⇒ 直接用它，不再打 9 折（打折等于自废窗口）；
    #   压缩线按 62% 留余量（原来是 83%，加上被高估的窗口 ⇒ 压缩线偏高、容易撞裁切）。
    target = reported or max(1000, int(real_tokens * 0.9))
    stamp = time.strftime("%Y%m%d-%H%M%S")
    raw = MODELS.read_text(encoding="utf-8")
    (OUT / ("models.json.bak-" + stamp)).write_text(raw, encoding="utf-8")
    plan = {"ts": stamp, "endpoint": ENDPOINT, "lane": p.get("lane"), "server_reported": reported,
            "real_tokens_est": real_tokens,
            "declared": [e for e in d["entries"] if e.get("slug") == "gbt-potato-v8"] or d["entries"],
            "suggest": {"context_window": target, "auto_compact_token_limit": int(target * 0.62)},
            "note": "仓外写面归主人：跑 apply-context-align.ps1 一键套用（内含备份+回读校验）"}
    (OUT / "context-align.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    ps = ("# 一键套用（备份 -> 写 -> 回读校验）。由 context-window-watch --fix 生成\n"
          "$m = Join-Path $env:USERPROFILE '.codex\\models.json'\n"
          "Copy-Item $m ($m + '.bak-apply-' + (Get-Date -Format yyyyMMdd-HHmmss)) -Force\n"
          "$j = Get-Content $m -Raw | ConvertFrom-Json\n"
          "foreach ($x in $j.models) { if ($x.slug -eq 'gbt-potato-v8') {"
          " $x.context_window = %d; $x.auto_compact_token_limit = %d } }\n"
          "$j | ConvertTo-Json -Depth 12 | Set-Content $m -Encoding utf8\n"
          "Select-String -Path $m -Pattern 'context_window|auto_compact' | Select-Object -First 4\n") % (
        plan["suggest"]["context_window"], plan["suggest"]["auto_compact_token_limit"])
    (OUT / "apply-context-align.ps1").write_text(ps, encoding="utf-8")
    return plan


# ══════════════════════════════════════════════════════════════════════════
# 在役车道（本地自有权重）的窗口判据
#   为什么加（口径翻正 · 留痕 2026-10-25）：
#     上面 W1–W5 量的是 `GBT_POTATO_BASE_URL`（RunPod 翻译层）**那条云端车道**。
#     主人令「不用云端驱动，按需激活使用本地算力」之后，那条车道已退役 ⇒
#     W1/W2/W3 天天红，红的原因不是"漂移"，而是"量了一条不在役的路"。
#     **判据必须量在役的东西**（同 `lane-gate-free.py` 第 2/3 代改写的口径）。
#   新口径（五条，全部机检、全部可红）：
#     LW1 权重元数据窗口可读 —— 直接读 GGUF 头里的 `*.context_length`（真测量，不猜）
#     LW2 我们开的窗口 ≤ 模型上限 —— 超了 llama.cpp 直接不加载
#     LW3 我们开的窗口 ≥ 够用线（1024）—— 实测：645 tok 在 512 下 HTTP 500、2048 下正常
#     LW4 **环形窗口预算（字符→token）≤ 开的 ctx** ← 2026-10-28 补：原来没有任何一条判据
#         把这两个数放在一起比，于是 7011 token 配 2048 ctx 时**谁都不红**，直到线上撞 500
#     LW5 满窗口一发预估延迟 ≤ 90s —— 超了就**先过变压器压缩**（降 token 才既快又准）。
#         🔴 绝不能建议「切 fast 档」：fast 档 ctx 更小，装不下满窗口时会**静默截断并胡说**。
#   退出条件：云端车道若哪天复活（`/models` 能回模型条目），自动改回量云端（判据不变）。
# ══════════════════════════════════════════════════════════════════════════
GGUF = ROOT / "state" / "weights" / "gbt-v8-v82-q5_0.gguf"
SHELL_CJS = ROOT / "holo_pet_w3" / "shell" / "main.cjs"
GPU_LANE = ROOT / "tools" / "model-bridge" / "gpu_lane.py"
MIN_USEFUL_CTX = 1024          # 实测门槛：645 token 的请求在 512 下 500、2048 下正常
_GGUF_FIXED = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}

# ── 实测常数（全部带出处与日期，禁写「约」）──────────────────────────────
# 12000 字符 → 7000 token：真分词器 `/tokenize` 实测（2026-10-28）
CHARS_PER_TOKEN = 1.714
# ngl24 / ctx8192 下处理 7011 token prompt 的速率（2026-10-28 llama-server timings 实测）
PROMPT_TPS_LONG = 139.51
# 满窗口一发可接受的墙钟上限（超过就该切快档或先压缩）
FULL_WINDOW_S = 90.0
# 变压器（gbt_allinone/tools/transformer_cap.py）实测（2026-10-28）：
#   12016 字符（181 行纯叙述）→ target 3000 实得 3000，倍率 0.25，耗时 0.06 s；
#   target 6000 实得 6000，倍率 0.50，耗时 0.02 s。⇒ 压缩几乎免费，收益是线性省 prompt 时间。
# 🔴 2026-10-28 二次纠正：`TRANSFORMER_RATIO` 原写 0.25 —— 那是**合成重复文本**的倍率
#    （大量相同填充可被去重）。换**真实语料**（仓库文档正文 11864 字符 / 254 行）实测：
#    **只能压到 0.920**（11864 → 10914），几乎没压动。
#    ⇒ 指望「压缩救满窗口延迟」是幻想；LW5 的处方已改为先讲清这一点。
TRANSFORMER_RATIO = 0.92          # 真实语料（保守）；合成重复文本可到 0.25
TRANSFORMER_RATIO_SYNTHETIC = 0.25
# 🔴 2026-10-28 纠正：原来写死 0.06s —— 那是**命中缓存后**的读数，不是首次成本。
#    实测首次压缩约 3.98~5.17s（同参数第二次 0.03s）。拿缓存读数当常数 = 把最好的情况当常态。
TRANSFORMER_S = 5.17          # 首次（真实语料实测，保守）
TRANSFORMER_S_CACHED = 0.03   # 同参数重复（变压器自己有 simhash 缓存）


def gguf_meta_ints(path: pathlib.Path, want) -> dict:
    """手读 GGUF 头里的整型 KV（只读前几百字节，不加载模型）。

    3.14 里没装 `gguf` 包，所以自己按格式读；只读到找齐 `want` 就停。
    读不成返回 `{}` —— **读不成不等于 0**（本仓明令），调用方据此判红。
    """
    found = {}
    try:
        with open(path, "rb") as f:
            if f.read(4) != b"GGUF":
                return {}
            struct.unpack("<I", f.read(4))[0]                  # version
            struct.unpack("<Q", f.read(8))[0]                  # tensor_count
            n_kv = struct.unpack("<Q", f.read(8))[0]
            for _ in range(min(int(n_kv), 4096)):
                klen = struct.unpack("<Q", f.read(8))[0]
                key = f.read(int(klen)).decode("utf-8", "replace")
                vtype = struct.unpack("<I", f.read(4))[0]
                if vtype in _GGUF_FIXED:
                    raw = f.read(_GGUF_FIXED[vtype])
                    fmt = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I",
                           5: "<i", 6: "<f", 7: "<B", 10: "<Q", 11: "<q", 12: "<d"}[vtype]
                    val = struct.unpack(fmt, raw)[0]
                elif vtype == 8:                               # string
                    slen = struct.unpack("<Q", f.read(8))[0]
                    f.read(int(slen))
                    continue
                elif vtype == 9:                               # array
                    etype = struct.unpack("<I", f.read(4))[0]
                    n = struct.unpack("<Q", f.read(8))[0]
                    if etype in _GGUF_FIXED:
                        f.read(_GGUF_FIXED[etype] * int(n))
                    elif etype == 8:
                        for _i in range(int(n)):
                            slen = struct.unpack("<Q", f.read(8))[0]
                            f.read(int(slen))
                    else:
                        return found
                    continue
                else:
                    return found
                if any(key.endswith(w) for w in want):
                    found[key.rsplit(".", 1)[-1]] = int(val)
                if len(found) >= len(want):
                    break
    except Exception:                                          # noqa: BLE001
        return found
    return found


def lane_model() -> pathlib.Path:
    """在役车道**实际加载**的那份权重（用来读 context_length 上限）。

    🔴 2026-10-28 为什么加：原来 LW1 写死读 `q5_0.gguf`。换到 4 GB 显存的 q3_k_m 之后，
    q5_0 一旦被清掉，LW1 就会因为「文件不在」而假红 —— 量的不是车道在用的东西。
    现口径：**先看 gpu_lane 里 MODEL 指向谁**，取不到再回落 q5_0。
    """
    try:
        t = GPU_LANE.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'gbt-v8-v82-([\w.\-]+)\.gguf', t)
        if m:
            p = ROOT / "state" / "weights" / ("gbt-v8-v82-%s.gguf" % m.group(1))
            if p.is_file():
                return p
    except OSError:
        pass
    return GGUF


def shell_ctx(path: pathlib.Path) -> tuple:
    """在役车道**真正开的窗口**：返回 (值, 出处)。读不到返回 (0, 原因)。

    🔴 2026-10-28 为什么改：原来只读 `holo_pet_w3/shell/main.cjs` 的 `--ctx`。
    实测外壳**根本不起模型**（整份 grep 只有注释提到 `panel_server.py` 的 SSE 路由），
    真起 llama 的是 `tools/model-bridge/gpu_lane.py`（`-c` + `GBT_GPU_CTX`）。
    判据指着一个不管这事的文件 ⇒ 永远「找不到 --ctx」⇒ 正控上挂一条红，
    把「我们其实开了 2048」说成「读不到」。判据必须指**真正拥有该事实的那个件**。
    现在按真实起模型的那条链取，且出处写明是谁说的。
    """
    try:
        txt = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return 0, "读不到 main.cjs：%s" % type(e).__name__
    m = re.search(r'"--ctx",\s*String\(process\.env\.GBT_LLM_CTX\s*\|\|\s*"(\d+)"\)', txt)
    if m:
        return int(m.group(1)), "main.cjs 的 `GBT_LLM_CTX || %s`" % m.group(1)
    m = re.search(r'"--ctx",\s*"(\d+)"', txt)
    if m:
        return int(m.group(1)), "main.cjs 写死 `%s`（**没有 env 口子**）" % m.group(1)
    # ② 当前在役：GPU 车道。**直接问模块要生效值**，不要用正则猜源码字面量。
    #    🔴 2026-10-28 教训：上一版正则匹配 `"GBT_GPU_CTX", "2048"`；同一天我把默认值
    #    改成 profile 表（long=8192/fast=2048）之后，这个正则**立刻读不到** ⇒ 判据又假红。
    #    判据依赖源码字面量 = 判据会随实现改写而假红，这是本仓反复吃过的亏。
    try:
        import importlib.util                          # noqa: PLC0415
        _spec = importlib.util.spec_from_file_location("_gpu_lane_probe", GPU_LANE)
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        _ctx = int(getattr(_mod, "_DEF_CTX", 0) or 0)
        if _ctx:
            return _ctx, "gpu_lane.py 的 `%s` 档默认 ctx=%d · ngl=%d（真读模块生效值）" % (
                getattr(_mod, "_PROFILE", "?"), _ctx, int(getattr(_mod, "NGL", 0) or 0))
    except Exception:                                  # noqa: BLE001
        pass
    # ③ 兜底：老形态的字面量（模块被改坏 / 导入失败时至少还能读出个数）
    try:
        g = GPU_LANE.read_text(encoding="utf-8", errors="replace")
    except OSError:
        g = ""
    m = re.search(r'"GBT_GPU_CTX",\s*"(\d+)"', g) if g else None
    if m:
        return int(m.group(1)), "gpu_lane.py 的字面量 `GBT_GPU_CTX` %s（兜底路径：模块导入失败）" % m.group(1)
    return 0, "main.cjs 没有 --ctx，gpu_lane.py 也读不到生效 ctx"


def judge_local(cfg: int, limit: int) -> list:
    """**纯函数**（负控直接喂数）：在役本地车道的三条判据。

    cfg = 我们开的窗口；limit = 模型元数据里的上限。0 一律当"读不到"⇒ 红。
    """
    return [
        ("LW1 权重元数据窗口可读", int(limit) > 0,
         "context_length=%d" % limit if limit else "读不到 context_length（读不成不等于 0）"),
        ("LW2 开的窗口 <= 模型上限", bool(cfg) and bool(limit) and cfg <= limit,
         "开 %s · 上限 %s" % (cfg or "?", limit or "?")),
        ("LW3 开的窗口 >= 够用线 %d" % MIN_USEFUL_CTX, bool(cfg) and cfg >= MIN_USEFUL_CTX,
         "开 %s · 够用线 %d（实测：645 tok 在 512 下 HTTP 500、2048 下正常）"
         % (cfg or "?", MIN_USEFUL_CTX)),
    ]


def ring_budget() -> int:
    """真读环形窗口预算（**字符**）。读不到返回 0 —— 读不到就是读不到，不当 0 放行。"""
    try:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone import brain_exec              # noqa: PLC0415
        r = brain_exec.execute(kind="ring_context", payload={"op": "stats"})
        return int(((r.get("result") or {}).get("window_budget")) or 0)
    except Exception:                                    # noqa: BLE001
        return 0


def judge_budget(window_chars: int, cfg: int, cpt: float = CHARS_PER_TOKEN,
                 tps: float = PROMPT_TPS_LONG, budget_s: float = FULL_WINDOW_S) -> list:
    """**纯函数**：把「环形窗口预算是多少 token」和「我们开的 ctx 是多少 token」放在一起比。

    🔴 为什么必须有这一条（2026-10-28 补）：LW2 只比「开的窗口 ≤ **模型上限**（32768）」，
    从来没有一条判据把「环形窗口的**预算**」和「ctx」对上。实测环形窗口预算 12000 字符
    = **7011 token**，而当时 ctx 是 2048 ⇒ 装满就 500。两个单位不同（字符 vs token）的数
    不放在一起比，**谁都不会红**，一直红不了，直到线上撞墙。
    """
    if not window_chars or not cfg:
        return [("LW4 环形窗口预算 <= 开的 ctx", False,
                 "判不了：窗口预算=%s 字符 / ctx=%s（读不到就当红，不许当 0 放行）"
                 % (window_chars or "?", cfg or "?"))]
    need = int(round(window_chars / cpt))
    fits = need <= cfg
    if fits:
        lw4_detail = ("预算 %d 字符 ≈ **%d token**（%.3f 字符/token）· ctx %d（留 %d token 余量）"
                      % (window_chars, need, cpt, cfg, cfg - need))
    else:
        # 🔴 2026-10-28 实测的后果，写进判据里，免得有人以为"装不下最多报个错"：
        #    ctx=2048 下发 12015 字符，HTTP **仍回 200**，但 prompt_tokens 只有 1934
        #    （本该 8078）⇒ **静默截断**，模型基于残缺上下文作答，针尖测试答「genoffice」
        #    （正确应为「赤鳞-7391」）。⇒ 不报错 ≠ 读全了，这是最像"胡说八道"的坏法。
        lw4_detail = ("预算 %d 字符 ≈ **%d token**（%.3f 字符/token）· ctx 只有 %d ⇒ **装不下 %d token**。"
                      "实测：**不带 `--no-context-shift`** 时 HTTP 仍回 **200**，prompt 被**静默截断**"
                      "（12015 字符 → 只吃 1934 token，本该 8078），模型基于残缺上下文作答、**答案变胡话**；"
                      "车道现已加 `--no-context-shift`，超预算会回 **400**（宁可报错不胡说），"
                      "但那一发也就做不成了 ⇒ 仍须加 ctx（走 long 档）或压窗口预算；**绝不能切 fast 档**"
                      % (window_chars, need, cpt, cfg, need - cfg))
    rows = [("LW4 环形窗口预算 <= 开的 ctx", fits, lw4_detail)]
    est = (need / tps) if tps else 0.0
    ok_t = 0 < est <= budget_s
    if ok_t:
        lw5_detail = ("预估 **%.1fs**（%d token ÷ %.2f t/s，2026-10-28 实测速率）" % (est, need, tps))
    else:
        _after_tok = int(need * TRANSFORMER_RATIO)
        _after_s = (_after_tok / tps) if tps else 0.0
        lw5_detail = ("预估 **%.1fs**（%d token ÷ %.2f t/s）⇒ 超阈值。"
                      "🔴 **别指望压缩救**：变压器在**真实语料上只能压到 %.2f 倍**"
                      "（11864→10914 字符，首次耗时 %.2fs；合成重复文本才有 %.2f 那种倍率）"
                      " ⇒ 压缩后约 **%d token**、总约 %.1fs，**省不到几秒**。"
                      "可行的是：**压小环形窗口预算**（真减少 token），或接受满窗口这一发慢。"
                      "⚠️ 压缩机**按行**工作：无换行的长段会被当 1 行保护、压不动；"
                      "含代码块等关键块会 `lost_critical` 而 **fail-open 回原样**。"
                      "**切 fast 档是错的**：它 ctx 更小，装不下时会**静默截断并胡说**"
                      % (est, need, tps, TRANSFORMER_RATIO, TRANSFORMER_S, TRANSFORMER_RATIO_SYNTHETIC,
                         _after_tok, _after_s + TRANSFORMER_S))
    rows.append(("LW5 满窗口一发 <= %.0fs" % budget_s, ok_t, lw5_detail))
    return rows


def local_lane_rows() -> list:
    """在役本地车道的三条判据 + 一条「云端旧车道」明示（不判红）。"""
    mdl = lane_model()
    limit = int(gguf_meta_ints(mdl, ("context_length",)).get("context_length") or 0)
    cfg, how = shell_ctx(SHELL_CJS)
    rows = judge_local(cfg, limit)
    rows[0] = (rows[0][0], rows[0][1],
               ("%s · %s" % (mdl.name, rows[0][2])) if limit else "%s（%s）" % (rows[0][2], mdl.name))
    rows[1] = (rows[1][0], rows[1][1], "%s（%s）" % (rows[1][2], how))
    rows[2] = (rows[2][0], rows[2][1], rows[2][2] if cfg else "开窗读不到（%s）" % how)
    # LW4/LW5：把「环形窗口预算（字符）」和「ctx（token）」真正对上，并预估满窗口延迟
    rows.extend(judge_budget(ring_budget(), cfg))
    rows.append(("· 云端旧车道（已按主人令退役，不判红）", True,
                 "W1–W5 量的 `GBT_POTATO_BASE_URL` 车道已退役；它复活（/models 能回模型）本件会自动改回量它"))
    return rows


# ══════════════════════════════════════════════════════════════════════════
# 归口：把上下文异常交回**大脑执行层**（Owner 令 2026-10-28）
#   「每一次的上下文异常都要返回大脑执行层，在分析、推理、排布、划分、纠正中
#     深度推进主线任务，永远不会胡说八道、不出现幻觉。」
#   🔴 为什么必须**显式指定 kind**（2026-10-28 实测）：
#     裸调 `brain_exec.unify(goal)` 时，语义路由把「上下文窗口漂移」判成
#     `tentacle.deep_diagnose`，而那个位要 `desktop_control` + `privacy_read` 授权
#     ⇒ execute 直接 denied（missing_scopes 里正是这两个）。
#     上下文漂移**不需要桌面控制** ⇒ 不是权限不够，是**选错了域**。
#   ⇒ 现在从 route 的 best/alternatives 里挑**上下文域**，再用它取一次只读现状。
#     **不自动改窗口**：改窗口会动模型输入，须人判断；本器只做归口 + 落结论。
CONTEXT_KINDS = ("ring_context", "context_vault", "project_context")


def escalate(rows: list) -> dict:
    """把红行交回大脑执行层：路由 → 选上下文域 → 取只读现状。

    失败一律如实报（via/why），**不假装成功**——这条也是判据：没接上就是没接上。
    """
    cfg, _how = shell_ctx(SHELL_CJS)
    limit = int(gguf_meta_ints(lane_model(), ("context_length",)).get("context_length") or 0)
    red = [n for n, ok, _ in rows if not ok]
    goal = ("上下文窗口异常，需要分析原因、重新排布窗口预算、纠正声明面并回到主线。"
            "红项：%s。当前开的窗口=%s，模型元数据上限=%s。" % ("、".join(red), cfg or "?", limit or "?"))
    out = {"goal": goal, "red": red, "routed": None, "chosen": None, "state": None, "via": None}
    try:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone import brain_exec            # noqa: PLC0415
    except Exception as exc:                           # noqa: BLE001
        out["via"] = "unavailable"
        out["why"] = "大脑执行层导入失败：%s" % type(exc).__name__
        return out
    try:
        r = brain_exec.route(goal)
        out["routed"] = {"best": (r.get("best") or {}).get("kind"),
                         "alts": [a.get("kind") for a in (r.get("alternatives") or [])],
                         "why": (r.get("semantic") or {}).get("reason")}
    except Exception as exc:                           # noqa: BLE001
        out["via"] = "route_failed"
        out["why"] = "route 失败：%s" % type(exc).__name__
        return out
    cands = [out["routed"]["best"]] + (out["routed"]["alts"] or [])
    chosen = next((k for k in cands if k in CONTEXT_KINDS), None)
    if not chosen:
        out["via"] = "no_context_kind"
        out["why"] = "route 里没有上下文域（best=%s）⇒ 不硬派，交人看" % out["routed"]["best"]
        return out
    out["chosen"] = chosen
    try:
        op = "stats" if chosen == "ring_context" else "status"
        out["state"] = brain_exec.execute(kind=chosen, payload={"op": op})
        out["via"] = "brain_exec.execute(%s/%s)" % (chosen, op)
    except Exception as exc:                           # noqa: BLE001
        out["via"] = "execute_failed"
        out["why"] = "execute 失败：%s" % type(exc).__name__
    return out


def selftest() -> int:
    ck = []
    ok_d = {"via": "t", "entries": [{"slug": "gbt-potato-v8", "context_window": 20000, "auto_compact_token_limit": 16000}]}
    ok_p = {"ok": True, "chars": 33000}
    def c(n, cond, d=""):
        ck.append(bool(cond)); log(("OK  " if cond else "BAD ") + n + (" — " + str(d)[:70] if d else ""))
    c("正例·五判据全绿", all(x[1] for x in judge(ok_d, ok_p)), [x for x in judge(ok_d, ok_p) if not x[1]])
    bad_d = dict(ok_d); bad_d["entries"] = [{"slug": "gbt-potato-v8", "context_window": 40000, "auto_compact_token_limit": None}]
    c("负例·声明>实测必须红", not [x for x in judge(bad_d, ok_p) if x[0].startswith("W2")][0][1])
    c("负例·自动压缩为空必须红", not [x for x in judge(bad_d, ok_p) if x[0].startswith("W4")][0][1])
    c("负例·取不到读数必须红", not judge(ok_d, {"ok": False})[0][1])
 # 2026-10-25 新增（在役本地车道三判据的正负控）：
    c("正控·本地车道(cfg=2048/上限32768) 三条全绿",
      all(x[1] for x in judge_local(2048, 32768)),
      [x for x in judge_local(2048, 32768) if not x[1]])
    c("负控·开的窗口超过模型上限 ⇒ LW2 必红**",
      not [x for x in judge_local(40000, 32768) if x[0].startswith("LW2")][0][1])
    c("负控·开 512（实测 645tok 会 500）⇒ LW3 必红",
      not [x for x in judge_local(512, 32768) if x[0].startswith("LW3")][0][1])
    c("负控·读不到上下文（limit=0）⇒ LW1 必须红、不许当 0 放行",
      not [x for x in judge_local(2048, 0) if x[0].startswith("LW1")][0][1])
    c("负控·不存在的权重文件 ⇒ gguf_meta_ints 返回空（不是 0 冒充）",
      gguf_meta_ints(ROOT / "state/weights/___没有这个___.gguf", ("context_length",)) == {})
 # 2026-10-28 新增（LW4/LW5 预算判据的正负控）：
    c("正例·窗口 12000 字符配 ctx8192 ⇒ LW4/LW5 全绿",
      all(x[1] for x in judge_budget(12000, 8192)),
      [x for x in judge_budget(12000, 8192) if not x[1]])
    c("负例·窗口 12000 字符配 ctx2048 ⇒ LW4 必红（7011 token 装不下）",
      not [x for x in judge_budget(12000, 2048) if x[0].startswith("LW4")][0][1])
    c("负例·窗口预算读不到(0) ⇒ LW4 必红、不许当 0 放行",
      not [x for x in judge_budget(0, 8192) if x[0].startswith("LW4")][0][1])
    c("负例·阈值压到 30s ⇒ LW5 必红（满窗口 ~50s）",
      not [x for x in judge_budget(12000, 8192, budget_s=30.0) if x[0].startswith("LW5")][0][1])
 # 🔴 2026-10-28：处方本身的判据。上一版 LW5 红时建议「切 fast 档」——实测那是**有害处方**
 #    （fast 档 ctx 更小，12015 字符会被静默截断到 1934 token 且答错）。处方不许指向死路。
    _lw5_red = [x for x in judge_budget(12000, 8192, budget_s=30.0) if x[0].startswith("LW5")][0][2]
    c("负例·LW5 处方必须指向变压器压缩、且写明「按行」这个失效条件（不许指向 fast 档）",
      all(k in _lw5_red for k in ("变压器", "按行", "fail-open", "fast 档是错的")), _lw5_red[:80])
    _lw4_red = [x for x in judge_budget(12000, 2048) if x[0].startswith("LW4")][0][2]
    c("负例·LW4 装不下必须同时写明两种后果：不带开关静默截断(200)、带开关 400",
      all(k in _lw4_red for k in ("静默截断", "200", "400")), _lw4_red[:80])
    _cfg, _how = shell_ctx(SHELL_CJS)
    c("正控·真读外壳的 ctx（应 >= %d 且带出处）" % MIN_USEFUL_CTX, _cfg >= MIN_USEFUL_CTX, "%s ← %s" % (_cfg, _how))
    bad = len([x for x in ck if not x])
    log("\ncontext-window-watch selftest: %d/%d" % (len(ck) - bad, len(ck)))
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--no-brain", action="store_true",
                    help="红的时候不要把异常交回大脑执行层（默认要交，Owner 令 2026-10-28）")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    d = declared()
    p = probe()
 # 2026-10-25：云端车道退役后，`probe()` 拿不到读数 ⇒ 原来 W1/W2/W3 全红，
    #    但红的是"量了一条不在役的路"。现在：**云端量不到 ⇒ 改量在役的本地车道**；
    #    云端哪天复活（probe ok 且自报窗口），自动回到 W1–W5（判据一行没改）。
    lane_note = "云端车道（W1–W5）"
    if p.get("ok"):
        rows = judge(d, p)
    else:
        rows = local_lane_rows()
        lane_note = "在役本地车道（LW1–LW5）；云端那条量不到、已退役，见末行"
    log("上下文窗口体检（%s）· 量的是：%s" % (time.strftime("%Y-%m-%d %H:%M:%S"), lane_note))
    log("  声明面：%s" % d["via"])
    for n, ok, det in rows:
        log("  " + ("✅ " if ok else "🔴 ") + n + " — " + str(det))
    if a.fix:
        if not p.get("ok"):
            log("  --fix 跳过：云端车道量不到读数，出不了可信的修正值（不拿猜的数写别人配置）")
        else:
            plan = fix(d, p)
        log("  已出补丁：outputs/context-align/{context-align.json, apply-context-align.ps1, models.json.bak-*}  "
            "建议 context_window=%d / auto_compact=%d" % (plan["suggest"]["context_window"], plan["suggest"]["auto_compact_token_limit"]))
    red = [n for n, ok, _ in rows if not ok]
    log("  结论：" + ("全绿" if not red else "红 %d 条 -> %s" % (len(red), "、".join(red))))
    # Owner 令 2026-10-28：**每一次**上下文异常都要返回大脑执行层做分析/推理/排布/划分/纠正。
    # 注意：归口**不改变红绿**（交回大脑不等于问题消失），所以退出码仍按红算。
    if red and not a.no_brain:
        log("  归口：把异常交回大脑执行层 …")
        esc = escalate(rows)
        if esc.get("chosen"):
            st = esc.get("state") or {}
            log("  归口结果：%s · 域=%s · ok=%s" % (esc.get("via"), esc["chosen"], st.get("ok")))
            log("  大脑给出的判断：%s" % (esc["routed"].get("why") or "（无）"))
        else:
            log("  🔴 归口没接上：%s — %s" % (esc.get("via"), esc.get("why")))
        try:
            OUT.mkdir(parents=True, exist_ok=True)
            p = OUT / ("context-escalate-%s.json" % time.strftime("%Y%m%d-%H%M%S"))
            p.write_text(json.dumps(esc, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
            log("  归口留痕：%s" % p.relative_to(ROOT).as_posix())
        except OSError as exc:
            log("  🔴 归口留痕写失败：%s" % type(exc).__name__)
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
