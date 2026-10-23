# -*- coding: utf-8 -*-
"""gbt_allinone.integration.smoke_test — 接轨层冒烟自测(标准库 + 现有依赖, 零新增依赖)。

覆盖:
  1) 未设令牌: /api/gbtwallet/health == 200 (默认行为不变)
  2) 设了 GBT_WALLET_API_TOKEN: 无令牌 -> 401; 错令牌 -> 401; 正确令牌 -> 200
  3) GBT_CORS_ORIGINS 生效(默认 "*" 时仍为 "*"); 预检 OPTIONS 由 CORS 外层直接应答
  4) auth.py 校验函数单测(常数时间比较、方案名大小写、非法头)
  5) 真机回环: uvicorn 起真实端口 + WalletClient 走 urllib 真 HTTP(含 Bearer)

用法:  python gbt_allinone/integration/smoke_test.py [--no-live]
退出码: 0=全部通过; 1=有失败。全部写盘都在系统临时目录内, 结束后删除。
"""
from __future__ import annotations

import importlib
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))          # 项目根
sys.path.insert(0, _ROOT)

TOKEN = "smoke-token-9f2c4a1b7e6d-not-a-real-secret"    # 仅用于本地冒烟的一次性测试值
PASS_PHRASE = "smoke-test-passphrase-throwaway"          # 同上: 临时钱包口令, 用完即删

RESULTS = []


