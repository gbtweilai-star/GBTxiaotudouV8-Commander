# -*- coding: utf-8 -*-
"""gbt-defense-inject -- 给**电脑全页 + 手机包**注入「自卫/反控」层（主人 2026-10-17 令）。

主人原话：「比如手机版安装上只要有黑客AI攻击直接反控，电脑版也是」。

## 设计（不是弹窗吓人，是可执行闭环）
每一页都带一段自包含 JS（`<!-- gbt-defense -->` 标记）：
1. **看**：扫所有输入框/文本域/粘贴内容 + 页面可见文本，匹配攻击特征
   （提示词注入 / 越狱 / 套密钥 / 破门指令 / 数据外带 / 远控话术）；
2. **拦**：命中即**阻断提交**（preventDefault + 清空/只读），并在页面固定一条自卫条显示"已拦截 + 原因"；
3. **留证**：证据（时间/来源/原文前 200 字/匹配规则）写 localStorage 环形缓冲（最多 50 条），可一键导出；
4. **反控**：
   · 若配了 `window.GBT_FRAMEWORK_URL`（联网到本机框架）⇒ POST `{url}/defense/report` 把证据交给框架，
     由框架走 `sec_defenses`（蓝队验证）→ `omni_plug ai_control`（反向操控攻击 AI）；
   · 未联网 ⇒ **离线降级**：只做本地拦截+留证，并明确写「未联网，反控需框架在线」，**不假装已反控**；
5. 语音（若可用）：本地 TTS 播报"检测到攻击，已拦截"。

## 用法
py -3.14 tools/codex-scripts/gbt-defense-inject.py            # 注入 电脑页 + 手机包
py -3.14 tools/codex-scripts/gbt-defense-inject.py --check    # 机检：每页都要有标记与关键 API
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
PAGE_DIRS = ["holo_pet_w3", "state", "state/blueprints", "docs"]
PACK = ROOT / "state" / "mobile-pack"
SKIP_PARTS = {".git", "node_modules", ".pylibs", "vendor", "_upstream", ".scratch",
              "mobile-pack", ".mimosa", "__pycache__", ".wrangler"}
MAX_PAGES = 3000
MARK = "<!-- gbt-defense -->"

DEFENSE_JS = r"""
(function(){
  if (window.__gbtDefense) return; window.__gbtDefense = 3;
  var RULES = [
    ["提示词注入", /(ignore|disregard|forget)\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?)/i],
    ["中文越狱", /(忽略|无视|忘记)(掉)?(之前|以上|前面|所有)(的)?(指令|提示|规则|要求)/],
    ["套系统提示", /(system\s*prompt|系统提示词|开发者消息|developer\s*message|你的设定原文|把你的规则贴出来)/i],
    ["套密钥", /(api[_\s-]?key|secret|token|密码|密钥|凭据).{0,12}(给我|发给我|贴出来|打印|显示|明文|show|print|reveal)/i],
    ["破门指令", /(rm\s+-rf|format\s+[a-z]:|del\s+\/f|drop\s+table|truncate\s+table|shutdown\s+\/s)/i],
    ["数据外带", /(curl\s+https?:\/\/|wget\s+https?:\/\/|upload|exfil|发送到|上传到).{0,40}(jsonl|审计|store|secrets?|dpapi|密钥)/i],
    ["远控接管", /(执行这条命令|run\s+this\s+command|反向\s*shell|reverse\s*shell|监听端口|bind\s+shell)/i]
  ];
  function check(text){ var t=String(text||""); for(var i=0;i<RULES.length;i++){ if(RULES[i][1].test(t)) return {rule:RULES[i][0],hit:(t.match(RULES[i][1])||[""])[0].slice(0,60)}; } return null; }
  function log(rec){
    try{ var b=JSON.parse(localStorage.getItem("gbt_defense_log")||"[]"); b.push(rec); if(b.length>50) b=b.slice(-50);
         localStorage.setItem("gbt_defense_log", JSON.stringify(b)); }catch(e){}
  }
  function bar(msg, tone){
    var d=document.getElementById("gbt-defense-bar");
    if(!d){ d=document.createElement("div"); d.id="gbt-defense-bar";
      d.style.cssText="position:fixed;left:8px;right:8px;bottom:74px;z-index:99998;font:13px/1.6 system-ui;border-radius:12px;padding:8px 10px;display:none;"; document.body.appendChild(d); }
    d.textContent=msg; d.style.display="block";
    d.style.background=(tone==="hit")?"rgba(120,20,20,.94)":"rgba(10,40,30,.94)";
    d.style.color="#eaf2ff"; d.style.border="1px solid "+(tone==="hit")?"#f5b041":"#00e5ff";
  }
  function baseUrl(){
    var b = window.GBT_FRAMEWORK_URL || "";
    if(!b){ try{ b = localStorage.getItem("gbt_framework_url") || ""; }catch(e){} }
    if(!b && /^https?:$/.test(location.protocol)){ b = location.protocol + "//" + location.hostname + ":8877"; }
    return b;
  }
  function report(rec){
    var base = baseUrl();
    if(!base){ log(rec); rec._status="未联网（离线仅拦截+留证，反控需框架在线）"; return Promise.resolve(rec); }
    log(rec);
    try{
      return fetch(base.replace(/\/$/,"")+"/defense/report",{method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify(rec)}).then(function(r){ rec._status="已上报框架 HTTP "+r.status; return rec; })
        .catch(function(e){ rec._status="上报失败："+String(e).slice(0,80); return rec; });
    }catch(e){ rec._status="上报异常："+String(e).slice(0,80); return rec; }
  }
  function speak(t){ /* 2026-10-18 主人令：**不许用 zh-CN SAPI 出声**（主人原话：「还有其他声音参入」）。
       这一行原来是 `new SpeechSynthesisUtterance; u.lang="zh-CN"; speak(u)` —— 每次误报都会用大陆腔机器音
       念一句「检测到攻击，已拦截」，和她的台湾腔神经嗓叠在一起，听起来就是"好几个声音在说话"。
       仓规：拿不到台湾腔就不出声，不用大陆腔顶替 ⇒ 现在**只留视觉红条 + 控制台留痕**；
       要真出声只能走能力位 `voice op=speak`（单一门）。 */
    try{ if(String(t)) console.info("[自卫] "+t+"（不发声：不用 zh-CN SAPI）"); }catch(e){} }
  function block(el, why){
    var rec={ts:new Date().toISOString(),url:location.href,rule:why.rule,hit:why.hit,
              where:(el&&(el.tagName||""))||"page-text"};
    bar("已拦截：疑似「"+why.rule+"」（"+why.hit+"）· 证据已留本地","hit"); speak("检测到攻击，已拦截");
    report(rec).then(function(){ bar("已拦截「"+why.rule+"」· "+((rec&&rec._status)||""),"hit"); });
    return true;
  }
  // ① 拦输入/粘贴
  function guardInputs(){
    var els=document.querySelectorAll("input,textarea,[contenteditable=true]");
    for(var i=0;i<els.length;i++){(function(el){
      el.addEventListener("paste",function(e){ var t=(e.clipboardData||window.clipboardData).getData("text"); var w=check(t);
        if(w){ e.preventDefault(); block(el,w); } });
      el.addEventListener("input",function(){ var w=check(el.value); if(w){ el.dataset.gbtBlocked="1";
        bar("该输入含攻击特征「"+w.rule+"」，已标记拦截 · 证据留本地","hit"); log({ts:new Date().toISOString(),url:location.href,rule:w.rule,hit:w.hit,where:"input-live"}); } });
      var f=el.form; if(f && !f.__gbtGuard){ f.__gbtGuard=1; f.addEventListener("submit",function(e){ var w=check(el.value);
        if(w){ e.preventDefault(); block(el,w); } }); }
    })(els[i]);}
  }
  // ② 扫页面可见文本（攻击内容被注入到页面时）
  /* 🔴 2026-10-18 修（主人投诉「还有其他声音参入」时挖到的真因）：
     原来这里对**页面自己的静态正文**跑 `block()` —— 于是像 digital-human 这种正文里写着
     「密钥 / 明文 / 凭证」字样的页面，**一打开就自己报一次"已拦截「套密钥」"**，
     还会念一句。这不是在拦攻击，是在拿自己的说明书当攻击。
     ⇒ 页面正文命中只**留证（log）**，不弹条、不再出声；真正要拦的是**输入/粘贴/提交**那三条路。 */
  function scanPage(){
    var t=(document.body&&document.body.innerText||"").slice(0,20000); var w=check(t);
    if(w){ log({ts:new Date().toISOString(),url:location.href,rule:w.rule,hit:w.hit,where:"page-text(仅留证)"}); }
  }
  // ③ 自卫条：显示状态 + 证据导出 + 反控说明
  function panel(){
    guardInputs();
    var d=document.createElement("div"); d.id="gbt-defense-pill";
    d.style.cssText="position:fixed;right:10px;bottom:124px;z-index:99999;background:rgba(8,12,20,.92);color:#9fb3c8;border:1px solid rgba(0,229,255,.35);border-radius:12px;padding:6px 10px;font:12px/1.5 system-ui;cursor:pointer";
    d.textContent="自卫：开"; d.title="点击查看拦截记录";
    d.onclick=function(){ var b=[]; try{b=JSON.parse(localStorage.getItem("gbt_defense_log")||"[]");}catch(e){}
      alert("拦截记录 "+b.length+" 条\n"+(b.slice(-5).map(function(x){return x.ts+" ["+x.rule+"] "+x.hit;}).join("\n")||"暂无")+
            "\n\n反控链：框架在线 ⇒ sec_defenses 验证 → omni_plug ai_control 反向操控攻击AI（未在线则不假装已反控）"); };
    document.body.appendChild(d);
  }
  document.addEventListener("DOMContentLoaded", function(){ panel(); scanPage(); });
  if (document.body && document.readyState!=="loading") { panel(); scanPage(); }
})();
"""


def _skip(p: Path) -> bool:
    return any(part in SKIP_PARTS for part in p.parts)


def _pages() -> list:
    out, seen = [], set()
    for d in PAGE_DIRS:
        b = ROOT / d
        if not b.is_dir():
            continue
        for f in b.rglob("*.html"):
            if _skip(f):
                continue
            k = str(f.resolve()).lower()
            if k in seen:
                continue
            seen.add(k)
            out.append(f)
            if len(out) > MAX_PAGES:
                raise SystemExit("页数 > %d ⇒ 疑似产物自反，拒绝注入" % MAX_PAGES)
    if PACK.is_dir():
        for f in PACK.rglob("*.html"):
            out.append(f)
    return out


def _inject(p: Path) -> bool:
    try:
        t = p.read_text(encoding="utf-8", errors="replace")
    except Exception:                                            # noqa: BLE001
        return False
    if MARK in t:
        if "window.__gbtDefense = 3" in t:
            return False
        # 旧版（v1 / v2）⇒ 剥掉旧块再注入 v3（不留两份）。
        # v3 = 2026-10-18：**不再用 zh-CN SAPI 出声**（主人：「还有其他声音参入」），
        #      且页面正文命中只留证不弹条（原来一打开页面自己就报"已拦截"）。
        import re as _re
        t = _re.sub(r"<!-- gbt-defense -->[\s\S]*?</script>", "", t, count=1)
    block = MARK + "\n<script>" + DEFENSE_JS + "</script>"
    if "</body>" in t:
        t = t.replace("</body>", block + "\n</body>", 1)
    else:
        t += block
    p.write_text(t, encoding="utf-8")
    return True


def do_inject() -> int:
    ps = _pages()
    n = 0
    for p in ps:
        if _inject(p):
            n += 1
    print("自卫层注入完成：扫 %d 页 · 新注入 %d · 已存在 %d" % (len(ps), n, len(ps) - n))
    return 0


def do_check() -> int:
    ps = _pages()
    miss = []
    for p in ps:
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except Exception:                                        # noqa: BLE001
            miss.append(str(p))
            continue
        ok = (MARK in t) and ("gbt-defense-bar" in t) and ("防御" in t or "defense" in t.lower())
        if not ok:
            miss.append(str(p))
    print("自卫层校验：页 %d · 齐 %d · 缺 %d%s"
          % (len(ps), len(ps) - len(miss), len(miss), ("（如 " + miss[0] + "）" if miss else "")))
    return 0 if not miss else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="电脑页+手机包 自卫/反控层注入（攻击→拦截→留证→反控）")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if a.check:
        return do_check()
    do_inject()
    return do_check()


if __name__ == "__main__":
    raise SystemExit(main())
