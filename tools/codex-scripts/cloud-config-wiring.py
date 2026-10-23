#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""**部署前接线对账**（离线 · 不改远端 · 不联网）—— 回答一个问题：

    「这份 `wrangler.toml` 声明的东西，跟代码真正读的东西，对得上吗？」

为什么要有这一件（一手账）：
  `deploy/cloud-10/` 是**生产落点**，而这个网一次都没部署过 ⇒ 任何"配置与代码对不上"
  都要等真部署那一刻才会以 `undefined` 的形式炸出来（那时已经在改远端了）。
  实测踩过的同型事故就在旁边：`wrangler.toml` 的注释里写着
  「不加 `--config` 会读到父目录那份 Pages 配置 ⇒ **会部到错的项目上**」——
  配置错位的代价不是报错，是**静默做错事**。

它查四类：
  A. **读而未声明**：代码读 `env.X` / `e.X` / `ctx.env.X`，而配置里既没声明、连注释里都没提
     ⇒ 部署后那个变量就是 `undefined`（这是**硬伤**）。
  B. **声明而未读**：配置声明了、代码一处都不读 ⇒ 死配置（只说不管）。
  C. **形态 B 的 10 个生成件**：每个模块的 `[[services]]` 绑定必须**正好**是它的 9 个对等位
     （多一个少一个都是拼接断裂），且包名/入口文件必须对得上。
  D. **容器面**：`container/server.py` 能编译、`Dockerfile` 的入口与 `wrangler.container.toml`
     说的是同一件事；容器配置里不许有明文密钥。

口径（三条，与全仓一致）：
  1. **不知道就说不知道**：`modules.js` 里有一处 `env[keyName]` 是**动态取键**，
     静态扫描**看不见**它 ⇒ 本器把它单独列出来，不假装"全部 env 读取已核对"。
  2. **注释里提过 ≠ 声明过**：注释提到只算"有人知道这件事"，不算"配好了"；两者分开列。
  3. 只读：不改配置、不碰远端、不联网。

用法：
  python tools/codex-scripts/cloud-config-wiring.py [--json] [--root deploy/cloud-10]
退出码：0 = 无硬伤；1 = 有硬伤（A 类或有 C/D 类不一致）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 🔴 2026-10-10 修（**同族缺陷，第二次撞上**）：本件在 **GBK 控制台**上不带 -X utf8 调用时**当场崩**。
#    实测真因（不是猜）：gbt_allinone/tests/test_cloud_config_wiring.py 第 34 行调本件用的是
#        subprocess.run([sys.executable, str(TOOL), "--root", root, "--json"], ...)
#    —— **没带 -X utf8**；本件 ensure_ascii=False 印到 U+21D2（⇒）时抛
#        UnicodeEncodeError: 'gbk' codec can't encode character U+21D2
#    ⇒ **stdout 是空的** ⇒ 测试的 _rep() 解析成 {} ⇒ 它那 5 条"检查器有没有牙"的自测**全红**。
#    ⇒ 这是**工具不够硬**，不是测试的错：任何不带 -X utf8 的调用者都会踩。
#    同类先例：tools/codex-scripts/audit-dead-judgments.py（2026-10-10 同一修法）。
#    全仓扫描：tools/codex-scripts 下会印非 ASCII 的 .py 里，**已有 307 件带守门、143 件还没带**。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")   # type: ignore[attr-defined]
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
ALIAS_DECL = re.compile(r"\b(?:const|let|var)\s+(e|env2|envAlias)\s*=\s*[^;\n]*\benv\b")
# ⚠️ 结尾是 {1,} 不是 {2,}：`AI` 只有 2 个字符，用 {2,} 会**扫不到 `e.AI`**，
#    于是本器会把「AI 绑定」报成"声明了但代码不读"（假红），而 AI 恰恰是最要紧的那一个绑定。
#    这是本器**自己的**一处假阳性，首跑就被这行读数暴露了。
ENV_READ = re.compile(r"\b(env|e|ctx\.env|this\.env)\s*\.\s*([A-Z][A-Z0-9_]{1,})\b")
DYN_READ = re.compile(r"\b(env|e)\s*\[\s*[A-Za-z_$][\w$]*\s*\]")
BINDING_LINE = re.compile(r'^\s*(?:#\s*)?binding\s*=\s*"([^"]+)"')
COMMENT_BINDING = re.compile(r'^\s*#\s*binding\s*=\s*"([^"]+)"')
TABLE = re.compile(r"^\s*\[\[?([^\]]+)\]\]?", re.M)
SECRETY = re.compile(r"(API_KEY|_KEY|TOKEN|TOKENS|SECRET|PASSWORD|PASSWD)\b")


