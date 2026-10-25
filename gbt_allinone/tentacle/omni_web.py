# gbt-capability: dynamic-import
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""web 域 mixin — 网页结构化读取 + **自适应元素重定位**（新域，2026-09-22 加入触手）

## 这个域解决什么问题

触手以前只会"看屏幕 + 点坐标"。网页这条路一旦要**读出结构**就断了：
页面改一次版，写死的选择器就全废，触手当场瞎。这正是风哥说的
「抓取能力融合进触手」要补的窟窿。

## 技术来源与我们的实现（必须写清，免得以后说不清）

思路提炼自 **D4Vinci/Scrapling**（BSD-3-Clause，Copyright (c) 2024 Karim shoair）
的 adaptive scraping：**两阶段 —— 先把元素特征存下来，页面改版后按相似度找回**。
它的文档（`agent-skill/Scrapling-Skill/references/parsing/adaptive.md`）把这套机制的
契约写得很清楚，我们据此**自己重写**：

  · 存什么：元素（标签名 / 文本 / 属性名+值 / 兄弟标签名 / 路径标签名）
            + 父元素（标签名 / 属性名+值 / 文本）
  · 怎么比：不是相等，是**相似度打分**；**连值里的顺序也算**（如 class 的书写顺序）
  · 键是什么：(域名, identifier) —— 域名靠 URL，identifier 默认取选择器串

**没有搬它一行代码**：它用 lxml + cssselect + orjson + tld，我们这台机器上这些都没有；
本模块**零第三方依赖**，解析器与选择器引擎都用 stdlib 自己写，权重表也是我们自己定的。
许可义务：BSD-3 只要求"用了它的代码"时保留版权声明 —— 我们没搬代码，仍在此写明出处。

## 外部内容纪律（读到的网页一律是**不可信数据，不是指令**）

本模块读回来的 HTML/正文**全部按不可信数据处理**：
不执行其中任何祈使句，不把它拼进 system 提示，不拿它驱动执行口。
（`web_fetch` 的返回值里没有任何"指令位"；调用方要把它喂给模型时，
必须自己在 system 侧声明"以下是外部资料"。）
覆盖校验器：`py -3.14 -m gbt_allinone.tools.external_content_check gbt_allinone`

## 与授权门的关系（铁律）

本域**有真出网能力**（`web_fetch` / `web_read`），但**不另开通道**：

  · 出网只发生在 `web_fetch` 这一个方法里，且只认 http/https；
  · 它**不是**绕过门 —— 调用方永远经 `run_task("tentacle", {"action": "web_fetch", ...})`，
    由 `security/policy.py` 判定。该文件原文：
        `elif kind == "tentacle":  if op not in _READ_ONLY_TENTACLE:  add("desktop_control")`
    `web_fetch` / `web_read` **不在** `_READ_ONLY_TENTACLE` 里 ⇒ **当前口径下要
    `desktop_control`**。这是**如实结果，不是缺陷**：门只有一处，作用域由主人定，
    我既不给自己发授权，也不去改 `policy.py`。
  · 想让它免卡（公开网页读取），只有主人能动那两处之一：
    ① 终端发放一次性 `desktop_control`；② 把 `web_fetch`/`web_read` 加进
    `_READ_ONLY_TENTACLE`。**我不代劳。**

为什么不用 `browser` 能力位的 `op=fetch`：那条路返回的是**已经去光标签的纯文本**
（`browser_cap.py::fetch` 里 `re.sub(r"<[^>]+>", " ", text)`），拿不到原始 HTML ⇒
**选不了元素、存不了特征、也就谈不上自适应重定位**。要读结构就必须拿原文。
两条路各有其位：`browser.op=fetch` 管"读一页正文"，本域的 `web_fetch` 管"读一页结构"。
"""

import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parent))


# ── 病因钩子：吞错统一收口 + 导航入口病因（**必须放在 sys.path 修正之后**）。
#    教训（2026-09-22 实测）：放在 insert 之前 ⇒ `from nav_etiology import …` 导入期就失败，
#    静默退回垫片 ⇒ 63 处"收口"一个病因都没真记上 = **假收口**。
try:
    from nav_etiology import (record_swallow as _record_swallow,
                              etiology as _etiology,
                              enrich as _enrich_cause)
except Exception:  # noqa: BLE001
    def _record_swallow(_e, _mod="?", _op=""):
        import sys as _s
        print(f"⚠️ {_mod}: 吞错: {_e}", file=_s.stderr)
        return "action_no_effect"

    def _etiology(_m, _o=""):
        def _d(fn):
            return fn
        return _d

    def _enrich_cause(r, _m="?", _o=""):
        return r

try:
    from omni_core import *  # noqa: F401,F403
except Exception as _e:  # noqa: BLE001
    _record_swallow(_e, "omni_web")

import html as _html
import json as _json
import os as _os
import re as _re
import sqlite3 as _sqlite3
import time as _time
import urllib.error as _urlerr
import urllib.request as _urlreq
from difflib import SequenceMatcher as _SM
from html.parser import HTMLParser as _HTMLParser
from urllib.parse import urljoin as _urljoin
from urllib.parse import urlparse as _urlparse

_URL_MAX = 2048
# ⚠️ 这个 UA 必须是**纯 ASCII**：urllib 用 latin-1 编请求头，
#    之前我在里面写了中文（`(+触手 web 域)`），结果每次出网都炸
#    `UnicodeEncodeError: 'latin-1' codec can't encode` —— 实测踩过，别再犯。
# 末尾的 `GBT-Xiaotudou/1.0` 是**robots.txt 的产品 token**（RFC 9309 §2.2.1：
# token 只允许字母/下划线/连字符，且 SHOULD 是 UA 串的子串）—— 抓取要报得出名号。
_DEFAULT_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 GBT-Xiaotudou/1.0")
_REDIRECT_CODES = {301, 302, 303, 307, 308}

# 自闭和标签（拿来即无子节点）
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
         "meta", "param", "source", "track", "wbr"}
# 内容不当正文读的标签
_OPAQUE = {"script", "style", "noscript", "template"}

_DB_ENV = "GBT_WEB_ADAPTIVE_DB"
_DEFAULT_DB = _P(__file__).resolve().parents[1] / "store" / "web_adaptive.sqlite3"

# 相似度权重表（我们自己定的，合计 1.00；每一项都可在读数里单独看到）
#
# ⚠️ 权重不是拍脑袋：2026-09-22 实测踩过一个坑 ——
#    改版把 `id="p1"` 挪成了 `data-id="p1"`（正是 Scrapling 文档里的原始场景）。
#    当时只在**同名属性之间**比值，属性名一改就完全看不见，结果两张双胞胎卡里
#    **选错了那一张**。源技术的口径明写是「属性（**名和值**）」⇒ 补了 `identity` 一项，
#    按**值**去找原件的识别 token（id 值 / class token / 其它属性值），
#    并让内容(text .20)在分量上压过外观(classes .14)。
_W = {
    "tag": 0.12,        # 标签名相同
    "id": 0.08,         # id 属性（同名同值）
    "classes": 0.14,    # class 序列相似（**顺序敏感**）
    "attrs": 0.10,      # 其余属性：名字集合 + 共有名的值
    "text": 0.20,       # 自身文本相似 —— 内容信号，压过外观
    "siblings": 0.07,   # 兄弟标签名序列相似
    "path": 0.09,       # 从根到自己的标签名序列相似
    "parent": 0.08,     # 父元素：标签名 + 属性 + 文本
    "identity": 0.12,   # 原件的识别 token 还能不能在候选身上按**值**找到
}


class _Node:
    """极简 DOM 节点。属性字典保序（Python dict 天然保序），这点对"顺序也算"很重要。"""

    __slots__ = ("tag", "attrs", "children", "parent", "texts", "index")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag
        self.attrs = dict(attrs or {})
        self.children = []
        self.parent = parent
        self.texts = []
        self.index = 0  # 在兄弟里的位置（0 基）

    def text(self) -> str:
        parts = list(self.texts)
        for c in self.children:
            parts.append(c.text())
        return _re.sub(r"\s+", " ", "".join(parts)).strip()

    def path_tags(self) -> list:
        out, cur = [], self
        while cur is not None and cur.parent is not None:
            out.append(cur.tag)
            cur = cur.parent
        return list(reversed(out))

    def siblings_tags(self) -> list:
        if self.parent is None:
            return []
        return [c.tag for c in self.parent.children]


class _TreeBuilder(_HTMLParser):
    """容错 HTML → 树。不追求规范级正确，追求"真实页面不炸、结构够用"。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("#document")
        self.stack = [self.root]
        self._opaque_depth = 0

    def handle_starttag(self, tag, attrs):
        if self._opaque_depth:
            if tag in _OPAQUE:
                self._opaque_depth += 1
            return
        if tag in _OPAQUE:
            self._opaque_depth = 1
            return
        parent = self.stack[-1]
        node = _Node(tag, attrs, parent)
        node.index = len(parent.children)
        parent.children.append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        if not self._opaque_depth and tag not in _OPAQUE:
            parent = self.stack[-1]
            node = _Node(tag, attrs, parent)
            node.index = len(parent.children)
            parent.children.append(node)

    def handle_endtag(self, tag):
        if self._opaque_depth:
            if tag in _OPAQUE:
                self._opaque_depth -= 1
            return
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if self._opaque_depth or not data.strip():
            return
        self.stack[-1].texts.append(data)


