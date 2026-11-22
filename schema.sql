PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  currency TEXT NOT NULL DEFAULT 'INR',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  kind TEXT NOT NULL CHECK(kind IN ('income','expense')),
  color TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  category_id INTEGER NOT NULL REFERENCES categories(id),
  kind TEXT NOT NULL CHECK(kind IN ('income','expense')),
  amount REAL NOT NULL CHECK(amount > 0),
  description TEXT NOT NULL,
  transaction_date TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS budgets (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  category_id INTEGER NOT NULL REFERENCES categories(id),
  monthly_limit REAL NOT NULL CHECK(monthly_limit > 0),
  UNIQUE(user_id, category_id)
);
CREATE TABLE IF NOT EXISTS financial_goals (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  name TEXT NOT NULL,
  target_amount REAL NOT NULL CHECK(target_amount > 0),
  saved_amount REAL NOT NULL DEFAULT 0 CHECK(saved_amount >= 0),
  target_date TEXT NOT NULL
);
