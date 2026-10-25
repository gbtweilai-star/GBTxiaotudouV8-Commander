"""GBT小土豆V8 · 统一数据后台：追加式 JSONL 审计日志 + 只读查询。

记录调用、配置变更、错误、被拒（危险能力）等事件，供审计复核。

V8 修复的两个暗伤：
1. query_log 改为反序流式读取（从文件尾往前拿 limit 条），不再全量读入内存；
2. 写入失败的内存缓冲提供 flush_memory_log() 回写路径，并在查询时自动尝试回写，
   不再静默丢失审计记录。
"""
import json
import os
import threading
import time
from pathlib import Path

from ._paths import STORE_DIR as _STORE_DIR  # 统一基址（支持 GBT_STORE_DIR 隔离）
# O53 甲案（风哥 2026-09-18 拍）：写入口前比对「绑定」与「当前 env」。
# 只读路径不挂这条检查；绑定后 env 漂移 = 拒绝写入，不自动改绑、不静默重绑。
from . import _paths as _paths_mod
_LOG = _STORE_DIR / "audit.jsonl"

# 内存缓冲区：当文件系统写入失败时的回退
_memory_log = []

# V8 极限打磨修复：并发追加审计曾出现行交错（10 路并发实测半截行）。
# 进程内所有写入/回写必须持同一把锁，保证 JSONL 每行完整。
_audit_lock = threading.Lock()


def _ensure():
    _paths_mod.verify_store_binding()   # O53 甲案：门在 mkdir 之前 —— 拒绝路径不产生任何文件
    _STORE_DIR.mkdir(parents=True, exist_ok=True)


_sanitize_meta_impl = None


def _sanitize_meta(meta):
    """审计账本写入前的统一脱敏（R120）。

    为什么放在写入侧：脱敏是账本的属性，不是每个调用者的义务。此前账本里凡是
    key 叫 prompt / content / messages / input 的行都是原样落盘，密钥类字段 likewise
    —— 靠调用方自觉迟早漏。
    规格实现见 security/data_policy.sanitize_for_audit：凭证掩码、对话类内容只留指纹
    （chars/items/sha256）、长文本截断；字段只改表示，不删除。
    脱敏器自身异常 -> 记一条不可用标记，绝不把原始 meta 落盘（宁可少记，不可泄漏）。
    """
    global _sanitize_meta_impl
    if _sanitize_meta_impl is None:
        from .security.data_policy import sanitize_for_audit
        _sanitize_meta_impl = sanitize_for_audit
    try:
        return _sanitize_meta_impl(meta or {})
    except Exception:  # noqa: BLE001
        return {"_audit_meta_unavailable": True}


# ── 审计落盘失败的**可见性**（2026-09-22 错报治理）────────────────────
_AUDIT_FAIL = {"count": 0, "reasons": {}, "last_at": None}


def _note_audit_failure(exc) -> None:
    """把「审计没落盘、转进了内存缓冲」这件事**说出来**。

    `audit()` 内部有内存缓冲兜底（不抛异常，业务不受影响），但这层兜底**原来是无声的**：
    账本看起来完整，实际有 N 条躺在内存里，调用方/看板/审计器都无从知道
    ⇒ 「账本说没发生，其实是没记上」= 最字面意义的错报。
    这里只做三件事：计数、记因、**同类只在首次出声**（避免刷屏把真故障淹掉）。
    """
    _AUDIT_FAIL["count"] += 1
    _AUDIT_FAIL["last_at"] = round(time.time(), 3)
    key = type(exc).__name__
    _AUDIT_FAIL["reasons"][key] = _AUDIT_FAIL["reasons"].get(key, 0) + 1
    if _AUDIT_FAIL["reasons"][key] == 1:
        try:
            import sys as _s
            print("⚠️ store.audit: 审计落盘失败（%s: %s）⇒ 已转内存缓冲（当前 %d 条未落盘）"
                  % (key, str(exc)[:120], len(_memory_log)), file=_s.stderr)
        except Exception:                                       # noqa: BLE001
            pass