# ── CSS 选择器子集（够用即止；不支持的一律当"不匹配"并如实报，不静默当全匹配）──
_SEL_ATTR = _re.compile(r"^\[([A-Za-z_:][-A-Za-z0-9_:.]*)\s*(?:([\^\$\*~|]?=)\s*\"?([^\]\"]*)\"?)?\]$")
# ⚠️ 伪类正则**不许加 ^ $ 锚点**：它在复合选择器里是"其中一段"，
#    写成 `^:nth-child\((\d+)\)$` 再配 `.search()` 会永远匹配不到
#    `article:nth-child(2)` —— 实测踩过（8 个用例因此报红）。
_SEL_NTH = _re.compile(r":nth-child\((\d+)\)")


def _split_selector(sel: str) -> list:
    """把选择器拆成 [(combinator, compound), ...]；支持后代(空格)与子代(>)。"""
    sel = (sel or "").strip()
    if not sel:
        return []
    parts = _re.split(r"\s*(>)\s*|\s+", sel)
    out, comb = [], " "
    for p in parts:
        if p is None or p == "":
            continue
        if p == ">":
            comb = ">"
            continue
        out.append((comb, p.strip()))
        comb = " "
    return out


def _match_compound(node, comp: str) -> bool:
    if comp in ("", "*"):
        return True
    # 先摘伪类
    nth = None
    m = _SEL_NTH.search(comp)
    if m:
        nth = int(m.group(1))
        comp = comp[:m.start()] + comp[m.end():]
    if ":first-child" in comp:
        nth = 1
        comp = comp.replace(":first-child", "")
    if ":last-child" in comp:
        if node.parent is None or node.index != len(node.parent.children) - 1:
            return False
        comp = comp.replace(":last-child", "")
    if nth is not None:
        if node.parent is None or node.index != nth - 1:
            return False
    # 属性谓词
    for am in _re.finditer(r"\[[^\]]*\]", comp):
        pred = _SEL_ATTR.match(am.group(0))
        if not pred:
            return False
        name, op, val = pred.group(1), pred.group(2), pred.group(3)
        if name not in node.attrs:
            return False
        if op is None:
            continue
        have = node.attrs.get(name, "")
        if op == "=" and have != val:
            return False
        if op == "^=" and not have.startswith(val):
            return False
        if op == "$=" and not have.endswith(val):
            return False
        if op == "*=" and val not in have:
            return False
    comp = _re.sub(r"\[[^\]]*\]", "", comp)
    # id / class / tag
    if "#" in comp:
        tag_part, _, id_part = comp.partition("#")
        if node.attrs.get("id") != id_part:
            return False
        comp = tag_part
    if "." in comp:
        tag_part, *klasses = comp.split(".")
        have = set((node.attrs.get("class") or "").split())
        if not all(k in have for k in klasses if k):
            return False
        comp = tag_part
    if comp and comp != "*" and node.tag != comp.lower():
        return False
    return True


def _select(root, selector: str) -> list:
    steps = _split_selector(selector)
    if not steps:
        return []
    current = [root]
    for comb, comp in steps:
        nxt = []
        for base in current:
            if comb == ">":
                pool = base.children
            else:
                pool = []
                stack = list(base.children)
                while stack:
                    n = stack.pop(0)
                    pool.append(n)
                    stack.extend(n.children)
            for n in pool:
                if _match_compound(n, comp):
                    nxt.append(n)
        # 去重（后代轴可能重复命中同一节点）
        seen, uniq = set(), []
        for n in nxt:
            if id(n) not in seen:
                seen.add(id(n))
                uniq.append(n)
        current = uniq
        if not current:
            break
    return current


