import http.server
import json
import threading
from collections.abc import Callable
from collections.abc import Iterator
from collections.abc import Mapping
from typing import Any

import pytest

# (method, path including query, headers, decoded JSON body) -> (status, JSON)
Handler = Callable[[str, str, Mapping[str, str], Any], tuple[int, Any]]
Serve = Callable[[Handler], str]


@pytest.fixture(name='serve', scope='function')
def serve_fixture() -> Iterator[Serve]:
    """Start a local JSON HTTP server per handler; returns its base URL."""
    servers: list[tuple[http.server.HTTPServer, threading.Thread]] = []

    def serve(handler: Handler) -> str:
        class RequestHandler(http.server.BaseHTTPRequestHandler):
            def _serve(self) -> None:
                length = int(self.headers.get('Content-Length') or 0)
                body = json.loads(self.rfile.read(length)) if length else None
                status, payload = handler(
                    self.command, self.path, dict(self.headers.items()), body
                )
                self.send_response(status)
                if payload is not None:
                    self.send_header('Content-Type', 'application/json')
                self.end_headers()
                if payload is not None:
                    self.wfile.write(json.dumps(payload).encode())

            do_GET = do_POST = do_PUT = do_DELETE = _serve

        server = http.server.ThreadingHTTPServer(
            ('127.0.0.1', 0), RequestHandler
        )
        # shutdown() only takes effect at the next poll, so keep it short.
        thread = threading.Thread(
            target=server.serve_forever, kwargs={'poll_interval': 0.01}
        )
        thread.start()
        servers.append((server, thread))
        return f'http://127.0.0.1:{server.server_address[1]}'

    yield serve
    for server, thread in servers:
        server.shutdown()
        server.server_close()
        thread.join()
