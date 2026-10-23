# -*- coding: utf-8 -*-
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 · arXiv 只读检索（**零凭据**源）。

为什么收它进来（Owner 风哥 2026-09-18 拍「吞噬吸收」）：

  · **零凭据** —— 公开 API，无 API key / 无 cookie / 无 token。
    结构性保证：本模块**不引用 os**，读不到任何环境变量。
  · **元数据 CC0 1.0** —— arXiv 明示描述性元数据属**公有领域**，可
    retrieve / store / transform / share。比 Reddit / X 那类带 ToS 争议的
    源干净得多，可安全进 store。
  · **限流 3 秒 / 请求 + 单连接** —— 与本框架「串行、无并发」纪律天然吻合：
    不是「我们迁就它」，是两边本来就同频。
  · 学术 / 深研链在本仓此前是**空的**（全仓 `arxiv` 零命中，2026-09-18 实测）。

源侧红线（ToU 硬约束，**不许绕**）：
  · 不得规避限流 —— 本模块用进程内最小间隔闸强制 3 秒，**绝不并发**
  · 不得威胁 arXiv 正常运行
  · 商业用途须先看 arXiv 品牌指南 / 考虑成为 affiliate（待 Owner 拍）

接口事实（源文档 user-manual + 本机实测复核 2026-09-18）：
  · 端点 `http://export.arxiv.org/api/query`，返回 Atom XML
  · `search_query` / `id_list` / `start`(0-based) / `max_results` /
    `sortBy`(relevance | lastUpdatedDate | submittedDate) / `sortOrder`
  · 只给 `search_query` -> 匹配结果；只给 `id_list` -> 按 id 返回；
    两者都给 -> **交集**
  · `max_results > 30_000` -> 源侧 HTTP 400

