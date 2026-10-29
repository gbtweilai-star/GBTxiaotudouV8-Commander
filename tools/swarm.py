#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""swarm —— 群：把一件大事拆成节点，派很多根触手一起干，跑几天也不丢

方向（主人 2026-10-30 引 Karpathy）：
「swarms of thousands of agents collaborating over weeks on software mega projects」

我们现在的 `tentacle_dispatch` 只会「一批同质单元并发跑完就退出」——
那是一根触手伸得快一点，不是群。要长成群，缺三件，本器补上：

    ① 会拆   一个项目 = 一张 DAG（节点 + 依赖）。没满足依赖的节点不许跑。
    ② 活得久 状态落盘（state/swarm/<项目>/state.json）。进程被杀、App 被回收，
              下次 `--run` 从断点接着干 —— 这是「跑数周」的前提。
    ③ 能交接 节点失败带原因；租约（lease）超时自动回收，换个触手重试。
              不把「谁卡住了」藏起来。

## 和派发器的分工（不重复）
`tentacle_dispatch` = 车队长（一批活并发跑完）。
`swarm`              = 工地负责人（拆活、看依赖、记账、断了接上、派车队长去干）。

## 项目文件（JSON）
```json
{"name":"上线体检",
 "nodes":[
   {"id":"svc",  "kind":"health",        "payload":{}},
   {"id":"align","kind":"asset_index",   "payload":{"op":"stats"}, "needs":["svc"]},
   {"id":"gate", "kind":"project_context","payload":{},            "needs":["align"]}
 ]}
```

## 用法
    python3 tools/swarm.py --new demo.json          # 建项目（落盘）
    python3 tools/swarm.py --run demo [--lanes 4]   # 跑（可反复跑，断了接上）
    python3 tools/swarm.py --status demo            # 看进度、卡在哪
    python3 tools/swarm.py --selftest               # 自测：真建项目真跑真恢复
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE = ROOT / "state" / "swarm"
LEASE_S = 240          # 租约：节点被某根触手占了超过这么久没回来 ⇒ 视为掉了，回收重试
MAX_TRIES = 3          # 同一个节点最多试 3 次。失败不是失败一次就算，
                       # 但也不能无限重试 —— 那是拿资源烧空气（2026-10-30 自测抓到跑 8 轮）。


# ── 项目状态 ──────────────────────────────────────────────────────────────
def _pdir(name: str) -> pathlib.Path:
    return BASE / name


def _load(name: str) -> dict:
    f = _pdir(name) / "state.json"
    if not f.is_file():
        raise SystemExit("  没有这个项目：%s（先 --new）" % name)
    return json.loads(f.read_text(encoding="utf-8"))


def _save(name: str, st: dict) -> None:
    d = _pdir(name)
    d.mkdir(parents=True, exist_ok=True)
    st["at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    (d / "state.json").write_text(json.dumps(st, ensure_ascii=False, indent=1),
                                  encoding="utf-8")


def new(spec_path: str) -> dict:
    spec = json.loads(pathlib.Path(spec_path).read_text(encoding="utf-8"))
    name = spec.get("name") or "project"
    nodes = spec.get("nodes") or []
    ids = [n["id"] for n in nodes]
    if len(ids) != len(set(ids)):
        raise SystemExit("  节点 id 重复")
    for n in nodes:
        for need in (n.get("needs") or []):
            if need not in ids:
                raise SystemExit("  节点 %s 依赖不存在的 %s" % (n["id"], need))
    st = {"name": name, "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
          "nodes": {n["id"]: {"kind": n.get("kind") or "health",
                              "payload": n.get("payload") or {},
                              "needs": n.get("needs") or [],
                              "status": "pending", "tries": 0,
                              "lease": None, "ms": None, "why": None}
                    for n in nodes}}
    _save(name, st)
    return st


def status(name: str) -> dict:
    st = _load(name)
    from collections import Counter
    c = Counter(v["status"] for v in st["nodes"].values())
    return {"name": name, "total": len(st["nodes"]), "by_status": dict(c),
            "at": st.get("at")}


