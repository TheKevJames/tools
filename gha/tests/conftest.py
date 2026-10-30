import http.server
import json
import pathlib
import threading
from collections.abc import Callable
from collections.abc import Iterator
from collections.abc import Mapping
from typing import Any

import pytest

from tests import fake_github

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

        class ReadyServer(http.server.ThreadingHTTPServer):
            def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
                self.is_ready = threading.Event()
                super().__init__(*args, **kwargs)

            def server_activate(self) -> None:
                super().server_activate()
                self.is_ready.set()

        server = ReadyServer(('127.0.0.1', 0), RequestHandler)
        # shutdown() only takes effect at the next poll, so keep it short.
        thread = threading.Thread(
            target=server.serve_forever, kwargs={'poll_interval': 0.01}
        )
        thread.start()
        server.is_ready.wait()
        servers.append((server, thread))
        return f'http://127.0.0.1:{server.server_address[1]}'

    yield serve
    for server, thread in servers:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture(name='github', scope='function')
def github_fixture(
    serve: Serve, monkeypatch: pytest.MonkeyPatch
) -> fake_github.FakeGitHub:
    fake = fake_github.FakeGitHub()

    def handle(
        method: str,
        path: str,
        headers: Mapping[str, str],
        body: Any,  # noqa: ANN401
    ) -> tuple[int, Any]:
        token = headers['Authorization'].removeprefix('Bearer ')
        return fake.handle(method, path, token, body)

    monkeypatch.setenv('GITHUB_API_URL', serve(handle))
    return fake


@pytest.fixture(name='checkout', scope='function')
def checkout_fixture(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> pathlib.Path:
    fake_github.write_checkout(tmp_path)
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(tmp_path / 'summary.md'))
    return tmp_path
