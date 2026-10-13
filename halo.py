import datetime as dt
import hashlib
import math
import os
import re
import secrets
import threading
import tkinter as tk
import calendar
from decimal import Decimal, InvalidOperation
from tkinter import messagebox

import customtkinter as ctk
import matplotlib.pyplot as map
import mysql.connector
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "123456"),
    "database": os.getenv("MYSQL_DATABASE", "expense_tracker"),
}


def _asset_path(filename):
    return os.path.join(BASE_DIR, filename)


def _money(amount):
    return f"₹{amount:,.2f}"


def get_connection(include_database=True):
    config = DB_CONFIG.copy()
    if not include_database:
        config.pop("database", None)
    return mysql.connector.connect(**config)


def init_database():
    try:
        connection = get_connection(include_database=False)
        cursor = connection.cursor()
        cursor.execute(f"create database if not exists {DB_CONFIG['database']}")
        cursor.close()
        connection.close()

        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            create table if not exists users (
                id int auto_increment primary key,
                username varchar(50) not null unique,
                salt char(32) not null,
                password_hash char(64) not null,
                created_at timestamp default current_timestamp
            )
            """
        )
        cursor.execute(
            """
            create table if not exists transactions (
                id int auto_increment primary key,
                user_id int not null,
                direction enum('Income', 'Expense') not null,
                category varchar(80) not null,
                amount decimal(12, 2) not null,
                description varchar(255),
                transaction_date date not null,
                payment_mode varchar(40),
                joy_index int,
                created_at timestamp default current_timestamp,
                foreign key (user_id) references users(id)
            )
            """
        )
        cursor.execute("show columns from transactions")
        columns = {row[0] for row in cursor.fetchall()}
        if "payment_mode" not in columns:
            cursor.execute("alter table transactions add column payment_mode varchar(40)")
        if "joy_index" not in columns:
            cursor.execute("alter table transactions add column joy_index int")
        cursor.execute(
            """
            create table if not exists balance (
                id int auto_increment primary key,
                username varchar(255) not null,
                amount decimal(12, 2) not null,
                description text,
                type varchar(50) not null,
                date date not null
            )
            """
        )
        cursor.execute(
            """
            create table if not exists holdings (
                id int auto_increment primary key,
                user_id int not null,
                name varchar(255) not null,
                ticker varchar(50) not null,
                type varchar(50) not null,
                sub varchar(255) not null,
                invested double not null,
                value double not null,
                color varchar(20) not null,
                letter varchar(10) not null,
                created_at datetime not null,
                foreign key (user_id) references users(id)
            )
            """
        )
        cursor.execute(
            """
            create table if not exists portfolio_history (
                id int auto_increment primary key,
                user_id int not null,
                recorded_at datetime not null,
                total_value double not null,
                total_invested double not null,
                foreign key (user_id) references users(id)
            )
            """
        )
        cursor.execute(
            """
            create table if not exists budget (
                id int auto_increment primary key,
                user_id int not null,
                category varchar(100) not null,
                period enum('monthly', 'yearly') not null,
                limit_amt double not null,
                month int default null,
                year int not null,
                created_at datetime not null,
                foreign key (user_id) references users(id)
            )
            """
        )
        _ensure_user_id_column(cursor, "holdings")
        _ensure_user_id_column(cursor, "portfolio_history")
        _ensure_user_id_column(cursor, "budget")
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Exception as e:
        print("DATABASE INIT ERROR:", e)
        return False


def _ensure_user_id_column(cursor, table_name):
    cursor.execute(f"show columns from {table_name}")
    columns = {row[0] for row in cursor.fetchall()}
    if "user_id" in columns:
        return
    cursor.execute(f"alter table {table_name} add column user_id int")
    try:
        cursor.execute(
            f"alter table {table_name} add constraint {table_name}_user_fk foreign key (user_id) references users(id)"
        )
    except Exception:
        pass


def get_user(username):
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "select id, username, salt, password_hash from users where username = %s",
            (username,),
        )
        user = cursor.fetchone()
        cursor.close()
        connection.close()
        return user
    except Exception as e:
        print("GET USER ERROR:", e)
        return None


def create_user(username, salt, password_hash):
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "insert into users (username, salt, password_hash) values (%s, %s, %s)",
            (username, salt, password_hash),
        )
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Exception as e:
        print("CREATE USER ERROR:", e)
        return False


def get_user_totals(username):
    totals = {"income": 0.0, "expense": 0.0, "balance": 0.0}
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            select
                coalesce(sum(case when t.direction = 'Income' then t.amount else 0 end), 0),
                coalesce(sum(case when t.direction = 'Expense' then t.amount else 0 end), 0)
            from transactions t
            join users u on u.id = t.user_id
            where u.username = %s
            """,
            (username,),
        )
        row = cursor.fetchone()
        cursor.close()
        connection.close()
        if row:
            totals["income"] = float(row[0] or 0)
            totals["expense"] = float(row[1] or 0)
            totals["balance"] = totals["income"] - totals["expense"]
        return totals
    except Exception as e:
        print("GET TOTALS ERROR:", e)
        return totals


CATEGORIES = [
    "Food",
    "Travel",
    "Shopping",
    "Education",
    "Healthcare",
    "Housing",
    "Subscriptions",
    "Essentials",
    "Loans",
    "Entertainment",
    "Income",
    "Miscellaneous",
]


def add_transaction(
    username,
    direction,
    category,
    amount,
    description,
    transaction_date,
    payment_mode=None,
    joy_index=None,
):
    user = get_user(username)
    if not user:
        return False, "User not found."
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            insert into transactions
                (user_id, direction, category, amount, description, transaction_date, payment_mode, joy_index)
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user["id"],
                direction,
                category,
                float(amount),
                description,
                transaction_date,
                payment_mode,
                joy_index,
            ),
        )
        connection.commit()
        cursor.close()
        connection.close()
        return True, None
    except Exception as e:
        return False, str(e)


def list_transactions(username):
    query = """
            select t.id, t.direction, t.category, t.amount, t.description, t.transaction_date,
                   t.payment_mode, t.joy_index
            from transactions t
            join users u on u.id = t.user_id
            where u.username = %s
            order by t.transaction_date desc, t.id desc
            """
    fallback = """
            select t.id, t.direction, t.category, t.amount, t.description, t.transaction_date
            from transactions t
            join users u on u.id = t.user_id
            where u.username = %s
            order by t.transaction_date desc, t.id desc
            """
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(query, (username,))
        except Exception:
            cursor.execute(fallback, (username,))
        rows = cursor.fetchall()
        cursor.close()
        connection.close()
        return rows
    except Exception as e:
        print("LIST TRANSACTIONS ERROR:", e)
        return []


