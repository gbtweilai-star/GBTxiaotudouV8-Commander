"""GBT小土豆V8 · 根治环（root_fix）——她自己的根源追踪纪律。

Owner 定调（2026-09-11）：发现问题必须追踪根源彻底修复，不允许"症状消失"式打补丁。
本模块把这套纪律变成她的原生能力：

  diagnose(symptom)   症状 → 根源诊断（五问法：哪里报的/数据从哪来/分类在哪断/豁免有几个/规则还是判例）
  patch_debt()        技术债盘点（判例法行数/白名单项数/豁免分支/审计轮转次数——补丁债量化）
  law()               根治铁律（写死的纪律——任何新修复必须过这五条）

根治铁律（写进代码的宪法）：
  1. 症状消失 ≠ 修复——必须能指出"根源在哪一层"（数据/分类/规则/结构）
  2. 禁止新增判例法（or key in (...)、reason 字符串猜测）——分类必须在源头
  3. 禁止枚举式白名单追新——规则化判定或单一来源引用
  4. 修复前先量化债（patch_debt），修复后债必须减少——债不降的修复是假修复
  5. 修复必须带防复发锁（测试或常驻检测），没有锁的修复会复发
"""
import json
import re
import time
import hashlib
from pathlib import Path

from . import _paths

_BASE = Path(__file__).resolve().parent


def _audit(event, meta):
    try:
        from .store import audit
        audit(event, meta)
    except Exception:
        pass


# ── 技术债量化（修复前后的对照基准）──

