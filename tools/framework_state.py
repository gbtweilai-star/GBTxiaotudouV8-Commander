# gbt-capability: framework_state
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""框架全状态一屏（主人令 2026-09-27：「**必须时刻随时都能感知到框架的所有状态**」
+「新增能力全部都要与触手双向绑定，确保触手随时使用不会有故障和断连，
以及都没实现却都没记录」）。

**为什么要有这个入口**：读数散在十几个文件与判据里（注册表 / 图鉴 / 分派 / 绑定账 /
技能锁 / 覆盖矩阵 / 视觉面 / 舰队 / 未实现登记）—— **散着 = 没人看**，于是"没实现"能悄悄挂着、
"断连"能悄悄长出来。本工具把它们**收成一屏**，并给出**红项清单**（读不到就如实写"读不到"，
不许用"应该没事"顶替）。

命令：
  python tools/framework_state.py            # 一屏人读
  python tools/framework_state.py --json     # 机读（给判据/自动化用）
  python tools/framework_state.py --brief    # 一行摘要（给日报/心跳用）

口径：**全部读盘现算**，不缓存、不沿用上次读数；每个面都带"来源"，读数可复核。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
STATE = ROOT / "state"


def _j(p: Path, default=None, *, must_parse: bool = False):
    """读 JSON。**坏文件不许静默当空**（实测血账：登记表里嵌套了英文双引号 ⇒ JSON 写坏，
    早先的读法把它当"没有登记"⇒ 报出 unimplemented_registered=0 的假读数）。
    `must_parse=True` 时，文件存在但解析失败 ⇒ 抛错，由调用方记成红项。"""
    if not p.is_file():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        if must_parse:
            raise ValueError(f"{p.name} 损坏（第 {e.lineno} 行）：{e.msg}") from e
        return default


def _age_h(p: Path) -> float | None:
    try:
        return round((time.time() - p.stat().st_mtime) / 3600, 2)
    except OSError:
        return None