def update_transaction(
    username,
    record_id,
    direction,
    category,
    amount,
    description,
    transaction_date,
    payment_mode=None,
    joy_index=None,
):
    user = get_user(username)
    if not user:
        return False, "User not found."
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            update transactions
            set direction = %s,
                category = %s,
                amount = %s,
                description = %s,
                transaction_date = %s,
                payment_mode = %s,
                joy_index = %s
            where id = %s and user_id = %s
            """,
            (
                direction,
                category,
                float(amount),
                description,
                transaction_date,
                payment_mode,
                joy_index,
                record_id,
                user["id"],
            ),
        )
        connection.commit()
        cursor.close()
        connection.close()
        return True, None
    except Exception as e:
        return False, str(e)


def delete_transaction(username, record_id):
    user = get_user(username)
    if not user:
        return False, "User not found."
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "delete from transactions where id = %s and user_id = %s",
            (record_id, user["id"]),
        )
        connection.commit()
        cursor.close()
        connection.close()
        return True, None
    except Exception as e:
        return False, str(e)



ANALYTICS_CATEGORIES = [
    "Travel",
    "Shopping",
    "Miscellaneous",
    "Subscriptions",
    "Essentials",
    "Healthcare",
    "Education",
    "Food",
    "Loans",
    "Housing",
]


def _as_date(value):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str) and value:
        return dt.datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    return None


def _expense_rows(rows):
    expenses = []
    for row in rows:
        direction = (row.get("direction") or "").strip()
        if direction.lower() != "expense":
            continue
        expenses.append(
            {
                "amount": float(row.get("amount") or 0),
                "date": _as_date(row.get("transaction_date")),
                "category": row.get("category") or "Miscellaneous",
            }
        )
    return expenses


def _seven_day_window(expenses):
    today = dt.date.today()
    dates = [item["date"] for item in expenses if item["date"]]
    end = today
    if dates:
        latest = max(dates)
        if latest > today or (today - latest).days > 6:
            end = latest
    return [end - dt.timedelta(days=offset) for offset in range(6, -1, -1)]


def build_analytics(parent, username):
    map.close("all")
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(0, weight=1)

    rows = list_transactions(username)
    expenses = _expense_rows(rows)
    last_days = _seven_day_window(expenses)
    spend_by_day = {day: 0.0 for day in last_days}
    category_totals = {name: 0.0 for name in ANALYTICS_CATEGORIES}
    total_spent = 0.0

    for item in expenses:
        total_spent += item["amount"]
        if item["date"] in spend_by_day:
            spend_by_day[item["date"]] += item["amount"]
        category = item["category"]
        if category not in category_totals:
            category_totals[category] = 0.0
        category_totals[category] += item["amount"]

    days = [day.strftime("%d %b") for day in last_days]
    spend = [spend_by_day[day] for day in last_days]
    pie_labels = []
    pie_values = []
    for name, value in category_totals.items():
        if value > 0:
            pie_labels.append(name)
            pie_values.append(value)
    if not pie_values:
        pie_labels = ["No data"]
        pie_values = [1]

    def refresh():
        for child in parent.winfo_children():
            child.destroy()
        build_analytics(parent, username)

    an = ctk.CTkFrame(parent)
    an.grid(row=0, column=0, sticky="nsew")
    an.grid_columnconfigure(0, weight=1)
    an.grid_rowconfigure(1, weight=1)

    Ana = ctk.CTkLabel(an, text="Analytics", text_color="white", font=("Arial", 50))
    Ana.grid(row=0, column=0, sticky="nw", pady=(70, 30), padx=50)

    scroll = ctk.CTkScrollableFrame(an)
    scroll.grid(row=1, column=0, sticky="nsew")
    cards = ctk.CTkFrame(scroll, width=1200, height=120)
    cards.pack()

    a_text = "Total Spent: ₹" + str(float(total_spent))
    a = ctk.CTkLabel(cards, height=100, width=250, text=a_text, text_color="white", font=("Calibri", 25), fg_color="#0B0D4D", corner_radius=6)
    a.pack(padx=20, pady=20, side="left")

    if any(spend):
        high = max(spend_by_day, key=spend_by_day.get)
        low = min(spend_by_day, key=spend_by_day.get)
        b_text = "Highest Spent On: " + high.strftime("%d %b")
        c_text = "Lowest Spent On: " + low.strftime("%d %b")
    else:
        b_text = "Highest Spent On: —"
        c_text = "Lowest Spent On: —"
    b = ctk.CTkLabel(cards, height=100, width=250, text=b_text, text_color="white", font=("Calibri", 25), fg_color="#510000", corner_radius=6)
    b.pack(padx=20, pady=20, side="left")
    c = ctk.CTkLabel(cards, height=100, width=250, text=c_text, text_color="white", font=("Calibri", 25), fg_color="#002E05", corner_radius=6)
    c.pack(padx=20, pady=20, side="left")

    avg = sum(spend) / len(spend) if spend else 0
    d_text = "Average Daily: ₹" + str(round(avg, 2))
    d = ctk.CTkLabel(cards, height=100, width=250, text=d_text, text_color="white", font=("Calibri", 25), fg_color="#660033", corner_radius=6)
    d.pack(padx=20, pady=20, side="left")

    g1 = ctk.CTkFrame(scroll, width=1200, height=400)
    g1.pack(fill="both", padx=10, pady=10)
    g1.pack_propagate(False)

    fig1, ax1 = map.subplots()
    ax1.plot(days, spend, color="#00C5DB", linestyle="-", marker="o")
    ax1.set_title("Last 7 Days Expense", color="white", font="Calibri", fontsize=20)
    ax1.set_xlabel("Date", color="#D7D7D7", fontsize=15)
    ax1.set_ylabel("Expense", color="#D7D7D7", fontsize=15)
    ax1.tick_params(axis="x", colors="white", labelsize=10)
    ax1.tick_params(axis="y", colors="white", labelsize=10)
    ax1.grid(True, linestyle="--", alpha=0.1, color="white")
    ax1.patch.set_edgecolor("none")
    ax1.patch.set_linewidth(0)
    for sp in ax1.spines.values():
        sp.set_visible(False)
    fig1.set_facecolor("#2B2B2B")
    ax1.set_facecolor("#2B2B2B")
    canvas1 = FigureCanvasTkAgg(fig1, master=g1)
    canvas1.draw()
    canvas1.get_tk_widget().pack(fill="both", expand=True)

    row2 = ctk.CTkFrame(scroll, width=1200, height=400)
    row2.pack(fill="both")
    g2 = ctk.CTkFrame(row2, width=600, height=400)
    g2.pack(fill="both", padx=10, pady=10, side="left")
    g2.pack_propagate(False)

    def pctchange(pct):
        return "%1.0f%%" % pct if pct > 0 else ""

    qw = max(pie_values)
    explode = [0] * len(pie_values)
    explode[pie_values.index(qw)] = 0.1
    fig2, ax2 = map.subplots()
    ax2.pie(
        pie_values,
        labels=pie_labels,
        textprops={"color": "#009AFF", "fontsize": 10},
        wedgeprops=dict(edgecolor="#2B2B2B"),
        explode=explode,
        autopct=pctchange,
        colors=["#A3F6DA", "#FFB0B0", "#FDFFB0", "#BDDAFF", "#95FF91", "#D6B6FF", "#FFE0B6", "#FFC7E9", "#E1E1E1", "#FFCC99"],
    )
    ax2.set_title("Category-wise Expense", color="white", font="Calibri", fontsize=20)
    fig2.set_facecolor("#2B2B2B")
    canvas2 = FigureCanvasTkAgg(fig2, master=g2)
    canvas2.draw()
    canvas2.get_tk_widget().pack(fill="both", expand=True, side="left")

    g3 = ctk.CTkFrame(row2, width=600, height=400)
    g3.pack(fill="both", padx=10, pady=10, side="left")
    g3.pack_propagate(False)

    fig3, ax3 = map.subplots()
    ax3.bar(days, spend, color="#00C5DB", width=0.3, align="center", edgecolor="black")
    fig3.set_facecolor("#2B2B2B")
    ax3.set_facecolor("#2B2B2B")
    ax3.set_title("Weekly Expenditure", color="white", font="Calibri", fontsize=20)
    ax3.set_xlabel("Date", color="white", fontsize=15)
    ax3.set_ylabel("Expense", color="white", fontsize=15)
    ax3.tick_params(axis="x", colors="white", labelsize=10)
    ax3.tick_params(axis="y", colors="white", labelsize=10)
    for s in ax3.spines.values():
        s.set_linewidth(1)
    ax3.spines["bottom"].set_color("white")
    ax3.spines["left"].set_color("white")
    ax3.spines["top"].set_color("#2B2B2B")
    ax3.spines["right"].set_color("#2B2B2B")
    canvas3 = FigureCanvasTkAgg(fig3, master=g3)
    canvas3.draw()
    canvas3.get_tk_widget().pack(fill="both", expand=True, side="left")

    selectedrow = {"index": None}

    def select_row(index):
        selectedrow["index"] = index
        for i, row_frame in enumerate(table_rows):
            row_frame.configure(fg_color="#00A998" if i == index else ("#2B2B2B" if i % 2 == 0 else "#242424"))

    def selected_record():
        index = selectedrow["index"]
        if index is None or index < 0 or index >= len(rows):
            messagebox.showinfo("select a row", "Click a transaction in the table first.")
            return None
        return rows[index]

    def deleterow():
        record = selected_record()
        if not record:
            return
        if not messagebox.askyesno("Delete", "Delete this transaction?"):
            return
        ok, err = delete_transaction(username, record["id"])
        if not ok:
            messagebox.showerror("Could not delete", err or "Could not delete this transaction.")
            return
        refresh()

    def editrow():
        record = selected_record()
        if not record:
            return
        when = _as_date(record.get("transaction_date")) or dt.date.today()
        pop_win = ctk.CTkToplevel(parent)
        pop_win.title("Edit transaction")
        pop_win.geometry("420x520")
        pop_win.grab_set()

        ctk.CTkLabel(pop_win, text="Edit transaction", font=("Arial", 22)).pack(pady=(20, 10))
        type_box = ctk.CTkComboBox(pop_win, values=["Income", "Expense"], width=300)
        type_box.set(record.get("direction") or "Expense")
        type_box.pack(pady=8)
        amount_box = ctk.CTkEntry(pop_win, width=300, placeholder_text="Amount")
        amount_box.insert(0, str(record.get("amount") or ""))
        amount_box.pack(pady=8)
        desc_box = ctk.CTkEntry(pop_win, width=300, placeholder_text="Description")
        desc_box.insert(0, record.get("description") or "")
        desc_box.pack(pady=8)
        cat_box = ctk.CTkComboBox(pop_win, values=ANALYTICS_CATEGORIES, width=300)
        cat_box.set(record.get("category") or "Miscellaneous")
        cat_box.pack(pady=8)
        mode_box = ctk.CTkComboBox(
            pop_win,
            values=["UPI", "Cash", "Debit Card", "Credit Card", "Net Banking", "Cheque", "EMI"],
            width=300,
        )
        mode_box.set(record.get("payment_mode") or "UPI")
        mode_box.pack(pady=8)
        date_row = ctk.CTkFrame(pop_win, fg_color="transparent")
        date_row.pack(pady=8)
        day_box = ctk.CTkComboBox(date_row, values=[str(i) for i in range(1, 32)], width=80)
        month_box = ctk.CTkComboBox(date_row, values=[str(i) for i in range(1, 13)], width=80)
        year_box = ctk.CTkComboBox(date_row, values=[str(i) for i in range(2025, 2031)], width=110)
        day_box.set(str(when.day))
        month_box.set(str(when.month))
        year_box.set(str(when.year))
        day_box.pack(side="left", padx=4)
        month_box.pack(side="left", padx=4)
        year_box.pack(side="left", padx=4)

        def save_edit():
            try:
                amount = float(amount_box.get())
                transaction_date = "{}-{:02d}-{:02d}".format(int(year_box.get()), int(month_box.get()), int(day_box.get()))
            except (TypeError, ValueError):
                messagebox.showerror("Invalid input", "Please enter a valid amount and date.")
                return
            ok, err = update_transaction(
                username,
                record["id"],
                type_box.get(),
                cat_box.get(),
                amount,
                desc_box.get(),
                transaction_date,
                payment_mode=mode_box.get(),
                joy_index=record.get("joy_index"),
            )
            if not ok:
                messagebox.showerror("Could not save", err or "Could not update this transaction.")
                return
            pop_win.destroy()
            refresh()

        ctk.CTkButton(pop_win, text="Save", fg_color="#00A998", command=save_edit).pack(pady=16)

    his = ctk.CTkLabel(scroll, text="Transaction history:", font=("Arial", 25))
    his.pack(pady=10)

    table_holder = ctk.CTkFrame(scroll, fg_color="#1a1a1a")
    table_holder.pack(pady=20, fill="x", padx=10)
    headers = ["Sl. No.", "Date", "Description", "Amount", "Category", "Type", "Mode"]
    header_row = ctk.CTkFrame(table_holder, fg_color="#00A998")
    header_row.pack(fill="x")
    for col, title in enumerate(headers):
        ctk.CTkLabel(header_row, text=title, font=("Arial", 16, "bold"), text_color="white", width=150, anchor="w").grid(
            row=0, column=col, padx=8, pady=8, sticky="ew"
        )
        header_row.grid_columnconfigure(col, weight=1)

    table_rows = []
    for index, row in enumerate(rows):
        when = _as_date(row.get("transaction_date"))
        date_text = when.strftime("%d/%m/%Y") if when else ""
        values = [
            str(index + 1),
            date_text,
            row.get("description") or "",
            _money(row.get("amount") or 0),
            row.get("category") or "",
            row.get("direction") or "",
            row.get("payment_mode") or "",
        ]
        color = "#2B2B2B" if index % 2 == 0 else "#242424"
        row_frame = ctk.CTkFrame(table_holder, fg_color=color)
        row_frame.pack(fill="x")
        row_frame.bind("<Button-1>", lambda _e, i=index: select_row(i))
        for col, value in enumerate(values):
            cell = ctk.CTkLabel(row_frame, text=value, font=("Arial", 16), text_color="white", width=150, anchor="w")
            cell.grid(row=0, column=col, padx=8, pady=8, sticky="ew")
            cell.bind("<Button-1>", lambda _e, i=index: select_row(i))
            row_frame.grid_columnconfigure(col, weight=1)
        table_rows.append(row_frame)

    btnframe = ctk.CTkFrame(scroll, fg_color="transparent")
    btnframe.pack(pady=10, side="left")
    editbtn = ctk.CTkButton(btnframe, text="Edit", command=editrow)
    editbtn.pack(side="left", padx=10)
    deletebtn = ctk.CTkButton(btnframe, text="Delete", command=deleterow)
    deletebtn.pack(side="left", padx=10)
    return an

bg = "#0d1117"
crd = "#161b22"
brd = "#2a3441"
acc = "#00d4aa"
txt = "#e6edf3"
mut = "#6e7f8f"
grn = "#3fb950"
red = "#ff6b6b"
ibg = "#0d1117"

COLORS = {
    "bg": bg,
    "panel": crd,
    "card": crd,
    "input": crd,
    "border": brd,
    "text": txt,
    "muted": mut,
    "blue": acc,
    "blue_hover": "#00a88a",
    "red": red,
    "red_hover": "#e05252",
    "green": grn,
    "yellow": "#facc15",
}

lst = []
his = []
investment_username = None

app = None
vlb = None
ilb = None
ylb = None
clb = None
cvs = None
hfr = None
bcv = None
rlb = None
plb = None
nlb = None


def _as_datetime(value):
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time.min)
    if isinstance(value, str) and value:
        text = value[:19]
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return dt.datetime.strptime(text, fmt)
            except ValueError:
                continue
    return dt.datetime.now()


def _investment_user():
    user = get_user(investment_username) if investment_username else None
    if not user:
        messagebox.showerror("User not found", "Could not match this portfolio to a logged-in user.")
        return None
    return user


def load_investments_from_db():
    global lst, his
    lst = []
    his = []
    user = get_user(investment_username) if investment_username else None
    if not user:
        return
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            select id, user_id, name, ticker, type, sub, invested, value, color, letter, created_at
            from holdings
            where user_id = %s
            order by id
            """,
            (user["id"],),
        )
        for row in cursor.fetchall():
            lst.append(
                {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "name": row["name"],
                    "ticker": row["ticker"],
                    "type": row["type"],
                    "sub": row["sub"],
                    "invested": float(row["invested"] or 0),
                    "value": float(row["value"] or 0),
                    "color": row["color"],
                    "letter": row["letter"],
                    "added_at": _as_datetime(row["created_at"]),
                }
            )
        cursor.execute(
            """
            select recorded_at, total_value, total_invested
            from portfolio_history
            where user_id = %s
            order by recorded_at, id
            """,
            (user["id"],),
        )
        his = [
            (
                _as_datetime(row["recorded_at"]),
                float(row["total_value"] or 0),
                float(row["total_invested"] or 0),
            )
            for row in cursor.fetchall()
        ]
        cursor.close()
        connection.close()
        if lst and not his:
            snapshot = (dt.datetime.now(), sum(h["value"] for h in lst), sum(h["invested"] for h in lst))
            his.append(snapshot)
            save_portfolio_snapshot(user["id"], snapshot[0], snapshot[1], snapshot[2])
    except Exception as e:
        print("LOAD INVESTMENTS ERROR:", e)
        lst = []
        his = []


def save_portfolio_snapshot(user_id, recorded_at, total_value, total_invested):
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            insert into portfolio_history (user_id, recorded_at, total_value, total_invested)
            values (%s, %s, %s, %s)
            """,
            (user_id, recorded_at, total_value, total_invested),
        )
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Exception as e:
        print("SAVE PORTFOLIO HISTORY ERROR:", e)
        return False


def save_holding_to_db(holding):
    user = _investment_user()
    if not user:
        return False
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            insert into holdings
                (user_id, name, ticker, type, sub, invested, value, color, letter, created_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user["id"],
                holding["name"],
                holding["ticker"],
                holding["type"],
                holding["sub"],
                holding["invested"],
                holding["value"],
                holding["color"],
                holding["letter"],
                holding["added_at"],
            ),
        )
        holding["id"] = cursor.lastrowid
        holding["user_id"] = user["id"]
        total_value = sum(item["value"] for item in lst)
        total_invested = sum(item["invested"] for item in lst)
        cursor.execute(
            """
            insert into portfolio_history (user_id, recorded_at, total_value, total_invested)
            values (%s, %s, %s, %s)
            """,
            (user["id"], holding["added_at"], total_value, total_invested),
        )
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Exception as e:
        messagebox.showerror("Database Error", f"Could not save investment:\n{e}")
        return False


def update_holding_in_db(holding):
    user = _investment_user()
    if not user:
        return False
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            update holdings
            set name = %s,
                ticker = %s,
                type = %s,
                sub = %s,
                invested = %s,
                value = %s,
                color = %s,
                letter = %s,
                created_at = %s
            where id = %s and user_id = %s
            """,
            (
                holding["name"],
                holding["ticker"],
                holding["type"],
                holding["sub"],
                holding["invested"],
                holding["value"],
                holding["color"],
                holding["letter"],
                holding["added_at"],
                holding["id"],
                user["id"],
            ),
        )
        total_value = sum(item["value"] for item in lst)
        total_invested = sum(item["invested"] for item in lst)
        cursor.execute(
            """
            insert into portfolio_history (user_id, recorded_at, total_value, total_invested)
            values (%s, %s, %s, %s)
            """,
            (user["id"], holding["added_at"], total_value, total_invested),
        )
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Exception as e:
        messagebox.showerror("Database Error", f"Could not update investment:\n{e}")
        return False


def inr(n):
    n = int(round(n))
    s = str(abs(n))
    if len(s) <= 3:
        res = s
    else:
        l3, rst, grp = s[-3:], s[:-3], []
        while len(rst) > 2:
            grp.append(rst[-2:]);
            rst = rst[:-2]
        if rst: grp.append(rst)
        grp.reverse()
        res = ",".join(grp) + "," + l3
    return ("-Rs. " if n < 0 else "Rs. ") + res


def pcl(v): return grn if v >= 0 else red


def ref():
    tv, ti = sum(h["value"] for h in lst), sum(h["invested"] for h in lst)
    vlb.configure(text=inr(tv));
    ilb.configure(text=inr(ti))
    gl = tv - ti
    pct = (gl / ti * 100) if ti else 0.0
    s = "+" if pct >= 0 else ""
    ylb.configure(text=f"{s}{round(pct, 1)}% Return", text_color=pcl(pct))
    rlb.configure(text=inr(gl), text_color=pcl(gl))
    plb.configure(text=f"{s}{round(pct, 2)}%", text_color=pcl(pct))
    clb.configure(text=f"{s}{round(pct, 2)}% total", text_color=pcl(pct))
    if lst:
        top = max(lst, key=lambda x: x["value"])
        top_pct = top["value"] / tv * 100 if tv else 0
        if top_pct >= 40:
            nlb.configure(text=f"{top['name']} makes up {round(top_pct, 1)}% of your portfolio.",
                          text_color=red)
        else:
            names = [top["name"]]
            if len(lst) > 1:
                names.append(lst[1]["name"])
            nlb.configure(text=f"Your portfolio is led by {' and '.join(names)}.",
                          text_color=mut)
    else:
        nlb.configure(text="Add holdings to view portfolio distribution and risk breakdown.",
                      text_color=mut)
    update_bar(tv, ti);
    render_chart();
    grd()


