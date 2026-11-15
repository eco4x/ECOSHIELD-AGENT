"""Initialize the shared ECOSHIELD demo employee database."""
import os
import sqlite3


DEFAULT_EMPLOYEES = (
    ("Alice Vance", "Finance"),
    ("Marcus Ward", "Human Resources"),
    ("Sarah Connor", "IT Operations"),
)


def setup_vault():
    db_path = os.environ.get("ECOSHIELD_DB_PATH", "ecoshield.db")
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY,
                name TEXT,
                department TEXT,
                risk_score INTEGER DEFAULT 0,
                status TEXT DEFAULT 'Secure'
            )
            """
        )
        for name, department in DEFAULT_EMPLOYEES:
            cursor.execute("SELECT 1 FROM employees WHERE name = ? AND department = ? LIMIT 1", (name, department))
            if cursor.fetchone() is None:
                cursor.execute(
                    "INSERT INTO employees (name, department) VALUES (?, ?)",
                    (name, department),
                )
        conn.commit()
    finally:
        conn.close()
    print(f"[+] ECOSHIELD Vault Initialized: {db_path} is ready.")


if __name__ == "__main__":
    setup_vault()
