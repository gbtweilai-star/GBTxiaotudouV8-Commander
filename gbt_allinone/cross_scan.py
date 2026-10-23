"""GBT小土豆V8 · 交叉扫（cross_scan）——深度穿透式交叉验证。

设计（Owner 定调 2026-09-11）：扫描器各自报告不算数——让它们互相咬：
每个扫描器的输出成为其他扫描器的输入，穿透到磁盘/导入/运行时三层。

十个交叉维度：
  A. 注册表 ↔ api 路由    声称的能力都有真实路由
  B. 模块清单 ↔ 导入      selfscan._MODULES 全部可导入
  D. 文档声称 ↔ 注册表    文档数字与真实对账
  E. 测试数 ↔ 测试文件    测试函数真实存在
  F. 审计 ↔ 注册表        审计里的 kind 无幽灵
  G. 相对导入 ↔ 磁盘      包内 import 闭包完整（无断链）
  H. 注册表 ↔ 运行时      全能力逐个可达（无僵尸）
  X. 多扫描器互证         selfscan/truth/ghost/hygiene/signature/inventory 判定一致
  V. 视图对账             inventory 双视图 + 异物清零
  W. 家根影子 ↔ 真身      根级同名 .py / 同名子目录清零（只读检查器 · O49）

🔴 **上面是「设计上有哪十个」，不是「跑了哪几个」** —— 别把声明读成覆盖：
  现读（2026-09-25 第 42 轮起）：**实现 6 个**（`A/B/G/V/W/X`；`deep=True` 再加 `H` ⇒ **7 个**）；
  **`D/E/F` 只有名字**（如实单列在 `dims_unimplemented` 里，不混进覆盖数）。
  为什么不硬凑：`F` 维照最自然的方式写会报 **86 条假警**（参考集不存在，见台账 F12/F5）；
  `D` 维的来源**已经存在**（`audit-injection-honesty.py` 那条「N个cap 必须等于活注册表」，
  且已是常设判据）⇒ 在这里再写一遍就是**抄第二份判据**，本仓明令禁止；
  `E` 维没有任何「声称的测试数」来源。**参考集不存在时写它，等于造一台报假警的机器。**
"""
import ast
import re
import time
import warnings  # R-H295：接管 ast.parse 的无效转义警告，别漏 stderr、别静默放行
from pathlib import Path

_BASE = Path(__file__).resolve().parent
_PKG = _BASE


def _v_dim(check_inventory=None) -> tuple:
    """V 维 · 视图对账（inventory 双视图 + 异物清零）—— 返回 `(findings, stats)`。

    🔴 2026-09-25 实现（在这之前，`V` 只出现在维度声明里，全文件没有第二处引用）。
    判据两条，都要能机检：
      ① 异物必须清零（`foreign > 0` ⇒ 有该处置的遗漏）；
      ② **双视图要算得平**：`你看到的（家根总项）` 必须等于六类之和。
         ②才是「对账」的本体 —— **只读一个数字不叫对账，加减法要闭合**。

    ⚠️ 安全红线：**必须 `fix=False`**。`inventory.scan(fix=True)` 会**真删文件**；
       扫描器里绝不许带清理动作 ——「扫一下」不该改动任何东西。

    为什么抽成独立函数：**为了让用例能在不跑整轮扫描的情况下验它**。
    整轮 `cross_scan.scan()` 要 15 秒，而这一维只要 0.4 秒；抽出来之后
    「真的传了 fix=False 吗」「双视图不平会不会报」这两条都能毫秒级验。
    `check_inventory` 只给用例注入桩；生产路径永远是 None ⇒ 真去调 inventory。
    """
    findings_out: list = []
    stats: dict = {"ran": False}
    try:
        if check_inventory is None:
            from . import inventory as _inv

            check_inventory = _inv.scan
        # ↓↓↓ 这行是安全红线：**只读**。任何时候都不许在这里传 fix=True。
        iv = check_inventory(fix=False)
        dv = iv.get("dual_view") or {}
        its = iv.get("items") or {}
        seen = int(dv.get("你看到的（家根总项）", -1))
        foreign = int(dv.get("异物（foreign）", len(its.get("foreign") or [])))
        by_class = {k: len(v or []) for k, v in its.items()}
        total = sum(by_class.values())
        stats = {"ran": True, "seen": seen, "by_class": by_class, "foreign": foreign,
                 "sum_by_class": total, "balanced": (seen == total), "fixed": iv.get("fixed")}
        if foreign:
            findings_out.append({"dim": "V", "issue": f"异物未清零: {foreign} 项（该处置的遗漏）"})
        if seen >= 0 and seen != total:
            findings_out.append({"dim": "V",
                                 "issue": f"双视图对不上: 家根总项 {seen} ≠ 六类之和 {total}（差 {seen - total}）"})
    except Exception as ve:  # noqa: BLE001
        findings_out.append({"dim": "V", "issue": f"视图对账跑不动: {type(ve).__name__}: {str(ve)[:60]}"})
    return findings_out, stats


