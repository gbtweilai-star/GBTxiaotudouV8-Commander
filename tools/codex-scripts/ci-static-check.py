# -*- coding: utf-8 -*-
# 开发者：自由的风 · 永久钢印 · 禁止删除
"""ci-static-check.py —— CI / Dockerfile 的静态校验（无第三方依赖）。

## 为什么需要它

本仓 `dependencies = []`（零第三方依赖），所以本机**没有 pyyaml**，
没法真解析 workflow。但 GitHub Actions 最常见的致命错就那么几类，
静态能抓，而且抓得住的都是「炸得最安静」的那几类：

  ① `tab` 缩进            —— 整份 workflow 编译失败
  ② `jobs:` 缺失           —— 一个 job 都不创建
  ③ job 缺 `runs-on`       —— 该 job 直接不创建
  ④ `${{ runner.temp }}` 在 **job 级** `env` —— 2026-11-04 实测炸过：
     整个 workflow 在编译期失效，`run` 的 name 退化成文件路径、
     一个 job 都不创建，而 check-runs 里**连报错都看不到**。
     这一类错只能靠静态抓，因为平台不会告诉你。
  ⑤ step 既没 `run` 也没 `uses` —— 要么写漏，要么缩进错，都会被静默忽略
  ⑥ Dockerfile 的 `CMD` 不是合法 JSON 数组 —— 镜像起不来

## 它不是 lint，是防「安静地失效」

真实红（测试挂了）有日志、有栈、有人会看见。
这里拦的是**没有日志的那一类** —— 推上去看着绿、或者压根没跑，
最贵的就是这种。

## 用法

    python tools/codex-scripts/ci-static-check.py
    python tools/codex-scripts/ci-static-check.py --json
    python tools/codex-scripts/ci-static-check.py --selftest   # 负控：证明它会红

`--selftest` 造五个坏样本，逐个断言被报出来。判据不会红的校验器
等于没有校验器 —— 所以这条要能过。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github" / "workflows" / "ci.yml"
DOCKERFILE = ROOT / "Dockerfile"


# ── 基础工具 ────────────────────────────────────────────────────────────────
def indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _is_comment_or_blank(s: str) -> bool:
    return (not s.strip()) or s.strip().startswith("#")


# ── ci.yml ─────────────────────────────────────────────────────────────────
def check_ci_text(text: str) -> list[str]:
    """对 workflow 文本做静态校验。抽成纯函数，才能被 selftest 喂坏样本。"""
    bad: list[str] = []
    lines = text.splitlines()

    # ① tab
    for i, ln in enumerate(lines, 1):
        if "\t" in ln and not ln.strip().startswith("#"):
            bad.append("L%d 含 tab（YAML 非法缩进，整份 workflow 会编译失败）" % i)

    # ② 顶格 jobs:
    if not any(ln.rstrip() == "jobs:" for ln in lines):
        bad.append("找不到顶格的 `jobs:` —— 一个 job 都不会创建")

    # ③④ job 必须有 runs-on + steps
    # 🔴 只在顶格 `jobs:` **之后**才开始识别 job。
    # 血账（本脚本 --selftest 抓到的自己的假阳性）：第一版按「缩进 2 且形如 `xxx:`」
    # 认 job，结果 `on:` 下的触发事件（`push:` / `pull_request:` / `workflow_dispatch:`）
    # 全被当成 job 报「缺 runs-on」—— 真实文件直接被判红。
    # 判据假阳性比漏报更坏：它会教人忽略这条判据。
    jobs: list[dict] = []
    cur: dict | None = None
    in_jobs = False
    for i, ln in enumerate(lines, 1):
        if _is_comment_or_blank(ln):
            continue
        ind = indent_of(ln)
        s = ln.strip()
        if ind == 0 and s == "jobs:":
            in_jobs = True
            continue
        if not in_jobs:
            continue
        if ind == 0:
            break                        # 顶层下一个键 ⇒ jobs 块结束
        if ind == 2 and re.match(r"^[A-Za-z0-9_-]+:\s*$", s):
            cur = {"name": s[:-1], "line": i, "runs_on": False, "steps": False}
            jobs.append(cur)
        elif cur is not None and ind > 2:
            if s.startswith("runs-on:"):
                cur["runs_on"] = True
            elif s.startswith("steps:"):
                cur["steps"] = True

    for j in jobs:
        if not j["runs_on"]:
            bad.append("job `%s`（L%d）缺 `runs-on` —— GitHub 会直接不创建这个 job"
                       % (j["name"], j["line"]))
        if not j["steps"]:
            bad.append("job `%s`（L%d）缺 `steps`" % (j["name"], j["line"]))

    # ⑤ runner.temp 出现在 job 级 env
    def env_blocks():
        i = 0
        while i < len(lines):
            ln = lines[i]
            if _is_comment_or_blank(ln):
                i += 1
                continue
            if ln.strip() == "env:":
                base = indent_of(ln)
                j, block = i + 1, []
                while j < len(lines):
                    l2 = lines[j]
                    if _is_comment_or_blank(l2):
                        j += 1
                        continue
                    if indent_of(l2) <= base:
                        break
                    block.append((j + 1, l2))
                    j += 1
                yield base, block
                i = j
            else:
                i += 1

    for base, block in env_blocks():
        if base > 6:
            continue                     # 只关心 job 级（缩进 4~6）
        for bl, btext in block:
            if "runner.temp" in btext:
                bad.append("L%d（job 级 env）出现 `${{ runner.temp }}` —— "
                           "该上下文在 job 级不可用：整份 workflow 会静默失效，"
                           "check-runs 里连报错都看不到" % bl)

    # ⑥ step 必须有 run 或 uses
    for i, ln in enumerate(lines):
        if not re.match(r"^\s+- name:", ln):
            continue
        # 取到下一个同级 `- ` 之前
        seg_lines = [ln]
        lead = indent_of(ln)
        for nxt in lines[i + 1:]:
            if nxt.strip():
                if indent_of(nxt) <= lead and nxt.strip().startswith("- "):
                    break
                if indent_of(nxt) < lead:
                    break
            seg_lines.append(nxt)
        seg = "\n".join(seg_lines)
        if ("run:" not in seg) and ("uses:" not in seg):
            bad.append("L%d 的 step 既没 `run:` 也没 `uses:` —— 会被静默忽略：%s"
                       % (i + 1, ln.strip()[:60]))
    return bad


# ── 文件存在性：absent ≠ bad ────────────────────────────────────────────────
# 🔴 2026-11-04 口径修正（血账）：生产树（Desktop\GBT小土豆V8）是**运行时树**，
# 不含 Dockerfile 与 .github/ —— 那是构建/CI 文件。原先把它当「目标不存在」判红，
# 于是这份自证在生产树必然失败。这跟 guard-three 把「产物没建」当 fail 是同一个错：
# 按 AGENTS.md §2.1 三态，缺依赖是 needs_dependency，不是 failed。
# 「本树不含这个文件」→ absent（如实报，不算失败）；「文件在但坏了」→ bad（真红）。
def check_one(path: Path, fn) -> dict:
    if not path.is_file():
        return {"file": path.name, "status": "absent", "problems": []}
    bad = fn(path.read_text(encoding="utf-8"))
    return {"file": path.name,
            "status": "bad" if bad else "ok",
            "problems": bad}


# ── Dockerfile ─────────────────────────────────────────────────────────────
def check_dockerfile_text(text: str) -> list[str]:
    m = re.search(r"^CMD\s+(\[.*\])\s*$", text, re.M)
    if not m:
        return ["Dockerfile 里没有 exec 形式的 CMD（应当写成 [\"sh\", \"-c\", \"...\"]）"]
    try:
        arr = json.loads(m.group(1))
    except Exception as e:                                        # noqa: BLE001
        return ["CMD 不是合法 JSON：%s" % e]
    bad: list[str] = []
    if not isinstance(arr, list) or not all(isinstance(x, str) for x in arr):
        return ["CMD 必须是字符串数组"]
    if arr and arr[0] in ("sh", "bash") and "-c" in arr:
        script = arr[-1]
        for q, label in (("'", "单引号"), ('"', "双引号")):
            if script.count(q) % 2:
                bad.append("CMD 的 shell 脚本%s不成对 —— 容器起来会语法错：%s"
                           % (label, script[:80]))
    return bad


# ── 负控：证明它会红 ────────────────────────────────────────────────────────
_BAD_CI = [
    ("tab 缩进",
     "name: x\non: push\njobs:\n  a:\n\truns-on: ubuntu-latest\n    steps:\n      - run: echo 1\n",
     "tab"),
    ("缺 jobs",
     "name: x\non: push\n",
     "jobs:"),
    ("缺 runs-on",
     "name: x\non: push\njobs:\n  a:\n    steps:\n      - run: echo 1\n",
     "runs-on"),
    ("job 级 env 里用 runner.temp",
     "name: x\non: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n"
     "    env:\n      D: ${{ runner.temp }}/x\n    steps:\n      - run: echo 1\n",
     "runner.temp"),
    ("step 只有 name",
     "name: x\non: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n      - name: 空壳\n",
     "既没 `run:` 也没 `uses:`"),
]

_BAD_DOCKERFILE = [
    # 不是 exec 形式（shell form）—— 报的是「没有 exec 形式的 CMD」
    ("不是 exec 形式", 'FROM x\nCMD sh -c "echo 1"\n', "exec 形式的 CMD"),
    # JSON 合法但脚本里单引号落单 —— 这条真的会在容器里炸
    ("CMD 引号不成对", 'FROM x\nCMD ["sh", "-c", "echo \'a"]\n', "不成对"),
]


def selftest() -> int:
    fails: list[str] = []
    print("=" * 74)
    print("负控：每个坏样本都必须被报出来（判据不会红 = 没有判据）")
    print("=" * 74)
    for label, text, needle in _BAD_CI:
        got = check_ci_text(text)
        hit = any(needle in g for g in got)
        print("  %s ci.yml · %-24s → %s"
              % ("✅" if hit else "❌", label,
                 (got[0][:70] if got else "(没报出来)")))
        if not hit:
            fails.append("ci.yml/%s 未被报出（期望含 %r，实得 %r）" % (label, needle, got))
    for label, text, needle in _BAD_DOCKERFILE:
        got = check_dockerfile_text(text)
        hit = any(needle in g for g in got)
        print("  %s Dockerfile · %-20s → %s"
              % ("✅" if hit else "❌", label,
                 (got[0][:70] if got else "(没报出来)")))
        if not hit:
            fails.append("Dockerfile/%s 未被报出（期望含 %r，实得 %r）"
                         % (label, needle, got))

    # 正控：真实文件必须通过；**不在本树**不算失败（生产树没有 Dockerfile）
    print("\n" + "-" * 74)
    for path, fn in ((CI, check_ci_text), (DOCKERFILE, check_dockerfile_text)):
        r = check_one(path, fn)
        if r["status"] == "ok":
            shown = "✅ 全过"
        elif r["status"] == "bad":
            shown = "❌ %s" % r["problems"][:2]
            fails.append("真实文件 %s 坏了：%r" % (r["file"], r["problems"]))
        else:
            shown = "◻ 不在本树（跳过，不算失败）"
        print("  正控 %-16s → %s" % (r["file"], shown))

    print("\n" + "=" * 74)
    print("自证通过（%d 个坏样本全被抓）" % (len(_BAD_CI) + len(_BAD_DOCKERFILE))
          if not fails else "自证失败 %d 项" % len(fails))
    for f in fails:
        print("  - %s" % f)
    return 0 if not fails else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="CI / Dockerfile 静态校验（抓「安静失效」那类）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true", help="负控：造坏样本证明它会红")
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()

    rows = [check_one(CI, check_ci_text), check_one(DOCKERFILE, check_dockerfile_text)]
    ok = all(r["status"] != "bad" for r in rows)

    if a.json:
        print(json.dumps({"ok": ok, "results": rows}, ensure_ascii=False, indent=1))
        return 0 if ok else 1

    print("=" * 70)
    print("CI / Dockerfile 静态校验")
    print("=" * 70)
    for r in rows:
        if r["status"] == "bad":
            print("\n❌ %s" % r["file"])
            for b in r["problems"]:
                print("   - %s" % b)
        elif r["status"] == "absent":
            print("\n◻ %s（不在本树，跳过 —— 运行时树不含构建/CI 文件）" % r["file"])
        else:
            print("\n✅ %s" % r["file"])
    print("\n" + "=" * 70)
    total = sum(len(r["problems"]) for r in rows)
    absent = sum(1 for r in rows if r["status"] == "absent")
    tail = "全过" if ok else "有 %d 处问题" % total
    if absent:
        tail += "（%d 个文件不在本树）" % absent
    print(tail)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