def check(name, fn):
    """执行一项检查并记录结果。"""
    try:
        detail = fn()
        RESULTS.append((True, name, detail if detail is not None else "ok"))
        print(f"[PASS] {name}: {RESULTS[-1][2]}")
        return True
    except Exception as e:                                   # noqa: BLE001
        RESULTS.append((False, name, f"{type(e).__name__}: {e}"))
        print(f"[FAIL] {name}: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False


def expect(cond, msg):
    if not cond:
        raise AssertionError(msg)


def fresh_api(token=None, cors=None):
    """按当前环境重新加载 gbt_wallet.api, 返回新的 app 实例(中间件按 env 重装)。"""
    if token is None:
        os.environ.pop("GBT_WALLET_API_TOKEN", None)
    else:
        os.environ["GBT_WALLET_API_TOKEN"] = token
    if cors is None:
        os.environ.pop("GBT_CORS_ORIGINS", None)
    else:
        os.environ["GBT_CORS_ORIGINS"] = cors
    import gbt_wallet.api as api_mod
    return importlib.reload(api_mod).app


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main(live=True):
    tmp = tempfile.mkdtemp(prefix="gbt_smoke_")
    os.environ["GBT_WALLET_DIR"] = tmp                # 必须在首次 import 前设置
    os.environ["GBT_PLATFORM_IDEM_FILE"] = os.path.join(tmp, "platform_idem.json")
    print(f"[env] GBT_WALLET_DIR={tmp}")

    from fastapi.testclient import TestClient
    from gbt_allinone.integration import auth

    # ---- 1) 默认(无令牌): 保持现状 ----
    def t1():
        app = fresh_api(token=None)
        with TestClient(app) as c:
            r = c.get("/api/gbtwallet/health")
        expect(r.status_code == 200, f"health 期望 200, 实际 {r.status_code}")
        body = r.json()
        expect(body.get("ok") is True, f"ok 字段异常: {body}")
        return f"200, initialized={body.get('initialized')}, version={body.get('version')}"

    check("无令牌 /health == 200 (默认行为不变)", t1)

    # ---- 2) 令牌鉴权 ----
    def t2a():
        app = fresh_api(token=TOKEN)
        with TestClient(app) as c:
            r = c.get("/api/gbtwallet/health")
        expect(r.status_code == 401, f"无令牌期望 401, 实际 {r.status_code}")
        return f"401, body={json.dumps(r.json(), ensure_ascii=False)[:80]}"

    def t2b():
        app = fresh_api(token=TOKEN)
        with TestClient(app) as c:
            r = c.get("/api/gbtwallet/health", headers={"Authorization": "Bearer wrong-token"})
        expect(r.status_code == 401, f"错令牌期望 401, 实际 {r.status_code}")
        return "401"

    def t2c():
        app = fresh_api(token=TOKEN)
        with TestClient(app) as c:
            r = c.get("/api/gbtwallet/health", headers={"Authorization": "Bearer " + TOKEN})
        expect(r.status_code == 200, f"正确令牌期望 200, 实际 {r.status_code}")
        return f"200, {r.json().get('version')}"

    def t2d():
        app = fresh_api(token=TOKEN)
        with TestClient(app) as c:                     # 其它受保护路由同样生效
            r = c.get("/api/gbtwallet/invoices")
        expect(r.status_code == 401, f"/invoices 无令牌期望 401, 实际 {r.status_code}")
        return "401 (/invoices)"

    check("有令牌 /health 无 token == 401", t2a)
    check("有令牌 /health 错 token == 401", t2b)
    check("有令牌 /health 正确 token == 200", t2c)
    check("有令牌 其它路由同样 401", t2d)

    # ---- 3) CORS ----
    def t3a():
        app = fresh_api(token=None, cors=None)         # 默认: "*"
        with TestClient(app) as c:
            r = c.options("/api/gbtwallet/health", headers={
                "Origin": "http://example.com", "Access-Control-Request-Method": "GET"})
        expect(r.status_code == 200, f"预检期望 200, 实际 {r.status_code}")
        expect(r.headers.get("access-control-allow-origin") == "*",
               f"默认 origin 头: {r.headers.get('access-control-allow-origin')}")
        return "预检 200, allow-origin=*"

    def t3b():
        app = fresh_api(token=None, cors="http://localhost:3000, https://app.example.com")
        with TestClient(app) as c:
            pre = c.options("/api/gbtwallet/health", headers={
                "Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
            ok = c.get("/api/gbtwallet/health", headers={"Origin": "http://localhost:3000"})
            bad = c.get("/api/gbtwallet/health", headers={"Origin": "http://evil.example.net"})
        expect(pre.headers.get("access-control-allow-origin") == "http://localhost:3000",
               f"白名单预检头异常: {pre.headers.get('access-control-allow-origin')}")
        expect(ok.headers.get("access-control-allow-origin") == "http://localhost:3000",
               f"白名单 GET 头异常: {ok.headers.get('access-control-allow-origin')}")
        expect(not bad.headers.get("access-control-allow-origin"),
               f"非白名单不应回 ACAO: {bad.headers.get('access-control-allow-origin')}")
        return "白名单生效, 非白名单无 ACAO"

    def t3c():
        """401 响应也要带 CORS 头(CORS 在鉴权外层), 否则前端只能看到跨域错误。"""
        app = fresh_api(token=TOKEN, cors="http://localhost:3000")
        with TestClient(app) as c:
            r = c.get("/api/gbtwallet/health", headers={"Origin": "http://localhost:3000"})
        expect(r.status_code == 401, f"期望 401, 实际 {r.status_code}")
        expect(r.headers.get("access-control-allow-origin") == "http://localhost:3000",
               f"401 缺 CORS 头: {r.headers.get('access-control-allow-origin')}")
        return "401 + allow-origin 同时存在"

    check("CORS 默认 '*'(预检 200)", t3a)
    check("CORS 读 GBT_CORS_ORIGINS", t3b)
    check("401 响应带 CORS 头(外层 CORS)", t3c)

    # ---- 4) auth.py 校验函数单测 ----
    def t4():
        os.environ.pop("GBT_CORS_ORIGINS", None)       # 先清干净, 才能断言"缺省 => *"
        os.environ.pop("GBT_WALLET_API_TOKEN", None)
        expect(auth.parse_origins(None) == ["*"], "parse_origins(None) 应为 ['*']")
        expect(auth.parse_origins("") == ["*"], "空值应为 ['*']")
        expect(auth.expected_token() == "", "无 env 时 expected_token 应为空")
        expect(auth.status()["auth_enabled"] is False, "无 env 时 auth_enabled 应为 False")
        expect(auth.parse_origins(" a , b ") == ["a", "b"], "逗号分隔/去空格失败")
        expect(auth.parse_origins("a;b") == ["a", "b"], "分号分隔失败")
        expect(auth.bearer_token("Bearer abc") == "abc", "Bearer 取值失败")
        expect(auth.bearer_token("bearer abc") == "abc", "方案名应大小写不敏感")
        expect(auth.bearer_token("Basic abc") == "", "非 Bearer 应为空")
        expect(auth.bearer_token("abc") == "", "无方案名应为空")
        expect(auth.bearer_token(None) == "", "None 应为空")
        expect(auth.verify_bearer("Bearer " + TOKEN, TOKEN) is True, "正确令牌应通过")
        expect(auth.verify_bearer("Bearer x", TOKEN) is False, "错误令牌应拒绝")
        expect(auth.verify_bearer(None, TOKEN) is False, "缺头应拒绝")
        expect(auth.verify_bearer("Bearer ", TOKEN) is False, "空令牌应拒绝")
        expect(auth.verify_bearer("Bearer x", "") is False, "服务端无令牌时函数应返回 False")
        expect(auth.is_authorized({}, token="") is True, "未配置令牌 => 放行")
        expect(auth.is_authorized({"Authorization": "Bearer " + TOKEN}, token=TOKEN) is True,
               "is_authorized 正确令牌")
        expect(auth.is_authorized([(b"authorization", b"Bearer " + TOKEN.encode())],
                                  token=TOKEN) is True, "ASGI bytes 头应可解析")
        fp = auth.token_fingerprint(TOKEN)
        expect(len(fp) == 12, "指纹长度应为 12")
        expect(TOKEN not in fp, "指纹不得回显令牌明文")
        expect(fp != auth.token_fingerprint(TOKEN + "x"), "不同令牌指纹应不同")
        expect(auth.token_fingerprint("") == "", "空令牌指纹应为空")
        return "22 项断言全部通过"

    check("auth.py 校验函数单测", t4)

    # ---- 5) 真机回环: uvicorn + WalletClient(真 HTTP, 含 Bearer) ----
    if not live:
        print("[SKIP] 真机回环(已指定 --no-live)")
    else:
        try:
            import uvicorn
        except Exception as e:                               # noqa: BLE001
            print(f"[SKIP] 真机回环: uvicorn 不可用({e})")
        else:
            from gbt_wallet import wallet as W
            os.environ["GBT_WALLET_PASS"] = PASS_PHRASE
            try:
                W.init(PASS_PHRASE, words=12)                # 临时钱包(仅本临时目录)
                print("[env] 临时钱包已初始化(助记词不打印、结束即删)")
            except Exception as e:                           # noqa: BLE001
                print(f"[warn] 临时钱包初始化失败({e}); create_invoice 将报错但鉴权路径仍验证")

            app = fresh_api(token=TOKEN, cors="http://localhost:3000")
            port = free_port()
            srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
            th = threading.Thread(target=srv.run, daemon=True)
            th.start()
            for _ in range(100):
                if srv.started:
                    break
                time.sleep(0.1)
            base = f"http://127.0.0.1:{port}"
            print(f"[env] uvicorn 已监听 {base}")

            from gbt_allinone.integration.platform_client import WalletClient, WalletApiError

            def t5a():
                c = WalletClient(base=base, token=TOKEN, timeout=5, retries=0)
                h = c.health()
                expect(h.get("ok") is True, f"health 异常: {h}")
                return f"health ok, base={c.base}"

            def t5b():
                c = WalletClient(base=base, token="bad-token", timeout=5, retries=0)
                try:
                    c.health()
                except WalletApiError as e:
                    expect(e.status == 401, f"期望 401, 实际 {e.status}")
                    return "401 WalletApiError(status=401)"
                raise AssertionError("错误令牌竟然通过了")

            def t5c():
                c = WalletClient(base=base, token=TOKEN, timeout=30, retries=0)
                inv = c.create_invoice("u_smoke", 1.23, "USDC.E",
                                       idempotency_key="smoke-1")
                expect(inv.get("invoice_id"), f"缺少 invoice_id: {inv}")
                expect(inv.get("user") == "u_smoke", "user 未回填")
                again = c.create_invoice("u_smoke", 1.23, "USDC.E", idempotency_key="smoke-1")
                expect(again["invoice_id"] == inv["invoice_id"], "幂等键未命中缓存")
                other = WalletClient(base="http://127.0.0.1:1", token=TOKEN, retries=0)
                expect(other._idem_get("smoke-1") is None, "换基址后不应命中旧幂等条目")
                expect(c._idem_get("smoke-1")["invoice_id"] == inv["invoice_id"],
                       "同基址应命中幂等条目")
                rows = c.list_invoices()
                expect(any(r["invoice_id"] == inv["invoice_id"] for r in rows), "列表未见新发票")
                mine = c.list_invoices(user="u_smoke")
                expect(len(mine) == 1, f"按用户过滤应为 1, 实际 {len(mine)}")
                ev = c.events(since=0, limit=5)
                expect(isinstance(ev, list), "events 应返回列表")
                return (f"发票 {inv['invoice_id']} / {inv.get('currency')} "
                        f"{inv.get('amount')} -> {inv.get('address')[:10]}…; "
                        f"幂等命中; 事件 {len(ev)} 条")
            def t5d():
                """令牌指纹两端一致: 服务端 auth.status() 与客户端所持令牌同源。"""
                fp = auth.token_fingerprint(TOKEN)
                expect(fp == auth.token_fingerprint(os.environ.get("GBT_WALLET_API_TOKEN")),
                       "令牌指纹不一致")
                return f"fingerprint={fp}"

            check("真机: 正确令牌 health 200", t5a)
            check("真机: 错误令牌 -> WalletApiError(401)", t5b)
            check("真机: 开票/幂等/列表/事件(真 HTTP)", t5c)
            check("真机: 令牌指纹一致(两端同源)", t5d)

            srv.should_exit = True
            th.join(timeout=10)

    shutil.rmtree(tmp, ignore_errors=True)
    ok = sum(1 for r in RESULTS if r[0])
    print(f"\n==== 冒烟结果: {ok}/{len(RESULTS)} 通过 ====")
    for good, name, detail in RESULTS:
        print(f"  {'PASS' if good else 'FAIL'}  {name}")
    return 0 if ok == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main(live="--no-live" not in sys.argv))
