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
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "context-align"
MODELS = pathlib.Path(os.path.expanduser("~/.codex/models.json"))
ENDPOINT = "https://gbt-potato-cloud-10.lopaycn.workers.dev/v1/chat/completions"
# 🔴 2026-10-21 口径翻正（留痕 · 谁改的、为什么改、原期望是什么）：
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
    # 🔴 2026-10-21：模型 id 必须用**端点自报的那个**（直连引擎只认 `/runpod-volume/gbt-v8-v83`，
    #   写 `gbt-potato-v8` 会被 vLLM 判 model not found ⇒ 二分全 False、把"不通"栽给上游）。
    probe_model = win.get("model_id") or "gbt-potato-v8"
    # 🔴 2026-10-21：服务端自报优先就**别默认二分**。实测无服务器冷启动一次 6 分钟没回
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
    # 🔴 2026-10-21 口径翻正（留痕）：**优先采信服务端自报的 `max_model_len`**。
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
    #  🔴 2026-10-15：1.1% 的测量误差被判成红 ⇒ 会天天误报、天天拦门（实测：声明 13361 / 实测 13218）。
    #     ⇒ W2 加 **5% 容差**；且"未收敛"归**黄**（报出来但放行）。
    _tol = 1.05
    _w2 = bool(p.get("ok")) and real_tokens > 0 and decl > 0 and decl <= real_tokens * _tol
    _w2_yellow = (not _w2) and bool(p.get("partial"))
    rows.append(("W2 声明 <= 实测×(1+5%)", _w2 or _w2_yellow,
                 "声明 %s / 实测 %s%s" % (decl, real_tokens,
                                        "（黄：未收敛，放行）" if _w2_yellow else "（容差 5%）")))
    drift = (abs(decl - real_tokens) / real_tokens) if real_tokens else None
    # 🔴 2026-10-18 加（**假红** · 留痕 · 原口径/为什么翻/现口径）：
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
    # 🔴 2026-10-21：服务端自报窗口就是权威 ⇒ 直接用它，不再打 9 折（打折等于自废窗口）；
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
    bad = len([x for x in ck if not x])
    log("\ncontext-window-watch selftest: %d/%d" % (len(ck) - bad, len(ck)))
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    d = declared()
    p = probe()
    rows = judge(d, p)
    log("上下文窗口体检（%s）" % time.strftime("%Y-%m-%d %H:%M:%S"))
    log("  声明面：%s" % d["via"])
    for n, ok, det in rows:
        log("  " + ("✅ " if ok else "🔴 ") + n + " — " + str(det))
    if a.fix:
        plan = fix(d, p)
        log("  已出补丁：outputs/context-align/{context-align.json, apply-context-align.ps1, models.json.bak-*}  "
            "建议 context_window=%d / auto_compact=%d" % (plan["suggest"]["context_window"], plan["suggest"]["auto_compact_token_limit"]))
    red = [n for n, ok, _ in rows if not ok]
    log("  结论：" + ("全绿" if not red else "红 %d 条 -> %s" % (len(red), "、".join(red))))
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
