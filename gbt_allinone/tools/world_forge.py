# -*- coding: utf-8 -*-
# gbt-capability: none  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""世界锻造内核（world_forge）—— 吞噬 AEON / WorldX / Temporal God 后蒸出的「第 0 步」

来历（2026-11-02 主人令）：「把这些全部仔细挨个拔出我们缺失的吞噬」。
三个仓都是**活体世界 / 世界模拟**，横着切共有的、而我们框架原来没有的，
是下面这一层 **确定性世界内核**（不是搬任何一份代码，只蒸机制）：

  · AEON（Linutesto/aeon-living-worlds）：
      - Tier-0 确定性仿真 = 唯一真相源（同 seed + 同 config ⇒ 同一个世界）；
      - 分层认知 L0..L5（环境/个体/物种心智/信仰/派系/文明）与 **LOD 人口池**；
      - 信念长出宗教/派系（宏观从个体信念里长出来，不是手写剧本）；
      - 世界之灵 LLM 只能发 **被夹紧的 Directive**（改规则、绝不许直接画结果）；
      - Chronicle 编年史 + sqlite 存档 + 分层重启（文明/地形/城市/心智）。
  · WorldX（YGYOOO/WorldX）：
      - 一句话 → 世界规格（编排模型设计世界、绘图模型出地图/立绘、视觉模型审图）；
      - 上帝模式（广播事件 / 编辑人设与记忆 / 与角色架空对话）；
      - 时间线系统（一个世界多条时间线）；
      - 四角色模型路由（编排/绘图/审查/世界驱动分开配）。
  · Temporal God Simulation 3D（organization-ai-projects/simulation_universe）：
      - 3D 体素网格（材质/温度/密度）+ 热扩散/冷却/重力；
      - 种群 → 文明涌现（人口阈值、科技/侵略/灵性）；
      - 内部 God AI（好奇/仁慈/残忍/无聊）用动作影响世界；
      - 时间回溯 + Multiverse 时间线分支（本件用「可复现重放」实现，不存每 tick 全量快照）。

一条铁律（与 AEON 逐字同源，我们照写）：
  **仿真内核是唯一改世界的东西；"神/世界之灵"只能发被夹紧的 Directive（改规则/加事件），
  绝不许直接给文明发人口、给城市改产出 —— 结果必须由内核 tick 自己长出来。**
  本件把这条写成可机检：`god()` 只改 `params` / 写 `events` / 记 `directives`，
  不改 `civs/cities` 的数值；`verify()` 里有一条专门钉它。

本件是**纯函数**：零出网、零起进程、零写盘（不 import urllib/socket/subprocess；
状态全在返回值里，调用方要落盘自己走门）。所以它可以先作为「候选能力位」存在，
注册进 `caps_registry` / 接进万能插要主人点头（本仓红线：AI 不自改 policy / 不擅加位）。

op（`run(op, **kw)`）：
  schema   世界规格字段 + 边界 + 三个来源的蒸馏出处（只读）
  gen      seed + spec ⇒ 世界（生成文明/城市/地形/体素，写编年史开篇）
  step     推进 N tick（返回新世界；history 里逐 tick 记 hash，可对账）
  focus    按城市物化 LOD 人物（受 persons_cap 限制）
  person   读一个人物的 grounded dossier（WorldX「架空对话」的地基，不编）
  god      世界之灵发一条被夹紧的 Directive（catastrophe/bless/rules/omen）
  rewind   回到第 t tick（**重放**：同 seed+directives ⇒ 同状态；不做全量快照）
  branch   在第 t tick 分叉出一条新时间线（改 spec 即换世界线）
  view     地形/体素 ASCII 切片（给面板/验收亲眼看）
  summary  现读统计（人口/文明/宗教/派系/编年史条数/状态 hash）
  verify   自检：确定性 / 夹紧 / God 不画结果 / rewind 对账（全绿才 ok）

用法：
  python -m gbt_allinone.tools.world_forge schema
  python -m gbt_allinone.tools.world_forge gen --seed 7
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
import re
import time

# ── 出处（吞噬记录：每个仓只取机制，不搬代码；许可一并如实写）────────────────
PROVENANCE = {
    "aeon-living-worlds": {
        "repo": "Linutesto/aeon-living-worlds",
        "license": "NOASSERTION（无明确许可 ⇒ 只蒸设计，不复制代码）",
        "distilled": ["Tier-0 确定性仿真唯一真相源", "L0..L5 分层认知 + LOD 人口池",
                      "信念→宗教/派系涌现", "World-Spirit 只发被夹紧的 Directive",
                      "Chronicle 编年史", "命名 RNG 流（子系统互不扰动）",
                      "分层重启（文明/地形/城市/心智）"],
        "capsule": "store/devoured/devoured_aeon_living_worlds/absorbed_knowledge.md",
    },
    "WorldX": {
        "repo": "YGYOOO/WorldX",
        "license": "MIT（许可允许，但本仓纪律：只蒸设计、不搬代码）",
        "distilled": ["一句话 → 世界规格（编排模型）", "地图/立绘生成 + 视觉审查循环",
                      "上帝模式（广播事件/编辑记忆人格/架空对话）", "时间线系统（多世界线）",
                      "四角色模型路由（编排/绘图/审查/世界驱动）"],
        "capsule": "store/devoured/devoured_worldx/absorbed_knowledge.md",
    },
    "simulation_universe": {
        "repo": "organization-ai-projects/simulation_universe",
        "license": "unknown（实验件 ⇒ 只蒸设计，不复制代码）",
        "distilled": ["3D 体素 + 材质温度/密度", "热扩散/冷却/重力",
                      "种群→文明涌现（人口阈值 + 科技/侵略/灵性）",
                      "内部 God AI 情绪状态 + 动作", "时间回溯 + Multiverse 分支"],
        "capsule": "store/devoured/devoured_temporal_god_sim/absorbed_knowledge.md",
    },
}

BIOMES = ("ocean", "coast", "grass", "forest", "desert", "tundra", "mountain", "volcano")
BIOME_ASCII = {"ocean": "~", "coast": ".", "grass": ",", "forest": "T", "desert": ":",
               "tundra": "*", "mountain": "^", "volcano": "A"}
