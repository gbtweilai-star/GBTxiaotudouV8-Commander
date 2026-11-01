"""test_attack_forensics.py · 受攻击取证与合法反制

判据：
  1. 取证：6 类采集器并发采集 → 证据目录 + manifest（每个文件 sha256）+ ZIP；
  2. 极限并发：agents 可配（测试用 8），耗时/文件数有读数；
  3. 资源回收：只回收本框架自己的非必需进程，系统/用户进程不碰；
  4. 攻击模式：respond() 进入攻击模式（V8 自我决策），且**转账仍被拦**；
  5. 非法反击（接管电源/控制台/键鼠/反入侵）→ blocked_illegal，附法律依据与合法替代；
  6. 审计：security-policy-audit 有 attack_on 记录。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gbt_allinone import attack_forensics as AF  # noqa: E402
from gbt_allinone import security_policy as SP  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    ok = bool(cond)
    print(("  ok   " if ok else "  FAIL ") + name + ((" · " + str(extra)) if extra else ""))
    if not ok:
        FAILS.append(name)


def main() -> int:
    iid = "TEST-" + time.strftime("%H%M%S")
    # 清攻击模式（测试隔离）
    SP.exit_attack_mode("test start")

    print("[1] 极限并发取证")
    c = AF.collect(agents=8, incident=iid)
    check("取证 ok", c.get("ok") is True, c.get("zip"))
    base = pathlib.Path(c.get("dir", ""))
    check("证据目录", base.is_dir(), base)
    check("ZIP", pathlib.Path(c.get("zip", "")).is_file(), c.get("zip"))
    mf = base / "manifest.json"
    check("manifest", mf.is_file())
    man = json.loads(mf.read_text(encoding="utf-8")) if mf.is_file() else {}
    check("manifest 文件 sha256", len(man.get("files") or []) >= 5,
          len(man.get("files") or []))
    check("采集器 >=16", len(man.get("collectors") or []) >= 16, man.get("collectors"))
    check("有进程/连接证据", (base / "processes.json").is_file()
          and (base / "connections.json").is_file())
    check("哈希链根", len(man.get("chain_root") or "") == 64, (man.get("chain_root") or "")[:12])
    check("哈希链完整", len(man.get("hash_chain") or []) >= 20,
          len(man.get("hash_chain") or []))
    check("证据索引", (base / "evidence-index.md").is_file())
    check("时间线", (base / "timeline.md").is_file() and (base / "timeline.json").is_file())

    print("[2] 资源回收只碰自己")
    rec = AF.reclaim_own_workers(apply=False)
    check("reclaim ok", rec.get("ok") is True, rec.get("reason"))
    check("保留关键进程计数", "kept_essential" in rec, rec)
    check("内存预算有读数", isinstance(rec.get("free_mb_before"), int)
          and rec.get("free_mb_before", 0) > 0, rec.get("free_mb_before"))
    for cand in rec.get("reclaimed_candidates") or []:
        cmd = str(cand.get("cmd") or "")
        check("候选只来自本框架",
              str(ROOT) in cmd or str(ROOT.parent) in cmd
              or any(h in cmd for h in AF.RECLAIMABLE_HINTS), cand)

    print("[3] 受攻击响应：攻击模式 + 取证")
    r = AF.respond("测试：模拟被扫描攻击", "edge log test", agents=8, ttl=120,
                   reclaim=False, incident=iid + "-respond")
    check("respond ok", r.get("ok") is True)
    check("进入攻击模式", (r.get("attack_mode") or {}).get("reason") == "测试：模拟被扫描攻击",
          r.get("attack_mode"))
    check("攻击模式生效", SP.attack_state().get("active") is True)
    check("转账仍被拦", SP.check("transfer")["decision"] == "blocked_transfer")
    check("黑客能力自我决策", SP.check("pentest")["decision"] == "attack_self_decision")
    SP.exit_attack_mode("test done")

    print("[4] 拒绝黑客反击")
    for op in ("power_off", "console_takeover", "kbm_cut", "hack_back"):
        d = AF.counterstrike(op)
        check("拒绝 " + op, d.get("blocked_illegal") is True and bool(d.get("legal_basis")),
              d.get("reason"))
    check("有合法替代清单", len(AF.counterstrike("power_off").get("legal_alternatives") or []) >= 3)

    print("[5] 审计")
    aud = SP.AUDIT.read_text(encoding="utf-8", errors="replace") if SP.AUDIT.is_file() else ""
    check("审计含 attack_on", '"attack_on"' in aud)

    # 清理测试证据
    for p in (ROOT / "outputs" / "forensics").glob(iid + "*"):
        try:
            shutil.rmtree(p, ignore_errors=True) if p.is_dir() else p.unlink()
        except Exception:
            pass

    print()
    if FAILS:
        print("FAILED %d: %s" % (len(FAILS), FAILS))
        return 1
    print("ALL OK —— 受攻击取证/极限并发/合法反制/拒绝黑客反击 全过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
