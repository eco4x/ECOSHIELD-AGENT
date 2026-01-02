import sqlite3

def draw_dashboard():
    conn = sqlite3.connect('ecoshield.db')
    cursor = conn.cursor()
    cursor.execute("SELECT department, risk_score FROM employees")
    data = cursor.fetchall()
    
    print("\n📊 ECOSHIELD VISUAL RISK DASHBOARD")
    print("="*40)
    
    for dept, score in data:
        # Create a bar using '#' characters
        bar = "#" * (score // 5) 
        print(f"{dept:<15} | {bar:<10} ({score} pts)")
    
    print("="*40)
    print("Green = Secure | Yellow = Warning | Red = LOCKED")
    conn.close()

if __name__ == "__main__":
    draw_dashboard()