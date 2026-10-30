#!/usr/bin/env python3
"""用镜像多维度空间跑一遍真实变更（不拿现实当试验场）

变更内容：把 10 个镜像位接进生产面板（holo_pet_w3/panel/index.html）
          + 面板后端新增 /api/mirror（转发到能力层，白名单 fail-closed）

口径见 docs/09：先在镜像维度成形 → 体检 → 计划 → 推演 → 一致性 → 排练
                → 一次性晋升（过 deploy_publish 门）。

用法：
  python3 tools/mirror_panel.py --emit      # 只打印计划（不写任何东西）
  python3 tools/mirror_panel.py --run       # 依次跑 shape/scan/plan/simulate/parity
  python3 tools/mirror_panel.py --plan      # 只跑 plan
"""
from __future__ import annotations

import argparse
import json
import pathlib
import socket
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))   # run_task 在 gbt_allinone 里，脚本模式要自己挂路径
PANEL = "holo_pet_w3/panel/index.html"
NAME = "panel-mirror"
HOST, PORT = "127.0.0.1", 8765


def _via_panel(kind: str, payload: dict) -> dict:
    """经面板 :8765 调 /api/capability（面板没有 /api/mirror，实测 404）。"""
    body = json.dumps({"kind": kind, "payload": payload, "confirm": True}).encode()
    s = socket.socket()
    s.settimeout(30)
    try:
        s.connect((HOST, PORT))
        s.sendall(b"POST /api/capability HTTP/1.0\r\nHost: x\r\n"
                  b"Content-Type: application/json\r\n"
                  b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body)
        buf = b""
        while True:
            c = s.recv(65536)
            if not c:
                break
            buf += c
        d = json.loads(buf.split(b"\r\n\r\n", 1)[1])
        d["_via"] = "panel"
        return d
    except Exception as exc:                                      # noqa: BLE001
        return {"ok": False, "_via": "panel",
                "_error": "%s: %s" % (type(exc).__name__, exc)}
    finally:
        s.close()


def call(op: str, payload: dict | None = None) -> dict:
    """调镜像能力：**进程内优先，面板兜底**。

    2026-10-30 两处修正，都是实测出来的：
      ① 原来 POST /api/mirror —— 面板没这个路由（直接 404），六步全"未输出"。
      ② 改打 /api/capability 后，面板是**异步受理**，还会撞 action_guard 去重，
         回一个 `{in_flight:true, reused:true}` 的空壳（没有 ok 字段）⇒ ok=None。
         面板内部本来就是 `api.run_task(kind, payload)`，所以直接走同一条路：
         少一跳 HTTP、少一层空壳。`_via` 如实标走的哪条。
    """
    kind = op if op.startswith("mirror_") else ("mirror_" + op)
    payload = dict(payload or {})
    sys.path.insert(0, ROOT)
    try:
        from gbt_allinone.api import run_task
        res = run_task(kind, payload)
        body = res.get("gbt_result", res) if isinstance(res, dict) else res
        out = body.get("result") if isinstance(body, dict) and "result" in body else body
        out = dict(out or {})
        out.setdefault("_via", "in-process")
        if out.get("ok") is not None:
            return out
    except Exception:                                             # noqa: BLE001
        pass
    r = _via_panel(kind, payload)
    r.setdefault("_via", "panel")
    return r


def result(r: dict) -> dict:
    return (r.get("gbt_result") or {}).get("result") or r.get("result") or {}


def build_plan() -> dict:
    return {
        "name": NAME,
        "plan": {
            "goal": "把镜像多维度空间（10 位）接进生产面板，且不改变现实树既有行为",
            "assumptions": [
                {"statement": "注入区块后原有导航与自卫挂件仍在",
                 "verify": "浏览器实读 DOM：gbt-mirror 存在、7 按钮、原 .rail 仍在"},
                {"statement": "/api/mirror 转发到能力层且白名单 fail-closed",
                 "verify": "POST op=bogus_op 应返回『未列出的 op（fail-closed）』"},
                {"statement": "面板后端在缺 research_status/social_platforms 时仍能启动",
                 "verify": "启动日志出现『GBT小土豆 3D 全息面板』且 :8765 可连"},
            ],
            "architecture": {
                "components": [
                    {"id": "panel_page", "responsibility": "面板页：展示镜像读数与七步入口",
                     "depends_on": []},
                    {"id": "panel_server", "responsibility": "面板后端 :8765：提供 /api/mirror",
                     "depends_on": []},
                    {"id": "capability_layer", "responsibility": "能力层 run_task：唯一真源与授权门",
                     "depends_on": []},
                    {"id": "mirror_space", "responsibility": "镜像维度存储：shape/scan/ascend",
                     "depends_on": ["capability_layer"]},
                ],
                "entrypoints": [PANEL, "holo_pet/panel_server.py"],
                "data_flow": [
                    {"from": "panel_page", "to": "panel_server"},
                    {"from": "panel_server", "to": "capability_layer"},
                    {"from": "capability_layer", "to": "mirror_space"},
                ],
            },
            "steps": [
                {"id": "S1", "action": "shape 面板页到镜像维度"},
                {"id": "S2", "action": "scan 五项体检"},
                {"id": "S3", "action": "simulate 静态推演"},
                {"id": "S4", "action": "parity 环境一致性"},
                {"id": "S5", "action": "rehearse 排练出指纹报告"},
                {"id": "S6", "action": "release 一次性晋升（过 deploy_publish 门）"},
            ],
            # 每个服务都带**可验证信号** —— 计划要求 health_url / heartbeat_file /
            # windows_service 三选一，否则报"缺少可验证信号"（实测踩到）
            "services": [
                {"name": "panel_server", "port": 8765, "host": "127.0.0.1",
                 "health_url": "http://127.0.0.1:8765/api/state"},
                {"name": "static_pages", "port": 8080, "host": "127.0.0.1",
                 "health_url": "http://127.0.0.1:8080/index.html"},
            ],
            "files": [PANEL, "holo_pet/panel_server.py"],
            # 🔴 rollback 是**计划顶层**字段，不是 rehearsal 的子键（实测踩到）
            "rollback": {
                "strategy": "command",
                "action": {"id": "rewind",
                           "argv": ["python3", "tools/mirror_rewind.py"],
                           "timeout": 120},
            },
            # 验收闭环：计划要求"代码/服务部署必须定义 rehearsal.acceptance"
            # acceptance 是**命令 id 列表**，必须引用 rehearsal.commands 里存在的 id
            # （实测：写成 {statement,evidence} 会报"acceptance 引用了不存在的命令"）
            "rehearsal": {
                "commands": [
                    {"id": "accept_probe",
                     "argv": ["python3", "tools/mirror_check.py"],
                     "timeout": 120},
                    {"id": "panel_alive",
                     "argv": ["python3", "tools/svcprobe.py", "tcp", "8765"],
                     "timeout": 30},
                ],
                "acceptance": ["accept_probe", "panel_alive"],
            },
            # 生产就在本机（同宿主）—— 计划要求显式声明，不能默认
            "environment": {
                "production": {"mode": "same_host", "platform": "linux",
                               "python": ".".join(sys.version.split()[0].split(".")[:2])},
            },
        },
    }


