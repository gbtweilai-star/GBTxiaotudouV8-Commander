
"""测试包入口 —— 测试隔离的唯一兜底（2026-09-17 立）。

为什么需要它：`gbt_allinone/__init__.py` 会 import `.store`，而 `store.py` **在 import 时**
就把 `_paths.STORE_DIR` 绑成常量。若测试模块在"还没设 GBT_STORE_DIR"的进程里被导入
（典型：`python -m unittest discover` 先导入父包 `gbt_allinone`，再执行测试模块体），
**父包这一步就把生产 store 绑上了** —— 测试模块体里再设环境变量已经来不及。

第一次实证（2026-09-17）：`unittest discover` 跑回归，把 `t-sched-run`
（`every_seconds=1` / `enabled=true`）写进了**生产** `gbt_allinone/store/schedules.json`；
契约测试 `test_framework.TestProductionStoreIsolation` 从此守住这条线。

本文件做两件事：
  ① 在任何测试模块体之前，把隔离 store 设好（setdefault，不覆盖调用方显式指定的值）；
  ② 若父包已经绑成生产 store（事后无法纠正），**立刻报错停下** ——
     宁可红，也不许带着生产 store 跑测试。
"""
import atexit
import os
import shutil
import tempfile
from pathlib import Path

_OWN_TEMP_DIRS: list = []


def _isolated_root(env_name: str, prefix: str) -> str:
    """setdefault 到临时根，**并登记清理**（O56 · 2026-10-16）。

    原来这里只有 `mkdtemp`、没有任何一处负责删 ⇒ 每起一个进程就留一个
    `%TEMP%\\gbt_test_store_*`（实测 2026-10-16 已堆到 2146 个）。
    现在只登记**本进程自己造**的那一个：调用方已显式设好的值不覆盖、也不删。
    """
    cur = os.environ.get(env_name)
    if cur:
        return cur
    d = tempfile.mkdtemp(prefix=prefix)
    os.environ[env_name] = d
    _OWN_TEMP_DIRS.append(d)
    return d


@atexit.register
def _cleanup_own_temp_dirs() -> None:
    """进程退出时删掉本包自己造的隔离根（幂等 · 不抛）。"""
    while _OWN_TEMP_DIRS:
        shutil.rmtree(_OWN_TEMP_DIRS.pop(), ignore_errors=True)


_PRODUCTION_STORE = (Path(__file__).resolve().parent.parent / "store").resolve()

_isolated_root("GBT_STORE_DIR", "gbt_test_store_")

from .. import _paths as _paths_mod  # noqa: E402

if Path(_paths_mod.STORE_DIR).resolve() == _PRODUCTION_STORE:
    raise RuntimeError(
        "拒绝在绑定【生产 store】的进程里跑测试：%s\n"
        "原因：gbt_allinone 包在导入时已绑定 STORE_DIR，早于任何测试模块设置环境变量。\n"
        "解法（二选一）：\n"
        "  ① 起 Python 之前先设环境变量：\n"
        '     PowerShell:  $env:GBT_STORE_DIR="$env:TEMP\\gbt_test_store"; '
        "py -3.10 -m unittest discover -s gbt_allinone\\tests -t . -p \"test_checkpoint.py\"\n"
        "  ② 直接跑测试文件（文件头先设环境变量再导包）：\n"
        "     py -3.10 gbt_allinone\\tests\\test_framework.py\n"
        % _paths_mod.STORE_DIR)

# ---- create 写根一次性隔离钩子（R107 · 风哥 2026-09-18 拍）----
# 为什么需要它：create 写根在**调用时**解析 GBT_CREATE_ROOT，不像 store 那样 import 期绑定，
# 所以没有任何"导入顺序"能兜底 —— 只能在包入口把它钉到隔离目录，并拒绝生产根。
# 实测（改动前）：隔离 store + 不设 GBT_CREATE_ROOT + import 本包 -> write_root() 返回生产
# outputs/ —— 任何"忘了设 env"的测试模块只要调一次 create.write 就写生产。
_isolated_root("GBT_CREATE_ROOT", "gbt_test_create_root_")

from .. import file_operation as _fo  # noqa: E402

if _fo.write_root() == _fo.DEFAULT_WRITE_ROOT:
    raise RuntimeError(
        "拒绝在指向【生产 outputs】的进程里跑测试：%s\n"
        "原因：create 写根在**调用时**解析 GBT_CREATE_ROOT；未隔离时一次 create.write "
        "就会把产物写进生产 outputs/。\n"
        "解法：起进程前显式设 GBT_CREATE_ROOT 到隔离目录；或让 gbt_allinone.tests "
        "包先加载（它会 setdefault 到临时根）。" % _fo.write_root())

# ---- see_first「先看后动」闸的蓝图目录隔离（2026-10-17 加）----------------------
# 同 GBT_STORE_DIR / GBT_CREATE_ROOT：不隔离 ⇒ 测试进程读的是**生产** state/blueprints，
# 而干净环境下那里永远没有「TTL 内已批蓝图」⇒ 任何**走行动类 op**（write/run/apply…）
# 的契约测试**恒被拦**（实测：test_coze_mail / test_file_operation 都红在这条，
# 报「未看先动，拒绝推进 · TTL 内无已批蓝图」）。
# 这里 setdefault 到临时目录，并放一份**测试专用已批蓝图**（一跑一换，退出即删）。
# 闸本体逻辑一个字不改：它仍然要求"TTL 内已批蓝图"，只是目录位置可注入（见 see_first._bdir）。
_bdir = Path(_isolated_root("SEE_FIRST_BDIR", "gbt_test_blueprints_"))
try:
    _bdir.mkdir(parents=True, exist_ok=True)
    (_bdir / "unit-test.approved").write_text(
        "单元测试专用已批蓝图（隔离目录；不进生产 state/blueprints）\n", encoding="utf-8")
except OSError:
    pass
