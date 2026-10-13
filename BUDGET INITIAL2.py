import customtkinter as ctk
import mysql.connector
from tkinter import ttk, messagebox
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime
BG, GOLD, TEXT = "#1B1B1F", "#C9A96E", "#F0EDE6"
DB_HOST, DB_USER, DB_PASS, DB_NAME = "localhost", "root", "YOUR_MYSQL_PASSWORD", "tracko"
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")
def connect():
    return mysql.connector.connect(host=DB_HOST, user=DB_USER,
                                   password=DB_PASS, database=DB_NAME)
def setup():
    con = connect()
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS budget (
        category VARCHAR(100) PRIMARY KEY,
        limit_amt DECIMAL(12,2) NOT NULL DEFAULT 0
    )""")
    cur.execute("SHOW COLUMNS FROM ie LIKE 'transaction_type'")
    if not cur.fetchone():
        cur.execute("ALTER TABLE ie ADD COLUMN transaction_type VARCHAR(20) NULL")
    con.commit()
    cur.close()
    con.close()
def money(value):
    return f"₹{float(value):,.2f}"
def read_data():
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT category, limit_amt FROM budget ORDER BY category")
    budgets = {str(c): float(v) for c, v in cur.fetchall()}
    cur.execute("""SELECT cat, amount, date FROM ie
                   WHERE LOWER(COALESCE(transaction_type,''))='expense'""")
    rows = cur.fetchall()
    cur.close()
    con.close()
    spent, dated = {}, []
    for category, amount, date_value in rows:
        category = str(category or "Uncategorised")
        spent[category] = spent.get(category, 0) + float(amount or 0)
        if date_value:
            parsed = None
            if isinstance(date_value, datetime):
                parsed = date_value.date()
            elif hasattr(date_value, "year"):
                parsed = date_value
            else:
                for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
                    try:
                        parsed = datetime.strptime(str(date_value)[:10], fmt).date()
                        break
                    except ValueError:
                        pass
            if parsed:
                dated.append((parsed, float(amount or 0)))
    return budgets, spent, dated
class BudgetApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Tracko | Budget Manager"); self.geometry("1180x760"); self.configure(fg_color=BG)
        ctk.CTkLabel(self, text="TRACKO  /  BUDGET MANAGER",
                     text_color=GOLD, font=("Arial", 24, "bold")).pack(pady=(16, 8))
        top = ctk.CTkFrame(self, fg_color=BG)
        top.pack(fill="x", padx=20)
        self.category = ctk.CTkEntry(top, placeholder_text="Category", width=190)
        self.category.pack(side="left", padx=5, pady=8)
        self.limit = ctk.CTkEntry(top, placeholder_text="Budget limit (₹)", width=190); self.limit.pack(side="left", padx=5, pady=8)
        ctk.CTkButton(top, text="Save / Update Budget", fg_color=GOLD,
                      text_color=BG, command=self.save_budget).pack(side="left", padx=6)
        ctk.CTkButton(top, text="Delete Selected", fg_color="#5A3030",
                      command=self.delete_budget).pack(side="left", padx=6)
        ctk.CTkButton(top, text="Refresh", fg_color="#34343A",
                      command=self.refresh).pack(side="left", padx=6)
        self.table = ttk.Treeview(self, columns=("cat", "limit", "spent", "left", "usage", "status"),
                                  show="headings", height=9)
        headings = [("cat", "Category"), ("limit", "Budget Limit"),
                    ("spent", "Amount Spent"), ("left", "Remaining"),
                    ("usage", "Usage"), ("status", "Status")]
        for key, label in headings:
            self.table.heading(key, text=label)
            self.table.column(key, width=170, anchor="center")
        self.table.pack(fill="x", padx=20, pady=8); self.table.bind("<<TreeviewSelect>>", self.select_row)
        self.graphs = ctk.CTkFrame(self, fg_color=BG)
        self.graphs.pack(fill="both", expand=True, padx=12, pady=6)
        setup()
        self.refresh()
    def save_budget(self):
        category = self.category.get().strip()
        try:
            limit = float(self.limit.get())
            if not category or limit < 0:
                raise ValueError
            con = connect()
            cur = con.cursor()
            cur.execute("""INSERT INTO budget(category, limit_amt) VALUES(%s,%s)
                ON DUPLICATE KEY UPDATE limit_amt=VALUES(limit_amt)""", (category, limit))
            con.commit()
            cur.close()
            con.close()
            self.category.delete(0, "end"); self.limit.delete(0, "end"); self.refresh()
        except ValueError:
            messagebox.showerror("Invalid input", "Enter a category and a non-negative budget.")
        except Exception as e:
            messagebox.showerror("Database error", str(e))
    def select_row(self, _event=None):
        selected = self.table.selection()
        if selected:
            values = self.table.item(selected[0], "values")
            self.category.delete(0, "end")
            self.category.insert(0, values[0])
            self.limit.delete(0, "end")
            self.limit.insert(0, values[1].replace("₹", "").replace(",", ""))
    def delete_budget(self):
        selected = self.table.selection()
        if not selected:
            messagebox.showinfo("Select a row", "Select a budget row first.")
            return
        category = self.table.item(selected[0], "values")[0]
        try:
            con = connect()
            cur = con.cursor()
            cur.execute("DELETE FROM budget WHERE category=%s", (category,))
            con.commit()
            cur.close(); con.close(); self.refresh()
        except Exception as e:
            messagebox.showerror("Database error", str(e))
    def refresh(self):
        try:
            budgets, spent, dated = read_data()
            for item in self.table.get_children(): self.table.delete(item)
            categories = sorted(set(budgets) | set(spent))
            total_limit = sum(budgets.values())
            total_spent = sum(spent.values())
            for category in categories:
                limit, amount = budgets.get(category, 0), spent.get(category, 0)
                remaining = limit - amount
                usage = amount / limit * 100 if limit else (100 if amount else 0)
                status = "Over budget" if amount > limit and limit else (
                    "No budget set" if not limit else "Near limit" if usage >= 90 else "On track")
                self.table.insert("", "end", values=(
                    category, money(limit), money(amount), money(remaining),
                    f"{usage:.1f}%", status))
            self.draw_graphs(budgets, spent, dated)
            if total_limit and total_spent / total_limit >= 0.9:
                messagebox.showwarning("Budget alert", "Total spending has reached 90% of total budget.")
        except Exception as e:
            messagebox.showerror("Could not load budget", str(e))
    def draw_graphs(self, budgets, spent, dated):
        for child in self.graphs.winfo_children(): child.destroy()
        fig = Figure(figsize=(10.0, 3.4), dpi=90, facecolor=BG)
        pie = fig.add_subplot(121)
        line = fig.add_subplot(122)
        pie.set_facecolor(BG)
        line.set_facecolor(BG)
        values = [(c, v) for c, v in spent.items() if v > 0]
        if values:
            pie.pie([v for _, v in values],
                    labels=[c for c, _ in values], autopct="%1.0f%%",
                    textprops={"color": TEXT, "fontsize": 8},
                    wedgeprops={"edgecolor": BG, "linewidth": 1})
            pie.set_title("Expense Distribution", color=GOLD, pad=10)
        else:
            pie.text(.5, .5, "No expense data", color=TEXT, ha="center", va="center")
            pie.set_title("Expense Distribution", color=GOLD)
        if dated:
            daily = {}
            for day, amount in dated:
                daily[day] = daily.get(day, 0) + amount
            running, dates, totals = 0, [], []
            for day in sorted(daily):
                running += daily[day]
                dates.append(day)
                totals.append(running)
            line.plot(dates, totals, marker="o", linewidth=2, color=GOLD)
            line.tick_params(axis="x", colors=TEXT, labelrotation=25, labelsize=7)
            line.tick_params(axis="y", colors=TEXT, labelsize=8)
            line.set_title("Cumulative Spending Over Time", color=GOLD, pad=10)
            line.set_ylabel("Amount (₹)", color=TEXT)
            line.grid(alpha=.18)
        else:
            line.text(.5, .5, "No dated expense data", color=TEXT, ha="center", va="center")
            line.set_title("Cumulative Spending Over Time", color=GOLD)
        for ax in (pie, line):
            for spine in ax.spines.values(): spine.set_color("#44444A")
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=self.graphs)
        canvas.draw(); canvas.get_tk_widget().pack(fill="both", expand=True)
if __name__ == "__main__":
    try:
        app = BudgetApp()
        app.mainloop()
    except Exception as error:
        messagebox.showerror("Tracko startup error", str(error))
