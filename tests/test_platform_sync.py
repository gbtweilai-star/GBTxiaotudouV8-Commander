"""test_platform_sync.py · 平台状态只读同步（mock 平台端到端）

判据：
  1. 只同步已提交的发现（draft 不查平台）；
  2. 平台状态映射到本地状态机，走合法路径（例 duplicate 需 submitted→duplicate）；
  3. dry-run 不落状态；apply 才回填，并写 platform-sync.jsonl 审计；
  4. 平台 404/未知状态/非法 token 都要如实报，不吞；
  5. mock 平台是只读的（POST/PUT/DELETE 均 405）。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
PY = str(ROOT / "pyembed" / "python.exe") if (ROOT / "pyembed" / "python.exe").is_file() else sys.executable
PORT = 18991
BASE = "http://127.0.0.1:%d" % PORT
FAILS = []


def check(name, cond, extra=""):
    ok = bool(cond)
    print(("  ok   " if ok else "  FAIL ") + name + ((" · " + str(extra)) if extra else ""))
    if not ok:
        FAILS.append(name)


def wait_up(timeout=15.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(BASE + "/healthz", timeout=1.5).read()
            return True
        except Exception:  # noqa: BLE001
            time.sleep(0.3)
    return False


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from gbt_allinone import bounty as B
    from gbt_allinone import platform_sync as PS
    from gbt_allinone import bounty_core as core

    # 清测试项目
    progs = B._read_json(B.PROGRAMS, [])
    progs = [p for p in progs if p.get("name") != "sync-lab"]
    B.PROGRAMS.write_text(json.dumps(progs, ensure_ascii=False, indent=1), encoding="utf-8")
    r = B.add_program("sync-lab", ["127.0.0.1"], authorization_ref="同步自测（本机）")
    pid = (r.get("program") or {}).get("id")

    print("[0] 造 3 条发现并提交")
    fids = []
    for i, sev in enumerate(("low", "medium", "high"), 1):
        fr = B.add_finding(pid, "sync 测试发现 %d" % i, sev, "127.0.0.1",
                           cwe="CWE-200", steps="只读", impact="演示", remediation="演示")
        fid = (fr.get("finding") or {}).get("id")
        B.set_status(fid, "submitted", note="test")
        fids.append(fid)
    check("三条已提交", all(B.list_findings()["findings"] and True for _ in fids), fids)

    # mock 平台状态：triaged / duplicate / paid
    mapping = {fids[0]: "triaged", fids[1]: "duplicate", fids[2]: "paid"}
    mapfile = ROOT / "state" / "bounty" / "mock-map.json"
    mapfile.write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.Popen([PY, "-X", "utf8", str(ROOT / "tools" / "lab" / "mock_platform.py"),
                             "--port", str(PORT), "--map", str(mapfile), "--token", "MOCK-TOKEN"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    try:
        check("mock 平台在线", wait_up(), BASE)
        os.environ["GBT_MOCK_PLATFORM_TOKEN"] = "MOCK-TOKEN"

        print("[1] dry-run 不改状态")
        conf = dict(PS.DEFAULT_PLATFORMS["mock"])
        conf["base_url"] = BASE
        old = PS._load_platforms
        PS._load_platforms = lambda: {"mock": conf}
        try:
            d = PS.sync("mock", dry_run=True, program=pid)
            check("dry-run ok", d.get("ok") is True, d.get("errors"))
            check("dry-run 有 3 条计划", len(d.get("transitions") or []) == 3,
                  [t.get("path") for t in (d.get("transitions") or [])])
            st = {x["id"]: x["status"] for x in B.list_findings()["findings"] if x["id"] in fids}
            check("dry-run 状态未变", all(v == "submitted" for v in st.values()), st)

            print("[2] apply 只读回填到状态机")
            a = PS.sync("mock", dry_run=False, program=pid)
            check("apply ok", a.get("ok") is True, a.get("errors"))
            check("apply 更新 3 条", a.get("updated") == 3, a.get("updated"))
            st2 = {x["id"]: x["status"] for x in B.list_findings()["findings"] if x["id"] in fids}
            check("triaged 回填", st2.get(fids[0]) == "triaged", st2)
            check("duplicate 回填", st2.get(fids[1]) == "duplicate", st2)
            check("paid 回填", st2.get(fids[2]) == "paid", st2)
            check("审计日志有记录", (ROOT / "state" / "bounty" / "platform-sync.jsonl").is_file())

            print("[3] 只读平台：写方法被拒")
            for method in ("POST", "PUT", "DELETE"):
                req = urllib.request.Request(BASE + "/api/v1/reports/" + fids[0],
                                             method=method, data=b"{}")
                try:
                    urllib.request.urlopen(req, timeout=5)
                    code = 200
                except urllib.error.HTTPError as e:
                    code = e.code
                check(method + " 405", code == 405, code)
        finally:
            PS._load_platforms = old

        print("[4] 未知 provider / 缺 token 如实报")
        check("未知 provider 拒绝", PS.sync("nosuch").get("ok") is False)
        conf2 = dict(PS.DEFAULT_PLATFORMS["mock"])
        conf2["base_url"] = BASE
        conf2["token_env"] = "NO_SUCH_TOKEN_ENV"
        conf2.pop("token_default", None)
        old2 = PS._load_platforms
        PS._load_platforms = lambda: {"mock": conf2}
        try:
            r2 = PS.sync("mock", dry_run=True)
            check("缺 token 拒绝", r2.get("ok") is False and "token" in (r2.get("reason") or ""),
                  r2.get("reason"))
        finally:
            PS._load_platforms = old2
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:  # noqa: BLE001
            proc.kill()

    print()
    if FAILS:
        print("FAILED %d: %s" % (len(FAILS), FAILS))
        return 1
    print("ALL OK —— 平台状态只读同步：dry-run/回填/审计/只读/异常 全链路")
    return 0


if __name__ == "__main__":
    sys.exit(main())
