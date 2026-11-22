import json
from http.server import BaseHTTPRequestHandler
from _db import init_db, metrics

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            init_db()
            self._ok(metrics())
        except Exception as e:
            self._err(str(e))

    def _ok(self, obj):
        self._send(200, obj)

    def _err(self, msg):
        self._send(500, {'error': msg})

    def _send(self, status, obj):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a): pass
