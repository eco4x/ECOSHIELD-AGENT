from flask import Flask, render_template_string, request, redirect, url_for, Response, jsonify, session
import sqlite3
import os
from io import StringIO
from datetime import datetime
app = Flask(__name__)
app.secret_key = os.environ.get('ECOSHIELD_SECRET_KEY', 'ecoshield-demo-key')

ADMIN_TOKEN = os.environ.get('ECOSHIELD_ADMIN_TOKEN', 'AdminDemo!2026')
CREDENTIALS = {
  'admin': {
    'email': 'admin@ecoshield.local',
    'password': 'AdminDemo!2026',
    'display_name': 'SOC Admin',
    'department': 'Security Operations'
  },
  'employee': {
    'email': 'alice.vance@ecofinance.local',
    'password': 'Hunter22!',
    'display_name': 'Alice Vance',
    'department': 'Finance'
  }
}

SOURCE_INFOS = {
  'Alice Vance': {'ip': '10.1.24.11', 'computer': 'FIN-WKSTN-A1', 'network': 'Finance VLAN'},
  'Marcus Ward': {'ip': '10.2.18.23', 'computer': 'HR-LAP-02', 'network': 'HR Subnet'},
  'Sarah Connor': {'ip': '10.3.10.17', 'computer': 'IT-SRV-08', 'network': 'IT Operations Zone'},
}

