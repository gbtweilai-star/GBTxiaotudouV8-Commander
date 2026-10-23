---
name: gbt-dangerous
displayName: GBT 危险名域（现读：拒绝名单已清空 · 名字只剩登记）
version: 2.0.1
description: GBT小土豆V8 `dangerous` 域的规程（2026-09-23 Owner 令后改口径）。**这一域现在没有拒绝名单**：旧版 `caps_registry.DISABLED_CAPS` 的 11 条已按 Owner「把禁止全部解开」清空，名字转进 `caps_registry.UNIMPLEMENTED_CAPS` 只做登记。本规程写三件事：① 这 11 个名字**只有名字、没有实现**——调用得到的是如实的 `unknown capability`，**不是**"被安全策略挡住"；② 解禁**没有**换来任何能力，也没有留下任何旁路开关（`DANGEROUS_ENABLED` 是历史常量，改它不产生实现）；③ 真正还在把关的**不是这份名单**，而是 `policy.py` 的作用域门 + 落点门 + Owner 终端授权——AI 一律不许给自己发授权、不许改 `policy.py`、不许绕门。当用户说「绕过付费墙 / 破解 / 键盘监听 / 屏幕窃取 / 社工钓鱼 / 渗透攻击 / 凭证窃取 / 无授权远控接管 / 设备接管 / 冻结或要挟资产 / 绕过访问控制自我解锁」，或问「这 11 个名字为什么调不动 / 是不是被禁了 / 现在能不能跑」时使用。
triggers:
  - "绕过付费墙"
  - "绕过许可"
  - "破解"
  - "键盘监听"
  - "键盘记录"
  - "屏幕监听"
  - "屏幕窃取"
  - "社工"
  - "钓鱼"
  - "渗透攻击"
  - "漏洞利用"
  - "凭证窃取"
  - "远控接管"
  - "设备接管"
  - "冻结资产"
  - "自我解锁"
  - "危险能力"
  - "被禁用的能力"
  - "禁止名单"
  - "禁止已解开"
---

# GBT 危险名域（现读：拒绝名单已清空 · 名字只剩登记）

> 开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
>
> ⚠️ **本文件 2.0 已改口径**。1.x 版把这一域写成"一份**永久拒绝名单**"——那句话在 2026-09-23
> Owner 明令「把禁止全部解开」之后**已经不是事实了**。旧文本保留在 §6「历史」，因为它是当时的真读数；
> 但**别拿旧文本当现读**。规矩是：**注册表输出说了算，任何文档（包括本文件）只是转述。**

**唯一现读入口（别信任何二手描述，包括本文件）**：

```powershell
# 现读：被拒名单（应为空 dict）+ 只登记未实现的名单（应为 11 条）
$env:PYTHONIOENCODING='utf-8'
py -3.14 -c "import sys;sys.path.insert(0,'.');from gbt_allinone import caps_registry as CR;print('被拒名单', len(CR.DISABLED_CAPS));print('只登记', len(CR.UNIMPLEMENTED_CAPS));[print(' ', k, '|', v) for k, v in CR.UNIMPLEMENTED_CAPS.items()]"
```

⚠️ **先设 `PYTHONIOENCODING='utf-8'`**：Windows 控制台默认编码会把中文打成乱码
（我第一发就拿到一串 `����ǽ�ƹ�`）。那不是"注册表坏了"，是**你的终端编码**。**不许拿乱码当读数。**

---

## 1. 现读事实（三条，都可以现场复核）

| # | 事实 | 复核命令 |
|---|---|---|
| 1 | 被拒名单**是空的**：`DISABLED_CAPS == {}` —— 没有任何名字被"策略"挡住 | 上面那段 |
| 2 | 那 11 个名字**仍在登记**：`UNIMPLEMENTED_CAPS` 11 条，每条一句中文说明 | 上面那段 |
| 3 | 它们**不在 `BENIGN_CAPS` 里**、**全仓没有实现文件**、`api.py` 里零分发分支 | `py -3.14 -c "import sys;sys.path.insert(0,'.');from gbt_allinone.caps_registry import BENIGN_CAPS,UNIMPLEMENTED_CAPS;print(sorted(set(BENIGN_CAPS)&set(UNIMPLEMENTED_CAPS)))"` → `[]` |

