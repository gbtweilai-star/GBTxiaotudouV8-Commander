/* wgpu-llm.js — 把整条 llama 前向搬上 WebGPU（2026-10-30）
 *
 * 为什么要它：bench-matvec 实测 —— 单算子走 GPU 是亏的（fence 往返 0.6ms），
 * 但**一个 token 的全部算子打包成一批、只等一次 fence**，210 次派发只要 10.6ms。
 * 现在 JS 标量路径 9.83 tok/s，这条路的上限约 94 tok/s。
 *
 * 设计取舍（照实测，不照教科书）：
 *   · 权重一次性反量化后上传显存常驻（540MB f32；单 buffer 上限 1GB，逐张量开 buffer）
 *   · 每 token：一个 command encoder 把所有算子排进去，最后**只 fence 一次**
 *   · 注意力做成「一个 head 一个工作组」，分数放工作组共享内存，避免多次派发
 *   · 激活值全部留在显存，中间不回读
 *
 * 数值口径：与 JS 版逐位对照（float 累加顺序不同 ⇒ 允许 1e-4 相对误差），
 * argmax 必须一致，否则判红。
 */

export const WK = `
struct P { nIn: u32, nOut: u32, a: f32, b: f32 };

/* ── matvec: y[o] = Σ W[o*nIn+i] * x[i] ───────────────────────────── */
@group(0) @binding(0) var<storage, read> MW: array<f32>;
@group(0) @binding(1) var<storage, read> MX: array<f32>;
@group(0) @binding(2) var<storage, read_write> MY: array<f32>;
@group(0) @binding(3) var<uniform> MP: P;
@compute @workgroup_size(64)
fn mv(@builtin(global_invocation_id) gid: vec3<u32>) {
  let o = gid.x;
  if (o >= MP.nOut) { return; }
  var s: f32 = 0.0;
  let base = o * MP.nIn;
  for (var i: u32 = 0u; i < MP.nIn; i = i + 1u) {
    s = s + MW[base + i] * MX[i];
  }
  MY[o] = s;
}

/* ── rmsnorm: y = x * rsqrt(mean(x^2)+eps) * w ────────────────────── */
@group(0) @binding(0) var<storage, read> RX: array<f32>;
@group(0) @binding(1) var<storage, read> RW: array<f32>;
@group(0) @binding(2) var<storage, read_write> RY: array<f32>;
@group(0) @binding(3) var<uniform> RP: P;
@compute @workgroup_size(256)
fn rms(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = gid.x;
  if (i >= RP.nIn) { return; }
  var ss: f32 = 0.0;
  for (var k: u32 = 0u; k < RP.nIn; k = k + 1u) { ss = ss + RX[k] * RX[k]; }
  let inv = inverseSqrt(ss / f32(RP.nIn) + RP.a);
  RY[i] = RX[i] * inv * RW[i];
}

/* ── 残差相加: x += y ─────────────────────────────────────────────── */
@group(0) @binding(0) var<storage, read_write> AX: array<f32>;
@group(0) @binding(1) var<storage, read> AY: array<f32>;
@group(0) @binding(2) var<uniform> AP: P;
@compute @workgroup_size(256)
fn add(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = gid.x;
  if (i >= AP.nIn) { return; }
  AX[i] = AX[i] + AY[i];
}

/* ── NEOX 式 RoPE：只作用于 q(9 头) 或 k(3 头) ─────────────────────── */
@group(0) @binding(0) var<storage, read_write> VX: array<f32>;
@group(0) @binding(1) var<uniform> VP: P;   /* nIn = nHead*hd, a = pos, b = theta */
@compute @workgroup_size(64)
fn rope(@builtin(global_invocation_id) gid: vec3<u32>) {
  let hd: u32 = VP.nOut;                 /* headDim */
  let half: u32 = hd >> 1u;
  let g = gid.x;                         /* 全局索引 = h*hd + i，i<half */
  let h = g / half;
  let i = g % half;
  let base = h * hd;
  let ang = VP.a * pow(VP.b, -2.0 * f32(i) / f32(hd));
  let c = cos(ang);
  let s = sin(ang);
  let a1 = VX[base + i];
  let b1 = VX[base + i + half];
  VX[base + i]        = a1 * c - b1 * s;
  VX[base + i + half] = a1 * s + b1 * c;
}

/* ── 注意力（单 token）：一个 head 一个工作组 ─────────────────────────
   输入 q(hd) · kcache(pos×nKV*hd) · vcache 同形；输出 ctx[head*hd ..]
   分数放工作组共享内存（最多 256 个位置）。 */
@group(0) @binding(0) var<storage, read> AQ: array<f32>;
@group(0) @binding(1) var<storage, read> AK: array<f32>;
@group(0) @binding(2) var<storage, read> AV: array<f32>;
@group(0) @binding(3) var<storage, read_write> AC: array<f32>;
@group(0) @binding(4) var<uniform> AP2: P;   /* nIn=pos+1, nOut=hd, a=nKV, b=kvHead */
var<workgroup> SC: array<f32, 256>;
@compute @workgroup_size(64)
fn attn(@builtin(workgroup_id) wid: vec3<u32>,
        @builtin(local_invocation_id) lid: vec3<u32>) {
  let h: u32 = wid.x;                   /* 工作组号 = 查询头（必须先定义） */
  let hd: u32 = AP2.nOut;
  let n: u32 = AP2.nIn;                 /* 位置数 */
  let nkv: u32 = u32(AP2.a);            /* KV 头数 */
  let nhead: u32 = u32(AP2.b);          /* 查询头数 */
  /* 🔴 2026-10-30：GQA 映射必须按查询头算；
     原来把 kvOff 写死成 0 ⇒ 9 个查询头全读同一个 KV 头，输出必错。 */
  let kvh: u32 = h / (nhead / nkv);
  let kvOff: u32 = kvh * hd;
  let scale = inverseSqrt(f32(hd));
  var m: f32 = -1e30;
  for (var t: u32 = 0u; t < n; t = t + 1u) {
    var s: f32 = 0.0;
    for (var d: u32 = 0u; d < hd; d = d + 1u) {
      s = s + AQ[h * hd + d] * AK[t * nkv * hd + kvOff + d];
    }
    s = s * scale;
    if (lid.x == 0u) { SC[t] = s; }
    m = max(m, s);
  }
  workgroupBarrier();
  /* softmax（单线程串行，位置数很小） */
  if (lid.x == 0u) {
    var sum: f32 = 0.0;
    for (var t: u32 = 0u; t < n; t = t + 1u) { SC[t] = exp(SC[t] - m); sum = sum + SC[t]; }
    let inv = 1.0 / sum;
    for (var t: u32 = 0u; t < n; t = t + 1u) { SC[t] = SC[t] * inv; }
  }
  workgroupBarrier();
  /* 加权求和 v */
  for (var d: u32 = lid.x; d < hd; d = d + 64u) {
    var acc: f32 = 0.0;
    for (var t: u32 = 0u; t < n; t = t + 1u) {
      acc = acc + SC[t] * AV[t * nkv * hd + kvOff + d];
    }
    AC[h * hd + d] = acc;
  }
}

/* ── SwiGLU: act = silu(g) * u ─────────────────────────────────────── */
@group(0) @binding(0) var<storage, read> SG: array<f32>;
@group(0) @binding(1) var<storage, read> SU: array<f32>;
@group(0) @binding(2) var<storage, read_write> SO: array<f32>;
@group(0) @binding(3) var<uniform> SP: P;
@compute @workgroup_size(256)
fn silu(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = gid.x;
  if (i >= SP.nIn) { return; }
  let g = SG[i];
  SO[i] = (g / (1.0 + exp(-g))) * SU[i];
}

/* ── 把新 k/v 写进 KV 缓存的第 pos 行 ───────────────────────────────── */
@group(0) @binding(0) var<storage, read> KS: array<f32>;
@group(0) @binding(1) var<storage, read_write> KD: array<f32>;
@group(0) @binding(2) var<uniform> KP: P;   /* nIn=行宽, nOut=pos */
@compute @workgroup_size(64)
fn kvput(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = gid.x;
  if (i >= KP.nIn) { return; }
  KD[KP.nOut * KP.nIn + i] = KS[i];
}
`;

