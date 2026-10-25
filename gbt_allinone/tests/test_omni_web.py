"""omni_web（web 域）验收：自适应元素重定位在**真实改版场景**下到底灵不灵。

用 Scrapling 文档里那个公开场景做判据（页面结构大改：多包了一层、class 改名、
id 挪到 data-id），看我们自己的实现能不能把元素找回来 —— 并且**分数不够时要认输**。

跑法：
    py -3.14 -m pytest gbt_allinone/tests/test_omni_web.py -q
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

_TENT = Path(__file__).resolve().parents[1] / "tentacle"


def _load():
    """照 bridge.py 的加载方式（spec_from_file_location）把 omni_web 装起来。"""
    if str(_TENT) not in sys.path:
        sys.path.insert(0, str(_TENT))
    spec = importlib.util.spec_from_file_location("_omni_web_test", str(_TENT / "omni_web.py"))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


OLD = """<!DOCTYPE html><html><head><title>Shop</title></head><body>
<div class="container">
  <section class="products">
    <article class="product" id="p1">
      <h3>Product 1</h3>
      <p class="description">Description 1</p>
    </article>
    <article class="product" id="p2">
      <h3>Product 2</h3>
      <p class="description">Description 2</p>
    </article>
  </section>
</div>
</body></html>"""

# 改版：外面多包一层、class 改名、id 变成 data-id、h3/p 又被包了一层
NEW = """<!DOCTYPE html><html><head><title>Shop</title></head><body>
<div class="new-container">
  <div class="product-wrapper">
    <section class="products">
      <article class="product new-class" data-id="p1">
        <div class="product-info">
          <h3>Product 1</h3>
          <p class="new-description">Description 1</p>
        </div>
      </article>
      <article class="product new-class" data-id="p2">
        <div class="product-info">
          <h3>Product 2</h3>
          <p class="new-description">Description 2</p>
        </div>
      </article>
    </section>
  </div>
</div>
</body></html>"""

# 完全无关的页面 —— 用来验证"分数不够时必须认输"
UNRELATED = """<html><body><footer><ul><li>Contact</li><li>About</li></ul></footer></body></html>"""


@pytest.fixture()
def web(tmp_path, monkeypatch):
    monkeypatch.setenv("GBT_WEB_ADAPTIVE_DB", str(tmp_path / "fp.sqlite3"))
    mod = _load()
    return mod, mod.OmniWebMixin()


# ── 拿 DOM 的基本功 ──────────────────────────────────────────────────────

def test_parse_counts_nodes(web):
    _, t = web
    got = t.web_parse(OLD, url="https://shop.example.com/x")
    assert got["ok"] is True
    assert got["domain"] == "example.com", "域名要剥掉 www 与子域，当隔离键"
    assert got["nodes"] > 5 and "article" in got["tags"]


def test_select_class_and_child_combinator(web):
    _, t = web
    assert t.web_select(OLD, ".product")["count"] == 2
    # 子代(>) 与后代(空格) 要区分：h3 不是 body 的直接子代
    assert t.web_select(OLD, "article > h3")["count"] == 2
    assert t.web_select(OLD, "body > h3")["count"] == 0
    assert t.web_select(OLD, "#p2 h3")["count"] == 1
    assert t.web_select(OLD, "section.products article:nth-child(2)")["count"] == 1


def test_select_attribute_predicates(web):
    _, t = web
    assert t.web_select(NEW, "[data-id=p1]")["count"] == 1
    assert t.web_select(NEW, "[data-id^=p]")["count"] == 2
    assert t.web_select(NEW, "[class*=new-class]")["count"] == 2
    assert t.web_select(NEW, "[data-id$=9]")["count"] == 0


def test_empty_selector_refuses_instead_of_matching_all(web):
    _, t = web
    got = t.web_select(OLD, "")
    assert got["ok"] is False and got["count"] == 0
    assert "不猜" in got["error"]


def test_web_text_reads_visible_text(web):
    _, t = web
    got = t.web_text(OLD)
    assert got["ok"] and got["title"] == "Shop"
    assert "Product 1" in got["text"] and "Description 2" in got["text"]
    assert "<h3>" not in got["text"], "读正文不该把标签读进来"


# ── 核心：自适应重定位 ───────────────────────────────────────────────────

def test_adaptive_relocates_after_restructure(web):
    _, t = web
    saved = t.web_save(OLD, "#p1", url="https://shop.example.com/x")
    assert saved["ok"] and saved["identifier"] == "#p1"
    assert saved["domain"] == "example.com"

    got = t.web_adaptive(NEW, "#p1", url="https://shop.example.com/x")
    assert got["ok"] is True
    assert got["relocated"] is True, "改版后应当找回：%s" % got
    assert got["match"]["tag"] == "article"
    assert got["match"]["attrs"].get("data-id") == "p1", "要找回来的正是 p1 那张卡"
    assert "Product 1" in got["match"]["text"]
    assert got["score"] >= got["threshold"]
    # 明细要能看出每一项，不许只给一个黑箱总分
    assert set(got["parts"]) == {"tag", "id", "classes", "attrs", "text",
                                "siblings", "path", "parent", "identity"}


# 非对称改版：p1 的 class 变了、p2 的**没变** —— 只按外观比必然选错 p2。
ASYM = """<html><body><section class="products">
<article class="product new-class" data-id="p1"><h3>Product 1</h3>
  <p class="description">Description 1</p></article>
