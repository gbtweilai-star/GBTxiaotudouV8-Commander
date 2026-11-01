# gbt-capability: two-way-sync
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""two-way-sync — 交付树 ↔ live 工作仓 双向同步（计划/校验器；写盘由 tools/two-way-sync.ps1 执行）。

为什么拆两层：
  · 本仓在 Windows 上跑 Python 时写不了 `Desktop\\GBT小土豆V8`（权限），
    所以**计划/校验/注册表插入/刷新链**用 Python（能写 live），**文件复制**用 PowerShell（能写 Desktop）。
用法（推荐直接跑 PowerShell 执行器）：
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\\two-way-sync.ps1 status
  powershell ... -File tools\\two-way-sync.ps1 pull -Apply
  powershell ... -File tools\\two-way-sync.ps1 push -Apply -Refresh
  powershell ... -File tools\\two-way-sync.ps1 verify
本文件也可单独跑（只读）：
  py -3.14 -X utf8 tools/codex-scripts/two-way-sync.py status --json
  py ... plan-pull --json        # 只列要拉的文件，不写盘
  py ... plan-push --json
  py ... apply-push-caps         # 只改 live 的 registry/api（幂等）
  py ... refresh --live <live>
  py ... verify
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_DELIVERY = Path(os.environ.get("GBT_DELIVERY", str(Path.home() / "Desktop" / "GBT小土豆V8")))

EXCLUDE_DIRS = {
    "state", "store", "vendor", "dist", "logs", ".git", "__pycache__",
    "node_modules", "outputs", "vaults",
    "holo_pet_w3/_archive-20261021", "tools/_retired", "holo_pet_w3/wgpu/_retired",
    "holo_pet/assets/digital-human/raw", "holo_pet_w3/eye/frames",
    "gbt_allinone/archived_logs", ".sync-backup", "sync-backup",
}
EXCLUDE_FILES = {
    "arms/omni_arm.py",
    "holo_pet/assets/digital-human/standard/tex/source-copy.png",
    "holo_pet_w3/kaleido/v2.html", "holo_pet_w3/kaleido/v3c.html",
    "holo_pet_w3/kaleido/v9c.html", "holo_pet_w3/kaleido/v12.html",
    "tools/codex-scripts/ninfer_verify.ps1",
}
# 交付档案：只属于交付树，绝不推 live
DELIVERY_ONLY_FILES = {"MANIFEST.json", "整理说明.md"}
DELIVERY_ONLY_PREFIX = ("整理报告/",)
# 拉取时不让 live 覆盖的交付成果（push 时仍会推给 live）
KEEP_PULL = {
    "gbt_allinone/tools/edit_core.py",
    "tools/train/gen_corpus_v31.py",
    "tools/codex-scripts/cloud-status.py",
    "tools/codex-scripts/capability-bindings.py",
    "arms/README.md",
    "deploy/cloud-10/mesh.json",
    "state/repo-layout.json", "state/page-caps.json",
    "gbt_allinone/tentacle/hand_retarget.py", "gbt_allinone/tentacle/hand_bridge.py",
    "tests/test_hand_retarget.py", "tests/test_hand_bridge.py",
    "gbt_allinone/tentacle/sync_guard.py", "tests/test_sync_guard.py", "docs/75-sync-guard.md",
    "tools/codex-scripts/two-way-sync.py", "tools/two-way-sync.ps1",
    "tests/test_two_way_sync.py", "docs/74-two-way-sync.md",
}
PAGE_PREFIX = "holo_pet_w3/brain/caps/"
PAGE_INDEX = "holo_pet_w3/index.html"


def sha(p: Path) -> str:
    d = p.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(d) + d).hexdigest()


def rel_skip(rel: str) -> bool:
    if rel in EXCLUDE_FILES:
        return True
    parts = rel.split("/")
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    for d in EXCLUDE_DIRS:
        if "/" in d and (rel == d or rel.startswith(d + "/")):
            return True
    return False


