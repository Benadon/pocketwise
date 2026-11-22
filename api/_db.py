"""
Shared DB logic — imported by sibling api/*.py files.
All files are in the same /api directory so the import works on Vercel.
Uses pg8000 (pure Python, no C build needed).
"""
import os, re, datetime
import pg8000.native

_URL = os.environ.get("DATABASE_URL", "")

CATS = [
    ('Salary',        'income',  '#19a88a'),
    ('Freelance',     'income',  '#6b83e8'),
    ('Food',          'expense', '#f2a75b'),
    ('Transport',     'expense', '#5c9fe8'),
    ('Housing',       'expense', '#8476e8'),
    ('Shopping',      'expense', '#ef7b83'),
    ('Health',        'expense', '#46b8ad'),
    ('Education',     'expense', '#e7bc50'),
    ('Entertainment', 'expense', '#bb78d2'),
    ('Utilities',     'expense', '#8b9aaa'),
]

def get_conn():
    m = re.match(r'postgres(?:ql)?://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/([^?]+)', _URL)
    if not m:
        raise ValueError("DATABASE_URL not set or invalid. Add it in Vercel → Settings → Environment Variables.")
    user, password, host, port, database = m.groups()
    return pg8000.native.Connection(
        user=user, password=password, host=host,
        port=int(port or 5432), database=database, ssl_context=True
    )

def cols(conn):
    return [c['name'] for c in conn.columns]

def rows_dicts(conn, result):
    c = cols(conn)
    return [dict(zip(c, r)) for r in result]

