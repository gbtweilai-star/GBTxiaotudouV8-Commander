# gbt-capability: coverage_matrix
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""全方位覆盖矩阵（主人令 2026-09-27：「把扫描和视觉的钩子全方位无死角覆盖，
确保没有任何死角和盲区才叫扫描，要不然扫来扫去都是故障还扫毛线」）。

**口径（这条最重要）**：**没被扫到的面，必须显式列出来并给出理由。**
隐式跳过 = 盲区。本矩阵把仓里**全部顶层树**逐个过一遍，每棵树只有两种归宿：

  · `扫`  —— 真跑一轮穿透式交叉扫描（钩子 → 交叉验证 ≥2 路 → 遗漏补扫 → 留痕）；
  · `排除` —— 写进 `EXCLUDED` 表，**附理由**；理由缺失即盲区，矩阵判红。

**五个面**（每棵树都过前四个面，第五个面单独跑一遍）：

  | 面 | 内容 | 判据 |
  |---|---|---|
  | A 文件树 | 逐棵树的交叉扫描 | 覆盖率必须 1.0（有未钩住的 = 红） |
  | B 能力位 | 185 位 × 3 路（注册表 / 图鉴 / 分派） | 三位一致才算钩住 |
  | C 绑定账 | 资产 ↔ 触手 | 断连（资产缺失 / 触手不在册）必须为 0 |
  | D 安全面 | 危险模式 → 分诊 | 只把「需人核」计入告警（另两类是预期命中） |
  | E **视觉面** | 视觉能力位 3 路 + 两条**防泄漏闸** | 见下 |

**为什么单独有 E 面**：视觉是这个家里最敏感的面 —— 那些帧是**主人的整块屏幕**。
所以视觉的钩子不止"通不通"，还有**不许出仓**：
  ① `holo_pet_w3/eye/frames/` 的 git 追踪数必须是 **0**（进过历史就删不干净）；
  ② `.gitignore` 里那道锁必须**真在**（锁没了，下一次 `git add -A` 就把屏幕写进索引）；
  ③ 视觉相关能力位（`vision` 域 + 名字含 screen/eye/visual/image 的）必须注册 ∧ 分派。

命令：
  python tools/coverage_matrix.py sweep            # 全量：全部顶层树 × 五面（写读数 + 留痕）
  python tools/coverage_matrix.py sweep --quick    # 只跑轻树（跳过大树，用于快速复查）
  python tools/coverage_matrix.py vision           # 只跑视觉面 E
  python tools/coverage_matrix.py matrix           # 打印上次矩阵读数
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
MATRIX = ROOT / "state" / "coverage_matrix.json"
ENGINE = ROOT / "tools" / "penetrating_cross_scan.py"

# ── 排除表（**每条必须有理由**；没有理由的排除 = 盲区）──────────────────
# 口径：排除的是「不是我们的源码」与「可重建/暂存」两类，**不是**"扫不动就不扫"。
EXCLUDED = {
    ".git": "版本库本体（不是被扫描对象，是被审计的账）",
    "__pycache__": "字节码缓存，可重建",
    ".trash": "暂存区（本仓 trash>rm 的落点），真身已判定为重复/废弃",
    ".backups": "备份区（skills-hub 等覆盖前留档），按定义与源重复",
    ".scratch": "作业临时区（历次作业临时脚本/中间产物），可由作业重跑",
    ".mimosa": "安全扫描插件作业目录（106,602 件 / 1.3GB），非本框架源码",
    "vendor": "第三方内嵌运行时（302MB，requirements 可重建）",
    "dist": "构建产物（可重建）",
    "my-project": "技能试跑脚手架（zenstack+VSCode 模板，11,450 件含 node_modules）",
    "审美相关skill": "第三方设计技能包（自带 LICENSE/NOTICE，按 /_upstream/ 政策不入史）",
    "archive": "历史归档（按 LAYOUT 只增不删，内容已封存）",
    ".fleet": "触手舰队工作区：每根一份 git worktree「副本」（与源同码）⇒ 扫它是重复劳动；"
              "舰队自身另有台账 state/fleet.jsonl + 看板 status + 探针逐根自证隔离",
}
# 大树：--quick 时跳过（正常 sweep 要扫；它们是源码/文档，不是缓存）
HEAVY = {"_upstream", "holo_pet", "output", "render"}

