import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from http.server import BaseHTTPRequestHandler
from lib.db import init_db, metrics

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            init_db()
            txs  = metrics()['transactions']
            rows = 'Date,Type,Category,Description,Amount\n'
            for x in txs:
                desc = x['description'].replace('"', '""')
                rows += f"{x['date']},{x['kind']},{x['category']},\"{desc}\",{x['amount']}\n"
            body = rows.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv')
            self.send_header('Content-Disposition', 'attachment; filename=finance-report.csv')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            body = str(e).encode()
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, *a): pass
