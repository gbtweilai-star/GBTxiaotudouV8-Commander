# -*- coding: utf-8 -*-
"""update_chain（本地更新测试链）契约/门/API/面板验收。"""
from __future__ import annotations

import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gbt_allinone.tools import update_chain as UC  # noqa: E402

OK = 0
FAIL = []


def check(name, cond, got=None):
    global OK
    if cond:
        OK += 1
        print("  ok  ", name)
    else:
        FAIL.append(name)
        print("  FAIL", name, "|", repr(got)[:200])


def main() -> int:
    print("[1] 契约（init/stage/confirm/rollback）")
    r = UC.verify()
    check("verify() 全绿", r["ok"] is True, r.get("failed"))
    check("判据数 ≥ 10", r["checks"] >= 10, r["checks"])
    d = pathlib.Path(tempfile.mkdtemp(prefix="gbt-chain-test-"))
    init = UC.init_channel(d)
    check("init 无密钥", init["ok"] and (d / "channel/manifest.json").is_file()
          and not (d / "channel/dev-key.pem").exists() and init.get("signature") is False)
    st = UC.stage(d)
    check("stage", st["ok"] and st["files"] >= 3 and st["confirm_token"] and st.get("signature") is False, st)
    check("坏 token 拒", _raises(lambda: UC.confirm(d, st["stage_id"], "bad")))
    ap = UC.confirm(d, st["stage_id"], st["confirm_token"])
    check("confirm 应用", ap["ok"] and ap["applied"], ap)
    check("target 版本", (d / "target/version.txt").read_text(encoding="utf-8").strip()
          == "8.0.1-test")
    rb = UC.rollback(d)
    check("rollback", rb["ok"] and rb["version"] == "8.0.0-local", rb)
    check("status production=false", UC.status(d)["production_update"] is False)
    check("路径越界拒", _raises(lambda: UC._safe_join(d, "../x")))
    check("未知 stage 拒", _raises(lambda: UC.confirm(d, "st-nope", "x")))
    check("空 root rollback 拒", _raises(lambda: UC.rollback(
        pathlib.Path(tempfile.mkdtemp(prefix="gbt-chain-empty-")))))

    print("[2] 统一门 / API / 面板 / APP")
    reg = (ROOT / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8")
    api = (ROOT / "gbt_allinone/api.py").read_text(encoding="utf-8")
    check("注册表 update_chain", '"update_chain": {' in reg and '"handler": "update_chain"' in reg)
    check("api 分派", 'kind == "update_chain"' in api)
    check("run_task 可达", _gate_ok())
    srv = (ROOT / "tools/console-server.py").read_text(encoding="utf-8")
    check("server /api/update-chain", '"/api/update-chain"' in srv and "update_chain" in srv)
    idx = (ROOT / "holo_pet_w3/console/index.html").read_text(encoding="utf-8")
    check("更新面板测试链按钮", 'id="up-chain-init"' in idx and 'id="up-chain-confirm"' in idx)
    js = (ROOT / "holo_pet_w3/console/update-panel.js").read_text(encoding="utf-8")
    check("UI init/stage/confirm/rollback", "/api/update-chain" in js and "up-chain-rollback" in js)
    payload = (ROOT.parent / "GBT小土豆V8桌面版" / "payload")
    if payload.is_dir():
        check("APP payload 已同步 update_chain",
              (payload / "gbt_allinone/tools/update_chain.py").is_file()
              and '"update_chain": {' in (payload / "gbt_allinone/caps_registry.py").read_text(encoding="utf-8"))
    check("文档 docs/178 存在", (ROOT / "docs/178-update-chain-local.md").is_file())

    print()
    if FAIL:
        print("FAILED", len(FAIL), FAIL)
        return 1
    print("ALL OK —— update_chain（无密钥 hash-only：stage/confirm/rollback，不碰正式 APP）全绿")
    return 0


def _raises(fn):
    try:
        fn()
        return False
    except (UC.ChainError, ValueError):
        return True


def _gate_ok():
    try:
        import gbt_allinone as g
        r = g.run_task("update_chain", {"op": "verify"}, safe=True)
        inner = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        return bool(r.get("ok")) and bool(inner.get("ok"))
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
