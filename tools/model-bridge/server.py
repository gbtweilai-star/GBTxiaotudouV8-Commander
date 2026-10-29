# -*- coding: utf-8 -*-
"""原生 APP ⇄ 原生大模型 的本地桥（127.0.0.1:8791，只监听回环）。

为什么要它：Electron 壳里的页面是 `file://`，**不能把密钥写进页面**（那等于把钥发给任何能看网页的人）。
所以页面只连本机桥，桥拿 DPAPI 保险箱里的钥去打上游，回执里**只出现槽名**，永不回显明文。

对外只三件：
  GET  /health                  —— 桥活着吗、每个上游配好没（不回钥）
  GET  /v1/models               —— 给界面用的模型清单
  POST /v1/chat/completions     —— 转发（支持 stream=true 的 SSE 直通）

默认上游 = `cloud`（云插件路线：GBT小土豆V8 大模型走云端 c01-llm-gateway 的 /v1 面，
2026-10-21 主人令接入，**2026-10-24 已随 RunPod 付费车道一并清理**）；
回包 `gbt.weights_ours` 逐发可见（自托管在线=true；超时回落 Workers AI 托管=false）。

纪律：
  · 只监听 127.0.0.1；不接外部连接；
  · 钥只从 `deepseek_key.load_key(profile)` 取（DPAPI），缺钥就如实报缺，不假装；
  · 上游 4xx/5xx 的原话必须带回来（P19），不许只说"失败了"；
  · 不落聊天内容（隐私）：只在 stderr 打一行 `slot/model/http/耗时`。

用法：
  py -3.14 -X utf8 tools/model-bridge/server.py            # 前台跑，Ctrl-C 停
  py -3.14 -X utf8 tools/model-bridge/server.py --port 8791 --self-test   # 自检一次就退
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# 🔴 2026-10-29 修 §三 第 3 项（502 归因错）：回环**强制直连** + 失败**分档**。
#    本机 `HTTP_PROXY` 是全局的、`urlopen` 对 127.0.0.1 不自动 bypass ⇒ 车道没起时
#    代理回 502，被我们当成「上游真回 502」上报。独立成 lane_guard，本文件不再自己判一遍。
if str(pathlib.Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import lane_guard as LG                                            # noqa: E402

# name → (base_url, model, vault profile, timeout_s)
# `cloud` = **云插件路线**（主人令 2026-10-21「把云插件的GBT小土豆V8大模型接入到原生APP里面使用」）：
#   Cloudflare Worker `gbt-potato-cloud-10`（10 云插件拼网里的 c01-llm-gateway，
#   单一 isolate · 现役域名 paysssk）的 OpenAI 兼容面 `/v1`，模型 id 报 `gbt-potato-v8`。
#   Worker 已配 LLM_ENDPOINT（= 我们的 RunPod 自托管端点）⇒ 非流式/流式都走自托管，
#   自托管超时按设计回落 Workers AI 托管兜底（回包 `gbt.weights_ours` 逐发可见，不许念成恒 true）。
#   `/v1/chat` 要网关钥 GW_AUTH（DPAPI 槽 `gateway`；2026-10 轮换后的现值只同步进保险箱，见 key_for）。
# 🔴 2026-10-24 主人令（逐字：「这个要花钱我们不需要直接清理了就没卡点了」）：
#   RunPod 付费车道（`ours` / `ours-alt`）与背后同源的 `cloud`（c01→RunPod）**已删除**；
#   现在只跑免费道：cfai（Cloudflare Workers AI）→ agnes → deepseek。
#   要恢复自有权重时，把车道定义加回来并把名字写进 OURS_LANES 即可。
# 🔴 2026-10-23 23:58 加（页面转圈的真因在这一层被量到）：
#    默认上游 cloud 打到 c01 → c01 等死掉的 RunPod 端点 ⇒ **它不报错、它挂住**，
#    于是「超时回落 Workers AI」这条兜底永远不触发（兜底只认 error，不认 hang）。
#    实测：本机桥 POST /v1/chat/completions **120 秒无回包**，主人在页面上看到的就是转圈。
#    做法：给**主车道一个硬截止**（默认 20s，可用 GBT_BRIDGE_PRIMARY_DEADLINE 调），
#    到点就换下一条车道，并在回包里**明示 lane 与 weights_ours**（兜底一律 false，不许糊）。
LANE_DEADLINE_S = int(os.environ.get("GBT_BRIDGE_PRIMARY_DEADLINE", "20"))
# 每条车道都有独立预算：自家车道 8s（GPU 起不来就该快速让位），免费道 20s。
# 🔴 2026-10-28 实测补（根因修）：`selfhost_gpu` **原来不在这张表里** ⇒ 它吃的是上面
#    `LANE_DEADLINE_S` 的 **20s 默认值**。而满窗口（ctx8192 / 12000 字）实测要 **46.5s**
#    ⇒ **必然超时**，于是按 LANE_CHAIN 兜底到 `selfhost`（CPU，ctx 2048），
#    再被 fit gate 判 `context_overflow`。用户看到的是「这发请求装不进上下文」，
#    **真因是预算把 GPU 车道掐死了** —— 这条坑让整套 q3_k_m/8192 的优化在真实路径上等于没接。
#    ⇒ 单列一条 180s（实测 46.5s 的约 3.9 倍，给冷启与更大窗口留余量）。
#    判据：tools/codex-scripts/lane-budget-check.py（红的时候直接印出这条处方）。
LANE_BUDGET = {"selfhost_gpu": 180, "selfhost": 120, "gate": 45,
               "cfai": 20, "agnes": 12, "deepseek": 12}

# 🔴 2026-10-24 主人令「不用云端驱动，按需激活使用本地算力」——
#    车道链**默认只走我们自己**：selfhost = 本机 GGUF（按需现拉、闲置自退）。
#    cfai（Cloudflare Workers AI）/ agnes / deepseek 用的都是**别人的权重、别人的算力**，
#    与「本地算力 + 不用云端」直接相悖 ⇒ **默认不再回落到它们**。
#    要恢复回落必须**显式** `GBT_ALLOW_CLOUD=1`：可见、可逆、可审计，
#    不再像以前那样"自己权重起不来就悄悄用别人的模型"（那会让 weights_ours=false 变成常态）。
ALLOW_CLOUD = os.environ.get("GBT_ALLOW_CLOUD") == "1"
_CLOUD_LANES = ["cfai", "agnes"] if ALLOW_CLOUD else []
_OURS_GPU = ["selfhost_gpu"] if os.environ.get("GBT_ENABLE_GPU") == "1" else []
if os.environ.get("GBT_ENABLE_SELFHOST_LANE") == "1":
    LANE_CHAIN = _OURS_GPU + ["selfhost"] + _CLOUD_LANES
else:
    # 没开 selfhost 车道时**不许把链清空**（空链=一个都不问，等于哑巴）。
    # 但那种配法本身也违反「不用云端」⇒ 至少保 localhost 一条，让失败带原因而不是沉默。
    LANE_CHAIN = (_CLOUD_LANES or ["selfhost"])

OURS_LANES = {"selfhost"}   # 免费 GPU 上跑我们自己的权重时，这条为 true（weights_ours=true）
FREE_LANES = {"cfai", "agnes", "gate"}

FALLBACK_ORDER = (["agnes", "deepseek"] if ALLOW_CLOUD else [])   # 不用云端 ⇒ 不兜别家模型

def _cfai_base():
    """Cloudflare Workers AI 的 OpenAI 兼容 base（免费额度那条道）。账户号不是密钥，可以落盘。"""
    try:
        import pathlib
        f = pathlib.Path(__file__).resolve().parents[2] / "state" / "cfai-account.txt"
        acct = f.read_text(encoding="utf-8").strip()
        return "https://api.cloudflare.com/client/v4/accounts/%s/ai/v1" % acct
    except Exception:                                        # noqa: BLE001
        return "https://api.cloudflare.com/client/v4/accounts/__MISSING__/ai/v1"


UPSTREAMS = {



    "local":    ("http://127.0.0.1:8000/v1", "gbt-v8", None, 120),
    # 🔴 2026-10-24 主人令「我们走的是免费道路」：
    #    Cloudflare Workers AI（OpenAI 兼容面）—— **免费额度**（每天 10k neurons/账号，我们 10 个账号）。
    #    账户号放 state/cfai-account.txt（不是密钥）；令牌进 DPAPI 保险箱 profile=cfai。
    #    实测过这条道：llama-3.3-70b 一轮 2.66 neurons、1.09s（本仓 2026-10-23 量过）。
    # 🔴 2026-10-24 主人令「走免费 GPU 跑我们自己的权重」：
    #    这一条是**我们自己的权重**（本地 v82/v70 Qwen2-7B nf4）在免费 GPU（Colab/Kaggle）上跑起来后，
    #    由 cloudflared 隧道暴露出来的 OpenAI 兼容地址。地址从环境变量来，没配就不进链。
    #    用法：set GBT_OURS_BASE_URL=https://xxx.trycloudflare.com/v1 然后 set GBT_ENABLE_SELFHOST_LANE=1
    # 🔴 2026-10-25 · D28-甲（主人口径「云端不是我们的选择」）：兜底从 https://__unset__/v1
    #    改成**本机回环** http://127.0.0.1:8792/v1（local_llm_server.py 的默认端口）。
    #    原状：不设 env 时地址是 __unset__ ⇒ 「默认走本机」名字对、地址悬空，连接必然失败。
    #    现口径：默认指向本机权重服务；桥仍会**按需拉起** 8792（闲置 900s 自退）；
    #    要用免费 GPU/隧道那条，仍可用 env 覆盖：set GBT_OURS_BASE_URL=https://xxx.trycloudflare.com/v1
    "selfhost": (os.environ.get("GBT_OURS_BASE_URL", "").rstrip("/") or "http://127.0.0.1:8792/v1",
                 os.environ.get("GBT_OURS_MODEL", "gbt-v8"), "potato", 120),

    # GPU 车道：llama.cpp Vulkan 后端（钉 b6000，见 gpu_lane.py）。
    # 单开一条而不是替换 CPU：GPU 出过「快但乱码」的事故（b11840 回归），
    # 所以它单独排队、起来先自检，自检不过桥就跳过它回落 CPU —— 宁可慢，不许答错。
    "selfhost_gpu": (os.environ.get("GBT_GPU_BASE_URL", "http://127.0.0.1:8793/v1"),
                     os.environ.get("GBT_GPU_MODEL", "gbt-v8"), "potato", 120),

    "cfai":     (_cfai_base(), "@cf/meta/llama-3.3-70b-instruct-fp8-fast", "custom", 60),  # 保险箱槽名固定，这把云 AI 令牌装 custom 槽
    "agnes":    ("https://apihub.agnes-ai.com/v1", "agnes-2.5-flash", "agnes", 180),
    "deepseek": ("https://api.deepseek.com/v1", "deepseek-chat", "deepseek", 180),
    "openai":   ("https://api.openai.com/v1", "gpt-4o-mini", "openai", 180),
}
# 默认 = 云插件路线（主人要的就是"云插件的GBT小土豆V8大模型"）；直连 RunPod 留作 `ours` 备用。
DEFAULT = ("selfhost_gpu" if (os.environ.get("GBT_ENABLE_GPU") == "1" and
                              os.environ.get("GBT_ENABLE_SELFHOST_LANE") == "1")
           else ("selfhost" if os.environ.get("GBT_ENABLE_SELFHOST_LANE") == "1" else "cfai"))

# ── 按需激活：selfhost 没起来就现拉起来，用完按 idle 自动退 ────────────────
# 主人令 2026-10-24「按需激活运行」：不要在开机时白占 5 GB 内存，
# 第一次真正要用我们的权重时才加载；闲置 N 秒后进程自己退出把内存还回去。
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
_OURS_PY = os.environ.get("GBT_LLM_PY") or (
    r"C:\Python312\python.exe" if os.path.exists(r"C:\Python312\python.exe") else sys.executable)
_OURS_SCRIPT = os.path.join(_HERE, "local_llm_server.py")
_OURS_WEIGHTS = os.environ.get("GBT_OURS_WEIGHTS") or os.path.join(
    _REPO, "state", "weights", "gbt-v8-v82-q5_0.gguf")
# 🔴 2026-10-25 主人令「按需激活，没激活的静默不占内存」：闲置默认 900s → **120s**。
#    实测热态 RSS 4640MB，900s 太迟；120s 足够一轮对话间隙又很快把内存还给系统。
_OURS_IDLE = os.environ.get("GBT_SELFHOST_IDLE", "120")
# 身体要用装得起 mss/cv2/sounddevice/pycaw 的那个解释器（本机是 3.12）
BODY_PY = os.environ.get("GBT_BODY_PY") or (
    r"C:\Python312\python.exe" if os.path.exists(r"C:\Python312\python.exe") else sys.executable)
_OURS_PROC = [None]
_LAST_MEM_GATE = [{"ok": True, "note": "尚未触发预检"}]
_LAST_UNLOAD = [None]   # 上一次 unload 的回执（供 /health 与外部闸判断「闲置」而非「半开」）
_LAST_UP_FAIL = [None]   # 上一次「现拉自有权重」失败的原因（结构化，供回包与 /health 用）
_WARM = {"started": 0.0, "state": "idle"}


# ── 计算器：模型算数不稳（实测 120÷2 答 30、10-3+2 答 12），把算术交给确定性代码 ──
# 只认四则与括号，其它一律拒；这是补模型短板的工具，不是通用 eval。
def calc(expr: str) -> dict:
    import ast as _ast
    import operator as _op
    OPS = {_ast.Add: _op.add, _ast.Sub: _op.sub, _ast.Mult: _op.mul,
           _ast.Div: _op.truediv, _ast.Mod: _op.mod, _ast.Pow: _op.pow,
           _ast.USub: _op.neg, _ast.UAdd: _op.pos}
    src = (expr or "").replace("×", "*").replace("÷", "/").replace("＝", "=").strip()
    node = _ast.parse(src, mode="eval").body
    depth = [0]

    def ev(n):
        depth[0] += 1
        if depth[0] > 40:
            raise ValueError("表达式太深")
        if isinstance(n, _ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, _ast.BinOp) and type(n.op) in OPS:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, _ast.Pow) and abs(b) > 12:
                raise ValueError("幂太大")
            return OPS[type(n.op)](a, b)
        if isinstance(n, _ast.UnaryOp) and type(n.op) in OPS:
            return OPS[type(n.op)](ev(n.operand))
        raise ValueError("只支持数字与 + - * / % ** 和括号")

    val = ev(node)
    if isinstance(val, float) and val.is_integer():
        val = int(val)
    return {"ok": True, "expr": src, "value": val}



def _budget() -> dict:
    """本体内存预算：把「够不够跑」变成可读的四个数，而不是感觉。"""
    try:
        import psutil
        vm = psutil.virtual_memory()
        total = round(vm.total / 1048576)
        used = round(vm.used / 1048576)
        return {"ram_total_mb": total, "ram_used_mb": used,
                "ram_free_mb": total - used,
                "verdict": "RAM 充足" if (total - used) > 1500 else "RAM 偏紧"}
    except Exception as exc:                                    # noqa: BLE001
        return {"error": "%s: %s" % (type(exc).__name__, str(exc)[:80])}

def _prewarm_caps() -> None:
    """桥一起来就把能力目录与 run_task 预热好。
    实测：冷桥第一次 /v1/dispatch 要 4.3s（全在 import），预热后 20–80ms。"""
    try:
        sys.path.insert(0, _REPO)
        from gbt_allinone import run_task  # noqa: F401
        run_task("echo", {})
        sys.stderr.write("[prewarm] 能力位目录已预热\n")
        # GPU 车道的自检在**启动时**做掉：它可能失败（这台机器就是），
        # 失败要花 ~20s，不能摊到用户的第一条消息上。
        if os.environ.get("GBT_ENABLE_GPU") == "1":
            ok = ensure_gpu()
            sys.stderr.write("[prewarm] GPU 车道 %s\n" % ("就绪" if ok else "不可用（回落 CPU）"))
    except Exception as exc:                                    # noqa: BLE001
        sys.stderr.write("[prewarm] 跳过：%s\n" % str(exc)[:100])


_GPU_TRIED = [False]


def ensure_gpu(wait_s: int = 200) -> bool:
    """起 GPU 车道并等它自检通过；不通过返回 False，桥回落 CPU。"""
    if os.environ.get("GBT_ENABLE_GPU") != "1":
        return False
    base = UPSTREAMS.get("selfhost_gpu", ("",))[0]
    if base and _health_ok(base):
        return True
    if _GPU_TRIED[0]:
        return False
    _GPU_TRIED[0] = True
    try:
        r = subprocess.run([_OURS_PY, os.path.join(_HERE, "gpu_lane.py"), "--start"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=wait_s, cwd=_REPO)
        tail = ((r.stdout or "").strip() or (r.stderr or "").strip())[-160:]
        sys.stderr.write("[gpu] %s\n" % tail)
        return r.returncode == 0
    except Exception as exc:                                    # noqa: BLE001
        sys.stderr.write("[gpu] 起不来：%s\n" % str(exc)[:120])
        return False


def warm_bg() -> None:
    """后台预热：把权重加载好，但不发对话。"""
    ok = ensure_selfhost()
    _WARM["state"] = "ready" if ok else "failed"


def _health_ok(url: str, timeout: float = 2.0) -> bool:
    """探活。上游 base 是 .../v1，而 /health 挂在根上 —— 必须先剥掉 /v1。
    2026-10-24 实测踩坑：拼成 /v1/health 恒 404 ⇒ 明明起来了还在等 150s，
    把「冷启动 2 秒」误读成「冷启动 160 秒」。"""
    try:
        root = url.rstrip("/")
        if root.endswith("/v1"):
            root = root[:-3]
        req = urllib.request.Request(root + "/health", headers={"User-Agent": UA})
        # 回环直连：探活最容易被全局代理污染成 502（见 lane_guard 头注 ①）
        with LG.open_url(root + "/health", req, timeout) as r:
            return r.status == 200
    except Exception:                                             # noqa: BLE001
        return False


# ── 内存预检（2026-10-25 立）──────────────────────────────────────────────
# 为什么要有：本机 7.5GB，在役权重 q5_0 是 4.88GB。余量不足时硬拉 = 进程被系统
# 杀掉或整机换页卡死，而且**失败不带原因**（外面只看到 502）。
# 口径（照本仓 fail-closed + 带原因）：
#   · 余量够 ⇒ 放行；
#   · 余量不够 ⇒ **不拉**，回 mem_insufficient 与「还差多少 MB」；
#   · 读不到内存数 ⇒ **不静默放行**：回执里带 mem_check="unavailable" 让人看见。
# 阈值：GBT_OURS_MIN_FREE_MB，默认 5500（4.88GB 权重 + 推理余量）。
def _free_mb() -> int | None:
    try:
        import ctypes

        class _MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        st = _MS()
        st.dwLength = ctypes.sizeof(_MS)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return None
        return int(st.ullAvailPhys / (1024 * 1024))
    except Exception:                                        # noqa: BLE001
        return None


def _mem_gate() -> dict:
    # 🔴 2026-10-25 纠正（主人当场指出）：权重服务是 Llama(..., use_mmap=True) ——
    #    **mmap 懒加载**，常驻不等于 4.88GB 全进内存，页按需调入。
    #    ⇒ 我原来把默认阈值写成 5500MB 并且**默认拦截**，等于把一条能跑的路挡死（P27：
    #      挡住的功能看着像没做）。现口径：GBT_OURS_MEM_GATE = warn(默认)/block/off。
    #      warn：只把读数报出来（mem_low=true），**照常拉起**；
    #      block：余量不足就不拉（老口径，需要严格保护的机器才用）；
    #      off：连读数都不看。
    _need = int(os.environ.get("GBT_OURS_MIN_FREE_MB", "1200"))
    _mode = os.environ.get("GBT_OURS_MEM_GATE", "warn").strip().lower()
    if _mode == "off":
        return {"ok": True, "mem_check": "off", "mode": _mode}
    free = _free_mb()
    if free is None:
        return {"ok": True, "mem_check": "unavailable", "mode": _mode, "need_mb": _need,
                "why": "读不到可用内存 ⇒ 不静默放行，但也不假装已量过"}
    if free < _need:
        base = {"free_mb": free, "need_mb": _need, "short_by_mb": _need - free, "mode": _mode,
                "why": "权重是 mmap 懒加载，余量偏小也能跑（会慢）；这里只报警不拦"}
        if _mode == "block":
            return {**base, "ok": False, "reason": "mem_insufficient",
                    "how": "放掉内存再来，或改 GBT_OURS_MEM_GATE=warn 允许慢跑"}
        return {**base, "ok": True, "mem_low": True}
    return {"ok": True, "free_mb": free, "need_mb": _need, "mode": _mode}


def _mem_gate_blocked() -> dict:
    need = int(os.environ.get("GBT_OURS_MIN_FREE_MB", "1200"))
    free = _free_mb()
    if free is None:
        return {"ok": True, "mem_check": "unavailable", "need_mb": need,
                "why": "读不到可用内存 ⇒ 不静默放行，但也不假装已量过"}
    if free < need:
        return {"ok": False, "reason": "mem_insufficient", "free_mb": free,
                "need_mb": need, "short_by_mb": need - free,
                "how": "放掉内存再来：关掉占大的程序（本机常见是浏览器），或用 GBT_OURS_MIN_FREE_MB 调低阈值（知道自己在干什么才调）"}
    return {"ok": True, "free_mb": free, "need_mb": need}


def unload_selfhost() -> dict:
    """**显式卸载**：把本机权重服务收掉，内存当场还给系统（按需激活的另一半）。

    为什么要有：主人令 2026-10-25「没激活的静默不就不占内存了」。只靠 idle 超时
    意味着「没人用也要占着直到超时」，而页面切换/换页时应当能立刻释放。
    口径：真的杀了才报 released；本来就没起来就如实报 not_running，**不许报假成功**。
    """
    killed = []
    proc = _OURS_PROC[0]
    if proc is not None and proc.poll() is None:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except Exception:                                # noqa: BLE001
                proc.kill()
            killed.append(proc.pid)
        except Exception as e:                               # noqa: BLE001
            return {"ok": False, "error": "terminate_failed: %s" % e}
    _OURS_PROC[0] = None
    # 兜底：按端口收（进程句柄丢了/别的实例拉起来的）
    try:
        port = urlsplit(UPSTREAMS.get("selfhost", ("",))[0]).port or 8792
    except Exception:                                        # noqa: BLE001
        port = 8792
    if _health_ok("http://127.0.0.1:%d/v1" % port):
        try:
            if os.name == "nt":
                out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=20).stdout
                for line in out.splitlines():
                    if (":%d" % port) in line and "LISTEN" in line.upper():
                        pid = line.split()[-1]
                        subprocess.run(["taskkill", "/PID", pid, "/T", "/F"],
                                       capture_output=True, timeout=20)
                        killed.append(int(pid))
                        break
        except Exception:                                    # noqa: BLE001
            pass
    time.sleep(1)
    still = _health_ok("http://127.0.0.1:%d/v1" % port)
    _LAST_UNLOAD[0] = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "killed_pids": killed,
                       "port": port, "still_up": still}
    return {"ok": not still, "killed_pids": killed, "port": port,
            "still_up": still, "free_mb": _free_mb(),
            "note": "ok=true 表示权重服务已停、内存已交回系统" if not still
                    else "仍在上（可能被别的进程占着），如实报 still_up"}


def _up_fail(reason: str, **extra) -> bool:
    """记录一次「现拉自有权重」失败（结构化），并返回 False。"""
    _LAST_UP_FAIL[0] = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "reason": reason, **extra}
    sys.stderr.write("[activate] 失败：%s\n" % json.dumps(_LAST_UP_FAIL[0], ensure_ascii=False))
    return False


def ensure_selfhost(wait_s: int = 150) -> bool:
    """selfhost 不在就拉起来；已在则秒回 True。返回是否就绪。

    🔴 2026-10-25 根因修（真故障追踪）：原来本函数**只把原因打到 stderr**，
       调用处又**不看返回值** ⇒ 权重起不来时，外面仍去请求一条死车道，
       错误形状退化成「连不上」，**真正的因（权重不在 / 内存被拦 / 拉起即死 / 等待超时）全被吞**。
       现在：每个早退都写 `_LAST_UP_FAIL`（带 reason + 细节），调用处据此**直接回结构化错误**。
    """
    base = UPSTREAMS.get("selfhost", ("",))[0]
    if not base:
        return _up_fail("not_configured", why="selfhost base_url 为空")
    if _health_ok(base):
        _LAST_UP_FAIL[0] = None
        return True
    proc = _OURS_PROC[0]
    if proc is not None and proc.poll() is None:
        pass                                  # 已经在起了，等它
    else:
        if not os.path.isfile(_OURS_WEIGHTS):
            return _up_fail("weights_missing", path=_OURS_WEIGHTS,
                            how="把权重放到该路径，或设 GBT_OURS_WEIGHTS")
        _g = _mem_gate()
        _LAST_MEM_GATE[0] = _g
        if not _g.get("ok"):
            return _up_fail("mem_blocked", **{k: _g.get(k) for k in ("free_mb", "need_mb", "short_by_mb")})
        if _g.get("mem_low"):
            sys.stderr.write("[activate] 内存偏小但照常拉起（mmap 懒加载）：%s\n" % json.dumps(_g, ensure_ascii=False))
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        cmd = [_OURS_PY, "-X", "utf8", _OURS_SCRIPT, "--model", _OURS_WEIGHTS,
               "--port", str(urlsplit(base).port or 8792), "--ctx",
               os.environ.get("GBT_SELFHOST_CTX", "256"), "--threads",
               os.environ.get("GBT_SELFHOST_THREADS", "8"), "--idle-exit", _OURS_IDLE]
        sys.stderr.write("[activate] 按需加载自有权重：%s\n" % " ".join(cmd[1:]))
        try:
            _OURS_PROC[0] = subprocess.Popen(cmd, cwd=_REPO, creationflags=flags,
                                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            return _up_fail("spawn_failed", error="%s: %s" % (type(e).__name__, str(e)[:160]),
                            cmd=" ".join(cmd[1:4]))
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < wait_s:
        if _health_ok(base):
            sys.stderr.write("[activate] 就绪，用时 %.1fs\n" % (time.perf_counter() - t0))
            _LAST_UP_FAIL[0] = None
            return True
        p2 = _OURS_PROC[0]
        if p2 is not None and p2.poll() is not None:
            # 进程已经死了（eos 可疑会 exit 3、缺 llama_cpp 会 exit 1 等）——原因带出去
            return _up_fail("exited", rc=p2.returncode, waited_s=round(time.perf_counter() - t0, 1),
                            how="看 `py -3.14 -X utf8 tools/model-bridge/local_llm_server.py --model <权重> --port 8792` 的前几行")
        time.sleep(2)
    return _up_fail("timeout", waited_s=wait_s,
                    how="权重太大/机器太慢；可加大 GBT_SELFHOST_WAIT 或先卸载其它占用")
# 主人令 2026-10-24「使用我们自己的权重」：启用 selfhost 车道时**默认就是自有权重**；
# 起不来才按 LANE_CHAIN 落免费道，回包 gbt.weights_ours=false 明示是别人的模型。
# ── 身份注入（2026-10-25）────────────────────────────────────────────────
# 为什么要这一层：三题对照实测 —— 事实题「中国的首都」→ 北京 ✅、算术题「3+4」→ 7 ✅、
# 但「你是谁」→ 它复读我们自己的训练语料（「我是记录者 DBCrafter…」）。
# 结论：**权重不坏，是身份没对齐**（语料里满是台账/技能文案，问身份就掉进那段）。
# 产品面正解：请求里没有 system 时，**由桥补一条身份**（不改权重、不重训）。
# 口径：只在**我们自己的车道**（selfhost / local / selfhost_gpu）注入；云端车道不动
#       （那是别人的模型，硬塞人设只会让它更胡说）。GBT_IDENTITY_PROMPT 可覆盖，
#       设成空串 = 关闭注入。
_OURS_LANE_NAMES = {"selfhost", "local", "selfhost_gpu"}
DEFAULT_IDENTITY = ("你是 GBT小土豆V8，一个跑在主人自己机器上的本地大模型助手。"
                    "回答简洁、直接；被问到你是谁时，就照这句话说，不要复述任何文档或台账原文。")

UA = "gbt-v8/model-bridge"
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def key_for(profile: str | None) -> tuple[str, str]:
    """返回 (key, slot_name)。本地 vLLM 不需要钥 ⇒ ('EMPTY','none:local')。

    🔴 gateway 槽特例（2026-10-21）：GW_AUTH 在 2026-10 轮换过，而 Windows 用户环境变量
    （HKCU\\Environment）与旧进程继承的 env 都还是轮换前的值 `gbt-gw-20260926` ——
    `load_key` 的"env 优先"策略会把**陈旧 env** 当好钥匙返回，打 Worker 一律 401。
    现值（`sk-gbt-ep-…`）只同步进了 DPAPI 保险箱文件（deepseek_key set --profile gateway，
    值取自主人凭据文件 ~/.dsh/.credentials.yaml，与 DSH 的 apiKeyEnv: GW_AUTH 同源）。
    ⇒ 该槽**以保险箱文件为准**：加载前把可能陈旧的 env 临时摘掉，读完还原。
    其余槽维持 deepseek_key 原策略（env 优先）。
    """
    if not profile:
        return "EMPTY", "none:local"
    from gbt_allinone import deepseek_key as DK
    saved_env = None
    if profile == "gateway":
        saved_env = os.environ.pop("GBT_GATEWAY_TOKEN", None)
    try:
        key, _src = DK.load_key(profile)
        if key:
            return key, "vault:" + profile
    except Exception as exc:                                  # noqa: BLE001
        return "", "err:%s" % type(exc).__name__
    finally:
        if saved_env is not None:
            os.environ["GBT_GATEWAY_TOKEN"] = saved_env
    return "", "missing:" + profile


def _gate_llm(body: dict) -> tuple[int, bytes]:
    """走**万能插·ai 插座**做反向调用（主人令 2026-10-24：触手=电缆，钥匙能通电就反向调云端算力）。

    形状（现读 `omni_plug` 源码 838~848 行）：
        cap omni_plug '{"op":"ai_control","target":"<https 端点>","model":"<我们自己的模型>",
                        "key_env":"<钥匙槽>","messages":[...],"max_tokens":N}'
    要点：
      · 只认 https（插座自己钉死）；钥匙只在槽里（key_slot 明示、绝不回显明文）；
      · target 指向**我们自己的算力**、model 指名**我们自己的权重** ⇒ 不是调第三方模型；
      · 回执带 `plug.state=plugged` + host/model/key_slot，可当"电缆已通"的证据。
    """
    payload = {"op": "ai_control",
               "target": OURS_COMPUTE["base_url"],
               "model": OURS_COMPUTE["model"],
               "key_env": OURS_COMPUTE.get("key_env", "potato"),
               "messages": body.get("messages") or [{"role": "user", "content": ""}],
               "max_tokens": int(body.get("max_tokens") or 256)}
    # 🔴 2026-10-24 00:20：改成**进程内直调唯一门** `api.run_task`。
    #   原因（实测）：走 CLI `five-dim.py cap omni_plug` 时，stdout 会被其他守卫的
    #   `[safe-delete]…` 提示打断、进程非零退出 ⇒ 回包不是 JSON ⇒ 这条车道 1 秒就"失败"，
    #   等于万能插电缆**根本没被真打过**。进程内 run_task 同样是唯一门（授权/审计都在里面）。
    try:
        sys.path.insert(0, str(ROOT_DIR))
        from gbt_allinone import api as _api
        d = _api.run_task("omni_plug", payload)
    except Exception as exc:                                 # noqa: BLE001
        return 0, json.dumps({"ok": False, "error": {"message": "run_task 异常: %s: %s"
                                                     % (type(exc).__name__, str(exc)[:160])}}).encode()
    r = (d.get("result") or {})
    inner = r.get("result") or r            # 信封两层：result.result
    if not inner.get("ok"):
        return 0, json.dumps({"ok": False,
                              "plug": inner.get("plug") or r.get("plug"),
                              "error": {"message": str(inner.get("reason") or inner.get("error")
                                                       or "万能插没拿到回包")[:300]}}).encode()
    text = inner.get("text") or ""
    conv = {"id": "plug-" + str(int(time.time())), "object": "chat.completion",
            "model": inner.get("model") or OURS_COMPUTE["model"],
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                         "finish_reason": "stop"}],
            "usage": inner.get("usage") or {},
            "gbt": {"lane": "omni_plug:ai", "weights_ours": True, "free": False,
                    "plug": inner.get("plug"), "via": "five-dim.py cap omni_plug op=ai_control"}}
    return 200, json.dumps(conv, ensure_ascii=False).encode()


def _post_json(url: str, payload: dict, key: str, timeout_s: int) -> tuple[int, bytes, str]:
    """发一发 JSON，返回 (http, 原始字节, 归因档)；4xx/5xx 也把上游原话带回来（P19）。

    🔴 2026-10-29 归还因（原来只有 (http, bytes)）：`st == -1` 一个数说不清是
      「车道没起」还是「等超时」还是「代理编的 502」——三者处置完全不同。
      归因由 `lane_guard.classify_exc` 判（纯函数、有负对照），本函数不另写一套。
    """
    req = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "User-Agent": UA,
                 "Authorization": "Bearer " + key})
    try:
        with LG.open_url(url, req, timeout_s) as r:
            return r.status, r.read(), "ok"
    except urllib.error.HTTPError as exc:
        # ⚠️ 先读 body 再归因：代理编的 502 只能靠 body 认出来（响应头里没有痕迹）
        raw = exc.read() or b""
        return exc.code, raw, LG.classify_exc(exc, url, raw)
    except Exception as exc:                                  # noqa: BLE001
        return -1, ("%s: %s" % (type(exc).__name__, str(exc)[:200])).encode("utf-8"), LG.classify_exc(exc, url)


def _extract_json(text: str) -> dict | None:
    """从模型回话里抠出第一个 JSON 对象（允许前后带尾巴/```）。"""
    if not text:
        return None
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        got = json.loads(text[start:i + 1])
                    except Exception:                         # noqa: BLE001
                        break
                    if isinstance(got, dict):
                        return got
                    break
        start = text.find("{", start + 1)
    return None


def _release_root() -> "pathlib.Path | None":
    """找 gbt_commander 检索库所在的根：线上仓与发布仓布局不同，两处都认。"""
    for cand in (ROOT / "outputs" / "open-source-release", ROOT):
        if (cand / "gbt_commander").is_dir() and (cand / "data" / "capabilities.json").is_file():
            return cand
    return None


def _shortlist(question: str, cat: dict, k: int = 18) -> tuple[list[str], str]:
    """把**全量**能力位收窄成候选，再让模型挑。

    为什么需要：实测（2026-10-21）让 7B 级模型直接面对全量目录时，它回的是
    `py -3.14 tools/codex-scripts/release.py` 这种**命令行**，不是能力位名 ——
    收窄到十几个候选后它才在"名字"这个层面作答。
    收窄用的是**已发布那套检索**（`gbt_commander.Catalog.search`：词表 + IDF），不另写一套。
    """
    rel = _release_root()
    try:
        if rel is None:
            raise RuntimeError("找不到 gbt_commander")
        if str(rel) not in sys.path:
            sys.path.insert(0, str(rel))
        from gbt_commander import Catalog                    # noqa: PLC0415
        c = Catalog.load(rel / "data" / "capabilities.json")
        hits = [cap.name for cap, _score in c.search(question, k)]
        hits = [h for h in hits if h in cat]
        if hits:
            return hits, "gbt_commander.search"
        raise RuntimeError("search 空")
    except Exception as exc:                                  # noqa: BLE001
        return sorted(cat)[:k], "fallback-first-%d(%s)" % (k, type(exc).__name__)


def _policy_gate(body: dict):
    """按 `serving_policy` 的档位判这一发；拒则返回结构化信封，放行返回 None。

    🔴 2026-10-28 补（**真实缺口**）：`serving_policy.py` 原来只被 `local_llm_server.py` 引用，
    而默认车道是 `selfhost_gpu`（走 llama-server）⇒ **桥这层根本没有策略**。
    也就是说「我们有内容策略开关」这个对外说法，在**默认路径上是空的**。
    这里补在**唯一出口**：一处覆盖 selfhost / selfhost_gpu / 云车道全部。
    默认档 `uncensored`（自用）⇒ 行为完全不变；`serving_policy.py --set-mode filter-lite|strict` 才生效。
    """
    try:
        if _HERE not in sys.path:
            sys.path.insert(0, _HERE)
        import serving_policy as _sp                          # noqa: PLC0415
        pol = _sp.Policy.load()
    except Exception as exc:                                  # noqa: BLE001
        # 策略层自己坏了不许把桥打死，但**不许静默**：打一行 stderr，这一发放行
        sys.stderr.write("[policy] 载入失败，已跳过（这一发不拦）：%s\n" % type(exc).__name__)
        return None
    if getattr(pol, "mode", "uncensored") == "uncensored":
        return None
    msgs = body.get("messages") or []
    text = " ".join(str(m.get("content") or "") for m in msgs
                    if str(m.get("role") or "") == "user")
    d = pol.check(text)
    if d.get("allow", True):
        return None
    sys.stderr.write("[policy] 拒绝一发（档位 %s，原因 %s）\n" % (d.get("mode"), d.get("reason")))
    return {"id": "policy-refused", "object": "chat.completion",
            "model": body.get("model") or "gbt",
            "choices": [{"index": 0, "finish_reason": "content_filter",
                         "message": {"role": "assistant",
                                     "content": "这条请求被本地策略层拦下：%s。当前档位 `%s`。"
                                                "（这是策略开关，不是模型能力问题）"
                                                % (d.get("reason"), d.get("mode"))}}],
            "gbt": {"policy_mode": d.get("mode"),
                    "policy_hits": [h.get("category") for h in (d.get("hits") or [])],
                    "gate_position": "bridge（唯一出口，覆盖所有车道）"}}


class Handler(BaseHTTPRequestHandler):
    server_version = "gbt-model-bridge/1.0"
    protocol_version = "HTTP/1.1"

    # ---------- 小工具 ----------
    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):                        # 只留一行最小读数
        sys.stderr.write("[bridge] %s\n" % (fmt % args))

    def handle_one_request(self):
        """吞掉「客户端提前断开」这一类，别把 traceback 打进日志。

        🔴 2026-10-28 实测：健康探测（`curl --max-time 2`）断开时，
        `BaseHTTPRequestHandler` 在 `readline()` 上抛
        `ConnectionAbortedError [WinError 10053]`，**整段 traceback 落到 stderr**。
        它不是请求路径上的错（那一发仍是 http=200），但会让日志变脏、
        也会让人误以为服务在报错。断开就是断开 —— 关掉连接、别喊。
        """
        try:
            super().handle_one_request()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            self.close_connection = True

    # ---------- 派活：两个 POST 端点 ----------
    @staticmethod
    def _catalog() -> dict:
        for p in (ROOT / "outputs" / "open-source-release" / "data" / "capabilities.json",
                  ROOT / "data" / "capabilities.json"):
            if p.is_file():
                try:
                    raw = json.loads(p.read_text(encoding="utf-8"))
                    caps = raw.get("capabilities") if isinstance(raw, dict) else raw
                    return {c["name"]: c for c in caps if isinstance(c, dict) and c.get("name")}
                except Exception:                             # noqa: BLE001
                    continue
        return {}

    def _route(self, body: dict) -> None:
        """问模型“该落哪个能力位”，再用**目录**校验（查不到就是幻觉，当场拒）。"""
        question = str(body.get("question") or "").strip()
        if not question:
            return self._json(400, {"ok": False, "error": {"message": "缺 question"}})
        cat = self._catalog()
        if not cat:
            return self._json(200, {"ok": False,
                                    "error": {"message": "读不到能力目录（capabilities.json）"}})
        # 先把**全量**收窄成候选，再让模型在这几个里挑 —— 7B 级模型直接面对全量会开始编命令
        # （实测它 2026-10-21 回的是 `py -3.14 tools/codex-scripts/release.py` 这种命令行）。
        # 收窄用的是我们**已发布的那套检索**（gbt_commander.Catalog），不另写一套：单一真源。
        short, how_short = _shortlist(question, cat, k=int(body.get("k") or 18))
        if not short:
            return self._json(200, {"ok": False,
                                    "error": {"message": "候选为空（检索没命中任何能力位）"}})
        prompt = ("你是 GBT小土豆V8 总指挥。下面是从 %d 位里筛出的候选能力位：\n%s\n"
                  "用户的话：%s\n"
                  "只回答最该执行的那一个能力位名字本身（不要解释、不要命令、不要代码块、不要标点）。"
                  % (len(cat), "\n".join("- " + s for s in short), question))
        name = str(body.get("upstream") or DEFAULT)
        cfg = UPSTREAMS.get(name) or UPSTREAMS[DEFAULT]
        base, model, profile, timeout_s = cfg
        key, slot = key_for(profile)
        if not key:
            return self._json(200, {"ok": False, "key_slot": slot,
                                    "error": {"message": "没有可用钥匙（槽 %s）" % slot}})
        payload = {"model": model, "max_tokens": 60, "temperature": 0,
                   "messages": [{"role": "user", "content": prompt}]}
        t0 = time.perf_counter()
        st, raw, kind_hint = _post_json(base.rstrip("/") + "/chat/completions", payload, key, timeout_s)
        dt = round(time.perf_counter() - t0, 2)
        text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
        if st != 200:
            return self._json(200, {"ok": False, "http": st, "upstream": name, "key_slot": slot,
                                    "kind": kind_hint, "why": LG.kind_text(kind_hint),
                                    "error": {"message": text[:400]}})
        try:
            d = json.loads(text)
        except Exception:                                     # noqa: BLE001
            return self._json(200, {"ok": False, "error": {"message": "回包不是 JSON"}})
        msg = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        answer = msg.strip().strip("`'\"。.,，:：\n\t ")
        cap, how = "", "模型原话不匹配目录"
        if answer in cat:                                     # ① 原话就是位名
            cap, how = answer, "模型原话精确命中"
        else:                                                 # ② 话里带了位名 ⇒ 取最长的那个
            for cand in sorted(cat, key=len, reverse=True):
                if cand in answer:
                    cap, how = cand, "模型原话里含位名"
                    break
        hit = cat.get(cap)
        out = {"ok": bool(hit), "capability": cap or answer, "args": {}, "match": how,
               "reason": answer[:80], "verified": bool(hit),
               "upstream": name, "model": d.get("model"), "elapsed_s": dt,
               "usage": d.get("usage") or {}, "key_slot": slot,
               "catalog_size": len(cat), "shortlist": short, "shortlist_by": how_short}
        if not hit:
            out["error"] = {"message": "模型给的名字在 %d 位目录里查不到（幻觉或措辞不符）：%r"
                                       % (len(cat), answer[:60] or "<空>")}
            return self._json(200, out)
        out.update({"domain": hit.get("domain"), "readonly": hit.get("readonly"),
                    "scopes_static": hit.get("scopes_static"),
                    "requires_params": hit.get("requires_params"),
                    "params_hint": hit.get("params_hint")})
        return self._json(200, out)

    def _dispatch(self, body: dict) -> None:
        """真调一次：**只走唯一门 run_task**。门缺票就如实回缺，不绕。"""
        kind = str(body.get("capability") or body.get("kind") or "").strip()
        if not kind:
            return self._json(400, {"ok": False, "error": {"message": "缺 capability"}})
        cat = self._catalog()
        if cat and kind not in cat:
            return self._json(400, {"ok": False,
                                    "error": {"message": "目录里没有这位能力位：%s" % kind}})
        payload = body.get("args") or {}
        if not isinstance(payload, dict):
            return self._json(400, {"ok": False, "error": {"message": "args 必须是对象"}})
        t0 = time.perf_counter()
        try:
            from gbt_allinone import run_task
            env = run_task(kind, payload) or {}
        except Exception as exc:                              # noqa: BLE001
            return self._json(200, {"ok": False, "capability": kind,
                                    "error": {"message": "%s: %s" % (type(exc).__name__,
                                                                     str(exc)[:300])}})
        dt = round(time.perf_counter() - t0, 2)
        sys.stderr.write("[bridge] dispatch kind=%s %.2fs\n" % (kind, dt))
        env = env if isinstance(env, dict) else {}
        # 门的拒绝信封把缺票放在 `missing`，正常的放 `missing_scopes` —— 两处都读，别念成空。
        missing = env.get("missing_scopes") or env.get("missing") or None
        return self._json(200, {"ok": bool(env.get("status") == "ok" or env.get("ok")),
                                "capability": kind, "elapsed_s": dt,
                                "gate": env.get("gate"),
                                "status": env.get("status"),
                                "denied": bool(env.get("denied")),
                                "message": env.get("message") or env.get("reason"),
                                "missing_scopes": missing,
                                "how_to_grant": env.get("how_to_grant"),
                                "envelope": env})

    # ---------- 路由 ----------
    def do_OPTIONS(self):                                     # noqa: N802
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):                                         # noqa: N802
        if self.path.startswith("/health"):
            # selfhost 的「状态」：现拉/就绪/已卸载（闲置）。外部闸靠它区分
            # 「按需闲置（对）」与「半开（坏）」——两者在端口读数上一模一样。
            _sh_up = _health_ok(UPSTREAMS.get("selfhost", ("",))[0] or "")
            _selfhost = {"up": _sh_up, "state": "ready" if _sh_up else
                         ("unloaded" if _LAST_UNLOAD[0] else
                          ("failed" if _LAST_UP_FAIL[0] else "idle")),
                         "last_unload": _LAST_UNLOAD[0],
                         "last_error": _LAST_UP_FAIL[0]}
            ups = []
            for name, (base, model, prof, _to) in UPSTREAMS.items():
                key, slot = key_for(prof)
                ups.append({"name": name, "base_url": base, "model": model,
                            "key_slot": slot, "key_ready": bool(key)})
            return self._json(200, {"ok": True, "service": "gbt-model-bridge",
                                    "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                    "default": DEFAULT, "upstreams": ups,
                                    "selfhost": _selfhost,
                                    "note": "钥只在桥里；页面永远拿不到明文"})
        if self.path.startswith("/v1/models"):
            return self._json(200, {"object": "list", "data": [
                {"id": m, "owned_by": n, "base_url": b} for n, (b, m, _p, _t) in UPSTREAMS.items()]})
        if self.path.startswith("/v1/unit"):
            # 本体：大模型和 APP 是一件事，不是两个进程两本账。
            # 这里把「壳 / 桥 / 权重 / 显卡」四段合成一个状态，一次性说清：
            # 谁在跑、占多少内存、用的是哪条车道、下一问要等多久。
            import subprocess as _sp
            def _ws(name, pat):
                """按**进程名 + 命令行**取工作集。
                2026-10-24 踩坑：只按命令行匹配时，探针自己的命令行里就含那个词，
                于是每次都把自己算进去（报 84 MB 的「壳」其实探针自己）。"""
                try:
                    o = _sp.run(["powershell","-NoProfile","-c",
                        "(Get-CimInstance Win32_Process -Filter \"Name='%s'\" | "
                        "Where-Object { $_.CommandLine -like '*%s*' } | "
                        "ForEach-Object { (Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue).WorkingSet64 })" % (name, pat)],
                        capture_output=True, text=True, timeout=20)
                    vals = [int(x) for x in (o.stdout or "").split() if x.isdigit()]
                    return round(sum(vals)/1048576) if vals else 0
                except Exception:                                # noqa: BLE001
                    return 0
            model_up = _health_ok(UPSTREAMS["selfhost"][0]) if UPSTREAMS.get("selfhost") else False
            gpu_up = _health_ok(UPSTREAMS["selfhost_gpu"][0]) if UPSTREAMS.get("selfhost_gpu") else False
            return self._json(200, {
                "ok": True, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "unit": "GBT小土豆V8 · 指挥官模型 + APP（一体）",
                "parts": {
                    "shell":   {"role": "壳（Electron）", "mem_mb": _ws("electron.exe", "holo_pet_w3")},
                    "bridge":  {"role": "桥（唯一出口）", "state": "up", "port": 8791, "mem_mb": _ws("python.exe", "server.py --port 8791")},
                    "weights": {"role": "自有权重 Q5_0", "state": "warm" if model_up else "cold",
                                "port": 8792, "mem_mb": _ws("python.exe", "local_llm_server"),
                                "idle_exit_s": int(_OURS_IDLE)},
                    "gpu":     {"role": "Vulkan 车道（实验）", "state": "up" if gpu_up else "off", "mem_mb": _ws("llama-server.exe", "llama-vulkan"),
                                "port": int(urlsplit(UPSTREAMS.get("selfhost_gpu", ("http://127.0.0.1:8793",))[0]).port or 8793),
                                "gate": "严判自检：不过不上生产"},
                },
                "lifecycle": {
                    "policy": "按需激活：首问现拉权重 → 闲置 %ss 自退 → 下次再拉" % _OURS_IDLE,
                    "quit": "壳退出时按端口收掉 8791/8792，不留后台进程",
                },
                "default_lane": DEFAULT,
                "budget": _budget(),
            })
        if self.path.startswith("/v1/body"):
            # 身体：装在哪台设备上，就把那台设备的感官/动作现读成身体。
            # 走**独立进程 + 3.12**：mss/cv2/sounddevice/pycaw 都装在那边，
            # 桥自己（3.14）不背这些依赖，也就不用为了读个电量去装一堆包。
            try:
                out = subprocess.run([BODY_PY, os.path.join(_HERE, "body.py")],
                                     capture_output=True, text=True, encoding="utf-8",
                                     errors="replace", timeout=60, cwd=_REPO)
                return self._json(200, json.loads(out.stdout or "{}"))
            except Exception as exc:                      # noqa: BLE001
                return self._json(200, {"ok": False, "error": "%s: %s"
                                        % (type(exc).__name__, str(exc)[:150])})
        if self.path.startswith("/v1/caps"):
            # 页面互通的口：全量能力位 + 各自页面地址，一次给全（前端缓存；条数由台账决定）
            try:
                import json as _json
                cbp = os.path.join(_REPO, "state", "cap-bindings.json")
                caps = _json.load(open(cbp, encoding="utf-8")).get("caps") or []
                out = [{"name": c.get("name"), "domain": c.get("domain"),
                        "desc": (c.get("desc") or "")[:120],
                        "page": "/holo_pet_w3/brain/caps/%s.html" % c.get("name")}
                       for c in caps if c.get("name")]
                return self._json(200, {"ok": True, "count": len(out), "caps": out})
            except Exception as exc:                      # noqa: BLE001
                return self._json(200, {"ok": False, "error": "%s: %s"
                                        % (type(exc).__name__, str(exc)[:120])})
        if self.path.startswith("/warm"):
            base = UPSTREAMS.get("selfhost", ("",))[0]
            up = _health_ok(base) if base else False
            if self.path.startswith("/warm/status"):
                return self._json(200, {
                    "ok": up, "state": "ready" if up else _WARM["state"],
                    "elapsed_s": round(time.time() - _WARM["started"], 1) if _WARM["started"] else 0})
            if up:
                _WARM["state"] = "ready"
                return self._json(200, {"ok": True, "state": "ready", "note": "已经就绪，无需预热"})
            if _WARM["state"] != "warming":
                _WARM["started"] = time.time()
                _WARM["state"] = "warming"
                threading.Thread(target=warm_bg, daemon=True).start()
            return self._json(200, {"ok": True, "state": "warming",
                                    "note": "后台加载 4.88 GB 权重，约 1–2 分钟"})
        return self._json(404, {"error": {"message": "no route %s" % self.path}})

    def do_POST(self):                                        # noqa: N802
        if self.path.startswith("/v1/unload") or self.path.startswith("/unload"):
            # 🔴 2026-10-25 实测坑：不把请求体读完就回包，Windows 上客户端会看到
            #    「response ended prematurely」（效果其实已经发生，但回包丢了 ⇒ 外面只能猜）。
            #    先把 Content-Length 读完（丢弃），再回结构化回执。
            try:
                _n = int(self.headers.get("Content-Length") or 0)
                if _n > 0:
                    self.rfile.read(_n)
            except Exception:                                # noqa: BLE001
                pass
            _res = unload_selfhost()
            return self._json(200, _res)
        KNOWN = ("/v1/chat/completions", "/v1/route", "/v1/dispatch", "/v1/calc", "/v1/body/act")
        if not any(self.path.startswith(k) for k in KNOWN):
            return self._json(404, {"error": {"message": "no route %s" % self.path}})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception as exc:                              # noqa: BLE001
            return self._json(400, {"error": {"message": "请求体不是 JSON：%s" % exc}})

        if self.path.startswith("/v1/body/act"):
            try:
                out = subprocess.run(
                    [BODY_PY, os.path.join(_HERE, "body.py"), "--act",
                     str(body.get("limb") or ""), json.dumps(body.get("args") or {}, ensure_ascii=False)],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=120, cwd=_REPO)
                return self._json(200, json.loads(out.stdout or "{}"))
            except Exception as exc:                      # noqa: BLE001
                return self._json(200, {"ok": False, "error": "%s: %s"
                                        % (type(exc).__name__, str(exc)[:150])})
        if self.path.startswith("/v1/calc"):
            try:
                return self._json(200, calc(str(body.get("expr") or "")))
            except Exception as exc:                          # noqa: BLE001
                return self._json(200, {"ok": False, "error": "%s: %s"
                                        % (type(exc).__name__, str(exc)[:120])})
        # ── 派活①：先问模型该落哪个能力位，再用目录校验（幻觉当场拒）────────────
        if self.path.startswith("/v1/route"):
            return self._route(body)
        # ── 派活②：真调一次（**走唯一门 run_task**，门拒就如实回拒）────────────
        if self.path.startswith("/v1/dispatch"):
            return self._dispatch(body)

        # ── 策略层：**在选车道之前**判，一处覆盖所有车道（含默认的 selfhost_gpu）────
        _pol = _policy_gate(body)
        if _pol is not None:
            return self._json(200, _pol)

        name = str(body.pop("upstream", "") or DEFAULT)
        if name not in UPSTREAMS:
            return self._json(400, {"error": {"message": "不认的上游：%s（可选 %s）"
                                              % (name, ",".join(UPSTREAMS))}})
        base, model_default, profile, timeout_s = UPSTREAMS[name]
        body.setdefault("model", model_default)
        stream = bool(body.get("stream"))

        key, slot = key_for(profile)
        if not key:
            return self._json(200, {"error": {"message": "没有可用钥匙（槽 %s）" % slot,
                                              "slot": slot},
                                    "ok": False})

        url = base.rstrip("/") + "/chat/completions"
        t0 = time.perf_counter()

        # 车道链：先打主人指定的那条（硬截止），不行再按 FALLBACK_ORDER 兜底。
        chain = [name] + [n for n in LANE_CHAIN if n in UPSTREAMS and n != name]
        resp = None
        prefetched = None          # 非流式：读到的整包（空 content 要换车道，所以提前读）
        attempts = []
        used = name
        for lane in chain:
            if lane == "selfhost":
                # 🔴 2026-10-25 根因修：原来忽略返回值 ⇒ 权重起不来还去打死车道，
                #    错误退化成「连不上」。现在：起不来就**带原因回包**，不再往下撞。
                if not ensure_selfhost():
                    fe = _LAST_UP_FAIL[0] or {"reason": "unknown"}
                    attempts.append({"lane": lane, "why": "自有权重起不来：%s" % fe.get("reason")})
                    return self._json(200, {
                        "ok": False, "lane": lane, "weights_ours": False,
                        "error": {"message": "自有权重车道未就绪（%s）" % fe.get("reason"),
                                  "reason": fe.get("reason"), "detail": fe,
                                  "how": fe.get("how") or "见 /health 的 selfhost.last_error"},
                        "attempts": attempts})
            if lane == "selfhost_gpu" and not ensure_gpu():
                continue                   # GPU 不通就跳过，走 CPU 车道
            l_base, l_model, l_profile, l_timeout = UPSTREAMS[lane]
            l_key, l_slot = key_for(l_profile)
            if not l_key:
                attempts.append({"lane": lane, "why": "钥槽 %s 没钥" % l_slot})
                continue
            l_body = dict(body)
            # 🔴 2026-10-24 00:12 自纠：原来只有**兜底车道**才换模型名，**主车道照抄页面传来的 model**
            #    ⇒ cfai（Workers AI）收到 "gbt-potato-v8" 这种它不认的名字，直接失败再落到兜底。
            #    正确口径：**每条车道都用它自己清单里的模型名**，页面传的 model 只在同名车道里保留。
            l_body["model"] = l_model
            # 🔴 2026-10-25 身份注入：自家车道 + 页面没给 system ⇒ 补一条身份
            if lane in _OURS_LANE_NAMES:
                _ident = os.environ.get("GBT_IDENTITY_PROMPT", DEFAULT_IDENTITY)
                _msgs = list(l_body.get("messages") or [])
                if _ident and _msgs:
                    if not any((m or {}).get("role") == "system" for m in _msgs):
                        _msgs = [{"role": "system", "content": _ident}] + _msgs
                    # 🔴 2026-10-25 实测追加：**这个权重量不读 system，读 user 段**。
                    #   对照（同一句「你是谁」）：
                    #     · 只塞 system  → 「我是龙珠融合版…」（仍复读训练语料）
                    #     · 用户段前缀   → 「我是 GBT小土豆V8，一个跑在主人自己机器上的本地大模型助手。」
                    #   所以两条都塞：system 留给以后换权重，user 段前缀负责现在真生效。
                    _prefix = "记住：你是 GBT小土豆V8，主人自己的本地模型，回答简洁直接。不要复述任何文档或台账原文。\n\n"
                    for _i in range(len(_msgs) - 1, -1, -1):
                        if (_msgs[_i] or {}).get("role") == "user":
                            if not str(_msgs[_i].get("content") or "").startswith("记住：你是 GBT小土豆V8"):
                                _msgs[_i] = dict(_msgs[_i],
                                                 content=_prefix + str(_msgs[_i].get("content") or ""))
                            break
                l_body["messages"] = _msgs
            if lane != name:
                l_body.pop("stream", None)           # 兜底不保证 SSE，先要整包
            l_url = l_base.rstrip("/") + "/chat/completions"
            l_req = urllib.request.Request(
                l_url, data=json.dumps(l_body, ensure_ascii=False).encode("utf-8"), method="POST",
                headers={"Content-Type": "application/json", "User-Agent": UA,
                         "Authorization": "Bearer " + l_key})
            budget = LANE_BUDGET.get(lane, LANE_DEADLINE_S)
            if lane == "gate":
                lt0 = time.perf_counter()
                try:
                    g_st, g_raw = _gate_llm(l_body)
                    if g_st == 200:
                        prefetched = g_raw
                        used = "gate"
                        sys.stderr.write("[bridge] 自家权重都不回包 ⇒ 经万能插走云端算力（%.1fs）\n"
                                         % (time.perf_counter() - lt0))
                        break
                    attempts.append({"lane": "gate", "http": g_st,
                                     "why": g_raw.decode("utf-8", "replace")[:160],
                                     "ms": int((time.perf_counter() - lt0) * 1000)})
                except Exception as exc:                      # noqa: BLE001
                    attempts.append({"lane": "gate", "why": type(exc).__name__,
                                     "ms": int((time.perf_counter() - lt0) * 1000)})
                continue
            lt0 = time.perf_counter()
            # 🔴 2026-10-29 修 §三 第 2 项（fit gate 只在 CPU 车道）：
            #    GPU 车道原来只靠 llama-server 的 `--no-context-shift` 回 400 兜底，
            #    而那是**推理跑起来之后**才回（满窗口实测 46.5s）⇒ 用户白等一场才被告知装不下。
            #    这里在**发请求之前**用车道自己的 `/tokenize` 数真 token（毫秒级）再判。
            #    只对 `selfhost_gpu` 做：CPU 车道自己在 local_llm_server.py 里已有同一套判据，
            #    重复判会变成两套判断（判据文化不允许）。
            if lane == "selfhost_gpu":
                _fit = LG.precheck_fit(l_base, l_body, lane=lane)
                if _fit.get("checked") and _fit.get("over"):
                    sys.stderr.write("[fit] 提前拒 lane=%s tokens=%s+%s > n_ctx=%s\n"
                                     % (lane, _fit.get("tokens"), _fit.get("max_tokens"),
                                        _fit.get("n_ctx")))
                    return self._json(200, {
                        "ok": False, "lane": lane, "weights_ours": False,
                        "error": {"message": "这发请求装不进 %s 车道的上下文：prompt %s + max_tokens %s "
                                             "> n_ctx %s（超 %s token）"
                                             % (lane, _fit.get("tokens"), _fit.get("max_tokens"),
                                                _fit.get("n_ctx"), _fit.get("over_by")),
                                  "reason": "context_overflow",
                                  "how": "缩短上下文、调小 max_tokens，或把 GBT_GPU_CTX 调大后重启车道；"
                                         "**这条是发之前判的**，没有白等推理"},
                        "fit": _fit, "attempts": attempts})
            try:
                resp = LG.open_url(l_url, l_req, budget)
                if not stream:
                    body_bytes = resp.read()
                    # 🔴 2026-10-24 00:00 实测：agnes 会回 **HTTP 200 但 content 为空**。
                    #    只认「连上了」就会把空白当答案发给主人 ⇒ 空 content 也算这条车道失败，换下一条。
                    try:
                        _d = json.loads(body_bytes.decode("utf-8", "replace"))
                        _m = ((_d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
                    except Exception:                          # noqa: BLE001
                        _m = ""
                    if not str(_m).strip():
                        attempts.append({"lane": lane, "why": "HTTP 200 但 content 为空",
                                         "ms": int((time.perf_counter() - lt0) * 1000)})
                        sys.stderr.write("[bridge] lane=%s 回空 content ⇒ 换下一条车道\n" % lane)
                        continue
                    prefetched = body_bytes
                used = lane
                if lane != name:
                    sys.stderr.write("[bridge] 主车道 %s 在 %ds 内没回包 ⇒ 兜底到 %s（weights_ours=false）\n"
                                     % (name, LANE_DEADLINE_S, lane))
                break
            except urllib.error.HTTPError as exc:
                # 502 分两种：上游真回 vs 本机代理编的（后者说明端点根本没通）
                # ⚠️ 必须先读 body 再归因 —— 代理的 502 只在 body 里留签名，响应头是干净的
                raw_b = exc.read() or b""
                kind = LG.classify_exc(exc, l_url, raw_b)
                raw = raw_b[:400].decode("utf-8", "replace")
                attempts.append({"lane": lane, "http": exc.code, "kind": kind,
                                 "why": LG.kind_text(kind) + ("：" + raw[:160] if raw else ""),
                                 "upstream_said": raw[:200],
                                 "ms": int((time.perf_counter() - lt0) * 1000)})
                sys.stderr.write("[bridge] lane=%s http=%s kind=%s slot=%s\n"
                                 % (lane, exc.code, kind, l_slot))
            except Exception as exc:                          # noqa: BLE001
                kind = LG.classify_exc(exc, l_url)
                attempts.append({"lane": lane, "kind": kind,
                                 "why": LG.kind_text(kind),
                                 "detail": "%s" % type(exc).__name__,
                                 "ms": int((time.perf_counter() - lt0) * 1000)})
                sys.stderr.write("[bridge] lane=%s net=%s detail=%s\n"
                                 % (lane, kind, type(exc).__name__))
        if resp is None:
            # 归因一起带出去：**「我们没起服务」与「上游报错」处置完全不同**
            kinds = sorted({a.get("kind") for a in attempts if a.get("kind")})
            return self._json(200, {"ok": False, "upstream": name, "attempts": attempts,
                                    "lane_used": None, "weights_ours": False,
                                    "kinds": kinds,
                                    "error": {"message": "所有车道都没回包（含兜底）",
                                              "why": "；".join(LG.kind_text(k) for k in kinds) or "无可用车道"}})
        if stream:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            # 车道印记：兜底车道一律 weights_ours=false（主人要的就是「不许糊」）
            self.send_header("x-gbt-lane", used)
            self.send_header("x-gbt-weights-ours", "true" if used in OURS_LANES else "false")
            self.send_header("x-gbt-free", "true" if used in FREE_LANES else "false")
            self._cors()
            self.end_headers()
            try:
                while True:
                    chunk = resp.readline()
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
                    # 🔴 2026-10-24 实测：收到 [DONE] 后不关连接 ⇒ curl 挂到 --max-time，
                    #    浏览器那边 reader 也永远等不到 done。见到 [DONE] 就收工并关连接。
                    if b"[DONE]" in chunk:
                        break
            except Exception:                                 # noqa: BLE001
                pass
            self.close_connection = True
            sys.stderr.write("[bridge] stream lane=%s used=%s model=%s %.2fs\n"
                             % (name, used, body.get("model"), time.perf_counter() - t0))
            return

        raw = prefetched if prefetched is not None else resp.read()
        sys.stderr.write("[bridge] upstream=%s used=%s model=%s http=200 %.2fs\n"
                         % (name, used, body.get("model"), time.perf_counter() - t0))
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("x-gbt-lane", used)
        self.send_header("x-gbt-weights-ours", "true" if used in OURS_LANES else "false")
        self.send_header("x-gbt-free", "true" if used in FREE_LANES else "false")
        self._cors()
        self.end_headers()
        self.wfile.write(raw)


def serve(port: int) -> int:
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=_prewarm_caps, daemon=True).start()
    print("模型桥已起：http://127.0.0.1:%d  （只在回环；Ctrl-C 停）" % port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停。")
    return 0


def self_test(port: int) -> int:
    """起一个线程跑桥，打一发真请求，打印读数后退出（证明桥真能用，不是写完就算）。"""
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=_prewarm_caps, daemon=True).start()
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    time.sleep(0.3)
    import urllib.request as U
    health = json.loads(U.urlopen("http://127.0.0.1:%d/health" % port, timeout=10).read())
    print("health ok=%s · 上游 %d 个 · 钥就绪：%s"
          % (health.get("ok"), len(health.get("upstreams") or []),
             {u["name"]: u["key_ready"] for u in health.get("upstreams") or []}))
    body = json.dumps({"upstream": DEFAULT, "model": UPSTREAMS[DEFAULT][1],
                       "messages": [{"role": "user", "content": "回一句：桥已接通。"}],
                       "max_tokens": 200}).encode()
    req = U.Request("http://127.0.0.1:%d/v1/chat/completions" % port, data=body,
                    headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    try:
        raw = U.urlopen(req, timeout=120).read()
    except Exception as exc:                                  # noqa: BLE001
        print("请求失败：", type(exc).__name__, exc)
        srv.shutdown()
        return 1
    dt = time.perf_counter() - t0
    d = json.loads(raw)
    if d.get("ok") is False or d.get("error"):
        print("上游/桥报错：", json.dumps(d, ensure_ascii=False)[:400])
        srv.shutdown()
        return 1
    msg = ((d.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    print("真回执：%.2fs · model=%s · usage=%s" % (dt, d.get("model"), d.get("usage")))
    print("正文前 120 字：%s" % msg.strip().replace("\n", " ")[:120])
    srv.shutdown()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    return self_test(a.port) if a.self_test else serve(a.port)


if __name__ == "__main__":
    raise SystemExit(main())