def update_bar(tv, ti):
    bcv.delete("all");
    w = bcv.winfo_width()
    if w > 1:
        bw = min(w, max(2, int(w * min(1.0, ti / tv if tv else 0))))
        bcv.create_rectangle(0, 1, bw, 6, fill=acc, outline="")


def render_chart():
    cvs.delete("all")
    w, h = cvs.winfo_width(), cvs.winfo_height()
    if w < 10 or h < 10:
        cvs.after(100, render_chart)
        return
    (draw_donut_chart if current_chart_mode == "allocation"
     else draw_timeline_chart)(w, h)


def draw_donut_chart(w, h):
    if not lst:
        cvs.create_text(w // 2, h // 2,
                        text="Add holdings to view allocation",
                        fill=mut, font=("Segoe UI", 15), anchor="center")
        return
    tv = sum(i["value"] for i in lst)
    if tv <= 0:
        cvs.create_text(w // 2, h // 2,
                        text="Total portfolio value is Rs. 0",
                        fill=mut, font=("Segoe UI", 15), anchor="center")
        return
    cx, cy, R = int(w * 0.32), int(h * 0.5), min(int(w * 0.32) - 30,
                                                 int(h * 0.5) - 25, 105)
    r_in = int(R * 0.52)
    start = 90.0
    for h_item in sorted(lst, key=lambda x: x["value"], reverse=True):
        f = h_item["value"] / tv
        ext = -f * 360
        cvs.create_arc(cx - R, cy - R, cx + R, cy + R,
                       start=start, extent=ext,
                       fill=h_item["color"], outline=crd, width=2)
        if f >= 0.05:
            md = start + ext / 2
            rad = math.radians(md)
            lr = (R + r_in) / 2
            lx = cx + lr * math.cos(rad)
            ly = cy - lr * math.sin(rad)
            cvs.create_text(lx, ly,
                            text=f"{round(f * 100, 1)}%",
                            fill="#1B1B1F", font=("Segoe UI", 11, "bold"))
        start += ext
    cvs.create_oval(cx - r_in, cy - r_in, cx + r_in, cy + r_in,
                    fill=crd, outline="")
    cvs.create_text(cx, cy - 10, text="Holdings",
                    fill=mut, font=("Segoe UI", 12, "bold"))
    cvs.create_text(cx, cy + 12, text=str(len(lst)),
                    fill=txt, font=("Segoe UI", 18, "bold"))
    leg_x = int(w * 0.58)
    start_y = max(18, int(h * 0.5 - (min(len(lst), 7) * 30) / 2))
    for i, h_item in enumerate(sorted(lst, key=lambda x: x["value"], reverse=True)[:7]):
        y = start_y + i * 30
        f = h_item["value"] / tv
        cvs.create_rectangle(leg_x, y, leg_x + 16, y + 16,
                             fill=h_item["color"])
        cvs.create_text(leg_x + 26, y + 8,
                        text=h_item["ticker"], anchor="w",
                        fill=txt, font=("Segoe UI", 14, "bold"))
        cvs.create_text(leg_x + 175, y + 8,
                        text=f"{round(f * 100, 1)}%", anchor="w",
                        fill=acc, font=("Segoe UI", 14, "bold"))
    if len(lst) > 7:
        rem = sum(x["value"] for x in lst[7:]) / tv
        y = start_y + 7 * 30
        cvs.create_rectangle(leg_x, y, leg_x + 16, y + 16,
                             fill="#6e7f8f")
        cvs.create_text(leg_x + 26, y + 8,
                        text=f"Others ({len(lst) - 7})", anchor="w",
                        fill=mut, font=("Segoe UI", 13))
        cvs.create_text(leg_x + 175, y + 8,
                        text=f"{round(rem * 100, 1)}%", anchor="w",
                        fill=mut, font=("Segoe UI", 13))


def draw_timeline_chart(w, h):
    pl, pr, pt, pb = 75, 20, 20, 50
    cw, ch = w - pl - pr, h - pt - pb
    if not his:
        y = pt + ch // 2
        seg = 8
        x = pl
        while x < w - pr:
            cvs.create_line(x, y, min(x + seg, w - pr), y, fill=brd, width=1)
            x += seg * 2
        cvs.create_text(w // 2, y - 14,
                        text="Add an investment to see your chart",
                        fill=mut, font=("Segoe UI", 13), anchor="s")
        return
    yv = [e[1] - e[2] for e in his]
    pnl = yv[-1]
    line_col, fill_col = (acc, "#382E1E") if pnl >= 0 else (red, "#3A1E1E")
    if len(his) == 1:
        mx = pl + cw // 2
        my = pt + ch // 2
        cvs.create_line(pl, my, w - pr, my, fill=brd, width=1)
        cvs.create_oval(mx - 6, my - 6, mx + 6, my + 6,
                        fill=line_col, outline=crd)
        s = "+" if pnl >= 0 else ""
        cvs.create_text(mx, my - 14,
                        text=f"P&L: {s}{inr(pnl)}", fill=line_col,
                        font=("Segoe UI", 13, "bold"), anchor="s")
        cvs.create_text(mx, my + 14,
                        text=his[0][0].strftime("%d %b %Y %H:%M"),
                        fill=mut, font=("Segoe UI", 11), anchor="n")
        return
    mn, mx = min(min(yv), 0), max(max(yv), 0)
    pad = (mx - mn) * 0.18 if mx != mn else 500
    mnd, mxd = mn - pad, mx + pad
    rng = mxd - mnd if mxd != mnd else 1.0
    for i in range(5):
        gy = pt + (ch / 4) * i
        rv = mxd - (rng / 4) * i
        cvs.create_line(pl, gy, w - pr, gy, fill="#2F2F36", width=1)
        s = "+" if rv > 0 else ""
        cvs.create_text(pl - 8, gy,
                        text=f"{s}Rs. {int(round(rv))}",
                        anchor="e",
                        fill=grn if rv > 1 else (red if rv < -1 else mut),
                        font=("Segoe UI", 11))
    cds = [(pl + i / (len(yv) - 1) * cw,
            pt + ch - ((v - mnd) / rng) * ch) for i, v in enumerate(yv)]
    zero_y = pt + ch - ((-mnd) / rng * ch)
    cvs.create_line(pl, zero_y, w - pr, zero_y,
                    fill=mut, width=1, dash=(3, 3))
    cvs.create_text(w - pr, zero_y - 10,
                    text="Break-even", fill=mut,
                    font=("Segoe UI", 10), anchor="e")
    fpt = cds + [(cds[-1][0], pt + ch), (cds[0][0], pt + ch)]
    cvs.create_polygon([c for p in fpt for c in p],
                       fill=fill_col, outline="")
    fcd = [c for p in cds for c in p]
    cvs.create_line(fcd, fill=line_col, width=2,
                    smooth=len(cds) >= 3)
    for i, (cx, cy) in enumerate(cds):
        r = 6 if i == len(cds) - 1 else 4
        cvs.create_oval(cx - r, cy - r, cx + r, cy + r,
                        fill=line_col, outline=crd)
    for i, t in enumerate([e[0] for e in his]):
        cx = cds[i][0]
        cvs.create_text(cx, pt + ch + 8,
                        text=t.strftime("%d %b\n%H:%M"),
                        fill=line_col if i == len(his) - 1 else mut,
                        font=("Segoe UI", 10,
                              "bold" if i == len(his) - 1 else "normal"),
                        anchor="n", justify="center")


def toggle_chart_mode(v):
    global current_chart_mode
    current_chart_mode = "allocation" if "Pie" in v else "timeline"
    render_chart()


def grd():
    for w in hfr.winfo_children():
        w.destroy()
    if not lst:
        ctk.CTkLabel(hfr,
                     text="No holdings yet  |  click + New Investment",
                     font=("Segoe UI", 14), text_color=mut) \
            .grid(row=0, column=0, columnspan=3, pady=30)
        return
    col = row = 0
    for h in lst:
        gl = h["value"] - h["invested"]
        pct = (gl / h["invested"] * 100) if h["invested"] else 0
        cd = ctk.CTkFrame(hfr, fg_color=crd,
                          corner_radius=12, border_width=1,
                          border_color=brd)
        cd.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
        cd.columnconfigure(1, weight=1)
        ifr = ctk.CTkFrame(cd, fg_color=h["color"],
                           width=54, height=54, corner_radius=10)
        ifr.grid(row=0, column=0, rowspan=2, padx=(14, 10), pady=12)
        ifr.grid_propagate(False)
        ctk.CTkLabel(ifr, text=h["letter"],
                     font=("Segoe UI", 22, "bold"),
                     text_color="#1B1B1F") \
            .place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(cd, text=h["name"],
                     font=("Segoe UI", 17, "bold"),
                     text_color=txt).grid(row=0, column=1,
                                          sticky="sw", pady=(12, 0))
        ctk.CTkLabel(cd, text=h["sub"],
                     font=("Segoe UI", 13),
                     text_color=mut).grid(row=1, column=1,
                                          sticky="nw", pady=(0, 12))
        ctk.CTkLabel(cd, text=inr(h["value"]),
                     font=("Segoe UI", 17, "bold"),
                     text_color=txt).grid(row=0, column=2,
                                          sticky="se", padx=(8, 14),
                                          pady=(12, 0))
        s = "+" if pct >= 0 else ""
        ctk.CTkLabel(cd,
                     text=f"{s}{round(pct, 1)}%",
                     font=("Segoe UI", 15, "bold"),
                     text_color=pcl(pct)) \
            .grid(row=1, column=2, sticky="ne",
                  padx=(8, 14), pady=(0, 12))
        col = (col + 1) % 3
        row += col == 0
    for c in range(3):
        hfr.columnconfigure(c, weight=1)


def add():
    win = ctk.CTkToplevel(app)
    win.title("Add Investment")
    win.geometry("480x460")
    win.resizable(False, False)
    win.configure(fg_color=bg)
    win.grab_set()
    win.lift()
    ctk.CTkLabel(win, text="Add Investment",
                 font=("Segoe UI", 20, "bold"),
                 text_color=txt).pack(anchor="w", padx=22,
                                      pady=(18, 12))

    r1 = ctk.CTkFrame(win, fg_color="transparent")
    r1.pack(fill="x", padx=22, pady=6)
    r1.columnconfigure((0, 1), weight=1)
    ctk.CTkLabel(r1, text="Asset Name",
                 font=("Segoe UI", 13, "bold"),
                 text_color=mut).grid(row=0, column=0, sticky="w")
    enm = ctk.CTkEntry(r1, placeholder_text="e.g. Reliance",
                       font=("Segoe UI", 14),
                       fg_color=ibg, border_color=brd,
                       text_color=txt, placeholder_text_color=mut)
    enm.grid(row=1, column=0, sticky="ew", padx=(0, 6))
    ctk.CTkLabel(r1, text="Ticker",
                 font=("Segoe UI", 13, "bold"),
                 text_color=mut).grid(row=0, column=1, sticky="w")
    etk = ctk.CTkEntry(r1, placeholder_text="RELIANCE",
                       font=("Segoe UI", 14),
                       fg_color=ibg, border_color=brd,
                       text_color=txt, placeholder_text_color=mut)
    etk.grid(row=1, column=1, sticky="ew", padx=(6, 0))

    r2 = ctk.CTkFrame(win, fg_color="transparent")
    r2.pack(fill="x", padx=22, pady=6)
    r2.columnconfigure((0, 1), weight=1)
    ctk.CTkLabel(r2, text="Type",
                 font=("Segoe UI", 13, "bold"),
                 text_color=mut).grid(row=0, column=0, sticky="w")
    combo_type = ctk.CTkComboBox(r2,
                                 values=["Equity", "Crypto", "Mutual Fund",
                                         "ETF", "Bond"],
                                 font=("Segoe UI", 14),
                                 fg_color=ibg, border_color=brd,
                                 text_color=txt, button_color=brd,
                                 dropdown_fg_color=crd)
    combo_type.set("Equity")
    combo_type.grid(row=1, column=0, sticky="ew", padx=(0, 6))
    ctk.CTkLabel(r2, text="Subtitle",
                 font=("Segoe UI", 13, "bold"),
                 text_color=mut).grid(row=0, column=1, sticky="w")
    esb = ctk.CTkEntry(r2,
                       placeholder_text="45 shares | Equity",
                       font=("Segoe UI", 14),
                       fg_color=ibg, border_color=brd,
                       text_color=txt, placeholder_text_color=mut)
    esb.grid(row=1, column=1, sticky="ew", padx=(6, 0))

    r3 = ctk.CTkFrame(win, fg_color="transparent")
    r3.pack(fill="x", padx=22, pady=6)
    r3.columnconfigure((0, 1), weight=1)
    ctk.CTkLabel(r3, text="Invested (Rs.)",
                 font=("Segoe UI", 13, "bold"),
                 text_color=mut).grid(row=0, column=0, sticky="w")
    ein = ctk.CTkEntry(r3, placeholder_text="100000",
                       font=("Segoe UI", 14),
                       fg_color=ibg, border_color=brd,
                       text_color=txt, placeholder_text_color=mut)
    ein.grid(row=1, column=0, sticky="ew", padx=(0, 6))
    ctk.CTkLabel(r3, text="Current Value (Rs.)",
                 font=("Segoe UI", 13, "bold"),
                 text_color=mut).grid(row=0, column=1, sticky="w")
    eva = ctk.CTkEntry(r3, placeholder_text="128450",
                       font=("Segoe UI", 14),
                       fg_color=ibg, border_color=brd,
                       text_color=txt, placeholder_text_color=mut)
    eva.grid(row=1, column=1, sticky="ew", padx=(6, 0))

    r4 = ctk.CTkFrame(win, fg_color="transparent")
    r4.pack(fill="x", padx=22, pady=6)
    ctk.CTkLabel(r4, text="Icon Color",
                 font=("Segoe UI", 13, "bold"),
                 text_color=mut).pack(anchor="w")
    cop = ["Gold", "Blue", "Emerald", "Coral", "Purple", "Teal", "Amber"]
    cva = ["#C9A96E", "#4E80EE", "#38A169", "#E56B6F",
           "#9D72FF", "#319795", "#D69E2E"]
    ccl = ctk.CTkComboBox(r4, values=cop,
                          font=("Segoe UI", 14),
                          fg_color=ibg, border_color=brd,
                          text_color=txt, button_color=brd,
                          dropdown_fg_color=crd)
    ccl.set("Gold")
    ccl.pack(fill="x")

    def do():
        nm, tkr = enm.get().strip(), etk.get().strip().upper()
        typ, sub = combo_type.get(), esb.get().strip()
        inv = float(ein.get().replace(",", "")) if ein.get().replace(",", "") else 0
        val = float(eva.get().replace(",", "")) if eva.get().replace(",", "") else 0
        if not nm:
            messagebox.showerror("Missing Field",
                                 "Enter asset name.", parent=win)
            return
        if inv < 0 or val < 0:
            messagebox.showerror("Invalid Input",
                                 "Positive numbers required.", parent=win)
            return
        if not tkr:
            tkr = nm[0].upper()
        if not sub:
            sub = typ
        pcl = cva[cop.index(ccl.get())] if ccl.get() in cop else acc

        existing = next((h for h in lst
                         if h["ticker"] == tkr and h["type"] == typ), None)
        if existing:
            existing["invested"] += inv
            existing["value"] += val
            existing["color"] = pcl
            existing["letter"] = tkr[0]
            existing["added_at"] = dt.datetime.now()
            update_holding_in_db(existing)
            nh = existing
        else:
            nh = {"name": nm, "ticker": tkr, "type": typ,
                  "sub": sub, "invested": inv, "value": val,
                  "color": pcl, "letter": tkr[0],
                  "added_at": dt.datetime.now()}
            lst.append(nh)
            save_holding_to_db(nh)

        his.append((nh["added_at"],
                    sum(i["value"] for i in lst),
                    sum(i["invested"] for i in lst)))
        win.destroy()
        ref()

    ctk.CTkButton(win, text="Add to Portfolio",
                  fg_color=acc, text_color=bg,
                  font=("Segoe UI", 15, "bold"),
                  hover_color="#B89758",
                  command=do) \
        .pack(fill="x", padx=22, pady=(14, 20))


