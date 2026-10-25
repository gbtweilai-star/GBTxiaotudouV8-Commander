# -*- coding: utf-8 -*-
"""驾驶舱滚到底，单独截「渲染进化 · 最优基因」那块（它在折叠线以下）。"""
import json
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright  # noqa: E402

full = json.loads((ROOT / ".scratch" / "_god_view_full.json").read_text(encoding="utf-8"))["channels"]
keys = ("w3:config", "w3:state", "w3:tasks", "w3:env", "w3:ledger", "w3:health", "w3:matrix",
        "w3:mindmap", "w3:selfcheck", "w3:introspect", "w3:tools", "w3:h1", "w3:pets",
        "w3:summon", "w3:eigenflux", "w3:coverage", "w3:orphans", "w3:gene")


def payload(n):
    return (full.get(n) or {}).get("value") or {"ok": False, "error": "未取"}


BRIDGE = ("(() => { const P=%s; const call=(n)=>Promise.resolve(P[n]||{ok:false,error:'未取'});"
          "window.gbtW3={readonly:true," %
          json.dumps({k: payload(k) for k in keys}, ensure_ascii=False) +
          ",".join("%s:()=>call('%s')" % (k.split(":")[1], k) for k in keys) +
          ",onEvent:()=>{},onStreamState:()=>{}};})();")

OUT = ROOT / "render" / "godview"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                          args=["--allow-file-access-from-files"])
    pg = b.new_page(viewport={"width": 1080, "height": 680}, device_scale_factor=2)
    pg.add_init_script(BRIDGE)
    pg.goto((ROOT / "holo_pet_w3/index.html").as_uri(), wait_until="load")
    pg.wait_for_timeout(1000)
    pg.evaluate("""() => document.querySelector('.gbt-tab[data-view="cockpit"]').click()""")
    pg.wait_for_timeout(600)
    for bid in ("btn-coverage", "btn-orphans", "btn-gene"):
        pg.evaluate("(id) => { const e=document.getElementById(id); if(e) e.click(); }", bid)
        pg.wait_for_timeout(1200)

    rep = pg.evaluate("""() => {
      const v = document.getElementById('view-cockpit');
      v.scrollTop = v.scrollHeight;
      const g = document.getElementById('gene-count');
      const rows = [...document.querySelectorAll('#gene-body tr')].map(tr =>
        [...tr.children].map(td => td.textContent + (td.className ? '['+td.className+']' : '')).join(' | '));
      return {
        scrollHeight: v.scrollHeight, clientHeight: v.clientHeight, scrollTop: v.scrollTop,
        gene_count: g ? g.textContent : null,
        gene_exp: document.getElementById('gene-exp').textContent,
        gene_at: document.getElementById('gene-at').textContent,
        winners: document.getElementById('gene-winners').innerText.slice(0, 220),
        primitives: rows,
        boundary: document.getElementById('gene-boundary').textContent.slice(0, 150),
      };
    }""")
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    pg.wait_for_timeout(400)
    card = pg.query_selector("#view-cockpit .gbt-card:last-of-type")
    if card:
        card.screenshot(path=str(OUT / "cockpit_最优基因.png"))
        print("\n单卡截图: render/godview/cockpit_最优基因.png")
    b.close()
