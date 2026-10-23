# -*- coding: utf-8 -*-
r"""tentacle-vault -- 触手密钥库（一根触手一个 DPAPI 封印的账户/密钥数据库）

主人令（2026-10-17）：「你要给他们安装一个密钥账户等数据库存放这些」+
  「每根触手都可以隔离使用万能插，互不干扰」⇒ 每根触手**自己的**密钥库：
  邮箱地址/开源账户/接码记录/云插件槽位/API 钥匙，全存这，**掩码显示、明文只供机器取用**。

落点（**仓外**，与 freebuff HOME / 浏览器 profile 同一纪律）：
  %LOCALAPPDATA%\gbt-tentacle-vault\<tid>\vault.db    每根一个，互不相同
  （凭据性质 ⇒ 永不入仓、永不进 git；.gitignore 也不依赖——它就在仓外）

安全口径（三条红线，逐条可验）：
  1. **DPAPI 用户级封印**：secret 落盘前经 Windows CryptProtectData 密文化；
     同用户同机器才解得开。entropy 按触手派生（blake2b(tid)）⇒ 另一根的密文拿来也解不开。
  2. **永不落明文**：库文件字节里不许出现 secret 原文（selftest 负控扫文件字节）。
  3. **掩码显示**：list/show 只给 掩码+指纹（blake2b 前 8 位，不可反推）；
     `fetch` 才出明文 —— **只供管道给自动化**，禁止贴屏/进日志/进对话（凭据不离屏律）。
诚实边界：DPAPI 是**用户级**加密 —— 防"别的用户/别的机器/误连"，**不防同用户同机器的
  恶意程序主动偷**（那要 OS 级身份分离，超出本件；要再上一层就上 DPAPI + 硬件 key）。

专业配置（与 sweep-db.py / db-fleet.sql §0 同口径）：
  page_size=8192 / journal_mode=WAL / synchronous=NORMAL / cache 64MB /
  foreign_keys=ON / busy_timeout=5s / mmap 256MB

用法：
  py -3.14 -X utf8 tools/codex-scripts/tentacle-vault.py init t1
  py -3.14 -X utf8 tools/codex-scripts/tentacle-vault.py add t1 --kind email \
      --platform github.com --identity t1-bot@x --secret - --note '开源账户用'   # 口令 stdin 进
  py -3.14 -X utf8 tools/codex-scripts/tentacle-vault.py add t1 --kind freebuff \
      --platform freebuff --identity t1-freebuff-reserved --generate --note '触手自设预留'
  py -3.14 -X utf8 tools/codex-scripts/tentacle-vault.py list t1
  py -3.14 -X utf8 tools/codex-scripts/tentacle-vault.py show t1 <account_id>
  py -3.14 -X utf8 tools/codex-scripts/tentacle-vault.py fetch t1 <account_id> --field password
  py -3.14 -X utf8 tools/codex-scripts/tentacle-vault.py retire t1 <account_id>
  py -3.14 -X utf8 tools/codex-scripts/tentacle-vault.py check
  py -3.14 -X utf8 tools/codex-scripts/tentacle-vault.py selftest

口令两条入口（红线 1 的延伸）：
  · `--secret -`：从 stdin 读（唯一推荐——不进 argv 就不进 shell 历史/进程表）；
  · `--generate`：**触手自己设口令**——进程内生成强随机（secrets.token_urlsafe），
    直接封印入库，全程不露面（连生成者都只看到掩码）；取出仍只经 fetch 供管道。
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import pathlib
import sqlite3
import sys
import time
import uuid
import secrets as _secrets_module          # 触手自设口令的随机源（别名防与局部 secret 混淆）

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

VAULT_BASE = pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "gbt-tentacle-vault"
TID_RE = __import__("re").compile(r"^[A-Za-z0-9_-]{1,16}$")

ACCOUNT_KINDS = ("email", "oss", "cloud_plugin", "freebuff", "phone_provider", "other")
SECRET_KINDS = ("password", "api_key", "token", "recovery", "other")

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
  account_id TEXT PRIMARY KEY,
  tid TEXT NOT NULL,
  kind TEXT NOT NULL,
  platform TEXT NOT NULL,
  identity TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  note TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_accounts_tid ON accounts(tid, kind);
CREATE TABLE IF NOT EXISTS secrets (
  secret_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES accounts(account_id),
  kind TEXT NOT NULL,
  cipher BLOB NOT NULL,
  fp TEXT NOT NULL,
  masked TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
"""


# ---------------------------------------------------------------- DPAPI（Windows 用户级封印）

