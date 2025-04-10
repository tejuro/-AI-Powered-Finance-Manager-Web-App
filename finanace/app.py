from flask import Flask, render_template, request, redirect, session, flash, url_for,jsonify
import pandas as pd
import os
import threading
import time
from datetime import datetime
import smtplib
import json
from collections import defaultdict
import google.generativeai as genai
import pandas as pd
from flask import jsonify

genai.configure(api_key="AIzaSyAGz847_wHPIRuI8_mn2abA6gsnKuh3ckU")

model = genai.GenerativeModel("gemini-pro")

app = Flask(__name__)
app.secret_key = 'your-secret-key'

USERS_FILE = 'users.json'
EXPENSES_FILE = 'expenses.xlsx'
BUDGET_FILE = 'budget.xlsx'
REMINDER_FILE = 'reminders.xlsx'

@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')

        if not email or not password or not name:
            flash("Please fill in all fields.")
            return redirect(url_for('signup'))

        # Load users.json
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as file:
                users = json.load(file)
        else:
            users = {}

        if email in users:
            flash("You have already signed up. Please log in.")
            return redirect(url_for('login'))

        # Save user
        users[email] = {'password': password, 'name': name}
        with open(USERS_FILE, 'w') as file:
            json.dump(users, file)

        flash("Signup successful! Please log in.")
        return redirect(url_for('login'))

    return render_template('signup.html')  # Renders the signup form if it's a GET request

@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash("Please enter both email and password.")
            return redirect(url_for('login'))

        users = {}
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as file:
                users = json.load(file)

        if email not in users:
            flash("Email not found. Please sign up.")
            return redirect(url_for('signup'))

        if users[email]['password'] != password:
            flash("Incorrect password.")
            return redirect(url_for('login'))

        # ✅ Set session data
        session['email'] = email
        session['name'] = users[email]['name']
        flash("Login successful!")


            # ✅ Clear user-specific BUDGET
        if os.path.exists(BUDGET_FILE):
            df = pd.read_excel(BUDGET_FILE)
            df = df[df['email'] != email]
            df.to_excel(BUDGET_FILE, index=False)

            # ✅ Clear user-specific BILL REMINDERS
        if os.path.exists(REMINDER_FILE):
            df = pd.read_excel(REMINDER_FILE)
            df = df[df['email'] != email]
            df.to_excel(REMINDER_FILE, index=False)

        return redirect(url_for('dashboard'))

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'email' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for('login'))


@app.route('/set_budget', methods=['POST'])
def set_budget():
    email = session.get('email')
    budget = request.form['budget']
    now = datetime.now()
    month = now.month
    year = now.year

    df = pd.DataFrame([[email, float(budget),month,year]], columns=['email', 'budget','month','year'])
    if os.path.exists(BUDGET_FILE):
        old = pd.read_excel(BUDGET_FILE)
        old = old[old['email'].str.strip().str.lower() != email.strip().lower()]
        old = old.dropna(how='all')
        df = pd.concat([old, df])

    df.to_excel(BUDGET_FILE, index=False)
    return "✅ Budget set successfully!"

from datetime import datetime

@app.route('/add_expense', methods=['POST'])
def add_expense():
    email = session.get('email')
    name = request.form['name']
    amount = float(request.form['amount'])
    date_str = request.form.get('date')  # Get date from the form

    try:
        # Convert the date string from the form to a datetime object
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        date = datetime.now().date()  # fallback to today if date is invalid

    # Create new expense entry
    df = pd.DataFrame([[email, name, amount, date]], columns=['email', 'name', 'amount', 'date'])

    # Load existing and append
    if os.path.exists(EXPENSES_FILE):
        old = pd.read_excel(EXPENSES_FILE)
        old = old.dropna(how='all')
        df = pd.concat([old, df])

    df.to_excel(EXPENSES_FILE, index=False)
    count = df[df['email'] == email].shape[0]
    return f"✅ Your {count} expense(s) added!"


@app.route('/ai/fraud_detection')
def fraud_detection():
    email = session.get('email')

    if not os.path.exists(EXPENSES_FILE) or not os.path.exists(BUDGET_FILE):
        return "No data available for fraud detection."

    expenses_df = pd.read_excel(EXPENSES_FILE)
    budget_df = pd.read_excel(BUDGET_FILE)

    expenses_df['date'] = pd.to_datetime(expenses_df['date'])
    now = datetime.now()
    this_month = now.month
    this_year = now.year

    # Filter current user & current month
    user_expenses = expenses_df[
        (expenses_df['email'] == email) &
        (expenses_df['date'].dt.month == this_month) &
        (expenses_df['date'].dt.year == this_year)
    ]

    if user_expenses.empty:
        return "No expenses found for this month."

    # Get current user's latest budget
    user_budget = budget_df[budget_df['email'] == email]
    if user_budget.empty:
        return "No budget set for this month."

    latest_budget = user_budget.iloc[-1]['budget']
    total_spent = user_expenses['amount'].sum()

    # Apply fraud detection logic based on total spent
    threshold = 0.20 if total_spent > 20000 else 0.30

    if total_spent > latest_budget * (1 + threshold):
        return f"🚨 Fraud Alert! You've spent ₹{total_spent:.2f}, which exceeds your budget ₹{latest_budget:.2f} by more than {int(threshold*100)}%."

    return f"✅ No fraud detected. You've spent ₹{total_spent:.2f} within your budget."



