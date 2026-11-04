# 152 · capability_router：四类人话接进 /api/chat，自动调用万能插

> 主人令 2026-11-02：「写 capability_router 接进 /api/chat：看屏幕、开网页、读写文件、看图四类，
> 自动调用万能插并验收」。

## 一、一句话

**把一句人话判成四类里的哪一类，再交给万能插真执行。**
路由只做「判类 + 取目标」，执行**一律**走 `run_task("omni_plug", payload)` ——
授权、审计、回执都在万能插那道门里，这里不另造第二套执行器。

```
用户一句人话
   │
   ▼
capability_router.classify()      纯文本：不执行、不联网、不写盘
   │  四类之外 / 像提问 ⇒ handled=False（交回对话模型，不抢话）
   ▼
capability_router.build_call()    白名单：只拼四种 omni_plug payload
   │
   ▼
api.run_task("omni_plug", …)      万能插唯一门：门 → 执行 → 审计 → 回执
   │
   ▼
/api/chat 回执 { ok, via:"capability_router", intent, call, capability, text }
```

## 二、四类怎么落（现读）

| 类 | 人话例子 | 万能插插座 | payload | 门（作用域） | 真执行落点 |
|---|---|---|---|---|---|
| `screen` 看屏幕 | 帮我看看屏幕 / 截个屏 | `app` | `{"op":"run","socket":"app","target":"","do":"see"}` | `privacy_read`（读屏=隐私载体） | `tentacle.see()` 整屏取帧（空目标 = 整屏，见 §五） |
| `web` 开网页 | 打开 https://example.com | `web` | `{"op":"run","socket":"web","target":URL,"do":"open"}` | `privacy_read`（+`desktop_control`，按环境判） | 系统默认浏览器真打开（`browser_cap.open_url`） |
| `file` 读写文件 | 读文件 a.txt / 写文件 a.txt 内容 你好 | `file` | `{"op":"run","socket":"file","target":绝对路径,"do":"read|write","args":{"text":…}}` | 写：`filesystem_write`；读：零作用域 | 万能插 `file` 插座真读/真写（写面仍受 `WRITE_ROOTS` 收口） |
| `image` 看图 | 看图 icons/avatar.png | `universal` | `{"op":"universal","target":绝对路径,"do":"view"}` | 读类（本机视觉，无写面） | `omni_adapter` 判类为图片 → `vision` op=analyze（PIL 像素级） |

**不新增能力位**：`capability_router` 不注册进 `caps_registry`（注册表锁不动），
它只是一层「人话 → 万能插」的路由；验收里有一条专门钉这个（router 不在 `BENIGN_CAPS`）。

## 三、判类规则（写死、可复核）

- **优先级** `screen > image > web > file`（同分时按此序；「看屏幕」最具体）；
  网址/路径是强目标证据：命中 URL 补 `web`，命中带扩展名路径补 `file`/`image`。
- **只接祈使/任务句**：带「吗 / 呢 / ？ / 怎么 / 如何 / 会不会…」、又没有
  「帮我 / 请 / 给我 / 麻烦 / 现在…」、且不以动作动词开头的 ⇒ 判为提问，
  `handled=False`。实测：「你会看屏幕吗？」→ 不执行；「帮我看看屏幕」→ 执行。
- **四类之外一律 `handled=False`**：闲聊、写诗、记忆类句子都照旧走对话模型，行为与接进前一致。
- **判不出目标不猜**：
  - 开网页没给网址 ⇒ `user_error`；
  - 写文件没给内容 ⇒ `user_error`（**不拿整句去写**）；
  - 看图给了非图片 ⇒ `user_error`（点名只接哪些扩展名）。
- **payload 白名单**：`build_call` 只按四类拼形状，`intent` 不是四类直接抛 `ValueError`；
  路由**不能**被当成万能插的任意透传口（不能 `intent="process"` 偷跑命令）。

## 四、执行纪律

- **唯一门**：`api.run_task("omni_plug", payload, safe=True)`。每次执行都进审计（call/ok/denied），
  回执里 `call={kind:"omni_plug", payload:…}` 可逐字段核对；
- **被门拒如实带回**：`denied` + `missing` + `how_to_grant` 原样透出，不把「要票」说成「坏了」；
- **回执裁剪**：截图 `image_base64`、钢印等大块字段不进聊天响应（`_trim`），只留可核对读数；
- **失败不冒充**：`ok` 由「信封 ok ∧ 万能插回执 ok ∧ 声明」共同决定，任一不满足就是 `ok=False` + 原因。