def _declared(toml_text: str) -> tuple[set, set, set]:
    """返回 (已声明名, 只在注释里出现过的名, 配置里提到过的任何全大写名)。"""
    declared, commented = set(), set()
    for line in toml_text.splitlines():
        m = BINDING_LINE.match(line)
        if not m:
            continue
        if COMMENT_BINDING.match(line):
            commented.add(m.group(1))
        else:
            declared.add(m.group(1))
    # [vars] 段里的普通键（含值为 "" 的）
    in_vars = False
    for line in toml_text.splitlines():
        s = line.strip()
        if s.startswith("["):
            in_vars = s == "[vars]"
            continue
        if in_vars and "=" in s and not s.startswith("#"):
            declared.add(s.split("=", 1)[0].strip())
    mentioned = set(re.findall(r"\b([A-Z][A-Z0-9_]{2,})\b", toml_text))
    return declared, commented, mentioned


def _reads(paths: list) -> tuple[dict, list, list]:
    """返回 (名字->[文件:行], 动态取键的位置, 扫过的文件)。"""
    reads: dict = {}
    dyn = []
    seen = []
    for p in paths:
        if not p.is_file():
            continue
        seen.append(str(p.relative_to(ROOT)) if str(p).startswith(str(ROOT)) else str(p))
        text = p.read_text(encoding="utf-8", errors="replace")
        aliases = {m.group(1) for m in ALIAS_DECL.finditer(text)}
        for m in ENV_READ.finditer(text):
            holder, name = m.group(1), m.group(2)
            # `e.X` 只在同文件里确认过 e 就是 env 别名时才采信（否则 e 可能是别的东西）
            if holder == "e" and "e" not in aliases:
                continue
            ln = text[: m.start()].count("\n") + 1
            reads.setdefault(name, []).append("%s:%d" % (p.name, ln))
        for m in DYN_READ.finditer(text):
            ln = text[: m.start()].count("\n") + 1
            dyn.append("%s:%d" % (p.name, ln))
    return reads, dyn, seen


