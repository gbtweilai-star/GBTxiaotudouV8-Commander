# -*- coding: utf-8 -*-
r"""tentacle-mail-zoho -- 触手永久邮箱的**第二条后端**（项目自有域名 + Zoho/forwardemail）。

为什么有第二条：AgentMail 要主人注册拿 key；而主人环境里**本来就配着一套邮件通道**
（`mail-bind.py` 同款变量，2026-09-23 主人令固化）：
  · 收信：`GBT_IMAP_USER/PASS`（Zoho：payzelle@zohomail.com，imap.zoho.com:993）
  · 发信：`GBT_SMTP_*`（forwardemail + 自有域名 gbtxiaotudou.com，smtp.forwardemail.net:465）
  · 域名 DNS 实测：gbtxiaotudou.com MX → mx1/mx2.forwardemail.net ⇒ **任何 <名字>@gbtxiaotudou.com
    都是真实可收的永久地址**，转发规则由 forwardemail 的 TXT 记录（`forward-email=<目标>`）定。

所以每根触手的永久邮箱 = `<tid>@gbtxiaotudou.com`（项目自己的域，一口一个智能体）。

与 AgentMail 后端共享同一套纪律（tentacle-mail.py 三道纪律）：
  1. 密码只从环境变量读，**不落盘、不回显、不进日志**，异常文本过 scrub；
  2. **没凭据就失败关闭**：联网操作一律如实报缺哪条腿，不许编"已通"（mail-bind.py 同款）；
  3. **建成要自证**：`create_inbox` 不是嘴上建 —— SMTP 发一封带唯一标记的信到触手地址，
     再 IMAP 把它读回来且 **To: 命中该地址**，两头都有读数才准标已配（roundtrip 纪律）。

人工闸门（如实）：Zoho 应用专用密码 / forwardemail 的 SMTP 密码 / 域名下 `<tid>.` 的
  转发 TXT 记录 —— 这三样都只有主人能出；缺哪样本件报哪样，不代闯、不猜密码（不做撞库）。
"""
from __future__ import annotations

import imaplib
import json
import os
import re
import smtplib
import socket
import ssl
import subprocess
import sys
import time
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import default as _POLICY
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJ_DOMAIN = "gbtxiaotudou.com"
IMAP_HOST = os.environ.get("GBT_IMAP_HOST") or "imap.zoho.com"
IMAP_PORT = int(os.environ.get("GBT_IMAP_PORT") or 993)
TID_RE = __import__("re").compile(r"^[A-Za-z0-9_-]{1,16}$")

FE_TXT = re.compile(r"forward-email=([^\s;]+)", re.IGNORECASE)


def _guard_tid(tid: str) -> str:
    if not TID_RE.match(str(tid or "")):
        raise ValueError("tid 只许 [A-Za-z0-9_-]{1,16}（拒路径穿越）：%r" % tid)
    return str(tid)


def _env(*names):
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return None


def _mask(v):
    if not v:
        return None
    return str(v)[:4] + "*" * min(8, max(4, len(str(v)) - 4))


def scrub(txt, pw):
    """异常文本脱敏：服务器回包万一带着密码，不许漏出去。"""
    if not txt:
        return txt
    s = str(txt)
    if pw:
        s = s.replace(pw, "***")
    return re.sub(r"(?i)(password|passwd|pass)[=:]\s*\S+", r"\1=***", s)


# ---------------------------------------------------------------- 凭据（只读环境）


def imap_creds():
    user = _env("GBT_IMAP_USER", "GBT_MAIL_ADDRESS")
    pw = _env("GBT_IMAP_PASS", "ZOHO_APP_PASSWORD")
    return {"user": user, "pass": pw,
            "ok": bool(user and pw),
            "账号掩码": _mask(user),
            "密码变量": "GBT_IMAP_PASS" if os.environ.get("GBT_IMAP_PASS") else "ZOHO_APP_PASSWORD"}