def pop():
    win = ctk.CTkToplevel(app)
    win.title("Portfolio Breakdown")
    win.geometry("780x640")
    win.configure(fg_color=bg)
    win.grab_set()
    win.lift()
    top = ctk.CTkFrame(win, fg_color="transparent")
    top.pack(fill="x", padx=24, pady=(20, 14))
    ctk.CTkLabel(top, text="Portfolio Breakdown",
                 font=("Segoe UI", 26, "bold"),
                 text_color=txt).pack(side="left")
    ctk.CTkButton(top, text="Close",
                  fg_color=crd, border_width=1, border_color=brd,
                  text_color=txt, font=("Segoe UI", 13, "bold"),
                  hover_color=brd, width=80, height=32,
                  corner_radius=16,
                  command=win.destroy).pack(side="right")
    if not lst:
        ctk.CTkLabel(win,
                     text="No holdings yet. Click + New Investment to add your first asset.",
                     font=("Segoe UI", 16), text_color=mut) \
            .pack(expand=True, pady=60)
        return
    tv, ti = sum(h["value"] for h in lst), sum(h["invested"] for h in lst)
    gl = tv - ti
    pct = (gl / ti * 100) if ti else 0
    s = "+" if pct >= 0 else ""
    sc = ctk.CTkFrame(win, fg_color=crd,
                      corner_radius=12, border_width=1,
                      border_color=brd)
    sc.pack(fill="x", padx=24, pady=(0, 16))
    sc.columnconfigure((0, 1, 2), weight=1)
    for txtc, valc in (("TOTAL INVESTED", ti),
                       ("CURRENT VALUE", tv),
                       ("NET UNREALIZED P&L", f"{s}{inr(gl)} ({s}{round(pct, 1)}%)")):
        frm = ctk.CTkFrame(sc, fg_color="transparent")
        frm.grid(row=0,
                 column=("TOTAL INVESTED",
                         "CURRENT VALUE",
                         "NET UNREALIZED P&L".split()[0]).index(txtc),
                 padx=18, pady=16, sticky="w")
        ctk.CTkLabel(frm, text=txtc,
                     font=("Segoe UI", 12, "bold"),
                     text_color=mut).pack(anchor="w")
        ctk.CTkLabel(frm,
                     text=inr(valc) if isinstance(valc, int) else valc,
                     font=("Segoe UI", 22, "bold"),
                     text_color=txt if isinstance(valc, int) else pcl(gl)) \
            .pack(anchor="w", pady=(4, 0))
    ctk.CTkLabel(win, text="Holdings Allocation",
                 font=("Segoe UI", 18, "bold"),
                 text_color=txt).pack(anchor="w", padx=24, pady=(0, 10))
    sfr = ctk.CTkScrollableFrame(win, fg_color=bg,
                                 scrollbar_button_color=brd)
    sfr.pack(fill="both", expand=True, padx=24, pady=(0, 20))
    for h in sorted(lst, key=lambda x: x["value"], reverse=True):
        hgl = h["value"] - h["invested"]
        hpct = (hgl / h["invested"] * 100) if h["invested"] else 0
        alloc = (h["value"] / tv * 100) if tv else 0
        sg = "+" if hpct >= 0 else ""
        row = ctk.CTkFrame(sfr, fg_color=crd,
                           corner_radius=12, border_width=1,
                           border_color=brd)
        row.pack(fill="x", pady=6)
        row.columnconfigure(1, weight=1)
        dot = ctk.CTkFrame(row, fg_color=h["color"],
                           width=46, height=46, corner_radius=10)
        dot.grid(row=0, column=0, rowspan=2,
                 padx=(14, 12), pady=12)
        dot.grid_propagate(False)
        ctk.CTkLabel(dot, text=h["letter"],
                     font=("Segoe UI", 18, "bold"),
                     text_color="#1B1B1F") \
            .place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(row,
                     text=f"{h['name']} ({h['ticker']})",
                     font=("Segoe UI", 16, "bold"),
                     text_color=txt).grid(row=0, column=1,
                                          sticky="w", pady=(12, 0))
        ctk.CTkLabel(row,
                     text=f"{h['sub']}  |  {round(alloc, 1)}% of total portfolio",
                     font=("Segoe UI", 13), text_color=mut) \
            .grid(row=1, column=1, sticky="w", pady=(0, 12))
        ctk.CTkLabel(row, text=inr(h["value"]),
                     font=("Segoe UI", 17, "bold"),
                     text_color=txt) \
            .grid(row=0, column=2, sticky="e",
                  padx=(10, 16), pady=(12, 0))
        ctk.CTkLabel(row,
                     text=f"{sg}{round(hpct, 1)}%  ({sg}{inr(hgl)})",
                     font=("Segoe UI", 14, "bold"),
                     text_color=pcl(hgl)) \
            .grid(row=1, column=2, sticky="e",
                  padx=(10, 16), pady=(0, 12))
        if h.get("id"):
            ctk.CTkButton(row, text="Remove",
                          fg_color="transparent", border_width=1,
                          border_color=brd, hover_color="#3A1E1E",
                          text_color=red, width=70, height=28,
                          font=("Segoe UI", 12, "bold"),
                          corner_radius=14,
                          command=lambda hid=h["id"]:
                          (delete_holding_from_db(hid),
                           win.destroy(),
                           pop())) \
                .grid(row=0, column=3, rowspan=2,
                      padx=(0, 16), pady=12)


def delete_holding_from_db(holding_id):
    global lst, his
    user = _investment_user()
    if not user:
        return False
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "delete from holdings where id = %s and user_id = %s",
            (holding_id, user["id"]),
        )
        connection.commit()
        cursor.close()
        connection.close()
        lst = [holding for holding in lst if holding.get("id") != holding_id]
        his.append((dt.datetime.now(),
                    sum(holding["value"] for holding in lst),
                    sum(holding["invested"] for holding in lst)))
        ref()
        return True
    except Exception as e:
        messagebox.showerror("DB Error", f"Delete failed:\n{e}")
        return False


def build_investments(parent, username):
    global app, ctl, vlb, ilb, ylb, clb, cvs, hfr, bcv, rlb, plb, nlb
    global investment_username, current_chart_mode
    investment_username = username
    current_chart_mode = "allocation"
    app = parent
    app.configure(fg_color=bg)
    load_investments_from_db()
    bar = ctk.CTkFrame(app, fg_color=bg, height=65)
    bar.pack(fill="x", padx=20, pady=(16, 0))
    bar.pack_propagate(False)
    logo_img = (ctk.CTkImage(Image.open("logo.png"), size=(135, 48))
                if os.path.exists("logo.png") else None)
    if logo_img:
        ctk.CTkLabel(bar, image=logo_img, text="").pack(side="left",
                                                        padx=(0, 16), pady=8)
    ctk.CTkLabel(bar, text="Investments",
                 font=("Segoe UI", 32, "bold"),
                 text_color=txt).pack(side="left", pady=8)
    ctk.CTkButton(bar, text="+ New Investment",
                  fg_color=crd, border_width=1, border_color=brd,
                  text_color=txt, corner_radius=20,
                  font=("Segoe UI", 15, "bold"),
                  hover_color=brd, command=add) \
        .pack(side="right", pady=8)

    frm = ctk.CTkFrame(app, fg_color=bg)
    frm.pack(fill="both", expand=True, padx=20, pady=14)
    frm.columnconfigure(0, weight=3)
    frm.columnconfigure(1, weight=1)
    frm.rowconfigure(0, weight=1)

    lft = ctk.CTkFrame(frm, fg_color=bg)
    lft.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    rgt = ctk.CTkFrame(frm, fg_color=bg)
    rgt.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

    ccd = ctk.CTkFrame(lft, fg_color=crd,
                       corner_radius=14, border_width=1,
                       border_color=brd)
    ccd.pack(fill="x", pady=(0, 14))
    header = ctk.CTkFrame(ccd, fg_color="transparent")
    header.pack(fill="x", padx=22, pady=(18, 0))
    ctl = ctk.CTkFrame(header, fg_color="transparent")
    ctl.pack(side="left")
    ctk.CTkLabel(ctl, text="TOTAL PORTFOLIO VALUE",
                 font=("Segoe UI", 13, "bold"),
                 text_color=mut).pack(anchor="w")
    vlb = ctk.CTkLabel(ctl, text="Rs. 0",
                       font=("Segoe UI", 44, "bold"),
                       text_color=txt)
    vlb.pack(anchor="w")
    top_right = ctk.CTkFrame(header, fg_color="transparent")
    top_right.pack(side="right", anchor="n")
    ylb = ctk.CTkLabel(top_right,
                       text="+0.0% Return",
                       font=("Segoe UI", 16, "bold"),
                       text_color=acc)
    ylb.pack(anchor="e", pady=(0, 6))
    chart_tab = ctk.CTkSegmentedButton(top_right,
                                       values=["Allocation Pie",
                                               "Performance (P&L)"],
                                       command=toggle_chart_mode,
                                       font=("Segoe UI", 12, "bold"),
                                       fg_color=ibg, selected_color=acc,
                                       selected_hover_color="#B89758",
                                       unselected_color=crd,
                                       text_color=txt)
    chart_tab.set("Allocation Pie")
    chart_tab.pack(anchor="e")
    lrw = ctk.CTkFrame(ccd, fg_color="transparent")
    lrw.pack(fill="x", padx=22, pady=(4, 0))
    ldc = tk.Canvas(lrw, width=12, height=12,
                    bg=crd, highlightthickness=0)
    ldc.create_oval(1, 1, 11, 11, fill=acc, outline="")
    ldc.pack(side="left", pady=3)
    ctk.CTkLabel(lrw, text="  PORTFOLIO  |  ",
                 font=("Segoe UI", 14), text_color=txt).pack(side="left")
    clb = ctk.CTkLabel(lrw, text="+0% total",
                       font=("Segoe UI", 14, "bold"),
                       text_color=acc)
    clb.pack(side="left")
    cvs = tk.Canvas(ccd, height=260, bg=crd,
                    highlightthickness=0)
    cvs.pack(fill="x", padx=22, pady=(8, 16))
    cvs.bind("<Configure>", lambda e: render_chart())

    ctk.CTkLabel(lft, text="Holdings",
                 font=("Segoe UI", 24, "bold"),
                 text_color=txt).pack(anchor="w", pady=(0, 10))
    hsc = ctk.CTkScrollableFrame(lft, fg_color=bg,
                                 scrollbar_button_color=brd)
    hsc.pack(fill="both", expand=True)
    hfr = ctk.CTkFrame(hsc, fg_color=bg)
    hfr.pack(fill="both", expand=True)

    # ── Right side (summary cards) ───────────────────
    icd = ctk.CTkFrame(rgt, fg_color=crd,
                       corner_radius=14, border_width=1,
                       border_color=brd)
    icd.pack(fill="x", pady=(0, 12))
    ctk.CTkLabel(icd, text="INVESTED CAPITAL",
                 font=("Segoe UI", 13, "bold"),
                 text_color=mut).pack(anchor="w", padx=20,
                                      pady=(16, 4))
    ilb = ctk.CTkLabel(icd, text="Rs. 0",
                       font=("Segoe UI", 34, "bold"),
                       text_color=txt)
    ilb.pack(anchor="w", padx=20)
    bcv = tk.Canvas(icd, height=6, bg=crd,
                    highlightthickness=0)
    bcv.pack(fill="x", padx=20, pady=(10, 18))
    bcv.bind("<Configure>", lambda e: update_bar(
        sum(h["value"] for h in lst),
        sum(h["invested"] for h in lst)))

    tcd = ctk.CTkFrame(rgt, fg_color=crd,
                       corner_radius=14, border_width=1,
                       border_color=brd)
    tcd.pack(fill="x", pady=(0, 12))
    ctk.CTkLabel(tcd, text="TOTAL UNREALIZED P&L",
                 font=("Segoe UI", 13, "bold"),
                 text_color=mut).pack(anchor="w", padx=20,
                                      pady=(16, 4))
    rlb = ctk.CTkLabel(tcd, text="Rs. 0",
                       font=("Segoe UI", 32, "bold"),
                       text_color=acc)
    rlb.pack(anchor="w", padx=20)
    plb = ctk.CTkLabel(tcd, text="+0%",
                       font=("Segoe UI", 16, "bold"),
                       text_color=grn)
    plb.pack(anchor="w", padx=20, pady=(0, 18))

    ncd = ctk.CTkFrame(rgt, fg_color=crd,
                       corner_radius=14, border_width=1,
                       border_color=brd)
    ncd.pack(fill="both", expand=True)
    ctk.CTkLabel(ncd, text="PORTFOLIO INSIGHTS",
                 font=("Segoe UI", 13, "bold"),
                 text_color=acc).pack(anchor="w", padx=20,
                                      pady=(16, 8))
    nlb = ctk.CTkLabel(ncd,
                       text="Add holdings to view portfolio distribution and risk breakdown.",
                       font=("Segoe UI", 14), text_color=mut,
                       wraplength=280, justify="left")
    nlb.pack(anchor="w", padx=20, pady=(0, 14))
    ctk.CTkButton(ncd, text="View Full Breakdown ->",
                  fg_color=crd, border_width=1,
                  border_color=brd, text_color=txt,
                  font=("Segoe UI", 14, "bold"),
                  hover_color="#2E2E35", anchor="w",
                  command=pop) \
        .pack(fill="x", padx=20, pady=(0, 18))

    ref()

