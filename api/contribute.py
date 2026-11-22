import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from _db import init_db, metrics, get_conn

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def do_POST(self):
        try:
            init_db()
            qs     = parse_qs(urlparse(self.path).query)
            gid    = int(qs.get('id', [None])[0])
            b      = json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or b'{}')
            amount = float(b['amount'])
            if amount <= 0: raise ValueError('Contribution must be above zero.')
            conn = get_conn()
            conn.run("UPDATE financial_goals SET saved_amount=saved_amount+:a WHERE id=:g AND user_id=1",
                     a=amount, g=gid)
            conn.close()
            self._send(200, {'ok': True, 'data': metrics()})
        except (ValueError, KeyError, TypeError) as e:
            self._send(400, {'error': str(e)})
        except Exception as e:
            self._send(500, {'error': str(e)})

    def _send(self, status, obj):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self._cors(); self.end_headers(); self.wfile.write(body)

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def log_message(self, *a): pass
