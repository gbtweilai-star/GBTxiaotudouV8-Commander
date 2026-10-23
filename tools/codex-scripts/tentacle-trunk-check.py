# -*- coding: utf-8 -*-
"""tentacle-trunk-check.py —— **触手主干判据**：每条能力必须长在触手上（缺一条腿 = 断连/缺失）。

主人令 2026-10-19（逐字）：「还有她的所有能力都要融合进触手，你没发现她的所有能力都是依仗触手而生吗
这样就不会出现缺失和断连」。

## 为什么要有这一条（和既有判据的分工）
仓里已有的判据各管一段：`binding_hook`（新增即过六腿）、`capability-bindings`（账）、
`tentacle_bind gaps`（资产漏绑）、`page-reach`（页面互通）。**但没有一条把它们合起来问**：
「这 336 位，每一位是不是**整根**长在触手上？」——于是可能出现"账上有、页上没有"、
"页上有、资产上没有"这种**半截连接**，任何人（包括我）都读不出来。
本件把六条腿压成一句人话的判据，并且**红就是红**（非零退出）。

## 六条腿（每一位都要，缺一即红）
  L1 登记：在 `caps_registry.BENIGN_CAPS` 里
  L2 派发：`api.py` 有它的分派（`kind == "x"` 或 `kind in (...)` 里含它）
  L3 承载：`state/cap-bindings.json` 台账里有它，且写着载体（触手承载/直连）
  L4 资产：`state/asset_bindings.json` 里至少一件资产绑到它（"手艺有落点"）
  L5 页面：`state/page-bindings.json` 里至少一页绑到它（"人点得到"）
  L6 记忆页：触手库（`state/obsidian_vaults.json`）里认得它（"她记得住"）

## 口径（不许含糊）
- **取不到 = 未验 = 红**（本仓铁律：取不到读数不许当通过）。每一腿都报"来源"。
- 只读：不写任何台账、不改注册表；缺了怎么补写在 `怎么补` 里，由人去补。
- `--json` 给机器读；默认给人读：先给总账，再逐条点名**断在哪一腿**。

用法：
    py -3.14 tools/codex-scripts/tentacle-trunk-check.py            # 人读
    py -3.14 tools/codex-scripts/tentacle-trunk-check.py --json     # 机器读
    py -3.14 tools/codex-scripts/tentacle-trunk-check.py --kind x   # 只看一条
退出码：0 全绿 · 1 有断连/缺失

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "state"
API = ROOT / "gbt_allinone" / "api.py"

TEST_HINT = {
    "L1": "补注册：gbt_allinone/caps_registry.py 的 BENIGN_CAPS 加一条",
    "L2": "补派发：gbt_allinone/api.py::_run_benign 加 if kind == \"…\" 分支",
    "L3": "重建账：py -3.14 tools/codex-scripts/capability-bindings.py",
    "L4": "绑资产：py -3.14 tools/tentacle_bind.py bind <资产> <kind>",
    "L5": "绑页面：py -3.14 tools/codex-scripts/page-bindings.py 后按它说的补 data-kind",
    "L6": "补记忆页：py -3.14 tools/binding_hook.py after-add --kind <kind>",
}


def _json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        return None


def _caps() -> dict:
    sys.path.insert(0, str(ROOT))
    from gbt_allinone.caps_registry import BENIGN_CAPS
    return dict(BENIGN_CAPS)


def _dispatch_kinds() -> set:
    """从 api.py 现读分派面：`kind == "x"` 与 `kind in ("a","b")` 两种写法都收。"""
    try:
        text = API.read_text(encoding="utf-8", errors="replace")
    except Exception:                                          # noqa: BLE001
        return set()
    out = set(re.findall(r'kind\s*==\s*"([A-Za-z0-9_]+)"', text))
    for grp in re.findall(r'kind\s+in\s+\(([^)]*)\)', text):
        out |= set(re.findall(r'"([A-Za-z0-9_]+)"', grp))
    return out


def _ledger_caps() -> dict:
    """cap-bindings 台账：{kind: row}。行里认 `carrier` / `binding` / `承载`。"""
    d = _json(STATE / "cap-bindings.json") or {}
    rows = d.get("caps") if isinstance(d, dict) else None
    if not isinstance(rows, list):
        return {}
    out = {}
    for r in rows:
        if isinstance(r, dict) and r.get("name"):
            out[str(r["name"])] = r
    return out


def _asset_bound() -> dict:
    """asset_bindings：{kind: [资产…]}（一条资产可绑多根触手）。"""
    d = _json(STATE / "asset_bindings.json") or {}
    out = {}
    if isinstance(d, dict):
        for path, meta in d.items():
            tens = (meta or {}).get("tentacles") or []
            for t in tens:
                out.setdefault(str(t), []).append(path)
    return out


def _page_bound() -> dict:
    """page-bindings：**真口径是 `逐页` 列表**（{at,页数,绑好,未绑好,逐页}），不是 page→kinds。

    🔴 2026-10-19 修（第一版判错了一次，P1 判据错尺）：我把这份账当成 `{页: [kind…]}` 读，
       而它实际是 `{"页数":40,"逐页":[…]}` ⇒ L5 恒为 0，337 位全被判"缺页腿" —— **假红**。
       现在按真结构读：`逐页` 里每项取 `kinds` / `caps` / `能力位` 三个可能字段名。
    """
    d = _json(STATE / "page-bindings.json")
    out = {}
    if not isinstance(d, dict):
        return out
    rows = d.get("逐页") or []
    if isinstance(rows, dict):
        rows = [{"page": k, **(v if isinstance(v, dict) else {})} for k, v in rows.items()]
    for r in rows:
        if not isinstance(r, dict):
            continue
        page = r.get("页") or r.get("page") or r.get("path") or ""
        kinds = r.get("正向_能力位") or r.get("kinds") or r.get("caps") or r.get("能力位") or []
        if isinstance(kinds, str):
            kinds = [kinds]
        for k in kinds:
            out.setdefault(str(k), []).append(page or "")
    # 兜底（真口径之二）：**一页一位的能力页**也算绑上 —— `brain/caps/<kind>.html` 是本位自己的页，
    # 不在这份 40 行台账里，但它显然是"人点得到"的那条腿（P1：别拿 40 行的账去量 406 页的面）。
    caps_dir = ROOT / "holo_pet_w3" / "brain" / "caps"
    if caps_dir.is_dir():
        for p in caps_dir.glob("*.html"):
            out.setdefault(p.stem, []).append("holo_pet_w3/brain/caps/" + p.name)
    return out


def _vault_caps() -> set:
    """触手库：obsidian 库里认得的 kind（README/记忆页文件名或索引里出现）。"""
    d = _json(STATE / "obsidian_vaults.json") or {}
    text = json.dumps(d, ensure_ascii=False)[:4_000_000]
    return set(re.findall(r"[A-Za-z][A-Za-z0-9_]{2,40}", text))


def check(only: str = "") -> dict:
    caps = _caps()
    disp = _dispatch_kinds()
    led = _ledger_caps()
    assets = _asset_bound()
    pages = _page_bound()
    vault = _vault_caps()

    kinds = [only] if only else sorted(caps)
    rows = []
    for k in kinds:
        legs = {
            "L1": k in caps,
            "L2": k in disp,
            "L3": k in led and bool((led.get(k) or {}).get("carrier") or (led.get(k) or {}).get("binding")
                                    or (led.get(k) or {}).get("承载")),
            "L4": bool(assets.get(k)),
            "L5": bool(pages.get(k)),
            "L6": k in vault,
        }
        bad = [n for n, v in legs.items() if not v]
        rows.append({"kind": k, "legs": legs, "missing": bad,
                     "domain": (caps.get(k) or {}).get("domain"),
                     "资产数": len(assets.get(k) or []), "页数": len(pages.get(k) or [])})
    total = len(rows)
    ok = [r for r in rows if not r["missing"]]
    broken = [r for r in rows if r["missing"]]
    per_leg = {n: sum(1 for r in rows if not r["legs"][n]) for n in ("L1", "L2", "L3", "L4", "L5", "L6")}
    return {"ok": not broken, "total": total, "全绿": len(ok), "断连": len(broken),
            "每腿缺数": per_leg,
            "来源": {"注册表": len(caps), "分派面": len(disp), "台账": len(led),
                     "资产绑": len(assets), "页绑": len(pages), "触手库": len(vault)},
            "怎么补": TEST_HINT,
            "断连清单": sorted(broken, key=lambda r: (len(r["missing"]), r["kind"]))[:80]}


def main() -> int:
    ap = argparse.ArgumentParser(description="触手主干判据：每条能力必须整根长在触手上（六腿）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--kind", default="")
    a = ap.parse_args()
    r = check(a.kind)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["ok"] else 1
    print("═" * 74)
    print("  触手主干判据 · 每条能力必须整根长在触手上（六腿）")
    print("═" * 74)
    s = r["来源"]
    print("  现读：注册表 %d · 分派面 %d · 台账 %d · 资产绑 %d · 页绑 %d · 触手库符号 %d"
          % (s["注册表"], s["分派面"], s["台账"], s["资产绑"], s["页绑"], s["触手库"]))
    print("  合计 %d 位 · 全绿 %d · **断连 %d**" % (r["total"], r["全绿"], r["断连"]))
    print("  每腿缺数：" + " · ".join("%s=%d" % (k, v) for k, v in r["每腿缺数"].items()))
    if r["断连清单"]:
        print("  ── 断连前 12 位（缺哪条腿 + 怎么补）──")
        for row in r["断连清单"][:12]:
            print("   🔴 %-24s 缺 %s · 域 %s · 资产 %d · 页 %d"
                  % (row["kind"], ",".join(row["missing"]), row["domain"], row["资产数"], row["页数"]))
            for m in row["missing"]:
                print("        %s → %s" % (m, TEST_HINT[m]))
    else:
        print("  ✅ 每一位六腿齐全：她所有能力都长在触手上，没缺失、没断连")
    print("  口径：取不到 = 未验 = 红；本件只读，不改任何台账")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
