#!/usr/bin/env python
# -*- coding: utf-8 -*-
# gbt-instrument: 装机回执 —— 从**真打出来的包**里量，不问打包器报了什么
# 开发者：自由的风 · GBT小土豆V8
"""装机回执生成器（只读 dist/，写一份 state/desktop-install-receipt.json）。

## 为什么要有它

「打包上线」这条在 2026-09-23 之前**一直是空的**：配置写了，但从没真跑过
（真跑才发现两条配置错误，见下）。而"打过包了"这句话如果没有**回执**，
下一个人只能靠信；六视角验收的「交付」格子也正是卡在这一件上（PENDING）。

## 它为什么不问打包器

回执**不采信 `npm run pack` 的 stdout**，而是**重新拆开 `dist/win-unpacked` 量一遍**：
文件数、字节数、exe、app 面清单、8 扇窗、负规则。
理由是本仓的老规矩：**报表层说的不算证据，被量的东西才算**。
（实测就撞过：electron-builder 打完包打印 "no node modules returned while searching
directories"，**而它确实往 `holo_pet_w3/` 装了一个 `node_modules`**。照抄它的 stdout
写回执，回执当场就是假的。）

## 两条负规则是回执的重点（不是"包能出来"）

  ① **触手拍的整屏截图不许进包**（`eye/frames/**` 12 张 / 1.9 MB）——
     打包白名单与 `.gitignore` 曾经不同步，App 会带着主人的桌面截图分发。
  ② **依赖目录不许进包**（`node_modules`）—— 白名单制就是为了这个。

用法：
    py -3.14 tools/codex-scripts/pack-receipt.py            # 量并写回执
    py -3.14 tools/codex-scripts/pack-receipt.py --dry       # 只量不写
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

APP = ROOT / "dist" / "win-unpacked"
SHELL = ROOT / "holo_pet_w3"
RECEIPT = ROOT / "state" / "desktop-install-receipt.json"
EXE = APP / "GBT小土豆V8.exe"


def walk(base: Path):
    out = []
    stack = [base]
    while stack:
        here = stack.pop()
        try:
            entries = list(os.scandir(here))
        except OSError:
            continue
        for ent in entries:
            try:
                if ent.is_dir(follow_symlinks=False):
                    stack.append(Path(ent.path))
                elif ent.is_file(follow_symlinks=False):
                    out.append((Path(ent.path).relative_to(base).as_posix(),
                                ent.stat(follow_symlinks=False).st_size))
            except OSError:
                continue
    return out


def sha16(p: Path) -> str:
    h = hashlib.sha256()
    try:
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()[:16]


def main() -> int:
    ap = argparse.ArgumentParser(description="装机回执（只读 dist/）")
    ap.add_argument("--dry", action="store_true", help="只量不写")
    a = ap.parse_args()

    checks: list[dict] = []

    def chk(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    if not APP.is_dir():
        chk("包在不在", False, "没有 %s —— 先跑 `cd holo_pet_w3 && npm run pack`" % APP)
        return _emit(checks, a.dry)

    files = walk(APP)
    total = sum(s for _r, s in files)
    app_files = [(r, s) for r, s in files if r.startswith("resources/app/")]

    # ── 基本件 ──
    chk("可执行文件", EXE.is_file(),
        ("%s · %.1f MB · sha16 %s" % (EXE.name, EXE.stat().st_size / 1048576, sha16(EXE)))
        if EXE.is_file() else "缺 %s" % EXE)
    chk("整包体量", len(files) > 100, "%d 文件 / %.1f MB" % (len(files), total / 1048576))
    chk("app 面非空", len(app_files) > 50,
        "%d 文件 / %.1f MB" % (len(app_files), sum(s for _r, s in app_files) / 1048576))

    # ── 壳要读的件 ──
    need = ["resources/app/shell/windows.json", "resources/app/shell/main.cjs",
            "resources/app/index.html", "resources/app/package.json",
            "resources/tools/codex-scripts/desktop-shell-guard.py",
            "resources/tools/codex-scripts/vendor_three.py",
            "resources/tools/codex-scripts/audit_skin.py"]
    missing = [n for n in need if not (APP / n).is_file()]
    chk("壳与 extraResources 齐件", not missing,
        "全在" if not missing else "缺：%s" % ", ".join(missing))

    # ── 8 扇窗（从**包内**的注册表现读，不是从源树）──
    nwin, ids = 0, []
    try:
        reg = json.loads((APP / "resources/app/shell/windows.json").read_text(encoding="utf-8"))
        ids = [w.get("id") for w in reg.get("windows", [])]
        nwin = len(ids)
    except (OSError, ValueError) as e:
        chk("包内窗口注册表", False, "读不动：%s" % e)
    src_win = 0
    try:
        src_win = len(json.loads((SHELL / "shell" / "windows.json")
                                 .read_text(encoding="utf-8")).get("windows", []))
    except (OSError, ValueError):
        pass
    chk("窗口数与源一致", nwin == src_win and nwin > 0,
        "包内 %d 扇 · 源 %d 扇 · %s" % (nwin, src_win, ", ".join(str(i) for i in ids)))

    # ── 负规则①：触手截图不许进包 ──
    shots = [r for r, _s in files
             if "eye/frames" in r or r.endswith("frames.js") or r.endswith(".png")
             and "/eye/" in r]
    chk("负规则·触手截图未进包", not shots,
        "零命中" if not shots else "**进包了 %d 个**：%s" % (len(shots), ", ".join(shots[:4])))

    # ── 负规则②：依赖目录不许进包 ──
    deps = [r for r, _s in files if "node_modules/" in r]
    chk("负规则·依赖目录未进包", not deps,
        "零命中" if not deps else "**进包了 %d 个**：%s" % (len(deps), ", ".join(deps[:4])))

    # ── 版本一致（源 package.json 与包的 electron 版本）──
    ev = ""
    try:
        ev = str(json.loads((SHELL / "package.json").read_text(encoding="utf-8"))
                 .get("build", {}).get("electronVersion", ""))
    except (OSError, ValueError):
        pass
    chk("electron 版本定值", bool(ev) and ev[0].isdigit(), "electronVersion=%r" % ev)

    # ── 🔴 包与源码**同源**吗（2026-09-23 第 46 轮加）──
    # 为什么这是本回执最该有的一格（实测教训）：
    #   我第 40 轮打出包、回执 **8 项红 0**；此后第 43-45 轮改了
    #   `window.js` / `index.html` / `shell/main.cjs` / `shell/preload.cjs` ——
    #   而回执**照样全绿**，因为原来的 8 项**只量包的形状，不量包的内容**。
    #   ⇒ 一个"PASS"的回执配一个**过期的包**，是最坏的一种绿：它让人以为装机件是新的。
    #   ⇒ 逐字节比 sha256：包里的 `resources/app/<路径>` 必须等于源里的同名文件。
    # ⚠️ `package.json` **不参与比对**：electron-builder 会重写它（裁剪字段），
    #    比它必然"不同源"，那是打包器的正常行为，不是缺陷。
    PARITY = ["index.html", "window.js", "window.css", "deck3d.css",
              "skin-mission-control.css", "ef_render.js",
              "shell/main.cjs", "shell/preload.cjs", "shell/chrome.cjs",
              "shell/windows.json", "shell/layout.cjs", "shell/url-policy.cjs",
              "brain/brain.js", "brain/brain-data.js", "brain/index.html",
              "code-deck/index.html", "exec-deck/index.html", "h1/index.html",
              "eye/index.html", "eigenflux/index.html"]
    pairs, miss = [], []
    for rel in PARITY:
        s = SHELL / rel
        d = APP / "resources" / "app" / rel
        if not s.is_file():
            continue                      # 源里没有的（例如某些窗未生成）不算红
        if not d.is_file():
            miss.append(rel + "（包里没有）")
            continue
        sa, sb = sha16(s), sha16(d)
        if sa != sb:
            miss.append("%s（源 %s ≠ 包 %s）" % (rel, sa, sb))
        else:
            pairs.append(rel)
    chk("包与源码同源", not miss,
        ("逐字节一致 %d 个文件" % len(pairs)) if not miss
        else ("**%d 个不一致**：%s" % (len(miss), " · ".join(miss[:4]))
              + ("…" if len(miss) > 4 else "")
              + " ⇒ 这个包**不是从当前源码打出来的**，回执不该判它 PASS"))

    return _emit(checks, a.dry, files=len(files), bytes_=total, exe=EXE, ev=ev)


def _emit(checks, dry, files=0, bytes_=0, exe=None, ev="") -> int:
    bad = [c for c in checks if not c["ok"]]
    verdict = "PASS" if not bad else "FAIL"
    print("=" * 84)
    print("装机回执 · 从**真打出来的包**里量（不采信打包器 stdout）")
    print("=" * 84)
    for c in checks:
        print("  %s %-30s %s" % ("✅" if c["ok"] else "🔴", c["check"], c["detail"]))
    print("-" * 84)
    print("  %s · %d 项 · 红 %d 项" % (verdict, len(checks), len(bad)))
    if dry:
        print("  （--dry：没写回执）")
        return 0 if not bad else 2
    if bad:
        print("  🔴 有红项 ⇒ **不写回执**（回执只记合格的包）")
        return 2
    payload = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "verdict": verdict,
        "what": "GBT小土豆V8 一体式桌面壳 · 装机包（electron-builder --win --dir · portable）",
        "artifact": {
            "exe": str(exe) if exe else "",
            "exe_bytes": exe.stat().st_size if exe and exe.is_file() else 0,
            "files": files, "bytes": bytes_, "electronVersion": ev,
        },
        "checks": checks,
        "why_measured_not_reported": (
            "回执不采信 `npm run pack` 的 stdout：实测它打印 "
            "'no node modules returned while searching directories'，"
            "**而它确实往 holo_pet_w3/ 装了一个 node_modules**。照抄 stdout 的回执当场就是假的。"),
        "note": "负规则两条（触手截图 / 依赖目录不许进包）是这份回执的重点。",
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("  ✅ 回执已写：%s" % RECEIPT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