def _rel_imports(src, issues=None):
    """源码里的**硬**相对导入（AST）：返回去重后的 [(点数, 模块首段), ...]。
    会被当成真 import（G 维今天的假阳性就是这么来的：那是**提到**，不是**用了**）。
    另外**只算硬导入**：包在 `try:` 里的导入是"优雅降级占位"（家规第 10 条：
    wallet/bridge/ledger 这类业务模块本就该在框架里缺席），不算断链。

    R-H295：
      ① `ast.parse(src)` 对**无效转义序列**会发 SyntaxWarning，文件名显示成 `<unknown>`
         （ast.parse 的默认 filename）—— 之前没人接管，于是它直接漏到 stderr 成了噪声，
         而报的其实是**被扫文件**里的坏转义（未来 Python 会变成报错）。现在显式接管。
      ② 原来 `except Exception: return []` —— 「解析不了」被当成「没有相对导入」，
         断链检测对这类文件**静默放行**。现在把解析失败如实记进 issues（调用方上报），
         不再把「不知道」说成「没问题」。
    """
    with warnings.catch_warnings(record=True) as _cw:
        warnings.simplefilter("always")
        try:
            # R-H295：本仓有 10 个 .py 带 UTF-8 BOM（Windows PowerShell 写盘的既有约定，
            # caps_registry.py / __init__.py 都在其中）。带 BOM 的文本喂给 ast.parse 会抛
            # `SyntaxError: invalid non-printable character U+FEFF` —— 修**读方**，不删 BOM
            # （BOM 是既有约定，删它会动 10 个文件的字节）。
            tree = ast.parse(src.lstrip("\ufeff"))
        except Exception as e:  # noqa: BLE001
            if issues is not None:
                issues.append("解析失败（该文件断链检测未执行）: %s: %s"
                              % (type(e).__name__, str(e)[:70]))
            return []
    if issues is not None:
        for _w in _cw:
            if issubclass(_w.category, SyntaxWarning):
                issues.append("第 %s 行无效转义（未来 Python 会报错）: %s"
                              % (getattr(_w, "lineno", 0) or 0, str(_w.message)[:70]))
    out = set()

    def walk(node, guarded=False):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Try):
                for b in child.body:                      # try 体内 = 受保护（可选）
                    walk(b, True)
                for b in list(child.orelse) + list(child.finalbody) + \
                        [s for h in child.handlers for s in h.body]:
                    walk(b, guarded)
                continue
            if isinstance(child, ast.ImportFrom) and child.level and child.module and not guarded:
                out.add((child.level, child.module.split(".")[0]))
            walk(child, guarded)

    walk(tree)
    return sorted(out)


def _audit(event, meta):
    try:
        from .store import audit
        audit(event, meta)
    except Exception:
        pass


_X_SCANNER_KINDS = ("selfscan", "truth_scan", "ghost_guard",
                    "file_hygiene", "signature_guard", "inventory")

# 侧效应能力：无需参数调用就会产生真实后果，所以 H 维逐个轻调用必须跳过（零副作用铁律）。
# 🔴 2026-09-24 深修（单一真源）：本名单原来是从探测视角**手抄**的 13 条，
# 与 `preflight._STATE_CHANGING_KINDS`（改状态的唯一定义，11 条）各算各的 ——
# 9 个会改状态的位（`root_fix`/`wf_run`/`wf_cache_clear`/`sched_tick` 等）不在
# 探测名单里，H 维当轮就真调过它们（`wf_cache_clear` 真清了传输缓存）。
# 现在：**改状态的完整名单从 preflight 派生**；本文件只保留纯探测语义的 4 条专项
# （跟"改状态"无关，纯探测护栏：防递归 / 防无参完整循环）。
# 面板等消费方引用本名单即可拿到**并集**；要"会不会改状态"的判据用
# `preflight.is_side_effect()` / `state_changing_kinds()`，不许再各抄一份。
from .preflight import state_changing_kinds as _state_changing_kinds

# 纯探测专项（跟"改状态"无关，是探测自身的护栏）：
#   · 部署/发布/队列/镜像塑形 —— 无参调用就是真实动作的前置
#   · 出网/外部模型/自主环/完整认知循环 —— 无参即真扫或真烧钱
#   · 防递归：扫描器不能扫自己
_PROBE_ONLY_KINDS = frozenset({
    "osint_scan", "pipeline_submit", "mirror_shape",
    "one_key_deploy", "deploy_queue", "think_loop", "autopilot",
    "sec_llm", "llm_chat", "devour_github",
    "cross_scan",
})

PROBE_SKIP_KINDS = _PROBE_ONLY_KINDS | _state_changing_kinds()

