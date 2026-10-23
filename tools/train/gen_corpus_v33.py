# v33: 修语料配比 —— 把 ComfyUI 族重复到不再被台账族淹没，并给独有开头
import hashlib, json
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / '.scratch' / 'self_knowledge_v32.jsonl'
OUT = ROOT / '.scratch' / 'self_knowledge_v33.jsonl'
MAN = ROOT / 'state' / 'train' / 'corpus_v33_manifest.json'
rows = [json.loads(l) for l in SRC.read_text(encoding='utf-8').splitlines() if l.strip()]
REP = ('秋叶版图示例', '秋叶版契约', '节点连线语义', '节点名册', '节点契约', '秋叶版规程')
FIX = ('的完整 API 格式', '的 ComfyUI API 图（class_type/inputs')
fixed = 0
for r in rows:
    o = r.get('output') or ''
    if o.startswith('**') and FIX[0] in o:
        r['output'] = o.replace(FIX[0], FIX[1], 1)
        fixed += 1
extra = []
for r in rows:
    if r.get('family') in REP:
        for _ in range(5):
            extra.append(dict(r))
out = rows + extra
OUT.write_text(''.join(json.dumps(r, ensure_ascii=False) + chr(10) for r in out), encoding='utf-8')
blob = OUT.read_bytes()
fam = defaultdict(int)
for r in out:
    fam[r.get('family') or '?'] += 1
MAN.write_text(json.dumps({'gen': 'v33', 'parent': 'v32', 'count': len(out), 'bytes': len(blob),
                           'sha256': hashlib.sha256(blob).hexdigest(),
                           'by_family': dict(sorted(fam.items(), key=lambda x: -x[1]))},
                          ensure_ascii=False, indent=1), encoding='utf-8')
print('v33', len(out), '| base', len(rows), '| extra', len(extra), '| fixed_prefix', fixed,
      '| bytes', len(blob), '| sha', hashlib.sha256(blob).hexdigest()[:16])
for k in REP:
    print('  ', k, fam.get(k))
