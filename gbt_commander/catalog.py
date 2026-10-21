# -*- coding: utf-8 -*-
"""能力目录的读取与检索（零第三方依赖，只用标准库）。

目录本体是 `data/capabilities.json`：由框架的 `gbt_allinone.caps_registry` 现读生成，
**不是手抄的清单**。每一份记录都是"这台机器上真存在的一位能力"，字段含义见下：

    name             能力位名（调用时就用它）
    domain           所属域（30 个域之一）
    desc             一句话说明（长的会写清 op、要什么参数、失败长什么样）
    readonly         是否是只读位（False ⇒ 调用会改状态/出网/花钱，必须先过授权门）
    requires_params  是否必须带参数（True ⇒ 空参调用会被判"缺参"而不是"通过"）
    scopes_static    这一位在门里登记的作用域（空列表 = 不需要授权，但**不等于只读**）
    params_hint      参数形状提示
    handler          框架内部的处理入口（只用于追溯，读者一般不用管）

用法：

    from gbt_commander import Catalog

    cat = Catalog.load()
    len(cat)                     # 341
    cat.domains()                # 30 个域名
    cat.get("mirror_scan")       # 取某一位
    cat.search("回滚发布", 3)     # 按意图找能力位，返回 [(capability, score)]
"""
from __future__ import annotations

import json
import math
import pathlib
import re
from dataclasses import dataclass, field
from typing import Iterable, Iterator

__all__ = ["Capability", "Catalog", "DEFAULT_DB", "DEFAULT_LEXICON"]

DEFAULT_DB = pathlib.Path(__file__).resolve().parent.parent / "data" / "capabilities.json"
DEFAULT_LEXICON = pathlib.Path(__file__).resolve().parent.parent / "data" / "intent-lexicon.json"

# 中文没有空格切词，用「汉字二元组」当检索单位；英文按词切。
_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_WORD = re.compile(r"[a-z0-9_]{2,}")


def _tokens(text: str) -> list[str]:
    """把一段中文/英文混排的意图切成可比较的检索单位。"""
    low = (text or "").lower()
    toks = _WORD.findall(low)
    han = _CJK.findall(low)
    toks.extend("".join(han[i:i + 2]) for i in range(len(han) - 1))
    if len(han) == 1:
        toks.append(han[0])
    return [t for t in toks if t]


def _parse_scopes(value) -> tuple[str, ...]:
    """把目录里的 `scopes_static` 归一成作用域名元组。

    🔴 这一格**不是列表，是人话**：实测 341 条全是字符串，形状两种 ——
        · `零作用域（空 payload 下不需要票）`（306 条，表示不需要授权）
        · `` `process_execute`、`external_llm` ``（35 条，反引号 + 顿号分隔）
    第一版直接 `tuple(str)`，把"零作用域"拆成了 21 个汉字单字（`零,作,用,域,（,空,…`），
    于是 stats 把 341 位全算成"要票"—— 这就是本仓最忌讳的那种假读数。
    所以这里按真形状解析，认不出的**不猜**：留空 + 由测试把这条钉住。
    """
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(v).strip() for v in value if str(v).strip())
    text = str(value)
    if "零作用域" in text:
        return ()
    parts = re.split(r"[、,，;；/\s]+", text)
    out = []
    for part in parts:
        cleaned = part.strip().strip("`'\"()（）").strip()
        if cleaned and re.fullmatch(r"[a-z][a-z0-9_]*", cleaned):
            out.append(cleaned)
    return tuple(out)


