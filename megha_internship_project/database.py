import sqlite3
import os

DATABASE = 'expenses.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    with conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                monthly_budget REAL DEFAULT 0.0
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        try:
            conn.execute('ALTER TABLE transactions ADD COLUMN user_id INTEGER REFERENCES users(id)')
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute('ALTER TABLE users ADD COLUMN monthly_budget REAL DEFAULT 0.0')
        except sqlite3.OperationalError:
            pass
    conn.close()

def add_user(username, password):
    conn = get_db()
    try:
        with conn:
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_user_by_username(username):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return user

def get_user_by_id(user_id):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return user

def update_budget(user_id, budget):
    conn = get_db()
    with conn:
        conn.execute('UPDATE users SET monthly_budget = ? WHERE id = ?', (budget, user_id))
    conn.close()

def add_transaction(user_id, type, amount, category, description, date_val):
    conn = get_db()
    with conn:
        conn.execute(
            'INSERT INTO transactions (type, amount, category, description, date, user_id) VALUES (?, ?, ?, ?, ?, ?)',
            (type, amount, category, description, date_val, user_id)
        )
    conn.close()

def get_transactions(user_id, limit=None, start_date=None, end_date=None):
    conn = get_db()
    query = 'SELECT * FROM transactions WHERE (user_id = ? OR user_id IS NULL)'
    params = [user_id]
    
    if start_date:
        query += ' AND date >= ?'
        params.append(start_date)
    if end_date:
        # append 23:59:59 to end date to include the whole day if it's just 'YYYY-MM-DD'
        query += ' AND date <= ?'
        if len(end_date) == 10:
            params.append(end_date + ' 23:59:59')
        else:
            params.append(end_date)
            
    query += ' ORDER BY date DESC'
    if limit and not (start_date or end_date):
        query += f' LIMIT {limit}'
        
    transactions = conn.execute(query, tuple(params)).fetchall()
    conn.close()
    return transactions

def get_summary(user_id):
    conn = get_db()
    
    # Get current month's expenses for budget calculation
    current_month_expense = conn.execute('''
        SELECT SUM(amount) FROM transactions 
        WHERE type = "expense" AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now') 
        AND (user_id = ? OR user_id IS NULL)
    ''', (user_id,)).fetchone()[0] or 0.0
    
    total_income = conn.execute('SELECT SUM(amount) FROM transactions WHERE type = "income" AND (user_id = ? OR user_id IS NULL)', (user_id,)).fetchone()[0] or 0.0
    total_expense = conn.execute('SELECT SUM(amount) FROM transactions WHERE type = "expense" AND (user_id = ? OR user_id IS NULL)', (user_id,)).fetchone()[0] or 0.0
    conn.close()
    return {
        'income': total_income,
        'expense': total_expense,
        'balance': total_income - total_expense,
        'current_month_expense': current_month_expense
    }

def get_report(user_id):
    conn = get_db()
    report = conn.execute('''
        SELECT type, category, SUM(amount) as total
        FROM transactions
        WHERE user_id = ? OR user_id IS NULL
        GROUP BY type, category
        ORDER BY type, total DESC
    ''', (user_id,)).fetchall()
    conn.close()
    return report

def get_monthly_expenses(user_id):
    conn = get_db()
    report = conn.execute('''
        SELECT strftime('%m', date) as month_num, strftime('%Y-%m', date) as month, SUM(amount) as total
        FROM transactions
        WHERE type = 'expense' AND (user_id = ? OR user_id IS NULL)
        GROUP BY month
        ORDER BY month ASC
    ''', (user_id,)).fetchall()
    conn.close()
    return report

def get_monthly_overview(user_id):
    conn = get_db()
    # Get last 6 months of data
    report = conn.execute('''
        SELECT 
            strftime('%Y-%m', date) as month,
            SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) as income,
            SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) as expense
        FROM transactions
        WHERE (user_id = ? OR user_id IS NULL)
        AND date >= date('now', '-6 months')
        GROUP BY month
        ORDER BY month ASC
    ''', (user_id,)).fetchall()
    conn.close()
    return report

def get_category_distribution(user_id):
    conn = get_db()
    report = conn.execute('''
        SELECT category, SUM(amount) as total
        FROM transactions
        WHERE type = 'expense' AND (user_id = ? OR user_id IS NULL)
        GROUP BY category
        ORDER BY total DESC
    ''', (user_id,)).fetchall()
    conn.close()
    return report

def get_transaction(id, user_id):
    conn = get_db()
    transaction = conn.execute('SELECT * FROM transactions WHERE id = ? AND (user_id = ? OR user_id IS NULL)', (id, user_id)).fetchone()
    conn.close()
    return transaction

def update_transaction(id, user_id, type, amount, category, description, date_val):
    conn = get_db()
    with conn:
        conn.execute(
            'UPDATE transactions SET type = ?, amount = ?, category = ?, description = ?, date = ? WHERE id = ? AND (user_id = ? OR user_id IS NULL)',
            (type, amount, category, description, date_val, id, user_id)
        )
    conn.close()

def delete_transaction(id, user_id):
    conn = get_db()
    with conn:
        conn.execute('DELETE FROM transactions WHERE id = ? AND (user_id = ? OR user_id IS NULL)', (id, user_id))
    conn.close()
