import hmac
import os
import sqlite3

from flask import Flask, Response, abort, render_template_string, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)

# Keep the simulator credential outside source control. Set
# ECOSHIELD_SIMULATION_TOKEN in the environment before enabling capture.
SIMULATION_USERNAME = "simulator"

limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
    default_limits=[],
)

BRAND_CONFIG = {
    "finance": {
        "name": "EcoFinance Bank",
        "accent": "#2c3e50",
        "msg": "Suspicious Transaction Alert",
        "department": "Finance",
    },
    "hr": {
        "name": "EcoHealth Solutions",
        "accent": "#27ae60",
        "msg": "Annual Benefits Enrollment",
        "department": "Human Resources",
    },
    "it": {
        "name": "EcoTech Systems",
        "accent": "#2980b9",
        "msg": "System Maintenance Required",
        "department": "IT Operations",
    },
}

HTML_LAYOUT = """
<div style="font-family: 'Segoe UI', sans-serif; max-width: 400px; margin: 80px auto; border-top: 8px solid {{ accent }}; padding: 30px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); border-radius: 5px;">
    <h1 style="color: #333; font-size: 22px;">🛡️ {{ name }}</h1>
    <p style="color: #666; font-size: 14px;"><strong>Simulation:</strong> {{ msg }}</p>
    <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
    <p style="font-size: 13px; color: #555;">
        This controlled exercise records a simulated department-level risk event.
        Do not enter personal information or real credentials.
    </p>
    <form method="POST" action="/capture">
        <input type="hidden" name="dept" value="{{ dept_key }}">
        <button type="submit" style="background:{{ accent }}; color:white; border:none; padding:12px; width:100%; border-radius:3px; cursor:pointer; font-weight:bold;">
            Run Security Simulation
        </button>
    </form>
    <p style="text-align:center; font-size:10px; color:#999; margin-top:20px;">&copy; 2026 EcoTechLabs Security Simulations</p>
</div>
"""


def require_simulator_auth():
    """Require HTTP Basic auth using a token configured outside the repository."""
    expected_token = os.environ.get("ECOSHIELD_SIMULATION_TOKEN")
    if not expected_token:
        abort(
            503,
            description=(
                "Simulation capture is disabled. Configure "
                "ECOSHIELD_SIMULATION_TOKEN on the server."
            ),
        )

    credentials = request.authorization
    supplied_token = credentials.password if credentials else ""
    valid_user = credentials is not None and credentials.username == SIMULATION_USERNAME
    valid_token = hmac.compare_digest(supplied_token or "", expected_token)

    if not (valid_user and valid_token):
        return Response(
            "Simulator authentication required.",
            401,
            {"WWW-Authenticate": 'Basic realm="ECOSHIELD Simulator"'},
        )
    return None


@app.route("/")
def index():
    dept_key = request.args.get("dept", "it").strip().lower()
    if dept_key not in BRAND_CONFIG:
        abort(400, description="Unknown simulation department.")

    brand = BRAND_CONFIG[dept_key]
    return render_template_string(
        HTML_LAYOUT,
        name=brand["name"],
        accent=brand["accent"],
        msg=brand["msg"],
        dept_key=dept_key,
    )


@app.route("/capture", methods=["POST"])
@limiter.limit("5 per minute")
def capture():
    auth_error = require_simulator_auth()
    if auth_error is not None:
        return auth_error

    dept_key = request.form.get("dept", "").strip().lower()
    brand = BRAND_CONFIG.get(dept_key)
    if brand is None:
        abort(400, description="Unknown simulation department.")

    try:
        with sqlite3.connect("ecoshield.db", timeout=5) as conn:
            cursor = conn.execute(
                """
                UPDATE employees
                SET risk_score = risk_score + 25,
                    status = 'Compromised'
                WHERE department = ?
                """,
                (brand["department"],),
            )
            if cursor.rowcount == 0:
                abort(404, description="No employee records found for this department.")
    except sqlite3.Error:
        app.logger.exception("Unable to record ECOSHIELD simulation event.")
        abort(500, description="Unable to record the simulation event.")

    return (
        "<div style='text-align:center; font-family:sans-serif; margin-top:100px;'>"
        "<h2>🚨 ECOSHIELD AGENT ALERT</h2>"
        "<p>This was a controlled security test by <b>EcoTechLabs</b>. "
        "Please report this to your supervisor.</p></div>"
    )


if __name__ == "__main__":
    app.run(port=5000)