def init_db():
    conn = get_conn()
    conn.run("""CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY, name TEXT NOT NULL,
        currency TEXT NOT NULL DEFAULT 'INR',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    conn.run("""CREATE TABLE IF NOT EXISTS categories (
        id SERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE,
        kind TEXT NOT NULL CHECK (kind IN ('income','expense')), color TEXT NOT NULL)""")
    conn.run("""CREATE TABLE IF NOT EXISTS transactions (
        id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
        category_id INTEGER NOT NULL REFERENCES categories(id),
        kind TEXT NOT NULL CHECK (kind IN ('income','expense')),
        amount NUMERIC NOT NULL CHECK (amount > 0),
        description TEXT NOT NULL, transaction_date DATE NOT NULL)""")
    conn.run("""CREATE TABLE IF NOT EXISTS budgets (
        id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
        category_id INTEGER NOT NULL REFERENCES categories(id),
        monthly_limit NUMERIC NOT NULL CHECK (monthly_limit > 0),
        UNIQUE (user_id, category_id))""")
    conn.run("""CREATE TABLE IF NOT EXISTS financial_goals (
        id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
        name TEXT NOT NULL, target_amount NUMERIC NOT NULL CHECK (target_amount > 0),
        saved_amount NUMERIC NOT NULL DEFAULT 0 CHECK (saved_amount >= 0),
        target_date DATE NOT NULL)""")

    if conn.run("SELECT COUNT(*) FROM users")[0][0] > 0:
        conn.close(); return

    conn.run("INSERT INTO users(name,currency) VALUES (:n,:c)", n='Prajwal Yadav', c='INR')
    for name, kind, color in CATS:
        conn.run("INSERT INTO categories(name,kind,color) VALUES (:n,:k,:c) ON CONFLICT DO NOTHING",
                 n=name, k=kind, c=color)

    id_rows = conn.run("SELECT id,name FROM categories")
    id_cols = cols(conn)
    ids = {r[id_cols.index('name')]: r[id_cols.index('id')] for r in id_rows}

    for cat, lim in {'Food':8500,'Transport':3500,'Housing':12000,'Shopping':5000,
                     'Health':2500,'Education':3000,'Entertainment':2500,'Utilities':2200}.items():
        conn.run("INSERT INTO budgets(user_id,category_id,monthly_limit) VALUES(1,:c,:l)", c=ids[cat], l=lim)

    today = datetime.date.today()
    for n,t,s,d in [('Emergency fund',60000,24500,today+datetime.timedelta(days=240)),
                    ('New laptop',75000,31200,today+datetime.timedelta(days=180)),
                    ('Travel fund',40000,16800,today+datetime.timedelta(days=120))]:
        conn.run("INSERT INTO financial_goals(user_id,name,target_amount,saved_amount,target_date) VALUES(1,:n,:t,:s,:d)",
                 n=n, t=t, s=s, d=d.isoformat())

    tx = []
    for back in range(3):
        month = today.replace(day=1) - datetime.timedelta(days=back*30)
        yy, mm = month.year, month.month
        def _day(d):
            last = (datetime.date(yy+int(mm==12), 1 if mm==12 else mm+1, 1)-datetime.timedelta(days=1)).day
            return datetime.date(yy, mm, min(d, last)).isoformat()
        tx += [(ids['Salary'],'income',52000,'Monthly salary',_day(1)),
               (ids['Freelance'],'income',6500 if back!=1 else 4000,'Design project',_day(18))]
        mult = [1.0,0.88,0.94][back]
        for cat,amt,desc,d in [('Housing',12000,'Monthly rent',3),('Food',7200,'Groceries and meals',9),
            ('Food',900,'Cafe',22),('Transport',2850,'Metro and rides',12),
            ('Shopping',4100 if back==0 else 2600,'Household and personal',15),
            ('Health',1200,'Pharmacy',10),('Education',2200,'Course materials',20),
            ('Entertainment',1850,'Weekend plans',24),('Utilities',1900,'Internet and utilities',26)]:
            tx.append((ids[cat],'expense',round(amt*mult,2),desc,_day(d)))

    for cid,kind,amt,desc,dt in tx:
        conn.run("INSERT INTO transactions(user_id,category_id,kind,amount,description,transaction_date) VALUES(1,:c,:k,:a,:d,:dt)",
                 c=cid, k=kind, a=amt, d=desc, dt=dt)
    conn.close()

def metrics():
    conn  = get_conn()
    today = datetime.date.today()
    start = today.replace(day=1).isoformat()

    r = conn.run("""SELECT t.id,t.kind,t.amount::float,t.description,
        t.transaction_date::text AS date, ca.name AS category, ca.color
        FROM transactions t JOIN categories ca ON ca.id=t.category_id
        WHERE t.user_id=1 AND t.transaction_date>=:s ORDER BY t.transaction_date DESC,t.id DESC""", s=start)
    month_rows = rows_dicts(conn, r)

    r = conn.run("""SELECT t.id,t.kind,t.amount::float,t.description,
        t.transaction_date::text AS date, ca.name AS category, ca.color
        FROM transactions t JOIN categories ca ON ca.id=t.category_id
        WHERE t.user_id=1 ORDER BY t.transaction_date DESC,t.id DESC LIMIT 100""")
    trans = rows_dicts(conn, r)

    r = conn.run("""SELECT b.id,b.monthly_limit::float AS limit_amount,ca.name AS category,ca.color
        FROM budgets b JOIN categories ca ON ca.id=b.category_id WHERE b.user_id=1""")
    budgets = []
    for b in rows_dicts(conn, r):
        actual = sum(x['amount'] for x in month_rows if x['kind']=='expense' and x['category']==b['category'])
        budgets.append({**b,'actual':actual,'percent':round(actual/b['limit_amount']*100) if b['limit_amount'] else 0})

    r = conn.run("SELECT * FROM financial_goals WHERE user_id=1 ORDER BY id")
    goals = []
    for g in rows_dicts(conn, r):
        g['target_amount'] = float(g['target_amount'])
        g['saved_amount']  = float(g['saved_amount'])
        g['target_date']   = g['target_date'].isoformat() if hasattr(g['target_date'],'isoformat') else str(g['target_date'])
        g['percent']       = min(100, round(g['saved_amount']/g['target_amount']*100)) if g['target_amount'] else 0
        goals.append(g)

    r    = conn.run("SELECT * FROM users WHERE id=1")
    user = rows_dicts(conn, r)[0]
    user['created_at'] = str(user.get('created_at',''))

    income  = sum(x['amount'] for x in month_rows if x['kind']=='income')
    expense = sum(x['amount'] for x in month_rows if x['kind']=='expense')
    planned = sum(b['limit_amount'] for b in budgets)
    save    = max(0, income-expense)
    sr      = save/income*100 if income else 0
    er      = expense/income*100 if income else 0
    util    = expense/planned if planned else 0
    score   = min(100, round(min(40,sr/20*40)+max(0,30-er/100*30)+max(0,30-min(100,util*100)/100*30)))
    label   = 'Strong' if score>=80 else 'Building' if score>=60 else 'Needs attention'

    spend_by = {}
    for x in month_rows:
        if x['kind']=='expense': spend_by[x['category']] = spend_by.get(x['category'],0)+x['amount']

    trend = []
    for back in range(5,-1,-1):
        month = today.replace(day=1)-datetime.timedelta(days=back*30)
        key   = month.strftime('%Y-%m')
        vals  = rows_dicts(conn, conn.run(
            "SELECT kind,amount::float FROM transactions WHERE user_id=1 AND to_char(transaction_date,'YYYY-MM')=:k", k=key))
        trend.append({'month':month.strftime('%b'),
                      'income':sum(v['amount'] for v in vals if v['kind']=='income'),
                      'expense':sum(v['amount'] for v in vals if v['kind']=='expense')})
    conn.close()
    return {'user':user,'income':income,'expense':expense,'saved':save,
            'savings_rate':round(sr,1),'expense_ratio':round(er,1),
            'score':score,'score_label':label,'transactions':trans,
            'month_transactions':month_rows,'budgets':budgets,'goals':goals,
            'spend_by':spend_by,'trend':trend}
