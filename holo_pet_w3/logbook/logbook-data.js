/* GBT小土豆V8 · 记录本数据件 —— **生成产物**，由 logbook.py render 覆盖，不许手改。
 * 重生成：py -3.14 tools/codex-scripts/logbook.py render
 * 口径：只追加 + 自链哈希；数字全部现算自 state/logbook.jsonl。 */
window.GBT_LOGBOOK = {
 "generated_at": "2026-11-06T05:01:24+08:00",
 "regen": "py -3.14 tools/codex-scripts/logbook.py render",
 "source": "state/logbook.jsonl（只追加 · 自链哈希）",
 "chain": {
  "ok": true,
  "detail": "链自洽：4 条记录，末条 hash=sha256:ee323ade1a210e6",
  "records": 4
 },
 "totals": {
  "records": 4,
  "scans": 0,
  "changes": 3,
  "decisions": 0,
  "delivers": 1
 },
 "scans": [],
 "records": [
  {
   "n": 1,
   "ts": "2026-11-06T04:41:13+08:00",
   "kind": "change",
   "actor": "codex",
   "what": "AI 打印 + 审美收尾：app.js 逐字打印、仪表盘改版面、<i> 归还在语义、taste_guard 两处假红修掉",
   "where": [
    "holo_pet_w3/console/app.js",
    "holo_pet_w3/console/app.css",
    "holo_pet_w3/console/index.html",
    "gbt_allinone/tentacle/taste_guard.py",
    "tools/codex-scripts/ledger-refresh.py"
   ],
   "hash": "sha256:ba848329e4c16e6",
   "prev": "genesis"
  },
  {
   "n": 2,
   "ts": "2026-11-06T05:01:18+08:00",
   "kind": "change",
   "actor": "codex",
   "what": "对话过程行拆成扫描/工具/回执/回答四段 + 进行中骨架（真实计时）+ 失败分支同款打印；服务端分报 ms_route/ms_run",
   "where": [
    "holo_pet_w3/console/app.js",
    "holo_pet_w3/console/app.css",
    "tools/console-server.py",
    "gbt_allinone/tests/test_console_chat_print.py"
   ],
   "hash": "sha256:8fe8f7b4e5fc8b3",
   "prev": "sha256:ba848329e4c16e6"
  },
  {
   "n": 3,
   "ts": "2026-11-06T05:01:24+08:00",
   "kind": "change",
   "actor": "codex",
   "what": "修屏幕采集自愈：mss 复用实例 DC 失效后永久 BitBlt failed（长驻服务 2/2 失败 / 同刻新进程 200ms 成功），改为失败即 _mss_drop() 重建再试一次，回执标 mss_recovered",
   "where": [
    "gbt_allinone/tentacle/omni_core.py"
   ],
   "hash": "sha256:23ad351b735fdf8",
   "prev": "sha256:8fe8f7b4e5fc8b3"
  },
  {
   "n": 4,
   "ts": "2026-11-06T05:01:24+08:00",
   "kind": "deliver",
   "actor": "codex",
   "what": "CHANGELOG 第三十八批 + 前端/服务端/采集三处推产品（payload sha 已核）+ 服务重启 pid 10604",
   "where": [
    "CHANGELOG.md"
   ],
   "hash": "sha256:ee323ade1a210e6",
   "prev": "sha256:23ad351b735fdf8"
  }
 ]
};
