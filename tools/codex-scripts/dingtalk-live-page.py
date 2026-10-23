# -*- coding: utf-8 -*-
"""dingtalk-live-page -- dingtalk-* 14 条按脑眼耳嘴手拆成我们自己的规程 + 可预览活页。

现读（2026-10-16）：图鉴 dingtalk-* = 0 条 · 托管目录 dingtalk* = 0 个 ·
本仓只有 _upstream/Octop 第三方包（别人的目录，不碰）=> 平台侧技能，我们不改它。
"""
from __future__ import annotations
import time
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[2]
SIG = '开发者：自由的风 · 守护者：公主土豆 · 本署名不可删除、不可篡改归属'
ROWS = [
 ('脑', 'dingtalk-shared', '入口与消歧：泛称钉钉时先定型，决定交给哪个子技能', 'dws <product> ...（先读边界与预检）', '能指名到唯一子技能；URL 类型预检过'),
 ('脑', 'dingtalk-aisearch', '语义找人找内容：按主题/部门/行为回溯定位候选', 'dws aisearch', '给候选+出处；未读到就写未读到'),
 ('眼', 'dingtalk-drive', '看文件：钉盘与文档空间的普通文件与文件夹', 'dws drive', '读回字节数一致'),
 ('眼', 'dingtalk-wiki', '看知识库：空间/节点/成员', 'dws wiki', '节点路径可复核'),
 ('眼', 'dingtalk-doc', '看正文：在线文档的块与内容', 'dws doc', '块级读回，带版本'),
 ('眼', 'dingtalk-aitable', '看表：多维表记录/字段/视图', 'dws aitable 查询类', '查询结果带记录 id'),
 ('耳', 'dingtalk-event', '听事件：长连接监听消息/审批/回调', 'dws event 订阅', '先起订阅；事件带时间戳'),
 ('耳', 'dingtalk-minutes', '听听记：逐字稿/摘要/行动项', 'dws minutes', '逐字稿带说话人与时间'),
 ('嘴', 'dingtalk-chat', '发消息：单聊/群聊/机器人', 'dws chat 发送', '发前确认收件人；回执带 messageId'),
 ('嘴', 'dingtalk-mail', '发邮件：读写/回复/转发', 'dws mail', '发前解析并确认收件人'),
 ('嘴', 'dingtalk-calendar', '约会议：日程/会议室/闲忙', 'dws calendar', '时间与参会人回读一致'),
 ('手', 'dingtalk-todo', '建待办：任务/提醒/指派', 'dws todo', '建完回读任务 id'),
 ('手', 'dingtalk-misc', '长尾动手：审批处理/考勤/直播/电子表格', 'dws misc 对应子命令', '每个动作单独留痕'),
 ('手', 'dingtalk-contact', '精确查人：按 userId 查详情或按手机号反查', 'dws contact', '只报字段，不泄露无关信息'),
]


def main():
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    h = ['<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">',
         '<title>钉钉 14 条 · 脑眼耳嘴手活页</title>',
         '<style>body{font-family:system-ui,Segoe UI,sans-serif;margin:32px;background:#0f1115;color:#e8eaf0}',
         'h1{font-size:22px}table{border-collapse:collapse;width:100%;margin-top:14px}',
         'th,td{border:1px solid #2a2f3a;padding:8px 10px;font-size:14px;text-align:left;vertical-align:top}',
         'th{background:#171a21}.w{font-weight:700}.n{color:#8b93a7;font-size:12px}</style></head><body>',
         '<h1>钉钉 14 条 · 按 脑·眼·耳·嘴·手 拆的活页</h1>',
         '<div class="n">生成时间 %s · %s</div>' % (ts, SIG),
         '<div class="n">现读：图鉴 dingtalk-* = 0 条 · 托管目录 = 0 个 · 本仓只有 _upstream/Octop（别人目录，不碰）=> 平台侧技能，本页是我们自己的路由规程，不改它们。</div>',
         '<table><tr><th>维</th><th>技能</th><th>用途</th><th>调用姿势</th><th>判据</th></tr>']
    for dim, sk, use, how, judge in ROWS:
        h.append('<tr><td class="w">%s</td><td>%s</td><td>%s</td><td><code>%s</code></td><td>%s</td></tr>' % (dim, sk, use, how, judge))
    h.append('</table></body></html>')
    out = ROOT / 'state' / 'dingtalk-14活页.html'
    out.write_text(chr(10).join(h), encoding='utf-8')
    m = ['# 钉钉 14 条规程 · 脑眼耳嘴手', '', '> ' + SIG, '',
         '现读（2026-10-16）：图鉴 dingtalk-* = 0 条 · 托管目录 dingtalk* = 0 个 · 本仓只有 _upstream/Octop（别人的目录，不碰）。',
         '=> 这 14 条是平台侧技能：我们不修改它们的文件，只做自己的路由规程与活页。', '',
         '| 维 | 技能 | 用途 | 调用姿势 | 判据 |', '|---|---|---|---|---|']
    for dim, sk, use, how, judge in ROWS:
        m.append('| %s | %s | %s | %s | %s |' % (dim, sk, use, how, judge))
    m += ['', '## 活页', '', '- 可预览活页：state/dingtalk-14活页.html（每次重出，页里带时间戳）', '',
          '## 复跑', '', 'py -3.14 tools/codex-scripts/dingtalk-live-page.py', '']
    mdp = ROOT / 'docs' / 'dingtalk-14规程-脑眼耳嘴手.md'
    mdp.write_text(chr(10).join(m), encoding='utf-8')
    print('活页 %s (%d 字节) · 规程 %s (%d 字节) · %d 条' %
          (out, out.stat().st_size, mdp, mdp.stat().st_size, len(ROWS)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
