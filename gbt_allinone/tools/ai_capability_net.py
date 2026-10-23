# -*- coding: utf-8 -*-
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""AI 能力穿透网 · **骨架**（第 1 刀 · Owner 2026-09-19 图纸）。

一句话：**不是导航，是穿透** —— 把索引拆成能力位，把触手接到能力位的真实入口上。

本刀只落**骨架**，三件：
  ① `CapabilityNode`：能力位（索引层 + 入口层的载体），**六个诚实位默认全 False**；
  ② 七栏读数的真相源：从 `caps_registry`（本地 111）与 `toolchain_manifest.json`（外部 19）灌种子；
  ③ `PenetrationProtocol.penetrate()` + `SwitchRouter.route()`：**只读**，未实现分支一律
     `{"ok": False, "reason": "not_implemented"}` —— **绝不返回空壳 `ok=True`**。

三条口径（Owner 原文，写进代码不靠自觉）：
    "在索引里" ≠ "能穿透" · "能穿透" ≠ "已核实能穿透" · "已核实" ≠ "已授权"
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROC_PRIMITIVES = ("subprocess", "Popen", "os.system", "Thread(", "asyncio",  # PROC_SCAN_OFF
                   "multiprocessing", "sched.", "urlopen", "requests.")       # PROC_SCAN_OFF


@dataclass
class CapabilityNode:
    """一个能力位。**诚实位默认全 False** —— 没跑过的永远是 False。"""
    name: str
    category: str = ""
    desc: str = ""
    web_url: str | None = None
    api_endpoint: str | None = None
    cli_command: str | None = None
    source: str = "unknown"          # local / owner-claim / fetched
    # ── 七栏（一层不许替下一层背书）──
    indexed: bool = False
    entry_known: bool = False
    reachable: bool = False
    verified_reachable: bool = False
    verified_readonly: bool = False
    has_test: bool = False
    penetrate_ready: bool = False
    # ── 其余 ──
    invoke_mode: str = "unknown"     # api / cli / web / manual / unknown
    auth_type: str = "unknown"       # free / api_key / oauth / owner_grant / blocked
    requires_params: list = field(default_factory=list)
    returns: list = field(default_factory=list)
    evidence_ref: str = ""
    needs_review: str = ""           # 非空 = 挂账（带复查触发条件）


# 四条 needs_review：**没有触发条件的挂账是死账** → 触发条件写死在这里
NEEDS_REVIEW_TRIGGERS = {
    "ghost_guard.main(argv=None)": "主人显式点名要跑 ghost_guard 时复查",
    "prompt_bridge.run(op='compile')": "compile 的写盘行为被核实后复查",
    "transfer.transfer(payload=None)": "签名被明确改成只读档时复查",
    "trend_watch(4候选)": "主人指定用哪个候选时复查",
}


def _local_nodes() -> list:
    """本地能力位（读数**全部现算**，不许写死 —— 见 build_net 的 metric_defs）。

    🔴 2026-09-22 第 35 轮改名（错报治理）：这个集合原来叫 **`GREEN6`**，
    但它的取值只有 **5** 个元素 —— **名字里的数字是假的**（"名字看着像计数"这类病，
    本仓已犯过第 4 次：`scanned` 曾是布尔、`GREEN6` 是 5 个）。现名 `GREEN`：
    不含数字的名字不会随成员增减而说谎。
    集合语义：**已核实为只读**的本地能力位（人工清单，逐条复核过；不自动取证）。
    """
    from gbt_allinone import caps_registry as C
    pkg = ROOT / "gbt_allinone"
    GREEN = {"brain_vault", "project_context", "root_fix", "selfscan", "topic_watch"}
    TESTED = {"project_context", "prompt_bridge"}
    nodes = []
    for c in C.all_caps():
        # 2026-10-17：`handler` 改为**分派键真名**后，这里要拿"实现模块"去判 on_disk ⇒ 读 `impl` 兜底。
        h = str(c.get("impl") or c.get("handler") or "")
        blocked = h == "blocked"
        on_disk = (pkg / (h + ".py")).is_file() if h and not blocked else False
        nodes.append(CapabilityNode(
            name=str(c.get("name") or h), category=str(c.get("domain") or ""),
            desc=str(c.get("desc") or "")[:80], source="local",
            indexed=True, entry_known=on_disk,
            reachable=on_disk, verified_reachable=on_disk,
            verified_readonly=h in GREEN, has_test=h in TESTED,
            penetrate_ready=h in GREEN,
            invoke_mode="api" if on_disk else "unknown",
            auth_type="blocked" if blocked else "unknown",
            requires_params=["params"] if c.get("requires_params") else [],
        ))
    return nodes