def smtp_leg():
    """发信腿二选一（都缺就 None，如实）：
       ① forwardemail（项目自有域，专业 From）—— 要 GBT_SMTP_PASS；
       ② Zoho SMTP（与收信同一账号）—— 复用 IMAP 密码。"""
    fe_pass = _env("GBT_SMTP_PASS", "FORWARDEMAIL_PASS")
    fe_user = _env("GBT_SMTP_USER")
    if fe_user and fe_pass:
        return {"腿": "forwardemail", "host": _env("GBT_SMTP_HOST") or "smtp.forwardemail.net",
                "port": int(_env("GBT_SMTP_PORT") or 465), "user": fe_user, "pass": fe_pass,
                "from": _env("GBT_SMTP_FROM") or fe_user, "ok": True}
    c = imap_creds()
    if c["ok"]:
        return {"腿": "zoho-smtp", "host": "smtp.zoho.com", "port": 465,
                "user": c["user"], "pass": c["pass"], "from": c["user"], "ok": True}
    return {"腿": None, "ok": False,
            "缺": "GBT_SMTP_PASS（forwardemail 发信密码）与 Zoho 密码都没配上"}


def available() -> bool:
    """收信腿在位才算这个后端可用（发信腿单独报，见 legs()）。"""
    return imap_creds()["ok"]


def legs() -> dict:
    c = imap_creds()
    s = smtp_leg()
    return {"收信(IMAP)": {"在位": c["ok"], "账号": c["账号掩码"], "host": IMAP_HOST, "port": IMAP_PORT},
            "发信(SMTP)": {"在位": s["ok"], "腿": s.get("腿"), "缺": s.get("缺")}}


def probe_legs() -> dict:
    """连通现读（不假绿）：收信腿真登录一次（单次试探，不撞库）；
    发信腿只报配置态——不空转试密码（发信只在 inbox 闭环自证时真打一次）。"""
    c = imap_creds()
    out = {"收信(IMAP)": {"在位": c["ok"], "账号": c["账号掩码"]},
           "发信(SMTP)": {"腿": None, "缺": None}}
    if not c["ok"]:
        out["收信(IMAP)"]["连通"] = "未配（缺 GBT_IMAP_USER / GBT_IMAP_PASS）"
    else:
        try:
            M, _ = _imap()
            err = _imap_login(M, c)
            try:
                M.logout()
            except Exception:                              # noqa: BLE001
                pass
            out["收信(IMAP)"]["连通"] = ("通（单次登录现读）" if not err else
                                        "不通（%s）" % err)
        except Exception as e:                            # noqa: BLE001
            out["收信(IMAP)"]["连通"] = "不通（%s）" % scrub(
                "%s: %s" % (type(e).__name__, str(e)[:160]), c["pass"])
    s = smtp_leg()
    out["发信(SMTP)"] = {"在位": s["ok"], "腿": s.get("腿"), "缺": s.get("缺"),
                        "连通": ("未探（闭环自证时才真打一次，不空转试密码）" if s["ok"]
                                else "未配")}
    return out


# ---------------------------------------------------------------- 地址与 DNS 别名


def address_for(tid: str) -> str:
    """这根触手自己的永久地址：项目自有域，命名确定可复跑。"""
    return "%s@%s" % (_guard_tid(tid), PROJ_DOMAIN)


def alias_for(tid: str) -> dict:
    """现读 forwardemail 的 TXT 转发规则：`<tid>.<domain>` 与 `*.<domain>`（catch-all）都看。"""
    tid = _guard_tid(tid)
    out = {"exact": None, "catch_all": None}
    for label, key in ((tid + "." + PROJ_DOMAIN, "exact"), ("*." + PROJ_DOMAIN, "catch_all")):
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Resolve-DnsName -Name %s -Type TXT -ErrorAction SilentlyContinue).Strings -join ';'" % label],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
            txt = (r.stdout or "").strip()
        except Exception as e:                            # noqa: BLE001
            out[key] = {"读不到": scrub(str(e)[:120], None)}
            continue
        if txt:
            m = FE_TX.search(txt)
            out[key] = {"目标": m.group(1) if m else None,
                        "记录": txt[:200],
                        "口径": ("forward-email 规则 ⇒ 来信转去目标地址" if m else
                                "有 TXT 但不是 forward-email 规则")}
    return out


