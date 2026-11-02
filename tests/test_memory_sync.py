import pathlib
import sys
import time

REPO = pathlib.Path(r"C:\Users\Lenovo E14 Gen 5\Documents\deepseek-harness\default-workspace\GBTxiaotudouV8-Commander\GBTxiaotudouV8-Commander-main")
sys.path.insert(0, str(REPO))
from gbt_allinone import memory_sync as MS
from gbt_allinone import memory_bank as MB

_tmp = REPO / "state" / "tmp"
_tmp.mkdir(parents=True, exist_ok=True)
MB.DB = _tmp / "test-memory-sync.db"
MS.BUS = _tmp / "test-memory-bus.jsonl"
for _f in (MB.DB, MS.BUS):
    try:
        _f.unlink()
    except Exception:
        pass

fails = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name + (" · " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


now = time.strftime("%Y-%m-%dT%H:%M:%S+07:00")
r1 = MS.write("agent-A", "GENESIS", at=now, source="test", actor="A", action="write1",
              target="mem", detail="同步层测试：第一条", evidence_sha256="a" * 64,
              confidence=0.9)
check("第一条写入", r1.get("ok") is True, r1)
r2 = MS.write("agent-B", r1.get("chain"), at=now, source="test", actor="B",
              action="write2", target="mem", detail="同步层测试：第二条", evidence_sha256="b" * 64,
              confidence=0.9)
check("链式写入", r2.get("ok") is True, r2)
r3 = MS.write("agent-C", "GENESIS", at=now, source="test", actor="C", action="conflict",
              target="mem", detail="并发冲突写入", evidence_sha256="c" * 64, confidence=0.9)
check("过期 parent 被拒", r3.get("ok") is False and r3.get("conflict") is True, r3)
ev = MS.subscribe(0)
check("广播事件", ev.get("count", 0) >= 2 and any(e.get("client") == "agent-A" for e in ev["events"]), ev.get("count"))
rp = MS.recall("同步层测试")
check("秒查覆盖", rp.get("returned", 0) >= 2 and rp.get("complete") is True, {k: rp.get(k) for k in ("returned", "coverage")})

print("ALL OK —— 记忆同步：乐观锁/链式版本/触手广播/秒查 全过" if not fails else "FAILED: %s" % fails)
sys.exit(1 if fails else 0)