const P = (nIn, nOut, a = 0, b = 0) => {
  const u = new Uint32Array(4);
  u[0] = nIn >>> 0; u[1] = nOut >>> 0;
  const f = new Float32Array(u.buffer);
  f[2] = a; f[3] = b;
  return u;
};

/** 一个哨兵：GPU 侧模型 */
export class WGPUModel {
  constructor(GGUF, device, adapter) {
    this.M = GGUF;
    this.dev = device;
    this.adapter = adapter;
    this.buf = new Map();          // name → GPUBuffer
    this.uniforms = new Map();
    this.bytes = 0;
  }

  /* 反量化 + 上传（一次性） */
  upload(onProgress) {
    const M = this.M, dev = this.dev;
    const names = ["token_embd.weight", "output_norm.weight"];
    for (let l = 0; l < M.nLayer; l++) {
      const p = "blk." + l + ".";
      for (const t of ["attn_norm.weight", "attn_q.weight", "attn_k.weight", "attn_v.weight",
                       "attn_output.weight", "ffn_norm.weight", "ffn_gate.weight",
                       "ffn_up.weight", "ffn_down.weight"]) names.push(p + t);
    }
    let i = 0;
    for (const n of names) {
      const arr = M.tensor(n);
      /* 权重也要 COPY_SRC：词嵌入那步是 copyBufferToBuffer 从权重里取一行。
         只有 STORAGE|COPY_DST 时整条命令缓冲校验失败（实测：encoder state is invalid）。 */
      const b = dev.createBuffer({ size: arr.byteLength,
        usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST | GPUBufferUsage.COPY_SRC });
      dev.queue.writeBuffer(b, 0, arr);
      this.buf.set(n, b);
      this.bytes += arr.byteLength;
      if (onProgress && (++i % 9 === 0)) onProgress(i, names.length, this.bytes);
    }
    return { tensors: names.length, mib: +(this.bytes / 1048576).toFixed(1) };
  }

