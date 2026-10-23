r"""GBT小土豆V8 · 桌面壳（保留 AutoClaw customtkinter 形态）。

依赖条件（两个都要满足，缺一不可）：
  1. 所用解释器**自带 tkinter**（标准 CPython 安装包默认带；AutoClaw 自带的
     resources\python 不含，所以不要用它跑本模块）；
  2. 该解释器里装了 customtkinter 与 darkdetect。

注意：customtkinter 依赖 tkinter。**所缺的是 tkinter 时，装 customtkinter 也弹不出窗口**。
      界面起不来时不要盲装，先跑下面这条看它报告的根因（它会说明缺的是 tkinter 还是
      customtkinter，并列出本机可用的解释器）：
          python -c "import sys;sys.path.insert(0,'.');from gbt_allinone.app import main;main()"
      不要用 `python -m gbt_allinone.app`：自带解释器开启安全路径，当前目录不进 sys.path；
      或直接用仓库根目录的 launch-gui.ps1 启动（它会自动挑一个能开窗的解释器）。
"""
import json
import os
import shutil
import subprocess
import sys

from .api import list_capabilities, run_task
from .store import query_log
# 🔴 事故对策（2026-09-25）：改走容错取表层，别让注册表被并发重写时把 GUI 也一起拖死
from .caps_tables import DISABLED_CAPS, UNIMPLEMENTED_CAPS

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

try:
    import tkinter as _tk  # noqa: F401
    _HAS_TK, _TK_ERR = True, ""
except Exception as e:  # noqa: BLE001
    _HAS_TK, _TK_ERR = False, str(e)

try:
    import customtkinter as ctk
    _HAS_UI = _HAS_TK
    _UI_ERR = "" if _HAS_TK else "tkinter 不可用"
except Exception as e:  # noqa: BLE001
    _HAS_UI = False
    _UI_ERR = str(e)


# 只 import 不足以判定：Tcl 运行时缺失时 import 能过、建窗口才报 TclError。
# 所以真正建一个窗口（withdraw 不入屏）再销毁，用退出码判定。
_PROBE_CODE = ("import tkinter,customtkinter;"
               "w=tkinter.Tk();w.withdraw();w.update();w.destroy()")


def _probe(py):
    """该解释器是否真的能同时用 tkinter 与 customtkinter 开出窗口。"""
    try:
        r = subprocess.run([py, "-c", _PROBE_CODE],
                           capture_output=True, timeout=60, creationflags=_NO_WINDOW)
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def _candidates():
    """列出可能可用的解释器；先问 py 启动器，再扫常见安装位置。"""
    out = []
    exe = shutil.which("py")
    if exe:
        try:
            r = subprocess.run([exe, "-0p"], capture_output=True, text=True,
                               timeout=20, creationflags=_NO_WINDOW)
            for line in (r.stdout or "").splitlines():
                for tok in line.replace("*", " ").split():
                    if tok.lower().endswith(".exe"):
                        out.append(tok)
        except Exception:  # noqa: BLE001
            pass
    for d in (r"C:\Python310", r"C:\Python311", r"C:\Python312", r"C:\Python313",
              os.path.expanduser(r"~\AppData\Local\Python"),
              os.path.expanduser(r"~\AppData\Roaming\uv\python")):
        if os.path.isdir(d):
            for cur, _dirs, files in os.walk(d):
                for f in files:
                    if f.lower() == "python.exe":
                        out.append(os.path.join(cur, f))
    seen, uniq = set(), []
    me = os.path.normcase(os.path.abspath(sys.executable))
    for c in out:
        if not os.path.isfile(c):
            continue
        n = os.path.normcase(os.path.abspath(c))
        if n == me or n in seen:
            continue
        seen.add(n)
        uniq.append(c)
    return uniq


def find_gui_python(limit=12):
    """返回本机一个真能开窗的解释器绝对路径；找不到返回 None。"""
    for c in _candidates()[:limit]:
        if _probe(c):
            return c
    return None


def _unsupported_hint():
    """缺依赖时给出根因与可执行的解决办法，而不是一句"去 pip install"。"""
    print("桌面壳无法启动。")
    print("  当前解释器 : %s" % sys.executable)
    print("  tkinter    : %s%s" % ("正常" if _HAS_TK else "缺失",
                                   "" if _HAS_TK else "   <-- 根因在这里"))
    print("  customtkinter: %s" % ("正常" if _HAS_UI else "不可用 (%s)" % (_UI_ERR[:80] or "未知原因")))
    if not _HAS_TK:
        print("  说明: customtkinter 依赖 tkinter。缺 tkinter 时，再怎么 pip install 也弹不出窗口。")
        print("        请换一个自带 tkinter 的解释器，不要用上面这个。")
    found = find_gui_python()
    if found:
        print("  本机可用解释器: %s" % found)
        print("  启动方式（在 %s 下执行）:" % ROOT_SHOWN)
        print("    \"%s\" -c \"import sys;sys.path.insert(0,'.');from gbt_allinone.app import main;main()\"" % found)
    else:
        print("  本机未找到同时具备 tkinter 与 customtkinter 的解释器。")
        print("  下一步: 安装 Python 官方版(勾选 tcl/tk)，再 pip install customtkinter darkdetect。")
    print("  或直接运行启动器: launch-gui.ps1")
    print("  只用命令行也可以（本机不能用 -m 形式，见下）:")
    print("    python -c \"import sys;sys.path.insert(0,'.');from gbt_allinone.cli import main;main(['list'])\"")
    print("  注: -m gbt_allinone 在本机不可用，因为解释器开启安全路径，当前目录不进 sys.path。")
    return 1