class _DataBlob(ctypes.Structure):
    # pbData 必须用 c_void_p：若用 c_char_p，读取该字段时 ctypes 会解引用成 bytes
    # （遇 NUL 截断）——string_at 拿到副本地址、LocalFree 收到野指针直接硬崩进程
    # （自检 exit 127 零输出的根因，已实测复现）。
    _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.c_void_p)]


def _blob(b: bytes):
    buf = ctypes.create_string_buffer(b, max(1, len(b)))
    return _DataBlob(len(b), ctypes.cast(buf, ctypes.c_void_p)), buf


def _entropy(tid: str) -> bytes:
    """按触手派生的附加熵 —— 另一根的密文拿到也解不开（同用户下多一层）。"""
    return hashlib.blake2b(("gbt-tentacle-vault|" + tid).encode("utf-8"),
                           digest_size=16).digest()


def seal(plain: bytes, tid: str) -> bytes:
    if os.name != "nt":
        raise RuntimeError("当前系统不支持 Windows DPAPI")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt32.CryptProtectData.argtypes = [ctypes.POINTER(_DataBlob), ctypes.c_wchar_p,
                                         ctypes.POINTER(_DataBlob), ctypes.c_void_p,
                                         ctypes.c_void_p, ctypes.c_ulong,
                                         ctypes.POINTER(_DataBlob)]
    crypt32.CryptProtectData.restype = ctypes.c_int
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    in_blob, in_buf = _blob(plain)
    ent_blob, ent_buf = _blob(_entropy(tid))
    out = _DataBlob()
    ok = crypt32.CryptProtectData(ctypes.byref(in_blob),
                                  "GBT小土豆V8 tentacle %s vault" % tid,
                                  ctypes.byref(ent_blob), None, None, 0x1,
                                  ctypes.byref(out))
    if not ok:
        raise RuntimeError("DPAPI 封印失败（winerr=%d）" % ctypes.get_last_error())
    data = ctypes.string_at(out.pbData, out.cbData)
    kernel32.LocalFree(out.pbData)
    del in_buf, ent_buf
    return data


def unseal(cipher: bytes, tid: str) -> bytes:
    if os.name != "nt":
        raise RuntimeError("当前系统不支持 Windows DPAPI")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt32.CryptUnprotectData.argtypes = [ctypes.POINTER(_DataBlob), ctypes.POINTER(ctypes.c_wchar_p),
                                           ctypes.POINTER(_DataBlob), ctypes.c_void_p,
                                           ctypes.c_void_p, ctypes.c_ulong,
                                           ctypes.POINTER(_DataBlob)]
    crypt32.CryptUnprotectData.restype = ctypes.c_int
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    in_blob, in_buf = _blob(cipher)
    ent_blob, ent_buf = _blob(_entropy(tid))
    out = _DataBlob()
    ok = crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, ctypes.byref(ent_blob),
                                    None, None, 0x1, ctypes.byref(out))
    if not ok:
        raise RuntimeError("DPAPI 解封失败（winerr=%d）" % ctypes.get_last_error())
    data = ctypes.string_at(out.pbData, out.cbData)
    kernel32.LocalFree(out.pbData)
    del in_buf, ent_buf
    return data


def fingerprint(plain: str) -> str:
    return hashlib.blake2b(plain.encode("utf-8"), digest_size=4).hexdigest()


def mask(plain: str) -> str:
    if not plain:
        return ""
    head = plain[:4]
    tail = plain[-4:] if len(plain) > 8 else ""
    return "%s…%s|#%s" % (head, tail, fingerprint(plain))


# ---------------------------------------------------------------- 库操作

def vault_path(tid: str) -> pathlib.Path:
    _guard_tid(tid)
    return VAULT_BASE / tid / "vault.db"


def _guard_tid(tid: str) -> None:
    if not TID_RE.match(str(tid or "")):
        raise ValueError("tid 只许 [A-Za-z0-9_-]{1,16}（拒路径穿越）：%r" % tid)


def connect(tid: str) -> sqlite3.Connection:
    p = vault_path(tid)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA mmap_size=268435456")
    conn.executescript(SCHEMA)
    return conn


def init_vault(tid: str) -> dict:
    conn = connect(tid)
    try:
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        conn.execute("INSERT OR IGNORE INTO meta(k, v) VALUES('schema_version', '1')")
        conn.execute("INSERT OR IGNORE INTO meta(k, v) VALUES('tid', ?)", (tid,))
        conn.execute("INSERT OR IGNORE INTO meta(k, v) VALUES('created_at', ?)", (now,))
        conn.commit()
        n_acc = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        return {"ok": True, "tid": tid, "vault": str(vault_path(tid)),
                "accounts": n_acc, "at": now}
    finally:
        conn.close()


