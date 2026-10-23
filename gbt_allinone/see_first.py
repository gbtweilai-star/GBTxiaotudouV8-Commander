# -*- coding: utf-8 -*-
"""see_first -- 代码层“先看后动”闸（TRAINING_LAW 第 37 条）。

只拦“会动手”的调用（写盘/出网/花钱/部署/推进一炉）；只读调用一律不拦。
要求：TTL 内有一份**已批立体蓝图**（state/blueprints/*.approved）。
"""
from __future__ import annotations
import os, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BDIR = ROOT / "state" / "blueprints"
TTL = 7200
ACTION_OPS = {"run", "deploy", "release", "apply", "write", "commit", "push", "publish", "provision",
              "rollback", "install", "delete", "rm", "kill", "stop", "start", "send", "post"}
ACTION_CAPS = {"one_key_deploy", "pipeline_submit", "pipeline_rollback", "mirror_release", "mirror_ascend",
               "mirror_rehearse", "room_release", "room_rehearse", "git_write", "code_patch", "auto_publish",
               "pod_link", "comfy_native", "deploy_cloudflare", "remote_domain", "device_takeover"}


def _bdir() -> Path:
    """蓝图目录（现读）。

    🔴 2026-10-17 加（留痕 · 原口径 / 为什么翻 / 现口径）：
      原口径：写死 `ROOT/state/blueprints`，**完全不认 `GBT_STORE_DIR` 隔离**。
      为什么翻：测试套件在隔离 store 里跑，可这道闸永远读**生产 state** ⇒
        ① 任何"走行动类"的契约测试在干净环境下永远被拦（实测 `test_file_operation`
           的 `test_trusted_session_dispatches_through_api` 就红在这里，
           报「未看先动，拒绝推进 · TTL 内无已批蓝图」）；
        ② 更糟：测试其实在**读生产蓝图**，隔离形同虚设。
      现口径：`SEE_FIRST_BDIR` 可把**目录位置**指到隔离目录 —— 只换位置，
        **不提供任何放行开关**、拦截判据一个字不改；不设时仍是 `ROOT/state/blueprints`。
    """
    return Path(os.environ.get("SEE_FIRST_BDIR") or BDIR)


def _approved_recent() -> tuple:
    bdir = _bdir()
    if not bdir.is_dir():
        return False, "无蓝图目录"
    now = time.time()
    best = None
    for f in bdir.glob("*.approved"):
        age = now - f.stat().st_mtime
        if age <= TTL and (best is None or age < best[0]):
            best = (age, f.stem)
    if best is None:
        return False, "TTL 内无已批蓝图"
    return True, "%s（%.0f 分钟前批）" % (best[1], best[0] / 60)


def is_action(kind: str, payload: dict) -> bool:
    if kind in ACTION_CAPS:
        return True
    op = str((payload or {}).get("op") or (payload or {}).get("action") or "").lower()
    return op in ACTION_OPS


# 🔴 2026-10-19 主人令（逐字）：「除了设计好的三个人工授权其他限制都给我去掉」
#    ⇒ 「先看后动」（第 37 条：TTL 内必须有已批蓝图）这道**流程门**关闭。
#    三道护栏不受影响（它们走的是 policy 的作用域门，不是这里）。
#    要恢复：把它改回 True 即可（判据一条没删，只是不再拦）。
BLUEPRINT_GATE = False


def guard(kind: str, payload: dict):
    """返回 None 表示放行；否则返回拒绝信封。"""
    if not BLUEPRINT_GATE:
        return None
    if not is_action(kind, payload):
        return None
    if os.environ.get("SEE_FIRST_FORCE_NONE") == "1":
        ok, why = False, "强制无批准（自测）"
    else:
        ok, why = _approved_recent()
    if ok:
        return None
    return {"ok": False, "reason": "未看先动，拒绝推进",
            "detail": why, "how": "先出立体蓝图并由主人 approve，再动手",
            "law": "TRAINING_LAW 第 37 条"}


def selftest() -> int:
    os.environ["SEE_FIRST_FORCE_NONE"] = "1"
    r1 = guard("comfy_native", {"op": "run"})
    r2 = guard("count_words", {"text": "a b"})
    ok_act = isinstance(r1, dict) and r1.get("ok") is False
    ok_read = r2 is None
    print("行动类（op=run）应拦:", "OK" if ok_act else "FAIL")
    print("只读类（count_words）应放:", "OK" if ok_read else "FAIL")
    del os.environ["SEE_FIRST_FORCE_NONE"]
    ok = ok_act and ok_read
    print("see_first 自测:", "OK（能拦能放）" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(selftest())
