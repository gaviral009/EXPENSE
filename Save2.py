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

basedir = os.path.dirname(os.path.abspath(__file__))

dbconfig = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "123456"),
    "database": os.getenv("MYSQL_DATABASE", "expense_tracker"),
}


def assetpath(filename):
    return os.path.join(basedir, filename)


def money(amount):
    return f"₹{amount:,.2f}"


def getconnection(includedatabase=True):
    config = dbconfig.copy()
    if not includedatabase:
        config.pop("database", None)
    return mysql.connector.connect(**config)


def initdatabase():
    try:
        connection = getconnection(includedatabase=False)
        cursor = connection.cursor()
        cursor.execute(f"create database if not exists {dbconfig['database']}")
        cursor.close()
        connection.close()

        connection = getconnection()
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
        ensureuseridcolumn(cursor, "holdings")
        ensureuseridcolumn(cursor, "portfolio_history")
        ensureuseridcolumn(cursor, "budget")
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Exception as e:
        print("DATABASE INIT ERROR:", e)
        return False


def ensureuseridcolumn(cursor, tablename):
    cursor.execute(f"show columns from {tablename}")
    columns = {row[0] for row in cursor.fetchall()}
    if "user_id" in columns:
        return
    cursor.execute(f"alter table {tablename} add column user_id int")
    try:
        cursor.execute(
            f"alter table {tablename} add constraint {tablename}_user_fk foreign key (user_id) references users(id)"
        )
    except Exception:
        pass


def getuser(username):
    try:
        connection = getconnection()
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


def createuser(username, salt, passwordhash):
    try:
        connection = getconnection()
        cursor = connection.cursor()
        cursor.execute(
            "insert into users (username, salt, password_hash) values (%s, %s, %s)",
            (username, salt, passwordhash),
        )
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Exception as e:
        print("CREATE USER ERROR:", e)
        return False


def getusertotals(username):
    totals = {"income": 0.0, "expense": 0.0, "balance": 0.0}
    try:
        connection = getconnection()
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


categories = [
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


def addtransaction(
    username,
    direction,
    category,
    amount,
    description,
    transactiondate,
    paymentmode=None,
    joyindex=None,
):
    user = getuser(username)
    if not user:
        return False, "User not found."
    try:
        connection = getconnection()
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
                transactiondate,
                paymentmode,
                joyindex,
            ),
        )
        connection.commit()
        cursor.close()
        connection.close()
        return True, None
    except Exception as e:
        return False, str(e)


def listtransactions(username):
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
        connection = getconnection()
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


def updatetransaction(
    username,
    recordid,
    direction,
    category,
    amount,
    description,
    transactiondate,
    paymentmode=None,
    joyindex=None,
):
    user = getuser(username)
    if not user:
        return False, "User not found."
    try:
        connection = getconnection()
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
                transactiondate,
                paymentmode,
                joyindex,
                recordid,
                user["id"],
            ),
        )
        connection.commit()
        cursor.close()
        connection.close()
        return True, None
    except Exception as e:
        return False, str(e)


def deletetransaction(username, recordid):
    user = getuser(username)
    if not user:
        return False, "User not found."
    try:
        connection = getconnection()
        cursor = connection.cursor()
        cursor.execute(
            "delete from transactions where id = %s and user_id = %s",
            (recordid, user["id"]),
        )
        connection.commit()
        cursor.close()
        connection.close()
        return True, None
    except Exception as e:
        return False, str(e)



analyticscategories = [
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


def asdate(value):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str) and value:
        return dt.datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    return None


def expenserows(rows):
    expenses = []
    for row in rows:
        direction = (row.get("direction") or "").strip()
        if direction.lower() != "expense":
            continue
        expenses.append(
            {
                "amount": float(row.get("amount") or 0),
                "date": asdate(row.get("transaction_date")),
                "category": row.get("category") or "Miscellaneous",
            }
        )
    return expenses


def sevendaywindow(expenses):
    today = dt.date.today()
    dates = [item["date"] for item in expenses if item["date"]]
    end = today
    if dates:
        latest = max(dates)
        if latest > today or (today - latest).days > 6:
            end = latest
    return [end - dt.timedelta(days=offset) for offset in range(6, -1, -1)]