# ── 特征与相似度（本域的核心）─────────────────────────────────────────────

def _node_signature(node: _Node) -> dict:
    """把一个节点压成可入库的特征字典。字段就是文档里那套，名字用我们自己的。"""
    p = node.parent
    return {
        "tag": node.tag,
        "id": node.attrs.get("id"),
        "class": node.attrs.get("class") or "",
        "attrs": {k: v for k, v in node.attrs.items() if k not in ("id", "class")},
        "text": node.text()[:400],
        "sibs": node.siblings_tags(),
        "path": node.path_tags(),
        "parent_tag": p.tag if p is not None else None,
        "parent_class": (p.attrs.get("class") or "") if p is not None else "",
        "parent_attrs": ({k: v for k, v in p.attrs.items() if k not in ("id", "class")}
                         if p is not None else {}),
        "parent_text": (p.text()[:200] if p is not None else ""),
    }


def _ratio(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return _SM(None, a, b).ratio()


def _seq_ratio(a: list, b: list) -> float:
    return _ratio(" ".join(a or []), " ".join(b or []))


def _attrs_score(x: dict, y: dict) -> float:
    """名字集合用 Jaccard，共有名再比值的相似度；两边都空 ⇒ 1.0（都没属性也是像）。"""
    if not x and not y:
        return 1.0
    kx, ky = set(x), set(y)
    if not kx or not ky:
        return 0.0
    jac = len(kx & ky) / len(kx | ky)
    shared = kx & ky
    if not shared:
        return jac * 0.5
    vals = sum(_ratio(str(x[k]), str(y[k])) for k in shared) / len(shared)
    return 0.6 * jac + 0.4 * vals


def _identity_score(orig: dict, cand: dict) -> float:
    """原件的「识别 token」在候选身上还找不找得到 —— **按值找，不按属性名找**。

    为什么非要有这一项：改版最常见的一手就是把标识挪个属性名
    （`id="p1"` → `data-id="p1"`）。只在同名属性之间比值的话，
    这一挪就彻底隐身，双胞胎卡里必然选错。实测踩过，所以单列一项。

    token 取：原件的 id 值、class 里的 token（≥3 字符，滤掉 `a`/`on` 这类噪声）、
    以及其它属性的值。候选侧把**属性名与值**都摊平了找。
    原件本来就没有 token ⇒ 返回 1.0（这一项不参与区分，不许凭空扣分）。
    """
    toks = set()
    oid = str(orig.get("id") or "").strip().lower()
    if oid:
        toks.add(oid)
    for t in (orig.get("class") or "").split():
        if len(t) >= 3:
            toks.add(t.lower())
    for v in (orig.get("attrs") or {}).values():
        if isinstance(v, str) and v.strip():
            toks.add(v.strip().lower())
    if not toks:
        return 1.0
    cand_vals = set()
    for k, v in (cand.get("attrs") or {}).items():
        cand_vals.add(str(k).strip().lower())
        if isinstance(v, str) and v.strip():
            cand_vals.add(v.strip().lower())
    cid = str(cand.get("id") or "").strip().lower()
    if cid:
        cand_vals.add(cid)
    for t in (cand.get("class") or "").split():
        cand_vals.add(t.lower())
    cand_vals.discard("")
    if not cand_vals:
        return 0.0
    return len(toks & cand_vals) / len(toks)


def _similarity(orig: dict, cand: dict) -> dict:
    """逐项打分并回传明细 —— 出问题时要能指到"是哪一项不像"，不许只给一个黑箱数字。"""
    parts = {
        "tag": 1.0 if orig.get("tag") == cand.get("tag") else 0.0,
        "id": 1.0 if (orig.get("id") and orig.get("id") == cand.get("id"))
              else (0.0 if orig.get("id") or cand.get("id") else 1.0),
        # 顺序敏感：class 的书写顺序变了也算不像
        "classes": _ratio(orig.get("class") or "", cand.get("class") or ""),
        "attrs": _attrs_score(orig.get("attrs") or {}, cand.get("attrs") or {}),
        "text": _ratio(orig.get("text") or "", cand.get("text") or ""),
        "siblings": _seq_ratio(orig.get("sibs") or [], cand.get("sibs") or []),
        "path": _seq_ratio(orig.get("path") or [], cand.get("path") or []),
        "parent": (0.4 * (1.0 if orig.get("parent_tag") == cand.get("parent_tag") else 0.0)
                   + 0.3 * _ratio(orig.get("parent_class") or "", cand.get("parent_class") or "")
                   + 0.3 * _attrs_score(orig.get("parent_attrs") or {}, cand.get("parent_attrs") or {})),
        "identity": _identity_score(orig, cand),
    }
    total = sum(_W[k] * v for k, v in parts.items())
    return {"score": round(total, 4),
            "parts": {k: round(v, 4) for k, v in parts.items()}}


# ── 指纹库（SQLite，键 = 域名 + identifier）────────────────────────────────

def _db_path() -> _P:
    return _P(_os.environ.get(_DB_ENV) or _DEFAULT_DB)


def _connect():
    p = _db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    con = _sqlite3.connect(str(p), check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""CREATE TABLE IF NOT EXISTS web_fingerprints (
        domain TEXT NOT NULL,
        identifier TEXT NOT NULL,
        signature TEXT NOT NULL,
        saved_at REAL NOT NULL,
        hits INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (domain, identifier))""")
    con.commit()
    return con


_TWO_LEVEL = ("co.uk", "com.cn", "com.hk", "com.tw", "co.jp", "com.au", "org.cn",
              "net.cn", "gov.cn", "edu.cn", "com.sg", "co.kr")


def _domain_of(url: str | None) -> str:
    """取"可登记的域"当隔离键。没装 tld 库，用两级后缀表兜底 —— 表里没有就走末两段。"""
    if not url:
        return "default"
    host = (_urlparse(url).hostname or "").lower().strip(".")
    if not host:
        return "default"
    if host.startswith("www."):
        host = host[4:]
    bits = host.split(".")
    if len(bits) >= 3 and ".".join(bits[-2:]) in _TWO_LEVEL:
        return ".".join(bits[-3:])
    return ".".join(bits[-2:]) if len(bits) >= 2 else host


# ══════════════ 编码判定：按 HTML 标准 13.2.3 的**优先级** ══════════════
# 规范顺序：① BOM sniff（certain，压过一切）② 传输层 Content-Type charset（certain）
#           ③ meta prescan（tentative）④ 兜底
# 实测教训：本模块第一版写的是"Content-Type → 正则找 meta → utf-8"，
# **BOM 这一级整个缺失**，而且把 meta 与 HTTP 头平级了 —— 标准里**传输层压过 meta**。
_WS_CHARS = "\t\n\x0c\r "

# BOM 表（Encoding 规范 §BOM sniff）：命中后必须**丢掉 BOM 字节**
_BOMS = ((b"\xef\xbb\xbf", "utf-8"), (b"\xfe\xff", "utf-16-be"), (b"\xff\xfe", "utf-16-le"))


def _bom_sniff(blob: bytes):
    for mark, label in _BOMS:
        if blob.startswith(mark):
            return label, blob[len(mark):]
    return None, blob


def _norm_label(label: str | None) -> str | None:
    """标签归一（HTML 标准）：文档内出现的 UTF-16 一律改判 UTF-8；x-user-defined → windows-1252。"""
    l = str(label or "").strip().lower()
    if l in ("utf-16", "utf-16be", "utf-16le", "utf16"):
        return "utf-8"
    if l == "x-user-defined":
        return "windows-1252"
    return l or None


_ATTR_RE = _re.compile(
    r"""([A-Za-z_:][-A-Za-z0-9_:.]*)\s*(?:=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+)))?""")


def _tag_attrs(tag: str) -> dict:
    """抠标签属性。规范要求**属性名先去重，先出现者胜**。"""
    body = tag[5:] if tag[:5].lower() == "<meta" else tag
    out = {}
    for m in _ATTR_RE.finditer(body):
        k = m.group(1).lower()
        if k in out:
            continue
        v = m.group(2)
        if v is None:
            v = m.group(3)
        if v is None:
            v = m.group(4) or ""
        out[k] = v
    return out


def _extract_charset_from_content(content: str | None) -> str | None:
    """HTML 的 meta 抽 charset 算法：大小写不敏感找 "charset" → 跳空白 → **必须是 `=`**
    （否则继续找下一个 "charset"）→ 可选成对引号 → 取到第一个 ASCII 空白或 `;`。
    引号没配对 ⇒ nothing（返回 None 并停止，不再往下找）。"""
    s = str(content or "")
    low = s.lower()
    i = 0
    while True:
        j = low.find("charset", i)
        if j < 0:
            return None
        k = j + 7
        while k < len(s) and s[k] in _WS_CHARS:
            k += 1
        if k < len(s) and s[k] == "=":
            k += 1
            while k < len(s) and s[k] in _WS_CHARS:
                k += 1
            if k >= len(s):
                return None
            if s[k] in "\"'":
                end = s.find(s[k], k + 1)
                if end < 0:
                    return None
                return s[k + 1:end] or None
            end = k
            while end < len(s) and s[end] not in _WS_CHARS + ";":
                end += 1
            return s[k:end] or None
        i = j + 7


_META_LIMIT = 1024


def _meta_prescan(blob: bytes) -> str | None:
    """meta prescan（tentative）。规范明写作者只能在**前 1024 字节**里声明 ⇒ 只看这一段。

    两个开关照规范走：`http-equiv="content-type"` ⇒ got pragma；
    `content` 里的 charset 只有在 got pragma 为真时才算数；
    `charset` 属性则**绕开**这个开关（优先级更高）。
    """
    head = blob[:_META_LIMIT]
    low = head.lower()
    charset = None
    got_pragma = False
    pos = 0
    while pos < len(low):
        lt = low.find(b"<", pos)
        if lt < 0:
            break
        if low.startswith(b"<!--", lt):                      # 注释跳过
            end = low.find(b"-->", lt + 4)
            pos = len(low) if end < 0 else end + 3
            continue
        nxt = low[lt + 5:lt + 6]
        if low.startswith(b"<meta", lt) and nxt in (b"", b"\x09", b"\x0a", b"\x0c",
                                                    b"\x0d", b"\x20", b"/"):
            gt = low.find(b">", lt)
            tag = head[lt:len(head) if gt < 0 else gt].decode("latin-1", "replace")
            attrs = _tag_attrs(tag)
            if attrs.get("http-equiv", "").strip().lower() == "content-type":
                got_pragma = True
            if attrs.get("charset", "").strip():
                if charset is None:
                    charset = _norm_label(attrs["charset"])
            elif "content" in attrs:
                got = _extract_charset_from_content(attrs["content"])
                if got and charset is None and got_pragma:
                    charset = _norm_label(got)
            if charset is not None:
                return charset
            pos = len(low) if gt < 0 else gt + 1
            continue
        pos = lt + 1
    return charset


# ══════════════ 出网：自己跟重定向（含 307/308）══════════════
class _NoRedirect(_urlreq.HTTPRedirectHandler):
    """不让 urllib 自己跟重定向。三个理由，全是实测/规范定的：

      ① **stdlib 默认不跟 307/308** —— RFC 9110 规定这两者**必须保持方法**，
         而 `HTTPRedirectHandler` 对它们不生成新请求，会当成错误抛出来。
         本模块此前对外声称"跟随重定向"，实际遇 307 就会失败 ⇒ **那是过度声称**。
      ② 要如实报出跳链 `history`。
      ③ 上限与防环得自己定：**RFC 9110 没有规定最大跳数**（5 跳是已废止的 RFC 2068 建议），
         原文只有 "A client SHOULD detect and intervene in cyclical redirections"。
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


