"""
Shared database helpers for Vercel serverless functions.
Uses psycopg2 to connect to Neon Postgres via the DATABASE_URL env var.
"""
import os, datetime, json
import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "")

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
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


def init_db():
    """Create tables and seed sample data if the database is empty."""
    conn = get_conn()
    cur  = conn.cursor()

    # ── Schema ──────────────────────────────────────────────────────────────
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id          SERIAL PRIMARY KEY,
        name        TEXT NOT NULL,
        currency    TEXT NOT NULL DEFAULT 'INR',
        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS categories (
        id    SERIAL PRIMARY KEY,
        name  TEXT NOT NULL UNIQUE,
        kind  TEXT NOT NULL CHECK (kind IN ('income','expense')),
        color TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS transactions (
        id               SERIAL PRIMARY KEY,
        user_id          INTEGER NOT NULL REFERENCES users(id),
        category_id      INTEGER NOT NULL REFERENCES categories(id),
        kind             TEXT    NOT NULL CHECK (kind IN ('income','expense')),
        amount           NUMERIC NOT NULL CHECK (amount > 0),
        description      TEXT    NOT NULL,
        transaction_date DATE    NOT NULL
    );
    CREATE TABLE IF NOT EXISTS budgets (
        id            SERIAL PRIMARY KEY,
        user_id       INTEGER NOT NULL REFERENCES users(id),
        category_id   INTEGER NOT NULL REFERENCES categories(id),
        monthly_limit NUMERIC NOT NULL CHECK (monthly_limit > 0),
        UNIQUE (user_id, category_id)
    );
    CREATE TABLE IF NOT EXISTS financial_goals (
        id            SERIAL PRIMARY KEY,
        user_id       INTEGER NOT NULL REFERENCES users(id),
        name          TEXT    NOT NULL,
        target_amount NUMERIC NOT NULL CHECK (target_amount > 0),
        saved_amount  NUMERIC NOT NULL DEFAULT 0 CHECK (saved_amount >= 0),
        target_date   DATE    NOT NULL
    );
    """)
    conn.commit()

    # ── Seed only once ───────────────────────────────────────────────────────
    cur.execute("SELECT COUNT(*) AS n FROM users")
    if cur.fetchone()['n'] > 0:
        cur.close(); conn.close(); return

    cur.execute("INSERT INTO users(name, currency) VALUES (%s, %s)", ('Prajwal Yadav', 'INR'))
    cur.executemany(
        "INSERT INTO categories(name, kind, color) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
        CATS
    )
    cur.execute("SELECT id, name FROM categories")
    ids = {r['name']: r['id'] for r in cur.fetchall()}

    budget_map = {
        'Food': 8500, 'Transport': 3500, 'Housing': 12000, 'Shopping': 5000,
        'Health': 2500, 'Education': 3000, 'Entertainment': 2500, 'Utilities': 2200,
    }
    cur.executemany(
        "INSERT INTO budgets(user_id, category_id, monthly_limit) VALUES (1, %s, %s)",
        [(ids[k], v) for k, v in budget_map.items()]
    )

    today = datetime.date.today()
    goals = [
        ('Emergency fund', 60000, 24500, today + datetime.timedelta(days=240)),
        ('New laptop',      75000, 31200, today + datetime.timedelta(days=180)),
        ('Travel fund',     40000, 16800, today + datetime.timedelta(days=120)),
    ]
    cur.executemany(
        "INSERT INTO financial_goals(user_id, name, target_amount, saved_amount, target_date) VALUES (1, %s, %s, %s, %s)",
        [(n, t, s, d.isoformat()) for n, t, s, d in goals]
    )

    rows = []
    for back in range(3):
        month = today.replace(day=1) - datetime.timedelta(days=back * 30)
        yy, mm = month.year, month.month

        def _day(d):
            last = (datetime.date(yy + int(mm == 12), 1 if mm == 12 else mm + 1, 1) - datetime.timedelta(days=1)).day
            return datetime.date(yy, mm, min(d, last)).isoformat()

        rows += [
            (ids['Salary'],    'income',  52000, 'Monthly salary', _day(1)),
            (ids['Freelance'], 'income',  6500 if back != 1 else 4000, 'Design project', _day(18)),
        ]
        mult = [1.0, 0.88, 0.94][back]
        for cat, amt, desc, d in [
            ('Housing',       12000, 'Monthly rent',            3),
            ('Food',           7200, 'Groceries and meals',      9),
            ('Food',            900, 'Cafe',                    22),
            ('Transport',      2850, 'Metro and rides',         12),
            ('Shopping',  4100 if back == 0 else 2600, 'Household and personal', 15),
            ('Health',         1200, 'Pharmacy',                10),
            ('Education',      2200, 'Course materials',        20),
            ('Entertainment',  1850, 'Weekend plans',           24),
            ('Utilities',      1900, 'Internet and utilities',  26),
        ]:
            rows.append((ids[cat], 'expense', round(amt * mult, 2), desc, _day(d)))

    cur.executemany(
        "INSERT INTO transactions(user_id, category_id, kind, amount, description, transaction_date) VALUES (1, %s, %s, %s, %s, %s)",
        rows
    )
    conn.commit()
    cur.close(); conn.close()


def metrics():
    conn = get_conn()
    cur  = conn.cursor()

    now   = datetime.date.today()
    start = now.replace(day=1).isoformat()

    cur.execute("""
        SELECT t.id, t.kind, t.amount::float, t.description,
               t.transaction_date::text AS date,
               ca.name AS category, ca.color
        FROM   transactions t
        JOIN   categories ca ON ca.id = t.category_id
        WHERE  t.user_id = 1 AND t.transaction_date >= %s
        ORDER  BY t.transaction_date DESC, t.id DESC
    """, (start,))
    month_rows = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT t.id, t.kind, t.amount::float, t.description,
               t.transaction_date::text AS date,
               ca.name AS category, ca.color
        FROM   transactions t
        JOIN   categories ca ON ca.id = t.category_id
        WHERE  t.user_id = 1
        ORDER  BY t.transaction_date DESC, t.id DESC
        LIMIT  100
    """)
    trans = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT b.id, b.monthly_limit::float AS limit_amount,
               ca.name AS category, ca.color
        FROM   budgets b
        JOIN   categories ca ON ca.id = b.category_id
        WHERE  b.user_id = 1
    """)
    budget_rows = [dict(r) for r in cur.fetchall()]

    budgets = []
    for b in budget_rows:
        actual = sum(x['amount'] for x in month_rows if x['kind'] == 'expense' and x['category'] == b['category'])
        budgets.append({**b, 'actual': actual, 'percent': round(actual / b['limit_amount'] * 100) if b['limit_amount'] else 0})

    cur.execute("SELECT * FROM financial_goals WHERE user_id = 1 ORDER BY id")
    goals = [dict(r) for r in cur.fetchall()]
    for g in goals:
        g['target_amount']  = float(g['target_amount'])
        g['saved_amount']   = float(g['saved_amount'])
        g['target_date']    = g['target_date'].isoformat() if hasattr(g['target_date'], 'isoformat') else str(g['target_date'])
        g['percent']        = min(100, round(g['saved_amount'] / g['target_amount'] * 100)) if g['target_amount'] else 0

    cur.execute("SELECT * FROM users WHERE id = 1")
    user = dict(cur.fetchone())
    user['created_at'] = str(user.get('created_at', ''))

    income  = sum(x['amount'] for x in month_rows if x['kind'] == 'income')
    expense = sum(x['amount'] for x in month_rows if x['kind'] == 'expense')
    planned = sum(b['limit_amount'] for b in budgets)
    utilization  = expense / planned if planned else 0
    save         = max(0, income - expense)
    savings_rate = save / income * 100 if income else 0
    expense_ratio= expense / income * 100 if income else 0
    score = round(
        min(40, savings_rate / 20 * 40) +
        max(0, 30 - expense_ratio / 100 * 30) +
        max(0, 30 - min(100, utilization * 100) / 100 * 30)
    )
    score = min(100, score)
    label = 'Strong' if score >= 80 else 'Building' if score >= 60 else 'Needs attention'

    spend_by = {}
    for x in month_rows:
        if x['kind'] == 'expense':
            spend_by[x['category']] = spend_by.get(x['category'], 0) + x['amount']

    trend = []
    for back in range(5, -1, -1):
        month = now.replace(day=1) - datetime.timedelta(days=back * 30)
        key   = month.strftime('%Y-%m')
        cur.execute(
            "SELECT kind, amount::float FROM transactions WHERE user_id=1 AND to_char(transaction_date,'YYYY-MM') = %s",
            (key,)
        )
        vals = cur.fetchall()
        trend.append({
            'month':   month.strftime('%b'),
            'income':  sum(x['amount'] for x in vals if x['kind'] == 'income'),
            'expense': sum(x['amount'] for x in vals if x['kind'] == 'expense'),
        })

    cur.close(); conn.close()
    return {
        'user': user, 'income': income, 'expense': expense, 'saved': save,
        'savings_rate': round(savings_rate, 1), 'expense_ratio': round(expense_ratio, 1),
        'score': score, 'score_label': label,
        'transactions': trans, 'month_transactions': month_rows,
        'budgets': budgets, 'goals': goals,
        'spend_by': spend_by, 'trend': trend,
    }