def add_account(tid: str, kind: str, platform: str, identity: str,
                secret: str = "", secret_kind: str = "password", note: str = "",
                generate: int = 0) -> dict:
    if kind not in ACCOUNT_KINDS:
        raise ValueError("kind 必须是 %s" % "/".join(ACCOUNT_KINDS))
    if not platform or not identity:
        raise ValueError("platform 与 identity 不许空")
    if secret and generate:
        raise ValueError("--secret 与 --generate 二选一（不许既给口令又让系统生成）")
    if generate:
        if generate < 16:
            raise ValueError("generate 至少 16 字节随机（强口令底线）")
        secret = _secrets_module.token_urlsafe(generate)   # 触手自己设：生成即封印，不露面
    conn = connect(tid)
    try:
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        aid = "acct_" + uuid.uuid4().hex[:16]
        conn.execute(
            "INSERT INTO accounts(account_id, tid, kind, platform, identity, status, note, created_at, updated_at)"
            " VALUES(?,?,?,?,?, 'active', ?,?,?)",
            (aid, tid, kind, platform, identity, note, now, now))
        out = {"ok": True, "account_id": aid, "tid": tid, "kind": kind,
               "platform": platform, "identity": identity}
        if secret:
            if secret_kind not in SECRET_KINDS:
                raise ValueError("secret_kind 必须是 %s" % "/".join(SECRET_KINDS))
            sid = "sec_" + uuid.uuid4().hex[:16]
            conn.execute(
                "INSERT INTO secrets(secret_id, account_id, kind, cipher, fp, masked, created_at)"
                " VALUES(?,?,?,?,?,?,?)",
                (sid, aid, secret_kind, seal(secret.encode("utf-8"), tid),
                 fingerprint(secret), mask(secret), now))
            out["secret_id"] = sid
            out["masked"] = mask(secret)
        conn.commit()
        return out
    finally:
        conn.close()


def list_accounts(tid: str, kind: str = "") -> dict:
    conn = connect(tid)
    try:
        sql = ("SELECT a.account_id, a.kind, a.platform, a.identity, a.status, a.note,"
               " (SELECT COUNT(*) FROM secrets s WHERE s.account_id=a.account_id) AS nsec"
               " FROM accounts a WHERE a.tid=?")
        args: list = [tid]
        if kind:
            sql += " AND a.kind=?"
            args.append(kind)
        sql += " ORDER BY a.created_at"
        rows = []
        for r in conn.execute(sql, args):
            rows.append({"account_id": r[0], "kind": r[1], "platform": r[2],
                         "identity": r[3], "status": r[4], "note": r[5], "secrets": r[6]})
        return {"ok": True, "tid": tid, "accounts": rows}
    finally:
        conn.close()


def show_account(tid: str, account_id: str) -> dict:
    conn = connect(tid)
    try:
        r = conn.execute(
            "SELECT account_id, kind, platform, identity, status, note, created_at, updated_at"
            " FROM accounts WHERE account_id=? AND tid=?", (account_id, tid)).fetchone()
        if not r:
            return {"ok": False, "error": "账户不存在或不属于本触手：%s" % account_id}
        secs = [{"secret_id": s[0], "kind": s[1], "masked": s[2], "fp": s[3], "created_at": s[4]}
                for s in conn.execute(
                    "SELECT secret_id, kind, masked, fp, created_at FROM secrets"
                    " WHERE account_id=? ORDER BY created_at", (account_id,))]
        return {"ok": True, "account": {"account_id": r[0], "kind": r[1], "platform": r[2],
                                        "identity": r[3], "status": r[4], "note": r[5],
                                        "created_at": r[6], "updated_at": r[7]}, "secrets": secs}
    finally:
        conn.close()


def fetch_secret(tid: str, account_id: str, field: str) -> dict:
    """**明文出口**：只供管道给自动化。禁止贴屏/进日志/进对话（凭据不离屏律）。"""
    conn = connect(tid)
    try:
        r = conn.execute(
            "SELECT cipher, kind FROM secrets WHERE account_id=? AND kind=?"
            " ORDER BY created_at DESC LIMIT 1", (account_id, field)).fetchone()
        if not r:
            return {"ok": False, "error": "没有 %s 类型的 secret：%s" % (field, account_id)}
        own = conn.execute("SELECT tid FROM accounts WHERE account_id=?", (account_id,)).fetchone()
        if not own or own[0] != tid:
            return {"ok": False, "error": "账户不属于本触手（拒绝跨触手取钥）"}
        try:
            plain = unseal(r[0], tid).decode("utf-8")
        except Exception as e:                     # noqa: BLE001
            return {"ok": False, "error": "解封失败：%s" % e}
        return {"ok": True, "account_id": account_id, "kind": r[1], "secret": plain}
    finally:
        conn.close()


