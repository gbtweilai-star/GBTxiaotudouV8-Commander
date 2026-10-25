# gbt-capability: recon_distill
"""蒸馏件：看懂一个程序（静态指纹 · 引擎现读 · 证据契约 · 复刻义务现算）。

## 这不是外挂 —— 这是「吞天」蒸出来的**我们自己的**能力
主人令（2026-10-12，逐字）：「我们吞噬都是加入蒸馏提炼出契合我们的能力」
「蒸馏提炼出契合我们的能力才是我们的」。

吞入件是 morluto/rea（rea.tools · npm rea-agents 6.4.0 · MIT）；**接入端**是隔壁 rea_reverse
（把活交给外部引擎、起了个 npx）。**本位不是接入端**：不联网、不起进程、不装引擎，只把 REA 那套
**方法论**提炼成我们自己的判据与读数 —— 所以它敢零作用域（本文件没有 subprocess / urllib / 写盘）。

## 蒸馏出四条（每条都指回 REA 的原话，见 op=provenance）
1. **证据契约**：结论必须带证据，**并且明说局限与未知**。
   REA 原话：results include the evidence and limitations behind each conclusion.
   → 我们：op=evidence —— 四件齐（claim / evidence / unknown / limitation）才算过，缺件当场拒，
     而且「无」也要写出来，空着 = 没交代。
2. **静态优先、不跑目标**。REA 原话：Static JavaScript and .NET inspection read the supplied files
   without running the application.
   → 我们：op=fingerprint 只读字节，**不执行目标**。
3. **确定性义务台账**。REA 有 build-reconstruction-obligation-ledger —
   Generate a deterministic Evidence-backed reconstruction obligation ledger。
   → 我们：op=obligations —— **现算不落盘**：看懂/复刻这个产物还缺哪些证据，每条带判据。
4. **引擎可换、能力与副作用要声明**。REA 的 provider 抽象（Ghidra / IDA / Hopper …）。
   → 我们：op=engines —— 现读本机有哪些引擎、缺哪个；缺就如实说缺（不假装能做 native）。

## 边界（和隔壁分清楚，别当同一件）
- rea_reverse = **接入端**（外部引擎那条线：胶囊 / 命令名 / cli 交给 desktop_commander 跑）。
- recon_distill = **蒸馏件**（我们自己的判据与读数；不依赖前者，也不依赖网络与引擎）。

op=fingerprint / engines / evidence / obligations / provenance / where
"""
from __future__ import annotations

import hashlib
import importlib.util
import shutil
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

_MAGIC = (
    (bytes([0x4D, 0x5A]), "PE / Windows 可执行或 DLL", "native"),
    (bytes([0x7F]) + b"ELF", "ELF / Linux-Unix 可执行", "native"),
    (bytes([0xCA, 0xFE, 0xBA, 0xBE]), "Java class 或 Mach-O fat", "jvm-or-macho"),
    (bytes([0xFE, 0xED, 0xFA, 0xCE]), "Mach-O 32", "native"),
    (bytes([0xFE, 0xED, 0xFA, 0xCF]), "Mach-O 64", "native"),
    (b"PK" + bytes([3, 4]), "ZIP 家族（asar / apk / jar / 办公件）", "zip"),
    (bytes([0x00]) + b"asm", "WebAssembly", "wasm"),
    (b"SQLite format 3", "SQLite 数据库", "data"),
    (b"%PDF", "PDF", "doc"),
    (bytes([0x89]) + b"PNG", "PNG 图", "image"),
    (bytes([0x1F, 0x8B]), "gzip 压缩流", "archive"),
)