## 五、顺手修掉的四处「插得上、驱动不了」（真缺陷，不是扩功能）

1. **web 插座驱动不了**（`gbt_allinone/omni_plug.py`）：原来 `socket=web` 插得上，
   但 `run` 只回一句「走触手 see」的失败 —— 与 app 插座真能 see 不对等。
   现在 `do=open` 接 `browser_cap.open_url`（系统默认浏览器真打开），`do=fetch` 接无头抓页。
2. **app 插座空目标必失败**：`plug()` 里空目标会被判「窗口没命中」，
   于是「看屏幕」连 plug 都过不去。现在空目标 = 整屏（`do=see` 走 `omni.see()`），
   给窗口名/可执行件才走原来的窗口路径。
3. **`universal` 分支的 Windows 路径 bug**（`gbt_allinone/omni_plug.py`）：
   原来用 `str(__file__).replace("gbt_allinone/omni_plug.py", "tools/omni_adapter.py")` 拼路径，
   Windows 反斜杠下 replace 永远不命中 ⇒ 把 `omni_plug.py` 自己当 adapter 执行，
   实测报 `'NoneType' object has no attribute '__dict__'`（「看图」当场撞上）。
   改成 `_ROOT / "tools" / "omni_adapter.py"`。
4. **`omni_adapter` 两处判类错**（`tools/omni_adapter.py`）：
   - `C:\...\avatar.png` 会被 `SCHEME_RE` 当成 scheme `"C:"` ⇒ 补「盘符路径先判」；
   - 盘上真实存在的相对路径（`icons/avatar.png`）会被「裸域名 ⇒ https」抢走 ⇒ 先按路径判；
   - 新增 `view/see/look/analyze` 动词 → 图片走 `vision`（缺 Pillow/numpy 就如实报缺）。

## 五·续、独立验收抓出的 10 个缺陷（F1–F7 + N1–N3，已全修 + 14 条回归判据）

第一版自测 42 项全绿，但**独立验收子代理**换了一批句子真跑，抓出 7 个问题（二次复验又抓 3 个，共 10 个）—— 这段比自测值钱：

| # | 严重度 | 缺陷（复现） | 修法（文件:位置） |
|---|---|---|---|
| F1 | **阻断** | 「读文件 X **里写的**结论」因句中一个「写」字被判 write，并把路径后尾巴当正文 ⇒ **读请求变成覆盖写** | write 判定只认显式写句式（`WRITE_RX`）；**无显式标记默认 read**；读/写同时显式命中 ⇒ `user_error`；写语义 + 多路径 ⇒ 不猜目标直接拒（F1b）；正文不再拿路径后任意尾巴（`capability_router.py` 判类段 + `_find_write_text`） |
| F2 | 应修 | 「把**这段文字**存到 X」把占位词当正文并报写成功 | `_clean_content` 拒绝指代词；「内容」标记冒号可省且优先于「把X存到」（`_find_write_text`） |
| F3 | 应修 | 「读文件 X 里 https://… 那段」被句中 URL 抢成开浏览器 | 只有「显式 web 动作 + 无更具体类」才让 URL 抬 web；显式 file/screen/image 优先（`classify`） |
| F5 | 应修 | 含空格 Windows 路径被截成 `C:\Users\Lenovo`（本仓路径就带空格） | 盘符/UNC 用「起于盘符、止于已知扩展名」的非贪婪匹配；无扩展名路径按盘上存在性从长到短收口（`_DRIVE_EXT_RE`/`_find_path`） |
| F4 | 应修 | 父目录不存在时 `file` 插座直接拒，「写新目录」永远到不了 mkdir | 写面（`WRITE_ROOTS`）内允许 plug 通过，run 时 `mkdir(parents=True)`（`omni_plug.py` `Pulse.plug`） |
| F6 | 可放过 | 看图目标不存在时掉进 path 分支被当命令跑（失败如实但语义错） | 图片扩展名 + 不存在 ⇒ 直接结构化报「图片不存在」（`tools/omni_adapter.py` `execute`） |
| F7 | 应修（防御） | `execute()`/`build_call()` 只验形状不验语义：把 image 的 `target_abs` 写成 `whoami.exe` 仍拼出合法 payload 并执行 | `build_call` 加语义校验（image 必图片扩展名 / web 必 http(s) / file 必齐 / 写必非空正文）；`execute` 捕 ValueError ⇒ `user_error` 且**不派发**（`capability_router.py`） |
| N1 | 应修（二次复验） | 句首裸写动词被「默认 read」吞掉：`写 X 内容 你好` 被判 read（不落盘） | 加 `BARE_WRITE_RX`：只在**子句开头**（^/标点后）认裸「写/保存/新建/追加/覆盖」；句中「里写的结论」仍不算 |
| N2 | 可放过→已修 | `看一下文件 X` 不接管（交回模型） | `READ_RX`/`FILE_KW` 补「看一下文件 / 看下文件」 |
| N3 | 可放过→已修 | 多路径保护过严：正文里提到别的路径也被拒 | 只有**正文标记之前**的路径才算目标候选；复制语义（把 A 里内容保存到 B）单独如实拒 `copy_unsupported` |