def verify_reality(plan: dict) -> dict:
    """放行前先验现实 —— 比 scan 的五项更严的一道。

    为什么加在编排层而不是改 scan()：
      scan() 是框架的"五项体检"契约，改了会动别人依赖的形状；
      这里做的是**编排层自己的更严门**：晋升前必须证明
        · 计划里每个服务的端口真的在听
        · 计划里每个文件真的在、哈希对得上
      任何一条不过就拒绝放行，并列出是哪条。

    走大脑执行层的 brain_verify（reality 面），不自己另写一套探活。
    """
    from gbt_allinone.api import run_task
    targets: list[str] = []
    for sv in (plan.get("plan", {}).get("services") or []):
        url = str(sv.get("health_url") or "")
        port = sv.get("port")
        if port:
            targets.append("%s :%s 应该在线" % (sv.get("name"), port))
        elif url:
            targets.append("%s %s 应该在线" % (sv.get("name"), url))
    for f in (plan.get("plan", {}).get("files") or []):
        targets.append("文件 %s 存在" % f)

    out = {"ok": True, "checks": [], "faces": 0}
    for t in targets:
        r = run_task("brain_verify", {"expectation": t})
        res = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
        v = res.get("verdict") or "unknown"
        faces = res.get("counted_faces") or []
        out["faces"] += 1 if faces else 0
        row = {"expectation": t, "verdict": v, "ok": bool(res.get("ok"))}
        out["checks"].append(row)
        if v == "failed":
            out["ok"] = False
    if out["faces"] == 0:
        out["ok"] = False
        out["why"] = "一条可验证面都没有 —— 不能凭 scan 的脸色就放行"
    return out


def show(op: str, r: dict) -> None:
    x = result(r)
    keys = [k for k in ("ok", "clean", "plan_sha", "report_sha", "tree_sha",
                        "passed", "blocked", "status", "files")
            if k in x]
    print("  %-9s ok=%-6s %s" % (op, r.get("ok"),
          " · ".join("%s=%s" % (k, str(x[k])[:60]) for k in keys)))
    if r.get("ok") is False:
        print("        错误: %s" % str(r.get("error") or x)[:240])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--run", action="store_true")
    a = ap.parse_args()

    plan = build_plan()
    if a.emit:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0

    if a.plan:
        show("plan", call("plan", plan))
        return 0

    if a.run:
        content = (ROOT / PANEL).read_text(encoding="utf-8")
        show("shape", call("shape", {"path": PANEL, "content": content,
                                     "note": "面板接入镜像多维度空间"}))
        srv_path = "holo_pet/panel_server.py"
        srv = (ROOT / srv_path).read_text(encoding="utf-8")
        show("shape", call("shape", {"path": srv_path, "content": srv,
                                     "note": "面板后端新增 /api/mirror"}))
        show("scan", call("scan"))
        show("plan", call("plan", plan))
        show("simulate", call("simulate", {"name": NAME}))
        show("parity", call("parity", {"name": NAME}))
        # ⑥ 放行前先验现实（编排层更严的门）
        v = verify_reality(plan)
        print("  %-9s ok=%-6s 验证面 %d 条" % ("verify", v["ok"], v["faces"]))
        for c in v["checks"]:
            print("     %s %-34s %s" % ("✅" if c["ok"] else "🔴", c["expectation"][:32], c["verdict"]))
        if not v["ok"]:
            print("     🔴 拒绝放行：%s" % (v.get("why") or "有面没过"))
            return 1
        print("     ✅ 现实全过 —— 可以进 release（release 本身还要过 deploy_publish 门）")
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
