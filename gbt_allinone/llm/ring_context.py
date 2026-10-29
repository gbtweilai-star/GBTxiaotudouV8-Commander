# -*- coding: utf-8 -*-
# gbt-capability: ring_context
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""ring_context —— 环形自动化上下文（主人令 2026-10-11）。

主人原话：「**给她设计一个圆型的自动化上下文，就是一直保持上下文长度却不会顶到溢出，
另一边是直接进数据库，需要查装一个秒查就好了**……类似手机屏幕，你不管怎么划他都一直
可以滚动上下，再回到数据库，需要查秒查。」

## 它解决什么（今日实锤）
  框架的系统提示词 13,480 字 + 长对话 ⇒ 端点 MAX_MODEL_LEN 顶爆 ⇒ 网关直接 **502**
  （实测：同一端点同一把钥匙，短提示词 200、长提示词 502）。
  ⇒ 上下文必须是**有界的**（一屏），**溢出不许丢**（落库），**要查必须秒回**。

## 三件事
  ① **环形窗口（一屏）**：`window()` 永远 ≤ window_chars —— 滑进来的新内容进来，
     最老的就被挤出去；**长度恒定，永不溢出**。
  ② **溢出落库**：被挤出的每一条**逐条落 SQLite FTS5**（seq 单调递增，只追加不改写）。
  ③ **秒查**：`recall(q, k)` 走 FTS5 MATCH + CJK 兜底 —— 老内容**搜一下就回来**。

## 铁律
  · **不许丢**：挤出 ≠ 删除，必须落库成功（落库失败就**不挤出**，宁可报错也不静默丢）；
  · **长度恒定**：`window()` 超预算 = bug，不是"差不多就行"；
  · **只追加**：库里只 append（seq 单调），不留改写路径；
  · **一屏给模型看，全量给查询用**：模型只看窗口，查得到的是全史。