_ENGINES = (
    ("ghidra", ("analyzeHeadless", "ghidraRun"), "反汇编/反编译（native）"),
    ("ida", ("ida64", "ida", "idat64"), "反汇编/反编译（native）"),
    ("hopper", ("hopper",), "反汇编（Hopper）"),
    ("jadx", ("jadx", "jadx-cli"), "Android APK 反编译"),
    ("apktool", ("apktool",), "Android 资源解码"),
    ("binwalk", ("binwalk",), "固件/容器切分"),
    ("unblob", ("unblob",), "固件/容器切分"),
    ("wabt", ("wasm2wat", "wat2wasm"), "WASM 文本化"),
    ("adb", ("adb",), "安卓设备抓取"),
    ("gdb", ("gdb",), "Linux 进程/崩溃捕获"),
    ("mitmdump", ("mitmdump",), "网络抓包"),
    ("node", ("node",), "JS / Electron 静态分析（REA 那条路要用）"),
    ("npx", ("npx",), "跑 npm 上的分析器（含 rea-agents）"),
)
_PY_PKGS = (("pwn", "pwntools", "ELF 布局 / 崩溃解析"), ("elftools", "pyelftools", "ELF 解析"))

# zip 家族里见到就说明它是什么的特征条目
_ZIP_MARKS = {
    "app.asar": "Electron 打包体（asar）",
    "AndroidManifest.xml": "Android 应用（APK）",
    "classes.dex": "Android 字节码",
    "[Content_Types].xml": "Office 文档（docx/xlsx/pptx）",
    "package.json": "Node 包 / JS 工程",
    "META-INF/MANIFEST.MF": "JAR / Java 包",
    "wasm": "WebAssembly 包体",
}


def _sha256(path: Path, limit_mb: int = 8) -> dict:
    h = hashlib.sha256()
    read = 0
    cap = max(1, int(limit_mb)) * 1024 * 1024
    with open(path, "rb") as fh:
        while read < cap:
            chunk = fh.read(min(1024 * 1024, cap - read))
            if not chunk:
                break
            h.update(chunk)
            read += len(chunk)
    return {"sha256_16": h.hexdigest()[:16], "hashed_bytes": read, "partial": read < path.stat().st_size}


def _look(path: Path) -> dict:
    if not path.exists():
        return {"ok": False, "error": "路径不存在：" + str(path)}
    if path.is_dir():
        entries = sorted(p.name for p in path.iterdir())[:40]
        return {"ok": True, "kind": "目录", "entries_top": len(entries), "entries": entries}
    size = path.stat().st_size
    head = path.read_bytes()[:16] if size else b""
    kind, family = "未知（无匹配魔数）", "unknown"
    for magic, label, fam in _MAGIC:
        if head.startswith(magic):
            kind, family = label, fam
            break
    info = {"ok": True, "kind": kind, "family": family, "size": size,
            "head_hex": head[:12].hex(), "sha": _sha256(path)}
    if family == "zip":
        try:
            import zipfile
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
            info["zip_entries"] = len(names)
            marks = sorted({v for k, v in _ZIP_MARKS.items() if any(n == k or n.endswith("/" + k) for n in names)})
            info["zip_marks"] = marks
            if marks:
                info["kind"] = kind + " ⇒ " + " / ".join(marks)
        except Exception as exc:                                   # noqa: BLE001
            info["zip_error"] = "%s: %s" % (type(exc).__name__, str(exc)[:80])
    return info


def engines(**_kw) -> dict:
    """现读本机分析引擎：在不在 PATH、能不能顶 native 那一路。"""
    rows, have, miss = [], [], []
    for name, cmds, why in _ENGINES:
        found = next((shutil.which(c) for c in cmds if shutil.which(c)), "")
        rows.append({"引擎": name, "在": bool(found), "path": found, "用途": why})
        (have if found else miss).append(name)
    pkgs = []
    for mod, label, why in _PY_PKGS:
        ok = importlib.util.find_spec(mod) is not None
        pkgs.append({"包": label, "在": ok, "用途": why})
        (have if ok else miss).append(label)
    native = [r["引擎"] for r in rows if r["在"] and r["引擎"] in ("ghidra", "ida", "hopper")]
    return {"ok": True, "op": "engines", "有": have, "缺": miss,
            "native_引擎": native, "native_能做吗": bool(native),
            "表": rows, "python 包": pkgs,
            "口径": "「缺」= PATH 上没有；缺 native 引擎就只能走 JS-Electron / .NET / 网页 / 包与资源那几路"
                    "（REA 自己也这么说：Static JavaScript analysis needs no native analysis engine）"}


