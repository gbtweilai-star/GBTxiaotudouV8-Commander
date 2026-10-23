"""常驻件（第 35 轮从 `.scratch/` 提升）：media-panel-perturb-b.py

为什么提升：`.scratch/` 会被清，而这是**判据的证据**。本仓已有先例
（`panel-connectivity.py` / `static-freshness.py` 都是从探针提升来的）。
跑法：`python tools/codex-scripts/media-panel-perturb-b.py`（0 = 判据全过）。
"""
"""补做扰动 B（反向对照）：许可账 +1 —— 这次**先验扰动生效**再量面板

上一次性失败的真因（我自己的错，记下来）：
  ① 路径用了 `.scratch/`（虽然仍在仓内，但口径是"仓内 `projects/` 之下的真文件"）；
  ② **没给必填 `source` / `license`** ⇒ 被「必填为空 ⇒ 拒绝登记」挡下；
  ③ **最要命的：我没验返回值**，扰动根本没生效就去量面板，然后判"判据没通过"。
  ⇒ 纪律：**扰动必须先自证生效**（返回 ok + 独立读数 +1），再去量被扰对象。
"""
import json  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
HTML = ROOT / "media-console.html"
TMPDIR = ROOT / "projects" / "_shared" / "probe-tmp"
TMP = TMPDIR / "20260923-music-probe-master.wav"
PATS = {
    "判据强度": r'人写步共 <b>(\d+)</b> 个：<span class="ok">契约判据 (\d+)</span> · <span class="warn">仅在场 (\d+)</span>',
    "骨架栏":  r'人写步共 <b>(\d+)</b> 个：<span class="ok">有可填骨架 (\d+)</span> · <span class="warn">只能给清单 (\d+)</span>',
    "许可":    r'<div class="tile"><b>(\d+)</b><span>许可已登记</span></div>',
    "发布":    r'<div class="tile"><b>(\d+)</b><span>发布包</span></div>',
}


def gen():
    subprocess.run([sys.executable, "tools/codex-scripts/media-console.py"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                   cwd=str(ROOT), timeout=600, check=True)
    h = HTML.read_text(encoding="utf-8")
    return {k: (re.search(p, h).groups() if re.search(p, h) else None) for k, p in PATS.items()}


def led():
    m = ROOT / "projects" / "_shared" / "licenses" / "manifest.json"
    return len(json.loads(m.read_text(encoding="utf-8")).get("entries") or [])


from gbt_allinone.tools import media_license as ML            # noqa: E402
from importlib.util import module_from_spec, spec_from_file_location   # noqa: E402
_s = spec_from_file_location("cr", ROOT / "tools" / "codex-scripts" / "clean_residue.py")
cr = module_from_spec(_s)
_s.loader.exec_module(cr)

print("=" * 80)
print("扰动 B（反向对照）· 许可账 +1 ⇒ 只许「许可」动")
print("=" * 80)
base, led0 = gen(), led()
print("  ① 基线      面板许可 %s ｜ 账上 %d 条" % (base["许可"][0], led0))

TMPDIR.mkdir(parents=True, exist_ok=True)
TMP.write_bytes(b"probe-license-perturbation")
reg = ML.run("register", file=TMP.relative_to(ROOT).as_posix(),
             source="第 34 轮扰动对照（临时件）", license="probe-only",
             note="用完即撤，只进回收站")
print("  ② 登记返回：%s" % json.dumps(reg, ensure_ascii=False)[:150])
led1 = led()
print("     **先验扰动生效**：账上 %d → %d 条 ｜ ok=%s" % (led0, led1, reg.get("ok")))
if not reg.get("ok") or led1 != led0 + 1:
    print("\n🔴 扰动没生效 ⇒ 停止，不去量面板（不许拿没生效的扰动当判据）")
    raise SystemExit(2)

pert = gen()
print("  ③ 扰动中    面板许可 %s ｜ 判据强度 %s ｜ 骨架栏 %s ｜ 发布 %s"
      % (pert["许可"][0], pert["判据强度"], pert["骨架栏"], pert["发布"]))

ML.run("unregister", file=TMP.relative_to(ROOT).as_posix(), why="第 34 轮扰动对照撤销")
cr._recycle_batch([TMP])
try:
    TMPDIR.rmdir()                                     # 空目录才删得掉；非空就留着，如实报
except OSError as e:
    print("  ⚠ 临时目录没删掉（如实报）：%s" % e)
after, led2 = gen(), led()
print("  ④ 复原后    面板许可 %s ｜ 账上 %d 条" % (after["许可"][0], led2))

crit = {
    "扰动自证生效（账上 +1）": led1 == led0 + 1,
    "许可 tile 跟着动（11→12）": pert["许可"][0] == str(int(base["许可"][0]) + 1),
    "反向对照：判据强度行**不动**": pert["判据强度"] == base["判据强度"],
    "反向对照：骨架栏**不动**": pert["骨架栏"] == base["骨架栏"],
    "反向对照：发布包**不动**": pert["发布"] == base["发布"],
    "复原：面板回基线": after == base,
    "复原：账回基线": led2 == led0,
}
print()
for k, v in crit.items():
    print("   %s %s" % ("✔" if v else "✗", k))
ok = all(crit.values())
print("\n判读：%s" % ("✅ 扰动 B 成立：许可读数**已证活的**，且反向对照全不动" if ok else "🔴 见上"))
raise SystemExit(0 if ok else 1)
