# -*- coding: utf-8 -*-
"""GGUF Q4_0 契约检查 —— 判定「是量化调用错了，还是 Q4_0 本来就不够」。

背景：同一份权重，fp16 产物能通顺、Q4_0 产物只会复读。范围收窄到
「gguf.quants.quantize 这一步」之后，剩下只有三种可能，本脚本用**不加载模型**的方式把它们分开：

  ① 库的 Q4_0 与 ggml 规范不一致（nibble 打包顺序 / 尺度符号 / 截断方式）
  ② 库没问题，是写文件时 shape / dtype 传错了（raw_shape 那条约定）
  ③ 两者都没错，是 Q4_0（每 32 元素单尺度）喂不动这份权重（离群通道）

## 用法（在装了 gguf 的那台机器上跑）

  python gguf-q4-contract-check.py env
      30 秒。打印 gguf 版本、add_tensor 的真实形参与源码、QuantizedArray 的
      shape/dtype/nbytes。→ 用来回答「raw_dtype 那条调用合不合法」。

  python gguf-q4-contract-check.py selftest
      不需要 gguf。验本脚本的 ggml 参考实现自洽（编码→解码误差 ≈ 半个步长）。

  python gguf-q4-contract-check.py compare
      随机张量：库产物 vs ggml 规范，逐字节。
      python gguf-q4-contract-check.py compare --npz layer_00.npz --key self_attn.q_proj
      真实张量：同上，但用真权重。

  python gguf-q4-contract-check.py scan --layers <_fp16mmap 目录>
      每张量的 Q4_0 理论误差排行（相对张量自身 RMS）。

## 判读

  env      → add_tensor 形参里**没有** raw_shape ⇒ add_tensor(name, q, raw_dtype=...)
             是合法用法（形状由 QuantizedArray 自带），可排除 ②。
  compare  → 字节全等 ⇒ 量化调用没 bug，直接转 K-quant（③）；
             不等，且 spec 解码误差≈0 / pairs 解码误差大
             ⇒ 库按「相邻两元素配一对」打包，llama.cpp 按「前半=低 nibble」解包。
                这就是那个「能加载、能跑、数值错」的 bug —— 换成官方 llama-quantize。
  scan     → Q4_0 对高斯权重的理论水位 ≈ 8.6%（本机实测，不是 2%）；
             某张量明显高于同批中位数 ⇒ 它有离群通道，Q4_0 不该用在它身上。

退出码：0 = 通过 / 一致；2 = 发现不一致（可当闸用）。
"""
from __future__ import annotations

import argparse
import os
import sys
import textwrap
import traceback

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

QK = 32                      # 每块元素数
BLOCK_BYTES = 18             # block_q4_0: ggml_half d(2) + uint8 qs[16]


# --------------------------------------------------------------------------
# ggml 的 Q4_0 参考实现（逐字节复刻 quantize_row_q4_0_ref / dequantize_row_q4_0）
# --------------------------------------------------------------------------
def ref_quantize(x: np.ndarray, chunk: int = 256) -> np.ndarray:
    """(rows, k) float32 → (rows, k/32*18) uint8。k 必须是 32 的倍数。

    逐行块处理：这张机器只有 7.4 GB 内存，3584x18944 的 down_proj 一次算要 ~1 GB 临时空间。
    """
    x = np.ascontiguousarray(x, dtype=np.float32)
    rows, k = x.shape
    if k % QK:
        raise ValueError("ne0=%d 不是 %d 的倍数，Q4_0 无定义" % (k, QK))
    nb = k // QK
    out = np.empty((rows, nb, BLOCK_BYTES), dtype=np.uint8)

    for lo in range(0, rows, chunk):
        hi = min(lo + chunk, rows)
        n = hi - lo
        xr = x[lo:hi].reshape(n, nb, QK)

        # 尺度：取块内**绝对值最大的那个带符号值** vmax，d = vmax / -8
        idx = np.argmax(np.abs(xr), axis=2)[..., None]
        vmax = np.take_along_axis(xr, idx, axis=2)[..., 0]
        d = (vmax / -8.0).astype(np.float32)

        dsafe = np.where(d != 0.0, d, 1.0).astype(np.float32)
        id_ = np.where(d != 0.0, 1.0 / dsafe, 0.0).astype(np.float32)

        # C 的 (int8_t) 截断 = 朝零取整，不是四舍五入
        xi = np.trunc(xr * id_[..., None] + 8.5).astype(np.int32)
        np.clip(xi, 0, 15, out=xi)

        # 打包顺序：qs[j] 的低 nibble 是元素 j，高 nibble 是元素 j+16（不是相邻两元素）
        qs = (xi[:, :, :16] | (xi[:, :, 16:] << 4)).astype(np.uint8)
        out[lo:hi, :, 0:2] = d.astype(np.float16).view(np.uint8).reshape(n, nb, 2)
        out[lo:hi, :, 2:] = qs

    return out.reshape(rows, nb * BLOCK_BYTES)


