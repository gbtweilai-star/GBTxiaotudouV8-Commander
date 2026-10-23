# -*- coding: utf-8 -*-
"""构建 V10：把「项目树」放进上帝视角（按 @deepseek-ai/dsh-api-workspace-files 规格呈现）。"""
import re
import shutil
from pathlib import Path

BASE = next(p for p in Path(__file__).resolve().parents
            if (p / "gbt_allinone").is_dir())   # 修：原 `.parent.parent` 只到 tools/（少一层）
S = BASE / ".scratch"
V9P = BASE / "V9 GBT小土豆V8-可交互原型.html"
V10P = BASE / "V10 GBT小土豆V8-可交互原型.html"

for p in [BASE / "V9 GBT小土豆V8-无限画布.html", V9P]:
    if p.exists():
        shutil.copy2(p, BASE / "archive" / p.name)
        print("归档:", p.name)

src = V9P.read_text(encoding="utf-8")
src = src.replace("可交互原型 V9", "可交互原型 V10")
src = re.sub(r"\bV9\b", "V10", src)

new_json = (S / "v10_manifest.json").read_text(encoding="utf-8").strip()
src, n = re.subn(r"const V10 = /\* full snapshot \+ plugin market \*/\{.*?\};\n",
                 lambda m: "const V10 = /* full snapshot + plugin market + project tree */" + new_json + ";\n",
                 src, count=1, flags=re.S)
assert n == 1, "数据层替换失败"

# ── 树的三件代码：插在 drawNet 之前 ──
TREE_JS = r"""
  /* ── 项目树（规格：@deepseek-ai/dsh-api-workspace-files · workspaceFiles.list） ── */
  function treeHuman(bytes) {
    if (bytes == null) return '';
    var u = ['B', 'KB', 'MB', 'GB'], i = 0, v = bytes;
    while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
    return (i === 0 ? v : v.toFixed(1)) + ' ' + u[i];
  }
  function treePathHead(root) {
    var sep = root.indexOf('\\') >= 0 ? '\\' : '/';
    var parts = root.split(sep);
    var last = parts.pop();
    return '<span style="color:var(--ink-3)">' + esc(parts.join(sep) + sep) + '</span>' +
      '<span style="color:var(--ink)">' + esc(last) + '</span>';
  }
  function treeRow(e, depth, root) {
    var pad = 8 + depth * 15;
    var ico = e.kind === 'directory'
      ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" width="12" height="12" style="color:var(--neon-2)" aria-hidden="true"><path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"/></svg>'
      : e.kind === 'file'
        ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" width="12" height="12" style="color:var(--ink-3)" aria-hidden="true"><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/></svg>'
        : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" width="12" height="12" style="color:var(--ink-3);opacity:.5" aria-hidden="true"><circle cx="12" cy="12" r="8"/></svg>';
    var tail = e.kind === 'directory'
      ? '<span class="mono dim" style="font-size:9.5px">' + (e.count == null ? '—' : e.count + ' 项') + '</span>'
      : (e.kind === 'file' ? '<span class="mono dim" style="font-size:9.5px">' + treeHuman(e.bytes) + '</span>' : '<span class="mono dim" style="font-size:9.5px">other</span>');
    var clickable = e.kind !== 'other';
    var tag = clickable ? 'button' : 'div';
    var attrs = clickable
      ? ' data-tree="' + esc(e.name) + '" data-kind="' + esc(e.kind) + '"' + (e.kind === 'directory' ? ' aria-expanded="' + (!!e.entries) + '"' : '')
      : ' aria-disabled="true"';
    var out = '<' + tag + attrs + ' style="display:flex;align-items:center;gap:7px;width:100%;text-align:left;padding:3px 8px 3px ' + pad +
      'px;border-radius:3px;' + (clickable ? '' : 'opacity:.45;cursor:not-allowed;') + '">' +
      ico + '<span style="font-family:var(--mono);font-size:10.5px;color:' +
      (e.kind === 'other' ? 'var(--ink-3)' : 'var(--ink)') + ';flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' +
      esc(e.name) + '</span>' + tail + '</' + tag + '>';
    if (e.entries && e.entries.length) {
      out += e.entries.map(function (c) { return treeRow(c, depth + 1, root); }).join('');
      if (e.truncated) {
        out += '<div style="padding:3px 8px 3px ' + (pad + 15) + 'px;font-family:var(--mono);font-size:9.5px;color:var(--amber)">' +
          '已达单层上限 ' + (e.count || 0) + '，其余已丢弃（规格：maxEntries）</div>';
      }
    } else if (e.entries && !e.entries.length) {
      out += '<div style="padding:3px 8px 3px ' + (pad + 15) + 'px;font-family:var(--mono);font-size:9.5px;color:var(--ink-3)">此目录为空</div>';
    }
    if (e.errors && e.errors.length) {
      out += '<div style="padding:3px 8px 3px ' + (pad + 15) + 'px;font-family:var(--mono);font-size:9.5px;color:var(--rose)">' +
        e.errors.map(function (x) { return esc(x.code || 'error'); }).join(' · ') + '</div>';
    }
    return out;
  }
  function treeCard() {
    var TR = V10.tree || {}, T = TR.tree || {}, sp = TR.spec || {};
    var ent = T.entries || [];
    var dirs = ent.filter(function (e) { return e.kind === 'directory'; }).length;
    var files = ent.filter(function (e) { return e.kind === 'file'; }).length;
    var others = ent.filter(function (e) { return e.kind === 'other'; }).length;
    return '<div class="card" style="margin-bottom:11px"><div class="card-h"><b>项目树</b> / PROJECT TREE' +
      '<span class="r">' + esc(sp.source || '') + '</span></div>' +
      '<div class="card-b">' +
      '<div style="display:flex;align-items:center;gap:9px;padding:6px 8px;border-bottom:1px solid var(--line);margin-bottom:6px">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" width="13" height="13" style="color:var(--neon-2)" aria-hidden="true"><path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"/></svg>' +
      '<span class="mono" style="font-size:11px;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' +
      treePathHead(String(T.path || '')) + '</span>' +
      '<span class="mono dim" style="font-size:9.5px">' + (T.count || 0) + ' 项 · 目录 ' + dirs + ' / 文件 ' + files +
      (others ? ' / 其他 ' + others : '') + '</span>' +
      '<button class="pill" id="treeReload" style="height:22px;font-size:10px">重新读取</button></div>' +
      '<div id="treeBody" style="max-height:290px;overflow:auto">' +
      ent.map(function (e) { return treeRow(e, 0, T.path); }).join('') +
      (T.truncated ? '<div style="padding:4px 8px;font-family:var(--mono);font-size:9.5px;color:var(--amber)">' +
        '根层已达上限 ' + (sp.limits ? sp.limits.maxEntries_root : '') + '（该目录共 ' + (T.count || 0) + ' 项），其余已丢弃并标记 truncated</div>' : '') +
      (ent.length ? '' : '<div style="padding:10px 8px;font-size:10.5px;color:var(--ink-3)">该会话没有工作目录 —— 规格要求只显示一行说明，而不是树。</div>') +
      '</div>' +
      '<p style="font-size:9.5px;color:var(--ink-3);margin-top:8px;line-height:1.8">' +
      '规格要点：' + esc(sp.order || '') + ' · dotfiles ' + esc(sp.dotfiles || '') + ' · ' + esc(sp.other_row || '') +
      '<br>已知限制：' + esc(sp.known_limits || '') + '</p>' +
      '</div></div>';
  }
"""
anchor = "  function drawNet() {"
assert anchor in src, "drawNet 锚点未命中"
src = src.replace(anchor, TREE_JS.strip() + "\n\n" + anchor, 1)

