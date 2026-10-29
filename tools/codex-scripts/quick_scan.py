# -*- coding: utf-8 -*-
"""全维度扫描故障问题 · 速扫（quick_scan v2）

固化自 2026-09-23 第 1 轮全树穿透扫描。把当轮"六步 + 六条硬规则"炼成一件能反复跑的速扫器。

六条硬规则 ↔ 实现：
  R1 先切面再扫 —— **显式白名单**切出生产面，其余按平面归类（不再用"非垃圾即生产"）
  R2 扫描器产物落树外（默认 %TEMP%\\gbt-quickscan）
  R3 收敛判据 —— 与 baseline 对账，输出 新增/已修/未变；退出码即门
  R4 声明必须机检 —— 技能根/依赖/计划任务/口径一律现扫，不手抄
  R5 异质尺交叉 —— 索引尺(git grep --cached) / 工作区尺(scandir) / 首方模块索引 三把并用
  R6 输出必带"没扫到什么"

v2 相对 v1 的修正（v1 自查抓到的 5 处不合格）：
  ① 生产面改显式白名单 —— v1 把 `.openclaw/tmp` 的脚本算成生产代码，于是
     `PySide6`/`live2d`/`engineering_details` 被误判成"活代码缺依赖"
  ② 计划任务误报解释器路径 —— `C:\\Python312\\python.exe` 不是项目目标，现已排除
  ③ requirements 的 BOM 注释行混进结论 —— 现按 utf-8-sig 读
  ④ 缺包没做首方判别 —— 现先查"仓内是否已有同名模块"，有则不算缺
  ⑤ 索引密钥把 `.scratch` 里的 node_modules 也算进来 —— 现分"全部/高信号"两栏
  另：跳过 `.git` 子树改用 git 自报体量；walk 改 scandir 免二次 stat；兄弟工作区探测加预算

只读铁律：不写被扫目录、不改既有文件、不需要任何授权作用域。
用法:
  py -3.14 tools/codex-scripts/quick_scan.py
  py -3.14 tools/codex-scripts/quick_scan.py --with-gates
  py -3.14 tools/codex-scripts/quick_scan.py --accept
退出码: 0 只有 P2/无故障 · 1 有 P0 · 2 有 P1 · 3 扫描器自身出错
"""
import argparse
import ast
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict

SCHEMA = 2
HERE = pathlib.Path(__file__).resolve()
ROOT = HERE.parents[2]
# 仓根按 __file__ 定位 ⇒ **与 cwd 无关**，从任何目录都能跑（见 SKILL §2 的 cwd 契约）。

# 控制台口径（2026-09-23 实测踩到）：GBK 控制台下直接 print 中文会**崩**
#   `UnicodeEncodeError: 'gbk' codec can't encode ...`；只 reconfigure stdout 不够，
#   还得把**控制台代码页**也切到 65001，否则中文以 UTF-8 写出、控制台按 GBK 解 ⇒ 乱码。
#   （同一条教训在 tools/codex-scripts/five-dim.py 第 23–30 行已记过一次，本件沿用。）
if os.name == "nt":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── R1 平面划分：显式白名单（不再是"非垃圾即生产"）──────────────────
PROD_TOPS = {
    "gbt_allinone", "tools", "plugins", "skills", "state", "memory", "config",
    "deploy", "projects", "delivery", "holo_pet", "holo_pet_w3", "potato_pet",
    "assets", "generated-images", "outputs", "render", "archive",
    "design-assets-index", "审美相关skill", "brain", "caps",
    "infinite-canvas-output", "latest_logs", "video-out", "data", ".dsh",
}
PLANE_BY_TOP = {
    ".scratch": "P3", ".trash": "P3", ".backups": "P3",
    "vendor": "P4", "_upstream": "P4", ".shadow-repo": "P4",
    ".openclaw": "P6", ".agents": "P6", ".cluster": "P6", ".autoclaw": "P6",
    ".opencode": "P6", ".claude": "P6", ".gbt": "P6", ".etiology": "P6",
    ".video": "P6", ".tripo": "P6", ".digihuman": "P6",
    ".openclaw-attachments": "P6", "agent-gvmz-gbtv8": "P6",
}
PLANE_NAME = {"P1": "生产代码面", "P2": "运行数据面", "P3": "作业临时面",
              "P4": "第三方参考面", "P5": "装机系统面", "P6": "机内状态面"}
SKIP_TOPS = {".git"}                      # 由 git 自报体量，不做逐文件 stat

TEXT_EXT = {".py", ".pyi", ".md", ".txt", ".json", ".jsonl", ".yaml", ".yml",
            ".toml", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".vue", ".css",
            ".html", ".htm", ".sh", ".ps1", ".bat", ".cmd", ".ini", ".cfg",
            ".env", ".sql", ".csv", ".xml"}
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".glb", ".gltf",
              ".mp3", ".mp4", ".wav", ".pdf", ".zip", ".gz", ".7z", ".exe",
              ".dll", ".pyd", ".so", ".bin", ".pak", ".cvr", ".hyb", ".woff",
              ".woff2", ".ttf", ".otf", ".pyc", ".map", ".wasm", ".db"}
MAX_TEXT = 1_500_000
BIG_FILE = 5 * 1024 * 1024
SIBLING_BUDGET = 1500                    # 兄弟工作区只数到这么多就停，防拖慢

# 通用残骸名（**不含 `_*.py`** —— `_utils.py`/`_base.py` 是合法的私有模块命名）
RESIDUE_RE = re.compile(
    r"(\.tmp$)|(\.temp$)|(\.bak$)|(\.old$)|(\.orig$)|(\.rej$)"
    r"|(~$)|(\.swp$)|(^~\$)|(\.crdownload$)|(\.part$)|(^\.#)", re.I)
# 只在**作业临时面**才算残骸的额外一条：家规点名的 `_*.py` 临场脚本
RESIDUE_P3_RE = re.compile(r"(^_\w+\.py$)|(\.tmp$)|(\.temp$)|(\.bak$)|(\.old$)"
                           r"|(\.orig$)|(\.rej$)|(~$)|(\.swp$)|(^~\$)", re.I)
GIT_SECRET_ERE = ("sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}"
                  "|gh[pousr]_[A-Za-z0-9]{30,}|AIza[0-9A-Za-z_-]{35}"
                  "|-----BEGIN [A-Z ]*PRIVATE KEY-----|xox[baprs]-[A-Za-z0-9-]{10,}")
TEXT_PATHSPEC = ["*.json", "*.jsonl", "*.py", "*.pyi", "*.md", "*.txt", "*.yaml",
                 "*.yml", "*.toml", "*.js", "*.mjs", "*.cjs", "*.ts", "*.tsx",
                 "*.env", "*.cfg", "*.ini", "*.sh", "*.ps1", "*.bat", "*.cmd",
                 "*.vue", "*.html", "*.css", "*.xml", "*.csv", "*.sql", "*.lock"]
INTERP_DIRS = re.compile(r"(program files|windows|python3|nodejs|\\appdata\\local\\programs)", re.I)
PROJECT_EXT = (".py", ".ps1", ".bat", ".cmd", ".js", ".mjs", ".cjs", ".json", ".yml", ".yaml")

FAULTS = []

# ── 兄弟模块：安全面(S) 与 进化层（缺失时**如实报缺**，不静默降级）────────
_SEC_ERR = _EVO_ERR = None
try:
    sys.path.insert(0, str(HERE.parent))
    import quickscan_security as SEC                      # noqa: E402
except Exception as _e:                                   # noqa: BLE001
    SEC, _SEC_ERR = None, "%s: %s" % (type(_e).__name__, str(_e)[:120])
try:
    import quickscan_evolve as EVO                         # noqa: E402
except Exception as _e:                                   # noqa: BLE001
    EVO, _EVO_ERR = None, "%s: %s" % (type(_e).__name__, str(_e)[:120])


def add(sev, plane, code, what, evidence, fix_hint):
    FAULTS.append({"sev": sev, "plane": plane, "code": code, "what": what,
                   "evidence": str(evidence)[:400], "fix": fix_hint})


def run(cmd, cwd=ROOT, timeout=180):
    try:
        p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    except Exception as e:
        return -1, "", "%s: %s" % (type(e).__name__, e)


def masked(s):
    s = str(s)
    return (s[:4] + "****") if len(s) > 4 else "****"


def _rel(p) -> str:
    """安全相对路径：**仓外**（例如 --selftest 的夹具树）退回绝对路径，不抛异常。"""
    try:
        return str(pathlib.Path(p).relative_to(ROOT))
    except Exception:
        return str(p)


def longest_ascending_run(tok):
    """最长单调递增/递减的连续字母数字串长度。

    真密钥是随机串（不会有 abcdefghijklmnop 这种长跑）；
    占位符/夹具基本都是顺序字母表 ⇒ 用它把两者分开，比"路径里有没有 test"可靠得多
    （实测：真密钥恰恰躺在 `.scratch/_m4_autoclaw_backup_*/openclaw.json` 里，
    按路径剔噪会把真密钥一起剔掉 —— 这条教训来自 2026-09-23 第 1 轮）。
    """
    best = cur = 1
    for i in range(1, len(tok)):
        a, b = ord(tok[i - 1]), ord(tok[i])
        if b - a == 1 or a - b == 1:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best


def classify_token(rule, tok, body_after):
    """credential_like / fixture_like —— 判据写出来，不装神"""
    if rule == "private_key":
        # 真私钥后面必有长 base64 体；夹具常常只有 16 字符就 END
        body = re.sub(r"[^A-Za-z0-9+/=]", "", body_after[:600])
        return "credential_like" if len(body) >= 200 else "fixture_like"
    if rule == "jwt":
        return "credential_like" if len(tok) >= 80 else "fixture_like"
    if len(tok) < 30:
        return "fixture_like"
    if longest_ascending_run(tok) >= 6:
        return "fixture_like"
    return "credential_like"


def classify(rel_parts):
    """返回 (平面, 是否生产面)。显式表驱动，不猜。"""
    if not rel_parts:
        return "P1", True
    if ".git" in rel_parts:
        return "skip", False          # 顶层与嵌套 .git 都跳过（_upstream 里也有 .git）
    top = rel_parts[0]
    if top in SKIP_TOPS:
        return "skip", False
    if "node_modules" in rel_parts:
        return "P4", False
    if top == "gbt_allinone":
        if "store" in rel_parts:
            return "P2", False
        if ".pylibs" in rel_parts or "__pycache__" in rel_parts:
            return "P4", False
        return "P1", True
    if top == ".dsh":
        return ("P1", True) if len(rel_parts) > 1 and rel_parts[1] == "skills" else ("P6", False)
    if top in PROD_TOPS:
        if "__pycache__" in rel_parts or ".pylibs" in rel_parts:
            return ("P4", False)
        return "P1", True
    if top in PLANE_BY_TOP:
        return PLANE_BY_TOP[top], False
    return "P6", False


DUP_EXACT_FLOOR = 64 * 1024        # 只对 ≥64KB 的同体积组做哈希（实测这档就覆盖 308.9MB）
DUP_EXACT_CAP = 400               # 单轮最多哈希多少个文件；**截断必须回报**，不许悄悄截


def scan_dup_exact(tree, floor=DUP_EXACT_FLOOR, cap=DUP_EXACT_CAP):
    """精确重复内容：**先按体积分组（免哈希，零 I/O）**，再对同体积组做 sha256 确认。

    🔴 为什么必须先分体积：体积不同 ⇒ 内容必不同。体积分组是**必要前置**，且零成本。
    🔴 为什么只做**生产面**：目录里那条写的是「全树 10,908 组 / 673.6 MB」，但全树的大头是
       第三方树与残骸（`_upstream/` = P4 · `.scratch/` = P3）—— 在那上面去重**没有意义**。
       实测生产面：397 组同体积 / 候选 578.5 MB；≥64KB 档 26 组 / **最多可回收 308.9 MB**。
    🔴 `cap` 截断必须回报（`capped` 字段）：否则"只比了一部分"会被读成"本轮已全比"。
    """
    by_size = defaultdict(list)
    for p, s in tree["prod"]:
        if s >= floor:
            by_size[s].append(p)
    pairs = [(s, p) for s, v in by_size.items() if len(v) > 1 for p in v]
    pairs.sort(key=lambda sp: -sp[0])          # 大件优先：先把最亏的比出来
    capped = len(pairs) > cap
    pairs = pairs[:cap]

    def _rel(x):
        try:
            return str(x.relative_to(ROOT))
        except ValueError:
            return str(x)                      # 夹具树在仓外（自检用）⇒ 退回绝对路径

    dig = defaultdict(list)
    for _s, p in pairs:
        h = hashlib.sha256()
        try:
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
        except OSError:
            continue
        dig[h.hexdigest()].append((_s, p))
    groups = []
    for d, v in dig.items():
        if len(v) < 2:
            continue
        groups.append({"sha256": d[:16], "n": len(v), "MB": round(v[0][0] / 1048576, 2),
                       "waste_mb": round(v[0][0] * (len(v) - 1) / 1048576, 2),
                       "paths": [_rel(x) for _ss, x in v[:4]]})
    groups.sort(key=lambda g: -g["waste_mb"])
    return {"floor_kb": floor // 1024, "cap": cap, "capped": capped,
            "cand_n": len(pairs), "groups_n": len(groups),
            "waste_mb": round(sum(g["waste_mb"] for g in groups), 1),
            "groups": groups[:20]}


_MTIME_SLACK = 120.0        # 时间戳判据容忍的时钟抖动（秒）；见 classify_mtime


def classify_mtime(st, now=None, plane=""):
    """把一个 stat 结果分成「时间戳三档」。返回 None 表示正常。

    🔴 为什么抽成**模块级函数**：这样 `--selftest` 能直接测**真身**。
       自检里复制一份判据去测，测的是那个副本，不是产品 —— 那正是本会话反复踩的坑。

    三档与它们的**天生噪声源**（都是实测出来的）：
      · future       mtime 落在将来（> now + 2 分钟）—— 只可能来自时钟跳变/坏工具
      · epoch0       mtime 落在 2000 年之前 —— 但 **ZIP 的时间戳下界是 1980-01-01**，
                     工具表达不了更早的时间就写这个哨兵值 ⇒ 必须把 `1980-01-01` 排除，
                     否则 `node_modules/electron/dist/*.pak` 那 282 个全会变成假阳性
                     （第一版就是这么错的，被紧接着的读数当场抓住）。
      · before_ctime mtime 早于创建时间 —— **Windows 上 ctime 是创建时间**，
                     解压/复制保留 mtime 时会大量出现 ⇒ 天生噪声大，报告时必须分平面。
    """
    now = time.time() if now is None else now
    out = {"future": False, "ahead_min": 0.0, "epoch0": False, "sentinel1980": False,
           "before_ctime": False, "behind_days": 0.0}
    if st is None:
        return None
    if st.st_mtime > now + _MTIME_SLACK:
        out["future"] = True
        out["ahead_min"] = round((st.st_mtime - now) / 60.0, 1)
    if 0 < st.st_mtime < 946684800:                     # 2000-01-01 之前
        if time.strftime("%Y-%m-%d", time.localtime(st.st_mtime)) == "1980-01-01":
            out["sentinel1980"] = True                  # ZIP 下界哨兵：已知、不是病
        else:
            out["epoch0"] = True
    if st.st_mtime < st.st_ctime - _MTIME_SLACK:
        out["before_ctime"] = True
        out["behind_days"] = round((st.st_ctime - st.st_mtime) / 86400.0, 1)
    return out if (out["future"] or out["epoch0"] or out["before_ctime"]
                   or out["sentinel1980"]) else None