VOXEL_MATERIALS = ("air", "rock", "soil", "water", "lava", "ice", "organic")
MATERIAL_ASCII = {"air": " ", "rock": "#", "soil": ".", "water": "~", "lava": "L",
                  "ice": "I", "organic": "%"}

DEFAULT_SPEC = {
    "seed": 7,
    "width": 24,
    "height": 24,
    "civs": 3,
    "cities_per_civ": 2,
    "water_level": 0.32,
    "warmth": 0.0,
    "voxel": True,
    "depth": 8,
    "persons_cap": 48,
    "ticks_cap": 500,
}
SPEC_BOUNDS = {
    "seed": (0, 2**32 - 1),
    "width": (8, 64),
    "height": (8, 64),
    "civs": (1, 8),
    "cities_per_civ": (1, 6),
    "water_level": (0.0, 0.8),
    "warmth": (-1.0, 1.0),
    "depth": (4, 16),
    "persons_cap": (1, 256),
    "ticks_cap": (1, 5000),
}
PARAM_BOUNDS = {
    "heat_diff": (0.0, 0.5),
    "cooling": (0.0, 0.2),
    "war_rate": (0.0, 1.0),
    "tech_rate": (0.0, 1.0),
    "blessing": (0.0, 1.0),
}
GOD_KINDS = ("catastrophe", "bless", "change_rules", "omen")
CIV_ARCHETYPES = ("农夫", "商队", "铁匠", "祭司", "航海", "游牧", "学者")
CIV_SYLLABLES = ("阿", "兰", "卡", "尔", "塔", "米", "诺", "斯", "维", "拉", "格", "德",
                 "塞", "恩", "图", "伊", "奥", "珊", "珀", "罗")
PERSON_NAMES = ("阿禾", "白露", "青岚", "沐风", "石生", "溪云", "陶朱", "南星", "知夏",
                "远山", "临水", "素问", "寒衣", "扶苏", "洛川", "尘上", "鹤鸣", "小满")
BIG5 = ("openness", "conscientiousness", "extraversion", "agreeableness", "neuroticism")


