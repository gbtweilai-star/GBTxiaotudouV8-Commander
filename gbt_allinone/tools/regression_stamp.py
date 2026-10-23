# -*- coding: utf-8 -*-
r"""回归四元组印章（R-H7 · 风哥 2026-09-18 判「解释器最阴」）。

为什么要有它
------------
四个变量里，**命令 / store 落点 / 身份读数**都写在命令里或能当场取到 ——
**只有解释器不在命令里**：`python` 是一个名字，不是一个解释器。
名字→实体的解析交给 PATH / install-manager shim / py.ini，还随身份变
（本机实测：`python` → 3.14.5，而记录里写的是 3.12；`py -0p` 名单里根本没有 3.14.5）。
更阴的是它不只改计数，还改**依赖来源**：`.pylibs` 只有 cp314 一棵 ABI 树，
3.14 下 `dxcam`/`cv2` 来自 `.pylibs`，3.12 下则由系统提供。

规则
----
1. **没有印章的回归结论不采信**：`run` 子命令先落四元组再跑。
2. **`run` 强制 `--expect-python X.Y`**：实际解释器不匹配就**拒绝跑**（fail-closed），
   而不是"跑完再解释为什么红集变了"。
3. 判成败只认**原生 rc** 与结尾 `Ran N tests` / `OK|FAILED` —— 与 `native_rc.py` 同一条铁律：
   禁止用管道后的外层 rc 判成败（本仓 R96 / R102 两次同坑）。
4. 只读：不装依赖、不改配置、不写生产 store；证据落 `.scratch/`。
5. **`run` 强制 `--store fresh|<路径>`**：store 落点同样"不在命令里"就会静默漂
   （实测：env 在 `import gbt_allinone` 之后再改**不生效**，`.pylibs` 那套 `STORE_DIR` 是 import 期绑定）。
6. **孩子要自报家门**：`run` 会注入一段 `sitecustomize`，让子进程在**退出时**打印它真正绑定的 store；
   请求的 store 与孩子自报的不一致 → 直接标红（这才是「落点」的证据，不是我写的那个字符串）。
7. **每个变量都要有原因码**（风哥 2026-09-18 判据）：身份有 `non_interactive_desktop`，
   解释器 / store 也必须各有一个**可 grep 的原因码**，否则它会在最需要定位时隐身：
   `interpreter_not_declared` · `interpreter_mismatch` · `store_not_declared` · `store_binding_mismatch`。
8. **跨口径必须显式声明**（风哥 2026-09-18 再收一格）：`--same-as <旧印章.json>` 会把本次四元组
   与旧基线逐项比对；**不同口径时打印 `comparability=not_comparable` + `reason_code=not_comparable`**，
   提醒"红集差异不得直接判为代码坏了"，并且**只允许逐名比对**。
   物理事实：本沙箱身份下 `C:\\Python312\\python.exe` 起不来（stdlib 读不到）
   ⇒ **"完全复现基线"在这套环境里做不到**，所以声明不是礼貌，是必需品。
9. **内存也要进章、也要设闸**（风哥 2026-09-18「内存需求」）：内存是**会漂的**环境变量
   （本机实测可用在 0.37–0.97 GB 之间浮动，占用 86–94%）；跑测试前声明 `--need-memory X`，
   低于阈值即拒绝（`reason_code=insufficient_memory`），免得把 OOM 造成的红当成代码红。
10. **磁盘也要进章、也要设闸**（风哥 2026-09-18「磁盘，无内存压力」）：内存会回落、**磁盘只降不升**
   ——所以磁盘的真口径是**预算 + 回收**，闸门只是下限（`--need-disk X` / `reason_code=insufficient_disk`）。
   本机实测：C: 475.9 GB 总 / **65.1 GB 可用**；工作区自身 ≈1.4 GB（其中 `.scratch` 自造 128 MB）。
11. **临界 ≠ 够**（风哥 2026-09-18「临界 / 推理峰值」）：判据不是"可用 ≥ 峰值"，而是
   **可用 ≥ 峰值 × 1.3 且不在换页中**（本机实测 pagefile 已吃 11.35 GB ⇒ 任何本地推理都会抖动）。
   声明 `--need-memory X` 时，若检测到重度换页 → 拒绝（`reason_code=swapping_active`）；
   确要跑加 `--allow-swap`。理由：换页会把"内存不足"伪装成"慢"，而慢会被读成"模型不行"。
12. **「零新增依赖」要可验**（风哥 2026-09-18：A 的定义就是零新增依赖）：
   印章每次记一枚**依赖指纹**（site-packages 的 dist-info 名单 hash + 关键包版本）。
    两次印章指纹一致 ⇒ 期间没装过东西；不一致 ⇒ 得说清装了什么、为什么。
    **口令**：A 版验收的判据 0 = 跑前跑后依赖指纹一致。这也是"一次只动一个变量"的机器版。

用法
----
    python -m gbt_allinone.tools.regression_stamp stamp
    python -m gbt_allinone.tools.regression_stamp run --expect-python 3.12 --store fresh -- \
        -m unittest gbt_allinone.tests.test_framework
    python -m gbt_allinone.tools.regression_stamp run --expect-python 3.14 --store fresh \
        --same-as .scratch/_stamp_20260918T230142-601400.json -- -m unittest <模块...>
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# 🔴 2026-09-23 第 40 轮补：**报告通道的编码也是判据的一部分**。
# 实测（`test_regression_stamp.py` 三条同时红）：本器 606 行那句
#   `print('[stamp] 依赖面未变 = True … ⇒ **结论**')`
# 里的 `⇒`（U+21D2）在 **cp936 管道**下抛 `UnicodeEncodeError: 'gbk' codec can't encode …`
# ⇒ 子进程当场崩 ⇒ 父进程找不到「依赖面未变 = True」这个标记 ⇒ 测试报红。
# 红的是**打印**，不是判据；但读数的人只会看到"印章坏了"。
# 同目录的 clean_residue / probe-* / dup-source-inventory 早就都锁了 UTF-8，本器漏了。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent.parent
SCRATCH = ROOT / '.scratch'


def _identity() -> dict:
    """身份读数（单一来源：capture_environment.capacity()，轻量、不枚举显卡）。"""
    try:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone.tentacle import capture_environment as ce
        return ce.capacity()
    except Exception as exc:  # noqa: BLE001 —— 章子盖不上也要如实写出来
        return {'ok': False, 'error': f'{type(exc).__name__}: {exc}'[:160]}


def _git_head() -> dict:
    try:
        head = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=str(ROOT),
                              capture_output=True, text=True, shell=False)
        date = subprocess.run(['git', 'log', '-1', '--format=%ci'], cwd=str(ROOT),
                              capture_output=True, text=True, shell=False)
        return {'head': (head.stdout or '').strip() or None,
                'head_date': (date.stdout or '').strip() or None}
    except Exception as exc:  # noqa: BLE001
        return {'head': None, 'error': f'{type(exc).__name__}: {exc}'[:120]}


def _store_dir() -> str:
    try:
        sys.path.insert(0, str(ROOT))
        from gbt_allinone import _paths
        return str(_paths.STORE_DIR)
    except Exception as exc:  # noqa: BLE001
        return f'(读不到: {type(exc).__name__})'


class _Mem(ctypes.Structure):
    _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]


class _Perf(ctypes.Structure):
    _fields_ = [('cb', ctypes.c_ulong), ('CommitTotal', ctypes.c_size_t),
                ('CommitLimit', ctypes.c_size_t), ('CommitPeak', ctypes.c_size_t),
                ('PhysicalTotal', ctypes.c_size_t), ('PhysicalAvailable', ctypes.c_size_t),
                ('SystemCache', ctypes.c_size_t), ('KernelTotal', ctypes.c_size_t),
                ('KernelPaged', ctypes.c_size_t), ('KernelNonpaged', ctypes.c_size_t),
                ('PageSize', ctypes.c_size_t), ('HandleCount', ctypes.c_ulong),
                ('ProcessCount', ctypes.c_ulong), ('ThreadCount', ctypes.c_ulong)]


_psapi = ctypes.WinDLL('psapi', use_last_error=True)
_psapi.GetPerformanceInfo.argtypes = [ctypes.POINTER(_Perf), ctypes.c_ulong]
_psapi.GetPerformanceInfo.restype = ctypes.c_int


def _memory() -> dict:
    """内存同样是「会漂的变量」（实测可用 0.37–0.97 GB）。

    只报「物理可用」会骗人：本机实测物理 7.39 GB、**提交已用 17.88 GB / 上限 23.39 GB**、
    分页文件已吃 ≈10.96 GB —— 内存压力早被静默转成了磁盘压力（换页）。
    **加载权重时真正撞的是 commit limit，不是物理可用量**，所以三个数一起报。
    """
    try:
        m = _Mem()
        m.dwLength = ctypes.sizeof(_Mem)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            return {'ok': False}
        out = {'ok': True,
               'total_gb': round(m.ullTotalPhys / 2 ** 30, 2),
               'avail_gb': round(m.ullAvailPhys / 2 ** 30, 2),
               'load_pct': int(m.dwMemoryLoad)}
        try:
            perf = _Perf()
            perf.cb = ctypes.sizeof(_Perf)
            if _psapi.GetPerformanceInfo(ctypes.byref(perf), perf.cb):
                ps = perf.PageSize
                commit = perf.CommitTotal * ps
                phys = perf.PhysicalTotal * ps
                avail = perf.PhysicalAvailable * ps
                out['commit_used_gb'] = round(commit / 2 ** 30, 2)
                out['commit_limit_gb'] = round(perf.CommitLimit * ps / 2 ** 30, 2)
                out['pagefile_used_gb'] = round(max(0.0, commit - (phys - avail)) / 2 ** 30, 2)
        except Exception:
            pass
        return out
    except Exception as exc:  # noqa: BLE001
        return {'ok': False, 'error': f'{type(exc).__name__}: {exc}'[:120]}


def _disk() -> dict:
    """磁盘只降不升：内存能回落，磁盘不能 —— 所以它是预算项，不只是闸门项。"""
    try:
        import shutil
        usage = shutil.disk_usage(str(ROOT.anchor or 'C:\\'))
        return {'ok': True, 'drive': str(ROOT.anchor or 'C:\\'),
                'total_gb': round(usage.total / 2 ** 30, 1),
                'free_gb': round(usage.free / 2 ** 30, 1)}
    except Exception as exc:  # noqa: BLE001
        return {'ok': False, 'error': f'{type(exc).__name__}: {exc}'[:120]}


_KEY_PKGS = ('numpy', 'pillow', 'pyautogui', 'mss', 'dxcam', 'onnxruntime', 'torch',
             'comtypes', 'requests', 'httpx')


def _deps() -> dict:
    """依赖指纹：「零新增依赖」要能验，不能只靠声明。

    取当前解释器的所有 dist-info 名单（排序）+ 关键包的存在与版本，合成一枚 sha256 短指纹。
    两次印章指纹一致 ⇒ 期间没装/卸任何包。
    """
    import importlib.metadata as md
    import hashlib
    try:
        names = sorted({d.metadata['Name'] for d in md.distributions() if d.metadata['Name']})
    except Exception:
        names = []
    got = {}
    for pkg in _KEY_PKGS:
        try:
            got[pkg] = md.version(pkg)
        except Exception:
            got[pkg] = None
    blob = ('|'.join(names) + '||' + '|'.join('%s=%s' % (k, got[k]) for k in _KEY_PKGS))
    return {'count': len(names), 'sha16': hashlib.sha256(blob.encode('utf-8')).hexdigest().upper()[:16],
            'key': got}


def _load_old(path: str) -> dict:
    """读旧印章/旧基线。基线文件把每次跑嵌在 runs[] 里 —— 取**最后一次**。"""
    try:
        doc = json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception as exc:  # noqa: BLE001
        return {'_error': f'{type(exc).__name__}: {exc}'[:160]}
    if isinstance(doc, dict) and isinstance(doc.get('runs'), list) and doc['runs']:
        doc = doc['runs'][-1]
    return doc if isinstance(doc, dict) else {'_error': '旧印章格式不认识'}


def _scope_of(stamp_like: dict) -> dict:
    """口径四要素 + store 模式（store 原始路径每次 fresh 都不同，比它没意义）。"""
    interp = stamp_like.get('interpreter') or {}
    ident = stamp_like.get('identity') or {}
    req = (stamp_like.get('store') or {}).get('requested') or ''
    mem = (stamp_like.get('memory') or {}).get('avail_gb')
    if mem is None:
        bucket = None
    elif float(mem) <= 0.5:
        bucket = 'tight(<=0.5GB)'
    elif float(mem) <= 1.5:
        bucket = 'mid(0.5-1.5GB)'
    else:
        bucket = 'loose(>1.5GB)'
    return {
        'interpreter': '%s %s' % (interp.get('version'), interp.get('cache_tag')),
        'identity': '%s|%s|%s' % ('interactive' if ident.get('interactive_desktop') else 'non_interactive',
                                  ident.get('desktop'), ident.get('process_session')),
        'deps': (stamp_like.get('deps') or {}).get('sha16'),
        'git': (stamp_like.get('git') or {}).get('head'),
        'store_mode': 'fresh' if 'gbt_stamp_store_' in str(req) else ('explicit' if req else None),
        'mem_bucket': bucket,
    }


def compare_scope(old: dict, cur: dict) -> tuple:
    """逐项比对口径 → (diffs, unknown, disclosed)。

    **任一侧为 None 记为"未知"而不是"不一致"** —— 旧基线可能没存这一项（例如 A 基线未记 store 模式），
    把未知当差异会造成假红（2026-09-18 实测踩到）。未知项要**如实列出**，不能悄悄跳过。

    **mem_bucket 只披露、不判**：实测 A 的判据在 avail 0.29 与 0.86 GB 两个窗口下逐条相同
    （判据②③不受内存影响），所以内存口径**进比对但不作 gate** —— 否则会把"实测证明不敏感"的变量
    变成假红来源。它仍然要打印出来，因为它解释了"这次跑的时候机器有多紧"。
    """
    diffs, unknown, disclosed = [], [], []
    for k in ('interpreter', 'identity', 'deps', 'git', 'store_mode', 'mem_bucket'):
        a, b = old.get(k), cur.get(k)
        if a is None or b is None:
            (disclosed if k == 'mem_bucket' else unknown).append(k)
            continue
        if a != b:
            (disclosed if k == 'mem_bucket' else diffs).append((k, a, b))
    return diffs, unknown, disclosed


def comparability_token(diffs: list, unknown: list) -> str:
    """口径比对的**机读令牌**（三态，`--same-as` 用）。

    🔴 2026-09-23 第 51 轮抽出（原来这段判断**埋在 `cmd_run` 的打印里**，没法判）：
      原文只有一句 `same = not diffs` ⇒ **明明有 N 项无法比对**，
      只要没有确凿差异就照样打 `comparability=same_scope`。
      人读那行括号里写了「未知项见上」，**但令牌把那句话丢了** ——
      下游只认 `same_scope`，会直接拿两次的红集对比，而**有些轴根本没验过**。
      ⇒ 抽成纯函数，好让判据直接钉住这三态（埋在打印里的逻辑没人守得住）。
    """
    if diffs:
        return 'not_comparable'
    if unknown:
        return 'same_scope_unverified_axes'
    return 'same_scope'


def collect(argv: list) -> dict:
    return {
        'at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'command': {'argv': argv, 'cwd': os.getcwd()},
        'store': {'GBT_STORE_DIR_env': os.environ.get('GBT_STORE_DIR') or None,
                  'bound_STORE_DIR': _store_dir()},
        'identity': _identity(),
        # 🔴 2026-09-23 第 51 轮加（**护照里的"四元组"一直是残缺的**）：
        #    `framework_gate.py:334` 从印章里取的是
        #    `("python", "store", "comparability", "identity")`，
        #    而这里原来**没有 `python`、也没有 `comparability`** ⇒ 那个 `if k in data`
        #    **静默跳过**它们，护照里只记到 **2/4**，且一声不响。
        #    实测（`.scratch/stamp_four_tuple_probe.py`）：盘上 **52 个印章，齐的 0 个（0%）**。
        #    ⇒ 这里补上 `python`（与 `_scope_of` 里那个字符串同形，便于人读与比对）。
        'python': '%s %s' % (sys.version.split()[0], sys.implementation.cache_tag),
        # `comparability` 也是护照四元组要的一项 ⇒ **必须每个章都有**。
        # ⚠️ 第一版我把它写在 `cmd_run` 里 —— 于是 `stamp` 子命令盖的章**照样缺这一项**
        #    （实测当场发现：`stamp` 走的是 `collect()` 而不过 `cmd_run`）。
        #    ⇒ 默认值放进 `collect()` 本身，**与入口无关**；`--same-as` 那一支再覆盖成真值。
        #    `not_requested` 是**诚实的默认**：没请求比对，本就是这个状态，不是"漏了"。
        'comparability': 'not_requested',
        # 🔴 2026-09-23 第 52 轮加：**内容指纹**（口径四要素管不了"内容有没有被改"）。
        #    第 51 轮两份回归读数都被并发写入污染，而我是事后按 mtime 考古才发现的 ⇒
        #    从这一轮起，印章自己带"跑之前树长什么样"。
        #    第 53 轮：**只写摘要进 .json**（明细 951 行会把印章撑大），明细留在内存里做 diff。
        'tree': _compact(_fingerprint()),
        'interpreter': {'version': sys.version.split()[0],
                        'cache_tag': sys.implementation.cache_tag,
                        'executable': sys.executable},
        'memory': _memory(),
        'disk': _disk(),
        'deps': _deps(),
        'git': _git_head(),
    }


def _fingerprint(with_rows: bool = False, subdir: str = "") -> dict:
    """整棵（剪枝后）代码树的内容指纹 —— 范围口径复用 `scan_scope`（**只有一份实现**）。

    `with_rows=True` ⇒ 另带逐文件明细，好在"树被改了"时**指名是谁动的**（第 53 轮加）。
    `subdir` ⇒ **只算依赖面那一刀**（第 56 轮加）。
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from scan_scope import tree_fingerprint
        return tree_fingerprint(ROOT, with_rows=with_rows, subdir=(subdir or None))
    except Exception as e:                                   # noqa: BLE001
        # 取不到就**如实报错**，不许返回一个看起来正常的空指纹（那会让"没变化"变成一句空话）
        return {'sha256': None, 'files': None, 'bytes': None,
                'unreadable': [], 'error': '%s: %s' % (type(e).__name__, e)}


