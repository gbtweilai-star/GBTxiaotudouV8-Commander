import pathlib
import sys
import time

REPO = pathlib.Path(r"C:\Users\Lenovo E14 Gen 5\Documents\deepseek-harness\default-workspace\GBTxiaotudouV8-Commander\GBTxiaotudouV8-Commander-main")
sys.path.insert(0, str(REPO))
from gbt_allinone import memory_bank as MB

fails = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name + (" · " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


base = timed = time.strftime("%Y-%m-%dT%H:%M:%S+07:00")
ok1 = MB.store(at=base, source="test", actor="tester", action="note", target="mem",
               detail="记忆完整性测试：全部必填字段都在", evidence_sha256="x" * 64,
               confidence=0.9, version=1, parent_hash="GENESIS")
check("完整入库", ok1.get("ok") is True, ok1)
bad = MB.store(at="", source="t", actor="t", action="a", target="t", detail="d",
               evidence_sha256="x", confidence=0.1, version=1, parent_hash="g")
check("缺字段拒收", bad.get("ok") is False and "缺" in bad.get("reason", ""), bad)
badt = MB.store(at="2026/11/02", source="t", actor="t", action="a", target="t",
                detail="d", evidence_sha256="x", confidence=0.1, version=1, parent_hash="g")
check("时间格式拒收", badt.get("ok") is False and "ISO8601" in badt.get("reason", ""), badt)
r = MB.recall("完整性测试")
check("秒查命中", r.get("ok") and r.get("returned", 0) >= 1, {k: r.get(k) for k in ("returned", "total", "coverage")})
check("覆盖率字段", "coverage" in r and "complete" in r)
# 90 天保留：插一条 100 天前的，gc dry-run 只报数；confirm 才删，且不删新记录
old = time.strftime("%Y-%m-%dT%H:%M:%S+07:00", time.localtime(time.time() - 100 * 86400))
MB.store(at=old, source="test", actor="tester", action="old", target="mem",
         detail="100 天前的旧记忆", evidence_sha256="y" * 64, confidence=0.5,
         version=1, parent_hash="GENESIS")
g1 = MB.gc(confirm=False)
check("gc 默认 dry-run", g1.get("dry_run") is True and g1.get("would_delete", 0) >= 1, g1)
g2 = MB.gc(confirm=True)
check("gc 只删旧记录", g2.get("deleted", 0) >= 1 and g2.get("deleted", 0) <= 2, g2)
r2 = MB.recall("完整性测试")
check("新记录未被删", r2.get("returned", 0) >= 1, r2.get("returned"))

print("ALL OK —— 记忆库：全字段入库/拒收/秒查覆盖/90天清理 全过" if not fails else "FAILED: %s" % fails)
sys.exit(1 if fails else 0)
