"""GBT小土豆V8 · 框架体检层（眼睛 + 声带）。

Owner 定调（2026-09-11）：哪里有毛病、断连、丢失，框架必须第一时间知道、
追踪根源、给出修复——不能手臂掉了眼睛看不见，连个响都没有。

五个体检维度：
  1. 路由完整性：BENIGN_CAPS 注册的每项能力在 api.py 必须有真实分派路径
     （静态提取 == / in (...) / startswith 三种路由形态，注册与路由双向对账）
  2. 模块健康：全部核心模块 import 必须成功（含 src.core、子包）
  3. 存储健康：store 下全部 JSON 必须可解析；关键目录必须存在
  4. 审计异常：近期 error/denied/svc_down/longrun_failed/stalled/pipeline_blocked
     聚合计数 + 按能力分组的根源线索
  5. 桩缺口：needs_dependency 的能力如实清点（不算病，算缺口）

严重度：P0 = 断连/损坏（必须修）；P1 = 异常在发生（要看）；P2 = 缺口（要知道）。
autofix=True 时只做安全修复：缺目录补建、损坏 JSON 备份后重置；其余只报不动。
"""
import importlib
import json
import re
import time
import sys
import time
from pathlib import Path

_BASE = Path(__file__).resolve().parent
_ROOT = _BASE          # V8 独立家：根就是 gbt_allinone 自己

_MODULES = [
    "api", "app", "cli", "engine", "ghost_guard", "longrun",
    "pipeline", "quant_tech", "schedule", "services", "soul", "store",
    "tactics",
    "integration.auth", "integration.platform_client",
    "integration.smoke_test",
    "recon.scanner", "recon.guard",
    "hygiene", "signature", "transfer", "auth_gate", "mirror_space", "qiankun", "think_loop", "brain_exec", "inventory", "cross_scan", "root_fix",
    # 补齐验收观察项：caps_registry 直接入列（不再只靠 routing 间接覆盖）
    "caps_registry",
    # 集成收口：第九批新模块全部入列（黑客大脑/LLM网关/自主编排/真实性审计/触手）
    "security.security_brain", "security.abl_gateway",
    "llm.bridge", "truth_scan", "autopilot", "tentacle.bridge",
    "record_grid",
]

# 资金模块（纯全能 AI 框架不随库分发）：存在则检查，不存在不算病
_MONEY_MODULES = [
    "notify", "export_statement", "loop",
    "ledger.core", "ledger.pool",
    "wallet.hd", "wallet.rpc", "wallet.consolidate",
    "adapters.wallet_adapter",
    "bridge.deposit_bridge",
]

# 适配器/桥目录为空目录时 Python 不导入，需目录探测
_PROBE_DIRS = ["adapters", "bridge"]

_ANOMALY_EVENTS = ("error", "svc_down", "longrun_failed",
                   "longrun_stalled", "pipeline_blocked")
# denied 是护栏正常拦截（测试/演示触发为主），单独统计不算病
_RESERVED_SERVICES = {"v8_isolated"}  # 预留端口，未启动属预期，不算掉线


_RECOVERED_CACHE = {}  # name -> (结论, 时刻)——热路径防抖：同 kind 30s 内只探一次


def _service_recovered(name: str) -> bool:
    """svc_down 的服务当前是否已探活在线（历史掉线已恢复）。

    TTL 缓存 30s：窗口内几十条同 kind 的 svc_down 只真实探活一次（性能基线守卫——
    每次 0.6s 探活 × 41 条曾把 selfscan 热路径顶到 600ms）。quiet=True 纯探活不落审计。
    """
    now = time.time()
    hit = _RECOVERED_CACHE.get(name)
    if hit and now - hit[1] < 30:
        return hit[0]
    try:
        from . import services
        snap = services.inspect(str(name), timeout=0.15, quiet=True)
        up = bool(snap.get("services", {}).get(str(name), {}).get("up"))
    except Exception:
        up = False
    _RECOVERED_CACHE[name] = (up, now)
    return up


