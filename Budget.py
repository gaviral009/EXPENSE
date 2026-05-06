import datetime as dt
import sqlite3
import threading
from decimal import Decimal, InvalidOperation
from tkinter import messagebox

import customtkinter as ctk


DATABASE_FILE = "expense_tracker.db"

COLORS = {
    "bg": "#0f172a",
    "panel": "#111827",
    "card": "#1f2937",
    "input": "#0b1220",
    "border": "#334155",
    "text": "#f8fafc",
    "muted": "#94a3b8",
    "blue": "#2563eb",
    "blue_hover": "#1d4ed8",
    "red": "#ef4444",
    "red_hover": "#dc2626",
    "green": "#22c55e",
    "yellow": "#facc15",
}


def get_db_connection():
    return sqlite3.connect(DATABASE_FILE)


def create_balance_table():
    query = """
        CREATE TABLE IF NOT EXISTS balance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT,
            type TEXT NOT NULL,
            date TEXT NOT NULL
        )
    """

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(query)
        connection.commit()
    except sqlite3.Error as err:
        messagebox.showerror("Database Error", f"Could not create balance table:\n{err}")
    finally:
        if "connection" in locals():
            connection.close()


def insert_balance_record(username, amount, description, record_type, record_date):
    query = """
        INSERT INTO balance (username, amount, description, type, date)
        VALUES (?, ?, ?, ?, ?)
    """

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            query,
            (
                username,
                float(amount),
                description,
                record_type,
                record_date.strftime("%Y-%m-%d"),
            ),
        )
        connection.commit()
        return True, None
    except sqlite3.Error as err:
        return False, str(err)
    finally:
        if "connection" in locals():
            connection.close()


def fetch_balance_records(username):
    query = """
        SELECT id, amount, description, type, date
        FROM balance
        WHERE username = ?
        ORDER BY date DESC, id DESC
    """

    try:
        connection = get_db_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        cursor.execute(query, (username,))
        return cursor.fetchall()
    except sqlite3.Error as err:
        messagebox.showerror("Database Error", f"Could not fetch records:\n{err}")
        return []
    finally:
        if "connection" in locals():
            connection.close()


def delete_balance_record(record_id, username):
    query = """
        DELETE FROM balance
        WHERE id = ? AND username = ?
    """

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute(query, (record_id, username))
        connection.commit()
        return True, None
    except sqlite3.Error as err:
        return False, str(err)
    finally:
        if "connection" in locals():
            connection.close()


def fetch_balance_totals(username):
    query = """
        SELECT
            COALESCE(SUM(CASE WHEN type = 'You owe' THEN amount ELSE 0 END), 0) AS total_you_owe,
            COALESCE(SUM(CASE WHEN type = 'You are owed' THEN amount ELSE 0 END), 0) AS total_you_are_owed
        FROM balance
        WHERE username = ?
    """

    try:
        connection = get_db_connection()
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        cursor.execute(query, (username,))
        row = cursor.fetchone()

        total_you_owe = Decimal(str(row["total_you_owe"] or 0))
        total_you_are_owed = Decimal(str(row["total_you_are_owed"] or 0))
        net_balance = total_you_are_owed - total_you_owe

        return total_you_owe, total_you_are_owed, net_balance
    except sqlite3.Error as err:
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
        record_date = record["date"]
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


if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")

    app = ctk.CTk()
    app.title("Expense Tracker - Balance Management")
    app.geometry("1100x650")
    app.minsize(900, 560)

    logged_in_username = "demo_user"

    frame = BalanceManagementFrame(app, logged_in_username)
    frame.pack(fill="both", expand=True)

    app.mainloop()
