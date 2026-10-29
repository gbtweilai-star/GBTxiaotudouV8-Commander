#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""pipeline-preflight · 「无限制创作流水线」**动手前的前置检查**（一条命令）

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要有这一件

主人立项的 ① 是「部署无审查图像触手」。但 `docs/无限制创作流水线.md` §9.0 列了**四个前置条件**，
条款上写着「**必须先满足，否则不做**」。**写在文档里的前置条件，人手一忙就会跳过** ⇒
本件把它变成**一条命令**：四个条件逐条现读，够了才说 READY。

## 口径（不许省）

- **四个条件全绿才 READY**；任何一条没满足 ⇒ **BLOCKED**（并点名是哪条）。
- **不猜**：每条都取**现读读数**（mtime/哈希、解释器与 torch 构建、磁盘上的权重文件名、可用内存）。
- 判据是**纯函数** `verdict(facts)` —— 于是自检能喂**人造事实**做正/负控，不靠真机状态碰运气。
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / "gbt_allinone" / "caps_registry.py"
COMFY = Path(r"C:\Users\ADMIN\ComfyUI")
VNV = COMFY / ".venv" / "Scripts" / "python.exe"

# **阈值不是拍的，是从观测数据推的**（2026-09-25 自纠）：
#    本会话记录的「活跃写盘时刻」（出处：账 §一百三十七–§一百四十五 的现读证据）：
OBSERVED_WRITES = ["05:14:10", "05:20:20", "05:27:41", "05:32:07", "05:34:33",
                   "05:36:41", "05:36:45", "05:37:27", "05:37:42", "05:37:46", "05:54:12"]
