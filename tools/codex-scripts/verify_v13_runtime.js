/* V12 运行期验证：stub DOM 里真跑 30 个面板 + 上帝视角，抓 undefined / 抛错 / 空输出。
   不是语法检查 —— 是把每个面板函数真调一遍，看它吐不吐 HTML。 */
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'V13 GBT小土豆V8-可交互原型.html'), 'utf8');
const m = html.match(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/);
if (!m) { console.error('没找到内联脚本'); process.exit(2); }
let code = m[1];

/* 在 IIFE 收口处挂出待测函数 */
/* 行尾可能是 CRLF，用正则匹配收口 */
const closeRe = /renderSessions\(\); renderComposer\(\); renderPanel\(\); syncSend\(\);\s*\}\)\(\);/;
if (!closeRe.test(code)) { console.error('IIFE 收口锚点未命中'); process.exit(2); }
const names = ['panelChat','panelSquare','panelBrain','panelDomains','panelAudit','panelHealth',
  'panelSettings','panelVoice','panelBluetooth','panelPlug','panelTentacle','panelMirror',
  'panelLLM','panelMind','panelRecon','panelSecurity','panelLongrun','panelCreate','panelOthers',
  'panelMarket','panelShell','panelSesshead','panelComposer2','panelViewring','panelToolcard',
  'panelGateask','panelSubskill','panelRightpane','panelSettingsX','panelOpenapp',
  'panelWsOverview','panelWsGap','panelWsHolo','panelWsPotato','panelWsFive','panelWsDesign',
  'panelWsRecon30','panelWsAesth','panelWsQuant','panelWsLedger',
  'slotMatrixCard','treeCard','wsCoverCard','renderGod','renderPanel'];
code = code.replace(closeRe,
  'renderSessions(); renderComposer();\n' +
  'globalThis.__T = { ' + names.map(n => n + ': ' + n).join(', ') + ', st: st, NAV: NAV, V13: V13 };\n})();');

/* ── stub DOM ── */
function mkEl(id) {
  const el = {
    id, _html: '', textContent: '', value: '', checked: false, dataset: {},
    style: new Proxy({}, { get: (t, k) => t[k] || '', set: (t, k, v) => { t[k] = v; return true; } }),
    classList: { _s: new Set(), add(c){this._s.add(c);}, remove(c){this._s.delete(c);},
                 toggle(c,f){ if(f===undefined){this._s.has(c)?this._s.delete(c):this._s.add(c);} else {f?this._s.add(c):this._s.delete(c);} },
                 contains(c){return this._s.has(c);} },
    set innerHTML(v) { this._html = String(v); }, get innerHTML() { return this._html; },
    addEventListener() {}, removeEventListener() {}, setAttribute() {}, getAttribute() { return null; },
    querySelector() { return null; }, querySelectorAll() { return []; },
    appendChild() {}, removeChild() {}, remove() {}, focus() {}, blur() {}, click() {},
    closest() { return null; }, getBoundingClientRect() { return { width: 1400, height: 900, top:0, left:0 }; },
    scrollTop: 0, scrollHeight: 100, offsetWidth: 100, offsetHeight: 100, children: [], firstChild: null,
  };
  return el;
}
const els = {};
const document_ = {
  getElementById(id) { return (els[id] = els[id] || mkEl(id)); },
  querySelector() { return null; }, querySelectorAll() { return []; },
  createElement(t) { return mkEl('new:' + t); },
  createElementNS(ns, t) { return mkEl('new:' + t); },
  addEventListener() {}, removeEventListener() {},
  body: mkEl('body'), documentElement: mkEl('html'), head: mkEl('head'),
  readyState: 'complete', cookie: '',
};
const window_ = {
  document: document_, innerWidth: 1512, innerHeight: 945, devicePixelRatio: 2,
  matchMedia() { return { matches: false, addEventListener() {}, addListener() {} }; },
  getComputedStyle() { return { getPropertyValue() { return '#000'; } }; },
  addEventListener() {}, removeEventListener() {}, setTimeout, clearTimeout, setInterval, clearInterval,
  requestAnimationFrame(cb) { return 0; }, cancelAnimationFrame() {},
  location: { href: 'file:///V12.html', search: '', hash: '' },
  navigator: { userAgent: 'node' }, localStorage: { getItem() { return null; }, setItem() {}, removeItem() {} },
};
window_.window = window_;
const ctx = { document: document_, window: window_, localStorage: window_.localStorage,
  navigator: window_.navigator, location: window_.location, getComputedStyle: window_.getComputedStyle,
  requestAnimationFrame: window_.requestAnimationFrame, matchMedia: window_.matchMedia,
  setTimeout, clearTimeout, setInterval, clearInterval, console, globalThis: globalThis };
ctx.globalThis = ctx;

/* ── 跑起来 ── */
const runner = new Function(...Object.keys(ctx), code);
let T;
try {
  runner(...Object.values(ctx));
  T = globalThis.__T || ctx.__T;
} catch (e) {
  console.error('✗ 脚本装载抛错:', e.message);
  console.error(e.stack.split('\n').slice(0, 5).join('\n'));
  process.exit(1);
}
if (!T) { console.error('✗ 没拿到导出钩子'); process.exit(1); }

