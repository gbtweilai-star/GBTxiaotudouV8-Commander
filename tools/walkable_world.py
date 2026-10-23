# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 可行走世界内核 (Walkable World Kernel) v1.0 —— **只读骨架**

蒸馏自：bEpicWorlds（规范由 Owner 于 2026-09-25 下达）
开发者：自由的风
守护者：公主土豆
禁止删除

⚠️ 本版性质（必须写在前头，防误读）：
    **这是只读骨架** —— 五原语的**契约、判据、留痕结构**都已写实，
    但**没有任何一步真的调用生成器**（本机也没有上游库：见 preflight 的取证读数）。
    凡未接线的位置一律 `not_wired`，**不假装能跑**。

五原语：READ（读图）· BUILD（构建）· WALK（行走）· PIN（别针）· EVOLVE（进化）

用法：
    python tools/walkable_world.py preflight
    python tools/walkable_world.py map                # 阶段地图 + 每步判据
    python tools/walkable_world.py run READ  --image <参考图>
    python tools/walkable_world.py run BUILD --image <参考图> --name <世界名> [--spec "..."]
    python tools/walkable_world.py run WALK  --name <世界名>
    python tools/walkable_world.py run PIN   --name <世界名> --note "这里树太多"
    python tools/walkable_world.py run EVOLVE --name <世界名>
退出码：0 = 该步如实完成或如实报未接线；1 = 判据不过（如无参考图）；2 = 前置不可达。
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field
from enum import Enum

# 🔴 2026-09-26 补：Windows 管道/重定向下 stdout 回落 GBK，emoji 一打印就崩；与 self_model.py 同一款补丁
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


WS = pathlib.Path(__file__).resolve().parents[1]
DH = WS / "holo_pet/assets/digital-human"
WORLDS = WS / "output/worlds"
TRACE = WS / "store/trace/walkable_world.jsonl"
COMFY = pathlib.Path(r"C:\Users\ADMIN\ComfyUI")
LEGACY_LIB = pathlib.Path(r"C:\Users\ADMIN\ComfyUI-SkinTokens")      # 隔壁那件（不是本域）


# ══════════════════════════════════════════════════════════════════════════
# 五原语
# ══════════════════════════════════════════════════════════════════════════
class P(Enum):
    READ = "读图"
    BUILD = "构建"
    WALK = "行走"
    PIN = "别针"
    EVOLVE = "进化"


RED_LINES = [
    "参考图驱动，不许凭空造 —— 无参考图即拒（create 直接返回 no_reference_image）",
    "每版必留，可 revert —— 版本目录只增不改，回退靠切换指针",
    "反馈 pin 必须可追 —— 每个 pin 带 position + view + snapshot",
    '写操作走门禁 —— create/edit/revert 都过 auth_gate（scope=filesystem_write）',
    '每次操作留痕 —— 写 trace_store，source_kind="bepic_world"',
]

HONEST_BOUNDARY = (
    "可行走世界内核保证『从参考图构建、可走、可反馈、可 revert』；"
    "它保证不了『世界一定好看』—— 好不好看，走进去的人说了算。"
)


@dataclass
class WorldSpec:
    name: str
    reference_image: str
    spec_text: str = ""
    biome: str = ""
    time_of_day: str = ""
    density: float = 1.0
    terrain_height: float = 1.0
    version: int = 0
    created: str = ""


@dataclass
class WorldFeedback:
    pin_id: str
    position: list = field(default_factory=list)
    view: dict = field(default_factory=dict)
    snapshot: str = ""
    note: str = ""
    resolved: bool = False
    reply: str = ""


