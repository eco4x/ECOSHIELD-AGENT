from flask import Flask, render_template_string, request
import sqlite3

app = Flask(__name__)

# Dynamic Branding Engine
BRAND_CONFIG = {
    "finance": {"name": "EcoFinance Bank", "accent": "#2c3e50", "msg": "Suspicious Transaction Alert"},
    "hr": {"name": "EcoHealth Solutions", "accent": "#27ae60", "msg": "Annual Benefits Enrollment"},
    "it": {"name": "EcoTech Systems", "accent": "#2980b9", "msg": "System Maintenance Required"}
}

HTML_LAYOUT = """
<div style="font-family: 'Segoe UI', sans-serif; max-width: 400px; margin: 80px auto; border-top: 8px solid {{accent}}; padding: 30px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); border-radius: 5px;">
    <h1 style="color: #333; font-size: 22px;">🛡️ {{name}}</h1>
    <p style="color: #666; font-size: 14px;"><strong>Notification:</strong> {{msg}}</p>
    <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
    <form method="POST" action="/capture?dept={{dept}}">
        <label style="font-size: 12px; color: #888;">Employee Email</label>
        <input type="text" name="email" placeholder="username@ecotech.com" style="width:100%; padding:10px; margin:5px 0 15px 0; border: 1px solid #ddd; border-radius: 3px;">
        <label style="font-size: 12px; color: #888;">Network Password</label>
        <input type="password" name="password" placeholder="••••••••" style="width:100%; padding:10px; margin:5px 0 20px 0; border: 1px solid #ddd; border-radius: 3px;">
        <button type="submit" style="background:{{accent}}; color:white; border:none; padding:12px; width:100%; border-radius: 3px; cursor:pointer; font-weight: bold;">Secure Sign-In</button>
    </form>
    <p style="text-align:center; font-size: 10px; color: #ccc; margin-top: 20px;">&copy; 2026 EcoTechLabs Security Simulations</p>
</div>
"""

@app.route('/')
def index():
    dept_key = request.args.get('dept', 'it')
    brand = BRAND_CONFIG.get(dept_key, BRAND_CONFIG['it'])
    return render_template_string(HTML_LAYOUT, **brand, dept=dept_key)

@app.route('/capture', methods=['POST'])
def capture():
    dept_target = request.args.get('dept', 'IT Operations')
    conn = sqlite3.connect('ecoshield.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE employees SET risk_score = risk_score + 25, status = 'Compromised' WHERE department LIKE ?", (f'%{dept_target}%',))
    conn.commit()
    conn.close()
    return "<div style='text-align:center; font-family:sans-serif; margin-top:100px;'><h2>🚨 ECOSHIELD AGENT ALERT</h2><p>This was a controlled security test by <b>EcoTechLabs</b>. Please report this to your supervisor.</p></div>"

if __name__ == "__main__":
    app.run(port=5000)