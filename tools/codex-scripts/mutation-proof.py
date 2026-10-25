"""突变证明 —— 把「这条控制真的会咬」从**口头声明**变成**可复核的一条命令**。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要有它
本仓已经有过三次「控制是装饰」的事故：
  ① `checkup._self_check` 写死 `len(steps) == 5` ⇒ 体检长到 28 步后判据**恒假**；
  ② 署名覆盖面闸的 `--trees` 默认漏掉 `docs/` ⇒ 整棵树**没人看**；
  ③ 位级写目标抽样两次抽错 ⇒ 判据**恒 None** 而没人响。
它们的共同点不是「判据写错了」，而是**没人验证过判据会咬**。
`criterion_bench` 只对**它自己那 7 类检测器**做了这件事；本工具把它推广成通用件：
**给它一把刀（把源码改坏），它必须见红；改不坏的地方，它必须说「没咬住」。**

## 三条硬纪律
1. **不动原件**：只在靶同目录写 `_mut_*.py`，`finally` 里删；跑完**查残留**。
2. **锚点必须唯一**：出现 0 次或 ≥2 次一律**拒绝**（绝不 replace-all 猜）。
3. **红灯要与判据同宽**：刀上写 `期望红灯含` ⇒ 必须**点名的那条控制**变红，
   「随便红一条」不算咬住（宽判据 = 假绿）。

用法：
  python tools/codex-scripts/mutation-proof.py list
  python tools/codex-scripts/mutation-proof.py run [--spec 名字或路径 ...]
  python tools/codex-scripts/mutation-proof.py selftest
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
S = ROOT / "tools" / "codex-scripts"
SPEC_DIR = S / "mutation-specs"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ---------------------------------------------------------------- 读红灯（两层）
def _red_count(txt: str) -> int | None:
    """从靶的 stdout 里读「不通过」条数；读不到返回 None（**未读到 ≠ 0**）。"""
    m = re.search(r'"不通过":\s*(\d+)', txt)
    return int(m.group(1)) if m else None


def _red_lines(txt: str) -> list[str]:
    return [ln.strip().rstrip(",").strip('"') for ln in txt.splitlines() if "✗" in ln]


def _did_bite(rc: int, txt: str, mode: str = "字段") -> tuple[bool, str]:
    """判「咬没咬」。**默认看靶自报的「不通过」字段**，不是看退出码。

    🔴 为什么默认不看退出码（本工具自检当场抓到的一次）：合成靶里的 `✗` 走 Windows
    默认 GBK 输出时会 `UnicodeEncodeError` **崩掉** —— stdout 空、rc=1。
    只看退出码就会把**崩溃**念成「咬住」：**红 ≠ 咬住**。
    ⇒ 没有「不通过」字段一律**不许当咬住**（fail-closed）；
       真要验「靠退出码表达」的靶，须在刀上显式写 `"红法": "退出码"`。
    """
    if mode == "退出码":
        return (rc != 0), "只看退出码 rc=%d（刀上显式声明的口径）" % rc
    n = _red_count(txt)
    if n is None:
        return False, "**未读到「不通过」字段**（rc=%d）⇒ 不许当咬住（可能只是崩了）" % rc
    return (n > 0), "「不通过」=%d" % n


def _env() -> dict:
    """子进程环境：**强制 UTF-8 stdout**。

    靶脚本自己 `reconfigure` 是常态，但不能指望每一件都这么写；
    而 Windows 默认 GBK 遇到 `✗`/中文会直接崩 ⇒ 读数是「崩溃」而不是「判据红了」。
    """
    e = dict(os.environ)
    e["PYTHONIOENCODING"] = "utf-8"
    return e


def _slug(old: str) -> str:
    keep = re.sub(r"[^0-9A-Za-z]+", "", old)[:12]
    return keep or "s"


def _sha(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def _resolve_target(spec_path: Path, rel: str) -> Path | None:
    """靶路径：**绝对按绝对**；相对按「规格目录 → 规格同级 → 作品目录」三级现找。"""
    p = Path(rel)
    if p.is_absolute():
        return p if p.is_file() else None
    for cand in (SPEC_DIR / p, spec_path.parent / p, spec_path.parent.parent / p):
        if cand.is_file():
            return cand
    return None


# ---------------------------------------------------------------- 跑一把刀
def _one_mutant(target: Path, mut: dict, args: list[str]) -> dict:
    # 🔴 必填字段**缺了就写「未读到」并拒绝**，绝不拿空串顶替当锚点：
    #    空串的读数是「锚点出现 0 次」——那会把「字段不在」误报成「代码里没有」。
    lack = [k for k in ("名", "旧", "新")
            if not isinstance(mut.get(k), str) or mut.get(k) == ""]
    if lack:
        return {"名": mut.get("名") if isinstance(mut.get("名"), str) else "**未读到**",
                "判决": "拒绝",
                "为什么": "**未读到**刀的必填字段 %s（不拿空串冒充锚点）" % lack}
    name, old, new = mut["名"], mut["旧"], mut["新"]
    want = list(mut["期望红灯含"]) if "期望红灯含" in mut else []
    mode = mut["红法"] if "红法" in mut else "字段"
    src = target.read_text(encoding="utf-8")
    n = src.count(old)
    if n != 1:
        return {"名": name, "判决": "拒绝",
                "为什么": "锚点出现 %d 次，必须恰好 1 次（不许 replace-all 猜）" % n}
    tmp = target.with_name("_mut_%s_%d%s" % (_slug(old), os.getpid(), target.suffix))
    if tmp.exists():
        return {"名": name, "判决": "拒绝", "为什么": "临时文件已存在：%s" % tmp.name}
    try:
        tmp.write_text(src.replace(old, new), encoding="utf-8")
        p = subprocess.run([sys.executable, str(tmp), *args], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", cwd=str(ROOT),
                           env=_env())
        txt = (p.stdout or "") + (p.stderr or "")
        bite, how = _did_bite(p.returncode, txt, mode)
        reds = _red_lines(txt)
        miss = [w for w in want if not any(w in r for r in reds)]
        if bite and miss:
            return {"名": name, "判决": "没咬住", "读数": how,
                    "为什么": "红的是别处，点名要红的 %s 没红（宽判据 = 假绿）" % miss,
                    "红灯数": len(reds), "实际红灯": reds[:4]}
        return {"名": name, "判决": "咬住" if bite else "没咬住",
                "读数": how, "红灯数": len(reds),
                "实际红灯": reds[:2] if reds else [txt.strip()[:120]]}
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


# ---------------------------------------------------------------- 跑一份规格
def run_spec(spec_path: Path) -> dict:
    d = json.loads(spec_path.read_text(encoding="utf-8"))
    miss = [k for k in ("名字", "靶", "刀") if k not in d]
    if miss:
        return {"规格": spec_path.name, "通过": False, "为什么": "缺字段 %s" % miss}
    target = _resolve_target(spec_path, d["靶"])
    if target is None:
        return {"规格": spec_path.name, "通过": False, "为什么": "靶找不到：%s" % d["靶"]}
    args = list(d.get("自检参数") or ["--selftest"])
    sha0 = _sha(target)                      # 🔴 「不动原件」不许只写在注释里

    base = subprocess.run([sys.executable, str(target), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", cwd=str(ROOT),
                          env=_env())
    btxt = (base.stdout or "") + (base.stderr or "")
    b_bite, b_how = _did_bite(base.returncode, btxt)
    if b_bite:
        return {"规格": spec_path.name, "名字": d["名字"], "靶": target.name, "通过": False,
                "原件绿": False,
                "为什么": "**原件本就不绿**（%s）⇒ 后面的刀即使见红也说明不了什么" % b_how}

    rows = [_one_mutant(target, m, args) for m in d["刀"]]
    residue = [p.name for p in target.parent.glob("_mut_*")]
    sha1 = _sha(target)
    ok = (bool(rows) and all(r["判决"] == "咬住" for r in rows) and not residue
          and sha0 == sha1)
    return {"规格": spec_path.name, "名字": d["名字"], "靶": target.name, "通过": ok,
            "原件绿": True, "原件读数": b_how, "原件未被改": sha0 == sha1,
            "原件sha": "%s → %s" % (sha0, sha1), "刀": rows,
            "残留": residue, "口径": d.get("口径", "")}


def _specs(sel: list[str]) -> list[Path]:
    all_specs = sorted(SPEC_DIR.glob("*.spec.json")) if SPEC_DIR.is_dir() else []
    if not sel:
        return all_specs
    out = []
    for s in sel:
        p = Path(s)
        if p.is_file():
            out.append(p)
            continue
        out.extend([q for q in all_specs if s in q.name])
    return out


def cmd_run(sel: list[str]) -> int:
    specs = _specs(sel)
    if not specs:
        print(json.dumps({"突变证明": {"通过": False,
                                   "为什么": "**一份规格都没有 = 不合格**（空表不许念成合格）",
                                   "规格目录": str(SPEC_DIR)}}, ensure_ascii=False, indent=1))
        return 2
    rows = [run_spec(p) for p in specs]
    ok = all(r.get("通过") for r in rows)
    print(json.dumps({"突变证明": {"通过": ok, "规格数": len(rows),
                               "口径": "**原件不动**；锚点必须唯一；点名要红的必须红"},
                      "逐份": rows}, ensure_ascii=False, indent=1))
    return 0 if ok else 1


# ---------------------------------------------------------------- 自检
# 合成靶：**两个旋钮 + 两条控制**，好让「红在别处」这类错法也能被验
_SYN = "\n".join([
    "import json, sys",
    "BITE = False",
    "ALSO = False",
    "lines = []",
    "if BITE:",
    "    lines.append('\u2717 控制甲 咬住了')",
    "if ALSO:",
    "    lines.append('\u2717 控制乙 咬住了')",
    'print(json.dumps({"自检": {"不通过": len(lines), "逐条": lines}}, ensure_ascii=False))',
    "sys.exit(1 if lines else 0)",
    "",
])


def _syn_spec(td: Path, muts: list[dict], bite_default: bool = False) -> Path:
    td.mkdir(parents=True, exist_ok=True)
    (td / "syn_target.py").write_text(
        _SYN.replace("BITE = False", "BITE = True" if bite_default else "BITE = False"),
        encoding="utf-8")
    spec = td / "syn.spec.json"
    spec.write_text(json.dumps({"名字": "合成靶", "靶": "syn_target.py",
                                "自检参数": ["--selftest"], "刀": muts}, ensure_ascii=False),
                    encoding="utf-8")
    return spec


def selftest() -> int:
    """本探针的自检：它必须**既能说「咬住」也能说「没咬住」** —— 否则它是装饰。"""
    checks, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad = bad + (0 if cond else 1)
        checks.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    real = _specs([])
    ck("真规格表**非空**（空表不许念成合格）", bool(real), "%d 份" % len(real))

    GOOD = {"名": "真刀", "旧": "BITE = False", "新": "BITE = True", "期望红灯含": ["控制甲"]}
    DUMMY = {"名": "假刀", "旧": "lines = []", "新": "lines = list()"}
    AMBIG = {"名": "锚点不唯一", "旧": "lines", "新": "LINES"}
    GONE = {"名": "锚点找不到", "旧": "这段锚点在源码里不存在", "新": "x"}
    WRONG = {"名": "红错地方", "旧": "ALSO = False", "新": "ALSO = True",
             "期望红灯含": ["控制甲"]}
    CRASH = {"名": "改崩", "旧": "lines = []", "新": "lines = (", "期望红灯含": ["控制甲"]}

    ck("子进程环境**强制 UTF-8**（否则 CJK 输出会崩成「假红」）",
       _env().get("PYTHONIOENCODING") == "utf-8", "PYTHONIOENCODING=utf-8")

    with tempfile.TemporaryDirectory() as tds:
        td = Path(tds)
        _syn_spec(td, [GOOD])
        tgt = td / "syn_target.py"
        sha_before = _sha(tgt)
        # ① 真刀 ⇒ 必须判「咬住」（且点名的那条控制真的红了）
        row = _one_mutant(tgt, GOOD, ["--selftest"])
        ck("**真刀 ⇒ 判「咬住」**", row["判决"] == "咬住",
           "%s ｜ %s" % (row["判决"], row.get("实际红灯")))
        # ② 假刀（等价改写、行为不变）⇒ 必须判「没咬住」
        row = _one_mutant(tgt, DUMMY, ["--selftest"])
        ck("**假刀（行为不变）⇒ 必须判「没咬住」**（否则见刀就咬）",
           row["判决"] == "没咬住", "%s ｜ %s" % (row["判决"], row.get("读数")))
        # ③ 锚点出现多次 ⇒ 必须**拒绝**，不许猜
        row = _one_mutant(tgt, AMBIG, ["--selftest"])
        ck("**锚点不唯一 ⇒ 拒绝**（绝不 replace-all）", row["判决"] == "拒绝",
           str(row.get("为什么"))[:70])
        # ④ 锚点找不到 ⇒ 必须拒绝
        row = _one_mutant(tgt, GONE, ["--selftest"])
        ck("**锚点找不到 ⇒ 拒绝**", row["判决"] == "拒绝", str(row.get("为什么"))[:70])
        # ④b 刀的必填字段缺了 ⇒ 拒绝并写「未读到」（不拿空串顶替当锚点）
        row = _one_mutant(tgt, {"名": "缺字段", "旧": "BITE = False"}, ["--selftest"])
        ck("**刀缺必填字段 ⇒ 拒绝且写「未读到」**（空串不许顶替）",
           row["判决"] == "拒绝" and "未读到" in str(row.get("为什么")),
           str(row.get("为什么"))[:70])
        # ⑤ 确实红了、但**红在别的控制**上 ⇒ 仍须判「没咬住」（同宽控制）
        #    🔴 这条控制差点是假绿：判据必须**证明「确实红了」**（读数真读到「不通过」，
        #    且红灯行里点名的那条**不是**要求的那条），否则崩溃路径也能把它喂饱。
        row = _one_mutant(tgt, WRONG, ["--selftest"])
        ck("**红在别处 ⇒ 也要判「没咬住」**（宽判据 = 假绿）",
           row["判决"] == "没咬住" and row.get("红灯数") == 1
           and any("控制乙" in r for r in (row.get("实际红灯") or []))
           and "别处" in str(row.get("为什么"))
           and str(row.get("读数", "")).startswith("「不通过」"),
           "%s ｜ %s ｜ %s" % (row["判决"], str(row.get("读数"))[:24],
                             str(row.get("为什么"))[:44]))
        # ⑥ **改崩（语法错）= 红 ≠ 咬住**：没有「不通过」字段一律不许当咬住
        row = _one_mutant(tgt, CRASH, ["--selftest"])
        ck("**改崩 ⇒ 不许当咬住**（fail-closed：红 ≠ 咬住）",
           row["判决"] == "没咬住" and "未读到" in str(row.get("读数")),
           "%s ｜ %s" % (row["判决"], str(row.get("读数"))[:70]))
        # ⑦ 原件本就不绿 ⇒ 整份不通过，且理由**点原件**
        row = run_spec(_syn_spec(td / "b", [GOOD], bite_default=True))
        ck("**原件不绿 ⇒ 整份不通过且理由点名**",
           row.get("通过") is False and row.get("原件绿") is False,
           str(row.get("为什么"))[:70])
        # ⑧ 残留检查：跑完不许留下 `_mut_*`
        left = [p.name for p in td.rglob("_mut_*")]
        ck("**跑完零残留**（`_mut_*` 一律删）", not left, "残留 %s" % (left or "无"))
        # ⑨ **原件逐字节没动**（sha 前后自比，不许只写在注释里）
        ck("**原件逐字节没动**（前后 sha 自比）", _sha(tgt) == sha_before,
           "sha %s" % sha_before)

    print(json.dumps({"自检": {"条数": len(checks), "通过": len(checks) - bad, "不通过": bad},
                      "逐条": checks}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def cmd_list() -> int:
    rows = []
    for p in (sorted(SPEC_DIR.glob("*.spec.json")) if SPEC_DIR.is_dir() else []):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            # 🔴 读不到就写「未读到」：`len(d.get("刀") or [])` 会把「字段不在」
            #    静默印成 `刀数: 0` —— 那正是本工具要打的那种假读数。
            if "刀" not in d:
                rows.append({"规格": p.name, "名字": d.get("名字", "**未读到**"),
                             "靶": d.get("靶", "**未读到**"),
                             "刀数": "**未读到 `刀`**（不拿 0 冒充）"})
                continue
            rows.append({"规格": p.name, "名字": d.get("名字", "**未读到**"),
                         "靶": d.get("靶", "**未读到**"), "刀数": len(d["刀"])})
        except Exception as e:
            rows.append({"规格": p.name, "读不了": str(e)})
    print(json.dumps({"规格目录": str(SPEC_DIR), "份数": len(rows), "逐份": rows},
                     ensure_ascii=False, indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "run", "selftest"])
    ap.add_argument("--spec", action="append", default=[])
    a = ap.parse_args()
    if a.cmd == "list":
        return cmd_list()
    if a.cmd == "run":
        return cmd_run(a.spec)
    return selftest()


if __name__ == "__main__":
    raise SystemExit(main())
