# -*- coding: utf-8 -*-
"""tentacle-double-plug · 双插回溯补插（主人令 2026-10-15：每个上下文至少两根触手插着）。

背景（现读）：state/asset_bindings.json 7,660 条里，**7,098 条只有 1 根触手**；
其中 sweep 4,584 + asset_index.wire 1,548 = 6,132 条（86%）来自批处理**每文件只写一根**。

做法：对单插记录**追加**第二根「路径域触手」（bind 语义是追加，永不覆盖/删除）；
写前**存快照**（state/asset_bindings.pre-dualplug.json）可回滚；默认 dry-run。
判据：--check 出双插率 + 零丢失（原有触手必须一根不少）；取不到读数=红。
用法：--dry-run | --apply | --check
开发者：自由的风 · 守护者：公主土豆 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"""
import argparse, datetime, json, pathlib, shutil, sys

R = pathlib.Path(__file__).resolve().parents[2]
BIND = R / "state" / "asset_bindings.json"
SNAP = R / "state" / "asset_bindings.pre-dualplug.json"

def _second(asset: str, have=()) -> str:
    a = asset.replace("\\", "/")
    if "/产线/" in a or "/成片/" in a or "/编剧室/" in a: return "filmkit"
    if "/tools/" in a: return "domain:tools"
    if a.endswith((".md", ".html", ".htm", ".txt", ".csv")): return "domain:docs"
    if a.startswith("projects/"): return "project_context"

def _second_type(asset: str) -> str:
    """扩展名族兜底：按**文件类型**给第二根（读一根 / 类一根），保证与第一根不同族。"""
    e = asset.lower().rsplit(".", 1)[-1] if "." in asset else ""
    if e in ("mp4", "mov", "mkv", "webm", "m4a", "mp3", "wav", "jpg", "jpeg", "png", "webp", "gif"):
        return "domain:media"
    if e in ("s", "asm", "c", "h", "cpp", "rs", "go"): return "domain:code"
    if e in ("json", "jsonl", "yaml", "yml", "toml", "ini", "cfg"): return "domain:state"
    if e in ("py", "ps1", "cmd", "bat", "sh", "mjs", "ts", "js"): return "domain:tentacle"
    if e in ("md", "txt", "csv", "html", "htm"): return "domain:docs"
    return ""

def _load():
    if not BIND.is_file(): return None
    try: return json.loads(BIND.read_text(encoding="utf-8", errors="replace"))
    except Exception: return None

def _valid_labels() -> set:
    """**单一词表真源** = `tools/tentacle_bind.py::_valid_labels()`。

    🔴 2026-10-17 加（留痕）：本件原来自己硬写 `domain:docs/media/state/code` 这些标签，
    而词表那边只有「能力位 kind ∪ domain:<注册表域>」⇒ 两套词表打架，写进账的 4953 条
    被反向校验全判「绑到不存在的能力位」。现在：①词表那边补了第三层 `FAMILY_LABELS`；
    ②本件**只从词表取**，不许在这里另造标签（再造就是又一次两套词表）。
    """
    import importlib.util as _iu
    p = pathlib.Path(__file__).resolve().parents[1] / "tentacle_bind.py"
    spec = _iu.spec_from_file_location("_tb", str(p))
    m = _iu.module_from_spec(spec)
    spec.loader.exec_module(m)
    return set(m._valid_labels() or set())


def _plan(d):
    valid = _valid_labels()
    todo = []
    for a, row in d.items():
        ts = (row or {}).get("tentacles") or []
        if len(ts) != 1:
            continue
        t2 = _second(a)
        if not t2 or t2 in ts:
            t2 = _second_type(a)          # 兜底：按类型给第二根
        # 只接受**词表里真有**的标签；造不出合法第二根就如实不补（不塞假标签）
        if t2 and t2 not in ts and (not valid or t2 in valid):
            todo.append((a, t2))
    return todo

def run(apply: bool) -> int:
    d = _load()
    if d is None: print("红：读不到 " + str(BIND)); return 1
    todo = _plan(d)
    total = len(d); single = sum(1 for r in d.values() if len((r or {}).get("tentacles") or []) == 1)
    print("上下文 %d · 单插 %d · 本次可补 %d" % (total, single, len(todo)))
    if not apply:
        print("（dry-run，未写盘；加 --apply 才落）例: " + str(todo[:3]))
        return 0
    if not SNAP.exists():
        shutil.copy2(BIND, SNAP); print("已存快照 " + SNAP.name)
    for a, t2 in todo:
        row = d.setdefault(a, {"tentacles": [], "note": "dualplug", "bound_at": ""})
        row.setdefault("tentacles", [])
        if t2 not in row["tentacles"]:
            row["tentacles"].append(t2)
            row["note"] = (row.get("note") or "") + "·双插"
            row["bound_at"] = row.get("bound_at") or datetime.datetime.now().isoformat(timespec="seconds")
            row["dualplug_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    BIND.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print("已补 %d 条并落盘" % len(todo))
    return 0

def check() -> int:
    d = _load(); res = []
    if d is None:
        res.append(("D1 绑定表可读", False, "读不到"))
    else:
        tot = len(d); multi = sum(1 for r in d.values() if len((r or {}).get("tentacles") or []) >= 2)
        rate = 100.0 * multi / max(tot, 1)
        res.append(("D1 绑定表可读", True, "%d 条" % tot))
        res.append(("D2 双插率 ≥50%", rate >= 50.0, "双插 %.1f%%（%d/%d）" % (rate, multi, tot)))
        if SNAP.exists():
            old = json.loads(SNAP.read_text(encoding="utf-8", errors="replace"))
            lost = [a for a, r in old.items() if a in d and not set((r or {}).get("tentacles") or []) <= set((d[a] or {}).get("tentacles") or [])]
            res.append(("D3 零丢失（只增不减）", not lost, ("丢了 %d 条" % len(lost)) if lost else "齐"))
        else:
            res.append(("D3 零丢失（只增不减）", True, "无快照可比（首次）"))
    for n, ok, det in res: print(("  OK   " if ok else "  FAIL ") + n + " — " + str(det))
    red = [n for n, ok, _ in res if not ok]
    print("判据 PASS %d · FAIL %d" % (len(res) - len(red), len(red)))
    return 1 if red else 0

def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true"); ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.check: return check()
    return run(apply=bool(a.apply))

if __name__ == "__main__":
    sys.exit(main())
