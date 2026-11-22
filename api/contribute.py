import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from lib.db import init_db, metrics, get_conn

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def do_POST(self):
        try:
            init_db()
            qs     = parse_qs(urlparse(self.path).query)
            gid    = int(qs.get('id', [None])[0])
            b      = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
            amount = float(b['amount'])
            if amount <= 0: raise ValueError('Contribution must be above zero.')
            conn = get_conn()
            conn.run(
                "UPDATE financial_goals SET saved_amount=saved_amount+:a WHERE id=:g AND user_id=1",
                a=amount, g=gid
            )
            conn.close()
            self._json({'ok': True, 'data': metrics()}, 200)
        except (ValueError, KeyError, TypeError) as e:
            self._json({'error': str(e)}, 400)
        except Exception as e:
            self._json({'error': str(e)}, 500)

    def _json(self, obj, status):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self._cors(); self.end_headers(); self.wfile.write(body)

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def log_message(self, *a): pass
