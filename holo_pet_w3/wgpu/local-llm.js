/* local-llm.js — 本机权重的统一入口（2026-10-30）
 *
 * 谁用它：她的页面（voice-theater / model-chat / 任何页）。
 * 对外只有一套 API，内部两条后端：
 *
 *   backend = auto   → 先试 WebGPU（wgpu-llm.js），不可用就退 JS 标量（gguf-llm.js）
 *   backend = gpu    → 只用 WebGPU（不可用就如实报错，不偷偷降级）
 *   backend = js     → 只用 JS
 *
 * 硬纪律（照主人令）：
 *   · 不冒充：status() 必须报真实 backend 与真实 tok/s，不估算
 *   · 不静默降级：显式指定 gpu 而 GPU 不可用时**报错**，不在背后换成 JS
 *   · 输出可对：两条后端跑同一提示必须给出同一答案（自检里比）
 */

import { GGUFModel, matvec, rmsnorm, rope, softmax } from "./gguf-llm.js";
import { WGPUModel } from "./wgpu-llm.js";

/* ── BPE 分词（照 GGUF 元数据，不靠库）─────────────────────────────── */
function makeTokenizer(M) {
  const t2i = new Map();
  M.tokens.forEach((t, i) => { if (!t2i.has(t)) t2i.set(t, i); });
  const rank = new Map();
  (M.kv["tokenizer.ggml.merges"] || []).forEach((m, i) => {
    const p = String(m).split(" ");
    if (p.length === 2) rank.set(p[0] + "\u0000" + p[1], i);
  });
  const SPECIALS = { "<|endoftext|>": 0, "<|im_start|>": 1, "<|im_end|>": 2 };
  const re = /(<\u007cendoftext\u007c>|<\u007cim_start\u007c>|<\u007cim_end\u007c>)/;
  const bpe = (piece) => {
    let seq = Array.from(piece).map((ch) => {
      const t = ch === " " ? "Ġ" : (ch === "\n" ? "Ċ" : (ch === "\t" ? "ĉ" : ch));
      return t2i.has(t) ? t : null;
    });
    if (seq.some((x) => x === null)) return [];
    let merged = true;
    while (merged && seq.length > 1) {
      merged = false;
      let bestRank = Infinity, bestAt = -1;
      for (let k = 0; k < seq.length - 1; k++) {
        const rk = rank.get(seq[k] + "\u0000" + seq[k + 1]);
        if (rk !== undefined && rk < bestRank) { bestRank = rk; bestAt = k; }
      }
      if (bestAt >= 0) { seq.splice(bestAt, 2, seq[bestAt] + seq[bestAt + 1]); merged = true; }
    }
    return seq.map((t) => t2i.get(t)).filter((x) => x !== undefined);
  };
  return {
    encode(text) {
      const ids = [];
      for (const seg of String(text).split(re)) {
        if (!seg) continue;
        if (SPECIALS[seg] !== undefined) { ids.push(SPECIALS[seg]); continue; }
        const pieces = seg.match(/\s?[A-Za-z]+|\s?[0-9]+|\s?[^\sA-Za-z0-9]+|\s+/g) || [];
        for (const pc of pieces) ids.push(...bpe(pc));
      }
      return ids;
    },
    decode(ids) {
      return ids.map((i) => (M.tokens[i] || "").replace(/Ġ/g, " ").replace(/Ċ/g, "\n")).join("");
    },
    eos: 2, imEnd: 2, imStart: 1,
  };
}

/* ── JS 后端：持久 KV + 增量解码 ─────────────────────────────────── */
function makeJSLlm(M, tk) {
  const nE = M.nEmbd, nH = M.nHead, nKV = M.nKV, hd = M.headDim, nFF = M.nFF;
  const T = (n) => M.tensor(n);
  const emb = T("token_embd.weight");
  let KV = [];
  const reset = () => { KV = []; };
  const silu = (x) => x / (1 + Math.exp(-x));

  /** 只算 [from, ids.length) 这些位置，返回最后一个位置的 logits */
  function step(ids, from) {
    let logits = null;
    for (let pos = from; pos < ids.length; pos++) {
      let x = emb.subarray(ids[pos] * nE, ids[pos] * nE + nE).slice();
      for (let l = 0; l < M.nLayer; l++) {
        const pre = "blk." + l + ".";
        if (!KV[l]) KV[l] = { k: [], v: [] };
        const h = rmsnorm(x, T(pre + "attn_norm.weight"), M.eps);
        const q = matvec(T(pre + "attn_q.weight"), h, nE, nE);
        const k = matvec(T(pre + "attn_k.weight"), h, nE, nKV * hd);
        const v = matvec(T(pre + "attn_v.weight"), h, nE, nKV * hd);
        rope(q, nH, hd, pos, M.ropeTheta);
        rope(k, nKV, hd, pos, M.ropeTheta);
        KV[l].k.push(k); KV[l].v.push(v);
        const ctx = new Float32Array(nE);
        const scale = 1 / Math.sqrt(hd);
        for (let hh = 0; hh < nH; hh++) {
          const kvh = Math.floor((hh * nKV) / nH);
          const sc = new Float32Array(pos + 1);
          for (let t = 0; t <= pos; t++) {
            const kk = KV[l].k[t];
            let s = 0;
            for (let d = 0; d < hd; d++) s += q[hh * hd + d] * kk[kvh * hd + d];
            sc[t] = s * scale;
          }
          const p = softmax(sc);
          for (let d = 0; d < hd; d++) {
            let acc = 0;
            for (let t = 0; t <= pos; t++) acc += p[t] * KV[l].v[t][kvh * hd + d];
            ctx[hh * hd + d] = acc;
          }
        }
        const ao = matvec(T(pre + "attn_output.weight"), ctx, nE, nE);
        for (let i = 0; i < nE; i++) x[i] += ao[i];
        const h2 = rmsnorm(x, T(pre + "ffn_norm.weight"), M.eps);
        const g = matvec(T(pre + "ffn_gate.weight"), h2, nE, nFF);
        const u = matvec(T(pre + "ffn_up.weight"), h2, nE, nFF);
        const act = new Float32Array(nFF);
        for (let i = 0; i < nFF; i++) act[i] = silu(g[i]) * u[i];
        const dn = matvec(T(pre + "ffn_down.weight"), act, nFF, nE);
        for (let i = 0; i < nE; i++) x[i] += dn[i];
      }
      if (pos === ids.length - 1) {
        const xf = rmsnorm(x, T("output_norm.weight"), M.eps);
        const V = M.tokens.length;
        logits = new Float32Array(V);
        for (let t = 0; t < V; t++) {
          let s = 0, b = t * nE;
          for (let i = 0; i < nE; i++) s += emb[b + i] * xf[i];
          logits[t] = s;
        }
      }
    }
    return logits;
  }
  return { kind: "js", step, reset };
}

