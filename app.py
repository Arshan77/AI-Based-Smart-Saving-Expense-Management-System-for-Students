from flask import Flask, render_template, request, redirect, session, flash, jsonify, url_for
# import mysql.connector
import os
from werkzeug.utils import secure_filename
from flask_bcrypt import Bcrypt
from datetime import datetime
import requests
import google.generativeai as genai
from uuid import uuid4

# ============================================================
# Application Initialization & Configuration Section
# ------------------------------------------------------------
# This section initializes the Flask application and sets up:
# - Secret key for session management
# - Gemini API client configuration
# - Password hashing using Bcrypt
# - MySQL database connection
# - Dictionary cursor for structured database queries
# ============================================================
app = Flask(__name__)
# Using your specific secret key
app.secret_key = "supersecretkey"

# Gemini API Setup
API_KEY = "AIzaSyABogLBIPoT4uQvR4GgTyup5dDI5XFB9Pc"
client = genai.Client(api_key=API_KEY)

# Upload folder setup
app.config["UPLOAD_FOLDER"] = "static/uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

bcrypt = Bcrypt(app)

# Database Connection
import psycopg2
import os

DATABASE_URL = os.environ.get("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Dictionary cursor allows accessing rows by column nam

# ============================================================
# Home & User Registration Routes
# ------------------------------------------------------------
# This section handles:
# - Redirecting users based on login session
# - New user registration
# - Checking existing users in the database
# - Password hashing using Bcrypt
# - Storing secure user data in MySQL
# ============================================================
@app.route("/")
def home():
    if "user_id" in session:
        return redirect("/dashboard")
    return redirect("/login")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash("User already exists with this email. Please login.", "danger")
            return redirect("/register")

        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")

        cursor.execute(
            "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
            (name, email, hashed_password)
        )
        conn.commit()

        flash("Registration successful! Please login.", "success")
        return redirect("/login")

    return render_template("register.html")

# ============================================================
# User Login & Logout Routes
# ------------------------------------------------------------
# This section handles:
# - User authentication using email and password
# - Secure password verification with Bcrypt
# - Session creation for logged-in users
# - Flash messages for login errors
# - Session clearing during logout
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user and bcrypt.check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect("/dashboard")
        else:
            flash("Invalid Email or Password", "danger")
            return redirect("/login")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ============================================================
# Dashboard Route – Financial Summary & AI Analysis Engine
# ------------------------------------------------------------
# This section performs:
# - Session validation for secure access
# - Fetching user profile information
# - Calculating total income, expenses, and balance
# - Retrieving transaction history (income, expense, savings)
# - Monthly budget retrieval
# - AI-based financial analysis and behavior classification
# - Expense category analysis
# - Spending ratio evaluation
# - 50/30/20 financial recommendation logic
# - Savings comparison analysis
# - Rendering complete financial dashboard to the user
# ============================================================

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]

    # --- PROFILE PIC ---
    cursor.execute("SELECT profile_pic FROM users WHERE id=%s", (user_id,))
    user_data = cursor.fetchone()
    user_pic = user_data["profile_pic"] if user_data and user_data.get("profile_pic") else None

    # --- TOTAL INCOME ---
    cursor.execute("SELECT SUM(amount) AS total FROM income WHERE user_id=%s", (user_id,))
    income_data = cursor.fetchone()
    total_income = float(income_data["total"]) if income_data and income_data["total"] is not None else 0.0

    # --- TOTAL EXPENSE ---
    cursor.execute("SELECT SUM(amount) AS total FROM expense WHERE user_id=%s", (user_id,))
    expense_data = cursor.fetchone()
    total_expense = float(expense_data["total"]) if expense_data and expense_data["total"] is not None else 0.0

    # --- BALANCE ---
    balance = total_income - total_expense

    # --- HISTORY FETCHING ---
    cursor.execute("SELECT id, amount, source, income_date FROM income WHERE user_id=%s ORDER BY income_date DESC", (user_id,))
    incomes = cursor.fetchall()

    cursor.execute("SELECT id, amount, category, expense_date FROM expense WHERE user_id=%s ORDER BY expense_date DESC", (user_id,))
    expenses = cursor.fetchall()

    cursor.execute("SELECT id, amount, saving_date FROM savings WHERE user_id=%s ORDER BY saving_date DESC", (user_id,))
    savings = cursor.fetchall()

    # --- BUDGET FETCHING ---
    now = datetime.now()
    month, year = now.strftime("%B"), now.year
    cursor.execute("SELECT monthly_budget FROM budget WHERE user_id=%s AND month=%s AND year=%s", (user_id, month, year))
    budget_data = cursor.fetchone()
    monthly_budget = float(budget_data["monthly_budget"]) if budget_data and budget_data["monthly_budget"] is not None else 0.0

    # ======================================================
    # AI ENGINE START
    # ======================================================

    if total_income > 0:
        balance_percentage = round((balance / total_income) * 100, 2)
    else:
        balance_percentage = 0.0

    if balance_percentage < 10:
        saving_status = "⚠ Poor Saving Habit"
    elif 10 <= balance_percentage < 20:
        saving_status = "🙂 Average Saver"
    elif 20 <= balance_percentage < 30:
        saving_status = "💪 Good Saving Behavior"
    else:
        saving_status = "🏆 Excellent Financial Control"

    if total_income == 0:
        ai_message = "Start adding income to activate AI analysis."
        ai_color = "secondary"
    elif balance_percentage < 0:
        ai_message = "🚨 Your expenses exceed your income. Immediate financial control is needed."
        ai_color = "danger"
    elif balance_percentage < 10:
        ai_message = "⚠ Your remaining balance is very low. You are close to overspending."
        ai_color = "warning"
    elif balance_percentage < 30:
        ai_message = "🙂 Your balance is moderate, but better expense control can improve it."
        ai_color = "info"
    elif balance_percentage < 50:
        ai_message = "💪 Good job! You are maintaining a healthy remaining balance."
        ai_color = "primary"
    else:
        ai_message = "🏆 Excellent! You have strong financial control and a high remaining balance."
        ai_color = "success"

    cursor.execute("""
        SELECT category, SUM(amount) AS total
        FROM expense
        WHERE user_id=%s
        GROUP BY category
        ORDER BY total DESC
        LIMIT 1
    """, (user_id,))
    top_category_data = cursor.fetchone()

    if top_category_data and top_category_data["total"] is not None:
        top_category = top_category_data["category"]
        top_category_amount = float(top_category_data["total"])
        category_message = f"You spend most on {top_category} (₹{top_category_amount}). Consider reducing it."
    else:
        category_message = "No expense data available yet."

    if total_income > 0:
        expense_ratio = (total_expense / total_income) * 100
    else:
        expense_ratio = 0

    if expense_ratio > 100:
        expense_alert = "🚨 You are spending more than your income!"
    elif expense_ratio > 80:
        expense_alert = "⚠ Warning: You are close to overspending."
    else:
        expense_alert = "✅ Your spending is under control."

    recommended_savings = round(total_income * 0.20, 2)
    recommended_needs = round(total_income * 0.50, 2)
    recommended_wants = round(total_income * 0.30, 2)

    cursor.execute("SELECT SUM(amount) AS total FROM savings WHERE user_id=%s", (user_id,))
    saving_data = cursor.fetchone()
    actual_savings = float(saving_data["total"]) if saving_data and saving_data["total"] is not None else 0.0

    if total_income == 0:
        savings_compare_msg = "Add income to activate savings analysis."
        savings_compare_color = "secondary"
    elif actual_savings > recommended_savings:
        extra_saved = round(actual_savings - recommended_savings, 2)
        savings_compare_msg = f"🔥 You saved ₹{extra_saved} more than recommended. Excellent discipline!"
        savings_compare_color = "success"
    elif actual_savings == recommended_savings:
        savings_compare_msg = "🎯 Perfect! You saved exactly as recommended."
        savings_compare_color = "info"
    elif actual_savings < 0:
        savings_compare_msg = "🚨 You are in deficit. Spending exceeds income."
        savings_compare_color = "danger"
    else:
        less_saved = round(recommended_savings - actual_savings, 2)
        savings_compare_msg = f"⚠ You saved ₹{less_saved} less than recommended. Try increasing savings."
        savings_compare_color = "warning"

    ai_answer = None

    # ======================================================
    # AI ENGINE END
    # ======================================================

    return render_template(
        "dashboard.html",
        name=session.get("user_name", "User"),
        total_income=total_income,
        total_expense=total_expense,
        balance=balance,
        incomes=incomes,
        expenses=expenses,
        savings=savings,
        user_pic=user_pic,
        monthly_budget=monthly_budget,
        balance_percentage=balance_percentage,
        saving_status=saving_status,
        ai_message=ai_message,
        ai_color=ai_color,
        category_message=category_message,
        expense_alert=expense_alert,
        recommended_savings=recommended_savings,
        recommended_needs=recommended_needs,
        recommended_wants=recommended_wants,
        actual_savings=actual_savings,
        savings_compare_msg=savings_compare_msg,
        savings_compare_color=savings_compare_color,
        ai_answer=ai_answer
    )