def _rel(p: Path) -> str:
    """尽量给相对路径；**不在仓内就老实给绝对路径**。

    ⚠️ 首版这里直接 `path.relative_to(ROOT)` —— 探针根（测试造的 TEMP 目录）不在仓内，
    于是抛 `ValueError` 把整个工具弄崩，四条探针用例全红。**「读数的呈现方式」不该把工具弄崩。**
    """
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="部署前接线对账（只读 · 离线）")
    ap.add_argument("--root", default=str(ROOT / "deploy" / "cloud-10"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    base = Path(a.root)
    if not base.is_dir():
        print("找不到 %s" % base)
        return 2

    cfg = base / "wrangler.toml"
    if not cfg.is_file():
        print("找不到 %s" % cfg)
        return 2
    toml_text = cfg.read_text(encoding="utf-8", errors="replace")
    declared, commented, mentioned = _declared(toml_text)
    reads, dyn, scanned = _reads([base / "src" / "worker.js", base / "src" / "modules.js"])

    # A 类：读到了，但既没声明、注释里也没提过 ⇒ 部署后就是 undefined
    hard, soft, ok = [], [], []
    for name, where in sorted(reads.items()):
        if name in declared:
            ok.append((name, where))
        elif name in commented or name in mentioned:
            soft.append((name, where))     # 注释里提过：有人知道，但配置里没声明
        else:
            hard.append((name, where))

    # B 类：声明了但从没读
    unused = sorted(n for n in declared if n not in reads)

    # C 类：形态 B 十个模块
    # ⚠️ 探针根（测试造的最小目录）通常没有 mesh.json —— 那不算错，**跳过并说明**，
    #    不许因此崩掉（首版会在 json.loads 处抛，探针用例根本跑不起来）。
    mod_problems, mesh_note = [], ""
    mesh_file = base / "mesh.json"
    modules = []
    if mesh_file.is_file():
        try:
            mesh = json.loads(mesh_file.read_text(encoding="utf-8"))
            modules = mesh.get("modules") or []
        except Exception as exc:  # noqa: BLE001
            mod_problems.append("mesh.json 读不动：%s" % str(exc)[:100])
    else:
        mesh_note = "mesh.json 不在 ⇒ 形态 B 未对账（不是通过，是没查）"
    ids = [m.get("id") if isinstance(m, dict) else m for m in modules]
    for m in modules:
        mid = m.get("id") if isinstance(m, dict) else m
        d = base / "modules" / mid
        wt = d / "wrangler.toml"
        if not wt.is_file():
            mod_problems.append("%s：wrangler.toml 不在" % mid)
            continue
        t = wt.read_text(encoding="utf-8", errors="replace")
        peers = set(re.findall(r'service\s*=\s*"([^"]+)"', t))
        want = {x for x in ids if x and x != mid}
        if peers != want:
            mod_problems.append("%s：服务绑定 %d 个（应 %d），差集 多=%s 少=%s"
                                % (mid, len(peers), len(want),
                                   sorted(peers - want)[:3], sorted(want - peers)[:3]))
        nm = re.search(r'^name\s*=\s*"([^"]+)"', t, re.M)
        if not nm or nm.group(1) != mid:
            mod_problems.append("%s：name 字段与目录名不符（%s）"
                                % (mid, nm.group(1) if nm else "无"))
        mn = re.search(r'^main\s*=\s*"([^"]+)"', t, re.M)
        if not mn or not (d / mn.group(1)).is_file():
            mod_problems.append("%s：main 指的文件不在（%s）" % (mid, mn.group(1) if mn else "无"))

    # D 类：容器面
    cont_problems, cont_notes = [], []
    srv = base / "container" / "server.py"
    if srv.is_file():
        import py_compile
        try:
            py_compile.compile(str(srv), doraise=True, cfile=str(Path(__import__("tempfile").gettempdir()) / "_cfgwire_srv.pyc"))
            cont_notes.append("container/server.py 编译通过")
        except Exception as exc:  # noqa: BLE001
            cont_problems.append("container/server.py 编译失败：%s" % str(exc)[:120])
    else:
        cont_notes.append("container/server.py 不在（容器面未做）")
    ctoml = base / "wrangler.container.toml"
    if ctoml.is_file():
        ct = ctoml.read_text(encoding="utf-8", errors="replace")
        if SECRETY.search(ct) and re.search(r'=\s*"[A-Za-z0-9_\-]{16,}"', ct):
            cont_problems.append("wrangler.container.toml 里疑似有明文密钥")
        cont_notes.append("wrangler.container.toml 在（%d 字节）" % len(ct))
    df = base / "container" / "Dockerfile"
    if df.is_file():
        dt = df.read_text(encoding="utf-8", errors="replace")
        if "server.py" not in dt:
            cont_problems.append("Dockerfile 里没提到 server.py ⇒ 入口可能对不上")
        cont_notes.append("Dockerfile 在")
    else:
        cont_notes.append("Dockerfile 不在")

    hard_issues = len(hard) + len(mod_problems) + len(cont_problems)
    rep = {"ok": hard_issues == 0, "readonly": True, "config": _rel(cfg),
           "declared": sorted(declared), "commented_only": sorted(commented),
           "read_names": sorted(reads), "scanned_files": scanned,
           "A_read_but_undeclared": hard, "B_declared_but_unread": unused,
           "notes_documented_but_not_declared": soft,
           "dynamic_env_access_unscannable": dyn,
           "form_b_problems": mod_problems, "form_b_note": mesh_note,
           "container_problems": cont_problems,
           "container_notes": cont_notes,
           "boundary": ("静态扫描**看不见**动态取键（`env[keyName]`）—— 见 dynamic_env_access_unscannable；"
                        "注释里提过只算『有人知道』，**不算声明过**。本器不联网、不改远端、不改配置。")}

    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print("═══ 部署前接线对账 · %s ═══" % rep["config"])
        print("扫过 %d 个源文件 · 配置里声明了 %d 个名 · 代码读到 %d 个名"
              % (len(scanned), len(declared), len(reads)))
        print("")
        if hard:
            print("🔴 A 类 · **读而未声明**（部署后就是 undefined）：")
            for n, w in hard:
                print("   · %-24s %s" % (n, " ".join(w[:2])))
        else:
            print("✅ A 类 · 读而未声明：0（代码读的每个名字，配置里都有交代）")
        if soft:
            print("🟡 注释里提过、但配置里**没有声明**（不算配好了）：")
            for n, w in soft:
                print("   · %-24s %s" % (n, " ".join(w[:2])))
        if unused:
            print("⚪ B 类 · 声明了但代码一处都不读（死配置）：%s" % "、".join(unused))
        if dyn:
            print("⚠ 动态取键（静态扫不到，别声称『全核对过』）：%s" % "、".join(dyn))
        print("")
        print("形态 B · 10 个生成件："
              + (mesh_note if mesh_note else
                 ("✅ 绑定/包名/入口全对" if not mod_problems else "🔴 %d 处不一致" % len(mod_problems))))
        for p in mod_problems[:12]:
            print("   · %s" % p)
        print("容器面：" + ("✅ " if not cont_problems else "🔴 ") + "；".join(cont_notes + cont_problems))
        print("")
        print("边界：%s" % rep["boundary"])
        print("结论：%s" % ("无硬伤" if hard_issues == 0 else "有 %d 处硬伤" % hard_issues))
    return 0 if hard_issues == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
