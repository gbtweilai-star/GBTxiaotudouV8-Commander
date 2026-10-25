# -*- coding: utf-8 -*-
"""R-H291 原生浏览器接线 · 回归验证。
要点：接线必须**只补分发、不动门** —— 读操作免卡、写操作照卡、别名与 policy.py 不许漂移。
"""
import json
import re
import sys
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
sys.path.insert(0, str(BASE))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from gbt_allinone import api, browser_cap, native_browser  # noqa: E402
from gbt_allinone.security import policy  # noqa: E402

ok_n = fail_n = 0


def chk(name, cond, detail=""):
    global ok_n, fail_n
    if cond:
        ok_n += 1
        print("  ✓ %-44s %s" % (name, detail))
    else:
        fail_n += 1
        print("  ✗ %-44s %s" % (name, detail))


print("=" * 88)
print("R-H291 原生浏览器接线 · 回归")
print("=" * 88)

# ── 1. 别名不漂移：api.py 认的 op 集合必须与 policy.py 认的一致 ──
src_pol = (BASE / "gbt_allinone/security/policy.py").read_text(encoding="utf-8")
# 只认「原生浏览器」那一段的别名（policy.py 里有 5 处 `op in (...)`，不能抓第一个）
m = re.search(r'if op in \(([^)]*)\):\s*\n\s*action = str\(', src_pol)
policy_ops = tuple(re.findall(r'"([a-z]+)"', m.group(1))) if m else ()
chk("别名与 policy.py 完全一致", bool(policy_ops) and set(policy_ops) == set(browser_cap.NATIVE_BROWSER_OPS),
    "policy=%s browser_cap=%s" % (list(policy_ops), list(browser_cap.NATIVE_BROWSER_OPS)))
chk("别名非空", len(browser_cap.NATIVE_BROWSER_OPS) >= 4, str(list(browser_cap.NATIVE_BROWSER_OPS)))
chk("api.py 不再自建第二份别名表（单一事实源）",
    not hasattr(api, "NATIVE_BROWSER_OPS"), "别名只在 browser_cap 里有一份")


def body_of(resp):
    """api.run_task 会把能力回执套两层（gbt_result.result / result），取到内层。"""
    b = resp
    for _ in range(4):
        if not isinstance(b, dict):
            break
        nxt = b.get("gbt_result") or b.get("result")
        if isinstance(nxt, dict) and ("ok" in nxt or "status" in nxt):
            b = nxt
        else:
            break
    return b


# ── 2. 接线生效：op=native 不再报「未知 op」 ──
r = api.run_task("browser", {"op": "native", "action": "status"}, safe=True, probe=True)
body = body_of(r)
chk("op=native 已被分发", "未知 op" not in json.dumps(body, ensure_ascii=False)[:400], "")
chk("回执带 cap=native_browser", body.get("cap") == "native_browser", str(body.get("cap")))
chk("回执带 backend=CDP", body.get("backend") == "chrome-devtools-protocol", str(body.get("backend")))
chk("status 如实报 CDP 是否可用", "cdp_available" in body,
    "cdp_available=%s" % body.get("cdp_available"))
chk("transport 是标准库实现（零第三方）",
    body.get("transport") == "standard-library-rfc6455", str(body.get("transport")))
chk("status 报出全部 29 个动作", len(body.get("actions") or []) == 29,
    "%d 个" % len(body.get("actions") or []))
chk("未接 CDP 时如实说明怎么开",
    isinstance(body.get("note"), str) and "launch" in (body.get("note") or ""),
    (body.get("note") or "")[:56])


# ── 2b. 框架自己的规格：api._run_benign 必须把 allow_private 交给 browser_cap ──
import types as _types  # noqa: E402
from unittest import mock as _mock  # noqa: E402
_raw = {"decision": _types.SimpleNamespace(allow_private=True)}
with _mock.patch.object(browser_cap, "run", return_value={"ok": True}) as _run:
    api._run_benign("browser", {"op": "native", "action": "navigate",
                                "url": "http://127.0.0.1:8080"}, _raw)