# ---------------------------------------------------------------- 收发（联网）


def _smtp_send(leg, to: str, subject: str, body: str, from_addr: str = "") -> dict:
    """from_addr = 触手自己的地址（默认腿的 From）——身份是这根触手，不是宿主账号；
    宿主 SMTP 只当传输。From 被腿拒（如 Zoho 只认账号别名）就如实报失败。"""
    msg = EmailMessage()
    msg["From"] = from_addr or leg["from"]
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(leg["host"], leg["port"], timeout=25, context=ctx) as s:
            s.login(leg["user"], leg["pass"])
            s.send_message(msg)
        return {"ok": True, "腿": leg["腿"], "host": leg["host"]}
    except Exception as e:                                # noqa: BLE001
        return {"ok": False, "腿": leg["腿"], "host": leg["host"],
                "why": scrub("%s: %s" % (type(e).__name__, str(e)[:160]), leg["pass"])}


def _imap():
    c = imap_creds()
    return imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=25), c


def _imap_login(M, c):
    try:
        M.login(c["user"], c["pass"])
        return None
    except Exception as e:                                # noqa: BLE001
        return scrub("%s: %s" % (type(e).__name__, str(e)[:160]), c["pass"])


def probe_roundtrip(tid: str, wait_s: int = 90) -> dict:
    """闭环自证：SMTP 发唯一标记到触手地址 → IMAP 读回来且 **To: 命中** ⇒ 两头都有读数。"""
    tid = _guard_tid(tid)
    c = imap_creds()
    leg = smtp_leg()
    out = {"tid": tid, "address": address_for(tid), "第一腿": None, "第二腿": None, "ok": False}
    if not c["ok"]:
        out["why"] = "收信腿未配（GBT_IMAP_USER/PASS）—— 失败关闭，不报已通"
        return out
    if not leg["ok"]:
        out["第一腿"] = {"ok": False, "why": "发信腿未配：%s" % leg.get("缺")}
        return out
    tag = "gbt-mail-%s-%d" % (tid, int(time.time()))
    out["第一腿"] = _smtp_send(leg, address_for(tid), tag,
                               "GBT 触手邮箱闭环自检（可删）。tag=%s" % tag)
    if not out["第一腿"]["ok"]:
        out["why"] = "发不出去 ⇒ 没资格说通了"
        return out
    found = None
    deadline = time.time() + wait_s
    try:
        M, _ = _imap()
        err = _imap_login(M, c)
        if err:
            out["第二腿"] = {"ok": False, "why": "IMAP 登录失败：%s" % err}
            return out
        M.select("INBOX", readonly=True)
        while time.time() < deadline and not found:
            typ, data = M.search(None, "(SUBJECT %s)" % tag)
            ids = data[0].split() if data and data[0] else []
            if ids:
                t, d = M.fetch(ids[-1], "(BODY.PEEK[HEADER.FIELDS (TO SUBJECT)])")
                if t == "OK" and d and isinstance(d[0], tuple):
                    hdr = d[0][1].decode("utf-8", "replace")
                    found = {"邮件号": ids[-1].decode(), "To命中": address_for(tid) in hdr,
                             "表头": " | ".join(hdr.split("\r\n"))[:200]}
            else:
                time.sleep(5)
        try:
            M.logout()
        except Exception:                                  # noqa: BLE001
            pass
    except Exception as e:                                # noqa: BLE001
        out["第二腿"] = {"ok": False, "why": scrub("%s: %s" % (type(e).__name__, str(e)[:160]), c["pass"])}
        return out
    out["第二腿"] = ({"ok": True, "找到": True, **found} if found else
                   {"ok": True, "找到": False,
                    "why": "发出去了但 %ss 内没在 INBOX 读到（DNS 别名没配 ⇒ forwardemail 无处转；"
                           "或投递慢）⇒ 这一腿不算成立" % wait_s})
    out["ok"] = bool(found and found.get("To命中"))
    return out