let pass = 0, fail = 0;
const results = [];
function check(name, fn) {
  try {
    /* 🔴 面板必须真写进 DOM —— 只看 chatBody/godBody 的实际内容，
       不接受「只 return 不写」的函数（那种在真界面里就是空白）。 */
    const snapshot = () => ((els['chatBody'] || {}).innerHTML || '') + '\u0000' + ((els['godBody'] || {}).innerHTML || '');
    const before = snapshot();
    fn();
    const now = snapshot();
    let s;
    if (now === before) s = '';
    else s = now.split('\u0000').sort((a, b) => b.length - a.length)[0];
    if (!s || s.length < 60) { results.push(['FAIL', name, '未写入 DOM（输出过短 ' + s.length + '）']); fail++; return; }
    if (/undefined/.test(s)) {
      const hit = s.match(/.{0,60}undefined.{0,40}/);
      results.push(['FAIL', name, '含 undefined → …' + hit[0].replace(/\s+/g, ' ') + '…']); fail++; return;
    }
    if (/\[object Object\]|NaN|Infinity/.test(s)) {
      const hit = s.match(/.{0,50}(\[object Object\]|NaN|Infinity).{0,30}/);
      results.push(['FAIL', name, '含脏值 → …' + hit[0].replace(/\s+/g, ' ') + '…']); fail++; return;
    }
    results.push(['OK', name, s.length + ' 字符']); pass++;
  } catch (e) {
    const st = (e.stack || '').split('\n').slice(1, 3).map(l => l.trim().replace(/\s*\(.*?\)\s*$/, '')).join(' | ');
    results.push(['FAIL', name, '抛错: ' + e.message + '  〈' + st + '〉']); fail++;
  }
}

/* 纯字符串函数（由 renderGod 内部调用，不直接写 DOM） */
function checkFn(name, fn) {
  try {
    const s = String(fn() == null ? '' : fn());
    if (!s || s.length < 60) { results.push(['FAIL', name, '返回过短 ' + s.length]); fail++; return; }
    if (/undefined|\[object Object\]|NaN|Infinity/.test(s)) {
      results.push(['FAIL', name, '含脏值']); fail++; return;
    }
    results.push(['OK', name, s.length + ' 字符']); pass++;
  } catch (e) {
    results.push(['FAIL', name, '抛错: ' + e.message]); fail++;
  }
}

const PANELS = [['panelChat','对话'],['panelSquare','能力广场'],['panelBrain','大脑执行层'],
  ['panelDomains','领域分类'],['panelAudit','审计台账'],['panelHealth','系统体检'],
  ['panelSettings','设置'],['panelVoice','语音'],['panelBluetooth','蓝牙'],['panelPlug','万能插'],
  ['panelTentacle','亿万触手'],['panelMirror','镜像与晋升'],['panelLLM','大模型通道'],
  ['panelMind','心智与记忆'],['panelRecon','情报与观察'],['panelSecurity','安全攻防'],
  ['panelLongrun','长程与工具'],['panelCreate','创作与吞噬'],['panelOthers','其余域'],
  ['panelMarket','插件市场'],['panelShell','★外壳与侧栏'],['panelSesshead','★会话头部'],
  ['panelComposer2','★输入区席位'],['panelViewring','★对话视图环'],['panelToolcard','★工具卡片'],
  ['panelGateask','★权限与提问'],['panelSubskill','★子代理与技能'],['panelRightpane','★右侧栏与预览'],
  ['panelSettingsX','★设置中心'],['panelOpenapp','★外部应用直通'],
  ['panelWsOverview','☆工作区源码总览'],['panelWsGap','☆缺口对账'],
  ['panelWsHolo','☆全息面板桥'],['panelWsPotato','☆桌面数字人'],
  ['panelWsFive','☆五维合一'],['panelWsDesign','☆设计大脑'],
  ['panelWsRecon30','☆情报流水线'],['panelWsAesth','☆审美技能'],
  ['panelWsQuant','☆量化与钱包'],['panelWsLedger','☆账本与审美脑']];
PANELS.forEach(([fn, zh]) => check(zh + ' (' + fn + ')', () => T[fn]()));

check('上帝视角 renderGod', () => { T.renderGod(); });
checkFn('席位矩阵卡 slotMatrixCard', () => T.slotMatrixCard());
checkFn('项目树卡 treeCard', () => T.treeCard());
checkFn('源码覆盖卡 wsCoverCard', () => T.wsCoverCard());

/* 逐导航项走一遍 renderPanel，确认分发不漏 */
const navKeys = T.NAV.map(n => n[1]);
navKeys.forEach(k => check('分发 nav=' + k, () => { T.st.nav = k; T.renderPanel(); }));

console.log('═'.repeat(76));
console.log('V12 运行期验证 · stub DOM 内真调每个面板');
console.log('═'.repeat(76));
results.forEach(r => console.log((r[0] === 'OK' ? '  ✓ ' : '  ✗ ') + r[1].padEnd(34) + r[2]));
console.log('─'.repeat(76));
console.log('通过 %d · 失败 %d · 共 %d', pass, fail, pass + fail);
console.log('导航项 %d 个:', navKeys.length);
console.log('席位真相: 官方 %d 席 / 已实现 %d / 缺口 %d',
  T.V13.dsh.n_total, T.V13.dsh.n_implemented, T.V13.dsh.n_missing);
const missingNames = T.V13.dsh.missing.filter(s => T.V13.dsh.slot_owner[s] === undefined);
console.log('缺口里有 %d 个没有注册方（应为 0）', missingNames.length);
process.exit(fail ? 1 : 0);