chk("browser_cap 收到 allow_private（框架规格）",
    bool(_run.call_args) and _run.call_args.kwargs.get("allow_private") is True,
    str(_run.call_args.kwargs.get("allow_private")) if _run.call_args else "未被调用")
chk("action 也透传到了浏览器门面",
    bool(_run.call_args) and _run.call_args.kwargs.get("action") == "navigate",
    str(_run.call_args.kwargs.get("action")) if _run.call_args else "未被调用")

# ── 3. 门没被放宽：只读免卡、写操作照卡 ──
print("\n● 作用域判定（门必须原样有效）")
READONLY = ["status", "list_tabs", "get_title", "get_url", "get_text", "dom_query",
            "get_cookies", "intercept_events", "intercept_status"]
for act in READONLY:
    d = policy.evaluate("browser", {"op": "native", "action": act})
    chk("只读 %s 免卡" % act, not d.scopes, "scopes=%s" % (d.scopes,))
for act in ["click_element", "type_text", "execute_script", "inject_script",
            "navigate", "launch", "ensure", "create_tab", "close_tab",
            "activate_tab", "reload", "back", "forward", "set_cookies",
            "privacy_mode", "intercept_requests", "intercept_stop", "pin_window"]:
    d = policy.evaluate("browser", {"op": "native", "action": act})
    chk("写操作 %s 照卡" % act, "browser_control" in d.scopes, "scopes=%s" % (d.scopes,))
d = policy.evaluate("browser", {"op": "native", "action": "screenshot"})
chk("screenshot 追加 filesystem_write", "filesystem_write" in d.scopes, "scopes=%s" % (d.scopes,))
d = policy.evaluate("browser", {"op": "native", "action": "get_cookies", "include_values": True})
chk("get_cookies+include_values 追加 privacy_read", "privacy_read" in d.scopes, "scopes=%s" % (d.scopes,))

# ── 4. 独立能力名不许存在（否则就是免门后门） ──
print("\n● 不许新开门")
names = {r["name"] for r in api.list_capabilities()}
chk("native_browser 未成为独立能力名", "native_browser" not in names, "")
d = policy.evaluate("native_browser", {"op": "native", "action": "click_element"})
chk("直呼 native_browser 在门那侧确实是空的（所以更不能注册它）", not d.scopes,
    "scopes=%s ⇒ 若注册就是免门洞，故只走 browser+op=native" % (d.scopes,))

# ── 5. 无回归：browser 原有 op 照旧 ──
print("\n● 原路径无回归")
r = api.run_task("browser", {"op": "open", "url": "https://example.com"}, safe=True, probe=True)
chk("op=open 仍走 browser_cap", "未知 op" not in json.dumps(r, ensure_ascii=False)[:300], "")
r = api.run_task("browser", {"op": "fetch", "url": "https://example.com"}, safe=True, probe=True)
chk("op=fetch 仍走 browser_cap", "未知 op" not in json.dumps(r, ensure_ascii=False)[:300], "")
r = api.run_task("browser", {"op": "nonsense"}, safe=True, probe=True)
chk("未知 op 仍如实报错", bool(r.get("ok")) is False, str(r.get("message"))[:60])

# ── 6. 注册表可发现性 ──
caps = {r["name"]: r for r in api.list_capabilities()}
chk("browser 登记已写明 native 一组", "op=native" in (caps.get("browser", {}).get("desc") or ""), "")
chk("能力总数未因接线而变化（140）", len(caps) == 140, "%d" % len(caps))
chk("native_browser 动作表可自查", "pin_window" in (native_browser.capabilities().get("actions") or []),
    "%d 个动作" % len(native_browser.capabilities().get("actions") or []))

print("\n" + "-" * 88)
print("通过 %d · 失败 %d" % (ok_n, fail_n))
sys.exit(0 if fail_n == 0 else 1)