def audit_failures() -> dict:
    """只读：审计落盘失败的计数与原因（给看板/审计器用）。

    `count > 0` ⇒ **账本可能缺行** —— 这是必须被看见的读数，不是内部细节。
    """
    return {"ok": True, "readonly": True, "count": _AUDIT_FAIL["count"],
            "reasons": dict(_AUDIT_FAIL["reasons"]),
            "last_at": _AUDIT_FAIL["last_at"],
            "pending_in_memory": len(_memory_log),
            "note": "count>0 ⇒ 有审计记录未落盘（在内存缓冲里），账本可能缺行"}


def audit(event, meta=None):
    """写入一条审计记录，返回该记录。

    🔴 口径（2026-09-22 第 34 轮精修）：**落盘意外永不抛；门拒绝必抛**。
    上一版写成"永不抛"，把两种完全不同的失败混成了一锅 —— 见下面的实测。

    🔴 为什么要有"落盘意外永不抛"这层：全仓有 ~20 处调用方写成
    `try: audit(...) except Exception: pass` —— 因为 `_audit_impl` 只在**文件写失败**时
    兜底（转内存缓冲），`_sanitize_meta` / `json.dumps` 等环节的异常**仍会抛出去**，
    于是调用方不得不各写一个静默兜底 ⇒ 「这次审计没记上」再次无声。
    ⇒ 把"落盘意外永不抛"钉在**这里**：转成**可见降级**（计数 + 出声 + 内存缓冲，
    见 `_note_audit_failure` / `audit_failures()`），并返回带 `_audit_degraded` 标记的记录。
    **在源头修一次，胜过在下游修 20 次**（必读清单第 31 条）。

    🔴 但**门拒绝不是落盘意外**（第 34 轮实测，`test_store_dir_binding_snapshot_blocks_env_drift`
    臂 B 抓出来的）：`verify_store_binding()` 抛的 RuntimeError 是"**拒绝写入**"的裁决 ——
    O53 甲案要求 fail-fast。上一版把它一起兜住了，实测后果：`store.audit()` 明明被门拒，
    脚本照样打印 ARM_B_WROTE、**进程退出码 0** ⇒ 调用方以为写成功了。
    这正是本仓最贵的那条教训（「有兜底的沉默比崩溃更坏」）在审计口上的翻版。
    ⇒ 门在 try **之外**先过：拒绝就抛；只有真正的落盘意外才转可见降级。
    """
    _paths_mod.verify_store_binding()   # 门：拒绝写入 ⇒ 必须抛（O53 甲案 fail-fast）
    try:
        return _audit_impl(event, meta)
    except Exception as _e:                                     # noqa: BLE001
        _note_audit_failure(_e)
        rec = {"ts": round(time.time(), 3),
               "iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "event": event,
               "meta": {"_audit_degraded": "%s: %s" % (type(_e).__name__, str(_e)[:160])}}
        try:
            _memory_log.append(rec)
        except Exception:                                       # noqa: BLE001
            pass
        return rec


def _audit_impl(event, meta=None):
    """写入一条审计记录，返回该记录。

    优先写入文件，失败时存入内存缓冲区（后续 flush_memory_log / query 时回写）。
    """
    _ensure()
    with _audit_lock:
        # ⛔ 2026-09-17 修复 ts 倒挂根因：时间戳必须在**持锁之后**取。
        #    此前 rec 在锁外构造，于是"先排队的不一定先取时间"——生产账本全量逐行复算：
        #    非空 287,890 行里 402 处 ts 倒挂（最差 -98 ms；抽样看只有 ≤6 ms，抽样会骗人），
        #    隔离复现 422 处（最差 -0.174 s）。
        #    边界说明：本锁是 threading.Lock，只保证**进程内**顺序；
        #    跨进程仍依赖 O_APPEND 原子追加，本改动不作更强承诺。
        rec = {
            "ts": round(time.time(), 3),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "event": event,
            "meta": _sanitize_meta(meta),
        }
        line = json.dumps(rec, ensure_ascii=False) + "\n"
        try:
            with open(_LOG, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())   # 强制落盘：降低进程崩溃丢失窗口
        except (PermissionError, OSError) as _e:
            # gatekeeper 或其他原因导致写入失败时，存入内存缓冲区
            _memory_log.append(rec)
            # 🔴 2026-09-22 修（错报治理）：转缓冲这件事**原来是无声的** ——
            # 账本"看起来完整"，而 N 条记录正躺在内存里；调用方与审计器都无从知道。
            # 这是最字面意义的错报：「账本说没发生，其实是没记上」。
            # ⇒ 计数 + 首次/每次换因都**显式出声**，并开只读口 `audit_failures()`。
            #    （不抛异常：审计失败绝不许把业务带崩 —— 只把沉默打破。）
            _note_audit_failure(_e)
    return rec


