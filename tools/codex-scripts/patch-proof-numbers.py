# -*- coding: utf-8 -*-
"""fig-caps 的副标题/脚注 + README 里的旧读数 → 三路真跑新口径（CRLF 安全，逐处断言命中）。"""
import pathlib
import sys
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = pathlib.Path(__file__).resolve().parents[2]
REL = ROOT / "outputs" / "open-source-release"


def load(p):
    return p.read_text(encoding="utf-8").replace("\r\n", "\n")


def save(p, t):
    p.write_text(t, encoding="utf-8", newline="\n")


def sub(t, old, new, tag):
    if old not in t:
        print("!! 没命中：", tag)
        sys.exit(2)
    print("   命中：", tag)
    return t.replace(old, new, 1)


pf = ROOT / "tools" / "codex-scripts" / "render-test-figures.py"
t = load(pf)
t = sub(t,
        '    dd.text((28, 50), "规则：只读且无需参数 → 真调一次；需参数 → 不瞎编；写盘/花钱/出网 → 一律不跑（不越授权门）",',
        '    dd.text((28, 50), "三路真跑：只读空参真调 · 需参数带真参 · 写口隔离 store；要票的当场拒，高危 8 位不跑",',
        "fig-caps 副标题")
t = sub(t,
        '    footer(dd, w, h, "数据源：tools/codex-scripts/probe-caps-live.py 现跑（%s）" % d.get("at", ""))',
        '    footer(dd, w, h, "数据源：tools/codex-scripts/gen-capability-proof.py 合成三路真跑（%s）" % d.get("at", ""))',
        "fig-caps 脚注")
save(pf, t)

pr = REL / "README.md"
t = load(pr)
t = sub(t, "| 3 | **221 位只读能力逐位真调通过**（不是\"模型会背\"，是\"调得动\"） | [能力自证](docs/07-capability-proof.md) |",
        "| 3 | **286 位逐位真跑通过**（只读空参 / 需参数带真参 / 写口隔离 store），**失败 0** | [能力自证](docs/07-capability-proof.md) |",
        "README 亮点3")
t = sub(t, "| ![能力自证](assets/fig-caps.png) | **调得动** | 341 位：真调通过 **221** · 只读要票 15 · 需参数 26 · 写口未跑 79 |",
        "| ![能力自证](assets/fig-caps.png) | **调得动** | 341 位：真跑通过 **286** · 要票 32 · 缺输入 14 · 缺依赖 1 · 高危未跑 8 · **失败 0** |",
        "README 证据表")
t = sub(t, "**\"能不能调得动\"另有一套证据**：[07 能力自证](docs/07-capability-proof.md)（221 位逐位真调通过）。",
        "**\"能不能调得动\"另有一套证据**：[07 能力自证](docs/07-capability-proof.md)（341 位里 **286 位真跑通过**，失败 0）。",
        "README 评测节尾")
t = sub(t, "│   ├── 07-capability-proof.md ← 341 位逐位真调（221 位通过 / 15 位只读要票 / 79 位写口）",
        "│   ├── 07-capability-proof.md ← 341 位逐位真跑（286 通过 / 32 要票 / 14 缺输入 / 1 缺依赖 / 8 高危未跑）",
        "README 结构")
save(pr, t)
print("README 已更新")