def ref_dequantize(buf: np.ndarray, rows: int, k: int, layout: str = "spec",
                  chunk: int = 256) -> np.ndarray:
    """(rows, nb, 18) uint8 → (rows, k) float32。

    layout="spec"  : 低 nibble = 前半 16 个元素（llama.cpp / ggml 的口径）
    layout="pairs" : 低 nibble = 第 2i 个元素（另一派实现常见的错法）
    """
    nb = k // QK
    b = np.asarray(buf, dtype=np.uint8).reshape(rows, nb, BLOCK_BYTES)
    v = np.empty((rows, k), dtype=np.float32)

    for lo in range(0, rows, chunk):
        hi = min(lo + chunk, rows)
        n = hi - lo
        bb = b[lo:hi]
        d = bb[:, :, 0:2].copy().view(np.float16).astype(np.float32)[..., 0]
        qs = bb[:, :, 2:]
        lo_n = (qs & 0x0F).astype(np.float32) - 8.0
        hi_n = ((qs >> 4) & 0x0F).astype(np.float32) - 8.0

        blk = np.empty((n, nb, QK), dtype=np.float32)
        if layout == "spec":
            blk[:, :, :16] = lo_n * d[..., None]
            blk[:, :, 16:] = hi_n * d[..., None]
        elif layout == "pairs":
            blk[:, :, 0::2] = lo_n * d[..., None]
            blk[:, :, 1::2] = hi_n * d[..., None]
        else:
            raise ValueError("未知 layout: %s" % layout)
        v[lo:hi] = blk.reshape(n, k)

    return v


def _stats(ref: np.ndarray, got: np.ndarray, chunk: int = 256) -> dict:
    """分块统计，避免 float64 全量副本把内存打爆。"""
    sse = 0.0
    sq = 0.0
    mx = 0.0
    n = 0
    for lo in range(0, ref.shape[0], chunk):
        hi = min(lo + chunk, ref.shape[0])
        a = ref[lo:hi].astype(np.float32)
        b = got[lo:hi].astype(np.float32)
        e = a - b
        sse += float(np.einsum("ij,ij->", e, e))
        sq += float(np.einsum("ij,ij->", a, a))
        mx = max(mx, float(np.abs(e).max()))
        n += a.size
    rms = (sse / max(n, 1)) ** 0.5
    scale = (sq / max(n, 1)) ** 0.5 or 1.0
    return {"max": mx, "rms": rms, "rel_rms": rms / scale, "scale": scale}


def _stats_quant(x: np.ndarray, buf: np.ndarray, layout: str = "spec",
                 chunk: int = 128) -> dict:
    """直接对着量化字节分块统计误差 —— 不materialize整个反量化张量（省 259MB×2）。"""
    rows, k = x.shape
    nb = k // QK
    b = np.asarray(buf, dtype=np.uint8).reshape(rows, nb, BLOCK_BYTES)
    sse = sq = mx = 0.0
    n = 0

    for lo in range(0, rows, chunk):
        hi = min(lo + chunk, rows)
        nn = hi - lo
        a = x[lo:hi].astype(np.float32)
        bb = b[lo:hi]
        d = bb[:, :, 0:2].copy().view(np.float16).astype(np.float32)[..., 0]
        qs = bb[:, :, 2:]
        lo_n = (qs & 0x0F).astype(np.float32) - 8.0
        hi_n = ((qs >> 4) & 0x0F).astype(np.float32) - 8.0

        blk = np.empty((nn, nb, QK), dtype=np.float32)
        if layout == "spec":
            blk[:, :, :16] = lo_n * d[..., None]
            blk[:, :, 16:] = hi_n * d[..., None]
        elif layout == "pairs":
            blk[:, :, 0::2] = lo_n * d[..., None]
            blk[:, :, 1::2] = hi_n * d[..., None]
        else:
            raise ValueError("未知 layout: %s" % layout)

        e = a - blk.reshape(nn, k)
        sse += float(np.einsum("ij,ij->", e, e))
        sq += float(np.einsum("ij,ij->", a, a))
        mx = max(mx, float(np.abs(e).max()))
        n += a.size

    rms = (sse / max(n, 1)) ** 0.5
    scale = (sq / max(n, 1)) ** 0.5 or 1.0
    return {"max": mx, "rms": rms, "rel_rms": rms / scale, "scale": scale}


