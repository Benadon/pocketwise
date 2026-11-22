"""
POST /api/transactions
Add a new income or expense transaction.
"""
import json, sys, os, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from http.server import BaseHTTPRequestHandler
from lib.db import init_db, metrics, get_conn


class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        try:
            init_db()
            length = int(self.headers.get('Content-Length', 0))
            body   = json.loads(self.rfile.read(length) or b'{}')

            name   = str(body['category'])
            kind   = str(body['kind'])
            amount = float(body['amount'])
            desc   = str(body['description']).strip()
            date   = str(body['date'])

            if amount <= 0 or not desc:
                raise ValueError('Check the amount and description.')
            datetime.date.fromisoformat(date)

            conn = get_conn()
            cur  = conn.cursor()
            cur.execute("SELECT id, kind FROM categories WHERE name = %s", (name,))
            row = cur.fetchone()
            if not row or row['kind'] != kind:
                raise ValueError('Invalid category for this transaction type.')

            cur.execute(
                "INSERT INTO transactions(user_id, category_id, kind, amount, description, transaction_date) VALUES (1, %s, %s, %s, %s, %s)",
                (row['id'], kind, amount, desc, date)
            )
            conn.commit()
            cur.close(); conn.close()

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
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def log_message(self, *args):
        pass
