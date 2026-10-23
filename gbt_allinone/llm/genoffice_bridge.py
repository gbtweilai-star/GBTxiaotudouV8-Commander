# gbt-capability: genoffice_bridge
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GenOffice AI 线接入统一密钥网关（genoffice_bridge）· 🥔GBT小土豆V8

════════════════════════════════════════════════════════════════════════
【为什么存在 —— 主人的令】

  令（2026-09-27）：「把密钥按顺序接上这个独立页面的 AI 然后品牌统一」
  补充令          ：「网关的 AI 的那条留着」

  落地形态 = **本地 OpenAI 兼容反向代理**：
      GenOffice  →  本桥（127.0.0.1:31716/v1）  →  key_gateway 选路  →  上游真模型
  于是 GenOffice 只需要握**一把统一密钥**（`gbtv8-…`），
  背后的换道、冷却、禁用、耗尽全部由网关机械闸管着。

  「那条留着」的落实方式：**保留 GenOffice 的 `custom` provider 不动**，
  只把它的 `baseUrl` 指向本桥、`apiKey` 换成统一密钥 —— 不新增 AI 线，只换接头。

════════════════════════════════════════════════════════════════════════
【对端契约（读 `resources/app.asar` 得到，不是猜的）】

  取证位置：`out/main/index.js`

  | 项 | 读数 |
  |---|---|
  | 主聊天函数 | `openAiCompatibleTurn(baseUrl, config, system, messages, tools, maxTokens, cb, wd, options)` |
  | 请求 | `POST {baseUrl}/chat/completions` · `Authorization: Bearer <apiKey>` |
  | 请求体 | `{model, max_tokens ∥ max_completion_tokens, messages, tools?, temperature:0.3, stream:true}` |
  | 消息形态 | `[{role:"system",content:str},{role:"user",content:str ∥ [{type:"text"},{type:"image_url",image_url:{url:"data:…;base64,…"}}]},{role:"assistant",…,reasoning_content?,tool_calls?},…]` |
  | 响应期望 | **SSE**（OpenAI `chat.completion.chunk`）；**同时容忍** `application/json` 整体返回 |
  | 辅助路径 | `chatOpenAiCompatible(...)` —— **非流式**，读 `choices[0].message.content` |
  | 连接窗 | `AI_CONNECT_TIMEOUT_MS = 60000` ⇒ **第一字节必须 60s 内到** |
  | 空闲窗 | `AI_IDLE_TIMEOUT_MS = 180000` ⇒ 之后每 180s 至少一个字节 |

  ⇒ **两条硬结论**：
     ① 必须做**真流式透传**。缓冲到生成结束才回，会撞 60s 连接窗（长回答必失败）。
     ② **换道总预算必须远小于 60s**，否则「换道」本身会把对端等的超时先撞掉。

