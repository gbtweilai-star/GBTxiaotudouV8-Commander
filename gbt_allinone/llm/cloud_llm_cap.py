# -*- coding: utf-8 -*-
"""云端算力能力：调用 Agnes AI 等云端算力运行 GBT 小土豆 V8 大模型。

只调算力，不调第三方模型。
本地推理慢时自动切换到云端算力。
"""
import sys
import json
import os
import urllib.request
import urllib.error
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

class CloudLLMCap:
    """云端算力能力处理器"""
    
    PROVIDERS = {
        "agnes": {
            "url": "https://apihub.agnes-ai.com/v1",
            "fallback_model": "agnes-3.0-flash",
            "image_model": "agnes-image-2.1-flash",
            "video_model": "agnes-video-2.5-flash"
        }
    }
    
    OPS = ["status", "list_models", "chat", "generate_image", "generate_video"]
    
    def run(self, payload=None):
        """统一入口"""
        p = dict(payload or {})
        op = str(p.get("op") or "status").lower()
        
        handler_name = "_handle_" + op
        handler = getattr(self, handler_name, None)
        if handler:
            return handler(p)
        return {"ok": False, "error": "unknown op: " + op, "ops": self.OPS}
    
    def _handle_status(self, p):
        """检查云端算力状态"""
        providers = []
        for name, cfg in self.PROVIDERS.items():
            configured = self._get_key(name) is not None
            providers.append({
                "name": name,
                "url": cfg["url"],
                "configured": configured,
                "models": {
                    "text": cfg.get("fallback_model"),
                    "image": cfg.get("image_model"),
                    "video": cfg.get("video_model")
                }
            })
        return {
            "ok": True,
            "cap": "cloud_llm",
            "desc": "调用Agnes AI云端算力运行GBT小土豆V8大模型",
            "providers": providers,
            "count": len(providers),
            "note": "只调算力，不调第三方模型"
        }
    
    def _handle_list_models(self, p):
        """列出可用模型"""
        provider = p.get("provider", "agnes")
        key = self._get_key(provider)
        if not key:
            return {"ok": False, "error": "provider " + provider + " key not configured"}
        
        cfg = self.PROVIDERS[provider]
        url = cfg["url"].rstrip("/") + "/models"
        try:
            req = urllib.request.Request(url, headers={"Authorization": "Bearer " + key})
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read().decode())
            models = [m["id"] for m in data.get("data", [])]
            return {"ok": True, "provider": provider, "models": models}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def _handle_chat(self, p):
        """文本推理 - 用云端算力跑GBT小土豆V8"""
        provider = p.get("provider", "agnes")
        model = p.get("model", self.PROVIDERS[provider]["fallback_model"])
        messages = p.get("messages", [])
        max_tokens = int(p.get("max_tokens") or 256)
        base_url = p.get("base_url") or self.PROVIDERS[provider]["url"]
        
        key = self._get_key(provider)
        if not key:
            return {"ok": False, "error": "provider " + provider + " key not configured"}
        
        return self._call_chat(base_url, key, model, messages, max_tokens)
    
    def _handle_generate_image(self, p):
        """图片生成"""
        provider = p.get("provider", "agnes")
        prompt = p.get("prompt", "")
        
        cfg = self.PROVIDERS.get(provider)
        if not cfg:
            return {"ok": False, "error": "unknown provider: " + provider}
        
        key = self._get_key(provider)
        if not key:
            return {"ok": False, "error": "provider " + provider + " key not configured"}
        
        url = cfg["url"].rstrip("/") + "/images/generations"
        body = json.dumps({
            "model": cfg.get("image_model", "agnes-image-2.1-flash"),
            "prompt": prompt
        }).encode()
        
        try:
            req = urllib.request.Request(url, data=body, headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + key
            })
            resp = urllib.request.urlopen(req, timeout=120)
            data = json.loads(resp.read().decode())
            return {"ok": True, "data": data}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def _handle_generate_video(self, p):
        """视频生成"""
        provider = p.get("provider", "agnes")
        prompt = p.get("prompt", "")
        
        cfg = self.PROVIDERS.get(provider)
        if not cfg:
            return {"ok": False, "error": "unknown provider: " + provider}
        
        key = self._get_key(provider)
        if not key:
            return {"ok": False, "error": "provider " + provider + " key not configured"}
        
        url = cfg["url"].rstrip("/") + "/videos/generations"
        body = json.dumps({
            "model": cfg.get("video_model", "agnes-video-2.5-flash"),
            "prompt": prompt
        }).encode()
        
        try:
            req = urllib.request.Request(url, data=body, headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + key
            })
            resp = urllib.request.urlopen(req, timeout=180)
            data = json.loads(resp.read().decode())
            return {"ok": True, "data": data}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def _call_chat(self, base_url, key, model, messages, max_tokens):
        """执行聊天调用"""
        url = base_url.rstrip("/") + "/chat/completions"
        body = json.dumps({
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens
        }).encode()
        
        try:
            req = urllib.request.Request(url, data=body, headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + key
            })
            resp = urllib.request.urlopen(req, timeout=120)
            data = json.loads(resp.read().decode())
            choice = data.get("choices", [{}])[0]
            message = choice.get("message", {})
            return {
                "ok": True,
                "model": model,
                "content": message.get("content", ""),
                "usage": data.get("usage", {})
            }
        except urllib.error.HTTPError as e:
            return {"ok": False, "error": "HTTP " + str(e.code) + ": " + e.read().decode()[:200]}
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def _get_key(self, provider):
        """从 DPAPI 保险箱取密钥"""
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            from gbt_allinone.deepseek_key import load_key
            key, masked = load_key(provider)
            return key
        except Exception:
            return None

# 模块级实例
_cap = CloudLLMCap()

# 模块级入口函数
def run(payload=None):
    """模块级入口，供 api.py 调用"""
    return _cap.run(payload)