# 🔴 2026-09-25 立：H 维的**整体预算**（Owner 令「继续扫描所有故障」期间实测逼出来的）。
#
# 症状（真跑，不是推演）：空参 `cross_scan` **两次都 >560s 不返回**；
# `scan(deep=False)` 只要 17.9s ⇒ 钱全花在 H 维。
#
# 根因（读源码 + 拿运行时普查的**逐位耗时表**对账，两处证据合得上）：
# H 维（本文件 355-372 行）对每个 `safe` 且不在 `PROBE_SKIP_KINDS` 里的能力位
# **就地同步** `run_task(name, {"_probe": True})`，**没有任何时间预算**。
# 而 `PROBE_SKIP_KINDS` 只排除**侧效应**位，**不排除"很慢的只读扫描器"** ⇒
# 这些位被逐个真调（下表是 `caps-runtime-census` 的现读耗时）：
#     sec_scan 299.7s · sec_chain 269.6s · sec_surface 26.6s · file_hygiene 8.6s ·
#     libtv_workflow 6.5s · sec_defenses 4.5s · caps_called_audit 4.0s · tentacle_status 3.1s
#     ……（其余 90 位多为 0.2–1s）
# 光把已量到的加起来就 **>620s** ⇒ **"不返回"不是死锁，是无上界的求和**。
# 而安全面新接线（第 7 节那 12 个位）让这个和又长了一截 —— 同一个病因，剂量变大。
#
# 取舍（为什么是"加预算 + 如实报没跑到"，而不是别的）：
#   · ❌ 不许改 `deep=False`：那等于**悄悄把 H 维整条砍掉**（2026-09-25 已撤回该建议）。
#   · ❌ 不许缩 `dims`：覆盖静默缩水，本仓最忌。
#   · ✅ 加**整体预算**，超了就**如实报出"还差哪几位没探到"**。
#     有界 + 诚实 > 无界 + 根本跑不起来（后者覆盖率是 **0**，更差）。
# 🔴 读数纪律：`deadline_hit: true` 时**绝不许**把 `deep_coverage` 念成"全扫过了" ——
#    `not_probed` 就是"这次没跑到"的名单，它既不是通过、也不是失败。
# 🔴 2026-09-25 立（**同一次实测的第二刀**）：H 维要跳过的**慢位**。
#
# 为什么光有整体预算不够（**我第一版就只加了预算，当场被自己的验证打回**）：
# 预算是"**起下一次调用之前**看一眼时钟"，它只约束**调用次数**，**约束不了单次调用的时长**。
# 实测证据：给 30s 预算真跑，**120s 都没回来** —— 因为循环早在 30s 前就起了
# `sec_chain` 那一发，而它自己要走 269s ⇒ 单发就把预算冲穿了。
#
# 判据（不是"猜谁慢"，是**量出来的**）：`caps-runtime-census` 现读 98 位只读位的耗时，
# 合计 **735.3s**，其中 ≥5s 的只有 6 位、合计 **672.2s**；**扣掉它们只剩 63.0s**。
#   sec_scan 299.7s · sec_chain 269.6s · sec_surface 26.6s · file_hygiene 8.6s ·
#   libtv_workflow 6.5s（`cross_scan` 61.1s 本来就在 `_PROBE_ONLY_KINDS` 里，防递归）
# ⇒ 跳掉这 5 位：H 维从 ~674s 降到 ~63s，进得了预算。
#
# 语义上也自洽：H 维自己的 docstring 写的就是「全能力**逐个轻调用**」——
# 一发 5 分钟的安全全扫**不是轻调用**，它是另一条专门的扫描线（`_X_SCANNER_KINDS` 已在跑）。
# 跳过**必须可见**（`deep_coverage.skipped_slow` + 量到的耗时），不许当成"探过了没问题"。
# ⚠️ 2026-10-17：名册改为「**量准的** ∪ **显式未量准的**」两桶（见下方 `_SLOW_KINDS` 的定义）。
#   原来这一行是一张手写 set，19 位里有 14 位**从没量过耗时** ⇒ 被
#   `test_cross_scan_h_budget` 咬成"名册只是口号"。现在位置留白、名册由两桶合成，别再往这里加。
_SLOW_KIND_COST_S = {"sec_scan": 299.7, "sec_chain": 269.6, "sec_surface": 26.6,
                     "file_hygiene": 8.6, "libtv_workflow": 6.5}

# 🔴 2026-10-17 加（留痕 · 名册不许是口号）：`_SLOW_KINDS` 已长到 19 位，而**量准的耗时只有 5 位**
#   ⇒ `test_cross_scan_h_budget::test_slow_roster_is_measured_not_asserted` 当场咬红
#   （"慢位 brain_verify 没有量到的耗时 ⇒ 这份名册只是口号"）。
#   处置**不编数字**、也不假装已量：把其余 14 位**显式登记为「未量准（带理由）」**——
#   它们在 H 维照样被跳过（慢是既定事实），但读数里 `cost_s = null` + 这句理由，
#   读的人能分清「量过 8.6s」与「没量准但确知慢」。**登记 ≠ 忽略**。
_SLOW_KINDS_UNMEASURED = {
    "page_scan": "按页绑定并发扫全树，单跑分钟级；未在预算内量准",
    "comfy_native": "ComfyUI 链路（本机 8188 未起时也会等满超时）",
    "asset_vault_freeze": "卷影/BitLocker/资产清单多点读，分钟级",
    "train_recipe": "训练就绪面现读 torch/CUDA/磁盘，慢且吃 IO",
    "task_manager": "进程表两次采样（CPU 需第二遍），秒级起",
    "db_probe": "SQLite/JSONL 多源只读统计，随库大小线性",
    "caps_called_audit": "近 220 个文件全量 AST 扫，十几秒级",
    "wave_probe": "波形探针逐段采样",
    "brain_health": "五维体检串链（route/execute/tentacle/vision/audit）",
    "console_pages": "多页现读渲染（工作台/3D/画廊/控制台/首页…）",
    "tentacle_comfy_bridge": "卡上 ComfyUI 往返（网络 + 生成）",
    "ghost_guard": "幽灵引号/坏字符全仓扫",
    "tentacle_status": "多触手状态逐根现读",
    "brain_verify": "肉眼验证（截屏 + UIA 读回 + 指纹），秒级到十几秒",
}
# 名册 = 「量准的」∪「显式未量准的」——两桶都可见，不许把未量准混进已量。
_SLOW_KINDS = frozenset(set(_SLOW_KIND_COST_S) | set(_SLOW_KINDS_UNMEASURED))

