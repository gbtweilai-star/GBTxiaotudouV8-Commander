# -*- coding: utf-8 -*-
# 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""重烤所有生成页（bake-all-pages）

根因（主人令 2026-10-16「把报警的全部追踪根因修复加固」）：
  快照页（把数据**烤进 HTML**的那种）**不会自己变新** —— 没人重烤就一直旧。
  实测：ai-board 117.3 小时 · blueprint 100.2 小时 · cloud-plugins/cloud-status/plugins-mesh 各 117.3 小时。

加固做法：每张快照页**自己报重生成命令**（页里就写着）⇒ 本件把它们逐条跑一遍，
  并报**重烤前/后的时间戳**。不编命令：页里没写就如实报「未读到重生成命令」。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

WS = Path(__file__).resolve().parents[2]
TS = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})")
CMD = re.compile(r"(py -3\.14 [^<\n\"]{0,160})")
SELF = Path(__file__).name

# 2026-10-17 加固（留痕：原口径 / 为什么翻 / 现口径）
#   原口径：`CMD.findall(整页)` —— 取页里**第一处** `py -3.14 …` 就当作重生成命令、直接 shell 执行。
#   为什么翻（2026-10-17 08:44 实测事故，已拦下但差点真跑）：
#     · code-deck 页第一处是 `-m gbt_allinone auth grant --scope filesystem_write --ttl 600`
#       ⇒ 这是**让 AI 给自己发授权**（红线），而且会阻塞等终端 YES；
#     · eye 页第一处是 `eye-feed.py --loop` ⇒ **永久循环**；
#     · digital-human 页第一处是 `intercom.py watch …` ⇒ 常驻监视。
#   原期望：只跑页里**明写的「重建 / 重生成」那一句**，别的 py 命令一概不碰。
#   现口径：① 只从「重建：」「重生成 」标记段取命令；② 命令尾部按 `·`/`｜`/`|`/`-->`/`<` 截断；
#           ③ 命中危险词（--loop / auth grant / watch / serve / daemon …）⇒ **不跑并报出理由**；
#           ④ 自我递归与判据命令同样不跑。
MARK = re.compile(r"(?:重建|重生成)\s*[:：]?\s*")
CUT = re.compile(r"·|｜|\||-->|<|\s{2,}")
DANGER = ("--loop", "auth grant", "grant --scope", " watch", "serve", "daemon",
          "--rounds", "--seconds", "watchdog")

# 2026-10-17 再加（留痕）：本件只该烤**快照页**（数据在生成时烤进 HTML）。
#   原口径把 21 个功能页**一视同仁**，于是把「活页」（静态壳 + `*-data.js` 渲染取数）也算成
#   「无重建标记 ⇒ 未跑」—— 那是**把设计意图当故障**（`page-bind-check` 的原话）。
#   证据：brain/capability-bar/db-fleet/digital-human/logbook 全都在页里引 `*-data.js`，
#         而 `db-fleet.py` / `logbook.py` 只**检查** index.html 存在、从不写它 ⇒ 它们没有 HTML 生成器，
#         只有数据件生成器。⇒ 现在按证据分型：活页不烤 HTML，只如实报它是活页。
LIVE_RE = re.compile(r"[\w.-]+-data\.js")
# 服务写页 / 静态页：全仓 0 个 HTML 生成器（2026-10-17 grep 实测），不猜、不编命令。
SERVICE_PAGES = {"eye": "活页（由 eye-feed.py 常驻服务写，不烤 HTML）"}
STATIC_PAGES = {"activity", "eigenflux", "h1", "panel"}


def _safe_cmd(text: str) -> tuple:
    """从页里取「重建/重生成」那一句命令。返回 (cmd, 不能跑的理由)。"""
    m = MARK.search(text)
    if not m:
        return "", "页里没有「重建/重生成」标记"
    line = text[m.end():].split("\n", 1)[0]
    cm = CMD.search(line)
    if not cm:
        return "", "标记后没读到 py -3.14 命令"
    cmd = CUT.split(cm.group(1))[0].strip()
    if not cmd:
        return "", "命令被截成空"
    if SELF in cmd or "page-bind-check" in cmd:
        return cmd, "自我递归／判据命令 ⇒ 不自动跑"
    low = cmd.lower()
    for bad in DANGER:
        if bad in low:
            return cmd, "危险命令（命中 %r）⇒ 不自动跑" % bad
    return cmd, ""


def _registry_cmds() -> dict:
    """从 `capability-audit.py` 的 ARTIFACTS 表读「产物相对路径 → 重建命令」。

    🔴 2026-10-17 加（留痕）：根因是**两套约定打架** ——
       `page-bind-check` 认 deck 家族 `data-data-kind="快照"`，而本件只认「重建：」标记；
       ⇒ code-deck/exec-deck/plugins-mesh/blueprint 这类页在本件眼里「没有重建标记」、永远烤不了。
       仓内其实**已有唯一命令真源**：`capability-audit.ARTIFACTS`（字段：id·路径·人读名·命令·stale_vs·宽限）。
       现口径：页里没写标记时，用这张表按产物路径兜底；仍然没有 ⇒ 如实报「未登记」。
       只用 `ast.literal_eval` **静态读表**，不 exec 任何模块、不跑命令。
    """
    out = {}
    try:
        import ast as _ast
        p = WS / "tools" / "codex-scripts" / "capability-audit.py"
        tree = _ast.parse(p.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, _ast.Assign):
                continue
            if not any(getattr(t, "id", "") == "ARTIFACTS" for t in node.targets):
                continue
            for row in _ast.literal_eval(node.value):
                if len(row) >= 4:
                    rel = str(row[1]).replace("\\", "/")
                    cmd = str(row[3]).strip()
                    if rel and cmd:
                        out.setdefault(rel, cmd)
    except Exception:                                          # noqa: BLE001
        return {}
    return out


