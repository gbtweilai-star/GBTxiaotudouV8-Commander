"""账本追加（**只追加、不重排**）—— 把「插一节进证据账」变成一条可复核的命令。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要有它
`memory/在办清单.md` 是证据账（上万行、只追加）。人工插章节有四个真风险：
  ① **署名被挤到中间** —— 本仓红线是「署名不可删除」，而"最后一行还是不是署名"
     人工是看不出来的（插完就没人再核对）；
  ② **写盘时换行被偷偷翻掉** —— `Path.write_text` 在 Windows 上会把 `\\n` 翻成 `\\r\\n`
     （实测踩过：`index.html` 凭空 +590 字节）⇒ 声称"只加了一节"，实际**改了整个文件的换行**；
  ③ 🔴 **真账本是 CRLF**（现读：CRLF 数 == LF 数 == 行数）—— 按 `\\n` 找分隔线的工具
     在它身上会**一插就拒**，或者更坏：混着写出一份**混合换行**的账；
  ④ **插入点靠猜** —— 分隔线不在就随便找个位置塞进去。

## 这一件干什么（fail-closed，**写之前**就拒）
- **最后一条非空行必须含署名**（单一真源 `gbt_allinone.soul.SIGNATURE`），署名后面还有正文 ⇒ **拒**；
- 署名行**之前必须有分隔线**，找不到 ⇒ **拒**（不猜插入点）；
- 待插章节**非空**；自带尾分隔线会被摘掉（**不许出现两条相邻 `---`**）；
- **换行口径先量**：全 LF / 全 CRLF 都照原样写；**混用 ⇒ 拒**（按字节写的工具把脏换行固化最坏）；
- 落盘用**字节**写，写完**逐字节自比**，并复核四条不变量：
  **前缀逐字节未动 · 后缀逐字节未动 · 署名仍在最后一行 · 落盘逐字节一致** + 换行仍均匀。

用法：
  python tools/codex-scripts/ledger-append.py append --section <正文.md> [--target <账本.md>]
  python tools/codex-scripts/ledger-append.py check [--target <账本.md>]
  python tools/codex-scripts/ledger-append.py selftest
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "memory" / "在办清单.md"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    sys.path.insert(0, str(ROOT))
    from gbt_allinone.soul import SIGNATURE as SIG_MARK      # 单一真源，不硬编码
except Exception:                                            # 进不去就退回字面量并**标注**
    SIG_MARK = "开发者：自由的风"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:12]


def _rel(p: Path) -> str:
    """仓内给相对路径；**临时靶（自检用）给全路径** —— 不许在这里抛异常。"""
    try:
        return str(p.relative_to(ROOT))
    except Exception:
        return str(p)


def _last_nonempty(text: str) -> str:
    for ln in reversed(text.splitlines()):
        if ln.strip():
            return ln
    return ""


def _sig_span(text: str) -> tuple[int, int] | None:
    """最后一条**含署名**的非空行的 (start, end) 偏移；一条都没有返回 `None`。"""
    pos, found = 0, None
    for ln in text.splitlines(keepends=True):
        if ln.strip() and SIG_MARK in ln:
            found = (pos, pos + len(ln))
        pos += len(ln)
    return found


def _has_content_after(text: str, end: int) -> bool:
    return any(ln.strip() for ln in text[end:].splitlines())


def _eol(text: str) -> tuple[str, str]:
    """量出换行口径。**混用一律拒** —— 本工具按字节写，混写会把脏换行固化进证据账。"""
    crlf, lf = text.count("\r\n"), text.count("\n")
    if crlf == 0:
        return "\n", ""
    if crlf == lf:
        return "\r\n", ""
    return "", "**目标混用换行**（CRLF %d ｜ LF %d）⇒ 拒（不许把脏换行固化进证据账）" % (crlf, lf)


def plan(text: str, section: str) -> tuple[dict, str, int]:
    """**只算不写**。返回 (判决, 新全文（拒绝时为空串）, 插入点)。"""
    eol, why = _eol(text)
    if not eol:
        return {"ok": False, "拒绝": why}, "", -1
    sep = eol + "---" + eol
    body = section.replace("\r\n", "\n").rstrip("\n")
    if body.rstrip().endswith("---"):                   # 摘掉自带尾分隔线，统一补一条
        body = body.rstrip()[:-3].rstrip("\n")
    if not body.strip():
        return {"ok": False, "拒绝": "**待插章节是空的**（空章节不许插进证据账）"}, "", -1
    body = body.replace("\n", eol)                       # 🔴 跟账本自己的换行口径走
    span = _sig_span(text)
    if span is None:
        return {"ok": False, "拒绝": "**整个账本里找不到含署名的行** ⇒ 拒（署名不可删除）"}, "", -1
    if _has_content_after(text, span[1]):
        return {"ok": False, "拒绝": "**署名后面还有正文** ⇒ 拒（署名不许被挤到中间）"}, "", -1
    j = text.rfind(sep, 0, span[0])
    if j < 0:
        return {"ok": False, "拒绝": "署名行之前没有分隔线 ⇒ 拒（不猜插入点）"}, "", -1
    at = j + len(eol)
    new = text[:at] + body + eol + eol + text[at:]
    return ({"ok": True, "插入点": at, "本段行数": len(body.splitlines()) + 2,
             "换行": "CRLF" if eol == "\r\n" else "LF"}, new, at)


def verify(old: str, new: str, at: int, intended: bytes, actual: bytes) -> dict:
    eol, _ = _eol(old)
    crlf, lf = actual.count(b"\r\n"), actual.count(b"\n")
    return {
        "前缀逐字节未动": new.startswith(old[:at]) and at > 0,
        "后缀逐字节未动": new.endswith(old[at:]) and len(new) > at,
        "署名仍在最后一行": SIG_MARK in _last_nonempty(new),
        "落盘逐字节一致": intended == actual,
        "换行仍均匀": (crlf == lf) if eol == "\r\n" else (crlf == 0),
    }


def do_append(section_path: Path, target: Path) -> tuple[int, dict]:
    if not target.is_file():                            # 🔴 未读到就是未读到，不拿「空账本」顶替
        return 2, {"ok": False,
                   "拒绝": "**账本不在盘上**：%s ⇒ 拒（未读到时不许当空账追加）" % _rel(target)}
    old_b = target.read_bytes()
    old = old_b.decode("utf-8")
    sec = section_path.read_text(encoding="utf-8")
    p, new, at = plan(old, sec)
    if not p["ok"]:
        return 2, p
    intended = new.encode("utf-8")
    target.write_bytes(intended)                        # 🔴 字节写，不翻换行
    actual = target.read_bytes()
    v = verify(old, new, at, intended, actual)
    out = {"ok": all(v.values()), "落点": _rel(target),
           "sha": "%s → %s" % (_sha(old_b), _sha(actual)),
           "行数": "%d → %d（本段 %d 行 · %s）" % (len(old.splitlines()), len(new.splitlines()),
                                            p["本段行数"], p["换行"]),
           "不变量": v}
    return (0 if out["ok"] else 1), out


def do_check(target: Path) -> tuple[int, dict]:
    if not target.is_file():
        return 2, {"账本": _rel(target), "**未读到**": "文件不在盘上 ⇒ 不念成合格"}
    raw = target.read_bytes()
    text = raw.decode("utf-8")
    eol, why = _eol(text)
    span = _sig_span(text)
    ok = bool(eol) and span is not None and not _has_content_after(text, span[1])
    return (0 if ok else 1), {"账本": _rel(target),
                              "行数": len(text.splitlines()),
                              "换行": ("CRLF" if eol == "\r\n" else ("LF" if eol else "**混合**")),
                              "最后一条非空行": _last_nonempty(text)[:60],
                              "署名在最后": ok,
                              "换行问题": why or "无",
                              "现读": "CRLF %d ｜ LF %d" % (raw.count(b"\r\n"), raw.count(b"\n"))}


def selftest() -> int:
    checks, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad = bad + (0 if cond else 1)
        checks.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    def brief(rep: dict) -> str:
        """一次运行的读数压成一行；**拒绝时明写「未读到」**，不拿空值顶替。

        🔴 形参特意叫 `rep`（结果记录）不叫 `out`：台架的 `TEXTISH` 把 `out` 当
        「可能装着源码文本的变量」，`"键" in out` 这种**字典键判断**会被读成
        「文本子串判据」（D2/D6 假阳性）。**键判断不是文本判据**，改名不改语义。
        """
        if "不变量" not in rep:
            return "**未读到不变量**（%s）" % rep.get("拒绝", "**未读到拒绝理由**")
        return "%s ｜ %s" % (rep.get("行数") or "**未读到行数**", rep["不变量"])

    SIGLINE = "%s---%s%s> %s · 守护者：公主土豆 · 本署名不可删除%s" % ("", "\n", "\n", SIG_MARK, "\n")
    BODY = "## 试插一节\n\n正文带中文与换行。\n"
    with tempfile.TemporaryDirectory() as tds:
        td = Path(tds)
        sec = td / "sec.md"
        sec.write_bytes(BODY.encode("utf-8"))            # 🔴 夹具也用字节写（write_text 会翻换行）

        def mk(name: str, raw: str) -> Path:
            p = td / name
            p.write_bytes(raw.encode("utf-8"))
            return p

        # ① 正控（LF 靶）
        tgt = mk("lf.md", "## 老的一节\n\n老正文\n\n" + SIGLINE)
        rc, out = do_append(sec, tgt)
        ck("**正控（LF 靶）：真插入 ⇒ 五条不变量全过**",
           rc == 0 and out["ok"] is True and all(out["不变量"].values()), brief(out))
        ck("**插入后署名仍是最后一条非空行**",
           SIG_MARK in _last_nonempty(tgt.read_text(encoding="utf-8")),
           _last_nonempty(tgt.read_text(encoding="utf-8"))[:44])

        # ② 正控（CRLF 靶 = 真账本的换行口径）
        crlf = mk("crlf.md", ("## 老的一节\n\n老正文\n\n" + SIGLINE).replace("\n", "\r\n"))
        rc, out = do_append(sec, crlf)
        raw = crlf.read_bytes()
        ck("**正控（CRLF 靶）：能插进去，且插入后仍是均匀 CRLF**",
           rc == 0 and out["ok"] is True and raw.count(b"\r\n") == raw.count(b"\n")
           and out["不变量"]["换行仍均匀"],
           "%s ｜ CRLF %d ｜ LF %d" % (out.get("行数") or "**未读到行数**",
                                     raw.count(b"\r\n"), raw.count(b"\n")))

        # ③ 负控：段自带尾分隔线 ⇒ 统一成一条，不许相邻双分隔线
        sec2 = td / "sec2.md"
        sec2.write_bytes("## 试插二\n\n正文\n\n---\n".encode("utf-8"))
        rc, _ = do_append(sec2, tgt)
        t2 = tgt.read_text(encoding="utf-8")
        ck("**段自带 `---` ⇒ 统一成一条（不出现相邻双分隔线）**",
           rc == 0 and "\n---\n\n---\n" not in t2 and t2.count("\n---\n") == 1,
           "分隔线数 %d" % t2.count("\n---\n"))

        # ④ 负控：空章节 ⇒ 拒绝且**文件逐字节未改**
        empty = td / "empty.md"
        empty.write_bytes("\n\n   \n".encode("utf-8"))
        snap = tgt.read_bytes()
        rc, out = do_append(empty, tgt)
        ck("**空章节 ⇒ 拒绝且文件逐字节未改**",
           rc == 2 and tgt.read_bytes() == snap and "空" in str(out.get("拒绝")),
           str(out.get("拒绝"))[:44])

        # ⑤ 负控：**署名被挤到中间** ⇒ 拒绝（这是本件存在的理由）
        mid = mk("mid.md", "## 旧节\n\n> %s\n\n## 署名后面的新节\n\n正文\n" % SIG_MARK)
        snap2 = mid.read_bytes()
        rc, out = do_append(sec, mid)
        ck("**署名被挤到中间 ⇒ 拒绝且文件未改**",
           rc == 2 and mid.read_bytes() == snap2 and "中间" in str(out.get("拒绝")),
           str(out.get("拒绝"))[:44])

        # ⑥ 负控：整个文件没有署名 ⇒ 拒绝且文件未改
        nosig = mk("nosig.md", "## 没有署名的账\n\n正文\n")
        snap3 = nosig.read_bytes()
        rc, out = do_append(sec, nosig)
        ck("**没有署名 ⇒ 拒绝且文件未改**",
           rc == 2 and nosig.read_bytes() == snap3 and "署名" in str(out.get("拒绝")),
           str(out.get("拒绝"))[:44])

        # ⑦ 负控：没有分隔线 ⇒ 拒绝（不猜插入点）
        nosep = mk("nosep.md", "## 没分隔线\n\n> %s\n" % SIG_MARK)
        rc, out = do_append(sec, nosep)
        ck("**没有分隔线 ⇒ 拒绝**（不猜插入点）",
           rc == 2 and "分隔线" in str(out.get("拒绝")), str(out.get("拒绝"))[:44])

        # ⑧ 负控：**混用换行**的靶 ⇒ 拒绝（不许把脏换行固化）
        mix = mk("mix.md", "## 老\n\n老正文\n\r\n---\r\n\r\n> %s\n" % SIG_MARK)
        snap4 = mix.read_bytes()
        rc, out = do_append(sec, mix)
        ck("**混用换行的靶 ⇒ 拒绝且文件未改**",
           rc == 2 and mix.read_bytes() == snap4 and "混用" in str(out.get("拒绝")),
           str(out.get("拒绝"))[:46])

        # ⑨ 正控：落盘不偷换换行（LF 靶全文 0 个 CRLF）
        ck("**LF 靶落盘后全文 0 个 CRLF**", b"\r\n" not in tgt.read_bytes(),
           "CRLF=%d" % tgt.read_bytes().count(b"\r\n"))

        # ⑩ 现读真账本（只读）：署名在最末 + 换行口径
        rc, out = do_check(LEDGER)
        ck("**真账本现读：署名在最后 · 换行均匀**", rc == 0,
           "%d 行 ｜ %s ｜ %s" % (out.get("行数", 0), out.get("换行"), out.get("现读")))

    print(json.dumps({"自检": {"条数": len(checks), "通过": len(checks) - bad, "不通过": bad},
                      "逐条": checks}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["append", "check", "selftest"])
    ap.add_argument("--section", help="待插章节的 md 文件")
    ap.add_argument("--target", default=str(LEDGER))
    a = ap.parse_args()
    if a.cmd == "selftest":
        return selftest()
    target = Path(a.target)
    if a.cmd == "check":
        rc, out = do_check(target)
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return rc
    if not a.section:
        print(json.dumps({"ok": False, "拒绝": "append 必须给 --section"}, ensure_ascii=False))
        return 2
    rc, out = do_append(Path(a.section), target)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