# ── E 面：视觉（最敏感的面）──────────────────────────────────────────
EYE_FRAMES = ROOT / "holo_pet_w3" / "eye" / "frames"
GITIGNORE_RULE = "holo_pet_w3/eye/frames/"
VISUAL_MEMORY = ROOT / "gbt_allinone" / "store" / "visual_memory"
VISION_HINTS = ("vision", "screen", "eye", "visual", "image", "camera")


def _engine():
    spec = importlib.util.spec_from_file_location("pcs", ENGINE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tracked_count(path: str) -> int:
    """git 追踪数（防泄漏判据的核心读数：为 0 才算没出仓）。"""
    out = subprocess.run(["git", "ls-files", path], cwd=ROOT,
                         capture_output=True, text=True).stdout
    return len([x for x in out.splitlines() if x.strip()])


def _cross_scan_trio() -> dict:
    """**F 面：交叉扫描三件套的常设调用者**（2026-09-27 加）。

    来历（外部评估读数，WorkBuddy 探针工作区 `caps_called_audit`）：**185 位里 175 位有调用者、
    3 位是孤儿** —— 孤儿正是本仓自建的 `penetrating_cross_scan` / `hook_enforcer` /
    `omission_detector`：**它们能过唯一门调到，但没有任何代码自动调它们**。
    ⇒ 判据说"接线 185/185"，而调用者审计说"175 有调用者"，**两句话都对**（量的是两件事）——
    但"没人自动调"是真缺口：再好的尺子不量东西就等于没有。

    所以本面在每次 sweep 时，**过唯一门**（`run_task`）各调一次（只读 op），
    把三件套从"孤儿"变成"有常设调用者"。三件套里任何一件报红，本面即红。
    """
    out = {}
    try:
        sys.path.insert(0, str(ROOT))
        import gbt_allinone as g
    except Exception as e:                                     # noqa: BLE001
        return {"ok": False, "why": f"框架导入失败：{type(e).__name__}: {e}", "caps": {}}
    for kind in ("penetrating_cross_scan", "hook_enforcer", "omission_detector"):
        try:
            r = g.run_task(kind, {"op": "report", "tail": 3})
            ok = bool(isinstance(r, dict) and r.get("ok", True))
            out[kind] = {"ok": ok, "status": str(r.get("status") or "")[:40]}
        except Exception as e:                                 # noqa: BLE001
            out[kind] = {"ok": False, "why": f"{type(e).__name__}: {str(e)[:120]}"}
    return {"ok": all(v.get("ok") for v in out.values()), "caps": out,
            "_口径": "过唯一门 run_task 只读调用；任一红即本面红（孤儿有能力位≠有人用它）"}


def vision_surface() -> dict:
    """E 面：视觉能力位 3 路 + 两条防泄漏闸（全部机检，无人工判读）。"""
    sys.path.insert(0, str(ROOT))
    findings, caps = [], {}
    try:
        from gbt_allinone.caps_registry import BENIGN_CAPS
        vis = sorted(k for k, v in BENIGN_CAPS.items()
                     if str(v.get("domain")) == "vision"
                     or any(h in k for h in VISION_HINTS))
        api_src = (ROOT / "gbt_allinone" / "api.py").read_text(encoding="utf-8")
        import re as _re
        for k in vis:
            dispatched = bool(_re.search(r'kind\s*==\s*"%s"' % _re.escape(k), api_src)
                              or _re.search(r'kind\s+in\s*\([^)]*"%s"' % _re.escape(k), api_src))
            caps[k] = {"in_registry": True, "dispatched": dispatched,
                       "domain": BENIGN_CAPS[k].get("domain")}
            if not dispatched:
                findings.append({"what": f"视觉能力位 {k} 未在 api.py 分派", "severity": "高"})
        caps["_count"] = len(vis)
    except Exception as e:                                     # noqa: BLE001
        findings.append({"what": f"读能力注册表失败：{e}", "severity": "高"})

    # 闸①：屏幕帧不许进版本库
    tracked_frames = _tracked_count("holo_pet_w3/eye/frames")
    frames_exist = EYE_FRAMES.is_dir()
    if tracked_frames:
        findings.append({"what": f"屏幕帧有 {tracked_frames} 个文件被 git 追踪（**必须为 0**）",
                         "severity": "高"})
    # 闸②：那道锁必须真在 .gitignore 里
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8", errors="replace")
    lock_present = GITIGNORE_RULE in gi
    if not lock_present:
        findings.append({"what": f".gitignore 里缺少屏幕帧锁：{GITIGNORE_RULE}", "severity": "高"})
    # 闸③：视觉记忆（store 面）不许进版本库
    tracked_vm = _tracked_count("gbt_allinone/store/visual_memory")
    if tracked_vm:
        findings.append({"what": f"视觉记忆有 {tracked_vm} 个文件被追踪（store 应整体不入库）",
                         "severity": "高"})
    return {"surface": "E 视觉", "ok": not findings, "caps": caps,
            "eye_frames": {"exist": frames_exist, "tracked": tracked_frames,
                           "dir": str(EYE_FRAMES)},
            "gitignore_lock": lock_present, "visual_memory_tracked": tracked_vm,
            "findings": findings,
            "_口径": "①帧追踪数=0 ②锁在 .gitignore ③能力位已分派 —— 三条全 True 才算视觉面无死角"}


def classify_trees(quick: bool = False) -> tuple[list, list]:
    """全部顶层树 → (要扫的, 排除的)。**排除必须带理由**，缺理由即红。"""
    scan, excl = [], []
    for d in sorted(ROOT.iterdir()):
        if not d.is_dir():
            continue
        name = d.name
        if name in EXCLUDED:
            why = EXCLUDED[name]
            excl.append({"tree": name, "reason": why,
                         "ok": bool(why and len(why) > 6)})
            continue
        if quick and name in HEAVY:
            excl.append({"tree": name, "reason": "quick 模式跳过（heavy，正常 sweep 会扫）",
                         "ok": True, "deferred": True})
            continue
        scan.append(name)
    return scan, excl


def sweep(quick: bool = False, verbose: bool = True) -> dict:
    eng = _engine()
    t0 = time.time()
    scan, excl = classify_trees(quick)
    trees, blind = [], []
    for t in scan:
        try:
            r = eng.run_pipeline(f"tree:{t}")
            sec = r.get("security", {}) or {}
            trees.append({"tree": t, "units": r["units"], "coverage": r["coverage"],
                          "missing": len(r.get("missing") or []),
                          "agree": r.get("agree"), "arbitrated": r.get("arbitrated"),
                          "sec_flagged": sec.get("flagged", 0),
                          "sec_needs_human": sec.get("needs_human", 0)})
            if r["coverage"] < 1.0:
                blind.append({"tree": t, "missing": (r.get("missing") or [])[:10]})
            if verbose:
                print(f"  ✓ {t:<22} 单元 {r['units']:>5} · 覆盖 {r['coverage']} · "
                      f"需人核 {sec.get('needs_human', 0)}")
        except Exception as e:                                  # noqa: BLE001
            blind.append({"tree": t, "error": str(e)[:200]})
            if verbose:
                print(f"  🔴 {t:<22} 扫不动：{str(e)[:120]}")
    if verbose:
        print("  ── B 能力位 / C 绑定账 ──")
    surfaces = {}
    for tgt in ("caps", "bindings", "registry"):
        try:
            r = eng.run_pipeline(tgt)
            surfaces[tgt] = {"ok": r["ok"], "units": r["units"],
                             "coverage": r["coverage"], "missing": len(r.get("missing") or [])}
            if verbose:
                print(f"  {'✓' if r['ok'] else '🔴'} {tgt:<22} 单元 {r['units']:>5} · 覆盖 {r['coverage']}")
        except Exception as e:                                  # noqa: BLE001
            surfaces[tgt] = {"ok": False, "error": str(e)[:200]}
    vis = vision_surface()
    if verbose:
        print(f"  {'✓' if vis['ok'] else '🔴'} E 视觉面               能力位 {vis['caps'].get('_count')} · "
              f"帧追踪 {vis['eye_frames']['tracked']} · 锁 {'在' if vis['gitignore_lock'] else '缺'}")
        for f in vis["findings"]:
            print(f"     · [{f['severity']}] {f['what']}")
    trio = _cross_scan_trio()
    if verbose:
        bad = [k for k, v in trio["caps"].items() if not v.get("ok")]
        print(f"  {'✓' if trio['ok'] else '🔴'} F 三件套调用者           "
              f"{len(trio['caps'])} 位过门调用" + (f" · 红：{bad}" if bad else " · 全绿"))

    no_reason = [e for e in excl if not e["ok"]]
    all_trees = len(scan) + len(excl)
    units_total = sum(t["units"] for t in trees)
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "quick": quick,
           "耗时s": round(time.time() - t0, 1),
           "顶层树": all_trees, "已扫": len(scan), "排除": len(excl),
           "扫的树": trees, "排除表": excl,
           "盲区": blind, "无理由排除": no_reason,
           "面B_C": surfaces, "面E视觉": vis, "面F三件套": trio,
           "全绿": (not blind and not no_reason and vis["ok"] and trio["ok"]
                    and all(s.get("ok") for s in surfaces.values())),
           "_口径": ("没被扫到的面必须显式列出并给理由；隐式跳过=盲区。"
                     "文件面覆盖必须 1.0；B/C 面断连必须 0；E 面三闸必须全 True。"),
           "单元总数": units_total}
    MATRIX.parent.mkdir(parents=True, exist_ok=True)
    MATRIX.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="全方位覆盖矩阵（无死角）")
    ap.add_argument("cmd", choices=["sweep", "vision", "matrix"])
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "vision":
        r = vision_surface()
        print(json.dumps(r, ensure_ascii=False, indent=1) if a.json
              else f"视觉面：{'全绿' if r['ok'] else '有红'}\n" +
                   "\n".join(f"  · [{f['severity']}] {f['what']}" for f in r["findings"]))
        return 0 if r["ok"] else 1
    if a.cmd == "matrix":
        if not MATRIX.is_file():
            print("还没有矩阵读数 ⇒ 先跑：python tools/coverage_matrix.py sweep")
            return 2
        d = json.loads(MATRIX.read_text(encoding="utf-8"))
        print(f"读数时间 {d['at']} · 耗时 {d['耗时s']}s · 顶层树 {d['顶层树']} "
              f"（已扫 {d['已扫']} / 排除 {d['排除']}）· 单元 {d['单元总数']} · "
              f"{'全绿' if d['全绿'] else '有红'}")
        for b in d["盲区"]:
            print(f"  🔴 盲区 {b}")
        for t in d["扫的树"]:
            if t["coverage"] < 1.0 or t["sec_needs_human"]:
                print(f"  ⚠️ {t['tree']} 覆盖 {t['coverage']} · 需人核 {t['sec_needs_human']}")
        return 0 if d["全绿"] else 1
    out = sweep(quick=a.quick, verbose=not a.json)
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print(f"\n═══ 矩阵 ═══ 顶层树 {out['顶层树']}（已扫 {out['已扫']} · 排除 {out['排除']}）"
              f" · 单元 {out['单元总数']} · 耗时 {out['耗时s']}s ⇒ "
              f"{'✅ 无死角' if out['全绿'] else '🔴 有死角'}")
        if out["盲区"]:
            print(f"  盲区 {len(out['盲区'])} 处：{out['盲区'][:3]}")
        if out["无理由排除"]:
            print(f"  🔴 无理由排除 {len(out['无理由排除'])} 处（=盲区）")
    return 0 if out["全绿"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
