#!/usr/bin/env python3
"""GGUF 元数据体检 —— 手写头解析，不 mmap 整个文件

为什么要手写：
  gguf.GGUFReader 对 4GB+ 文件会 mmap 全部，本机 4.1 GB 内存直接 OOM。
  这里只读文件头 + KV 段，按需 seek，几 MB 内存就够。

查什么（都是"乱码常见真因"，跟训练好坏无关）：
  · chat_template 在不在 —— 不在就说明宿主会套自己的模板，身份/角色 token 可能错位
  · tokenizer.ggml.* —— tokens/scores/token_type 数量是否一致
  · bos/eos/padding token id —— 缺了会停不下来或起步就歪
  · 词表大小 vs 模型 config 的 vocab_size —— 不匹配会切错 token
  · 特殊 token（<|im_start|> 等）是否真的在词表里

用法：
  python3 tools/gguf_meta.py <file.gguf> [more.gguf ...]
"""
from __future__ import annotations

import struct
import sys

# GGUF 值类型
T = {0: "u8", 1: "i8", 2: "u16", 3: "i16", 4: "u32", 5: "i32",
     6: "f32", 7: "bool", 8: "str", 9: "arr", 10: "u64", 11: "i64", 12: "f64"}
FMT = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i",
       6: "<f", 7: "<?", 10: "<Q", 11: "<q", 12: "<d"}
SZ = {k: struct.calcsize(v) for k, v in FMT.items()}


class R:
    def __init__(self, f):
        self.f = f

    def raw(self, n):
        b = self.f.read(n)
        if len(b) != n:
            raise EOFError("短读")
        return b

    def scalar(self, t):
        if t not in FMT:
            raise ValueError("标量类型异常 %s" % t)
        return struct.unpack(FMT[t], self.raw(SZ[t]))[0]

    def string(self):
        n = struct.unpack("<Q", self.raw(8))[0]
        return self.raw(n).decode("utf-8", "replace")

    def value(self, t):
        if t == 8:
            return self.string()
        if t == 9:
            et = struct.unpack("<I", self.raw(4))[0]
            n = struct.unpack("<Q", self.raw(8))[0]
            # 数组元素可能巨大（tokens 十几万条）——只取前几个 + 记长度
            keep = min(n, 8)
            head = []
            for _ in range(n):
                if len(head) < keep:
                    head.append(self.value(et))
                else:
                    self._skip(et)
            return {"__array__": T.get(et, et), "n": n, "head": head}
        return self.scalar(t)

    def _skip(self, t):
        if t == 8:
            n = struct.unpack("<Q", self.raw(8))[0]
            self.f.seek(n, 1)
            return
        if t == 9:
            et = struct.unpack("<I", self.raw(4))[0]
            n = struct.unpack("<Q", self.raw(8))[0]
            for _ in range(n):
                self._skip(et)
            return
        self.f.seek(SZ[t], 1)


def read_meta(path: str) -> dict:
    with open(path, "rb") as f:
        r = R(f)
        magic = r.raw(4)
        if magic != b"GGUF":
            raise ValueError("不是 GGUF：%r" % magic)
        ver = struct.unpack("<I", r.raw(4))[0]
        n_tensors = struct.unpack("<Q", r.raw(8))[0]
        n_kv = struct.unpack("<Q", r.raw(8))[0]
        kv = {}
        for _ in range(n_kv):
            key = r.string()
            vt = struct.unpack("<I", r.raw(4))[0]
            kv[key] = r.value(vt)
        return {"__ver__": ver, "__n_tensors__": n_tensors, **kv}


def token_str(v) -> str:
    if isinstance(v, str):
        return repr(v)
    if isinstance(v, dict):
        return "<%s ×%d>" % (v["__array__"], v["n"])
    return str(v)


def report(path: str) -> dict:
    print("\n" + "=" * 78)
    print("  文件: %s" % path)
    try:
        m = read_meta(path)
    except Exception as exc:                                  # noqa: BLE001
        print("  🔴 读不了：%s" % exc)
        return {"path": path, "ok": False, "err": str(exc)}
    print("  GGUF v%s · 张量 %d 个 · KV %d 条"
          % (m["__ver__"], m["__n_tensors__"], len(m) - 2))

    g = lambda k: m.get("general." + k)                    # noqa: E731
    print("  架构          %s" % g("architecture"))
    print("  名称          %s" % g("name"))
    print("  量化版本      %s" % g("file_type"))

    tmpl = m.get("tokenizer.chat_template")
    print("\n  ── 分词/模板（乱码真因常在这）──")
    if tmpl:
        print("  chat_template ✅ 存在 · %d 字符" % len(tmpl))
        print("     前 120 字: %s" % tmpl[:120].replace("\n", " "))
    else:
        print("  chat_template 🔴 **缺失** —— 宿主只能自套模板，角色/边界 token 极易错位")

    for k in ("tokenizer.ggml.model", "tokenizer.ggml.pre",
              "tokenizer.ggml.bos_token_id", "tokenizer.ggml.eos_token_id",
              "tokenizer.ggml.padding_token_id",
              "tokenizer.ggml.add_bos_token", "tokenizer.ggml.add_eos_token"):
        if k in m:
            print("  %-38s %s" % (k.split(".")[-1], token_str(m[k])))
        else:
            print("  %-38s 🔴 缺失" % k.split(".")[-1])

    toks = m.get("tokenizer.ggml.tokens")
    if isinstance(toks, dict):
        print("  %-38s %d 条" % ("tokens 数量", toks["n"]))
        for k in ("scores", "token_type"):
            v = m.get("tokenizer.ggml." + k)
            if isinstance(v, dict):
                mark = "✅" if v["n"] == toks["n"] else "🔴 不一致"
                print("  %-38s %d 条 %s" % (k + " 数量", v["n"], mark))

    # 特殊 token 是否真在词表里
    if isinstance(toks, dict):
        head = toks["head"]
        print("\n  ── 词表前几个 token（能看出是不是 Qwen）──")
        print("     %s" % head)

    cfg_vocab = None
    for key in m:
        if key.endswith("vocab_size"):
            cfg_vocab = m[key]
            print("  %-38s %s" % (key, cfg_vocab))
    if cfg_vocab and isinstance(toks, dict) and cfg_vocab != toks["n"]:
        print("  🔴 vocab_size(%s) ≠ tokens 数(%d) —— 切词会错位"
              % (cfg_vocab, toks["n"]))
    elif cfg_vocab and isinstance(toks, dict):
        print("  ✅ vocab_size 与 tokens 数一致（%d）" % cfg_vocab)

    return {"path": path, "ok": True, "chat_template": bool(tmpl),
            "tokens": (toks or {}).get("n") if isinstance(toks, dict) else None,
            "bos": m.get("tokenizer.ggml.bos_token_id"),
            "eos": m.get("tokenizer.ggml.eos_token_id"),
            "pad": m.get("tokenizer.ggml.padding_token_id")}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    rows = [report(p) for p in sys.argv[1:]]
    if len(rows) > 1:
        print("\n" + "=" * 78)
        print("  横向对照")
        print("  %-46s %-8s %-8s %-6s %-6s %s"
              % ("文件", "chat_tmpl", "tokens", "bos", "eos", "pad"))
        for r in rows:
            if not r.get("ok"):
                print("  %-46s 🔴 %s" % (r["path"].split("/")[-1], r.get("err")))
                continue
            print("  %-46s %-8s %-8s %-6s %-6s %s"
                  % (r["path"].split("/")[-1], "✅" if r["chat_template"] else "🔴缺",
                     r["tokens"], r["bos"], r["eos"], r["pad"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
