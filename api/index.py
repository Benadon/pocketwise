"""
PocketWise — single Flask app served as one Vercel Python function.
All routes handled here: /api/data, /api/transactions, /api/budgets,
/api/goals, /api/contribute, /api/export
"""
import os, re, datetime, json
from flask import Flask, request, jsonify, Response
import pg8000.native

app = Flask(__name__)

# ── DB connection ────────────────────────────────────────────────────────────

def get_conn():
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set. "
                           "Add it in Vercel → Project → Settings → Environment Variables.")
    m = re.match(r'postgres(?:ql)?://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/([^?]+)', url)
    if not m:
        raise RuntimeError(f"Cannot parse DATABASE_URL (first 40 chars): {url[:40]}")
    user, password, host, port, database = m.groups()
    return pg8000.native.Connection(
        user=user, password=password, host=host,
        port=int(port or 5432), database=database, ssl_context=True
    )

def q(conn, sql, **kw):
    rows   = conn.run(sql, **kw)
    colnames = [c['name'] for c in conn.columns]
    return [dict(zip(colnames, r)) for r in rows]

# ── Schema + seed ────────────────────────────────────────────────────────────

CATS = [
    ('Salary','income','#19a88a'), ('Freelance','income','#6b83e8'),
    ('Food','expense','#f2a75b'), ('Transport','expense','#5c9fe8'),
    ('Housing','expense','#8476e8'), ('Shopping','expense','#ef7b83'),
    ('Health','expense','#46b8ad'), ('Education','expense','#e7bc50'),
    ('Entertainment','expense','#bb78d2'), ('Utilities','expense','#8b9aaa'),
]

