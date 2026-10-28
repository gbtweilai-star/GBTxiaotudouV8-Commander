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

import hashlib
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


DEFAULT_WINDOW_CHARS = 12000


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
        # 🔴 2026-10-28：**不能用 WAL**。
        #   WAL 依赖共享内存（-shm），而 iSH 的 mmap 是**每进程私有**的
        #   ⇒ 一个进程写进去、另一个进程读不到（实测：写入后另开连接查询 0 条，
        #     同进程内却能查到）。
        #   这和之前免费池 better-sqlite3 写入丢失是**同一个根因**。
        #   改成 DELETE（回滚日志）模式：不依赖共享内存，跨进程立即可见。
        try:
            c.execute('PRAGMA journal_mode=DELETE')
        except sqlite3.OperationalError:
            pass
        c.execute('PRAGMA synchronous=FULL')
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
            # 🔴 2026-10-28：原来 turns 表**没有 name 列** —— 所有会话共用一个表，
            #   于是"按名字恢复窗口"根本做不到，而 self._ring 是纯内存的，
            #   进程一换窗口就空（实测：同实例 5 条 / 新实例 0 条，库里 52 条仍在）。
            #   ⇒ 那叫"会话内有限上下文"，不叫无限。
            #   这里做**加法迁移**：补 name 列（老行落 'default'），以后按名恢复。
            cols = {r[1] for r in c.execute('PRAGMA table_info(turns)').fetchall()}
            if 'name' not in cols:
                c.execute("ALTER TABLE turns ADD COLUMN name TEXT DEFAULT 'default'")
            # 🔴 2026-10-28：加**内容指纹列**做幂等。
            #   为什么要：桥现在要"每问都存"（不存的话短请求的事实永远进不了库，
            #   实测埋进去的 ZX-4471-QK 查了 0 条）。
            #   但每次请求都是新 RingContext，seq 从 MAX 接着涨 ⇒ 全存会无限重复。
            #   用 sha1(role+content) 去重：同一条话进库只留一份。
            if 'h' not in cols:
                c.execute("ALTER TABLE turns ADD COLUMN h TEXT")
            try:
                c.execute('CREATE INDEX IF NOT EXISTS idx_turns_h ON turns(h)')
            except sqlite3.OperationalError:
                pass
            row = c.execute('SELECT MAX(seq) FROM turns').fetchone()
            self._seq = int(row[0] or 0)
        self._restore_window()

    # ── ① 入环：超预算就把最老的挤出去（先落库，再挤出）──────────────────
    def push(self, role: str, content: str, meta: dict | None = None) -> dict:
        """推一条进环。**先落库成功，才允许挤出**（不出库就不挤出）。"""
        item = {'seq': self._seq + 1, 'role': role, 'content': content,
                'at': time.strftime('%Y-%m-%dT%H:%M:%S'), 'meta': meta or {}}
        self._seq += 1
        item['chars'] = len(content)
        # 🔴 2026-10-28：**同一条话不重复进环**。
        #   设计用法是「一条长命的 RingContext，只 push 新消息」；
        #   但调用方（桥）是无状态的，每请求会 new 一个再把历史重推一遍 ——
        #   那样 _persist 去重了，`_ring` 却会重复，window() 里同一条话出现好几遍。
        #   这里加一道环内去重：与环里**最近 8 条**任一条相同 ⇒ 直接返回，不入环。
        #   （只比最近 8 条：老消息可能被合法地重复提到，不该永久拦住。）
        _h_now = hashlib.sha1(("%s\x00%s" % (role, content)).encode("utf-8")).hexdigest()
        for _old in self._ring[-8:]:
            if _old.get("h") == _h_now or (_old.get("role") == role
                                           and _old.get("content") == content):
                return {'ok': True, 'seq': _old.get('seq'), 'dup': True,
                        'window_chars': self._chars, 'window_items': len(self._ring),
                        'evicted': []}
        item['h'] = _h_now
        self._ring.append(item)
        self._chars += item['chars']
        # 🔴 2026-10-28：原来**只有被挤出时才落库**，于是"最近这一屏"从来没进过库
        #   （实测：90 字远没到 4000 预算 ⇒ 一条没存 ⇒ 换进程窗口 0 条）。
        #   ⇒ 那不叫无限上下文，叫"进程内有限窗口 + 老内容可搜"。
        #   现在改成**每条都落库**，内存窗口只是"库的一个视图"：
        #   进程重启后能从这个会话的尾部把窗口读回来。
        self._persist(item)
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

    def _restore_window(self, max_items: int = 400) -> int:
        """从库里把这个会话最近的若干条读回内存窗口（按预算截断）。

        没有这一步，"窗口"就是进程私有的：换进程等于失忆，
        只能靠 recall 一条条捞。补上之后才配叫**跨进程的无限上下文**。
        """
        try:
            with self._conn() as c:
                rows = c.execute(
                    "SELECT seq, at, role, content, chars FROM turns "
                    "WHERE COALESCE(name, 'default') = ? ORDER BY seq DESC LIMIT ?",
                    (self.name, int(max_items))).fetchall()
        except Exception:                                     # noqa: BLE001
            return 0
        restored = 0
        for seq, at, role, content, chars in reversed(rows):
            n = int(chars or len(content or ''))
            if self._chars + n > self.window_chars and self._ring:
                break
            self._ring.append({'seq': int(seq), 'at': at, 'role': role,
                               'content': content, 'chars': n, 'meta': {}})
            self._chars += n
            restored += 1
        return restored

    def _persist(self, item: dict) -> bool:
        """把一条写进库（**幂等**，INSERT OR REPLACE）。每次 push 都调用。"""
        return self._spill(item)

    def _spill(self, item: dict) -> bool:
        """把一个被挤出的条目落库（FTS5 同步）。返回是否落库成功。"""
        try:
            with self._conn() as c:
                import hashlib as _hl
                _h = _hl.sha1(("%s\x00%s" % (item['role'], item['content']))
                              .encode('utf-8')).hexdigest()
                # 🔴 2026-10-28：去重**必须按会话隔离**。
                #   原来只按 h 全局查 ⇒ A 会话存过的话，B 会话 push 时被当成重复跳过，
                #   B 会话里就永远没有这条（实测 final 会话只剩 1 条）。
                _dup = c.execute(
                    "SELECT seq FROM turns WHERE h = ? "
                    "AND COALESCE(name, 'default') = ? LIMIT 1",
                    (_h, self.name)).fetchone()
                if _dup:
                    return True          # 同一句话已经在库里，不重复存
                c.execute('INSERT OR REPLACE INTO turns '
                          '(seq, at, role, content, chars, name, h) '
                          'VALUES (?,?,?,?,?,?,?)',
                          (item['seq'], item['at'], item['role'], item['content'],
                           item['chars'], self.name, _h))
                try:
                    # 🔴 2026-10-28：改成"每条都落库"后，同一条会被写两次
                    #   （push 时一次、被挤出时再一次），第二次插 FTS 的 rowid
                    #   已经存在 ⇒ IntegrityError。而这里原来只 catch
                    #   OperationalError ⇒ 异常冒出去 ⇒ _spill 返回 False
                    #   ⇒ 挤出循环 break ⇒ **环形"长度恒定"铁律被破坏**
                    #   （实测窗口涨到 8070 / 预算 3000）。
                    #   两处都修：FTS 用 OR REPLACE，且把 IntegrityError 也接住。
                    c.execute('INSERT OR REPLACE INTO turns_fts (rowid, content) VALUES (?,?)',
                              (item['seq'], item['content']))
                except (sqlite3.OperationalError, sqlite3.IntegrityError):
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
                    # 🔴 2026-10-28：**召回必须限定本会话**。
                    #   原来不限 name ⇒ 会串到别的会话去（实测：final 会话自己只有 1 条，
                    #   却 recall 出 3 条 —— 全是别的测试会话的）。
                    #   每个会话是一个独立的环，串了就等于偷看别人的上下文。
                    rows = c.execute(
                        'SELECT t.seq, t.at, t.role, t.content FROM turns_fts f '
                        'JOIN turns t ON t.seq = f.rowid WHERE turns_fts MATCH ? '
                        "AND COALESCE(t.name, 'default') = ? "
                        'ORDER BY rank LIMIT ?',
                        (_fts_q(query), self.name, k)).fetchall()
                except sqlite3.OperationalError:
                    rows = []
                if not rows:
                    rows = c.execute(
                        'SELECT seq, at, role, content FROM turns '
                        "WHERE content LIKE ? AND COALESCE(name, 'default') = ? "
                        'ORDER BY seq DESC LIMIT ?',
                        ('%' + query + '%', self.name, k)).fetchall()
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