<article class="product" data-id="p2"><h3>Product 2</h3>
  <p class="description">Description 2</p></article>
</section></body></html>"""


def test_adaptive_survives_id_moved_to_data_attribute(web):
    """`id="p1"` 被挪成 `data-id="p1"` 且**只有它这一张动了外观**时，必须选对。

    这是源技术文档里的原始场景。我第一版实现在这里**选错了**（选了 p2）：
    因为只在**同名属性**之间比值，属性名一改就隐身，而 p2 的 class 没变反而更像。
    修法是加了 `identity` 项（按**值**找原件的识别 token）+ 让内容权重压过外观。
    这条用例就是钉住它，防止以后被"优化"回去。
    """
    _, t = web
    t.web_save(OLD, "#p1", url="https://shop.example.com/x")
    got = t.web_adaptive(ASYM, "#p1", url="https://shop.example.com/x")
    assert got["relocated"] is True, got
    assert got["match"]["attrs"].get("data-id") == "p1", \
        "必须选中被挪走 id 的那一张，而不是外观没变的那一张：%s" % got["parts"]
    assert got["parts"]["identity"] >= 0.99, "识别 token 应当按值找到"


def test_adaptive_picks_the_right_twin(web):
    """两张卡长得几乎一样，必须靠内容选中 p1 而不是 p2。"""
    _, t = web
    t.web_save(OLD, "#p2", url="https://shop.example.com/x")
    got = t.web_adaptive(NEW, "#p2", url="https://shop.example.com/x")
    assert got["relocated"] is True
    assert got["match"]["attrs"].get("data-id") == "p2"


def test_adaptive_admits_failure_on_unrelated_page(web):
    _, t = web
    t.web_save(OLD, "#p1", url="https://shop.example.com/x")
    got = t.web_adaptive(UNRELATED, "#p1", url="https://shop.example.com/x")
    assert got["ok"] is True
    assert got["relocated"] is False, "无关页面不该硬凑一个结果：%s" % got
    assert got["score"] < got["threshold"]
    assert "没找回" in (got["reason"] or "")


def test_adaptive_says_so_when_nothing_was_saved(web):
    _, t = web
    got = t.web_adaptive(NEW, "#never-saved", url="https://shop.example.com/x")
    assert got["ok"] is True and got["relocated"] is False
    assert "没存过" in got["reason"]


def test_domain_isolation(web):
    """同一个 identifier 在不同**可登记域**下必须互不干扰。"""
    _, t = web
    t.web_save(OLD, "#p1", url="https://shop.example.com/")
    got = t.web_adaptive(NEW, "#p1", url="https://shop.other.com/")
    assert got["relocated"] is False and "没存过" in got["reason"]


def test_subdomains_share_fingerprints(web):
    """子域刻意共享指纹：站点换个子域/改个 URL 不该把存过的特征全丢掉。

    （Scrapling 为同一目的专门做了 `adaptive_domain` 参数；我们直接按
     **可登记域**取键，天然就是这个行为 —— 所以这条要钉住，防止以后被"优化"掉。）
    """
    _, t = web
    t.web_save(OLD, "#p1", url="https://a.example.com/")
    got = t.web_adaptive(NEW, "#p1", url="https://b.example.com/")
    assert got["relocated"] is True, "同一可登记域的不同子域应当共用特征库"


def test_save_refuses_when_selector_misses(web):
    _, t = web
    got = t.web_save(OLD, ".no-such-thing", url="https://x.example.com/")
    assert got["ok"] is False and "没有东西可存" in got["error"]


def test_stats_shows_what_was_saved(web):
    _, t = web
    t.web_save(OLD, "#p1", url="https://shop.example.com/x")
    st = t.web_stats(url="https://shop.example.com/x")
    assert st["ok"] and st["count"] == 1
    assert st["rows"][0][0] == "#p1"


def test_two_level_suffix_domain(web):
    """两级后缀（com.cn）要按三段取，否则会把不同站点混成一个域。"""
    mod, _ = web
    assert mod._domain_of("https://www.shop.example.com.cn/a") == "example.com.cn"
    assert mod._domain_of("https://a.b.co.uk/x") == "b.co.uk"
    assert mod._domain_of(None) == "default"


def test_bad_source_reports_instead_of_raising(web):
    _, t = web
    got = t.web_parse(12345)
    assert got["ok"] is False and "解析失败" in got["error"]


# ── 读网（web_fetch / web_read）：本域唯一的网络动作 ──────────────────────
# 用本机临时 HTTP 服务做**真出网**验证 —— 不 mock、不打桩，真发请求真收字节。

import threading  # noqa: E402
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer  # noqa: E402

PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>触手读网验收</title></head>
<body><div class="container"><section class="products">
<article class="product" id="p1"><h3>Product 1</h3><p class="description">Description 1</p></article>
<article class="product" id="p2"><h3>Product 2</h3><p class="description">Description 2</p></article>
</section></div></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # 静音
        return

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/ok"):
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/redirect"):
            self.send_response(302)
            self.send_header("Location", "/ok")
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            body = b"<html><body>nope</body></html>"
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


@pytest.fixture()
def site():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    yield "http://127.0.0.1:%d" % srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def test_fetch_refuses_non_http_scheme(web):
    """不给本地文件留口子 —— file:// 必须当面拒绝。"""
    _, t = web
    got = t.web_fetch("file:///C:/Windows/win.ini")
    assert got["ok"] is False and "只读 http/https" in got["error"]


