# -*- coding: utf-8 -*-
# gbt-capability: filesystem_write  ⬻ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""主题渲染器（theme-render）—— 一份色源，重生成所有界面的主题块。

蒸馏来源：Omarchy 的「`colors.toml` 主色 + 模板重生成全系统配置」。
**只借思想**：它的模板是 `~/.config/omarchy/themed/*.tpl`，我们的模板是四个界面
文件里的**标记块**（`/* GBT-THEME-BEGIN */` … `/* GBT-THEME-END */`）。

三条纪律（写死）：
  ① **块外一字不动**：没有标记块的文件**跳过并报出来**（不猜、不整文件重写）；
  ② **不许假绿**：模板引用了色源里没有的 token ⇒ 报错，不静默留空；
  ③ **默认不落盘**：无参 = 预览（只打印不写）；`--apply` 才写；`--check` 只报漂移。

用法：
  py -3.14 tools/theme-render.py list
  py -3.14 tools/theme-render.py show --palette default
  py -3.14 tools/theme-render.py                 # 预览（不写盘）
  py -3.14 tools/theme-render.py --check         # 漂移检查（改了色源没重生成 ⇒ 非零）
  py -3.14 tools/theme-render.py --apply         # 真写（原子写 + `.bak` 留一份）
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 🔴 2026-10-15 修（真 bug · 实测咬到）：
#    `--apply` **文件已经写完并落了 .bak**，但最后那行 print 里的 `⇒`（\u21d2）
#    在 Windows GBK 控制台抛 UnicodeEncodeError ⇒ **整个进程 rc=1**
#    ⇒ 在自动化里会被误判成「渲染失败」，而其实已经成功 —— 这是最坏的一种假报。
#    改法：把 stdout/stderr 都钉成 utf-8（拿不到就退 errors="replace"，绝不因打印崩）。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PALETTES_DIR = ROOT / "state" / "theme" / "palettes"
# 模板**独立成件**（不再从 `.bak` 取）—— 否则旧备份会变成真源，正是“旧件混乱”。
TEMPLATES_DIR = ROOT / "state" / "theme" / "templates"
TARGETS = (
    "holo_pet/styles.css",
    "holo_pet_w3/window.css",
    "holo_pet_w3/deck3d.css",
    "holo_pet_w3/skin-mission-control.css",
)

TOKEN = re.compile(r"@@([A-Za-z0-9_]+)@@")
# 定义不一定占整行（`--mc-1: 4px;  --mc-2: 8px;` 同行多个）⇒ 不锚行首
DEF = re.compile(r"(--[A-Za-z0-9_-]+)\s*:")
# 捕获组：1=变量名，2=是否带兜底（`var(--x, ...)`）
USE = re.compile(r"var\(\s*(--[A-Za-z0-9_-]+)\s*(,?)")
# 运行时定义：这类变量不写在 `:root` 里，而是由 JS 在元素上 setProperty 写入
#   （例：`--z` 由滚动侧写）⇒ 不能当“未定义”报错，但要点名出来。
RUNTIME_DEFS = frozenset(("--z", "--drift", "--gbt3d-float", "--gbt3d-lift", "--scroll-y", "--p"))
# 可见性：同一个页面里一起加载的文件 ⇒ 变量可互用（不能当悬空）。
VISIBILITY = {
    "holo_pet_w3/skin-mission-control.css": ("holo_pet_w3/window.css", "holo_pet_w3/deck3d.css"),
    "holo_pet_w3/window.css": ("holo_pet_w3/skin-mission-control.css", "holo_pet_w3/deck3d.css"),
    "holo_pet_w3/deck3d.css": ("holo_pet_w3/window.css", "holo_pet_w3/skin-mission-control.css"),
}
BLOCK = re.compile(r"/\* GBT-THEME-BEGIN[^\n]*\*/\r?\n(.*?)\r?\n[ \t]*/\* GBT-THEME-END \*/", re.S)


def _toml_load(path: Path) -> dict:
    try:
        import tomllib
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except ModuleNotFoundError:                                     # pragma: no cover
        import json
        return json.loads(path.read_text(encoding="utf-8"))


