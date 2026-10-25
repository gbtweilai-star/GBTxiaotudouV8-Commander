# -*- coding: utf-8 -*-
"""丢失腿复原（主人令 2026-10-04：「穿透式交叉扫描把没接上和缺失没实现的全部抓出来追踪根因修复优化补齐固化」）。

## 根因（已取证）
活树注册表 217 位 vs 基线工作树（`.scratch/_baseline_wt`）239 位 ⇒ **本分支少 24 位**，
git 历史里从未出现过它们（= 丢在分支合并/清理里）。其中 **18 位基线里有完整模块**（可直接复原），
另 6 位基线里也只有页面/触手库壳子（= 真未实现，登记为 unimplemented 或留待主人定）。

## 本件做什么（三处接线，逐位）
  ① 模块：`<base>/gbt_allinone/tools/<name>.py` → 活树同路径（已存在则跳过，不覆盖）
  ② 注册表：从基线 `caps_registry.py` 取该位的条目块 → 插进活树 `BENIGN_CAPS` 闭括号前
  ③ 分派：从基线 `api.py` 取 `if kind == "<name>":` 块 → 插进活树分派链兜底注释前
  ④ 作用域：从基线 `security/policy.py` 取同名 `if/elif kind == "<name>":` 块（若基线就没有 = 零作用域，不动）

## 纪律
  · **默认 dry-run**（只演不改）；`--apply` 才落盘；
  · 落盘前**逐文件备份**（.bak-restore-<时间戳>），落盘后 `py_compile` 全检 + 逐位 import 冒烟；
  · **不覆盖活树已有文件**（活树有的东西比基线新，绝不回退）；
  · 结果落 `state/restore_missing_caps.json`（谁复原了/谁没模块/失败原因），可复核。

用法：
    py -3.14 tools/codex-scripts/restore_missing_caps.py            # dry-run（看计划）
    py -3.14 tools/codex-scripts/restore_missing_caps.py --apply    # 落盘

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import argparse
import json
import py_compile
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / ".scratch" / "_baseline_wt"
LIVE_REG = ROOT / "gbt_allinone" / "caps_registry.py"
LIVE_API = ROOT / "gbt_allinone" / "api.py"
LIVE_POL = ROOT / "gbt_allinone" / "security" / "policy.py"
RECEIPT = ROOT / "state" / "restore_missing_caps.json"
STAMP = time.strftime("%Y%m%d-%H%M%S")


def registry_names(src: str) -> set:
    return set(re.findall(r'^\s{4}"([a-z0-9_]+)":\s*\{', src, re.M))


def block_of(src: str, name: str, indent: str = "    ") -> str:
    """取注册表条目块（含末尾逗号）。"""
    m = re.search(r'\n%s"%s": \{.*?\n%s\},' % (indent, re.escape(name), indent), src, re.S)
    return m.group(0) if m else ""


def api_block_of(src: str, name: str) -> str:
    m = re.search(r'\n    if kind == "%s":.*?(?=\n    if kind == "|\n    # 🔴 2026-09-25|\Z)'
                  % re.escape(name), src, re.S)
    return m.group(0) if m else ""


def policy_block_of(src: str, name: str) -> str:
    m = re.search(r'\n    (?:if|elif) kind == "%s":.*?(?=\n    (?:if|elif) kind == "|\n    # ──|\Z)'
                  % re.escape(name), src, re.S)
    return m.group(0) if m else ""


def insert_before_dict_close(src: str, anchor_call: str, snippet: str) -> str:
    """把 snippet 插到 `BENIGN_CAPS = {` 那个字典的闭括号前。"""
    i = src.index(anchor_call)
    j = src.index("{", i)
    depth = 0
    for k in range(j, len(src)):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                return src[:k] + snippet.lstrip("\n") + src[k:]
    raise RuntimeError("找不到字典闭括号")


def insert_before_marker(src: str, marker: str, snippet: str) -> str:
    i = src.index(marker)
    return src[:i] + snippet.lstrip("\n") + src[i:]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--base", default=str(BASE))
    args = ap.parse_args(argv)

    base = Path(args.base)
    if not base.exists():
        print("基线工作树不在：%s" % base)
        return 2

    live_src = LIVE_REG.read_text(encoding="utf-8")
    base_reg = (base / "gbt_allinone" / "caps_registry.py").read_text(encoding="utf-8", errors="replace")
    base_api = (base / "gbt_allinone" / "api.py").read_text(encoding="utf-8", errors="replace")
    base_pol_path = base / "gbt_allinone" / "security" / "policy.py"
    base_pol = base_pol_path.read_text(encoding="utf-8", errors="replace") if base_pol_path.exists() else ""

    live = registry_names(live_src)
    missing = sorted(registry_names(base_reg) - live)

    plan, with_mod, register_only, without_mod = [], [], [], []
    reg_snips, api_snips, pol_snips = [], [], []
    def find_mod(root: Path, name: str):
        """模块可能不在 tools/ 下（实测：tripo.py / notion_bridge.py 在包根，freellmapi 在 llm/）
        ⇒ 全包递归找，别把「有实现没登记」误判成「没实现」。"""
        hits = [x for x in (root / "gbt_allinone").rglob("%s.py" % name)
                if ".pylibs" not in str(x) and "__pycache__" not in str(x)]
        return hits[0] if hits else None

    for name in missing:
        mod_base = find_mod(base, name)
        mod_live = find_mod(ROOT, name)
        entry = block_of(base_reg, name)
        api_b = api_block_of(base_api, name)
        pol_b = policy_block_of(base_pol, name) if base_pol else ""
        row = {"name": name, "module_base": bool(mod_base), "module_live": bool(mod_live),
               "registry_block": bool(entry), "api_block": bool(api_b), "policy_block": bool(pol_b)}
        plan.append(row)
        if mod_base and not mod_live:
            with_mod.append(row)          # 要复制模块 + 登记
            reg_snips.append(entry)
            if api_b:
                api_snips.append(api_b)
            if pol_b:
                pol_snips.append(pol_b)
        elif mod_base and mod_live:
            # **只登记**（活树已有模块：实测 freellmapi / notion_bridge / tripo 就是这类 ——
            # 有实现、没进注册表 ⇒ 门与面板都看不见它）
            register_only.append(row)
            reg_snips.append(entry)
            if api_b:
                api_snips.append(api_b)
            if pol_b:
                pol_snips.append(pol_b)
        elif not mod_base:
            without_mod.append(row)

    print("== 复原计划 ==")
    print("活树缺失 %d 位；要复制模块 %d 位；只登记（活树已有模块）%d 位；基线也没模块 %d 位"
          % (len(missing), len(with_mod), len(register_only), len(without_mod)))
    print("\n可复原（复制模块）：")
    for r in with_mod:
        print("  %-18s 注册表块:%s api块:%s policy块:%s"
              % (r["name"], "有" if r["registry_block"] else "**缺**",
                 "有" if r["api_block"] else "**缺**",
                 "有" if r["policy_block"] else "无(零作用域)"))
    print("\n只登记（模块已在活树，只补注册表/api）：",
          ", ".join(r["name"] for r in register_only) or "无")
    print("\n基线也没模块（真未实现，需主人定）：", ", ".join(r["name"] for r in without_mod) or "无")
    missing_api = [r["name"] for r in with_mod if not r["api_block"]]
    if missing_api:
        print("⚠ 这些位基线注册表有、api 分派块取不到（要人看一眼）：", missing_api)

    if not args.apply:
        print("\n（dry-run：什么都没改。要落盘加 --apply）")
        return 0

    # ── 落盘（逐文件备份 → 改 → 编译 → 冒烟）──
    copied, failed = [], []
    for r in with_mod:
        src = find_mod(base, r["name"])
        dst = ROOT / src.relative_to(base)
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied.append(str(dst.relative_to(ROOT)))
        except OSError as exc:
            failed.append({"file": str(dst), "error": str(exc)[:160]})

    for path, snips in ((LIVE_REG, reg_snips), (LIVE_API, api_snips), (LIVE_POL, pol_snips)):
        if not snips:
            continue
        try:
            backup = path.with_suffix(path.suffix + ".bak-restore-" + STAMP)
            if not backup.exists():
                shutil.copy2(path, backup)
            src = path.read_text(encoding="utf-8")
            if path == LIVE_REG:
                src = insert_before_dict_close(src, "BENIGN_CAPS", "\n".join(snips) + "\n")
            else:
                marker = "# 🔴 2026-09-25 **假绿修复**" if path == LIVE_API else None
                if marker is None or marker not in src:
                    failed.append({"file": str(path), "error": "插入锚点找不到"})
                    continue
                src = insert_before_marker(src, marker, "\n".join(snips) + "\n")
            path.write_text(src, encoding="utf-8")
        except Exception as exc:                              # noqa: BLE001
            failed.append({"file": str(path), "error": str(exc)[:200]})

    # 编译检查（四处）
    compile_errors = []
    for path in [LIVE_REG, LIVE_API, LIVE_POL] + [
            ROOT / find_mod(base, r["name"]).relative_to(base) for r in with_mod]:
        try:
            py_compile.compile(str(path), doraise=True)
        except Exception as exc:                              # noqa: BLE001
            compile_errors.append({"file": str(path), "error": str(exc)[:200]})

    # 冒烟：逐位真调一次（只调 status/只读 op，避免副作用）
    smoke = []
    if not compile_errors:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone import run_task
        for r in with_mod:
            name = r["name"]
            try:
                env = run_task(name, {"op": "status"}, safe=True)
                smoke.append({"name": name, "ok": bool(env.get("ok")),
                              "status": (env.get("result") or {}).get("status") if isinstance(env.get("result"), dict) else None,
                              "error": env.get("error")})
            except Exception as exc:                          # noqa: BLE001
                smoke.append({"name": name, "ok": False, "error": str(exc)[:160]})

    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "planned": len(missing),
           "restored_modules": copied, "skipped_no_module": [r["name"] for r in without_mod],
           "failed": failed, "compile_errors": compile_errors, "smoke": smoke,
           "note": "复原=三处接线（模块/注册表/api）；作用域块仅在基线有才插；备份 *.bak-restore-" + STAMP}
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n== 落盘结果 ==")
    print("复制模块 %d 件 · 编译错误 %d · 失败 %d · 冒烟：" %
          (len(copied), len(compile_errors), len(failed)))
    for s in smoke:
        print("  %-18s %s %s" % (s["name"], "ok" if s["ok"] else "失败",
                                 (s.get("status") or s.get("error") or "")[:60]))
    print("回执：%s" % RECEIPT)
    return 1 if (compile_errors or failed) else 0


if __name__ == "__main__":
    sys.exit(main())