def _http_fetch(url: str, *, timeout: int = 25, max_bytes: int = 4 * 1024 * 1024,
                max_redirects: int = 8, headers: dict | None = None) -> dict:
    """真发请求的**唯一**出口。**永不抛**，一律回结构化 dict。

    GET-only 的抓取器里，301/302/303/307/308 的方法改写差别不体现（都是 GET），
    但仍按规范把状态码与跳链如实记下来。
    """
    hdrs = {"User-Agent": _DEFAULT_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
    if isinstance(headers, dict):
        hdrs.update({str(k): str(v) for k, v in headers.items()})
    opener = _urlreq.build_opener(_NoRedirect)
    current = url
    seen = [url]
    history = []
    t0 = _time.time()
    for hop in range(int(max_redirects) + 1):
        try:
            req = _urlreq.Request(current, headers=hdrs)
            resp = opener.open(req, timeout=max(3, int(timeout)))
        except _urlerr.HTTPError as e:
            code = int(getattr(e, "code", 0) or 0)
            loc = (e.headers.get("Location") if e.headers else None) or ""
            if code in _REDIRECT_CODES and loc:
                if hop >= int(max_redirects):
                    return {"ok": False, "url": url, "final_url": current, "status": code,
                            "history": history,
                            "error": "重定向超过自己定的上限 %d 跳（RFC 9110 没规定上限，"
                                     "这个数是我们的纪律）" % int(max_redirects),
                            "ms": int((_time.time() - t0) * 1000)}
                nxt = _urljoin(current, loc)                 # 规范：Location 相对当前请求 URI 解析
                if nxt in seen:
                    return {"ok": False, "url": url, "final_url": current, "status": code,
                            "history": history,
                            "error": "检测到重定向环：%s 又指向已访问过的 %s" % (current, nxt),
                            "ms": int((_time.time() - t0) * 1000)}
                history.append({"status": code, "from": current, "to": nxt})
                seen.append(nxt)
                current = nxt
                continue
            return {"ok": False, "url": url, "final_url": current, "status": code,
                    "history": history,
                    "error": "HTTP %s —— 非 2xx，不把它当内容返回" % (code or "?"),
                    "ms": int((_time.time() - t0) * 1000)}
        except _urlerr.URLError as e:
            return {"ok": False, "url": url, "final_url": current,
                    "error": "连不上：%s" % str(getattr(e, "reason", e))[:180],
                    "history": history, "ms": int((_time.time() - t0) * 1000)}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "url": url, "final_url": current,
                    "error": "%s: %s" % (type(e).__name__, str(e)[:180]),
                    "history": history, "ms": int((_time.time() - t0) * 1000)}
        try:
            status = int(getattr(resp, "status", 0) or 0)
            final_url = resp.geturl() or current
            ctype = (resp.headers.get("Content-Type") or "")
            transport = _charset_from_content_type(ctype)
            blob = resp.read(int(max_bytes) + 1)
        finally:
            try:
                resp.close()
            except Exception:  # noqa: BLE001
                pass
        truncated = len(blob) > int(max_bytes)
        if truncated:
            blob = blob[:int(max_bytes)]
        return {"ok": True, "url": url, "final_url": final_url, "status": status,
                "content_type": ctype.split(";")[0].strip(), "transport_charset": transport,
                "blob": blob, "truncated": truncated, "history": history,
                "ms": int((_time.time() - t0) * 1000)}
    return {"ok": False, "url": url, "error": "重定向处理异常终止", "history": history,
            "ms": int((_time.time() - t0) * 1000)}