def load_palette(name: str = "default"):
    """读一份色源 ⇒ (name, meta, values, colors, dims)。

    values = colors + dims 合并（模板只认一个名字空间）；
    拆开供判据用：“颜色渲染了没”和“尺寸渲染了没”是两件事。
    """
    p = PALETTES_DIR / ("%s.toml" % name)
    if not p.exists():
        p = PALETTES_DIR / ("%s.json" % name)
    if not p.exists():
        return None, None, None, None, None
    data = _toml_load(p)
    if p.stem != "default":
        # “只写差异”的备选色源：自己的 colors 是 default 的**真子集**（少于全部）
        #   才算“继承 + 覆盖”；否则它就是一份完整色源，不能拿 default 去覆盖它。
        #   （实测踩过：无条件合并会把 jade 的 gold 又改回 default 的）
        _n0, _m0, _v0, c0, d0 = load_palette("default")
        own = data.get("colors") or {}
        if own and set(k.lower() for k in own) < set((c0 or {}).keys()):
            merged = dict(c0 or {})
            merged.update(own)
            data["colors"] = merged
            if not (data.get("dims") or {}):
                data["dims"] = dict(d0 or {})
    # 取值空间 = colors + dims 合并 —— 模板里不区分“这是颜色还是尺寸”，
    #   只有一个名字。重名时 colors 优先（并在这里就能发现，不留到渲染时）。
    colors = {k.lower(): v for k, v in (data.get("colors") or {}).items()}
    dims = {k.lower(): v for k, v in (data.get("dims") or {}).items()}
    values = dict(dims)
    values.update(colors)          # 重名时 colors 优先
    return p.stem, (data.get("meta") or {}), values, colors, dims


def list_palettes() -> list:
    if not PALETTES_DIR.is_dir():
        return []
    out = []
    for f in sorted(PALETTES_DIR.iterdir()):
        if f.suffix in (".toml", ".json"):
            name, meta, _values, colors, dims = load_palette(f.stem)
            out.append({"name": name, "file": str(f), "colors": len(colors or {}),
                        "dims": len(dims or {}), "meta": meta or {}})
    return out


def _block_tokens(text: str) -> list:
    toks = []
    for m in BLOCK.finditer(text):
        toks.extend(TOKEN.findall(m.group(1)))
    return toks


def has_block(text: str) -> bool:
    return bool(BLOCK.search(text))


def render_block(template_block: str, colors: dict, meta: dict = None) -> str:
    """把模板块里的 @@token@@ 换成色值。缺 token ⇒ **抛错**（不许留空）。"""
    meta = meta or {}
    missing = []

    def sub(m):
        key = m.group(1).lower()
        if key in colors:
            return str(colors[key])
        if key in meta:
            return str(meta[key])
        missing.append(key)
        return m.group(0)

    out = TOKEN.sub(sub, template_block)
    if missing:
        raise KeyError("色源缺 token：%s" % ", ".join(sorted(set(missing))))
    return out


def _template_of(rel) -> str:
    """取该目标的**模板块**：优先读 `.bak`（含 @@token@@ 的原始模板），

    没有 `.bak` 就用文件里现在的块（第一次渲染前就是模板）。
    """
    tpl = TEMPLATES_DIR / (Path(rel).name + ".tpl")
    if tpl.exists():
        return tpl.read_text(encoding="utf-8").strip("\n")
    # 模板没建的目标：退回读文件里现有的块（首次接入时就是模板）
    p = Path(rel) if Path(rel).is_absolute() else (ROOT / rel)
    if p.exists():
        m = BLOCK.search(p.read_text(encoding="utf-8"))
        if m:
            return m.group(1)
    return ""


def orphan_vars(text: str, blocks_text: str = None, visible_text: str = "") -> dict:
    """漂移守卫：主题块**之外**的 CSS 规则引用了未定义的变量 ⇒ 报出来。

    为什么要这道：旧 `:root` 块被末尾主题块覆盖后，文件里会**同名变量定义两次**；
    将来清理时一旦删错一行，引用就会悬空。这道闸把那种“删完才发现样式塔了”变成可机检。
    """
    defs = set(DEF.findall(text)) | set(DEF.findall(blocks_text or ""))
    defs |= set(DEF.findall(visible_text or ""))
    pre = text
    m = BLOCK.search(text)
    if m:
        pre = text[:m.start()] + text[m.end():]
    orphans, fallback_only, runtime = set(), set(), set()
    for name, comma in USE.findall(pre):
        if name in defs:
            continue
        if name in RUNTIME_DEFS:          # JS 运行时写入 ⇒ 不是未定义
            runtime.add(name)
            continue
        (fallback_only if comma else orphans).add(name)
    return {"ok": not orphans,
            "orphans": sorted(orphans),          # 无定义、无兜底 ⇒ 真悬空
            "fallback_only": sorted(fallback_only),  # 无定义但有兜底 ⇒ 能跑，但不该长期靠兜底
            "runtime": sorted(runtime),
            "defined": len(defs), "used_outside": len({x[0] for x in USE.findall(pre)})}