H_BUDGET_S = 240.0

# 专项名单单独导出，供想区分"改状态"与"探测专项"的读数用（如 caliber 对账）。
PROBE_ONLY_KINDS = _PROBE_ONLY_KINDS

# R97 · 改法 3a：X 维门禁失败分因（不再有笼统 gate_error 整句）
GATE_CHILD_RC = "child_rc"                   # 子进程 rc != 0
GATE_CHILD_TIMEOUT = "child_timeout"         # 超时
GATE_CHILD_NO_OUT = "child_out_missing"      # --out 文件不存在
GATE_CHILD_BAD_JSON = "child_out_not_json"   # --out 内容不可解析

_X_CHILD_SRC = r"""
import json, sys
sys.stdout = sys.stderr          # R97 · 改法 3b：结果只走 --out，print 一律不污染结果流
sys.path.insert(0, sys.argv[1])
from gbt_allinone.api import run_task
kinds = json.loads(sys.argv[2])
out_path = sys.argv[3]
verdicts = {}
sections = {}
for kind in kinds:
    try:
        r = run_task(kind, {})
        b = r.get("gbt_result", r) if isinstance(r, dict) else {}
        res = b.get("result", {}) if isinstance(b, dict) else {}
        v = res.get("verdict") or res.get("status")
        if kind == "ghost_guard":
            v = "clean" if res.get("clean") else "dirty"
        verdicts[kind] = v
        if kind == "selfscan":
            sections = res.get("sections", {}) or {}
    except Exception as e:
        verdicts[kind] = "ERROR:%s" % (str(e)[:30],)
with open(out_path, "w", encoding="utf-8") as fh:
    json.dump({"verdicts": verdicts, "selfscan_sections": sections}, fh,
              ensure_ascii=False)
"""


def _x_run_isolated(kinds=_X_SCANNER_KINDS, timeout_s: int = 240, store_dir=None,
                    child_src=None) -> dict:
    """X 维：在**子进程 + 隔离 store** 里跑 6 个扫描器（O54 · 方案 A）。

    O53：`_paths.STORE_DIR` 在 `import gbt_allinone` 那一刻被钉成常量 —— 同进程内设
    `GBT_STORE_DIR` 对它无效，所以必须**先把环境变量设好、再起子进程**。
    成功 = 门禁跑完（**生产主账本零足迹**）；跑不完 -> `gate_error` 装**分因码**，
    由 scan() 落一条 `health_channel_failed` 到主账本 —— 《终端失败必须响》第二十五章。
    R97 · 改法 3：结果**只走 `--out` 文件**，stdout / stderr 只进 `gate_detail` 日志、
    不参与判据；判定优先级写死：timeout -> rc -> out 缺失 -> out 不是 JSON。
    store_dir 只给判别性负对照用（指到假生产 -> 必须看到足迹）；
    child_src 只给判别性负对照用（注入噪声 / 坏 JSON / 超时 / 退码）。
    """
    import json as _json
    import os as _os
    import shutil as _shutil
    import sys as _sys
    import tempfile as _tempfile
    from subprocess import TimeoutExpired as _TimeoutExpired

    from .tools.native_rc import run_native

    iso = store_dir or _tempfile.mkdtemp(prefix="gbt_cross_scan_iso_")
    env = dict(_os.environ)
    env["GBT_STORE_DIR"] = str(iso)
    env["PYTHONUTF8"] = "1"
    out = {"verdicts": {}, "selfscan_sections": {}, "gate_error": None,
           "gate_detail": "", "iso": str(iso), "child_rc": None}
    src = _X_CHILD_SRC if child_src is None else str(child_src)
    fd, out_name = _tempfile.mkstemp(prefix="gbt_cross_scan_out_", suffix=".json")
    _os.close(fd)
    out_file = Path(out_name)
    try:
        rc, stdout_b, stderr_b = run_native(
            [_sys.executable, "-c", src, str(_PKG.parent), _json.dumps(list(kinds)),
             str(out_file)],
            timeout=timeout_s, env=env)
        out["child_rc"] = rc
        tail = stderr_b.decode("utf-8", "replace")[-200:]
        if rc != 0:
            out["gate_error"] = GATE_CHILD_RC
            out["gate_detail"] = "rc=%d stderr=%s" % (rc, tail)
        elif not out_file.exists() or out_file.stat().st_size == 0:
            # 🔴 2026-09-22 第 40 轮修（错报治理 · **归因错 + 死分支**）：
            #    `out_file` 是上面 `mkstemp` 造出来的 ⇒ **它必然 exists**（空文件也算存在），
            #    所以原来那句 `elif not out_file.exists(): GATE_CHILD_NO_OUT` 是**死代码**，
            #    永远轮不到。"子进程退出 0 但一个字节都没写"于是掉进下面的解析分支，
            #    被报成 `child_out_not_json`（「out 内容不可解析」+ JSONDecodeError: Expecting value…）
            #    —— 读的人会去查"子进程的 JSON 序列化哪儿写坏了"，而真相是**它根本没写**。
            #    实测（本轮受控子进程）：③「退出 0 不写 out」报的是 `child_out_not_json`；
            #    修后报 `child_out_missing`（④「写了但不是 JSON」仍报 `child_out_not_json`）。
            #    ⇒ 判据改成**缺失或空**：空文件 = 没写，"没写"与"写了但坏"必须分开归因。
            out["gate_error"] = GATE_CHILD_NO_OUT
            out["gate_detail"] = "rc=0 stdout_bytes=%d stderr=%s" % (len(stdout_b), tail)
        else:
            try:
                payload = _json.loads(out_file.read_text(encoding="utf-8"))
            except Exception as exc:
                out["gate_error"] = GATE_CHILD_BAD_JSON
                out["gate_detail"] = "%s: %s" % (type(exc).__name__, str(exc)[:120])
            else:
                out["verdicts"] = payload.get("verdicts", {}) or {}
                out["selfscan_sections"] = payload.get("selfscan_sections", {}) or {}
                out["gate_detail"] = "stdout_bytes=%d stderr_bytes=%d" % (
                    len(stdout_b), len(stderr_b))
    except _TimeoutExpired:
        out["gate_error"] = GATE_CHILD_TIMEOUT
        out["gate_detail"] = "timeout>%ss" % timeout_s
    except Exception as exc:
        out["gate_error"] = GATE_CHILD_RC
        out["gate_detail"] = "%s: %s" % (type(exc).__name__, str(exc)[:120])
    finally:
        try:
            if out_file.exists():
                out_file.unlink()
        except OSError:
            pass
        if store_dir is None:
            _shutil.rmtree(str(iso), ignore_errors=True)
    return out

