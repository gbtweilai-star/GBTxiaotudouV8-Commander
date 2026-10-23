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
# 只有这三条车道跑的是**我们自己的权重**（云端 workers 拼网 / RunPod 直连 / 本机 vLLM）。
# 免费道路（cfai=Cloudflare Workers AI、agnes）是别人的模型 ⇒ weights_ours 必须 false，不许糊。
# 车道总顺序：**我们自己的权重排最前**（ours 直连 RunPod → ours-alt → 云端拼网 cloud），
# 只有它们都不回包时才落免费道（cfai=Workers AI、agnes），最后才是 deepseek。
# 每条车道都有独立预算：自家车道 8s（GPU 起不来就该快速让位），免费道 20s。
LANE_CHAIN = (["selfhost", "cfai", "agnes"] if os.environ.get("GBT_ENABLE_SELFHOST_LANE") == "1"
              # 免费 GPU 上的**我们自己的权重**一旦就位，用这条开关把它排到最前
              else ["cfai", "agnes"])
LANE_BUDGET = {"selfhost": 120, "gate": 45, "cfai": 20, "agnes": 12, "deepseek": 12}

OURS_LANES = {"selfhost"}   # 免费 GPU 上跑我们自己的权重时，这条为 true（weights_ours=true）
FREE_LANES = {"cfai", "agnes", "gate"}

FALLBACK_ORDER = ["agnes", "deepseek"]   # 主人令：免费优先（cfai 主道；agnes 免费额度；deepseek 兜最后）

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
    "selfhost": (os.environ.get("GBT_OURS_BASE_URL", "").rstrip("/") or "https://__unset__/v1",
                 os.environ.get("GBT_OURS_MODEL", "gbt-v8"), "potato", 120),

    "cfai":     (_cfai_base(), "@cf/meta/llama-3.3-70b-instruct-fp8-fast", "custom", 60),  # 保险箱槽名固定，这把云 AI 令牌装 custom 槽
    "agnes":    ("https://apihub.agnes-ai.com/v1", "agnes-2.5-flash", "agnes", 180),
    "deepseek": ("https://api.deepseek.com/v1", "deepseek-chat", "deepseek", 180),
    "openai":   ("https://api.openai.com/v1", "gpt-4o-mini", "openai", 180),
}
# 默认 = 云插件路线（主人要的就是"云插件的GBT小土豆V8大模型"）；直连 RunPod 留作 `ours` 备用。
DEFAULT = ("selfhost" if os.environ.get("GBT_ENABLE_SELFHOST_LANE") == "1" else "cfai")

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
_OURS_IDLE = os.environ.get("GBT_SELFHOST_IDLE", "900")
_OURS_PROC = [None]
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
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:                                             # noqa: BLE001
        return False


