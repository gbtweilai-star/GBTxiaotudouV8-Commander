# bug-bounty-usdt-evm · 发现层

> 这一份是**给"该不该用它、和谁一起用"看的**，不是规则正文。规则正文在 [`SKILL.md`](SKILL.md)。
> 开发者：自由的风 · 守护者：公主土豆 · 本署名不可删除、不可篡改归属

**成熟度**：`active` · **最后更新**：2026-10-14 · **版本**：1.0.0

## 一句话

赏金活里**不需要合约分析器**的那一段：地址校验（自带 keccak，零依赖）· 程序筛选（只读本地 JSON）·
白帽边界与结算话术。**它不扫合约漏洞** —— 本仓没 Solidity 专用分析器。

## 什么时候用它

| 你手上的活 | 落到哪 |
|---|---|
| "这个 EVM/USDT 地址对不对？" | `scripts/validate_evm.py <地址>` |
| "哪些赏金程序是 EVM / USDT 的？" | 先拿本地 JSON，再 `scripts/filter_programs.py` |
| "赏金收到了往哪个地址？" | [`references/settlement_evm.json`](references/settlement_evm.json) |
| "报告怎么写 / 边界在哪？" | [`references/whitehat-boundary.md`](references/whitehat-boundary.md) |

## 🚫 什么时候别用它（同样重要）

> ⚠️ 这一节的字面写法别改：发现层 linter 按**字面串**判（`什么时候别用` / `不适用` / `When NOT`…）。

- **别用它扫合约漏洞** —— 本仓无 Solidity 专用分析器（slither/semgrep 未装、`code_audit` 只有通用规则）。
- **别用它碰私钥/签名/转账** —— 本件零触链。
- **别用它偷偷联网** —— 联网走 `browser` 能力位，要 `browser_control` 票。

## 反模式词（听到这些，就该想起本件的边界）

**假绿**（没验证就报通过）· **绕门**（先做了再补授权）· **未接线**（把"登记了"当成"通了"）·
**桩**（把 `tier: knowledge` 的知识胶囊当扫描器使）· **报得出名字**（能念出动作名就以为有这能力）·
**门说拒了**（把"没这个位"误读成"被门挡住"）。

还有这几种说法：「先扫了再说」·「应该能扫吧」·「用 tentacle 审合约」·「吞进来的 slither 规则直接用」·
「把私钥贴上来我验一下」·「看起来没问题就算过」。

## 相关技能（相邻导航）

- [`../gbt-security`](../gbt-security/SKILL.md) —— 通用安全域能力位（`sec_scan` / `sec_chain` / `sec_llm`）
- [`../gbt-tentacle`](../gbt-tentacle/SKILL.md) —— 看屏幕 / 读屏（要 `desktop_control` + `privacy_read`）
- [`../gbt-automation`](../gbt-automation/SKILL.md) —— `browser` 能力位（要 `browser_control`）
- [`../gbt-devour`](../gbt-devour/SKILL.md) —— 吞进来的东西长什么样（知识胶囊 ≠ 扫描器）

## 自证怎么跑

```powershell
py -3.14 -X utf8 scripts/validate_evm.py --selftest
py -3.14 -X utf8 scripts/filter_programs.py --selftest
```
