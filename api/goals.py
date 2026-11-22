import json, datetime
from http.server import BaseHTTPRequestHandler
from _db import init_db, metrics, get_conn

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def do_POST(self):
        try:
            init_db()
            b      = json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or b'{}')
            name   = str(b['name']).strip()
            target = float(b['target'])
            date   = str(b['date'])
            if not name or target <= 0: raise ValueError('Enter a goal name and target above zero.')
            datetime.date.fromisoformat(date)
            conn = get_conn()
            conn.run("""INSERT INTO financial_goals(user_id,name,target_amount,saved_amount,target_date)
                VALUES(1,:n,:t,0,:d)""", n=name, t=target, d=date)
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
