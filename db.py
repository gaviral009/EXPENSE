import os

import mysql.connector

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "123456"),
    "database": os.getenv("MYSQL_DATABASE", "expense_tracker"),
}


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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
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
