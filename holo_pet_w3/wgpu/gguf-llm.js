/* gguf-llm.js — 浏览器内 llama 前向（零依赖）
   2026-10-31 升级：RangeBuffer 按需激活（不一次读全量文件）。
   Header ~1MB 一次性读；每个张量数据在 tensor() 首次调用时 fetch，此后缓存。
   内存占用 ≈ 正在 forward 的层数 × 每层权重 F32 大小（而非全模型）。
*/

const GGUF_T = { U8:0,I8:1,U16:2,I16:3,U32:4,I32:5,F32:6,BOOL:7,STR:8,ARR:9,U64:10,I64:11,F64:12 };
const GT = { F32:0, F16:1, Q4_0:2, Q4_1:3, Q5_0:6, Q5_1:7, Q8_0:8, Q2_K:10, Q3_K:11,
             Q4_K:12, Q5_K:13, Q6_K:14 };

const BLK = {
  0:  [1, 4],     1:  [1, 2],     2:  [32, 18],   3:  [32, 20],
  6:  [32, 22],   7:  [32, 24],   8:  [32, 34],
  10: [256, 84],  11: [256, 110], 12: [256, 144], 13: [256, 176], 14: [256, 210],
};

const FP16 = (function(){
  const t = new Float32Array(65536), buf = new ArrayBuffer(4), dv = new DataView(buf);
  for (let i=0;i<65536;i++){
    const s = (i & 0x8000) ? -1 : 1, e = (i >> 10) & 0x1f, m = i & 0x3ff;
    let v;
    if (e === 0) v = s * m * Math.pow(2, -24);
    else if (e === 31) v = m ? NaN : s * Infinity;
    else v = s * (1 + m / 1024) * Math.pow(2, e - 15);
    t[i] = v;
  }
  return t;
})();
function f16(u8, off){ return FP16[(u8[off] | (u8[off+1] << 8)) & 0xffff]; }

