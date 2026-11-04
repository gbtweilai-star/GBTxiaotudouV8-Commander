/* 主动智能体面板：状态/工单/下单/起停，数据来自 /api/proactive */
(function(){
 if(window.__gbtProactive) return; window.__gbtProactive=true;
 var $=function(id){return document.getElementById(id)};
 function esc(s){return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
 function render(d){
  $("pa-sub").textContent=(d.running?"运行中":"未运行")+" · "+new Date().toLocaleTimeString();
  var c=d.counts||{}; $("pa-counts").innerHTML=["queued","running","done","failed"].map(function(k){return "<span>"+k+" <b>"+(c[k]||0)+"</b></span>"}).join("");
  $("pa-list").innerHTML=(d.tickets||[]).map(function(t){return "<div class='pa-ticket'><b>"+esc(t.id)+"</b><i>"+esc(t.state)+"</i><p>"+esc(t.title)+"</p><small>"+esc((t.result||"").slice(0,120))+"</small></div>"}).join("")||"<div class='pa-empty'>还没有工单</div>";
 }
 function load(){fetch("/api/proactive?op=status").then(function(r){return r.json()}).then(function(d){if(d&&d.ok)render(d)}).catch(function(){})}
 function act(op,body){body=body||{op:op};fetch("/api/proactive",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)}).then(function(r){return r.json()}).then(load)}
 function wire(){var b=$("proactive-toggle"); if(!b)return;
  b.addEventListener("click",function(){var p=$("proactive-panel");p.classList.toggle("open");if(p.classList.contains("open"))load()});
  $("pa-close").addEventListener("click",function(){$("proactive-panel").classList.remove("open")});
  $("pa-start").addEventListener("click",function(){act("start")});
  $("pa-blueprint").addEventListener("click",function(){act("blueprint")});
  $("pa-stop").addEventListener("click",function(){act("stop")});
  $("pa-form").addEventListener("submit",function(e){e.preventDefault();var v=$("pa-input").value.trim();if(!v)return;$("pa-input").value="";act("submit",{op:"submit",text:v})});
  load(); setInterval(function(){if($("proactive-panel").classList.contains("open"))load()},3000);
 }
 if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",wire);else wire();
})();