@dataclass(frozen=True)
class Capability:
    """一位能力的只读视图（构造后不再改）。"""

    name: str
    domain: str
    desc: str = ""
    readonly: bool = True
    requires_params: bool = False
    scopes_static: tuple[str, ...] = field(default_factory=tuple)
    params_hint: str = ""
    handler: str = ""

    @classmethod
    def from_record(cls, rec: dict) -> "Capability":
        return cls(
            name=str(rec.get("name") or ""),
            domain=str(rec.get("domain") or ""),
            desc=str(rec.get("desc") or ""),
            readonly=bool(rec.get("readonly", True)),
            requires_params=bool(rec.get("requires_params", False)),
            scopes_static=_parse_scopes(rec.get("scopes_static")),
            params_hint=str(rec.get("params_hint") or ""),
            handler=str(rec.get("handler") or ""),
        )

    @property
    def needs_ticket(self) -> bool:
        """这一位有没有挂授权作用域（有 ⇒ 调用前必须主人发票）。"""
        return bool(self.scopes_static)

    @property
    def one_liner(self) -> str:
        """把说明压成一行，便于表格里看。"""
        text = " ".join(self.desc.split())
        return text if len(text) <= 110 else text[:109] + "…"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "domain": self.domain,
            "readonly": self.readonly,
            "requires_params": self.requires_params,
            "scopes_static": list(self.scopes_static),
            "params_hint": self.params_hint,
            "desc": self.desc,
        }