  /* Range 模式：并行预取所有权重块，再逐个写入 GPU */
  async uploadAsync(onProgress) {
    const M = this.M, dev = this.dev;
    const names = ["token_embd.weight", "output_norm.weight"];
    for (let l = 0; l < M.nLayer; l++) {
      const p = "blk." + l + ".";
      for (const t of ["attn_norm.weight", "attn_q.weight", "attn_k.weight", "attn_v.weight",
                       "attn_output.weight", "ffn_norm.weight", "ffn_gate.weight",
                       "ffn_up.weight", "ffn_down.weight"]) names.push(p + t);
    }
    /* 并行预取所有 tensor（RangeBuffer 内部用 64MB 块缓存，实际网络请求 ≤ ceil(total/64MB)） */
    const tasks = names.map(n => M.tensorAsync(n));
    const arrays = await Promise.all(tasks);
    let i = 0;
    for (const arr of arrays) {
      const n = names[i++];
      const b = dev.createBuffer({ size: arr.byteLength,
        usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST | GPUBufferUsage.COPY_SRC });
      dev.queue.writeBuffer(b, 0, arr);
      this.buf.set(n, b);
      this.bytes += arr.byteLength;
      if (onProgress) onProgress(i, names.length, this.bytes);
    }
    return { tensors: names.length, mib: +(this.bytes / 1048576).toFixed(1) };
  }

  _act(name, count) {
    if (!this.buf.has(name)) {
      /* 🔴 2026-10-30：必须带 COPY_DST —— 词嵌入那一步是 copyBufferToBuffer 写进 act.x 的，
         少了它会整体校验失败、整条命令缓冲被丢弃 ⇒ 所有激活恒 0、argmax 恒 0（<|endoftext|>）。 */
      const b = this.dev.createBuffer({ size: count * 4,
        usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST });
      this.buf.set(name, b);
    }
    return this.buf.get(name);
  }

  _uni(key, arr) {
    const b = this.dev.createBuffer({ size: 16, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST });
    this.dev.queue.writeBuffer(b, 0, arr);
    this.uniforms.set(key, b);
    return b;
  }