def buildanalytics(parent, username):
    map.close("all")
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(0, weight=1)

    rows = listtransactions(username)
    expenses = expenserows(rows)
    lastdays = sevendaywindow(expenses)
    spendbyday = {day: 0.0 for day in lastdays}
    categorytotals = {name: 0.0 for name in analyticscategories}
    totalspent = 0.0

    for item in expenses:
        totalspent += item["amount"]
        if item["date"] in spendbyday:
            spendbyday[item["date"]] += item["amount"]
        category = item["category"]
        if category not in categorytotals:
            categorytotals[category] = 0.0
        categorytotals[category] += item["amount"]

    days = [day.strftime("%d %b") for day in lastdays]
    spend = [spendbyday[day] for day in lastdays]
    pielabels = []
    pievalues = []
    for name, value in categorytotals.items():
        if value > 0:
            pielabels.append(name)
            pievalues.append(value)
    if not pievalues:
        pielabels = ["No data"]
        pievalues = [1]

    def refresh():
        for child in parent.winfo_children():
            child.destroy()
        buildanalytics(parent, username)

    an = ctk.CTkFrame(parent)
    an.grid(row=0, column=0, sticky="nsew")
    an.grid_columnconfigure(0, weight=1)
    an.grid_rowconfigure(1, weight=1)

    analyticslabel = ctk.CTkLabel(an, text="Analytics", text_color="white", font=("Arial", 50))
    analyticslabel.grid(row=0, column=0, sticky="nw", pady=(70, 30), padx=50)

    scroll = ctk.CTkScrollableFrame(an)
    scroll.grid(row=1, column=0, sticky="nsew")
    cards = ctk.CTkFrame(scroll, width=1200, height=120)
    cards.pack()

    atext = "Total Spent: ₹" + str(float(totalspent))
    a = ctk.CTkLabel(cards, height=100, width=250, text=atext, text_color="white", font=("Calibri", 25), fg_color="#0B0D4D", corner_radius=6)
    a.pack(padx=20, pady=20, side="left")

    if any(spend):
        high = max(spendbyday, key=spendbyday.get)
        low = min(spendbyday, key=spendbyday.get)
        btext = "Highest Spent On: " + high.strftime("%d %b")
        ctext = "Lowest Spent On: " + low.strftime("%d %b")
    else:
        btext = "Highest Spent On: —"
        ctext = "Lowest Spent On: —"
    b = ctk.CTkLabel(cards, height=100, width=250, text=btext, text_color="white", font=("Calibri", 25), fg_color="#510000", corner_radius=6)
    b.pack(padx=20, pady=20, side="left")
    c = ctk.CTkLabel(cards, height=100, width=250, text=ctext, text_color="white", font=("Calibri", 25), fg_color="#002E05", corner_radius=6)
    c.pack(padx=20, pady=20, side="left")

    avg = sum(spend) / len(spend) if spend else 0
    dtext = "Average Daily: ₹" + str(round(avg, 2))
    d = ctk.CTkLabel(cards, height=100, width=250, text=dtext, text_color="white", font=("Calibri", 25), fg_color="#660033", corner_radius=6)
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

    qw = max(pievalues)
    explode = [0] * len(pievalues)
    explode[pievalues.index(qw)] = 0.1
    fig2, ax2 = map.subplots()
    ax2.pie(
        pievalues,
        labels=pielabels,
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

    def selectrow(index):
        selectedrow["index"] = index
        for i, rowframe in enumerate(tablerows):
            rowframe.configure(fg_color="#00A998" if i == index else ("#2B2B2B" if i % 2 == 0 else "#242424"))

    def selectedrecord():
        index = selectedrow["index"]
        if index is None or index < 0 or index >= len(rows):
            messagebox.showinfo("select a row", "Click a transaction in the table first.")
            return None
        return rows[index]

    def deleterow():
        record = selectedrecord()
        if not record:
            return
        if not messagebox.askyesno("Delete", "Delete this transaction?"):
            return
        ok, err = deletetransaction(username, record["id"])
        if not ok:
            messagebox.showerror("Could not delete", err or "Could not delete this transaction.")
            return
        refresh()

    def editrow():
        record = selectedrecord()
        if not record:
            return
        when = asdate(record.get("transaction_date")) or dt.date.today()
        popwin = ctk.CTkToplevel(parent)
        popwin.title("Edit transaction")
        popwin.geometry("420x520")
        popwin.grab_set()

        ctk.CTkLabel(popwin, text="Edit transaction", font=("Arial", 22)).pack(pady=(20, 10))
        typebox = ctk.CTkComboBox(popwin, values=["Income", "Expense"], width=300)
        typebox.set(record.get("direction") or "Expense")
        typebox.pack(pady=8)
        amountbox = ctk.CTkEntry(popwin, width=300, placeholder_text="Amount")
        amountbox.insert(0, str(record.get("amount") or ""))
        amountbox.pack(pady=8)
        descbox = ctk.CTkEntry(popwin, width=300, placeholder_text="Description")
        descbox.insert(0, record.get("description") or "")
        descbox.pack(pady=8)
        catbox = ctk.CTkComboBox(popwin, values=analyticscategories, width=300)
        catbox.set(record.get("category") or "Miscellaneous")
        catbox.pack(pady=8)
        modebox = ctk.CTkComboBox(
            popwin,
            values=["UPI", "Cash", "Debit Card", "Credit Card", "Net Banking", "Cheque", "EMI"],
            width=300,
        )
        modebox.set(record.get("payment_mode") or "UPI")
        modebox.pack(pady=8)
        daterow = ctk.CTkFrame(popwin, fg_color="transparent")
        daterow.pack(pady=8)
        daybox = ctk.CTkComboBox(daterow, values=[str(i) for i in range(1, 32)], width=80)
        monthbox = ctk.CTkComboBox(daterow, values=[str(i) for i in range(1, 13)], width=80)
        yearbox = ctk.CTkComboBox(daterow, values=[str(i) for i in range(2025, 2031)], width=110)
        daybox.set(str(when.day))
        monthbox.set(str(when.month))
        yearbox.set(str(when.year))
        daybox.pack(side="left", padx=4)
        monthbox.pack(side="left", padx=4)
        yearbox.pack(side="left", padx=4)

        def saveedit():
            try:
                amount = float(amountbox.get())
                transactiondate = "{}-{:02d}-{:02d}".format(int(yearbox.get()), int(monthbox.get()), int(daybox.get()))
            except (TypeError, ValueError):
                messagebox.showerror("Invalid input", "Please enter a valid amount and date.")
                return
            ok, err = updatetransaction(
                username,
                record["id"],
                typebox.get(),
                catbox.get(),
                amount,
                descbox.get(),
                transactiondate,
                paymentmode=modebox.get(),
                joyindex=record.get("joy_index"),
            )
            if not ok:
                messagebox.showerror("Could not save", err or "Could not update this transaction.")
                return
            popwin.destroy()
            refresh()

        ctk.CTkButton(popwin, text="Save", fg_color="#00A998", command=saveedit).pack(pady=16)

    his = ctk.CTkLabel(scroll, text="Transaction history:", font=("Arial", 25))
    his.pack(pady=10)

    tableholder = ctk.CTkFrame(scroll, fg_color="#1a1a1a")
    tableholder.pack(pady=20, fill="x", padx=10)
    headers = ["Sl. No.", "Date", "Description", "Amount", "Category", "Type", "Mode"]
    headerrow = ctk.CTkFrame(tableholder, fg_color="#00A998")
    headerrow.pack(fill="x")
    for col, title in enumerate(headers):
        ctk.CTkLabel(headerrow, text=title, font=("Arial", 16, "bold"), text_color="white", width=150, anchor="w").grid(
            row=0, column=col, padx=8, pady=8, sticky="ew"
        )
        headerrow.grid_columnconfigure(col, weight=1)

    tablerows = []
    for index, row in enumerate(rows):
        when = asdate(row.get("transaction_date"))
        datetext = when.strftime("%d/%m/%Y") if when else ""
        values = [
            str(index + 1),
            datetext,
            row.get("description") or "",
            money(row.get("amount") or 0),
            row.get("category") or "",
            row.get("direction") or "",
            row.get("payment_mode") or "",
        ]
        color = "#2B2B2B" if index % 2 == 0 else "#242424"
        rowframe = ctk.CTkFrame(tableholder, fg_color=color)
        rowframe.pack(fill="x")
        rowframe.bind("<Button-1>", lambda e, i=index: selectrow(i))
        for col, value in enumerate(values):
            cell = ctk.CTkLabel(rowframe, text=value, font=("Arial", 16), text_color="white", width=150, anchor="w")
            cell.grid(row=0, column=col, padx=8, pady=8, sticky="ew")
            cell.bind("<Button-1>", lambda e, i=index: selectrow(i))
            rowframe.grid_columnconfigure(col, weight=1)
        tablerows.append(rowframe)

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

colors = {
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
investmentusername = None

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


def asdatetime(value):
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


def investmentuser():
    user = getuser(investmentusername) if investmentusername else None
    if not user:
        messagebox.showerror("User not found", "Could not match this portfolio to a logged-in user.")
        return None
    return user


def loadinvestmentsfromdb():
    global lst, his
    lst = []
    his = []
    user = getuser(investmentusername) if investmentusername else None
    if not user:
        return
    try:
        connection = getconnection()
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
                    "added_at": asdatetime(row["created_at"]),
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
                asdatetime(row["recorded_at"]),
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
            saveportfoliosnapshot(user["id"], snapshot[0], snapshot[1], snapshot[2])
    except Exception as e:
        print("LOAD INVESTMENTS ERROR:", e)
        lst = []
        his = []


def saveportfoliosnapshot(userid, recordedat, totalvalue, totalinvested):
    try:
        connection = getconnection()
        cursor = connection.cursor()
        cursor.execute(
            """
            insert into portfolio_history (user_id, recorded_at, total_value, total_invested)
            values (%s, %s, %s, %s)
            """,
            (userid, recordedat, totalvalue, totalinvested),
        )
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Exception as e:
        print("SAVE PORTFOLIO HISTORY ERROR:", e)
        return False


def saveholdingtodb(holding):
    user = investmentuser()
    if not user:
        return False
    try:
        connection = getconnection()
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
        totalvalue = sum(item["value"] for item in lst)
        totalinvested = sum(item["invested"] for item in lst)
        cursor.execute(
            """
            insert into portfolio_history (user_id, recorded_at, total_value, total_invested)
            values (%s, %s, %s, %s)
            """,
            (user["id"], holding["added_at"], totalvalue, totalinvested),
        )
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Exception as e:
        messagebox.showerror("Database Error", f"Could not save investment:\n{e}")
        return False


def updateholdingindb(holding):
    user = investmentuser()
    if not user:
        return False
    try:
        connection = getconnection()
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
        totalvalue = sum(item["value"] for item in lst)
        totalinvested = sum(item["invested"] for item in lst)
        cursor.execute(
            """
            insert into portfolio_history (user_id, recorded_at, total_value, total_invested)
            values (%s, %s, %s, %s)
            """,
            (user["id"], holding["added_at"], totalvalue, totalinvested),
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
        toppct = top["value"] / tv * 100 if tv else 0
        if toppct >= 40:
            nlb.configure(text=f"{top['name']} makes up {round(toppct, 1)}% of your portfolio.",
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
    updatebar(tv, ti);
    renderchart();
    grd()


def updatebar(tv, ti):
    bcv.delete("all");
    w = bcv.winfo_width()
    if w > 1:
        bw = min(w, max(2, int(w * min(1.0, ti / tv if tv else 0))))
        bcv.create_rectangle(0, 1, bw, 6, fill=acc, outline="")


def renderchart():
    cvs.delete("all")
    w, h = cvs.winfo_width(), cvs.winfo_height()
    if w < 10 or h < 10:
        cvs.after(100, renderchart)
        return
    (drawdonutchart if currentchartmode == "allocation"
     else drawtimelinechart)(w, h)


def drawdonutchart(w, h):
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
    cx, cy, radius = int(w * 0.32), int(h * 0.5), min(int(w * 0.32) - 30,
                                                 int(h * 0.5) - 25, 105)
    rin = int(radius * 0.52)
    start = 90.0
    for hitem in sorted(lst, key=lambda x: x["value"], reverse=True):
        f = hitem["value"] / tv
        ext = -f * 360
        cvs.create_arc(cx - radius, cy - radius, cx + radius, cy + radius,
                       start=start, extent=ext,
                       fill=hitem["color"], outline=crd, width=2)
        if f >= 0.05:
            md = start + ext / 2
            rad = math.radians(md)
            lr = (radius + rin) / 2
            lx = cx + lr * math.cos(rad)
            ly = cy - lr * math.sin(rad)
            cvs.create_text(lx, ly,
                            text=f"{round(f * 100, 1)}%",
                            fill="#1B1B1F", font=("Segoe UI", 11, "bold"))
        start += ext
    cvs.create_oval(cx - rin, cy - rin, cx + rin, cy + rin,
                    fill=crd, outline="")
    cvs.create_text(cx, cy - 10, text="Holdings",
                    fill=mut, font=("Segoe UI", 12, "bold"))
    cvs.create_text(cx, cy + 12, text=str(len(lst)),
                    fill=txt, font=("Segoe UI", 18, "bold"))
    legx = int(w * 0.58)
    starty = max(18, int(h * 0.5 - (min(len(lst), 7) * 30) / 2))
    for i, hitem in enumerate(sorted(lst, key=lambda x: x["value"], reverse=True)[:7]):
        y = starty + i * 30
        f = hitem["value"] / tv
        cvs.create_rectangle(legx, y, legx + 16, y + 16,
                             fill=hitem["color"])
        cvs.create_text(legx + 26, y + 8,
                        text=hitem["ticker"], anchor="w",
                        fill=txt, font=("Segoe UI", 14, "bold"))
        cvs.create_text(legx + 175, y + 8,
                        text=f"{round(f * 100, 1)}%", anchor="w",
                        fill=acc, font=("Segoe UI", 14, "bold"))
    if len(lst) > 7:
        rem = sum(x["value"] for x in lst[7:]) / tv
        y = starty + 7 * 30
        cvs.create_rectangle(legx, y, legx + 16, y + 16,
                             fill="#6e7f8f")
        cvs.create_text(legx + 26, y + 8,
                        text=f"Others ({len(lst) - 7})", anchor="w",
                        fill=mut, font=("Segoe UI", 13))
        cvs.create_text(legx + 175, y + 8,
                        text=f"{round(rem * 100, 1)}%", anchor="w",
                        fill=mut, font=("Segoe UI", 13))


def drawtimelinechart(w, h):
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
    linecol, fillcol = (acc, "#382E1E") if pnl >= 0 else (red, "#3A1E1E")
    if len(his) == 1:
        mx = pl + cw // 2
        my = pt + ch // 2
        cvs.create_line(pl, my, w - pr, my, fill=brd, width=1)
        cvs.create_oval(mx - 6, my - 6, mx + 6, my + 6,
                        fill=linecol, outline=crd)
        s = "+" if pnl >= 0 else ""
        cvs.create_text(mx, my - 14,
                        text=f"P&L: {s}{inr(pnl)}", fill=linecol,
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
    zeroy = pt + ch - ((-mnd) / rng * ch)
    cvs.create_line(pl, zeroy, w - pr, zeroy,
                    fill=mut, width=1, dash=(3, 3))
    cvs.create_text(w - pr, zeroy - 10,
                    text="Break-even", fill=mut,
                    font=("Segoe UI", 10), anchor="e")
    fpt = cds + [(cds[-1][0], pt + ch), (cds[0][0], pt + ch)]
    cvs.create_polygon([c for p in fpt for c in p],
                       fill=fillcol, outline="")
    fcd = [c for p in cds for c in p]
    cvs.create_line(fcd, fill=linecol, width=2,
                    smooth=len(cds) >= 3)
    for i, (cx, cy) in enumerate(cds):
        r = 6 if i == len(cds) - 1 else 4
        cvs.create_oval(cx - r, cy - r, cx + r, cy + r,
                        fill=linecol, outline=crd)
    for i, t in enumerate([e[0] for e in his]):
        cx = cds[i][0]
        cvs.create_text(cx, pt + ch + 8,
                        text=t.strftime("%d %b\n%H:%M"),
                        fill=linecol if i == len(his) - 1 else mut,
                        font=("Segoe UI", 10,
                              "bold" if i == len(his) - 1 else "normal"),
                        anchor="n", justify="center")


def togglechartmode(v):
    global currentchartmode
    currentchartmode = "allocation" if "Pie" in v else "timeline"
    renderchart()


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
    combotype = ctk.CTkComboBox(r2,
                                 values=["Equity", "Crypto", "Mutual Fund",
                                         "ETF", "Bond"],
                                 font=("Segoe UI", 14),
                                 fg_color=ibg, border_color=brd,
                                 text_color=txt, button_color=brd,
                                 dropdown_fg_color=crd)
    combotype.set("Equity")
    combotype.grid(row=1, column=0, sticky="ew", padx=(0, 6))
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
        typ, sub = combotype.get(), esb.get().strip()
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
            updateholdingindb(existing)
            nh = existing
        else:
            nh = {"name": nm, "ticker": tkr, "type": typ,
                  "sub": sub, "invested": inv, "value": val,
                  "color": pcl, "letter": tkr[0],
                  "added_at": dt.datetime.now()}
            lst.append(nh)
            saveholdingtodb(nh)

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
                          (deleteholdingfromdb(hid),
                           win.destroy(),
                           pop())) \
                .grid(row=0, column=3, rowspan=2,
                      padx=(0, 16), pady=12)


def deleteholdingfromdb(holdingid):
    global lst, his
    user = investmentuser()
    if not user:
        return False
    try:
        connection = getconnection()
        cursor = connection.cursor()
        cursor.execute(
            "delete from holdings where id = %s and user_id = %s",
            (holdingid, user["id"]),
        )
        connection.commit()
        cursor.close()
        connection.close()
        lst = [holding for holding in lst if holding.get("id") != holdingid]
        his.append((dt.datetime.now(),
                    sum(holding["value"] for holding in lst),
                    sum(holding["invested"] for holding in lst)))
        ref()
        return True
    except Exception as e:
        messagebox.showerror("DB Error", f"Delete failed:\n{e}")
        return False


def buildinvestments(parent, username):
    global app, ctl, vlb, ilb, ylb, clb, cvs, hfr, bcv, rlb, plb, nlb
    global investmentusername, currentchartmode
    investmentusername = username
    currentchartmode = "allocation"
    app = parent
    app.configure(fg_color=bg)
    loadinvestmentsfromdb()
    bar = ctk.CTkFrame(app, fg_color=bg, height=65)
    bar.pack(fill="x", padx=20, pady=(16, 0))
    bar.pack_propagate(False)
    logoimg = (ctk.CTkImage(Image.open("logo.png"), size=(135, 48))
                if os.path.exists("logo.png") else None)
    if logoimg:
        ctk.CTkLabel(bar, image=logoimg, text="").pack(side="left",
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
    topright = ctk.CTkFrame(header, fg_color="transparent")
    topright.pack(side="right", anchor="n")
    ylb = ctk.CTkLabel(topright,
                       text="+0.0% Return",
                       font=("Segoe UI", 16, "bold"),
                       text_color=acc)
    ylb.pack(anchor="e", pady=(0, 6))
    charttab = ctk.CTkSegmentedButton(topright,
                                       values=["Allocation Pie",
                                               "Performance (P&L)"],
                                       command=togglechartmode,
                                       font=("Segoe UI", 12, "bold"),
                                       fg_color=ibg, selected_color=acc,
                                       selected_hover_color="#B89758",
                                       unselected_color=crd,
                                       text_color=txt)
    charttab.set("Allocation Pie")
    charttab.pack(anchor="e")
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
    cvs.bind("<Configure>", lambda e: renderchart())

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
    bcv.bind("<Configure>", lambda e: updatebar(
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

def createbalancetable():
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
        connection = getconnection()
        cursor = connection.cursor()
        cursor.execute(query)
        connection.commit()
    except mysql.connector.Error as err:
        messagebox.showerror("Database Error", f"Could not create balance table:\n{err}")
    finally:
        if "connection" in locals():
            connection.close()


def insertbalancerecord(username, amount, description, recordtype, recorddate):
    query = """
        insert into balance (username, amount, description, type, date)
        values (%s, %s, %s, %s, %s)
    """

    try:
        connection = getconnection()
        cursor = connection.cursor()
        cursor.execute(
            query,
            (
                username,
                amount,
                description,
                recordtype,
                recorddate,
            ),
        )
        connection.commit()
        return True, None
    except mysql.connector.Error as err:
        return False, str(err)
    finally:
        if "connection" in locals():
            connection.close()


def fetchbalancerecords(username):
    query = """
        select id, amount, description, type, date
        from balance
        where username = %s
        order by date desc, id desc
    """

    try:
        connection = getconnection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (username,))
        return cursor.fetchall()
    except mysql.connector.Error as err:
        messagebox.showerror("Database Error", f"Could not fetch records:\n{err}")
        return []
    finally:
        if "connection" in locals():
            connection.close()


def deletebalancerecord(recordid, username):
    query = """
        delete from balance
        where id = %s and username = %s
    """

    try:
        connection = getconnection()
        cursor = connection.cursor()
        cursor.execute(query, (recordid, username))
        connection.commit()
        return True, None
    except mysql.connector.Error as err:
        return False, str(err)
    finally:
        if "connection" in locals():
            connection.close()


def fetchbalancetotals(username):
    query = """
        select
            coalesce(sum(case when type = 'You owe' then amount else 0 end), 0) as total_you_owe,
            coalesce(sum(case when type = 'You are owed' then amount else 0 end), 0) as total_you_are_owed
        from balance
        where username = %s
    """

    try:
        connection = getconnection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (username,))
        row = cursor.fetchone()

        totalyouowe = Decimal(str(row["total_you_owe"] or 0))
        totalyouareowed = Decimal(str(row["total_you_are_owed"] or 0))
        netbalance = totalyouareowed - totalyouowe

        return totalyouowe, totalyouareowed, netbalance
    except mysql.connector.Error as err:
        messagebox.showerror("Database Error", f"Could not calculate totals:\n{err}")
        return Decimal("0.00"), Decimal("0.00"), Decimal("0.00")
    finally:
        if "connection" in locals():
            connection.close()


class balancemanager(ctk.CTkFrame):
    def __init__(self, master, username):
        super().__init__(master)
        self.username = username

        createbalancetable()
        self.buildui()
        self.loadrecords()

    def buildui(self):
        self.configure(fg_color=colors["bg"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        self.summaryframe = ctk.CTkFrame(self, fg_color="transparent")
        self.summaryframe.grid(
            row=0,
            column=0,
            columnspan=2,
            padx=24,
            pady=(24, 10),
            sticky="ew",
        )

        for column in range(3):
            self.summaryframe.grid_columnconfigure(column, weight=1, uniform="summary")

        _, self.totalowevalue = self.createsummarycard(
            self.summaryframe, 0, "Total You Owe", colors["red"]
        )
        _, self.totalowedvalue = self.createsummarycard(
            self.summaryframe, 1, "Total You Are Owed", colors["green"]
        )
        _, self.netbalancevalue = self.createsummarycard(
            self.summaryframe, 2, "Net Balance", colors["yellow"]
        )

        self.formframe = ctk.CTkFrame(
            self,
            fg_color=colors["panel"],
            corner_radius=18,
            border_width=1,
            border_color=colors["border"],
        )
        self.formframe.grid(row=1, column=0, padx=(24, 12), pady=(10, 24), sticky="nsew")
        self.formframe.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.formframe,
            text="Balance Manager",
            text_color=colors["text"],
            font=ctk.CTkFont(size=28, weight="bold"),
        ).grid(row=0, column=0, padx=24, pady=(28, 8), sticky="w")

        ctk.CTkLabel(
            self.formframe,
            text="Track what you owe and what others owe you.",
            text_color=colors["muted"],
            font=ctk.CTkFont(size=14),
        ).grid(row=1, column=0, padx=24, pady=(0, 24), sticky="w")

        self.amountentry = self.createentry("Amount")
        self.amountentry.grid(row=2, column=0, padx=24, pady=(0, 16), sticky="ew")

        self.descriptionentry = self.createentry("Description")
        self.descriptionentry.grid(row=3, column=0, padx=24, pady=(0, 16), sticky="ew")

        self.typedropdown = ctk.CTkOptionMenu(
            self.formframe,
            values=["You owe", "You are owed"],
            fg_color=colors["input"],
            button_color=colors["blue"],
            button_hover_color=colors["blue_hover"],
            dropdown_fg_color=colors["card"],
            dropdown_hover_color=colors["blue"],
            dropdown_text_color=colors["text"],
            text_color=colors["text"],
            corner_radius=12,
            height=46,
            font=ctk.CTkFont(size=15),
        )
        self.typedropdown.grid(row=4, column=0, padx=24, pady=(0, 16), sticky="ew")
        self.typedropdown.set("You owe")

        self.dateentry = self.createentry("Date  YYYY-MM-DD")
        self.dateentry.insert(0, dt.date.today().strftime("%Y-%m-%d"))
        self.dateentry.grid(row=5, column=0, padx=24, pady=(0, 24), sticky="ew")

        self.addbutton = ctk.CTkButton(
            self.formframe,
            text="Add Record",
            command=self.addrecord,
            fg_color=colors["blue"],
            hover_color=colors["blue_hover"],
            text_color=colors["text"],
            corner_radius=14,
            height=48,
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.addbutton.grid(row=6, column=0, padx=24, pady=(0, 28), sticky="ew")

        self.recordscontainer = ctk.CTkFrame(
            self,
            fg_color=colors["panel"],
            corner_radius=18,
            border_width=1,
            border_color=colors["border"],
        )
        self.recordscontainer.grid(row=1, column=1, padx=(12, 24), pady=(10, 24), sticky="nsew")
        self.recordscontainer.grid_columnconfigure(0, weight=1)
        self.recordscontainer.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self.recordscontainer,
            text="Records",
            text_color=colors["text"],
            font=ctk.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, padx=24, pady=(24, 12), sticky="w")

        self.recordsframe = ctk.CTkScrollableFrame(
            self.recordscontainer,
            fg_color="transparent",
            scrollbar_button_color=colors["border"],
            scrollbar_button_hover_color=colors["blue"],
        )
        self.recordsframe.grid(row=1, column=0, padx=18, pady=(0, 18), sticky="nsew")
        self.recordsframe.grid_columnconfigure(0, weight=1)

    def createentry(self, placeholder):
        return ctk.CTkEntry(
            self.formframe,
            placeholder_text=placeholder,
            fg_color=colors["input"],
            border_color=colors["border"],
            text_color=colors["text"],
            placeholder_text_color=colors["muted"],
            corner_radius=12,
            height=48,
            font=ctk.CTkFont(size=15),
        )

    def createsummarycard(self, parent, column, title, color):
        card = ctk.CTkFrame(
            parent,
            fg_color=colors["card"],
            corner_radius=16,
            border_width=1,
            border_color=colors["border"],
        )
        card.grid(row=0, column=column, padx=8, sticky="ew")

        ctk.CTkLabel(
            card,
            text=title,
            text_color=colors["muted"],
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", padx=18, pady=(16, 4))

        valuelabel = ctk.CTkLabel(
            card,
            text="0.00",
            text_color=color,
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        valuelabel.pack(anchor="w", padx=18, pady=(0, 16))

        return card, valuelabel

    def validateinputs(self):
        amounttext = self.amountentry.get().strip()
        description = self.descriptionentry.get().strip()
        recordtype = self.typedropdown.get()
        datetext = self.dateentry.get().strip()

        if not amounttext:
            messagebox.showwarning("Validation Error", "Amount is required.")
            return None

        try:
            amount = Decimal(amounttext)
            if amount <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            messagebox.showwarning("Validation Error", "Amount must be a positive number.")
            return None

        if not description:
            messagebox.showwarning("Validation Error", "Description is required.")
            return None

        try:
            recorddate = dt.datetime.strptime(datetext, "%Y-%m-%d").date()
        except ValueError:
            messagebox.showwarning("Validation Error", "Date must be in YYYY-MM-DD format.")
            return None

        return amount, description, recordtype, recorddate

    def addrecord(self):
        cleanedvalues = self.validateinputs()

        if cleanedvalues is None:
            return

        amount, description, recordtype, recorddate = cleanedvalues

        self.addbutton.configure(state="disabled", text="Adding...")
        self.update_idletasks()

        def saverecord():
            success, error = insertbalancerecord(
                self.username,
                amount,
                description,
                recordtype,
                recorddate,
            )
            self.after(0, lambda: self.afterrecordsaved(success, error))

        threading.Thread(target=saverecord, daemon=True).start()

    def afterrecordsaved(self, success, error=None):
        self.addbutton.configure(state="normal", text="Add Record")

        if success:
            self.clearinputs()
            self.loadrecords()
            messagebox.showinfo("Success", "Balance record added successfully.")
        elif error:
            messagebox.showerror("Database Error", f"Could not add record:\n{error}")

    def clearinputs(self):
        self.amountentry.delete(0, "end")
        self.descriptionentry.delete(0, "end")
        self.typedropdown.set("You owe")
        self.dateentry.delete(0, "end")
        self.dateentry.insert(0, dt.date.today().strftime("%Y-%m-%d"))

    def loadrecords(self):
        for widget in self.recordsframe.winfo_children():
            widget.destroy()

        records = fetchbalancerecords(self.username)

        if not records:
            ctk.CTkLabel(
                self.recordsframe,
                text="No balance records found.",
                text_color=colors["muted"],
                font=ctk.CTkFont(size=15),
            ).grid(row=0, column=0, padx=10, pady=30)
        else:
            for index, record in enumerate(records):
                self.addrecordrow(index, record)

        self.updatetotals()

    def addrecordrow(self, rownumber, record):
        recordid = record["id"]
        amount = f"{Decimal(str(record['amount'])):.2f}"
        description = record["description"]
        recordtype = record["type"]
        rawdate = record["date"]
        if hasattr(rawdate, "strftime"):
            recorddate = rawdate.strftime("%Y-%m-%d")
        else:
            recorddate = str(rawdate) if rawdate is not None else ""
        typecolor = colors["red"] if recordtype == "You owe" else colors["green"]

        card = ctk.CTkFrame(
            self.recordsframe,
            fg_color=colors["card"],
            corner_radius=14,
            border_width=1,
            border_color=colors["border"],
        )
        card.grid(row=rownumber, column=0, padx=4, pady=8, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=0)

        ctk.CTkLabel(
            card,
            text=amount,
            text_color=typecolor,
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, padx=18, pady=(14, 2), sticky="w")

        ctk.CTkLabel(
            card,
            text=recordtype,
            text_color=typecolor,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=1, padx=18, pady=(14, 2), sticky="e")

        ctk.CTkLabel(
            card,
            text=description,
            text_color=colors["text"],
            font=ctk.CTkFont(size=15),
            anchor="w",
            justify="left",
            wraplength=420,
        ).grid(row=1, column=0, columnspan=2, padx=18, pady=(2, 6), sticky="ew")

        ctk.CTkLabel(
            card,
            text=recorddate,
            text_color=colors["muted"],
            font=ctk.CTkFont(size=13),
        ).grid(row=2, column=0, padx=18, pady=(0, 14), sticky="w")

        ctk.CTkButton(
            card,
            text="Delete",
            command=lambda rid=recordid: self.confirmdeleterecord(rid),
            fg_color=colors["red"],
            hover_color=colors["red_hover"],
            text_color=colors["text"],
            corner_radius=10,
            width=86,
            height=32,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=2, column=1, padx=18, pady=(0, 14), sticky="e")

    def confirmdeleterecord(self, recordid):
        confirm = messagebox.askyesno(
            "Delete Record",
            "Are you sure you want to delete this balance record?",
        )

        if not confirm:
            return

        def deleterecord():
            success, error = deletebalancerecord(recordid, self.username)
            self.after(0, lambda: self.afterrecorddeleted(success, error))

        threading.Thread(target=deleterecord, daemon=True).start()

    def afterrecorddeleted(self, success, error=None):
        if success:
            self.loadrecords()
            messagebox.showinfo("Deleted", "Balance record deleted successfully.")
        elif error:
            messagebox.showerror("Database Error", f"Could not delete record:\n{error}")

    def updatetotals(self):
        totalyouowe, totalyouareowed, netbalance = fetchbalancetotals(self.username)

        self.totalowevalue.configure(text=f"{totalyouowe:.2f}")
        self.totalowedvalue.configure(text=f"{totalyouareowed:.2f}")
        self.netbalancevalue.configure(text=f"{netbalance:.2f}")



def loadbudgetdata(username):
    """Return this user's saved budgets and expense transactions."""
    user = getuser(username)
    if not user:
        return [], []

    connection = None
    cursor = None
    try:
        connection = getconnection()
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


def addbudget(username, category, period, limitamt, month, year):
    user = getuser(username)
    if not user:
        return False, "User not found."
    connection = None
    cursor = None
    try:
        connection = getconnection()
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
                limitamt,
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


def deletebudget(username, budgetid):
    user = getuser(username)
    if not user:
        return False, "User not found."
    connection = None
    cursor = None
    try:
        connection = getconnection()
        cursor = connection.cursor()
        cursor.execute(
            "delete from budget where id = %s and user_id = %s",
            (budgetid, user["id"]),
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


def budgetcurrency(value):
    number = int(round(value))
    digits = str(abs(number))
    if len(digits) <= 3:
        result = digits
    else:
        lastthree, remaining, groups = digits[-3:], digits[:-3], []
        while len(remaining) > 2:
            groups.append(remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.append(remaining)
        groups.reverse()
        result = ",".join(groups) + "," + lastthree
    return ("-Rs. " if number < 0 else "Rs. ") + result


def buildbudget(parent, username, period):
    """Build the monthly or yearly budget view inside the main application."""
    bg, card, border, accent, text = "#1B1B1F", "#242429", "#38383F", "#C9A96E", "#F0EDE6"
    muted, green, red, inputbg = "#9C9993", "#4EBA6F", "#E06A6A", "#161619"
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
    budgetframe = ctk.CTkFrame(parent, fg_color=bg)
    budgetframe.grid(row=0, column=0, sticky="nsew")

    top = ctk.CTkFrame(budgetframe, fg_color=bg, height=68)
    top.pack(fill="x", padx=20, pady=(14, 0))
    top.pack_propagate(False)
    title = "Monthly Budget" if period == "monthly" else "Yearly Budget"
    ctk.CTkLabel(top, text=title, font=("Segoe UI", 28, "bold"), text_color=text).pack(side="left")
    yeartotal = ctk.CTkLabel(top, text="Year: Rs. 0", font=("Segoe UI", 14, "bold"), text_color=accent)
    periodtotal = ctk.CTkLabel(
        top,
        text=("Month: Rs. 0" if period == "monthly" else "Selected year: Rs. 0"),
        font=("Segoe UI", 14, "bold"),
        text_color=green,
    )
    yeartotal.pack(side="right", padx=(0, 24))
    periodtotal.pack(side="right", padx=(0, 30))

    nav = ctk.CTkFrame(budgetframe, fg_color=card, corner_radius=10)
    nav.pack(fill="x", padx=20, pady=8)
    buttonstyle = dict(
        width=95,
        height=34,
        fg_color="transparent",
        border_width=1,
        border_color=border,
        text_color=text,
        hover_color=border,
        font=("Segoe UI", 13),
    )
    navlabel = ctk.CTkLabel(nav, text="", font=("Segoe UI", 17, "bold"), text_color=accent)

    body = ctk.CTkFrame(budgetframe, fg_color=bg)
    body.pack(fill="both", expand=True, padx=20, pady=(0, 16))
    body.columnconfigure((0, 1), weight=1)
    body.rowconfigure((0, 1), weight=1)

    def spendbycategory(month=None, year=None):
        totals = {}
        for expense in state["expenses"]:
            expensedate = expense["date"]
            if year and expensedate.year != year:
                continue
            if month and expensedate.month != month:
                continue
            category = expense["category"]
            totals[category] = totals.get(category, 0) + expense["amount"]
        return totals

    def monthlytotals():
        totals = [0.0] * 12
        for expense in state["expenses"]:
            if expense["date"].year == state["year"]:
                totals[expense["date"].month - 1] += expense["amount"]
        return totals

    def drawpie(canvas, data):
        canvas.delete("all")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 10 or height < 10:
            canvas.after(100, lambda: drawpie(canvas, data))
            return
        total = sum(data.values()) or 1
        centerx, centery = int(width * 0.38), height // 2
        radius = min(centerx - 20, centery - 20, 110)
        innerradius = int(radius * 0.52)
        start = 90.0
        for index, (_, value) in enumerate(sorted(data.items(), key=lambda item: -item[1])):
            extent = -(value / total) * 360
            canvas.create_arc(
                centerx - radius,
                centery - radius,
                centerx + radius,
                centery + radius,
                start=start,
                extent=extent,
                fill=colors[index % len(colors)],
                outline=card,
                width=2,
            )
            start += extent
        canvas.create_oval(
            centerx - innerradius,
            centery - innerradius,
            centerx + innerradius,
            centery + innerradius,
            fill=card,
            outline="",
        )
        canvas.create_text(centerx, centery, text=budgetcurrency(sum(data.values())), fill=text, font=("Segoe UI", 11, "bold"))
        legendx = centerx + radius + 20
        legendy = max(10, centery - len(data) * 13)
        for index, (label, value) in enumerate(sorted(data.items(), key=lambda item: -item[1])[:8]):
            y = legendy + index * 26
            canvas.create_rectangle(legendx, y, legendx + 12, y + 12, fill=colors[index % len(colors)], outline="")
            canvas.create_text(legendx + 18, y + 6, text=label, anchor="w", fill=text, font=("Segoe UI", 11))
            canvas.create_text(legendx + 160, y + 6, text=f"{value / total * 100:.1f}%", anchor="w", fill=accent, font=("Segoe UI", 11, "bold"))

    def drawbar(canvas, labels, values):
        canvas.delete("all")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 10 or height < 10:
            canvas.after(100, lambda: drawbar(canvas, labels, values))
            return
        paddingleft, paddingright, paddingtop, paddingbottom = 65, 10, 20, 38
        chartwidth = width - paddingleft - paddingright
        chartheight = height - paddingtop - paddingbottom
        maximum = max(values) if any(value > 0 for value in values) else 1
        gap = chartwidth // len(labels)
        barwidth = int(gap * 0.6)
        for index in range(5):
            gridy = paddingtop + chartheight * index // 4
            canvas.create_line(paddingleft, gridy, width - paddingright, gridy, fill="#2F2F36", width=1)
            canvas.create_text(paddingleft - 6, gridy, text=budgetcurrency(maximum * (1 - index / 4)), anchor="e", fill=muted, font=("Segoe UI", 9))
        for index, (label, value) in enumerate(zip(labels, values)):
            barx = paddingleft + index * gap + (gap - barwidth) // 2
            barheight = int(chartheight * value / maximum) if maximum else 0
            bary = paddingtop + chartheight - barheight
            canvas.create_rectangle(barx, bary, barx + barwidth, paddingtop + chartheight, fill=accent if value > 0 else border, outline="")
            canvas.create_text(barx + barwidth // 2, paddingtop + chartheight + 5, text=label, fill=muted, font=("Segoe UI", 9), anchor="n")
            if value > 0:
                canvas.create_text(barx + barwidth // 2, bary - 3, text=budgetcurrency(value), fill=text, font=("Segoe UI", 8), anchor="s")

    def makecard(row, column, titletext):
        frame = ctk.CTkFrame(body, fg_color=card, corner_radius=12, border_width=1, border_color=border)
        frame.grid(
            row=row,
            column=column,
            sticky="nsew",
            padx=(0, 8) if column == 0 else (8, 0),
            pady=(0, 8) if row == 0 else (8, 0),
        )
        ctk.CTkLabel(frame, text=titletext, font=("Segoe UI", 14, "bold"), text_color=text).pack(anchor="w", padx=16, pady=(14, 4))
        return frame

    pieframe = makecard(0, 0, "Category Breakdown")
    piecanvas = tk.Canvas(pieframe, bg=card, highlightthickness=0, height=230)
    piecanvas.pack(fill="both", expand=True, padx=14, pady=(0, 14))
    barframe = makecard(0, 1, "Monthly Spend – This Year")
    barcanvas = tk.Canvas(barframe, bg=card, highlightthickness=0, height=230)
    barcanvas.pack(fill="both", expand=True, padx=14, pady=(0, 14))
    tableframe = makecard(1, 1, "Budget vs Spend")
    scroll = ctk.CTkScrollableFrame(tableframe, fg_color="transparent", scrollbar_button_color=border)
    scroll.pack(fill="both", expand=True, padx=8, pady=(0, 10))
    table = ctk.CTkFrame(scroll, fg_color="transparent")
    table.pack(fill="both", expand=True)

    def reloaddata():
        state["budgets"], state["expenses"] = loadbudgetdata(username)

    def refresh():
        monthspend = spendbycategory(state["month"], state["year"])
        yearspend = spendbycategory(year=state["year"])
        selectedspend = monthspend if period == "monthly" else yearspend
        periodtotal.configure(
            text=(f"Month: {budgetcurrency(sum(monthspend.values()))}" if period == "monthly" else f"Selected year: {budgetcurrency(sum(yearspend.values()))}")
        )
        yeartotal.configure(text=f"Year: {budgetcurrency(sum(yearspend.values()))}")
        navlabel.configure(text=f"{calendar.month_name[state['month']]}  {state['year']}")
        drawpie(piecanvas, selectedspend)
        drawbar(barcanvas, [calendar.month_abbr[month] for month in range(1, 13)], monthlytotals())
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
        for rowindex, budget in enumerate(rows, start=1):
            spent = selectedspend.get(budget["category"], 0)
            limitamt = budget["limit_amt"]
            remaining = limitamt - spent
            percentage = spent / limitamt * 100 if limitamt else 0
            percentagecolor = red if percentage >= 90 else (accent if percentage >= 70 else green)
            if percentage >= 90 and budget["id"] not in state["warned"]:
                state["warned"].add(budget["id"])
                budgetframe.after(100, lambda item=budget, value=percentage: messagebox.showwarning("Budget Alert", f"{item['category']} is at {value:.1f}% of limit!"))
            values = [
                budget["category"],
                budget["period"].capitalize(),
                budgetcurrency(limitamt),
                budgetcurrency(spent),
                budgetcurrency(max(0, remaining)),
                f"{percentage:.1f}%",
            ]
            valuecolors = [text, muted, text, text, green if remaining >= 0 else red, percentagecolor]
            for column, (value, color) in enumerate(zip(values, valuecolors)):
                ctk.CTkLabel(table, text=value, font=("Segoe UI", 12), text_color=color).grid(row=rowindex, column=column, padx=8, pady=3)
            ctk.CTkButton(
                table,
                text="✕",
                width=28,
                height=28,
                fg_color="transparent",
                text_color=red,
                hover_color="#3A1E1E",
                command=lambda budgetid=budget["id"]: delete(budgetid),
            ).grid(row=rowindex, column=6)

    def delete(budgetid):
        success, error = deletebudget(username, budgetid)
        if not success:
            messagebox.showerror("Database Error", f"Could not delete budget:\n{error}")
            return
        state["warned"].discard(budgetid)
        reloaddata()
        refresh()

    def openadd():
        window = ctk.CTkToplevel(budgetframe)
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
            entry = ctk.CTkEntry(row, placeholder_text=placeholder, font=("Segoe UI", 13), fg_color=inputbg, border_color=border, text_color=text, placeholder_text_color=muted)
            entry.pack(side="left", fill="x", expand=True)
            return entry

        def dropdown(label, options, default):
            row = ctk.CTkFrame(window, fg_color="transparent")
            row.pack(fill="x", padx=24, pady=4)
            ctk.CTkLabel(row, text=label, font=("Segoe UI", 13), text_color=muted, width=100, anchor="e").pack(side="left", padx=(0, 8))
            combo = ctk.CTkComboBox(row, values=options, font=("Segoe UI", 13), fg_color=inputbg, border_color=border, text_color=text, button_color=border, dropdown_fg_color=card)
            combo.set(default)
            combo.pack(side="left", fill="x", expand=True)
            return combo

        categoryentry = field("Category", "e.g. Food")
        limitentry = field("Limit (Rs.)", "5000")
        dropdown("Period", [period.capitalize()], period.capitalize())
        monthcombo = dropdown("Month", [calendar.month_name[month] for month in range(1, 13)], calendar.month_name[state["month"]])
        yearentry = field("Year", str(state["year"]))

        def save():
            category = categoryentry.get().strip()
            if not category:
                messagebox.showerror("Error", "Enter a category.", parent=window)
                return
            try:
                limitamt = float(limitentry.get().replace(",", ""))
                year = int(yearentry.get() or state["year"])
            except ValueError:
                messagebox.showerror("Error", "Enter a valid limit and year.", parent=window)
                return
            month = [calendar.month_name[item] for item in range(1, 13)].index(monthcombo.get()) + 1 if period == "monthly" else None
            success, error = addbudget(username, category, period, limitamt, month, year)
            if not success:
                messagebox.showerror("Database Error", f"Could not save budget:\n{error}", parent=window)
                return
            reloaddata()
            refresh()
            window.destroy()

        ctk.CTkButton(window, text="Save Budget", fg_color=accent, text_color=bg, font=("Segoe UI", 14, "bold"), hover_color="#B89758", command=save).pack(fill="x", padx=24, pady=(16, 22))

    def navigatemonth(delta):
        state["month"] += delta
        if state["month"] > 12:
            state["month"] = 1
            state["year"] += 1
        if state["month"] < 1:
            state["month"] = 12
            state["year"] -= 1
        refresh()

    def navigateyear(delta):
        state["year"] += delta
        refresh()

    ctk.CTkButton(nav, text="◀ Year", command=lambda: navigateyear(-1), **buttonstyle).pack(side="left", padx=6, pady=7)
    ctk.CTkButton(nav, text="◀ Month", command=lambda: navigatemonth(-1), **buttonstyle).pack(side="left", padx=2, pady=7)
    navlabel.pack(side="left", expand=True)
    ctk.CTkButton(nav, text="Month ▶", command=lambda: navigatemonth(1), **buttonstyle).pack(side="right", padx=2, pady=7)
    ctk.CTkButton(nav, text="Year ▶", command=lambda: navigateyear(1), **buttonstyle).pack(side="right", padx=6, pady=7)
    ctk.CTkButton(nav, text="+ Add Budget", width=130, height=34, fg_color=accent, text_color=bg, font=("Segoe UI", 13, "bold"), hover_color="#B89758", command=openadd).pack(side="right", padx=14, pady=7)

    piecanvas.bind("<Configure>", lambda event: refresh())
    barcanvas.bind("<Configure>", lambda event: refresh())
    reloaddata()
    refresh()
    return budgetframe



def hashpassword(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return salt, digest


def verifypassword(password, salt, digest):
    _, computed = hashpassword(password, salt)
    return secrets.compare_digest(computed, digest)


def validatepassword(password):
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
    screenwidth = win.winfo_screenwidth()
    screenheight = win.winfo_screenheight()
    x = (screenwidth // 2) - (width // 2)
    y = (screenheight // 2) - (height // 2)
    win.geometry(f"{width}x{height}+{x}+{y}")


def clearroot(root):
    for child in root.winfo_children():
        child.destroy()


def sideb(
    parent,
    onhome=None,
    onincome=None,
    oninvestments=None,
    onbalance=None,
    onanalytics=None,
    onbudgetmonthly=None,
    onbudgetyearly=None,
):
    icon1 = ctk.CTkImage(dark_image=Image.open(assetpath("icon1.png")))
    icon2 = ctk.CTkImage(dark_image=Image.open(assetpath("icon2.png")))
    icon3 = ctk.CTkImage(dark_image=Image.open(assetpath("icon3.png")))
    icon4 = ctk.CTkImage(dark_image=Image.open(assetpath("icon4.png")))
    icon5 = ctk.CTkImage(dark_image=Image.open(assetpath("icon5.png")))
    logo = ctk.CTkImage(dark_image=Image.open(assetpath("final logo.png")), size=(222, 87))

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
            bt41.grid(row=5, column=0, sticky="ew")
            bt42.grid(row=6, column=0, sticky="ew")
            bt5.grid_configure(row=7)
            bt4.configure(text="Budget                        ▼")
            visible = True
        else:
            bt41.grid_forget()
            bt42.grid_forget()
            bt5.grid_configure(row=5)
            bt4.configure(text="Budget                        ▶")
            visible = False

    logobtn = ctk.CTkButton(
        sidebar,
        fg_color="#202020",
        hover_color="#202020",
        width=250,
        height=200,
        text="",
        image=logo,
        command=onhome,
    )
    logobtn.grid(row=0, column=0)

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
        command=onincome,
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
        command=oninvestments,
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
        command=onbalance,
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
        command=onanalytics,
    )
    bt41 = ctk.CTkButton(
        sidebar,
        width=250,
        height=50,
        fg_color="#444444",
        hover_color="#00A998",
        text="   Monthly",
        text_color="white",
        anchor="w",
        font=("Calibri", 16),
        command=onbudgetmonthly,
    )
    bt42 = ctk.CTkButton(
        sidebar,
        width=250,
        height=50,
        fg_color="#444444",
        hover_color="#00A998",
        text="   Yearly",
        text_color="white",
        anchor="w",
        font=("Calibri", 16),
        command=onbudgetyearly,
    )

    bt1.grid(row=1, column=0, sticky="ew")
    bt2.grid(row=2, column=0, sticky="ew")
    bt3.grid(row=3, column=0, sticky="ew")
    bt4.grid(row=4, column=0, sticky="ew")
    bt5.grid(row=5, column=0, sticky="ew")
    ctk.CTkFrame(sidebar, fg_color="#202020").grid(row=8, column=0, sticky="nsew")
    return sidebar


def clearcontent(holder):
    for child in holder.winfo_children():
        child.destroy()


def buildloggedin(root, username):
    clearroot(root)
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

    def showdashboard():
        clearcontent(content)
        builddashboard(content, username, onincome=showincome)

    def showincome():
        clearcontent(content)
        buildincomeexpense(content, username)

    def showinvestments():
        clearcontent(content)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)
        holder = ctk.CTkFrame(content, fg_color="#0d1117")
        holder.grid(row=0, column=0, sticky="nsew")
        buildinvestments(holder, username)

    def showbalance():
        clearcontent(content)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)
        frame = balancemanager(content, username)
        frame.grid(row=0, column=0, sticky="nsew")

    def showanalytics():
        clearcontent(content)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)
        holder = ctk.CTkFrame(content, fg_color="transparent")
        holder.grid(row=0, column=0, sticky="nsew")
        buildanalytics(holder, username)

    def showmonthlybudget():
        clearcontent(content)
        buildbudget(content, username, "monthly")

    def showyearlybudget():
        clearcontent(content)
        buildbudget(content, username, "yearly")

    sideb(
        fra,
        onhome=showdashboard,
        onincome=showincome,
        oninvestments=showinvestments,
        onbalance=showbalance,
        onanalytics=showanalytics,
        onbudgetmonthly=showmonthlybudget,
        onbudgetyearly=showyearlybudget,
    )
    showdashboard()
    return fra


def builddashboard(parent, username, onincome=None):
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(0, weight=1)

    trykare = ctk.CTkImage(dark_image=Image.open(assetpath("wave.jpeg")), size=(1274, 784))
    wel = ctk.CTkImage(dark_image=Image.open(assetpath("Welc.png")), size=(321, 179))

    intro = ctk.CTkFrame(parent, fg_color="transparent", bg_color="transparent")
    intro.grid(row=0, column=0, sticky="nsew")
    intro.grid_columnconfigure(0, weight=1)
    intro.grid_rowconfigure(0, weight=1)

    bg = ctk.CTkLabel(intro, image=trykare, text="")
    bg.place(relx=0, rely=0, relheight=1, relwidth=1)
    bg.lower()
    wavesrc = Image.open(assetpath("wave.jpeg"))
    bgsize = {"w": 0, "h": 0}

    def resizebg(event):
        if event.width < 2 or event.height < 2:
            return
        if event.width == bgsize["w"] and event.height == bgsize["h"]:
            return
        bgsize["w"] = event.width
        bgsize["h"] = event.height
        resized = wavesrc.resize((event.width, event.height), Image.Resampling.LANCZOS)
        newimg = ctk.CTkImage(dark_image=resized, size=(event.width, event.height))
        bg.configure(image=newimg)
        bg.image = newimg

    intro.bind("<Configure>", resizebg)

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

    totals = getusertotals(username)

    def statlabel(column, title, value, color):
        card = ctk.CTkLabel(
            act,
            width=300,
            height=100,
            fg_color=color,
            text=f"{title}:\n{money(value)}",
            text_color="white",
            font=("Calibri", 30),
            corner_radius=8,
        )
        card.grid(row=2, column=column, padx=20, pady=30)

    statlabel(0, "Balance", totals["balance"], "#510000")
    statlabel(1, "Income", totals["income"], "#002E05")
    statlabel(2, "Expense", totals["expense"], "#001036")

    return intro


def buildincomeexpense(parent, username):
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(0, weight=1)

    ie = ctk.CTkFrame(parent, fg_color="#1B1B1F")
    ie.grid(row=0, column=0, sticky="nsew")
    ie.grid_columnconfigure(0, weight=1)
    ie.grid_rowconfigure(1, weight=1)

    incomelabel = ctk.CTkLabel(ie, text="Income and Expenses", text_color="#F0EDE6", font=("Arial", 50))
    incomelabel.grid(row=0, column=0, sticky="nw", pady=(50, 20), padx=50)

    iebox = ctk.CTkScrollableFrame(ie, fg_color="#2B2B2B")
    iebox.grid(row=1, column=0, sticky="nsew", pady=(20, 20), padx=50)

    combostyle = dict(
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
    incexd = ctk.CTkComboBox(row1, values=["Income", "Expense"], **combostyle)
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
        **combostyle,
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
        **combostyle,
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
    jitd = ctk.CTkComboBox(row6, values=["1 (Least Joy)", "2", "3", "4", "5 (Most Joy)"], **combostyle)
    jitd.pack(padx=10, pady=10, anchor="nw")
    ctk.CTkLabel(
        row6,
        text="(How much Joy did this transaction give you on a scale of 1 to 5?)",
        text_color="#D2D2D2",
        font=("Arial", 20),
    ).pack(side="left", padx=10, pady=(10, 5), anchor="w")

    def savetransaction():
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
            dayvalue = int(day.get())
            monthvalue = int(month.get())
            yearvalue = int(year.get())
            joy = int(jitd.get()[0])
        except (TypeError, ValueError, IndexError):
            messagebox.showerror("Invalid input", "Please complete every field.")
            return
        transactiondate = "{}-{:02d}-{:02d}".format(yearvalue, monthvalue, dayvalue)
        ok, err = addtransaction(
            username,
            direction,
            category,
            amount,
            description,
            transactiondate,
            paymentmode=mode,
            joyindex=joy,
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
        command=savetransaction,
    ).pack(pady=(10, 10), padx=50, anchor="se")
    return ie


def buildauthscreen(root, logoimg):
    clearroot(root)
    root.grid_columnconfigure(0, weight=0)
    root.grid_rowconfigure(0, weight=0)

    leftframe = ctk.CTkFrame(root, corner_radius=0)
    leftframe.pack(side="left", fill="both", expand=True)

    originalimg = Image.open(assetpath("bg.jpg"))
    imglabel = ctk.CTkLabel(leftframe, text="")
    imglabel.place(x=0, y=0, relwidth=1, relheight=1)

    def resizeimage(event):
        newwidth = max(event.width, 1)
        newheight = max(event.height, 1)
        resized = originalimg.resize((newwidth, newheight), Image.Resampling.LANCZOS)
        newimg = ctk.CTkImage(resized, size=(newwidth, newheight))
        imglabel.configure(image=newimg)
        imglabel.image = newimg

    leftframe.bind("<Configure>", resizeimage)

    rightframe = ctk.CTkFrame(root, fg_color="#0d0d0d")
    rightframe.pack(side="right", fill="both", expand=True)

    loginframe = ctk.CTkFrame(rightframe, fg_color="transparent")
    signupframe = ctk.CTkFrame(rightframe, fg_color="transparent")

    def showlogin():
        signupframe.pack_forget()
        loginstatus.configure(text="")
        loginframe.pack(fill="both", expand=True)

    def showsignup():
        loginframe.pack_forget()
        signupstatus.configure(text="")
        signupframe.pack(fill="both", expand=True)

    logincontainer = ctk.CTkFrame(loginframe, fg_color="transparent")
    logincontainer.place(relx=0.5, rely=0.5, anchor="center")
    ctk.CTkLabel(logincontainer, image=logoimg, text="").pack(pady=(0, 10))
    ctk.CTkLabel(logincontainer, text="Sign in", font=("Arial", 28)).pack(pady=10)
    username = ctk.CTkEntry(logincontainer, width=300, height=40, placeholder_text="Username")
    username.pack(pady=10)
    password = ctk.CTkEntry(logincontainer, width=300, height=40, show="*", placeholder_text="Password")
    password.pack(pady=10)
    loginstatus = ctk.CTkLabel(logincontainer, text="", text_color="#ff6b6b", font=("Arial", 12))
    loginstatus.pack()

    def attemptlogin():
        uservalue = username.get().strip()
        passwordvalue = password.get()
        if not uservalue or not passwordvalue:
            loginstatus.configure(text="Please enter both username and password.", text_color="#ff6b6b")
            return
        record = getuser(uservalue)
        if not record or not verifypassword(passwordvalue, record["salt"], record["password_hash"]):
            loginstatus.configure(text="Invalid username or password.", text_color="#ff6b6b")
            return
        clearroot(root)
        root.title("Expense Tracker")
        buildloggedin(root, uservalue)

    ctk.CTkButton(
        logincontainer,
        text="Login",
        width=300,
        height=45,
        corner_radius=25,
        command=attemptlogin,
    ).pack(pady=15)
    ctk.CTkButton(
        logincontainer,
        text="Create Account",
        width=300,
        height=45,
        fg_color="transparent",
        border_width=1,
        corner_radius=25,
        command=showsignup,
    ).pack(pady=10)

    signupcontainer = ctk.CTkFrame(signupframe, fg_color="transparent")
    signupcontainer.place(relx=0.5, rely=0.5, anchor="center")
    ctk.CTkLabel(signupcontainer, image=logoimg, text="").pack(pady=(0, 10))
    ctk.CTkLabel(signupcontainer, text="Create Account", font=("Arial", 28)).pack(pady=10)
    newuser = ctk.CTkEntry(signupcontainer, width=300, height=40, placeholder_text="Username")
    newuser.pack(pady=10)
    newpass = ctk.CTkEntry(signupcontainer, width=300, height=40, show="*", placeholder_text="Password")
    newpass.pack(pady=10)
    confirmpass = ctk.CTkEntry(
        signupcontainer,
        width=300,
        height=40,
        show="*",
        placeholder_text="Confirm Password",
    )
    confirmpass.pack(pady=10)
    signupstatus = ctk.CTkLabel(signupcontainer, text="", text_color="#ff6b6b", font=("Arial", 12))
    signupstatus.pack()

    def attemptsignup():
        uservalue = newuser.get().strip()
        passwordvalue = newpass.get()
        confirmvalue = confirmpass.get()
        if not uservalue:
            signupstatus.configure(text="Please enter a username.", text_color="#ff6b6b")
            return
        if len(uservalue) > 50:
            signupstatus.configure(text="Username must be 50 characters or fewer.", text_color="#ff6b6b")
            return
        if passwordvalue != confirmvalue:
            signupstatus.configure(text="Passwords do not match.", text_color="#ff6b6b")
            return
        err = validatepassword(passwordvalue)
        if err:
            signupstatus.configure(text=err, text_color="#ff6b6b")
            return
        existing = getuser(uservalue)
        if existing:
            signupstatus.configure(text="Username already exists.", text_color="#ff6b6b")
            return
        salt, digest = hashpassword(passwordvalue)
        if not createuser(uservalue, salt, digest):
            signupstatus.configure(text="Could not create account. Check MySQL connection.", text_color="#ff6b6b")
            return
        signupstatus.configure(text="Account created! Please sign in.", text_color="#4ade80")
        newuser.delete(0, "end")
        newpass.delete(0, "end")
        confirmpass.delete(0, "end")
        root.after(900, showlogin)

    ctk.CTkButton(
        signupcontainer,
        text="Create Account",
        width=300,
        height=45,
        corner_radius=25,
        command=attemptsignup,
    ).pack(pady=15)
    ctk.CTkButton(
        signupcontainer,
        text="Back to Login",
        width=300,
        height=45,
        fg_color="transparent",
        border_width=1,
        corner_radius=25,
        command=showlogin,
    ).pack(pady=10)
    loginframe.pack(fill="both", expand=True)


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    root.title("Expense Tracker")
    center(root, 1524, 784)
    logoimg = ctk.CTkImage(Image.open(assetpath("final logo.png")), size=(222, 87))
    if not initdatabase():
        print("MySQL connection failed. Check DB_CONFIG and make sure MySQL is running.")
    buildauthscreen(root, logoimg)
    root.mainloop()


if __name__ == "__main__":
    main()




