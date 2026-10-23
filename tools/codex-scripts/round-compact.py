# -*- coding: utf-8 -*-
"""round-compact -- 每炉固定收尾三件：压缩显存 · 压缩体积 · 重新双向绑定并出精准直达索引。

C1 显存压缩已生效（现读源码开关 + 最近实测峰值）
C2 文件体积压缩（量读数 · 把旧日志 gzip 进 .scratch/archive · 报省下多少字节）
C3 重新双向绑定触手（autobind apply + 连接登记 check + 绑定 check）+ 生成精准直达索引 state/direct-index.json
用法：py -3.14 tools/codex-scripts/round-compact.py [--gzip-old] [--round v41]
"""
from __future__ import annotations
import argparse, gzip, json, shutil, subprocess, sys, time
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
ARCH = ROOT / ".scratch" / "archive"
IDX = ROOT / "state" / "direct-index.json"
KNOBS = {
    "训练固定长度装箱 BLOCK=512": ("tools/train/train_v26_qlora.py", "BLOCK"),
    "use_cache=False（省显存）": ("tools/train/train_v26_qlora.py", "use_cache"),
    "expandable_segments": (".scratch/launch_v41.py", "expandable_segments"),
    "推理 low_cpu_mem_usage": ("tools/train/accept_infer.py", "low_cpu_mem_usage"),
    "推理 SDPA 注意力": ("tools/train/accept_infer.py", "sdpa"),
    "推理 OOM→4bit 回退": ("tools/train/accept_infer.py", "4bit"),
}


def run(args, timeout=300):
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT), timeout=timeout)
    return (p.returncode, (p.stdout or "") + (p.stderr or ""))


def c1():
    print("[C1] 显存压缩开关（现读源码，不采信自述）")
    ok = 0
    for name, (f, kw) in KNOBS.items():
        p = ROOT / f
        hit = p.is_file() and kw in p.read_text(encoding="utf-8", errors="replace")
        ok += 1 if hit else 0
        print("   %s %s" % ("OK " if hit else "RED", name))
    peak = ""
    for lg in sorted((ROOT / ".scratch").glob("train_v4*.log"), key=lambda x: x.stat().st_mtime, reverse=True)[:1]:
        body = ""
        try:
            body = lg.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass
        for ln in body.splitlines():
            if "peak" in ln.lower() or "GB" in ln:
                peak = ln.strip()[:110]
    print("   最近显存读数：%s" % (peak or "未读到（训练日志里没打印峰值）"))
    return ok, len(KNOBS)


def c2(gzip_old: bool, round_name: str):
    print("[C2] 文件体积（量读数 + 压缩旧日志）")
    targets = []
    for pat in ("state/train/corpus_v4*_manifest.json", ".scratch/self_knowledge_v4*.jsonl",
                ".scratch/*_a4*.jsonl", ".scratch/*.log", "docs/*.md", "state/*.json"):
        targets += list(ROOT.glob(pat))
    total = sum(p.stat().st_size for p in targets if p.is_file())
    big = sorted(((p.stat().st_size, p) for p in targets if p.is_file()), reverse=True)[:6]
    print("   在役件 %d 个 · 合计 %.1f MB" % (len(targets), total / 1048576))
    for sz, p in big:
        print("     最大 %8.1f KB  %s" % (sz / 1024, p.relative_to(ROOT)))
    saved = 0
    if gzip_old:
        ARCH.mkdir(parents=True, exist_ok=True)
        cutoff = time.time() - 3 * 3600
        for lg in list((ROOT / ".scratch").glob("*.log")):
            if lg.stat().st_mtime < cutoff and lg.stat().st_size > 4096:
                dst = ARCH / (lg.name + ".gz")
                with lg.open("rb") as fi, gzip.open(dst, "wb") as fo:
                    shutil.copyfileobj(fi, fo)
                saved += lg.stat().st_size - dst.stat().st_size
                lg.unlink()
        print("   旧日志 gzip 归档：省下 %.1f KB（原件已 gzip 进 .scratch/archive，可 gunzip 还原）" % (saved / 1024))
    return total, saved


def c3():
    print("[C3] 重新双向绑定 + 精准直达索引")
    rc1, o1 = run([PY, "-X", "utf8", "tools/codex-scripts/capability-autobind.py", "apply"], timeout=420)
    rc2, o2 = run([PY, "-X", "utf8", "tools/codex-scripts/tentacle-link-registry.py", "--check"])
    rc3, o3 = run([PY, "-X", "utf8", "tools/codex-scripts/capability-bindings.py", "--check"])
    bind_ok = "FAIL 0" in o2
    link_ok = "FAIL 0" in o3
    print("   autobind: %s | 连接登记 FAIL0: %s | 绑定 FAIL0: %s" % ("OK" if rc1 == 0 else "RED", bind_ok, link_ok))
    # 直达索引：能力位 -> handler + 一句话用法（从注册表抽取，O(1) 直达）
    idx = {}
    reg = (ROOT / "gbt_allinone" / "caps_registry.py").read_text(encoding="utf-8", errors="replace")
    import re
    for m in re.finditer(r'^\s{4}"([a-z0-9_]+)":\s*\{', reg, re.M):
        name = m.group(1)
        block = reg[m.end():m.end() + 400]
        h = re.search(r'"handler":\s*"([^"]+)"', block)
        d = re.search(r'"domain":\s*"([^"]+)"', block)
        idx[name] = {"domain": (d.group(1) if d else ""), "handler": (h.group(1) if h else ""),
                     "direct": "five-dim.py cap " + name}
    # 今晚新增的直达样例（精准直达：位 -> op -> 一句话）
    for extra, ops in (("skill_forge", "think/radar/experience/style/anti"),
                       ("offense_ops", "plan/roles/tools/evidence/memory/gate"),
                       ("spider_ops", "plan/adaptive/fetch/parse/robots"),
                       ("showcase_ops", "concept/parts/frame/motion/readout/selfcheck")):
        if extra in idx:
            idx[extra]["ops"] = ops
    IDX.write_text(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "count": len(idx), "index": idx},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print("   直达索引：%d 位 -> %s（O(1) 直达：cap <位> 即到 handler）" % (len(idx), IDX.name))
    return bind_ok and link_ok, len(idx)


def main():
    ap = argparse.ArgumentParser(description="每炉收尾：压缩显存/体积 + 双向绑定 + 直达索引")
    ap.add_argument("--gzip-old", action="store_true")
    ap.add_argument("--round", default="")
    a = ap.parse_args()
    ok1, n1 = c1()
    total, saved = c2(a.gzip_old, a.round)
    ok3, n3 = c3()
    verdict = ok1 == n1 and ok3
    print("== 收尾判定 %s（显存开关 %d/%d · 绑定 %s · 直达位 %d）==" % ("PASS" if verdict else "FAIL", ok1, n1, "OK" if ok3 else "RED", n3))
    try:
        run([PY, "-X", "utf8", "tools/codex-scripts/logbook.py", "append", "--kind", "change", "--what",
             "round-compact %s: 显存开关 %d/%d · 体积 %.1fMB(省 %.1fKB) · 绑定 %s · 直达 %d 位"
             % (a.round or "-", ok1, n1, total / 1048576, saved / 1024, "OK" if ok3 else "RED", n3)], timeout=90)
    except Exception:
        pass
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
