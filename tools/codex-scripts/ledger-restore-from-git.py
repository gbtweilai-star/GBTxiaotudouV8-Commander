#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从 git HEAD 恢复台账（原子替换，绝不 open(目标,'w')）+ 补回丢的那一笔 + 写本轮进度。

2026-10-22 事故：一次探针用 `open(path,'w')` 试写，把 160,588 字节的台账截成 0 字节。
恢复源 = git HEAD 的 `state/排查台账.json`（86,072 字节 · 结构完整 · 17 键），
丢的是 2026-10-11 → 10-18 之间的增量（1 笔 log + 那句 10-18 的「现在在做」，后者的原文本轮手握）。
"""
import json
import os
import subprocess
import sys
import tempfile

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = r"C:\Users\ADMIN\Desktop\GBT小土豆V8"
LEDGER = os.path.join(ROOT, "state", "排查台账.json")

IN_PROGRESS = (
    "2026-10-22：**页面卡死的两个真因已钉死并修好 · 模型车道立成常设判据**。"
    "① 冷启动真因 = RunPod 端点 `workersMin=0` + `idleTimeout=5s`（每轮回收 worker，实测 92–300 秒）"
    "⇒ 已改 `workersMin=1` / `idleTimeout=600`，实测首字 0.5–1.5s、整轮 0.8–2.0s；"
    "② 页面转圈真因 = 宿主 `deepseek-flash` 的 `maxTokens=256000` 撞 1M 上下文墙"
    "（账本原话 requested 1053232 > 1048576，第 118/135/154/179 轮四次）⇒ 已定 `maxTokens=32000` 并留痕；"
    "③ 新增唯一入口 `tools/codex-scripts/lane-doctor.py`（G1–G10 十条判据）+ `docs/模型车道运维.md`，"
    "已挂进 `boot-selfcheck.py`（`--quick` 跳过 · `--gate` 离线不判红 · 实测 PASS 10/10）；"
    "④ 订正 `GW_AUTH`（refs，Worker 网关钥）与 HKCU `GBT_GATEWAY_TOKEN`（本机能力网关 X-GBT-Token）是**两把钥**，互抄必 401。"
)

LOST_LOG = {
    "at": "2026-10-18T05:42:58+07:00",
    "text": "**改走隔离房间**：全量扫描 462,429 件 + 清旧两笔已落地；台账写手与一屏账改为"
            "「房间 room=ledger-writer-20261018 里跑绿 → 一次性原子替换」，生产面回滚到干净基线。",
    "note": "本条在 2026-10-22 恢复时按原文补回（原文件被截断后从 git HEAD 还原，此笔为增量内容）。",
}


def main():
    # 1) 从 git HEAD 取原文
    raw = subprocess.run(["git", "show", "HEAD:state/排查台账.json"], cwd=ROOT,
                         capture_output=True, check=True).stdout.decode("utf-8")
    led = json.loads(raw)
    print("恢复源：git HEAD · %d 字节 · %d 键 · updated_at=%s"
          % (len(raw), len(led), led.get("updated_at")))

    # 2) 补回丢掉的那一笔（只在没有它时补）
    log = led.get("log")
    if not isinstance(log, list):
        log = []
        led["log"] = log
    if not any(str(e.get("at")) == LOST_LOG["at"] for e in log if isinstance(e, dict)):
        log.append(dict(LOST_LOG))
        print("已补回 2026-10-18 那一笔 log（原文件里最后一笔增量）")

    # 3) 写本轮「现在在做」（人写字节，写手不代笔）
    led["in_progress"] = IN_PROGRESS

    # 4) 原子替换：写临时件 → os.replace，全程不 open(目标,'w')
    fd, tmp = tempfile.mkstemp(prefix="ledger-", suffix=".json", dir=os.path.dirname(LEDGER))
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(led, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    # 先留一份备份（这份备份就是"下一次被截断时的救生圈"）
    if os.path.getsize(LEDGER) > 0:
        bak = LEDGER + ".bak-before-restore"
        with open(LEDGER, "rb") as src, open(bak, "wb") as dst:
            dst.write(src.read())
    os.replace(tmp, LEDGER)
    print("已原子替换 → %s（%d 字节）" % (LEDGER, os.path.getsize(LEDGER)))

    # 5) 自检：能解析 + 关键节在
    with open(LEDGER, encoding="utf-8") as fh:
        chk = json.load(fh)
    print("自检：可解析 · 键 %d · log %d 笔 · open_faults %d · not_done %d · owner_decisions %d"
          % (len(chk), len(chk.get("log") or []), len(chk.get("open_faults") or []),
             len(chk.get("not_done") or []), len(chk.get("owner_decisions") or [])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