function dequant(u8, off, type, nElem){
  const out = new Float32Array(nElem);
  if (type === GT.F32) {
    const dv = new DataView(u8.buffer, u8.byteOffset + off, nElem*4);
    for (let i=0;i<nElem;i++) out[i] = dv.getFloat32(i*4, true);
    return out;
  }
  if (type === GT.F16) {
    for (let i=0;i<nElem;i++) out[i] = f16(u8, off + i*2);
    return out;
  }
  if (type === 2) {
    const nb = nElem / 32;
    for (let b=0;b<nb;b++){
      const o = off + b*18, d = f16(u8,o), qs = o+2, o32 = b*32;
      for (let j=0;j<16;j++){
        const v = u8[qs+j];
        out[o32+j]      = d * ((v & 0x0f) - 8);
        out[o32+j+16]   = d * ((v >> 4)   - 8);
      }
    }
    return out;
  }
  if (type === 6) {
    const nb = nElem / 32;
    for (let b=0;b<nb;b++){
      const o = off + b*22, d = f16(u8,o);
      const qh = (u8[o+2] | (u8[o+3]<<8) | (u8[o+4]<<16) | (u8[o+5]<<24)) >>> 0;
      const qs = o+6, o32 = b*32;
      for (let j=0;j<16;j++){
        const x = u8[qs+j];
        const lo = (x & 0x0f) | (((qh >> j) & 1) << 4);
        const hi = (x >> 4)   | (((qh >> (j+16)) & 1) << 4);
        out[o32+j]    = d * (lo - 16);
        out[o32+j+16] = d * (hi - 16);
      }
    }
    return out;
  }
  if (type === 8) {
    const nb = nElem / 32;
    for (let b=0;b<nb;b++){
      const o = off + b*34, d = f16(u8,o), o32 = b*32;
      for (let j=0;j<32;j++){
        const q = (u8[o+2+j] << 24) >> 24;
        out[o32+j] = d * q;
      }
    }
    return out;
  }
  if (type === 12) {
    const nb = nElem / 256;
    for (let b=0;b<nb;b++){
      const o = off + b*144;
      const d = f16(u8, o), dmin = f16(u8, o+2);
      const sc = o+4, qs = o+16, o256 = b*256;
      const getSM = (j) => {
        let s6, m6;
        if (j < 4) { s6 = u8[sc+j] & 63; m6 = u8[sc+j+4] & 63; }
        else { s6 = (u8[sc+j+4] & 0x0f) | ((u8[sc+j-4] >> 6) << 4); m6 = (u8[sc+j+4] >> 4) | ((u8[sc+j-0] >> 6) << 4); }
        return [s6, m6];
      };
      let is = 0;
      for (let g=0;g<4;g++){
        const [s0, m0] = getSM(is), [s1, m1] = getSM(is+1);
        const d1 = d*s0, dm1 = dmin*m0, d2 = d*s1, dm2 = dmin*m1;
        const q = qs + g*32;
        for (let l=0;l<32;l++){
          out[o256 + g*64 + l]    = d1 * (u8[q+l] & 0x0f) - dm1;
          out[o256 + g*64 + l+32] = d2 * (u8[q+l] >>   4) - dm2;
        }
        is += 2;
      }
    }
    return out;
  }
  if (type === 14) {
    const nb = nElem / 256;
    for (let b=0;b<nb;b++){
      const o = off + b*210;
      const ql0 = o, qh0 = o+128, sc0 = o+192, d = f16(u8, o+208);
      const o256 = b*256;
      for (let g=0;g<2;g++){
        const ql = ql0 + g*64, qh = qh0 + g*32, sc = sc0 + g*8;
        for (let l=0;l<32;l++){
          const is = l >> 4;
          const qhb = u8[qh + l];
          const q1 = (((u8[ql + l])      & 0x0F) | (((qhb >> 0) & 3) << 4)) - 32;
          const q2 = (((u8[ql + l + 32]) & 0x0F) | (((qhb >> 2) & 3) << 4)) - 32;
          const q3 = (((u8[ql + l])      >> 4  ) | (((qhb >> 4) & 3) << 4)) - 32;
          const q4 = (((u8[ql + l + 32]) >> 4  ) | (((qhb >> 6) & 3) << 4)) - 32;
          const s1 = (u8[sc + is + 0] << 24) >> 24;
          const s2 = (u8[sc + is + 2] << 24) >> 24;
          const s3 = (u8[sc + is + 4] << 24) >> 24;
          const s4 = (u8[sc + is + 6] << 24) >> 24;
          const base = o256 + g*128;
          out[base + l +  0] = d * s1 * q1;
          out[base + l + 32] = d * s2 * q2;
          out[base + l + 64] = d * s3 * q3;
          out[base + l + 96] = d * s4 * q4;
        }
      }
    }
    return out;
  }
  throw new Error("未实现的反量化类型 " + type);
}

/* ── RangeBuffer：大文件按需激活（2026-10-31）──────────────────
   策略：一次性 pre-fetch 64MB 大块（覆盖大多数 tensor），
         tensor() 在块内按 offset 切片，不触发额外网络请求。
         超出块范围时自动追加下一个 64MB 块。
*/
class RangeBuffer {
  constructor(url, onProgress) {
    this.url = url;
    this._cache = new Map();   /* off (block-aligned) → Uint8Array(64MB chunk) */
    this._totalLoaded = 0;
    this._onProgress = onProgress || null;
  }
  async read(off, count) {
    const CHUNK = 64 * 1024 * 1024;   /* 64MB 一块 */
    const blockStart = Math.floor(off / CHUNK) * CHUNK;
    let chunk = this._cache.get(blockStart);
    if (!chunk) {
      const r = await fetch(this.url, {
        headers: { Range: `bytes=${blockStart}-${blockStart + CHUNK - 1}` }
      });
      if (!r.ok || r.status !== 206) throw new Error(`Range fetch ${this.url} @${blockStart} → HTTP ${r.status}`);
      chunk = new Uint8Array(await r.arrayBuffer());
      this._cache.set(blockStart, chunk);
      this._totalLoaded += chunk.byteLength;
      if (this._onProgress) this._onProgress(this._totalLoaded);
    }
    const rel = off - blockStart;
    return chunk.slice(rel, rel + count);
  }
  async stat() {
    /* 不读文件内容，只拿 Content-Length */
    const r = await fetch(this.url, { method: 'HEAD' });
    return Number(r.headers.get('Content-Length')) || 0;
  }
}

