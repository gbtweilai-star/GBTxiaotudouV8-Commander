# -*- coding: utf-8 -*-
"""逐页绑定的审查 —— 每一页都要扫到、主脑要看得见（主人令 2026-10-11，逐字）

主人原话：
  「记得每一页都要亲自扫描到触手双向绑定好，确保所有的状态主脑第一时间都能知道，
    别搞得像无关要紧是的」

## 为什么要有这一件
  页面不是画给人看的装饰 —— 它是主脑的眼睛。一页存在，但页里的 id 在主脑数据里
  找不到，等于这一页主脑看不见；页找得到、节点却没有承载（bundle），等于没接上触手。
  这两种都不会报错，只会静默地少一页。所以必须逐页扫，不能抽样。

## 三查（每一页都过一遍，不抽样）
  ① 每一页都要能对上主脑：页里的 data-kind 必须在 brain-data.js 的 nodes 里找得到
  ② 每一页都要接上触手：那个节点必须有 bundle（承载），且 impl 状态如实
  ③ 主脑数据要新鲜：brain-data.js 的 at 与现在的差超过阈值 ⇒ 黄警（状态不是第一时间的）
     功能页另查：有没有引用 brain-data.js（拿不到数据 = 看不见状态）

## 负控（真植入）
  ① 塞一个主脑数据里没有的 data-kind ⇒ 必须点名（死页）
  ② 塞一个没有 bundle 的节点 ⇒ 必须点名（没接触手）
  ③ 把主脑数据的 at 改旧 ⇒ 必须报黄（不新鲜）

用法: py -3.14 -X utf8 tools/codex-scripts/page-bind-check.py [--json] [--selftest]
退出码：0 = 无红；1 = 有红（死页 / 没接触手）；3 = 不适用。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")   # type: ignore[attr-defined]
    except Exception:
        pass

WS = pathlib.Path(__file__).resolve().parents[2]
BRAIN = WS / "holo_pet_w3" / "brain"
CAPS = BRAIN / "caps"
DATA = BRAIN / "brain-data.js"
STALE_HOURS = 24.0
# 🔴 2026-10-11 加（主人令「确保所有的状态主脑第一时间都能知道」）：
#    功能页分两种 —— **活的**（引 brain-data.js / 自己的 data.js / fetch / 全局，渲染时取数）
#    与**快照的**（生成时把数据**烤进 HTML**）。烤的页不会自己变新：
#    实测 ai-board 烤的是 10-10 00:41（**25 小时前**）、cloud-plugins/cloud-status 烤的
#    是 10-08（**3 天前**）、plugins-mesh 烤的是 10-04（**6 天前**）—— 页好好地在盘上，
#    主脑看到的却是几天前的状态。⇒ 快照页必须**带生成时间戳**且**不许旧过阈值**。
SNAPSHOT_MAX_HOURS = 24.0
_TS = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})")


def load_brain(path=None):
    f = pathlib.Path(path or DATA)
    if not f.is_file():
        return None
    t = f.read_text(encoding="utf-8", errors="replace")
    i = t.find("{")
    if i < 0:
        return None
    try:
        return json.loads(t[i:].rstrip().rstrip(";"))
    except Exception:  # noqa: BLE001
        return None


def page_kinds(caps_dir=None):
    d = pathlib.Path(caps_dir or CAPS)
    if not d.is_dir():
        return None
    out = {}
    for f in sorted(d.glob("*.html")):
        if f.name == "index.html":
            continue
        t = f.read_text(encoding="utf-8", errors="replace")
        m = re.search('data-kind="([^"]+)"', t)
        out[f.name] = m.group(1) if m else None
    return out


def feature_pages(brain_dir=None):
    """21 个功能页：抽它是不是"烤了时间戳的快照页"。"""
    d = pathlib.Path(brain_dir or BRAIN).parent
    out = {}
    if not d.is_dir():
        return out
    for sub in sorted(d.iterdir()):
        f = sub / "index.html"
        if not sub.is_dir() or not f.is_file():
            continue
        t = f.read_text(encoding="utf-8", errors="replace")
        m = _TS.search(t)
        # 🔴 2026-10-11 修：relative_to(WS) 在**仓外文件**上会抛 ValueError，把整条判据弄崩。
        #    本仓早有这条教训（audit-dead-judgments.py 的原话：「别让打印文件名这种小事
        #    把整条判据弄崩」）—— 自检喂临时目录时我就撞上了。⇒ 相对化失败就退成绝对路径。
        try:
            _rel = str(f.relative_to(WS)).replace(chr(92), "/")
        except ValueError:
            _rel = str(f).replace(chr(92), "/")
        # 🔴 2026-10-11 收紧（**别把设计意图当故障**）：
        #    只有**自动生成**的页才该"跟着状态变新"——认它头部那句「自动生成，别手改」。
        #    实测：blueprint 与 digital-human 头里**没有**这句、全仓也找不到写它们的脚本
        #    ⇒ 它们是**手写页**，页里那个时间戳**不是"生成时间"**（可能是内容自己的日期）。
        #    对它们报"烤旧了"= 把设计意图当故障 ⇒ 只对自动生成页查新鲜度。
        # 🔴 2026-10-11 放宽（**我的标记口径太窄，误判了两个页**）：
        #    本仓对"自动生成的页"有**两套**约定，我只认了第一套 ——
        #      ① 「自动生成，别手改。重建：…」（cap-pages / ai-board / brain-feed 那一家）
        #      ② **deck 家族的约定**：data-data-kind="快照" + data-data-at="<时刻>"
        #         （code-deck.py L336 · exec-deck.py L234 都是这么写的，而且 exec-deck L195
        #          的设计原话就是「页面**必须把快照时刻与重生成命令写在脸上**」）
        #    ⇒ 只认①会把②误判成"无标记页（判不了）"，而它们其实**自己把时刻写在脸上了**。
        # 🔴 2026-10-11 加第三套约定（**手写页声明**）：
        #    实测 digital-human 是**手写页**（162KB，全仓 0 个写它的脚本）——
        #    对它报「无标记页（判不了）」= 把设计意图当故障。⇒ 页里明写「手写页」即认。
        _hand = "手写页" in t
        _auto = (("自动生成" in t and "别手改" in t)
                 or ('data-data-kind="快照"' in t and "data-data-at" in t))
        out[sub.name] = {"file": _rel, "cooked_at": m.group(1) if m else None,
                         "auto_generated": _auto, "hand_written": _hand}
    return out


def feature_freshness(now=None):
    """逐功能页看"烤的时间"有多旧。没时间戳 = 活的（不算旧）。"""
    pages = feature_pages()
    stale, fresh, untimed, hand, declared = [], [], [], [], []
    for name, info in sorted(pages.items()):
        at = info.get("cooked_at")
        if not at:
            untimed.append(name)
            continue
        if not info.get("auto_generated"):
            # 🔴 2026-10-11 勘误：这里原来叫 hand（手写页），**叫错了**。
            #    实测：cloud-plugins / cloud-status / code-deck / exec-deck / plugins-mesh / energy
            #    **都是生成器写的**（我当场跑过 cloud-plugins.py gen / code-deck.py --html，页真的变了），
            #    只是**那些生成器不在页里留标记** ⇒ 从页本身**判不出**它是生成物还是手写物。
            #    ⇒ 诚实口径：这一档叫 **无标记页（判不了）**，不许冒充"手写"（那是编事实）。
            if info.get("hand_written"):
                # 2026-10-11：页里**明写「手写页」**的（如 digital-human，162KB 全仓 0 个生成器）
                #   ⇒ 自报手写，单列一档：不再算「判不了」，也**不建议它补重建命令**（它本就没有生成器）。
                declared.append(name)
            else:
                hand.append(name)
            continue
        h = stale_hours(at, now)
        if h is not None and h > SNAPSHOT_MAX_HOURS:
            stale.append({"page": name, "cooked_at": at, "hours": round(h, 1)})
        else:
            fresh.append({"page": name, "cooked_at": at, "hours": round(h or 0, 1)})
    return {"stale": stale, "fresh": fresh, "untimed": untimed,
            "hand_written": hand, "hand_declared": declared, "total": len(pages)}


def stale_hours(at_text, now=None):
    try:
        t = _dt.datetime.fromisoformat(str(at_text))
    except Exception:  # noqa: BLE001
        return None
    if t.tzinfo:
        now = now or _dt.datetime.now(tz=t.tzinfo)
    else:
        now = now or _dt.datetime.now()
    return (now - t).total_seconds() / 3600.0


def audit(brain=None, kinds=None, now=None):
    brain = brain if brain is not None else load_brain()
    kinds = kinds if kinds is not None else page_kinds()
    if brain is None or kinds is None:
        return {"ok": False, "why": "拿不到主脑数据或页面目录", "dead": [], "unbound": [],
                "pages": 0, "nodes": 0}
    by_id = {n.get("id"): n for n in (brain.get("nodes") or [])}
    dead, unbound, fine = [], [], 0
    for page, kind in sorted(kinds.items()):
        if not kind:
            dead.append({"page": page, "kind": None, "why": "页里没有 data-kind（抽不到 id）"})
            continue
        n = by_id.get(kind)
        if n is None:
            dead.append({"page": page, "kind": kind, "why": "主脑数据里没有这个 id ⇒ 主脑看不见这一页"})
            continue
        if not n.get("bundle"):
            unbound.append({"page": page, "kind": kind, "why": "节点没有 bundle ⇒ 没接上触手"})
            continue
        fine += 1
    st = stale_hours(brain.get("at"), now)
    return {"ok": True, "pages": len(kinds), "nodes": len(by_id),
            "fine": fine, "dead": dead, "unbound": unbound,
            "at": brain.get("at"), "stale_hours": st,
            "stale": (st is not None and st > STALE_HOURS)}


def selftest():
    ok = []
    b = load_brain()
    k = page_kinds()
    ok.append(("真件·读到主脑数据", bool(b and b.get("nodes")),
               "%d 个节点" % len(b["nodes"]) if b else "读不到"))
    ok.append(("真件·逐页读到 data-kind（不抽样）", bool(k) and len(k) > 100,
               "%d 页" % (len(k) or 0)))
    r = audit(b, k) if (b and k) else {}
    ok.append(("真件·全部页面都能对上主脑且有 bundle",
               bool(r.get("dead") == [] and r.get("unbound") == []),
               "死页 %d · 没接触手 %d" % (len(r.get("dead") or []), len(r.get("unbound") or []))))
    kk = dict(k)
    kk["_zz_probe.html"] = "绝不存在的能力位zzz"
    r2 = audit(b, kk)
    ok.append(("真植入负控·塞一个主脑没有的 data-kind ⇒ 必须点名",
               any(x["page"] == "_zz_probe.html" for x in r2["dead"]),
               "点名 %d 条死页" % len(r2["dead"])))
    b2 = json.loads(json.dumps(b))
    b2["nodes"].append({"id": "zz_nobundle", "impl": True})
    k2 = dict(k); k2["_zz_nb.html"] = "zz_nobundle"
    r3 = audit(b2, k2)
    ok.append(("真植入负控·塞一个没有 bundle 的节点 ⇒ 必须点名没接触手",
               any(x["kind"] == "zz_nobundle" for x in r3["unbound"]),
               "点名 %d 条没接触手" % len(r3["unbound"])))
    b3 = json.loads(json.dumps(b))
    b3["at"] = "2020-01-01T00:00:00"
    r4 = audit(b3, k)
    ok.append(("真植入负控·主脑数据改旧 ⇒ 必须报不新鲜", bool(r4.get("stale")),
               "旧 %.1f 小时" % (r4.get("stale_hours") or 0)))
    # 真植入负控④：造一个"烤旧了"的功能页 ⇒ 新鲜度检查必须点名
    # 🔴 首跑这条**自己把我抓了**：feature_pages 的参数是 **brain 目录**（它内部取 .parent 得到
    #    holo_pet_w3），而我第一次传的是已经是父目录的 root ⇒ 它扫到临时目录的上一层去了、
    #    点名为 []。⇒ 自检的错也要当真错修，不许放水。现在按真语义传 brain 目录。
    import tempfile as _tf
    with _tf.TemporaryDirectory() as td:
        base = pathlib.Path(td) / "holo_pet_w3"
        brain_dir = base / "brain"
        brain_dir.mkdir(parents=True)
        (base / "zz_old").mkdir(parents=True)
        (base / "zz_old" / "index.html").write_text(
            "<html>生成 2020-01-01T00:00:00</html>", encoding="utf-8")
        (base / "zz_live").mkdir(parents=True)
        (base / "zz_live" / "index.html").write_text(
            "<html>活页，没有烤时间戳</html>", encoding="utf-8")
        pages = feature_pages(brain_dir)
        _old = [k for k, v in pages.items()
                if v.get("cooked_at") and (stale_hours(v["cooked_at"]) or 0) > SNAPSHOT_MAX_HOURS]
        ok.append(("真植入负控·造一个烤旧了的快照页 ⇒ 必须点名", _old == ["zz_old"],
                   "点名 %s" % _old))
        ok.append(("真件·活页（无烤时间戳）不算旧", "zz_live" not in _old,
                   "点名 %s" % _old))
    bad = [n for n, c, _ in ok if not c]
    for n, c, d in ok:
        print("  %-52s %s  (%s)" % (n, "✅" if c else "❌", d))
    print("")
    print("page-bind-check 自检: %s（%d 条）"
          % ("全部通过" if not bad else "%d 条失败" % len(bad), len(ok)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description="逐页绑定审查（每一页都要扫到）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    r = audit()
    if not r.get("ok"):
        print("逐页绑定审查 · 不适用：%s" % r.get("why"))
        return 3
    print("=" * 74)
    print("逐页绑定审查 —— 每一页都要扫到、主脑要看得见")
    print("=" * 74)
    print("  页面 %d 个 · 主脑节点 %d 个 · 对得上且接了触手的 %d 个"
          % (r["pages"], r["nodes"], r["fine"]))
    print("  主脑数据 at = %s（%.1f 小时前）%s"
          % (r.get("at"), r.get("stale_hours") or 0,
             "  ⚠️ 不新鲜（超 %.0f 小时）" % STALE_HOURS if r.get("stale") else "  ✅ 新鲜"))
    print("")
    if r["dead"]:
        print("  🔴 主脑看不见的页（页在，id 对不上）—— %d 个" % len(r["dead"]))
        for x in r["dead"][:20]:
            print("      %s → %s（%s）" % (x["page"], x["kind"], x["why"]))
    if r["unbound"]:
        print("  🔴 没接上触手的页（节点没有 bundle）—— %d 个" % len(r["unbound"]))
        for x in r["unbound"][:20]:
            print("      %s → %s（%s）" % (x["page"], x["kind"], x["why"]))
    if not r["dead"] and not r["unbound"]:
        print("  ✅ 每一页都对得上主脑，且每一页都接了触手")
    print("")
    f = feature_freshness()
    print("  功能页新鲜度：**带标记的生成页** 旧 %d · 新鲜 %d ｜ 无时间戳(活的) 11 类 %d ｜ **无标记页(判不了)** %d（共 %d）"
          % (len(f["stale"]), len(f["fresh"]), len(f["untimed"]),
             len(f.get("hand_written") or []), f["total"]))
    if f.get("hand_written"):
        print("      无标记页（头里没有「自动生成/别手改/重建」⇒ **从页本身判不出它是生成物还是手写物**，")
        print("      故不按新鲜度判 —— 但那不等于它们不过期）：%s" % "、".join(f["hand_written"]))
    if f.get("hand_declared"):
        print("      自报手写页（页里明写「手写页」⇒ 不参与新鲜度判，也不需要它补重建命令）：%s"
              % "、".join(f["hand_declared"]))
    if f.get("hand_written"):
        print("      🔴 建议：这几页的生成器**在页里补一句重建命令**（像 ai-board 那样），")
        print("         否则「主脑看到的它新不新」永远没人能机检。")
    for x in f["stale"]:
        print("      ⚠️ %s 烤的是 %s（**%.1f 小时前**）⇒ 主脑看到的是旧状态"
              % (x["page"], x["cooked_at"], x["hours"]))
    if not f["stale"]:
        print("      ✅ 没有烤过期的快照页")
    print("")
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    red = bool(r["dead"] or r["unbound"])
    return 1 if red else 0


if __name__ == "__main__":
    raise SystemExit(main())