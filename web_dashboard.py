from flask import Flask, render_template_string, request, redirect, url_for, Response, jsonify, session
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from functools import wraps
import hmac
import sqlite3
import os
from io import StringIO
from datetime import datetime, timedelta
from assessment_engine import (
    initialize_assessment_schema, create_campaign, activate_due_campaigns,
    list_campaigns, list_employee_assignments, record_interaction,
    complete_learning, scenario_options, campaign_report,
)
app = Flask(__name__)
secret_key = os.environ.get('ECOSHIELD_SECRET_KEY', '')
required_credentials = {
    'ECOSHIELD_ADMIN_EMAIL': os.environ.get('ECOSHIELD_ADMIN_EMAIL', '').strip().lower(),
    'ECOSHIELD_ADMIN_PASSWORD': os.environ.get('ECOSHIELD_ADMIN_PASSWORD', ''),
    'ECOSHIELD_EMPLOYEE_EMAIL': os.environ.get('ECOSHIELD_EMPLOYEE_EMAIL', '').strip().lower(),
    'ECOSHIELD_EMPLOYEE_PASSWORD': os.environ.get('ECOSHIELD_EMPLOYEE_PASSWORD', ''),
}
missing_settings = [name for name, value in required_credentials.items() if not value]
if not secret_key or len(secret_key) < 32:
    missing_settings.append('ECOSHIELD_SECRET_KEY (at least 32 characters)')
if missing_settings:
    raise RuntimeError('Missing or invalid required security settings: ' + ', '.join(missing_settings))
if len(required_credentials['ECOSHIELD_ADMIN_PASSWORD']) < 12 or len(required_credentials['ECOSHIELD_EMPLOYEE_PASSWORD']) < 12:
    raise RuntimeError('Admin and employee passwords must each be at least 12 characters.')

app.config.update(
    SECRET_KEY=secret_key,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('ECOSHIELD_COOKIE_SECURE', 'true').lower() == 'true',
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
    SESSION_REFRESH_EACH_REQUEST=True,
)
csrf = CSRFProtect(app)
limiter = Limiter(key_func=get_remote_address, app=app, default_limits=[])

CREDENTIALS = {
    'admin': {
        'email': required_credentials['ECOSHIELD_ADMIN_EMAIL'],
        'password': required_credentials['ECOSHIELD_ADMIN_PASSWORD'],
        'display_name': 'Readiness Admin',
        'department': 'Security Operations'
    },
    'employee': {
        'email': required_credentials['ECOSHIELD_EMPLOYEE_EMAIL'],
        'password': required_credentials['ECOSHIELD_EMPLOYEE_PASSWORD'],
        'display_name': 'Alice Vance',
        'department': 'Finance'
    }
}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('user_role'):
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get('user_role') != 'admin':
            if request.path.startswith('/api/'):
                status = 401 if not session.get('user_role') else 403
                return jsonify({'error': 'Administrator access required'}), status
            return ('Administrator access required', 401 if not session.get('user_role') else 403)
        return view(*args, **kwargs)
    return wrapped


@app.after_request
def add_security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
    return response

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
    <p>Sign in with the account credentials configured by the system administrator.</p>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="POST" action="/login">
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />
      <input name="email" placeholder="Email" autocomplete="username" required />
      <input name="password" type="password" placeholder="Password" autocomplete="current-password" required />
      <button type="submit">Sign in</button>
    </form>
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
@limiter.limit('5 per minute')
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        for role, user in CREDENTIALS.items():
            if hmac.compare_digest(email, user['email']) and hmac.compare_digest(password, user['password']):
                session.clear()
                session.permanent = True
                session['user_role'] = role
                session['user_name'] = user['display_name']
                session['department'] = user['department']
                return redirect(url_for('dashboard'))
        error = 'Invalid email or password.'
    return render_template_string(LOGIN_PAGE, error=error)


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    initialize_database()
    ensure_seed_data()
    assessment_conn = get_db_connection()
    activate_due_campaigns(assessment_conn)
    campaigns = list_campaigns(assessment_conn)
    assignments = list_employee_assignments(assessment_conn, session.get('user_name')) if get_current_user() == 'employee' else []
    assessment_conn.close()
    profiles = get_profiles()
    events = get_latest_events()
    agent_alerts = get_agent_alerts()
    notice_id = request.args.get('notice_id')
    report_success = request.args.get('reported') == '1'
    notice_event = None
    user_role = get_current_user()
    if notice_id:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT * FROM events WHERE id = ?', (notice_id,))
        row = cur.fetchone()
        if row and (user_role == 'admin' or row['user'] == session.get('user_name')):
            notice_event = dict(row)
            notice_event['details'] = row['details'] + ' Recommended actions: report the simulation and review the linked learning guidance.'
        conn.close()
    user_profile = get_user_profile()
    template = ADMIN_PAGE if user_role == 'admin' else EMPLOYEE_PAGE
    return render_template_string(template,
        active_events=sum(1 for e in events if e['status'] == 'active'),
        risk_score=current_risk_score(),
        review_count=calculate_review_count(),
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
        user_profile=user_profile,
        agent_alerts=agent_alerts,
        campaigns=campaigns,
        assignments=assignments,
        scenario_options=scenario_options()
    )