LOGIN_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>ECOSHIELD Login</title>
  <style>
    body{margin:0;font-family:Inter,system-ui,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#041017;color:#e9f7ff;display:flex;align-items:center;justify-content:center;height:100vh;}
    .card{background:#0f1f30;border:1px solid rgba(255,255,255,.08);border-radius:24px;padding:32px;width:min(520px,95vw);box-shadow:0 24px 70px rgba(0,0,0,.28);}
    h1{margin-top:0;font-size:2rem;}
    p{color:#8da8c3;line-height:1.6;}
    input{width:100%;padding:14px;border-radius:14px;border:1px solid rgba(255,255,255,.12);background:#07121f;color:#e9f7ff;margin-top:12px;}
    button{width:100%;margin-top:18px;padding:14px;border:none;border-radius:16px;background:linear-gradient(135deg,#39d5e0,#1cc0ff);color:#031922;font-weight:700;cursor:pointer;}
    .hint{background:rgba(255,255,255,.04);padding:14px;border-radius:16px;margin-top:18px;color:#8da8c3;}
    .error{color:#ff8b8b;margin-top:12px;}
  </style>
</head>
<body>
  <div class="card">
    <h1>ECOSHIELD Demo Login</h1>
    <p>Use the dummy credentials below to open a separate admin tab and employee tab for the simulation.</p>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="POST" action="/login">
      <input name="email" placeholder="Email" autocomplete="username" required />
      <input name="password" type="password" placeholder="Password" autocomplete="current-password" required />
      <button type="submit">Sign in</button>
    </form>
    <div class="hint">
      <strong>Admin:</strong> admin@ecoshield.local / AdminDemo!2026<br />
      <strong>Employee:</strong> alice.vance@ecofinance.local / Hunter22!
    </div>
  </div>
</body>
</html>
"""

@app.route('/')
def home():
    if get_current_user():
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        for role, user in CREDENTIALS.items():
            if email == user['email'] and password == user['password']:
                session['user_role'] = role
                session['user_name'] = user['display_name']
                session['department'] = user['department']
                return redirect(url_for('dashboard'))
        error = 'Invalid credentials. Use the demo values shown below.'
    return render_template_string(LOGIN_PAGE, error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    if not get_current_user():
        return redirect(url_for('login'))
    initialize_database()
    ensure_seed_data()
    profiles = get_profiles()
    events = get_latest_events()
    agent_alerts = get_agent_alerts()
    notice_id = request.args.get('notice_id')
    report_success = request.args.get('reported') == '1'
    notice_event = None
    if notice_id:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT * FROM events WHERE id = ?', (notice_id,))
        row = cur.fetchone()
        if row:
            notice_event = dict(row)
            notice_event['details'] = row['details'] + ' Recommended actions: change password, report to admin.'
        conn.close()
    user_role = get_current_user()
    user_profile = get_user_profile()
    template = ADMIN_PAGE if user_role == 'admin' else EMPLOYEE_PAGE
    return render_template_string(template,
        active_events=sum(1 for e in events if e['status'] == 'active'),
        risk_score=current_risk_score(),
        locked_count=calculate_locked_count(),
        traps=TRAP_DEFINITIONS,
        events=events,
        profiles=profiles,
        event_count=get_event_count(),
        incident_summary=get_incident_summary(),
        notice_event=notice_event,
        report_success=report_success,
        user_role=user_role,
        user_name=session.get('user_name'),
        department=session.get('department'),
        admin_token=ADMIN_TOKEN,
        user_profile=user_profile,
        agent_alerts=agent_alerts
    )


@app.route('/trigger', methods=['POST'])
def trigger():
    if not get_current_user():
        return redirect(url_for('login'))
    trap_id = request.form.get('trap_id')
    trap = next((item for item in TRAP_DEFINITIONS if item['id'] == trap_id), None)
    if not trap:
        return redirect(url_for('dashboard'))
    if get_current_user() == 'employee':
        trap = dict(trap)
        trap['user'] = session.get('user_name')
        trap['department'] = session.get('department')
    event_id = add_event(trap)
    update_risk_for_user(trap)
    run_ai_agent_watcher(trap)
    return redirect(url_for('dashboard', notice_id=event_id))

# Admin and employee templates (kept at module top-level)
ADMIN_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>ECOSHIELD Admin Console</title>
  <style>
    body{margin:0;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#041017;color:#e9f7ff;}
    .page{padding:24px;max-width:1400px;margin:0 auto;}
    .card{background:#0f1f30;border:1px solid rgba(255,255,255,.08);border-radius:24px;padding:24px;margin-bottom:18px;}
    .header{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:14px;}
    h1{margin:0;font-size:2.4rem;}
    .metrics{display:grid;grid-template-columns:repeat(4,minmax(180px,1fr));gap:16px;margin-top:18px;}
    .metric{background:rgba(255,255,255,.04);padding:18px;border-radius:20px;}
    .metric strong{display:block;font-size:1.8rem;}
    .button-row{display:flex;flex-wrap:wrap;gap:12px;}
    button{border:none;border-radius:16px;padding:14px 18px;font-weight:700;color:#041922;background:linear-gradient(135deg,#39d5e0,#1cc0ff);cursor:pointer;}
    .event-item{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:18px;padding:18px;margin-bottom:14px;}
    .pill{display:inline-block;padding:10px 14px;border-radius:999px;font-size:.82rem;font-weight:700;}
    .pill.low{background:rgba(84,212,143,.12);color:#5ce2a3;}
    .pill.mid{background:rgba(247,199,74,.14);color:#f7c74e;}
    .pill.high{background:rgba(255,92,122,.14);color:#ff6c6c;}
    .note{background:rgba(255,255,255,.05);padding:18px;border-radius:18px;color:#a7cfe5;margin-top:16px;}
    a.logout{display:inline-block;padding:12px 16px;background:#1f4260;color:#fff;border-radius:14px;text-decoration:none;}
  </style>
</head>
<body>
  <div class="page">
    <div class="card header">
      <div>
        <h1>Admin SOC Console</h1>
        <p style="color:#7ca8c9;margin:8px 0 0;">Logged in as {{ user_name }} · {{ department }}</p>
      </div>
      <div class="button-row">
        <a class="logout" href="/logout">Logout</a>
      </div>
    </div>
    <div class="card metrics">
      <div class="metric"><strong>{{ active_events }}</strong><span>Active incidents</span></div>
      <div class="metric"><strong>—</strong><span>Admin risk</span></div>
      <div class="metric"><strong>{{ locked_count }}</strong><span>Locked accounts</span></div>
      <div class="metric"><strong>{{ event_count }}</strong><span>Total events</span></div>
    </div>
    {% if agent_alerts %}
    <div class="card">
      <h2>🤖 AI Agent Watcher - Automated Alerts</h2>
      <p style="color:#7ca8c9;margin:8px 0 0;">24/7 autonomous defense system. AI agent automatically analyzes incidents, locks risky accounts, and escalates to incident team.</p>
      {% for alert in agent_alerts %}
      <div class="event-item" style="border-left: 4px solid {% if alert.severity == 'CRITICAL' %}#ff6c6c{% elif alert.severity == 'HIGH' %}#f7c74e{% else %}#5ce2a3{% endif %};">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:12px;">
          <div>
            <strong style="color: {% if alert.severity == 'CRITICAL' %}#ff6c6c{% elif alert.severity == 'HIGH' %}#f7c74e{% else %}#5ce2a3{% endif %};">{{ alert.user }}</strong>
            <p style="margin:4px 0 0;color:#7ca8c9;font-size:.9rem;">{{ alert.timestamp }}</p>
          </div>
          <span class="pill {% if alert.severity == 'CRITICAL' %}high{% elif alert.severity == 'HIGH' %}mid{% else %}low{% endif %}">{{ alert.severity }}</span>
        </div>
        <p style="margin:12px 0;color:#c7dfea;"><strong>Action:</strong> {{ alert.action }}</p>
        <p style="margin:12px 0;color:#a7cfe5;"><strong>Analysis:</strong> {{ alert.reason }}</p>
        <div style="margin-top:12px;padding:12px;background:rgba(255,255,255,.03);border-radius:12px;color:#8da8c3;font-size:.95rem;">
          <strong>Isolation:</strong> {{ alert.isolation_details }}<br/>
          <strong>Status:</strong> {{ alert.escalation_status }}
        </div>
      </div>
      {% endfor %}
    </div>
    {% endif %}
    <div class="card">
      <div class="header">
        <div>
          <h2>Phish Investigation Feed</h2>
          <p style="color:#7ca8c9;margin:8px 0 0;">Review where the phish came from, affected user, and quarantine status.</p>
        </div>
        <form method="POST" action="/admin/actions" style="display:flex;gap:12px;flex-wrap:wrap;align-items:center;">
          <input name="admin_token" placeholder="Admin token" autocomplete="off" style="padding:12px 14px;border-radius:14px;border:1px solid rgba(255,255,255,.08);background:#081823;color:#e9f7ff;" />
          <button name="action" value="run_sentinel">Run Sentinel</button>
          <button name="action" value="export_events">Export Logs</button>
        </form>
      </div>
      {% for event in events %}
      <div class="event-item">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:14px;">
          <div>
            <strong>{{ event.title }}</strong>
            <p style="margin:8px 0 0;color:#7ca8c9;">{{ event.user }} · {{ event.timestamp }}</p>
          </div>
          <span class="pill {{ event.level }}">{{ event.level|upper }}</span>
        </div>
        <p style="margin:14px 0 0;color:#c7dfea;">{{ event.details }}</p>
        <div style="margin-top:14px;color:#8da8c3;font-size:.95rem;display:grid;grid-template-columns:repeat(3,minmax(120px,1fr));gap:12px;">
          <span><strong>IP</strong><br />{{ event.source_ip or 'Unknown' }}</span>
          <span><strong>Host</strong><br />{{ event.source_host or 'Unknown' }}</span>
          <span><strong>Network</strong><br />{{ event.source_network or 'Unknown' }}</span>
        </div>
        <div style="margin-top:12px;color:#99bcd9;font-size:.95rem;"><strong>Isolation:</strong> {{ event.source_network or 'Unknown' }} quarantined from the main network for investigation.</div>
      </div>
      {% endfor %}
    </div>
    <div class="card note">
      <strong>Admin guidance:</strong> Use this console to identify the click source, isolate the impacted machine, and coordinate response actions.
    </div>
  </div>
</body>
</html>
"""

EMPLOYEE_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Email Inbox</title>
  <style>
    body{margin:0;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:radial-gradient(circle at top left, rgba(57,213,224,.16), transparent 30%), linear-gradient(180deg, #02101d 0%, #061b2d 100%);color:#e9f7ff;}
    .page{padding:24px;max-width:1000px;margin:0 auto;}
    .header{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:14px;margin-bottom:24px;}
    h1{margin:0;font-size:2rem;}
    a.logout{display:inline-block;padding:10px 14px;background:#1f4260;color:#fff;border-radius:12px;text-decoration:none;font-size:.9rem;}
    .inbox-container{background:#0f1f30;border:1px solid rgba(255,255,255,.06);border-radius:20px;padding:20px;}
    .email-item{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:18px;margin-bottom:14px;cursor:pointer;transition:all .2s ease;}
    .email-item:hover{background:rgba(255,255,255,.08);border-color:rgba(57,213,224,.3);transform:translateX(4px);}
    .email-header{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:12px;}
    .email-from{font-weight:700;color:#39d5e0;}
    .email-subject{color:#e9f7ff;font-weight:600;}
    .email-time{color:#7ca8c9;font-size:.85rem;}
    .email-preview{color:#a7cfe5;font-size:.9rem;margin:12px 0;}
    .attachment{display:inline-block;background:rgba(57,213,224,.12);color:#39d5e0;padding:8px 12px;border-radius:8px;font-size:.85rem;font-weight:600;margin-top:10px;}
    .locked-notice{background:rgba(255,108,108,.12);border:2px solid rgba(255,108,108,.3);border-radius:16px;padding:24px;margin-bottom:24px;color:#ff8b8b;}
    .locked-notice h2{margin-top:0;color:#ff6c6c;}
    .locked-notice p{line-height:1.6;margin:8px 0;}
    .locked-notice strong{color:#ff9999;}
    .awareness-box{background:rgba(255,255,255,.05);border-left:4px solid #39d5e0;border-radius:12px;padding:16px;margin-top:16px;color:#c7dfea;}
    .awareness-box strong{color:#39d5e0;}
    .status-chip{display:inline-block;padding:8px 12px;border-radius:999px;font-size:.85rem;font-weight:700;background:rgba(255,108,108,.14);color:#ff6c6c;}
  </style>
</head>
<body>
  <div class="page">
    <div class="header">
      <div>
        <h1>📧 Email Inbox</h1>
        <p style="color:#7ca8c9;margin:8px 0 0;">{{ user_name }} · {{ department }}</p>
      </div>
      <a class="logout" href="/logout">Logout</a>
    </div>

    {% if user_profile and user_profile.status == 'LOCKED' %}
    <div class="locked-notice">
      <h2>🔒 Account Locked - Security Incident</h2>
      <p><strong>Status:</strong> <span class="status-chip">LOCKED</span></p>
      <p><strong>Risk Score:</strong> {{ user_profile.risk_score }} points (Critical Threshold Exceeded)</p>
      <p><strong>Reason:</strong> Your account was locked after a phishing simulation was triggered. This protective measure prevents unauthorized access to company systems and data.</p>
      <p><strong>What Happened:</strong> You clicked a malicious link or opened a suspicious attachment. The attack successfully captured credentials or established unauthorized access.</p>
      <p><strong>Next Steps:</strong></p>
      <ul style="margin:8px 0;padding-left:20px;">
        <li>Contact your IT/Security team immediately</li>
        <li>Do NOT reuse this password on any other system</li>
        <li>Change your password once account is restored</li>
        <li>Review the security awareness training below</li>
      </ul>
      <div class="awareness-box">
        <strong>🎓 Cyber Awareness Training:</strong>
        <p>Phishing attacks are the #1 cause of data breaches. Attackers use social engineering, urgency, and trust to trick employees. Always:</p>
        <ul style="margin:8px 0;padding-left:20px;">
          <li>Verify sender email addresses carefully</li>
          <li>Hover over links to see the actual destination URL</li>
          <li>Be suspicious of unexpected attachments</li>
          <li>Never share credentials via email or chat</li>
          <li>Report suspicious messages to security@company.local</li>
        </ul>
      </div>
    </div>
    {% else %}
    <div class="inbox-container">
      <p style="color:#7ca8c9;margin-bottom:16px;">You have {{ traps|length }} pending messages:</p>
      {% for trap in traps %}
      <form method="POST" action="/trigger" style="margin:0;">
        <input type="hidden" name="trap_id" value="{{ trap.id }}" />
        <button type="submit" style="background:none;border:none;width:100%;text-align:left;padding:0;cursor:pointer;">
          <div class="email-item">
            <div class="email-header">
              <div>
                <div class="email-from">{{ trap.sender or 'Company Admin' }}</div>
                <div class="email-subject">{{ trap.label }}</div>
                <div class="email-preview">{{ trap.preview or 'Important message - Action required' }}</div>
              </div>
              <div class="email-time">Now</div>
            </div>
            <div class="attachment">📎 Attachment or Link</div>
          </div>
        </button>
      </form>
      {% endfor %}
    </div>
    <div style="margin-top:20px;padding:16px;background:rgba(255,255,255,.04);border-radius:12px;color:#8da8c3;font-size:.9rem;">
      <strong>Inbox Help:</strong> Click any email to open it. This is a security awareness simulation - your responses help train security reflexes. If you click a suspicious link/attachment, your account will be locked as a protective measure.
    </div>
    {% endif %}
  </div>
</body>
</html>
"""

MAIN_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>ECOSHIELD SOC Dashboard</title>
<style>
:root {
  --bg: #041017;
  --panel: #0f1f30;
  --panel-soft: #16304c;
  --text: #e9f7ff;
  --muted: #7ca8c9;
  --accent: #39d5e0;
  --danger: #ff6c6c;
  --warning: #f7c74e;
  --success: #5ce2a3;
  --shadow: 0 24px 70px rgba(0,0,0,.28);
}
*{box-sizing:border-box;}
body{margin:0;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:radial-gradient(circle at top left, rgba(57,213,224,.16), transparent 30%), linear-gradient(180deg, #02101d 0%, #061b2d 100%);color:var(--text);}
.page{padding:24px;max-width:1440px;margin:0 auto;}
header{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-start;gap:18px;margin-bottom:24px;}
h1{margin:0;font-size:clamp(2rem,2.5vw,3rem);letter-spacing:.03em;}
.intro{max-width:760px;color:var(--muted);line-height:1.7;margin-top:12px;}
.grid{display:grid;grid-template-columns:repeat(12,1fr);gap:18px;}
.card{background:var(--panel);border:1px solid rgba(255,255,255,.06);box-shadow:var(--shadow);border-radius:24px;padding:24px;}
.span6{grid-column:span 6;}
.span4{grid-column:span 4;}
.span12{grid-column:span 12;}
.metric{display:flex;justify-content:space-between;align-items:center;gap:16px;}
.metric strong{display:block;font-size:1.3rem;}
.metric span{color:var(--muted);}
.list-item{padding:18px;border-radius:18px;background:rgba(255,255,255,.03);display:grid;grid-template-columns:1fr auto;gap:14px;align-items:center;margin-bottom:14px;}
.pill{padding:8px 14px;border-radius:999px;font-size:.82rem;font-weight:700;letter-spacing:.01em;}
.pill.low{background:rgba(84,212,143,.12);color:var(--success);}
.pill.mid{background:rgba(247,199,74,.14);color:var(--warning);}
.pill.high{background:rgba(255,92,122,.14);color:var(--danger);}
.button-row{display:flex;flex-wrap:wrap;gap:14px;}
.button-row button, .control-button{border:none;border-radius:16px;padding:14px 18px;font-weight:700;cursor:pointer;color:#fff;background:linear-gradient(135deg,var(--accent),#1cc0ff);box-shadow:0 18px 40px rgba(57,213,224,.18);transition:transform .16s ease,filter .16s ease;}
.button-row button:hover, .control-button:hover{transform:translateY(-2px);filter:brightness(1.05);}
.status-chip{padding:10px 14px;border-radius:999px;font-size:.82rem;font-weight:700;}
.status-chip.active{background:rgba(57,213,224,.12);color:var(--accent);}
.status-chip.completed{background:rgba(92,226,163,.14);color:var(--success);}
.status-chip.locked{background:rgba(255,108,108,.14);color:var(--danger);}
.event-list{max-height:520px;overflow:auto;padding-right:4px;}
.event-item{padding:20px;border-radius:20px;border:1px solid rgba(255,255,255,.05);margin-bottom:16px;background:rgba(255,255,255,.03);}
.event-item time{font-size:.82rem;color:var(--muted);display:block;margin-bottom:10px;}
.event-header{display:flex;justify-content:space-between;align-items:center;gap:10px;}
.gauge{position:relative;margin-top:16px;height:16px;border-radius:999px;background:rgba(255,255,255,.06);overflow:hidden;}
.gauge-fill{height:100%;border-radius:999px;background:linear-gradient(90deg,var(--accent),#1bc3ff);}
.control-panel input, .control-panel textarea{width:100%;background:#0e2340;border:1px solid rgba(255,255,255,.08);color:var(--text);border-radius:14px;padding:12px;margin-top:8px;}
.control-panel textarea{resize:none;}
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.72);display:flex;align-items:center;justify-content:center;z-index:20;}
.modal-content{width:min(98vw,640px);background:#0b1624;border-radius:24px;padding:28px;box-shadow:var(--shadow);}
.modal-content h3{margin-top:0;}
.modal-actions{display:flex;flex-wrap:wrap;gap:12px;justify-content:flex-end;margin-top:18px;}
.modal-actions a, .modal-actions button{padding:12px 16px;border-radius:14px;text-decoration:none;font-weight:700;}
.modal-actions a{background:#1f4260;color:#fff;}
@media(max-width:980px){.span6,.span4,.span12{grid-column:span 12;}}
</style>
</head>
<body>
<div class="page">
  <header>
    <div>
      <h1>ECOSHIELD SOC Dashboard</h1>
      <p class="intro">Interactive SOC demo with trap simulation, Vault risk profiles, automatic sentinel response, and demo awareness notes.</p>
    </div>
    <div class="card" style="min-width:280px;">
      <div class="metric"><strong>{{active_events}}</strong><span>Active Traps</span></div>
      <div class="metric"><strong>{{risk_score}}</strong><span>Overall Risk</span></div>
      <div class="metric"><strong>{{locked_count}}</strong><span>Locked Accounts</span></div>
    </div>
  </header>

  <div class="grid">
    <section class="card span6">
      <h2>Trap Simulation</h2>
      <p style="color:var(--muted);margin-bottom:18px;">Trigger a demo phishing trap and watch how the system elevates risk, flags the user, and issues automated sentinel actions.</p>
      <div class="button-row">
        {% for trap in traps %}
          <form method="POST" action="/trigger" style="margin:0;">
            <input type="hidden" name="trap_id" value="{{trap.id}}" />
            <button type="submit">{{trap.label}}</button>
          </form>
        {% endfor %}
      </div>
      <div style="margin-top:24px;">
        <div class="metric"><strong>{{event_count}}</strong><span>Total Simulated Events</span></div>
        <div style="margin-top:14px;">Overall risk gauge</div>
        <div class="gauge"><div class="gauge-fill" style="width:{{risk_score}}%;"></div></div>
      </div>
    </section>

    <section class="card span6">
      <h2>Event Feed</h2>
      <div class="event-list">
        {% for event in events %}
          <article class="event-item">
            <div class="event-header">
              <strong>{{event.title}}</strong>
              <span class="pill {{event.level}}">{{event.level|upper}}</span>
            </div>
            <time>{{event.timestamp}}</time>
            <p>{{event.details}}</p>
            <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;font-size:.9rem;color:var(--muted);">
              <span>{{event.user}}</span>
              <span class="status-chip {{event.status}}">{{event.status}}</span>
            </div>
          </article>
        {% endfor %}
      </div>
    </section>

    <section class="card span4">
      <h2>Vault Profiles</h2>
      {% for profile in profiles %}
        <div class="list-item">
          <div>
            <div><strong>{{profile.name}}</strong> · {{profile.department}}</div>
            <small>{{profile.status}} · {{profile.risk_score}} pts</small>
          </div>
          <span class="pill {{profile.level}}">{{profile.level|upper}}</span>
        </div>
      {% endfor %}
    </section>

    <section class="card span4">
      <h2>Incident Summary</h2>
      <div class="mini-grid">
        <div class="mini-card"><strong>{{incident_summary.highest_risk}}</strong><div style="color:var(--muted);margin-top:8px;">Highest risk</div></div>
        <div class="mini-card"><strong>{{incident_summary.recent_user}}</strong><div style="color:var(--muted);margin-top:8px;">Latest target</div></div>
        <div class="mini-card"><strong>{{incident_summary.actions_taken}}</strong><div style="color:var(--muted);margin-top:8px;">Auto responses</div></div>
      </div>
    </section>

    <section class="card span4">
      <h2>Demo Credentials</h2>
      <div class="list-item" style="grid-template-columns:1fr;">
        <strong>Admin token</strong>
        <span style="color:var(--muted);">AdminDemo!2026</span>
      </div>
      <div class="list-item" style="grid-template-columns:1fr;">
        <strong>Phished user</strong>
        <span style="color:var(--muted);">alice.vance@ecofinance.local</span>
        <span style="color:var(--muted);">Hunter22!</span>
      </div>
      <div class="control-panel" style="margin-top:12px;">
        <form method="POST" action="/admin/actions">
          <input name="admin_token" placeholder="Admin token" autocomplete="off" />
          <div class="button-row" style="margin-top:12px;">
            <button name="action" value="run_sentinel" class="control-button">Run Sentinel</button>
            <button name="action" value="export_events" class="control-button">Export Events</button>
          </div>
        </form>
      </div>
    </section>
  </div>
</div>

{% if notice_event %}
<div class="modal-overlay">
  <div class="modal-content">
    <h3>Security Awareness Notice</h3>
    <p>This simulation is a controlled training environment from EcoTechLabs.</p>
    <p><strong>{{notice_event.user}}</strong> submitted credentials into a phish trap.</p>
    <p>{{notice_event.details}}</p>
    <p style="color:var(--muted);">Recommended actions: change the password, report the event to admin, and do not reuse credentials.</p>
    <form method="POST" action="/api/report">
      <input type="hidden" name="user" value="{{notice_event.user}}" />
      <input type="hidden" name="event_id" value="{{notice_event.id}}" />
      <textarea name="note" placeholder="Optional report note"></textarea>
      <div class="modal-actions">
        <button type="submit" class="control-button">Report to Admin</button>
        <a href="/">Close</a>
      </div>
    </form>
  </div>
</div>
{% endif %}
{% if report_success %}
<div class="modal-overlay">
  <div class="modal-content">
    <h3>Report Submitted</h3>
    <p>Your incident report has been recorded. The SOC team will review it in this demo.</p>
    <div class="modal-actions">
      <a href="/">Close</a>
    </div>
  </div>
</div>
{% endif %}
</body>
</html>
"""

TRAP_DEFINITIONS = [
    {"id": "finance-phish", "label": "Finance Phishing Email", "sender": "finance@bank-update.com", "preview": "Urgent: Verify your account - Click here", "user": "Alice Vance", "department": "Finance", "impact": 18, "event_type": "Credential Harvest"},
    {"id": "hr-benefits", "label": "HR Benefits Alert", "sender": "HR Department", "preview": "New benefits package available - Review document", "user": "Marcus Ward", "department": "Human Resources", "impact": 14, "event_type": "Phishing Click"},
    {"id": "it-maintenance", "label": "IT Maintenance Notice", "sender": "IT Support <support@company.local>", "preview": "Scheduled maintenance - Confirm access", "user": "Sarah Connor", "department": "IT Operations", "impact": 17, "event_type": "Password Entry"},
    {"id": "exec-target", "label": "Executive Fraud Link", "sender": "CEO Office", "preview": "Confidential: Board meeting minutes attached", "user": "Alice Vance", "department": "Finance", "impact": 22, "event_type": "Suspicious Access"},
    {"id": "benefits-update", "label": "Policy Update", "sender": "Compliance Team", "preview": "Updated security policy - Action required", "user": "Marcus Ward", "department": "Human Resources", "impact": 12, "event_type": "Suspicious Link"},
    {"id": "it-alert", "label": "Account Verification", "sender": "Security <security@company.local>", "preview": "Unusual login detected - Verify identity", "user": "Sarah Connor", "department": "IT Operations", "impact": 16, "event_type": "Credential Replay"}
]

EVENT_TEMPLATES = {
    "Credential Harvest": "Dummy credentials were submitted via a deceptive finance form.",
    "Phishing Click": "A user clicked a compromised HR-style link and exposed the session.",
    "Password Entry": "A fake maintenance page captured a login attempt.",
    "Suspicious Access": "An exec-style phishing page triggered a high-risk access event.",
    "Suspicious Link": "A policy update lure generated anomalous user behavior.",
    "Credential Replay": "The page collected and replayed user credentials.",
}

STATUS_COLORS = [(0, "low"), (35, "mid"), (50, "high")]


def get_db_connection():
    conn = sqlite3.connect('ecoshield.db')
    conn.row_factory = sqlite3.Row
    return conn


def get_current_user():
    return session.get('user_role')


def initialize_database():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY,
            name TEXT,
            department TEXT,
            risk_score INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Secure'
        )''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            user TEXT,
            department TEXT,
            trap_id TEXT,
            event_type TEXT,
            impact INTEGER,
            details TEXT,
            status TEXT,
            source_ip TEXT,
            source_host TEXT,
            source_network TEXT
        )''')
    for column in ('source_ip', 'source_host', 'source_network'):
        try:
            cur.execute(f'ALTER TABLE events ADD COLUMN {column} TEXT')
        except sqlite3.OperationalError:
            pass
    cur.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            user TEXT,
            event_id INTEGER,
            note TEXT
        )''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS agent_actions (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            user TEXT,
            action TEXT,
            reason TEXT,
            severity TEXT,
            escalation_status TEXT,
            isolation_details TEXT
        )''')
    conn.commit()
    conn.close()


def ensure_seed_data():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM employees")
    if cur.fetchone()[0] == 0:
        targets = [
            ('Alice Vance', 'Finance'),
            ('Marcus Ward', 'Human Resources'),
            ('Sarah Connor', 'IT Operations'),
        ]
        cur.executemany('INSERT INTO employees (name, department) VALUES (?, ?)', targets)
        conn.commit()
    conn.close()


def score_label(score):
    if score >= 50:
        return 'high'
    if score >= 35:
        return 'mid'
    return 'low'


def current_risk_score():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT SUM(risk_score) FROM employees')
    total = cur.fetchone()[0] or 0
    conn.close()
    return min(total, 100)


def calculate_locked_count():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM employees WHERE status = 'LOCKED'")
    count = cur.fetchone()[0]
    conn.close()
    return count


def add_event(trap):
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    details = EVENT_TEMPLATES.get(trap['event_type'], 'Simulated deception activity detected.')
    status = 'active'
    source = SOURCE_INFOS.get(trap['user'], {'ip': '10.0.0.1', 'computer': 'UNKNOWN', 'network': 'Unclassified'})
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO events (timestamp, user, department, trap_id, event_type, impact, details, status, source_ip, source_host, source_network) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (timestamp, trap['user'], trap['department'], trap['id'], trap['event_type'], trap['impact'], details, status, source['ip'], source['computer'], source['network'])
    )
    event_id = cur.lastrowid
    conn.commit()
    conn.close()
    return event_id


def update_risk_for_user(trap):
    if get_current_user() == 'admin':
        return
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT id, risk_score, status FROM employees WHERE name = ?', (trap['user'],))
    row = cur.fetchone()
    if not row:
        cur.execute('INSERT INTO employees (name, department, risk_score) VALUES (?, ?, ?)', (trap['user'], trap['department'], trap['impact']))
        conn.commit()
        conn.close()
        return

    new_score = row['risk_score'] + trap['impact']
    new_status = row['status']
    if new_score >= 50 and row['status'] != 'LOCKED':
        new_status = 'LOCKED'
    elif new_score >= 35 and row['status'] == 'Secure':
        new_status = 'Compromised'
    cur.execute('UPDATE employees SET risk_score = ?, status = ? WHERE id = ?', (new_score, new_status, row['id']))
    conn.commit()
    conn.close()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM employees WHERE status = 'LOCKED'")
    count = cur.fetchone()[0]
    conn.close()
    return count


def run_ai_agent_watcher(trap):
    """AI-assisted agent analyzes trap events 24/7 and takes automated action."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get user's recent activity
    cur.execute('SELECT COUNT(*) FROM events WHERE user = ?', (trap['user'],))
    event_count = cur.fetchone()[0]
    
    cur.execute('SELECT risk_score, status FROM employees WHERE name = ?', (trap['user'],))
    emp_row = cur.fetchone()
    
    if not emp_row:
        conn.close()
        return
    
    risk_score = emp_row['risk_score']
    current_status = emp_row['status']
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    
    # AI Analysis Rules
    action = None
    reason = None
    severity = 'LOW'
    
    # Multiple incidents = high risk pattern
    if event_count >= 3:
        reason = f"Repeated phishing engagement detected ({event_count} incidents in session). Pattern suggests social engineering susceptibility."
        severity = 'HIGH'
        action = 'ALERT_ESCALATE'
    
    # Combined high risk + compromised = critical
    if risk_score >= 50 and current_status == 'LOCKED':
        reason = f"Critical risk threshold exceeded. Risk score: {risk_score} pts. Account locked to prevent lateral movement. Credentials compromised across multiple attack vectors."
        severity = 'CRITICAL'
        action = 'ESCALATE_INCIDENT'
    
    # Medium risk pattern
    elif risk_score >= 35 and event_count >= 2:
        reason = f"Suspicious pattern detected. Risk score: {risk_score} pts. Multiple trap engagements indicate training gap. Recommend enhanced security awareness."
        severity = 'MEDIUM'
        action = 'ALERT_SOC'
    
    # Single high-impact incident
    elif trap['impact'] >= 15 and event_count == 1:
        reason = f"High-impact incident detected: {trap['event_type']}. Immediate security awareness intervention recommended."
        severity = 'MEDIUM'
        action = 'ALERT_SOC'
    
    # Create agent action record if action triggered
    if action:
        source = SOURCE_INFOS.get(trap['user'], {'network': 'Unclassified'})
        isolation_details = f"Isolated from {source['network']} · Access revoked · Credentials flagged"
        escalation_status = 'ESCALATED_TO_SOC' if severity in ['MEDIUM', 'HIGH'] else 'ESCALATED_TO_INCIDENT_TEAM'
        
        cur.execute('''
            INSERT INTO agent_actions (timestamp, user, action, reason, severity, escalation_status, isolation_details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, trap['user'], action, reason, severity, escalation_status, isolation_details))
        conn.commit()
    
    conn.close()


def get_latest_events(limit=12):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM events ORDER BY id DESC LIMIT ?', (limit,))
    rows = cur.fetchall()
    conn.close()
    events = []
    for row in rows:
        events.append({
            'id': row['id'],
            'title': f"{row['event_type']} - {row['department']}",
            'timestamp': row['timestamp'],
            'details': row['details'],
            'user': row['user'],
            'status': row['status'],
            'level': score_label(row['impact']),
            'source_ip': row['source_ip'],
            'source_host': row['source_host'],
            'source_network': row['source_network']
        })
    return events


def get_profiles():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT name, department, risk_score, status FROM employees ORDER BY risk_score DESC')
    rows = cur.fetchall()
    conn.close()
    profiles = []
    for row in rows:
        profiles.append({
            'name': row['name'],
            'department': row['department'],
            'risk_score': row['risk_score'],
            'status': row['status'],
            'level': score_label(row['risk_score'])
        })
    return profiles


def get_event_count():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM events')
    count = cur.fetchone()[0]
    conn.close()
    return count


def get_incident_summary():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT MAX(risk_score) FROM employees')
    highest = cur.fetchone()[0] or 0
    cur.execute('SELECT user FROM events ORDER BY id DESC LIMIT 1')
    latest = cur.fetchone()
    latest_user = latest[0] if latest else 'None'
    cur.execute("SELECT COUNT(*) FROM events WHERE status = 'active'")
    active = cur.fetchone()[0]
    conn.close()
    return {
        'highest_risk': f"{highest} pts",
        'recent_user': latest_user,
        'actions_taken': active
    }


def process_sentinel():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE events SET status = 'completed' WHERE status = 'active'")
    cur.execute("UPDATE employees SET status = 'LOCKED' WHERE risk_score >= 50")
    conn.commit()
    conn.close()


def get_agent_alerts(limit=10):
    """Retrieve AI agent alerts and actions."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM agent_actions ORDER BY id DESC LIMIT ?', (limit,))
    rows = cur.fetchall()
    conn.close()
    alerts = []
    for row in rows:
        alerts.append({
            'id': row['id'],
            'timestamp': row['timestamp'],
            'user': row['user'],
            'action': row['action'],
            'reason': row['reason'],
            'severity': row['severity'],
            'escalation_status': row['escalation_status'],
            'isolation_details': row['isolation_details']
        })
    return alerts


def get_user_profile():
  if get_current_user() != 'employee':
    return None
  name = session.get('user_name')
  conn = get_db_connection()
  cur = conn.cursor()
  cur.execute('SELECT name, department, risk_score, status FROM employees WHERE name = ?', (name,))
  row = cur.fetchone()
  conn.close()
  if not row:
    return {
      'name': name,
      'department': session.get('department'),
      'risk_score': 0,
      'status': 'Secure',
      'level': 'low'
    }
  return {
    'name': row['name'],
    'department': row['department'],
    'risk_score': row['risk_score'],
    'status': row['status'],
    'level': score_label(row['risk_score'])
  }



@app.route('/api/report', methods=['POST'])
def api_report():
    data = request.form or request.json or {}
    user = data.get('user')
    event_id = data.get('event_id')
    note = data.get('note', '')
    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('INSERT INTO reports (timestamp, user, event_id, note) VALUES (?, ?, ?, ?)', (ts, user, event_id, note))
    conn.commit()
    conn.close()
    if request.content_type and 'application/json' in request.content_type:
        return jsonify({'ok': True}), 201
    return redirect(url_for('dashboard', notice_id=event_id, reported='1'))


@app.route('/admin/actions', methods=['POST'])
def admin_actions():
    token = request.form.get('admin_token')
    action = request.form.get('action')
    if token != ADMIN_TOKEN:
        return "Unauthorized (invalid admin token)", 401
    if action == 'run_sentinel':
        process_sentinel()
        return redirect(url_for('dashboard'))
    if action == 'export_events':
        return redirect(url_for('export_events', format='csv'))
    return redirect(url_for('dashboard'))


@app.route('/export')
def export_events():
    fmt = request.args.get('format', 'csv')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM events ORDER BY id DESC')
    rows = cur.fetchall()
    conn.close()
    if fmt == 'json':
        return jsonify([dict(r) for r in rows])
    output = StringIO()
    headers = ['id','timestamp','user','department','trap_id','event_type','impact','details','status']
    output.write(','.join(headers) + '\n')
    for r in rows:
        row = [str(r[h]).replace('"', '""') for h in headers]
        output.write(','.join('"%s"' % v for v in row) + '\n')
    return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=events.csv'})


@app.route('/api/status')
def api_status():
    profiles = get_profiles()
    return jsonify({
        'active_events': sum(1 for e in get_latest_events() if e['status'] == 'active'),
        'risk_score': current_risk_score(),
        'locked_count': calculate_locked_count(),
        'profiles': profiles,
    })


@app.route('/api/events')
def api_events():
    return jsonify(get_latest_events(50))


@app.route('/api/profiles')
def api_profiles():
    return jsonify(get_profiles())


@app.route('/api/ai/analyze', methods=['POST'])
def ai_analyze():
    data = request.json or {}
    events = data.get('events') or []
    if not events:
        return jsonify({'summary': 'No events provided.'})
    highest = max(events, key=lambda e: e.get('impact', 0))
    severity = 'High' if highest.get('impact',0) >= 20 else 'Medium' if highest.get('impact',0) >= 10 else 'Low'
    summary = f"Detected {len(events)} recent events. Highest-impact event: {highest.get('event_type')} targeting {highest.get('user')} (impact {highest.get('impact')}). Severity: {severity}."
    suggestions = [
        'Investigate the highest-impact event and isolate the user session.',
        'Force password reset for the affected account and monitor for lateral activity.',
        'Review the phishing chain and block any malicious senders.'
    ]
    return jsonify({'summary': summary, 'suggestions': suggestions})


if __name__ == '__main__':
    initialize_database()
    ensure_seed_data()
    app.run(host='0.0.0.0', port=5000, debug=True)