def walk_tree():
    """scandir 递归（免二次 stat），平面归类 + 库存读数"""
    prod, junk = [], defaultdict(list)
    empty_files, empty_dirs, residue, big = [], [], [], []
    name_size = defaultdict(list)
    total = total_bytes = 0
    nm_n = 0
    # ── MTIME_ANOMALY（2026-09-24 第 96 轮新增，来自目录的『待进化』清单）────────
 # 为什么接在这里：本函数**每个文件已经 stat 过一次**（下面 `st = e.stat(...)`）
    #    ⇒ mtime/ctime 是**顺手拿到**的：不多走一遍树、不多发一次系统调用。
    #    （另一条路是单开一个 scan 函数再 walk 一次 —— 那是白加 6~13 秒，不做。）
    # 判定逻辑在模块级 `classify_mtime()` 里（自检能测真身）；这里只收集 + 分平面。
    _now_ts = time.time()
    mt_future, mt_before_ctime, mt_epoch = [], [], []
    mt_sentinel_n = 0            # 被排除的 ZIP 下界哨兵数（**如实记，不藏着**）
    stack = [ROOT]
    while stack:
        d = stack.pop()
        try:
            it = list(os.scandir(d))
        except OSError:
            continue
        dparts = d.relative_to(ROOT).parts
        plane, is_prod = classify(dparts)
        if plane == "skip":
            continue
        files = dirs = 0
        for e in it:
            try:
                is_dir = e.is_dir(follow_symlinks=False)
                if is_dir and e.name == "node_modules" and "node_modules" not in dparts:
                    nm_n += 1          # 只数**顶层安装**，不数嵌套的 node_modules
                if is_dir:
                    sub = dparts + (e.name,)
                    if classify(sub)[0] == "skip":
                        continue
                    stack.append(pathlib.Path(e.path))
                    dirs += 1
                    continue
                if not e.is_file(follow_symlinks=False):
                    continue
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            files += 1
            size = st.st_size
            total += 1
            total_bytes += size
            rel = str(pathlib.Path(e.path).relative_to(ROOT))
            # —— 时间戳异常：判定走模块级 `classify_mtime`（自检测的就是它，不是副本）——
            _mt = classify_mtime(st, _now_ts, plane)
            if _mt:
                if _mt["sentinel1980"]:
                    mt_sentinel_n += 1          # 已知的 ZIP 下界哨兵：计数但不报病
                if _mt["future"]:
                    mt_future.append({"path": rel, "plane": plane, "ahead_min": _mt["ahead_min"]})
                if _mt["epoch0"]:
                    mt_epoch.append({"path": rel, "plane": plane,
                                     "mtime": time.strftime("%Y-%m-%d", time.localtime(st.st_mtime))})
                if _mt["before_ctime"]:
                    mt_before_ctime.append({"path": rel, "plane": plane,
                                            "behind_days": _mt["behind_days"]})
            if plane in ("P2", "P4"):
                # 平面② 是运行时**数据**（浏览器 profile 里的 .tmp 是它自己的缓存）；
                # 平面④ 是别人家的树 —— 两面的命名都不算本仓卫生问题，只计体积
                pass
            else:
                if size == 0 and e.name != "__init__.py":
                    empty_files.append(rel)     # __init__.py 空是约定；.gitkeep 空也是约定
                _rx = RESIDUE_P3_RE if plane == "P3" else RESIDUE_RE
                if e.name != "__init__.py" and _rx.search(e.name):
                    residue.append({"path": rel, "size": size})
            if size >= BIG_FILE:
                big.append({"path": rel, "MB": round(size / 1048576, 2)})
                name_size[(e.name, size)].append(rel)
            (prod if is_prod else junk[plane]).append((pathlib.Path(e.path), size))
        if files == 0 and dirs == 0 and dparts and plane != "P4":
            empty_dirs.append(str(d.relative_to(ROOT)))
    return {"prod": prod, "junk": dict(junk), "total": total, "bytes": total_bytes,
            "empty_files": empty_files, "empty_dirs": empty_dirs,
            "residue": residue, "big": big, "name_size": name_size,
            "mtime_anomaly": {"future": mt_future, "before_ctime": mt_before_ctime,
                              "epoch0": mt_epoch, "sentinel1980_n": mt_sentinel_n},
            "node_modules_n": nm_n}


def scan_plane1_prod(prod):
    """平面① 生产代码面：能不能跑（语法 / 绝对导入 / 相对导入 / 无效转义 / 卫生读数）"""
    import warnings as _w
    fp_mods, fp_dirs = set(), set()
    for p, _ in prod:
        if p.suffix == ".py":
            fp_mods.add(p.stem)
            fp_dirs.add(p.parent.name)
    py_n = py_ok = bare = todos = checked = 0
    syn_err, unresolved, _, escapes = [], [], [], []
    bom, nonutf8, mojibake, mixed_eol, nul = [], [], [], [], []
    json_bad, yaml_bad, toml_bad = [], [], []
    MOJI = re.compile(r"(â€|Ã[\x80-\xbf]|ï¿½|锟斤拷|\ufffd)")
 # 2026-09-24 修一条**引用型/自指型假红**（与 TEST_CALIBER_HIJACK 同一类：判据分不清"病"和"讲病的教材"）。
    #    实测：本仓 21 条 MOJIBAKE 命中**全部**属于下面两类，没有一条是真乱码 ——
    #      · `tools/codex-scripts/quick_scan.py` L291：**它自己的乱码正则字面量**（自指）
    #      · `skills/gbt-quickscan/SKILL.md` L216 引用实例 `GBTС����V8`（讲控制台代码页那一课）
    #      · `skills/gbt-finance/SKILL.md` 引用 `����`（讲 PowerShell 管道解码那一课）
    #      · `skills/gbt-creation/SKILL.md` 引用 `ģ��1 �籾����` · `skills/gbt-dangerous/SKILL.md` 引用 `����ǽ�ƹ�`
    #    ⇒ 修法两条，都不削弱"真乱码要报"：
    #      ① 匹配前**去掉行内代码 `…` 与围栏块 ```…```**（教材里的例子都写在代码span里）；
    #      ② **跳过定义这份模式表的本文件自己**（自指没法靠 ① 解决）。
    #    ⇒ 剩下的命中才是"没被引号包起来的裸乱码"，那才是真信号。
 # 这一行我第一版写成 `str(Path(__file__).resolve())` —— 而本文件**没有导入 `Path`**
    #    （用的是 `import pathlib` + L43 已有的 `HERE`）⇒ `NameError` ⇒ 扫描器 exit 3、报告根本没写，
    #    而我当时用 `Select-String '^故障'` 把 traceback 过滤掉了，于是**拿旧报告当新读数**。
    #    ⇒ 教训：**过滤器会吞掉报错**；跑完要看 exit 码，别只看自己关心的那行。
    _SELF = {str(HERE)}
    _FENCE = re.compile(r"```.*?```", re.S)
    _INLINE = re.compile(r"`[^`\n]*`")

    def _moji_hits(t: str) -> int:
        return len(MOJI.findall(_INLINE.sub("", _FENCE.sub("", t))))
    for p, size in prod:
        ext = p.suffix.lower()
        if ext not in TEXT_EXT or ext in BINARY_EXT or size > MAX_TEXT:
            continue
        checked += 1
        try:
            raw = p.read_bytes()
        except OSError:
            continue
        rel = _rel(p)
        if raw.startswith(b"\xef\xbb\xbf"):
            bom.append(rel)
        if b"\x00" in raw:
            nul.append(rel)
            continue
        try:
            t = raw.decode("utf-8")
        except UnicodeDecodeError:
            nonutf8.append(rel)
            t = raw.decode("utf-8", "replace")
        if _moji_hits(t) and str(p.resolve()) not in _SELF:
            mojibake.append(rel)
        crlf, lf = t.count("\r\n"), t.count("\n")
        if crlf and (lf - crlf):
            mixed_eol.append(rel)
        todos += len(re.findall(r"(?i)\b(TODO|FIXME|XXX|HACK)\b", t))
        if ext == ".json" and size < 600_000:
            try:
                json.loads(t.lstrip("\ufeff"))
            except Exception as e:
                if not p.name.startswith("tsconfig"):
                    json_bad.append({"path": rel, "msg": str(e)[:80]})
        elif ext in (".yaml", ".yml") and size < 600_000:
            try:
                import yaml
                yaml.safe_load(t)
            except ImportError:
                pass
            except Exception as e:
                yaml_bad.append({"path": rel, "msg": str(e)[:80]})
        elif ext == ".toml" and size < 600_000:
            try:
                import tomllib
                tomllib.loads(t)
            except Exception as e:
                toml_bad.append({"path": rel, "msg": str(e)[:80]})
        if ext != ".py":
            continue
        py_n += 1
        with _w.catch_warnings(record=True) as cw:
            _w.simplefilter("always")
            try:
                tree = ast.parse(t.lstrip("\ufeff"))
                py_ok += 1
            except SyntaxError as e:
                syn_err.append({"path": rel, "line": e.lineno, "msg": str(e.msg)[:90]})
                continue
            for w in cw:
                if issubclass(w.category, SyntaxWarning) and len(escapes) < 40:
                    escapes.append("%s:%s %s" % (rel, getattr(w, "lineno", 0),
                                                 str(w.message)[:70]))
        for n in ast.walk(tree):
            if isinstance(n, ast.ExceptHandler) and n.type is None:
                bare += 1
            if isinstance(n, ast.Import):
                for a in n.names:
                    unresolved.append((rel, a.name, 0))
            elif isinstance(n, ast.ImportFrom):
                if n.module or n.level:
                    unresolved.append((rel, n.module or "", n.level))
    return {"text_checked": checked, "py_n": py_n, "py_ok": py_ok,
            "syntax_errors": syn_err, "bare_except": bare, "todo_markers": todos,
            "invalid_escapes": escapes,
            "bom": bom, "non_utf8": nonutf8, "mojibake": mojibake,
            "mixed_eol": mixed_eol, "nul_like": nul,
            "json_bad": json_bad, "yaml_bad": yaml_bad, "toml_bad": toml_bad,
            "_imports": unresolved, "_fp_mods": fp_mods, "_fp_dirs": fp_dirs}


def check_deps(imports, fp_mods, fp_dirs):
    """R4+R5：依赖声明 vs 实际导入；相对导入断链；先做**首方判别**再判第三方缺失"""
    import importlib.util as u
    declared = set()
    req = ROOT / "requirements.txt"
    if req.exists():
        for ln in req.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                declared.add(re.split(r"[<>=!\[;,\s]", ln)[0].strip())
    declared.discard("")
    # 家规第 10 条：wallet / ledger / bridge 这类资金模块**本就该在框架里缺席**
    # （已移出家 Workspace）。它们的"断链"是设计，不是故障 —— 别把它报成病。
    KNOWN_ABSENT = {"bridge", "wallet", "ledger", "wallet_adapter", "money_route",
                    "export_statement", "notify", "loop", "gbt_wallet"}
    missing, third, first_party_import = Counter(), Counter(), Counter()
    absent_abs = Counter()          # 绝对导入里"家规本该缺席"的（设计，不是故障）
    rel_broken, rel_absent = [], []

 # 2026-09-24 修两处**拿名字硬比**造成的假红（都是实测出来的）：
    #   ① **模块名 ≠ 发行名**：声明 `pillow` 清不掉 `PIL`；声明 `opencv-python`
    #      反而会被判"装不上"（发行名不是模块，`find_spec('opencv-python')` 必为 None）。
    #      ⇒ 修法**不手写别名表**（手写会过期），用解释器自己的权威映射
    #      `importlib.metadata.packages_distributions()`（模块 → 提供它的发行）。
    #   ② `declared_but_unimportable` 同理：声明的是发行名时，要问"**这个发行装了没**"，
    #      而不是"这个名字能不能 import"。
    try:
        import importlib.metadata as _md
        _PD = _md.packages_distributions()
    except Exception:                                                      # noqa: BLE001
        _md, _PD = None, {}
    _declared_l = {d.lower() for d in declared}

    # ③ 补一层映射：`packages_distributions()` 对**部分包是查不到的**
    #    （实测 `win32con` 没有任何发行声明它归谁 —— 而它明明由已声明的 `pywin32` 提供）。
    #    ⇒ 对**已声明的发行**再问一遍它自己的 `top_level.txt`（很多包装了这个文件，
    #      列明"我提供哪些导入名"）。仍然不手写别名表。
    _provides = {}                       # 发行名(小写) -> {它提供的导入名}
    if _md is not None:
        for d in declared:
            for nm in (d, d.lower(), d.lower().replace("_", "-")):
                try:
                    dist = _md.distribution(nm)
                except (_md.PackageNotFoundError, ValueError, OSError):
                    continue
                try:
                    txt = dist.read_text("top_level.txt") or ""
                except Exception:                                          # noqa: BLE001
                    txt = ""
                _provides[d.lower()] = {x.strip().lower() for x in txt.splitlines() if x.strip()}
                break
    _covered_by_provides = set()
    for mods in _provides.values():
        _covered_by_provides |= mods

    def _declared_covers(mod):
        """这个导入名，算不算"已经声明过"（认模块名、发行名、元数据对应关系、top_level、**文件归属**）。"""
        if mod in declared or mod.lower() in _declared_l:
            return True
        if mod.lower() in _covered_by_provides:
            return True
        if any(str(d).lower() in _declared_l for d in (_PD.get(mod) or [])):
            return True
        # ④ 最后一道：**按文件归属证**。pywin32 这类包的元数据里没有 `win32con`
        #    （它的 top_level / packages_distributions 都不列它），
        #    但 `win32con.py` 的**文件**就在 pywin32 的 RECORD 里 ⇒ 用文件身份来判，
        #    而不是靠"猜别名"。只对**映射不到的**那一两个模块走这条路，开销可忽略。
        if _md is None:
            return False
        spec = u.find_spec(mod)
        if spec is None or not spec.origin:
            return False
        try:
            origin = pathlib.Path(spec.origin).resolve()
        except (OSError, ValueError):
            return False

        def _norm(p):
            """把 RECORD 里的路径规范化成"可比的模块路径"。
            🔴 为什么必须这么比（实测 pywin32 311）：它的 RECORD 里**只列了
            `win32/lib/__pycache__/win32con.cpython-314.pyc`，没列源文件 `win32/lib/win32con.py`**
            （只装预编译）⇒ 精确比路径必然对不上，于是明明由一个**已声明**的发行提供的模块
            被误报成"未声明"。⇒ 去掉 __pycache__、把 .cpython-NNN.pyc 折回 .py 再比。"""
            s = str(p).replace("\\", "/").replace("__pycache__/", "")
            return re.sub(r"\.cpython-\d+\.pyc$", ".py", s)

        origin_rel = None
        for d in declared:
            for nm in (d, d.lower(), d.lower().replace("_", "-")):
                try:
                    dist = _md.distribution(nm)
                except (_md.PackageNotFoundError, ValueError, OSError):
                    continue
                try:
                    root = pathlib.Path(dist.locate_file("")).resolve()
                    origin_rel = _norm(origin.relative_to(root))
                except (OSError, ValueError):
                    origin_rel = None
                if origin_rel:
                    for f in (dist.files or []):
 # 必须「全等 或 带 `/` 后缀」两条都留：只留后缀会把
                        #    `win32/lib/win32con.py` 这种**全等**情形判否（两端都没有
                        #    前导 `/` ⇒ `endswith("/" + x)` 永远不成立）—— 这是我第一版
                        #    「收紧」时自己造出来的新假阳性，被紧接着的读数当场抓住。
                        nf = _norm(f)
                        if nf == origin_rel or nf.endswith("/" + origin_rel):
                            return True
                break
        return False

    def _declared_usable(name):
        """这个声明名在本机**可用**吗（模块名走 import；发行名走 metadata 的版本查询）。"""
        if u.find_spec(name) is not None:
            return True
        if _md is None:
            return False
        for cand in (name, name.lower(), name.lower().replace("_", "-")):
            try:
                _md.version(cand)
                return True
            except (_md.PackageNotFoundError, ValueError, OSError):
                continue
        return False
    for f, mod, level in imports:
        if level:
            base = (ROOT / f).parent
            for _ in range(level - 1):
                base = base.parent
            first = mod.split(".")[0] if mod else ""
            if first and not ((base / (first + ".py")).exists()
                              or (base / first / "__init__.py").exists()):
                rec = {"file": f, "import": "." * level + mod}
                (rel_absent if first in KNOWN_ABSENT else rel_broken).append(rec)
            continue
        top = mod.split(".")[0]
        if not top or top in sys.stdlib_module_names:
            continue
        if top in fp_mods or top in fp_dirs or (ROOT / (top + ".py")).exists() \
                or (ROOT / top).is_dir() or (ROOT / "gbt_allinone" / (top + ".py")).exists() \
                or (ROOT / "gbt_allinone" / top).is_dir() \
                or (ROOT / "gbt_allinone" / "tentacle" / (top + ".py")).exists():
            first_party_import[top] += 1        # 同包兄弟导入 / 仓内模块 —— 不是依赖问题
            continue
        third[top] += 1
        if u.find_spec(top) is None:
 # 家规第 10 条本来说"wallet/ledger/bridge 这类资金模块本该在框架里缺席，
            #    别把它报成病" —— 但**旧版只把这个白名单用在相对导入上**，
            #    绝对导入的 `import gbt_wallet`（smoke_test.py 两处）照样被算成"缺依赖"。
            #    ⇒ 这里把同一条家规补到绝对导入上，并且**不是删掉、是单列**（照实可见）。
            if top in KNOWN_ABSENT:
                absent_abs[top] += 1
            else:
                missing[top] += 1
    return {"declared": sorted(declared),
            "missing_third_party": dict(missing),
            "absent_by_design_abs": dict(absent_abs),
            "third_party_used": dict(third),
            "first_party_shallow_imports": dict(first_party_import),
            "relative_broken": rel_broken[:40],
            "relative_broken_n": len(rel_broken),
            "relative_absent_by_design": rel_absent[:20],
            "relative_absent_by_design_n": len(rel_absent),
 # 认模块名 / 发行名 / 元数据对应关系 / top_level（见上面 _declared_covers 的说明）
            # 并且**只报"本机有、但没写下来"的**（那才是"重装即成谜"）。
            # 本机根本没有的那些已经由 DEP_MISSING 逐条报了 ⇒ 再报一遍是**同一个事实报两遍**，
            # 而且会**惩罚诚实的做法**（把装不上的写进声明 = 亲手制造 DEP_DECLARED_UNUSABLE）。
            "used_but_not_declared": sorted(k for k in third
                                            if not _declared_covers(k)
                                            and u.find_spec(k) is not None),
            "declared_but_unimportable": sorted(k for k in declared if not _declared_usable(k))}


