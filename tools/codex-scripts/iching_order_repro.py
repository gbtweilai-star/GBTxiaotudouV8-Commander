"""判别性复现：证明「位序镜像」缺陷是真的，且新自检**真咬得住**。

🔴 只说"修好了"不算证据 —— 一条**从没红过**的回归测试证明不了任何事。
   本脚本把**旧约定**（上→初）与**新约定**（初→上）并排算给你看：
   旧约定下 `震` 的局势查出 `艮`，新自检第 ⑨/⑩ 条必红；新约定下全对。

用法：python tools/codex-scripts/iching_order_repro.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import iching_kernel as K  # noqa: E402


def old_bits(c) -> str:
    """旧版 bits()：**上→初**（exit 打头）。"""
    return "%d%d%d%d%d%d" % (c.exit, c.authority, c.collab, c.risk, c.resource, c.timing)


def main() -> int:
    cases = [
        ("震", dict(timing=1, collab=1), "100100", "震"),
        ("艮", dict(risk=1, exit=1), "001001", "艮"),
        ("巽", dict(resource=1, risk=1, authority=1, exit=1), "011011", "巽"),
        ("兑", dict(timing=1, resource=1, collab=1, authority=1), "110110", "兑"),
    ]
    bad = 0
    print("%-4s %-8s %-8s %-10s %-10s %s" % ("期望", "旧位串", "旧查出", "新位串", "新查出", "判定"))
    for want, kw, want_new, _ in cases:
        c = K.DecisionContext(**kw)
        ob, nb = old_bits(c), c.bits()
        o = K.KING_WEN.get(ob, ("", "**未收录**"))[1]
        n = K.KING_WEN.get(nb, ("", "**未收录**"))[1]
        # 构造判据：旧约定要么查不出、要么查出**别的卦**（这就是镜像铁证）
        old_wrong = (o != want)
        new_right = (n == want and nb == want_new)
        ok = old_wrong and new_right
        bad += 0 if ok else 1
        print("%-4s %-8s %-8s %-10s %-10s %s"
              % (want, ob, o, nb, n, "✓ 旧错新对" if ok else "✗ 判别失败"))
    print()
    print("旧约定：bits[0]=上爻 ⇒ 与卦表键(bits[0]=初爻)**反着** ⇒ 非回文卦被镜像")
    print("回文卦（坎010010 / 离101101 / 乾111111 / 坤000000）两套约定同值 ⇒ **挡不住这个缺陷**，")
    print("这正是上一版 8 条自检全绿却带着真缺陷的原因。")
    print()
    print("现役 consult() 复核：", end=" ")
    live = {w: K.consult(K.DecisionContext(**kw))["卦名"] for w, kw, _, _ in cases}
    print(live)
    live_ok = all(live[w] == w for w, _, _, _ in cases)
    print("现役 consult 全对:", live_ok)
    rc = 0 if (bad == 0 and live_ok) else 9
    print("判别 %d 例 ｜ 不判别 %d 例 ｜ rc=%d" % (len(cases), bad, rc))
    return rc


if __name__ == "__main__":
    sys.exit(main())