def test_fetch_refuses_empty_url(web):
    _, t = web
    got = t.web_fetch("")
    assert got["ok"] is False and "不猜" in got["error"]


def test_fetch_reports_http_error_status(web, site):
    """404 不许当内容返回。"""
    _, t = web
    got = t.web_fetch(site + "/missing")
    assert got["ok"] is False
    assert got["status"] == 404
    assert "不把它当内容返回" in got["error"]


def test_fetch_returns_raw_html_and_follows_redirect(web, site):
    _, t = web
    got = t.web_fetch(site + "/redirect")
    assert got["ok"] is True
    assert got["status"] == 200
    assert got["final_url"].endswith("/ok"), "要如实报出重定向后的落点"
    assert "<article" in got["html"], "必须给原始 HTML，不是去标签的纯文本"
    assert got["title"] == "触手读网验收"
    assert got["bytes"] > 0 and got["truncated"] is False


def test_fetch_truncates_and_says_so(web, site):
    _, t = web
    got = t.web_fetch(site + "/ok", max_bytes=120)
    assert got["ok"] is True and got["truncated"] is True
    assert got["bytes"] == 120
    assert "已截断" in got["note"], "截断了就必须说截断了"


def test_fetch_normalizes_bare_domain_and_reports_it(web, site):
    """没写协议时补 https:// —— 但**要如实标出补过**，别让人以为 URL 原样就是这样。"""
    _, t = web
    bare = site.replace("http://", "") + "/ok"
    got = t.web_fetch(bare)
    assert got["normalized"] is True
    assert got["url"] == "https://" + bare
    # 本机验收服务只开 HTTP，所以这一发必然连不上 —— 那就必须**如实报错**，不许假装成功
    assert got["ok"] is False and got["error"]


