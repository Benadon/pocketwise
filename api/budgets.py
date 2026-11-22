import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from http.server import BaseHTTPRequestHandler
from lib.db import init_db, metrics, get_conn, _rows_as_dicts

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def do_POST(self):
        try:
            init_db()
            b        = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
            category = str(b['category'])
            amount   = float(b['amount'])
            if amount <= 0: raise ValueError('Enter a valid monthly limit.')
            conn = get_conn()
            rows = conn.run("SELECT id FROM categories WHERE name=:n AND kind='expense'", n=category)
            if not rows: raise ValueError('Category not found.')
            cid = rows[0][0]
            conn.run("""
                INSERT INTO budgets(user_id, category_id, monthly_limit)
                VALUES (1, :c, :l)
                ON CONFLICT (user_id, category_id)
                DO UPDATE SET monthly_limit = EXCLUDED.monthly_limit
            """, c=cid, l=amount)
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