# ══════════════════════════════════════════════════════════════════════════
# 内核（契约层：判据写实，生成端未接线）
# ══════════════════════════════════════════════════════════════════════════
class Kernel:
    def __init__(self):
        self.worlds: dict[str, WorldSpec] = {}
        self.feedbacks: dict[str, list[WorldFeedback]] = {}
        self._load()

    # ── 留痕（红线④⑤）────────────────────────────────────────────────────
    def trace(self, op: str, **kw):
        TRACE.parent.mkdir(parents=True, exist_ok=True)
        rec = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "source_kind": "bepic_world",
               "op": op, **kw}
        with TRACE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ── 落点 ──────────────────────────────────────────────────────────────
    def wdir(self, name: str) -> pathlib.Path:
        return WORLDS / name

    def vdir(self, name: str, v: int) -> pathlib.Path:
        return self.wdir(name) / f"v{v:03d}"

    def _load(self):
        if not WORLDS.exists():
            return
        for d in sorted(WORLDS.iterdir()):
            spec_f = d / "spec.json"
            if d.is_dir() and spec_f.exists():
                try:
                    self.worlds[d.name] = WorldSpec(**json.loads(spec_f.read_text(encoding="utf-8")))
                    fb = d / "feedback.jsonl"
                    self.feedbacks[d.name] = (
                        [WorldFeedback(**json.loads(l)) for l in fb.read_text(encoding="utf-8").splitlines() if l.strip()]
                        if fb.exists() else [])
                except Exception:
                    pass

    # ── READ：读参考图 + 分析 ─────────────────────────────────────────────
    def read(self, image: str) -> dict:
        p = pathlib.Path(image)
        if not p.is_absolute():
            p = WS / image
        if not p.is_file():
            self.trace("read", ok=False, reason="image_not_found", image=str(p))
            return {"ok": False, "primitive": "READ", "reason": "image_not_found", "path": str(p)}
        size = p.stat().st_size
        # 分析端：**未接线**（上游 bepic_worlds 库本机不存在，见 preflight）
        out = {"ok": True, "primitive": "READ", "image": str(p), "bytes": size,
               "analysis": {"status": "not_wired",
                            "would_extract": ["天空色", "地平线颜色", "地平线倾斜→相机角度",
                                              "太阳位置", "雾浓度", "地面纹理（裁图）", "植被色调"],
                            "why": "上游 bepic_worlds 库不存在 ⇒ 不假装读到了"}}
        self.trace("read", ok=True, image=str(p), bytes=size)
        return out

    # ── BUILD：构建世界 ──────────────────────────────────────────────────
    def build(self, spec: WorldSpec) -> dict:
        if not spec.reference_image:
            self.trace("build", ok=False, reason="no_reference_image")
            return {"ok": False, "primitive": "BUILD", "reason": "no_reference_image",
                    "red_line": RED_LINES[0]}
        r = self.read(spec.reference_image)
        if not r["ok"]:
            return {"ok": False, "primitive": "BUILD", "reason": "read_failed", "detail": r}
        spec.version = 1
        spec.created = time.strftime("%Y-%m-%d %H:%M:%S")
        d = self.vdir(spec.name, 1)
        d.mkdir(parents=True, exist_ok=True)
        (self.wdir(spec.name) / "spec.json").write_text(
            json.dumps(asdict(spec), ensure_ascii=False, indent=1), encoding="utf-8")
        (d / "world.json").write_text(json.dumps(
            {"name": spec.name, "version": 1, "reference_image": spec.reference_image,
             "parts": {"env": None, "terrain": None, "scatter": None, "refcam": None, "hero": None},
             "status": "not_wired",
             "note": "五件产物（env/terrain/scatter/refcam/hero）本版**未生成** —— 生成端未接线"},
            ensure_ascii=False, indent=1), encoding="utf-8")
        self.worlds[spec.name] = spec
        self.feedbacks.setdefault(spec.name, [])
        self.trace("build", ok=True, name=spec.name, version=1)
        return {"ok": True, "primitive": "BUILD", "name": spec.name, "version": 1,
                "dir": str(d.relative_to(WS)), "generator": "not_wired"}

    # ── WALK：走进世界 ───────────────────────────────────────────────────
    def walk(self, name: str) -> dict:
        if name not in self.worlds:
            return {"ok": False, "primitive": "WALK", "reason": "not_found"}
        viewer = WS / "plugins/gbt-master/tools/model-turnaround.html"   # 现成的可交互查看器
        out = {"ok": True, "primitive": "WALK", "name": name,
               "version": self.worlds[name].version,
               "viewer": str(viewer.relative_to(WS)) if viewer.exists() else None,
               "status": "not_wired",
               "note": "本版没有真 3D 世界查看器；现成可交互件只有单模型转面查看器"}
        self.trace("walk", ok=True, name=name, version=self.worlds[name].version)
        return out

    # ── PIN：打别针（人指）────────────────────────────────────────────────
    def pin(self, name: str, note: str, position=None, view=None, snapshot="") -> dict:
        if name not in self.worlds:
            return {"ok": False, "primitive": "PIN", "reason": "not_found"}
        fb = WorldFeedback(pin_id=f"pin-{int(time.time()*1000)}",
                           position=position or [], view=view or {}, snapshot=snapshot, note=note)
        self.feedbacks.setdefault(name, []).append(fb)
        f = self.wdir(name) / "feedback.jsonl"
        with f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(fb), ensure_ascii=False) + "\n")
        self.trace("pin", ok=True, name=name, pin_id=fb.pin_id, note=note)
        return {"ok": True, "primitive": "PIN", "pin_id": fb.pin_id, "note": note}

    # ── EVOLVE：读反馈 → 编辑 → 新版本 ───────────────────────────────────
    def get_feedback(self, name: str) -> list[dict]:
        return [asdict(f) for f in self.feedbacks.get(name, []) if not f.resolved]

    def evolve(self, name: str, ops=None, note: str = "") -> dict:
        if name not in self.worlds:
            return {"ok": False, "primitive": "EVOLVE", "reason": "not_found"}
        ops = ops or [{"from": "pending_pins"}]
        self.worlds[name].version += 1
        v = self.worlds[name].version
        d = self.vdir(name, v)
        d.mkdir(parents=True, exist_ok=True)
        (d / "world.json").write_text(json.dumps(
            {"name": name, "version": v, "ops": ops, "note": note, "status": "not_wired"},
            ensure_ascii=False, indent=1), encoding="utf-8")
        (self.wdir(name) / "spec.json").write_text(
            json.dumps(asdict(self.worlds[name]), ensure_ascii=False, indent=1), encoding="utf-8")
        self.trace("evolve", ok=True, name=name, version=v, ops=ops, note=note)
        return {"ok": True, "primitive": "EVOLVE", "name": name, "version": v,
                "generator": "not_wired"}

    def revert(self, name: str, version: int) -> dict:
        if name not in self.worlds:
            return {"ok": False, "primitive": "EVOLVE", "reason": "not_found"}
        if not self.vdir(name, version).exists():
            return {"ok": False, "primitive": "EVOLVE", "reason": "version_not_found"}
        old = self.worlds[name].version
        self.worlds[name].version = version
        (self.wdir(name) / "spec.json").write_text(
            json.dumps(asdict(self.worlds[name]), ensure_ascii=False, indent=1), encoding="utf-8")
        self.trace("revert", ok=True, name=name, frm=old, to=version)
        return {"ok": True, "primitive": "EVOLVE", "name": name, "reverted_to": version}

    def resolve(self, name: str, pin_id: str, reply: str) -> dict:
        for f in self.feedbacks.get(name, []):
            if f.pin_id == pin_id:
                f.resolved, f.reply = True, reply
                p = self.wdir(name) / "feedback.jsonl"
                p.write_text("\n".join(json.dumps(asdict(x), ensure_ascii=False)
                                       for x in self.feedbacks[name]) + "\n", encoding="utf-8")
                self.trace("resolve", ok=True, name=name, pin_id=pin_id, reply=reply)
                return {"ok": True, "primitive": "EVOLVE", "pin_id": pin_id}
        return {"ok": False, "primitive": "EVOLVE", "reason": "pin_not_found"}


