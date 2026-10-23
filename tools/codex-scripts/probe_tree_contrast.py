# -*- coding: utf-8 -*-
"""工作树为什么这么暗 —— 在真浏览器里量计算样式，不猜。

读 render/godview/tree_工作树.png 时肉眼看到：整棵树对比度极低。
候选原因（都要用实测排除）：
  ① .gbt-node[data-hit="false"]{opacity:.32} —— 空搜索框误判成"不命中"
  ② data-state="off" 的 --gbt-off(#6B7280) 灰字压深底
  ③ 祖先节点 opacity/滤镜叠加
"""
from __future__ import annotations

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


BRIDGE = "(() => { const P=%s; const call=(n)=>Promise.resolve(P[n]||{ok:false,error:'未取 '+n});" \
         "window.gbtW3={readonly:true,config:()=>call('w3:config'),state:()=>call('w3:state')," \
         "tasks:()=>call('w3:tasks'),env:()=>call('w3:env'),ledger:()=>call('w3:ledger')," \
         "health:()=>call('w3:health'),matrix:()=>call('w3:matrix'),mindmap:()=>call('w3:mindmap')," \
         "selfcheck:()=>call('w3:selfcheck'),introspect:()=>call('w3:introspect'),tools:()=>call('w3:tools')," \
         "h1:()=>call('w3:h1'),pets:()=>call('w3:pets'),summon:()=>call('w3:summon')," \
         "eigenflux:()=>call('w3:eigenflux'),onEvent:()=>{},onStreamState:()=>{}};})();" % json.dumps(
             {k: payload(k) for k in ("w3:config", "w3:state", "w3:tasks", "w3:env", "w3:ledger", "w3:health",
                                      "w3:matrix", "w3:mindmap", "w3:selfcheck", "w3:introspect", "w3:tools",
                                      "w3:h1", "w3:pets", "w3:summon", "w3:eigenflux")}, ensure_ascii=False)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME, args=["--allow-file-access-from-files"])
    pg = b.new_page(viewport={"width": 1080, "height": 680})
    pg.add_init_script(BRIDGE)
    pg.goto(PAGE.as_uri(), wait_until="load")
    pg.wait_for_timeout(1500)
    pg.click('.gbt-tab[data-view="tree"]')
    pg.wait_for_timeout(1200)

    rep = pg.evaluate("""() => {
      const host = document.getElementById('tree-host');
      const nodes = [...document.querySelectorAll('#tree-host .gbt-node')];
      const labels = nodes.map(n => n.querySelector('.gbt-node-label')).filter(Boolean);
      const sample = labels.slice(0, 6).map(l => {
        const cs = getComputedStyle(l);
        return {text: (l.textContent||'').slice(0,26), color: cs.color, opacity: cs.opacity,
                border: cs.borderLeftColor, fs: cs.fontSize};
      });
      const hits = nodes.map(n => n.dataset.hit);
      const states = nodes.map(n => n.dataset.state);
      return {
        engine: host ? host.dataset.engine : null,
        node_count: nodes.length,
        label_count: labels.length,
        search_value: document.getElementById('search-box').value,
        hit_true: hits.filter(v => v === 'true').length,
        hit_false: hits.filter(v => v === 'false').length,
        hit_undef: hits.filter(v => v === undefined).length,
        state_counts: states.reduce((a,s)=>{a[s||'(none)']=(a[s||'(none)']||0)+1;return a;},{}),
        host_opacity: host ? getComputedStyle(host).opacity : null,
        sample,
      };
    }""")
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    b.close()