@app.route('/ai/smart_tips', methods=['POST'])
def ai_smart_tips():
    if not os.path.exists(EXPENSES_FILE):
        return jsonify({"tip": "⚠ No expense data found. Please add at least 3 months of expenses."})

    df = pd.read_excel(EXPENSES_FILE)

    if df.empty or len(df) < 10:
        return jsonify({"tip": "⚠ Add more expense data for smarter tips (at least 10 entries recommended)."})

    avg_spend = df['amount'].mean()
    high_spend = df.loc[df['amount'] == df['amount'].max()]

    tip = f"Your average expense is ₹{avg_spend:.2f}. Try reducing '{high_spend.iloc[0]['name']}' to save more."

    return jsonify({"tip": tip})

@app.route('/ai/expense_prediction')
def predict_next_month_expense():
    email = session.get('email')
    if not os.path.exists(EXPENSES_FILE):
        return "No expenses data to predict."

    df = pd.read_excel(EXPENSES_FILE)
    df['date'] = pd.to_datetime(df['date'])
    df = df[df['email'] == email]

    if df.empty:
        return "No expenses found for this user."

    # Extract month from date
    df['month'] = df['date'].dt.to_period('M')

    # Get last 3 months
    last_3_months = sorted(df['month'].unique())[-3:]
    df_last_3 = df[df['month'].isin(last_3_months)]

    # Group by category and month
    pivot = df_last_3.groupby(['month', 'name'])['amount'].sum().reset_index()

    # Count how many months each category appears in
    category_counts = pivot.groupby('name')['month'].count()

    predictions = {}
    for category in pivot['name'].unique():
        cat_data = pivot[pivot['name'] == category]['amount']
        if category_counts[category] == 3:
            # Common category in all 3 months → take monthly average
            predictions[category] = cat_data.mean()
        else:
            # Uncommon → take total average (even if in 1 or 2 months)
            predictions[category] = cat_data.mean()

    # Generate output
    result = "📊 Category-wise Prediction:\n"
    total = 0
    for cat, val in predictions.items():
        result += f"🔹 {cat}: ₹{val:.2f}\n"
        total += val

    result += f"\n📈 Total Predicted Expense for Next Month: ₹{total:.2f}"
    return result

@app.route('/set_reminder', methods=['GET', 'POST'])
def set_reminder():
    if request.method == 'POST':
        bill_name = request.form['bill_name']
        due_date = request.form['due_date']
        email = request.form['email']

        df = pd.DataFrame([[bill_name, due_date, email]], columns=['bill_name', 'due_date', 'email'])

        if os.path.exists(REMINDER_FILE):
            old = pd.read_excel(REMINDER_FILE)
            df = pd.concat([old, df], ignore_index=True)

        df.to_excel(REMINDER_FILE, index=False)
        return "✅ Reminder Set Successfully!"

    return render_template('set_reminder.html')

def send_email(to_email, subject, message):
    sender_email = "tejuselvaraj2006@gmail.com"
    sender_password = "tyrw nkfd rihr tydh"  # App password for Gmail

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(sender_email, sender_password)
            msg = f"Subject: {subject}\n\n{message}"
            smtp.sendmail(sender_email, to_email, msg)
            print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")
def reminder_check():
    sent_today = set()  # To avoid duplicate emails within the same day

    while True:
        if os.path.exists(REMINDER_FILE):
            try:
                df = pd.read_excel(REMINDER_FILE)
                today = datetime.now().date()

                for _, row in df.iterrows():
                    due_date = pd.to_datetime(row['due_date']).date()
                    identifier = f"{row['email']}_{row['bill_name']}_{due_date}"

                    if due_date == today and identifier not in sent_today:
                        send_email(
                            row['email'],
                            "Bill Reminder",
                            f"Hi! Your bill '{row['bill_name']}' is due today ({due_date})!"
                        )
                        print(f"✅ Reminder sent to {row['email']} for {row['bill_name']}")
                        sent_today.add(identifier)

            except Exception as e:
                print("❌ Error in reminder check:", e)

        time.sleep(10)

if __name__ == "__main__":
    threading.Thread(target=reminder_check, daemon=True).start()
    app.run(debug=True)
