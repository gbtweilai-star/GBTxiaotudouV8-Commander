#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# gbt-capability: bug-bounty-usdt-evm · validate_evm
"""EVM 地址校验器 —— **纯标准库，零依赖**。

为什么不用 `eth_utils`：本仓声明口径是 3.14，而 `py -3.14` 上
`eth_utils` / `web3` / `Crypto` / `eth_hash` **一个都没装**（现读 `importlib.util.find_spec` 全 False；
只有默认 `python` 3.12 装了 eth_utils / Crypto / eth_hash）。所以校验器自带一份
**纯 python keccak-256**（EIP-55 只用到 keccak-256，不是 sha3-256），跑哪个解释器都一样。

判三件事（分开报，不混成一句「有效」）：
  1. `shape_ok`      —— `^0x[0-9a-fA-F]{40}$`（最基础的形状）
  2. `checksum`      —— `valid` / `all_lower` / `all_upper` / `bad`
                        （EIP-55 原文：全小写、全大写是**合法**写法，只是**没带**校验和；
                         混大小写才是「带了校验和」，那时**必须**能对上，对不上就是坏地址）
  3. `checksum_addr` —— 该地址的规范 EIP-55 写法（拿去用这个）

命令：
  py -3.14 -X utf8 skills/bug-bounty-usdt-evm/scripts/validate_evm.py 0x12113c19...2957
  py -3.14 -X utf8 skills/bug-bounty-usdt-evm/scripts/validate_evm.py --selftest

退出码（写死，别改）：
  0 = 形状合法（不论有没有带校验和）
  1 = 形状非法，或混大小写但校验和对不上
  2 = selftest 失败（判据自己坏了，比对象坏了更严重）
"""
from __future__ import annotations

import argparse
import json
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_EVM_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_MASK64 = (1 << 64) - 1

# --- 纯 python keccak-256（Keccak-f[1600] · rate=136 · padding 0x01，非 SHA3 的 0x06）-----
_RC = (
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
)
_PILN = (10, 7, 11, 17, 18, 3, 5, 16, 8, 21, 24, 4, 15, 23, 19, 13, 12, 2, 20, 14, 22, 9, 6, 1)
_ROTL = (1, 3, 6, 10, 15, 21, 28, 36, 45, 55, 2, 14, 27, 41, 56, 8, 25, 43, 62, 18, 39, 61, 20, 44)
_RATE = 136  # keccak-256: (1600 - 2*256) // 8 = 136


def _rotl64(x: int, n: int) -> int:
    n &= 63
    if n == 0:
        return x & _MASK64
    return ((x << n) | (x >> (64 - n))) & _MASK64


def _keccak_f1600(lanes: list) -> list:
    for rnd in range(24):
        bc = [lanes[i] ^ lanes[i + 5] ^ lanes[i + 10] ^ lanes[i + 15] ^ lanes[i + 20] for i in range(5)]
        for i in range(5):
            t = bc[(i + 4) % 5] ^ _rotl64(bc[(i + 1) % 5], 1)
            for j in range(0, 25, 5):
                lanes[j + i] ^= t
        t = lanes[1]
        for i in range(24):
            j = _PILN[i]
            bc[0] = lanes[j]
            lanes[j] = _rotl64(t, _ROTL[i])
            t = bc[0]
        for j in range(0, 25, 5):
            for i in range(5):
                bc[i] = lanes[j + i]
            for i in range(5):
                lanes[j + i] ^= (~bc[(i + 1) % 5] & _MASK64) & bc[(i + 2) % 5]
        lanes[0] ^= _RC[rnd]
    return lanes


