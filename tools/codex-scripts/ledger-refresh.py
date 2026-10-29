#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""台账写手（P9 · 「账没有写手必烂」的根治件）· 2026-10-18 立。

## 为什么要有这件

`state/排查台账.json` 是宿主插件渲染进**会话头的第三块上下文**（`gbt-progress-ledger`），
Owner 令叫它「唯一进度真源」。2026-10-18 全量扫描现读出来的病灶：

    `updated_at = 2026-10-11T20:01:17+07:00`  ← **6 天 8 小时没动**
    而 `state/logbook.jsonl` 同一天 04:57 还在写（第 701 笔）

⇒ 注入给模型的「唯一进度真源」其实是**六天前的快照**。这正是本仓根因表 P9：
**手造的账没有生产者 ⇒ 它只会越来越旧**（同型实证：`state/caps-beyond-probeable.json`
注册表长到 232 而它停在 30）。

## 它写什么、不写什么（这条最重要）

**不写**：`in_progress` / `not_done` / `open_faults` / `owner_decisions` / `根因模式表`
—— 这些是**判断**，机器编出来就是造假账。人写，本件只**量它多久没动**。

**写**（全部有真证据、可复算）：
  1. `state/工程进度.md` —— 台账自己声明过的「人读一屏账」（原先**声明了但文件不存在**）；
  2. 台账 `工程进度一屏账` 那一节的 `updated` / `行数`（与 1 实盘对齐，不再手填）；
  3. 台账 `_写手` 一节：每一节的 sha16 + 最后改动时刻、本次复算读数、腐烂项；
  4. `updated_at`：**只在真内容变了时**才前进（内容不变就不许动，否则就是假新鲜）。

## 腐烂判据（有牙，`--check` 非零退出）

  R1 声明了 `state/工程进度.md` 而盘上没有 / 与实盘不一致
  R2 `in_progress` 里那个人写日期，比 logbook 最新一笔旧 **> 72 小时**，且期间机器日志已前进 ≥ 20 笔
     （「人写的停在 X、机器日志已跑到 Y」—— 本仓最典型的无声腐烂）
  R3 `_写手` 节缺失（= 又退化成手造账）
  R4 `_写手.checked_at` 超过 24 小时（写手自己没人调 —— P8：驱动没接上）

## 时辰口径（F15 的坑，必须绕开）

`state/logbook.jsonl` 里的 `ts` 实测是 **`+08:00`**，而本机真实偏移是 **`+07:00`**。
⇒ **不许原样抄**：一律 `astimezone()` 换成机器本地偏移再落盘。
`gbt_allinone/tests/test_progress_ledger_contract.py` 会咬住这条（偏移必须是机器偏移或 UTC）。

用法：
    py -3.14 tools/codex-scripts/ledger-refresh.py            # 复算并落盘（写手）
    py -3.14 tools/codex-scripts/ledger-refresh.py --check     # 只读判据（开机自检用，非零=红）
    py -3.14 tools/codex-scripts/ledger-refresh.py --check --json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "state" / "排查台账.json"
LOGBOOK = ROOT / "state" / "logbook.jsonl"
SHEET = ROOT / "state" / "工程进度.md"

# 编码守门（本机控制台 GBK：不带这道闸时印中文会 UnicodeEncodeError ⇒ stdout 空 ⇒ 调用方解析空 ⇒ 恒红）
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

HUMAN_SECTIONS = ("in_progress", "not_done", "open_faults", "owner_decisions", "根因模式表")
STALE_HOURS = 24
INPROGRESS_MAX_AGE_H = 72
LOGBOOK_ADVANCE_TRIGGER = 20


# ── 时辰 ──────────────────────────────────────────────────────────────────────
def now_local() -> datetime:
    return datetime.now().astimezone()


def stamp(dt: datetime) -> str:
    """机器本地偏移的 ISO 串（F15：不写 +08:00 这种看起来很像的编造值）。"""
    return dt.astimezone().replace(microsecond=0).isoformat()


def parse_any(raw: str) -> datetime | None:
    """吃 `2026-10-18T04:57:56+08:00` / `2026-10-18 04:57` / `2026/10/18 04:57:56` 三种写法。"""
    if not raw:
        return None
    t = str(raw).strip().replace("/", "-").replace(" ", "T")
    try:
        d = datetime.fromisoformat(t)
    except ValueError:
        return None
    return d.astimezone() if d.tzinfo is None else d