# 把 treeCard() 插进上帝视角第一排之后、第二排之前
old_g = "      '<div class=\"grow2\">' +"
assert old_g in src, "grow2 锚点未命中"
src = src.replace(old_g, "      treeCard() +\n" + old_g, 1)

# 树的交互：点击目录折叠/展开、点击文件显示资源地址、重新读取
old_hook = "drawNet();\n    $('godBody').querySelectorAll('.tab').forEach"
new_hook = """drawNet();
    var tb = $('treeBody');
    if (tb) tb.addEventListener('click', function (ev) {
      var row = ev.target.closest('[data-tree]'); if (!row) return;
      var kind = row.getAttribute('data-kind');
      if (kind === 'directory') {
        var open = row.getAttribute('aria-expanded') === 'true';
        row.setAttribute('aria-expanded', String(!open));
        var sib = row.nextElementSibling;
        while (sib && sib.getAttribute && !sib.getAttribute('data-tree') && sib.tagName === 'DIV' && !sib.style.paddingLeft) {
          sib.style.display = open ? 'none' : ''; sib = sib.nextElementSibling;
        }
      }
    });
    var trl = $('treeReload');
    if (trl) trl.addEventListener('click', function () {
      trl.textContent = '读取中…';
      window.setTimeout(function () { trl.textContent = '重新读取'; }, 500);
    });
    $('godBody').querySelectorAll('.tab').forEach"""
assert old_hook in src, "钩子锚点未命中"
src = src.replace(old_hook, new_hook, 1)

V10P.write_text(src, encoding="utf-8")
print("写出:", V10P.name, len(V10P.read_bytes()), "B")