def ensure_selfhost(wait_s: int = 150) -> bool:
    """selfhost 不在就拉起来；已在则秒回 True。返回是否就绪。"""
    base = UPSTREAMS.get("selfhost", ("",))[0]
    if not base:
        return False
    if _health_ok(base):
        return True
    proc = _OURS_PROC[0]
    if proc is not None and proc.poll() is None:
        pass                                  # 已经在起了，等它
    else:
        if not os.path.isfile(_OURS_WEIGHTS):
            sys.stderr.write("[activate] 权重不在：%s\n" % _OURS_WEIGHTS)
            return False
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        cmd = [_OURS_PY, "-X", "utf8", _OURS_SCRIPT, "--model", _OURS_WEIGHTS,
               "--port", str(urlsplit(base).port or 8792), "--ctx",
               os.environ.get("GBT_SELFHOST_CTX", "256"), "--threads",
               os.environ.get("GBT_SELFHOST_THREADS", "8"), "--idle-exit", _OURS_IDLE]
        sys.stderr.write("[activate] 按需加载自有权重：%s\n" % " ".join(cmd[1:]))
        _OURS_PROC[0] = subprocess.Popen(cmd, cwd=_REPO, creationflags=flags,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < wait_s:
        if _health_ok(base):
            sys.stderr.write("[activate] 就绪，用时 %.1fs\n" % (time.perf_counter() - t0))
            return True
        time.sleep(2)
    sys.stderr.write("[activate] %ds 内没起来\n" % wait_s)
    return False
# 主人令 2026-10-24「使用我们自己的权重」：启用 selfhost 车道时**默认就是自有权重**；
# 起不来才按 LANE_CHAIN 落免费道，回包 gbt.weights_ours=false 明示是别人的模型。
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


def _post_json(url: str, payload: dict, key: str, timeout_s: int) -> tuple[int, bytes]:
    """发一发 JSON，返回 (http, 原始字节)；4xx/5xx 也把上游原话带回来（P19）。"""
    req = urllib.request.Request(
        url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "User-Agent": UA,
                 "Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as exc:
        return exc.code, (exc.read() or b"")
    except Exception as exc:                                  # noqa: BLE001
        return -1, ("%s: %s" % (type(exc).__name__, str(exc)[:200])).encode("utf-8")


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
    """把 341 位收窄成候选，再让模型挑。

    为什么需要：实测（2026-10-21）让 7B 级模型直接面对 341 位时，它回的是
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
        # 先把 341 位**收窄成候选**，再让模型在这几个里挑 —— 7B 级模型直接面对 341 位会开始编命令
        # （实测它 2026-10-21 回的是 `py -3.14 tools/codex-scripts/release.py` 这种命令行）。
        # 收窄用的是我们**已发布的那套检索**（gbt_commander.Catalog），不另写一套：单一真源。
        short, how_short = _shortlist(question, cat, k=int(body.get("k") or 18))
        if not short:
            return self._json(200, {"ok": False,
                                    "error": {"message": "候选为空（检索没命中任何能力位）"}})
        prompt = ("你是 GBT小土豆V8 总指挥。下面是从 341 位里筛出的候选能力位：\n%s\n"
                  "用户的话：%s\n"
                  "只回答最该执行的那一个能力位名字本身（不要解释、不要命令、不要代码块、不要标点）。"
                  % ("\n".join("- " + s for s in short), question))
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
        st, raw = _post_json(base.rstrip("/") + "/chat/completions", payload, key, timeout_s)
        dt = round(time.perf_counter() - t0, 2)
        text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
        if st != 200:
            return self._json(200, {"ok": False, "http": st, "upstream": name, "key_slot": slot,
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
            out["error"] = {"message": "模型给的名字在 341 位目录里查不到（幻觉或措辞不符）：%r"
                                       % (answer[:60] or "<空>")}
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
            ups = []
            for name, (base, model, prof, _to) in UPSTREAMS.items():
                key, slot = key_for(prof)
                ups.append({"name": name, "base_url": base, "model": model,
                            "key_slot": slot, "key_ready": bool(key)})
            return self._json(200, {"ok": True, "service": "gbt-model-bridge",
                                    "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                    "default": DEFAULT, "upstreams": ups,
                                    "note": "钥只在桥里；页面永远拿不到明文"})
        if self.path.startswith("/v1/models"):
            return self._json(200, {"object": "list", "data": [
                {"id": m, "owned_by": n, "base_url": b} for n, (b, m, _p, _t) in UPSTREAMS.items()]})
        if self.path.startswith("/v1/caps"):
            # 页面互通的口：341 个能力位 + 各自页面地址，一次给全（前端缓存）
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
        KNOWN = ("/v1/chat/completions", "/v1/route", "/v1/dispatch", "/v1/calc")
        if not any(self.path.startswith(k) for k in KNOWN):
            return self._json(404, {"error": {"message": "no route %s" % self.path}})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception as exc:                              # noqa: BLE001
            return self._json(400, {"error": {"message": "请求体不是 JSON：%s" % exc}})

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
                ensure_selfhost()          # 按需激活：不在就现拉
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
            try:
                resp = urllib.request.urlopen(l_req, timeout=budget)
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
                raw = (exc.read() or b"")[:400].decode("utf-8", "replace")
                attempts.append({"lane": lane, "http": exc.code, "why": raw[:200],
                                 "ms": int((time.perf_counter() - lt0) * 1000)})
                sys.stderr.write("[bridge] lane=%s http=%s slot=%s\n" % (lane, exc.code, l_slot))
            except Exception as exc:                          # noqa: BLE001
                attempts.append({"lane": lane, "why": "%s" % type(exc).__name__,
                                 "ms": int((time.perf_counter() - lt0) * 1000)})
                sys.stderr.write("[bridge] lane=%s net_error=%s\n" % (lane, type(exc).__name__))
        if resp is None:
            return self._json(200, {"ok": False, "upstream": name, "attempts": attempts,
                                    "lane_used": None, "weights_ours": False,
                                    "error": {"message": "所有车道都没回包（含兜底）"}})
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
    print("模型桥已起：http://127.0.0.1:%d  （只在回环；Ctrl-C 停）" % port)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停。")
    return 0


def self_test(port: int) -> int:
    """起一个线程跑桥，打一发真请求，打印读数后退出（证明桥真能用，不是写完就算）。"""
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
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