@app.route('/campaigns/create', methods=['POST'])
@admin_required
def campaign_create():
    initialize_database()
    ensure_seed_data()
    conn = get_db_connection()
    try:
        create_campaign(
            conn,
            request.form.get('name', ''),
            request.form.get('department', ''),
            request.form.get('scenario_key', ''),
            request.form.get('scheduled_at', ''),
            session.get('user_name'),
            os.environ.get('ECOSHIELD_TIMEZONE', 'Africa/Kampala'),
            request.form.get('retest_of_campaign_id') or None,
        )
    except ValueError as exc:
        conn.close()
        return str(exc), 400
    conn.close()
    return redirect(url_for('dashboard'))


@app.route('/campaigns/<int:campaign_id>/report')
@admin_required
def campaign_report_view(campaign_id):
    conn = get_db_connection()
    try:
        report = campaign_report(conn, campaign_id)
    except LookupError:
        conn.close()
        return 'Campaign not found', 404
    conn.close()
    return render_template_string("""
    <!doctype html>
    <html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Campaign readiness report · ECOSHIELD</title>
    <style>
      body{margin:0;padding:24px;background:#041017;color:#e9f7ff;font-family:Inter,system-ui,sans-serif}
      main{max-width:900px;margin:0 auto}.card{background:#0f1f30;border:1px solid #26394b;border-radius:18px;padding:22px;margin:16px 0}
      .metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px}
      .metric{background:#162b40;padding:16px;border-radius:12px}.metric strong{display:block;font-size:1.6rem}
      p,small{color:#a7cfe5;line-height:1.5}a{color:#39d5e0}
      table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:12px;border-bottom:1px solid #26394b}
    </style></head><body><main>
      <p><a href="{{ url_for('dashboard') }}">← Back to dashboard</a></p>
      <section class="card">
        <h1>{{ report.campaign.name }}</h1>
        <p>{{ report.campaign.department }} · {{ report.campaign.scenario_key }} · {{ report.campaign.status }}</p>
        <p>This report uses aggregate training-simulation outcomes. It does not indicate compromise or measure real-world breach probability.</p>
      </section>
      <section class="card">
        <h2>Campaign outcomes</h2>
        <div class="metrics">
          <div class="metric"><strong>{{ report.metrics.assigned_count }}</strong><small>Assigned</small></div>
          <div class="metric"><strong>{{ report.metrics.completed_count }}</strong><small>Responses completed</small></div>
          <div class="metric"><strong>{{ report.metrics.clicked_count }}</strong><small>Clicked</small></div>
          <div class="metric"><strong>{{ report.metrics.reported_count }}</strong><small>Reported</small></div>
          <div class="metric"><strong>{{ report.metrics.ignored_count }}</strong><small>Ignored</small></div>
          <div class="metric"><strong>{{ report.metrics.learning_completion_rate }}%</strong><small>Learning completion</small></div>
        </div>
      </section>
      {% if report.comparison %}
      <section class="card">
        <h2>Change since baseline</h2>
        <p>Baseline: {{ report.comparison.baseline_campaign_name }}</p>
        <table>
          <tr><th>Measure</th><th>Baseline</th><th>Retest</th><th>Change</th></tr>
          <tr><td>Click rate</td><td>{{ report.baseline_metrics.click_rate }}%</td><td>{{ report.metrics.click_rate }}%</td><td>{{ report.comparison.click_rate_change_pp }} percentage points</td></tr>
          <tr><td>Report rate</td><td>{{ report.baseline_metrics.report_rate }}%</td><td>{{ report.metrics.report_rate }}%</td><td>{{ report.comparison.report_rate_change_pp }} percentage points</td></tr>
          <tr><td>Learning completion</td><td>{{ report.baseline_metrics.learning_completion_rate }}%</td><td>{{ report.metrics.learning_completion_rate }}%</td><td>{{ report.comparison.learning_completion_change_pp }} percentage points</td></tr>
        </table>
        <p>A lower click rate and higher report rate can indicate improvement in this exercise. Interpret results in context and avoid using them to shame individual employees.</p>
      </section>
      {% else %}
      <section class="card"><h2>Baseline campaign</h2><p>This campaign has no linked baseline. Complete it, then create a retest using the same audience and scenario to compare results.</p></section>
      {% endif %}
    </main></body></html>
    """, report=report)