def _routed_kinds():
    """静态提取 api.py 里全部真实分派路径。"""
    src = (_BASE / "api.py").read_text(encoding="utf-8")
    kinds = set(re.findall(r'kind == "(\w+)"', src))
    for tup in re.findall(r'if kind in \((.*?)\)', src, re.DOTALL):
        kinds.update(re.findall(r'"(\w+)"', tup))
    # 变量形式元组：_XXX_KINDS = (...) / _MONEY_KINDS = (...) ——赋值后 `if kind in _XXX`
    # （降级占位路由也算有效路由：能力有明确的分派路径与响应语义）
    for var, tup in re.findall(r'(_\w*KINDS\w*)\s*=\s*\((.*?)\)', src, re.DOTALL):
        if f"if kind in {var}" in src:
            kinds.update(re.findall(r'"(\w+)"', tup))
    prefixes = set(re.findall(r'kind\.startswith\("(\w+)"\)', src))
    # _STUB_DEPS 桩家族（如实缺口，不算断连）
    stubs = set()
    for k, v in re.findall(r'"(\w+)":\s*"([^"]*)"', src):
        if v.startswith("需") and k not in ("note",):
            stubs.add(k)
    return kinds, prefixes, stubs


def check_routing():
    from .caps_registry import BENIGN_CAPS
    routed, prefixes, stubs = _routed_kinds()
    registered = set(BENIGN_CAPS)

    def _covered(k):
        return k in routed or k in stubs or any(k.startswith(p) for p in prefixes)

    unrouted = sorted(k for k in registered if not _covered(k))
    ghost_routes = sorted(k for k in (routed | stubs) if k not in registered)
    return {"registered": len(registered), "routed": len(routed | stubs),
            "unrouted": unrouted, "ghost_routes": ghost_routes,
            "ok": not unrouted and not ghost_routes}


_MODULE_CACHE = {"result": None}


def check_modules():
    """模块健康检查（进程内缓存：导入结果不会中途变化，缓存后 0ms）。"""
    if _MODULE_CACHE["result"] is not None:
        r = dict(_MODULE_CACHE["result"])
        r["cached"] = True
        return r
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    bad = []
    for m in _MODULES:
        full = m if m.startswith("gbt_allinone") else "gbt_allinone." + m
        try:
            importlib.import_module(full)
        except Exception as e:  # noqa: BLE001
            bad.append({"module": full, "error": f"{type(e).__name__}: {e}"[:160]})
    # 资金模块：存在则检查，不存在不算病（纯全能 AI 框架不随库分发）
    money_checked = 0
    for m in _MONEY_MODULES:
        full = m if m.startswith("gbt_allinone") else "gbt_allinone." + m
        try:
            mod = importlib.import_module(full)
        except ImportError:
            continue  # 未分发→跳过，不算失败
        except Exception as e:  # noqa: BLE001
            bad.append({"module": full, "error": f"{type(e).__name__}: {e}"[:160]})
            money_checked += 1
            continue
        money_checked += 1
    _MODULE_CACHE["result"] = {"checked": len(_MODULES) + money_checked, "failed": bad, "ok": not bad}
    return dict(_MODULE_CACHE["result"])


