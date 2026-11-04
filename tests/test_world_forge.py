# -*- coding: utf-8 -*-
"""world_forge 验收：吞噬 AEON / WorldX / Temporal God 后蒸出的世界内核。

主人令 2026-11-02：「把这些全部仔细挨个拔出我们缺失的吞噬」——三个仓共有的
「确定性活体世界内核」在这件里落地；判据只认真跑：

  ① 确定性：同 seed+spec ⇒ 同 hash；换 seed ⇒ 换世界；40 tick 重跑逐字同；
  ② 分层：世界 → 城市 → 文明 → 宗教/派系（从信念与影响力自己长出来）；
  ③ 铁律：世界之灵只准发被夹紧的 Directive（改规则/事件），**不许直接改人口/产出**；
  ④ 时间：rewind 用「同 seed+directives 重放」对账 history；branch 出独立世界线；
  ⑤ LOD：焦点才物化人物，受 persons_cap 限制；dossier 不编；
  ⑥ 纯函数：AST 导入面零出网/零起进程；view 能亲眼看到地形/体素。

跑法：python tests/test_world_forge.py
"""
from __future__ import annotations

import ast
import os
import pathlib
import sys

ROOT = pathlib.Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(ROOT))

FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)[:300]))
    if not cond:
        FAILED.append(name)


