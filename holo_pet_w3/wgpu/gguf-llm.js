/* gguf-llm.js — 浏览器内 llama 前向（零依赖）
   2026-10-30。只做一件事：把 GGUF 里的量化权重真算成 logits。

   为什么自己写：这台机器上 llama.cpp 跑不起来（iSH 缺 FCVT 指令），
   wllama 的依赖链在 iSH 上装不齐。要"自己定规则"，就得自己算。

   实现范围（照 tiny.gguf 实测张量表，不猜名字）：
     token_embd.weight      Q8_0  [576, 49152]
     blk.N.attn_norm.weight F32   [576]
     blk.N.attn_q.weight    Q5_0  [576, 576]
     blk.N.attn_k.weight    Q5_0  [576, 192]   ← 3 个 KV 头 × 64
     blk.N.attn_v.weight    Q8_0  [576, 192]
     blk.N.attn_output.weight Q5_0 [576, 576]
     blk.N.ffn_norm.weight  F32   [576]
     blk.N.ffn_gate.weight  Q5_0  [576, 1536]
     blk.N.ffn_up.weight    Q5_0  [576, 1536]
     blk.N.ffn_down.weight  Q6_K  [1536, 576]
     词表绑定：无 output.weight ⇒ lm_head = token_embd（tied）
*/

const GGUF_T = { U8:0,I8:1,U16:2,I16:3,U32:4,I32:5,F32:6,BOOL:7,STR:8,ARR:9,U64:10,I64:11,F64:12 };
const GT = { F32:0, F16:1, Q4_0:2, Q4_1:3, Q5_0:6, Q5_1:7, Q8_0:8, Q2_K:10, Q3_K:11,
             Q4_K:12, Q5_K:13, Q6_K:14 };

/* 每个 block 的「值个数 / 字节数」 */
const BLK = {
  0:  [1, 4],     /* F32 */
  1:  [1, 2],     /* F16 */
  2:  [32, 18],   /* Q4_0 */
  3:  [32, 20],   /* Q4_1 */
  6:  [32, 22],   /* Q5_0 */
  7:  [32, 24],   /* Q5_1 */
  8:  [32, 34],   /* Q8_0 */
  10: [256, 84],  /* Q2_K */
  11: [256, 110], /* Q3_K */
  12: [256, 144], /* Q4_K */
  13: [256, 176], /* Q5_K */
  14: [256, 210], /* Q6_K */
};