def test_read_one_shot_fetch_select(web, site):
    """一句话读网：抓 → 解析 → 选择。"""
    _, t = web
    got = t.web_read(site + "/ok", selector=".product")
    assert got["ok"] is True and got["mode"] == "select"
    assert got["count"] == 2
    assert got["title"] == "触手读网验收"
    assert got["matches"][0]["tag"] == "article"


def test_read_one_shot_text(web, site):
    _, t = web
    got = t.web_read(site + "/ok")
    assert got["ok"] is True and got["mode"] == "text"
    assert "Product 1" in got["text"] and "<h3>" not in got["text"]


def test_read_adaptive_survives_restructure_over_the_wire(web, site):
    """端到端：先存特征 → 页面改版 → 同一条读网调用把元素找回来。"""
    _, t = web
    url = site + "/ok"
    first = t.web_read(url, selector="#p1", auto_save=True)
    assert first["ok"] and first["count"] == 1
    assert first["saved"]["ok"] is True

    # 改版：多包一层、class 改名、id 挪到 data-id
    NEWER = PAGE.replace('class="container"', 'class="new-container"') \
                .replace('<article class="product" id="p1">',
                         '<article class="product new-class" data-id="p1">') \
                .replace('id="p2"', 'data-id="p2"')
    t.web_parse(NEWER)  # 确认能解析
    got = t.web_adaptive({"html": NEWER, "url": url}, "#p1", url=url)
    assert got["relocated"] is True, "改版后应当找回：%s" % got
    assert got["match"]["attrs"].get("data-id") == "p1"


def test_read_adaptive_on_404_is_honest(web, site):
    """抓不到就不该往下装 —— 失败的阶段要说清楚。"""
    _, t = web
    got = t.web_read(site + "/missing", selector="#p1", adaptive=True)
    assert got["ok"] is False and got["stage"] == "fetch"
    assert got["status"] == 404


# ══════════ 规范级行为：robots(RFC 9309) / 编码(HTML 标准) / 重定向(RFC 9110) ══════════
# 这三块都是**照权威原文实现**的，所以用例直接照规范条款写判据。

SPEC_PAGE = ("<!DOCTYPE html><html><head><title>规范验收</title></head>"
             "<body><h1>你好</h1></body></html>")


class _SpecHandler(BaseHTTPRequestHandler):
    """可配置的验收服务。类属性即配置，用例改它就行。"""
    robots_status = 404          # 默认 404 = Unavailable ⇒ 规范判"放行"
    robots_body = ""
    transport_charset = "utf-8"
    meta_charset = ""
    with_bom = False
    filler = 0                   # 在 meta 之前塞多少字节（验"只看前 1024 字节"）

    def log_message(self, *a):
        return

    def _send(self, code, body: bytes, ctype="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redir(self, code, loc):
        self.send_response(code)
        self.send_header("Location", loc)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):  # noqa: N802
        p = self.path.split("?")[0]
        if p == "/robots.txt":
            if self.robots_status != 200:
                self._send(self.robots_status, b"nope", "text/plain")
                return
            self._send(200, self.robots_body.encode("utf-8"), "text/plain; charset=utf-8")
            return
        if p == "/307":
            return self._redir(307, "/ok")
        if p == "/308":
            return self._redir(308, "/ok")
        if p == "/loop":
            return self._redir(302, "/loop")
        if p.startswith("/hop"):                 # 非环形链：/hop3 → /hop2 → /hop1 → /hop0 → /ok
            try:
                k = int(p[4:])
            except ValueError:
                k = 0
            return self._redir(302, "/ok" if k <= 0 else "/hop%d" % (k - 1))
        if p == "/page":
            meta = ('<meta charset="%s">' % self.meta_charset) if self.meta_charset else ""
            pad = ("<!--" + "x" * max(0, self.filler) + "-->") if self.filler else ""
            body = (SPEC_PAGE.replace("<head>", "<head>" + pad + meta)).encode("utf-8")
            if self.with_bom:
                body = b"\xef\xbb\xbf" + body
            ctype = "text/html" + ("; charset=" + self.transport_charset
                                   if self.transport_charset else "")
            self._send(200, body, ctype)
            return
        if p == "/ok":
            body = PAGE.encode("utf-8")
            self._send(200, body)
            return
        self._send(404, b"<html><body>nope</body></html>")