/* ── GPU 后端：包一层同样的 step 接口 ───────────────────────────── */
function makeGPULlm(G) {
  /* 预填要**逐位置**走：KV 缓存必须按 pos 依次写进去。
     只算最后一位会让前面位置的 KV 空着，注意力就少了前缀。 */
  return {
    kind: "gpu",
    async step(ids, from) {
      let lg = null;
      for (let p = from; p < ids.length; p++) lg = await G.step(ids[p], p);
      return lg;
    },
    reset: () => G.reset(),
  };
}

/* ── 统一入口 ───────────────────────────────────────────────────── */
export async function createLocalLLM(opts = {}) {
  const url = opts.modelUrl || "models/tiny.gguf";
  const backend = (opts.backend || "auto").toLowerCase();
  const t0 = performance.now();
  const buf = await (await fetch(url)).arrayBuffer();
  const M = new GGUFModel(buf);
  const tk = makeTokenizer(M);
  const loadMs = performance.now() - t0;

  let engine = null, note = "";
  if (backend === "auto" || backend === "gpu") {
    try {
      if (!navigator.gpu) throw new Error("没有 navigator.gpu");
      const G = await WGPUModel.create(M);
      G.upload();
      G.prepare(opts.maxPos || 64);
      engine = makeGPULlm(G);
      engine.gpu = G;
    } catch (e) {
      if (backend === "gpu") throw new Error("显式要求 gpu，但起不来：" + (e && e.message || e));
      note = "GPU 不可用，已退 JS：" + (e && e.message || e);
    }
  }
  if (!engine) engine = makeJSLlm(M, tk);

  const argmaxPen = (lg, ids, pen) => {
    const a = Array.from(lg);
    const seen = new Set(ids.slice(-16));
    for (const t of seen) { if (a[t] > 0) a[t] /= pen; else a[t] *= pen; }
    let bi = 0, bv = -1e30;
    for (let i = 0; i < a.length; i++) if (a[i] > bv) { bv = a[i]; bi = i; }
    return bi;
  };

  /** 对话：走 chat 模板，遇 eos 停 */
  async function chat(userText, maxTokens = 24, o = {}) {
    const pen = o.repetitionPenalty || 1.25;
    const p = "<|im_start|>user\n" + String(userText) + "<|im_end|>\n<|im_start|>assistant\n";
    const ids = tk.encode(p);
    engine.reset();
    let lg = await engine.step(ids, 0);
    const gen = ids.slice();
    let nxt = argmaxPen(lg, gen, pen);
    const t1 = performance.now();
    let n = 0;
    for (let i = 0; i < maxTokens; i++) {
      gen.push(nxt); n++;
      if (nxt === tk.imEnd) break;
      lg = await engine.step(gen, gen.length - 1);
      nxt = argmaxPen(lg, gen, pen);
    }
    const dt = (performance.now() - t1) / 1000;
    const outIds = gen.slice(ids.length).filter((x) => x !== tk.imEnd);
    return { ok: true, text: tk.decode(outIds).trim(), ids: outIds, tokens: outIds.length,
             seconds: +dt.toFixed(2), tokPerSec: dt > 0 ? +(outIds.length / dt).toFixed(2) : null };
  }

  /** 裸续写：给对照/测试用，返回 top-1 */
  async function nextToken(promptText) {
    const ids = tk.encode(promptText);
    engine.reset();
    const lg = await engine.step(ids, 0);
    const top = argmaxPen(lg, ids, 1.0);
    return { id: top, text: tk.decode([top]), ids };
  }

  return {
    backend: engine.kind,
    note,
    loadMs: +loadMs.toFixed(0),
    model: { arch: M.arch, layers: M.nLayer, emb: M.nEmbd, heads: M.nHead,
             kvHeads: M.nKV, headDim: M.headDim, vocab: M.tokens.length },
    chat, nextToken, tokenize: tk.encode, decode: tk.decode,
    reset: () => engine.reset(),
  };
}
