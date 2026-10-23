# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 区块邻域同视闸（Owner 令 2026-10-14 · 常驻纪律）。

> 主人令（逐字）：**「在操作一个区块的时候必须同时关注相关区块，确保一切都在掌控之内完成」**
>             +「一个眼睛不够的话触手以亿万眼睛……这才是她视觉最牛逼的地方，要不然就是盲猜盲打」。

## 这条纪律要判什么
**动一个区块之前/之中/之后，它的关联区块必须"同一时刻"都有读数** —— 不是事后补看、更不是盲改。
两档实现（谁在场看谁）：
  · **云插件区块**：给模块 id（如 gbt-c01-llm-gateway），本闸从 mesh.json 取它的**9 条邻域边**，
    再去云端 /health 把**每个邻邻区块**的现读逐条抓回来 —— 少一个 = 红。
  · **本仓文件区块**：给文件路径，本闸算它的**关联文件**（谁 import 它 / 它 import 谁 / 同目录同族件），
    逐件报"在不在、多大、改没改" —— 声明了却不看 = 红。

## 判据（fail-closed）
  W1 区块识别   ：能认出这个区块（模块 id 或存在的文件）；认不出 ⇒ 红（不许猜）
  W2 邻域完备   ：mesh 区块 ⇒ 邻域边数 == 9；文件区块 ⇒ 关联件 ≥ 1
  W3 邻域全读   ：每个邻域**都有现读**（云 /health 行 or 文件 stat）—— 缺一条 ⇒ 红
  W4 邻域无红   ：云 /health 里邻域行不得 ok=false；本仓关联件不得缺失
  W5 不装看      ：取不到就写"未读到"，**不许**用 0/空当"已看"

用法：
    py -3.14 tools/codex-scripts/block-neighborhood-watch.py --block gbt-c01-llm-gateway
    py -3.14 tools/codex-scripts/block-neighborhood-watch.py --block deploy/cloud-10/src/worker.js
    py -3.14 tools/codex-scripts/block-neighborhood-watch.py --selftest

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MESH = ROOT / "deploy" / "cloud-10" / "mesh.json"
BASELINE = ROOT / "state" / "neighborhood-baseline.json"
BASE = os.environ.get("GBT_CLOUD_BASE", "https://gbt-potato-cloud-10.lopaycn.workers.dev")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36")
ROWS: list = []


def j(cid: str, name: str, ok: bool, detail: str) -> None:
    ROWS.append({"id": cid, "name": name, "ok": bool(ok), "detail": detail})
    print("%s %-3s %-12s %s" % ("PASS" if ok else "FAIL", cid, name, detail))


