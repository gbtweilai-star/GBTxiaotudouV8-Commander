#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把台账「现在在做」改成本轮真实进度（人写字节，写手不代笔，所以由本件来写）。

只改 `in_progress` 一个字段，其余一字不动；改完再跑一次 ledger-refresh.py
让它复算 sha16 / changed_at / rot。
"""
import json
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

PATH = r"C:\Users\ADMIN\Desktop\GBT小土豆V8\state\排查台账.json"

TEXT = (
    "2026-10-22：**开机自检 45 步 / 红 0 全绿（43.3 秒）**；页面卡死的两个真因已钉死。"
    "① 冷启动真因 = RunPod 端点 `workersMin=0` + `idleTimeout=5s`（每轮回收 worker，实测 92–300 秒）"
    "⇒ 已改 `workersMin=1` / `idleTimeout=600`，实测首字 0.5–1.5s、整轮 0.8–2.0s（`lane-doctor.py` G1–G10 十条判据，"
    "已挂进 `boot-selfcheck.py`，`--quick` 跳过 / `--gate` 离线不判红）；"
    "② 页面转圈真因 = 宿主 `deepseek-flash` 的 `maxTokens=256000` 撞 1M 上下文墙"
    "（账本原话 requested 1053232 > 1048576，第 118/135/154/179 轮四次）⇒ 已定 `maxTokens=32000` 并留痕；"
    "③ 本轮清掉的存量红：装机副本漂移（34 件逐字节同步）· 编码守门（38 件补守门 → 新增违规 0）· "
    "触手主干六腿（`cap-pages.py` 生成 342 页，L5 断连 308→**0**，341/341 六腿齐）· 通电秒达（缺腿 0、真调用 14.3ms / 预算 500）· "
    "覆盖无死角且新鲜（`coverage_matrix.py sweep`，6.37 万单元）· 多域监控驱动轮（`project_drift` 基线 `from_pack=false` 现场重建）；"
    "④ 规程：`docs/模型车道运维.md`；订正 `GW_AUTH`（refs，Worker 网关钥）与 HKCU `GBT_GATEWAY_TOKEN`（本机能力网关 X-GBT-Token）是**两把钥**，互抄必 401。"
    "⑤ P8 收口：`monitor-loop` 接上**每 6 小时一次的重烤驱动**（`brain-feed --out` + `bake-all-pages`），"
    "并且判「真落盘」看数据里的 `at` 不看退出码 —— 主脑数据 41h → **0.0h**，快照页过期 0 个。"
    "⑥ 判据收口：框架自改门**重立基线**（2026-10-22T05:14:08）+ 223 件历史遗留**明示登记**"
    "（`state/framework-passports-legacy.json`，不是补齐）· **咬合力反证**通过（改源件不记账必红、写回必绿）· "
    "F19 装了**满载红灯猎手**（4 负载×5 轮全绿，回执 `state/load-red-hunt.json`，失败用例名会逐条记），"
    "**需人读 2 → 1**（只剩 F3 等 D4 甲/乙拍板）· 交付声明 **15/15**（镜像排练 9/9，票 grant-1792621291023；"
    "该绿是树指纹绑定的，下次改树即失效）。"
    "⑦ **判据/驱动又收了口（2026-10-22 收尾）**：开机自检 **45 → 46 步**（新增「规程缺口量具可复跑」——"
    "不是判缺口=0，是判**尺子还能跑**）· `monitor-loop` 接上 **F19 满载红灯猎手（24h 一次）**，"
    "并且**真跑了一次**验证驱动（150 秒 / 3 轮 × 4 负载 / 回执 at 已刷新，判口径是看 `at` 变没变、不看 rc）· "
    "`spec-gap-scan.py` 把台账里**无法复跑的「5 处」**换成现算读数：**341 位 / 30 域 / 缺口 149 位** · "
    "`d7-skill-boundary.py` 把技能面 235 减到 **该补 0**（177 全是例外：料/上游/重复）· "
    "`legacy-grouping.py` 量出 F22 那 223 件里 **221 件仍在役**（所以**不标 accepted-legacy**）。"
    "本段共**自纠 7 次**（根/名字/容器/是否在役/量法各异），每次都留痕在原工具注释里。"
    "⑧ **风险面收口 + 自纠进模式表**：`caps-write-gate-census.py`（341 位四档：只读 212 · 模块有写口 41 · 需授权 20 · 分派无 import 68）"
    "→ `cap-write-reach.py`（从分派入口做仓内调用图可达性：**可达 27 · 不可达 12 · 入口未解析 2**）"
    "→ 再逐个看写盘函数签名（`inventory.scan(fix=False)` / `selfscan.scan(autofix=False)` / `hygiene.scan(fix=False)` / "
    "`cross_scan` 内部 fix=False）⇒ **默认参数下会真动手的可疑面收敛到一类、目前为 0**。"
    "另把今天 10 次自纠写成两条根因模式：**P33 量具自身的两类系统错**（过滤写在循环外 / 读不到当结论 / 裸名当路径 / 对象当键）"
    "· **P34 粒度与单位当结论**（名字 vs 目录 / 模块级 vs 可达 / 语法可达 vs 默认参数可达）。根因模式表现 **33 条**。"
)


def main():
    with open(PATH, encoding="utf-8") as fh:
        j = json.load(fh)
    old = j.get("in_progress")
    if old == TEXT:
        print("in_progress 已是本轮文本，未改")
        return 0
    j["in_progress"] = TEXT
    # 🔴 2026-10-22 改（当天真栽的跟头）：这里原来直接 `open(PATH,"w")`，对这份台账会抛
    #    `OSError: [Errno 22] Invalid argument` —— 宿主正盯着它（注入会话头）。
    #    同一次操作改成「临时件 + os.replace」当场成功。台账这类被别人持有的文件只许原子替换。
    import os
    import tempfile
    fd, tmp = tempfile.mkstemp(prefix="ledger-", suffix=".json", dir=os.path.dirname(PATH))
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(j, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, PATH)
    print("in_progress 已更新 · 旧长度 %d 字 → 新长度 %d 字" % (len(old or ""), len(TEXT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