def caliber_hijack(tc):
    """仓外 pytest 配置是否**真能**劫持 rootdir？→ (fire: bool, hijack_list: list)

    🔴 为什么抽成模块级函数（第 106 轮）：这条判据**本会话被我修过一次**
       （`if hij:` → `if hij and not repo_local_config`），而**修完之后两个方向都没验过** ——
       `--discover` 把它列进「从未响过且没被自检验过」就是证据。抽出来才测得了真身。

    🔴 判据的实质（原注释里已写、有实测支撑）：pytest 的 rootdir 是
       **从 cwd 向上遇到的第一个配置就停** ⇒ 只有「**上级有、仓根没有**」时，
       那条上级配置才真能劫持。仓根一旦有自己的配置（本仓是 `pytest.ini`），
       上级的就被挡住 ⇒ **不许再报**（旧版 `if hij:` 就是这个假红：按它自己给的修法
       修完，它照样报 —— 实测 collection 错误 251→0 而它仍响）。
    """
    hij = list(tc.get("parent_config_hijack") or [])
    return (bool(hij) and not tc.get("repo_local_config")), hij


def scan_test_caliber(deep=False):
    """T 面 · 测试口径（2026-09-23 第 1 轮最大发现：仓内无自证配置，结论由仓外决定）"""
    out = {"repo_local_config": [], "parent_config_hijack": [], "collect": {}}
    for name in ("pytest.ini", "conftest.py", "pyproject.toml", "setup.cfg", "tox.ini"):
        if (ROOT / name).exists():
            out["repo_local_config"].append(name)
    conftest = ROOT / "conftest.py"
    out["conftest_sets_store"] = bool(
        conftest.exists() and "GBT_STORE_DIR" in conftest.read_text(
            encoding="utf-8", errors="replace"))
    # 上级目录里有没有会劫持 rootdir 的配置（跑到盘根为止）
    p = ROOT.parent
    for _ in range(6):
        for name in ("pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini"):
            f = p / name
            if f.exists():
                out["parent_config_hijack"].append(str(f))
        if p.parent == p:
            break
        p = p.parent
    if deep:
        tests = ROOT / "gbt_allinone" / "tests"
        if tests.is_dir():
            for label, env_extra in (("no_isolated_store", {}),
                                     ("with_isolated_store",
                                      {"GBT_STORE_DIR": str(pathlib.Path(
                                          os.environ.get("TEMP", "/tmp")) / "gbt_qs_store")})):
                env = dict(os.environ, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1",
                           **env_extra)
                try:
                    r = subprocess.run(
                        [sys.executable, "-m", "pytest", str(tests), "--collect-only",
                         "-q", "-p", "no:cacheprovider"],
                        cwd=str(ROOT), capture_output=True, timeout=180, env=env)
                    txt = r.stdout.decode("utf-8", "replace")
                    # 2026-10-16 判据翻正（留痕 · 不静默）：
                    #   翻了哪条口径：T 面 collected 的解析正则。
                    #   为什么翻：原正则只认 pytest <= 7 的措辞「collected N items」；
                    #     本机 pytest >= 8 的 -q 收尾语是「N tests collected in Xs」
                    #     ⇒ 正则**恒不匹配** ⇒ collected 恒记 0 ⇒ T 面**恒报**
                    #     TEST_COLLECT_ZERO（假红，不是测试坏了）。
                    #   实证（2026-10-16）：同一条命令真跑输出
                    #     「2992 tests collected in 5.03s」；旧正则命中=False、
                    #     新正则命中=True。
                    #   原期望：两种措辞都要认。负对照口径不变 —— 真 0 条仍报 0。
                    # 两个分支的计数都在 group(1)，故下面取用口径不用改。
                    ncol = re.search(r"collected (\d+) items?", txt) or re.search(
                        r"(\d+) tests? collected", txt)
                    nerr = re.search(r"(\d+) errors?", txt)
                    out["collect"][label] = {
                        "rc": r.returncode,
                        "collected": int(ncol.group(1)) if ncol else 0,
                        "errors": int(nerr.group(1)) if nerr else 0,
                    }
                except subprocess.TimeoutExpired:
                    out["collect"][label] = {"rc": "timeout>180s"}
                except Exception as e:
                    out["collect"][label] = {"rc": type(e).__name__}
    return out


def scan_doclinks_prod(prod):
    """L4 · 生产面 md 相对链接断链"""
    total = missed = 0
    samples = []
    for p, size in prod:
        if p.suffix != ".md" or size > MAX_TEXT:
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in re.finditer(r"\[[^\]]*\]\(([^)\s]+)\)", t):
            u = m.group(1)
            if u.startswith(("http", "//", "data:", "#", "mailto:", "javascript:")):
                continue
            u2 = u.split("?")[0].split("#")[0]
            if not u2:
                continue
            total += 1
            if not (p.parent / u2).exists() and not (ROOT / u2).exists():
                missed += 1
                if len(samples) < 20:
                    samples.append("%s -> %s" % (_rel(p), u2))
    return {"links_total": total, "broken_n": missed, "broken": samples}


def scan_shadow():
    """W 面 · .shadow-repo 与真身是否漂移（第二真相）"""
    sh = ROOT / ".shadow-repo" / "gbt_allinone"
    real = ROOT / "gbt_allinone"
    if not sh.is_dir() or not real.is_dir():
        return {"present": False}
    same = diff = missing = 0
    diffs = []
    n = 0
    for dp, dn, fn in os.walk(sh):
        dn[:] = [d for d in dn if d not in ("__pycache__", ".pylibs", "store", "mirror_space")]
        for f in fn:
            sp = pathlib.Path(dp) / f
            try:
                relp = sp.relative_to(sh)
            except ValueError:
                continue
            rp = real / relp
            if not rp.exists():
                missing += 1
                continue
            n += 1
            if n > 1200:
                break
            try:
                a = hashlib.sha256(sp.read_bytes()).hexdigest()
                b = hashlib.sha256(rp.read_bytes()).hexdigest()
            except OSError:
                continue
            if a == b:
                same += 1
            else:
                diff += 1
                if len(diffs) < 20:
                    diffs.append(str(relp))
    return {"present": True, "compared": n, "same": same, "diff": diff,
            "only_in_shadow": missing, "diff_samples": diffs}


def scan_clock():
    """口径面 · 时钟（面板读数走 UTC，文件时间戳走本机时区 —— 交叉核对会差数小时）"""
    import datetime as dt
    local = dt.datetime.now().astimezone()
    utc = dt.datetime.now(dt.timezone.utc)
    rc, so, _ = run(["git", "log", "-1", "--format=%ad", "--date=iso"])
    commit = so.strip()
    return {"local": local.strftime("%Y-%m-%d %H:%M:%S"),
            "utc": utc.strftime("%Y-%m-%d %H:%M:%S"),
            "local_utc_offset_h": round(local.utcoffset().total_seconds() / 3600, 1),
            "last_commit_local": commit,
            "note": "本仓运行时面板的『读数』时刻走 UTC；文件时间戳与 git 提交走本机时区"}


def scan_panels():
    """面板登记表 ↔ 盘上实物（本仓的交付面）"""
    rd = ROOT / "plugins" / "gbt-master" / "README.md"
    out = {"registry": str(rd.relative_to(ROOT)) if rd.exists() else None,
           "declared": 0, "missing": [], "host_version": None, "pkg_version": None}
    pj = ROOT / "plugins" / "gbt-master" / "package.json"
    if pj.exists():
        try:
            out["pkg_version"] = json.loads(pj.read_text(encoding="utf-8")).get("version")
        except Exception:
            pass
    if rd.exists():
        t = rd.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"^\|\s*\d+\s*\|[^|]*\|[^|]*\|\s*`([^`]+)`\s*\|", t, re.M):
            path = m.group(1)
            out["declared"] += 1
            if not (ROOT / path).exists():
                out["missing"].append(path)
    try:
        import urllib.request
        # 本机代理会让 127.0.0.1 的请求也走代理 ⇒ TimeoutError。
        # 显式装一个"空代理"opener 绕开（环境变量 http_proxy 存在时的标准坑）。
        op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with op.open("http://127.0.0.1:3080/gbt-master", timeout=12) as r:
            d = json.loads(r.read().decode("utf-8"))
        out["host_version"] = d.get("version")
        out["host_panels"] = len(d.get("panels") or [])
        out["host_panels_all_exist"] = all(x.get("exists") for x in (d.get("panels") or []))
    except Exception as e:
        out["host"] = "未取到（%s）" % type(e).__name__
    return out


def scan_ports():
    """暴露面 · 监听端口（只报，不猜）"""
    ps = ("Get-NetTCPConnection -State Listen | ForEach-Object { "
          "$_.LocalAddress + '|' + $_.LocalPort + '|' + $_.OwningProcess }")
    rc, so, _ = run(["powershell", "-NoProfile", "-Command", ps], timeout=60)
    rows = []
    for line in so.splitlines():
        parts = line.strip().split("|")
        if len(parts) != 3:
            continue
        try:
            addr, port, pid = parts[0], int(parts[1]), int(parts[2])
        except ValueError:
            continue
        rows.append({"addr": addr, "port": port, "pid": pid})
    exposed = []
    if rows:
        pids = sorted({r["pid"] for r in rows if r["addr"] == "0.0.0.0"})
        names = {}
        if pids:
            rc, so, _ = run(["powershell", "-NoProfile", "-Command",
                             "Get-Process -Id %s | ForEach-Object { $_.Id + '|' + $_.ProcessName }"
                             % ",".join(map(str, pids))], timeout=40)
            for line in so.splitlines():
                a = line.strip().split("|")
                if len(a) == 2:
                    names[a[0]] = a[1]
        for r in rows:
            if r["addr"] == "0.0.0.0" and names.get(str(r["pid"]), "") in ("python", "pythonw",
                                                                           "node", "electron"):
                exposed.append({"port": r["port"], "pid": r["pid"],
                                "proc": names.get(str(r["pid"]))})
    return {"listen_n": len(rows), "app_exposed_on_0.0.0.0": exposed,
            "demo": [{"addr": r["addr"], "port": r["port"]} for r in rows[:12]]}


def scan_plane234(junk, name_size):
    out = {}
    for k in ("P2", "P3", "P4", "P6"):
        lst = junk.get(k, [])
        out[k] = {"files": len(lst), "MB": round(sum(s for _, s in lst) / 1048576, 1)}
    dups = [{"name": n, "MB": round(s / 1048576, 2), "n": len(v), "paths": v[:6]}
            for (n, s), v in name_size.items() if len(v) > 1]
    dups.sort(key=lambda x: -(x["MB"] * x["n"]))
    out["big_same_name_size"] = dups[:25]
    return out


