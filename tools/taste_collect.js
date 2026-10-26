// taste_lint 采集器 —— 在真页面里量，不靠猜。由 tools/taste_lint.py 注入执行。
// 只读，不改页面。**顶层 return**（外壳是 async 函数，包 IIFE 拿不到返回值）。
  const vis = (el) => {
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return cs.display !== "none" && cs.visibility !== "hidden" && r.width > 4 && r.height > 4;
  };
  const textOf = (el) => (el.innerText || el.textContent || "").trim();
  const inCode = (el) => !!(el.closest("pre, code, textarea, input"));
  const uniq = (a) => Array.from(new Set(a));

  const all = Array.from(document.querySelectorAll("body *")).filter(vis);

  // ── 标题：字号 + 是否超两行（用 rect 高 / 行高） ─────────────────────
  const heads = Array.from(document.querySelectorAll("h1,h2,h3,h4,h5,h6"))
    .filter(vis).map((el) => {
      const cs = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.2;
      return { tag: el.tagName.toLowerCase(), text: textOf(el).slice(0, 60),
               fontSize: Math.round(parseFloat(cs.fontSize)),
               lines: Math.max(1, Math.round(r.height / lh)),
               words: textOf(el).split(/\s+/).filter(Boolean).length };
    });

  // ── 字号 / 字体 / 颜色 ────────────────────────────────────────────────
  const sizes = uniq(all.filter((e) => textOf(e)).map((e) => Math.round(parseFloat(getComputedStyle(e).fontSize)))).sort((a,b)=>a-b);
  const families = uniq(all.filter((e) => textOf(e)).map((e) => getComputedStyle(e).fontFamily.split(",")[0].replace(/["']/g, "").trim()));

  // ── 装饰计数 ─────────────────────────────────────────────────────────
  const grads = all.filter((e) => (getComputedStyle(e).backgroundImage || "").includes("gradient")
                                 && !e.closest("[data-ui]")).length;
  const shadows = all.filter((e) => {
    const s = getComputedStyle(e).boxShadow;
    return s && s !== "none" && !e.closest("[data-ui]");
  }).length;
  const hairlines = all.filter((e) => {
    if (e.closest("[data-ui], pre, code, table, input, textarea, select")) return false;
    const cs = getComputedStyle(e);
    const sides = ["Top","Right","Bottom","Left"];
    return sides.some((s) => cs["border" + s + "Width"] === "1px" && cs["border" + s + "Style"] !== "none");
  }).length;
  const mono = all.filter((e) => {
    if (inCode(e)) return false;
    const f = (getComputedStyle(e).fontFamily || "").toLowerCase();
    return f.includes("mono");
  }).length;
  const upperTracked = all.filter((e) => {
    if (!textOf(e) || inCode(e)) return false;
    const cs = getComputedStyle(e);
    const ls = parseFloat(cs.letterSpacing) || 0;
    return cs.textTransform === "uppercase" && ls >= 0.5;
  }).length;
  const glass = all.filter((e) => {
    const cs = getComputedStyle(e);
    return (cs.backdropFilter && cs.backdropFilter !== "none") ||
           ((cs.webkitBackdropFilter || "") !== "" && (cs.webkitBackdropFilter||"") !== "none");
  }).length;

  // ── 圆角：9–16px 的"软圆角"是弱站默认 ────────────────────────────────
  const radii = all.map((e) => getComputedStyle(e).borderRadius).filter((r) => r && r !== "0px");
  const softRadius = radii.filter((r) => {
    const n = parseFloat(r); return n >= 9 && n <= 16;
  }).length;

  // ── 文案禁令：emoji / 索引号 / 眉标 ──────────────────────────────────
  const bodyText = document.body.innerText || "";
  const emoji = (bodyText.match(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/gu) || []).length;
  const idxNum = all.filter((e) => {
    const t = textOf(e); if (!t || t.length > 12 || inCode(e)) return false;
    return /^(0\d|\d\d)$/.test(t) || /^Step\s*\d+$/i.test(t) || /^\(\d{2,3}\)$/.test(t);
  }).length;
  const eyebrows = all.filter((e) => {
    const t = textOf(e); if (!t || t.length > 24 || inCode(e)) return false;
    const cs = getComputedStyle(e);
    const fs = parseFloat(cs.fontSize);
    const nxt = e.nextElementSibling;
    const followedByHead = nxt && /^H[1-6]$/.test(nxt.tagName);
    return fs <= 13 && (followedByHead || cs.textTransform === "uppercase");
  }).length;

  // ── 强调色：动作色出现几次 ──────────────────────────────────────────
  const actionColors = uniq(all.filter((e) => /^(BUTTON|A)$/.test(e.tagName) && vis(e))
    .map((e) => getComputedStyle(e).backgroundColor).filter((c) => c && c !== "rgba(0, 0, 0, 0)"));

  // ── 图 ──────────────────────────────────────────────────────────────
  const imgs = Array.from(document.querySelectorAll("img")).filter(vis);
  const heroShare = (() => {
    if (!imgs.length) return 0;
    const vh = window.innerHeight;
    const r = imgs[0].getBoundingClientRect();
    return Math.min(1, Math.max(0, (Math.min(r.bottom, vh) - Math.max(r.top, 0)) / vh));
  })();

  // ── 节间距：顶层块的垂直间隔 ────────────────────────────────────────
  const main = document.querySelector("main") || document.body;
  const blocks = Array.from(main.children).filter(vis);
  const gaps = [];
  for (let i = 1; i < blocks.length; i++) {
    const a = blocks[i - 1].getBoundingClientRect(), b = blocks[i].getBoundingClientRect();
    if (b.top > a.bottom) gaps.push(Math.round(b.top - a.bottom));
  }
  const bodyCs = getComputedStyle(document.body);

  return JSON.stringify({
    url: location.href, w: window.innerWidth, h: window.innerHeight,
    counts: { elements: all.length, images: imgs.length, blocks: blocks.length },
    headings: heads,
    fontSizes: sizes, fontFamilies: families,
    decor: { gradients: grads, shadows: shadows, hairlines: hairlines, mono: mono,
             upperTracked: upperTracked, glass: glass, softRadius: softRadius },
    copy: { emoji: emoji, indexNumbering: idxNum, eyebrows: eyebrows },
    color: { bodyBg: bodyCs.backgroundColor, bodyInk: bodyCs.color, actionColors: actionColors },
    image: { heroShare: +heroShare.toFixed(2) },
    gaps: gaps
  });
