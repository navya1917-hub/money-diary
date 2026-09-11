from flask import Flask, render_template, request, redirect, url_for, session
import pg8000
import os
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)

# --------------------------------------------------
# FLASK SECRET KEY
# --------------------------------------------------

app.secret_key = os.environ.get("FLASK_SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY environment variable is not set.")


# --------------------------------------------------
# POSTGRESQL CONNECTION
# --------------------------------------------------

conn = pg8000.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    port=int(os.environ.get("DB_PORT", "5432")),
    database=os.environ.get("DB_NAME", "Money_dairy"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD")
)


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# --------------------------------------------------
# REGISTER
# --------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            return "Passwords do not match!"

        password_hash = generate_password_hash(password)

        try:
            with conn.cursor() as cursor:

                cursor.execute(
                    """
                    INSERT INTO users (name, email, password_hash)
                    VALUES (%s, %s, %s)
                    """,
                    (name, email, password_hash)
                )

            conn.commit()

        except Exception as e:
            conn.rollback()
            return f"Registration failed: {e}"

        return redirect(url_for("login"))

    return render_template("register.html")


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        with conn.cursor() as cursor:

            cursor.execute(
                """
                SELECT id, name, password_hash
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            user = cursor.fetchone()

        if user is None:
            return "Invalid email or password!"

        user_id = user[0]
        name = user[1]
        password_hash = user[2]

        if not check_password_hash(password_hash, password):
            return "Invalid email or password!"

        session["user_id"] = user_id
        session["user_name"] = name

        return redirect(url_for("dashboard"))

    return render_template("login.html")


# --------------------------------------------------
# LOGOUT
# --------------------------------------------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    with conn.cursor() as cursor:

        # Total income
        cursor.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE user_id = %s
            AND type = 'Income'
            """,
            (user_id,)
        )

        total_income = cursor.fetchone()[0]

        # Total expenses
        cursor.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE user_id = %s
            AND type = 'Expense'
            """,
            (user_id,)
        )

        total_expenses = cursor.fetchone()[0]

        # Balance
        balance = total_income - total_expenses

        # Recent transactions
        cursor.execute(
            """
            SELECT type, amount, category, date, description
            FROM transactions
            WHERE user_id = %s
            ORDER BY date DESC, id DESC
            LIMIT 5
            """,
            (user_id,)
        )

        recent_transactions = cursor.fetchall()

        # Spending by category
        cursor.execute(
            """
            SELECT category, SUM(amount)
            FROM transactions
            WHERE user_id = %s
            AND type = 'Expense'
            GROUP BY category
            ORDER BY SUM(amount) DESC
            """,
            (user_id,)
        )

        category_data = cursor.fetchall()

    total_category_expense = sum(item[1] for item in category_data)

    spending_data = []

    for category, amount in category_data:

        if total_category_expense > 0:
            percentage = round(
                (float(amount) / float(total_category_expense)) * 100,
                1
            )
        else:
            percentage = 0

        spending_data.append(
            (category, amount, percentage)
        )

    return render_template(
        "dashboard.html",
        total_income=total_income,
        total_expenses=total_expenses,
        balance=balance,
        recent_transactions=recent_transactions,
        spending_data=spending_data
    )


# --------------------------------------------------
# ADD INCOME
# --------------------------------------------------

@app.route("/add-income", methods=["GET", "POST"])
def add_income():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        amount = request.form["amount"]
        category = request.form["category"]
        transaction_date = request.form["date"]
        description = request.form["description"]

        user_id = session["user_id"]

        with conn.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO transactions
                (user_id, type, amount, category, date, description)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    "Income",
                    amount,
                    category,
                    transaction_date,
                    description
                )
            )

        conn.commit()

        return redirect(url_for("dashboard"))

    return render_template("add_income.html")


# --------------------------------------------------
# ADD EXPENSE
# --------------------------------------------------

@app.route("/add-expense", methods=["GET", "POST"])
def add_expense():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        amount = request.form["amount"]
        category = request.form["category"]
        transaction_date = request.form["date"]
        description = request.form["description"]

        user_id = session["user_id"]

        with conn.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO transactions
                (user_id, type, amount, category, date, description)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    "Expense",
                    amount,
                    category,
                    transaction_date,
                    description
                )
            )

        conn.commit()

        return redirect(url_for("dashboard"))

    return render_template("add_expense.html")


# --------------------------------------------------
# TRANSACTIONS
# --------------------------------------------------

@app.route("/transactions")
def transactions():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    with conn.cursor() as cursor:

        cursor.execute(
            """
            SELECT id, type, amount, category, date, description
            FROM transactions
            WHERE user_id = %s
            ORDER BY date DESC, id DESC
            """,
            (user_id,)
        )

        all_transactions = cursor.fetchall()

    return render_template(
        "transactions.html",
        transactions=all_transactions
    )


# --------------------------------------------------
# EDIT TRANSACTION
# --------------------------------------------------

@app.route("/edit-transaction/<int:transaction_id>", methods=["GET", "POST"])
def edit_transaction(transaction_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    with conn.cursor() as cursor:

        cursor.execute(
            """
            SELECT id, type, amount, category, date, description
            FROM transactions
            WHERE id = %s
            AND user_id = %s
            """,
            (transaction_id, user_id)
        )

        transaction = cursor.fetchone()

    if transaction is None:
        return "Transaction not found!"

    if request.method == "POST":

        amount = request.form["amount"]
        category = request.form["category"]
        transaction_date = request.form["date"]
        description = request.form["description"]

        with conn.cursor() as cursor:

            cursor.execute(
                """
                UPDATE transactions
                SET amount = %s,
                    category = %s,
                    date = %s,
                    description = %s
                WHERE id = %s
                AND user_id = %s
                """,
                (
                    amount,
                    category,
                    transaction_date,
                    description,
                    transaction_id,
                    user_id
                )
            )

        conn.commit()

        return redirect(url_for("transactions"))

    return render_template(
        "edit_transaction.html",
        transaction=transaction
    )


# --------------------------------------------------
# DELETE TRANSACTION
# --------------------------------------------------

@app.route("/delete-transaction/<int:transaction_id>", methods=["POST"])
def delete_transaction(transaction_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    with conn.cursor() as cursor:

        cursor.execute(
            """
            DELETE FROM transactions
            WHERE id = %s
            AND user_id = %s
            """,
            (transaction_id, user_id)
        )

    conn.commit()

    return redirect(url_for("transactions"))


# --------------------------------------------------
# MONTHLY REPORT
# --------------------------------------------------

@app.route("/reports")
def reports():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    selected_month = request.args.get("month")

    if not selected_month:
        selected_month = datetime.now().strftime("%Y-%m")

    try:
        selected_date = datetime.strptime(
            selected_month,
            "%Y-%m"
        )

    except ValueError:
        selected_date = datetime.now()
        selected_month = selected_date.strftime("%Y-%m")

    month_name = selected_date.strftime("%B")
    year = selected_date.year

    # --------------------------------------------------
    # MONTHLY INCOME
    # --------------------------------------------------

    with conn.cursor() as cursor:

        cursor.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE user_id = %s
            AND type = 'Income'
            AND TO_CHAR(date, 'YYYY-MM') = %s
            """,
            (user_id, selected_month)
        )

        monthly_income = cursor.fetchone()[0]

        # --------------------------------------------------
        # MONTHLY EXPENSES
        # --------------------------------------------------

        cursor.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE user_id = %s
            AND type = 'Expense'
            AND TO_CHAR(date, 'YYYY-MM') = %s
            """,
            (user_id, selected_month)
        )

        monthly_expenses = cursor.fetchone()[0]

        # --------------------------------------------------
        # CATEGORY SPENDING
        # --------------------------------------------------

        cursor.execute(
            """
            SELECT category, SUM(amount)
            FROM transactions
            WHERE user_id = %s
            AND type = 'Expense'
            AND TO_CHAR(date, 'YYYY-MM') = %s
            GROUP BY category
            ORDER BY SUM(amount) DESC
            """,
            (user_id, selected_month)
        )

        category_spending = cursor.fetchall()

        # --------------------------------------------------
        # MONTHLY TRANSACTIONS
        # --------------------------------------------------

        cursor.execute(
            """
            SELECT type, amount, category, date, description
            FROM transactions
            WHERE user_id = %s
            AND TO_CHAR(date, 'YYYY-MM') = %s
            ORDER BY date DESC, id DESC
            """,
            (user_id, selected_month)
        )

        monthly_transactions = cursor.fetchall()

    monthly_balance = monthly_income - monthly_expenses

    return render_template(
        "reports.html",
        selected_month=selected_month,
        month_name=month_name,
        year=year,
        monthly_income=monthly_income,
        monthly_expenses=monthly_expenses,
        monthly_balance=monthly_balance,
        category_spending=category_spending,
        monthly_transactions=monthly_transactions
    )


# --------------------------------------------------
# RUN APPLICATION
# --------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)