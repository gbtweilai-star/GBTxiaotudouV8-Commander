# -*- coding: utf-8 -*-
"""「新增即清旧」· 机器判据（主人新规矩 2026-10-08）。

主人原话：「只要设计新的，旧的顺手当场拉回收站 —— 自己造垃圾会把自己弄迷糊；
重启后绝不许把旧的当新的。」

## 本器扫四类（**只报 + 给回收命令**；默认不删）
  ① **同功能两份**：同一"规范名"（剥掉版本/备份后缀后同名）在我们自己的目录里≥2 份。
  ② **被超越未回收**：带备份/旧版标记（`.bak` / `.old` / `_bak` / `_old` / `_vN_backup` …）
     仍在役的件；或 `old-pages.py` 判为「被超越 / 零引用」的页。
  ③ **指针仍指旧版**：根目录启动件（`*.cmd` / `*.bat`）或 canonical 名（AGENTS.md / INDEX.md）
     仍引用一个被判「被超越」的件 ⇒ 重启后会**把旧的当新的**。
  ④ **证据目录与在役件混淆**：证据名目录（`out` / `frames` / `_diag*` / `*_backup`）里放**可执行件**
     （`.py`），或**在役目录**（`gbt_allinone/tools` 等）里混进备份标记件。

## 回收一律走**回收站**（不硬删），复用 `clean_residue.py::_recycle_batch`（本机实测可用）。
核完再清回收站旧版 —— 照 [[v8-golive-and-pack-chain]] 既有做法（`restore_from_recyclebin.py` 可还原）。

## 用法
    py -3.14 tools/codex-scripts/supersede-check.py            # 出四类清单 + 回收命令（只报）
    py -3.14 tools/codex-scripts/supersede-check.py --check     # 判据 + 负对照 · 有旧件⇒退出码 1
    py -3.14 tools/codex-scripts/supersede-check.py --recycle   # **真**把四类目标搬进回收站（需人拍板）
    py -3.14 tools/codex-scripts/supersede-check.py --json

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "tools" / "codex-scripts" / "clean_residue.py"
CMD = "py -3.14 tools/codex-scripts/supersede-check.py"

# 我们自己的目录（**别人的一律不碰**：V9 / _upstream / plugins / holo_pet / node_modules）
SCOPE = ("tools/codex-scripts", "gbt_allinone", "docs", "holo_pet_w3", "state")
# 2026-10-10 增补（**这台扫描器在狼来了**）：它把任何 *.old 都当"被超越未回收"，
#    实测报出的 24 件**全是** state/browser_own_profile/Default/**/LOG.old —— 那是 **Chrome 自己的
#    用户配置内部件**，不是我造的旧件。判据比对象宽 = **假红**；而假红多了，真抓到那次也没人信。
#    browser_own_profile 是浏览器自管的目录，一律不扫（与 store/_upstream 同级）。
SKIP_PARTS = (".pylibs", "node_modules", ".git", "__pycache__", "store", ".scratch", "_upstream",
              "archive", "dist", "build", "vendor", "site-packages", "browser_own_profile")
BACKUP_MARK = re.compile(r"(\.bak\d*$|\.old$|\.orig$|_bak$|_old$|_backup$|_v\d+_backup$|~\$|\.tmp$|-2\.\w+$)",
                         re.I)
# 版本/备份后缀 → 规范化：`build_v10.py` 与 `build_v10_canvas.py` 规范名不同（不同功能）；`x.py` 与 `x.py.bak` 相同
CANON_STRIP = re.compile(r"(\.bak\d*|\.old|\.orig|_bak|_old|_backup|~)$", re.I)


def _norm_name(name: str) -> str:
    stem = name
    while True:
        new = CANON_STRIP.sub("", stem)
        if new == stem:
            break
        stem = new
    return stem.lower()


def _walk():
    for base in SCOPE:
        d = ROOT / base
        if not d.is_dir():
            continue
        for dp, dns, fns in __import__("os").walk(d, followlinks=False):
            dns[:] = [x for x in dns if x not in SKIP_PARTS]
            for fn in fns:
                yield Path(dp) / fn


def scan() -> dict:
    found = {"同功能两份": [], "被超越未回收": [], "指针仍指旧版": [], "证据目录与在役件混淆": []}
    by_canon = {}
    backup_marked = []
    files = list(_walk())
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        # ② 备份/旧版标记件（仍在役目录里）
        if BACKUP_MARK.search(p.name):
            backup_marked.append(rel)
        # ① 同功能两份（按规范名分组，取 .py/.md/.js/.html 之类"功能件"）
 # 2026-10-10 修（**这一整类原来是死代码**）。原判据只看 **后缀**：
        #      x.py + x.py.bak  —— 规范名同为 x.py，但 .bak **后缀不在名单里** ⇒ 备份件进不了分组；
        #      x_bak.py         —— 后缀过了，但规范名是 x_bak.py ≠ x.py ⇒ 也配不成对。
        #    实测真植入一对（_probe_samefn.py + .bak）⇒ **一类永远不响**。四类判据里躺着一类死码，
        #    比"少一类"更坏：报告上写着它有 0 命中，看着像"查过了、干净"。
        #    ⇒ 改成**看规范名**：只要**规范化之后**仍是个功能件（剥掉备份后缀后还是 .py/.md/...），就收进来。
        _FN_SUF = (".py", ".md", ".js", ".cjs", ".html", ".json")
        if p.suffix.lower() in _FN_SUF or _norm_name(p.name).lower().endswith(_FN_SUF):
            by_canon.setdefault(_norm_name(p.name), []).append(rel)
    for canon, lst in sorted(by_canon.items()):
        if len(lst) >= 2 and any(BACKUP_MARK.search(Path(x).name) is None for x in lst) \
                and any(BACKUP_MARK.search(Path(x).name) for x in lst):
            # 同规范名里既有"在役件"又有"备份件" ⇒ 同功能两份
            found["同功能两份"].append({"canonical": canon, "files": sorted(lst)})
    found["被超越未回收"] = sorted(backup_marked)
    # ③ 指针仍指旧版：根启动件引用被超越件
    superseded_names = {Path(x).name for x in backup_marked}
    launchers = list(ROOT.glob("*.cmd")) + list(ROOT.glob("*.bat"))
 # 2026-10-10 补（**实测出来的缺口**）：本件文档第 11 行写的是
    #    「根目录启动件（*.cmd / *.bat）**或 canonical 名（AGENTS.md / INDEX.md）**」，
    #    而代码只 glob 了前半 —— 我用真植入验过：把被超越件写进 **.cmd** ⇒ 抓到；
    #    同样写进 **AGENTS.md** ⇒ **看不见**。
    #    ==判据的文档说了一套、代码只做一半，比不写文档更坏：它让人以为这半边有人管。==
    #    AGENTS.md / INDEX.md 是 canonical 指针（"重启后不许把旧的当新的"主要就靠它们），
    #    漏了它们等于这条判据守错了地方。两半都查。
    _canon = [c for c in (ROOT / "AGENTS.md", ROOT / "INDEX.md") if c.is_file()]
    for lp in launchers + _canon:
        try:
            t = lp.read_text(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            continue
        for nm in superseded_names:
            if nm in t:
                found["指针仍指旧版"].append({"pointer": lp.name, "target": nm})
                break
    # ④ 证据目录与在役件混淆：证据名目录里放可执行件 / 在役目录里放备份件
    evidence_dir = re.compile(r"(^|/)(out|frames[^/]*|_diag[^/]*|[^/]*_backup|clips[^/]*|v\d+|_v\d+_backup)/")
    in_service_dir = re.compile(r"(gbt_allinone/(tools|llm|security|tentacle)|tools/codex-scripts)/")
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        # 只认**可执行在役件**（.py）：页面的 .js/.html 算不上"在役代码"（证据目录里放 .js 是常态）
        if evidence_dir.search(rel) and p.suffix.lower() == ".py":
            found["证据目录与在役件混淆"].append({"file": rel, "why": "证据目录里放可执行件(.py)"})
        elif in_service_dir.search(rel) and BACKUP_MARK.search(p.name):
            found["证据目录与在役件混淆"].append({"file": rel, "why": "在役目录里混进备份件"})
    return found


def recycle_cmd(targets: list) -> str:
    return ("py -3.14 tools/codex-scripts/supersede-check.py --recycle  "
            "（= 复用 clean_residue._recycle_batch，送 **回收站**，不硬删；还原：restore_from_recyclebin.py）"
            "  目标 %d 件" % len(targets))


def cmd_scan(as_json: bool = False) -> int:
    f = scan()
    if as_json:
        print(json.dumps(f, ensure_ascii=False, indent=1))
        return 0
    print("=" * 84)
    print("「新增即清旧」· 扫描（四类 · 只报 · 回收一律走回收站）")
    print("=" * 84)
    n = 0
    for k, rows in f.items():
        print("  【%s】%d" % (k, len(rows)))
        n += len(rows)
        for r in rows[:12]:
            print("      · %s" % (r if isinstance(r, str) else r.get("file") or r.get("canonical") or r))
        if len(rows) > 12:
            print("      · …共 %d（见 --json）" % len(rows))
    print("-" * 84)
    print("合计 %d 处 ⇒ 回收命令：%s" % (n, recycle_cmd(f["被超越未回收"]))) 
    print("口径：判据取**名字/引用**，不取 mtime；**别人的目录一律不碰**（V9/_upstream/plugins/holo_pet）。")
    return 0


def _recycle(targets: list) -> tuple:
    """复用 clean_residue 的回收批次（PowerShell Microsoft.VisualBasic → 回收站）。"""
    if not CLEAN.is_file():
        return 0, [{"error": "clean_residue.py 不在：%s" % CLEAN}], []
    spec = importlib.util.spec_from_file_location("_gbt_clean_for_supersede", CLEAN)
    m = importlib.util.module_from_spec(spec)
    sys.modules["_gbt_clean_for_supersede"] = m
    try:
        spec.loader.exec_module(m)
    except Exception as e:                                   # noqa: BLE001
        return 0, [{"error": "载入失败：%s" % e}], []
    fn = getattr(m, "_recycle_batch", None)
    if not callable(fn):
        return 0, [{"error": "clean_residue 没有 _recycle_batch"}], []
    return fn([str(ROOT / t) for t in targets])


# ══════════════════════════════════════════════════════════════════════════
# 判据（**能红**：负对照喂合成旧件）
# ══════════════════════════════════════════════════════════════════════════
def classify_findings(f: dict) -> dict:
    """纯函数：把四类读数判成红/绿（负对照直接喂合成 dict）。"""
    return {"同功能两份": bool(f.get("同功能两份")),
            "被超越未回收": bool(f.get("被超越未回收")),
            "指针仍指旧版": bool(f.get("指针仍指旧版")),
            "证据目录与在役件混淆": bool(f.get("证据目录与在役件混淆")),
            "any": any(bool(f.get(k)) for k in ("同功能两份", "被超越未回收", "指针仍指旧版", "证据目录与在役件混淆"))}


def cmd_check(as_json: bool = False) -> int:
    f = scan()
    cls = classify_findings(f)
    rows = [{"id": "S1 同功能两份必须被点出", "ok": True, "detail": "%d 组" % len(f["同功能两份"])},
            {"id": "S2 被超越未回收必须被点出", "ok": True, "detail": "%d 件" % len(f["被超越未回收"])},
            {"id": "S3 指针仍指旧版必须被点出", "ok": True, "detail": "%d 处" % len(f["指针仍指旧版"])},
            {"id": "S4 证据目录/在役件混淆必须被点出", "ok": True, "detail": "%d 处" % len(f["证据目录与在役件混淆"])},
            {"id": "S5 扫描**不删**（默认只报；删要走 --recycle）", "ok": True,
             "detail": "默认 mode=scan（recycle 需显式 --recycle）"}]
    # 负对照：合成四类旧件 ⇒ 每类都必须被判红
    negs = []
    for k in ("同功能两份", "被超越未回收", "指针仍指旧版", "证据目录与在役件混淆"):
        synth = {kk: [] for kk in ("同功能两份", "被超越未回收", "指针仍指旧版", "证据目录与在役件混淆")}
        synth[k] = ["合成旧件"] if k != "同功能两份" else [{"canonical": "x", "files": ["x.py", "x.py.bak"]}]
        negs.append(("喂坏：合成 %s" % k, k, classify_findings(synth)[k],
                     "判定红=%s（应红）" % classify_findings(synth)[k]))
 # 2026-10-10 补一条**扫描器级**负对照：上面那些喂的是**合成 dict**（只测分类器）。
#    而这次真出问题的地方在**扫描器**（过度匹配 Chrome 配置）—— 分类器再对也看不出来。
#    做法：往我们自己的树里**真放一个 .old**，扫描必须**扫到它**；同时**浏览器配置里的 .old 不许被扫到**。
    _scan_neg = None
    try:
        _probe_dir = ROOT / "state" / "_selftest_supersede"
        _probe_dir.mkdir(parents=True, exist_ok=True)
        _probe = _probe_dir / "real_superseded_thing.old"
        _probe.write_text("selftest", encoding="utf-8")
        try:
            _hit = any("real_superseded_thing.old" in str(x) for x in scan()["被超越未回收"])
            _browser_hits = [x for x in scan()["被超越未回收"] if "browser_own_profile" in str(x)]
            _scan_neg = (_hit and not _browser_hits,
                         "真放 .old 扫到=%s · 浏览器配置 .old 误报=%d 件" % (_hit, len(_browser_hits)))
        finally:
            _probe.unlink(missing_ok=True)
            try:
                _probe_dir.rmdir()
            except OSError:
                pass
    except Exception as _e:                                      # noqa: BLE001
        _scan_neg = (False, "扫描器级负对照跑不起来：%s" % type(_e).__name__)

 # 2026-10-10 补**四类全真植入**的常驻负对照。
    #    原有四条喂的是**合成 dict** ⇒ 只测分类器；而真出问题的两处都在**扫描器**：
    #      ① 曾整类是死代码（x.py.bak 进不了分组）· ③ 文档说查 AGENTS.md 而代码只查了 .cmd。
    #    这两处**分类器再对也看不出来**。⇒ 四类各真植入一个，**每一类都必须在实扫里被点出**。
    _live_neg = None
    try:
        _d = ROOT / "state" / "_selftest_supersede2"
        _d.mkdir(parents=True, exist_ok=True)
        _f1 = _d / "samefn.py"; _f1b = _d / "samefn.py.bak"          # ① 同功能两份
        _f2 = _d / "leftover.py.old"                                  # ② 被超越未回收
        _f3 = ROOT / "_selftest_ptr.cmd"                              # ③ 指针指旧版
        _d4 = _d / "_diag_live"; _d4.mkdir(exist_ok=True)             # ④ 证据目录放 .py
        _f4 = _d4 / "impl.py"
        _ag = ROOT / "AGENTS.md"; _agbak = _ag.read_bytes() if _ag.is_file() else None
        for _p, _c in ((_f1, "# new\n"), (_f1b, "# old\n"), (_f2, "# old\n"),
                       (_f3, "@echo off\r\nrem _selftest_supersede2/leftover.py.old\r\n"), (_f4, "# x\n")):
            _p.write_text(_c, encoding="utf-8")
        try:
            if _agbak is not None:      # ③ 的另半：canonical 指针也必须抓到
                _ag.write_text(_ag.read_text(encoding="utf-8", errors="replace")
                               + "\n<!-- _selftest_supersede2/leftover.py.old -->\n", encoding="utf-8")
            _r = scan()
            _c1 = any("samefn" in str(x) for x in _r["同功能两份"])
            _c2 = any("leftover.py.old" in str(x) for x in _r["被超越未回收"])
            _c3 = any("_selftest_ptr.cmd" in str(x.get("pointer")) for x in _r["指针仍指旧版"])
            _c3b = (any("AGENTS.md" in str(x.get("pointer")) for x in _r["指针仍指旧版"])
                    if _agbak is not None else True)
            _c4 = any("_diag_live" in str(x.get("file", x)) for x in _r["证据目录与在役件混淆"])
            _live_neg = (all((_c1, _c2, _c3, _c3b, _c4)),
                         "真植入四类: ①两份=%s ②未回收=%s ③cmd=%s ③AGENTS=%s ④证据目录=%s"
                         % (_c1, _c2, _c3, _c3b, _c4))
        finally:
            for _p in (_f1, _f1b, _f2, _f3, _f4):
                _p.unlink(missing_ok=True)
            try:
                _d4.rmdir(); _d.rmdir()
            except OSError:
                pass
            if _agbak is not None:
                _ag.write_bytes(_agbak)
    except Exception as _e3:                                        # noqa: BLE001
        _live_neg = (False, "四类真植入负对照跑不起来：%s" % type(_e3).__name__)

 # 2026-10-10 补扫描器级负对照 2：**③ 指针仍指旧版** 的两半都要有牙。
    #    真植入：一个被超越件 + 两个真指针（根 .cmd 一个、AGENTS.md 一个）⇒ **两半都必须被抓到**。
    _ptr_neg = None
    try:
        _pf = ROOT / "state" / "_selftest_superseded.py"
        _pb = ROOT / "state" / "_selftest_superseded.py.bak"
        _pc = ROOT / "_selftest_pointer.cmd"
        _ag = ROOT / "AGENTS.md"
        _ag_bak = _ag.read_bytes() if _ag.is_file() else None
        _pf.write_text("# selftest\n", encoding="utf-8")
        _pb.write_text("# selftest old\n", encoding="utf-8")
        _pc.write_text("@echo off\r\nrem state/_selftest_superseded.py.bak\r\n", encoding="utf-8")
        try:
            if _ag_bak is not None:
                _ag.write_text(_ag.read_text(encoding="utf-8", errors="replace")
                               + "\n<!-- state/_selftest_superseded.py.bak -->\n", encoding="utf-8")
            _names = [x.get("pointer") for x in scan()["指针仍指旧版"]]
            _cmd_ok = "_selftest_pointer.cmd" in _names
            _ag_ok = ("AGENTS.md" in _names) if _ag_bak is not None else True
            _ptr_neg = (_cmd_ok and _ag_ok,
                        "根 .cmd 抓到=%s · AGENTS.md 抓到=%s" % (_cmd_ok, _ag_ok))
        finally:
            for _p in (_pf, _pb, _pc):
                _p.unlink(missing_ok=True)
            if _ag_bak is not None:
                _ag.write_bytes(_ag_bak)
    except Exception as _e2:                                        # noqa: BLE001
        _ptr_neg = (False, "指针级负对照跑不起来：%s" % type(_e2).__name__)

    # 负对照：全空 ⇒ 必须全绿（不虚报）
    empty = {kk: [] for kk in ("同功能两份", "被超越未回收", "指针仍指旧版", "证据目录与在役件混淆")}
    negs.append(("正控：全空时必须全绿（不虚报）", "ALL", not classify_findings(empty)["any"],
                 "any=%s（应 False）" % classify_findings(empty)["any"]))

    fails = [r for r in rows if not r["ok"]]
    nfr = [n for n in negs if not n[2]]
    if as_json:
        print(json.dumps({"rows": rows, "findings_counts": {k: len(v) for k, v in f.items()},
                          "negatives": [{"n": n, "t": t, "ok": o, "d": d} for n, t, o, d in negs],
                          "pass": len(rows) - len(fails), "fail": len(fails),
                          "neg_pass": len(negs) - len(nfr)}, ensure_ascii=False, indent=1))
    else:
        print("=" * 84)
        print("「新增即清旧」· 判据（含负对照）")
        print("=" * 84)
        for r in rows:
            print("%s %-46s %s" % ("PASS" if r["ok"] else "FAIL", r["id"], r["detail"][:100]))
        print("-" * 84)
        if _scan_neg is not None:
            _o, _d = _scan_neg
            negs.append(("扫描器级：真 .old 要扫到 / 浏览器件不许误报", "扫描器", _o, _d))
        if _ptr_neg is not None:
            _o, _d = _ptr_neg
            negs.append(("指针级：根 .cmd 与 AGENTS.md 两半都要抓到", "扫描器", _o, _d))
        if _live_neg is not None:
            _o, _d = _live_neg
            negs.append(("四类全真植入：每类都必须在实扫里被点出", "扫描器", _o, _d))
 # 2026-10-13 修（坏尺子·把失败漏成 0）：`nfr` 原先在三段 `negs.append(...)` **之前**就算完了，
        #    于是后追加的扫描器级负对照**永远进不了失败表** ⇒ 逐行打印有 FAIL、总数却报 FAIL 0
        #    （"没验的/失败的被记成绿"，比对象坏了更危险）。这里追加完**重算一次**。
        nfr = [n for n in negs if not n[2]]
        for n, t, o, d in negs:
            print("%s 负对照[%-6s] %-30s %s" % ("PASS" if o else "FAIL", t, n[:30], d[:80]))
        print("-" * 84)
        print("判据 PASS %d · FAIL %d ｜ 负对照 PASS %d · FAIL %d"
              % (len(rows) - len(fails), len(fails), len(negs) - len(nfr), len(nfr)))
    # 判据本身永远 PASS（它是"扫出来没有"的事实报告）；闸的语义 = **有旧件就非零退出**
    return 1 if cls["any"] else 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                    # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="「新增即清旧」机器判据（扫四类 · 只报 · 回收走回收站）")
    ap.add_argument("verb", nargs="?", default="scan", choices=["scan", "check", "recycle"])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--recycle", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.check or a.verb == "check":
        return cmd_check(a.json)
    if a.recycle or a.verb == "recycle":
        f = scan()
        targets = f["被超越未回收"]
        print("将要送回收站的「被超越未回收」%d 件：%s" % (len(targets), "、".join(targets[:8]) or "无"))
        if not targets:
            print("（无目标；不动作）")
            return 0
        moved, fails, gone = _recycle(targets)
        print("实际搬运 %d 件 · 失败 %d · 已消失 %d" % (len(moved), len(fails), len(gone)))
        for x in fails[:6]:
            print("  失败：%s" % x)
        return 0 if not fails else 1
    return cmd_scan(a.json)


if __name__ == "__main__":
    raise SystemExit(main())
