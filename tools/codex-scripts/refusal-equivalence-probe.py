"""拒绝等价面现读（只读）—— 改"硬拒 → 授权即过"**之前**，先把当前行为钉住。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要有它
主人令「限制全改人工授权」，但 §十三 那 5 处路径类防护**改一行就可能悄悄放宽**。
所以顺序必须是：**先量出现在到底什么被拒、什么放行**（逐条读数，不是一个"我记得"），
再动代码；动完再量一遍，**差异必须逐条说得出来**（没差异 = 改动对未授权路径零影响 = 回滚面成立）。

## 它量什么
只探**纯校验函数**（不改状态）：`_check_rel` / `_check_content` / `_resolve_target_name` /
`_require_enabled` / `_write_root_checked`。
**有副作用的入口（`_op_write`）不直探** —— 如实列进「不可直探」清单，**绝不静默跳过**
（本仓纪律：探不了的也要上账）。

用法：
  python tools/codex-scripts/refusal-equivalence-probe.py snapshot   # 钉基线（只读，不改任何东西）
  python tools/codex-scripts/refusal-equivalence-probe.py check      # 与基线逐条对差
  python tools/codex-scripts/refusal-equivalence-probe.py selftest
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
BASE = ROOT / "state" / "refusal-equivalence.json"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 🔴 2026-10-13 修（**坏尺子**二连 · 现读实测，不是推演）：
#   ① **量错了面**：本件要钉的是「**未授权**路径的行为」，可它原先量在**活 store** 上 ——
#      实测：store 里一张 2026-10-08 发的 `filesystem_write` **时段授权**还活着（TTL 到 2027）
#      ⇒ `file_operation._authorized()` 短路生效 ⇒ 三态校验被跳过 ⇒ 6 条读数与基线不一致，
#      看着像"改坏了"，量的其实是「**已授权**那条路」。（本仓纪律：坏判据比坏对象更危险。）
#      **精准修法**：只隔离"授权"这一个变量 —— 把本进程的**授权账本**指到一个空的临时文件
#      （真 store 一个字不动）⇒ 未授权路径才是被测面，且 `_write_root_checked` 那类
#      「是否被隔离」的判断**不受牵连**（第一版改 `GBT_STORE_DIR` 时它就被牵连了，现读抓出来的）。
#      子进程（经门探走 `five-dim.py`）另给它一份空 store（它只跑"设计上必被拒"的输入）。
#   ② **读数带随机**：经门探里"超长路径"那条的错误文本里带随机 `.tmp` 后缀
#      ⇒ `diff(measure(), measure())` 实测 = **1 条**（自己跟自己都对不上），长期红会被训练成忽略红。
#      修法：比对前把随机后缀归一成 `<rand>`。
#   ③ **尺子没钉住自己量的环境**：`_write_root_checked()` 的读数**随"进程是否隔离 store"变**
#      （隔离时不许写生产 `outputs/`）—— 于是它在 `regression_stamp --store fresh` 下**必然**与基线不一致
#      （实测：原生 rc=1，且拒句里还带随机临时 store 路径）。修法：本件**一律在「未隔离 store」下量**
#      （进来就把 `GBT_STORE_DIR` 清掉再 import）；"隔离态"是**另一把尺子**的事，不混在这一把里。
import os as _os
import re as _re
import tempfile as _tf

_os.environ.pop("GBT_STORE_DIR", None)          # ⇒ 本进程按"未隔离 store"量（见文件头 ③）

_RAND_SUFFIX = _re.compile(r"\.[A-Za-z0-9_-]{6,12}\.tmp")
# 子进程那条（经门探）用的空 store：它只跑"设计上必被拒"的输入，故给个干净的房子
_CHILD_STORE = _tf.mkdtemp(prefix="gbt_refusal_probe_child_store_")


def _norm(text) -> str:
    """把**天生随机**的那一段（临时文件后缀）归一 —— 归一的只有随机，语义一个字不动。"""
    return _RAND_SUFFIX.sub(".<rand>.tmp", str(text or ""))


def _isolate_grants() -> str:
    """把**本进程**读的授权账本换成一个空文件（真账本一个字不动）⇒ 量到的是未授权路径。

    为什么打这里而不打 `GBT_STORE_DIR`：实测（2026-10-13）—— 改 store 会把
    `file_operation._write_root_checked` 也一起改了（"进程已隔离 store 就不许写生产 outputs/"），
    于是尺子自己造出一条假差异。授权是**唯一**要隔离的变量。
    """
    from gbt_allinone import auth_gate as _AG
    empty = Path(_tf.mkdtemp(prefix="gbt_refusal_probe_grants_")) / "auth_grants.jsonl"
    _AG._GRANTS = empty
    return str(empty)

# **不可直探**（会改状态）—— 如实列出，不许静默跳过
NOT_PROBED = {
    "file_operation._op_write": "写入口：直探会真落盘（备份+覆盖），只许走门",
    "api._run_benign(wf_define)": "执行能力：直探会跑真动作",
}

# 🔴 **改走门探**（不许直调模块）：喂的都是**设计上必被拒**的输入（越界/带盘符/超长），
#    门（`run_task`）会先要授权 ⇒ 函数根本跑不到 ⇒ **零副作用**。
#    这样"不可直探"那两条就有了**未授权现状读数**：门先挡、missing 里是哪个作用域。
DOOR_CASES = (
    ("create/越界路径", "越界 path ⇒ 门先挡", "create", '{"op":"write","path":"../x.txt","content":"x"}'),
    ("create/盘符路径", "带盘符 ⇒ 门先挡", "create", '{"op":"write","path":"C:/x.txt","content":"x"}'),
    ("create/超长路径", "超长 ⇒ 门先挡", "create", '{"op":"write","path":"' + "a" * 300 + '","content":"x"}'),
    ("wf_define/写工作流", "wf_define ⇒ 门先挡", "wf_define",
     '{"op":"define","name":"_probe_noop","workflow":{"steps":[]}}'),
)


def _cases() -> list:
    """(编号, 说明, 调用)。全部是**纯校验**，不落盘。"""
    from gbt_allinone import file_operation as F

    state = {"enabled": True, "text_exit_target": "state/text_exit.txt"}
    off = {"enabled": False, "text_exit_target": "state/text_exit.txt"}
    return [
        ("check_rel/空", "缺 path ⇒ 拒", lambda: F._check_rel("")),
        ("check_rel/正常", "相对路径 ⇒ 过", lambda: F._check_rel("a/b.txt")),
        ("check_rel/反斜杠", "反斜杠归一 ⇒ 过", lambda: F._check_rel("a\\b.txt")),
        ("check_rel/绝对", "/etc/passwd ⇒ 拒", lambda: F._check_rel("/etc/passwd")),
        ("check_rel/盘符", "C:/x ⇒ 拒", lambda: F._check_rel("C:/x")),
        ("check_rel/上跳", "../../x ⇒ 拒", lambda: F._check_rel("../../x")),
        ("check_rel/超长", "300 字符 ⇒ 拒", lambda: F._check_rel("a" * 300)),
        ("check_content/None", "None ⇒ 空串", lambda: F._check_content(None)),
        ("check_content/正常", "短文本 ⇒ 过", lambda: F._check_content("hi")),
        ("check_content/非字符串", "int ⇒ 拒", lambda: F._check_content(123)),
        ("check_content/上限内", "等于上限 ⇒ 过", lambda: F._check_content("x" * F.CONTENT_MAX)),
        ("check_content/超限", "上限+1 ⇒ 拒", lambda: F._check_content("x" * (F.CONTENT_MAX + 1))),
        ("require_enabled/开", "enabled=True ⇒ 过", lambda: F._require_enabled(state)),
        ("require_enabled/关", "enabled=False ⇒ 拒", lambda: F._require_enabled(off)),
        ("resolve_target/不指定", "不带 target_source ⇒ 过", lambda: F._resolve_target_name({}, state)),
        ("resolve_target/default带target", "default 却自带 target ⇒ 拒",
         lambda: F._resolve_target_name({"target_source": "default", "target": "z"}, state)),
        ("resolve_target/非法来源", "target_source=bogus ⇒ 拒",
         lambda: F._resolve_target_name({"target_source": "bogus"}, state)),
        ("write_root_checked/现进程", "写根闸门（只读调用）", lambda: F._write_root_checked()),
    ]


def _outcome(fn) -> str:
    """把一次调用的结果压成**固定形状**的读数（成功给值/类型，拒绝给异常类与首句）。"""
    try:
        v = fn()
    except Exception as exc:                            # 拒 = 异常；把类名与首句钉下来
        head = _norm(str(exc).splitlines()[0][:60]) if str(exc) else ""
        return "拒:%s:%s" % (type(exc).__name__, head)
    return "过:%s:%s" % (type(v).__name__, (str(v)[:60] if v is not None else ""))


def measure() -> dict:
    grants_to = _isolate_grants()          # 只隔离"授权"这一个变量（见文件头 ①）
    rows, fails = {}, {}
    for cid, why, fn in _cases():
        try:
            rows[cid] = {"说明": why, "结果": _outcome(fn)}
        except Exception as exc:                        # 造用例都失败 ⇒ 如实记，不吞
            fails[cid] = "%s: %s" % (type(exc).__name__, str(exc)[:60])
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "逐条": rows,
            "**造不出用例的**": fails, "**不可直探（会改状态）**": NOT_PROBED,
            "经门探": measure_door(),
            "授权隔离": "本进程授权账本已指向空文件（%s）⇒ 量到的就是**未授权**路径；"
                    "子进程另给空 store（%s）；本进程**已清 `GBT_STORE_DIR`** ⇒ 一律按"
                    "「未隔离 store」量（`_write_root_checked` 那条不再随环境漂）"
                    % (grants_to, _CHILD_STORE),
            "口径": "只探纯校验函数；有副作用的入口如实列进不可直探、**再经唯一门探它的未授权现状**，"
            "**不静默跳过**"}


def _res(row: dict) -> str:
    """一条读数的「结果」；**没有这一栏就写「未读到」**，不拿空串/0 顶替。"""
    if "结果" in row:
        return row["结果"]
    return "**未读到（这条没有『结果』字段）**"


def diff(old: dict, new: dict) -> list:
    """**纯函数**：逐条对差（新增/消失/结果变了都算差异）。"""
    a = old["逐条"] if "逐条" in old else {}
    b = new["逐条"] if "逐条" in new else {}
    out = []
    for k in sorted(set(a) | set(b)):
        if k not in a:                                  # 新增用例：基线里**未读到**这一条
            out.append({"用例": k, "基线": "**未读到（基线里没有这条）**", "现在": _res(b[k])})
        elif k not in b:                                # 用例消失：现在**未读到**
            out.append({"用例": k, "基线": _res(a[k]), "现在": "**未读到（现在没有这条）**"})
        elif _res(a[k]) != _res(b[k]):
            out.append({"用例": k, "基线": _res(a[k]), "现在": _res(b[k])})
    da = old["经门探"] if "经门探" in old else {}
    db = new["经门探"] if "经门探" in new else {}
    for k in sorted(set(da) | set(db)):
        ra = _res(da[k]) if k in da else "**未读到（基线里没有这条）**"
        rb = _res(db[k]) if k in db else "**未读到（现在没有这条）**"
        if ra != rb:
            out.append({"用例": "经门探/" + k, "基线": ra, "现在": rb})
    return out


def door_ok(rows: dict) -> list:
    """**纯函数**：经门探的合法类别只有两种 —— `门先挡` / `本体拒`。
    出现别的（尤其"成功"）⇒ 点名（成功 = 可能真落盘，必须人看）。"""
    return [k for k, v in rows.items()
            if v.get("类别") not in ("门先挡", "本体拒", "**未读到**")]


def measure_door() -> dict:
    """**经门探**：走 `five-dim.py cap`（唯一门 `run_task`），喂"设计上必被拒"的输入。

    读数分三档（现读出来的，不是我预设的）：
      - **门先挡**：门先要授权（`denied:true` + `missing` 列出作用域）⇒ 函数根本没跑；
      - **本体拒**：该 kind **零作用域**（门不拦），但本体以 `user_error`/`needs_*` 拒入参；
      - 🔴 **没挡住**：出现别的（尤其"成功"）⇒ 点名人看，**绝不吞**。
    """
    import subprocess
    out = {}
    for cid, why, kind, payload in DOOR_CASES:
        cmd = [sys.executable, str(ROOT / "tools" / "codex-scripts" / "five-dim.py"),
               "cap", kind, payload]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", cwd=str(ROOT),
                               env={**_os.environ, "GBT_STORE_DIR": _CHILD_STORE})
            env = json.loads(p.stdout)
        except Exception as exc:
            out[cid] = {"说明": why, "类别": "**未读到**",
                        "结果": "**未读到**（%s: %s）" % (type(exc).__name__, str(exc)[:50])}
            continue
        body = env.get("result") if isinstance(env.get("result"), dict) else {}
        denied = env.get("denied") is True or str(env.get("status")) == "denied"
        miss = body.get("missing") or []
        cls = body.get("error_class") or body.get("status") or env.get("status")
        if denied:
            out[cid] = {"说明": why, "类别": "门先挡",
                        "结果": "门先挡（denied）｜缺作用域 %s" % (miss or "**未读到**")}
        elif str(body.get("status")) in ("error", "needs_dependency", "needs_browser_debug",
                                         "not_wired") or str(env.get("status")) == "error":
            out[cid] = {"说明": why, "类别": "本体拒",
                        "结果": "门没挡（该 kind 零作用域）· 本体拒（%s）⇒ 零副作用"
                        % _norm(body.get("message") or body.get("error") or cls)}
        else:
            out[cid] = {"说明": why, "类别": "没挡住",
                        "结果": "🔴 **没挡住**（status=%s）⇒ 有东西可能真跑起来了"
                        % (env.get("status"),)}
    return out


def snapshot(reason: str = "") -> int:
    """钉基线。🔴 **必须写原因**：每一处读数变化都要有人认领 ——
    没写原因直接拒（rc=2），不许"默默重钉"把红洗成绿（同族：`refusal-census settle`）。"""
    if not (reason or "").strip():
        print(json.dumps({"类别": "未写原因",
                          "拒绝": "**重钉基线必须写原因**（`--reason`）：这次读数为什么变、谁认的"},
                         ensure_ascii=False, indent=1))
        return 2
    m = measure()
    m["重钉原因"] = reason.strip()
    BASE.parent.mkdir(parents=True, exist_ok=True)
    BASE.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"钉基线": {"逐条": len(m["逐条"]), "不可直探": len(NOT_PROBED)},
                      "重钉原因": m["重钉原因"],
                      "落盘": str(BASE.relative_to(ROOT)), "at": m["at"]},
                     ensure_ascii=False, indent=1))
    return 0


def check_report(base: Path | None = None) -> tuple[int, dict]:
    """**只算不打印**（判据建在结构上，不建在打印文本上）。`base` 可注入 ⇒ 拒法分支能被控制真触发。"""
    base = base or BASE
    if not base.is_file():
        return 2, {"类别": "未钉基线", "判决": "🔴 **未钉基线** ⇒ 先跑 `snapshot`（没基线就没有等价面）"}
    try:
        old = json.loads(base.read_text(encoding="utf-8"))
    except Exception as exc:
        return 2, {"类别": "未读到基线内容", "判决": "🔴 **未读到基线内容**（%s）⇒ 拒" % str(exc)[:50]}
    new = measure()
    d = diff(old, new)
    base_at = old["at"] if "at" in old else "**未读到（基线没有 at 字段）**"
    return (0 if not d else 1), {
        "类别": "一致" if not d else "有差异",
        "基线": base_at, "现逐条": len(new["逐条"]), "差异条数": len(d), "差异": d[:12],
        "基线重钉原因": old.get("重钉原因") or "**未读到（基线是旧口径钉的，没写原因）**",
        "**不可直探（会改状态）**": new["**不可直探（会改状态）**"],
        "经门探": new["经门探"],
        "判决": ("✅ 与基线**逐条一致**（未授权路径的行为没变 ⇒ 回滚面成立）" if not d else
               "🔴 **有 %d 条与基线不一致** ⇒ 逐条说清是「故意改的」还是「改坏了」；"
               "故意改的必须 `snapshot` 重钉并写原因" % len(d))}


def check() -> int:
    rc, out = check_report()
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return rc


def selftest() -> int:
    checks, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad = bad + (0 if cond else 1)
        checks.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    m = measure()
    if not m["逐条"]:                       # 🔴 一条用例都取不到 ⇒ 如实报「未读到」，不许当合格
        print(json.dumps({"自检": {"条数": 1, "通过": 0, "不通过": 1},
                          "逐条": ["✗ **未读到任何等价面用例**（探针全失败）⇒ 判不合格"]},
                         ensure_ascii=False, indent=1))
        return 1
    ck("**现读：探得到用例**（且没有造不出的）",
       len(m["逐条"]) >= 15 and not m["**造不出用例的**"],
       "逐条 %d ｜ 造不出 %s" % (len(m["逐条"]), m["**造不出用例的**"] or "无"))
    ck("**现读：拒与过两种读数都取到了**（判据有分辨力）",
       any(v["结果"].startswith("拒:") for v in m["逐条"].values())
       and any(v["结果"].startswith("过:") for v in m["逐条"].values()),
       "拒 %d ｜ 过 %d" % (sum(1 for v in m["逐条"].values() if v["结果"].startswith("拒:")),
                        sum(1 for v in m["逐条"].values() if v["结果"].startswith("过:"))))
    ck("**不可直探的必须被如实列出**（不许静默跳过）",
       len(m["**不可直探（会改状态）**"]) >= 2, "列出 %d 条" % len(m["**不可直探（会改状态）**"]))
    # ⑨ 经门探：两条"不可直探"的，走唯一门也要有未授权现状读数 —— 且**必须门先挡**
    door = m["经门探"]
    ck("**经门探：每条都有读数**", len(door) == len(DOOR_CASES), "%d 条" % len(door))
    ck("**经门探：每条都是「门先挡」或「本体拒」**（出现别的 ⇒ 点名，尤其「成功」）",
       not door_ok(door),
       "｜".join("%s=%s" % (k, v["类别"]) for k, v in list(door.items())[:3]))
    ck("**负控：伪造一条「没挡住」⇒ 必须被点名**",
       door_ok({"x": {"类别": "没挡住"}}) == ["x"], "")
    ck("**经门探的输入都是「设计上必被拒」的**（越界/盘符/超长/只定义不执行）",
       all(("../" in p) or ("C:/" in p) or (len(p) > 300) or ("wf_define" in k)
           for _, _, k, p in DOOR_CASES), "口径写在 DOOR_CASES 里")
    ck("**对差判据：完全一致 ⇒ 无差异**", diff(m, m) == [], "")
    mutated = json.loads(json.dumps(m))
    k = sorted(mutated["逐条"])[0]
    mutated["逐条"][k]["结果"] = "过:str:被人为改过"
    d = diff(m, mutated)
    ck("**负控：人为改一条 ⇒ 必须点名那一条**", len(d) == 1 and d[0]["用例"] == k,
       "点名 %s" % (d[0]["用例"] if d else "无"))
    gone = json.loads(json.dumps(m))
    gone["逐条"].pop(k)
    ck("**负控：用例消失 ⇒ 也算差异**（不许当没发生）",
       len(diff(m, gone)) == 1, "")
    # ⑦⑧ 基线那两条拒法（基线可注入 ⇒ 能真触发；判据建在**结构**上）
    import tempfile as _tf

    with _tf.TemporaryDirectory() as tds:
        bd = Path(tds) / "base.json"
        rc, d = check_report(bd)
        ck("**基线不存在 ⇒ rc=2 且类别=未钉基线**",
           rc == 2 and d.get("类别") == "未钉基线", d.get("类别"))
        bd.write_text("这不是 json", encoding="utf-8")
        rc, d = check_report(bd)
        ck("**基线读不成 JSON ⇒ rc=2 且类别=未读到基线内容**",
           rc == 2 and d.get("类别") == "未读到基线内容", d.get("类别"))
        bd.write_text(json.dumps({"逐条": m["逐条"], "经门探": m["经门探"]},
                                 ensure_ascii=False), encoding="utf-8")
        rc, d = check_report(bd)
        ck("**基线缺 at 字段 ⇒ 如实写「未读到 at」且仍能对差**",
           "未读到" in str(d.get("基线")) and rc == 0, "%s ｜ rc=%d" % (d.get("基线"), rc))
    print(json.dumps({"自检": {"条数": len(checks), "通过": len(checks) - bad, "不通过": bad},
                      "逐条": checks}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["snapshot", "check", "selftest"])
    ap.add_argument("--reason", default="", help="snapshot 专用：这次为什么重钉（**必写**）")
    a = ap.parse_args()
    return {"snapshot": lambda: snapshot(a.reason), "check": check,
            "selftest": selftest}[a.cmd]()


if __name__ == "__main__":
    raise SystemExit(main())
