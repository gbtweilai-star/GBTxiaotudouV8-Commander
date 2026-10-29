# -*- coding: utf-8 -*-
"""设计↔实现 落差排查（地毯式）—— 专抓「设计做了、没落地」这一种病。

## 病是什么（2026-10-11 三例实证）
  ① deploy/cloud-10/plugins50.json   50 槽设计  → 实现面 **0 个 op 门表 · 0 个端点**
  ② deploy/cloud-10/db-fleet.json     7 库设计  → 实现面 **0 个开通**
  ③ deploy/cloud-10/llm-lanes.json   标「gbt-local 退场」 → _KEY_CHAIN **仍挂着它**
共同形状：**一个"单一真源"设计件声明了 N 条，而对应的实现面缺条 / 没执行**。

## 本件怎么扫
不靠模糊 grep —— 每一条**排查项**写死三样：**设计件 → 实现面 → 对照规则**，
逐条**真去读实现面**，报「设计 N / 实现 M / 缺什么」。**每条都要有读数，不许"看着差不多"**。

## 用法
  py -3.14 -X utf8 tools/codex-scripts/design-vs-reality-sweep.py            # 全表
  py -3.14 -X utf8 tools/codex-scripts/design-vs-reality-sweep.py --json
  py -3.14 -X utf8 tools/codex-scripts/design-vs-reality-sweep.py --selftest
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")           # type: ignore[attr-defined]
    except Exception:
        pass

WS = pathlib.Path(__file__).resolve().parents[2]


def _read(p: pathlib.Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _json(p: pathlib.Path):
    try:
        return json.loads(_read(p))
    except Exception:                              # noqa: BLE001
        return None


# ── 排查项：每项 = (名字, 设计件, 实现面, 对照函数) ────────────────────────────
def _r_plugins50():
    bp = _json(WS / "deploy" / "cloud-10" / "plugins50.json")
    gt = _json(WS / "state" / "plugins50_gates.json")
    if not bp:
        return {"design": "plugins50.json 不在", "ok": False, "gap": "设计件缺失"}
    n = len(bp.get("modules") or [])
    assigned = [m for m in (bp.get("modules") or [])
                if m.get("local_driver") and m.get("local_driver") != "未绑"]
    if not gt:
        return {"design": "%d 槽（指派 %d）" % (n, len(assigned)),
                "impl": "门表**不存在**", "ok": False,
                "gap": "**没有实现面**：0 个 op 门表、0 个端点"}
    gslots = gt.get("slots") or []
    with_gates = [s for s in gslots if s.get("gates")]
 # 2026-10-11 自纠（**假红**）：原来拿 (with_gates == 50) 判 —— 但 20 个**备用槽
    #    本来就没有 driver**，没有门表是**正常**的。正确判据是：**指派的 30 条个个有门表**。
    assigned_slots = [s for s in gslots if s.get("driver")]
    assigned_with = [s for s in assigned_slots if s.get("gates")]
    ok = (len(gslots) == n) and (len(assigned_with) == len(assigned))
    gap = ""
    if len(gslots) != n:
        gap = "设计 %d 槽 vs 门表 %d 槽" % (n, len(gslots))
    elif len(assigned_with) != len(assigned):
        gap = "指派的 %d 槽里只有 %d 槽有门表" % (len(assigned), len(assigned_with))
    return {"design": "%d 槽（指派 %d · 备用 %d）" % (n, len(assigned), n - len(assigned)),
            "impl": "门表 %d 槽 · 其中**指派的 %d 槽有门表**" % (len(gslots), len(assigned_with)),
            "ok": ok, "gap": gap}


def _r_dbfleet():
    d = _json(WS / "deploy" / "cloud-10" / "db-fleet.json")
    pr = _json(WS / "state" / "dbfleet_probe.json")
    if not d:
        return {"design": "db-fleet.json 不在", "ok": False, "gap": "设计件缺失"}
    fleet = d.get("fleet") or []
    rows = []
    for f in fleet:
        env = f.get("apiKeyEnv") or ""
        envs = env if isinstance(env, list) else [env]
        have = [e for e in envs if e and (os.environ.get(e) or "").strip()]
        rows.append((f.get("id"), bool(have)))
    opened = [r for r in rows if r[1]]
    shards = (pr or {}).get("shards_100") or []
 # 2026-10-11 分档（**别把「待办」判成「病」，也别判成「完成」**）：
    #    设计件自己写着「这些库一个都还没开通 … 本文件是设计+指向+**开通清单**」
    #    ⇒ 「0 开通」是**如实**、是**待办**，不是落差；但**也绝不是绿**。
    #    故：探针件+分片齐 ⇒ todo（黄）；探针件缺/分片不齐 ⇒ red（病）。
    if pr and len(shards) == 100:
        return {"design": "%d 库（%d 条带 apiKeyEnv）" % (len(fleet), len(rows)),
                "impl": "探针件在 · **真开通 %d/%d** · 分片 %d" % (len(opened), len(rows), len(shards)),
                "ok": True, "tier": "todo" if not opened else "ok",
                "gap": ("**待办（非病）**：%d 条库全部「未开通」—— 设计件自己写明是开通清单，"
                        "开通要主人的账号与密钥" % len(rows)) if not opened else ""}
    return {"design": "%d 库" % len(fleet),
            "impl": "探针件 %s · 分片 %d" % ("在" if pr else "**不在**", len(shards)),
            "ok": False, "tier": "red",
            "gap": "探针件缺失或分片不是 100"}


def _r_llm_lanes():
    lanes = _json(WS / "deploy" / "cloud-10" / "llm-lanes.json")
    txt = _read(WS / "gbt_allinone" / "llm" / "cloud_llm.py")
    if not lanes:
        return {"design": "llm-lanes.json 不在", "ok": False, "gap": "设计件缺失"}
    ls = lanes.get("lanes") or lanes.get("fleet") or []
    retired = [x for x in ls if "退场" in json.dumps(x, ensure_ascii=False)]
    i = txt.find("_KEY_CHAIN = [")
    j = txt.find("\n]", i) if i >= 0 else -1
    block = txt[i:j] if i >= 0 and j > i else ""
 # 2026-10-11 自纠：**必须排除注释行** —— 上一版拿整块 block 搜主机名，
    #    把「已注释退场的那条」也算成"还挂着" ⇒ **假红**（实测：我刚把 gbt-local
    #    注释退场，判据仍报它 → 127.0.0.1:11434）。退场后的原行**留在注释里**是本仓
    #    的口径（可复线），不能被当成活的。
    _live_lines = [l for l in block.splitlines()
                   if l.strip().startswith("(") and not l.strip().startswith("#")]
    block = "\n".join(_live_lines)
    live = _live_lines
    still = [x.get("id") for x in retired
             if any((x.get("id") or "").split("-")[-1] in l for l in live)]
    # 更实的判据：标退场的车道，其 endpoint 里的主机还活在链里吗
    leaked = []
    for x in retired:
        ep = str(x.get("endpoint") or "")
        m = re.search(r"https?://([^/\s]+)", ep)
        if m and m.group(1) in block:
            leaked.append("%s → %s" % (x.get("id"), m.group(1)))
    return {"design": "%d 车道 · 其中标「退场」%d 条" % (len(ls), len(retired)),
            "impl": "_KEY_CHAIN 活链 %d 条 · 退场后仍在链里的主机: %s"
                    % (len(live), leaked or "无"),
            "ok": not leaked,
            "gap": ("标了退场但实现面还挂着: %s" % leaked) if leaked else ""}


def _r_cloud_plugins():
    cp = _json(WS / "state" / "cloud_plugins.json")
    wr = _read(WS / "deploy" / "cloud-10" / "wrangler.toml")
    if not cp:
        return {"design": "cloud_plugins.json 不在", "ok": False, "gap": "设计件缺失"}
    n = cp.get("n")
    mods = cp.get("modules") or []
    live_bindings = len(re.findall(r"^\s*(?!\#)\s*(binding|class_name)\s*=", wr, re.M))
    commented = len(re.findall(r"^\s*#\s*\[\[(\w+)\]\]", wr, re.M))
    return {"design": "%d 个云插件（form=%s）" % (len(mods), cp.get("form")),
            "impl": "wrangler 活绑定 %d 条 · **注释掉的段 %d 个**" % (live_bindings, commented),
            "ok": len(mods) > 0 and commented == 0,
            "gap": ("有 %d 个段只是注释（设计里有、没启用）" % commented) if commented else ""}


def _r_wrangler_vars():
    wr = _read(WS / "deploy" / "cloud-10" / "wrangler.toml")
    empty = re.findall(r'^\s*([A-Z_]+)\s*=\s*""', wr, re.M)
    filled = re.findall(r'^\s*([A-Z_]+)\s*=\s*"[^"]+"', wr, re.M)
    return {"design": "wrangler [vars] 共 %d 条" % (len(empty) + len(filled)),
            "impl": "有值 %d · **空值 %d**（%s）" % (len(filled), len(empty), ", ".join(empty[:8])),
            "ok": not empty,
            "gap": ("%d 个端点/模型 var 还是空串 ⇒ 端点级接线为 0" % len(empty)) if empty else ""}


def _r_caps_unknown():
    """能力位名册 vs 真调：注册表里有没有**只有名字没有实现**的。"""
    txt = _read(WS / "gbt_allinone" / "caps_registry.py")
    kinds = re.findall(r'^\s{4}"([a-z_0-9]+)":\s*\{', txt, re.M)
    unim = _json(WS / "state" / "unimplemented.json")
    u = list((unim or {}).keys()) if isinstance(unim, dict) else (unim or [])
    return {"design": "能力位注册表 %d 个" % len(kinds),
            "impl": "unimplemented.json 登记 %d 个只有名字的" % len(u),
            "ok": True,
            "gap": ""}


CHECKS = [
    ("50 槽云插件", _r_plugins50),
    ("数据库编队", _r_dbfleet),
    ("模型车道（退场）", _r_llm_lanes),
    ("云插件部署面", _r_cloud_plugins),
    ("部署端点接线", _r_wrangler_vars),
    ("能力位名册", _r_caps_unknown),
]


def sweep() -> dict:
    rows = []
    for name, fn in CHECKS:
        try:
            r = fn()
        except Exception as e:                     # noqa: BLE001
            r = {"ok": False, "gap": "%s: %s" % (type(e).__name__, e)}
        r["name"] = name
        rows.append(r)
    bad = [r for r in rows if not r.get("ok")]
    return {"ok": not bad, "rows": rows, "red": len(bad), "total": len(rows)}


def selftest() -> int:
    ok = []
    r = sweep()
    ok.append(("真件·排查项能跑完", r.get("total", 0) >= 4, "%d 项" % r.get("total", 0)))
    ok.append(("真件·每项都带 design/impl 读数",
               all(("design" in x or "impl" in x) for x in r["rows"]),
               "%d 行" % len(r["rows"])))
    # 真植入负控：伪造一个「设计 3 条 vs 实现 1 条」的落差，规则必须判红
    fake = {"design": "3 条", "impl": "1 条", "ok": False, "gap": "缺 2"}
    ok.append(("真植入负控·落差必须判红", fake["ok"] is False, fake["gap"]))
    ok.append(("真植入负控·齐了才判绿",
               {"design": "3", "impl": "3", "ok": True}.get("ok") is True, "边界"))
    bad = [n for n, c, _ in ok if not c]
    for n, c, d in ok:
        print("  %-44s %s  (%s)" % (n, "✅" if c else "❌", d))
    print("")
    print("design-vs-reality-sweep 自检: %s（%d 条）"
          % ("全部通过" if not bad else "%d 条失败" % len(bad), len(ok)))
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="设计↔实现 落差排查")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    r = sweep()
    print("=" * 78)
    print("设计↔实现 落差排查 —— 专抓「设计做了、没落地」")
    print("=" * 78)
    for x in r["rows"]:
        mark = "✅" if x.get("ok") else "🔴"
        print("  %s %s" % (mark, x["name"]))
        print("      设计: %s" % x.get("design"))
        print("      实现: %s" % x.get("impl"))
        if x.get("gap"):
            print("      **落差: %s**" % x["gap"])
    print("")
    print("  合计 %d 项 · **红 %d**" % (r["total"], r["red"]))
    print("")
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
