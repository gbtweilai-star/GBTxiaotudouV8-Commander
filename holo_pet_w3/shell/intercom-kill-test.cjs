/* 单元级验证：`child.kill()` 能不能真的停掉对讲子进程（含 py.exe 派生的真解释器）
 *
 * ## 要回答的问题
 * `main.cjs` 起对讲用的是 `spawn(PETS_PY_EXE, ["-3.10", intercom.py, "watch"])`，
 * 而 `PETS_PY_EXE` = **`py`（Python 启动器）**。启动器会再派生一个真解释器。
 * ⇒ **`child.kill()` 只杀父**时，python.exe 可能变孤儿**继续开着麦克风**。
 *   页面上一切正常（状态说"未在听"）—— 这就是最典型的假绿，也是主人那句
 *   「关闭她也跟着关闭」真正的风险点。
 *
 * ## 判据（量进程，不信自述）
 *   ① 起之前：命令行含 intercom.py 的进程 = 0
 *   ② 起来后：≥ 1
 *   ③ `child.kill()` 之后等 3 秒：**回到 0** ← 这条不过就是真缺陷
 *
 * 用纯 node 跑（不需要 Electron）：`node holo_pet_w3/shell/intercom-kill-test.cjs`
 * 报告走 stdout + 落盘 `.scratch/_intercom_kill.json`（Electron 那边 stdout 不回传的坑，这里没有）。
 */
"use strict";
const path = require("path");
const fs = require("fs");
const { spawn, execFileSync } = require("child_process");

const ROOT = path.resolve(__dirname, "..", "..");
const JS = path.join(ROOT, "tools", "codex-scripts", "intercom.py");
const OUT = path.join(ROOT, ".scratch", "_intercom_kill.json");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* 🔴 第 1 版这个查询**把自己也算进去了**：探针命令行里含 `*intercom.py*` 这个字面量，
    于是"存活 1 个"其实是 PowerShell 探针本身 ⇒ 差点把 PASS 判成"杀不干净"。
    ⇒ 必须同时按**进程名**过滤（只认 py.exe / python*），把探针排除掉。 */
const Q = "(Get-CimInstance Win32_Process | Where-Object { "
        + "($_.Name -eq 'py.exe' -or $_.Name -like 'python*') "
        + "-and $_.CommandLine -like '*intercom.py*' } "
        + "| Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress)";

function procs() {
  try {
    const out = execFileSync("powershell", ["-NoProfile", "-Command", Q],
                             { encoding: "utf8", timeout: 25000 }).trim();
    if (!out) return [];
    const j = JSON.parse(out);
    return (Array.isArray(j) ? j : [j]).map((p) => ({
      pid: p.ProcessId, ppid: p.ParentProcessId,
      cmd: String(p.CommandLine || "").slice(0, 110),
    }));
  } catch (e) {
    return [{ error: String(e).slice(0, 140) }];
  }
}

(async () => {
  const rep = { steps: [] };
  const before = procs();
  rep.steps.push({ step: "① 起之前", count: before.length, procs: before });

  const child = spawn("py", ["-3.10", JS, "watch", "--jsonl", "--seconds", "3"],
                      { cwd: ROOT, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
  rep.child_pid = child.pid;
  await sleep(5000);                                   // 让它真起来并跑一两轮

  const during = procs();
  rep.steps.push({ step: "② 监听中", count: during.length, procs: during });

  child.kill();                                        // ← 就是 main.cjs 现在用的那一句
  await sleep(3000);

  let after = procs();
  rep.steps.push({ step: "③ child.kill() 之后 3s", count: after.length, procs: after });

  /* 若仍有存活：这就是真缺陷 —— 顺手验一下按**进程树**杀能不能清干净 */
  rep.verdict = (before.length === 0 && during.length >= 1 && after.length === 0)
    ? "✅ child.kill() 就够了：三条判据全过（起前 0 · 中 ≥1 · kill 后 0）"
    : "❗**child.kill() 杀不干净**：kill 后仍有 " + after.length + " 个存活（孤儿解释器，麦克风没关）";

  if (after.length) {
    rep.tree_kill = [];
    for (const p of after) {
      try {
        execFileSync("taskkill", ["/PID", String(p.pid), "/T", "/F"],
                     { encoding: "utf8", timeout: 15000 });
        rep.tree_kill.push({ pid: p.pid, killed: true });
      } catch (e) {
        rep.tree_kill.push({ pid: p.pid, killed: false, err: String(e).slice(0, 90) });
      }
    }
    await sleep(1500);
    const after2 = procs();
    rep.steps.push({ step: "④ taskkill /T /F 之后", count: after2.length, procs: after2 });
    rep.tree_kill_works = after2.length === 0;
  }

  fs.writeFileSync(OUT, JSON.stringify(rep, null, 1), "utf8");
  console.log(JSON.stringify(rep, null, 1));
  process.exit(rep.verdict.startsWith("✅") ? 0 : 1);
})();
