---
name: gbt-brain-vault
description: GBT小土豆的大脑记忆库（Obsidian 库）。开工时先读它的「地图/记忆总纲.md」把记忆接上；要记东西写进「收集箱」。当用户提到记忆、脑库、Obsidian、收集箱、记一笔、别忘了、想忘都忘不了、地图、思维导图时使用。
triggers:
  - "记忆库"
  - "脑库"
  - "Obsidian"
  - "收集箱"
  - "记一笔"
  - "别忘了"
  - "记忆总纲"
  - "大脑记忆"
---

# GBT小土豆 大脑记忆库

**库根**：`C:\Users\ADMIN\Documents\Codex\ObsidianVault`

## 一、开工第一件事（这就是"跟着一起上线"）

读这三篇，把记忆接上：

```
地图/记忆总纲.md      ← 根节点：记忆怎么用、有哪些枝
地图/MOC-总览.md      ← 全部笔记的入口
收集箱.md             ← 随手记的落点（最新记录在下面）
```

读完再看 `日记/<今天>.md`（若存在）。

## 二、要记东西时（不要另找地方）

**追加一行到 `收集箱.md`**（QuickAdd 的「记到收集箱」就是这个落点）。
格式与 QuickAdd 一致：一行一条、带时间戳前缀。**先记，不分类**；整理是后面的事。

## 三、这套库的架构（别改坏）

| 件 | 说明 |
|---|---|
| `.obsidian\plugins` | **junction** → `Documents\Codex\ObsidianPlugins`（中央插件库：quickadd v2.25.0 · notebook-navigator v3.3.7）。**不要把它当普通目录删** |
| 核心插件 | graph ✓ backlink ✓ canvas ✓ daily-notes ✓ templates ✓（另开了 zk-prefixer / random-note / slash-command / footnotes / workspaces） |
| `模板/` | 日记模板 · 随手记模板（templates 插件的 templateFolder） |
| `地图/` | 记忆总纲 · MOC-总览 · **思维导图.canvas**（原生画布：节点+连线） |
| `日记/` | daily-notes 落点（`YYYY-MM-DD`） |

## 四、红线

- **不删主人的笔记**；要动先备份、并说清动什么。
- 库在 `Documents\Codex\`，**不在工作区**里 —— 写它需要出沙箱授权。
- 链接要**写全路径**（`[[人物/人物总览|人物]]`），否则图谱上就是**断链**（读数里叫 `unresolved`）。

---

## 五、未验账（**本件没验过什么，别当成验过**）

**先说验过的（2026-09-22 现读，全在盘上）**：
库根 `C:\Users\ADMIN\Documents\Codex\ObsidianVault` **在**；
`地图\记忆总纲.md` · `地图\MOC-总览.md` · `收集箱.md` · `地图\思维导图.canvas` · `.obsidian` **全 True**；
`.obsidian\plugins` 现读 **LinkType = Junction**（与 §三 写的一致）；
`quickadd\manifest.json` → **2.25.0** · `notebook-navigator\manifest.json` → **3.3.7**（与 §三 写的版本一致）。

**没验过的（逐条）**：

| # | 没验什么 | 为什么 |
|---|---|---|
| 1 | **Obsidian 应用本身**装没装、在不在跑 | 本件只验库文件，没验应用（没起过、没看进程） |
| 2 | 从**沙箱身份**写库会不会被拒 | 文里说"要出沙箱授权"，但**本件零写入**，一次都没试 |
| 3 | QuickAdd 的「记到收集箱」是否真落到 `收集箱.md` | 没触发过那个命令 |
| 4 | 图谱 `unresolved` 断链数 | 没读 —— 所以**不许说"现在没有断链"** |
| 5 | `日记\<今天>.md` 是否存在 | 没读那一天的文件 |
| 6 | 核心插件开关表（graph/backlink/… /zk-prefixer 等） | 只抄了口径，没读 `.obsidian\core-plugins.json` |

---

## 六、出处与固化

| 什么 | 在哪 |
|---|---|
| 本规程（源） | `<仓>\skills\gbt-brain-vault\SKILL.md` |
| 装机副本（AutoClaw 口径） | `~/.openclaw-autoclaw/skills/gbt-brain-vault/SKILL.md`（现读与源同哈希） |
| ⚠️ 本会话能不能自动加载 | **不能**（现读本机 DSH 的技能扫描根不含 `~/.openclaw-autoclaw/skills`）⇒ 目前**按路径读** |
| 记忆库真源 | `C:\Users\ADMIN\Documents\Codex\ObsidianVault`（**在工作区之外**，写它要过沙箱授权） |
| 读数时间 | 2026-09-22（上面那些"在/版本号"都是那一刻现读的） |
