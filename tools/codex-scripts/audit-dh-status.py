# -*- coding: utf-8 -*-
"""数字人**唯一状态源**（`STATUS.json`）的读数审计 —— 它引用到的文件到底在不在、大小对不对。

为什么单给它一道门：这份文件是**每轮会话上下文**的来源（宿主插件现读它、注入 systemPrompt），
所以它写的每一个路径/字节数都会被下一轮的模型当成事实。**它写错，模型就跟着错**。
实测踩过（同一族的第 4 次）：`current_asset_verdict.readings.joints` 那条路径读错 ⇒ 注入文本
长期写着「关节 undefined」；而这次要查的是**文件引用**：状态源说某产物在 `raw/xxx.glb`、
说它 45,754,652 B —— 那就得逐条现读盘。

判据（现读，不猜）：
  · 字符串里出现的相对路径（带扩展名）⇒ 相对 `holo_pet/assets/digital-human/` 判断存在性；
  · 绝对路径（`C:\\…`）⇒ 直接判断存在性；
  · 括号里写 `1.75MB` / `45,754,652 B` 这类**大小声明**，且同一行/同一条目有可定位的文件 ⇒ 比字节数（±5% 容差，因为"1.75MB"是四舍五入）。
默认**只报告**（退出码 0）；`--strict` 时"文件不在"记硬失败（大小对不上只警告，避免把四舍五入判成错）。

用法：
    py -3.14 tools/codex-scripts/audit-dh-status.py            # 报告
    py -3.14 tools/codex-scripts/audit-dh-status.py --strict    # 文件不在就非零退出
    py -3.14 tools/codex-scripts/audit-dh-status.py --status <另一份.json>   # 审候选稿（不动现役的）
    py -3.14 tools/codex-scripts/audit-dh-status.py --no-receipt             # 不写回执（不留痕）
    py -3.14 tools/codex-scripts/audit-dh-status.py --negctl    # 负控：故意写死路径必须判红（不碰真件、不写回执）
退出码：0 = 通过；1 = --strict 下有缺失 / 负控未通过；2 = 状态源本身不在盘上。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
STATUS = ROOT / "holo_pet" / "assets" / "digital-human" / "STATUS.json"
BASE = STATUS.parent
OUT = ROOT / "state" / "dh_status_audit.json"

REL_RE = re.compile(r"(?<![\w/\\~.])((?:~[\\/]|\.{1,2}[\\/])?(?:[A-Za-z0-9_\u4e00-\u9fff\-]+[\\/])+[A-Za-z0-9_\u4e00-\u9fff\-]+\.(?:glb|gltf|fbx|png|jpg|jpeg|webp|mp4|mov|json|md|py|ps1|txt|csv|wav|mp3))")
# ⚠️ 全角标点必须排除：状态源里绝对路径后面常紧跟 `（说明）`，
#    第一版只排了 `）` 没排 `（`，于是把 `…\skills\digihuman-pipeline\（托管根…` 整段当路径 ⇒ 假红。
ABS_RE = re.compile(r"([A-Za-z]:\\[^\"'，。；、（）()\s]+)")
SIZE_RE = re.compile(r"(\d[\d,]{2,})\s*(?:B|字节)\b|(\d+(?:\.\d+)?)\s*(MB|KB|GB)", re.I)


def walk(o, path="$", out=None):
    out = [] if out is None else out
    if isinstance(o, dict):
        for k, v in o.items():
            walk(v, "%s.%s" % (path, k), out)
    elif isinstance(o, list):
        for i, v in enumerate(o):
            walk(v, "%s[%d]" % (path, i), out)
    elif isinstance(o, str):
        out.append((path, o))
    return out


def negctl() -> int:
    """负控：**故意写一个不在盘的路径**，这道门必须判红。

    为什么必须常驻：本门的判据是"引用到的文件在不在盘上"。如果哪天正则被改窄、
    或者基准列表被改得"怎么都能命中"，**缺失就会被静默吞掉**，而输出照样是
    「引用文件 全在盘」—— 与真的全在盘一模一样。坏输入必须变红，才算门还在。
    夹具写在临时目录、一律 `--no-receipt`，**不碰现役状态源、不盖真回执**。
    """
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="dh-status-negctl-"))
    real = "render/骨架复核-数字人idle.png"          # 现读在盘（正对照）
    ghost = "render/__definitely_absent__.png"        # 现读必然不在盘（负对照）
    cases = [("clean", real, 0), ("missing_ref", ghost, 1)]
    wrong = []
    for name, ref, want in cases:
        p = tmp / (name + ".json")
        p.write_text(json.dumps({"probe": ref}, ensure_ascii=False), encoding="utf-8")
        print("---- 负控 %s（引用 %s，期望退出码 %d）----" % (name, ref, want))
        got = main(["--status", str(p), "--strict", "--no-receipt"])
        mark = "✅" if got == want else "🔴"
        print("   %s 负控 %-12s 期望 %d · 实得 %d" % (mark, name, want, got))
        if got != want:
            wrong.append(name)
    if wrong:
        print("🔴 负控失败：%s —— 这门的「文件不在盘」判据不灵敏（等于没这道门）" % "、".join(wrong))
        return 1
    print("✅ 负控通过：干净引用判绿（exit 0）· 幽灵引用判红（exit 1）")
    return 0


def main(argv: list[str]) -> int:
    strict = "--strict" in argv
    no_receipt = "--no-receipt" in argv
    # `--status` 是为了**能在候选稿上跑**（也为了负控能不碰现役那份）。
    status_path = STATUS
    if "--status" in argv:
        i = argv.index("--status")
        if i + 1 >= len(argv):
            print("🔴 --status 后面要给一个 json 路径")
            return 2
        status_path = Path(argv[i + 1])
    if not status_path.is_file():
        print("🔴 状态源不在盘上：%s" % status_path)
        return 2
    base = status_path.parent
    try:
        shown = str(status_path.relative_to(ROOT))
    except ValueError:
        shown = str(status_path)                     # 临时稿在仓外，别 raise
    data = json.loads(status_path.read_text(encoding="utf-8"))
    strings = walk(data)

    refs: dict[str, dict] = {}          # 文件路径 -> 谁引用了它
    for path, text in strings:
        for m in REL_RE.finditer(text):
            rel = m.group(1).replace("\\", "/")
            refs.setdefault(rel, {"abs": None, "refs": []})["refs"].append(path)
        for m in ABS_RE.finditer(text):
            raw = m.group(1).rstrip("\\/")
            refs.setdefault(raw, {"abs": raw, "refs": []})["refs"].append(path)

    # ⚠️ 相对路径的**基准不唯一**（这是我第一版把 29 个文件误报成"不在盘"的原因）：
    #    状态源里的相对路径有三种基准 —— ① 它自己所在的目录（`raw/…`、`samples/…`）
    #    ② 仓根（`tools/codex-scripts/…`、`plugins/…`、`render/…`）③ 它提到的技能目录（`scripts/…`、`references/…`）。
    #    ⇒ **三个基准都不命中才算不在盘**；命中就把"用哪个基准"写进回执。
    BASES = [base, ROOT, ROOT / "skills" / "digihuman-pipeline"]

    def resolve(rel_or_abs: str):
        if re.match(r"^[A-Za-z]:", rel_or_abs):
            p = Path(rel_or_abs)
            return (p, "绝对路径") if p.exists() else (None, None)
        # `~/…`：状态源里写 `~/.tripo/config.json`；第一版正则把 `~/.` 吃掉、只剩 `tripo/config.json`
        # ⇒ 假红（真身其实在用户目录）。这里显式展开。
        if rel_or_abs.startswith("~"):
            p = Path(rel_or_abs.replace("~", str(Path.home()), 1))
            return (p, "~ 展开") if p.exists() else (None, None)
        for b in BASES:
            p = b / rel_or_abs
            if p.exists():
                return p, str(b)
        return None, None

    missing, present = [], []
    for key, info in sorted(refs.items()):
        p, which = resolve(info["abs"] or key)
        row = {"path": key, "resolved": str(p) if p else None, "base": which, "refs": info["refs"][:3]}
        if p is None:
            missing.append(row)
        else:
            row["bytes"] = p.stat().st_size if p.is_file() else None
            present.append(row)

    # 大小声明：只在**同一条字符串里只有一个文件引用**时才敢配对（否则不知道那个 MB 说的是哪个文件）
    size_checks, size_warn = [], []
    for path, text in strings:
        files = [m.group(1).replace("\\", "/") for m in REL_RE.finditer(text)]
        files += [m.group(1).rstrip("\\/") for m in ABS_RE.finditer(text)]
        if len(files) != 1:
            continue
        target = Path(files[0]) if re.match(r"^[A-Za-z]:", files[0]) else base / files[0]
        if not target.is_file():
            continue
        actual = target.stat().st_size
        for m in SIZE_RE.finditer(text):
            if m.group(1):
                claimed = int(m.group(1).replace(",", ""))
            else:
                val, unit = float(m.group(2)), m.group(3).upper()
                claimed = int(val * {"KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3}[unit])
            row = {"ref": files[0], "field": path, "claimed": claimed, "actual": actual,
                   "delta_pct": round((actual - claimed) / claimed * 100, 2) if claimed else None}
            (size_checks if claimed and abs(actual - claimed) / claimed <= 0.05 else size_warn).append(row)

    print("=" * 84)
    print("数字人状态源读数审计 · %s" % shown)
    print("=" * 84)
    print("引用到的文件：%d 个（在盘 %d · **不在盘 %d**）" % (len(refs), len(present), len(missing)))
    for r in present:
        print("   ✅ %-58s %s B  ← %s" % (r["path"][:58], r["bytes"] if r["bytes"] is not None else "（目录）", r["base"]))
    for r in missing:
        print("   🔴 不在盘 %-50s ← %s" % (r["path"][:50], "、".join(r["refs"][:2])))
    print("大小声明：对得上 %d 条 · 对不上 %d 条（±5%% 容差；对不上的多半是四舍五入，故只警告）"
          % (len(size_checks), len(size_warn)))
    for r in size_warn:
        print("   ⚠ %s：声明 %s B，实际 %s B（差 %s%%）"
              % (r["ref"], r["claimed"], r["actual"], r["delta_pct"]))

    if no_receipt:
        print("（--no-receipt：跳过回执落盘 —— 负控/试跑不留痕，别把真回执盖成试跑结果）")
    else:
        OUT.write_text(json.dumps({"at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
                                   "status_file": shown,
                                   "referenced": sorted(refs.keys()), "present": present,
                                   "missing": missing, "size_ok": size_checks, "size_warn": size_warn},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
        print("回执 → %s" % OUT.relative_to(ROOT))
    print("-" * 84)
    if missing and strict:
        print("结论：**有 %d 个被引用的文件不在盘上**（--strict 下算硬失败）。" % len(missing))
        return 1
    print("结论：引用文件 %s · 大小声明 %s（%s）"
          % ("全在盘" if not missing else "%d 个不在盘" % len(missing),
             "都对得上" if not size_warn else "%d 条对不上" % len(size_warn),
             "已加 --strict：文件不在就判红" if strict else "未加 --strict：缺失只报告，加 --strict 才判红"))
    return 0


if __name__ == "__main__":
    if "--negctl" in sys.argv[1:]:
        raise SystemExit(negctl())
    raise SystemExit(main(sys.argv[1:]))