def _charset_from_content_type(ctype: str) -> str | None:
    """只从**传输层** Content-Type 里取 charset（HTTP 侧算法，与 HTML 的 meta 算法不同）。"""
    m = _re.search(r";\s*charset\s*=\s*\"?([^\";\s]+)\"?", str(ctype or ""), _re.I)
    return _norm_label(m.group(1)) if m else None


# ══════════════ robots.txt：按 RFC 9309 全文实现 ══════════════
# 产品 token 必须只含 字母/下划线/连字符（ABNF: identifier = 1*(%x2D/%x41-5A/%x5F/%x61-7A)），
# 且**应当**是 UA 串的子串 —— 所以 _DEFAULT_UA 里带着它。
_ROBOTS_TOKEN = "GBT-Xiaotudou"
_ROBOTS_MAX_BYTES = 512 * 1024      # 规范 MUST ≥ 500 KiB
_ROBOTS_TTL = 24 * 3600             # 规范 SHOULD NOT 缓存超过 24 小时
_ROBOTS_CACHE: dict = {}


def _robots_parse(text: str) -> list:
    """RFC 9309 §2.2 的宽松实现。返回 [(agents:[…], rules:[(allow?, pattern), …]), …]

    组的边界：**连续多个 user-agent 行属于同一组**；一旦出现过规则，
    再来 user-agent 行就开新组。出现在任何 user-agent 之前的规则**不属于任何组，忽略**。
    """
    groups, agents, rules = [], [], []
    for raw in str(text or "").splitlines():
        line = raw.split("#", 1)[0]          # 注释：整行或行尾
        line = line.strip()
        if not line:
            continue
        key, sep, val = line.partition(":")
        if not sep:
            continue
        k = key.strip().lower()
        v = val.strip()
        if k == "user-agent":
            if rules:                        # 上一组到此为止
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(v.lower())
        elif k in ("allow", "disallow"):
            if not agents:                   # 不属于任何组 ⇒ 忽略（规范 SHOULD）
                continue
            rules.append((k == "allow", v))
    if agents:
        groups.append((agents, rules))
    return groups


def _robots_rules_for(groups: list, token: str):
    """**同名组合并**（规范 MUST）—— 注意这里**不是**最长匹配，最长匹配只用于路径。

    返回 rules 列表；都没有 ⇒ None（= 无规则适用 ⇒ 全放行）。
    """
    tok = str(token or "").lower()
    merged, star = [], None
    for agents, rules in groups:
        if tok and tok in agents:
            merged.extend(rules)
        if "*" in agents and star is None:
            star = rules
    if merged:
        return merged
    return star


def _robots_pattern_re(pat: str):
    """`*` = 0..n 任意字符（**含 `/`**）；结尾 `$` = 锚定末尾；其余按字面量。"""
    anchored = pat.endswith("$")
    body = pat[:-1] if anchored else pat
    out = []
    for ch in body:
        out.append(".*" if ch == "*" else _re.escape(ch))
    return _re.compile("^" + "".join(out) + ("$" if anchored else ""))