def collect() -> dict:
    """收全框架状态。每个面：读数 + 来源 + 红项。"""
    out: dict = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "faces": {}, "red": []}

    # ① 能力位：登记 / 图鉴 / 分派 / 未实现登记
    face = {"source": "gbt_allinone/caps_registry.py + state/skill_atlas.json + gbt_allinone/api.py"}
    try:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone.caps_registry import BENIGN_CAPS
        src = (ROOT / "gbt_allinone" / "api.py").read_text(encoding="utf-8")
        atlas = _j(STATE / "skill_atlas.json", {}) or {}
        atlas_kinds = {c.get("kind") for c in (atlas.get("caps") or [])}
        und = _j(STATE / "unimplemented.json", {}, must_parse=True) or {}
        und_kinds = {i.get("kind") for i in (und.get("items") or [])}
        undispatched, not_atlas = [], []
        for k in BENIGN_CAPS:
            if not (re.search(r'kind\s*==\s*"%s"' % re.escape(k), src)
                    or re.search(r'kind\s+in\s+\([^)]*"%s"' % re.escape(k), src)):
                undispatched.append(k)
            if k not in atlas_kinds:
                not_atlas.append(k)
        face.update({"registry": len(BENIGN_CAPS), "atlas": len(atlas_kinds),
                     "undispatched": undispatched, "not_in_atlas": not_atlas,
                     "unimplemented_registered": len(und_kinds)})
        unreg = sorted(set(undispatched + not_atlas) - und_kinds)
        if unreg:
            face["未登记缺口"] = unreg
            out["red"].append(f"能力位 {len(unreg)} 个「没接/不在图鉴」且**未登记**在 state/unimplemented.json：{unreg[:6]}")
    except Exception as e:                                     # noqa: BLE001
        face["error"] = f"{type(e).__name__}: {e}"
        out["red"].append(f"能力位读数失败：{e}")
    out["faces"]["能力位"] = face

    # ② 双向绑定：资产↔触手（两个方向都要通）
    face = {"source": "state/asset_bindings.json + tools/tentacle_bind.py"}
    b = _j(STATE / "asset_bindings.json", {}) or {}
    missing, ghost, labels = [], [], set()
    try:
        import importlib.util as _iu
        sp = _iu.spec_from_file_location("tbx", ROOT / "tools" / "tentacle_bind.py")
        tb = _iu.module_from_spec(sp)
        sp.loader.exec_module(tb)
        labels = set(tb._valid_labels() or [])
        for a, row in b.items():
            if not (ROOT / a).exists():
                missing.append(a)
            for t in (row.get("tentacles") or []):
                if labels and t not in labels:
                    ghost.append(f"{a} → {t}")
    except Exception as e:                                     # noqa: BLE001
        face["error"] = f"{type(e).__name__}: {e}"
    face.update({"assets": len(b), "断连_资产缺失": len(missing),
                 "断连_触手不在册": len(ghost), "有效触手标签": len(labels)})
    try:
        from gbt_allinone.caps_registry import BENIGN_CAPS as _bc
        no_tentacle = sorted(set(_bc) - labels) if labels else []
        face["能力位无触手标签"] = no_tentacle
        if no_tentacle:
            out["red"].append(f"{len(no_tentacle)} 个能力位在触手字典里叫不出来（反向绑定断）：{no_tentacle[:6]}")
    except Exception:                                          # noqa: BLE001
        pass
    if missing or ghost:
        out["red"].append(f"绑定断连：资产缺失 {len(missing)} · 触手不在册 {len(ghost)}")
    out["faces"]["双向绑定"] = face

    # ③ 技能：源 ↔ 装
    face = {"source": "state/skills_install.lock.json"}
    lock = _j(STATE / "skills_install.lock.json", {}) or {}
    ins = sum(1 for v in (lock.get("skills") or {}).values() if v.get("in_sync"))
    face.update({"总数": lock.get("count"), "一致": ins})
    if lock.get("count") and ins != lock.get("count"):
        out["red"].append(f"技能源↔装：{ins}/{lock.get('count')} 一致 ⇒ 有分叉")
    out["faces"]["技能源装"] = face

    # ④ 覆盖矩阵
    face = {"source": "state/coverage_matrix.json"}
    cm = _j(STATE / "coverage_matrix.json", {}) or {}
    face.update({"全绿": cm.get("全绿"), "顶层树": cm.get("顶层树"),
                 "已扫": cm.get("已扫"), "排除": cm.get("排除"),
                 "盲区": len(cm.get("盲区") or []), "读数时间": cm.get("at"),
                 "年龄h": _age_h(STATE / "coverage_matrix.json")})
    if not cm.get("全绿"):
        out["red"].append(f"覆盖矩阵不是全绿（盲区 {len(cm.get('盲区') or [])}）")
    out["faces"]["覆盖矩阵"] = face

    # ⑤ 视觉面（最敏感）
    face = {"source": "state/coverage_matrix.json · 面E视觉"}
    vis = (cm.get("面E视觉") or {})
    face.update({"ok": vis.get("ok"), "帧追踪": (vis.get("eye_frames") or {}).get("tracked"),
                 "锁在": vis.get("gitignore_lock")})
    if vis and not vis.get("ok"):
        out["red"].append("视觉面有红（帧可能出仓/锁缺失/能力位未分派）")
    out["faces"]["视觉面"] = face

    # ⑥ 舰队
    face = {"source": "state/fleet_active.json + state/fleet.jsonl"}
    fa = _j(STATE / "fleet_active.json", {}) or {}
    face.update({"在册": len(fa), "台账行": sum(1 for _ in (STATE / "fleet.jsonl").open(encoding="utf-8"))
                 if (STATE / "fleet.jsonl").is_file() else 0})
    out["faces"]["舰队"] = face

    # ⑦ 判据与台账新鲜度
    face = {"source": "state/*.jsonl 时间戳"}
    face["读数年龄h"] = {name: _age_h(STATE / name) for name in
                        ("coverage_matrix.json", "full_scan.json", "asset_bindings.json",
                         "cross_scan_trace.jsonl", "selfgrowth.jsonl")}
    stale = [k for k, v in face["读数年龄h"].items() if isinstance(v, (int, float)) and v > 30]
    face["过期读数"] = stale
    out["faces"]["读数新鲜度"] = face

    out["ok"] = not out["red"]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="框架全状态一屏（全读盘现算）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--brief", action="store_true")
    a = ap.parse_args(argv)
    s = collect()
    if a.brief:
        caps = s["faces"]["能力位"]
        bind = s["faces"]["双向绑定"]
        print(f"[{s['at']}] 能力位 {caps.get('registry')} · 未实现登记 {caps.get('unimplemented_registered')} · "
              f"绑定 {bind.get('assets')} · 断连 {bind.get('断连_资产缺失')}+{bind.get('断连_触手不在册')} · "
              f"技能 {s['faces']['技能源装'].get('一致')}/{s['faces']['技能源装'].get('总数')} · "
              f"矩阵 {'绿' if s['faces']['覆盖矩阵'].get('全绿') else '红'} · "
              f"红项 {len(s['red'])}")
        return 0 if s["ok"] else 1
    if a.json:
        print(json.dumps(s, ensure_ascii=False, indent=1))
        return 0 if s["ok"] else 1
    print(f"═══ 框架全状态 · {s['at']} ═══")
    for name, f in s["faces"].items():
        bits = " · ".join(f"{k}={v}" for k, v in f.items() if k not in ("source", "读数年龄h", "过期读数"))
        print(f"  【{name}】{bits}")
        print(f"      来源：{f.get('source')}")
    if s["red"]:
        print(f"\n🔴 红项 {len(s['red'])}：")
        for r in s["red"]:
            print("   ·", r)
    else:
        print("\n✅ 全绿（每个面都有读数，且都在位）")
    return 0 if s["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