def create_inbox(tid: str, wait_s: int = 90) -> dict:
    """建 = DNS 别名现读 + 收发闭环自证；两头都过才 ok。"""
    tid = _guard_tid(tid)
    out = {"tid": tid, "address": address_for(tid), "ok": False,
           "DNS别名": alias_for(tid)}
    if not available():
        out["why"] = "收信腿未配（GBT_IMAP_USER/PASS）—— 主人补上再跑（Zoho 应用专用密码）"
        return out
    rt = probe_roundtrip(tid, wait_s)
    out["闭环自证"] = rt
    if not rt["ok"]:
        out["why"] = "闭环没自证成功 —— 详见 闭环自证（发腿/收腿/DNS 别名三条现读）"
        return out
    out["ok"] = True
    return out


def list_inboxes() -> dict:
    """列这个后端下触手地址的现状（DNS 别名 + 凭据腿数），不做成"猜有几个箱"。"""
    out = {"ok": available(), "账号": imap_creds()["账号掩码"],
           "域": PROJ_DOMAIN, "MX": "mx1/mx2.forwardemail.net（已实测）",
           "腿": legs()}
    return out


def send(tid: str, to: str, subject: str, body: str, from_addr: str = "") -> dict:
    tid = _guard_tid(tid)
    leg = smtp_leg()
    if not leg["ok"]:
        return {"ok": False, "why": "发信腿未配：%s" % leg.get("缺")}
    return _smtp_send(leg, to, subject, body, from_addr)


