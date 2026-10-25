#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""执行留痕器 —— 每一步逐字记，报告可复算。

Owner 2026-09-22：
  「不管是你还是触手，每次报告必须精细到每一步是怎么执行的都要打印出来，
    证明没有假执行等一系列的代码错误问题」

═══ 为什么要有这个东西 ═══
  报告里写"我扫了 8529 个文件"，读者**无法验证**。
  报告里写"我跑了 `<这条命令>`，它返回 `<这段输出>`，退出码 0" —— 读者**能复算**。

  差别不在诚实与否，在**可证伪性**：
    · 不可证伪的报告 = 只能选择信或不信 ⇒ 假执行与真执行长得一样
    · 可证伪的报告 = 任何人重跑一遍就知道 ⇒ 假执行当场露馅

  ⇒ 本模块把"每一步"落成结构化记录，报告时逐条打印。

═══ 记录什么（六项，缺一不算一步）═══
    ① 序号       —— 可引用（"见 STEP 007"）
    ② 动作逐字   —— 命令/代码原文，**不许概括**
    ③ 启动时刻   —— 时间戳
    ④ 退出码     —— 不是"成功/失败"，是真实数字
    ⑤ 产出摘要   —— stdout/stderr 的头尾 + **sha256**（全文可另行落盘核对）
    ⑥ 判定       —— ok / fail / skip，**skip 必须带理由**

═══ 铁律 ═══
  · **失败也记** —— 崩溃、超时、非零退出，全部原样入账。不许只留成功的。
  · **skip 要理由** —— 没做就说没做，写清为什么。
  · **摘要不是全文** —— 长输出落盘 + 记 sha256；报告里给头尾，让人能去核对。
  · 本模块**只写 .scratch/ 下的留痕文件**，不碰生产面。
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRACE_DIR = ROOT / ".scratch" / "_traces"
HEAD = 240          # 报告里显示的输出头
TAIL = 240          # 报告里显示的输出尾