/* ── fp16 → f32（一次性查表，快且不会踩错）────────────────────────── */
const FP16 = (function(){
  const t = new Float32Array(65536);
  const buf = new ArrayBuffer(4), dv = new DataView(buf);
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

/* ── 反量化：把一个张量整块读成 Float32Array ────────────────────────
   口径：块布局照 llama.cpp ggml-quants.c，别自己发明。
   慢一点没关系，先要「对」；后面再谈 SIMD/WebGPU。 */
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
  if (type === 2) {            /* Q4_0: d(fp16) + 16B qs = 32 个 4bit */
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
  if (type === 6) {            /* Q5_0: d + qh(u32) + 16B qs，5bit */
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
  if (type === 8) {            /* Q8_0: d(fp16) + 32×int8 */
    const nb = nElem / 32;
    for (let b=0;b<nb;b++){
      const o = off + b*34, d = f16(u8,o), o32 = b*32;
      for (let j=0;j<32;j++){
        const q = (u8[o+2+j] << 24) >> 24;      /* 有符号 */
        out[o32+j] = d * q;
      }
    }
    return out;
  }
  if (type === 12) {           /* Q4_K：256 值 / 144 字节 = d,dmin(fp16) + scales(12B) + qs(128B)
                                  6-bit 的 scale/min 打包是 llama.cpp 的惯例，照抄不发明 */
    const nb = nElem / 256;
    for (let b=0;b<nb;b++){
      const o = off + b*144;
      const d = f16(u8, o), dmin = f16(u8, o+2);
      const sc = o+4, qs = o+16;
      const o256 = b*256;
      const getSM = (j) => {                 /* → [scale6, min6] */
        let s6, m6;
        if (j < 4) { s6 = u8[sc+j] & 63; m6 = u8[sc+j+4] & 63; }
        else {
          s6 = (u8[sc+j+4] & 0x0f) | ((u8[sc+j-4] >> 6) << 4);
          m6 = (u8[sc+j+4] >> 4)   | ((u8[sc+j-0] >> 6) << 4);
        }
        return [s6, m6];
      };
      let is = 0;
      for (let g=0; g<4; g++){               /* 4 组 × 64 值，每组两个 32-子块 */
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
  if (type === 14) {           /* Q6_K: 256 值：ql(128) qh(64) scales(16 int8) d(fp16) */
    const nb = nElem / 256;
    for (let b=0;b<nb;b++){
      const o = off + b*210;
      const ql = o, qh = o+128, sc = o+192, d = f16(u8, o+208);
      const o256 = b*256;
      for (let n=0;n<2;n++){                     /* 两个 128 半块 */
        for (let l=0;l<32;l++){
          const is = n*8 + (l/16|0);             /* scales 索引 */
          const s = (((u8[sc+is] << 24) >> 24)) * d;   /* int8 有符号 */
          const qhb = u8[qh + n*32 + l];
          const lo = (u8[ql + n*64 + l] & 0x0f) | (((qhb >> 0) & 3) << 4);
          const hi = (u8[ql + n*64 + l + 32] & 0x0f) | (((qhb >> 2) & 3) << 4);
          out[o256 + n*128 + l]      = s * (lo - 32);
          out[o256 + n*128 + l + 32] = s * (hi - 32);
        }
      }
    }
    return out;
  }
  throw new Error("未实现的反量化类型 " + type);
}

/* ── 张量索引 ─────────────────────────────────────────────────────── */
class GGUFModel {
  constructor(buf){
    this.buf = buf;
    this.u8 = new Uint8Array(buf);
    const dv = new DataView(buf);
    let p = 4;
    const ver = dv.getUint32(p, true); p += 4;
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
    this.tensors = {};
    this.order = [];
    for (let i=0;i<nTen;i++){
      const name = rdStr();
      const nd = dv.getUint32(p,true); p+=4;
      const dims = [];
      for (let d=0;d<nd;d++){ dims.push(Number(dv.getBigUint64(p,true))); p+=8; }
      const type = dv.getUint32(p,true); p+=4;
      const off = Number(dv.getBigUint64(p,true)); p+=8;
      this.tensors[name] = {name, dims, type, off};
      this.order.push(name);
    }
    /* 🔴 2026-10-30 实测坑：张量数据段要按 general.alignment（默认 32）**对齐**。
       不对齐时 attn_norm 读出 -15045 / -7e24 这种数（错 8 字节），
       反量化看着都对、结果全崩。python 侧同一位置复算证实：差的就是这 8 字节。 */
    const _al = Number(this.kv["general.alignment"] || 32);
    this.dataStart = Math.ceil(p / _al) * _al;
    this.alignment = _al;
    this.dataStartRaw = p;
    const a = this.kv["general.architecture"] || "llama";
    this.arch = a;
    this.nLayer = this.kv[a+".block_count"] || 0;
    this.nEmbd  = this.kv[a+".embedding_length"] || 0;
    this.nHead  = this.kv[a+".attention.head_count"] || 0;
    this.nKV    = this.kv[a+".attention.head_count_kv"] || this.nHead;
    this.nFF    = this.kv[a+".feed_forward_length"] || 0;
    this.eps    = this.kv[a+".attention.layer_norm_rms_epsilon"] || 1e-5;
    this.ropeTheta = this.kv[a+".rope.freq_base"] || 10000;
    this.headDim = this.nEmbd / this.nHead;
    this.tokens = this.kv["tokenizer.ggml.tokens"] || [];
    this._cache = new Map();
  }
  /* 取一张量的 Float32 视图（缓存：135M 参数全展开约 540MB，按需才展） */
  tensor(name, cache=true){
    const t = this.tensors[name];
    if (!t) throw new Error("没有张量 "+name);
    if (cache && this._cache.has(name)) return this._cache.get(name);
    const [vs, bs] = BLK[t.type] || [0,0];
    let nElem = 1;
    for (const d of t.dims) nElem *= d;
    const nBytes = (nElem / vs) * bs;
    const arr = dequant(this.u8, this.dataStart + t.off, t.type, nElem);
    if (cache) this._cache.set(name, arr);
    return arr;
  }
  /* 只取某一行（token embedding 用：49152×576 全展开太重） */
  row(name, idx){
    const t = this.tensors[name];
    const [vs, bs] = BLK[t.type];
    const cols = t.dims[0];                 /* ne0 = 行内元素数 */
    const rowBytes = (cols / vs) * bs;
    const base = this.dataStart + t.off + idx * rowBytes;
    return dequant(this.u8, base, t.type, cols);
  }
}

/* ── 数学小件 ─────────────────────────────────────────────────────── */
function rmsnorm(x, w, eps){
  let s = 0;
  for (let i=0;i<x.length;i++) s += x[i]*x[i];
  const r = 1 / Math.sqrt(s/x.length + eps);
  const o = new Float32Array(x.length);
  for (let i=0;i<x.length;i++) o[i] = x[i]*r*w[i];
  return o;
}
/* y = W·x，W 存成 [in, out]（ne0=in）⇒ 对每个 out 取一整行做点积 */
function matvec(W, x, nIn, nOut){
  const y = new Float32Array(nOut);
  for (let o=0;o<nOut;o++){
    let s = 0;
    const base = o*nIn;
    for (let i=0;i<nIn;i++) s += W[base+i]*x[i];
    y[o] = s;
  }
  return y;
}
/* RoPE：llama / qwen2 用的是 **NEOX 式**（rotate_half）——
   第 i 维和第 i + d/2 维配对，不是相邻 (0,1)(2,3) 配对。
   2026-10-30 实测：写成相邻配对 ⇒ 首 token 直接出 <|endoftext|>（分布崩了）。 */
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
  let m = -Infinity;
  for (let i=0;i<v.length;i++) if (v[i]>m) m = v[i];
  let s = 0;
  const o = new Float32Array(v.length);
  for (let i=0;i<v.length;i++){ o[i] = Math.exp(v[i]-m); s += o[i]; }
  for (let i=0;i<v.length;i++) o[i] /= s;
  return o;
}

export { GGUFModel, rmsnorm, matvec, rope, softmax, dequant, GT };
