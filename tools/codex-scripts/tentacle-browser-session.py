# -*- coding: utf-8 -*-
r"""tentacle-browser-session -- 一根触手的隔离无痕浏览器会话（playwright 持久化 profile · Edge 通道）。

由 tools/codex-scripts/tentacle-gear.py browser 调起；**不单独当人用**。
  参数：<profile目录> <起始url> <headless 0|1> <超时秒(0=等关)> <会话记录.json> <自动关秒(0=等关)>
隔离口径：profile 每根触手一个（%LOCALAPPDATA%\gbt-tentacle-browser\<tid>\）——
  cookie/登录态只归这根触手，与人用的 Edge 不共享，也与别的触手不共享。
退出：窗口全关 / 超时 / 自动关 三者最先发生；会话记录（起止/时长/页面数）落盘供审计。
"""
import json
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")   # type: ignore[attr-defined]
    except Exception:
        pass


def main() -> int:
    profile, url, headless_s, tmo_s, rec_path, auto_s = sys.argv[1:7]
    headless = headless_s == "1"
    timeout = float(tmo_s or 0)
    auto = float(auto_s or 0)
    rec = {"profile": profile, "url": url, "headless": headless,
           "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": False}
    t0 = time.time()
    pages_max = 0
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                profile, channel="msedge", headless=headless,
                no_viewport=not headless,
                args=["--no-first-run", "--no-default-browser-check",
                      "--disable-features=msEdgeSidebarV2"])
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            if url and url != "about:blank":
                try:
                    page.goto(url, timeout=60000)
                except Exception as e:                        # noqa: BLE001
                    rec["goto_error"] = str(e)[:200]
            if auto > 0:                                       # 快检模式：到点主动关
                time.sleep(auto)
                try:
                    ctx.close()
                except Exception:                              # noqa: BLE001
                    pass
                rec["auto_closed"] = True
            else:                                              # 人等关 / 超时兜底
                while True:
                    time.sleep(0.5)
                    alive = [pg for pg in ctx.pages if not pg.is_closed()]
                    pages_max = max(pages_max, len(alive))
                    if not alive:
                        break
                    if timeout and (time.time() - t0) >= timeout:
                        rec["timeout_hit"] = True
                        try:
                            ctx.close()
                        except Exception:                      # noqa: BLE001
                            pass
                        break
            try:
                pages_max = max(pages_max, len([pg for pg in ctx.pages if not pg.is_closed()]))
            except Exception:                                  # noqa: BLE001
                pass
            rec["pages_max"] = pages_max
            rec["seconds"] = round(time.time() - t0, 1)
            rec["closed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            rec["ok"] = True
    except Exception as e:                                    # noqa: BLE001
        rec["error"] = "%s: %s" % (type(e).__name__, str(e)[:300])
    if rec_path:
        with open(rec_path, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)
    print(json.dumps(rec, ensure_ascii=False))
    return 0 if rec.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