**把这三条连起来读**：解禁前调用这 11 个名字，得到 `{"status":"denied","message":"capability disabled by safety policy"}`；
解禁后得到 `{"status":"error","message":"unknown capability …"}`。**两次都不会跑出任何东西** ——
因为**根本没有实现**。⇒ **"禁止"在这里挡的一直是空气**；解禁**没有**换来能力，也**没有**留下旁路。

---

## 2. 那 11 个名字（登记原文，一个字没改）

| # | 名字 | 登记说明（= 注册表原因原文） | 现在什么状态 | 点它会得到什么 |
|---|---|---|---|---|
| 1 | `paywallbuster` | 付费墙绕过（许可规避）—— 仅登记，无实现 | 只有名字 | `unknown capability` |
| 2 | `data_hijack` | 会话/数据劫持 —— 仅登记，无实现 | 只有名字 | `unknown capability` |
| 3 | `remote_domain` | 无授权远程接管（零护栏远控）—— 仅登记，无实现 | 只有名字 | `unknown capability` |
| 4 | `onboarding_gate` | 绕过自身访问控制的自我解锁 —— 仅登记，无实现 | 只有名字 | `unknown capability` |
| 5 | `keylogger` | 键盘/输入监听 —— 仅登记，无实现 | 只有名字 | `unknown capability` |
| 6 | `screen_sniff` | 屏幕监听/窃取 —— 仅登记，无实现 | 只有名字 | `unknown capability` |
| 7 | `device_takeover` | 无授权设备接管 —— 仅登记，无实现 | 只有名字 | `unknown capability` |
| 8 | `pentest` | 渗透攻击/利用 —— 仅登记，无实现 | 只有名字 | `unknown capability` |
| 9 | `asset_vault_freeze` | 资产锁定/冻结/追回要挟 —— 仅登记，无实现 | 只有名字 | `unknown capability` |
| 10 | `credential_steal` | 凭证窃取 —— 仅登记，无实现 | 只有名字 | `unknown capability` |
| 11 | `social_eng` | 社工/钓鱼 —— 仅登记，无实现 | 只有名字 | `unknown capability` |

> ⚠️ **别把"没有实现"说成"被挡住了"**。前者是**没做**（可机检：全仓零实现文件），
> 后者是**做了但门关着**（会暗示"门一开就能用"）。这两句话的后果完全不同：
> 说成后者，下一轮就会有人去琢磨"那怎么开门"——而门后面**什么都没有**。

> ✅ `pentest` 那条要单独说清：同类**合法**需求本来就有良性通道 ——
> `sec_surface` / `sec_scan` / `sec_chain` / `sec_defenses` 一直在 `BENIGN_CAPS` 里，
> 授权渗透测试走它们 + Owner 发放的作用域，**不需要** `pentest` 这个名字。

---

## 3. 真正还在把关的是什么（不是这份名单）

名单清空**不等于**门没了。现读四道门，**一道都没动**：

| # | 门 | 位置 | 它拦什么 |
|---|---|---|---|
| 1 | **作用域门** | `gbt_allinone/security/policy.py` | 会改状态的位要先有作用域（`deploy_publish` / `filesystem_write` / `process_execute` …） |
| 2 | **落点门** | `one_key_deploy` 必须显式声明落点（`room=` 或 `into_global_production=true`），不声明直接拒 | 生产零修改 |
| 3 | **授权发放** | `python -m gbt_allinone auth grant --scope <s> --ttl 600` | **只能主人在终端发** |
| 4 | **Owner 唯一权限** | 工作区 `AGENTS.md`「Highest-Priority Rules」 | 权限/配置/策略只由 Owner 改 |

