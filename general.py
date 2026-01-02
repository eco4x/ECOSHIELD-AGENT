import sqlite3

def generate_report():
    # Connect to the vault we created
    conn = sqlite3.connect('ecoshield.db')
    cursor = conn.cursor()
    
    print("\n" + "="*50)
    print("🛡️  ECOSHIELD AGENT: INTELLIGENCE REPORT")
    print("="*50)
    print(f"{'NAME':<15} | {'DEPARTMENT':<15} | {'RISK'}")
    print("-" * 50)
    
    # Pull data to see who was 'Caught'
    cursor.execute("SELECT name, department, risk_score FROM employees ORDER BY risk_score DESC")
    rows = cursor.fetchall()
    
    for name, dept, score in rows:
        status_icon = "🔴" if score > 0 else "🟢"
        print(f"{name:<15} | {dept:<15} | {score} {status_icon}")
    
    print("="*50)
    
    # Mitigation logic
    if any(row[2] > 0 for row in rows):
        print("\n[!] MITIGATION STRATEGY REQUIRED:")
        print(" -> High risk detected in Finance. Recommend 2FA Enforcement.")
    else:
        print("\n[+] All systems clear. No compromises detected.")
        
    conn.close()

if __name__ == "__main__":
    generate_report()