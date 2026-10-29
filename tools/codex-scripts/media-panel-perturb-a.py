"""常驻件（第 35 轮从 `.scratch/` 提升）：media-panel-perturb-a.py

为什么提升：`.scratch/` 会被清，而这是**判据的证据**。本仓已有先例
（`panel-connectivity.py` / `static-freshness.py` 都是从探针提升来的）。
跑法：`python tools/codex-scripts/media-panel-perturb-a.py`（0 = 判据全过）。
"""
"""媒体面板两行的**扰动验证**（可逆 + 反向对照）——第 34 轮

判据（扰动法）：
  改**源头** → 重生成面板 → 看读数**跟不跟着动**。跟得动 = 真连着；纹丝不动 = 写死的。
  且**必须有反向对照**：扰 A 只许动 A 的读数，B 的读数必须不动。

本探针做两扰：
  ① **判据强度行**：`media_run._VALIDATORS` 去掉一条 ⇒ 预期 契约判据 6→5 / 仅在场 0→1
  ② **反向对照**：许可账登记一件 ⇒ 预期 许可 tile 11→12，而判据强度行**不动**

纪律：**源码逐字节还原**（比对 sha256）；产物重生成回基线；许可账扰动用登记/撤销成对，不留脏。
⚠️ 骨架自检栏那一扰**这轮没做**（骨架生成是长 if 链，扰动面大）；如实记，不假装做过。
"""
import hashlib  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
MR = ROOT / "gbt_allinone" / "tools" / "media_run.py"
HTML = ROOT / "media-console.html"
LYRICS_LINE = '    "lyrics": _validate_lyrics,        # 歌词 → 仓内音乐契约（`music-production` §1–§3）\n'

PATS = {
    "判据强度": r'人写步共 <b>(\d+)</b> 个：<span class="ok">契约判据 (\d+)</span> · <span class="warn">仅在场 (\d+)</span>',
    "骨架栏":  r'人写步共 <b>(\d+)</b> 个：<span class="ok">有可填骨架 (\d+)</span> · <span class="warn">只能给清单 (\d+)</span>',
    "许可":    r'<div class="tile"><b>(\d+)</b><span>许可已登记</span></div>',
    "发布":    r'<div class="tile"><b>(\d+)</b><span>发布包</span></div>',
}


def gen():
    p = subprocess.run([sys.executable, "tools/codex-scripts/media-console.py"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=str(ROOT), timeout=600)
    if p.returncode != 0:
        raise SystemExit("生成器失败：%s\n%s" % (p.stdout[-400:], p.stderr[-400:]))
    h = HTML.read_text(encoding="utf-8")
    out = {}
    for k, pat in PATS.items():
        m = re.search(pat, h)
        out[k] = tuple(m.groups()) if m else None
    return out


def show(tag, r):
    print("  %-16s 判据强度 %s ｜ 骨架栏 %s ｜ 许可 %s ｜ 发布 %s"
          % (tag, r["判据强度"], r["骨架栏"], r["许可"], r["发布"]))


orig = MR.read_bytes()
sha0 = hashlib.sha256(orig).hexdigest()
text = orig.decode("utf-8")
if LYRICS_LINE not in text:
    raise SystemExit("靶子那行没找到（源码变了）—— 停止，不猜着改")

print("=" * 86)
print("媒体面板两行 · 扰动验证（源头可逆 + 反向对照）")
print("=" * 86)
base = gen()
show("① 基线", base)

# ── 扰动 A：去掉 lyrics 的判据 ──
MR.write_text(text.replace(LYRICS_LINE, ""), encoding="utf-8")
a = gen()
show("② 扰 A（去判据）", a)
MR.write_bytes(orig)                      # 立刻还原
back = gen()
show("③ 还原后", back)

# ── 第 35 轮提升时**删掉**了原来那段"扰动 B（许可账 +1）" ────────────────
#    原因（留着就是**假红**，而假红比没有判据更坏）：那一段是我第一次的**失败版** ——
#      ① 用 `.scratch/` 的临时件（口径是「仓内 `projects/` 之下的真文件」）；
#      ② 没给必填的 `source` / `license` ⇒ 被「必填为空」拒；
#      ③ **没验返回值**就去量面板 ⇒ 扰动根本没生效，却报「许可没跟着动」。
#    正确版已单独立件：`media-panel-perturb-b.py`（先验登记 ok 与账上 +1，再量面板）。
#    **一件工具只判它自己扰的那一格**；跨格的反向对照由各件自己的 crit 负责。

sha1 = hashlib.sha256(MR.read_bytes()).hexdigest()
print()
crit = {
    "源码逐字节还原": sha0 == sha1,
    "扰 A：判据强度跟着动（契约 6→5 且 仅在场 0→1）":
        base["判据强度"][1:] == ("6", "0") and a["判据强度"][1:] == ("5", "1"),
    "扰 A：骨架栏**不动**（反向对照）": a["骨架栏"] == base["骨架栏"],
    "扰 A：许可/发布**不动**（反向对照）": a["许可"] == base["许可"] and a["发布"] == base["发布"],
    "还原后回基线": back == base,
}
for k, v in crit.items():
    print("   %s %s" % ("✔" if v else "✗", k))
print("\n判读：%s" % ("✅ 判据强度行**已证活的**（扰动跟得动 + 反向对照不动）" if all(crit.values())
                   else "🔴 有判据没通过，见上"))
print("配套：许可账见 `media-panel-perturb-b.py` · 骨架自检栏见 `media-panel-perturb-c.py`。")
raise SystemExit(0 if all(crit.values()) else 1)
