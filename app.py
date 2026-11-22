from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import json, sqlite3, datetime, mimetypes

BASE = Path(__file__).resolve().parent
DB = BASE / 'finance_coach.db'
STATIC = BASE / 'static'
CATS = [('Salary','income','#19a88a'),('Freelance','income','#6b83e8'),('Food','expense','#f2a75b'),('Transport','expense','#5c9fe8'),('Housing','expense','#8476e8'),('Shopping','expense','#ef7b83'),('Health','expense','#46b8ad'),('Education','expense','#e7bc50'),('Entertainment','expense','#bb78d2'),('Utilities','expense','#8b9aaa')]

def conn():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c

def init_db():
    with conn() as c:
        c.executescript((BASE / 'schema.sql').read_text(encoding='utf-8'))
        if c.execute('SELECT COUNT(*) FROM users').fetchone()[0]: return
        c.execute('INSERT INTO users(name,currency) VALUES (?,?)', ('Prajwal Yadav','INR'))
        c.executemany('INSERT INTO categories(name,kind,color) VALUES (?,?,?)', CATS)
        ids = {r['name']:r['id'] for r in c.execute('SELECT id,name FROM categories')}
        budgets = {'Food':8500,'Transport':3500,'Housing':12000,'Shopping':5000,'Health':2500,'Education':3000,'Entertainment':2500,'Utilities':2200}
        c.executemany('INSERT INTO budgets(user_id,category_id,monthly_limit) VALUES (1,?,?)', [(ids[k],v) for k,v in budgets.items()])
        today = datetime.date.today()
        goals = [('Emergency fund',60000,24500, today+datetime.timedelta(days=240)),('New laptop',75000,31200,today+datetime.timedelta(days=180)),('Travel fund',40000,16800,today+datetime.timedelta(days=120))]
        c.executemany('INSERT INTO financial_goals(user_id,name,target_amount,saved_amount,target_date) VALUES(1,?,?,?,?)', [(n,t,s,d.isoformat()) for n,t,s,d in goals])
        # 90 days of fictional activity, with current-month spending intentionally close to budgets.
        rows=[]
        for back in range(3):
            month = today.replace(day=1) - datetime.timedelta(days=back*30)
            yy,mm=month.year,month.month
            def day(d): return datetime.date(yy,mm,min(d, (datetime.date(yy+int(mm==12), 1 if mm==12 else mm+1,1)-datetime.timedelta(days=1)).day)).isoformat()
            rows += [(ids['Salary'],'income',52000,'Monthly salary',day(1)),(ids['Freelance'],'income',6500 if back!=1 else 4000,'Design project',day(18))]
            mult = [1.0,0.88,0.94][back]
            for cat,amt,desc,d in [('Housing',12000,'Monthly rent',3),('Food',7200,'Groceries and meals',9),('Food',900,'Cafe',22),('Transport',2850,'Metro and rides',12),('Shopping',4100 if back==0 else 2600,'Household and personal',15),('Health',1200,'Pharmacy',10),('Education',2200,'Course materials',20),('Entertainment',1850,'Weekend plans',24),('Utilities',1900,'Internet and utilities',26)]:
                rows.append((ids[cat],'expense',round(amt*mult,2),desc,day(d)))
        c.executemany('INSERT INTO transactions(user_id,category_id,kind,amount,description,transaction_date) VALUES(1,?,?,?,?,?)',rows)

def metrics():
    with conn() as c:
        now=datetime.date.today(); start=now.replace(day=1).isoformat()
        month_rows=[dict(r) for r in c.execute("SELECT t.id,t.kind,t.amount,t.description,t.transaction_date AS date,ca.name AS category,ca.color FROM transactions t JOIN categories ca ON ca.id=t.category_id WHERE user_id=1 AND transaction_date>=? ORDER BY transaction_date DESC,t.id DESC",(start,))]
        trans=[dict(r) for r in c.execute("SELECT t.id,t.kind,t.amount,t.description,t.transaction_date AS date,ca.name AS category,ca.color FROM transactions t JOIN categories ca ON ca.id=t.category_id WHERE user_id=1 ORDER BY transaction_date DESC,t.id DESC LIMIT 100")]
        budgets=[]
        for r in c.execute('SELECT b.id,b.monthly_limit AS limit_amount,ca.name AS category,ca.color FROM budgets b JOIN categories ca ON ca.id=b.category_id WHERE b.user_id=1'):
            actual=sum(x['amount'] for x in month_rows if x['kind']=='expense' and x['category']==r['category'])
            budgets.append({**dict(r),'actual':actual,'percent':round(actual/r['limit_amount']*100)})
        goals=[dict(r) for r in c.execute('SELECT * FROM financial_goals WHERE user_id=1 ORDER BY id')]
        for g in goals:g['percent']=min(100,round(g['saved_amount']/g['target_amount']*100))
        income=sum(x['amount'] for x in month_rows if x['kind']=='income'); expense=sum(x['amount'] for x in month_rows if x['kind']=='expense')
        planned=sum(b['limit_amount'] for b in budgets); utilization=expense/planned if planned else 0
        save=max(0,income-expense); savings_rate=save/income*100 if income else 0; expense_ratio=expense/income*100 if income else 0
        score=round(min(40,savings_rate/20*40)+max(0,30-expense_ratio/100*30)+max(0,30-min(100,utilization*100)/100*30))
        score=min(100,score); label='Strong' if score>=80 else 'Building' if score>=60 else 'Needs attention'
        spend_by={}
        for x in month_rows:
            if x['kind']=='expense':spend_by[x['category']]=spend_by.get(x['category'],0)+x['amount']
        # 6 month trend grouped by month
        trend=[]
        for back in range(5,-1,-1):
            month=now.replace(day=1)-datetime.timedelta(days=back*30); key=month.strftime('%Y-%m')
            vals=[r for r in c.execute("SELECT kind,amount FROM transactions WHERE user_id=1 AND substr(transaction_date,1,7)=?",(key,))]
            trend.append({'month':month.strftime('%b'),'income':sum(x['amount'] for x in vals if x['kind']=='income'),'expense':sum(x['amount'] for x in vals if x['kind']=='expense')})
        return {'user':dict(c.execute('SELECT * FROM users WHERE id=1').fetchone()),'income':income,'expense':expense,'saved':save,'savings_rate':round(savings_rate,1),'expense_ratio':round(expense_ratio,1),'score':score,'score_label':label,'transactions':trans,'month_transactions':month_rows,'budgets':budgets,'goals':goals,'spend_by':spend_by,'trend':trend}

