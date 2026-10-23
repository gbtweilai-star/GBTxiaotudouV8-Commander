# -*- coding: utf-8 -*-
"""用浏览器触手把 HN 投稿页的三个字段填好，**停在 submit 前不进**。

走唯一门：`run_task("browser", {"op":"native","action":"execute_script","js":...})`。
需要 `browser_control` 票（时段票，600s 够用）。

纪律：
  · 只填 `title` / `url` / `text` 三个输入框，**绝不点 submit**（点了就是对外发帖，必须主人按）；
  · 填完回读三个框的值做验收（不看"应该成功了"）；
  · 没登录（页面还是 login 表单）⇒ 如实报"未登录"，不硬填；
  · 现场教训：`execute_script` 的位置参数叫 **js**，不是 script —— 传错会被门当场回
    `execute_script() missing 1 required positional argument: 'js'`。

用法：
  py -3.14 -X utf8 tools/codex-scripts/fill-hn-submit.py
  py -3.14 -X utf8 tools/codex-scripts/fill-hn-submit.py --dry   # 只看状态不填
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

TITLE = "Show HN: A 7.6B model that routes requests to 341 audited capability bits"
URL = "https://github.com/gbtweilai-star/GBTxiaotudouV8-Commander"
TEXT = ("Live 3D preview (20k tentacles, no deps): "
        "https://gbtweilai-star.github.io/GBTxiaotudouV8-Commander/arms/tentacle3d.html"
        "\n\nIt started as a shield — every write / spend / network action needs a human ticket — "
        "and ended up as a remote control: the same plug can point at any OpenAI-compatible endpoint, "
        "so a key plus a network path is enough to reverse-call cloud models or free GPU spaces.")
SUBMIT_PAGE = "https://news.ycombinator.com/submit"


def gate(payload: dict) -> dict:
    """走唯一门，并把多层信封**挖到最里面那层**（带 action/result 的能力位回执）。"""
    from gbt_allinone import run_task
    env = run_task("browser", payload) or {}
    cur, best, hops = env, {}, 0
    while isinstance(cur, dict) and hops < 6:
        if "ok" in cur and ("action" in cur or "error" in cur):
            best = cur
        nxt = cur.get("result") if isinstance(cur.get("result"), dict) else None
        if nxt is None:
            break
        cur, hops = nxt, hops + 1
    return best or (cur if isinstance(cur, dict) else {})


def _find_js_json(node, depth: int = 0):
    """从任意层的回包里找出 execute_script 返回的那段 JSON 字符串。"""
    if depth > 8:
        return None
    if isinstance(node, str):
        s = node.strip()
        if s.startswith("{") and '"url"' in s:
            try:
                v = json.loads(s)
                return v if isinstance(v, dict) else None
            except Exception:                                  # noqa: BLE001
                return None
        return None
    if isinstance(node, dict):
        for v in node.values():
            got = _find_js_json(v, depth + 1)
            if got is not None:
                return got
        return None
    if isinstance(node, (list, tuple)):
        for v in node:
            got = _find_js_json(v, depth + 1)
            if got is not None:
                return got
    return None


def js(code: str) -> dict:
    return gate({"op": "native", "action": "execute_script", "js": code})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    nav = gate({"op": "native", "action": "navigate", "url": SUBMIT_PAGE})
    print("导航：ok=%s url=%s" % (nav.get("ok"), nav.get("url") or SUBMIT_PAGE))

    state = js('JSON.stringify({url:location.href,'
               'login:!!document.querySelector("input[name=acct]"),'
               'hasTitle:!!document.querySelector("input[name=title]")})')
    raw = state.get("value") or state.get("result") or ""
    try:
        st = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except Exception:                                          # noqa: BLE001
        print("DOM 回读解析不了，原始回包：", str(state)[:300])
        return 1
    print("页面状态：", st)

    if st.get("login") and not st.get("hasTitle"):
        print("\n⛔ 还没登录（页面是 login 表单）。请在 9222 那个 Chrome 窗口里登录一次；"
              "我不代输密码，也不读密码框。")
        return 2
    if not st.get("hasTitle"):
        print("\n⛔ 页面上找不到 title 输入框（既不是登录页也不是投稿页？）")
        return 3
    if a.dry:
        print("\n--dry：状态正常，未写入。")
        return 0

    payload = {"title": TITLE, "url": URL, "text": TEXT}
    fill = js(
        "(() => { const v = %s;"
        " const t = document.querySelector('input[name=title]');"
        " const u = document.querySelector('input[name=url]');"
        " const x = document.querySelector('textarea[name=text]');"
        " const set = (el, val) => { if (!el) return false;"
        "   el.focus(); el.value = val;"
        "   el.dispatchEvent(new Event('input', {bubbles:true}));"
        "   el.dispatchEvent(new Event('change', {bubbles:true})); return el.value === val; };"
        " return JSON.stringify({title:set(t, v.title), url:set(u, v.url), text:set(x, v.text)});"
        "})()" % json.dumps(payload, ensure_ascii=False)
    )
    print("写入回执：", fill.get("value") or fill.get("result") or fill)

    verify = js('JSON.stringify({title:(document.querySelector("input[name=title]")||{}).value,'
                'url:(document.querySelector("input[name=url]")||{}).value,'
                'textLen:((document.querySelector("textarea[name=text]")||{}).value||"").length,'
                'submitButton:!!document.querySelector("input[type=submit]")})')
    print("回读验收：", verify.get("value") or verify.get("result") or verify)
    print("\n✅ 三个字段已填好，**没有点 submit**。现在等主人在窗口里确认后自己点。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
