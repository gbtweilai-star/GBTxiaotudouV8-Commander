# -*- coding: utf-8 -*-
"""行式记录网格（record_grid）——自描述文本的拆解 / 校验 / 归一 / 回写核心。

来源：吸收 2000 年代 AI 链接清单格式的**方法**，不复制其数据。
被吸收的本质只有四条：
  ① 行式记录 —— 一行一条，可 grep、可 diff、可手改，不需要任何工具链；
  ② 闭集词表 —— 标签与类别是受控词汇，语义写进契约而非自由发挥；
  ③ 分隔纪律 —— 用「位置 + 分隔符」而非引号转义，换取文本的极简；
  ④ 解析期守契约 —— 格式不合法当场暴露，不静默吞掉。

重印（合上原件、只看本质重建）时补上原件没有的四点，这是它更原生的地方：
  · 逐行诊断不中断：一行坏不废整卷，坏行带行号 / 原文 / 原因原样上报；
  · 显式解码 + 位置感知分词：字节先解码再判格式，BOM/GBK 不再被误判成「格式错」；
    且记录每个 token 的字符偏移，尾部自由文本按原文切片，保留原始空格；
  · 词表即数据：未知词不再 assert 崩溃，降级为 finding 并保留记录；
  · 回写自证：emit 出的文本重新 parse 后记录指纹不变（parse∘emit 幂等），
    能力自证而不是自说。

它对原格式最脆弱处的正面修复是「贪心 + 回溯」字段匹配：标题里出现 http 字样、
备注里出现标签词，都不会把整行判死。
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import dataclasses
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

DECODERS: tuple[str, ...] = ("utf-8-sig", "utf-8", "gbk", "cp936", "latin-1")
DEFAULT_SCHEMES: tuple[str, ...] = ("http", "https", "ftp", "ftps", "mailto", "file", "sftp", "news")
FLEX_KINDS = ("flex",)
ATOM_KINDS = ("atom", "url", "packed", "number", "tail", "flex")
_SCHEME_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.\-]*):")
_NUM_RE = re.compile(r"[+-]?\d+$")
_WS_RE = re.compile(r"\S+")
MARKER_CHARS = "*!+^~"


@dataclass(frozen=True)
class Field:
    """一个字段的读取契约：kind 决定读法，其余属性按 kind 取用。"""

    name: str
    kind: str = "flex"
    required: bool = False
    marker: str = ""                       # flex：附着在末尾的标记（如推荐星号）
    left: str = ""                         # packed：左侧（多值）字段名
    right: str = ""                        # packed：右侧（单值）字段名
    left_vocab: frozenset[str] = frozenset()
    right_vocab: frozenset[str] = frozenset()

    def to_dict(self) -> dict:
        out = {"name": self.name, "kind": self.kind, "required": self.required}
        if self.marker:
            out["marker"] = self.marker
        if self.kind == "packed":
            out.update({"left": self.left, "right": self.right,
                        "left_vocab": sorted(self.left_vocab),
                        "right_vocab": sorted(self.right_vocab)})
        return out

    @staticmethod
    def from_dict(raw: dict) -> "Field":
        return Field(
            name=str(raw.get("name") or ""),
            kind=str(raw.get("kind") or "flex"),
            required=bool(raw.get("required")),
            marker=str(raw.get("marker") or ""),
            left=str(raw.get("left") or ""),
            right=str(raw.get("right") or ""),
            left_vocab=frozenset(raw.get("left_vocab") or ()),
            right_vocab=frozenset(raw.get("right_vocab") or ()),
        )


@dataclass(frozen=True)
class Plan:
    """一张记录表的结构：字段顺序 + 分隔方式 + URL 协议白名单。"""

    name: str
    fields: tuple[Field, ...]
    sep: str | None = None                  # None = 按空白切分
    quoted: bool = False                    # sep 模式下是否走引号规则（RFC4180 风格）
    url_schemes: tuple[str, ...] = DEFAULT_SCHEMES
    note: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "sep": self.sep, "quoted": self.quoted,
                "url_schemes": list(self.url_schemes), "note": self.note,
                "fields": [f.to_dict() for f in self.fields]}

    @staticmethod
    def from_dict(raw: dict) -> "Plan":
        fields = tuple(Field.from_dict(f) for f in (raw.get("fields") or ()))
        if not fields:
            raise ValueError("plan.fields 不能为空")
        names = [f.name for f in fields]
        if len(set(names)) != len(names):
            raise ValueError(f"plan.fields 名称重复: {names}")
        sep = raw.get("sep", None)
        if sep is not None:
            sep = str(sep)
            if sep == "\\t":
                sep = "\t"
            if len(sep) != 1:
                raise ValueError("plan.sep 只能是单个字符或 null（空白切分）")
        return Plan(name=str(raw.get("name") or "custom"), fields=fields,
                    sep=sep, quoted=bool(raw.get("quoted")),
                    url_schemes=tuple(raw.get("url_schemes") or DEFAULT_SCHEMES),
                    note=str(raw.get("note") or ""))


# 预置结构：被吸收格式的「语法」——词表是默认建议值，按语料替换
PLAN_PRESETS: dict[str, Plan] = {
    "link_index": Plan(
        name="link_index",
        fields=(
            Field("title", "flex", required=True, marker="*"),
            Field("url", "url", required=True),
            Field("packed", "packed", required=True, left="topics", right="genre",
                  left_vocab=frozenset(),
                  right_vocab=frozenset()),
            Field("comment", "tail"),
        ),
        sep=None,
        note="标题[*] URL 标签,标签.类别 备注 —— 行式链接/资源索引的通用形态",
    ),
}


def _looks_url(token: str, schemes: Sequence[str]) -> bool:
    m = _SCHEME_RE.match(token or "")
    return bool(m) and m.group(1).lower() in schemes


def _tokenize(line: str, plan: Plan) -> list[tuple[str, int, int]]:
    """切分为 (token, start, end)；保留字符偏移，尾字段可按原文精确切片。"""
    if plan.sep is None:
        return [(m.group(), m.start(), m.end()) for m in _WS_RE.finditer(line)]
    if plan.quoted:
        return _tokenize_quoted(line, plan.sep)
    return _tokenize_by_char(line, plan.sep)


def _tokenize_by_char(line: str, sep: str) -> list[tuple[str, int, int]]:
    out: list[tuple[str, int, int]] = []
    pos = 0
    while True:
        idx = line.find(sep, pos)
        if idx < 0:
            out.append((line[pos:], pos, len(line)))
            return out
        out.append((line[pos:idx], pos, idx))
        pos = idx + 1


def _tokenize_quoted(line: str, sep: str) -> list[tuple[str, int, int]]:
    try:
        values = next(csv.reader(io.StringIO(line), delimiter=sep))
    except Exception:
        return _tokenize_by_char(line, sep)
    out: list[tuple[str, int, int]] = []
    pos = 0
    for value in values:
        idx = line.find(value, pos) if value else pos
        if idx < 0:
            return _tokenize_by_char(line, sep)
        out.append((value, idx, idx + len(value)))
        pos = idx + len(value)
    return out


def _match_fields(fields: Sequence[Field], tokens: list[tuple[str, int, int]],
                  raw: str, plan: Plan) -> tuple[dict, list[dict]] | None:
    """贪心 + 回溯：为整行找一组满足全部字段契约的切分；失败返回 None。"""
    findings: list[dict] = []
    total = len(fields)
    ntok = len(tokens)

    def walk(idx: int, cur: int, acc: dict) -> dict | None:
        if idx == total:
            return acc if cur >= ntok else None
        spec = fields[idx]

        if spec.kind == "tail":
            if idx != total - 1:
                raise ValueError("tail 字段必须是最后一个字段")
            start = tokens[cur][1] if cur < ntok else len(raw)
            out = dict(acc)
            out[spec.name] = raw[start:].strip()
            return out

        if cur >= ntok:
            if spec.required:
                return None
            out = dict(acc)
            out[spec.name] = [] if spec.kind == "packed" else ""
            return walk(idx + 1, cur, out)

        if spec.kind == "atom":
            out = dict(acc)
            out[spec.name] = tokens[cur][0]
            return walk(idx + 1, cur + 1, out)

        if spec.kind == "number":
            token = tokens[cur][0]
            if not _NUM_RE.match(token):
                if spec.required:
                    return None
                out = dict(acc)
                out[spec.name] = None
                return walk(idx + 1, cur, out)
            out = dict(acc)
            out[spec.name] = int(token)
            return walk(idx + 1, cur + 1, out)

        if spec.kind == "url":
            token = tokens[cur][0]
            if not _looks_url(token, plan.url_schemes):
                return None
            out = dict(acc)
            out[spec.name] = token
            return walk(idx + 1, cur + 1, out)

        if spec.kind == "packed":
            token = tokens[cur][0]
            if "." not in token:
                return None
            left_raw, _, right = token.rpartition(".")
            values = [v for v in left_raw.split(",") if v]
            unknown = [v for v in values if spec.left_vocab and v not in spec.left_vocab]
            if spec.right_vocab and right not in spec.right_vocab:
                unknown.append(right)
            if unknown:
                findings.append({"code": "unknown_vocabulary", "field": spec.name,
                                 "token": token, "value": ",".join(unknown)})
            out = dict(acc)
            out[spec.left] = values
            out[spec.right] = right
            return walk(idx + 1, cur + 1, out)

        if spec.kind == "flex":
            for end in range(cur + 1, ntok + 1):
                value = " ".join(t[0] for t in tokens[cur:end])
                out = dict(acc)
                if spec.marker and value.endswith(spec.marker) and len(value) > len(spec.marker):
                    out[spec.name] = value[: -len(spec.marker)].strip()
                    out[spec.name + "_flag"] = True
                else:
                    out[spec.name] = value
                    if spec.marker:
                        out[spec.name + "_flag"] = False
                got = walk(idx + 1, end, out)
                if got is not None:
                    return got
            if not spec.required:
                out = dict(acc)
                out[spec.name] = ""
                return walk(idx + 1, cur, out)
            return None

        raise ValueError(f"未知字段类型: {spec.kind}")

    acc = walk(0, 0, {})
    if acc is None:
        return None
    return acc, findings


# ── 解码 / 解析 / 回写 / 自证 ──────────────────────────────────────────────

def decode_bytes(data: bytes, preferred: str | None = None) -> tuple[str, str, int]:
    """字节 → (文本, 编码, 替换字符数)。显式解码，绝不把编码问题当成格式问题。"""
    if preferred:
        try:
            return data.decode(preferred), preferred, 0
        except (LookupError, UnicodeDecodeError):
            pass
    # BOM 优先：先认字节序标记，再按内容试编码。顺序反了会把 BOM 当正文（\ufeff 入字段）
    # 或把「无 BOM 的 UTF-8」标成 utf-8-sig（名字失真，调用方据此判错）。
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig"), "utf-8-sig", 0
    for bom, enc in ((b"\xff\xfe\x00\x00", "utf-32"), (b"\x00\x00\xfe\xff", "utf-32"),
                     (b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16")):
        if data.startswith(bom):
            try:
                return data.decode(enc), enc, 0
            except (LookupError, UnicodeDecodeError):
                break
    for enc in DECODERS:
        if enc == "utf-8-sig":
            continue
        try:
            return data.decode(enc), enc, 0
        except (LookupError, UnicodeDecodeError):
            continue
    text = data.decode("utf-8", errors="replace")
    return text, "utf-8(replace)", text.count("\ufffd")


def _diagnose(raw: str, plan: Plan) -> dict:
    """匹配失败时给出可执行的定位提示，而不是只说一句 invalid。"""
    tokens = _tokenize(raw, plan)
    values = [t[0] for t in tokens]
    url_like = [v for v in values if _SCHEME_RE.match(v)]
    looks_like_url_tag = [v for v in url_like if not _looks_url(v, plan.url_schemes)]
    hints = [f"字段数 {len(values)}，契约要求 {len(plan.fields)} 个字段"]
    if looks_like_url_tag:
        hints.append(f"疑似 URL 但协议不在白名单: {looks_like_url_tag[0][:60]}")
    elif url_like:
        packed = [v for v in values if "." in v]
        if not packed:
            hints.append("缺少「标签,标签.类别」段（packed 字段）")
        else:
            hints.append(f"packed 段 {packed[-1][:40]} 与字段顺序不符或含空标签")
    else:
        hints.append("未找到 URL 段，检查是否缺少协议前缀或字段顺序颠倒")
    return {"code": "template_mismatch", "hints": hints}


def parse_text(text: str, plan: Plan, *, encoding: str = "utf-8",
               max_line_len: int = 20000) -> dict:
    """逐行解析；坏行不废整卷，带行号 / 原文 / 原因原样上报。"""
    records: list[dict] = []
    invalid: list[dict] = []
    findings: list[dict] = []
    blank = 0
    longest = 0
    for lineno, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            blank += 1
            continue
        longest = max(longest, len(raw))
        if len(raw) > max_line_len:
            invalid.append({"line": lineno, "raw": raw[:200], "code": "line_too_long",
                            "hints": [f"行长 {len(raw)} 超过上限 {max_line_len}"]})
            continue
        tokens = _tokenize(raw, plan)
        matched = _match_fields(plan.fields, tokens, raw, plan)
        if matched is None:
            item = {"line": lineno, "raw": raw[:200]}
            item.update(_diagnose(raw, plan))
            invalid.append(item)
            continue
        record, line_findings = matched
        record["_line"] = lineno
        records.append(record)
        for finding in line_findings:
            finding = dict(finding)
            finding["line"] = lineno
            findings.append(finding)
    ok = not invalid
    return {
        "ok": ok,
        "status": "ok" if ok else "partial",
        "plan": plan.name,
        "encoding": encoding,
        "records": records,
        "invalid": invalid,
        "findings": findings,
        "stats": {"lines": len(text.splitlines()), "records": len(records),
                  "invalid": len(invalid), "blank": blank, "findings": len(findings),
                  "longest_line": longest, "fields": [f.name for f in plan.fields]},
        "fingerprint": records_fingerprint(records),
    }


def parse_bytes(data: bytes, plan: Plan, *, preferred_encoding: str | None = None) -> dict:
    text, encoding, replaced = decode_bytes(data, preferred_encoding)
    out = parse_text(text, plan, encoding=encoding)
    out["decode"] = {"encoding": encoding, "replaced_chars": replaced}
    return out


def records_fingerprint(records: Sequence[dict]) -> str:
    canonical = json.dumps([{k: v for k, v in sorted(r.items())} for r in records],
                           ensure_ascii=False, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def _emit_field(spec: Field, record: dict) -> str:
    if spec.kind == "packed":
        left = record.get(spec.left) or []
        if isinstance(left, str):
            left = [left] if left else []
        right = record.get(spec.right) or ""
        if not left and not right:
            return ""
        return ",".join(str(v) for v in left) + "." + str(right)
    value = record.get(spec.name, "")
    if value is None:
        value = ""
    text = str(value)
    if spec.kind == "flex" and spec.marker and record.get(spec.name + "_flag"):
        text += spec.marker
    return text


def emit_records(records: Sequence[dict], plan: Plan) -> str:
    """记录 → 文本。空白分隔时按段拼接并去尾空格；字符分隔时严格按位输出。"""
    lines: list[str] = []
    for record in records:
        parts = [_emit_field(spec, record) for spec in plan.fields]
        if plan.sep is None:
            lines.append(" ".join(p for p in parts if p != "").rstrip())
        elif plan.quoted:
            buf = io.StringIO()
            csv.writer(buf, delimiter=plan.sep, lineterminator="").writerow(parts)
            lines.append(buf.getvalue())
        else:
            lines.append(plan.sep.join(parts))
    return "\n".join(lines) + ("\n" if lines else "")


def verify_roundtrip(text: str, plan: Plan) -> dict:
    """自证：parse → emit → parse，记录指纹必须一致（parse∘emit 幂等）。"""
    first = parse_text(text, plan)
    emitted = emit_records(first["records"], plan)
    second = parse_text(emitted, plan)
    same = first["fingerprint"] == second["fingerprint"]
    diff = None
    if not same:
        for a, b in zip(first["records"], second["records"]):
            if a != b:
                diff = {"expected": a, "actual": b}
                break
        if diff is None:
            diff = {"expected_records": len(first["records"]),
                    "actual_records": len(second["records"])}
    return {"ok": same, "idempotent": same, "records": len(first["records"]),
            "fingerprint": first["fingerprint"], "reparsed": second["fingerprint"],
            "invalid_first": len(first["invalid"]), "invalid_second": len(second["invalid"]),
            "first_difference": diff,
            "note": "幂等指的是记录层（字段值）一致；原始空白排版不做逐字节还原"}


def check_vocabulary(values: Iterable[str], allowed: Iterable[str]) -> dict:
    """受控词表校验：返回越界值（保留原值，不静默丢弃）。"""
    allow = {str(v) for v in allowed}
    items = [str(v) for v in values if str(v) != ""]
    outside = sorted({v for v in items if v not in allow})
    return {"ok": not outside, "checked": len(items), "vocab_size": len(allow),
            "outside": outside, "outside_ratio": round(len(outside) / max(1, len(items)), 4)}


# ── 结构发现（面对一个陌生文本，先看清它的骨架）─────────────────────────────

def _value_type(value: str) -> str:
    if value == "":
        return "empty"
    if _NUM_RE.match(value):
        return "number"
    if _SCHEME_RE.match(value):
        return "url"
    return "text"


def profile_text(text: str, *, max_lines: int = 800,
                 sep_candidates: Sequence[str] = ("\t", "|", ";", ","),
                 vocab_max_cardinality: int = 24) -> dict:
    """给陌生文本做结构画像：分隔方式、列数稳定性、每列类型、候选词表、表头与标记。"""
    all_lines = text.splitlines()
    rows = [line for line in all_lines if line.strip()][:max_lines]
    if not rows:
        return {"ok": False, "error": "文本为空或无有效行"}

    candidates = []
    for sep in list(sep_candidates) + [None]:
        counts = [len(_tokenize(row, Plan("probe", (), sep=sep))) for row in rows]
        mode, hits = Counter(counts).most_common(1)[0]
        candidates.append({
            "sep": "whitespace" if sep is None else sep,
            "sep_repr": "\\s+" if sep is None else repr(sep),
            "modal_fields": mode,
            "consistency": round(hits / len(counts), 4),
            "min_fields": min(counts),
            "max_fields": max(counts),
        })
    # 只保留真正能切出多列的候选：切不出分隔符的方案「一致性」必然虚高（恒为 1 列），
    # 那是退化结果而不是结构证据。多列候选里按「一致性 × 列数」打分。
    usable = [c for c in candidates if c["modal_fields"] >= 2]
    pool = usable or candidates
    pool.sort(key=lambda c: (round(c["consistency"] * min(c["modal_fields"], 12), 4),
                             c["modal_fields"]), reverse=True)
    candidates.sort(key=lambda c: (c["modal_fields"] >= 2, c["consistency"]), reverse=True)
    best = pool[0]
    best = dict(best, degraded=not usable)
    sep = None if best["sep"] == "whitespace" else best["sep"]
    probe = Plan("probe", (), sep=sep)
    token_rows = [_tokenize(row, probe) for row in rows]
    width = best["modal_fields"]
    aligned = [t for t in token_rows if len(t) == width]

    columns = []
    for index in range(width):
        values = [t[index][0] for t in aligned]
        types = Counter(_value_type(v) for v in values)
        distinct = sorted(set(values))
        col = {
            "index": index,
            "type_candidates": {k: v for k, v in types.most_common()},
            "distinct": len(distinct),
            "empty": types.get("empty", 0),
            "looks_like": types.most_common(1)[0][0],
        }
        dominant = types.most_common(1)[0][0]
        if dominant in ("number", "url"):
            col["suggested_kind"] = dominant
        elif 1 <= len(distinct) <= vocab_max_cardinality and len(distinct) < len(values):
            col["suggested_kind"] = "packed" if any("." in v for v in distinct) else "flex"
            col["vocabulary_candidate"] = distinct
        else:
            col["suggested_kind"] = "flex" if index < width - 1 else "tail"
        # URL 列天然带点（域名的点），不能当「多值.单值」组合字段——显式排除，
        # 否则画像会把 URL 误判成 packed，起草出的骨架凭空多出两列。
        dotted = ([] if dominant == "url"
                  else [v for v in values if v.count(".") == 1 and v.split(".")[0]])
        if dotted and len(dotted) >= max(1, int(0.6 * len(values))):
            lefts = [v.split(".", 1)[0] for v in dotted]
            rights = [v.split(".", 1)[1] for v in dotted]
            col["dotted_pair"] = True
            col["dotted_left_values"] = sorted(set(",".join(lefts).split(",")))
            col["dotted_left_multi"] = any("," in v for v in lefts)
            col["dotted_right_values"] = sorted(set(rights))
        markers = Counter(v[-1] for v in values
                          if v and v[-1] in MARKER_CHARS and len(v) > 1)
        if markers and markers.most_common(1)[0][1] >= max(2, int(0.08 * len(values))):
            col["trailing_marker"] = markers.most_common(1)[0][0]
        columns.append(col)

    header = {"likely": False, "basis": []}
    if len(aligned) >= 3:
        for index, col in enumerate(columns):
            head_type = _value_type(aligned[0][index][0])
            body = Counter(_value_type(t[index][0]) for t in aligned[1:])
            if body:
                dominant_body = body.most_common(1)[0][0]
                if head_type != dominant_body and dominant_body not in ("empty",):
                    header["basis"].append(
                        f"第 {index} 列：首行 {head_type}，其余多为 {dominant_body}")
        header["likely"] = bool(header["basis"])

    endings = Counter("\r\n" if line.endswith("\r") else "" for line in all_lines)
    return {
        "ok": True,
        "lines": {"total": len(all_lines), "non_blank": len([l for l in all_lines if l.strip()]),
                  "blank": len(all_lines) - len([l for l in all_lines if l.strip()]),
                  "sampled": len(rows)},
        "line_ending": "mixed" if len({k for k in endings if k}) > 1 else
                       ("crlf" if endings.get("\r\n") else "lf"),
        "candidates": candidates,
        "best": {"sep": best["sep"], "sep_repr": best["sep_repr"],
                 "modal_fields": width, "consistency": best["consistency"],
                 "aligned_rows": len(aligned)},
        "columns": columns,
        "header": header,
        "fingerprint": "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:32],
    }


def draft_plan(profile: dict, name: str = "draft") -> dict:
    """把画像翻成 plan 骨架（可交给 parse 直接用，词表留空由使用方填）。

    画像只是"从外表看到的样子"，不是真相：空白切分下变长字段会把后续列挤乱
    （实测：标题是单词的行会把标签列顶到第 4 列）。因此起草时做两件事——
    ① 变长行存在（max_fields > modal_fields 或一致性 < 1）就补一个 tail 收尾，
       保证「列数可变」这一事实被骨架显式容纳，而不是靠回溯硬猜；
    ② 把不确定项写进 warnings，让使用方知道哪儿需要人工确认。
    """
    if not profile.get("ok"):
        raise ValueError("profile 无效，无法起草 plan")
    fields = []
    warnings = []
    for col in profile["columns"]:
        index = col["index"]
        if col.get("dotted_pair"):
            fields.append({"name": f"col{index}_left", "kind": "packed",
                           "left": f"col{index}_tags", "right": f"col{index}_class",
                           "left_vocab": [], "right_vocab": [],
                           "left_multi": bool(col.get("dotted_left_multi"))})
            warnings.append(f"第 {index} 列疑似「多值.单值」组合字段，词表待人工确认")
        else:
            kind = col.get("suggested_kind", "flex")
            if kind == "packed":
                kind = "flex"
            fields.append({"name": f"col{index}", "kind": kind})
    best = profile.get("best", {})
    variable_width = (best.get("max_fields", 0) > best.get("modal_fields", 0)
                      or float(best.get("consistency", 1)) < 1.0
                      or best.get("degraded"))
    if fields and fields[-1]["kind"] != "tail" and variable_width:
        fields.append({"name": "remainder", "kind": "tail"})
        warnings.append("列宽不固定：已补 tail 字段承接变长尾部（自由文本）")
    if best.get("degraded"):
        warnings.append("未发现可靠分隔符：按空白切分，可能需要显式指定 sep")
    if best.get("consistency") is not None and float(best["consistency"]) < 0.8:
        warnings.append(f"列数一致性仅 {best['consistency']}：骨架仅为起点，需人工核对")
    if profile.get("header", {}).get("likely"):
        warnings.append("首行疑似表头，解析时应跳过或单独取出")
    return {"name": name,
            "sep": None if best.get("sep") in (None, "whitespace") else best["sep"],
            "fields": fields, "warnings": warnings,
            "based_on": {"modal_fields": best.get("modal_fields"),
                         "consistency": best.get("consistency"),
                         "sampled_lines": profile.get("lines", {}).get("sampled")}}


# ── 能力入口：run_op ───────────────────────────────────────────────────────

_HOME = Path(__file__).resolve().parent.parent


def _preset(name: str, vocab: dict | None = None) -> Plan:
    if name not in PLAN_PRESETS:
        raise ValueError(f"未知 plan 预置: {name}；已注册 {sorted(PLAN_PRESETS)}")
    plan = PLAN_PRESETS[name]
    if not vocab:
        return plan
    fields = []
    for spec in plan.fields:
        if spec.kind == "packed":
            fields.append(dataclasses.replace(
                spec,
                left_vocab=frozenset(vocab.get(spec.left, spec.left_vocab)),
                right_vocab=frozenset(vocab.get(spec.right, spec.right_vocab)),
            ))
        else:
            fields.append(spec)
    return dataclasses.replace(plan, fields=tuple(fields))


def _resolve_plan(payload: dict) -> Plan:
    if payload.get("plan"):
        return Plan.from_dict(dict(payload["plan"]))
    return _preset(str(payload.get("plan_name") or "link_index"), payload.get("vocab"))


def _read_input(payload: dict) -> tuple[str, dict]:
    if payload.get("text") is not None:
        return str(payload["text"]), {"source": "inline", "bytes": len(str(payload["text"]).encode("utf-8"))}
    path = payload.get("path")
    if not path:
        raise ValueError("需要 text（内联文本）或 path（框架内相对路径）")
    from .safe_io import safe_relative_path
    target = safe_relative_path(_HOME, str(path))
    if not target.is_file():
        raise ValueError(f"文件不存在: {path}")
    data = target.read_bytes()
    text, encoding, replaced = decode_bytes(data, payload.get("encoding"))
    return text, {"source": "path", "path": str(target.relative_to(_HOME)),
                  "bytes": len(data), "encoding": encoding, "replaced_chars": replaced}


def run_op(op: str, payload: dict | None = None) -> dict:
    """统一能力入口：profile / parse / emit / verify / vocab / draft / presets。"""
    p = dict(payload or {})
    op = (op or "profile").lower()
    from .store import audit

    if op == "presets":
        return {"ok": True, "presets": {k: v.to_dict() for k, v in PLAN_PRESETS.items()},
                "note": "预置是格式语法；词表请按语料用 vocab 覆盖"}

    if op in ("profile", "draft"):
        text, source = _read_input(p)
        profile = profile_text(text, max_lines=int(p.get("max_lines", 800)))
        if op == "profile":
            audit("record_grid", {"op": "profile", "source": source.get("source"),
                                  "lines": profile.get("lines", {}).get("total")})
            return {"ok": True, "profile": profile, "source": source}
        drafted = draft_plan(profile, str(p.get("plan_name") or "draft"))
        audit("record_grid", {"op": "draft", "columns": len(drafted["fields"])})
        return {"ok": True, "plan": drafted, "profile": profile, "source": source}

    if op == "parse":
        plan = _resolve_plan(p)
        text, source = _read_input(p)
        result = parse_text(text, plan, encoding=source.get("encoding") or "utf-8")
        result["source"] = source
        audit("record_grid", {"op": "parse", "plan": plan.name,
                              "records": len(result["records"]),
                              "invalid": len(result["invalid"])})
        return result

    if op == "verify":
        plan = _resolve_plan(p)
        text, source = _read_input(p)
        result = verify_roundtrip(text, plan)
        result["source"] = source
        result["plan"] = plan.name
        audit("record_grid", {"op": "verify", "plan": plan.name, "ok": result["ok"]})
        return result

    if op == "emit":
        plan = _resolve_plan(p)
        records = p.get("records")
        if not isinstance(records, list) or not records:
            raise ValueError("emit 需要 records（记录列表）")
        text = emit_records(records, plan)
        out = {"ok": True, "plan": plan.name, "text": text,
               "bytes": len(text.encode("utf-8")),
               "lines": len([l for l in text.splitlines() if l.strip()])}
        target = p.get("out")
        if target:
            from . import _paths
            from .safe_io import atomic_write_text, safe_relative_path
            root = _paths.STORE_DIR / "record_grid"
            dest = safe_relative_path(root, str(target))
            atomic_write_text(dest, text)
            out["written"] = str(dest)
            audit("record_grid", {"op": "emit", "plan": plan.name, "out": str(dest.name)})
        return out

    if op == "vocab":
        values = p.get("values")
        if values is None and p.get("text"):
            text, _src = _read_input(p)
            sep = p.get("sep")
            values = [v.strip() for v in text.replace(sep or "\n", "\n").split("\n") if v.strip()]
        if not isinstance(values, (list, tuple)):
            raise ValueError("vocab 需要 values（列表）或 text + sep")
        allowed = p.get("allowed") or p.get("vocab") or []
        return check_vocabulary([str(v) for v in values], allowed)

    raise ValueError(f"未知 op: {op}；可选 profile/draft/parse/verify/emit/vocab/presets")


OPS: tuple[str, ...] = ("presets", "profile", "draft", "parse", "verify", "emit", "vocab")
