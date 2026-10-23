# -*- coding: utf-8 -*-
"""性能监控与自动切换：本地慢 → 自动用云端算力加速。

逻辑：
1. 监控本地推理响应时间
2. 超阈值（默认2秒）自动切换到云端算力
3. 支持文本/图片/视频生成任务
"""
import sys
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.threshold_ms = 2000  # 响应超时阈值（毫秒）
        self.local_endpoint = "http://127.0.0.1:8317/v1"  # CLIProxyAPI
        self.cloud_providers = {
            "agnes": {
                "url": "https://apihub.agnes-ai.com/v1",
                "key_provider": "agnes",
                "fallback_model": "agnes-3.0-flash"
            }
        }
        self.stats = {
            "local_calls": 0,
            "cloud_calls": 0,
            "switches": 0,
            "last_local_time_ms": 0,
            "last_cloud_time_ms": 0
        }
    
    def check_local_health(self):
        """检查本地服务状态"""
        try:
            req = urllib.request.Request(
                f"{self.local_endpoint}/health",
                headers={"Authorization": "Bearer gbtv8-eb1140905a9ceceeeb809f3d9ec5d299"}
            )
            resp = urllib.request.urlopen(req, timeout=3)
            return {"ok": True, "time_ms": resp.headers.get("X-Response-Time", 0)}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def call_local(self, payload):
        """调用本地推理"""
        t0 = time.time()
        try:
            body = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{self.local_endpoint}/chat/completions",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer gbtv8-eb1140905a9ceceeeb809f3d9ec5d299"
                }
            )
            resp = urllib.request.urlopen(req, timeout=60)
            data = json.loads(resp.read().decode())
            elapsed = (time.time() - t0) * 1000
            self.stats["local_calls"] += 1
            self.stats["last_local_time_ms"] = elapsed
            return {"ok": True, "data": data, "time_ms": elapsed, "source": "local"}
        except Exception as e:
            return {"ok": False, "error": str(e), "time_ms": (time.time()-t0)*1000, "source": "local"}
    
    def call_cloud(self, payload, provider="agnes"):
        """调用云端算力"""
        t0 = time.time()
        try:
            from gbt_allinone.deepseek_key import load_key
            key, _ = load_key(provider)
            cfg = self.cloud_providers[provider]
            body = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{cfg['url']}/chat/completions",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {key}"
                }
            )
            resp = urllib.request.urlopen(req, timeout=60)
            data = json.loads(resp.read().decode())
            elapsed = (time.time() - t0) * 1000
            self.stats["cloud_calls"] += 1
            self.stats["last_cloud_time_ms"] = elapsed
            self.stats["switches"] += 1
            return {"ok": True, "data": data, "time_ms": elapsed, "source": "cloud"}
        except Exception as e:
            return {"ok": False, "error": str(e), "time_ms": (time.time()-t0)*1000, "source": "cloud"}
    
    def smart_call(self, messages, model="gbt-potato-v8", max_tokens=256, 
                   use_cloud_if_slow=True, task_type="text"):
        """智能调用：优先本地，慢则切云端"""
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens
        }
        
        # 先试本地
        local_result = self.call_local(payload)
        
        if local_result["ok"] and local_result["time_ms"] < self.threshold_ms:
            # 本地够快，直接用
            return local_result
        
        # 本地慢或失败，切云端
        if use_cloud_if_slow:
            # 云端用兼容模型
            cloud_payload = payload.copy()
            cloud_payload["model"] = "agnes-3.0-flash"  # 云端兼容模型
            return self.call_cloud(cloud_payload, "agnes")
        
        return local_result
    
    def get_status(self):
        """获取状态"""
        local_health = self.check_local_health()
        return {
            "ok": True,
            "monitor": {
                "threshold_ms": self.threshold_ms,
                "stats": self.stats,
                "local_health": local_health
            }
        }

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("op", choices=["status", "call", "test"])
    ap.add_argument("--messages", default='[{"role":"user","content":"ping"}]')
    ap.add_argument("--model", default="gbt-potato-v8")
    args = ap.parse_args()
    
    pm = PerformanceMonitor()
    
    if args.op == "status":
        print(json.dumps(pm.get_status(), ensure_ascii=False, indent=2))
    elif args.op == "call":
        import json as _json
        msgs = _json.loads(args.messages)
        r = pm.smart_call(msgs, model=args.model)
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif args.op == "test":
        r = pm.smart_call([{"role":"user","content":"用一句话介绍你自己"}])
        if r["ok"]:
            content = r["data"].get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"[{r['source']}] {content} ({r['time_ms']:.0f}ms)")
        else:
            print(f"ERROR: {r.get('error')}")
