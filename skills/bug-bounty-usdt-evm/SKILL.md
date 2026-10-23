---
name: bug-bounty-usdt-evm
displayName: BUG BOUNTY · USDT/EVM 结算链（地址校验 + 程序筛选 + 白帽边界）
version: 1.0.0
status: active
lastUpdated: 2026-10-14
description: 只做「不需要合约分析器」的那一段赏金活：① EVM 地址校验（纯标准库 + 自带 keccak-256 算 EIP-55，零依赖）；② 按链/资产类型/代币/最低赏金筛选赏金程序（**读本地 JSON，不联网**）；③ 白帽边界与结算话术模板（只给公开收款地址，私钥永不落盘）。它**不是**合约审计器 —— 本仓没有 Solidity 专用分析器（slither/semgrep 未装、code_audit 只有通用规则），所以「挖 Immunefi 的 Solidity 合约」这件事本技能**不承诺**，要补得先经主人批准装包。当用户说「校验这个钱包地址是不是有效 / 这个 USDT 地址对不对 / 帮我筛一下哪些赏金程序是 EVM 或 USDT 的 / 赏金怎么收钱 / 报漏洞的话术怎么写 / 白帽边界在哪」时使用。
triggers:
  - "赏金"
  - "bug bounty"
  - "漏洞赏金"
  - "Immunefi"
  - "EVM 地址校验"
  - "USDT 地址"
  - "钱包地址对不对"
  - "EIP-55"
  - "checksum 校验"
  - "结算地址"
  - "白帽"
  - "报漏洞话术"
  - "TRC20 还是 ERC20"
antiTriggers:
  - "帮我扫这个合约漏洞"（本技能不做 —— 本仓无 Solidity 专用分析器）
  - "把私钥给我看"（永不）
  - "帮我转 USDT"（本技能不触链、不签名）
relatedSkills:
  - gbt-security（sec_scan / sec_chain 等通用安全域能力位）
  - gbt-tentacle（读屏/看屏幕，要 desktop_control + privacy_read）
  - gbt-automation（browser 能力位，要 browser_control）
---

# bug-bounty-usdt-evm · 只做「能证明的那一段」

**成熟度**：active · **最后更新**：2026-10-14 · **版本**：1.0.0（agent 直接落盘件，未过 `pipeline_submit` —— 见 §4 诚实账）

> 开发者：自由的风 · 守护者：公主土豆 · 本署名不可删除、不可篡改归属

## 0. 先把丑话说在前面（口径，别念成绿的）

**本技能不是合约审计器。** 本仓现在**没有** Solidity 专用分析器，三条都现读过：

| 那句"应该能做" | 本仓真读数 | 出处 |
|---|---|---|
| 用 `tentacle` 做合约审计 | `tentacle {"action":"audit_smart_contract"}` **全仓 0 命中**，触手动作表里没这名字 | 在办清单 §二百六十三 |
| 调「吞进来的」slither / semgrep 规则 | `store/devoured/semgrep/` 只是 `tier: knowledge` 的**知识胶囊**（`run.py` 只回知识文本，**不跑扫描**）；`slither` 全仓 0 命中；两个 CLI 本机 `where.exe` 都找不到 | 同上 |
| 用 `code_audit` 扫 `.sol` | `code_audit` 是真能力位，**但没有 Solidity 专用规则**（全仓 grep `.sol｜solidity｜solc` = 0）⇒ 扫 `.sol` 只是**通用规则水平** | 同上 |

⇒ 「本仓本来就能挖 Immunefi 的 Solidity 合约」这句话**不成立**。想补要装 `slither-analyzer`
（联网 + 装包 ⇒ **必须主人批**）。本技能先把**不需要分析器的那一段**做扎实。

---

## 1. 真动作映射（每条都能在本仓验）

| 想干的事 | 本仓真动作 | 要不要授权票 | 出处 |
|---|---|---|---|
| 校验 EVM 地址 / EIP-55 校验和 | `scripts/validate_evm.py`（**纯标准库**，自带 keccak-256） | **不要** | 本件，已过 selftest |
| 按链/类型/代币/赏金筛程序 | `scripts/filter_programs.py`（读**本地** JSON） | **不要** | 本件，已过 selftest |
| 结算话术 / 白帽边界 | `references/whitehat-boundary.md`（模板，纯文本） | **不要** | 本件 |
| 收款地址配置 | `references/settlement_evm.json`（**只有公开地址**，无私钥） | **不要** | 本件 |
| 拿赏金程序清单（联网） | `browser` 能力位（`{"op":"..."}`） | **要 `browser_control`** | 在办清单 §二百六十一 / AGENTS.md §4 |
| 读屏幕上的文字 | `tentacle {"action":"read_text"}` —— 读的是**渲染出来的文字**，不是"读 GitHub" | **要 `desktop_control` + `privacy_read`** | 在办清单 §二百六十三 |
| 静态扫代码 | `cap code_audit '{"op":"scan", ...}'`（通用规则；policy 里无该位分支 ⇒ 不额外要票，但它会写 `state/`） | 不要票，但要懂它会写盘 | §二百六十三 |
| Solidity 专用分析 | **本仓没有** | 需主人批装包 | §二百六十三 |

**联网那一步为什么不做在脚本里**：脚本在没人看着的时候出去拿数据，读回来的东西又会被当"事实"用。
所以本技能的脚本一律**只读盘**；要联网就手动走 `browser` 能力位，**拿着授权票**去拿，拿回来落盘成 JSON，再交给 `filter_programs.py` 筛。

