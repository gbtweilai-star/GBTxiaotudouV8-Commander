# -*- coding: utf-8 -*-
"""intent_route -- 意图路由能力包主程序

被 cap_pack 以如下方式调用：
    python.exe -X utf8 main.py <action> <json_params>

actions:
    route   {"query": "...", "top": 8}   → 候选能力（规则优先 + 统计兜底）
    domains {}                            → 32 域统计
    kinds   {"domain": "recon"}           → 某域 / 全部能力名
    stats   {}                            → 索引自检

输出：单行 JSON 到 stdout。纯标准库，零依赖。
"""
import sys
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
CAPS_PATH = os.path.join(HERE, 'caps.json')

STOP_CHARS = '的了在是我有个把这那一下吗呢吧啊就都也还'
STOP_GRAMS = {
    '帮我', '什么', '有什', '一个', '这个', '那个', '可以', '怎么', '如何',
    '一下', '我的', '你的', '现在', '然后', '就是', '还是', '以及', '或者',
    '需要', '进行', '通过', '因为', '所以', '如果', '但是', '不是', '没有',
    '个视', '么样', '这儿', '那儿', '看看',
}
INTERNAL_DOMAINS = {'pipeline', 'infra', 'framework', 'ui', 'desktop', 'security', 'data', 'engine'}

# L1 规则层：高频意图 → 能力位（命中即置顶）
INTENT_MAP = [
    (('剪视频', '剪辑', '剪片', '成片', '视频剪辑'), ['edit_pipeline', 'media_run', 'media_pipeline']),
    (('看屏幕', '屏幕上', '截屏', '看界面', '看桌面', '看看桌面'), ['body_see', 'vision_grounding', 'tentacle']),
    (('在干什么', '在干嘛', '在做什么', '状态怎么样', '她现在', '现在什么样', '忙什么'), ['body_map', 'tentacle', 'duty_board']),
    (('读窗口', '窗口列表', '有哪些窗口', '看窗口'), ['tentacle', 'vision_grounding']),
    (('建模', '零件', '三维模型', 'CAD', '工程图', '导出STEP', '3D打印'), ['cadgen']),
    (('上下文', '上下文异常', '窗口溢出', '上下文超了'), ['context_guard']),
    (('动效', '动画', '特效', '组件', '微交互'), ['art_chain', 'bits_kit', 'motion_kit', 'art_brief']),
    (('放大', '高清', '4K', '锐化', '洗图'), ['comfy_native']),
    (('数字人', '口播', '照片说话', '让照片说'), ['digital_human']),
    (('混音', '母带', '音量归一'), ['audio_mix']),
    (('提取音频', '抽音频', '取声音', '抽出音轨', '音频提取', '音频', '音轨'), ['audio_extract']),
    (('出视频', '生成视频', '做视频'), ['comfy_cloud', 'i2v_agnes', 'hunyuan_video']),
    (('自我纠正', '自主纠错', '自动修', '自己修好', '自己修'), ['autopilot', 'replan_loop', 'think_loop']),
    (('七步链', '执行链', '不可跳步'), ['chain_kernel']),
    (('调研', '情报', '找资料', '研究一下'), ['research_intel', 'self_intake', 'scrapling']),
    (('抓网页', '爬取', '抓取网页'), ['scrapling', 'browser']),
    (('回忆', '之前说过', '记忆里', '想起来'), ['memory_manager', 'brain_vault', 'obsidian_vault']),
    (('省内存', '内存压缩', '压缩模型'), ['offload_distill', 'quant_plan', 'transformer']),
    (('部署', '上线', '发布上线'), ['one_key_deploy', 'pipeline_submit', 'mirror_release']),
    (('巡检', '探活', '服务还活着'), ['svc_inspect']),
    (('提醒', '定时提醒', '别忘了'), ['reminder']),
    (('念一下', '说出来', '朗读', '语音播报'), ['body_say', 'voice']),
    (('点击', '点按', '打字', '输入文字'), ['body_click', 'body_type']),
    (('画个图', '生成图', '出图', '画一张'), ['comfyui', 'comfy_native', 'art_chain']),
    (('写代码', '改代码', '改文件'), ['code_patch', 'git_read', 'git_write']),
    (('版本回滚', '查看提交', 'git', '回滚'), ['git_read', 'git_write']),
    (('任务进度', '长任务', '任务图'), ['lr_status', 'task_graph', 'long_run_supervisor']),
    (('知识库', '查资料库', '百科'), ['wiki_graph', 'doc_intake', 'memory_manager']),
    (('思维导图', '脑图'), ['thebrain_bridge']),
    (('看这个图', '识别图片', '图里是什么'), ['vision', 'vision_grounding']),
    # 逆向 / 反向工程（REA）
    (('逆向', '反编译', '反汇编', '无源码', '二进制分析', 'APK', '.NET', 'Electron分析'),
     ['rea_reverse', 'recon_distill', 'sec_llm']),
    (('吞噬', '吞天', '吸收能力', '自我进化'), ['devour_github', 'devour_pulse', 'devour_scan']),
]