def _robots_allows(rules, path: str) -> tuple[bool, str]:
    """**最长（按八位组数）胜出**；等长时 allow 胜；无匹配 ⇒ 放行。

    `Disallow:` 空值：RFC 9309 **只给了编码形式 `empty-pattern = *WS`，没给匹配语义**（查不到）。
    这里显式选业界惯例「空值不构成限制」，并在此注明**这是我们的选择、不是规范**。
    """
    if rules is None:
        return True, "无匹配组且无 * 组 ⇒ 规范：no rules apply（放行）"
    if path == "/robots.txt":
        return True, "规范：/robots.txt 隐含放行"
    best = None
    for allow, pat in rules:
        if pat == "":                        # 空值：非规范选择，见 docstring
            continue
        if _robots_pattern_re(pat).match(path):
            octets = len(pat.encode("utf-8"))
            if best is None or octets > best[0] or (octets == best[0] and allow and not best[1]):
                best = (octets, allow, pat)
    if best is None:
        return True, "组内无规则匹配 ⇒ 规范：放行"
    return best[1], "最长八位组胜出：%s（%d 八位组）" % (best[2], best[0])


def _parse_page(source):
    """source 可以是 HTML 字符串、{'html':...}/{'page':...} 袋子，或已建好的 root。"""
    if isinstance(source, _Node):
        return source, None
    if isinstance(source, dict):
        for k in ("html", "page", "source"):
            if k in source:
                return _parse_page(source[k])
        raise ValueError("袋子里没有 html/page/source 字段")
    if not isinstance(source, str):
        raise ValueError("拿不到 HTML：期望字符串或袋子，实得 %s" % type(source).__name__)
    b = _TreeBuilder()
    b.feed(source)
    b.close()
    return b.root, None


