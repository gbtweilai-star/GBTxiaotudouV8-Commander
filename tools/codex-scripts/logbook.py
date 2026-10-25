# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 记录本（logbook）—— 「重启之后不许失忆」的那一本。

## 为什么要这件

主人令（2026-10-07，逐字）：
    「给她设计一个记录本，不管做什么都要在里面有记录，防止重启之后大模型不知道，
      比如每天扫描扫过哪里、修改过哪里、新增了哪里，全部都要有记录。」

这句话要的是**跨重启的事实连续性**：大模型每换一轮上下文/每重启一次，
上一轮"做过什么、动过哪些文件"就没了。人靠记忆，模型只能靠**落盘且可复核**的东西。

所以这本记录本钉三件事：
  ① **只追加**（append-only）：写完的行不许改；改动只能靠新写一条记录说明；
  ② **自链哈希**（prev_hash → hash）：任何一行被偷偷改过，`verify` 当场报出**第几行断链**；
  ③ **每日扫描**：把"扫了哪里、改了什么、新增了什么、删了什么"算出来写进本子 —— 
     不是让人自己回忆，是**用文件指纹现算**。

## 与仓里既有账本的关系（不许重复造）

`gbt_allinone` 那套审计账本记的是**能力位调用**（谁调了哪个 op、批没批）。
本记录本记的是**工程事实的变迁**（文件级扫描）+ **工程动作**（append 的人/模型手记）。
两者不重叠：一个管"动作合不合规"，一个管"工程变成了什么样"。

## 说法（口径纪律）

- 数字一律**现算**：扫描数与差值来自 `state/logbook-snapshot.json` 与真盘对比；
- **首扫无旧基线 ⇒ 明说"建基线"**，不假装"今天改了 12000 个文件"；
- 触顶（超过 `--max-files`）⇒ 记录里带 `max_files_hit: true`，**不许静默截断**；
- 页面数据是**产物**：由 `render` 覆盖，页首写着生成时刻与重生成命令。

## 用法

    py -3.14 tools/codex-scripts/logbook.py append --kind change --what "…" [--where 路径]… [--actor 谁]
    py -3.14 tools/codex-scripts/logbook.py scan [--label 每日扫描]
    py -3.14 tools/codex-scripts/logbook.py show [-n 20]
    py -3.14 tools/codex-scripts/logbook.py verify
    py -3.14 tools/codex-scripts/logbook.py render
    py -3.14 tools/codex-scripts/logbook.py check

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
STATE = ROOT / "state"
LOG = STATE / "logbook.jsonl"
SNAP = STATE / "logbook-snapshot.json"
DIGEST = STATE / "logbook-digest.md"
PAGE_DIR = ROOT / "holo_pet_w3" / "logbook"
DATA_JS = PAGE_DIR / "logbook-data.js"

GENESIS = "genesis"
KINDS = ("scan", "change", "decision", "deliver", "note")
SAMPLE_LIMIT = 40        # 每条记录里每类最多带多少条样路径（全量在快照里，不塞进日志）
TZ = timezone(timedelta(hours=8))   # 本机时区（北京时间）——读数与人对得上

# 目录级排除：这些树**不是工程事实**（依赖缓存 / 版本库内部 / 回收站 / 触手截图）
EXCLUDE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    ".backups", "_archive", ".shadow-repo", ".openclaw", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".next", ".turbo", ".cache", "frames",
    "$RECYCLE.BIN", ".idea", ".vscode", ".zcode",
    # 2026-10-08 加：**安全钩子自己的状态目录**。实测：它一次基线快照就往仓里塞
    # 5005 个文件（`hook-state/<会话>/….baseline/<sha>.source`）⇒ 扫描账目被工具噪声淹掉，
    # 真改动（24 个）反而要在一堆哈希文件名里找。它**不是工程事实**，与 node_modules 同类，
    # 故排除。口径：**排除的是工具状态，不是"不好看的改动"** —— 真丢了工程件这里照样报。
    ".mimosa",
    ".codex", ".claude", ".cursor", ".aider",
}


# ────────────────────────────── 基础 ──────────────────────────────
def now_iso() -> str:
    return datetime.now(TZ).replace(microsecond=0).isoformat()


