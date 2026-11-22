import json
from http.server import BaseHTTPRequestHandler
from _db import init_db, metrics, get_conn

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def do_POST(self):
        try:
            init_db()
            b        = json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or b'{}')
            category = str(b['category'])
            amount   = float(b['amount'])
            if amount <= 0: raise ValueError('Enter a valid monthly limit.')
            conn = get_conn()
            rows = conn.run("SELECT id FROM categories WHERE name=:n AND kind='expense'", n=category)
            if not rows: raise ValueError('Category not found.')
            cid = rows[0][0]
            conn.run("""INSERT INTO budgets(user_id,category_id,monthly_limit) VALUES(1,:c,:l)
                ON CONFLICT(user_id,category_id) DO UPDATE SET monthly_limit=EXCLUDED.monthly_limit""",
                c=cid, l=amount)
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