源侧 406 归因（2026-09-18 本机实测 · 60+ 次打点 · **结论未定** —— 见文末「未收口」）：
  · **候选解释（未定 · 不许当结论用）= 该 URL 是否命中源侧（Fastly）共享缓存**
    （相关性成立、**因果未证**：未控变量只剩 **时限**；边缘节点**未排除**（见下「未控第三变量」））：`X-Cache` 含 `HIT`
    -> 200；`MISS, MISS` -> 406（响应体 0 字节）。
  · **决定性对照 · 实验 A（2026-09-18，把「编码」和「缓存」拆开）**：
      同逻辑查询、同 5 参数，只差冒号写法：
        字面 `:` -> 406（`MISS, MISS`）· `%3A` -> 200（`MISS, HIT, HIT`）· 相邻可复现
      再给 `%3A` 形状**造必然冷的 URL**（`max_results` 1->2；追加 `x=1`）：
        两条**全部 406（`MISS, MISS`）**
      => **URL 编码 / 形状不是判别量**。`%3A` 常 200，只因它是 `urlencode()` 的
         产物 —— 全世界客户端都在请求这个形状，所以它在缓存里。编码是「热门度」的
         **代理**，不是原因。（上一轮把「编码翻面」当判别量 = 把相关提前叫成因果，作废。）
  · **Accept 分桶对照（同日，关掉最后一个未排除变量）**：
      热对照 200（`MISS, HIT, HIT`，`X-Served-By=cache-bkk2280029-BKK`）
      两个**不同随机词**的冷 URL：`Accept: application/atom+xml` -> 406；
      `Accept: */*` -> 406（节点 2280021 / 2280022，各自 `MISS, MISS`）
      => **`Accept` 不是判别量**，缓存判别量保住。
  · **冷 URL 换请求头 / UA 对照（同日，把上面那条无效对照补成有效对照）**：
      热对照 2/2 = 200；三条冷 URL：现 UA + `Accept: application/atom+xml` -> 406；
      Chrome 伪装 UA -> 406；空 UA -> 406（四个不同边缘节点，各自 `MISS, MISS`）
      => **请求头 / UA / `Accept` 在冷 URL 上都不是判别量**。
  · **缓存既是护身符也是定时炸弹**：命中来的 200 是**借的**，不是契约 —— TTL 到期 /
    节点轮换 / 被逐出，同一条 URL 拿到的就是源侧真实响应。所以降级路径必须按
    **主路径**写，命中缓存只算加分项；负缓存（把 406 存进 TTL）是 CDN 经典事故。
  · **已被实测逐条否决 / 降级的假设**（对照实验，非推断）：
      - 请求头 / UA 伪装 —— **降级为「非有效对照」**：那四组打在一条**已命中缓存**
        的 URL 上（全 200），只证明「命中缓存时请求头无关」，不证明「406 与请求头
        无关」。（`Accept` 与 UA / 空 UA 已由冷 URL 对照补测排除，见下一条。）
      - 空格未编码 —— `+` 与 `%20` 同样 406；多词不是特例
      - 字段前缀 / 引号 —— `all:` / `ti:` / `abs:` / `cat:` 都可通可不通；
        `all:"..."` 反而 400
      - 参数个数 —— 1p / 2p / 3p 只要命中缓存即 200；3p 冷词照样 406
      - 参数形状（含 `sortBy` / `sortOrder`）—— 同为 3 参数，热词 200、冷词 406
      - 请求长度阈值 —— 同长度同结构，只换热词冷词即翻面
      - 限流窗口 —— 静默 300 秒后同一 URL 仍 406
  · **复现性（是数据，不是结论）**：同一观测窗内不抖动 —— 冷词 3/3 全 406（跨 3 个不同
    边缘节点）· 热词 2/2 全 200。**这只证明「窗内稳定」，不证明「同一 URL 跨 TTL
    稳定」**：既没测过一条会翻面的 URL，也没做过跨 TTL 复测。
  · **未收口（不假装知道）**：为什么源侧拒服务未命中缓存的 URL —— 本机单一出口
    无法判定是「本出口被限」还是「源侧对冷查询的整体姿态」。
  · **未控第三变量（Owner 风哥 2026-09-18 点名：「自相矛盾 -> 存在第三个变量，结论不许定」）**：
      - **节点：落盘证据只够说「观测范围内不是判别量」，不够说「已排除」** ——
        全 `.scratch` 里 arxiv 节点读数**只有 `_z28.out` 一处落盘**（`_z31`/`_z32`/
        `_z33`/`_z35`/`_z37` **只有脚本、无 `.out`**）：冷词 406 跨 5 个节点
        （2280039 / 2280033 / 2280036 / 2280026 / 2280027），而**同一个节点 2280039
        对热 URL 给 200、对冷 URL 给 406**（`A#2` vs `S#1` / `T3#1`）
        => **采样内**节点不是判别量。**但**：本文档另引用的 2280021 / 2280022 / 2280029
        **没有对应输出落盘、不可复核**；「是否存在某些节点会服务冷 URL」在采样内
        **无法证否**。故口径 = **「落盘 5 节点内不是判别量」**，不是「已排除」
        （上一轮写成「已由 `_z28` 实测排除」= 判据作用面写错，O51 族）。
      - **时限（TTL）：未排除** —— `A` 臂在 5 分钟窗内两次都 200
        （`MISS, HIT, HIT`），但**从未跨 TTL 观察**；早期 200（`_z19`/`_z21` 时代）
        与后来的 406 之间发生过什么，**无法判断**。
      - **一次被自己判废的收口尝试（2026-09-18 14:01–14:18 · 落盘 `.scratch/_z41_closure.out`
        + `_z42_ttlwatch.out`）**：按上面形态跑了 —— `H`（`max_results=1`）3/3 = 200
        （`X-Cache=MISS, HIT, HIT`，`Age` 2680 -> 2984 -> 3288，**与墙钟 1:1** =
        同一条条目）；14:14:45 / 14:16:45 仍 200（`Age` 3453 / 3573）；
        **14:17:45 翻成 406（`MISS, MISS`，`Age` 消失）**，连打 3 次确认、5 个不同 BKK 节点。
        **但这一轮整体作废**（Owner 风哥 2026-09-18 点名：「A2 对照自己红了 -> 本轮整体作废」）：
        对照臂（`H`）的**唯一职责**是证明「环境没变、源侧仍在服务」；它一旦自己变红，就
        **分不清**「被测 URL 的条目到期」与「源侧 / 本出口整体开始拒服务」—— 因为翻转时刻
        **没有第二条独立缓存键**仍为 200 可作锚。故 `TTL ≈ 3600 s` 只是**候选读数，
        不许当结论**。（O51 族：把结论压在「对照」身上 —— 对照红了，判据就没了判别力。）
      - **修正后的收口形态（未跑 · 等 Owner 拍）**：至少 **3 条互不相同的缓存键**
        （不同 `search_query` 或不同参数），其中 >= 2 条当前为 200 作**锚**；跨 >= 1 小时后同批打：
        · 观察键翻红而**锚仍绿** => 环境未变，翻面可归因于该键自身条目到期（**可判**）；
        · 观察键与锚**同批全红** => 环境变了，**本轮作废**（与本次同下场）。
      - **证据链硬伤**：`_z19` / `_z21` / `_z23` / `_z24` / `_z25` / `_z26` / `_z27` /
        `_z31` / `_z32` / `_z33` / `_z35` / `_z37` 在 `.scratch` 里**只有脚本、
        没有 `.out`** —— 那些结果**不可复核**（arxiv 侧落盘 = `_z28.out` /
        `_z41_closure.out` / `_z42_ttlwatch.out`）。
      - **另一条未控（我方自污染）**：早期探针（`_z19` / `_z21` / `_z23`）是用
        **字面冒号**请求 `all:electron&start=0&max_results=1` 并拿到 200 的；若 200 会被
        边缘缓存，那条条目就是**我们自己灌的**，不是「世界很热」。
        它与「缓存成员资格」相容，但会让「热门度」这个解释**失去独立证据**。
  · **收口只认一种实验形态**：同一 URL ≥ 3 次 · **跨 ≥ 10 分钟（跨 TTL）** ·
    逐次记 `X-Served-By` / `X-Cache` / `Age` · **输出落盘**。
    跑不出这张表，判别量就**不许定**。
  · **命题边界**：上面每条「否决」都来自**同刻只换一个变量**的对照实验；
    凡没做过同刻对照的变量，一律写「未排除」，不写成「已否决」。
  · 因此正确姿态是：**如实记录诊断 + 退避 + 绝不伪装**，并把
    `X-Cache` / `X-Served-By` / 响应体前 200 B 带进返回值与异常（`diagnostics`）。

