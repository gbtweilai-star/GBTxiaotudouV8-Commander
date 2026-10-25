"""技能描述瘦身刀（GBT小土豆V8 · 原生能力预算）

为什么只压 description：
    Codex 装配时**只读 frontmatter 的 description**，正文永不自动进上下文
    （2026-09-18 探针实测：44,930 B 的 SKILL.md 只占列表 102 字符）。
    因此把长描述压成一句摘要，原文一字不丢地挪进正文存档段 —— 能力零损失，
    上下文占用线性下降。

判据（C3 · 独立判据）：
    `codex debug prompt-input "probe"` 的 <skills_instructions> 块 ≤ 11000 字符，
    且 63 条技能一条不少（条数不减才算"能力不丢"）。

用法：
    python -m gbt_allinone.tools.skill_slim            # 干跑，不写任何文件
    python -m gbt_allinone.tools.skill_slim --apply    # 真写（先备份 + 落版本锁）
    python -m gbt_allinone.tools.skill_slim --check    # 差异检测（对比版本锁）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

CAP = 110                 # 单条摘要上限（字符）——122 是硬上限，110 留余量
TARGET_BLOCK = 11000      # 技能块目标上限（字符）
ARCHIVE_MARK = "## 完整描述（原文存档 · 瘦身于 2026-09-18）"
STAMP = "2026-09-18"

HERE = Path(__file__).resolve()
WORKSPACE = HERE.parents[2]
LOCK_PATH = HERE.parent / "skill_slim.lock.json"
BACKUP_DIR = WORKSPACE / ".scratch" / f"skill_slim_backup_{STAMP}"

ROOTS = [
    ("r0", Path.home() / ".codex" / "skills"),
    ("r1", Path.home() / ".agents" / "skills"),
    ("r2", Path.home() / ".codex" / "skills" / ".system"),
    ("r3", WORKSPACE / ".agents" / "skills"),
]

FM_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?", re.S)
DESC_RE = re.compile(r"^([ \t]*)description[ \t]*:[ \t]*(.*)$", re.M)
KEY_RE = re.compile(r"^([A-Za-z_][\w-]*)[ \t]*:")


class SlimError(RuntimeError):
    pass


# ── YAML frontmatter 解析（支持多行折叠 / 字面块）──

def strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        inner = s[1:-1]
        if s[0] == "'":
            inner = inner.replace("''", "'")
        return inner
    return s


def read_description(fm: str) -> tuple[str, int, int, str]:
    """返回 (描述全文, 起始行号, 结束行号, 块风格)。行号相对 fm 内 0 基。"""
    lines = fm.split("\n")
    for i, line in enumerate(lines):
        m = DESC_RE.match(line)
        if not m:
            continue
        val = m.group(2).strip()
        style = "scalar"
        if val in ("", ">", ">-", ">+", "|", "|-", "|+"):
            style = "folded" if val.startswith(">") else "literal"
            style = style if val else "folded"
            j = i + 1
            block = []
            while j < len(lines):
                nxt = lines[j]
                if nxt.strip() == "" or nxt[:1] in (" ", "\t"):
                    block.append(nxt)
                    j += 1
                else:
                    break
            while block and block[-1].strip() == "":
                block.pop()
            ded = [b[2:] if b[:2] == "  " else b.lstrip("\t") for b in block]
            joiner = "\n" if style == "literal" else " "
            return joiner.join(x.strip() for x in ded if x.strip() != "").strip(), i, j - 1, style
        return strip_quotes(val), i, i, "scalar"
    return "", -1, -1, "missing"


# ── 摘要生成（可审可改：只切句，不改写）──

def make_summary(desc: str, cap: int = CAP) -> str:
    """把长描述压成一句 ≤cap 的摘要 —— 只做**截句**，不重写、不丢关键词序。"""
    text = " ".join(desc.split())
    if len(text) <= cap:
        return text
    window = text[:cap]
    # 掩码代码段：`` `...` `` 里被切断会产出半截 URL / 半截包名（实测踩过）
    masked = re.sub(r"`[^`]*`", lambda m: "\x00" * len(m.group(0)), window)
    for sep in ("。", "；", "！", "？", ". ", "; "):
        idx = masked.rfind(sep)
        if idx >= 30:
            return sanitize_scalar(window[: idx + (1 if sep in ("。", "；", "！", "？") else 0)])
    # 不用 "/" 作分隔符：`@cloudflare/sandbox@next` 这类包名会被切碎（实测踩过）
    for sep in ("，", ",", "、", "—", "：", "(", " "):
        idx = masked.rfind(sep)
        if idx >= 30:
            return sanitize_scalar(window[:idx])
    head = window
    if head.count("`") % 2:
        head = head[: head.rfind("`")]
    return sanitize_scalar(head)


def sanitize_scalar(s: str) -> str:
    """让摘要能安全地做 YAML 裸标量（不引号、不换行、不触发注释）。"""
    s = " ".join(s.split())
    s = s.replace(": ", "：").replace(":#", "：＃")
    while s[:1] in ("-", "#", "&", "*", "!", "?", "|", ">", "@", "`", "%"):
        s = s[1:].lstrip()
    return s


def split_doc(text: str):
    m = FM_RE.match(text)
    if not m:
        return None, None, text
    return m.group(1), m, text[m.end():]


def build_archive(orig: str) -> str:
    return (
        f"{ARCHIVE_MARK}\n\n"
        "> 本段是**瘦身前 frontmatter.description 的原文**，一字未改；上方 frontmatter 只留\n"
        f"> 一句摘要（≤{CAP} 字符）供 Codex 列表加载。改描述前请先读本段，改完同步本段。\n\n"
        f"{orig.strip()}\n"
    )


def upsert_archive(body: str, orig: str) -> str:
    block = build_archive(orig)
    if ARCHIVE_MARK in body:
        head, _, tail = body.partition(ARCHIVE_MARK)
        nxt = re.search(r"^## ", tail, re.M)
        rest = tail[nxt.start():] if nxt else ""
        return head + block + ("\n" + rest if rest else "")
    sep = "" if body.endswith("\n\n") else ("\n" if body.endswith("\n") else "\n\n")
    return body + sep + block


# ── 扫描 ──

def find_skills():
    found = []
    for tag, root in ROOTS:
        if not root.exists():
            continue
        for p in sorted(root.rglob("SKILL.md")):
            rel_parts = p.parts[len(root.parts):-1]
            if any(part.startswith(".") for part in rel_parts):
                continue
            found.append((tag, root, p))
    return found


def analyze(tag, root, path: Path) -> dict:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    fm, m, body = split_doc(text)
    rec = {"root": tag, "path": str(path), "rel": str(path.relative_to(root)),
           "bytes": len(raw), "crlf": raw.count(b"\r\n"), "lf": raw.count(b"\n"),
           "sha16": hashlib.sha256(raw).hexdigest()[:16], "skip": None}
    if fm is None:
        rec["skip"] = "no-frontmatter"
        return rec
    desc, i0, i1, style = read_description(fm)
    rec.update({"desc_raw": desc, "desc_chars": len(desc), "style": style,
                "line_idx": [i0, i1], "body": body, "fm": fm})
    rec["already"] = ARCHIVE_MARK in body
    summary = sanitize_scalar(make_summary(desc))
    rec["summary"] = summary
    rec["summary_chars"] = len(summary)
    rec["needed"] = len(desc) > CAP   # 已 ≤CAP 的一条不动：没有可存档的删减，改了只是白churn
    return rec


def rewrite(rec) -> str | None:
    if not rec.get("needed") or rec.get("skip"):
        return None
    fm_lines = rec["fm"].split("\n")
    i0, i1 = rec["line_idx"]
    if i0 < 0:
        return None
    new_line = f"description: {rec['summary']}"
    fm_new = "\n".join(fm_lines[:i0] + [new_line] + fm_lines[i1 + 1:])
    body_new = upsert_archive(rec["body"], rec["desc_raw"])
    return f"---\n{fm_new}\n---\n{body_new}"


# ── 主流程 ──

def _load_lock() -> dict:
    if LOCK_PATH.exists():
        try:
            return json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {"generated_at": None, "cap": CAP, "archive_mark": ARCHIVE_MARK, "skills": {}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真写（默认干跑）")
    ap.add_argument("--check", action="store_true", help="差异检测")
    ap.add_argument("--relock", action="store_true", help="只重建版本锁（不写任何 SKILL.md）")
    args = ap.parse_args(argv)

    skills = [analyze(*s) for s in find_skills()]

    if args.check:
        if not LOCK_PATH.exists():
            print(f"[check] 无版本锁：{LOCK_PATH}")
            return 2
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        drift = []
        for s in skills:
            old = lock["skills"].get(s["path"])
            if not old:
                drift.append((s["path"], "新增（锁里没有）"))
            elif old.get("sha16_after") and s["sha16"] != old["sha16_after"]:
                drift.append((s["path"], f'被改动 {old["sha16_after"]} -> {s["sha16"]}'))
        print(f"[check] 技能 {len(skills)} · 漂移 {len(drift)}")
        for p, why in drift:
            print(f"  ! {why}\n      {p}")
        return 0 if not drift else 1

    todo = [s for s in skills if s.get("needed") and not s.get("skip")]
    print(f"[scan] 技能 {len(skills)} 条 · 需瘦身 {len(todo)} 条 · 上限 {CAP} 字符")
    for s in todo:
        print(f"  {s['desc_chars']:>5} -> {s['summary_chars']:>4}  {s['root']}/{s['rel']}")
    if not args.apply and not args.relock:
        print("[dry-run] 未写任何文件。加 --apply 才写。")
        return 0

    if args.relock:
        lock = _load_lock()
        for s in skills:
            if not s.get("skip"):
                rec = dict(lock["skills"].get(s["path"], {}))
                rec.update({"root": s["root"], "rel": s["rel"],
                            "sha16_now": s["sha16"], "desc_chars_now": s["desc_chars"],
                            "archive": s.get("already", False)})
                lock["skills"][s["path"]] = rec
        lock["generated_at"] = datetime.now().isoformat(timespec="seconds")
        LOCK_PATH.write_text(json.dumps(lock, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[relock] {len(lock["skills"])} 条 -> {LOCK_PATH}")
        return 0

    if not todo:
        print("[apply] 无需改动")
        return 0

    sys.path.insert(0, str(WORKSPACE))
    from gbt_allinone.safe_io import atomic_write_text_aligned

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    lock = _load_lock()   # 与既有锁合并：按「本轮 todo」建锁会丢掉上一轮的条目
    lock.update({"cap": CAP, "archive_mark": ARCHIVE_MARK})
    lock["generated_at"] = datetime.now().isoformat(timespec="seconds")
    written, failed = 0, []
    for s in todo:
        new_text = rewrite(s)
        if new_text is None:
            failed.append((s["path"], "no-change")); continue
        flat = f"{s['root']}__{s['rel'].replace(os.sep, '_')}.bak"
        shutil.copy2(s["path"], BACKUP_DIR / flat)
        try:
            atomic_write_text_aligned(s["path"], new_text)
        except Exception as exc:  # noqa: BLE001
            shutil.copy2(BACKUP_DIR / flat, s["path"])
            failed.append((s["path"], f"{type(exc).__name__}: {exc}")); continue
        raw2 = Path(s["path"]).read_bytes()
        tf = raw2.decode("utf-8")
        fm2, _, body2 = split_doc(tf)
        d2, *_ = read_description(fm2)
        ok = (ARCHIVE_MARK in body2) and (len(d2) <= CAP) and (d2 == s["summary"]) and (fm2 is not None)
        lock["skills"][s["path"]] = {
            "root": s["root"], "rel": s["rel"],
            "sha16_before": s["sha16"], "sha16_after": hashlib.sha256(raw2).hexdigest()[:16],
            "desc_chars_before": s["desc_chars"], "desc_chars_after": len(d2),
            "archive": ARCHIVE_MARK in body2, "verified": bool(ok)}
        written += 1

    LOCK_PATH.write_text(json.dumps(lock, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[apply] 写了 {written} 条 · 失败 {len(failed)} 条 · 备份 {BACKUP_DIR}")
    for p, why in failed:
        print(f"  ! {why}  {p}")
    print(f"[lock] {LOCK_PATH}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
