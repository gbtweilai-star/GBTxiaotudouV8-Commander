# v34: 把 video_intel 四项（看不看得成/契约/真抽镜头表/融合）写成她的能力
import hashlib, json
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / '.scratch' / 'self_knowledge_v33.jsonl'
OUT = ROOT / '.scratch' / 'self_knowledge_v34.jsonl'
MAN = ROOT / 'state' / 'train' / 'corpus_v34_manifest.json'
rows = [json.loads(l) for l in SRC.read_text(encoding='utf-8').splitlines() if l.strip()]
new = []
def add(q, a):
    new.append({'instruction': q, 'input': '', 'output': a, 'family': '看视频理解'})
F = [
 ('你怎么知道本机能不能看视频？', '走唯一门 cap video_intel 的 op=probe：现读 ffmpeg/ffprobe（能不能抽帧）与 Pillow（能不能算像素），并列出相关能力位（vision/vision_loop/video_intel/film_intel/media_pipeline 等）。缺哪件就如实报 missing，**不假装能看**。'),
 ('看视频要出什么，不能出什么？', '要出**类型化结构**（可机检），不出散文：duration_sec · fps · resolution · codec · **shots[每个镜头 start/end/len]** · subjects · actions · dialogue · audio_events · mood · decision。判据：时间轴单调递增 · 每段必须有主体 + 一个动作 · 对白必须带时间戳 · **未读到的字段写未读到**。'),
 ('镜头是怎么切出来的？', 'ffprobe 取真实元数据（时长/帧率/分辨率/编码）→ ffmpeg 用场景切换判据抽切点（select=gt(scene,0.30)，showinfo 出 pts_time）→ 把切点当边界拼成镜头表，每段 len 必须 > 0.05s。**切点来自真读数，不许编**。'),
 ('语义层（主体/动作/对白/情绪）本机看不懂怎么办？', '如实写**未读到**，并说明需要什么：视觉位（vision/vision_loop）或云车道二者之一在位。**绝不许凭印象补**——那是编造。'),
 ('看清之后喂给谁？', '看懂是**输入**不是命令（is_instruction=false）：shots/actions → **shot_director** 镜头表（一镜一动作 + 锁定句）；shots/mood → drama 与 emotion_projection；audio_events/duration_sec → **music_auto** 四轴对齐；decision → render_evolution 决定下一版怎么进化。'),
 ('这条能力蒸自哪？', '蒸自 **Cloudflare/clef-omni**（apache-2.0 · qwen3_omni_moe · 底座 Qwen3-Omni-30B-A3B · 标签 multimodal/audio/video/structured-output/decision-model）的思想：**全模态输入 → 类型化结构化输出**；我们**只蒸思想不搬权重**。'),
 ('命令怎么写？', 'cap video_intel 的 JSON：{"op":"probe"} 看能不能看；{"op":"schema"} 取类型化契约；{"op":"understand","path":"某个.mp4"} 真抽镜头表；{"op":"fuse"} 取创作链映射。全部只读、零作用域、不出网。'),
]
for q, a in F:
    for _ in range(3):
        add(q, a)
out = rows + new
OUT.write_text(''.join(json.dumps(r, ensure_ascii=False) + chr(10) for r in out), encoding='utf-8')
blob = OUT.read_bytes()
fam = defaultdict(int)
for r in out:
    fam[r.get('family') or '?'] += 1
MAN.write_text(json.dumps({'gen': 'v34', 'parent': 'v33', 'count': len(out), 'bytes': len(blob),
                           'sha256': hashlib.sha256(blob).hexdigest(),
                           'by_family': dict(sorted(fam.items(), key=lambda x: -x[1]))},
                          ensure_ascii=False, indent=1), encoding='utf-8')
print('v34', len(out), '| new', len(new), '| bytes', len(blob), '| sha', hashlib.sha256(blob).hexdigest()[:16])
print('看视频理解', fam.get('看视频理解'))
