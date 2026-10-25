# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 自进化知识库（knowledge_base）

Owner 2026-09-22 定调：
    「设计一个自己的知识库，记录大模型的技术输出来提升自己、进化自己、
      衍生出自己的输出方式方向，自我能源补给，自主输出，动脑输出。」

═══ 四个词对四个动作 ═══
    记录大模型的技术输出   -> deposit()      原样落盘，带全溯源
    提升自己 / 进化自己    -> digest()       从原始输出里抽出可复用技术要点
    衍生自己的输出方式方向 -> derive_voice()  按**实测统计**归纳我们自己的写法
    自我能源补给           -> energy()      只数磁盘上真实条目，不数计数器
    自主输出 / 动脑输出    -> pulse()       一步跑完上面四步（供万能插脉冲调用）

═══ 反假执行四条（本模块的底线）═══
  1. **无溯源不收**：deposit() 缺 source 或 text 一律拒收并说明缺什么。
     宁可不收，也不编一条空记录充数。
  2. **不许假成功**：digest() 一条也抽不出时返回 digested=0 + reason，
     不是 {"ok": True} 糊过去。
  3. **能源不注水**：energy() 读的是磁盘上真实文件数，不是内存里的累加变量。
  4. **失败要能追**：pulse() 沿用 devour_pulse() 2026-09-22 的修法，
     哪一段挂了写进 stage_errors，不许和「真的没有」长得一样。

═══ 门纪律 ═══
  本模块是**纯库**，不自己开 run_task kind，因此不新增未登记的能力面。
  它由已授权的 `devour_pulse` 链路调用（security/policy.py:271 已有正式门：
  data_export + filesystem_write + external_llm）。
  写 store 前按 _paths.verify_store_binding()（O53 甲案）先验绑定。