def mirror_overwritten(rows, slack=6 * 3600):
    """同名技能**内容一致、但 mtime 跨度很大** ⇒ 发生过一次覆盖/同步，**方向未知**。

    🔴 为什么需要它（第 104 轮实测教训）：09-24 06:57 有一次外部动作把 `.agents` 那两份技能
       **用旧版覆盖** ⇒ 内容变得与另外三个根一致 ⇒ `SKILL_MIRROR_DIVERGED` 静默。
       **那次覆盖在读数里完全看不见** —— 因为"一致"既可能是"本来就一致"，
       也可能是"**刚被覆盖成一致**"。这两个状态天差地别，而原判据分不出来。
    ⚠️ 本判据**只看得见"发生过覆盖"，看不见"哪边是对的"**（没有历史可比）⇒
       它报的是"**待确认**"，不是"有错"。**不许把它念成"发现错误"。**

    rows: {name: {root: (sha12, mtime)}}；返回按跨度降序的 dict 列表。
    """
    out = []
    for n, per in rows.items():
        if len(per) < 2:
            continue
        if len({h for h, _ in per.values()}) != 1:      # 内容不一致 ⇒ 归 MIRROR_DIVERGED 管
            continue
        ts = {k: t for k, (_, t) in per.items()}
        if max(ts.values()) - min(ts.values()) > slack:
            nk = max(ts, key=lambda k: ts[k])
            ok = min(ts, key=lambda k: ts[k])
            out.append({"name": n, "newest": nk, "oldest": ok,
                        "days": round((ts[nk] - ts[ok]) / 86400.0, 1), "roots": len(per)})
    out.sort(key=lambda x: -x["days"])
    return out


def declared_face(atlas_path, roots):
    """图鉴"声明面" vs 盘上实物：**用图鉴自己的 `path` 字段判**，不拿 `name` 猜目录名。

    🔴 为什么改成这样（2026-09-24 第 99 轮，被读数当场否掉两版）：
       v1 拿 `name` 去比"会话根下的目录名" ⇒ 报"97 个加载不到"，
       而逐条核对图鉴的 `path` 发现 **97/97 的路径都存在** —— 假报告，两个原因：
         ① `name` 常是**显示名**（`Agentic Coding`）而目录是 slug（`agentic-coding`）；
         ② 根集**又漏了一棵**：仓内 `审美相关skill/skills/`（887 个技能文件，就是
            `PROD_TOPS_UNTRACKED` 里那棵树）。
       ⇒ 教训同 §五十一：**别拿"名字"去猜"实物在哪"，用实物自己记的路径。**

    返回 {"declared_n", "path_missing":[...], "outside_roots":[...], "err"}
      · path_missing  = 图鉴说在这儿，盘上却没有（**声明了没实物**）⇒ 真信号
      · outside_roots = 盘上有，但不在**任何会话根**下（声明在别处、本会话加载不到）⇒ 真信号
    """
    p = pathlib.Path(atlas_path)
    if not p.is_file():
        return {"err": "图鉴不存在: %s" % p}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:                                                 # noqa: BLE001
        return {"err": "图鉴读取失败 %s: %s" % (type(e).__name__, e)}
    rows = d.get("skills") if isinstance(d, dict) else d
    if not isinstance(rows, list):
        return {"err": "图鉴结构不认识（skills 不是列表）"}
    _roots = [pathlib.Path(x).resolve() for x in roots]
    declared, miss, outside = 0, [], []
    for r in rows:
        if not isinstance(r, dict):
            continue
        name = r.get("name") or r.get("id")
        if not name:
            continue
        declared += 1
        raw = r.get("path")
        if not raw:
            miss.append({"name": str(name), "path": None, "why": "图鉴没记路径"})
            continue
        pp = pathlib.Path(str(raw))
        if not pp.is_absolute():
            pp = ROOT / pp
        try:
            rp = pp.resolve()
        except OSError:
            rp = pp
        if not rp.exists():
            miss.append({"name": str(name), "path": str(raw), "why": "盘上不存在"})
            continue
        if not any(rp == x or x in rp.parents for x in _roots):
            outside.append({"name": str(name), "path": str(raw)})
    return {"declared_n": declared, "path_missing": miss, "outside_roots": outside,
            "roots_checked": [str(x) for x in _roots], "err": None}


def scan_plane5():
    """平面⑤ 装机/系统面：指向对不对（R4 机检）"""
    out = {}
    home = pathlib.Path(os.path.expanduser("~"))
    roots = {
        "repo_skills": ROOT / "skills",
        "repo_.dsh_skills": ROOT / ".dsh" / "skills",
        "agents": home / ".agents" / "skills",
        "openclaw_autoclaw": home / ".openclaw-autoclaw" / "skills",
        "claude": home / ".claude" / "skills",
    }
 # 2026-09-24 第 98 轮补：**旧根集漏了会话真正的加载根** —— agent preset 的 `skills/`。
    #    实测（拿当前会话技能目录里的名字反查）：`cordis-plugin-development` /
    #    `editing-cordis-compositions` / `fc-nginx-website` / `opensearch` 这四个名字
    #    **在本会话里能加载**，却在上面那 5 个根里**一个都找不到**；
    #    它们只在 `$DSH_HOME/.agent-presets/<preset>/skills/` 里（本机 preset = `gbt-spine`）。
    #    ⇒ 旧根集把"本会话可读"算错了（它算的是 `.agents` + `.dsh/skills`）。
 # 只收**本机 preset**；装机自带那份在 npm-cache 里、属发布物，**不列进来、也不改**。
    dsh_home = pathlib.Path(os.environ.get("DSH_HOME") or (home / ".dsh"))
    presets_dir = dsh_home / ".agent-presets"
    if presets_dir.is_dir():
        for _p in sorted(presets_dir.iterdir()):
            _sd = _p / "skills"
            if _sd.is_dir():
                roots["preset_" + _p.name] = _sd

    skills, per_root_names, per_root_mtime = {}, {}, {}
    for k, d in roots.items():
        if d.is_dir():
            g = sorted(p.name for p in d.iterdir() if p.is_dir() and p.name.startswith("gbt-"))
            skills[k] = {"path": str(d), "gbt_n": len(g), "has_gbt_system": "gbt-system" in g}
            per_root_names[k], per_root_mtime[k] = {}, {}
            for n in g:
                _f = d / n / "SKILL.md"
                if _f.is_file():
                    per_root_names[k][n] = hashlib.sha256(_f.read_bytes()).hexdigest()[:12]
                    per_root_mtime[k][n] = _f.stat().st_mtime
        else:
            skills[k] = {"path": str(d), "exists": False, "gbt_n": 0}
    out["skill_roots"] = skills
    # 口径必须**可审计**：把"我到底查了哪些根"原样带出来（否则「可读 N 个」是不可复核的数）
    out["skill_roots_checked"] = sorted(skills)
    out["session_readable_gbt_n"] = (
        skills.get("repo_.dsh_skills", {}).get("gbt_n", 0)
        + skills.get("agents", {}).get("gbt_n", 0)
        + sum(v.get("gbt_n", 0) for k, v in skills.items() if k.startswith("preset_")))

    # ── 同名技能跨根**内容分歧**（2026-09-24 第 98 轮）
    # 待进化那条 `SKILL_DECLARED_NOT_LOADABLE` 要的正是"逐名差集"。但实测本机 4 个根
    # **镜像**同一批 gbt-*（各 59 个）⇒ 真正的风险**不是"缺"，而是"同名不同内容"**：
    # 改了一份、另一份没改 ⇒ "改哪份生效"说不清。只哈希 gbt-* 的 SKILL.md（小文件，秒级）。
    _div = []
    _allnames = sorted({n for v in per_root_names.values() for n in v})
    for n in _allnames:
        where = {k: v[n] for k, v in per_root_names.items() if n in v}
        if len(where) >= 2 and len(set(where.values())) > 1:
            _div.append({"name": n, "roots": sorted(where), "sha12": where})
    out["skill_mirror_diverged"] = {
        "n": len(_div), "names_seen_in_any_root": len(_allnames),
        "roots_hashed": sorted(per_root_names), "sample": _div[:12]}

    # ── 同名 + **内容一致但 mtime 差很多** = 覆盖/同步的痕迹（2026-09-24 第 105 轮）
    # 动机：06:57 那次外部覆盖把分歧"抹平"了，而在读数里**完全看不见**。
    # 【实测】59 个名字里内容一致的：<6h 57 个 · **1~7d 2 个**（正是被覆盖的那两个）· ≥7d 0
    # ⇒ 这条信号在本机**零噪声**。
    _rows = {}
    for _k in per_root_names:
        for _n, _h in per_root_names[_k].items():
            _rows.setdefault(_n, {})[_k] = (_h, per_root_mtime.get(_k, {}).get(_n, 0.0))
    _ovr = mirror_overwritten(_rows)
    out["skill_mirror_overwritten"] = {
        "n": len(_ovr), "slack_h": 6, "sample": _ovr[:12],
        "roots_hashed": sorted(per_root_names)}

    # ── 声明面 vs 盘上实物（2026-09-24 第 99 轮：待进化的 `SKILL_DECLARED_NOT_LOADABLE`）
    # 判定走**图鉴自己的 `path`**（权威），不拿 `name` 猜目录名 —— v1 就是这么错的：
    # `name` 常是显示名（`Agentic Coding`）而目录是 slug（`agentic-coding`）⇒ 报出 97 个假缺。
 # 根集也已按 §五十一 补上 `$DSH_HOME/.agent-presets/*/skills`；
    #    但注意仓内还有一棵 `审美相关skill/skills/`（887 个技能文件）**不在**会话根里 ——
    #    它会被这条判据如实列进 `outside_roots`，那正是要让人看见的东西。
    _df = declared_face(ROOT / "state" / "skill_atlas.json",
                        [d for d in roots.values() if d.is_dir()])
    _out = _df.get("outside_roots") or []
    out["skill_declared"] = {
        "atlas": str(ROOT / "state" / "skill_atlas.json"),
        "declared_n": _df.get("declared_n", 0),
        "path_missing_n": len(_df.get("path_missing") or []),
        "path_missing_sample": [x["name"] for x in (_df.get("path_missing") or [])[:8]],
        "outside_roots_n": len(_out),
        "outside_roots_sample": [x["path"] for x in _out[:6]],
        # 有多少是"在仓内、但不在任何会话根下"（`审美相关skill` 那种）vs 仓外
        "outside_in_repo_n": sum(1 for x in _out
                                 if str(x["path"]).replace("/", "\\").startswith(str(ROOT))),
        "roots_checked": _df.get("roots_checked") or [],
        "error": _df.get("err")}
    ps = ("Get-ScheduledTask | Where-Object { $_.TaskName -like 'GBT*' } | ForEach-Object { "
          "$_.TaskName + '|' + $_.State + '|' + (($_.Actions | ForEach-Object { "
          "$_.Execute + [char]31 + $_.Arguments }) -join ' ;; ') }")
    rc, so, _ = run(["powershell", "-NoProfile", "-Command", ps], timeout=60)
    tasks = []
    path_re = re.compile(r"[A-Za-z]:\\[^\"';|\x1f]+?\.(?:%s)" % "|".join(
        e.lstrip(".") for e in PROJECT_EXT))
    for line in so.splitlines():
        line = line.strip()
        if "|" not in line:
            continue
        name, state, actions = (line.split("|", 2) + ["", ""])[:3]
        targets = path_re.findall(actions.replace("\x1f", "  "))
        outside, missing = [], []
        for t in targets:
            if not pathlib.Path(t).exists():
                missing.append(t)
                continue
            if INTERP_DIRS.search(t):
                continue                       # 解释器/系统目录不是项目目标
            if str(ROOT).lower() not in t.lower().replace("/", "\\"):
                outside.append(t)
 # 2026-09-23 第 48 轮修（**FR-8 的形：静默截断**）：
        #    三个 `[:4]` 都只列前 4 条，却**不说还有多少条没列出来** ——
        #    10 条缺失只看到 4 条，读者会把「只列了 4 条」读成「一共只有 4 条」。
        #    修法与本会话在 `pipeline.list_records` / `collab_gateway.inbox` /
        #    `agency_tentacles.catalog` 的改法同款：**报全量数 + 一句 note**。
 # `"missing_total"` **不会**再触发 FR-2：那条规则的正则是
        #       `["']missing["']\s*[:=]`（`missing` 后紧跟引号），
        #       而 `"missing_total"` 里 `missing` 后面是 `_`，不匹配。
 # 本行以上新增了注释 ⇒ 带 missing 键那一行的**行号会变**，
        #       必须同步更新 `false_report_audit.KNOWN_LEGIT` 里带行号的那条登记
        #       （第 48 轮刚立的判据会在行号填错时变红，见 `test_false_report_audit.py`）。
 # 上面两句**故意不把那个键的写法原样抄进来**（不写成 引号+missing+引号+冒号）：
        #       抄进来就等于在**被审计的文件里**摆了一个 FR-2 的正则靶子 ——
        #       实测第 48 轮就是这么自己撞上去的（那一行被当成一条新的 FR-2 命中报出来）。
        #       这正是本会话第 79 条：**我的记录动作，改变了我自己的测量结果。**
        _shown = max(len(targets), len(outside), len(missing))
        tasks.append({"task": name.strip(), "state": state.strip(),
                      "targets": targets[:4], "outside_repo": outside[:4],
                      "missing": missing[:4],
                      "targets_total": len(targets),
                      "outside_repo_total": len(outside),
                      "missing_total": len(missing),
                      "count_note": ("三个 *_total 是全量；上面三个列表各只列前 4 条"
                                     + ("（**有截断**）" if _shown > 4 else "（未截断）"))})
    out["scheduled_tasks"] = tasks
    sib = []
    for base in (ROOT.parent, home):
        try:
            for d in base.iterdir():
                if not d.is_dir() or d == ROOT or not re.search(r"GBT|xiaotudou|gbt", d.name, re.I):
                    continue
                n = 0
                for dp, dn, fn in os.walk(d):
                    dn[:] = [x for x in dn if x not in
                             ("node_modules", ".git", ".scratch", "site-packages", ".venv")]
                    n += sum(1 for f in fn if f.endswith(".py"))
                    if n >= SIBLING_BUDGET:
                        break
                sib.append({"path": str(d), "py_files": n,
                            "capped": n >= SIBLING_BUDGET})
        except OSError:
            pass
    out["sibling_workspaces"] = sorted(sib, key=lambda x: -x["py_files"])[:8]
    out["python_running"] = sys.version.split()[0]
    out["caliber_declared"] = "3.14.5 / cpython-314"
    return out


