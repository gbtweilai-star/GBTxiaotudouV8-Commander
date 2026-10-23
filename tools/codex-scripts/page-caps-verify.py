# -*- coding: utf-8 -*-
"""申报可信度检查：`state/page-caps.json` 里申报的能力位，**在页面里找得到证据吗**。

为什么要有这一件：`page-bindings.py` 判的是"有没有申报"，它**不看申报跟页面内容对不对得上**。
申报可以写得很漂亮但跟页面无关 —— 那就是"洗白"。本件专查这一格：

  对每页的每个申报位，算三档证据：
    强  —— 页里出现该位**名字**
    中  —— 页里出现该位 desc 里的关键名词（≥2 个不同词命中）
    弱  —— 页里都没有（只剩申报书上的字）

用法：
  py -3.14 -X utf8 tools/codex-scripts/page-caps-verify.py            # 报读数（弱申报 exit 1）
  py -3.14 -X utf8 tools/codex-scripts/page-caps-verify.py --selftest # 负对照：塞假申报必报弱
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[2]
PANEL = ROOT / "holo_pet_w3" / "panel" / "index.html"
DECL = ROOT / "state" / "page-caps.json"
OUT = ROOT / "state" / "page-caps-verify.json"

STOP = set("的一是在有和就不都也很与及其这那些为以对从到被把或而如果所以因为能力位可以主人令本次全部当前现在逐步每个所有以及然后就是这种那个这样那样里面外面上面下面".replace(" ", ""))


def pages() -> dict:
    txt = PANEL.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"const PAGES = \[(.*?)\n\];", txt, re.S)
    out = {}
    if not m:
        return out
    for mm in re.finditer(r'id:\s*"([^"]+)"[^}]*?rel:\s*"([^"]+)"', m.group(1)):
        out[mm.group(1)] = mm.group(2)
    return out


def caps() -> dict:
    sys.path.insert(0, str(ROOT))
    try:
        from gbt_allinone.caps_registry import BENIGN_CAPS
        return dict(BENIGN_CAPS)
    except Exception:                                                 # noqa: BLE001
        return {}


def nouns(desc: str) -> list:
    """关键名词：ASCII ≥4 位 + **中文二元/三元组**（整句没空格也能切出真词），排掉泛用词。"""
    ws = re.split(r"[^0-9A-Za-z\u4e00-\u9fff]+", desc or "")
    out = []
    for w in ws:
        if not w or w in STOP:
            continue
        cjk = re.findall(r"[\u4e00-\u9fff]", w)
        asc = re.findall(r"[A-Za-z0-9_]+", w)
        # 中文：2-gram（这些才是"只读/数据/日志/后台"这类真词）
        for run in re.findall(r"[\u4e00-\u9fff]{2,}", w):
            for i in range(len(run) - 1):
                g = run[i:i + 2]
                if g not in STOP:
                    out.append(g)
        for a in asc:
            if len(a) >= 4 and not re.fullmatch(r"[0-9]+", a):
                out.append(a)
        _ = (cjk, asc)
    # 去重保序
    seen, res = set(), []
    for x in out:
        if x not in seen and x not in STOP:
            seen.add(x)
            res.append(x)
    return res[:24]


def verify(decl_override: dict | None = None) -> dict:
    pgs, cp = pages(), caps()
    decl = json.loads(DECL.read_text(encoding="utf-8"))
    if decl_override:
        decl.update(decl_override)
    rows = []
    for pid, meta in decl.items():
        if pid.startswith("_") or not isinstance(meta, dict):
            continue
        rel = pgs.get(pid)
        rec = {"页": pid, "申报": meta.get("caps") or [], "落点": rel, "证据": {}}
        if not rel:
            rec["判定"] = "页不在面板清单（申报了幽灵页）"
            rec["最强"] = "弱"
            rows.append(rec)
            continue
        f = (PANEL.parent / rel).resolve()
        if not f.is_file():
            rec["判定"] = "落点不在盘"
            rec["最强"] = "弱"
            rows.append(rec)
            continue
        h = f.read_text(encoding="utf-8", errors="replace")
        # 申报可显式给证据（file 相对面板目录；needle 必须真的出现在那个件里）
        ev = meta.get("evidence") or {}
        ev_text, ev_ok, ev_path = "", False, None
        if isinstance(ev, dict) and ev.get("file") and ev.get("needle"):
            ef = (PANEL.parent / ev["file"]).resolve()
            ev_path = str(ev["file"])
            if ef.is_file():
                ev_text = ef.read_text(encoding="utf-8", errors="replace")
                ev_ok = ev["needle"] in ev_text
        best = "弱"
        for c in rec["申报"]:
            d = (cp.get(c) or {}).get("desc", "")
            hit_name = bool(re.search(r"\b" + re.escape(c) + r"\b", h))
            nz = [w for w in nouns(d) if w in h]
            ev_hit = bool(ev_ok and (
                c in (ev.get("needle") or "")
                or ev.get("needle") in (d or "")
                or c in (ev.get("file") or "")
                or c in ev_text))
            lvl = "强" if hit_name else ("中" if len(nz) >= 2 else ("中" if ev_hit else "弱"))
            rec["证据"][c] = {"名字命中": hit_name, "desc名词命中": nz[:5],
                             "申报证据件": ev_path, "申报证据命中": ev_hit, "档": lvl}
            if lvl == "强":
                best = "强"
            elif lvl == "中" and best == "弱":
                best = "中"
        rec["最强"] = best
        rows.append(rec)
    weak = [r for r in rows if r["最强"] == "弱"]
    res = {"at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"), "页数": len(rows),
           "强": sum(1 for r in rows if r["最强"] == "强"),
           "中": sum(1 for r in rows if r["最强"] == "中"),
           "弱": len(weak), "逐页": rows}
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def main() -> int:
    if "--selftest" in sys.argv:
        # ① 幽灵页：清单里没有这个 id ⇒ 必须判弱
        r1 = verify({"页不存在的幽灵": {"caps": ["health"], "why": "负对照①：幽灵页"}})
        ghost = [x for x in r1["逐页"] if x["页"] == "页不存在的幽灵"][0]
        # ② 空申报：caps=[] ⇒ 必须判弱
        r2 = verify({"welcome": {"caps": [], "why": "负对照②：空申报"}})
        empty = [x for x in r2["逐页"] if x["页"] == "welcome"][0]
        ok1, ok2 = ghost["最强"] == "弱", empty["最强"] == "弱"
        print("负对照①幽灵页 ⇒ %s（应弱）" % ghost["最强"])
        print("负对照②空申报 ⇒ %s（应弱）" % empty["最强"])
        print("自检：%s" % ("PASS" if (ok1 and ok2) else "FAIL"))
        return 0 if (ok1 and ok2) else 1

    r = verify()
    print("申报可信度：%d 页 · 强 %d · 中 %d · **弱 %d**"
          % (r["页数"], r["强"], r["中"], r["弱"]))
    for x in r["逐页"]:
        if x["最强"] != "强":
            print("  %-14s %-4s 申报=%s 证据=%s"
                  % (x["页"], x["最强"], ",".join(x["申报"]),
                     json.dumps(x["证据"], ensure_ascii=False)[:160]))
    return 0 if r["弱"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
