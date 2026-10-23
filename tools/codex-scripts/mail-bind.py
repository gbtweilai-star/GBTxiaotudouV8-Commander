#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""邮箱**双向绑定**（收 + 发）· 固化与验证（主人 2026-09-23 令）

## 它解决什么
主人要的是「登入 + 双向绑定 + 固化备用」。本仓现状（真读数）：
**发信腿已配**（`GBT_SMTP_*` = forwardemail + 自有域名）但**收信腿是断的**
（`GBT_IMAP_*` / 应用专用密码都未配）⇒ 「收不到验证码」。

本件把**收**这条腿接上，并把「绑没绑上」变成**可复核的读数**，而不是一句声明。

## 三条口径（写死）
1. **密码只从环境变量读，永不落盘、永不回显、永不进日志。** 报告里只有「已配 / 未配」
   与前 4 位掩码；异常文本也要过一遍脱敏（服务器回包万一带着它，不许漏出去）。
2. **没凭据就失败关闭**：`verify` / `roundtrip` 一律 `status: no_credential` + 退出码 3，
   **不许**编出任何"已连接/已收信"的字段。（与 `figma-fetch.py` 同一套纪律。）
3. **`roundtrip` 才算"双向"**：只登录一次 IMAP 叫「能收」；要证明**双向**，
   必须 **SMTP 发一封给自己 → IMAP 把它读回来**。少一半就是少一半，报告里分开写。

## 凭据落点（主人自己做，值不经过 AI）
```
setx GBT_IMAP_HOST "imap.zoho.com"
setx GBT_IMAP_PORT "993"
setx GBT_IMAP_USER "payzelle@zohomail.com"     # 账号名不是密码
setx GBT_IMAP_PASS "<Zoho 后台生成的应用专用密码>"
```
（`ZOHO_APP_PASSWORD` 也可作为密码变量名；`GBT_MAIL_ADDRESS` 可作为账号名兜底。）