def scan_git(tree):
    """G 索引面：三把尺"""
    out = {}
    rc, _, _ = run(["git", "rev-parse", "--is-inside-work-tree"])
    out["is_repo"] = (rc == 0)
    if not out["is_repo"]:
        return out
    out["head"] = run(["git", "rev-parse", "--short", "HEAD"])[1].strip()
    rc, so, _ = run(["git", "count-objects", "-vH"])
    out["git_objects"] = so.strip().replace("\n", " | ")
    idx = ROOT / ".git" / "index"
    out["index_MB"] = round(idx.stat().st_size / 1048576, 2) if idx.exists() else None
 # 2026-09-24 第 100 轮：**必须关掉 `core.quotepath`**，否则含非 ASCII 字节的路径会被
    #    git **整体加引号转义**（`"delivery/逆向…`、`"\345\256\241…`），于是 `f.split("/")[0]`
    #    拿到的是 `"delivery` / `"\345…` 这种**对不上的键** ⇒ `tracked_by_top.get(t)` 恒为 0
    #    ⇒ P0 `PROD_TOPS_UNTRACKED` **假红**。实测（第 100 轮）：
    #      `审美相关skill` 索引里实际 **890** 条、`delivery` **170** 条，却被报成「入库 0」；
    #      而 `projects`/`.dsh`/`plugins` 在两种口径下都是 0 ⇒ **那三条是真的**。
 # L1153 的 `??` 那一支**早就 `.strip('"')` 了** —— 只有这一支漏了去引号。
    tracked = [li for li in run(["git", "-c", "core.quotepath=false", "ls-files"])[1].splitlines()
               if li.strip()]
    out["tracked_n"] = len(tracked)
    junk_pat = re.compile(r"^(\.scratch/|\.trash/|\.backups/|\.shadow-repo/|_upstream/|vendor/)"
                          r"|/node_modules/")
    junk_t = [f for f in tracked if junk_pat.search(f)]
    out["tracked_junk_n"] = len(junk_t)
    out["tracked_junk_pct"] = round(100.0 * len(junk_t) / max(1, len(tracked)), 1)
    junk_set = set(junk_t)
    b = 0
    big = []

    def _stat(f):
        try:
            return f, (ROOT / f).stat().st_size
        except OSError:
            return f, -1
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=12) as ex:      # NTFS 上 stat 是 I/O 密集，线程池有效
        for f, s in ex.map(_stat, tracked, chunksize=512):
            if s < 0:
                continue
            if f in junk_set:
                b += s
            if s >= 20 * 1024 * 1024:
                big.append({"path": f, "MB": round(s / 1048576, 2)})
    out["tracked_junk_MB"] = round(b / 1048576, 1)
    big.sort(key=lambda x: -x["MB"])
    out["tracked_large"] = big[:15]
 # 2026-09-24 第 101 轮：与 L1107 同一个坑。**当前计数不受影响，但这是巧合**——
    #    实测：未跟踪名的**首段**是转义形态的有 **18 条**，而它们**全是仓根级文件**（无 `/`），
 # 于是靠下面 `"/" not in f` 那一支被收进来了。 一旦出现"未跟踪目录挂在非 ASCII
    #    顶层下"，它就会**被静默丢掉**（`f.split("/")[0]` 对不上 `PROD_TOPS`）。
    #    ⇒ 关掉 quotepath：计数不变（实测 `??` 两种口径都是 44460 条），
    #      但路径变回可读、且不再依赖巧合。
    rc, so, _ = run(["git", "-c", "core.quotepath=false", "status", "--porcelain=v1", "-uall"])
    lines = [li for li in so.splitlines() if li.strip()]
    out["porcelain_n"] = len(lines)
    out["porcelain_cats"] = dict(Counter(li[:2] for li in lines))
    rc, so, _ = run(["git", "ls-files", "-o", "--exclude-standard", "plugins"])
    out["plugins_untracked_n"] = len([li for li in so.splitlines() if li.strip()])
    rc, so, _ = run(["git", "check-ignore", "-q", "plugins/gbt-master"])
    out["plugins_ignored"] = (rc == 0)
 # 2026-09-23 自查补：原版只查 plugins/，漏掉了 skills/ 与 tools/ 同样未入库。
    # 泛化成"生产面每个顶层的入库比例"——凡 ≥20 个文件且入库 0 个 = 只活在磁盘上。
    prod_by_top = Counter()
    for p, _ in tree["prod"]:
        try:
            prod_by_top[p.relative_to(ROOT).parts[0]] += 1
        except (ValueError, IndexError):
            pass
    tracked_by_top = Counter(f.split("/")[0] for f in tracked)
    out["prod_top_tracking"] = {
        t: {"files": n, "tracked": tracked_by_top.get(t, 0)}
        for t, n in sorted(prod_by_top.items(), key=lambda kv: -kv[1])}
    out["prod_tops_untracked"] = sorted(
        (t for t, n in prod_by_top.items()
         if n >= 20 and tracked_by_top.get(t, 0) == 0),
        key=lambda t: -prod_by_top[t])
    # 生产面"未入库也未被忽略"的散件（含根级交付物 —— 这类单文件不会被上面的顶层判据抓到）
    untr = [li[3:].strip().strip('"') for li in lines if li.startswith("?? ")]
    prod_untr = [f for f in untr
                 if f.split("/")[0] in PROD_TOPS or "/" not in f]
    out["untracked_prod_n"] = len(prod_untr)
    out["untracked_prod_samples"] = prod_untr[:25]
 # 命门：`git grep` 的开关必须放在 `--` **之前**。
    # 2026-09-23 自查抓到：写成 `git grep ... -- <pathspec> -l` 时 `-l` 被当成**路径**，
    # git 退回按行输出 ⇒ 报告里把真密钥**明文打了出来**。
    # 现在只用 `-n`（且放在 `--` 前），并且**一律经过 masked() 再入报告**。
    base = ["git", "grep", "--cached", "-I", "-n", "-E", GIT_SECRET_ERE, "--"] + TEXT_PATHSPEC
    rc, so, _ = run(base, timeout=150)
    cred, fixture = [], []
    for li in so.splitlines():
        parts = li.split(":", 2)
        if len(parts) != 3:
            continue
        f, ln, content = parts
        m = re.search(GIT_SECRET_ERE, content)
        if not m:
            continue
        rule = ("private_key" if "PRIVATE KEY" in m.group(0)
                else "jwt" if m.group(0).startswith("eyJ")
                else "aws" if m.group(0).startswith("AKIA")
                else "github" if m.group(0).startswith("gh")
                else "google" if m.group(0).startswith("AIza")
                else "slack" if m.group(0).startswith("xox")
                else "openai")
        kind = classify_token(rule, m.group(0), content[m.end():])
        rec = {"file": f, "line": ln, "rule": rule, "masked": masked(m.group(0))}
        (cred if kind == "credential_like" else fixture).append(rec)
    out["index_secret_credential_like"] = cred[:40]
    out["index_secret_credential_like_n"] = len(cred)
    out["index_secret_fixture_like_n"] = len(fixture)
    out["index_secret_files_n"] = len({h["file"] for h in cred} | {h["file"] for h in fixture})
    out["index_secret_triage"] = ("credential_like = 无长递增字母跑 且 ≥30 字符；"
                                  "private_key 需 base64 体 ≥200；其余归 fixture_like")
    return out


def scan_framework_gates():
    sys.path.insert(0, str(ROOT))
    try:
        from gbt_allinone.caps_registry import BENIGN_CAPS
        from gbt_allinone.security import policy
        from gbt_allinone.cross_scan import PROBE_SKIP_KINDS
    except Exception as e:
        return {"error": "%s: %s" % (type(e).__name__, e)}
    import tempfile
    iso = tempfile.mkdtemp(prefix="gbt_qs_iso_")
    env = dict(os.environ, GBT_STORE_DIR=iso, PYTHONUTF8="1",
               PYTHONDONTWRITEBYTECODE="1")
    picks = ["selfscan", "truth_scan", "file_hygiene", "inventory", "signature_guard",
             "auth_gate_status", "health", "ghost_guard", "caps_called_audit",
             "coverage_auditor", "sec_surface", "sec_defenses",
             # 这两个在 2026-09-23 万能插最大档实测**无参调用挂死 ≥180 s**，
             # 放进集里就是为了让"挂死"这件事每轮都被看见（超时即报 GATE_RED）
             "sec_scan", "sec_chain"]
    PICK_TIMEOUT = 90
    child = ("import json,sys;sys.stdout=sys.stderr;sys.path.insert(0,sys.argv[1]);"
             "from gbt_allinone.api import run_task;"
             "r=run_task(sys.argv[2],{});b=r.get('gbt_result',r) if isinstance(r,dict) else {};"
             "res=b.get('result') if isinstance(b,dict) else None;"
             "open(sys.argv[3],'w',encoding='utf-8').write(json.dumps("
             "{'status':(b.get('status') if isinstance(b,dict) else None) or 'ok',"
             "'verdict':(res.get('verdict') if isinstance(res,dict) else None),"
             "'ok':(res.get('ok') if isinstance(res,dict) else None),"
             "'head':(json.dumps(res,ensure_ascii=False,default=str)[:200] if res is not None else None)},"
             "ensure_ascii=False))")
    res = {}
    for k in picks:
        meta = BENIGN_CAPS.get(k)
        if not meta or not meta.get("safe") or k in PROBE_SKIP_KINDS:
            res[k] = {"skipped": "不在可直跑集"}
            continue
        try:
            if list(getattr(policy.evaluate(k, {}), "scopes", ()) or ()):
                res[k] = {"skipped": "要过授权门"}
                continue
        except Exception:
            res[k] = {"skipped": "policy 求值失败"}
            continue
        fd, o = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            p = subprocess.run([sys.executable, "-c", child, str(ROOT), k, o],
                               timeout=PICK_TIMEOUT, env=env, capture_output=True)
            res[k] = json.loads(pathlib.Path(o).read_text(encoding="utf-8"))
            res[k]["rc"] = p.returncode
        except subprocess.TimeoutExpired:
            res[k] = {"status": "timeout>%ds" % PICK_TIMEOUT}
        except Exception as e:
            res[k] = {"status": type(e).__name__}
        finally:
            try:
                os.unlink(o)
            except OSError:
                pass
    import shutil
    shutil.rmtree(iso, ignore_errors=True)
    return res


def caliber_mismatch(p5):
    """解释器口径是否真的与**声明**不符？→ dict。

    🔴 为什么重写（第 107 轮）：原判据是 `if p5.get("python_running") != "3.14.5"` ——
       **写死了一个常量**，而它报的文案是「口径与**声明**不符」并引用了 `caliber_declared`。
       后果（下一次补丁升级就会现形）：本仓升到 3.14.6 时，它会印出
       **「运行 3.14.6 · 声明 3.14.6 / cpython-314」**，然后**照样叫"不符"** ——
       一句话自己打自己的脸。**判据不许拿常量冒充"声明"。**

    🔴 口径怎么算（沿用家规的语义：声明是 `3.14.5 / cpython-314`，**换解释器才打 not_comparable**）：
       - **major.minor** 不同 ⇒ 真不符（换了解释器）；用 `cache_tag` 补强的 `cpython-314` 也一并看；
       - **只差补丁号**（3.14.5 vs 3.14.6）⇒ **不算不符**（同一个 cpython-314，仍是可比口径），
         但这事必须**看得见**（由调用方写进盲区口径），不能悄悄放过；
       - **读不出来**（running 空 / declared 解析不出）⇒ **报**（未知不许当通过）。
    """
    run = str(p5.get("python_running") or "").strip()
    dec_raw = str(p5.get("caliber_declared") or "").strip()

    def _mm(s):
        m = re.match(r"^(\d+)\.(\d+)", s)
        return (m.group(1), m.group(2)) if m else None

    run_mm, dec_mm = _mm(run), _mm(dec_raw)
    out = {"running": run, "declared": dec_raw, "running_mm": run_mm, "declared_mm": dec_mm,
           "fire": False, "why": "", "patch_only": False}
    if not run or run_mm is None:
        out.update(fire=True, why="运行口径读不出来（未知不许当通过）")
    elif dec_mm is None:
        out.update(fire=True, why="声明口径读不出 major.minor（未知不许当通过）")
    elif run_mm != dec_mm:
        out.update(fire=True, why="%s ≠ %s（换了解释器）"
                   % (".".join(run_mm), ".".join(dec_mm)))
    elif run != dec_raw.split("/")[0].strip():
        # 同 major.minor、只差补丁号或后缀 ⇒ 不算不符，但要让调用方把这件事写出去
        out.update(patch_only=True, why="同 %s 族、仅补丁号/后缀不同（仍按可比口径处理）"
                   % ".".join(run_mm))
    return out


def _ver_tuple(s, n=4):
    """把 '1.2.3-beta' 这类串取出一串数字 → (1,2,3)。取不到数字返回 None。"""
    parts = re.findall(r"\d+", str(s or ""))
    return tuple(int(x) for x in parts[:n]) if parts else None


def host_version_behind(pn):
    """跑着的宿主版本是否**落后于**盘上包声明？→ dict(fire, ahead, absent, why, pkg, host)

    🔴 为什么重写（第 108 轮）：原条件只查 `pkg_version != host_version`（**只查不等**），
       而它的文案断言的是**一个方向** ——「跑着的宿主版本**落后于**盘上包声明（改了还没重启）」。
       ⇒ 一旦宿主**比盘上包新**（开发中很常见：宿主先重启、包还没发），
       它会照样报「宿主**落后**」，**把方向说反**。
       **判据的文案断言了什么方向，条件就必须真判那个方向**；只查"不等"就是把方向丢了。

    🔴 另一条同样要紧：**"面没取到" ≠ "值读不出来"**。
       原判据在任一侧为空时**静默**（那是"这个面没接线"），此时**不该报**；
       但两侧都在、只是**读不出数字**时**必须报**（未知不许当通过）。
    """
    pkg = str(pn.get("pkg_version") or "").strip()
    host = str(pn.get("host_version") or "").strip()
    out = {"pkg": pkg, "host": host, "fire": False, "ahead": False, "absent": False, "why": ""}
    if not pkg or not host:
        out.update(absent=True, why="版本面未取到（盘上/宿主任一侧为空）⇒ 本判据本轮未生效")
        return out
    pv, hv = _ver_tuple(pkg), _ver_tuple(host)
    if not pv or not hv:
        out.update(fire=True, why="两侧都在、但有版本读不出数字（未知不许当通过）")
    elif hv < pv:
        out.update(fire=True, why="宿主 %s < 盘上 %s ⇒ 改了还没重启" % (host, pkg))
    elif hv > pv:
        out.update(ahead=True, why="宿主 %s > 盘上 %s ⇒ 宿主**超前**，非本判据的风险" % (host, pkg))
    return out