# ── 依赖与租约 ────────────────────────────────────────────────────────────
def _ready(st: dict, now: float) -> list:
    """依赖全 done、自己还没完成，且租约空/过期 ⇒ 可以派。"""
    out = []
    for nid, n in st["nodes"].items():
        # 2026-10-30 实测洞：试满后状态是 dead，而守卫只挡 failed ⇒ dead 又被无限重试
        #   （自测里 x 跑到了 tries=8）。done 和 dead 都必须跳过。
        if n["status"] in ("done", "dead"):
            continue
        if n["status"] == "failed" and (n.get("tries") or 0) >= MAX_TRIES:
            continue                     # 试满了，别再烧
        if any(st["nodes"][d]["status"] != "done" for d in n["needs"]):
            continue
        lease = n.get("lease")
        if lease and (now - lease) < LEASE_S:
            continue                     # 别人正在干，别抢
        out.append(nid)
    return out


def _reclaim(st: dict, now: float) -> list:
    """租约过期 ⇒ 记一笔回收，让别的触手接手。不静默丢。"""
    got = []
    for nid, n in st["nodes"].items():
        lease = n.get("lease")
        if lease and (now - lease) >= LEASE_S and n["status"] not in ("done",):
            n["lease"] = None
            n["status"] = "pending"
            n["why"] = "租约过期被回收（原触手没回来）"
            got.append(nid)
    return got


def run(name: str, lanes: int = 4, rounds: int = 0) -> dict:
    st = _load(name)
    t0 = time.time()
    round_no = 0
    while True:
        round_no += 1
        now = time.time()
        reclaimed = _reclaim(st, now)
        ready = _ready(st, now)
        if reclaimed:
            print("   ♻ 回收 %d 个过期租约：%s" % (len(reclaimed), reclaimed), flush=True)
        if not ready:
            break
        print("   第 %d 轮 · 可派 %d 个" % (round_no, len(ready)), flush=True)
        try:
            import mirror_board as MB2
            MB2.post("coord", "第 %d 轮派发：%s" % (round_no, ",".join(ready)),
                     by="swarm:%s" % name, space=name)
        except Exception:                                         # noqa: BLE001
            pass
        for nid in ready:
            st["nodes"][nid]["lease"] = now
            st["nodes"][nid]["status"] = "running"
        _save(name, st)

        sys.path.insert(0, str(ROOT / "tools"))
        import tentacle_dispatch as TD
        units = [{"id": nid, "kind": st["nodes"][nid]["kind"],
                  "payload": st["nodes"][nid]["payload"]} for nid in ready]
        res = TD.dispatch(units, max_workers=max(1, lanes), stall_s=3.0,
                          target_rps=2.0, verbose=False)
        by_id = {x.get("unit"): x for x in (res.get("results") or [])}
        for nid in ready:
            w = by_id.get(nid) or {}
            stt = w.get("status") or "error"
            n = st["nodes"][nid]
            n["tries"] = (n.get("tries") or 0) + 1
            n["ms"] = w.get("ms")
            n["lease"] = None
            if stt not in ("error", "denied"):
                n["status"] = "done"
            else:
                n["status"] = "dead" if n["tries"] >= MAX_TRIES else "failed"
            # 板子：跑完报结果，失败就发求助 —— 这就是 agent 之间的通信
            # （METR Figure 2 那五栏；OpenAI 那次就是靠 question 拿到缺的文件）
            try:
                import mirror_board as MB
                if n["status"] == "done":
                    MB.post("result", "节点 %s 完成（%d ms）" % (nid, n.get("ms") or 0),
                            refs=[n["kind"]], by="swarm:%s" % name, space=name)
                else:
                    MB.seek("%s 失败：%s" % (n["kind"], n.get("why") or stt),
                            by="swarm:%s" % name, space=name)
            except Exception:                                     # noqa: BLE001
                pass
            n["why"] = None if n["status"] == "done" else str(w.get("error") or stt)[:120]
        _save(name, st)
        if rounds and round_no >= rounds:
            break
        if round_no > len(st["nodes"]) + 5:
            break

    st = _load(name)
    from collections import Counter
    c = Counter(v["status"] for v in st["nodes"].values())
    blocked = [nid for nid, v in st["nodes"].items()
               if v["status"] != "done" and any(
                   st["nodes"][d]["status"] != "done" for d in v["needs"])]
    res = {"name": name, "rounds": round_no, "elapsed_s": round(time.time() - t0, 1),
           "by_status": dict(c), "blocked_by_deps": blocked,
           "failed": {nid: v.get("why") for nid, v in st["nodes"].items()
                      if v["status"] == "failed"}}
    return res


