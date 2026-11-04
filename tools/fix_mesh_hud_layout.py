# -*- coding: utf-8 -*-
import pathlib
import shutil

R = pathlib.Path(r"C:\Users\Lenovo E14 Gen 5\Desktop\GBT小土豆V8")
PAY = pathlib.Path(r"C:\Users\Lenovo E14 Gen 5\Desktop\GBT小土豆V8桌面版\payload")

# 1) index: reserve a layout slot under tabs (not floating over right panel)
for idx in (R / "holo_pet_w3/console/index.html", PAY / "holo_pet_w3/console/index.html"):
    t = idx.read_text(encoding="utf-8")
    if 'id="mesh-hud-slot"' not in t:
        anchor = "    </nav>\n\n    <!-- 视图 1：对话"
        assert anchor in t, idx
        t = t.replace(anchor, '    </nav>\n    <div id="mesh-hud-slot" class="mesh-hud-slot"></div>\n\n    <!-- 视图 1：对话', 1)
        idx.write_text(t, encoding="utf-8")
        print("slot", idx)

# 2) page-mesh: append HUD into slot
for js in (R / "holo_pet_w3/console/page-mesh.js", PAY / "holo_pet_w3/console/page-mesh.js"):
    t = js.read_text(encoding="utf-8")
    old = '''    hud.appendChild(btn);
    document.body.appendChild(hud);'''
    new = '''    hud.appendChild(btn);
    var slot = document.getElementById("mesh-hud-slot");
    if (slot) { hud.classList.add("in-slot"); slot.appendChild(hud); }
    else { document.body.appendChild(hud); }'''
    if old in t:
        js.write_text(t.replace(old, new, 1), encoding="utf-8")
        print("slot hud", js)

# 3) CSS: HUD in flow, no fixed overlay
for css in (R / "holo_pet_w3/console/app.css", PAY / "holo_pet_w3/console/app.css"):
    t = css.read_text(encoding="utf-8")
    old = '''#page-mesh-hud { position: fixed; right: 18px; bottom: 8px; z-index: 90; color: var(--dim);
  font: 400 8px/1.3 var(--mono); background: rgba(10,14,19,.6); border: 1px solid var(--line);
  border-radius: 8px; padding: 2px 7px; pointer-events: none; opacity: .75; }'''
    new = '''.mesh-hud-slot { flex: none; min-height: 16px; padding: 1px 2px 0; }
#page-mesh-hud { position: static; right: auto; bottom: auto; z-index: 4; color: var(--dim);
  font: 400 8px/1.3 var(--mono); background: transparent; border: 0;
  border-radius: 0; padding: 0; pointer-events: none; opacity: .8; display: flex;
  align-items: center; gap: 6px; flex-wrap: wrap; }'''
    if old in t:
        css.write_text(t.replace(old, new, 1), encoding="utf-8")
        print("slot css", css)
print("done")
