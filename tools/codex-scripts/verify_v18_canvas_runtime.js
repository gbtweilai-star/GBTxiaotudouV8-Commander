/* V11 画布运行期验证：抽出 scene 里所有顶层函数定义（含 helper 与 p1~p33），
   逐个真调，抓抛错 / undefined / 脏值 / 空页。
   不依赖画布模板 API —— 只验证页面字符串构建是否成立。 */
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'V18 GBT小土豆V8-无限画布.html'), 'utf8');
const m = html.match(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/);
if (!m) { console.error('没找到内联脚本'); process.exit(2); }
const code = m[1];

const ss = code.indexOf('/* ===== scene ===== */');
const se = code.indexOf('\n  initScene();', ss);
if (ss < 0 || se < 0) { console.error('scene 区块锚点未命中'); process.exit(2); }
const scene = code.slice(ss, se);

/* 按花括号配对抽出 scene 内所有 2 空格缩进的 function 定义 */
function extractFns(src) {
  const out = {};
  const re = /^  function ([A-Za-z_$][\w$]*)\s*\(/gm;
  let hit;
  while ((hit = re.exec(src)) !== null) {
    const name = hit[1];
    let i = src.indexOf('{', hit.index), depth = 0, inStr = false, q = '', esc = false;
    for (; i < src.length; i++) {
      const c = src[i];
      if (inStr) {
        if (esc) esc = false;
        else if (c === '\\') esc = true;
        else if (c === q) inStr = false;
        continue;
      }
      if (c === '"' || c === "'" || c === '`') { inStr = true; q = c; continue; }
      if (c === '{') depth++;
      else if (c === '}') { depth--; if (depth === 0) break; }
    }
    out[name] = src.slice(hit.index, i + 1);
  }
  return out;
}

const fns = extractFns(scene);
console.log('抽出顶层函数:', Object.keys(fns).length, '个 →', Object.keys(fns).join(' '));

/* UI_STRINGS 里的 section 标题是画布用到的外部数据，从脚本里原样取出 */
const us = code.indexOf('const UI_STRINGS = {');
const ue = code.indexOf('\n  };', us) + 5;
const uiStrings = us >= 0 ? code.slice(us, ue) : 'const UI_STRINGS = {};';

/* 品牌常量 BRAND 也是页面字符串依赖的外部数据，同样原样取出 */
const bs = code.indexOf('const BRAND = {');
let brandDecl = 'const BRAND = { logo: "" };';
if (bs >= 0) {
  let i = code.indexOf('{', bs), d = 0, ins = false, q = '', e = false;
  for (; i < code.length; i++) {
    const c = code[i];
    if (ins) {
      if (e) e = false;
      else if (c === '\\') e = true;
      else if (c === q) ins = false;
      continue;
    }
    if (c === '"' || c === "'" || c === '`') { ins = true; q = c; continue; }
    if (c === '{') d++;
    else if (c === '}') { d--; if (d === 0) break; }
  }
  brandDecl = code.slice(bs, i + 1) + ';';
}
console.log('品牌常量:', brandDecl.length, 'B');

const body = uiStrings + '\n' + brandDecl + '\n' + Object.values(fns).join('\n\n') +
  '\n; return { fns: Object.keys(' + JSON.stringify(Object.keys(fns)) + '), g: (n) => eval(n) };';
let api;
try {
  api = new Function(body + '\n//# sourceURL=canvas-scene.js')();
} catch (e) {
  console.error('✗ 函数体抽取后无法求值:', e.message);
  process.exit(1);
}

const pages = Object.keys(fns).filter(n => /^p\d+$/.test(n))
  .sort((a, b) => Number(a.slice(1)) - Number(b.slice(1)));

console.log('═'.repeat(78));
console.log('V11 画布运行期验证 · 真调每一页');
console.log('═'.repeat(78));
console.log('页面函数:', pages.length, '个  (' + pages[0] + ' … ' + pages[pages.length - 1] + ')');

let fail = 0;
const labels = {
  p24: '外壳与侧栏', p25: '会话头部', p26: '输入区席位', p27: '对话视图环', p28: '工具卡片',
  p29: '权限与提问', p30: '子代理与技能', p31: '右侧栏与预览', p32: '设置中心', p33: '外部应用直通',
};
pages.forEach(n => {
  let s;
  try { s = String(api.g(n)() ?? ''); }
  catch (e) { console.log('  ✗ ' + n.padEnd(5) + ' 抛错: ' + e.message); fail++; return; }
  const zh = labels[n] ? '  ★' + labels[n] : '';
  if (s.length < 300) { console.log('  ✗ ' + n.padEnd(5) + ' 过短 ' + s.length + zh); fail++; return; }
  if (/undefined/.test(s)) {
    const h = s.match(/.{0,46}undefined.{0,26}/);
    console.log('  ✗ ' + n.padEnd(5) + ' 含 undefined → …' + h[0].replace(/\s+/g, ' ') + '…' + zh); fail++; return;
  }
  if (/\[object Object\]|NaN/.test(s)) {
    const h = s.match(/.{0,46}(\[object Object\]|NaN).{0,26}/);
    console.log('  ✗ ' + n.padEnd(5) + ' 含脏值 → …' + h[0].replace(/\s+/g, ' ') + '…' + zh); fail++; return;
  }
  console.log('  ✓ ' + n.padEnd(5) + (s.length / 1024).toFixed(1).padStart(5) + ' KB' + zh);
});

console.log('─'.repeat(78));
console.log('页面 %d · 失败 %d', pages.length, fail);
console.log('宿主外壳层页 p24~p33: %d 个', pages.filter(n => +n.slice(1) >= 24).length);
process.exit(fail ? 1 : 0);
