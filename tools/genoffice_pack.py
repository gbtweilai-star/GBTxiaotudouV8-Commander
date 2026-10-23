"""GenOffice 蒸馏版 · 打包（一次性脚本 · 可重复运行）。

口径：**发布件不是第二份源** —— 包里放的是**快照 + 清单（含源路径与 sha256）**，
真源永远是仓内那几份；这样既能交付，又不会长出"分叉的第二份代码"。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import time
import zipfile

ROOT = pathlib.Path(r"C:\Users\ADMIN\Desktop\GBT小土豆V8")
NAME = "genoffice-distill-" + time.strftime("%Y%m%d")
OUT = ROOT / "dist" / NAME
CANON = [
    "skills/gbt-genoffice/SKILL.md",
    "gbt_allinone/tools/genoffice_cap.py",
]


def sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


INSTALL = """# GenOffice 蒸馏版 · 安装与接线（一页）

> 本包是**发布快照**；真源在仓内（`skills/gbt-genoffice/SKILL.md` 与 `gbt_allinone/tools/genoffice_cap.py`），
> 清单 `manifest.json` 记了源路径与 sha256，可随时核对"这份快照对应源上的哪一版"。

## 一、装它（只要 CLI，不要它的应用进程）
1. 装 GenOffice 桌面本体（genoffice.ai）⇒ 得到 CLI：
   `%LOCALAPPDATA%\\Programs\\GenOffice\\resources\\cli\\genoffice.cmd`
2. 若 CLI 在别处：把它的目录写进 `~/.genoffice/launcher`（一行路径），我们的 `_cli()` 会先读它。

## 二、接它（万能插主控）
框架已含 `genoffice` 能力位（注册表 ↔ api.py 路由 ↔ 处理器 ↔ 技能，四处互锁）。调用：

```python
import gbt_allinone as g
g.run_task("genoffice", {"op": "status"})                          # 体检
g.run_task("genoffice", {"op": "ops"})                             # 自述能力面
g.run_task("genoffice", {"op": "info", "args": ["<文件>"]})         # 读类：直连
g.run_task("genoffice", {"op": "render", "args": ["<文件>"]})       # 写类：过 filesystem_write 门
```

技能装到枢纽：`python tools/skills_sync.py sync`（源↔装由哈希锁保证一致）。

## 三、两条门（都是主人定的，一条命令可开）
| 门 | 何时撞上 | 开法 |
|---|---|---|
| `filesystem_write` | 一切写类（create/convert/merge/render/slides/sheet/docs 的写子命令） | `python -m gbt_allinone auth grant --scope filesystem_write --ttl 600` |
| 控制端开关 | `open`/`selection`/`mcp`/`install-cli`/`skill`（默认不在主控面上） | 调用时带 `allow_control_endpoint: true`；放行写入 `state/genoffice_control.jsonl` 留痕 |

## 四、自检（装完跑这三条）
1. `{"op":"status"}` ⇒ 应看到 `genoffice 0.10.1467` 与"蒸馏口径"三行；
2. `{"op":"info","args":["<任一 pdf>"]}` ⇒ `ok=true · exit=0 · N pages`；
3. `{"op":"render","args":["<任一 pdf>"]}` ⇒ 未授权时应 `denied=true` 并给出授权命令（**这是正确行为**）。
"""

DEMO = '''"""最小示例（不需要写权限）：体检 + 自述 + 真读一个 PDF。"""
import sys
sys.path.insert(0, r"<仓根>")
import gbt_allinone as g

for payload in ({"op": "status"}, {"op": "ops"}):
    print(g.run_task("genoffice", payload).get("result"))
print(g.run_task("genoffice", {"op": "info", "args": [r"<某个 pdf 路径>"]}).get("result"))
'''


def main() -> int:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "INSTALL.md").write_text(INSTALL, encoding="utf-8")
    (OUT / "demo.py").write_text(DEMO, encoding="utf-8")
    man = {"package": NAME, "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "口径": "发布快照（非第二份源）：真源路径与哈希记在下面，可核对",
           "snapshot": [], "canonical": [], "engine": {"cli": "genoffice 0.10.1467",
                                                       "接入": "本地引擎 10 项 + 免费AI 3 项",
                                                       "控制端类": "默认不接 · 点名放行 · 留痕"}}
    for rel in CANON:
        src = ROOT / rel
        dst = OUT / pathlib.Path(rel).name
        shutil.copy2(src, dst)
        man["canonical"].append({"path": rel, "sha256_16": sha(src), "bytes": src.stat().st_size})
        man["snapshot"].append(dst.name)
    (OUT / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    zpath = OUT.with_suffix(".zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(OUT.rglob("*")):
            z.write(f, f.relative_to(OUT.parent))
    print(f"包已出：{zpath}（{zpath.stat().st_size/1024:.0f} KB）")
    print("清单：", json.dumps(man["canonical"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