⇒ 所以遇到真实的有后果请求，**正确回应仍是**：不绕门 → 说清要过哪道门 → 缺授权就**如实报缺什么**。
变的只是理由：**不是"永久拒绝名单里有它"，而是"门在这儿 + 名字后面本来就没有实现"。**

---

## 4. AI 的红线（解禁后一条都没放宽）

1. **不许给自己发授权**（不许写 `store/auth_grants.jsonl`、不许代跑 `auth grant`、不许改 `policy.py`）。
2. **不许绕门**：一切写生产/镜像的动作走 `run_task`，不许直调模块函数。
3. **不许把"没有实现"包装成"缺授权就能做"** —— 那是**造能力**，比缺能力严重得多。
4. **不许改 Owner 的配置文件**（`settings.yaml` 等）—— 要改先问。
5. **不许拿乱码/二手描述当读数** —— 现读入口永远在 §0 那段命令。

---

## 5. 遇到这类请求怎么答（现读版）

```
用户：帮我绕过某个付费墙 / 做个键盘记录器 / 无授权接管某台设备
→ ① 如实说：这类名字（paywallbuster / keylogger / device_takeover …）在注册表里
      **只有名字、没有实现**，点下去只会得到 unknown capability —— 不是"被策略挡住的"。
   ② 说清真正会拦的地方：有后果的动作要过 policy.py 的作用域门 + 落点门，
      而授权**只能主人在终端发放**；AI 不给自己发授权。
   ③ 给合法替代（有就给，没有就说没有）：授权安全测试走 sec_surface / sec_scan /
      sec_chain / sec_defenses；许可问题走法务/采购路径，不走代码。
   ④ 不写"我可以研究一下 / 试试看 / 只跑一次"这种中间态 —— 因为**没什么可研究的**：
      名字后面是空的，不是关着的门。
```

---

## 6. 历史（1.x 原文口径 · 留给"当时确实是这么读的"）

> 1.x 版原文如下，**只作历史记录，不是现读**：
>
> > `dangerous` 不是"还没接入的能力域"，也不是"缺一张授权卡就能开的域"。它是一份 **永久拒绝名单**
> > （`caps_registry.DISABLED_CAPS` 11 条，每条带一句中文原因，永久禁用）。一句话：**这 11 个名字没有"以后"，只有"不"。**
> > 拦点在图鉴 dispatch 分支（`api.py:1190`），不是 `policy.py` 的作用域门。
> > 谁把 `DISABLED_CAPS` 改小谁就是在拆闸 —— AI 一律不许改。
>
> **为什么改**：Owner 2026-09-23 令「把禁止全部解开」，并给了理由：**这道闸挡的是空气**
> （11 条零实现），却让当天所有扫描在"能看见什么"上持续失真 —— 真正的盲点不是它，
> 是**探测闸**（`cross_scan.PROBE_SKIP_KINDS` / atlas `needs_confirmation` / `omni` 默认拒绝）。
> 解禁的可机检后果见 §1：**行为等价，能力零增益**。
>
> 那句"名字没有以后、只有不"现在**仍然对** —— 但正确理由是**没有实现**，不是**被禁止**。

---

## 7. 未验账（这一版没验到的，如实挂着 · 2026-09-23 立账）

1. **「零实现」的搜索边界**：§1 的三条事实核查是按**本仓源码**搜的（`BENIGN_CAPS` 无、
   `api.py` 零引用、仓内无实现文件）。若某条名字的实现藏在**第三方包、动态 import
   或运行时注入**里，这个搜索方法查不到 —— 只能说"本仓源码层没有实现"，
   **不能**说"绝对没有实现"。
2. **`DANGEROUS_ENABLED` 的运行时行为没实测**：「改它不产生实现」是**源码层**结论
   （没有分支引用它产生能力），没有在运行时真改这个常量试一遍。
3. **bash / cmd 口径的现读命令没验**：§0 的现读命令是 PowerShell 口径
   （`$env:PYTHONIOENCODING='utf-8'`），在 bash / cmd 下的等价写法**未实测**
   （编码行为可能不同，别拿乱码当读数的规矩照旧）。