# =================================================
# DATA ENTRY ROUTES
# =================================================

@app.route("/add_income", methods=["GET", "POST"])
def add_income():
    if "user_id" not in session: return redirect("/login")
    if request.method == "POST":
        cursor.execute("INSERT INTO income (user_id, amount, source, income_date) VALUES (%s, %s, %s, %s)", 
                       (session["user_id"], request.form["amount"], request.form["source"], request.form["date"]))
        conn.commit()
        flash("Income added successfully!", "success")
        return redirect("/dashboard")
    return render_template("add_income.html")

@app.route("/add_expense", methods=["GET", "POST"])
def add_expense():
    if "user_id" not in session: return redirect("/login")
    if request.method == "POST":
        cursor.execute("INSERT INTO expense (user_id, amount, category, expense_date) VALUES (%s, %s, %s, %s)", 
                       (session["user_id"], request.form["amount"], request.form["category"], request.form["date"]))
        conn.commit()
        flash("Expense added successfully!", "success")
        return redirect("/dashboard")
    return render_template("add_expense.html")

@app.route("/add_saving", methods=["GET", "POST"])
def add_saving():
    if "user_id" not in session: return redirect("/login")
    if request.method == "POST":
        cursor.execute("INSERT INTO savings (user_id, amount, saving_date) VALUES (%s, %s, %s)", 
                       (session["user_id"], request.form["amount"], datetime.now().date()))
        conn.commit()
        return redirect("/dashboard")
    return render_template("add_saving.html")