def patch_debt() -> dict:
    """补丁债盘点：判例法/白名单枚举/豁免分支/审计轮转——量化到数字。"""
    debt = {}

    # 1) selfscan 判例法（信号分级里 or 开头的猜 reason 行）
    ss = (_BASE / 'selfscan.py').read_text(encoding='utf-8', errors='replace')
    m = re.search(r'# 信号分级.*?sig = ', ss, re.S)
    if m:
        debt['selfscan_判例行'] = len([l for l in m.group(0).split('\n')
                                       if l.strip().startswith('or')])

    # 2) hygiene 家根枚举（HOME_ALLOWED 集合大小）
    hy = (_BASE / 'hygiene.py').read_text(encoding='utf-8', errors='replace')
    m2 = re.search(r'HOME_ALLOWED = \{(.*?)\}', hy, re.S)
    debt['hygiene_白名单项'] = len(re.findall(r'"[^"]+"', m2.group(1))) if m2 else 0

    # 3) 豁免分支（hygiene 里带注释的 continue）
    debt['hygiene_豁免分支'] = len(re.findall(r'continue\s*#', hy))

    # 4) 审计轮转（archived_logs 里的 audit-* 文件——每次轮转=一次症状消失史）
    arch = _BASE / 'archived_logs'
    debt['审计轮转次数'] = len(list(arch.rglob('audit*.jsonl'))) if arch.exists() else 0

    debt['合计'] = sum(v for v in debt.values() if isinstance(v, int))
    debt['checked_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
    return debt


# ── 症状 → 根源诊断（五问法）──

def diagnose(symptom: str) -> dict:
    """对一个症状做根源诊断：五问法定位断在哪一层。

    symptom: 症状描述（如 'hygiene 报 messy' / 'selfscan P1'）
    """
    if not symptom:
        raise ValueError('需要 symptom：症状描述')
    t0 = time.time()
    answers = []

    # 问1：症状在哪报告？（哪个扫描器/层）
    reporters = []
    for kind, hint in (('selfscan', ['selfscan', 'P0', 'P1', '体检', '信号']),
                       ('file_hygiene', ['hygiene', 'messy', '家根', '游离']),
                       ('signature_guard', ['署名', 'signature', 'missing']),
                       ('ghost_guard', ['ghost', '幽灵', '复发']),
                       ('cross_scan', ['交叉', 'cross'])):
        if any(h in symptom for h in hint):
            reporters.append(kind)
    answers.append(('谁在报', reporters or ['未识别——查症状描述']))

    # 问2：数据从哪来？（该报告的输入链）
    chains = {
        'selfscan': '审计事件(store/audit.jsonl) ← api.run_task 的 error/user_error 分类',
        'file_hygiene': '家根/包内文件系统 ← inventory._classify 归属',
        'signature_guard': '框架页面扫描 ← signature._scan_pages ← inventory 归属',
        'ghost_guard': '目录树+注册表 ← 九维检测',
        'cross_scan': '六扫描器互证 + 注册表/导入/磁盘交叉',
    }
    answers.append(('数据链', [chains.get(r, '未知') for r in reporters[0:1]] or ['先定位报告者']))

    # 问3：分类在哪断？（源头分类 or 下游猜测）
    is_source_classified = 'user_error' in (_BASE / 'api.py').read_text(encoding='utf-8', errors='replace')
    answers.append(('源头分类', ['已就位（user_error/error 分流）' if is_source_classified
                                 else '缺失——api 层还是一把抓']))

    # 问4：当前债值（对照基准）
    answers.append(('当前补丁债', patch_debt()['合计']))

    # 问5：该用规则还是判例？（根治方向）
    verdict_rule = ('规则/源头分类（判例法已退役）' if is_source_classified
                    else '先做源头分类，再谈其他')
    answers.append(('根治方向', [verdict_rule]))

    result = {'ok': True, 'symptom': symptom[:200], 'five_questions': answers,
              'law': LAW, 'elapsed_ms': round((time.time() - t0) * 1000, 1)}
    _audit('root_fix_diagnose', {'symptom': symptom[:80], 'debt': answers[3][1]})
    return result


LAW = [
    '症状消失 ≠ 修复——必须指出根源在哪一层',
    '禁止新增判例法（or key in / reason 猜测）——分类在源头',
    '禁止枚举白名单追新——规则化或单一来源',
    '修复前后债必须下降——债不降的是假修复',
    '修复必须带防复发锁——没锁的会复发',
]


def law() -> dict:
    """根治铁律（宪法查询）。"""
    return {'ok': True, 'laws': LAW,
            'note': '任何修复 PR/补丁过不了这五条 = 打回重做'}




# ── 坑册（pit_log）：一个坑踩两次 = 根治失败 ──

_PIT_PATH = _paths.STORE_DIR / 'pit_log.json'
_WORKLOG_PATH = _paths.STORE_DIR / 'work_log.jsonl'
_PROTECT_FILES = [
    # 源码保护清单：这些文件被删/被清空 = 框架残废，开工查看必须先验
    '_paths.py', 'api.py', 'caps_registry.py', 'engine.py', 'store.py',
    'selfscan.py', 'ghost_guard.py', 'root_fix.py', 'inventory.py',
    'hygiene.py', 'signature.py', 'mirror_space.py', 'qiankun.py',
    'tests/test_framework.py',
]


def _load_pits() -> list:
    try:
        return json.loads(_PIT_PATH.read_text(encoding='utf-8')).get('pits', [])
    except Exception:
        return []


def _save_pits(pits: list) -> None:
    _PIT_PATH.write_text(json.dumps(
        {'pits': pits, 'note': '坑册：踩过的坑与防复发锁——开工先查，一个坑不踩两次'},
        ensure_ascii=False, indent=2), encoding='utf-8')


def pit_record(pit: str, root_cause: str, lesson: str, guard: str = '') -> dict:
    """登坑：现象 + 根源 + 教训 + 防复发锁。同坑（指纹相似）拒绝重复登记。"""
    for key, val in (('pit', pit), ('root_cause', root_cause), ('lesson', lesson)):
        if not val:
            raise ValueError(f'需要 {key}：坑册三要素缺一不可')
    pits = _load_pits()
    fp = _pit_fp(pit)
    for old in pits:
        if _pit_fp(old['pit']) == fp:
            _audit('pit_duplicate', {'pit': pit[:60], 'first_at': old.get('at')})
            return {'ok': False, 'duplicate': True,
                    'message': f"这坑已踩过（{old.get('at', '')[:10]}）：{old['pit'][:60]}——直接用现有教训，不重复登记",
                    'existing': old}
    entry = {'pit': pit[:300], 'root_cause': root_cause[:300], 'lesson': lesson[:300],
             'guard': guard[:160], 'at': time.strftime('%Y-%m-%dT%H:%M:%S')}
    pits.append(entry)
    _save_pits(pits)
    _audit('pit_recorded', {'pit': pit[:60], 'guard': guard[:60] or '无锁（待补）'})
    return {'ok': True, 'total': len(pits), 'entry': entry,
            'note': '登记成功。guard 非空时应在 tests/test_framework.py 建同名防复发测试'}


def _pit_fp(pit: str) -> str:
    """坑指纹：去空白小写——同一现象换个说法也算同坑。"""
    return re.sub(r'\s+', '', pit.lower())[:120]


def pit_check(keywords: str) -> dict:
    """开工查坑：关键词命中已踩过的坑——先看再动手的第一步。"""
    if not keywords:
        raise ValueError('需要 keywords：任务/症状关键词')
    hits = []
    for p in _load_pits():
        blob = p['pit'] + p['root_cause'] + p['lesson']
        if any(k in blob for k in keywords.split() if len(k) >= 2):
            hits.append(p)
    return {'ok': True, 'keywords': keywords[:120], 'hits': len(hits), 'pits': hits[:8],
            'total_pits': len(_load_pits())}


# ── 开工查看：先看再动手，严禁盲打 ──

def pre_work(task: str = '') -> dict:
    """开工查看（ 不管做什么先看）：任务相关坑 + 框架健康 + 源码保护 + 家规——四看齐了才许动手。"""
    # 看一：任务相关坑（防重踩）
    pits = pit_check(task).get('pits', []) if task else []
    # 看二：框架健康（四扫描器 + 债值）
    health = {'verdicts': {}, 'debt_total': None}
    try:
        from . import selfscan as _ss
        r = _ss.scan()
        health['verdicts']['selfscan'] = r.get('verdict')
        health['debt_total'] = patch_debt().get('合计')
    except Exception as e:
        health['verdicts']['selfscan'] = f'probe_failed: {e}'
    # 看三：源码保护（关键文件在不在、空没空）
    missing, empty = [], []
    for name in _PROTECT_FILES:
        p = _BASE / name
        if not p.exists():
            missing.append(name)
        elif p.stat().st_size < 100:
            empty.append(name)
    # 看四：家规在场（LAYOUT.md——文件分类纪律的唯一文本）
    layout = (_BASE / 'LAYOUT.md')
    health['layout_md'] = layout.exists() and layout.stat().st_size > 100
    return {'ok': True, 'task': (task or '')[:160],
            'related_pits': pits, 'pit_total': len(_load_pits()),
            'health': health,
            'source_guard': {'missing': missing, 'empty': empty},
            'verdict': 'BLOCK——先处理红灯再动手' if (missing or empty or not health['layout_md'])
                       else 'GO——坑已避开、家底完好，可以动手'}
    # （下方 unreachable——保持结构清晰故不合并）


# ── 工作日志：每次工作都会成长、有据可查 ──

# 幂等窗口（秒）：**同内容**在窗口内只落一条。
#
# 为什么需要（今晚实测到的）：落账脚本跑第二遍时，`at` 每次都不同 ⇒ 拿时间戳当身份等于没做幂等。
# 实测后果：`work_log.jsonl` 多一条 + 生命事件多一条（`life/events.jsonl` 第 165/166 行），
# 而 `work_log_mirrored` 还报 `duplicate=false` —— 镜像那层按**含 at 的 digest** 判，永远不重合。
#
# 口径（承 O73 与 `POST /webhook` 契约）：**写入前查指纹**，不靠事后删。
# 保护点是**唯一收口** —— 在这里挡住，主账与生命事件两个 sink 一起不再重复。
_WORKLOG_DEDUPE_WINDOW_S = 300.0
_WORKLOG_SCAN_TAIL = 40


def _worklog_fingerprint(row: dict) -> str:
    """内容指纹：**只取 action/title/detail，不含 at** —— 时间戳不参与身份。"""
    parts = (
        str(row.get('action') or ''),
        ' '.join(str(row.get('title') or '').split()),
        ' '.join(str(row.get('detail') or '').split()),
    )
    return hashlib.sha256('\u241f'.join(parts).encode('utf-8')).hexdigest()[:32]


def _worklog_recent() -> list:
    """只读尾巴（不整文件载入）。"""
    try:
        text = _WORKLOG_PATH.read_text(encoding='utf-8')
    except Exception:
        return []
    rows = []
    for line in text.strip().split('\n')[-_WORKLOG_SCAN_TAIL:]:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def _worklog_duplicate_of(row: dict, window_s: float | None = None):
    """写入前查：同指纹且未过窗口 ⇒ `(True, 旧行, 年龄秒)`；否则 `(False, None, None)`。"""
    window = _WORKLOG_DEDUPE_WINDOW_S if window_s is None else float(window_s)
    fingerprint = _worklog_fingerprint(row)
    now = time.time()
    for prev in reversed(_worklog_recent()):
        if _worklog_fingerprint(prev) != fingerprint:
            continue
        try:
            age = now - time.mktime(time.strptime(str(prev.get('at')), '%Y-%m-%dT%H:%M:%S'))
        except Exception:                                        # noqa: BLE001
            continue
        if 0 <= age <= window:
            return True, prev, int(age)
    return False, None, None


def work_log(action: str, title: str, detail: str = '') -> dict:
    """记工作日志（action: start/done/lesson）——收工必记债值与测试结果，成长可回放。"""
    if action not in ('start', 'done', 'lesson'):
        raise ValueError('需要 action：start/done/lesson')
    if not title:
        raise ValueError('需要 title：这次工作做了什么')
    row = {'at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'action': action,
           'title': title[:200], 'detail': detail[:400]}
    if action == 'done':
        # 收工自动带债值快照——下次开工可对照「债有没有回升」
        try:
            row['debt_total'] = patch_debt().get('合计')
        except Exception:
            pass
    duplicate, prev, age = _worklog_duplicate_of(row)
    if duplicate:
        _audit('work_log_duplicate_skipped', {
            'action': action, 'title': title[:60],
            'fingerprint': _worklog_fingerprint(row)[:16],
            'age_s': age, 'window_s': _WORKLOG_DEDUPE_WINDOW_S,
        })
        return {'ok': True, 'duplicate': True, 'skipped': True, 'row': row,
                'first_at': (prev or {}).get('at'), 'age_s': age,
                'window_s': _WORKLOG_DEDUPE_WINDOW_S}
    with _WORKLOG_PATH.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + chr(10))
    _audit('work_log', {'action': action, 'title': title[:60]})
    # R117 · 推式镜像成生命事件：life_archive.remember_work_log() 本来就是为这条日志
    # 写的（source.kind = "root_fix.work_log"，按 digest 幂等），但此前只有
    # ingest_sources() 的拉式回填、没有一处推送 —— 于是"日志落盘即形成生命事件"
    # 不成立，test_root_fix_work_log_mirrors_into_life_timeline 一直是红。
    # 不连坐：工作日志是主账、生命事件是副本；副本失败主账照写，并且落审计（不静默）。
    try:
        from . import life_archive
        _mirrored = life_archive.remember_work_log(row)
        _audit('work_log_mirrored', {'action': action, 'ok': bool(_mirrored.get('ok', True)),
                                     'duplicate': bool(_mirrored.get('duplicate'))})
    except Exception as exc:  # noqa: BLE001
        _audit('work_log_mirror_failed', {'action': action,
                                          'error': f'{type(exc).__name__}: {exc}'})
    # 成功路径也**明说** `duplicate: False` —— 不让"键不存在"去表达"没重复"
    # （同族教训：`[取不到]` 与 `0` 必须分得开，别让缺席当答案）。
    return {'ok': True, 'duplicate': False, 'skipped': False, 'row': row}


