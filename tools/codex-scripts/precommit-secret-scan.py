"""提交前凭据自审 —— 只看**暂存区**（将要进仓库的那一份），数明文密钥出现几次。

⚠️ 这份工具**必须留在仓里**。它此前的版本只存在于 `%TEMP%` ⇒ 重启即消失，
   「强制自审」于是完全靠记忆执行 —— 记忆一断就等于没有（第 52 轮登记为 F17）。
   放到仓里之后，开机自检能点名它、git 能看见它的改动、别人能读到它。

三条判据
  ① 逐字比对：保险箱里每个 profile 的密钥，在暂存 diff 里出现次数必须是 **0**。
     密钥**当场从 DPAPI 保险箱解出来、只在内存里过一遍**：
       · 不读任何明文参照文件（旧版要读 `%TEMP%/mcporter.json.before-dpapi.bak`，
         那等于「防明文落盘的工具自己依赖一份明文落盘」）；
       · 不写任何明文落盘；
       · 不打印密钥本身，只打印掩码。
  ② 形状扫描：新增行里像密钥的长串。**不依赖参照物** ——
     ① 只能逮住"我手上有的那些密钥"，逮不住"我没登记过的凭据"。
  ③ 反空洞：一个 profile 都没解出来时，①其实一条都没比过 ⇒ **不许报绿**。
     「没跑成」和「跑通了没命中」不是同一个结论。

退出码契约
  0 = 干净（① 真比过 且 命中 0）· 1 = 命中明文 · 2 = 自审本身没跑成（含反空洞触发）。
  `--allow-empty-vault` 只在"明知保险箱是空的"时用，且会把 ② 标成唯一判据。

用法
  python tools/codex-scripts/precommit-secret-scan.py            # 查暂存区
  python tools/codex-scripts/precommit-secret-scan.py --json
  python tools/codex-scripts/precommit-secret-scan.py --selftest # 离线自证有牙（不碰真密钥）
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# 2026-10-10 修（**同族编码缺陷，第三次撞上**）：本件在 **GBK 控制台**上不带 -X utf8 调用时**当场崩**。
#    实测真因（不是猜）：gbt_allinone/tests/test_precommit_secret_scan.py 第 118 行调本件用的是
#        subprocess.run([PY, str(TOOL), "--selftest", "--json"], ...)     # PY = sys.executable
#    —— **没带 -X utf8**；本件打印含 U+21D2（⇒）时抛
#        UnicodeEncodeError: 'gbk' codec can't encode character U+21D2
#    ⇒ stdout/stderr 空 ⇒ 它的自检判据 test_selftest_is_green 判 rc != 0 ⇒ 恒红。
#    同族先例（同日）：audit-dead-judgments.py · cloud-config-wiring.py —— 三件一个病。
#    全仓扫描：tools/codex-scripts 下会印非 ASCII 的 .py 里，**已有 307 件带守门、143 件还没带**
#    （本件是其中之一，现补上）。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")   # type: ignore[attr-defined]
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]

# 形状扫描用的候选长串：够长、单行、不含空格。
# 为什么不用「必须是 sk-/ak- 开头」：ADP（来也）的 key 是纯十六进制长串，不带前缀 ⇒
# 只按前缀扫等于给它开后门。
_CANDIDATE = re.compile(r"[A-Za-z0-9_\-]{20,}")
# 明显不是密钥的长串（提交哈希、包版本、base64 图片片段、uuid 等）——只做**减噪**，不做放行。
_NOISE = (
    re.compile(r"^[0-9a-fA-F]{40}$"),          # git sha1
    re.compile(r"^[0-9a-fA-F]{64}$"),          # sha256
    re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F-]{27}$"),  # uuid
    re.compile(r"^\d+(?:[._-]\d+){1,}$"),      # 版本号
)


def _mask(value: str) -> str:
    text = str(value or "")
    return (text[:4] + "****") if len(text) >= 4 else "****"


def vault_keys() -> tuple[dict[str, str], list[str]]:
    """从 DPAPI 保险箱取**每个 profile** 的密钥（只在内存里）。返回 (keys, 读不出的名单)。

    找不到 profile 表 / 一个都解不出来都算"读不出"，由调用方决定这算不算反空洞。
    绝不让异常把密钥带进消息里 —— 这里只回 profile 名。
    """
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        from gbt_allinone import deepseek_key as dk  # noqa: PLC0415
    except Exception:  # noqa: BLE001
        return {}, ["<导入 deepseek_key 失败>"]
    keys: dict[str, str] = {}
    failed: list[str] = []
    for name in sorted(getattr(dk, "_PROFILES", {}) or {}):
        try:
            key, _source = dk.load_from_vault(name)
        except Exception:  # noqa: BLE001
            failed.append(name)
            continue
        if key:
            keys[name] = key
        else:
            failed.append(name)
    return keys, failed


def exact_hits(diff: str, keys: dict[str, str]) -> list[dict]:
    """① 逐字比对。只回 profile 名 + 掩码 + 次数，**不回密钥**。"""
    hits = []
    for name, key in sorted(keys.items()):
        n = diff.count(key) if key else 0
        if n:
            hits.append({"profile": name, "masked": _mask(key), "count": n})
    return hits


def shape_hits(diff: str) -> list[dict]:
    """② 形状扫描：只看**新增行**（删除行里的旧密钥不构成"这次要进库的明文"）。"""
    seen: dict[str, int] = {}
    for line in str(diff or "").splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for token in _CANDIDATE.findall(line[1:]):
            if any(p.match(token) for p in _NOISE):
                continue
            seen[_mask(token)] = seen.get(_mask(token), 0) + 1
    return [{"masked": m, "count": c} for m, c in sorted(seen.items())]


def scan(diff: str, keys: dict[str, str], *, failed: list[str] | None = None,
         allow_empty_vault: bool = False) -> dict:
    exact = exact_hits(diff, keys)
    shapes = shape_hits(diff)
    exact_ran = bool(keys)
    problems: list[str] = []
    if not exact_ran and not allow_empty_vault:
        problems.append(
            "保险箱里一个密钥都没解出来 ⇒ ①逐字比对**根本没比**，不许报绿"
            "（读不出：%s）" % ("、".join(failed or []) or "未知"))
    if exact:
        problems.append("① 逐字比对命中明文：%s"
                        % "、".join("%s(%s)×%d" % (h["profile"], h["masked"], h["count"])
                                   for h in exact))
    ok = not problems
    return {
        "ok": ok,
        "exit": 0 if ok else (1 if exact else 2),
        "diff_chars": len(str(diff or "")),
        "profiles_compared": len(keys),
        "profiles_unreadable": list(failed or []),
        "exact_ran": exact_ran,
        "exact_hits": exact,
        "shape_hits": shapes,
        "problems": problems,
    }


def _git_diff(staged: bool = True) -> str:
    cmd = ["git", "diff", "--cached"] if staged else ["git", "diff"]
    out = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise RuntimeError("git diff 失败（rc=%d）：%s" % (out.returncode, out.stderr.strip()[:200]))
    return out.stdout


def selftest() -> dict:
    """离线自证有牙：种进去必须逮住，且**不许恒真**。不碰任何真密钥。"""
    controls: list[dict] = []

    def ck(name: str, cond: bool, detail: str = "") -> None:
        controls.append({"control": name, "ok": bool(cond), "detail": detail})

    fake = "sk-" + "Zq7" * 12          # 合成凭据；形状像 sk- 前缀长串
    fake2 = "b3f4" + "0a" * 14          # 合成十六进制长串（ADP 那一路的形状）
    # `fake` 故意种**两处**：①要证明它不只是"见到就回 true"，还**数得对**
    # （数错次数意味着"命中了几处"这个结论不可信）。
    diff = ("--- a/x\n+++ b/x\n@@\n"
            "-old line\n"
            "+API_KEY = \"%s\"\n"
            "+rotated = '%s'\n"
            "+plain = '%s'\n" % (fake, fake, fake2))

    # ① 有牙：登记的合成密钥必须被逐字逮住，且**次数要对**
    h = exact_hits(diff, {"synthetic": fake})
    ck("①逐字比对能逮住且数得对",
       len(h) == 1 and h[0]["count"] == 2, json.dumps(h, ensure_ascii=False))
    # ① 不误报：没登记的串不在逐字结果里
    ck("①不误报未登记串", exact_hits(diff, {"other": "NOPE" + "x" * 20}) == [])
    # ① 不泄露：结果里绝不能出现密钥本身
    ck("①结果不含密钥原文",
       fake not in json.dumps(h, ensure_ascii=False),
       "掩码=%s" % (h[0]["masked"] if h else ""))
    # ② 有牙：不依赖参照物也能看出形状
    s = shape_hits(diff)
    ck("②形状扫描能逮住", len(s) >= 2, json.dumps(s, ensure_ascii=False))
    # ② 只看新增行：删除行里的密钥不算"这次要进库的"
    ck("②不看删除行", shape_hits("--- a/x\n+++ b/x\n-x = \"%s\"\n" % fake) == [])
    # ② 减噪：git sha 不该被当成密钥刷屏
    ck("②git sha 减噪",
       shape_hits('+sha = "da39a3ee5e6b4b0d3255bfef95601890afd80709"\n') == [])
    # ③ 反空洞：保险箱空 ⇒ 必须非 0 退出码，不许报绿
    r = scan("+nothing\n", {}, failed=["deepseek"])
    ck("③空保险箱不许报绿", r["ok"] is False and r["exit"] == 2,
       "exit=%s problems=%s" % (r["exit"], r["problems"]))
    # ③ 反空洞的例外必须显式声明
    r2 = scan("+nothing\n", {}, failed=["deepseek"], allow_empty_vault=True)
    ck("③显式放过时才放行", r2["ok"] is True and r2["exact_ran"] is False)
    # ③ 真命中 ⇒ 退出码 1（与"没跑成"的 2 分开）
    r3 = scan(diff, {"synthetic": fake})
    ck("③命中与没跑成不同码", r3["exit"] == 1, "exit=%s" % r3["exit"])
    # 干净 diff + 真比过 ⇒ 0
    r4 = scan("+hello world\n", {"synthetic": fake})
    ck("③干净即 0", r4["exit"] == 0 and r4["ok"] and r4["exact_ran"])

    passed = sum(1 for c in controls if c["ok"])
    return {"ok": passed == len(controls), "passed": passed, "total": len(controls),
            "controls": controls}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="提交前凭据自审（只看暂存区）")
    ap.add_argument("--json", action="store_true", help="机器可读（人读提示走 stderr）")
    ap.add_argument("--selftest", action="store_true", help="离线自证有牙，不碰真密钥")
    ap.add_argument("--allow-empty-vault", action="store_true",
                    help="保险箱为空时也放行 ②；必须显式给，且会在输出里标注")
    args = ap.parse_args(argv)

    if args.selftest:
        rep = selftest()
        if args.json:
            print(json.dumps(rep, ensure_ascii=False, indent=2))
        else:
            for c in rep["controls"]:
                print("  %s %s%s" % ("✓" if c["ok"] else "🔴", c["control"],
                                     ("  " + c["detail"]) if (c["detail"] and not c["ok"]) else ""))
            print("自证 %d/%d" % (rep["passed"], rep["total"]))
        return 0 if rep["ok"] else 1

    try:
        diff = _git_diff()
    except Exception as exc:  # noqa: BLE001
        print("🔴 自审没跑成：%s" % exc)
        return 2

    keys, failed = vault_keys()
    rep = scan(diff, keys, failed=failed, allow_empty_vault=args.allow_empty_vault)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        for p in rep["problems"]:
            print(p, file=sys.stderr)
    else:
        print("暂存 diff = %d 字符" % rep["diff_chars"])
        print("① 逐字比对：比了 %d 个 profile（读不出 %d 个）⇒ 命中明文 **%d** 处%s"
              % (rep["profiles_compared"], len(rep["profiles_unreadable"]),
                 sum(h["count"] for h in rep["exact_hits"]),
                 "" if rep["exact_ran"] else "  🔴 其实一条都没比"))
        for h in rep["exact_hits"]:
            print("     🔴 %s（%s）×%d" % (h["profile"], h["masked"], h["count"]))
        print("② 形状扫描：新增行里像密钥的长串 **%d** 个 %s"
              % (len(rep["shape_hits"]), [s["masked"] for s in rep["shape_hits"]]))
        for p in rep["problems"]:
            print("   🔴 " + p)
        print("结论：%s（退出码 %d）" % ("干净" if rep["ok"] else "不许提交", rep["exit"]))
    return rep["exit"]


if __name__ == "__main__":
    raise SystemExit(main())