def walk(root: Path) -> dict[str, Path]:
    out = {}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if rel_skip(rel):
            continue
        out[rel] = p
    return out


def is_delivery_only(rel: str) -> bool:
    return rel in DELIVERY_ONLY_FILES or rel.startswith(DELIVERY_ONLY_PREFIX)


def plan_pull(live: Path, deliv: Path) -> list[str]:
    copy = []
    for rel, p in walk(live).items():
        if is_delivery_only(rel) or rel in KEEP_PULL:
            continue
        if rel.startswith(PAGE_PREFIX) or rel == PAGE_INDEX:
            if (deliv / rel).is_file():       # 交付树已修过 boot 深度 → 保留交付版
                continue
        q = deliv / rel
        if not q.is_file() or sha(q) != sha(p):
            copy.append(rel)
    return sorted(copy)


def plan_push(live: Path, deliv: Path) -> list[str]:
    copy = []
    for rel, p in walk(deliv).items():
        if is_delivery_only(rel):
            continue
        q = live / rel
        if not q.is_file() or sha(q) != sha(p):
            copy.append(rel)
    return sorted(copy)


def caps_count(root: Path) -> int:
    try:
        return int(json.loads((root / "data/capabilities.json").read_text(encoding="utf-8")).get("count") or 0)
    except Exception:  # noqa: BLE001
        return -1


def newest_source_age(root: Path) -> float:
    newest = 0.0
    for rel, p in walk(root).items():
        newest = max(newest, p.stat().st_mtime)
    return (__import__("time").time() - newest) if newest else -1.0


def status(live: Path, deliv: Path) -> dict:
    L, D = walk(live), walk(deliv)
    only_l = sorted(set(L) - set(D))
    only_d = [x for x in sorted(set(D) - set(L)) if not is_delivery_only(x)]
    differ = [r for r in sorted(set(L) & set(D)) if sha(L[r]) != sha(D[r])]
    return {
        "live": str(live), "delivery": str(deliv),
        "live_caps": caps_count(live), "delivery_caps": caps_count(deliv),
        "live_files": len(L), "delivery_files": len(D),
        "only_live": only_l, "only_delivery": only_d, "differ": differ,
        "quiet_age_s": round(newest_source_age(live), 1),
        "verdict": "ALIGNED" if not only_l and not only_d and not differ else "DRIFT",
    }


REG_BLOCK = '''    "hand_retarget": {
        "domain": 'device',
        "desc": '身体·手语翻译（2026-11-01 蒸馏自 dexterous-hand 知识胶囊）：把 21 点手部跟踪'
                '（Vision Pro/Quest3/摄像头/IMU 手套先转 21 点）映射成目标灵巧手关节角；内置 '
                'generic_15dof / generic_20dof 模型，也接受自定义 chain/joints/limit 模型；'
                '几何向量法（**非 IK**）：三点屈曲 + 掌平面外展 + 关节限位 + 中性位标定 + 左右手符号，'
                '纯计算零依赖。op=status/models/retarget/where。诚实边界：无接触/触觉建模；'
                '外展/对掌为掌平面近似；高精度需逆运动学求解器（本仓暂无）',
        "handler": 'hand_retarget',
        "safe": True,
    },
    "hand_bridge": {
        "domain": 'device',
        "desc": '身体·手部硬件桥（2026-11-01 蒸馏自 dexterous-hand 知识胶囊）：灵巧手 HAL —— '
                'connect/read_state/move/stop/disconnect；传输 loopback（**仿真真跑**）/ Modbus TCP'
                '（纯 stdlib 组 MBAP+PDU 真帧）/ 串口 / CAN（缺 pyserial·python-can 时如实 '
                'needs_dependency）；关节表+限位+回读统一。**真机写必须给 register_map**'
                '（厂商寄存器表未吸收 ⇒ needs_config，不猜），move 默认 dry_run，真机写需 confirm=true，'
                'stop 同样要 confirm。op=status/transports/profiles/connect/read_state/move/stop/'
                'disconnect/where。诚实边界：loopback 是仿真装置，不驱动真手',
        "handler": 'hand_bridge',
        "safe": False,
    },
'''
API_BLOCK = '''    if kind == "hand_retarget":
        # 手部姿态重定向（2026-11-01 蒸馏自 dexterous-hand 知识胶囊）：21 点 → 关节角。
        # 纯计算、零依赖；不是 IK，接触/触觉未建模（模块头写死边界）。
        from .tentacle import hand_retarget as _hrt
        p = payload or {}
        return _hrt.run(p.get("op", "status"), **{k: v for k, v in p.items() if k != "op"})
    if kind == "hand_bridge":
        # 灵巧手 HAL（2026-11-01）：loopback 仿真真跑 / Modbus TCP 真帧 / 串口·CAN 缺依赖如实报；
        # 真机必须 register_map，写操作默认 dry_run 且要 confirm（模块自己收口，不碰 policy.py）。
        from .tentacle import hand_bridge as _hbr
        p = payload or {}
        return _hbr.run(p.get("op", "status"), **{k: v for k, v in p.items() if k != "op"})
'''