  static async create(GGUF) {
    const adapter = await navigator.gpu.requestAdapter();
    if (!adapter) throw new Error("requestAdapter 返回 null");
    const device = await adapter.requestDevice();
    /* 2026-10-30：WebGPU 的校验错误是**静默**的 —— 命令录制失败时 onSubmittedWorkDone
       照样立刻 resolve，表现成"2ms 跑完、结果是垃圾"。必须挂错误钩子。 */
    const gpuErrors = [];
    device.onuncapturederror = (e) => { gpuErrors.push(String(e.error && e.error.message || e)); };
    const mod = device.createShaderModule({ code: WK });
    const info = await mod.getCompilationInfo();
    const errs = info.messages.filter(m => m.type === "error");
    if (errs.length) throw new Error("WGSL 编译错误: " + errs.map(e => e.message).join("; "));
    const pipes = {};
    for (const e of ["mv", "rms", "add", "rope", "attn", "silu", "kvput"])
      pipes[e] = device.createComputePipeline({ layout: "auto", compute: { module: mod, entryPoint: e } });
    const m = new WGPUModel(GGUF, device, adapter);
    m.pipes = pipes;
    m.gpuErrors = gpuErrors;
    return m;
  }
}

/* ── 前向编排：一个 token 一个 encoder，只 fence 一次 ───────────────── */
WGPUModel.prototype.prepare = function (maxPos = 64) {
  const M = this.M, dev = this.dev, d = M.nEmbd, ff = M.nFF, hd = M.headDim;
  this.maxPos = maxPos;
  const A = (n, c) => this._act(n, c);
  const b = {
    x: A("act.x", d), h: A("act.h", d), q: A("act.q", d),
    k: A("act.k", M.nKV * hd), v: A("act.v", M.nKV * hd),
    ctx: A("act.ctx", d), o: A("act.o", d), h2: A("act.h2", d),
    g: A("act.g", ff), u: A("act.u", ff), act: A("act.act", ff),
    dn: A("act.dn", d), xf: A("act.xf", d),
    logits: A("act.logits", M.tokens.length),
  };
  const kv = [];
  for (let l = 0; l < M.nLayer; l++) {
    kv.push({
      k: this._act("kv.k." + l, maxPos * M.nKV * hd),
      v: this._act("kv.v." + l, maxPos * M.nKV * hd),
    });
  }
  this.A = b; this.KV = kv;

  const rd = dev.createBuffer({ size: M.tokens.length * 4, usage: GPUBufferUsage.MAP_READ | GPUBufferUsage.COPY_DST });
  this.readback = rd;

  /* 预建 bind group（每 token 不重建，否则 CPU 侧会吃掉全部收益） */
  const L = this.pipes;
  const bg = (pipe, entries) => dev.createBindGroup({ layout: pipe.getBindGroupLayout(0), entries });
  const mk = (W, X, Y, u) => [{ binding: 0, resource: { buffer: W } },
                              { binding: 1, resource: { buffer: X } },
                              { binding: 2, resource: { buffer: Y } },
                              { binding: 3, resource: { buffer: u } }];
  this.B = { mv: [], rms: [], rope: [], attn: [], silu: [], add: [], kvput: [] };
  for (let l = 0; l < M.nLayer; l++) {
    const p = "blk." + l + ".";
    const G = n => this.buf.get(p + n);
    const row = {};
    row.q  = bg(L.mv, mk(G("attn_q.weight"), b.h, b.q, this._uni("u.q" + l,  P(d, d))));
    row.k  = bg(L.mv, mk(G("attn_k.weight"), b.h, b.k, this._uni("u.k" + l,  P(d, M.nKV * hd))));
    row.v  = bg(L.mv, mk(G("attn_v.weight"), b.h, b.v, this._uni("u.v" + l,  P(d, M.nKV * hd))));
    row.o  = bg(L.mv, mk(G("attn_output.weight"), b.ctx, b.o, this._uni("u.o" + l, P(d, d))));
    row.ga = bg(L.mv, mk(G("ffn_gate.weight"), b.h2, b.g, this._uni("u.ga" + l, P(d, ff))));
    row.up = bg(L.mv, mk(G("ffn_up.weight"), b.h2, b.u, this._uni("u.up" + l, P(d, ff))));
    row.dn = bg(L.mv, mk(G("ffn_down.weight"), b.act, b.dn, this._uni("u.dn" + l, P(ff, d))));
    row.rn1 = bg(L.rms, [{ binding: 0, resource: { buffer: b.x } },
                         { binding: 1, resource: { buffer: G("attn_norm.weight") } },
                         { binding: 2, resource: { buffer: b.h } },
                         { binding: 3, resource: { buffer: this._uni("u.rn1" + l, P(d, d, M.eps)) } }]);
    row.rn2 = bg(L.rms, [{ binding: 0, resource: { buffer: b.x } },
                         { binding: 1, resource: { buffer: G("ffn_norm.weight") } },
                         { binding: 2, resource: { buffer: b.h2 } },
                         { binding: 3, resource: { buffer: this._uni("u.rn2" + l, P(d, d, M.eps)) } }]);
    row.rq = bg(L.rope, [{ binding: 0, resource: { buffer: b.q } },
                         { binding: 1, resource: { buffer: this._uni("u.rq" + l, P(M.nHead * hd, hd, 0, M.ropeTheta)) } }]);
    row.rk = bg(L.rope, [{ binding: 0, resource: { buffer: b.k } },
                         { binding: 1, resource: { buffer: this._uni("u.rk" + l, P(M.nKV * hd, hd, 0, M.ropeTheta)) } }]);
    row.kput = bg(L.kvput, [{ binding: 0, resource: { buffer: b.k } },
                            { binding: 1, resource: { buffer: this.KV[l].k } },
                            { binding: 2, resource: { buffer: this._uni("u.kput" + l, P(M.nKV * hd, 0)) } }]);
    row.vput = bg(L.kvput, [{ binding: 0, resource: { buffer: b.v } },
                            { binding: 1, resource: { buffer: this.KV[l].v } },
                            { binding: 2, resource: { buffer: this._uni("u.vput" + l, P(M.nKV * hd, 0)) } }]);
    row.a = bg(L.attn, [{ binding: 0, resource: { buffer: b.q } },
                        { binding: 1, resource: { buffer: this.KV[l].k } },
                        { binding: 2, resource: { buffer: this.KV[l].v } },
                        { binding: 3, resource: { buffer: b.ctx } },
                        { binding: 4, resource: { buffer: this._uni("u.a" + l, P(d, hd, M.nKV, M.nHead)) } }]);
    row.si = bg(L.silu, [{ binding: 0, resource: { buffer: b.g } },
                         { binding: 1, resource: { buffer: b.u } },
                         { binding: 2, resource: { buffer: b.act } },
                         { binding: 3, resource: { buffer: this._uni("u.si" + l, P(ff, ff)) } }]);
    row.ad1 = bg(L.add, [{ binding: 0, resource: { buffer: b.x } },
                         { binding: 1, resource: { buffer: b.o } },
                         { binding: 2, resource: { buffer: this._uni("u.ad1" + l, P(d, d)) } }]);
    row.ad2 = bg(L.add, [{ binding: 0, resource: { buffer: b.x } },
                         { binding: 1, resource: { buffer: b.dn } },
                         { binding: 2, resource: { buffer: this._uni("u.ad2" + l, P(d, d)) } }]);
    this.B.mv.push(row);
  }
  this.bRow = {
    emb: bg(L.mv, mk(this.buf.get("token_embd.weight"), b.xf, b.logits,
                     this._uni("u.emb", P(d, M.tokens.length)))),
    outn: bg(L.rms, [{ binding: 0, resource: { buffer: b.x } },
                     { binding: 1, resource: { buffer: this.buf.get("output_norm.weight") } },
                     { binding: 2, resource: { buffer: b.xf } },
                     { binding: 3, resource: { buffer: this._uni("u.outn", P(d, d, M.eps)) } }]),
  };
  return true;
};