"""
from __future__ import annotations

import hashlib
import inspect
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from ._paths import STORE_DIR, verify_store_binding

KB_ROOT: Path = STORE_DIR / "knowledge"

_IMPL_VERSION = "1.0"

# 哪些字段算「溯源」。缺 source 就没法回答"这条知识哪来的"，直接拒收。
_REQUIRED = ("source", "text")

# ═══════════════════ 准入：只能是我们的资料（Owner 2026-09-22 定）═══════════════════
# Owner 原话：「必须确保只能是你的资料不能混入其他资料」。
#
# 判据：**白名单，默认拒**（不是黑名单）—— 名单外的一律进不来，
#       包括今天想得到和想不到的来源。黑名单只能挡住已经知道的东西。
#
# 谁算「我们」：产出**发生在我们自己框架里**的那些。
#   codex        —— 本框架 codex_bridge 跑出来的回合（Owner 要记的「大模型技术输出」）
#   gbt          —— 框架自身产出的结论/报告
#   gbt_allinone —— 框架模块直接投递
#   owner        —— 主人本人的输入
SOURCE_ALLOWLIST = ("codex", "gbt", "gbt_allinone", "owner")

# 明确**不属于我们**、绝不许进知识库的（用来给出人话的拒收理由，不是唯一防线）。
FOREIGN_SOURCES = ("devour", "devour_github", "github", "external", "foreign",
                   "platform", "web", "crawl", "scrape", "unknown")

# 知识库是**独立**的一块，与外面那棵"吞进来的"树物理分开：
#   store/knowledge/  ← 本知识库（只放我们的）
#   store/devoured/   ← 吞噬吞进来的外部知识（别人的，另一棵树）
# 两者绝不互相读写 —— 见 verify_seal() 的跨树污染检查。
SEPARATE_FROM = ("devoured",)


# ═══════════════════════════ 目录骨架 ═══════════════════════════

def paths() -> dict:
    """知识库五个落点的单一来源。落点固定在 store 下，不散落。"""
    return {
        "root": KB_ROOT,
        "raw": KB_ROOT / "raw",
        "techniques": KB_ROOT / "techniques.jsonl",
        "voice": KB_ROOT / "own_voice.md",
        "energy": KB_ROOT / "energy.json",
        "index": KB_ROOT / "index.json",
        "rejected": KB_ROOT / "rejected.jsonl",
    }


def _caller() -> str:
    """谁把这条知识投进来的 —— **看出来的，不是被投递方自己说的**。

    为什么不用一个 admitted_by 参数：调用方想写什么就写什么，等于没有溯源。
    这里往上翻调用栈，找到第一个不在本文件里的帧，记它的 模块:函数:行号。
    这样"这条是谁投的"就有了独立于投递方的证据。
    """
    me = Path(__file__).name
    for fr in inspect.stack()[2:]:
        if Path(fr.filename).name != me:
            return f"{Path(fr.filename).name}:{fr.function}:{fr.lineno}"
    return "(未知调用方)"


def _source_kind(source: str) -> str:
    """把来源归类：ours / foreign。白名单默认拒。"""
    s = (source or "").strip().lower()
    for ok in SOURCE_ALLOWLIST:
        # 允许 codex / codex:xxx / codex-xxx 这类带后缀的写法，但前缀必须精确匹配整个词
        if s == ok or s.startswith(ok + ":") or s.startswith(ok + "-") or s.startswith(ok + " "):
            return "ours"
    return "foreign"


def _note_rejection(rec: dict, reason: str) -> None:
    """把被拒的投递记下来 —— 拒收也要留痕，否则'有人想混进来'这件事看不见。"""
    try:
        p = _ensure()["rejected"]
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "at": _now(), "reason": reason,
                "source": str(rec.get("source") or "")[:80],
                "caller": _caller(),
                "text_head": str(rec.get("text") or "")[:120],
            }, ensure_ascii=False) + "\n")
    except Exception:                                               # noqa: BLE001
        pass                      # 留痕失败不能反过来把拒收变成接收


def _ensure() -> dict:
    p = paths()
    for key in ("raw",):
        p[key].mkdir(parents=True, exist_ok=True)
    KB_ROOT.mkdir(parents=True, exist_ok=True)
    return p


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# ═══════════════════════════ 索引 ═══════════════════════════

def _load_index() -> dict:
    p = paths()["index"]
    if not p.is_file():
        return {"entries": {}, "digested": [], "version": _IMPL_VERSION}
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as e:                                          # noqa: BLE001
        # 索引坏了不能装作没事：如实带走原因，让调用方看见。
        return {"entries": {}, "digested": [], "version": _IMPL_VERSION,
                "index_error": f"{type(e).__name__}: {str(e)[:120]}"}
    data.setdefault("entries", {})
    data.setdefault("digested", [])
    return data


def _save_index(idx: dict) -> None:
    paths()["index"].write_text(
        json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")


# ═══════════════════════════ 一 · 记录（deposit）═══════════════════════════

def deposit(record: dict) -> dict:
    """把一段大模型技术输出原样收进知识库。

    拒收规则（宁可拒收，不编空记录）：
      - 不是 dict / 缺 source / 缺 text / text 去空白后为空  -> 直接拒
      - 同一内容（sha256 相同）已经在库                              -> 去重，不重复落盘
    """
    if not isinstance(record, dict):
        return {"ok": False, "refused": True, "reason": "record 必须是 dict",
                "missing": ["record"]}
    missing = [k for k in _REQUIRED if not str(record.get(k) or "").strip()]
    if missing:
        return {"ok": False, "refused": True,
                "reason": "缺溯源字段，" + " 与 ".join(missing) + " 为空 —— 无源不收",
                "missing": missing}

    # ── 准入闸（Owner：「只能是你的资料不能混入其他资料」）──
    # 白名单默认拒：名单外的一律不进。拒收也留痕。
    src_raw = str(record["source"]).strip()
    kind = _source_kind(src_raw)
    if kind != "ours":
        hit = [f for f in FOREIGN_SOURCES if f in src_raw.lower()]
        why = ("来源被识别为外部资料（" + "/".join(hit) + "）"
               if hit else "来源不在白名单里")
        reason = (f"拒收外来资料：source={src_raw[:40]!r} {why}；"
                  f"本知识库只收 {list(SOURCE_ALLOWLIST)} 产出的资料")
        _note_rejection(record, reason)
        return {"ok": False, "refused": True, "foreign": True,
                "reason": reason, "allowlist": list(SOURCE_ALLOWLIST)}

    caller = _caller()

    text = str(record["text"])
    source = src_raw
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()

    verify_store_binding()          # O53 甲案：写 store 前先验绑定
    p = _ensure()
    idx = _load_index()
    if sha in idx["entries"]:
        # 去重时**照样给 path**：不然调用方拿到的键时有时无
        # （插入有 path、去重只有 existing），是个坑 —— 实测已经被坑过一次。
        return {"ok": True, "deduped": True, "sha256": sha,
                "path": idx["entries"][sha]["path"],
                "existing": idx["entries"][sha]["path"],
                "note": "同内容已在库，不重复落盘（去重不是失败）"}

    ts = _now()
    ym = ts[:7]
    (p["raw"] / ym).mkdir(parents=True, exist_ok=True)
    fname = f"{ts.replace(':', '').replace('-', '')[:15]}-{source[:16]}-{sha[:8]}.json"
    fname = re.sub(r"[^0-9A-Za-z_.\u4e00-\u9fff-]", "_", fname)
    dst = p["raw"] / ym / fname

    body = {
        "sha256": sha,
        "source": source,
        "admitted_by": caller,        # 独立观测出来的投递方（不由投递方自报）
        "sealed": True,               # 已过准入闸，是我们自己的资料
        "model": str(record.get("model") or ""),
        "thread_id": str(record.get("thread_id") or ""),
        "turn_id": str(record.get("turn_id") or ""),
        "captured_at": ts,
        "chars": len(text),
        "text": text,
        "extra": {k: v for k, v in record.items()
                  if k not in ("text",) and k not in _REQUIRED},
    }
    dst.write_text(json.dumps(body, ensure_ascii=False, indent=1), encoding="utf-8")

    idx["entries"][sha] = {"path": dst.relative_to(KB_ROOT).as_posix(),
                           "source": source, "bytes": dst.stat().st_size,
                           "captured_at": ts, "admitted_by": caller}
    _save_index(idx)
    return {"ok": True, "deduped": False, "sha256": sha,
            "path": dst.relative_to(KB_ROOT).as_posix(),
            "bytes": dst.stat().st_size, "chars": len(text)}


# ═══════════════════════ 二 · 蒸馏技术要点（digest）═══════════════════════

_FENCE = re.compile(r"```([A-Za-z0-9_+-]*)\n(.*?)```", re.S)
_IDENT = re.compile(r"`([^`\n]{2,80})`")
_FILEREF = re.compile(r"([A-Za-z0-9_./\\-]+\.(?:py|js|ts|tsx|json|md|html|bat|ps1|yaml|yml|toml))(?::(\d+))?")
# 2026-09-22 放宽（实测教训）：原来只认**行首**命令，于是
# 「命令：py -3.14 -m gbt_allinone.cli status」这种**带中文标签**的写法一条都抽不到
# —— 而本仓报告里恰恰全是这种写法。改成「行首 或 冒号/空白之后」都认。
# 代价是会误抓散文（「用 git 提交」），所以下面再过一道 CJK 过滤把散文剔掉。
_CMD = re.compile(r"(?:^|[\s:：>])((?:py|python|pip|npm|pnpm|npx|git|pwsh|powershell|node|wrangler|tripo)\s+[^\n]{2,120})", re.M)
_CJK = re.compile(r"[\u4e00-\u9fff]")


def _extract_signals(text: str) -> dict:
    """从原始输出里抽**可核对的**信号。

    说清楚这里做什么、不做什么：
      做   —— 抽出代码块、被反引号包住的标识符、文件名:行号、命令行。这些是**字面量**，
              抽出来能回去原文逐字对上，不掺解释。
      不做 —— 不假装做语义总结。语义归纳留给 derive_voice() 用**统计**说话。
    """
    fences = [{"lang": (m.group(1) or "").strip(), "chars": len(m.group(2))}
              for m in _FENCE.finditer(text)]
    idents = sorted({m.group(1).strip() for m in _IDENT.finditer(text)})
    files = sorted({(m.group(1), m.group(2) or "") for m in _FILEREF.finditer(text)})
    cmds = set()
    for m in _CMD.finditer(text):
        c = m.group(1).strip().rstrip("。，,;；")
        parts = c.split()
        # 第一个参数带中文 = 散文（「用 git 提交」），不是命令行，剔掉。
        if len(parts) > 1 and _CJK.search(parts[1]):
            continue
        cmds.add(c)
    return {
        "code_blocks": len(fences),
        "code_langs": sorted({f["lang"] for f in fences if f["lang"]}),
        "identifiers": idents[:80],
        "files": [f"{a}:{b}" if b else a for a, b in files][:80],
        "commands": sorted(cmds)[:40],
        "extractor": "literal-only v1.1（字面量抽取，不做语义总结）",
    }


def digest(force: bool = False) -> dict:
    """把还没蒸馏过的原始条目抽出技术要点，追加进 techniques.jsonl。

    返回 digested 与 skipped；一条也没蒸出来时给 reason，不给假 ok。
    """
    verify_store_binding()
    p = _ensure()
    idx = _load_index()
    done = set(idx.get("digested") or [])
    todo = [s for s in idx["entries"] if force or s not in done]

    if not todo:
        reason = ("库里还没有任何原始条目" if not idx["entries"]
                  else "所有条目都已蒸馏过（force=True 可重蒸）")
        return {"digested": 0, "skipped": len(idx["entries"]), "reason": reason,
                "ok": False, "reason_kind": "nothing_to_do"}

    written, errors = 0, {}
    with p["techniques"].open("a", encoding="utf-8") as fh:
        for sha in todo:
            meta = idx["entries"][sha]
            src = KB_ROOT / meta["path"]
            try:
                rec = json.loads(src.read_text(encoding="utf-8-sig"))
                sig = _extract_signals(rec.get("text", ""))
                row = {"at": _now(), "sha256": sha, "source": rec.get("source", ""),
                       "model": rec.get("model", ""), "chars": rec.get("chars", 0),
                       **sig}
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                written += 1
            except Exception as e:                                  # noqa: BLE001
                errors[sha[:12]] = f"{type(e).__name__}: {str(e)[:120]}"
    if written:
        idx["digested"] = sorted(done | {s for s in todo if s[:12] not in errors})
        _save_index(idx)
    return {"digested": written, "skipped": len(idx["entries"]) - written,
            "stage_errors": errors, "ok": written > 0,
            "reason": "" if written else "全部条目抽取失败，见 stage_errors"}


# ═══════════════════ 三 · 衍生自己的输出方式（derive_voice）═══════════════

def _read_techniques() -> list:
    p = paths()["techniques"]
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except Exception:                                       # noqa: BLE001
                continue
    return out


def derive_voice(min_samples: int = 3) -> dict:
    """按**实测统计**归纳我们自己的输出方式，写 own_voice.md。

    纪律：样本不够就**明说样本不够**，不硬凑一份"风格"出来。
    每一条结论后面都挂样本数，让它可证伪。
    """
    verify_store_binding()
    rows = _read_techniques()
    if len(rows) < min_samples:
        res = {"ok": False, "samples": len(rows), "min_samples": min_samples,
               "reason": f"技术要点只有 {len(rows)} 条，不足 {min_samples} 条，"
                         f"样本不够就不归纳 —— 不硬凑风格"}
        if not paths()["voice"].is_file():
            return res
        return res

    langs, idents, files, cmds = {}, {}, {}, {}
    for r in rows:
        for l in r.get("code_langs") or []:
            langs[l] = langs.get(l, 0) + 1
        for i in r.get("identifiers") or []:
            idents[i] = idents.get(i, 0) + 1
        for f in r.get("files") or []:
            files[f] = files.get(f, 0) + 1
        for c in r.get("commands") or []:
            head = c.split()[0] if c.split() else c
            cmds[head] = cmds.get(head, 0) + 1

    top = lambda d, n=10: sorted(d.items(), key=lambda kv: -kv[1])[:n]   # noqa: E731
    n = len(rows)
    lines = [
        "# 我们自己的输出方式（由实测统计归纳 · 不是许愿）",
        "",
        "> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属",
        "",
        f"- 归纳时间：{_now()}",
        f"- 样本：**{n}** 条技术要点（来自知识库 `techniques.jsonl`）",
        f"- 归纳方式：**数出来的**，每条结论后挂样本数；样本不足 {min_samples} 条时不归纳",
        "",
        "## 一 · 我们实际在用什么语言写代码块",
        "",
    ]
    lines += [f"- `{k or '(无标注)'}` × {v}" for k, v in top(langs)] or ["- （样本里没有代码块）"]
    lines += ["", "## 二 · 我们反复引用的标识符（说明我们的词汇表）", ""]
    lines += [f"- `{k}` × {v}" for k, v in top(idents, 20)] or ["- （无）"]
    lines += ["", "## 三 · 我们反复处理的文件（说明我们的战场在哪）", ""]
    lines += [f"- `{k}` × {v}" for k, v in top(files, 20)] or ["- （无）"]
    lines += ["", "## 四 · 我们实际敲的命令（说明我们的手法）", ""]
    lines += [f"- `{k}` × {v}" for k, v in top(cmds, 15)] or ["- （无）"]
    lines += [
        "",
        "## 五 · 这份文件怎么用",
        "",
        "下次要产出东西（报告 / 代码 / 交付件）时，**按上面统计出来的习惯写**：",
        "常用语言优先、词汇表里的词优先、动手方式优先用数出来的那几种。",
        "统计变了就重跑 `knowledge_base.derive_voice()` 覆盖本文件 —— 它是**推论**，不是圣旨。",
        "",
    ]
    paths()["voice"].write_text("\n".join(lines), encoding="utf-8")
    return {"ok": True, "samples": n, "path": "own_voice.md",
            "top_langs": top(langs, 5), "top_idents": top(idents, 5),
            "bytes": paths()["voice"].stat().st_size}


# ═══════════════════════ 四 · 自我能源补给（energy）═══════════════════════

def energy() -> dict:
    """能源 = 磁盘上真实存在的知识量。不读内存计数器，所以注不了水。"""
    p = paths()
    raw_files = list(p["raw"].rglob("*.json")) if p["raw"].is_dir() else []
    raw_bytes = sum(f.stat().st_size for f in raw_files)
    tech_lines = 0
    if p["techniques"].is_file():
        tech_lines = sum(1 for l in p["techniques"].read_text(
            encoding="utf-8-sig").splitlines() if l.strip())
    idx = _load_index()
    return {
        "raw_entries": len(raw_files),
        "raw_bytes": raw_bytes,
        "techniques": tech_lines,
        # 补给量：一个原始条目 + 一条要点 = 2 格电。纯计数，可复核。
        "energy_units": len(raw_files) + tech_lines,
        "has_own_voice": p["voice"].is_file(),
        "voice_bytes": p["voice"].stat().st_size if p["voice"].is_file() else 0,
        "dedup_index": len(idx.get("entries") or {}),
        "index_error": idx.get("index_error", ""),
        "note": ("能源来自磁盘实际文件数 —— 空库必然是 0，注不了水"
                 if len(raw_files) == 0 else
                 f"{len(raw_files)} 条原始 + {tech_lines} 条要点"),
    }


# ═══════════════════════ 五 · 脉冲（pulse）═══════════════════════════════

def pulse() -> dict:
    """自主输出 / 动脑输出：一步跑完 蒸馏 -> 衍生自己的输出方式 -> 数能源。

    哪一段挂了写进 stage_errors（沿用 devour_pulse 2026-09-22 的修法）。
    """
    stage_errors: dict = {}
    try:
        d = digest()
    except Exception as e:                                          # noqa: BLE001
        d = {"digested": 0, "reason": "digest 抛异常"}
        stage_errors["digest"] = f"{type(e).__name__}: {str(e)[:120]}"
    try:
        v = derive_voice()
    except Exception as e:                                          # noqa: BLE001
        v = {"ok": False, "reason": "derive_voice 抛异常"}
        stage_errors["derive_voice"] = f"{type(e).__name__}: {str(e)[:120]}"
    try:
        en = energy()
    except Exception as e:                                          # noqa: BLE001
        en = {"energy_units": 0}
        stage_errors["energy"] = f"{type(e).__name__}: {str(e)[:120]}"
    try:
        seal = verify_seal()
    except Exception as e:                                          # noqa: BLE001
        seal = {"sealed": False, "checked": 0, "violations": [],
                "note": "verify_seal 抛异常"}
        stage_errors["verify_seal"] = f"{type(e).__name__}: {str(e)[:120]}"
    if not seal.get("sealed", False):
        # 库被污染 = 这一轮的产出不可信，必须显式报出来，不许当没事
        stage_errors.setdefault(
            "seal", "库里混入了外来资料或溯源不全：" +
                    str(seal.get("violations", [])[:3])[:160])

    # ok        = 没崩（哪段挂了在 stage_errors 里）
    # productive= **真的往前走了吗**（蒸出新要点 或 归纳出输出方式）
    # 两个分开报：空转一轮不许长得像有产出 —— 这是反假执行。
    productive = bool(d.get("digested")) or bool(v.get("ok"))
    return {
        "ok": not stage_errors,
        "productive": productive,
        "version": _IMPL_VERSION,
        "stages": {
            "digest": {"digested": d.get("digested", 0),
                       "reason": d.get("reason", "")},
            "derive_voice": {"ok": v.get("ok", False),
                             "samples": v.get("samples", 0),
                             "reason": v.get("reason", "")},
            "energy": en,
            "seal": {"sealed": seal.get("sealed"), "checked": seal.get("checked"),
                     "foreign_rejected": seal.get("foreign_rejected")},
        },
        "stage_errors": stage_errors,
        "stages_degraded": sorted(stage_errors),
        "note": ("" if productive else
                 "本轮没有新增：既没蒸出新要点，也没归纳出输出方式 —— "
                 "不是失败，但也不是产出，如实报空转"),
        "at": _now(),
    }


# ═══════════════════ 七 · 封印审计（verify_seal）════════════════════════

def verify_seal() -> dict:
    """审计整库：证明「里面只有我们的资料」。

    不是喊口号，是**逐条验**：
      1. 每条 raw 的 source 必须在白名单里 —— 名单外即为侵入
      2. 每条 raw 必须有 admitted_by（独立观测到的投递方），没有 = 溯源不完整
      3. 每条 raw 的 sealed 必须为 True
      4. 跨树污染：知识库目录里不许出现任何"吞进来的"那棵树的路径
         （store/devoured/ 装的是别人家的知识，绝不能混进来）

    返回 sealed=True 才叫"确保"；找到任何一条违规就 sealed=False 并把证据列出来。
    """
    p = paths()
    violations: list = []
    checked = 0
    raw_files = sorted(p["raw"].rglob("*.json")) if p["raw"].is_dir() else []
    for f in raw_files:
        checked += 1
        rel = f.relative_to(KB_ROOT).as_posix()
        try:
            rec = json.loads(f.read_text(encoding="utf-8-sig"))
        except Exception as e:                                      # noqa: BLE001
            violations.append({"path": rel, "why": f"读不出来: {type(e).__name__}"})
            continue
        src = str(rec.get("source") or "")
        if _source_kind(src) != "ours":
            violations.append({"path": rel, "why": f"外来资料来源: {src[:60]!r}"})
        if not str(rec.get("admitted_by") or "").strip():
            violations.append({"path": rel, "why": "缺 admitted_by，溯源不完整"})
        if rec.get("sealed") is not True:
            violations.append({"path": rel, "why": "sealed 不是 True"})

    # 跨树污染：知识库根下出现被隔离的那棵树的名字
    cross = []
    if KB_ROOT.is_dir():
        for f in KB_ROOT.rglob("*"):
            parts = set(f.relative_to(KB_ROOT).parts)
            for bad in SEPARATE_FROM:
                if bad in parts:
                    cross.append(f.relative_to(KB_ROOT).as_posix())
    if cross:
        violations.append({"path": "(跨树)", "why":
                           f"知识库里出现了 {list(SEPARATE_FROM)} 的东西: {cross[:5]}"})

    # 被拒的外来投递次数（拒收留痕，证明闸门真的在工作）
    rej = 0
    if p["rejected"].is_file():
        rej = sum(1 for l in p["rejected"].read_text(
            encoding="utf-8-sig").splitlines() if l.strip())

    return {
        "sealed": not violations,
        "checked": checked,
        "violations": violations,
        "foreign_rejected": rej,
        "allowlist": list(SOURCE_ALLOWLIST),
        "separate_from": list(SEPARATE_FROM),
        "note": ("全库 " + str(checked) + " 条，全是我们的资料，无外来混入"
                 if not violations else
                 "发现 " + str(len(violations)) + " 条违规 —— 库不干净"),
    }


# ═══════════════════════ 八 · 回忆（recall）═══════════════════════════════

def recall(query: str, limit: int = 10) -> dict:
    """按关键词回查知识库（要点优先，其次原始条目）。"""
    q = (query or "").strip()
    if not q:
        return {"ok": False, "reason": "query 为空"}
    ql = q.lower()
    hits = []
    for r in _read_techniques():
        blob = json.dumps(r, ensure_ascii=False).lower()
        if ql in blob:
            hits.append({"kind": "technique", "sha256": r.get("sha256", ""),
                         "source": r.get("source", ""), "at": r.get("at", "")})
        if len(hits) >= limit:
            break
    if len(hits) < limit:
        p = paths()["raw"]
        idx = _load_index()
        for sha, meta in (idx.get("entries") or {}).items():
            f = KB_ROOT / meta["path"]
            if not f.is_file():
                continue
            try:
                if ql in f.read_text(encoding="utf-8-sig").lower():
                    hits.append({"kind": "raw", "sha256": sha,
                                 "source": meta.get("source", ""),
                                 "at": meta.get("captured_at", "")})
            except Exception:                                       # noqa: BLE001
                continue
            if len(hits) >= limit:
                break
    return {"ok": True, "query": q, "count": len(hits), "hits": hits[:limit]}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    out = {"status": energy, "digest": digest, "voice": derive_voice,
           "pulse": pulse}.get(cmd)
    if out is None:
        print(json.dumps({"error": f"未知命令 {cmd}",
                          "可用": ["status", "digest", "voice", "pulse"]},
                         ensure_ascii=False, indent=2))
        raise SystemExit(2)
    print(json.dumps(out(), ensure_ascii=False, indent=2))
