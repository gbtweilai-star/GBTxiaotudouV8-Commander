# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""GBT小土豆V8 · 外源情报检索引擎（last30days 同化件）。

同化自 MIT 许可的上游 `last30days`（见 `ATTRIBUTION.md` + `LICENSE`）。
本包是**框架原生层**，不是外部技能 —— 由 `gbt_allinone.topic_watch` 的
engine 面调用，与 95 个 caps 走同一套注册与判据。

调用入口：
    python -m gbt_allinone.recon.last30days.cli "<topic>" --emit=compact --save-dir <dir>

同化改动（2026-09-18 供应链审查结论，逐条在源码内就地标注）：
  · 移除 `setup` 子命令 —— 上游会用本机 GitHub PAT 向第三方换 API key
  · 移除浏览器 cookie 自动提取（cookie_extract / chrome_cookies / safari_cookies
    + `env.get_config()` 的调用点 + `vendor/bird-search` 的浏览器分支）
  · 移除宿主 Codex 登录读取与 chatgpt.com 回传（env / providers 的休眠开关）
  · 落盘锚点全部改到框架 store（store.py / briefing.py / env.py），不写用户主目录
  · 导入结构本土化：`lib/` -> `engine/`，入口 `last30days.py` -> `cli.py`,
    子进程 PID 登记表拆为 `_pids.py`（去掉入口与库的循环依赖）
"""
from __future__ import annotations

VERSION = "v3.0.0 + gbt-v8-assimilated"
UPSTREAM = "https://github.com/mvanhorn/last30days-skill"
UPSTREAM_LICENSE = "MIT"

__all__ = ["cli", "engine", "store", "briefing", "watchlist"]
