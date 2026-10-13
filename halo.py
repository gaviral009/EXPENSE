import datetime as dt
import hashlib
import os
import re
import secrets

import customtkinter as ctk
import mysql.connector
from PIL import Image
from tkinter import messagebox

from analytics import build_analytics
from balance_manager import BalanceManagementFrame
from investments import build_investments

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
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
        cursor.close()
        connection.close()

        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                salt CHAR(32) NOT NULL,
                password_hash CHAR(64) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                direction ENUM('Income', 'Expense') NOT NULL,
                category VARCHAR(80) NOT NULL,
                amount DECIMAL(12, 2) NOT NULL,
                description VARCHAR(255),
                transaction_date DATE NOT NULL,
                payment_mode VARCHAR(40),
                joy_index INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        cursor.execute("SHOW COLUMNS FROM transactions")
        columns = {row[0] for row in cursor.fetchall()}
        if "payment_mode" not in columns:
            cursor.execute("ALTER TABLE transactions ADD COLUMN payment_mode VARCHAR(40)")
        if "joy_index" not in columns:
            cursor.execute("ALTER TABLE transactions ADD COLUMN joy_index INT")
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Exception as e:
        print("DATABASE INIT ERROR:", e)
        return False


def get_user(username):
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, username, salt, password_hash FROM users WHERE username = %s",
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
            "INSERT INTO users (username, salt, password_hash) VALUES (%s, %s, %s)",
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
            SELECT
                COALESCE(SUM(CASE WHEN t.direction = 'Income' THEN t.amount ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN t.direction = 'Expense' THEN t.amount ELSE 0 END), 0)
            FROM transactions t
            JOIN users u ON u.id = t.user_id
            WHERE u.username = %s
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
            INSERT INTO transactions
                (user_id, direction, category, amount, description, transaction_date, payment_mode, joy_index)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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
            SELECT t.id, t.direction, t.category, t.amount, t.description, t.transaction_date,
                   t.payment_mode, t.joy_index
            FROM transactions t
            JOIN users u ON u.id = t.user_id
            WHERE u.username = %s
            ORDER BY t.transaction_date DESC, t.id DESC
            """
    fallback = """
            SELECT t.id, t.direction, t.category, t.amount, t.description, t.transaction_date
            FROM transactions t
            JOIN users u ON u.id = t.user_id
            WHERE u.username = %s
            ORDER BY t.transaction_date DESC, t.id DESC
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
            UPDATE transactions
            SET direction = %s,
                category = %s,
                amount = %s,
                description = %s,
                transaction_date = %s,
                payment_mode = %s,
                joy_index = %s
            WHERE id = %s AND user_id = %s
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
            "DELETE FROM transactions WHERE id = %s AND user_id = %s",
            (record_id, user["id"]),
        )
        connection.commit()
        cursor.close()
        connection.close()
        return True, None
    except Exception as e:
        return False, str(e)


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


def sideb(parent, on_home=None, on_income=None, on_investments=None, on_balance=None, on_analytics=None):
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
    )
    bt4_2 = ctk.CTkButton(
        sidebar,
        width=250,
        height=50,
        fg_color="#444444",
        hover_color="#00A998",
        text="   Long Term",
        text_color="white",
        anchor="w",
        font=("Calibri", 16),
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
        build_investments(holder)

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

    sideb(
        fra,
        on_home=show_dashboard,
        on_income=show_income,
        on_investments=show_investments,
        on_balance=show_balance,
        on_analytics=show_analytics,
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