# 依赖面 = 包（**保守超集**：实测依赖面 199 个文件 ⊂ 包内 351+ 个 .py）
DEPS_SUBDIR = 'gbt_allinone'


def _compact(fp: dict) -> dict:
    """去掉逐文件明细的那一份 —— **印章文件不该被 951 行明细撑大**。

    ⚠️ 但明细**不是丢掉**：它在内存里留着做 `_diff`（见 `cmd_run`），
       只是**不写进 .json**。判据里有一条专门看这件事。
    """
    return {k: v for k, v in (fp or {}).items() if k != 'rows'}


def _diff(before: dict, after: dict) -> dict:
    """是谁动的 —— "不作收据"必须能指名，否则又绕回考古（第 53 轮）。"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from scan_scope import diff_trees
        return diff_trees(before, after)
    except Exception as e:                                   # noqa: BLE001
        return {'available': False, 'added': [], 'removed': [], 'changed': [],
                'note': '取不出差异：%s: %s' % (type(e).__name__, e)}


def write_stamp(stamp: dict, tag: str = 'stamp') -> Path:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    unique = time.strftime('%Y%m%dT%H%M%S') + '-%06d' % (time.time_ns() % 1000000)
    path = SCRATCH / ('_%s_%s.json' % (tag, unique))
    path.write_text(json.dumps(stamp, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


def print_stamp(stamp: dict, path: Path) -> None:
    ident = stamp['identity']
    interp = stamp['interpreter']
    store = stamp['store']['bound_STORE_DIR']
    print('=' * 62)
    print('回归四元组印章（没有它，结论不采信）')
    print('=' * 62)
    print('  命令      %s' % subprocess.list2cmdline([str(a) for a in stamp['command']['argv']]))
    print('  store     %s' % store)
    print('  身份      interactive_desktop=%s · desktop=%s · session=%s'
          % (ident.get('interactive_desktop'), ident.get('desktop'), ident.get('process_session')))
    print('  解释器    %s · %s · %s'
          % (interp['version'], interp['cache_tag'], interp['executable']))
    print('  git       %s (%s)' % (stamp['git'].get('head'), stamp['git'].get('head_date')))
    print('  证据      %s' % path)
    print('=' * 62)


VERDICT_RE = re.compile(r'^(Ran \d+ tests.*|OK.*|FAILED.*)$', re.M)
SELF_REPORT_RE = re.compile(r'^\[stamp\] (child_bound_store|child_interpreter)=(.*)$', re.M)

SITECUSTOMIZE = '''# 由 gbt_allinone/tools/regression_stamp.py 生成：子进程退出时自报绑定落点。
import atexit
import sys


def _report():
    mod = sys.modules.get('gbt_allinone._paths')
    where = getattr(mod, 'STORE_DIR', '?') if mod is not None else '(child 未 import gbt_allinone)'
    sys.stderr.write('[stamp] child_bound_store=%s\\n' % where)
    sys.stderr.write('[stamp] child_interpreter=%s %s\\n'
                     % (sys.version.split()[0], sys.implementation.cache_tag))


atexit.register(_report)
'''


def _verdict(text: str) -> list:
    return [m.group(1).strip() for m in VERDICT_RE.finditer(text)][-2:]


def cmd_stamp(_args) -> int:
    stamp = collect(['regression_stamp', 'stamp'])
    path = write_stamp(stamp, 'stamp')
    print_stamp(stamp, path)
    return 0


def cmd_run(args) -> int:
    want = (args.expect_python or '').strip()
    have = sys.version.split()[0]
    want_store = (args.store or '').strip()
    if not want_store:
        print('拒绝执行：run 子命令必须显式给 --store fresh|<路径>（把 store 落点逼进命令里）')
        print('reason_code=store_not_declared')
        return 2
    if want_store == 'fresh':
        store_dir = tempfile.mkdtemp(prefix='gbt_stamp_store_')
    else:
        store_dir = str(Path(want_store).expanduser())
        Path(store_dir).mkdir(parents=True, exist_ok=True)
    site_dir = SCRATCH / '_stamp_site'
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / 'sitecustomize.py').write_text(SITECUSTOMIZE, encoding='utf-8')
    child_env = os.environ.copy()
    child_env['GBT_STORE_DIR'] = store_dir
    child_env['PYTHONPATH'] = str(site_dir) + os.pathsep + child_env.get('PYTHONPATH', '')
    # 🔴 2026-09-23 第 53 轮修（**我把"跑前"那一份挪到了跑后 ⇒ 永远报"树没变"**）：
    #    第 52 轮 `before` 取自 `collect()`（在**孩子跑之前**算的），是对的；
    #    第 53 轮我为了拿"带明细"的那一份，顺手改成 `before = _fingerprint(...)` 写在**跑完那几行里**
    #    —— 于是两次指纹**都在孩子跑完之后**取，**任何改动都测不出来**。
    #    实测当场撞到：让孩子建一个新 .py 文件，读数照样是
    #    「树指纹未变 = True（962 个文件）」—— **一个永远说"干净"的机制，比没有更坏**。
    #    ⇒ "跑前"必须在**这里**（孩子启动之前）取，带明细存在内存里，跑完再用。
    tree_before_full = _fingerprint(with_rows=True)
    # 🔴 第 56 轮：**依赖面**那一刀（实测依赖面 199 个文件全在包里；近几轮"导致不作收据"
    #    的 13 个改动里 12 个在包外、与本次读数无关 ⇒ **收据看这一份**）。
    deps_before_full = _fingerprint(with_rows=True, subdir=DEPS_SUBDIR)
    mem = _memory()
    need = float(args.need_memory or 0)
    if need and (not mem.get('ok') or float(mem.get('avail_gb') or 0) < need):
        print('拒绝执行：需要可用内存 >= %.2f GB，实测 %.2f GB（占用 %s%%）'
              % (need, float(mem.get('avail_gb') or 0), mem.get('load_pct')))
        print('原因：内存会漂（本机实测可用 0.37–0.97 GB）；拿 OOM 造成的红当代码红，等于自欺。')
        print('reason_code=insufficient_memory')
        return 2
    disk = _disk()
    need_disk = float(args.need_disk or 0)
    if need_disk and (not disk.get('ok') or float(disk.get('free_gb') or 0) < need_disk):
        print('拒绝执行：需要 %s 可用磁盘 >= %.1f GB，实测 %.1f GB'
              % (disk.get('drive'), need_disk, float(disk.get('free_gb') or 0)))
        print('原因：磁盘只降不升 —— 内存能回落，磁盘不能；先回收再跑，别把产物写进残量里。')
        print('reason_code=insufficient_disk')
        return 2
    pf_gb = float(mem.get('pagefile_used_gb') or 0)
    if need and pf_gb > 0.2 and not args.allow_swap:
        print('拒绝执行：检测到**正在换页**（分页文件已用 %.2f GB）。' % pf_gb)
        print('原因：临界不等于够 —— 可用内存 %.2f GB 只是名义值；物理不足时不报错，只变慢，'
              '而慢会被误读成"模型不行/代码退步"。' % float(mem.get('avail_gb') or 0))
        print('判据：可用 >= 峰值 × 1.3 **且**不在换页中。确要跑：加 --allow-swap。')
        print('reason_code=swapping_active')
        return 2
    stamp = collect(sys.argv)
    stamp['store']['requested'] = store_dir
    # 跑前那一份**带明细**的指纹（第 53 轮）：摘要进印章，明细留内存做 diff。
    # ⚠️ 它必须来自**孩子启动之前**取的那一次（`tree_before_full`），
    #    不许在这里重新算 —— 那样"跑前"就成了"跑后"，改动一律测不出来（第 53 轮踩过）。
    stamp['tree'] = _compact(tree_before_full)
    path = write_stamp(stamp, 'stamp')
    print_stamp(stamp, path)
    print('  store(请求) %s' % store_dir)
    print('=' * 62)
    if not want:
        print('拒绝执行：run 子命令必须显式给 --expect-python X.Y（把解释器逼进命令里）')
        print('reason_code=interpreter_not_declared')
        return 2
    if not have.startswith(want):
        print('拒绝执行：实际解释器 %s（%s）与 --expect-python %s 不符。'
              % (have, sys.implementation.cache_tag, want))
        print('原因：解释器不匹配会同时改「判据在哪跑」与「依赖从哪来」（.pylibs ABI overlay），'
              '红集不可比 —— 请换成匹配的解释器再跑。')
        print('reason_code=interpreter_mismatch')
        return 2
    cmd = list(args.rest)
    if cmd and cmd[0] == '--':
        cmd = cmd[1:]
    if not cmd:
        print('拒绝执行：-- 后面没给命令')
        return 2
    if cmd[0].startswith('-') or cmd[0].lower().endswith('.py'):
        # 首参以 '-' 开头（典型 `-m unittest ...` / `-c "..."`）或以 .py 结尾（脚本路径）
        # → 用**当前解释器**跑，免得裸 `-m` / 裸脚本路径让 CreateProcess 找不到
        # 可执行文件（R-H7 实测踩过 `WinError 2`；R-H18 又踩过 `WinError 193 不是有效 Win32 应用`）。
        cmd = [sys.executable] + cmd
    print('执行：%s' % ' '.join(cmd))
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       encoding='utf-8', errors='replace', shell=False, env=child_env)
    text = (p.stdout or '') + (p.stderr or '')
    out = path.with_suffix('.txt')
    out.write_text(text, encoding='utf-8')
    report = dict(SELF_REPORT_RE.findall(text))
    child_store = (report.get('child_bound_store') or '').strip()
    child_py = (report.get('child_interpreter') or '').strip()
    print('孩子自报     store = %s' % (child_store or '(无自报 → sitecustomize 没被加载)'))
    print('             解释器 = %s' % (child_py or '(无自报)'))
    # 孩子没 import 仓内包时 sitecustomize 会写一句说明，**那不是"落点不一致"**（假阳性，
    # 2026-09-18 用裸 `-c "print(1)"` 的孩子实测踩到）。
    _no_report = (not child_store) or child_store.startswith('(child')
    if child_store and not _no_report and os.path.normcase(child_store) != os.path.normcase(store_dir):
        print('!! 落点不一致：请求 %s ≠ 实际 %s —— 本次结论的 store 归属不可采信'
              % (store_dir, child_store))
        print('reason_code=store_binding_mismatch')
    # 解释器同样要「孩子自报 vs 请求」比对 —— `--expect-python` 只校验了**印章自己**，
    # 而真正跑判据的是孩子（风哥 2026-09-18「新变量：解释器」）。
    if child_py and want and not child_py.split()[0].startswith(want):
        print('!! 孩子解释器不一致：请求 %s ≠ 实际 %s —— 本次结论的解释器归属不可采信'
              % (want, child_py))
        print('reason_code=interpreter_child_mismatch')
    store_match = bool(child_store) and _no_report is False and \
        os.path.normcase(child_store) == os.path.normcase(store_dir)
    print('原生 rc = %s   （判成败只看这个 + 下面这行，不看管道 rc）' % p.returncode)
    for line in _verdict(text):
        print('  %s' % line)
    print('  原始输出 %s' % out)
    ident = stamp['identity']
    print('--- 可 grep 的可见化出口 ---')
    print('[stamp] interpreter=%s %s' % (have, sys.implementation.cache_tag))
    print('[stamp] store_requested=%s' % store_dir)
    print('[stamp] store_match=%s' % store_match)
    print('[stamp] identity=%s desktop=%s session=%s'
          % ('interactive' if ident.get('interactive_desktop') else 'non_interactive',
             ident.get('desktop'), ident.get('process_session')))
    print('[stamp] memory=avail %s GB / total %s GB (load %s%%)'
          % (mem.get('avail_gb'), mem.get('total_gb'), mem.get('load_pct')))
    if mem.get('commit_used_gb') is not None:
        print('[stamp] commit=%s/%s GB pagefile=%s GB %s'
              % (mem.get('commit_used_gb'), mem.get('commit_limit_gb'),
                 mem.get('pagefile_used_gb'),
                 '(swapping)' if float(mem.get('pagefile_used_gb') or 0) > 0.2 else ''))
    print('[stamp] disk=%s free %s GB / total %s GB'
          % (disk.get('drive'), disk.get('free_gb'), disk.get('total_gb')))
    deps = _deps()
    print('[stamp] deps=%d pkgs sha16=%s key=%s'
          % (deps['count'], deps['sha16'],
             ','.join('%s:%s' % (k, deps['key'][k] or '-') for k in ('numpy', 'onnxruntime', 'torch', 'dxcam'))))
    if args.same_as:
        old = _load_old(args.same_as)
        print('--- 口径比对（--same-as）---')
        print('  旧基线: %s' % args.same_as)
        if old.get('_error'):
            print('  读不到旧基线：%s' % old['_error'])
            print('  comparability=unknown')
            print('reason_code=baseline_unreadable')
            stamp['comparability'] = 'unknown'
        else:
            diffs, unknown, disclosed = compare_scope(_scope_of(old), _scope_of(stamp))
            for k, a, b in diffs:
                print('  [X ] %-12s 旧=%s  新=%s' % (k, a, b))
            for k in unknown:
                print('  [?? ] %-12s 旧基线未记录 -> 本项无法比对（不算差异）' % k)
            for item in disclosed:
                if isinstance(item, tuple):
                    print('  [~~ ] %-12s 旧=%s  新=%s（只披露，不判口径）' % item)
                else:
                    print('  [~~ ] %-12s 旧基线未记录（只披露，不判口径）' % item)
            # 🔴 2026-09-23 第 51 轮修：三态令牌（见 `comparability_token` 的注释）。
            #    原来只有 `same = not diffs` ⇒ "有未知轴"被说成了"同口径"。
            token = comparability_token(diffs, unknown)
            if token == 'not_comparable':
                print('  **本次不可与原基线同口径比较**：红集差异不得直接判为"代码坏了"；只允许逐名比对。')
                print('  comparability=not_comparable')
                print('reason_code=not_comparable')
            elif token == 'same_scope_unverified_axes':
                print('  [OK] 已记录项全部一致 —— **但有 %d 项旧基线没记录（%s），'
                      '这些轴这次没验过**，别把"没有确凿差异"当成"全轴同口径"。'
                      % (len(unknown), '、'.join(unknown)))
                print('  comparability=same_scope_unverified_axes')
                print('reason_code=unknown_axes_present')
            else:
                print('  [OK] 已记录项全部一致（且无未知项）')
                print('  comparability=same_scope')
            stamp['comparability'] = token
    print('[stamp] rc=%s' % p.returncode)
    # 🔴 2026-09-23 第 52 轮：跑完**再算一次指纹** —— 这是"这次读数干不干净"的**证明**。
    after = _fingerprint(with_rows=True)
    before = tree_before_full                       # ← **孩子跑之前**取的那一份（第 53 轮修）
    stamp['tree_after'] = _compact(after)
    same_tree = (before.get('sha256') is not None and before.get('sha256') == after.get('sha256'))
    stamp['tree_changed'] = (not same_tree)
    delta = None if same_tree else _diff(before, after)
    stamp['tree_delta'] = delta
    # 🔴 第 56 轮：**收据的有效性看依赖面**（整仓的 tree_changed 只作披露）。
    dep_after = _fingerprint(with_rows=True, subdir=DEPS_SUBDIR)
    stamp['deps_subdir'] = DEPS_SUBDIR
    stamp['deps_after'] = _compact(dep_after)
    same_deps = (deps_before_full.get('sha256') is not None
                 and deps_before_full.get('sha256') == dep_after.get('sha256'))
    stamp['deps_changed'] = (not same_deps)
    dep_delta = None if same_deps else _diff(deps_before_full, dep_after)
    stamp['deps_delta'] = dep_delta
    if before.get('sha256') is None or after.get('sha256') is None \
            or deps_before_full.get('sha256') is None or dep_after.get('sha256') is None:
        print('[stamp] ⚠️ 树指纹**取不到**（%s / %s）⇒ **本次无法证明"跑的时候树没被改"**'
              % (before.get('error'), deps_before_full.get('error')))
        print('           tree_changed=unknown')
    elif not stamp['deps_changed']:
        # 🔴 第 56 轮：**依赖面没变 ⇒ 收据成立**（哪怕整仓被别的会话改过）
        print('[stamp] 依赖面未变 = True（%d 个文件 / %s…）⇒ **收据成立**'
              % (dep_after.get('files'), str(dep_after.get('sha256'))[:12]))
        if stamp['tree_changed']:
            names = []
            for kind in ('changed', 'added', 'removed'):
                names += (delta or {}).get(kind) or []
            print('           （面外另有 %d 个文件动过：%s%s —— **与本次读数无关**）'
                  % (len(names), '、'.join(names[:4]), '…' if len(names) > 4 else ''))
    else:
        print('[stamp] !! **依赖面在跑的中途被改了** —— 这份读数**不能当收据**，只能当冒烟：')
        print('           跑前 %s…  跑后 %s…'
              % (str(deps_before_full.get('sha256'))[:12], str(dep_after.get('sha256'))[:12]))
        if not (dep_delta or {}).get('available'):
            print('           ⚠️ %s' % (dep_delta or {}).get('note'))
        else:
            for kind, label in (('changed', '改了'), ('added', '新增'), ('removed', '删了')):
                names = dep_delta.get(kind) or []
                if names:
                    shown = '、'.join(names[:6]) + ('…（共 %d 个）' % len(names)
                                                    if len(names) > 6 else '')
                    print('           %s %d 个：%s' % (label, len(names), shown))
    stamp['result'] = {'rc': int(p.returncode), 'store_match': store_match,
                       'child_report': report, 'verdict': _verdict(text)}
    path.write_text(json.dumps(stamp, ensure_ascii=False, indent=2), encoding='utf-8')
    return int(p.returncode)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog='regression_stamp', description='回归四元组印章')
    sub = ap.add_subparsers(dest='sub')
    sub.add_parser('stamp', help='只打四元组并落盘')
    rp = sub.add_parser('run', help='先打章，再跑命令（强制 --expect-python）')
    rp.add_argument('--expect-python', default='', help='要求的主版本.次版本，如 3.12')
    rp.add_argument('--store', default='', help='store 落点：fresh（每次全新）或显式路径')
    rp.add_argument('--need-memory', default='', help='要求的最低可用内存（GB），低于则拒绝')
    rp.add_argument('--need-disk', default='', help='要求的最低可用磁盘（GB），低于则拒绝')
    rp.add_argument('--allow-swap', action='store_true', help='允许在换页中跑（默认拒绝）')
    rp.add_argument('--same-as', default='', help='与旧印章/旧基线比对口径；不同则显式声明 not_comparable')
    rp.add_argument('rest', nargs=argparse.REMAINDER, help='-- 之后的真实命令')
    args = ap.parse_args(argv)
    if args.sub == 'stamp':
        return cmd_stamp(args)
    if args.sub == 'run':
        return cmd_run(args)
    ap.print_help()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
