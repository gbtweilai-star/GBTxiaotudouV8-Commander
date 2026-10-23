"""「依赖面 ⊆ 包」这条**必须每次都能重跑**，不许只量过一次就写进结论（2026-09-23 第 57 轮立）。

═══ 这笔债是怎么欠下的 ═══
第 56 轮把收据的判据从整仓 `tree_changed` 换成依赖面 `deps_changed`，依据是**量过一次**的读数：
「依赖面 = 199 个文件，全部落在 `gbt_allinone/` 之内」。
那次量的过程留在 `.scratch/measure_dep_face.py` 里 —— 结论对，但**它是一次考古**：
  ① 跑不跑由我记不记得决定，**不在任何红绿判据里**；
  ② 谁改了 import 结构、谁往包里加了一个指向仓外的模块，`DEPS_SUBDIR = "gbt_allinone"`
     这一刀就会**悄悄漏量**，而收据照样念「面内没变 ⇒ 收据成立」；
  ③ 一个只量过一次的读数，过几天就变成"我以为"。
⇒ 本轮把那条测量变成**判据**：真起一次 pytest 收集 → 数出依赖面 → 断言它整个落在那一刀之内。

═══ 第 57 轮它第一次开火：抓到的**不是假红，是真洞** ═══
判据装上的第一次全量跑，它就红了，点名：
    `.scratch/_stamp_site/sitecustomize.py`
—— 那是**回归印章自己**为了让孩子自报 store/解释器而注入到 `PYTHONPATH` 的文件，
落在包**外**。也就是说：**带章运行时，「依赖面 ⊆ 包」这句话是假的**。
修法不是把例外写死（手写排除名单一定会过期 —— 本会话第 60 条），而是**算出来并记名**：
  · 注入面从 `PYTHONPATH` **算**（不写死路径）；
  · 命中的注入文件**照样列出来**（不静默丢掉）；
  · 并且加一条更硬的判据：**注入面必须落在剪枝目录里**（`.scratch` 是 `SKIP_DIRS`）——
    否则收据既看不见它（不进指纹）、又不覆盖它（不在 `DEPS_SUBDIR`）= 真洞。

═══ 判据四条（少一条就有一类假绿）═══
  ① **实测依赖面非空**（极小兜底）**且含本进程确实 import 过的包内模块**（结构性下限，算出来的）
     —— 空集里当然没有逃逸，没有下限的「一个都没跑出去」是空话；
  ② **面 ⊆ 包**（路径前缀判，不是子串判；注入面记名后可归属）—— 逃逸者必须**点名**；
  ③ **面 ⊆ 收据指纹真正覆盖的文件**（**注入面除外**）—— 收据的指纹只算 `CODE_SUFFIXES`
     且按 `SKIP_DIRS` 剪枝，所以依赖面上若出现一个"指纹根本不算"的文件（`.pyd` / `store/`
     里的东西），改它**不会**让 `deps_changed` 动 ⇒ 收据会假绿。
     ⚠️ 注入面为什么除外：它与收据**同源**（压印自己写的），且按设计落在剪枝区 ——
        收据对剪枝区**本来就不看**（`.scratch` 在 `SKIP_DIRS` 里）。所以第 ③ 条对注入面
        不成立，**但第 ④ 条替它兜底**：注入面一旦落到非剪枝区，就是真洞（红）。
        第 57 轮带章全量跑实测：只是把注入面从"逃逸"里摘出来还不够，它还会被第 ③ 条
        抓住 ⇒ 两条口径必须一起说清，否则**每次带章跑都假红**。
  ④ **注入面必须在剪枝区** —— 见上。

═══ 两种量法（为什么默认走便宜的那条）═══
  · **进程内**（默认判据）：`sys.modules` 里落在本仓的模块文件 —— 这是**本次运行真正 import 了
    哪些文件**，零成本、不需要子进程、不受内存压力影响。口径是"收集期 + 已执行用例的导入"，
    是本仓收据口径的**超集**（更强）。
  · **子进程整包收集**（重口径，交叉验证）：`GBT_DEPFACE_HEAVY=1` 时才跑。它要再起一个
    pytest 收集整个 `gbt_allinone/tests`（~20-40 秒、吃内存）。**默认不跑**并写明怎么跑：
    在内存被压到 0.6GB 的全量跑里，这条重口径会因为起不来而报"量不到"，那就成了
    「由负载决定、不由对错决定的红」—— 本会话第 52/53/54 轮已经栽过三次的那种**错报**。
  ⚠️ 边界（与第 56 轮同一条，不缩小也不夸大）：量的是**收集期/已导入**的依赖面；
     将来才 import 的东西不在里面。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(_TOOLS))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import isolation_sweep as iso  # noqa: E402
import scan_scope as ss  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FACE_TARGET = ROOT / "gbt_allinone" / "tests"
MARKER = "@@DEPS@@"
# 🔴 下限只做**极小兜底**（"量崩了"那种：收集失败/口径改了/目标指错）。
# 曾经写 50，结果**单文件跑时假红**：只跑本文件时进程内面本来就只有 17 个模块 ——
# 那是诚实的分母，不是缺陷。**由口径决定、不由对错决定的红，就是错报**
# （本会话第 52/53/54 轮栽过三次，这里是第四次，被我自己新立的判据抓到）。
# ⇒ 真正的下限是**结构性**的：本进程确实 import 过的包内模块必须在面里（见 must_be_in_face()）。
FACE_FLOOR = 5
HEAVY_ENV = "GBT_DEPFACE_HEAVY"

# 子进程里干的事：真起一次 pytest 收集，然后把 `sys.modules` 里**落在本仓内**的模块文件路径 dump 出来。
# 那是**这一次收集真的加载了哪些文件**，不是"我认为它会加载哪些"。
DUMP_SRC = '''
import json, pathlib, sys
import pytest

root = pathlib.Path(r"@@ROOT@@").resolve()
target = pathlib.Path(r"@@TARGET@@").resolve()
prc = pytest.main(["--collect-only", "-q", "-p", "no:cacheprovider", str(target)])
files = []
for name, mod in list(sys.modules.items()):
    f = getattr(mod, "__file__", None)
    if not f:
        continue
    try:
        p = pathlib.Path(f).resolve()
    except Exception:
        continue
    if str(p).startswith(str(root)):
        try:
            files.append(str(p.relative_to(root)).replace("\\\\", "/"))
        except ValueError:
            pass
print("@@MARKER@@" + json.dumps({"rc": int(prc), "files": sorted(set(files))}))
'''.replace("@@MARKER@@", MARKER)


def _rel_under(p, root=ROOT) -> str:
    """绝对路径 → 仓内相对（正斜杠）；不在仓内返回空串。"""
    try:
        return str(Path(p).resolve().relative_to(Path(root).resolve())).replace("\\", "/")
    except Exception:  # noqa: BLE001
        return ""


def face_in_process(root=ROOT) -> list:
    """**进程内**实测依赖面：本次运行（含收集期与已执行用例的导入）落在本仓的模块文件。

    零成本、无子进程 ⇒ 不会被内存/负载压成"量不到"（那是错报的温床）。
    """
    out = set()
    for mod in list(sys.modules.values()):
        f = getattr(mod, "__file__", None)
        if not f:
            continue
        rel = _rel_under(f, root)
        if rel:
            out.add(rel)
    return sorted(out)


def vendor_files(root=ROOT) -> list:
    """**算出来的**第三方 vendored 库：`sys.modules` 里落在 `vendor/` 的模块文件。

    🔴 2026-10-17 加（留痕 · 实测 · 原口径 / 为什么翻 / 现口径）：
      原口径：面 = 落在本仓的全部模块；逃逸里除注入面/测试台外**一律判红**。
      为什么翻：`test_scan_cap` / `test_vision_print` 会触发 PIL（`vendor/pylibs/cp314/PIL/**`）
        ⇒ 组合/全量跑里凭空冒出 **124 件**"包外逃逸"，判红；单跑本文件却绿。
        它们**不是本仓第一方依赖**，是 vendored 第三方件（自带版本，不随本包发版）。
      现口径：从 `sys.modules` **算**出 `vendor/` 下的模块，**记名**（`vendor_hits`）、不判红；
        `gbt_allinone/` 之外**第一方**逃逸照旧判红（这条判据的核心没变）。
    """
    out = set()
    for mod in list(sys.modules.values()):
        f = getattr(mod, "__file__", None)
        if not f:
            continue
        rel = _rel_under(f, root)
        if rel and rel.startswith("vendor/"):
            out.add(rel)
    return sorted(out)


def harness_files(root=ROOT) -> list:
    """**算出来的**测试台模块：本次运行里被**测试代码 `importlib` 加载**的 `tools/` 脚本。

    🔴 2026-10-17 加（留痕 · 实测 · 原口径 / 为什么翻 / 现口径）：
      原口径：面 = `sys.modules` 里落在本仓的全部模块。
      为什么翻：`tools/` 是**诊断/一次性脚本区**（不是 `gbt_allinone` 的运行时依赖），
        但多个判据文件会用 `importlib` 直接加载它们（如本文件的 `GEN` / `VERIFY` / `AUD`）⇒
        `sys.modules` 里出现 `tools/...` 模块 ⇒ 依赖面里冒出**包外**条目 ⇒
        本判据在**全量/组合跑**里红、单跑却绿（典型跨用例污染）。
      现口径：把 `tools/` 下的已载入模块**算出来**并**记名**（`harness_hits`）——
        不静默丢弃、也不判红：它们是**测试台的工具**，不是包的运行时依赖。
        包外**其它**逃逸（真依赖错位）照旧判红。
    """
    out = set()
    for mod in list(sys.modules.values()):
        f = getattr(mod, "__file__", None)
        if not f:
            continue
        rel = _rel_under(f, root)
        if rel and rel.startswith("tools/"):
            out.add(rel)
    return sorted(out)


def injected_dirs(root=ROOT, env=None) -> list:
    """**算出来的**注入面：本次运行往 `PYTHONPATH` 里塞过什么目录（仓内相对）。

    不写死路径 —— 手写的排除名单一定会过期（第 60 条）。当前唯一的来源是
    `regression_stamp` 给孩子注入的 `sitecustomize.py`（它靠这个让孩子自报 store/解释器）。
    """
    env = os.environ if env is None else env
    out = []
    for raw in str(env.get("PYTHONPATH") or "").split(os.pathsep):
        raw = raw.strip()
        if not raw:
            continue
        rel = _rel_under(raw, root)
        if rel:
            out.append(rel)
    return sorted(set(out))


def injected_files(root=ROOT) -> list:
    """**算出来的**注入文件：pytest 自己载入的 `conftest.py`（不经 `PYTHONPATH`）。

    🔴 2026-10-17 加（留痕 · 实测 · 原口径 / 为什么翻 / 现口径）：
      原口径：注入面**只**从 `PYTHONPATH` 算（回归印章的 `sitecustomize.py`）。
      为什么翻：仓库根 `conftest.py` 是 **pytest rootdir 自己注入的**（钉 rootdir、提供夹具），
        它不经过 `PYTHONPATH` ⇒ 被 `unattributable` 判成"真逃逸"，
        `test_dependency_face` 因此恒红（实测点名：`conftest.py`）。
      现口径：从 `sys.modules` **算**出"已载入的、文件名恰为 `conftest.py`"的仓内文件，
        作为**注入文件名记**（`injected_file_hits`）—— 不静默放过，也不维护文件名白名单：
        只认结构化事实（pytest 的 conftest 约定文件名）。
    """
    out = set()
    for mod in list(sys.modules.values()):
        f = getattr(mod, "__file__", None)
        if not f:
            continue
        try:
            p = Path(f)
        except Exception:                                      # noqa: BLE001
            continue
        if p.name != "conftest.py":
            continue
        rel = _rel_under(p, root)
        if rel:
            out.add(rel)
    return sorted(out)


def unattributable(face, subdir, injected) -> list:
    """面里**不在包里、也不是注入面**的文件（= 真逃逸）。"""
    esc = outside_face(face, subdir)
    return sorted(f for f in esc
                  if not any(f == d or f.startswith(d.rstrip("/") + "/") for d in injected))


def unpruned_injections(injected, skip_dirs) -> list:
    """注入面里**落在非剪枝区**的目录 —— 收据既看不见、又不覆盖，= 真洞。"""
    return sorted(d for d in injected if d.split("/")[0] not in set(skip_dirs))


def measure_face(root=ROOT, timeout=900, target=None) -> dict:
    """重口径：真起一次 pytest 收集，返回落在本仓内的模块文件（相对 `root`、正斜杠）。

    返回 `{"available", "state", "files", "rc", "note"}` —— `available=False` 表示**量不到**，
    与「面是空的」是两件事，调用方不许把两者念成一句。
    `rc` 是**那次收集**的返回码：只有 `rc == 0` 才算量到 —— 收集没跑通时加载到的模块少一批，
    面会被**截短**，而"截短的面 ⊆ 包"照样成立（假绿通道）。
    """
    root = Path(root).resolve()
    target = Path(target).resolve() if target else FACE_TARGET.resolve()
    tmp = Path(tempfile.mkdtemp(prefix="gbt_depface_"))
    try:
        script = tmp / "_dump_deps.py"
        script.write_text(DUMP_SRC.replace("@@ROOT@@", str(root))
                                  .replace("@@TARGET@@", str(target)), encoding="utf-8")
        env = dict(os.environ)
        # 测试纪律：绝不绑生产 store —— 子进程用自己的临时落点。
        env["GBT_STORE_DIR"] = str(tmp / "store")
        env["GBT_WEB_ADAPTIVE_DB"] = str(tmp / "adaptive.db")
        env["GBT_CALL_GRAPH_DB"] = str(tmp / "callgraph.db")
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            p = subprocess.run([sys.executable, str(script)], cwd=str(root), env=env,
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"available": False, "state": "cannot_tell", "files": [], "rc": None,
                    "note": "收集超过 %s 秒还没回来 ⇒ **量不到**（这不是『面跑出去了』）" % timeout}
        out = (p.stdout or "") + (p.stderr or "")
        marker = [ln for ln in out.splitlines() if ln.startswith(MARKER)]
        if not marker:
            return {"available": False, "state": "cannot_tell", "files": [], "rc": p.returncode,
                    "note": "子进程没吐出面（进程 rc=%s）⇒ **量不到**，这不是『面跑出去了』；尾巴：%s"
                            % (p.returncode, out[-300:].replace("\n", " | "))}
        payload = json.loads(marker[0][len(MARKER):])
        prc = payload.get("rc")
        if prc != 0:
            # 🔴 这条是自家判据咬出来的（第 57 轮）：面是**收集期**量出来的，
            #    收集一旦没跑通（用例文件 import 失败等），加载到的模块就**少一批** ⇒
            #    面被截短，而"截短的面 ⊆ 包"照样成立 ⇒ **一个假绿通道**。
            #    ⇒ 收集没跑通 = **量不到**，不是"面是干净的"。
            return {"available": False, "state": "cannot_tell", "files": [], "rc": prc,
                    "note": "**收集本身没跑通**（pytest rc=%s）⇒ 量出来的面是被截短的，"
                            "**量不到**——收集都没成功，拿它去说『面 ⊆ 包』是没有分母的" % prc}
        try:
            where = str(target.relative_to(root))
        except ValueError:
            where = str(target)
        return {"available": True, "state": "measured", "files": payload.get("files") or [], "rc": 0,
                "note": "子进程真起了一次 pytest 收集（pytest rc=0，目标 %s）" % where}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def outside_face(face, subdir) -> list:
    """面里**不在 `subdir` 之内**的文件。

    判据是**路径前缀**，不是子串 —— 子串判会把 `other/gbt_allinone/x.py`
    和 `gbt_allinone_extra/x.py` 一起当成"包内"，那正是这一条要拦的假绿。
    """
    pref = subdir.replace("\\", "/").strip("/") + "/"
    return sorted(f for f in (face or [])
                  if not f.replace("\\", "/").startswith(pref))


def judge(face, subdir, floor=FACE_FLOOR, covered=None, injected=None,
          skip_dirs=None, injected_files=None, harness_files=None, vendor_files=None) -> dict:
    """纯判定（不碰盘）—— 好让变异验证能咬到它。

    `covered` 给定时（收据指纹的 `rows` 路径集），再查第 ③ 条：面里的文件必须**都被指纹覆盖**。
    `injected` 给定时（本次运行往 `PYTHONPATH` 注入的仓内目录），包外命中里属于注入面的
    **记名不判红**；再查第 ④ 条：注入面必须落在剪枝区（`skip_dirs`）。
    `injected_files` 给定时（pytest 自己注入的 `conftest.py`），逐**文件**记名不判红
    （与目录级注入不同：conftest 在 rootdir 根上，天然不在剪枝区，故不套第 ④ 条）。
    """
    face = sorted({f.replace("\\", "/") for f in (face or [])})
    injected = sorted({d.replace("\\", "/").strip("/") for d in (injected or [])})
    inj_files = sorted({f.replace("\\", "/").strip("/") for f in (injected_files or [])})
    esc = outside_face(face, subdir)
    hits = sorted(f for f in esc
                  if any(f == d or f.startswith(d + "/") for d in injected))
    file_hits = sorted(f for f in esc if f in set(inj_files))
    hrn_hits = sorted(f for f in esc if f in set(h.replace("\\", "/") for h in (harness_files or [])))
    vnd_hits = sorted(f for f in esc if f in set(h.replace("\\", "/") for h in (vendor_files or [])))
    real = sorted(f for f in esc if f not in hits and f not in set(file_hits)
                  and f not in set(hrn_hits) and f not in set(vnd_hits))
    uncovered = sorted(f for f in face if covered is not None and f not in covered
                       and f not in set(hits) and f not in set(file_hits)
                       and f not in set(hrn_hits) and f not in set(vnd_hits))
    unpruned = unpruned_injections(injected, skip_dirs) if skip_dirs is not None else []
    out = {"face": len(face), "escapees": real, "injected_hits": hits,
           "injected_file_hits": file_hits, "harness_hits": hrn_hits, "vendor_hits": vnd_hits,
           "uncovered": uncovered, "unpruned_injections": unpruned, "subdir": subdir}
    if len(face) < floor:
        out.update(green=False, reason=(
            "实测依赖面只数到 %d 个文件（下限 %d）⇒ 这一条是**空话**：空集里当然没有逃逸。"
            "不许把『没量到』念成『面 ⊆ 包』。" % (len(face), floor)))
        return out
    if real:
        out.update(green=False, reason=(
            "实测依赖面里有 %d 个文件**落在 `%s/` 之外**、且不是本次运行的注入面 ⇒ "
            "「面 ⊆ 包」不成立，收据会漏量它们：%s" % (len(real), subdir, "、".join(real[:8]))))
        return out
    if unpruned:
        out.update(green=False, reason=(
            "注入面落在**非剪枝区**：%s ⇒ 收据既看不见它（不进指纹）又不覆盖它（不在 `%s/`）"
            "= 真洞" % ("、".join(unpruned[:4]), subdir)))
        return out
    if uncovered:
        out.update(green=False, reason=(
            "依赖面上有 %d 个文件**收据指纹根本不覆盖**（后缀不在 CODE_SUFFIXES，或落在 SKIP_DIRS 里）"
            "⇒ 改它不会让 `deps_changed` 动，收据会假绿：%s"
            % (len(uncovered), "、".join(uncovered[:8]))))
        return out
    tail = ("；包外命中 %d 个**是本次运行注入的**（%s）—— 记名，不算逃逸"
            % (len(hits), "、".join(hits[:3]))) if hits else ""
    out.update(green=True, reason=(
        "%d 个实测依赖文件全部落在 `%s/` 之内，且全部在收据指纹的覆盖面里%s"
        % (len(face), subdir, tail)))
    return out


_CACHE = {}


def _face_once() -> list:
    if "face" not in _CACHE:
        _CACHE["face"] = face_in_process()
    return _CACHE["face"]


def _covered_once() -> set:
    if "covered" not in _CACHE:
        fp = ss.tree_fingerprint(ROOT, subdir=iso.DEPS_SUBDIR, with_rows=True)
        _CACHE["covered"] = {r["path"] for r in fp.get("rows") or []}
    return _CACHE["covered"]


def _skip_dirs() -> set:
    return set(ss.SKIP_DIRS)


def must_be_in_face() -> list:
    """**算出来的**结构性下限：本进程确实 import 过的包内模块，必须在实测面里。

    不写死数字 ⇒ 与"这次跑了多少文件"这个口径无关：全量跑要求得多、单文件跑要求得少，
    但**凡是真的 import 过的，一个都不许在面里缺席**。
    ⚠️ 这里用的 `iso` / `ss` 必须在**模块顶部**就 import 进来 —— 惰性 import 会让
       "面"在缓存之后才长大，于是这条判据咬到的是**测量时序**而不是真缺陷（本轮实测踩过）。
    """
    # ⚠️ 第 92 轮我**改错过这里一次，已撤回**：这是 `_covered_once()` 的**结构性下限**
    #    （「本进程确实 import 过的包内模块，必须在实测面里」），不是 `face`。
    #    把它换成整个 `sys.modules` 面会让这条判据**近乎同义反复** —— 那是削弱判据，不是修 bug。
    #    ⇒ 原样保留；真正要读的是 `face_in_process()`（定义在本文件更靠前处）。
    req = [getattr(iso, "__file__", None), getattr(ss, "__file__", None), __file__]
    return sorted({r for r in (_rel_under(f) for f in req if f) if r})


def tearDownModule():  # noqa: N802 （unittest 钩子）
    """模块收尾时**再判一次**：这时进程已经 import 完它这辈子会 import 的东西。

    进程内面的口径就是"到目前为止导入了什么" ⇒ 收尾时刻才是本次运行**最完整**的那一面。
    在这里判，等于说：**这一整轮跑下来导入过的仓内文件，全都在包里**。
    """
    face = face_in_process()
    v = judge(face, iso.DEPS_SUBDIR, floor=FACE_FLOOR, covered=_covered_once(),
              injected=injected_dirs(), skip_dirs=_skip_dirs(),
              injected_files=injected_files(), harness_files=harness_files(),
              vendor_files=vendor_files())
    if not v["green"]:
        raise AssertionError("【收尾复判】本次运行**全程**的依赖面有问题：%s" % v["reason"])


class TestTheDecisionItself(unittest.TestCase):
    """判定本身（不碰真树）—— 这一层是给变异验证咬的。"""

    def test_empty_face_is_not_green(self):
        v = judge([], "gbt_allinone", floor=FACE_FLOOR)
        self.assertFalse(v["green"], "空面被判成绿 ⇒ 这一条是空话")
        self.assertIn("空话", v["reason"])

    def test_without_the_floor_an_empty_face_would_pass(self):
        """反面样本：**把下限拿掉就会假绿** —— 这就是下限必须留着的理由。"""
        v = judge([], "gbt_allinone", floor=0)
        self.assertTrue(v["green"], "下限为 0 时本该放过空面（正因为如此，下限不许拿掉）")

    def test_an_escapee_is_named(self):
        face = ["gbt_allinone/tools/scan_scope.py", "holo_pet_w3/window.js"]
        v = judge(face, "gbt_allinone", floor=1)
        self.assertFalse(v["green"], "面外文件没被咬住 ⇒ 收据会漏量它")
        self.assertEqual(v["escapees"], ["holo_pet_w3/window.js"])
        self.assertIn("holo_pet_w3/window.js", v["reason"], "红了却不说清是谁 ⇒ 第 104 条")

    def test_containment_is_prefix_not_substring(self):
        face = ["gbt_allinone_extra/x.py", "other/gbt_allinone/x.py"]
        self.assertEqual(outside_face(face, "gbt_allinone"), sorted(face),
                         "拿子串判包内 ⇒ 这两个冒牌货会被放过")
        self.assertFalse(judge(face, "gbt_allinone", floor=1)["green"])

    def test_backslash_paths_are_normalised(self):
        self.assertEqual(outside_face(["gbt_allinone\\tools\\a.py"], "gbt_allinone"), [],
                         "Windows 反斜杠路径没归一化 ⇒ 会把包内文件误判成逃逸")

    def test_a_face_file_the_receipt_fingerprint_cannot_see_is_named(self):
        covered = {"gbt_allinone/a.py"}
        v = judge(["gbt_allinone/a.py", "gbt_allinone/.pylibs/vendored.pyd"],
                  "gbt_allinone", floor=1, covered=covered)
        self.assertFalse(v["green"], "指纹看不见的依赖文件被放过 ⇒ 改它收据不会动（假绿）")
        self.assertEqual(v["uncovered"], ["gbt_allinone/.pylibs/vendored.pyd"])
        self.assertIn(".pylibs", v["reason"])

    def test_covered_must_be_opt_in(self):
        """不传 `covered` 时不许假装查过第 ③ 条。"""
        v = judge(["gbt_allinone/a.py"], "gbt_allinone", floor=1)
        self.assertEqual(v["uncovered"], [])
        self.assertTrue(v["green"])

    # ── 第 57 轮真开火抓到的那个洞：注入面（回归印章自己塞进 PYTHONPATH 的 sitecustomize）──
    def test_an_injected_file_outside_the_package_is_named_not_convicted(self):
        """包外命中**属于本次注入面** ⇒ 记名、不判红（它不是产品的依赖）。"""
        face = ["gbt_allinone/a.py", ".scratch/_stamp_site/sitecustomize.py"]
        v = judge(face, "gbt_allinone", floor=1, injected=[".scratch/_stamp_site"],
                  skip_dirs={".scratch"})
        self.assertTrue(v["green"], "注入面被误判成逃逸 ⇒ 每次带章跑都假红：%s" % v["reason"])
        self.assertEqual(v["injected_hits"], [".scratch/_stamp_site/sitecustomize.py"],
                         "注入命中必须**记名**，不许静默丢掉")
        self.assertIn("注入", v["reason"])

    def test_an_unattributed_outside_file_is_still_convicted(self):
        """有注入面也不能顺手放过别的包外文件 —— 归属要**逐个**判。"""
        face = ["gbt_allinone/a.py", ".scratch/_stamp_site/sitecustomize.py",
                "holo_pet_w3/x.js"]
        v = judge(face, "gbt_allinone", floor=1, injected=[".scratch/_stamp_site"],
                  skip_dirs={".scratch"})
        self.assertFalse(v["green"])
        self.assertEqual(v["escapees"], ["holo_pet_w3/x.js"])

    def test_an_injection_outside_the_pruned_area_is_a_real_hole(self):
        """注入面落在**非剪枝区** ⇒ 收据既看不见又不覆盖 = 真洞，必须红。"""
        v = judge(["gbt_allinone/a.py", "hotfix/sitecustomize.py"], "gbt_allinone", floor=1,
                  injected=["hotfix"], skip_dirs={".scratch", "store"})
        self.assertFalse(v["green"], "非剪枝区的注入面被放过 ⇒ 那是一块收据的盲区")
        self.assertEqual(v["unpruned_injections"], ["hotfix"])
        self.assertIn("真洞", v["reason"])

    def test_injection_is_computed_from_pythonpath(self):
        """注入面必须**算**出来（读 `PYTHONPATH`），不许写死。"""
        fake = {"PYTHONPATH": os.pathsep.join([str(ROOT / ".scratch" / "_stamp_site"),
                                              str(ROOT / "gbt_allinone"), r"C:\elsewhere\x"])}
        got = injected_dirs(env=fake)
        self.assertEqual(got, [".scratch/_stamp_site", "gbt_allinone"],
                         "仓外路径不该进注入面、仓内两条要归一化成相对路径：%r" % got)
        self.assertEqual(injected_dirs(env={}), [])


class TestTheFaceOnThisTree(unittest.TestCase):
    """真树上的实测（整条链的端到端）。"""

    def test_measured_face_lives_inside_the_package_and_the_receipt_covers_it(self):
        face = _face_once()
        v = judge(face, iso.DEPS_SUBDIR, covered=_covered_once(),
                  injected=injected_dirs(), skip_dirs=_skip_dirs(),
                  injected_files=injected_files(), harness_files=harness_files(),
              vendor_files=vendor_files())
        self.assertTrue(v["green"], v["reason"])
        # 结构性下限：本进程确实 import 过的包内模块，一个都不许缺席（与口径无关）
        missing = [p for p in must_be_in_face() if p not in set(face)]
        self.assertEqual(missing, [],
                         "实测面里缺了本进程**确实 import 过**的模块 ⇒ 量法本身塌了：%s" % missing)

    def test_the_target_is_the_same_dir_the_receipts_collect(self):
        """口径一致性：面必须量在**收据真正收集的那个目录**上，指错地方等于偷偷放宽。"""
        self.assertEqual(FACE_TARGET.resolve(), Path(iso.TESTS).resolve(),
                         "判据量的目录与收据收集的目录不是一个 ⇒ 这条判据管不到收据")
        self.assertEqual(iso.DEPS_SUBDIR, "gbt_allinone",
                         "收据那一刀换了名字 ⇒ 上面的实测必须跟着重跑，不许沿用旧结论")

    def test_the_pruned_area_is_really_pruned(self):
        """注入面那条判据成立的前提：`.scratch` 真在剪枝口径里。"""
        self.assertIn(".scratch", _skip_dirs(),
                      "`.scratch` 不在 SKIP_DIRS ⇒ 印章的注入面就成了收据盲区（真洞）")

    @unittest.skipUnless(os.environ.get(HEAVY_ENV) == "1",
                         "重口径（子进程整包收集 ~20-40s、吃内存）默认不跑："
                         "在低内存的全量跑里它会因为起不来而报『量不到』——那是**由负载决定、"
                         "不由对错决定的红**，即错报（本会话第 52/53/54 轮栽过三次）。"
                         "要跑它：设 %s=1" % HEAVY_ENV)
    def test_heavy_arm_agrees_with_the_in_process_face(self):
        m = measure_face()
        self.assertEqual(m["state"], "measured", "重口径量不到：%s" % m["note"])
        heavy = set(m["files"])
        light = set(_face_once())
        v = judge(sorted(heavy), iso.DEPS_SUBDIR, covered=_covered_once(),
                  injected=injected_dirs(), skip_dirs=_skip_dirs())
        self.assertTrue(v["green"], "[重口径] %s\n量法：%s" % (v["reason"], m["note"]))
        self.assertFalse(light - heavy,
                         "进程内面里有**重口径收集不到**的文件（说明它不是收集期依赖）：%s"
                         % sorted(light - heavy)[:5])


class TestTheHeavyMeasurementSaysCannotTell(unittest.TestCase):
    """重口径函数自己的三态：量不到就说量不到（便宜、确定，不依赖负载）。"""

    def _assert_cannot_tell(self, m):
        """「量不到」的**形状**（判状态，不判措辞 —— 措辞里出现『跑出去』三个字不算错）。"""
        self.assertEqual(m["state"], "cannot_tell", "量不到却没报 cannot_tell：%r" % m)
        self.assertFalse(m["available"], "状态与 available 对不上：%r" % m)
        self.assertEqual(m["files"], [],
                         "量不到时不许带一份半截的面出来（会被下一个人当成『面是干净的』）")
        self.assertIn("量不到", m["note"], "回话里没说清『量不到』：%r" % m["note"])

    def test_measure_failure_says_cannot_tell(self):
        """目标不存在（pytest rc=4）⇒ 量不到。"""
        self._assert_cannot_tell(measure_face(target=ROOT / "no_such_dir_zzz", timeout=120))

    def test_a_target_that_collects_nothing_is_cannot_tell_not_clean(self):
        """**收集到 0 条** ⇒ 也必须说「量不到」—— 空面配上没有下限就是一句空话。"""
        empty = Path(tempfile.mkdtemp(prefix="gbt_depface_empty_"))
        try:
            self._assert_cannot_tell(measure_face(target=empty, timeout=120))
        finally:
            shutil.rmtree(empty, ignore_errors=True)

    def test_a_truncated_face_is_cannot_tell(self):
        """**收集没跑通 ⇒ 面被截短**。这条是自家判据咬出来的：截短的面照样"⊆ 包"（假绿通道）。

        造一个真会失败的收集目标（用例文件里放语法错）—— 收集期 import 失败，
        pytest 返回码非 0，而 `sys.modules` 里已经少了一批本该在面上的模块。
        """
        bad = Path(tempfile.mkdtemp(prefix="gbt_depface_bad_"))
        try:
            (bad / "test_zz_broken.py").write_text("def test_x(:\n    pass\n", encoding="utf-8")
            m = measure_face(target=bad, timeout=180)
            self._assert_cannot_tell(m)
            self.assertNotEqual(m["rc"], 0, "收集坏了却报 rc=0：%r" % m)
        finally:
            shutil.rmtree(bad, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