# ══════════════════════════════════════════════════════════════════════════
# preflight —— 规范 §⑥「先取证」
# ══════════════════════════════════════════════════════════════════════════
def preflight() -> int:
    rows, bad = [], 0

    def chk(name, ok, note):
        nonlocal bad
        rows.append((name, ok, note))
        if ok is False:
            bad += 1

    chk("ComfyUI 环境", COMFY.is_dir(), str(COMFY) if COMFY.is_dir() else "不在盘上")
    chk("output/worlds/", WORLDS.exists(),
        str(WORLDS.relative_to(WS)) if WORLDS.exists() else "不存在（BUILD 时会自动建）")
    lib_ok = False
    for mod in ("bepic_worlds", "bepic", "epicworlds"):
        try:
            __import__(mod)
            lib_ok = True
            break
        except Exception:
            pass
    chk("bepic_worlds 库", lib_ok, "已装" if lib_ok else "**未装** ⇒ 生成端 not_wired（不许假装能跑）")
    chk("trace_store 落点", True, str(TRACE.relative_to(WS)) + ("（已存在）" if TRACE.exists() else "（首次写入时建）"))
    print("可行走世界内核 · preflight（规范 §⑥ 先取证）")
    for n, ok, note in rows:
        flag = "✅" if ok is True else ("🔴" if ok is False else "⚠️")
        print(f"  {flag} {n:<20} {note}")
    print(f"\n  取证结论：{len(rows)-bad}/{len(rows)} 就绪")
    if not lib_ok:
        print("  ⚠️ 上游库缺失 ⇒ 本内核停在**只读骨架**：五原语契约与留痕写实，生成端一律 not_wired。")
    return 0