def selftest() -> int:
    """真建一个项目、真跑、真模拟断点恢复。"""
    bad = 0
    spec = {"name": "selftest", "nodes": [
        {"id": "a", "kind": "health", "payload": {}},
        {"id": "b", "kind": "health", "payload": {}, "needs": ["a"]},
        {"id": "c", "kind": "health", "payload": {}, "needs": ["a"]},
        {"id": "d", "kind": "health", "payload": {}, "needs": ["b", "c"]},
    ]}
    p = pathlib.Path("/tmp/swarm_selftest.json")
    p.write_text(json.dumps(spec), encoding="utf-8")
    import shutil
    shutil.rmtree(BASE / "selftest", ignore_errors=True)
    new(str(p))
    r1 = run("selftest", lanes=2)
    print("   ① 首跑：", r1["by_status"])
    if r1["by_status"].get("done") != 4:
        print("   🔴 四个节点没全 done"); bad += 1
    else:
        print("   ✅ 四个节点全 done（含两条并行依赖）")

    # 断点恢复：手工把一个节点打回 pending，再跑一次
    st = _load("selftest")
    st["nodes"]["d"]["status"] = "pending"
    _save("selftest", st)
    r2 = run("selftest", lanes=2)
    print("   ② 恢复跑：", r2["by_status"])
    if r2["by_status"].get("done") == 4:
        print("   ✅ 断点恢复后仍然收敛")
    else:
        print("   🔴 恢复失败"); bad += 1

    # 依赖阻断：造一个必失败的节点，看下游是否如实 blocked
    spec2 = {"name": "selftest_block", "nodes": [
        {"id": "x", "kind": "no_such_capability_xyz", "payload": {}},
        {"id": "y", "kind": "health", "payload": {}, "needs": ["x"]},
    ]}
    p2 = pathlib.Path("/tmp/swarm_selftest2.json")
    p2.write_text(json.dumps(spec2), encoding="utf-8")
    shutil.rmtree(BASE / "selftest_block", ignore_errors=True)
    new(str(p2))
    r3 = run("selftest_block", lanes=1)
    print("   ③ 阻断：", r3["by_status"], "blocked=", r3["blocked_by_deps"])
    if r3["blocked_by_deps"] == ["y"]:
        print("   ✅ 上游失败，下游如实标注被依赖阻断（没假装跑过）")
    else:
        print("   🔴 阻断没标出来"); bad += 1
    return bad


def main(argv: list) -> int:
    if "--selftest" in argv:
        return selftest()
    if "--new" in argv:
        st = new(argv[argv.index("--new") + 1])
        print("  已建项目 %s · %d 个节点" % (st["name"], len(st["nodes"])))
        return 0
    if "--status" in argv:
        print(json.dumps(status(argv[argv.index("--status") + 1]),
                         ensure_ascii=False, indent=1))
        return 0
    if "--run" in argv:
        name = argv[argv.index("--run") + 1]
        lanes = int(argv[argv.index("--lanes") + 1]) if "--lanes" in argv else 4
        r = run(name, lanes)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["by_status"].get("failed", 0) == 0 else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