# ── 证据源 ────────────────────────────────────────────────────────────────────
def load_ledger() -> dict:
    with LEDGER.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_logbook() -> list:
    rows = []
    if not LOGBOOK.is_file():
        return rows
    with LOGBOOK.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            at = parse_any(row.get("ts") or "")
            if at is None:
                continue
            rows.append({"at": at, "what": str(row.get("what") or "").strip(),
                         "kind": str(row.get("kind") or ""), "n": row.get("n")})
    return rows


def sha16(value) -> str:
    blob = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def atomic_write(path, text: str) -> None:
    """原子落盘：写同目录临时件 → os.replace。**绝不 `open(目标,'w')`**。

    🔴 2026-10-22 实证（当天真栽的跟头，留痕）：
      对本台账直接 `Path.write_text(...)` / `open(path,'w')` 会抛
      `OSError: [Errno 22] Invalid argument` —— 因为宿主那一侧正盯着这份台账
      （它被注入进每个会话头），写入句柄撞在共享打开上。
      同一次操作改成「临时件 + os.replace」当场成功。
      ⇒ 台账这种**被别人持有/监视**的文件，落盘一律走原子替换。
      同轮事故：一次探针误用 `open(path,'w')` 把台账截成 0 字节，
      已从 git HEAD 恢复（log 95 笔与各节完好，详见
      tools/codex-scripts/ledger-restore-from-git.py 里的恢复说明）。
    """
    directory = os.path.dirname(str(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".atomic-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ── 一屏账（人读 · 每行带证据）────────────────────────────────────────────────
def render_sheet(led: dict, logbook: list, at: datetime) -> tuple:
    """返回 (markdown 全文, 行列表)。行列表用来算「行数」，不靠数分隔符。

    🔴 2026-10-18 两轮自纠（都是**判据设计错**，不是文件坏 —— 记在这里防下一版又踩）：

    第一版：把「生成时刻 = 当前时间」写进页面 ⇒ 任何时刻复算都不相等 ⇒ R1 恒红。
    第二版：改成读 `logbook` 末笔与 `boot-selfcheck-last.json` ⇒ 仍然恒红，因为这两份**
            每次开机/每记一笔都在变**，于是「一屏账陈旧」几乎每次启动都成立 ⇒ 判据退化成噪声。
            本仓的对错口径是「被噪声淹没的红 = 等于没有判据」。

    ⇒ 定稿口径：**本页是台账的纯函数**（输入只有 `led`），不读 logbook、不读体检落痕。
      理由：这一页叫「工程进度一屏账」，它呈现的是**台账这个真相源**；
      体检读数由 `boot-selfcheck.py` 自己给，不需要这一页转述（转述就会漂）。
      于是 R1 只在**真该红**时红：有人手改了这一页，或台账改了却没跑写手。
    """
    ref = parse_any(str(led.get("updated_at") or "")) or at
    faults = led.get("open_faults") or []
    not_done = led.get("not_done") or []
    asks = led.get("owner_decisions") or []
    rows = []

    rows.append(("现在在做", str(led.get("in_progress") or "（未写）"),
                 "台账 `in_progress` · 人写 · 写手不代笔"))
    rows.append(("未清故障", "**%d 条** · %s" % (
        len(faults),
        " · ".join("%s[%s]" % (f.get("id"), f.get("severity")) for f in faults) or "（无）"),
        "台账 `open_faults` · 逐条带 `evidence` · 复验走 `reverify-open-faults.py`"))
    rows.append(("没做", "**%d 条** · 名单全文在台账 `not_done`" % len(not_done),
                 "台账 `not_done` · 每项带 id/what/why/where"))
    rows.append(("等你拍板", "**%d 条** · %s" % (
        len(asks), " ".join(str(a.get("id")) for a in asks) or "（无）"),
        "台账 `owner_decisions` · 每条带 ask/why"))

    tail = (led.get("log") or [])[-5:]
    if tail:
        rows.append(("最近 5 笔排查记录",
                     "<br>".join("%s · %s" % (str(r.get("at") or ""), str(r.get("what") or "")[:88])
                                 for r in reversed(tail)),
                     "台账 `log` 末 %d 笔 · 全量机器轨迹在 `state/logbook.jsonl`" % len(tail)))
    else:
        rows.append(("最近 5 笔排查记录", "（台账 log 空）", "台账 `log`"))

    out = [
        "# GBT小土豆V8 · 工程进度一屏账",
        "",
        "> **本页由 `tools/codex-scripts/ledger-refresh.py` 生成，不要手改。**",
        "> 它原先只被台账 `工程进度一屏账` 那一节**声明**过（写于 2026-09-28），而盘上从来没有这个文件 ——",
        "> 2026-10-18 全量扫描现读发现「声明了不存在」，本轮补上写手（P9：账没有写手必烂）。",
        "",
        "- 台账时间点：**%s**（本页是台账的纯函数：只随台账变，不随「此刻」漂）" % stamp(ref),
        "- 证据口径：只写有真证据的行；没证据写未验；每行带证据与缺口",
        "- 人写字那一半（现在在做 / 没做 / 未清故障 / 等你拍板）**写手不代笔**，只负责量它多久没动",
        "- 体检读数不在这里转述：跑 `python tools/codex-scripts/boot-selfcheck.py`（转述会漂）",
        "",
 # 2026-10-18 镜像体检当场逮到：mirror_scan 的 signature 一项红 —— 本仓规矩是
        #    「文本页（.md/.html/.htm/.txt/.csv）必须携带开发者署名」，判据是 signature.has_signature
        #    里那个标记串。生产上没暴露（题面不在那一步），镜像里 4/5 一跑就现形。
        "> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属",
        "",
        "| 类别 | 现读 | 证据 |",
        "|---|---|---|",
    ]
    for cat, val, ev in rows:
        out.append("| %s | %s | `%s` |" % (cat, val.replace("|", "\\|"), ev))
    out.append("")
    return "\n".join(out), rows


# ── 复算 ──────────────────────────────────────────────────────────────────────
def rotate(led: dict, logbook: list, at: datetime) -> tuple:
    """返回 (rot, 新 _写手 块, 真变了的节, 一屏账行数)。rot 是**真腐烂**，不是提醒。"""
    writer = led.get("_写手") if isinstance(led.get("_写手"), dict) else {}
    prev_sections = writer.get("sections") if isinstance(writer.get("sections"), dict) else {}

    sections = {}
    moved = []
    for key in HUMAN_SECTIONS:
        h = sha16(led.get(key))
        old = prev_sections.get(key) or {}
        changed_at = old.get("changed_at")
 # 只有这一节的 sha 与**上次落盘记下的**不同，才算人改过 ⇒ changed_at 才前进。
        #    拿"当前内容跟自己比"永远相等 —— 那正是本轮第一版写歪的地方。
        if old.get("sha16") != h or not changed_at:
            changed_at = stamp(at)
            if old.get("sha16") is not None and old.get("sha16") != h:
                moved.append(key)
        sections[key] = {"sha16": h, "changed_at": changed_at}

    rot = []

    # R1 一屏账：声明了就必须在，且与实盘一致
    sheet_text, sheet_rows = render_sheet(led, logbook, at)
    declared = led.get("工程进度一屏账") if isinstance(led.get("工程进度一屏账"), dict) else {}
    if not SHEET.is_file():
        rot.append({"rule": "R1", "field": "state/工程进度.md",
                    "why": "台账声明了这一屏账，盘上却没有这个文件"})
    else:
        disk = SHEET.read_text(encoding="utf-8", errors="replace")
        if disk.strip() != sheet_text.strip():
            rot.append({"rule": "R1", "field": "state/工程进度.md",
                        "why": "盘上与按证据复算出来的内容不一致（有人手改了，或证据动了没重算）"})

    # R2 人写的日期 vs 机器日志前进
    raw_ip = str(led.get("in_progress") or "")
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw_ip)
    if m and logbook:
        try:
            written = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).astimezone()
        except ValueError:
            written = None
        if written is not None:
            age_h = (at - written).total_seconds() / 3600.0
            advanced = sum(1 for r in logbook if r["at"] > written)
            if age_h > INPROGRESS_MAX_AGE_H and advanced >= LOGBOOK_ADVANCE_TRIGGER:
                rot.append({"rule": "R2", "field": "in_progress",
                            "why": "「现在在做」停在 %s（%.1f 小时前），而机器日志此后已前进 %d 笔"
                                   " ⇒ 注入给模型的不是现在，是那天的快照"
                                   % (m.group(0), age_h, advanced)})
    else:
        rot.append({"rule": "R2", "field": "in_progress",
                    "why": "`in_progress` 里没有 `YYYY-MM-DD` 日期，无法判新旧（时间点是 Owner 明确要的）"})

    # R3 写手节缺失
    if not writer:
        rot.append({"rule": "R3", "field": "_写手",
                    "why": "台账没有 `_写手` 节 ⇒ 又退化成手工账，没人能判它烂没烂"})

    # R4 写手自己没人调
    checked = parse_any(writer.get("checked_at") or "")
    if checked is None:
        rot.append({"rule": "R4", "field": "_写手.checked_at",
                    "why": "没有 `checked_at` ⇒ 不知道写手有没有跑过"})
    elif (at - checked) > timedelta(hours=STALE_HOURS):
        rot.append({"rule": "R4", "field": "_写手.checked_at",
                    "why": "写手上次跑在 %s（超过 %d 小时）⇒ 驱动没接上（P8）"
                           % (stamp(checked), STALE_HOURS)})

    fresh = {
        "writer": "tools/codex-scripts/ledger-refresh.py",
        "口径": "人写字不代笔；只复算有证据的那一半。rot 非空 = 账在烂，不许当提醒读",
        "checked_at": stamp(at),
        "sections": sections,
        "工程进度.md": {"sha16": sha16(sheet_text), "rows": len(sheet_rows)},
        "rot": rot,
    }
    # 「声明值」与实盘对齐（这一节原先手填，现在由写手对齐；sha 变了才动 updated）
    prev_sheet_sha = (declared.get("sha16") if isinstance(declared, dict) else None) or ""
    sheet_changed = prev_sheet_sha != fresh["工程进度.md"]["sha16"]
    led["工程进度一屏账"] = {
        "updated": stamp(at) if (sheet_changed or not declared.get("updated"))
                   else declared.get("updated"),
        "行数": fresh["工程进度.md"]["rows"],
        "位置": "state/工程进度.md（人读一屏）",
        "sha16": fresh["工程进度.md"]["sha16"],
        "_口径": "只写有真证据的行；没证据写未验；每行带证据与缺口",
        "写手": "tools/codex-scripts/ledger-refresh.py（本节数字由写手对齐，不手填）",
    }
    return rot, fresh, moved, sheet_rows