def scan(deep: bool = True, h_budget_s: float | None = H_BUDGET_S) -> dict:
    """深度穿透式交叉扫。deep=True 时含 H 维（全能力运行时可达——较慢）。

    `h_budget_s`：H 维的**整体时间预算**（秒）。默认 240s。
      · 传 `None` ⇒ **无预算**（改动前的旧行为，会真的跑几分钟到十几分钟）；
      · 超预算后不再起新调用，把剩下的位**如实记进 `deep_coverage.not_probed`**，
        并置 `deadline_hit: true` —— **没跑到 ≠ 通过**。
    为什么默认有界：无界时空参 `cross_scan` 实测 >560s 不返回（H 维逐个真调，
    而里面躺着 `sec_scan`/`sec_chain` 这类 5 分钟级的只读扫描器）。详见 `H_BUDGET_S` 上方注释。
    """
    t0 = time.time()
    findings = []

    from .caps_registry import BENIGN_CAPS
    _dim_t = {}
    _t_dim = time.monotonic()
    api_src = (_PKG / 'api.py').read_text(encoding='utf-8', errors='replace')

    # A. 注册表 ↔ api 路由
    for name in BENIGN_CAPS:
        if f'"{name}"' not in api_src:
            findings.append({"dim": "A", "issue": f"注册表能力 {name} 在 api.py 无路由"})

    # B. 模块清单 ↔ 导入
    import importlib
    ss_src = (_PKG / 'selfscan.py').read_text(encoding='utf-8', errors='replace')
    m = re.search(r'_MODULES = \[(.*?)\]', ss_src, re.S)
    mods = re.findall(r'"([\w.]+)"', m.group(1)) if m else []
    for mod in mods:
        full = mod if mod.startswith('gbt_allinone') else f'gbt_allinone.{mod}'
        try:
            importlib.import_module(full)
        except Exception as e:
            findings.append({"dim": "B", "issue": f"模块 {mod} 导入失败: {str(e)[:50]}"})

    _dim_t['A+B'] = round(time.monotonic() - _t_dim, 1)
    _audit('cross_scan_dim', {'dim': 'A+B', 's': _dim_t['A+B']})
    _t_dim = time.monotonic()
    # G. 相对导入 ↔ 磁盘（断链检测）· R-H170 起**走 AST**，不再正则扫原文
    for p in _PKG.rglob('*.py'):
        if not p.is_file() or '__pycache__' in str(p) or '.pylibs' in str(p):
            continue
        _parse_issues = []
        rels = _rel_imports(p.read_text(encoding='utf-8', errors='replace'),
                            issues=_parse_issues)
        for _pi in _parse_issues:
            findings.append({"dim": "G", "issue": "%s: %s" % (p.relative_to(_PKG), _pi)})
        for lvl, rel in rels:
            base = p.parent
            for _ in range(lvl - 1):        # 按点数上溯：`..x` 从上一级找真身
                base = base.parent
            if not ((base / f'{rel}.py').exists() or (base / rel / '__init__.py').exists()):
                findings.append({"dim": "G", "issue": f"断链 {p.relative_to(_PKG)}: {'.' * lvl}{rel}"})
        # 子包误用单点（.store 在子包里应双点）
        if p.parent != _PKG and any(lvl == 1 and rel == "store" for lvl, rel in rels):
            findings.append({"dim": "G", "issue": f"{p.relative_to(_PKG)}: 子包用 .store 应为 ..store"})

    # X. 多扫描器互证
    # W. 家根影子 ↔ 真身（O49 · gbt_allinone/tools/shadow_check.py 只读检查器）
    try:
        from .tools.shadow_check import shadow_report
        _srep = shadow_report()
        # 影子存在 ≠ 影子有害。只报「有影子」的话，这条红分不出
        # 「潜在隐患（无人引用、代价 0）」和「活的解析错位（`import 同名` 会拿到根上那个）」，
        # 结果只能长期挂着当噪声。把可达性一并报出来，红才有信息量。
        _exp = _srep.get("exposure", "unknown")
        _reach = _srep.get("shadow_reachable") or {}
        for _n in _srep["shadow_files"]:
            findings.append({"dim": "W",
                             "issue": f"家根影子 .py（与 gbt_allinone/ 同名）: {_n} [exposure={_exp}]"})
        for _n in _srep["shadow_dirs"]:
            findings.append({"dim": "W",
                             "issue": f"家根影子子目录（与 gbt_allinone/ 同名）: {_n} [exposure={_exp}]"})
        if _exp == "live":
            for _h in (_reach.get("hits") or [])[:5]:
                findings.append({"dim": "W", "issue": (
                    f"影子被非限定引用（活错位）: {_h.get('file')}:{_h.get('line')}  {_h.get('text')}")})
        shadow_verdict = _srep["verdict"]
        shadow_exposure = _exp
    except Exception as e:
        shadow_verdict = f"ERROR:{str(e)[:40]}"
        shadow_exposure = "unknown"
        findings.append({"dim": "W", "issue": f"影子检查器不可用: {shadow_verdict}"})

    from .api import run_task
    _x = _x_run_isolated()
    verdicts = _x["verdicts"]
    _ss_sections = _x["selfscan_sections"]
    if _x["gate_error"]:
        findings.append({"dim": "X", "issue": "隔离门禁失败[%s]: %s" % (
            _x["gate_error"], _x["gate_detail"])})
        _audit("health_channel_failed", {"channel": "cross_scan_x",
                                          "reason": _x["gate_error"],
                                          "detail": _x["gate_detail"]})
    bad_verdicts = {k: v for k, v in verdicts.items()
                    if v not in ("clean", "fixed", "restored", "ok")}
    # 数据态豁免：selfscan 在隔离/空 store 下 P0/P1 是数据态（缺目录/审计足迹），
    # 真伪看关键区块：routing（全路由）+ modules（全导入）都 ok = 执行层健康，数据态不算病
    # R-H295：豁免必须**写出来**。原先只把 selfscan 从 bad_verdicts 里 pop 掉，
    # 而 scanners_verdict 里仍原样留着 "selfscan": "P0" —— 读的人只看到 P0、
    # 对应 findings 里却没有 X 条目，**分不清是「已豁免」还是「漏报了」**。
    # 现在 raw 判定与豁免决定并列上报，谁被豁、按什么理由豁，一眼可查。
    _verdict_exempt = {}
    if verdicts.get("selfscan") in ("P0", "P1"):
        try:
            _secs = _ss_sections or {}
            if (_secs.get("routing", {}).get("ok") and _secs.get("modules", {}).get("ok")
                    and not _secs.get("routing", {}).get("unrouted")
                    and not _secs.get("modules", {}).get("failed")):
                bad_verdicts.pop("selfscan", None)
                _verdict_exempt["selfscan"] = {
                    "raw_verdict": verdicts.get("selfscan"),
                    "exempted": True,
                    "why": ("隔离/空 store 下的数据态（缺目录/审计足迹），不是执行层故障；"
                            "关键区块 routing（全路由）+ modules（全导入）均 ok"),
                    "routing_ok": True, "modules_ok": True}
            else:
                _verdict_exempt["selfscan"] = {
                    "raw_verdict": verdicts.get("selfscan"), "exempted": False,
                    "why": "关键区块 routing/modules 未全绿 ⇒ 不豁免，按真故障上报"}
        except Exception as _e:  # noqa: BLE001
            _verdict_exempt["selfscan"] = {
                "raw_verdict": verdicts.get("selfscan"), "exempted": False,
                "why": "豁免判定本身出错: %s" % str(_e)[:60]}
    for k, v in bad_verdicts.items():
        findings.append({"dim": "X", "issue": f"扫描器 {k} 判定异常: {v}"})

    # H. 运行时可达（deep 模式：全能力逐个轻调用）
    # 🔴 2026-09-23 补分母：原版只报 `checked`（≈125），**不报被跳过的 13 条侧效应位**——
    # 读的人看到 "checked 125" 会以为"全扫过了"，而真相是"扫了 125、跳了 13"。
    # 这正是"扫不出问题"的病灶形态：**没有分母，红绿都不算数**。
    # 现在把跳过名单一并交出去（跳过是**设计**，不是缺陷；但**必须可见**）。
    deep_stats = {"checked": 0, "dead": [], "skipped_n": 0, "skipped": [],
                  "unsafe_n": 0, "unsafe": [], "not_probed": [],
                  "skipped_slow": [], "budget_s": h_budget_s,
                  "elapsed_s": 0.0, "deadline_hit": False}
    _dim_t['G'] = round(time.monotonic() - _t_dim, 1)
    _audit('cross_scan_dim', {'dim': 'G', 's': _dim_t['G']})
    _t_dim = time.monotonic()
    if deep:
        skip = PROBE_SKIP_KINDS
        _h_t0 = time.monotonic()
        for name in sorted(BENIGN_CAPS):
            if not BENIGN_CAPS[name].get("safe"):
                deep_stats["unsafe"].append(name)
                continue
            if name in skip:
                deep_stats["skipped"].append(name)
                continue
            # 🔴 第一刀：**慢位不轻调用**（量出来的 5 位，见 `_SLOW_KINDS`）。
            #    光靠下面的预算挡不住它们 —— 单发 269s 就能把预算冲穿。
            if name in _SLOW_KINDS:
                deep_stats["skipped_slow"].append(name)
                continue
            # 🔴 第二刀：预算检查放在**调用之前** —— 超了就不再起新调用。
            #    ⚠️ 它只约束"还能起几发"，**约束不了单发时长**：若哪一位没被量到却要跑几分钟，
            #       这一发仍会冲穿预算。所以 `deadline_hit` 与 `not_probed` 都要如实报出来。
            if h_budget_s is not None and (time.monotonic() - _h_t0) > float(h_budget_s):
                deep_stats["deadline_hit"] = True
                deep_stats["not_probed"].append(name)
                continue
            deep_stats["checked"] += 1
            try:
                _t_probe = time.monotonic()
                r = run_task(name, {"_probe": True})
                _audit("cross_scan_probe",
                       {"name": name, "s": round(time.monotonic() - _t_probe, 1)})
                b = r.get("gbt_result", r) if isinstance(r, dict) else {}
                st = b.get("status") if isinstance(b, dict) else "?"
                if st not in ("ok", "error", "denied"):
                    deep_stats["dead"].append(name)
            except Exception:
                deep_stats["dead"].append(name)
        deep_stats["elapsed_s"] = round(time.monotonic() - _h_t0, 1)
        deep_stats["skipped_n"] = len(deep_stats["skipped"])
        deep_stats["unsafe_n"] = len(deep_stats["unsafe"])
        for name in deep_stats["dead"]:
            findings.append({"dim": "H", "issue": f"僵尸能力（运行时不可达）: {name}"})

    # ── V 维：视图对账（inventory 双视图 + 异物清零）─────────────────────────
    # 🔴 2026-09-25 **实现**（在这一天之前它只出现在维度声明里，没有任何实现）。
    #    判据两条，都要能机检：
    #      ① 异物必须清零（`foreign > 0` ⇒ 有该处置的遗漏）；
    #      ② **双视图要算得平**：`你看到的（家根总项）` 必须等于六类之和。
    #         ②才是「对账」的本体 —— **只读一个数字不叫对账，加减法要闭合**。
    #    ⚠️ 安全红线：**必须 `fix=False`**。`inventory.scan(fix=True)` 会**真删文件**；
    #       扫描器里绝不许带清理动作 ——「扫一下」不该改动任何东西。
    #        （有专门用例盯着这条：见 `test_cross_scan_v_dim.py` 的 kwargs 断言。）
    _v_findings, v_stats = _v_dim()
    findings.extend(_v_findings)

    # ── 维度口径：**声称覆盖必须等于实际覆盖** ──────────────────────────
    # 上一版写死 ["A","B","D","E","F","G","W","X","V"]+["H"] —— 报 10 维。
    # 但实测：D / E / F / V 在整个文件里**各只出现在这一行**，没有任何实现，
    # 全仓也没有任何地方产出这四个维度的 finding。
    # 也就是说：**扫描声称 10 维覆盖，实际只有 6 维能产出发现。**
    # 这正是《反空壳与反假执行律》禁的那类事 —— 把"没扫"折算成"扫了"。
    #
    # 现在的口径：
    #   dims_implemented —— 真有实现、能产出 finding 的维度
    #   dims_unimplemented —— 声明过但没实现的，**如实单列，不混进覆盖数**
    # 🔴 2026-09-25：V 从"未实现"移进"已实现"（上面那段就是它的实现）。
    #    D / E / F 仍留在未实现里 —— 第 41 轮量过：它们的**参考集**还不存在
    #    （F 维照最自然的方式写会报 86 条假警；见台账 F5/F12），不许凭感觉挑一个来源当判据。
    _DIMS_IMPL = ["A", "B", "G", "V", "W", "X"] + (["H"] if deep else [])
    _DIMS_NOT_IMPL = ["D", "E", "F"]
    dims_run = _DIMS_IMPL
    # 🔴 2026-09-22 修（错报治理）：`ok` 原来是 `not findings`，而 findings 里混着 **latent 影子**
    # （家根 tools/ deploy/ 与 gbt_allinone/ 同名 —— 只是名字撞了、全包**无非限定引用**、代价 0）。
    # 本仓自己的判据（`test_no_live_shadow_exposure`）写着「影子**被非限定引用**才叫活的解析错位；
    # 只是名字撞了不算」—— 既然不算病，就不该让它把整体判成不干净。
    # 家规还有一句：「**一条长期红的断言等于没有断言**」，而这个 ok=False 正是那个永久假警报。
    # ⇒ 判决只由**非 latent** 的 findings 决定；latent 仍留在 findings 里（读数不丢），
    #    并另给 `hard_findings` / `latent_only` 让人能区分"只有 latent"与"真干净"。
    #    判据用**实测的 `shadow_exposure`**（none/latent/live/unknown），不去猜字符串 ——
    #    影子检查器不可用时它是 `unknown`，那类 W 条目**照样算病**（不被豁免）。
    _hard = [f for f in findings
             if not (f.get("dim") == "W" and shadow_exposure == "latent")]
    result = {
        "ok": not _hard,
        "verdict": "clean" if not _hard else "findings",
        "findings": findings,
        "hard_findings": len(_hard),
        "latent_only": bool(findings) and not _hard,
        "dims": dims_run,
        "dims_implemented": _DIMS_IMPL,
        "dims_unimplemented": _DIMS_NOT_IMPL,
        # V 维的原始读数（只读一次、印出来，让人能自己复算那笔加减法）
        "v_view": v_stats,
        "coverage_note": (
            f"本扫描有实现的维度 {len(_DIMS_IMPL)} 个（{'/'.join(_DIMS_IMPL)}）；"
            f"另有 {len(_DIMS_NOT_IMPL)} 个维度（{'/'.join(_DIMS_NOT_IMPL)}）"
            f"**只有名字、没有实现**，已从 dims 中剔除 —— "
            f"不许把「声明过」读成「扫过了」。"),
        "deep_checked": deep_stats["checked"],
        # 分母：H 维到底覆盖了几条、跳了几条、为什么跳。跳过 ≠ 没问题，只是**换人/换场**做。
        "deep_coverage": {
            "checked": deep_stats["checked"],
            "skipped_side_effect_n": deep_stats["skipped_n"],
            "skipped_side_effect": deep_stats["skipped"],
            "unsafe_n": deep_stats["unsafe_n"],
            "unsafe": deep_stats["unsafe"],
            # 🔴 第三个分母（2026-09-25 加）：**因为超预算而根本没起调用的**那些位。
            "budget_s": deep_stats["budget_s"],
            "elapsed_s": deep_stats["elapsed_s"],
            "deadline_hit": deep_stats["deadline_hit"],
            "not_probed_n": len(deep_stats["not_probed"]),
            "not_probed": deep_stats["not_probed"],
            # 🔴 第四个分母：**慢位**（量出来的，不是猜的）—— H 是"轻调用"，它们不是轻调用。
            "skipped_slow_n": len(deep_stats["skipped_slow"]),
            "skipped_slow": deep_stats["skipped_slow"],
            "skipped_slow_cost_s": {k: _SLOW_KIND_COST_S.get(k) for k in deep_stats["skipped_slow"]},
            "note": ("侧效应位（发布/部署/出网/完整认知循环）与未标 safe 的位**不在 H 维轻调用里** —— "
                     "跳过是设计，但必须看得见："
                     f"`checked({deep_stats['checked']}) + skipped_n({deep_stats['skipped_n']}) + "
                     f"unsafe_n({deep_stats['unsafe_n']}) + not_probed_n({len(deep_stats['not_probed'])}) + "
                     f"skipped_slow_n({len(deep_stats['skipped_slow'])}) == len(BENIGN_CAPS)`。"
                     "**`not_probed` = 这次没跑到**（不是通过、也不是失败）；"
                     "**`skipped_slow` = 超过 5s 的慢位，不属『轻调用』**"
                     "（`skipped_slow_cost_s` 是量到的耗时，加总约 611s）。"
                     "`deadline_hit: true` 时绝不许把本读数念成『全扫过了』。"
                     "要真探被跳过的位请用 `py -3.14 tools/codex-scripts/cap_probe_all.py`"
                     "（隔离 store + 逐条超时）。"),
        },
        "scanners_verdict": verdicts,
        # 各扫描器原始判定里被豁免的，逐条写明「豁了谁、按什么理由」——
        # 避免 scanners_verdict 里挂着 P0、findings 里却没有对应条目时无从分辨
        "verdict_exemptions": _verdict_exempt,
        "shadow_verdict": shadow_verdict,
        # none / latent（有影子但全包无非限定引用、代价 0）/ live（真错位）/ unknown（没量到）
        "shadow_exposure": shadow_exposure,
        "elapsed_ms": round((time.time() - t0) * 1000, 1),
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    # O54：门禁**跑完** = 成功 = 生产主账本零足迹（不再每跑一次写一行 cross_scan）；
    # 跑不完（X 维隔离门禁自检失败）已在上面落 health_channel_failed —— 《终端失败必须响》。
    return result


# AGENTS.md 兼容别名：mesh_scan() = scan()（N触手网格交叉验证的统一入口）
mesh_scan = scan