class OmniWebMixin:
    """web 域能力 — 结构化读取（6 方法）。

    铁律：**看不懂就说看不懂**。选择器不支持、HTML 空、指纹库没存过、
    相似度不够 —— 一律返回带原因的失败态，绝不返回一个"看起来像"的结果糊过去。
    """

    # ── 1. 解析 ──
    def web_parse(self, html, url: str | None = None) -> dict:
        """HTML → 结构化页对象（本域其余方法的入参）。只吃字符串，不联网。"""
        try:
            root, _ = _parse_page(html)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": "解析失败：%s" % e, "domain": _domain_of(url)}
        nodes = []

        def walk(n):
            nodes.append(n)
            for c in n.children:
                walk(c)

        walk(root)
        return {"ok": True, "domain": _domain_of(url), "url": url,
                "nodes": len(nodes), "tags": sorted({n.tag for n in nodes if n.tag})[:40],
                "page": {"__web_page__": True, "url": url, "root": root}}

    # ── 2. 选择 ──
    def web_select(self, source, selector: str, limit: int | None = None) -> dict:
        """CSS 选择器子集：tag / #id / .class / [attr] / [attr=v] / [attr^=$=*=v] /
        :nth-child(n) / :first-child / :last-child / * ；支持后代(空格)与子代(>)。
        不支持的一律"不匹配"并如实报，**不静默当全匹配**。"""
        try:
            root, _ = _parse_page(source)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": "解析失败：%s" % e, "matches": [], "count": 0}
        sel = (selector or "").strip()
        if not sel:
            return {"ok": False, "error": "选择器为空 —— 不猜你想选什么", "matches": [], "count": 0}
        try:
            found = _select(root, sel)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": "选择器执行失败：%s" % e, "matches": [], "count": 0}
        cap = int(limit) if limit else 0
        if cap > 0:
            found = found[:cap]
        return {"ok": True, "selector": sel, "count": len(found),
                "matches": [{"tag": n.tag, "text": n.text()[:400], "attrs": dict(n.attrs),
                             "path": n.path_tags(), "index": n.index,
                             "__node__": n} for n in found]}

    # ── 3. 存特征 ──
    def web_save(self, source, selector: str, identifier: str | None = None,
                 url: str | None = None) -> dict:
        """把**选区里第一个元素**的特征存进指纹库。

        ⚠️ 只存第一个 —— 这是刻意的：选区若一次命中多个不同位置的元素，
        存"第一个"是可解释的；存"全部"会让重定位变成撞运气。
        （Scrapling 同样只存第一个，且把它写在文档的 Known Issues 里。）"""
        got = self.web_select(source, selector, limit=1)
        if not got.get("ok"):
            return got
        if not got["count"]:
            return {"ok": False, "error": "选择器没命中任何元素，没有东西可存",
                    "selector": selector, "count": 0}
        node = got["matches"][0]["__node__"]
        ident = (identifier or selector).strip()
        dom = _domain_of(url)
        sig = _node_signature(node)
        try:
            con = _connect()
            con.execute(
                "INSERT OR REPLACE INTO web_fingerprints (domain, identifier, signature, saved_at, hits)"
                " VALUES (?,?,?,?,0)", (dom, ident, _json.dumps(sig, ensure_ascii=False), _time.time()))
            con.commit()
            con.close()
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": "指纹落库失败：%s" % e, "identifier": ident, "domain": dom}
        return {"ok": True, "domain": dom, "identifier": ident,
                "note": "已存第 1 个命中元素的特征", "signature": sig}

    # ── 4. 自适应重定位（本域的核心价值）──
    def web_adaptive(self, source, selector: str, identifier: str | None = None,
                     url: str | None = None, min_score: float = 0.55) -> dict:
        """选择器失效后，按存下来的特征在页面上找**最像**的那个元素。

        返回里必须带三样东西才叫"如实"：命中的分数、逐项明细、以及
        `relocated` 真假 —— 分数不够就认输，**不给一个勉强像的充数**。
        """
        ident = (identifier or selector).strip()
        dom = _domain_of(url)
        try:
            con = _connect()
            row = con.execute("SELECT signature FROM web_fingerprints WHERE domain=? AND identifier=?",
                              (dom, ident)).fetchone()
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": "指纹库读不了：%s" % e, "relocated": False}
        if row is None:
            return {"ok": True, "relocated": False, "reason":
                    "库里没存过这个 identifier —— 先用 web_save 存一次（域=%s / id=%s）" % (dom, ident),
                    "domain": dom, "identifier": ident}
        orig = _json.loads(row[0])
        try:
            root, _ = _parse_page(source)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": "解析失败：%s" % e, "relocated": False}
        best, best_detail = None, None
        stack = [root]
        while stack:
            n = stack.pop()
            stack.extend(n.children)
            sc = _similarity(orig, _node_signature(n))
            if best_detail is None or sc["score"] > best_detail["score"]:
                best, best_detail = n, sc
        if best is None:
            return {"ok": True, "relocated": False, "reason": "页面里一个节点都没有",
                    "domain": dom, "identifier": ident}
        hit = best_detail["score"] >= float(min_score)
        if hit:
            try:
                con = _connect()
                con.execute("UPDATE web_fingerprints SET hits = hits + 1 WHERE domain=? AND identifier=?",
                            (dom, ident))
                con.commit()
                con.close()
            except Exception:  # noqa: BLE001
                pass  # 计数失败不影响"找回"这个事实，但也不假装成功
        return {"ok": True, "relocated": bool(hit), "score": best_detail["score"],
                "threshold": float(min_score), "parts": best_detail["parts"],
                "domain": dom, "identifier": ident,
                "match": {"tag": best.tag, "text": best.text()[:400],
                          "attrs": dict(best.attrs), "path": best.path_tags()},
                "reason": None if hit else
                          "最像的那个只有 %.4f 分（阈值 %.2f）—— 判定为没找回，不拿它充数"
                          % (best_detail["score"], float(min_score))}

    # ── 5. 读正文 ──
    def web_text(self, source, selector: str | None = None, limit: int = 200) -> dict:
        """取可读正文。给了 selector 就只读命中的那几个。"""
        if selector:
            got = self.web_select(source, selector, limit=limit)
            if not got.get("ok"):
                return got
            return {"ok": True, "count": got["count"],
                    "blocks": [{"tag": m["tag"], "text": m["text"]} for m in got["matches"]]}
        try:
            root, _ = _parse_page(source)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": "解析失败：%s" % e}
        return {"ok": True, "text": root.text()[:20000], "title": self._web_title(root)}

    @staticmethod
    def _web_title(root) -> str:
        for n in root.children:
            if n.tag == "title":
                return n.text()
        stack = list(root.children)
        while stack:
            n = stack.pop(0)
            if n.tag == "title":
                return n.text()
            stack.extend(n.children)
        return ""

    # ── 6. 库状态（看得见才敢信）──
    def web_stats(self, url: str | None = None) -> dict:
        """指纹库现状。给域名就只看那个域。"""
        dom = _domain_of(url) if url else None
        try:
            con = _connect()
            if dom:
                rows = con.execute(
                    "SELECT identifier, saved_at, hits FROM web_fingerprints WHERE domain=?"
                    " ORDER BY saved_at DESC", (dom,)).fetchall()
            else:
                rows = con.execute(
                    "SELECT domain, identifier, saved_at, hits FROM web_fingerprints"
                    " ORDER BY saved_at DESC LIMIT 200").fetchall()
            con.close()
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": "指纹库读不了：%s" % e, "db": str(_db_path())}
        return {"ok": True, "db": str(_db_path()), "domain": dom, "count": len(rows),
                "rows": [list(r) for r in rows]}

    # ── 7. robots.txt：按 RFC 9309 判"这一趟该不该抓" ──────────────────────
    def web_robots(self, url: str, timeout: int = 15, cache_seconds: int = _ROBOTS_TTL,
                   max_redirects: int = 5, user_agent: str | None = None) -> dict:
        """取 robots.txt 并判定。**返回的是带理由的决定，不是一个孤零零的 bool。**

        RFC 9309 §2.3.1 的默认行为是**不对称的**，最容易写错：
          · 2xx ⇒ MUST 遵守解析出来的规则
          · **4xx（Unavailable）⇒ MAY access any resources（放行）**
          · **5xx 或网络错误（Unreachable）⇒ MUST assume complete disallow（完全禁抓）**
          · robots.txt 自己的重定向 SHOULD 跟 ≥5 跳（可跨 authority）；超过 MAY 视为不可用
          · 缓存 SHOULD NOT 超过 24 小时；解析上限 MUST ≥ 500 KiB
        `Crawl-delay` / `Request-rate` 在 RFC 9309 全文 **0 次命中** ⇒ **不实现**（查不到就不编）。
        """
        raw = str(url or "").strip()
        if not _re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw):
            raw = "https://" + raw
        u = _urlparse(raw)
        if (u.scheme or "").lower() not in ("http", "https") or not u.hostname:
            return {"ok": False, "decision": "disallow", "url": raw,
                    "error": "robots 判定要有 http/https 的主机名"}
        root = "%s://%s" % (u.scheme, u.netloc)
        robots_url = root + "/robots.txt"
        path = u.path or "/"
        key = root.lower()
        now = _time.time()
        hit = _ROBOTS_CACHE.get(key)
        if hit and hit[0] > now:
            d = dict(hit[1])
            d["cached"] = True
            dec, why = _robots_allows(d.pop("_rules", None), path)
            return {**d, "ok": True, "decision": "allow" if dec else "disallow",
                    "reason": why, "path": path, "cached": True}

        got = _http_fetch(robots_url, timeout=timeout, max_bytes=_ROBOTS_MAX_BYTES,
                          max_redirects=max_redirects)
        if not got.get("ok"):
            st = int(got.get("status") or 0)
            if 400 <= st <= 499:          # Unavailable ⇒ 放行
                return {"ok": True, "decision": "allow", "url": robots_url, "status": st,
                        "path": path, "cached": False,
                        "reason": "HTTP %d = Unavailable ⇒ 规范：MAY access any resources（放行）" % st}
            # 5xx / 连不上 / 重定向过多 ⇒ Unreachable ⇒ **完全禁抓**（fail-closed）
            return {"ok": True, "decision": "disallow", "url": robots_url, "status": st or None,
                    "path": path, "cached": False,
                    "reason": "取不到 robots.txt（%s）⇒ 规范：MUST assume complete disallow"
                              "（fail-closed，宁可少抓不可乱抓）" % (got.get("error") or "无响应")}

        blob = got["blob"]
        cs, _ = _bom_sniff(blob)          # robots.txt MUST 是 UTF-8；有 BOM 就认 BOM
        text = blob.decode(cs or "utf-8", errors="replace")
        groups = _robots_parse(text)
        rules = _robots_rules_for(groups, user_agent or _ROBOTS_TOKEN)
        dec, why = _robots_allows(rules, path)
        info = {"ok": True, "url": robots_url, "status": got.get("status"), "path": path,
                "groups": len(groups), "rules": 0 if rules is None else len(rules),
                "cached": False, "_rules": rules}
        _ROBOTS_CACHE[key] = (now + max(60, int(cache_seconds)), dict(info))
        return {**{k: v for k, v in info.items() if k != "_rules"},
                "decision": "allow" if dec else "disallow", "reason": why}

    # ── 8. 真出网读一页（本域唯一的网络动作）─────────────────────────────
    def web_fetch(self, url: str, timeout: int = 25, max_bytes: int = 4 * 1024 * 1024,
                  headers: dict | None = None, max_redirects: int = 8,
                  honor_robots: bool = True) -> dict:
        """读一个网页，返回**原始 HTML**（不是去标签的纯文本）。

        为什么非要原文：`browser` 能力位的 `op=fetch` 把标签全删了
        （`browser_cap.py` 里 `re.sub(r"<[^>]+>", " ", text)`），
        那样**选不了元素、存不了特征**，自适应重定位就无从谈起。

        纪律：
          · 只认 http/https —— 别的协议一律拒绝并说明（不给 `file://` 留口子）；
          · **默认先问 robots.txt**（RFC 9309）；被禁就如实拒绝，并把理由带出来；
          · 自己跟重定向（含 stdlib 默认不跟的 **307/308**）、自己定上限、自己防环；
          · 编码按 HTML 标准的优先级：**BOM → 传输层 → meta prescan → 兜底**，
            并把"是哪一级定的"报出来（`charset_source`），出乱码时能直接定位；
          · 有超时、有字节上限；超限**截断并如实标 `truncated`**，不假装读全；
          · 非 2xx ⇒ `ok=False` 带状态码，**不把 404 页面当内容返回**。

        门在哪：**本方法不自授权**。调用方经 `run_task` → `security/policy.py` 判定
        （当前口径见文件头：要 `desktop_control`）。我不给自己发授权。
        """
        raw_url = str(url or "").strip()
        if not raw_url:
            return {"ok": False, "error": "没给 url —— 不猜你想读哪一页"}
        if len(raw_url) > _URL_MAX:
            return {"ok": False, "error": "url 太长（>%d）" % _URL_MAX}
        normalized = False
        if not _re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw_url):
            raw_url = "https://" + raw_url
            normalized = True
        scheme = (_urlparse(raw_url).scheme or "").lower()
        if scheme not in ("http", "https"):
            return {"ok": False, "url": raw_url,
                    "error": "只读 http/https；拿到的是 %r —— 拒绝（不给本地文件留口子）" % scheme}
        if not (_urlparse(raw_url).hostname or ""):
            return {"ok": False, "url": raw_url, "error": "url 里没有主机名"}

        robots = None
        if honor_robots:
            robots = self.web_robots(raw_url, timeout=min(int(timeout), 15))
            if robots.get("decision") != "allow":
                return {"ok": False, "url": raw_url, "normalized": normalized,
                        "robots": robots, "stage": "robots",
                        "error": "robots.txt 不允许抓这个路径：%s" % robots.get("reason")}

        got = _http_fetch(raw_url, timeout=timeout, max_bytes=max_bytes,
                          max_redirects=max_redirects, headers=headers)
        if not got.get("ok"):
            return {k: v for k, v in got.items() if k != "blob"}
        blob = got["blob"]
        cs, blob = _bom_sniff(blob)
        source = "bom" if cs else ""
        if cs is None:
            cs = got.get("transport_charset")
            source = "transport" if cs else ""
        if cs is None:
            cs = _meta_prescan(blob)
            source = "meta" if cs else ""
        if cs is None:
            cs, source = "utf-8", "default"
        try:
            text = blob.decode(cs, errors="replace")
        except LookupError:
            text = blob.decode("utf-8", errors="replace")
            cs, source = "utf-8", "default(未知标签被拒)"
        tm = _re.search(r"<title[^>]*>(.*?)</title>", text, _re.S | _re.I)
        title = _html.unescape(_re.sub(r"\s+", " ", tm.group(1)).strip())[:200] if tm else ""
        return {"ok": True, "url": raw_url, "final_url": got["final_url"],
                "status": got["status"], "domain": _domain_of(got["final_url"]),
                "content_type": got["content_type"], "charset": cs, "charset_source": source,
                "bytes": len(blob), "truncated": got["truncated"], "history": got["history"],
                "html": text, "title": title, "normalized": normalized, "ms": got["ms"],
                "robots": robots or {"decision": "skipped", "reason": "调用方显式关掉了 robots 检查"},
                "note": ("已截断到 %d 字节（页面更大）" % int(max_bytes)) if got["truncated"]
                        else "完整读取"}

    def web_read(self, url: str, selector: str | None = None,
                 adaptive: bool = False, auto_save: bool = False,
                 identifier: str | None = None, limit: int | None = None,
                 timeout: int = 25, max_bytes: int = 4 * 1024 * 1024,
                 honor_robots: bool = True) -> dict:
        """**一句话读网**：抓 → 解析 → （选择 / 自适应找回 / 读正文）。

        这是给大脑用的那一个口：不想分三步就调它。
        选择器失效时传 `adaptive=True`，它会按存过的特征把元素找回来 ——
        这是本域存在的意义（页面改版后触手不再当场瞎）。
        """
        f = self.web_fetch(url, timeout=timeout, max_bytes=max_bytes,
                           honor_robots=honor_robots)
        if not f.get("ok"):
            return {"ok": False, "stage": "fetch", "url": url, "error": f.get("error"),
                    "status": f.get("status"), "ms": f.get("ms")}
        out = {"ok": True, "url": f["url"], "final_url": f["final_url"],
               "status": f["status"], "domain": f["domain"], "bytes": f["bytes"],
               "truncated": f["truncated"], "title": f["title"],
               "fetch_ms": f["ms"], "transport": "web_fetch（原始 HTML）"}
        page = {"html": f["html"], "url": f["final_url"]}
        if selector and adaptive:
            got = self.web_adaptive(page, selector, identifier=identifier,
                                    url=f["final_url"])
            out["mode"] = "adaptive"
            out.update({k: got.get(k) for k in
                        ("relocated", "score", "threshold", "parts", "match", "reason")})
            out["ok"] = bool(got.get("ok"))
        elif selector:
            got = self.web_select(page, selector, limit=limit)
            out["mode"] = "select"
            out["count"] = got.get("count", 0)
            out["matches"] = [{k: m[k] for k in ("tag", "text", "attrs", "path", "index")}
                              for m in got.get("matches", [])]
            out["ok"] = bool(got.get("ok"))
            if not out["ok"]:
                out["error"] = got.get("error")
            if auto_save and out["ok"] and out["count"]:
                out["saved"] = self.web_save(page, selector, identifier=identifier,
                                             url=f["final_url"])
        else:
            got = self.web_text(page)
            out["mode"] = "text"
            out["text"] = got.get("text", "")
        return out
