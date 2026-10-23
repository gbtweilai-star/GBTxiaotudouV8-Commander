#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 shell/nav-compact.js（唯一写入口）。

为什么要有生成器（而不是手写那个 js）：
  2026-10-21 实测抓到 `shell/nav-compact.js` 被写成**半截残件** —— 文件末尾
  `.catch(` 的处理体被整段数据行覆盖，紧接着又多出一句 `mount([])`，
  于是「无内联数据」那条路上会**先挂一条空导航、再挂一条真导航**（两条叠在页头）。
  残件的形状是「同一文件头被写了两遍」，属于本仓 P5（长会话写出多件混写的坏件）。
  根治办法不是再手改一次，而是让这个文件**只有生成器一个写手**：
    · 数据唯一来源 = shell/nav-index.json（由 compact-app-nav.py 从 windows.json 生成）
    · 本脚本把数据内联进 js（file:// 下 fetch 被 CORS 挡死，必须内联）
    · 输出模板在下面写死一遍，跑几次都是同一份字节

用法：
  python tools/codex-scripts/gen-nav-compact.py            # 写盘
  python tools/codex-scripts/gen-nav-compact.py --check    # 只比对，不写
"""
import argparse
import hashlib
import json
import os
import sys
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SHELL = os.path.join(REPO, "holo_pet_w3", "shell")
INDEX = os.path.join(SHELL, "nav-index.json")
OUT = os.path.join(SHELL, "nav-compact.js")

# 7 个主入口：id 必须真实存在于 nav-index.json（找不到就灰掉，不瞎跳）
PRIMARY = [
    ("digital-human", "她"),
    ("dsh-chat", "对话"),
    ("panel", "面板"),
    ("capabilities", "能力"),
    ("energy", "能量"),
    ("logbook", "记录"),
    ("blueprint", "蓝图"),
]

TEMPLATE = """/* GBT小土豆V8 · 紧凑导航（唯一一份 · 由 tools/codex-scripts/gen-nav-compact.py 生成，别手改）
 * 设计：品牌 + 7 个主入口 + 一个可折叠的「更多」，其余入口收进折叠区，永不丢。
 * 数据源：shell/nav-index.json（数据本行内联 —— file:// 下 fetch 会被 CORS 挡死）
 * 什么时候**不画**（2026-10-21 主人令「一堆东西推挤在一起」的根治）：
 *   ① 页面里先写 window.GBT_NAV_DISABLE = true        —— 例如控制面板，它有自己的左栏；
 *   ② window.gbtW3 在（= 运行在壳里）                  —— 壳的标题栏本来就有一条窗口切换条，
 *      再画一条 = 60px 内两条导航。壳外（普通浏览器打开）照旧画，页面照样能到处跳。
 *   想强行画回来：window.GBT_NAV_FORCE = true
 */