def judge(tree, p1, deps, p234, p5, git, gates, extra=None):
    extra = extra or {}
    # ── T 测试口径面（今天的头号发现）
    tc = extra.get("test_caliber") or {}
    if tc:
        if not tc.get("repo_local_config"):
            add("P1", "T", "TEST_CALIBER_MISSING",
                "仓内没有自证测试口径的文件（跑法要靠口口相传）",
                "根目录无 pytest.ini/conftest.py/pyproject.toml/setup.cfg/tox.ini",
                "加 conftest.py（自动设 GBT_STORE_DIR）+ pyproject.toml（钉 rootdir 与超时）")
        hij = tc.get("parent_config_hijack") or []
 # 2026-09-24 修一条**假红判据**（坏判据比坏对象更危险）：
        #    原来只写 `if hij:` ⇒ 只要上级存在配置文件就报，
        #    **完全不看仓根有没有自己的配置**。而它自己给的修法恰恰是"在仓根放配置钉死 rootdir"
        #    ⇒ 按修法修完，它照样报（实测：改前 rootdir=C:\Users\ADMIN / configfile=pyproject.toml，
        #      加了仓根 pytest.ini 后 configfile=pytest.ini、collection 错误 251→0，而这条仍被报出来）。
        #    pytest 的 rootdir 是**从 cwd 向上遇到的第一个配置**就停 ⇒
        #    只有"上级有、仓根没有"时那条上级配置才真能劫持。
        if caliber_hijack(tc)[0]:
            add("P1", "T", "TEST_CALIBER_HIJACK",
                "**仓外**的 pytest 配置会劫持 rootdir 并强加超时 —— 仓内测试结论不由仓内决定",
                "检出上级配置：%s（且**仓根没有**自己的配置，pytest 会一路向上走到它）"
                % ", ".join(hij[:3]),
                "在仓根放 pytest.ini/pyproject.toml 钉死 rootdir；或清掉上级那份")
        col = tc.get("collect") or {}
        if col.get("no_isolated_store", {}).get("collected", 1) == 0:
            a = col.get("no_isolated_store", {})
            b = col.get("with_isolated_store", {})
            add("P1", "T", "TEST_COLLECT_ZERO",
                "默认姿势收不到任何用例（设隔离 store 才收得到）",
                "不设 GBT_STORE_DIR：collected=%s errors=%s ｜ 设了：collected=%s"
                % (a.get("collected"), a.get("errors"), b.get("collected")),
                "把 GBT_STORE_DIR 的设定写进仓内 conftest.py，别靠人记")
        if not tc.get("conftest_sets_store") and tc.get("repo_local_config"):
            add("P2", "T", "CONFTEST_NO_STORE_ISOLATION",
                "有仓内配置但没自动隔离 store", "conftest.py 未出现 GBT_STORE_DIR",
                "补上，否则每次都要人手动设环境变量")
    # ── 编码/解析卫生（从慢扫搬进速扫）
    for key, code, what, sev in (
            ("bom", "BOM_PRESENT", "生产面文本带 UTF-8 BOM", "P2"),
            ("non_utf8", "NON_UTF8", "生产面文本不是 UTF-8（GBK 等）", "P1"),
            ("nul_like", "NUL_BYTES", "文本扩展名里含 NUL 字节", "P2"),
            ("mojibake", "MOJIBAKE", "生产面文本有乱码标记", "P2"),
            ("mixed_eol", "MIXED_EOL", "同一文件混合换行", "P2")):
        v = p1.get(key) or []
        if v:
            add(sev, "P1", code, what, "%d 个，例：%s" % (len(v), ", ".join(v[:3])),
                "统一；非 UTF-8 的 .bat 在 UTF-8 控制台下必然乱码")
    for key, code, what in (("json_bad", "JSON_BAD", "生产面 JSON 解析失败"),
                            ("yaml_bad", "YAML_BAD", "生产面 YAML 解析失败"),
                            ("toml_bad", "TOML_BAD", "生产面 TOML 解析失败")):
        v = p1.get(key) or []
        if v:
            add("P1" if len(v) > 3 else "P2", "P1", code, what,
                "%d 个：%s" % (len(v), "; ".join("%s %s" % (x["path"], x["msg"])
                                               for x in v[:3])),
                "逐个修；BOM 前缀的 JSON 要用 utf-8-sig 读")
    if p1.get("invalid_escapes"):
        add("P2", "P1", "INVALID_ESCAPE",
            "无效转义序列（未来 Python 版本会升级为报错）",
            "%d 处，例：%s" % (len(p1["invalid_escapes"]), p1["invalid_escapes"][0]),
            "用 raw string 或双反斜杠")
    if p1.get("todo_markers", 0) > 500:
        add("P2", "P1", "TODO_HIGH", "生产面 TODO/FIXME/XXX/HACK 过多",
            "%d 处" % p1["todo_markers"], "清理或转成登记表，别留在代码里当注释")
    if deps.get("relative_broken_n"):
        add("P1", "P1", "REL_IMPORT_BROKEN", "相对导入断链（包内引用不到真身）",
            "%d 处，例：%s" % (deps["relative_broken_n"],
                           "; ".join("%s %s" % (x["file"], x["import"])
                                     for x in deps["relative_broken"][:3])),
            "补文件或改导入层级")
    # ── 文档断链
    dl = extra.get("doclinks") or {}
    if dl.get("broken_n"):
        add("P1" if dl["broken_n"] > 20 else "P2", "P1", "DOC_LINKS_BROKEN",
            "生产面文档相对链接断链",
            "%d/%d 条；例：%s" % (dl["broken_n"], dl.get("links_total"),
                              "; ".join(dl["broken"][:3])),
            "补文件或改链接")
    # ── 第二真相
    sh = extra.get("shadow") or {}
    if sh.get("present") and sh.get("diff", 0) > 10:
        add("P1", "P4", "SHADOW_DRIFT",
            ".shadow-repo 与真身内容漂移（第二真相）",
            "可比 %d：同 %d / **不同 %d** / 真身没有 %d；例：%s"
            % (sh.get("compared"), sh.get("same"), sh.get("diff"),
               sh.get("only_in_shadow"), ", ".join(sh.get("diff_samples", [])[:3])),
            "把影子仓标为只读归档或删除，别让两处真相并存")
    # ── 面板交付面
    pn = extra.get("panels") or {}
    if pn.get("missing"):
        add("P1", "P1", "PANEL_REGISTRY_MISSING",
            "面板登记表里有文件不存在（登记面与实物脱钩）",
            "登记 %s 条，缺：%s" % (pn.get("declared"), ", ".join(pn["missing"][:4])),
            "补文件或从登记表撤下")
    _hv = host_version_behind(pn)
    if _hv["fire"]:
        add("P2", "P5", "HOST_VERSION_BEHIND",
            "跑着的宿主版本落后于盘上包声明（改了还没重启）",
            "盘上 %s vs 宿主现报 %s" % (pn["pkg_version"], pn["host_version"]),
            "重启会话头才会换代；不是坏了，但别当成已生效")
    # ── 暴露面
    pt = extra.get("ports") or {}
    if pt.get("app_exposed_on_0.0.0.0"):
        add("P1", "P5", "PORT_EXPOSED",
            "应用进程监听在 0.0.0.0（对外可及）",
            "; ".join("%s:%s pid=%s" % (x["proc"], x["port"], x["pid"])
                      for x in pt["app_exposed_on_0.0.0.0"][:4]),
            "确认是否必要；非必要改成只绑 127.0.0.1")
    # ── 根级/散件未入库
    if git.get("untracked_prod_n", 0) > 50:
        add("P1", "G", "UNTRACKED_PROD_FILES",
            "生产面有大量未入库也未被忽略的散件",
            "%d 个（含根级交付物：%s）"
            % (git["untracked_prod_n"],
               ", ".join(git.get("untracked_prod_samples", [])[:4])),
            "git add 或写进 .gitignore 并说明理由")
    # ── P0
    cred = git.get("index_secret_credential_like_n", 0)
    if cred:
        top = git.get("index_secret_credential_like", [])
        add("P0", "G", "SECRET_IN_INDEX",
            "git 索引里有**像真密钥**的串（一条 commit 即写入历史）",
            "%d 条（另有 %d 条判为夹具/占位符）：%s"
            % (cred, git.get("index_secret_fixture_like_n", 0),
               "; ".join("%s:%s %s" % (h["file"], h["line"], h["masked"]) for h in top[:4])),
            "git rm --cached 这些文件 + 轮换密钥；先 git log -S 确认是否已进历史")
    ut = git.get("prod_tops_untracked") or []
    if ut:
        detail = "; ".join("%s(%d 文件/入库 0)"
                           % (t, git["prod_top_tracking"][t]["files"]) for t in ut[:5])
        add("P0", "G", "PROD_TOPS_UNTRACKED",
            "生产面有整棵顶层不在版本控制里（能力只活在磁盘上）",
            detail,
            "把这些顶层纳入版本控制，或明确声明它们是本机状态（.gitignore + 写明理由）")
    if git.get("tracked_junk_pct", 0) > 50:
        add("P0", "G", "INDEX_MOSTLY_JUNK",
            "版本控制索引过半是作业残骸（门只挡新增，没清存量）",
            "跟踪 %d，残骸 %d（%.1f%%），约 %.1f MB"
            % (git["tracked_n"], git["tracked_junk_n"], git["tracked_junk_pct"],
               git.get("tracked_junk_MB", 0)),
            "对 .scratch/.trash/.backups/node_modules 执行 git rm -r --cached（不删盘上文件）")
    sk = p5.get("skill_roots", {})
    a = sk.get("repo_skills", {}).get("gbt_n", 0)
    read_n = p5.get("session_readable_gbt_n", 0)
    if a > 0 and read_n > 0 and a > read_n * 1.5:
        add("P0", "P5", "SKILL_ROOT_SPLIT",
            "规程技能大面积落在**本会话读不到**的根（声明面与可执行面脱钩）",
            "repo/skills=%d · 本会话可读各根合计=%d · **查过的根=%s**"
            % (a, read_n, ",".join(p5.get("skill_roots_checked") or [])),
            "把这批规程同步进 <repo>/.dsh/skills 或 ~/.agents/skills")
    # ── SKILL_MIRROR_DIVERGED（2026-09-24 第 98 轮）
    # 为什么单列一条：`SKILL_ROOT_SPLIT` 管的是"**缺**"（读不到），
    # 而实测本机 4 个根**镜像**同一批 gbt-*（各 59 个）⇒ 真正的风险是"**同名不同内容**"：
    # 改了一份、另一份没改 ⇒ "改哪份生效"说不清。两种形状不同，不合并。
    _smd = p5.get("skill_mirror_diverged") or {}
    if _smd.get("n"):
        _ex = (_smd.get("sample") or [{}])[0]
        add("P1", "P5", "SKILL_MIRROR_DIVERGED",
            "同名技能在多个根里**内容不一致**（改一份不生效，说不清哪份是真源）",
            "%d/%d 个 gbt-* 名字跨根分歧；例：%s 落在 %s；**哈希过的根=%s**"
            % (_smd["n"], _smd.get("names_seen_in_any_root", 0), _ex.get("name", "?"),
               ",".join(_ex.get("roots") or []), ",".join(_smd.get("roots_hashed") or [])),
            "指定唯一真源，其余改为链接，或在文件头写明『本文件由 X 同步』")
    # ── SKILL_MIRROR_OVERWRITTEN（第 105 轮）
    # 与上一条互补：上一条管"**不一致**"；这条管"**一致、但刚被覆盖过**"。
    # 起因就是 09-24 06:57 那次外部覆盖：它把分歧抹平了、判据静默，**而过程没人看得见**。
    _smo = p5.get("skill_mirror_overwritten") or {}
    if _smo.get("n"):
        _eo = (_smo.get("sample") or [{}])[0]
        add("P2", "P5", "SKILL_MIRROR_OVERWRITTEN",
            "同名技能**内容一致但时间戳差很多** ⇒ 发生过一次覆盖/同步，**方向未知**",
            "%d 个 gbt-* 名字：内容一致、mtime 跨度 > %dh；例：%s（最新=%s · 最旧=%s · 差 %.1f 天）"
            % (_smo["n"], _smo.get("slack_h", 6), _eo.get("name", "?"),
               _eo.get("newest", "?"), _eo.get("oldest", "?"), _eo.get("days", 0)),
            "确认那次覆盖的方向是不是你要的。**本判据只看得见『发生过覆盖』，"
            "看不见『哪边是对的』（没有历史可比）⇒ 它报的是待确认，不是有错。**")
    # ── SKILL_DECLARED_NOT_LOADABLE（2026-09-24 第 99 轮：待进化之一，先量后做）
    # 与上面两条的分工：`SKILL_ROOT_SPLIT` 管"**大面积**读不到"（P0）；
    # 这条管"**逐名**核对：图鉴声明了、却在所有查过的根里都找不到"（P1）。
    _sdc = p5.get("skill_declared") or {}
    if _sdc.get("path_missing_n") or _sdc.get("outside_roots_n"):
        add("P1", "P5", "SKILL_DECLARED_NOT_LOADABLE",
            "图鉴声明的技能**加载不到**：要么声明了没实物，要么实物不在任何会话根下",
            "声明 %d · **盘上不存在 %d** · **不在会话根下 %d**（其中仓内 %d）；"
            "缺物例：%s；不在根下例：%s；**查过的根=%s**"
            % (_sdc.get("declared_n", 0), _sdc.get("path_missing_n", 0),
               _sdc.get("outside_roots_n", 0), _sdc.get("outside_in_repo_n", 0),
               ", ".join(_sdc.get("path_missing_sample") or [])[:70] or "（无）",
               " ｜ ".join((_sdc.get("outside_roots_sample") or [])[:2]),
               ",".join(_sdc.get("roots_checked") or [])),
            "逐条处置：补实物、或把它所在的树加进可加载根、或从图鉴删掉并写明理由")
    # ── P1
    if p1["syntax_errors"]:
        add("P1", "P1", "PY_SYNTAX", "生产代码面有语法错误",
            "; ".join("%s:%s %s" % (e["path"], e["line"], e["msg"])
                      for e in p1["syntax_errors"][:4]),
            "逐个修；注意 .scratch 里的历史脚本不算生产面")
    if deps.get("missing_third_party"):
        add("P1", "P1", "DEP_MISSING",
            "生产代码导入的第三方包在本机不可用（该路径是死的）",
            "缺：%s" % ", ".join("%s×%d" % (k, v) for k, v in
                               sorted(deps["missing_third_party"].items(), key=lambda x: -x[1])[:10]),
            "装，或标成优雅降级并写进 requirements")
    if deps.get("used_but_not_declared"):
        add("P1", "P1", "DEP_UNDECLARED",
            "requirements.txt 没声明生产代码真正在用的包（重装即成谜）",
            "未声明：%s" % ", ".join(deps["used_but_not_declared"][:10]),
            "按实际导入重写 requirements.txt")
    if deps.get("declared_but_unimportable"):
        add("P1", "P1", "DEP_DECLARED_UNUSABLE",
            "requirements.txt 声明的包在本机装不上（声明不可执行）",
            "不可用：%s" % ", ".join(deps["declared_but_unimportable"][:10]),
            "补 vendor 路径说明，或改声明")
    tasks_bad = [t for t in p5.get("scheduled_tasks", []) if t.get("outside_repo")]
    if tasks_bad:
        add("P1", "P5", "TASK_OUTSIDE_REPO", "自启任务指向别的项目（跑的是别处的代码）",
            "; ".join("%s→%s" % (t["task"], t["outside_repo"][0]) for t in tasks_bad[:4]),
            "逐个确认停用或改指；改自启属有后果动作，须主人点头")
    tasks_missing = [t for t in p5.get("scheduled_tasks", []) if t.get("missing")
                     and t.get("state", "").lower() in ("ready", "running")]
    if tasks_missing:
        add("P1", "P5", "TASK_TARGET_MISSING", "已启用的自启任务目标文件不存在（静默失败）",
            "; ".join("%s→%s" % (t["task"], t["missing"][0]) for t in tasks_missing[:4]),
            "修路径或停用")
    if len(p5.get("sibling_workspaces", [])) >= 2:
        add("P1", "P5", "SIBLING_WORKSPACES", "多个兄弟工作区并存，盘上无裁决谁是源",
            "; ".join("%s(%s py)" % (s["path"], ("≥%d" % s["py_files"]) if s.get("capped")
                                     else s["py_files"]) for s in p5["sibling_workspaces"][:4]),
            "指定唯一真源，其余标为只读或归档")
    if gates and not gates.get("error"):
        for k, v in gates.items():
            if isinstance(v, dict) and (v.get("verdict") in ("P0", "P1", "dirty")
                                        or v.get("status") == "timeout>240s"):
                add("P1", "F", "GATE_RED", "框架自带门报红/无响应：%s" % k,
                    "verdict=%s status=%s head=%s" % (v.get("verdict"), v.get("status"),
                                                      (v.get("head") or "")[:90]),
                    "读该门 findings；P0 可能已被 cross_scan 按数据态豁免，别只看总判定")
    # ── P2
    if tree["residue"]:
        add("P2", "P3", "TEMP_RESIDUE", "临时残骸文件名",
            "%d 个，例：%s" % (len(tree["residue"]),
                           ", ".join(x["path"] for x in tree["residue"][:3])),
            "归档或清；注意 _*.py 是本仓历史作业脚本命名")
    if tree["empty_files"]:
        add("P2", "P3", "EMPTY_FILES", "空文件",
            "%d 个，例：%s" % (len(tree["empty_files"]), ", ".join(tree["empty_files"][:3])),
            "清")
    if tree["empty_dirs"]:
        add("P2", "P3", "EMPTY_DIRS", "空目录",
            "%d 个，例：%s" % (len(tree["empty_dirs"]), ", ".join(tree["empty_dirs"][:3])),
            "清或补 .gitkeep")
    # ── MTIME_ANOMALY（2026-09-24 第 96 轮：目录里挂着的『待进化』之一，现落地）
 # 分档**不按数量、按「有多不可能」**：
    #    future       → 机器上出现**未来文件**只可能来自时钟跳变 / 坏工具 / 坏归档 ⇒ P1
    #    epoch0       → mtime 落在 2000 年之前 ⇒ 几乎必是坏拷贝 ⇒ P2
    #    before_ctime → **Windows 上 ctime 是创建时间**，解压/复制保留 mtime 会天生刷屏
    #                   ⇒ 只报**生产面**（排除 P4 第三方树：那是归档语义，不是本仓的病）
    # 一个码只发**一条**判词（不是三条）：`diff_baseline` 按 code 建字典，
    #    同码多条只会互相覆盖 ⇒ 那等于给自己造一个"看起来报了、其实被覆盖"的假读数。
    _ma = (tree or {}).get("mtime_anomaly") or {}
    _fut = _ma.get("future") or []
    # 下面两档都排除 P4（第三方树）：那是**归档语义**，不是本仓的病
    _ep0 = [x for x in (_ma.get("epoch0") or []) if str(x.get("plane")) != "P4"]
    # 注意：`before_ctime` 这一档**故意不取用**（理由见下），它只经 `planes.mtime_anomaly` 出产物
    _sn = int(_ma.get("sentinel1980_n") or 0)     # 被排除的 ZIP 下界哨兵数（如实报）
 # `before_ctime` **故意不进故障**（2026-09-24 第 96 轮，量出来的决定）：
    #    实测本机全树 14290 个命中，其中 **9540 个倒挂不到 1 天**（= 复制/检出的常态），
    #    1~7 天又有 1679 个；剩下的按族归因全落在 `store/native_browser/profile`
    #    （Chromium 自带旧时间戳）与第三方树上 —— **都是合法拷贝，不是病**。
    #    ⇒ 把它报成故障就是"把常态念成病"。它只作为读数留在 `planes.mtime_anomaly` 里。
    if _fut or _ep0:
        _sev = "P1" if _fut else "P2"
        _parts = []
        if _fut:
            _parts.append("未来时间戳 %d 个（例：%s）" % (len(_fut), ", ".join(
                "%s +%.1f 分钟" % (x["path"], x["ahead_min"]) for x in _fut[:2])))
        if _ep0:
            _parts.append("mtime 早于 2000 年 %d 个（例：%s）" % (len(_ep0), ", ".join(
                "%s @%s" % (x["path"], x["mtime"]) for x in _ep0[:2])))
        if _sn:
            _parts.append("（另有 %d 个是 **ZIP 时间戳下界 1980-01-01** 的哨兵值，"
                          "已知不是病，已排除）" % _sn)
        add(_sev, "P3", "MTIME_ANOMALY", "文件时间戳异常（倒挂 / 落在将来 / 落在远古）",
            "；".join(_parts),
            "核对系统时钟与产生这些文件的工具；解包/复制要显式规范化 mtime；"
            "『早于创建时间』这一档在 Windows 上天生噪声大，故已排除第三方树")
    if p234.get("big_same_name_size"):
        add("P2", "P4", "BIG_DUP_NAME_SIZE",
            "同名同体积大文件存在多份（免哈希即可判）",
            "; ".join("%s ×%d（%sMB）" % (d["name"], d["n"], d["MB"])
                      for d in p234["big_same_name_size"][:4]),
            "留一份，其余改用链接或删除")
    # ── DUP_EXACT_CONTENT（2026-09-24 第 97 轮：目录『待进化』之一，先量后做）
    # 与 BIG_DUP_NAME_SIZE 的分工：那条**只看同名同体积**（免哈希、可误报不同内容）；
    # 这条**用 sha256 确认内容相同**（跨文件名也算），是它的严格版。
    _de = (extra or {}).get("dup_exact") or {}
    if _de.get("groups_n"):
        _g0 = (_de.get("groups") or [{}])[0]
        add("P2", "P4", "DUP_EXACT_CONTENT",
            "同体积**且内容相同**的文件有多份（sha256 确认，可回收空间）",
            "≥%dKB 档：%d 组 / **可回收 %.1f MB**；最大一组 %s（%.2fMB ×%d）；"
            "本轮哈希 %d 个%s"
            % (_de.get("floor_kb", 0), _de["groups_n"], _de.get("waste_mb", 0),
               (_g0.get("paths") or ["?"])[0], _g0.get("MB", 0), _g0.get("n", 0),
               _de.get("cand_n", 0),
               "（**已达上限 %d，未全比**）" % _de["cap"] if _de.get("capped") else ""),
            "留一份，其余改用硬链接或删除；**本判据只报不删**")
    if tree.get("node_modules_n", 0) > 1:
        add("P2", "P4", "NODE_MODULES_MULTI", "树里有多份 node_modules（同依赖多装）",
            "%d 份" % tree["node_modules_n"], "收到一处或明确忽略")
    if tree["big"]:
        mx = max(tree["big"], key=lambda x: x["MB"])
        add("P2", "P4", "BIG_FILES", "超 5MB 的大文件",
            "%d 个，最大 %s（%sMB）" % (len(tree["big"]), mx["path"], mx["MB"]),
            "确认是否该入库；入库前走 LFS 或排除")
    if p1["bare_except"] > 50:
        add("P2", "P1", "BARE_EXCEPT", "裸 except 过多（掩盖故障）",
            "%d 处" % p1["bare_except"], "逐处收窄异常类型")
    _cm = caliber_mismatch(p5)
    if _cm["fire"]:
        add("P2", "P5", "CALIBER_MISMATCH", "解释器口径与声明不符",
            "运行 %s · 声明 %s —— %s" % (_cm["running"] or "(空)", _cm["declared"] or "(空)",
                                     _cm["why"]),
            "统一口径；跨口径读数打 not_comparable")