/* ── GGUFModel：双模式（小模型全量 / 大模型 Range 按需）───────── */
class GGUFModel {
  constructor(opts){
    this._cache = {}; this._rb = null; this.u8 = null; this.dataStart = 0;
    if (opts.buf) {
      this.buf = opts.buf; this.u8 = new Uint8Array(opts.buf);
      this._parseFromBuffer();
    } else if (opts.url) {
      this.modelUrl = opts.url; this._onProgress = opts.onProgress || null;
    } else { throw new Error("GGUFModel needs {buf} or {url}"); }
  }
  _parseFromBuffer(){
    const buf = this.buf, dv = new DataView(buf); let p = 8;  // GGUF v3: magic(4)+ver(4)=8, nTen at 8, nKV at 16, KV at 24
    const nTen = Number(dv.getBigUint64(p, true)); p += 8;
    const nKV = Number(dv.getBigUint64(p, true)); p += 8;
    const TD = new TextDecoder();
    const rdStr = () => { const n = Number(dv.getBigUint64(p,true)); p += 8;
                          const s = TD.decode(this.u8.slice(p, p+n)); p += n; return s; };
    const rdVal = (t) => {
      switch(t){
        case 0:{const v=this.u8[p];p+=1;return v;}
        case 1:{const v=dv.getInt8(p);p+=1;return v;}
        case 2:{const v=dv.getUint16(p,true);p+=2;return v;}
        case 3:{const v=dv.getInt16(p,true);p+=2;return v;}
        case 4:{const v=dv.getUint32(p,true);p+=4;return v;}
        case 5:{const v=dv.getInt32(p,true);p+=4;return v;}
        case 6:{const v=dv.getFloat32(p,true);p+=4;return v;}
        case 7:{const v=this.u8[p];p+=1;return !!v;}
        case 8: return rdStr();
        case 9:{
          const et=dv.getUint32(p,true);p+=4; const n=Number(dv.getBigUint64(p,true));p+=8;
          const a=[];
          if(et===8){for(let i=0;i<n;i++)a.push(rdStr());}
          else if(et===4||et===5){for(let i=0;i<n;i++)a.push(dv.getInt32(p+i*4,true));p+=n*4;}
          else if(et===6){p+=n*4;a.push("["+n+" f32]");}
          else if(et===0||et===1||et===7){p+=n;a.push("["+n+" u8]");}
          else { for(let i=0;i<n;i++) rdVal(et); a.push("["+n+"]"); }
          return a;
        }
        case 10: case 11: {const v=Number(dv.getBigUint64(p,true));p+=8;return v;}
        case 12: {const v=dv.getFloat64(p,true);p+=8;return v;}
        default: throw new Error("KV 类型 "+t);
      }
    };
    this.kv = {};
    for (let i=0;i<nKV;i++){ const k = rdStr(); const t = dv.getUint32(p,true); p+=4; this.kv[k] = rdVal(t); }
    this.tensors = {}; this.order = [];
    for (let i=0;i<nTen;i++){
      const name = rdStr(), nd = dv.getUint32(p,true); p+=4;
      const dims = []; for (let d=0;d<nd;d++){ dims.push(Number(dv.getBigUint64(p,true))); p+=8; }
      const type = dv.getUint32(p,true); p+=4;
      const off = Number(dv.getBigUint64(p,true)); p+=8;
      this.tensors[name] = {name, dims, type, off}; this.order.push(name);
    }
    const _al = Number(this.kv["general.alignment"] || 32);
    this.dataStart = Math.ceil(p / _al) * _al; this.alignment = _al;
    const a = this.kv["general.architecture"] || "llama";
    this.arch = a; this.nLayer = this.kv[a+".block_count"] || 0;
    this.nEmbd  = this.kv[a+".embedding_length"] || 0;
    this.nHead  = this.kv[a+".attention.head_count"] || 0;
    this.nKV    = this.kv[a+".attention.head_count_kv"] || this.nHead;
    this.nFF    = this.kv[a+".feed_forward_length"] || 0;
    this.eps    = this.kv[a+".attention.layer_norm_rms_epsilon"] || 1e-5;
    this.ropeTheta = this.kv[a+".rope.freq_base"] || 10000;
    this.headDim = this.nEmbd / this.nHead;
    this.tokens = this.kv["tokenizer.ggml.tokens"] || [];
  }
  async initRangeBuffer(){
    if (this._rb) return;
    if (!this.modelUrl) throw new Error("没有 url，无法 RangeBuffer");
    this._rb = new RangeBuffer(this.modelUrl, this._onProgress);
    /* 🔴 修复：直接 fetch 整个 header（不经过 RangeBuffer 切片），
       这样 DataView 的偏移量直接对应文件偏移，不用换算。 */
    const hdrR = await fetch(this.modelUrl, { headers: { Range: 'bytes=0-1048575' } });
    if (hdrR.status !== 206) throw new Error(`Header fetch HTTP ${hdrR.status}`);
    const hdrBytes = new Uint8Array(await hdrR.arrayBuffer());
    const dv = new DataView(hdrBytes.buffer, hdrBytes.byteOffset, hdrBytes.byteLength);
    let p = 8;  // GGUF v3: magic(4)+ver(4)=8, nTen at 8, nKV at 16, KV at 24
    const nTen = Number(dv.getBigUint64(p, true)); p += 8;
    const nKV = Number(dv.getBigUint64(p, true)); p += 8;
    // GGUF v3: 无迭代次数 n 字段，KV 直接从 p=24 开始（第一个 kLen）
    const TD = new TextDecoder();
    const rdStr = () => { const n = Number(dv.getBigUint64(p,true)); p += 8;
                          const s = TD.decode(hdrBytes.slice(p, p+n)); p += n; return s; };
    const rdVal = (t) => {
      switch(t){
        case 0:{const v=hdrBytes[p];p+=1;return v;}
        case 1:{const v=dv.getInt8(p);p+=1;return v;}
        case 2:{const v=dv.getUint16(p,true);p+=2;return v;}
        case 3:{const v=dv.getInt16(p,true);p+=2;return v;}
        case 4:{const v=dv.getUint32(p,true);p+=4;return v;}
        case 5:{const v=dv.getInt32(p,true);p+=4;return v;}
        case 6:{const v=dv.getFloat32(p,true);p+=4;return v;}
        case 7:{const v=hdrBytes[p];p+=1;return !!v;}
        case 8: return rdStr();
        case 9:{
          const et=dv.getUint32(p,true);p+=4; const n=Number(dv.getBigUint64(p,true));p+=8;
          const a=[];
          if(et===8){for(let i=0;i<n;i++)a.push(rdStr());}
          else if(et===4||et===5){for(let i=0;i<n;i++)a.push(dv.getInt32(p+i*4,true));p+=n*4;}
          else if(et===6){p+=n*4;a.push("["+n+" f32]");}
          else if(et===0||et===1||et===7){p+=n;a.push("["+n+" u8]");}
          else { for(let i=0;i<n;i++) rdVal(et); a.push("["+n+"]"); }
          return a;
        }
        case 10: case 11: {const v=Number(dv.getBigUint64(p,true));p+=8;return v;}
        case 12: {const v=dv.getFloat64(p,true);p+=8;return v;}
        default: throw new Error("KV 类型 "+t);
      }
    };
    this.kv = {};
    for (let i=0;i<nKV;i++){ const k = rdStr(); const t = dv.getUint32(p,true); p+=4; this.kv[k] = rdVal(t); }
    this.tensors = {}; this.order = [];
    for (let i=0;i<nTen;i++){
      const name = rdStr(), nd = dv.getUint32(p,true); p+=4;
      const dims = []; for (let d=0;d<nd;d++){ dims.push(Number(dv.getBigUint64(p,true))); p+=8; }
      const type = dv.getUint32(p,true); p+=4;
      const off = Number(dv.getBigUint64(p,true)); p+=8;
      this.tensors[name] = {name, dims, type, off}; this.order.push(name);
    }
    const _al = Number(this.kv["general.alignment"] || 32);
    this.dataStart = Math.ceil(p / _al) * _al; this.alignment = _al;
    const a = this.kv["general.architecture"] || "llama";
    this.arch = a; this.nLayer = this.kv[a+".block_count"] || 0;
    this.nEmbd  = this.kv[a+".embedding_length"] || 0;
    this.nHead  = this.kv[a+".attention.head_count"] || 0;
    this.nKV    = this.kv[a+".attention.head_count_kv"] || this.nHead;
    this.nFF    = this.kv[a+".feed_forward_length"] || 0;
    this.eps    = this.kv[a+".attention.layer_norm_rms_epsilon"] || 1e-5;
    this.ropeTheta = this.kv[a+".rope.freq_base"] || 10000;
    this.headDim = this.nEmbd / this.nHead;
    this.tokens = this.kv["tokenizer.ggml.tokens"] || []; console.log(`[GGUF] ${nTen} tensors, arch=${this.arch}, layers=${this.nLayer}, dataStart=${this.dataStart}`);
  }
  tensor(name){
    if (this._cache[name]) return this._cache[name];
    if (!this.u8) throw new Error("tensor() 需要同步数据源，请用 tensorAsync()");
    const t = this.tensors[name]; if (!t) throw new Error("没有张量 "+name);
    const [vs, bs] = BLK[t.type] || [0,0];
    let nElem = 1; for (const d of t.dims) nElem *= d;
    const arr = dequant(this.u8, this.dataStart + t.off, t.type, nElem);
    this._cache[name] = arr; return arr;
  }
  async tensorAsync(name){
    if (this._cache[name]) return this._cache[name];
    if (!this._rb) await this.initRangeBuffer();
    const t = this.tensors[name]; if (!t) throw new Error("没有张量 "+name);
    const [vs, bs] = BLK[t.type] || [0,0];
    let nElem = 1; for (const d of t.dims) nElem *= d;
    const nBytes = (nElem / vs) * bs;
    const raw = await this._rb.read(t.off, nBytes);
    const arr = dequant(raw, 0, t.type, nElem);
    this._cache[name] = arr; return arr;
  }
  row(name, idx){
    if (this.u8) {
      const t = this.tensors[name], [vs, bs] = BLK[t.type];
      const cols = t.dims[0], rowBytes = (cols / vs) * bs;
      return dequant(this.u8, this.dataStart + t.off + idx * rowBytes, t.type, cols);
    }
    throw new Error("row() 不支持 RangeBuffer，用 tensorAsync(name) 再切片");
  }
}