def retire_account(tid: str, account_id: str) -> dict:
    conn = connect(tid)
    try:
        own = conn.execute("SELECT tid FROM accounts WHERE account_id=?", (account_id,)).fetchone()
        if not own or own[0] != tid:
            return {"ok": False, "error": "账户不存在或不属于本触手：%s" % account_id}
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        conn.execute("UPDATE accounts SET status='retired', updated_at=? WHERE account_id=?",
                     (now, account_id))
        conn.commit()
        return {"ok": True, "account_id": account_id, "status": "retired", "at": now}
    finally:
        conn.close()


def check() -> int:
    """全库总检：每根触手的账户数、掩码纪律、无明文抽样。"""
    rows = []
    if VAULT_BASE.is_dir():
        for d in sorted(VAULT_BASE.iterdir()):
            if not d.is_dir():
                continue
            tid = d.name
            if not TID_RE.match(tid):
                continue
            try:
                r = list_accounts(tid)
                by_kind: dict = {}
                for a in r["accounts"]:
                    by_kind[a["kind"]] = by_kind.get(a["kind"], 0) + 1
                rows.append((tid, len(r["accounts"]), by_kind))
            except Exception as e:                 # noqa: BLE001
                rows.append((tid, -1, {"error": str(e)[:60]}))
    print("触手密钥库总检（%s）" % VAULT_BASE)
    total = 0
    for tid, n, by_kind in rows:
        total += max(0, n)
        print("  %-6s 账户 %d  %s" % (tid, n, json.dumps(by_kind, ensure_ascii=False)))
    if not rows:
        print("  （还没有任何密钥库 —— 用 init <tid> 建）")
    print()
    print("  红线：明文只经 fetch 供机器取用；list/show 恒掩码；库文件永不入仓")
    print("判据：%s" % ("PASS（%d 根触手有库，共 %d 个账户）" % (len(rows), total) if rows else "PASS（空册，未建库）"))
    return 0


