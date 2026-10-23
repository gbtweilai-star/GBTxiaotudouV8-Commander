# -*- coding: utf-8 -*-
"""驾驶舱那两块为什么不填 —— 在真浏览器里问，不猜。"""
import json
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright  # noqa: E402

PAGE = ROOT / "holo_pet_w3" / "index.html"
FULL = ROOT / ".scratch" / "_god_view_full.json"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
full = json.loads(FULL.read_text(encoding="utf-8"))["channels"]


def payload(n):
    return (full.get(n) or {}).get("value") or {"ok": False, "error": "未取"}


keys = ("w3:config", "w3:state", "w3:tasks", "w3:env", "w3:ledger", "w3:health",
        "w3:matrix", "w3:mindmap", "w3:selfcheck", "w3:introspect", "w3:tools",
        "w3:h1", "w3:pets", "w3:summon", "w3:eigenflux", "w3:coverage", "w3:orphans")
BRIDGE = ("(() => { const P=%s; const call=(n)=>Promise.resolve(P[n]||{ok:false,error:'未取 '+n});"
          "window.gbtW3={readonly:true," %
          json.dumps({k: payload(k) for k in keys}, ensure_ascii=False) +
          ",".join("%s:()=>call('%s')" % (k.split(":")[1], k) for k in keys) +
          ",onEvent:()=>{},onStreamState:()=>{}};})();")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, args=["--allow-file-access-from-files"])
    pg = b.new_page(viewport={"width": 1080, "height": 680})
    logs = []
    pg.on("console", lambda m: logs.append(m.type + ": " + m.text[:160]))
    pg.on("pageerror", lambda e: logs.append("PAGEERROR: " + str(e)[:200]))
    pg.add_init_script(BRIDGE)
    pg.goto(PAGE.as_uri(), wait_until="load")
    pg.wait_for_timeout(1200)

    print("桥上有 coverage 吗:", pg.evaluate("() => typeof (window.gbtW3||{}).coverage"))
    print("按钮存在吗:", pg.evaluate("() => !!document.getElementById('btn-coverage')"))
    print("容器存在吗:", pg.evaluate("() => !!document.getElementById('cov-gaps')"))

    # 手动点，并同步等一次桥调用结果
    r = pg.evaluate("""async () => {
      const out = {};
      out.before = document.getElementById('cov-reportable').textContent;
      try {
        const resp = await window.gbtW3.coverage();
        out.bridge_ok = resp && resp.ok;
        out.bridge_keys = resp && resp.data ? Object.keys(resp.data) : null;
        out.raw_keys = resp && resp.data && resp.data.raw ? Object.keys(resp.data.raw) : null;
        out.reportable = resp && resp.data && resp.data.raw ? resp.data.raw.reportable_modules : null;
      } catch (e) { out.bridge_error = String(e); }
      const btn = document.getElementById('btn-coverage');
      btn.click();
      await new Promise(r => setTimeout(r, 600));
      out.after_click_reportable = document.getElementById('cov-reportable').textContent;
      out.after_click_gaps = document.getElementById('cov-gaps').innerText.slice(0, 200);
      out.after_click_at = document.getElementById('cov-at').textContent;
      return out;
    }""")
    print(json.dumps(r, ensure_ascii=False, indent=1))
    print("\n控制台:", logs[:8] or "(无)")
    b.close()