/* 一个 token 的前向：全部算子排进一个 encoder，最后 fence 一次 */
WGPUModel.prototype.step = async function (tokenId, pos) {
  const M = this.M, dev = this.dev, d = M.nEmbd, hd = M.headDim, ff = M.nFF;
  const nKV = M.nKV, A = this.A;
  const enc = dev.createCommandEncoder();

  /* 词嵌入 → x（从 token_embd 里取一行；用 GPU 拷贝避免大反量化回读） */
  const src = this.buf.get("token_embd.weight");
  enc.copyBufferToBuffer(src, tokenId * d * 4, A.x, 0, d * 4);

  const run = (pipe, bg2, n) => {
    const p = enc.beginComputePass();
    p.setPipeline(pipe); p.setBindGroup(0, bg2);
    p.dispatchWorkgroups(Math.ceil(n / 64));
    p.end();
  };
  const run256 = (pipe, bg2, n) => {
    const p = enc.beginComputePass();
    p.setPipeline(pipe); p.setBindGroup(0, bg2);
    p.dispatchWorkgroups(Math.ceil(n / 256));
    p.end();
  };

  for (let l = 0; l < M.nLayer; l++) {
    const R = this.B.mv[l];
    /* 位置相关的 uniform 要逐 token 更新 */
    dev.queue.writeBuffer(this.uniforms.get("u.rq" + l), 0, P(M.nHead * hd, hd, pos, M.ropeTheta));
    dev.queue.writeBuffer(this.uniforms.get("u.rk" + l), 0, P(nKV * hd, hd, pos, M.ropeTheta));
    dev.queue.writeBuffer(this.uniforms.get("u.kput" + l), 0, P(nKV * hd, pos));
    dev.queue.writeBuffer(this.uniforms.get("u.vput" + l), 0, P(nKV * hd, pos));
    dev.queue.writeBuffer(this.uniforms.get("u.a" + l), 0, P(pos + 1, hd, nKV, M.nHead));

    run256(this.pipes.rms, R.rn1, d);                    /* h = rmsnorm(x) */
    run(this.pipes.mv, R.q, d);                          /* q */
    run(this.pipes.mv, R.k, nKV * hd);                   /* k */
    run(this.pipes.mv, R.v, nKV * hd);                   /* v */
    run(this.pipes.rope, R.rq, M.nHead * hd / 2 * 1);    /* rope(q) —— 只跑 half 个索引 */
    run(this.pipes.rope, R.rk, nKV * hd / 2);
    run(this.pipes.kvput, R.kput, nKV * hd);
    run(this.pipes.kvput, R.vput, nKV * hd);
    /* 注意力：一个 head 一个工作组（9 个） */
    const pa = enc.beginComputePass();
    pa.setPipeline(this.pipes.attn); pa.setBindGroup(0, R.a);
    pa.dispatchWorkgroups(M.nHead);
    pa.end();
    run(this.pipes.mv, R.o, d);                          /* o = W·ctx */
    run256(this.pipes.add, R.ad1, d);                    /* x += o */

    run256(this.pipes.rms, R.rn2, d);
    run(this.pipes.mv, R.ga, ff);
    run(this.pipes.mv, R.up, ff);
    run256(this.pipes.silu, R.si, ff);
    run(this.pipes.mv, R.dn, d);
    run256(this.pipes.add, R.ad2, d);
  }
  run256(this.pipes.rms, this.bRow.outn, d);              /* xf = rmsnorm(x) */
  run(this.pipes.mv, this.bRow.emb, M.tokens.length);      /* logits */

  enc.copyBufferToBuffer(A.logits, 0, this.readback, 0, M.tokens.length * 4);
  dev.queue.submit([enc.finish()]);
  await dev.queue.onSubmittedWorkDone();
  await this.readback.mapAsync(GPUMapMode.READ);
  const lg = new Float32Array(this.readback.getMappedRange()).slice();
  this.readback.unmap();
  return lg;
};

WGPUModel.prototype.reset = function () { this.pos = 0; };

/* 调试：把任意激活缓冲回读几个值（拷到 readback 再 map） */
WGPUModel.prototype.peek = async function (name, count = 4) {
  const dev = this.dev, src = this.A[name];
  const n = Math.min(count, Math.floor(src.size / 4));
  const enc = dev.createCommandEncoder();
  enc.copyBufferToBuffer(src, 0, this.readback, 0, n * 4);
  dev.queue.submit([enc.finish()]);
  await dev.queue.onSubmittedWorkDone();
  await this.readback.mapAsync(GPUMapMode.READ);
  const a = new Float32Array(this.readback.getMappedRange(0, n * 4)).slice();
  this.readback.unmap();
  return a;
};
