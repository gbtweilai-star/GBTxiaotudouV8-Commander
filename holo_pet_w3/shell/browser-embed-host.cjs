'use strict';
/* ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
 * 我们自己的原生浏览器宿主（browser_embed）—— Electron WebContentsView。
 *
 * 对照上游参考项目 `electron/browser-embed-host.cjs` 的**架构**（WebContentsView 子视图 +
 * 主进程统一管分区/边界/下载/权限），只取设计，不搬代码。
 * 契约真源在 Python：`gbt_allinone/tools/browser_embed.py`（URL/边界/标签/下载名判据）。
 *
 * 用法：
 *   const host = require('./browser-embed-host.cjs');
 *   host.install({ app, ipcMain, session, WebContentsView, shell, getWindow: () => win });
 *   渲染进程经 preload `window.gbtBrowser` 调 IPC `browser:embed`。
 */

const path = require('path');
const fs = require('fs');

const PARTITION = 'persist:gbt-browser';
const MAX_TABS = 12;
const SEARCH_BASE = 'https://www.bing.com/search?q=';

function normalizeUrl(raw) {
  var s = String(raw || '').trim();
  if (!s) return { ok: false, reason: 'empty' };
  if (s.length > 4096) return { ok: false, reason: 'too_long' };
  var low = s.toLowerCase();
  if (low.indexOf('://') >= 0) {
    var scheme = low.split('://')[0];
    if (scheme !== 'http' && scheme !== 'https') {
      return { ok: false, reason: 'scheme_not_allowed', scheme: scheme };
    }
    return { ok: true, url: s };
  }
  if (/^(javascript|data|file|vbscript|about|chrome|edge):/.test(low)) {
    return { ok: false, reason: 'scheme_not_allowed' };
  }
  if (/^[\w-]+(\.[\w-]+)+([/:?#].*)?$/.test(s)) return { ok: true, url: 'https://' + s };
  if (/^localhost(:\d+)?(\/.*)?$/.test(s)) return { ok: true, url: 'http://' + s };
  return { ok: true, url: SEARCH_BASE + encodeURIComponent(s), search: true };
}

function sanitizeDownloadName(name) {
  var s = String(name || '').trim().replace(/\\/g, '/').split('/').pop();
  s = s.replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').replace(/^[ .]+|[ .]+$/g, '');
  if (!s || /^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$/i.test(s)) return 'download';
  if (s.length > 180) {
    var i = s.lastIndexOf('.');
    s = i > 0 ? s.slice(0, 170) + s.slice(i, i + 9) : s.slice(0, 180);
  }
  return s;
}

function install(opts) {
  const app = opts.app;
  const ipcMain = opts.ipcMain;
  const session = opts.session;
  const WebContentsView = opts.WebContentsView;
  const getWindow = opts.getWindow;
  const shell = opts.shell;
  if (typeof WebContentsView !== 'function') {
    return { ok: false, error: 'WebContentsView unavailable（Electron 版本太旧）' };
  }

  var tabs = [];
  var activeId = null;
  var nextId = 1;
  var bounds = { x: 0, y: 0, width: 0, height: 0 };
  var visible = false;
  var lastError = '';

  function win() { try { return getWindow(); } catch (e) { return null; } }

  function emit(payload) {
    var w = win();
    if (!w || w.isDestroyed()) return;
    try { w.webContents.send('browser:embed:event', payload); } catch (e) {}
  }

  function state() {
    var active = tabById(activeId);
    return {
      ok: true,
      visible: visible,
      active: activeId,
      tabs: tabs.map(function (t) {
        return { id: t.id, url: t.url, title: t.title, loading: !!t.loading };
      }),
      url: active ? active.url : '',
      title: active ? active.title : '',
      canGoBack: active ? active.view.webContents.navigationHistory.canGoBack() : false,
      canGoForward: active ? active.view.webContents.navigationHistory.canGoForward() : false,
      error: lastError || null
    };
  }

  function tabById(id) {
    for (var i = 0; i < tabs.length; i++) if (tabs[i].id === id) return tabs[i];
    return null;
  }

  function downloadDir() {
    var d = path.join(app.getPath('downloads'), 'GBT浏览器');
    try { fs.mkdirSync(d, { recursive: true }); } catch (e) {}
    return d;
  }

  function attach(tab) {
    var w = win();
    if (!w || !tab) return;
    if (tab.attached) return;
    try { w.contentView.addChildView(tab.view); tab.attached = true; } catch (e) { lastError = String(e); }
  }

  function detach(tab) {
    var w = win();
    if (!w || !tab || !tab.attached) return;
    try { w.contentView.removeChildView(tab.view); } catch (e) {}
    tab.attached = false;
  }

  function applyBounds() {
    var w = win();
    var tab = tabById(activeId);
    if (!w || !tab) return;
    var z = 1;
    try { z = w.webContents.getZoomFactor() || 1; } catch (e) {}
    var b = {
      x: Math.round(bounds.x * z), y: Math.round(bounds.y * z),
      width: Math.round(bounds.width * z), height: Math.round(bounds.height * z)
    };
    try { tab.view.setBounds(b); } catch (e) {}
  }

  function apply() {
    if (!visible) {
      tabs.forEach(function (t) { detach(t); });
      return;
    }
    var tab = tabById(activeId);
    if (!tab) return;
    tabs.forEach(function (t) { if (t !== tab) detach(t); });
    attach(tab);
    applyBounds();
  }

  function newTab(url) {
    if (tabs.length >= MAX_TABS) return { ok: false, error: 'too_many_tabs' };
    var id = nextId++;
    var view = new WebContentsView({
      webPreferences: {
        partition: PARTITION,
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
        spellcheck: false
      }
    });
    var tab = { id: id, url: '', title: '新标签页', loading: false, view: view, attached: false };
    var wc = view.webContents;
    wc.setWindowOpenHandler(function (info) {
      var n = normalizeUrl(info && info.url);
      if (n.ok) { navigateIn(tab, n.url); return { action: 'deny' }; }
      return { action: 'deny' };
    });
    wc.on('will-navigate', function (e, u) { if (!normalizeUrl(u).ok) e.preventDefault(); });
    wc.on('did-navigate', function (_e, u) { tab.url = u; emit({ type: 'navigate', tabId: tab.id, url: u }); });
    wc.on('did-navigate-in-page', function (_e, u) { tab.url = u; emit({ type: 'navigate', tabId: tab.id, url: u }); });
    wc.on('page-title-updated', function (_e, title) { tab.title = String(title || ''); emit({ type: 'title', tabId: tab.id, title: tab.title }); });
    wc.on('did-start-loading', function () { tab.loading = true; emit({ type: 'loading', tabId: tab.id, loading: true }); });
    wc.on('did-stop-loading', function () { tab.loading = false; emit({ type: 'loading', tabId: tab.id, loading: false, url: tab.url }); });
    wc.on('did-fail-load', function (_e, code, desc, u) {
      if (code === -3) return;
      lastError = desc || String(code);
      emit({ type: 'fail', tabId: tab.id, code: code, error: lastError, url: u });
    });
    try {
      wc.session.setPermissionRequestHandler(function (_wc, _permission, cb) { cb(false); });
      wc.session.setPermissionCheckHandler(function () { return false; });
      wc.session.on('will-download', function (_e, item) {
        var name = sanitizeDownloadName(item.getFilename());
        var target = path.join(downloadDir(), name);
        try { item.setSavePath(target); } catch (e) { lastError = String(e); }
        emit({ type: 'download', name: name, path: target, state: 'started' });
        item.once('done', function (_ev, st) {
          emit({ type: 'download', name: name, path: target, state: st });
        });
      });
    } catch (e) { lastError = String(e); }
    tabs.push(tab);
    activeId = id;
    if (url) navigateIn(tab, url);
    apply();
    return { ok: true, id: id, state: state() };
  }

  function navigateIn(tab, url) {
    if (!tab) return { ok: false, error: 'no_tab' };
    var n = normalizeUrl(url);
    if (!n.ok) return { ok: false, error: n.reason || 'bad_url' };
    tab.url = n.url;
    try { tab.view.webContents.loadURL(n.url); } catch (e) { lastError = String(e); return { ok: false, error: lastError }; }
    emit({ type: 'navigate', tabId: tab.id, url: n.url });
    return { ok: true, url: n.url };
  }

  function activeTab() { return tabById(activeId); }

  function handle(payload) {
    var op = String((payload && payload.op) || 'state');
    try {
      if (op === 'show') {
        bounds = payload.bounds || bounds;
        visible = true;
        if (!activeTab()) newTab('about:blank');
        apply();
        return state();
      }
      if (op === 'hide') { visible = false; apply(); return state(); }
      if (op === 'setBounds') { bounds = payload.bounds || bounds; applyBounds(); return state(); }
      if (op === 'state') return state();
      if (op === 'navigate') {
        var r = navigateIn(activeTab(), payload.url);
        return Object.assign({}, state(), r);
      }
      if (op === 'newTab') {
        var nt = newTab(payload.url || 'about:blank');
        return Object.assign({}, state(), nt);
      }
      if (op === 'switchTab') {
        if (!tabById(Number(payload.id))) return { ok: false, error: 'no_such_tab' };
        activeId = Number(payload.id);
        apply();
        return state();
      }
      if (op === 'closeTab') {
        var id = Number(payload.id);
        var idx = tabs.findIndex(function (t) { return t.id === id; });
        if (idx < 0) return { ok: false, error: 'no_such_tab' };
        var t = tabs[idx];
        detach(t);
        try { t.view.webContents.close(); } catch (e) {}
        tabs.splice(idx, 1);
        if (activeId === id) {
          activeId = tabs.length ? tabs[Math.min(idx, tabs.length - 1)].id : null;
        }
        if (!tabs.length && visible) { newTab('about:blank'); }
        apply();
        return state();
      }
      var tab = activeTab();
      if (!tab) return { ok: false, error: 'no_tab' };
      if (op === 'back') { if (tab.view.webContents.navigationHistory.canGoBack()) tab.view.webContents.navigationHistory.goBack(); return state(); }
      if (op === 'forward') { if (tab.view.webContents.navigationHistory.canGoForward()) tab.view.webContents.navigationHistory.goForward(); return state(); }
      if (op === 'reload') { tab.view.webContents.reload(); return state(); }
      if (op === 'stop') { tab.view.webContents.stop(); return state(); }
      return { ok: false, error: 'unknown_op:' + op };
    } catch (e) {
      lastError = String(e);
      return { ok: false, error: lastError };
    }
  }

  ipcMain.handle('browser:embed', function (_e, payload) { return handle(payload || {}); });
  try {
    session.fromPartition(PARTITION).setPermissionRequestHandler(function (_wc, _p, cb) { cb(false); });
    session.fromPartition(PARTITION).setPermissionCheckHandler(function () { return false; });
  } catch (e) {}
  var w = win();
  if (w) w.on('closed', function () { tabs.forEach(function (t) { try { t.view.webContents.close(); } catch (e) {} }); tabs = []; });
  return { ok: true };
}

module.exports = { install: install, normalizeUrl: normalizeUrl, sanitizeDownloadName: sanitizeDownloadName };