def fingerprint(path: str = "", hash_mb: int = 8, **_kw) -> dict:
    """静态指纹：只读字节，**不执行目标**（蒸馏自 REA 的 static-first 口径）。"""
    if not path:
        return {"ok": False, "op": "fingerprint", "fail_closed": True, "error": "要给 path",
                "例": {"path": "C:/Windows/System32/notepad.exe"}}
    p = Path(str(path)).expanduser()
    info = _look(p)
    if not info.get("ok"):
        return {"ok": False, "op": "fingerprint", "path": str(p), **info}
    return {"ok": True, "op": "fingerprint", "path": str(p), "执行": "无（只读字节；没运行目标）", **info}


def evidence(claim: str = "", evidence: str = "", unknown: str = "", limitation: str = "", **_kw) -> dict:
    """证据契约：四件齐才算过；「无」也要写出来，空着 = 没交代。"""
    fields = {"claim": str(claim).strip(), "evidence": str(evidence).strip(),
              "unknown": str(unknown).strip(), "limitation": str(limitation).strip()}
    missing = [k for k, v in fields.items() if not v]
    return {"ok": not missing, "op": "evidence", "fail_closed": bool(missing),
            "缺件": missing, "fields": fields,
            "口径": "蒸馏自 REA：results include the evidence and limitations behind each conclusion ⇒ "
                    "结论必须带证据，**并且明说局限与未知**；没有未知也要写「无」，空着就是没交代"}


def obligations(path: str = "", **_kw) -> dict:
    """复刻义务**现算**（确定性、不落盘）：要看懂/复刻这个产物，必须能拿出哪些证据。"""
    if not path:
        return {"ok": False, "op": "obligations", "fail_closed": True, "error": "要给 path"}
    p = Path(str(path)).expanduser()
    info = _look(p)
    if not info.get("ok"):
        return {"ok": False, "op": "obligations", "path": str(p), **info}
    fam = info.get("family") or "unknown"
    zip_ok = bool(info.get("zip_entries"))
    eng = engines()
    native_ok = eng["native_能做吗"]
    rows = [
        {"义务": "① 认出这是什么产物", "判据": "魔数 + 大小 + sha256 现读得到",
         "现在满足": bool(info.get("head_hex")), "靠谁": "本位（op=fingerprint）"},
        {"义务": "② 说清有哪些组成部分", "判据": "容器能列条目 / 引擎能列段表",
         "现在满足": bool(zip_ok) or native_ok,
         "靠谁": "本位（zip 家族本地可列）" if zip_ok else "要 native 引擎（现在缺）"},
        {"义务": "③ 说清它按什么规则做事", "判据": "反汇编/反编译或源码可读",
         "现在满足": native_ok or fam in ("zip", "unknown"),
         "靠谁": "引擎（Ghidra/IDA/Hopper）或静态读源码"},
        {"义务": "④ 每条结论都带证据并明说局限", "判据": "op=evidence 四件齐",
         "现在满足": True, "靠谁": "本位（判据在本地，不靠引擎）"},
        {"义务": "⑤ 能做出等价物并测它", "判据": "③ 与 ④ 都齐，且有可回放的测试",
         "现在满足": False, "靠谁": "要人定的验收判据（本位只列义务，不代判）"},
    ]
    return {"ok": True, "op": "obligations", "path": str(p), "family": fam,
            "义务": rows, "还缺": [r["义务"] for r in rows if not r["现在满足"]],
            "本机引擎": {"native": eng["native_引擎"], "缺": eng["缺"]},
            "口径": "蒸馏自 REA 的 reconstruction obligation ledger —— **确定性**：同样的输入给同样的义务表；"
                    "本位只**列**义务与判据，不代判「做完了」"}