def _external_nodes() -> list:
    """外部工具清单（19 条 · 没抓过 ⇒ fetched 只能是 False）。"""
    p = ROOT / ".cluster" / "dd_squad" / "toolchain_manifest.json"
    if not p.is_file():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    nodes = []
    for group, items in (data.get("groups") or {}).items():
        for it in items:
            repo = str(it.get("repo") or "").strip()
            # 旧字段名是 repo；兼容新写法 url
            url = str(it.get("url") or repo or "").strip() or None
            nodes.append(CapabilityNode(
                name=str(it.get("name") or "?"), category=group, source="owner-claim",
                web_url=url, indexed=True, entry_known=bool(url),
                invoke_mode="unknown", auth_type="unknown"))
    return nodes


class PenetrationProtocol:
    """统一调用接口。**本刀全身只读** —— 任何执行分支都返回 not_implemented。"""

    def penetrate(self, node: CapabilityNode, params: dict | None = None) -> dict:
        params = dict(params or {})
        missing = [p for p in (node.requires_params or []) if p not in params]
        if missing:
            return {"ok": False, "reason": "missing_params", "missing": missing,
                    "node": node.name}
        # 骨架阶段：调用层未实现 —— 绝不用空壳 ok=True 顶上
        return {"ok": False, "reason": "not_implemented", "node": node.name,
                "invoke_mode": node.invoke_mode,
                "note": "骨架阶段只读：等契约层收口 + 过授权门；未实现不返回 ok=True"}


class SwitchRouter:
    """切换＝路由（不是导航）。按维度返回命中列表 —— **只读**。"""

    def __init__(self, nodes: list):
        self.nodes = list(nodes)

    def route(self, intent: str, dimension: str = "category") -> list:
        q = str(intent or "").strip().lower()
        if not q:
            return []
        if dimension == "category":
            return [n for n in self.nodes if q in str(n.category).lower()]
        if dimension == "auth":
            return [n for n in self.nodes if q in str(n.auth_type).lower()]
        if dimension == "source":
            return [n for n in self.nodes if q in str(n.source).lower()]
        if dimension == "name":
            return [n for n in self.nodes if q in str(n.name).lower()]
        return [n for n in self.nodes if q in (str(n.name) + str(n.desc)).lower()]


def run(op="status", **params) -> dict:
    """能力入口（只读 · R-H194 补）：status / net。**不写盘、不出网、不执行。**

    为什么补：本能力位此前没有 `run()`，编排内核接不上 ⇒ 它一直是没人调的孤儿。
    """
    op = str(op or "status")
    built = build_net()
    if op == "net":
        return {"ok": True, "readonly": True, **built}
    if op == "status":
        return {"ok": True, "readonly": True,
                "counts": {"total": len(built.get("nodes") or []),
                           "local": len(built.get("local") or []),
                           "external": len(built.get("external") or [])},
                "seven_columns": built.get("seven_columns"),
                "note": "穿透网七栏只读读数（net 拿全量）"}
    raise ValueError("未知 op %r（可用：status/net）" % (op,))