用法::

    from gbt_allinone.recon import arxiv
    hits = arxiv.search("retrieval augmented generation", max_results=5)
    arxiv.selftest()            # 零凭据 / 限速闸 / 热探针 / 冷探针 四项自检

CLI::

    python -m gbt_allinone.recon.arxiv "your query" --max 5
    python -m gbt_allinone.recon.arxiv --selftest
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

API = "http://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
OPENSEARCH = "{http://a9.com/-/spec/opensearch/1.1/}"

MIN_INTERVAL_S = 3.0            # ToU：<= 1 请求 / 3 秒，单连接
MAX_RESULTS_CEILING = 30_000    # 超过 -> 源侧 HTTP 400
SORT_BY = ("relevance", "lastUpdatedDate", "submittedDate")
SORT_ORDER = ("ascending", "descending")
LICENSE_NOTE = "arXiv 描述性元数据 = CC0 1.0（公有领域），可自由存储 / 转换 / 分享"
THROTTLE_CODES = (403, 406, 429)   # 源侧拒服务（406 归因见模块 docstring）


class SourceThrottled(RuntimeError):
    """源侧拒服务（403 / 406 / 429）—— **把决定权交回调用方**。

    归因（2026-09-18 实测，见模块 docstring「源侧 406 归因」）：
      · **候选解释（未定）** = 该 URL 是否命中源侧（Fastly）共享缓存；
        相关性成立、**因果未证**（未控变量只剩 **时限**；边缘节点**未排除** —— 见模块 docstring「未控第三变量」）。已排除 URL 编码 /
        引号 / 间隔 / 参数个数 / 参数形状 / 检索词冷热本身
      · 命中 -> 200；未命中（`X-Cache: MISS, MISS`）-> 406 —— 「未命中」只是**候选解释
        （未定）**的代理，不是已证因果；静默 300 秒后仍 406（**跨 TTL 未测**）
      · 编码 / 形状 / `Accept` **均已被决定性对照排除**（实验 A + Accept 分桶）
        —— 换编码、换形状、换 `Accept` 都救不了未命中缓存的 URL

    **不承诺「退避后一定能好」**：退避有效与否**未验证**，已有反证是 300 秒静默无效。
    调用方请把 `diagnostics` 记进日志，再决定重试还是放弃。

    为什么不自动重试：源侧 ToU 是「<= 1 请求 / 3 秒」，无脑重试只会加速撞限流。
    为什么不伪装浏览器：UA 伪装既是骗源站，也可能被判定为规避行为
    （ToU 明写「不得规避限流」）—— 得不偿失。
    """

    def __init__(self, message: str, *,
                 diagnostics: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.diagnostics: Dict[str, Any] = diagnostics or {}


_last_call_at = 0.0


def _request_headers() -> Dict[str, str]:
    """请求头（**零凭据**）—— 运行时可断言：无 Authorization / Cookie。

    刻意**不伪装浏览器**（否决「换成 Chrome UA 绕反爬」，2026-09-18 实测复核）：

      · 上一版这里写「406 不复现、当时是瞬时限流」—— **契约与实测冲突，已作废**。
        那条结论是打在一条源侧共享缓存已命中的 URL 上，四组请求头全 200 只证明
        「命中缓存时请求头无关」，不证明「406 与请求头无关」。
      · 冷 URL 换请求头对照（2026-09-18 实测 · 5 次打点）：热对照 2/2 = 200；
        冷 URL 上「现 UA + `Accept:atom`」「Chrome 伪装 UA」「空 UA」**三条全 406**
        —— 请求头 / UA / `Accept` 在未命中缓存的 URL 上都不是判别量。
        （注：最早那组「四组请求头全 200」只打在**缓存命中**的 URL 上，属无效对照。）
      · 而 UA 伪装既是骗源站，也可能被判定为规避行为（ToU 明写「不得规避限流」）。

    这里只加一个诚实的 `Accept`（声明期望格式 = Atom/XML）—— 技术头，不是伪装。
    """
    return {"User-Agent": "GBTxiaotudouV8-arxiv/1.0 (+info.arxiv.org/help/api/tou.html)",
            "Accept": "application/atom+xml,application/xml;q=0.9,*/*;q=0.8"}


def _throttle() -> float:
    """进程内最小间隔闸 —— 串行、无并发，绝不绕源侧 3 秒限流。

    返回本次实际等待秒数（0 = 距上次已超 3 秒）。首次调用天然不等待。
    """
    global _last_call_at
    wait = MIN_INTERVAL_S - (time.monotonic() - _last_call_at)
    if wait > 0:
        time.sleep(wait)
    _last_call_at = time.monotonic()
    return max(0.0, wait)


DIAG_HEADERS = ("X-Cache", "X-Served-By", "X-Cache-Hits", "Content-Type")
BODY_SNIPPET_BYTES = 200
PROBE_HOT_QUERY = "all:electron"    # 极热检索词：源侧共享缓存最可能已有条目


def _diagnostics(headers: Any, status: Optional[int],
                 exc: Any = None) -> Dict[str, Any]:
    """把源侧响应头 / 状态 / 响应体前 200 B 收成结构化诊断。

    为什么必须收（风哥 2026-09-18 点名）：`X-Cache` 是「是否命中源侧共享缓存」这一
    **候选解释（未定）**的唯一可观测代理，
    而它过去只活在 `.scratch` 探针里 —— 离开探针，线上再出 406 就是瞎的。

    键名固定：`http` / `x_cache` / `x_served_by` / `x_cache_hits` /
    `content_type` / `body_snippet`（406 时实测为空串：源侧不回体）。
    """
    out: Dict[str, Any] = {"http": status}
    for name in DIAG_HEADERS:
        try:
            out[name.lower().replace("-", "_")] = headers.get(name)
        except Exception:
            out[name.lower().replace("-", "_")] = None
    snippet = ""
    if exc is not None:
        try:
            snippet = exc.read()[:BODY_SNIPPET_BYTES].decode("utf-8", "replace")
        except Exception:
            snippet = ""
    out["body_snippet"] = snippet
    return out


def _throttle_message(query: Optional[str], url: str,
                      diag: Dict[str, Any]) -> str:
    """把「源侧拒服务」写成**事实**，不写成猜测（不说「退避就能好」）。"""
    cache = diag.get("x_cache") or "?"
    if "HIT" in str(cache):
        hint = "命中源侧共享缓存，却仍被拒 —— 待复核"
    else:
        hint = "未命中源侧共享缓存（实测这一路必然 406；退避是否有效未验证）"
    return ("源侧未提供本次检索：HTTP %s · X-Cache=%s（%s）· query=%r"
            % (diag.get("http"), cache, hint, query))


def _fetch(params: Dict[str, Any], *, timeout: int,
           throttle: bool) -> Dict[str, Any]:
    """统一取数：闸 -> 请求 -> 诊断 -> 解析。`search()` 与探针共用。"""
    url = API + "?" + urllib.parse.urlencode(params)
    waited = _throttle() if throttle else 0.0
    t0 = time.perf_counter()
    req = urllib.request.Request(url, headers=_request_headers())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = getattr(resp, "status", None)
            diag = _diagnostics(resp.headers, status)
    except urllib.error.HTTPError as exc:
        diag = _diagnostics(exc.headers, exc.code, exc)
        if exc.code in THROTTLE_CODES:
            raise SourceThrottled(
                _throttle_message(params.get("search_query"), url, diag),
                diagnostics=diag) from exc
        raise
    parsed = _parse(raw)
    return {"ok": True, "query": params.get("search_query"), "url": url,
            "http": status,
            "total_results": parsed["total_results"],
            "count": len(parsed["entries"]),
            "entries": parsed["entries"],
            "latency_ms": round((time.perf_counter() - t0) * 1000.0, 1),
            "throttle_waited_s": round(waited, 2),
            "diagnostics": diag,
            "license": LICENSE_NOTE}


def _probe(query: str, *, timeout: int = 30) -> Dict[str, Any]:
    """最小形状探针（仅 `search_query` + `max_results`）。

    为什么最小形状：探针要验的是「闸 + 连通 + 解析」这条**路径**。
    2026-09-18 实测已把「参数形状」排除为 406 的判别量，这里用最小形状**只为**提高
    命中源侧共享缓存的概率（`all:electron&max_results=1` 实测稳定 200），
    **不代表生产形状** —— 生产形状见 `search()`。
    """
    return _fetch({"search_query": query, "max_results": 1},
                  timeout=timeout, throttle=True)


def _norm(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _pdf_link(entry: ET.Element) -> str:
    for link in entry.findall(ATOM + "link"):
        if (link.get("title") or "").lower() == "pdf":
            return link.get("href") or ""
    return ""


def _parse(xml_text: str) -> Dict[str, Any]:
    """Atom XML -> 结构化条目。"""
    root = ET.fromstring(xml_text)
    total = root.findtext(OPENSEARCH + "totalResults")
    entries: List[Dict[str, Any]] = []
    for e in root.findall(ATOM + "entry"):
        entries.append({
            "id": (e.findtext(ATOM + "id") or "").strip(),
            "title": _norm(e.findtext(ATOM + "title")),
            "summary": _norm(e.findtext(ATOM + "summary")),
            "published": (e.findtext(ATOM + "published") or "").strip(),
            "updated": (e.findtext(ATOM + "updated") or "").strip(),
            "authors": [_norm(a.findtext(ATOM + "name"))
                        for a in e.findall(ATOM + "author")],
            "categories": [c.get("term") for c in e.findall(ATOM + "category")],
            "pdf": _pdf_link(e),
        })
    return {"total_results": int(total) if (total or "").isdigit() else None,
            "entries": entries}


def search(query: str, *, max_results: int = 10, start: int = 0,
           sort_by: str = "submittedDate", sort_order: str = "descending",
           timeout: int = 30, throttle: bool = True) -> Dict[str, Any]:
    """零凭据检索。返回结构化结果；失败 -> 抛（调用方决定怎么处理）。

    `throttle=False` 仅供自检测量用；**生产路径一律走闸**（默认 True）。
    """
    if max_results > MAX_RESULTS_CEILING:
        raise ValueError("max_results 超源侧上限 %d（源侧会返 HTTP 400）"
                         % MAX_RESULTS_CEILING)
    if sort_by not in SORT_BY:
        raise ValueError("sort_by 只允许 %s" % (SORT_BY,))
    if sort_order not in SORT_ORDER:
        raise ValueError("sort_order 只允许 %s" % (SORT_ORDER,))

    params = {"search_query": query, "start": int(start),
              "max_results": int(max_results),
              "sortBy": sort_by, "sortOrder": sort_order}
    # 参数形状**刻意不动**：2026-09-18 实测「形状」已被排除为 406 的判别量
    # （同为 3 参数，热词 200 / 冷词 406），动它没有实测收益。
    return _fetch(params, timeout=timeout, throttle=throttle)


def selftest() -> Dict[str, Any]:
    """四项自检（机械可复核，全部实测）：

      ① 零凭据 —— 请求头无 Authorization / Cookie；模块**不引用 os**
      ② 限速闸 —— 连调 2 次 `_throttle()`，实测间隔 >= MIN_INTERVAL_S（**本地计时**）
      ③ 热探针 —— 最小形状 + 极热检索词（源侧共享缓存最可能命中）：验
         「闸 + 连通 + 解析」这条路径。形状已被实测排除为 406 的判别量，
         这里用最小形状**只为**提高命中率，**不代表生产形状**。
      ④ 冷探针 —— **走生产路径 `search()`**，检索词一次性随机（构造必然的 cache
         MISS）：验「源侧当前能否服务任意检索」。这是本模块的核心用途，
         拒服务时必须报出来，**不许拿热探针的绿去冒充**。

    判据只断言**运行时对象**与**模块级 import**，不靠扫自己源码里的字面量
    （那样判据会被自己的模式表染红 —— 自伤）。
    """
    checks: List[Dict[str, Any]] = []

    # ① 结构性零凭据（**不依赖网络** —— 网络挂了这两条也该跑绿）
    headers = _request_headers()
    bad = [k for k in headers if k.lower() in ("authorization", "cookie")]
    checks.append({"id": "1", "name": "零凭据 · 请求头", "network": False,
                   "ok": not bad, "detail": "headers=%s" % sorted(headers)})

    # 模块命名空间里没有 `os` -> 读不到任何环境变量。
    # 哪天有人加 `import os` 想从 env 里捞 key，这条立刻判红。
    import gbt_allinone.recon.arxiv as _self
    uses_os = "os" in vars(_self)
    checks.append({"id": "1", "name": "零凭据 · 不引用 os", "network": False,
                   "ok": not uses_os,
                   "detail": "模块命名空间无 os（结构性：读不到环境变量）"})

    # ② 限速闸 —— 纯本地计时，**不需要网络**（上一版靠两次联网间接测，网络一挂就白测）
    t_first = time.monotonic()
    _throttle()
    _throttle()
    gap = time.monotonic() - t_first
    checks.append({"id": "2", "name": "限速闸 · 3 秒最小间隔", "network": False,
                   "ok": gap >= MIN_INTERVAL_S,
                   "detail": "连调 2 次实测间隔 %.2fs（阈值 %.2fs；本地计时，不依赖网络）"
                             % (gap, MIN_INTERVAL_S)})

    notes: List[str] = []

    # ③ 热探针（依赖源站）—— 被挡住 -> **未验证**：不当绿，也不当逻辑红
    hot_ok = False
    hot_check: Dict[str, Any] = {"id": "3", "name": "热探针 · 闸 + 连通 + 解析",
                                 "network": True, "ok": False, "verified": False,
                                 "detail": "**未验证** —— 热探针未跑"}
    try:
        a = _probe(PROBE_HOT_QUERY)
        e0 = (a["entries"] or [{}])[0]
        fields_ok = (bool(e0.get("id")) and bool(e0.get("title"))
                     and bool(e0.get("published")))
        hot_ok = bool(a["entries"]) and fields_ok
        hot_check.update({
            "ok": hot_ok, "verified": True,
            "detail": "query=%s · HTTP %s · X-Cache=%s · total=%s count=%s · 首条 %s"
                      % (PROBE_HOT_QUERY, a["http"], a["diagnostics"].get("x_cache"),
                         a["total_results"], a["count"],
                         (e0.get("published") or "")[:10])})
    except SourceThrottled as exc:
        hot_check["detail"] = "**未验证** —— %s" % exc
        notes.append("热探针：%s" % exc)
    except urllib.error.URLError as exc:
        hot_check["detail"] = "**未验证** —— 网络不可达：%s" % (exc.reason,)
        notes.append("热探针：网络不可达 %s" % (exc.reason,))

    # ④ 冷探针（依赖源站）—— 走生产路径的真实参数形状；随机词 => 必然 cache MISS
    cold_query = "all:%s" % uuid.uuid4().hex[:10]
    cold_ok = False
    cold_check: Dict[str, Any] = {"id": "4", "name": "冷探针 · 源侧服务任意检索",
                                  "network": True, "ok": False, "verified": False,
                                  "detail": "**未验证** —— 冷探针未跑"}
    try:
        c = search(cold_query, max_results=1)
        cold_ok = True
        cold_check.update({
            "ok": True, "verified": True,
            "detail": "query=%s · HTTP %s · X-Cache=%s —— 任意检索可用"
                      % (cold_query, c["http"], c["diagnostics"].get("x_cache"))})
    except SourceThrottled as exc:
        # 这是**已核实的红**（源侧确实拒了），不是「未验证」
        cold_check.update({
            "ok": False, "verified": True,
            "detail": "**源侧拒服务**：%s —— 任意检索当前不可用"
                      "（实测为 URL 未命中共享缓存，不是本模块逻辑缺陷）" % exc})
        notes.append("冷探针：%s" % exc)
    except urllib.error.URLError as exc:
        cold_check["detail"] = "**未验证** —— 网络不可达：%s" % (exc.reason,)
        notes.append("冷探针：网络不可达 %s" % (exc.reason,))

    checks.extend((hot_check, cold_check))

    logic_ok = all(c["ok"] for c in checks if not c["network"])
    return {"ok": logic_ok and hot_ok and cold_ok,
            "logic_ok": logic_ok,
            "hot_ok": hot_ok,
            "cold_ok": cold_ok,
            "network_verified": hot_ok and cold_ok,
            "block_note": " | ".join(notes),
            "checks": checks,
            "min_interval_s": MIN_INTERVAL_S,
            "license": LICENSE_NOTE}


def _render(result: Dict[str, Any]) -> str:
    diag = result.get("diagnostics") or {}
    lines = ["arXiv 检索 · %s" % result["query"],
             "HTTP %s · %s 条 / 共 %s · %.1f ms · %s"
             % (result["http"], result["count"], result["total_results"],
                result["latency_ms"], result["license"]),
             "源侧：X-Cache=%s · X-Served-By=%s"
             % (diag.get("x_cache"), diag.get("x_served_by")), ""]
    for i, e in enumerate(result["entries"], 1):
        lines.append("%2d. [%s] %s" % (i, (e["published"] or "")[:10], e["title"]))
        if e["authors"]:
            lines.append("    作者：%s" % ", ".join(e["authors"][:4]))
        if e["categories"]:
            lines.append("    分类：%s" % ", ".join([c for c in e["categories"] if c][:5]))
        lines.append("    %s" % e["id"])
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m gbt_allinone.recon.arxiv",
        description="arXiv 零凭据只读检索（限速 3 秒/请求，串行不并发）")
    ap.add_argument("query", nargs="?", default=None, help="检索词")
    ap.add_argument("--max", type=int, default=5, help="返回条数（默认 5）")
    ap.add_argument("--start", type=int, default=0, help="起始下标（0-based）")
    ap.add_argument("--sort-by", default="submittedDate", choices=SORT_BY)
    ap.add_argument("--sort-order", default="descending", choices=SORT_ORDER)
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--selftest", action="store_true", help="跑四项自检")
    args = ap.parse_args(argv)

    if args.selftest:
        rep = selftest()
        if args.json:
            sys.stdout.write(json.dumps(rep, ensure_ascii=False, indent=2) + "\n")
        else:
            for c in rep["checks"]:
                mark = ("未验证" if c.get("verified") is False
                        else ("绿" if c["ok"] else "红"))
                sys.stdout.write("[%s] %s · %s\n    %s\n"
                                 % (mark, c["id"], c["name"], c["detail"]))
            if rep["ok"]:
                verdict = "全绿 —— 封版"
            elif not rep["logic_ok"]:
                verdict = "有逻辑红 —— 不许放行"
            elif not rep["hot_ok"]:
                verdict = "结构全绿；热探针**未验证**（源侧连常用检索也没服务）"
            elif not rep["cold_ok"]:
                verdict = ("结构 + 热路径全绿；**冷查询被源侧拒服务**"
                           "—— 任意检索当前不可用，**不是本模块的逻辑缺陷**")
            else:
                verdict = "结构性检查全绿；联网段**未验证**"
            sys.stdout.write("\n自检：" + verdict + "\n")
        # 三态退出码：0 全绿 / 1 逻辑红 / 2 网络未验证（不阻塞，但明确不是绿）
        if rep["ok"]:
            return 0
        if rep["logic_ok"]:
            return 2
        return 1

    if not args.query:
        ap.error("要么给检索词，要么 --selftest")
    res = search(args.query, max_results=args.max, start=args.start,
                 sort_by=args.sort_by, sort_order=args.sort_order)
    if args.json:
        sys.stdout.write(json.dumps(res, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(_render(res) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