def work_log_read(limit: int = 20) -> dict:
    """回看工作日志（最近 N 条）——成长有据可查。"""
    rows = []
    try:
        for line in _WORKLOG_PATH.read_text(encoding='utf-8').strip().split(chr(10))[-limit:]:
            if line.strip():
                rows.append(json.loads(line))
    except Exception:
        pass
    return {'ok': True, 'rows': rows, 'count': len(rows)}


def seed_pits() -> dict:
    """预登记坑册（幂等：已存在的同坑跳过）。"""
    rows = []
    rows.append(pit_record('内联 python -c 带嵌套引号 -> SyntaxError: unterminated string literal', 'PowerShell/CMD 对双引号转义与 Python 字面量冲突', '严禁内联 python -c 写含引号代码', '写 _*.py 辅助脚本用后即删'))
    rows.append(pit_record('GBK 控制台把中文输出成 乱码/???? -> 误判为代码 bug', 'Windows 控制台默认 GBK，Python 输出 UTF-8 被错解', '判断真实内容必须显式 UTF-8', "sys.stdout.reconfigure(encoding='utf-8')"))
    rows.append(pit_record('utf-8-sig(BOM) 文件用 utf-8 读 -> 首个 key 前混入 \\ufeff -> json 解析失败', 'BOM 文件当无 BOM 读', '读写编码规则固定：读 utf-8-sig、写 utf-8-sig（BOM 文件）', "统一 io.open(encoding='utf-8-sig')"))
    rows.append(pit_record('测试把数据写进家根 store -> 家根被污染', '测试与生产共用物理目录，无隔离', '测试必须走隔离 store', '_paths.py 单一来源 + GBT_STORE_DIR 环境变量'))
    rows.append(pit_record('Windows 下 relative_to(ROOT)+CWD 解析漂移 -> 静默创建家根 store/ 孤儿目录', '路径解析依赖 CWD，未锚定 ROOT', 'store 路径一律基于 __file__ 的 ROOT 绝对解析', '全部模块引用 _paths.STORE_DIR'))
    rows.append(pit_record('多线程并发写审计 JSONL 无锁 -> 出现半行损坏（第 34 行中断）', 'JSONL 追加写非原子，无进程内锁', '审计写入必须加锁', 'store.py 用 threading.Lock 保护 audit+flush'))
    rows.append(pit_record('审计 error 事件语义过载（用法错误与真故障混记）-> 下游只能判例法猜', '错误未在源头分类，ValueError 与真 bug 同为 error', '错误必须在产生处分类', 'api.run_task 源头分流 user_error / error'))
    rows.append(pit_record('扫描器扫到自己的临时产物（观察者效应）-> 误报游离文件', '扫描器与运行环境共用目录，不区分自身足迹', '扫描器必须跳过自身与瞬态文件', 'inventory._classify 归类 transient + 自身跳过'))
    added = sum(1 for r in rows if r.get("ok"))
    dup = sum(1 for r in rows if r.get("duplicate"))
    return {"ok": True, "registered": added, "duplicates": dup, "total": len(_load_pits())}