def keccak256(data: bytes) -> bytes:
    """Keccak-256（不是 SHA3-256：padding 0x01，不是 0x06）。"""
    lanes = [0] * 25
    off = 0
    n = len(data)
    while n - off >= _RATE:
        block = data[off:off + _RATE]
        for i in range(_RATE // 8):
            lanes[i] ^= int.from_bytes(block[i * 8:(i + 1) * 8], "little")
        _keccak_f1600(lanes)
        off += _RATE
    tail = bytearray(data[off:])
    tail.append(0x01)
    while len(tail) < _RATE:
        tail.append(0x00)
    tail[-1] |= 0x80
    for i in range(_RATE // 8):
        lanes[i] ^= int.from_bytes(tail[i * 8:(i + 1) * 8], "little")
    _keccak_f1600(lanes)
    return b"".join(l.to_bytes(8, "little") for l in lanes)[:32]


# ---------------------------------------------------------------------- EIP-55
def to_checksum_address(address: str) -> str:
    """返回规范 EIP-55 写法。输入必须是形状合法的 0x + 40 hex。"""
    body = address[2:].lower()
    digest = keccak256(body.encode("ascii")).hex()
    out = []
    for i, ch in enumerate(body):
        out.append(ch.upper() if ch.isalpha() and int(digest[i], 16) >= 8 else ch)
    return "0x" + "".join(out)


def classify_checksum(address: str) -> str:
    """valid / all_lower / all_upper / bad。"""
    body = address[2:]
    has_lower = any(c.islower() for c in body)
    has_upper = any(c.isupper() for c in body)
    if not has_upper:
        return "all_lower"
    if not has_lower:
        return "all_upper"
    return "valid" if address == to_checksum_address(address) else "bad"


def inspect(address: str) -> dict:
    shape_ok = bool(_EVM_RE.fullmatch(address or ""))
    if not shape_ok:
        return {
            "input": address,
            "shape_ok": False,
            "checksum": "n/a",
            "checksum_addr": None,
            "verdict": "invalid_shape",
            "note": "形状不合法：必须是 0x + 恰好 40 个 hex 字符",
        }
    status = classify_checksum(address)
    verdict = {
        "valid": "ok_checksummed",
        "all_lower": "ok_no_checksum",
        "all_upper": "ok_no_checksum",
        "bad": "invalid_checksum",
    }[status]
    note = {
        "valid": "带 EIP-55 校验和且对得上",
        "all_lower": "全小写：合法，但没带校验和（转写时用 checksum_addr）",
        "all_upper": "全大写：合法，但没带校验和（转写时用 checksum_addr）",
        "bad": "混大小写 ⇒ 声明了校验和，但对不上 ⇒ 地址被改过或抄错（**不要用它**）",
    }[status]
    return {
        "input": address,
        "shape_ok": True,
        "checksum": status,
        "checksum_addr": to_checksum_address(address),
        "verdict": verdict,
        "note": note,
    }


# ---------------------------------------------------------------------- selftest
# EIP-55 官方 4 条测试向量（写死在 spec 里）
_EIP55_ALL_VALID = [
    "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed",
    "0xfB6916095ca1df60bB79Ce92cE3Ea74c37c5d359",
    "0xdbF03B407c01E7cD3CBea99509d93f8DDDC8C6FB",
    "0xD1220A0cf47c7B9Be7A2E6BA89F429762e7b9aDb",
]


def selftest() -> int:
    fails = []

    vectors = {
        b"": "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470",
        b"abc": "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45",
        b"testing": "5f16f4c7f149ac4f9510d9cf8cf384038ad348b3bcdc01915f95de12df9d1b02",
    }
    for msg, want in vectors.items():
        got = keccak256(msg).hex()
        if got != want:
            fails.append(f"keccak256({msg!r}) = {got}, 期望 {want}")

    for addr in _EIP55_ALL_VALID:
        st = classify_checksum(addr)
        if st != "valid":
            fails.append(f"{addr} 应判 valid，实判 {st}")

    # 负对照 1：把一条官方向量改一个小写字母大小写 ⇒ 必须报 bad
    tampered = "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAeD"
    if classify_checksum(tampered) != "bad":
        fails.append("篡改大小写没被判 bad（判据失效）")

    # 负对照 2：长度不对 ⇒ shape 必须不过
    if inspect("0x1211").get("shape_ok"):
        fails.append("短地址被判 shape_ok（判据失效）")

    # 负对照 3：非 hex ⇒ shape 必须不过
    if inspect("0x" + "z" * 40).get("shape_ok"):
        fails.append("非 hex 字符被判 shape_ok（判据失效）")

    # 正例：全小写合法但无校验和
    if classify_checksum("0x12113c1904342b7ad20b38271840c1b0e4962957") != "all_lower":
        fails.append("全小写地址没被判 all_lower（判据失效）")

    if fails:
        print(json.dumps({"selftest": "FAIL", "fails": fails}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps({"selftest": "PASS", "vectors": 3, "eip55": 4, "negatives": 4}, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="EVM 地址校验（纯标准库 · 零依赖 · EIP-55）")
    ap.add_argument("address", nargs="?", help="0x 开头的 40 位十六进制地址")
    ap.add_argument("--selftest", action="store_true", help="跑官方向量 + 负对照")
    ap.add_argument("--quiet", action="store_true", help="只输出 JSON（给机器读）")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.address:
        ap.print_help()
        return 1

    res = inspect(args.address.strip())
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res["verdict"] in ("ok_checksummed", "ok_no_checksum") else 1


if __name__ == "__main__":
    raise SystemExit(main())
