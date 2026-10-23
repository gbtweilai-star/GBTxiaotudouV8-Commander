"""GBT小土豆V8 · 注册表防复发检测（Ghost Guard）。

背景（Owner 口径）：旧体系"每次扫都一大堆问题"的根源是分类口径打架 +
三套镜像副本反复滋生。V8 已收口为唯一注册表，本模块负责保证它不再长回来。

检测项（V8 专属防复发——对齐旧体系三大死因）：
  1. absorbed/ 不允许回来（幽灵镜像目录）
  2. _shadowed/ _build/ 不允许回来
  3. *.deploy_bak 不允许回来
  4. 攻击类命名目录不允许回来（在 caps 类目录中出现即报警）
  5. 注册表自身：DISABLED 与 BENIGN 不得重叠
  6. 口径唯一性——包内代码不得出现私有能力清单（旧病根：三口径打架交集仅 50）
  7. 胶囊滋生率——devoured 杂交链（_x_）出现即报警（旧病根：unclassified 越裁决越滋生）
  8. 活跃区能力副本——capability.json 出现在 store 外（旧病根：三套镜像 510 副本）
  9. 胶囊降威完整性——devoured 内不得有 capability.json / auto_exec: True

用法：python -m gbt_allinone.ghost_guard   （退出码 0=干净，1=发现复发）
"""
import json
import re
import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent
_ROOT = _BASE          # V8 独立家：根就是 gbt_allinone 自己（不再上溯混居目录）

FORBIDDEN_DIRS = [
    _ROOT / "gbt_allinone" / "absorbed",
    _ROOT / "gbt_allinone" / "absorbed" / "_shadowed",
    _ROOT / "gbt_allinone" / "absorbed" / "_build",
]

ATTACK_NAMES = {
    "keylogger", "mimikatz", "xss_tester", "sqli_tester", "phishing_engine",
    "data_hijack", "paywallbuster", "process_injector", "command_injector",
    "dir_buster", "_2captcha", "twocaptcha", "penetration_scan", "abliterator",
}

SCAN_CAP_ROOTS = ["caps"]


class _CaliberCache:
    sig = None
    result = None


_CALIBER_CACHE = _CaliberCache()   # V8 自有 caps（旧 gbt_runtime 已不随迁）


def _cannot_scan(rule: str, why: str, missing) -> dict:
    """R-H295 · ⑥ G1/G2：扫不了时的**结构化拒绝**（不是"无发现"）。

    《触手覆盖矩阵.md》§三：镜组 6 个只有 4 个能报"做不了"。本文件的病最隐蔽：
    原来的 `if not root_dir.exists(): continue` —— **静默跳过**，
    于是扫根不存在时它会报"findings: []"，读起来就是**绿**（没幽灵）。
    "没扫"被当成了"没幽灵"，这是假绿，比抛异常更坏。
    """
    return {
        "ok": False,
        "unavailable": True,
        "denied": False,
        "rule": rule,
        "action": "ghost_guard.scan",
        "missing": list(missing or ()),
        "why": str(why)[:240],
        "error": str(why)[:240],  # 向后兼容：老调用方读 error
        "findings": [],
        # 🔴 2026-09-22 修（错报治理 · 第 31 轮）：`scanned` 原来是**布尔**，
        # 而字段名看着像计数 ⇒ 读数里"扫了多少"读不出来（**没有分母的绿/红**）。
        # 现在它就是**扫过的文件数**：`if res["scanned"]:` 的真假语义不变（n>0 为真、0 为假，
        # 而 0 = 一个都没扫到，本就该判为未验成）。
        "scanned": 0,
        "scanned_files": 0,
        "note": "扫不了 ⇒ **没验成**，不许报『无发现』（那会被读成绿）。",
    }


