import sqlite3

def setup_vault():
    # This creates the database file ecoshield.db
    conn = sqlite3.connect('ecoshield.db')
    cursor = conn.cursor()
    
    # Create the table to track employee risk
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY,
            name TEXT,
            department TEXT,
            risk_score INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Secure'
        )
    ''')
    
    # Add your initial 'Targets'
    targets = [
        ('Alice Vance', 'Finance'),
        ('Marcus Ward', 'Human Resources'),
        ('Sarah Connor', 'IT Operations')
    ]
    cursor.executemany('INSERT INTO employees (name, department) VALUES (?, ?)', targets)
    
    conn.commit()
    conn.close()
    print("[+] ECOSHIELD Vault Initialized: ecoshield.db is ready.")

if __name__ == "__main__":
    setup_vault()