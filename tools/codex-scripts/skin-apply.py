# -*- coding: utf-8 -*-
"""皮肤重装器 —— 读落盘备份，吐出**可直接提交给 `cordis_define` 的载荷**。

## 为什么需要它

动态 Cordis 插件**只活在当前进程里**（官方口径：`definitions do not survive a process restart`）。
⇒ 皮肤重启即失，而"照着备份再手写一遍 JS"正是**手抄容易抄错**的地方（本仓栽过多次）。
本器把那一步变成**一条命令**：读 `xianxia-tech-tokens.json` → 吐 `code.client` 全文。

## 它**不做**什么

- **不联网、不写盘、不调任何 Cordis API** —— 只读备份、只打印。
- **不自己定义/激活插件**：`cordis_define` / `cordis_run` 是 Agent 的工具，不是本器的活。
  （激活客户端包须主人批准 —— 本器**不代批**。）

## 跑法

    py -3.14 tools/codex-scripts/skin-apply.py            # 用备份里的 ACTIVE
    py -3.14 tools/codex-scripts/skin-apply.py B          # 临时换 B 档预览载荷
    py -3.14 tools/codex-scripts/skin-apply.py A --json   # 连 name/purpose/idPrefix 一起给
"""

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
BAK = ROOT / "projects" / "_shared" / "brand" / "skin" / "xianxia-tech-tokens.json"
SOURCE = "gbt-xianxia-tech-skin"

HEAD = """// 仙侠 × 科技 · 对话页皮肤（GBT小土豆V8）
//
// ⚠️ 本件由 `tools/codex-scripts/skin-apply.py` 从
//    `projects/_shared/brand/skin/xianxia-tech-tokens.json` **生成** ——
//    要改配色**改那份 JSON**，不要改这里（改了下次重装就丢）。
//
// 走官方主题令牌路（`theme.overrideTokens`），不碰 DOM、不碰布局、不改源码：
//   服务原文：「token 级的分层 —— 基座主题分毫不动，层按序叠加、后来者按 token 胜出，
//             移除一层就还原它盖住的那些」；返回 disposer。
// ⇒ 停 / 改 / 卸都干净回退。
const ACTIVE = '%s'   // 备份里的当前档
const SOURCE = '%s'

const PALETTES = %s

return {
  apply(ctx) {
    const theme = ctx.get('theme')
    if (theme === undefined) return
    const tokens = PALETTES[ACTIVE] || PALETTES.A
    ctx.effect(() => theme.overrideTokens(SOURCE, tokens))
  },
}
"""


def main() -> int:
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("palette", nargs="?", default="")
    ap.add_argument("--json", action="store_true")
    a, _unknown = ap.parse_known_args()

    if not BAK.exists():
        print("❌ 备份不在盘上：%s" % BAK.relative_to(ROOT).as_posix())
        print("   本器**不猜配色** —— 没有备份就没有皮肤。")
        return 1
    d = json.loads(BAK.read_text(encoding="utf-8"))
    pal = d.get("palettes") or {}
    active = (a.palette or d.get("ACTIVE") or "A").strip().upper()
    if active not in pal:
        print("❌ 备份里没有这一档 %r（有：%s）" % (active, "、".join(sorted(pal))))
        return 1

    # 只取 `--dsw-*` 令牌，且**只认带 light+dark 两项的** —— 缺一项就拒，不替它补
    bad = []
    clean = {}
    for k, v in pal.items():
        toks = {t: x for t, x in v.items() if str(t).startswith("--dsw-")}
        if not toks:
            continue
        for t, modes in toks.items():
            if not (isinstance(modes, dict) and set(modes) == {"light", "dark"}):
                bad.append("%s / %s" % (k, t))
        clean[k] = toks
    if bad:
        print("❌ 这些令牌没有齐 light+dark，**不许上线**（服务会在边界抛错）：")
        for x in bad[:8]:
            print("     ", x)
        return 1
    n_tok = len(clean[active])
    js = HEAD % (active, SOURCE, json.dumps(clean, ensure_ascii=False, indent=2))

    print("=" * 74)
    print("皮肤载荷（档 %s · %s）" % (active, pal[active].get("名", "")))
    print("=" * 74)
    print("  令牌 %d 个 · 每个都有 light+dark · 来源 %s"
          % (n_tok, BAK.relative_to(ROOT).as_posix()))
    print("  ⚠️ 本器只**打印**：`cordis_define` / `cordis_run` 由 Agent 做，激活须主人批准。")
    print("-" * 74)
    if a.json:
        print(json.dumps({"name": "仙侠×科技 · 对话页皮肤（%s）" % pal[active].get("名", active),
                          "purpose": "用官方 theme.overrideTokens 给对话页叠一层仙侠×科技配色"
                                     "（%d 个令牌 × 亮/暗两套），可停可卸、随时还原，不改源码不碰 DOM。"
                                     % n_tok,
                          "idPrefix": "xian", "code": {"client": js}},
                         ensure_ascii=False, indent=2))
    else:
        print(js)
    return 0


if __name__ == "__main__":
    sys.exit(main())