SYNC_REG_BLOCK = '''    "sync_guard": {
        "domain": 'project',
        "desc": '双仓同步巡检（2026-11-01）：交付树 ↔ live 工作仓 的 sha1 对账——'
                'status（只报差异）/ verify（判 ALIGNED：only_live=0 · differ=0 · 两边 cap 计数相等）/ '
                'patrol（verify + 可选写 state/sync_guard.jsonl 台账）/ where。'
                'DRIFT 时出 alerts（sync_drift / caps_mismatch）并给修复命令；**只读，不自动 pull/push**，'
                '修复由 tools/two-way-sync.ps1 执行。交付树路径默认 ~/Desktop/GBT小土豆V8，'
                '可用 delivery 参数或 GBT_DELIVERY 覆盖',
        "handler": 'sync_guard',
        "safe": True,
    },

'''
SYNC_API_BLOCK = '''    if kind == "sync_guard":
        # 双仓同步巡检（2026-11-01）：只读 sha1 对账；DRIFT 出 alerts；不自动 pull/push。
        from .tentacle import sync_guard as _sg
        p = payload or {}
        return _sg.run(p.get("op", "status"), **{k: v for k, v in p.items() if k != "op"})
'''


def apply_push_caps(live: Path) -> dict:
    regp, apip = live / "gbt_allinone/caps_registry.py", live / "gbt_allinone/api.py"
    out = {"hand_registry": False, "hand_api": False, "sync_guard_registry": False,
           "sync_guard_api": False}
    reg = regp.read_text(encoding="utf-8")
    if '"hand_retarget"' not in reg:
        anchor = "    # ── 官方 Codex 能力化（B 档 · 风哥 2026-09-15 批准）──"
        if anchor not in reg:
            raise SystemExit("registry anchor missing")
        reg = reg.replace(anchor, REG_BLOCK + "\n" + anchor, 1)
        out["hand_registry"] = True
    if '"sync_guard"' not in reg:
        anchor = "    # ── 官方 Codex 能力化（B 档 · 风哥 2026-09-15 批准）──"
        if anchor not in reg:
            raise SystemExit("registry anchor missing")
        reg = reg.replace(anchor, SYNC_REG_BLOCK + "\n" + anchor, 1)
        out["sync_guard_registry"] = True
    if out["hand_registry"] or out["sync_guard_registry"]:
        regp.write_text(reg, encoding="utf-8")
    api = apip.read_text(encoding="utf-8")
    if '"hand_retarget"' not in api:
        anchor = '    if kind == "project_drift":'
        if anchor not in api:
            raise SystemExit("api anchor missing")
        api = api.replace(anchor, API_BLOCK + anchor, 1)
        out["hand_api"] = True
    if '"sync_guard"' not in api:
        anchor = '    if kind == "project_drift":'
        if anchor not in api:
            raise SystemExit("api anchor missing")
        api = api.replace(anchor, SYNC_API_BLOCK + anchor, 1)
        out["sync_guard_api"] = True
    if out["hand_api"] or out["sync_guard_api"]:
        apip.write_text(api, encoding="utf-8")
    return out