def check_store(full: bool = False):
    store = __import__("gbt_allinone._paths", fromlist=["STORE_DIR"]).STORE_DIR
    need_dirs = ["pipeline/mirror", "pipeline/gate", "pipeline/quarantine",
                 "pipeline/production", "pipeline/records", "wf_runs"]
    missing = [d for d in need_dirs if not (store / d).exists()]
    corrupted = []
    unreadable = []
    empty = []
    checked = 0
    n = 0
    attempted = 0
    if store.exists():
        # 性能纪律：全量列出 + 分层检查——活跃工作文件（顶层）全查，
        # 历史记录目录（wf_runs/pipeline/records）每目录抽前 50 个
        # 🔴 2026-10-17 修三处假红（主人令「无死角原生扫描」；全量模式一开就当场咬出来的）：
        #   ① `rglob("*.json")` 会把**名叫 *.json 的目录**也收进来 —— 实测
        #      `store/pipeline/production/.versions/capability.json` 与 `knowledge.json` 都是**目录**，
        #      读它必 PermissionError，被念成"读不了"= 假红，还白白压低覆盖率。
        #      现只收 `is_file()`；那些怪目录单列 `odd_dirs` **如实报**（不藏，只是不再冒充 JSON 文件）。
        #   ② 浏览器档案 `native_browser/profile/**` 是 Chrome 的组件数据（JSONL：一行一对象），
        #      拿"单对象 JSON"尺去量它必报 `Extra data` ⇒ 单列 `foreign_skipped`，不计红。
        #   ③ 0 字节 / 纯空白不是"损坏"，是**空文件** ⇒ 单列 `empty`（仍是问题，但归类必须说对）。
        _ALL = [p for p in store.rglob("*.json")]
        odd_dirs = [p for p in _ALL if p.is_dir()]
        all_json = [p for p in _ALL if p.is_file()]
        foreign = [p for p in all_json
                   if "native_browser" in p.parts and "profile" in p.parts]
        all_json = [p for p in all_json if p not in foreign]
        n = len(all_json)
        active = [jf for jf in store.glob("*.json") if jf.is_file()]
        # 🔴 2026-10-17 加（主人令：「大模型每次扫描必须无死角原生扫描」）：
        #   原口径固定抽样 150 个非活跃 JSON（性能纪律：全量解析实测 2317ms，超 selfscan 500ms 预算）。
        #   但"抽样"就是**盲区** —— 用户要的是「无死角」，那就得让**原生判据**自己能做到全量，
        #   而不是在仓外另写脚本补。⇒ 加 `full=True` 全量模式（不抽）；默认仍抽样保预算，
        #   `coverage` 字段照旧如实标 full/sampled，绝不把抽样读成全量。
        if full:
            sampled = [jf for jf in all_json if jf not in active]
        else:
            sampled = [jf for jf in all_json if jf not in active][:150]
        attempted = len(active) + len(sampled)
        for jf in active + sampled:
            try:
                raw = jf.read_text(encoding="utf-8")
            except (PermissionError, OSError) as e:
                # 🔴 「读不了」≠「坏了」：权限拒绝是**没扫到**，不是文件损坏。
                #    实测（生产 store）：`pipeline/production/.versions/*.json` 就是这么被拒的
                #    —— 修①之后这类已不再进来，但真目录/真锁文件仍可能，如实单列。
                unreadable.append({"file": str(jf.relative_to(_BASE)),
                                   "error": type(e).__name__})
                continue
            if not raw.strip():
                empty.append({"file": str(jf.relative_to(_BASE)),
                              "bytes": jf.stat().st_size if jf.is_file() else 0})
                checked += 1
                continue
            try:
                json.loads(raw)
                checked += 1
            except Exception as e:  # noqa: BLE001
                corrupted.append({"file": str(jf.relative_to(_BASE)),
                                  "error": str(e)[:100]})
    complete = attempted >= n
    # 🔴 2026-09-22 第 37 轮修（错报治理 · 本轮抓到最大的一条）：
    #    原来只返回 `json_files`(=分母) + `corrupted`(抽样的结论) + `ok`，
    #    **不返回"到底检查了多少"**。实测生产 store：2681 个 .json 只解析 **159** 个（**5.9%**）——
    #    全量解析要 2317ms、超 selfscan 的 500ms 预算（剪掉 native_browser 那 34MB 浏览器剖析后
    #    仍要 679ms）⇒ **抽样是必要的**，问题不在抽样，在**把抽样结论说成全量结论**。
    #    `corrupted: []` 一交出去，读的人就会得出"全库 2681 个都没坏"。
    #    ⇒ 现在把**分母 / 分子 / 覆盖口径**一并交出，并写明"未检查 ≠ 没有"。
    return {"json_files": n, "json_checked": checked, "json_attempted": attempted,
            "json_unreadable": len(unreadable),
            "json_empty": len(empty),
            "coverage": "full" if complete else "sampled",
            "coverage_note": ("全量解析（%d/%d）" % (checked, n) if complete else
                              "**抽样** %d/%d（%.1f%%）—— 其余 %d 个**没检查**，"
                              "不许读成『没有损坏』"
                              % (attempted, n, 100.0 * attempted / max(1, n), n - attempted)),
            "missing_dirs": missing,
            "corrupted": corrupted,
            "unreadable": unreadable,
            "empty": empty,
            # 不是 JSON 文件却叫 *.json 的目录 / 浏览器 JSONL 组件：单列，**不计红**，但不藏
            "odd_dirs": [str(p.relative_to(_BASE)) for p in odd_dirs],
            "foreign_skipped": len(foreign),
            # ok 的**作用域**是本轮检查范围，不是"整个 store" —— 口径写在 ok_scope 里
            "ok": not missing and not corrupted,
            "ok_scope": "本轮检查范围内（覆盖口径见 coverage / coverage_note）"}


