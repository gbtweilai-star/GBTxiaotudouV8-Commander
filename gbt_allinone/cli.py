"""GBT小土豆V8 · CLI 交互壳（标准库实现，可运行验证）。"""
import json
import sys

from .api import list_capabilities, run_task
from .store import audit, query_log, log_count
from .caps_registry import UNIMPLEMENTED_CAPS


def _read_payload_file(fp: str) -> dict:
    """读 payload 文件 —— **必须吃 BOM**：

    实测踩过（2026-10-15，主人在 Windows PowerShell 5.1 里）：
      `\'{...}\' | Set-Content -Encoding utf8 p.json` ⇒ PS 5.1 写出的是 **UTF-8 with BOM**，
      而 `json.loads(….decode("utf-8"))` 会报 `Unexpected UTF-8 BOM` ⇒ 看起来像“文件读不到”，
      实际是**编码口径**问题。现在一律用 `utf-8-sig`。
    """
    from pathlib import Path as _P
    p = _P(fp)
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as exc:                                  # noqa: BLE001
        raise ValueError("读不到 %s（%s）" % (p, type(exc).__name__)) from exc


def _payload_from(raw: str, kind: str = "") -> tuple:
    """把一串参数解成 payload：回 (payload, 错误文本)。"""
    raw = str(raw or "").strip()
    if not raw:
        return {}, ""
    if raw.startswith("@"):
        try:
            return _read_payload_file(raw[1:]), ""
        except ValueError as exc:
            return None, "[错误] %s（提示：PowerShell 里 `@p.json` 会被当成展开运算符 ⇒ 请写成 `\"@p.json\"` 或用 --json-file）" % exc
    if raw[:1] in ("{", "["):
        try:
            return json.loads(raw), ""
        except Exception as exc:                              # noqa: BLE001
            return None, ("[错误] payload 不是合法 JSON（%s）：%s\n"
                          "   shell 会吃内层双引号。三条**不靠引号**的写法：\n"
                          "   ① \u7ba1\u9053：'{\"op\":\"…\"}' | py -3.14 -X utf8 -m gbt_allinone run %s --stdin\n"
                          "   ② \u6587\u4ef6：py -3.14 -X utf8 -m gbt_allinone run %s --json-file p.json\n"
                          "   ③ 裸\u8def\u5f84：py -3.14 -X utf8 -m gbt_allinone run %s p.json（\u8def\u5f84\u5b58\u5728\u5c31当 JSON \u8bfb）") % (type(exc).__name__, raw[:120], kind or "<kind>", kind or "<kind>", kind or "<kind>")
    _p = __import__("pathlib").Path(raw)
    if _p.is_file():
        try:
            return _read_payload_file(raw), ""
        except ValueError as exc:
            return None, "[错误] %s" % exc
    return {"text": raw}, ""

def cmd_list():
    print("== 可用能力（真能调，可执行）==")
    for c in list_capabilities(filter_dangerous=True):
        print(f"  - {c['name']:<14} [{c['domain']}] {c['desc']}")
    print("== 登记未实现的能力（只有名字、没有实现；禁止已解开，它们**不是**被挡住的）==")
    for k, reason in UNIMPLEMENTED_CAPS.items():
        print(f"  - {k:<16} unimplemented: {reason}")
    print(f"== 审计日志条数: {log_count()} ==")


def cmd_run(kind, payload=None):
    r = run_task(kind, payload)
    print(r)


def cmd_audit():
    for row in query_log(limit=20):
        print(f"  {row['iso']}  {row['event']:<7} {row['meta']}")


def cmd_auth(argv):
    """auth 子命令：grant（人工交互发放）/ status（只读查询）。

    grant 是授权的唯二发放途径之一（另一条是主人手写授权文件）。
    run_task 的任何路由都到不了这里。
    """
    from . import auth_gate
    sub = argv[1] if len(argv) > 1 else "status"
    if sub == "status":
        import json
        print(json.dumps(auth_gate.status(), ensure_ascii=False, indent=2))
        return 0
    if sub == "grant":
        # 解析 --scope / --ttl / --purpose
        scope, ttl, purpose = "osint_private", auth_gate.DEFAULT_TTL_S, ""
        i = 2
        while i < len(argv):
            if argv[i] == "--scope" and i + 1 < len(argv):
                scope = argv[i + 1]; i += 2
            elif argv[i] == "--ttl" and i + 1 < len(argv):
                ttl = int(argv[i + 1]); i += 2
            elif argv[i] == "--purpose" and i + 1 < len(argv):
                purpose = argv[i + 1]; i += 2
            else:
                i += 1
        r = auth_gate.cli_grant_interactive(scope, ttl, purpose)
        import json
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r.get("ok") else 1
    print("用法: gbt_allinone auth [status|grant --scope <s> --ttl <s> --purpose <text>]")
    return 1


def main(argv):
    # 🔴 2026-10-14 修（实测根因）：Windows 控制台默认 GBK，而能力描述里有 "⇒"（\u21d2）
    #    ⇒ `py -3.14 -m gbt_allinone list` 打到一半抛 UnicodeEncodeError('gbk')，命令整条死。
    #    修法：进入 CLI 前把 stdout/stderr 切成 utf-8（errors=replace，宁可降级字符也别崩）。
    #    口径：这是**输出编码**问题，不是能力面问题 —— 不许把它念成"能力位坏了"。
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:                                       # noqa: BLE001
            pass
    if not argv or argv[0] in ("list", "-l"):
        cmd_list()
        return 0
    if argv[0] in ("audit", "log"):
        cmd_audit()
        return 0
    if argv[0] == "auth":
        return cmd_auth(argv)
    if argv[0] in ("run", "call"):
        kind = argv[1] if len(argv) > 1 else "health"
        payload, err = {}, ""
        rest = list(argv[2:])
        # R-H1003（2026-10-15 实测）：三条**不靠 shell 引号**的入口。
        #   病因：PS 5.1 的 `Set-Content -Encoding utf8` **写 BOM** ⇒ json.loads 报错；
        #        而 `@p.json` 在 PowerShell 里是**展开运算符** ⇒ 未加引号必炸。
        if rest and rest[0] == "--stdin":
            payload = json.loads(sys.stdin.read() or "{}")
        elif rest and rest[0] in ("--json-file", "-f", "--file"):
            fp = rest[1] if len(rest) > 1 else ""
            try:
                payload = _read_payload_file(fp)
            except ValueError as exc:                          # noqa: BLE001
                print("[错误] %s" % exc)
                return 2
        elif rest:
            payload, err = _payload_from(rest[0], kind)
            if err:
                print(err)
                return 2
        cmd_run(kind, payload)
        return 0
        return 0
    print("用法: gbt_allinone [list|audit|auth|run <kind> [json]]")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