def build_template(target_text: str, colors: dict, meta: dict = None,
                   template: str = None) -> str:
    """重生成整份文件内容。

    模板优先用**独立模板件**（传入 `template`）；传不到才退回文件里现有的块。
    为什么要分开：一旦渲染过，文件里的块就没有 `@@token@@` 了 ——
    拿它当模板就永远不会再变（实测踩过：新加的 `--gbt-mono` 怎么跑都不进文件）。
    """
    m = BLOCK.search(target_text)
    if not m:
        return target_text
    body = template if (template and "@@" in template) else m.group(1)
    new_block = render_block(body, colors, meta)
    return target_text[:m.start(1)] + new_block + target_text[m.end(1):]


def scan(colors: dict, meta: dict = None, paths=None) -> dict:
    """只读扫描：逐个目标看**有没有标记块 / 块内 token 能不能全解析**。"""
    files, skipped, errors, notes = [], [], [], []
    for rel in (paths or TARGETS):
        p = (ROOT / rel) if not Path(rel).is_absolute() else Path(rel)
        if not p.exists():
            skipped.append({"file": rel, "why": "不存在"})
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            skipped.append({"file": rel, "why": "读不动：%s" % type(exc).__name__})
            continue
        if not has_block(text):
            skipped.append({"file": rel, "why": "没有 GBT-THEME 标记块"})
            continue
        vis = "\n".join((ROOT / v).read_text(encoding="utf-8")
                         for v in VISIBILITY.get(rel, ()) if (ROOT / v).exists())
        orph = orphan_vars(text, _template_of(rel), vis)
        if not orph["ok"]:
            errors.append({"file": rel, "error": "引用了**无定义且无兜底**的变量：%s"
                                             % ", ".join(orph["orphans"][:8])})
        if orph["fallback_only"]:
            notes.append({"file": rel, "note": "靠兜底跑的变量（能跑但不该长期靠）：%s"
                                        % ", ".join(orph["fallback_only"][:8])})
        tmpl = _template_of(rel)
        try:
            block = render_block(tmpl, colors, meta)
        except KeyError as exc:
            errors.append({"file": rel, "error": str(exc)})
            block = ""
        # 报**变量数**：渲染前看模板里的 token，渲染后看落地的 CSS 变量
        n_vars = len(TOKEN.findall(tmpl)) or len(re.findall(r"--[A-Za-z0-9_-]+\s*:", block))
        files.append({"file": rel, "vars": n_vars, "tokens": sorted(set(TOKEN.findall(tmpl))),
                      "bytes": len(text)})
    return {"ok": not errors, "files": files, "skipped": skipped, "errors": errors, "notes": notes}


def drift(colors: dict, meta: dict = None, paths=None) -> dict:
    """漂移：文件里**已渲染**的主题块与色源现在该给的值不一致 ⇒ 有人改了色源没重生成。"""
    out = []
    for rel in (paths or TARGETS):
        p = (ROOT / rel) if not Path(rel).is_absolute() else Path(rel)
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        if not has_block(text):
            continue
        want = build_template(text, colors, meta, _template_of(rel))
        if want != text:
            out.append({"file": rel, "reason": "主题块与色源/模板不一致"})
    return {"ok": not out, "drifted": out}