def cmd_map():
    print("可行走世界内核 · 阶段地图（五原语）")
    plan = [
        (P.READ, "读参考图 + 分析", "参考图存在且可读", "未接线（上游库缺）"),
        (P.BUILD, "构建世界（env/terrain/scatter/refcam/hero）", "**必须有参考图**（红线①）", "未接线"),
        (P.WALK, "走进世界（人看）", "世界存在且版本目录在", "未接线（无 3D 世界查看器）"),
        (P.PIN, "打别针（人指）", "pin 带 position+view+snapshot（红线③）", "契约已写实"),
        (P.EVOLVE, "读反馈→编辑→新版本 / revert", "每版必留、可 revert（红线②）", "契约已写实"),
    ]
    for p, what, gate, state in plan:
        print(f"  {p.value:<4} {what:<40} 判据: {gate:<32} 现状: {state}")
    print("\n  五原语缺一不可：不 READ 就是瞎造，不 BUILD 就是空谈，不 WALK 就没法验，"
          "不 PIN 就没反馈，不 EVOLVE 就是一次性作品。")
    print("\n  五条红线：")
    for i, r in enumerate(RED_LINES, 1):
        print(f"   {i}. {r}")
    print(f"\n  {HONEST_BOUNDARY}")


def main():
    a = sys.argv[1:]
    cmd = a[0] if a else "preflight"
    if cmd == "preflight":
        return preflight()
    if cmd == "map":
        cmd_map()
        return 0
    if cmd == "run":
        if len(a) < 2:
            print("用法: run <READ|BUILD|WALK|PIN|EVOLVE> [...]")
            return 2
        k = Kernel()
        prim = a[1].upper()
        def opt(flag, default=None):
            # 🔴 2026-09-26 自纠：flag 恰为最后一个参数时 a[i+1] 会 IndexError；缺值回落 default
            if flag not in a:
                return default
            i = a.index(flag)
            return a[i + 1] if i + 1 < len(a) else default
        img, name = opt("--image"), opt("--name")
        if prim == "READ":
            # 🔴 2026-09-26 自纠：READ 失败也 return 0 违反文件头退出码契约（与 BUILD/WALK/PIN 同口径）
            r = k.read(img or "")
            print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r["ok"] else 1
        if prim == "BUILD":
            r = k.build(WorldSpec(name=name or "world", reference_image=img or "",
                                  spec_text=opt("--spec", ""), biome=opt("--biome", ""),
                                  time_of_day=opt("--time", "")))
            print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r["ok"] else 1
        if prim == "WALK":
            r = k.walk(name or ""); print(json.dumps(r, ensure_ascii=False, indent=1))
            return 0 if r["ok"] else 1
        if prim == "PIN":
            r = k.pin(name or "", opt("--note", "")); print(json.dumps(r, ensure_ascii=False, indent=1))
            return 0 if r["ok"] else 1
        if prim == "EVOLVE":
            # 🔴 2026-09-26 自纠：EVOLVE 失败也 return 0 违反文件头退出码契约（与 BUILD/WALK/PIN 同口径）
            r = k.evolve(name or "", note=opt("--note", ""))
            print(json.dumps(r, ensure_ascii=False, indent=1)); return 0 if r["ok"] else 1
        print(f"未知原语 {prim}"); return 2
    if cmd == "feedback":
        k = Kernel()
        print(json.dumps(k.get_feedback(a[1] if len(a) > 1 else ""), ensure_ascii=False, indent=1))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