════════════════════════════════════════════════════════════════════════
【三条纪律（不商量）】

  1. **只绑回环**。`0.0.0.0` 一律拒绝 —— 本桥是个带密钥校验的代理，
     绑出去就等于把网关的换道能力对公网开放。
  2. **每个 /v1/* 请求都必须带 `gbtv8-` 统一密钥**，经 `key_gateway.verify()`
     按**摘要比对**校验（库里只有 blake2b 摘要，没有明文）。
     无密钥 / 假密钥一律 401 —— **本桥不是开放代理**。
  3. **明文密钥永不出现在响应、日志、磁盘**。上游真密钥只在出网那一瞬间存在于
     进程内存；对外一律用 `key_gateway.mask()`（形态
     `🥔GBT小土豆V8|agnes|sk-O…RQca|#36d0a692`）。
     **不另开第二条取密钥的路**（R-H201）：本桥只调 `key_gateway.materialize()`。

════════════════════════════════════════════════════════════════════════
【诚实边界】

  本桥保证：GenOffice 侧**只握一把钥匙**；换道是**活的**（每次请求现算顺序）；
  429/402/401 会**自动落向下一家且真能出结果**；全不可用时 fail-closed 如实报错；
  明文密钥不落任何一处。

  本桥**不保证**：
    · 免费额度用不完（额度由平台给，不由本桥给）；
    · 400/422 自动修好 —— 那是请求参数问题，本桥只如实报错（I2：换道会把
      「参数写错」伪装成「模型不行」）；
    · **流中途**故障能换道 —— SSE 头一旦发出就无法回到「换一家重来」。
      流中途出错只能如实推一个 SSE error 事件后收尾（下面 `_relay_stream` 里
      有明确标注的那一处）。这是流式协议的**固有代价**，不是本桥的疏忽。
    · 生图/生视频（`/v1/images/generations`）—— `multimodal_port` 目前只到
      「密钥分叉 + 目录 + 探测」，**没有生图调用实现**，故本桥如实回 501，
      不假装能画。

用法
    # 起服务（默认 127.0.0.1:31716）
    python -m gbt_allinone.llm.genoffice_bridge serve

    # 自检（会在临时端口起真服务 + 打真请求；--offline 跳过出网那两条）
    python -m gbt_allinone.llm.genoffice_bridge selftest

    # 看接线状态（免密钥）
    curl http://127.0.0.1:31716/health
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import ssl
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_HERE = Path(__file__).resolve()
if str(_HERE.parents[2]) not in sys.path:
    sys.path.insert(0, str(_HERE.parents[2]))

try:                                                    # 作为包模块导入
    from . import key_gateway as KG
except ImportError:                                     # 作为脚本直接跑
    from gbt_allinone.llm import key_gateway as KG      # type: ignore

BRAND = "GBT小土豆V8"
BRAND_TAG = "🥔GBT小土豆V8"
CAP = "genoffice_bridge"
VERSION = "1.0"

DEFAULT_PORT = 31716
LOOPBACK = ("127.0.0.1", "localhost", "::1")

# ── 对端实测常量（survey/old-main.js）──────────────────────────────────
GI_CONNECT_TIMEOUT_MS = 60_000      # AI_CONNECT_TIMEOUT_MS
GI_IDLE_TIMEOUT_MS = 180_000        # AI_IDLE_TIMEOUT_MS

# ⚠️ 这两个数是**由对端倒推出来的硬预算**，不是随手定的：
#    对端首字节窗 60s ⇒ 一次请求的全部换道尝试必须在此之内完成，
#    否则「我还在换道」而「对端已经超时」⇒ 报成超时，比不换道还糟。
FIRST_BYTE_BUDGET_S = 45.0          # 留 15s 余量给网络与序列化
PER_ATTEMPT_CONNECT_S = 12.0        # 单次上游连接超时
PER_ATTEMPT_READ_S = 300.0          # 流已建立后的单次读超时（配合 180s 空闲窗）
RETRY_SAME_MAX = 1                  # 同一家最多再试 1 次（transient/5xx）

MAX_BODY = 32 * 1024 * 1024         # 请求体上限（含 base64 图片，故给得宽）
MAX_UPSTREAM_BYTES = 64 * 1024 * 1024

# ⚠️ 血账（2026-09-28 实弹首次出网即炸）：HTTP 响应头按 **latin-1** 编码
#    （`http.server.send_header` → `.encode('latin-1','strict')`）。
#    我最初把「带 🥔 的掩码」塞进 `X-GBT-Key`、把 `GBT小土豆V8` 塞进 `X-GBT-Brand`
#    ⇒ 直接 `UnicodeEncodeError`，**连接被掐断，对端收到 RemoteDisconnected**。
#    教训：**品牌标志属于响应体，不属于响应头**。头里只放 ASCII 可印字符。
BRAND_ASCII = "GBT-XiaoTuDou-V8"    # 头里用的 ASCII 品牌 slug


def _hdr(value) -> str:
    """把任意值净化成合法的 HTTP 头值（ASCII、无 CR/LF）。

    双保险：即使将来 `PROVIDERS` 里出现非 ASCII 的名字，也只是这个头难看，
    不会把整个响应打崩。
    """
    s = str(value or "")
    s = s.replace("\r", "").replace("\n", "")
    return s.encode("ascii", "replace").decode("ascii")[:200]


def obs_headers(prov: str, mat: dict) -> dict:
    """对外**可观测性头**（全 ASCII）。

    ⚠️ 只给**指纹**（`#36d0a692`），不给掩码 —— 掩码里带品牌 emoji 🥔，
    而头必须 latin-1；顺带也少暴露 4 个明文字符。要看完整掩码请读
    `/v1/models` 或 `/health` 的响应**体**（体是 UTF-8，放得下 🥔）。
    """
    return {"X-GBT-Brand": BRAND_ASCII,
            "X-GBT-Provider": _hdr(prov),
            "X-GBT-Key-Fp": _hdr(KG.fingerprint(str(mat.get("key") or ""))),
            "X-GBT-Wire": _hdr(mat.get("wire") or "")}


# I3：不榨干储备 —— 这里只做**提示**，真正的储备由 key_gateway.RESERVE_RATIO 把控。


class _UpstreamFail(Exception):
    """上游失败（带状态码，供网关分类）。**消息里绝不含密钥。**"""

    def __init__(self, status, text):
        self.status = int(status or 0)
        self.text = str(text or "")[:600]
        super().__init__("HTTP %s: %s" % (self.status, self.text[:200]))


# ══════════════════════════════════════════════════════════════════════
# 一、接线辅助（纯函数，便于自检直接钉）
# ══════════════════════════════════════════════════════════════════════

def model_index() -> dict:
    """`model 名 → provider 名` 的映射。

    用途：GenOffice 的 `providers.custom.model` 就是它想用的模型名；
    拿它去**固定优先通道**（`plan(prefer=…)`），等价于给主人一个「模型选择器」。
    """
    idx = {}
    for p in KG.PROVIDERS:
        m = str(p.get("model") or "").strip().lower()
        if m:
            idx[m] = p["name"]
    # 常见别名（对端 UI 里出现的名字）
    idx.setdefault("gpt-4o-mini", "openai")
    idx.setdefault("deepseek-flash", "deepseek")
    idx.setdefault("agnes-2.5-flash", "agnes")
    return idx


def prefer_from_model(model: str) -> str:
    """入站 model 名 → 优先 provider。认不出就返回空（交给网关按能源排）。"""
    m = str(model or "").strip().lower()
    if not m:
        return ""
    idx = model_index()
    if m in idx:
        return idx[m]
    tail = m.rsplit("/", 1)[-1]                 # `openai/gpt-4o-mini` 这类带前缀的
    if tail in idx:
        return idx[tail]
    return ""


def build_upstream_body(incoming: dict, mat: dict) -> dict:
    """把对端请求体改写成「发给某一家上游」的请求体。

    ⚠️ 关键取舍（实测得出，不是风格问题）：

    · **上游声明了 model ⇒ 覆盖**。因为 `agnes-2.5-flash` 在 deepseek 上不存在，
      换道后不覆盖 model 必然 404。
    · **上游 model 为空 ⇒ 透传入站 model**。`freellmapi`（聚合 34 家）与
      `potato`（本地）在 `PROVIDERS` 里 model 就是空字符串 —— 它们**按模型名路由**，
      覆盖成空串会把请求打废。这一条是正负对照的核心（自检 C2）。
    """
    body = dict(incoming)
    up_model = str(mat.get("model") or "").strip()
    if up_model:
        body["model"] = up_model
    elif not str(body.get("model") or "").strip():
        raise _UpstreamFail(400, "入站请求既没给 model，上游也没声明 model —— 无法路由")
    # 推理模型坑：max_tokens 太小会被 reasoning 吃光 ⇒ 200 但 content 空。
    # 网关在声明层给了 min_max_tokens 下限，这里保证不低于它。
    floor = int(mat.get("min_max_tokens", 0) or 0)
    if floor:
        cur = body.get("max_tokens", body.get("max_completion_tokens"))
        try:
            cur = int(cur) if cur is not None else 0
        except (TypeError, ValueError):
            cur = 0
        if cur < floor:
            # 谁在用它就改谁，不无中生有地加一个对端没发的字段
            if "max_completion_tokens" in body:
                body["max_completion_tokens"] = floor
            else:
                body["max_tokens"] = floor
    return body


def is_loopback_url(url: str) -> bool:
    """上游地址是否指向本机。

    ⚠️ 这是**有意的私有地址放行**，理由：`PROVIDERS` 里 `freellmapi`(31415) 与
    `potato`(8111) **在声明层就是回环地址**，且地址来自我们自己的 `PROVIDERS`，
    不是来自请求方 —— 不构成 SSRF 面。除此之外一律不准私有地址。
    """
    try:
        h = urllib.parse.urlsplit(str(url)).hostname or ""
    except ValueError:
        return False
    return h.lower() in LOOPBACK


def _scan_plaintext(blobs: list, secrets: list) -> list:
    """在若干文本里找有没有出现明文密钥。返回命中列表（**只报位置不报内容**）。"""
    hits = []
    for s in secrets:
        s = str(s or "")
        if len(s) < 8:
            continue
        for i, b in enumerate(blobs):
            if s in str(b or ""):
                hits.append({"blob_index": i, "secret_fingerprint": KG.fingerprint(s)})
    return hits


# ══════════════════════════════════════════════════════════════════════
# 二、出站（唯一一条路：net_guard 守门）
# ══════════════════════════════════════════════════════════════════════

def _open_upstream(mat: dict, body: dict, connect_s: float):
    """向上游发起一次请求，返回 (conn, resp)。

    ── 为什么流式这条不走 `cloud_llm._safe_json` ─────────────────────
    `_safe_json` 会 `response.read()` 到 EOF **再返回** —— 那是「缓冲」，不是「透传」。
    流式场景必须边收边发（否则撞对端 60s 连接窗），故此处改用
    `net_guard.validate_url()` **先做同一套守门**（协议/端口/SSRF/主机策略），
    再自己用 `http.client` 逐块读。
    ⇒ **守门没有绕过，绕开的只是「缓冲」这一步。** 这是一个刻意的、有理由的偏离。

    非流式场景仍走 `net_guard.safe_request`（见 `_call_json`），那条路连审计一起走全。
    """
    from gbt_allinone.security import net_guard as NG

    url = str(mat["url"]).rstrip("/") + "/chat/completions"
    v = NG.validate_url(url, allow_private=is_loopback_url(url))
    headers = {"Content-Type": "application/json", "Accept": "application/json",
               "Authorization": "Bearer " + mat["key"],
               "User-Agent": "Mozilla/5.0 GBT-V8/1.0"}
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    if v.scheme == "https":
        conn = http.client.HTTPSConnection(
            v.host, v.port, timeout=connect_s,
            context=ssl.create_default_context())
    else:
        conn = http.client.HTTPConnection(v.host, v.port, timeout=connect_s)
    try:
        conn.request("POST", v.path, body=payload, headers=headers)
        resp = conn.getresponse()
    except Exception as exc:                            # noqa: BLE001
        conn.close()
        # 网络/连接类 → 无状态码，交给网关归类为 transient
        raise _UpstreamFail(0, "连接上游失败：%s" % str(exc)[:200]) from exc
    return conn, resp


def _call_json(mat: dict, body: dict, timeout_s: float) -> dict:
    """非流式出站：走 `net_guard.safe_request`（守门 + AI 审计一起走全）。"""
    from gbt_allinone.security import net_guard as NG

    url = str(mat["url"]).rstrip("/") + "/chat/completions"
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json",
               "Authorization": "Bearer " + mat["key"],
               "Accept": "application/json"}
    r = NG.safe_request(url, method="POST", headers=headers, body=payload,
                        timeout=timeout_s, max_bytes=MAX_UPSTREAM_BYTES,
                        allow_private=is_loopback_url(url))
    status = int(r.get("status") or 0)
    text = (r.get("body") or b"").decode("utf-8", errors="replace")
    if status >= 400:
        raise _UpstreamFail(status, text)
    try:
        return json.loads(text)
    except Exception as exc:                            # noqa: BLE001
        raise _UpstreamFail(502, "上游返回非 JSON：%s" % text[:200]) from exc


def _sse(payload: dict) -> bytes:
    return ("data: " + json.dumps(payload, ensure_ascii=False) + "\n\n").encode("utf-8")


def _synth_sse_from_json(data: dict, model: str) -> bytes:
    """把「整体 JSON 结果」**合成**成 OpenAI SSE 片段。

    为什么要这一步：对端 `openAiCompatibleTurn` 发的是 `stream:true`，虽然它
    也容忍整体 JSON，但**非 openai 协议族**（anthropic/gemini）本来就没有
    OpenAI 式 SSE。合成就地补齐，让对端只面对一种形态。
    """
    msg = (data.get("choices") or [{}])[0].get("message") or {}
    content = msg.get("content") or ""
    base = {"id": data.get("id") or "chatcmpl-gbt", "object": "chat.completion.chunk",
            "created": int(data.get("created") or time.time()), "model": model}
    out = [_sse({**base, "choices": [{"index": 0, "delta": {"role": "assistant"},
                                      "finish_reason": None}]})]
    if content:
        out.append(_sse({**base, "choices": [{"index": 0,
                                              "delta": {"content": content},
                                              "finish_reason": None}]}))
    out.append(_sse({**base, "choices": [{"index": 0, "delta": {},
                                          "finish_reason": "stop"}]}))
    out.append(b"data: [DONE]\n\n")
    return b"".join(out)


# ══════════════════════════════════════════════════════════════════════
# 三、非 openai 协议族的**最小**转换（anthropic / gemini）
#     诚实标注：只覆盖文本消息，**不支持 tools**，且**不做流式**（合成 SSE 顶上）。
#     两家当前无密钥 ⇒ 这条路径是「设计完整但未被实弹走过」的。代码里不假装。
# ══════════════════════════════════════════════════════════════════════

def _split_system(body: dict) -> tuple:
    """拆出 (system 文本, 其余消息)。"""
    sys_txt, rest = "", []
    for m in (body.get("messages") or []):
        if str(m.get("role")) == "system":
            c = m.get("content")
            sys_txt += (c if isinstance(c, str) else json.dumps(c, ensure_ascii=False))
        else:
            rest.append(m)
    return sys_txt, rest


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(p.get("text") or "") for p in content
                         if isinstance(p, dict) and p.get("type") == "text")
    return ""


def to_anthropic(body: dict, mat: dict) -> dict:
    sys_txt, rest = _split_system(body)
    msgs = [{"role": ("assistant" if str(m.get("role")) == "assistant" else "user"),
             "content": _text_of(m.get("content"))} for m in rest]
    return {"model": mat.get("model") or body.get("model"),
            "max_tokens": int(body.get("max_tokens") or 4096),
            "system": sys_txt, "messages": msgs}


def from_anthropic(data: dict) -> dict:
    txt = ""
    for blk in (data.get("content") or []):
        if isinstance(blk, dict) and blk.get("type") == "text":
            txt += str(blk.get("text") or "")
    return {"choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": txt}}]}


def to_gemini(body: dict, mat: dict) -> dict:
    sys_txt, rest = _split_system(body)
    contents = [{"role": ("model" if str(m.get("role")) == "assistant" else "user"),
                 "parts": [{"text": _text_of(m.get("content"))}]} for m in rest]
    out = {"contents": contents}
    if sys_txt:
        out["systemInstruction"] = {"parts": [{"text": sys_txt}]}
    return out


def from_gemini(data: dict) -> dict:
    txt = ""
    for cand in (data.get("candidates") or []):
        for part in ((cand.get("content") or {}).get("parts") or []):
            txt += str(part.get("text") or "")
    return {"choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": txt}}]}


def _upstream_nonnative(mat: dict, body: dict, timeout_s: float) -> dict:
    """anthropic / gemini 的非流式出站（走 net_guard 守门）。返回**统一成 OpenAI 形态**。"""
    from gbt_allinone.security import net_guard as NG

    wire, url = mat["wire"], str(mat["url"]).rstrip("/")
    if wire == "anthropic":
        req_url = url + "/v1/messages"
        hdr = {"Content-Type": "application/json", "x-api-key": mat["key"],
               "anthropic-version": "2023-06-01"}
        payload = to_anthropic(body, mat)
    else:                                               # gemini
        m = urllib.parse.quote(str(mat.get("model") or body.get("model") or ""), safe="")
        req_url = "%s/models/%s:generateContent?key=%s" % (url, m, mat["key"])
        hdr = {"Content-Type": "application/json"}
        payload = to_gemini(body, mat)
    r = NG.safe_request(req_url, method="POST", headers=hdr,
                        body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                        timeout=timeout_s, max_bytes=MAX_UPSTREAM_BYTES,
                        allow_private=is_loopback_url(req_url))
    status = int(r.get("status") or 0)
    text = (r.get("body") or b"").decode("utf-8", errors="replace")
    if status >= 400:
        raise _UpstreamFail(status, text)
    try:
        data = json.loads(text)
    except Exception as exc:                            # noqa: BLE001
        raise _UpstreamFail(502, "上游返回非 JSON：%s" % text[:200]) from exc
    return from_anthropic(data) if wire == "anthropic" else from_gemini(data)


# ══════════════════════════════════════════════════════════════════════
# 四、HTTP 服务
# ══════════════════════════════════════════════════════════════════════

class Handler(BaseHTTPRequestHandler):
    server_version = "GBT-GenOfficeBridge/%s" % VERSION
    protocol_version = "HTTP/1.1"

    # ── 记账（**不记内容、不记密钥**）───────────────────────────────
    def log_message(self, fmt, *args):                  # 关掉默认逐请求访问日志
        return

    def _note(self, **kw):
        row = {"brand": BRAND, "cap": CAP, "t": time.strftime("%Y-%m-%dT%H:%M:%S")}
        row.update(kw)
        try:
            print(json.dumps(row, ensure_ascii=False), file=sys.stderr)
        except Exception:                               # noqa: BLE001
            pass

    # ── 响应原语 ───────────────────────────────────────────────────
    def _json(self, code: int, obj: dict, extra: dict | None = None):
        body = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(_hdr(k), _hdr(v))
        self.end_headers()
        self.wfile.write(body)

    def _err(self, code: int, kind: str, msg: str, **extra):
        self._json(code, {"error": {"message": msg, "type": kind,
                                    "brand": BRAND_TAG, **extra}})

    def _chunk(self, data: bytes):
        if not data:
            return
        self.wfile.write(("%x\r\n" % len(data)).encode("ascii") + data + b"\r\n")

    def _chunk_end(self):
        self.wfile.write(b"0\r\n\r\n")

    # ── 统一密钥校验 ───────────────────────────────────────────────
    def _auth(self):
        """返回 (ok, info)。**库里只有摘要**，比对不出明文。"""
        h = self.headers.get("Authorization") or ""
        if not h.lower().startswith("bearer "):
            return False, {"error": "缺少 Authorization: Bearer <gbtv8-…>"}
        raw = h[7:].strip()
        if not raw.startswith(KG.MINT_PREFIX):
            return False, {"error": "不是统一网关密钥（前缀应为 %r）" % KG.MINT_PREFIX}
        v = KG.verify(raw)
        return bool(v.get("ok")), v

    # ── 路由 ───────────────────────────────────────────────────────
    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path.rstrip("/") or "/"
        if path in ("/health", "/healthz"):
            try:
                e = KG.energy()
                head = {"ok": True, "brand": BRAND, "service": CAP,
                        "version": VERSION, "auth": "Bearer %s<32hex>" % KG.MINT_PREFIX,
                        "bound": "%s:%s" % self.server.server_address[:2],
                        "gateway_alive": e.get("alive"), "gateway_total": e.get("total"),
                        "invariants": e.get("invariants"),
                        "note": "统一密钥经摘要比对校验；明文密钥不落响应/日志/磁盘"}
            except Exception as exc:                    # noqa: BLE001
                head = {"ok": True, "brand": BRAND, "service": CAP,
                        "gateway_error": str(exc)[:200]}
            self._json(200, head)
            return
        if path in ("/v1/models", "/models"):
            ok, info = self._auth()
            if not ok:
                self._err(401, "authentication_error", "统一密钥校验失败",
                          detail=info.get("error"))
                return
            self._models()
            return
        self._err(404, "not_found", "未知路径（可用：/health、/v1/models、"
                                    "/v1/chat/completions）")

    def _models(self):
        """把「网关当前真能出网的通道」报成模型列表，供对端 UI 选。

        ⚠️ 用 `alive` 过滤 —— 这就是「模型选择器只会列出真能用的」。
        """
        rows = []
        for x in KG.rank():
            if not x["alive"]:
                continue
            mid = str(x["model"] or "").strip()
            if not mid:
                # 空 model 的聚合通道（freellmapi / potato）以通道名报出
                mid = x["provider"]
            rows.append({"id": mid, "object": "model", "owned_by": x["provider"],
                         "x_gbt_tier": x.get("tier"), "x_gbt_masked": ""})
        for r in rows:                                  # 掩码单独补，绝不带明文
            k, _ = KG.key_for(r["owned_by"])
            r["x_gbt_masked"] = KG.mask(k, r["owned_by"]) if k else ""
        self._json(200, {"object": "list", "brand": BRAND_TAG, "data": rows,
                         "note": "仅列出网关判定为「可用」的通道"})

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path.rstrip("/") or "/"
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            self._err(411, "invalid_request_error", "缺 Content-Length 或请求体为空")
            return
        if length > MAX_BODY:
            self._err(413, "invalid_request_error",
                      "请求体超过 %d 字节上限" % MAX_BODY, received_bytes=length)
            return

        if path in ("/v1/images/generations", "/images/generations"):
            self._images(length)
            return
        if path not in ("/v1/chat/completions", "/chat/completions",
                        "/v1/completions"):
            self._drain(length)
            self._err(404, "not_found",
                      "未知路径（本桥只接 /v1/chat/completions 与 /v1/images/generations）")
            return

        # 鉴权要在**读体之前**做 —— 未授权请求不该让我们先吃下 32MB
        ok, info = self._auth()
        if not ok:
            self._drain(length)
            self._note(event="denied", path=path, why=str(info.get("error"))[:120])
            self._err(401, "authentication_error", "统一密钥校验失败",
                      detail=info.get("error"))
            return
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:                               # noqa: BLE001
            self._err(400, "invalid_request_error", "请求体不是合法 JSON")
            return
        if not isinstance(body, dict) or not isinstance(body.get("messages"), list):
            self._err(400, "invalid_request_error", "缺少 messages 数组")
            return
        self._chat(body, info)

    def _drain(self, length: int):
        try:
            left = int(length)
        except (TypeError, ValueError):
            return
        if left > MAX_BODY:
            left = MAX_BODY
        while left > 0:
            blk = self.rfile.read(min(65536, left))
            if not blk:
                break
            left -= len(blk)

    def _images(self, length: int):
        """生图/生视频：**如实回 501**。

        `multimodal_port` 目前只到「Y 字端口 + 维度目录 + 通道探测」，
        **没有生图调用实现**（其 `run()` 只有 catalog/status/probe/arms）。
        假装能画比如实回绝更坏 —— 前者会让主人以为链路通了。
        """
        ok, _ = self._auth()
        self._drain(length)
        if not ok:
            self._err(401, "authentication_error", "统一密钥校验失败")
            return
        try:
            import importlib
            mm = importlib.import_module("gbt_allinone.llm.multimodal_port")
            st = mm.status()
            catalog = {"text": mm.catalog("text"), "image": mm.catalog("image"),
                       "video": mm.catalog("video")}
        except Exception as exc:                        # noqa: BLE001
            st, catalog = {"error": str(exc)[:200]}, {}
        self._json(501, {"error": {
            "message": "本桥不生图：`multimodal_port` 尚无生图调用实现（只有密钥分叉与目录）。"
                       "生图线请走 Y 字端口（MULTIMODAL_Y_PORT.md）或等该端口补上 generate。",
            "type": "not_implemented", "brand": BRAND_TAG,
            "multimodal_status": st, "dimension_catalog": catalog}})

    # ── 主路径：chat/completions ───────────────────────────────────
    def _chat(self, body: dict, keyinfo: dict):
        stream = bool(body.get("stream"))
        prefer = prefer_from_model(body.get("model"))
        pl = KG.plan(need_tokens=_need_tokens(body), prefer=prefer)
        if not pl.get("ok"):
            self._note(event="fail_closed", reason=pl.get("error"))
            self._err(503, "no_available_channel",
                      pl.get("error") or "所有通道都不可用",
                      candidates=pl.get("candidates"), how_to_fix=pl.get("how_to_fix"))
            return

        order = [o["provider"] for o in (pl.get("order") or []) if o.get("alive")]
        if not order:
            self._err(503, "no_available_channel", "网关没有任何可出网的通道")
            return

        t0, tried = time.time(), []
        deadline = t0 + FIRST_BYTE_BUDGET_S
        stream_started = False

        for prov in order:
            if time.time() >= deadline:
                tried.append({"provider": prov, "skipped": "首字节预算耗尽"})
                break
            mat = KG.materialize(prov)
            if not mat.get("ok"):
                tried.append({"provider": prov, "skipped": mat.get("error")})
                continue
            try:
                up_body = build_upstream_body(body, mat)
            except _UpstreamFail as f:
                tried.append({"provider": prov, "err_class": "bad_request",
                              "status": f.status, "error": f.text})
                break                                   # 参数问题 ⇒ 硬停（I2）
            if stream and mat.get("wire") != "openai":
                up_body = dict(up_body)
                up_body.pop("stream", None)             # 非 openai 族不做流式

            attempts = 0
            while True:
                attempts += 1
                remain = max(2.0, min(PER_ATTEMPT_CONNECT_S, deadline - time.time()))
                try:
                    if stream:
                        self._relay_stream(mat, up_body, prov, tried, pl,
                                           keyinfo, t0, stream_started)
                        return
                    data = (self._call_json_path(mat, up_body)
                            if mat.get("wire") == "openai"
                            else _upstream_nonnative(mat, up_body, PER_ATTEMPT_READ_S))
                    KG.note_result(prov, ok=True, tokens=_tokens_of(data))
                    self._note(event="call_ok", wire=mat.get("wire"), provider=prov,
                               model=mat.get("model") or body.get("model"),
                               masked=mat.get("masked"), ms=int((time.time() - t0) * 1000),
                               key_id=keyinfo.get("key_id"),
                               tried_before=[t["provider"] for t in tried[:3]])
                    self._json(200, _ensure_shape(data, mat),
                               extra=obs_headers(prov, mat))
                    return
                except _UpstreamFail as f:
                    d = KG.note_result(prov, ok=False, status=f.status, error=f.text)
                    tried.append({"provider": prov, "attempt": attempts,
                                  "err_class": d.get("err_class"), "status": f.status,
                                  "error": f.text[:200]})
                    if not d.get("retry_same") and not d.get("escalate"):
                        # bad_request / unknown ⇒ **硬停**，不拿换道掩盖自己的错
                        self._note(event="hard_stop", provider=prov,
                                   err_class=d.get("err_class"), status=f.status)
                        self._err(int(f.status) if f.status in (400, 401, 402, 403, 404,
                                                                422, 429) else 502,
                                  "upstream_error", f.text,
                                  err_class=d.get("err_class"),
                                  why_no_failover=d.get("action"), provider=prov)
                        return
                    if d.get("retry_same") and attempts <= RETRY_SAME_MAX \
                            and time.time() < deadline:
                        time.sleep(0.8 * attempts)
                        continue
                    break                               # 本家到此为止 → 下一家

        self._note(event="fail_closed", tried=len(tried))
        self._err(502, "all_channels_failed",
                  "全部 %d 条通道都试过且都失败 —— 如实报错，不静默降级" % len(order),
                  tried=tried, first_byte_budget_s=FIRST_BYTE_BUDGET_S,
                  how_to_fix="补密钥 / key_gateway op=reset 清运行态 / 等冷却到期")

    def _call_json_path(self, mat: dict, up_body: dict) -> dict:
        """openai 族非流式。`stream` 已被移除。"""
        b = dict(up_body)
        b.pop("stream", None)
        return _call_json(mat, b, PER_ATTEMPT_READ_S)

    def _relay_stream(self, mat, up_body, prov, tried, pl, keyinfo, t0, started):
        """真流式：先连上游，**拿到 2xx 头之后再**给对端发响应头，然后逐块透传。

        顺序是刻意的：上游 4xx/5xx 时我们**还没给对端发过任何字节**，
        于是还能干净地换道（`_UpstreamFail` 冒泡到 `_chat` 的循环）。
        """
        conn, resp = _open_upstream(mat, up_body, PER_ATTEMPT_CONNECT_S)
        try:
            if resp.status >= 400:
                raise _UpstreamFail(resp.status,
                                    resp.read(65536).decode("utf-8", errors="replace"))
            KG.note_result(prov, ok=True)
            self._note(event="stream_open", provider=prov,
                       model=mat.get("model") or up_body.get("model"),
                       masked=mat.get("masked"), key_id=keyinfo.get("key_id"),
                       ms=int((time.time() - t0) * 1000),
                       tried_before=[t["provider"] for t in tried[:3]])
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-transform")
            self.send_header("Transfer-Encoding", "chunked")
            for k, v in obs_headers(prov, mat).items():
                self.send_header(k, v)
            self.end_headers()
            try:
                while True:
                    blk = resp.read(4096)
                    if not blk:
                        break
                    self._chunk(blk)
                    try:
                        self.wfile.flush()
                    except Exception:                   # noqa: BLE001
                        pass
                self._chunk_end()
            except Exception as exc:                    # noqa: BLE001
                # ⚠️ 流中途故障：头已发出，**无法换道**（SSE 协议固有代价）。
                #    如实推一个 error 事件后收尾，绝不静默截断成「答完了」。
                self._note(event="stream_broken", provider=prov, error=str(exc)[:160])
                try:
                    self._chunk(_sse({"error": {
                        "message": "上游流中断（已发出的头无法撤回，故不能换道）：%s"
                                   % str(exc)[:200],
                        "type": "upstream_stream_broken", "brand": BRAND_TAG}}))
                    self._chunk_end()
                except Exception:                       # noqa: BLE001
                    pass
        finally:
            try:
                conn.close()
            except Exception:                           # noqa: BLE001
                pass


def _need_tokens(body: dict) -> int:
    """给网关一个粗估的 token 需求（用于声明了配额的通道的余量判断）。"""
    try:
        approx_in = len(json.dumps(body.get("messages") or [], ensure_ascii=False)) // 4
    except Exception:                                   # noqa: BLE001
        approx_in = 0
    try:
        out = int(body.get("max_tokens") or body.get("max_completion_tokens") or 2048)
    except (TypeError, ValueError):
        out = 2048
    return max(0, approx_in + out)


def _tokens_of(data: dict) -> int:
    u = (data or {}).get("usage") or {}
    try:
        return int(u.get("total_tokens") or 0)
    except (TypeError, ValueError):
        return 0


def _ensure_shape(data: dict, mat: dict) -> dict:
    """保证回复符合对端期望：`choices[0].message.content` 非空。

    ⚠️ 血账：推理模型（agnes / NVIDIA glm）会把 `max_tokens` 吃光 ⇒
    HTTP 200 但 `content` 为空、`reasoning_content` 非空。对端会报
    「AI returned an empty response」——那是**假故障**。这里如实标注出来。
    """
    if not isinstance(data, dict):
        return {"choices": [{"message": {"role": "assistant",
                                         "content": str(data)}}]}
    ch = data.get("choices") or []
    msg = (ch[0].get("message") if ch and isinstance(ch[0], dict) else None) or {}
    if not msg.get("content"):
        if msg.get("reasoning_content"):
            data["x_gbt_warning"] = ("推理模型吃光了 token 预算：content 为空但 "
                                     "reasoning_content 非空。这不是模型不行，是预算不够 —— "
                                     "请调大 max_tokens（provider=%s）" % mat.get("provider"))
        else:
            data["x_gbt_warning"] = ("上游 200 但 content 为空（provider=%s，model=%s）"
                                     % (mat.get("provider"), mat.get("model")))
    return data


# ══════════════════════════════════════════════════════════════════════
# 五、启动 / 自检
# ══════════════════════════════════════════════════════════════════════

def make_server(host: str = "127.0.0.1", port: int = DEFAULT_PORT,
                allow_non_loopback: bool = False) -> ThreadingHTTPServer:
    if host not in LOOPBACK and not allow_non_loopback:
        raise SystemExit(
            "⛔ 拒绝绑 %r：本桥是带密钥校验的网关代理，绑非回环等于对外开放换道能力。\n"
            "   确有需要请显式加 --allow-non-loopback 并自行承担后果。" % host)
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.daemon_threads = True
    return srv


def serve(host="127.0.0.1", port=DEFAULT_PORT, allow_non_loopback=False):
    srv = make_server(host, port, allow_non_loopback)
    a = srv.server_address
    print(json.dumps({"ok": True, "brand": BRAND, "service": CAP, "version": VERSION,
                      "listening": "http://%s:%s" % (a[0], a[1]),
                      "openai_base_url": "http://%s:%s/v1" % (a[0], a[1]),
                      "genoffice_hint": "把 ai-settings.json 的 providers.custom.baseUrl "
                                        "指向上面这行，apiKey 换成 gbtv8- 统一密钥",
                      "auth": "Bearer gbtv8-<32hex>（经摘要比对）",
                      "note": "Ctrl+C 停止"}, ensure_ascii=False), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye · 🥔GBT小土豆V8", flush=True)
    finally:
        srv.server_close()


_LOOPBACK_OPENER = None


def _loopback_opener():
    """回环直连用的 opener —— **绕开环境代理**（本机实测逼出）。

    本机环境设了 `http_proxy = https_proxy = http://127.0.0.1:55482`，
    而 `urllib` 默认会把 **127.0.0.1 的请求也塞给代理**。后果是：
      · 走代理探 `127.0.0.1:31716` → 代理回 **502 Bad Gateway**
      · 绕过代理探 `127.0.0.1:31716` → **WinError 10061 目标计算机积极拒绝**
    两种状态在代码里长得一模一样，于是「服务没起」会被误读成「代理挡路」，
    接线判定、自检结论全部失真。回环请求本来就不该出小区，故此处强制直连。

    ⚠️ 机理备案（实测查清，别按直觉记）：
    真正起作用的是 `build_opener` 内部的 `skip.add(ProxyHandler)` —— 它让
    **默认的**（会读环境变量的）那个 ProxyHandler 不被安装。传进去的
    `ProxyHandler({})` **并没有被挂上**：它 `proxies` 为空 ⇒ 不 setattr 任何
    `*_open` 方法 ⇒ `add_handler` 抛 `ValueError("drop the handler")` ⇒
    被 `build_opener` 里 `except ValueError: pass` 静默吞掉。
    所以自检的判据是「有没有**带代理表**的 ProxyHandler」，不是「有没有 ProxyHandler」。
    """
    global _LOOPBACK_OPENER
    if _LOOPBACK_OPENER is None:
        import urllib.request as _ur
        _LOOPBACK_OPENER = _ur.build_opener(_ur.ProxyHandler({}))
    return _LOOPBACK_OPENER


def _status_or_none(url, timeout=3.0):
    """探一个 URL，返回状态码；任何异常（拒连/超时/代理错）返回 None。"""
    import urllib.request as _ur
    try:
        with _loopback_opener().open(_ur.Request(url, method="GET"),
                                     timeout=timeout) as r:
            return r.status
    except _ur.HTTPError as e:
        return e.code
    except Exception:                                   # noqa: BLE001
        return None


def _http(port, method, path, body=None, token=None, timeout=120):
    """自检用的小客户端（不引第三方依赖）—— 走 `_loopback_opener()` 直连。"""
    import urllib.request
    import urllib.error
    url = "http://127.0.0.1:%d%s" % (port, path)
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with _loopback_opener().open(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, dict(r.headers), raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, dict(e.headers), raw.decode("utf-8", errors="replace")


def selftest(live: bool = True, verbose: bool = True) -> int:
    """自检：在**临时端口起真服务**，打**真 HTTP 请求**。

    `live=False` 时跳过需要真实出网的两条（省钱、离线可用），其余照跑。
    """
    rows, results = [], []

    def chk(name, ok, detail=""):
        results.append(bool(ok))
        rows.append("  [%s] %s%s" % ("PASS" if ok else "FAIL", name,
                                     (" · " + str(detail)) if detail else ""))
        return bool(ok)

    # 1) 临时端口起真服务
    srv = make_server("127.0.0.1", 0)
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    minted = KG.mint("genoffice-bridge 自检", scopes="llm.chat")
    tok = minted.get("key")
    try:
        # ── A 存活与接线 ──
        st, hd, txt = _http(port, "GET", "/health")
        h = json.loads(txt)
        chk("A0 /health 免密钥可达", st == 200 and h.get("ok"))
        chk("A1 品牌在册", h.get("brand") == BRAND, h.get("brand"))
        chk("A2 只绑回环", str(h.get("bound", "")).startswith("127.0.0.1"), h.get("bound"))
        chk("A3 拒绝绑 0.0.0.0",
            _refuses_non_loopback(), "make_server('0.0.0.0') 必须 SystemExit")
        chk("A4 网关能源可读", isinstance(h.get("gateway_alive"), int),
            "alive=%s/%s" % (h.get("gateway_alive"), h.get("gateway_total")))
        # A5/A6/A7 —— 代理绕行回归钉（本机 http_proxy 会把回环请求也劫走）
        # 机理备案（实测查清，别再猜）：`build_opener(ProxyHandler({}))` **不是**
        # 「挂上一个空 handler」—— `ProxyHandler({})` 因 `proxies` 为空、不 setattr
        # 任何 `*_open` 方法，`add_handler` 抛 ValueError("drop the handler")，
        # 被 `build_opener` 内 `except ValueError: pass` 静默吞掉；真正起作用的是
        # `skip.add(ProxyHandler)` 让**默认的**（读环境变量的）那个不被安装。
        # 所以判定必须看「有没有**带代理表**的 ProxyHandler」，而不是「有没有 ProxyHandler」。
        import urllib.request as _urq
        _op = _loopback_opener()
        _bad = [x for x in _op.handlers
                if type(x).__name__ == "ProxyHandler" and getattr(x, "proxies", None)]
        chk("A5 自检 opener 不携带代理（回环请求不外发；退回无参 build_opener() 即 FAIL）",
            not _bad, "带代理的 ProxyHandler=%d 个 / 共 %d 个 handler"
            % (len(_bad), len(_op.handlers)))
        _st31716 = _status_or_none("http://127.0.0.1:%d/health" % DEFAULT_PORT)
        chk("A6 探 %d 不得是代理回的 502（否则『没起』被伪装成『代理挡路』）"
            % DEFAULT_PORT, _st31716 != 502, "status=%s" % _st31716)
        _envprx = _urq.getproxies()
        if _envprx:
            _defbad = [x for x in _urq.build_opener().handlers
                       if type(x).__name__ == "ProxyHandler"
                       and getattr(x, "proxies", None)]
            chk("A7 对照组成立：本机确有代理（默认 opener 读到了代理表）",
                bool(_defbad), "env=%s" % sorted(_envprx))
        else:
            chk("A7 本机无代理 —— A5/A6 属空转防护（记 PASS 并备案）",
                True, "getproxies()={}")

        # ── B 鉴权（三道负对照 + 一道正对照）──
        st, _, txt = _http(port, "POST", "/v1/chat/completions",
                           {"model": "x", "messages": [{"role": "user", "content": "hi"}]})
        chk("B0 无密钥必须 401", st == 401, "HTTP %s" % st)
        st, _, _ = _http(port, "POST", "/v1/chat/completions",
                         {"model": "x", "messages": [{"role": "user", "content": "hi"}]},
                         token="gbtv8-" + "0" * 32)
        chk("B1 伪造 gbtv8- 密钥必须 401", st == 401, "HTTP %s" % st)
        st, _, _ = _http(port, "POST", "/v1/chat/completions",
                         {"model": "x", "messages": [{"role": "user", "content": "hi"}]},
                         token="freellmapi-whatever-not-unified")  # PROC_SCAN_OFF: 自检负对照夹具（B2 非统一前缀必须 401），非真实密钥
        chk("B2 非统一前缀必须 401", st == 401, "HTTP %s" % st)
        st, _, txt = _http(port, "GET", "/v1/models", token=tok)
        chk("B3 真统一密钥放行 /v1/models", st == 200, "HTTP %s" % st)
        ids = [m.get("id") for m in (json.loads(txt).get("data") or [])]
        chk("B4 模型列表只含可用通道且有内容", bool(ids), "count=%d" % len(ids))

        # ── C 选路接线（正负对照：空 model 透传 vs 非空 model 覆盖）──
        chk("C0 认得出 agnes-2.5-flash → agnes",
            prefer_from_model("agnes-2.5-flash") == "agnes",
            prefer_from_model("agnes-2.5-flash"))
        chk("C1 认不出就交回网关排序",
            prefer_from_model("完全不存在的模型名") == "", "''")
        non_empty = next(p for p in KG.PROVIDERS if str(p.get("model") or "").strip())
        upstream_empty = next(p for p in KG.PROVIDERS if not str(p.get("model") or "").strip())
        b_non = build_upstream_body({"model": "对端发的名字"}, {
            "model": non_empty["model"], "min_max_tokens": 0})
        chk("C2 正对照：上游声明了 model ⇒ 必须**覆盖**",
            b_non["model"] == non_empty["model"],
            "%s → %s" % (non_empty["name"], b_non["model"]))
        b_emp = build_upstream_body({"model": "对端发的名字"}, {
            "model": upstream_empty.get("model") or "", "min_max_tokens": 0})
        chk("C2' 负对照：上游 model 为空 ⇒ 必须**透传**（覆盖会打废 freellmapi）",
            b_emp["model"] == "对端发的名字",
            "%s → %s" % (upstream_empty["name"], b_emp["model"]))
        b_floor = build_upstream_body({"model": "m", "max_tokens": 8},
                                      {"model": "m", "min_max_tokens": 512})
        chk("C3 推理模型下限：max_tokens 8 → 抬到 512",
            b_floor["max_tokens"] == 512, b_floor["max_tokens"])
        b_keep = build_upstream_body({"model": "m", "max_tokens": 4096},
                                     {"model": "m", "min_max_tokens": 512})
        chk("C3' 够大就不动它（不无谓改写）", b_keep["max_tokens"] == 4096, b_keep["max_tokens"])

        # ── D 密钥纪律（明文不许出现在任何对外字节里）──
        secrets = []
        for name in [p["name"] for p in KG.PROVIDERS]:
            m = KG.materialize(name)
            if m.get("ok"):
                secrets.append(m["key"])
        blobs = [txt, json.dumps(h)]
        blobs += [txt2 for _, _, txt2 in [_http(port, "GET", "/v1/models", token=tok)]]
        hits = _scan_plaintext(blobs, secrets)
        chk("D0 对外字节里零明文密钥", not hits, "命中 %d 处" % len(hits))
        mk = KG.mask(secrets[0] if secrets else "sk-abcdefghijkl", "t")
        chk("D1 掩码里无明文", (secrets[0] not in mk) if secrets else True, mk)
        chk("D2 掩码带品牌标志", mk.startswith(BRAND_TAG), mk.split("|")[0])
        # ⚠️ 回归钉（血账 2026-09-28）：头必须 latin-1 可编码。
        #    最初把带 🥔 的掩码塞进 X-GBT-Key ⇒ send_header 抛 UnicodeEncodeError
        #    ⇒ 对端 RemoteDisconnected。这条**不出网**就能钉死，不必等实弹。
        probe = obs_headers("agnes", {"key": secrets[0] if secrets else "sk-x",
                                      "wire": "openai",
                                      "masked": mk})
        try:
            [str(v).encode("latin-1") for v in probe.values()]
            hdr_ok = True
        except UnicodeEncodeError:
            hdr_ok = False
        chk("D3 响应头全 latin-1 可编码（血账回归钉）", hdr_ok,
            "X-GBT-Brand=%s" % probe.get("X-GBT-Brand"))
        chk("D3' 头里放的是指纹而不是带 emoji 的掩码",
            "🥔" not in json.dumps(probe, ensure_ascii=False),
            "X-GBT-Key-Fp=%s" % probe.get("X-GBT-Key-Fp"))

        # ── E 输入闸 ──
        st, _, _ = _http(port, "POST", "/v1/chat/completions",
                         {"no_messages": True}, token=tok)
        chk("E0 缺 messages ⇒ 400", st == 400, "HTTP %s" % st)
        st, _, _ = _http(port, "POST", "/v1/images/generations",
                         {"prompt": "土豆"}, token=tok)
        chk("E1 生图未实现 ⇒ 如实 501（不假装能画）", st == 501, "HTTP %s" % st)
        st, _, _ = _http(port, "POST", "/v1/nope", {}, token=tok)
        chk("E2 未知路径 ⇒ 404", st == 404, "HTTP %s" % st)

        # ── F 实弹：真出网（可选）──
        if live:
            st, hdr, txt = _http(port, "POST", "/v1/chat/completions",
                                 {"model": "agnes-2.5-flash",
                                  "messages": [{"role": "system", "content": "只回四个字"},
                                               {"role": "user", "content": "请回：土豆加油"}],
                                  "max_tokens": 64, "stream": False}, token=tok)
            ok = st == 200
            reply = ""
            if ok:
                j = json.loads(txt)
                reply = str(((j.get("choices") or [{}])[0].get("message") or {})
                            .get("content") or "")
            chk("F0 实弹非流式出网成功", ok, "HTTP %s" % st)
            chk("F0' 真拿到了回答内容", bool(reply.strip()), repr(reply[:40]))
            f0_hdr = {k.lower(): v for k, v in hdr.items()}
            chk("F0'' 可观测性头在册且全 ASCII",
                f0_hdr.get("x-gbt-brand") == BRAND_ASCII
                and bool(f0_hdr.get("x-gbt-provider"))
                and bool(f0_hdr.get("x-gbt-key-fp")),
                "brand=%s provider=%s fp=%s" % (f0_hdr.get("x-gbt-brand"),
                                                f0_hdr.get("x-gbt-provider"),
                                                f0_hdr.get("x-gbt-key-fp")))
            leak0 = _scan_plaintext([txt] + list(hdr.values()), secrets)
            chk("F0''' 实弹响应（体+头）里也无明文密钥", not leak0,
                "命中 %d 处" % len(leak0))

            f1_max_tokens = 1024          # 别用 64：推理模型会被 reasoning 吃光（实测）
            st, hdr, txt = _http(port, "POST", "/v1/chat/completions",
                                 {"model": "deepseek-flash",
                                  "messages": [{"role": "user",
                                                "content": "数到三，只输出数字"}],
                                  "max_tokens": f1_max_tokens, "stream": True}, token=tok)
            chk("F1 实弹流式成功", st == 200, "HTTP %s" % st)
            chunks = [ln[6:] for ln in txt.splitlines()
                      if ln.startswith("data: ") and ln[6:].strip() != "[DONE]"]
            got, reasoning, finish = "", "", None
            for c in chunks:
                try:
                    d = json.loads(c)
                except Exception:                       # noqa: BLE001
                    continue
                ch = (d.get("choices") or [{}])[0]
                dl = ch.get("delta") or {}
                # ⚠️ 血账（2026-09-28 实弹）：最初只累加 `content`，于是
                #    deepseek-flash（**是推理模型**）的流被判成「拼不出内容」——
                #    其实 66 个片段全都是 `reasoning_content`。判据本身写歪了，
                #    不是透传坏了。必须**分开累计**，才看得见真正的现象。
                got += dl.get("content") or ""
                reasoning += dl.get("reasoning_content") or ""
                if ch.get("finish_reason"):
                    finish = ch["finish_reason"]
            chk("F1' SSE 片段可解析（真解出 JSON）", bool(chunks),
                "chunks=%d" % len(chunks))
            chk("F1'' 拼出了内容（content 或 reasoning 至少一样非空）",
                bool(got.strip()) or bool(reasoning.strip()),
                "content=%r reasoning=%d字 finish=%s"
                % (got[:24], len(reasoning), finish))
            f1_hdr = {k.lower(): v for k, v in hdr.items()}
            chk("F1''' 流式也带上游标识头（真判据，不是恒真）",
                f1_hdr.get("x-gbt-brand") == BRAND_ASCII
                and bool(f1_hdr.get("x-gbt-provider")),
                "brand=%s provider=%s" % (f1_hdr.get("x-gbt-brand"),
                                          f1_hdr.get("x-gbt-provider")))
            chk("F1'''' 流式响应体里无明文密钥",
                not _scan_plaintext([txt], secrets), "命中 0 期望")
            if reasoning.strip() and not got.strip():
                rows.append("  [NOTE] 该通道把预算全用在 reasoning 上、content 为空"
                            "（预算 max_tokens=%d 太小）—— 这是**上游行为**，"
                            "本桥如实透传，不伪造答案。" % f1_max_tokens)
        else:
            rows.append("  [SKIP] F0/F1 实弹出网（--offline）")

        # ── G 运行态副作用可见（换道记账真在写）──
        pl = KG.plan()
        chk("G0 plan 每次现算且带 brand", pl.get("brand") == KG.BRAND_TAG, pl.get("chosen"))
        rt = KG._rload()
        chk("G1 运行态落点已记账", bool(rt.get(KG._GLOBAL_ACTIVE)), rt.get(KG._GLOBAL_ACTIVE))
    finally:
        srv.shutdown()
        srv.server_close()
        if minted.get("key_id"):
            KG.revoke(minted["key_id"])
            mk2 = KG.keys()
            revoked = [k for k in mk2["keys"] if k["key_id"] == minted["key_id"]]
            results.append(bool(revoked and revoked[0]["revoked"]))
            rows.append("  [%s] H0 自检密钥已吊销（不留后门）"
                        % ("PASS" if (revoked and revoked[0]["revoked"]) else "FAIL"))

    passed, total = sum(results), len(results)
    if verbose:
        print(f"🥔{BRAND} · GenOffice 桥接自检 {passed}/{total}")
        print("\n".join(rows))
        print("🥔%s · %s/%s" % (BRAND, "ALL PASS" if passed == total else "有 FAIL", total))
    return 0 if passed == total else 1


def _refuses_non_loopback() -> bool:
    try:
        make_server("0.0.0.0", 0)
        return False
    except SystemExit:
        return True
    except Exception:                                   # noqa: BLE001
        return False


# ══════════════════════════════════════════════════════════════════════
# 六、能力位入口（触手）· 2026-09-28 补
# ══════════════════════════════════════════════════════════════════════
#
# **为什么补这一格**：本模块原先只有 `serve()` / `selftest()` / `main()` 三个入口，
# 没有统一的 `run(op)` —— 于是它**当不成能力位**：`run_task("genoffice_bridge", ...)`
# 在 `_run_task_core` 第 1772 行就被 `if kind not in BENIGN_CAPS` 挡下，
# 回一句 "unknown capability（没有这个能力位名）"。实测三连全部如此，
# `genoffice_bridge` 甚至被邻近匹配建议成 `genoffice`。
# 这与主人令「新增能力全部都要与触手双向绑定，确保触手随时使用不会有故障和断连」相悖。
#
# **两条硬约束（照抄 `tools/genoffice_cap.py` 的口径）**：
#   ① **能力位入口绝不阻塞** —— CODING_DISCIPLINE 第 35 条「穿透传输不阻塞」。
#      `serve()` 是 `serve_forever()` 常驻，会把调用方吊死 ⇒ **不进能力位**，
#      如实回 `cli_only` 并给出 CLI 走法（是"指路"，不是"拒绝"）。
#   ② 写类/出网类 op 的作用域声明挂在 **cap 边界**（`security/policy.py::evaluate`
#      的 `kind == "genoffice_bridge"` 分支），与本域既有口径一致
#      （见 `llm/unified.py::status()` 的 `gate` 字段）。本入口**不自挂第二道闸**。
# 只有 serve 是"不进能力位"的 —— 其余 op 都走能力位（读类直连 / 写类过门）。
_RUN_CLI_ONLY = ("serve",)


def run(op: str = "status", **params) -> dict:
    """能力位统一入口。op ∈ status / probe / selftest / serve。

    · `status`   —— 只读：网关接线状态（不调模型、不出网、不落盘）
    · `probe`    —— 只读：探本桥监听端口是否存活（回环 GET /health）
    · `selftest` —— 会铸一把测试钥 + 起临时端口 + 真出网 ⇒ 过门（cap 边界声明作用域）
    · `serve`    —— **不在能力位上**（常驻阻塞），走 CLI
    """
    op = str(op or "status").strip().lower()

    if op == "status":
        # 与 `main()` 的默认分支**同一份实现**（`main` 调本函数）——
        # 避免"CLI 报的数"与"触手看到的数"两处真相各自漂移。
        return _status_payload()

    if op == "probe":
        port = int(params.get("port", DEFAULT_PORT) or DEFAULT_PORT)
        host = str(params.get("host", "127.0.0.1") or "127.0.0.1")
        code = _status_or_none("http://%s:%d/health" % (host, port))
        return {"ok": code == 200, "cap": CAP, "brand": BRAND_TAG, "op": "probe",
                "host": host, "port": port, "http": code,
                "listening": code is not None,
                "note": ("本桥在监听" if code == 200 else
                         "本桥未在监听（http=None 表示拒连/超时；回环请求已绕开环境代理）")}

    if op == "selftest":
        rc = selftest(live=bool(params.get("live", True)),
                      verbose=bool(params.get("verbose", False)))
        return {"ok": rc == 0, "cap": CAP, "brand": BRAND_TAG, "op": "selftest",
                "exit": rc,
                "note": "exit 0 = 全过；非 0 = 有 FAIL（逐条明细用 CLI selftest 看）"}

    if op in _RUN_CLI_ONLY:
        return {"ok": False, "cli_only": True, "cap": CAP, "brand": BRAND_TAG, "op": op,
                "why": "serve 是 serve_forever 常驻 —— 能力位入口不许挂住调用方"
                       "（CODING_DISCIPLINE 第 35 条：穿透传输不阻塞）",
                "how": "python -m gbt_allinone.llm.genoffice_bridge serve"}

    return {"ok": False, "fail_closed": True, "cap": CAP, "brand": BRAND_TAG,
            "error": "未知 op %r" % op,
            "available": ["status", "probe", "selftest", "serve"]}


def _status_payload() -> dict:
    """网关接线的**唯一**取值处（`main()` 与 `run("status")` 共用）。"""
    e = KG.energy()
    return {"ok": True, "brand": BRAND, "brand_tag": BRAND_TAG, "cap": CAP,
            "version": VERSION, "default_port": DEFAULT_PORT,
            "summary": e.get("summary"), "alive": e.get("alive"),
            "total": e.get("total"),
            "slots": [{k: s[k] for k in ("provider", "status", "model",
                                         "masked", "tier")}
                      for s in e.get("slots", [])],
            "note": "起服务：python -m gbt_allinone.llm.genoffice_bridge serve"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="genoffice_bridge",
        description="🥔%s · GenOffice AI 线 → 统一密钥网关（本地 OpenAI 兼容桥）" % BRAND)
    sub = ap.add_subparsers(dest="cmd")
    p1 = sub.add_parser("serve", help="起服务")
    p1.add_argument("--host", default="127.0.0.1")
    p1.add_argument("--port", type=int, default=DEFAULT_PORT)
    p1.add_argument("--allow-non-loopback", action="store_true",
                    help="⛔ 允许绑非回环（默认拒绝）")
    p2 = sub.add_parser("selftest", help="自检（临时端口 + 真 HTTP）")
    p2.add_argument("--offline", action="store_true", help="跳过真实出网那两条")
    sub.add_parser("status", help="打印网关接线状态")
    # 2026-09-28 补：把「能力位入口」也开一个 CLI 口 —— 主人要能手跑**触手同一条入口**
    # （OP-35 精神：接线要能被单独验，不能只靠"触手用时才知道断没断"）。
    p3 = sub.add_parser("run", help="走能力位入口 run(op)（与触手同一条路）")
    p3.add_argument("--op", default="status",
                    help="status / probe / selftest（serve 不在能力位上）")
    p3.add_argument("--live", action="store_true", help="selftest 时真出网")

    args = ap.parse_args(argv)
    cmd = args.cmd or "status"
    if cmd == "serve":
        serve(args.host, args.port, args.allow_non_loopback)
        return 0
    if cmd == "selftest":
        return selftest(live=not args.offline)
    if cmd == "run":
        r = run(args.op, live=bool(getattr(args, "live", False)), verbose=True)
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r.get("ok") else 1
    print(json.dumps(_status_payload(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