def canon(obj) -> str:
    """规范化 JSON —— 链上的哈希必须**只跟内容有关**，不许跟键序/空格有关。"""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def chain_hash(prev_hash: str, payload: dict) -> str:
    return "sha256:" + hashlib.sha256((prev_hash + "|" + canon(payload)).encode("utf-8")).hexdigest()


def read_records() -> list:
    if not LOG.exists():
        return []
    out = []
    for i, line in enumerate(LOG.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception as exc:                                      # noqa: BLE001
            out.append({"_bad_line": i, "_why": str(exc), "_raw": line[:200]})
    return out


def verify_chain(records: list | None = None) -> tuple:
    """逐行重算链。返回 `(ok, bad_n, why)` —— 断在哪一行、为什么，说清楚。"""
    recs = read_records() if records is None else records
    prev = GENESIS
    for idx, rec in enumerate(recs, 1):
        if "_bad_line" in rec:
            return False, rec["_bad_line"], "第 %d 行不是合法 JSON：%s" % (rec["_bad_line"], rec["_why"])
        if rec.get("prev_hash") != prev:
            return False, idx, "第 %d 行的 prev_hash 与上一行的 hash 不接（被改过或被插过行）" % idx
        payload = {k: v for k, v in rec.items() if k != "hash"}
        want = chain_hash(prev, payload)
        if rec.get("hash") != want:
            return False, idx, "第 %d 行内容与哈希不符（该行被改过）：实得 %s，应为 %s" % (
                idx, str(rec.get("hash"))[:22], want[:22])
        prev = rec["hash"]
    return True, 0, "链自洽：%d 条记录，末条 hash=%s" % (len(recs), prev[:22])


def append_record(kind: str, what: str, where: list, actor: str, evidence: dict | None = None) -> dict:
    """唯一的写入口 —— 链在这里续上，谁都不许在别处直接往 jsonl 里写。"""
    if kind not in KINDS:
        raise SystemExit("kind 必须是 %s 之一，收到 %r" % ("/".join(KINDS), kind))
    if not str(what).strip():
        raise SystemExit("what 不许为空 —— 一条不知道干了什么的记录等于没记")
    recs = read_records()
    prev = recs[-1]["hash"] if recs and "hash" in recs[-1] else GENESIS
    payload = {
        "n": len(recs) + 1,
        "ts": now_iso(),
        "kind": kind,
        "actor": actor or "unknown",
        "what": str(what).strip(),
        "where": [str(w) for w in (where or [])] or ["(未点名)"],
    }
    if evidence:
        payload["evidence"] = evidence
    payload["prev_hash"] = prev
    payload["hash"] = chain_hash(prev, payload)
    STATE.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(canon_log_line(payload) + "\n")
    return payload


def canon_log_line(rec: dict) -> str:
    """落盘形态：**不排序**（人读的时候字段顺序要顺），但哈希是对排序后的 canon 算的。

    ⚠️ 这一条是坑：`verify` 必须**从盘上读回来的对象**重算（json.loads 之后再 canon），
    所以键序在这条路径上不影响判定。当初若拿"写下去的字符串"去验，就会一改字段顺序全红。
    """
    return json.dumps(rec, ensure_ascii=False)


# ────────────────────────────── 扫描 ──────────────────────────────
def iter_files(root: Path, max_files: int) -> tuple:
    """走一遍真盘，返回 `({相对路径: [size, mtime_ns]}, 是否触顶)`。"""
    out = {}
    hit = False
    stack = [root]
    while stack:
        cur = stack.pop()
        try:
            entries = list(os.scandir(cur))
        except (PermissionError, OSError):
            continue                      # 读不了就跳过（并在下面按"没扫到"如实处理）
        for e in entries:
            try:
                if e.is_dir(follow_symlinks=False):
                    if e.name in EXCLUDE_DIRS:
                        continue
                    stack.append(Path(e.path))
                elif e.is_file(follow_symlinks=False):
                    st = e.stat(follow_symlinks=False)
                    out[str(Path(e.path).relative_to(root)).replace("\\", "/")] = [st.st_size, st.st_mtime_ns]
                    if len(out) >= max_files:
                        hit = True
                        return out, hit
            except OSError:
                continue
    return out, hit


def cmd_scan(args) -> int:
    new, hit = iter_files(ROOT, args.max_files)
    old = {}
    prev_at = None
    if SNAP.exists():
        try:
            snap = json.loads(SNAP.read_text(encoding="utf-8"))
            old = {k: list(v) for k, v in (snap.get("files") or {}).items()}
            prev_at = snap.get("at")
            prev_excl = set(snap.get("exclude") or [])
        except Exception:                                             # noqa: BLE001
            old, prev_at, prev_excl = {}, None, set()   # 快照坏了 ⇒ 按首扫处理（下面会明说是建基线）

    added = sorted(set(new) - set(old))
    deleted = sorted(set(old) - set(new))
    modified = sorted(k for k in (set(new) & set(old)) if new[k] != old[k])

    # 🔴 2026-10-08 修的真缺陷（我自己撞出来的）：**改了排除集，下一次扫描会报出巨量「删除」** ——
    # 实测：把工具状态目录 .mimosa（87,361 个文件 / 1.1 GB）排除后，复扫报「删除 91355」。
    # 那不是真删了 9 万个工程件，是**基线口径变了**。一条会报假红的账目比没有账目更坏
    # （下一个人会去追这 9 万个「删除」）。⇒ 规矩：**排除集一变就按「重建基线」记**，不报增删改。
    excl_changed = bool(old) and set(prev_excl) != set(EXCLUDE_DIRS)
    baseline_reason = None
    if prev_at is None:
        baseline_reason = "第一次扫描，没有旧快照可比"
    elif excl_changed:
        baseline_reason = ("**排除集变更**（上次 %d 条 / 本次 %d 条）⇒ 基线重建，本次不报增删改"
                           % (len(prev_excl), len(EXCLUDE_DIRS)))

    if baseline_reason:
        what = "%s：**建基线**（%s）—— 现盘 %d 个文件已记成基线" % (args.label, baseline_reason, len(new))
    else:
        what = ("%s：扫 %d 个文件 · 未变 %d · 改动 %d · 新增 %d · 删除 %d"
                % (args.label, len(new), len(new) - len(added) - len(modified),
                   len(modified), len(added), len(deleted)))

    evidence = {
        "label": args.label,
        "roots": ["."],
        "scanned": len(new),
        "unchanged": len(new) - len(added) - len(modified),
        "modified": len(modified),
        "added": len(added),
        "deleted": len(deleted),
        "max_files_hit": bool(hit),
        "max_files": args.max_files,
        "baseline": bool(baseline_reason),
        "baseline_reason": baseline_reason,
        "prev_snapshot_at": prev_at,
        "basis": "state/logbook-snapshot.json（文件指纹 size+mtime_ns）",
        "exclude_dirs": sorted(EXCLUDE_DIRS),
        "samples": {
            "added": added[:SAMPLE_LIMIT],
            "modified": modified[:SAMPLE_LIMIT],
            "deleted": deleted[:SAMPLE_LIMIT],
        },
    }
    if hit:
        what += ("（**注意：文件数触顶 %d，本次扫描被截断** —— 不是「就只有这些」）"
                 % args.max_files)
    rec = append_record("scan", what, ["."], "logbook.py scan", evidence)

    STATE.mkdir(parents=True, exist_ok=True)
    SNAP.write_text(json.dumps({"at": rec["ts"], "count": len(new), "files": new,
                                "exclude": sorted(EXCLUDE_DIRS)},
                               ensure_ascii=False), encoding="utf-8")
    print("=" * 78)
    print("记录本 · 扫描")
    print("=" * 78)
    print("  " + what)
    print("  快照 → %s（%d 个文件）" % (SNAP, len(new)))
    if baseline_reason:
        # 基线档（首扫 / 排除集变更）：此刻"新增"会是全盘十几万条 —— 那是**基线口径**，
        # 不是"今天新增了十几万个"。所以这一档**不列改动**，只列几条样例说明记的是哪些东西。
        print("  基线样例（前 8 个）：")
        for p in sorted(new)[:8]:
            print("    · %s" % p)
    else:
        for name, items in (("新增", added), ("改动", modified), ("删除", deleted)):
            for p in items[:12]:
                print("    %s %s" % (name, p))
            if len(items) > 12:
                print("    %s …（共 %d，其余已记进记录）" % (name, len(items)))
        if not (added or modified or deleted):
            print("    与上次快照逐项一致：没有任何新增/改动/删除")
    print("  记录第 %d 条 · hash=%s" % (rec["n"], rec["hash"][:22]))
    return 0


# ────────────────────────────── 其余子命令 ──────────────────────────────
def cmd_append(args) -> int:
    ev = {"evidence": args.evidence} if args.evidence else None
    rec = append_record(args.kind, args.what, args.where, args.actor, ev)
    print("已记第 %d 条（%s）· hash=%s" % (rec["n"], rec["kind"], rec["hash"][:22]))
    # 🔴 2026-10-09 根因修复（主人令「生产面板禁止有任何污点」）：
    #    原来 append 与 render **是断开的** —— 记一条就让派生件（logbook-data.js / logbook-digest.md）
    #    落后源件；超过审计的 600s 宽限后，面板立刻多一条「陈旧 · 断连」。
    #    **每记一条就欠一个红**，这是自触发回路。⇒ append 默认顺手渲染（--no-render 可关）。
    if not getattr(args, "no_render", False):
        try:
            cmd_render(None)
            print("  ↳ 已顺手渲染派生件（消掉「陈旧」自触发；要关用 --no-render）")
        except Exception as exc:                                   # noqa: BLE001
            print("  ⚠️ 渲染失败（如实报，不静默）：%s: %s" % (type(exc).__name__, exc))
    return 0


def cmd_show(args) -> int:
    recs = read_records()
    for rec in recs[-args.n:]:
        if "_bad_line" in rec:
            print("!! 坏行 %d：%s" % (rec["_bad_line"], rec["_why"]))
            continue
        ev = rec.get("evidence") or {}
        tail = ""
        if rec.get("kind") == "scan":
            tail = " [+%s ~%s -%s]" % (ev.get("added"), ev.get("modified"), ev.get("deleted"))
        print("#%-4d %s %-8s %s%s" % (rec.get("n"), str(rec.get("ts"))[:19], rec.get("kind"),
                                      rec.get("what"), tail))
    ok, bad, why = verify_chain(recs)
    print("-" * 78)
    print(("✅ " if ok else "❌ ") + why)
    return 0 if ok else 1


def cmd_verify(_args) -> int:
    ok, bad, why = verify_chain()
    print(("✅ " if ok else "❌ ") + why)
    if not ok:
        print("   断点在第 %d 行 —— 本子只许追加，改过就要留下说明（新写一条 note）" % bad)
    return 0 if ok else 1


def cmd_render(_args) -> int:
    recs = [r for r in read_records() if "_bad_line" not in r]
    ok, _bad, why = verify_chain(recs)
    scans = [r for r in recs if r.get("kind") == "scan"]
    data = {
        "generated_at": now_iso(),
        "regen": "py -3.14 tools/codex-scripts/logbook.py render",
        "source": "state/logbook.jsonl（只追加 · 自链哈希）",
        "chain": {"ok": ok, "detail": why, "records": len(recs)},
        "totals": {
            "records": len(recs),
            "scans": len(scans),
            "changes": len([r for r in recs if r.get("kind") == "change"]),
            "decisions": len([r for r in recs if r.get("kind") == "decision"]),
            "delivers": len([r for r in recs if r.get("kind") == "deliver"]),
        },
        "scans": [{
            "n": r.get("n"), "ts": r.get("ts"), "label": (r.get("evidence") or {}).get("label"),
            "scanned": (r.get("evidence") or {}).get("scanned"),
            "unchanged": (r.get("evidence") or {}).get("unchanged"),
            "added": (r.get("evidence") or {}).get("added"),
            "modified": (r.get("evidence") or {}).get("modified"),
            "deleted": (r.get("evidence") or {}).get("deleted"),
            "baseline": (r.get("evidence") or {}).get("baseline"),
            "truncated": (r.get("evidence") or {}).get("max_files_hit"),
            "samples": (r.get("evidence") or {}).get("samples") or {},
        } for r in scans[-60:]],
        "records": [{"n": r.get("n"), "ts": r.get("ts"), "kind": r.get("kind"),
                     "actor": r.get("actor"), "what": r.get("what"),
                     "where": r.get("where"), "hash": str(r.get("hash"))[:22],
                     "prev": str(r.get("prev_hash"))[:22]} for r in recs[-300:]],
    }
    PAGE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_JS.write_text(
        "/* GBT小土豆V8 · 记录本数据件 —— **生成产物**，由 logbook.py render 覆盖，不许手改。\n"
        " * 重生成：%s\n"
        " * 口径：只追加 + 自链哈希；数字全部现算自 state/logbook.jsonl。 */\n"
        "window.GBT_LOGBOOK = %s;\n" % (data["regen"], json.dumps(data, ensure_ascii=False, indent=1)),
        encoding="utf-8")

    lines = ["# 记录本速读（%s）" % data["generated_at"],
             "",
             "> 生成产物：`py -3.14 tools/codex-scripts/logbook.py render`。源：`state/logbook.jsonl`（只追加 · 自链哈希）。",
             "",
             "## 链状态", "", "- " + ("✅ " if ok else "❌ ") + why, "",
             "## 统计", "",
             "| 条数 | 扫描 | 改动 | 决策 | 交付 |", "|---|---|---|---|---|",
             "| %d | %d | %d | %d | %d |" % (data["totals"]["records"], data["totals"]["scans"],
                                             data["totals"]["changes"], data["totals"]["decisions"],
                                             data["totals"]["delivers"]), "",
             "## 最近 15 条", ""]
    for r in data["records"][-15:]:
        lines.append("- `#%s` %s **%s** %s" % (r["n"], r["ts"], r["kind"], r["what"]))
    lines += ["", "## 扫描史（最近 10 次）", ""]
    for s in data["scans"][-10:]:
        lines.append("- %s %s：扫 %s · +%s ~%s -%s%s"
                     % (s["ts"], s["label"], s["scanned"], s["added"], s["modified"], s["deleted"],
                        "（建基线）" if s["baseline"] else ""))
    DIGEST.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("已生成：%s" % DATA_JS)
    print("已生成：%s" % DIGEST)
    return 0


def cmd_check(_args) -> int:
    """判据 —— 带**负对照**（判据不会报红的判据等于没有判据）。"""
    out = []

    def add(cid, ok, detail):
        out.append((cid, ok, detail))

    recs = read_records()
    bad_lines = [r for r in recs if "_bad_line" in r]
    add("L1", not bad_lines, "jsonl 每行都能解析（坏行 %d 条）" % len(bad_lines))

    ok, bad, why = verify_chain(recs)
    add("L2", ok, "自链哈希自洽 —— " + why)

    missing = []
    for rec in recs:
        if "_bad_line" in rec:
            continue
        if not all(str(rec.get(k) or "").strip() for k in ("ts", "kind", "actor", "what")):
            missing.append(rec.get("n"))
        elif not rec.get("where"):
            missing.append(rec.get("n"))
    add("L3", not missing, "每条都有 ts/kind/actor/what/where（缺项的第 %s 条）" % missing)

    # 负对照：把内容改一个字符，verify **必须**报红
    tampered = [dict(r) for r in recs if "_bad_line" not in r]
    neg_ok = False
    neg_why = "记录本还是空的 ⇒ 负对照跑不了（先 append 一条）"
    if tampered:
        tampered[0]["what"] = str(tampered[0]["what"]) + "（篡改）"
        n_ok, n_bad, n_why = verify_chain(tampered)
        neg_ok = (not n_ok)
        neg_why = "改一个字后 verify " + ("报红 ✅（第 %d 行）" % n_bad if not n_ok else "**仍报绿 ❌**")
    add("L4", neg_ok, "负对照：内容被改必须断链 —— " + neg_why)

    snap_ok = False
    snap_why = "没有 state/logbook-snapshot.json"
    if SNAP.exists():
        try:
            snap = json.loads(SNAP.read_text(encoding="utf-8"))
            last_scan = [r for r in recs if r.get("kind") == "scan"]
            snap_ok = bool(snap.get("files")) and bool(last_scan)
            snap_why = ("快照 %d 个文件 · 最后一条扫描记录 #%s（%s）"
                        % (len(snap.get("files") or {}),
                           (last_scan[-1].get("n") if last_scan else "无"),
                           (last_scan[-1].get("ts") if last_scan else "无")))
        except Exception as exc:                                      # noqa: BLE001
            snap_why = "快照解析失败：%s" % exc
    add("L5", snap_ok, "扫描有基线可比 —— " + snap_why)

    fresh = False
    fresh_why = "还没 render 过（页面数据件不存在）"
    if DATA_JS.exists() and recs:
        try:
            txt = DATA_JS.read_text(encoding="utf-8")
            gen = json.loads(txt.split("=", 1)[1].rstrip().rstrip(";")).get("generated_at") or ""
            last_ts = str([r for r in recs if "_bad_line" not in r][-1].get("ts") or "")
            fresh = gen >= last_ts
            fresh_why = "页面生成时刻 %s · 最后一条记录 %s（页面不许比记录还旧）" % (gen, last_ts)
        except Exception as exc:                                      # noqa: BLE001
            fresh_why = "数据件读不动：%s" % exc
    add("L6", fresh, "面板数据不比记录旧 —— " + fresh_why)

    if PAGE_DIR.joinpath("index.html").exists():
        html = PAGE_DIR.joinpath("index.html").read_text(encoding="utf-8", errors="replace")
        body = re.sub(r"<!--.*?-->", "", html, flags=re.S)   # 注里的出处 URL 不算引用
        dirty = [t for t in ("http://", "https://", "fetch(", "XMLHttpRequest", "<iframe",
                             "<img", "src=\"http", "src='http")
                 if t in body]
        add("L7", not dirty, "页面自包含（远端引用/取数口：%s）" % (dirty or "无"))
    else:
        add("L7", False, "页面 holo_pet_w3/logbook/index.html 不存在")

    print("=" * 78)
    print("记录本 · 判据")
    print("=" * 78)
    for cid, okk, detail in out:
        print("  %s %-4s %s" % ("✅" if okk else "❌", cid, detail))
    passed = sum(1 for _c, o, _d in out if o)
    print("-" * 78)
    print("  PASS %d · FAIL %d（共 %d 条）" % (passed, len(out) - passed, len(out)))
    if passed != len(out):
        print("  ⚠️ 有判据没过 —— 别宣称记录本可用")
    return 0 if passed == len(out) else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="GBT小土豆V8 · 记录本（只追加 · 自链哈希 · 每日扫描）")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("append", help="手记一条（任何动作都可以记）")
    a.add_argument("--no-render", action="store_true",
                   help="记完不渲染派生件（默认渲染：否则每记一条都会让面板多一条「陈旧」）")
    a.add_argument("--kind", required=True, choices=KINDS)
    a.add_argument("--what", required=True, help="一行说清做了/决定了什么（不许空）")
    a.add_argument("--where", action="append", default=[], help="涉及路径，可重复")
    a.add_argument("--actor", default="unknown", help="谁做的（模型名 / 人 / 脚本）")
    a.add_argument("--evidence", default="", help="证据：命令、读数、回执路径")
    a.set_defaults(func=cmd_append)

    s = sub.add_parser("scan", help="扫一遍真盘，算出改动/新增/删除并记账")
    s.add_argument("--label", default="扫描")
    s.add_argument("--max-files", type=int, default=200000, help="文件数上限（触顶会如实标出）")
    s.set_defaults(func=cmd_scan)

    sh = sub.add_parser("show", help="看最近几条")
    sh.add_argument("-n", type=int, default=20)
    sh.set_defaults(func=cmd_show)

    sub.add_parser("verify", help="验链").set_defaults(func=cmd_verify)
    sub.add_parser("render", help="生成面板数据件 + 速读 md").set_defaults(func=cmd_render)
    sub.add_parser("check", help="判据（含负对照）").set_defaults(func=cmd_check)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