def scan() -> dict:
    findings = []

    # R-H295：扫根不存在时**不许静默 continue** —— 那会把"没扫"说成"没幽灵"。
    if not _ROOT.exists():
        return _cannot_scan("ghost_scan_root_missing",
                            "扫描根不存在：%s（扫不了，不是没幽灵）" % _ROOT, ["scan_root"])

    for d in FORBIDDEN_DIRS:
        if d.exists():
            findings.append({"kind": "ghost_dir", "path": str(d),
                             "why": "已清理的幽灵/构建目录重新出现"})

    # 定点扫描（性能纪律）：.deploy_bak 历史上只出现在代码目录旁边，
    # 顶层 + 活跃代码目录两层足够覆盖；跳过 .pylibs/store/archived_logs 等大数据树
    baks = []
    scan_roots = [_ROOT]   # 独立家：只扫自己
    _skip = {"archived_logs", ".pylibs", "store", "__pycache__", "gbt_runtime",
             "node_modules", ".venv", "tentacle"}
    for root_dir in scan_roots:
        if not root_dir.exists():
            continue
        try:
            for p in root_dir.glob("*.deploy_bak"):
                baks.append(str(p))
            for child in root_dir.iterdir():
                if child.is_dir() and child.name not in _skip:
                    for p in child.glob("*.deploy_bak"):
                        baks.append(str(p))
                    for sub in child.iterdir():
                        if sub.is_dir() and sub.name not in _skip:
                            for p in sub.glob("*.deploy_bak"):
                                baks.append(str(p))
        except OSError:
            continue
    baks = baks[:20]
    for b in baks[:20]:
        findings.append({"kind": "bak_file", "path": str(b),
                         "why": ".deploy_bak 备份散件复发"})

    for root_name in SCAN_CAP_ROOTS:
        root = _ROOT / root_name
        if not root.exists():
            continue
        for child in root.iterdir():
            if child.is_dir() and child.name.lower() in ATTACK_NAMES:
                findings.append({"kind": "attack_dir", "path": str(child),
                                 "why": f"攻击类命名目录复发: {child.name}"})

    try:
        # 🔴 事故对策（2026-09-25）：容错取表；缺表时**本检查照旧会报**（空集合 ⇒ 漏检会被点名）
        from .caps_tables import BENIGN_CAPS, DISABLED_CAPS, UNIMPLEMENTED_CAPS
        # 2026-09-23 解禁后 DISABLED_CAPS 已清空 —— 但"重叠检测"不能跟着变成空转：
        # 现在真正会撞车的是 UNIMPLEMENTED_CAPS（只有名字、没有实现）混进 BENIGN_CAPS
        # （那会让一个空名字被当成可用能力播出去）。两个集合一起查，缺一个就是漏检。
        for label, names in (("禁用名单", DISABLED_CAPS), ("登记未实现名单", UNIMPLEMENTED_CAPS)):
            for name in set(BENIGN_CAPS) & set(names):
                findings.append({"kind": "registry_overlap", "item": name,
                                 "why": f"能力同时出现在良性与{label}"})
    except Exception as e:
        findings.append({"kind": "registry_error", "why": f"注册表读取失败: {e}"})

    # ── 6. 口径唯一性：私有能力清单检测（旧病根：三口径打架）──
    # 包内代码里出现"能力字典"形态（>=5 个 "domain": 键值对的大字典）且不引用 caps_registry = 私有口径
    # 指纹缓存：源码清单（路径+mtime）不变则复用结论（性能纪律——检测本身 <5ms）
    # 性能纪律：iterdir 逐层展开（~15ms）替代 rglob（Windows 下 100-600ms）；
    # 跳过 store/archived_logs/.pylibs 大数据树——口径只存在于代码区
    _SKIP_TREES = {"store", "archived_logs", ".pylibs", "__pycache__"}
    _files = []
    _stack = [_BASE]
    # 读不了的目录一律**记名**：静默 continue 等于把"没扫"说成"没有"（第 34 轮）。
    # 与第 8 项共用同一张名单，最后随返回值交出去（有分母，红绿才算数）。
    _unreadable = []
    while _stack:
        _d = _stack.pop()
        try:
            for _e in _d.iterdir():
                if _e.is_dir():
                    if _e.name not in _SKIP_TREES:
                        _stack.append(_e)
                elif _e.suffix == ".py":
                    _files.append(_e)
        except OSError as _exc:
            _unreadable.append("%s (%s)" % (_d, type(_exc).__name__))
            continue
    _sig = str(sorted((str(p.relative_to(_BASE)), round(p.stat().st_mtime, 2)) for p in _files))
    # 🔴 2026-09-22 删（第 34 轮）：这里原来有一行死代码
    #     `if getattr(_CALIBER_CACHE, "sig", None) == _sig_str if False else False: pass`
    # `_sig_str` **从未定义**；`A if False else False` 恒为 False，真分支不被求值，
    # 所以它今天不炸 —— 但它是颗雷：谁把 False 改成 True 就是 NameError。
    # 不留"今天恰好不炸"的代码（这正是错报的温床：静默、无输出、无人知道它在）。
    _private = _CALIBER_CACHE.result if _CALIBER_CACHE.sig == _sig else None
    if _CALIBER_CACHE.sig != _sig:
        for p in _files:
            if not p.is_file() or p.name in ("ghost_guard.py", "caps_registry.py"):
                continue
            try:
                src = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            # 真 import 了 caps_registry 才算"引用注册表"。
            # 🔴 2026-09-22 修：原来是 `if "caps_registry" in src`（**文本关键词**）——
            # 注释里提一句就会被跳过 ⇒ 可能**漏掉真的私有注册表**（假阴性）。
            # 现走 AST 真 import 判据；但**文本先当廉价前置筛**（真 import 必然含该文本），
            # 没提到的文件就不解析 —— 否则全仓扫描每个文件都要 ast.parse（实测会把
            # test_framework 里那条全仓扫描用例顶过 30s 单测超时）。
            if "caps_registry" in src:
                from .tools.source_judge import imports_module as _imports
                if _imports(src, "caps_registry") is True:
                    continue
            n_domain = len(re.findall(r'"\w+":\s*\{\s*"domain":', src))
            if n_domain >= 5:
                _private = {"kind": "private_registry", "path": str(p.relative_to(_BASE)),
                            "why": f"私有能力清单（{n_domain} 项 domain 字典）——口径必须唯一（caps_registry）"}
                break
        _CALIBER_CACHE.sig = _sig
        _CALIBER_CACHE.result = _private
    if _private:
        findings.append(_private)

    # ── 7. 胶囊滋生率：devoured 杂交链级联（旧病根：越裁决越滋生）──
    # 口径（v2 语义修正）：单级合法知识杂交（bandit × gitleaks）是吞天设计能力，不报；
    # 只有**级联滋生**（_x_ 再杂交出 _x_，或 recombined_from 里已含 _x_）才是旧病根形态。
    devoured = _BASE / "store" / "devoured"
    if devoured.exists():
        for child in devoured.iterdir():
            if not (child.is_dir() and "_x_" in child.name):
                continue
            cascading = child.name.count("_x_") >= 2
            if not cascading:
                kj = child / "knowledge.json"
                if kj.exists():
                    try:
                        parents = json.loads(kj.read_text(encoding="utf-8")).get("recombined_from", [])
                        cascading = any("_x_" in str(x) for x in parents)
                    except Exception:
                        cascading = True   # 读不出溯源 = 来路不明，从严
                else:
                    cascading = True       # 无 knowledge.json 的 _x_ 目录 = 野生滋生，从严
            if cascading:
                findings.append({"kind": "hybrid_chain", "path": f"store/devoured/{child.name}",
                                 "why": "杂交链级联滋生（_x_ 再生 _x_）——重组防膨胀已被绕过"})

    # ── 8. 活跃区能力副本：capability.json 在 store 外（旧病根：镜像 510 副本）──
    # 🔴 2026-09-22 修（错报治理 · 第 34 轮）：原来是 `_BASE.rglob(...)` —— 先走完整棵树、
    # 再逐条过滤。实测一次 330.5ms、访问 2014 个目录 / 19037 个文件，其中 1979 个目录
    # （store 1269 + .pylibs 710）走完就被丢掉，是纯浪费；`test_perf_baseline` 的 500ms
    # 上限因此被顶红（实测 673ms）。这不是"阈值太严"，是**代码真的白扫了 19037 个文件**。
    # 现改成**下探前剪枝**（复用同一套 _SKIP_TREES）：实测 2.5ms（132×）。
    # 为什么可以剪：文件级排除判据（.pylibs / archived_logs / __pycache__ 子串、
    # store 前缀）对"路径追加"是**单调的** —— 目录被排除 ⇒ 它的所有后代必被排除，
    # 所以"剪掉该目录不下探"与"走完再 continue"判定集合相同。
    # 实测全树只有 2 个 capability.json，都在 store 下、本来就被排除 ⇒ 改动前后
    # findings 完全一致（都是 0 条）。基线已留证：scanned=342 / clean=True / sha256 140a615a…
    _cap_json = []
    _cstack = [_BASE]
    while _cstack:
        _d = _cstack.pop()
        try:
            for _e in _d.iterdir():
                if _e.is_dir():
                    if _e.name not in _SKIP_TREES:
                        _cstack.append(_e)
                elif _e.name == "capability.json" and _e.is_file():
                    _cap_json.append(_e)
        except OSError as _exc:
            # 读不了的目录**记名**（复用上面那张名单，不覆盖它）
            _unreadable.append("%s (%s)" % (_d, type(_exc).__name__))
            continue
    for p in _cap_json:
        findings.append({"kind": "cap_copy", "path": str(p.relative_to(_BASE)),
                         "why": "capability.json 出现在活跃代码区（镜像副本种子）"})

    # ── 9. 胶囊降威完整性：store 内不得有 capability.json / auto_exec: True ──
    if devoured.exists():
        for p in devoured.rglob("capability.json"):
            findings.append({"kind": "cap_in_devoured", "path": str(p.relative_to(_BASE)),
                             "why": "胶囊未降威（应全部为 knowledge.json 数据形态）"})
        for p in devoured.rglob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if data.get("auto_exec") is True:
                    findings.append({"kind": "capsule_armed", "path": str(p.relative_to(_BASE)),
                                     "why": "胶囊带 auto_exec: True（可执行声明——滋生种子）"})
            except Exception:
                continue

    # R-H295：成功路径也要**显式 ok:True** —— 拒绝路径给的是 ok:False，
    # 成功却不带 ok 键的话，调用方没法用同一个字段区分（只有 "clean" 一个键时，
    # 拒绝返回里 clean 缺失，读的人还得先判断键在不在）。同一字段，两个取值，才叫形状。
    return {"ok": True, "clean": not findings, "findings": findings,
            # `scanned` = **真分母**（扫过的文件数），不再是布尔开关（第 31 轮）
            "scanned": len(_files), "scanned_files": len(_files),
            # 没扫到的目录**交出去**：`findings: []` 只有在"该扫的都扫到了"时才等于"干净"。
            "unreadable": _unreadable, "unreadable_count": len(_unreadable),
            "checked_at": __import__("time").strftime("%Y-%m-%dT%H:%M:%S")}


def main(argv=None):
    r = scan()
    import json
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r["clean"] else 1


if __name__ == "__main__":
    sys.exit(main())