def selftest() -> int:
    """负控八件套 + 正照：DPAPI 往返 / 无明文落盘 / 跨触手隔离 / tid 守卫 /
    掩码纪律 / 触手自设口令不露面 / secret+generate 互斥。"""
    tmp = pathlib.Path(os.environ.get("TEMP", ".")) / ("vault-selftest-%s" % uuid.uuid4().hex[:8])
    tmp.mkdir(parents=True, exist_ok=True)
    tid_a, tid_b = "selftestA", "selftestB"
    va, vb = tmp / tid_a, tmp / tid_b
    va.mkdir(); vb.mkdir()
    global VAULT_BASE
    old_base = VAULT_BASE
    VAULT_BASE = tmp
    fails = []
    try:
        secret = "P@ssw0rd-触手密钥自检-9876"
        # 正照 1：DPAPI 封印 → 解封往返一致
        cipher = seal(secret.encode("utf-8"), tid_a)
        back = unseal(cipher, tid_a).decode("utf-8")
        print("正照1·DPAPI 往返一致 =", back == secret, "（必须 True）")
        if back != secret:
            fails.append("dpapi-roundtrip")
        # 负控 2：库文件字节里不许出现明文（无明文落盘）
        add_account(tid_a, "email", "github.com", "selftest-a@example.invalid",
                    secret=secret, note="自检")
        raw = (tmp / tid_a / "vault.db").read_bytes()
        leak = secret.encode("utf-8") in raw
        print("负控2·库文件含明文 =", leak, "（必须 False）")
        if leak:
            fails.append("plaintext-on-disk")
        # 负控 3：跨触手隔离 —— B 的库里不许有 A 的账户；A 的密文拿去 B 解不开
        rb = list_accounts(tid_b)["accounts"]
        cross = any(a["identity"] == "selftest-a@example.invalid" for a in rb)
        print("负控3a·B 库含 A 账户 =", cross, "（必须 False）")
        if cross:
            fails.append("cross-tentacle-row")
        try:
            unseal(cipher, tid_b)
            unseal_ok = True
        except Exception:                          # noqa: BLE001
            unseal_ok = False
        print("负控3b·A 的密文用 B  entropy 解开 =", unseal_ok, "（必须 False）")
        if unseal_ok:
            fails.append("cross-tentacle-entropy")
        # 负控 4：掩码不含完整明文
        m = mask(secret)
        full_in_mask = secret in m or len(m) >= len(secret)
        print("负控4·掩码含完整明文 =", full_in_mask, "（必须 False）")
        if full_in_mask:
            fails.append("mask-leak")
        # 负控 5：tid 守卫（路径穿越拒）
        bad = False
        for bad_tid in ("../evil", "a/b", "", "x" * 17):
            try:
                _guard_tid(bad_tid)
            except ValueError:
                continue
            bad = True
        print("负控5·坏 tid 被拒 =", not bad, "（必须 True）")
        if bad:
            fails.append("tid-guard")
        # 负控 6：list 恒掩码（拿不到明文）
        r = list_accounts(tid_a)["accounts"]
        masked_only = all("secret" not in a for a in r)
        print("负控6·list 不带明文 =", masked_only, "（必须 True）")
        if not masked_only:
            fails.append("list-plaintext")
        # 负控 7：--generate 触手自设口令 —— 明文只进封印，输出只有掩码；fetch 才解封且够强
        g = add_account(tid_a, "freebuff", "freebuff", "selftest-gen@example.invalid",
                        generate=24, note="自检-生成")
        no_plain_out = "secret" not in g and bool(g.get("masked"))
        f = fetch_secret(tid_a, g["account_id"], "password")
        strong = bool(f.get("ok")) and len(f.get("secret", "")) >= 24
        print("负控7·生成口令输出无明文 =", no_plain_out,
              "· fetch 解封且够强 =", strong, "（必须 True/True）")
        if not (no_plain_out and strong):
            fails.append("generate-no-plaintext")
        # 负控 8：既给 --secret 又给 --generate = 拒（不许两份口令打架）
        try:
            add_account(tid_a, "other", "freebuff", "selftest-both@example.invalid",
                        secret="x", generate=24)
            both_rejected = False
        except ValueError:
            both_rejected = True
        print("负控8·secret+generate 同给被拒 =", both_rejected, "（必须 True）")
        if not both_rejected:
            fails.append("generate-and-secret")
    finally:
        VAULT_BASE = old_base
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    print("自检：%s" % ("全过" if not fails else "失败 %s" % fails))
    return 0 if not fails else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="触手密钥库（DPAPI 封印 · 每根一个）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("tid")
    p = sub.add_parser("add"); p.add_argument("tid")
    p.add_argument("--kind", required=True); p.add_argument("--platform", required=True)
    p.add_argument("--identity", required=True); p.add_argument("--secret", default="")
    p.add_argument("--secret-kind", default="password"); p.add_argument("--note", default="")
    p.add_argument("--generate", type=int, default=0, nargs="?", const=24, metavar="BYTES",
                   help="触手自己设口令：生成 N 字节（≥16，裸写默认 24）强随机直接封印入库，全程不露面")
    p = sub.add_parser("list"); p.add_argument("tid"); p.add_argument("--kind", default="")
    p = sub.add_parser("show"); p.add_argument("tid"); p.add_argument("account_id")
    p = sub.add_parser("fetch"); p.add_argument("tid"); p.add_argument("account_id")
    p.add_argument("--field", default="password")
    p = sub.add_parser("retire"); p.add_argument("tid"); p.add_argument("account_id")
    sub.add_parser("check")
    sub.add_parser("selftest")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    try:
        if a.cmd == "init":
            r = init_vault(a.tid)
        elif a.cmd == "add":
            secret_arg = a.secret
            if secret_arg == "-":                        # stdin 入口：不进 argv 就不进历史/进程表
                secret_arg = sys.stdin.read().strip()
            r = add_account(a.tid, a.kind, a.platform, a.identity,
                            secret_arg, a.secret_kind, a.note, a.generate)
        elif a.cmd == "list":
            r = list_accounts(a.tid, a.kind)
        elif a.cmd == "show":
            r = show_account(a.tid, a.account_id)
        elif a.cmd == "fetch":
            r = fetch_secret(a.tid, a.account_id, a.field)
            if r.get("ok") and not a.json:
                # 明文出口：stdout 只给管道；--json 时连信封都不带（调用方自取）
                sys.stdout.write(r["secret"])
                sys.stdout.flush()
                return 0
        elif a.cmd == "retire":
            r = retire_account(a.tid, a.account_id)
        elif a.cmd == "check":
            return check()
        else:
            return selftest()
    except (ValueError, RuntimeError) as e:
        r = {"ok": False, "error": str(e)}
    if a.cmd == "fetch" and r.get("ok") and not a.json:
        sys.stdout.write(r["secret"]); sys.stdout.flush(); return 0
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.json else
          json.dumps(r, ensure_ascii=False))
    return 0 if r.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