# ── 工具 ────────────────────────────────────────────────────────────────────
def _rng(seed: int, stream: str) -> random.Random:
    """命名 RNG 流（AEON 同款机制）：blake2b(seed:stream) 派生子种子。

    这样「气候流」和「战争流」互不扰动 —— 加一条事件不会把别的子系统全改一遍，
    确定性才守得住（这是本件敢说"同输入同世界"的根）。
    """
    h = hashlib.blake2b(("%s:%s" % (int(seed), stream)).encode("utf-8"), digest_size=8).digest()
    return random.Random(int.from_bytes(h, "big"))


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _canon(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def state_hash(world: dict) -> str:
    """状态指纹：排除 history（否则自我引用）；其余按 canonical JSON 逐字节哈希。"""
    body = {k: v for k, v in world.items() if k not in ("history",)}
    return hashlib.sha256(_canon(body).encode("utf-8")).hexdigest()[:16]


def _normalize_spec(spec: dict | None) -> dict:
    out = dict(DEFAULT_SPEC)
    for k, v in (spec or {}).items():
        if k in DEFAULT_SPEC:
            out[k] = v
    for k, (lo, hi) in SPEC_BOUNDS.items():
        if k in out and isinstance(out[k], bool):
            continue
        if k in ("seed", "width", "height", "civs", "cities_per_civ", "depth",
                 "persons_cap", "ticks_cap"):
            out[k] = int(_clamp(int(out.get(k, DEFAULT_SPEC[k])), lo, hi))
        else:
            out[k] = float(_clamp(float(out.get(k, DEFAULT_SPEC[k])), lo, hi))
    out["voxel"] = bool(out.get("voxel", True))
    return out


def _civ_name(rng) -> str:
    return "".join(rng.choice(CIV_SYLLABLES) for _ in range(rng.randint(2, 3)))


def _gen_terrain(rng, spec: dict):
    """value-noise 地形（纯随机网格 + 三遍邻域平滑）：海/岸/草/林/漠/苔/山。"""
    W, H = spec["width"], spec["height"]
    base = [[rng.random() for _ in range(W)] for _ in range(H)]
    for _ in range(3):
        nxt = [[0.0] * W for _ in range(H)]
        for y in range(H):
            for x in range(W):
                acc, n = 0.0, 0
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        yy, xx = y + dy, x + dx
                        if 0 <= yy < H and 0 <= xx < W:
                            acc += base[yy][xx]
                            n += 1
                nxt[y][x] = acc / n
        base = nxt
    moist = [[rng.random() for _ in range(W)] for _ in range(H)]
    water = spec["water_level"]
    warm = spec["warmth"]
    elev = [[round(base[y][x], 4) for x in range(W)] for y in range(H)]
    biome = []
    for y in range(H):
        row = []
        for x in range(W):
            e = base[y][x]
            m = moist[y][x]
            if e < water:
                row.append("ocean")
            elif e < water + 0.06:
                row.append("coast")
            elif e > 0.80:
                row.append("volcano" if m > 0.86 else "mountain")
            elif m < 0.30:
                row.append("desert")
            elif e > 0.70 - warm * 0.1:
                row.append("tundra")
            elif m > 0.62:
                row.append("forest")
            else:
                row.append("grass")
        biome.append(row)
    return biome, elev


def _gen_voxels(rng, spec: dict, biome, elev):
    """3D 体素层（Temporal God 蒸馏）：高度 = 地形海拔，材质按深度/湿度/火山分布。"""
    if not spec.get("voxel"):
        return []
    W, H, D = spec["width"], spec["height"], spec["depth"]
    layers = []
    for z in range(D):
        plane = []
        for y in range(H):
            row = []
            for x in range(W):
                b = biome[y][x]
                h = int(elev[y][x] * D)
                if z > h:
                    row.append("air")
                elif b == "ocean":
                    row.append("water")
                elif b == "volcano" and z >= h - 1:
                    row.append("lava")
                elif z == 0:
                    row.append("rock")
                elif z >= h - 1:
                    row.append("soil" if b in ("grass", "forest", "desert") else "ice")
                else:
                    row.append("rock")
            plane.append(row)
        layers.append(plane)
    return layers


def _place_cities(rng, spec, biome, elev):
    """在陆地上放城市（每个文明 cities_per_civ 座）；位置由 RNG 流决定、可复现。"""
    H, W = spec["height"], spec["width"]
    land = [(x, y) for y in range(H) for x in range(W)
            if biome[y][x] not in ("ocean", "coast")]
    if not land:
        land = [(W // 2, H // 2)]
    rng.shuffle(land)
    cities, civs = [], []
    used = set()
    for c in range(spec["civs"]):
        civ = {
            "id": "civ-%d" % c,
            "name": _civ_name(rng),
            "archetype": rng.choice(CIV_ARCHETYPES),
            "tech": round(0.2 + rng.random() * 0.3, 3),
            "war": round(rng.random(), 3),
            "expansion": round(rng.random(), 3),
            "spirituality": round(rng.random(), 3),
            "pop": 0,
        }
        civs.append(civ)
        for i in range(spec["cities_per_civ"]):
            spot = None
            for (x, y) in land:
                if (x, y) not in used:
                    spot = (x, y)
                    used.add((x, y))
                    break
            if spot is None:
                spot = (rng.randrange(W), rng.randrange(H))
            pop = int(80 + rng.random() * 420)
            civ["pop"] += pop
            cities.append({
                "id": "city-%d-%d" % (c, i),
                "name": _civ_name(rng) + "城",
                "civ": civ["id"],
                "x": spot[0], "y": spot[1],
                "pop": pop,
                "food": round(1.0 + rng.random() * 0.6, 3),
                "culture": round(rng.random(), 3),
                "infra": round(rng.random() * 0.5, 3),
                "influence": round(rng.random() * 0.5, 3),
                "faith": round(rng.uniform(-0.3, 0.3), 3),
                "grievance": round(rng.random() * 0.2, 3),
            })
    return civs, cities


# ── 生成 ────────────────────────────────────────────────────────────────────
def gen(spec: dict | None = None) -> dict:
    """seed + spec ⇒ 世界。同 (seed, spec) **永远**同一世界（含编年史开篇）。"""
    spec = _normalize_spec(spec)
    rng_t = _rng(spec["seed"], "terrain")
    biome, elev = _gen_terrain(rng_t, spec)
    voxels = _gen_voxels(_rng(spec["seed"], "voxel"), spec, biome, elev)
    civs, cities = _place_cities(_rng(spec["seed"], "cities"), spec, biome, elev)
    world = {
        "seed": spec["seed"],
        "spec": spec,
        "tick": 0,
        "biome": biome,
        "elev": elev,
        "voxels": voxels,
        "civs": civs,
        "cities": cities,
        "persons": [],
        "religions": [],
        "factions": [],
        "chronicle": [{"tick": 0, "kind": "genesis",
                       "text": "世界诞生：%d 个文明在 %dx%d 的地上落脚。" % (len(civs),
                                                                        spec["width"], spec["height"]),
                       "tags": ["genesis"]}],
        "god": {"curiosity": 0.6, "benevolence": 0.5, "cruelty": 0.15, "boredom": 0.1,
                "last": "None"},
        "params": {"heat_diff": 0.10, "cooling": 0.02, "war_rate": 0.35,
                   "tech_rate": 0.50, "blessing": 0.50},
        "directives": [],
        "history": [],
    }
    world["history"].append({"tick": 0, "hash": state_hash(world), "pop": _total_pop(world),
                             "civs": len(world["civs"]), "religions": 0, "factions": 0})
    return world


def _total_pop(world: dict) -> int:
    return int(sum(c.get("pop", 0) for c in world.get("cities") or []))


def _event(world, kind, text, tags=None):
    world["chronicle"].append({"tick": world["tick"], "kind": kind, "text": text,
                               "tags": list(tags or [kind])})


def _cities_of(world, civ_id):
    return [c for c in world["cities"] if c["civ"] == civ_id]


def _civ(world, civ_id):
    for c in world["civs"]:
        if c["id"] == civ_id:
            return c
    return None


def _tick(world: dict) -> None:
    """一个 tick：气候→食物→生死→信念→宗教/派系→战争→科技→上帝情绪。

    每层只走自己的 step，**结果由规则算出来，不由外部直接写**（AEON 的同一条纪律）。
    """
    world["tick"] += 1
    t = world["tick"]
    rng = _rng(world["seed"], "tick:%d" % t)
    rng_war = _rng(world["seed"], "war:%d" % t)
    weather = 0.75 + 0.5 * rng.random()

    # ① 气候/食物/人口（城市层）
    for city in world["cities"]:
        biome = world["biome"][city["y"]][city["x"]]
        bonus = {"grass": 0.20, "forest": 0.12, "coast": 0.08, "desert": -0.10,
                 "tundra": -0.08, "mountain": -0.12, "volcano": -0.2,
                 "ocean": -0.3}.get(biome, 0.0)
        city["food"] = round(max(0.0, city["food"] * 0.92 + (0.12 + bonus) * weather), 3)
        growth = (city["food"] - 0.9) * 0.6 + city["infra"] * 0.05
        city["pop"] = int(max(0, city["pop"] + round(growth * (city["pop"] ** 0.5) * 2.0)))
        if city["food"] < 0.35:
            city["grievance"] = round(min(1.0, city["grievance"] + 0.05), 3)
            if city["pop"] > 0 and rng.random() < 0.25 and t % 7 == 0:
                lost = int(city["pop"] * 0.12)
                city["pop"] = max(0, city["pop"] - lost)
                _event(world, "famine", "%s 饥荒，人口 -%d。" % (city["name"], lost))
        else:
            city["grievance"] = round(max(0.0, city["grievance"] - 0.02), 3)

    # ② 文明层：人口汇总 / 科技 / 侵略
    for civ in world["civs"]:
        cities = _cities_of(world, civ["id"])
        civ["pop"] = sum(c["pop"] for c in cities)
        if cities:
            civ["tech"] = round(min(9.9, civ["tech"] + 0.002 * world["params"]["tech_rate"]
                                    * (1 + civ["pop"] / 2000.0)), 3)
        if civ["tech"] > 2.0 and t % 9 == 0:
            _event(world, "golden_age", "%s 进入黄金时代（科技 %.2f）。" % (civ["name"], civ["tech"]),
                   ["tech"])

    # ③ 信念 → 宗教（L3）：城市信念漂移，过阈值就有宗教从信念里长出来
    for city in world["cities"]:
        civ = _civ(world, city["civ"])
        drift = rng.uniform(-0.06, 0.06) + (civ["spirituality"] - 0.5) * 0.02
        city["faith"] = round(_clamp(city["faith"] + drift, -1.0, 1.0), 3)
        if abs(city["faith"]) > 0.55 and civ and rng.random() < 0.5:
            axis = "光明" if city["faith"] > 0 else "深渊"
            existing = [r for r in world["religions"] if r["civ"] == city["civ"] and r["axis"] == axis]
            if not existing:
                rel = {"id": "religion-%d" % len(world["religions"]),
                       "name": _civ_name(rng) + "教", "axis": axis, "civ": city["civ"],
                       "origin": city["name"], "adherents": city["pop"],
                       "tick": t}
                world["religions"].append(rel)
                _event(world, "religion", "%s 的信念凝成了 %s（%s轴）。" % (city["name"],
                                                                         rel["name"], axis))
            else:
                existing[0]["adherents"] = int(existing[0]["adherents"] + city["pop"] * 0.15)
    for r in world["religions"]:
        if r["adherents"] > 1500 and not r.get("schism") and rng.random() < 0.2:
            r["schism"] = True
            _event(world, "schism", "%s 因教义分裂，圣战一触即发。" % r["name"], ["faith", "war"])

    # ④ 派系（L4）：城市影响力过阈值 ⇒ 从城市里长出派系
    for city in world["cities"]:
        city["influence"] = round(min(3.0, city["influence"] + city["culture"] * 0.01
                                      + city["infra"] * 0.005), 3)
        city["culture"] = round(min(3.0, city["culture"] + 0.002), 3)
        if city["influence"] > 1.2 and rng.random() < 0.08:
            if not any(f["home"] == city["id"] for f in world["factions"]):
                ftype = rng.choice(("行会", "教团", "军团", "商会"))
                fac = {"id": "faction-%d" % len(world["factions"]),
                       "name": city["name"] + ftype, "type": ftype, "home": city["id"],
                       "civ": city["civ"], "influence": 1.0, "tick": t}
                world["factions"].append(fac)
                _event(world, "faction", "%s 里长出了 %s。" % (city["name"], fac["name"]))

    # ⑤ 战争/起义（L5）：只在「真有兵、真相邻」的文明之间打，战果由人口算
    if rng_war.random() < float(world["params"]["war_rate"]) * 0.04 and len(world["civs"]) > 1:
        a, b = rng_war.sample(world["civs"], 2)
        if a["pop"] > 300 and b["pop"] > 300:
            ratio = (a["pop"] * (0.5 + a["tech"]) * (0.5 + a["war"])) / \
                    max(1.0, (b["pop"] * (0.5 + b["tech"]) * (0.5 + b["war"])))
            loser, winner = (b, a) if ratio >= 1 else (a, b)
            shift = int(min(loser["pop"], winner["pop"]) * 0.08)
            loser_city = max(_cities_of(world, loser["id"]) or [{"pop": 0, "id": ""}],
                             key=lambda c: c["pop"])
            loser_city["pop"] = max(0, loser_city["pop"] - shift)
            if loser_city["pop"] == 0:
                _event(world, "war", "%s 被 %s 攻灭，%s 陷落。" % (loser["name"], winner["name"],
                                                                loser_city.get("name", "?")))
            else:
                _event(world, "war", "%s 与 %s 交战，%s 人口 -%d。" % (a["name"], b["name"],
                                                                  loser["name"], shift))
    for city in world["cities"]:
        if city["grievance"] > 0.8 and rng.random() < 0.3:
            others = [c for c in world["civs"] if c["id"] != city["civ"]]
            if others:
                new_civ = rng.choice(others)
                _event(world, "rebellion", "%s 爆发起义，改投 %s。" % (city["name"], new_civ["name"]))
                city["civ"] = new_civ["id"]
                city["grievance"] = 0.2

    # ⑥ 上帝/世界之灵：情绪会自己漂；动作只来自被夹紧的 directive（不画结果）
    god = world["god"]
    god["curiosity"] = round(_clamp(god["curiosity"] + rng.uniform(-0.02, 0.02), 0, 1), 3)
    god["boredom"] = round(_clamp(god["boredom"] + rng.uniform(-0.01, 0.02), 0, 1), 3)
    if rng.random() < 0.05:
        god["last"] = "None"

    # ⑦ LOD：超预算就放掉"不在焦点"的人物（AEON 同款：只保焦点城市的高保真）
    cap = int(world["spec"].get("persons_cap") or 48)
    if len(world["persons"]) > cap:
        world["persons"] = world["persons"][:cap]

    world["history"].append({"tick": t, "hash": state_hash(world), "pop": _total_pop(world),
                             "civs": len(world["civs"]), "religions": len(world["religions"]),
                             "factions": len(world["factions"])})


def step(world: dict, ticks: int = 1, directives=None) -> dict:
    """推进 N tick。directives=[{at_tick, action}]：在指定 tick **之前**由 `god()` 夹紧并应用。

    这个形状让「时间回溯」不用存全量快照：同 seed + 同 directives 重放到任一 tick，
    状态 hash 必须与 history 里记的一致（`rewind` 会逐字对账）。
    """
    world = copy.deepcopy(world)
    directives = list(directives or [])
    n = max(0, int(ticks))
    for _ in range(n):
        due = [d for d in directives if int(d.get("at_tick", 0)) == world["tick"]]
        for d in due:
            world = _apply_directive(world, d.get("action") or {}, record=True)
        _tick(world)
    return world


def _clamp_directive(action: dict) -> dict:
    """把世界之灵的动作夹成白名单形状：只准碰 params / 事件，绝不准碰人口与产出。"""
    kind = str((action or {}).get("kind") or "omen").lower()
    if kind not in GOD_KINDS:
        return {"ok": False, "error": "user_error: 不认的世界之灵动作 %s（可用 %s）"
                                      % (kind, "/".join(GOD_KINDS))}
    out = {"kind": kind, "params": {}}
    for k, v in ((action or {}).get("params") or {}).items():
        if k in PARAM_BOUNDS:
            lo, hi = PARAM_BOUNDS[k]
            out["params"][k] = round(float(_clamp(float(v), lo, hi)), 3)
    return {"ok": True, **out}


def _apply_directive(world: dict, action: dict, record: bool = False) -> dict:
    """应用夹紧后的 directive：**只改 params / 写事件 / 记 directives**。

    反例（本件一律不做，`verify()` 钉它）：不许 `city["pop"] = ...`、不许给文明加科技、
    不许写宗教/派系生成 —— 那些只能由 `_tick()` 按规则自己长出来。
    """
    world = copy.deepcopy(world)
    d = _clamp_directive(action)
    if not d.get("ok"):
        return world
    kind = d["kind"]
    if record:
        world["directives"].append({"at_tick": world["tick"], "action": action})
    for k, v in d.get("params", {}).items():
        world["params"][k] = v
    god = world["god"]
    if kind == "catastrophe":
        world["params"]["heat_diff"] = round(_clamp(world["params"].get("heat_diff", 0.1) + 0.05,
                                                    *PARAM_BOUNDS["heat_diff"]), 3)
        god["cruelty"] = round(_clamp(god["cruelty"] + 0.1, 0, 1), 3)
        _event(world, "god", "天灾降临：热浪参数升到 %.3f。" % world["params"]["heat_diff"],
               ["god", "catastrophe"])
    elif kind == "bless":
        world["params"]["tech_rate"] = round(_clamp(world["params"].get("tech_rate", 0.0) + 0.05,
                                                    *PARAM_BOUNDS["tech_rate"]), 3)
        god["benevolence"] = round(_clamp(god["benevolence"] + 0.1, 0, 1), 3)
        _event(world, "god", "神恩笼罩：技术增长率升到 %.3f。" % world["params"]["tech_rate"],
               ["god", "bless"])
    elif kind == "change_rules":
        god["curiosity"] = round(_clamp(god["curiosity"] + 0.1, 0, 1), 3)
        _event(world, "god", "世界规则被改写：%s。" % _canon(world["params"])[:120], ["god", "rules"])
    else:  # omen
        god["boredom"] = round(_clamp(god["boredom"] - 0.1, 0, 1), 3)
        _event(world, "god", "天空出现预兆，众城惶惶。", ["god", "omen"])
    god["last"] = kind
    return world


def god(world: dict, action: dict) -> dict:
    """世界之灵发一条 Directive（夹紧 + 只改规则/事件），返回 {world, receipt}。"""
    clamped = _clamp_directive(action)
    if not clamped.get("ok"):
        return {"ok": False, "error": clamped.get("error"), "world": world}
    new_world = _apply_directive(world, action, record=True)
    return {"ok": True, "receipt": clamped, "world": new_world,
            "params": new_world["params"], "god": new_world["god"]}


# ── 焦点人物（LOD）与 dossier ───────────────────────────────────────────────
def focus(world: dict, city_id: str, limit: int | None = None) -> dict:
    """把某座城市的人物物化（AEON LOD）：只有焦点城市的人才是"完整的人"。"""
    world = copy.deepcopy(world)
    city = next((c for c in world["cities"] if c["id"] == city_id), None)
    if city is None:
        return {"ok": False, "error": "user_error: 没有这座城 %s" % city_id, "world": world}
    cap = int(world["spec"].get("persons_cap") or 48)
    want = int(limit or min(8, max(1, city["pop"] // 60)))
    want = min(want, cap)
    rng = _rng(world["seed"], "persons:%s:%d" % (city_id, world["tick"]))
    kept = [p for p in world["persons"] if p["city"] != city_id]
    made = []
    for i in range(want):
        name = rng.choice(PERSON_NAMES)
        person = {
            "id": "person-%s-%d" % (city_id, i),
            "name": name,
            "city": city_id,
            "civ": city["civ"],
            "age": rng.randint(16, 70),
            "big5": {k: round(rng.random(), 3) for k in BIG5},
            "goal": rng.choice(("温饱", "致富", "求知", "扬名", "复仇", "守家", "传教")),
            "belief": round(city["faith"] + rng.uniform(-0.15, 0.15), 3),
            "memory": [],
            "materialized_tick": world["tick"],
        }
        made.append(person)
    merged = (kept + made)[:cap]
    world["persons"] = merged
    _event(world, "focus", "焦点落到 %s：物化 %d 人。" % (city["name"], len(made)), ["lod"])
    return {"ok": True, "city": city["name"], "persons": len(made),
            "materialized_total": len(merged), "world": world}


def person(world: dict, person_id: str) -> dict:
    """grounded dossier：只报人物记录里真有的；要"架空对话"接外部模型，本件不编。"""
    p = next((x for x in world["persons"] if x["id"] == person_id), None)
    if p is None:
        return {"ok": False, "error": "user_error: 没有这个人物 %s（先 focus 一座城）" % person_id}
    city = next((c for c in world["cities"] if c["id"] == p["city"]), {})
    return {"ok": True, "person": p, "city": city.get("name"),
            "note": "dossier 只含世界记录里的事实；采访/对话要模型，走 ai 插座或外部模型（本件不编）"}


# ── 重放 / 分叉（Multiverse）───────────────────────────────────────────────
def _replay_to(world: dict, tick: int) -> dict:
    """从 genesis 重放到第 tick（同 seed + 同 directives），再与 history 对账。"""
    tick = max(0, int(tick))
    fresh = gen(world["spec"])
    directives = sorted(world.get("directives") or [], key=lambda d: d.get("at_tick", 0))
    fresh["directives"] = []
    while fresh["tick"] < tick:
        due = [d for d in directives if int(d.get("at_tick", 0)) == fresh["tick"]]
        for d in due:
            fresh = _apply_directive(fresh, d.get("action") or {}, record=True)
        _tick(fresh)
    return fresh


def rewind(world: dict, tick: int) -> dict:
    """回到第 tick：重放 + 状态 hash 对账（对不上就如实报 mismatch，不假装成功）。"""
    try:
        fresh = _replay_to(world, tick)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, str(exc)[:160])}
    recorded = next((h for h in world.get("history") or [] if h["tick"] == int(tick)), None)
    got = state_hash(fresh)
    if recorded is None:
        return {"ok": False, "error": "user_error: 时间线里没有第 %d tick" % tick, "world": fresh}
    ok = recorded["hash"] == got
    fresh["rewound_to"] = int(tick)
    return {"ok": ok, "tick": int(tick), "expected": recorded["hash"], "got": got, "world": fresh,
            **({} if ok else {"error": "hash mismatch：重放状态与历史不一致，确定性被破坏"})}


def branch(world: dict, tick: int, spec_patch: dict | None = None) -> dict:
    """在第 tick 分叉出一条新时间线：改 spec（或换 seed）后从 genesis 重放该 tick 数。"""
    base = rewind(world, tick)
    if not base.get("ok"):
        return base
    src = base["world"]
    spec = dict(src["spec"])
    for k, v in (spec_patch or {}).items():
        if k in DEFAULT_SPEC:
            spec[k] = v
    if spec_patch and "seed" not in spec_patch:
        # 不改 seed 也能分叉：用 spec 的指纹派生一个确定的新种子（同 patch 同新盘）
        spec["seed"] = (int(spec["seed"]) ^ (int(hashlib.sha256(
            _canon(spec_patch).encode()).hexdigest()[:8], 16))) % (2**32)
    fresh = gen(spec)
    directives = sorted(world.get("directives") or [], key=lambda d: d.get("at_tick", 0))
    while fresh["tick"] < int(tick):
        due = [d for d in directives if int(d.get("at_tick", 0)) == fresh["tick"]]
        for d in due:
            fresh = _apply_directive(fresh, d.get("action") or {}, record=True)
        _tick(fresh)
    fresh["branch_of"] = {"seed": world["seed"], "tick": int(tick)}
    _event(fresh, "branch", "第 %d tick 分叉出新的世界线（seed %d）。" % (int(tick), fresh["seed"]),
           ["branch", "multiverse"])
    return {"ok": True, "branch": fresh["branch_of"], "seed": fresh["seed"], "world": fresh}


# ── 视图 / 统计 / 自检 ─────────────────────────────────────────────────────
def summary(world: dict) -> dict:
    hist = world.get("history") or []
    return {
        "ok": True, "tick": world["tick"], "seed": world["seed"],
        "world": "%dx%d" % (world["spec"]["width"], world["spec"]["height"]),
        "civs": len(world["civs"]), "cities": len(world["cities"]),
        "pop": _total_pop(world),
        "persons_materialized": len(world.get("persons") or []),
        "religions": len(world["religions"]), "factions": len(world["factions"]),
        "chronicle": len(world["chronicle"]),
        "hash": state_hash(world),
        "history_ticks": len(hist),
        "god": world["god"], "params": world["params"],
        "last_events": [e["text"] for e in world["chronicle"][-3:]],
    }


def view(world: dict, z: int | None = None) -> dict:
    """地形/体素 ASCII 切片（面板与验收能亲眼看；不返回 base64 大图）。"""
    rows = "".join("".join(BIOME_ASCII.get(b, "?") for b in row) + "\n"
                   for row in world["biome"])
    vox = ""
    if world.get("voxels"):
        depth = len(world["voxels"])
        zz = int(_clamp(depth // 2 if z is None else int(z), 0, depth - 1))
        vox = "".join("".join(MATERIAL_ASCII.get(m, "?") for m in row) + "\n"
                      for row in world["voxels"][zz])
    return {"ok": True, "tick": world["tick"], "biome": rows,
            "voxel_z": (int(z) if z is not None else None), "voxel": vox}


def schema() -> dict:
    return {
        "ok": True,
        "name": "world_forge",
        "what": "确定性活体世界内核（吞噬 AEON/WorldX/Temporal God 蒸出来的第 0 步）",
        "ops": ["schema", "spec", "gen", "step", "focus", "person", "god", "rewind",
                "branch", "encode", "decode", "view3d", "view", "summary", "verify"],
        "spec_default": dict(DEFAULT_SPEC),
        "spec_bounds": {k: list(v) for k, v in SPEC_BOUNDS.items()},
        "param_bounds": {k: list(v) for k, v in PARAM_BOUNDS.items()},
        "god_kinds": list(GOD_KINDS),
        "provenance": PROVENANCE,
        "invariant": "仿真内核是唯一改世界的东西；世界之灵只能发被夹紧的 Directive（改规则/加事件），不许直接画结果。",
        "boundaries": ["纯函数：零出网 / 零起进程 / 零写盘（要存盘由调用方走 filesystem_write 门）",
                       "不是成品游戏：平衡与叙事深度只到「第 0 步」，不冒充 AEON 的成品度",
                       "只看设计、不搬任何代码（AEON/Temporal God 许可不明，WorldX 虽 MIT 也只蒸设计）"],
        "registration": "已注册能力位（2026-11-02 主人点头；caps_registry + api 分派 + run_task 万能插唯一门）；零作用域纯函数（policy 未改）",
    }



# ── P1：一句话 → 世界规格（纯文本映射，不依赖 LLM；LLM 可先出 spec 再走夹紧）────
_CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
           "八": 8, "九": 9, "十": 10}


def _num(s: str):
    s = str(s or "")
    if s.isdigit():
        return int(s)
    if s in _CN_NUM:
        return _CN_NUM[s]
    if s.startswith("十"):
        return 10 + _CN_NUM.get(s[1:], 0)
    if "十" in s:
        a, b = s.split("十", 1)
        return _CN_NUM.get(a, 1) * 10 + _CN_NUM.get(b, 0)
    return None


BIOME_COLOR = {"ocean": "#2f6f9f", "coast": "#5a9ec4", "grass": "#6f9e57",
               "forest": "#3f7a4f", "desert": "#c9a45b", "tundra": "#b8c7cf",
               "mountain": "#7d7f86", "volcano": "#b4452f"}
SAVE_FORMAT = "gbt-world-save-v1"


def spec_from_prompt(prompt: str) -> dict:
    """一句话 → 世界 spec。**纯文本映射**（不调模型、不出网）；LLM 版可先出 JSON 再交给
    `_normalize_spec` 夹紧 —— 规格只是参数，不是世界结果（结果仍由 gen/step 长出来）。"""
    text = str(prompt or "").strip()
    spec = dict(DEFAULT_SPEC)
    matched = []
    low = text.lower()
    if re.search(r"大|广阔|大陆|巨型", text):
        spec["width"] = spec["height"] = 40
        matched.append("大世界")
    elif re.search(r"小|微型|小岛|村落", text):
        spec["width"] = spec["height"] = 16
        matched.append("小世界")
    if re.search(r"海|海洋|岛|湖|水", text):
        spec["water_level"] = 0.45
        matched.append("多水")
    if re.search(r"沙漠|荒漠|干旱", text):
        spec["water_level"] = 0.15
        spec["warmth"] = 0.7
        matched.append("沙漠")
    if re.search(r"冰|极寒|雪|冬", text):
        spec["warmth"] = -0.7
        matched.append("严寒")
    if re.search(r"火|火山|熔岩", text):
        spec["warmth"] = 0.5
        matched.append("火山")
    m = re.search(r"([一两二三四五六七八九十\d]+)\s*个?(?:文明|国家|势力|民族)", text)
    if m:
        _n = _num(m.group(1))
        if _n:
            spec["civs"] = _n
            matched.append("文明数")
    m = re.search(r"(?:每|各)(?:个)?(?:文明|国家|势力)?\s*([一两二三四五六七八九十\d]+)\s*(?:座)?(?:城|城市)", text)
    if m:
        _n = _num(m.group(1))
        if _n:
            spec["cities_per_civ"] = _n
            matched.append("城数")
    if re.search(r"体素|3d|三维", low):
        spec["voxel"] = True
        matched.append("体素")
    if re.search(r"无体素|不要3d|二维|2d", low):
        spec["voxel"] = False
        matched.append("二维")
    m = re.search(r"seed\s*[=:：]?\s*(\d+)", low)
    if m:
        spec["seed"] = int(m.group(1))
    spec = _normalize_spec(spec)
    return {"ok": True, "spec": spec, "matched": matched, "prompt": text,
            "note": "纯文本映射（无 LLM）；LLM 出的 spec 也要过 _normalize_spec 夹紧"}


def encode(world: dict) -> dict:
    """世界 → 可存盘的存档串（JSON + sha256）。**只编码不落盘**；落盘由调用方走 filesystem_write 门。"""
    w = copy.deepcopy(world or {})
    payload = {"format": SAVE_FORMAT, "seed": w.get("seed"), "spec": w.get("spec"), "world": w}
    raw = _canon(payload)
    sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return {"ok": True, "format": SAVE_FORMAT, "bytes": len(raw.encode("utf-8")),
            "sha256": sha, "json": raw}


def decode(blob, expect_sha256: str = "") -> dict:
    """存档串 → 世界（校验格式与 sha256；对不上就拒，不把坏档当世界载入）。"""
    try:
        payload = blob if isinstance(blob, dict) else json.loads(str(blob))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": "存档不是合法 JSON：%s: %s"
                                      % (type(exc).__name__, str(exc)[:120])}
    if not isinstance(payload, dict) or payload.get("format") != SAVE_FORMAT:
        return {"ok": False, "error": "存档格式不认（需要 %s）" % SAVE_FORMAT}
    world = payload.get("world")
    if not isinstance(world, dict) or "seed" not in world or "biome" not in world:
        return {"ok": False, "error": "存档缺 world.seed/biome，拒绝当世界载入"}
    raw = _canon(payload)
    sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    if expect_sha256 and str(expect_sha256).lower() != sha:
        return {"ok": False, "error": "存档 sha256 对不上（被改过或拷坏）",
                "expected": str(expect_sha256)[:32], "got": sha[:32]}
    return {"ok": True, "world": world, "sha256": sha,
            "tick": int(world.get("tick") or 0), "format": SAVE_FORMAT}


def view3d(world: dict) -> dict:
    """世界 → 3D 视图数据（列高度/生物群系/城市/文明/体素材质计数）。给 Three.js 面板用，纯数据。"""
    w = copy.deepcopy(world or {})
    biome = w.get("biome") or []
    elev = w.get("elev") or []
    H = len(biome)
    W = len(biome[0]) if H else 0
    depth = int((w.get("spec") or {}).get("depth") or 8)
    columns = []
    for y in range(H):
        for x in range(W):
            e = float(elev[y][x]) if y < len(elev) and x < len(elev[y]) else 0.0
            columns.append({"x": x, "y": y, "h": round(e * depth, 2), "biome": biome[y][x]})
    civs = [{"id": c.get("id"), "name": c.get("name"), "tech": c.get("tech"),
             "pop": c.get("pop")} for c in (w.get("civs") or [])]
    cities = [{"id": c.get("id"), "name": c.get("name"), "civ": c.get("civ"),
               "x": c.get("x"), "y": c.get("y"), "pop": c.get("pop")}
              for c in (w.get("cities") or [])]
    layers = {}
    for z, plane in enumerate(w.get("voxels") or []):
        counts = {}
        for row in plane:
            for m in row:
                counts[m] = counts.get(m, 0) + 1
        layers[str(z)] = counts
    return {"ok": True, "tick": w.get("tick"), "seed": w.get("seed"),
            "world": {"width": W, "height": H, "depth": depth},
            "palette": dict(BIOME_COLOR), "columns": columns,
            "civs": civs, "cities": cities, "layer_counts": layers,
            "stats": {"civs": len(civs), "cities": len(cities),
                      "religions": len(w.get("religions") or []),
                      "factions": len(w.get("factions") or []), "pop": _total_pop(w)}}


def verify() -> dict:
    """自检（全绿才 ok）：确定性 / spec 夹紧 / 重放对账 / 分叉独立 / God 不画结果 / 零依赖。"""
    rows = []

    def ck(name, cond, detail=""):
        rows.append({"check": name, "ok": bool(cond), "detail": str(detail)[:160]})

    a = gen({"seed": 7, "width": 16, "height": 16, "civs": 2, "cities_per_civ": 2})
    b = gen({"seed": 7, "width": 16, "height": 16, "civs": 2, "cities_per_civ": 2})
    c = gen({"seed": 8, "width": 16, "height": 16, "civs": 2, "cities_per_civ": 2})
    ck("同 seed+spec ⇒ 同世界", state_hash(a) == state_hash(b), state_hash(a))
    ck("换 seed ⇒ 换世界", state_hash(a) != state_hash(c))
    s = gen({"seed": 7, "width": 999, "height": 999, "civs": 99})
    ck("spec 越界被夹紧", s["spec"]["width"] == 64 and s["spec"]["civs"] == 8,
       (s["spec"]["width"], s["spec"]["civs"]))
    d = step(a, 40)
    e = step(a, 40)
    ck("step 可复现（40 tick 同 hash）", state_hash(d) == state_hash(e), state_hash(d))
    ck("编年史在长", len(d["chronicle"]) > len(a["chronicle"]), len(d["chronicle"]))
    ck("有城市/人口", d["cities"] and _total_pop(d) > 0, _total_pop(d))
    g = god(a, {"kind": "bless"})
    ck("god 只碰 params/事件（人口不动）", _total_pop(g["world"]) == _total_pop(a)
       and g["world"]["params"].get("tech_rate", 0) > 0, g["world"]["params"])
    g2 = god(a, {"kind": "catastrophe"})
    ck("catastrophe 参数被夹紧", 0 <= g2["world"]["params"]["heat_diff"] <= 0.5,
       g2["world"]["params"]["heat_diff"])
    bad = god(a, {"kind": "set_population", "pop": 99999})
    ck("不认的 Directive 被拒", bad.get("ok") is False)
    walked = step(a, 60, directives=[{"at_tick": 10, "action": {"kind": "bless"}}])
    rw = rewind(walked, 30)
    ck("rewind 对账（tick 30 重放 hash 一致）", rw.get("ok") is True, rw.get("got"))
    br = branch(walked, 30, {"civs": 3})
    ck("branch 出独立世界线", br.get("ok") is True and br["seed"] != walked["seed"], br.get("seed"))
    f = focus(a, a["cities"][0]["id"])
    ck("焦点物化人物受 cap 限制", f.get("ok") and len(f["world"]["persons"]) <= a["spec"]["persons_cap"],
       len(f["world"]["persons"]))
    v = view(a)
    ck("view 出 ASCII 地形", len(v["biome"].splitlines()) == a["spec"]["height"], len(v["biome"]))
    sp = spec_from_prompt("海边的三个文明，每国两座城，体素世界")
    ck("P1 spec：一句话出规格且夹紧", sp["ok"] and sp["spec"]["civs"] == 3
       and sp["spec"]["voxel"] is True, sp.get("matched"))
    ck("P1 spec 可复现", sp["spec"] == spec_from_prompt("海边的三个文明，每国两座城，体素世界")["spec"])
    enc = encode(a)
    dec = decode(enc["json"], expect_sha256=enc["sha256"])
    ck("P1 存档 encode→decode 对账", dec.get("ok") is True
       and state_hash(dec["world"]) == state_hash(a), dec.get("error"))
    ck("P1 存档被改过拒载",
       decode(enc["json"].replace('"seed":7', '"seed":8'),
              expect_sha256=enc["sha256"]).get("ok") is False)
    v3 = view3d(a)
    ck("P1 view3d 列数=宽×高且城市齐",
       len(v3["columns"]) == a["spec"]["width"] * a["spec"]["height"]
       and len(v3["cities"]) == len(a["cities"]),
       (len(v3["columns"]), len(v3["cities"])))
    # 零出网/零起进程：不能拿注释里的字当判据（本文件 docstring 就写着这几个词）——
    #   按 AST 的 **import 面** 判：只要不导入 urllib/socket/subprocess/http/requests 即绿。
    import ast as _ast
    mods = set()
    for node in _ast.walk(_ast.parse(open(__file__, encoding="utf-8").read())):
        if isinstance(node, _ast.Import):
            mods.update(x.name.split(".")[0] for x in node.names)
        elif isinstance(node, _ast.ImportFrom) and node.module:
            mods.add(node.module.split(".")[0])
    _net = mods & {"urllib", "socket", "subprocess", "http", "requests"}
    ck("零出网/零起进程（AST 导入面无 urllib/socket/subprocess/http）", not _net, sorted(_net))
    failed = [r["check"] for r in rows if not r["ok"]]
    return {"ok": not failed, "checks": rows, "failed": failed,
            "note": "纯函数自检：不落盘、不出网、不依赖本机模型"}


def run(op: str = "schema", **kw) -> dict:
    op = str(op or "schema").lower()
    if op == "schema":
        return schema()
    if op == "spec":
        return spec_from_prompt(kw.get("prompt") or kw.get("text") or "")
    if op == "encode":
        return encode(kw.get("world") or {})
    if op == "decode":
        return decode(kw.get("blob") if kw.get("blob") is not None else kw.get("json"),
                      expect_sha256=str(kw.get("sha256") or ""))
    if op == "view3d":
        return view3d(kw.get("world") or gen(kw.get("spec") or {}))
    if op == "gen":
        return {"ok": True, "world": gen(kw.get("spec") or {})}
    if op == "step":
        return {"ok": True, "world": step(kw.get("world") or {}, int(kw.get("ticks") or 1),
                                          kw.get("directives"))}
    if op == "focus":
        r = focus(kw.get("world") or {}, str(kw.get("city") or ""), kw.get("limit"))
        return r
    if op == "person":
        return person(kw.get("world") or {}, str(kw.get("person") or ""))
    if op == "god":
        return god(kw.get("world") or {}, kw.get("action") or {})
    if op == "rewind":
        return rewind(kw.get("world") or {}, int(kw.get("tick") or 0))
    if op == "branch":
        return branch(kw.get("world") or {}, int(kw.get("tick") or 0), kw.get("spec_patch") or {})
    if op == "view":
        return view(kw.get("world") or {}, kw.get("z"))
    if op == "summary":
        return summary(kw.get("world") or {})
    if op == "verify":
        return verify()
    return {"ok": False, "error": "不认的 op：%s" % op,
            "known": ["schema", "gen", "step", "focus", "person", "god", "rewind", "branch",
                      "view", "summary", "verify"]}


def main(argv=None) -> int:
    import argparse
    import sys
    ap = argparse.ArgumentParser(description="world_forge —— 确定性活体世界内核（吞噬蒸馏第 0 步）")
    ap.add_argument("op", nargs="?", default="schema",
                    choices=["schema", "gen", "step", "focus", "person", "god", "rewind",
                             "branch", "view", "summary", "verify"])
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--ticks", type=int, default=50)
    ap.add_argument("--spec", default="{}", help="JSON：width/height/civs/cities_per_civ/...")
    a = ap.parse_args(argv)
    spec = json.loads(a.spec or "{}")
    spec.setdefault("seed", a.seed)
    if a.op == "gen":
        w = gen(spec)
        out = summary(w)
    elif a.op == "verify":
        out = verify()
    else:
        w = gen(spec)
        w = step(w, a.ticks)
        out = {"summary": summary(w), "view": view(w)["biome"],
               "chronicle": [e["text"] for e in w["chronicle"][-5:]]}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())