def provenance(**_kw) -> dict:
    """蒸馏出处：每条落成哪个 op、来自 REA 的哪句原话（可复核，不靠回忆）。"""
    return {"ok": True, "op": "provenance", "kind": "recon_distill",
            "吞入件": {"repo": "morluto/rea", "site": "https://rea.tools/", "npm": "rea-agents 6.4.0",
                       "license": "MIT", "胶囊": "gbt_allinone/store/devoured/devoured_morluto_rea/"},
            "蒸馏映射": [
                {"REA 原话/出处": "results include the evidence and limitations behind each conclusion（README：Analysis runs locally …）",
                 "落成": "op=evidence（四件齐才算过）"},
                {"REA 原话/出处": "Static JavaScript and .NET inspection read the supplied files without running the application（README：Process behavior 段）",
                 "落成": "op=fingerprint（只读字节，不执行目标）"},
                {"REA 原话/出处": "build-reconstruction-obligation-ledger — Generate a deterministic Evidence-backed reconstruction obligation ledger（rea --help）",
                 "落成": "op=obligations（确定性、现算、不落盘）"},
                {"REA 原话/出处": "Native analysis can use an existing Hopper, Ghidra, or IDA installation（README：Setup 段）",
                 "落成": "op=engines（引擎现读 + 缺件如实报）"},
                {"REA 原话/出处": "compare two canonical Evidence bundles（rea --help）",
                 "落成": "**未蒸馏**（如实标：我们暂时没有两份证据包可比 —— 没做就不写）"},
            ],
            "边界": "接入端 ≡ rea_reverse（外部引擎那条线）；本位 ≡ 蒸馏件（我们自己的判据与读数）",
            "口径": "蒸馏 = 把外面的方法论变成我们自己的判据；**没蒸出来的如实体现在「未蒸馏」那一行**"}


def where(**_kw) -> dict:
    return {"ok": True, "op": "where", "kind": "recon_distill", "tentacle": "recon_distill",
            "entry": "run_task('recon_distill', {'op': …})",
            "ops": ["fingerprint", "engines", "evidence", "obligations", "provenance", "where"],
            "files": {"handler": "gbt_allinone/tools/recon_distill.py",
                      "胶囊": "gbt_allinone/store/devoured/devoured_morluto_rea/"},
            "scopes": "零作用域（只读 + 纯算：无 subprocess / 无 urllib / 无写盘）",
            "contract": [
                {"op": "fingerprint", "params": "path / hash_mb", "returns": "静态指纹 + 家族判定（不执行目标）"},
                {"op": "engines", "params": "无", "returns": "本机分析引擎现读 + 缺件"},
                {"op": "evidence", "params": "claim / evidence / unknown / limitation", "returns": "四件齐才算过"},
                {"op": "obligations", "params": "path", "returns": "复刻义务现算（确定性，不落盘）"},
                {"op": "provenance", "params": "无", "returns": "每条蒸馏自 REA 哪句原话、落成哪个 op"},
            ]}


_OPS = {"fingerprint": fingerprint, "engines": engines, "evidence": evidence,
        "obligations": obligations, "provenance": provenance, "where": where}
_ALLOWED = {"fingerprint": {"path", "hash_mb"}, "engines": set(), "evidence": {"claim", "evidence", "unknown", "limitation"},
            "obligations": {"path"}, "provenance": set(), "where": set()}


def run_op(op: str = "where", **params) -> dict:
    op = (op or "where").strip().lower()
    fn = _OPS.get(op)
    if fn is None:
        return {"ok": False, "op": op, "fail_closed": True, "error": "未知 op：" + op,
                "ops": sorted(_OPS), "how": "run_task('recon_distill', {'op': …})"}
    extra = set(params) - _ALLOWED[op]
    if extra:
        return {"ok": False, "op": op, "fail_closed": True,
                "error": "不认的参数：" + str(sorted(extra)), "allowed": sorted(_ALLOWED[op])}
    return fn(**params)