def check_audit(last=500):
    """审计体检（信号分级版 · 口径 R-H167 定清）。

    五档信号（**这是"病灶怎么分"，不是"成绩怎么算"**）：
      runtime   运行时故障——真正要追的病（默认算 anomaly）
      guard     护栏拦截——内网/安全策略/演练被门禁挡下：护栏在正常工作（不算病，如实列出）
      trace     测试足迹——测试件（命中共用排除表）/探针/历史长程残留（不算病，可溯）
      legacy    V5 遗留服务——已登记为"未迁移"：不报警，但 svc_inspect 仍能显式查到（≠ 删除）
      recovered 历史掉线且当前已探活在线：如实报"已恢复"，不算现行故障

    读数口径（**别用错尺子** · R-H167）：
      · `anomalies` = 窗口内 `_ANOMALY_EVENTS` 的**全部事件条数**，恒等于
        runtime + guard + trace + legacy + recovered —— **它含"已恢复"，不是净化成绩**。
        它是"报警源总量"：净化刀不改变它（实测：净化前后都是 20）。
      · **净化成绩只看 `runtime_faults`**。前后对比必须带这条分母，
        不许用"排除了多少"代替"剩下多少"。
    """
    from .store import query_log
    # 净化刀（R-H157）：排除表**引用** trace_store 那一张（唯一真相源，不另抄一份）
    from .trace_store import SELFTEST_HINTS as _SELFTEST_HINTS, DRILL_KINDS as _DRILL_KINDS
    # V5 遗留服务：登记为"未迁移" —— 不报警，但 svc_inspect 仍可显式查到（legacy ≠ 删除）
    _LEGACY_SERVICES = {
        "payment_gateway", "blockchain_bridge", "social_trading_v2", "monitor_service",
        "backtest_api_v2", "cis_harvesting_v2", "quant_api", "cis_v42_trader",
        "crypto_gateway", "gbt_wallet_api", "gbt_cap_bridge", "hcl_control", "gate_daemon"}

    def _hit(hint: str, text: str) -> bool:
        """词边界命中：**不许裸子串**（R-H158 实测教训：`test_` 撞上 `backtest_api_v2` 假阳性）。"""
        i = text.find(hint)
        while i >= 0:
            left_ok = i == 0 or not (text[i - 1].isalnum() or text[i - 1] == "_")
            j = i + len(hint)
            right_ok = j >= len(text) or not (text[j].isalnum() or text[j] == "_")
            if left_ok and right_ok:
                return True
            i = text.find(hint, i + 1)
        return False
    rows = query_log(limit=last)

    # 恢复证据索引：窗口内每 kind 的成功调用（audit('ok')）——error 之后有 ok = 已恢复。
    # 性能：单遍预扫描同时完成轻字段归一（rows 行已是 dict，避免二次全量解析）。
    ok_kinds = set()
    for _r in rows:
        if _r.get("event") == "ok":
            _m = _r.get("meta") or {}
            _k = _m.get("kind") or _m.get("services") or _m.get("name")
            if isinstance(_k, str):
                ok_kinds.add(_k)
            elif isinstance(_k, list):
                ok_kinds.update([x for x in _k if isinstance(x, str)])
    by_event = {}
    by_kind = {}
    by_signal = {"runtime": 0, "guard": 0, "trace": 0, "legacy": 0, "recovered": 0}
    samples = []
    for r in rows:
        ev = r.get("event", "")
        if ev not in _ANOMALY_EVENTS:
            continue
        meta = r.get("meta") or {}
        kind = meta.get("kind") or meta.get("task_id") or meta.get("name") or meta.get("services", ["?"])
        if isinstance(kind, list):
            kind = [k for k in kind if k not in _RESERVED_SERVICES] or None
        if kind is None:
            continue  # 纯预留端口足迹
        key = kind if isinstance(kind, str) else ",".join(map(str, kind))
        reason = str(meta.get("reason", ""))

        # 信号分级（v2 源头分类版——判例法退役）：
        # user_error 事件天然不算 anomaly（不在 _ANOMALY_EVENTS 里），
        # error 事件现在只剩真故障——不可改名的历史足迹只剩 T00（下面单独一档）。
        if meta.get("probe"):
            sig = "trace"     # 探针/观察者足迹（源头标记）：不是现行故障——最优先判定
        elif ("内网" in reason or "安全策略" in reason
                or str(meta.get("kind") or "") in _DRILL_KINDS):
            # 护栏拦截：内网 / 安全策略 / 演练被门禁挡下 —— 护栏在正常工作（不算病，如实列出）
            sig = "guard"
        elif any(_hit(h, str(key).lower()) for h in _SELFTEST_HINTS):
            # R-H167：测试件（命中共用排除表）**归 trace，不归 guard**。
            # guard 的含义是"护栏在正常工作"，测试件是"根本不该进账的测试噪声"；
            # 两件事挤在一格，读数的意思就变了（实测：7 条测试件 pipeline_blocked 被读成"护栏忙了 7 次"）。
            # 顺手退役最后一个前缀判例（`startswith("t-")`）——不再靠前缀猜，改由排除表裁决（R-H157 的本意）。
            # 词边界匹配（R-H158）：堵掉 test_ 撞 backtest_api_v2 的假阳性。
            sig = "trace"
        elif any(s.strip() in _LEGACY_SERVICES for s in str(key).split(",")):
            # R-H158：支持**多服务逗号串**拆解（实测：鉴权/服务类 svc_down 的 key 是拼接串）
            sig = "legacy"   # V5 遗留服务：不算 anomaly（仍可被 svc_inspect 显式查到）
        elif key.startswith("T00"):   # 历史长程测试任务（审计轮转前的旧记录，不可改名）
            sig = "trace"
        elif ev == "svc_down" and _service_recovered(key):
            sig = "recovered"  # 历史掉线且当前已探活在线：如实报已恢复，不算现行故障
        elif ev == "svc_down":
            # 多服务合并行：逐服务探活，全部在线则视为已恢复（修复验收提出的盲点）
            names = [n.strip() for n in str(key).split(",") if n.strip()]
            if names and all(_service_recovered(n) for n in names):
                sig = "recovered"
            else:
                sig = "runtime"
        elif ev == "error" and key in ok_kinds:
            sig = "recovered"  # 故障后同能力已有成功调用：如实报已恢复，不算现行故障
        else:
            sig = "runtime"

        by_event[ev] = by_event.get(ev, 0) + 1
        by_signal[sig] = by_signal.get(sig, 0) + 1
        # R-H298（2026-09-22 根因修复）：多服务合并行**逐服务分账**。
        # 病根：`meta.services` 本来是**列表**，被这里 `",".join(...)` 压成**一个 key** ⇒
        #   报出来的"一个 capability"其实是 13 个 V5 遗留服务（payment_gateway, blockchain_bridge, …），
        #   读的人既看不出是哪些、也没法逐个处置。
        # 口径（必须写明，否则又是一处误读）：
        #   by_event / by_signal **按事件计**（不受此改动影响）；
        #   by_kind 是**逐服务明细** ⇒ 它的合计**不要求等于**事件数。
        _members = [s.strip() for s in str(key).split(",") if s.strip()] or [str(key)]
        for _m in _members:
            by_kind.setdefault(_m, {"runtime": 0, "guard": 0, "trace": 0, "legacy": 0,
                                    "recovered": 0})[sig] += 1
        if sig == "runtime" and len(samples) < 5:
            samples.append({"event": ev, "kind": key, "reason": reason[:120],
                            "at": r.get("iso")})

    total = sum(by_event.values())
    runtime = by_signal["runtime"]
    # R-H167 口径（机器可读，给面板/沙盘/图纸取数用）：**别拿 anomalies 当净化成绩**。
    scope = {
        "anomalies": ("窗口内 _ANOMALY_EVENTS 的全部事件数"
                      "（= runtime+guard+trace+legacy+recovered，含已恢复）——不是净化成绩"),
        "scoreboard": "runtime_faults",
        "why": "guard/trace/legacy/recovered 都不是现行故障；只有 runtime 才是要追的病",
        "before_after_rule": "净化前后对比必须同路径同窗口，且必须带 runtime_faults 这条分母",
    }
    return {"window": last, "anomalies": total, "runtime_faults": runtime,
            "by_event": by_event, "by_signal": by_signal,
            "errors_by_kind": by_kind, "recent_runtime": samples,
            "reading_scope": scope,
            "ok": runtime == 0}


