import sqlite3
import time

def monitor_and_lock():
    print("[🛡️] Sentinel Active: Monitoring for high-risk behavior...")
    
    while True:
        conn = sqlite3.connect('ecoshield.db')
        cursor = conn.cursor()
        
        # Look for anyone with a risk score >= 50
        cursor.execute("SELECT name, department, risk_score FROM employees WHERE risk_score >= 50 AND status != 'LOCKED'")
        breach_risks = cursor.fetchall()
        
        if breach_risks:
            for name, dept, score in breach_risks:
                print(f"\n[🚨] ALERT: {name} ({dept}) has reached Critical Risk ({score})!")
                print(f"[🔒] AUTOMATION: Locking {dept} network credentials to prevent breach...")
                
                # Update status to LOCKED
                cursor.execute("UPDATE employees SET status = 'LOCKED' WHERE name = ?", (name,))
            
            conn.commit()
        
        conn.close()
        # Wait 5 seconds before checking again (simulating real-time monitoring)
        time.sleep(5)

if __name__ == "__main__":
    try:
        monitor_and_lock()
    except KeyboardInterrupt:
        print("\n[!] Sentinel deactivated.")