def create_balance_table():
    query = """
        create table if not exists balance (
            id int auto_increment primary key,
            username varchar(255) not null,
            amount decimal(12, 2) not null,
            description text,
            type varchar(50) not null,
            date date not null
        )
    """

    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(query)
        connection.commit()
    except mysql.connector.Error as err:
        messagebox.showerror("Database Error", f"Could not create balance table:\n{err}")
    finally:
        if "connection" in locals():
            connection.close()


def insert_balance_record(username, amount, description, record_type, record_date):
    query = """
        insert into balance (username, amount, description, type, date)
        values (%s, %s, %s, %s, %s)
    """

    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            query,
            (
                username,
                amount,
                description,
                record_type,
                record_date,
            ),
        )
        connection.commit()
        return True, None
    except mysql.connector.Error as err:
        return False, str(err)
    finally:
        if "connection" in locals():
            connection.close()


def fetch_balance_records(username):
    query = """
        select id, amount, description, type, date
        from balance
        where username = %s
        order by date desc, id desc
    """

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (username,))
        return cursor.fetchall()
    except mysql.connector.Error as err:
        messagebox.showerror("Database Error", f"Could not fetch records:\n{err}")
        return []
    finally:
        if "connection" in locals():
            connection.close()


def delete_balance_record(record_id, username):
    query = """
        delete from balance
        where id = %s and username = %s
    """

    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(query, (record_id, username))
        connection.commit()
        return True, None
    except mysql.connector.Error as err:
        return False, str(err)
    finally:
        if "connection" in locals():
            connection.close()


def fetch_balance_totals(username):
    query = """
        select
            coalesce(sum(case when type = 'You owe' then amount else 0 end), 0) as total_you_owe,
            coalesce(sum(case when type = 'You are owed' then amount else 0 end), 0) as total_you_are_owed
        from balance
        where username = %s
    """

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (username,))
        row = cursor.fetchone()

        total_you_owe = Decimal(str(row["total_you_owe"] or 0))
        total_you_are_owed = Decimal(str(row["total_you_are_owed"] or 0))
        net_balance = total_you_are_owed - total_you_owe

        return total_you_owe, total_you_are_owed, net_balance
    except mysql.connector.Error as err:
        messagebox.showerror("Database Error", f"Could not calculate totals:\n{err}")
        return Decimal("0.00"), Decimal("0.00"), Decimal("0.00")
    finally:
        if "connection" in locals():
            connection.close()


