"""把权重分片按序合并成单个 GGUF，并校验魔数与大小（换机器重装权重的第一步）。

用法：python tools/merge-weights.py <weights_dir> <out.gguf> <part1> <part2> ...
按参数顺序合并（分片名里带 .part1/.part2 ...，按字典序排会出错，所以显式给顺序）。
"""
import os
import sys

def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    d, out, parts = sys.argv[1], sys.argv[2], sys.argv[3:]
    total = 0
    with open(out, "wb") as w:
        for name in parts:
            p = os.path.join(d, name)
            size = os.path.getsize(p)
            with open(p, "rb") as r:
                while True:
                    buf = r.read(8 * 1024 * 1024)
                    if not buf:
                        break
                    w.write(buf)
            total += size
            print("  + %-36s %6.2f GB" % (name, size / 1e9), flush=True)
    head = open(out, "rb").read(4)
    print("merged:", out)
    print("  bytes: %d (%.2f GB)" % (total, total / 1e9))
    print("  magic: %r %s" % (head, "OK" if head == b"GGUF" else "!! 不是 GGUF"))
    return 0 if head == b"GGUF" else 1


if __name__ == "__main__":
    raise SystemExit(main())
