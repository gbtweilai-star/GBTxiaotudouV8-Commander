# gbt-capability: remote_controller
"""remote_controller 判据：没有远端同意，session 一律 denied。"""
from __future__ import annotations

import hashlib
import hmac
import importlib.util
import tempfile
from pathlib import Path

MOD = Path(__file__).resolve().parents[1] / "gbt_allinone" / "tentacle" / "remote_controller.py"
FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILED.append(name)


def load():
    spec = importlib.util.spec_from_file_location("remote_controller_mod", MOD)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main() -> int:
    R = load()
    with tempfile.TemporaryDirectory() as td:
        store = str(Path(td) / "sessions.json")
        print("[1] 只有请求，没有远端同意 → session denied")
        q = R.run("request", store=store)
        check("pending", q.get("status") == "pending" and q.get("request_id"), q)
        rid, code, secret = q["request_id"], q["code"], q["agent_secret"]
        s0 = R.run("session", store=store, request_id=rid)
        check("denied", s0.get("status") == "denied", s0)

        print("[2] 请求方自批（无远端 confirmed / 无签名）→ 拒")
        a0 = R.run("approve", store=store, request_id=rid, code=code)
        check("needs_remote_consent", a0.get("status") == "needs_remote_consent", a0)
        a1 = R.run("approve", store=store, request_id=rid, code=code,
                   remote_user={"confirmed": True, "host": "remote-pc", "user": "owner"})
        check("bad_signature", a1.get("status") == "bad_signature", a1)

        print("[3] code 错 → 拒")
        sig = hmac.new(secret.encode(), ("%s|%s|%s" % (rid, "remote-pc", "owner")).encode(), hashlib.sha256).hexdigest()
        a2 = R.run("approve", store=store, request_id=rid, code="000000",
                   remote_user={"confirmed": True, "host": "remote-pc", "user": "owner"}, agent_signature=sig)
        check("bad_code", a2.get("status") == "bad_code", a2)

        print("[4] 远端 agent 签名 + 用户确认 → 批准 → session")
        a3 = R.run("approve", store=store, request_id=rid, code=code,
                   remote_user={"confirmed": True, "host": "remote-pc", "user": "owner"}, agent_signature=sig)
        check("approved", a3.get("status") == "approved", a3)
        s1 = R.run("session", store=store, request_id=rid)
        check("session", s1.get("status") == "session" and s1.get("session", {}).get("id"), s1)

        print("[5] 撤销后 session 拒")
        R.run("revoke", store=store, request_id=rid)
        s2 = R.run("session", store=store, request_id=rid)
        check("revoked denied", s2.get("status") == "denied", s2)
        au = R.run("audit", store=store)
        check("有审计", len(au.get("events") or []) >= 4, au)

    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), FAILED))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