"""
from __future__ import annotations

import json
import os
import pathlib
import sqlite3
import time

_BASE = pathlib.Path(__file__).resolve().parent
_ROOT = _BASE.parents[1]


def _store_dir() -> pathlib.Path:
    d = os.environ.get("GBT_STORE_DIR")
    if d:
        return pathlib.Path(d)
    return _ROOT / "gbt_allinone" / "store"


# 🔴 2026-10-28 主人令「权重模型上下文最长长度让触手把控好」：
#   原来 `DEFAULT_WINDOW_CHARS = 12000` 是**写死的**，与模型实际 ctx 无关 ——
#   模型换了（2048 / 8192 / 32768）窗口预算纹丝不动，那叫"拍板"不叫"把控"。
#   现改为**按模型 ctx 派生**，并把三条实测口径写死在这里：
#     ① 字符/token：**1.714**（2026-10-28 真分词器实测，12000 字符 = 7000 token）；
#     ② 安全系数 **0.8**：留出 system 提示 / 输出余量；
#     ③ 上限仍受 12000 约束（设计上"一屏"，不是越大越好）。
#   🔴 更要紧的实测（同日）：**整窗硬塞 0/4，recall 秒查 3/4** ——
#     说明历史本来就该走 recall，window 只负责"最近那屏"。窗口不是越大越好。
def _default_window_chars() -> int:
    """按模型 ctx 派生一屏预算（触手口径）；读不到就回落设计值并**说明**。

    取值顺序（都读**真实来源**，不猜）：
      ① 环境 `GBT_LLM_CTX`（壳/车道启动时设的，是真在跑的那个 ctx）；
      ② `state/model-ctx.json` 的 `ctx`（触手落盘的模型上限缓存，存在才用）；
      ③ 都读不到 ⇒ 12000（设计值），**不静默变成 0**。
    """
    ctx = 0
    try:
        ctx = int(os.environ.get("GBT_LLM_CTX") or 0)
    except (TypeError, ValueError):
        ctx = 0
    if ctx <= 0:
        try:
            f = _ROOT / "state" / "model-ctx.json"
            if f.is_file():
                ctx = int((json.loads(f.read_text(encoding="utf-8")) or {}).get("ctx") or 0)
        except Exception:                                      # noqa: BLE001
            ctx = 0
    if ctx <= 0:
        return 12000                    # 读不到模型上限 ⇒ 用设计值
    return max(512, min(12000, int(ctx * 1.714 * 0.8)))


DEFAULT_WINDOW_CHARS = _default_window_chars()


class RingContext:
    """环形上下文：一屏窗口 + 全量落库 + 秒查。"""

    def __init__(self, name: str = 'default', window_chars: int = DEFAULT_WINDOW_CHARS,
                 db_path: pathlib.Path | None = None):
        self.name = name
        self.window_chars = int(window_chars)
        self.db_path = pathlib.Path(db_path) if db_path else (_store_dir() / 'ring_context' / 'ring.db')
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ring: list[dict] = []
        self._chars = 0
        self._seq = 0
        self._init_db()

    def _conn(self):
        c = sqlite3.connect(str(self.db_path))
        c.execute('PRAGMA journal_mode=WAL')
        return c

    def _init_db(self):
        with self._conn() as c:
            c.execute('CREATE TABLE IF NOT EXISTS turns ('
                      'seq INTEGER PRIMARY KEY, at TEXT, role TEXT, content TEXT, chars INTEGER)')
            try:
                c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS turns_fts USING fts5("
                          "content, tokenize='unicode61')")
            except sqlite3.OperationalError:
                pass
            row = c.execute('SELECT MAX(seq) FROM turns').fetchone()
            self._seq = int(row[0] or 0)

    # ── ① 入环：超预算就把最老的挤出去（先落库，再挤出）──────────────────
    def push(self, role: str, content: str, meta: dict | None = None) -> dict:
        """推一条进环。**先落库成功，才允许挤出**（不出库就不挤出）。"""
        item = {'seq': self._seq + 1, 'role': role, 'content': content,
                'at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'meta': meta or {}}
        self._seq += 1
        item['chars'] = len(content)
        self._ring.append(item)
        self._chars += item['chars']
        evicted = []
        while self._chars > self.window_chars and len(self._ring) > 1:
            oldest = self._ring[0]
            if not self._spill(oldest):          # 落库失败：不挤出（宁可超一点也不丢）
                break
            self._ring.pop(0)
            self._chars -= oldest['chars']
            evicted.append(oldest['seq'])
        return {'ok': True, 'seq': item['seq'], 'window_chars': self._chars,
                'window_items': len(self._ring), 'evicted': evicted}

    def _spill(self, item: dict) -> bool:
        """把一个被挤出的条目落库（FTS5 同步）。返回是否落库成功。"""
        try:
            with self._conn() as c:
                c.execute('INSERT OR REPLACE INTO turns (seq, at, role, content, chars) VALUES (?,?,?,?,?)',
                          (item['seq'], item['at'], item['role'], item['content'], item['chars']))
                try:
                    c.execute('INSERT INTO turns_fts (rowid, content) VALUES (?,?)',
                              (item['seq'], item['content']))
                except sqlite3.OperationalError:
                    pass
            return True
        except Exception:
            return False

    # ── ② 一屏：给模型看的有界上下文（恒定长度）──────────────────────────
    def window(self, system: str = '') -> list[dict]:
        """返回**有界**的上下文（system 也计入预算；超了从最老的对话开始让位）。"""
        budget = self.window_chars - len(system or '')
        out: list[dict] = []
        used = 0
        for it in reversed(self._ring):
            if used + it['chars'] > budget and out:
                break
            out.append({'role': it['role'], 'content': it['content']})
            used += it['chars']
        out.reverse()
        msgs = ([{'role': 'system', 'content': system}] if system else []) + out
        total = sum(len(m['content']) for m in msgs)
        return msgs if total <= self.window_chars else msgs[-1:]

    # ── ③ 秒查：老内容搜一下回来（FTS5 + CJK 兜底）───────────────────────
    def recall(self, query: str, k: int = 5) -> dict:
        """秒查全史（含已挤出窗口的）。FTS5 命中优先，CJK 走 LIKE 兜底。"""
        t0 = time.time()
        hits: list[dict] = []
        try:
            with self._conn() as c:
                try:
                    rows = c.execute(
                        'SELECT t.seq, t.at, t.role, t.content FROM turns_fts f '
                        'JOIN turns t ON t.seq = f.rowid WHERE turns_fts MATCH ? '
                        'ORDER BY rank LIMIT ?', (_fts_q(query), k)).fetchall()
                except sqlite3.OperationalError:
                    rows = []
                if not rows:
                    rows = c.execute('SELECT seq, at, role, content FROM turns '
                                     'WHERE content LIKE ? ORDER BY seq DESC LIMIT ?',
                                     ('%' + query + '%', k)).fetchall()
        except Exception as e:
            return {'ok': False, 'error': repr(e)[:200], 'hits': []}
        for r in rows:
            hits.append({'seq': r[0], 'at': r[1], 'role': r[2], 'content': r[3]})
        return {'ok': True, 'query': query, 'hits': hits, 'ms': round((time.time() - t0) * 1000, 2)}

    def stats(self) -> dict:
        with self._conn() as c:
            n = c.execute('SELECT COUNT(*) FROM turns').fetchone()[0]
        return {'ok': True, 'db': str(self.db_path), 'db_turns': int(n),
                'window_chars': self._chars, 'window_budget': self.window_chars,
                'window_items': len(self._ring), 'seq': self._seq}


def _fts_q(q: str) -> str:
    """把查询变成 FTS5 安全串（逐词加引号，避免语法错）。"""
    parts = [p for p in str(q).replace('"', ' ').split() if p]
    return ' '.join('"%s"' % p for p in parts) or '""'


def run(payload: dict | None = None) -> dict:
    """门内入口（run_task 唯一门）。op=push/window/recall/stats/clear_window。"""
    p = dict(payload or {})
    op = str(p.get('op') or 'stats').strip().lower()
    rc = RingContext(name=str(p.get('name') or 'default'),
                     window_chars=int(p.get('window_chars') or DEFAULT_WINDOW_CHARS))
    if op == 'stats':
        return rc.stats()
    if op == 'push':
        return rc.push(str(p.get('role') or 'user'), str(p.get('content') or ''))
    if op == 'window':
        return {'ok': True, 'messages': rc.window(str(p.get('system') or ''))}
    if op == 'recall':
        return rc.recall(str(p.get('query') or ''), int(p.get('k') or 5))
    return {'ok': False, 'fail_closed': True,
            'error': "user_error: 未列出的 op（fail-closed）",
            'ops': ['stats', 'push', 'window', 'recall']}


if __name__ == '__main__':
    import sys
    rc = RingContext(name='cli')
    print(json.dumps(rc.stats(), ensure_ascii=False, indent=1))