# -*- coding: utf-8 -*-
"""④ 自省真正落盘（《待落刀登记.md》§二十 #4）的回归。

病根：reflect() 只返回一个 `log_ref: "root_fix.work_log"` **字符串引用**，从不调用它
⇒「自省发现了什么」只活在内存里，进程一退就没了，违背红线④「问完必须沉淀」。

验七件事：
  ① 只读口（law / reflections / short_boards）**不写盘**（前后 work_log 行数不变）
  ② `persist` 真的写进 store/work_log.jsonl（行数 +1，内容含缺口）
  ③ 落盘回执如实（landing / persisted / receipt）
  ④ 重复 persist 被 root_fix 的去重窗口拦下，且**如实报 duplicate**（不是假成功）
  ⑤ 非法 gap 类型被拒（不许把不认识的缺口写进去）
  ⑥ 无缺口时不写、如实报 why
  ⑦ 只读口的 `persisted_reflections` 计数跟着走（"引用不是写入"这件事看得见）

全程用临时 GBT_STORE_DIR，**不碰真 store**。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CHILD = r'''
import json, os, sys
sys.path.insert(0, r"%s")
from gbt_allinone.tools import meta_cognition as MC

WL = os.path.join(os.environ["GBT_STORE_DIR"], "work_log.jsonl")

def wl_lines():
    try:
        return [l for l in open(WL, encoding="utf-8") if l.strip()]
    except FileNotFoundError:
        return []

out = {}
out["before_lines"] = len(wl_lines())

# ① 只读口不写盘
out["law"] = MC.run("law")
out["reflections0"] = MC.run("reflections")
out["short0"] = MC.run("short_boards")
out["after_readonly_lines"] = len(wl_lines())

# ②③ persist 真写
out["reflect"] = MC.run("reflect", task_id="t-1", scope="brain",
                        gaps=[{"type": "missing_context", "note": "缺 8080 端口上下文"},
                              {"type": "uncertain", "note": "不确定该用哪套密钥路径"}])
out["persist"] = MC.run("persist", task_id="t-1", scope="brain")
out["after_persist_lines"] = len(wl_lines())

# ④ 重复 persist → 去重
out["persist_again"] = MC.run("persist", task_id="t-1", scope="brain")
out["after_dup_lines"] = len(wl_lines())

# ⑤ 非法 gap 类型
out["bad_type"] = MC.run("persist", gaps=[{"type": "not_a_real_type", "note": "x"}])

# ⑥ 无缺口
MC2 = MC.MetaCognitionLoop()
out["empty"] = MC2.persist_reflections()

# ⑦ 计数可见
out["law_after"] = MC.run("law")

# work_log 真内容
rows = []
for l in wl_lines():
    try: rows.append(json.loads(l))
    except Exception: pass
out["work_log_rows"] = rows
print(json.dumps(out, ensure_ascii=False, default=str))
''' % str(ROOT)

tmp = tempfile.mkdtemp(prefix="gbt_meta_persist_")
env = dict(os.environ, GBT_STORE_DIR=tmp, PYTHONIOENCODING="utf-8")
cp = subprocess.run([sys.executable, "-c", CHILD], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", env=env, timeout=180)
if cp.returncode != 0:
    print("子进程失败:", cp.returncode)
    print(cp.stdout[-2000:])
    print(cp.stderr[-2000:])
    sys.exit(1)

d = json.loads(cp.stdout.strip().splitlines()[-1])

ok = fail = 0


def chk(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print("  ✓ %-50s %s" % (name, detail))
    else:
        fail += 1
        print("  ✗ %-50s %s" % (name, detail))


print("① 只读口不写盘")
chk("law/reflections/short_boards 前后行数不变",
    d["before_lines"] == d["after_readonly_lines"] == 0,
    "%d -> %d" % (d["before_lines"], d["after_readonly_lines"]))
chk("law 报明唯一写盘 op",
    d["law"].get("non_readonly_op", "").startswith("persist"),
    str(d["law"].get("non_readonly_op"))[:40])

print("\n②③ persist 真写 + 回执如实")
chk("reflect 记录成功", d["reflect"].get("ok") is True,
    "log_ref=%s" % d["reflect"].get("log_ref"))
chk("persist 后 work_log 行数 +1", d["after_persist_lines"] == 1,
    "%d -> %d" % (d["after_readonly_lines"], d["after_persist_lines"]))
p = d["persist"]
chk("persist ok 且 persisted=1", p.get("ok") is True and p.get("persisted") == 1,
    str(p.get("landing"))[:44])
chk("persist 报 readonly=False（它就是要写）", p.get("readonly") is False, "")
chk("回执带 receipt", isinstance(p.get("receipt"), dict), "")
rows = d["work_log_rows"]
chk("work_log 里真是 lesson 级且含缺口",
    bool(rows) and rows[-1].get("action") == "lesson"
    and "missing_context" in str(rows[-1].get("detail")),
    "action=%s" % (rows[-1].get("action") if rows else None))

print("\n④ 重复 persist 走去重窗口，且如实报")
pa = d["persist_again"]
chk("重复不增行", d["after_dup_lines"] == d["after_persist_lines"],
    "%d -> %d" % (d["after_persist_lines"], d["after_dup_lines"]))
chk("重复时如实报 duplicate（不假成功）",
    pa.get("ok") is True and pa.get("duplicate") is True and pa.get("persisted") == 0,
    "duplicate=%s persisted=%s" % (pa.get("duplicate"), pa.get("persisted")))

print("\n⑤⑥ 拒得住的")
chk("非法 gap 类型被拒", d["bad_type"].get("ok") is False
    and d["bad_type"].get("rule") == "unknown_gap_type",
    str(d["bad_type"].get("rule")))
chk("无缺口时不写、如实报 why",
    d["empty"].get("ok") is False and bool(d["empty"].get("why")),
    str(d["empty"].get("why"))[:44])

print("\n⑦ 计数跟着走（引用≠写入 这件事看得见）")
chk("law.persisted_reflections 从 0 变 1",
    d["law"].get("persisted_reflections") == 0
    and d["law_after"].get("persisted_reflections") == 1,
    "%s -> %s" % (d["law"].get("persisted_reflections"),
                  d["law_after"].get("persisted_reflections")))

import shutil  # noqa: E402
shutil.rmtree(tmp, ignore_errors=True)
print("\n" + "-" * 78)
print("通过 %d · 失败 %d" % (ok, fail))
sys.exit(0 if fail == 0 else 1)
