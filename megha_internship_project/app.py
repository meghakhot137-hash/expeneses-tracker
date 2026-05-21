from flask import Flask, render_template, request, redirect, url_for, flash, session
import database
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super_secret_key_change_in_production')

# Initialize DB on startup
database.init_db()

CATEGORIES = [
    'Groceries',
    'Dining Out',
    'Transportation',
    'Fuel / Gas',
    'Housing / Rent',
    'Utilities',
    'Subscriptions',
    'Entertainment',
    'Health & Medical',
    'Shopping',
    'Salary / Wages',
    'Freelance',
    'Other'
]

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Please provide both username and password.', 'danger')
            return redirect(url_for('register'))
            
        hashed_password = generate_password_hash(password)
        if database.add_user(username, hashed_password):
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Username already exists.', 'danger')
            return redirect(url_for('register'))
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = database.get_user_by_username(username)
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    search = request.args.get('search', '')
    
    user = database.get_user_by_id(session['user_id'])
    budget = user['monthly_budget'] if user else 0.0
    
    summary = database.get_summary(session['user_id'])
    
    # Enhanced transaction retrieval with search
    conn = database.get_db()
    query = 'SELECT * FROM transactions WHERE (user_id = ? OR user_id IS NULL)'
    params = [session['user_id']]
    
    if search:
        query += ' AND (description LIKE ? OR category LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%'])
    
    if start_date:
        query += ' AND date >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND date <= ?'
        params.append(end_date + ' 23:59:59' if len(end_date) == 10 else end_date)
        
    query += ' ORDER BY date DESC LIMIT 10'
    transactions = conn.execute(query, tuple(params)).fetchall()
    conn.close()

    # Data for charts
    monthly_overview = database.get_monthly_overview(session['user_id'])
    category_distribution = database.get_category_distribution(session['user_id'])
    
    return render_template('index.html', 
                           summary=summary, 
                           transactions=transactions, 
                           start_date=start_date, 
                           end_date=end_date, 
                           search=search,
                           budget=budget,
                           monthly_overview=[dict(row) for row in monthly_overview],
                           category_distribution=[dict(row) for row in category_distribution])

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        type = request.form.get('type')
        amount = float(request.form.get('amount'))
        category = request.form.get('category')
        description = request.form.get('description')
        date_str = request.form.get('date') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        database.add_transaction(session['user_id'], type, amount, category, description, date_str)
        flash(f'{type.capitalize()} of ${amount:.2f} added successfully!', 'success')
        return redirect(url_for('index'))
        
    return render_template('add_transaction.html', categories=CATEGORIES, now=datetime.now().strftime('%Y-%m-%d'))

@app.route('/report')
@login_required
def report():
    report_data = database.get_report(session['user_id'])
    income_data = [dict(row) for row in report_data if row['type'] == 'income']
    expense_data = [dict(row) for row in report_data if row['type'] == 'expense']
    
    monthly_expenses = database.get_monthly_expenses(session['user_id'])
    monthly_data = [dict(row) for row in monthly_expenses]
    
    return render_template('report.html', income_data=income_data, expense_data=expense_data, monthly_data=monthly_data)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    transaction = database.get_transaction(id, session['user_id'])
    if not transaction:
        flash('Transaction not found or unauthorized.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        type = request.form.get('type')
        amount = float(request.form.get('amount'))
        category = request.form.get('category')
        description = request.form.get('description')
        date_str = request.form.get('date') or transaction['date']
        
        database.update_transaction(id, session['user_id'], type, amount, category, description, date_str)
        flash('Transaction updated successfully!', 'success')
        return redirect(url_for('index'))
        
    return render_template('edit_transaction.html', transaction=transaction, categories=CATEGORIES)

@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    database.delete_transaction(id, session['user_id'])
    flash('Transaction deleted.', 'success')
    return redirect(url_for('index'))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user = database.get_user_by_id(session['user_id'])
    if request.method == 'POST':
        budget = request.form.get('budget', type=float)
        if budget is not None:
            database.update_budget(session['user_id'], budget)
            flash('Budget updated successfully!', 'success')
            return redirect(url_for('settings'))
            
    return render_template('settings.html', user=user)

@app.route('/export/csv')
@login_required
def export_csv():
    import csv
    import io
    from flask import Response
    
    transactions = database.get_transactions(session['user_id'])
    
    dest = io.StringIO()
    writer = csv.writer(dest)
    writer.writerow(['ID', 'Type', 'Amount', 'Category', 'Description', 'Date'])
    
    for t in transactions:
        writer.writerow([t['id'], t['type'], t['amount'], t['category'], t['description'], t['date']])
    
    output = dest.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=expenses.csv"}
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)