# =================================================
# DELETE & CLEAR ROUTES
# =================================================

@app.route("/delete_income/<int:id>")
def delete_income(id):
    if "user_id" not in session: return redirect("/login")
    cursor.execute("DELETE FROM income WHERE id=%s AND user_id=%s", (id, session["user_id"]))
    conn.commit()
    return redirect("/dashboard")

@app.route("/delete_expense/<int:id>")
def delete_expense(id):
    if "user_id" not in session: return redirect("/login")
    cursor.execute("DELETE FROM expense WHERE id=%s AND user_id=%s", (id, session["user_id"]))
    conn.commit()
    return redirect("/dashboard")

@app.route("/delete_saving/<int:id>")
def delete_saving(id):
    if "user_id" not in session: return redirect("/login")
    cursor.execute("DELETE FROM savings WHERE id=%s AND user_id=%s", (id, session["user_id"]))
    conn.commit()
    return redirect("/dashboard")

@app.route("/clear_income")
def clear_income():
    cursor.execute("DELETE FROM income WHERE user_id=%s", (session["user_id"],))
    conn.commit()
    return redirect("/dashboard")

@app.route("/clear_expense")
def clear_expense():
    cursor.execute("DELETE FROM expense WHERE user_id=%s", (session["user_id"],))
    conn.commit()
    return redirect("/dashboard")

@app.route("/clear_savings")
def clear_savings():
    cursor.execute("DELETE FROM savings WHERE user_id=%s", (session["user_id"],))
    conn.commit()
    return redirect("/dashboard")

