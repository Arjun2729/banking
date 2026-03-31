import random
import string
from decimal import Decimal, InvalidOperation
from functools import wraps

import mysql.connector
from flask import (Flask, flash, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from config import DB_CONFIG, SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_db():
    return mysql.connector.connect(**DB_CONFIG)


def query(sql, params=(), one=False, commit=False):
    """Execute a query and optionally return results."""
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute(sql, params)
    if commit:
        db.commit()
        db.close()
        return cur.lastrowid
    result = cur.fetchone() if one else cur.fetchall()
    db.close()
    return result


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    if "user_id" not in session:
        return None
    return query(
        "SELECT id, full_name, email, phone, created_at FROM users WHERE id=%s",
        (session["user_id"],), one=True
    )


def gen_account_no():
    while True:
        no = "ACC" + "".join(random.choices(string.digits, k=10))
        exists = query("SELECT id FROM accounts WHERE account_no=%s", (no,), one=True)
        if not exists:
            return no


# ---------------------------------------------------------------------------
# Context processor
# ---------------------------------------------------------------------------

@app.context_processor
def inject_user():
    return {"nav_user": get_current_user()}


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email     = request.form.get("email", "").strip().lower()
        phone     = request.form.get("phone", "").strip()
        password  = request.form.get("password", "")
        confirm   = request.form.get("confirm_password", "")

        if not all([full_name, email, password]):
            flash("Name, email, and password are required.", "danger")
            return render_template("register.html")
        if password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return render_template("register.html")

        existing = query("SELECT id FROM users WHERE email=%s", (email,), one=True)
        if existing:
            flash("An account with that email already exists.", "danger")
            return render_template("register.html")

        pw_hash = generate_password_hash(password)
        db = get_db()
        cur = db.cursor(dictionary=True)
        try:
            cur.execute(
                "INSERT INTO users (full_name, email, phone, password_hash) VALUES (%s,%s,%s,%s)",
                (full_name, email, phone or None, pw_hash)
            )
            user_id = cur.lastrowid
            acc_no = gen_account_no()
            cur.execute(
                "INSERT INTO accounts (user_id, account_type, account_no, balance) VALUES (%s,'checking',%s,0.00)",
                (user_id, acc_no)
            )
            db.commit()
        except Exception as e:
            db.rollback()
            flash("Registration failed. Please try again.", "danger")
            return render_template("register.html")
        finally:
            db.close()

        flash("Account created! Please log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = query("SELECT * FROM users WHERE email=%s", (email,), one=True)
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html")
        session["user_id"] = user["id"]
        flash(f"Welcome back, {user['full_name']}!", "success")
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Protected routes
# ---------------------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    uid = session["user_id"]
    accounts = query(
        "SELECT * FROM accounts WHERE user_id=%s ORDER BY created_at ASC", (uid,)
    )
    total_balance = sum(a["balance"] for a in accounts)

    recent_txns = query(
        """
        SELECT t.*, a.account_no, a.account_type
        FROM transactions t
        JOIN accounts a ON t.account_id = a.id
        WHERE a.user_id = %s
        ORDER BY t.created_at DESC
        LIMIT 8
        """,
        (uid,)
    )
    return render_template("dashboard.html",
                           accounts=accounts,
                           total_balance=total_balance,
                           recent_txns=recent_txns)


@app.route("/accounts")
@login_required
def accounts():
    uid = session["user_id"]
    accs = query("SELECT * FROM accounts WHERE user_id=%s ORDER BY created_at ASC", (uid,))
    return render_template("accounts.html", accounts=accs)


@app.route("/accounts/new", methods=["POST"])
@login_required
def new_account():
    uid  = session["user_id"]
    atype = request.form.get("account_type", "")
    if atype not in ("checking", "savings"):
        flash("Invalid account type.", "danger")
        return redirect(url_for("accounts"))
    existing = query(
        "SELECT id FROM accounts WHERE user_id=%s AND account_type=%s", (uid, atype), one=True
    )
    if existing:
        flash(f"You already have a {atype} account.", "warning")
        return redirect(url_for("accounts"))
    acc_no = gen_account_no()
    query(
        "INSERT INTO accounts (user_id, account_type, account_no, balance) VALUES (%s,%s,%s,0.00)",
        (uid, atype, acc_no), commit=True
    )
    flash(f"New {atype} account opened: {acc_no}", "success")
    return redirect(url_for("accounts"))


@app.route("/accounts/<int:acc_id>")
@login_required
def account_detail(acc_id):
    uid = session["user_id"]
    acc = query(
        "SELECT * FROM accounts WHERE id=%s AND user_id=%s", (acc_id, uid), one=True
    )
    if not acc:
        flash("Account not found.", "danger")
        return redirect(url_for("accounts"))
    page  = max(1, int(request.args.get("page", 1)))
    limit = 10
    offset = (page - 1) * limit
    total_count = query(
        "SELECT COUNT(*) AS cnt FROM transactions WHERE account_id=%s", (acc_id,), one=True
    )["cnt"]
    txns = query(
        "SELECT * FROM transactions WHERE account_id=%s ORDER BY created_at DESC LIMIT %s OFFSET %s",
        (acc_id, limit, offset)
    )
    total_pages = max(1, -(-total_count // limit))
    return render_template("account_detail.html",
                           acc=acc, txns=txns,
                           page=page, total_pages=total_pages)


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    uid = session["user_id"]
    accounts = query("SELECT * FROM accounts WHERE user_id=%s", (uid,))
    if request.method == "POST":
        acc_id = request.form.get("account_id")
        raw    = request.form.get("amount", "").replace(",", "")
        try:
            amount = Decimal(raw)
            if amount <= 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            flash("Enter a valid positive amount.", "danger")
            return render_template("deposit.html", accounts=accounts)

        acc = query(
            "SELECT * FROM accounts WHERE id=%s AND user_id=%s", (int(acc_id), uid), one=True
        )
        if not acc:
            flash("Account not found.", "danger")
            return render_template("deposit.html", accounts=accounts)

        db = get_db()
        cur = db.cursor(dictionary=True)
        try:
            cur.execute(
                "SELECT balance FROM accounts WHERE id=%s FOR UPDATE", (acc["id"],)
            )
            row = cur.fetchone()
            new_bal = row["balance"] + amount
            cur.execute("UPDATE accounts SET balance=%s WHERE id=%s", (new_bal, acc["id"]))
            cur.execute(
                "INSERT INTO transactions (account_id, type, amount, balance_after, description) "
                "VALUES (%s,'deposit',%s,%s,%s)",
                (acc["id"], amount, new_bal, "Cash deposit")
            )
            db.commit()
        except Exception:
            db.rollback()
            flash("Deposit failed. Please try again.", "danger")
            return render_template("deposit.html", accounts=accounts)
        finally:
            db.close()

        flash(f"INR {amount:,.2f} deposited to {acc['account_no']}.", "success")
        return redirect(url_for("dashboard"))
    return render_template("deposit.html", accounts=accounts)


@app.route("/withdraw", methods=["GET", "POST"])
@login_required
def withdraw():
    uid = session["user_id"]
    accounts = query("SELECT * FROM accounts WHERE user_id=%s", (uid,))
    if request.method == "POST":
        acc_id = request.form.get("account_id")
        raw    = request.form.get("amount", "").replace(",", "")
        try:
            amount = Decimal(raw)
            if amount <= 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            flash("Enter a valid positive amount.", "danger")
            return render_template("withdraw.html", accounts=accounts)

        acc = query(
            "SELECT * FROM accounts WHERE id=%s AND user_id=%s", (int(acc_id), uid), one=True
        )
        if not acc:
            flash("Account not found.", "danger")
            return render_template("withdraw.html", accounts=accounts)

        db = get_db()
        cur = db.cursor(dictionary=True)
        try:
            cur.execute(
                "SELECT balance FROM accounts WHERE id=%s FOR UPDATE", (acc["id"],)
            )
            row = cur.fetchone()
            if row["balance"] < amount:
                db.close()
                flash("Insufficient funds.", "danger")
                return render_template("withdraw.html", accounts=accounts)
            new_bal = row["balance"] - amount
            cur.execute("UPDATE accounts SET balance=%s WHERE id=%s", (new_bal, acc["id"]))
            cur.execute(
                "INSERT INTO transactions (account_id, type, amount, balance_after, description) "
                "VALUES (%s,'withdrawal',%s,%s,%s)",
                (acc["id"], amount, new_bal, "Cash withdrawal")
            )
            db.commit()
        except Exception:
            db.rollback()
            flash("Withdrawal failed. Please try again.", "danger")
            return render_template("withdraw.html", accounts=accounts)
        finally:
            db.close()

        flash(f"INR {amount:,.2f} withdrawn from {acc['account_no']}.", "success")
        return redirect(url_for("dashboard"))
    return render_template("withdraw.html", accounts=accounts)


@app.route("/transfer", methods=["GET", "POST"])
@login_required
def transfer():
    uid = session["user_id"]
    accounts = query("SELECT * FROM accounts WHERE user_id=%s", (uid,))
    if request.method == "POST":
        from_id = request.form.get("from_account")
        to_id   = request.form.get("to_account")
        raw     = request.form.get("amount", "").replace(",", "")
        try:
            amount = Decimal(raw)
            if amount <= 0:
                raise ValueError
        except (InvalidOperation, ValueError):
            flash("Enter a valid positive amount.", "danger")
            return render_template("transfer.html", accounts=accounts)

        if from_id == to_id:
            flash("Cannot transfer to the same account.", "danger")
            return render_template("transfer.html", accounts=accounts)

        from_id_int = int(from_id)
        to_id_int   = int(to_id)

        db = get_db()
        cur = db.cursor(dictionary=True)
        try:
            # Lock in sorted order to prevent deadlock
            ids = sorted([from_id_int, to_id_int])
            cur.execute(
                "SELECT id, balance, account_no FROM accounts WHERE id IN (%s,%s) AND user_id=%s FOR UPDATE",
                (*ids, uid)
            )
            rows = {r["id"]: r for r in cur.fetchall()}

            if len(rows) != 2:
                flash("One or both accounts are invalid.", "danger")
                return render_template("transfer.html", accounts=accounts)

            src = rows[from_id_int]
            dst = rows[to_id_int]

            if src["balance"] < amount:
                flash("Insufficient funds.", "danger")
                return render_template("transfer.html", accounts=accounts)

            new_src = src["balance"] - amount
            new_dst = dst["balance"] + amount

            cur.execute("UPDATE accounts SET balance=%s WHERE id=%s", (new_src, from_id_int))
            cur.execute("UPDATE accounts SET balance=%s WHERE id=%s", (new_dst, to_id_int))
            cur.execute(
                "INSERT INTO transactions (account_id, type, amount, balance_after, description, related_account) "
                "VALUES (%s,'transfer_out',%s,%s,%s,%s)",
                (from_id_int, amount, new_src, f"Transfer to {dst['account_no']}", to_id_int)
            )
            cur.execute(
                "INSERT INTO transactions (account_id, type, amount, balance_after, description, related_account) "
                "VALUES (%s,'transfer_in',%s,%s,%s,%s)",
                (to_id_int, amount, new_dst, f"Transfer from {src['account_no']}", from_id_int)
            )
            db.commit()
        except Exception:
            db.rollback()
            flash("Transfer failed. Please try again.", "danger")
            return render_template("transfer.html", accounts=accounts)
        finally:
            db.close()

        flash(f"INR {amount:,.2f} transferred successfully.", "success")
        return redirect(url_for("dashboard"))
    return render_template("transfer.html", accounts=accounts)


@app.route("/transactions")
@login_required
def transactions():
    uid      = session["user_id"]
    acc_filter  = request.args.get("account", "")
    type_filter = request.args.get("type", "")
    from_date   = request.args.get("from_date", "")
    to_date     = request.args.get("to_date", "")
    page  = max(1, int(request.args.get("page", 1)))
    limit = 15
    offset = (page - 1) * limit

    user_accounts = query("SELECT * FROM accounts WHERE user_id=%s ORDER BY created_at ASC", (uid,))

    where = ["a.user_id = %s"]
    params = [uid]

    if acc_filter:
        where.append("t.account_id = %s")
        params.append(int(acc_filter))
    if type_filter:
        where.append("t.type = %s")
        params.append(type_filter)
    if from_date:
        where.append("DATE(t.created_at) >= %s")
        params.append(from_date)
    if to_date:
        where.append("DATE(t.created_at) <= %s")
        params.append(to_date)

    where_clause = " AND ".join(where)

    count_row = query(
        f"SELECT COUNT(*) AS cnt FROM transactions t JOIN accounts a ON t.account_id=a.id WHERE {where_clause}",
        tuple(params), one=True
    )
    total_count = count_row["cnt"]
    total_pages = max(1, -(-total_count // limit))

    txns = query(
        f"""
        SELECT t.*, a.account_no, a.account_type
        FROM transactions t
        JOIN accounts a ON t.account_id = a.id
        WHERE {where_clause}
        ORDER BY t.created_at DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params) + (limit, offset)
    )

    return render_template("transactions.html",
                           txns=txns,
                           user_accounts=user_accounts,
                           page=page,
                           total_pages=total_pages,
                           acc_filter=acc_filter,
                           type_filter=type_filter,
                           from_date=from_date,
                           to_date=to_date)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    uid  = session["user_id"]
    user = get_current_user()
    if request.method == "POST":
        action = request.form.get("action")
        db = get_db()
        cur = db.cursor()
        try:
            if action == "update_info":
                full_name = request.form.get("full_name", "").strip()
                phone     = request.form.get("phone", "").strip()
                if not full_name:
                    flash("Name cannot be empty.", "danger")
                    return render_template("profile.html", user=user)
                cur.execute(
                    "UPDATE users SET full_name=%s, phone=%s WHERE id=%s",
                    (full_name, phone or None, uid)
                )
                db.commit()
                flash("Profile updated.", "success")

            elif action == "change_password":
                current_pw = request.form.get("current_password", "")
                new_pw     = request.form.get("new_password", "")
                confirm_pw = request.form.get("confirm_password", "")
                cur2 = db.cursor(dictionary=True)
                cur2.execute("SELECT password_hash FROM users WHERE id=%s", (uid,))
                row = cur2.fetchone()
                if not check_password_hash(row["password_hash"], current_pw):
                    flash("Current password is incorrect.", "danger")
                    return render_template("profile.html", user=user)
                if new_pw != confirm_pw:
                    flash("New passwords do not match.", "danger")
                    return render_template("profile.html", user=user)
                if len(new_pw) < 6:
                    flash("Password must be at least 6 characters.", "danger")
                    return render_template("profile.html", user=user)
                cur.execute(
                    "UPDATE users SET password_hash=%s WHERE id=%s",
                    (generate_password_hash(new_pw), uid)
                )
                db.commit()
                flash("Password changed successfully.", "success")
        except Exception:
            db.rollback()
            flash("Update failed. Please try again.", "danger")
        finally:
            db.close()
        return redirect(url_for("profile"))
    return render_template("profile.html", user=user)


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("404.html", error="Internal server error."), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