对应的 14 条回归判据已进 `tests/test_capability_router.py` 的 `[1c]` 与 `[4]` 段：
F1 读文件不被写（含「把 X 里写的结论」两种变体）、F1b 多路径写不猜目标、F2 占位词/内容标记两条、
F3 URL 不抢类 + 单贴链接不动手、F5 含空格路径、F7 两道、F4 新目录写、F6 缺件看图、
N1 句首裸写动词、N2「看一下文件」、N3 正文里的路径不算目标冲突
—— 56 项全绿（复跑两次一致）。

## 六、接进 /api/chat

`tools/console-server.py::_chat()` 在**调模型之前**先过 router：

```python
if use_capabilities and os.environ.get("GBT_CAPABILITY_ROUTER", "1") != "0":
    try:
        from gbt_allinone import capability_router as _CR
        cap = _CR.run(text, context=context)
        if cap.get("handled"):
            return cap                      # 命中即真执行，不再问模型
    except Exception:
        print("…降级…", file=sys.stderr)     # 路由坏了降级对话模型，但必须留痕
```

- **开关**：body 里 `"capability": false`，或环境变量 `GBT_CAPABILITY_ROUTER=0`；
- **不抢话**：四类之外/提问句照旧走模型，响应形状与接进前一致；
- **界面**：`holo_pet_w3/console/app.js` 对 `via=capability_router` 的回执显示
  「万能插 · 类别 · Nms · 已落审计」，与普通回答的 token/上下文 meta 分开。

真 HTTP 回执（四类各一条，实测）：

```json
{"ok": true, "handled": true, "via": "capability_router", "intent": "file",
 "text": "写文件：.scratch/router-accept/http.txt（23 字节）",
 "call": {"kind": "omni_plug", "payload": {"op":"run","socket":"file","do":"write"}},
 "capability": {"op":"run","ok":true,"socket":"file","plug":"plugged","wrote_bytes":23}}
```

## 七、验收（2026-11-02 现读）

跑法：

```bash
# 本仓标准口径是 py -3.14；本轮验收机没有全局 py，实际用便携 Python 3.12（含 pillow/numpy/mss）跑，读数见下表
py -3.14 -X utf8 tests/test_capability_router.py
```

| 项 | 读数 | 怎么读 |
|---|---|---|
| 判据总数 | **56 项 · ALL OK · 0 FAIL** | 逐条真跑（模块自述 4 + 判类 1 + 反例 9 + 独立验收回归 14（[1c]12 + [4]2）+ 白名单 6 + 门 3 + 真执行 10 + 开网页 4 + /api/chat 接线 5 = 56，复跑两次一致） |
| 判类 | 10/10 中 | screen/web/file read/file write/image 各 2 例 |
| 不抢话 | 4/4 `handled=False` | 「你好，你是谁」「今天天气怎么样」「帮我写一首诗」「记住这件事」 |
| 提问不擅自动手 | 「你会看屏幕吗？」→ `handled=False` | 问句 + 无祈使词 |
| 独立验收回归 | 首轮子代理报 **1 阻断 + 6 应修**（F1–F7）→ 全修；二次复验再报 **1 应修 + 2 可放过**（N1–N3）→ 全修；累计加 **14 条**判据，复验脚本原样重跑全绿 | 见 §五·续；这是本件最值钱的一段（自己测全绿≠没问题） |
| 门在生效 | 非可信会话跑「看屏幕」⇒ `denied` · `missing=["privacy_read"]` · 带 `how_to_grant` | 万能插作用域门真挡（不是路由自己挡） |
| 自动调用万能插 | spy 记到**每次**执行 `kind="omni_plug"` | 6 次真执行全过 spy |
| 写文件 | 真落盘 `你好，万能插` · `wrote_bytes=18`（UTF-8）· 新目录也可建（F4） | 逐字节读回比对 |
| 读文件 | 回执 `read` 命中 `你好，万能插`；「读文件 X 里写的结论」仍是 read，不覆盖（F1） | 内容比对 + 原文件逐字未变 |
| 看图 | `icons/avatar.png` → **512x512 · 亮度=187.1 · 对比度=82.7**；目标不存在 ⇒ 结构化报缺（F6） | 本机 `vision` analyze 真跑 |
| 看屏幕 | 整屏 **1920x1200**（app 插座 `see`） | 真取帧（环境不可采集时会结构化报 `missing/why`，验收对两种都判） |
| 开网页 | `backend=system-default-browser` · URL 真交给浏览器 | 测试打桩记录 URL；opt-in 可真弹浏览器 |
| /api/chat 接线 | `_chat("读文件 …")` → `via="capability_router"` | 真调 server 的 `_chat`；并验 `use_capabilities=False` 回到模型分流 |
| 真 HTTP 四类 | write/read/image/screen/web 全 `ok=true, handled=true, via=capability_router` | 起 `console-server.py --port 18966` 后用便携 python POST（utf-8） |