def norm(s):
    return re.sub('[%s]' % STOP_CHARS, '', s or '')


def kw_match(k, q):
    kn, qn = norm(k), norm(q)
    if not kn:
        return False
    if kn in qn:
        return True
    cs = set(kn)
    if len(cs) >= 3:
        return len(cs & set(qn)) / len(cs) >= 0.80
    return False


def grams(s):
    s = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', ' ', s or '')
    out = set()
    for w in s.split():
        if len(w) < 2:
            continue
        for i in range(len(w) - 1):
            g = w[i:i + 2]
            if g not in STOP_GRAMS:
                out.add(g)
    return out


def stat_score(qg, cap):
    ph = grams(' '.join(cap.get('p') or []))
    de = grams(cap.get('t') or '')
    s = len(qg & ph) * 3.0 + len(qg & de) * 1.0
    d = cap.get('t') or ''
    if any(h in d for h in ('常用说法', '入口', '总入口', '一键', '人话')):
        s *= 1.15
    if cap.get('d') in INTERNAL_DOMAINS:
        s *= 0.35
    if cap.get('p'):
        s *= 1.2
    return s


def load_caps():
    with open(CAPS_PATH, encoding='utf-8') as f:
        return json.load(f)


def action_route(caps, params):
    q = str(params.get('query') or '').strip()
    top = int(params.get('top') or 8)
    if not q:
        return {'ok': False, 'error': 'user_error: 需要 query'}
    by_kind = {c['k']: c for c in caps}
    qg = grams(q)

    seen, ordered = set(), []
    for kws, kinds in INTENT_MAP:
        if any(kw_match(k, q) for k in kws):
            for rank, kind in enumerate(kinds):
                if kind in by_kind and kind not in seen:
                    seen.add(kind)
                    ordered.append((kind, 'rule', 100.0 - rank))

    scored = []
    for c in caps:
        if c['k'] in seen:
            continue
        s = stat_score(qg, c)
        if s > 0:
            scored.append((s, c['k']))
    scored.sort(key=lambda x: -x[0])
    for s, kind in scored[:top * 2]:
        ordered.append((kind, 'stat', round(s, 1)))

    out = []
    for kind, layer, score in ordered[:top]:
        c = by_kind.get(kind, {})
        out.append({
            'kind': kind,
            'domain': c.get('d'),
            'layer': layer,
            'score': score,
            'safe': c.get('s'),
            'desc': (c.get('t') or '')[:90],
            'phrases': (c.get('p') or [])[:5],
            'call': 'api.run_task("%s", {...})' % kind,
        })
    return {'ok': True, 'query': q, 'top': len(out), 'candidates': out,
            'rule_hits': len(seen), 'stat_hits': len(scored)}


def action_domains(caps):
    from collections import Counter
    cnt = Counter(c['d'] for c in caps)
    return {'ok': True, 'total': len(caps), 'domains': dict(cnt.most_common())}


def action_kinds(caps, params):
    dom = params.get('domain')
    rows = [{'kind': c['k'], 'domain': c['d'], 'safe': c.get('s')}
            for c in caps if not dom or c['d'] == dom]
    return {'ok': True, 'count': len(rows), 'kinds': rows}


def main(argv):
    caps = load_caps()
    action = 'route'
    params = {}
    if len(argv) > 1 and argv[1].strip():
        action = argv[1].strip()
    if len(argv) > 2 and argv[2].strip():
        try:
            params = json.loads(argv[2])
        except Exception as e:
            print(json.dumps({'ok': False, 'error': 'bad params json: %s' % e}, ensure_ascii=False))
            return 1

    try:
        if action == 'route':
            r = action_route(caps, params)
        elif action == 'domains':
            r = action_domains(caps)
        elif action == 'kinds':
            r = action_kinds(caps, params)
        elif action == 'stats':
            r = {'ok': True, 'caps': len(caps), 'with_phrases': sum(1 for c in caps if c.get('p'))}
        else:
            r = {'ok': False, 'error': 'unknown action: %s (route/domains/kinds/stats)' % action}
    except Exception as e:
        r = {'ok': False, 'error': '%s: %s' % (type(e).__name__, str(e)[:200])}

    print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