def snapshot_pages() -> list:
    root = WS / "holo_pet_w3"
    out = []
    if not root.is_dir():
        return out
    reg = _registry_cmds()
    for sub in sorted(root.iterdir()):
        f = sub / "index.html"
        if not sub.is_dir() or not f.is_file():
            continue
        t = f.read_text(encoding="utf-8", errors="replace")
        cmd, why = _safe_cmd(t)
        cmd_src = "页内标记" if cmd else ""
        if not cmd:
            rel = "holo_pet_w3/%s/index.html" % sub.name
            rc = reg.get(rel, "")
            if rc:
                cmd, why, cmd_src = rc, "", "登记表(capability-audit.ARTIFACTS)"
        if not cmd:
            # 没命令 ⇒ 按**证据**分型，而不是笼统一句「未跑到」：
            if LIVE_RE.search(t):
                why = "活页（*-data.js 驱动，HTML 不烤；数据件由各自生成器刷新）"
            elif sub.name in SERVICE_PAGES:
                why = SERVICE_PAGES[sub.name]
            elif sub.name in STATIC_PAGES:
                why = "静态页（全仓 0 个 HTML 生成器，实测 2026-10-17）"
            elif not why:
                why = "页里没有「重建/重生成」标记"
        ts = TS.findall(t)
        out.append({"page": sub.name, "file": str(f).replace(chr(92), "/"),
                    "baked_at": ts[0] if ts else "",
                    "cmds": [cmd] if cmd else [], "skip_why": why,
                    "cmd_src": cmd_src})
    return out


def run(apply: bool = True, only: str = "") -> dict:
    pages = snapshot_pages()
    rows, ran, failed = [], 0, 0
    for p in pages:
        if only and only != p["page"]:
            continue
        cmd = p["cmds"][0] if p["cmds"] else ""
        row = {"page": p["page"], "before": p["baked_at"], "cmd": cmd,
               "skip_why": p.get("skip_why", "")}
        if not cmd:
            row["result"] = p.get("skip_why") or "未读到重生成命令（不编）"
            rows.append(row)
            continue
        if not apply:
            row["result"] = "仅预览"
            rows.append(row)
            continue
        r = subprocess.run(cmd, shell=True, cwd=str(WS), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        ran += 1
        f = Path(p["file"])
        ts2 = TS.findall(f.read_text(encoding="utf-8", errors="replace")) if f.is_file() else []
        row["after"] = ts2[0] if ts2 else ""
        row["rc"] = r.returncode
 # 2026-10-20 口径修正（留痕，P1「判据错尺」实证）：
        #    原来把 `rc != 0` 直接记失败。实测 exec-deck.py --html 每次**都写出了页**
        #    （data-at/mtime 前进、内容是本轮的），但它把"有 1 条要人看的事项"也编码成 rc=2
        #    ⇒ 页面明明写好了却报"失败"。改成：**页时间戳没前进 + rc!=0** 才算失败；
        #    时间戳前进但 rc!=0 ⇒ 记成 `已写页·rc≠0` 单列，既不误报失败、也不把待办吞掉。
        advanced = bool(ts2 and ts2[0] != (p["baked_at"] or ""))
        if r.returncode != 0 and not advanced:
            failed += 1
            row["result"] = "写页失败（rc=%s，时间戳未前进）" % r.returncode
        elif r.returncode != 0:
            row["result"] = "已写页 · 生成器 rc=%s（把待办也编码进退出码）" % r.returncode
        else:
            row["result"] = "已重烤"
        row["tail"] = ((r.stdout or "") + (r.stderr or "")).replace(chr(10), " ").strip()[-120:]
        rows.append(row)
    return {"ok": failed == 0, "kind": "bake_all_pages", "apply": apply,
            "pages": len(pages), "ran": ran, "failed": failed, "rows": rows}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="重烤所有生成页（读每页自报的命令）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    r = run(apply=not a.dry_run, only=a.only)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        _skip = sum(1 for x in r["rows"] if x.get("skip_why"))
        _warn = sum(1 for x in r["rows"] if str(x.get("result", "")).startswith("已写页"))
        print("重烤生成页：%d 页 · 跑了 %d · 失败 %d · 已写页但rc≠0 %d · 未跑 %d"
              % (r["pages"], r["ran"], r["failed"], _warn, _skip))
        for x in r["rows"]:
            print("  %-14s %s -> %s  rc=%s%s"
                  % (x["page"], x.get("before") or "无标记", x.get("after") or "无标记",
                     x.get("rc", "-"),
                     ("  ← " + x["skip_why"]) if x.get("skip_why") else ""))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