## 用法
```
python tools/codex-scripts/mail-bind.py status       # 每条腿 已配/未配 + 端点通不通（不带凭据）
python tools/codex-scripts/mail-bind.py verify       # 真登录 IMAP + 列 INBOX（只读，不取正文）
python tools/codex-scripts/mail-bind.py probe        # **分辨型**诊断：IMAP×4 主机 + SMTP×3 主机，逐条说清卡在哪
python tools/codex-scripts/mail-bind.py roundtrip    # 发一封给自己再读回来 ⇒ 这才叫双向
python tools/codex-scripts/mail-bind.py bind         # 固化非密配置到 state/mail_bind.json
```
退出码：0 成 · 3 无凭据 · 4 端点不通 · 5 认证失败 · 6 其它
"""
from __future__ import annotations

import argparse
import imaplib
import json
import os
import re
import smtplib
import socket
import ssl
import sys
import time
from email.message import EmailMessage
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "state" / "mail_bind.json"

PASS_VARS = ("GBT_IMAP_PASS", "ZOHO_APP_PASSWORD")
# 🔴 第 78 轮抓出来的真缺陷：原来回退链里带 `GBT_SMTP_USER` ⇒ 本机 `GBT_SMTP_USER`
#    是**另一个服务**（forwardemail 的 noreply@…）⇒ 固化时它**冒充了本账号**，
#    盘上写下"服务=Zoho Mail，账号=nore********"这种**假账**。
#    ⇒ 回退只认本账号自己的变量名；发信腿那条另列（见 `cmd_status` 的「发信腿（既有的那条）」）。
USER_VARS = ("GBT_IMAP_USER", "GBT_MAIL_ADDRESS")
ZOHO_HINT = ("zoho.com", "zohomail")
DEFAULTS = {"host": "imap.zoho.com", "port": 993, "smtp_host": "smtp.zoho.com", "smtp_port": 465}

# 凭据**变量名**可换（`--pass-env` / `--user-env`）—— 与 `figma-fetch.py --token-env` 同一套做法。
# 两个用途：① 不把变量名写死（换服务/换命名规矩时不用改代码）；
# ② 让验收器能造出「真的没有凭据」这一态去验**失败关闭**（否则本机 setx 过的值会被读出来，
#    "无凭据"这一态根本造不出来）。名字可换，**值**照样不落盘、不回显。
OVERRIDE = {"pass": None, "user": None}


def env2(*names):
    """按顺序取第一个非空环境变量（Process → User → Machine 三层都看）。"""
    for n in names:
        for scope in ("Process", "User", "Machine"):
            v = os.environ.get(n) if scope == "Process" else None
            if v:
                return n, v
        v = os.environ.get(n)
        if v:
            return n, v
    # 兜底：读 User/Machine（setx 写的是 User 层，本进程可能还没继承）
    for n in names:
        for scope in ("User", "Machine"):
            try:
                import winreg
                key = (winreg.HKEY_CURRENT_USER if scope == "User" else winreg.HKEY_LOCAL_MACHINE)
                sub = "Environment" if scope == "User" else r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
                with winreg.OpenKey(key, sub) as k:
                    v, _ = winreg.QueryValueEx(k, n)
                    if v:
                        return n, v
            except Exception:                                              # noqa: BLE001
                continue
    return None, None


def mask(v):
    """凭据/账号只许出现前 4 位（本仓规矩）。"""
    if not v:
        return None
    v = str(v)
    return v[:4] + "*" * min(8, max(4, len(v) - 4))


def creds():
    hn, host = env2("GBT_IMAP_HOST")
    pn, port = env2("GBT_IMAP_PORT")
    un, user = env2(*(OVERRIDE["user"],) if OVERRIDE["user"] else USER_VARS)
    pwn, pw = env2(*(OVERRIDE["pass"],) if OVERRIDE["pass"] else PASS_VARS)
    return {
        "host": host or DEFAULTS["host"], "host_env": hn or "(默认)",
        "port": int(port) if port else DEFAULTS["port"], "port_env": pn or "(默认)",
        "user": user, "user_env": un, "user_mask": mask(user),
        "pass": pw, "pass_env": pwn,
        "状态": {"host": "已配" if host else "默认值", "user": "已配" if user else "未配",
               "pass": "已配" if pw else "未配"},
    }


def scrub(txt, pw):
    """异常文本脱敏：万一服务器/库把密码带回来，不许漏出去。"""
    if not txt:
        return txt
    s = str(txt)
    if pw:
        s = s.replace(pw, "***")
    return re.sub(r"(?i)(password|passwd|pass)[=:]\s*\S+", r"\1=***", s)


def tcp_probe(host, port, timeout=8.0):
    """只做 TCP+TLS 握手，不带任何凭据 ⇒ 证明"端点可达"与"能登录"是两件事。"""
    t0 = time.time()
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, int(port)), timeout=timeout) as raw:
            with ctx.wrap_socket(raw, server_hostname=host) as s:
                return {"ok": True, "tls": s.version(),
                        "证书主体": (s.getpeercert() or {}).get("subject"),
                        "耗时s": round(time.time() - t0, 2)}
    except Exception as e:                                                 # noqa: BLE001
        return {"ok": False, "why": "%s: %s" % (type(e).__name__, scrub(e, None)),
                "耗时s": round(time.time() - t0, 2)}


def cmd_status(a):
    c = creds()
    res = {"ok": True, "status": "status",
           "凭据": {"host": c["状态"]["host"], "user": c["状态"]["user"], "pass": c["状态"]["pass"],
                  "host值": c["host"], "host变量": c["host_env"],
                  "账号掩码": c["user_mask"], "账号变量": c["user_env"],
                  "密码变量": c["pass_env"]},
           "收信端点": tcp_probe(c["host"], c["port"])}
    sh = os.environ.get("GBT_SMTP_HOST") or env2("GBT_SMTP_HOST")[1]
    sp = os.environ.get("GBT_SMTP_PORT") or env2("GBT_SMTP_PORT")[1]
    res["发信腿（已有的那条）"] = {
        "host": sh or None, "port": sp or None,
        "状态": "已配" if sh else "未配",
        "_注意": "这条是 forwardemail + 自有域名，**不是** Zoho；双向绑定要的是同一个账号收发。"}
    res["_口径"] = ("「端点可达」只证明网络与 TLS 通，**不证明能登录** —— 两件事分开报。"
                  "密码只报已配/未配与前 4 位掩码，本件不落盘、不回显。")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


def _need_cred(c):
    if not c["user"] or not c["pass"]:
        print(json.dumps({"ok": False, "status": "no_credential",
                          "凭据": {"user": c["状态"]["user"], "pass": c["状态"]["pass"]},
                          "how_to": "主人本机 setx GBT_IMAP_USER / GBT_IMAP_PASS（应用专用密码），"
                                    "值不要贴给 AI",
                          "_口径": "失败关闭：没凭据就不报任何「已连接/已登录/已收信」字段。"},
                         ensure_ascii=False, indent=1))
        return 3
    return 0


def cmd_verify(a):
    c = creds()
    rc = _need_cred(c)
    if rc:
        return rc
    try:
        M = imaplib.IMAP4_SSL(c["host"], c["port"], timeout=20)
    except Exception as e:                                                 # noqa: BLE001
        print(json.dumps({"ok": False, "status": "endpoint_unreachable",
                          "why": scrub(e, c["pass"]), "host": c["host"], "port": c["port"]},
                         ensure_ascii=False, indent=1))
        return 4
    try:
        M.login(c["user"], c["pass"])
    except Exception as e:                                                 # noqa: BLE001
        print(json.dumps({"ok": False, "status": "auth_failed", "account": c["user_mask"],
                          "why": scrub(e, c["pass"]),
                          "_口径": "认证失败 ≠ 端点不通：端点刚才已经握上手了，是账号/应用密码不对。"},
                         ensure_ascii=False, indent=1))
        return 5
    out = {"ok": True, "status": "verify", "account": c["user_mask"], "host": c["host"]}
    try:
        typ, data = M.select("INBOX", readonly=True)
        out["INBOX"] = {"select": typ.decode() if isinstance(typ, bytes) else str(typ),
                        "邮件总数": int(data[0]) if data and data[0] else None}
        typ, data = M.search(None, "ALL")
        ids = (data[0].split() if data and data[0] else [])
        out["最近 3 封的主题（只读表头，不取正文）"] = []
        for i in ids[-3:]:
            t, d = M.fetch(i, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])")
            if t == "OK" and d and isinstance(d[0], tuple):
                out["最近 3 封的主题（只读表头，不取正文）"].append(
                    d[0][1].decode("utf-8", "replace").strip().replace("\r\n", " | ")[:200])
    except Exception as e:                                                 # noqa: BLE001
        out["INBOX"] = {"why": scrub(e, c["pass"])}
    finally:
        try:
            M.logout()
        except Exception:                                                  # noqa: BLE001
            pass
    out["_口径"] = "只读验证：登录 + 选 INBOX + 读表头。**没有取任何正文，没有删任何信。**"
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


def cmd_roundtrip(a):
    c = creds()
    rc = _need_cred(c)
    if rc:
        return rc
    tag = "gbt-bind-%d" % int(time.time())
    from_addr = c["user"]
    os.environ.get("GBT_SMTP_HOST")
    use_zoho = (a.smtp_host or DEFAULTS["smtp_host"])
    port = int(a.smtp_port or DEFAULTS["smtp_port"])
    out = {"ok": False, "status": "roundtrip", "account": c["user_mask"], "标记": tag,
           "第一腿（SMTP 发给自己）": None, "第二腿（IMAP 读回来）": None}
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = from_addr
    msg["Subject"] = tag
    msg.set_content("GBT 双向绑定自检，可删。tag=%s" % tag)
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(use_zoho, port, timeout=25, context=ctx) as s:
            s.login(c["user"], c["pass"])
            s.send_message(msg)
        out["第一腿（SMTP 发给自己）"] = {"ok": True, "host": use_zoho, "port": port}
    except Exception as e:                                                 # noqa: BLE001
        out["第一腿（SMTP 发给自己）"] = {"ok": False, "host": use_zoho, "port": port,
                                 "why": scrub(e, c["pass"])}
        out["_口径"] = ("**双向只成了一半不到**：发信腿没过 ⇒ 没资格说「绑上了」。"
                      "注意这与已经配好的 forwardemail 那条不是同一件事。")
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 5
    found = None
    deadline = time.time() + (a.wait or 90)
    try:
        M = imaplib.IMAP4_SSL(c["host"], c["port"], timeout=20)
        M.login(c["user"], c["pass"])
        M.select("INBOX", readonly=True)
        while time.time() < deadline and not found:
            typ, data = M.search(None, '(SUBJECT "%s")' % tag)
            ids = data[0].split() if data and data[0] else []
            if ids:
                found = ids[-1].decode() if isinstance(ids[-1], bytes) else str(ids[-1])
                break
            time.sleep(5)
        M.logout()
    except Exception as e:                                                 # noqa: BLE001
        out["第二腿（IMAP 读回来）"] = {"ok": False, "why": scrub(e, c["pass"])}
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 6
    out["第二腿（IMAP 读回来）"] = ({"ok": True, "找到": True, "邮件号": found,
                             "等了多少秒": round((a.wait or 90) - max(0, deadline - time.time()), 1)}
                            if found else
                            {"ok": True, "找到": False,
                             "why": "发出去了但 %ss 内没在 INBOX 里查到（Zoho 免费版投递可能慢，"
                             "或进了垃圾箱）⇒ **这一腿不算成立**" % (a.wait or 90)})
    out["ok"] = bool(found)
    out["status"] = "roundtrip_ok" if found else "roundtrip_half"
    out["_口径"] = ("双向 = 发得出去 **且** 收得回来，两条腿都有读数才算。"
                  "自检信带唯一标记（可删），没有动收件箱里任何别的信。")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if found else 6


def cmd_probe(a):
    """**分辨型**诊断：IMAP 多主机 + SMTP 多主机，逐主机分开报「握得上手」与「认证通过」。

    为什么要分两条腿：IMAP 失败有好几种完全不同的真因，处置也不同 ——
    ① 凭据本身不对 ⇒ 两条腿一起拒；② 只是后台**没开 IMAP 访问** ⇒ SMTP 可能过、只有 IMAP 拒。
    两条腿一起看，才分得清该去改哪儿。
    """
    c = creds()
    rc = _need_cred(c)
    if rc:
        return rc

    def try_imap(h):
        t0 = time.time()
        try:
            M = imaplib.IMAP4_SSL(h, 993, timeout=20)
            M.login(c["user"], c["pass"])
            n = None
            try:
                _t, d = M.select("INBOX", readonly=True)
                n = int(d[0]) if d and d[0] else None
            except Exception:                                              # noqa: BLE001
                pass
            try:
                M.logout()
            except Exception:                                              # noqa: BLE001
                pass
            return {"登录": "成功", "INBOX 总数": n, "耗时s": round(time.time() - t0, 2)}
        except Exception as e:                                             # noqa: BLE001
            return {"登录": "失败", "why": scrub(e, c["pass"])[:160],
                    "耗时s": round(time.time() - t0, 2)}

    def try_smtp(h):
        t0 = time.time()
        try:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(h, 465, timeout=20, context=ctx) as s:
                s.login(c["user"], c["pass"])
            return {"登录": "成功", "耗时s": round(time.time() - t0, 2)}
        except Exception as e:                                             # noqa: BLE001
            return {"登录": "失败", "why": scrub(e, c["pass"])[:160],
                    "耗时s": round(time.time() - t0, 2)}

    imap = {h: try_imap(h) for h in ("imap.zoho.com", "imap.zoho.in", "imap.zoho.eu", "imap.zoho.com.au")}
    imap_ok = [h for h, r in imap.items() if r["登录"] == "成功"]
    smtp = {}
    for h in ("smtp.zoho.com", "smtp.zoho.in", "smtp.zoho.eu"):
        smtp[h] = try_smtp(h)
        if smtp[h]["登录"] == "成功":
            break                                   # 通了一条就别继续试（不做无谓的失败尝试）
    smtp_ok = [h for h, r in smtp.items() if r["登录"] == "成功"]

    def own_domain_imap():
        """自有域收信腿（`gbtxiaotudou.com` 托管在 forwardemail）：**收发同一个账号**才叫双向。

        为什么单独一条（2026-10-21 加）：本机现在是**两个账号** —— 收信 `payz****@zohomail.com`、
        发信 `nore****@gbtxiaotudou.com`。就算 Zoho 那条登录成功，也收不到自己发出去的那封信，
        「双向」永远验不成。这条腿用发信那个账号 + 它自己的邮箱密码去登 forwardemail 的 IMAP。
        没有密码变量时**如实报未配**，绝不拿 Zoho 的账号去冒充这一条。
        """
        un, user = env2("GBT_SMTP_USER")
        pn, pw = env2("GBT_SMTP_PASS", "GBT_SMTP_PASSWORD",
                      "FORWARDEMAIL_PASS", "GBT_FORWARDEMAIL_PASS")
        if not user:
            return {"状态": "未配", "why": "缺账号变量 GBT_SMTP_USER", "端点": "imap.forwardemail.net:993"}
        if not pw:
            return {"状态": "未配", "why": "缺密码变量（GBT_SMTP_PASS / FORWARDEMAIL_PASS 都没有）",
                    "账号掩码": mask(user), "账号变量": un, "端点": "imap.forwardemail.net:993"}
        t0 = time.time()
        try:
            M = imaplib.IMAP4_SSL("imap.forwardemail.net", 993, timeout=20)
            M.login(user, pw)
            n = None
            try:
                _t, d = M.select("INBOX", readonly=True)
                n = int(d[0]) if d and d[0] else None
            except Exception:                                              # noqa: BLE001
                pass
            try:
                M.logout()
            except Exception:                                              # noqa: BLE001
                pass
            return {"状态": "登录成功", "账号掩码": mask(user), "账号变量": un,
                    "INBOX 总数": n, "耗时s": round(time.time() - t0, 2)}
        except Exception as e:                                             # noqa: BLE001
            return {"状态": "登录失败", "账号掩码": mask(user), "账号变量": un,
                    "why": scrub(e, pw)[:160], "耗时s": round(time.time() - t0, 2)}

    res = {"ok": bool(imap_ok), "status": "login_ok" if imap_ok else "auth_failed",
           "account": c["user_mask"], "IMAP": imap, "SMTP": smtp,
           "自有域收信腿": own_domain_imap(),
           "下一步": ("收信腿通了 ⇒ 可以跑 roundtrip 验双向" if imap_ok and smtp_ok else
                   "只有一条腿通 ⇒ 去 Zoho 后台查另一条腿的开关" if (imap_ok or smtp_ok) else
                   "两条腿一起被拒 ⇒ 问题在**凭据本身**，按下面顺序查：\n"
                   "  ① **两步验证与应用专用密码必须配套**：开了 2FA 就必须用应用专用密码（主密码一律不过）；"
                   "没开 2FA 时应用专用密码也**不生效** —— 这两种错配都会得到同一个 `AUTHENTICATIONFAILED`。\n"
                   "  ② **setx 时那个密码串有没有打错**（应用密码是随机串，手输极易错一格）；"
                   "更稳的做法：复制粘贴，或先写进一个临时文件核对再 setx。\n"
                   "  ③ Zoho 后台 → 设置 → 邮件 → 邮件账户 → **IMAP 访问 = 启用**（Zoho 默认不开）。\n"
                   "  ④ 账号收信域到底是不是 `zohomail.com`（浏览器登进 mail.zoho.com 看右上角那个地址最准）。")}
    res["_口径"] = ("密码只从环境变量读（含 setx 写进注册表的那份），**不落盘、不回显、异常文本过脱敏**；"
                  "「握得上手」与「认证通过」分开报。失败重试有上限，不做撞库。")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if imap_ok else 5


def cmd_bind(a):
    """固化**非密**配置：只写主机/端口/账号掩码/变量名 ⇒ 重启不丢，密码永远在环境里。"""
    c = creds()
    STATE.parent.mkdir(parents=True, exist_ok=True)
    rec = {"绑定时间": time.strftime("%Y-%m-%dT%H:%M:%S"), "服务": "Zoho Mail",
           "收信": {"host": c["host"], "port": c["port"], "host变量": c["host_env"],
                  "账号掩码": c["user_mask"], "账号变量": c["user_env"]},
           "密码落点": {"变量名": c["pass_env"] or PASS_VARS[0], "值": "不落盘（只在环境变量里）"},
           "发信（既有）": {"host": os.environ.get("GBT_SMTP_HOST"), "状态": "已配"
                      if os.environ.get("GBT_SMTP_HOST") else "未配"},
           "凭据状态": c["状态"]}
    if c["user"] and not any(d in c["user"] for d in ZOHO_HINT):
        rec["_账号域核对"] = ("⚠️ 这个账号的域**看起来不是 Zoho 的**（收到 %s）⇒ "
                         "请核对 `GBT_IMAP_USER` 是不是真填了 %s 那个地址；"
                         "本件不回退到别的服务的账号（那会写下假账）。"
                         % (c["user_mask"], "payzelle@zohomail.com"))
    STATE.write_text(json.dumps(rec, ensure_ascii=False, indent=1), "utf-8")
    print(json.dumps({"ok": True, "status": "bound", "落点": str(STATE), "记录": rec,
                      "_口径": "固化的是**非密配置**；密码只在环境变量里，本文件里没有它。"},
                     ensure_ascii=False, indent=1))
    return 0


def main():
    ap = argparse.ArgumentParser(description="邮箱双向绑定（收+发）· 固化与验证")
    sub = ap.add_subparsers(dest="cmd")
    for name, fn in (("status", cmd_status), ("verify", cmd_verify), ("probe", cmd_probe),
                     ("roundtrip", cmd_roundtrip), ("bind", cmd_bind)):
        p = sub.add_parser(name)
        p.set_defaults(fn=fn)
        p.add_argument("--pass-env", default="", help="改读哪个变量拿密码（默认 GBT_IMAP_PASS）")
        p.add_argument("--user-env", default="", help="改读哪个变量拿账号（默认 GBT_IMAP_USER）")
        if name == "roundtrip":
            p.add_argument("--smtp-host", default="")
            p.add_argument("--smtp-port", default="")
            p.add_argument("--wait", type=int, default=90, help="等收信最多多少秒")
    a = ap.parse_args()
    if not getattr(a, "fn", None):
        ap.print_help()
        return 2
    OVERRIDE["pass"] = a.pass_env or None
    OVERRIDE["user"] = a.user_env or None
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