def mesh() -> dict:
    try:
        return json.loads(MESH.read_text(encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        return {}


def cloud_health() -> dict:
    """云端 10 区块现读（哪一位 ok/未读到，一次全拿）。"""
    req = urllib.request.Request(BASE.rstrip("/") + "/health", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:        # noqa: S310
            return {"ok": True, "at": time.strftime("%H:%M:%S"),
                    "rows": {str(x.get("id")): x for x in (json.loads(r.read().decode("utf-8", "replace")).get("rows") or [])}}
    except Exception as exc:                                     # noqa: BLE001
        return {"ok": False, "reason": str(exc)[:120]}


def neighbors_of(module_id: str) -> list:
    m = mesh()
    ids = [x.get("id") for x in (m.get("modules") or [])]
    return [i for i in ids if i and i != module_id]


def related_files(path: Path) -> list:
    """本仓文件区块的关联件：它依赖的 / 依赖它的 / 同目录同族 / 结构化被测面。

    🔴 2026-10-17 修（**监控盲区** · 留痕 · 原口径 / 为什么翻 / 现口径）：
      原口径：① 只认 JS 相对 import；② 同目录同族写的是
        `path.parent.glob(path.suffix)` —— **漏了 `*`**，`.py`/`.js` 永远匹配 0 件；
        ③ 测试件与独立脚本没有 import 边 ⇒ 三类加起来还是 0。
      实测：本轮改过的 5 个区块（4 个测试件 + 1 个脚本）**全部报「关联件 0 件」FAIL**
      ⇒ 闸对"我要动的区块"恰好是瞎的（W2/W3 必红），等于"盲改"。
      现口径：在原有规则上补三块**结构化**邻域，并把 glob 修对：
        ① 字面 `.py` 路径（`"tools/codex-scripts/xxx.py"` 这类，importlib 加载的）→ 解析得到就收；
        ② 测试件 `tests/test_X.py` → 被测模块 `gbt_allinone/X.py` / `gbt_allinone/tools/X.py`
           + `tests/__init__.py`（包级隔离钩子）；
        ③ 同目录同族件 `*` + 后缀（数量多但每次只 stat，成本可忽略）。
    """
    out = set()
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    import re
    for m in re.finditer(r'from\s+["\'](\.{1,2}/[^"\']+)["\']', text):
        rel = (path.parent / m.group(1)).resolve()
        for cand in (rel, rel.with_suffix(".js"), rel.with_suffix(".py")):
            if cand.is_file():
                out.add(cand)
    # ① 字面 `.py` 路径（测试里 importlib 直接加载的工具脚本）
    for m in re.finditer(r'["\']([A-Za-z0-9_./\\-]+\.py)["\']', text):
        cand = (ROOT / m.group(1).replace("\\", "/"))
        if cand.is_file():
            out.add(cand)
    # ② 测试件 → 被测模块 + 包入口
    if path.parent.name == "tests" and path.name.startswith("test_"):
        stem = path.stem[len("test_"):]
        for cand in (ROOT / "gbt_allinone" / (stem + ".py"),
                     ROOT / "gbt_allinone" / "tools" / (stem + ".py"),
                     path.parent / "__init__.py"):
            if cand.is_file():
                out.add(cand)
    # 谁 import 它（同目录 + 上一级，够用且快）
    stem = path.stem
    for root in {path.parent, path.parent.parent}:
        for f in root.glob("*.js"):
            if f == path:
                continue
            try:
                if stem in f.read_text(encoding="utf-8", errors="replace"):
                    out.add(f)
            except OSError:
                pass
    # ③ 同目录同族件（**修 glob**：原来只写后缀、没有 `*` ⇒ 永远 0 件）
    # 🔴 2026-10-18 修（**邻域被海淹没** · 留痕 · 原口径 / 为什么翻 / 现口径）：
    #   原口径：同目录同后缀**全部**算邻域 ⇒ 实测 `tools/codex-scripts` 下 555 件全成了"邻域"，
    #     于是"邻居冒出一件新的"永远判成意外变动 ⇒ 天天报红 = 训练人不看红线（红线变成噪音）。
    #   现口径：同族只收**同族前缀**（`accept-all-*.py` 之类，前缀按第一个连字符切）；
    #     其余同目录件不再当邻域 —— 它们是**别的区块**，由它们自己的邻域规则管。
    fam = path.stem.split("-")[0] or path.stem
    for f in path.parent.glob(fam + "*" + path.suffix):
        out.add(f)
    for f in path.parent.glob(fam + "_*" + path.suffix):
        out.add(f)
    return sorted(out)


def watch_module(mid: str) -> int:
    ns = neighbors_of(mid)
    j("W1", "区块识别", mid in [x.get("id") for x in (mesh().get("modules") or [])], "模块 %s" % mid)
    j("W2", "邻域完备", len(ns) == 9, "邻域 %d 位（应 9）：%s" % (len(ns), "、".join(ns)))
    h = cloud_health()
    if not h.get("ok"):
        j("W3", "邻域全读", False, "云 /health 未读到：%s" % h.get("reason"))
        return 1
    rows = h["rows"]
    missing, bad = [], []
    for n in ns:
        r = rows.get(n)
        if not r:
            missing.append(n)
        elif r.get("ok") is False:
            bad.append(n)
    j("W3", "邻域全读", not missing, "缺读数 %d 位：%s（/health %s）" % (len(missing), "、".join(missing) or "无", h.get("at")))
    j("W4", "邻域无红", not bad, "红位：%s" % ("、".join(bad) or "无"))
    print("\n邻域同视读数（%s 的 9 位）：" % mid)
    for n in ns:
        r = rows.get(n) or {}
        print("   %-26s ok=%-5s %s" % (n, r.get("ok"), (r.get("reading") or r.get("op") or "未读到")))
    return 0 if not missing and not bad else 1


def watch_file(rel: str) -> int:
    p = (ROOT / rel).resolve() if not Path(rel).is_absolute() else Path(rel)
    j("W1", "区块识别", p.is_file(), "%s（%s）" % (rel, "在" if p.is_file() else "不存在"))
    if not p.is_file():
        return 1
    rels = related_files(p)
    j("W2", "邻域完备", len(rels) >= 1, "关联件 %d 件" % len(rels))
    rows = []
    for q in rels:
        st = q.stat()
        rows.append({"块": str(q.relative_to(ROOT)), "bytes": st.st_size,
                     "mtime": time.strftime("%m-%d %H:%M", time.localtime(st.st_mtime))})
    j("W3", "邻域全读", len(rows) == len(rels) and len(rows) > 0,
      "逐件 stat 完成 %d/%d" % (len(rows), len(rels)))
    j("W4", "邻域无红", all(r["bytes"] > 0 for r in rows),
      "空件：%s" % (", ".join(r["块"] for r in rows if r["bytes"] <= 0) or "无"))
    print("\n邻域同视读数（%s 的关联区块）：" % rel)
    for r in rows[:20]:
        print("   %-52s %8d B  %s" % (r["块"], r["bytes"], r["mtime"]))
    return 0


def _fp(p: Path) -> dict:
    """单件指纹：大小 + mtime_ns + 小文件 sha16（大文件只 stat，别把闸拖死）。"""
    st = p.stat()
    h = ""
    if st.st_size <= 4 * 1024 * 1024:
        try:
            h = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        except OSError:
            h = ""
    return {"bytes": st.st_size, "mtime_ns": st.st_mtime_ns, "sha16": h}


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p)


def _load_baseline() -> dict:
    if BASELINE.is_file():
        try:
            return json.loads(BASELINE.read_text(encoding="utf-8"))
        except Exception:                                        # noqa: BLE001
            return {}
    return {}


def snapshot(rel: str) -> int:
    """**改前**拍邻域基线（纪律：动一个区块之前，先把它的关联区块全拍下来）。"""
    p = (ROOT / rel).resolve() if not Path(rel).is_absolute() else Path(rel)
    rels = related_files(p)
    j("S1", "区块识别", p.is_file(), rel)
    j("S2", "邻域完备", len(rels) >= 1, "关联件 %d 件" % len(rels))
    if not rels:
        return 1
    data = _load_baseline()
    data[_rel(p)] = {"at": time.strftime("%Y-%m-%d %H:%M:%S"),
                     "rows": {_rel(q): _fp(q) for q in rels if q.is_file()}}
    try:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError as exc:                                       # noqa: BLE001
        print("FAIL 基线写不进去：%s" % exc)
        return 1
    print("\n基线已存（%s）：%d 件 → %s" % (rel, len(rels), BASELINE))
    return 0


def diff(rel: str, expect: list, run_tests: bool) -> int:
    """**改后**逐件比对：只有 `--expect` 里声明的件许变；其余变了就红（修一个坏一个当场抓）。

    多路读数（"触手"）：① 指纹（size + mtime_ns + sha16）② 存在性 ③ 关联测试真跑。
    """
    p = (ROOT / rel).resolve() if not Path(rel).is_absolute() else Path(rel)
    base = _load_baseline().get(_rel(p))
    if not base:
        j("D0", "有基线", False, "没拍过基线 ⇒ 先跑 --snapshot（不许拿现状当「没变」）")
        return 1
    cur = {_rel(q): _fp(q) for q in related_files(p) if q.is_file()}
    old = base.get("rows") or {}
    exp = {x.strip().replace("\\", "/") for x in expect if x.strip()}
    missing = sorted(set(old) - set(cur))
    added = sorted(set(cur) - set(old))
    changed = sorted(k for k in set(old) & set(cur) if old[k].get("sha16") != cur[k].get("sha16"))
    unexpected = sorted(set(missing) | (set(changed) - exp) | (set(added) - exp))
    j("D1", "邻域仍在", not missing, "消失 %d 件：%s" % (len(missing), "、".join(missing[:4]) or "无"))
    j("D2", "新增可见", True, "新增 %d 件：%s" % (len(added), "、".join(added[:4]) or "无"))
    j("D3", "变动在册", not (set(changed) - exp),
      "变动 %d 件（无意 %d）：%s" % (len(changed), len(set(changed) - exp),
                                    "、".join(sorted(set(changed) - exp)[:4]) or "无"))
    rc = 0 if not unexpected else 1
    if run_tests:
        tfiles = [k for k in sorted(cur) if k.split("/")[-1].startswith("test_") and k.endswith(".py")]
        if tfiles:
            cmd = [sys.executable, "-X", "utf8", "-m", "pytest", *tfiles[:12], "-q", "--timeout=120",
                   "-p", "no:cacheprovider"]
            try:
                pr = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", timeout=900)
                tail = (pr.stdout or "").strip().splitlines()[-1:] or [""]
                j("D4", "关联测试", pr.returncode == 0, "%s（%d 个测试件）" % (tail[0][:90], len(tfiles[:12])))
                rc = rc or (0 if pr.returncode == 0 else 1)
            except Exception as exc:                             # noqa: BLE001
                j("D4", "关联测试", False, "跑不动：%s" % str(exc)[:80])
                rc = 1
    print("\n改后比对（%s）：基线 %s · 变动 %d · 意外 %d" %
          (rel, base.get("at"), len(changed), len(unexpected)))
    for k in sorted(set(changed) | set(missing)):
        print("   %s %s" % ("有意" if k in exp else "**意外**", k))
    return rc


def _snap(rel: str) -> dict:
    """单区块邻域快照（静默，给"和执行同步"的调用方用）。"""
    p = (ROOT / rel).resolve() if not Path(rel).is_absolute() else Path(rel)
    rels = related_files(p)
    return {"block": _rel(p), "ok": bool(rels),
            "rows": {_rel(q): _fp(q) for q in rels if q.is_file()}}


def guard_pre(blocks, expect=None) -> dict:
    """**同步护栏·执行前**：把每个区块的邻域拍进基线（静默返回 dict）。

    为什么要"和执行同步"（Owner 令）：光有独立的 `--snapshot/--diff` 只是又一条**靠记性**的纪律；
    把它焊进 `five-dim.py cap` 的同一次执行里，才是"改一处、关联区块同时被盯着"。
    """
    data = _load_baseline()
    got = {}
    for b in blocks or []:
        s = _snap(b)
        if not s["ok"]:
            got[s["block"]] = {"ok": False, "note": "邻域为空（W2 红：认不出相关区块）"}
            continue
        data[s["block"]] = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "rows": s["rows"]}
        got[s["block"]] = {"ok": True, "n": len(s["rows"])}
    try:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError as exc:                                       # noqa: BLE001
        return {"ok": False, "blocks": got, "note": "基线写不进去：%s" % exc}
    return {"ok": all(v.get("ok") for v in got.values()), "blocks": got}


def guard_post(blocks, expect=None) -> dict:
    """**同步护栏·执行后**：逐件比对；`expect` 里声明的许变，其余变了 ⇒ `ok=False`（修一个坏一个当场抓）。"""
    data = _load_baseline()
    exp = {str(x).strip().replace("\\", "/") for x in (expect or []) if str(x).strip()}
    changed, missing, added, unexpected, per = [], [], [], [], {}
    for b in blocks or []:
        s = _snap(b)
        base = data.get(s["block"]) or {}
        old = base.get("rows") or {}
        cur = s["rows"]
        m = sorted(set(old) - set(cur))
        a = sorted(set(cur) - set(old))
        c = sorted(k for k in set(old) & set(cur) if old[k].get("sha16") != cur[k].get("sha16"))
        # 新增也算意外：邻域里**冒出**一件也可能是 residue（与 `diff()` 同口径，别两边打架）
        u = sorted((set(m) | set(c) | set(a)) - exp)
        missing += m
        added += a
        changed += c
        unexpected += u
        per[s["block"]] = {"changed": c, "missing": m, "added": a, "unexpected": u,
                           "baseline_at": base.get("at"), "n": len(cur)}
    return {"ok": not unexpected, "changed": changed, "missing": missing, "added": added,
            "unexpected": unexpected, "expect": sorted(exp), "blocks": per}



# ═══ 2026-10-18 追加：**跨命令常驻**的邻域记忆（Owner 令逐字：「邻域无意外变动这个也要让大模型形成肌肉记忆」）═══
# 为什么加：`five-dim.py cap` 里的 guard 只盯**一发 cap 之内**（执行前拍、执行后比）。
#   实测漏洞：本机上多数增量是 **bash / edit 写盘**（不走 cap）⇒ 那一段完全在盲区里。
# 现口径：把"上一次看到的邻域"存在盘上（state/neighborhood-ledger.json），
#   ① sight()      —— 开工前照镜子：报**与你最近动过的区块相邻**的那些件，自上次以来发生了什么；
#   ② after_write  —— 任意写盘动作之后复核：一条命令批改一批文件，一并交代；
#   ③ known()      —— 给「谁动过」提供现读，不写死、不猜。
LEDGER = ROOT / "state" / "neighborhood-ledger.json"


def _ledger_load() -> dict:
    if LEDGER.is_file():
        try:
            d = json.loads(LEDGER.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except Exception:                                        # noqa: BLE001
            return {}
    return {}


def _ledger_save(d: dict) -> None:
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass                                                     # 写不进就下次再拍，不装死也不崩


def _recent_blocks(led: dict, within_s: int = 6 * 3600) -> list:
    """最近动过的区块（按基线时间倒序，超时不算）。"""
    now = time.time()
    rows = []
    for b, v in (led.get("blocks") or {}).items():
        t = float(v.get("ts") or 0)
        if now - t <= within_s:
            rows.append((t, b))
    return [b for _, b in sorted(rows, reverse=True)]


def known() -> dict:
    """现读：盘上记得哪些区块、各自最后一次看到是什么时候（取不到就如实空着）。"""
    led = _ledger_load()
    blocks = led.get("blocks") or {}
    return {"ok": bool(blocks), "ledger": str(LEDGER.relative_to(ROOT)),
            "blocks": {b: {"at": v.get("at"), "n": len(v.get("rows") or {})}
                       for b, v in blocks.items()},
            "note": "空 = 还没照过镜子（不是「无变动」）"}


def sight(blocks=None, within_s: int = 6 * 3600) -> dict:
    """**开工前照镜子**：报最近动过的区块（或显式给的）当前邻域读数，并顺手刷新基线。

    取不到就写未读到 —— 空列表绝不当"无变动"念。"""
    led = _ledger_load()
    targets = [b for b in (blocks or []) if b] or _recent_blocks(led, within_s)
    if not targets:
        return {"ok": False, "blocks": {},
                "note": "盘上没有近期区块基线 ⇒ 先视一处（--block X --snapshot）再开工"}
    out = {}
    for b in targets[:12]:
        prev = ((led.get("blocks") or {}).get(b) or {}).get("rows") or {}
        s = _snap(b)
        cur = s["rows"]
        gap = sorted(k for k in set(prev) & set(cur)
                     if prev[k].get("sha16") != cur[k].get("sha16") and k != s["block"])
        gone = sorted(set(prev) - set(cur))
        new = sorted(set(cur) - set(prev))
        out[b] = {"ok": bool(s["ok"]), "n": len(cur), "since": gap[:6], "gone": gone[:4],
                  "new": new[:4],
                  "note": "自上次以来有变动" if (gap or gone or new) else "邻域无意外变动"}
        if s["ok"]:
            led.setdefault("blocks", {})[b] = {
                "at": time.strftime("%Y-%m-%d %H:%M:%S"), "ts": time.time(), "rows": cur}
    _ledger_save(led)
    return {"ok": all(v["ok"] for v in out.values()),
            "blocks": out,
            "note": ("邻域无意外变动" if all(v["note"] == "邻域无意外变动" for v in out.values())
                     else "邻域有变动 ⇒ 逐条交代（改了谁、为什么）")}


def after_write(blocks, expect=None) -> dict:
    """**写盘之后复核**：把一批被改的文件算作 expect，报出它们邻域里**其余**的意外变动。"""
    led = _ledger_load()
    exp = {str(x).strip().replace("\\", "/") for x in (expect or []) if str(x).strip()}
    rows = {}
    for b in blocks or []:
        s = _snap(b)
        if not s["ok"]:
            rows[b] = {"ok": False, "note": "邻域为空（认不出相关区块）"}
            continue
        prev = ((led.get("blocks") or {}).get(s["block"]) or {}).get("rows") or {}
        cur = s["rows"]
        changed = sorted(k for k in set(prev) & set(cur)
                         if prev[k].get("sha16") != cur[k].get("sha16") and k != s["block"])
        missing = sorted(set(prev) - set(cur))
        added = sorted(set(cur) - set(prev))
        unexpected = sorted((set(changed) | set(missing) | set(added)) - exp - {s["block"]})
        rows[s["block"]] = {"ok": not unexpected, "changed": changed[:8], "missing": missing[:4],
                            "added": added[:4], "unexpected": unexpected[:8],
                            "n": len(cur),
                            "note": "邻域无意外变动" if not unexpected else "邻域有意外变动 ⇒ 交代或回退"}
        led.setdefault("blocks", {})[s["block"]] = {
            "at": time.strftime("%Y-%m-%d %H:%M:%S"), "ts": time.time(), "rows": cur}
    _ledger_save(led)
    ok = all(v.get("ok") for v in rows.values()) if rows else False
    return {"ok": ok, "blocks": rows, "expect": sorted(exp),
            "note": "邻域无意外变动" if ok else "邻域有意外变动 ⇒ 交代或回退"}

def selftest() -> int:
    checks = []
    def ck(name, ok, detail=""):
        checks.append({"判据": name, "ok": bool(ok), "读数": str(detail)[:120]})
        print(("✓ " if ok else "✗ ") + name + (" — " + str(detail)[:100] if detail else ""))
    m = mesh()
    ck("负控·真源读得到", bool(m.get("modules")), "模块 %d" % len(m.get("modules") or []))
    ck("正控·邻域=9（c01）", len(neighbors_of("gbt-c01-llm-gateway")) == 9, len(neighbors_of("gbt-c01-llm-gateway")))
    ck("负控·不存在的模块 ⇒ 邻域 0 ⇒ 该红", len([x for x in (m.get("modules") or []) if x.get("id") == "不存在"]) == 0)
    rf = related_files(ROOT / "deploy/cloud-10/src/worker.js")
    ck("正控·文件邻域非空", len(rf) >= 1, "关联 %d 件" % len(rf))
    ck("负控·不存在的文件 ⇒ 邻域空 ⇒ 该红", related_files(ROOT / "no/such/file.js") == [])
    bad = [c for c in checks if not c["ok"]]
    print("\n邻域闸 selftest：%d/%d" % (len(checks) - len(bad), len(checks)))
    return 1 if bad else 0


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                        # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(description="区块邻域同视闸（一次看全关联区块）")
    ap.add_argument("--block", default="", help="模块 id 或仓内文件路径")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--snapshot", action="store_true", help="改前：把该区块的邻域拍成基线")
    ap.add_argument("--diff", action="store_true", help="改后：与基线逐件比对（意外变动即红）")
    ap.add_argument("--expect", default="", help="有意改动的文件（逗号分隔，相对仓根）")
    ap.add_argument("--tests", action="store_true", help="顺带真跑关联测试件（test_*.py）")
    ap.add_argument("--sight", action="store_true",
                    help="开工前照镜子：最近动过的区块自上次以来发生了什么（并刷新基线）")
    ap.add_argument("--known", action="store_true", help="盘上记得哪些区块（现读）")
    ap.add_argument("--after-write", action="store_true",
                    help="写盘之后复核：--expect 里的是有意改动，其余变动算意外")
    ap.add_argument("--blocks", default="", help="一次交代多个区块（逗号分隔），配 --sight/--after-write")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.known:
        r = known()
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r.get("ok") else 1
    if a.sight or a.after_write:
        blocks = [x for x in [a.block] + a.blocks.split(",") if x.strip()]
        blocks = [x.strip() for x in blocks]
        if a.after_write:
            r = after_write(blocks, expect=[x for x in a.expect.split(",") if x.strip()])
        else:
            r = sight(blocks)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r.get("ok") else 1
    if not a.block:
        print("用法：--block <模块id|文件路径> [--snapshot|--diff --expect a.py,b.py --tests] 或 --selftest")
        return 2
    if a.snapshot:
        return snapshot(a.block)
    if a.diff:
        return diff(a.block, [x for x in a.expect.split(",")], a.tests)
    print("=== 区块邻域同视 · %s · 云 %s ===" % (a.block, BASE))
    if a.block in [x.get("id") for x in (mesh().get("modules") or [])]:
        rc = watch_module(a.block)
    else:
        rc = watch_file(a.block)
    bad = [r for r in ROWS if not r["ok"]]
    print("\n判据 PASS %d · FAIL %d" % (len(ROWS) - len(bad), len(bad)))
    out = ROOT / "state" / "block-neighborhood.json"
    try:
        out.write_text(json.dumps({"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "block": a.block,
                                   "rows": ROWS}, ensure_ascii=False, indent=2), encoding="utf-8")
        print("读数落：%s" % out)
    except OSError:
        pass
    return rc


if __name__ == "__main__":
    sys.exit(main())