# =================================================
# PROFILE & BUDGET MANAGEMENT
# =================================================

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session: return redirect("/login")
    user_id = session["user_id"]
    if request.method == "POST":
        name = request.form["name"]
        file = request.files["profile_pic"]
        if file and file.filename != "":
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            cursor.execute("UPDATE users SET name=%s, profile_pic=%s WHERE id=%s", (name, filename, user_id))
        else:
            cursor.execute("UPDATE users SET name=%s WHERE id=%s", (name, user_id))
        conn.commit()
        session["user_name"] = name
        return redirect("/dashboard")
    cursor.execute("SELECT name, profile_pic FROM users WHERE id=%s", (user_id,))
    user = cursor.fetchone()
    return render_template("profile.html", user=user)

@app.route("/set_budget", methods=["GET", "POST"])
def set_budget():
    if "user_id" not in session: return redirect("/login")
    user_id = session["user_id"]
    if request.method == "POST":
        amount = request.form["amount"]
        now = datetime.now()
        month, year = now.strftime("%B"), now.year
        cursor.execute("SELECT * FROM budget WHERE user_id=%s AND month=%s AND year=%s", (user_id, month, year))
        if cursor.fetchone():
            cursor.execute("UPDATE budget SET monthly_budget=%s WHERE user_id=%s AND month=%s AND year=%s", (amount, user_id, month, year))
        else:
            cursor.execute("INSERT INTO budget (user_id, monthly_budget, month, year) VALUES (%s, %s, %s, %s)", (user_id, amount, month, year))
        conn.commit()
        return redirect("/dashboard")
    return render_template("set_budget.html")

# ============================================================
# AI Chat System – Gemini Integration with Multi-Chat Support
# ------------------------------------------------------------
# This section handles:
# - Secure access to AI chat (session protected)
# - Multiple chat creation and switching
# - Session-based chat storage
# - Sending user prompts to Gemini AI
# - Storing AI responses in conversation history
# - Dynamic chat title generation
# - Chat deletion functionality
# - Rendering AI chat interface
# ============================================================

@app.route('/ask_ai', methods=['GET', 'POST'])
def ask_ai():
    if "user_id" not in session: return redirect("/login")
    
    if "chats" not in session:
        session["chats"] = []
    if "active_chat_id" not in session:
        session["active_chat_id"] = None

    if request.args.get("new_chat"):
        new_chat = {"id": str(uuid4()), "title": "New Chat", "messages": []}
        session["chats"].append(new_chat)
        session["active_chat_id"] = new_chat["id"]
        session.modified = True
        return redirect(url_for('ask_ai'))

    if request.args.get("chat_id"):
        session["active_chat_id"] = request.args.get("chat_id")
        session.modified = True
        return redirect(url_for('ask_ai'))

    if not session["active_chat_id"] or not session["chats"]:
        new_chat = {"id": str(uuid4()), "title": "Initial Chat", "messages": []}
        session["chats"] = [new_chat]
        session["active_chat_id"] = new_chat["id"]
        session.modified = True

    if request.method == 'POST':
        question = request.form.get('question')
        active_chat = next((chat for chat in session["chats"] if chat["id"] == session["active_chat_id"]), None)
        
        if active_chat and question:
            active_chat["messages"].append({"role": "user", "content": question})
            try:
                response = client.models.generate_content(model="gemini-2.5-flash", contents=question)
                ai_answer = response.text
            except Exception as e:
                ai_answer = f"Error: {str(e)}"
            
            active_chat["messages"].append({"role": "ai", "content": ai_answer})
            if len(active_chat["messages"]) <= 2:
                active_chat["title"] = question[:30]
            session.modified = True

    current_active_chat = next((chat for chat in session["chats"] if chat["id"] == session["active_chat_id"]), None)
    return render_template('ask_ai.html', chats=session["chats"], active_chat=current_active_chat)

@app.route('/delete_chat/<chat_id>')
def delete_chat(chat_id):
    if "chats" in session:
        session["chats"] = [c for c in session["chats"] if c["id"] != chat_id]
        if session.get("active_chat_id") == chat_id:
            session["active_chat_id"] = None
        session.modified = True
    return redirect(url_for('ask_ai'))

# =================================================
# MAIN ENTRY POINT
# =================================================
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)