class Trace:
    """一次作业的执行留痕。用法：

        t = Trace("扫主机安全")
        t.step("跑六层扫描", ["py", "-3.14", "-m", "gbt_allinone.tools.host_security_scan"])
        t.skip("病毒库比对", "需要外部病毒库，本机没有")
        print(t.report())
    """

    def __init__(self, title: str, actor: str = "AI"):
        self.title = title
        self.actor = actor
        self.t0 = time.time()
        self.steps: list = []
        TRACE_DIR.mkdir(parents=True, exist_ok=True)
        self.stamp = time.strftime("%Y%m%dT%H%M%S")
        self.raw_dir = TRACE_DIR / f"{self.stamp}-raw"
        self.raw_dir.mkdir(exist_ok=True)

    # ── 记一次真实执行的命令 ──
    def step(self, what: str, cmd: list, cwd: str | None = None,
             timeout: int = 1800, note: str = "") -> dict:
        i = len(self.steps) + 1
        started = time.strftime("%Y-%m-%dT%H:%M:%S")
        t1 = time.time()
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                               cwd=cwd or str(ROOT), encoding="utf-8", errors="replace")
            rc, out, err = r.returncode, r.stdout or "", r.stderr or ""
        except subprocess.TimeoutExpired:
            rc, out, err = -1, "", f"TimeoutExpired({timeout}s)"
        except Exception as e:                                    # noqa: BLE001
            rc, out, err = -2, "", f"{type(e).__name__}: {str(e)[:200]}"
        dur = round(time.time() - t1, 2)
        blob = f"CMD: {' '.join(map(str, cmd))}\nEXIT: {rc}\n--- STDOUT ---\n{out}\n--- STDERR ---\n{err}"
        sha = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        rawf = self.raw_dir / f"step{i:03d}.txt"
        rawf.write_text(blob, encoding="utf-8")
        rec = {"i": i, "kind": "run", "what": what, "cmd": [str(c) for c in cmd],
               "started": started, "exit": rc, "dur_s": dur,
               "out_head": out[:HEAD], "out_tail": out[-TAIL:] if len(out) > HEAD else "",
               "err_head": err[:HEAD], "sha256": sha, "raw": str(rawf.relative_to(ROOT)),
               "verdict": "ok" if rc == 0 else "fail", "note": note}
        self.steps.append(rec)
        return rec

    # ── 记一次"没做"，必须给理由 ──
    def skip(self, what: str, why: str) -> dict:
        rec = {"i": len(self.steps) + 1, "kind": "skip", "what": what,
               "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "verdict": "skip", "why": why}
        self.steps.append(rec)
        return rec

    # ── 记一次"直接读"（不经子进程的动作，例如读文件、调函数）──
    def fact(self, what: str, how: str, got: str) -> dict:
        """`how` 要写清**怎么得到的**（跑了什么/读了哪个文件哪一行）。"""
        rec = {"i": len(self.steps) + 1, "kind": "fact", "what": what, "how": how,
               "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "got": str(got)[:HEAD * 2], "verdict": "ok"}
        self.steps.append(rec)
        return rec

    # ── 出报告：**逐步打印，不是概括** ──
    def report(self) -> str:
        n_ok = sum(1 for s in self.steps if s["verdict"] == "ok")
        n_fail = sum(1 for s in self.steps if s["verdict"] == "fail")
        n_skip = sum(1 for s in self.steps if s["verdict"] == "skip")
        L = []
        L.append("═" * 78)
        L.append(f"执行留痕 · {self.title} · 执行者 {self.actor}")
        L.append(f"起 {time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(self.t0))} · "
                 f"共 {len(self.steps)} 步 · ok {n_ok} · fail {n_fail} · skip {n_skip} · "
                 f"耗时 {round(time.time()-self.t0,1)}s")
        L.append("═" * 78)
        for s in self.steps:
            L.append("")
            L.append(f"[STEP {s['i']:03d}] {s['started']}  {s['what']}")
            if s["kind"] == "run":
                L.append(f"    ▸ 逐字命令: {' '.join(s['cmd'])}")
                L.append(f"    ▸ 退出码  : {s['exit']}   (耗时 {s['dur_s']}s)")
                if s.get("out_head"):
                    L.append(f"    ▸ 输出头  : {s['out_head'].strip()[:HEAD]}")
                if s.get("out_tail"):
                    L.append(f"    ▸ 输出尾  : {s['out_tail'].strip()[-TAIL:]}")
                if s.get("err_head"):
                    L.append(f"    ▸ stderr  : {s['err_head'].strip()[:HEAD]}")
                L.append(f"    ▸ 全文sha : {s['sha256'][:32]}…  原文: {s['raw']}")
                L.append(f"    ▸ 判定    : {'✔ ok' if s['verdict']=='ok' else '✘ fail'}")
                if s.get("note"):
                    L.append(f"    ▸ 备注    : {s['note']}")
            elif s["kind"] == "skip":
                L.append(f"    ▸ **没做**，理由: {s.get('why')}")
            else:
                L.append(f"    ▸ 怎么得到: {s.get('how')}")
                L.append(f"    ▸ 读数    : {str(s.get('got'))[:HEAD]}")
        L.append("")
        L.append("─" * 78)
        L.append("**复算方式**：上面每条 `逐字命令` 都可以原样重跑；")
        L.append(f"完整输出落在 `{self.raw_dir.relative_to(ROOT)}/stepNNN.txt`，sha256 已记 —— 可逐个核对。")
        L.append("**没做的**在报告里标 `没做` 并给了理由 —— 没扫到 ≠ 没问题。")
        L.append("─" * 78)
        return "\n".join(L)

    def save(self) -> Path:
        p = TRACE_DIR / f"{self.stamp}-{self.title.replace(' ', '_')[:40]}.txt"
        p.write_text(self.report(), encoding="utf-8")
        return p


# ═══ 自查：本模块自己能不能过逐行穷尽扫描 ═══
def _selftest() -> int:
    t = Trace("留痕器自检", actor="trace")
    t.step("跑逐行穷尽扫描（只看本文件）",
           [sys.executable, "-m", "gbt_allinone.tools.code_exhaustive_scan", "--json"])
    t.skip("病毒库比对", "需要外部病毒库，本机没有 —— 如实记，不当成已做")
    print(t.report())
    return 0


if __name__ == "__main__":
    sys.exit(_selftest())