def alerts(last=500):
    """声带：近期异常摘要 + 根源线索（分级版）。

    R-H297（2026-09-22 根因修复）：`quiet` 原来等价于 `runtime_faults == 0`，
    于是出现**读起来自相矛盾**的一屏：`quiet: true` 与 `anomalies: 4` 并排显示。
    病根是**字段名骗人**：它只说「没有现行故障」，却长得像「一切正常」。
    后果不是难看，是**给故障喘息** —— 人扫一眼 `quiet: true` 就不往下看了，
    而那几条（`svc_down` / `pipeline_blocked`）会一直挂着没人碰。
    修法：`quiet` 保留（不破坏既有消费者），**另加无歧义的三个字段**，
    并把「quiet 到底代表什么」在 `quiet_means` 与 `note` 里写死。
    """
    a = check_audit(last)
    if a["anomalies"] == 0:
        return {"quiet": True, "quiet_means": "窗口内确实什么都没有",
                "any_signal": False, "needs_a_look": False, "anomalies": 0,
                "note": "窗口期内无异常事件"}
    top = sorted(a["errors_by_kind"].items(),
                 key=lambda x: -(int(x[1].get("runtime", 0) or 0) * 100
                                 + int(x[1].get("guard", 0) or 0) * 10
                                 + int(x[1].get("trace", 0) or 0)
                                 + int(x[1].get("legacy", 0) or 0)))[:5]
    runtime_faults = a["runtime_faults"]
    # 🔴 2026-10-13 修（框架禁红黄 · 追到的根因就在这一行）：
    #    原来 `needs_a_look` **无条件 True** —— 只要"异常事件数≠0"就置位，于是
    #    **测试足迹**（实测：`_def_probe.txt`，磁盘上没有这个文件、**也不是在册能力位**）
    #    把这条点亮 ⇒ alerts 飘红 ⇒ 深扫报红。真口径只有两条：
    #      ① 有**现行故障**（runtime/guard）⇒ 必须人看；
    #      ② 异常落在**在册能力位**上 ⇒ 必须人看；
    #      只剩"不在册名字上的 trace 足迹" ⇒ 那是测试残留，**不置位**，只如实列出。
    try:
        from .caps_registry import BENIGN_CAPS as _REG
        _names = set(_REG.keys())
    except Exception:                                        # noqa: BLE001
        _names = set()
    _reg_hits, _stray = {}, {}
    for _k, _v in (a.get("errors_by_kind") or {}).items():
        (_reg_hits if _k in _names else _stray)[_k] = _v
    _guard = int((a.get("by_signal") or {}).get("guard", 0) or 0)
    _look = bool(runtime_faults or _guard or _reg_hits)
    return {"quiet": runtime_faults == 0,
            "quiet_means": ("窗口内没有**现行故障**（runtime_faults=0）；"
                            "但异常事件数不为 0 ⇒ 仍需人逐条看一眼"),
            "any_signal": True,
            "needs_a_look": _look,
            "needs_a_look_means": ("真故障(runtime/guard) 或 在册能力位异常 ⇒ True；"
                                   "只有不在册名字上的测试足迹 ⇒ False"),
            "registered_anomalies": len(_reg_hits),
            "unregistered_footprints": sorted(_stray)[:8],
            "anomalies": a["anomalies"],
            "runtime_faults": runtime_faults,
            "by_signal": a["by_signal"],
            "by_event": a["by_event"],
            "top_offenders": [{"capability": k, "runtime": v.get("runtime", 0),
                                "guard": v.get("guard", 0), "trace": v.get("trace", 0),
                                "legacy": v.get("legacy", 0),
                                "total": sum(int(v.get(x, 0) or 0)
                                             for x in ("runtime", "guard", "trace",
                                                       "legacy", "recovered"))}
                               for k, v in top],
            "note": ("runtime=要追的病；guard=护栏正常工作；trace=测试足迹；"
                     "legacy=历史缺席；recovered=历史掉线已恢复。"
                     "⚠️ **别只看 quiet**：anomalies 不为 0 就得逐条看，"
                     "否则那几条会一直挂着没人碰。")}