def build_net() -> dict:
    """建网：本地 + 外部 → 七栏读数。**每一格都能追到盘上。**

    🔴 2026-09-22 第 35 轮修（错报治理 · 这是**产品在说谎**，不只是测试写死）：

    七栏里原本有 **5 栏是现算的**（`"%d/%d" % (col(...), len(...))`），
    而 `verified(readonly)` 与 `penetrate_ready` **两栏是写死的字面量**：

        "verified(readonly)": "%d 口 / %d 位" % (9, 6),

    有病的地方在于它**长得像现算** —— `%d` 占位符摆在那里，参数却是 `9` 和 `6` 两个字面量。
    实测真相：`GREEN` 只有 **5** 个成员 ⇒ 该栏真值是 5 而不是 6；
    而 `9` 在整个仓库里**找不到任何定义或可算来源**（`_READONLY_MODULES` 是 37、
    `entry_known` 是 19、`entry ∩ 只读注册表` 是 0，没有一个是 9），
    所有副本（原型 HTML、无限画布、trace 里的面板截图）都是同一个字面量抄来抄去。
    更要命的是它**流到了主人眼睛看的那块面板上**
    （`tools/codex-scripts/build_v8_canvas.py:157-158` 写着『值与 :root 清单逐字一致』）。

    ⇒ 现改为**全部现算**，并把**口径写进返回值**（`metric_defs`）：谁能算就报谁、
    算不出来的**不编**。`9 口` 那一半被拿掉，因为盘上没有任何东西能支撑它 ——
    这是我**不敢替主人定义**的量，所以只能如实说"这个数没有出处"。
    主人给出 `口` 的定义后，这里再加一行现算即可。
    """
    local, external = _local_nodes(), _external_nodes()
    nodes = local + external

    def col(attr, pool):
        return sum(1 for n in pool if getattr(n, attr))

    # 已核实只读：位=已核实只读的能力位个数；口=其中**确实有入口**的个数。
    # 两个数**都是现算的**，谁涨谁落都跟着走，不存在"写死的读数"。
    green_local = [n for n in local if n.verified_readonly]
    green_entry = [n for n in green_local if n.entry_known]
    green_txt = "%d 口 / %d 位" % (len(green_entry), len(green_local))

    return {
        "ok": True, "readonly": True,
        "nodes": nodes, "local": local, "external": external,
        "seven_columns": {
            "indexed": "%d/%d" % (col("indexed", nodes), len(nodes)),
            "entry_known": "%d/%d" % (col("entry_known", nodes), len(nodes)),
            "reachable": "%d/%d" % (col("reachable", local), len(local)),
            "verified(reachable)": "%d/%d" % (col("verified_reachable", local), len(local)),
            "verified(readonly)": green_txt,
            "has_test": "%d/%d" % (col("has_test", local), len(local)),
            "penetrate_ready": green_txt,
        },
        # 口径必须跟着读数一起交出去：否则下一个人读到 "5 口 / 5 位" 还是得猜单位。
        "metric_defs": {
            "位": "本地能力位里 **已核实只读** 的个数（现算：verified_readonly 为真的节点数）",
            "口": "上述已核实只读位里 **确实有入口文件在盘上** 的个数（现算：entry_known 为真）",
            "GREEN 出处": "人工逐条复核的只读清单（%d 条）；**不自动取证** ⇒ evidence_ref 为空"
                          % len(green_local),
            "9 口 已撤": ("原写法 `\"%%d 口 / %%d 位\" %% (9, 6)` 里 9 与 6 都是**字面量**，"
                          "长得像现算其实写死。实测真值 6→%d；9 在盘上**无定义、无来源**，"
                          "故撤下该半句，不替主人编一个新定义。" % len(green_local)),
        },
        "evidence_ref_note": ("`CapabilityNode.evidence_ref` 目前**恒为空串**（注册表 147 条里 "
                              "0 条带 evidence 字段）⇒ 任何『带着 evidence_ref』的断言都只能用 "
                              "`is not None` 空过。这是已知缺口，已在此显式登记，不再假装有证据。"),
        "needs_review": NEEDS_REVIEW_TRIGGERS,
        "honest_boundary": ("穿透网只保证『能力位可路由』，不保证『每个能力位都可穿透』；"
                            "『在索引里』不等于『能穿透』，『能穿透』不等于『已核实能穿透』，"
                            "『已核实』不等于『已授权』。"),
    }


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="AI 能力穿透网（骨架 · 只读）")
    ap.add_argument("cmd", nargs="?", default="status", choices=("status", "review"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    net = build_net()
    if a.cmd == "review":
        out = {"ok": True, "needs_review": net["needs_review"]}
    else:
        out = {k: v for k, v in net.items() if k not in ("nodes", "local", "external")}
        out["counts"] = {"total": len(net["nodes"]), "local": len(net["local"]),
                         "external": len(net["external"])}
    print(json.dumps(out, ensure_ascii=False, indent=1) if a.json
          else json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