REFRESH = [
    "tools/codex-scripts/export-capabilities.py",
    "tools/codex-scripts/gen-open-source-caps.py --out .",
    "tools/codex-scripts/capability-bindings.py",
    "tools/codex-scripts/capability-audit.py probe",
    "tools/codex-scripts/capability-audit.py render",
    "tools/codex-scripts/gen-authz-page.py",
]


def refresh(live: Path) -> dict:
    res = {}
    for cmd in REFRESH:
        parts = cmd.split()
        script = live / parts[0]
        if not script.is_file():
            res[cmd] = "missing"
            continue
        r = subprocess.run([sys.executable, "-B", "-X", "utf8", str(script)] + parts[1:],
                           cwd=str(live), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=1200,
                           env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"})
        res[cmd] = r.returncode
    return res


def verify(live: Path, deliv: Path) -> dict:
    st = status(live, deliv)
    reg_live = caps_count(live) == caps_count(deliv) and caps_count(live) > 0
    st["caps_equal"] = reg_live
    st["verdict"] = "ALIGNED" if (not st["only_live"] and not st["differ"]
                                  and not st["only_delivery"] and reg_live) else "DRIFT"
    return st


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="two-way-sync")
    ap.add_argument("op", choices=["status", "plan-pull", "plan-push", "verify",
                                   "apply-push-caps", "refresh"])
    ap.add_argument("--live", default="")
    ap.add_argument("--delivery", default=str(DEFAULT_DELIVERY))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    live = Path(args.live).resolve() if args.live else Path(__file__).resolve().parents[2]
    deliv = Path(args.delivery).resolve()
    if not (live / "gbt_allinone").is_dir():
        print("live 不是 GBT 仓根（缺 gbt_allinone/）：%s" % live, file=sys.stderr)
        return 2
    if not deliv.is_dir():
        print("交付树不存在：%s（用 --delivery 指定）" % deliv, file=sys.stderr)
        return 2

    if args.op in ("status", "verify"):
        st = verify(live, deliv) if args.op == "verify" else status(live, deliv)
        print(json.dumps(st, ensure_ascii=False, indent=1) if args.json else _fmt(st))
        return 0
    if args.op == "plan-pull":
        files = plan_pull(live, deliv)
        print(json.dumps({"op": "pull", "copy": files, "count": len(files)}, ensure_ascii=False) if args.json
              else "拉取计划 %d 个文件" % len(files))
        return 0
    if args.op == "plan-push":
        files = plan_push(live, deliv)
        print(json.dumps({"op": "push", "copy": files, "count": len(files)}, ensure_ascii=False) if args.json
              else "推送计划 %d 个文件" % len(files))
        return 0
    if args.op == "apply-push-caps":
        print(json.dumps(apply_push_caps(live), ensure_ascii=False))
        return 0
    if args.op == "refresh":
        print(json.dumps(refresh(live), ensure_ascii=False))
        return 0
    return 2


def _fmt(st: dict) -> str:
    lines = ["live caps=%s / delivery caps=%s" % (st["live_caps"], st["delivery_caps"]),
             "source files: live=%s delivery=%s" % (st["live_files"], st["delivery_files"]),
             "only_live=%d only_delivery(no archive)=%d differ=%d quiet_age=%.1fs" %
             (len(st["only_live"]), len(st["only_delivery"]), len(st["differ"]), st["quiet_age_s"]),
             "verdict: %s" % st["verdict"]]
    for tag, key in (("+", "only_live"), ("-", "only_delivery"), ("~", "differ")):
        for rel in st[key][:20]:
            lines.append("  %s %s" % (tag, rel))
        if len(st[key]) > 20:
            lines.append("  ... 共 %d" % len(st[key]))
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
