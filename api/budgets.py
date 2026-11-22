"""
POST /api/budgets
Create or update a monthly budget for a category.
"""
import json, sys, os
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

            category = str(body['category'])
            amount   = float(body['amount'])
            if amount <= 0:
                raise ValueError('Enter a valid monthly limit.')

            conn = get_conn()
            cur  = conn.cursor()
            cur.execute("SELECT id FROM categories WHERE name = %s AND kind = 'expense'", (category,))
            row = cur.fetchone()
            if not row:
                raise ValueError('Category not found or is not an expense category.')

            cur.execute("""
                INSERT INTO budgets(user_id, category_id, monthly_limit)
                VALUES (1, %s, %s)
                ON CONFLICT (user_id, category_id)
                DO UPDATE SET monthly_limit = EXCLUDED.monthly_limit
            """, (row['id'], amount))
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
