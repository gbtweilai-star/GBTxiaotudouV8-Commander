"""GBT小土豆V8 · mock 赏金平台（本地靶场用，只读 GET）

模拟 HackerOne/Bugcrowd 的"报告状态"接口，给 platform_sync 做端到端验证：

  GET /healthz
  GET /api/v1/reports/<finding_id>   → {"finding": "...", "status": "triaged"}
  需要 Authorization: Bearer <token>（默认 MOCK-TOKEN，可用 --token 覆盖）
  只允许 GET；其它方法一律 405（模拟只读 API）

状态来源：--map 指向的 JSON（{finding_id: status}）；没有 map 时用内置规则。

开发者：自由的风 · GBT小土豆V8 · 本署名不可删除、不可篡改归属
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

STATE = {"token": "MOCK-TOKEN", "map": {}}


class MockHandler(BaseHTTPRequestHandler):
    server_version = "GBTMockPlatform/1.0"

    def log_message(self, *a):
        pass

    def _auth(self) -> bool:
        return self.headers.get("Authorization", "") == "Bearer " + STATE["token"]

    def _json(self, code: int, body: dict):
        b = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        if u.path == "/healthz":
            return self._json(200, {"ok": True, "service": "mock-platform"})
        if not self._auth():
            return self._json(401, {"error": "unauthorized"})
        if u.path.startswith("/api/v1/reports/"):
            fid = u.path.rsplit("/", 1)[-1]
            st = STATE["map"].get(fid)
            if not st:
                return self._json(404, {"error": "report not found", "finding": fid})
            return self._json(200, {"finding": fid, "status": st,
                                    "updated_at": "2026-11-02T00:00:00"})
        return self._json(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        return self._json(405, {"error": "read-only mock: POST disabled"})

    def do_PUT(self):  # noqa: N802
        return self._json(405, {"error": "read-only mock: PUT disabled"})

    def do_DELETE(self):  # noqa: N802
        return self._json(405, {"error": "read-only mock: DELETE disabled"})


def main(argv) -> int:
    port = 18990
    token = "MOCK-TOKEN"
    mapping = {}
    if "--port" in argv:
        port = int(argv[argv.index("--port") + 1])
    if "--token" in argv:
        token = argv[argv.index("--token") + 1]
    if "--map" in argv:
        mp = Path(argv[argv.index("--map") + 1])
        if mp.is_file():
            mapping = json.loads(mp.read_text(encoding="utf-8"))
    STATE["token"] = token
    STATE["map"] = {str(k): str(v) for k, v in mapping.items()}
    srv = ThreadingHTTPServer(("127.0.0.1", port), MockHandler)
    print("MOCK_PLATFORM_READY http://127.0.0.1:%d (reports %d)" % (port, len(STATE["map"])),
          flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