@app.route('/assessments/<int:assignment_id>/respond', methods=['POST'])
@login_required
def assessment_respond(assignment_id):
    if get_current_user() != 'employee':
        return 'Employee access required', 403
    conn = get_db_connection()
    try:
        record_interaction(conn, assignment_id, session.get('user_name'), request.form.get('interaction', ''))
    except (ValueError, LookupError) as exc:
        conn.close()
        return str(exc), 400
    conn.close()
    return redirect(url_for('dashboard'))


@app.route('/assessments/<int:assignment_id>/learning-complete', methods=['POST'])
@login_required
def learning_complete(assignment_id):
    if get_current_user() != 'employee':
        return 'Employee access required', 403
    conn = get_db_connection()
    try:
        complete_learning(conn, assignment_id, session.get('user_name'))
    except LookupError as exc:
        conn.close()
        return str(exc), 404
    conn.close()
    return redirect(url_for('dashboard'))


@app.route('/trigger', methods=['POST'])
@login_required
def trigger():
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
    run_rule_watcher(trap)
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
    a.logout,button.logout{display:inline-block;padding:12px 16px;background:#1f4260;color:#fff;border:0;border-radius:14px;text-decoration:none;cursor:pointer;}
  </style>
</head>
<body>
  <div class="page">
    <div class="card header">
      <div>
        <h1>Security Readiness Workspace</h1>
        <p style="color:#7ca8c9;margin:8px 0 0;">Logged in as {{ user_name }} · {{ department }}</p>
      </div>
      <div class="button-row">
        <form method="POST" action="/logout" style="display:inline;margin:0;">
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}" /><button class="logout" type="submit">Logout</button></form>
      </div>
    </div>
    <div class="card metrics">
      <div class="metric"><strong>{{ active_events }}</strong><span>Active demo events</span></div>
      <div class="metric"><strong>{{ campaigns|length }}</strong><span>Campaigns</span></div>
      <div class="metric"><strong>{{ review_count }}</strong><span>Profiles needing review</span></div>
      <div class="metric"><strong>{{ event_count }}</strong><span>Total events</span></div>
    </div>
    <div class="card">
      <h2>Campaign planner</h2>
      <p style="color:#7ca8c9;">Schedule a controlled assessment for a team. Due campaigns are activated by the lightweight scheduler. Employee interactions are recorded as training signals only.</p>
      <form method="POST" action="/campaigns/create" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;align-items:end;">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />
        <label>Campaign name<input name="name" maxlength="80" required placeholder="November security check" style="display:block;width:100%;padding:12px;margin-top:6px;border-radius:10px;" /></label>
        <label>Audience<select name="department" required style="display:block;width:100%;padding:12px;margin-top:6px;border-radius:10px;"><option>All teams</option><option>Finance</option><option>Human Resources</option><option>IT Operations</option></select></label>
        <label>Scenario<select name="scenario_key" required style="display:block;width:100%;padding:12px;margin-top:6px;border-radius:10px;">{% for scenario in scenario_options %}<option value="{{ scenario.key }}">{{ scenario.title }}</option>{% endfor %}</select></label>
        <label>Retest baseline (optional)<select name="retest_of_campaign_id" style="display:block;width:100%;padding:12px;margin-top:6px;border-radius:10px;"><option value="">New baseline campaign</option>{% for campaign in campaigns %}{% if campaign.status == 'completed' %}<option value="{{ campaign.id }}">{{ campaign.name }} · {{ campaign.department }} · {{ campaign.scenario_key }}</option>{% endif %}{% endfor %}</select></label>
        <label>Schedule (Kampala time)<input type="datetime-local" name="scheduled_at" required style="display:block;width:100%;padding:12px;margin-top:6px;border-radius:10px;" /></label>
        <button type="submit">Schedule assessment</button>
      </form>
      <h3 style="margin-top:24px;">Campaign activity</h3>
      {% for campaign in campaigns %}
        <div class="event-item">
          <strong>{{ campaign.name }}</strong> · {{ campaign.department }} · {{ campaign.scenario_key }}
          <p style="color:#7ca8c9;margin:8px 0;">{{ campaign.scheduled_at }} UTC · Status: {{ campaign.status }}</p>
          <p style="color:#a7cfe5;margin:0;">Assigned: {{ campaign.assigned_count }} · Responses: {{ campaign.completed_count or 0 }} · Clicked: {{ campaign.clicked_count }} · Reported: {{ campaign.reported_count }}</p>
          <p style="margin:10px 0 0;"><a href="{{ url_for('campaign_report_view', campaign_id=campaign.id) }}" style="color:#39d5e0;">View readiness report →</a></p>
        </div>
      {% else %}
        <p style="color:#7ca8c9;">No campaigns scheduled yet.</p>
      {% endfor %}
    </div>
    {% if agent_alerts %}
    <div class="card">
      <h2>Training Recommendations</h2>
      <p style="color:#7ca8c9;margin:8px 0 0;">Transparent rules review simulated training signals and suggest follow-up learning. No account lockout, network isolation, or external escalation is performed.</p>
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
          <strong>Execution status:</strong> {{ alert.isolation_details }}<br/>
          <strong>Status:</strong> {{ alert.escalation_status }}
        </div>
      </div>
      {% endfor %}
    </div>
    {% endif %}
    <div class="card">
      <div class="header">
        <div>
          <h2>Simulation Activity</h2>
          <p style="color:#7ca8c9;margin:8px 0 0;">Review the controlled simulation, affected demo profile, and recorded status.</p>
        </div>
        <form method="POST" action="/admin/actions" style="display:flex;gap:12px;flex-wrap:wrap;align-items:center;">
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />
          <button name="action" value="run_sentinel">Close demo events</button>
          <button name="action" value="export_events">Export simulation records</button>
        </form>
      </div>
      {% for event in events %}
      <div class="event-item">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:14px;">
          <div>
            <strong>{{ event.title }}</strong>
            <p style="margin:8px 0 0;color:#7ca8c9;">{{ event.user }} · {{ event.timestamp }}</p>
          </div>
          <span class="pill {{ event.level }}">{{ event.level|upper }} training signal</span>
        </div>
        <p style="margin:14px 0 0;color:#c7dfea;">{{ event.details }}</p>
        <div style="margin-top:14px;color:#8da8c3;font-size:.95rem;display:grid;grid-template-columns:repeat(3,minmax(120px,1fr));gap:12px;">
          <span><strong>IP</strong><br />{{ event.source_ip or 'Unknown' }}</span>
          <span><strong>Host</strong><br />{{ event.source_host or 'Unknown' }}</span>
          <span><strong>Network</strong><br />{{ event.source_network or 'Unknown' }}</span>
        </div>
        <div style="margin-top:12px;color:#99bcd9;font-size:.95rem;"><strong>Response:</strong> Demo event recorded only. No device or network isolation was performed.</div>
      </div>
      {% endfor %}
    </div>
    <div class="card note">
      <strong>Admin guidance:</strong> Review the evidence, assign targeted learning, and document any real-world response separately. The actions shown here are simulation records.
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
  <title>Employee Security Learning</title>
  <style>
    body{margin:0;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:radial-gradient(circle at top left, rgba(57,213,224,.16), transparent 30%), linear-gradient(180deg, #02101d 0%, #061b2d 100%);color:#e9f7ff;}
    .page{padding:24px;max-width:1000px;margin:0 auto;}
    .header{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:14px;margin-bottom:24px;}
    h1{margin:0;font-size:2rem;}
    a.logout,button.logout{display:inline-block;padding:10px 14px;background:#1f4260;color:#fff;border:0;border-radius:12px;text-decoration:none;font-size:.9rem;cursor:pointer;}
    .inbox-container{background:#0f1f30;border:1px solid rgba(255,255,255,.06);border-radius:20px;padding:20px;}
    .email-item{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:18px;margin-bottom:14px;cursor:pointer;transition:all .2s ease;}
    .email-item:hover{background:rgba(255,255,255,.08);border-color:rgba(57,213,224,.3);transform:translateX(4px);}
    .email-header{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:12px;}
    .email-from{font-weight:700;color:#39d5e0;}
    .email-subject{color:#e9f7ff;font-weight:600;}
    .email-time{color:#7ca8c9;font-size:.85rem;}
    .email-preview{color:#a7cfe5;font-size:.9rem;margin:12px 0;}
    .attachment{display:inline-block;background:rgba(57,213,224,.12);color:#39d5e0;padding:8px 12px;border-radius:8px;font-size:.85rem;font-weight:600;margin-top:10px;}
    .training-notice{background:rgba(255,108,108,.12);border:2px solid rgba(255,108,108,.3);border-radius:16px;padding:24px;margin-bottom:24px;color:#ff8b8b;}
    .training-notice h2{margin-top:0;color:#ff6c6c;}
    .training-notice p{line-height:1.6;margin:8px 0;}
    .training-notice strong{color:#ff9999;}
    .awareness-box{background:rgba(255,255,255,.05);border-left:4px solid #39d5e0;border-radius:12px;padding:16px;margin-top:16px;color:#c7dfea;}
    .awareness-box strong{color:#39d5e0;}
    .status-chip{display:inline-block;padding:8px 12px;border-radius:999px;font-size:.85rem;font-weight:700;background:rgba(255,108,108,.14);color:#ff6c6c;}
  </style>
</head>
<body>
  <div class="page">
    <div class="header">
      <div>
        <h1>Security Learning</h1>
        <p style="color:#7ca8c9;margin:8px 0 0;">{{ user_name }} · {{ department }}</p>
      </div>
      <form method="POST" action="/logout" style="display:inline;margin:0;">
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}" /><button class="logout" type="submit">Logout</button></form>
    </div>

    <div class="inbox-container" style="margin-bottom:20px;">
      <h2>Scheduled security checks</h2>
      <p style="color:#7ca8c9;">Review each controlled scenario and choose the response you would take. Never enter a real password or authentication code.</p>
      {% for assignment in assignments %}
        <div class="email-item">
          <div class="email-header">
            <div>
              <div class="email-from">{{ assignment.scenario_sender }}</div>
              <div class="email-subject">{{ assignment.scenario_subject }}</div>
              <div class="email-preview">{{ assignment.scenario_message }}</div>
            </div>
            <div class="email-time">{{ assignment.status }}</div>
          </div>
          <p style="color:#a7cfe5;">Campaign: {{ assignment.campaign_name }} · {{ assignment.scenario_title }}</p>
          {% if assignment.status == 'assigned' %}
            <form method="POST" action="{{ url_for('assessment_respond', assignment_id=assignment.id) }}" style="display:flex;flex-wrap:wrap;gap:10px;">
              <input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />
              <button name="interaction" value="reported" type="submit">Report as suspicious</button>
              <button name="interaction" value="clicked" type="submit">I would open it</button>
              <button name="interaction" value="ignored" type="submit">Ignore for now</button>
            </form>
          {% else %}
            <p><strong>Recorded response:</strong> {{ assignment.interaction }} · {{ assignment.signal }}</p>
            <div class="awareness-box">
              <strong>🎓 {{ assignment.lesson_title }}</strong>
              <p>{{ assignment.lesson }}</p>
              <p><strong>Next step:</strong> {{ assignment.next_step }}</p>
              {% if assignment.learning_status == 'completed' %}
                <p>Learning completed.</p>
              {% else %}
                <form method="POST" action="{{ url_for('learning_complete', assignment_id=assignment.id) }}">
                  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />
                  <button type="submit">Mark lesson complete</button>
                </form>
              {% endif %}
            </div>
          {% endif %}
        </div>
      {% else %}
        <p style="color:#7ca8c9;">No scheduled assessments are assigned to this account yet.</p>
      {% endfor %}
    </div>

    {% if user_profile and user_profile.status in ['Needs Review', 'Training Recommended'] %}
    <div class="training-notice">
      <h2>⚠️ Additional Training Guidance Recommended</h2>
      <p><strong>Demo profile status:</strong> <span class="status-chip">HIGH RISK</span></p>
      <p><strong>Training indicator:</strong> {{ user_profile.risk_score }} points (review threshold reached)</p>
      <p><strong>Reason:</strong> Your training indicator reached the configured review threshold after a controlled simulation. No real company account has been locked by this prototype.</p>
      <p><strong>What Happened:</strong> The exercise recorded an interaction with a simulated security scenario. It did not capture real credentials or establish access to company systems.</p>
      <p><strong>Next Steps:</strong></p>
      <ul style="margin:8px 0;padding-left:20px;">
        <li>Contact your IT/Security team immediately</li>
        <li>Report suspicious messages using your organisation's approved process</li>
        <li>Review the short security lesson below</li>
        <li>Apply the guidance in the next simulation</li>
      </ul>
      <div class="awareness-box">
        <strong>🎓 Recommended Cyber Awareness:</strong>
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
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />
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
      <strong>Inbox Help:</strong> This is a controlled security-awareness simulation. Your interaction is recorded as a training signal only. Never enter a real password, authentication code, or personal information.
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
<title>ECOSHIELD Security Readiness</title>
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
      <h1>ECOSHIELD Security Readiness</h1>
      <p class="intro">A lightweight small-team prototype for controlled security simulations, explainable risk signals, employee learning, and follow-up review.</p>
    </div>
    <div class="card" style="min-width:280px;">
      <div class="metric"><strong>{{active_events}}</strong><span>Active simulations</span></div>
      <div class="metric"><strong>{{risk_score}}</strong><span>Readiness indicator</span></div>
      <div class="metric"><strong>{{review_count}}</strong><span>Profiles needing review</span></div>
    </div>
  </header>

  <div class="grid">
    <section class="card span6">
      <h2>Controlled Security Simulations</h2>
      <p style="color:var(--muted);margin-bottom:18px;">Run a controlled training scenario, record the response, and identify where employees may need guidance.</p>
      <div class="button-row">
        {% for trap in traps %}
          <form method="POST" action="/trigger" style="margin:0;">
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />
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
      <h2>Simulation Activity</h2>
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
      <h2>Readiness Summary</h2>
      <div class="mini-grid">
        <div class="mini-card"><strong>{{incident_summary.highest_risk}}</strong><div style="color:var(--muted);margin-top:8px;">Highest training indicator</div></div>
        <div class="mini-card"><strong>{{incident_summary.recent_user}}</strong><div style="color:var(--muted);margin-top:8px;">Recent participant</div></div>
        <div class="mini-card"><strong>{{incident_summary.actions_taken}}</strong><div style="color:var(--muted);margin-top:8px;">Training recommendations</div></div>
      </div>
    </section>

  </div>
</div>

{% if notice_event %}
<div class="modal-overlay">
  <div class="modal-content">
    <h3>Security Awareness Notice</h3>
    <p>This simulation is a controlled training environment from EcoTechLabs.</p>
    <p><strong>{{notice_event.user}}</strong> interacted with a simulated security scenario. No real credentials were collected.</p>
    <p>{{notice_event.details}}</p>
    <p style="color:var(--muted);">Recommended actions: report the suspicious message, review the relevant learning guidance, and apply it during the next assessment.</p>
    <form method="POST" action="/api/report">
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}" />
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
    <p>Your incident report has been recorded. The administrator can review it in this demo.</p>
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
    {"id": "finance-phish", "label": "Finance Phishing Email", "sender": "finance@bank-update.example", "preview": "Urgent: Review your account - Open the message", "user": "Alice Vance", "department": "Finance", "impact": 18, "event_type": "Phishing Link Interaction"},
    {"id": "hr-benefits", "label": "HR Benefits Alert", "sender": "HR Department", "preview": "New benefits package available - Review document", "user": "Marcus Ward", "department": "Human Resources", "impact": 14, "event_type": "Phishing Click"},
    {"id": "it-maintenance", "label": "IT Maintenance Notice", "sender": "IT Support <support@company.local>", "preview": "Scheduled maintenance - Review the notice", "user": "Sarah Connor", "department": "IT Operations", "impact": 17, "event_type": "Suspicious Link"},
    {"id": "exec-target", "label": "Executive Fraud Link", "sender": "CEO Office", "preview": "Confidential: Board meeting minutes attached", "user": "Alice Vance", "department": "Finance", "impact": 22, "event_type": "Suspicious Access"},
    {"id": "benefits-update", "label": "Policy Update", "sender": "Compliance Team", "preview": "Updated security policy - Action required", "user": "Marcus Ward", "department": "Human Resources", "impact": 12, "event_type": "Suspicious Link"},
    {"id": "it-alert", "label": "Account Verification", "sender": "Security <security@company.local>", "preview": "Unusual login detected - Review the alert", "user": "Sarah Connor", "department": "IT Operations", "impact": 16, "event_type": "Suspicious Access"}
]

EVENT_TEMPLATES = {
    "Phishing Link Interaction": "A controlled phishing link interaction was recorded. No credentials were requested or collected.",
    "Phishing Click": "A user interacted with a simulated HR-style link. No real session was exposed.",
    "Password Entry": "A user reached a simulated maintenance page. No password field or credential collection was used.",
    "Suspicious Access": "An exec-style phishing page triggered a high-risk access event.",
    "Suspicious Link": "A policy update lure generated anomalous user behavior.",
    "Credential Replay": "A simulated suspicious-access signal was recorded; no credentials were collected or replayed.",
}

STATUS_COLORS = [(0, "low"), (35, "mid"), (50, "high")]


DB_PATH = os.environ.get('ECOSHIELD_DB_PATH', 'ecoshield.db')


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
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
    initialize_assessment_schema(conn)
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


def calculate_review_count():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM employees WHERE status = 'Needs Review'")
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
    if new_score >= 50 and row['status'] != 'Needs Review':
        new_status = 'Needs Review'
    elif new_score >= 35 and row['status'] == 'Secure':
        new_status = 'Training Recommended'
    cur.execute('UPDATE employees SET risk_score = ?, status = ? WHERE id = ?', (new_score, new_status, row['id']))
    conn.commit()
    conn.close()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM employees WHERE status = 'Needs Review'")
    count = cur.fetchone()[0]
    conn.close()
    return count


def run_rule_watcher(trap):
    """Apply transparent demo rules to a simulation event and record recommendations."""
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
    
    # Rule-based training-signal review
    action = None
    reason = None
    severity = 'LOW'
    
    # Multiple incidents = high risk pattern
    if event_count >= 3:
        reason = f"Repeated simulated interactions were recorded ({event_count} events). Review the pattern privately and offer relevant guidance."
        severity = 'HIGH'
        action = 'REVIEW_REPEATED_TRAINING_SIGNALS'
    
    # High training indicator threshold
    if risk_score >= 50 and current_status == 'Needs Review':
        reason = f"The training indicator reached the review threshold ({risk_score} points). This is not evidence of account compromise; review the employee's learning needs."
        severity = 'CRITICAL'
        action = 'REVIEW_TRAINING_INDICATOR'
    
    # Medium risk pattern
    elif risk_score >= 35 and event_count >= 2:
        reason = f"Repeated training signals indicate a possible learning gap (indicator: {risk_score}). Recommend targeted security awareness guidance."
        severity = 'MEDIUM'
        action = 'ASSIGN_TARGETED_LEARNING'
    
    # Single high-impact incident
    elif trap['impact'] >= 15 and event_count == 1:
        reason = f"A simulated scenario recorded a training signal: {trap['event_type']}. Recommend reviewing the relevant awareness lesson."
        severity = 'MEDIUM'
        action = 'ASSIGN_TARGETED_LEARNING'
    
    # Create agent action record if action triggered
    if action:
        source = SOURCE_INFOS.get(trap['user'], {'network': 'Unclassified'})
        isolation_details = 'No account lockout, device isolation, or access revocation was performed; this is a training recommendation only.'
        escalation_status = 'SIMULATED_RECOMMENDATION_ONLY'
        
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
    cur.execute('SELECT COUNT(*) FROM agent_actions')
    action_count = cur.fetchone()[0]
    conn.close()
    return {
        'highest_risk': f"{highest} pts",
        'recent_user': latest_user,
        'actions_taken': action_count
    }


def process_sentinel():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE events SET status = 'completed' WHERE status = 'active'")
    cur.execute("UPDATE employees SET status = 'Needs Review' WHERE risk_score >= 50")
    conn.commit()
    conn.close()


def get_agent_alerts(limit=10):
    """Retrieve rule-based training recommendations."""
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
@login_required
def api_report():
    data = request.form if request.form else (request.get_json(silent=True) or {})
    try:
        event_id = int(data.get('event_id'))
    except (TypeError, ValueError):
        return jsonify({'error': 'A valid event_id is required'}), 400
    note = str(data.get('note', '')).strip()[:2000]
    conn = get_db_connection()
    cur = conn.cursor()
    event = cur.execute('SELECT user FROM events WHERE id = ?', (event_id,)).fetchone()
    if not event:
        conn.close()
        return jsonify({'error': 'Event not found'}), 404
    user = event['user']
    if get_current_user() == 'employee' and user != session.get('user_name'):
        conn.close()
        return jsonify({'error': 'You may only report your own events'}), 403
    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    cur.execute('INSERT INTO reports (timestamp, user, event_id, note) VALUES (?, ?, ?, ?)', (ts, user, event_id, note))
    conn.commit()
    conn.close()
    if request.is_json:
        return jsonify({'ok': True}), 201
    return redirect(url_for('dashboard', notice_id=event_id, reported='1'))


@app.route('/admin/actions', methods=['POST'])
@admin_required
def admin_actions():
    action = request.form.get('action')
    if action == 'run_sentinel':
        process_sentinel()
        return redirect(url_for('dashboard'))
    if action == 'export_events':
        return redirect(url_for('export_events', format='csv'))
    return redirect(url_for('dashboard'))


@app.route('/export')
@admin_required
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
@admin_required
def api_status():
    profiles = get_profiles()
    return jsonify({
        'active_events': sum(1 for e in get_latest_events() if e['status'] == 'active'),
        'risk_score': current_risk_score(),
        'review_count': calculate_review_count(),
        'profiles': profiles,
    })


@app.route('/api/events')
@admin_required
def api_events():
    return jsonify(get_latest_events(50))


@app.route('/api/profiles')
@admin_required
def api_profiles():
    return jsonify(get_profiles())


@app.route('/api/readiness/analyze', methods=['POST'])
@app.route('/api/ai/analyze', methods=['POST'])  # Backwards-compatible legacy path.
@admin_required
def readiness_analyze():
    """Legacy endpoint name; this is transparent rule-based training analysis, not AI."""
    data = request.get_json(silent=True) or request.form
    events = data.get('events') or []
    if not events:
        return jsonify({
            'analysis_type': 'rule_based_training_signal',
            'summary': 'No simulation events were provided.',
            'suggestions': [],
            'real_containment_performed': False,
        })
    highest = max(events, key=lambda event: event.get('impact', 0))
    summary = (
        f"Reviewed {len(events)} supplied simulation event(s). The highest training-signal "
        f"impact was {highest.get('impact', 0)} for {highest.get('event_type', 'a scenario')}. "
        "This is an awareness indicator, not evidence of compromise."
    )
    suggestions = [
        'Review the interaction privately and non-punitively with the employee.',
        'Assign the short learning item that matches the scenario.',
        'Run a later controlled retest to check whether the behaviour improves.',
    ]
    return jsonify({
        'analysis_type': 'rule_based_training_signal',
        'summary': summary,
        'suggestions': suggestions,
        'real_containment_performed': False,
    })


if __name__ == '__main__':
    initialize_database()
    ensure_seed_data()
    app.run(host=os.environ.get('ECOSHIELD_HOST', '127.0.0.1'), port=int(os.environ.get('PORT', '5000')), debug=False)
