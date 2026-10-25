"""10 条职责 · **等效底层账**（只读）—— 那 8 个不存在的插件，职责现在由谁承担。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要有它
主人令「以 10 个云插件部署」。现读（`cloud-plugins-check.py`）：**只有 2 条真存在**，
8 条 npm 404。⇒ 要么停在这句"做不到"，要么回答**下一个真问题**：
**那 8 条职责，现在由本仓/DSH 的什么真东西承担？** 本件就是把这件事逐条对上账。

## 三档（宁窄不宽）
- `✅ 现读通过`：真件在盘 **且** 本脚本能机检通过；
- `🟡 有真件·本脚本验不了`：真件在盘，但验证方式在本脚本能力之外（**如实写清为什么**）；
- `🔴 没有真件`：本仓没有等价物（例如 abliterated 权重）。

**不许**把「有真件」念成「这条插件装上了」——插件名与职责是两件事。

用法：
  python tools/codex-scripts/ten-plugin-equivalence.py check [--json]
  python tools/codex-scripts/ten-plugin-equivalence.py selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 主人那张图里的 10 条（**逐字照录**）
ROWS = (
    ("dsh-llm-qwen-local", "本地模型接入（适配器）",
     "插件**真存在**（0.4.1）＋本仓假端点已验形状", "npm"),
    ("dsh-force-compact", "上下文压缩",
     "DSH 自带自动压缩（**本会话自己就发生过**：会话头那份 checkpoint 就是压缩产物）", None),
    ("dsh-llm-qwen-abliterated", "无审查推理（模型增强）",
     "**本仓没有**：要 abliterated 权重 + 一个端点（权重本机 0 个）", "none_real"),
    ("dsh-tool-web", "联网搜索与抓取",
     "`web_fetch` 可用（本会话多次真取回）；`web_search` **现读在本环境是坏的**", None),
    ("dsh-tool-file", "文件系统操作",
     "DSH 内建 read/write/edit/glob/grep（**本会话全程在用**）＋`file_operation.py` 写根闸门", None),
    ("dsh-tool-shell", "命令行执行",
     "DSH 内建 pwsh（**本会话全程在用**）；框架侧要 `process_execute` 作用域", None),
    ("dsh-memory-vector", "向量记忆",
     "`gbt_allinone/tools/context_vault.py`（sqlite + FTS5 真库）", "context_vault"),
    ("dsh-memory-local", "本地持久化记忆",
     "`memory/**` + `state/**` 文件式持久化（本会话写入 1.1 万行账）", None),
    ("dsh-policy-guard", "权限与安全策略",
     "`gbt_allinone/security/policy.py` + `auth_gate.py`（15 作用域 · owner_control 一条顶全部）", "policy"),
    ("dsh-observability", "可观测性与审计",
     "插件**真存在**（0.1.0，OTLP span）＋本仓 `trace_store`/审计元数据", "npm"),
)


def _probe_npm(name: str) -> tuple[str, str]:
    """机检「这个插件真存在」：现查 npm registry（404 ⇒ 不存在；网络失败 ⇒ 未读到，不算不存在）。"""
    import urllib.error
    import urllib.request
    url = "https://registry.npmjs.org/" + name
    try:
        with urllib.request.urlopen(url, timeout=12) as r:       # noqa: S310（公开只读）
            d = json.loads(r.read().decode("utf-8", errors="replace"))
        return "✅ 现读通过", "npm 现读存在 ｜ 最新 %s" % (d.get("dist-tags") or {}).get("latest")
    except urllib.error.HTTPError as e:
        return ("🔴 没有真件" if e.code == 404 else "🟡 有真件·本脚本验不了",
                "npm HTTP %s" % e.code)
    except Exception as exc:
        return "🟡 有真件·本脚本验不了", "**未读到**（%s）" % type(exc).__name__


def probe(kind: str | None, name: str = "") -> tuple[str, str]:
    """能机检的才机检；不能的老实说为什么。返回 (档, 读数)。"""
    if kind is None:
        return "🟡 有真件·本脚本验不了", "验证方式在本脚本能力之外（会话内实测，如实标）"
    if kind == "none_real":
        return "🔴 没有真件", "**本仓没有等价物**（要 abliterated 权重 + 一个端点；权重本机 0 个）"
    if kind == "npm":
        return _probe_npm(name)
    if kind == "context_vault":
        p = ROOT / "gbt_allinone" / "tools" / "context_vault.py"
        if not p.is_file():
            return "🔴 没有真件", "**未读到** %s" % p.relative_to(ROOT)
        db = ROOT / "gbt_allinone" / "store" / "context_vault" / "index.sqlite3"
        if not db.is_file():
            return "🟡 有真件·本脚本验不了", "**未读到**库文件（代码在、库没建）"
        import sqlite3
        try:                                    # 🔴 开真库查真表：**不拿"源码里提到 FTS5"当判据**
            con = sqlite3.connect("file:%s?mode=ro" % db.as_posix(), uri=True)
            rows = con.execute("SELECT name FROM sqlite_master "
                               "WHERE type='table' AND sql LIKE '%%fts5%%'").fetchall()
            con.close()
        except Exception as exc:
            return "🟡 有真件·本脚本验不了", "库读不开：%s" % type(exc).__name__
        names = [r[0] for r in rows]
        return (("✅ 现读通过" if names else "🟡 有真件·本脚本验不了"),
                "库在（%s）｜ FTS5 虚拟表 %d 张%s ｜ sqlite %s"
                % (db.name, len(names), ("（" + "、".join(names[:2]) + "）") if names else "（**未读到**）",
                   sqlite3.sqlite_version))
    if kind == "policy":
        try:
            from gbt_allinone.security import policy as P
            from gbt_allinone import auth_gate as G
        except Exception as exc:
            return "🔴 没有真件", "导入失败：%s" % type(exc).__name__
        n1, n2 = len(P.SCOPE_DESCRIPTIONS), len(getattr(G, "SCOPES", {}) or {})
        ok = n1 > 0 and n2 > 0 and "owner_control" in getattr(G, "SCOPES", {})
        return (("✅ 现读通过" if ok else "🔴 没有真件"),
                "门侧 %d ｜ 可授权 %d ｜ owner_control=%s"
                % (n1, n2, "在" if "owner_control" in getattr(G, "SCOPES", {}) else "**未读到**"))
    return "🟡 有真件·本脚本验不了", "未知探针 %r" % kind


def build() -> dict:
    rows = []
    for name, why, real, kind in ROWS:
        tier, reading = probe(kind, name)
        rows.append({"插件": name, "职责": why, "现读真件": real, "档": tier, "读数": reading})
    count = {"✅ 现读通过": 0, "🟡 有真件·本脚本验不了": 0, "🔴 没有真件": 0}
    for r in rows:
        count[r["档"]] = count.get(r["档"], 0) + 1
    return {"名单条数": len(rows), "逐条": rows, "统计": count,
            "口径": "**有真件 ≠ 该插件装上了**：插件名与职责是两件事；"
            "`🟡` 一律写清为什么本脚本验不了，不冒充通过"}


def check(as_json: bool) -> int:
    d = build()
    if not d["逐条"]:
        print(json.dumps({"拒绝": "**名单是空的 ⇒ 拒绝**"}, ensure_ascii=False))
        return 2
    if as_json:
        print(json.dumps(d, ensure_ascii=False, indent=1))
    else:
        print("10 条职责 · 等效底层账（现读）")
        print("统计：✅ 通过 %d ｜ 🟡 本脚本验不了 %d ｜ 🔴 没有真件 %d"
              % (d["统计"]["✅ 现读通过"], d["统计"]["🟡 有真件·本脚本验不了"],
                 d["统计"]["🔴 没有真件"]))
        for r in d["逐条"]:
            print("  %s %-26s %s" % (r["档"], r["插件"], r["现读真件"][:64]))
            if r["档"] == "✅ 现读通过":
                print("        读数：%s" % r["读数"])
        print("口径：%s" % d["口径"])
    return 0


def selftest() -> int:
    checks, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad = bad + (0 if cond else 1)
        checks.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    ck("**名单恰好 10 条**（逐字来自截图，不增不减）",
       len(ROWS) == 10 and ROWS[0][0] == "dsh-llm-qwen-local", "%d 条" % len(ROWS))
    d = build()
    ck("**三档都出现了**（判据有分辨力）",
       all(d["统计"][k] > 0 for k in ("✅ 现读通过", "🟡 有真件·本脚本验不了", "🔴 没有真件")),
       json.dumps(d["统计"], ensure_ascii=False))
    ck("**负控：没有真件的那条必须判 🔴**（abliterated 权重本机 0 个）",
       any(r["档"] == "🔴 没有真件" and "abliterated" in r["插件"] for r in d["逐条"]), "")
    ck("**负控：`🟡` 必须写明为什么验不了**（不许空白糊过去）",
       all(r["读数"] for r in d["逐条"] if r["档"].startswith("🟡")), "")
    ck("**边界：未知探针 ⇒ 不许判通过**",
       probe("不存在的探针")[0].startswith("🟡"), probe("不存在的探针")[0])
    print(json.dumps({"自检": {"条数": len(checks), "通过": len(checks) - bad, "不通过": bad},
                      "逐条": checks}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "selftest"])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.cmd == "selftest":
        return selftest()
    return check(a.json)


if __name__ == "__main__":
    raise SystemExit(main())