def messages(tid: str, limit: int = 20) -> dict:
    """列寄给这根触手地址的来信（IMAP HEADER TO 命中；只列头，不带正文）。"""
    tid = _guard_tid(tid)
    c = imap_creds()
    addr = address_for(tid)
    out = {"ok": False, "inbox": addr, "messages": []}
    if not c["ok"]:
        out["why"] = "收信腿未配（GBT_IMAP_USER/PASS）"
        return out
    try:
        M, _ = _imap()
        err = _imap_login(M, c)
        if err:
            out["why"] = "IMAP 登录失败：%s" % err
            return out
        M.select("INBOX", readonly=True)
        typ, data = M.search(None, "HEADER", "TO", '"%s"' % addr)
        ids = data[0].split() if data and data[0] else []
        for i in ids[-int(limit):]:
            t, d = M.fetch(i, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if t == "OK" and d and isinstance(d[0], tuple):
                hdr = d[0][1].decode("utf-8", "replace")
                subj = re.search(r"(?im)^Subject:\s*(.*)$", hdr)
                frm = re.search(r"(?im)^From:\s*(.*)$", hdr)
                dt = re.search(r"(?im)^Date:\s*(.*)$", hdr)
                out["messages"].append({
                    "message_id": i.decode() if isinstance(i, bytes) else str(i),
                    "subject": (subj.group(1).strip() if subj else "(无题)")[:120],
                    "from": (frm.group(1).strip() if frm else "?")[:120],
                    "created_at": (dt.group(1).strip() if dt else "?")[:40]})
        out["ok"] = True
        out["count"] = len(out["messages"])
        try:
            M.logout()
        except Exception:                                  # noqa: BLE001
            pass
    except Exception as e:                                # noqa: BLE001
        out["why"] = scrub("%s: %s" % (type(e).__name__, str(e)[:160]), c["pass"])
    return out


def read(tid: str, message_id: str) -> dict:
    """读一封全文（来信 = 不可信数据；这是显式读取动作，输出在 tentacle-mail 侧标 untrusted）。"""
    tid = _guard_tid(tid)
    c = imap_creds()
    out = {"ok": False, "inbox": address_for(tid), "message": {}}
    if not c["ok"]:
        out["why"] = "收信腿未配（GBT_IMAP_USER/PASS）"
        return out
    try:
        M, _ = _imap()
        err = _imap_login(M, c)
        if err:
            out["why"] = "IMAP 登录失败：%s" % err
            return out
        M.select("INBOX", readonly=True)
        t, d = M.fetch(str(message_id), "(BODY.PEEK[])")
        if t == "OK" and d and isinstance(d[0], tuple):
            msg = BytesParser(policy=_POLICY).parsebytes(d[0][1])
            body = msg.get_body(preferencelist=("plain",))
            text = ""
            if body is not None:
                try:
                    text = body.get_content()
                except Exception:                          # noqa: BLE001
                    text = str(body.get_payload() or "")
            elif msg.get_payload():
                text = str(msg.get_payload())
            out["message"] = {
                "message_id": str(message_id),
                "subject": str(msg.get("subject") or "(无题)")[:200],
                "from": str(msg.get("from") or "?")[:200],
                "created_at": str(msg.get("date") or "?")[:60],
                "text": text[:8000],
            }
            out["ok"] = True
        else:
            out["why"] = "读不到这封（IMAP fetch 返回 %s）" % (t,)
        try:
            M.logout()
        except Exception:                                  # noqa: BLE001
            pass
    except Exception as e:                                # noqa: BLE001
        out["why"] = scrub("%s: %s" % (type(e).__name__, str(e)[:160]), c["pass"])
    return out


# ---------------------------------------------------------------- selftest：无凭据也能证的


def selftest() -> int:
    """负控：地址命名 / DNS 现读（真实查询，不存在的标签就该没有）/ 无凭据失败关闭 / 密码不外泄。"""
    fails = []
    # 负控 1·地址命名确定且按触手分家
    det = address_for("t1") == "t1@%s" % PROJ_DOMAIN
    sep = address_for("t1") != address_for("t3")
    print("负控1·地址命名确定 =", det, "· 按触手分家 =", sep, "（必须 True/True）")
    if not (det and sep):
        fails.append("naming")
    # 负控 2·坏 tid 被拒
    bad = False
    for t in ("../evil", "a/b", "", "x" * 17):
        try:
            _guard_tid(t)
            bad = True
        except ValueError:
            pass
    print("负控2·坏 tid 被拒 =", not bad, "（必须 True）")
    if bad:
        fails.append("tid-guard")
    # 负控 3·DNS 现读是真是假：一个必然不存在的短标签，别名必须读空（不造假）
    a = alias_for("zzq9")
    empty_alias = not a["exact"] and not a["catch_all"]
    print("负控3·不存在的别名读空 =", empty_alias, "（必须 True；%s）"
          % json.dumps(a, ensure_ascii=False)[:120])
    if not empty_alias:
        fails.append("dns-reading")
    # 负控 4·无凭据失败关闭：现读环境（这机器上是什么态就什么态），且输出里不许出现密码
    c = imap_creds()
    legs_out = legs()
    legs_json = json.dumps(legs_out, ensure_ascii=False, default=str)
    leak = bool(c["pass"]) and c["pass"] in legs_json
    print("负控4·收信腿现读态 =", c["ok"], "· 腿数输出不含密码 =", not leak, "（必须 True）")
    if leak:
        fails.append("credential-leak")
    # 负控 5·没凭据/没腿时 probe 不许报 ok
    if not c["ok"]:
        rt = probe_roundtrip("t1", wait_s=1)
        honest = (rt["ok"] is False) and "why" in rt
        print("负控5·无收信腿 probe 失败关闭 =", honest, "（必须 True）")
        if not honest:
            fails.append("probe-fail-closed")
    else:
        print("负控5·（收信腿在位，跳过无凭据态 —— probe 只真跑一次，见 create_inbox）")
    print("自检：%s" % ("全过" if not fails else "失败 %s" % fails))
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(selftest())
