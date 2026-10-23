# -*- coding: utf-8 -*-
"""安全扫（security scan）· 病毒木马精准扫描 → **蒸馏成本仓原生病因语言**

与三条自检线的分工（别混）：
  selfscan / cross_scan / truth_scan = **框架自己有没有病**（路由/模块/存储/真执行）
  本文件 = **外部来的东西有没有毒**（文件/二进制/脚本/Office），并把结论翻译成**病因 + 改法**。

四台引擎（能跑哪台跑哪台，全部**如实标注**）：
  A · Defender（真 AV 特征库，本机 `MpCmdRun.exe`）—— 唯一有真实恶意特征库的一台
  B · 静态分诊（`pefile` + 标准库）—— 段熵/导入表/签名/字符串/Zone.Identifier
  C · 自研规则表（YARA **风格**，不是 YARA 引擎；装 `yara-python` 可升级）
  D · 哈希与来源（sha256 · 大小 · mtime；VirusTotal 需 key ⇒ 未配就如实说没查）

判据（**门必须能失败**）：
  ① 出结论（不是空报告）② 必带 sha256 ③ 每条命中必须带**证据片段**
  ④ **EICAR 自证门**：行业标准测试串**必须被判恶**——判不出来说明扫描器根本没在工作

    python tools/security/scan.py <path...>          # 扫文件/目录
    python tools/security/scan.py --eicar-selftest   # 自证门（造 EICAR 临时件，扫完即删）
    python tools/security/scan.py --rules            # 打印自研规则表
    python tools/security/scan.py --ledger
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import pathlib
import re
import subprocess
import sys
import time

# 🔴 2026-09-26 补：Windows 管道/重定向下 stdout 回落 GBK，emoji 一打印就崩；与 self_model.py 同一款补丁
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


WS = pathlib.Path(__file__).resolve().parents[2]
LEDGER = WS / ".security/ledger.jsonl"
MPCMDRUN = pathlib.Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Windows Defender" / "MpCmdRun.exe"

# ── 病因词表（本仓语言；与 rca.py 的 PLAYBOOK 同源）─────────────────────
MAL_CAUSES = {
    "known_malware": ("AV 特征库命中（已确认的恶意体）", "立即隔离；**不要打开**；查来源（谁给的/哪来的）；上报主人"),
    "packed_or_obfuscated": ("加壳/高度混淆（段熵高、导入极少）", "不信任；在隔离环境里跑或直接弃用；若是自研件需解释为何加壳"),
    "script_obfuscation": ("脚本混淆（-enc / 长 base64 / 拼接执行）", "解出明文再判；`-enc` 的 PowerShell 默认按可疑处理"),
    "macro_payload": ("Office 宏载荷", "禁用宏；用 oletools 提取宏源码再判；来源不可信就别开"),
    "lotl_abuse": ("LOLBin 滥用（certutil/mshta/rundll32/regsvr32/wmic 下载执行）", "看完整命令行；确认是否业务需要；否则按可疑处置"),
    "injection_capable": ("具备注入能力（VirtualAlloc+WriteProcessMemory+CreateRemoteThread）", "看是否真的是调试/安全工具；否则高度可疑"),
    "suspicious_network": ("内嵌网络指示（URL/IP/域名）", "核对这些地址；不明来源的下载地址一律不访问"),
    "unsigned_or_tampered": ("无签名/签名无效/时间戳异常", "优先只运行有有效签名的；无签名件要有来源与哈希留痕"),
    "clean": ("未见可疑（**不等于安全**：只说明这几台引擎没发现）", "照常用；但仍遵循来源纪律（provenance）"),
}

# ── C · 自研规则表（distilled：从热门项目的常见手法蒸馏，非 YARA 引擎）──────
RULES = [
    ("ps_encoded",        "high",   "script_obfuscation", rb"powershell[^\n]{0,80}-(enc|encodedcommand)", "PowerShell 编码命令"),
    ("frombase64",        "high",   "script_obfuscation", rb"FromBase64String|base64\s*-d|\[Convert\]::FromBase64", "base64 解码执行"),
    ("iex_download",      "high",   "script_obfuscation", rb"Invoke-Expression|IEX\s*\(|DownloadString|DownloadFile", "下载并执行"),
    ("certutil_dl",       "high",   "lotl_abuse",         rb"certutil(\.exe)?\s+-urlcache|certutil\s+-decode", "certutil 下载/解码"),
    ("mshta_remote",      "high",   "lotl_abuse",         rb"mshta(\.exe)?\s+https?://", "mshta 远程执行"),
    ("rundll32_js",       "high",   "lotl_abuse",         rb"rundll32(\.exe)?\s+[^\n]{0,40}(javascript|\.dll,)", "rundll32 执行"),
    ("regsvr32_scrobj",   "high",   "lotl_abuse",         rb"regsvr32(\.exe)?[^\n]{0,60}/i:?https?://|scrobj\.dll", "regsvr32 scriptlet"),
    ("wmic_exec",         "med",    "lotl_abuse",         rb"wmic(\.exe)?\s+process\s+call\s+create", "wmic 创建进程"),
    ("inject_trio",       "high",   "injection_capable",  rb"VirtualAllocEx|WriteProcessMemory|CreateRemoteThread", "注入 API"),
    ("ransom_note",       "high",   "known_malware",      rb"your files have been encrypted|decrypt.{0,20}bitcoin|README_DECRYPT", "勒索信特征"),
    ("vba_project",       "med",    "macro_payload",      rb"vbaProject|Attribute\s+VB_Name|AutoOpen|Document_Open", "Office 宏"),
    ("lnk_cmd",           "med",    "lotl_abuse",         rb"\.lnk.{0,40}cmd\.exe|\\Windows\\System32\\cmd\.exe\s+/c", "快捷方式拉 cmd"),
    ("shadow_delete",     "high",   "known_malware",      rb"vssadmin\s+delete\s+shadows|wbadmin\s+delete\s+catalog", "删卷影（勒索前置）"),
    ("net_url",           "low",    "suspicious_network", rb"https?://[A-Za-z0-9._\-]{4,}", "内嵌 URL"),
    ("net_ip",            "low",    "suspicious_network", rb"\b(?:\d{1,3}\.){3}\d{1,3}\b", "内嵌 IP"),
]
SUSP_IMPORTS = {"VirtualAlloc", "VirtualAllocEx", "WriteProcessMemory", "CreateRemoteThread",
                "SetWindowsHookEx", "GetAsyncKeyState", "URLDownloadToFile", "WinExec",
                "ShellExecuteA", "IsDebuggerPresent", "NtUnmapViewOfSection", "QueueUserAPC"}


def log(entry: dict):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    entry["at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def hashes(p: pathlib.Path):
    h = {k: hashlib.new(k) for k in ("sha256", "sha1", "md5")}
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            for x in h.values():
                x.update(chunk)
    return {k: v.hexdigest() for k, v in h.items()}


def entropy(b: bytes):
    if not b:
        return 0.0
    from collections import Counter
    c = Counter(b)
    n = len(b)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


# ── A · Defender ───────────────────────────────────────────────────────────
def engine_defender(p: pathlib.Path):
    if not MPCMDRUN.exists():
        return None, "MpCmdRun 不在（无 Defender）"
    try:
        r = subprocess.run([str(MPCMDRUN), "-Scan", "-ScanType", "3", "-File", str(p),
                            "-DisableRemediation"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    except Exception as e:
        return None, f"调用失败 {type(e).__name__}"
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    # Defender: 0 = 未发现威胁；2 = 发现威胁
    if r.returncode == 0:
        return False, "未发现威胁（returncode 0）"
    if r.returncode == 2:
        return True, f"**发现威胁**（returncode 2）{out.splitlines()[-1][:90] if out else ''}"
    return None, f"未预期返回码 {r.returncode}：{out[:90]}"


# ── B · 静态分诊 ───────────────────────────────────────────────────────────
def engine_static(p: pathlib.Path):
    hits = []
    data = p.read_bytes() if p.stat().st_size < 200 * 1024 * 1024 else b""
    head = data[:2]
    is_pe = head == b"MZ"
    if is_pe:
        try:
            import pefile
            pe = pefile.PE(str(p), fast_load=True)
            pe.parse_data_directories()
            secs = [(s.Name.rstrip(b"\x00").decode("latin1", "ignore"), s.SizeOfRawData,
                     round(entropy(s.get_data() or b""), 2)) for s in pe.sections]
            high = [s for s in secs if s[2] >= 7.2]
            if high:
                hits.append(("packed_or_obfuscated", f"高熵段 {high[:3]}（≥7.2 疑加壳/加密）"))
            imports = set()
            if hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
                for m in pe.DIRECTORY_ENTRY_IMPORT:
                    for imp in m.imports:
                        if imp.name:
                            imports.add(imp.name.decode("latin1", "ignore"))
            sus = sorted(imports & SUSP_IMPORTS)
            if len(sus) >= 3:
                hits.append(("injection_capable", f"可疑导入 {len(sus)} 个：{sus[:6]}"))
            if len(imports) <= 8 and p.stat().st_size > 100 * 1024:
                hits.append(("packed_or_obfuscated", f"导入表极小（{len(imports)} 个）但体积 {p.stat().st_size//1024}KB"))
            hits.append(("_info", f"PE 段 {len(secs)} 个 · 熵 {[s[2] for s in secs][:6]} · 导入 {len(imports)} 个"))
        except Exception as e:
            hits.append(("_info", f"PE 解析受限：{type(e).__name__}"))
    # 文本/脚本类：规则表
    text = data if data else p.read_bytes()[:4 << 20]
    for name, sev, cause, pat, desc in RULES:
        m = re.search(pat, text, re.I)
        if m:
            frag = text[max(0, m.start() - 20):m.end() + 20].decode("utf-8", "ignore").replace("\n", " ")[:80]
            hits.append((cause, f"[{sev}] {desc} · 片段「{frag}」"))
    # Zone.Identifier（Mark-of-the-Web）+ 双扩展名
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            f"Get-Item -LiteralPath '{p}' -Stream Zone.Identifier -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Stream"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        if "Zone.Identifier" in (r.stdout or ""):
            hits.append(("suspicious_network", "带 Mark-of-the-Web（来自网络下载）—— 来源需核实"))
    except Exception:
        pass
    if re.search(r"\.(pdf|doc|docx|xls|xlsx|jpg|png|txt|mp4)\.(exe|scr|bat|cmd|ps1|vbs|js)$", p.name, re.I):
        hits.append(("known_malware", f"双扩展名伪装：{p.name}"))
    return hits


# ── 签名（B 的一部分）──────────────────────────────────────────────────────
def signature_state(p: pathlib.Path):
    if p.suffix.lower() not in (".exe", ".dll", ".sys", ".ps1", ".msi"):
        return None
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            f"(Get-AuthenticodeSignature -LiteralPath '{p}').Status"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        return (r.stdout or "").strip() or None
    except Exception:
        return None


def verdict_of(causes):
    order = ["known_malware", "packed_or_obfuscated", "script_obfuscation", "macro_payload",
             "lotl_abuse", "injection_capable", "unsigned_or_tampered", "suspicious_network"]
    for c in order:
        if c in causes:
            return c
    return "clean"


def scan_one(p: pathlib.Path, quiet=False):
    hs = hashes(p)
    causes, evidence = [], []
    av_hit, av_note = engine_defender(p)
    if av_hit is True:
        causes.append("known_malware"); evidence.append(("A·Defender", av_note))
    for c, e in engine_static(p):
        if c.startswith("_"):
            evidence.append(("B·静态", e)); continue
        causes.append(c); evidence.append(("B·静态", e))
    sig = signature_state(p)
    if sig and sig not in ("Valid",):
        causes.append("unsigned_or_tampered"); evidence.append(("B·签名", f"Authenticode 状态 = {sig}"))
    elif sig:
        evidence.append(("B·签名", "签名有效"))
    causes = list(dict.fromkeys(causes))
    v = verdict_of(causes)
    if not quiet:
        print(f"\n── {p.name}  ({p.stat().st_size/1024:.1f} KB)")
        print(f"   sha256 {hs['sha256'][:32]}…")
        print(f"   A·Defender : {av_note}")
        for src, e in evidence:
            print(f"   {src:<11}: {e}")
        cn, fix = MAL_CAUSES[v]
        print(f"   ⇒ 判定【{cn}】 cause={v}")
        print(f"   ⇒ 处置：{fix}")
    ok = bool(evidence) and bool(hs["sha256"])
    log({"op": "scan", "file": p.name, "sha256": hs["sha256"], "verdict": v, "causes": causes,
         "defender": av_hit, "ok": ok})
    return {"file": str(p), "verdict": v, "causes": causes, "sha256": hs["sha256"],
            "defender": av_hit, "evidence": [e for _, e in evidence], "ok": ok}


def cmd_eicar():
    """④ 自证门：EICAR 标准测试串**必须**被判恶。判不出来 ⇒ 扫描器没在工作。"""
    eicar = (r"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*")
    p = pathlib.Path(os.environ.get("TEMP", ".")) / "dsh-gbtdh-eicar-selftest.com"
    p.write_bytes(eicar.encode())
    print("EICAR 自证门（行业标准测试串 · 47 字节 · 无害，只用来验证扫描器在工作）")
    r = scan_one(p)
    try:
        p.unlink()
        print("   （临时件已删）")
    except Exception as e:
        print(f"   ⚠️ 临时件删除失败：{type(e).__name__}（位置 {p}）")
    caught = r["causes"] != [] and r["verdict"] != "clean"
    print(f"\nS-安全门: {'✅' if caught else '❌'} "
          f"{'EICAR 被判恶 ⇒ 扫描器确实在工作' if caught else 'EICAR 没被判恶 ⇒ 扫描器形同虚设'}")
    return 0 if caught else 1


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); return
    if a[0] == "--rules":
        print(f"自研规则表（{len(RULES)} 条 · YARA 风格，非 YARA 引擎）")
        for n, sev, cause, _p, desc in RULES:
            print(f"  [{sev:<4}] {n:<18} → {cause:<22} {desc}")
        return
    if a[0] == "--ledger":
        if LEDGER.exists():
            for l in LEDGER.read_text(encoding="utf-8").strip().splitlines()[-8:]:
                print("  " + l)
        else:
            print("  （账本未落盘）")
        return
    if a[0] == "--eicar-selftest":
        sys.exit(cmd_eicar())
    targets = []
    for x in a:
        p = pathlib.Path(x)
        targets += [f for f in p.rglob("*") if f.is_file()] if p.is_dir() else ([p] if p.exists() else [])
    if not targets:
        print("没有可扫的目标"); return
    results = [scan_one(t) for t in targets]
    bad = [r for r in results if r["verdict"] != "clean"]
    print(f"\n扫了 {len(results)} 个 · 有可疑 {len(bad)} 个 · 未见可疑 {len(results)-len(bad)} 个")
    print("（'未见可疑' ≠ 安全：只说明这几台引擎没发现）")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
