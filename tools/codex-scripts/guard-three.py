# -*- coding: utf-8 -*-
"""三条默认的自动闸 —— 不用人提醒，跑一次就知道有没有漏。

主人令 2026-11-04：「把这三个调用设置成默认使用，别一直要我提醒」。

    ① 万能插 omni_plug      —— 碰外部之前用它，每次动作必须留痕
    ② 多域监控 impact_check —— 改东西之前算影响面，且能读到万能插的留痕
    ③ 原子替换             —— 写别人会读的文件，不许裸 write_text

退出码：0 全过 / 1 有 fail。`warn` 与 `needs_build` 不算失败，但都会列出来。

四态（对齐 AGENTS.md §2.1 的失败三态，外加 pass）：
    pass        判据过
    needs_build 产物还没建（这台机器没跑过初始化）—— 不阻断，如实报缺哪几件
    warn        取不到依赖，没法判（例如缺 omni_discover）
    fail        真坏了：产物在但内容坏 / 逻辑坏 / 闸少了牙

用法：
    py tools/codex-scripts/guard-three.py                    # 开发仓口径
    py tools/codex-scripts/guard-three.py --json
    py tools/codex-scripts/guard-three.py --require-products # 生产树 / CI 口径（要求产物齐备）
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 「别处会读」的关键产物 —— 这些必须原子写
CRITICAL = (
    "state/model-pack/wiring.json",
    "state/codepage_index.json",
    "state/model-pack/tactile-tree.npz",
    "state/model-pack/tactile-tree.names.json",
    "state/model-pack/tactile-tree.meta.json",
    "state/commander/recall-20.json",
    "state/commander/coverage-rows.jsonl",
    "state/weights/ACTIVE.json",
)


def _api():
    from gbt_allinone import api
    return api


def _peel(env):
    r = (env or {}).get("result") or {}
    return r.get("result") if isinstance(r.get("result"), dict) else r


def check_omni() -> dict:
    """① 万能插：能应答 + 留痕写侧没断（status 不许留痕 / energy 必须留痕）

    🔴 2026-11-06 口径修正（血账）：旧版拿 `op=status` 判断「留痕在长个儿」。
    当天 `omni_plug._sync_impact` 已按设计跳过纯读 status（旧台账最后 10 行
    全被 status 空记录占满，真实动作被挤出 recent），于是这道闸必红：
    实测 `128346 → 128346`。闸不许因为「按设计不写」而红。
    新口径双向：status 必须**不**长（噪声门），energy 必须**长**（写侧门）。
    """
    p = os.path.join(ROOT, "state", "omni-impact.jsonl")
    try:
        api = _api()
    except Exception as e:                                        # noqa: BLE001
        return {"item": "万能插", "status": "fail",
                "why": "%s: %s" % (type(e).__name__, str(e)[:120])}

    def _size() -> int:
        return os.path.getsize(p) if os.path.isfile(p) else 0

    def _run(op: str) -> dict:
        try:
            return _peel(api.run_task("omni_plug", {"op": op}))
        except Exception as e:                                    # noqa: BLE001
            return {"ok": False,
                    "error": "%s: %s" % (type(e).__name__, str(e)[:120])}

    b0 = _size()
    st = _run("status")
    b1 = _size()
    if not st.get("ok"):
        return {"item": "万能插", "status": "fail",
                "why": "status 本体 ok=false：%s" % st.get("error")}
    if b1 != b0:
        return {"item": "万能插", "status": "fail",
                "why": "status 也留痕了（%d → %d 字节）—— 噪声会淹掉真实动作" % (b0, b1)}

    en = _run("energy")
    b2 = _size()
    if not en.get("ok"):
        return {"item": "万能插", "status": "fail",
                "why": "energy 本体 ok=false：%s" % en.get("error")}
    if b2 <= b1:
        return {"item": "万能插", "status": "fail",
                "why": "跑了一次 energy，留痕没长（%d → %d 字节）—— 写侧断了" % (b1, b2)}

    n = sum(1 for _ in open(p, encoding="utf-8"))
    return {"item": "万能插", "status": "pass",
            "detail": {"留痕行": n, "字节": b2,
                       "status_delta": b1 - b0, "energy_delta": b2 - b1}}


def check_impact(require_products: bool = False) -> dict:
    """② 多域监控：图连通 + 能读到万能插留痕 + where 自述正确

    🔴 2026-11-04 口径修正（血账）：本闸原先在**开发仓**恒红，红的原因是
    `state/model-pack/wiring.json` 不存在 —— 而 `state/*/` 整目录被 `.gitignore:419`
    忽略，产物本来就只长在生产树。把「没建图」报成「图坏了」违反本仓 AGENTS.md §2.1
    三态口径（缺依赖是 `needs_dependency`，不是 `failed`）。
    红久了就没人看，等于这道闸不存在。所以缺产物一律落 `needs_build`：
    如实报、可读、不阻断。加 `--require-products` 时才要求齐备（生产树/CI 全流程用）。
    """
    try:
        api = _api()
        st = _peel(api.run_task("impact_check", {"op": "status"}))
        rc = _peel(api.run_task("impact_check", {"op": "recent"}))
        wh = _peel(api.run_task("impact_check", {"op": "where"}))
    except Exception as e:                                        # noqa: BLE001
        return {"item": "多域监控", "status": "fail",
                "why": "%s: %s" % (type(e).__name__, str(e)[:120])}
    bad = []
    if not st.get("ok"):
        err = str(st.get("error") or "")
        # 产物缺席 ≠ 接线坏了：这一档是 needs_build，不是 fail
        if ("wiring.json" in err or "不存在" in err) and not require_products:
            return {"item": "多域监控", "status": "needs_build",
                    "why": "图还没建（%s）—— 先跑 tools/codex-scripts/wiring-build.py"
                           % err[:120]}
        bad.append("status ok=false：%s" % st.get("error"))
    comp = st.get("graph_components")
    if comp is not None and comp != 1:
        bad.append("连通分量 %s ≠ 1（图没全通）" % comp)
    if (rc.get("count") or 0) <= 0:
        why = str(rc.get("why") or "")
        if ("wiring.json" in why or "不存在" in why) and not require_products:
            return {"item": "多域监控", "status": "needs_build",
                    "why": "读不到万能插留痕，因为图还没建（%s）" % why[:120]}
        bad.append("recent count=0 —— 读不到万能插留痕（%s）" % why)
    if "wiring-build" not in str(wh.get("builder") or ""):
        bad.append("where.builder 不是 wiring-build：%r" % (wh.get("builder"),))
    if bad:
        return {"item": "多域监控", "status": "fail", "why": "；".join(bad)}
    return {"item": "多域监控", "status": "pass",
            "detail": {"nodes": st.get("nodes"), "components": comp,
                       "recent": rc.get("count"), "builder": wh.get("builder")}}


def check_atomic(require_products: bool = False) -> dict:
    """③ 原子替换：关键产物可读 + 无 .tmp 残留 + 关键模块没裸 write_text

    🔴 2026-11-04 口径修正：缺产物是 `needs_build`（没跑过初始化），
    不是「写坏了」。只有**产物存在但坏**（不是合法 JSON / 有 .tmp 残留 /
    关键模块裸写）才判 fail —— 那才是原子性真的破了。
    """
    issues, missing, detail = [], [], {}
    for rel in CRITICAL:
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            # 产物缺席单独收：它是 needs_build 的依据，不是 fail 的依据
            missing.append(rel)
            continue
        detail[rel] = os.path.getsize(p)

    # 要求齐备时，缺一件才算问题（CI/生产树全流程口径）
    if missing and require_products:
        issues.extend("缺产物 %s" % rel for rel in missing)

    # .tmp 残留 = 原子写中途崩过
    pack = os.path.join(ROOT, "state", "model-pack")
    tmps = [f for f in (os.listdir(pack) if os.path.isdir(pack) else []) if ".tmp" in f]
    if tmps:
        issues.append("有 .tmp 残留（原子写没清干净）：%s" % tmps[:5])

    # 关键产物若 JSON，必须能解析
    for rel in CRITICAL:
        if not rel.endswith(".json"):
            continue
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8") as fh:
                json.load(fh)
        except Exception as e:                                    # noqa: BLE001
            issues.append("%s 不是合法 JSON（写坏了）：%s" % (rel, type(e).__name__))

    # AST：关键模块里有没有对**关键路径**裸 write_text
    targets = ("wiring.json", "codepage_index.json", "tactile-tree", "recall-20")
    suspects = []
    for rel in ("gbt_allinone/tactile_tree.py", "gbt_allinone/codepage.py",
                "tools/codex-scripts/wiring-build.py", "tools/codex-scripts/recall-snapshot.py"):
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p):
            continue
        try:
            tree = ast.parse(open(p, encoding="utf-8", errors="replace").read())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            name = node.func.attr
            if name not in ("write_text", "write_bytes"):
                continue
            src = ast.get_source_segment(open(p, encoding="utf-8", errors="replace").read(), node) or ""
            if ".tmp" in src or "_atomic" in src:
                continue
            if any(t in src for t in targets):
                suspects.append("%s:%d 裸 %s 写关键路径" % (rel, node.lineno, name))
    if suspects:
        issues.append("；".join(suspects[:4]))

    if issues:
        return {"item": "原子替换", "status": "fail", "why": "；".join(issues)}
    if missing:
        return {"item": "原子替换", "status": "needs_build",
                "why": "%d/%d 件产物还没建（未要求齐备，先跑 warmup.py / wiring-build.py）：%s"
                       % (len(missing), len(CRITICAL), "、".join(missing[:4])),
                "missing": missing, "detail": detail}
    return {"item": "原子替换", "status": "pass", "detail": detail}


def check_probe() -> dict:
    """④ 探测超时有界 —— 那 20 秒的来源，回退了要立刻看见。

    2026-11-04：`surface_audit` 曾 22.2s，cProfile 指认 `socket.connect` 14 次吃掉 20.3s，
    全是回环死口在等 1.0s 超时。砍到 0.06s 后 6.3s。
    这里不复跑 `surface_audit`（6 秒太慢），只钉**单次探测**的上限 —— 那个才是根。

    🔴 2026-11-04 合并血账：这一项原先**只长在生产树**，开发仓的 guard-three 是 3 项。
    两边各自演化导致「开发仓改了闸、生产树加了检查」的单向覆盖风险 ——
    按开发仓版本覆盖过去就会**静默丢掉这一项**（闸少一颗牙没人看得见）。
    现已合并回来，两边同一份。
    """
    import socket
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    try:
        import omni_discover as D
    except Exception as e:                                        # noqa: BLE001
        return {"item": "探测超时", "status": "warn",
                "why": "取不到 omni_discover：%s" % str(e)[:80]}
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    finally:
        s.close()
    t0 = time.perf_counter()
    got = D._tcp(port)
    dt = time.perf_counter() - t0
    if got is not None:
        return {"item": "探测超时", "status": "fail",
                "why": "死口 %d 竟然探到了（探测在返假值）" % port}
    if dt > 0.5:
        return {"item": "探测超时", "status": "fail",
                "why": "探死口 %.2fs > 0.5s —— 超时被改回去了（修复前 1.0s/次 ×14 = 20s）"
                       % dt}
    return {"item": "探测超时", "status": "pass",
            "detail": {"死口耗时_ms": round(dt * 1000, 1)}}


def check_env() -> dict:
    r"""⑤ 运行时：跑的是不是仓内 pyembed + 采集三路齐不齐 + **真能不能出一帧**

    🔴 2026-11-06 加这一颗牙的血账（同一个事故的两面）：
      ① 本轮我在 `Desktop\GBT小土豆V8` 里用
         `.cache\codex-runtimes\...\python.exe` 跑了半天 —— 那套没有
         mss / uiautomation / pyautogui，屏幕采集「三路全灭」。我据此断言
         「采集能力丢了」，实际是**解释器换了，能力一直在**。
      ② 仓里的 `pyembed/` 是被我从别处搬回来的 **3.12.10**，而
         `.scratch/fix_pth.py` 当年修的是另一份 **3.13** —— 运行时版本也对不上。
         更糟的是：那次「修 `._pth`」的脚本躺在 `.scratch/`（AGENTS.md 自己标注
         "临时产物（可删）"），换一份运行时它就静默消失，谁也不会发现。

    三态口径（AGENTS.md §2.1）：
      跑错解释器      → **fail**（不是缺件，是用错工具，必须改）
      是 pyembed 但缺腿 → needs_dependency（去装，不是代码坏）
      腿齐却抓不到帧   → needs_dependency（环境不让看，别硬算成代码坏）

    数据源复用不重写：依赖清单读 `tentacle.bridge.self_diagnose()`，
    真出帧读 `brain_exec._vision_dim()` —— 本闸只做归因，不自己再探一遍。
    """
    pyembed = os.path.join(ROOT, "pyembed", "python.exe")
    has_embedded = os.path.isfile(pyembed)
    try:
        in_repo = bool(has_embedded) and \
            os.path.normcase(os.path.abspath(sys.executable)) == \
            os.path.normcase(os.path.abspath(pyembed))
    except Exception:                                             # noqa: BLE001
        in_repo = False

    try:
        from gbt_allinone.tentacle import bridge as TB
        diag = TB.self_diagnose()
    except Exception as e:                                        # noqa: BLE001
        return {"item": "运行时", "status": "warn",
                "why": "取不到 self_diagnose：%s: %s" % (type(e).__name__, str(e)[:100])}

    deps = diag.get("deps") or {}
    legs = {k: bool((v or {}).get("ok")) for k, v in deps.items()}
    # 三路取 **any**（不是 all）：dxcam / mss / pyautogui 任一路能抓帧就够。
    #
    # 口径（2026-11-05 复核，别再来一遍）：`pyembed` 是 embeddable 包，自带的是
    # mss + pyautogui，**dxcam 通常就是缺的** —— 那是正常状态，不是故障。
    # 判据是下面的 has_leg；明细里那个 `dxcam: false` 只说明"这一路没有"，
    # **不等于"屏幕采集全灭"**。血账：2026-11-05 我看到 false 就把它记成
    # 「三路缺一路·未闭合」，查了判定逻辑才发现用的是 any()、一直是绿的 ——
    # 只看数据不看消费方怎么用，是这一轮犯的第四次同类错误。
    has_leg = any(legs.get(m) for m in ("dxcam", "mss", "pyautogui"))

    try:
        from gbt_allinone import brain_exec as BE
        vd = BE._vision_dim()
    except Exception as e:                                        # noqa: BLE001
        vd = {"ok": False, "detail": "%s: %s" % (type(e).__name__, str(e)[:120])}

    detail = {
        "exe": sys.executable,
        "version": sys.version.split()[0],
        "in_repo_pyembed": in_repo,
        "pure_embed_python": pyembed if os.path.isfile(pyembed) else None,
        "deps": legs,
        "frame": vd,
    }

    # 开发仓**本来就不携带运行时**（pyembed 只在产品树里）——
    # 那是缺件（needs_dependency），不是"用错工具"，不能让开发仓恒红。
    # 红久了就没人看，闸就等于不存在（同 check_impact 那条血账）。
    if not has_embedded:
        return {"item": "运行时", "status": "needs_dependency",
                "why": "本仓没有 pyembed\\python.exe（开发仓通常不携带运行时）—— "
                       "要验采集/视觉请用产品树的 .\\pyembed\\python.exe 跑本仓代码",
                "detail": detail}
    if not in_repo:
        return {"item": "运行时", "status": "fail",
                "why": "跑本仓的不是仓内 pyembed（当前 %s）—— 系统别的 Python 没有"
                       "采集依赖，在它下面屏幕等于全灭；用 .\\pyembed\\python.exe 重跑"
                       % sys.executable, "detail": detail}
    if not has_leg:
        return {"item": "运行时", "status": "needs_dependency",
                "why": "采集三路（dxcam/mss/pyautogui）全缺 —— 屏幕抓不到帧",
                "detail": detail}
    if not vd.get("ok"):
        return {"item": "运行时", "status": "needs_dependency",
                "why": "依赖在但抓不到帧：%s" % str(vd.get("detail"))[:120],
                "detail": detail}
    return {"item": "运行时", "status": "pass", "detail": detail}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="三条默认的自动闸")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--require-products", action="store_true",
                    help="要求运行时产物齐备（生产树 / CI 全流程用）。"
                         "不加则缺产物报 needs_build —— 不阻断，但如实列出缺哪几件")
    a = ap.parse_args(argv)

    t0 = time.time()
    checks = [check_omni(),
              check_impact(a.require_products),
              check_atomic(a.require_products),
              check_probe(),
              check_env()]
    fails = [c for c in checks if c["status"] == "fail"]
    needs = [c for c in checks if c["status"] == "needs_build"]
    needs_dep = [c for c in checks if c["status"] == "needs_dependency"]
    out = {
        "ok": not fails,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "elapsed_ms": int((time.time() - t0) * 1000),
        "checks": checks,
        "failed": [c["item"] for c in fails],
        "needs_build": [c["item"] for c in needs],
        "needs_dependency": [c["item"] for c in needs_dep],
        "口径": "三条默认 = 万能插 / 多域监控 / 原子替换（+ 探测超时 + 运行时，共 5 项自检）；"
                "缺一条就算没做完。缺产物是 needs_build、缺依赖是用错/缺件，都不是 fail",
    }

    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print("=" * 66)
        print("三条默认自检")
        print("=" * 66)
        for c in checks:
            mark = {"pass": "✅", "fail": "❌", "warn": "⚠️",
                    "needs_build": "🏗", "needs_dependency": "🧩"}.get(c["status"], "?")
            print(f"\n{mark} {c['item']}")
            if c.get("why"):
                print(f"   → {c['why']}")
            if c.get("detail"):
                print("   " + json.dumps(c["detail"], ensure_ascii=False)[:300])
        print(f"\n{'=' * 66}")
        tail = "全过" if out["ok"] else "未过：" + " / ".join(out["failed"])
        if needs:
            tail += "（%d 项待初始化：%s）" % (len(needs), " / ".join(out["needs_build"]))
        if needs_dep:
            tail += "（%d 项缺依赖：%s）" % (len(needs_dep), " / ".join(out["needs_dependency"]))
        print(f"{tail}  ({out['elapsed_ms']}ms)")
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