#    相邻间隔最大 = **16.4 分钟**（05:37:46 → 05:54:12）。
#    我最初写死 **10 分钟** ⇒ **会把活跃期误判成「他停手了」**（这条自纠就是这么来的）。
#    ⇒ 阈值取「活跃期最大间隔」的 ~1.8 倍 = **30 分钟**，并且**如实标残余风险**：
#      静默判据只能**降低**误判概率，**证明不了**"他以后不会再写"。
NEED_FREE_MB = 4283      # 估峰值（与 comfy-surface 同一口径）
STABLE_MIN = 30          # ← 由上面那串数据推出（活跃最大间隔 16.4 × ~1.8）

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def gather() -> dict:
    """**现读**四个条件的事实（不做判断 —— 判断在 `verdict`）。"""
    f: dict = {}
    # ① 注册表还被人写吗（mtime 稳定度 + 指纹）
    try:
        st = REG.stat()
        f["注册表_mtime"] = st.st_mtime
        f["注册表_静默分钟"] = round((time.time() - st.st_mtime) / 60.0, 1)
        f["注册表_sha256_前12"] = hashlib.sha256(REG.read_bytes()).hexdigest()[:12]
    except Exception as e:  # noqa: BLE001
        f["注册表_未读到"] = "%s: %s" % (type(e).__name__, str(e)[:50])
    # ② GPU 接上了吗（ComfyUI venv 的 torch 构建）
    try:
        r = subprocess.run(
            [str(VNV), "-c",
             "import json,torch;print(json.dumps({'torch':torch.__version__,"
             "'cuda':bool(torch.cuda.is_available()),"
             "'directml':__import__('importlib.util',fromlist=['x']).find_spec('torch_directml') is not None}))"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        if r.returncode == 0:
            f["算力"] = json.loads((r.stdout or "").strip().splitlines()[-1])
        else:
            f["算力_未读到"] = ((r.stderr or "")[-120:]).strip()
    except Exception as e:  # noqa: BLE001
        f["算力_未读到"] = "%s: %s" % (type(e).__name__, str(e)[:50])
    # ③ 权重在盘上吗
    hits = []
    try:
        for p in COMFY.joinpath("models").rglob("*"):
            if not p.is_file():
                continue
            low = p.name.lower()
            if ("qwen" in low or "uncensored" in low or "heretic" in low) and \
                    p.suffix.lower() in (".safetensors", ".gguf", ".ckpt", ".pt", ".bin"):
                hits.append("%s（%.1f GB）" % (p.name, p.stat().st_size / 1024 ** 3))
    except Exception as e:  # noqa: BLE001
        f["权重_未读到"] = "%s: %s" % (type(e).__name__, str(e)[:50])
    f["权重命中"] = hits
    # ④ 内存够吗（Windows 现读）
    try:
        class _M(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = _M()
        m.dwLength = ctypes.sizeof(_M)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        f["空闲MB"] = m.ullAvailPhys // 1024 ** 2
        f["占用率%"] = m.dwMemoryLoad
    except Exception as e:  # noqa: BLE001
        f["内存_未读到"] = "%s: %s" % (type(e).__name__, str(e)[:50])
    return f


def verdict(f: dict) -> dict:
    """**纯函数**：事实 → 逐条状态 + 总判决。**不读盘、不猜**。"""
    rows = []
    # ① 注册表稳定
    q = f.get("注册表_静默分钟")
    ok1 = isinstance(q, (int, float)) and q >= STABLE_MIN
    rows.append({"条件": "① 注册表不再被并发改写（他停手了）", "过": bool(ok1),
                 "读数": ("静默 %.1f 分钟（阈值 ≥%d）｜ sha %.12s"
                        % (q, STABLE_MIN, f.get("注册表_sha256_前12") or "?"))
                 if q is not None else "**未读到**"})
    # ② GPU
    a = f.get("算力") or {}
    ok2 = bool(a.get("cuda")) or bool(a.get("directml"))
    rows.append({"条件": "② GPU 接上了（CUDA 或 DirectML）", "过": ok2,
                 "读数": ("torch %s ｜ cuda=%s ｜ directml=%s"
                        % (a.get("torch"), a.get("cuda"), a.get("directml")))
                 if a else "**未读到**"})
    # ③ 权重
    hits = f.get("权重命中") or []
    rows.append({"条件": "③ 无审查权重已在盘上", "过": bool(hits),
                 "读数": "、".join(hits) if hits else "**本地没有**（差下载）"})
    # ④ 内存
    free = f.get("空闲MB")
    ok4 = isinstance(free, int) and free >= NEED_FREE_MB
    rows.append({"条件": "④ 可用内存 ≥ 估峰值", "过": bool(ok4),
                 "读数": ("空闲 %s MB ／ 估峰值 %d MB（%s）"
                        % (free, NEED_FREE_MB, "够" if ok4 else "**不够**"))
                 if isinstance(free, int) else "**未读到**"})
    blocked = [r["条件"] for r in rows if not r["过"]]
    return {"判决": ("✅ **READY**（四个条件都满足，可以照 §九 清单动手）" if not blocked
                   else "🔴 **BLOCKED**（%d/4 条未满足）" % len(blocked)),
            "未满足": blocked, "逐条": rows,
            "口径": "**四绿才 READY**；未满足就**不动手**（先解决它们，别硬上）"}


def cmd_check(a) -> int:
    f = gather()
    v = verdict(f)
    print(json.dumps({"判决": v["判决"], "逐条": v["逐条"], "未满足": v["未满足"],
                      "原始事实": f, "口径": v["口径"]}, ensure_ascii=False, indent=1))
    return 0 if not v["未满足"] else 3


def cmd_selftest(a) -> int:
    lines, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    all_good = {"注册表_静默分钟": 30, "注册表_sha256_前12": "abc123",
                "算力": {"torch": "2.14.0+cu", "cuda": True, "directml": False},
                "权重命中": ["qwen.gguf（12.0 GB）"], "空闲MB": 6000}
    v1 = verdict(all_good)
    ck("**正控：四条全绿 ⇒ READY**", v1["判决"].startswith("✅") and not v1["未满足"],
       v1["判决"])
    bad_mem = dict(all_good, 空闲MB=500)
    v2 = verdict(bad_mem)
    ck("**负控：内存不够 ⇒ BLOCKED 且点名第④条**",
       v2["判决"].startswith("🔴") and any("④" in x for x in v2["未满足"]),
       "未满足 = %s" % v2["未满足"])
    no_gpu = dict(all_good, 算力={"torch": "2.14.0+cpu", "cuda": False, "directml": False})
    v3 = verdict(no_gpu)
    ck("**负控：CPU 构建 ⇒ BLOCKED 且点名第②条**",
       v3["判决"].startswith("🔴") and any("②" in x for x in v3["未满足"]),
       "未满足 = %s" % v3["未满足"])
    none = verdict({})
    ck("**负控：什么都没读到 ⇒ BLOCKED（未读到不许当满足）**",
       none["判决"].startswith("🔴") and len(none["未满足"]) == 4,
       "未满足 %d 条" % len(none["未满足"]))
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def cmd_threshold(a) -> int:
    """把「静默多少分钟才算他停手」**从观测数据推一遍**（不是我拍的数字）。"""
    def _m(s):
        h, mi, sec = (int(x) for x in s.split(":"))
        return h * 60 + mi + sec / 60.0
    t = sorted(_m(x) for x in OBSERVED_WRITES)
    gaps = [round(b - a, 1) for a, b in zip(t, t[1:])]
    mx = max(gaps) if gaps else 0
    print(json.dumps({
        "观测到的活跃写盘时刻（本会话取证）": OBSERVED_WRITES,
        "相邻间隔（分钟）": gaps,
        "**活跃期最大间隔**": mx,
        "我最初写死的阈值": 10,
        "它安不安全": ("🔴 **不安全** —— 最大间隔 %.1f 分钟 > 10 ⇒ 会把活跃期误判成「他停手了」" % mx),
        "现在的阈值（由数据推）": STABLE_MIN,
        "推法": "活跃期最大间隔 %s × ~1.8 ⇒ %d 分钟" % (mx, STABLE_MIN),
        "🔴 残余风险（不许省）": "静默判据只能**降低**误判概率，**证明不了**「他以后不会再写」；"
        "真正的证据只有**事后时间**。所以条件①即使判 ✅，也不当「绝对安全」念。",
    }, ensure_ascii=False, indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="无限制创作流水线 · 前置检查（一条命令）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").set_defaults(func=cmd_check)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    sub.add_parser("threshold").set_defaults(func=cmd_threshold)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
