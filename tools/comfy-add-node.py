# -*- coding: utf-8 -*-
"""补节点脚手架（comfy-add-node）：一个能力位式的**生成器**，不是手写。

## 为什么要有

按清单补节点时，每个节点都是同一套形态：`def _n_<Name>(inputs, ctx)` + `NODES` 注册行。
手写 15 个能忍，补 800 个不能忍——而且手抄最容易出错（少一个 `?`、少一个 `writes`）。

本工具按**族模板**生成骨架，落到独立模块 `gbt_allinone/tools/comfy_nodes_extra.py`，
由 `comfy_native` 在 import 时合并进 `NODES`：
**不往主模块里追加代码**（主模块已经很大，自动追加是维护灾难）。

## 三族模板

| 族 | 输入 | 适用 |
|---|---|---|
| `image` | `image` + `out` + 参数 | 取源图 → 处理 → 落盘（writes=True） |
| `mask`  | `mask` + `out` + 参数 | 取遮罩 → 处理 → 落盘（writes=True） |
| `passthrough` | 任意值 | 只透传/只读数（writes=False） |

## 用法

```powershell
py -3 -X utf8 tools/comfy-add-node.py --name ImageFlipX --family image --apply
py -3 -X utf8 tools/comfy-add-node.py --name ImageFlipX --family image --dry-run   # 只看生成什么
```

生成后**必须**跑一次冒烟（工具会打印建议命令）；函数体里留 `TODO` 的实现要人填。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRA = os.path.join(ROOT, "gbt_allinone", "tools", "comfy_nodes_extra.py")

TEMPLATES = {
    "image": '''

def _n_{name}(inputs: dict, ctx: dict) -> dict:
    """{desc}"""
    import pathlib
    from PIL import Image
    src = inputs.get("image") or inputs.get("path")
    if not src:
        return {{"ok": False, "error": "user_error: 要 image"}}
    img = Image.open(str(src)).convert("RGBA")
    # TODO 实现：{name}（PIL 纯 CPU）
    out = _out_path(inputs, "{tag}")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return {{"ok": True, "out": out, "width": img.width, "height": img.height}}
''',
    "mask": '''

def _n_{name}(inputs: dict, ctx: dict) -> dict:
    """{desc}"""
    import pathlib
    from PIL import Image
    src = inputs.get("mask") or inputs.get("image")
    if not src:
        return {{"ok": False, "error": "user_error: 要 mask/image"}}
    im = Image.open(str(src))
    m = im.convert("L") if str(inputs.get("mask") or "") else im.convert("RGBA").split()[-1]
    # TODO 实现：{name}（遮罩处理）
    out = _out_path(inputs, "{tag}")
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    m.convert("RGBA").save(out)
    return {{"ok": True, "out": out}}
''',
    "passthrough": '''

def _n_{name}(inputs: dict, ctx: dict) -> dict:
    """{desc}"""
    val = inputs.get("value")
    # TODO 实现：{name}（只读/透传，不落盘）
    return {{"ok": True, "value": val}}
''',
}

REGISTER = '''
NODES["{name}"] = {{"fn": _n_{name}, "in": {ins}, "out": {outs}, "writes": {writes},
                   "desc": "{desc}（{family} 族脚手架生成 {at}）"}}
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="", help="节点名（ComfyUI 同名，驼峰）；批量模式可省")
    ap.add_argument("--family", choices=sorted(TEMPLATES), default="image")
    ap.add_argument("--desc", default="待补实现")
    ap.add_argument("--from-harvest", action="store_true",
                    help="批量：读 state/comfy-harvest.json 的 useful_list，生成**待审**骨架文件")
    ap.add_argument("--harvest", default="state/comfy-harvest.json")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    # ── 批量模式：只生成**待审文件**，不直接进 extras ──
    # 为什么不当场追加：骨架里的函数体是 TODO，追加进 extras 会变成"能跑但做错事"的节点
    # （image 族会原样落盘、mask 族会原样输出）——那是最坏的一种假绿。
    if args.from_harvest:
        hp = args.harvest if os.path.isabs(args.harvest) else os.path.join(ROOT, args.harvest)
        if not os.path.exists(hp):
            print("没有 harvest 清单：", hp, "（先跑 comfy_native op=harvest）")
            return 1
        data = open(hp, encoding="utf-8").read()
        import json as _json
        try:
            harvest = _json.loads(data)
        except Exception as e:  # noqa: BLE001
            print("harvest 不是 JSON：", e)
            return 1
        names = harvest.get("useful_list") or []
        if not names:
            print("清单里没有要补的节点（useful_list 为空）")
            return 0
        ts = time.strftime("%Y%m%d-%H%M%S")
        stage = os.path.join(ROOT, "state", "tmp", "comfy-scaffold-%s.py" % ts)
        todo = os.path.join(ROOT, "state", "comfy-scaffold-%s.md" % ts)
        os.makedirs(os.path.dirname(stage), exist_ok=True)
        existing = open(EXTRA, encoding="utf-8").read() if os.path.exists(EXTRA) else ""
        parts, lines, skipped = [], ["# 待补节点（%d 个）" % len(names), ""], []
        for nm in names:
            nm = str(nm).strip()
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{2,40}", nm):
                skipped.append((nm, "名字不合法"))
                continue
            if ('NODES["%s"]' % nm) in existing:
                skipped.append((nm, "已注册"))
                continue
            fam = "mask" if "Mask" in nm else ("passthrough" if not any(
                h in nm for h in ("Image", "Scale", "Crop", "Blur", "Color")) else "image")
            part = TEMPLATES[fam].format(
                name=nm, tag=re.sub(r"[^a-z0-9]+", "", nm.lower())[:14] or "node",
                desc="待补实现（harvest 清单）") + REGISTER.format(
                name=nm, ins='["mask", "out"]' if fam == "mask" else '["image", "out"]',
                outs='["MASK"]' if fam == "mask" else '["IMAGE"]',
                writes="False" if fam == "passthrough" else "True",
                desc="待补实现（harvest 清单）", family=fam, at=time.strftime("%Y-%m-%d"))
            parts.append(part)
            lines.append("- [ ] `%s`（%s 族）" % (nm, fam))
        if not parts:
            print("没有可生成的（全部已注册或名字不合法）")
            return 0
        with open(stage, "w", encoding="utf-8") as fh:
            fh.write("# -*- coding: utf-8 -*-\n")
            fh.write("# 待审骨架（不要直接 import）：逐个填实现后再合并进 comfy_nodes_extra.py\n")
            fh.write("\n".join(parts))
        with open(todo, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n\n跳过：\n" +
                     "\n".join("- %s：%s" % (n, w) for n, w in skipped))
        print("== 批量生成（待审）==")
        print("生成骨架 %d 个 → %s" % (len(parts), stage))
        print("待办清单 →", todo)
        if skipped:
            print("跳过 %d 个：" % len(skipped), skipped[:5])
        print("注意：**没有**写进 comfy_nodes_extra.py —— 骨架是 TODO，直接进去会变成\"能跑但做错事\"的节点。")
        print("下一步：逐个填实现 → 追加进 extras → 跑 tests/test_comfy_engine.py")
        return 0

    if not args.name and not args.from_harvest:
        print("要么 --name <节点名>，要么 --from-harvest")
        return 2
    name = args.name.strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{2,40}", name):
        print("节点名不合法：", name)
        return 2
    if not (args.dry_run or args.apply):
        print("要么 --dry-run（只看），要么 --apply（落盘）")
        return 2

    tag = re.sub(r"[^a-z0-9]+", "", name.lower())[:14] or "node"
    fn = TEMPLATES[args.family].format(name=name, tag=tag, desc=args.desc)
    ins, outs, writes = {
        "image": ('["image", "out"]', '["IMAGE"]', "True"),
        "mask": ('["mask", "out"]', '["MASK"]', "True"),
        "passthrough": ('["value?"]', '["VALUE"]', "False"),
    }[args.family]
    reg = REGISTER.format(name=name, ins=ins, outs=outs, writes=writes,
                          desc=args.desc, family=args.family,
                          at=time.strftime("%Y-%m-%d"))
    snippet = fn + reg

    print("== 生成骨架 ==")
    print(snippet)
    if args.dry_run:
        print("（dry-run：没有落盘）")
        return 0

    if not os.path.exists(EXTRA):
        print("缺 %s —— 先建空模块（NODES = {}）" % EXTRA)
        return 1
    src = open(EXTRA, encoding="utf-8").read()
    if ('NODES["%s"]' % name) in src:
        print("已存在同名注册，拒绝覆盖：", name)
        return 1
    with open(EXTRA, "a", encoding="utf-8") as fh:
        fh.write(snippet)
    print("已追加到：", EXTRA)
    print("下一步：① 把 TODO 实现填上  ② 跑冒烟：")
    print("  py -3 -X utf8 -c \"import sys;sys.path.insert(0,'.');from gbt_allinone.tools import comfy_native as CN;"
          "print(len(CN.NODES)); print(CN.NODES.get('%s'))\"" % name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