ROOT_SHOWN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_gui():
    if not _HAS_UI:
        return _unsupported_hint()
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    app = ctk.CTk()
    app.title("GBT小土豆V8 · 独立私人框架")
    app.geometry("900x560")

    frame = ctk.CTkFrame(app)
    frame.pack(fill="both", expand=True, padx=12, pady=12)

    title = ctk.CTkLabel(frame, text="GBT小土豆V8 · 统一接口 · 独立私人框架 · 与任何企业公司无关",
                         font=("", 18, "bold"))
    title.pack(pady=(12, 6))

    caps = list_capabilities(filter_dangerous=True)
    cap_names = [f"{c['name']} [{c['domain']}]" for c in caps]

    output = ctk.CTkTextbox(frame, width=560, height=300)
    output.pack(side="right", padx=12, pady=12, fill="both", expand=True)

    left = ctk.CTkFrame(frame)
    left.pack(side="left", padx=12, pady=12, fill="y")

    def on_run():
        out = []
        for name in cap_names:
            kind = name.split(" [")[0]
            r = run_task(kind, {"text": "GBT小土豆V8联调"})
            out.append(json.dumps(r, ensure_ascii=False))
        output.delete("1.0", "end")
        output.insert("1.0", "\n".join(out))

    def on_audit():
        output.delete("1.0", "end")
        rows = query_log(limit=30)
        output.insert("1.0", "\n".join(
            f"{r['iso']}  {r['event']:<7} {json.dumps(r['meta'], ensure_ascii=False)}"
            for r in rows))

    btn_run = ctk.CTkButton(left, text="运行全部良性能力", command=on_run)
    btn_run.pack(pady=6)
    btn_audit = ctk.CTkButton(left, text="查看审计日志", command=on_audit)
    btn_audit.pack(pady=6)

    def on_ghost():
        r = run_task("ghost_guard", {})
        output.delete("1.0", "end")
        output.insert("1.0", json.dumps(r, ensure_ascii=False, indent=2))

    def on_services():
        r = run_task("svc_inspect", {})
        output.delete("1.0", "end")
        body = r.get("gbt_result", {}).get("result", {})
        lines = [f"服务巡检: {body.get('up')}/{body.get('total')} 在线"]
        for name, s in (body.get("services") or {}).items():
            mark = "●" if s["up"] else "○"
            lines.append(f"  {mark} {name:<22} {s['host']}:{s['port']:<6} [{s.get('owner','')}]")
        output.delete("1.0", "end")
        output.insert("1.0", chr(10).join(lines))

    def on_workflows():
        r = run_task("wf_status", {})
        output.delete("1.0", "end")
        output.insert("1.0", json.dumps(r, ensure_ascii=False, indent=2))

    btn_ghost = ctk.CTkButton(left, text="防复发检测", command=on_ghost, fg_color="#2563eb", hover_color="#1d4ed8")
    btn_ghost.pack(pady=6)
    btn_svc = ctk.CTkButton(left, text="服务巡检", command=on_services, fg_color="#2563eb", hover_color="#1d4ed8")
    btn_svc.pack(pady=6)
    btn_wf = ctk.CTkButton(left, text="工作流记录", command=on_workflows, fg_color="#2563eb", hover_color="#1d4ed8")
    btn_wf.pack(pady=6)

    def on_longrun():
        r = run_task("lr_status", {})
        output.delete("1.0", "end")
        body = r.get("gbt_result", {}).get("result", {})
        p = body.get("progress", {})
        lines = [f"长程任务: 共{p.get('total',0)} 完成{p.get('done',0)} 待办{p.get('pending',0)} "
                 f"失败{p.get('failed',0)} 卡住{p.get('stalled',0)}"]
        for t in (body.get("tasks") or [])[:20]:
            mark = {"done": "✓", "failed": "✗", "stalled": "⚠"}.get(t.get("status"), "…")
            lines.append(f"  {mark} {t.get('task_id')} [{t.get('priority','m')}] {t.get('description','')[:30]} "
                         f"({t.get('attempts',0)}次)")
        output.delete("1.0", "end")
        output.insert("1.0", chr(10).join(lines))

    def on_longrun_tick():
        r = run_task("lr_tick", {"max_tasks": 3})
        output.delete("1.0", "end")
        output.insert("1.0", json.dumps(r, ensure_ascii=False, indent=2))

    btn_lr = ctk.CTkButton(left, text="长程任务面板", command=on_longrun, fg_color="#7c3aed", hover_color="#6d28d9")
    btn_lr.pack(pady=6)
    btn_lrt = ctk.CTkButton(left, text="推进任务图", command=on_longrun_tick, fg_color="#7c3aed", hover_color="#6d28d9")
    btn_lrt.pack(pady=6)

    def on_selfscan():
        r = run_task("selfscan", {})
        output.delete("1.0", "end")
        body = r.get("gbt_result", {}).get("result", {})
        lines = [f"框架体检: {body.get('verdict')} | 能力 {body.get('capabilities_total')} 项"]
        for f_ in body.get("findings", []):
            lines.append(f"  · {f_}")
        if not body.get("findings"):
            lines.append("  · 五维全过，无断连无损坏")
        output.delete("1.0", "end")
        output.insert("1.0", chr(10).join(lines))

    btn_scan = ctk.CTkButton(left, text="框架体检", command=on_selfscan, fg_color="#dc2626", hover_color="#b91c1c")
    btn_scan.pack(pady=6)

    def on_brain_health():
        r = run_task("brain_health", {})
        output.delete("1.0", "end")
        body = r.get("gbt_result", {}).get("result", {})
        lines = [f"大脑执行层五维健康: {body.get('healthy_dims')}/{body.get('total_dims')} · 评分 {body.get('score')}"]
        for k, v in body.get("dims", {}).items():
            mark = "✓" if v.get("ok") else "✗"
            lines.append(f"  {mark} {k}: {v.get('detail', '')[:60]}")
        output.insert("1.0", chr(10).join(lines))

    btn_brain = ctk.CTkButton(left, text="大脑五维健康", command=on_brain_health, fg_color="#0ea5e9", hover_color="#0284c7")
    btn_brain.pack(pady=6)

    def on_inventory():
        r = run_task("inventory", {})
        output.delete("1.0", "end")
        body = r.get("gbt_result", {}).get("result", {})
        dv = body.get("dual_view", {})
        lines = [f"全息盘点: {body.get('verdict')}"]
        for k, v in dv.items():
            lines.append(f"  · {k}: {v}")
        foreign = body.get("items", {}).get("foreign", [])
        if foreign:
            lines.append(f"  · 异物清单: {foreign[:10]}")
        output.insert("1.0", chr(10).join(lines))

    btn_inv = ctk.CTkButton(left, text="全息盘点", command=on_inventory, fg_color="#059669", hover_color="#047857")
    btn_inv.pack(pady=6)

    def on_qiankun():
        r = run_task("mirror_status", {})
        output.delete("1.0", "end")
        body = r.get("gbt_result", {}).get("result", {})
        lines = [f"镜像多维度空间: 现实 v{body.get('reality', {}).get('version', 0)} · 零漂移 {'✓' if body.get('clean') else '✗'}"]
        lines.append(f"  · 镜像维度: {body.get('dimension', {}).get('files', 0)} 文件")
        lines.append(f"  · 生产现实: {body.get('reality', {}).get('files', 0)} 文件")
        drift = body.get("reality_drift", [])
        if drift:
            lines.append(f"  · 现实漂移 {len(drift)} 处: {drift[:5]}")
        output.insert("1.0", chr(10).join(lines))

    btn_qk = ctk.CTkButton(left, text="镜像空间状态", command=on_qiankun, fg_color="#7c2d12", hover_color="#9a3412")
    btn_qk.pack(pady=6)

    def on_tentacle():
        r = run_task("tentacle_status", {})
        output.delete("1.0", "end")
        body = r.get("gbt_result", {}).get("result", {})
        d = body.get("diagnose", {})
        cov = body.get("coverage", {})
        lines = ["触手就绪: %s | 能力 %s 项 | 邻域 %s 个" % (d.get("ok"), d.get("manifest_methods"), cov.get("total_domains"))]
        for dep, info in (d.get("deps") or {}).items():
            mark = "●" if info.get("ok") else "○"
            lines.append("  %s %-14s %s" % (mark, dep, info.get("role", "")))
        lines.append("  · 全部能力经 tentacle 能力调用（清单见 tentacle_manifest）")
        output.delete("1.0", "end")
        output.insert("1.0", chr(10).join(lines))

    btn_tent = ctk.CTkButton(left, text="触手面板", command=on_tentacle, fg_color="#0d9488", hover_color="#0f766e")
    btn_tent.pack(pady=6)

    lbl = ctk.CTkLabel(left, text=f"良性能力 {len(caps)} 个\n登记未实现 {len(UNIMPLEMENTED_CAPS)} 个（禁止已解开）",
                       justify="left")
    lbl.pack(pady=6)

    output.insert("1.0", "桌面壳就绪。点击按钮运行/查看审计。")
    app.mainloop()
    return 0


def main():
    return run_gui()


if __name__ == "__main__":
    sys.exit(main())
