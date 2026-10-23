# -*- coding: utf-8 -*-
"""亿万触手寻址（逻辑）：地址是算出来的，不占盘；钥匙是派生出来的，盘上只有一把主密钥。

主人令（2026-10-12）：「对比一下把 V8 缺少的能力在自己项目树上生出，别去搬过来」。
本件是 V9 有、V8 没有的那一件，按 V8 自己的口径重做（方法论取自 V9
core/tentacle_scale.py 的公开设计，没有搬它的代码、没有搬它的文件）。

诚实分层（这是能不能真做的分水岭，**不许把「逻辑」说成「实体」**）：
  · 10^8 个真进程/真文件：不可能（盘、内存、句柄都不干）—— 谁承诺这个就是吹；
  · 10^8 个逻辑触手：可行 —— 地址是算出来的（不占盘）；
  · 实体化只在真用到时发生，闲置可回收 —— 于是「亿万」只是地址空间的宽度；
  · 钥匙不逐根存：主密钥 HMAC 派生（同一根永远同一把、彼此不同、可复算）。

本件**只做只读那一半**（寻址 + 派生 + 自证），实体化/落盘那一半**留给主人开作用域**：
  新增的能力位若不在 security/policy.py 挂作用域，就是「零作用域」（本仓登记在册的坑：
  零作用域 不等于 只读），而 policy.py 只有主人能改。所以本模块**不建目录、不写盘、
  不生成主密钥** —— 主密钥不在就如实报「未配」，不偷偷造一把。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import hashlib
import hmac
import re
from pathlib import Path

# 逻辑地址空间宽度（1 亿）—— 这是"亿万触手"里的"亿"，是宽度不是盘的负担
ADDR_SPACE = 10 ** 8

# 分片数：10^8 根 / 1024 片 ≈ 每片 10 万条（真落库时才用得上）
SHARD_N = 1024

# 主密钥落点：数据一律进 store/（LAYOUT.md 的家规）
_PKG = Path(__file__).resolve().parents[1]
MASTER = _PKG / "store" / "tentacle_scale" / "master.secret"

_ADDR_RE = re.compile(r"^t?\d{1,8}$", re.I)


def addr(i) -> str:
    """逻辑触手号：t00000001 … t99999999（算出来的，不占盘）。"""
    n = int(i)
    if not (1 <= n <= ADDR_SPACE):
        raise ValueError("超出地址空间 1..%d：%s" % (ADDR_SPACE, i))
    return "t%08d" % n


def parse(a):
    """把 t00000001 / 1 / "00000001" 解回整数序号（不合法就抛，**不猜**）。"""
    s = str(a).strip()
    if not _ADDR_RE.match(s):
        raise ValueError("不是合法触手号：%r（形如 t00000001）" % a)
    n = int(s.lstrip("tT"))
    if not (1 <= n <= ADDR_SPACE):
        raise ValueError("超出地址空间 1..%d：%s" % (ADDR_SPACE, a))
    return n


def shard_of(i) -> int:
    """第 i 根落在哪个分片（0..SHARD_N-1）。"""
    return parse(i) % SHARD_N if not isinstance(i, int) else int(i) % SHARD_N


def shard_path(i) -> str:
    """该分片的库路径（**只报路径，不建、不写**）。"""
    return str(MASTER.parent / ("shard_%04d.sqlite3" % shard_of(i)))


def master_state() -> dict:
    """主密钥状态：**只报「已配/未配」，永不出内容、不出前 4 位以外的任何字节**。"""
    p = MASTER
    if not p.is_file():
        return {
            "状态": "未配",
            "路径": str(p),
            "怎么配": ("本件**故意不代建**：主密钥属凭据类落盘，要有 filesystem_write 作用域才动。"
                       "请在 security/policy.py 给 tentacle_scale 挂作用域后再由主人下令生成。"),
        }
    try:
        raw = p.read_bytes()
    except Exception as exc:                      # noqa: BLE001
        return {"状态": "读不到", "路径": str(p), "原因": str(exc)}
    return {
        "状态": "已配",
        "路径": str(p),
        "字节": len(raw),
        "指纹": hashlib.sha256(raw).hexdigest()[:16],
        "口径": "只报指纹，不回显内容（凭据纪律）",
    }


def key(a) -> dict:
    """派生第 a 根的钥匙指纹：**同一根永远同一把、彼此不同、可复算**。

    不出完整钥匙（凭据纪律：只回指纹）。主密钥不在就如实报「未配」，不偷偷造一把。
    """
    try:
        n = parse(a)
    except ValueError as exc:
        return {"ok": False, "状态": "地址不合法", "原因": str(exc)}
    st = master_state()
    if st["状态"] != "已配":
        return {
            "ok": False,
            "状态": "主密钥未配",
            "触手": addr(n),
            "主密钥": st,
            "为什么": "派生要有主密钥；本件只读，不代建（见 master_state.怎么配）",
        }
    raw = MASTER.read_bytes()
    fp = hmac.new(raw, addr(n).encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "ok": True,
        "状态": "已派生",
        "触手": addr(n),
        "分片": shard_of(n),
        "钥匙指纹": fp[:16],
        "口径": "只回指纹，不回完整钥匙；同一根每次复算都是这一枚",
    }


def space() -> dict:
    """地址空间现状（**只读自证**：宽多少、怎么分片、盘上现在有没有东西）。"""
    root = MASTER.parent
    shards = 0
    if root.is_dir():
        try:
            shards = len(list(root.glob("shard_*.sqlite3")))
        except Exception:                          # noqa: BLE001
            shards = 0
    return {
        "ok": True,
        "地址空间": ADDR_SPACE,
        "地址式样": "t00000001",
        "分片数": SHARD_N,
        "每片约": ADDR_SPACE // SHARD_N,
        "落点": str(root),
        "盘上分片": shards,
        "主密钥": master_state(),
        "诚实分层": {
            "逻辑触手": "10^8（地址算出来的，不占盘）",
            "实体触手": "只在真用到时实体化（**本件不做，等主人给作用域**）",
            "真进程/真文件 10^8": "不可能，谁承诺这个就是吹",
        },
    }


def run(op: str, payload: dict | None = None) -> dict:
    """唯一入口：op=space/addr/parse/shard/key/master。**认不出的 op 一律拒绝（fail-closed）**。"""
    p = payload or {}
    op = str(op or "space").strip().lower()
    try:
        if op in ("space", "status", "info"):
            return space()
        if op == "master":
            return {"ok": master_state()["状态"] == "已配", "主密钥": master_state()}
        if op in ("addr", "number"):
            return {"ok": True, "触手": addr(p.get("i", p.get("n", 1)))}
        if op == "parse":
            n = parse(p.get("a", p.get("addr", p.get("t", ""))))
            return {"ok": True, "序号": n, "触手": addr(n), "分片": shard_of(n)}
        if op == "shard":
            i = p.get("i", p.get("n", p.get("a", p.get("addr", 1))))
            return {"ok": True, "触手": addr(parse(i) if isinstance(i, str) else i),
                    "分片": shard_of(i if isinstance(i, int) else parse(i)),
                    "库路径": shard_path(i if isinstance(i, int) else parse(i))}
        if op in ("key", "keys"):
            return key(p.get("a", p.get("addr", p.get("i", p.get("n", 1)))))
    except ValueError as exc:
        return {"ok": False, "status": "error", "error_class": "user_error", "原因": str(exc)}
    return {
        "ok": False,
        "status": "error",
        "error_class": "user_error",
        "message": "未知 op:%s（space/addr/parse/shard/key/master）" % op,
        "fail_closed": True,
    }