真实 HTTP 读数（端口 18966，`POST /api/chat`）：

| 一句话 | 回执 `text` |
|---|---|
| `写文件 .scratch/router-accept/http.txt 内容 从 /api/chat 进来的` | 写文件：…（23 字节）· 文件真落盘 |
| `读文件 .scratch/router-accept/http.txt` | 读文件：…（前 200 字）从 /api/chat 进来的 |
| `看图 icons/avatar.png` | 看图：icons/avatar.png（512x512 · 亮度=187.1 · 对比度=82.7） |
| `帮我看看屏幕` | 看屏幕：已取到屏幕帧 · 1920x1200（经万能插 app 插座） |
| `打开 https://example.com` | 开网页：https://example.com（backend=system-default-browser） |

## 八、边界（说清楚，不含糊）

1. **开网页 = 把 URL 交给系统默认浏览器**：这里不保证页面渲染完成、不读页面内容
   （要读正文走 `do=fetch` 或 `browser` 能力位）；
2. **看图 = 本机像素级视觉分析**（尺寸/主色/亮度/对比度/网格/边缘），**不是语义识别**；
   语义识图要接云端视觉模型（`vision op=cloud`），缺配置会如实报 `needs_dependency`；
3. **看屏幕受采集身份门约束**：非交互桌面/窗口站不对时万能插会结构化拒绝（`missing/why`），
   不冒充已看到；
4. **写文件有落点门**：万能插 `_guard_write` 只准写仓内 `projects/ · outputs/ · .scratch/`；
5. **四类之外不抢话**：闲聊/提问仍走对话模型 —— 接进前后行为一致；
6. **不新增能力位**：注册表计数不受影响。

## 九、复跑（四条命令）

```bash
# ① 验收（56 项）
py -3.14 -X utf8 tests/test_capability_router.py

# ② 单元：判类（纯文本）
py -3.14 -X utf8 -c "import sys;sys.path.insert(0,'.');from gbt_allinone import capability_router as CR;import json;print(json.dumps(CR.classify('看图 icons/avatar.png'),ensure_ascii=False))"

# ③ 真 HTTP（起服务后另开一个终端）
py -3.14 -X utf8 tools/console-server.py --port 18966
curl.exe -s -X POST http://127.0.0.1:18966/api/chat -H "Content-Type: application/json" --data-binary "{\"text\":\"帮我看看屏幕\"}"

# ④ 回归：编译改过的文件
py -3.14 -m py_compile gbt_allinone/capability_router.py tests/test_capability_router.py gbt_allinone/omni_plug.py tools/omni_adapter.py tools/console-server.py
```

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属

## 十、APP 真机接线（2026-11-02）

- 桌面版 APP（`GBT小土豆V8桌面版/payload`）已同步本件 + `world_forge` / `pentest_flow`；console 对话页新增
  **万能插四类快捷条**（看屏幕 / 开网页 / 读文件 / 看图），点一下就走 `/api/chat → capability_router → 万能插`；
- 真机 CDP 点「看屏幕」：回复「看屏幕：已取到屏幕帧 · 1920x1200（经万能插 app 插座）」，
  meta「万能插 · 看屏幕 · 733ms · 已落审计」（截图 `assets/app-capability-router.png`）；
- APP 原有路由 `/api/dh/hand`、`/api/tianzhen` 保留可用；详见 `docs/157-p1-registration-app.md`。