def init_db():
    conn = get_conn()
    conn.run("""CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY, name TEXT NOT NULL,
        currency TEXT NOT NULL DEFAULT 'INR',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    conn.run("""CREATE TABLE IF NOT EXISTS categories(
        id SERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE,
        kind TEXT NOT NULL CHECK(kind IN('income','expense')), color TEXT NOT NULL)""")
    conn.run("""CREATE TABLE IF NOT EXISTS transactions(
        id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id),
        category_id INT NOT NULL REFERENCES categories(id),
        kind TEXT NOT NULL CHECK(kind IN('income','expense')),
        amount NUMERIC NOT NULL CHECK(amount>0),
        description TEXT NOT NULL, transaction_date DATE NOT NULL)""")
    conn.run("""CREATE TABLE IF NOT EXISTS budgets(
        id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id),
        category_id INT NOT NULL REFERENCES categories(id),
        monthly_limit NUMERIC NOT NULL CHECK(monthly_limit>0),
        UNIQUE(user_id,category_id))""")
    conn.run("""CREATE TABLE IF NOT EXISTS financial_goals(
        id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id),
        name TEXT NOT NULL, target_amount NUMERIC NOT NULL CHECK(target_amount>0),
        saved_amount NUMERIC NOT NULL DEFAULT 0 CHECK(saved_amount>=0),
        target_date DATE NOT NULL)""")

    if conn.run("SELECT COUNT(*) FROM users")[0][0] > 0:
        conn.close(); return

    conn.run("INSERT INTO users(name,currency) VALUES(:n,:c)", n='Prajwal Yadav', c='INR')
    for name,kind,color in CATS:
        conn.run("INSERT INTO categories(name,kind,color) VALUES(:n,:k,:c) ON CONFLICT DO NOTHING",
                 n=name, k=kind, c=color)

    id_rows = q(conn, "SELECT id,name FROM categories")
    ids = {r['name']: r['id'] for r in id_rows}

    for cat,lim in {'Food':8500,'Transport':3500,'Housing':12000,'Shopping':5000,
                    'Health':2500,'Education':3000,'Entertainment':2500,'Utilities':2200}.items():
        conn.run("INSERT INTO budgets(user_id,category_id,monthly_limit) VALUES(1,:c,:l)",
                 c=ids[cat], l=lim)

    today = datetime.date.today()
    for n,t,s,d in [('Emergency fund',60000,24500,today+datetime.timedelta(days=240)),
                    ('New laptop',75000,31200,today+datetime.timedelta(days=180)),
                    ('Travel fund',40000,16800,today+datetime.timedelta(days=120))]:
        conn.run("""INSERT INTO financial_goals(user_id,name,target_amount,saved_amount,target_date)
                 VALUES(1,:n,:t,:s,:d)""", n=n, t=t, s=s, d=d.isoformat())

    tx = []
    for back in range(3):
        month = today.replace(day=1) - datetime.timedelta(days=back*30)
        yy,mm = month.year, month.month
        def _day(d):
            last = (datetime.date(yy+int(mm==12), 1 if mm==12 else mm+1, 1)-datetime.timedelta(days=1)).day
            return datetime.date(yy, mm, min(d,last)).isoformat()
        tx += [(ids['Salary'],'income',52000,'Monthly salary',_day(1)),
               (ids['Freelance'],'income',6500 if back!=1 else 4000,'Design project',_day(18))]
        mult = [1.0,0.88,0.94][back]
        for cat,amt,desc,d in [
            ('Housing',12000,'Monthly rent',3),('Food',7200,'Groceries and meals',9),
            ('Food',900,'Cafe',22),('Transport',2850,'Metro and rides',12),
            ('Shopping',4100 if back==0 else 2600,'Household and personal',15),
            ('Health',1200,'Pharmacy',10),('Education',2200,'Course materials',20),
            ('Entertainment',1850,'Weekend plans',24),('Utilities',1900,'Internet and utilities',26)]:
            tx.append((ids[cat],'expense',round(amt*mult,2),desc,_day(d)))

    for cid,kind,amt,desc,dt in tx:
        conn.run("""INSERT INTO transactions(user_id,category_id,kind,amount,description,transaction_date)
                 VALUES(1,:c,:k,:a,:d,:dt)""", c=cid, k=kind, a=amt, d=desc, dt=dt)
    conn.close()

# ── Metrics ──────────────────────────────────────────────────────────────────

def metrics():
    conn  = get_conn()
    today = datetime.date.today()
    start = today.replace(day=1).isoformat()

    month_rows = q(conn, """
        SELECT t.id,t.kind,t.amount::float,t.description,
               t.transaction_date::text AS date, ca.name AS category, ca.color
        FROM transactions t JOIN categories ca ON ca.id=t.category_id
        WHERE t.user_id=1 AND t.transaction_date>=:s
        ORDER BY t.transaction_date DESC,t.id DESC""", s=start)

    trans = q(conn, """
        SELECT t.id,t.kind,t.amount::float,t.description,
               t.transaction_date::text AS date, ca.name AS category, ca.color
        FROM transactions t JOIN categories ca ON ca.id=t.category_id
        WHERE t.user_id=1 ORDER BY t.transaction_date DESC,t.id DESC LIMIT 100""")

    budgets = []
    for b in q(conn, """
        SELECT b.id,b.monthly_limit::float AS limit_amount,ca.name AS category,ca.color
        FROM budgets b JOIN categories ca ON ca.id=b.category_id WHERE b.user_id=1"""):
        actual = sum(x['amount'] for x in month_rows if x['kind']=='expense' and x['category']==b['category'])
        budgets.append({**b,'actual':actual,
                        'percent':round(actual/b['limit_amount']*100) if b['limit_amount'] else 0})

    goals = []
    for g in q(conn, "SELECT * FROM financial_goals WHERE user_id=1 ORDER BY id"):
        g['target_amount'] = float(g['target_amount'])
        g['saved_amount']  = float(g['saved_amount'])
        g['target_date']   = g['target_date'].isoformat() if hasattr(g['target_date'],'isoformat') else str(g['target_date'])
        g['percent']       = min(100,round(g['saved_amount']/g['target_amount']*100)) if g['target_amount'] else 0
        goals.append(g)

    user = q(conn, "SELECT * FROM users WHERE id=1")[0]
    user['created_at'] = str(user.get('created_at',''))

    income  = sum(x['amount'] for x in month_rows if x['kind']=='income')
    expense = sum(x['amount'] for x in month_rows if x['kind']=='expense')
    planned = sum(b['limit_amount'] for b in budgets)
    save    = max(0, income-expense)
    sr      = save/income*100 if income else 0
    er      = expense/income*100 if income else 0
    util    = expense/planned if planned else 0
    score   = min(100,round(min(40,sr/20*40)+max(0,30-er/100*30)+max(0,30-min(100,util*100)/100*30)))
    label   = 'Strong' if score>=80 else 'Building' if score>=60 else 'Needs attention'

    spend_by = {}
    for x in month_rows:
        if x['kind']=='expense': spend_by[x['category']] = spend_by.get(x['category'],0)+x['amount']

    trend = []
    for back in range(5,-1,-1):
        month = today.replace(day=1)-datetime.timedelta(days=back*30)
        key   = month.strftime('%Y-%m')
        vals  = q(conn,"SELECT kind,amount::float FROM transactions WHERE user_id=1 AND to_char(transaction_date,'YYYY-MM')=:k",k=key)
        trend.append({'month':month.strftime('%b'),
                      'income':sum(v['amount'] for v in vals if v['kind']=='income'),
                      'expense':sum(v['amount'] for v in vals if v['kind']=='expense')})
    conn.close()
    return {'user':user,'income':income,'expense':expense,'saved':save,
            'savings_rate':round(sr,1),'expense_ratio':round(er,1),
            'score':score,'score_label':label,'transactions':trans,
            'month_transactions':month_rows,'budgets':budgets,'goals':goals,
            'spend_by':spend_by,'trend':trend}

# ── Routes ───────────────────────────────────────────────────────────────────

@app.route('/api/data')
def api_data():
    try:
        init_db()
        return jsonify(metrics())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/transactions', methods=['POST'])
def api_transactions():
    try:
        init_db()
        b      = request.get_json()
        name   = str(b['category'])
        kind   = str(b['kind'])
        amount = float(b['amount'])
        desc   = str(b['description']).strip()
        date   = str(b['date'])
        if amount<=0 or not desc: raise ValueError('Check amount and description.')
        datetime.date.fromisoformat(date)
        conn = get_conn()
        rows = q(conn,"SELECT id,kind FROM categories WHERE name=:n",n=name)
        if not rows: raise ValueError('Category not found.')
        cat = rows[0]
        if cat['kind']!=kind: raise ValueError('Wrong category type.')
        conn.run("""INSERT INTO transactions(user_id,category_id,kind,amount,description,transaction_date)
                 VALUES(1,:c,:k,:a,:d,:dt)""", c=cat['id'],k=kind,a=amount,d=desc,dt=date)
        conn.close()
        return jsonify({'ok':True,'data':metrics()})
    except (ValueError,KeyError,TypeError) as e:
        return jsonify({'error':str(e)}),400
    except Exception as e:
        return jsonify({'error':str(e)}),500

@app.route('/api/budgets', methods=['POST'])
def api_budgets():
    try:
        init_db()
        b        = request.get_json()
        category = str(b['category'])
        amount   = float(b['amount'])
        if amount<=0: raise ValueError('Enter a valid monthly limit.')
        conn = get_conn()
        rows = conn.run("SELECT id FROM categories WHERE name=:n AND kind='expense'",n=category)
        if not rows: raise ValueError('Category not found.')
        cid = rows[0][0]
        conn.run("""INSERT INTO budgets(user_id,category_id,monthly_limit) VALUES(1,:c,:l)
                 ON CONFLICT(user_id,category_id) DO UPDATE SET monthly_limit=EXCLUDED.monthly_limit""",
                 c=cid,l=amount)
        conn.close()
        return jsonify({'ok':True,'data':metrics()})
    except (ValueError,KeyError,TypeError) as e:
        return jsonify({'error':str(e)}),400
    except Exception as e:
        return jsonify({'error':str(e)}),500

@app.route('/api/goals', methods=['POST'])
def api_goals():
    try:
        init_db()
        b      = request.get_json()
        name   = str(b['name']).strip()
        target = float(b['target'])
        date   = str(b['date'])
        if not name or target<=0: raise ValueError('Enter a goal name and target above zero.')
        datetime.date.fromisoformat(date)
        conn = get_conn()
        conn.run("""INSERT INTO financial_goals(user_id,name,target_amount,saved_amount,target_date)
                 VALUES(1,:n,:t,0,:d)""",n=name,t=target,d=date)
        conn.close()
        return jsonify({'ok':True,'data':metrics()})
    except (ValueError,KeyError,TypeError) as e:
        return jsonify({'error':str(e)}),400
    except Exception as e:
        return jsonify({'error':str(e)}),500

@app.route('/api/contribute', methods=['POST'])
def api_contribute():
    try:
        init_db()
        gid    = int(request.args.get('id'))
        b      = request.get_json()
        amount = float(b['amount'])
        if amount<=0: raise ValueError('Contribution must be above zero.')
        conn = get_conn()
        conn.run("UPDATE financial_goals SET saved_amount=saved_amount+:a WHERE id=:g AND user_id=1",
                 a=amount,g=gid)
        conn.close()
        return jsonify({'ok':True,'data':metrics()})
    except (ValueError,KeyError,TypeError) as e:
        return jsonify({'error':str(e)}),400
    except Exception as e:
        return jsonify({'error':str(e)}),500

@app.route('/api/export')
def api_export():
    try:
        init_db()
        txs  = metrics()['transactions']
        rows = 'Date,Type,Category,Description,Amount\n'
        for x in txs:
            desc = x['description'].replace('"','""')
            rows += f"{x['date']},{x['kind']},{x['category']},\"{desc}\",{x['amount']}\n"
        return Response(rows, mimetype='text/csv',
                        headers={'Content-Disposition':'attachment; filename=finance-report.csv'})
    except Exception as e:
        return str(e), 500