@pytest.fixture()
def spec():
    """每个用例都拿一个干净的配置（类属性是共享的，必须显式复位）。"""
    saved = {k: getattr(_SpecHandler, k) for k in
             ("robots_status", "robots_body", "transport_charset",
              "meta_charset", "with_bom", "filler")}
    _load()  # 确保 omni_web 已加载（_ROBOTS_CACHE 在模块里）
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _SpecHandler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % srv.server_address[1]
    yield base
    for k, v in saved.items():
        setattr(_SpecHandler, k, v)
    srv.shutdown()
    srv.server_close()


def _reset_robots_cache():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_ow_t", str(_TENT / "omni_web.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── robots：RFC 9309 §2.3.1 的**非对称**默认行为（最容易写错的一条）──

def test_robots_5xx_means_complete_disallow(web, spec):
    """🔴 5xx/网络错误 = Unreachable ⇒ **MUST assume complete disallow**（fail-closed）。

    这条与 4xx 完全相反，写错的代价是"该禁的照抓"。
    """
    _, t = web
    _SpecHandler.robots_status = 500
    r = t.web_robots(spec + "/page")
    assert r["decision"] == "disallow"
    assert "MUST assume complete disallow" in r["reason"]


def test_robots_4xx_means_allow(web, spec):
    """4xx = Unavailable ⇒ **MAY access any resources**（放行）。与 5xx 相反。"""
    _, t = web
    _SpecHandler.robots_status = 404
    r = t.web_robots(spec + "/page")
    assert r["decision"] == "allow"
    assert "Unavailable" in r["reason"]


def test_robots_disallow_is_honored_and_fetch_refuses(web, spec):
    _, t = web
    _SpecHandler.robots_status = 200
    _SpecHandler.robots_body = "User-agent: *\nDisallow: /page\n"
    r = t.web_robots(spec + "/page")
    assert r["decision"] == "disallow"
    got = t.web_fetch(spec + "/page")
    assert got["ok"] is False and got["stage"] == "robots"
    assert "robots.txt 不允许" in got["error"]
    # 同站别的路径不受影响
    assert t.web_fetch(spec + "/ok")["ok"] is True


def test_robots_longest_octets_wins(web, spec):
    """路径按**八位组数最长**胜出（不是书写顺序、不是 disallow 优先）。"""
    _, t = web
    _SpecHandler.robots_status = 200
    _SpecHandler.robots_body = ("User-agent: *\nAllow: /page\n"
                                "Disallow: /page/secret\n")
    assert t.web_robots(spec + "/page/x")["decision"] == "allow"
    assert t.web_robots(spec + "/page/secret/a")["decision"] == "disallow"


def test_robots_allow_wins_on_tie(web, spec):
    """等长时 **allow 胜**（规范 SHOULD）。"""
    _, t = web
    _SpecHandler.robots_status = 200
    _SpecHandler.robots_body = "User-agent: *\nDisallow: /page\nAllow: /page\n"
    assert t.web_robots(spec + "/page")["decision"] == "allow"


def test_robots_groups_with_same_agent_are_merged(web, spec):
    """同名 user-agent 的多个组**必须合并**（不是最长匹配、不是只取第一个）。"""
    _, t = web
    _SpecHandler.robots_status = 200
    _SpecHandler.robots_body = ("User-agent: GBT-Xiaotudou\nDisallow: /a\n\n"
                                "User-agent: GBT-Xiaotudou\nDisallow: /b\n")
    assert t.web_robots(spec + "/a")["decision"] == "disallow"
    assert t.web_robots(spec + "/b")["decision"] == "disallow", "第二组也必须被合并进来"


def test_robots_wildcard_and_end_anchor(web, spec):
    """`*` = 0..n 任意字符（含 `/`）；结尾 `$` 锚定。"""
    _, t = web
    _SpecHandler.robots_status = 200
    _SpecHandler.robots_body = "User-agent: *\nDisallow: /*.gif$\n"
    assert t.web_robots(spec + "/a/b/pic.gif")["decision"] == "disallow"
    assert t.web_robots(spec + "/a/b/pic.gif.html")["decision"] == "allow"


