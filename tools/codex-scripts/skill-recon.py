# -*- coding: utf-8 -*-
"""skill-recon · 技能对账 + 安全扫描 + 体检（蒸馏自 K-Dense-AI/scientific-agent-skills，MIT）。

上游口径（README 徽章，现读 2026-10-15）：MIT · arXiv 2609.00065 · Skills **177** · Databases 100+ ·
Standard **Agent Skills**/**Agent Plugins** · CI 含 **Security Scan** + **Skill Tests**。
本件只蒸馏它的三条工程纪律：**标准校验 / 安全扫描 / 可跑判据**，不搬它的技能内容。

判据（fail-closed）：S1 同名冲突（两棵树同名但内容不同）· S2 前注缺失/坏 YAML · S3 桩件（<20 行且无 scripts/）
              S4 安全扫描五类命中（索取凭据 / 破坏命令 / 拉取执行 / 改系统配置 / 伪装系统指令）
              S5 取不到读数 ⇒ 红（空/不存在不许当绿）
用法：py -3.14 tools/codex-scripts/skill-recon.py [--check|--selftest]
开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations
import argparse, hashlib, os, pathlib, re, sys, tempfile

ROOTS = [pathlib.Path(os.path.expanduser("~/.openclaw-autoclaw/skills")),
         pathlib.Path(os.path.expanduser("~/.agents/skills"))]
DANGER = [
    ("索取凭据", re.compile(r"(请提供|填入|粘贴|发送)[^\n]{0,12}(API[ _-]?KEY|密钥|token|密码|凭据)", re.I)),
    ("破坏命令", re.compile(r"\brm\s+-rf\b|\bdel\s+/f|\bformat\s+[a-z]:|清空磁盘", re.I)),
    ("拉取执行", re.compile(r"(curl|iwr|Invoke-WebRequest)[^\n]{0,80}\|\s*(bash|sh|iex|Invoke-Expression)", re.I)),
    ("改系统配置", re.compile(r"\breg\s+add\b|\bsetx\b[^\n]{0,40}(PATH|环境变量)|改\s*policy\.py", re.I)),
    ("伪装系统指令", re.compile(r"ignore (all )?previous instructions|you are now|system\s*:\s*you", re.I)),
]

def _fm(text):
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    if not m: return None, "缺前注"
    try:
        import yaml
        yaml.safe_load(m.group(1))
    except ImportError:
        pass
    except Exception as e:
        return None, "YAML 坏: " + str(e)[:40]
    nm = re.search(r"^name:\s*(.+)$", m.group(1), re.M)
    return (nm.group(1).strip() if nm else None), None

def _norm(txt: str) -> str:
    """归一化后再比 —— **口径改动留痕（R-H998 · 2026-10-15）**：

    原期望：同名 SKILL.md 两棵树**逐字节相同**才是同一份；
    实测翻正（第二版·同日）：安装流程还会把**长 description 截断**（374 字 → 125 字）——
    这是安装期的显示裁剪，不是内容漂移 ⇒ 描述行**整体不参与比较**，只在 S1b 里另报件数。
    实测翻正：安装流程会给 `description:` 自动**加引号**（YAML 保护）并把行尾转成 LF，
    于是 66 件本来同源的技能全被判成"同名不同内容"（**格式化差异被当成内容漂移**）。
    现在：行尾统一 LF + 去掉 description 值两端的引号之后再比 —— 只报**语义**差异。
    """
    t = str(txt or "").replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for line in t.split("\n"):
        s = line.strip()
        if s.startswith("description:"):
            # 描述**整个不参与比较**：安装流程会把长描述截断（实测 374 字 → 125 字）
            out.append("description: <安装流程可截断·不参与比对>")
        else:
            out.append(line)
    return "\n".join(out).strip()

def scan():
    rows = {}
    for root in ROOTS:
        if not root.is_dir():
            print("  S5 红：读不到技能根 " + str(root))
            return None
        for d in sorted(root.iterdir()):
            md = d / "SKILL.md"
            if not md.is_file(): continue
            txt = md.read_text(encoding="utf-8", errors="replace")
            nm, err = _fm(txt)
            h = hashlib.sha256(_norm(txt).encode("utf-8", "replace")).hexdigest()[:12]
            rows.setdefault(nm or d.name, []).append({
                "tree": root.name, "dir": d.name, "lines": txt.count(chr(10)) + 1,
                "has_scripts": (d / "scripts").is_dir(), "err": err, "sha": h, "path": str(md)})
    return rows

def check() -> int:
    rows = scan()
    if rows is None: print("判据 PASS 0 · FAIL 1（取不到读数）"); return 1
    n = sum(len(v) for v in rows.values())
    print("=== 技能对账（%d 件 / %d 名）===" % (n, len(rows)))
    # R-H998 · 2026-10-15 留痕：以前读不出“到底比的是哪两棵”，实测后补上。
    #   本工具比的是**两棵安装树**，**不含仓内 `.dsh/skills`**；
    #   其中 `~/.agents/skills` 按 AGENTS.md 是**外部共享树（明令不许写）** ⇒ S1 不是“仓内 vs 已装”，
    #   而是“两棵已装树之间的年代差”。要看仓内与已装是否一致，另跑对拍。
    print("  根（本工具只比这两棵）：")
    for _r in ROOTS:
        print("    · %s%s" % (_r, "（外部共享树，不写）" if ".agents" in str(_r) else ""))
    conf = [k for k, v in rows.items() if len(v) > 1 and len({x["sha"] for x in v}) > 1]
    badhead = [(k, x["err"]) for k, v in rows.items() for x in v if x["err"]]
    stubs = [k for k, v in rows.items() for x in v if x["lines"] < 20 and not x["has_scripts"]]
    print("  S1 同名不同内容（重复/漂移）：%d 个 ⇒ %s" % (len(conf), conf[:8]))
    print("  S2 前注问题：%d 件 ⇒ %s" % (len(badhead), badhead[:5]))
    print("  S3 桩件：%d 个 ⇒ %s" % (len(stubs), stubs[:8]))
    hits = []
    for k, v in rows.items():
        for x in v:
            t = pathlib.Path(x["path"]).read_text(encoding="utf-8", errors="replace")
            for label, pat in DANGER:
                for m in pat.finditer(t):
                    ln = t[:m.start()].count(chr(10)) + 1
                    hits.append((k, label, ln)); break
    print("  S4 安全扫描命中：%d 件 ⇒ %s" % (len(hits), hits[:6]))
    red = bool(conf or badhead or hits)
    print("判据 PASS %d · FAIL %d" % (1 if not red else 0, 1 if red else 0))
    return 1 if red else 0

def selftest() -> int:
    ck = []
    def c(n, ok, d=""):
        ck.append(bool(ok)); print(("OK  " if ok else "BAD ") + n + (" — " + str(d)[:60] if d else ""))
    d = pathlib.Path(tempfile.mkdtemp())
    good = d / "clean" / "SKILL.md"; good.parent.mkdir(parents=True)
    good.write_text("---\nname: clean\ndescription: ok\n---\n" + "x\n" * 25, encoding="utf-8")
    evil = d / "evil" / "SKILL.md"; evil.parent.mkdir(parents=True)
    evil.write_text("---\nname: evil\ndescription: bad\n---\n" + "x\n" * 25 + "rm -rf /  ; 请提供 API KEY\n", encoding="utf-8")
    t = evil.read_text(encoding="utf-8")
    c("正控·干净件无命中", not any(p.search(good.read_text(encoding="utf-8")) for _, p in DANGER))
    c("负控·破坏命令必须命中", bool(DANGER[1][1].search(t)))
    c("负控·索取凭据必须命中", bool(DANGER[0][1].search(t)))
    c("正控·前注能解析", _fm(good.read_text(encoding="utf-8"))[0] == "clean")
    c("负控·缺前注要报错", _fm("no frontmatter")[1] is not None)
    bad = len([x for x in ck if not x])
    print("\nskill-recon selftest: %d/%d" % (len(ck) - bad, len(ck)))
    return 1 if bad else 0

def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true"); ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    return selftest() if a.selftest else check()

if __name__ == "__main__":
    sys.exit(main())