def _autofix(sec_store):
    """安全自动修复：补目录、损坏 JSON 备份后重置。返回修复清单。"""
    fixed = []
    store = __import__("gbt_allinone._paths", fromlist=["STORE_DIR"]).STORE_DIR
    for d in sec_store.get("missing_dirs", []):
        (store / d).mkdir(parents=True, exist_ok=True)
        fixed.append(f"补建目录 store/{d}")
    for c in sec_store.get("corrupted", []):
        f = _BASE / c["file"]
        bak = f.with_suffix(f.suffix + f".corrupt-{int(time.time())}")
        f.rename(bak)
        default = {"next_id": 1, "tasks": []} if f.name == "tasks.json" else {}
        f.write_text(json.dumps(default, ensure_ascii=False), encoding="utf-8")
        fixed.append(f"损坏 JSON 已备份重置: {c['file']} -> {bak.name}")
    return fixed


def scan(autofix: bool = False, full: bool = False) -> dict:
    routing = check_routing()
    modules = check_modules()
    store_sec = check_store(full=full)
    audit_sec = check_audit()
    stubs = sorted(_routed_kinds()[2])

    findings = []
    if not routing["ok"]:
        findings.append("P0 路由断连: " +
                        (f"未路由能力 {routing['unrouted']} " if routing["unrouted"] else "") +
                        (f"幽灵路由 {routing['ghost_routes']}" if routing["ghost_routes"] else ""))
    if not modules["ok"]:
        findings.append(f"P0 模块导入失败: {[b['module'] for b in modules['failed']]}")
    if not store_sec["ok"]:
        findings.append(f"P0/P1 存储异常: 缺目录{store_sec['missing_dirs']} 损坏{len(store_sec['corrupted'])}个")
    if not audit_sec["ok"]:
        findings.append(f"P1 运行时故障 {audit_sec['runtime_faults']} 起: "
                        f"{ {k: v['runtime'] for k, v in audit_sec['errors_by_kind'].items() if v['runtime'] > 0} }")

    verdict = "clean"
    if any(f.startswith("P1") for f in findings):
        verdict = "P1"
    if any(f.startswith("P0") for f in findings):
        verdict = "P0"

    fixed = _autofix(store_sec) if autofix else []
    if fixed:
        store_sec = check_store()  # 复验
        findings.append("已自动修复: " + "; ".join(fixed))

    return {
        "verdict": verdict,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "findings": findings,
        "sections": {
            "routing": routing,
            "modules": modules,
            "store": store_sec,
            "audit": audit_sec,
            "stub_gaps": stubs,
        },
        "capabilities_total": routing["registered"],
        # 🔴 2026-09-22 第 37 轮加（错报治理）：**覆盖口径必须一眼可读**。
        #    原来那句 note 写的是「clean=五维**全过**」，而存储维度实测只检查了 **5.9%**
        #    ⇒ 五维里的"全过"是假的。现在把每个维度的覆盖口径摊在顶层，
        #    并把 note 改成**带前提**的说法（"在本轮检查范围内"），
        #    读者不必去翻 sections 才知道哪个维度是抽样的。
        #    另：`check_audit` 只读**最后 `window` 行**（窗读），**不是全账本** ⇒
        #    它的口径如实写成 `window(N 行)`，不许默认成 "full"（那又是同一个病）。
        "coverage": {
            "routing": "full",
            "modules": "full",
            "store": store_sec.get("coverage"),
            "audit": ("window(%s 行)" % audit_sec.get("window")
                      if audit_sec.get("window") is not None else "full"),
            "stub_gaps": "full",
            "note": "本表逐维标明覆盖口径；**未检查 ≠ 没有**。",
        },
        "coverage_incomplete": [
            k for k, v in (("store", store_sec.get("coverage")),
                           ("audit", "window" if audit_sec.get("window") is not None else "full"))
            if v != "full"],
        "note": "P0=断连/损坏必须修；P1=异常在发生；"
                "clean=五维**在本轮检查范围内**未发现问题（**不是**『五维全量验过』——"
                "抽样维度见 coverage / coverage_incomplete；桩缺口如实列出不算病）",
    }
