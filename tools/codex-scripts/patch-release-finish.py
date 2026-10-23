# -*- coding: utf-8 -*-
"""收尾三件小事：README 加 Release 徽章与链接 · CHANGELOG 补这一轮 · 07 加「自己复核」。
CRLF 安全；每处替换断言命中；可选处不命中只告警。"""
import pathlib
import sys
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

REL = pathlib.Path(__file__).resolve().parents[2] / "outputs" / "open-source-release"


def load(p):
    return p.read_text(encoding="utf-8").replace("\r\n", "\n")


def save(p, t):
    p.write_text(t, encoding="utf-8", newline="\n")


def sub(t, old, new, tag, required=True):
    if old not in t:
        print(("!! 没命中：" if required else "（可选未命中）") + tag)
        if required:
            sys.exit(2)
        return t
    print("   命中：", tag)
    return t.replace(old, new, 1)


# ── README：Release 徽章 + 发布行 ──
p = REL / "README.md"
t = load(p)
t = sub(t,
        '  <img alt="license" src="https://img.shields.io/badge/license-Apache--2.0-blue?style=flat-square">',
        '  <img alt="license" src="https://img.shields.io/badge/license-Apache--2.0-blue?style=flat-square">\n'
        '  <a href="https://github.com/gbtweilai-star/GBTxiaotudouV8-Commander/releases/latest">'
        '<img alt="release" src="https://img.shields.io/github/v/release/gbtweilai-star/GBTxiaotudouV8-Commander?style=flat-square"></a>',
        "Release 徽章")
t = sub(t,
        "**已公开且可复核**：能力位全量清单（341 位）",
        "**发布**：本仓库有可引用的 Release —— "
        "[`v83-commander-2026-10-21`](https://github.com/gbtweilai-star/GBTxiaotudouV8-Commander/releases/tag/v83-commander-2026-10-21)"
        "（含本版读数与已知限制）。\n\n**已公开且可复核**：能力位全量清单（341 位）",
        "README 发布行")
save(p, t)

# ── CHANGELOG：补这一轮 ──
p = REL / "CHANGELOG.md"
t = load(p)
t = sub(t, "## 2026-10-21 · 第二批公开（GBT天真 / 五维合一 / 多域监控）",
        """## 2026-10-21 · 第三批：能力自证从「221 通过 / 79 未跑」到「297 通过 / 失败 0」

### 修复（这一批都是真 bug，不是文案）
- **内网护栏名不符实**：`policy.py` 的 `add()` 只认 `HUMAN_GATES`，而 `osint_scan` 声明 `osint_private`、表里写
  `network_private`；`auth_gate.ENFORCED_SCOPES` 同病 ⇒ 内网扫描不打票就能跑（实测 `127.0.0.1 → ok`）。
  两处补 `osint_private` 后实测 `denied · missing=['osint_private']`。**一条修复让 4 条红了很久的测试同时转绿。**

### 证明（三路真跑，341 位一位一行）
- 只读位空参真调（90s 超时口径）· 需参数位**带人写样本参数**真跑 · 写口位**隔离 store**真跑
- 主人发票后又真跑 21 位（11 位转绿）：`autopilot` `think_loop` `sec_llm` `codex_chat` `devour_github`
  `tentacle` `codex_models` `codex_thread_new` `devour_pulse` `bluetooth` `vision`
- **终账：297 通过 / 要票 12 / 缺输入 23 / 缺依赖 1 / 高危未跑 8 / 失败 0**
- 12 位要票的是生产写入与隐私载体（mirror_* · pipeline_submit · keylogger 等）——**被门挡住是设计**

### 工具（都在 `tools/codex-scripts/`）
`probe-caps-params.py` · `probe-caps-params-fix4.py` · `probe-caps-write.py` · `probe-with-tickets.py` ·
`gen-capability-proof.py`（分桶合计 ≠ 341 直接退出）

## 2026-10-21 · 第二批公开（GBT天真 / 五维合一 / 多域监控）""",
        "CHANGELOG 第三批")
save(p, t)

# ── 07：加「自己复核」 ──
p = REL / "docs" / "07-capability-proof.md"
t = load(p)
if "## 六、自己复核" not in t:
    t = t.rstrip() + """

## 六、自己复核（三条命令，不需要任何票）

```bash
# ① 只读位：空 payload 逐位真调（90s 超时；慢 ≠ 坏）
py -3.14 tools/codex-scripts/probe-caps-live.py --timeout 90

# ② 需参数位：带**人写样本参数**真跑（隔离 store；不自动猜参数）
py -3.12 tools/codex-scripts/probe-caps-params.py

# ③ 写口位：隔离 store 真跑（高危 8 位按名单跳过）
py -3.12 tools/codex-scripts/probe-caps-write.py

# ④ 合成一份账（分桶合计 ≠ 341 会直接退出，防止漏位）
py -3.12 tools/codex-scripts/gen-capability-proof.py
```

> 口径要点：**降级/拒绝/缺参都如实入账**；`信封 status=ok` 但本体 `ok=false` 不算通过；
> 要票的位只有主人发票后才会转绿（`probe-with-tickets.py`），票用完即销的位不重复消费。
"""
save(p, t)
print("三件收尾完成")
