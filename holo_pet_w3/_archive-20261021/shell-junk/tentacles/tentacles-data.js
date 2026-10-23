// 触手装备区页面数据 —— 由 tools/codex-scripts/tentacle-gear.py render 生成，勿手改
window.GBT_TENTACLES = {
 "generated_at": "2026-10-17T19:16:08",
 "source": "state/tentacle-provision.json（账本真源）+ 磁盘实况（tentacle-gear.py render 现读）",
 "regen": "py -3.14 -X utf8 tools/codex-scripts/tentacle-gear.py render",
 "check": "py -3.14 -X utf8 tools/codex-scripts/tentacle-gear.py check",
 "honesty": [
  "每根触手的独立永久邮箱**实配 0 个**：接线件 tentacle-mail.py 双后端已备好（A·AgentMail 要主人注册 key；B·项目自有域 <tid>@gbtxiaotudou.com 要主人补 Zoho 应用密码 / DNS 转发 TXT）⇒ 差的只是主人物权凭据那一下（inbox <tid> 闭环自证即配）",
  "手机验证（5sim.net）共享给所有触手，但**待主人充值**（本件不代付、不代充）",
  "freebuff login 是**交互式 TUI** ⇒ 要人工一次；登录后每根才能用自己的额度",
  "⑥⑦⑧ 的『已备』只认磁盘实况：workflows.json / profile / vault.db 落盘为证，账本说已备而磁盘没有会被 check 抓出来"
 ],
 "totals": {
  "触手": 2,
  "自给自足": 0,
  "装备齐备": 0,
  "⑥万能插执行器": 2,
  "⑦无痕浏览器": 2,
  "⑧密钥库": 2,
  "邮箱实配": 0
 },
 "tentacles": [
  {
   "id": "t1",
   "自给自足": false,
   "装备齐备": false,
   "items": [
    {
     "#": "①",
     "件": "开源账户",
     "状态": "未配",
     "值": "",
     "就绪": false,
     "口径": "一根一个，互不共用",
     "缺什么谁能给": "主人/触手自己有头有脸地注册（要邮箱+接码；5sim 充值是主人的事）"
    },
    {
     "#": "②",
     "件": "邮箱",
     "状态": "未配",
     "值": "",
     "就绪": false,
     "口径": "一根一个，**它自己的**永久邮箱",
     "缺什么谁能给": "**主人给一条凭据即通**：tentacle-mail.py 双后端已备好 —— A·AgentMail key（key set）或 B·Zoho 应用密码 setx GBT_IMAP_PASS + DNS 转发 TXT；然后 inbox <tid> 闭环自证"
    },
    {
     "#": "③",
     "件": "手机验证",
     "状态": "**待主人充值**",
     "值": "",
     "就绪": false,
     "口径": "共享给所有触手用；充值由主人自己来（本件不代付、不代充）",
     "缺什么谁能给": "**主人自己给 5sim.net 充值**（本件不代付、不代充）"
    },
    {
     "#": "④",
     "件": "独立云插件",
     "状态": "已挂号",
     "值": "",
     "就绪": true,
     "口径": "一根一个槽位、独立配额",
     "缺什么谁能给": "可自动登记（provision --admit 已挂 t3）"
    },
    {
     "#": "⑤",
     "件": "freebuff",
     "状态": "已装",
     "值": "C:\\Users\\ADMIN\\AppData\\Local\\gbt-freebuff\\t1",
     "就绪": true,
     "口径": "每根一份隔离 HOME（C:\\Users\\ADMIN\\AppData\\Local\\gbt-freebuff\\t1）；freebuff 0.0.195 已探到；login 是交互式 TUI ⇒ 要人工一次（用它自己的邮箱注册）",
     "缺什么谁能给": "装可自动；**login 是交互式 TUI ⇒ 要人工一次**"
    },
    {
     "#": "⑥",
     "件": "万能插执行器",
     "状态": "已备",
     "值": "C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8\\state\\tentacle-exec\\t1（2 次运行记录）",
     "就绪": true,
     "口径": "GBT_STORE_DIR 按触手分家 ⇒ workflows/wf_runs/transfer_cache 互不干扰；作为该触手的主执行器",
     "缺什么谁能给": "**全自动**：gear <tid> 实备（隔离 store 落在 state/tentacle-exec/<tid>）"
    },
    {
     "#": "⑦",
     "件": "无痕浏览器",
     "状态": "已备",
     "值": "C:\\Users\\ADMIN\\AppData\\Local\\gbt-tentacle-browser\\t1",
     "就绪": true,
     "口径": "playwright 持久化隔离 context（Edge 通道）；cookie/登录态只归这根触手",
     "缺什么谁能给": "**全自动**：gear <tid> 实备（profile 在 %LOCALAPPDATA%\\gbt-tentacle-browser\\<tid>）"
    },
    {
     "#": "⑧",
     "件": "密钥库",
     "状态": "已备",
     "值": "C:\\Users\\ADMIN\\AppData\\Local\\gbt-tentacle-vault\\t1\\vault.db",
     "就绪": true,
     "口径": "DPAPI 用户级封印 + 按触手 entropy；掩码显示，明文只供机器取用（fetch）；诚实边界：不防同用户同机器的恶意触手主动偷（那要 OS 级身份分离）",
     "缺什么谁能给": "**全自动**：gear <tid> 实备（vault.db 在 %LOCALAPPDATA%\\gbt-tentacle-vault\\<tid>，DPAPI 封印）"
    }
   ],
   "缺": [
    "开源账户",
    "邮箱",
    "手机验证"
   ]
  },
  {
   "id": "t3",
   "自给自足": false,
   "装备齐备": false,
   "items": [
    {
     "#": "①",
     "件": "开源账户",
     "状态": "未配",
     "值": "",
     "就绪": false,
     "口径": "一根一个，互不共用",
     "缺什么谁能给": "主人/触手自己有头有脸地注册（要邮箱+接码；5sim 充值是主人的事）"
    },
    {
     "#": "②",
     "件": "邮箱",
     "状态": "未配",
     "值": "",
     "就绪": false,
     "口径": "一根一个，**它自己的**永久邮箱",
     "缺什么谁能给": "**主人给一条凭据即通**：tentacle-mail.py 双后端已备好 —— A·AgentMail key（key set）或 B·Zoho 应用密码 setx GBT_IMAP_PASS + DNS 转发 TXT；然后 inbox <tid> 闭环自证"
    },
    {
     "#": "③",
     "件": "手机验证",
     "状态": "**待主人充值**",
     "值": "",
     "就绪": false,
     "口径": "共享给所有触手用；充值由主人自己来（本件不代付、不代充）",
     "缺什么谁能给": "**主人自己给 5sim.net 充值**（本件不代付、不代充）"
    },
    {
     "#": "④",
     "件": "独立云插件",
     "状态": "已挂号",
     "值": "",
     "就绪": true,
     "口径": "一根一个槽位、独立配额",
     "缺什么谁能给": "可自动登记（provision --admit 已挂 t3）"
    },
    {
     "#": "⑤",
     "件": "freebuff",
     "状态": "已装",
     "值": "C:\\Users\\ADMIN\\AppData\\Local\\gbt-freebuff\\t3",
     "就绪": true,
     "口径": "每根一份隔离 HOME（C:\\Users\\ADMIN\\AppData\\Local\\gbt-freebuff\\t3）；freebuff 0.0.195 已探到；login 是交互式 TUI ⇒ 要人工一次（用它自己的邮箱注册）",
     "缺什么谁能给": "装可自动；**login 是交互式 TUI ⇒ 要人工一次**"
    },
    {
     "#": "⑥",
     "件": "万能插执行器",
     "状态": "已备",
     "值": "C:\\Users\\ADMIN\\Desktop\\GBT小土豆V8\\state\\tentacle-exec\\t3（2 次运行记录）",
     "就绪": true,
     "口径": "GBT_STORE_DIR 按触手分家 ⇒ workflows/wf_runs/transfer_cache 互不干扰；作为该触手的主执行器",
     "缺什么谁能给": "**全自动**：gear <tid> 实备（隔离 store 落在 state/tentacle-exec/<tid>）"
    },
    {
     "#": "⑦",
     "件": "无痕浏览器",
     "状态": "已备",
     "值": "C:\\Users\\ADMIN\\AppData\\Local\\gbt-tentacle-browser\\t3",
     "就绪": true,
     "口径": "playwright 持久化隔离 context（Edge 通道）；cookie/登录态只归这根触手",
     "缺什么谁能给": "**全自动**：gear <tid> 实备（profile 在 %LOCALAPPDATA%\\gbt-tentacle-browser\\<tid>）"
    },
    {
     "#": "⑧",
     "件": "密钥库",
     "状态": "已备",
     "值": "C:\\Users\\ADMIN\\AppData\\Local\\gbt-tentacle-vault\\t3\\vault.db",
     "就绪": true,
     "口径": "DPAPI 用户级封印 + 按触手 entropy；掩码显示，明文只供机器取用（fetch）；诚实边界：不防同用户同机器的恶意触手主动偷（那要 OS 级身份分离）",
     "缺什么谁能给": "**全自动**：gear <tid> 实备（vault.db 在 %LOCALAPPDATA%\\gbt-tentacle-vault\\<tid>，DPAPI 封印）"
    }
   ],
   "缺": [
    "开源账户",
    "邮箱",
    "手机验证"
   ]
  }
 ],
 "conventions": {
  "一根触手 = 一个智能体": " profession/tentacle_id/llm_profile/context_namespace/room_id 五重身份；并行默认 8 根、硬顶 32",
  "万能插隔离": "GBT_STORE_DIR 按触手分家（engine import 时绑定）⇒ workflows/wf_runs/transfer_cache 每根一份，互不干扰",
  "无痕浏览器": "playwright 持久化 context + Edge 通道（channel=msedge）；profile 落 %LOCALAPPDATA%\\gbt-tentacle-browser\\<tid>，cookie/登录态只归这根",
  "密钥库": "DPAPI 用户级封印 + 按触手 entropy；掩码显示，明文只经 fetch 供管道取用；诚实边界：不防同用户同机器的恶意程序主动偷",
  "账本真源": "state/tentacle-provision.json（tentacle-provision.py 写）；本页数据由 tentacle-gear.py render 生成"
 }
};