def score(faults):
    c = Counter(f["sev"] for f in faults)
    return {"P0": c.get("P0", 0), "P1": c.get("P1", 0), "P2": c.get("P2", 0),
            "total": len(faults)}


def diff_baseline(cur, base, cur_flags=None):
    if cur_flags and base.get("flags") and cur_flags != base["flags"]:
 # 点名**是哪几个开关**不一致，而不是只说"开关不一致"：
        #    读的人要能一眼分出这是「面没跑」还是「测试口径没跑」——两者的后果完全不同。
        _bf, _cf = base["flags"], cur_flags
        _differ = sorted(k for k in set(_bf) | set(_cf) if _bf.get(k) != _cf.get(k))
        return {"not_comparable": True,
                "why": "基线口径与本轮不同（开关不一致：%s）——按家规不得直接判为『新增故障』"
                       % ("、".join(_differ) if _differ else "未知（基线未记录该项）"),
                "flags_differ": _differ,
                "base_flags": _bf, "cur_flags": _cf,
                "base_at": base.get("meta", {}).get("at")}
    # 比对**按判据码**（code），不按证据文本 ——
    # 否则同一个故障换了几个样本文件名就会被算成"新增 1 / 已修 1"，读数抖动、无法收敛。
    # 证据的变化单列进 `evidence_changed`，不混进"新增"。
    b = {f["code"]: f for f in base.get("faults", [])}
    c = {f["code"]: f for f in cur}
    new = [c[k] for k in c if k not in b]
    fixed = [b[k] for k in b if k not in c]
    changed = [{"code": k, "was": b[k]["evidence"][:110], "now": c[k]["evidence"][:110]}
               for k in c if k in b and b[k].get("evidence") != c[k].get("evidence")]
    return {"new": new, "fixed": fixed, "same_n": len([k for k in c if k in b]),
            "evidence_changed": changed[:20], "evidence_changed_n": len(changed),
            "base_at": base.get("meta", {}).get("at"),
            "base_flags": base.get("flags"), "cur_flags": cur_flags}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-gates", action="store_true")
    ap.add_argument("--with-tests", action="store_true",
                    help="真跑 pytest --collect-only 两次（不设/设隔离 store），拿 0 vs N 的硬证据")
    ap.add_argument("--no-security", action="store_true",
                    help="跳过安全面(S)：反病毒可见性/持久化/远控/IOC/供应链/hosts/伪装扩展名")
    ap.add_argument("--av-scan", action="store_true",
                    help="🔴 对本仓跑一次真实 Defender 按需扫描（MpCmdRun -DisableRemediation）；慢")
    ap.add_argument("--with-host", action="store_true",
                    help="接入仓内已有主机六层 L3-L5（进程/网络/可疑位置）")
    ap.add_argument("--host-sign", action="store_true",
                    help="配合 --with-host：对进程做数字签名核验（很慢，150s+）")
    ap.add_argument("--no-ledger", action="store_true", help="不往 ledger.jsonl 追加本轮记录")
    ap.add_argument("--trend", action="store_true", help="只输出自动收集的台账趋势后退出")
    ap.add_argument("--discover", action="store_true",
                    help="只输出病因对账（该进化的方向 + 判据死活三分）后退出")
    ap.add_argument("--selftest", action="store_true",
                    help="负对照自检：种已知假故障，验判据真会响；死判据列出来")
    ap.add_argument("--accept", action="store_true")
    ap.add_argument("--json", default=None)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    outdir = pathlib.Path(os.environ.get(
        "GBT_QUICKSCAN_OUT",
        pathlib.Path(os.environ.get("TEMP", "/tmp")) / "gbt-quickscan"))
    outdir.mkdir(parents=True, exist_ok=True)
    outfile = pathlib.Path(a.json) if a.json else outdir / "latest.json"
    basefile = outdir / "baseline.json"

    t0 = time.time()
    stages = {}
    marks = {"last": t0}

    def stage(name):
        now = time.time()
        stages[name] = round(now - marks["last"], 1)
        marks["last"] = now

    tree = walk_tree()
    stage("walk")
    p1 = scan_plane1_prod(tree["prod"])
    stage("plane1_prod")
    imports = p1.pop("_imports", [])
    fp_mods = p1.pop("_fp_mods", set())
    fp_dirs = p1.pop("_fp_dirs", set())
    deps = check_deps(imports, fp_mods, fp_dirs)
    stage("deps")
    p234 = scan_plane234(tree["junk"], tree["name_size"])
    stage("plane234")
    p5 = scan_plane5()
    stage("plane5_machine")
    git = scan_git(tree)
    stage("git_index")
    extra = {
        "test_caliber": scan_test_caliber(deep=a.with_tests),
        "doclinks": scan_doclinks_prod(tree["prod"]),
        "shadow": scan_shadow(),
        "clock": scan_clock(),
        "panels": scan_panels(),
        "ports": scan_ports(),
        # DUP_EXACT_CONTENT（2026-09-24 第 97 轮）：先量后做 —— 实测生产面 ≥64KB 档
        # 26 组 / 最多可回收 308.9 MB，代价是哈希 62 个文件（几秒）。
        "dup_exact": scan_dup_exact(tree),
    }
    stage("extra_faces")
    # ── 安全面(S)：反病毒可见性 / 持久化与远控 / IOC / 供应链 / hosts
    sec_out = None
    if not a.no_security:
        if SEC is None:
            add("P2", "S", "SEC_MODULE_MISSING",
                "安全面模块没装载（本面整块没跑 —— 是「没扫到」，不是「干净」）",
                _SEC_ERR or "import 失败",
                "确认 tools/codex-scripts/quickscan_security.py 存在且可导入")
        else:
            try:
                sec_out = SEC.run(ROOT, tree["prod"],
                                  av_scan=bool(a.av_scan),
                                  host_layers=bool(a.with_host),
                                  host_check_sign=bool(a.host_sign))
                for x in sec_out["faults"]:
                    FAULTS.append(x)
            except Exception as e:                        # noqa: BLE001
                add("P2", "S", "SEC_MODULE_ERROR",
                    "安全面执行出错（本面没跑完 —— 不是「干净」）",
                    "%s: %s" % (type(e).__name__, str(e)[:150]),
                    "看 traceback 修模块；别把出错读成通过")
    stage("security_face")
    gates = scan_framework_gates() if a.with_gates else {}
    stage("framework_gates")
    judge(tree, p1, deps, p234, p5, git, gates, extra)
    stage("judge")

    rep = {
        "schema": SCHEMA,
        "meta": {"tool": "quick_scan", "root": str(ROOT),
                 "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                 "elapsed_s": round(time.time() - t0, 1),
                 "stages_s": stages, "python": sys.version.split()[0]},
        "planes": {
            "P1_production": {**p1, "files": len(tree["prod"]),
                              "MB": round(sum(s for _, s in tree["prod"]) / 1048576, 1)},
            "P2_runtime_data": p234.get("P2", {}),
            "P3_job_residue": p234.get("P3", {}),
            "P4_third_party": {**p234.get("P4", {}),
                               "big_same_name_size": p234.get("big_same_name_size", []),
                               "node_modules_copies": tree.get("node_modules_n", 0)},
            "P6_machine_state": p234.get("P6", {}),
            "P5_machine": p5,
            "T_test_caliber": extra.get("test_caliber"),
            "W_shadow": extra.get("shadow"),
            "clock": extra.get("clock"),
            "panels": extra.get("panels"),
            "ports": extra.get("ports"),
            "doclinks": extra.get("doclinks"),
            "S_security": (sec_out["report"] if sec_out else {"skipped": True}),
 # 时间戳异常**原样**进产物（含被排除的 ZIP 哨兵计数）：
            #    判词里只报"非 P4"的，但读数本身不该被藏起来 —— 否则下次谁也说不清
            #    "到底扫到多少、排除了多少"。
            "mtime_anomaly": tree.get("mtime_anomaly"),
            "plane_names": PLANE_NAME,
        },
        "G_index": git,
        "F_gates": gates,
        "deps": deps,
        "inventory": {"files_total": tree["total"], "bytes_total": tree["bytes"],
                      "GB": round(tree["bytes"] / 2 ** 30, 2),
                      "note": "跳过 .git 子树（由 git count-objects 自报）"},
        "faults": FAULTS,
        "score": score(FAULTS),
        "evolution": {
            "ledger": None, "trend": None, "discover": None, "selftest": None,
            "evolve_module_missing": _EVO_ERR,
        },
        "blind_spots": [
            "只 stat 全树、只读**生产面**内容；平面②③④⑥的内容不逐文件解析",
            "跳过 .git 子树逐文件遍历（改用 git count-objects 自报体量）",
            "重复检测两把尺：大文件同名同体积（全树免哈希）· 精确重复**未做**",
            "未做：动态导入追踪 / 密钥有效性验证 / 二进制格式校验 / 权限位 / 提交历史逐笔审计",
            "未扫：符号链接目标 / 其他用户 profile 下的内容 / 兄弟工作区的内部结构",
            "F 面框架门以**隔离 store** 计，与生产 store 读数不同口径；selfscan 在该口径下必报 P0（数据态），本件照报不豁免",
            "T 面不加 --with-tests 时只做**静态**口径检查（配置有无/上级劫持），不真跑收集",
            "W 面影子比对上限 1200 个文件；超出部分未逐字节比",
            "编码/断链/JSON 解析只覆盖**生产面**（第三方与残骸面不解析内容，故不会报它们的坏）",
            "S 面安全判据是**启发式**：IOC 命中只说明「这段代码长得像那些手法」，不等于恶意；一律只报不判",
            "S 面**不做**全盘哈希比对病毒库（不用外部库）/ 实时行为监控 / 内核 rootkit / 已删除痕迹 / 内存注入",
            "S 面**不自动隔离、不 kill、不改 Defender 设置**；按需扫描(MpCmdRun)默认不跑，需显式加 --av-scan",
            "进化层的『可能已死判据』只是候选：真死活要靠 --selftest 判定，别直接照它删判据",
        ],
    }
 # 面选择必须进 flags（2026-09-24 补）。旧 flags 只记 with_gates/with_tests，
    #    而 `--no-security` 会让 **S 面整块 10 条**不出读数（机器状态码如
    #    PERSIST_USER_WRITABLE 在 4 分钟内不可能消失又回来）⇒ 台账无法区分
    #    「S 面跑了且干净」与「S 面根本没跑」，diff_baseline 的 not_comparable 也拦不住。
    #    实测代价：04:22–05:20 共 8 轮用了 --no-security，`19` 被当成全口径报出去，
    #    其中 10 条不是"修好了"而是"没扫"。这是**坏判据比坏对象更危险**的又一例。
 # 一条**实测口径**要写进产物，否则读的人会以为"没报 = 没扫"：
    #    `mtime 早于创建时间` 全树命中上万，而它是 Windows 上复制/检出/解包的常态
    #    ⇒ 不进判词，但必须在"口径/盲区"里说清它被看过、以及为什么不算病。
    _ma_all = (tree or {}).get("mtime_anomaly") or {}
    if _ma_all.get("before_ctime") or _ma_all.get("sentinel1980_n"):
        rep["blind_spots"].append(
            "MTIME：`mtime 早于创建时间` 实测 %d 个（其中倒挂<1 天 %d 个 = 复制/检出的常态）"
            "· **故不作为故障报**；ZIP 下界哨兵 1980-01-01 另 %d 个（归档格式限制）"
            "· 完整读数见 planes.mtime_anomaly"
            % (len(_ma_all.get("before_ctime") or []),
               sum(1 for x in (_ma_all.get("before_ctime") or []) if x.get("behind_days", 0) < 1),
               int(_ma_all.get("sentinel1980_n") or 0)))
    # DUP_EXACT_CONTENT 的**口径**也要进产物：截断与范围都必须可见
    _de_all = (extra or {}).get("dup_exact") or {}
    if _de_all:
        rep["blind_spots"].append(
            "DUP_EXACT：只比**生产面** ≥%dKB 的同体积文件（第三方树与残骸不去重）"
            "· 本轮候选 %d 个、实际哈希 %d 个%s · 精确重复只查内容相等，"
            "**不判该不该删**（删除是主人的决定）"
            % (_de_all.get("floor_kb", 0), _de_all.get("cand_n", 0),
               _de_all.get("cand_n", 0),
               "，**已达上限 %d 故未全比**" % _de_all["cap"] if _de_all.get("capped") else ""))
    # 图鉴读不了 ⇒ 必须说清"这条判据没生效"，否则读者会以为"一个都没缺"
    # 用 locals().get 取值：避免因 main 里的变量改名而 NameError（本会话踩过同型）
    _p5v = locals().get("p5")
    _skd = (_p5v or {}).get("skill_declared") if isinstance(_p5v, dict) else None
    if _skd and _skd.get("error"):
        rep["blind_spots"].append(
            "SKILL_DECLARED：**图鉴读不了 ⇒ 这条判据本轮未生效**（%s）—— "
            "不要把『没报缺』读成『一个都不缺』" % _skd["error"])
    # CALIBER：同族但补丁号/后缀不同 ⇒ **不算不符**，但口径差异必须留痕（否则"没报"= 看不见）
    if isinstance(_p5v, dict):
        _cmv = caliber_mismatch(_p5v)
        if _cmv.get("patch_only"):
            rep["blind_spots"].append(
                "CALIBER：%s vs %s —— %s" % (_cmv["running"], _cmv["declared"], _cmv["why"]))
    # HOST_VERSION：两种"没报"必须分开说 —— 面没取到（未生效）vs 宿主超前（非本判据风险）
    _pnv = locals().get("pn")
    if isinstance(_pnv, dict):
        _hvv = host_version_behind(_pnv)
        if _hvv.get("absent"):
            rep["blind_spots"].append(
                "HOST_VERSION：%s ⇒ **本判据本轮未生效**（不要把『没报落后』读成『版本一致』）"
                % _hvv["why"])
        elif _hvv.get("ahead"):
            rep["blind_spots"].append("HOST_VERSION：%s" % _hvv["why"])
    flags = {"with_gates": bool(a.with_gates), "with_tests": bool(a.with_tests),
             "no_security": bool(a.no_security), "av_scan": bool(a.av_scan),
             "with_host": bool(a.with_host), "host_sign": bool(a.host_sign)}
    if basefile.exists():
        try:
            rep["diff"] = diff_baseline(FAULTS, json.loads(basefile.read_text(encoding="utf-8")),
                                        flags)
        except Exception as e:
            rep["diff"] = {"error": type(e).__name__}
    outfile.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.accept:
        basefile.write_text(json.dumps({"meta": rep["meta"], "faults": FAULTS,
                                        "score": rep["score"], "flags": flags},
                                       ensure_ascii=False, indent=1), encoding="utf-8")
    # ── 自动进化层：收集台账 / 病因对账 / 负对照自检
    codes_now = [f["code"] for f in FAULTS]
    if EVO is None:
        print("[进化层缺件] %s" % (_EVO_ERR or "quickscan_evolve 未装载"))
    else:
        rep["evolution"]["discover"] = EVO.discover(outdir, set(codes_now))
        if not a.no_ledger:
            p = EVO.append_ledger(outdir, flags=flags, score=rep["score"],
                                  codes=codes_now, meta=rep["meta"])
            rep["evolution"]["ledger"] = str(p)
        rep["evolution"]["trend"] = {k: v for k, v in EVO.trend(outdir).items() if k != "per_code"}
    if a.selftest:
        if EVO is None:
            print("无法自检：进化层缺件")
        else:
            st = EVO.selftest(sys.modules[__name__], outdir)
            rep["evolution"]["selftest"] = st
            outfile.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
            print("=" * 70)
            print("负对照自检｜夹具 %s" % st["fixture_dir"])
            print("=" * 70)
            for c in st["checks"]:
                print("  [%s] %-34s %s" % ("OK" if c["ok"] else "死判据", c["rule"],
                                           c.get("detail", "")))
                if c["miss"]:
                    print("        没响的判据: %s" % ", ".join(c["miss"]))
            print("-" * 70)
            print("结论：%s ｜ 死判据 %s"
                  % ("全部判据都能响" if st["ok"] else "**有死判据**",
                     ", ".join(st["dead_rules"]) or "无"))
            print(st["note"])
            return 0 if st["ok"] else 2
    if a.discover:
        d = rep["evolution"]["discover"]
        outfile.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        print("=" * 70)
        print("病因对账：目录 %d 条 ｜ 已实现 %d ｜ **待进化 %d** ｜ 休眠 %d ｜ 可疑 %d ｜ 未登记 %d"
              % (d["causes_total"], d["implemented_declared"], d["todo_n"],
                 d.get("dormant_n", 0), d.get("suspect_n", 0), d["unregistered_n"]))
        print("=" * 70)
        print("▼ 该进化的方向（目录已登记、判据未实现）：")
        for c in d["todo"]:
            print("   [%s] %-28s %s" % (c.get("plane"), c.get("code"), c.get("title")))
            if c.get("how"):
                print("        怎么做: %s" % c["how"])
        if d.get("suspect"):
            print("▼ 从未响过且未被自检验过（跑 --selftest 判死活）：%s" % ", ".join(d["suspect"]))
 # 第 103 轮：把"量过、决定不做"的**也打出来**（连理由一起）。
        #    只把它们从 todo 里摘掉而不显示，读的人会以为"这些条目消失了"；
        #    打出来才看得见"有人量过、结论是不值得做"，也才好在有异议时被推翻。
        for _r in d.get("rejected_measured") or []:
            print("▼ 已量过·不做 [%s]：%s" % (_r["code"], _r.get("why") or ""))
        if d.get("dormant"):
            print("▼ 从未响过但**自检证实会响**（休眠，不是死）：%s" % ", ".join(d["dormant"]))
        if d["unregistered"]:
            print("▼ 引擎报了但目录没登记（把目录补上）：%s" % ", ".join(d["unregistered"]))
        print(d["note"])
        return 0
    if a.trend:
        t = EVO.trend(outdir) if EVO else {}
        outfile.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        print("=" * 70)
        print("自动收集台账：共 %d 轮" % t.get("runs_total", 0))
        print("=" * 70)
        for h in (t.get("history") or [])[-15:]:
            print("  %s  %s  判据 %s 个  %s" % (h["at"], h["score"], h["n_codes"], h["flags"]))
        print("-" * 70)
        print("常驻故障 %d 条（≥80%% 轮次都出现）：%s"
              % (t.get("chronic_n", 0), ", ".join(t.get("chronic") or [])[:400]))
        print("闪断故障 %d 条（只出现过一次）：%s"
              % (t.get("transient_n", 0), ", ".join(t.get("transient") or [])[:300]))
        print("逐条首见/末见/次数：")
        for k, v in sorted((t.get("per_code") or {}).items()):
            print("   %-30s 首见 %s  末见 %s  %d 次" % (k, v["first_seen"], v["last_seen"], v["runs"]))
        return 0

    if not a.quiet:
        s = rep["score"]
        pl = rep["planes"]
        print("=" * 70)
        print("全维度故障速扫  %s  ·  %.1fs  ·  %d 文件 / %.2f GB"
              % (rep["meta"]["at"], rep["meta"]["elapsed_s"], tree["total"],
                 rep["inventory"]["GB"]))
        print("=" * 70)
        print("故障：P0=%d  P1=%d  P2=%d  合计=%d   阶段耗时 %s"
              % (s["P0"], s["P1"], s["P2"], s["total"], stages))
        print("平面：P1生产 %d 文件/%.1fMB · P2数据 %.1fMB · P3残骸 %.1fMB · P4三方 %.1fMB · P6机内 %.1fMB"
              % (pl["P1_production"]["files"], pl["P1_production"]["MB"],
                 pl["P2_runtime_data"].get("MB", 0), pl["P3_job_residue"].get("MB", 0),
                 pl["P4_third_party"].get("MB", 0), pl["P6_machine_state"].get("MB", 0)))
        print("索引：跟踪 %d · 残骸 %d(%.1f%%)/%.1fMB · 脏行 %d · 入库密钥 像真的%d/夹具%d"
              % (git.get("tracked_n", 0), git.get("tracked_junk_n", 0),
                 git.get("tracked_junk_pct", 0), git.get("tracked_junk_MB", 0),
                 git.get("porcelain_n", 0), git.get("index_secret_credential_like_n", 0),
                 git.get("index_secret_fixture_like_n", 0)))
        print("依赖：声明 %d · 缺(生产) %d · 未声明 %d · 声明不可用 %d"
              % (len(deps.get("declared", [])), len(deps.get("missing_third_party", {})),
                 len(deps.get("used_not_declared", [])) if deps.get("used_not_declared")
                 else len(deps.get("used_but_not_declared", [])),
                 len(deps.get("declared_but_unimportable", []))))
        if sec_out:
            av = sec_out["report"]["av"]
            print("安全面：反病毒在位=%s · **本仓被排除=%s** · 排除 %d 条 · 远控自启 %d · IOC %d"
                  % (av.get("present"), av.get("workspace_excluded"),
                     len(av.get("exclusions") or []),
                     sum(1 for x in FAULTS if x["code"] == "PERSIST_REMOTE_CONTROL"),
                     sec_out["report"]["iocs"].get("hits_n")))
        ev = rep.get("evolution") or {}
        if ev.get("discover"):
            d = ev["discover"]
            print("进化层：台账 %s 轮 · 目录 %d 条 · **待进化 %d** · 休眠 %d · 可疑 %d · 未登记 %d"
                  % ((ev.get("trend") or {}).get("runs_total"), d["causes_total"],
                     d["todo_n"], d.get("dormant_n", 0), d.get("suspect_n", 0),
                     d["unregistered_n"]))
        if rep.get("diff"):
            d = rep["diff"]
            if d.get("not_comparable"):
                print("收敛：**不可比** —— %s（基线 %s ｜ 本轮 %s）"
                      % (d["why"], d.get("base_flags"), d.get("cur_flags")))
            else:
                print("收敛：新增 %d · 已修 %d · 未变 %d ｜ 读数变化 %d（基线 %s ｜ 口径 %s）"
                      % (len(d.get("new", [])), len(d.get("fixed", [])),
                         d.get("same_n", 0), d.get("evidence_changed_n", 0),
                         d.get("base_at"), d.get("cur_flags")))
                for ev in (d.get("evidence_changed") or [])[:5]:
                    print("       ↻ %s：%s" % (ev["code"], ev["now"][:110]))
        print("-" * 70)
        for f in sorted(FAULTS, key=lambda x: x["sev"]):
            print("[%s][%s] %-22s %s" % (f["sev"], f["plane"], f["code"], f["what"]))
            print("      证据: %s" % f["evidence"][:150])
            print("      修法: %s" % f["fix"][:150])
        print("-" * 70)
        print("没扫到什么（仪器盲区）:")
        for b in rep["blind_spots"]:
            print("  · " + b)
        print("产物: %s" % outfile)
    if a.accept:
        return 0
    if rep["score"]["P0"]:
        return 1
    if rep["score"]["P1"]:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(3)