# --------------------------------------------------------------------------
# 子命令
# --------------------------------------------------------------------------
def cmd_env(args) -> int:
    import inspect

    try:
        import gguf  # noqa
    except Exception:
        print("[x] 这个解释器没有 gguf 包：%s" % sys.executable)
        print("    在装了 gguf 的那台机器上跑这个子命令（本脚本的 selftest 不需要 gguf）。")
        return 2

    print("gguf 版本 :", getattr(gguf, "__version__", "?"))
    print("gguf 路径 :", gguf.__file__)
    print("numpy     :", np.__version__)
    print()

    has_raw_shape = None
    shape_ok = False
    try:
        sig = inspect.signature(gguf.GGUFWriter.add_tensor)
        print("add_tensor%s" % str(sig))
        has_raw_shape = "raw_shape" in sig.parameters
        print("  → 有 raw_shape 形参吗：%s" % ("有" if has_raw_shape else "没有"))
    except Exception:
        traceback.print_exc()

    print()
    print("---- add_tensor 源码 ----")
    try:
        print(textwrap.indent(textwrap.dedent(inspect.getsource(gguf.GGUFWriter.add_tensor)), "  "))
    except Exception:
        print("  (取不到源码)")

    print()
    print("---- quantize() 的返回物 ----")
    rng = np.random.default_rng(0)
    x = rng.normal(0, 0.02, (64, 256)).astype(np.float32)
    try:
        q = gguf.quants.quantize(x, gguf.GGMLQuantizationType.Q4_0)
        print("  type        :", type(q).__name__)
        print("  .shape      :", getattr(q, "shape", "<无这个属性>"))
        print("  .dtype      :", getattr(q, "dtype", "<无这个属性>"))
        print("  .qtype      :", getattr(q, "qtype", "<无这个属性>"))
        data = np.asarray(getattr(q, "data", q)).ravel()
        print("  bytes       : %d  (原始张量 %d 元素 x 4B = %d；Q4_0 期望 %d)"
              % (data.nbytes, x.size, x.nbytes, 64 * (256 // 32) * 18))
        shape_ok = tuple(getattr(q, "shape", ())) == x.shape
        print("  → shape 是否等于原始张量：%s" % ("是" if shape_ok else "否"))
    except Exception:
        traceback.print_exc()
        return 2

    print()
    if has_raw_shape is False and shape_ok:
        print("[✓] 结论：add_tensor 没有 raw_shape 形参，且 QuantizedArray 自带原始 shape")
        print("    ⇒ add_tensor(name, q, raw_dtype=QTYPE) 是合法用法，可以排除「传参传错」。")
        print("    ⇒ 下一步跑 compare，看字节对不对。")
        return 0
    if has_raw_shape is True:
        print("[!] 结论：这个版本的 add_tensor 有 raw_shape 形参 —— 要确认不传它时用的是")
        print("    QuantizedArray.shape 还是打包后的 shape。看上面源码里 tensor_shape 怎么取的。")
        return 0
    print("[!] 结论：shape 没有保留 —— 写文件时必须显式传 raw_shape=原始形状，否则 llama.cpp")
    print("    读到的是打包后的形状（这是能加载但数值错的一条真实路径）。")
    return 2


def cmd_selftest(args) -> int:
    rng = np.random.default_rng(20261024)
    x = rng.normal(0, 0.02, (128, 512)).astype(np.float32)
    buf = ref_quantize(x)
    back = ref_dequantize(buf, 128, 512, "spec")
    st = _stats(x, back)

    # 理论水位：步长 = 块内 max/8，均匀量化误差 RMS ≈ step/√12
    blocks = x.reshape(128, 16, QK)
    step = float(np.mean(np.abs(blocks).max(axis=2) / 8.0))
    expect = step / np.sqrt(12.0)

    print("参考实现自洽检查（128x512 N(0, 0.02)）")
    print("  字节数      : %d（期望 %d）" % (buf.size, 128 * 16 * 18))
    print("  max 误差    : %.6f" % st["max"])
    print("  RMS 误差    : %.6f   rel_rms = %.2f%%" % (st["rms"], st["rel_rms"] * 100))
    print("  理论 RMS    : %.6f（step/√12）" % expect)

    ok_len = buf.size == 128 * 16 * 18
    ok_err = st["rms"] < expect * 1.5
    print("  → 长度 %s · 误差量级 %s" % ("OK" if ok_len else "FAIL", "OK" if ok_err else "FAIL"))
    if not (ok_len and ok_err):
        print("[x] 参考实现自己就不对，先修脚本再谈别的。")
        return 2
    print("[✓] 参考实现可用：它按「低 nibble=前半 16 元素」打包，与 ggml 一致。")
    print("    注：8.6% 不是异常 —— Q4_0 每 32 元素一个尺度，对高斯权重的 rel_rms 理论值就是 ~8.6%。")
    return 0


def cmd_compare(args) -> int:
    if args.npz:
        z = np.load(args.npz)
        if args.key not in z:
            print("[x] %s 里没有键 %r；现有键：%s" % (args.npz, args.key, ", ".join(sorted(z.keys()))))
            return 2
        x = np.ascontiguousarray(z[args.key], dtype=np.float32)
        if x.ndim != 2:
            print("[x] 只有二维张量能用 Q4_0；这个键是 %d 维" % x.ndim)
            return 2
        label = "%s:%s %s" % (os.path.basename(args.npz), args.key, x.shape)
    else:
        rng = np.random.default_rng(7)
        x = rng.normal(0, 0.02, (256, 512)).astype(np.float32)
        label = "random 256x512 N(0,0.02)"

    ref = ref_quantize(x)
    print("输入：%s" % label)
    print("  元素 %d · 块数 %d · 参考产物 %d 字节" % (x.size, x.size // QK, ref.size))

    try:
        import gguf
        q = gguf.quants.quantize(x, gguf.GGMLQuantizationType.Q4_0)
    except Exception as exc:
        print("  [!] 没有可用的 gguf（%s）—— 只做参考实现自洽检查：" % type(exc).__name__)
        st = _stats_quant(x, ref)
        print("      ref 解码 max=%.6f rms=%.6f rel_rms=%.2f%%"
              % (st["max"], st["rms"], st["rel_rms"] * 100))
        return 0

    lib = np.asarray(getattr(q, "data", q)).ravel().view(np.uint8)
    print("  库产物 %d 字节" % lib.size)

    if lib.size != ref.size:
        print("[x] 长度就不对（库 %d vs 规范 %d）—— 先看 env 里 QuantizedArray 的 shape。"
              % (lib.size, ref.size))
        return 2

    if lib.tobytes() == ref.tobytes():
        print("[✓] 与 ggml 规范**逐字节全等** ⇒ 这个库的 Q4_0 没写错，量化调用无罪。")
        print("    下一步不要再改量化代码：直接换 K-quant（Q4_K_M），或查 Q4_0 对这份权重的离群通道。")
        return 0

    # 不等 —— 定位差异，并判断是「尺度」还是「nibble 顺序」的问题
    diff = np.nonzero(lib != ref)[0]
    print("[x] 不一致：%d / %d 字节不同，首个差异在第 %d 字节" % (diff.size, ref.size, diff[0]))
    print("    首个差异落在第 %d 块、块内偏移 %d（0-1=d，2-17=qs）"
          % (diff[0] // BLOCK_BYTES, diff[0] % BLOCK_BYTES))

    rows, k = x.shape
    d_lib = lib.reshape(-1, BLOCK_BYTES)[:, 0:2]
    d_ref = ref.reshape(-1, BLOCK_BYTES)[:, 0:2]
    d_same = float(np.mean(np.all(d_lib == d_ref, axis=1)))
    print("    尺度 d 相同的块占比：%.1f%%" % (d_same * 100))

    for layout, name in (("spec", "低nibble=前半16元素（llama.cpp 口径）"),
                         ("pairs", "低nibble=相邻两元素（常见错法）")):
        try:
            st = _stats_quant(x, lib, layout)
        except Exception:
            continue
        print("    按 [%s] 解码库产物：max=%.6f rms=%.6f rel_rms=%.2f%%"
              % (name, st["max"], st["rms"], st["rel_rms"] * 100))

    print()
    print("[判读] 如果 spec 的 rel_rms 明显大于 pairs 的，就是这个库的打包顺序与 llama.cpp 反了：")
    print("       文件能加载、能跑、但每个 32 元素块内部的数值被重新排列 ⇒ 输出退化成复读。")
    print("       修法：不要改库，直接用官方 llama-quantize 重做（路 B）。")
    return 2


def cmd_scan(args) -> int:
    d = args.layers
    files = sorted(f for f in os.listdir(d) if f.endswith(".npz"))
    if not files:
        print("[x] %s 里没有 npz" % d)
        return 2

    rows_out = []
    for fn in files[: args.limit]:
        z = np.load(os.path.join(d, fn))
        for key in z.files:
            a = z[key]
            if a.ndim != 2 or a.shape[-1] % QK:
                continue
            rows_k, k = a.shape
            tot_sse = tot_sq = 0.0
            mx = 0.0
            cnt = 0
            for lo in range(0, rows_k, 64):
                hi = min(lo + 64, rows_k)
                x = np.ascontiguousarray(a[lo:hi], dtype=np.float32)
                buf = ref_quantize(x, chunk=64)
                st = _stats_quant(x, buf, chunk=64)
                nn = int(x.size)
                tot_sse += (st["rms"] ** 2) * nn
                tot_sq += (st["scale"] ** 2) * nn
                mx = max(mx, st["max"])
                cnt += nn
                del x, buf
            rel = ((tot_sse / cnt) ** 0.5) / (((tot_sq / cnt) ** 0.5) or 1.0)
            rows_out.append((rel, fn, key, tuple(a.shape), mx))
            del a

    if not rows_out:
        print("[x] 没有可量化的二维张量")
        return 2

    rows_out.sort(reverse=True)
    print("Q4_0 理论误差排行（rel_rms 相对张量自身 RMS；高斯权重水位 ~8.6%）")
    med = float(np.median([r[0] for r in rows_out]))
    for rel, fn, key, shape, mx in rows_out[:10]:
        flag = "  <== 偏高" if rel > max(0.15, med * 1.6) else ""
        print("  %6.2f%%  max=%.4f  %-14s %-24s %s%s"
              % (rel * 100, mx, fn, key, shape, flag))
    allr = np.array([r[0] for r in rows_out])
    print("  共 %d 个张量：中位 %.2f%% · 90 分位 %.2f%% · 最大 %.2f%%"
          % (len(allr), np.median(allr) * 100, np.percentile(allr, 90) * 100, allr.max() * 100))
    print()
    print("[判读] 若中位在 8%~9% 附近、只有少数张量明显更高，说明误差**集中在离群通道**，")
    print("       全张量 max（比如 0.047）既不能当「正常」也不能当「烂了」——要按张量看。")
    print("       真正该比的是：同一张量上 Q4_0 的 rel_rms 与 Q4_K 的 rel_rms，差几倍就是几倍。")
    return 0


def cmd_roundtrip(args) -> int:
    """最狠的一条：用 export-gguf-q4.py 里**一模一样的写法**写一个小 GGUF，再读回来核对。

    覆盖的是「② 传参 / 形状 / 类型」这条路径：add_tensor(q, raw_dtype=...) 落盘后，
    llama.cpp 看到的 ne0 是不是原始列数、字节数对不对、解出来还像不像原张量。
    """
    import tempfile

    try:
        import gguf
    except Exception as exc:
        print("[x] 没有 gguf（%s），这条子命令跑不了。" % type(exc).__name__)
        return 2

    rng = np.random.default_rng(11)
    x = rng.normal(0, 0.02, (args.rows, args.cols)).astype(np.float32)
    rows, cols = x.shape
    qtype = gguf.GGMLQuantizationType.Q4_0

    tmp = os.path.join(tempfile.gettempdir(), "q4_contract_rt.gguf")
    if os.path.exists(tmp):
        os.remove(tmp)

    w = gguf.GGUFWriter(tmp, "qwen2")
    w.add_block_count(1)
    w.add_embedding_length(cols)
    w.add_file_type(gguf.LlamaFileType.MOSTLY_Q4_0)
    # ↓ 与 export-gguf-q4.py 第 90-91 行完全相同的调用
    q = gguf.quants.quantize(x, qtype)
    w.add_tensor("blk.0.ffn_down.weight", q, raw_dtype=qtype)
    w.write_header_to_file()
    w.write_kv_data_to_file()
    w.write_tensors_to_file()
    w.close()

    size = os.path.getsize(tmp)
    print("写出 %s · %d 字节" % (os.path.basename(tmp), size))

    r = gguf.GGUFReader(tmp)
    hit = [t for t in r.tensors if t.name == "blk.0.ffn_down.weight"]
    if not hit:
        print("[x] 读回来找不到这个张量（名字写错了？）")
        return 2
    t = hit[0]
    raw = np.asarray(t.data).ravel().view(np.uint8)
    expect_bytes = rows * (cols // QK) * BLOCK_BYTES

    print("  读回 shape  : %s   （读库按 ggml 反序给出：第一维 = ne0 = %s，要等于列数）"
          % (tuple(t.shape), tuple(t.shape)[0]))
    print("  读回 type   : %s" % t.tensor_type.name)
    print("  读回 bytes  : %d（期望 %d）" % (raw.size, expect_bytes))

    ok_shape = tuple(t.shape) == (cols, rows)
    ok_type = t.tensor_type == qtype
    ok_size = raw.size == expect_bytes

    back = ref_dequantize(raw, rows, cols, "spec")
    st = _stats(x, back)
    print("  解回来看    : max=%.6f rms=%.6f rel_rms=%.2f%%"
          % (st["max"], st["rms"], st["rel_rms"] * 100))
    ok_val = st["rel_rms"] < 0.15

    print()
    print("  shape %s · type %s · bytes %s · 数值 %s"
          % ("OK" if ok_shape else "FAIL", "OK" if ok_type else "FAIL",
             "OK" if ok_size else "FAIL", "OK" if ok_val else "FAIL"))

    if ok_shape and ok_type and ok_size and ok_val:
        print("[✓] 写盘→读回这条路径是通的：形状/类型/字节/数值都对得上。")
        print("    ⇒ 与 export-gguf-q4.py 同构的调用**没有**把张量写坏。")
        print("    ⇒ 如果成品还是会复读，问题不在 add_tensor/raw_dtype，而在 Q4_0 对这份权重的适应性。")
        return 0

    print("[x] 这条路径就有问题，把上面四项里 FAIL 的那一项贴出来再谈别的。")
    if not ok_shape:
        print("    shape 不对 = llama.cpp 会按转置或错维读 ⇒ 能加载但输出乱。")
    return 2


def cmd_meta(args) -> int:
    """体检 GGUF 的 tokenizer 键 —— 专抓「eos 缺失 ⇒ 生成到第一个逗号就停」这个坑。

    实测（2026-10-24 本机）：导出脚本用 model.vocab 查特殊 token，而 <|im_end|> 在
    added_tokens 里 ⇒ bos/eos/pad 三个键根本没写进文件 ⇒ llama.cpp 回落 eos=11，
    而 11 解出来是逗号。表现是「只吐两个 token 就收尾，看着还挺通顺」。
    """
    try:
        import gguf
    except Exception:
        print("[x] 没有 gguf")
        return 2

    import gc
    bad = 0
    for path in args.files:
        print("=== %s ===" % os.path.basename(path))
        try:
            r = gguf.GGUFReader(path)
        except Exception as e:
            print("  [x] 打不开：%s" % (str(e) or type(e).__name__))
            bad += 1
            gc.collect()
            continue
        f = r.fields

        toks = None
        if "tokenizer.ggml.tokens" in f:
            try:
                toks = f["tokenizer.ggml.tokens"].contents()
            except Exception:
                toks = None
        n_tok = len(toks) if toks is not None else -1

        def _id(key):
            if key not in f:
                return None
            try:
                v = f[key].contents()
                return int(v[0]) if isinstance(v, (list, tuple)) else int(v)
            except Exception:
                return None

        missing = []
        for short, key in (("bos", "tokenizer.ggml.bos_token_id"),
                           ("eos", "tokenizer.ggml.eos_token_id"),
                           ("pad", "tokenizer.ggml.padding_token_id")):
            i = _id(key)
            if i is None:
                missing.append(short)
                print("  %-4s : 缺失" % short)
            else:
                s = ""
                if toks is not None and 0 <= i < n_tok:
                    s = " = %r" % (toks[i],)
                print("  %-4s : %d%s" % (short, i, s))

        ct = f.get("tokenizer.chat_template")
        print("  chat_template : %s" % ("缺失" if ct is None else "%d 字符" % len(ct.contents())))

        rows = -1
        for t in r.tensors:
            if t.name == "token_embd.weight":
                rows = int(t.shape[-1])
                break
        print("  tokens=%d  token_embd 行数=%d %s" % (
            n_tok, rows, "" if n_tok == rows else "<== 对不上"))

        if missing:
            print("  [x] 缺 %s ⇒ llama.cpp 会用默认值（实测 eos 落到逗号），生成被截断"
                  % "/".join(missing))
            bad += 1
        else:
            print("  [✓] 三个特殊 token id 都在")
        print()
        del r
        gc.collect()

    if bad:
        print("[x] %d/%d 个文件不合格" % (bad, len(args.files)))
        return 2
    print("[✓] 全部合格")
    return 0


# --------------------------------------------------------------------------
# 就地补 KV：不重新量化，只把 bos/eos/pad 三个键插进已产出的 GGUF
# --------------------------------------------------------------------------
_SIZES = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8}


def _read_val(fh, pos: int, vt: int, want: bool = False):
    """读一个 GGUF value，返回 (value 或 None, 新位置)。want=False 时只跳过。"""
    import struct
    if vt in _SIZES:
        n = _SIZES[vt]
        fh.seek(pos)
        raw = fh.read(n)
        val = None
        if want:
            val = struct.unpack("<" + {1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f",
                                       10: "Q", 11: "q", 12: "d", 0: "B", 7: "?"}[vt], raw)[0]
        return val, pos + n
    if vt == 8:                                     # string
        fh.seek(pos)
        n = struct.unpack("<Q", fh.read(8))[0]
        return None, pos + 8 + n
    if vt == 9:                                     # array
        fh.seek(pos)
        inner, cnt = struct.unpack("<IQ", fh.read(12))
        pos += 12
        if inner in _SIZES:
            return None, pos + _SIZES[inner] * cnt
        for _ in range(cnt):                        # string 数组
            pos = _read_val(fh, pos, inner)[1]
        return None, pos
    raise ValueError("未知 value type %d" % vt)


def _kv_u32(key: str, val: int) -> bytes:
    import struct
    kb = key.encode("utf-8")
    return struct.pack("<Q", len(kb)) + kb + struct.pack("<I", 4) + struct.pack("<I", val)


def cmd_fixids(args) -> int:
    """把 bos/eos/pad 三个键插进已有 GGUF —— 不碰任何张量字节。

    做法：GGUF 的 tensor_info.offset 是**相对数据段起点**的，所以只要在 KV 区末尾
    插入 delta 字节（delta 取 alignment 的整数倍），后面整段原样平移即可，
    张量信息与数据一个字节都不用改。
    """
    import shutil
    import struct

    src, dst = args.src, args.dst
    if os.path.exists(dst):
        print("[x] 目标已存在：%s" % dst)
        return 2

    with open(src, "rb") as fh:
        magic, ver, n_t, n_kv = struct.unpack("<4sIQQ", fh.read(24))
        if magic != b"GGUF":
            print("[x] 不是 GGUF：%r" % magic)
            return 2
        pos = 24
        alignment = 32
        seen = set()
        for _ in range(n_kv):
            fh.seek(pos)
            n = struct.unpack("<Q", fh.read(8))[0]
            key = fh.read(n).decode("utf-8")
            vt = struct.unpack("<I", fh.read(4))[0]
            pos = fh.tell()
            if key == "general.alignment":
                val, pos = _read_val(fh, pos, vt, want=True)
                alignment = int(val)
            else:
                pos = _read_val(fh, pos, vt)[1]
            seen.add(key)
        kv_end = pos

        # 扫 tensor_info，算出数据段起点的对齐位置
        pos = kv_end
        for _ in range(n_t):
            fh.seek(pos)
            n = struct.unpack("<Q", fh.read(8))[0]
            pos += 8 + n
            fh.seek(pos)
            n_dims = struct.unpack("<I", fh.read(4))[0]
            pos += 4 + 8 * n_dims + 4 + 8
        infos_end = pos
        data_start = (infos_end + alignment - 1) // alignment * alignment

    adds = [("tokenizer.ggml.bos_token_id", args.bos),
            ("tokenizer.ggml.eos_token_id", args.eos),
            ("tokenizer.ggml.padding_token_id", args.pad)]
    adds = [(k, v) for k, v in adds if k not in seen]
    if not adds:
        print("[✓] 三个键本来就都在，不用补")
        return 0
    raw = b"".join(_kv_u32(k, v) for k, v in adds)
    # 数据段起点由"info 块结束位置向上对齐"决定，**不是**简单加 delta：
    # 原来的 padding 会吸收一部分插入量（实测插 133 字节，数据段只平移 128）。
    new_infos_end = infos_end + len(raw)
    new_data_start = (new_infos_end + alignment - 1) // alignment * alignment
    pad = new_data_start - new_infos_end
    delta = new_data_start - data_start

    # 布局：[head][kv][raw 紧贴][tensor_info][padding + extra][data]
    # 🔴 第一版把 padding 放在 raw 后面 ⇒ tensor_info 被整体推后 31 字节，
    #    读库按"KV 读完就是 info"解析，于是把 info 读成空名字/空形状（实测 n_kv=10 但 tensor=('',F32,())）。
    #    padding 只能放在 info 与 data 之间，且要让数据段起点仍是 alignment 的整数倍。
    with open(src, "rb") as fi, open(dst, "wb") as fo:
        fo.write(struct.pack("<4sIQQ", magic, ver, n_t, n_kv + len(adds)))
        _copy_range(fi, fo, 24, kv_end)
        fo.write(raw)
        _copy_range(fi, fo, kv_end, infos_end)
        fo.write(b"\x00" * pad)
        _copy_range(fi, fo, data_start, os.path.getsize(src))

    print("补入 %d 个键 · KV 增 %d 字节 · 数据段平移 %d 字节（新起点 %d = %d 对齐）"
          % (len(adds), len(raw), delta, new_data_start, alignment))
    print("  %s → %s  (%.2f GB)" % (src, dst, os.path.getsize(dst) / 1024 ** 3))
    return 0


def _copy_range(fi, fo, start: int, end: int, chunk: int = 8 << 20) -> None:
    """显式按区间搬字节。

    第一版用 BufferedReader 包装再 copyfileobj，读预取会吃掉后面的字节，
    导致数据段整段写成 0（实测 B[384:] 全是 \x00）。这里不用任何缓冲包装。
    """
    fi.seek(start)
    left = end - start
    while left > 0:
        b = fi.read(min(chunk, left))
        if not b:
            raise IOError("源文件提前结束：还剩 %d 字节没搬" % left)
        fo.write(b)
        left -= len(b)


def main() -> int:
    p = argparse.ArgumentParser(description="GGUF Q4_0 契约检查")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("env", help="看 add_tensor / QuantizedArray 契约")
    sub.add_parser("selftest", help="不需要 gguf：验参考实现自洽")

    pc = sub.add_parser("compare", help="库产物 vs ggml 规范")
    pc.add_argument("--npz", help="用真实层张量")
    pc.add_argument("--key", default="", help="npz 里的键")

    ps = sub.add_parser("scan", help="每张量的 Q4_0 理论误差排行")
    ps.add_argument("--layers", required=True, help="_fp16mmap 目录")
    ps.add_argument("--limit", type=int, default=28, help="最多读几个 npz（默认 28）")

    pm = sub.add_parser("meta", help="体检 tokenizer 键（bos/eos/pad/chat_template）")
    pm.add_argument("files", nargs="+")

    pf = sub.add_parser("fixids", help="给已有 GGUF 补 bos/eos/pad（不重新量化）")
    pf.add_argument("--src", required=True)
    pf.add_argument("--dst", required=True)
    pf.add_argument("--bos", type=int, default=151643)
    pf.add_argument("--eos", type=int, default=151645)
    pf.add_argument("--pad", type=int, default=151643)

    pr = sub.add_parser("roundtrip", help="写盘→读回：验 add_tensor 这条路径")
    pr.add_argument("--rows", type=int, default=512)
    pr.add_argument("--cols", type=int, default=2048)

    args = p.parse_args()
    if args.cmd == "compare" and args.npz and not args.key:
        print("[x] 给了 --npz 就要给 --key")
        return 2
    return {"env": cmd_env, "selftest": cmd_selftest, "compare": cmd_compare,
            "scan": cmd_scan, "roundtrip": cmd_roundtrip, "meta": cmd_meta,
            "fixids": cmd_fixids}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