function rmsnorm(x, w, eps){
  let s = 0; for (let i=0;i<x.length;i++) s += x[i]*x[i];
  const r = 1 / Math.sqrt(s/x.length + eps);
  const o = new Float32Array(x.length);
  for (let i=0;i<x.length;i++) o[i] = x[i]*r*w[i];
  return o;
}
function matvec(W, x, nIn, nOut){
  const y = new Float32Array(nOut);
  for (let o=0;o<nOut;o++){ let s=0; const base=o*nIn; for (let i=0;i<nIn;i++) s += W[base+i]*x[i]; y[o]=s; }
  return y;
}
function rope(x, nHead, headDim, pos, theta){
  const half = headDim >> 1;
  for (let h=0;h<nHead;h++){
    const base = h*headDim;
    for (let i=0;i<half;i++){
      const inv = Math.pow(theta, -2*i/headDim);
      const ang = pos * inv, c = Math.cos(ang), s = Math.sin(ang);
      const a = x[base+i], b = x[base+i+half];
      x[base+i]      = a*c - b*s;
      x[base+i+half] = a*s + b*c;
    }
  }
}
function softmax(v){
  let m = -Infinity; for (let i=0;i<v.length;i++) if (v[i]>m) m = v[i];
  let s = 0; const o = new Float32Array(v.length);
  for (let i=0;i<v.length;i++){ o[i] = Math.exp(v[i]-m); s += o[i]; }
  for (let i=0;i<v.length;i++) o[i] /= s;
  return o;
}
export { GGUFModel, rmsnorm, matvec, rope, softmax, dequant, GT };
