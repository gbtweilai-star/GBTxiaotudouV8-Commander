# 深挖 C2/C3：多轮记忆错、system 不服从 —— 到底是接线问题还是模型能力问题？
import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8111"
MODEL = "gbt-v8-v82-q5_0"


def post(path, payload, timeout=300):
    rq = urllib.request.Request(BASE + path,
                                data=json.dumps(payload).encode("utf-8"),
                                headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(rq, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return {"__err": f"HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}"}
    except Exception as e:
        return {"__err": f"{type(e).__name__}: {str(e)[:150]}"}


MSGS = [{"role": "user", "content": "记住这个数字：7391"},
        {"role": "assistant", "content": "好的，7391。"},
        {"role": "user", "content": "刚才的数字是多少？只给数字。"}]

print("=" * 96)
print("① 看实际渲染出来的 prompt（/apply-template）")
for path in ("/apply-template", "/v1/apply-template"):
    d = post(path, {"messages": MSGS}, timeout=30)
    if "__err" not in d:
        print(f"  端点 {path} 可用")
        print("  " + json.dumps(d, ensure_ascii=False)[:900])
        break
    print(f"  端点 {path}: {d['__err'][:90]}")

print("=" * 96)
print("② C2 换不同 max_tokens 重测（排除截断/幻觉）")
for mt in (16, 48, 128):
    d = post("/v1/chat/completions", {"model": MODEL, "messages": MSGS,
                                      "max_tokens": mt, "temperature": 0.0, "stream": False})
    if "__err" in d:
        print(f"  max_tokens={mt}: {d['__err'][:90]}")
        continue
    ch = d["choices"][0]
    txt = (ch.get("message") or {}).get("content", "").strip()
    print(f"  max_tokens={mt:>3}: {txt[:90]!r}  finish={ch.get('finish_reason')}")
    print(f"               命中 7391: {'7391' in txt}")

print("=" * 96)
print("③ C2 换问法（排除「刚才」这种指代）")
for q in ("7391 是多少？", "重复我上面给的数字", "上一轮 user 说了什么数字？"):
    d = post("/v1/chat/completions", {"model": MODEL,
                                      "messages": [MSGS[0], MSGS[1], {"role": "user", "content": q}],
                                      "max_tokens": 40, "temperature": 0.0, "stream": False})
    if "__err" in d:
        print(f"  {q!r}: {d['__err'][:80]}")
        continue
    txt = (d["choices"][0].get("message") or {}).get("content", "").strip()
    print(f"  {q!r:<28} → {txt[:70]!r}  命中={'7391' in txt}")

print("=" * 96)
print("④ C3 system 服从性：三种强度")
for sysmsg in ("只用英文回答。",
               "CRITICAL: You MUST answer ONLY in English. Never use Chinese characters.",
               "You are an English-only assistant. Reply in English exclusively."):
    d = post("/v1/chat/completions", {"model": MODEL,
                                      "messages": [{"role": "system", "content": sysmsg},
                                                   {"role": "user", "content": "你叫什么名字？"}],
                                      "max_tokens": 40, "temperature": 0.0, "stream": False})
    txt = (d["choices"][0].get("message") or {}).get("content", "").strip() if "__err" not in d else d["__err"]
    has_cjk = any("\u4e00" <= c <= "\u9fff" for c in txt)
    print(f"  system={sysmsg[:34]!r:<38} 含中文={has_cjk}  → {txt[:56]!r}")
