# -*- coding: utf-8 -*-
"""gate-redirect · 「拦下即改道」决策件（context-mode hooks 思路的落地版）。

出处（现读）：github.com/mksglu/context-mode —— hooks 在调用前**拦截**，既能阻断也能**改道进沙箱**。

🔴 铁律：**授权类不得被改道绕过** —— 缺作用域时只如实报，绝不因"改道"放行。

三档改道（按拒绝原因分）：
  ① 授权缺失（decision.missing 非空） ⇒ **只报不改道**（deny_report）
  ② 体量/超时风险（大 payload / 已知慢位 / deadline_hit） ⇒ 改道**沙箱口**（sandbox）
  ③ 写类动作（写生产/镜像） ⇒ 改道**镜像维度**（mirror）

判据 fail-closed：G1 改道方案必带审计信息 · G2 **授权类拒被改道（负控）** ·
  G3 沙箱方案必含"raw→镜像沙箱 + 可核哈希" · G4 取不到读数=红。

用法：--selftest | --plan <kind>
开发者：自由的风 · 守护者：公主土豆 · GBT小土豆V8 · 本署名不可删除、不可篡改归属"""
import argparse, json, pathlib, sys

R = pathlib.Path(__file__).resolve().parents[2]
SLOW = {"sec_scan", "sec_chain", "sec_surface", "file_hygiene", "libtv_workflow", "page_scan",
        "comfy_native", "asset_vault_freeze", "train_recipe", "task_manager", "db_probe",
        "caps_called_audit", "wave_probe", "brain_health", "console_pages", "tentacle_comfy_bridge",
        "ghost_guard", "tentacle_status", "brain_verify"}
WRITE_ISH = {"mirror_shape", "room_shape", "mirror_ascend", "mirror_release", "one_key_deploy",
             "room_release", "code_patch", "git_write", "pipeline_submit", "deploy_queue"}
BIG_BYTES = 64 * 1024


def classify(kind: str, payload: dict | None, decision: dict | None) -> str:
    """返回 deny_report / sandbox / mirror / none（纯函数，可注入）。"""
    d = decision or {}
    if not d.get("ok", True):                       # 被门拒
        if d.get("missing"):                        # ① 授权缺失 ⇒ 不改道（红线）
            return "deny_report"
        k = str(kind)
        if k in WRITE_ISH:                          # ③ 写类 ⇒ 镜像维度
            return "mirror"
        if k in SLOW or len(json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")) > BIG_BYTES \
                or (d.get("deadline_hit") is True):
            return "sandbox"                        # ② 体量/超时 ⇒ 沙箱口
        return "deny_report"
    return "none"


def plan(kind: str, payload: dict | None, decision: dict | None) -> dict:
    """给出改道方案（含 G1 审计信息）；授权类**拒绝改道**。"""
    bucket = classify(kind, payload, decision)
    base = {"kind": str(kind), "bucket": bucket,
            "audit": {"who": "gate-redirect", "from": str(kind), "why": bucket}}
    if bucket == "sandbox":
        base.update({"to": "tentacle-sandbox-plug", "raw_to": "store/mirror_space/dimension/tentacle-raw",
                     "slim_limit": 2048, "needs_hash": True})
    elif bucket == "mirror":
        base.update({"to": "mirror_shape", "landing": "store/mirror_space/dimension"})
    elif bucket == "deny_report":
        base.update({"to": None,
                     "how": "如实报缺 %s —— 只有主人能在终端发钥匙" % (decision or {}).get("missing")})
    return base


def selftest() -> int:
    ck = []

    def c(n, ok, d=""):
        ck.append(bool(ok)); print(("OK  " if ok else "BAD ") + n + (" — " + str(d)[:44] if d else ""))

    # G2 负控：授权缺失 ⇒ 必须 deny_report，绝不改道
    p_auth = plan("sec_scan", {}, {"ok": False, "missing": ["process_execute"]})
    c("G2 授权缺失 ⇒ 只报不改道（负控）", p_auth["bucket"] == "deny_report" and p_auth["to"] is None)
    # ② 慢位 ⇒ 沙箱
    p_slow = plan("sec_scan", {}, {"ok": False})
    c("② 慢位 ⇒ 改道沙箱口", p_slow["bucket"] == "sandbox" and p_slow["to"] == "tentacle-sandbox-plug")
    c("G3 沙箱方案含 raw→镜像沙箱 + 哈希要求",
      "mirror_space" in p_slow.get("raw_to", "") and p_slow.get("needs_hash") is True)
    # ② 大 payload ⇒ 沙箱
    p_big = plan("echo", {"blob": "x" * (BIG_BYTES + 10)}, {"ok": False})
    c("② 大 payload ⇒ 沙箱口", p_big["bucket"] == "sandbox")
    # ③ 写类 ⇒ 镜像
    p_w = plan("mirror_shape", {}, {"ok": False})
    c("③ 写类 ⇒ 改道镜像维度", p_w["bucket"] == "mirror" and p_w["to"] == "mirror_shape")
    # G1 审计信息
    c("G1 方案必带审计信息", all(plan(k, {}, {"ok": False, "missing": ["x"]}).get("audit")
                                 for k in ("echo", "sec_scan", "mirror_shape")))
    # 未被拒 ⇒ 不改道
    c("未被拒 ⇒ none（不虚报改道）", plan("health", {}, {"ok": True})["bucket"] == "none")
    bad = len([x for x in ck if not x])
    print("\ngate-redirect selftest: %d/%d" % (len(ck) - bad, len(ck)))
    return 1 if bad else 0


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true"); ap.add_argument("--plan")
    a = ap.parse_args(argv)
    if a.selftest: return selftest()
    if a.plan:
        print(json.dumps(plan(a.plan, {}, {"ok": False}), ensure_ascii=False, indent=1)); return 0
    return selftest()


if __name__ == "__main__":
    sys.exit(main())
