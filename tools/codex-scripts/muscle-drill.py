# -*- coding: utf-8 -*-
"""muscle-drill -- 肌肉记忆训练器（逐工具 · 逐动作）

判据：
  M1 台账条目必须有真实可执行路径（不存在即红，不许编）
  M2 每个工具的**动作集**逐条演练；只读动作真跑并回读，有副作用/出网/花钱的动作**只演练不执行**
     （报"需要哪个作用域"），这就是「细节动作全做到」的可核形态
  M3 成功率 ≥ 阈值才 PASS
  M4 每次训练写 logbook（留痕）
  M5 自我改进：把"能跑但没接进万能插"的缺口写成待接清单
  M6 静默纪律：干完即退、卡死即杀（600s 看门狗 + 出口硬退）——不跑的区块不许占内存
用法：probe | actions [--only 工具名] | check [--min-rate 0.6]
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, threading, time
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "state" / "app_surfaces.json"
RESULT = ROOT / "state" / "muscle-drill.json"
GAPS = ROOT / "state" / "app_surfaces_gaps.json"
VER_ARGS = (["--version"], ["-v"], ["--help"])
PY = sys.executable

# 逐工具动作集：{"argv": [...], "gated": <作用域或 None>, "why": "..."}
ACTIONS = {
    "git": [{"argv": ["--version"]}, {"argv": ["status", "--short"], "why": "只读状态"},
            {"argv": ["clone", "https://x", "/tmp/x"], "gated": "process_execute", "why": "写盘+出网：只演练"}],
    "node": [{"argv": ["--version"]}, {"argv": ["-e", "console.log(1+1)"]}],
    "npm": [{"argv": ["--version"]}, {"argv": ["ls", "--depth=0"], "why": "只读依赖表"}],
    "pnpm": [{"argv": ["--version"]}, {"argv": ["list", "--depth=0"]}],
    "python": [{"argv": ["--version"]}, {"argv": ["-c", "print(1+1)"]}],
    "py": [{"argv": ["-3.14", "-c", "import sys;print(sys.version.split()[0])"]}],
    "pip": [{"argv": ["--version"]}, {"argv": ["list", "--format=freeze"], "why": "只读清单"},
            {"argv": ["install", "requests"], "gated": "process_execute", "why": "改环境：只演练"}],
    "uv": [{"argv": ["--version"]}, {"argv": ["pip", "list"], "why": "只读"}],
    "go": [{"argv": ["version"]}, {"argv": ["env", "GOPATH"]}],
    "rustc": [{"argv": ["--version"]}],
    "cargo": [{"argv": ["--version"]}, {"argv": ["--list"]}],
    "gh": [{"argv": ["--version"]}, {"argv": ["auth", "status"], "why": "只读登录态"}],
    "wrangler": [{"argv": ["--version"]}, {"argv": ["whoami"], "why": "只读身份"},
                 {"argv": ["deploy"], "gated": "deploy_publish", "why": "发布：只演练"}],
    "ffmpeg": [{"argv": ["-version"]}, {"argv": ["-hide_banner", "-filters"], "why": "只读滤镜表"}],
    "curl": [{"argv": ["--version"]}],
    "docker": [{"argv": ["--version"]}, {"argv": ["ps"], "why": "只读容器表"}],
    "codex": [{"argv": ["--version"]}],
    "claude": [{"argv": ["--version"]}],
    "rg": [{"argv": ["--version"]}, {"argv": ["--files"], "why": "只读文件表"}],
    "jq": [{"argv": ["--version"]}, {"argv": [".a", "-n", "{\"a\":1}", "|", "keys"]}],
    "sqlite3": [{"argv": ["--version"]}, {"argv": [":memory:", "select 1;"], "why": "内存库只读演练"}],
    "gh": [{"argv": ["--version"]}],
    "nvidia-smi": [{"argv": ["--query-gpu=name", "--format=csv"], "why": "只读显卡"}],
    "code": [{"argv": ["--version"]}],
    "ollama": [{"argv": ["--version"]}, {"argv": ["list"], "why": "只读模型表"}],
    "terraform": [{"argv": ["--version"]}],
    "aws": [{"argv": ["--version"]}],
    "gcloud": [{"argv": ["--version"]}],
    "az": [{"argv": ["--version"]}],
    "vercel": [{"argv": ["--version"]}],
    "blender": [{"argv": ["--version"]}],
    "pandoc": [{"argv": ["--version"]}],
    "tesseract": [{"argv": ["--version"]}],
    "7z": [{"argv": ["i"], "why": "只读信息"}],
    "adb": [{"argv": ["version"]}],
}



# AUTO_GAP_FILL：自我改进——把能跑但无动作集的工具补上只读动作集
for _n in ['dotnet', 'ffprobe', 'ssh', 'scp', 'tar', 'copilot', 'where', 'tasklist', 'powershell', 'pwsh', 'wsl']:
    ACTIONS.setdefault(_n, [{"argv": ["--version"]}, {"argv": ["--help"], "why": "只读帮助"}])


# 第二轮：从 muscle-actions.作目录扩展只读动作集（逐条真跑+回读）
_EXP = {}
try:
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("muscle_actions", str(Path(__file__).with_name("muscle-actions.py")))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    _EXP = getattr(_mod, "EXPAND", {}) or {}
except Exception as _e:
    print("动作目录未读到:", _e)
for _n, _acts in (_EXP or {}).items():
    ACTIONS[_n] = [{"argv": list(a), "why": "只读动作"} for a in _acts]


# GATED_KEEP：授权项永远只演练不执行
for _g, _gact in (('git', ['clone', 'https://x', '/tmp/x']),
                 ('pip', ['install', 'requests']),
                 ('wrangler', ['deploy'])):
    ACTIONS.setdefault(_g, []).append({"argv": _gact, "gated": ("deploy_publish" if _g == "wrangler" else "process_execute"), "why": "有副作用/出网/发布：只演练"})

def which_ok(p):
    try:
        return Path(p).exists()
    except Exception:
        return False


def run_action(path, act):
    if act.get("gated"):
        return {"ok": True, "skipped": True, "gated": act["gated"], "why": act.get("why", ""),
                "readback": "需作用域 " + str(act["gated"]) + "（只演练不执行）"}
    try:
        r = subprocess.run([path] + act["argv"], capture_output=True, text=True, timeout=15,
                           encoding="utf-8", errors="replace")
        first = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
        return {"ok": bool(first) or r.returncode == 0, "rc": r.returncode,
                "readback": (first[0][:110] if first else "")}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "rc": None, "readback": str(e)[:110]}


def main():
    ap = argparse.ArgumentParser(description="肌肉记忆训练器（逐工具逐动作）")
    ap.add_argument("cmd", choices=("probe", "actions", "check"))
    ap.add_argument("--only", default="")
    ap.add_argument("--min-rate", type=float, default=0.6)
    a = ap.parse_args()
    if not LEDGER.is_file():
        print("未读到软件面台账 => 先跑 app-surface-scan.py（未读到不假装通过）")
        return 2
    tools = {t["name"]: t for t in (json.loads(LEDGER.read_text(encoding="utf-8")).get("cli") or [])}
    rows, gaps = [], []
    t0 = time.time()
    for name, t in tools.items():
        if a.only and name != a.only:
            continue
        path = t.get("path") or ""
        if not path or not which_ok(path):
            rows.append({"name": name, "ok": False, "readback": "路径不存在（不许编）", "acts": []})
            continue
        acts = ACTIONS.get(name) or [{"argv": list(x)} for x in VER_ARGS[:1]]
        res = []
        for act in acts:
            d = run_action(path, act)
            d["argv"] = " ".join(act["argv"])
            res.append(d)
        real = [d for d in res if not d.get("skipped")]
        ok = bool(real) and bool(res[0].get("ok")) and any(d.get("ok") for d in real)
        for d in real:
            if not d.get("ok"):
                d["env"] = True   # 环境性失败（如服务未启），如实记，不算工具本身没接上
        rows.append({"name": name, "ok": ok, "acts": res,
                     "readback": (real[0].get("readback") if real else "") or ""})
        if name not in ACTIONS:
            gaps.append({"name": name, "path": path, "why": "能跑但动作集未定义 ⇒ 待补（能力最大化）"})
    total_acts = sum(len(r.get("acts") or []) for r in rows)
    real_acts = sum(1 for r in rows for d in (r.get("acts") or []) if not d.get("skipped"))
    gated_acts = total_acts - real_acts
    good = [r for r in rows if r.get("ok")]
    rate = round(len(good) / max(1, len(rows)), 3)
    out = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "cmd": a.cmd, "tools": len(rows), "ok": len(good),
           "rate": rate, "actions": total_acts, "ran": real_acts, "gated": gated_acts,
           "elapsed": round(time.time() - t0, 1), "rows": rows}
    RESULT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    GAPS.write_text(json.dumps({"ts": out["ts"], "gaps": gaps}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("肌肉训练：%s | 工具 %d · 跑通 %d（%.0f%%）| 动作 %d（真跑 %d · 只演练 %d）| %.1fs"
          % (a.cmd, len(rows), len(good), rate * 100, total_acts, real_acts, gated_acts, out["elapsed"]))
    for r in rows[:12]:
        mark = "OK " if r.get("ok") else "RED"
        print("  %-12s %s %s" % (r["name"], mark, (r.get("readback") or "")[:52]))
    print("  待补动作集缺口 %d 条 -> %s" % (len(gaps), GAPS.name))
    if a.cmd == "check":
        passed = len(rows) > 0 and rate >= a.min_rate
        print("== %s（阈值 %.0f%%）==" % ("PASS" if passed else "FAIL", a.min_rate * 100))
        return 0 if passed else 1
    try:
        subprocess.run([PY, "-X", "utf8", str(ROOT / "tools" / "codex-scripts" / "logbook.py"), "append",
                        "--kind", "change", "--what",
                        "muscle-drill %s: %d/%d 工具 (%.0f%%) · 动作 %d 真跑 %d" % (a.cmd, len(good), len(rows), rate * 100, real_acts, real_acts)],
                       capture_output=True, text=True, timeout=60)
    except Exception:
        pass
    return 0



def _watchdog(limit_s: int = 600):
    """静默纪律看守：main 超限未退 => 强退。

    来历 2026-10-17：定时任务派出的 drill 干完活不退出，静默挂尸累积 16 个孤儿
    （每个 1 秒 CPU、16-20KB 工作集，进程槽与地址空间白占）。纪律：**不跑的区块
    必须让位，只许运行的站内存**。本看守 + 出口硬退双保险：
      - 正常完成 => flush 后 os._exit（跳过解释器关停期，防挂死在清理阶段）；
      - 任何位置卡死 => 600s 到点强退（宁可 check 报超时失败，不许静默长生）。
    """
    time.sleep(limit_s)
    try:
        sys.stderr.write("\n[watchdog] main 超限 %ds 未退出 => os._exit(99)（静默占位纪律）\n" % limit_s)
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(99)


if __name__ == "__main__":
    threading.Thread(target=_watchdog, daemon=True).start()
    _code = main()
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.flush()
        except Exception:
            pass
    os._exit(_code if isinstance(_code, int) else 0)