class Catalog:
    """341 位能力的目录。构造一次，之后只读。"""

    def __init__(self, caps: Iterable[Capability], meta: dict | None = None,
                 lexicon: list[dict] | None = None) -> None:
        self._caps = list(caps)
        self._by_name: dict[str, list[Capability]] = {}
        for cap in self._caps:
            self._by_name.setdefault(cap.name, []).append(cap)
        self.meta = dict(meta or {})
        # 意图词表：命中就强加权；点错名字的条目记进 lexicon_problems，交给测试报红。
        self.lexicon: list[dict] = []
        self.lexicon_problems: list[str] = []
        for entry in lexicon or []:
            say = [s.lower() for s in (entry.get("say") or []) if str(s).strip()]
            target = {k: float(v) for k, v in (entry.get("caps") or {}).items()}
            if not say or not target:
                continue
            bad = [name for name in target if name not in self._by_name]
            if bad:
                self.lexicon_problems.append("%s（点错名字：%s）" % (entry.get("what") or "?", ",".join(bad)))
                target = {k: v for k, v in target.items() if k in self._by_name}
            if target:
                self.lexicon.append({"what": entry.get("what") or "", "say": say, "caps": target})

    # ---------- 构造 ----------
    @classmethod
    def load(cls, path: str | pathlib.Path | None = None,
             lexicon_path: str | pathlib.Path | None = None) -> "Catalog":
        """从 `data/capabilities.json` 读目录；文件不在就抛出**带路径的**错误。

        若同目录下有 `intent-lexicon.json`，一并读进来当"人工词表"（没有也能跑）。
        """
        p = pathlib.Path(path) if path else DEFAULT_DB
        if not p.is_file():
            raise FileNotFoundError(
                "找不到能力目录：%s（它由框架的 caps_registry 现读生成，随仓库一起发布）" % p
            )
        raw = json.loads(p.read_text(encoding="utf-8"))
        records = raw.get("capabilities") if isinstance(raw, dict) else raw
        if not isinstance(records, list) or not records:
            raise ValueError("能力目录格式不对：期望 {\"capabilities\": [...]}，实际读到 %r" % type(records))
        meta = {k: raw[k] for k in ("count", "domains", "note") if isinstance(raw, dict) and k in raw}

        lexicon: list[dict] = []
        lp = pathlib.Path(lexicon_path) if lexicon_path else DEFAULT_LEXICON
        if lp.is_file():
            try:
                blob = json.loads(lp.read_text(encoding="utf-8"))
                lexicon = list(blob.get("intents") or []) if isinstance(blob, dict) else list(blob)
            except Exception as exc:                              # noqa: BLE001
                raise ValueError("意图词表读不了：%s（%s）" % (lp, exc)) from exc
        return cls((Capability.from_record(r) for r in records), meta, lexicon)

    # ---------- 基本读取 ----------
    def __len__(self) -> int:
        return len(self._caps)

    def __iter__(self) -> Iterator[Capability]:
        return iter(self._caps)

    def names(self) -> list[str]:
        return [c.name for c in self._caps]

    def domains(self) -> dict[str, int]:
        """域名 → 成员数。"""
        out: dict[str, int] = {}
        for cap in self._caps:
            out[cap.domain] = out.get(cap.domain, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))

    def get(self, name: str) -> Capability | None:
        """按名字取；同名多位存在于不同域时返回第一个，多用途请用 get_all。"""
        hits = self._by_name.get(name) or []
        return hits[0] if hits else None

    def get_all(self, name: str) -> list[Capability]:
        return list(self._by_name.get(name) or [])

    def by_domain(self, domain: str) -> list[Capability]:
        return [c for c in self._caps if c.domain == domain]

    def stats(self) -> dict:
        """一眼能说的几个数：总数 / 域数 / 只读几多 / 要票几多 / 必须带参几多。"""
        return {
            "capabilities": len(self._caps),
            "domains": len(self.domains()),
            "readonly": sum(1 for c in self._caps if c.readonly),
            "writes": sum(1 for c in self._caps if not c.readonly),
            "needs_ticket": sum(1 for c in self._caps if c.needs_ticket),
            "requires_params": sum(1 for c in self._caps if c.requires_params),
        }

    # ---------- 检索 ----------
    def _df(self) -> dict[str, int]:
        """每个检索词在多少位能力里出现过（缓存一次，用来算稀有度权重）。"""
        cached = getattr(self, "_df_cache", None)
        if cached is not None:
            return cached
        df: dict[str, int] = {}
        for cap in self._caps:
            blob = (cap.name + " " + cap.domain + " " + cap.desc).lower()
            for tok in set(_tokens(blob)):
                df[tok] = df.get(tok, 0) + 1
        self._df_cache = df
        return df

    def lexicon_hits(self, query: str) -> list[dict]:
        """这条意图命中了词表里的哪几条（给 CLI 用来解释"为什么是它"）。"""
        low = (query or "").lower()
        return [e for e in self.lexicon if any(p in low for p in e["say"])]

    def score(self, cap: Capability, query: str) -> float:
        """把一个意图和一位能力算成可比的分。

        四条口径（都是被测试咬出来的）：
        1. **词表命中一票定音**：`ppt` / `回滚` / `无人值守` 这类意图词，是人工维护的强信号，
           命中给的权重远大于全文检索的零碎分数；
        2. **稀有词更值钱**：`markdown` 只有一两位提过，`变成` 一大片都提过 —— 不按稀有度加权，
           前者的信号会被后者的噪声淹没；
        3. **名字命中 > 域命中 > 说明命中**（6 / 3 / 1）；
        4. **每个词只算一次**：同一个词在长说明里出现十遍也不该翻十倍。
        """
        low = (query or "").lower()
        total = 0.0
        for entry in self.lexicon_hits(low):
            weight = entry["caps"].get(cap.name)
            if weight:
                total += 100.0 * weight

        toks = sorted(set(_tokens(low)))
        if not toks:
            return total
        df = self._df()
        n = max(1, len(self._caps))
        name = cap.name.lower()
        domain = cap.domain.lower()
        desc = cap.desc.lower()
        for tok in toks:
            weight = math.log(1.0 + n / max(1, df.get(tok, 1)))
            if tok in name:
                total += 6.0 * weight
            elif tok in domain:
                total += 3.0 * weight
            elif tok in desc:
                total += 1.0 * weight
        return total

    def search(self, query: str, limit: int = 5) -> list[tuple[Capability, float]]:
        """按意图找能力位，返回 [(capability, score)]，分高者在前，0 分不返回。"""
        scored = [(cap, self.score(cap, query)) for cap in self._caps]
        scored = [pair for pair in scored if pair[1] > 0]
        scored.sort(key=lambda pair: (-pair[1], pair[0].name))
        return scored[: max(1, int(limit))]