def test_robots_absent_group_falls_back_to_star(web, spec):
    """没有精确组时用 `*` 组；连 `*` 都没有 ⇒ no rules apply（放行）。"""
    _, t = web
    _SpecHandler.robots_status = 200
    _SpecHandler.robots_body = "User-agent: SomeOtherBot\nDisallow: /page\n"
    assert t.web_robots(spec + "/page")["decision"] == "allow"


# ── 编码：BOM → 传输层 → meta → 兜底（HTML 标准 13.2.3）──

def test_bom_beats_transport_and_is_stripped(web, spec):
    """BOM 是 certain，**压过传输层**；且命中后必须**丢掉 BOM 字节**。"""
    _, t = web
    _SpecHandler.with_bom = True
    _SpecHandler.meta_charset = "gbk"          # 两个都故意写错，看谁说了算
    got = t.web_fetch(spec + "/page", honor_robots=False)
    assert got["charset_source"] == "bom"
    assert got["charset"] == "utf-8"
    assert not got["html"].startswith("\ufeff"), "BOM 必须被丢掉，不许留在正文里"
    assert "你好" in got["html"]


def test_transport_beats_meta(web, spec):
    """传输层 Content-Type 是 certain，**压过 meta prescan**（tentative）。"""
    _, t = web
    _SpecHandler.transport_charset = "gbk"
    _SpecHandler.meta_charset = "utf-8"        # 故意与传输层冲突
    got = t.web_fetch(spec + "/page", honor_robots=False)
    assert got["charset_source"] == "transport"
    assert got["charset"] == "gbk", "meta 不许越级压过 HTTP 头"


def test_meta_used_only_when_transport_silent(web, spec):
    _, t = web
    _SpecHandler.transport_charset = ""        # 传输层不说
    _SpecHandler.meta_charset = "utf-8"
    got = t.web_fetch(spec + "/page", honor_robots=False)
    assert got["charset_source"] == "meta" and got["charset"] == "utf-8"


def test_meta_beyond_1024_bytes_is_ignored(web, spec):
    """规范：作者只能在**前 1024 字节**里声明 ⇒ 更靠后的 meta 不算数。"""
    _, t = web
    _SpecHandler.transport_charset = ""
    _SpecHandler.meta_charset = "utf-8"
    _SpecHandler.filler = 1200
    got = t.web_fetch(spec + "/page", honor_robots=False)
    assert got["charset_source"] == "default", \
        "meta 在 1024 字节之后，规范说看不到它"


# ── 重定向：RFC 9110（stdlib 默认不跟 307/308，必须自己跟）──

def test_follows_307_and_308(web, spec):
    """🔴 stdlib 的 HTTPRedirectHandler **默认不跟 307/308** —— 实测踩过。

    本模块此前对外声称"跟随重定向"，遇 307 其实会失败 ⇒ 那是过度声称。
    """
    _, t = web
    for code in ("/307", "/308"):
        got = t.web_fetch(spec + code, honor_robots=False)
        assert got["ok"] is True, "%s 必须能跟上：%s" % (code, got.get("error"))
        assert got["final_url"].endswith("/ok")
        assert len(got.get("history", [])) == 1


def test_redirect_cycle_is_detected(web, spec):
    """RFC 9110 没规定最大跳数，只要求 SHOULD 检测环 —— 环必须被抓出来。"""
    _, t = web
    got = t.web_fetch(spec + "/loop", honor_robots=False, max_redirects=6)
    assert got["ok"] is False
    assert "环" in got["error"]


def test_redirect_hop_limit_is_ours_and_declared(web, spec):
    """上限是我们自己定的 —— 报错时必须说清这一点，别让人以为是规范要求。

    注意要用**非环形**的链来测：`/loop` 自己指自己，环检测会先触发（那是更好的行为）。
    """
    _, t = web
    got = t.web_fetch(spec + "/hop3", honor_robots=False, max_redirects=1)
    assert got["ok"] is False
    assert "没规定上限" in got["error"], got["error"]
    # 给够跳数就该跟到底
    assert t.web_fetch(spec + "/hop3", honor_robots=False, max_redirects=8)["ok"] is True