window.GBT_NAV_INDEX = __DATA__;
(function () {
  if (window.GBT_NAV_FORCE) { /* 强行画：跳过下面两道闸 */ }
  else if (window.GBT_NAV_DISABLE) return;
  else if (window.gbtW3) return;   /* 壳里：标题栏已有窗口切换条，别再画一条 */
  var ME = document.currentScript;
  var ROOT = (ME && ME.src || '').replace(/\\/shell\\/nav-compact\\.js.*$/, '');
  var PRIMARY = __PRIMARY__;

  function css() {
    return '' +
      '#gbt-nav{position:sticky;top:0;z-index:99;display:flex;align-items:center;gap:10px;' +
      'padding:6px 12px;font:13px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;' +
      'background:rgba(11,13,18,.92);backdrop-filter:blur(8px);color:#e8ecef;' +
      'border-bottom:1px solid rgba(255,255,255,.08)}' +
      '#gbt-nav .b{font-weight:700;letter-spacing:.5px;color:#f2c14e}' +
      '#gbt-nav a{color:#cfd6dd;text-decoration:none;padding:2px 8px;border-radius:8px}' +
      '#gbt-nav a:hover{background:rgba(242,193,78,.14);color:#fff}' +
      '#gbt-nav .sp{flex:1}' +
      '#gbt-nav details{position:relative}' +
      '#gbt-nav summary{cursor:pointer;list-style:none;padding:2px 10px;border-radius:8px;' +
      'border:1px solid rgba(255,255,255,.14);color:#cfd6dd}' +
      '#gbt-nav summary::-webkit-details-marker{display:none}' +
      '#gbt-nav .panel{position:absolute;right:0;top:130%;width:min(720px,86vw);max-height:60vh;' +
      'overflow:auto;background:#12151c;border:1px solid rgba(255,255,255,.12);border-radius:12px;' +
      'padding:10px 12px;box-shadow:0 18px 50px rgba(0,0,0,.55)}' +
      '#gbt-nav .panel h4{margin:8px 0 4px;font-size:12px;color:#8b97a5;font-weight:600}' +
      '#gbt-nav .panel a{display:inline-block;font-size:12px;margin:0 2px 2px 0}';
  }

  function short(label) {
    return String(label || '').replace(/^GBT小土豆V8\\s*·\\s*/, '');
  }

  function build(list) {
    var el = document.createElement('div');
    el.id = 'gbt-nav';
    var byId = {};
    (list || []).forEach(function (it) { if (it.id) byId[it.id] = it.path; });
    var h = '<span class="b">GBT小土豆V8</span>';
    PRIMARY.forEach(function (p) {
      var path = byId[p[0]];
      if (path) h += '<a data-id="' + p[0] + '" href="' + ROOT + '/' + path + '">' + p[1] + '</a>';
      else h += '<a data-id="' + p[0] + '" style="opacity:.45" title="这一版没有这个窗">' + p[1] + '</a>';
    });
    h += '<span class="sp"></span>';
    var groups = {};
    (list || []).forEach(function (it) {
      var g = it.group || '其他';
      (groups[g] = groups[g] || []).push(it);
    });
    var n = (list || []).length;
    h += '<details><summary>更多（' + n + '）</summary><div class="panel">';
    Object.keys(groups).sort().forEach(function (g) {
      h += '<h4>' + g + '</h4>';
      groups[g].forEach(function (it) {
        h += '<a href="' + ROOT + '/' + it.path + '">' + short(it.label) + '</a>';
      });
    });
    h += '</div></details>';
    el.innerHTML = h;
    return el;
  }

  function mount(list) {
    if (document.getElementById('gbt-nav')) return;   /* 只许挂一条 */
    var st = document.createElement('style');
    st.textContent = css();
    document.head.appendChild(st);
    var bar = build(list);
    var host = document.getElementById('gbt-direct-nav');
    if (host && host.parentNode) host.parentNode.replaceChild(bar, host);
    else document.body.insertBefore(bar, document.body.firstChild);
    window.__GBT_NAV = { count: (list || []).length, primary: PRIMARY.length };
  }

  /* 数据已内联 ⇒ 永远同步挂载，不再走 fetch（原 fetch 分支在 file:// 下必然失败，
     且是残件的来源）。这条路径就一条，跑几次都一样。 */
  mount(window.GBT_NAV_INDEX.links || []);
})();
"""


def render():
    with open(INDEX, encoding="utf-8") as fh:
        idx = json.load(fh)
    links = idx.get("links") or []
    data = json.dumps({"schema": idx.get("schema", "gbt-nav/v1"), "links": links},
                      ensure_ascii=False, separators=(",", ":"))
    primary = json.dumps([[i, t] for i, t in PRIMARY], ensure_ascii=False)
    # 不用 % 格式化：模板里有 CSS 的 `top:130%` 会跟格式符打架
    return TEMPLATE.replace("__DATA__", data).replace("__PRIMARY__", primary)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只比对，不写盘")
    args = ap.parse_args()

    body = render()
    old = None
    if os.path.isfile(OUT):
        with open(OUT, encoding="utf-8") as fh:
            old = fh.read()

    if args.check:
        same = old == body
        print(json.dumps({
            "check": True,
            "same": same,
            "old_sha16": hashlib.sha256((old or "").encode()).hexdigest()[:16],
            "new_sha16": hashlib.sha256(body.encode()).hexdigest()[:16],
            "out": OUT,
        }, ensure_ascii=False))
        return 0 if same else 1

    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
    os.replace(tmp, OUT)   # 原子替换：旧版不保留
    print(json.dumps({
        "wrote": OUT,
        "bytes": len(body.encode("utf-8")),
        "sha16": hashlib.sha256(body.encode("utf-8")).hexdigest()[:16],
        "links": len(json.load(open(INDEX, encoding="utf-8")).get("links") or []),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
