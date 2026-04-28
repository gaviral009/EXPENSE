import customtkinter as ctk
from PIL import Image
import mysql.connector
from mysql.connector import Error
import os
import re
import hashlib
import secrets
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
import os
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": "expense_tracker",
}
def _asset_path(filename):
    return os.path.join(BASE_DIR, filename)
def _get_connection(include_database=True):
    config = DB_CONFIG.copy()
    if not include_database:
        config.pop("database", None)
    return mysql.connector.connect(**config)
def _init_database():
    try:
        connection = _get_connection(include_database=False)
        cursor = connection.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
        cursor.close()
        connection.close()
        connection = _get_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) NOT NULL UNIQUE,
                salt VARCHAR(64) NOT NULL,
                password_hash VARCHAR(64) NOT NULL
            )
            """
        )
        connection.commit()
        cursor.close()
        connection.close()
        return True
    except Exception as e:
        print("CREATE USER ERROR ❌:", e)
        return False
def _get_user(username):
    try:
        connection = _get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT username, salt, password_hash FROM users WHERE username = %s",
            (username,),
        )
        user = cursor.fetchone()
        cursor.close()
        connection.close()
        return user
    except Exception as e:
        print("CREATE USER ERROR ❌:", e)
        return False
def _create_user(username, salt, password_hash):
    try:
        connection = _get_connection()
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
        print("CREATE USER ERROR ❌:", e)
        return False
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
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
root = ctk.CTk()
root.title("Expense Tracker")
def center(win, width, height):
    win.update_idletasks()
    screen_width = win.winfo_screenwidth()
    screen_height = win.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    win.geometry(f"{width}x{height}+{x}+{y}")
center(root, 1524, 784)
logo_img = ctk.CTkImage(Image.open(_asset_path("final logo.png")), size=(222, 87))
def _clear_root():
    for child in root.winfo_children():
        child.destroy()
def build_auth_screen():
    _clear_root()
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
        record = _get_user(user_value)
        if not record or not _verify_password(password_value, record["salt"], record["password_hash"]):
            login_status.configure(text="Invalid username or password.", text_color="#ff6b6b")
            return
        build_dashboard(user_value)
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
        if password_value != confirm_value:
            signup_status.configure(text="Passwords do not match.", text_color="#ff6b6b")
            return
        err = _validate_password(password_value)
        if err:
            signup_status.configure(text=err, text_color="#ff6b6b")
            return
        if _get_user(user_value):
            signup_status.configure(text="Username already exists.", text_color="#ff6b6b")
            return
        salt, digest = _hash_password(password_value)
        if not _create_user(user_value, salt, digest):
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
def build_dashboard(username_value):
    _clear_root()
    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(0, weight=1)
    fra = ctk.CTkFrame(root)
    fra.grid(row=0, column=0, sticky="nsew")
    fra.grid_columnconfigure(0, weight=0)
    fra.grid_columnconfigure(1, weight=1)
    fra.grid_rowconfigure(0, weight=1)
    trykare = ctk.CTkImage(dark_image=Image.open(_asset_path("wave.jpeg")), size=(1274, 784))
    icon1 = ctk.CTkImage(dark_image=Image.open(_asset_path("icon1.png")))
    icon2 = ctk.CTkImage(dark_image=Image.open(_asset_path("icon2.png")))
    icon3 = ctk.CTkImage(dark_image=Image.open(_asset_path("icon3.png")))
    icon4 = ctk.CTkImage(dark_image=Image.open(_asset_path("icon4.png")))
    icon5 = ctk.CTkImage(dark_image=Image.open(_asset_path("icon5.png")))
    wel = ctk.CTkImage(dark_image=Image.open(_asset_path("Welc.png")), size=(321, 179))
    intro = ctk.CTkFrame(fra, width=1274, height=784, fg_color="transparent", bg_color="transparent")
    intro.grid(row=0, column=1, sticky="nsew")
    label = ctk.CTkLabel(intro, image=trykare, text="")
    label.place(relx=0, rely=0, relheight=1, relwidth=1)
    act = ctk.CTkFrame(intro, width=1174, height=684)
    act.place(x=50, y=50)
    hi = ctk.CTkLabel(
        act,
        text=f"Hi {username_value}!",
        text_color="#D7D7D7",
        font=("Segoe UI", 40),
        fg_color="transparent",
        bg_color="transparent",
    )
    hi.place(x=50, y=20)
    wlc = ctk.CTkLabel(act, image=wel, text="", fg_color="transparent", bg_color="transparent")
    wlc.place(x=400, y=100)
    bal = ctk.CTkButton(
        act,
        width=300,
        height=100,
        fg_color="#510000",
        text="Balance:\n₹0.00",
        text_color="white",
        font=("Calibri", 30),
        hover_color="#C00000",
        border_color="#D7D7D7",
        border_width=1,
    )
    bal.place(x=80, y=300)
    inc = ctk.CTkButton(
        act,
        width=300,
        height=100,
        fg_color="#002E05",
        text="Income:\n₹0.00",
        text_color="white",
        font=("Calibri", 30),
        hover_color="#006B0E",
        border_color="#D7D7D7",
        border_width=1,
    )
    inc.place(x=430, y=300)
    exp = ctk.CTkButton(
        act,
        width=300,
        height=100,
        fg_color="#001036",
        text="Expense:\n₹0.00",
        text_color="white",
        font=("Calibri", 30),
        hover_color="#001F66",
        border_color="#D7D7D7",
        border_width=1,
    )
    exp.place(x=780, y=300)
    sidebar = ctk.CTkFrame(fra, width=250, fg_color="#202020")
    sidebar.grid(row=0, column=0, sticky="nsw")
    sidebar.grid_propagate(False)
    ctk.CTkLabel(sidebar, fg_color="#202020", width=250, height=200, text="", image=logo_img).grid(row=0, column=0)
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
    )
    state = {"visible": False}

    def showextra():
        if not state["visible"]:
            bt4_1.grid(row=5, column=0, sticky="w")
            bt4_2.grid(row=6, column=0, sticky="w")
            bt5.grid_configure(row=7)
            bt4.configure(text="Budget                        ▼")
            state["visible"] = True
        else:
            bt4_1.grid_forget()
            bt4_2.grid_forget()
            bt5.grid_configure(row=5)
            bt4.configure(text="Budget                        ▶")
            state["visible"] = False

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
    bt1.grid(row=1, column=0)
    bt2.grid(row=2, column=0)
    bt3.grid(row=3, column=0)
    bt4.grid(row=4, column=0)
    bt5.grid(row=5, column=0)
    def on_enter(event):
        event.widget.configure(text_color="black", fg_color="#00A998")
    def on_leave(event):
        event.widget.configure(text_color="white")
        if event.widget in (bt4_1, bt4_2):
            event.widget.configure(fg_color="#444444")
        else:
            event.widget.configure(fg_color="#202020")
    for button in (bt1, bt2, bt3, bt4, bt5, bt4_1, bt4_2):
        button.bind("<Enter>", on_enter)
        button.bind("<Leave>", on_leave)
if not _init_database():
    print("MySQL connection failed. Check DB_CONFIG and make sure MySQL is running.")
build_auth_screen()
root.mainloop()
