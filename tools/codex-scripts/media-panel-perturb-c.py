"""常驻件（第 35 轮从 `.scratch/` 提升）：media-panel-perturb-c.py

为什么提升：`.scratch/` 会被清，而这是**判据的证据**。本仓已有先例
（`panel-connectivity.py` / `static-freshness.py` 都是从探针提升来的）。
跑法：`python tools/codex-scripts/media-panel-perturb-c.py`（0 = 判据全过）。
"""
"""扰动 C：媒体面板「骨架自检栏」——可逆 + 反向对照（第 35 轮）

靶子：`media_run.scaffold()` 里 arrangement **没有分支** ⇒ 落到 `else:` ⇒ 面板报
「只能给清单」。临时给它一个骨架 ⇒ 预期 骨架栏 6/5/1 → **6/6/0**。

判据：
  · 骨架栏跟得动（有可填骨架 5→6 且 只能给清单 1→0）
  · 反向对照：判据强度行 / 许可 / 发布 **一个都不许动**
  · 源码逐字节还原（sha256）
纪律（第 34 轮学到的）：**扰动必须先自证生效**（这里以"骨架栏确实动了"为生效证据，
  同时另取一次 `scaffold()` 的直接返回作为独立读数），再去下结论。
"""
import hashlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
MR = ROOT / "gbt_allinone" / "tools" / "media_run.py"
HTML = ROOT / "media-console.html"
OLD = ('    else:\n        why = ("这一步要的是**二进制工程件**（DAW 导出），模板给不出件；"\n')
NEW = ('    elif step == "arrangement":        # ← 第 35 轮**扰动专用**，验完即还原\n'
       '        skel = "# arrangement（扰动用临时骨架，验完即撤销）"\n'
       '    else:\n        why = ("这一步要的是**二进制工程件**（DAW 导出），模板给不出件；"\n')

PATS = {
    "骨架栏":  r'人写步共 <b>(\d+)</b> 个：<span class="ok">有可填骨架 (\d+)</span> · <span class="warn">只能给清单 (\d+)</span>',
    "判据强度": r'人写步共 <b>(\d+)</b> 个：<span class="ok">契约判据 (\d+)</span> · <span class="warn">仅在场 (\d+)</span>',
    "许可":    r'<div class="tile"><b>(\d+)</b><span>许可已登记</span></div>',
    "发布":    r'<div class="tile"><b>(\d+)</b><span>发布包</span></div>',
}


def gen():
    subprocess.run([sys.executable, "tools/codex-scripts/media-console.py"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                   cwd=str(ROOT), timeout=600, check=True)
    h = HTML.read_text(encoding="utf-8")
    return {k: (re.search(p, h).groups() if re.search(p, h) else None) for k, p in PATS.items()}


def scaffold_how():
    """独立读数：直接问 `scaffold()` 要 arrangement 的那一格是什么形状。"""
    import importlib
    from gbt_allinone.tools import media_run as M
    importlib.reload(M)
    r = M.scaffold("music", "arrangement", "probe")
    t = r.get("text") or ""
    return {"ok": r.get("ok"), "给得出骨架": ("本步给不出可填骨架" not in t)}


orig = MR.read_bytes()
sha0 = hashlib.sha256(orig).hexdigest()
text = orig.decode("utf-8")
if OLD not in text:
    raise SystemExit("靶子那段没找到（源码变了）—— 停止，不猜着改")

print("=" * 82)
print("扰动 C · 骨架自检栏（源头可逆 + 反向对照）")
print("=" * 82)
base, how0 = gen(), scaffold_how()
print("  ① 基线    骨架栏 %s ｜ 判据强度 %s ｜ 许可 %s ｜ 发布 %s" % (base["骨架栏"], base["判据强度"], base["许可"], base["发布"]))
print("     独立读数：scaffold('music','arrangement') = %s" % json.dumps(how0, ensure_ascii=False))

MR.write_text(text.replace(OLD, NEW), encoding="utf-8")
pert, how1 = gen(), scaffold_how()
print("  ② 扰动中  骨架栏 %s ｜ 判据强度 %s ｜ 许可 %s ｜ 发布 %s" % (pert["骨架栏"], pert["判据强度"], pert["许可"], pert["发布"]))
print("     独立读数：scaffold(...) = %s" % json.dumps(how1, ensure_ascii=False))

MR.write_bytes(orig)                                   # 立刻还原
back, how2 = gen(), scaffold_how()
print("  ③ 还原后  骨架栏 %s ｜ 判据强度 %s ｜ 许可 %s ｜ 发布 %s" % (back["骨架栏"], back["判据强度"], back["许可"], back["发布"]))

sha1 = hashlib.sha256(MR.read_bytes()).hexdigest()
crit = {
    "扰动自证生效（独立读数：给得出骨架 True）": how0.get("给得出骨架") is False and how1.get("给得出骨架") is True,
    "骨架栏跟得动（5→6 且 只能给清单 1→0）":
        base["骨架栏"][1:] == ("5", "1") and pert["骨架栏"][1:] == ("6", "0"),
    "反向对照：判据强度行**不动**": pert["判据强度"] == base["判据强度"],
    "反向对照：许可 / 发布**不动**": pert["许可"] == base["许可"] and pert["发布"] == base["发布"],
    "源码逐字节还原": sha0 == sha1,
    "复原后回基线（独立读数也回 False）": back == base and how2.get("给得出骨架") is False,
}
print()
for k, v in crit.items():
    print("   %s %s" % ("✔" if v else "✗", k))
ok = all(crit.values())
print("\n判读：%s" % ("✅ 骨架自检栏**已证活的** —— 媒体面板 6 项读数全部有扰动证据" if ok else "🔴 见上"))
raise SystemExit(0 if ok else 1)