# ── 主流程 ────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="台账写手 / 腐烂判据")
    ap.add_argument("--check", action="store_true", help="只读判据（不写盘）· rot 非空 = 非零退出")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    at = now_local()
    if not LEDGER.is_file():
        print("FAIL 台账不存在：%s" % LEDGER)
        return 1
    led = load_ledger()
    logbook = load_logbook()
    rot, fresh, moved, sheet_rows = rotate(led, logbook, at)
    sheet_text, _rows = render_sheet(led, logbook, at)

    if a.check:
        rows = [
            ("W1 台账可解析", True, "顶层 %d 键 · log %d 笔" % (len(led), len(led.get("log") or []))),
            ("W2 证据源在位", LOGBOOK.is_file(),
             "logbook %s 笔 · 最新 %s" % (
                 len(logbook), stamp(logbook[-1]["at"]) if logbook else "（读不到）")),
            ("W3 一屏账在位且与证据一致", not any(r["rule"] == "R1" for r in rot),
             str(SHEET) + ("（在）" if SHEET.is_file() else "（缺）")),
            ("W4 人写字没停在旧日期（≤%dh）" % INPROGRESS_MAX_AGE_H,
             not any(r["rule"] == "R2" for r in rot),
             "「现在在做」= %s" % str(led.get("in_progress") or "")[:60]),
            ("W5 写手节在位", not any(r["rule"] == "R3" for r in rot),
             "_写手 %s" % ("在" if isinstance(led.get("_写手"), dict) else "缺")),
            ("W6 写手 24h 内跑过", not any(r["rule"] == "R4" for r in rot),
             str((led.get("_写手") or {}).get("checked_at") or "（无）")),
        ]
        bad = [r for r in rows if not r[1]]
        if a.json:
            print(json.dumps({"ok": not bad and not rot, "rows": rows, "rot": rot},
                             ensure_ascii=False, indent=1))
        else:
            print("=== 台账写手与一屏账 · 判据 ===")
            for name, ok, now in rows:
                print("%s %-34s %s" % ("PASS" if ok else "FAIL", name, now))
            if rot:
                print("--- 腐烂项 %d 条（这**不是提醒**）---" % len(rot))
                for r in rot:
                    print("  [%s] %s: %s" % (r["rule"], r["field"], r["why"]))
                print("⇒ 修：py -3.14 tools/codex-scripts/ledger-refresh.py")
            print("判据 PASS %d · FAIL %d ｜ 腐烂项 %d"
                  % (len(rows) - len(bad), len(bad), len(rot)))
        return 0 if (not bad and not rot) else 1

    # ── 写手模式 ──
 # 2026-10-18 三次自纠（全是"顺序/口径"错，不是笔误 —— 记在这里防下一版又踩）：
    #   ① `rot` 原先在写一屏账**之前**算 ⇒ 首跑把「文件不存在」存进 `_写手.rot`，
    #      下次读账的人看到的是**已经不成立**的腐烂项（本仓 F15/F16/F17 栽的就是"账比事实旧"）。
    #      ⇒ 先落一屏账，**再**复算 rot。
    #   ② `updated_at` 原先靠"sha 变了"判断，而首跑没有上一版 sha ⇒ 人明明改了 in_progress，
    #      `updated_at` 却纹丝不动 ⇒ **假陈旧**。⇒ 改成**从证据派生**。
    #   ③【房间排练当场抓到的】上面两条修完之后，写手仍要**跑两遍才收敛**：
    #      一屏账先用**旧** `updated_at` 渲染落盘，之后才把 `updated_at` 改成新值
    #      ⇒ 盘上那一页立刻相对新证据"陈旧"，`--check` 立刻判 R1 红。
    #      生产上没暴露，是因为上一轮的跑法顺序刚好把它盖住了（假绿）。
    #      ⇒ 定稿顺序（一步收敛，可证幂等）：
    #         算人写字节 sha → 定 `updated_at` → **写进内存** → 渲染一屏账 → 落盘 → 复算 rot → 写台账
    #      判据就是本函数自己的 C2/C3：**写完立刻 --check 必须绿，再跑一次一屏账 sha 不许变。**
    SHEET.parent.mkdir(parents=True, exist_ok=True)

    # 1) 人写字节的 sha 与 changed_at（rotate 里同一套逻辑，这里先算出来）
    prev_sections = ((led.get("_写手") or {}).get("sections")
                     if isinstance((led.get("_写手") or {}).get("sections"), dict) else {})
    sections, moved = {}, []
    for key in HUMAN_SECTIONS:
        h = sha16(led.get(key))
        old = prev_sections.get(key) or {}
        changed_at = old.get("changed_at")
        if old.get("sha16") != h or not changed_at:
            changed_at = stamp(at)
            if old.get("sha16") is not None and old.get("sha16") != h:
                moved.append(key)
        sections[key] = {"sha16": h, "changed_at": changed_at}

    # 2) 先定 updated_at 并写进内存（渲染要读它）
    cands = [parse_any(sections[k].get("changed_at") or "") for k in HUMAN_SECTIONS]
    cands += [parse_any(str(r.get("at") or "")) for r in (led.get("log") or [])[-1:]]
    cands = [c for c in cands if c is not None]
    led["updated_at"] = stamp(max(cands) if cands else at)

    # 3) 渲染 → 落盘（此后盘上内容与证据一致）
    sheet_text, _rows = render_sheet(led, logbook, at)
    atomic_write(SHEET, sheet_text)

    # 4) 复算 rot（此时一屏账已在盘上且内容自洽）+ 组装 _写手
    rot, fresh, _moved2, sheet_rows = rotate(led, logbook, at)
    fresh["sections"] = sections          # changed_at 以第 1 步为准（rotate 会重算一遍，取同一份）
    led["_写手"] = fresh
    led.setdefault("_口径", "")
    atomic_write(LEDGER, json.dumps(led, ensure_ascii=False, indent=1) + "\n")

    print("=== 台账写手 ===")
    print("一屏账已重算 → %s（%d 行 · %d 字节）" % (SHEET, fresh["工程进度.md"]["rows"],
                                                len(sheet_text.encode("utf-8"))))
    print("台账已落盘 → %s" % LEDGER)
    print("`updated_at` = %s（派生自 max(log 末笔, 人写字节 changed_at)，不是跑一次就刷一次）"
          % led["updated_at"])
    if moved:
        print("  本次人改过的节：%s" % "、".join(moved))
    else:
        print("  本次人写字节无变化（写手只对齐派生那一半）")
    print("本节快照：" + " · ".join("%s=%s" % (k, v["sha16"]) for k, v in
                                   sorted(fresh["sections"].items())))
    if rot:
        print("--- 仍有腐烂项 %d 条 ---" % len(rot))
        for r in rot:
            print("  [%s] %s: %s" % (r["rule"], r["field"], r["why"]))
        print("（R2 这类要人补：把「现在在做」改成今天的真实进度，写手不代笔）")
    else:
        print("腐烂项 0 · 复跑判据：py -3.14 tools/codex-scripts/ledger-refresh.py --check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
