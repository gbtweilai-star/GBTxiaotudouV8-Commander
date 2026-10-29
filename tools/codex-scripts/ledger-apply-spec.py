#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按 spec 改台账（只支持两种安全动作）：改在册故障正文 / 追加一条待拍板。

为什么要有它：这段文字里有 `**`、反引号、中文引号，内联 python 在 PowerShell 里
反复被吃引号（同一个坑踩过三次）。把 spec 写成 JSON 文件，一次就对。

spec 形如：
{
  "fault_updates": {"F9": {"what": "...", "evidence": "...", "state": "..."}},
  "owner_decisions_add": [{"id": "D7", "ask": "...", "why": "..."}]
}

用法：py -3.14 tools/codex-scripts/ledger-apply-spec.py --spec state/ledger-spec.json
"""
import argparse
import json
import os
import sys
import tempfile
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEDGER = os.path.join(ROOT, "state", "排查台账.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    a = ap.parse_args()
    sp = os.path.join(ROOT, a.spec)
    raw = open(sp, encoding="utf-8").read()
    try:
        spec = json.loads(raw)
    except json.JSONDecodeError as e:
 # 2026-10-25 加（同一处我自己连错三次）：以前只抛一屏 traceback，
        #    真正的毛病是「字符串里用了 ASCII 双引号」——那种错在长中文句子里
        #    极难凭行号找到。现在**直接把出错位置前后各 40 字打出来**，
        #    并点名最常见的两种成因，让人一眼看见是哪个引号把字符串截断了。
        lo, hi = max(0, e.pos - 40), min(len(raw), e.pos + 40)
        around = raw[lo:hi].replace("\n", "⏎")
        print("spec JSON 解析失败：%s" % a.spec)
        print("  位置：line %d col %d（第 %d 字符）" % (e.lineno, e.colno, e.pos))
        print("  上下文：…%s…" % around)
        print("  最常见成因：① 字符串里用了 ASCII 双引号（改用「」）"
              "② 少逗号/多逗号 ③ 反斜杠没转义（Windows 路径写 \\\\）")
        return 2
    led = json.load(open(LEDGER, encoding="utf-8"))
    changed = []

    for fid, patch in (spec.get("fault_updates") or {}).items():
        hit = [f for f in (led.get("open_faults") or []) if str(f.get("id")) == fid]
        if not hit:
            print("跳过 %s：未清故障里没有这条" % fid)
            continue
        for k, v in patch.items():
            hit[0][k] = v
        changed.append("fault:" + fid)

 # 2026-10-25 加（从源头解决「没有起点」）：
    #    实测病根：`owner_decisions` / `open_faults` **写入时不留时间戳** ⇒ 事后只能
    #    靠 log 回推，而回推会撞号（`D6` 在不同编号体系里指过不同的事，见 logbook #286）。
    #    ⇒ 新增条目**当场盖章**：`asked_at` / `opened_at`（+ 谁写的）。
    #    这样以后新加的条目天生带权威时间，`≥` 下界只留给历史遗留。
    _STAMP = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    _BY = os.environ.get("GBT_LEDGER_ACTOR") or "ledger-apply-spec"

    for item in (spec.get("open_faults_add") or []):
        of = led.setdefault("open_faults", [])
        if any(str(x.get("id")) == str(item.get("id")) for x in of if isinstance(x, dict)):
            print("跳过 %s：已在未清故障里" % item.get("id"))
            continue
        if isinstance(item, dict):
            item.setdefault("opened_at", _STAMP)
            item.setdefault("opened_by", _BY)
        of.append(item)
        changed.append("open_fault:" + str(item.get("id")))

    for item in (spec.get("owner_decisions_add") or []):
        od = led.setdefault("owner_decisions", [])
        if any(str(x.get("id")) == str(item.get("id")) for x in od if isinstance(x, dict)):
            print("跳过 %s：已在待拍板里" % item.get("id"))
            continue
        if isinstance(item, dict):
            item.setdefault("asked_at", _STAMP)
            item.setdefault("asked_by", _BY)
        od.append(item)
        changed.append("decision:" + str(item.get("id")))

 # 2026-10-24 扩两动作（P9「账没有写手必烂」的直接病根）：
    # 本器原来只认「改故障 / 加待拍板」，**「今天做了什么」这条路根本没有写手**
    # ⇒ 只能手抠 `state/排查台账.json`，抠漏了账就停在旧日期上（本轮实例：
    # 本地权重接进 APP 这件事做完了却一个字没进主台账，主人因此以为没做）。
    #   · in_progress_set：整段替换 in_progress（字是人写的，本器只负责落对位置）
    #   · rounds_inc     ：顺带 +1 轮次（只在 in_progress 真换时算）
    #   · today_done_prepend：把今天的账插到**最前**（该数组的口径是最新在前）
 # 2026-10-24 扩：**结账也要有写手**。
    #    原来只能改故障正文、**不能结**（open_faults → closed_faults）⇒
    #    前提已垮、判据（probe）已经在催了，也只能手工搬 —— 迟早烂在账上（P9）。
    #    spec: "faults_close": {"F26": {"why": "...", "state": "...", "evidence": "..."}}
    for fid, meta in (spec.get("faults_close") or {}).items():
        of = led.setdefault("open_faults", [])
        hit = [f for f in of if str(f.get("id")) == fid]
        if not hit:
            print("跳过 %s：未清故障里没有这条（可能已结）" % fid)
            continue
        f = dict(hit[0])
        of.remove(hit[0])
        f["closed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        if meta.get("why"):
            f["closed_why"] = meta["why"]
        if meta.get("evidence"):
            f["evidence"] = meta["evidence"]
        f["state"] = meta.get("state") or ("已结（%s）" % f["closed_at"])
        led.setdefault("closed_faults", []).append(f)
        changed.append("closed:" + fid)

    ip = spec.get("in_progress_set")
    if ip:
        led["in_progress"] = ip
        changed.append("in_progress")
        if spec.get("rounds_inc"):
            led["rounds_done"] = int(led.get("rounds_done") or 0) + int(spec["rounds_inc"])
            changed.append("rounds_done+%d" % int(spec["rounds_inc"]))

    for text in (spec.get("today_done_prepend") or []):
        td = led.setdefault("today_done", [])
        if text in td:
            print("跳过重复的 today_done 条目")
            continue
        td.insert(0, text)
        changed.append("today_done")

    if not changed:
        print("没有可应用的动作")
        return 0

    led.setdefault("log", []).append({
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "what": "台账按 spec 更新：" + "、".join(changed),
        "text": "spec=%s ｜ 动作：%s" % (a.spec, "、".join(changed)),
        "note": "由 tools/codex-scripts/ledger-apply-spec.py 应用（原子替换）",
    })
    fd, tmp = tempfile.mkstemp(prefix="ledger-", suffix=".json", dir=os.path.dirname(LEDGER))
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(led, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, LEDGER)
    print("已应用：%s ｜ open_faults %d · owner_decisions %d"
          % ("、".join(changed), len(led.get("open_faults") or []), len(led.get("owner_decisions") or [])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
