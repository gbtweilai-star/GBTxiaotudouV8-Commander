# -*- coding: utf-8 -*-
"""把开源发布包成形进镜像维度，让 mirror_scan / mirror_simulate 有实物可验。

为什么需要这个脚本（2026-11-04）：
    `store/` 被 .gitignore，clone 下来的 `store/mirror_space/dimension` 是空的。
    于是镜像的五个只读位 mirro_plan / simulate / parity / rehearse / release
    虽然 `status=ok`（调用通路通），业务上空转：`mirror_scan` 只过 3/5
    （non_empty、entry_point 挂），`mirror_simulate` 6/9。
    「调用成功 ≠ 维度已成形」——本脚本把发布清单真正 shape 进去。

成形后必须满足 scan 五项（这是晋升前置条件，不达标就该红）：
    ① 非空  ② 无 0 字节文件  ③ 文本页（.md/.html/.txt）带开发者署名
    ④ 无 _*.py / *.tmp / __pycache__ 残留  ⑤ 有入口（index.html/main.py/app.py/start.ps1）

用法：
    py -3.12 -X utf8 tools/codex-scripts/seed-mirror-dimension.py            # 成形 + 体检
    py -3.12 -X utf8 tools/codex-scripts/seed-mirror-dimension.py --dry-run  # 只列清单
"""
from __future__ import annotations

import json
import pathlib
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from gbt_allinone import mirror_space as MS  # noqa: E402

ENTRY_NAME = "main.py"
ENTRY_CONTENT = '''#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GBT小土豆V8 开源发布包 · 镜像维度入口。

本文件由 tools/codex-scripts/seed-mirror-dimension.py 生成，只为让镜像维度
具备一个可被 mirror_scan 认到的入口（index.html / main.py / app.py / start.ps1）。

真正的生产入口不是这里，而是单一门：
    from gbt_allinone.api import run_task
    run_task(kind, payload)          # 授权 · 审计 · 钢印 都在这一处

开发者：自由的风
"""
from __future__ import annotations

import sys


def main() -> int:
    sys.path.insert(0, ".")
    from gbt_allinone.api import run_task

    r = run_task("health", {})
    body = r.get("gbt_result", r) if isinstance(r, dict) else {}
    print("mirror entry ok:", body.get("status"), "· 能力位:", len(__import__("gbt_allinone").list_capabilities()))
    return 0 if body.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

# (维度内路径, 仓库内来源, 类型) —— 类型: text / binary / literal
MANIFEST = (
    (ENTRY_NAME, "gbt_allinone/api.py", "literal"),
    ("README.md", "README.md", "text"),
    ("docs/09-mirror-space.md", "docs/09-mirror-space.md", "text"),
    ("docs/03-capabilities.md", "docs/03-capabilities.md", "text"),
    ("CHANGELOG.md", "CHANGELOG.md", "text"),
    ("data/capabilities.json", "data/capabilities.json", "text"),
    ("data/capability-live-test.json", "data/capability-live-test.json", "text"),
    ("tools/codex-scripts/probe-caps-live.py", "tools/codex-scripts/probe-caps-live.py", "text"),
    ("tools/codex-scripts/render-social-preview.py", "tools/codex-scripts/render-social-preview.py", "text"),
    ("tools/codex-scripts/sync-readme-figures.py", "tools/codex-scripts/sync-readme-figures.py", "text"),
    ("assets/social-preview.png", "assets/social-preview.png", "binary"),
)


def main() -> int:
    dry = "--dry-run" in sys.argv[1:]
    print("镜像维度 ←", MS._DIM)
    ok_cnt = 0
    for dim_path, repo_path, kind in MANIFEST:
        src = ROOT / repo_path
        if kind == "literal":
            if dry:
                print(f"  [literal] {dim_path}  ({len(ENTRY_CONTENT)} chars)")
                ok_cnt += 1
                continue
            res = MS.shape(dim_path, ENTRY_CONTENT, "发布包入口")
        elif kind == "binary":
            if not src.is_file():
                print(f"  [skip] {dim_path} —— 仓库内缺 {repo_path}")
                continue
            if dry:
                print(f"  [binary] {dim_path}  ({src.stat().st_size} bytes)")
                ok_cnt += 1
                continue
            res = MS.shape_bytes(dim_path, src.read_bytes(), "首屏图")
        else:
            if not src.is_file():
                print(f"  [skip] {dim_path} —— 仓库内缺 {repo_path}")
                continue
            if dry:
                print(f"  [text] {dim_path}  ({src.stat().st_size} bytes)")
                ok_cnt += 1
                continue
            res = MS.shape(dim_path, src.read_text(encoding="utf-8"), "发布文档")
        if not res.get("ok"):
            raise SystemExit(f"成形失败 {dim_path}: {res.get('error')}")
        ok_cnt += 1

    if dry:
        print(f"[dry-run] 待成形 {ok_cnt} 个文件（未写入）")
        return 0

    tree = MS.dimension_tree()["stage"]
    print(f"维度内文件 {len(tree)} 个 · 合计 {sum(v['size'] for v in tree.values())} bytes")

    scan = MS.scan()
    print(f"体检 {scan['passed']}/{scan['total']} -> {'全绿' if scan['ok'] else '未通过'}")
    for name, c in scan["checks"].items():
        print(f"  {'✓' if c['ok'] else '✗'} {name}: {c['detail']}")
    return 0 if scan["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