class Handler(BaseHTTPRequestHandler):
    def send_json(self,obj,status=200):
        data=json.dumps(obj).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(data)
    def body(self): return json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or b'{}')
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/api/data': self.send_json(metrics()); return
        if path.startswith('/api/export.csv'):
            data=metrics()['transactions']; out='Date,Type,Category,Description,Amount\n'+''.join(f"{x['date']},{x['kind']},{x['category']},\"{x['description'].replace(chr(34),chr(34)*2)}\",{x['amount']}\n" for x in data)
            b=out.encode(); self.send_response(200); self.send_header('Content-Type','text/csv'); self.send_header('Content-Disposition','attachment; filename=finance-report.csv'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b); return
        rel='index.html' if path=='/' else path.lstrip('/')
        file=(STATIC/rel).resolve()
        if not str(file).startswith(str(STATIC.resolve())) or not file.exists() or not file.is_file(): self.send_error(404); return
        b=file.read_bytes(); self.send_response(200); self.send_header('Content-Type',mimetypes.guess_type(file.name)[0] or 'application/octet-stream'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        p=urlparse(self.path).path; x=self.body()
        try:
            with conn() as c:
                if p=='/api/transactions':
                    name=str(x['category']); kind=x['kind']; amount=float(x['amount']); desc=str(x['description']).strip(); date=str(x['date'])
                    row=c.execute('SELECT id,kind FROM categories WHERE name=?',(name,)).fetchone()
                    if not row or row['kind']!=kind or amount<=0 or not desc: raise ValueError('Check the category, amount, and description.')
                    datetime.date.fromisoformat(date)
                    c.execute('INSERT INTO transactions(user_id,category_id,kind,amount,description,transaction_date) VALUES(1,?,?,?,?,?)',(row['id'],kind,amount,desc,date))
                elif p=='/api/budgets':
                    amount=float(x['amount']); row=c.execute('SELECT id FROM categories WHERE name=? AND kind="expense"',(x['category'],)).fetchone()
                    if not row or amount<=0: raise ValueError('Enter a valid category and limit.')
                    c.execute('INSERT INTO budgets(user_id,category_id,monthly_limit) VALUES(1,?,?) ON CONFLICT(user_id,category_id) DO UPDATE SET monthly_limit=excluded.monthly_limit',(row['id'],amount))
                elif p=='/api/goals':
                    name=str(x['name']).strip(); target=float(x['target']); date=str(x['date'])
                    if not name or target<=0: raise ValueError('Enter a goal name and a target above zero.')
                    datetime.date.fromisoformat(date); c.execute('INSERT INTO financial_goals(user_id,name,target_amount,saved_amount,target_date) VALUES(1,?,?,0,?)',(name,target,date))
                elif p.startswith('/api/goals/') and p.endswith('/contribute'):
                    gid=int(p.split('/')[3]); amount=float(x['amount'])
                    if amount<=0: raise ValueError('Contribution must be above zero.')
                    c.execute('UPDATE financial_goals SET saved_amount=saved_amount+? WHERE id=? AND user_id=1',(amount,gid))
                else: self.send_error(404); return
            self.send_json({'ok':True,'data':metrics()})
        except (ValueError,KeyError,TypeError) as e:self.send_json({'error':str(e)},400)
    def log_message(self,*args): pass

if __name__=='__main__':
    init_db(); print('AI Finance Coach running at http://127.0.0.1:8000'); ThreadingHTTPServer(('127.0.0.1',8000),Handler).serve_forever()
