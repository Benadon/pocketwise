import json, datetime
from http.server import BaseHTTPRequestHandler
from _db import init_db, metrics, get_conn, cols

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def do_POST(self):
        try:
            init_db()
            b      = json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or b'{}')
            name   = str(b['category'])
            kind   = str(b['kind'])
            amount = float(b['amount'])
            desc   = str(b['description']).strip()
            date   = str(b['date'])
            if amount <= 0 or not desc: raise ValueError('Check amount and description.')
            datetime.date.fromisoformat(date)
            conn = get_conn()
            rows = conn.run("SELECT id,kind FROM categories WHERE name=:n", n=name)
            if not rows: raise ValueError('Category not found.')
            c = cols(conn)
            cat = dict(zip(c, rows[0]))
            if cat['kind'] != kind: raise ValueError('Wrong category type.')
            conn.run("""INSERT INTO transactions(user_id,category_id,kind,amount,description,transaction_date)
                VALUES(1,:c,:k,:a,:d,:dt)""", c=cat['id'], k=kind, a=amount, d=desc, dt=date)
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
