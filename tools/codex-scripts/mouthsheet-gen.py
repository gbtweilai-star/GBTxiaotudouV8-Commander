# -*- coding: utf-8 -*-
"""mouthsheet-gen.py — 用 Seedream 改图，从**她自己的脸**生成 viseme 形状表。

## 为什么是这条路（不是继续调 shader）
Live2D 官方 Motion-sync 文档（docs.live2d.com/en/cubism-editor-manual/motion-sync/）：
音频 → viseme 时序 → **在用户预定义的每个 viseme 形状之间混合**。
⇒ 专业做法先有"形状表"（美术），再由音频给权重。程序化椭圆永远做不到
（两版牙腔贴图放大实测都不合格，见 DH2D.md 第十一节）。

## 2026-10-19 订正过的三件事（都有服务器原话，别再照旧认知跑）
1. `dola-seedream-5-0-pro` **只支持 share_service，不支持建专属端点**
   （`infer endpoint capability get` 的 supported_methods 只有 share_service）
   ⇒ 旧版"先建一个 ep-"整条路是错的，已删。
2. 数据面本来就能通（错误里带 request id），卡点是**模型没开通**：
   `models activate` 回 `ark: API error: /user/accountProfile/?hiddenNavbar=true`
   ⇒ 主人去 https://console.byteplus.com/user/accountProfile/ 完成开户+支付验证。
3. 传输改走**数据面直连**（POST {base_url}/images/generations，model 传模型名）。
   为什么不走 `arkcli +gen`：它在 platform profile 下强制要 `ep-…`，模型名一律被拦
   （实测 `--force` 也拦）；`arkcli api` 的 `--params` 又塞不进 base64
   （578KB 图 → 772KB 参数字符串，远超 Windows 命令行上限）。

## 用法
  py -3.14 tools/codex-scripts/mouthsheet-gen.py --check    # 只查前置，不出网、不花钱
  py -3.14 tools/codex-scripts/mouthsheet-gen.py --probe    # 纯文本生图，验证"模型开通了没有"（不发送她的脸）
  py -3.14 tools/codex-scripts/mouthsheet-gen.py --gen      # 真生成 4 张口型（会把脸发到 Ark）
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys

# ── 编码守门（encoding-guard 要求）：不带 -X utf8 调用时不许静默输出空 ──
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FACE = ROOT / 'outputs' / 'ref' / 'face-ref.png'
OUT = ROOT / 'outputs' / 'mouth-sheet'

MODEL = 'dola-seedream-5-0-pro'
DEFAULT_BASE = 'https://ark.ap-southeast.bytepluses.com/api/v3'
CONSOLE_FIX = 'https://console.byteplus.com/user/accountProfile/'

# 4 个 viseme：闭（基准）/ 半开（ə）/ 大开（a）/ 圆（o）
VISEMES = [
    {'tag': 'closed', 'jaw': 0.00,
     'text': '同一人物正面脸部的图像编辑：嘴巴保持自然闭合的浅笑，头发、眼睛、鼻子、脸型、肤色、光照、构图与参考图完全一致，不改变任何其它内容。写实摄影风格。'},
    {'tag': 'half', 'jaw': 0.35,
     'text': '同一人物正面脸部的图像编辑：只把嘴改成半张（说话中间态，上下唇分开约一指宽，露出一点上齿），头发、眼睛、鼻子、脸型、肤色、光照、构图与参考图完全一致，不改变任何其它内容。写实摄影风格。'},
    {'tag': 'open', 'jaw': 0.80,
     'text': '同一人物正面脸部的图像编辑：只把嘴改成张大说话（发「啊」，嘴张开、露出上齿与口腔、舌略可见），头发、眼睛、鼻子、脸型、肤色、光照、构图与参考图完全一致，不改变任何其它内容。写实摄影风格。'},
    {'tag': 'round', 'jaw': 0.60,
     'text': '同一人物正面脸部的图像编辑：只把嘴改成收圆（发「哦」，双唇前撮收成小圆口），头发、眼睛、鼻子、脸型、肤色、光照、构图与参考图完全一致，不改变任何其它内容。写实摄影风格。'},
]


def ark(*args, timeout=300):
    """跑 arkcli（Windows：which 拿到 .ps1 shim Python 起不来 ⇒ 直走 run.js）。"""
    run_js = os.path.join(os.environ.get('APPDATA', ''), 'npm', 'node_modules',
                          '@byteplus', 'ark-cli', 'scripts', 'run.js')
    cmd = (['node', run_js] if os.path.exists(run_js) else ['arkcli']) + list(args)
    env = dict(os.environ, ARKCLI_NO_UPDATE_NOTIFIER='1')
    r = subprocess_run(cmd, env, timeout)
    out = (r[0] or b'').decode('utf-8', 'replace') + (r[1] or b'').decode('utf-8', 'replace')
    try:
        # arkcli 会在 JSON **后**追加 "New arkcli version available…" ⇒ 整串 loads 会 Extra data
        j = json.JSONDecoder().raw_decode(out[out.index('{'):])[0]
    except Exception:                                                 # noqa: BLE001
        j = {'ok': False, 'raw': out[:400]}
    return r[2], j


def subprocess_run(cmd, env, timeout):
    import subprocess
    p = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env)
    return p.stdout, p.stderr, p.returncode


def api_key():
    """从 arkcli 自己的身份库取钥（只用于本机出网，**绝不打印**）。"""
    k = os.environ.get('ARK_API_KEY', '').strip()
    if k:
        return k
    base = Path(os.environ.get('USERPROFILE') or Path.home()) / '.arkcli-bp' / 'identities'
    for f in sorted(base.glob('*/apikey.json')):
        try:
            k = json.loads(f.read_text(encoding='utf-8')).get('api_key') or ''
        except Exception:                                             # noqa: BLE001
            k = ''
        if k:
            return k
    return ''


def base_url():
    return (os.environ.get('ARK_BASE_URL') or '').strip() or DEFAULT_BASE


def post_json(path, body, timeout=600):
    key = api_key()
    if not key:
        return 0, {'ok': False, 'why': '找不到 Ark API key（~/.arkcli-bp/identities/*/apikey.json）'}
    data = json.dumps(body, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(base_url().rstrip('/') + path, data=data, method='POST',
                                 headers={'Authorization': 'Bearer ' + key,
                                          'Content-Type': 'application/json',
                                          # 出网带正常 UA：边缘会拦空 UA（台账 P17）
                                          'User-Agent': 'gbt-mouthsheet/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode('utf-8', 'replace'))
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        return e.code, {'ok': False, 'http': e.code, 'raw': raw[:1200]}
    except Exception as e:                                            # noqa: BLE001
        return 0, {'ok': False, 'why': type(e).__name__ + ': ' + str(e)[:300]}


def check():
    """前置检查：参考图 / SSO / 账号验证 / 模型在册 / 钥在。任何一项缺都如实报缺 + 给那一行解法。"""
    rec = {'ok': False, 'face_ref': str(FACE), 'model': MODEL, 'steps': {}}
    if not FACE.is_file():
        rec['steps']['face_ref'] = {'ok': False, 'why': '参考图不在（先跑 mouth-lab.py 裁 face-ref.png）'}
        return rec
    rec['steps']['face_ref'] = {'ok': True, 'bytes': FACE.stat().st_size}

    rc, j = ark('auth', 'status', '--format', 'json')
    sso = ((j.get('byteplus_sso') or {}).get('identity') or {})
    rec['steps']['sso'] = {
        'ok': rc == 0 and bool(sso),
        'logged_in': j.get('logged_in'),
        'expired': (j.get('byteplus_sso') or {}).get('expired'),
        'verified': sso.get('verified'),
        'account': sso.get('account_id'),
    }
    if not rec['steps']['sso']['ok']:
        rec['steps']['sso']['fix'] = 'arkcli auth login'
        return rec
    if sso.get('verified') is not True:
        # arkcli-shared 的账号验证闸：verified=false 时不许做计费写入 ⇒ 由主人去 console 补
        rec['steps']['sso']['ok'] = False
        rec['steps']['sso']['fix'] = CONSOLE_FIX
        rec['steps']['sso']['why'] = ('账号资料/支付验证未完成（identity.verified=false）。'
                                      '证据：models activate 回 '
                                      '"ark: API error: /user/accountProfile/?hiddenNavbar=true"')
        rec['怎么解'] = ('主人在浏览器打开 %s 完成开户+支付验证；完事本脚本会自动变成就绪'
                        '（条件满足即重走，台账 P15）' % CONSOLE_FIX)
        return rec

    rc, j = ark('models', 'get', MODEL, '--format', 'json')
    rec['steps']['model'] = {'ok': rc == 0, 'version': j.get('primary_version'),
                             'why': None if rc == 0 else (j.get('error') or {}).get('message')}
    rec['steps']['api_key'] = {'ok': bool(api_key())}
    rec['ok'] = all(s.get('ok') for s in rec['steps'].values())
    if rec['ok']:
        rec['next'] = 'py -3.14 tools/codex-scripts/mouthsheet-gen.py --probe'
    return rec


def _first_url(j):
    for k in ('data', 'output', 'outputs', 'result'):
        v = j.get(k)
        if isinstance(v, list) and v:
            it = v[0]
            if isinstance(it, dict):
                for kk in ('url', 'image_url', 'output_url'):
                    if it.get(kk):
                        return it[kk]
        if isinstance(v, dict):
            for kk in ('url', 'image_url', 'output_url'):
                if v.get(kk):
                    return v[kk]
    return None


def probe():
    """纯文本生图：只验证「模型开通了没有 / 数据面通不通」，**不发送她的脸**。"""
    t0 = time.time()
    st, j = post_json('/images/generations',
                      {'model': MODEL, 'prompt': 'a single red apple on white background',
                       'size': '1K', 'response_format': 'url', 'watermark': False})
    url = _first_url(j)
    rec = {'ok': st == 200 and bool(url), 'http': st, 'model': MODEL,
           'secs': round(time.time() - t0, 1),
           'url': url, 'raw': None if (st == 200 and url) else j}
    print('<<<GBT-MOUTH-PROBE>>>')
    print(json.dumps(rec, ensure_ascii=False, indent=1))
    return rec


def gen(model=MODEL):
    OUT.mkdir(parents=True, exist_ok=True)
    b64 = base64.b64encode(FACE.read_bytes()).decode('ascii')
    made = []
    for v in VISEMES:
        t0 = time.time()
        st, j = post_json('/images/generations',
                          {'model': model, 'prompt': v['text'], 'image': [b64],
                           'size': '1K', 'response_format': 'url', 'watermark': False},
                          timeout=900)
        url = _first_url(j)
        item = {'tag': v['tag'], 'jaw': v['jaw'], 'http': st, 'url': url,
                'secs': round(time.time() - t0, 1), 'ok': False, 'file': None, 'bytes': -1,
                'sha16': None, 'raw': None}
        if url:
            dst = OUT / ('face-%s.png' % v['tag'])
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'gbt-mouthsheet/1.0'})
                with urllib.request.urlopen(req, timeout=300) as r:
                    blob = r.read()
                dst.write_bytes(blob)
                item.update(ok=len(blob) > 1024, file=str(dst), bytes=len(blob),
                            sha16=hashlib.sha256(blob).hexdigest()[:16])
            except Exception as e:                                    # noqa: BLE001
                item['raw'] = 'download failed: %s: %s' % (type(e).__name__, str(e)[:200])
        if not item['ok']:
            # P26：格式/失败类读数必须带原始载荷，不许只说"没拿到图"
            item['raw'] = item['raw'] or j
        made.append(item)
        print('  [%s] http=%s ok=%s %ss' % (v['tag'], st, item['ok'], item['secs']))

    idx = {'schema': 'gbt-mouth-sheet/v1', 'source_face': str(FACE), 'model': model,
           'base_url': base_url(), 'ts': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
           'items': made,
           'blend': '运行时按 viseme 权重在这些形状间线性混合（Live2D motion-sync 同一口径）'}
    (OUT / 'sheet.json').write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding='utf-8')
    print('<<<GBT-MOUTH-SHEET>>>')
    print(json.dumps({k: v for k, v in idx.items() if k != 'items'}, ensure_ascii=False, indent=1))
    print('items: %d ok / %d' % (sum(1 for m in made if m['ok']), len(made)))
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--probe', action='store_true', help='纯文本生图验证模型是否开通（不发送她的脸）')
    ap.add_argument('--gen', action='store_true')
    ap.add_argument('--model', default=MODEL)
    a = ap.parse_args()

    c = check()
    if a.check or not (a.probe or a.gen):
        print('<<<GBT-MOUTH-CHECK>>>')
        print(json.dumps(c, ensure_ascii=False, indent=1))
        sys.exit(0 if c.get('ok') else 3)
    if not c.get('ok'):
        print('<<<GBT-MOUTH-CHECK>>>')
        print(json.dumps(c, ensure_ascii=False, indent=1))
        sys.exit(3)
    if a.probe:
        sys.exit(0 if probe().get('ok') else 4)
    idx = gen(a.model)
    sys.exit(0 if all(m['ok'] for m in idx['items']) else 5)


if __name__ == '__main__':
    main()