---

## 2. 三个可跑件（都有 selftest，都能负对照）

### ① 地址校验 —— 零依赖，哪个解释器都能跑

```powershell
py -3.14 -X utf8 skills/bug-bounty-usdt-evm/scripts/validate_evm.py 0x12113c1904342B7aD20b38271840C1B0e4962957
py -3.14 -X utf8 skills/bug-bounty-usdt-evm/scripts/validate_evm.py --selftest
```

为什么自带 keccak：本仓口径是 3.14，`py -3.14` 上 `eth_utils` / `web3` / `Crypto` / `eth_hash`
**一个都没装**（只有默认 `python` 3.12 装了）。所以不能写「用 eth_utils 做 checksum + 零依赖」——
那是自相矛盾的。本件把 keccak-256（**不是 sha3-256**，padding 是 `0x01` 不是 `0x06`）用纯 python 实现，
并用 EIP-55 官方向量 4 条 + keccak 官方向量 3 条 + 4 条负对照自证。

判三个层次，**分开报**（不能混成一句"有效"）：

- `shape_ok`：`^0x[0-9a-fA-F]{40}$`
- `checksum`：`valid` / `all_lower` / `all_upper` / `bad`
  （EIP-55 原文：全小写、全大写是**合法**写法，只是没带校验和；**混大小写才是"带了校验和"，那时对不上就是坏地址**）
- `checksum_addr`：规范 EIP-55 写法 —— 抄地址时用这个

### ② 程序筛选 —— 只读本地 JSON

```powershell
py -3.14 -X utf8 skills/bug-bounty-usdt-evm/scripts/filter_programs.py --template      # 先拿空模板
py -3.14 -X utf8 skills/bug-bounty-usdt-evm/scripts/filter_programs.py --in state/bounties_raw.json --chain arbitrum --type smart_contract --token usdt
py -3.14 -X utf8 skills/bug-bounty-usdt-evm/scripts/filter_programs.py --selftest
```

它**不造数据**：输入里没有的字段就没有，筛不出来就报 0 命中（0 命中也是"跑成了"）。

### ③ 结算与边界 —— 模板

- `references/settlement_evm.json`：收款地址 + 支持的链 + 红线（私钥永不落盘）
- `references/whitehat-boundary.md`：白帽六条 + 三段结算话术 + 「不许出现的三样东西」

---

## 3. 标准流程（照这个顺序走）

1. **核地址**（不要票）：`validate_evm.py <地址>` → `verdict` 必须是 `ok_checksummed` 或 `ok_no_checksum`；
   `bad` 就停下，别用。
2. **拿清单**（看情况）：主人给本地 JSON；或拿 `browser_control` 票走 `browser` 能力位抓 → 落盘成 JSON。
3. **筛**（不要票）：`filter_programs.py` 按链/类型/代币/赏金筛 → 出候选。
4. **读 scope**：把程序的 in-scope 资产抄下来存档 —— **这是后面所有动作的边界**。
5. **要挖合约** ⇒ 本仓现在**没有**这个能力，如实说，问主人批不批装分析器。
6. **报漏洞 / 收钱** ⇒ 用 `references/whitehat-boundary.md` 的两段模板，**地址只发一次、发前再核一遍**。

---

## 4. 诚实账（哪条验了、哪条没验）

| 项 | 状态 |
|---|---|
| `validate_evm.py --selftest` | ✅ **真跑通**（3 keccak 向量 + 4 EIP-55 向量 + 4 负对照 = PASS，退出码 0） |
| `validate_evm.py` 跑 `0x12113c19…2957` | ✅ **真读数**：`shape_ok=true` · `checksum=valid` · `verdict=ok_checksummed` |
| `filter_programs.py --selftest` | ✅ **真跑通**（6 例，含"不存在的链必须 0 命中"负对照 = PASS） |
| `filter_programs.py` 跑**真实**赏金清单 | ⚠️ **未验** —— 手上没有真清单（联网要票，本件不自己出去） |
| 「本技能能扫 Solidity 漏洞」 | ❌ **不成立**，本仓无 Solidity 专用分析器 |
| 收款地址链上可用性（USDT 合约 / chainId） | ⚠️ **未验** —— 本件未联网核，收款前必须链上自核 |
| 过 `pipeline_submit` 门 | ❌ **没有** —— 本件是 **agent 直接落盘**（不是过门写入）；`pipeline_submit` 要 `deploy_publish` 票，现读 **0 张**，票在主人手上 |

**装载**：本仓技能的唯一真相是仓内 `skills/<名>/`；装到运行时（`~/.agents/skills/`）走
`py -3.14 tools/skills_sync.py sync --only bug-bounty-usdt-evm`。
按 AGENTS.md 的安全纪律，**装之前要先出 SKILL VETTING REPORT 并经主人确认** ——
本件是自研件，装卸载通道同 `gbt-*`。

---

## 5. 什么时候**别**用它

- 想让它**扫合约漏洞** → 别用，本仓没这个能力（要装 slither 得先批）。
- 想让它**触碰私钥 / 代替签名 / 转钱** → 别用，本件零触链、只存公开地址。
- 想让它**在没人看着时联网抓数据** → 别用，联网走 `browser` 能力位、要票、要人盯着。
- 只想问「一个普通地址格式对不对」 → 直接用 `validate_evm.py` 就行，不用读全文。
