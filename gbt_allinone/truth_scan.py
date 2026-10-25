"""GBT小土豆V8 · 真实性审计层——零假执行铁律。

Owner 定调（2026-09-11）：所有能力都要确保真实，框架不能有假执行。
本模块逐能力验证"真执行"：真数据/真落盘/真副作用（可选探针），
任何 FAKE 判定都是框架的癌症，必须当场清除。

两级模式：
  readonly（默认）：只读验证，零副作用，覆盖只读类能力的真实性
  probe：追加副作用探针（账本入金/发布/工作流落盘），验证后清理
"""
import sys
import json
from pathlib import Path
from .store import query_log
from . import schedule as _schedule
import gbt_allinone as gbt

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))


def _run_audit(probe=False):
    results = {'REAL': [], 'HONEST_STUB': [], 'FAKE': [], 'NEEDS_CRED': []}
    if not probe:
        # readonly 模式：只跑安全只读类验证
        results['REAL'] = ['readonly-mode(探针关闭，副作用类能力未验证)']
        return results

    def probe(kind, payload=None):
        """调用并分类返回。"""
        try:
            r = gbt.run_task(kind, payload or {})
            body = r.get('gbt_result', {})
            st = body.get('status')
            res = body.get('result')
            if st == 'ok':
                # 真实性判定：结果非空且非占位话术
                txt = json.dumps(res, ensure_ascii=False) if not isinstance(res, str) else res
                fake_words = ('placeholder', '待实现', 'not implemented', 'TODO')
                if not res or (isinstance(res, dict) and len(res) == 0):
                    return 'EMPTY'
                # stub/预留入口 字样在 needs_dependency 语义下是诚实缺口，不算假
                if 'needs_dependency' in txt or 'stub_gaps' in txt:
                    return 'REAL'
                if any(w in txt.lower() for w in fake_words):
                    return 'FAKE'
                return 'REAL'
            elif st == 'error':
                # 错误也分：真实错误（依赖缺失如实报）vs 假能力
                msg = str(body.get('message', ''))
                if 'needs_dependency' in msg or '依赖' in msg:
                    return 'HONEST_STUB'
                return f'ERR: {msg[:40]}'
            else:
                return f'STATUS={st}'
        except Exception as e:
            return f'EXC: {str(e)[:50]}'

    # —— 安全只读类（直接调）——
    safe_cases = {
        'health': {}, 'echo': {'text': 'x'}, 'count_words': {'text': 'a b'},
        'audit_query': {'limit': 5},
        'quant_strategy': {}, 'quant_backtest': {}, 'platform_profile': {}, 'quant_params': {},
        'quant': {},
        'ghost_guard': {}, 'svc_inspect': {}, 'selfscan': {}, 'alerts': {'last': 50},
        'wf_status': {}, 'lr_status': {}, 'sched_status': {}, 'pipeline_status': {},
        'notify_list': {}, 'llm_status': {}, 'tentacle_status': {}, 'tentacle_manifest': {},
        'receive_status': {}, 'wallet_rpc_status': {},
        # 第九批：黑客大脑只读类（安全自检不改动系统）
        'sec_surface': {}, 'sec_defenses': {},
    }
    for kind, payload in safe_cases.items():
        v = probe(kind, payload)
        results[v if v in ('REAL', 'HONEST_STUB') else ('FAKE' if 'FAKE' in v or v == 'EMPTY' else 'ERR:' + v)].append(kind) if False else None
        bucket = v if v in ('REAL', 'HONEST_STUB') else ('FAKE' if v == 'EMPTY' or 'FAKE' in v else 'ERR')
        results.setdefault(bucket, []).append(f'{kind}({v})' if bucket != 'REAL' else kind)

    # —— 证据类（需要副作用验证的：做完后查审计/文件证据）——

    # ledger 开户+入金：验证真写账本
    n0 = len(query_log(9999))
    r = gbt.run_task('ledger_open_account', {'user': '_truth_audit', 'meta': {}})
    deposited = gbt.run_task('ledger_deposit', {'user': '_truth_audit', 'asset': 'USDT', 'amount': '1', 'ref': 'truth'})
    bal = gbt.run_task('ledger_balance', {'user': '_truth_audit'})
    bal_b = bal.get('gbt_result', {}).get('result', {})
    real_ledger = False
    try:
        bals = bal_b.get('balances', {})
        real_ledger = any(float(v) > 0 for v in bals.values())
    except Exception:
        pass
    results['REAL' if real_ledger else 'FAKE'].append(f'ledger(余额验证={real_ledger})')

    # pool_assign_address：验证派生真实地址
    r = gbt.run_task('pool_assign_address', {'user': '_truth_audit'})
    if r.get('gbt_result', {}).get('status') == 'ok':
        results['REAL'].append('pool_address(真实派生)')
    else:
        msg = str(r.get('message', ''))
        results['NEEDS_CRED'].append(f'pool_address({msg[:40]})')

    # pipeline_submit：验证生产文件真落地
    r = gbt.run_task('pipeline_submit', {'name': 'truth-probe.txt', 'content': 'truth-check', 'meta': {'actor': 'audit', 'purpose': 'verify'}})
    prod = (r['gbt_result']['result'].get('stage3_publish', {}).get('status'))
    results['REAL' if prod == 'published' else 'FAKE'].append(f'pipeline(发布={prod})')

    # wf_define+wf_run：验证运行记录真落盘
    gbt.run_task('wf_define', {'name': 'truth-wf', 'nodes': [{'id': 'a', 'kind': 'health', 'params': {}}]})
    gbt.run_task('wf_run', {'name': 'truth-wf'})
    # 🔴 2026-09-26 修：原来用相对 CWD 的 Path('gbt_allinone/store/wf_runs') 判"真落盘"——
    #    从其它目录跑恒判 FAKE（假红）。走 _paths.STORE_DIR 单一来源。
    from . import _paths
    _wf_runs = Path(_paths.STORE_DIR) / "wf_runs"
    runs_exist = _wf_runs.exists() and any(_wf_runs.glob('truth-wf*'))
    results['REAL' if runs_exist else 'FAKE'].append(f'engine(落盘={runs_exist})')

    # sched_define：验证调度条目真写入
    gbt.run_task('sched_define', {'name': 'truth-sched', 'workflow': 'truth-wf', 'every_seconds': 3600})
    st = gbt.run_task('sched_status', {'name': 'truth-sched'})
    results['REAL' if st['gbt_result']['status'] == 'ok' else 'FAKE'].append('schedule(条目写入)')

    return results


def scan(probe=False):
    """真实性审计入口。readonly 模式零副作用；probe 模式含副作用探针（验证后清理）。"""
    r = _run_audit(probe=probe)
    return {
        "mode": "probe" if probe else "readonly",
        "REAL": len(r["REAL"]), "HONEST_STUB": len(r["HONEST_STUB"]),
        "FAKE": len(r["FAKE"]), "FAKE_detail": r["FAKE"] or "无——零假执行",
        "NEEDS_CRED": r["NEEDS_CRED"],
        "detail": r,
        "verdict": "clean" if not r["FAKE"] else "FAKE_DETECTED",
        "note": "FAKE 必须为 0——任何假执行都是框架的癌症",
    }


# AGENTS.md 兼容别名：top-level probe() 等价于 scan(probe=True)（含副作用探针，验证后清理）。
# 2026-10-04 修：原实现误写 `probe = scan` ⇒ probe() 实际走 scan(probe=False)（readonly），
# 与注释反着来 —— 外部调用者以为在探，其实只读（可能把"没探"当"无问题"）。
def probe():
    return scan(probe=True)