def flush_memory_log() -> int:
    """把内存缓冲中的审计记录回写落盘，返回成功回写条数。"""
    if not _memory_log:
        return 0
    written = 0
    with _audit_lock:
        try:
            _ensure()
            with open(_LOG, "a", encoding="utf-8") as f:
                while _memory_log:
                    rec = _memory_log.pop(0)
                    try:
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        written += 1
                    except (PermissionError, OSError):
                        _memory_log.insert(0, rec)
                        break
                f.flush()
                os.fsync(f.fileno())   # 批量回写后统一落盘
        except (PermissionError, OSError, RuntimeError) as _e:
            # 🔴 2026-09-22 修（错报治理）：回写失败原来静默 `pass`，调用方看不出
            # "这批缓冲**没回写成功**"。记录**没丢**（仍在 `_memory_log` 里），
            # 但"没回写"这件事必须能被读到 ⇒ 与落盘失败同一口径记账。
            # 🔴 第 34 轮补 `RuntimeError`：绑定门拒绝也是"这批没回写"的一种。
            #    之前它从 `except (PermissionError, OSError)` 旁边漏出去，在 atexit 里
            #    变成一条 "Exception ignored in atexit callback" 的裸 traceback ——
            #    进程照样退 0、没人计数、看板读不出"有几条没落盘"。
            #    捕获后走同一记账口：**出声 + 计数**，`audit_failures()` 里
            #    `pending_in_memory > 0` 就是"账本可能缺行"的诚实读数。
            _note_audit_failure(_e)
    return written


def _iter_log_reversed():
    """从文件尾往前按行产出（反序流式，不全量驻留内存）。"""
    if not _LOG.exists():
        return
    with open(_LOG, "rb") as f:
        f.seek(0, os.SEEK_END)
        pos = f.tell()
        buf = b""
        while pos > 0:
            step = min(8192, pos)
            pos -= step
            f.seek(pos)
            chunk = f.read(step)
            buf = chunk + buf
            lines = buf.split(b"\n")
            buf = lines.pop(0)  # 首段是未完整行，留到下一轮
            for line in reversed(lines):
                yield line
        if buf.strip():
            yield buf


def query_log(event=None, limit=200):
    """只读返回审计日志（可过滤 event），近期在前 -> 按时间升序返回最近 limit 条。

    兼容旧语义：返回列表按 ts 升序排列（最旧在前、最新在后），条数为最近 limit 条。
    """
    flush_memory_log()
    picked = []
    scanned = 0
    for raw in _iter_log_reversed():
        try:
            rec = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:
            continue
        if event is not None and rec.get("event") != event:
            continue
        picked.append(rec)
        scanned += 1
        if scanned >= limit:
            break
    picked.reverse()
    if _memory_log:
        picked.extend(_memory_log[-limit:])
        picked.sort(key=lambda x: x.get("ts", 0))
    return picked[-limit:]


def log_count():
    """审计日志总条数（流式统计，不全量驻留内存）。"""
    flush_memory_log()
    n = 0
    if _LOG.exists():
        with open(_LOG, "rb") as f:
            for line in f:
                if line.strip():
                    n += 1
    return n + len(_memory_log)


import atexit as _atexit

# 进程退出时兑底：把内存缓冲里没落盘的审计尽量回写，减少崩溃/退出丢失
_atexit.register(flush_memory_log)