def main() -> int:
    from gbt_allinone.tools import world_forge as WF

    print("[1] schema：蒸馏出处与边界说清楚")
    s = WF.schema()
    check("schema ok", s.get("ok") is True)
    check("ops 齐", set(s.get("ops") or []) >= {"schema", "gen", "step", "focus", "person",
                                                "god", "rewind", "branch", "view", "summary",
                                                "verify"}, s.get("ops"))
    prov = s.get("provenance") or {}
    check("三个来源都记了出处",
          {"aeon-living-worlds", "WorldX", "simulation_universe"} <= set(prov), list(prov))
    check("每个来源都有胶囊路径", all("capsule" in v for v in prov.values()))
    check("铁律写进自述", "唯一" in (s.get("invariant") or ""), s.get("invariant"))

    print("[2] 确定性（Tier-0 唯一真相源）")
    spec = {"seed": 7, "width": 16, "height": 16, "civs": 2, "cities_per_civ": 2}
    a = WF.gen(spec)
    b = WF.gen(spec)
    c = WF.gen(dict(spec, seed=8))
    check("同 seed+spec ⇒ 同 hash", WF.state_hash(a) == WF.state_hash(b), WF.state_hash(a))
    check("换 seed ⇒ 换世界", WF.state_hash(a) != WF.state_hash(c))
    d1 = WF.step(a, 40)
    d2 = WF.step(a, 40)
    check("40 tick 重跑逐字同", WF.state_hash(d1) == WF.state_hash(d2), WF.state_hash(d1))
    check("history 逐 tick 记 hash", len(d1["history"]) == 41
          and all("hash" in h for h in d1["history"]), len(d1["history"]))

    print("[2b] spec 夹紧 / 世界结构")
    big = WF.gen({"seed": 7, "width": 999, "height": 999, "civs": 99, "cities_per_civ": 99})
    check("spec 越界被夹紧", (big["spec"]["width"], big["spec"]["height"], big["spec"]["civs"],
                          big["spec"]["cities_per_civ"]) == (64, 64, 8, 6),
          {k: big["spec"][k] for k in ("width", "height", "civs", "cities_per_civ")})
    check("地形/体素都生成", len(a["biome"]) == 16 and len(a["biome"][0]) == 16
          and len(a["voxels"]) == a["spec"]["depth"], (len(a["biome"]), a["spec"]["depth"]))
    check("开篇编年史有一条 genesis", a["chronicle"][0]["kind"] == "genesis", a["chronicle"][0])

    print("[3] 演化：宗教/派系从信念与影响力里长出来")
    w = WF.step(a, 300)
    summ = WF.summary(w)
    check("300 tick 跑完", summ["tick"] == 300, summ["tick"])
    check("人口 > 0 且城市在", summ["pop"] > 0 and summ["cities"] == 4, (summ["pop"], summ["cities"]))
    check("宗教涌现（信念→宗教）", summ["religions"] >= 1, summ["religions"])
    check("派系涌现（影响力→派系）", summ["factions"] >= 1, summ["factions"])
    check("编年史在长（> 开篇）", summ["chronicle"] > 1, summ["chronicle"])
    kinds = {e["kind"] for e in w["chronicle"]}
    check("编年史有多种事件（不是只一种）", len(kinds) >= 3, sorted(kinds))
    check("chronicle 只追加（无删除）", len(w["chronicle"]) > len(a["chronicle"]))

    print("[4] 铁律：世界之灵只发 Directive（改规则/事件，不画结果）")
    g = WF.god(a, {"kind": "bless"})
    check("bless ok 且 params 真变",
          g.get("ok") is True and g["world"]["params"]["tech_rate"] > a["params"]["tech_rate"],
          g["world"]["params"])
    check("bless 不动人口（结果不许手画）", WF._total_pop(g["world"]) == WF._total_pop(a))
    check("directive 被记进 log", len(g["world"]["directives"]) == 1,
          g["world"]["directives"])
    cat = WF.god(a, {"kind": "catastrophe", "params": {"heat_diff": 999}})
    check("catastrophe 参数被夹紧到边界",
          cat["world"]["params"]["heat_diff"] == 0.5, cat["world"]["params"])
    bad = WF.god(a, {"kind": "set_population", "pop": 99999})
    check("不认的 Directive 被拒", bad.get("ok") is False, bad.get("error"))
    check("God 情绪在状态里（curiosity/benevolence/cruelty/boredom）",
          set(("curiosity", "benevolence", "cruelty", "boredom")) <= set(a["god"]))

    print("[5] 时间：rewind 重放对账 / branch 独立世界线")
    walked = WF.step(a, 60, directives=[{"at_tick": 10, "action": {"kind": "bless"}}])
    rw = WF.rewind(walked, 30)
    check("rewind 到 tick 30 对账一致", rw.get("ok") is True, rw.get("got"))
    check("rewind 回的世界 tick=30", rw["world"]["tick"] == 30, rw["world"]["tick"])
    br = WF.branch(walked, 30, {"civs": 3})
    check("branch ok 且新 seed", br.get("ok") is True and br["seed"] != walked["seed"], br.get("seed"))
    check("branch 的世界是 tick 30 的新世界线",
          br["world"]["tick"] == 30 and len(br["world"]["civs"]) == 3,
          (br["world"]["tick"], len(br["world"]["civs"])))
    br2 = WF.branch(walked, 30, {"civs": 3})
    check("同 patch 分叉可复现", br2["seed"] == br["seed"] and
          WF.state_hash(br2["world"]) == WF.state_hash(br["world"]))
    check("history 里 tick 30 的 hash 对得上",
          next(h for h in walked["history"] if h["tick"] == 30)["hash"]
          == WF.rewind(walked, 30)["got"])

    print("[6] LOD 人物 + dossier")
    f = WF.focus(a, a["cities"][0]["id"])
    check("focus ok 且物化人物", f.get("ok") is True and f["persons"] > 0, f.get("persons"))
    check("人物数受 persons_cap 限制",
          len(f["world"]["persons"]) <= a["spec"]["persons_cap"], len(f["world"]["persons"]))
    p = f["world"]["persons"][0]
    dossier = WF.person(f["world"], p["id"])
    check("dossier 只给真有的", dossier.get("ok") is True
          and dossier["person"]["id"] == p["id"], dossier.get("error"))
    check("dossier 不编（带 note 说明要模型才对话）", "不编" in (dossier.get("note") or "")
          or "dossier" in (dossier.get("note") or ""), dossier.get("note"))
    check("按城市再去 focus 同一城结果稳定（重放同 seed）",
          WF.state_hash(WF.focus(a, a["cities"][0]["id"])["world"]) ==
          WF.state_hash(f["world"]))

    print("[7] view / summary / run 分派")
    v = WF.view(a)
    check("view 地形行数=height", len(v["biome"].splitlines()) == a["spec"]["height"],
          len(v["biome"].splitlines()))
    check("view 体素切片存在", bool(v["voxel"]) and len(v["voxel"].splitlines()) == a["spec"]["height"])
    check("地形 ASCII 只用已知字符",
          set(v["biome"].replace("\n", "")) <= set(WF.BIOME_ASCII.values()),
          sorted(set(v["biome"].replace("\n", ""))))
    check("summary 字段齐", {"tick", "civs", "pop", "religions", "factions", "chronicle", "hash"}
          <= set(summ) and summ["ok"] is True)
    r = WF.run("gen", spec=spec)
    check("run(gen) 出世界", r.get("ok") and "world" in r, list(r))
    r = WF.run("summary", world=r["world"])
    check("run(summary) 出读数", r.get("ok") and r.get("tick") == 0)
    r = WF.run("nope")
    check("run 不认的 op 如实拒", r.get("ok") is False and "known" in r)

    print("[8] 纯函数：AST 导入面零出网/零起进程 + 模块自检")
    src = (ROOT / "gbt_allinone" / "tools" / "world_forge.py").read_text(encoding="utf-8")
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            mods.update(x.name.split(".")[0] for x in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    check("无 urllib/socket/subprocess/http 导入",
          not (mods & {"urllib", "socket", "subprocess", "http", "requests"}), sorted(mods))
    vf = WF.verify()
    check("模块自检全绿", vf.get("ok") is True, vf.get("failed"))
    check("自检项数 ≥ 14", len(vf.get("checks") or []) >= 14, len(vf.get("checks") or []))

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 世界内核确定/分层/铁律/时间回放/LOD/纯函数 全绿；吞噬的丢失项已落地")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