def apply(colors: dict, meta: dict = None, paths=None, backup: bool = True) -> dict:
    written = []
    for rel in (paths or TARGETS):
        p = (ROOT / rel) if not Path(rel).is_absolute() else Path(rel)
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        if not has_block(text):
            continue
        want = build_template(text, colors, meta, _template_of(rel))
        if want == text:
            continue
        if backup:
            p.with_suffix(p.suffix + ".bak").write_text(text, encoding="utf-8")
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(want, encoding="utf-8")
        tmp.replace(p)
        written.append({"file": rel, "before": len(text), "after": len(want)})
    return {"ok": True, "written": written}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GBT 主题渲染器（单一色源 ⇒ 界面主题块）")
    ap.add_argument("cmd", nargs="?", default="preview",
                    choices=["preview", "list", "show", "check", "apply"])
    ap.add_argument("--palette", default="default")
    ap.add_argument("--outdir", default="",
                    help="预览落点：传了就把渲染结果写到该目录（**不碰原文件**）")
    ap.add_argument("--apply", action="store_true", help="真写盘（默认只预览）")
    ap.add_argument("--check", action="store_true", help="只报漂移（等价于 check 子命令）；非零 = 改了色源没重生成")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args(argv)
    if args.check:
        args.cmd = "check"

    if args.cmd == "list":
        rows = list_palettes()
        if not rows:
            print("未读到任何色源：%s" % PALETTES_DIR)
            return 1
        for r in rows:
            print("%-16s 颜色 %-3d 尺寸 %-3d  %s"
                  % (r["name"], r["colors"], r["dims"], (r["meta"] or {}).get("name", "")))
        return 0

    name, meta, colors, _colors, _dims = load_palette(args.palette)
    if colors is None:
        print("色源不存在：%s（先跑 list 看有哪些）" % args.palette)
        return 2
    if args.cmd == "show":
        print("# %s · %s（共 %d 个取值空间条目：colors + dims）"
              % (name, (meta or {}).get("name", ""), len(colors)))
        for k in sorted(colors):
            print("  %-18s %s" % (k, colors[k]))
        return 0

    if args.cmd == "check":
        d = drift(colors, meta)
        s = scan(colors, meta)
        for x in s["files"]:
            print("OK   %s（主题变量 %d 个已与色源一致）" % (x["file"], x["vars"]))
        for x in s["skipped"]:
            print("跳过 %s —— %s" % (x["file"], x["why"]))
        for x in s["notes"]:
            print("提示 %s —— %s" % (x["file"], x["note"]))
        for x in s["errors"]:
            print("错误 %s —— %s" % (x["file"], x["error"]))
        for x in d["drifted"]:
            print("漂移 %s —— %s" % (x["file"], x["reason"]))
        ok = d["ok"] and s["ok"]
        print("判据 %s（漂移 %d · 错误 %d）"
              % ("PASS" if ok else "FAIL", len(d["drifted"]), len(s["errors"])))
        return 0 if ok else 1

    if args.cmd == "apply" or args.apply:
        res = apply(colors, meta, backup=not args.no_backup)
        for x in res["written"]:
            print("已重生成 %s（%d ⇒ %d 字节）" % (x["file"], x["before"], x["after"]))
        if not res["written"]:
            print("无需重生成：主题块已与色源一致")
        return 0

    if args.outdir:
        out = Path(args.outdir)
        out.mkdir(parents=True, exist_ok=True)
        rows = []
        for rel in TARGETS:
            p = ROOT / rel
            if not p.exists():
                continue
            text = p.read_text(encoding="utf-8")
            if not has_block(text):
                continue
            dst = out / Path(rel).name
            dst.write_text(build_template(text, colors, meta, _template_of(rel)), encoding="utf-8")
            rows.append({"file": str(dst), "bytes": dst.stat().st_size})
        print("预览落点：%s（**原文件一字未动**）" % out)
        for x in rows:
            print("  %-28s %d 字节" % (Path(x["file"]).name, x["bytes"]))
        print("要真写原件请用 --apply")
        return 0
    s = scan(colors, meta)
    print("预览（**不写盘**）· 色源 %s" % name)
    for x in s["files"]:
        print("  将渲染 %s（%d token）" % (x["file"], len(x["tokens"])))
    for x in s["skipped"]:
        print("  跳过 %s —— %s" % (x["file"], x["why"]))
    for x in s["errors"]:
        print("  错误 %s —— %s" % (x["file"], x["error"]))
    for x in drift(colors, meta)["drifted"]:
        print("  漂移 %s —— %s" % (x["file"], x["reason"]))
    print("要真写请加 --apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