class BalanceManagementFrame(ctk.CTkFrame):
    def __init__(self, master, username):
        super().__init__(master)
        self.username = username

        create_balance_table()
        self.build_ui()
        self.load_records()

    def build_ui(self):
        self.configure(fg_color=COLORS["bg"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        self.summary_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.summary_frame.grid(
            row=0,
            column=0,
            columnspan=2,
            padx=24,
            pady=(24, 10),
            sticky="ew",
        )

        for column in range(3):
            self.summary_frame.grid_columnconfigure(column, weight=1, uniform="summary")

        _, self.total_owe_value = self.create_summary_card(
            self.summary_frame, 0, "Total You Owe", COLORS["red"]
        )
        _, self.total_owed_value = self.create_summary_card(
            self.summary_frame, 1, "Total You Are Owed", COLORS["green"]
        )
        _, self.net_balance_value = self.create_summary_card(
            self.summary_frame, 2, "Net Balance", COLORS["yellow"]
        )

        self.form_frame = ctk.CTkFrame(
            self,
            fg_color=COLORS["panel"],
            corner_radius=18,
            border_width=1,
            border_color=COLORS["border"],
        )
        self.form_frame.grid(row=1, column=0, padx=(24, 12), pady=(10, 24), sticky="nsew")
        self.form_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.form_frame,
            text="Balance Manager",
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=28, weight="bold"),
        ).grid(row=0, column=0, padx=24, pady=(28, 8), sticky="w")

        ctk.CTkLabel(
            self.form_frame,
            text="Track what you owe and what others owe you.",
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=14),
        ).grid(row=1, column=0, padx=24, pady=(0, 24), sticky="w")

        self.amount_entry = self.create_entry("Amount")
        self.amount_entry.grid(row=2, column=0, padx=24, pady=(0, 16), sticky="ew")

        self.description_entry = self.create_entry("Description")
        self.description_entry.grid(row=3, column=0, padx=24, pady=(0, 16), sticky="ew")

        self.type_dropdown = ctk.CTkOptionMenu(
            self.form_frame,
            values=["You owe", "You are owed"],
            fg_color=COLORS["input"],
            button_color=COLORS["blue"],
            button_hover_color=COLORS["blue_hover"],
            dropdown_fg_color=COLORS["card"],
            dropdown_hover_color=COLORS["blue"],
            dropdown_text_color=COLORS["text"],
            text_color=COLORS["text"],
            corner_radius=12,
            height=46,
            font=ctk.CTkFont(size=15),
        )
        self.type_dropdown.grid(row=4, column=0, padx=24, pady=(0, 16), sticky="ew")
        self.type_dropdown.set("You owe")

        self.date_entry = self.create_entry("Date  YYYY-MM-DD")
        self.date_entry.insert(0, dt.date.today().strftime("%Y-%m-%d"))
        self.date_entry.grid(row=5, column=0, padx=24, pady=(0, 24), sticky="ew")

        self.add_button = ctk.CTkButton(
            self.form_frame,
            text="Add Record",
            command=self.add_record,
            fg_color=COLORS["blue"],
            hover_color=COLORS["blue_hover"],
            text_color=COLORS["text"],
            corner_radius=14,
            height=48,
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.add_button.grid(row=6, column=0, padx=24, pady=(0, 28), sticky="ew")

        self.records_container = ctk.CTkFrame(
            self,
            fg_color=COLORS["panel"],
            corner_radius=18,
            border_width=1,
            border_color=COLORS["border"],
        )
        self.records_container.grid(row=1, column=1, padx=(12, 24), pady=(10, 24), sticky="nsew")
        self.records_container.grid_columnconfigure(0, weight=1)
        self.records_container.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self.records_container,
            text="Records",
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, padx=24, pady=(24, 12), sticky="w")

        self.records_frame = ctk.CTkScrollableFrame(
            self.records_container,
            fg_color="transparent",
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["blue"],
        )
        self.records_frame.grid(row=1, column=0, padx=18, pady=(0, 18), sticky="nsew")
        self.records_frame.grid_columnconfigure(0, weight=1)

    def create_entry(self, placeholder):
        return ctk.CTkEntry(
            self.form_frame,
            placeholder_text=placeholder,
            fg_color=COLORS["input"],
            border_color=COLORS["border"],
            text_color=COLORS["text"],
            placeholder_text_color=COLORS["muted"],
            corner_radius=12,
            height=48,
            font=ctk.CTkFont(size=15),
        )

    def create_summary_card(self, parent, column, title, color):
        card = ctk.CTkFrame(
            parent,
            fg_color=COLORS["card"],
            corner_radius=16,
            border_width=1,
            border_color=COLORS["border"],
        )
        card.grid(row=0, column=column, padx=8, sticky="ew")

        ctk.CTkLabel(
            card,
            text=title,
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", padx=18, pady=(16, 4))

        value_label = ctk.CTkLabel(
            card,
            text="0.00",
            text_color=color,
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        value_label.pack(anchor="w", padx=18, pady=(0, 16))

        return card, value_label

    def validate_inputs(self):
        amount_text = self.amount_entry.get().strip()
        description = self.description_entry.get().strip()
        record_type = self.type_dropdown.get()
        date_text = self.date_entry.get().strip()

        if not amount_text:
            messagebox.showwarning("Validation Error", "Amount is required.")
            return None

        try:
            amount = Decimal(amount_text)
            if amount <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            messagebox.showwarning("Validation Error", "Amount must be a positive number.")
            return None

        if not description:
            messagebox.showwarning("Validation Error", "Description is required.")
            return None

        try:
            record_date = dt.datetime.strptime(date_text, "%Y-%m-%d").date()
        except ValueError:
            messagebox.showwarning("Validation Error", "Date must be in YYYY-MM-DD format.")
            return None

        return amount, description, record_type, record_date

    def add_record(self):
        cleaned_values = self.validate_inputs()

        if cleaned_values is None:
            return

        amount, description, record_type, record_date = cleaned_values

        self.add_button.configure(state="disabled", text="Adding...")
        self.update_idletasks()

        def save_record():
            success, error = insert_balance_record(
                self.username,
                amount,
                description,
                record_type,
                record_date,
            )
            self.after(0, lambda: self.after_record_saved(success, error))

        threading.Thread(target=save_record, daemon=True).start()

    def after_record_saved(self, success, error=None):
        self.add_button.configure(state="normal", text="Add Record")

        if success:
            self.clear_inputs()
            self.load_records()
            messagebox.showinfo("Success", "Balance record added successfully.")
        elif error:
            messagebox.showerror("Database Error", f"Could not add record:\n{error}")

    def clear_inputs(self):
        self.amount_entry.delete(0, "end")
        self.description_entry.delete(0, "end")
        self.type_dropdown.set("You owe")
        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, dt.date.today().strftime("%Y-%m-%d"))

    def load_records(self):
        for widget in self.records_frame.winfo_children():
            widget.destroy()

        records = fetch_balance_records(self.username)

        if not records:
            ctk.CTkLabel(
                self.records_frame,
                text="No balance records found.",
                text_color=COLORS["muted"],
                font=ctk.CTkFont(size=15),
            ).grid(row=0, column=0, padx=10, pady=30)
        else:
            for index, record in enumerate(records):
                self.add_record_row(index, record)

        self.update_totals()

    def add_record_row(self, row_number, record):
        record_id = record["id"]
        amount = f"{Decimal(str(record['amount'])):.2f}"
        description = record["description"]
        record_type = record["type"]
        raw_date = record["date"]
        if hasattr(raw_date, "strftime"):
            record_date = raw_date.strftime("%Y-%m-%d")
        else:
            record_date = str(raw_date) if raw_date is not None else ""
        type_color = COLORS["red"] if record_type == "You owe" else COLORS["green"]

        card = ctk.CTkFrame(
            self.records_frame,
            fg_color=COLORS["card"],
            corner_radius=14,
            border_width=1,
            border_color=COLORS["border"],
        )
        card.grid(row=row_number, column=0, padx=4, pady=8, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(
            card,
            text=amount,
            text_color=type_color,
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, padx=18, pady=(14, 2), sticky="w")

        ctk.CTkLabel(
            card,
            text=record_type,
            text_color=type_color,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=1, padx=18, pady=(14, 2), sticky="e")

        ctk.CTkLabel(
            card,
            text=description,
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=15),
            anchor="w",
            justify="left",
            wraplength=420,
        ).grid(row=1, column=0, columnspan=2, padx=18, pady=(2, 6), sticky="ew")

        ctk.CTkLabel(
            card,
            text=record_date,
            text_color=COLORS["muted"],
            font=ctk.CTkFont(size=13),
        ).grid(row=2, column=0, padx=18, pady=(0, 14), sticky="w")

        ctk.CTkButton(
            card,
            text="Delete",
            command=lambda rid=record_id: self.confirm_delete_record(rid),
            fg_color=COLORS["red"],
            hover_color=COLORS["red_hover"],
            text_color=COLORS["text"],
            corner_radius=10,
            width=86,
            height=32,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=2, column=1, padx=18, pady=(0, 14), sticky="e")

    def confirm_delete_record(self, record_id):
        confirm = messagebox.askyesno(
            "Delete Record",
            "Are you sure you want to delete this balance record?",
        )

        if not confirm:
            return

        def delete_record():
            success, error = delete_balance_record(record_id, self.username)
            self.after(0, lambda: self.after_record_deleted(success, error))

        threading.Thread(target=delete_record, daemon=True).start()

    def after_record_deleted(self, success, error=None):
        if success:
            self.load_records()
            messagebox.showinfo("Deleted", "Balance record deleted successfully.")
        elif error:
            messagebox.showerror("Database Error", f"Could not delete record:\n{error}")

    def update_totals(self):
        total_you_owe, total_you_are_owed, net_balance = fetch_balance_totals(self.username)

        self.total_owe_value.configure(text=f"{total_you_owe:.2f}")
        self.total_owed_value.configure(text=f"{total_you_are_owed:.2f}")
        self.net_balance_value.configure(text=f"{net_balance:.2f}")



def _load_budget_data(username):
    """Return this user's saved budgets and expense transactions."""
    user = get_user(username)
    if not user:
        return [], []

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            select id, category, period, limit_amt, month, year, created_at
            from budget
            where user_id = %s
            order by year, month, category
            """,
            (user["id"],),
        )
        budgets = [
            {key: float(value) if key == "limit_amt" else value for key, value in row.items()}
            for row in cursor.fetchall()
        ]
        cursor.execute(
            """
            select amount, category, transaction_date as date
            from transactions
            where user_id = %s and direction = 'Expense'
            order by transaction_date
            """,
            (user["id"],),
        )
        expenses = [
            {"amount": float(row["amount"]), "category": row["category"], "date": row["date"]}
            for row in cursor.fetchall()
            if row["date"] is not None
        ]
        return budgets, expenses
    except Exception as e:
        print("BUDGET LOAD ERROR:", e)
        return [], []
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def _add_budget(username, category, period, limit_amt, month, year):
    user = get_user(username)
    if not user:
        return False, "User not found."
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            insert into budget
                (user_id, category, period, limit_amt, month, year, created_at)
            values (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user["id"],
                category,
                period,
                limit_amt,
                month if period == "monthly" else None,
                year,
                dt.datetime.now(),
            ),
        )
        connection.commit()
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def _delete_budget(username, budget_id):
    user = get_user(username)
    if not user:
        return False, "User not found."
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            "delete from budget where id = %s and user_id = %s",
            (budget_id, user["id"]),
        )
        connection.commit()
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def _budget_currency(value):
    number = int(round(value))
    digits = str(abs(number))
    if len(digits) <= 3:
        result = digits
    else:
        last_three, remaining, groups = digits[-3:], digits[:-3], []
        while len(remaining) > 2:
            groups.append(remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.append(remaining)
        groups.reverse()
        result = ",".join(groups) + "," + last_three
    return ("-Rs. " if number < 0 else "Rs. ") + result


def build_budget(parent, username, period):
    """Build the monthly or yearly budget view inside the main application."""
    bg, card, border, accent, text = "#1B1B1F", "#242429", "#38383F", "#C9A96E", "#F0EDE6"
    muted, green, red, input_bg = "#9C9993", "#4EBA6F", "#E06A6A", "#161619"
    colors = ["#4E80EE", "#38A169", "#E56B6F", "#9D72FF", "#319795", "#D69E2E", "#C9A96E", "#F687B3"]
    state = {
        "budgets": [],
        "expenses": [],
        "month": dt.datetime.now().month,
        "year": dt.datetime.now().year,
        "warned": set(),
    }

    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(0, weight=1)
    budget_frame = ctk.CTkFrame(parent, fg_color=bg)
    budget_frame.grid(row=0, column=0, sticky="nsew")

    top = ctk.CTkFrame(budget_frame, fg_color=bg, height=68)
    top.pack(fill="x", padx=20, pady=(14, 0))
    top.pack_propagate(False)
    title = "Monthly Budget" if period == "monthly" else "Yearly Budget"
    ctk.CTkLabel(top, text=title, font=("Segoe UI", 28, "bold"), text_color=text).pack(side="left")
    year_total = ctk.CTkLabel(top, text="Year: Rs. 0", font=("Segoe UI", 14, "bold"), text_color=accent)
    period_total = ctk.CTkLabel(
        top,
        text=("Month: Rs. 0" if period == "monthly" else "Selected year: Rs. 0"),
        font=("Segoe UI", 14, "bold"),
        text_color=green,
    )
    year_total.pack(side="right", padx=(0, 24))
    period_total.pack(side="right", padx=(0, 30))

    nav = ctk.CTkFrame(budget_frame, fg_color=card, corner_radius=10)
    nav.pack(fill="x", padx=20, pady=8)
    button_style = dict(
        width=95,
        height=34,
        fg_color="transparent",
        border_width=1,
        border_color=border,
        text_color=text,
        hover_color=border,
        font=("Segoe UI", 13),
    )
    nav_label = ctk.CTkLabel(nav, text="", font=("Segoe UI", 17, "bold"), text_color=accent)

    body = ctk.CTkFrame(budget_frame, fg_color=bg)
    body.pack(fill="both", expand=True, padx=20, pady=(0, 16))
    body.columnconfigure((0, 1), weight=1)
    body.rowconfigure((0, 1), weight=1)

    def spend_by_category(month=None, year=None):
        totals = {}
        for expense in state["expenses"]:
            expense_date = expense["date"]
            if year and expense_date.year != year:
                continue
            if month and expense_date.month != month:
                continue
            category = expense["category"]
            totals[category] = totals.get(category, 0) + expense["amount"]
        return totals

    def monthly_totals():
        totals = [0.0] * 12
        for expense in state["expenses"]:
            if expense["date"].year == state["year"]:
                totals[expense["date"].month - 1] += expense["amount"]
        return totals

    def draw_pie(canvas, data):
        canvas.delete("all")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 10 or height < 10:
            canvas.after(100, lambda: draw_pie(canvas, data))
            return
        total = sum(data.values()) or 1
        center_x, center_y = int(width * 0.38), height // 2
        radius = min(center_x - 20, center_y - 20, 110)
        inner_radius = int(radius * 0.52)
        start = 90.0
        for index, (_, value) in enumerate(sorted(data.items(), key=lambda item: -item[1])):
            extent = -(value / total) * 360
            canvas.create_arc(
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
                start=start,
                extent=extent,
                fill=colors[index % len(colors)],
                outline=card,
                width=2,
            )
            start += extent
        canvas.create_oval(
            center_x - inner_radius,
            center_y - inner_radius,
            center_x + inner_radius,
            center_y + inner_radius,
            fill=card,
            outline="",
        )
        canvas.create_text(center_x, center_y, text=_budget_currency(sum(data.values())), fill=text, font=("Segoe UI", 11, "bold"))
        legend_x = center_x + radius + 20
        legend_y = max(10, center_y - len(data) * 13)
        for index, (label, value) in enumerate(sorted(data.items(), key=lambda item: -item[1])[:8]):
            y = legend_y + index * 26
            canvas.create_rectangle(legend_x, y, legend_x + 12, y + 12, fill=colors[index % len(colors)], outline="")
            canvas.create_text(legend_x + 18, y + 6, text=label, anchor="w", fill=text, font=("Segoe UI", 11))
            canvas.create_text(legend_x + 160, y + 6, text=f"{value / total * 100:.1f}%", anchor="w", fill=accent, font=("Segoe UI", 11, "bold"))

    def draw_bar(canvas, labels, values):
        canvas.delete("all")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 10 or height < 10:
            canvas.after(100, lambda: draw_bar(canvas, labels, values))
            return
        padding_left, padding_right, padding_top, padding_bottom = 65, 10, 20, 38
        chart_width = width - padding_left - padding_right
        chart_height = height - padding_top - padding_bottom
        maximum = max(values) if any(value > 0 for value in values) else 1
        gap = chart_width // len(labels)
        bar_width = int(gap * 0.6)
        for index in range(5):
            grid_y = padding_top + chart_height * index // 4
            canvas.create_line(padding_left, grid_y, width - padding_right, grid_y, fill="#2F2F36", width=1)
            canvas.create_text(padding_left - 6, grid_y, text=_budget_currency(maximum * (1 - index / 4)), anchor="e", fill=muted, font=("Segoe UI", 9))
        for index, (label, value) in enumerate(zip(labels, values)):
            bar_x = padding_left + index * gap + (gap - bar_width) // 2
            bar_height = int(chart_height * value / maximum) if maximum else 0
            bar_y = padding_top + chart_height - bar_height
            canvas.create_rectangle(bar_x, bar_y, bar_x + bar_width, padding_top + chart_height, fill=accent if value > 0 else border, outline="")
            canvas.create_text(bar_x + bar_width // 2, padding_top + chart_height + 5, text=label, fill=muted, font=("Segoe UI", 9), anchor="n")
            if value > 0:
                canvas.create_text(bar_x + bar_width // 2, bar_y - 3, text=_budget_currency(value), fill=text, font=("Segoe UI", 8), anchor="s")

    def make_card(row, column, title_text):
        frame = ctk.CTkFrame(body, fg_color=card, corner_radius=12, border_width=1, border_color=border)
        frame.grid(
            row=row,
            column=column,
            sticky="nsew",
            padx=(0, 8) if column == 0 else (8, 0),
            pady=(0, 8) if row == 0 else (8, 0),
        )
        ctk.CTkLabel(frame, text=title_text, font=("Segoe UI", 14, "bold"), text_color=text).pack(anchor="w", padx=16, pady=(14, 4))
        return frame

    pie_frame = make_card(0, 0, "Category Breakdown")
    pie_canvas = tk.Canvas(pie_frame, bg=card, highlightthickness=0, height=230)
    pie_canvas.pack(fill="both", expand=True, padx=14, pady=(0, 14))
    bar_frame = make_card(0, 1, "Monthly Spend – This Year")
    bar_canvas = tk.Canvas(bar_frame, bg=card, highlightthickness=0, height=230)
    bar_canvas.pack(fill="both", expand=True, padx=14, pady=(0, 14))
    table_frame = make_card(1, 1, "Budget vs Spend")
    scroll = ctk.CTkScrollableFrame(table_frame, fg_color="transparent", scrollbar_button_color=border)
    scroll.pack(fill="both", expand=True, padx=8, pady=(0, 10))
    table = ctk.CTkFrame(scroll, fg_color="transparent")
    table.pack(fill="both", expand=True)

    def reload_data():
        state["budgets"], state["expenses"] = _load_budget_data(username)

    def refresh():
        month_spend = spend_by_category(state["month"], state["year"])
        year_spend = spend_by_category(year=state["year"])
        selected_spend = month_spend if period == "monthly" else year_spend
        period_total.configure(
            text=(f"Month: {_budget_currency(sum(month_spend.values()))}" if period == "monthly" else f"Selected year: {_budget_currency(sum(year_spend.values()))}")
        )
        year_total.configure(text=f"Year: {_budget_currency(sum(year_spend.values()))}")
        nav_label.configure(text=f"{calendar.month_name[state['month']]}  {state['year']}")
        draw_pie(pie_canvas, selected_spend)
        draw_bar(bar_canvas, [calendar.month_abbr[month] for month in range(1, 13)], monthly_totals())
        for widget in table.winfo_children():
            widget.destroy()
        for column, heading in enumerate(["Category", "Period", "Limit", "Spent", "Remaining", "%", ""]):
            ctk.CTkLabel(table, text=heading, font=("Segoe UI", 12, "bold"), text_color=muted).grid(row=0, column=column, padx=8, pady=4)
        rows = [
            budget
            for budget in state["budgets"]
            if budget["period"] == period
            and budget["year"] == state["year"]
            and (period != "monthly" or budget.get("month") == state["month"])
        ]
        for row_index, budget in enumerate(rows, start=1):
            spent = selected_spend.get(budget["category"], 0)
            limit_amt = budget["limit_amt"]
            remaining = limit_amt - spent
            percentage = spent / limit_amt * 100 if limit_amt else 0
            percentage_color = red if percentage >= 90 else (accent if percentage >= 70 else green)
            if percentage >= 90 and budget["id"] not in state["warned"]:
                state["warned"].add(budget["id"])
                budget_frame.after(100, lambda item=budget, value=percentage: messagebox.showwarning("Budget Alert", f"{item['category']} is at {value:.1f}% of limit!"))
            values = [
                budget["category"],
                budget["period"].capitalize(),
                _budget_currency(limit_amt),
                _budget_currency(spent),
                _budget_currency(max(0, remaining)),
                f"{percentage:.1f}%",
            ]
            value_colors = [text, muted, text, text, green if remaining >= 0 else red, percentage_color]
            for column, (value, color) in enumerate(zip(values, value_colors)):
                ctk.CTkLabel(table, text=value, font=("Segoe UI", 12), text_color=color).grid(row=row_index, column=column, padx=8, pady=3)
            ctk.CTkButton(
                table,
                text="✕",
                width=28,
                height=28,
                fg_color="transparent",
                text_color=red,
                hover_color="#3A1E1E",
                command=lambda budget_id=budget["id"]: delete(budget_id),
            ).grid(row=row_index, column=6)

    def delete(budget_id):
        success, error = _delete_budget(username, budget_id)
        if not success:
            messagebox.showerror("Database Error", f"Could not delete budget:\n{error}")
            return
        state["warned"].discard(budget_id)
        reload_data()
        refresh()

    def open_add():
        window = ctk.CTkToplevel(budget_frame)
        window.title("Add Budget")
        window.geometry("400x360")
        window.configure(fg_color=bg)
        window.grab_set()
        window.lift()
        ctk.CTkLabel(window, text="Add Budget", font=("Segoe UI", 20, "bold"), text_color=text).pack(anchor="w", padx=24, pady=(20, 12))

        def field(label, placeholder):
            row = ctk.CTkFrame(window, fg_color="transparent")
            row.pack(fill="x", padx=24, pady=4)
            ctk.CTkLabel(row, text=label, font=("Segoe UI", 13), text_color=muted, width=100, anchor="e").pack(side="left", padx=(0, 8))
            entry = ctk.CTkEntry(row, placeholder_text=placeholder, font=("Segoe UI", 13), fg_color=input_bg, border_color=border, text_color=text, placeholder_text_color=muted)
            entry.pack(side="left", fill="x", expand=True)
            return entry

        def dropdown(label, options, default):
            row = ctk.CTkFrame(window, fg_color="transparent")
            row.pack(fill="x", padx=24, pady=4)
            ctk.CTkLabel(row, text=label, font=("Segoe UI", 13), text_color=muted, width=100, anchor="e").pack(side="left", padx=(0, 8))
            combo = ctk.CTkComboBox(row, values=options, font=("Segoe UI", 13), fg_color=input_bg, border_color=border, text_color=text, button_color=border, dropdown_fg_color=card)
            combo.set(default)
            combo.pack(side="left", fill="x", expand=True)
            return combo

        category_entry = field("Category", "e.g. Food")
        limit_entry = field("Limit (Rs.)", "5000")
        dropdown("Period", [period.capitalize()], period.capitalize())
        month_combo = dropdown("Month", [calendar.month_name[month] for month in range(1, 13)], calendar.month_name[state["month"]])
        year_entry = field("Year", str(state["year"]))

        def save():
            category = category_entry.get().strip()
            if not category:
                messagebox.showerror("Error", "Enter a category.", parent=window)
                return
            try:
                limit_amt = float(limit_entry.get().replace(",", ""))
                year = int(year_entry.get() or state["year"])
            except ValueError:
                messagebox.showerror("Error", "Enter a valid limit and year.", parent=window)
                return
            month = [calendar.month_name[item] for item in range(1, 13)].index(month_combo.get()) + 1 if period == "monthly" else None
            success, error = _add_budget(username, category, period, limit_amt, month, year)
            if not success:
                messagebox.showerror("Database Error", f"Could not save budget:\n{error}", parent=window)
                return
            reload_data()
            refresh()
            window.destroy()

        ctk.CTkButton(window, text="Save Budget", fg_color=accent, text_color=bg, font=("Segoe UI", 14, "bold"), hover_color="#B89758", command=save).pack(fill="x", padx=24, pady=(16, 22))

    def navigate_month(delta):
        state["month"] += delta
        if state["month"] > 12:
            state["month"] = 1
            state["year"] += 1
        if state["month"] < 1:
            state["month"] = 12
            state["year"] -= 1
        refresh()

    def navigate_year(delta):
        state["year"] += delta
        refresh()

    ctk.CTkButton(nav, text="◀ Year", command=lambda: navigate_year(-1), **button_style).pack(side="left", padx=6, pady=7)
    ctk.CTkButton(nav, text="◀ Month", command=lambda: navigate_month(-1), **button_style).pack(side="left", padx=2, pady=7)
    nav_label.pack(side="left", expand=True)
    ctk.CTkButton(nav, text="Month ▶", command=lambda: navigate_month(1), **button_style).pack(side="right", padx=2, pady=7)
    ctk.CTkButton(nav, text="Year ▶", command=lambda: navigate_year(1), **button_style).pack(side="right", padx=6, pady=7)
    ctk.CTkButton(nav, text="+ Add Budget", width=130, height=34, fg_color=accent, text_color=bg, font=("Segoe UI", 13, "bold"), hover_color="#B89758", command=open_add).pack(side="right", padx=14, pady=7)

    pie_canvas.bind("<Configure>", lambda event: refresh())
    bar_canvas.bind("<Configure>", lambda event: refresh())
    reload_data()
    refresh()
    return budget_frame



def _hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return salt, digest


def _verify_password(password, salt, digest):
    _, computed = _hash_password(password, salt)
    return secrets.compare_digest(computed, digest)


def _validate_password(password):
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return "Password must contain an uppercase letter."
    if not re.search(r"[a-z]", password):
        return "Password must contain a lowercase letter."
    if not re.search(r"\d", password):
        return "Password must contain a number."
    return None


def center(win, width, height):
    win.update_idletasks()
    screen_width = win.winfo_screenwidth()
    screen_height = win.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    win.geometry(f"{width}x{height}+{x}+{y}")


def _clear_root(root):
    for child in root.winfo_children():
        child.destroy()


def sideb(
    parent,
    on_home=None,
    on_income=None,
    on_investments=None,
    on_balance=None,
    on_analytics=None,
    on_budget_monthly=None,
    on_budget_yearly=None,
):
    icon1 = ctk.CTkImage(dark_image=Image.open(_asset_path("icon1.png")))
    icon2 = ctk.CTkImage(dark_image=Image.open(_asset_path("icon2.png")))
    icon3 = ctk.CTkImage(dark_image=Image.open(_asset_path("icon3.png")))
    icon4 = ctk.CTkImage(dark_image=Image.open(_asset_path("icon4.png")))
    icon5 = ctk.CTkImage(dark_image=Image.open(_asset_path("icon5.png")))
    logo = ctk.CTkImage(dark_image=Image.open(_asset_path("final logo.png")), size=(222, 87))

    parent.grid_columnconfigure(0, weight=0, minsize=250)
    sidebar = ctk.CTkFrame(parent, width=250, fg_color="#202020", corner_radius=0)
    sidebar.grid(row=0, column=0, sticky="nsew")
    sidebar.grid_propagate(False)
    sidebar.grid_columnconfigure(0, weight=1)
    sidebar.grid_rowconfigure(8, weight=1)

    visible = False

    def showextra():
        nonlocal visible
        if not visible:
            bt4_1.grid(row=5, column=0, sticky="ew")
            bt4_2.grid(row=6, column=0, sticky="ew")
            bt5.grid_configure(row=7)
            bt4.configure(text="Budget                        ▼")
            visible = True
        else:
            bt4_1.grid_forget()
            bt4_2.grid_forget()
            bt5.grid_configure(row=5)
            bt4.configure(text="Budget                        ▶")
            visible = False

    logo_btn = ctk.CTkButton(
        sidebar,
        fg_color="#202020",
        hover_color="#202020",
        width=250,
        height=200,
        text="",
        image=logo,
        command=on_home,
    )
    logo_btn.grid(row=0, column=0)

    bt1 = ctk.CTkButton(
        sidebar,
        width=250,
        height=50,
        fg_color="#202020",
        hover_color="#00A998",
        text="Income/Expense",
        text_color="white",
        font=("Calibri", 20),
        anchor="w",
        image=icon1,
        command=on_income,
    )
    bt2 = ctk.CTkButton(
        sidebar,
        width=250,
        height=50,
        fg_color="#202020",
        hover_color="#00A998",
        text="Investments",
        text_color="white",
        font=("Calibri", 20),
        anchor="w",
        image=icon4,
        command=on_investments,
    )
    bt3 = ctk.CTkButton(
        sidebar,
        width=250,
        height=50,
        fg_color="#202020",
        hover_color="#00A998",
        text="Balance Management",
        text_color="white",
        font=("Calibri", 20),
        anchor="w",
        image=icon3,
        command=on_balance,
    )
    bt4 = ctk.CTkButton(
        sidebar,
        width=250,
        height=50,
        fg_color="#202020",
        hover_color="#00A998",
        text="Budget                        ▶",
        text_color="white",
        font=("Calibri", 20),
        anchor="w",
        image=icon5,
        command=showextra,
    )
    bt5 = ctk.CTkButton(
        sidebar,
        width=250,
        height=50,
        fg_color="#202020",
        hover_color="#00A998",
        text="Analytics",
        text_color="white",
        font=("Calibri", 20),
        anchor="w",
        image=icon2,
        command=on_analytics,
    )
    bt4_1 = ctk.CTkButton(
        sidebar,
        width=250,
        height=50,
        fg_color="#444444",
        hover_color="#00A998",
        text="   Monthly",
        text_color="white",
        anchor="w",
        font=("Calibri", 16),
        command=on_budget_monthly,
    )
    bt4_2 = ctk.CTkButton(
        sidebar,
        width=250,
        height=50,
        fg_color="#444444",
        hover_color="#00A998",
        text="   Yearly",
        text_color="white",
        anchor="w",
        font=("Calibri", 16),
        command=on_budget_yearly,
    )

    bt1.grid(row=1, column=0, sticky="ew")
    bt2.grid(row=2, column=0, sticky="ew")
    bt3.grid(row=3, column=0, sticky="ew")
    bt4.grid(row=4, column=0, sticky="ew")
    bt5.grid(row=5, column=0, sticky="ew")
    ctk.CTkFrame(sidebar, fg_color="#202020").grid(row=8, column=0, sticky="nsew")
    return sidebar


def _clear_content(holder):
    for child in holder.winfo_children():
        child.destroy()


def build_logged_in(root, username):
    _clear_root(root)
    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(0, weight=1)

    fra = ctk.CTkFrame(root, fg_color="#202020")
    fra.grid(row=0, column=0, sticky="nsew")
    fra.grid_columnconfigure(0, weight=0, minsize=250)
    fra.grid_columnconfigure(1, weight=1)
    fra.grid_rowconfigure(0, weight=1)

    content = ctk.CTkFrame(fra, fg_color="transparent")
    content.grid(row=0, column=1, sticky="nsew")
    content.grid_columnconfigure(0, weight=1)
    content.grid_rowconfigure(0, weight=1)

    def show_dashboard():
        _clear_content(content)
        build_dashboard(content, username, on_income=show_income)

    def show_income():
        _clear_content(content)
        build_income_expense(content, username)

    def show_investments():
        _clear_content(content)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)
        holder = ctk.CTkFrame(content, fg_color="#0d1117")
        holder.grid(row=0, column=0, sticky="nsew")
        build_investments(holder, username)

    def show_balance():
        _clear_content(content)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)
        frame = BalanceManagementFrame(content, username)
        frame.grid(row=0, column=0, sticky="nsew")

    def show_analytics():
        _clear_content(content)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)
        holder = ctk.CTkFrame(content, fg_color="transparent")
        holder.grid(row=0, column=0, sticky="nsew")
        build_analytics(holder, username)

    def show_monthly_budget():
        _clear_content(content)
        build_budget(content, username, "monthly")

    def show_yearly_budget():
        _clear_content(content)
        build_budget(content, username, "yearly")

    sideb(
        fra,
        on_home=show_dashboard,
        on_income=show_income,
        on_investments=show_investments,
        on_balance=show_balance,
        on_analytics=show_analytics,
        on_budget_monthly=show_monthly_budget,
        on_budget_yearly=show_yearly_budget,
    )
    show_dashboard()
    return fra


def build_dashboard(parent, username, on_income=None):
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(0, weight=1)

    trykare = ctk.CTkImage(dark_image=Image.open(_asset_path("wave.jpeg")), size=(1274, 784))
    wel = ctk.CTkImage(dark_image=Image.open(_asset_path("Welc.png")), size=(321, 179))

    intro = ctk.CTkFrame(parent, fg_color="transparent", bg_color="transparent")
    intro.grid(row=0, column=0, sticky="nsew")
    intro.grid_columnconfigure(0, weight=1)
    intro.grid_rowconfigure(0, weight=1)

    bg = ctk.CTkLabel(intro, image=trykare, text="")
    bg.place(relx=0, rely=0, relheight=1, relwidth=1)
    bg.lower()
    wave_src = Image.open(_asset_path("wave.jpeg"))
    bg_size = {"w": 0, "h": 0}

    def resize_bg(event):
        if event.width < 2 or event.height < 2:
            return
        if event.width == bg_size["w"] and event.height == bg_size["h"]:
            return
        bg_size["w"] = event.width
        bg_size["h"] = event.height
        resized = wave_src.resize((event.width, event.height), Image.Resampling.LANCZOS)
        new_img = ctk.CTkImage(dark_image=resized, size=(event.width, event.height))
        bg.configure(image=new_img)
        bg.image = new_img

    intro.bind("<Configure>", resize_bg)

    act = ctk.CTkFrame(intro)
    act.place(relx=0.04, rely=0.06, relwidth=0.92, relheight=0.88)
    act.grid_columnconfigure((0, 1, 2), weight=1)
    act.grid_rowconfigure(3, weight=1)

    hi = ctk.CTkLabel(
        act,
        text=f"Hi {username}!",
        text_color="#D7D7D7",
        font=("Segoe UI", 40),
        fg_color="transparent",
        bg_color="transparent",
    )
    hi.grid(row=0, column=0, columnspan=3, padx=50, pady=(20, 0), sticky="w")

    wlc = ctk.CTkLabel(act, image=wel, text="", fg_color="transparent", bg_color="transparent")
    wlc.grid(row=1, column=0, columnspan=3, pady=(20, 10))

    totals = get_user_totals(username)

    def stat_label(column, title, value, color):
        card = ctk.CTkLabel(
            act,
            width=300,
            height=100,
            fg_color=color,
            text=f"{title}:\n{_money(value)}",
            text_color="white",
            font=("Calibri", 30),
            corner_radius=8,
        )
        card.grid(row=2, column=column, padx=20, pady=30)

    stat_label(0, "Balance", totals["balance"], "#510000")
    stat_label(1, "Income", totals["income"], "#002E05")
    stat_label(2, "Expense", totals["expense"], "#001036")

    return intro


def build_income_expense(parent, username):
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(0, weight=1)

    ie = ctk.CTkFrame(parent, fg_color="#1B1B1F")
    ie.grid(row=0, column=0, sticky="nsew")
    ie.grid_columnconfigure(0, weight=1)
    ie.grid_rowconfigure(1, weight=1)

    InE = ctk.CTkLabel(ie, text="Income and Expenses", text_color="#F0EDE6", font=("Arial", 50))
    InE.grid(row=0, column=0, sticky="nw", pady=(50, 20), padx=50)

    iebox = ctk.CTkScrollableFrame(ie, fg_color="#2B2B2B")
    iebox.grid(row=1, column=0, sticky="nsew", pady=(20, 20), padx=50)

    combo_style = dict(
        width=250,
        height=40,
        corner_radius=8,
        fg_color="#202020",
        border_color="#555555",
        text_color="white",
        font=("Calibri", 16),
        button_color="#00A998",
        button_hover_color="#008F82",
        dropdown_fg_color="#202020",
        dropdown_text_color="white",
        dropdown_hover_color="#00A998",
        dropdown_font=("Calibri", 16),
    )

    row1 = ctk.CTkFrame(iebox, fg_color="#2B2B2B")
    row1.pack(pady=(10, 10), padx=50, anchor="nw", fill="x")
    ctk.CTkLabel(row1, text="Income/Expense:               ", text_color="#F0EDE6", font=("Arial", 25)).grid(
        row=1, column=0, sticky="nsew"
    )
    incexd = ctk.CTkComboBox(row1, values=["Income", "Expense"], **combo_style)
    incexd.grid(row=1, column=1, sticky="nsew")

    rowa = ctk.CTkFrame(iebox, fg_color="#2B2B2B")
    rowa.pack(pady=(10, 10), padx=50, anchor="nw", fill="x")
    ctk.CTkLabel(rowa, text="Amount:                            ", text_color="#F0EDE6", font=("Arial", 25)).grid(
        row=1, column=0, sticky="nsew"
    )
    amte = ctk.CTkEntry(
        rowa,
        placeholder_text="Enter Amount (₹)",
        width=250,
        height=40,
        corner_radius=8,
        fg_color="#202020",
        border_color="#555555",
    )
    amte.grid(row=1, column=1, sticky="nsew")

    row2 = ctk.CTkFrame(iebox, fg_color="#2B2B2B")
    row2.pack(pady=(10, 10), padx=50, anchor="nw", fill="x")
    ctk.CTkLabel(row2, text="Description:                       ", text_color="#F0EDE6", font=("Arial", 25)).grid(
        row=1, column=0, sticky="nsew"
    )
    dese = ctk.CTkEntry(
        row2,
        placeholder_text="Enter Description",
        width=250,
        height=40,
        corner_radius=8,
        fg_color="#202020",
        border_color="#555555",
    )
    dese.grid(row=1, column=1, sticky="nsew")

    row3 = ctk.CTkFrame(iebox, fg_color="#2B2B2B")
    row3.pack(pady=(10, 10), padx=50, anchor="nw", fill="x")
    ctk.CTkLabel(row3, text="Category:                           ", text_color="#F0EDE6", font=("Arial", 25)).grid(
        row=1, column=0, sticky="nsew"
    )
    catd = ctk.CTkComboBox(
        row3,
        values=[
            "Essentials",
            "Food",
            "Healthcare",
            "Travel",
            "Shopping",
            "Subscriptions",
            "Education",
            "Loans",
            "Housing",
            "Miscellaneous",
        ],
        **combo_style,
    )
    catd.grid(row=1, column=1, sticky="nsew")

    row4 = ctk.CTkFrame(iebox, fg_color="#2B2B2B")
    row4.pack(pady=(10, 10), padx=50, anchor="nw", fill="x")
    ctk.CTkLabel(row4, text="Mode of Payment:              ", text_color="#F0EDE6", font=("Arial", 25)).grid(
        row=1, column=0, sticky="nsew"
    )
    modd = ctk.CTkComboBox(
        row4,
        values=["UPI", "Cash", "Debit Card", "Credit Card", "Net Banking", "Cheque", "EMI"],
        **combo_style,
    )
    modd.grid(row=1, column=1, sticky="nsew")

    row5 = ctk.CTkFrame(iebox, fg_color="#2B2B2B")
    row5.pack(pady=(10, 10), padx=50, anchor="nw", fill="x")
    ctk.CTkLabel(row5, text="Date:(Date/Month/Year)     ", text_color="#F0EDE6", font=("Arial", 25)).grid(
        row=1, column=0, sticky="nsew"
    )
    day = ctk.CTkComboBox(row5, values=[str(i) for i in range(1, 32)], width=80, height=40, corner_radius=8, fg_color="#202020", border_color="#555555", text_color="white", font=("Calibri", 16), button_color="#00A998", button_hover_color="#008F82", dropdown_fg_color="#202020", dropdown_text_color="white", dropdown_hover_color="#00A998", dropdown_font=("Calibri", 16))
    day.grid(row=1, column=1, padx=5)
    month = ctk.CTkComboBox(row5, values=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"], width=80, height=40, corner_radius=8, fg_color="#202020", border_color="#555555", text_color="white", font=("Calibri", 16), button_color="#00A998", button_hover_color="#008F82", dropdown_fg_color="#202020", dropdown_text_color="white", dropdown_hover_color="#00A998", dropdown_font=("Calibri", 16))
    month.grid(row=1, column=2, padx=5)
    year = ctk.CTkComboBox(row5, values=[str(i) for i in range(2025, 2031)], width=110, height=40, corner_radius=8, fg_color="#202020", border_color="#555555", text_color="white", font=("Calibri", 16), button_color="#00A998", button_hover_color="#008F82", dropdown_fg_color="#202020", dropdown_text_color="white", dropdown_hover_color="#00A998", dropdown_font=("Calibri", 16))
    year.grid(row=1, column=3, padx=5)
    today = dt.date.today()
    day.set(str(today.day))
    month.set(str(today.month))
    year.set(str(today.year))

    row6 = ctk.CTkFrame(iebox, fg_color="#2B2B2B")
    row6.pack(pady=(10, 10), padx=50, anchor="nw", fill="x")
    ctk.CTkLabel(row6, text="Joy Index Tracker:             ", text_color="#F0EDE6", font=("Arial", 25)).pack(
        side="left", pady=10, anchor="nw"
    )
    jitd = ctk.CTkComboBox(row6, values=["1 (Least Joy)", "2", "3", "4", "5 (Most Joy)"], **combo_style)
    jitd.pack(padx=10, pady=10, anchor="nw")
    ctk.CTkLabel(
        row6,
        text="(How much Joy did this transaction give you on a scale of 1 to 5?)",
        text_color="#D2D2D2",
        font=("Arial", 20),
    ).pack(side="left", padx=10, pady=(10, 5), anchor="w")

    def save_transaction():
        try:
            amount = float(amte.get())
        except (TypeError, ValueError):
            messagebox.showerror("Invalid amount", "Please enter a valid amount.")
            return
        if amount <= 0:
            messagebox.showerror("Invalid amount", "Amount must be greater than 0.")
            return
        description = dese.get()
        category = catd.get()
        direction = incexd.get()
        mode = modd.get()
        try:
            day_value = int(day.get())
            month_value = int(month.get())
            year_value = int(year.get())
            joy = int(jitd.get()[0])
        except (TypeError, ValueError, IndexError):
            messagebox.showerror("Invalid input", "Please complete every field.")
            return
        transaction_date = "{}-{:02d}-{:02d}".format(year_value, month_value, day_value)
        ok, err = add_transaction(
            username,
            direction,
            category,
            amount,
            description,
            transaction_date,
            payment_mode=mode,
            joy_index=joy,
        )
        if not ok:
            messagebox.showerror("Could not save", err or "Could not add this transaction.")
            return
        messagebox.showinfo("Success", "Transaction added successfully!")
        amte.delete(0, "end")
        dese.delete(0, "end")

    ctk.CTkButton(
        iebox,
        text="Add transaction",
        fg_color="#00A998",
        text_color="white",
        width=250,
        height=50,
        font=("Arial", 20),
        command=save_transaction,
    ).pack(pady=(10, 10), padx=50, anchor="se")
    return ie


def build_auth_screen(root, logo_img):
    _clear_root(root)
    root.grid_columnconfigure(0, weight=0)
    root.grid_rowconfigure(0, weight=0)

    left_frame = ctk.CTkFrame(root, corner_radius=0)
    left_frame.pack(side="left", fill="both", expand=True)

    original_img = Image.open(_asset_path("bg.jpg"))
    img_label = ctk.CTkLabel(left_frame, text="")
    img_label.place(x=0, y=0, relwidth=1, relheight=1)

    def resize_image(event):
        new_width = max(event.width, 1)
        new_height = max(event.height, 1)
        resized = original_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        new_img = ctk.CTkImage(resized, size=(new_width, new_height))
        img_label.configure(image=new_img)
        img_label.image = new_img

    left_frame.bind("<Configure>", resize_image)

    right_frame = ctk.CTkFrame(root, fg_color="#0d0d0d")
    right_frame.pack(side="right", fill="both", expand=True)

    login_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
    signup_frame = ctk.CTkFrame(right_frame, fg_color="transparent")

    def show_login():
        signup_frame.pack_forget()
        login_status.configure(text="")
        login_frame.pack(fill="both", expand=True)

    def show_signup():
        login_frame.pack_forget()
        signup_status.configure(text="")
        signup_frame.pack(fill="both", expand=True)

    login_container = ctk.CTkFrame(login_frame, fg_color="transparent")
    login_container.place(relx=0.5, rely=0.5, anchor="center")
    ctk.CTkLabel(login_container, image=logo_img, text="").pack(pady=(0, 10))
    ctk.CTkLabel(login_container, text="Sign in", font=("Arial", 28)).pack(pady=10)
    username = ctk.CTkEntry(login_container, width=300, height=40, placeholder_text="Username")
    username.pack(pady=10)
    password = ctk.CTkEntry(login_container, width=300, height=40, show="*", placeholder_text="Password")
    password.pack(pady=10)
    login_status = ctk.CTkLabel(login_container, text="", text_color="#ff6b6b", font=("Arial", 12))
    login_status.pack()

    def attempt_login():
        user_value = username.get().strip()
        password_value = password.get()
        if not user_value or not password_value:
            login_status.configure(text="Please enter both username and password.", text_color="#ff6b6b")
            return
        record = get_user(user_value)
        if not record or not _verify_password(password_value, record["salt"], record["password_hash"]):
            login_status.configure(text="Invalid username or password.", text_color="#ff6b6b")
            return
        _clear_root(root)
        root.title("Expense Tracker")
        build_logged_in(root, user_value)

    ctk.CTkButton(
        login_container,
        text="Login",
        width=300,
        height=45,
        corner_radius=25,
        command=attempt_login,
    ).pack(pady=15)
    ctk.CTkButton(
        login_container,
        text="Create Account",
        width=300,
        height=45,
        fg_color="transparent",
        border_width=1,
        corner_radius=25,
        command=show_signup,
    ).pack(pady=10)

    signup_container = ctk.CTkFrame(signup_frame, fg_color="transparent")
    signup_container.place(relx=0.5, rely=0.5, anchor="center")
    ctk.CTkLabel(signup_container, image=logo_img, text="").pack(pady=(0, 10))
    ctk.CTkLabel(signup_container, text="Create Account", font=("Arial", 28)).pack(pady=10)
    new_user = ctk.CTkEntry(signup_container, width=300, height=40, placeholder_text="Username")
    new_user.pack(pady=10)
    new_pass = ctk.CTkEntry(signup_container, width=300, height=40, show="*", placeholder_text="Password")
    new_pass.pack(pady=10)
    confirm_pass = ctk.CTkEntry(
        signup_container,
        width=300,
        height=40,
        show="*",
        placeholder_text="Confirm Password",
    )
    confirm_pass.pack(pady=10)
    signup_status = ctk.CTkLabel(signup_container, text="", text_color="#ff6b6b", font=("Arial", 12))
    signup_status.pack()

    def attempt_signup():
        user_value = new_user.get().strip()
        password_value = new_pass.get()
        confirm_value = confirm_pass.get()
        if not user_value:
            signup_status.configure(text="Please enter a username.", text_color="#ff6b6b")
            return
        if len(user_value) > 50:
            signup_status.configure(text="Username must be 50 characters or fewer.", text_color="#ff6b6b")
            return
        if password_value != confirm_value:
            signup_status.configure(text="Passwords do not match.", text_color="#ff6b6b")
            return
        err = _validate_password(password_value)
        if err:
            signup_status.configure(text=err, text_color="#ff6b6b")
            return
        existing = get_user(user_value)
        if existing:
            signup_status.configure(text="Username already exists.", text_color="#ff6b6b")
            return
        salt, digest = _hash_password(password_value)
        if not create_user(user_value, salt, digest):
            signup_status.configure(text="Could not create account. Check MySQL connection.", text_color="#ff6b6b")
            return
        signup_status.configure(text="Account created! Please sign in.", text_color="#4ade80")
        new_user.delete(0, "end")
        new_pass.delete(0, "end")
        confirm_pass.delete(0, "end")
        root.after(900, show_login)

    ctk.CTkButton(
        signup_container,
        text="Create Account",
        width=300,
        height=45,
        corner_radius=25,
        command=attempt_signup,
    ).pack(pady=15)
    ctk.CTkButton(
        signup_container,
        text="Back to Login",
        width=300,
        height=45,
        fg_color="transparent",
        border_width=1,
        corner_radius=25,
        command=show_login,
    ).pack(pady=10)
    login_frame.pack(fill="both", expand=True)


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    root.title("Expense Tracker")
    center(root, 1524, 784)
    logo_img = ctk.CTkImage(Image.open(_asset_path("final logo.png")), size=(222, 87))
    if not init_database():
        print("MySQL connection failed. Check DB_CONFIG and make sure MySQL is running.")
    build_auth_screen(root, logo_img)
    root.mainloop()


if __name__ == "__main__":
    main()




