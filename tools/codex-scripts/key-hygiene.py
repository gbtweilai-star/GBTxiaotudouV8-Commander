# -*- coding: utf-8 -*-
"""GBT小土豆V8 · 密钥卫生闸（Owner 令 2026-10-14：新增即清旧 · 密钥面专版）。

主人原话（逐字）：「把旧的东西清理掉避免混乱，我跟你说过一百次了你都没记住，
给她把这个习惯加入，别每次做事自己搬石头砸自己的脚」。

为什么单开这一件：仓里已有 supersede-check.py（管本地文件四类旧件），但它看不见远端 ——
  ① Cloudflare Worker 的 secret 旧钥位（单值钥被列表钥取代后仍挂着）
  ② 门里 key_gateway 的废钥（铸了没用 / 明文丢了 / 被同 label 新钥取代）
  ③ 本地 .dev.vars / keys.env 的失效凭据副本（远端都退了，本地还留着 = 混乱源头）

判据（fail-closed）
  H1 远端旧钥位 ：列表钥（*_TOKENS）在役时，同族单值钥（*_TOKEN）不许还在 secret 里
  H2 门里废钥   ：库内 revoked=false 且 calls==0 且已过宽限期（30 分钟）⇒ 废钥，要 revoke
  H3 本地失效件 ：.dev.vars / keys.env 里出现已退场键名且值非空 ⇒ 红
  H4 不装看     ：远端读数取不到 ⇒ 写「未读到」并红（离线跑要显式 --offline）

用法
  py -3.14 tools/codex-scripts/key-hygiene.py            # 全跑（要 CF 凭据）
  py -3.14 tools/codex-scripts/key-hygiene.py --offline  # 只跑 H2/H3（显式降级，读数里标出来）
  py -3.14 tools/codex-scripts/key-hygiene.py --selftest

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# Windows 上 npx 不是可执行名（是 npx.cmd）⇒ 先解析真身；解释器用 sys.executable（就是本进程的 3.14）
NPX = shutil.which("npx") or shutil.which("npx.cmd") or "npx.cmd"
PYEXE = sys.executable or "py"

ROOT = Path(__file__).resolve().parents[2]
CF_ENV = Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V9\state\keys.env")
SINGLE, LIST = "GBT_ENDPOINT_TOKEN", "GBT_ENDPOINT_TOKENS"
GRACE_MIN = 30
ROWS = []


def j(cid, name, ok, detail):
    ROWS.append({"id": cid, "name": name, "ok": bool(ok), "detail": str(detail)[:200]})
    print(("%s %-3s %-10s %s" % ("PASS" if ok else "FAIL", cid, name, detail))[:220])


def _cf_env():
    env = dict(os.environ)
    try:
        for line in CF_ENV.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    except OSError:
        pass
    return env


def remote_secrets():
    """远端 secret 名单（经 wrangler；只读名字，不读值）。"""
    try:
        p = subprocess.run([NPX, "--yes", "wrangler", "secret", "list",
                            "--config", "deploy/cloud-10/wrangler.toml"],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=180, env=_cf_env(),
                           encoding="utf-8", errors="replace")
        out = (p.stdout or "") + (p.stderr or "")
        names = re.findall(r'"name"\s*:\s*"([^"]+)"', out)
        if names:
            return {"ok": True, "names": names}
        return {"ok": False, "reason": out[-200:]}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)[:200]}


def library_keys():
    """门里钥库（走唯一门 five-dim.py cap key_gateway，不直调模块函数）。"""
    try:
        p = subprocess.run([PYEXE, "tools/codex-scripts/five-dim.py", "cap", "key_gateway",
                            json.dumps({"op": "keys"}, ensure_ascii=False), "--full"],
                           cwd=str(ROOT), capture_output=True, text=True, timeout=180,
                           encoding="utf-8", errors="replace")
        raw = (p.stdout or "") + (p.stderr or "")
        i = raw.find("{")
        if i < 0:
            return {"ok": False, "reason": raw[-200:]}
        doc = json.loads(raw[i:])
 # 2026-10-14 自纠：原来死盯 result.preview.keys._head 一层 —— 结构一变就返回空列表，
        #    被 H2 念成「在役 0 把，无废钥」= **假绿**（取不到不许当 0，是本仓明令）。
        #    改成递归收集：凡是带 key_id 的字典都算一条钥，结构怎么收窄都跑得掉。
        found = []

        def _walk(o):
            if isinstance(o, dict):
                if "key_id" in o:
                    found.append(o)
                for v in o.values():
                    _walk(v)
            elif isinstance(o, list):
                for v in o:
                    _walk(v)

        _walk(doc)
        if not found:
            return {"ok": False, "reason": "解析到 0 条 key_id（结构可能又变了）——如实报未读到，不许当 0"}
        return {"ok": True, "keys": found}
    except Exception as exc:
        return {"ok": False, "reason": str(exc)[:200]}


CODE_EXT = (".py", ".js", ".mjs", ".cjs", ".ps1")
# 只在这几棵树上找活引用（全仓 34 万件，不能裸 walk）；账本/产出/文档不算活引用。
REF_ROOTS = ("tools", "gbt_allinone", "holo_pet_w3/shell", "deploy")
_REF_SKIP = {"node_modules", ".git", "__pycache__", "outputs", "output", "state",
             "memory", "docs", ".pylibs", "third_party"}


def live_refs(name: str, limit: int = 12) -> list:
    """**活引用**：这个名字真的被代码用到（返回 `文件:行` 列表）。

    🔴 2026-10-25 为什么加（口径翻正 · 留痕）：
      H1 原口径 = 「远端同时挂着 `X` 与 `XS` ⇒ 判 `X` 被取代、应删」。
      它只量了**名字还在**，没量**是否真被取代** —— 实测本轮就撞上：
      `GBT_ENDPOINT_TOKEN` 在 `chain-check.py:117` · `cloud-mesh.py:1340` ·
      `model-align.py:258` · `keys-page.py:67` **四处仍在调用**，
      删了会把这几条链路当场打死。**有活引用的钥不叫"被取代"，叫"仍在役"。**
      ⇒ 现口径：只有**零活引用**才算被取代（该删）。
      原期望没丢：零引用的老钥照样红、照样要删。

    保守口径（宁可不删）：注释行（`#` / `//` / `*` 开头）不算引用 ——
    但**行尾注释里出现它仍算引用**（拿不准就当成"有人还在用"，错杀比漏报贵）。
    """
    hits = []
    for root in REF_ROOTS:
        base_dir = ROOT / root
        if not base_dir.is_dir():
            continue
        for base, dirs, files in os.walk(base_dir):
            dirs[:] = [d for d in dirs if d not in _REF_SKIP]
            for fn in files:
                if not fn.lower().endswith(CODE_EXT):
                    continue
                p = Path(base) / fn
                try:
                    if p.stat().st_size > 2_000_000:
                        continue
                    txt = p.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                for i, line in enumerate(txt.splitlines(), 1):
                    if name not in line:
                        continue
                    s = line.strip()
                    if s.startswith("#") or s.startswith("//") or s.startswith("*"):
                        continue
                    try:
                        rel = p.relative_to(ROOT).as_posix()
                    except ValueError:
                        rel = str(p)
                    hits.append("%s:%d" % (rel, i))
                    if len(hits) >= limit:
                        return hits
    return hits


def check_remote(offline):
    if offline:
        j("H1", "远端旧钥位", True, "跳过（--offline 显式降级）—— 读数里带着这句，不许念成全绿")
        return True
    r = remote_secrets()
    if not r.get("ok"):
        j("H1", "远端旧钥位", False, "未读到远端 secret 名单：%s" % r.get("reason"))
        return False
    names = r["names"]
    stale, in_use = [], []
    for n in names:
        if not (n.endswith("S") and n[:-1] in names):
            continue
        single = n[:-1]
        refs = live_refs(single)
        (in_use if refs else stale).append((single, refs))
    if stale:
        j("H1", "远端旧钥位", False,
          "被取代且**零活引用**的单值钥：%s ⇒ 应 `wrangler secret delete`"
          % "、".join(x[0] for x in stale))
        return False
    if in_use:
        j("H1", "远端旧钥位", True,
          "单值钥仍在役（有活引用，不算被取代，**不动它**）：%s｜迁移完引用再删"
          % "；".join("%s ← %s" % (x[0], "、".join(x[1][:3])) for x in in_use))
        return True
    j("H1", "远端旧钥位", True,
      "secret %d 条：%s；无被取代的单值钥" % (len(names), "、".join(sorted(names))))
    return True


def check_library():
    r = library_keys()
    if not r.get("ok"):
        j("H2", "门里废钥", False, "未读到钥库：%s" % r.get("reason"))
        return False
    now = time.time()
    waste = []
    for k in r["keys"]:
        if k.get("revoked"):
            continue
        calls = k.get("calls") or 0
        try:
            ts = time.mktime(time.strptime(str(k.get("created_at"))[:19], "%Y-%m-%dT%H:%M:%S"))
        except Exception:
            ts = now
        age = (now - ts) / 60.0
        if calls == 0 and age > GRACE_MIN:
            waste.append("%s(%s,%.0f分钟,calls=0)" % (k.get("key_id"), k.get("label"), age))
    j("H2", "门里废钥", not waste,
      ("铸了没用还在役：%s ⇒ 应 key_gateway revoke" % "、".join(waste)) if waste
      else "在役 %d 把，无 calls=0 废钥" % len([x for x in r["keys"] if not x.get("revoked")]))
    return not waste


def check_local(retired):
    files = [ROOT / "deploy/cloud-10/.dev.vars", ROOT / "state/keys.env",
             Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V9\state\keys.env"),
             Path(r"C:\Users\ADMIN\gbt-potato-v9\state\keys.env")]
    hits = []
    for f in files:
        try:
            txt = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for n in retired:
            for m in re.finditer(r"^\s*%s\s*=\s*(\S+)" % re.escape(n), txt, re.M):
                if m.group(1).strip():
                    hits.append("%s:%s" % (f.name, n))
    j("H3", "本地失效件", not hits,
      ("远端都退了，本地还留值：%s（下次照它接 = 混乱源头）" % "、".join(hits)) if hits
      else "本地无已退场键的非空值（检查 %d 个键名）" % len(retired))
    return not hits


def selftest():
    ck = []
    def c(name, ok, d=""):
        ck.append(bool(ok))
        print(("OK  " if ok else "BAD ") + name + (" — " + str(d)[:90] if d else ""))
 # 2026-10-25 口径翻正后，控制也一起改（旧控制写的是"名字同时在 ⇒ 必被取代"，
    #    那正是被证伪的那条）。现在分两个方向各控一次：
    #      正控：名字同时在 **且零活引用** ⇒ 才算被取代（用一个人造名，仓里必然零引用）
    #      负控：名字同时在 **但有活引用** ⇒ **不许**判被取代（用真实的 GBT_ENDPOINT_TOKEN）
 # 2026-10-25 自纠（P33 量具把自己算进去）：第一版这里写 `fake = "GBT_..._SELFTEST_ONLY"`，
    #    于是 `live_refs(fake)` 在 **本文件第 255 行** 命中——**判据把自己的测试字面量当成了活引用**，
    #    正控当场 BAD。⇒ 名字**拼出来**，别以完整字面量出现。
    fake = "GBT_SUPERSEDED_" + "SELFTEST_ONLY"
    refs_fake = live_refs(fake)
    c("正控·零活引用的老单值 ⇒ 认作被取代", refs_fake == [], refs_fake[:3])
    refs_real = live_refs(SINGLE)
    c("负控·有活引用的单值 ⇒ 不许判被取代", len(refs_real) > 0,
      "活引用 %d 处（例：%s）" % (len(refs_real), refs_real[:2]))
    c("负控·注释行不算活引用（人造名只在注释里也不该被算进来）", refs_fake == [], refs_fake[:3])
    names_clean = [LIST, "GW_AUTH"]
    stale2 = [n[:-1] for n in names_clean if n.endswith("S") and n[:-1] in names_clean]
    c("负控·只有列表 ⇒ 不许虚报", stale2 == [], stale2)
    dev = ROOT / "deploy/cloud-10/.dev.vars"
    txt = dev.read_text(encoding="utf-8", errors="replace") if dev.exists() else ""
    c("正控·.dev.vars 已清（不该再有旧键赋值）", ("GBT_ENDPOINT_TOKEN=" not in txt), "看到赋值" if "GBT_ENDPOINT_TOKEN=" in txt else "只剩注释")
    c("正控·真源读得到（mesh.json 在）", (ROOT / "deploy/cloud-10/mesh.json").is_file())
    bad = len([x for x in ck if not x])
    print("\n密钥卫生闸 selftest：%d/%d" % (len(ck) - bad, len(ck)))
    return 1 if bad else 0


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    print("=== 密钥卫生闸 · 新增即清旧（密钥面）===")
    sec = {"names": []} if a.offline else remote_secrets()
    retired = [SINGLE] if (LIST in (sec.get("names") or [])) else ([SINGLE, LIST] if a.offline else [])
    ok1 = check_remote(a.offline)
    ok2 = check_library()
    ok3 = check_local(retired)
    bad = [r for r in ROWS if not r["ok"]]
    print("\n判据 PASS %d · FAIL %d" % (len(ROWS) - len(bad), len(bad)))
    try:
        (ROOT / "state" / "key-hygiene.json").write_text(json.dumps(
            {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "offline": bool(a.offline), "rows": ROWS},
            ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass
    return 0 if (ok1 and ok2 and ok3) else 1


if __name__ == "__main__":
    sys.exit(main())
