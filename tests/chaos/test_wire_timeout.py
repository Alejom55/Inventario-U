"""Exercise the actual HTTP timeout against an isolated loopback dependency."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time

import pytest

from app.integrations.external_api import ExternalApiError, get_json


def test_real_slow_dependency_opens_circuit_and_preserves_trace(monkeypatch):
    observed = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            observed.append(self.headers.get('X-Trace-Id'))
            time.sleep(.25)
            try:
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.end_headers()
                self.wfile.write(b'{"id":"synthetic"}')
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass  # The protected client deliberately closes timed-out connections.
    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    worker = threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        assert get_json(base,'/entity','deportBack','wire-baseline') == {'id':'synthetic'}
        monkeypatch.setenv('RESILIENCE_MODE','protected')
        monkeypatch.setenv('DEPORTBACK_TIMEOUT_SECONDS','0.05')
        for _ in range(3):
            with pytest.raises(ExternalApiError,match='tiempo de espera'):
                get_json(base,'/entity','deportBack','wire-protected')
        with pytest.raises(ExternalApiError,match='circuito abierto'):
            get_json(base,'/entity','deportBack','must-not-reach-dependency')
        assert observed == ['wire-baseline'] + ['wire-protected']*3
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
